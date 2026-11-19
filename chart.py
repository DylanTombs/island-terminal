"""14-day screen-time bar chart: paired block bars, red where a bar crosses the limit."""

from __future__ import annotations

import math
from datetime import date, timedelta

import colors as c

DAYS = 14
GROUP_W = 5  # per day: 2 + 2 bar columns (or 3 solo) and a gap
MAX_ROWS = 10
EIGHTHS = " ▁▂▃▄▅▆▇█"
AXIS = 5  # " 6h ┤"

ME_RGB, FRIEND_RGB = (120, 200, 90), (100, 170, 235)
OVER_RGB, LIMIT_RGB = (235, 80, 70), (232, 190, 80)


def rgb(color: tuple[int, int, int]) -> str:
    return f"38;2;{color[0]};{color[1]};{color[2]}"


def fmt_hm(minutes: float) -> str:
    m = round(minutes)
    if m < 60:
        return f"{m}m"
    return f"{m // 60}h" if m % 60 == 0 else f"{m // 60}h {m % 60:02d}m"


def _avg(days: dict, dates: list[date]) -> float | None:
    vals = [days[d.isoformat()] for d in dates if d.isoformat() in days]
    return sum(vals) / len(vals) if vals else None


def summary(days: dict, today: date, limit: int | None = None) -> str:
    this = [today - timedelta(days=i) for i in range(7)]
    prev = [today - timedelta(days=i) for i in range(7, 14)]
    a, b = _avg(days, prev), _avg(days, this)
    if a is None or b is None:
        return "not enough history yet for a week-on-week comparison"
    pct = round((b - a) / a * 100) if a else 0
    sign = "−" if pct < 0 else "+"
    text = f"this week {fmt_hm(a)} → {fmt_hm(b)} a day ({sign}{abs(pct)}%)"
    if limit is not None:
        over = sum(1 for d in this if days.get(d.isoformat(), 0) > limit)
        text += f" · over {over}/7 days"
    return text


def _scale(values: list[float], limit: int) -> tuple[int, int]:
    """(rows, minutes per row): whole hours per row, at most MAX_ROWS rows."""
    peak_h = math.ceil(max(max(values, default=0), limit + 30) / 60)
    step_h = math.ceil(peak_h / MAX_ROWS)
    return math.ceil(peak_h / step_h), step_h * 60


def _cell(minutes, lo: int, hi: int, limit: int, color, on: bool) -> str | None:
    """One bar cell covering [lo, hi) minutes, or None if the bar doesn't reach it."""
    if minutes is None or minutes <= lo:
        return None
    eighth = 8 if minutes >= hi else round((minutes - lo) / (hi - lo) * 8)
    if eighth == 0:
        return None
    over = minutes > limit and hi > limit
    return c.paint(EIGHTHS[eighth], rgb(OVER_RGB if over else color), on)


def _columns(mine: dict, friend: dict | None, d: date, limits: tuple[int, int]) -> list[tuple]:
    """(minutes, colour, that person's limit) per bar column for one day."""
    key = d.isoformat()
    me = (mine.get(key), ME_RGB, limits[0])
    gap = (None, None, None)
    if friend is None:
        return [me] * 3 + [gap] * 2
    return [me] * 2 + [(friend.get(key), FRIEND_RGB, limits[1])] * 2 + [gap]


def _row(cols, lo, hi, limit, label, on) -> str:
    on_limit = lo < limit <= hi
    tick = "┼" if on_limit else "┤"
    out = [c.paint(f"{label:>3} {tick}", c.DIM, on)]
    for minutes, color, own_limit in cols:
        cell = _cell(minutes, lo, hi, own_limit, color, on)
        if cell:
            out.append(cell)
        else:
            out.append(c.paint("╌", rgb(LIMIT_RGB), on) if on_limit else " ")
    return "".join(out)


def render_chart(mine: dict, limit: int, today: date, on: bool,
                 friend: dict | None = None, names=("me", "friend"),
                 friend_limit: int | None = None) -> list[str]:
    dates = [today - timedelta(days=DAYS - 1 - i) for i in range(DAYS)]
    values = [v for src in (mine, friend or {}) for d in dates
              if (v := src.get(d.isoformat())) is not None]
    rows, per_row = _scale(values, limit)
    limits = (limit, friend_limit if friend_limit is not None else limit)
    cols = [col for d in dates for col in _columns(mine, friend, d, limits)]
    lines = [c.paint("  screen time · last 14 days", c.BOLD, on)]
    for r in range(rows, 0, -1):
        hours = r * per_row // 60
        label = f"{hours}h" if rows <= 8 or r % 2 == 0 else ""
        lines.append(_row(cols, (r - 1) * per_row, r * per_row, limit, label, on))
    lines.append(c.paint("    └" + "─" * (DAYS * GROUP_W), c.DIM, on))
    lines.extend(_day_labels(dates, today, on))
    lines.append("")
    lines.append(_legend(names, friend is not None, limit, on))
    lines.extend(_summaries(mine, friend, names, limits, today, on))
    return lines


def _day_labels(dates: list[date], today: date, on: bool) -> list[str]:
    def label(d: date, text: str) -> str:
        cell = f"{text:<{GROUP_W}}"
        return c.paint(cell, c.BOLD, on) if d == today else c.paint(cell, c.DIM, on)
    letters = "".join(label(d, "MTWTFSS"[d.weekday()]) for d in dates)
    nums = "".join(label(d, str(d.day)) for d in dates)
    return ["     " + letters, "     " + nums]


def _legend(names, has_friend: bool, limit: int, on: bool) -> str:
    parts = [c.paint("██", rgb(ME_RGB), on) + f" {names[0]}"]
    if has_friend:
        parts.append(c.paint("██", rgb(FRIEND_RGB), on) + f" {names[1]}")
    parts.append(c.paint("██", rgb(OVER_RGB), on) + " over limit")
    parts.append(c.paint("╌╌", rgb(LIMIT_RGB), on) + f" limit {fmt_hm(limit)}")
    return "  " + "   ".join(parts)


def _summaries(mine, friend, names, limits, today, on) -> list[str]:
    people = [(names[0], mine, ME_RGB, limits[0])]
    if friend is not None:
        people.append((names[1], friend, FRIEND_RGB, limits[1]))
    width = max(len(p[0]) for p in people)
    return ["  " + c.paint(f"{n:<{width}}", rgb(color), on) + "  " + summary(days, today, lim)
            for n, days, color, lim in people]
