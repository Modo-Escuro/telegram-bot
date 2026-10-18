"""Transcrição opt-in: áudio só em memória, transporte sem logs e reserva diária durável."""

import json
import os
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from .telegram import NoRedirect

MAX_BYTES = 5 * 1024 * 1024
MAX_SECONDS = 60


class VoiceError(Exception):
    def __init__(self):
        super().__init__(
            "Não consegui entender este áudio com segurança. Tente um áudio curto e claro ou escreva a mensagem."
        )


@dataclass(frozen=True)
class VoiceConfig:
    key: str = field(repr=False)
    daily_seconds: int

    @classmethod
    def from_env(cls):
        enabled = os.getenv("TELEGRAM_VOICE_ENABLED", "false")
        if enabled not in {"true", "false"}:
            raise ValueError("TELEGRAM_VOICE_ENABLED deve ser true ou false.")
        if enabled == "false":
            return None
        key = os.getenv("GROQ_API_KEY", "")
        limit = os.getenv("TELEGRAM_VOICE_DAILY_SECONDS", "")
        if (
            not re.fullmatch(r"[!-~]{20,200}", key)
            or not limit.isdigit()
            or not 60 <= int(limit) <= 36000
        ):
            raise ValueError(
                "Voz requer GROQ_API_KEY e TELEGRAM_VOICE_DAILY_SECONDS entre 60 e 36000."
            )
        return cls(key, int(limit))


def voice_metadata(message):
    voice = message.get("voice")
    if not isinstance(voice, dict):
        raise VoiceError()
    file_id, duration, size = voice.get("file_id"), voice.get("duration"), voice.get("file_size")
    if not isinstance(file_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,512}", file_id):
        raise VoiceError()
    if type(duration) is not int or not 1 <= duration <= MAX_SECONDS:
        raise VoiceError()
    if size is not None and (type(size) is not int or not 0 < size <= MAX_BYTES):
        raise VoiceError()
    return {"file_id": file_id, "duration": duration}


class VoiceTranscriber:
    def __init__(self, config, budget_path, *, opener=None, clock=time.time):
        self.config, self.path, self.clock = config, budget_path, clock
        self.opener = opener or build_opener(NoRedirect())

    def reserve(self, duration):
        day = int(self.clock() // 86400)
        self.path.touch(mode=0o600, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.execute(
                "CREATE TABLE IF NOT EXISTS voice_usage(day INTEGER PRIMARY KEY, seconds INTEGER NOT NULL)"
            )
            db.commit()
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM voice_usage WHERE day<?", (day - 7,))
            row = db.execute("SELECT seconds FROM voice_usage WHERE day=?", (day,)).fetchone()
            seconds = max(10, duration)
            if (row[0] if row else 0) + seconds > self.config.daily_seconds:
                raise VoiceError()
            db.execute(
                "INSERT INTO voice_usage VALUES (?,?) ON CONFLICT(day) DO UPDATE SET seconds=seconds+excluded.seconds",
                (day, seconds),
            )
            db.commit()
        finally:
            db.close()

    def transcribe(self, audio, duration):
        if (
            not audio.startswith(b"OggS")
            or len(audio) > MAX_BYTES
            or not 1 <= duration <= MAX_SECONDS
        ):
            raise VoiceError()
        self.reserve(duration)
        boundary = "ailo-" + secrets.token_hex(16)
        parts = []
        for name, value in {
            "model": "whisper-large-v3-turbo",
            "language": "pt",
            "response_format": "verbose_json",
            "temperature": "0",
        }.items():
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
            )
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="voice.ogg"\r\nContent-Type: audio/ogg\r\n\r\n'.encode()
            + audio
            + b"\r\n"
        )
        parts.append(f"--{boundary}--\r\n".encode())
        request = Request(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            data=b"".join(parts),
            headers={
                "Authorization": "Bearer " + self.config.key,
                "Content-Type": "multipart/form-data; boundary=" + boundary,
            },
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=8) as response:
                raw = response.read(65537)
            if len(raw) > 65536:
                raise VoiceError()
            result = json.loads(raw)
            text, segments = result.get("text"), result.get("segments")
            if (
                not isinstance(text, str)
                or not 1 <= len(text.strip()) <= 4000
                or not isinstance(segments, list)
                or not segments
            ):
                raise VoiceError()
            for segment in segments:
                probability = segment.get("no_speech_prob")
                logprob = segment.get("avg_logprob")
                if (
                    type(probability) not in (int, float)
                    or type(logprob) not in (int, float)
                    or not 0 <= probability < 0.6
                    or not -1 <= logprob <= 0
                ):
                    raise VoiceError()
            return text.strip()
        except HTTPError as exc:
            exc.close()
            raise VoiceError() from None
        except (URLError, OSError, HTTPException, ValueError, AttributeError, TypeError):
            raise VoiceError() from None
