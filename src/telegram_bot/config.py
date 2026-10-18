import os
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    token: str = field(repr=False)
    allowed_user_id: int | None = None
    state_dir: Path = Path("data")
    conversation_enabled: bool = False

    @classmethod
    def from_env(cls, *, identify: bool = False):
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not re.fullmatch(r"[1-9][0-9]*:[A-Za-z0-9_-]{20,}", token):
            raise ValueError("Configure TELEGRAM_BOT_TOKEN com o token do BotFather.")
        raw_id = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
        conversation = os.getenv("TELEGRAM_CONVERSATION_ENABLED", "false")
        if conversation not in {"true", "false"}:
            raise ValueError("TELEGRAM_CONVERSATION_ENABLED deve ser true ou false.")
        if not identify and not re.fullmatch(r"[1-9][0-9]*", raw_id):
            raise ValueError("Configure TELEGRAM_ALLOWED_USER_ID com seu ID numérico positivo.")
        return cls(
            token=token,
            allowed_user_id=None if identify else int(raw_id),
            state_dir=Path(os.getenv("TELEGRAM_STATE_DIR", "data")),
            conversation_enabled=conversation == "true",
        )
