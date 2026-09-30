"""All menu screens.

Each screen is rebuilt from scratch when shown, so language switches (and the
RTL mirroring that comes with Hebrew) apply instantly everywhere.
"""

import math

from panda3d.core import ColorBlendAttrib, WindowProperties

from neon_shared import weapons as W
from neon_shared.abilities import ABILITIES, BY_ID as AB_BY_ID, IDS as AB_IDS

from .. import i18n, story
from ..input import key_label
from ..progression import achievements as ACH
from ..progression import battlepass as BP
from ..progression import shop as SH
from ..progression import skins as SK
from ..storage import DEFAULT_HUD_ELEMENTS, DEFAULT_BINDINGS
from . import theme as T
from .widgets import UI

RESOLUTIONS = [(1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2560, 1440), (3840, 2160)]
FPS_CAPS = [0, 60, 120, 144, 165, 240]
TIME_LIMITS = [0, 5, 8, 10, 15, 20]
SCORE_LIMITS = [10, 15, 20, 25, 30, 40, 50]
MODES = ["ffa", "duel", "team", "coop", "endless"]
MAPS = ["grid", "forest", "backrooms", "random"]
DIFFS = ["easy", "normal", "hard", "nightmare"]


def reward_text(reward):
    kind, val = reward
    if kind == "coins":
        return i18n.t("rw_coins", n=val)
    if kind == "chip":
        return i18n.t("rw_chip") + (" x%d" % val if val > 1 else "")
    if kind == "wskin":
        return i18n.t("rw_wskin", name=SK.weapon_skin(val)["name"])
    if kind == "cskin":
        return i18n.t("rw_cskin", name=SK.char_skin(val)["name"])
    if kind == "title":
        return i18n.t("rw_title", name=val)
    return str(val)


class Menus:
    def __init__(self, app):
        self.app = app
        self.ui = UI(app)
        self.root = None
        self.current = None
        self.prev = None
        self.settings_return = "main"
        self.settings_tab = "video"
        self.loadout_focus = "primary"
        self.toast_node = None
        self.toast_t = 0.0
        self.anim = []
        self.t = 0.0
        self.hud_edit = None
        self.lobby_sig = None
        self.binding_action = None

    # ================================================================== core
    def _clear(self):
        if self.root is not None:
            self.root.removeNode()
        self.root = None
        self.anim = []

    def hide_all(self):
        self._clear()
        self.current = None
        if self.hud_edit:
            self._end_hud_edit(save=False)

    def show(self, name, **kw):
        self._clear()
        self.prev = self.current
        self.current = name
        self.root = self.app.aspect2d.attachNewNode("menu_" + name)
        getattr(self, "_build_" + name)(**kw)

    def toast(self, s, dur=2.5):
        if self.toast_node is not None:
            self.toast_node.removeNode()
        self.toast_node = T.text(self.app.aspect2d, s, (0, 0.9), 0.045, T.GOLD, "center",
                                 self.ui.font)
        self.toast_t = dur

    def handle_escape(self):
        c = self.current
        if self.hud_edit:
            self._end_hud_edit(save=True)
            self.show("settings", tab="hud")
            return True
        if self.binding_action:
            return True
        if c in ("play", "multiplayer", "loadout", "battlepass", "locker", "career", "story",
                 "shop"):
            self.app.audio.ui("ui_back")
            self.show("main")
            return True
        if c == "gunsmith":
            self.app.audio.ui("ui_back")
            self.gs_preview = {}
            self.show(getattr(self, "gs_return", "loadout"))
            return True
        if c == "settings":
            self._save_settings()
            self.app.audio.ui("ui_back")
            self.show(self.settings_return)
            return True
        if c == "lobby":
            return True
        if c == "rooms":
            self._stop_browser()
            self.app.audio.ui("ui_back")
            self.show("multiplayer")
            return True
        if c == "results":
            self.show("main")
            return True
        return False

    def update(self, dt):
        self.t += dt
        if self.toast_t > 0:
            self.toast_t -= dt
            if self.toast_t <= 0 and self.toast_node is not None:
                self.toast_node.removeNode()
                self.toast_node = None
        for fn in self.anim:
            fn(self.t)
        if self.hud_edit:
            self._hud_edit_update(dt)
        if self.current == "lobby":
            self._lobby_poll()
        if self.current == "rooms":
            self._rooms_poll()

    # ================================================================== shared pieces
    def _backdrop(self, side=True):
        ar = self.app.getAspectRatio()
        # dark wash over the showcase scene
        T.card(self.root, -ar, ar, -1, 1, (0, 0.01, 0.015, 0.45 if side else 0.62))
        if side:
            x0, x1 = (-ar, -ar + 1.1) if not i18n.is_rtl() else (ar - 1.1, ar)
            T.card(self.root, x0, x1, -1, 1, (0, 0.02, 0.03, 0.55))

    def _header(self, key):
        ar = self.app.getAspectRatio()
        x = T.mx(-ar + 0.12)
        al = T.ui_align("left")
        T.text(self.root, i18n.t(key), (x, 0.82), 0.09, T.CYAN, al, self.ui.dfont)
        T.card(self.root, min(x, x + (0.9 if al == "left" else -0.9)),
               max(x, x + (0.9 if al == "left" else -0.9)), 0.79, 0.795, T.CYAN)

    def _back_button(self, target="main", cmd=None):
        ar = self.app.getAspectRatio()
        def go():
            if cmd:
                cmd()
            self.show(target)
        self.ui.button(self.root, i18n.t("back"), (T.mx(-ar + 0.35), -0.88), go, 0.45,
                       sound="ui_back")

    def _logo(self, parent, pos, scale):
        """Neon logo: layered glow copies of the title text + flicker."""
        node = parent.attachNewNode("logo")
        node.setPos(pos[0], 0, pos[1])
        font = self.app.fonts._load("bahnschrift.ttf") or self.ui.dfont
        glow = T.textured_card(node, self.app.ui_textures.glow, -scale * 5.5, scale * 5.5,
                               -scale * 1.1, scale * 1.9, (0.1, 0.75, 1.0, 0.28))
        glow.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add,
                                             ColorBlendAttrib.O_incoming_alpha,
                                             ColorBlendAttrib.O_one))
        layers = []
        for i, (s, a) in enumerate(((1.06, 0.12), (1.035, 0.18), (1.015, 0.3))):
            t = T.text(node, "NEON GRID", (0, 0), scale * s, (0.1, 0.9, 1.0, a), "center", font,
                       shadow=False)
            t.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add,
                                              ColorBlendAttrib.O_incoming_alpha,
                                              ColorBlendAttrib.O_one))
            layers.append(t)
        core = T.text(node, "NEON GRID", (0, 0), scale, (0.85, 1.0, 1.0, 1), "center", font,
                      shadow=False)
        T.text(node, i18n.t("subtitle"), (0, -scale * 0.62), max(0.032, scale * 0.24),
                     (0.2, 0.9, 1.0, 1), "center", self.ui.font, shadow=False)
        T.card(node, -scale * 3.2, scale * 3.2, -scale * 0.3, -scale * 0.285, (0.1, 0.9, 1.0, 0.8))

        def flicker(t):
            f = 1.0
            ph = math.sin(t * 7.1) * math.sin(t * 2.3)
            if ph > 0.96:
                f = 0.35
            core.setAlphaScale(f)
            for lay in layers:
                lay.setAlphaScale(f * (0.8 + 0.2 * math.sin(t * 2.0)))
            glow.setAlphaScale(0.75 + 0.25 * math.sin(t * 1.3))
        self.anim.append(flicker)
        return node

    # ================================================================== title
    def _build_title(self):
        ar = self.app.getAspectRatio()
        T.card(self.root, -ar, ar, -1, 1, (0, 0.01, 0.015, 0.35))
        self._logo(self.root, (0, 0.2), 0.3)
        prompt = T.text(self.root, i18n.t("press_start"), (0, -0.45), 0.045, T.WHITE, "center",
                        self.ui.font)
        T.text(self.root, "v1.0  //  " + ("EN" if not i18n.is_rtl() else "HE"), (ar - 0.05, -0.95),
               0.03, T.GREY, "right", self.ui.font)
        self.anim.append(lambda t: prompt.setAlphaScale(0.4 + 0.6 * abs(math.sin(t * 2))))

        def go(_name):
            self.app.audio.ui("ui_click")
            self.show("main")
        self.app.input.capture_next(go)

    # ================================================================== main
    def _build_main(self):
        self.app.input.capture_callback = None
        self._backdrop()
        ar = self.app.getAspectRatio()
        rtl = i18n.is_rtl()
        lx = -ar + 0.55 if not rtl else ar - 0.55
        self._logo(self.root, (lx, 0.72), 0.12)
        items = [("play", lambda: self.show("play")),
                 ("multiplayer", lambda: self.show("multiplayer")),
                 ("story", lambda: self.show("story")),
                 ("loadout", lambda: self.show("loadout")),
                 ("shop", lambda: self.show("shop")),
                 ("battlepass", lambda: self.show("battlepass")),
                 ("locker", lambda: self.show("locker")),
                 ("career", lambda: self.show("career")),
                 ("settings", lambda: self._open_settings("main")),
                 ("quit", self.app.shutdown)]
        for i, (key, cmd) in enumerate(items):
            self.ui.button(self.root, i18n.t(key), (lx, 0.38 - i * 0.105), cmd, 0.78, 0.085,
                           0.05, align=T.ui_align("left"), font=self.ui.dfont)
        self._profile_panel()

    def _profile_panel(self):
        prof = self.app.storage.profile.data
        ar = self.app.getAspectRatio()
        rtl = i18n.is_rtl()
        x1 = ar - 0.08 if not rtl else -ar + 0.98
        x0 = x1 - 0.9
        y1 = 0.9
        f = self.ui.frame(self.root, x0, x1, y1 - 0.4, y1)
        lvl, into, need = BP.account_level(prof["xp_total"])
        name = self.app.storage.settings["network"]["player_name"]
        al = T.ui_align("left")
        tx = x0 + 0.04 if not rtl else x1 - 0.04
        self.ui.label(f, name, (tx, y1 - 0.08), 0.05, T.WHITE, al, self.ui.dfont)
        self.ui.label(f, i18n.visual(prof["equipped"].get("title", "")), (tx, y1 - 0.13), 0.032,
                      T.GOLD, al)
        self.ui.label(f, i18n.t("level", n=lvl), (tx, y1 - 0.2), 0.04, T.CYAN, al)
        self.ui.bar(f, x0 + 0.04, y1 - 0.24, 0.82, into / need)
        tier, tin, tneed = BP.tier_progress(prof["xp_total"])
        self.ui.label(f, i18n.t("bp_tier", n=tier) + "   " + i18n.t("bp_xp", xp=tin, need=tneed),
                      (tx, y1 - 0.3), 0.032, T.GREY, al)
        self.ui.label(f, i18n.t("coins", n=prof["coins"]), (tx, y1 - 0.36), 0.04, T.GOLD, al)
        n = len(BP.claimable(prof))
        if n:
            self.ui.label(f, "! %d" % n, (x1 - 0.05 if not rtl else x0 + 0.05, y1 - 0.36), 0.04,
                          T.GOLD, T.ui_align("right"))
        # daily challenges summary
        ch = ACH.ensure_daily(prof)
        y = y1 - 0.5
        self.ui.label(self.root, i18n.t("cr_challenges"), (tx, y), 0.035, T.CYAN, al)
        for i, c in enumerate(ch):
            s = i18n.t("chl_" + c["id"], n=c["target"]) + "  %d/%d" % (c["progress"], c["target"])
            self.ui.label(self.root, s, (tx, y - 0.05 - i * 0.045), 0.03,
                          T.GREEN if c["done"] else T.WHITE, al)

    # ================================================================== play
    def _build_play(self):
        self._backdrop(False)
        self._header("play")
        prof = self.app.storage.profile
        cfg = prof["last_mode"]
        ar = self.app.getAspectRatio()
        rtl = i18n.is_rtl()
        # mode list
        mx = T.mx(-ar + 0.55)
        self.mode_btns = []
        desc = self.ui.label(self.root, "", (mx, -0.2), 0.034, T.GREY, T.ui_align("left"),
                             wordwrap=21)
        desc.setX(mx - 0.38 if not rtl else mx + 0.38)
        if cfg.get("map") not in MAPS:
            cfg["map"] = "grid"

        def describe():
            s = i18n.raw("desc_" + cfg["mode"]) + "\n\n" + i18n.raw("opt_map") + ": " + \
                i18n.raw("map_" + cfg["map"]) + "\n" + i18n.raw("mapdesc_" + cfg["map"])
            if rtl:
                s = i18n.visual("\n".join(i18n.wrap(part, 34) if part else ""
                                          for part in s.split("\n")))
            T.set_text(desc, s)

        def pick(m):
            cfg["mode"] = m
            self.show("play")
        for i, m in enumerate(MODES):
            active = cfg["mode"] == m
            self.ui.button(self.root, ("> " if active and not rtl else "") + i18n.t("mode_" + m) +
                           (" <" if active and rtl else ""),
                           (mx, 0.55 - i * 0.11), lambda m=m: pick(m), 0.78, 0.09, 0.048,
                           align=T.ui_align("left"), font=self.ui.dfont,
                           color=(0.05, 0.3, 0.35, 0.95) if active else None)
        describe()
        # options
        ox = T.mx(0.55)
        f = self.ui.frame(self.root, ox - 0.75, ox + 0.75, -0.62, 0.66)
        self.ui.label(f, i18n.t("match_options"), (ox, 0.58), 0.045, T.CYAN, "center")
        y = 0.46
        mode = cfg["mode"]

        def set_map(i):
            cfg["map"] = MAPS[i]
            describe()
        self.ui.selector(f, i18n.t("opt_map"), [i18n.t("map_" + m) for m in MAPS],
                         MAPS.index(cfg["map"]), (ox, y), set_map)
        y -= 0.1
        if mode in ("ffa",):
            opts = [str(n) for n in range(1, 8)]
            self.ui.selector(f, i18n.t("opt_bots"), opts, max(0, min(6, cfg["bots"] - 1)), (ox, y),
                             lambda i: cfg.__setitem__("bots", i + 1))
            y -= 0.1
        from ..entities.bot import COIN_MULT
        dopts = ["%s   %sx \u00a2" % (i18n.t("diff_" + d), ("%g" % COIN_MULT[d]))
                 for d in DIFFS]
        if cfg["difficulty"] not in DIFFS:
            cfg["difficulty"] = "normal"
        self.ui.selector(f, i18n.t("opt_difficulty"), dopts, DIFFS.index(cfg["difficulty"]),
                         (ox, y), lambda i: cfg.__setitem__("difficulty", DIFFS[i]))
        y -= 0.1
        if mode in ("ffa", "duel", "team"):
            topts = [i18n.t("unlimited") if n == 0 else i18n.t("minutes", n=n) for n in TIME_LIMITS]
            ti = TIME_LIMITS.index(cfg["time_limit"]) if cfg["time_limit"] in TIME_LIMITS else 2
            self.ui.selector(f, i18n.t("opt_time"), topts, ti, (ox, y),
                             lambda i: cfg.__setitem__("time_limit", TIME_LIMITS[i]))
            y -= 0.1
            sopts = [str(n) for n in SCORE_LIMITS]
            si = SCORE_LIMITS.index(cfg["score_limit"]) if cfg["score_limit"] in SCORE_LIMITS else 3
            self.ui.selector(f, i18n.t("opt_score"), sopts, si, (ox, y),
                             lambda i: cfg.__setitem__("score_limit", SCORE_LIMITS[i]))
            y -= 0.1
        self.ui.toggle(f, i18n.t("opt_lives"), cfg["lives"], (ox, y),
                       lambda v: cfg.__setitem__("lives", v))
        y -= 0.1
        lopts = [str(n) for n in range(1, 10)]
        self.ui.selector(f, i18n.t("opt_lives_count"), lopts, max(0, cfg["lives_count"] - 1),
                         (ox, y), lambda i: cfg.__setitem__("lives_count", i + 1))
        y -= 0.07
        self.ui.label(f, i18n.t("lives_hint"), (ox, y), 0.028, T.GREY, "center")
        y -= 0.09
        self.ui.toggle(f, i18n.t("opt_chaos"), cfg["chaos"], (ox, y),
                       lambda v: cfg.__setitem__("chaos", v))
        y -= 0.07
        self.ui.label(f, i18n.t("chaos_hint"), (ox, y), 0.028, T.GREY, "center")

        def start():
            prof.save()
            c = dict(cfg)
            if c["mode"] == "duel" and c["score_limit"] > 20:
                c["score_limit"] = 10
            if c["map"] == "random":
                import random
                c["map"] = random.choice(MAPS[:-1])
            self.app.start_match(c)
        self.ui.button(self.root, i18n.t("start"), (ox, -0.76), start, 0.7, 0.11, 0.065,
                       font=self.ui.dfont, color=(0.05, 0.35, 0.4, 0.95))
        self._back_button()

    # ================================================================== story
    def _build_story(self):
        if story.launch(self.app):
            return
        self._backdrop(False)
        self._header("story_title")
        f = self.ui.frame(self.root, -0.9, 0.9, -0.3, 0.3)
        self.ui.label(f, i18n.t("story_soon", _wrap=60), (0, 0.05), 0.045, T.WHITE, "center",
                      wordwrap=34)
        self._back_button()

    # ================================================================== multiplayer
    def _build_multiplayer(self, status=""):
        self._backdrop(False)
        self._header("mp_title")
        st = self.app.storage.settings
        net = st["network"]
        self.mp_code = getattr(self, "mp_code", "")
        f = self.ui.frame(self.root, -0.85, 0.85, -0.6, 0.62)
        y = 0.48

        def set_name(v):
            net["player_name"] = v.strip()[:14] or "Runner"
        self.ui.entry(f, i18n.t("mp_name"), net["player_name"], (0, y), set_name, 1.5, 0.6, 14)
        y -= 0.11
        self.ui.entry(f, i18n.t("mp_server"), net["server"], (0, y),
                      lambda v: net.update(server=v.strip(), server_from_config=False), 1.5, 0.6,
                      96)
        y -= 0.11

        def set_code(v):
            self.mp_code = "".join(ch for ch in v.upper() if ch.isalpha())[:4]
        self.ui.entry(f, i18n.t("mp_code"), self.mp_code, (0, y), set_code, 1.5, 0.6, 4, upper=True)
        y -= 0.14
        self.ui.button(f, i18n.t("mp_find_rooms"), (0, y), lambda: self.show("rooms"), 1.46, 0.1,
                       0.05, font=self.ui.dfont, color=(0.05, 0.35, 0.42, 0.95))
        y -= 0.125
        self.ui.button(f, i18n.t("mp_host_online"), (-0.38, y), lambda: self._mp("host_online"), 0.7)
        self.ui.button(f, i18n.t("mp_join_online"), (0.38, y), lambda: self._mp("join_online"), 0.7)
        y -= 0.1
        self.ui.button(f, i18n.t("mp_host_lan"), (-0.38, y), lambda: self._mp("host_lan"), 0.7)
        self.ui.button(f, i18n.t("mp_join_lan"), (0.38, y), lambda: self._mp("join_lan"), 0.7)
        y -= 0.11
        self.mp_status = self.ui.label(f, status, (0, y), 0.033, T.GOLD, "center", wordwrap=44)
        self.ui.label(f, i18n.t("mp_hint", _wrap=80), (0, -0.54), 0.028, T.GREY, "center",
                      wordwrap=48)
        self._back_button(cmd=lambda: st.save())

    def _mp(self, action):
        from ..net.session import NetSession
        st = self.app.storage.settings
        st.save()
        if self.app.net is not None:
            self.app.net.leave()
        sess = NetSession(self.app)
        self.app.net = sess
        code = getattr(self, "mp_code", "")
        if action in ("join_online", "join_lan") and len(code) != 4:
            T.set_text(self.mp_status, i18n.t("mp_code_rules", _wrap=60))
            self.app.net = None
            return
        T.set_text(self.mp_status, i18n.t("mp_connecting"))
        if action == "host_online":
            sess.host_online()
        elif action == "join_online":
            sess.join_online(code)
        elif action == "host_lan":
            sess.host_lan()
        else:
            T.set_text(self.mp_status, i18n.t("mp_searching_lan", code=code))
            sess.join_lan(code)
        self.show("lobby")

    # ================================================================== room browser
    def _stop_browser(self):
        b = getattr(self, "browser", None)
        if b is not None:
            b.stop()
        self.browser = None

    def _build_rooms(self):
        from ..net.browser import RoomBrowser
        from ..net.session import NetSession
        self._backdrop(False)
        self._header("mp_rooms_title")
        if getattr(self, "browser", None) is None:
            self.browser = RoomBrowser(NetSession(self.app)._address())
        br = self.browser
        self.rooms_version = br.version
        rooms = list(br.rooms)
        rtl = i18n.is_rtl()
        # status line
        if br.status == "searching":
            status = i18n.t("mp_rooms_searching")
        elif rooms:
            status = i18n.t("mp_rooms_count", n=len(rooms))
        else:
            status = i18n.t("mp_rooms_none", _wrap=90)
        if br.relay_ok is False:
            status += "   " + i18n.t("mp_rooms_relay_down", addr=br.relay)
        self.ui.label(self.root, status, (0, 0.68), 0.032, T.GOLD, "center", wordwrap=70)
        # column headers
        cols = [(-1.3, "rb_code", "left"), (-0.92, "rb_host", "left"),
                (-0.32, "rb_players", "center"), (0.06, "opt_map", "center"),
                (0.44, "rb_state", "center"), (0.8, "rb_source", "center")]
        for x, key, al in cols:
            xx = -x if rtl else x
            self.ui.label(self.root, i18n.t(key), (xx, 0.57), 0.03, T.CYAN, T.ui_align(al))
        T.card(self.root, -1.4, 1.4, 0.545, 0.55, T.CYAN)
        sf = self.ui.scroll(self.root, -1.42, 1.42, -0.74, 0.53, len(rooms) * 0.1 + 0.02)
        cv = sf.getCanvas()
        for i, r in enumerate(rooms):
            y = 0.48 - i * 0.1
            full = r["players"] >= r["max"]
            T.card(cv, -1.4, 1.33, y - 0.042, y + 0.042, T.PANEL if i % 2 else (0.03, 0.09, 0.11, 0.85))
            vals = [r["code"], r["host"], "%d / %d" % (r["players"], r["max"]),
                    i18n.t("map_" + (r.get("map") if r.get("map") in MAPS else "grid")),
                    i18n.t("rb_lobby") if r["state"] == "lobby" else i18n.t("rb_playing"),
                    ("LAN" if r["source"] == "lan" else i18n.t("rb_online")) +
                    ("  %dms" % r["ping"] if r.get("ping") is not None else "")]
            colors = [T.CYAN, T.WHITE, T.RED if full else T.WHITE, T.GOLD,
                      T.GREEN if r["state"] == "lobby" else T.ORANGE, T.GREY]
            for (x, _, al), v, col in zip(cols, vals, colors):
                xx = -x if rtl else x
                self.ui.label(cv, v, (xx, y - 0.012), 0.036 if al != "left" or x > -1.2 else 0.042,
                              col, T.ui_align(al), self.ui.dfont if x < -1.2 else None)

            def join(r=r):
                sess = NetSession(self.app)
                if self.app.net is not None:
                    self.app.net.leave()
                self.app.net = sess
                self._stop_browser()
                sess.join_direct(r["addr"], r["code"])
                self.show("lobby")
            bx = 1.12 if not rtl else -1.12
            self.ui.button(cv, i18n.t("rb_join"), (bx, y), join, 0.3, 0.07, 0.034,
                           enabled=not full, color=(0.05, 0.35, 0.42, 0.95))
        ar = self.app.getAspectRatio()

        def back():
            self._stop_browser()
            self.show("multiplayer")
        self.ui.button(self.root, i18n.t("back"), (T.mx(-ar + 0.35), -0.88), back, 0.45,
                       sound="ui_back")
        self.ui.button(self.root, i18n.t("rb_refresh"), (0, -0.88),
                       lambda: br.refresh_now(), 0.5, 0.08, 0.04)
        self.ui.button(self.root, i18n.t("mp_host_online"), (T.mx(ar - 0.45), -0.88),
                       lambda: (self._stop_browser(), self._mp("host_online")), 0.6, 0.08, 0.04,
                       color=(0.35, 0.28, 0.05, 0.95))

    def _rooms_poll(self):
        br = getattr(self, "browser", None)
        if br is not None and self.current == "rooms" and br.version != self.rooms_version:
            self.show("rooms")

    def _build_lobby(self):
        self._backdrop(False)
        self._header("mp_title")
        f = self.ui.frame(self.root, -0.85, 0.85, -0.6, 0.62)
        self.lobby_frame = f
        self.lobby_code = self.ui.label(f, "", (0, 0.45), 0.08, T.CYAN, "center", self.ui.dfont)
        self.lobby_status = self.ui.label(f, "", (0, 0.35), 0.031, T.GOLD, "center", wordwrap=52)
        self.lobby_info = self.ui.label(f, "", (0, 0.235), 0.036, T.CYAN, "center")
        self.ui.label(f, i18n.t("mp_players"), (0, 0.13), 0.04, T.GREY, "center")
        self.lobby_list = [self.ui.label(f, "", (0, 0.06 - i * 0.055), 0.04, T.WHITE, "center")
                           for i in range(8)]

        def leave():
            if self.app.net:
                self.app.net.leave()
            self.app.net = None
            self.show("multiplayer")
        self.lobby_start = self.ui.button(f, i18n.t("mp_start_match"), (0, -0.46),
                                          lambda: self.app.net and self.app.net.request_start(),
                                          0.7, 0.1)
        self.lobby_start.hide()
        # the host's address is hidden unless explicitly revealed
        self.lobby_show_addr = False
        self.lobby_addr = self.ui.label(f, "", (0, -0.565), 0.028, T.GREY, "center", wordwrap=70)

        def toggle_addr():
            self.lobby_show_addr = not self.lobby_show_addr
            self.lobby_sig = None
            self._lobby_poll()
        self.lobby_addr_btn = self.ui.button(f, i18n.t("mp_show_addr"), (0.6, 0.55), toggle_addr,
                                             0.42, 0.06, 0.03)
        self.lobby_addr_btn.hide()

        def next_map():
            net = self.app.net
            if net is None:
                return
            if not net.map_supported:
                self.toast(i18n.t("mp_map_old_server"), 4.0)
                return
            maps = MAPS[:-1]
            net.set_map(maps[(maps.index(net.map) + 1) % len(maps)] if net.map in maps else "grid")
        self.lobby_map_btn = self.ui.button(f, "", (-0.6, 0.55), next_map, 0.46, 0.06, 0.03,
                                            color=(0.35, 0.28, 0.05, 0.95))
        self.lobby_map_btn.hide()
        self.ui.button(self.root, i18n.t("mp_leave"), (T.mx(-self.app.getAspectRatio() + 0.35), -0.88),
                       leave, 0.45, sound="ui_back")
        self.lobby_sig = None
        self._lobby_poll()

    def _lobby_poll(self):
        net = self.app.net
        if net is None or self.current != "lobby":
            return
        sig = (net.code, net.status, net.error, tuple(net.lobby_players), net.is_host,
               self.lobby_show_addr, net.map)
        if sig == self.lobby_sig:
            return
        self.lobby_sig = sig
        if net.error:
            self.show("multiplayer", status=i18n.t("mp_failed", err=net.error))
            self.app.net = None
            return
        T.set_text(self.lobby_code, i18n.t("mp_room_code", code=net.code) if net.code else "")
        T.set_text(self.lobby_status, net.status_text())
        for i, lbl in enumerate(self.lobby_list):
            T.set_text(lbl, net.lobby_players[i] if i < len(net.lobby_players) else "")
        if net.is_host and net.code:
            self.lobby_start.show()
            self.lobby_map_btn.show()
            self.lobby_map_btn["text"] = i18n.t("mp_map_btn", map=i18n.raw("map_" + net.map))
        else:
            self.lobby_start.hide()
            self.lobby_map_btn.hide()
        T.set_text(self.lobby_info, i18n.t("mp_room_info", mode=i18n.raw("mode_online"),
                                           map=i18n.raw("map_" + net.map), n=net.score_limit)
                   if net.code else "")
        local = getattr(net, "hosted_locally", False) and net.is_host and net.code
        if local:
            self.lobby_addr_btn.show()
            self.lobby_addr_btn["text"] = i18n.t("mp_hide_addr" if self.lobby_show_addr
                                                 else "mp_show_addr")
            T.set_text(self.lobby_addr, i18n.t("mp_addr_line", addr=net.local_addr, _wrap=80)
                       if self.lobby_show_addr else "")
        else:
            self.lobby_addr_btn.hide()
            T.set_text(self.lobby_addr, "")

    # ================================================================== loadout
    def _build_loadout(self):
        self._backdrop(False)
        self._header("loadout")
        prof = self.app.storage.profile
        pd = prof.data
        SH.sanitize_loadout(pd)
        lo = pd["loadout"]
        if not hasattr(self, "lo_preview"):
            self.lo_preview = {}
        prev = self.lo_preview
        ar = self.app.getAspectRatio()
        rtl = i18n.is_rtl()
        self.ui.label(self.root, i18n.t("coins", n=pd["coins"]), (T.mx(ar - 0.1), 0.82), 0.055,
                      T.GOLD, T.ui_align("right"), self.ui.dfont)
        self.ui.label(self.root, i18n.t("lo_coins_hint"), (T.mx(ar - 0.1), 0.76), 0.028, T.GREY,
                      T.ui_align("right"))
        self.ui.button(self.root, i18n.t("shop"), (T.mx(ar - 0.75), 0.8), lambda: self.show("shop"),
                       0.34, 0.08, 0.038, font=self.ui.dfont, color=(0.35, 0.28, 0.05, 0.95))
        lx = T.mx(-ar + 0.85)
        f = self.ui.frame(self.root, lx - 0.72, lx + 0.72, -0.72, 0.7)
        y = 0.6

        def wname(w):
            if SH.owns_weapon(pd, w["id"]):
                return w["name"]
            return "%s   %d \u00a2" % (w["name"], SH.weapon_price(w["id"]))

        def aname(a):
            if SH.owns_ability(pd, a["id"]):
                return a["name"]
            return "%s   %d \u00a2" % (a["name"], SH.ability_price(a["id"]))
        ranged_names = [wname(w) for w in W.RANGED]
        melee_names = [wname(w) for w in W.MELEE]
        ab_names = [aname(a) for a in ABILITIES]

        def setw(slot, ids):
            def f_(i):
                wid = ids[i]
                self.loadout_focus = slot
                if SH.owns_weapon(pd, wid):
                    lo[slot] = wid
                    prev.pop(slot, None)
                    prof.save()
                else:
                    prev[slot] = wid          # preview a locked weapon; buy it on the right
                self.show("loadout")
            return f_
        for slot, key, ids, names in (("primary", "lo_primary", W.RANGED_IDS, ranged_names),
                                      ("secondary", "lo_secondary", W.RANGED_IDS, ranged_names),
                                      ("melee", "lo_melee", W.MELEE_IDS, melee_names)):
            cur = prev.get(slot, lo[slot])
            self.ui.selector(f, i18n.t(key), names, ids.index(cur), (lx, y), setw(slot, ids),
                             1.35, 0.45)
            y -= 0.1

        def equip_ability(idx, aid):
            other = lo["abilities"][1 - idx]
            if aid == other:
                lo["abilities"][1 - idx] = lo["abilities"][idx]
            lo["abilities"][idx] = aid
            prev.pop("ability%d" % idx, None)
            prof.save()

        def seta(idx):
            def f_(i):
                aid = AB_IDS[i]
                if SH.owns_ability(pd, aid):
                    equip_ability(idx, aid)
                else:
                    prev["ability%d" % idx] = aid
                self.show("loadout")
            return f_
        for idx in range(2):
            cur = prev.get("ability%d" % idx, lo["abilities"][idx])
            self.ui.selector(f, i18n.t("lo_ability%d" % (idx + 1)), ab_names,
                             AB_IDS.index(cur), (lx, y), seta(idx), 1.35, 0.45)
            y -= 0.1
        # ability descriptions (+ buy button for a previewed locked ability)
        y -= 0.02
        tx = lx - 0.65 if not rtl else lx + 0.65
        for idx in range(2):
            aid = prev.get("ability%d" % idx, lo["abilities"][idx])
            a = AB_BY_ID[aid]
            owned = SH.owns_ability(pd, aid)
            self.ui.label(f, a["name"].upper(), (tx, y), 0.034, T.CYAN if owned else T.GOLD,
                          T.ui_align("left"))
            self.ui.label(f, a["desc"], (tx, y - 0.045), 0.03, T.WHITE, T.ui_align("left"),
                          wordwrap=26)
            self.ui.label(f, i18n.t("cooldown", n=int(a["cooldown"])) + "   " +
                          i18n.t("energy_cost", n=a["energy"]), (tx, y - 0.09), 0.028,
                          T.GREY, T.ui_align("left"))
            if not owned:
                price = SH.ability_price(aid)

                def buy_ab(aid=aid, idx=idx):
                    if SH.buy_ability(pd, aid):
                        self.app.audio.ui("coin")
                        equip_ability(idx, aid)
                    else:
                        self.toast(i18n.t("lk_not_enough"))
                    self.show("loadout")
                self.ui.button(f, i18n.t("lo_buy", cost=price),
                               (lx + (0.45 if not rtl else -0.45), y - 0.04), buy_ab, 0.36, 0.07,
                               0.032, color=(0.35, 0.28, 0.05, 0.95) if pd["coins"] >= price else None)
            y -= 0.15
        # focus buttons to inspect weapon upgrades
        for i, slot in enumerate(("primary", "secondary", "melee")):
            self.ui.button(f, i18n.t("lo_" + slot), (lx - 0.45 + i * 0.45, -0.64),
                           lambda s=slot: (setattr(self, "loadout_focus", s), self.show("loadout")),
                           0.42, 0.07, 0.035,
                           color=(0.05, 0.3, 0.35, 0.95) if self.loadout_focus == slot else None)
        focus = self.loadout_focus
        self._weapon_panel(prev.get(focus, lo[focus]), focus)
        self._back_button(cmd=self.lo_preview.clear)

    def _weapon_panel(self, wid, slot):
        prof = self.app.storage.profile
        pd = prof.data
        ar = self.app.getAspectRatio()
        rx = T.mx(ar - 0.8)
        f = self.ui.frame(self.root, rx - 0.7, rx + 0.7, -0.72, 0.7)
        owned = SH.owns_weapon(pd, wid)
        xp = pd["weapon_xp"].get(wid, 0)
        unlocked = SH.unlocked_tier(pd, wid)
        sel = min(unlocked, pd["weapon_tier_sel"].get(wid, unlocked))
        s = W.weapon_stats(wid, sel)
        base = W.BY_ID[wid]
        al = T.ui_align("left")
        tx = rx - 0.64 if not i18n.is_rtl() else rx + 0.64
        self.ui.label(f, s["name"].upper(), (tx, 0.6), 0.055, T.WHITE, al, self.ui.dfont)
        self.ui.label(f, s["cls"].upper() + ("" if owned else "   " + i18n.t("lo_locked")),
                      (tx, 0.545), 0.03, T.CYAN if owned else T.GOLD, al)
        y = 0.46
        if s["melee"]:
            rows = [("st_damage", s["dmg"] / 90), ("st_firerate", s["rps"] / 4.0),
                    ("st_range", s["range"] / 3.8), ("st_mobility", (s["move"] - 0.6) / 0.95),
                    ("st_dps", W.dps(s) / 130)]
        else:
            rows = [("st_damage", s["dmg"] * s["pellets"] / 110), ("st_firerate", s["rps"] / 17),
                    ("st_magazine", s["mag"] / 80), ("st_reload", (4.2 - s["reload"]) / 3.2),
                    ("st_range", min(1, s["range"] / 120)),
                    ("st_handling", (0.85 - s["swap"]) / 0.6), ("st_dps", W.dps(s) / 220)]
        for key, v in rows:
            self.ui.label(f, i18n.t(key), (tx, y), 0.032, T.GREY, al)
            bx = rx - 0.15 if not i18n.is_rtl() else rx - 0.63
            self.ui.bar(f, bx, y - 0.005, 0.78, max(0.03, min(1.0, v)))
            y -= 0.06
        if not owned:
            # locked weapon: big buy button instead of the upgrade section
            price = SH.weapon_price(wid)
            y -= 0.1

            def buy():
                if SH.buy_weapon(pd, wid):
                    pd["loadout"][slot] = wid
                    self.lo_preview.pop(slot, None)
                    prof.save()
                    self.app.audio.ui("coin")
                else:
                    self.toast(i18n.t("lk_not_enough"))
                self.show("loadout")
            self.ui.label(f, i18n.t("lo_buy_hint", _wrap=40), (rx, y), 0.032, T.GREY, "center",
                          wordwrap=30)
            y -= 0.14
            self.ui.button(f, i18n.t("lo_buy", cost=price), (rx, y), buy, 0.8, 0.11, 0.05,
                           font=self.ui.dfont,
                           color=(0.35, 0.28, 0.05, 0.95) if pd["coins"] >= price else None)
            if pd["coins"] < price:
                self.ui.label(f, i18n.t("lo_need_more", n=price - pd["coins"]), (rx, y - 0.1),
                              0.03, T.ORANGE, "center")
            return
        # tier selection
        y -= 0.02
        opts = ["%d" % i for i in range(unlocked + 1)]

        def set_tier(i):
            pd["weapon_tier_sel"][wid] = i
            prof.save()
            self.show("loadout")
        self.ui.selector(f, i18n.t("lo_tier"), opts, sel, (rx, y), set_tier, 1.3, 0.55)
        y -= 0.08
        table = W.MELEE_TIERS if base["melee"] else W.TIERS
        for i, tdef in enumerate(table):
            got = i < unlocked
            active = i < sel
            col = T.CYAN if active else (T.WHITE if got else T.GREY)
            mark = ("\u2022 " if active else "\u00b7 ")
            self.ui.label(f, mark + "%d  %s" % (i + 1, tdef["name"]), (tx, y), 0.03, col, al)
            self.ui.label(f, tdef["desc"] if got else i18n.t("lo_locked"),
                          (tx + (0.5 if not i18n.is_rtl() else -0.5), y), 0.026, col, al)
            y -= 0.045
        y -= 0.02
        nxt = W.TIER_XP[unlocked] if unlocked < 5 else None
        self.ui.label(f, i18n.t("lo_weapon_xp", xp=int(xp)) + "   " +
                      (i18n.t("lo_next_tier", xp=nxt) if nxt is not None else i18n.t("lo_max_tier")),
                      (tx, y), 0.03, T.GREY, al)
        y -= 0.075
        tier_price = SH.next_tier_price(pd, wid)

        def buy_tier():
            if SH.buy_tier(pd, wid):
                prof.save()
                self.app.audio.ui("level_up")
            else:
                self.toast(i18n.t("lk_not_enough"))
            self.show("loadout")
        if not base["melee"]:
            fitted = len(pd["weapon_mods"].get(wid, {}))

            def open_gs():
                self.gs_weapon = wid
                self.gs_preview = {}
                self.gs_return = "loadout"
                self.show("gunsmith")
            self.ui.button(f, i18n.t("edit_weapon") + ("  (%d)" % fitted if fitted else ""),
                           (rx + (0.4 if not i18n.is_rtl() else -0.4), 0.6), open_gs, 0.5, 0.09,
                           0.036, font=self.ui.dfont, color=(0.05, 0.35, 0.42, 0.95))
        if tier_price is not None:
            self.ui.button(f, i18n.t("lo_buy_tier", n=unlocked + 1, cost=tier_price), (rx, y),
                           buy_tier, 0.9, 0.075, 0.036,
                           color=(0.35, 0.28, 0.05, 0.95) if pd["coins"] >= tier_price else None)
        y -= 0.09
        chips = pd["upgrade_chips"]

        def use_chip():
            if pd["upgrade_chips"] > 0 and unlocked < 5:
                pd["upgrade_chips"] -= 1
                pd["weapon_bonus_tiers"][wid] = pd["weapon_bonus_tiers"].get(wid, 0) + 1
                pd["weapon_tier_sel"][wid] = unlocked + 1
                prof.save()
                self.app.audio.ui("level_up")
                self.show("loadout")
        self.ui.button(f, i18n.t("lo_apply_chip", n=chips), (rx, y), use_chip, 0.9, 0.07, 0.032,
                       enabled=chips > 0 and unlocked < 5)

    # ================================================================== shop
    def _build_shop(self, tab=None):
        from . import shop_screen
        shop_screen.build(self, tab)

    # ================================================================== gunsmith (weapon mods)
    def _build_gunsmith(self):
        self._backdrop(False)
        prof = self.app.storage.profile
        pd = prof.data
        wid = self.gs_weapon
        prev = self.gs_preview
        base = W.BY_ID[wid]
        ar = self.app.getAspectRatio()
        rtl = i18n.is_rtl()
        al = T.ui_align("left")
        x = T.mx(-ar + 0.12)
        T.text(self.root, i18n.t("edit_weapon") + "  //  " + base["name"].upper(), (x, 0.82), 0.075,
               T.CYAN, al, self.ui.dfont)
        self.ui.label(self.root, i18n.t("coins", n=pd["coins"]), (T.mx(ar - 0.1), 0.82), 0.055,
                      T.GOLD, T.ui_align("right"), self.ui.dfont)
        self.ui.label(self.root, i18n.t("gs_hint"), (x, 0.74), 0.03, T.GREY, al)
        fitted = pd["weapon_mods"].setdefault(wid, {})
        lx = T.mx(-ar + 0.95)
        f = self.ui.frame(self.root, lx - 0.85, lx + 0.85, -0.78, 0.68)
        y = 0.58
        tx = lx - 0.8 if not rtl else lx + 0.8
        for slot in W.MOD_SLOTS:
            choices = W.mods_for(wid, slot)
            self.ui.label(f, i18n.t("slot_" + slot), (tx, y + 0.005), 0.038, T.CYAN, al,
                          self.ui.dfont)
            if not choices:
                self.ui.label(f, i18n.t("gs_no_slot"), (lx + 0.2, y), 0.03, T.GREY, "center")
                y -= 0.265
                continue
            ids = [None] + [m["id"] for m in choices]

            def label(mid):
                if mid is None:
                    return i18n.t("mod_none")
                m = W.MOD_BY_ID[mid]
                if SH.owns_mod(pd, mid):
                    return m["name"]
                return "%s   %d \u00a2" % (m["name"], m["price"])
            names = [label(m) for m in ids]
            cur = prev.get(slot, fitted.get(slot))
            if cur not in ids:
                cur = None

            def pick(slot=slot, ids=ids):
                def fn(i):
                    mid = ids[i]
                    if mid is None or SH.owns_mod(pd, mid):
                        SH.fit_mod(pd, wid, slot, mid)
                        prev.pop(slot, None)
                        prof.save()
                        self.app.audio.ui("switch")
                    else:
                        prev[slot] = mid
                    self.show("gunsmith")
                return fn
            self.ui.selector(f, "", names, ids.index(cur), (lx + 0.12, y - 0.075), pick(), 1.4,
                             0.0)
            desc_y = y - 0.15
            if cur is not None:
                m = W.MOD_BY_ID[cur]
                owned = SH.owns_mod(pd, cur)
                self.ui.label(f, m["desc"], (tx, desc_y), 0.029, T.WHITE if owned else T.GREY, al)
                if owned:
                    self.ui.label(f, i18n.t("mod_fitted"), (tx + (1.5 if not rtl else -1.5), desc_y),
                                  0.028, T.GREEN, T.ui_align("right"))
                else:
                    def buy(mid=cur, slot=slot):
                        if SH.buy_mod(pd, mid):
                            SH.fit_mod(pd, wid, slot, mid)
                            prev.pop(slot, None)
                            prof.save()
                            self.app.audio.ui("coin")
                        else:
                            self.toast(i18n.t("lk_not_enough"))
                        self.show("gunsmith")
                    self.ui.button(f, i18n.t("lo_buy", cost=m["price"]),
                                   (lx + (0.62 if not rtl else -0.62), desc_y + 0.012), buy, 0.36,
                                   0.06, 0.03,
                                   color=(0.35, 0.28, 0.05, 0.95) if pd["coins"] >= m["price"]
                                   else None)
            y -= 0.265
        # ---- stats with the fitted (and previewed) mods
        tier = min(SH.unlocked_tier(pd, wid), pd["weapon_tier_sel"].get(wid, 99))
        eff = dict(fitted)
        eff.update({k: v for k, v in prev.items() if v})
        s = W.weapon_stats(wid, tier, eff)
        b0 = W.weapon_stats(wid, tier)
        rx = T.mx(ar - 0.7)
        g = self.ui.frame(self.root, rx - 0.6, rx + 0.6, -0.78, 0.68)
        gx = rx - 0.55 if not rtl else rx + 0.55
        self.ui.label(g, i18n.t("gs_stats"), (gx, 0.58), 0.04, T.CYAN, al, self.ui.dfont)
        rows = [("st_damage", "dmg", 1), ("st_firerate", "rps", 1), ("st_magazine", "mag", 1),
                ("st_reload", "reload", -1), ("st_range", "range", 1), ("st_spread", "spread", -1),
                ("st_recoil", "recoil", -1), ("st_handling", "swap", -1),
                ("st_mobility", "move", 1), ("st_zoom", "zoom", -1)]
        yy = 0.47
        for key, stat, good in rows:
            v0, v1 = b0[stat], s[stat]
            self.ui.label(g, i18n.t(key), (gx, yy), 0.03, T.GREY, al)
            if abs(v1 - v0) < 1e-6:
                txt, col = self._fmt_stat(stat, v1), T.WHITE
            else:
                better = (v1 > v0) == (good > 0)
                pct = (v1 / v0 - 1) * 100 if v0 else 0
                txt = "%s  (%+.0f%%)" % (self._fmt_stat(stat, v1), pct)
                col = T.GREEN if better else T.RED
            self.ui.label(g, txt, (gx + (1.1 if not rtl else -1.1), yy), 0.03, col,
                          T.ui_align("right"))
            yy -= 0.062
        yy -= 0.03
        tags = []
        if "suppressed" in s["flags"]:
            tags.append(i18n.t("mod_silent"))
        if "laser" in s["flags"]:
            tags.append(i18n.t("mod_laser"))
        if s.get("reticle") in ("dot", "holo"):
            tags.append(i18n.t("mod_reticle_" + s["reticle"]))
        if s["scoped"]:
            tags.append(i18n.t("mod_scoped"))
        self.ui.label(g, "   ".join(tags), (rx, yy), 0.034, T.GOLD, "center")

        def back():
            self.gs_preview = {}
            self.show(getattr(self, "gs_return", "loadout"))
        self.ui.button(self.root, i18n.t("back"), (T.mx(-ar + 0.35), -0.9), back, 0.45,
                       sound="ui_back")

    @staticmethod
    def _fmt_stat(stat, v):
        if stat in ("reload", "swap"):
            return "%.2fs" % v
        if stat in ("spread", "recoil"):
            return "%.2f\u00b0" % v
        if stat in ("move", "zoom"):
            return "%.2fx" % v
        if stat == "range":
            return "%dm" % v
        if stat == "rps":
            return "%.1f/s" % v
        return "%d" % round(v)

    # ================================================================== battle pass
    def _build_battlepass(self):
        self._backdrop(False)
        self._header("bp_title")
        prof = self.app.storage.profile
        pd = prof.data
        tier, tin, tneed = BP.tier_progress(pd["xp_total"])
        f = self.ui.frame(self.root, -1.4, 1.4, 0.48, 0.72)
        self.ui.label(f, i18n.t("bp_tier", n=tier), (T.mx(-1.35), 0.62), 0.06, T.WHITE,
                      T.ui_align("left"), self.ui.dfont)
        self.ui.bar(f, -0.9, 0.62, 1.0, tin / tneed)
        self.ui.label(f, i18n.t("bp_xp", xp=tin, need=tneed), (-0.4, 0.53), 0.03, T.GREY, "center")
        self.ui.label(f, i18n.t("bp_note"), (T.mx(1.35), 0.53), 0.026, T.GREY, T.ui_align("right"))

        def unlock():
            if BP.unlock_premium(pd):
                prof.save()
                self.app.audio.ui("level_up")
            else:
                self.toast(i18n.t("lk_not_enough"))
            self.show("battlepass")

        def claim_all():
            if BP.claim_all(pd):
                prof.save()
                self.app.audio.ui("pickup")
            self.show("battlepass")
        if pd["pass"]["premium"]:
            self.ui.label(f, i18n.t("bp_premium_owned"), (0.75, 0.6), 0.04, T.GOLD, "center")
        else:
            self.ui.button(f, i18n.t("bp_unlock_premium", cost=BP.PREMIUM_COST), (0.75, 0.62),
                           unlock, 0.7, 0.08, 0.034)
        self.ui.button(f, i18n.t("bp_claim") + " ALL", (T.mx(-1.15), 0.53 - 0.001), claim_all,
                       0.35, 0.06, 0.03, enabled=bool(BP.claimable(pd)))
        # columns
        sf = self.ui.scroll(self.root, -1.4, 1.4, -0.78, 0.44, BP.TIERS * 0.1 + 0.05)
        cv = sf.getCanvas()
        self.ui.label(self.root, i18n.t("bp_free"), (-0.35, 0.455), 0.03, T.CYAN, "center")
        self.ui.label(self.root, i18n.t("bp_premium"), (0.75, 0.455), 0.03, T.GOLD, "center")
        claimed_f = pd["pass"]["claimed_free"]
        claimed_p = pd["pass"]["claimed_premium"]
        for t in range(1, BP.TIERS + 1):
            y = 0.4 - (t - 1) * 0.1
            got = t <= tier
            T.card(cv, -1.38, 1.3, y - 0.04, y + 0.04,
                   (0.03, 0.12, 0.15, 0.85) if got else (0.02, 0.04, 0.05, 0.7))
            self.ui.label(cv, i18n.t("bp_tier", n=t), (-1.33, y - 0.012), 0.032,
                          T.CYAN if got else T.GREY, "left")
            for track, table, claimed, x in (("free", BP.FREE, claimed_f, -0.35),
                                             ("premium", BP.PREMIUM, claimed_p, 0.75)):
                if t not in table:
                    continue
                self.ui.label(cv, reward_text(table[t]), (x - 0.12, y - 0.012), 0.03,
                              T.WHITE if got else T.GREY, "center")
                if t in claimed:
                    self.ui.label(cv, i18n.t("bp_claimed"), (x + 0.38, y - 0.012), 0.028, T.GREEN,
                                  "center")
                elif got and (track == "free" or pd["pass"]["premium"]):
                    def c(track=track, t=t):
                        if BP.claim(pd, track, t):
                            prof.save()
                            self.app.audio.ui("pickup")
                        self.show("battlepass")
                    self.ui.button(cv, i18n.t("bp_claim"), (x + 0.38, y), c, 0.2, 0.06, 0.03)
                else:
                    self.ui.label(cv, i18n.t("bp_locked"), (x + 0.38, y - 0.012), 0.028, T.GREY,
                                  "center")
        self._back_button()

    # ================================================================== locker
    def _build_locker(self):
        self._backdrop(False)
        self._header("lk_title")
        prof = self.app.storage.profile
        pd = prof.data
        self.ui.label(self.root, i18n.t("coins", n=pd["coins"]), (T.mx(1.4), 0.82), 0.05, T.GOLD,
                      T.ui_align("right"))
        cols = [("lk_weapon_skins", SK.WEAPON_SKINS, "owned_weapon_skins", "weapon_skin", -0.95),
                ("lk_char_skins", SK.CHAR_SKINS, "owned_char_skins", "char_skin", 0.05)]
        for key, table, owned_key, eq_key, x in cols:
            x = T.mx(x) if not i18n.is_rtl() else -x - 0.0
            self.ui.label(self.root, i18n.t(key), (x + 0.45, 0.68), 0.045, T.CYAN, "center")
            for i, sk in enumerate(table):
                y = 0.58 - i * 0.105
                owned = sk["id"] in pd[owned_key]
                equipped = pd["equipped"][eq_key] == sk["id"]
                T.card(self.root, x - 0.02, x + 0.94, y - 0.045, y + 0.045, T.PANEL)
                T.card(self.root, x, x + 0.06, y - 0.03, y + 0.03, sk["body"] + (1,))
                T.card(self.root, x + 0.065, x + 0.085, y - 0.03, y + 0.03, sk["accent"] + (1,))
                self.ui.label(self.root, sk["name"], (x + 0.11, y - 0.012), 0.034,
                              T.WHITE if owned else T.GREY, "left")
                bx = x + 0.78
                if equipped:
                    self.ui.label(self.root, i18n.t("lk_equipped"), (bx, y - 0.012), 0.03, T.GREEN,
                                  "center")
                elif owned:
                    def eq(k=eq_key, sid=sk["id"]):
                        pd["equipped"][k] = sid
                        prof.save()
                        self.show("locker")
                    self.ui.button(self.root, i18n.t("lk_equip"), (bx, y), eq, 0.26, 0.065, 0.03)
                elif sk["source"] == "shop":
                    def buy(k=owned_key, s=sk):
                        if pd["coins"] >= s["price"]:
                            pd["coins"] -= s["price"]
                            pd[k].append(s["id"])
                            prof.save()
                            self.app.audio.ui("coin")
                        else:
                            self.toast(i18n.t("lk_not_enough"))
                        self.show("locker")
                    self.ui.button(self.root, i18n.t("lk_buy", cost=sk["price"]), (bx, y), buy,
                                   0.26, 0.065, 0.028)
                else:
                    self.ui.label(self.root, i18n.t("lk_pass_only"), (bx, y - 0.012), 0.026,
                                  T.GOLD, "center")
        # titles
        tx = T.mx(1.15)
        self.ui.label(self.root, i18n.t("lk_titles"), (tx, 0.68), 0.045, T.CYAN, "center")
        for i, title in enumerate(pd["owned_titles"]):
            y = 0.58 - i * 0.09
            eq = pd["equipped"].get("title") == title

            def set_title(tt=title):
                pd["equipped"]["title"] = tt
                prof.save()
                self.show("locker")
            self.ui.button(self.root, title, (tx, y), set_title, 0.5, 0.07, 0.034,
                           color=(0.05, 0.35, 0.4, 0.95) if eq else None)
        self._back_button()

    # ================================================================== career
    def _build_career(self):
        self._backdrop(False)
        self._header("cr_title")
        st = self.app.storage
        s = st.stats.data
        hs = st.highscores.data
        pd = st.profile.data
        al = T.ui_align("left")
        # stats
        x = T.mx(-1.45)
        self.ui.label(self.root, i18n.t("cr_stats"), (x, 0.66), 0.045, T.CYAN, al)
        kd = s["kills"] / max(1, s["deaths"])
        acc = 100.0 * s["shots_hit"] / max(1, s["shots_fired"])
        tp = int(s["time_played"])
        rows = [("cs_kills", s["kills"]), ("cs_deaths", s["deaths"]), ("cs_kd", "%.2f" % kd),
                ("cs_headshots", s["headshots"]), ("cs_accuracy", "%.1f%%" % acc),
                ("cs_matches", s["matches"]), ("cs_wins", s["wins"]),
                ("cs_time", "%dh %02dm" % (tp // 3600, (tp // 60) % 60)),
                ("cs_melee", s["melee_kills"]), ("cs_streak", s["best_streak"]),
                ("cs_damage", s["damage"]), ("cs_abilities", s["abilities_used"]),
                ("cs_drones", s["drones_destroyed"]), ("cs_turrets", s["turrets_destroyed"])]
        for i, (k, v) in enumerate(rows):
            y = 0.57 - i * 0.052
            self.ui.label(self.root, i18n.t(k), (x, y), 0.032, T.GREY, al)
            self.ui.label(self.root, str(v), (x + (0.75 if al == "left" else -0.75), y), 0.032,
                          T.WHITE, T.ui_align("right"))
        # high scores
        y = 0.57 - len(rows) * 0.052 - 0.05
        self.ui.label(self.root, i18n.t("cr_highscores"), (x, y), 0.04, T.CYAN, al)
        d = hs["duel_wins"]
        hrows = [("hs_endless", hs["endless_wave"]), ("hs_endless_kills", hs["endless_kills"]),
                 ("hs_coop", hs["coop_wave"]), ("hs_ffa", hs["ffa_kills"]),
                 ("hs_duel", "%d / %d / %d / %d" % (d.get("easy", 0), d.get("normal", 0),
                                                    d.get("hard", 0), d.get("nightmare", 0)))]
        for i, (k, v) in enumerate(hrows):
            yy = y - 0.06 - i * 0.05
            self.ui.label(self.root, i18n.t(k), (x, yy), 0.03, T.GREY, al)
            self.ui.label(self.root, str(v), (x + (0.75 if al == "left" else -0.75), yy), 0.03,
                          T.WHITE, T.ui_align("right"))
        # achievements
        ax = T.mx(-0.45)
        self.ui.label(self.root, i18n.t("cr_achievements") + "  %d/%d" % (len(pd["achievements"]),
                                                                            len(ACH.ACH_IDS)),
                      (ax, 0.66), 0.045, T.CYAN, al)
        sf = self.ui.scroll(self.root, -0.5 if not i18n.is_rtl() else -0.55,
                            0.55 if not i18n.is_rtl() else 0.5, -0.8, 0.6,
                            len(ACH.ACH_IDS) * 0.09 + 0.02)
        cv = sf.getCanvas()
        for i, aid in enumerate(ACH.ACH_IDS):
            y = 0.56 - i * 0.09
            got = aid in pd["achievements"]
            name, desc = i18n.pair("ach_" + aid)
            xx = -0.45 if not i18n.is_rtl() else 0.45
            T.card(cv, -0.48, 0.48, y - 0.05, y + 0.035,
                   (0.03, 0.14, 0.16, 0.85) if got else (0.02, 0.04, 0.05, 0.7))
            self.ui.label(cv, ("• " if got else "") + name, (xx, y - 0.005), 0.032,
                          T.GOLD if got else T.WHITE, al)
            self.ui.label(cv, desc, (xx, y - 0.04), 0.025, T.GREY, al)
        # challenges
        cx = T.mx(0.7)
        self.ui.label(self.root, i18n.t("cr_challenges"), (cx, 0.66), 0.045, T.CYAN, al)
        for i, c in enumerate(ACH.ensure_daily(pd)):
            y = 0.55 - i * 0.18
            T.card(self.root, 0.68 if not i18n.is_rtl() else -1.48, 1.48 if not i18n.is_rtl()
                   else -0.68, y - 0.13, y + 0.04, T.PANEL)
            xx = cx + (0.04 if al == "left" else -0.04)
            self.ui.label(self.root, i18n.t("chl_" + c["id"], n=c["target"]), (xx, y - 0.02),
                          0.034, T.GREEN if c["done"] else T.WHITE, al)
            bx = 0.72 if not i18n.is_rtl() else -1.44
            self.ui.bar(self.root, bx, y - 0.07, 0.72, c["progress"] / max(1, c["target"]),
                        T.GREEN if c["done"] else T.CYAN)
            self.ui.label(self.root, ("%d / %d   " % (c["progress"], c["target"])) +
                          (i18n.t("ch_done") if c["done"] else i18n.t("ch_reward", xp=c["xp"],
                                                                     coins=c["coins"])),
                          (xx, y - 0.115), 0.026, T.GREY, al)
        self._back_button()

    # ================================================================== settings
    def _open_settings(self, ret):
        self.settings_return = ret
        self.show("settings")

    def _save_settings(self):
        self.app.storage.settings.save()

    def _build_settings(self, tab=None):
        if tab:
            self.settings_tab = tab
        tab = self.settings_tab
        self._backdrop(False)
        self._header("set_title")
        tabs = ["video", "audio", "controls", "gameplay", "hud", "language"]
        for i, t in enumerate(tabs):
            x = -1.25 + i * 0.5
            if i18n.is_rtl():
                x = -x
            self.ui.button(self.root, i18n.t("tab_" + t), (x, 0.66),
                           lambda t=t: self.show("settings", tab=t), 0.47, 0.08, 0.036,
                           color=(0.05, 0.35, 0.4, 0.95) if t == tab else None)
        self.set_frame = self.ui.frame(self.root, -1.4, 1.4, -0.78, 0.58)
        getattr(self, "_tab_" + tab)(self.set_frame)

        def back():
            self._save_settings()
            self.show(self.settings_return)
        ar = self.app.getAspectRatio()
        self.ui.button(self.root, i18n.t("back"), (T.mx(-ar + 0.35), -0.88), back, 0.45,
                       sound="ui_back")

        def reset():
            from ..storage import DEFAULT_SETTINGS
            import copy
            st = self.app.storage.settings
            lang = st["language"]
            st.data = copy.deepcopy(DEFAULT_SETTINGS)
            st["language"] = lang
            self.app.input.bindings = st["controls"]["bindings"]
            self.app.input.settings = st.data
            self.app.audio.settings = st.data
            st.save()
            self.app.hud.rebuild()
            self.show("settings")
        self.ui.button(self.root, i18n.t("reset_defaults"), (T.mx(ar - 0.45), -0.88), reset, 0.6,
                       0.07, 0.034)

    def _tab_video(self, f):
        v = self.app.storage.settings["video"]
        y = 0.46
        q = ["high", "low"]
        self.ui.selector(f, i18n.t("quality"), [i18n.t("q_high"), i18n.t("q_low")], q.index(v["quality"]),
                         (0, y), lambda i: v.__setitem__("quality", q[i]), 1.8, 0.8)
        self.ui.label(f, i18n.t("quality_hint"), (0, y - 0.06), 0.026, T.GREY, "center")
        y -= 0.13
        res = [tuple(v["resolution"])] if tuple(v["resolution"]) not in RESOLUTIONS else []
        opts = RESOLUTIONS + res
        ri = opts.index(tuple(v["resolution"]))

        def set_res(i):
            v["resolution"] = list(opts[i])
            self._apply_window()
        self.ui.selector(f, i18n.t("resolution"), ["%d x %d" % r for r in opts], ri, (0, y), set_res,
                         1.8, 0.8)
        y -= 0.1

        def set_fs(on):
            v["fullscreen"] = on
            self._apply_window()
        self.ui.toggle(f, i18n.t("fullscreen"), v["fullscreen"], (0, y), set_fs, 1.8, 0.8)
        y -= 0.1

        def set_vsync(on):
            v["vsync"] = on
            self.app._apply_fps_cap()
        self.ui.toggle(f, i18n.t("vsync"), v["vsync"], (0, y), set_vsync, 1.8, 0.8)
        y -= 0.1

        def set_cap(i):
            v["fps_cap"] = FPS_CAPS[i]
            self.app._apply_fps_cap()
        ci = FPS_CAPS.index(v["fps_cap"]) if v["fps_cap"] in FPS_CAPS else 3
        self.ui.selector(f, i18n.t("fps_cap"), [i18n.t("unlimited") if c == 0 else str(c)
                                                for c in FPS_CAPS], ci, (0, y), set_cap, 1.8, 0.8)
        y -= 0.1
        self.ui.slider(f, i18n.t("fov"), v["fov"], (0, y),
                       lambda x: v.__setitem__("fov", int(x)), 70, 120, 1.8, 0.8, "{:.0f}")
        y -= 0.1

        def set_bloom(x):
            v["bloom"] = round(x, 2)
            self.app.postfx.set_bloom(v["bloom"])
        self.ui.slider(f, i18n.t("bloom"), v["bloom"], (0, y), set_bloom, 0.0, 2.0, 1.8, 0.8,
                       "{:.0%}")
        y -= 0.1
        self.ui.toggle(f, i18n.t("reflections"), v["reflections"], (0, y),
                       lambda on: v.__setitem__("reflections", on), 1.8, 0.8)
        y -= 0.1
        self.ui.toggle(f, i18n.t("show_fps"), v["show_fps"], (0, y),
                       lambda on: v.__setitem__("show_fps", on), 1.8, 0.8)
        self.ui.label(f, i18n.t("restart_hint"), (0, -0.72), 0.026, T.GREY, "center")

    def _apply_window(self):
        v = self.app.storage.settings["video"]
        props = WindowProperties()
        props.setFullscreen(v["fullscreen"])
        props.setSize(*v["resolution"])
        self.app.base.win.requestProperties(props)

    def _tab_audio(self, f):
        a = self.app.storage.settings["audio"]
        y = 0.42
        for key in ("master", "music", "effects", "voice"):
            def setv(x, key=key):
                a[key] = round(x, 2)
            self.ui.slider(f, i18n.t(key), a[key], (0, y), setv, 0, 1, 1.8, 0.8)
            y -= 0.12
        self.ui.toggle(f, i18n.t("announcer"), a["announcer"], (0, y),
                       lambda on: a.__setitem__("announcer", on), 1.8, 0.8)
        y -= 0.14
        self.ui.button(f, "TEST", (0, y), lambda: self.app.audio.announce("headshot") or
                       self.app.audio.play2d("explosion", 0.6), 0.4, 0.07, 0.034)

    def _tab_controls(self, f):
        c = self.app.storage.settings["controls"]
        y = 0.48
        self.ui.slider(f, i18n.t("sensitivity"), c["sensitivity"], (-0.65, y),
                       lambda x: c.__setitem__("sensitivity", round(x, 2)), 0.1, 4.0, 1.25, 0.6,
                       "{:.2f}")
        self.ui.slider(f, i18n.t("ads_sens"), c["ads_sensitivity"], (0.65, y),
                       lambda x: c.__setitem__("ads_sensitivity", round(x, 2)), 0.2, 1.5, 1.25,
                       0.6, "{:.2f}")
        y -= 0.1
        self.ui.toggle(f, i18n.t("invert_y"), c["invert_y"], (-0.65, y),
                       lambda on: c.__setitem__("invert_y", on), 1.25, 0.6)
        self.ui.toggle(f, i18n.t("toggle_crouch"), c["toggle_crouch"], (0.65, y),
                       lambda on: c.__setitem__("toggle_crouch", on), 1.25, 0.6)
        y -= 0.1
        self.ui.label(f, i18n.t("bindings"), (0, y), 0.04, T.CYAN, "center")
        y -= 0.07
        b = c["bindings"]
        actions = list(DEFAULT_BINDINGS.keys())
        half = (len(actions) + 1) // 2
        for i, act in enumerate(actions):
            col = 0 if i < half else 1
            row = i if i < half else i - half
            x = -0.65 if col == 0 else 0.65
            if i18n.is_rtl():
                x = -x
            yy = y - row * 0.066
            self.ui.label(f, i18n.t("bind_" + act), (x - 0.55 if not i18n.is_rtl() else x + 0.55,
                                                    yy - 0.012), 0.03, T.GREY, T.ui_align("left"))
            label = i18n.t("press_key") if self.binding_action == act else key_label(b[act])

            def rebind(a=act):
                self.binding_action = a
                self.show("settings", tab="controls")

                def got(name, a=a):
                    self.binding_action = None
                    if name != "escape":
                        # swap if already used
                        for k, v in b.items():
                            if v == name and k != a:
                                b[k] = b[a]
                        b[a] = name
                        self.app.input._handles.clear()
                    self.show("settings", tab="controls")
                self.app.base.taskMgr.doMethodLater(0.15, lambda task: self.app.input.capture_next(got),
                                                    "bind-capture")
            self.ui.button(f, label, (x + 0.3 if not i18n.is_rtl() else x - 0.3, yy), rebind,
                           0.42, 0.058, 0.03)

    def _tab_gameplay(self, f):
        from .hud import CROSS_COLORS, CROSS_STYLES, CrosshairPreview
        g = self.app.storage.settings["gameplay"]
        prev = CrosshairPreview(f, self.app.ui_textures, (T.mx(1.0), 0.05), 3.2)
        prev.update(g)
        self.ui.label(f, i18n.t("crosshair_preview"), (T.mx(1.0), 0.3), 0.032, T.GREY, "center")

        def setg(key, refresh=True):
            def fn(v):
                g[key] = round(v, 2) if isinstance(v, float) else v
                prev.update(g)
            return fn
        x = T.mx(-0.35)
        y = 0.47
        W_, LW = 1.3, 0.6
        self.ui.toggle(f, i18n.t("screen_shake"), g["screen_shake"], (x, y),
                       setg("screen_shake"), W_, LW)
        y -= 0.1
        self.ui.toggle(f, i18n.t("hit_markers"), g["hit_markers"], (x, y), setg("hit_markers"),
                       W_, LW)
        y -= 0.12
        self.ui.selector(f, i18n.t("crosshair_style"),
                         [i18n.t("cross_%d" % i) for i in range(len(CROSS_STYLES))],
                         g["crosshair_style"] % len(CROSS_STYLES), (x, y),
                         setg("crosshair_style"), W_, LW)
        y -= 0.1
        self.ui.selector(f, i18n.t("crosshair_color"),
                         [i18n.t("col_%d" % i) for i in range(len(CROSS_COLORS))],
                         g["crosshair_color"] % len(CROSS_COLORS), (x, y),
                         setg("crosshair_color"), W_, LW)
        y -= 0.1
        self.ui.slider(f, i18n.t("crosshair_size"), g["crosshair_size"], (x, y),
                       setg("crosshair_size"), 0.4, 2.5, W_, LW, "{:.1f}")
        y -= 0.1
        self.ui.slider(f, i18n.t("crosshair_thickness"), g["crosshair_thickness"], (x, y),
                       setg("crosshair_thickness"), 0.5, 3.0, W_, LW, "{:.1f}")
        y -= 0.1
        self.ui.slider(f, i18n.t("crosshair_gap"), g["crosshair_gap"], (x, y),
                       setg("crosshair_gap"), 0.0, 5.0, W_, LW, "{:.1f}")
        y -= 0.1
        self.ui.toggle(f, i18n.t("crosshair_outline"), g["crosshair_outline"], (x, y),
                       setg("crosshair_outline"), W_, LW)
        y -= 0.1
        self.ui.toggle(f, i18n.t("crosshair_dynamic"), g["crosshair_dynamic"], (x, y),
                       setg("crosshair_dynamic"), W_, LW)

    def _tab_hud(self, f):
        h = self.app.storage.settings["hud"]
        y = 0.46

        def sc(x):
            h["scale"] = round(x, 2)
            self.app.hud.place_all()

        def op(x):
            h["opacity"] = round(x, 2)
            self.app.hud.place_all()
        self.ui.slider(f, i18n.t("hud_scale"), h["scale"], (-0.65, y), sc, 0.5, 1.6, 1.25, 0.55,
                       "{:.0%}")
        self.ui.slider(f, i18n.t("hud_opacity"), h["opacity"], (0.65, y), op, 0.2, 1.0, 1.25, 0.55,
                       "{:.0%}")
        y -= 0.12
        els = h["elements"]
        keys = list(DEFAULT_HUD_ELEMENTS.keys())
        for i, k in enumerate(keys):
            col = i % 2
            row = i // 2
            x = -0.65 if col == 0 else 0.65
            if i18n.is_rtl():
                x = -x
            yy = y - row * 0.09

            def tog(on, k=k):
                els[k]["visible"] = on
                self.app.hud.place_all()
            self.ui.toggle(f, i18n.t("el_" + k), els[k]["visible"], (x, yy), tog, 1.25, 0.55)
        y -= ((len(keys) + 1) // 2) * 0.09 + 0.06
        self.ui.button(f, i18n.t("hud_edit"), (-0.4, y), self._start_hud_edit, 0.7, 0.085, 0.04)

        def reset():
            import copy
            h["elements"] = copy.deepcopy(DEFAULT_HUD_ELEMENTS)
            h["scale"] = 1.0
            h["opacity"] = 0.95
            self.app.hud.place_all()
            self.show("settings", tab="hud")
        self.ui.button(f, i18n.t("hud_reset"), (0.4, y), reset, 0.7, 0.085, 0.04)

    def _tab_language(self, f):
        st = self.app.storage.settings

        def set_lang(lang):
            st["language"] = lang
            i18n.set_language(lang)
            st.save()
            self.app.hud.rebuild()
            self.show("settings", tab="language")
        self.ui.label(f, i18n.t("language"), (0, 0.35), 0.05, T.CYAN, "center")
        he_font = self.app.fonts._load("segoeui.ttf") or self.ui.font
        self.ui.button(f, "English", (0, 0.18), lambda: set_lang("en"), 0.7, 0.1, 0.05,
                       color=(0.05, 0.35, 0.4, 0.95) if st["language"] == "en" else None)
        self.ui.button(f, "עברית"[::-1], (0, 0.04), lambda: set_lang("he"), 0.7, 0.1, 0.05,
                       color=(0.05, 0.35, 0.4, 0.95) if st["language"] == "he" else None,
                       font=he_font)

    # ================================================================== HUD editor
    def _start_hud_edit(self):
        self._save_settings()
        self._clear()
        self.current = "hud_edit"
        self.root = self.app.aspect2d.attachNewNode("hud_edit")
        hud = self.app.hud
        hud.editing = True
        hud.place_all()
        hud.root.show()
        self.hud_edit = {"drag": None, "outlines": {}}
        T.text(self.root, i18n.t("hud_edit_hint"), (0, 0.75), 0.04, T.GOLD, "center", self.ui.font)
        # sample content so elements are visible without a match
        T.set_text(hud.mi_big, "4:20")
        T.set_text(hud.mi_small, i18n.t("first_to", n=25))
        T.set_text(hud.ammo_mag, "30")
        T.set_text(hud.ammo_res, "/ 120")
        T.set_text(hud.ammo_name, "AR-7 PULSE")
        T.set_text(hud.kill_nodes[0], "VECTOR  [Hornet SMG]  CIPHER")
        T.set_text(hud.notice_nodes[0], "+30 AMMO")
        for arc in hud.dmg_arcs[:1]:
            arc[0].setColor(1, 0.2, 0.15, 0.6)

    def _end_hud_edit(self, save=True):
        hud = self.app.hud
        hud.editing = False
        for n in self.hud_edit.get("outlines", {}).values():
            n.removeNode()
        self.hud_edit = None
        if hud.match is None:
            hud.root.hide()
        hud.place_all()
        if save:
            self._save_settings()

    def _hud_edit_update(self, dt):
        hud = self.app.hud
        mw = self.app.base.mouseWatcherNode
        els = hud.layout()
        ar = self.app.getAspectRatio()
        # outlines
        outl = self.hud_edit["outlines"]
        for key, el in hud.elements.items():
            if key not in outl:
                outl[key] = self.root.attachNewNode("ol")
            o = outl[key]
            for ch in list(o.getChildren()):
                ch.removeNode()
            p = el.root.getPos()
            s = el.root.getScale()[0]
            b = el.bounds
            col = (0.2, 1, 1, 0.5) if els[key]["visible"] else (1, 0.3, 0.3, 0.5)
            x0, x1, y0, y1 = p.x + b[0] * s, p.x + b[1] * s, p.z + b[2] * s, p.z + b[3] * s
            for (a, bb, c, d) in ((x0, x1, y0, y0 + 0.003), (x0, x1, y1 - 0.003, y1),
                                  (x0, x0 + 0.003, y0, y1), (x1 - 0.003, x1, y0, y1)):
                T.card(o, a, bb, c, d, col)
            T.text(o, i18n.t("el_" + key), (x0, y1 + 0.01), 0.025, col, "left", self.ui.font)
        if mw is None or not mw.hasMouse():
            return
        mx_, my_ = mw.getMouse()
        ax = mx_ * ar
        ay = my_
        down = self.app.input.key_down("mouse1")
        drag = self.hud_edit["drag"]
        if down:
            if drag is None:
                key = hud.element_at(ax, ay)
                if key:
                    p = hud.elements[key].root.getPos()
                    self.hud_edit["drag"] = (key, p.x - ax, p.z - ay)
            else:
                key, ox, oy = drag
                nx = (ax + ox) / ar
                if i18n.is_rtl():
                    nx = -nx
                els[key]["x"] = max(-1.0, min(1.0, round(nx, 3)))
                els[key]["y"] = max(-1.0, min(1.0, round(ay + oy, 3)))
                hud.place_all()
        else:
            self.hud_edit["drag"] = None
        w = self.app.input.consume_wheel()
        if w:
            key = hud.element_at(ax, ay)
            if key:
                els[key]["scale"] = max(0.4, min(2.5, round(els[key]["scale"] + 0.1 * w, 2)))
                hud.place_all()
        rc = self.app.input.key_down("mouse3")
        if rc and not self.hud_edit.get("rc"):
            key = hud.element_at(ax, ay)
            if key:
                els[key]["visible"] = not els[key]["visible"]
                hud.place_all()
        self.hud_edit["rc"] = rc

    # ================================================================== pause / results
    def _build_pause(self):
        ar = self.app.getAspectRatio()
        T.card(self.root, -ar, ar, -1, 1, (0, 0.01, 0.015, 0.6))
        T.text(self.root, i18n.t("paused"), (0, 0.45), 0.1, T.CYAN, "center", self.ui.dfont)
        self.ui.button(self.root, i18n.t("resume"), (0, 0.2), lambda: self.app.set_paused(False),
                       0.7, 0.1, 0.05)
        self.ui.button(self.root, i18n.t("settings"), (0, 0.07), lambda: self._open_settings("pause"),
                       0.7, 0.1, 0.05)
        self.ui.button(self.root, i18n.t("quit_to_menu"), (0, -0.06), self.app.quit_to_menu, 0.7,
                       0.1, 0.05, sound="ui_back")

    def show_results(self, summary):
        self.show("results", summary=summary)

    def _build_results(self, summary):
        self._backdrop(False)
        won = summary["won"]
        title = i18n.t("res_title")
        if won is True:
            title = i18n.t("you_win")
        elif won is False:
            title = i18n.t("you_lose")
        T.text(self.root, title, (0, 0.7), 0.12, T.CYAN if won is not False else T.RED, "center",
               self.ui.dfont)
        T.text(self.root, i18n.t("mode_" + summary["mode"]) + "   " + summary["subtitle"],
               (0, 0.58), 0.045, T.WHITE, "center", self.ui.font)
        f = self.ui.frame(self.root, -0.8, 0.8, -0.62, 0.5)
        coin_line = i18n.t("res_coins", n=summary["coins"])
        if summary.get("diff_mult", 1.0) != 1.0:
            coin_line += "   (" + i18n.t("res_diff_mult", d=i18n.raw(
                "diff_" + summary.get("difficulty", "normal")), m="%g" % summary["diff_mult"]) + ")"
        lines = [("%s %d   %s %d" % (i18n.t("cs_kills"), summary["kills"], i18n.t("cs_deaths"),
                                     summary["deaths"]), T.WHITE),
                 (i18n.t("res_xp", n=summary["xp"]), T.GREEN),
                 (coin_line, T.GOLD)]
        if summary["new_best"]:
            lines.append((i18n.t("res_new_best"), T.GOLD))
        if summary["level_after"] > summary["level_before"]:
            lines.append((i18n.t("res_level_up", n=summary["level_after"]), T.CYAN))
        if summary["tier_after"] > summary["tier_before"]:
            lines.append((i18n.t("res_tier_up", n=summary["tier_after"]), T.CYAN))
        for name, tier in summary["tier_unlocks"]:
            lines.append((i18n.t("res_tier_unlock", weapon=name, n=tier), T.CYAN))
        for aid in summary["achievements"]:
            lines.append((i18n.t("res_achievement", name=i18n.pair("ach_" + aid)[0]), T.GOLD))
        for c in summary["challenges"]:
            lines.append((i18n.t("res_challenge", name=i18n.t("chl_" + c["id"], n=c["target"])),
                          T.GREEN))
        if summary.get("boosts"):
            lines.append((i18n.t("res_boosts", names=", ".join(
                i18n.raw("boost_" + b) for b in summary["boosts"])), T.GOLD))
        for i, (s, col) in enumerate(lines[:11]):
            self.ui.label(f, s, (0, 0.4 - i * 0.085), 0.045 if i < 3 else 0.036, col, "center")
        self.ui.button(self.root, i18n.t("res_continue"), (0, -0.76),
                       lambda: self.show("lobby" if self.app.net is not None else "main"), 0.7,
                       0.1, 0.05)
