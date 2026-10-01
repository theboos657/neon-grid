"""Secret cheat ("hack") menu: press  [  then  L  then  '  during an offline match.

Everything here only changes the local player for the current match: nothing is
saved, the profile is never touched, and all of it is gone when the match ends.
Online matches refuse to open it (the server would reject the results anyway).
"""

import math

from panda3d.core import Vec3

from .. import i18n
from . import theme as T
from .widgets import UI

SEQUENCE = ["[", "l", "'"]
SEQ_WINDOW = 2.5        # seconds to type the whole sequence

CHEATS = [
    ("fly", "hk_fly"), ("noclip", "hk_noclip"), ("aimbot", "hk_aimbot"), ("god", "hk_god"),
    ("ammo", "hk_ammo"), ("onehit", "hk_onehit"), ("speed", "hk_speed"), ("esp", "hk_esp"),
    ("nocd", "hk_nocd"), ("superjump", "hk_superjump"), ("lowgrav", "hk_lowgrav"),
]


class HackMenu:
    def __init__(self, app):
        self.app = app
        self.ui = UI(app)
        self.visible = False
        self.root = None
        self.keys = []
        b = app.base
        for k in ("[", "l", "'"):
            b.accept(k, self._key, [k])
            b.accept("shift-" + k, self._key, [k])

    # ------------------------------------------------------------------ key sequence
    def _key(self, k):
        now = self.app.clock.getFrameTime()
        self.keys = [(kk, t) for (kk, t) in self.keys if now - t < SEQ_WINDOW] + [(k, now)]
        if [kk for kk, _ in self.keys[-3:]] == SEQUENCE:
            self.keys = []
            self.toggle()

    def toggle(self):
        app = self.app
        m = app.match
        if self.visible:
            self.close()
            return
        if app.state != "match" or m is None or m.player is None:
            return
        if m.online:
            app.menus.toast(i18n.t("hk_online"), 3.0)
            return
        self.visible = True
        app.input.set_captured(False)
        self._build()

    def close(self):
        self.visible = False
        if self.root is not None:
            self.root.removeNode()
            self.root = None
        app = self.app
        if app.state == "match" and not app.paused and app.match is not None:
            app.input.set_captured(True)

    # ------------------------------------------------------------------ ui
    def _build(self):
        if self.root is not None:
            self.root.removeNode()
        ar = self.app.getAspectRatio()
        self.root = self.app.aspect2d.attachNewNode("hacks")
        self.root.setBin("gui-popup", 90)
        x0 = -ar + 0.05
        f = self.ui.frame(self.root, x0, x0 + 0.95, -0.95, 0.95, (0.03, 0.0, 0.03, 0.93))
        cx = x0 + 0.475
        T.text(f, i18n.t("hk_title"), (cx, 0.84), 0.07, (1.0, 0.25, 0.4, 1), "center",
               self.ui.dfont)
        T.text(f, i18n.t("hk_note", _wrap=40), (cx, 0.77), 0.026, T.GREY, "center",
               self.ui.font, wordwrap=34)
        cheats = self._cheats()
        for i, (key, label) in enumerate(CHEATS):
            on = cheats.get(key, False)
            txt = ("[ON]  " if on else "[  ]  ") + i18n.t(label)

            def flip(k=key):
                c = self._cheats()
                c[k] = not c.get(k, False)
                self._apply()
                self._build()
            self.ui.button(f, txt, (cx, 0.66 - i * 0.105), flip, 0.85, 0.085, 0.036,
                           align="left", color=(0.35, 0.05, 0.12, 0.95) if on else None)
        self.ui.button(f, i18n.t("hk_close"), (cx, -0.86), self.close, 0.6, 0.08, 0.04)

    def _cheats(self):
        p = self.app.match.player
        if not hasattr(p, "cheats"):
            p.cheats = {}
        return p.cheats

    def _apply(self):
        """Map cheats onto the player's existing flags."""
        p = self.app.match.player
        c = p.cheats
        p.god = c.get("god", False)
        p.infinite_ammo = c.get("ammo", False)
        p.infinite_energy = c.get("nocd", False)
        p.no_cooldowns = c.get("nocd", False)


# ---------------------------------------------------------------------- gameplay hooks
def fly_update(c, dt):
    """Fly / noclip movement (called from movement.update when active)."""
    m = c.match
    b = c.body
    inp = c.input
    noclip = c.cheats.get("noclip")
    yaw = math.radians(c.yaw)
    pit = math.radians(c.pitch)
    fwd = Vec3(-math.sin(yaw) * math.cos(pit), math.cos(yaw) * math.cos(pit), math.sin(pit))
    right = Vec3(math.cos(yaw), math.sin(yaw), 0)
    wish = right * inp.move_x + fwd * inp.move_y
    im = m.app.input
    if im.down("jump"):
        wish.z += 1.0
    if im.down("crouch"):
        wish.z -= 1.0
    if wish.length() > 1:
        wish.normalize()
    speed = 26.0 if inp.sprint else 13.0
    b.vel = wish * speed
    b.on_ground = False
    c.crouching = False
    c.sprinting = False
    if noclip:
        b.pos += b.vel * dt
        lim = m.coll.ceiling_z - 0.5
        b.pos.z = max(0.0, min(lim, b.pos.z))
        h = 60.0
        b.pos.x = max(-h, min(h, b.pos.x))
        b.pos.y = max(-h, min(h, b.pos.y))
    else:
        m.coll.move(b, dt)


def aimbot(match, p, dt):
    """Snap the view onto the closest visible enemy's head while aiming or firing."""
    inp = p.input
    if not (inp.ads or inp.fire):
        return
    eye = p.eye_pos()
    yaw = math.radians(p.yaw)
    look = Vec3(-math.sin(yaw), math.cos(yaw), 0)
    best = None
    best_score = 1e9
    for e in match.enemies_of(p):
        head = e.eye_pos() + Vec3(0, 0, 0.05)
        d = head - eye
        dist = d.length()
        if dist < 0.5 or dist > 120:
            continue
        flat = Vec3(d.x, d.y, 0)
        if flat.length() > 0.01:
            flat.normalize()
        ang = math.degrees(math.acos(max(-1.0, min(1.0, flat.dot(look)))))
        if ang > 75 or not match.coll.line_of_sight(eye, head):
            continue
        score = ang * 2 + dist * 0.3
        if score < best_score:
            best_score = score
            best = d
    if best is None:
        return
    p.yaw = math.degrees(math.atan2(-best.x, best.y))
    p.pitch = math.degrees(math.atan2(best.z, math.hypot(best.x, best.y)))


def esp(match, p):
    """Wallhack: keep every enemy marked through walls."""
    for e in match.enemies_of(p):
        e.reveal_until = match.time + 0.25
        e.revealed_to_team = p.team
