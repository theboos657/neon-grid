"""Training mode: a shooting range full of targets.

Targets are hazard-like objects (shootable, never shoot back).  They fall when
destroyed and pop back up two seconds later.  Press the interact key (F) to
swap your primary for the next gun in the catalogue, so every weapon can be
tried before buying it.  Nothing here gives coins or XP.
"""

import math
import random

from panda3d.core import Vec3, Vec4

from neon_shared import arena_layout as L
from neon_shared import weapons as W
from neon_shared.hitmath import ray_aabb, ray_sphere

from . import i18n
from .gfx import geom
from .modes import Mode

MAT_BOARD = Vec4(20, 0.3, 0.0, 0.0)
MAT_GLOW = Vec4(1, 0, 0, 1.6)


class Target:
    is_hazard = True
    is_target = True
    name = "TARGET"
    team = -99
    radius = 0.6

    def __init__(self, mode, kind, x, y, z, extra):
        m = mode.m
        self.mode = mode
        self.match = m
        self.kind = kind
        self.home = Vec3(x, y, z)
        self.pos = Vec3(x, y, z)
        self.extra = extra
        self.alive = True
        self.health = self.max_health = 100.0
        self.emp_until = 0.0
        self.down_t = 0.0          # time left lying down after being destroyed
        self.fall = 0.0
        self.hidden = kind == "popup"
        self.state_t = random.uniform(0.5, 2.5)
        self.up_since = 0.0
        self.phase = random.uniform(0, math.tau)
        self.dir = 1.0
        self.np = m.world_root.attachNewNode("target")
        self.pivot = self.np.attachNewNode("pivot")
        mb = geom.MeshBuilder("board")
        white = (0.9, 0.9, 0.88, 1)
        orange = (1.0, 0.45, 0.1, 1)
        mb.cbox((0, 0, 0.2), (0.08, 0.08, 0.4), (0.3, 0.3, 0.32, 1))          # stand
        mb.cbox((0, 0, 1.0), (0.56, 0.1, 1.2), orange)                        # torso
        mb.cbox((0, 0, 1.0), (0.4, 0.11, 0.9), white)
        mb.sphere((0, 0, 1.86), 0.21, orange, 6, 10)                          # head
        b = mb.node()
        b.reparentTo(self.pivot)
        b.setTexture(m.textures.white)
        b.setShaderInput("u_mat", MAT_BOARD)
        mb = geom.MeshBuilder("rings")
        for i, r in enumerate((0.18, 0.11, 0.05)):
            mb.ring(r - 0.03, r, (1.0, 0.1, 0.1, 1) if i != 1 else (1, 1, 1, 1), 20, z=0)
        rings = mb.node()
        rings.reparentTo(self.pivot)
        rings.setP(90)
        rings.setPos(0, -0.062, 1.15)
        rings.setTwoSided(True)
        rings.setTexture(m.textures.white)
        rings.setShaderInput("u_mat", MAT_GLOW)
        rings.setShaderInput("u_hue", 0.0)
        self.np.setPos(self.pos)
        if self.hidden:
            self.pivot.setP(-90)

    # ---------------------------------------------------------------- shooting
    def center(self):
        return self.pos + Vec3(0, 0, 1.2)

    def ray_hit(self, o, d, max_t):
        if not self.alive or self.hidden or self.fall > 0:
            return None
        h = self.pos + Vec3(0, 0, 1.86)
        t = ray_sphere(o, d, h, 0.23)
        best = None
        if t is not None and t <= max_t:
            best = (t, True)
        p = self.pos
        r = ray_aabb(o, d, (p.x - 0.3, p.y - 0.08, p.z + 0.38, p.x + 0.3, p.y + 0.08, p.z + 1.62,
                            "t"), max_t)
        if r is not None and (best is None or r[0] < best[0]):
            best = (r[0], False)
        return best

    def apply_hit(self, dmg, source, headshot=False, pos=None, weapon=""):
        if not self.alive:
            return False
        self.mode.on_target_hit(self, dmg, headshot, pos)
        self.health -= dmg
        self.match.fx.sparks_at(pos or self.center(), (0, -1, 0), 10, (1.0, 0.6, 0.2), 5)
        if self.health <= 0:
            self.alive = False
            self.fall = 0.35
            self.mode.on_target_down(self)
            self.match.audio.play3d("explosion_small", self.center(), 0.4)
            return True
        return False

    def emp(self, duration):
        pass

    @property
    def emped(self):
        return False

    # ---------------------------------------------------------------- motion
    def update(self, dt, t):
        if self.fall > 0:
            self.fall -= dt
            self.pivot.setP(-90 * (1 - max(0.0, self.fall) / 0.35))
            if self.fall <= 0:
                self.down_t = 2.0
            return
        if not self.alive:
            self.down_t -= dt
            if self.down_t <= 0:
                self.alive = True
                self.health = self.max_health
                self.pivot.setP(0)
                if self.kind == "popup":
                    self.hidden = True
                    self.pivot.setP(-90)
                    self.state_t = random.uniform(0.8, 2.5)
            return
        if self.kind == "slide":
            self.pos.x = self.home.x + math.sin(t * 0.9 + self.phase) * self.extra * 0.5
        elif self.kind == "strafe":
            self.state_t -= dt
            if self.state_t <= 0:
                self.state_t = random.uniform(0.4, 1.4)
                self.dir = random.choice((-1.0, 1.0))
            self.pos.x += self.dir * 6.5 * dt
            lim = self.extra * 0.5
            if abs(self.pos.x - self.home.x) > lim:
                self.pos.x = self.home.x + math.copysign(lim, self.pos.x - self.home.x)
                self.dir *= -1
        elif self.kind == "popup":
            self.state_t -= dt
            if self.hidden and self.state_t <= 0:
                self.hidden = False
                self.pivot.setP(0)
                self.up_since = t
                self.state_t = 2.6
            elif not self.hidden and self.state_t <= 0:
                self.hidden = True
                self.pivot.setP(-90)
                self.state_t = random.uniform(0.8, 2.5)
        self.np.setPos(self.pos)

    def cleanup(self):
        self.np.removeNode()


class Training(Mode):
    key = "training"

    def __init__(self, match, cfg):
        super().__init__(match, cfg)
        self.time_limit = 0.0
        self.score_limit = 0
        self.targets = []
        self.hits = 0
        self.heads = 0
        self.downs = 0
        self.reactions = []
        self.gun_i = -1

    def hazard_config(self):
        return {"turrets": False, "drones": 0, "traps": False, "chaos": False}

    def setup(self):
        p = self.add_player(0)
        for w in p.weapons:
            w.max_reserve = 999
            w.reserve = 999
        for (kind, x, y, z, extra) in L.TARGETS:
            self.targets.append(Target(self, kind, x, y, z, extra))

    def extra_shootables(self):
        return [t for t in self.targets if t.alive and not t.hidden]

    def on_target_hit(self, tgt, dmg, headshot, pos):
        self.hits += 1
        if headshot:
            self.heads += 1

    def on_target_down(self, tgt):
        self.downs += 1
        m = self.m
        if tgt.kind == "popup":
            self.reactions.append(m.time - tgt.up_since)
        if m.player is not None and m.hud:
            dist = (tgt.center() - m.player.eye_pos()).length()
            m.hud.notice(i18n.t("tr_down", m=int(dist)), (1.0, 0.75, 0.3, 1), 1.0)

    def update(self, dt):
        self.elapsed += dt
        t = self.m.time
        for tg in self.targets:
            tg.update(dt, t)
        m = self.m
        p = m.player
        if p is not None and p.alive and m.app.input.pressed("interact") and not m.frozen:
            self._next_gun(p)
        for w in (p.weapons if p is not None else []):
            if w.reserve < 300:
                w.reserve = 999

    def _next_gun(self, p):
        """Try every ranged gun for free (training only)."""
        ids = W.RANGED_IDS
        self.gun_i = (self.gun_i + 1) % len(ids)
        wid = ids[self.gun_i]
        from .combat.weapon_state import WeaponState
        ws = WeaponState(wid, 0)
        ws.max_reserve = ws.reserve = 999
        p.weapons[0] = ws
        p.slot = 0
        ws.draw()
        self.m.on_weapon_switch(p)
        if self.m.hud:
            self.m.hud.notice(i18n.t("tr_gun", w=ws.name.upper()), (0.3, 1.0, 1.0, 1), 1.6)

    def check_end(self):
        pass

    def can_respawn(self, c):
        return True

    def time_left(self):
        return None

    def hud_info(self):
        shots = max(1, self.m.stats["shots"])
        acc = min(100, int(round(100.0 * self.hits / shots)))
        rt = ("  |  " + i18n.raw("tr_react", s="%.2f" % (sum(self.reactions[-10:]) /
                                                      len(self.reactions[-10:])))
              if self.reactions else "")
        small = i18n.raw("tr_stats", h=self.hits, a=acc, hs=self.heads, d=self.downs) + rt
        return i18n.t("mode_training"), i18n.visual(small + "   |   " + i18n.raw("tr_hint"))

    def finish(self):
        pass

    def cleanup(self):
        for tg in self.targets:
            tg.cleanup()
        self.targets = []
