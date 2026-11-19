#!/usr/bin/env python3
"""Cut the four farm scenes out of assets/scenes.png into assets/scenes/<state>.{png,ppm}.

The source is a 2x2 sheet (thriving, drought / overgrown, winter). macOS `sips` does
the crop. The .png is the untouched full-resolution crop, shown as a real image in
terminals that support inline images (iTerm2). The .ppm is a resampled copy for the
half-block fallback in other terminals. Run once after replacing assets/scenes.png:

    python3 tools/import_scenes.py
"""

from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "scenes.png"
OUT_DIR = ROOT / "assets" / "scenes"
STORE_W = 360  # stored width; island downsamples from this at draw time
INSET = 4  # px trimmed inside each panel's border

# Artwork bounds (x0, y0, x1, y1) on the 2730x1536 sheet, found by dark-pixel profiles.
PANELS = {
    "thriving": (101, 182, 1339, 764),
    "drought": (1389, 182, 2627, 764),
    "overgrown": (101, 862, 1339, 1441),
    "winter": (1389, 862, 2627, 1441),
}


def _sips(*args: str) -> None:
    result = subprocess.run(["sips", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"sips failed: {result.stderr.strip()}")


def _read_bmp(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    offset = struct.unpack_from("<I", data, 10)[0]
    w, h = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0] // 8
    stride = (w * bpp + 3) & ~3
    bottom_up, h = h > 0, abs(h)
    rgb = bytearray()
    for y in range(h):
        row = offset + (h - 1 - y if bottom_up else y) * stride
        for x in range(w):
            b, g, r = data[row + x * bpp: row + x * bpp + 3]
            rgb += bytes((r, g, b))
    return w, h, bytes(rgb)


def cut(state: str, box: tuple[int, int, int, int], tmp: Path) -> Path:
    x0, y0, x1, y1 = box[0] + INSET, box[1] + INSET, box[2] - INSET, box[3] - INSET
    w, h = x1 - x0, y1 - y0
    store_h = round(STORE_W * h / w)
    png = OUT_DIR / f"{state}.png"
    _sips("-c", str(h), str(w), "--cropOffset", str(y0), str(x0), str(SOURCE), "--out", str(png))
    bmp = tmp / f"{state}.bmp"
    _sips("-s", "format", "bmp", str(SOURCE), "--out", str(bmp))
    _sips("-c", str(h), str(w), "--cropOffset", str(y0), str(x0), str(bmp))
    _sips("-z", str(store_h), str(STORE_W), str(bmp))
    pw, ph, rgb = _read_bmp(bmp)
    out = OUT_DIR / f"{state}.ppm"
    out.write_bytes(f"P6 {pw} {ph} 255\n".encode() + rgb)
    return out


def main() -> int:
    if not SOURCE.exists():
        print(f"missing {SOURCE}", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for state, box in PANELS.items():
            print(cut(state, box, Path(tmp)).relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
