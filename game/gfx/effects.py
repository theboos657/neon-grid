"""High-level visual effects: explosions, sparks, shockwaves, smoke, debris,
laser pulses, tracers, muzzle flashes, fire zones and warning markers.

Everything is pooled; nothing is created or destroyed during a fight.
"""

import math
import random

import numpy as np
from panda3d.core import ColorBlendAttrib, TransparencyAttrib, Vec3, Vec4

from . import geom, shaders
from .particles import ParticleSystem

ADD = ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_one,
                            ColorBlendAttrib.O_one)
PREMUL = ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_one,
                               ColorBlendAttrib.O_one_minus_incoming_alpha)


def fx_node(np_, mode, additive=True, hue_lock=False):
    """Configure a NodePath to render with the FX shader."""
    np_.setShader(shaders.get("fx"))
    np_.setShaderInput("u_fxMode", mode)
    np_.setShaderInput("u_hueLock", 1.0 if hue_lock else 0.0)
    np_.setAttrib(ADD if additive else PREMUL)
    np_.setTransparency(TransparencyAttrib.M_none)
    np_.setDepthWrite(False)
    np_.setTwoSided(True)
    np_.setBin("fixed", 8)
    np_.setLightOff(1)
    return np_


class _Pooled:
    __slots__ = ("np", "life", "max_life", "data")

    def __init__(self, np_):
        self.np = np_
        self.life = 0.0
        self.max_life = 1.0
        self.data = None


def _rand_dirs(n, spread=1.0, up_bias=0.0):
    v = np.random.normal(size=(n, 3)).astype(np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True) + 1e-6
    v[:, 2] += up_bias
    return v * spread


class Effects:
    def __init__(self, parent, lights, quality="high", audio=None):
        self.parent = parent
        self.root = parent.attachNewNode("fx")
        self.lights = lights
        self.audio = audio
        self.q = 1.0 if quality == "high" else 0.35
        cap = int(4000 * self.q) + 400
        self.sparks = ParticleSystem(self.root, cap, "add", "sparks")
        self.glow = ParticleSystem(self.root, int(cap * 0.6), "add", "glow")
        self.smoke = ParticleSystem(self.root, int(1400 * self.q) + 100, "alpha", "smoke")
        self.debris = ParticleSystem(self.root, int(900 * self.q) + 100, "debris", "debris")
        self.systems = [self.sparks, self.glow, self.smoke, self.debris]
        self.shake = 0.0

        # beams (lasers / tracers)
        self.beams = []
        proto = geom.beam_mesh()
        for _ in range(96):
            b = proto.copyTo(self.root)
            fx_node(b, 0)
            b.hide()
            self.beams.append(_Pooled(b))
        # shockwave rings
        mb = geom.MeshBuilder("ring")
        mb.ring(0.75, 1.0, (1, 1, 1, 1), 48)
        ring_proto = mb.node()
        self.rings = []
        for _ in range(12):
            r = ring_proto.copyTo(self.root)
            fx_node(r, 2)
            r.hide()
            self.rings.append(_Pooled(r))
        # flash billboards (muzzle / explosion cores)
        card_proto = geom.card(1, 1)
        self.flashes = []
        for _ in range(24):
            c = card_proto.copyTo(self.root)
            fx_node(c, 5)
            c.setBillboardPointEye()
            c.hide()
            self.flashes.append(_Pooled(c))
        # chunky debris (real little boxes)
        mb = geom.MeshBuilder("chunk")
        mb.cbox((0, 0, 0), (1, 1, 1), (0.08, 0.09, 0.1, 1))
        chunk_proto = mb.node()
        mb2 = geom.MeshBuilder("chunkglow")
        mb2.cbox((0, 0, 0.5), (1.05, 0.2, 0.2), (0.2, 1.0, 1.0, 1))
        chunk_glow = mb2.node()
        self.chunks = []
        n_chunks = 40 if self.q >= 1 else 12
        for _ in range(n_chunks):
            c = chunk_proto.copyTo(self.root)
            g = chunk_glow.copyTo(c)
            c.setShader(shaders.get("world"))
            c.setShaderInput("u_mat", Vec4(30, 0.8, 0.3, 0.0))
            g.setShaderInput("u_mat", Vec4(1, 0, 0, 2.5))
            c.hide()
            self.chunks.append(_Pooled(c))
        # persistent fire zones etc.
        self.fires = []
        self.t = 0.0

    # ------------------------------------------------------------------
    def _take(self, pool):
        best = min(pool, key=lambda p: p.life)
        best.np.show()
        return best

    def set_screen_height(self, h):
        for s in self.systems:
            s.set_screen_height(h)

    # ------------------------------------------------------------------ beams
    def beam(self, start, end, color=(0.2, 1.0, 1.0), width=0.08, life=0.1, intensity=3.0):
        """A short glowing laser pulse between two points."""
        start = Vec3(start)
        end = Vec3(end)
        d = end - start
        ln = d.length()
        if ln < 0.01:
            return
        b = self._take(self.beams)
        b.life = b.max_life = life
        b.data = (Vec4(color[0] * intensity, color[1] * intensity, color[2] * intensity, 1), width)
        b.np.setPos(start)
        b.np.lookAt(end)
        b.np.setScale(width, ln, width)
        b.np.setColorScale(b.data[0])

    def tracer(self, start, end, color=(0.6, 1.0, 1.0)):
        """Thin bullet tracer: a brief streak over the last part of the path."""
        start = Vec3(start)
        end = Vec3(end)
        d = end - start
        ln = d.length()
        if ln < 0.5:
            return
        seg = min(ln, 6.0 + ln * 0.3)
        s = end - d / ln * seg
        self.beam(s, end, color, width=0.035, life=0.06, intensity=2.2)

    # ------------------------------------------------------------------ bursts
    def sparks_at(self, pos, normal=(0, 0, 1), count=14, color=(0.4, 1.0, 1.0), speed=7.0):
        n = max(2, int(count * self.q))
        v = _rand_dirs(n, 1.0) + np.asarray(normal, np.float32) * 1.2
        v *= np.random.uniform(0.3, 1.0, (n, 1)).astype(np.float32) * speed
        c = (color[0] * 3, color[1] * 3, color[2] * 3, 1)
        self.sparks.emit(n, pos, v, (0.15, 0.4), (0.06, 0.1), 0.0, c,
                         (color[0], color[1] * 0.5, color[2] * 0.5, 0), drag=2.0, grav=14.0,
                         bounce=0.4)
        self.glow.emit(1, pos, (0, 0, 0), 0.08, 0.6, 0.2, (color[0] * 2, color[1] * 2,
                                                           color[2] * 2, 1), (0, 0, 0, 0))

    def impact(self, pos, normal, color=(0.3, 1.0, 1.0), strong=False):
        self.sparks_at(pos, normal, 18 if strong else 9, color, 9 if strong else 6)
        # tiny smoke puff + glowing scorch that fades
        self.smoke.emit(max(1, int(2 * self.q)), pos, np.asarray(normal, np.float32) * 0.6,
                        (0.5, 0.9), 0.15, 0.6, (0.12, 0.14, 0.16, 0.5), (0.05, 0.05, 0.06, 0))
        self.glow.emit(1, Vec3(pos) + Vec3(*normal) * 0.02, (0, 0, 0), 1.2, 0.18, 0.12,
                       (color[0], color[1], color[2], 0.8), (0.2, 0.05, 0.0, 0))

    def blood(self, pos, color=(0.2, 1.0, 1.0)):
        """Cyber 'blood': bright cyan data sparks."""
        n = max(3, int(12 * self.q))
        v = _rand_dirs(n, 1.0, 0.4) * 4.0
        self.sparks.emit(n, pos, v, (0.2, 0.5), (0.05, 0.09), 0.0,
                         (color[0] * 2.5, color[1] * 2.5, color[2] * 2.5, 1), (0, 0.2, 0.4, 0),
                         drag=1.5, grav=10.0, bounce=0.3)

    def muzzle(self, pos, forward, color=(0.4, 1.0, 1.0), size=0.5, light=True):
        f = self._take(self.flashes)
        f.life = f.max_life = 0.05
        f.np.setPos(pos)
        f.np.setScale(size)
        f.data = Vec4(color[0] * 4, color[1] * 4, color[2] * 4, 1)
        f.np.setColorScale(f.data)
        n = max(2, int(6 * self.q))
        v = (_rand_dirs(n, 1.5) + np.asarray(forward, np.float32) * 5.0)
        self.sparks.emit(n, pos, v, (0.04, 0.1), 0.04, 0.0, (color[0] * 3, color[1] * 3,
                                                            color[2] * 3, 1), (1, 0.5, 0.2, 0),
                         drag=6.0)
        if light:
            self.lights.flash(pos, color, 7.0, 0.06)

    def pulse_flash(self, pos, color, size, life=0.12):
        f = self._take(self.flashes)
        f.life = f.max_life = life
        f.np.setPos(pos)
        f.np.setScale(size)
        f.data = Vec4(color[0], color[1], color[2], 1)
        f.np.setColorScale(f.data)

    def shockwave(self, pos, radius, color=(0.3, 1.0, 1.0), life=0.45, up=True):
        r = self._take(self.rings)
        r.life = r.max_life = life
        r.data = (radius, Vec4(color[0] * 3, color[1] * 3, color[2] * 3, 1))
        r.np.setPos(pos)
        r.np.setHpr(0, 0, 0) if up else r.np.setHpr(random.uniform(0, 360), 90, 0)
        r.np.setScale(0.1)

    # ------------------------------------------------------------------ explosions
    def explosion(self, pos, radius=4.0, kind="explosive", big=True):
        """Over-the-top explosion.  kind: explosive | flash | fire | plasma | emp."""
        pos = Vec3(pos)
        q = self.q
        if kind == "flash":
            self.pulse_flash(pos, (12, 12, 12), radius * 3.0, 0.25)
            self.shockwave(pos + Vec3(0, 0, 0.1), radius * 2.2, (1, 1, 1), 0.35)
            self.sparks_at(pos, (0, 0, 1), 40, (1, 1, 1), 10)
            self.lights.flash(pos, (1, 1, 1), radius * 5, 0.35)
            return
        if kind == "emp":
            self.shockwave(pos + Vec3(0, 0, 0.8), radius, (0.3, 0.6, 1.0), 0.5)
            self.shockwave(pos + Vec3(0, 0, 0.8), radius * 0.8, (0.6, 0.9, 1.0), 0.35, up=False)
            self.sparks_at(pos + Vec3(0, 0, 1), (0, 0, 1), 60, (0.4, 0.7, 1.0), 12)
            self.lights.flash(pos, (0.4, 0.7, 1.0), radius * 2, 0.4)
            return
        if kind == "plasma":
            col = (0.3, 0.9, 1.0)
            hot = (1.2, 3.0, 3.5, 1)
        elif kind == "fire":
            col = (1.0, 0.45, 0.1)
            hot = (4.0, 1.6, 0.3, 1)
        else:
            col = (1.0, 0.6, 0.25)
            hot = (5.0, 3.0, 1.2, 1)
        s = radius / 4.0
        # core flash
        self.pulse_flash(pos, (hot[0] * 2, hot[1] * 2, hot[2] * 2), radius * 2.4, 0.18)
        self.lights.flash(pos, col, radius * 4.5, 0.5)
        # fireball: glowing blobs expanding
        n = int(40 * q * s) + 6
        v = _rand_dirs(n, 1.0, 0.3) * np.random.uniform(2, 7, (n, 1)).astype(np.float32) * s
        self.glow.emit(n, pos, v, (0.3, 0.7), (0.6 * s, 1.1 * s), (1.6 * s, 2.6 * s), hot,
                       (col[0] * 0.3, col[1] * 0.1, 0.05, 0), drag=4.0, grav=-2.0, pos_jitter=0.3)
        # sparks
        n = int(90 * q * s) + 10
        v = _rand_dirs(n, 1.0, 0.5) * np.random.uniform(6, 22, (n, 1)).astype(np.float32)
        self.sparks.emit(n, pos, v, (0.4, 1.3), (0.05, 0.1), 0.02, (4, 3, 1.5, 1),
                         (col[0], col[1] * 0.4, 0.1, 0), drag=1.2, grav=12.0, bounce=0.35)
        # smoke column
        n = int(26 * q * s) + 4
        v = _rand_dirs(n, 1.0, 1.2) * np.random.uniform(0.5, 3, (n, 1)).astype(np.float32)
        self.smoke.emit(n, pos, v, (1.6, 3.2), (0.8 * s, 1.4 * s), (3 * s, 5 * s),
                        (0.08, 0.09, 0.1, 0.75), (0.03, 0.03, 0.035, 0), drag=1.5, grav=-0.8,
                        pos_jitter=0.6 * s)
        # hot debris embers
        n = int(40 * q * s) + 6
        v = _rand_dirs(n, 1.0, 1.0) * np.random.uniform(4, 13, (n, 1)).astype(np.float32)
        self.debris.emit(n, pos, v, (1.0, 2.2), (0.08, 0.16), 0.05, (3, 1.6, 0.6, 1),
                         (0.4, 0.1, 0.05, 1), drag=0.3, grav=16.0, bounce=0.45)
        # chunks
        for _ in range(int(8 * (1 if q >= 1 else 0.4))):
            c = self._take(self.chunks)
            c.life = c.max_life = random.uniform(1.5, 2.6)
            c.np.setPos(pos + Vec3(random.uniform(-.3, .3), random.uniform(-.3, .3), 0.3))
            c.np.setScale(random.uniform(0.12, 0.3) * s)
            c.np.setHpr(random.uniform(0, 360), random.uniform(0, 360), 0)
            vel = Vec3(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(0.6, 1.6))
            vel.normalize()
            c.data = [vel * random.uniform(6, 14), Vec3(random.uniform(-500, 500),
                                                        random.uniform(-500, 500), 0)]
        # shockwaves
        self.shockwave(pos + Vec3(0, 0, 0.15), radius * 2.0, col, 0.45)
        self.shockwave(pos + Vec3(0, 0, 0.6), radius * 1.4, (1, 0.9, 0.7), 0.3, up=False)
        self.shake = max(self.shake, 0.6 * s)

    def fire_zone(self, pos, radius, duration):
        self.fires.append([Vec3(pos), radius, duration, duration])

    def ground_warning(self, pos, radius, color, t_frac):
        """Pulsing ring used by traps (call every frame while warning)."""
        n = 1 if random.random() < 0.5 else 0
        if n:
            a = random.uniform(0, math.tau)
            p = Vec3(pos) + Vec3(math.cos(a) * radius, math.sin(a) * radius, 0.05)
            self.glow.emit(1, p, (0, 0, 1.5), 0.4, 0.25, 0.1,
                           (color[0] * 3, color[1] * 3, color[2] * 3, 1), (0, 0, 0, 0))

    def trail(self, pos, color, size=0.25):
        self.glow.emit(1, pos, (0, 0, 0), 0.18, size, 0.02,
                       (color[0] * 2.5, color[1] * 2.5, color[2] * 2.5, 1), (0, 0, 0, 0))

    def pickup_burst(self, pos, color=(0.3, 1.0, 1.0)):
        n = max(4, int(24 * self.q))
        v = _rand_dirs(n, 1.0, 1.2) * 3.0
        self.sparks.emit(n, pos, v, (0.3, 0.7), 0.08, 0.0, (color[0] * 3, color[1] * 3,
                                                           color[2] * 3, 1), (0, 0, 0, 0),
                         drag=3.0, grav=-2.0)

    # ------------------------------------------------------------------ update
    def update(self, dt):
        self.t += dt
        for s in self.systems:
            s.update(dt)
        for b in self.beams:
            if b.life > 0:
                b.life -= dt
                if b.life <= 0:
                    b.np.hide()
                else:
                    k = b.life / b.max_life
                    c = b.data[0]
                    b.np.setColorScale(c[0] * k, c[1] * k, c[2] * k, 1)
                    w = b.data[1] * (0.5 + 0.5 * k)
                    b.np.setSx(w)
                    b.np.setSz(w)
        for r in self.rings:
            if r.life > 0:
                r.life -= dt
                if r.life <= 0:
                    r.np.hide()
                else:
                    k = 1.0 - r.life / r.max_life
                    ease = 1 - (1 - k) ** 3
                    r.np.setScale(max(0.05, r.data[0] * ease))
                    c = r.data[1]
                    f = (1 - k) ** 1.5
                    r.np.setColorScale(c[0] * f, c[1] * f, c[2] * f, 1)
        for f in self.flashes:
            if f.life > 0:
                f.life -= dt
                if f.life <= 0:
                    f.np.hide()
                else:
                    k = f.life / f.max_life
                    c = f.data
                    f.np.setColorScale(c[0] * k, c[1] * k, c[2] * k, 1)
        for c in self.chunks:
            if c.life > 0:
                c.life -= dt
                if c.life <= 0:
                    c.np.hide()
                    continue
                vel, spin = c.data
                vel.z -= 18 * dt
                p = c.np.getPos() + vel * dt
                if p.z < 0.05:
                    p.z = 0.05
                    vel.z = -vel.z * 0.35
                    vel.x *= 0.6
                    vel.y *= 0.6
                    spin *= 0.5
                c.np.setPos(p)
                c.np.setHpr(c.np.getHpr() + spin * dt)
                if c.life < 0.4:
                    c.np.setScale(c.np.getScale() * (1 - dt * 3))
        # fire zones
        alive = []
        for fz in self.fires:
            fz[2] -= dt
            if fz[2] > 0:
                alive.append(fz)
                pos, rad = fz[0], fz[1]
                n = max(1, int(8 * self.q))
                ang = np.random.uniform(0, math.tau, n)
                rr = np.sqrt(np.random.uniform(0, 1, n)) * rad
                p = np.stack([pos.x + np.cos(ang) * rr, pos.y + np.sin(ang) * rr,
                              np.full(n, 0.1)], 1).astype(np.float32)
                v = np.zeros((n, 3), np.float32)
                v[:, 2] = np.random.uniform(1.5, 3.5, n)
                self.glow.emit(n, p, v, (0.35, 0.8), (0.5, 0.9), 0.1, (3.5, 1.2, 0.2, 1),
                               (0.6, 0.05, 0.0, 0), drag=0.5, grav=-1.0)
                if random.random() < 0.3 * self.q:
                    self.smoke.emit(1, p[0] + np.array([0, 0, 1.0], np.float32), (0, 0, 1.5),
                                    (1.5, 2.5), 0.8, 2.5, (0.06, 0.05, 0.05, 0.5),
                                    (0.02, 0.02, 0.02, 0))
                if int(self.t * 20) % 6 == 0:
                    self.lights.flash(pos + Vec3(0, 0, 1), (1.0, 0.45, 0.1), rad * 2.5, 0.12)
        self.fires = alive
        self.shake = max(0.0, self.shake - dt * 2.5)

    def clear(self):
        for s in self.systems:
            s.clear()
        for pool in (self.beams, self.rings, self.flashes, self.chunks):
            for p in pool:
                p.life = 0
                p.np.hide()
        self.fires = []
