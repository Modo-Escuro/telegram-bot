"""Senha e isolamento com credenciais e usuários sintéticos; nunca consome Telegram real."""

import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError

from test_conversation_worker import Fixture
from test_conversation_worker import update as conversation_update

from telegram_bot.access import SESSION_SECONDS, AccessStore
from telegram_bot.backend import BackendConfig
from telegram_bot.config import Config
from telegram_bot.conversation import ConversationClient
from telegram_bot.conversation_runner import scope_for
from telegram_bot.multiuser import PasswordRouter, UserSession
from telegram_bot.state import State
from telegram_bot.telegram import Telegram, TelegramError

PASSWORD = "synthetic-password"
TOKEN = "900001:" + "x" * 30
A, B, BOT = 111111111, 222222222, 900001


def update(n, owner=A, text="/start", chat_type="private"):
    return {
        "update_id": n,
        "message": {
            "message_id": n + 100,
            "from": {"id": owner, "is_bot": False},
            "chat": {"id": owner, "type": chat_type},
            "text": text,
        },
    }


class AccessTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "access.sqlite3"
        self.now = 100000
        self.store = self.open()

    def open(self, password=PASSWORD, capacity=100):
        store = AccessStore(self.path, password, TOKEN, clock=lambda: self.now, capacity=capacity)
        self.addCleanup(store.close)
        return store

    def test_two_users_restart_and_password_rotation(self):
        self.assertEqual(self.store.enter(A, PASSWORD), "OK")
        self.assertFalse(self.store.allowed(B))
        self.assertEqual(self.store.enter(B, PASSWORD), "OK")
        self.assertEqual(self.open().owners(), [A, B])
        self.assertFalse(self.open("different-synthetic-password").allowed(A))
        self.assertTrue(self.store.allowed(A))

    def test_expiration_and_logout_do_not_authorize_other_user(self):
        self.store.enter(A, PASSWORD)
        self.store.enter(B, PASSWORD)
        self.store.revoke(A)
        self.assertFalse(self.store.checker(A)())
        self.assertTrue(self.store.checker(B)())
        self.now += SESSION_SECONDS
        self.assertFalse(self.store.allowed(B))

    def test_failed_attempts_survive_restart_and_unlock_after_window(self):
        for _ in range(5):
            self.assertEqual(self.store.enter(A, "wrong-synthetic"), "DENIED")
        self.assertEqual(self.open().enter(A, PASSWORD), "LIMIT")
        self.assertEqual(self.store.enter(B, PASSWORD), "OK")
        self.now += 901
        self.assertEqual(self.store.enter(A, PASSWORD), "OK")

    def test_global_attempt_limit_and_capacity(self):
        store = self.open(capacity=1)
        self.assertEqual(store.enter(A, PASSWORD), "OK")
        self.assertEqual(store.enter(B, PASSWORD), "FULL")
        for owner in range(1, 99):
            store.enter(owner, "wrong-synthetic")
        self.assertEqual(store.enter(999, PASSWORD), "LIMIT")

    def test_password_never_persisted_and_notice_is_limited(self):
        self.store.enter(A, PASSWORD)
        self.store.enter(B, "wrong-synthetic")
        dump = "\n".join(self.store.db.iterdump())
        for text in [PASSWORD, TOKEN, "wrong-synthetic"]:
            self.assertNotIn(text, dump)
        self.assertTrue(self.store.notice(A))
        self.assertFalse(self.store.notice(A))
        self.now += 61
        self.assertTrue(self.store.notice(A))


class RouterTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name)
        self.state = State(self.path / f"bot-{BOT}.sqlite3")
        self.addCleanup(self.state.close)
        self.config = Config(TOKEN, A, self.path, False, PASSWORD)
        self.created = {}

        def factory(config, bot, owner, check):
            session = Mock()
            session.check = check
            self.created[owner] = session
            return session

        self.router = PasswordRouter(self.config, BOT, self.state, session_factory=factory)
        self.addCleanup(self.router.close)
        self.api = Mock()

    def receive(self, *updates):
        self.router.receive(self.api, updates, "demo_bot")

    def test_unauthenticated_text_and_callback_do_not_reach_backend(self):
        self.receive(update(1, text="Dados que não devem chegar ao modelo"))
        self.assertEqual(self.created, {})
        self.assertNotIn("Dados", self.api.send.call_args.args[1])
        callback = {
            "update_id": 2,
            "callback_query": {
                "id": "synthetic",
                "from": {"id": A, "is_bot": False},
                "message": {"message_id": 10, "chat": {"id": B, "type": "private"}},
                "data": "ifc:synthetic-confirmation",
            },
        }
        self.receive(callback)
        self.assertEqual(self.created, {})

    def test_password_command_deleted_and_never_forwarded_even_for_authenticated_user(self):
        self.receive(update(1, text="/entrar " + PASSWORD))
        self.api.call.assert_called_with("deleteMessage", {"chat_id": A, "message_id": 101})
        self.created[A].receive.assert_not_called()
        self.receive(update(2, text="/entrar " + PASSWORD))
        self.created[A].receive.assert_not_called()
        self.assertNotIn(PASSWORD, "\n".join(self.router.access.db.iterdump()))

    def test_users_dispatched_separately_and_logout_blocks_callbacks(self):
        self.receive(update(1, text="/entrar " + PASSWORD), update(2, B, "/entrar " + PASSWORD))
        self.receive(update(3, text="/conectar"), update(4, B, "/conectar"))
        self.assertEqual(self.created[A].receive.call_args.args[1]["message"]["from"]["id"], A)
        self.assertEqual(self.created[B].receive.call_args.args[1]["message"]["from"]["id"], B)
        self.receive(update(5, text="/sair"))
        self.assertFalse(self.created[A].check())
        self.assertTrue(self.created[B].check())
        self.receive(update(6, text="/conectar"))
        self.assertEqual(self.created[A].receive.call_count, 1)

    def test_groups_edited_messages_and_other_bot_commands_never_admit(self):
        self.receive(update(1, text="/entrar " + PASSWORD, chat_type="group"))
        self.receive(update(2, text="/entrar@outro_bot " + PASSWORD))
        self.receive(
            {"update_id": 3, "edited_message": update(3, text="/entrar " + PASSWORD)["message"]}
        )
        self.assertFalse(self.router.access.allowed(A))
        self.assertEqual(self.created, {})

    def test_replay_does_not_redeliver_and_restart_reconstructs_authenticated_users(self):
        self.receive(update(1, text="/entrar " + PASSWORD))
        self.receive(update(2, text="/conectar"))
        self.receive(update(2, text="/conectar"))
        self.assertEqual(self.created[A].receive.call_count, 1)
        other = PasswordRouter(self.config, BOT, self.state, session_factory=self.router.factory)
        self.addCleanup(other.close)
        other.tick(self.api)
        self.assertIn(A, other.sessions)

    def test_delete_message_failure_does_not_echo_password(self):
        self.api.call.side_effect = TelegramError(code=400)
        self.receive(update(1, text="/entrar " + PASSWORD))
        self.assertTrue(self.router.access.allowed(A))
        self.assertNotIn(PASSWORD, self.api.send.call_args.args[1])

    def test_password_entry_with_real_telegram_client_and_fake_http(self):
        # Regressão do crash real: Mock de Telegram.call escondia a lista METHODS do transporte.
        for number, failure in enumerate([None, 400, 403, 429, 500], start=1):
            with self.subTest(delete_error=failure):
                calls = []

                class Opener:
                    def __init__(self, recorded, error):
                        self.recorded, self.error = recorded, error

                    def open(self, request, timeout):
                        method = request.full_url.rsplit("/", 1)[-1]
                        payload = json.loads(request.data)
                        self.recorded.append((method, payload))
                        if method == "deleteMessage" and self.error:
                            raise HTTPError(
                                request.full_url, self.error, "synthetic", {}, io.BytesIO(b"{}")
                            )
                        result = True if method == "deleteMessage" else {"message_id": 900}
                        return io.BytesIO(json.dumps({"ok": True, "result": result}).encode())

                telegram = Telegram(TOKEN, Opener(calls, failure))
                message = update(number, text="/entrar " + PASSWORD)
                self.router.receive(telegram, [message], "demo_bot")
                self.assertTrue(self.router.access.allowed(A))
                self.assertEqual(self.state.offset(), number + 1)
                self.assertEqual([c[0] for c in calls], ["deleteMessage", "sendMessage"])
                self.assertEqual(calls[0][1], {"chat_id": A, "message_id": 100 + number})
                self.assertIn("Acesso à demo liberado", calls[1][1]["text"])
                self.assertNotIn(PASSWORD, json.dumps(calls))
                self.router.receive(telegram, [message], "demo_bot")
                self.assertEqual(len(calls), 2)  # Replay não repete remoção/entrada.

    def test_real_sessions_keep_legacy_state_and_separate_login_watch(self):
        self.state.watch_login(A, "synthetic-attempt-a", self.state.clock() + 500)
        a = UserSession(self.config, BOT, A, lambda: True)
        b = UserSession(self.config, BOT, B, lambda: True)
        try:
            b.state.watch_login(B, "synthetic-attempt-b", b.state.clock() + 500)
            self.assertEqual(a.state.login_watch()["owner"], A)
            self.assertEqual(b.state.login_watch()["owner"], B)
            b.state.stop_login_watch()
            self.assertEqual(a.state.login_watch()["attempt_id"], "synthetic-attempt-a")
        finally:
            a.close()
            b.close()

    def test_two_outboxes_preserve_routing_scope_and_hide_password(self):
        cfg = replace(self.config, conversation_enabled=True)
        backend_env = {
            "BACKEND_BASE_URL": "http://127.0.0.1:9999",
            "BACKEND_API_TOKEN": "synthetic-token-xxxxxxxxxxxxxxxxxxxxx",
        }
        with (
            patch.dict("os.environ", backend_env, clear=True),
            patch("telegram_bot.multiuser.ConversationService"),
            patch("telegram_bot.conversation.build_opener", return_value=Mock()),
            patch("telegram_bot.backend.build_opener", return_value=Mock()),
        ):
            a = UserSession(cfg, BOT, A, lambda: True)
            b = UserSession(cfg, BOT, B, lambda: True)
            try:
                a.receive(self.api, update(1, text="Mensagem sintética A"), "demo_bot")
                b.receive(self.api, update(2, B, "Mensagem sintética B"), "demo_bot")
                self.assertNotEqual(a.box.scope, b.box.scope)
                self.assertEqual(
                    json.loads(bytes(a.box.active()["body"]))["input"]["text"],
                    "Mensagem sintética A",
                )
                self.assertEqual(
                    json.loads(bytes(b.box.active()["body"]))["input"]["text"],
                    "Mensagem sintética B",
                )
                self.assertEqual(a.connections.backend.config.organizer_id, A)
                self.assertEqual(b.connections.backend.config.organizer_id, B)
                self.assertTrue(b.connections.backend.config.password_access)
                self.assertEqual(a.box.scope, scope_for(a.connections.backend.config, BOT))
            finally:
                a.close()
                b.close()

    def test_conversation_http_uses_own_identity_and_password_marker_only(self):
        opener = Mock()
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 404
        response.read.return_value = b"{}"
        response.headers.get_content_type.return_value = "application/json"
        opener.open.return_value = response
        client = ConversationClient(
            BackendConfig(
                "http://127.0.0.1:9999", "synthetic-token-xxxxxxxxxxxxxxxxxxxxx", B, True
            ),
            BOT,
            opener=opener,
        )
        from telegram_bot.conversation import ConversationError

        with self.assertRaises(ConversationError):
            client.get_snapshot()
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header("X-telegram-user-id"), str(B))
        self.assertEqual(request.get_header("X-telegram-access"), "PASSWORD")
        self.assertNotIn(PASSWORD, str(request.header_items()))

    def test_public_config_needs_no_allowlist_and_password_is_hidden(self):
        with patch.dict(
            "os.environ",
            {
                "TELEGRAM_BOT_TOKEN": TOKEN,
                "TELEGRAM_ACCESS_PASSWORD": PASSWORD,
                "TELEGRAM_ALLOWED_USER_ID": "",
            },
            clear=True,
        ):
            cfg = Config.from_env()
            self.assertIsNone(cfg.allowed_user_id)
            self.assertNotIn(PASSWORD, repr(cfg))
        with (
            patch.dict(
                "os.environ",
                {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_ACCESS_PASSWORD": "x"},
                clear=True,
            ),
            self.assertRaises(ValueError),
        ):
            Config.from_env()


class WorkerAccessTests(Fixture):
    def test_expired_access_never_sends_queued_text(self):
        self.adapter.receive(conversation_update())
        self.worker.access_allowed = lambda: False
        self.tick(3)
        self.assertEqual(self.client.sent, [])
        self.telegram.send.assert_not_called()

    def test_logout_during_snapshot_read_blocks_delivery(self):
        self.adapter.receive(conversation_update())
        self.tick(2)
        authorized = True
        original = self.client.get_snapshot

        def revoke():
            nonlocal authorized
            authorized = False
            return original()

        self.worker.access_allowed = lambda: authorized
        self.client.get_snapshot = revoke
        self.tick(3)
        self.telegram.send.assert_not_called()
