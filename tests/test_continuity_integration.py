"""HTTP real contra API fixada: sessão/MCP/Gemini falsos, fora de produção."""

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
from urllib.request import Request, urlopen

from test_continuity_addresses import TelegramWire
from test_conversation_worker import BOT, OWNER, update

from telegram_bot.backend import Backend, BackendConfig
from telegram_bot.connections import Connections
from telegram_bot.conversation import ConversationClient, ConversationError
from telegram_bot.conversation_runner import Conversations, ConversationWorker
from telegram_bot.outbox import Outbox
from telegram_bot.state import State
from telegram_bot.telegram import Telegram

ROOT = os.environ.get("CONTINUITY_API_ROOT")
API_COMMIT = "a72f7958bafda3036a5c6f77045d13925b25233b"
TOKEN = "test-bot-token-0123456789abcdefghijklmnop"


@unittest.skipUnless(ROOT, "Definir CONTINUITY_API_ROOT para integração de continuidade/endereços")
class ContinuityIntegration(unittest.TestCase):
    def setUp(self):
        self.root = Path(ROOT).resolve()
        self.assertEqual(
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip(),
            API_COMMIT,
        )
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        target = self.root / ".continuity-synthetic-test.ts"
        self.assertFalse(target.exists())
        shutil.copyfile(Path(__file__).parent / "fixtures/continuity-api.ts", target)
        self.addCleanup(target.unlink)
        self.errors = (self.path / "node-errors.log").open("w+", encoding="utf-8")
        self.addCleanup(self.errors.close)
        env = {
            k: v
            for k, v in os.environ.items()
            if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT"}
        }
        env.update(CONTINUITY_TEST_ONLY="1", CONTINUITY_TEST_DB=str(self.path / "api.sqlite3"))
        self.process = subprocess.Popen(
            ["node", "--import", "tsx", str(target)],
            cwd=self.root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=self.errors,
            text=True,
            encoding="utf-8",
        )
        self.addCleanup(self.stop)
        ready = queue.Queue()
        threading.Thread(
            target=lambda: ready.put(self.process.stdout.readline()), daemon=True
        ).start()
        try:
            self.base = "http://127.0.0.1:" + str(json.loads(ready.get(timeout=20))["port"])
        except (queue.Empty, ValueError, KeyError):
            self.fail("Fixture sintética não iniciou; verificar dependências/API fixada")
        config = BackendConfig(self.base, TOKEN, OWNER)
        self.client = ConversationClient(config, BOT, timeout=5)
        self.backend = Backend(config)
        self.state = State(self.path / "bot.sqlite3")
        self.addCleanup(self.state.close)
        self.box = Outbox(self.path / "bot.sqlite3", "synthetic-integration")
        self.addCleanup(self.box.close)
        self.adapter = Conversations(self.box, self.client)
        self.wire = TelegramWire()
        self.telegram = Telegram("synthetic-token", self.wire)
        self.worker = ConversationWorker(
            self.box,
            self.client,
            self.telegram,
            OWNER,
            link_status=lambda: self.backend.status(timeout=5),
        )

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process.stdout.close()

    def request(self, path, *, post=False):
        with urlopen(
            Request(self.base + path, method="POST" if post else "GET"), timeout=5
        ) as response:
            return json.load(response)

    def drive(self):
        deadline = time.monotonic() + 12

        def pending():
            return self.box.db.execute(
                "SELECT 1 FROM conversation_outbox WHERE state NOT IN ('DONE','CANCELLED','EXPIRED')"
            ).fetchone()

        while pending() and time.monotonic() < deadline:
            self.worker.tick()
            time.sleep(0.05)
        self.assertFalse(pending())

    def test_message_completes_automatically_and_replay_does_not_call_model_again(self):
        self.adapter.receive(update())
        self.drive()
        self.adapter.receive(update())
        self.drive()
        self.assertEqual(len(self.wire.messages), 1)
        self.assertIn("Pessoa sintética", self.wire.messages[1]["text"])
        stats = self.request("/synthetic/stats")
        self.assertEqual(stats["calls"], 1)
        self.assertTrue(all(x in {"listAddresses", "getUser"} for x in stats["operations"]))

    def test_connected_restores_context_and_offers_address_without_new_turn(self):
        self.adapter.receive(update())
        self.drive()
        # O mesmo watcher usado pelo polling detecta CONNECTED após retorno do navegador.
        self.state.watch_login(OWNER, "synthetic-oauth-attempt", time.time() + 300)
        message = self.telegram.send(
            OWNER, "Login sintético em acompanhamento", {"inline_keyboard": []}
        )
        self.state.login_message(
            "synthetic-oauth-attempt", message["message_id"], "AWAITING_AUTHORIZATION"
        )
        handler = Connections(self.backend, self.state, OWNER, conversations=self.adapter)
        handler.tick(self.telegram, OWNER)
        self.assertFalse(handler.watching)
        self.drive()
        texts = "\n".join(x["text"] for x in self.wire.messages.values())
        self.assertIn("Pessoa sintética", texts)
        self.assertIn("Confirma usar", texts)
        self.assertEqual(self.request("/synthetic/stats")["calls"], 1)

    def test_zero_one_multiple_explicit_selection_and_organizer_isolation(self):
        for n in (0, 1, 2):
            self.request("/synthetic/addresses/" + str(n), post=True)
            review = self.client.get_addresses()
            self.assertEqual(len(review["options"]), n)
        reference = review["options"][1]["choiceRef"]
        other = ConversationClient(BackendConfig(self.base, TOKEN, 222222222), BOT)
        with self.assertRaises(ConversationError):
            other.select_address(reference)
        self.assertEqual(self.client.select_address(reference)["state"], "SELECTED")
        self.assertEqual(self.client.select_address(reference)["state"], "SELECTED")
        self.assertEqual(self.request("/synthetic/stats")["calls"], 0)
        self.request("/synthetic/addresses/0", post=True)
        with self.assertRaises(ConversationError):
            self.client.select_address(reference)
