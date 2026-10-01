"""Third-person character model (bots, wingmen, remote players, decoys).

A jointed, cartoon-proportioned runner: two-part arms and legs (elbows and
knees bend while running), rounded head, hands and boots.  Each outfit picks a
headpiece (helmet, hood, cap, astronaut bowl, banana, shark, skull, knight,
cat ears, crown, mohawk, pirate hat, ninja mask) and a back item (backpack,
cape, wings, katana, air tank).
"""

import math

from panda3d.core import TextNode, TransparencyAttrib, Vec4

from ..gfx import geom
from ..gfx.effects import fx_node
from ..progression.skins import char_skin

MAT_BODY = Vec4(36, 0.7, 0.45, 0)
MAT_NEON = Vec4(1, 0, 0, 2.8)


def _blob(mb, c, r, col, seg=10):
    """Rounded part (sphere scaled per axis)."""
    cx, cy, cz = c
    rx, ry, rz = r
    rings = max(4, seg // 2)
    for i in range(rings):
        t0 = math.pi * i / rings - math.pi / 2
        t1 = math.pi * (i + 1) / rings - math.pi / 2
        for j in range(seg):
            p0 = math.tau * j / seg
            p1 = math.tau * (j + 1) / seg
            base = mb.count
            for (t, pp) in ((t0, p0), (t0, p1), (t1, p1), (t1, p0)):
                n = (math.cos(t) * math.cos(pp), math.cos(t) * math.sin(pp), math.sin(t))
                mb.vw.addData3(cx + n[0] * rx, cy + n[1] * ry, cz + n[2] * rz)
                mb.nw.addData3(*n)
                mb.cw.addData4(*col)
                mb.tw.addData2(pp / math.tau, t / math.pi + 0.5)
            mb.tris.addVertices(base, base + 1, base + 2)
            mb.tris.addVertices(base, base + 2, base + 3)
            mb.count += 4


def _mesh(parent, tex, mat, fill, texture=None, two_sided=False):
    mb = geom.MeshBuilder("part")
    fill(mb)
    n = mb.node()
    n.reparentTo(parent)
    n.setTexture(texture or tex.white)
    n.setShaderInput("u_mat", mat)
    if two_sided:
        n.setTwoSided(True)
    return n


def _build_body(v, tex, sk, body, dark, acc, visor):
    """Assemble the jointed character for outfit ``sk`` onto CharacterVisual ``v``."""
    head_kind = sk.get("head", "helmet")
    back = sk.get("back", "pack")
    skin = tuple(sk.get("skin", (0.85, 0.65, 0.5))) + (1,)
    black = (0.05, 0.05, 0.06, 1)
    white = (0.95, 0.95, 0.92, 1)
    boot = (dark[0] * 0.7, dark[1] * 0.7, dark[2] * 0.7, 1)
    v.hips = v.model.attachNewNode("hips")
    v.hips.setZ(0.92)
    # ---- torso: pelvis, belly, chest, shoulders, belt
    _mesh(v.hips, tex, MAT_BODY, lambda m: (
        m.cbox((0, 0, 0.04), (0.38, 0.24, 0.18), dark),
        _blob(m, (0, 0, 0.28), (0.22, 0.14, 0.2), body),
        m.cbox((0, 0, 0.44), (0.5, 0.28, 0.32), body),
        _blob(m, (-0.29, 0, 0.56), (0.11, 0.11, 0.1), body),
        _blob(m, (0.29, 0, 0.56), (0.11, 0.11, 0.1), body),
        m.cbox((0, 0, 0.13), (0.4, 0.26, 0.06), dark),
        m.cbox((0, 0, 0.66), (0.13, 0.13, 0.08), skin if head_kind in
               ("cap", "mohawk", "pirate", "banana") else dark)), tex.white)
    _mesh(v.hips, tex, MAT_NEON, lambda m: (
        m.cbox((0, 0.142, 0.47), (0.05, 0.02, 0.24), acc),
        m.cbox((0, 0.135, 0.13), (0.12, 0.02, 0.05), acc),
        m.cbox((0.17, 0.142, 0.56), (0.12, 0.02, 0.03), acc),
        m.cbox((-0.17, 0.142, 0.56), (0.12, 0.02, 0.03), acc)))
    # ---- head
    v.head = v.hips.attachNewNode("head")
    v.head.setZ(0.72)
    _build_head(v, tex, head_kind, body, dark, acc, visor, skin, black, white)
    # ---- legs: thigh -> knee -> shin -> boot
    v.legs = []
    v.knees = []
    for sx in (-0.11, 0.11):
        pivot = v.hips.attachNewNode("leg")
        pivot.setPos(sx, 0, 0)
        _mesh(pivot, tex, MAT_BODY, lambda m: (
            m.cbox((0, 0, -0.22), (0.17, 0.19, 0.44), dark),
            _blob(m, (0, 0.02, -0.44), (0.1, 0.1, 0.08), body)), tex.white)
        knee = pivot.attachNewNode("knee")
        knee.setZ(-0.44)
        _mesh(knee, tex, MAT_BODY, lambda m: (
            m.cbox((0, 0, -0.2), (0.15, 0.17, 0.38), dark),
            m.cbox((0, 0.05, -0.43), (0.18, 0.3, 0.12), boot)), tex.white)
        _mesh(knee, tex, MAT_NEON, lambda m: m.cbox((0, 0.095, -0.15), (0.04, 0.02, 0.16), acc))
        v.legs.append(pivot)
        v.knees.append(knee)
    # ---- arms: shoulder -> upper arm -> elbow -> forearm -> hand
    v.arms = []
    glove = (dark[0] * 0.8, dark[1] * 0.8, dark[2] * 0.8, 1)
    for sx in (-0.31, 0.31):
        pivot = v.hips.attachNewNode("arm")
        pivot.setPos(sx, 0, 0.58)
        _mesh(pivot, tex, MAT_BODY, lambda m: (
            m.cbox((0, 0, -0.15), (0.13, 0.14, 0.3), body),
            m.cbox((0, 0, -0.42), (0.12, 0.13, 0.26), body),
            _blob(m, (0, 0.0, -0.58), (0.075, 0.075, 0.08), glove)), tex.white)
        v.arms.append(pivot)
    # ---- weapon held forward
    v.gun = v.hips.attachNewNode("gun")
    v.gun.setPos(0.2, 0.32, 0.44)
    _mesh(v.gun, tex, MAT_BODY, lambda m: (
        m.cbox((0, 0.2, 0), (0.09, 0.62, 0.13), (0.1, 0.1, 0.12, 1)),
        m.cbox((0, -0.02, -0.1), (0.07, 0.1, 0.16), (0.12, 0.12, 0.14, 1))), tex.metal)
    _mesh(v.gun, tex, MAT_NEON, lambda m: m.cbox((0, 0.2, 0.072), (0.03, 0.5, 0.02), acc))
    v.arms[1].setP(80)
    v.arms[0].setP(70)
    v.arms[0].setH(-25)
    # ---- back item
    v.cape = None
    if back == "pack":
        _mesh(v.hips, tex, MAT_BODY, lambda m: (
            m.cbox((0, -0.22, 0.42), (0.36, 0.16, 0.4), dark),
            m.cbox((0, -0.31, 0.32), (0.3, 0.04, 0.16), body)), tex.white)
        _mesh(v.hips, tex, MAT_NEON, lambda m: m.cbox((0, -0.305, 0.5), (0.2, 0.02, 0.04), acc))
    elif back == "tank":
        _mesh(v.hips, tex, MAT_BODY, lambda m: (
            m.cylinder((-0.1, -0.24, 0.2), 0.09, 0.5, (0.8, 0.8, 0.82, 1), 10),
            m.cylinder((0.1, -0.24, 0.2), 0.09, 0.5, (0.8, 0.8, 0.82, 1), 10)), tex.white)
    elif back == "katana":
        sword = v.hips.attachNewNode("sword")
        sword.setPos(0, -0.18, 0.45)
        sword.setR(35)
        _mesh(sword, tex, MAT_BODY, lambda m: (
            m.cbox((0, 0, -0.1), (0.05, 0.04, 0.9), (0.85, 0.88, 0.9, 1)),
            m.cbox((0, 0, 0.42), (0.14, 0.06, 0.03), black),
            m.cbox((0, 0, 0.55), (0.04, 0.04, 0.22), dark)), tex.white)
    elif back == "cape":
        v.cape = v.hips.attachNewNode("cape")
        v.cape.setPos(0, -0.16, 0.66)
        _mesh(v.cape, tex, MAT_BODY, lambda m: m.box((-0.28, -0.03, -0.95), (0.28, 0.0, 0.0),
                                                     (acc[0] * 0.5, acc[1] * 0.5, acc[2] * 0.5,
                                                      1)), two_sided=True)
    elif back == "wings":
        for sgn in (-1, 1):
            w = v.hips.attachNewNode("wing")
            w.setPos(sgn * 0.12, -0.2, 0.5)
            w.setH(sgn * 25)
            w.setR(sgn * -20)
            _mesh(w, tex, MAT_NEON, lambda m, s_=sgn: (
                m.box((min(0, s_ * 0.7), -0.01, -0.1), (max(0, s_ * 0.7), 0.01, 0.45),
                      (acc[0] * 0.6, acc[1] * 0.6, acc[2] * 0.6, 1))), two_sided=True)


def _build_head(v, tex, kind, body, dark, acc, visor, skin, black, white):
    h = v.head
    face_y = 0.15

    def eyes(m, col=black, z=0.17, y=face_y, size=0.035):
        m.cbox((-0.06, y, z), (size, 0.02, size * 1.2), col)
        m.cbox((0.06, y, z), (size, 0.02, size * 1.2), col)

    if kind in ("cap", "mohawk", "pirate"):
        _mesh(h, tex, MAT_BODY, lambda m: (
            _blob(m, (0, 0, 0.15), (0.15, 0.15, 0.17), skin),
            eyes(m), m.cbox((0, face_y, 0.08), (0.08, 0.02, 0.015), (0.4, 0.15, 0.12, 1))))
        if kind == "cap":
            _mesh(h, tex, MAT_BODY, lambda m: (
                m.cylinder((0, 0, 0.24), 0.16, 0.07, body, 14),
                _blob(m, (0, 0, 0.3), (0.16, 0.16, 0.06), body),
                m.box((-0.12, 0.08, 0.24), (0.12, 0.3, 0.26), acc)))
        elif kind == "mohawk":
            _mesh(h, tex, MAT_NEON, lambda m: m.cbox((0, -0.02, 0.33), (0.05, 0.3, 0.14), acc))
        else:
            _mesh(h, tex, MAT_BODY, lambda m: (
                m.cylinder((0, 0, 0.27), 0.17, 0.12, black, 14),
                m.box((-0.3, -0.1, 0.27), (0.3, 0.1, 0.31), black),
                m.cbox((0.06, face_y + 0.005, 0.17), (0.07, 0.02, 0.06), black)))
            _mesh(h, tex, MAT_NEON, lambda m: m.cbox((0, 0.12, 0.33), (0.08, 0.02, 0.05),
                                                     (1.0, 0.85, 0.3, 1)))
    elif kind == "hood" or kind == "ninja":
        cloth = dark if kind == "hood" else body
        _mesh(h, tex, MAT_BODY, lambda m: (
            _blob(m, (0, -0.02, 0.15), (0.19, 0.2, 0.21), cloth),
            m.cbox((0, 0.13, 0.15), (0.22, 0.04, 0.16), black)))
        _mesh(h, tex, MAT_NEON, lambda m: eyes(m, visor, 0.17, 0.155, 0.03))
        if kind == "ninja":
            _mesh(h, tex, MAT_NEON, lambda m: m.cbox((0, 0, 0.27), (0.4, 0.42, 0.04), acc))
    elif kind == "astro":
        _mesh(h, tex, MAT_BODY, lambda m: (
            _blob(m, (0, 0, 0.16), (0.23, 0.23, 0.23), (0.9, 0.9, 0.92, 1)),
            m.cylinder((0, 0, -0.06), 0.16, 0.06, dark, 14)), tex.white)
        _mesh(h, tex, Vec4(80, 1.5, 0.4, 1.2), lambda m: _blob(m, (0, 0.06, 0.17),
                                                              (0.19, 0.19, 0.15), visor))
    elif kind == "banana":
        _mesh(h, tex, MAT_BODY, lambda m: (
            _blob(m, (0, -0.02, 0.24), (0.2, 0.19, 0.36), (0.97, 0.85, 0.15, 1)),
            m.cbox((0, -0.02, 0.62), (0.06, 0.06, 0.08), (0.3, 0.2, 0.08, 1)),
            eyes(m, black, 0.2, 0.17, 0.04),
            m.cbox((0, 0.17, 0.08), (0.1, 0.02, 0.02), black)))
    elif kind == "shark":
        grey = (0.4, 0.5, 0.6, 1)
        _mesh(h, tex, MAT_BODY, lambda m: (
            _blob(m, (0, -0.02, 0.18), (0.21, 0.23, 0.22), grey),
            m.cbox((0, -0.05, 0.42), (0.04, 0.18, 0.2), grey),
            m.cbox((0, 0.14, 0.12), (0.2, 0.06, 0.14), black),
            _blob(m, (0, 0.12, 0.12), (0.12, 0.04, 0.09), skin),
            eyes(m, black, 0.25, 0.19, 0.03)))
        _mesh(h, tex, MAT_BODY, lambda m: [m.tri((x - 0.02, 0.2, 0.2), (x + 0.02, 0.2, 0.2),
                                                 (x, 0.2, 0.15), white, (0, 1, 0))
                                           for x in (-0.09, -0.045, 0.0, 0.045, 0.09)],
              two_sided=True)
    elif kind == "skull":
        _mesh(h, tex, MAT_BODY, lambda m: (
            _blob(m, (0, 0, 0.16), (0.17, 0.18, 0.19), white),
            m.cbox((0, 0.06, 0.03), (0.16, 0.12, 0.08), white),
            m.cbox((0, 0.16, 0.08), (0.004 + 0.1, 0.02, 0.012), black)))
        _mesh(h, tex, MAT_NEON, lambda m: eyes(m, visor, 0.18, 0.165, 0.045))
    elif kind == "knight":
        steel = (0.75, 0.77, 0.8, 1)
        _mesh(h, tex, Vec4(80, 1.4, 0.3, 0), lambda m: (
            m.cylinder((0, 0, -0.02), 0.19, 0.38, steel, 16),
            _blob(m, (0, 0, 0.36), (0.19, 0.19, 0.08), steel),
            m.cbox((0, 0.18, 0.2), (0.24, 0.03, 0.035), black),
            m.cbox((0, 0.18, 0.1), (0.035, 0.03, 0.14), black)), tex.white)
        _mesh(h, tex, MAT_BODY, lambda m: _blob(m, (0, -0.05, 0.5), (0.05, 0.18, 0.12), acc))
    else:
        # helmet with a glowing visor (+ cat ears or a crown)
        _mesh(h, tex, MAT_BODY, lambda m: (
            _blob(m, (0, 0, 0.16), (0.18, 0.19, 0.2), body),
            m.cbox((0, 0.13, 0.15), (0.26, 0.08, 0.1), dark)), tex.white)
        _mesh(h, tex, MAT_NEON, lambda m: m.cbox((0, 0.175, 0.16), (0.24, 0.02, 0.065), visor))
        if kind == "cat":
            _mesh(h, tex, MAT_BODY, lambda m: [
                cone_part(m, (sx, 0, 0.3), 0.07, 0.16, body) for sx in (-0.1, 0.1)])
            _mesh(h, tex, MAT_NEON, lambda m: [
                cone_part(m, (sx, 0.012, 0.31), 0.04, 0.11, acc) for sx in (-0.1, 0.1)])
        elif kind == "crown":
            gold = (1.0, 0.8, 0.25, 1)
            _mesh(h, tex, Vec4(1, 0, 0, 1.4), lambda m: (
                m.cylinder((0, 0, 0.32), 0.15, 0.07, gold, 12),
                [cone_part(m, (math.cos(a) * 0.13, math.sin(a) * 0.13, 0.39), 0.035, 0.09, gold)
                 for a in [i * math.tau / 5 for i in range(5)]]))
    v.visor = h


def cone_part(m, c, r, hgt, col, seg=8):
    cx, cy, cz = c
    for i in range(seg):
        a0 = math.tau * i / seg
        a1 = math.tau * (i + 1) / seg
        am = (a0 + a1) / 2
        m.tri((cx + math.cos(a0) * r, cy + math.sin(a0) * r, cz),
              (cx + math.cos(a1) * r, cy + math.sin(a1) * r, cz), (cx, cy, cz + hgt), col,
              (math.cos(am), math.sin(am), 0.4))


class CharacterVisual:
    def __init__(self, match, skin_id="default", team_color=None, name="", show_name=False,
                 hologram=False):
        self.match = match
        tex = match.textures
        sk = char_skin(skin_id)
        body = sk["body"] + (1,)
        dark = (sk["body"][0] * 0.6, sk["body"][1] * 0.6, sk["body"][2] * 0.6, 1)
        acc = tuple(team_color or sk["accent"]) + (1,)
        visor = tuple(team_color or sk["visor"]) + (1,)
        self.root = match.world_root.attachNewNode("character")
        self.model = self.root.attachNewNode("model")
        _build_body(self, tex, sk, body, dark, acc, visor)
        # name tag
        self.tag = None
        if name:
            tn = TextNode("tag")
            tn.setText(name)
            tn.setAlign(TextNode.ACenter)
            if match.font:
                tn.setFont(match.font)
            tn.setTextColor(acc[0], acc[1], acc[2], 1)
            self.tag = match.overlay_root.attachNewNode(tn)
            self.tag.setScale(0.28)
            self.tag.setBillboardPointEye()
            self.tag.setDepthTest(True)       # walls, trees and props hide name tags
            self.tag.setDepthWrite(False)
            self.tag.setBin("fixed", 50)
            self.tag.setShaderOff(10)
            self.tag.setLightOff(10)
            if not show_name:
                self.tag.hide()
        self.show_name = show_name
        self.phase = 0.0
        self.cloak = 0.0
        self.revealed = False
        self.hologram = hologram
        # scan-pulse marker (overlay root is not mirrored and ignores depth)
        self.marker = geom.card(0.5, 0.5)
        self.marker.reparentTo(match.overlay_root)
        fx_node(self.marker, 5, hue_lock=True)
        self.marker.setBillboardPointEye()
        self.marker.setDepthTest(False)
        self.marker.setBin("fixed", 45)
        self.marker.setColorScale(4, 0.6, 0.3, 1)
        self.marker.hide()
        if hologram:
            self.set_hologram()

    def set_hologram(self):
        fx_node(self.model, 4, additive=True)
        self.model.setColorScale(0.05, 0.6, 0.8, 1)

    def muzzle_world(self):
        return self.gun.getPos(self.match.world_root) + \
            self.gun.getQuat(self.match.world_root).getForward() * 0.55

    def update(self, dt, pos, yaw, pitch, speed, crouch, cloak_alpha=1.0, revealed=False,
               tag_visible=False):
        self.root.setPos(pos)
        self.root.setH(yaw)
        self.model.setSz(0.7 if crouch else 1.0)
        self.phase += dt * speed * 1.5
        k = min(1.0, speed / 6.0)
        sw = math.sin(self.phase) * k * 38
        self.legs[0].setP(sw)
        self.legs[1].setP(-sw)
        # knees bend on the back swing; a little bounce while running
        self.knees[0].setP(-max(0.0, math.sin(self.phase + 1.2)) * 55 * k - (25 if crouch else 0))
        self.knees[1].setP(-max(0.0, math.sin(self.phase + 1.2 + math.pi)) * 55 * k -
                           (25 if crouch else 0))
        self.hips.setZ(0.92 + abs(math.sin(self.phase)) * 0.04 * k)
        self.arms[0].setP(70 + sw * 0.2)
        self.head.setP(max(-40, min(40, pitch * 0.6)))
        self.gun.setP(pitch * 0.9)
        self.arms[1].setP(80 + pitch * 0.8)
        if self.cape is not None:
            self.cape.setP(-8 - 30 * k + math.sin(self.phase * 0.5) * 4 * k)
        # cloak: fade out to a faint shimmer
        if cloak_alpha < 0.99:
            if self.cloak == 0.0:
                self.model.setTransparency(TransparencyAttrib.M_alpha)
            self.model.setAlphaScale(cloak_alpha)
            self.cloak = cloak_alpha
        elif self.cloak:
            self.model.clearTransparency()
            self.model.setAlphaScale(1.0)
            self.cloak = 0.0
        # scan pulse reveal: glowing marker drawn through walls
        if revealed:
            self.marker.show()
            self.marker.setPos(pos.x, pos.y, pos.z + (1.3 if crouch else 1.9))
            self.marker.setScale(1.2 + 0.3 * math.sin(self.phase * 0.2 + pos.x))
        elif self.revealed:
            self.marker.hide()
        self.revealed = revealed
        if self.tag is not None:
            self.tag.setPos(pos.x, pos.y, pos.z + 2.15)
            if self.show_name or tag_visible:
                self.tag.show()
            else:
                self.tag.hide()

    def show(self):
        self.root.show()

    def hide(self):
        self.root.hide()
        self.marker.hide()
        if self.tag is not None:
            self.tag.hide()

    def destroy(self):
        self.root.removeNode()
        self.marker.removeNode()
        if self.tag is not None:
            self.tag.removeNode()
