"""data/<name>.json: {"YYYY-MM-DD": minutes}. Validates anything it reads."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from config import APP_DIR, slug

DATA_DIR = APP_DIR / "data"
STATE_DIR = APP_DIR / ".island"
MANUAL_PATH = STATE_DIR / "manual.json"


def validate_days(raw) -> tuple[dict[str, int], int]:
    """Keep only valid {ISO date: 0..1440} entries. Returns (days, skipped)."""
    if not isinstance(raw, dict):
        return {}, 1
    good, skipped = {}, 0
    for k, v in raw.items():
        try:
            date.fromisoformat(k)
            ok = len(k) == 10 and not isinstance(v, bool) and isinstance(v, (int, float)) and 0 <= v <= 1440
        except (TypeError, ValueError):
            ok = False
        if ok:
            good[k] = round(v)
        else:
            skipped += 1
    return dict(sorted(good.items())), skipped


def read_days(path: Path) -> tuple[dict[str, int], int]:
    if not path.exists():
        return {}, 0
    try:
        return validate_days(json.loads(path.read_text()))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}, 1


def write_days(path: Path, days: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(dict(sorted(days.items())), indent=1) + "\n")
    tmp.replace(path)


def my_path(name: str) -> Path:
    return DATA_DIR / f"{slug(name)}.json"
