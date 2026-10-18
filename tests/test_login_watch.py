"""BOT-02: relógio, Telegram e backend falsos; nenhum polling/token real."""

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock
from urllib.error import URLError

from test_connections import ATTEMPT, CONFIRM, SECRET, USER, click, payload, pending, update

from telegram_bot.backend import Backend, BackendConfig, BackendError, LinkStatus
from telegram_bot.connections import Connections, status_reply
from telegram_bot.runner import poll, process_batch
from telegram_bot.state import State
from telegram_bot.telegram import Telegram, TelegramError


def authorizing(expires=600, attempt=ATTEMPT):
    return LinkStatus(
        "AWAITING_AUTHORIZATION",
        False,
        (),
        attempt,
        "PENDING_AUTHORIZATION",
        None,
        attempt_expires_at=expires,
    )


class WatchEnvironment:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.sqlite3"
        self.now = 0
        self.state = State(self.path, clock=lambda: self.now)
        self.backend = Mock()
        self.backend.connect.return_value = (
            authorizing(),
            "https://api.example.test/private-login",
        )
        self.backend.status.return_value = authorizing()
        self.backend.confirm.return_value = LinkStatus.parse(
            payload("CONNECTED", True, ["ADDRESSES_READ"])
        )
        self.connections = Connections(self.backend, self.state, USER)
        self.api = Mock()
        self.api.send.return_value = {"message_id": 50}

    def tearDown(self):
        self.state.close()
        self.temp.cleanup()

    def start(self):
        process_batch(
            self.api, self.state, [update(text="/conectar")], USER, "demo", self.connections
        )
        self.api.reset_mock()

    def awaiting_confirmation(self, expires=900):
        self.backend.status.return_value = replace(pending(), attempt_expires_at=expires)


class WatchTests(WatchEnvironment, unittest.TestCase):
    def test_authorization_updates_known_message_without_confirming(self):
        self.start()
        self.awaiting_confirmation()
        self.connections.tick(self.api, USER)
        self.backend.status.assert_called_once_with(timeout=5)
        method, body = self.api.call.call_args.args
        self.assertEqual("editMessageText", method)
        self.assertEqual(50, body["message_id"])
        self.assertEqual(USER, body["chat_id"])
        self.assertEqual(
            "ifc:" + CONFIRM, body["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        )
        self.backend.confirm.assert_not_called()
        self.api.send.assert_not_called()

    def test_same_phase_does_not_edit_again_even_after_restart(self):
        self.start()
        self.awaiting_confirmation()
        self.connections.tick(self.api, USER)
        self.state.close()
        self.state = State(self.path, clock=lambda: self.now)
        self.connections = Connections(self.backend, self.state, USER)
        self.now = 6
        self.connections.tick(self.api, USER)
        self.api.call.assert_called_once()
        self.assertEqual(900, self.state.login_watch()["expires"])

    def test_restart_before_callback_recovers_attempt_and_message(self):
        self.start()
        self.state.close()
        self.state = State(self.path, clock=lambda: self.now)
        self.connections = Connections(self.backend, self.state, USER)
        self.awaiting_confirmation()
        self.connections.tick(self.api, USER)
        self.assertEqual(50, self.api.call.call_args.args[1]["message_id"])

    def test_only_metadata_is_persisted(self):
        self.start()
        self.awaiting_confirmation()
        self.connections.tick(self.api, USER)
        dump = "\n".join(self.state.db.iterdump())
        for secret in (SECRET, CONFIRM, "private-login", "Maria", "@example.com"):
            self.assertNotIn(secret, dump)
        self.assertIn(ATTEMPT, dump)

    def test_queries_are_spaced_and_bounded(self):
        self.start()
        self.connections.tick(self.api, USER)
        self.connections.tick(self.api, USER)
        self.assertEqual(1, self.backend.status.call_count)
        self.now = 1200
        self.connections.tick(self.api, USER)
        self.assertFalse(self.connections.watching)
        self.assertEqual(1, self.backend.status.call_count)

    def test_callback_just_before_auth_expiry_can_extend_confirmation_window(self):
        self.start()
        self.now = 601
        self.awaiting_confirmation(expires=1190)
        self.connections.tick(self.api, USER)
        self.assertTrue(self.connections.watching)
        self.assertEqual(1190, self.state.login_watch()["expires"])

    def test_expired_attempt_removes_keyboard_and_stops(self):
        self.start()
        self.now = 600
        self.connections.tick(self.api, USER)
        self.assertFalse(self.connections.watching)
        self.assertIn("expirou", self.api.call.call_args.args[1]["text"])
        self.assertEqual([], self.api.call.call_args.args[1]["reply_markup"]["inline_keyboard"])

    def test_explicit_zero_expiry_is_not_replaced_with_a_future_deadline(self):
        self.start()
        self.awaiting_confirmation(expires=0)
        self.connections.tick(self.api, USER)
        self.assertFalse(self.connections.watching)
        self.assertIn("expirou", self.api.call.call_args.args[1]["text"])

    def test_temporary_backend_failure_does_not_logout_or_confirm(self):
        self.start()
        self.backend.status.side_effect = BackendError()
        self.connections.tick(self.api, USER)
        self.assertTrue(self.connections.watching)
        self.api.call.assert_not_called()
        self.backend.confirm.assert_not_called()
        self.backend.disconnect.assert_not_called()
        self.now = 601
        self.connections.tick(self.api, USER)
        self.assertFalse(self.connections.watching)

    def test_replaced_attempt_is_not_silently_adopted(self):
        self.start()
        self.backend.status.return_value = authorizing(attempt="n" * 24)
        self.connections.tick(self.api, USER)
        self.assertFalse(self.connections.watching)
        self.assertIn("substituída", self.api.call.call_args.args[1]["text"])

    def test_other_organizer_cannot_receive_saved_notification(self):
        self.start()
        self.connections = Connections(self.backend, self.state, USER + 1)
        self.connections.tick(self.api, USER + 1)
        self.backend.status.assert_not_called()
        self.api.call.assert_not_called()
        self.assertIsNone(self.state.login_watch())

    def test_telegram_edit_retries_same_message_and_respects_rate_limit(self):
        self.start()
        self.awaiting_confirmation()
        self.api.call.side_effect = TelegramError(429, 20)
        self.connections.tick(self.api, USER)
        self.now = 6
        self.connections.tick(self.api, USER)
        self.assertEqual(1, self.api.call.call_count)
        self.api.call.side_effect = None
        self.now = 20
        self.connections.tick(self.api, USER)
        self.assertEqual([50, 50], [c.args[1]["message_id"] for c in self.api.call.call_args_list])
        self.api.send.assert_not_called()

    def test_deleted_message_ends_watcher_with_manual_fallback_available(self):
        self.start()
        self.awaiting_confirmation()
        self.api.call.side_effect = TelegramError(400)
        self.connections.tick(self.api, USER)
        self.assertFalse(self.connections.watching)
        self.api.call.side_effect = None
        reply = self.connections.reply("/confirmar", [], 2)
        self.assertIn("Confirmar conexão", repr(reply.markup))

    def test_send_failure_and_replay_attach_recovery_message_without_new_login(self):
        self.api.send.side_effect = TelegramError(500)
        with self.assertRaises(TelegramError):
            process_batch(
                self.api, self.state, [update(text="/conectar")], USER, "demo", self.connections
            )
        self.api.send.side_effect = None
        process_batch(
            self.api, self.state, [update(text="/conectar")], USER, "demo", self.connections
        )
        self.backend.connect.assert_called_once()
        self.assertEqual(50, self.state.login_watch()["message_id"])

    def test_confirmation_click_stops_watch_and_never_repeats_mutation(self):
        self.start()
        self.awaiting_confirmation()
        process_batch(self.api, self.state, [click(2)], USER, "demo", self.connections)
        self.assertFalse(self.connections.watching)
        process_batch(self.api, self.state, [click(2)], USER, "demo", self.connections)
        self.backend.confirm.assert_called_once_with(CONFIRM)

    def test_poll_uses_short_wait_only_for_pending_login(self):
        self.start()
        self.api.updates.side_effect = [[], TelegramError(409)]
        with self.assertRaises(TelegramError):
            poll(self.api, self.state, USER, "demo", connections=self.connections)
        self.assertEqual(3, self.api.updates.call_args.kwargs["timeout"])
        self.assertEqual(50, self.state.login_watch()["message_id"])


class AccountActionTests(WatchEnvironment, unittest.TestCase):
    def test_cancel_preserves_link_and_does_not_disconnect(self):
        connected = LinkStatus.parse(payload("CONNECTED", True, ["ADDRESSES_READ"]))
        self.backend.cancel.return_value = connected, True
        reply = self.connections.reply("/cancelar", [], 1)
        self.assertIn("preserva", reply.text)
        self.assertIn("conectada", reply.text)
        self.backend.cancel.assert_called_once()
        self.backend.disconnect.assert_not_called()

    def test_disconnect_preserves_attempt_and_does_not_claim_revocation(self):
        self.backend.disconnect.return_value = authorizing(), True
        reply = self.connections.reply("/desconectar", [], 1)
        self.assertIn("Não foi solicitada revogação", reply.text)
        self.assertIn("continua", reply.text)
        self.assertTrue(self.connections.watching)
        self.backend.cancel.assert_not_called()

    def test_replay_after_timeout_does_not_repeat_cancel_or_disconnect(self):
        for command, method in (
            ("/cancelar", self.backend.cancel),
            ("/desconectar", self.backend.disconnect),
        ):
            method.side_effect = BackendError(uncertain=True)
            n = 10 if command == "/cancelar" else 11
            self.assertIn("Não a repetirei", self.connections.reply(command, [], n).text)
            self.connections.reply(command, [], n)
            method.assert_called_once()

    def test_stale_cancel_and_disconnect_buttons_do_not_mutate(self):
        self.backend.status.return_value = authorizing(attempt="n" * 24)
        self.connections.action_click("ifx:" + ATTEMPT, 10)
        self.connections.action_click("ifd:" + "l" * 24, 11)
        self.backend.cancel.assert_not_called()
        self.backend.disconnect.assert_not_called()

    def test_unauthorized_callbacks_never_cancel_or_disconnect(self):
        for i, prefix in enumerate(("ifx:", "ifd:"), start=2):
            event = click(i, user=USER + 1)
            event["callback_query"]["data"] = prefix + ATTEMPT
            process_batch(self.api, self.state, [event], USER, "demo", self.connections)
        self.assertEqual([], self.backend.mock_calls)

    def test_matching_cancel_button_calls_only_cancel(self):
        self.backend.status.return_value = authorizing()
        self.backend.cancel.return_value = LinkStatus.parse(payload()), True
        event = click()
        event["callback_query"]["data"] = "ifx:" + ATTEMPT
        process_batch(self.api, self.state, [event], USER, "demo", self.connections)
        self.backend.cancel.assert_called_once()
        self.backend.disconnect.assert_not_called()

    def test_matching_disconnect_button_calls_only_disconnect(self):
        self.backend.status.return_value = LinkStatus.parse(
            payload("CONNECTED", True, ["ADDRESSES_READ"])
        )
        self.backend.disconnect.return_value = LinkStatus.parse(payload()), True
        event = click()
        event["callback_query"]["data"] = "ifd:" + "l" * 24
        process_batch(self.api, self.state, [event], USER, "demo", self.connections)
        self.backend.disconnect.assert_called_once()
        self.backend.cancel.assert_not_called()

    def test_oversize_references_do_not_generate_invalid_buttons(self):
        status = replace(authorizing(attempt="a" * 100), link_id="l" * 100)
        self.assertIsNone(status_reply(status).markup)


class ExtraTransportTests(unittest.TestCase):
    def test_additive_migration_preserves_existing_cursor_and_action(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.sqlite3"
            with closing(sqlite3.connect(path)) as db, db:
                db.execute(
                    "CREATE TABLE cursor (id INTEGER PRIMARY KEY, offset INTEGER, updated REAL)"
                )
                db.execute(
                    "CREATE TABLE actions (update_id INTEGER PRIMARY KEY, created REAL NOT NULL)"
                )
                db.execute("INSERT INTO cursor VALUES (1, 20, 1)")
                db.execute("INSERT INTO actions VALUES (19, 1)")
            state = State(path, clock=lambda: 2)
            try:
                self.assertEqual(20, state.offset())
                self.assertFalse(state.claim_action(19))
                self.assertIsNone(state.login_watch())
                self.assertEqual("ok", state.db.execute("PRAGMA integrity_check").fetchone()[0])
            finally:
                state.close()

    def client(self, body):
        opener = Mock()
        opener.open.return_value = io.BytesIO(json.dumps(body).encode())
        return Backend(BackendConfig("http://localhost:8000", SECRET, USER), opener), opener

    def test_cancel_and_disconnect_use_existing_routes(self):
        cases = [
            ("cancel", "POST", "cancel", {"cancelled": True}),
            (
                "disconnect",
                "DELETE",
                "link",
                {"removed": True, "providerRevocation": "NOT_ATTEMPTED"},
            ),
        ]
        for method, verb, path, fields in cases:
            client, opener = self.client({**payload(), **fields})
            _, changed = getattr(client, method)()
            request = opener.open.call_args.args[0]
            self.assertEqual(verb, request.method)
            self.assertTrue(request.full_url.endswith("/api/bot/ifood/" + path))
            self.assertTrue(changed)

    def test_disconnect_timeout_is_uncertain_and_never_retried(self):
        client, opener = self.client({})
        opener.open.side_effect = URLError(SECRET)
        with self.assertRaises(BackendError) as ctx:
            client.disconnect()
        self.assertTrue(ctx.exception.uncertain)
        opener.open.assert_called_once()
        self.assertNotIn(SECRET, str(ctx.exception))

    def test_invalid_mutation_responses_fail_closed(self):
        for fields in ({"removed": "yes"}, {"removed": True, "providerRevocation": "REVOKED"}):
            client, _ = self.client({**payload(), **fields})
            with self.assertRaises(BackendError):
                client.disconnect()

    def test_expiry_requires_timezone_and_valid_date(self):
        for value in (None, 123, "bad", "2026-10-18T00:00:00"):
            body = payload("AWAITING_AUTHORIZATION")
            body["attempt"] = {
                "attemptId": ATTEMPT,
                "status": "PENDING_AUTHORIZATION",
                "expiresAt": value,
            }
            with self.assertRaises(BackendError):
                LinkStatus.parse(body)
        body["attempt"]["expiresAt"] = "2026-10-18T00:00:00Z"
        self.assertEqual(
            datetime(2026, 10, 18, tzinfo=UTC).timestamp(),
            LinkStatus.parse(body).attempt_expires_at,
        )

    def test_telegram_short_polling_and_edit_have_no_parse_mode(self):
        opener = Mock()
        opener.open.return_value = io.BytesIO(b'{"ok":true,"result":[]}')
        telegram = Telegram("synthetic-token", opener)
        telegram.updates(None, timeout=3)
        self.assertEqual(3, json.loads(opener.open.call_args.args[0].data)["timeout"])
        opener.open.return_value = io.BytesIO(b'{"ok":true,"result":true}')
        telegram.call(
            "editMessageText", {"chat_id": USER, "message_id": 10, "text": "<b>plain</b>"}
        )
        self.assertNotIn("parse_mode", json.loads(opener.open.call_args.args[0].data))
