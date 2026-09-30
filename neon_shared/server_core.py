"""Authoritative match server (standard library only).

Used two ways:
  * ``server/relay_server.py`` runs it on a VPS for internet play (rooms are
    created/joined with 4-letter codes).
  * The game embeds it in a background thread for LAN hosting.

Server-authoritative rules & anti-cheat sanity checks
----------------------------------------------------
* Health, damage, kills, respawns, scores and the match clock live here only.
* Hitscan shots are re-traced on the server against *lag-compensated* player
  positions (rewound by the shooter's latency) and static arena geometry.
* Projectile hits reported by clients are validated: the shot must exist,
  travel time must be plausible, the impact must lie on the fired ray and the
  target must have been near the impact point.
* Movement uses a token-bucket speed limit (allows dashes/slides/jump pads
  but not speed hacks) plus arena bounds; violations snap the player back.
* Fire rate, magazine size (vs. reloads), weapon ownership, shot origin vs.
  server position and pellet cone are checked for every shot.
* Repeated violations get the client kicked.
"""

import asyncio
import collections
import logging
import math
import random
import time

from . import arena_layout as L
from . import protocol as P
from .hitmath import first_static_hit, hit_combatant, normalize
from .weapons import BY_ID, damage_at, weapon_stats

log = logging.getLogger("neongrid.server")

SPEED_BUDGET_RATE = 21.0      # m/s sustained (knife sprint 14 m/s x Overdrive x tier + margin)
SPEED_BUDGET_MAX = 14.0       # burst metres (dash is 8 m)
MAX_REWIND = 0.35
RESPAWN_DELAY = 3.0
VIOLATION_KICK = 10


class Player:
    def __init__(self, pid, writer):
        self.id = pid
        self.writer = writer
        self.name = "Runner"
        self.skin = "default"
        self.room = None
        self.weapons = {}
        self.pos = (0.0, 0.0, 0.0)
        self.yaw = 0.0
        self.pitch = 0.0
        self.crouch = False
        self.weapon = ""
        self.alive = False
        self.hp = 100.0
        self.kills = self.deaths = self.score = 0
        self.last_state = time.monotonic()
        self.budget = SPEED_BUDGET_MAX
        self.history = collections.deque(maxlen=40)     # (t, pos, crouch)
        self.last_fire = {}
        self.shots_since_reload = {}
        self.reload_at = {}
        self.pending = {}      # projectile seq -> (t, wid, o, d)
        self.violations = collections.deque(maxlen=64)
        self.rtt = 0.1
        self.respawn_at = 0.0
        self.last_damage = 0.0
        self.closed = False

    def send(self, msg):
        if self.closed:
            return
        try:
            self.writer.write(P.encode(msg))
        except Exception:
            self.closed = True

    def eye(self):
        return (self.pos[0], self.pos[1], self.pos[2] + (1.05 if self.crouch else 1.62))

    def pos_at(self, t):
        """Lag compensation: interpolated position at server time ``t``."""
        h = self.history
        if not h:
            return self.pos, self.crouch
        if t >= h[-1][0]:
            return h[-1][1], h[-1][2]
        prev = h[0]
        for item in h:
            if item[0] >= t:
                t0, p0, c0 = prev
                t1, p1, c1 = item
                k = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                k = min(1.0, max(0.0, k))
                return tuple(p0[i] + (p1[i] - p0[i]) * k for i in range(3)), c1
            prev = item
        return h[0][1], h[0][2]


class Room:
    def __init__(self, code, host):
        self.code = code
        self.host = host
        self.players = {}
        self.state = "lobby"
        self.time_limit = 8 * 60
        self.score_limit = 25
        self.start_time = 0.0
        self.set_map("grid")

    def set_map(self, map_id):
        self.layout = L.get(L.valid(map_id))
        self.map = self.layout.map_id

    def broadcast(self, msg, exclude=None):
        for p in self.players.values():
            if p is not exclude:
                p.send(msg)

    def lobby_msg(self):
        return {"t": "room", "code": self.code, "host": self.host,
                "players": [{"id": p.id, "name": p.name, "skin": p.skin}
                            for p in self.players.values()], "state": self.state,
                "map": self.map, "mode": "ffa", "score_limit": self.score_limit,
                "time_limit": self.time_limit}


class GameServer:
    def __init__(self, max_rooms=500):
        self.rooms = {}
        self.players = {}
        self.next_id = 1
        self.max_rooms = max_rooms
        self.rng = random.Random()
        self._server = None
        self.loop = None

    # ------------------------------------------------------------------ plumbing
    async def serve(self, host="0.0.0.0", port=P.DEFAULT_PORT):
        self.loop = asyncio.get_running_loop()
        from .transport import accept

        async def on_connect(reader, writer):
            # raw TCP, WebSocket and plain-HTTP health checks share one port
            await accept(reader, writer, self._client)
        self._server = await asyncio.start_server(on_connect, host, port, limit=P.MAX_LINE)
        log.info("NEON GRID server listening on %s:%d", host, port)
        tick = asyncio.create_task(self._tick_loop())
        try:
            async with self._server:
                await self._server.serve_forever()
        finally:
            tick.cancel()

    def stop(self):
        if self._server is not None and self.loop is not None:
            self.loop.call_soon_threadsafe(self._server.close)

    async def _client(self, reader, writer):
        pid = self.next_id
        self.next_id += 1
        p = Player(pid, writer)
        self.players[pid] = p
        try:
            sock = writer.get_extra_info("socket")
            if sock is not None:
                import socket
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        p.send({"t": "welcome", "id": pid})
        try:
            while not p.closed:
                line = await reader.readline()
                if not line:
                    break
                try:
                    msg = P.decode(line)
                except ValueError:
                    self._violation(p, "garbage")
                    continue
                self._dispatch(p, msg)
                try:
                    await writer.drain()
                except ConnectionError:
                    break
        except (ConnectionError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            pass
        finally:
            self._leave(p)
            self.players.pop(pid, None)
            try:
                writer.close()
            except Exception:
                pass

    def _dispatch(self, p, msg):
        handler = getattr(self, "_on_" + str(msg.get("t")), None)
        if handler is None:
            return
        try:
            handler(p, msg)
        except Exception:
            log.exception("handler error for %s", msg.get("t"))

    # ------------------------------------------------------------------ lobby
    def _on_hello(self, p, m):
        p.name = str(m.get("name", "Runner"))[:14] or "Runner"
        p.skin = str(m.get("skin", "default"))[:24]
        lo = m.get("loadout") or {}
        tiers = m.get("tiers") or {}
        mods = m.get("mods") if isinstance(m.get("mods"), dict) else {}
        p.weapons = {}
        for slot in ("primary", "secondary", "melee"):
            wid = lo.get(slot)
            if wid in BY_ID:
                try:
                    tier = int(tiers.get(wid, 0))
                except (TypeError, ValueError):
                    tier = 0
                p.weapons[wid] = weapon_stats(wid, max(0, min(5, tier)), mods.get(wid))
        if not p.weapons:
            p.weapons = {"vx9": weapon_stats("vx9"), "katana": weapon_stats("katana")}

    def _new_code(self):
        for _ in range(200):
            code = "".join(self.rng.choice(P.CODE_LETTERS) for _ in range(4))
            if code not in self.rooms:
                return code
        raise RuntimeError("no free room codes")

    def _on_create(self, p, m):
        self._leave(p)
        if len(self.rooms) >= self.max_rooms:
            p.send({"t": "error", "msg": "server full"})
            return
        room = Room(self._new_code(), p.id)
        cfg = m.get("config") or {}
        try:
            room.time_limit = max(60, min(30 * 60, int(cfg.get("time_limit", 8)) * 60))
            room.score_limit = max(5, min(100, int(cfg.get("score_limit", 25))))
        except (TypeError, ValueError):
            pass
        room.set_map(str(cfg.get("map", "grid")))
        self.rooms[room.code] = room
        room.players[p.id] = p
        p.room = room
        p.send(room.lobby_msg())
        log.info("room %s created by %s", room.code, p.name)

    def _on_join(self, p, m):
        code = str(m.get("code", "")).upper()[:4]
        room = self.rooms.get(code)
        if room is None:
            p.send({"t": "error", "msg": "room %s not found" % code})
            return
        if len(room.players) >= P.MAX_PLAYERS:
            p.send({"t": "error", "msg": "room is full"})
            return
        self._leave(p)
        room.players[p.id] = p
        p.room = room
        room.broadcast(room.lobby_msg())
        if room.state == "live":
            # join in progress
            self._send_start(room, only=p)
            self._respawn(room, p)

    def _on_map(self, p, m):
        """Host picks the map while the room is still in the lobby."""
        room = p.room
        if room is None or room.host != p.id or room.state == "live":
            return
        room.set_map(str(m.get("map", "grid")))
        room.broadcast(room.lobby_msg())

    def _on_start(self, p, m):
        room = p.room
        if room is None or room.host != p.id or room.state == "live":
            return
        room.state = "live"
        room.start_time = time.monotonic()
        for q in room.players.values():
            q.kills = q.deaths = q.score = 0
        self._send_start(room)
        now = time.monotonic()
        for q in room.players.values():
            q.hp = 100.0
            q.alive = True
            q.respawn_at = now
            q.budget = SPEED_BUDGET_MAX
            q.last_state = now
            q.history.clear()
            q.shots_since_reload.clear()
            q.reload_at.clear()
        room.broadcast(room.lobby_msg())

    def _send_start(self, room, only=None):
        spawns = {}
        for q in room.players.values():
            x, y, yaw = self._spawn_point(room, q)
            q.pos = (x, y, 0.0)
            q.yaw = yaw
            spawns[str(q.id)] = [x, y, 0.0, yaw]
        msg = {"t": "start", "spawns": spawns, "time_limit": room.time_limit,
               "score_limit": room.score_limit, "map": room.map, "mode": "ffa",
               "players": [{"id": q.id, "name": q.name, "skin": q.skin, "w": list(q.weapons)}
                           for q in room.players.values()]}
        if only is not None:
            only.send(msg)
        else:
            room.broadcast(msg)

    def _leave(self, p):
        room = p.room
        if room is None:
            return
        room.players.pop(p.id, None)
        p.room = None
        if not room.players:
            self.rooms.pop(room.code, None)
            log.info("room %s closed", room.code)
            return
        if room.host == p.id:
            room.host = next(iter(room.players))
        room.broadcast(room.lobby_msg())

    def _on_leave(self, p, m):
        self._leave(p)

    def _on_ping(self, p, m):
        p.send({"t": "pong", "t0": m.get("t0")})

    def _on_list(self, p, m):
        """Room browser: every open room on this server (works before 'hello')."""
        rooms = []
        for r in list(self.rooms.values())[:200]:
            host = r.players.get(r.host)
            rooms.append({"code": r.code, "host": host.name if host else "?",
                          "players": len(r.players), "max": P.MAX_PLAYERS, "state": r.state,
                          "score_limit": r.score_limit, "time_limit": r.time_limit,
                          "map": r.map})
        p.send({"t": "rooms", "rooms": rooms})

    def _on_rtt(self, p, m):
        try:
            p.rtt = max(0.0, min(1.0, float(m.get("v", 0.1))))
        except (TypeError, ValueError):
            pass

    # ------------------------------------------------------------------ movement
    def _on_st(self, p, m):
        room = p.room
        if room is None or room.state != "live" or not p.alive:
            return
        now = time.monotonic()
        dt = min(0.5, now - p.last_state)
        p.last_state = now
        new = P.vec3(m.get("p"), p.pos)
        p.budget = min(SPEED_BUDGET_MAX, p.budget + SPEED_BUDGET_RATE * dt)
        dh = math.hypot(new[0] - p.pos[0], new[1] - p.pos[1])
        ok = True
        if dh > p.budget + 1.0:
            ok = False
        lay = room.layout
        if abs(new[0]) > lay.HALF + 0.5 or abs(new[1]) > lay.HALF + 0.5 or \
                new[2] < -1.0 or new[2] > lay.CEILING_Z:
            ok = False
        if not ok:
            self._violation(p, "speed/bounds")
            p.send({"t": "correct", "p": list(p.pos)})
            return
        p.budget -= dh
        p.pos = new
        try:
            p.yaw = float(m.get("yaw", 0.0)) % 360.0
            p.pitch = max(-90.0, min(90.0, float(m.get("pitch", 0.0))))
        except (TypeError, ValueError):
            pass
        p.crouch = bool(m.get("cr"))
        w = m.get("w")
        if w in p.weapons:
            p.weapon = w
        p.history.append((now, p.pos, p.crouch))

    # ------------------------------------------------------------------ combat
    def _weapon_check(self, p, wid, now, count=1):
        if wid not in p.weapons:
            self._violation(p, "weapon not in loadout")
            return None
        s = p.weapons[wid]
        min_dt = (1.0 / s["rps"]) * 0.7 if s["burst"] <= 1 else 0.05
        last = p.last_fire.get(wid, 0.0)
        if now - last < min_dt:
            self._violation(p, "fire rate")
            return None
        if not s["melee"]:
            if now < p.reload_at.get(wid, 0.0):
                self._violation(p, "fired while reloading")
                return None
            n = p.shots_since_reload.get(wid, 0) + count
            if n > s["mag"] + 1:
                self._violation(p, "magazine")
                return None
            p.shots_since_reload[wid] = n
        p.last_fire[wid] = now
        return s

    def _on_reload(self, p, m):
        wid = m.get("w")
        if wid in p.weapons and not p.weapons[wid]["melee"]:
            p.shots_since_reload[wid] = 0
            p.reload_at[wid] = time.monotonic() + p.weapons[wid]["reload"] * 0.75

    def _origin_ok(self, p, o):
        e = p.eye()
        return math.dist(o, e) < 3.0

    def _on_fire(self, p, m):
        room = p.room
        if room is None or room.state != "live" or not p.alive:
            return
        now = time.monotonic()
        wid = m.get("w")
        s = self._weapon_check(p, wid, now)
        if s is None or s["melee"]:
            return
        o = P.vec3(m.get("o"), p.eye())
        if not self._origin_ok(p, o):
            self._violation(p, "origin")
            return
        d = normalize(P.vec3(m.get("d"), (0, 1, 0)))
        dirs = m.get("ds") or [d]
        if not isinstance(dirs, list) or len(dirs) > s["pellets"]:
            self._violation(p, "pellets")
            return
        cone = math.cos(math.radians(min(45.0, s["spread"] * 14 + 3.0)))
        clean = []
        for dd in dirs:
            v = normalize(P.vec3(dd, d))
            if v[0] * d[0] + v[1] * d[1] + v[2] * d[2] < cone:
                self._violation(p, "pellet cone")
                return
            clean.append(v)
        if s["speed"] > 0:
            seq = m.get("seq")
            if isinstance(seq, int):
                p.pending[seq] = (now, wid, o, clean[0])
                if len(p.pending) > 64:
                    p.pending.pop(next(iter(p.pending)))
            room.broadcast({"t": "shot", "id": p.id, "w": wid, "o": list(o),
                            "e": [list(v) for v in clean], "proj": 1}, exclude=p)
            return
        ends = []
        rewind = now - min(MAX_REWIND, p.rtt * 0.5 + 0.1)
        for v in clean:
            ends.append(self._trace(room, p, o, v, s, rewind))
        room.broadcast({"t": "shot", "id": p.id, "w": wid, "o": list(o), "e": ends},
                       exclude=p)

    def _trace(self, room, shooter, o, d, s, t):
        t_wall, _ = first_static_hit(o, d, room.layout.STATIC_BOXES, s["maxr"])
        limit = t_wall if t_wall is not None else s["maxr"]
        hits = []
        for q in room.players.values():
            if q is shooter or not q.alive:
                continue
            pos, cr = q.pos_at(t)
            r = hit_combatant(o, d, pos, cr, limit)
            if r is not None:
                hits.append((r[0], q, r[1]))
        hits.sort(key=lambda h: h[0])
        if not s["pierce"]:
            hits = hits[:1]
        end_t = limit
        for (dist, q, head) in hits:
            dmg = damage_at(s, dist) * (s["hs"] if head else 1.0)
            self._damage(room, shooter, q, dmg, s["name"], head)
            if not s["pierce"]:
                end_t = dist
        return [o[0] + d[0] * end_t, o[1] + d[1] * end_t, o[2] + d[2] * end_t]

    def _on_phit(self, p, m):
        room = p.room
        if room is None or room.state != "live":
            return
        seq = m.get("seq")
        rec = p.pending.pop(seq, None) if isinstance(seq, int) else None
        if rec is None:
            return
        t0, wid, o, d = rec
        s = p.weapons[wid]
        now = time.monotonic()
        pos = P.vec3(m.get("pos"), o)
        # impact must lie on the fired ray, within plausible travel time
        rel = (pos[0] - o[0], pos[1] - o[1], pos[2] - o[2])
        along = rel[0] * d[0] + rel[1] * d[1] + rel[2] * d[2]
        perp = math.sqrt(max(0.0, rel[0] ** 2 + rel[1] ** 2 + rel[2] ** 2 - along * along))
        travel = max(0.0, along) / max(1.0, s["speed"])
        if perp > 1.5 or along < -0.5 or (now - t0) + 0.25 + p.rtt < travel * 0.6:
            self._violation(p, "projectile")
            return
        tgt_id = m.get("tgt")
        direct = None
        if tgt_id is not None:
            q = room.players.get(tgt_id)
            if q is not None and q.alive and q is not p:
                qpos, cr = q.pos_at(now - min(MAX_REWIND, p.rtt * 0.5 + 0.1))
                chest = (qpos[0], qpos[1], qpos[2] + 1.0)
                if math.dist(chest, pos) < 2.6:
                    self._damage(room, p, q, s["dmg"], s["name"], False)
                    direct = q
        if s["splash"] > 0:
            for q in list(room.players.values()):
                if not q.alive or q is direct:
                    continue
                chest = (q.pos[0], q.pos[1], q.pos[2] + 1.0)
                dist = math.dist(chest, pos)
                if dist > s["splash"] + 0.4:
                    continue
                k = max(0.0, 1.0 - max(0.0, dist - 0.5) / s["splash"] * 0.7)
                dmg = s["splash_dmg"] * k * (0.4 if q is p else 1.0)
                self._damage(room, p, q, dmg, s["name"], False)

    def _on_melee(self, p, m):
        room = p.room
        if room is None or room.state != "live" or not p.alive:
            return
        now = time.monotonic()
        wid = m.get("w")
        s = self._weapon_check(p, wid, now)
        if s is None or not s["melee"]:
            return
        o = p.eye()
        d = normalize(P.vec3(m.get("d"), (0, 1, 0)))
        half = math.radians(s["arc"] * 0.5)
        t = now - min(MAX_REWIND, p.rtt * 0.5 + 0.1)
        for q in list(room.players.values()):
            if q is p or not q.alive:
                continue
            qpos, cr = q.pos_at(t)
            c = (qpos[0], qpos[1], qpos[2] + (0.8 if cr else 1.2))
            v = (c[0] - o[0], c[1] - o[1], c[2] - o[2])
            dist = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
            if dist > s["range"] + 0.8 or dist < 1e-3:
                continue
            cosang = (v[0] * d[0] + v[1] * d[1] + v[2] * d[2]) / dist
            if math.acos(max(-1.0, min(1.0, cosang))) > half and dist > 0.9:
                continue
            tw, _ = first_static_hit(o, (v[0] / dist, v[1] / dist, v[2] / dist),
                                     room.layout.STATIC_BOXES, dist)
            if tw is not None:
                continue
            self._damage(room, p, q, s["dmg"], s["name"], False)

    def _damage(self, room, attacker, victim, dmg, wname, head):
        if not victim.alive or dmg <= 0:
            return
        now = time.monotonic()
        if now < victim.respawn_at + 1.5:      # spawn protection
            return
        victim.hp -= dmg
        victim.last_damage = now
        msg = {"t": "hit", "a": attacker.id, "v": victim.id, "dmg": round(dmg, 1), "hs": head,
               "hp": max(0.0, round(victim.hp, 1))}
        attacker.send(msg)
        if victim is not attacker:
            victim.send(msg)
        if victim.hp <= 0:
            victim.alive = False
            victim.deaths += 1
            victim.respawn_at = now + RESPAWN_DELAY
            if attacker is not victim:
                attacker.kills += 1
                attacker.score += 1
            room.broadcast({"t": "kill", "k": attacker.id, "v": victim.id, "w": wname, "hs": head})

    def _violation(self, p, what):
        now = time.monotonic()
        p.violations.append(now)
        recent = [t for t in p.violations if now - t < 10.0]
        log.info("violation by %s (%d): %s", p.name, p.id, what)
        if len(recent) >= VIOLATION_KICK:
            p.send({"t": "kick", "msg": "anti-cheat: " + what})
            p.closed = True
            try:
                p.writer.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ match flow
    def _spawn_point(self, room, p):
        best = None
        best_d = -1.0
        pts = list(room.layout.SPAWNS)
        self.rng.shuffle(pts)
        for (x, y, yaw) in pts:
            d = min([math.hypot(q.pos[0] - x, q.pos[1] - y) for q in room.players.values()
                     if q is not p and q.alive] or [99.0])
            if d > best_d:
                best_d = d
                best = (x, y, yaw)
        return best

    def _respawn(self, room, p, announce=True):
        x, y, yaw = self._spawn_point(room, p)
        p.pos = (x, y, 0.0)
        p.hp = 100.0
        p.alive = True
        p.respawn_at = time.monotonic()
        p.budget = SPEED_BUDGET_MAX
        p.history.clear()
        p.shots_since_reload.clear()
        p.reload_at.clear()
        room.broadcast({"t": "respawn", "id": p.id, "p": [x, y, 0.0, yaw]})

    async def _tick_loop(self):
        interval = 1.0 / P.TICK_RATE
        while True:
            await asyncio.sleep(interval)
            now = time.monotonic()
            for room in list(self.rooms.values()):
                if room.state != "live":
                    continue
                left = room.time_limit - (now - room.start_time)
                for p in room.players.values():
                    if not p.alive and now >= p.respawn_at and p.respawn_at > 0:
                        self._respawn(room, p)
                    # health regeneration (mirrors the client rule)
                    if p.alive and p.hp < 100 and now - p.last_damage > 6.0:
                        p.hp = min(100.0, p.hp + 9.0 * interval)
                pl = [[p.id, round(p.pos[0], 3), round(p.pos[1], 3), round(p.pos[2], 3),
                       round(p.yaw, 1), round(p.pitch, 1), int(p.crouch), int(p.alive),
                       round(p.hp, 1), p.weapon, p.score, p.kills, p.deaths,
                       int(p.rtt * 1000)] for p in room.players.values()]
                room.broadcast({"t": "snap", "ts": now, "left": max(0.0, left), "pl": pl})
                top = max((p.score for p in room.players.values()), default=0)
                if left <= 0 or top >= room.score_limit:
                    self._end(room)
                for p in room.players.values():
                    try:
                        await p.writer.drain()
                    except Exception:
                        p.closed = True

    def _end(self, room):
        room.state = "lobby"
        ranking = sorted(room.players.values(), key=lambda p: (-p.score, p.deaths))
        room.broadcast({"t": "end", "winner": ranking[0].id if ranking else None,
                        "scores": [[p.id, p.name, p.kills, p.deaths, p.score] for p in ranking]})
        for p in room.players.values():
            p.alive = False
            p.respawn_at = 0.0
        room.broadcast(room.lobby_msg())


def run_in_thread(host="0.0.0.0", port=P.DEFAULT_PORT):
    """Start a GameServer on a daemon thread (LAN hosting).  Returns (server, thread)."""
    import threading
    srv = GameServer(max_rooms=4)
    ready = threading.Event()
    errors = []

    def runner():
        async def main():
            try:
                task = asyncio.ensure_future(srv.serve(host, port))
                await asyncio.sleep(0.2)
                ready.set()
                await task
            except asyncio.CancelledError:
                pass                   # normal shutdown
            except Exception as e:     # port in use etc.
                errors.append(e)
                ready.set()
        try:
            asyncio.run(main())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            errors.append(e)
            ready.set()

    th = threading.Thread(target=runner, name="neongrid-lan-server", daemon=True)
    th.start()
    ready.wait(3.0)
    if errors:
        raise errors[0]
    return srv, th
