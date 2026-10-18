"""BOT-01: cenários sintéticos; sem Telegram/MCP/modelo reais."""

import copy
import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

from telegram_bot.backend import BackendConfig
from telegram_bot.config import Config
from telegram_bot.conversation import ConversationClient, ConversationError
from telegram_bot.conversation_contract import ProtocolError, Snapshot, encode
from telegram_bot.conversation_runner import Conversations, ConversationService, ConversationWorker
from telegram_bot.conversation_view import chunks, render
from telegram_bot.outbox import DAY, Outbox
from telegram_bot.runner import process_batch
from telegram_bot.state import State
from telegram_bot.telegram import TelegramError

NOW = datetime(2026, 10, 18, tzinfo=UTC).timestamp()
OWNER, BOT = 111111111, 900001
CONFIG = BackendConfig("http://127.0.0.1:9999", "synthetic-token-xxxxxxxxxxxxxxxxxxxxxxxxx", OWNER)


def update(number=1, text="Somos duas pessoas"):
    return {
        "update_id": number,
        "message": {
            "message_id": 100 + number,
            "from": {"id": OWNER, "is_bot": False},
            "chat": {"id": OWNER, "type": "private"},
            "text": text,
        },
    }


def snapshot(version=0, text="Resposta sintética"):
    return Snapshot(
        encode(
            {
                "contractVersion": "1.0",
                "conversationId": str(OWNER),
                "version": version,
                "phase": "COLLECTING",
                "blocks": [{"kind": "TEXT", "text": text, "source": "SERVER"}],
                "pending": [],
                "allowedActions": [],
                "humanApproval": None,
            }
        ),
        version,
        "COLLECTING",
    )


class FakeClient:
    """Usa a preparação/validação real do cliente; finge somente a API remota."""

    def __init__(self):
        self.real = ConversationClient(CONFIG, BOT)
        self.operations, self.sent = {}, []
        self.current = snapshot()
        self.finish = True
        self.failure = None
        self.lose_response = False

    def prepare_text(self, *args):
        return self.real.prepare_text(*args)

    def prepare_cancel(self, *args):
        return self.real.prepare_cancel(*args)

    def restore(self, *args):
        return self.real.restore(*args)

    def get_snapshot(self):
        if self.failure:
            raise self.failure
        return self.current

    def send(self, command):
        body = command.to_dict()
        self.sent.append(command.serialize())
        if self.failure:
            raise self.failure
        if command.schema == "cancel":
            self.finish = True
            self.cancelled = True
            return Mock(status="REQUESTED")
        event_id = body["eventId"]
        if event_id not in self.operations:
            raw = {
                "contractVersion": "1.0",
                "conversationId": str(OWNER),
                "eventId": event_id,
                "operationId": f"operation_synthetic_{len(self.operations):04d}",
                "baseVersion": body["expectedVersion"],
                "resultVersion": None,
                "status": "ACCEPTED",
                "createdAt": "2026-10-18T00:00:00Z",
                "deadlineAt": "2026-10-18T00:02:00Z",
                "pollAfterMs": 100,
                "completeness": "NONE",
                "snapshot": None,
                "changes": [],
                "error": None,
            }
            self.operations[event_id] = raw
        operation = self.real._operation(copy.deepcopy(self.operations[event_id]))
        if self.lose_response:
            self.lose_response = False
            raise ConversationError("UNAVAILABLE", uncertain=True)
        return operation

    def get_operation(self, operation_id, *, event_id):
        raw = copy.deepcopy(self.operations[event_id])
        if self.failure:
            raise self.failure
        if self.finish:
            version = raw["baseVersion"] + 1
            raw.update(
                status="SUCCEEDED",
                resultVersion=version,
                completeness="COMPLETE",
                pollAfterMs=None,
                snapshot=snapshot(version).to_dict(),
            )
            if self.current.version < version:
                self.current = snapshot(version)
        return self.real._operation(raw)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "bot.sqlite3"
        self.now = NOW
        self.state = State(self.path, clock=lambda: self.now)
        self.addCleanup(self.state.close)
        self.box = Outbox(self.path, "synthetic-scope", clock=lambda: self.now)
        self.addCleanup(self.box.close)
        self.client = FakeClient()
        self.adapter = Conversations(self.box, self.client)
        self.telegram = Mock()
        self.telegram.send.side_effect = lambda *args: {
            "message_id": 1000 + self.telegram.send.call_count
        }
        self.worker = ConversationWorker(
            self.box, self.client, self.telegram, OWNER, clock=lambda: self.now
        )

    def tick(self, count=1):
        for _ in range(count):
            self.worker.tick()
            self.now += 1

    def restart_box(self):
        other = Outbox(self.path, "synthetic-scope", clock=lambda: self.now)
        self.addCleanup(other.close)
        return other


class DurableTests(Fixture):
    def test_cancel_during_snapshot_lookup_cannot_resurrect_local_event(self):
        for failure in (None, ConversationError("UNAVAILABLE")):
            with self.subTest(failure=failure is not None):
                number = 1 if failure is None else 3
                self.adapter.receive(update(number))
                event = self.box.active()["seq"]

                def lookup(number=number, failure=failure):
                    # Outra conexão representa a thread de recebimento enquanto o GET está pendente.
                    other = self.restart_box()
                    Conversations(other, self.client).receive(
                        update(number + 1, "/interromper"), "/interromper"
                    )
                    if failure:
                        raise failure
                    return snapshot()

                self.client.get_snapshot = lookup
                self.tick()
                self.assertEqual(self.box.get(event)["state"], "CANCELLED")
                self.assertIsNone(self.box.get(event)["command"])
                self.assertEqual(self.client.sent, [])
                self.tick(3)

    def test_blocked_telegram_does_not_pin_local_status_cursor(self):
        self.telegram.send.side_effect = TelegramError(code=403)
        process_batch(
            self.telegram,
            self.state,
            [update(1, "/andamento")],
            OWNER,
            "bot",
            conversations=self.adapter,
        )
        self.assertEqual(self.state.offset(), 2)

    def test_feature_is_disabled_by_default_and_flag_is_strict(self):
        from unittest.mock import patch

        env = {"TELEGRAM_BOT_TOKEN": "12345:" + "a" * 30, "TELEGRAM_ALLOWED_USER_ID": str(OWNER)}
        with patch.dict("os.environ", env, clear=True):
            self.assertFalse(Config.from_env().conversation_enabled)
        with patch.dict("os.environ", {**env, "TELEGRAM_CONVERSATION_ENABLED": "true"}, clear=True):
            self.assertTrue(Config.from_env().conversation_enabled)
        with (
            patch.dict("os.environ", {**env, "TELEGRAM_CONVERSATION_ENABLED": "yes"}, clear=True),
            self.assertRaises(ValueError),
        ):
            Config.from_env()

    def test_cursor_and_receipt_commit_together_and_duplicate_does_not_duplicate(self):
        self.adapter.receive(update())
        self.assertEqual(self.state.offset(), 2)
        self.adapter.receive(update())
        self.assertEqual(
            self.box.db.execute("SELECT count(*) FROM conversation_outbox").fetchone()[0], 1
        )
        self.assertIsNotNone(self.restart_box().active())

    def test_crash_before_cursor_rolls_back_receipt(self):
        self.box.db.execute(
            "CREATE TRIGGER fail_cursor BEFORE INSERT ON cursor BEGIN SELECT RAISE(ABORT,'synthetic failure'); END"
        )
        self.box.db.commit()
        with self.assertRaises(sqlite3.Error):
            self.adapter.receive(update())
        self.assertIsNone(self.box.active())
        self.assertIsNone(self.state.offset())

    def test_same_identity_with_different_content_conflicts(self):
        self.adapter.receive(update())
        with self.assertRaises(ProtocolError):
            self.adapter.receive(update(text="Outro texto"))

    def test_reused_update_number_with_new_message_id_is_distinct(self):
        self.adapter.receive(update())
        another = update()
        another["message"]["message_id"] += 10000
        self.adapter.receive(another)
        self.assertEqual(
            self.box.db.execute("SELECT count(*) FROM conversation_outbox").fetchone()[0], 2
        )

    def test_post_timeout_replays_exact_bytes_after_restart(self):
        self.adapter.receive(update())
        self.tick()
        self.client.lose_response = True
        self.tick()
        self.assertEqual(self.box.active()["state"], "POST_UNKNOWN")
        self.now += 10
        worker = ConversationWorker(
            self.restart_box(), self.client, self.telegram, OWNER, clock=lambda: self.now
        )
        worker.tick()
        self.assertEqual(len(self.client.operations), 1)
        self.assertEqual(self.client.sent[0], self.client.sent[1])
        self.assertIsNone(self.box.active()["command"])
        self.assertIsNone(self.box.active()["body"])

    def test_accepted_operation_survives_restart_without_another_post(self):
        self.adapter.receive(update())
        self.tick(2)
        worker = ConversationWorker(
            self.restart_box(), self.client, self.telegram, OWNER, clock=lambda: self.now
        )
        worker.tick()
        worker.tick()
        self.assertEqual(len(self.client.sent), 1)
        self.assertIsNone(self.box.active())

    def test_queue_uses_latest_version_once_and_preserves_original_command_after_send(self):
        self.adapter.receive(update())
        self.adapter.receive(update(2, "Corrigindo: orçamento de 150 reais"))
        self.tick(10)
        documents = [json.loads(raw) for raw in self.client.sent]
        self.assertEqual([d["expectedVersion"] for d in documents], [0, 1])
        self.assertEqual(len(self.client.operations), 2)

    def test_unavailable_snapshot_pauses_and_resume_does_not_try_empty_command(self):
        self.adapter.receive(update())
        self.client.failure = ConversationError("UNAVAILABLE")
        for _ in range(4):
            self.tick()
            self.now += 40
        self.assertEqual(len(self.client.sent), 0)
        self.tick(2)  # Aviso técnico de pausa, separado do evento preservado.
        self.assertIsNone(self.box.next())
        self.client.failure = None
        self.adapter.receive(update(2, "/retomar"), "/retomar")
        self.tick(10)
        self.assertEqual(len(self.client.operations), 1)

    def test_three_uncertain_posts_require_explicit_resume_of_same_command(self):
        self.adapter.receive(update())
        self.tick()
        self.client.failure = ConversationError("UNAVAILABLE", uncertain=True)
        for _ in range(3):
            self.tick()
            self.now += 40
        before = list(self.client.sent)
        self.tick(3)
        self.assertEqual(self.client.sent, before)
        self.client.failure = None
        self.adapter.receive(update(2, "/retomar"), "/retomar")
        self.tick(10)
        self.assertEqual(len(self.client.operations), 1)
        self.assertTrue(all(raw == before[0] for raw in self.client.sent))

    def test_body_waiting_for_unavailable_snapshot_also_expires(self):
        self.adapter.receive(update(text="Conteúdo temporário"))
        self.client.failure = ConversationError("UNAVAILABLE")
        self.tick()
        self.now += DAY + 1
        self.box.expire()
        self.assertIsNone(self.box.active()["body"])
        self.assertEqual(self.box.active()["notice"], "EXPIRED")

    def test_stale_rejection_does_not_rewrite_or_resend_event(self):
        self.adapter.receive(update())
        self.tick()
        old = bytes(self.box.active()["command"])
        self.client.failure = ConversationError("STALE_VERSION")
        self.tick()
        self.client.failure = None
        self.tick(3)
        self.assertEqual(self.client.sent, [old])
        self.assertIsNone(self.box.active())

    def test_capacity_rejects_with_persisted_notice_and_keeps_cursor(self):
        self.box.capacity = 1
        self.adapter.receive(update())
        self.adapter.receive(update(2))
        row = self.box.db.execute(
            "SELECT * FROM conversation_outbox WHERE notice='QUEUE_FULL'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertIsNone(row["body"])
        self.assertEqual(self.state.offset(), 3)
        self.tick(2)
        self.assertIn("fila", self.telegram.send.call_args.args[1])

    def test_expiry_scrubs_unsent_body_but_not_unconfirmed_post(self):
        self.adapter.receive(update())
        self.now += DAY + 1
        self.box.expire()
        self.assertIsNone(self.box.active()["body"])
        self.assertEqual(self.box.active()["notice"], "EXPIRED")
        self.tick(2)
        self.adapter.receive(update(2))
        self.tick()
        self.client.lose_response = True
        self.tick()
        self.now += DAY + 1
        self.box.expire()
        self.assertIsNotNone(self.box.active()["command"])

    def test_scope_isolation_and_existing_login_tables_preserved(self):
        self.state.claim_action(999)
        self.state.watch_login(OWNER, "synthetic-attempt", self.now + 100)
        self.adapter.receive(update())
        other = Outbox(self.path, "other-bot")
        self.addCleanup(other.close)
        self.assertIsNone(other.active())
        self.assertIsNotNone(self.state.login_watch())
        self.assertFalse(self.state.claim_action(999))


class DeliveryTests(Fixture):
    def test_terminal_response_uses_current_snapshot_not_old_operation_content(self):
        self.adapter.receive(update())
        self.tick(2)
        self.client.current = snapshot(10, "Conteúdo neutro atual")
        self.tick(2)
        self.assertIn("Conteúdo neutro atual", self.telegram.send.call_args.args[1])
        self.assertNotIn("Resposta sintética", self.telegram.send.call_args.args[1])

    def test_reply_timeout_is_uncertain_without_repeating_api_post_or_send(self):
        self.adapter.receive(update())
        self.tick(2)
        self.telegram.send.side_effect = TelegramError()
        self.tick(5)
        self.assertEqual(self.telegram.send.call_count, 1)
        self.assertEqual(len(self.client.sent), 1)
        self.assertEqual(self.box.active()["state"], "DELIVERY_UNKNOWN")
        self.assertIsNone(self.box.active()["body"])
        self.telegram.send.side_effect = lambda *args: {"message_id": 600}
        self.adapter.receive(update(2, "/retomar"), "/retomar")
        self.tick(8)
        self.assertIsNone(self.box.active())
        self.assertEqual(len(self.client.sent), 1)

    def test_crash_during_telegram_send_is_not_automatically_retried(self):
        self.adapter.receive(update())
        self.tick(2)
        row = self.box.active()
        self.box.save(row["seq"], state="SENDING")
        other = self.restart_box()
        self.assertEqual(other.active()["state"], "DELIVERY_UNKNOWN")
        self.assertIsNone(other.next())

    def test_progress_is_edited_and_not_resent_after_restart(self):
        self.client.finish = False
        self.adapter.receive(update())
        self.tick(4)
        self.assertEqual(self.telegram.send.call_count, 1)
        self.client.finish = True
        self.tick(3)
        self.assertEqual(self.telegram.send.call_count, 1)
        self.assertIn("Resposta sintética", self.telegram.call.call_args.args[1]["text"])

    def test_multiple_chunks_recover_known_delivery_without_resending_previous_parts(self):
        self.adapter.receive(update())
        self.tick(2)
        self.client.current = snapshot(10, "😀" * 4000)
        self.tick(8)
        self.assertEqual(self.telegram.send.call_count, 3)
        for call in self.telegram.send.call_args_list:
            self.assertLessEqual(len(call.args[1].encode("utf-16-le")) // 2, 3500)
        self.assertIsNone(self.box.active())

    def test_no_snapshots_response_text_or_telegram_tokens_in_database(self):
        self.adapter.receive(update(text="Texto temporário privado"))
        self.tick(5)
        dump = " ".join(self.box.db.iterdump())
        for secret in [
            "Texto temporário privado",
            "Resposta sintética",
            CONFIG.token,
            "humanApproval",
        ]:
            self.assertNotIn(secret, dump)

    def test_rate_limit_delays_and_forbidden_finishes_local_delivery(self):
        self.adapter.receive(update())
        self.tick(2)
        self.telegram.send.side_effect = TelegramError(429, 30)
        self.tick()
        row = self.box.active()
        self.assertGreaterEqual(row["due"], self.now + 29)
        self.telegram.send.side_effect = TelegramError(403)
        self.now += 31
        self.tick()
        self.assertIsNone(self.box.active())


class ControlTests(Fixture):
    def test_plain_text_with_at_sign_is_not_mistaken_for_targeted_command(self):
        process_batch(
            self.telegram,
            self.state,
            [update(text="contato@exemplo.invalid")],
            OWNER,
            "demo",
            conversations=self.adapter,
        )
        self.assertIsNotNone(self.box.active())

    def test_stop_during_api_response_does_not_start_telegram_delivery(self):
        self.adapter.receive(update())
        self.tick(2)
        self.worker.stop_event.set()
        self.worker.tick()
        self.telegram.send.assert_not_called()

    def test_cancel_before_send_is_local_and_does_not_call_api(self):
        self.adapter.receive(update())
        self.adapter.receive(update(2, "/interromper"), "/interromper")
        self.tick(4)
        self.assertEqual(self.client.sent, [])
        self.assertIsNone(self.box.active())
        self.assertIn("Nenhum cancelamento remoto", self.telegram.send.call_args.args[1])

    def test_cancel_accepted_operation_has_own_origin_and_exact_replay(self):
        self.client.finish = False
        self.adapter.receive(update())
        self.tick(2)
        self.adapter.receive(update(2, "/interromper"), "/interromper")
        self.tick(5)
        commands = [json.loads(raw) for raw in self.client.sent]
        cancel = next(d for d in commands if "operationId" in d)
        self.assertNotEqual(cancel["eventId"], commands[0]["eventId"])
        self.assertEqual(cancel["source"]["messageId"], "102")
        self.assertIn("operation_synthetic", cancel["operationId"])

    def test_private_authorization_and_commands_do_not_enter_api_queue(self):
        denied = update()
        denied["message"]["from"]["id"] = 999
        process_batch(
            self.telegram, self.state, [denied], OWNER, "demo", conversations=self.adapter
        )
        self.assertIsNone(self.box.active())
        process_batch(
            self.telegram,
            self.state,
            [update(2, "/ajuda")],
            OWNER,
            "demo",
            conversations=self.adapter,
        )
        self.assertIsNone(self.box.active())
        self.assertIn("/retomar", self.telegram.send.call_args.args[1])
        process_batch(
            self.telegram,
            self.state,
            [update(3, "Nova mensagem")],
            OWNER,
            "demo",
            conversations=self.adapter,
        )
        self.assertIsNotNone(self.box.active())
        self.assertEqual(self.client.sent, [])

    def test_blocked_api_worker_does_not_block_ingestion_or_help(self):
        entered, release = threading.Event(), threading.Event()

        def client_factory():
            client = FakeClient()

            def slow():
                entered.set()
                release.wait(3)
                return snapshot()

            client.get_snapshot = slow
            return client

        self.adapter.receive(update())
        service = ConversationService(
            self.path, "synthetic-scope", client_factory, lambda: self.telegram, OWNER
        )
        service.start()
        try:
            self.assertTrue(entered.wait(2))
            process_batch(
                self.telegram,
                self.state,
                [update(2, "/ajuda"), update(3, "Correção")],
                OWNER,
                "demo",
                conversations=self.adapter,
            )
            self.assertEqual(self.state.offset(), 4)
            self.assertFalse(service.failed.is_set())
        finally:
            release.set()
            service.stop()

    def test_pending_checks_stop_after_deadline_and_recovery_is_explicit(self):
        self.client.finish = False
        self.adapter.receive(update())
        self.tick(2)
        self.now += 200
        self.tick()
        self.tick(2)
        self.assertIsNone(self.box.next())
        self.assertEqual(self.box.active()["state"], "PAUSED")

    def test_formatting_omits_technical_references_and_handles_emoji(self):
        value = snapshot().to_dict()
        value["humanApproval"] = {"reviewRef": "private-review", "approvalRef": "private-approval"}
        value["blocks"][0]["text"] = "**Texto** private-approval <b>literal</b>"
        text = render(Snapshot(encode(value), 0, "COLLECTING"))
        self.assertNotIn("private-approval", text)
        self.assertIn("<b>literal</b>", text)  # Sem parse_mode: texto simples.
        self.assertEqual("".join(chunks("😀" * 8000)), "😀" * 8000)
