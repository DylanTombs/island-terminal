"""Sample data for filming: a month of screen time.

The story: around 6h a day last week, cut to under the 4h limit this week. The mode
picks how today ends, and so which scene shows:
  grow (default)  under today            -> thriving
  wilt            over today (7h)        -> severe drought
  abandon         over 3 days running    -> overgrown
"""

from __future__ import annotations

from datetime import date, timedelta

LIMIT = 240  # the story is told against a 4h limit, whatever your config says
NAME = "You"
MODES = ("grow", "wilt", "abandon")

# Oldest first, ending today. Steady early weeks so the field is well grown.
_EARLY = 16
_DAYS = [300, 210, 190, 230, 280, 200, 215, 225, 180, 235, 220, 250, 205, 190,
         410, 380, 340, 395, 360, 330, 375,
         235, 235, 228, 220, 215, 240, 214]
_OVER_TODAY = 420
_OVER_LAST_3 = [300, 350, 420]


def _dated(values: list[int], today: date) -> dict[str, int]:
    start = today - timedelta(days=len(values) - 1)
    return {(start + timedelta(days=i)).isoformat(): v for i, v in enumerate(values)}


def sample(today: date, mode: str = "grow") -> dict[str, int]:
    if mode not in MODES:
        raise ValueError(f"demo mode must be one of {', '.join(MODES)}")
    values = [180 + (i * 37) % 55 for i in range(_EARLY)] + _DAYS
    if mode == "wilt":
        values = values[:-1] + [_OVER_TODAY]
    elif mode == "abandon":
        values = values[:-3] + _OVER_LAST_3
    return _dated(values, today)
