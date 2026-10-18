"""Bot → HTTP/SQLite reais → MCP sintético; jamais usa credenciais ou polling externo."""

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
from urllib.error import URLError
from urllib.request import Request, build_opener, urlopen

from telegram_bot.backend import Backend, BackendConfig
from telegram_bot.cart import Carts
from telegram_bot.cart_client import CartClient, CartError
from telegram_bot.conversation import ConversationClient
from telegram_bot.runner import process_batch
from telegram_bot.state import State

ROOT = os.environ.get("CART_API_ROOT")
OWNER, BOT = 111111111, 900001
TOKEN = "test-bot-token-0123456789abcdefghijklmnop"


class LoseConfirmReply:
    def __init__(self):
        self.opener = build_opener()
        self.posts = 0

    def open(self, request, timeout):
        response = self.opener.open(request, timeout=timeout)
        if request.method == "POST" and request.full_url.endswith("/confirm"):
            self.posts += 1
            response.read()
            response.close()
            raise URLError("synthetic response loss after effect")
        return response


@unittest.skipUnless(ROOT, "Definir CART_API_ROOT para ensaio HTTP CART-01")
class CartIntegration(unittest.TestCase):
    SHAPE = "synthetic"
    def setUp(self):
        self.root = Path(ROOT).resolve()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.target = self.root / ".cart-synthetic-test.ts"
        self.assertFalse(self.target.exists())
        shutil.copyfile(Path(__file__).parent / "fixtures/cart-api.ts", self.target)
        self.addCleanup(self.target.unlink)
        self.errors = (self.path / "node-errors.log").open("w+", encoding="utf-8")
        self.addCleanup(self.errors.close)
        self.start_api()
        self.addCleanup(self.stop_api)
        self.state = State(self.path / "bot.sqlite3")
        self.addCleanup(self.state.close)
        self.telegram = Mock()
        self.telegram.send.return_value = {"message_id": 55}
        self.carts = self.make_carts()
        self.addCleanup(lambda: self.carts.close())

    def start_api(self):
        env = {
            k: v
            for k, v in os.environ.items()
            if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT"}
        }
        env.update(
            CART_TEST_ONLY="1",
            CART_TEST_DB=str(self.path / "api.sqlite3"),
            CART_TEST_REMOTE=str(self.path / "provider.json"),
            CART_TEST_SHAPE=self.SHAPE,
        )
        self.process = subprocess.Popen(
            ["node", "--import", "tsx", str(self.target)],
            cwd=self.root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=self.errors,
            text=True,
            encoding="utf-8",
        )
        ready = queue.Queue()
        threading.Thread(
            target=lambda: ready.put(self.process.stdout.readline()), daemon=True
        ).start()
        try:
            self.base = "http://127.0.0.1:" + str(json.loads(ready.get(timeout=20))["port"])
        except (queue.Empty, ValueError, KeyError):
            self.fail("Fixture CART-01 não iniciou; conferir API e dependências locais")
        config = BackendConfig(self.base, TOKEN, OWNER)
        self.client, self.conversation, self.backend = (
            CartClient(config),
            ConversationClient(config, BOT),
            Backend(config),
        )

    def stop_api(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process.stdout.close()

    def make_carts(self):
        return Carts(
            self.state,
            self.client,
            self.conversation,
            self.backend,
            BOT,
            OWNER,
            scope="synthetic-cart-http",
        )

    def synthetic(self, path, *, post=False):
        with urlopen(
            Request(self.base + "/synthetic/" + path, method="POST" if post else "GET"), timeout=5
        ) as response:
            return json.load(response)

    def pump(self):
        deadline = time.monotonic() + 8
        while self.carts.future is not None and time.monotonic() < deadline:
            self.carts.tick(self.telegram)
            time.sleep(0.01)
        self.assertIsNone(self.carts.future)

    def choose_and_review(self):
        choices = self.conversation.get_addresses()["options"]
        self.conversation.select_address(choices[0]["choiceRef"])
        self.carts.receive("/revisarcarrinho")
        self.pump()
        self.assertIsNotNone(self.carts.review)
        shown = self.telegram.send.call_args.args[1]
        for fact in (
            "Pessoa S.",
            "Loja sintética",
            "Casa",
            "1 × Arroz",
            "Total completo desconhecido",
        ):
            self.assertIn(fact, shown)
        return {
            "id": "human-callback",
            "from": {"id": OWNER, "is_bot": False},
            "message": {
                "message_id": 55,
                "chat": {"id": OWNER, "type": "private"},
                "from": {"id": BOT, "is_bot": True},
            },
            "data": "cart:" + self.carts.review["button"],
        }

    def test_address_review_human_click_final_costs_replay_and_isolation(self):
        with self.assertRaises(CartError):
            self.client.review()
        callback = self.choose_and_review()
        conversations = Mock()
        event = {"update_id": 50, "callback_query": callback}
        for _ in range(2):
            process_batch(
                self.telegram,
                self.state,
                [event],
                OWNER,
                "bot",
                conversations=conversations,
                carts=self.carts,
            )
            self.pump()
        self.assertEqual(self.synthetic("stats")["writes"], 1)
        self.assertEqual(self.carts._row()[1], "SUCCEEDED")
        self.assertIn("Total observado: R$ 26,00", self.telegram.send.call_args.args[1])
        conversations.receive.assert_not_called()
        other = CartClient(BackendConfig(self.base, TOKEN, 222222222))
        with self.assertRaises(CartError):
            other.request(self.carts._row()[0])
        dump = "\n".join(self.state.db.iterdump())
        for secret in ("Arroz", "Pessoa S.", "Casa", "human-callback"):
            self.assertNotIn(secret, dump)

    def test_lost_reply_recovers_by_get_and_failed_current_read_does_not_rewrite(self):
        callback = self.choose_and_review()
        opener = LoseConfirmReply()
        self.client.opener = opener
        self.carts.click(callback)
        self.pump()
        self.assertEqual(self.carts._row()[1], "SUCCEEDED")
        self.assertEqual(opener.posts, 1)
        self.synthetic("mode/read-failed", post=True)
        self.carts.receive("/conferircarrinho")
        self.pump()
        self.assertEqual(self.carts._row()[1], "SUCCEEDED")
        self.assertIn("Não consegui conferir", self.telegram.send.call_args.args[1])
        self.assertEqual(self.synthetic("stats")["writes"], 1)

    def test_unknown_effect_survives_api_and_bot_restart_without_second_write(self):
        callback = self.choose_and_review()
        self.synthetic("mode/unknown", post=True)
        self.carts.click(callback)
        self.pump()
        self.assertEqual(self.carts._row()[1], "RESULT_UNKNOWN")
        self.carts.close()
        self.stop_api()
        self.start_api()
        self.carts = self.make_carts()
        self.carts.receive("/conferircarrinho")
        self.pump()
        self.assertEqual(self.carts._row()[1], "RESULT_UNKNOWN")
        self.assertIn("desconhecido", self.carts.receive("/revisarcarrinho"))
        with self.assertRaises(CartError):
            self.client.review()
        self.assertEqual(self.synthetic("stats")["writes"], 1)


class ObservedShapeCartIntegration(CartIntegration):
    """Mesmo fluxo com a forma das respostas reais da INT-02 (valores sintéticos)."""

    SHAPE = "observed"

    def test_address_review_human_click_final_costs_replay_and_isolation(self):
        callback = self.choose_and_review()
        event = {"update_id": 60, "callback_query": callback}
        for _ in range(2):
            process_batch(
                self.telegram, self.state, [event], OWNER, "bot",
                conversations=Mock(), carts=self.carts,
            )
            self.pump()
        self.assertEqual(self.synthetic("stats")["writes"], 1)
        self.assertEqual(self.carts._row()[1], "SUCCEEDED")
        shown = self.telegram.send.call_args.args[1]
        self.assertIn("Total informado pelo iFood (não confirmado): R$ 15,99", shown)
        self.assertIn("Benefícios do iFood (não detalhados): R$ 10,00", shown)
        self.assertNotIn("Total observado", shown)
        self.assertIn("PEDIDO NÃO ENVIADO", shown)
