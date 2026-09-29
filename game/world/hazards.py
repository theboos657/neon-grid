"""Arena threats.

Three threat families, each with a clear telegraph before it hurts you:
  * Turrets    - red laser sight + rising beep for 1.2 s, then a 5-round burst.
  * Drones     - glow brighter + charge whine for 0.9 s, then a plasma bolt.
  * Grenade traps (explosive / flashbang / fire) - coloured floor ring and a
    floating icon pulse for 2 s before detonation.
Chaos Mode adds sweeping lasers (height telegraphed 1 s ahead), proximity
mines (blinking, beep before blast) and low-gravity lift zones.
"""

import math
import random

from panda3d.core import TextNode, Vec3, Vec4

from neon_shared import arena_layout as L
from neon_shared.hitmath import ray_sphere, spread_dir

from ..gfx import geom
from ..gfx.effects import fx_node

MAT_BODY = Vec4(50, 0.9, 0.4, 0)
MAT_NEON = Vec4(1, 0, 0, 2.6)
RED = (1.0, 0.12, 0.1)
TRAP_COLORS = {"explosive": (1.0, 0.15, 0.1), "flash": (1.0, 1.0, 1.0), "fire": (1.0, 0.5, 0.05)}
TRAP_ICONS = {"explosive": "!", "flash": "*", "fire": "^"}


class Hazard:
    is_hazard = True
    name = "HAZARD"
    team = -99

    def __init__(self, match):
        self.match = match
        self.alive = True
        self.health = 100.0
        self.max_health = 100.0
        self.emp_until = 0.0
        self.radius = 0.6
        self.pos = Vec3()

    @property
    def cid(self):
        return id(self)

    def center(self):
        return self.pos

    def ray_hit(self, o, d, max_t):
        if not self.alive:
            return None
        t = ray_sphere(o, d, self.center(), self.radius)
        if t is not None and t <= max_t:
            return (t, False)
        return None

    def apply_hit(self, dmg, source, headshot=False, pos=None, weapon=""):
        if not self.alive:
            return False
        self.health -= dmg
        self.match.fx.sparks_at(pos or self.center(), (0, 0, 1), 8, (1.0, 0.6, 0.3), 6)
        if self.health <= 0:
            self.destroy(source)
            return True
        return False

    def destroy(self, source):
        self.alive = False
        self.match.fx.explosion(self.center(), 2.5, "explosive")
        self.match.audio.play3d("explosion_small", self.center())
        self.match.on_hazard_destroyed(self, source)

    def emp(self, duration):
        self.emp_until = self.match.time + duration

    @property
    def emped(self):
        return self.match.time < self.emp_until


# ============================================================================
class Turret(Hazard):
    name = "TURRET"

    def __init__(self, match, x, y, z, heading):
        super().__init__(match)
        self.mount = Vec3(x, y, z)
        self.heading = heading
        self.health = self.max_health = 150.0
        self.radius = 0.7
        self.state = "scan"
        self.timer = 0.0
        self.target = None
        self.shots_left = 0
        self.respawn = 0.0
        self.yaw = heading
        self.pitch = -15.0
        self.beep_t = 0.0
        # visuals
        self.np = match.world_root.attachNewNode("turret")
        self.np.setPos(self.mount)
        self.np.setH(heading)
        mb = geom.MeshBuilder("turret_base")
        mb.cbox((0, -0.2, 0), (1.4, 0.4, 1.4), (0.25, 0.27, 0.3, 1))
        mb.cbox((0, 0.3, 0), (0.4, 0.8, 0.4), (0.25, 0.27, 0.3, 1))
        b = mb.node()
        b.reparentTo(self.np)
        b.setTexture(match.textures.metal)
        b.setShaderInput("u_mat", MAT_BODY)
        self.head = self.np.attachNewNode("head")
        self.head.setPos(0, 0.8, 0)
        self.head.setH(0)
        mb = geom.MeshBuilder("turret_head")
        mb.sphere((0, 0, 0), 0.55, (0.3, 0.32, 0.36, 1), 8, 12)
        mb.cbox((0.14, 0.7, 0), (0.1, 1.0, 0.1), (0.2, 0.2, 0.22, 1))
        mb.cbox((-0.14, 0.7, 0), (0.1, 1.0, 0.1), (0.2, 0.2, 0.22, 1))
        h = mb.node()
        h.reparentTo(self.head)
        h.setTexture(match.textures.metal)
        h.setShaderInput("u_mat", MAT_BODY)
        mb = geom.MeshBuilder("turret_eye")
        mb.cbox((0, 0.5, 0.12), (0.34, 0.1, 0.1), (1, 1, 1, 1))
        mb.cbox((0, 0, 0.0), (1.16, 0.06, 0.06), (1, 1, 1, 1))
        self.eye = mb.node()
        self.eye.reparentTo(self.head)
        self.eye.setTexture(match.textures.white)
        self.eye.setShaderInput("u_mat", MAT_NEON)
        self.eye.setShaderInput("u_hue", 0.0)
        # laser sight
        self.sight = geom.beam_mesh()
        self.sight.reparentTo(match.world_root)
        fx_node(self.sight, 0, hue_lock=True)
        self.sight.hide()

    def center(self):
        return self.head.getPos(self.match.world_root)

    def muzzle(self):
        return self.head.getPos(self.match.world_root) + self._aim_dir() * 1.2

    def _aim_dir(self):
        q = self.head.getQuat(self.match.world_root)
        return q.getForward()

    def _find_target(self):
        best = None
        bd = 34.0 * 34.0
        hp = self.head.getPos(self.match.world_root)
        facing = Vec3(-math.sin(math.radians(self.heading)), math.cos(math.radians(self.heading)), 0)
        for c in self.match.hazard_targets():
            aim = c.chest_pos()
            d = aim - hp
            dl = d.lengthSquared()
            if dl > bd:
                continue
            dn = Vec3(d)
            dn.normalize()
            if dn.dot(facing) < -0.2:
                continue
            if not self.match.coll.line_of_sight(hp + dn * 1.3, aim):
                continue
            best = c
            bd = dl
        return best

    def _aim_at(self, pos, dt, speed=160.0):
        hp = self.head.getPos(self.match.world_root)
        d = pos - hp
        want_yaw = math.degrees(math.atan2(-d.x, d.y))
        want_pitch = math.degrees(math.atan2(d.z, math.hypot(d.x, d.y)))
        dy = (want_yaw - self.yaw + 180) % 360 - 180
        step = speed * dt
        self.yaw += max(-step, min(step, dy))
        self.pitch += max(-step, min(step, want_pitch - self.pitch))
        self.head.setHpr(self.match.world_root, self.yaw, self.pitch, 0)
        return abs(dy) < 4

    def update(self, dt, t):
        m = self.match
        if not self.alive:
            self.respawn -= dt
            if self.respawn <= 0:
                self.alive = True
                self.health = self.max_health
                self.np.show()
                self.state = "scan"
            return
        if self.emped:
            self.sight.hide()
            self.eye.setColorScale(0.2, 0.3, 0.8, 1)
            self.head.setP(-35 + math.sin(t * 20) * 2)
            if random.random() < 0.1:
                m.fx.sparks_at(self.center(), (0, 0, 1), 3, (0.4, 0.6, 1.0), 4)
            return
        self.timer -= dt
        if self.state == "scan":
            self.eye.setColorScale(1.0, 0.35, 0.1, 1)
            self.yaw = self.heading + math.sin(t * 0.6 + self.heading) * 50
            self.pitch = -12
            self.head.setHpr(m.world_root, self.yaw, self.pitch, 0)
            if self.timer <= 0:
                self.timer = 0.3
                tgt = self._find_target()
                if tgt:
                    self.target = tgt
                    self.state = "lock"
                    self.timer = 1.2
                    m.audio.play3d("turret_lock", self.center())
        elif self.state == "lock":
            tgt = self.target
            if tgt is None or not tgt.alive or tgt.cloaked:
                self.state = "scan"
                self.sight.hide()
                return
            self._aim_at(tgt.chest_pos(), dt, 220)
            # telegraph: red laser sight, blink speeds up
            k = 1 - self.timer / 1.2
            self.sight.show()
            mz = self.muzzle()
            end = tgt.chest_pos()
            self.sight.setPos(mz)
            self.sight.lookAt(end)
            ln = (end - mz).length()
            self.sight.setScale(0.03 + 0.03 * k, ln, 0.03 + 0.03 * k)
            blink = 1.0 if math.sin(t * (10 + 30 * k)) > 0 else 0.35
            self.sight.setColorScale(2.5 * blink, 0.15 * blink, 0.1 * blink, 1)
            self.eye.setColorScale(3 * blink, 0.2, 0.1, 1)
            self.beep_t -= dt
            if self.beep_t <= 0:
                self.beep_t = 0.35 - 0.25 * k
                m.audio.play3d("beep", self.center(), 0.5)
            if tgt is m.player:
                m.warn_player("turret", self.center())
            if self.timer <= 0:
                self.state = "fire"
                self.shots_left = 5
                self.timer = 0.0
                self.sight.hide()
        elif self.state == "fire":
            tgt = self.target
            if tgt is not None and tgt.alive:
                self._aim_at(tgt.chest_pos(), dt, 90)
            if self.timer <= 0 and self.shots_left > 0:
                self.shots_left -= 1
                self.timer = 0.12
                mz = self.muzzle()
                d = spread_dir(tuple(self._aim_dir()), 2.2, random)
                m.hazard_shot(self, mz, Vec3(*d), 7, (1.0, 0.2, 0.1))
                m.audio.play3d("turret_fire", mz)
            if self.shots_left <= 0 and self.timer <= 0:
                self.state = "cool"
                self.timer = 2.5
        elif self.state == "cool":
            self.eye.setColorScale(0.6, 0.2, 0.1, 1)
            if self.timer <= 0:
                self.state = "scan"

    def destroy(self, source):
        super().destroy(source)
        self.np.hide()
        self.sight.hide()
        self.respawn = 35.0

    def cleanup(self):
        self.np.removeNode()
        self.sight.removeNode()


# ============================================================================
class Drone(Hazard):
    name = "DRONE"

    def __init__(self, match, pos, hp_scale=1.0):
        super().__init__(match)
        self.pos = Vec3(pos)
        self.vel = Vec3(0, 0, 0)
        self.health = self.max_health = 60.0 * hp_scale
        self.radius = 0.65
        self.state = "hunt"
        self.timer = random.uniform(1.0, 2.0)
        self.target = None
        self.retarget = 0.0
        self.orbit = random.choice((-1, 1))
        self.np = match.world_root.attachNewNode("drone")
        mb = geom.MeshBuilder("drone")
        mb.cylinder((0, 0, -0.12), 0.45, 0.24, (0.28, 0.3, 0.34, 1), 12)
        mb.sphere((0, 0, -0.1), 0.28, (0.2, 0.22, 0.25, 1), 6, 10)
        for a in range(4):
            ang = a * math.pi / 2 + math.pi / 4
            mb.cbox((math.cos(ang) * 0.6, math.sin(ang) * 0.6, 0.0), (0.5, 0.08, 0.05),
                    (0.2, 0.2, 0.22, 1))
        b = mb.node()
        b.reparentTo(self.np)
        b.setTexture(match.textures.metal)
        b.setShaderInput("u_mat", MAT_BODY)
        mb = geom.MeshBuilder("drone_glow")
        mb.ring(0.47, 0.55, (1, 1, 1, 1), 20, z=0.0)
        mb.sphere((0, 0.26, -0.12), 0.1, (1, 1, 1, 1), 4, 6)
        self.glow = mb.node()
        self.glow.reparentTo(self.np)
        self.glow.setTwoSided(True)
        self.glow.setTexture(match.textures.white)
        self.glow.setShaderInput("u_mat", MAT_NEON)
        self.glow.setShaderInput("u_hue", 0.0)
        self.np.setPos(self.pos)

    def update(self, dt, t):
        if not self.alive:
            return
        m = self.match
        if self.emped:
            self.vel.z -= 3 * dt
            self.vel *= 0.97
            self.pos += self.vel * dt
            self.pos.z = max(1.0, self.pos.z)
            self.np.setPos(self.pos)
            self.glow.setColorScale(0.2, 0.4, 1.0, 1)
            return
        self.retarget -= dt
        if self.retarget <= 0 or self.target is None or not self.target.alive:
            self.retarget = 0.8
            self.target = self._pick_target()
        tgt = self.target
        desired = Vec3(self.pos)
        if tgt is not None:
            tp = tgt.chest_pos()
            to = self.pos - tp
            to.z = 0
            dist = to.length()
            if dist < 0.1:
                to = Vec3(1, 0, 0)
                dist = 1.0
            to /= dist
            side = Vec3(-to.y, to.x, 0) * self.orbit
            want_d = 10.0
            desired = tp + to * want_d + side * 4.0
            desired.z = tp.z + 3.5 + math.sin(t * 0.7 + id(self) % 7) * 1.0
        else:
            desired = Vec3(math.sin(t * 0.2 + id(self)) * 18, math.cos(t * 0.17 + id(self)) * 18, 6)
        desired.z = min(max(desired.z, 2.0), L.CEILING_Z - 1.5)
        lim = L.HALF - 1.5
        desired.x = min(max(desired.x, -lim), lim)
        desired.y = min(max(desired.y, -lim), lim)
        steer = desired - self.pos
        if steer.length() > 1:
            steer.normalize()
            steer *= 7.5
        self.vel += (steer - self.vel) * min(1.0, dt * 2.0)
        new = self.pos + self.vel * dt
        if m.coll.point_blocked(new, 0.6):
            self.vel = Vec3(-self.vel.x * 0.5, -self.vel.y * 0.5, 3.0)
            self.orbit *= -1
        else:
            self.pos = new
        self.np.setPos(self.pos + Vec3(0, 0, math.sin(t * 3 + id(self) % 5) * 0.08))
        if tgt is not None:
            self.np.lookAt(tgt.chest_pos())
            self.np.setP(self.np.getP() * 0.3)
        # attack cycle
        self.timer -= dt
        if self.state == "hunt":
            self.glow.setColorScale(1.2, 0.3, 0.1, 1)
            if self.timer <= 0 and tgt is not None and \
                    m.coll.line_of_sight(self.pos, tgt.chest_pos()):
                self.state = "charge"
                self.timer = 0.9
                m.audio.play3d("drone_charge", self.pos)
        elif self.state == "charge":
            k = 1 - self.timer / 0.9
            f = 1 + 3 * k + (1.0 if math.sin(t * 40) > 0 else 0)
            self.glow.setColorScale(f, 0.3 * f, 0.1 * f, 1)
            if random.random() < 0.5:
                m.fx.glow.emit(1, self.pos, (0, 0, 0), 0.1, 0.3 + k * 0.4, 0.05,
                               (3, 0.6, 0.2, 1), (0, 0, 0, 0))
            if tgt is m.player:
                m.warn_player("drone", self.pos)
            if self.timer <= 0:
                if tgt is not None and tgt.alive:
                    aim = tgt.chest_pos() + tgt.body.vel * 0.25
                    d = aim - self.pos
                    d.normalize()
                    m.projectiles.spawn_hazard_bolt(self, self.pos + d * 0.7, d)
                    m.audio.play3d("drone_shot", self.pos)
                self.state = "hunt"
                self.timer = random.uniform(1.8, 2.6)

    def _pick_target(self):
        best = None
        bd = 45 * 45
        for c in self.match.hazard_targets():
            d = (c.chest_pos() - self.pos).lengthSquared()
            if d < bd:
                bd = d
                best = c
        return best

    def destroy(self, source):
        super().destroy(source)
        self.np.hide()
        self.match.interact.drop(self.pos - Vec3(0, 0, 1.0), 6, 40)

    def cleanup(self):
        self.np.removeNode()


# ============================================================================
class GrenadeTrap(Hazard):
    """Floor hatch that pops a grenade after a clear 2 s warning."""
    name = "TRAP"

    def __init__(self, match, x, y):
        super().__init__(match)
        self.pos = Vec3(x, y, 0)
        self.state = "idle"
        self.kind = "explosive"
        self.timer = 0.0
        self.beep_t = 0.0
        self.np = match.world_root.attachNewNode("trap")
        self.np.setPos(self.pos)
        mb = geom.MeshBuilder("hatch")
        mb.cylinder((0, 0, 0), 0.6, 0.05, (0.2, 0.2, 0.22, 1), 16)
        h = mb.node()
        h.reparentTo(self.np)
        h.setTexture(match.textures.stripes)
        h.setShaderInput("u_mat", Vec4(20, 0.5, 0, 0.25))
        h.setShaderInput("u_hue", 0.0)
        mb = geom.MeshBuilder("trap_ring")
        mb.ring(0.9, 1.0, (1, 1, 1, 1), 48, z=0.06)
        self.ring = mb.node()
        self.ring.reparentTo(self.np)
        fx_node(self.ring, 4, hue_lock=True)
        self.ring.hide()
        tn = TextNode("trap_icon")
        tn.setText("!")
        tn.setAlign(TextNode.ACenter)
        if match.font:
            tn.setFont(match.font)
        self.icon = self.np.attachNewNode(tn)
        self.icon.setPos(0, 0, 2.6)
        self.icon.setScale(1.4)
        self.icon.setBillboardPointEye()
        fx_node(self.icon, 3, hue_lock=True)
        self.icon.hide()
        self.icon_tn = tn
        self.grenade = None

    def ray_hit(self, o, d, max_t):
        return None       # traps are not shootable

    def trigger(self, kind=None):
        if self.state != "idle":
            return
        self.kind = kind or random.choice(("explosive", "flash", "fire"))
        self.state = "warn"
        self.timer = 2.0
        self.icon_tn.setText(TRAP_ICONS[self.kind])
        self.ring.show()
        self.icon.show()
        self.match.audio.play3d("trap_warn", self.pos)

    def update(self, dt, t):
        if self.state == "idle":
            return
        m = self.match
        self.timer -= dt
        c = TRAP_COLORS[self.kind]
        if self.state == "warn":
            k = 1 - self.timer / 2.0
            radius = {"explosive": 5.5, "flash": 3.0, "fire": 4.0}[self.kind]
            pulse = 0.5 + 0.5 * math.sin(t * (8 + 20 * k))
            self.ring.setScale(radius * (0.3 + 0.7 * min(1, k * 1.6)))
            self.ring.setColorScale(c[0] * (1 + 2 * pulse), c[1] * (1 + 2 * pulse),
                                    c[2] * (1 + 2 * pulse), 1)
            self.icon.setColorScale(c[0] * 3, c[1] * 3, c[2] * 3, 1)
            self.icon.setZ(2.6 + math.sin(t * 6) * 0.15)
            m.fx.ground_warning(self.pos, radius * 0.9, c, k)
            self.beep_t -= dt
            if self.beep_t <= 0:
                self.beep_t = 0.4 - 0.3 * k
                m.audio.play3d("beep", self.pos, 0.6)
            if self.timer <= 0.3 and self.grenade is None:
                # grenade pops out of the hatch
                self.grenade = self.pos + Vec3(0, 0, 0.2)
            if self.grenade is not None:
                self.grenade.z += dt * 5
                m.fx.trail(self.grenade, c, 0.3)
            if self.timer <= 0:
                self._detonate()
        elif self.state == "burning":
            if int(t * 10) != int((t - dt) * 10):
                for tg in m.living_combatants():
                    d = tg.body.pos - self.pos
                    if d.x * d.x + d.y * d.y < 4.0 * 4.0 and tg.body.pos.z < 1.5:
                        tg.ignite(self, 2.0)
            if self.timer <= 0:
                self.state = "idle"

    def _detonate(self):
        m = self.match
        p = self.grenade or (self.pos + Vec3(0, 0, 1.2))
        self.grenade = None
        self.ring.hide()
        self.icon.hide()
        if self.kind == "explosive":
            m.fx.explosion(p, 5.0, "explosive")
            m.audio.play3d("explosion", p)
            m.radial_damage(p, 5.5, 70, self, "TRAP", kind="explosive")
            self.state = "idle"
        elif self.kind == "flash":
            m.fx.explosion(p, 3.0, "flash")
            m.audio.play3d("flashbang", p)
            m.flashbang(p, 16.0, self)
            self.state = "idle"
        else:
            m.fx.explosion(p, 3.0, "fire")
            m.fx.fire_zone(self.pos, 4.0, 5.0)
            m.audio.play3d("fire_bomb", p)
            m.radial_damage(p, 3.0, 20, self, "TRAP", kind="fire")
            self.state = "burning"
            self.timer = 5.0

    def cleanup(self):
        self.np.removeNode()


# ============================================================================
class LaserSweeper(Hazard):
    name = "LASER"

    def __init__(self, match, x, y, length):
        super().__init__(match)
        self.pos = Vec3(x, y, 0)
        self.length = length
        self.angle = random.uniform(0, math.tau)
        self.speed = 0.85 * random.choice((-1, 1))
        self.heights = (0.5, 1.35)
        self.level = 0
        self.switch_t = 7.0
        self.hit_cd = {}
        self.np = match.world_root.attachNewNode("sweeper")
        self.np.setPos(self.pos)
        mb = geom.MeshBuilder("post")
        mb.cylinder((0, 0, 0), 0.35, 1.8, (0.25, 0.25, 0.28, 1), 12)
        p = mb.node()
        p.reparentTo(self.np)
        p.setTexture(match.textures.metal)
        p.setShaderInput("u_mat", MAT_BODY)
        self.beam = geom.beam_mesh()
        self.beam.reparentTo(self.np)
        fx_node(self.beam, 0, hue_lock=True)
        self.beam2 = geom.beam_mesh()
        self.beam2.reparentTo(self.np)
        fx_node(self.beam2, 0, hue_lock=True)

    def ray_hit(self, o, d, max_t):
        return None

    def update(self, dt, t):
        m = self.match
        self.angle += self.speed * dt
        self.switch_t -= dt
        warn = self.switch_t < 1.0
        if self.switch_t <= 0:
            self.level = 1 - self.level
            self.switch_t = random.uniform(5.0, 8.0)
        h = self.heights[self.level]
        blink = 1.0 if (not warn or math.sin(t * 30) > 0) else 0.3
        col = (3.0 * blink, 0.9 * blink if warn else 0.1, 0.1) if warn else (3.0, 0.12, 0.1)
        for b, a in ((self.beam, self.angle), (self.beam2, self.angle + math.pi)):
            b.setPos(0, 0, h)
            b.setHpr(math.degrees(a) - 90, 0, 0)
            b.setScale(0.12, self.length, 0.12)
            b.setColorScale(col[0], col[1], col[2], 1)
        # damage: distance from each body to the two arms
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        for c in m.living_combatants():
            if m.time < self.hit_cd.get(c.cid, 0):
                continue
            feet = c.body.pos.z
            if not (feet < h < feet + c.body.height):
                continue
            dx = c.body.pos.x - self.pos.x
            dy = c.body.pos.y - self.pos.y
            along = dx * ca + dy * sa
            perp = abs(-dx * sa + dy * ca)
            if abs(along) <= self.length and perp < c.body.radius + 0.08:
                self.hit_cd[c.cid] = m.time + 0.6
                m.damage(c, 22, self, "LASER", Vec3(c.body.pos.x, c.body.pos.y, h), kind="laser")
                push = Vec3(-sa, ca, 0) * (1 if (-dx * sa + dy * ca) > 0 else -1)
                c.body.vel += push * 6 + Vec3(0, 0, 3)
                m.fx.sparks_at(Vec3(c.body.pos.x, c.body.pos.y, h), (0, 0, 1), 16, RED, 7)

    def cleanup(self):
        self.np.removeNode()


class Mine(Hazard):
    name = "MINE"

    def __init__(self, match, spots, mgr):
        super().__init__(match)
        self.spots = spots
        self.mgr = mgr
        self.radius = 0.4
        self.health = self.max_health = 1.0
        self.state = "armed"
        self.timer = 0.0
        self.np = match.world_root.attachNewNode("mine")
        mb = geom.MeshBuilder("mine")
        mb.cylinder((0, 0, 0), 0.32, 0.12, (0.2, 0.2, 0.22, 1), 12)
        b = mb.node()
        b.reparentTo(self.np)
        b.setTexture(match.textures.metal)
        b.setShaderInput("u_mat", MAT_BODY)
        mb = geom.MeshBuilder("mine_light")
        mb.sphere((0, 0, 0.14), 0.08, (1, 1, 1, 1), 4, 6)
        self.light = mb.node()
        self.light.reparentTo(self.np)
        self.light.setTexture(match.textures.white)
        self.light.setShaderInput("u_mat", MAT_NEON)
        self.light.setShaderInput("u_hue", 0.0)
        self._place()

    def _place(self):
        occupied = {(round(m.pos.x), round(m.pos.y)) for m in self.mgr.mines
                    if m is not self and m.alive}
        free = [s for s in self.spots if (round(s[0]), round(s[1])) not in occupied]
        s = random.choice(free or self.spots)
        self.pos = Vec3(s[0] + random.uniform(-1.5, 1.5), s[1] + random.uniform(-1.5, 1.5), 0.0)
        self.np.setPos(self.pos)
        self.np.show()
        self.alive = True
        self.state = "armed"

    def center(self):
        return self.pos + Vec3(0, 0, 0.1)

    def update(self, dt, t):
        m = self.match
        if not self.alive:
            self.timer -= dt
            if self.timer <= 0:
                self._place()
            return
        if self.state == "armed":
            on = math.sin(t * 5 + self.pos.x) > 0.6
            self.light.setColorScale(3 if on else 0.3, 0.1, 0.05, 1)
            for c in m.living_combatants():
                if (c.body.pos - self.pos).lengthSquared() < 2.3 * 2.3:
                    self.state = "trip"
                    self.timer = 0.5
                    m.audio.play3d("mine_beep", self.pos)
                    break
        elif self.state == "trip":
            self.timer -= dt
            on = math.sin(t * 50) > 0
            self.light.setColorScale(4 if on else 0.5, 0.2, 0.1, 1)
            if self.timer <= 0:
                self.destroy(None)

    def apply_hit(self, dmg, source, headshot=False, pos=None, weapon=""):
        if self.alive:
            self.destroy(source)
        return True

    def destroy(self, source):
        m = self.match
        self.alive = False
        self.np.hide()
        self.timer = 12.0
        m.fx.explosion(self.center(), 4.0, "explosive")
        m.audio.play3d("explosion", self.center())
        m.radial_damage(self.center(), 4.0, 55, source if source is not None else self, "MINE",
                        kind="explosive")

    def cleanup(self):
        self.np.removeNode()


class GravityZone:
    def __init__(self, match, x, y, r):
        self.match = match
        self.pos = Vec3(x, y, 0)
        self.r = r
        self.np = match.world_root.attachNewNode("gravzone")
        self.np.setPos(self.pos)
        mb = geom.MeshBuilder("grav_rings")
        for z in (0.05, 3.0, 6.0):
            mb.ring(r - 0.12, r, (0.5, 0.4, 1.0, 1), 40, z=z)
        self.rings = mb.node()
        self.rings.reparentTo(self.np)
        fx_node(self.rings, 4, hue_lock=True)
        self.rings.setColorScale(0.6, 0.5, 2.0, 1)
        col = geom.cone_mesh(12)
        col.reparentTo(self.np)
        col.setPos(0, 0, 8)
        col.setScale(r, r, 8)
        fx_node(col, 1, hue_lock=True)
        col.setColorScale(0.08, 0.05, 0.25, 1)

    def contains(self, p):
        d = p - self.pos
        return d.x * d.x + d.y * d.y < self.r * self.r and p.z < 8.5

    def update(self, dt, t):
        self.rings.setH(t * 30)
        self.rings.setZ(math.sin(t * 1.2) * 0.4)
        if random.random() < 0.6 * self.match.fx.q + 0.2:
            a = random.uniform(0, math.tau)
            rr = math.sqrt(random.random()) * self.r
            self.match.fx.glow.emit(1, self.pos + Vec3(math.cos(a) * rr, math.sin(a) * rr, 0.1),
                                    (0, 0, random.uniform(2, 4)), 2.0, 0.12, 0.02,
                                    (1.0, 0.8, 3.0, 1), (0.2, 0.1, 0.6, 0))

    def cleanup(self):
        self.np.removeNode()


# ============================================================================
class HazardManager:
    def __init__(self, match, turrets=True, drones=0, traps=True, chaos=False,
                 drone_interval=30.0):
        self.match = match
        self.turrets = [Turret(match, *t) for t in L.TURRETS] if turrets else []
        self.drones = []
        self.max_drones = drones
        self.drone_interval = drone_interval
        self.drone_timer = drone_interval * 0.6
        self.traps = [GrenadeTrap(match, *p) for p in L.TRAP_SPOTS] if traps else []
        self.trap_timer = random.uniform(8, 14)
        self.chaos = chaos
        self.mines = []
        self.sweepers = []
        self.gravity = []
        self.enabled = True
        if chaos:
            self.sweepers = [LaserSweeper(match, *s) for s in L.LASER_SWEEPERS]
            for _ in range(6):
                self.mines.append(Mine(match, L.MINE_FIELD, self))
            self.gravity = [GravityZone(match, *g) for g in L.GRAVITY_ZONES]

    def all_shootable(self):
        out = [t for t in self.turrets if t.alive]
        out += [d for d in self.drones if d.alive]
        out += [m for m in self.mines if m.alive]
        return out

    def spawn_drone(self, hp_scale=1.0):
        p = random.choice(L.DRONE_SPAWNS)
        d = Drone(self.match, Vec3(*p), hp_scale)
        self.drones.append(d)
        self.match.fx.shockwave(Vec3(*p), 3.0, (1.0, 0.3, 0.1), 0.5, up=False)
        return d

    def gravity_at(self, p):
        for g in self.gravity:
            if g.contains(p):
                return True
        return False

    def trigger_random_trap(self, kind=None):
        idle = [t for t in self.traps if t.state == "idle"]
        if idle:
            random.choice(idle).trigger(kind)

    def emp(self, pos, radius, duration):
        for h in self.all_shootable():
            if (h.center() - pos).lengthSquared() < radius * radius:
                h.emp(duration)

    def update(self, dt, t):
        if not self.enabled:
            return
        for tr in self.turrets:
            tr.update(dt, t)
        for d in self.drones:
            d.update(dt, t)
        dead = [d for d in self.drones if not d.alive]
        for d in dead:
            d.cleanup()
        self.drones = [d for d in self.drones if d.alive]
        if self.max_drones > 0:
            self.drone_timer -= dt
            if self.drone_timer <= 0:
                self.drone_timer = self.drone_interval
                if len(self.drones) < self.max_drones:
                    self.spawn_drone()
        if self.traps:
            self.trap_timer -= dt
            if self.trap_timer <= 0:
                self.trap_timer = random.uniform(9, 17) * (0.6 if self.chaos else 1.0)
                self.trigger_random_trap()
            for tr in self.traps:
                tr.update(dt, t)
        for s in self.sweepers:
            s.update(dt, t)
        for mn in self.mines:
            mn.update(dt, t)
        for g in self.gravity:
            g.update(dt, t)

    def cleanup(self):
        for group in (self.turrets, self.drones, self.traps, self.sweepers, self.mines,
                      self.gravity):
            for h in group:
                h.cleanup()
