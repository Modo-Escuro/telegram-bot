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
    access_password: str = field(default="", repr=False)
    access_max_users: int = 100

    @classmethod
    def from_env(cls, *, identify: bool = False):
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not re.fullmatch(r"[1-9][0-9]*:[A-Za-z0-9_-]{20,}", token):
            raise ValueError("Configure TELEGRAM_BOT_TOKEN com o token do BotFather.")
        raw_id = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
        password = os.getenv("TELEGRAM_ACCESS_PASSWORD", "")
        if password and not re.fullmatch(r"[!-~]{6,80}", password):
            raise ValueError("TELEGRAM_ACCESS_PASSWORD deve ter 6 a 80 caracteres sem espaços.")
        limit = os.getenv("TELEGRAM_ACCESS_MAX_USERS", "100")
        if not limit.isdigit() or not 1 <= int(limit) <= 200:
            raise ValueError("TELEGRAM_ACCESS_MAX_USERS deve estar entre 1 e 200.")
        if raw_id and not re.fullmatch(r"[1-9][0-9]*", raw_id):
            raise ValueError("TELEGRAM_ALLOWED_USER_ID inválido.")
        conversation = os.getenv("TELEGRAM_CONVERSATION_ENABLED", "false")
        if conversation not in {"true", "false"}:
            raise ValueError("TELEGRAM_CONVERSATION_ENABLED deve ser true ou false.")
        if not identify and not password and not raw_id:
            raise ValueError("Configure TELEGRAM_ALLOWED_USER_ID com seu ID numérico positivo.")
        return cls(
            token=token,
            allowed_user_id=None if identify or not raw_id else int(raw_id),
            state_dir=Path(os.getenv("TELEGRAM_STATE_DIR", "data")),
            conversation_enabled=conversation == "true",
            access_password=password,
            access_max_users=int(limit),
        )
