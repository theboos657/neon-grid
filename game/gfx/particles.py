"""numpy-driven GPU point-sprite particle systems.

Each system owns a fixed pool of particles stored in numpy arrays.  Every frame
the whole pool is integrated with vectorised math and uploaded as one vertex
buffer, so thousands of sparks cost roughly one draw call and ~0.2 ms of Python.
"""

import numpy as np
from panda3d.core import (ColorBlendAttrib, Geom, GeomNode, GeomPoints,
                          GeomVertexArrayFormat, GeomVertexData, GeomVertexFormat,
                          InternalName, NodePath, OmniBoundingVolume, ShaderAttrib,
                          TransparencyAttrib)

from . import shaders

_FORMAT = None


def _format():
    global _FORMAT
    if _FORMAT is None:
        arr = GeomVertexArrayFormat()
        arr.addColumn(InternalName.getVertex(), 3, Geom.NT_float32, Geom.C_point)
        arr.addColumn(InternalName.getColor(), 4, Geom.NT_float32, Geom.C_color)
        arr.addColumn(InternalName.make("size"), 1, Geom.NT_float32, Geom.C_other)
        _FORMAT = GeomVertexFormat.registerFormat(GeomVertexFormat(arr))
    return _FORMAT


class ParticleSystem:
    """mode: 'add' (glowing), 'alpha' (smoke), 'debris' (hard squares, additive)."""

    def __init__(self, parent, capacity=3000, mode="add", name="particles"):
        self.cap = capacity
        self.mode = mode
        n = capacity
        self.pos = np.zeros((n, 3), np.float32)
        self.vel = np.zeros((n, 3), np.float32)
        self.life = np.zeros(n, np.float32)       # remaining
        self.max_life = np.ones(n, np.float32)
        self.size0 = np.zeros(n, np.float32)
        self.size1 = np.zeros(n, np.float32)
        self.col0 = np.zeros((n, 4), np.float32)
        self.col1 = np.zeros((n, 4), np.float32)
        self.drag = np.zeros(n, np.float32)
        self.grav = np.zeros(n, np.float32)
        self.bounce = np.zeros(n, np.float32)
        self.cursor = 0
        self.out = np.zeros((n, 8), np.float32)
        self.active_count = 0

        self.vdata = GeomVertexData(name, _format(), Geom.UHStream)
        self.vdata.uncleanSetNumRows(n)
        self.vdata.modifyArrayHandle(0).copyDataFrom(self.out.tobytes())
        prim = GeomPoints(Geom.UHStatic)
        prim.addConsecutiveVertices(0, n)
        geom = Geom(self.vdata)
        geom.addPrimitive(prim)
        gn = GeomNode(name)
        gn.addGeom(geom)
        gn.setBounds(OmniBoundingVolume())
        gn.setFinal(True)
        self.np = NodePath(gn)
        self.np.reparentTo(parent)

        sh = ShaderAttrib.make(shaders.get("particle"))
        sh = sh.setFlag(ShaderAttrib.F_shader_point_size, True)
        self.np.setAttrib(sh)
        self.np.setShaderInput("u_blendMode", {"add": 0, "alpha": 1, "debris": 2}[mode])
        self.np.setShaderInput("u_screenH", 900.0)
        self.np.setDepthWrite(False)
        self.np.setLightOff(1)
        if mode == "alpha":
            self.np.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add,
                                                    ColorBlendAttrib.O_incoming_alpha,
                                                    ColorBlendAttrib.O_one_minus_incoming_alpha))
            self.np.setBin("fixed", 5)
        else:
            self.np.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add,
                                                    ColorBlendAttrib.O_one,
                                                    ColorBlendAttrib.O_one))
            self.np.setBin("fixed", 10)
        self.np.setTransparency(TransparencyAttrib.M_none)

    def set_screen_height(self, h):
        self.np.setShaderInput("u_screenH", float(h))

    # ------------------------------------------------------------------
    def emit(self, count, pos, vel, life, size0, size1, col0, col1, drag=0.0, grav=0.0,
             bounce=0.0, pos_jitter=0.0):
        """Emit ``count`` particles.  ``vel`` may be an (count, 3) array or a 3-tuple.
        life / sizes may be scalars or (lo, hi) tuples for random ranges."""
        if count <= 0:
            return
        count = min(count, self.cap)
        idx = (np.arange(count) + self.cursor) % self.cap
        self.cursor = (self.cursor + count) % self.cap

        def rng(v):
            if isinstance(v, tuple):
                return np.random.uniform(v[0], v[1], count).astype(np.float32)
            return np.full(count, v, np.float32)

        p = np.asarray(pos, np.float32).reshape(-1, 3)
        if p.shape[0] == 1:
            p = np.repeat(p, count, axis=0)
        if pos_jitter:
            p = p + np.random.uniform(-pos_jitter, pos_jitter, (count, 3)).astype(np.float32)
        self.pos[idx] = p
        v = np.asarray(vel, np.float32)
        self.vel[idx] = v if v.ndim == 2 else np.repeat(v.reshape(1, 3), count, axis=0)
        lf = rng(life)
        self.life[idx] = lf
        self.max_life[idx] = lf
        self.size0[idx] = rng(size0)
        self.size1[idx] = rng(size1)
        self.col0[idx] = np.asarray(col0, np.float32)
        self.col1[idx] = np.asarray(col1, np.float32)
        self.drag[idx] = drag
        self.grav[idx] = grav
        self.bounce[idx] = bounce

    def clear(self):
        self.life[:] = 0

    def update(self, dt, floor_z=0.0):
        alive = self.life > 0
        self.active_count = int(alive.sum())
        if self.active_count == 0 and not self._dirty_last:
            return
        self._dirty_last = self.active_count > 0
        self.life[alive] -= dt
        a = alive
        # integrate
        self.vel[a, 2] -= self.grav[a] * dt
        damp = np.exp(-self.drag[a] * dt)[:, None]
        self.vel[a] *= damp
        self.pos[a] += self.vel[a] * dt
        # bounce on the floor
        b = a & (self.bounce > 0) & (self.pos[:, 2] < floor_z)
        if b.any():
            self.pos[b, 2] = floor_z
            self.vel[b, 2] *= -self.bounce[b]
            self.vel[b, :2] *= 0.6
        k = np.clip(1.0 - self.life / self.max_life, 0.0, 1.0)
        out = self.out
        out[:, 0:3] = self.pos
        out[:, 3:7] = self.col0 + (self.col1 - self.col0) * k[:, None]
        size = self.size0 + (self.size1 - self.size0) * k
        out[:, 7] = np.where(self.life > 0, size, 0.0)
        self.vdata.modifyArrayHandle(0).copyDataFrom(out.tobytes())

    _dirty_last = True
