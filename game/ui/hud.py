"""Minimal in-match HUD.

Elements (each independently positioned, scaled, faded and toggled from the
Settings > HUD tab or the drag-and-drop HUD editor):
    health, energy, ammo, abilities, crosshair, killfeed, matchinfo,
    notices, damage_dir
Positions are stored as fractions of the half-screen so layouts survive
resolution changes; Hebrew mirrors the layout horizontally.
"""

import math

from panda3d.core import Vec3

from neon_shared.abilities import MAX_ENERGY

from .. import i18n
from ..storage import DEFAULT_HUD_ELEMENTS
from . import theme as T

# crosshair styles: (line angles in degrees, centre dot, ring, dynamic spread allowed)
CROSS_STYLES = [
    ((0, 90, 180, 270), True, False, True),      # 0 classic
    ((), True, True, True),                      # 1 circle + dot
    ((), True, False, False),                    # 2 dot
    ((0, 90, 180, 270), False, False, True),     # 3 cross
    ((90, 180, 270), True, False, True),         # 4 T-shape
    ((45, 135, 225, 315), True, False, True),    # 5 X
    ((135, 225), True, False, False),            # 6 chevron
    ((), False, True, True),                     # 7 ring
    ((0, 90, 180, 270), True, False, False),     # 8 static plus
]
CROSS_COLORS = [(0.2, 1.0, 1.0, 1), (1, 1, 1, 1), (1.0, 0.3, 0.9, 1), (0.5, 1.0, 0.3, 1),
                (1.0, 0.95, 0.3, 1),
                (1.0, 0.55, 0.1, 1), (1.0, 0.2, 0.2, 1), (0.3, 0.5, 1.0, 1)]
ELEMENTS = list(DEFAULT_HUD_ELEMENTS.keys())


class Element:
    """Positionable HUD element root."""

    def __init__(self, hud, key):
        self.hud = hud
        self.key = key
        self.root = hud.root.attachNewNode("el_" + key)
        self.content = self.root.attachNewNode("content")
        self.side = 1        # +1 anchored left (grows right), -1 anchored right, 0 centred
        self.bounds = (-0.1, 0.1, -0.05, 0.05)   # local editor hit box

    def cfg(self):
        return self.hud.layout()[self.key]

    def place(self):
        c = self.cfg()
        ar = self.hud.app.getAspectRatio()
        fx = c["x"]
        if i18n.is_rtl():
            fx = -fx
        self.root.setPos(fx * ar, 0, c["y"])
        s = c["scale"] * self.hud.global_scale()
        self.root.setScale(s)
        self.root.setAlphaScale(c["opacity"] * self.hud.global_opacity())
        side = 0 if abs(fx) < 0.3 else (1 if fx < 0 else -1)
        if c["visible"] or self.hud.editing:
            self.root.show()
        else:
            self.root.hide()
        return side


class HUD:
    def __init__(self, app):
        self.app = app
        self.root = app.aspect2d.attachNewNode("hud")
        self.root.hide()
        self.tex = app.ui_textures
        self.match = None
        self.editing = False
        self.visible = False
        self.elements = {}
        self.kill_lines = []
        self.notices = []
        self.dmg_arcs = []
        self.hit_t = 0.0
        self.hit_kind = 0
        self.flash_t = 0.0
        self.flash_max = 1.0
        self.flash_a = 0.0
        self.warn_t = {}
        self.warn_pos = {}
        self.big_t = 0.0
        self.cap_t = 0.0
        self.show_scores = False
        self.fps_acc = 0.0
        self.fps_frames = 0
        self._build()

    # ------------------------------------------------------------------ config
    def layout(self):
        return self.app.storage.settings["hud"]["elements"]

    def global_scale(self):
        return self.app.storage.settings["hud"]["scale"]

    def global_opacity(self):
        return self.app.storage.settings["hud"]["opacity"]

    # ------------------------------------------------------------------ build
    def _build(self):
        for n in list(self.root.getChildren()):
            n.removeNode()
        self.elements = {}
        f_disp = self.app.fonts.get("display")
        f_ui = self.app.fonts.get("ui")
        self.f_disp = f_disp
        self.f_ui = f_ui
        # full-screen overlays (not part of the editable layout)
        self.overlay = self.root.attachNewNode("overlay")
        self.overlay.setBin("fixed", 0)
        self.vignette = T.textured_card(self.overlay, self.tex.vignette, -2.5, 2.5, -1, 1,
                                        (0.8, 0.0, 0.05, 0))
        self.flash_card = T.card(self.overlay, -3, 3, -1, 1, (1, 1, 1, 0))
        self.scope = self.root.attachNewNode("scope")
        T.textured_card(self.scope, self.tex.scope, -1, 1, -1, 1)
        T.card(self.scope, -3, -1, -1, 1, (0, 0, 0, 1))
        T.card(self.scope, 1, 3, -1, 1, (0, 0, 0, 1))
        self.scope.hide()
        for key in ELEMENTS:
            self.elements[key] = Element(self, key)
        self._build_contents()
        # center messages
        self.big = T.text(self.root, "", (0, 0.35), 0.13, T.CYAN, "center", f_disp)
        self.big_sub = T.text(self.root, "", (0, 0.24), 0.055, T.WHITE, "center", f_ui)
        self.caption = T.text(self.root, "", (0, 0.55), 0.075, T.GOLD, "center", f_disp)
        self.countdown = T.text(self.root, "", (0, 0.1), 0.22, T.CYAN, "center", f_disp)
        self.respawn = T.text(self.root, "", (0, -0.2), 0.07, T.WHITE, "center", f_ui)
        self.fps = T.text(self.root, "", (0, 0), 0.04, T.GREY, "left", f_ui)
        self.fps.reparentTo(self.app.a2dTopLeft)
        self.fps.setPos(0.03, 0, -0.06)
        self.fps.hide()
        self.warn_text = T.text(self.root, "", (0, 0.2), 0.06, T.ORANGE, "center", f_disp)
        self.warn_arrow = T.textured_card(self.root, self.tex.arc, -0.3, 0.3, -0.3, 0.3,
                                          (1, 0.5, 0.1, 0))
        # scoreboard
        self.scoreboard = self.root.attachNewNode("scoreboard")
        self.scoreboard.hide()
        self.place_all()

    def _build_contents(self):
        """(Re)build element internals according to their side."""
        f_disp = self.f_disp
        f_ui = self.f_ui
        for key, el in self.elements.items():
            for ch in list(el.content.getChildren()):
                ch.removeNode()
            el.side = el.place()
        s = self.elements
        # --- health
        e = s["health"]
        sd = e.side or 1
        W = 0.62
        x0, x1 = (0, W) if sd > 0 else (-W, 0)
        T.card(e.content, x0, x1, 0.0, 0.05, (0.02, 0.05, 0.07, 0.75))
        self.hp_fill = T.card(e.content, 0, W, 0.006, 0.044, T.CYAN)
        self.hp_fill.setX(x0)
        self.sh_fill = T.card(e.content, 0, W, 0.034, 0.044, (0.8, 0.9, 1.0, 0.95))
        self.sh_fill.setX(x0)
        for i in range(1, 10):
            T.card(e.content, x0 + W * i / 10 - 0.002, x0 + W * i / 10 + 0.002, 0.004, 0.046,
                   (0, 0, 0, 0.6))
        align = "left" if sd > 0 else "right"
        self.hp_text = T.text(e.content, "100", (x0 if sd > 0 else x1, 0.07), 0.075, T.WHITE,
                              align, f_disp)
        self.hp_label = T.text(e.content, i18n.t("hp"), ((x0 + 0.17) if sd > 0 else (x1 - 0.17),
                                                         0.07), 0.035, T.CYAN, align, f_ui)
        e.bounds = (x0 - 0.02, x1 + 0.02, -0.01, 0.15)
        self.hp_x0 = x0
        self.hp_w = W
        # --- energy
        e = s["energy"]
        sd = e.side or 1
        W2 = 0.45
        x0, x1 = (0, W2) if sd > 0 else (-W2, 0)
        T.card(e.content, x0, x1, 0.0, 0.022, (0.02, 0.05, 0.07, 0.75))
        self.en_fill = T.card(e.content, 0, W2, 0.004, 0.018, T.GREEN)
        self.en_fill.setX(x0)
        self.en_text = T.text(e.content, "100", ((x1 + 0.015) if sd > 0 else (x0 - 0.015), 0.0),
                              0.032, T.GREEN, "left" if sd > 0 else "right", f_ui)
        e.bounds = (x0 - 0.02, x1 + 0.1, -0.01, 0.035)
        self.en_x0 = x0
        self.en_w = W2
        # --- ammo
        e = s["ammo"]
        sd = e.side or -1
        align = "right" if sd < 0 else "left"
        self.ammo_mag = T.text(e.content, "30", (0 if sd > 0 else -0.16, 0.02), 0.11, T.WHITE,
                               align, f_disp)
        self.ammo_res = T.text(e.content, "/ 120", (0.14 if sd > 0 else 0, 0.02), 0.045, T.GREY,
                               align, f_ui)
        self.ammo_name = T.text(e.content, "", (0 if sd > 0 else 0, 0.12), 0.038, T.CYAN, align,
                                f_ui)
        self.ammo_tier = T.text(e.content, "", (0 if sd > 0 else 0, 0.165), 0.03, T.GOLD, align,
                                f_ui)
        self.reload_bg = T.card(e.content, -0.3 if sd < 0 else 0, 0 if sd < 0 else 0.3, -0.02,
                                -0.008, (0.1, 0.2, 0.25, 0.8))
        self.reload_fill = T.card(e.content, 0, 0.3, -0.02, -0.008, T.CYAN)
        self.reload_x0 = -0.3 if sd < 0 else 0
        self.reload_fill.setX(self.reload_x0)
        e.bounds = (-0.35, 0.02, -0.03, 0.2) if sd < 0 else (-0.02, 0.35, -0.03, 0.2)
        # --- abilities
        e = s["abilities"]
        self.ab_slots = []
        for i in range(2):
            x = (-0.09 if i == 0 else 0.09)
            if i18n.is_rtl():
                x = -x
            node = e.content.attachNewNode("ab%d" % i)
            node.setPos(x, 0, 0)
            T.card(node, -0.07, 0.07, -0.07, 0.07, (0.02, 0.05, 0.07, 0.8))
            fill = T.card(node, -0.07, 0.07, -0.07, 0.07, (0.1, 0.8, 1.0, 0.35))
            border = T.card(node, -0.07, 0.07, 0.064, 0.07, T.CYAN)
            icon = T.text(node, "", (0, -0.025), 0.07, T.WHITE, "center", f_disp)
            key = T.text(node, "", (0, -0.105), 0.03, T.GREY, "center", f_ui)
            cd = T.text(node, "", (0, 0.085), 0.03, T.WHITE, "center", f_ui)
            self.ab_slots.append((node, fill, border, icon, key, cd))
        e.bounds = (-0.17, 0.17, -0.13, 0.12)
        # --- crosshair
        e = s["crosshair"]
        self.cross_parts = []
        for i in range(4):
            holder = e.content.attachNewNode("cp")
            shape = holder.attachNewNode("shape")
            outline = T.card(shape, -0.0048, 0.0048, -0.0025, 0.0265, (0, 0, 0, 0.55))
            core = T.card(shape, -0.0026, 0.0026, 0.0, 0.024, (1, 1, 1, 1))
            self.cross_parts.append((holder, core, outline, shape))
        dot = e.content.attachNewNode("dot")
        self.cross_dot_outline = T.card(dot, -0.0055, 0.0055, -0.0055, 0.0055, (0, 0, 0, 0.55))
        self.cross_dot_core = T.card(dot, -0.0033, 0.0033, -0.0033, 0.0033, (1, 1, 1, 1))
        self.cross_dot = dot
        # optic reticles shown while aiming down sights
        self.reticle = e.content.attachNewNode("reticle")
        self.ret_dot = T.card(self.reticle, -0.004, 0.004, -0.004, 0.004, (1, 0.15, 0.1, 1))
        self.ret_ring = T.textured_card(self.reticle, self.tex.ring, -0.045, 0.045, -0.045, 0.045,
                                        (1, 0.25, 0.2, 0.9))
        self.reticle.hide()
        self.cross_ring = T.textured_card(e.content, self.tex.ring, -0.028, 0.028, -0.028, 0.028)
        self.hit_parts = []
        for i in range(4):
            n = T.card(e.content, -0.0032, 0.0032, 0.014, 0.036, (1, 1, 1, 1))
            n.setR(45 + i * 90)
            self.hit_parts.append(n)
        self.port_bg = T.card(e.content, -0.06, 0.06, -0.075, -0.066, (0.05, 0.1, 0.1, 0.8))
        self.port_fill = T.card(e.content, 0, 0.12, -0.075, -0.066, T.GREEN)
        self.port_fill.setX(-0.06)
        self.port_txt = T.text(e.content, i18n.t("charging"), (0, -0.11), 0.03, T.GREEN, "center",
                               f_ui)
        self.target_name = T.text(e.content, "", (0, 0.05), 0.032, T.RED, "center", f_ui)
        e.bounds = (-0.06, 0.06, -0.06, 0.06)
        # --- kill feed
        e = s["killfeed"]
        sd = e.side or -1
        self.kill_nodes = []
        for i in range(5):
            t = T.text(e.content, "", (0, -i * 0.055), 0.036, T.WHITE,
                       "right" if sd < 0 else "left", f_ui)
            self.kill_nodes.append(t)
        e.bounds = (-0.8, 0.02, -0.25, 0.05) if sd < 0 else (-0.02, 0.8, -0.25, 0.05)
        # --- match info
        e = s["matchinfo"]
        self.mi_big = T.text(e.content, "", (0, -0.02), 0.07, T.WHITE, "center", f_disp)
        self.mi_small = T.text(e.content, "", (0, -0.075), 0.035, T.CYAN, "center", f_ui)
        e.bounds = (-0.4, 0.4, -0.09, 0.06)
        # --- notices
        e = s["notices"]
        self.notice_nodes = [T.text(e.content, "", (0, -i * 0.055), 0.042, T.WHITE, "center", f_ui)
                             for i in range(4)]
        e.bounds = (-0.4, 0.4, -0.2, 0.05)
        # --- damage direction
        e = s["damage_dir"]
        self.dmg_arcs = []
        for i in range(6):
            n = T.textured_card(e.content, self.tex.arc, -0.34, 0.34, -0.34, 0.34, (1, 0.2, 0.15, 0))
            self.dmg_arcs.append([n, 0.0, 0.0])
        e.bounds = (-0.3, 0.3, -0.3, 0.3)

    def rebuild(self):
        """Call after language/layout/font changes."""
        self._build()
        if self.match is not None:
            self.root.show()

    def place_all(self):
        need_rebuild = False
        for el in self.elements.values():
            side = el.place()
            if side != el.side:
                need_rebuild = True
        if need_rebuild:
            self._build_contents()

    # ------------------------------------------------------------------ lifecycle
    def begin_match(self, match):
        self.match = match
        self.kill_lines = []
        self.notices = []
        self.big_t = self.cap_t = 0.0
        self.flash_a = 0.0
        self.place_all()
        self.root.show()
        self._refresh_ability_icons()

    def end_match(self):
        self.match = None
        self.root.hide()
        self.scoreboard.hide()
        self.fps.hide()

    def _refresh_ability_icons(self):
        m = self.match
        if m is None or m.player is None:
            return
        b = self.app.storage.settings["controls"]["bindings"]
        from ..input import key_label
        for i, slot in enumerate(self.ab_slots):
            node, fill, border, icon, key, cd = slot
            if i < len(m.player.abilities):
                ab = m.player.abilities[i]
                T.set_text(icon, ab.data["icon"])
                T.set_text(key, key_label(b["ability%d" % (i + 1)]))

    # ------------------------------------------------------------------ events
    def add_kill(self, killer, victim, weapon, headshot, by_player, of_player, kc, vc):
        s = "%s  [%s%s]  %s" % (killer, weapon, " • HS" if headshot else "", victim)
        col = T.CYAN if by_player else (T.RED if of_player else T.WHITE)
        self.kill_lines.insert(0, [i18n.visual(s), col, 5.0])
        self.kill_lines = self.kill_lines[:5]

    def notice(self, s, color=T.WHITE, dur=1.5):
        self.notices.insert(0, [s, color, dur])
        self.notices = self.notices[:4]

    def big_message(self, s, sub="", dur=2.5):
        T.set_text(self.big, s)
        T.set_text(self.big_sub, sub)
        self.big_t = dur

    def announcer_caption(self, s):
        T.set_text(self.caption, s)
        self.cap_t = 1.6

    def hit_marker(self, kill=False, head=False):
        if not self.app.storage.settings["gameplay"]["hit_markers"]:
            return
        self.hit_t = 0.25 if kill else 0.15
        self.hit_kind = 2 if kill else (1 if head else 0)

    def damage_taken(self, amount, angle):
        if angle is None:
            return
        best = min(self.dmg_arcs, key=lambda a: a[1])
        best[1] = 1.2
        best[2] = angle

    def flash(self, strength, duration):
        self.flash_a = max(self.flash_a, strength)
        self.flash_t = duration
        self.flash_max = duration

    def warn(self, kind, pos):
        self.warn_t[kind] = 0.25
        self.warn_pos[kind] = Vec3(pos)

    # ------------------------------------------------------------------ update
    def update(self, dt, m):
        app = self.app
        p = m.player
        st = app.storage.settings.data
        # fps
        if st["video"]["show_fps"]:
            self.fps.show()
            self.fps_acc += dt
            self.fps_frames += 1
            if self.fps_acc > 0.5:
                T.set_text(self.fps, "%d FPS" % round(self.fps_frames / self.fps_acc))
                self.fps_acc = 0.0
                self.fps_frames = 0
        else:
            self.fps.hide()
        # match info
        big, small = m.mode.hud_info()
        T.set_text(self.mi_big, big)
        T.set_text(self.mi_small, small)
        # countdown
        if m.state == "countdown":
            n = int(math.ceil(m.state_t))
            T.set_text(self.countdown, str(max(1, n)) if n > 0 else "")
        else:
            T.set_text(self.countdown, "")
        # big message / caption timers
        if self.big_t > 0:
            self.big_t -= dt
            a = min(1.0, self.big_t * 2)
            self.big.setAlphaScale(a)
            self.big_sub.setAlphaScale(a)
            if self.big_t <= 0:
                T.set_text(self.big, "")
                T.set_text(self.big_sub, "")
        if self.cap_t > 0:
            self.cap_t -= dt
            self.caption.setAlphaScale(min(1.0, self.cap_t * 3))
            self.caption.setScale(0.075 * (1 + max(0, self.cap_t - 1.3) * 1.2))
            if self.cap_t <= 0:
                T.set_text(self.caption, "")
        # kill feed
        for i, node in enumerate(self.kill_nodes):
            if i < len(self.kill_lines):
                line = self.kill_lines[i]
                line[2] -= dt
                T.set_text(node, line[0])
                node.node().setTextColor(*line[1])
                node.setAlphaScale(min(1.0, line[2]))
            else:
                T.set_text(node, "")
        self.kill_lines = [k for k in self.kill_lines if k[2] > 0]
        # notices
        for i, node in enumerate(self.notice_nodes):
            if i < len(self.notices):
                n = self.notices[i]
                n[2] -= dt
                T.set_text(node, n[0])
                node.node().setTextColor(*n[1])
                node.setAlphaScale(min(1.0, n[2] * 2))
            else:
                T.set_text(node, "")
        self.notices = [n for n in self.notices if n[2] > 0]
        # scoreboard
        want_sb = app.input.down("scoreboard") or m.state == "ended"
        if want_sb != self.show_scores:
            self.show_scores = want_sb
            if want_sb:
                self._build_scoreboard(m)
                self.scoreboard.show()
            else:
                self.scoreboard.hide()
        elif want_sb and int(m.time * 4) != int((m.time - dt) * 4):
            self._build_scoreboard(m)
        if p is None:
            return
        self._update_player(dt, m, p, st)

    def _update_player(self, dt, m, p, st):
        # health / shield
        hpk = max(0.0, p.health / p.max_health)
        self.hp_fill.setSx(max(0.001, hpk))
        low = hpk < 0.35
        if low:
            pulse = 0.6 + 0.4 * math.sin(m.time * 8)
            self.hp_fill.setColor(1.0, 0.25, 0.25, 1)
            self.vignette.setColor(0.8, 0.0, 0.05, (0.35 - hpk) * 1.6 * pulse)
        else:
            self.hp_fill.setColor(*T.CYAN)
            self.vignette.setColor(0.8, 0, 0.05, 0)
        T.set_text(self.hp_text, str(int(math.ceil(p.health))))
        if p.shield_hp > 0 and m.time < p.shield_until:
            self.sh_fill.show()
            self.sh_fill.setSx(max(0.001, p.shield_hp / 60.0))
        else:
            self.sh_fill.hide()
        # energy
        ek = p.energy / MAX_ENERGY
        self.en_fill.setSx(max(0.001, ek))
        T.set_text(self.en_text, str(int(p.energy)))
        # ammo
        ws = p.weapon()
        if ws.melee:
            T.set_text(self.ammo_mag, "∞" if False else "--")
            T.set_text(self.ammo_res, "")
        else:
            T.set_text(self.ammo_mag, str(ws.mag))
            T.set_text(self.ammo_res, "/ %d" % ws.reserve)
            self.ammo_mag.node().setTextColor(*(T.RED if ws.mag <= ws.stats["mag"] * 0.2
                                                else T.WHITE))
        name = ws.name.upper()
        if ws.reloading:
            name = i18n.t("reloading")
        elif not ws.melee and ws.mag == 0 and ws.reserve == 0:
            name = i18n.t("no_ammo")
        T.set_text(self.ammo_name, name)
        T.set_text(self.ammo_tier, "TIER " + "•" * ws.tier + "·" * (5 - ws.tier))
        if ws.reloading:
            self.reload_bg.show()
            self.reload_fill.show()
            self.reload_fill.setSx(max(0.001, ws.reload_fraction()))
        else:
            self.reload_bg.hide()
            self.reload_fill.hide()
        # abilities
        for i, slot in enumerate(self.ab_slots):
            node, fill, border, icon, key, cd = slot
            if i >= len(p.abilities):
                node.hide()
                continue
            node.show()
            ab = p.abilities[i]
            fr = ab.fraction()
            fill.setSz(max(0.001, fr))
            fill.setZ(-0.07 * (1 - fr))
            locked = m.time < p.ability_lock_until
            if ab.ready and not locked:
                enough = p.energy >= ab.data["energy"] or p.infinite_energy
                col = T.CYAN if enough else T.ORANGE
                fill.setColor(col[0], col[1], col[2], 0.35)
                border.setColor(*col)
                T.set_text(cd, "")
            else:
                fill.setColor(0.3, 0.4, 0.45, 0.4)
                border.setColor(0.3, 0.4, 0.45, 1)
                T.set_text(cd, "%d" % math.ceil(ab.cooldown_left) if not locked else "EMP")
        # crosshair
        self._update_crosshair(dt, m, p, ws, st)
        # damage direction arcs
        for arc in self.dmg_arcs:
            n, life, ang = arc
            if life > 0:
                arc[1] -= dt
                n.setR(-ang)
                n.setColor(1, 0.2, 0.15, min(1.0, arc[1]) * 0.9)
            else:
                n.setColor(1, 0.2, 0.15, 0)
        # flash overlay
        if self.flash_t > 0:
            self.flash_t -= dt
            k = self.flash_a * min(1.0, self.flash_t / (self.flash_max * 0.6))
            self.flash_card.setColor(1, 1, 1, max(0, k))
        else:
            self.flash_card.setColor(1, 1, 1, 0)
            self.flash_a = 0.0
        # threat warnings
        wtxt = ""
        wpos = None
        for kind in list(self.warn_t.keys()):
            self.warn_t[kind] -= dt
            if self.warn_t[kind] <= 0:
                del self.warn_t[kind]
                continue
            wtxt = i18n.t("turret_lock" if kind == "turret" else "drone_lock")
            wpos = self.warn_pos.get(kind)
        if wtxt and int(m.time * 6) % 2 == 0:
            T.set_text(self.warn_text, wtxt)
        else:
            T.set_text(self.warn_text, "")
        if wpos is not None:
            d = wpos - p.body.pos
            ang = math.degrees(math.atan2(-d.x, d.y)) - p.yaw
            self.warn_arrow.setR(-ang)
            self.warn_arrow.setColor(1, 0.55, 0.1, 0.9)
        else:
            self.warn_arrow.setColor(1, 0.55, 0.1, 0)
        # respawn / eliminated
        if not p.alive and m.state == "live":
            if p.eliminated or (m.mode.lives is not None and (p.lives or 0) <= 0
                                and not m.mode.can_respawn(p)):
                T.set_text(self.respawn, i18n.t("eliminated") + "   " + i18n.t("spectating"))
            else:
                T.set_text(self.respawn, i18n.t("respawn_in", n=max(1, int(math.ceil(p.respawn_timer)))))
        else:
            T.set_text(self.respawn, "")
        # scope overlay / optic reticles
        vm = m.viewmodel
        ret = ws.stats.get("reticle")
        aiming = p.alive and p.input.ads and not ws.melee and vm.ads_k > 0.8
        if aiming and ws.stats["scoped"]:
            if not self.app.scope.ok:
                self.scope.show()           # fallback: flat overlay
            else:
                self.scope.hide()           # the real scope lens is on the weapon
            self.elements["crosshair"].root.hide()
        else:
            self.scope.hide()
            self.elements["crosshair"].place()
        self.optic_active = aiming and ret in ("dot", "holo")
        if self.optic_active:
            self.reticle.show()
            if ret == "dot":
                self.ret_ring.hide()
            else:
                self.ret_ring.show()
        else:
            self.reticle.hide()

    def _update_crosshair(self, dt, m, p, ws, st):
        g = st["gameplay"]
        from ..combat.firing import effective_spread
        spread = effective_spread(p, ws) if not ws.melee else 1.0
        # convert spread (deg) to screen units given the current fov
        fov = max(20.0, self.app.camLens.getFov()[0])
        dyn = math.tan(math.radians(min(spread, 30))) / math.tan(math.radians(fov / 2)) \
            * self.app.getAspectRatio()
        apply_crosshair(self, g, dyn)
        if getattr(self, "optic_active", False):
            for n, core, outline, shape in self.cross_parts:
                n.hide()
            self.cross_dot.hide()
            self.cross_ring.hide()
        # hit marker
        if self.hit_t > 0:
            self.hit_t -= dt
            hc = [(1, 1, 1, 1), (1.0, 0.85, 0.2, 1), (1.0, 0.2, 0.2, 1)][self.hit_kind]
            s = 1.0 + (0.4 if self.hit_kind == 2 else 0.0)
            for n in self.hit_parts:
                n.show()
                n.setColor(hc[0], hc[1], hc[2], min(1.0, self.hit_t * 8))
                n.setScale(s)
        else:
            for n in self.hit_parts:
                n.hide()
        # charging port progress
        if p.port_progress > 0:
            self.port_bg.show()
            self.port_fill.show()
            self.port_txt.show()
            self.port_fill.setSx(max(0.001, p.port_progress))
        else:
            self.port_bg.hide()
            self.port_fill.hide()
            self.port_txt.hide()
        tgt = m.crosshair_target
        T.set_text(self.target_name, tgt.name if tgt is not None and m.hostile(p, tgt) else "")

    def _build_scoreboard(self, m):
        sb = self.scoreboard
        for ch in list(sb.getChildren()):
            ch.removeNode()
        rows = m.mode.scoreboard()
        h = 0.14 + 0.065 * len(rows)
        T.card(sb, -0.85, 0.85, 0.45 - h, 0.5, T.PANEL)
        T.card(sb, -0.85, 0.85, 0.494, 0.5, T.CYAN)
        f = self.f_ui
        rtl = i18n.is_rtl()
        cols = [(-0.78, "sb_name", "left"), (0.2, "sb_kills", "center"), (0.35, "sb_deaths", "center"),
                (0.52, "sb_score", "center"), (0.7, "sb_ping", "center")]
        for x, key, al in cols:
            xx = -x if rtl else x
            al2 = T.ui_align(al)
            T.text(sb, i18n.t(key), (xx, 0.42), 0.035, T.CYAN, al2, f)
        for i, (name, k, d, sc, ping, me, team, elim) in enumerate(rows):
            y = 0.35 - i * 0.065
            if me:
                T.card(sb, -0.83, 0.83, y - 0.018, y + 0.045, (0.1, 0.5, 0.6, 0.35))
            col = T.CYAN if me else T.WHITE
            if m.mode.team_based:
                col = (0.4, 0.95, 1.0, 1) if team == 0 else (1.0, 0.4, 0.45, 1)
            if elim:
                col = T.GREY
            vals = [name, str(k), str(d), str(sc), str(ping) if ping else "-"]
            for (x, _, al), v in zip(cols, vals):
                xx = -x if rtl else x
                T.text(sb, v, (xx, y), 0.04, col, T.ui_align(al), f)

    # ------------------------------------------------------------------ editor
    def element_at(self, x, y):
        for key in reversed(ELEMENTS):
            el = self.elements[key]
            p = el.root.getPos()
            s = el.root.getScale()[0]
            b = el.bounds
            if p.x + b[0] * s <= x <= p.x + b[1] * s and p.z + b[2] * s <= y <= p.z + b[3] * s:
                return key
        return None


def apply_crosshair(h, g, dynamic_gap):
    """Configure crosshair parts on ``h`` (the HUD, or the settings preview) from the
    gameplay settings ``g``.  ``dynamic_gap`` is the current spread in screen units."""
    style = g.get("crosshair_style", 0) % len(CROSS_STYLES)
    angles, dot, ring, allow_dyn = CROSS_STYLES[style]
    col = CROSS_COLORS[g.get("crosshair_color", 0) % len(CROSS_COLORS)]
    size = g.get("crosshair_size", 1.0)
    thick = g.get("crosshair_thickness", 1.0)
    outline = g.get("crosshair_outline", True)
    gap = 0.012 + g.get("crosshair_gap", 0.0) * 0.01
    if allow_dyn and g.get("crosshair_dynamic", True):
        gap += dynamic_gap
    gap = min(gap, 0.25)
    for i, (n, core, ol, shape) in enumerate(h.cross_parts):
        if i < len(angles):
            a = angles[i]
            r = math.radians(a)
            n.show()
            n.setPos(math.sin(r) * gap, 0, math.cos(r) * gap)
            n.setR(a)
            shape.setScale(thick, 1, size)
            core.setColor(*col)
            if outline:
                ol.show()
            else:
                ol.hide()
        else:
            n.hide()
    if dot:
        h.cross_dot.show()
        h.cross_dot.setScale(0.6 + 0.4 * thick)
        h.cross_dot_core.setColor(*col)
        if outline:
            h.cross_dot_outline.show()
        else:
            h.cross_dot_outline.hide()
    else:
        h.cross_dot.hide()
    if ring:
        h.cross_ring.show()
        h.cross_ring.setScale((0.5 + gap * 20) * size)
        h.cross_ring.setColor(*col)
    else:
        h.cross_ring.hide()


class CrosshairPreview:
    """Stand-alone crosshair drawn in the settings screen."""

    def __init__(self, parent, tex, pos, scale=2.5):
        self.root = parent.attachNewNode("xhair_preview")
        self.root.setPos(pos[0], 0, pos[1])
        self.root.setScale(scale)
        T.card(self.root, -0.06, 0.06, -0.06, 0.06, (0.2, 0.3, 0.35, 0.35))
        self.cross_parts = []
        for i in range(4):
            holder = self.root.attachNewNode("cp")
            shape = holder.attachNewNode("shape")
            ol = T.card(shape, -0.0048, 0.0048, -0.0025, 0.0265, (0, 0, 0, 0.55))
            core = T.card(shape, -0.0026, 0.0026, 0.0, 0.024, (1, 1, 1, 1))
            self.cross_parts.append((holder, core, ol, shape))
        dot = self.root.attachNewNode("dot")
        self.cross_dot_outline = T.card(dot, -0.0055, 0.0055, -0.0055, 0.0055, (0, 0, 0, 0.55))
        self.cross_dot_core = T.card(dot, -0.0033, 0.0033, -0.0033, 0.0033, (1, 1, 1, 1))
        self.cross_dot = dot
        self.cross_ring = T.textured_card(self.root, tex.ring, -0.028, 0.028, -0.028, 0.028)

    def update(self, g):
        apply_crosshair(self, g, 0.01)
