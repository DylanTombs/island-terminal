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


def panel(header: list[str], png: Path, cols: int) -> str:
    """Header lines, then the image `cols` cells wide; the cursor ends on the line below."""
    return "".join(line + "\n" for line in header) + escape(png, cols, rows_for(cols)) + "\n"
