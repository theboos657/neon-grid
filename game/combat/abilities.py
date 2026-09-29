"""Runtime behaviour of the 10 loadout abilities."""

import math
import random

from panda3d.core import Vec3

from neon_shared.abilities import BY_ID

from ..gfx import geom
from ..gfx.effects import fx_node


class AbilityState:
    def __init__(self, aid):
        self.id = aid
        self.data = BY_ID[aid]
        self.cooldown_left = 0.0

    @property
    def ready(self):
        return self.cooldown_left <= 0

    def fraction(self):
        if self.cooldown_left <= 0:
            return 1.0
        return 1.0 - self.cooldown_left / self.data["cooldown"]

    def update(self, dt):
        if self.cooldown_left > 0:
            self.cooldown_left -= dt


def try_activate(match, c, ab):
    """Returns True on success, or a reason string ('cooldown'/'energy'/'locked')."""
    if not ab.ready:
        return "cooldown"
    if match.time < c.ability_lock_until:
        return "locked"
    if c.energy < ab.data["energy"] and not c.infinite_energy:
        return "energy"
    if not c.infinite_energy:
        c.energy -= ab.data["energy"]
    ab.cooldown_left = ab.data["cooldown"] * (0.05 if c.no_cooldowns else 1.0)
    _EFFECTS[ab.id](match, c, ab.data)
    match.on_ability(c, ab.id)
    return True


# ---------------------------------------------------------------------------
def _shield(m, c, d):
    c.shield_hp = 60.0
    c.shield_until = m.time + d["duration"]
    m.fx.shockwave(c.body.pos + Vec3(0, 0, 1), 2.0, (0.3, 0.8, 1.0), 0.35, up=False)
    m.audio.play3d("shield", c.body.pos, source=c)


def _dash(m, c, d):
    yaw = math.radians(c.yaw)
    fwd = Vec3(-math.sin(yaw), math.cos(yaw), 0)
    right = Vec3(math.cos(yaw), math.sin(yaw), 0)
    wish = right * c.input.move_x + fwd * c.input.move_y
    if wish.lengthSquared() < 0.01:
        wish = fwd
    wish.normalize()
    speed = 8.0 / d["duration"]
    c.body.vel = Vec3(wish.x * speed, wish.y * speed, max(c.body.vel.z, 1.0))
    c.dash_until = m.time + d["duration"]
    for i in range(6):
        m.fx.trail(c.body.pos + Vec3(0, 0, 1.0) + wish * (i * 0.3), (0.3, 1.0, 1.0), 0.5)
    m.audio.play3d("dash", c.body.pos, source=c)


def _scan(m, c, d):
    until = m.time + d["duration"]
    for e in m.enemies_of(c):
        if (e.body.pos - c.body.pos).length() < 40.0:
            e.reveal_until = until
            e.revealed_to_team = c.team
            e.revealed_by = c.cid
    m.fx.shockwave(c.body.pos + Vec3(0, 0, 0.2), 40.0, (0.2, 1.0, 1.0), 1.1)
    m.fx.shockwave(c.body.pos + Vec3(0, 0, 1.2), 25.0, (0.6, 1.0, 1.0), 0.8)
    m.audio.play3d("scan", c.body.pos, source=c)


def _decoy(m, c, d):
    m.spawn_decoy(c, d["duration"])
    m.audio.play3d("decoy", c.body.pos, source=c)


def _heal(m, c, d):
    c.heal_left = 45.0
    c.heal_rate = 45.0 / d["duration"]
    m.fx.pickup_burst(c.body.pos + Vec3(0, 0, 1), (0.3, 1.0, 0.5))
    m.audio.play3d("heal", c.body.pos, source=c)


def _speed(m, c, d):
    c.speed_until = m.time + d["duration"]
    m.audio.play3d("speed", c.body.pos, source=c)


def _jets(m, c, d):
    c.body.vel.z = max(c.body.vel.z, 10.5)
    c.body.on_ground = False
    c.jets_until = m.time + d["duration"]
    m.fx.shockwave(c.body.pos + Vec3(0, 0, 0.1), 2.5, (0.4, 0.9, 1.0), 0.3)
    m.audio.play3d("jets", c.body.pos, source=c)


def _emp(m, c, d):
    p = c.body.pos + Vec3(0, 0, 1.0)
    r = 9.0
    m.fx.explosion(p, r, "emp")
    m.audio.play3d("emp", p, source=c)
    if m.hazards:
        m.hazards.emp(p, r, d["duration"])
    for e in m.enemies_of(c):
        if (e.chest_pos() - p).length() < r:
            e.ability_lock_until = m.time + d["duration"]
            e.energy = max(0.0, e.energy - 30)
            e.cloak_until = 0.0
            m.damage(e, 10, c, "EMP", e.chest_pos(), False, kind="emp")


def _cloak(m, c, d):
    c.cloak_until = m.time + d["duration"]
    m.fx.sparks_at(c.body.pos + Vec3(0, 0, 1), (0, 0, 1), 20, (0.5, 0.8, 1.0), 3)
    m.audio.play3d("cloak", c.body.pos, source=c)


def _gravity(m, c, d):
    o = c.eye_pos()
    fwd = c.aim_dir()
    t, n = m.coll.raycast(o, fwd, 25.0)
    p = o + fwd * ((t - 0.8) if t is not None else 25.0)
    if p.z < 1.0:
        p.z = 1.0
    m.wells.append(GravityWell(m, c, p, d["duration"]))
    m.audio.play3d("gravity", p, source=c)


_EFFECTS = {"shield": _shield, "dash": _dash, "scan": _scan, "decoy": _decoy, "heal": _heal,
            "speed": _speed, "jets": _jets, "emp": _emp, "cloak": _cloak, "gravity": _gravity}


class GravityWell:
    """Singularity that pulls enemies in, ticks damage, then implodes."""

    def __init__(self, m, owner, pos, duration):
        self.m = m
        self.owner = owner
        self.pos = Vec3(pos)
        self.life = duration
        self.tick = 0.0
        mb = geom.MeshBuilder("well")
        mb.sphere((0, 0, 0), 1.0, (1, 1, 1, 1), 8, 12)
        self.np = mb.node()
        self.np.reparentTo(m.world_root)
        self.np.setPos(self.pos)
        self.np.setScale(0.6)
        self.np.setTexture(m.textures.white)
        from panda3d.core import Vec4
        self.np.setShaderInput("u_mat", Vec4(1, 0, 0, 3.0))
        self.np.setColorScale(0.5, 0.3, 1.5, 1)
        self.ring = geom.card(1, 1)
        self.ring.reparentTo(m.world_root)
        self.ring.setPos(self.pos)
        fx_node(self.ring, 5, hue_lock=True)
        self.ring.setBillboardPointEye()
        self.ring.setScale(5)
        self.ring.setColorScale(0.4, 0.2, 1.2, 1)

    def update(self, dt):
        m = self.m
        self.life -= dt
        self.tick -= dt
        pulse = 0.6 + 0.15 * math.sin(m.time * 20)
        self.np.setScale(pulse)
        # inflowing particles
        for _ in range(3):
            a = random.uniform(0, math.tau)
            b = random.uniform(-1, 1)
            off = Vec3(math.cos(a) * math.sqrt(1 - b * b), math.sin(a) * math.sqrt(1 - b * b), b) * 5
            m.fx.glow.emit(1, self.pos + off, (-off.x * 2.2, -off.y * 2.2, -off.z * 2.2), 0.45,
                           0.15, 0.02, (1.2, 0.8, 3.0, 1), (0.2, 0.1, 0.8, 0))
        for e in m.enemies_of(self.owner):
            d = self.pos - e.chest_pos()
            dist = d.length()
            if dist < 7.5 and dist > 0.3:
                pull = (1.0 - dist / 7.5) * 38.0 + 6.0
                e.body.vel += d / dist * pull * dt
                e.body.on_ground = False if d.z > 0.5 else e.body.on_ground
                if self.tick <= 0:
                    m.damage(e, 4, self.owner, "GRAVITY WELL", e.chest_pos(), False, kind="gravity")
        if self.tick <= 0:
            self.tick = 0.25
        if self.life <= 0:
            m.fx.explosion(self.pos, 3.0, "emp")
            m.radial_damage(self.pos, 3.5, 15, self.owner, "GRAVITY WELL", kind="gravity")
            self.np.removeNode()
            self.ring.removeNode()
            return False
        return True

    def remove(self):
        self.np.removeNode()
        self.ring.removeNode()
