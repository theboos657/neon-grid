"""Hidden developer/debug menu.  Toggle with Ctrl+Shift+F10."""

from . import theme as T
from .widgets import UI


class DebugMenu:
    def __init__(self, app):
        self.app = app
        self.ui = UI(app)
        self.visible = False
        self.root = None
        self.info = None
        self.hazards_on = True

    def toggle(self):
        self.visible = not self.visible
        if self.visible:
            self._build()
            self.app.input.set_captured(False)
        else:
            if self.root is not None:
                self.root.removeNode()
                self.root = None
            if self.app.state == "match" and not self.app.paused:
                self.app.input.set_captured(True)

    def _player(self):
        m = self.app.match
        return m.player if m is not None else None

    def _flag(self, attr):
        p = self._player()
        if p is not None:
            setattr(p, attr, not getattr(p, attr))
            self.msg("%s = %s" % (attr, getattr(p, attr)))

    def msg(self, s):
        self.app.menus.toast("[DEBUG] " + s, 2.0)

    def _profile(self, fn, text):
        fn(self.app.storage.profile.data)
        self.app.storage.profile.save()
        self.msg(text)

    def _build(self):
        ar = self.app.getAspectRatio()
        self.root = self.app.aspect2d.attachNewNode("debug")
        self.root.setBin("gui-popup", 100)
        f = self.ui.frame(self.root, ar - 1.0, ar - 0.02, -0.98, 0.98, (0.05, 0.0, 0.05, 0.92))
        T.text(f, "DEBUG", (ar - 0.51, 0.9), 0.06, T.ORANGE, "center", self.ui.dfont)
        m = self.app.match
        items = [
            ("God mode", lambda: self._flag("god")),
            ("Infinite ammo", lambda: self._flag("infinite_ammo")),
            ("Infinite energy", lambda: self._flag("infinite_energy")),
            ("No cooldowns", lambda: self._flag("no_cooldowns")),
            ("+5000 XP", lambda: self._profile(lambda p: p.__setitem__("xp_total", p["xp_total"] + 5000),
                                               "+5000 XP")),
            ("+1000 coins", lambda: self._profile(lambda p: p.__setitem__("coins", p["coins"] + 1000),
                                                  "+1000 coins")),
            ("+5 upgrade chips", lambda: self._profile(
                lambda p: p.__setitem__("upgrade_chips", p["upgrade_chips"] + 5), "+5 chips")),
            ("Unlock all skins", self._unlock_all),
            ("Spawn bot", self._spawn_bot),
            ("Spawn drone", lambda: m and m.hazards.spawn_drone()),
            ("Trap: explosive", lambda: m and m.hazards.trigger_random_trap("explosive")),
            ("Trap: flashbang", lambda: m and m.hazards.trigger_random_trap("flash")),
            ("Trap: fire", lambda: m and m.hazards.trigger_random_trap("fire")),
            ("Big explosion here", self._boom),
            ("Kill all bots", self._kill_bots),
            ("Toggle hazards", self._toggle_hazards),
            ("Toggle FPS", self._toggle_fps),
            ("End match (win)", self._end_win),
            ("Reset profile", self._reset_profile),
        ]
        for i, (label, cmd) in enumerate(items):
            self.ui.button(f, label, (ar - 0.51, 0.8 - i * 0.082), cmd, 0.85, 0.07, 0.034,
                           align="left")
        self.info = T.text(f, "", (ar - 0.95, -0.8), 0.028, T.GREY, "left", self.ui.font)

    def _unlock_all(self):
        from ..progression import skins as SK

        def f(p):
            p["owned_weapon_skins"] = [s["id"] for s in SK.WEAPON_SKINS]
            p["owned_char_skins"] = [s["id"] for s in SK.CHAR_SKINS]
            for t in ("Glitch", "Runner", "Voltage", "Overclocked", "Neon Saint", "Gridmaster"):
                if t not in p["owned_titles"]:
                    p["owned_titles"].append(t)
        self._profile(f, "all skins unlocked")

    def _spawn_bot(self):
        m = self.app.match
        if m is None:
            return
        m.mode.add_bot(1 if m.mode.team_based else 1)
        self.msg("bot spawned")

    def _boom(self):
        m = self.app.match
        p = self._player()
        if m is None or p is None:
            return
        pos = p.eye_pos() + p.aim_dir() * 8
        m.fx.explosion(pos, 5.0, "explosive")
        m.audio.play3d("explosion", pos)

    def _kill_bots(self):
        m = self.app.match
        if m is None:
            return
        for c in m.combatants:
            if not c.is_player and c.alive:
                m.damage(c, 9999, m.player, "DEBUG", c.chest_pos())

    def _toggle_hazards(self):
        m = self.app.match
        if m is None:
            return
        m.hazards.enabled = not m.hazards.enabled
        self.msg("hazards %s" % m.hazards.enabled)

    def _toggle_fps(self):
        v = self.app.storage.settings["video"]
        v["show_fps"] = not v["show_fps"]

    def _end_win(self):
        m = self.app.match
        if m is None:
            return
        if m.player:
            m.player.score = 99
        m.end({"won": True, "place": 1, "mode": m.mode.key, "subtitle": "DEBUG"})

    def _reset_profile(self):
        st = self.app.storage
        st.profile.reset()
        st.stats.reset()
        st.highscores.reset()
        self.msg("profile reset")

    def update(self, dt):
        if not self.visible or self.info is None:
            return
        m = self.app.match or self.app.showcase
        fps = self.app.clock.getAverageFrameRate()
        s = "FPS %.0f" % fps
        if m is not None:
            s += "\nparticles %d" % sum(ps.active_count for ps in m.fx.systems)
            s += "\ncombatants %d  decoys %d" % (len(m.combatants), len(m.decoys))
            p = m.player
            if p is not None:
                s += "\npos %.1f %.1f %.1f" % (p.body.pos.x, p.body.pos.y, p.body.pos.z)
                s += "\nvel %.1f" % p.body.vel.length()
        T.set_text(self.info, s)
