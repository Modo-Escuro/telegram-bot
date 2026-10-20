"""Prévia social opcional: não cria outro turno nem persiste texto da API."""

import json
import unittest

import test_conversation as transport
from test_conversation_worker import Fixture, update

from telegram_bot.conversation import ConversationError


class ProgressTransportTests(unittest.TestCase):
    client = transport.ConversationTests.client

    def test_progress_is_scoped_to_operation_and_event(self):
        body = {
            "contractVersion": "1.0",
            "enabled": True,
            "operationId": "operation_synthetic_0000",
            "eventId": "tg-event-1",
            "text": "Que lindo! Que tal um bolo acompanhado de uma flor?",
        }
        client, opener = self.client(body, status=200)
        text = client.get_progress(body["operationId"], event_id=body["eventId"])
        self.assertIn("Que lindo", text)
        self.assertTrue(opener.open.call_args.args[0].full_url.endswith("/progress"))
        opener.open.return_value = transport.Response({**body, "eventId": "another-event"}, 200)
        with self.assertRaises(ConversationError):
            client.get_progress(body["operationId"], event_id=body["eventId"])

    def test_old_api_disables_only_optional_progress(self):
        client, opener = self.client({}, status=404)
        self.assertIsNone(client.get_progress("operation_synthetic_0000", event_id="tg-event-1"))
        self.assertIsNone(client.get_progress("operation_synthetic_0000", event_id="tg-event-1"))
        self.assertEqual(opener.open.call_count, 1)


class ProgressDeliveryTests(Fixture):
    def test_preview_is_sent_once_and_final_result_edits_the_same_message(self):
        self.client.finish = False
        self.client.get_progress = lambda *args, **kwargs: "Que lindo! Vou buscar algumas opções."
        self.adapter.receive(update(text="Quero um bolo para minha namorada"))
        self.tick(4)
        self.assertEqual(self.telegram.send.call_count, 1)
        self.assertIn("Que lindo", self.telegram.send.call_args.args[1])
        self.assertEqual(len(self.client.sent), 1)
        self.assertNotIn("Que lindo", "\n".join(self.box.db.iterdump()))
        self.client.finish = True
        self.tick(4)
        self.assertIsNone(self.box.active())
        self.assertEqual(self.telegram.send.call_count, 1)
        self.assertTrue(
            any(c.args[0] == "editMessageText" for c in self.telegram.call.call_args_list)
        )
        self.assertEqual(len(self.client.sent), 1)

    def test_optional_progress_failure_does_not_pause_the_final_result(self):
        def failed(*args, **kwargs):
            raise ConversationError("UNAVAILABLE")

        self.client.get_progress = failed
        self.client.finish = False
        self.adapter.receive(update())
        self.tick(3)
        self.client.finish = True
        self.tick(4)
        self.assertIsNone(self.box.active())
        self.assertEqual(len(self.client.sent), 1)
        self.assertEqual(json.loads(self.client.sent[0])["input"]["kind"], "TEXT")
