"""Fonts, colours and small drawing helpers shared by HUD and menus."""

import logging
import os

import numpy as np
from panda3d.core import (CardMaker, Filename, NodePath, SamplerState, TextNode, Texture,
                          TransparencyAttrib)

from .. import i18n

log = logging.getLogger("ui")

CYAN = (0.15, 0.95, 1.0, 1)
CYAN_DIM = (0.08, 0.45, 0.55, 1)
WHITE = (0.92, 0.97, 1.0, 1)
GREY = (0.55, 0.62, 0.68, 1)
RED = (1.0, 0.28, 0.3, 1)
ORANGE = (1.0, 0.6, 0.2, 1)
GREEN = (0.3, 1.0, 0.6, 1)
GOLD = (1.0, 0.85, 0.35, 1)
PANEL = (0.01, 0.03, 0.045, 0.82)
PANEL_LIGHT = (0.03, 0.09, 0.12, 0.9)

def _real_case(path):
    """Return ``path`` with the on-disk letter case (Panda's VFS is case-sensitive)."""
    path = os.path.abspath(path)
    drive, rest = os.path.splitdrive(path)
    cur = drive + os.sep
    for part in [p for p in rest.split(os.sep) if p]:
        try:
            match = next((e for e in os.listdir(cur) if e.lower() == part.lower()), part)
        except OSError:
            match = part
        cur = os.path.join(cur, match)
    return cur


WIN_FONTS = _real_case(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
# (latin, hebrew-capable) candidates per role
FONT_CANDIDATES = {
    "display": (["bahnschrift.ttf", "segoeuib.ttf", "arialbd.ttf"], ["segoeuib.ttf", "arialbd.ttf"]),
    "ui": (["bahnschrift.ttf", "segoeui.ttf", "arial.ttf"], ["segoeui.ttf", "arial.ttf"]),
    "mono": (["consola.ttf", "cour.ttf"], ["segoeui.ttf", "arial.ttf"]),
}


class Fonts:
    def __init__(self, loader):
        self.loader = loader
        self.cache = {}
        self.default = TextNode.getDefaultFont()

    def _load(self, fname, bold=False):
        key = fname
        if key in self.cache:
            return self.cache[key]
        path = _real_case(os.path.join(WIN_FONTS, fname))
        font = None
        if os.path.exists(path):
            try:
                font = self.loader.loadFont(Filename.fromOsSpecific(path).getFullpath())
                if font is not None and font.isValid():
                    font.setPixelsPerUnit(72)
                    font.setPageSize(1024, 1024)
                    font.setMinfilter(SamplerState.FT_linear_mipmap_linear)
                    font.setMagfilter(SamplerState.FT_linear)
                else:
                    font = None
            except Exception:
                log.exception("font load failed: %s", path)
                font = None
        self.cache[key] = font
        return font

    def get(self, role="ui"):
        latin, hebrew = FONT_CANDIDATES.get(role, FONT_CANDIDATES["ui"])
        names = hebrew if i18n.is_rtl() else latin
        for n in names:
            f = self._load(n)
            if f is not None:
                return f
        return self.default


def card(parent, x0, x1, y0, y1, color, name="card"):
    cm = CardMaker(name)
    cm.setFrame(x0, x1, y0, y1)
    n = parent.attachNewNode(cm.generate())
    n.setColor(*color)
    n.setTransparency(TransparencyAttrib.M_alpha)
    return n


def text(parent, s, pos=(0, 0), scale=0.05, color=WHITE, align="left", font=None, shadow=True,
         wordwrap=None, name="text"):
    tn = TextNode(name)
    tn.setText(s)
    if font is not None:
        tn.setFont(font)
    a = {"left": TextNode.ALeft, "right": TextNode.ARight, "center": TextNode.ACenter}[align]
    tn.setAlign(a)
    tn.setTextColor(*color)
    if shadow:
        tn.setShadow(0.06, 0.06)
        tn.setShadowColor(0, 0, 0, 0.8)
    if wordwrap and not i18n.is_rtl():
        tn.setWordwrap(wordwrap)   # RTL text is pre-wrapped by i18n.t(_wrap=...)
    n = parent.attachNewNode(tn)
    n.setPos(pos[0], 0, pos[1])
    n.setScale(scale)
    n.setTransparency(TransparencyAttrib.M_alpha)
    return n


def set_text(np_, s):
    np_.node().setText(s)


def ui_align(default="left"):
    """Mirror left/right alignment for RTL languages."""
    if i18n.is_rtl():
        return {"left": "right", "right": "left"}.get(default, default)
    return default


def mx(x):
    """Mirror an x coordinate for RTL layouts."""
    return -x if i18n.is_rtl() else x


# ---------------------------------------------------------------------------
# generated overlay textures
# ---------------------------------------------------------------------------
def _tex(name, rgba):
    h, w, _ = rgba.shape
    data = (np.clip(rgba, 0, 1) * 255).astype(np.uint8)[::-1, :, [2, 1, 0, 3]]
    t = Texture(name)
    t.setup2dTexture(w, h, Texture.T_unsigned_byte, Texture.F_rgba8)
    t.setRamImage(np.ascontiguousarray(data).tobytes())
    t.setMinfilter(SamplerState.FT_linear)
    t.setMagfilter(SamplerState.FT_linear)
    t.setWrapU(SamplerState.WM_clamp)
    t.setWrapV(SamplerState.WM_clamp)
    return t


def arc_texture(size=128):
    """Damage-direction wedge: bright arc at the top, fading."""
    y, x = np.mgrid[0:size, 0:size]
    cx = cy = size / 2 - 0.5
    dx = (x - cx) / (size / 2)
    dy = (cy - y) / (size / 2)
    r = np.sqrt(dx * dx + dy * dy)
    ang = np.degrees(np.arctan2(dx, dy))
    band = np.exp(-((r - 0.85) ** 2) / 0.004)
    wedge = np.clip(1 - np.abs(ang) / 28.0, 0, 1)
    a = band * wedge
    img = np.ones((size, size, 4))
    img[..., 3] = a
    return _tex("arc", img)


def ring_texture(size=128, thickness=0.08):
    y, x = np.mgrid[0:size, 0:size]
    c = size / 2 - 0.5
    r = np.sqrt((x - c) ** 2 + (y - c) ** 2) / (size / 2)
    a = np.exp(-((r - 0.9) ** 2) / (thickness ** 2 * 0.2))
    img = np.ones((size, size, 4))
    img[..., 3] = np.clip(a, 0, 1)
    return _tex("ring", img)


def vignette_texture(size=256):
    y, x = np.mgrid[0:size, 0:size]
    c = size / 2 - 0.5
    r = np.sqrt((x - c) ** 2 + (y - c) ** 2) / (size / 2)
    a = np.clip((r - 0.55) / 0.6, 0, 1) ** 1.5
    img = np.ones((size, size, 4))
    img[..., 3] = a
    return _tex("vignette", img)


def scope_texture(size=512):
    y, x = np.mgrid[0:size, 0:size]
    c = size / 2 - 0.5
    r = np.sqrt((x - c) ** 2 + (y - c) ** 2) / (size / 2)
    img = np.zeros((size, size, 4))
    edge = np.clip((r - 0.9) / 0.04, 0, 1)
    img[..., 3] = edge
    # reticle lines
    line = ((np.abs(x - c) < 1.0) | (np.abs(y - c) < 1.0)) & (r < 0.9) & (r > 0.04)
    ticks = (np.abs(y - c) < 5) & (np.abs(x - c) % 40 < 1.5) & (r < 0.6)
    img[..., 0][line | ticks] = 0.1
    img[..., 1][line | ticks] = 1.0
    img[..., 2][line | ticks] = 1.0
    img[..., 3][line | ticks] = 0.85
    return _tex("scope", img)


def logo_glow_texture(w=512, h=128):
    y, x = np.mgrid[0:h, 0:w]
    dx = (x - w / 2) / (w / 2)
    dy = (y - h / 2) / (h / 2)
    a = np.exp(-(dx * dx * 1.2 + dy * dy * 3.0) * 2.0)
    img = np.ones((h, w, 4))
    img[..., 3] = a
    return _tex("logo_glow", img)


class UITextures:
    def __init__(self):
        self.arc = arc_texture()
        self.ring = ring_texture()
        self.vignette = vignette_texture()
        self.scope = scope_texture()
        self.glow = logo_glow_texture()


def textured_card(parent, tex, x0, x1, y0, y1, color=(1, 1, 1, 1)):
    n = card(parent, x0, x1, y0, y1, color)
    n.setTexture(tex)
    return n


def empty(parent, name="node"):
    return parent.attachNewNode(name) if parent is not None else NodePath(name)
