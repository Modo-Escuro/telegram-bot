"""Jornada por botões e apresentação com fatos sintéticos, sem rede externa."""

import io
import json
import unittest
from unittest.mock import Mock

import test_conversation_worker as conversation
import test_password_access as access
from test_connections import CONFIRM, pending
from test_login_context import connected

from telegram_bot.connections import Connections
from telegram_bot.conversation_contract import Snapshot, encode
from telegram_bot.conversation_view import render
from telegram_bot.menu import BUTTONS, keyboard
from telegram_bot.runner import process_batch
from telegram_bot.telegram import Telegram, TelegramError


class NavigationTests(conversation.Fixture):
    def test_buttons_use_controls_and_keep_event_identity(self):
        backend = Mock()
        backend.status.return_value = connected()
        connections = Connections(
            backend, self.state, conversation.OWNER, conversations=self.adapter
        )
        for n, label in enumerate(["Minha conexão", "Acompanhar", "Ajuda"], 1):
            process_batch(
                self.telegram,
                self.state,
                [conversation.update(n, label)],
                conversation.OWNER,
                "bot",
                connections,
                self.adapter,
            )
        backend.status.assert_called_once()
        self.assertEqual(self.client.sent, [])
        self.assertIsNone(self.box.active())
        self.assertEqual(self.state.offset(), 4)

    def test_old_confirmation_on_connected_account_only_recovers_context(self):
        backend = Mock()
        backend.status.return_value = connected()
        connections = Connections(
            backend, self.state, conversation.OWNER, conversations=self.adapter
        )
        reply = connections.confirm_click(CONFIRM, 1)
        self.assertIn("conectada", reply.text)
        self.assertNotIn("/confirmar", reply.text)
        backend.confirm.assert_not_called()
        self.assertEqual(
            self.box.db.execute(
                "SELECT count(*) FROM conversation_outbox WHERE kind='CONTEXT'"
            ).fetchone()[0],
            1,
        )
        backend.status.return_value = pending()
        reply = connections.confirm_click("z" * 24, 2)
        self.assertEqual(reply.markup["inline_keyboard"][0][0]["callback_data"], "ifc:" + CONFIRM)
        backend.confirm.assert_not_called()


class EntryTests(unittest.TestCase):
    setUp = access.RouterTests.setUp
    receive = access.RouterTests.receive

    def test_password_replay_after_delivery_failure_cannot_become_chat(self):
        self.receive(access.update(1, text="Entrar na demo"))
        self.api.send.side_effect = TelegramError(500)
        with self.assertRaises(TelegramError):
            self.receive(access.update(2, text=access.PASSWORD))
        self.api.send.side_effect = None
        self.receive(access.update(2, text=access.PASSWORD))
        self.created[access.A].receive.assert_not_called()
        self.assertEqual(self.state.offset(), 3)

    def test_button_and_plain_password_never_reach_model_or_database(self):
        self.receive(access.update(1, text="Entrar na demo"))
        self.assertTrue(self.router.access.awaiting_entry(access.A))
        self.receive(access.update(2, text=access.PASSWORD))
        self.assertTrue(self.router.access.allowed(access.A))
        self.created[access.A].receive.assert_not_called()
        self.assertNotIn(access.PASSWORD, "\n".join(self.router.access.db.iterdump()))
        self.api.call.assert_called_with("deleteMessage", {"chat_id": access.A, "message_id": 102})
        self.receive(access.update(3, text="Sair da demo"))
        self.assertFalse(self.router.access.allowed(access.A))

    def test_entry_cancel_expiry_and_restart(self):
        self.receive(access.update(1, text="Entrar na demo"))
        reopened = access.AccessStore(
            self.path / f"bot-{access.BOT}-access.sqlite3", access.PASSWORD, access.TOKEN
        )
        try:
            self.assertTrue(reopened.awaiting_entry(access.A))
        finally:
            reopened.close()
        now = self.router.access.clock()
        self.router.access.clock = lambda: now + 301
        self.receive(access.update(2, text=access.PASSWORD))
        self.assertEqual(self.created, {})
        self.assertIn("tempo", self.api.send.call_args.args[1])
        self.receive(
            access.update(3, text="Entrar na demo"), access.update(4, text="Cancelar entrada")
        )
        self.assertFalse(self.router.access.awaiting_entry(access.A))


class PresentationTests(unittest.TestCase):
    def document(self):
        d = conversation.snapshot().to_dict()
        d["blocks"] = [
            {
                "kind": "GROUP",
                "participants": [
                    {
                        "participantRef": "person_a",
                        "displayName": "Ana",
                        "conditions": ["Alergia: amendoim (obrigatória)"],
                    },
                    {
                        "participantRef": "person_b",
                        "displayName": "Bia",
                        "conditions": ["Sem restrições alimentares"],
                    },
                ],
                "budgetCents": 15000,
            },
            {
                "kind": "TEXT",
                "source": "SERVER",
                "text": "Ana entrou na compra. Bia entrou na compra. Registrei alergia a amendoim para Ana. Bia não tem restrições. Teto máximo de R$ 150.00 para o grupo.",
            },
            {"kind": "TEXT", "source": "SERVER", "text": "Orçamento do grupo: R$ 150.00 (máximo)."},
        ]
        d["pending"] = ["Vocês preferem economia ou rapidez?"]
        return d

    def test_reported_example_has_one_budget_and_no_duplicate_narration(self):
        d = self.document()
        text = render(Snapshot(encode(d), 0, "COLLECTING"))
        self.assertEqual(text.count("150,00"), 1)
        self.assertIn("(máximo)", text)
        self.assertIn("amendoim (obrigatória)", text)
        self.assertNotIn("entrou na compra", text)
        self.assertNotIn("em preparação", text)
        self.assertIn("Vocês preferem economia ou rapidez?", text)

    def test_unknown_warning_and_model_text_are_not_suppressed(self):
        d = self.document()
        d["blocks"] += [
            {"kind": "TEXT", "source": "SERVER", "text": "Não removi a alergia de Ana."},
            {"kind": "TEXT", "source": "MODEL", "text": "Ana entrou na compra."},
        ]
        d["pending"] = [
            "Qual é o orçamento do grupo?",
            "Vocês preferem economia ou rapidez?",
            "Alergênicos não verificados: item bloqueado para Ana.",
        ]
        text = render(Snapshot(encode(d), 0, "COLLECTING"))
        self.assertIn("Não removi a alergia", text)
        self.assertIn("Assistente: Ana entrou na compra.", text)
        self.assertIn("item bloqueado", text)
        self.assertNotIn("Vocês preferem", text)

    def test_keyboard_labels_all_resolve_and_transport_keeps_inline_buttons(self):
        for row in keyboard()["keyboard"]:
            for button in row:
                self.assertIn(button["text"], BUTTONS)
        opener = Mock()
        opener.open.side_effect = lambda *a, **k: io.BytesIO(b'{"ok":true,"result":{}}')
        api = Telegram("synthetic", opener)
        api.send(1, "Oi")
        self.assertEqual(json.loads(opener.open.call_args.args[0].data)["reply_markup"], keyboard())
        inline = {"inline_keyboard": [[{"text": "Login", "url": "https://example.test"}]]}
        api.send(1, "Conectar", inline)
        self.assertEqual(json.loads(opener.open.call_args.args[0].data)["reply_markup"], inline)
