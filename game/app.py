"""NEON GRID application: window, subsystems and the top-level state machine.

States:  loading -> title -> menu <-> match -> results -> menu
A bot-only "showcase" match runs behind the title and menus as a live
background.  The main loop is crash-safe: an exception inside a match is
written to the crash log and the game returns to the menu instead of dying.
"""

import logging
import math
import os
import sys

from panda3d.core import ClockObject, Filename, Vec3, loadPrcFileData

from . import crashlog, i18n, paths
from .storage import Storage

log = logging.getLogger("app")


def configure_prc(settings, offscreen=False):
    v = settings["video"]
    w, h = v["resolution"]
    lines = [
        "window-title NEON GRID",
        "win-size %d %d" % (w, h),
        "fullscreen %s" % ("#t" if v["fullscreen"] else "#f"),
        "sync-video %s" % ("#t" if v["vsync"] else "#f"),
        "textures-power-2 none",
        "audio-library-name p3openal_audio",
        "show-frame-rate-meter #f",
        "framebuffer-srgb #f",
        "gl-coordinate-system default",
        "notify-level-glgsg warning",
        "notify-level-display warning",
        "default-model-extension .bam",
        "support-threads #t",
        "texture-anisotropic-degree 8",
        "want-pstats #f",
        "load-display pandagl",
        "aux-display pandadx9",
        "garbage-collect-states #t",
        "vfs-case-sensitive #f",
    ]
    ico = paths.asset("icon.ico")
    if os.path.exists(ico):
        lines.append("icon-filename %s" % Filename.fromOsSpecific(ico).getFullpath())
    if getattr(sys, "frozen", False):
        # plugins live next to the bundled panda3d package
        root = paths.resource_root()
        lines.append("plugin-path %s" % Filename.fromOsSpecific(
            os.path.join(root, "panda3d")).getFullpath())
    if offscreen:
        lines.append("window-type offscreen")
    loadPrcFileData("neongrid", "\n".join(lines))


class NeonGridApp:
    """Created in main.py.  Wraps a ShowBase instance (self.base)."""

    def __init__(self, args=None):
        self.args = args or {}
        if any(self.args.get(k) for k in ("autotest", "menutest", "nettest")):
            from .storage import JsonStore
            JsonStore.read_only = True
        self.storage = Storage()
        if self.args.get("quality"):          # CLI override (not saved)
            self.storage.settings["video"]["quality"] = self.args["quality"]
        if self.args.get("lang"):
            self.storage.settings["language"] = self.args["lang"]
        i18n.set_language(self.storage.settings["language"])
        self._apply_default_server()
        configure_prc(self.storage.settings.data, offscreen=self.args.get("offscreen", False))
        from direct.showbase.ShowBase import ShowBase
        self.base = ShowBase()
        b = self.base
        b.disableMouse()
        b.setBackgroundColor(0, 0.01, 0.015, 1)
        b.camLens.setNearFar(0.05, 400.0)
        self.render = b.render
        self.aspect2d = b.aspect2d
        self.a2dTopLeft = b.a2dTopLeft
        self.camera = b.camera
        self.camLens = b.camLens
        self.win = b.win
        self.loader = b.loader
        self.clock = ClockObject.getGlobalClock()
        self._apply_fps_cap()

        from .gfx.postfx import PostFX
        from .gfx.textures import TextureBank
        from .input import InputManager
        from .ui.theme import Fonts, UITextures
        self.fonts = Fonts(b.loader)
        self.textures = TextureBank()
        self.ui_textures = UITextures()
        v = self.storage.settings["video"]
        self.postfx = PostFX(b, v["quality"] == "high" and v["bloom"] > 0, v["bloom"])
        self.input = InputManager(b, self.storage.settings.data)
        from .gfx.scope import ScopeView
        self.scope = ScopeView(b, v["quality"])
        from .audio.manager import AudioManager
        self.audio = AudioManager(b, self.storage.settings.data)
        self.nav_graph = None
        self.match = None
        self.showcase = None
        self.state = "loading"
        self.paused = False
        self.hud = None
        self.menus = None
        self.debug = None
        self.results = None
        self.net = None
        self.fly_t = 0.0
        self.error_notice = None
        b.accept("window-event", self._on_window_event)
        b.accept("escape", self._on_escape)
        b.accept("f10", self._on_f10)
        b.taskMgr.add(self._main_task, "neongrid-main", sort=10)
        self._loading_sequence()

    # ------------------------------------------------------------------ helpers
    def _apply_default_server(self):
        """Use the relay baked into assets/config.json unless the player picked their own."""
        import json
        try:
            with open(paths.asset("config.json"), encoding="utf-8") as f:
                default = (json.load(f).get("default_server") or "").strip()
        except (OSError, ValueError):
            return
        if not default:
            return
        net = self.storage.settings["network"]
        if net.get("server", "").strip() in ("", "127.0.0.1:47777", "localhost:47777") or \
                net.get("server_from_config"):
            net["server"] = default
            net["server_from_config"] = True       # follow future config changes too

    def getAspectRatio(self):
        return self.base.getAspectRatio()

    def set_fov(self, fov):
        self.camLens.setFov(max(30.0, min(130.0, fov)))

    def _apply_fps_cap(self):
        v = self.storage.settings["video"]
        cap = v.get("fps_cap", 0)
        if cap and not v["vsync"]:
            self.clock.setMode(ClockObject.MLimited)
            self.clock.setFrameRate(cap)
        else:
            self.clock.setMode(ClockObject.MNormal)

    def get_nav(self, coll):
        """Navigation graphs are expensive to build, so keep one per map."""
        from neon_shared import arena_layout as L
        if self.nav_graph is None:
            self.nav_graph = {}
        nav = self.nav_graph.get(L.CURRENT)
        if nav is None:
            from .entities.nav import NavGraph
            nav = self.nav_graph[L.CURRENT] = NavGraph(coll)
        else:
            nav.coll = coll
        return nav

    def menus_open(self):
        return self.paused or (self.debug is not None and self.debug.visible)

    # ------------------------------------------------------------------ boot
    def _loading_sequence(self):
        from .ui import theme as T
        b = self.base
        node = self.aspect2d.attachNewNode("loading")
        font = self.fonts.get("display")
        T.text(node, "NEON GRID", (0, 0.1), 0.16, T.CYAN, "center", font)
        msg = T.text(node, i18n.t("loading"), (0, -0.1), 0.05, T.WHITE, "center",
                     self.fonts.get("ui"))
        for _ in range(2):
            b.graphicsEngine.renderFrame()
        T.set_text(msg, i18n.t("loading_audio"))
        b.graphicsEngine.renderFrame()
        self.audio.generate()
        self.audio.load()
        T.set_text(msg, i18n.t("loading"))
        b.graphicsEngine.renderFrame()
        from .ui.hud import HUD
        from .ui.menus import Menus
        from .ui.debug_menu import DebugMenu
        self.hud = HUD(self)
        self.debug = DebugMenu(self)
        self.menus = Menus(self)
        node.removeNode()
        self.start_showcase()
        if self.args.get("autotest"):
            self.start_match(self.args["autotest"])
            self.state = "match"
        elif self.args.get("nettest"):
            self._nettest_begin()
        elif self.args.get("menutest"):
            self.state = "menu"
            self._menutest_steps = self._menutest_plan()
            b.taskMgr.doMethodLater(1.5, self._menutest_step, "menutest")
        else:
            self.state = "title"
            self.menus.show("title")
        self.audio.start_music(menu=not self.args.get("autotest"))

    # ------------------------------------------------------------------ showcase
    def start_showcase(self):
        if self.showcase is not None:
            return
        from .match import Match
        self.showcase = Match(self, {"mode": "ffa"}, showcase=True)
        self.fly_t = 0.0

    def stop_showcase(self):
        if self.showcase is not None:
            self.showcase.cleanup()
            self.showcase = None

    def _fly_camera(self, dt):
        self.fly_t += dt * 0.05
        t = self.fly_t
        r = 22.0 + 6.0 * math.sin(t * 0.7)
        x = math.cos(t) * r
        y = math.sin(t) * r
        z = 5.0 + 2.5 * math.sin(t * 1.3)
        self.camera.setPos(x, y, z)
        self.camera.lookAt(math.cos(t + 1.2) * 4, math.sin(t + 1.2) * 4, 1.5)
        self.set_fov(80)

    # ------------------------------------------------------------------ matches
    def start_match(self, config):
        self.stop_showcase()
        self.close_match()
        from .match import Match
        self.menus.hide_all()
        self.paused = False
        self.match = Match(self, config)
        if self.args.get("autoplay"):
            self._install_autoplay()
        self.state = "match"
        self.input.set_captured(not self.args.get("offscreen"))
        self.audio.menu_music = False
        log.info("Match started: %s", config)

    def _install_autoplay(self):
        """Debug/testing: let a bot brain drive the local player."""
        from .entities.bot import BotBrain
        m = self.match
        brain = BotBrain(m, m.player, "hard")
        ctrl = m.player_ctrl
        orig = ctrl.update

        def upd(dt):
            orig(dt)
            brain.update(dt)
        ctrl.update = upd

    def close_match(self):
        if self.match is not None:
            try:
                self.match.cleanup()
            except Exception:
                log.exception("match cleanup failed")
            self.match = None
        if self.net is not None and self.state != "match":
            pass

    def finish_match(self):
        """Called when the end-of-match delay expires: apply rewards, show results."""
        m = self.match
        from .progression.rewards import apply_match
        summary = apply_match(self, m)
        self.close_match()
        self.input.set_captured(False)
        self.start_showcase()
        self.audio.menu_music = True
        self.state = "menu"
        self.menus.show_results(summary)

    def quit_to_menu(self):
        if self.net is not None:
            self.net.leave()
        self.close_match()
        self.paused = False
        self.input.set_captured(False)
        self.start_showcase()
        self.audio.menu_music = True
        self.state = "menu"
        self.menus.show("main")

    # ------------------------------------------------------------------ input events
    def _on_escape(self):
        if self.debug and self.debug.visible:
            self.debug.toggle()
            return
        if self.menus and self.menus.handle_escape():
            return
        if self.state == "match" and self.match is not None:
            self.set_paused(not self.paused)

    def set_paused(self, on):
        self.paused = on
        if on:
            self.input.set_captured(False)
            self.menus.show("pause")
        else:
            self.menus.hide_all()
            self.input.set_captured(True)

    def _on_f10(self):
        from panda3d.core import KeyboardButton
        mw = self.base.mouseWatcherNode
        if mw.isButtonDown(KeyboardButton.control()) and mw.isButtonDown(KeyboardButton.shift()):
            self.debug.toggle()

    def _on_window_event(self, win):
        self.base.windowEvent(win)
        if win is not self.base.win:
            return
        props = win.getProperties()
        if not props.getOpen():
            self.shutdown()
            return
        self.postfx.update_aspect()
        h = win.getYSize()
        for m in (self.match, self.showcase):
            if m is not None:
                m.fx.set_screen_height(h)
        if self.hud:
            self.hud.place_all()
        if self.state == "match" and not self.paused and props.getForeground() is False:
            # alt-tab: release the mouse
            self.set_paused(True)

    # ------------------------------------------------------------------ main loop
    def _main_task(self, task):
        dt = min(self.clock.getDt(), 0.05)
        try:
            self.input.poll()
            if self.net is not None:
                self.net.update(dt)
            if self.state == "match" and self.match is not None:
                if not self.paused or self.net is not None:
                    self.match.update(dt)
                m = self.match
                if m is not None and m.state == "ended" and m.state_t <= 0:
                    self.finish_match()
            elif self.showcase is not None:
                self.showcase.update(dt)
                self._fly_camera(dt)
            if self.menus:
                self.menus.update(dt)
            if self.debug:
                self.debug.update(dt)
            self.audio.update(dt, self.camera)
            if self.args.get("autotest"):
                self._autotest_tick(dt)
        except Exception:
            path = crashlog.write_crash(context="main loop, state=%s" % self.state)
            log.error("Recovered from error; crash log at %s", path)
            if self.args.get("autotest"):
                raise
            self._recover(path)
        return task.cont

    def _recover(self, path):
        try:
            self.close_match()
        except Exception:
            pass
        self.match = None
        self.paused = False
        self.input.set_captured(False)
        self.state = "menu"
        try:
            self.stop_showcase()
            self.start_showcase()
        except Exception:
            self.showcase = None
        self.menus.show("main")
        self.menus.toast("Error recovered - see %s" % path, 6.0)

    # ------------------------------------------------------------------ LAN end-to-end harness
    def _nettest_begin(self):
        from .net.session import NetSession
        self.state = "menu"
        self.net = NetSession(self)
        self.storage.profile["last_mode"]["map"] = self.args.get("map") or "grid"   # read-only run
        self.net.host_lan()
        self.args["autotest"] = {"mode": "online"}      # enables screenshots/duration
        self._nt_started = False
        self.base.taskMgr.add(self._nettest_task, "nettest")

    def _nettest_task(self, task):
        n = self.net
        if n is None:
            return task.done
        if n.code and not getattr(self, "_nt_bot", False):
            self._nt_bot = True
            import tests.netbot as nb
            port = n.lan_server._server.sockets[0].getsockname()[1]  # noqa: F841
            nb.run(port, n.code, duration=self.args.get("duration", 20))
        if n.code and len(n.lobby_players) >= 2 and not self._nt_started:
            self._nt_started = True
            n.request_start()
            if self.args.get("autoplay"):
                def later(t):
                    if self.match is not None:
                        self._install_autoplay()
                    return t.done
                self.base.taskMgr.doMethodLater(0.5, later, "nt-auto")
            return task.done
        return task.cont

    # ------------------------------------------------------------------ menu screenshot harness
    def _menutest_plan(self):
        steps = []
        for lang in ("en", "he"):
            steps.append(("lang", lang))
            for scr in ("title", "main", "play", "multiplayer", "loadout", "battlepass",
                        "locker", "career", "story"):
                steps.append(("show", scr, {}))
            for tab in ("video", "audio", "controls", "gameplay", "hud", "language"):
                steps.append(("show", "settings", {"tab": tab}))
            steps.append(("hudedit",))
            steps.append(("lockedpreview",))
            steps.append(("gunsmith",))
            steps += [("roomsetup",), ("roomshow",), ("roomshot",), ("lobbyshot",)]
            for tab in ("weapons", "attachments", "upgrades", "boosts"):
                steps.append(("show", "shop", {"tab": tab}))
            steps.append(("show", "results", {"summary": {
                "won": True, "mode": "ffa", "subtitle": "#1", "xp": 1450, "coins": 88,
                "level_before": 3, "level_after": 4, "tier_before": 2, "tier_after": 3,
                "achievements": ["first_blood"], "challenges": [], "tier_unlocks": [("AR-7 Pulse", 1)],
                "new_best": True, "kills": 12, "deaths": 3, "wave": 0, "place": 1}}))
        return steps

    def _menutest_step(self, task):
        out = self.args.get("shots_dir")
        if not self._menutest_steps:
            self.shutdown()
            return task.done
        step = self._menutest_steps.pop(0)
        if step[0] == "hudedit":
            self.menus._start_hud_edit()
            self.base.graphicsEngine.renderFrame()
            self.menus.update(0.016)
            self.base.graphicsEngine.renderFrame()
            fn = os.path.join(out, "menu_%s_hudedit.png" % i18n.language())
            self.base.win.saveScreenshot(Filename.fromOsSpecific(fn))
            self.menus._end_hud_edit(save=False)
            return task.again
        if step[0] == "roomsetup":
            if self.net is None:
                from .net.session import NetSession
                self.net = NetSession(self)
                self.net.host_lan()
            task.delayTime = 2.5
            return task.again
        if step[0] == "roomshow":
            self.menus.show("rooms")
            task.delayTime = 4.0
            return task.again
        if step[0] == "lobbyshot":
            self.menus.show("lobby")
            self.menus._lobby_poll()
            self.base.graphicsEngine.renderFrame()
            self.base.graphicsEngine.renderFrame()
            fn = os.path.join(out, "menu_%s_lobby.png" % i18n.language())
            self.base.win.saveScreenshot(Filename.fromOsSpecific(fn))
            task.delayTime = 0.4
            return task.again
        if step[0] == "roomshot":
            self.menus.show("rooms")
            self.base.graphicsEngine.renderFrame()
            self.base.graphicsEngine.renderFrame()
            fn = os.path.join(out, "menu_%s_rooms.png" % i18n.language())
            self.base.win.saveScreenshot(Filename.fromOsSpecific(fn))
            self.menus._stop_browser()
            task.delayTime = 0.4
            return task.again
        if step[0] == "gunsmith":
            pd = self.storage.profile.data
            pd["owned_mods"] = ["suppressor", "reddot"]
            pd["weapon_mods"] = {"ar7": {"muzzle": "suppressor", "optic": "reddot"}}
            self.menus.gs_weapon = "ar7"
            self.menus.gs_preview = {"magazine": "extmag"}
            self.menus.show("gunsmith")
            self.base.graphicsEngine.renderFrame()
            self.base.graphicsEngine.renderFrame()
            fn = os.path.join(out, "menu_%s_gunsmith.png" % i18n.language())
            self.base.win.saveScreenshot(Filename.fromOsSpecific(fn))
            return task.again
        if step[0] == "lockedpreview":
            self.menus.lo_preview = {"primary": "lance", "ability0": "emp"}
            self.menus.loadout_focus = "primary"
            self.menus.show("loadout")
            self.base.graphicsEngine.renderFrame()
            self.base.graphicsEngine.renderFrame()
            fn = os.path.join(out, "menu_%s_loadout_locked.png" % i18n.language())
            self.base.win.saveScreenshot(Filename.fromOsSpecific(fn))
            self.menus.lo_preview = {}
            return task.again
        if step[0] == "lang":
            self.storage.settings["language"] = step[1]
            i18n.set_language(step[1])
            self.hud.rebuild()
            return task.again
        name, kw = step[1], step[2]
        self.menus.show(name, **kw)
        self.base.graphicsEngine.renderFrame()
        self.base.graphicsEngine.renderFrame()
        tag = name + ("_" + kw["tab"] if "tab" in kw else "")
        fn = os.path.join(out, "menu_%s_%s.png" % (i18n.language(), tag))
        self.base.win.saveScreenshot(Filename.fromOsSpecific(fn))
        task.delayTime = 0.4
        return task.again

    # ------------------------------------------------------------------ automated test hook
    _at_time = 0.0
    _at_shots = 0

    def _autotest_tick(self, dt):
        self._at_time += dt
        fx = self.args.get("fxtest")
        if fx and self.match is not None and self.match.player is not None:
            m = self.match
            k = int(self._at_time / 2.0)
            if k != getattr(self, "_fx_k", -1) and self._at_time > 3.5:
                self._fx_k = k
                p = m.player
                pos = p.eye_pos() + p.aim_dir() * 9 - Vec3(0, 0, 1.2)
                kind = ["explosive", "plasma", "fire", "flash", "emp"][k % 5]
                m.fx.explosion(pos, 4.5, kind)
                if kind == "fire":
                    m.fx.fire_zone(Vec3(pos.x, pos.y, 0), 4.0, 3.0)
                self._fx_shot_at = self._at_time + 0.12
            if getattr(self, "_fx_shot_at", 0) and self._at_time >= self._fx_shot_at:
                self._fx_shot_at = 0
                fn = os.path.join(self.args["shots_dir"], "fx_%02d.png" % self._fx_k)
                self.base.win.saveScreenshot(Filename.fromOsSpecific(fn))
        endat = self.args.get("endat")
        if endat and self.match is not None:
            if self._at_time > endat - 2.5 and not self.debug.visible and not getattr(self, "_dbg_done", False):
                self._dbg_done = True
                self.debug.toggle()               # exercise the debug menu
            if self._at_time > endat and self.match.state != "ended":
                self.debug.toggle()
                self.debug._end_win()
        interval = self.args.get("shot_interval", 4.0)
        out = self.args.get("shots_dir")
        if out and self._at_time > (self._at_shots + 1) * interval:
            self._at_shots += 1
            fn = os.path.join(out, "shot_%02d.png" % self._at_shots)
            self.base.win.saveScreenshot(Filename.fromOsSpecific(fn))
            if self.match is not None:
                m = self.match
                log.info("autotest t=%.1f fps=%.1f alive=%d kills=%s", self._at_time,
                         self.clock.getAverageFrameRate(),
                         len(m.living_combatants()), [c.kills for c in m.combatants])
        if self._at_time > self.args.get("duration", 20):
            log.info("autotest complete, avg fps %.1f", self.clock.getAverageFrameRate())
            if self.net is not None:
                log.info("net: shots sent %d, hits confirmed %d",
                         getattr(self.net, "fired", 0), getattr(self.net, "hits_confirmed", 0))
            self.shutdown()

    def is_test_run(self):
        return any(self.args.get(k) for k in ("autotest", "menutest", "nettest"))

    def shutdown(self):
        try:
            if not self.is_test_run():  # automated tests never touch the player's saves
                self.storage.save_all()
        except Exception:
            pass
        if self.net is not None:
            try:
                self.net.leave()
            except Exception:
                pass
        self.base.userExit()

    def run(self):
        self.base.run()
