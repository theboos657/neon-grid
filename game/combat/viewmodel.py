"""First-person weapon models and their procedural animation.

Rendered by the dedicated view-model camera (see gfx.postfx).  All motion here
is the *weapon* moving (sway, bob, recoil, reload, swing) - the player camera
itself never bobs or tilts.
"""

import math

from panda3d.core import PTA_LVecBase4f, Vec3, Vec4

from ..gfx import geom, shaders
from ..progression.skins import weapon_skin

MAT_BODY = Vec4(50, 1.0, 0.25, 0)
MAT_NEON = Vec4(1, 0, 0, 3.0)
HAND = (0.08, 0.085, 0.1, 1)


def _mat_node(mb, parent, tex, mat):
    n = mb.node()
    n.reparentTo(parent)
    n.setTexture(tex)
    n.setShaderInput("u_mat", mat)
    return n


def build_weapon(stats, skin, textures):
    """Return (root NodePath, muzzle offset Vec3)."""
    from panda3d.core import NodePath
    root = NodePath("vm_weapon")
    body = skin["body"] + (1,)
    dark = (skin["body"][0] * 0.5, skin["body"][1] * 0.5, skin["body"][2] * 0.5, 1)
    acc = skin["accent"] + (1,)
    b = geom.MeshBuilder("vm_body")
    n = geom.MeshBuilder("vm_neon")
    cls = stats["cls"]
    muzzle = Vec3(0, 0.6, 0.03)
    if stats["melee"]:
        wid = stats["id"]
        b.cbox((0, 0, -0.05), (0.05, 0.05, 0.2), dark)                       # grip
        b.cbox((0, 0, 0.07), (0.12, 0.05, 0.03), body)                       # guard
        if wid == "katana":
            n.cbox((0, 0, 0.45), (0.012, 0.045, 0.72), acc)
        elif wid == "baton":
            b.cbox((0, 0, 0.3), (0.045, 0.045, 0.45), body)
            n.cbox((0, 0, 0.45), (0.05, 0.05, 0.2), acc)
        elif wid == "axe":
            b.cbox((0, 0, 0.3), (0.035, 0.035, 0.5), body)
            n.cbox((0, 0.1, 0.48), (0.02, 0.2, 0.18), acc)
        elif wid == "knife":
            n.cbox((0, 0, 0.2), (0.01, 0.035, 0.24), acc)
        elif wid == "whip":
            for i in range(8):
                n.cbox((0, i * 0.03, 0.12 + i * 0.07), (0.018, 0.018, 0.07), acc)
        elif wid == "gravhammer":
            b.cbox((0, 0, 0.3), (0.04, 0.04, 0.5), body)
            b.cbox((0, 0, 0.58), (0.22, 0.14, 0.14), body)
            n.cbox((0.112, 0, 0.58), (0.01, 0.1, 0.1), acc)
            n.cbox((-0.112, 0, 0.58), (0.01, 0.1, 0.1), acc)
        elif wid == "claws":
            for x in (-0.04, 0, 0.04):
                n.cbox((x, 0, 0.22), (0.01, 0.02, 0.28), acc)
        elif wid == "spear":
            b.cbox((0, 0, 0.35), (0.03, 0.03, 0.8), body)
            n.cbox((0, 0, 0.82), (0.015, 0.05, 0.18), acc)
        elif wid == "fist":
            b.cbox((0, 0.02, 0.05), (0.12, 0.12, 0.14), body)
            n.cbox((0, 0.085, 0.05), (0.1, 0.01, 0.08), acc)
        else:  # chainblade
            b.cbox((0, 0, 0.35), (0.02, 0.07, 0.55), body)
            n.cbox((0, 0.038, 0.35), (0.022, 0.01, 0.55), acc)
            n.cbox((0, -0.038, 0.35), (0.022, 0.01, 0.55), acc)
        root_body = _mat_node(b, root, textures.white, MAT_BODY)
        root_neon = _mat_node(n, root, textures.white, MAT_NEON)
        # hand
        h = geom.MeshBuilder("hand")
        h.cbox((0, 0, -0.05), (0.09, 0.1, 0.1), HAND)
        _mat_node(h, root, textures.white, Vec4(10, 0.2, 0.2, 0))
        return root, muzzle, (root_body, root_neon)

    # ------------------------------------------------------------- guns
    L = {"pistol": 0.22, "smg": 0.34, "rifle": 0.5, "shotgun": 0.5, "sniper": 0.62,
         "plasma": 0.42, "rail": 0.56}[cls]
    H = {"pistol": 0.08, "smg": 0.09, "rifle": 0.09, "shotgun": 0.1, "sniper": 0.085,
         "plasma": 0.12, "rail": 0.1}[cls]
    W = 0.055 if cls in ("pistol", "smg") else 0.065
    if cls == "plasma":
        W = 0.09
    b.cbox((0, L * 0.25, 0), (W, L * 0.7, H), body)                     # receiver
    b.cbox((0, -0.02, -0.09), (W * 0.8, 0.06, 0.13), dark)               # grip
    if cls not in ("pistol",):
        b.cbox((0, L * 0.55 + 0.1, 0.012), (W * 0.55, 0.3 if cls in ("rifle", "sniper", "rail")
                                            else 0.16, H * 0.45), dark)   # barrel
    if cls in ("smg", "rifle", "sniper"):
        b.cbox((0, L * 0.2, -0.09), (W * 0.7, 0.07, 0.12), dark)          # magazine
    if cls in ("rifle", "sniper", "rail", "shotgun"):
        b.cbox((0, -0.16, -0.01), (W * 0.8, 0.18, H * 0.8), dark)         # stock
    mods = stats.get("mods") or {}
    scope = None
    if mods.get("optic"):
        pass                                # the optic mod replaces the stock sight
    elif stats["scoped"]:
        scope = _scope(b, n, L * 0.25, H * 0.5 + 0.04, 0.22, 0.05, dark, acc)
    elif cls != "plasma":
        b.cbox((0, L * 0.1, H * 0.5 + 0.012), (0.02, 0.05, 0.024), dark)  # iron sight
    if cls == "shotgun":
        b.cbox((0, L * 0.6, -0.04), (W * 0.9, 0.18, 0.05), dark)          # pump
    if cls == "plasma":
        n.cbox((0, L * 0.3, 0.0), (W + 0.004, 0.05, H * 0.6), acc)
        n.cbox((0, L * 0.5, 0.0), (W + 0.004, 0.05, H * 0.6), acc)
        n.cbox((0, L * 0.62 + 0.02, 0.0), (0.05, 0.02, 0.05), acc)
    if cls == "rail":
        for i in range(4):
            n.cbox((0, L * 0.35 + i * 0.07, H * 0.5 + 0.005), (W * 0.9, 0.025, 0.01), acc)
        n.cbox((W * 0.5 + 0.003, L * 0.5, 0), (0.005, L * 0.6, 0.012), acc)
        n.cbox((-W * 0.5 - 0.003, L * 0.5, 0), (0.005, L * 0.6, 0.012), acc)
    # side accent strips (skin)
    pat = skin["pattern"]
    n.cbox((W * 0.5 + 0.002, L * 0.25, H * 0.15), (0.004, L * 0.6, 0.008), acc)
    n.cbox((-W * 0.5 - 0.002, L * 0.25, H * 0.15), (0.004, L * 0.6, 0.008), acc)
    if pat == "stripes":
        for i in range(3):
            n.cbox((0, L * 0.05 + i * 0.05, H * 0.5 + 0.002), (W * 1.02, 0.012, 0.004), acc)
    elif pat == "digital":
        for i in range(5):
            n.cbox((W * 0.5 + 0.002, L * 0.0 + i * 0.045, -H * 0.2 + (i % 2) * 0.02),
                   (0.004, 0.02, 0.012), acc)
    barrel_end = L * 0.55 + 0.1 + (0.15 if cls in ("rifle", "sniper", "rail") else 0.08)
    if cls == "pistol":
        barrel_end = L * 0.6 + 0.01
    n.cbox((0, barrel_end - 0.005, 0.012), (W * 0.45, 0.012, H * 0.4), acc)
    muzzle = Vec3(0, barrel_end + 0.02, 0.012)
    muzzle, mod_scope = _attachments(b, n, mods, L, H, W, barrel_end, muzzle, body, dark, acc)
    scope = mod_scope or scope
    root_body = _mat_node(b, root, textures.white, MAT_BODY)
    if scope is not None:
        # the rear lens shows the live scope camera (see gfx/scope.py)
        center, radius = scope
        lens = geom.card(radius * 2, radius * 2)
        lens.reparentTo(root)
        lens.setPos(center)
        lens.setShader(shaders.get("scopelens"), 10)
        lens.setShaderInput("u_reticle", 1 if stats["zoom"] >= 0.45 else 0)
        root.setPythonTag("scope", (Vec3(center), radius))
    root_neon = _mat_node(n, root, textures.white, MAT_NEON)
    # gloved hands
    h = geom.MeshBuilder("hands")
    h.cbox((0, -0.02, -0.1), (0.075, 0.09, 0.09), HAND)
    h.cbox((-0.02, L * 0.5, -0.06), (0.08, 0.1, 0.07), HAND)
    _mat_node(h, root, textures.white, Vec4(10, 0.2, 0.2, 0))
    return root, muzzle, (root_body, root_neon)


RED = (1.0, 0.12, 0.08, 1)


def _scope(b, n, cy, cz, ln, w, dark, acc):
    """Scope tube with an eyepiece bell.  Returns (rear lens centre, lens radius)."""
    b.cbox((0, cy, cz), (w, ln, w), dark)                               # tube
    b.cbox((0, cy, cz - w * 0.6), (0.02, ln * 0.35, w * 0.4), dark)       # mount
    rear = cy - ln / 2
    b.cbox((0, rear + 0.02, cz), (w * 1.02, 0.04, w * 1.02), dark)        # eyepiece
    b.cbox((0, cy + ln / 2 - 0.015, cz), (w * 1.25, 0.03, w * 1.25), dark)  # objective bell
    n.cbox((0, rear + 0.041, cz + w * 0.7), (w * 1.0, 0.006, 0.004), acc)
    n.cbox((0, cy + ln / 2 + 0.001, cz), (w * 0.9, 0.003, w * 0.9), acc)  # front lens glint
    # the lens card is drawn round (with its own metal eyepiece ring) by the shader
    return (Vec3(0, rear - 0.0015, cz), w * 0.78)


def _attachments(b, n, mods, L, H, W, barrel_end, muzzle, body, dark, acc):
    """Add attachment geometry; returns (muzzle point, scope info or None)."""
    top = H * 0.5
    scope = None
    o = mods.get("optic")
    if o == "reddot":
        b.cbox((0, L * 0.2, top + 0.02), (0.03, 0.05, 0.035), dark)
        n.cbox((0, L * 0.2 - 0.026, top + 0.028), (0.008, 0.004, 0.008), RED)
    elif o == "holo":
        b.cbox((0, L * 0.2, top + 0.01), (0.05, 0.06, 0.012), dark)
        for sx in (-0.022, 0.022):
            b.cbox((sx, L * 0.2 + 0.02, top + 0.035), (0.006, 0.02, 0.045), dark)
        b.cbox((0, L * 0.2 + 0.02, top + 0.06), (0.05, 0.02, 0.006), dark)
        n.cbox((0, L * 0.2 + 0.02, top + 0.035), (0.036, 0.002, 0.036), (0.1, 0.9, 1.0, 0.6))
    elif o in ("acog", "sniperscope"):
        ln = 0.16 if o == "acog" else 0.27
        w = 0.045 if o == "acog" else 0.052
        scope = _scope(b, n, L * 0.25, top + 0.045, ln, w, dark, acc)
    m = mods.get("muzzle")
    if m == "suppressor":
        b.cbox((0, barrel_end + 0.11, 0.012), (0.042, 0.2, 0.042), dark)
        n.cbox((0, barrel_end + 0.11, 0.034), (0.01, 0.16, 0.003), acc)
        muzzle = Vec3(0, barrel_end + 0.22, 0.012)
    elif m == "compensator":
        b.cbox((0, barrel_end + 0.035, 0.012), (0.04, 0.06, 0.04), dark)
        for i in range(3):
            n.cbox((0, barrel_end + 0.015 + i * 0.018, 0.033), (0.03, 0.006, 0.003), acc)
        muzzle = Vec3(0, barrel_end + 0.07, 0.012)
    elif m == "choke":
        b.cbox((0, barrel_end + 0.02, 0.012), (0.05, 0.04, 0.05), dark)
        muzzle = Vec3(0, barrel_end + 0.045, 0.012)
    elif m == "flashhider":
        for sx, sz in ((-0.012, 0), (0.012, 0), (0, 0.012), (0, -0.012)):
            b.cbox((sx, barrel_end + 0.03, 0.012 + sz), (0.008, 0.05, 0.008), dark)
        muzzle = Vec3(0, barrel_end + 0.06, 0.012)
    g = mods.get("magazine")
    if g == "extmag":
        b.cbox((0, L * 0.2, -0.13), (W * 0.72, 0.075, 0.2), dark)
        n.cbox((W * 0.36 + 0.002, L * 0.2, -0.16), (0.003, 0.05, 0.08), acc)
    elif g == "fastmag":
        b.cbox((0, L * 0.2, -0.1), (W * 0.72, 0.07, 0.13), dark)
        n.cbox((0, L * 0.2 - 0.036, -0.14), (W * 0.6, 0.004, 0.02), acc)
    u = mods.get("underbarrel")
    if u == "vgrip":
        b.cbox((0, L * 0.5, -0.08), (0.03, 0.035, 0.1), dark)
    elif u == "angled":
        b.cbox((0, L * 0.5, -0.055), (0.03, 0.09, 0.04), dark)
    elif u == "laser":
        b.cbox((W * 0.5 + 0.016, L * 0.45, -0.01), (0.022, 0.08, 0.022), dark)
        n.cbox((W * 0.5 + 0.016, L * 0.45 + 0.041, -0.01), (0.01, 0.004, 0.01), RED)
    k = mods.get("stock")
    if k == "lightstock":
        b.cbox((0, -0.2, 0.0), (0.012, 0.2, 0.012), dark)
        b.cbox((0, -0.2, -0.05), (0.012, 0.2, 0.012), dark)
        b.cbox((0, -0.3, -0.025), (0.03, 0.02, 0.08), dark)
    elif k == "heavystock":
        b.cbox((0, -0.19, -0.015), (W * 1.05, 0.22, H * 1.1), body)
        n.cbox((W * 0.525 + 0.002, -0.19, -0.015), (0.003, 0.16, 0.01), acc)
    return muzzle, scope


EYE_RELIEF = 0.075        # distance from the eye to the scope's rear lens while aiming


class ViewModel:
    def __init__(self, vm_root, textures, lights):
        self.vm_root = vm_root
        self.textures = textures
        self.lights = lights
        self.anchor = vm_root.attachNewNode("vm_anchor")
        self.anchor.setShader(shaders.get("world"))
        # lighting for the view-model scene (key + fill in camera space)
        self.pos_arr = PTA_LVecBase4f.emptyArray(8)
        self.col_arr = PTA_LVecBase4f.emptyArray(8)
        self.pos_arr[0] = Vec4(-1.5, 0.5, 2.0, 10)
        self.col_arr[0] = Vec4(1.1, 2.2, 2.6, 1)
        self.pos_arr[1] = Vec4(2.0, 1.0, -0.5, 10)
        self.col_arr[1] = Vec4(0.5, 0.9, 1.6, 1)
        self.pos_arr[2] = Vec4(0.3, 1.2, 0.3, 3)
        self.col_arr[2] = Vec4(0, 0, 0, 1)            # muzzle flash light
        a = self.anchor
        a.setShaderInput("u_lightPos", self.pos_arr)
        a.setShaderInput("u_lightCol", self.col_arr)
        a.setShaderInput("u_numLights", 3)
        a.setShaderInput("u_camPos", Vec3(0, 0, 0))
        a.setShaderInput("u_ambient", Vec3(0.55, 0.62, 0.7))
        a.setShaderInput("u_fog", Vec4(0, 0, 0, 0))
        a.setShaderInput("u_mirror", 0.0)
        a.setShaderInput("u_hue", 0.0)
        a.setShaderInput("u_neonGain", 1.0)
        a.setShaderInput("u_time", 0.0)
        a.setShaderInput("u_mat", MAT_BODY)
        a.setShaderInput("u_scopeActive", 0.0)
        a.setShaderInput("u_reticle", 0)
        from panda3d.core import Texture
        a.setShaderInput("scopeTex", Texture("scope_placeholder"))
        self.scope_info = None
        self.cache = {}
        self.current = None
        self.current_key = None
        self.muzzle = Vec3(0, 0.6, 0)
        self.base_pos = Vec3(0.17, 0.5, -0.19)
        # animation state
        self.t = 0.0
        self.recoil = 0.0
        self.recoil_v = 0.0
        self.sway = Vec3(0, 0, 0)
        self.bob = 0.0
        self.swing = 0.0
        self.swing_dir = 1
        self.flash_t = 0.0
        self.ads_k = 0.0
        self.sprint_k = 0.0
        self.hidden = False

    def set_scope_view(self, scope_view):
        """Feed the live scope texture to every scope lens."""
        if scope_view is not None and scope_view.ok:
            self.anchor.setShaderInput("scopeTex", scope_view.tex)

    def set_scope_active(self, on):
        self.anchor.setShaderInput("u_scopeActive", 1.0 if on else 0.0)

    def set_weapon(self, stats, skin_id):
        key = (stats["id"], skin_id, tuple(sorted((stats.get("mods") or {}).items())))
        if key == self.current_key:
            return
        if self.current is not None:
            self.current.detachNode()
        if key not in self.cache:
            node, muzzle, parts = build_weapon(stats, weapon_skin(skin_id), self.textures)
            self.cache[key] = (node, muzzle)
        node, muzzle = self.cache[key]
        self.scope_info = node.getPythonTag("scope")
        node.reparentTo(self.anchor)
        self.current = node
        self.current_key = key
        self.muzzle = muzzle
        self.stats = stats
        node.setScale(0.72)
        if stats["melee"]:
            self.base_pos = Vec3(0.24, 0.5, -0.3)
        else:
            self.base_pos = Vec3(0.17, 0.5, -0.19)

    def kick(self, amount):
        self.recoil_v += amount
        self.flash_t = 0.05

    def start_swing(self):
        self.swing = 1.0
        self.swing_dir *= -1

    def muzzle_view(self):
        """Muzzle position in view (camera) space."""
        if self.current is None:
            return Vec3(0.2, 0.6, -0.15)
        return self.vm_root.getRelativePoint(self.current, self.muzzle)

    def update(self, dt, c, ws, mouse_dx, mouse_dy, hue, gain):
        self.t += dt
        a = self.anchor
        a.setShaderInput("u_time", self.t)
        a.setShaderInput("u_hue", hue)
        a.setShaderInput("u_neonGain", gain)
        if self.current is None:
            return
        # muzzle light
        if self.flash_t > 0:
            self.flash_t -= dt
            col = ws.stats["color"]
            self.col_arr[2] = Vec4(col[0] * 6, col[1] * 6, col[2] * 6, 1)
        else:
            self.col_arr[2] = Vec4(0, 0, 0, 1)
        # recoil spring
        self.recoil_v += (-self.recoil * 180.0 - self.recoil_v * 18.0) * dt
        self.recoil += self.recoil_v * dt
        # sway follows mouse movement (lagged)
        target = Vec3(-mouse_dx * 0.0006, 0, mouse_dy * 0.0006)
        target.x = max(-0.04, min(0.04, target.x))
        target.z = max(-0.04, min(0.04, target.z))
        self.sway += (target - self.sway) * min(1.0, dt * 10)
        # bob from movement (weapon only)
        hs = math.hypot(c.body.vel.x, c.body.vel.y)
        moving = c.body.on_ground and hs > 1.0 and c.sliding <= 0
        self.bob += dt * hs * 1.25 if moving else 0.0
        amp = min(1.0, hs / 9.0) if moving else 0.0
        bob_x = math.sin(self.bob) * 0.012 * amp
        bob_z = -abs(math.cos(self.bob)) * 0.012 * amp
        # sprint / ads blending
        want_sprint = 1.0 if c.sprinting else 0.0
        self.sprint_k += (want_sprint - self.sprint_k) * min(1.0, dt * 8)
        want_ads = 1.0 if (c.input.ads and not ws.melee) else 0.0
        self.ads_k += (want_ads - self.ads_k) * min(1.0, dt * 12)
        pos = Vec3(self.base_pos)
        ads_pos = Vec3(0.0, 0.36, -0.092)
        info = getattr(self, "scope_info", None)
        if info is not None and ws.stats["scoped"]:
            # bring the scope's rear lens right in front of the eye
            center, radius = info
            ads_pos = Vec3(0, EYE_RELIEF, 0) - center * self.current.getScale()[0]
        pos = pos * (1 - self.ads_k) + ads_pos * self.ads_k
        pos += self.sway * (1 - self.ads_k * 0.8) + Vec3(bob_x, 0, bob_z) * (1 - self.ads_k * 0.8)
        h = 0.0
        p = 0.0
        r = 0.0
        # sprint pose
        pos += Vec3(-0.04, -0.02, -0.04) * self.sprint_k
        h += 25 * self.sprint_k
        r += -12 * self.sprint_k
        p += -10 * self.sprint_k
        # slide pose
        if c.sliding > 0:
            r += 10
        # recoil
        pos.y -= self.recoil * 0.05
        p += self.recoil * 12
        # reload animation: dip + roll
        if ws.reloading:
            k = ws.reload_fraction()
            s = math.sin(k * math.pi)
            pos.z -= 0.12 * s
            r += 35 * s
            p -= 15 * s
        # draw animation
        if ws.swap_left > 0:
            k = ws.swap_left / max(0.01, ws.stats["swap"])
            pos.z -= 0.3 * k
            p -= 40 * k
        # melee swing
        if self.swing > 0:
            self.swing = max(0.0, self.swing - dt * ws.stats["rps"] * 2.2)
            k = 1 - self.swing
            s = math.sin(k * math.pi)
            style = ws.stats.get("style", "slash")
            if style == "stab":
                pos.y += 0.25 * s
                p -= 10 * s
            elif style == "chop":
                p -= 80 * s
                pos.y += 0.1 * s
            elif style == "bash":
                pos.y += 0.18 * s
                pos.x -= 0.1 * s
            else:
                h += 70 * s * self.swing_dir
                r += 40 * s * self.swing_dir
                pos.x -= 0.18 * s * self.swing_dir
                p -= 30 * s
        if ws.melee and self.swing <= 0:
            p += -20
            r += -10
        a.setPos(pos)
        a.setHpr(h, p, r)
        if self.hidden:
            a.hide()
        else:
            a.show()
