import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from telegram_bot.config import Config
from telegram_bot.runner import identify, poll, process_batch, reply_for
from telegram_bot.state import WEEK, State, single_instance
from telegram_bot.telegram import Telegram, TelegramError

TOKEN = "12345:" + "a" * 30
ALLOWED = 123456


def update(number=1, user=ALLOWED, chat_type="private", text="/start"):
    return {
        "update_id": number,
        "message": {
            "from": {"id": user, "is_bot": False},
            "chat": {"id": user, "type": chat_type},
            "text": text,
        },
    }


class FakeAPI:
    def __init__(self):
        self.sent = []
        self.failure = None

    def send(self, chat_id, text):
        if self.failure:
            raise self.failure
        self.sent.append((chat_id, text))


class AccessTests(unittest.TestCase):
    def test_start_status_and_help_for_organizer(self):
        for command in ["/start", "/start@demo_bot", "/help", "/ajuda", "/status"]:
            with self.subTest(command=command):
                self.assertIsNotNone(reply_for(update(text=command), ALLOWED, "demo_bot"))
        self.assertIn("não verificado", reply_for(update(text="/status"), ALLOWED, "demo_bot"))

    def test_other_user_and_nonprivate_chats_are_silent(self):
        for item in [
            update(user=999),
            update(chat_type="group"),
            update(chat_type="supergroup"),
            update(chat_type="channel"),
            {"update_id": 1, "callback_query": {"data": "approve"}},
            {"update_id": 1, "edited_message": update()["message"]},
        ]:
            with self.subTest(item=item):
                self.assertIsNone(reply_for(item, ALLOWED, "demo_bot"))

    def test_inconsistent_identity_and_business_message_rejected(self):
        variants = []
        item = update()
        item["message"]["chat"]["id"] = 999
        variants.append(item)
        item = update()
        item["message"]["from"]["is_bot"] = True
        variants.append(item)
        item = update()
        item["message"]["business_connection_id"] = "external"
        variants.append(item)
        item = update()
        del item["message"]["from"]
        variants.append(item)
        for item in variants:
            self.assertIsNone(reply_for(item, ALLOWED, "demo_bot"))

    def test_commands_to_another_bot_are_ignored(self):
        self.assertIsNone(reply_for(update(text="/start@other_bot"), ALLOWED, "demo_bot"))

    def test_user_text_is_not_echoed_or_treated_as_purchase(self):
        response = reply_for(update(text="CONFIRMAR pedido segredo-123"), ALLOWED, "demo_bot")
        self.assertNotIn("segredo-123", response)
        self.assertIn("não está disponível", response)

    def test_config_fails_closed_and_hides_token(self):
        for env in [
            {},
            {"TELEGRAM_BOT_TOKEN": TOKEN},
            {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_ALLOWED_USER_ID": "-1"},
        ]:
            with patch.dict("os.environ", env, clear=True), self.assertRaises(ValueError):
                Config.from_env()
        with patch.dict(
            "os.environ",
            {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_ALLOWED_USER_ID": str(ALLOWED)},
            clear=True,
        ):
            config = Config.from_env()
            self.assertEqual(ALLOWED, config.allowed_user_id)
            self.assertNotIn(TOKEN, repr(config))

    def test_identify_requires_exact_challenge_in_private_chat(self):
        class IdentifyAPI:
            def updates(self, offset):
                return [
                    update(1, user=999, text="/identificar errado"),
                    update(2, chat_type="group", text="/identificar challenge"),
                    update(3, text="/identificar challenge"),
                ]

        emitted = []
        with patch("telegram_bot.runner.secrets.token_urlsafe", return_value="challenge"):
            result = identify(IdentifyAPI(), clock=lambda: 0, emit=emitted.append)
        self.assertEqual(ALLOWED, result)
        self.assertIn(str(ALLOWED), emitted[-1])

    def test_identify_expires(self):
        clock = iter([0, 181])
        with self.assertRaisesRegex(ValueError, "expirou"):
            identify(FakeAPI(), clock=lambda: next(clock), emit=lambda _: None)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.sqlite3"
        self.state = State(self.path)
        self.api = FakeAPI()

    def tearDown(self):
        self.state.close()
        self.temp.cleanup()

    def test_duplicate_and_restart_do_not_reply_again(self):
        process_batch(self.api, self.state, [update(), update()], ALLOWED, "demo_bot")
        self.state.close()
        self.state = State(self.path)
        process_batch(self.api, self.state, [update()], ALLOWED, "demo_bot")
        self.assertEqual(1, len(self.api.sent))
        self.assertEqual(2, self.state.offset())

    def test_unauthorized_updates_are_consumed_without_reply(self):
        process_batch(self.api, self.state, [update(user=999)], ALLOWED, "demo_bot")
        self.assertEqual([], self.api.sent)
        self.assertEqual(2, self.state.offset())

    def test_failed_send_does_not_advance_cursor(self):
        self.api.failure = TelegramError(500)
        with self.assertRaises(TelegramError):
            process_batch(self.api, self.state, [update()], ALLOWED, "demo_bot")
        self.assertIsNone(self.state.offset())
        self.api.failure = None
        process_batch(self.api, self.state, [update()], ALLOWED, "demo_bot")
        self.assertEqual(1, len(self.api.sent))

    def test_blocked_bot_does_not_stall_queue(self):
        self.api.failure = TelegramError(403)
        process_batch(self.api, self.state, [update()], ALLOWED, "demo_bot")
        self.assertEqual(2, self.state.offset())

    def test_random_id_after_week_is_not_discarded(self):
        self.state.clock = lambda: 0
        self.state.done(99999)
        self.state.clock = lambda: WEEK
        self.assertIsNone(self.state.offset())
        process_batch(self.api, self.state, [update(1)], ALLOWED, "demo_bot")
        self.assertEqual(1, len(self.api.sent))

    def test_single_instance_rejects_concurrent_process_and_releases(self):
        lock = Path(self.temp.name) / "bot.lock"
        with single_instance(lock), self.assertRaises(ValueError), single_instance(lock):
            self.fail("Segunda instância aceita")
        with single_instance(lock):
            pass

    def test_poll_respects_retry_after_and_conflict_stops(self):
        class RetryAPI:
            def __init__(self):
                self.calls = 0

            def updates(self, offset):
                self.calls += 1
                raise TelegramError(429, 12) if self.calls == 1 else TelegramError(409)

        waits = []
        with patch("builtins.print"), self.assertRaises(TelegramError) as error:
            poll(RetryAPI(), self.state, ALLOWED, "demo_bot", sleep=waits.append)
        self.assertEqual([12], waits)
        self.assertEqual(409, error.exception.code)


class TransportTests(unittest.TestCase):
    def test_poll_request_and_timeout(self):
        class Opener:
            def open(self, request, timeout):
                self.request, self.timeout = request, timeout
                return io.BytesIO(b'{"ok":true,"result":[]}')

        opener = Opener()
        Telegram(TOKEN, opener).updates(42)
        payload = json.loads(opener.request.data)
        self.assertEqual(42, payload["offset"])
        self.assertEqual(["message", "callback_query"], payload["allowed_updates"])
        self.assertGreater(opener.timeout, payload["timeout"])

    def test_errors_do_not_expose_url_token_or_remote_body(self):
        class Opener:
            def open(self, request, timeout):
                raise URLError(TOKEN)

        with self.assertRaises(TelegramError) as error:
            Telegram(TOKEN, Opener()).call("getMe")
        self.assertNotIn(TOKEN, str(error.exception))

        class HttpOpener:
            def open(self, request, timeout):
                raise HTTPError(
                    request.full_url,
                    429,
                    TOKEN,
                    {},
                    io.BytesIO(
                        json.dumps(
                            {"description": TOKEN, "parameters": {"retry_after": 9}}
                        ).encode()
                    ),
                )

        with self.assertRaises(TelegramError) as error:
            Telegram(TOKEN, HttpOpener()).call("getMe")
        self.assertEqual(9, error.exception.retry_after)
        self.assertNotIn(TOKEN, str(error.exception))

    def test_webhook_blocks_startup_without_deletion(self):
        api = Telegram(TOKEN)
        with patch.object(
            api,
            "call",
            side_effect=[
                {"is_bot": True, "id": 123, "username": "demo_bot"},
                {"url": "https://example.org"},
            ],
        ) as call:
            with self.assertRaisesRegex(ValueError, "webhook ativo"):
                api.check()
            self.assertEqual(["getMe", "getWebhookInfo"], [c.args[0] for c in call.call_args_list])

    def test_no_unimplemented_methods(self):
        with self.assertRaises(ValueError):
            Telegram(TOKEN).call("deleteWebhook")


if __name__ == "__main__":
    unittest.main()
