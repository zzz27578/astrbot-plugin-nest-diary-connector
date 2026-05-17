from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    admin_password: str
    bot_api_token: str
    host: str
    port: int
    enable_self_update: bool


def load_settings() -> Settings:
    return Settings(
        data_dir=Path(os.getenv("NEST_DATA_DIR", "/app/data")),
        admin_password=os.getenv("NEST_ADMIN_PASSWORD", ""),
        bot_api_token=os.getenv("NEST_BOT_API_TOKEN", ""),
        host=os.getenv("NEST_HOST", "0.0.0.0"),
        port=int(os.getenv("NEST_PORT", "28080")),
        enable_self_update=os.getenv("NEST_ENABLE_SELF_UPDATE", "false").lower() in {"1", "true", "yes", "on"},
    )
