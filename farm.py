"""Pure farm rules. No I/O.

- The field has PLOTS plots, each at stage 0 (bare) .. MAX_STAGE (in bloom).
- Good day: if a crop is wilted it recovers; otherwise the first unfinished plot
  grows one stage, so the field fills up left to right over weeks.
- Bad day: the newest healthy crop wilts. If one is already wilted (two bad days
  running), the wilted crop dies back a stage instead.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

PLOTS = 10
MAX_STAGE = 4
HISTORY_DAYS = 120
DETAIL_STREAK = 3


@dataclass(frozen=True)
class Plot:
    stage: int = 0
    wilted: bool = False


@dataclass(frozen=True)
class Farm:
    plots: tuple[Plot, ...] = tuple(Plot() for _ in range(PLOTS))
    streak: int = 0  # consecutive good days
    recent: tuple[bool, ...] = ()  # last few days, True = bad

    @property
    def grey_sky(self) -> bool:
        return sum(self.recent[-3:]) >= 2

    @property
    def details(self) -> bool:
        return self.streak >= DETAIL_STREAK


def _set(plots, i, plot):
    return plots[:i] + (plot,) + plots[i + 1:]


def step(farm: Farm, bad: bool) -> Farm:
    plots = farm.plots
    wilted = next((i for i, p in enumerate(plots) if p.wilted), None)
    if bad:
        if wilted is not None:
            p = plots[wilted]
            stage = p.stage - 1
            plots = _set(plots, wilted, Plot(stage, stage > 0))
        else:
            grown = [i for i, p in enumerate(plots) if p.stage > 0]
            if grown:
                i = grown[-1]
                plots = _set(plots, i, replace(plots[i], wilted=True))
    elif wilted is not None:
        plots = _set(plots, wilted, replace(plots[wilted], wilted=False))
    else:
        i = next((i for i, p in enumerate(plots) if p.stage < MAX_STAGE), None)
        if i is not None:
            plots = _set(plots, i, Plot(plots[i].stage + 1))
    return Farm(plots, 0 if bad else farm.streak + 1, (farm.recent + (bad,))[-7:])


def personal_streak(days: dict, limit: int, today: date) -> int:
    """Days in a row under the limit, ending today (or yesterday if today is empty)."""
    d = today if today.isoformat() in days else today - timedelta(days=1)
    n = 0
    while d.isoformat() in days and days[d.isoformat()] <= limit:
        n += 1
        d -= timedelta(days=1)
    return n


def simulate(days: dict, limit: int, today: date) -> tuple[Farm, Farm]:
    """Returns (farm as of yesterday, farm including today), replaying every day with data."""
    if not days:
        return Farm(), Farm()
    start = max(date.fromisoformat(min(days)), today - timedelta(days=HISTORY_DAYS))
    farm = Farm()
    d = start
    while d < today:
        key = d.isoformat()
        if key in days:
            farm = step(farm, days[key] > limit)
        d += timedelta(days=1)
    key = today.isoformat()
    return farm, (step(farm, days[key] > limit) if key in days else farm)
