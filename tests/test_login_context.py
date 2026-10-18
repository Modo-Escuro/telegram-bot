"""Retomada BOT-02: autenticação, vínculo e snapshot sintéticos; nenhuma compra/polling."""

from dataclasses import replace
from unittest.mock import Mock

from test_connections import ATTEMPT, CONFIRM, pending
from test_conversation_worker import OWNER, Fixture, snapshot, update

from telegram_bot.backend import BackendError, LinkStatus
from telegram_bot.connections import Connections
from telegram_bot.conversation import ConversationError
from telegram_bot.conversation_contract import Snapshot, encode
from telegram_bot.conversation_runner import ConversationWorker
from telegram_bot.outbox import DAY
from telegram_bot.runner import process_batch
from telegram_bot.telegram import TelegramError

LINK = "synthetic-link-xxxxxxxxxxxxxxxx"


def connected():
    return LinkStatus("CONNECTED", True, ("ADDRESSES_READ",), None, None, LINK)


def group():
    document = snapshot(4).to_dict()
    document["blocks"] = [
        {"kind": "TEXT", "text": "Proposta antiga: compra aprovada", "source": "MODEL"},
        {
            "kind": "GROUP",
            "participants": [
                {
                    "participantRef": "person_reference_0000",
                    "displayName": "Pessoa sintética",
                    "conditions": ["Alergia obrigatória a leite"],
                }
            ],
            "budgetCents": 12345,
        },
    ]
    document["pending"] = ["Pergunta antiga da compra anterior"]
    return Snapshot(encode(document), 4, "COLLECTING")


class LoginContextTests(Fixture):
    def setUp(self):
        super().setUp()
        self.status = Mock(return_value=connected())
        self.client.current = group()
        self.worker.link_status = self.status
        self.backend = Mock()
        self.backend.status.return_value = pending()
        self.backend.confirm.return_value = connected()
        self.backend.verify.return_value = connected()
        self.connections = Connections(self.backend, self.state, OWNER, conversations=self.adapter)

    def rows(self):
        return self.box.db.execute(
            "SELECT * FROM conversation_outbox WHERE kind='CONTEXT'"
        ).fetchall()

    def enqueue(self, source="synthetic-confirm-1"):
        self.assertTrue(self.adapter.restore_after_login(connected(), source))

    def test_human_confirmation_queues_followup_before_delivery(self):
        reply = self.connections.confirm_click(CONFIRM, 1)
        self.backend.confirm.assert_called_once_with(CONFIRM)
        self.assertIn("Vou recuperar o grupo", reply.text)
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.client.sent, [])
        self.telegram.send.assert_not_called()

    def test_callback_redelivery_after_send_failure_recovers_without_confirming_twice(self):
        callback = {
            "update_id": 1,
            "callback_query": {
                "id": "synthetic-callback",
                "from": {"id": OWNER, "is_bot": False},
                "message": {"message_id": 51, "chat": {"id": OWNER, "type": "private"}},
                "data": "ifc:" + CONFIRM,
            },
        }
        self.telegram.send.side_effect = TelegramError()
        with self.assertRaises(TelegramError):
            process_batch(
                self.telegram, self.state, [callback], OWNER, "bot", self.connections, self.adapter
            )
        self.backend.status.return_value = connected()
        self.telegram.send.side_effect = lambda *args: {"message_id": 52}
        process_batch(
            self.telegram, self.state, [callback], OWNER, "bot", self.connections, self.adapter
        )
        self.backend.confirm.assert_called_once()
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.state.offset(), 2)

    def test_authorized_but_not_confirmed_never_queues_context(self):
        self.connections._present(pending(), resume_key="not-confirmed")
        self.connections._present(replace(connected(), operational=False), resume_key="unverified")
        self.connections._present(
            replace(connected(), allowed_operations=()), resume_key="no-scope"
        )
        self.assertEqual(self.rows(), [])
        self.backend.confirm.assert_not_called()

    def test_old_or_unauthorized_callback_cannot_schedule_followup(self):
        self.connections.confirm_click("old-confirmation-xxxxxxxxx", 1)
        other = OWNER + 1
        callback = {
            "update_id": 2,
            "callback_query": {
                "id": "foreign-callback",
                "from": {"id": other, "is_bot": False},
                "message": {"message_id": 51, "chat": {"id": other, "type": "private"}},
                "data": "ifc:" + CONFIRM,
            },
        }
        process_batch(
            self.telegram, self.state, [callback], OWNER, "bot", self.connections, self.adapter
        )
        self.assertEqual(self.rows(), [])
        self.backend.confirm.assert_not_called()

    def test_verify_replay_only_queries_status_and_recovers_same_followup(self):
        first = self.connections.reply("/verificar", [], 1)
        self.backend.status.return_value = connected()
        second = self.connections.reply("/verificar", [], 1)
        self.assertIn("Vou recuperar o grupo", first.text)
        self.assertIn("Vou recuperar o grupo", second.text)
        self.backend.verify.assert_called_once()
        self.assertEqual(len(self.rows()), 1)

    def test_legacy_login_without_conversation_feature_is_unchanged(self):
        legacy = Connections(self.backend, self.state, OWNER)
        self.assertNotIn("Vou recuperar o grupo", legacy.confirm_click(CONFIRM, 1).text)
        self.assertEqual(self.rows(), [])

    def test_restoration_after_reopening_sqlite_reads_only_current_group(self):
        self.enqueue()
        recovered = self.restart_box()
        self.worker = ConversationWorker(
            recovered,
            self.client,
            self.telegram,
            OWNER,
            clock=lambda: self.now,
            link_status=self.status,
        )
        self.tick(2)
        text = self.telegram.send.call_args.args[1]
        self.assertIn("Pessoa sintética", text)
        self.assertIn("leite", text)
        self.assertIn("R$ 123,45", text)
        self.assertNotIn("compra aprovada", text)
        self.assertNotIn("Pergunta antiga", text)
        self.assertEqual(self.client.sent, [])
        self.assertEqual(self.rows()[0]["state"], "DONE")

    def test_link_change_before_read_does_not_fetch_or_display_old_context(self):
        self.enqueue()
        self.status.return_value = replace(connected(), link_id="different-link-xxxxxxxxxx")
        self.client.get_snapshot = Mock(side_effect=AssertionError("must not read"))
        self.tick(3)
        self.assertNotIn("Pessoa sintética", self.telegram.send.call_args.args[1])
        self.assertIn("vínculo", self.telegram.send.call_args.args[1])
        self.assertEqual(self.client.sent, [])

    def test_link_change_during_snapshot_read_prevents_presentation(self):
        self.enqueue()
        self.status.side_effect = [
            connected(),
            replace(connected(), link_id="another-link-xxxxxxxxxxxx"),
        ]
        self.tick(3)
        self.assertNotIn("Pessoa sintética", self.telegram.send.call_args.args[1])
        self.assertEqual(self.client.sent, [])

    def test_unavailable_link_retries_with_bound_without_logout_or_confirmation(self):
        self.enqueue()
        self.status.side_effect = BackendError()
        for _ in range(3):
            self.tick()
            self.now += 40
        self.tick(2)
        self.assertEqual(self.rows()[0]["attempts"], 3)
        self.backend.disconnect.assert_not_called()
        self.backend.confirm.assert_not_called()
        self.status.side_effect = None
        self.adapter.receive(update(2, "/retomar"), "/retomar")
        self.tick(6)
        self.assertEqual(self.rows()[0]["state"], "DONE")
        self.assertEqual(self.client.sent, [])

    def test_delivery_timeout_does_not_repeat_snapshot_message_until_explicit_resume(self):
        self.enqueue()
        self.telegram.send.side_effect = TelegramError()
        self.tick(3)
        self.assertEqual(self.telegram.send.call_count, 1)
        self.assertEqual(self.rows()[0]["state"], "DELIVERY_UNKNOWN")
        self.telegram.send.side_effect = lambda *args: {"message_id": 55}
        self.adapter.receive(update(2, "/retomar"), "/retomar")
        self.tick(6)
        self.assertEqual(self.rows()[0]["state"], "DONE")
        self.assertEqual(self.client.sent, [])

    def test_rate_limit_retries_and_403_finishes_delivery(self):
        self.enqueue()
        self.telegram.send.side_effect = TelegramError(code=429, retry_after=25)
        self.tick(2)
        self.assertEqual(self.telegram.send.call_count, 1)
        self.now += 30
        self.telegram.send.side_effect = TelegramError(code=403)
        self.tick()
        self.assertEqual(self.rows()[0]["state"], "DONE")

    def test_missing_snapshot_produces_guidance_without_creating_conversation(self):
        self.enqueue()
        self.client.failure = ConversationError("NOT_FOUND")
        self.tick(3)
        self.assertIn("Não há conversa salva", self.telegram.send.call_args.args[1])
        self.assertEqual(self.client.sent, [])

    def test_full_queue_explains_rejected_restore_without_discarding_text(self):
        self.box.capacity = 1
        self.adapter.receive(update())
        reply = self.connections.confirm_click(CONFIRM, 2)
        self.assertIn("fila está cheia", reply.text)
        self.assertEqual(self.rows(), [])
        self.assertIsNotNone(self.box.active()["body"])

    def test_restore_metadata_has_no_link_identity_snapshot_or_confirmation(self):
        self.enqueue()
        self.tick(2)
        dump = "\n".join(self.box.db.iterdump())
        for private in (
            LINK,
            CONFIRM,
            "Pessoa sintética",
            "leite",
            "Proposta antiga",
            "m***@example.com",
        ):
            self.assertNotIn(private, dump)

    def test_same_restore_key_never_changes_account_on_replay(self):
        self.enqueue()
        self.assertFalse(
            self.adapter.restore_after_login(
                replace(connected(), link_id="changed-link-xxxxxxxxxxxx"), "synthetic-confirm-1"
            )
        )
        self.assertEqual(len(self.rows()), 1)

    def test_expired_followup_has_no_snapshot_and_requires_new_verification(self):
        self.enqueue()
        self.now += DAY + 1
        self.tick(2)
        self.assertIn("expirou", self.telegram.send.call_args.args[1])
        self.status.assert_not_called()
        self.assertEqual(self.client.sent, [])

    def test_expunged_snapshot_before_first_send_cannot_restore_old_group(self):
        self.enqueue()
        self.client.current = snapshot(5, "Estado neutro após expurgo")
        self.tick(2)
        self.assertNotIn("Pessoa sintética", self.telegram.send.call_args.args[1])
        self.assertIn("Não há grupo salvo", self.telegram.send.call_args.args[1])

    def test_recovered_login_watch_only_restores_server_confirmed_operational_link(self):
        self.state.watch_login(OWNER, ATTEMPT, self.now + 600)
        self.state.login_message(ATTEMPT, 51, "AWAITING_CONFIRMATION")
        self.backend.status.return_value = connected()
        self.connections.tick(self.telegram, OWNER)
        self.assertEqual(len(self.rows()), 1)
        self.assertIsNone(self.state.login_watch())
        self.backend.confirm.assert_not_called()

    def test_disconnect_and_cancel_do_not_resume_group(self):
        self.backend.cancel.return_value = connected(), True
        self.backend.disconnect.return_value = (
            replace(
                connected(),
                state="DISCONNECTED",
                operational=False,
                allowed_operations=(),
                link_id=None,
            ),
            True,
        )
        self.connections.reply("/cancelar", [], 1)
        self.connections.reply("/desconectar", [], 2)
        self.assertEqual(self.rows(), [])

    def test_additive_migration_preserves_pending_text_and_cursor(self):
        self.adapter.receive(update())
        original = bytes(self.box.active()["body"])
        # Emula o schema da BOT-01 anterior a este incremento, com evento já recebido.
        self.box.db.execute("ALTER TABLE conversation_outbox DROP COLUMN link_hash")
        self.box.db.commit()
        recovered = self.restart_box()
        self.assertEqual(bytes(recovered.active()["body"]), original)
        self.assertEqual(self.state.offset(), 2)
        self.assertIn("link_hash", recovered.active().keys())

    def test_shutdown_during_link_check_does_not_start_another_request(self):
        self.enqueue()
        self.client.get_snapshot = Mock(side_effect=AssertionError("must not read"))

        def stopping():
            self.worker.stop_event.set()
            return connected()

        self.status.side_effect = stopping
        self.tick()
        self.telegram.send.assert_not_called()
        self.assertEqual(self.rows()[0]["state"], "CONTEXT")

    def test_unavailable_status_is_not_announced_as_account_change(self):
        self.enqueue()
        self.status.return_value = replace(connected(), state="UNAVAILABLE", operational=False)
        self.tick()
        self.assertEqual(self.rows()[0]["state"], "PAUSED")
        self.telegram.send.assert_not_called()

    def test_lost_confirmation_reply_is_recovered_by_watch_without_repeating_confirm(self):
        self.state.watch_login(OWNER, ATTEMPT, self.now + 600)
        self.state.login_message(ATTEMPT, 51, "AWAITING_CONFIRMATION")
        self.backend.confirm.side_effect = BackendError(uncertain=True)
        reply = self.connections.confirm_click(CONFIRM, 1)
        self.assertIn("Não a repetirei", reply.text)
        self.backend.status.return_value = connected()
        self.connections.tick(self.telegram, OWNER)
        self.assertEqual(len(self.rows()), 1)
        self.backend.confirm.assert_called_once()

    def test_link_is_checked_again_before_sending_each_part(self):
        document = group().to_dict()
        document["blocks"] = [
            {
                "kind": "GROUP",
                "participants": [
                    {
                        "participantRef": f"person_reference_{n:04d}",
                        "displayName": f"Pessoa {n}",
                        "conditions": ["Condição informada " + "x" * 250],
                    }
                    for n in range(15)
                ],
                "budgetCents": 12345,
            }
        ]
        self.client.current = Snapshot(encode(document), 4, "COLLECTING")
        self.enqueue()
        self.tick()
        self.assertEqual(self.telegram.send.call_count, 1)
        self.status.return_value = replace(connected(), link_id="changed-link-xxxxxxxxxxxx")
        self.tick(3)
        self.assertEqual(self.telegram.send.call_count, 1)
        self.assertIn("validar o mesmo vínculo", self.telegram.call.call_args.args[1]["text"])
        self.assertEqual(self.client.sent, [])

    def test_watch_reports_full_queue_with_manual_fallback(self):
        self.box.capacity = 0
        self.state.watch_login(OWNER, ATTEMPT, self.now + 600)
        self.state.login_message(ATTEMPT, 51, "AWAITING_CONFIRMATION")
        self.backend.status.return_value = connected()
        self.connections.tick(self.telegram, OWNER)
        self.assertIn("fila está cheia", self.telegram.call.call_args.args[1]["text"])
        self.assertIn("/verificar", self.telegram.call.call_args.args[1]["text"])
        self.assertEqual(self.rows(), [])
