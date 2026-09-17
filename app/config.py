"""環境変数(.env)と config/sources.yaml を読み込む設定モジュール。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SOURCES_YAML_PATH = Path(os.getenv("SOURCES_CONFIG_PATH", BASE_DIR / "config" / "sources.yaml"))


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./data/app.db"))

    rakuten_app_id: str = field(default_factory=lambda: os.getenv("RAKUTEN_APP_ID", ""))
    rakuten_access_key: str = field(default_factory=lambda: os.getenv("RAKUTEN_ACCESS_KEY", ""))
    yahoo_app_id: str = field(default_factory=lambda: os.getenv("YAHOO_APP_ID", ""))

    line_channel_access_token: str = field(default_factory=lambda: os.getenv("LINE_CHANNEL_ACCESS_TOKEN", ""))

    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))

    app_host: str = field(default_factory=lambda: os.getenv("APP_HOST", "0.0.0.0"))
    app_port: int = field(default_factory=lambda: int(os.getenv("APP_PORT", "8000")))
    default_poll_interval_sec: int = field(
        default_factory=lambda: int(os.getenv("DEFAULT_POLL_INTERVAL_SEC", "900"))
    )

    @property
    def line_enabled(self) -> bool:
        return bool(self.line_channel_access_token)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


settings = Settings()


def load_sources_config() -> dict[str, Any]:
    """config/sources.yaml を読み込んで dict を返す。"""
    if not SOURCES_YAML_PATH.exists():
        return {"default_keywords": [], "default_exclude_keywords": [], "sources": []}
    with open(SOURCES_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("default_keywords", [])
    data.setdefault("default_exclude_keywords", [])
    data.setdefault("sources", [])
    return data
