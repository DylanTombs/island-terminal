"""The farm artwork (assets/scenes/<state>.ppm, cut by tools/import_scenes.py) as Canvases."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pixelfarm

SCENE_DIR = Path(__file__).resolve().parent / "assets" / "scenes"
ASPECT = 168 / 360  # height / width of the stored scenes


class SceneError(ValueError):
    pass


def height_for(width: int) -> int:
    """Pixel height for a panel `width` pixels wide; even, since a cell is 2 pixels tall."""
    return max(2, 2 * round(width * ASPECT / 2))


def _parse_ppm(data: bytes) -> tuple[int, int, bytes]:
    parts = data.split(maxsplit=4)
    if len(parts) < 5 or parts[0] != b"P6" or parts[3] != b"255":
        raise SceneError("not an 8-bit binary PPM (P6)")
    w, h = int(parts[1]), int(parts[2])
    pixels = parts[4]
    if len(pixels) < w * h * 3:
        raise SceneError(f"truncated PPM: expected {w * h * 3} bytes, got {len(pixels)}")
    return w, h, pixels


@lru_cache(maxsize=None)
def _source(state: str) -> pixelfarm.Canvas | None:
    path = SCENE_DIR / f"{state}.ppm"
    if not path.exists():
        return None
    w, h, px = _parse_ppm(path.read_bytes())
    cv = pixelfarm.Canvas(w, h)
    cv.px = [[tuple(px[(y * w + x) * 3:(y * w + x) * 3 + 3]) for x in range(w)] for y in range(h)]
    return cv


@lru_cache(maxsize=None)
def scene(state: str, width: int) -> pixelfarm.Canvas | None:
    """The artwork for `state` downsampled to `width` pixels, or None if it isn't installed."""
    src = _source(state)
    return src.resized(width, height_for(width)) if src else None
