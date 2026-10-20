"""Entrada natural sem formulário; botões individual/grupo antigos continuam verificáveis."""

import json

from test_conversation_worker import BOT, OWNER, Fixture, update

from telegram_bot.conversation_runner import MODE_QUESTION, MODE_TEXTS
from telegram_bot.runner import process_batch


def start(update_id=1):
    return {
        "update_id": update_id,
        "message": {
            "message_id": 10 + update_id,
            "date": 1,
            "from": {"id": OWNER, "is_bot": False},
            "chat": {"id": OWNER, "type": "private"},
            "text": "/start",
        },
    }


def click(update_id, data, message_id, sender=OWNER):
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"cb-{update_id}",
            "from": {"id": sender, "is_bot": False},
            "data": data,
            "message": {
                "message_id": message_id,
                "from": {"id": BOT, "is_bot": True},
                "chat": {"id": OWNER, "type": "private"},
            },
        },
    }


class ModeTests(Fixture):
    def run_batch(self, *updates):
        process_batch(
            self.telegram, self.state, list(updates), OWNER, "bot", conversations=self.adapter
        )

    def prompt_id(self):
        # Teclado emitido por uma versão anterior do bot, ainda registrado no SQLite.
        message_id = 42
        self.state.mode_prompt(message_id)
        context, _ = self.adapter.profile_context()
        self.state.bind_prompt(message_id, context)
        return message_id

    def sent_texts(self):
        self.tick(4)
        return [json.loads(raw)["input"]["text"] for raw in self.client.sent if b'"input"' in raw]

    def test_start_invites_natural_request_without_individual_group_form(self):
        self.run_batch(start())
        texts = [c.args[1] for c in self.telegram.send.call_args_list]
        self.assertTrue(any("bolo" in text for text in texts))
        self.assertNotIn(MODE_QUESTION, texts)
        self.assertEqual(self.client.sent, [])
        self.assertIsNone(self.box.active())

    def test_each_button_sends_exact_text_once_even_with_double_click(self):
        for choice in ("individual", "group"):
            with self.subTest(choice=choice):
                self.setUp()
                self.run_batch(start())
                prompt = self.prompt_id()
                self.run_batch(click(2, "mode:" + choice, prompt))
                self.run_batch(click(3, "mode:" + choice, prompt))  # clique duplo
                self.assertEqual(self.sent_texts(), [MODE_TEXTS[choice]])
                replies = [c.args[1] for c in self.telegram.send.call_args_list]
                self.assertFalse(any("automaticamente" in r for r in replies))
                self.assertTrue(any("já foi usada" in r for r in replies))

    def test_old_unknown_or_foreign_click_sends_nothing(self):
        self.run_batch(start(1))
        old = self.prompt_id()
        self.state.mode_prompt(old + 2)  # outro teclado legado invalida o anterior
        self.run_batch(click(3, "mode:group", old))
        self.run_batch(click(4, "mode:qualquer", old + 2))
        self.run_batch(click(5, "mode:group", old + 2, sender=OWNER + 1))
        self.assertEqual(self.sent_texts(), [])

    def test_typing_directly_still_works_without_answering_buttons(self):
        self.run_batch(start())
        self.adapter.receive(update(7, "Somos Ana e Bia."))
        self.assertEqual(self.sent_texts(), ["Somos Ana e Bia."])
