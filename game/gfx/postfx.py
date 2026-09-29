"""Bloom post-processing and the weapon view-model render layer.

High quality: scene -> HDR float buffer -> bright pass -> two blur levels ->
ACES tonemapped composite.  Low quality: render straight to the window.

The first-person weapon is drawn by a second camera into the *same* scene
buffer after clearing depth, so it never clips into walls and still blooms.
"""

import logging

from direct.filter.FilterManager import FilterManager
from panda3d.core import (Camera, FrameBufferProperties, NodePath, PerspectiveLens, Texture,
                          Vec2)

from . import shaders

log = logging.getLogger("postfx")


class PostFX:
    def __init__(self, base, enable_bloom=True, bloom_strength=1.0):
        self.base = base
        self.enabled = False
        self.manager = None
        self.final_quad = None
        self.vm_region = None
        self.vm_root = NodePath("viewmodel_root")
        self.vm_lens = PerspectiveLens()
        self.vm_lens.setMinFov(54)
        self.vm_lens.setNearFar(0.01, 10.0)
        self.vm_cam = self.vm_root.attachNewNode(Camera("vm_cam", self.vm_lens))
        self.bloom_strength = bloom_strength
        if enable_bloom:
            try:
                self._setup_bloom()
            except Exception:  # driver without float buffers etc.
                log.exception("Bloom setup failed; falling back to direct rendering")
                self._teardown()
        if not self.enabled:
            self._setup_direct_vm()
        self.update_aspect()

    # ------------------------------------------------------------------
    def _setup_bloom(self):
        base = self.base
        self.manager = FilterManager(base.win, base.cam)
        fbp = FrameBufferProperties()
        fbp.setFloatColor(True)
        fbp.setRgbaBits(16, 16, 16, 16)
        fbp.setDepthBits(24)
        self.scene_tex = Texture("scene")
        self.depth_tex = Texture("depth")
        quad = self.manager.renderSceneInto(colortex=self.scene_tex, depthtex=self.depth_tex,
                                            fbprops=fbp)
        if quad is None:
            raise RuntimeError("renderSceneInto failed")
        self.final_quad = quad

        hdr = FrameBufferProperties()
        hdr.setFloatColor(True)
        hdr.setRgbaBits(16, 16, 16, 0)

        def pass_(div, tex_name):
            tex = Texture(tex_name)
            q = self.manager.renderQuadInto(colortex=tex, div=div, fbprops=hdr)
            if q is None:
                raise RuntimeError("renderQuadInto failed")
            return q, tex

        bright_q, bright_t = pass_(2, "bright")
        bright_q.setShader(shaders.get("bright"))
        bright_q.setShaderInput("src", self.scene_tex)
        bright_q.setShaderInput("u_threshold", 0.85)

        # level 1: quarter res
        b1x_q, b1x_t = pass_(4, "b1x")
        b1x_q.setShader(shaders.get("blur"))
        b1x_q.setShaderInput("src", bright_t)
        b1x_q.setShaderInput("u_dir", Vec2(1, 0))
        b1y_q, b1y_t = pass_(4, "b1y")
        b1y_q.setShader(shaders.get("blur"))
        b1y_q.setShaderInput("src", b1x_t)
        b1y_q.setShaderInput("u_dir", Vec2(0, 1))
        # level 2: eighth res, wider spread
        b2x_q, b2x_t = pass_(8, "b2x")
        b2x_q.setShader(shaders.get("blur"))
        b2x_q.setShaderInput("src", b1y_t)
        b2x_q.setShaderInput("u_dir", Vec2(1.6, 0))
        b2y_q, b2y_t = pass_(8, "b2y")
        b2y_q.setShader(shaders.get("blur"))
        b2y_q.setShaderInput("src", b2x_t)
        b2y_q.setShaderInput("u_dir", Vec2(0, 1.6))

        quad.setShader(shaders.get("composite"))
        quad.setShaderInput("scene", self.scene_tex)
        quad.setShaderInput("bloom1", b1y_t)
        quad.setShaderInput("bloom2", b2y_t)
        quad.setShaderInput("u_bloom", self.bloom_strength)
        quad.setShaderInput("u_exposure", 1.0)

        # view-model layer inside the scene buffer
        scene_buf = self.manager.buffers[0]
        self.vm_region = scene_buf.makeDisplayRegion()
        self._config_vm_region()
        self.enabled = True
        log.info("Bloom pipeline active")

    def _setup_direct_vm(self):
        self.vm_region = self.base.win.makeDisplayRegion()
        self._config_vm_region()

    def _config_vm_region(self):
        r = self.vm_region
        r.setSort(20)
        r.setClearDepthActive(True)
        r.setClearColorActive(False)
        r.setCamera(self.vm_cam)

    def _teardown(self):
        if self.manager:
            try:
                self.manager.cleanup()
            except Exception:
                pass
        self.manager = None
        self.enabled = False

    # ------------------------------------------------------------------
    def set_bloom(self, strength):
        self.bloom_strength = strength
        if self.final_quad is not None:
            self.final_quad.setShaderInput("u_bloom", strength)

    def set_exposure(self, e):
        if self.final_quad is not None:
            self.final_quad.setShaderInput("u_exposure", e)

    def update_aspect(self):
        ar = self.base.getAspectRatio()
        self.vm_lens.setAspectRatio(ar)
        self.vm_lens.setMinFov(54)         # constant vertical framing on any aspect ratio

    def destroy(self):
        if self.vm_region is not None:
            win = self.vm_region.getWindow()
            win.removeDisplayRegion(self.vm_region)
            self.vm_region = None
        self._teardown()
