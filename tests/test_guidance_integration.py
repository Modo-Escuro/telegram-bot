"""Bot e API desta alteração via HTTP real; serviços externos sintéticos."""

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

from test_conversation_worker import BOT, OWNER, update

from telegram_bot.backend import BackendConfig
from telegram_bot.conversation import ConversationClient
from telegram_bot.conversation_runner import Conversations, ConversationWorker
from telegram_bot.outbox import Outbox
from telegram_bot.state import State

ROOT = os.environ.get("GUIDANCE_API_ROOT")


@unittest.skipUnless(ROOT, "Definir GUIDANCE_API_ROOT para ensaio da navegação contextual")
class GuidanceIntegration(unittest.TestCase):
    def test_text_to_offer_to_button_to_bag_and_clear_preserves_group(self):
        root = Path(ROOT).resolve()
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name)
        target = root / ".guidance-synthetic-test.ts"
        self.assertFalse(target.exists())
        shutil.copyfile(Path(__file__).parent / "fixtures/guidance-api.ts", target)
        self.addCleanup(target.unlink)
        errors = (path / "node-errors.log").open("w+", encoding="utf-8")
        self.addCleanup(errors.close)
        env = {
            k: v
            for k, v in os.environ.items()
            if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT"}
        }
        env.update(GUIDANCE_TEST_ONLY="1", GUIDANCE_TEST_DB=str(path / "api.sqlite3"))
        process = subprocess.Popen(
            ["node", "--import", "tsx", str(target)],
            cwd=root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=errors,
            text=True,
            encoding="utf-8",
        )

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
        # Drenar logs sintéticos para não bloquear o servidor quando o pipe encher.
        threading.Thread(target=lambda: list(process.stdout), daemon=True).start()
        client = ConversationClient(
            BackendConfig(base, "test-bot-token-0123456789abcdefghijklmnop", OWNER), BOT
        )
        state = State(path / "bot.sqlite3")
        self.addCleanup(state.close)
        box = Outbox(path / "bot.sqlite3", "guidance-http")
        self.addCleanup(box.close)
        adapter = Conversations(box, client)
        telegram = Mock()
        telegram.send.side_effect = lambda *args: {"message_id": 100 + telegram.send.call_count}
        worker = ConversationWorker(box, client, telegram, OWNER)

        def drive():
            deadline = time.monotonic() + 12
            while box.active() and time.monotonic() < deadline:
                worker.tick()
                time.sleep(0.02)
            active = box.active()
            self.assertIsNone(
                active, {k: active[k] for k in ("state", "notice", "attempts")} if active else None
            )

        adapter.receive(
            update(
                1,
                "Somos Ana. Ana não tem restrição. Teto de R$ 100. Prefiro economia. Sugere pizza",
            )
        )
        drive()
        before = client.get_snapshot().to_dict()
        self.assertEqual(before["phase"], "PROPOSALS_READY")
        group = next(b for b in before["blocks"] if b["kind"] == "GROUP")
        shown = telegram.send.call_args.args
        choice = shown[2]["inline_keyboard"][0][0]
        self.assertEqual(choice["text"], "Escolher opção 1")
        callback = {
            "id": "guidance-human-click",
            "from": {"id": OWNER, "is_bot": False},
            "data": choice["callback_data"],
            "message": {
                "message_id": 100 + telegram.send.call_count,
                "from": {"id": BOT, "is_bot": True},
                "chat": {"id": OWNER, "type": "private"},
            },
        }
        adapter.flow_click(callback, 2)
        adapter.flow_click(callback, 2)
        drive()
        selected = client.get_snapshot().to_dict()
        self.assertEqual(selected["version"], before["version"] + 1)
        self.assertEqual(selected["phase"], "EDITING_CART")
        self.assertIsNone(selected["humanApproval"])
        self.assertIn("Carrinho simulado", telegram.send.call_args.args[1])
        adapter.receive(update(3, "Esvaziar sacola"))
        drive()
        cleared = client.get_snapshot().to_dict()
        self.assertEqual(next(b for b in cleared["blocks"] if b["kind"] == "GROUP"), group)
        self.assertFalse(any(b["kind"] == "REVIEW" for b in cleared["blocks"]))
