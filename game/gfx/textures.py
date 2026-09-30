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


# ---------------------------------------------------------------------------
# Map textures (forest / backrooms).  Mostly luminance detail around ~0.8 so
# vertex colours can tint them; created lazily by TextureBank.get().
# ---------------------------------------------------------------------------
def _gray(name, v, mipmap=True, tint=(1.0, 1.0, 1.0)):
    img = np.zeros(v.shape + (4,))
    for i in range(3):
        img[..., i] = v * tint[i]
    img[..., 3] = 1
    return _to_texture(name, img, mipmap)


def grass(size=256):
    """Tiles every 4 m: green with dry patches and blade speckle."""
    rng = np.random.default_rng(21)
    patches = fbm(size, 4, 4, rng)
    blades = rng.random((size, size))
    detail = fbm(size, 32, 2, rng)
    v = 0.55 + 0.35 * detail + 0.25 * (blades - 0.5)
    dry = np.clip((patches - 0.52) * 4.0, 0, 1)
    img = np.zeros((size, size, 4))
    img[..., 0] = v * (0.30 + 0.35 * dry)
    img[..., 1] = v * (0.62 + 0.05 * dry)
    img[..., 2] = v * (0.18 + 0.05 * dry)
    img[..., 3] = 1
    return _to_texture("grass", img)


def bark(size=128):
    rng = np.random.default_rng(22)
    y, x = np.mgrid[0:size, 0:size]
    n = fbm(size, 8, 3, rng)
    ridges = 0.5 + 0.5 * np.sin(x * (np.pi * 2 * 10 / size) + n * 7.0)
    v = 0.45 + 0.4 * ridges * (0.7 + 0.3 * fbm(size, 16, 2, rng))
    return _gray("bark", v)


def foliage(size=128):
    rng = np.random.default_rng(23)
    n = fbm(size, 16, 3, rng)
    speck = rng.random((size, size))
    v = 0.55 + 0.4 * n + 0.2 * (speck - 0.5)
    return _gray("foliage", v)


def wood(size=128):
    """Horizontal log / plank grain."""
    rng = np.random.default_rng(24)
    y, x = np.mgrid[0:size, 0:size]
    n = fbm(size, 4, 4, rng)
    grain = 0.5 + 0.5 * np.sin(y * (np.pi * 2 * 6 / size) + n * 9.0)
    seam = (y % (size // 4)) < 2
    v = 0.6 + 0.3 * grain
    v = np.where(seam, 0.3, v)
    return _gray("wood", v)


def rock(size=128):
    rng = np.random.default_rng(25)
    n = fbm(size, 6, 5, rng)
    cracks = np.abs(fbm(size, 10, 3, rng) - 0.5) < 0.02
    v = 0.5 + 0.45 * n
    v = np.where(cracks, v * 0.55, v)
    return _gray("rock", v)


def carpet(size=256):
    """Damp office carpet, tiles every 4 m."""
    rng = np.random.default_rng(26)
    fibre = rng.random((size, size))
    n = fbm(size, 8, 4, rng)
    damp = np.clip((fbm(size, 3, 4, rng) - 0.55) * 3.0, 0, 1)
    v = (0.72 + 0.18 * n + 0.14 * (fibre - 0.5)) * (1.0 - 0.3 * damp)
    return _gray("carpet", v)


def wallpaper(size=256):
    """Mono-yellow wallpaper: faint vertical stripes with a diamond motif, grime at the bottom.
    One tile = 2 m wide, 4 m tall (v runs up the wall)."""
    rng = np.random.default_rng(27)
    y, x = np.mgrid[0:size, 0:size]
    stripe = 0.5 + 0.5 * np.cos(x * (np.pi * 2 * 8 / size))
    dx = np.abs(((x % (size // 8)) - size / 16) / (size / 16))
    dy = np.abs(((y % (size // 8)) - size / 16) / (size / 16))
    diamond = (np.abs((dx + dy) - 0.8) < 0.12).astype(float)
    n = fbm(size, 4, 4, rng)
    v = 0.82 + 0.06 * stripe + 0.07 * diamond - 0.12 * n
    # bottom of the texture is the bottom of the wall (row 0 is the top in numpy)
    grime = np.clip((y / size - 0.8) * 4.0, 0, 1) * (0.3 + 0.4 * n)
    v = v * (1.0 - grime * 0.45)
    return _gray("wallpaper", v)


def ceiling_tiles(size=128):
    """Drop-ceiling tiles, 2 x 2 tiles per texture (tile = 0.6 m)."""
    rng = np.random.default_rng(28)
    y, x = np.mgrid[0:size, 0:size]
    half = size // 2
    edge = ((x % half) < 3) | ((y % half) < 3)
    pits = rng.random((size, size)) < 0.04
    n = fbm(size, 8, 3, rng)
    v = 0.78 + 0.12 * n
    v = np.where(pits, v * 0.8, v)
    v = np.where(edge, 0.55, v)
    return _gray("ceiling", v)


class TextureBank:
    """Create all procedural textures once."""

    def __init__(self):
        self.white = white()
        self.wall = wall_panels()
        self.metal = metal()
        self.floor = floor()
        self.stripes = hazard_stripes()
        self.glow = radial_glow()
        self._lazy = {}

    _MAKERS = {"grass": grass, "bark": bark, "foliage": foliage, "wood": wood, "rock": rock,
               "carpet": carpet, "wallpaper": wallpaper, "ceiling": ceiling_tiles}

    def get(self, name):
        """Map textures are only generated the first time a map needs them."""
        tex = self._lazy.get(name)
        if tex is None:
            tex = self._lazy[name] = self._MAKERS[name]()
        return tex
