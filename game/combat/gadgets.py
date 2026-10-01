"""Hotbar gadgets: thrown bombs (slot 4) and a personal attack drone (slot 5).

Offline everything is simulated here.  Online the thrower's game simulates its own
bombs/drone and reports the blast / drone hits; the server validates and applies the
damage, and other players see a visual copy (``remote_*``).
"""

import math
import random

from panda3d.core import NodePath, Vec3, Vec4

from neon_shared import gadgets as G

from ..gfx import geom

GRAVITY = 18.0
MAT_BODY = Vec4(40.0, 0.6, 0.4, 0.0)
MAT_GLOW = Vec4(1.0, 0.0, 0.0, 2.5)


class Bomb:
    def __init__(self, mgr, owner, pos, vel, seq=None, remote=False):
        self.owner = owner
        self.pos = Vec3(pos)
        self.vel = Vec3(vel)
        self.fuse = G.BOMB_FUSE if not remote else G.BOMB_FUSE + 3.0   # remote waits for "boom"
        self.seq = seq
        self.remote = remote
        self.np = mgr.bomb_proto.copyTo(mgr.match.world_root)
        self.np.setPos(self.pos)
        self.done = False


class Drone:
    """Friendly drone that orbits its owner and shoots the nearest visible enemy."""

    def __init__(self, mgr, owner, remote=False):
        m = mgr.match
        self.owner = owner
        self.remote = remote
        self.life = G.DRONE_LIFE
        self.fire_t = 1.0
        self.phase = random.uniform(0, math.tau)
        self.pos = owner.body.pos + Vec3(0, 0, 2.6)
        self.np = mgr.drone_proto.copyTo(m.world_root)
        self.np.setPos(self.pos)
        self.target = None
        self.done = False


class GadgetManager:
    def __init__(self, match):
        self.match = match
        self.bombs = []
        self.drones = []
        self.seq = 0
        mb = geom.MeshBuilder("bomb")
        mb.sphere((0, 0, 0), 0.16, (0.18, 0.2, 0.22, 1), 6, 10)
        mb.cbox((0, 0, 0.17), (0.07, 0.07, 0.08), (0.25, 0.25, 0.27, 1))
        body = mb.node()
        body.setTexture(match.textures.metal)
        body.setShaderInput("u_mat", MAT_BODY)
        mb = geom.MeshBuilder("bomb_led")
        mb.ring(0.1, 0.165, (1.0, 0.3, 0.1, 1), 16, z=0.0)
        led = mb.node()
        led.setTwoSided(True)
        led.setTexture(match.textures.white)
        led.setShaderInput("u_mat", MAT_GLOW)
        led.setShaderInput("u_hue", 0.0)
        self.bomb_proto = NodePath("bomb")
        body.reparentTo(self.bomb_proto)
        led.reparentTo(self.bomb_proto)
        mb = geom.MeshBuilder("ally_drone")
        mb.cylinder((0, 0, -0.08), 0.3, 0.16, (0.25, 0.28, 0.32, 1), 12)
        for a in range(4):
            ang = a * math.pi / 2 + math.pi / 4
            mb.cbox((math.cos(ang) * 0.42, math.sin(ang) * 0.42, 0.0), (0.34, 0.06, 0.04),
                    (0.2, 0.2, 0.22, 1))
        d = mb.node()
        d.setTexture(match.textures.metal)
        d.setShaderInput("u_mat", MAT_BODY)
        mb = geom.MeshBuilder("ally_drone_glow")
        mb.ring(0.31, 0.37, (0.2, 1.0, 0.6, 1), 18, z=0.0)
        mb.sphere((0, 0.2, -0.08), 0.07, (0.2, 1.0, 0.6, 1), 4, 6)
        g = mb.node()
        g.setTwoSided(True)
        g.setTexture(match.textures.white)
        g.setShaderInput("u_mat", MAT_GLOW)
        g.setShaderInput("u_hue", 0.0)
        self.drone_proto = NodePath("ally_drone")
        d.reparentTo(self.drone_proto)
        g.reparentTo(self.drone_proto)

    # ------------------------------------------------------------------ actions
    def throw(self, c):
        """Slot 4.  Returns an error key or None."""
        m = self.match
        if not c.alive:
            return "dead"
        if c.bombs <= 0:
            return "no_bombs"
        c.bombs -= 1
        fwd = c.aim_dir()
        o = c.eye_pos() + fwd * 0.5 - Vec3(0, 0, 0.15)
        v = fwd * G.BOMB_THROW_SPEED + Vec3(0, 0, 3.5) + Vec3(c.body.vel.x, c.body.vel.y, 0) * 0.5
        seq = None
        if m.net is not None and getattr(c, "net_local", False):
            self.seq += 1
            seq = self.seq
            m.net.local_bomb(seq, o, v, c)
        self.bombs.append(Bomb(self, c, o, v, seq))
        m.audio.play3d("melee_swing", o, 0.6, source=c)
        return None

    def deploy(self, c):
        """Slot 5.  Returns an error key or None."""
        m = self.match
        if not c.alive:
            return "dead"
        if m.time < c.drone_ready_at:
            return "drone_cd"
        c.drone_ready_at = m.time + G.DRONE_COOLDOWN
        for d in self.drones:
            if d.owner is c:
                d.life = 0.0
        self.drones.append(Drone(self, c))
        if m.net is not None and getattr(c, "net_local", False):
            m.net.local_drone(c)
        m.audio.play3d("drone_charge", c.body.pos + Vec3(0, 0, 2), 0.6, source=c)
        m.fx.shockwave(c.body.pos + Vec3(0, 0, 2.4), 1.2, (0.2, 1.0, 0.6), 0.3)
        return None

    # ------------------------------------------------------------------ network (others' gadgets)
    def remote_bomb(self, c, o, v):
        self.bombs.append(Bomb(self, c, o, v, remote=True))

    def remote_boom(self, c, pos):
        for b in self.bombs:
            if b.remote and b.owner is c and not b.done:
                b.pos = Vec3(pos)
                self._explode(b)
                return
        self._blast_fx(Vec3(pos))

    def remote_drone(self, c):
        for d in self.drones:
            if d.owner is c:
                d.life = 0.0
        self.drones.append(Drone(self, c, remote=True))

    def remote_drone_shot(self, c, target):
        for d in self.drones:
            if d.owner is c and not d.done and target is not None:
                self._bolt_fx(d, target.chest_pos())

    # ------------------------------------------------------------------ simulation
    def update(self, dt):
        m = self.match
        for b in self.bombs:
            if b.done:
                continue
            b.vel.z -= GRAVITY * dt
            step = b.vel * dt
            ln = step.length()
            if ln > 1e-5:
                d = step / ln
                t, n = m.coll.raycast(b.pos, d, ln + 0.16)
                if t is not None:
                    # bounce: reflect off the surface and lose energy
                    b.pos += d * max(0.0, t - 0.17)
                    vn = b.vel.dot(n)
                    b.vel = (b.vel - n * (2 * vn)) * 0.45
                    if n.z > 0.7 and abs(b.vel.z) < 1.5:
                        b.vel.z = 0.0
                        b.vel.x *= 0.8
                        b.vel.y *= 0.8
                else:
                    b.pos += step
            b.np.setPos(b.pos)
            b.np.setH(b.np.getH() + 360 * dt)
            b.fuse -= dt
            # blinking LED speeds up near the end
            blink = 1.0 if math.sin(m.time * (8 + 30 * max(0.0, 1 - b.fuse / G.BOMB_FUSE))) > 0 \
                else 0.25
            b.np.setColorScale(blink, blink, blink, 1)
            if b.fuse <= 0:
                self._explode(b)
        self.bombs = [b for b in self.bombs if not b.done]
        for d in self.drones:
            if d.done:
                continue
            d.life -= dt
            if not d.owner.alive and d.life > 0.8:
                d.life = 0.8                     # the drone powers down with its owner
            if d.life <= 0:
                self._remove_drone(d)
                continue
            self._drone_update(d, dt)
        self.drones = [d for d in self.drones if not d.done]

    def _drone_update(self, d, dt):
        m = self.match
        o = d.owner
        d.phase += dt * 0.9
        right = Vec3(math.cos(math.radians(o.yaw)), math.sin(math.radians(o.yaw)), 0)
        want = o.body.pos + right * (1.4 * math.cos(d.phase)) + \
            Vec3(math.sin(d.phase) * 0.8, math.cos(d.phase * 0.7) * 0.8, 2.5)
        want.z = min(want.z, m.coll.ceiling_z - 0.6)
        d.pos += (want - d.pos) * min(1.0, dt * 3.0)
        d.np.setPos(d.pos + Vec3(0, 0, math.sin(m.time * 4 + d.phase) * 0.06))
        if d.life < 2.0:
            d.np.setAlphaScale(max(0.2, d.life / 2.0))
        if d.remote:
            d.np.setH(o.yaw)
            return
        # pick the nearest visible enemy
        best = None
        bd = G.DRONE_RANGE
        for e in m.enemies_of(o):
            if e.cloaked:
                continue
            dist = (e.chest_pos() - d.pos).length()
            if dist < bd and m.coll.line_of_sight(d.pos, e.chest_pos()):
                bd = dist
                best = e
        d.target = best
        if best is not None:
            d.np.lookAt(best.chest_pos())
            d.np.setP(d.np.getP() * 0.3)
        else:
            d.np.setH(o.yaw)
        d.fire_t -= dt
        if best is not None and d.fire_t <= 0:
            d.fire_t = G.DRONE_FIRE_INTERVAL
            aim = best.chest_pos() + best.body.vel * 0.15
            v = aim - d.pos
            v.normalize()
            m.projectiles.spawn_ally_bolt(o, d.pos + v * 0.45, v)
            m.audio.play3d("drone_shot", d.pos, 0.7)

    def _bolt_fx(self, d, end):
        m = self.match
        m.fx.beam(d.pos, end, (0.2, 1.0, 0.6), 0.06, 0.12, 3.0)
        m.fx.impact(end, Vec3(0, 0, 1), (0.2, 1.0, 0.6))
        m.audio.play3d("drone_shot", d.pos, 0.6)

    def _remove_drone(self, d):
        d.done = True
        self.match.fx.sparks_at(d.pos, (0, 0, 1), 18, (0.2, 1.0, 0.6), 4)
        d.np.removeNode()

    def _blast_fx(self, pos):
        m = self.match
        m.fx.explosion(pos, G.BOMB_RADIUS * 0.8, "explosive")
        m.audio.play3d("explosion", pos)

    def _explode(self, b):
        m = self.match
        b.done = True
        b.np.removeNode()
        self._blast_fx(b.pos)
        if b.remote:
            return
        if m.net is not None and b.seq is not None:
            m.net.local_boom(b.seq, b.pos, b.owner)          # the server applies the damage
        else:
            m.radial_damage(b.pos + Vec3(0, 0, 0.2), G.BOMB_RADIUS, G.BOMB_DMG, b.owner, "BOMB",
                            kind="explosive")

    def cleanup(self):
        for b in self.bombs:
            if not b.done:
                b.np.removeNode()
        for d in self.drones:
            if not d.done:
                d.np.removeNode()
        self.bombs = []
        self.drones = []
