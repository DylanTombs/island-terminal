"""ANSI colour helpers. Callers pass `on` so NO_COLOR is decided once."""

from __future__ import annotations

import os
import re
import shutil
import sys

RESET = "\x1b[0m"
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

GREEN, BRIGHT_GREEN, YELLOW, BRIGHT_YELLOW = "32", "92", "33", "93"
RED, BRIGHT_RED, BLUE, CYAN, MAGENTA = "31", "91", "34", "36", "35"
WHITE, GREY, BOLD, DIM = "97", "90", "1", "2"


def color_enabled(stream=sys.stdout) -> bool:
    if "NO_COLOR" in os.environ:
        return False
    return stream.isatty() or "ISLAND_FORCE_COLOR" in os.environ


def term_width(stream=sys.stdout) -> int:
    """Terminal width ($COLUMNS wins), 80 when not attached to a terminal."""
    return shutil.get_terminal_size((80, 24)).columns


def paint(text: str, code: str | None, on: bool) -> str:
    return f"\x1b[{code}m{text}{RESET}" if on and code and text else text


def visible_len(text: str) -> int:
    return len(_ANSI.sub("", text))


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - visible_len(text))
