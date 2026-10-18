"""Limpar perfil e remover pessoa: confirmação por botão, texto fixo do contrato, envio único."""

import json

from test_conversation_worker import OWNER, Fixture
from test_individual_mode import click

from telegram_bot.conversation_contract import Snapshot, encode
from telegram_bot.conversation_runner import CLEAR_QUESTION, CLEAR_TEXT, remove_text
from telegram_bot.menu import BUTTONS, keyboard
from telegram_bot.runner import NO_PEOPLE, process_batch


def command(update_id, text):
    return {
        "update_id": update_id,
        "message": {
            "message_id": 10 + update_id,
            "date": 1,
            "from": {"id": OWNER, "is_bot": False},
            "chat": {"id": OWNER, "type": "private"},
            "text": text,
        },
    }


def group_snapshot(*names):
    body = {
        "contractVersion": "1.0",
        "conversationId": str(OWNER),
        "version": 3,
        "phase": "COLLECTING",
        "blocks": [
            {
                "kind": "GROUP",
                "participants": [
                    {"participantRef": f"p{i}", "displayName": n, "conditions": []}
                    for i, n in enumerate(names)
                ],
                "budgetCents": None,
            }
        ],
        "pending": [],
        "allowedActions": [],
        "humanApproval": None,
    }
    return Snapshot(encode(body), 3, "COLLECTING")


class ProfileTests(Fixture):
    def run_batch(self, *updates):
        process_batch(
            self.telegram, self.state, list(updates), OWNER, "bot", conversations=self.adapter
        )

    def prompt(self, text):
        calls = [c for c in self.telegram.send.call_args_list if c.args[1] == text]
        self.assertEqual(len(calls), 1)
        return calls[0], 1001 + self.telegram.send.call_args_list.index(calls[0])

    def sent_texts(self):
        self.tick(4)
        return [json.loads(raw)["input"]["text"] for raw in self.client.sent if b'"input"' in raw]

    def test_menu_has_buttons(self):
        self.assertEqual(BUTTONS["Limpar perfil"], "/limpar")
        self.assertEqual(BUTTONS["Remover pessoa"], "/remover")
        labels = [b["text"] for row in keyboard()["keyboard"] for b in row]
        self.assertIn("Limpar perfil", labels)
        self.assertIn("Remover pessoa", labels)

    def test_clear_asks_first_and_sends_exact_text_once(self):
        self.run_batch(command(1, "/limpar"))
        call, prompt = self.prompt(CLEAR_QUESTION)
        self.assertEqual(
            [b["callback_data"] for b in call.args[2]["inline_keyboard"][0]], ["clr:yes", "clr:no"]
        )
        self.assertEqual(self.client.sent, [])  # perguntar não apaga nada
        self.run_batch(click(2, "clr:yes", prompt))
        self.run_batch(click(3, "clr:yes", prompt))  # clique duplo
        self.assertEqual(self.sent_texts(), [CLEAR_TEXT])
        replies = [c.args[1] for c in self.telegram.send.call_args_list]
        self.assertTrue(any("já foi usada" in r for r in replies))

    def test_cancel_old_and_foreign_clicks_send_nothing(self):
        self.run_batch(command(1, "/limpar"))
        _, old = self.prompt(CLEAR_QUESTION)
        self.run_batch(click(2, "clr:no", old))
        self.run_batch(click(3, "clr:yes", old))  # já consumido pelo cancelar
        self.run_batch(command(4, "/limpar"))
        current = 1001 + len(self.telegram.send.call_args_list) - 1
        self.run_batch(click(5, "clr:yes", current, sender=OWNER + 1))  # outra pessoa
        self.run_batch(click(6, "rm:0", current))  # tipo errado para o teclado
        self.assertEqual(self.sent_texts(), [])

    def test_remove_lists_people_and_sends_exact_name_once(self):
        self.client.current = group_snapshot("Ana", "Bia")
        self.run_batch(command(1, "/remover"))
        call, prompt = self.prompt("Quem você quer remover do pedido?")
        rows = call.args[2]["inline_keyboard"]
        self.assertEqual([r[0]["text"] for r in rows], ["Remover Ana", "Remover Bia", "Cancelar"])
        self.assertEqual([r[0]["callback_data"] for r in rows], ["rm:0", "rm:1", "rm:no"])
        self.run_batch(click(2, "rm:1", prompt))
        self.run_batch(click(3, "rm:0", prompt))  # teclado já usado
        self.assertEqual(self.sent_texts(), [remove_text("Bia")])
        self.assertEqual(remove_text("Bia"), "Confirmo: remover Bia do pedido.")

    def test_remove_invalid_index_or_cancel_sends_nothing(self):
        self.client.current = group_snapshot("Ana")
        self.run_batch(command(1, "/remover"))
        _, prompt = self.prompt("Quem você quer remover do pedido?")
        self.run_batch(click(2, "rm:9", prompt))
        self.assertEqual(self.sent_texts(), [])

    def test_remove_without_people(self):
        self.client.current = group_snapshot()
        self.run_batch(command(1, "/remover"))
        self.assertEqual(self.telegram.send.call_args_list[-1].args[1], NO_PEOPLE)
        self.assertEqual(self.client.sent, [])
