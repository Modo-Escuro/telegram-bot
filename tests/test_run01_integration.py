"""Integração HTTP real bot→RUN-01/DATA-01, processador sintético e rede só loopback.

BOT01_API_ROOT aponta ao checkout fixado em API_COMMIT; a CI possui job obrigatório próprio.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock
from urllib.request import Request, urlopen

from telegram_bot.backend import BackendConfig
from telegram_bot.conversation import ConversationClient, ConversationError
from telegram_bot.conversation_runner import Conversations, ConversationWorker
from telegram_bot.outbox import Outbox
from telegram_bot.state import State

API_COMMIT = "d2883f120419385c5ec902740330c3743f130b44"
API_ROOT = os.environ.get("BOT01_API_ROOT")
OWNER, BOT = 111111111, 900001


def update(number, text="adicionar pessoa"):
    return {
        "update_id": number,
        "message": {
            "message_id": number + 100,
            "from": {"id": OWNER, "is_bot": False},
            "chat": {"id": OWNER, "type": "private"},
            "text": text,
        },
    }


@unittest.skipUnless(API_ROOT, "Definir BOT01_API_ROOT para o job de integração RUN-01 fixada")
class Run01Integration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(API_ROOT).resolve()
        self.assertEqual(
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            API_COMMIT,
        )
        self.assertTrue(
            (root / "node_modules").is_dir(), "Instalar o lockfile da API antes do ensaio"
        )
        fixture = Path(__file__).parent / "fixtures/run01-api.ts"
        # Resolução de módulos Node ocorre na raiz da API, sem copiar dependências para o bot.
        target = root / ".bot01-synthetic-test.ts"
        self.assertFalse(target.exists(), "Outro ensaio usa este checkout da API")
        shutil.copyfile(fixture, target)
        self.addCleanup(target.unlink)
        env = {
            k: v
            for k, v in os.environ.items()
            if k.upper()
            in {
                "PATH",
                "SYSTEMROOT",
                "WINDIR",
                "TEMP",
                "TMP",
                "COMSPEC",
                "PATHEXT",
            }
        }
        env.update(BOT01_TEST_ONLY="1", BOT01_TEST_DB=str(Path(self.temp.name) / "api.sqlite"))
        self.errors = (Path(self.temp.name) / "node-errors.log").open("w+", encoding="utf-8")
        self.addCleanup(self.errors.close)
        self.process = subprocess.Popen(
            ["node", "--import", "tsx", str(target)],
            cwd=root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=self.errors,
            text=True,
            encoding="utf-8",
        )
        self.addCleanup(self.stop_api)
        # O leitor fica numa thread limitada; evita travar a suíte se Node falhar antes de anunciar a porta.
        import queue
        import threading

        result = queue.Queue()
        threading.Thread(
            target=lambda: result.put(self.process.stdout.readline()), daemon=True
        ).start()
        try:
            ready = json.loads(result.get(timeout=20))
        except (queue.Empty, ValueError):
            self.fail("Fixture RUN-01 não iniciou; conferir Node/dependências no checkout de teste")
        self.base = f"http://127.0.0.1:{ready['port']}"
        config = BackendConfig(self.base, "synthetic-token-xxxxxxxxxxxxxxxxxxxxxxxxx", OWNER)
        self.client = ConversationClient(config, BOT, timeout=2)
        self.path = Path(self.temp.name) / "bot.sqlite3"
        self.state = State(self.path)
        self.addCleanup(self.state.close)
        self.box = Outbox(self.path, "run01-integration")
        self.addCleanup(self.box.close)
        self.adapter = Conversations(self.box, self.client)
        self.telegram = Mock()
        self.telegram.send.side_effect = lambda *args: {
            "message_id": 500 + self.telegram.send.call_count
        }
        self.worker = ConversationWorker(self.box, self.client, self.telegram, OWNER)

    def stop_api(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process.stdout.close()

    def request(self, path, method="GET"):
        with urlopen(Request(self.base + path, method=method), timeout=2) as response:
            return json.load(response)

    def drive(self, timeout=8):
        deadline = time.monotonic() + timeout
        while self.box.active() and time.monotonic() < deadline:
            self.worker.tick()
            time.sleep(0.03)
        self.assertIsNone(self.box.active(), "Fila não concluiu no prazo do ensaio sintético")

    def test_http_accept_recovery_and_durable_domain_snapshot(self):
        self.adapter.receive(update(1))
        self.adapter.receive(update(1))
        self.drive()
        self.assertEqual(self.request("/synthetic/stats")["executions"], 1)
        current = self.client.get_snapshot().to_dict()
        self.assertEqual(current["version"], 1)
        self.assertEqual(current["blocks"][0]["participants"][0]["displayName"], "Pessoa sintética")
        self.assertIn("Pessoa sintética", self.telegram.send.call_args.args[1])

    def test_lost_post_response_replays_exact_event_without_new_domain_change(self):
        self.adapter.receive(update(1))
        self.worker.tick()  # prepara versão 0
        original = self.client.send

        def lose(command):
            original(command)
            raise ConversationError("UNAVAILABLE", uncertain=True)

        self.client.send = lose
        self.worker.tick()
        command = bytes(self.box.active()["command"])
        self.client.send = original
        self.box.save(self.box.active()["seq"], due=time.time())
        recovered = Outbox(self.path, "run01-integration")
        self.addCleanup(recovered.close)
        self.worker = ConversationWorker(recovered, self.client, self.telegram, OWNER)
        self.drive()
        self.assertEqual(self.request("/synthetic/stats")["executions"], 1)
        self.assertEqual(self.client.get_snapshot().version, 1)
        self.assertEqual(json.loads(command)["expectedVersion"], 0)

    def test_expunged_history_is_not_reintroduced_after_bot_restart(self):
        self.adapter.receive(update(1))
        self.worker.tick()
        self.worker.tick()
        operation_id, event_id = self.box.active()["operation_id"], self.box.active()["event_id"]
        deadline = time.monotonic() + 5
        while not self.client.get_operation(operation_id, event_id=event_id).terminal:
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.03)
        self.assertEqual(self.request("/synthetic/expire", "POST")["purged"], 1)
        self.drive()
        sent = " ".join(call.args[1] for call in self.telegram.send.call_args_list)
        self.assertNotIn("Pessoa sintética", sent)
        self.assertEqual(self.client.get_snapshot().to_dict()["blocks"], [])
        old = self.client.get_operation(operation_id, event_id=event_id).to_dict()
        self.assertEqual(old["changes"], [])

    def test_close_removes_domain_and_cannot_restore_old_reply(self):
        self.adapter.receive(update(1))
        self.drive()
        self.telegram.reset_mock()
        self.adapter.receive(update(2, "encerrar"))
        self.drive()
        text = " ".join(c.args[1] for c in self.telegram.send.call_args_list)
        self.assertIn("excluídos", text)
        self.assertNotIn("Pessoa sintética", text)
