"""Light rig for the custom world shader + the day/night neon cycle.

The world shader supports up to 8 point lights.  Each frame we pick the static
arena lights closest to the camera and reserve a few slots for short-lived
dynamic lights (muzzle flashes, explosions).  Everything is pushed to the GPU
through PTA arrays, so updating a light is just an array write.
"""

import colorsys
import math

from panda3d.core import PTA_LVecBase4f, Vec3, Vec4


class DynamicLight:
    __slots__ = ("pos", "color", "radius", "life", "max_life")

    def __init__(self, pos, color, radius, life):
        self.pos = Vec3(pos)
        self.color = color
        self.radius = radius
        self.life = life
        self.max_life = life


class LightRig:
    def __init__(self, root, max_lights=8, dynamic_slots=3):
        self.root = root
        self.max_lights = max_lights
        self.dynamic_slots = dynamic_slots if max_lights > 4 else 1
        self.static = []      # (Vec3 pos, (r,g,b) base colour, radius, intensity)
        self.dynamic = []
        self.pos_arr = PTA_LVecBase4f.emptyArray(8)
        self.col_arr = PTA_LVecBase4f.emptyArray(8)
        self.cycle_time = 0.0
        self.cycle_period = 240.0
        self.hue = 0.0
        self.gain = 1.0
        self.flicker_seed = 0.0
        root.setShaderInput("u_lightPos", self.pos_arr)
        root.setShaderInput("u_lightCol", self.col_arr)
        root.setShaderInput("u_numLights", 0)
        root.setShaderInput("u_hue", 0.0)
        root.setShaderInput("u_neonGain", 1.0)
        root.setShaderInput("u_ambient", Vec3(0.05, 0.06, 0.07))
        root.setShaderInput("u_fog", Vec4(0.0, 0.015, 0.02, 0.018))
        root.setShaderInput("u_mirror", 0.0)
        root.setShaderInput("u_time", 0.0)
        root.setShaderInput("u_camPos", Vec3(0, 0, 0))
        root.setShaderInput("u_hueLock", 0.0)

    def add_static(self, pos, color=(0.2, 0.9, 1.0), radius=22.0, intensity=1.0):
        self.static.append((Vec3(*pos), color, radius, intensity))

    def flash(self, pos, color=(1.0, 0.7, 0.4), radius=10.0, life=0.12):
        if len(self.dynamic) >= 8:
            self.dynamic.pop(0)
        self.dynamic.append(DynamicLight(pos, color, radius, life))

    def set_cycle(self, t):
        self.cycle_time = t

    def update(self, dt, cam_pos, time_now):
        # --- day/night style neon cycle: hue drifts +/- ~12 degrees, gain breathes
        self.cycle_time += dt
        ph = (self.cycle_time / self.cycle_period) * math.tau
        self.hue = math.sin(ph) * 0.22 + math.sin(ph * 3.1) * 0.05       # radians
        self.gain = 1.0 + 0.16 * math.sin(ph + 1.3)
        amb = 0.045 + 0.02 * (0.5 + 0.5 * math.cos(ph))
        self.root.setShaderInput("u_hue", self.hue)
        self.root.setShaderInput("u_neonGain", self.gain)
        self.root.setShaderInput("u_ambient", Vec3(amb * 0.8, amb, amb * 1.15))
        self.root.setShaderInput("u_time", time_now)
        self.root.setShaderInput("u_camPos", cam_pos)

        # --- dynamic lights
        alive = []
        for d in self.dynamic:
            d.life -= dt
            if d.life > 0:
                alive.append(d)
        self.dynamic = alive
        dyn = sorted(self.dynamic, key=lambda d: -d.life / d.max_life)[:self.dynamic_slots]

        n_static = self.max_lights - len(dyn)
        ranked = sorted(self.static, key=lambda s: (s[0] - cam_pos).lengthSquared())[:n_static]
        hue_shift_rgb = self._hue_shift_fn()
        i = 0
        for (p, c, r, inten) in ranked:
            cc = hue_shift_rgb(c)
            g = inten * self.gain
            self.pos_arr[i] = Vec4(p.x, p.y, p.z, r)
            self.col_arr[i] = Vec4(cc[0] * g, cc[1] * g, cc[2] * g, 1)
            i += 1
        for d in dyn:
            k = d.life / d.max_life
            self.pos_arr[i] = Vec4(d.pos.x, d.pos.y, d.pos.z, d.radius)
            self.col_arr[i] = Vec4(d.color[0] * k * 3, d.color[1] * k * 3, d.color[2] * k * 3, 1)
            i += 1
        self.root.setShaderInput("u_numLights", i)

    def _hue_shift_fn(self):
        shift = self.hue / math.tau

        def f(c):
            h, l, s = colorsys.rgb_to_hls(*c)
            return colorsys.hls_to_rgb((h + shift) % 1.0, l, s)
        return f
