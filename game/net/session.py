"""Client side of a multiplayer session.

Networking runs on background threads (connect, read); the main thread
drains a queue once per frame, so Panda3D objects are only touched from the
main thread.
"""

import logging
import math
import queue
import socket
import threading
import time
from collections import deque

from panda3d.core import Vec3

from neon_shared import GAME_VERSION
from neon_shared import protocol as P
from neon_shared import transport

from .. import i18n
from ..modes import player_loadout, player_tiers
from . import lan

log = logging.getLogger("net")
SEND_RATE = 20.0
INTERP_DELAY = 0.1


class NetSession:
    def __init__(self, app):
        self.app = app
        self.sock = None
        self.rx = queue.Queue()
        self.wlock = threading.Lock()
        self.my_id = None
        self.code = ""
        self.is_host = False
        self.lobby_players = []
        self.status = "connecting"
        self.error = None
        self.lan_server = None
        self.beacon = None
        self.closed = False
        self.match = None
        self.send_t = 0.0
        self.ping_t = 0.0
        self.rtt = 0.1
        self.seq = 0
        self.remote = {}          # server id -> deque of snapshots
        self.time_left = None
        self.score_limit = 25
        self.names = {}

    # ------------------------------------------------------------------ connect
    def _address(self):
        """Server address from settings: host:port, ws://... or wss://..."""
        return self.app.storage.settings["network"]["server"].strip() or \
            "127.0.0.1:%d" % P.DEFAULT_PORT

    def _addr(self):
        _, host, port, _ = transport.parse_address(self._address())
        return host, port

    def _hello(self):
        prof = self.app.storage.profile.data
        lo = player_loadout(self.app)       # same loadout the match will actually use
        tiers = player_tiers(prof)
        self.send({"t": "hello", "name": self.app.storage.settings["network"]["player_name"],
                   "ver": GAME_VERSION, "skin": prof["equipped"]["char_skin"],
                   "loadout": {k: lo[k] for k in ("primary", "secondary", "melee")},
                   "mods": {w: lo["mods"].get(w, {}) for w in (lo["primary"], lo["secondary"])},
                   "tiers": {w: tiers.get(w, 0) for w in (lo["primary"], lo["secondary"],
                                                          lo["melee"])}})

    def _start_thread(self, fn):
        threading.Thread(target=self._guard(fn), name="net-connect", daemon=True).start()

    def _guard(self, fn):
        def run():
            try:
                fn()
            except Exception as e:
                log.warning("network error: %s", e)
                self.rx.put({"t": "_error", "msg": str(e) or e.__class__.__name__})
        return run

    def _connect(self, address, port=None):
        """Connect to ``address`` (host:port, ws:// or wss://) or (host, port)."""
        if port is not None:
            address = "%s:%d" % (address, port)
        scheme = transport.parse_address(address)[0]
        # free hosting platforms may need up to a minute to wake a sleeping server
        wait = 75.0 if scheme != "tcp" else 5.0
        conn = transport.connect(address, timeout=wait, connect_timeout=8.0)
        conn.settimeout(None)
        self.sock = conn
        threading.Thread(target=self._reader, name="net-reader", daemon=True).start()
        self._hello()

    def _reader(self):
        conn = self.sock
        try:
            while not self.closed:
                line = conn.readline(P.MAX_LINE)
                if not line:
                    break
                try:
                    self.rx.put(P.decode(line))
                except ValueError:
                    continue
        except OSError:
            pass
        if not self.closed:
            self.rx.put({"t": "_error", "msg": "connection lost"})

    def host_online(self):
        """Host through the relay server; if it can't be reached, host the room on
        this PC instead (the game has the same server built in)."""
        def go():
            try:
                self._connect(self._address())
            except (OSError, ConnectionError) as e:
                log.info("relay unreachable (%s); hosting on this PC", e)
                self._host_local()
                return
            self.send({"t": "create", "config": self._config()})
        self.status = "connecting"
        self._start_thread(go)

    def join_online(self, code):
        """Join through the relay / host IP; falls back to finding the room on the LAN."""
        def go():
            try:
                self._connect(self._address())
            except (OSError, ConnectionError) as e:
                found = lan.find_room(code, 3.0)      # beacons, then a LAN scan
                if found is None:
                    raise OSError(self._friendly(e, "join")) from e
                self._connect(found[0], found[1])
            self.send({"t": "join", "code": code.upper()})
        self._start_thread(go)

    def join_direct(self, address, code):
        """Join a room found by the room browser (``address`` in any supported format)."""
        def go():
            try:
                self._connect(address)
            except (OSError, ConnectionError) as e:
                raise OSError(i18n.raw("mp_err_join_failed")) from e
            self.send({"t": "join", "code": code.upper()})
        self._start_thread(go)

    def _host_local(self):
        """Run the match server inside the game on this PC and join it."""
        from neon_shared.server_core import run_in_thread
        port = P.DEFAULT_PORT
        last = None
        for cand in (P.DEFAULT_PORT, P.DEFAULT_PORT + 2, P.DEFAULT_PORT + 3):
            try:
                self.lan_server, _ = run_in_thread("0.0.0.0", cand)
                port = cand
                break
            except OSError as e:
                last = e
        if self.lan_server is None:
            raise OSError(i18n.raw("mp_err_port")) from last
        self.hosted_locally = True
        self.local_addr = "%s:%d" % (lan.primary_ip(), port)
        self._connect("127.0.0.1", port)
        self.send({"t": "create", "config": self._config()})
        self.beacon = lan.Beacon(lambda: self.code, port,
                                 self.app.storage.settings["network"]["player_name"])

    def host_lan(self):
        self._start_thread(self._host_local)

    def join_lan(self, code):
        def go():
            found = lan.find_room(code, 4.0)          # beacons, then a LAN scan
            if found is None:
                raise OSError(i18n.raw("mp_not_found_lan", code=code))
            self._connect(found[0], found[1])
            self.send({"t": "join", "code": code.upper()})
        self._start_thread(go)

    def _friendly(self, e, action):
        """Human-readable reason for a failed connection."""
        addr = self._address()
        if isinstance(e, ConnectionRefusedError):
            return i18n.raw("mp_err_refused", addr=addr)
        if isinstance(e, (socket.timeout, TimeoutError)):
            return i18n.raw("mp_err_timeout", addr=addr)
        if isinstance(e, socket.gaierror):
            return i18n.raw("mp_err_address", addr=addr)
        return str(e) or e.__class__.__name__

    def _config(self):
        cfg = self.app.storage.profile["last_mode"]
        return {"time_limit": cfg.get("time_limit") or 8, "score_limit": cfg.get("score_limit", 25)}

    # ------------------------------------------------------------------ io
    def send(self, msg):
        s = self.sock
        if s is None or self.closed:
            return
        data = P.encode(msg)
        try:
            with self.wlock:
                s.send_line(data)
        except (OSError, ConnectionError) as e:
            self.rx.put({"t": "_error", "msg": str(e)})

    def request_start(self):
        self.send({"t": "start"})

    def status_text(self):
        if self.error:
            return i18n.t("mp_failed", err=self.error)
        if not self.code:
            return i18n.t("mp_connecting")
        if self.is_host and getattr(self, "hosted_locally", False):
            # the IP address is only shown on request (SHOW ADDRESS button in the lobby)
            return i18n.t("mp_hosting_local", code=self.code, _wrap=60)
        if self.is_host:
            return i18n.t("mp_waiting")
        return i18n.t("mp_host_only")

    def leave(self):
        if self.closed:
            return
        try:
            self.send({"t": "leave"})
        except Exception:
            pass
        self.closed = True
        if self.sock is not None:
            self.sock.close()
        if self.beacon:
            self.beacon.stop()
        if self.lan_server:
            self.lan_server.stop()
        if self.app.net is self:
            self.app.net = None

    # ------------------------------------------------------------------ per frame
    def update(self, dt):
        for _ in range(400):
            try:
                msg = self.rx.get_nowait()
            except queue.Empty:
                break
            h = getattr(self, "_m_" + msg["t"].lstrip("_"), None)
            if h is not None:
                try:
                    h(msg)
                except Exception:
                    log.exception("bad message %s", msg.get("t"))
        m = self.match
        if m is None or self.closed:
            return
        now = time.monotonic()
        self.ping_t -= dt
        if self.ping_t <= 0:
            self.ping_t = 2.0
            self.send({"t": "ping", "t0": now})
        self.send_t -= dt
        p = m.player
        if self.send_t <= 0 and p is not None and p.alive:
            self.send_t = 1.0 / SEND_RATE
            self.send({"t": "st", "p": [round(p.body.pos.x, 3), round(p.body.pos.y, 3),
                                        round(p.body.pos.z, 3)],
                       "yaw": round(p.yaw, 1), "pitch": round(p.pitch, 1),
                       "cr": int(p.crouching), "w": p.weapon().id})
        self._interpolate(now)

    # ------------------------------------------------------------------ lobby messages
    def _m_error(self, msg):
        self.error = msg.get("msg", "error")
        if self.match is not None:
            self._drop_to_menu(self.error)

    def _m_kick(self, msg):
        self.error = msg.get("msg", "kicked")
        self._drop_to_menu(self.error)

    def _drop_to_menu(self, err):
        self.match = None
        self.leave()
        self.app.quit_to_menu()
        self.app.menus.toast(i18n.t("mp_disconnected", err=err), 5.0)

    def _m_welcome(self, msg):
        self.my_id = msg["id"]

    def _m_room(self, msg):
        self.code = msg.get("code", "")
        self.is_host = msg.get("host") == self.my_id
        self.lobby_players = []
        for pl in msg.get("players", []):
            self.names[pl["id"]] = pl["name"]
            tag = "  [HOST]" if pl["id"] == msg.get("host") else ""
            me = "  <" if pl["id"] == self.my_id else ""
            self.lobby_players.append(pl["name"] + tag + me)

    def _m_pong(self, msg):
        t0 = msg.get("t0")
        if isinstance(t0, (int, float)):
            self.rtt = max(0.0, time.monotonic() - t0)
            self.send({"t": "rtt", "v": round(self.rtt, 3)})

    def _m_start(self, msg):
        self.score_limit = msg.get("score_limit", 25)
        self.time_left = msg.get("time_limit")
        self.remote = {}
        cfg = {"mode": "online", "online": True, "session": self, "start": msg,
               "score_limit": self.score_limit, "time_limit": 0}
        self.app.start_match(cfg)
        self.match = self.app.match

    # ------------------------------------------------------------------ match messages
    def _combatant(self, sid):
        m = self.match
        if m is None:
            return None
        return m.net_ids.get(sid)

    def _m_snap(self, msg):
        m = self.match
        if m is None:
            return
        self.time_left = msg.get("left")
        now = time.monotonic()
        for row in msg.get("pl", []):
            sid, x, y, z, yaw, pitch, cr, alive, hp, w, score, kills, deaths, ping = row
            c = self._combatant(sid)
            if c is None:
                c = m.mode.add_remote(sid, self.names.get(sid, "?"), "default")
            c.score, c.kills, c.deaths, c.ping = score, kills, deaths, ping
            if c.is_player:
                c.health = min(c.health, hp) if hp < c.health else hp
                if not alive and c.alive:
                    c.die()
                continue
            buf = self.remote.setdefault(sid, deque(maxlen=30))
            buf.append((now, Vec3(x, y, z), yaw, pitch, bool(cr), bool(alive)))
            c.health = hp
            if w and w != c.weapon().id:
                for i, ws in enumerate(c.weapons):
                    if ws.id == w:
                        c.slot = i

    def _interpolate(self, now):
        t = now - INTERP_DELAY
        for sid, buf in self.remote.items():
            c = self._combatant(sid)
            if c is None or not buf:
                continue
            a = buf[0]
            b = buf[-1]
            for i in range(len(buf) - 1):
                if buf[i][0] <= t <= buf[i + 1][0]:
                    a, b = buf[i], buf[i + 1]
                    break
            else:
                if t > buf[-1][0]:
                    a = b = buf[-1]
            span = b[0] - a[0]
            k = 0.0 if span <= 0 else min(1.0, max(0.0, (t - a[0]) / span))
            pos = a[1] + (b[1] - a[1]) * k
            dy = (b[2] - a[2] + 180) % 360 - 180
            c.body.pos = pos
            c.yaw = a[2] + dy * k
            c.pitch = a[3] + (b[3] - a[3]) * k
            c.crouching = b[4]
            if span > 0:
                v = (b[1] - a[1]) / span
                c.body.vel = Vec3(v.x, v.y, v.z)
            alive = b[5]
            if alive and not c.alive:
                c.alive = True
                if c.visual:
                    c.visual.show()
            elif not alive and c.alive:
                c.alive = False
                if c.visual:
                    c.visual.hide()

    def _m_shot(self, msg):
        m = self.match
        c = self._combatant(msg.get("id"))
        if m is None or c is None or not c.alive:
            return
        from neon_shared.weapons import BY_ID
        s = BY_ID.get(msg.get("w"))
        if s is None:
            return
        o = c.muzzle_pos()
        m.fx.muzzle(o, c.aim_dir(), s["color"], 0.45, light=True)
        m.audio.play_weapon(s["sfx"], o, c)
        for e in msg.get("e", []):
            v = Vec3(*P.vec3(e))
            if msg.get("proj"):
                m.projectiles.spawn(c, o + v * 0.3, v, s, s["name"])
            elif s["cls"] == "rail":
                m.fx.beam(o, v, s["color"], 0.12, 0.14, 4.0)
            else:
                m.fx.tracer(o, v, s["color"])
                m.fx.impact(v, Vec3(0, 0, 1), s["color"])

    def _m_hit(self, msg):
        m = self.match
        if m is None:
            return
        a = self._combatant(msg.get("a"))
        v = self._combatant(msg.get("v"))
        if v is None:
            return
        hp = msg.get("hp", 0)
        dmg = msg.get("dmg", 0)
        v.health = hp
        v.last_damage_time = m.time
        m.fx.blood(v.chest_pos(), (1.0, 0.3, 0.2) if msg.get("hs") else (0.2, 0.95, 1.0))
        if v.is_player and m.hud:
            ang = None
            if a is not None and a is not v:
                d = a.chest_pos() - v.body.pos
                ang = math.degrees(math.atan2(-d.x, d.y)) - v.yaw
                v.last_attacker = a
            m.hud.damage_taken(dmg, ang)
            m.player_ctrl.add_shake(min(0.25, dmg / 120.0))
        if a is not None and a.is_player and v is not a:
            self.hits_confirmed = getattr(self, "hits_confirmed", 0) + 1
            m.stats["damage"] += dmg
            m.stats["hits"] += 1
            wid = a.weapon().id
            m.stats["weapon_xp"][wid] = m.stats["weapon_xp"].get(wid, 0) + dmg / 10.0
            if m.hud:
                m.hud.hit_marker(kill=hp <= 0, head=bool(msg.get("hs")))
            m.audio.play2d("headshot" if msg.get("hs") else "hitmarker", 0.7)

    def _m_kill(self, msg):
        m = self.match
        if m is None:
            return
        k = self._combatant(msg.get("k"))
        v = self._combatant(msg.get("v"))
        if v is None:
            return
        v.health = 0
        v.alive = False
        v.respawn_timer = 1e9
        m.on_kill(v, k, msg.get("w", ""), bool(msg.get("hs")), "net")

    def _m_respawn(self, msg):
        m = self.match
        c = self._combatant(msg.get("id"))
        if m is None or c is None:
            return
        x, y, z, yaw = msg.get("p", [0, 0, 0, 0])
        m.spawn_at(c, (x, y, z), yaw)
        if not c.is_player:
            self.remote.pop(msg.get("id"), None)

    def _m_correct(self, msg):
        m = self.match
        if m is None or m.player is None:
            return
        m.player.body.pos = Vec3(*P.vec3(msg.get("p"), tuple(m.player.body.pos)))
        m.player.body.vel = Vec3(0, 0, 0)

    def _m_end(self, msg):
        m = self.match
        if m is None:
            return
        scores = msg.get("scores", [])
        place = 1 + next((i for i, row in enumerate(scores) if row[0] == self.my_id), 0)
        won = msg.get("winner") == self.my_id
        m.end({"won": won, "place": place, "mode": "ffa", "subtitle": i18n.t("place", n=place),
               "score": m.player.score if m.player else 0})
        self.match = None

    # ------------------------------------------------------------------ local actions
    def local_fire(self, ws, origin, fwd, dirs):
        """Returns the projectile sequence number (or None)."""
        self.fired = getattr(self, "fired", 0) + 1
        seq = None
        if ws.stats["speed"] > 0:
            self.seq += 1
            seq = self.seq
        self.send({"t": "fire", "w": ws.id, "o": [round(v, 3) for v in origin],
                   "d": [round(v, 4) for v in fwd],
                   "ds": [[round(v, 4) for v in d] for d in dirs], "seq": seq})
        return seq

    def local_melee(self, ws, origin, fwd):
        self.send({"t": "melee", "w": ws.id, "o": [round(v, 3) for v in origin],
                   "d": [round(v, 4) for v in fwd]})

    def local_reload(self, ws):
        self.send({"t": "reload", "w": ws.id})

    def projectile_hit(self, seq, target, pos):
        sid = None
        if target is not None and not getattr(target, "is_hazard", False):
            sid = getattr(target, "net_id", None)
        self.send({"t": "phit", "seq": seq, "tgt": sid, "pos": [round(v, 3) for v in pos]})
