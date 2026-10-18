"""Regressores da demo: transporte Telegram fiel, RUN-01/MCP/modelo sintéticos."""

import copy
import hashlib
import io
import json
from datetime import UTC, datetime
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

from test_conversation_worker import BOT, OWNER, FakeClient, Fixture, update

from telegram_bot.backend import LinkStatus
from telegram_bot.conversation_contract import encode
from telegram_bot.conversation_runner import Conversations, ConversationWorker
from telegram_bot.runner import process_batch
from telegram_bot.telegram import Telegram, TelegramError

LINK = "synthetic-link-xxxxxxxxxxxxxxxx"


class TelegramWire:
    """Reproduz a restrição documentada: ReplyKeyboardMarkup não pode ser editado."""

    def __init__(self):
        self.messages = {}
        self.edits = 0
        self.lose_edit_ack = False

    def open(self, request, timeout=None):
        method = request.full_url.rsplit("/", 1)[-1]
        body = json.loads(request.data)
        result = True
        if method == "sendMessage":
            mid = len(self.messages) + 1
            self.messages[mid] = body
            result = {"message_id": mid}
        elif method == "editMessageText":
            self.edits += 1
            old = self.messages[body["message_id"]]
            if "keyboard" in old.get("reply_markup", {}):
                return io.BytesIO(
                    encode(
                        {
                            "ok": False,
                            "error_code": 400,
                            "description": "Bad Request: message can't be edited",
                        }
                    )
                )
            if old["text"] == body["text"]:
                return io.BytesIO(
                    encode(
                        {
                            "ok": False,
                            "error_code": 400,
                            "description": "Bad Request: message is not modified",
                        }
                    )
                )
            self.messages[body["message_id"]] = body
            if self.lose_edit_ack:
                self.lose_edit_ack = False
                raise URLError("sintético: resposta da edição perdida")
        return io.BytesIO(encode({"ok": True, "result": result}))


class ContinuityTests(Fixture):
    def test_edit_errors_are_classified_for_http_and_json_without_exposing_description(self):
        for description, expected in (
            ("Bad Request: message can't be edited", "EDIT_UNAVAILABLE"),
            ("Bad Request: message to edit not found", "EDIT_UNAVAILABLE"),
            ("Bad Request: message is not modified", "NOT_MODIFIED"),
            ("Bad Request: invalid markup", "OTHER"),
            ([], "OTHER"),
        ):
            for http in (False, True):
                with self.subTest(description=description, http=http):
                    body = encode({"ok": False, "error_code": 400, "description": description})
                    opener = Mock()
                    if http:
                        opener.open.side_effect = HTTPError(
                            "http://synthetic", 400, "synthetic", {}, io.BytesIO(body)
                        )
                    else:
                        opener.open.return_value = io.BytesIO(body)
                    with self.assertRaises(TelegramError) as caught:
                        Telegram("synthetic-token", opener).call("editMessageText", {})
                    self.assertEqual(caught.exception.reason, expected)
                    self.assertEqual(caught.exception.code, 400)
                    self.assertNotIn("Bad Request", str(caught.exception))

    def test_legacy_uneditable_progress_recovers_and_drains_next_text_without_command(self):
        self.real_telegram()
        self.client.finish = False
        self.adapter.receive(update())
        self.tick(3)
        # Mensagem enviada por versão antiga, com teclado que impede edição.
        self.seed_legacy_progress()
        self.wire.messages[1]["reply_markup"] = {"keyboard": [[{"text": "Ajuda"}]]}
        row = self.box.active()
        self.box.save(row["seq"], state="DELIVERY_UNKNOWN", attempts=3)
        self.adapter.receive(update(2, "Mais uma mensagem"))
        self.client.finish = True
        self.worker = ConversationWorker(
            self.restart_box(), self.client, self.worker.telegram, OWNER, clock=lambda: self.now
        )
        self.tick(12)
        self.assertIsNone(self.box.active())
        self.assertEqual(len(self.client.sent), 2)  # Um POST por texto, sem replay.
        self.assertEqual(len(self.wire.messages), 3)
        self.assertIn("Resposta sintética", self.wire.messages[2]["text"])
        self.assertNotIn("keyboard", self.wire.messages[2]["reply_markup"])

    def test_uneditable_progress_is_replaced_automatically_on_live_delivery(self):
        self.real_telegram()
        self.client.finish = False
        self.adapter.receive(update())
        self.tick(3)
        self.seed_legacy_progress()
        self.wire.messages[1]["reply_markup"] = {"keyboard": [[{"text": "Ajuda"}]]}
        self.client.finish = True
        self.tick(6)
        self.assertIsNone(self.box.active())
        self.assertEqual(len(self.wire.messages), 2)
        self.assertEqual(len(self.client.sent), 1)

    def test_known_delivery_recovery_budget_survives_restart(self):
        self.client.finish = False
        self.adapter.receive(update())
        self.tick(3)
        self.seed_legacy_progress()
        row = self.box.active()
        self.box.save(row["seq"], state="DELIVERY_UNKNOWN", attempts=3)
        self.telegram.call.side_effect = TelegramError(400)  # Erro não classificado.
        self.client.finish = True
        self.tick(8)
        self.assertEqual(self.box.active()["state"], "DELIVERY_UNKNOWN")
        self.assertEqual(self.box.active()["delivery_recoveries"], 1)
        self.assertIsNone(self.restart_box().next())
        self.assertEqual(len(self.client.sent), 1)

    def real_telegram(self):
        self.wire = TelegramWire()
        self.worker.telegram = Telegram("synthetic-token", self.wire)

    def test_pending_operation_is_silent_and_duplicate_update_does_not_send_again(self):
        self.real_telegram()
        self.client.finish = False
        self.adapter.receive(update())
        self.tick(3)
        self.assertEqual(self.wire.messages, {})
        self.assertEqual(self.box.active()["state"], "ACCEPTED")
        self.client.finish = True
        self.tick(4)
        self.adapter.receive(update())
        self.tick(3)
        self.assertIsNone(self.box.active())
        self.assertIn("Resposta sintética", self.wire.messages[1]["text"])
        self.assertEqual(len(self.wire.messages), 1)
        self.assertEqual(len(self.client.sent), 1)

    def test_ack_lost_after_edit_recovers_same_message_without_duplicate_or_model_call(self):
        self.real_telegram()
        self.client.finish = False
        self.adapter.receive(update())
        self.tick(3)
        self.seed_legacy_progress()
        self.wire.lose_edit_ack = True
        self.client.finish = True
        self.tick()
        self.now += 10
        self.tick(5)
        self.assertIsNone(self.box.active())
        self.assertEqual(len(self.wire.messages), 1)
        self.assertEqual(len(self.client.sent), 1)

    def test_restart_delivers_pending_result_without_another_event(self):
        self.real_telegram()
        self.client.finish = False
        self.adapter.receive(update())
        self.tick(3)
        self.client.finish = True
        self.worker = ConversationWorker(
            self.restart_box(), self.client, self.worker.telegram, OWNER, clock=lambda: self.now
        )
        self.tick(4)
        self.assertIsNone(self.box.active())
        self.assertEqual(len(self.wire.messages), 1)
        self.assertEqual(len(self.client.sent), 1)

    def test_oauth_releases_only_safe_known_operation_lookup_once(self):
        self.adapter.receive(update())
        self.tick(2)
        row = self.box.active()
        self.box.save(row["seq"], state="PAUSED", notice="UNAVAILABLE", attempts=3)
        status = LinkStatus("CONNECTED", True, ("ADDRESSES_READ",), None, None, LINK)
        self.adapter.restore_after_login(status, "oauth-synthetic")
        self.assertEqual(self.box.get(row["seq"])["state"], "ACCEPTED")
        self.worker.link_status = lambda: status
        self.tick(8)
        self.assertEqual(len(self.client.sent), 1)
        self.assertIsNone(self.box.active())

    def test_oauth_does_not_release_unknown_delivery_or_unknown_remote_result(self):
        self.adapter.receive(update())
        self.tick(2)
        row = self.box.active()
        self.box.save(row["seq"], state="DELIVERY_UNKNOWN", attempts=3)
        self.adapter.restore_after_login(
            LinkStatus("CONNECTED", True, ("ADDRESSES_READ",), None, None, LINK), "oauth-other"
        )
        self.assertEqual(self.box.get(row["seq"])["state"], "DELIVERY_UNKNOWN")


class AddressClient(FakeClient):
    addresses_supported = True
    bot_id = BOT
    organizer_id = OWNER

    def __init__(self, now):
        super().__init__()
        self.now = now
        self.options = ["Casa · Centro", "Trabalho · Bairro sintético"]
        self.selected = []
        self.address_failure = None

    def get_addresses(self):
        if self.address_failure:
            raise self.address_failure
        return {
            "state": "CHOICE_REQUIRED" if self.options else "EMPTY",
            "linkHash": hashlib.sha256(LINK.encode()).hexdigest(),
            "options": [
                {
                    "choiceRef": str(i) * 32,
                    "label": label,
                    "expiresAt": datetime.fromtimestamp(self.now() + 300, UTC).isoformat(),
                }
                for i, label in enumerate(self.options, 1)
            ],
        }

    def select_address(self, reference):
        self.selected.append(reference)
        return {"state": "SELECTED", "purchaseAuthorized": False}


class AddressTests(Fixture):
    def setUp(self):
        super().setUp()
        self.client = AddressClient(lambda: self.now)
        self.adapter = Conversations(self.box, self.client)
        self.worker = ConversationWorker(
            self.box, self.client, self.telegram, OWNER, clock=lambda: self.now
        )

    def review(self):
        self.adapter.receive(update(1, "/enderecos"), "/enderecos")
        self.tick(3)
        message = self.telegram.send.call_args
        return {
            "id": "synthetic-address-callback",
            "from": {"id": OWNER, "is_bot": False},
            "data": "ifa:1" + "1" * 31,
            "message": {
                "message_id": 1001,
                "from": {"id": BOT, "is_bot": True},
                "chat": {"id": OWNER, "type": "private"},
            },
        }, message

    def test_oauth_automatically_offers_addresses_without_model_or_event(self):
        status = LinkStatus("CONNECTED", True, ("ADDRESSES_READ",), None, None, LINK)
        self.worker.link_status = lambda: status
        self.adapter.restore_after_login(status, "oauth-address-test")
        self.tick(8)
        all_text = "\n".join(c.args[1] for c in self.telegram.send.call_args_list)
        self.assertIn("Qual endereço", all_text)
        self.assertEqual(self.client.sent, [])

    def test_multiple_addresses_click_is_bound_and_replayed_once_outside_model(self):
        callback, message = self.review()
        self.assertIn("Casa", message.args[1])
        self.assertEqual(len(message.args[2]["inline_keyboard"]), 2)
        self.assertEqual(self.client.selected, [])
        process_batch(
            self.telegram,
            self.state,
            [{"update_id": 2, "callback_query": callback}],
            OWNER,
            "bot",
            conversations=self.adapter,
        )
        self.tick(4)
        process_batch(
            self.telegram,
            self.state,
            [{"update_id": 2, "callback_query": callback}],
            OWNER,
            "bot",
            conversations=self.adapter,
        )
        self.tick(3)
        self.assertEqual(self.client.selected, ["1" * 32])
        self.assertEqual(self.client.sent, [])
        dump = "\n".join(self.box.db.iterdump())
        self.assertNotIn("Casa", dump)
        self.assertNotIn("Bairro sintético", dump)

    def test_wrong_person_bot_message_forward_and_expiration_cannot_select(self):
        callback, _ = self.review()
        for key in ("person", "bot", "message", "forward"):
            item = copy.deepcopy(callback)
            if key == "person":
                item["from"]["id"] += 1
            if key == "bot":
                item["message"]["from"]["id"] += 1
            if key == "message":
                item["message"]["message_id"] += 1
            if key == "forward":
                item["message"]["forward_origin"] = {"type": "hidden_user"}
            self.assertFalse(self.adapter.address_click(item, 2))
        self.now += 301
        self.assertFalse(self.adapter.address_click(callback, 2))
        self.assertEqual(self.client.selected, [])

    def test_zero_and_one_have_distinct_messages_and_one_still_needs_click(self):
        self.client.options = []
        self.adapter.receive(update(1, "/enderecos"), "/enderecos")
        self.tick(3)
        self.assertIn("Cadastre um endereço no aplicativo", self.telegram.send.call_args.args[1])
        self.client.options = ["Casa · Centro"]
        self.adapter.receive(update(2, "/enderecos"), "/enderecos")
        self.tick(3)
        self.assertIn("Confirma usar", self.telegram.send.call_args.args[1])
        self.assertEqual(self.client.selected, [])

    def test_mcp_error_never_claims_zero_addresses_and_retries_are_bounded(self):
        from telegram_bot.conversation import ConversationError

        self.client.address_failure = ConversationError("UNAVAILABLE")
        self.adapter.receive(update(1, "/enderecos"), "/enderecos")
        for _ in range(6):
            self.tick()
            self.now += 40
        text = "\n".join(c.args[1] for c in self.telegram.send.call_args_list)
        self.assertNotIn("não retornou endereços", text)
        self.assertIsNone(self.box.next())
        self.assertEqual(self.client.sent, [])
