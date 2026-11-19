"""Bridges the farm rules to the TrueColor pixel-art scene in pixelfarm.py."""

from __future__ import annotations

from datetime import date, timedelta

import farm as farm_rules
import pixelfarm
import scenes

# Scene width in pixels (= terminal columns) per size, plus a 1-column border each side.
SIZES = {"small": 80, "full": pixelfarm.W}
DEFAULT_SIZE = "full"
STALE_DAYS = 3
WEEK = 7
OVERGROWN_RUN = 3  # over this many days running
FADE_STEPS = (0.25, 0.5, 0.75, 1.0)
_SHORT = {
    "thriving": "THRIVING (PEAK HARVEST)", "drought": "SEVERE DROUGHT (PARCHED)",
    "overgrown": "OVERGROWN (ABANDONED)", "winter": "DEEP WINTER (FROZEN)",
}


def panel_width(size: str = DEFAULT_SIZE) -> int:
    return SIZES[size] + 2


def personal_over(days: dict, limit: int, today: date) -> tuple[bool, ...]:
    """Oldest-first over/under flags for this person's last WEEK days that have data."""
    keys = [(today - timedelta(days=i)).isoformat() for i in range(WEEK - 1, -1, -1)]
    return tuple(days[k] > limit for k in keys if k in days)


def condition(over: tuple[bool, ...], stale: bool) -> str:
    """The scene is personal: whoever keeps going over gets the bad weather."""
    if stale:
        return "winter"
    if len(over) >= OVERGROWN_RUN and all(over[-OVERGROWN_RUN:]):
        return "overgrown"
    if over and over[-1]:
        return "drought"
    return "thriving"


def person_condition(days: dict, limit: int, today: date) -> str:
    return condition(personal_over(days, limit, today), is_stale(days, today))


def title_for(name: str, cond: str) -> str:
    return f"{name.upper()} · {_SHORT[cond]}"


def progress(farm: farm_rules.Farm) -> float:
    grown = sum(p.stage for p in farm.plots if not p.wilted)
    return grown / (farm_rules.PLOTS * farm_rules.MAX_STAGE)


def is_stale(days: dict, today: date) -> bool:
    recent = {(today - timedelta(days=i)).isoformat() for i in range(STALE_DAYS)}
    return not recent & days.keys()


def _scene(cond: str, farm, size: str):
    """The artwork for this person's condition; the drawn farm if the art isn't installed."""
    w = SIZES[size]
    art = scenes.scene(cond, w)
    if art is not None:
        return art
    cv = pixelfarm.render_scene(cond, progress(farm), min(3, farm.streak))
    return cv.resized(w, scenes.height_for(w))


def frames(name: str, before, after, days: dict, limit: int, today: date,
           size: str = DEFAULT_SIZE) -> list[list[str]]:
    """Panels for the open animation: yesterday's scene cross-fading into today's."""
    stale = is_stale(days, today)
    cond = condition(personal_over(days, limit, today), stale)
    cond_before = condition(personal_over(days, limit, today - timedelta(days=1)), stale)
    title = f"{name.upper()} · {_SHORT[cond]}"
    end = _scene(cond, after, size)
    final = pixelfarm.panel(cond, title, end)
    if before == after and cond_before == cond:
        return [final]
    start = _scene(cond_before, before, size)
    return [pixelfarm.panel(cond, title, pixelfarm.crossfade(start, end, t))
            for t in FADE_STEPS[:-1]] + [final]
