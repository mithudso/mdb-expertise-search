#!/usr/bin/env python3
"""Render the Chrome extension icons (16/32/48/128 px PNG) with no image library.

A teal rounded square with a white magnifier whose lens holds a small speed chevron. Shapes are
signed-distance functions sampled 4x4 per pixel for anti-aliasing; PNGs are written with zlib.

    python scripts/make_chrome_icons.py      # writes editors/chrome/icons/icon{16,32,48,128}.png
"""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "editors" / "chrome" / "icons"
BG = (11, 110, 90)
FG = (255, 255, 255)


def rounded_square(x: float, y: float, r: float) -> float:
    qx, qy = abs(x - 0.5) - (0.5 - r), abs(y - 0.5) - (0.5 - r)
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r


def segment(x, y, ax, ay, bx, by) -> float:
    px, py, vx, vy = x - ax, y - ay, bx - ax, by - ay
    t = max(0.0, min(1.0, (px * vx + py * vy) / (vx * vx + vy * vy)))
    return math.hypot(px - vx * t, py - vy * t)


def glyph(x: float, y: float, size: int) -> float:
    """Distance to the white mark (negative inside)."""
    cx, cy, r = 0.43, 0.43, 0.215
    w = 0.075 if size > 20 else 0.11  # thicker strokes at 16 px
    ring = abs(math.hypot(x - cx, y - cy) - r) - w / 2
    handle = segment(x, y, 0.60, 0.60, 0.80, 0.80) - w * 0.75
    d = min(ring, handle)
    if size >= 32:  # chevron inside the lens: "faster"
        chev = min(segment(x, y, 0.37, 0.35, 0.46, 0.43), segment(x, y, 0.46, 0.43, 0.37, 0.51)) - w * 0.38
        d = min(d, chev)
    return d


def render(size: int) -> bytes:
    ss = 4
    rows = []
    for py in range(size):
        row = bytearray([0])  # filter: none
        for px in range(size):
            cov_bg = cov_fg = 0.0
            for sy in range(ss):
                for sx in range(ss):
                    x = (px + (sx + 0.5) / ss) / size
                    y = (py + (sy + 0.5) / ss) / size
                    if rounded_square(x, y, 0.22) <= 0:
                        cov_bg += 1
                        if glyph(x, y, size) <= 0:
                            cov_fg += 1
            n = ss * ss
            a = cov_bg / n
            f = cov_fg / cov_bg if cov_bg else 0.0
            rgb = [round(BG[i] * (1 - f) + FG[i] * f) for i in range(3)]
            row += bytes(rgb + [round(a * 255)])
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for s in (16, 32, 48, 128):
        (OUT / f"icon{s}.png").write_bytes(render(s))
        print(f"wrote {OUT / f'icon{s}.png'}")


if __name__ == "__main__":
    main()
