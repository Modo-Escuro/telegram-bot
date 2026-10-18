"""Sessão original da mensagem permanece após replay e reinício; backend falso."""

from unittest.mock import Mock

from test_conversation_worker import Fixture, snapshot, update

from telegram_bot.conversation import ConversationError
from telegram_bot.conversation_runner import Conversations, ConversationWorker


class AccountSessions(Fixture):
    def test_restart_and_replay_keep_original_session_and_never_send_to_b(self):
        self.client.account_context = Mock(return_value="a" * 64)
        self.adapter.receive(update())
        self.client.account_context.return_value = "b" * 64
        reopened = self.restart_box()
        Conversations(reopened, self.client).receive(update())
        self.client.account_context.assert_called_once()
        self.assertEqual(reopened.active()["account_session"], "a" * 64)
        self.client.get_snapshot = Mock(side_effect=ConversationError("LINK_CHANGED"))
        worker = ConversationWorker(
            reopened, self.client, self.telegram, 111111111, clock=lambda: self.now
        )
        worker.tick()
        self.client.get_snapshot.assert_called_once_with(session_ref="a" * 64)
        self.assertEqual(self.client.sent, [])
        self.assertEqual(reopened.active()["notice"], "LINK_CHANGED")

    def test_version_send_and_poll_use_same_session(self):
        self.client.account_context = Mock(return_value="a" * 64)
        self.client.get_snapshot = Mock(return_value=snapshot())
        original_send, original_poll = self.client.send, self.client.get_operation
        self.client.send = Mock(side_effect=lambda command, **kw: original_send(command))
        self.client.get_operation = Mock(
            side_effect=lambda op, event_id, **kw: original_poll(op, event_id=event_id)
        )
        self.adapter.receive(update())
        self.tick(4)
        self.assertEqual(self.client.send.call_args.kwargs, {"session_ref": "a" * 64})
        self.assertEqual(self.client.get_operation.call_args.kwargs["session_ref"], "a" * 64)
        self.client.get_snapshot.assert_called_with(session_ref="a" * 64)

    def test_identity_unavailable_does_not_queue_unbound_message(self):
        self.client.account_context = Mock(side_effect=ConversationError("UNAVAILABLE"))
        self.assertIn("confirmar a conta", self.adapter.receive(update()))
        self.assertIsNone(self.box.active())
