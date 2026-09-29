"""Builds the visual arena: black structures, cyan neon trim, a wet reflective
floor, ceiling light panels with volumetric-looking beams and holographic
signs.

Reflections: the whole ``world`` subtree is instanced a second time under a
node scaled by -1 on Z.  The floor is drawn afterwards, semi-transparent and
without depth writes, so the mirrored world shows through puddles like a wet
floor.  Low quality simply skips the mirror instance.
"""

import math
import random

from panda3d.core import CullFaceAttrib, TextNode, TransparencyAttrib, Vec4

from neon_shared import arena_layout as L

from ..gfx import geom, shaders
from ..gfx.effects import fx_node

CYAN = (0.08, 0.9, 1.0, 1)
CYAN_SOFT = (0.05, 0.55, 0.75, 1)
DEEP = (0.05, 0.3, 1.0, 1)
WHITE_CYAN = (0.6, 1.0, 1.0, 1)
STRUCT = (0.34, 0.37, 0.41, 1)
CRATE = (0.3, 0.32, 0.36, 1)

MAT_STRUCT = Vec4(28.0, 0.35, 0.35, 0.0)
MAT_METAL = Vec4(60.0, 0.9, 0.3, 0.0)
MAT_NEON = Vec4(1.0, 0.0, 0.0, 2.6)
MAT_SCREEN = Vec4(1.0, 0.0, 0.0, 1.4)

SIGN_TEXT = {"sign_grid": "THE  GRID", "sign_arena": "ARENA 07", "sign_sponsor": "NEOTEK",
             "sign_danger": "HIGH VOLTAGE"}


class ArenaVisuals:
    def __init__(self, render, world_root, textures, lights, quality="high", font=None,
                 reflections=True):
        self.render = render
        self.root = world_root
        self.tex = textures
        self.lights = lights
        self.quality = quality
        self.font = font
        self.static_np = world_root.attachNewNode("arena_static")
        self.signs = []
        self.beams = []
        self._build_structures()
        self._build_neon()
        self._build_ceiling()
        self._build_signs()
        self._build_floor(reflections and quality == "high")

    # ------------------------------------------------------------------ structure
    def _build_structures(self):
        walls = geom.MeshBuilder("walls")
        props = geom.MeshBuilder("props")
        for b in L.STATIC_BOXES:
            mn = (b[0], b[1], b[2])
            mx = (b[3], b[4], b[5])
            kind = b[6]
            if kind in ("wall", "pillar", "platform", "step", "ceiling"):
                walls.box(mn, mx, STRUCT, uv_scale=0.25)
            elif kind in ("crate", "cover", "rail", "support", "catwalk"):
                props.box(mn, mx, CRATE, uv_scale=0.5)
        w = walls.node()
        w.reparentTo(self.static_np)
        w.setTexture(self.tex.wall)
        w.setShaderInput("u_mat", MAT_STRUCT)
        p = props.node()
        p.reparentTo(self.static_np)
        p.setTexture(self.tex.metal)
        p.setShaderInput("u_mat", MAT_METAL)

    # ------------------------------------------------------------------ neon trim
    def _build_neon(self):
        mb = geom.MeshBuilder("neon")
        H = L.HALF
        t = 0.06
        # wall trims: floor skirting, mid band, top band
        for z, col, th in ((0.25, CYAN, 0.08), (3.2, CYAN_SOFT, 0.05), (11.4, CYAN, 0.1)):
            mb.box((-H, H - t, z), (H, H, z + th), col)
            mb.box((-H, -H, z), (H, -H + t, z + th), col)
            mb.box((H - t, -H, z), (H, H, z + th), col)
            mb.box((-H, -H, z), (-H + t, H, z + th), col)
        # vertical wall ribs every 8 m (skip where signs hang)
        for i in range(-3, 4):
            x = i * 8.0
            for sgn in (1, -1):
                if abs(x) > 5:
                    mb.box((x - 0.04, sgn * H - (t if sgn > 0 else 0), 0.3),
                           (x + 0.04, sgn * H + (0 if sgn > 0 else t), 11.4), CYAN_SOFT)
                    mb.box((sgn * H - (t if sgn > 0 else 0), x - 0.04, 0.3),
                           (sgn * H + (0 if sgn > 0 else t), x + 0.04, 11.4), CYAN_SOFT)
        # chevron light panels low on the walls
        for i in range(-3, 3):
            x = i * 8.0 + 4.0
            for sgn in (1, -1):
                y = sgn * (H - 0.03)
                mb.box((x - 1.6, y - 0.03, 1.2), (x + 1.6, y + 0.03, 1.35), DEEP)
                mb.box((y - 0.03, x - 1.6, 1.2), (y + 0.03, x + 1.6, 1.35), DEEP)
        for b in L.STATIC_BOXES:
            kind = b[6]
            x0, y0, z0, x1, y1, z1 = b[:6]
            e = 0.05
            if kind == "pillar":
                for (cx, cy) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
                    mb.box((cx - e, cy - e, 0), (cx + e, cy + e, z1), CYAN)
                for z in (1.0, 5.0, 9.0):
                    mb.box((x0 - e, y0 - e, z), (x1 + e, y1 + e, z + 0.12), WHITE_CYAN)
            elif kind in ("crate", "cover", "step", "platform", "catwalk"):
                zc = z1
                col = CYAN if kind != "step" else WHITE_CYAN
                th = 0.04
                mb.box((x0 - e, y0 - e, zc - th), (x1 + e, y0 + e, zc + 0.005), col)
                mb.box((x0 - e, y1 - e, zc - th), (x1 + e, y1 + e, zc + 0.005), col)
                if kind != "step":
                    mb.box((x0 - e, y0 - e, zc - th), (x0 + e, y1 + e, zc + 0.005), col)
                    mb.box((x1 - e, y0 - e, zc - th), (x1 + e, y1 + e, zc + 0.005), col)
                if kind == "crate":
                    # glowing seam across the face
                    mb.box((x0 - e, (y0 + y1) / 2 - 0.03, z0 + 0.1),
                           (x1 + e, (y0 + y1) / 2 + 0.03, z1 - 0.1), CYAN_SOFT)
                if kind == "catwalk":
                    # underside strip lights
                    for yy in range(int(y0) + 2, int(y1) - 1, 4):
                        mb.box((x0 + 0.5, yy - 0.6, z0 - 0.02), (x1 - 0.5, yy + 0.6, z0), CYAN_SOFT)
        # jump pads / floor rings are built by interactables
        n = mb.node()
        n.reparentTo(self.static_np)
        n.setTexture(self.tex.white)
        n.setShaderInput("u_mat", MAT_NEON)

        # static light sources for the rig
        for (x, y) in ((-16, -16), (16, 16), (-16, 16), (16, -16), (0, 0), (0, -24), (0, 24),
                       (-24, 0), (24, 0)):
            self.lights.add_static((x, y, 9.5), (0.15, 0.85, 1.0), 24.0, 0.95)
        for (x, y) in ((-30, -20), (30, 20), (-30, 20), (30, -20)):
            self.lights.add_static((x, y, 2.5), (0.1, 0.5, 1.0), 14.0, 0.9)
        for sx in (1, -1):
            for sy in (1, -1):
                self.lights.add_static((sx * 12.3, sy * 12.3, 1.5), (0.2, 1.0, 1.0), 9.0, 0.8)

    # ------------------------------------------------------------------ ceiling
    def _build_ceiling(self):
        mb = geom.MeshBuilder("ceiling_lights")
        z = L.CEILING_Z - 0.02
        spots = [(-16, -16), (16, 16), (-16, 16), (16, -16), (0, 0), (0, -24), (0, 24),
                 (-24, 0), (24, 0)]
        for (x, y) in spots:
            mb.box((x - 2.2, y - 0.25, z - 0.06), (x + 2.2, y + 0.25, z), WHITE_CYAN, faces="b")
            mb.box((x - 0.25, y - 2.2, z - 0.06), (x + 0.25, y + 2.2, z), WHITE_CYAN, faces="b")
        # long ceiling strips
        for i in range(-3, 4):
            mb.box((-30, i * 8 - 0.05, z - 0.03), (30, i * 8 + 0.05, z), CYAN_SOFT, faces="b")
        n = mb.node()
        n.reparentTo(self.static_np)
        n.setTexture(self.tex.white)
        n.setShaderInput("u_mat", MAT_NEON)
        if self.quality != "high":
            return
        # volumetric beams: soft additive cones under the ceiling lights
        proto = geom.cone_mesh(16)
        for (x, y) in spots:
            c = proto.copyTo(self.root)
            c.setPos(x, y, L.CEILING_Z - 0.1)
            c.setScale(3.2, 3.2, 10.5)
            fx_node(c, 1)
            c.setColorScale(0.06, 0.28, 0.34, 1)
            self.beams.append(c)

    # ------------------------------------------------------------------ holograms
    def _build_signs(self):
        for (x, y, z, hdg, key) in L.HOLO_SIGNS:
            holder = self.root.attachNewNode("sign")
            holder.setPos(x, y, z)
            holder.setH(hdg)
            tn = TextNode("holo")
            tn.setText(SIGN_TEXT.get(key, key))
            tn.setAlign(TextNode.ACenter)
            if self.font:
                tn.setFont(self.font)
            txt = holder.attachNewNode(tn)
            txt.setScale(1.8)
            txt.setPos(0, 0.5, -0.6)
            txt.setH(180)
            fx_node(txt, 3)
            txt.setColorScale(0.25, 1.6, 2.0, 1)
            # frame
            mb = geom.MeshBuilder("frame")
            w = max(6.0, len(SIGN_TEXT.get(key, key)) * 1.15)
            mb.box((-w / 2, 0.3, -1.1), (w / 2, 0.36, -1.02), CYAN)
            mb.box((-w / 2, 0.3, 1.25), (w / 2, 0.36, 1.33), CYAN)
            f = mb.node()
            f.reparentTo(holder)
            f.setTexture(self.tex.white)
            f.setShaderInput("u_mat", MAT_NEON)
            # projector haze
            glow = geom.card(w, 2.6)
            glow.reparentTo(holder)
            glow.setPos(0, 0.45, 0.1)
            fx_node(glow, 5)
            glow.setColorScale(0.02, 0.12, 0.16, 1)
            self.signs.append((holder, txt, random.random() * 10))

    # ------------------------------------------------------------------ floor
    def _build_floor(self, reflections):
        H = L.HALF
        mb = geom.MeshBuilder("floor")
        n = 8
        step = 2 * H / n
        for i in range(n):
            for j in range(n):
                x0 = -H + i * step
                y0 = -H + j * step
                x1, y1 = x0 + step, y0 + step
                s = 1.0 / 8.0
                mb.quad((x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0), (1, 1, 1, 1),
                        (0, 0, 1), ((x0 * s, y0 * s), (x1 * s, y0 * s), (x1 * s, y1 * s),
                                    (x0 * s, y1 * s)))
        self.floor = mb.node()
        self.floor.reparentTo(self.render)
        self.floor.setTexture(self.tex.floor)
        self.floor.setShader(shaders.get("floor"))
        self.floor.setShaderInput("u_reflect", 1.0 if reflections else 0.0)
        self.mirror = None
        if reflections:
            self.floor.setTransparency(TransparencyAttrib.M_alpha)
            self.floor.setDepthWrite(False)
            self.floor.setBin("fixed", 0)
            self.mirror = self.render.attachNewNode("mirror")
            self.root.instanceTo(self.mirror)
            self.mirror.setScale(1, 1, -1)
            self.mirror.setShaderInput("u_mirror", 1.0)
            self.mirror.setAttrib(CullFaceAttrib.makeReverse())

    def set_reflections(self, on):
        if self.mirror is not None:
            if on:
                self.mirror.show()
            else:
                self.mirror.hide()

    def update(self, t):
        for holder, txt, ph in self.signs:
            # occasional glitch jitter on the holograms
            g = math.sin(t * 7.3 + ph) * math.sin(t * 2.1 + ph * 3)
            if g > 0.93:
                txt.setX(random.uniform(-0.08, 0.08))
                txt.setColorScale(0.5, 1.2, 2.4, 1)
            else:
                txt.setX(0)
                txt.setColorScale(0.25, 1.6, 2.0, 1)
