"""Turn app-usage intervals into minutes per local calendar day."""

from __future__ import annotations

from datetime import datetime, time, timedelta

MIN_SESSION_S = 1
MAX_SESSION_S = 12 * 3600


def merge_intervals(intervals) -> list[tuple[float, float]]:
    """Drop noise (<1 s or >12 h), then merge overlaps so nothing double-counts."""
    clean = sorted(
        (s, e) for s, e in intervals if MIN_SESSION_S <= e - s <= MAX_SESSION_S
    )
    merged: list[tuple[float, float]] = []
    for s, e in clean:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def _next_midnight(ts: float) -> float:
    day = datetime.fromtimestamp(ts).date() + timedelta(days=1)
    return datetime.combine(day, time()).timestamp()


def daily_minutes(intervals) -> dict[str, int]:
    """Minutes per local date (YYYY-MM-DD); sessions crossing midnight are split."""
    seconds: dict[str, float] = {}
    for s, e in merge_intervals(intervals):
        while s < e:
            cut = min(e, _next_midnight(s))
            key = datetime.fromtimestamp(s).date().isoformat()
            seconds[key] = seconds.get(key, 0.0) + (cut - s)
            s = cut
    return {d: round(sec / 60) for d, sec in sorted(seconds.items())}
