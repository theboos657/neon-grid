"""Loot boxes, energy charging ports, jump pads, sliding walls and pickups
(coin / XP orbs dropped by enemies)."""

import math
import random

from panda3d.core import Vec3, Vec4

from neon_shared import arena_layout as L
from neon_shared.abilities import MAX_ENERGY, PORT_CHARGE_TIME
from neon_shared.pickups import HEAL_AMOUNT, HEAL_RADIUS, HEAL_RESPAWN

from ..gfx import geom
from ..gfx.effects import fx_node

MAT_NEON = Vec4(1, 0, 0, 2.6)
MAT_BODY = Vec4(40, 0.8, 0.35, 0)
LOOT_COOLDOWN = 25.0


def _world_mat(np_, mat):
    np_.setShaderInput("u_mat", mat)


class LootBox:
    """Rechargeable crate: refills ammo for all weapons (coins come from kills)."""

    def __init__(self, match, x, y, z=0.0):
        self.match = match
        self.pos = Vec3(x, y, z)
        self.ready = True
        self.timer = 0.0
        self.np = match.world_root.attachNewNode("lootbox")
        self.np.setPos(self.pos)
        mb = geom.MeshBuilder("loot")
        mb.cbox((0, 0, 0.35), (1.1, 0.8, 0.7), (0.3, 0.32, 0.36, 1))
        body = mb.node()
        body.reparentTo(self.np)
        body.setTexture(match.textures.metal)
        _world_mat(body, MAT_BODY)
        mb = geom.MeshBuilder("loot_glow")
        mb.cbox((0, 0, 0.72), (1.14, 0.84, 0.05), (0.1, 1.0, 1.0, 1))
        mb.cbox((0, -0.41, 0.35), (0.5, 0.02, 0.12), (1.0, 0.85, 0.2, 1))
        mb.cbox((0, 0.41, 0.35), (0.5, 0.02, 0.12), (1.0, 0.85, 0.2, 1))
        self.glow = mb.node()
        self.glow.reparentTo(self.np)
        self.glow.setTexture(match.textures.white)
        _world_mat(self.glow, MAT_NEON)
        # floating holo icon
        mb = geom.MeshBuilder("icon")
        mb.cbox((0, 0, 0), (0.25, 0.25, 0.25), (1, 1, 1, 1))
        self.icon = mb.node()
        self.icon.reparentTo(self.np)
        self.icon.setPos(0, 0, 1.3)
        self.icon.setTexture(match.textures.white)
        _world_mat(self.icon, MAT_NEON)
        self.icon.setColorScale(0.2, 1.0, 1.0, 1)

    def update(self, dt, t):
        if not self.ready:
            self.timer -= dt
            if self.timer <= 0:
                self.ready = True
                self.glow.setColorScale(1, 1, 1, 1)
                self.icon.show()
                self.match.fx.pickup_burst(self.pos + Vec3(0, 0, 0.9))
            else:
                k = 1 - self.timer / LOOT_COOLDOWN
                self.glow.setColorScale(0.15 + 0.2 * k, 0.15 + 0.2 * k, 0.15 + 0.2 * k, 1)
            return
        self.icon.setH(t * 90)
        self.icon.setZ(1.3 + math.sin(t * 2.5) * 0.12)
        for c in self.match.living_combatants():
            if (c.body.pos - self.pos).lengthSquared() < 1.6 * 1.6 and \
                    abs(c.body.pos.z - self.pos.z) < 1.5 and c.needs_loot():
                self.open(c)
                break

    def open(self, c):
        self.ready = False
        self.timer = LOOT_COOLDOWN
        self.icon.hide()
        ammo = c.refill_ammo(0.5)
        coins = 0
        self.match.fx.pickup_burst(self.pos + Vec3(0, 0, 0.8), (1.0, 0.85, 0.3))
        self.match.audio.play3d("pickup", self.pos)
        self.match.on_loot(c, ammo, coins)


class ChargePort:
    """Stand on it for PORT_CHARGE_TIME seconds to fully recharge energy."""

    def __init__(self, match, x, y, z=0.0):
        self.match = match
        self.pos = Vec3(x, y, z)
        self.progress = {}
        self.np = match.world_root.attachNewNode("port")
        self.np.setPos(self.pos)
        mb = geom.MeshBuilder("port")
        mb.cylinder((0, 0, 0), 1.3, 0.08, (0.2, 0.22, 0.25, 1), 24)
        base = mb.node()
        base.reparentTo(self.np)
        base.setTexture(match.textures.metal)
        _world_mat(base, MAT_BODY)
        mb = geom.MeshBuilder("port_ring")
        mb.ring(1.05, 1.25, (0.2, 1.0, 0.6, 1), 32, z=0.09)
        mb.ring(0.3, 0.42, (0.2, 1.0, 0.6, 1), 24, z=0.09)
        ring = mb.node()
        ring.reparentTo(self.np)
        ring.setTwoSided(True)
        ring.setTexture(match.textures.white)
        _world_mat(ring, MAT_NEON)
        self.ring = ring
        col = geom.cone_mesh(12)
        self.column = col
        col.reparentTo(self.np)
        col.setPos(0, 0, 3.0)
        col.setScale(1.2, 1.2, 3.0)
        fx_node(col, 1, hue_lock=True)
        col.setColorScale(0.02, 0.3, 0.15, 1)

    def update(self, dt, t):
        active = False
        for c in self.match.living_combatants():
            d = c.body.pos - self.pos
            if d.x * d.x + d.y * d.y < 1.25 * 1.25 and -0.3 < d.z < 0.6:
                if c.energy >= MAX_ENERGY - 0.5:
                    self.progress[c.cid] = 0.0
                    c.port_progress = 0.0
                    continue
                active = True
                p = self.progress.get(c.cid, 0.0) + dt
                self.progress[c.cid] = p
                c.port_progress = min(1.0, p / PORT_CHARGE_TIME)
                if int(t * 12) % 3 == 0:
                    a = random.uniform(0, math.tau)
                    self.match.fx.glow.emit(1, self.pos + Vec3(math.cos(a), math.sin(a), 0.1),
                                            (0, 0, 3.0), 0.6, 0.18, 0.05, (0.4, 3.0, 1.5, 1),
                                            (0, 0.2, 0.1, 0))
                if p >= PORT_CHARGE_TIME:
                    c.energy = MAX_ENERGY
                    c.port_progress = 0.0
                    self.progress[c.cid] = 0.0
                    self.match.fx.pickup_burst(c.body.pos + Vec3(0, 0, 1), (0.3, 1.0, 0.6))
                    self.match.audio.play3d("energy_full", self.pos)
                    self.match.on_port_charge(c)
            else:
                if self.progress.get(c.cid):
                    self.progress[c.cid] = 0.0
                    c.port_progress = 0.0
        k = 1.0 + (0.8 + 0.6 * math.sin(t * 10) if active else 0.25 * math.sin(t * 2))
        self.ring.setColorScale(k, k, k, 1)
        self.ring.setH(t * (120 if active else 20))


class JumpPad:
    def __init__(self, match, x, y, tx, ty, tz, z0=0.0):
        self.match = match
        self.pos = Vec3(x, y, z0)
        self.target = Vec3(tx, ty, tz)
        self.np = match.world_root.attachNewNode("jumppad")
        self.np.setPos(self.pos)
        mb = geom.MeshBuilder("pad")
        mb.cylinder((0, 0, 0), 1.1, 0.12, (0.2, 0.2, 0.24, 1), 20)
        b = mb.node()
        b.reparentTo(self.np)
        b.setTexture(match.textures.metal)
        _world_mat(b, MAT_BODY)
        mb = geom.MeshBuilder("pad_glow")
        for i in range(3):
            mb.ring(0.35 + i * 0.25, 0.43 + i * 0.25, (0.1, 0.8, 1.0, 1), 24, z=0.13)
        g = mb.node()
        g.reparentTo(self.np)
        g.setTwoSided(True)
        g.setTexture(match.textures.white)
        _world_mat(g, MAT_NEON)
        self.glow = g
        # launch velocity so the apex clears the catwalk railings
        apex = max(tz, z0) + 2.2
        grav = 18.0
        vz = math.sqrt(2 * grav * (apex - z0))
        t_up = vz / grav
        t_down = math.sqrt(2 * (apex - tz) / grav)
        flight = t_up + t_down
        self.launch = Vec3((tx - x) / flight, (ty - y) / flight, vz)

    def update(self, dt, t):
        self.glow.setColorScale(1 + 0.5 * math.sin(t * 6), 1 + 0.5 * math.sin(t * 6), 1 + 0.5 *
                                math.sin(t * 6), 1)
        for c in self.match.living_combatants():
            d = c.body.pos - self.pos
            if d.x * d.x + d.y * d.y < 1.0 and -0.3 < d.z < 0.3 and c.body.vel.z <= 0.1:
                c.body.vel = Vec3(self.launch)
                c.body.on_ground = False
                c.launched = 1.2
                self.match.audio.play3d("jumppad", self.pos)
                self.match.fx.shockwave(self.pos + Vec3(0, 0, 0.2), 2.5, (0.2, 0.9, 1.0), 0.3)


class SlidingWall:
    """Moves back and forth; its stripes flash before each move (warning)."""

    def __init__(self, match, cx, cy, sx, sy, h, axis, travel, period, phase):
        self.match = match
        self.c = Vec3(cx, cy, 0)
        self.size = (sx, sy, h)
        self.axis = axis
        self.travel = travel
        self.period = period
        self.phase = phase
        self.box = match.coll.add_dynamic([0, 0, 0, 0, 0, 0, "slider"])
        self.np = match.world_root.attachNewNode("slider")
        mb = geom.MeshBuilder("slider")
        mb.box((-sx / 2, -sy / 2, 0), (sx / 2, sy / 2, h), (0.35, 0.38, 0.42, 1), uv_scale=0.5)
        body = mb.node()
        body.reparentTo(self.np)
        body.setTexture(match.textures.metal)
        _world_mat(body, MAT_BODY)
        mb = geom.MeshBuilder("slider_warn")
        e = 0.03
        mb.box((-sx / 2 - e, -sy / 2 - e, h - 0.25), (sx / 2 + e, sy / 2 + e, h - 0.05),
               (1, 1, 1, 1), uv_scale=2.0)
        mb.box((-sx / 2 - e, -sy / 2 - e, 0.05), (sx / 2 + e, sy / 2 + e, 0.25),
               (1, 1, 1, 1), uv_scale=2.0)
        self.warn = mb.node()
        self.warn.reparentTo(self.np)
        self.warn.setTexture(match.textures.stripes)
        _world_mat(self.warn, Vec4(1, 0, 0, 1.2))
        self.warn.setShaderInput("u_hue", 0.0)
        mb = geom.MeshBuilder("slider_neon")
        mb.box((-sx / 2 - e, -sy / 2 - e, h * 0.5 - 0.04), (sx / 2 + e, sy / 2 + e, h * 0.5 + 0.04),
               (0.1, 0.9, 1, 1))
        n = mb.node()
        n.reparentTo(self.np)
        n.setTexture(match.textures.white)
        _world_mat(n, MAT_NEON)
        self.moving_prev = False
        self.update(0, 0)

    def _offset(self, t):
        # dwell - move - dwell - move, eased
        u = ((t + self.phase) % self.period) / self.period
        if u < 0.35:
            k = 0.0
        elif u < 0.5:
            k = (u - 0.35) / 0.15
            k = k * k * (3 - 2 * k)
        elif u < 0.85:
            k = 1.0
        else:
            k = 1 - (u - 0.85) / 0.15
            k = k * k * (3 - 2 * k)
        return (k - 0.5) * self.travel, u

    def update(self, dt, t):
        off, u = self._offset(t)
        p = Vec3(self.c)
        if self.axis == "x":
            p.x += off
        else:
            p.y += off
        self.np.setPos(p)
        sx, sy, h = self.size
        self.box[0:6] = [p.x - sx / 2, p.y - sy / 2, 0.0, p.x + sx / 2, p.y + sy / 2, h]
        # warning flashes during the second before a move starts, and while moving
        warn = (0.27 < u < 0.5) or (0.77 < u < 1.0)
        if warn:
            f = 1.0 + 2.5 * (0.5 + 0.5 * math.sin(t * 22))
            self.warn.setColorScale(f, f * 0.6, f * 0.2, 1)
        else:
            self.warn.setColorScale(0.35, 0.3, 0.2, 1)
        moving = (0.35 < u < 0.5) or (0.85 < u < 1.0)
        if moving and not self.moving_prev:
            self.match.audio.play3d("wall_slide", p)
        self.moving_prev = moving


class Pickup:
    """Coin / XP orb dropped by enemies; magnetises toward nearby combatants."""
    __slots__ = ("pos", "vel", "kind", "amount", "life", "np")

    def __init__(self, pos, kind, amount, np_):
        self.pos = Vec3(pos)
        self.vel = Vec3(random.uniform(-2, 2), random.uniform(-2, 2), random.uniform(3, 5))
        self.kind = kind
        self.amount = amount
        self.life = 20.0
        self.np = np_


class HealthPack:
    """Floating green cross: +50 health, comes back 20 s after it is taken."""

    def __init__(self, match, index, x, y, z=0.0):
        self.match = match
        self.index = index
        self.pos = Vec3(x, y, z)
        self.ready = True
        self.timer = 0.0
        self.pending = 0.0       # online: waiting for the server's answer
        self.np = match.world_root.attachNewNode("healthpack")
        self.np.setPos(self.pos)
        mb = geom.MeshBuilder("hp_base")
        mb.cylinder((0, 0, 0), 0.55, 0.08, (0.2, 0.22, 0.25, 1), 16)
        base = mb.node()
        base.reparentTo(self.np)
        base.setTexture(match.textures.metal)
        _world_mat(base, MAT_BODY)
        mb = geom.MeshBuilder("hp_cross")
        g = (0.25, 1.0, 0.45, 1)
        mb.cbox((0, 0, 0), (0.62, 0.2, 0.2), g)
        mb.cbox((0, 0, 0), (0.2, 0.2, 0.62), g)
        cross = mb.node()
        cross.reparentTo(self.np)
        cross.setZ(0.9)
        cross.setTexture(match.textures.white)
        _world_mat(cross, Vec4(1, 0, 0, 2.4))
        cross.setShaderInput("u_hue", 0.0)
        self.cross = cross
        mb = geom.MeshBuilder("hp_ring")
        mb.ring(0.4, 0.5, g, 20, z=0.09)
        ring = mb.node()
        ring.reparentTo(self.np)
        ring.setTwoSided(True)
        ring.setTexture(match.textures.white)
        _world_mat(ring, Vec4(1, 0, 0, 2.0))
        ring.setShaderInput("u_hue", 0.0)
        self.ring = ring

    def set_ready(self, on):
        self.ready = on
        self.timer = 0.0 if on else HEAL_RESPAWN
        if on:
            self.cross.show()
        else:
            self.cross.hide()

    def update(self, dt, t):
        m = self.match
        if not self.ready:
            self.timer -= dt
            if self.timer <= 0 and not m.online:
                self.set_ready(True)
            self.ring.setColorScale(0.3, 0.3, 0.3, 1)
            return
        self.cross.setH(t * 90)
        self.cross.setZ(0.9 + 0.12 * math.sin(t * 2.5 + self.index))
        self.ring.setColorScale(1, 1, 1, 1)
        if self.pending > 0:
            self.pending -= dt
            return
        for c in m.living_combatants():
            d = c.body.pos - self.pos
            if d.x * d.x + d.y * d.y > HEAL_RADIUS * HEAL_RADIUS or not -0.6 < d.z < 1.2:
                continue
            if c.health >= c.max_health:
                continue
            if m.online:
                if getattr(c, "net_local", False) and m.net is not None:
                    m.net.local_heal(self.index, c)
                    self.pending = 0.8
                continue
            c.health = min(c.max_health, c.health + HEAL_AMOUNT)
            self.taken(c)
            break

    def taken(self, c):
        m = self.match
        self.set_ready(False)
        m.fx.pickup_burst(self.pos + Vec3(0, 0, 0.9), (0.3, 1.0, 0.5))
        m.audio.play3d("energy_full", self.pos, 0.7)
        if c is not None and c is m.player and m.hud:
            from .. import i18n
            m.hud.notice(i18n.t("pickup_heal", n=int(HEAL_AMOUNT)), (0.3, 1.0, 0.5, 1), 1.4)


class Interactables:
    def __init__(self, match):
        self.match = match
        self.heals = [HealthPack(match, i, *p) for i, p in enumerate(L.HEAL_SPOTS)]
        self.loot = [LootBox(match, *p) for p in L.LOOT_BOXES]
        self.ports = [ChargePort(match, *p) for p in L.CHARGE_PORTS]
        self.pads = [JumpPad(match, *p) for p in L.JUMP_PADS]
        self.walls = [SlidingWall(match, *w) for w in L.SLIDING_WALLS]
        self.pickups = []
        mb = geom.MeshBuilder("orb")
        mb.sphere((0, 0, 0), 0.14, (1, 1, 1, 1), 6, 8)
        self.orb_proto = mb.node()

    def drop(self, pos, coins, xp):
        for kind, amount, col in (("coin", coins, (1.0, 0.8, 0.2, 1)), ("xp", xp, (0.3, 1.0, 0.5, 1))):
            if amount <= 0:
                continue
            n = self.orb_proto.copyTo(self.match.world_root)
            n.setTexture(self.match.textures.white)
            n.setShaderInput("u_mat", Vec4(1, 0, 0, 3.0))
            n.setShaderInput("u_hue", 0.0)
            n.setColor(col)
            self.pickups.append(Pickup(pos + Vec3(0, 0, 1.0), kind, amount, n))

    def update(self, dt, t):
        for o in self.loot:
            o.update(dt, t)
        for o in self.ports:
            o.update(dt, t)
        for o in self.pads:
            o.update(dt, t)
        for o in self.heals:
            o.update(dt, t)
        for o in self.walls:
            o.update(dt, t)
        alive = []
        coll = self.match.coll
        for p in self.pickups:
            p.life -= dt
            taker = None
            best = 16.0
            for c in self.match.living_combatants():
                if not c.collects_pickups:
                    continue
                d = (c.body.pos + Vec3(0, 0, 1.0) - p.pos)
                dl = d.lengthSquared()
                if dl < best:
                    best = dl
                    taker = (c, d)
            if taker:
                c, d = taker
                if d.length() < 0.7:
                    self.match.on_pickup(c, p.kind, p.amount)
                    self.match.fx.pickup_burst(p.pos, (1, 0.8, 0.2) if p.kind == "coin"
                                               else (0.3, 1, 0.5))
                    p.np.removeNode()
                    continue
                d.normalize()
                p.vel = p.vel * 0.8 + d * 3.2     # converges to ~16 m/s toward the taker
            else:
                p.vel.z -= 12 * dt
            p.pos += p.vel * dt
            g = coll.ground_height(p.pos.x, p.pos.y, 0.1, p.pos.z + 0.3) + 0.3
            if p.pos.z < g:
                p.pos.z = g
                p.vel.z = abs(p.vel.z) * 0.3
                p.vel.x *= 0.8
                p.vel.y *= 0.8
            p.np.setPos(p.pos + Vec3(0, 0, math.sin(t * 4 + p.life) * 0.06))
            if p.life <= 0:
                p.np.removeNode()
                continue
            alive.append(p)
        self.pickups = alive
