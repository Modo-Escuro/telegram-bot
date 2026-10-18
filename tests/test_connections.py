import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from telegram_bot.backend import Backend, BackendConfig, BackendError, LinkStatus
from telegram_bot.connections import Connections, status_reply, status_text
from telegram_bot.runner import process_batch, reply_for
from telegram_bot.state import State
from telegram_bot.telegram import TelegramError

USER = 123456
SECRET = "x" * 40
CONFIRM = "c" * 24
ATTEMPT = "a" * 24


def payload(state="DISCONNECTED", operational=False, ops=None):
    return {
        "state": state,
        "operational": operational,
        "allowedOperations": ops or [],
        "linkId": "l" * 24 if operational else None,
        "attempt": None,
    }


def pending():
    body = payload("AWAITING_CONFIRMATION")
    body["attempt"] = {
        "attemptId": ATTEMPT,
        "status": "PENDING_CONFIRMATION",
        "confirmationId": CONFIRM,
        "accountIdentity": {
            "status": "VERIFIED",
            "displayName": "Maria S.",
            "emailMasked": "m***@example.com",
        },
    }
    return LinkStatus.parse(body)


def update(n=1, user=USER, text="/ifood"):
    return {
        "update_id": n,
        "message": {
            "from": {"id": user, "is_bot": False},
            "chat": {"id": user, "type": "private"},
            "text": text,
        },
    }


def click(n=1, user=USER, confirmation=CONFIRM):
    return {
        "update_id": n,
        "callback_query": {
            "id": "telegram-callback",
            "from": {"id": user, "is_bot": False},
            "message": {"message_id": 10, "chat": {"id": USER, "type": "private"}},
            "data": "ifc:" + confirmation,
        },
    }


class TransportTests(unittest.TestCase):
    def client(self, result):
        opener = Mock()
        opener.open.return_value = io.BytesIO(json.dumps(result).encode())
        return Backend(BackendConfig("http://localhost:8000", SECRET, USER), opener), opener

    def test_identity_headers_and_confirm_contract(self):
        backend, opener = self.client(payload("CONNECTED", True, ["ADDRESSES_READ"]))
        backend.confirm(CONFIRM)
        req = opener.open.call_args.args[0]
        self.assertEqual("POST", req.method)
        self.assertEqual("Bearer " + SECRET, req.get_header("Authorization"))
        self.assertEqual(str(USER), req.get_header("X-telegram-user-id"))
        self.assertEqual({"confirmationId": CONFIRM}, json.loads(req.data))
        self.assertEqual(50, opener.open.call_args.kwargs["timeout"])

    def test_insecure_remote_or_credential_url_rejected(self):
        for url in [
            "http://example.com",
            "https://user:pass@example.com",
            "https://a.test/path",
            "https://a.test?token=x",
            "http://127.0.0.1:0",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                BackendConfig(url, SECRET, USER)
        self.assertNotIn(SECRET, repr(BackendConfig("https://api.example.com", SECRET, USER)))

    def test_connect_url_must_match_backend_and_attempt(self):
        body = payload("AWAITING_AUTHORIZATION")
        body["attempt"] = {"attemptId": ATTEMPT, "status": "PENDING_AUTHORIZATION"}
        for url in [
            "https://evil.test/auth/ifood/start?a=" + ATTEMPT + "&t=" + SECRET,
            "http://localhost:8000/auth/ifood/start?a=wrong&t=" + SECRET,
            "http://localhost:8000/auth/ifood/start?a=" + ATTEMPT + "&t=" + SECRET,
        ]:
            backend, _ = self.client({**body, "authorizationUrl": url})
            if url.endswith("a=" + ATTEMPT + "&t=" + SECRET) and url.startswith("http:"):
                self.assertEqual(url, backend.connect()[1])
            else:
                with self.assertRaises(BackendError):
                    backend.connect()

    def test_timeout_no_retry_or_remote_secrets(self):
        backend, opener = self.client({})
        opener.open.side_effect = URLError(SECRET)
        with self.assertRaises(BackendError) as ctx:
            backend.confirm(CONFIRM)
        self.assertTrue(ctx.exception.uncertain)
        self.assertNotIn(SECRET, str(ctx.exception))
        self.assertEqual(1, opener.open.call_count)

    def test_known_http_errors_sanitized(self):
        backend, opener = self.client({})
        opener.open.side_effect = HTTPError(
            "http://localhost",
            410,
            SECRET,
            {},
            io.BytesIO(
                json.dumps({"error": {"kind": "CONFIRMATION_EXPIRED", "message": SECRET}}).encode()
            ),
        )
        with self.assertRaises(BackendError) as ctx:
            backend.confirm(CONFIRM)
        self.assertEqual("CONFIRMATION_EXPIRED", ctx.exception.kind)
        self.assertNotIn(SECRET, str(ctx.exception))

    def test_bad_status_not_connected(self):
        for body in [
            {},
            payload("invented"),
            {
                **payload("CONNECTED", True, ["ADDRESSES_READ"]),
                "linkId": None,
            },
        ]:
            with self.assertRaises(BackendError):
                LinkStatus.parse(body)

    def test_malformed_state_does_not_crash_polling(self):
        for state in [[], {}, 123, None]:
            with self.assertRaises(BackendError):
                LinkStatus.parse(payload(state))

    def test_configuration_optional_but_partial_rejected(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(BackendConfig.from_env(USER))
        with (
            patch.dict("os.environ", {"BACKEND_BASE_URL": "http://localhost:8000"}, clear=True),
            self.assertRaises(ValueError),
        ):
            BackendConfig.from_env(USER)
        with patch.dict(
            "os.environ",
            {
                "BACKEND_BASE_URL": "http://localhost:8000",
                "BACKEND_API_TOKEN": SECRET,
            },
            clear=True,
        ):
            self.assertEqual(USER, BackendConfig.from_env(USER).organizer_id)

    def test_callback_id_cannot_exceed_telegram_limit(self):
        body = payload("AWAITING_CONFIRMATION")
        body["attempt"] = {
            "attemptId": ATTEMPT,
            "status": "PENDING_CONFIRMATION",
            "confirmationId": "a" * 61,
        }
        with self.assertRaises(BackendError):
            LinkStatus.parse(body)

    def test_connected_without_operation_is_not_ready(self):
        text = status_text(LinkStatus.parse(payload("CONNECTED")))
        self.assertIn("ainda não liberado", text)
        self.assertIn("não aprova", text)

    def test_identity_unknown_is_explicit(self):
        status = pending()
        status = LinkStatus(
            status.state, False, (), ATTEMPT, "PENDING_CONFIRMATION", None, CONFIRM, None
        )
        self.assertIn("Não foi possível verificar", status_reply(status).text)


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.sqlite3"
        self.state = State(self.path)
        self.backend = Mock()
        self.backend.status.return_value = pending()
        self.backend.confirm.return_value = LinkStatus.parse(
            payload("CONNECTED", True, ["ADDRESSES_READ"])
        )
        self.connections = Connections(self.backend, self.state)
        self.api = Mock()

    def tearDown(self):
        self.state.close()
        self.temp.cleanup()

    def test_unauthorized_message_or_click_never_calls_backend(self):
        process_batch(
            self.api,
            self.state,
            [update(user=999), click(2, user=999)],
            USER,
            "demo",
            self.connections,
        )
        self.backend.assert_not_called()
        self.assertEqual([], self.backend.mock_calls)
        self.api.send.assert_not_called()

    def test_confirm_command_only_presents_button(self):
        reply = reply_for(update(text="/confirmar"), USER, "demo", self.connections)
        self.assertIn("Maria S.", reply.text)
        data = reply.markup["inline_keyboard"][0][0]["callback_data"]
        self.assertEqual("ifc:" + CONFIRM, data)
        self.assertLessEqual(len(data.encode()), 64)
        self.backend.confirm.assert_not_called()

    def test_confirm_with_code_rejected(self):
        reply = reply_for(update(text="/confirmar ABC-234"), USER, "demo", self.connections)
        self.assertIn("sem argumentos", reply.text)
        self.backend.status.assert_not_called()

    def test_stale_button_does_not_confirm_new_attempt(self):
        reply = self.connections.confirm_click("z" * 24, 1)
        self.assertEqual(reply.markup["inline_keyboard"][0][0]["callback_data"], "ifc:" + CONFIRM)
        self.backend.confirm.assert_not_called()

    def test_click_acknowledged_and_keyboard_removed(self):
        process_batch(self.api, self.state, [click()], USER, "demo", self.connections)
        self.backend.confirm.assert_called_once_with(CONFIRM)
        self.assertEqual("answerCallbackQuery", self.api.call.call_args_list[0].args[0])
        self.assertEqual("editMessageReplyMarkup", self.api.call.call_args_list[-1].args[0])

    def test_send_failure_and_restart_never_repeat_confirmation(self):
        self.api.send.side_effect = TelegramError(500)
        with self.assertRaises(TelegramError):
            process_batch(self.api, self.state, [click()], USER, "demo", self.connections)
        self.state.close()
        self.state = State(self.path)
        self.connections = Connections(self.backend, self.state)
        self.api.send.side_effect = None
        self.backend.status.return_value = self.backend.confirm.return_value
        process_batch(self.api, self.state, [click()], USER, "demo", self.connections)
        self.backend.confirm.assert_called_once()

    def test_connect_timeout_is_not_retried_on_replay(self):
        self.backend.connect.side_effect = BackendError(uncertain=True)
        first = self.connections.reply("/conectar", [], 1)
        second = self.connections.reply("/conectar", [], 1)
        self.assertIn("Não a repetirei", first.text)
        self.backend.connect.assert_called_once()
        self.assertIsNotNone(second.text)

    def test_verify_and_status_use_correct_operations(self):
        self.backend.verify.return_value = LinkStatus.parse(payload("UNAVAILABLE"))
        self.assertIn("não significa logout", self.connections.reply("/verificar", [], 1).text)
        self.connections.reply("/ifood", [], 2)
        self.backend.verify.assert_called_once()
        self.backend.status.assert_called_once()

    def test_missing_config_does_not_access_account(self):
        reply = Connections(None, self.state).reply("/conectar", [], 1)
        self.assertIn("não foi configurada", reply.text)
