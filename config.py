"""Loads config.json (falls back to sensible defaults)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
DEFAULT_LIMIT = 240


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    name: str = "Me"
    friend: str | None = None
    limit_minutes: int = DEFAULT_LIMIT
    friend_limit_minutes: int | None = None
    share_repo: str | None = None
    iphone_device_id: str | None = None
    source: str = "auto"  # auto | iphone | mac

    @property
    def friend_limit(self) -> int:
        return self.friend_limit_minutes or self.limit_minutes


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "me"


def _limit(value, key: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 1440:
        raise ConfigError(f"config.json: {key} must be minutes between 1 and 1440")
    return value


def load(path: Path = CONFIG_PATH) -> Config:
    if not path.exists():
        return Config()
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config.json is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("config.json must be a JSON object")
    source = raw.get("source", "auto")
    if source not in ("auto", "iphone", "mac"):
        raise ConfigError("config.json: source must be auto, iphone or mac")
    return Config(
        name=str(raw.get("name") or "Me"),
        friend=str(raw["friend"]) if raw.get("friend") else None,
        limit_minutes=_limit(raw.get("limit_minutes", DEFAULT_LIMIT), "limit_minutes"),
        friend_limit_minutes=_limit(raw.get("friend_limit_minutes"), "friend_limit_minutes"),
        share_repo=raw.get("share_repo") or None,
        iphone_device_id=raw.get("iphone_device_id") or None,
        source=source,
    )
