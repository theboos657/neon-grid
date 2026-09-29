"""Picture-in-picture scopes.

When the player aims down a magnified scope, a second camera (sitting exactly
at the player's eye) renders the arena with a narrow field of view into an
HDR texture.  That texture is shown on the scope's rear lens on the
first-person weapon, so you really look *through* the scope while the gun,
the scope tube and the unmagnified arena around it stay visible.

The buffer only renders while a scope is in use, so it costs nothing otherwise.
"""

import logging

from panda3d.core import (Camera, FrameBufferProperties, PerspectiveLens, SamplerState,
                          Texture)

from . import shaders

log = logging.getLogger("scope")


class ScopeView:
    def __init__(self, base, quality="high"):
        self.base = base
        self.size = 768 if quality == "high" else 512
        self.tex = Texture("scope_view")
        self.tex.setMinfilter(SamplerState.FT_linear)
        self.tex.setMagfilter(SamplerState.FT_linear)
        self.tex.setWrapU(SamplerState.WM_clamp)
        self.tex.setWrapV(SamplerState.WM_clamp)
        self.buffer = None
        self.cam = None
        self.lens = PerspectiveLens()
        self.lens.setAspectRatio(1.0)
        self.lens.setNearFar(0.1, 400.0)
        self.lens.setFov(20)
        self.active = False
        try:
            fbp = FrameBufferProperties()
            fbp.setFloatColor(True)
            fbp.setRgbaBits(16, 16, 16, 0)
            fbp.setDepthBits(24)
            buf = base.win.makeTextureBuffer("scope", self.size, self.size, self.tex, False, fbp)
            if buf is None:
                buf = base.win.makeTextureBuffer("scope", self.size, self.size, self.tex)
            if buf is None:
                raise RuntimeError("no offscreen buffer")
            buf.setSort(-20)
            buf.setClearColor((0.0, 0.01, 0.015, 1))
            self.buffer = buf
            cam_node = Camera("scope_cam", self.lens)
            # parented to the player camera -> always exactly at the eye
            self.cam = base.camera.attachNewNode(cam_node)
            dr = buf.makeDisplayRegion()
            dr.setCamera(self.cam)
            buf.setActive(False)
        except Exception:
            log.exception("Scope buffer unavailable; scopes fall back to a zoom overlay")
            self.buffer = None

    @property
    def ok(self):
        return self.buffer is not None

    def set_active(self, on, fov=20.0):
        if not self.ok:
            return
        if on != self.active:
            self.buffer.setActive(on)
            self.active = on
        if on:
            self.lens.setFov(max(2.0, fov))


def lens_shader():
    return shaders.get("scopelens")
