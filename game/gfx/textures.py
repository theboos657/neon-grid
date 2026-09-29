"""Procedural textures generated with numpy at startup (no image assets)."""

import numpy as np
from panda3d.core import SamplerState, Texture

_rng = np.random.default_rng(1337)


def _to_texture(name, rgba, mipmap=True):
    """rgba: float array (h, w, 4) in 0..1 -> Panda Texture."""
    h, w, _ = rgba.shape
    data = (np.clip(rgba, 0, 1) * 255).astype(np.uint8)
    # Panda expects BGRA row order bottom-to-top
    data = data[::-1, :, [2, 1, 0, 3]]
    tex = Texture(name)
    tex.setup2dTexture(w, h, Texture.T_unsigned_byte, Texture.F_rgba8)
    tex.setRamImage(np.ascontiguousarray(data).tobytes())
    tex.setWrapU(SamplerState.WM_repeat)
    tex.setWrapV(SamplerState.WM_repeat)
    if mipmap:
        tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
        tex.setAnisotropicDegree(8)
    else:
        tex.setMinfilter(SamplerState.FT_linear)
    tex.setMagfilter(SamplerState.FT_linear)
    return tex


def _value_noise(size, cells, rng):
    """Tileable smooth value noise in 0..1."""
    grid = rng.random((cells, cells))
    x = np.linspace(0, cells, size, endpoint=False)
    xi = x.astype(int)
    xf = x - xi
    xf = xf * xf * (3 - 2 * xf)
    x0 = xi % cells
    x1 = (xi + 1) % cells
    # bilinear with smoothstep weights
    g00 = grid[np.ix_(x0, x0)]
    g10 = grid[np.ix_(x1, x0)]
    g01 = grid[np.ix_(x0, x1)]
    g11 = grid[np.ix_(x1, x1)]
    wy = xf[:, None]
    wx = xf[None, :]
    a = g00 * (1 - wy) + g10 * wy
    b = g01 * (1 - wy) + g11 * wy
    return a * (1 - wx) + b * wx


def fbm(size, base_cells=4, octaves=5, rng=None):
    rng = rng or _rng
    out = np.zeros((size, size))
    amp = 1.0
    total = 0.0
    cells = base_cells
    for _ in range(octaves):
        out += _value_noise(size, cells, rng) * amp
        total += amp
        amp *= 0.5
        cells *= 2
    return out / total


def white():
    return _to_texture("white", np.ones((4, 4, 4)), mipmap=False)


def wall_panels(size=256):
    """Dark tech panels with seams, bolts and faint grime."""
    n = fbm(size, 4, 5)
    img = np.zeros((size, size, 4))
    base = 0.13 + n * 0.08
    y, x = np.mgrid[0:size, 0:size]
    # panel seams every 1/2 of the tile
    seam = ((x % (size // 2)) < 3) | ((y % (size // 2)) < 3)
    seam2 = ((y % (size // 4)) < 2) & ((x % (size // 2)) > size // 8)
    base = np.where(seam, 0.03, base)
    base = np.where(seam2, base * 0.6, base)
    # small vent slots
    vent = ((y % (size // 2)) > size * 0.36) & ((y % (size // 2)) < size * 0.44) & \
           ((x % 12) < 7) & ((x % (size // 2)) > size * 0.1) & ((x % (size // 2)) < size * 0.4)
    base = np.where(vent, 0.02, base)
    img[..., 0] = base * 0.92
    img[..., 1] = base * 1.0
    img[..., 2] = base * 1.08
    img[..., 3] = 1.0
    return _to_texture("wall_panels", img)


def metal(size=128):
    n = fbm(size, 8, 4)
    img = np.zeros((size, size, 4))
    y, x = np.mgrid[0:size, 0:size]
    brushed = 0.9 + 0.1 * np.sin(y * 0.7 + n * 6)
    v = (0.18 + n * 0.1) * brushed
    edge = ((x < 3) | (x > size - 4) | (y < 3) | (y > size - 4))
    v = np.where(edge, v * 0.4, v)
    img[..., 0] = v
    img[..., 1] = v * 1.02
    img[..., 2] = v * 1.07
    img[..., 3] = 1
    return _to_texture("metal", img)


def floor(size=512):
    """R: wetness (puddles), G: grid lines, B: grime.  One tile = 8 m."""
    wet = fbm(size, 3, 6)
    wet = (wet - wet.min()) / (np.ptp(wet) + 1e-6)
    grime = fbm(size, 16, 3)
    y, x = np.mgrid[0:size, 0:size]
    step = size // 4          # a line every 2 m
    lx = np.minimum(x % step, step - (x % step))
    ly = np.minimum(y % step, step - (y % step))
    grid = np.exp(-(np.minimum(lx, ly) ** 2) / 2.0)
    img = np.zeros((size, size, 4))
    img[..., 0] = wet
    img[..., 1] = grid
    img[..., 2] = grime
    img[..., 3] = 1
    return _to_texture("floor", img)


def hazard_stripes(size=64):
    y, x = np.mgrid[0:size, 0:size]
    s = ((x + y) // (size // 4)) % 2
    img = np.zeros((size, size, 4))
    img[..., 0] = np.where(s == 0, 1.0, 0.05)
    img[..., 1] = np.where(s == 0, 0.75, 0.05)
    img[..., 2] = np.where(s == 0, 0.1, 0.05)
    img[..., 3] = 1
    return _to_texture("stripes", img)


def radial_glow(size=64):
    y, x = np.mgrid[0:size, 0:size]
    d = np.sqrt((x - size / 2 + 0.5) ** 2 + (y - size / 2 + 0.5) ** 2) / (size / 2)
    a = np.clip(1 - d, 0, 1) ** 2
    img = np.ones((size, size, 4))
    img[..., 3] = a
    return _to_texture("glow", img, mipmap=False)


class TextureBank:
    """Create all procedural textures once."""

    def __init__(self):
        self.white = white()
        self.wall = wall_panels()
        self.metal = metal()
        self.floor = floor()
        self.stripes = hazard_stripes()
        self.glow = radial_glow()
