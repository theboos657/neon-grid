"""Bot AI.

Bots drive a Combatant through the same InputState as the player, so they
move, shoot, reload and use abilities under identical rules.  Difficulty
tunes perception and aim, not stats:

    reaction  - delay before firing at a newly seen target
    aim_error - degrees of aim wobble
    turn      - max turn rate (deg/s)
    track     - how quickly aim follows a moving target (lag)
"""

import math
import random

from panda3d.core import Vec3

from neon_shared import weapons as W
from neon_shared.bots import BOT_NAMES, LOADOUT_POOL  # noqa: F401  (shared with the server)

DIFFICULTY = {
    "easy":   {"reaction": 0.65, "aim_error": 5.5, "turn": 200.0, "track": 3.0, "ability": 0.15,
               "strafe": 0.4, "view": 38.0, "burst": 0.7, "lead": 0.0},
    "normal": {"reaction": 0.36, "aim_error": 2.8, "turn": 340.0, "track": 6.0, "ability": 0.4,
               "strafe": 0.75, "view": 48.0, "burst": 0.85, "lead": 0.5},
    "hard":   {"reaction": 0.2, "aim_error": 1.3, "turn": 520.0, "track": 11.0, "ability": 0.8,
               "strafe": 1.0, "view": 60.0, "burst": 1.0, "lead": 1.0},
    "nightmare": {"reaction": 0.12, "aim_error": 0.7, "turn": 720.0, "track": 16.0,
                  "ability": 1.0, "strafe": 1.0, "view": 75.0, "burst": 1.0, "lead": 1.0},
}

DIFF_ORDER = ["easy", "normal", "hard", "nightmare"]
# coin multiplier per chosen difficulty (applied to all coins earned in the match)
COIN_MULT = {"easy": 0.5, "normal": 1.0, "hard": 2.0, "nightmare": 2.5}


def random_loadout(rng, difficulty="normal"):
    from neon_shared.abilities import IDS
    prim, sec = rng.choice(LOADOUT_POOL)
    return {"primary": prim, "secondary": sec, "melee": rng.choice(W.MELEE_IDS),
            "abilities": rng.sample(IDS, 2)}


def _ang_diff(a, b):
    return (b - a + 180.0) % 360.0 - 180.0


class BotBrain:
    def __init__(self, match, c, difficulty="normal"):
        self.m = match
        self.c = c
        self.set_difficulty(difficulty)
        self.rng = random.Random(c.cid * 7919 + 13)
        self.target = None
        self.target_seen_at = -99.0
        self.last_seen_pos = None
        self.last_seen_time = -99.0
        self.perceive_t = 0.0
        self.path = []
        self.path_goal = None
        self.repath_t = 0.0
        self.goal_kind = None
        self.strafe_dir = 1
        self.strafe_t = 0.0
        self.jump_t = self.rng.uniform(2, 5)
        self.stuck_t = 0.0
        self.last_pos = Vec3(c.body.pos)
        self.aim_offset = Vec3(0, 0, 0)
        self.aim_offset_t = 0.0
        self.crouch_t = 0.0
        self.ability_t = self.rng.uniform(3, 8)
        self.hold_fire_t = 0.0
        self.flashed = False

    def set_difficulty(self, d):
        self.difficulty = d if d in DIFFICULTY else "normal"
        self.p = DIFFICULTY[self.difficulty]

    # ------------------------------------------------------------------ perception
    def _visible(self, e):
        c = self.c
        m = self.m
        if not e.alive:
            return False
        d = e.chest_pos() - c.eye_pos()
        dist = d.length()
        if dist > self.p["view"]:
            return False
        if getattr(e, "cloaked", False) and dist > 5.0:
            return False
        # field of view 150 deg, but always notice close enemies / attackers
        fwd = c.aim_dir()
        if dist > 6 and d.normalized().dot(fwd) < -0.25 and e is not c.last_attacker:
            return False
        revealed = m.time < getattr(e, "reveal_until", 0) and \
            getattr(e, "revealed_to_team", None) == c.team
        if revealed:
            return True
        return m.coll.line_of_sight(c.eye_pos(), e.chest_pos()) or \
            m.coll.line_of_sight(c.eye_pos(), e.eye_pos())

    def _perceive(self):
        c = self.c
        best = None
        best_score = 1e9
        for e in self.m.targets_for(c):
            if not self._visible(e):
                continue
            dist = (e.body.pos - c.body.pos).length()
            score = dist
            if e is self.target:
                score -= 8           # stickiness
            if e is c.last_attacker and self.m.time - c.last_damage_time < 3:
                score -= 12
            if getattr(e, "is_decoy", False):
                score -= 4           # decoys are attractive
            if score < best_score:
                best_score = score
                best = e
        if best is not None:
            if best is not self.target:
                self.target_seen_at = self.m.time
            self.target = best
            self.last_seen_pos = Vec3(best.body.pos)
            self.last_seen_time = self.m.time
        else:
            if self.target is not None and not self.target.alive:
                self.last_seen_pos = None
            self.target = None
        # react to damage from something unseen: turn toward it
        if best is None and self.m.time - self.c.last_damage_time < 0.6 and self.c.last_attacker:
            la = self.c.last_attacker
            if la.alive:
                self.last_seen_pos = Vec3(la.body.pos)
                self.last_seen_time = self.m.time

    # ------------------------------------------------------------------ navigation
    def _choose_goal(self):
        c = self.c
        m = self.m
        rng = self.rng
        if c.needs_loot():
            boxes = [b for b in m.interact.loot if b.ready]
            if boxes:
                b = min(boxes, key=lambda b: (b.pos - c.body.pos).lengthSquared())
                return (b.pos.x, b.pos.y, b.pos.z), "loot"
        if c.energy < 40 and rng.random() < 0.5:
            p = min(m.interact.ports, key=lambda p: (p.pos - c.body.pos).lengthSquared())
            return (p.pos.x, p.pos.y, 0.0), "port"
        if self.last_seen_pos is not None and m.time - self.last_seen_time < 8:
            p = self.last_seen_pos
            return (p.x, p.y, p.z), "hunt"
        # roam toward the nearest enemy sometimes (keeps matches lively)
        if rng.random() < 0.55:
            ens = [e for e in m.targets_for(c) if e.alive]
            if ens:
                e = min(ens, key=lambda e: (e.body.pos - c.body.pos).lengthSquared())
                p = e.body.pos
                return (p.x + rng.uniform(-6, 6), p.y + rng.uniform(-6, 6), p.z), "hunt"
        return m.nav.random_node_pos(rng), "roam"

    def _repath(self, goal, kind):
        c = self.c
        self.path = self.m.nav.path((c.body.pos.x, c.body.pos.y, c.body.pos.z), goal)
        if self.path:
            self.path.pop(0)
        self.path_goal = goal
        self.goal_kind = kind
        self.repath_t = 2.5 if kind != "hunt" else 1.4

    def _follow_path(self):
        """Return desired world-space move direction (Vec3, z=0) or None."""
        c = self.c
        p = c.body.pos
        while self.path:
            wx, wy, wz = self.path[0]
            d = Vec3(wx - p.x, wy - p.y, 0)
            if d.length() < 0.7 and abs(wz - p.z) < 1.2:
                self.path.pop(0)
                continue
            # waypoint far above (jump pad target / catwalk): walk to the pad and wait
            d.normalize()
            return d, wz
        return None, None

    # ------------------------------------------------------------------ main update
    def update(self, dt):
        c = self.c
        m = self.m
        inp = c.input
        if not c.alive:
            self.path = []
            self.target = None
            return
        p = self.p
        flashed = m.time < c.flash_until
        self.perceive_t -= dt
        if self.perceive_t <= 0:
            self.perceive_t = 0.12 if self.difficulty in ("hard", "nightmare") else 0.2
            if not flashed:
                self._perceive()
            else:
                self.target = None
        tgt = self.target
        self.repath_t -= dt

        # --- movement goal
        move = None
        if tgt is not None:
            to = tgt.body.pos - c.body.pos
            dist = to.length()
            ws = c.weapon()
            pref = self._preferred_range(ws)
            flat = Vec3(to.x, to.y, 0)
            if flat.length() > 0.01:
                flat.normalize()
            side = Vec3(-flat.y, flat.x, 0) * self.strafe_dir
            self.strafe_t -= dt
            if self.strafe_t <= 0:
                self.strafe_t = self.rng.uniform(0.5, 1.6)
                if self.rng.random() < p["strafe"]:
                    self.strafe_dir *= -1
            if dist > pref * 1.3:
                if self.repath_t <= 0 or not self.path:
                    self._repath((tgt.body.pos.x, tgt.body.pos.y, tgt.body.pos.z), "hunt")
                pd, _ = self._follow_path()
                move = (pd or flat) + side * 0.35 * p["strafe"]
            elif dist < pref * 0.6:
                move = -flat + side * 0.6
            else:
                move = side * p["strafe"] + flat * 0.15
        else:
            if self.repath_t <= 0 or not self.path:
                goal, kind = self._choose_goal()
                self._repath(goal, kind)
            move, _ = self._follow_path()

        # --- stuck detection -> jump / repath
        moved = (c.body.pos - self.last_pos).length()
        self.last_pos = Vec3(c.body.pos)
        if move is not None and moved < 0.5 * dt:
            self.stuck_t += dt
        else:
            self.stuck_t = max(0.0, self.stuck_t - dt)
        want_jump = False
        if self.stuck_t > 0.4:
            want_jump = True
        if self.stuck_t > 1.2:
            self.stuck_t = 0
            self.path = []
            self.repath_t = 0
            self.strafe_dir *= -1

        # --- convert world move to local input
        yaw_r = math.radians(c.yaw)
        fwd = Vec3(-math.sin(yaw_r), math.cos(yaw_r), 0)
        right = Vec3(math.cos(yaw_r), math.sin(yaw_r), 0)
        if move is not None and move.lengthSquared() > 0.001:
            mv = Vec3(move)
            mv.z = 0
            if mv.length() > 1:
                mv.normalize()
            inp.move_x = mv.dot(right)
            inp.move_y = mv.dot(fwd)
        else:
            inp.move_x = inp.move_y = 0.0
        inp.sprint = tgt is None and move is not None
        # occasional hops & crouch-peeks in fights
        self.jump_t -= dt
        if tgt is not None and self.jump_t <= 0:
            self.jump_t = self.rng.uniform(1.5, 4.0) / max(0.3, p["strafe"])
            want_jump = want_jump or self.rng.random() < 0.5 * p["strafe"]
        inp.jump = want_jump
        self.crouch_t -= dt
        if tgt is not None and self.difficulty != "easy" and self.crouch_t <= 0:
            self.crouch_t = self.rng.uniform(1.0, 3.0)
            inp.crouch = self.rng.random() < 0.25
        elif tgt is None:
            inp.crouch = False
            # slide occasionally while sprinting
            if self.rng.random() < 0.004 and c.sprinting:
                inp.crouch = True

        # --- aim
        if tgt is not None:
            self._aim(dt, tgt)
        elif move is not None and move.lengthSquared() > 0.01:
            want = math.degrees(math.atan2(-move.x, move.y))
            if self.last_seen_pos is not None and m.time - self.last_seen_time < 3:
                d = self.last_seen_pos - c.body.pos
                want = math.degrees(math.atan2(-d.x, d.y))
            self._turn_to(want, 0.0, dt, 0.6)

        # --- weapon choice & firing
        self._weapon_logic(tgt)
        # --- abilities
        self.ability_t -= dt
        if self.ability_t <= 0:
            self.ability_t = self.rng.uniform(2.0, 5.0)
            if self.rng.random() < p["ability"]:
                self._use_ability(tgt)

    def _preferred_range(self, ws):
        cls = ws.stats["cls"]
        return {"melee": 1.5, "shotgun": 6.0, "smg": 10.0, "pistol": 14.0, "rifle": 18.0,
                "plasma": 16.0, "rail": 22.0, "sniper": 28.0}.get(cls, 14.0)

    def _turn_to(self, yaw, pitch, dt, scale=1.0):
        c = self.c
        turn = self.p["turn"] * scale * dt
        dy = _ang_diff(c.yaw, yaw)
        c.yaw += max(-turn, min(turn, dy))
        dp = pitch - c.pitch
        c.pitch += max(-turn, min(turn, dp))
        c.pitch = max(-80, min(80, c.pitch))
        return abs(dy), abs(dp)

    def _aim(self, dt, tgt):
        c = self.c
        p = self.p
        # periodically re-roll aim wobble
        self.aim_offset_t -= dt
        if self.aim_offset_t <= 0:
            self.aim_offset_t = self.rng.uniform(0.25, 0.6)
            e = p["aim_error"] * (3.0 if self.m.time < c.flash_until else 1.0)
            self.aim_offset = Vec3(self.rng.gauss(0, e), self.rng.gauss(0, e) * 0.6, 0)
        ws = c.weapon()
        aim = tgt.chest_pos()
        if self.difficulty in ("hard", "nightmare") and ws.stats["hs"] >= 1.6 and \
                self.rng.random() < (0.5 if self.difficulty == "hard" else 0.75):
            aim = tgt.eye_pos()
        if ws.stats["speed"] > 0 and p["lead"] > 0:
            dist = (aim - c.eye_pos()).length()
            aim = aim + tgt.body.vel * (dist / ws.stats["speed"]) * p["lead"]
        d = aim - c.eye_pos()
        yaw = math.degrees(math.atan2(-d.x, d.y)) + self.aim_offset.x
        pitch = math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))) + self.aim_offset.y
        # tracking lag: move part of the way each frame
        k = min(1.0, p["track"] * dt)
        want_yaw = c.yaw + _ang_diff(c.yaw, yaw) * k * 3
        want_pitch = c.pitch + (pitch - c.pitch) * k * 3
        self._turn_to(want_yaw, want_pitch, dt)
        self.aim_err_now = abs(_ang_diff(c.yaw, yaw)) + abs(pitch - c.pitch)

    def _weapon_logic(self, tgt):
        c = self.c
        inp = c.input
        m = self.m
        ws = c.weapon()
        inp.fire = False
        inp.ads = False
        if tgt is None:
            # tactical reload / swap back to primary
            if not ws.melee and ws.mag < ws.stats["mag"] * 0.5 and ws.reserve > 0:
                inp.reload = True
            if c.slot == 2 and (c.weapons[0].mag > 0 or c.weapons[0].reserve > 0):
                inp.switch_to = 0
            return
        dist = (tgt.body.pos - c.body.pos).length()
        # melee when very close, guns otherwise
        if dist < 2.4 and c.slot != 2 and self.rng.random() < 0.35:
            inp.switch_to = 2
            return
        if dist > 4.0 and c.slot == 2:
            inp.switch_to = 0 if (c.weapons[0].mag > 0 or c.weapons[0].reserve > 0) else 1
            return
        if not ws.melee and ws.mag == 0 and ws.reserve == 0:
            return
        if m.time - self.target_seen_at < self.p["reaction"]:
            return
        err = getattr(self, "aim_err_now", 99)
        tol = 6.0 if ws.melee else max(2.5, 60.0 / max(dist, 1.0))
        if ws.stats["scoped"] and dist > 12:
            inp.ads = True
        if err < tol and dist < ws.stats["maxr"] * 0.9:
            if ws.stats["auto"]:
                inp.fire = self.rng.random() < self.p["burst"]
            else:
                inp.fire = True
                inp.fire_pressed = self.rng.random() < 0.5 * self.p["burst"] + 0.2
        c.aim_error = self.p["aim_error"] * 0.4

    def _use_ability(self, tgt):
        c = self.c
        # hotbar gadgets: lob a bomb at mid range, call a drone when fighting
        if tgt is not None:
            dist = (tgt.body.pos - c.body.pos).length()
            if c.bombs > 0 and 7.0 < dist < 18.0 and self.rng.random() < 0.35:
                c.input.bomb = True
                return
            if self.m.time >= c.drone_ready_at and self.rng.random() < 0.3:
                c.input.drone = True
                return
        for i, ab in enumerate(c.abilities):
            if not ab.ready or c.energy < ab.data["energy"]:
                continue
            aid = ab.id
            ok = False
            if aid in ("shield", "heal") and c.health < 55 and tgt is not None:
                ok = True
            elif aid == "heal" and c.health < 40:
                ok = True
            elif aid in ("dash", "speed", "jets") and tgt is not None and self.rng.random() < 0.5:
                ok = True
            elif aid in ("scan",) and tgt is None:
                ok = True
            elif aid in ("emp", "gravity") and tgt is not None and \
                    (tgt.body.pos - c.body.pos).length() < (8 if aid == "emp" else 20):
                ok = True
            elif aid in ("decoy", "cloak") and tgt is not None and c.health < 60:
                ok = True
            if ok:
                c.input.ability[i] = True
                return
