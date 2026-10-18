"""Áudio, fornecedor e Telegram sintéticos. Nenhuma chamada paga ou polling real."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import test_conversation_worker as fixtures

from telegram_bot.conversation_contract import decode
from telegram_bot.conversation_runner import ConversationWorker
from telegram_bot.runner import START, process_batch
from telegram_bot.telegram import Telegram, TelegramError
from telegram_bot.voice import VoiceConfig, VoiceError, VoiceTranscriber


def audio_update(n=1, owner=fixtures.OWNER):
    result = fixtures.update(n)
    result["message"].pop("text")
    result["message"]["from"]["id"] = owner
    result["message"]["chat"]["id"] = owner
    result["message"]["voice"] = {"file_id": "synthetic_file", "duration": 12, "file_size": 100}
    return result


class VoicePipelineTests(fixtures.Fixture):
    def setUp(self):
        super().setUp()
        self.adapter.voice_enabled = True
        self.transcriber = Mock()
        self.transcriber.transcribe.return_value = "Ana tem alergia a amendoim. Teto de 150 reais."
        self.worker.transcriber = self.transcriber
        self.telegram.download_voice.return_value = b"OggSsynthetic"

    def test_order_identity_replay_and_no_audio_bytes_in_database(self):
        self.adapter.receive(audio_update())
        self.adapter.receive(fixtures.update(2, "Na verdade 140 reais"))
        original = self.box.active()["event_id"]
        self.tick()
        row = self.box.active()
        self.assertEqual(row["event_id"], original)
        self.assertIsNone(row["voice"])
        self.assertIn("amendoim", decode(bytes(row["body"]))["input"]["text"])
        self.adapter.receive(audio_update())
        self.tick(2)
        self.transcriber.transcribe.assert_called_once()
        self.assertNotIn("OggS", "\n".join(self.box.db.iterdump()))
        self.assertIn("Confira especialmente", self.telegram.send.call_args_list[0].args[1])

    def test_unauthorized_and_disabled_do_not_download(self):
        process_batch(
            self.telegram,
            self.state,
            [audio_update(owner=fixtures.OWNER + 1)],
            fixtures.OWNER,
            "demo",
            conversations=self.adapter,
        )
        self.assertIsNone(self.box.active())
        self.adapter.voice_enabled = False
        self.assertIn("Ainda não", self.adapter.receive(audio_update(2)))
        self.telegram.download_voice.assert_not_called()

    def test_cancel_during_transcription_does_not_resurrect_audio(self):
        self.adapter.receive(audio_update())
        seq = self.box.active()["seq"]

        def transcribe(*args):
            self.adapter.receive(fixtures.update(2, "/interromper"), "/interromper")
            return "Texto antigo"

        self.transcriber.transcribe.side_effect = transcribe
        self.tick()
        self.assertEqual(self.box.get(seq)["state"], "CANCELLED")
        self.assertIsNone(self.box.get(seq)["body"])
        self.telegram.send.assert_not_called()

    def test_restart_with_unknown_transcription_does_not_call_provider_again(self):
        self.adapter.receive(audio_update())
        self.box.save(self.box.active()["seq"], state="TRANSCRIBING")
        other = self.restart_box()
        worker = ConversationWorker(
            other, self.client, self.telegram, fixtures.OWNER, transcriber=self.transcriber
        )
        worker.tick()
        self.transcriber.transcribe.assert_not_called()
        self.assertIn("não será repetida", self.telegram.send.call_args.args[1])

    def test_logout_during_download_prevents_external_transcription(self):
        self.adapter.receive(audio_update())
        self.worker.access_allowed = Mock(side_effect=[True, False])
        self.tick()
        self.transcriber.transcribe.assert_not_called()
        self.telegram.send.assert_not_called()

    def test_voice_is_text_not_a_navigation_command(self):
        self.transcriber.transcribe.return_value = "/desconectar"
        self.adapter.receive(audio_update())
        self.tick()
        self.assertEqual(
            decode(bytes(self.box.active()["body"]))["input"],
            {"kind": "TEXT", "text": "/desconectar"},
        )

    def test_failed_transcription_and_replay_do_not_charge_again(self):
        self.transcriber.transcribe.side_effect = VoiceError()
        self.adapter.receive(audio_update())
        self.tick()
        self.adapter.receive(audio_update())
        self.tick(3)
        self.transcriber.transcribe.assert_called_once()
        self.assertEqual(self.client.sent, [])


class VoiceTransportTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "budget.sqlite3"
        self.opener = Mock()
        self.result = {
            "text": "Ana tem alergia",
            "segments": [{"no_speech_prob": 0.1, "avg_logprob": -0.2}],
        }
        self.opener.open.side_effect = lambda *a, **k: io.BytesIO(json.dumps(self.result).encode())
        self.config = VoiceConfig("synthetic-key-xxxxxxxx", 60)
        self.transcriber = VoiceTranscriber(self.config, self.path, opener=self.opener)

    def test_fixed_destination_language_and_durable_budget(self):
        self.assertEqual(self.transcriber.transcribe(b"OggSfake", 60), "Ana tem alergia")
        request = self.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.groq.com/openai/v1/audio/transcriptions")
        self.assertIn(b"whisper-large-v3-turbo", request.data)
        self.assertIn(b"\r\npt\r\n", request.data)
        restarted = VoiceTranscriber(self.config, self.path, opener=self.opener)
        with self.assertRaises(VoiceError):
            restarted.transcribe(b"OggSfake", 1)
        self.opener.open.assert_called_once()
        self.assertNotIn(self.config.key, repr(self.config))

    def test_low_confidence_empty_and_non_audio_are_rejected(self):
        for result in [
            {"text": "invenção", "segments": [{"no_speech_prob": 0.9, "avg_logprob": -2}]},
            {"text": "", "segments": []},
        ]:
            self.result = result
            with self.assertRaises(VoiceError):
                self.transcriber.transcribe(b"OggSfake", 1)
        with self.assertRaises(VoiceError):
            self.transcriber.transcribe(b"not audio", 1)

    def test_flag_requires_explicit_key_and_limit(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(VoiceConfig.from_env())
        with (
            patch.dict("os.environ", {"TELEGRAM_VOICE_ENABLED": "true"}, clear=True),
            self.assertRaises(ValueError),
        ):
            VoiceConfig.from_env()

    def test_typing_is_native_rate_limited_and_failure_does_not_crash(self):
        api = Telegram("synthetic", self.opener)
        api.call = Mock(side_effect=TelegramError(429))
        with patch("telegram_bot.telegram.time.monotonic", side_effect=[10, 11, 15]):
            api.typing(1)
            api.typing(1)
            api.typing(1)
        self.assertEqual(api.call.call_count, 2)
        api.call.assert_called_with("sendChatAction", {"chat_id": 1, "action": "typing"}, timeout=1)
        self.assertIn("Eu sou o Ailo", START)

    def test_display_name_is_ailo_and_failure_is_nonfatal(self):
        api = Telegram("synthetic", self.opener)
        api.call = Mock(side_effect=TelegramError(500))
        api.configure_name({"first_name": "Ailo"})
        api.call.assert_not_called()
        api.configure_name({"first_name": "Nome anterior"})
        api.call.assert_called_once_with("setMyName", {"name": "Ailo"}, timeout=3)

    def test_download_rejects_external_path_and_oversize(self):
        api = Telegram("synthetic", self.opener)
        api.call = Mock(return_value={"file_path": "https://attacker.test/audio"})
        with self.assertRaises(TelegramError):
            api.download_voice("id", 10)
        self.opener.open.assert_not_called()
        api.call.return_value = {"file_path": "voice/file_1.oga"}
        self.opener.open.side_effect = lambda *a, **k: io.BytesIO(b"x" * 11)
        with self.assertRaises(TelegramError):
            api.download_voice("id", 10)
        self.assertEqual(
            self.opener.open.call_args.args[0].full_url,
            "https://api.telegram.org/file/botsynthetic/voice/file_1.oga",
        )
