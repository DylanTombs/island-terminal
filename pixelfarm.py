#!/usr/bin/env python3
"""pixelfarm: a 3/4 isometric pixel-art farm in TrueColor half-blocks.

Usage:
  python3 pixelfarm.py [thriving|drought|overgrown|winter|all] [--png out.png]

Every terminal cell is two stacked pixels (upper = foreground of '▀', lower =
background). The scene is drawn into an RGB pixel buffer by a tiny Canvas class,
then compiled to ANSI. Stdlib only.
"""

from __future__ import annotations

import math
import shutil
import struct
import sys
import zlib

W, H = 120, 76  # pixels per panel -> 120 columns x 38 rows
STATES = ("thriving", "drought", "overgrown", "winter")
TITLES = {
    "thriving": "CONDITION: THRIVING (PEAK HARVEST)",
    "drought": "CONDITION: SEVERE DROUGHT (PARCHED)",
    "overgrown": "CONDITION: OVERGROWN (ABANDONED)",
    "winter": "CONDITION: DEEP WINTER (FROZEN)",
}
ACCENT = {
    "thriving": (120, 200, 90), "drought": (214, 168, 92),
    "overgrown": (110, 170, 80), "winter": (150, 196, 228),
}
SLATE, SLATE_HI = (22, 28, 32), (36, 46, 52)

# ------------------------------------------------------------------ helpers


def hsh(x: int, y: int, s: int = 0) -> float:
    n = (x * 374761393 + y * 668265263 + s * 982451653) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65536


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def pick(x, y, cols, s=0, weights=None):
    r = hsh(x, y, s)
    weights = weights or [1 / len(cols)] * len(cols)
    acc = 0.0
    for c, w in zip(cols, weights):
        acc += w
        if r < acc:
            return c
    return cols[-1]


def V(*p):
    return tuple(float(v) for v in p)


def add(p, q, k=1.0):
    return (p[0] + q[0] * k, p[1] + q[1] * k)


# ------------------------------------------------------------------ canvas


class Canvas:
    def __init__(self, w: int, h: int, bg=(0, 0, 0)):
        self.w, self.h = w, h
        self.px = [[bg] * w for _ in range(h)]

    def set(self, x, y, c):
        x, y = int(round(x)), int(round(y))
        if c and 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[y][x]
        return (0, 0, 0)

    def blend(self, x, y, c, a):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = mix(self.px[y][x], c, a)

    def fill(self, inside, color, bbox=None):
        """Fill every pixel where inside(x+.5, y+.5); color is rgb or fn(x, y)."""
        x0, y0, x1, y1 = bbox or (0, 0, self.w, self.h)
        for y in range(max(0, int(y0)), min(self.h, int(y1) + 1)):
            for x in range(max(0, int(x0)), min(self.w, int(x1) + 1)):
                if inside(x + 0.5, y + 0.5):
                    c = color(x, y) if callable(color) else color
                    self.set(x, y, c)

    def poly(self, pts, color):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]

        def inside(px, py):
            hit = False
            j = len(pts) - 1
            for i in range(len(pts)):
                xi, yi = pts[i]
                xj, yj = pts[j]
                if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                    hit = not hit
                j = i
            return hit

        self.fill(inside, color, (min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1))

    def ellipse(self, cx, cy, rx, ry, color):
        self.fill(lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1,
                  color, (cx - rx - 1, cy - ry - 1, cx + rx + 1, cy + ry + 1))

    def line(self, p, q, color, thick=1):
        n = int(max(abs(q[0] - p[0]), abs(q[1] - p[1]))) + 1
        for i in range(n + 1):
            t = i / n
            x, y = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
            for k in range(thick):
                c = color(int(x), int(y)) if callable(color) else color
                self.set(x, y + k, c)

    def rect(self, x0, y0, x1, y1, color):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self.set(x, y, color(x, y) if callable(color) else color)

    def resized(self, w: int, h: int) -> "Canvas":
        """Area-averaged downscale: each output pixel blends the source pixels it covers."""
        out = Canvas(w, h)
        sx, sy = self.w / w, self.h / h
        out.px = [[self._area(x * sx, y * sy, sx, sy) for x in range(w)] for y in range(h)]
        return out

    def _area(self, x0, y0, sx, sy):
        x1, y1 = x0 + sx, y0 + sy
        acc, total = [0.0, 0.0, 0.0], 0.0
        for j in range(int(y0), min(self.h, math.ceil(y1))):
            wy = min(y1, j + 1) - max(y0, j)
            for i in range(int(x0), min(self.w, math.ceil(x1))):
                w = (min(x1, i + 1) - max(x0, i)) * wy
                p = self.px[j][i]
                acc = [acc[k] + p[k] * w for k in range(3)]
                total += w
        return tuple(round(a / total) for a in acc)

    # -------------------------------------------------------------- output

    def to_ansi(self) -> list[str]:
        rows = []
        for y in range(0, self.h - 1, 2):
            out, last = [], None
            for x in range(self.w):
                top, bot = self.px[y][x], self.px[y + 1][x]
                key = (top, bot)
                if key != last:
                    out.append(f"\x1b[38;2;{top[0]};{top[1]};{top[2]};48;2;{bot[0]};{bot[1]};{bot[2]}m")
                    last = key
                out.append("▀")
            rows.append("".join(out) + "\x1b[0m")
        return rows

    def to_png(self, path: str, scale: int = 6) -> None:
        raw = bytearray()
        for row in self.px:
            line = bytearray([0])
            for c in row:
                line.extend(bytes(c) * scale)
            raw.extend(bytes(line) * scale)

        def chunk(tag, data):
            return (struct.pack(">I", len(data)) + tag + data
                    + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

        hdr = struct.pack(">IIBBBBB", self.w * scale, self.h * scale, 8, 2, 0, 0, 0)
        with open(path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", hdr)
                    + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


# ------------------------------------------------------------------ palettes

PALETTES = {
    "thriving": dict(
        g=[(86, 166, 54), (104, 184, 62), (72, 148, 46)], dirt=[(214, 178, 116), (198, 160, 100)],
        rut=(170, 132, 82), leaf=(58, 138, 48), leaf_hi=(118, 192, 74), leaf_dk=(34, 92, 36),
        trunk=(106, 70, 40), fruit=(226, 64, 44), wheat=(228, 188, 78), wheat_hi=(252, 226, 128),
        wheat_dk=(182, 138, 50), soil=(118, 78, 46), soil_dk=(88, 56, 32), pumpkin=(234, 124, 30),
        pumpkin_hi=(252, 168, 64), vine=(52, 124, 42), wall=(192, 42, 40), wall_dk=(146, 28, 30),
        wall_hi=(214, 72, 60), trim=(244, 238, 226), roof=(72, 86, 108), roof_hi=(100, 116, 140),
        roof_dk=(46, 56, 72), silo=(180, 50, 44), silo_hi=(214, 92, 76), dome=(196, 200, 206),
        water=(58, 120, 204), water_hi=(140, 196, 244), water_dk=(38, 86, 160), bank=(64, 112, 46),
        fence=(116, 76, 42), fence_hi=(162, 114, 66), fence_dk=(76, 48, 26)),
    "drought": dict(
        g=[(216, 182, 122), (204, 166, 106), (190, 152, 96)], dirt=[(228, 200, 148), (214, 184, 132)],
        rut=(186, 150, 102), leaf=(0, 0, 0), leaf_hi=(0, 0, 0), leaf_dk=(0, 0, 0),
        trunk=(104, 84, 66), fruit=None, wheat=(160, 120, 68), wheat_hi=(190, 154, 94),
        wheat_dk=(118, 86, 50), soil=(146, 108, 70), soil_dk=(110, 80, 52), pumpkin=None,
        pumpkin_hi=None, vine=(128, 100, 62), wall=(176, 104, 80), wall_dk=(138, 80, 60),
        wall_hi=(196, 130, 100), trim=(214, 200, 172), roof=(140, 130, 118), roof_hi=(168, 156, 140),
        roof_dk=(102, 94, 86), silo=(156, 156, 150), silo_hi=(190, 188, 180), dome=(176, 172, 164),
        water=(150, 120, 86), water_hi=(172, 142, 104), water_dk=(96, 72, 50), bank=(170, 136, 92),
        fence=(116, 88, 60), fence_hi=(150, 118, 84), fence_dk=(82, 60, 40)),
    "overgrown": dict(
        g=[(50, 94, 38), (64, 112, 44), (40, 76, 32)], dirt=[(118, 96, 60), (98, 80, 50)],
        rut=(80, 64, 40), leaf=(38, 92, 40), leaf_hi=(74, 130, 54), leaf_dk=(22, 60, 28),
        trunk=(84, 58, 36), fruit=None, wheat=(82, 92, 40), wheat_hi=(112, 112, 52),
        wheat_dk=(58, 60, 30), soil=(80, 62, 40), soil_dk=(58, 44, 28), pumpkin=None,
        pumpkin_hi=None, vine=(54, 84, 34), wall=(98, 72, 48), wall_dk=(66, 48, 32),
        wall_hi=(124, 94, 62), trim=(146, 136, 108), roof=(78, 108, 58), roof_hi=(108, 138, 68),
        roof_dk=(48, 72, 38), silo=(122, 124, 116), silo_hi=(150, 152, 140), dome=(136, 138, 128),
        water=(40, 70, 50), water_hi=(62, 102, 62), water_dk=(28, 50, 36), bank=(36, 70, 30),
        fence=(92, 64, 38), fence_hi=(120, 90, 58), fence_dk=(60, 42, 24)),
    "winter": dict(
        g=[(234, 241, 249), (218, 230, 243), (200, 215, 233)], dirt=[(192, 206, 222), (176, 192, 210)],
        rut=(150, 168, 192), leaf=(0, 0, 0), leaf_hi=(0, 0, 0), leaf_dk=(0, 0, 0),
        trunk=(92, 78, 70), fruit=None, wheat=(226, 234, 246), wheat_hi=(246, 250, 255),
        wheat_dk=(120, 92, 70), soil=(126, 96, 74), soil_dk=(98, 74, 58), pumpkin=None,
        pumpkin_hi=None, vine=(126, 96, 74), wall=(178, 46, 44), wall_dk=(136, 30, 32),
        wall_hi=(204, 74, 64), trim=(244, 246, 250), roof=(240, 246, 252), roof_hi=(252, 254, 255),
        roof_dk=(150, 172, 204), silo=(170, 176, 186), silo_hi=(210, 216, 224), dome=(236, 242, 250),
        water=(146, 190, 224), water_hi=(190, 222, 244), water_dk=(110, 152, 196), bank=(246, 250, 255),
        fence=(112, 80, 54), fence_hi=(150, 112, 80), fence_dk=(74, 52, 36)),
}

# ------------------------------------------------------------------ layout
# Isometric axes: A runs up-right (2,-1), B runs down-right (2,1).

PATH = [((-4, 12), (56, 42)), ((56, 42), (78, 47)), ((56, 42), (64, 58)), ((64, 58), (70, 80)),
        ((56, 42), (120, 66))]
WHEAT = (V(0, 46), V(26, -13), V(14, 7))
PUMPKIN = (V(24, 21), V(22, -11), V(16, 8))
GARDEN = (V(74, 80), V(30, -15), V(18, 9))
BARN_F, BARN_W, BARN_L, BARN_H = V(70, 40), V(18, 9), V(22, -11), 13
POND = [(24, 63, 11, 5), (36, 64, 9, 5), (30, 67, 10, 4), (17, 66, 6, 3)]
RIDGE_TREES = [(x, 14 + (i % 2) * 2) for i, x in enumerate(range(4, 66, 10))] + [(108, 13), (117, 17)]
SIDE_TREES = [(116, 30), (6, 74), (15, 76), (111, 53)]


def local(p0, a, b, x, y):
    det = a[0] * b[1] - a[1] * b[0]
    dx, dy = x - p0[0], y - p0[1]
    return (dx * b[1] - dy * b[0]) / det, (a[0] * dy - a[1] * dx) / det


def corners(p0, a, b):
    return [p0, add(p0, a), add(add(p0, a), b), add(p0, b)]


def seg_dist(px, py, p, q):
    vx, vy = q[0] - p[0], q[1] - p[1]
    t = max(0, min(1, ((px - p[0]) * vx + (py - p[1]) * vy) / (vx * vx + vy * vy)))
    return math.hypot(px - p[0] - vx * t, py - p[1] - vy * t)


# ------------------------------------------------------------------ ground


def ground(cv, P, S):
    for y in range(H):
        for x in range(W):
            c = pick(x, y, P["g"], 1, [0.45, 0.35, 0.2])
            r = hsh(x, y, 2)
            if S == "thriving" and r < 0.012:
                c = pick(x, y, [(250, 250, 240), (250, 220, 80), (240, 140, 180)], 3)
            elif S == "overgrown" and r < 0.08:
                c = (30, 62, 26)
            elif S == "winter" and r < 0.05:
                c = (186, 204, 226)
            cv.set(x, y, c)
    if S == "drought":
        for i in range(70):
            x, y = hsh(i, 0, 7) * W, hsh(i, 1, 7) * H
            for _ in range(4):
                nx, ny = x + (hsh(int(x), int(y), 8) - 0.5) * 6, y + (hsh(int(y), int(x), 9) - 0.5) * 4
                cv.line((x, y), (nx, ny), (164, 128, 84))
                x, y = nx, ny


def path(cv, P, S):
    half = 2.2 if S == "overgrown" else 3.0

    def col(x, y):
        d = min(seg_dist(x + .5, y + .5, p, q) for p, q in PATH)
        if S == "overgrown" and hsh(x, y, 11) < 0.35:
            return pick(x, y, P["g"], 12)
        if abs(d - half * 0.45) < 0.45:
            return P["rut"]
        return pick(x, y, P["dirt"], 13)

    cv.fill(lambda x, y: min(seg_dist(x, y, p, q) for p, q in PATH) < half, col)


# ------------------------------------------------------------------ fields


def field_wheat(cv, P, S):
    p0, a, b = WHEAT
    rows = 7

    def col(x, y):
        s, t = local(p0, a, b, x + .5, y + .5)
        f = (t * rows) % 1
        if S == "winter":
            return P["wheat_dk"] if f < 0.3 else pick(x, y, [P["wheat"], P["wheat_hi"]], 20)
        if S == "drought":
            if hsh(x, y, 21) < 0.45:
                return pick(x, y, P["g"], 22)
            return P["wheat_dk"] if f < 0.25 else pick(x, y, [P["wheat"], P["wheat_hi"]], 23)
        if f < 0.18:
            return P["wheat_dk"]
        return P["wheat_hi"] if (x + y // 2) % 3 == 0 else pick(x, y, [P["wheat"], P["wheat_hi"]], 24, [.7, .3])

    cv.poly(corners(p0, a, b), col)
    if S in ("thriving", "drought", "overgrown"):  # stalk tips poking up for volume
        tops = 3 if S == "thriving" else 2
        for i in range(0, 60):
            s = i / 60
            base = add(p0, a, s)
            if hsh(i, 0, 25) < (0.9 if S == "thriving" else 0.5):
                for k in range(1, tops + 1):
                    cv.set(base[0], base[1] - k, P["wheat_hi"] if k == tops else P["wheat"])


def field_crops(cv, P, S, plot, crop, progress=1.0):
    p0, a, b = plot
    rows = 5

    def col(x, y):
        s, t = local(p0, a, b, x + .5, y + .5)
        f = (t * rows) % 1
        if S == "winter":
            return P["soil"] if f < 0.3 and hsh(x, y, 30) < 0.8 else pick(x, y, P["g"], 31)
        if S == "overgrown":
            return pick(x, y, [P["wheat"], P["wheat_dk"], P["soil"], (40, 70, 30)], 32)
        if S == "thriving" and crop == "pumpkin" and hsh(x, y, 35) < 0.3:
            return P["vine"]
        return P["soil_dk"] if f < 0.3 else P["soil"]

    cv.poly(corners(p0, a, b), col)
    cols = 7
    for i in range(rows):
        for j in range(cols):
            cx, cy = add(add(p0, a, (j + .5) / cols), b, (i + .55) / rows)
            ix, iy = int(cx), int(cy)
            if (i * cols + j) >= progress * rows * cols:
                continue
            if S == "thriving" and crop == "pumpkin":
                cv.set(ix - 2, iy - 1, P["vine"])
                cv.set(ix + 2, iy, P["vine"])
                cv.rect(ix - 1, iy - 1, ix + 1, iy, P["pumpkin"])
                cv.set(ix - 1, iy - 1, P["pumpkin_hi"])
                cv.set(ix, iy - 2, P["vine"])
            elif S == "thriving":  # veg garden
                cv.set(ix, iy - 1, P["leaf_hi"])
                cv.set(ix - 1, iy, P["leaf"])
                cv.set(ix + 1, iy, P["leaf"])
                cv.set(ix, iy, pick(ix, iy, [(240, 200, 40), (220, 60, 40), P["leaf_dk"]], 33))
            elif S == "drought" and hsh(i, j, 34) < 0.6:
                cv.line((ix, iy), (ix, iy - 2), P["vine"])
                cv.set(ix + 1, iy - 2, P["wheat_dk"])
            elif S == "overgrown":
                cv.line((ix - 1, iy), (ix + 1, iy - 2), (100, 76, 46))


# ------------------------------------------------------------------ fences


def fence(cv, P, S, p, q, seed=0):
    n = int(abs(q[0] - p[0])) or 1
    for i in range(n + 1):
        x = p[0] + (q[0] - p[0]) * i / n
        y = p[1] + (q[1] - p[1]) * i / n
        broken = S == "overgrown" and hsh(i, seed, 40) < 0.22
        if not broken:
            cv.set(x, y - 2, P["fence"])
            cv.set(x, y - 4, P["fence_hi"])
            if S == "winter":
                cv.set(x, y - 5, (248, 252, 255))
        if i % 4 == 0 and not (S == "overgrown" and hsh(i, seed, 41) < 0.15):
            for k in range(0, 5):
                cv.set(x, y - k, P["fence_dk"] if k else P["fence"])
            if S == "winter":
                cv.set(x, y - 5, (255, 255, 255))
        if S == "overgrown" and hsh(i, seed, 42) < 0.4:
            cv.set(x, y - 1 - int(hsh(i, seed, 43) * 3), (44, 96, 36))


# ------------------------------------------------------------------ trees


def tree(cv, P, S, x, y, r=4.0, seed=0):
    if S in ("drought", "winter") and not (S == "winter" and hsh(x, y, 50) < 0.4):
        bare_tree(cv, P, S, x, y, r, seed)
        return
    if S == "winter":
        evergreen(cv, x, y, r)
        return
    cv.rect(x, y - 3, x + 1, y, P["trunk"])
    cx, cy = x + 0.5, y - 3 - r * 0.7

    def col(px, py):
        d = ((px - cx) + (py - cy)) / (2 * r)
        c = mix(P["leaf_hi"], P["leaf_dk"], d + 0.5 + (hsh(px, py, 51) - 0.5) * 0.5)
        if P["fruit"] and hsh(px, py, 52) < 0.08:
            return P["fruit"]
        return c

    cv.ellipse(cx, cy, r, r * 0.85, col)


def bare_tree(cv, P, S, x, y, r, seed):
    top = y - r * 2.2
    cv.line((x, y), (x, top), P["trunk"])
    cv.set(x + 1, y, P["trunk"])

    def branch(px, py, ang, ln, depth):
        if depth == 0 or ln < 1:
            return
        qx, qy = px + math.cos(ang) * ln, py - math.sin(ang) * ln
        cv.line((px, py), (qx, qy), P["trunk"])
        if S == "winter":
            cv.set(qx, qy - 1, (250, 252, 255))
        branch(qx, qy, ang + 0.5, ln * 0.65, depth - 1)
        branch(qx, qy, ang - 0.5, ln * 0.65, depth - 1)

    branch(x, top + 2, math.pi / 2 + 0.6, r * 0.9, 3)
    branch(x, top + 2, math.pi / 2 - 0.6, r * 0.9, 3)
    branch(x, top + 4, math.pi / 2 + 1.0, r * 0.6, 2)


def evergreen(cv, x, y, r):
    cv.rect(x, y - 1, x, y, (80, 60, 44))
    for tier in range(3):
        base = y - 1 - tier * 3
        half = r - tier * 1.2
        for k in range(4):
            w = half * (1 - k / 4)
            for dx in range(int(-w), int(w) + 1):
                snow = k == 3 or (dx == int(-w) or hsh(int(x + dx), base - k, 53) < 0.25)
                cv.set(x + dx, base - k, (240, 246, 252) if snow else (34, 84, 64))


# ------------------------------------------------------------------ barn


def barn(cv, P, S):
    F, Wv, L, h = BARN_F, BARN_W, BARN_L, BARN_H
    G = add(F, Wv)
    up = (0, -h)
    Ft, Gt, GL, GLt = add(F, up), add(G, up), add(G, L), add(add(G, L), up)
    apex = add(add(F, Wv, 0.5), (0, -h - 10))
    apexL = add(apex, L)

    def wall(shade):
        def col(x, y):
            base = P["wall_dk"] if x % 3 == 0 else (P["wall_hi"] if shade else P["wall"])
            if S == "overgrown" and hsh(x, y, 60) < 0.12:
                return (34, 26, 20)
            if S == "drought" and hsh(x, y, 61) < 0.2:
                return mix(base, (210, 190, 160), 0.4)
            return base if shade else mix(base, (0, 0, 0), 0.18)
        return col

    cv.poly([GL, add(GL, (0, 1)), add(G, (0, 1)), G], (0, 0, 0))  # shadow line
    cv.poly([F, G, Gt, apex, Ft], wall(True))
    cv.poly([G, GL, GLt, Gt], wall(False))
    roof(cv, P, S, Gt, GLt, apex, apexL)
    # trims
    for p, q in ((F, Ft), (G, Gt), (GL, GLt)):
        cv.line(p, q, P["trim"])
    cv.line(add(Ft, (-1, 1)), apex, P["roof_dk"], 2)
    cv.line(apex, add(Gt, (1, 1)), P["trim"])
    door(cv, P, S, F, Wv)
    loft = [add(add(F, Wv, s), (0, -dy)) for s, dy in ((0.4, 14), (0.6, 14), (0.6, 19), (0.4, 19))]
    cv.poly(loft, P["wheat"] if S == "thriving" else (40, 28, 22))
    for i in range(4):
        cv.line(loft[i], loft[(i + 1) % 4], P["trim"])
    for s in (0.3, 0.7):
        win = [add(add(G, L, s + ds), (0, -dy)) for ds, dy in ((0, 5), (0.12, 5), (0.12, 9), (0, 9))]
        cv.poly(win, (40, 30, 30) if S != "winter" else (240, 200, 110))
        for i in range(4):
            cv.line(win[i], win[(i + 1) % 4], P["trim"])
    topper(cv, P, S, add(apex, L, 0.45))


def door(cv, P, S, F, Wv):
    q = [add(add(F, Wv, s), (0, -dy)) for s, dy in ((0.27, 0), (0.73, 0), (0.73, 9), (0.27, 9))]
    cv.poly(q, P["wall_dk"] if S != "overgrown" else (30, 24, 18))
    if S == "overgrown":
        cv.line(q[0], q[3], P["trim"])
        return
    for i in range(4):
        cv.line(q[i], q[(i + 1) % 4], P["trim"])
    m_bot = ((q[0][0] + q[1][0]) / 2, (q[0][1] + q[1][1]) / 2)
    m_top = ((q[3][0] + q[2][0]) / 2, (q[3][1] + q[2][1]) / 2)
    cv.line(m_bot, m_top, P["trim"])
    for a_, b_ in ((q[0], m_top), (q[3], m_bot), (m_bot, q[2]), (m_top, q[1])):
        cv.line(a_, b_, P["trim"])


def roof(cv, P, S, Gt, GLt, apex, apexL):
    pts = [add(Gt, (0, 1)), add(GLt, (1, 1)), add(apexL, (1, 0)), apex]
    eave_to_ridge = (apex[0] - Gt[0], apex[1] - Gt[1])

    def col(x, y):
        _, v = local(Gt, (GLt[0] - Gt[0], GLt[1] - Gt[1]), eave_to_ridge, x + .5, y + .5)
        band = int(v * 7)
        c = P["roof_hi"] if band % 2 else P["roof"]
        if (v * 7) % 1 < 0.2:
            c = P["roof_dk"]
        if S == "winter":
            c = mix(P["roof_hi"], (170, 192, 222), v * 0.8 + hsh(x, y, 70) * 0.15 + (0.5 if v < 0.1 else 0))
        if S == "drought" and x % 4 == 0 and hsh(x, 0, 71) < 0.5:
            c = mix(c, (150, 90, 50), 0.6)
        if S == "overgrown":
            if hsh(x // 3, y // 2, 72) < 0.18:
                return (24, 20, 16)
            if hsh(x, y, 73) < 0.35:
                return pick(x, y, [(70, 120, 50), (96, 140, 60)], 74)
        return c

    cv.poly(pts, col)
    if S == "winter":  # icicles
        n = int(GLt[0] - Gt[0])
        for i in range(0, n, 2):
            x = Gt[0] + i
            y = Gt[1] + (GLt[1] - Gt[1]) * i / n + 2
            for k in range(1 + int(hsh(i, 0, 75) * 2)):
                cv.set(x, y + k, (200, 228, 248))


def topper(cv, P, S, at):
    x, y = int(at[0]), int(at[1])
    if S in ("drought", "winter"):
        cv.rect(x, y - 4, x + 1, y, (130, 60, 48))
        cv.set(x, y - 5, (90, 80, 76))
        cv.set(x + 1, y - 5, (90, 80, 76))
        smoke(cv, x, y - 7)
        return
    if S == "overgrown":
        cv.line((x - 1, y), (x + 2, y - 3), P["wall_dk"])
        return
    cv.rect(x - 1, y - 3, x + 2, y, P["wall"])
    cv.set(x, y - 2, P["trim"])
    cv.set(x + 1, y - 2, P["trim"])
    cv.line((x - 2, y - 4), (x + 3, y - 4), P["roof_dk"])
    cv.line((x - 1, y - 5), (x + 2, y - 5), P["roof"])
    cv.set(x + 1, y - 7, (60, 60, 60))
    cv.set(x + 1, y - 6, (60, 60, 60))


def smoke(cv, x, y):
    for i in range(6):
        cx, cy = x + i * 1.6, y - i * 2.2
        r = 1.2 + i * 0.35
        cv.fill(lambda px, py: (px - cx) ** 2 + (py - cy) ** 2 <= r * r,
                lambda px, py: mix(cv.get(px, py), (226, 226, 230), 0.75 - i * 0.1),
                (cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1))


def silo(cv, P, S, x=66, top=12, bottom=33, r=4):
    def col(px, py):
        k = (px + 0.5 - x) / r
        c = mix(P["silo_hi"], mix(P["silo"], (0, 0, 0), 0.35), (k + 1) / 2)
        if (py - top) % 5 == 0:
            c = mix(c, (0, 0, 0), 0.2)
        if S == "overgrown" and hsh(px, py, 80) < 0.2:
            return (70, 110, 50)
        if S == "drought" and hsh(px, py, 81) < 0.15:
            return (150, 100, 60)
        return c

    cv.rect(x - r, top, x + r - 1, bottom, col)
    cv.ellipse(x, top, r, 3, lambda px, py: mix(
        (250, 250, 255) if S == "winter" else P["dome"], (90, 90, 96), (px - x + r) / (2 * r) * 0.7))


# ------------------------------------------------------------------ props


def tractor(cv, x, y, body, rusty=False):
    dark = (36, 32, 30)
    cv.rect(x, y - 4, x + 6, y - 2, body)
    cv.rect(x + 6, y - 3, x + 8, y - 2, mix(body, (0, 0, 0), 0.2))
    cv.rect(x + 1, y - 8, x + 3, y - 5, dark)
    cv.rect(x + 2, y - 7, x + 2, y - 6, (150, 190, 210) if not rusty else (60, 50, 40))
    cv.line((x + 1, y - 8), (x + 3, y - 8), body)
    cv.set(x + 7, y - 5, dark)
    cv.ellipse(x + 1.5, y - 0.5, 2.3, 2.3, dark)
    cv.set(x + 1, y - 1, (130, 130, 130))
    cv.ellipse(x + 7.5, y + 0.2, 1.3, 1.3, dark)
    if rusty:
        for i in range(8):
            cv.set(x + i, y - 3 - (i % 2), (150, 80, 46) if i % 3 else (60, 100, 40))


def bale(cv, x, y, P, round_=False):
    if round_:
        cv.ellipse(x, y, 3, 2.6, lambda px, py: mix(P["wheat_hi"], P["wheat_dk"],
                                                      math.hypot(px - x, py - y) / 3))
        cv.set(x, y, P["wheat_dk"])
        return
    cv.rect(x, y - 1, x + 4, y, P["wheat"])
    cv.rect(x + 1, y - 2, x + 5, y - 2, P["wheat_hi"])
    cv.rect(x + 5, y - 1, x + 5, y, P["wheat_dk"])


def cow(cv, x, y):
    cv.rect(x, y - 2, x + 3, y - 1, (250, 250, 246))
    cv.set(x + 1, y - 2, (30, 30, 30))
    cv.set(x + 3, y - 1, (30, 30, 30))
    cv.set(x + 4, y - 2, (40, 36, 34))
    cv.set(x + 4, y - 3, (240, 190, 180))
    cv.set(x, y, (40, 36, 34))
    cv.set(x + 3, y, (40, 36, 34))


def sheep(cv, x, y):
    cv.rect(x, y - 2, x + 2, y - 1, (244, 240, 230))
    cv.set(x + 1, y - 3, (255, 255, 250))
    cv.set(x + 3, y - 2, (60, 56, 56))
    cv.set(x, y, (60, 56, 56))
    cv.set(x + 2, y, (60, 56, 56))


def chicken(cv, x, y, brown=False):
    body = (178, 96, 48) if brown else (250, 250, 250)
    cv.rect(x, y - 1, x + 1, y - 1, body)
    cv.set(x + 1, y - 2, body)
    cv.set(x + 1, y - 3, (220, 40, 40))
    cv.set(x + 2, y - 2, (240, 180, 40))


def sunflower(cv, x, y):
    cv.line((x, y), (x, y - 4), (60, 130, 40))
    cv.set(x - 1, y - 2, (80, 160, 50))
    for dx, dy in ((-1, -5), (1, -5), (0, -6), (0, -4), (-1, -6), (1, -6), (-1, -4), (1, -4)):
        cv.set(x + dx, y + dy, (250, 200, 30))
    cv.set(x, y - 5, (110, 60, 20))


def stove(cv, x, y):
    cv.rect(x, y - 4, x + 3, y, (40, 40, 44))
    cv.rect(x + 1, y - 2, x + 2, y - 1, (250, 140, 40))
    cv.rect(x + 1, y - 9, x + 1, y - 5, (60, 60, 66))
    smoke(cv, x + 1, y - 11)
    for i in range(3):
        cv.ellipse(x + 6 + i * 2, y - 1, 1, 1, (130, 90, 60))


def pond(cv, P, S):
    def inside(x, y):
        return any(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1 for cx, cy, rx, ry in POND)

    seeds = [(hsh(i, 0, 90) * 34 + 12, hsh(i, 1, 90) * 12 + 58) for i in range(14)]

    def col(x, y):
        edge = not all(inside(x + .5 + dx, y + .5 + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if edge:
            return P["bank"] if S != "drought" else P["water_dk"]
        if S == "drought":
            d = sorted(math.hypot(x - sx, (y - sy) * 1.6) for sx, sy in seeds)
            return P["water_dk"] if d[1] - d[0] < 0.9 else pick(x, y, [P["water"], P["water_hi"]], 91)
        if S == "overgrown":
            if hsh(x // 2, y, 92) < 0.25:
                return (96, 160, 70)
            return pick(x, y, [P["water"], P["water_dk"], P["water_hi"]], 93, [.6, .3, .1])
        if S == "winter":
            return P["water_hi"] if hsh(x, y, 94) < 0.3 else P["water"]
        if (x + y * 3) % 7 == 0 and hsh(x, y, 95) < 0.6:
            return P["water_hi"]
        return P["water"] if y > 63 else mix(P["water"], P["water_dk"], 0.4)

    cv.fill(inside, col, (0, 54, 50, 76))
    if S == "winter":
        for i in range(5):
            x, y = 20 + i * 4, 60 + (i % 2) * 3
            for _ in range(4):
                nx, ny = x + (hsh(int(x), i, 96) - 0.3) * 6, y + (hsh(i, int(y), 97) - 0.5) * 4
                if inside(nx, ny):
                    cv.line((x, y), (nx, ny), (252, 254, 255))
                x, y = nx, ny
    if S == "thriving":
        for x, y in ((14, 64), (40, 60), (44, 66)):
            cv.line((x, y), (x, y - 3), (60, 130, 50))


# ------------------------------------------------------------------ scene


def render_scene(S: str, progress: float = 1.0, herd: int = 3) -> Canvas:
    """progress 0..1 fills the crop plots; herd 0..3 sets how many animals roam."""
    P = PALETTES[S]
    cv = Canvas(W, H)
    ground(cv, P, S)
    path(cv, P, S)
    for i, (x, y) in enumerate(RIDGE_TREES):
        tree(cv, P, S, x, y, 4.5 if S != "overgrown" else 5.5, i)
    if S == "overgrown":
        for x, y in ((14, 18), (2, 28), (118, 36), (102, 64), (60, 14)):
            tree(cv, P, S, x, y, 5)
    p0, a, b = PUMPKIN
    fence(cv, P, S, p0, add(p0, a), 1)
    fence(cv, P, S, add(p0, a), add(add(p0, a), b), 2)
    field_crops(cv, P, S, PUMPKIN, "pumpkin", progress)
    fence(cv, P, S, p0, add(p0, b), 3)
    fence(cv, P, S, add(p0, b), add(add(p0, a), b), 4)
    silo(cv, P, S)
    barn(cv, P, S)
    fence(cv, P, S, V(102, 40), V(120, 31), 5)
    p0, a, b = WHEAT
    field_wheat(cv, P, S)
    fence(cv, P, S, add(p0, b), add(add(p0, a), b), 6)
    fence(cv, P, S, p0, add(p0, b), 7)
    fence(cv, P, S, add(p0, a), add(add(p0, a), b), 8)
    pond(cv, P, S)
    fence(cv, P, S, V(44, 54), V(58, 61), 9)
    fence(cv, P, S, V(58, 61), V(40, 70), 10)
    field_crops(cv, P, S, GARDEN, "veg", progress)
    fence(cv, P, S, V(80, 74), V(120, 54), 11)
    props(cv, P, S, herd)
    for i, (x, y) in enumerate(SIDE_TREES):
        tree(cv, P, S, x, y, 4.5, 20 + i)
    weather(cv, S)
    return cv


def props(cv, P, S, herd=3):
    if S == "thriving":
        tractor(cv, 50, 48, (204, 40, 36))
        herd = max(0, min(3, herd))
        for x, y in ((90, 55), (96, 58)):
            bale(cv, x, y, P)
        bale(cv, 104, 62, P, round_=True)
        for x, y in ((8, 30), (112, 46), (64, 44))[:herd]:
            cow(cv, x, y)
        for x, y in ((62, 52), (30, 54), (46, 60), (70, 50))[:herd + 1]:
            sheep(cv, x, y)
        for i, (x, y) in enumerate(((78, 56), (84, 60), (74, 61), (36, 50), (20, 36))[:herd + 2]):
            chicken(cv, x, y, i % 2 == 0)
        for x, y in ((112, 64), (116, 66), (108, 67)):
            sunflower(cv, x, y)
    elif S == "drought":
        for x, y in ((86, 56), (100, 60), (60, 30), (112, 66)):
            bale(cv, x, y, P, round_=True)
    elif S == "overgrown":
        tractor(cv, 50, 48, (150, 80, 46), rusty=True)
        tractor(cv, 98, 62, (110, 70, 44), rusty=True)
        for x, y in ((86, 58), (90, 61)):
            cv.rect(x, y - 2, x + 3, y, (96, 66, 40))
            cv.line((x, y - 2), (x + 3, y), (60, 40, 24))
        for i in range(260):  # tall weeds everywhere
            x, y = int(hsh(i, 2, 99) * W), int(hsh(i, 3, 99) * H)
            cv.line((x, y), (x + (i % 3) - 1, y - 2), pick(x, y, [(46, 100, 36), (78, 120, 44), (30, 70, 28)], 98))
    elif S == "winter":
        stove(cv, 104, 66)
        for i in range(3):
            cv.rect(92 + i * 2, 55 - i, 94 + i * 2, 56 - i, (120, 84, 56))
            cv.set(93 + i * 2, 54 - i, (250, 252, 255))


def weather(cv, S):
    if S == "winter":
        for i in range(140):
            x, y = hsh(i, 5, 110) * W, hsh(i, 6, 110) * H
            cv.blend(x, y, (255, 255, 255), 0.85)
    if S == "drought":  # heat haze: warm tint
        for y in range(H):
            for x in range(W):
                cv.px[y][x] = mix(cv.px[y][x], (240, 200, 130), 0.08)


# ------------------------------------------------------------------ frame


def crossfade(a: Canvas, b: Canvas, t: float) -> Canvas:
    out = Canvas(a.w, a.h)
    out.px = [[mix(pa, pb, t) for pa, pb in zip(ra, rb)] for ra, rb in zip(a.px, b.px)]
    return out


def fg(c):
    return f"\x1b[38;2;{c[0]};{c[1]};{c[2]}m"


def bg(c):
    return f"\x1b[48;2;{c[0]};{c[1]};{c[2]}m"


RESET = "\x1b[0m"


def panel(S: str, title: str | None = None, canvas: Canvas | None = None) -> list[str]:
    acc = ACCENT[S]
    cv = canvas or render_scene(S)
    art = cv.to_ansi()
    inner = cv.w
    t = f" {title or TITLES[S]} "
    side = (inner - len(t)) // 2
    dots = "▒" * 1
    head = (bg(SLATE) + fg(mix(acc, SLATE, 0.55)) + dots * side + fg(acc) + "\x1b[1m" + t
            + "\x1b[22m" + fg(mix(acc, SLATE, 0.55)) + dots * (inner - side - len(t)))
    edge = bg(SLATE) + fg(acc)
    lines = [edge + "┌" + "─" * inner + "┐" + RESET,
             edge + "│" + head + edge + "│" + RESET]
    lines += [edge + "│" + RESET + row + edge + "│" + RESET for row in art]
    lines.append(edge + "└" + "─" * inner + "┘" + RESET)
    return lines


def monitor(panels: list[list[str]], per_row: int) -> list[str]:
    width = per_row * (W + 2) + (per_row - 1) + 4
    status = " ░░░ ISLAND/FARM-OS  │ ▓▓▓▓▓▓▓▓░░ │ LINK OK "
    out = [bg(SLATE) + fg((110, 170, 90)) + status.ljust(width) + RESET]
    for r in range(0, len(panels), per_row):
        group = panels[r:r + per_row]
        for row in zip(*group):
            out.append(bg(SLATE) + "  " + (bg(SLATE) + " ").join(row) + bg(SLATE) + "  " + RESET)
    out.append(bg(SLATE) + " " * width + RESET)
    return out


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    which = args[0] if args else "all"
    if which not in STATES + ("all",):
        print(f"usage: pixelfarm.py [{'|'.join(STATES)}|all] [--png out.png]", file=sys.stderr)
        return 2
    if "--png" in argv:
        i = argv.index("--png")
        target = argv[i + 1] if i + 1 < len(argv) else "farm.png"
        states = STATES if which == "all" else (which,)
        for s in states:
            path_ = target if len(states) == 1 else target.replace(".png", f"-{s}.png")
            render_scene(s).to_png(path_)
            print(path_)
        return 0
    states = STATES if which == "all" else (which,)
    panels = [panel(s) for s in states]
    cols = shutil.get_terminal_size((130, 40)).columns
    per_row = 2 if len(panels) > 1 and cols >= 2 * (W + 2) + 5 else 1
    print("\n".join(monitor(panels, per_row)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
