"""Pergunta individual/grupo no início: botões fora do modelo, texto fixo, envio único."""

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
        calls = [c for c in self.telegram.send.call_args_list if c.args[1] == MODE_QUESTION]
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            [b["callback_data"] for b in calls[0].args[2]["inline_keyboard"][0]],
            ["mode:individual", "mode:group"],
        )
        index = self.telegram.send.call_args_list.index(calls[0])
        return 1001 + index  # Fixture devolve message_id = 1000 + chamada

    def sent_texts(self):
        self.tick(4)
        return [json.loads(raw)["input"]["text"] for raw in self.client.sent if b'"input"' in raw]

    def test_start_asks_individual_or_group_once(self):
        self.run_batch(start())
        self.prompt_id()
        self.assertEqual(self.client.sent, [])  # perguntar não envia nada ao backend

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
                self.assertTrue(any("já foi usada" in r for r in replies))

    def test_old_unknown_or_foreign_click_sends_nothing(self):
        self.run_batch(start(1))
        old = self.prompt_id()
        self.run_batch(start(2))  # novo teclado invalida o anterior
        self.run_batch(click(3, "mode:group", old))
        self.run_batch(click(4, "mode:qualquer", old + 2))
        self.run_batch(click(5, "mode:group", old + 2, sender=OWNER + 1))
        self.assertEqual(self.sent_texts(), [])

    def test_typing_directly_still_works_without_answering_buttons(self):
        self.run_batch(start())
        self.adapter.receive(update(7, "Somos Ana e Bia."))
        self.assertEqual(self.sent_texts(), ["Somos Ana e Bia."])
