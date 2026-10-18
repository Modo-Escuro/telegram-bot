"""Navegação contextual: identidade real de callback, versão e entrega durável."""

import copy
from datetime import UTC, datetime
from unittest.mock import Mock

from test_conversation_worker import BOT, OWNER, Fixture, snapshot, update

from telegram_bot import conversation_buttons as buttons
from telegram_bot.conversation_contract import Snapshot, encode
from telegram_bot.conversation_runner import Conversations
from telegram_bot.runner import process_batch


class ButtonTests(Fixture):
    def test_no_restrictions_is_inline_and_keeps_version_and_callback_source(self):
        action = {**self.action, "kind": "EDIT_CONTEXT", "actionRef": "none_" + "b" * 32}
        current = self.client.current.to_dict()
        current["allowedActions"] = [action]
        view = Mock()
        view.to_dict.return_value = current
        options = buttons.offered(view)
        self.assertEqual(options[0][0], "Não tenho restrições")
        self.assertIn("inline_keyboard", buttons.markup(options))
        buttons.bind(self.box, 42, BOT, options)
        self.adapter.flow_click({**self.callback, "data": "cv:" + action["actionRef"]}, 1)
        self.tick(2)
        self.assertIn(b'"action":"EDIT_CONTEXT"', self.client.sent[0])
        self.assertIn(b'"kind":"CALLBACK"', self.client.sent[0])
        self.assertIn(b'"expectedVersion":1', self.client.sent[0])

    def setUp(self):
        super().setUp()
        self.client.bot_id = BOT
        self.client.prepare_action = self.client.real.prepare_action
        self.action = {
            "kind": "SELECT_PROPOSAL",
            "actionRef": "choose1_" + "a" * 32,
            "expectedVersion": 1,
            "expiresAt": datetime.fromtimestamp(self.now + 300, UTC).isoformat(),
        }
        self.options = [("Escolher opção 1", self.action)]
        self.callback = {
            "id": "callback-synthetic-1",
            "from": {"id": OWNER, "is_bot": False},
            "data": "cv:" + self.action["actionRef"],
            "message": {
                "message_id": 42,
                "from": {"id": BOT, "is_bot": True},
                "chat": {"id": OWNER, "type": "private"},
            },
        }
        buttons.bind(self.box, 42, BOT, self.options)
        self.client.current = snapshot(1)

    def test_restart_duplicate_callback_and_original_source(self):
        adapter = Conversations(self.restart_box(), self.client)
        adapter.flow_click(self.callback, 1)
        adapter.flow_click(self.callback, 1)
        self.assertEqual(
            self.box.db.execute("SELECT count(*) FROM conversation_outbox").fetchone()[0], 1
        )
        self.tick(2)
        command = self.client.sent[0]
        self.assertIn(b'"kind":"CALLBACK"', command)
        self.assertIn(b'"messageId":"42"', command)
        self.assertIn(b'"callbackQueryId":"callback-synthetic-1"', command)
        self.assertIn(b'"expectedVersion":1', command)
        self.assertNotIn(b'"kind":"TEXT"', command)
        self.assertIn(b"-callback-", command)

    def test_stale_click_is_not_rebased_or_sent(self):
        self.adapter.flow_click(self.callback, 1)
        self.client.current = snapshot(2)
        self.tick()
        self.assertEqual(self.box.active()["notice"], "STALE_VERSION")
        self.assertEqual(self.client.sent, [])

    def test_wrong_message_bot_forward_expiry_and_malformed_source(self):
        for change in (
            {"message_id": 99},
            {"from": {"id": BOT + 1, "is_bot": True}},
            {"from": None},
            {"from": []},
            {"forward_origin": {"type": "user"}},
        ):
            with self.subTest(change=change):
                callback = copy.deepcopy(self.callback)
                callback["message"].update(change)
                self.assertIsNone(buttons.resolve(self.box, callback, BOT))
        self.now += 301
        self.assertIsNone(buttons.resolve(self.box, self.callback, BOT))
        self.box.expire()
        self.assertEqual(
            self.box.db.execute("SELECT count(*) FROM conversation_buttons").fetchone()[0], 0
        )

    def test_other_sender_and_chat_cannot_queue(self):
        for part in ("sender", "chat"):
            callback = copy.deepcopy(self.callback)
            if part == "sender":
                callback["from"]["id"] += 1
            else:
                callback["message"]["chat"]["id"] += 1
            process_batch(
                self.telegram,
                self.state,
                [{"update_id": 1, "callback_query": callback}],
                OWNER,
                "bot",
                conversations=self.adapter,
            )
            self.assertIsNone(self.box.active())
            self.assertIn("validar", self.adapter.flow_click(callback, 2))
            self.assertIsNone(self.box.active())

    def test_review_is_separate_and_never_prepares_remote_cart(self):
        review = {**self.action, "kind": "REQUEST_REVIEW", "actionRef": "review_" + "b" * 32}
        buttons.bind(self.box, 42, BOT, [("Revisar carrinho", review)])
        callback = {**self.callback, "data": "cv:" + review["actionRef"]}
        carts = Mock()
        self.adapter.flow_click(callback, 1, carts)
        carts.receive.assert_called_once_with("/revisarcarrinho", expected_version=1)
        carts.invalidate.assert_not_called()
        self.assertIsNone(self.box.active())
        self.adapter.flow_click(self.callback, 2, carts)
        carts.invalidate.assert_called_once()

    def test_only_last_message_has_buttons_and_persistence_has_no_catalog(self):
        self.adapter.receive(update())
        row = self.box.active()
        parts = ["Descrição privada sintética", "Escolha uma opção"]
        on_delivery = Mock(side_effect=lambda mid: buttons.bind(self.box, mid, BOT, self.options))
        for _ in range(3):
            self.worker._deliver(
                self.box.get(row["seq"]),
                parts,
                markup=buttons.markup(self.options),
                on_delivery=on_delivery,
            )
        calls = self.telegram.send.call_args_list
        self.assertEqual(calls[0].args[2], {"inline_keyboard": []})
        self.assertEqual(calls[1].args[2], buttons.markup(self.options))
        on_delivery.assert_called_once_with(1002)
        values = self.box.db.execute("SELECT * FROM conversation_buttons").fetchall()
        self.assertNotIn(self.action["actionRef"], str([tuple(r) for r in values]))
        self.assertNotIn("privada", str([tuple(r) for r in values]))

    def test_review_button_requires_cart_flag_and_resume_offers_no_actions(self):
        from telegram_bot.conversation_view import render

        raw = snapshot(1).to_dict()
        raw["allowedActions"] = [
            self.action,
            {**self.action, "kind": "REQUEST_REVIEW", "actionRef": "review_" + "b" * 32},
        ]
        current = Snapshot(encode(raw), 1, "COLLECTING")
        self.assertEqual(len(buttons.offered(current)), 1)
        self.assertEqual(len(buttons.offered(current, cart=True)), 2)
        self.assertNotIn("Qual opção", render(current, collection_only=True))
