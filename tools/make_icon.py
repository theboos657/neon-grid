"""Generates assets/icon.ico and assets/icon.png (neon 'N' on a grid).

    python tools/make_icon.py

Pure numpy + stdlib (PNG encoder included) so it runs without Panda3D.
"""

import os
import struct
import zlib

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def render(size):
    s = size
    y, x = np.mgrid[0:s, 0:s].astype(float) / (s - 1)
    img = np.zeros((s, s, 4))
    # rounded dark tile
    r = 0.18
    dx = np.maximum(np.abs(x - 0.5) - (0.5 - r), 0)
    dy = np.maximum(np.abs(y - 0.5) - (0.5 - r), 0)
    inside = np.sqrt(dx * dx + dy * dy) <= r
    img[..., 0] = 0.01
    img[..., 1] = 0.04
    img[..., 2] = 0.06
    img[..., 3] = inside * 1.0
    # faint grid
    g = ((np.abs((x * 6) % 1 - 0.5) > 0.47) | (np.abs((y * 6) % 1 - 0.5) > 0.47)) & inside
    img[g, 1] += 0.12
    img[g, 2] += 0.15

    def seg(ax, ay, bx, by, w):
        px, py = x - ax, y - ay
        vx, vy = bx - ax, by - ay
        t = np.clip((px * vx + py * vy) / (vx * vx + vy * vy), 0, 1)
        d = np.sqrt((px - vx * t) ** 2 + (py - vy * t) ** 2)
        return d
    d = np.minimum(np.minimum(seg(0.3, 0.75, 0.3, 0.25, 0), seg(0.3, 0.25, 0.7, 0.75, 0)),
                   seg(0.7, 0.75, 0.7, 0.25, 0))
    core = np.clip(1 - d / 0.045, 0, 1)
    glow = np.exp(-(d / 0.09) ** 2) * 0.8
    for c, k in ((0, 0.2), (1, 1.0), (2, 1.0)):
        img[..., c] = np.clip(img[..., c] + glow * k + core * (0.7 + 0.3 * k), 0, 1)
    img[..., 3] = np.maximum(img[..., 3], np.clip(glow, 0, 1) * inside)
    return (img * 255).astype(np.uint8)


def png_bytes(rgba):
    h, w, _ = rgba.shape
    raw = b"".join(b"\x00" + rgba[row].tobytes() for row in range(h))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main():
    out = os.path.join(ROOT, "assets")
    os.makedirs(out, exist_ok=True)
    sizes = [256, 64, 48, 32, 16]
    pngs = [png_bytes(render(s)) for s in sizes]
    with open(os.path.join(out, "icon.png"), "wb") as f:
        f.write(pngs[0])
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    for s, data in zip(sizes, pngs):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    with open(os.path.join(out, "icon.ico"), "wb") as f:
        f.write(header + entries + b"".join(pngs))
    print("wrote assets/icon.ico and assets/icon.png")


if __name__ == "__main__":
    main()
