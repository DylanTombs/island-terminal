"""ASCII farm scene: 60 columns x 17 rows, plain ASCII, optional ANSI colour."""

from __future__ import annotations

from dataclasses import dataclass

import colors as c
from farm import Farm

WIDTH, HEIGHT = 60, 17
CROP_TOP, SOIL_ROW, FENCE_ROW = 12, 16, 11
PLOT_W = 6

# 4-line sprites, 5 columns wide, bottom line sits on the soil.
GROWING = (
    ("     ", "     ", "     ", " . . "),
    ("     ", "     ", "     ", " \\|/ "),
    ("     ", "     ", " \\|/ ", "  |  "),
    ("     ", "  |  ", " \\|/ ", " \\|/ "),
    ("  @  ", " \\|/ ", " \\|/ ", " \\|/ "),
)
WILTED = (
    GROWING[0],
    ("     ", "     ", "     ", " /|\\ "),
    ("     ", "     ", " /|\\ ", "  |  "),
    ("     ", "  )  ", " /|\\ ", " /|\\ "),
    ("   o ", "  )  ", " /|\\ ", " /|\\ "),
)

SUN = ("  \\ | /", "-- (O) --", "  / | \\")
CLOUD = ("   .--.  ", " .(    ). ", "(___.__)_)")
BARN = (
    "    .-----.    ",
    "   /  [_]  \\   ",
    "  /_________\\  ",
    "  |  |\\ /|  |  ",
    "  |  | X |  |  ",
    "  |__|/_\\|__|  ",
)
SILO = (" ___ ", "(___)", "|   |", "|===|", "|   |", "|___|")
SCARECROW = ("  _^_ ", "  (o) ", " --|--", "   |  ", "  / \\ ")
HILLS = ((23, "_.-~~~-._"), (32, "_.-~-._"), (49, "_.-~~-._"))


@dataclass(frozen=True)
class Style:
    barn: str
    head: str
    head_color: str


STYLES = {
    "wheat": Style(c.RED, "@", c.BRIGHT_YELLOW),
}


def _blank():
    return [[(" ", None) for _ in range(WIDTH)] for _ in range(HEIGHT)]


def _put(grid, row, col, text, color, skip_spaces=True):
    for i, ch in enumerate(text):
        x = col + i
        if 0 <= row < HEIGHT and 0 <= x < WIDTH and not (skip_spaces and ch == " "):
            grid[row][x] = (ch, color)


def _sky(grid, farm: Farm):
    if farm.grey_sky:
        for col in (3, 22, 40):
            for r, line in enumerate(CLOUD):
                _put(grid, r, col, line, c.GREY)
        for col in range(4, 56, 3):
            _put(grid, 3 + col % 2, col, "/", c.GREY)
        return
    for r, line in enumerate(SUN):
        _put(grid, r, 48, line, c.BRIGHT_YELLOW)
    for r, line in enumerate(CLOUD):
        _put(grid, r + 1, 4, line, c.WHITE)
    if farm.details:
        _put(grid, 1, 28, "v   v", c.GREY)
        _put(grid, 2, 32, "v", c.GREY)


def _yard(grid, farm: Farm, style: Style):
    for col, hill in HILLS:
        _put(grid, 10, col, hill, c.GREEN)
    for r, line in enumerate(BARN):
        color = c.WHITE if r < 3 else style.barn
        _put(grid, 5 + r, 1, line, color)
    for r, line in enumerate(SILO):
        _put(grid, 5 + r, 17, line, c.GREY if farm.grey_sky else c.WHITE)
    if farm.details:
        for r, line in enumerate(SCARECROW):
            _put(grid, 6 + r, 44, line, c.YELLOW)
    fence = "".join("+" if x % 4 == 0 else "-" for x in range(WIDTH))
    _put(grid, FENCE_ROW, 0, fence, c.YELLOW)


def _crop_color(ch: str, wilted: bool, style: Style) -> str:
    if ch == ".":
        return c.YELLOW
    if wilted:
        return c.GREY if ch == "o" else c.YELLOW
    if ch == style.head:
        return style.head_color
    return c.GREEN if ch == "|" else c.BRIGHT_GREEN


def _field(grid, farm: Farm, style: Style, sink: dict[int, int]):
    _put(grid, SOIL_ROW, 0, "~" * WIDTH, c.YELLOW)
    for i, plot in enumerate(farm.plots):
        sprite = (WILTED if plot.wilted else GROWING)[plot.stage]
        offset = sink.get(i, 0)  # animation: sprite rises out of the soil
        col = 1 + i * PLOT_W
        for r, line in enumerate(sprite):
            row = CROP_TOP + r + offset
            if row >= SOIL_ROW:
                continue
            line = line.replace("@", style.head)
            for x, ch in enumerate(line):
                if ch != " ":
                    _put(grid, row, col + x, ch, _crop_color(ch, plot.wilted, style))
        if farm.details and i < len(farm.plots) - 1:
            _put(grid, SOIL_ROW - 1, col + 5, '"', c.GREEN)


def render_farm(farm: Farm, on: bool, variant: str = "wheat",
                sink: dict[int, int] | None = None) -> list[str]:
    """Return HEIGHT lines, each exactly WIDTH visible columns."""
    style = STYLES[variant]
    grid = _blank()
    _sky(grid, farm)
    _yard(grid, farm, style)
    _field(grid, farm, style, sink or {})
    return ["".join(c.paint(ch, col, on) for ch, col in row) for row in grid]
