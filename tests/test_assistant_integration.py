"""Contrato atual do assistente em HTTP real, separado dos pins históricos; nenhuma rede externa."""

import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock
from urllib.request import urlopen

from test_conversation_worker import BOT, OWNER, update

from telegram_bot.backend import BackendConfig
from telegram_bot.cart_client import CartClient, CartError
from telegram_bot.conversation import ConversationClient
from telegram_bot.conversation_runner import Conversations, ConversationWorker
from telegram_bot.outbox import Outbox
from telegram_bot.state import State

ROOT = os.environ.get("ASSISTANT_API_ROOT")


@unittest.skipUnless(ROOT, "Definir ASSISTANT_API_ROOT para o contrato atual do assistente")
class AssistantIntegration(unittest.TestCase):
    def test_text_memory_choice_review_and_allergy_invalidation(self):
        root = Path(ROOT).resolve()
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name)
        target = root / ".assistant-synthetic-test.ts"
        self.assertFalse(target.exists())
        shutil.copyfile(Path(__file__).parent / "fixtures/assistant-api.ts", target)
        self.addCleanup(target.unlink)
        errors = (path / "node-errors.log").open("w+", encoding="utf-8")
        self.addCleanup(errors.close)
        env = {k: v for k, v in os.environ.items() if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT"}}
        env.update(ASSISTANT_TEST_ONLY="1", ASSISTANT_TEST_DB=str(path / "api.sqlite3"))
        process = subprocess.Popen(["node", "--import", "tsx", str(target)], cwd=root, env=env, stdout=subprocess.PIPE, stderr=errors, text=True, encoding="utf-8")

        def stop():
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            process.stdout.close()

        self.addCleanup(stop)
        ready = queue.Queue()
        threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True).start()
        try:
            base = "http://127.0.0.1:" + str(json.loads(ready.get(timeout=20))["port"])
        except (queue.Empty, ValueError, KeyError):
            errors.flush()
            errors.seek(0)
            self.fail("Fixture sintética falhou: " + errors.read()[-3000:])
        threading.Thread(target=lambda: list(process.stdout), daemon=True).start()
        config = BackendConfig(base, "synthetic-token-xxxxxxxxxxxxxxxxxxxxxxxxx", OWNER)
        client, cart = ConversationClient(config, BOT), CartClient(config)
        state = State(path / "bot.sqlite3")
        self.addCleanup(state.close)
        box = Outbox(path / "bot.sqlite3", "assistant-http")
        self.addCleanup(box.close)
        adapter = Conversations(box, client)
        telegram = Mock()
        telegram.send.side_effect = lambda *args: {"message_id": 100 + telegram.send.call_count}
        worker = ConversationWorker(box, client, telegram, OWNER)

        def drive(number, text):
            adapter.receive(update(number, text))
            deadline = time.monotonic() + 12
            while box.active() and time.monotonic() < deadline:
                worker.tick()
                time.sleep(0.02)
            self.assertIsNone(box.active())
            return client.get_snapshot(session_ref=client.account_context()).to_dict()

        def stats():
            with urlopen(base + "/__synthetic-stats", timeout=5) as response:
                return json.load(response)

        choices = client.get_addresses()
        client.select_address(choices["options"][0]["choiceRef"])
        drive(1, "Não tenho restrições. Orçamento máximo de R$ 100.")
        options = drive(2, "Quero arroz para mim.")
        self.assertTrue(any(b["kind"] == "TEXT" and b["text"].startswith("1.") for b in options["blocks"]))
        before = stats()
        chosen = drive(3, "Confirmo: escolher a opção 1.")
        self.assertIn("Sacola atual", json.dumps(chosen, ensure_ascii=False))
        self.assertEqual(stats(), before)
        self.assertEqual(cart.review()["purpose"], "PREPARE_CART")
        drive(4, "Minha namorada gosta de chocolate.")
        self.assertEqual(adapter.memory_names(), ["namorada"])
        before = stats()
        drive(5, "Confirmo: remover namorada do pedido.")
        self.assertEqual(adapter.memory_names(), [])
        self.assertEqual(stats(), before)
        drive(6, "Eu sou alérgico a amendoim.")
        with self.assertRaises(CartError) as denied:
            cart.review()
        self.assertIn(denied.exception.code, {"CART_BAG_UNVERIFIED", "CART_GROUP_BLOCKED", "CART_ITEM_BLOCKED"})
        self.assertEqual(stats()["writes"], 0)
