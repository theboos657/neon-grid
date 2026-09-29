"""Third-person character model (bots, wingmen, remote players, decoys).

A stylised armoured runner assembled from boxes with emissive visor and
armour seams.  Legs/arms swing procedurally from movement speed.
"""

import math

from panda3d.core import TextNode, TransparencyAttrib, Vec4

from ..gfx import geom
from ..gfx.effects import fx_node
from ..progression.skins import char_skin

MAT_BODY = Vec4(36, 0.7, 0.45, 0)
MAT_NEON = Vec4(1, 0, 0, 2.8)


def _part(parent, textures, boxes, mat, tex=None):
    mb = geom.MeshBuilder("part")
    for (c, s, col) in boxes:
        mb.cbox(c, s, col)
    n = mb.node()
    n.reparentTo(parent)
    n.setTexture(tex or textures.white)
    n.setShaderInput("u_mat", mat)
    return n


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
        self.hips = self.model.attachNewNode("hips")
        self.hips.setZ(0.92)
        # torso & head
        _part(self.hips, tex, [((0, 0, 0.08), (0.42, 0.26, 0.22), dark),
                               ((0, 0, 0.42), (0.56, 0.32, 0.5), body),
                               ((0, -0.2, 0.42), (0.36, 0.14, 0.44), dark)], MAT_BODY, tex.metal)
        _part(self.hips, tex, [((0, 0.165, 0.46), (0.06, 0.02, 0.36), acc),
                               ((0.2, 0.165, 0.58), (0.1, 0.02, 0.04), acc),
                               ((-0.2, 0.165, 0.58), (0.1, 0.02, 0.04), acc),
                               ((0, -0.28, 0.45), (0.2, 0.02, 0.3), acc)], MAT_NEON)
        self.head = self.hips.attachNewNode("head")
        self.head.setZ(0.72)
        _part(self.head, tex, [((0, 0, 0.14), (0.28, 0.3, 0.3), body)], MAT_BODY, tex.metal)
        self.visor = _part(self.head, tex, [((0, 0.14, 0.16), (0.24, 0.04, 0.08), visor)], MAT_NEON)
        # limbs
        self.legs = []
        for sx in (-0.12, 0.12):
            pivot = self.hips.attachNewNode("leg")
            pivot.setPos(sx, 0, 0)
            _part(pivot, tex, [((0, 0, -0.44), (0.17, 0.2, 0.88), dark)], MAT_BODY, tex.metal)
            _part(pivot, tex, [((0, 0.105, -0.5), (0.04, 0.02, 0.2), acc)], MAT_NEON)
            self.legs.append(pivot)
        self.arms = []
        for sx in (-0.34, 0.34):
            pivot = self.hips.attachNewNode("arm")
            pivot.setPos(sx, 0, 0.62)
            _part(pivot, tex, [((0, 0, -0.3), (0.14, 0.16, 0.6), body)], MAT_BODY, tex.metal)
            self.arms.append(pivot)
        # weapon held forward
        self.gun = self.hips.attachNewNode("gun")
        self.gun.setPos(0.22, 0.3, 0.42)
        _part(self.gun, tex, [((0, 0.2, 0), (0.1, 0.6, 0.14), (0.1, 0.1, 0.12, 1))], MAT_BODY,
              tex.metal)
        _part(self.gun, tex, [((0, 0.2, 0.075), (0.03, 0.5, 0.02), acc)], MAT_NEON)
        self.arms[1].setP(80)
        self.arms[0].setP(70)
        self.arms[0].setH(-25)
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
            self.tag.setDepthTest(False)
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
        sw = math.sin(self.phase) * min(1.0, speed / 6.0) * 38
        self.legs[0].setP(sw)
        self.legs[1].setP(-sw)
        self.arms[0].setP(70 + sw * 0.2)
        self.head.setP(max(-40, min(40, pitch * 0.6)))
        self.gun.setP(pitch * 0.9)
        self.arms[1].setP(80 + pitch * 0.8)
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
