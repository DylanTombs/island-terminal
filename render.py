"""Composes headers, farm(s) and the chart; plays the open animation."""

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
MIN_IMAGE_COLS = 50
GAP = "   "


@dataclass(frozen=True)
class Person:
    name: str
    days: dict
    limit: int
    variant: str


def header(p: Person, today: date, on: bool) -> list[str]:
    key = today.isoformat()
    mins = p.days.get(key)
    streak = farm_rules.personal_streak(p.days, p.limit, today)
    if mins is None:
        state, today_txt = c.paint("no data yet", c.GREY, on), "today --"
    else:
        over = mins > p.limit
        state = c.paint("over" if over else "under", c.RED if over else c.GREEN, on)
        today_txt = f"today {chart.fmt_hm(mins)}"
    parts = [c.paint(f"{p.name}'s island", c.BOLD, on), today_txt,
             f"(limit {chart.fmt_hm(p.limit)}) · {state}",
             f"streak {streak} day{'s' if streak != 1 else ''}"]
    # Wrap the " · "-joined segments at the farm width.
    lines, cur = [], ""
    for i, part in enumerate(parts):
        sep = "" if not cur else (" " if i == 2 else " · ")
        if cur and c.visible_len(cur + sep + part) > art.WIDTH:
            lines.append(cur)
            cur = part
        else:
            cur += sep + part
    return lines + [cur]


def _changed(before, after) -> list[int]:
    return [i for i, (a, b) in enumerate(zip(before.plots, after.plots)) if a != b]


def frames(before, after, on: bool, variant: str) -> list[list[str]]:
    """~1 s of today's change: a crop rising out of the soil, or flickering to wilt."""
    changed = _changed(before, after)
    final = art.render_farm(after, on, variant)
    if not changed:
        return [final]
    grew = any(after.plots[i].stage > before.plots[i].stage and not after.plots[i].wilted
               for i in changed)
    if grew:
        seq = [art.render_farm(after, on, variant, {i: k for i in changed}) for k in (4, 3, 2, 1)]
    else:
        old = art.render_farm(before, on, variant)
        seq = [old, final, old, final, old]
    return seq + [final]


def _side_by_side(blocks: list[list[str]]) -> list[str]:
    height = max(len(b) for b in blocks)
    padded = [b + [""] * (height - len(b)) for b in blocks]
    width = max(c.visible_len(line) for b in blocks for line in b)
    return [GAP.join(c.pad(line, width) for line in row) for row in zip(*padded)]


def _stack(blocks: list[list[str]]) -> list[str]:
    out = []
    for b in blocks:
        out.extend(b + [""])
    return out[:-1]


def use_pixel_art(mode: str, on: bool, size: str = pixelview.DEFAULT_SIZE) -> bool:
    """auto: pixel art when colour is on and the terminal fits one pixel panel."""
    if mode in ("ascii", "pixel"):
        return mode == "pixel" and on
    return on and c.term_width() >= pixelview.panel_width(size)


def build_frames(people: list[Person], today: date, on: bool, pixel: bool = False,
                 size: str = pixelview.DEFAULT_SIZE) -> list[list[str]]:
    linked = [(p.days, p.limit) for p in people]
    before, after = farm_rules.simulate(linked, today)
    headers = [header(p, today, on) for p in people]
    rows = max(len(h) for h in headers)  # pad so side-by-side panels line up
    per_person = []
    for p, hdr in zip(people, headers):
        hdr = hdr + [""] * (rows - len(hdr))
        if pixel:
            seq = pixelview.frames(p.name, before, after, p.days, p.limit, today, size)
        else:
            seq = frames(before, after, on, p.variant)
        per_person.append([hdr + f for f in seq])
    n = max(len(f) for f in per_person)
    per_person = [f + [f[-1]] * (n - len(f)) for f in per_person]
    width = pixelview.panel_width(size) if pixel else art.WIDTH
    wide = c.term_width() >= len(people) * width + len(GAP) * (len(people) - 1)
    combine = _side_by_side if wide else _stack
    return [combine([pp[i] for pp in per_person]) for i in range(n)]


def image_panels(people: list[Person], today: date, on: bool) -> str | None:
    """The real artwork as inline images (iTerm2), or None if the terminal can't show it."""
    if not (on and inline_image.supported()):
        return None
    conds = [pixelview.person_condition(p.days, p.limit, today) for p in people]
    pngs = [inline_image.scene_png(cond) for cond in conds]
    if not all(pngs):
        return None
    gap = len(GAP)
    cols = min(inline_image.MAX_PANEL_COLS,
               (c.term_width() - gap * (len(people) - 1)) // len(people))
    if cols < MIN_IMAGE_COLS:  # too narrow side by side: stack full width
        cols = min(inline_image.MAX_PANEL_COLS, c.term_width())
        return "".join(image_panels_row([(p, cond, png)], today, on, cols, gap)
                       for p, cond, png in zip(people, conds, pngs))
    return image_panels_row(list(zip(people, conds, pngs)), today, on, cols, gap)


def image_panels_row(row, today: date, on: bool, cols: int, gap: int) -> str:
    items = []
    for p, cond, png in row:
        accent = pixelfarm.ACCENT[cond]
        title = c.paint(pixelview.title_for(p.name, cond), f"1;38;2;{accent[0]};{accent[1]};{accent[2]}", on)
        items.append((header(p, today, on) + [title], png))
    return inline_image.grid(items, cols, gap)


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


def show(people: list[Person], today: date, on: bool, animate: bool,
         with_chart: bool = True, notes: list[str] | None = None, art_mode: str = "auto",
         size: str = pixelview.DEFAULT_SIZE) -> None:
    out = sys.stdout
    pixel = use_pixel_art(art_mode, on, size)
    images = image_panels(people, today, on) if art_mode != "ascii" else None
    if images:
        out.write(images)
    else:
        _play(build_frames(people, today, on, pixel, size), animate)
    if with_chart:
        me, *rest = people
        friend = rest[0] if rest else None
        out.write("\n" + "\n".join(chart.render_chart(
            me.days, me.limit, today, on, friend.days if friend else None,
            (me.name, friend.name if friend else ""),
            friend.limit if friend else None)) + "\n")
    for note in notes or []:
        out.write(c.paint(note, c.GREY, on) + "\n")
