"""Composes the header, the farm and the chart; plays the ASCII open animation."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from datetime import date

import art
import chart
import colors as c
import farm as farm_rules
import inline_image
import pixelfarm
import pixelview

FRAME_S = 0.18


@dataclass(frozen=True)
class Person:
    name: str
    days: dict
    limit: int


def possessive(name: str) -> str:
    """"Dylan's", but "My"/"Your" for the default names (not "Me's")."""
    return {"me": "My", "you": "Your"}.get(name.strip().lower(), f"{name}'s")


def header(p: Person, today: date, on: bool, width: int = art.WIDTH) -> list[str]:
    key = today.isoformat()
    mins = p.days.get(key)
    streak = farm_rules.personal_streak(p.days, p.limit, today)
    if mins is None:
        state, today_txt = c.paint("no data yet", c.GREY, on), "today --"
    else:
        over = mins > p.limit
        state = c.paint("over" if over else "under", c.RED if over else c.GREEN, on)
        today_txt = f"today {chart.fmt_hm(mins)}"
    parts = [c.paint(f"{possessive(p.name)} island", c.BOLD, on), today_txt,
             f"(limit {chart.fmt_hm(p.limit)}) · {state}",
             f"streak {streak} day{'s' if streak != 1 else ''}"]
    # Wrap the " · "-joined segments at the farm width.
    lines, cur = [], ""
    for i, part in enumerate(parts):
        sep = "" if not cur else (" " if i == 2 else " · ")
        if cur and c.visible_len(cur + sep + part) > width:
            lines.append(cur)
            cur = part
        else:
            cur += sep + part
    return lines + [cur]


def _changed(before, after) -> list[int]:
    return [i for i, (a, b) in enumerate(zip(before.plots, after.plots)) if a != b]


def frames(before, after, on: bool) -> list[list[str]]:
    """~1 s of today's change: a crop rising out of the soil, or flickering to wilt."""
    changed = _changed(before, after)
    final = art.render_farm(after, on)
    if not changed:
        return [final]
    grew = any(after.plots[i].stage > before.plots[i].stage and not after.plots[i].wilted
               for i in changed)
    if grew:
        seq = [art.render_farm(after, on, sink={i: k for i in changed}) for k in (4, 3, 2, 1)]
    else:
        old = art.render_farm(before, on)
        seq = [old, final, old, final, old]
    return seq + [final]


def use_pixel_art(mode: str, on: bool, size: str = pixelview.DEFAULT_SIZE) -> bool:
    """auto: pixel art when colour is on and the terminal fits one pixel panel."""
    if mode in ("ascii", "pixel"):
        return mode == "pixel" and on
    return on and c.term_width() >= pixelview.panel_width(size)


def build_frames(p: Person, today: date, on: bool, pixel: bool = False,
                 size: str = pixelview.DEFAULT_SIZE) -> list[list[str]]:
    before, after = farm_rules.simulate(p.days, p.limit, today)
    hdr = header(p, today, on)
    if pixel:
        seq = pixelview.frames(p.name, before, after, p.days, p.limit, today, size)
    else:
        seq = frames(before, after, on)
    return [hdr + f for f in seq]


def image_panel(p: Person, today: date, on: bool) -> str | None:
    """The real artwork as an inline image (iTerm2), or None if the terminal can't show it."""
    if not (on and inline_image.supported()):
        return None
    cond = pixelview.person_condition(p.days, p.limit, today)
    png = inline_image.scene_png(cond)
    if png is None:
        return None
    cols = min(chart.WIDTH, c.term_width())  # as wide as the graph below it
    accent = pixelfarm.ACCENT[cond]
    title = c.paint(pixelview.title_for(p.name, cond),
                    f"1;38;2;{accent[0]};{accent[1]};{accent[2]}", on)
    return inline_image.panel(header(p, today, on, cols) + [title], png, cols)


def _play(seq: list[list[str]], animate: bool) -> None:
    out = sys.stdout
    if not animate:
        seq = seq[-1:]
    if len(seq) > 1:
        out.write("\x1b[?25l")
    try:
        for i, frame in enumerate(seq):
            if i:
                out.write(f"\x1b[{len(frame)}A\r")
            out.write("\n".join(frame) + "\n")
            out.flush()
            if i < len(seq) - 1:
                time.sleep(FRAME_S)
    finally:
        if len(seq) > 1:
            out.write("\x1b[?25h")


def show(p: Person, today: date, on: bool, animate: bool,
         with_chart: bool = True, notes: list[str] | None = None, art_mode: str = "auto",
         size: str = pixelview.DEFAULT_SIZE) -> None:
    out = sys.stdout
    image = image_panel(p, today, on) if art_mode != "ascii" else None
    if image:
        out.write(image)
    else:
        _play(build_frames(p, today, on, use_pixel_art(art_mode, on, size), size), animate)
    if with_chart:
        out.write("\n" + "\n".join(chart.render_chart(p.days, p.limit, today, on)) + "\n")
    for note in notes or []:
        out.write(c.paint(note, c.GREY, on) + "\n")
