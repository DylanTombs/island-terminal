"""Show the real farm artwork as images in terminals with the iTerm2 inline-image protocol.

No redrawing: the PNG file bytes go to the terminal as-is (OSC 1337 File=...), and
the terminal scales the actual picture into a box of character cells.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

import scenes

# Terminals known to speak OSC 1337 inline images.
_IMAGE_TERMINALS = {"iTerm.app", "WezTerm"}
CELL_ASPECT = 2.3  # cell height / width in iTerm2's default font (measured)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 20_000_000
MAX_PANEL_COLS = 60  # ~ a normal-sized terminal for the pair; matches header wrap width


def supported() -> bool:
    if os.environ.get("ISLAND_INLINE_IMAGES") == "0":
        return False
    term = os.environ.get("TERM_PROGRAM", "")
    return term in _IMAGE_TERMINALS or os.environ.get("LC_TERMINAL") == "iTerm2"


def scene_png(state: str) -> Path | None:
    """The scene's PNG if it's installed and really is a (reasonably sized) PNG."""
    path = scenes.SCENE_DIR / f"{state}.png"
    try:
        with path.open("rb") as f:
            ok = f.read(len(PNG_MAGIC)) == PNG_MAGIC
        return path if ok and path.stat().st_size <= MAX_BYTES else None
    except OSError:
        return None


def rows_for(cols: int) -> int:
    """Cell rows an image `cols` cells wide takes at the scenes' aspect ratio."""
    return max(1, round(cols * scenes.ASPECT / CELL_ASPECT))


def escape(path: Path, cols: int, rows: int) -> str:
    data = path.read_bytes()
    payload = base64.b64encode(data).decode("ascii")
    return (f"\x1b]1337;File=inline=1;size={len(data)};width={cols};height={rows};"
            f"preserveAspectRatio=1:{payload}\x07")


def grid(items: list[tuple[list[str], Path]], cols: int, gap: int) -> str:
    """Panels side by side: each a few header lines over an image `cols` cells wide.

    Space is reserved first so nothing scrolls mid-draw, then each panel is placed
    with save/restore-cursor and a column move.
    """
    rows = rows_for(cols)
    head = max(len(h) for h, _ in items)
    height = head + rows
    out = ["\n" * height, f"\x1b[{height}A", "\x1b7"]
    for i, (header, png) in enumerate(items):
        x = i * (cols + gap) + 1
        out.append("\x1b8")
        for line in header + [""] * (head - len(header)):
            out.append(f"\x1b[{x}G{line}\x1b[1B")
        out.append(f"\x1b[{x}G" + escape(png, cols, rows))
    out.append("\x1b8" + f"\x1b[{height}B\r")
    return "".join(out)
