"""CART-01: origem humana, revisão, replay e recuperação; rede inteiramente falsa."""

import copy
import io
import json
import tempfile
import time
import unittest
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import URLError

from telegram_bot.backend import BackendConfig, LinkStatus
from telegram_bot.cart import Carts, review_text
from telegram_bot.cart_client import CartClient, CartError
from telegram_bot.cart_view import current_text
from telegram_bot.config import Config
from telegram_bot.conversation_contract import Snapshot, encode
from telegram_bot.menu import keyboard
from telegram_bot.runner import process_batch
from telegram_bot.state import State

OWNER, BOT = 111111111, 900001
REFERENCE = "r" * 32
TOKEN = "synthetic-token-" + "x" * 32
REQUEST = "11111111-1111-4111-8111-111111111111"
NOW = 1_800_000_000


def review():
    return {
        "purpose": "PREPARE_CART",
        "confirmationRef": REFERENCE,
        "version": 1,
        "fingerprint": "a" * 64,
        "expiresAt": datetime.fromtimestamp(NOW + 300, UTC).isoformat(),
        "unknownCosts": True,
        "totalCents": None,
        "observedSubtotalCents": 2000,
        "purchaseAuthorized": False,
        "checkoutEnabled": False,
        "lines": [
            {
                "name": "Arroz",
                "itemId": "item-sintetico",
                "quantity": 1,
                "unitMinCents": 2000,
                "unitMaxCents": 2000,
                "consumerIds": ["person-a"],
                "optionIds": [],
            }
        ],
        "changes": [{"tool": "createCart", "args": {}}],
        "remoteItems": [],
        "display": {
            "accountLabel": "Pessoa S. · p***@example.test",
            "merchantName": "Loja sintética",
            "addressLabel": "Casa · Centro · Cidade sintética",
            "items": [{"itemId": "item-sintetico", "name": "Arroz", "options": []}],
        },
    }


def current():
    return {
        "purchaseAuthorized": False,
        "checkoutEnabled": False,
        "paymentEnabled": False,
        "display": review()["display"],
        "cart": {
            "items": [
                {"itemId": "item-sintetico", "quantity": 1, "options": [], "unitPrice": 2000}
            ],
            "totals": {
                "subtotal": 2000,
                "deliveryFee": 500,
                "serviceFee": 100,
                "discount": 0,
                "total": 2600,
            },
        },
        "budget": {"status": "WITHIN_LIMITS"},
    }


def snapshot(version=1):
    return Snapshot(
        encode(
            {
                "blocks": [
                    {
                        "kind": "GROUP",
                        "participants": [
                            {
                                "participantRef": "person-a",
                                "displayName": "Pessoa sintética",
                                "conditions": ["Sem restrições declaradas"],
                            }
                        ],
                    }
                ]
            }
        ),
        version,
        "COLLECTING",
    )


def result(state="SUCCEEDED"):
    return {
        "operationId": "o" * 32,
        "state": state,
        "completedOperations": 1,
        "purpose": "PREPARE_CART",
        "purchaseAuthorized": False,
        "checkoutEnabled": False,
        "paymentEnabled": False,
    }


class Response(io.BytesIO):
    def __init__(self, body, status=200):
        super().__init__(json.dumps(body).encode())
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = "application/json"


class TransportTests(unittest.TestCase):
    def client(self, body):
        opener = Mock()
        opener.open.return_value = Response(body)
        return CartClient(
            BackendConfig("http://localhost:8000", TOKEN, OWNER, True), opener=opener
        ), opener

    def test_exact_human_channel_and_recovery_use_authenticated_scope(self):
        client, opener = self.client(result())
        client.confirm(REFERENCE, REQUEST, "callback-sintetico")
        request = opener.open.call_args.args[0]
        self.assertEqual(
            json.loads(request.data),
            {
                "purpose": "PREPARE_CART",
                "source": "TELEGRAM_CALLBACK",
                "confirmationRef": REFERENCE,
                "requestId": REQUEST,
                "callbackId": "callback-sintetico",
            },
        )
        self.assertEqual(request.get_header("X-telegram-user-id"), str(OWNER))
        self.assertEqual(request.get_header("X-telegram-chat-id"), str(OWNER))
        self.assertEqual(request.get_header("X-telegram-access"), "PASSWORD")
        self.assertNotIn("userId", json.loads(request.data))
        opener.open.return_value = Response(result())
        client.request(REQUEST)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.method, "GET")
        self.assertTrue(request.full_url.endswith("/cart-writes/requests/" + REQUEST))
        self.assertIsNone(request.data)

    def test_timeout_never_retries_post_and_does_not_expose_provider_body(self):
        client, opener = self.client({})
        opener.open.side_effect = URLError("token-privado endereço-sintético")
        with self.assertRaises(CartError) as caught:
            client.confirm(REFERENCE, REQUEST, "callback")
        self.assertTrue(caught.exception.uncertain)
        self.assertNotIn("token-privado", str(caught.exception))
        self.assertEqual(opener.open.call_count, 1)

    def test_invalid_or_authorizing_response_never_reports_success(self):
        for change in [
            {"purchaseAuthorized": True},
            {"paymentEnabled": True},
            {"state": "ORDER_SENT"},
        ]:
            with self.subTest(change=change):
                client, _ = self.client({**result(), **change})
                with self.assertRaises(CartError):
                    client.confirm(REFERENCE, REQUEST, "callback")

    def test_review_unknown_cost_and_contract_are_required(self):
        client, _ = self.client(review())
        self.assertEqual(client.review()["confirmationRef"], REFERENCE)
        for change in [{"totalCents": 0}, {"unknownCosts": False}, {"purpose": "SUBMIT_ORDER"}]:
            client, _ = self.client({**review(), **change})
            with self.assertRaises(CartError):
                client.review()


class CallbackTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.state = State(Path(self.directory.name) / "bot.sqlite3", clock=lambda: NOW)
        self.addCleanup(self.state.close)
        self.client, self.conversation, self.backend = Mock(), Mock(), Mock()
        self.client.review.side_effect = lambda: copy.deepcopy(review())
        self.client.confirm.return_value = result()
        self.client.request.return_value = result()
        self.client.current.return_value = current()
        self.conversation.get_snapshot.return_value = snapshot()
        self.backend.status.return_value = SimpleNamespace(
            state="CONNECTED",
            operational=True,
            allowed_operations=("CART_WRITE",),
            link_id="l" * 24,
        )
        self.api = Mock()
        self.api.send.return_value = {"message_id": 55}
        self.carts = self.make()
        self.addCleanup(lambda: self.carts.close())

    def make(self):
        return Carts(
            self.state,
            self.client,
            self.conversation,
            self.backend,
            BOT,
            OWNER,
            scope="synthetic-scope",
            clock=lambda: NOW,
        )

    def pump(self):
        deadline = time.monotonic() + 3
        while self.carts.future is not None and time.monotonic() < deadline:
            self.carts.tick(self.api)
            time.sleep(0.001)
        self.assertIsNone(self.carts.future)

    def prepare(self):
        self.carts.receive("/revisarcarrinho")
        self.pump()
        self.assertIsNotNone(self.carts.review)
        return {
            "id": "callback-sintetico",
            "from": {"id": OWNER, "is_bot": False},
            "message": {
                "message_id": 55,
                "chat": {"id": OWNER, "type": "private"},
                "from": {"id": BOT, "is_bot": True},
            },
            "data": "cart:" + self.carts.review["button"],
        }

    def test_review_does_not_write_and_valid_human_click_writes_once(self):
        callback = self.prepare()
        self.client.confirm.assert_not_called()
        text = self.api.send.call_args.args[1]
        for fact in [
            "Pessoa sintética",
            "1 × Arroz",
            "R$ 20,00",
            "Total completo desconhecido",
            "NÃO ENVIA",
        ]:
            self.assertIn(fact, text)
        self.assertNotIn(REFERENCE, text)
        self.carts.click(callback)
        self.pump()
        self.carts.click(callback)
        self.client.confirm.assert_called_once()
        self.assertIn("PEDIDO NÃO ENVIADO", self.api.send.call_args.args[1])
        self.assertIn("Total observado: R$ 26,00", self.api.send.call_args.args[1])
        dump = "\n".join(self.state.db.iterdump())
        for secret in [REFERENCE, "Pessoa sintética", "Arroz", callback["id"], callback["data"]]:
            self.assertNotIn(secret, dump)

    def test_failed_final_read_preserves_succeeded_and_never_repeats_confirm(self):
        callback = self.prepare()
        self.client.current.side_effect = CartError()
        self.carts.click(callback)
        self.pump()
        self.assertEqual(self.carts._row()[1], "SUCCEEDED")
        self.assertIn("Não consegui conferir", self.api.send.call_args.args[1])
        self.client.current.side_effect = None
        self.carts.receive("/conferircarrinho")
        self.pump()
        self.assertIn("Total observado: R$ 26,00", self.api.send.call_args.args[1])
        self.client.confirm.assert_called_once()

    def test_lost_confirm_reply_recovers_succeeded_in_same_turn_by_get(self):
        callback = self.prepare()
        self.client.confirm.side_effect = CartError(uncertain=True)
        self.carts.click(callback)
        self.pump()
        self.assertEqual(self.carts._row()[1], "SUCCEEDED")
        self.client.confirm.assert_called_once()
        self.client.request.assert_called_once()

    def test_identity_missing_blocks_button_and_options_and_removal_are_named(self):
        value = review()
        for key in ("accountLabel", "merchantName", "addressLabel"):
            changed = copy.deepcopy(value)
            del changed["display"][key]
            with self.assertRaises(CartError):
                review_text(changed, snapshot())
        value["lines"][0]["optionIds"] = ["option-a"]
        value["display"]["items"][0]["options"] = [
            {"optionId": "option-a", "quantity": 1, "name": "Sem molho"}
        ]
        value["remoteItems"] = [{"itemId": "item-extra", "quantity": 2, "options": []}]
        value["display"]["items"].append({"itemId": "item-extra", "name": "Bebida", "options": []})
        value["changes"] = [{"tool": "removeItemFromCart", "args": {}}]
        shown = review_text(value, snapshot())
        for fact in (
            "Pessoa S.",
            "Loja sintética",
            "Casa",
            "Sem molho",
            "2 × Bebida",
            "remover item",
        ):
            self.assertIn(fact, shown)

    def test_final_costs_malformed_or_changed_do_not_claim_budget_validated(self):
        self.assertIn("R$ 26,00", current_text(current()))
        value = current()
        value["budget"]["status"] = "UNVERIFIED"
        self.assertIn("Orçamento não verificado", current_text(value))
        for change in (None, -1, True, 0.01):
            value = current()
            value["cart"]["totals"]["deliveryFee"] = change
            with self.assertRaises(CartError):
                current_text(value)

    def test_existing_configured_item_uses_one_label_for_current_and_desired(self):
        value = review()
        option = {"optionId": "option-a", "quantity": 1}
        value["lines"][0]["optionIds"] = ["option-a"]
        value["display"]["items"][0]["options"] = [{**option, "name": "Sem molho"}]
        value["remoteItems"] = [{"itemId": "item-sintetico", "quantity": 2, "options": [option]}]
        value["changes"] = [{"tool": "updateCartItem", "args": {}}]
        self.assertIn("2 × Arroz (1 × Sem molho)", review_text(value, snapshot()))
        value["display"]["items"].append(copy.deepcopy(value["display"]["items"][0]))
        with self.assertRaises(CartError):
            review_text(value, snapshot())

    def test_polling_routes_human_callback_outside_conversation_model(self):
        callback = self.prepare()
        conversations = Mock()
        process_batch(
            self.api,
            self.state,
            [{"update_id": 50, "callback_query": callback}],
            OWNER,
            "bot",
            conversations=conversations,
            carts=self.carts,
        )
        self.pump()
        self.client.confirm.assert_called_once()
        conversations.receive.assert_not_called()
        process_batch(
            self.api,
            self.state,
            [{"update_id": 50, "callback_query": callback}],
            OWNER,
            "bot",
            conversations=conversations,
            carts=self.carts,
        )
        self.client.confirm.assert_called_once()

    def test_wrong_person_chat_bot_message_or_forward_cannot_confirm(self):
        callback = self.prepare()
        variants = []
        for field, value in [("message_id", 56), ("forward_origin", {"type": "hidden_user"})]:
            item = copy.deepcopy(callback)
            item["message"][field] = value
            variants.append(item)
        item = copy.deepcopy(callback)
        item["from"]["id"] += 1
        variants.append(item)
        item = copy.deepcopy(callback)
        item["message"]["chat"]["type"] = "group"
        variants.append(item)
        item = copy.deepcopy(callback)
        item["message"]["from"]["id"] += 1
        variants.append(item)
        for item in variants:
            self.carts.click(item)
        self.client.confirm.assert_not_called()
        self.assertIsNone(self.carts.future)

    def test_expired_or_stale_version_preserves_state_and_allows_new_review(self):
        callback = self.prepare()
        self.conversation.get_snapshot.return_value = snapshot(2)
        self.carts.click(callback)
        self.pump()
        self.client.confirm.assert_not_called()
        self.assertEqual(self.carts._row()[1], "FAILED")

    def test_timeout_then_restart_recovers_by_get_without_reference_or_post_replay(self):
        callback = self.prepare()
        self.client.confirm.side_effect = CartError(uncertain=True)
        self.client.request.side_effect = CartError("CART_INTENT_NOT_FOUND")
        self.carts.click(callback)
        self.pump()
        self.assertEqual(self.carts._row()[1], "RESULT_UNKNOWN")
        self.carts.close()
        self.carts = self.make()
        self.assertIsNone(self.carts.review)
        self.assertIn("desconhecido", self.carts.receive("/revisarcarrinho"))
        self.client.request.side_effect = None
        self.carts.receive("/conferircarrinho")
        self.pump()
        self.assertEqual(self.carts._row()[1], "SUCCEEDED")
        self.client.confirm.assert_called_once()

    def test_conversation_input_and_restart_invalidate_old_button(self):
        callback = self.prepare()
        message = {
            "update_id": 1,
            "message": {
                "message_id": 99,
                "from": {"id": OWNER, "is_bot": False},
                "chat": {"id": OWNER, "type": "private"},
                "text": "Corrija o orçamento",
            },
        }
        conversations = Mock()
        conversations.COMMANDS = set()
        conversations.receive.return_value = None
        process_batch(
            self.api,
            self.state,
            [message],
            OWNER,
            "bot",
            conversations=conversations,
            carts=self.carts,
        )
        self.carts.click(callback)
        self.client.confirm.assert_not_called()
        self.carts.close()
        self.carts = self.make()
        self.carts.click(callback)
        self.client.confirm.assert_not_called()

    def test_telegram_uncertain_review_delivery_does_not_leave_usable_reference(self):
        from telegram_bot.telegram import TelegramError

        self.api.send.side_effect = TelegramError(500)
        self.carts.receive("/revisarcarrinho")
        self.pump()
        self.assertIsNone(self.carts.review)
        self.client.confirm.assert_not_called()

    def test_incomplete_options_or_unlabeled_removal_block_button(self):
        for mutate in [
            lambda x: x["lines"][0]["optionIds"].append("option-unknown"),
            lambda x: x["remoteItems"].append({"itemId": "unknown", "quantity": 1, "options": []}),
        ]:
            doc = review()
            mutate(doc)
            with self.assertRaises(CartError):
                review_text(doc, snapshot())

    def test_malformed_remote_item_blocks_review_without_stopping_polling(self):
        self.client.review.return_value = {**review(), "remoteItems": [None]}
        self.client.review.side_effect = None
        self.carts.receive("/revisarcarrinho")
        self.pump()
        self.assertIsNone(self.carts.review)
        self.client.confirm.assert_not_called()
        self.assertIn("revisão completa e válida", self.api.send.call_args.args[1])

    def test_group_budget_and_previous_remote_costs_are_visible_and_distinct(self):
        doc = snapshot().to_dict()
        doc["blocks"][0]["budgetCents"] = 3000
        doc["blocks"].append(
            {"kind": "TEXT", "source": "SERVER", "text": "Orçamento do grupo: R$ 30.00 (máximo)."}
        )
        current = Snapshot(encode(doc), 1, "COLLECTING")
        value = {
            **review(),
            "remoteCosts": {
                "subtotal": 1000,
                "deliveryFee": 500,
                "serviceFee": 100,
                "discount": 0,
                "total": 1600,
            },
        }
        text = review_text(value, current)
        for fact in [
            "R$ 30,00 (máximo)",
            "antes destas alterações",
            "Entrega: R$ 5,00",
            "Total atual: R$ 16,00",
            "Subtotal observado dos itens: R$ 20,00",
            "Total completo desconhecido",
        ]:
            self.assertIn(fact, text)
        value["remoteCosts"]["total"] = 0
        with self.assertRaises(CartError):
            review_text(value, current)

    def test_expired_review_and_malformed_callback_never_send_confirm(self):
        value = review()
        value["expiresAt"] = datetime.fromtimestamp(NOW, UTC).isoformat()
        self.client.review.side_effect = lambda: value
        self.carts.receive("/revisarcarrinho")
        self.pump()
        self.assertIsNone(self.carts.review)
        self.client.review.side_effect = lambda: review()
        callback = self.prepare()
        for malformed in [
            {**callback, "message": None},
            {**callback, "from": None},
            {**callback, "message": {"chat": None}},
        ]:
            self.carts.click(malformed)
        self.client.confirm.assert_not_called()

    def test_disabled_navigation_never_enters_conversation_model(self):
        conversations = Mock()
        conversations.COMMANDS = set()
        update = {
            "update_id": 1,
            "message": {
                "from": {"id": OWNER, "is_bot": False},
                "chat": {"id": OWNER, "type": "private"},
                "text": "Revisar carrinho",
            },
        }
        process_batch(self.api, self.state, [update], OWNER, "bot", conversations=conversations)
        conversations.receive.assert_not_called()
        self.assertIn("indisponível", self.api.send.call_args.args[1])


class ConfigurationTests(unittest.TestCase):
    def test_opt_in_is_separate_and_requires_conversation(self):
        env = {"TELEGRAM_BOT_TOKEN": "900001:" + "x" * 30, "TELEGRAM_ALLOWED_USER_ID": str(OWNER)}
        with patch.dict("os.environ", env, clear=True):
            self.assertFalse(Config.from_env().cart_enabled)
        for flag in ["true", "invalid"]:
            with (
                patch.dict("os.environ", {**env, "TELEGRAM_CART_ENABLED": flag}, clear=True),
                self.assertRaises(ValueError),
            ):
                Config.from_env()
        self.assertNotIn("Revisar carrinho", str(keyboard()))
        self.assertIn("Revisar carrinho", str(keyboard(cart=True)))

    def test_link_status_accepts_only_item_cart_scopes_without_authorizing_payment(self):
        data = {
            "state": "CONNECTED",
            "operational": True,
            "linkId": "l" * 24,
            "attempt": None,
            "allowedOperations": ["CART_READ", "CART_WRITE"],
        }
        self.assertIn("CART_WRITE", LinkStatus.parse(data).allowed_operations)
