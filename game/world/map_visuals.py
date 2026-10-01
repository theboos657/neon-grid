"""Visual builders for the FOREST and BACKROOMS maps.

Same interface as ``ArenaVisuals`` (``floor``, ``mirror``, ``update(t)``,
``set_reflections``).  Collision comes from ``neon_shared.arena_layout``; these
classes only draw, batching everything static into a few meshes per material.
"""

import math
import random

from panda3d.core import TransparencyAttrib, Vec3, Vec4

from neon_shared import arena_layout as L

from ..gfx import geom, shaders
from ..gfx.effects import fx_node

# u_mat: x gloss, y spec, z rim, w emission
MAT_MATTE = Vec4(8.0, 0.05, 0.0, 0.0)
MAT_WOOD = Vec4(12.0, 0.10, 0.0, 0.0)
MAT_LEAF = Vec4(6.0, 0.04, 0.0, 0.0)
MAT_ROCK = Vec4(10.0, 0.08, 0.0, 0.0)
MAT_PAINT = Vec4(70.0, 0.7, 0.0, 0.0)
MAT_WALL = Vec4(10.0, 0.06, 0.0, 0.0)
MAT_EMIT = Vec4(1.0, 0.0, 0.0, 1.5)
MAT_EMIT_SOFT = Vec4(1.0, 0.0, 0.0, 0.8)
MAT_SKY = Vec4(1.0, 0.0, 0.0, 1.0)


# ---------------------------------------------------------------------------- mesh helpers
def cone(mb, c, r, h, color, seg=10):
    cx, cy, cz = c
    k = r / h
    for i in range(seg):
        a0 = math.tau * i / seg
        a1 = math.tau * (i + 1) / seg
        am = (a0 + a1) / 2
        n = Vec3(math.cos(am), math.sin(am), k)
        n.normalize()
        mb.tri((cx + math.cos(a0) * r, cy + math.sin(a0) * r, cz),
               (cx + math.cos(a1) * r, cy + math.sin(a1) * r, cz), (cx, cy, cz + h), color,
               (n.x, n.y, n.z))
        mb.tri((cx + math.cos(a1) * r, cy + math.sin(a1) * r, cz),
               (cx + math.cos(a0) * r, cy + math.sin(a0) * r, cz), (cx, cy, cz), color, (0, 0, -1))


def hcyl(mb, c, r, length, axis, color, seg=12, cap=None):
    """Horizontal cylinder along 'x' or 'y' centred on c."""
    cx, cy, cz = c
    h = length / 2

    def pt(a, s):
        u, v = math.cos(a) * r, math.sin(a) * r
        return (cx + s, cy + u, cz + v) if axis == "x" else (cx + u, cy + s, cz + v)

    for i in range(seg):
        a0 = math.tau * i / seg
        a1 = math.tau * (i + 1) / seg
        am = (a0 + a1) / 2
        n = (0, math.cos(am), math.sin(am)) if axis == "x" else (math.cos(am), 0, math.sin(am))
        mb.quad(pt(a0, -h), pt(a1, -h), pt(a1, h), pt(a0, h), color, n,
                ((0, i / seg), (0, (i + 1) / seg), (length, (i + 1) / seg), (length, i / seg)))
        cc = cap or color
        for s in (-h, h):
            ctr = (cx + s, cy, cz) if axis == "x" else (cx, cy + s, cz)
            nn = ((1 if s > 0 else -1, 0, 0) if axis == "x" else (0, 1 if s > 0 else -1, 0))
            mb.tri(pt(a0, s), pt(a1, s), ctr, cc, nn)


def blob(mb, c, radii, color, seed, rings=6, seg=10, jitter=0.16):
    """Lumpy ellipsoid (rocks, bushes, duck bodies)."""
    cx, cy, cz = c
    rx, ry, rz = radii

    def rad(t, p):
        return 1.0 + jitter * (math.sin(p * 3 + seed * 17) * math.cos(t * 2 + seed * 5) +
                               0.5 * math.sin(p * 5 + t * 3 + seed * 11))

    def pt(t, p):
        k = rad(t, p)
        d = (math.cos(t) * math.cos(p), math.cos(t) * math.sin(p), math.sin(t))
        return (cx + d[0] * rx * k, cy + d[1] * ry * k, cz + d[2] * rz * k), d

    for i in range(rings):
        t0 = math.pi * i / rings - math.pi / 2
        t1 = math.pi * (i + 1) / rings - math.pi / 2
        for j in range(seg):
            p0 = math.tau * j / seg
            p1 = math.tau * (j + 1) / seg
            (a, na), (b, nb), (cc, nc), (d, nd) = pt(t0, p0), pt(t0, p1), pt(t1, p1), pt(t1, p0)
            base = mb.count
            for v, n, uv in ((a, na, (p0, t0)), (b, nb, (p1, t0)), (cc, nc, (p1, t1)),
                             (d, nd, (p0, t1))):
                mb.vw.addData3(*v)
                mb.nw.addData3(*n)
                mb.cw.addData4(*color)
                mb.tw.addData2(uv[0] * 0.6, uv[1] * 0.6)
            mb.tris.addVertices(base, base + 1, base + 2)
            mb.tris.addVertices(base, base + 2, base + 3)
            mb.count += 4


def disc(mb, c, r, color, seg=14):
    cx, cy, cz = c
    for i in range(seg):
        a0 = math.tau * i / seg
        a1 = math.tau * (i + 1) / seg
        mb.tri((cx + math.cos(a0) * r, cy + math.sin(a0) * r, cz),
               (cx + math.cos(a1) * r, cy + math.sin(a1) * r, cz), (cx, cy, cz), color, (0, 0, 1))


def make_sky(parent, tex, top, hor, R=190.0):
    """Gradient sky / water dome around the map (unlit, no fog)."""
    def mix(a, b, k):
        return tuple(x + (y - x) * k for x, y in zip(a, b))
    mb = geom.MeshBuilder("sky")
    rings, seg = 10, 24
    for i in range(rings):
        t0 = -0.25 + (math.pi / 2 + 0.25) * i / rings
        t1 = -0.25 + (math.pi / 2 + 0.25) * (i + 1) / rings
        for j in range(seg):
            p0 = math.tau * j / seg
            p1 = math.tau * (j + 1) / seg
            base = mb.count
            for (t, p) in ((t0, p0), (t0, p1), (t1, p1), (t1, p0)):
                col = mix(hor, top, max(0.0, math.sin(t)) ** 0.6)
                mb.vw.addData3(R * math.cos(t) * math.cos(p), R * math.cos(t) * math.sin(p),
                               R * math.sin(t))
                mb.nw.addData3(0, 0, -1)
                mb.cw.addData4(col[0], col[1], col[2], 1)
                mb.tw.addData2(0.5, 0.5)
            mb.tris.addVertices(base, base + 1, base + 2)
            mb.tris.addVertices(base, base + 2, base + 3)
            mb.count += 4
    sky = mb.node()
    sky.reparentTo(parent)
    sky.setShader(shaders.get("world"))
    sky.setTexture(tex.white)
    sky.setTwoSided(True)
    sky.setShaderInput("u_mat", MAT_SKY)
    sky.setShaderInput("u_ambient", Vec3(0, 0, 0))
    sky.setShaderInput("u_sunCol", Vec3(0, 0, 0))
    sky.setShaderInput("u_numLights", 0)
    sky.setShaderInput("u_fog", Vec4(0, 0, 0, 0))
    sky.setBin("background", 1)
    sky.setDepthWrite(False)
    return sky


def ground(parent, tex, half, color, uv=0.25, n=22, jitter=0.12, seed=5, mat=None):
    """Large tinted ground plane (vertex colours vary a little for natural variation)."""
    mb = geom.MeshBuilder("ground")
    step = 2 * half / n
    rng = random.Random(seed)
    tint = {}
    for i in range(n + 1):
        for j in range(n + 1):
            k = rng.uniform(1 - jitter, 1 + jitter * 0.6)
            tint[(i, j)] = (min(1, color[0] * k), min(1, color[1] * k), min(1, color[2] * k), 1)
    for i in range(n):
        for j in range(n):
            x0, y0 = -half + i * step, -half + j * step
            x1, y1 = x0 + step, y0 + step
            base = mb.count
            for (x, y, key) in ((x0, y0, (i, j)), (x1, y0, (i + 1, j)), (x1, y1, (i + 1, j + 1)),
                                (x0, y1, (i, j + 1))):
                mb.vw.addData3(x, y, 0)
                mb.nw.addData3(0, 0, 1)
                mb.cw.addData4(*tint[key])
                mb.tw.addData2(x * uv, y * uv)
            mb.tris.addVertices(base, base + 1, base + 2)
            mb.tris.addVertices(base, base + 2, base + 3)
            mb.count += 4
    return _node(mb, parent, tex, mat or MAT_MATTE, two_sided=False)


def vdisc(mb, c, r, facing, color, seg=14):
    """Vertical disc (door, porthole, window) facing +-x or +-y."""
    cx, cy, cz = c
    ax, sgn = facing[0], (1 if facing[1] == "+" else -1)
    n = (sgn, 0, 0) if ax == "x" else (0, sgn, 0)
    for i in range(seg):
        a0 = math.tau * i / seg
        a1 = math.tau * (i + 1) / seg
        def pt(a):
            u, v = math.cos(a) * r, math.sin(a) * r
            return (cx, cy + u, cz + v) if ax == "x" else (cx + u, cy, cz + v)
        mb.tri(pt(a0), pt(a1), (cx, cy, cz), color, n)


class Xf:
    """Place local prop geometry (x right, y forward, z up) with a 90-degree-step heading."""

    def __init__(self, x, y, hdg, z=0.0):
        self.x, self.y, self.z = x, y, z
        self.q = int(round(hdg / 90.0)) % 4

    def p(self, lx, ly, lz=0.0):
        x, y = lx, ly
        for _ in range(self.q):
            x, y = -y, x
        return (self.x + x, self.y + y, self.z + lz)

    def axis(self, a):
        return a if self.q % 2 == 0 else ("y" if a == "x" else "x")

    def box(self, mb, mn, mx, color, uv=0.5):
        a = self.p(mn[0], mn[1], mn[2])
        b = self.p(mx[0], mx[1], mx[2])
        mb.box((min(a[0], b[0]), min(a[1], b[1]), a[2]), (max(a[0], b[0]), max(a[1], b[1]), b[2]),
               color, uv_scale=uv)

    def cyl(self, mb, lc, r, h, color, seg=12):
        mb.cylinder(self.p(*lc), r, h, color, seg)

    def hcyl(self, mb, lc, r, length, axis, color, seg=10, cap=None):
        hcyl(mb, self.p(*lc), r, length, self.axis(axis), color, seg, cap)


def _node(mb, parent, tex, mat, two_sided=True):
    n = mb.node()
    n.reparentTo(parent)
    n.setTexture(tex)
    n.setShaderInput("u_mat", mat)
    if two_sided:
        n.setTwoSided(True)
    return n


def _shade(c, k):
    return (min(1.0, c[0] * k), min(1.0, c[1] * k), min(1.0, c[2] * k), 1)


class _MapVisuals:
    def __init__(self, render, world_root, textures, lights, quality="high", font=None,
                 reflections=True):
        self.render = render
        self.root = world_root
        self.tex = textures
        self.lights = lights
        self.quality = quality
        self.theme = L.THEME
        self.static_np = world_root.attachNewNode("map_static")
        # nodes outside the lit world (sky etc.); removed by Match.cleanup
        self.floor = render.attachNewNode("map_extra")
        self.mirror = None
        self.anim = []           # (light index, callable(t) -> intensity) for flicker
        lights.set_theme(self.theme)

    def set_reflections(self, on):
        pass

    def _light(self, pos, color, radius, intensity):
        self.lights.add_static(pos, color, radius, intensity)
        return len(self.lights.static) - 1

    def _set_light(self, idx, intensity=None, color=None):
        p, c, r, i = self.lights.static[idx]
        self.lights.static[idx] = (p, color or c, r, i if intensity is None else intensity)

    def update(self, t):
        pass


# ============================================================================ FOREST
class ForestVisuals(_MapVisuals):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.rng = random.Random(77)
        self._build_ground()
        self._build_trees()
        self._build_rocks_logs()
        self._build_cabin()
        self._build_towers()
        self._build_fence()
        self._build_campfire()
        self._build_sky()
        self._build_fireflies()
        self._sky_k = -1.0

    # ------------------------------------------------------------------ ground
    def _build_ground(self):
        mb = geom.MeshBuilder("ground")
        H = L.HALF + 44
        n = 22
        step = 2 * H / n
        rng = random.Random(5)
        tint = {}
        for i in range(n + 1):
            for j in range(n + 1):
                k = rng.uniform(0.82, 1.1)
                tint[(i, j)] = (k * rng.uniform(0.95, 1.05), k, k * rng.uniform(0.9, 1.0), 1)
        s = 0.25
        for i in range(n):
            for j in range(n):
                x0 = -H + i * step
                y0 = -H + j * step
                x1, y1 = x0 + step, y0 + step
                base = mb.count
                for (x, y, key) in ((x0, y0, (i, j)), (x1, y0, (i + 1, j)), (x1, y1, (i + 1, j + 1)),
                                    (x0, y1, (i, j + 1))):
                    mb.vw.addData3(x, y, 0)
                    mb.nw.addData3(0, 0, 1)
                    mb.cw.addData4(*tint[key])
                    mb.tw.addData2(x * s, y * s)
                mb.tris.addVertices(base, base + 1, base + 2)
                mb.tris.addVertices(base, base + 2, base + 3)
                mb.count += 4
        _node(mb, self.static_np, self.tex.get("grass"), MAT_LEAF, two_sided=False)
        # worn dirt around the cabin, the campfire and the towers
        mb = geom.MeshBuilder("dirt")
        dirt = (0.55, 0.42, 0.28, 1)
        camp = self.theme_decor("campfire")[0]
        spots = [(0, 0, 8.0), (camp["x"], camp["y"], 3.2)]
        for d in self.theme_decor("tower"):
            spots.append((d["x"], d["y"], 4.2))
        for (x, y, r) in spots:
            disc(mb, (x, y, 0.02), r, dirt, 18)
        n = _node(mb, self.static_np, self.tex.get("grass"), MAT_MATTE)
        n.setDepthOffset(2)

    def theme_decor(self, kind):
        return [d for d in L.DECOR if d["k"] == kind]

    # ------------------------------------------------------------------ trees / bushes
    def _build_trees(self):
        trunks = geom.MeshBuilder("trunks")
        leaves = geom.MeshBuilder("leaves")
        far = geom.MeshBuilder("far_leaves")
        low = self.quality != "high"
        for d in L.DECOR:
            k = d["k"]
            if k not in ("pine", "oak", "bush"):
                continue
            x, y = d["x"], d["y"]
            s = d.get("s", 1.0)
            if k == "bush":
                g = 0.75 + d["seed"] * 0.3
                col = (0.16 * g, 0.36 * g, 0.12 * g, 1)
                rng = random.Random(d["seed"])
                for i in range(2 if low else 4):
                    ox, oy = rng.uniform(-0.6, 0.6) * s, rng.uniform(-0.6, 0.6) * s
                    r = rng.uniform(0.55, 0.85) * s
                    blob(leaves, (x + ox, y + oy, r * 0.55), (r, r, r * 0.8), _shade(col, rng.uniform(0.85, 1.15)),
                         rng.random(), 4 if low else 5, 7 if low else 9, 0.2)
                continue
            r = d.get("r", 0.3)
            is_far = d.get("far", False)
            mb = far if is_far else leaves
            trunk_col = (0.42, 0.32, 0.24, 1)
            if k == "pine":
                h = 7.5 * s
                trunks.cylinder((x, y, 0), r, h * 0.55, trunk_col, 6 if is_far else 8, caps=False)
                g = 0.8 + (d.get("h", 0) % 40) / 100
                col = (0.10 * g, 0.30 * g, 0.16 * g, 1)
                layers = 3 if (low or is_far) else 4
                for i in range(layers):
                    f = i / layers
                    rr = (2.3 - 1.5 * f) * s
                    cone(mb, (x, y, h * (0.3 + 0.45 * f)), rr, h * 0.42 * (1.0 - 0.25 * f),
                         _shade(col, 1.0 + 0.12 * i), 7 if is_far else 10)
            else:
                h = 6.0 * s
                trunks.cylinder((x, y, 0), r * 1.2, h * 0.7, (0.38, 0.30, 0.23, 1),
                                6 if is_far else 8, caps=False)
                g = 0.8 + (d.get("h", 0) % 50) / 120
                col = (0.22 * g, 0.42 * g, 0.14 * g, 1)
                rng = random.Random(int(d.get("h", 0) * 100))
                n = 3 if (low or is_far) else 5
                for i in range(n):
                    a = math.tau * i / n + rng.random()
                    off = 1.1 * s if i else 0.0
                    rr = rng.uniform(1.5, 2.1) * s
                    blob(mb, (x + math.cos(a) * off, y + math.sin(a) * off,
                              h * 0.78 + rng.uniform(-0.3, 0.8) * s), (rr, rr, rr * 0.8),
                         _shade(col, rng.uniform(0.85, 1.15)), rng.random(),
                         4 if is_far else 5, 7 if is_far else 9, 0.18)
        _node(trunks, self.static_np, self.tex.get("bark"), MAT_WOOD)
        _node(leaves, self.static_np, self.tex.get("foliage"), MAT_LEAF)
        _node(far, self.static_np, self.tex.get("foliage"), MAT_LEAF)

    # ------------------------------------------------------------------ rocks & logs
    def _build_rocks_logs(self):
        rocks = geom.MeshBuilder("rocks")
        logs = geom.MeshBuilder("logs")
        for d in L.DECOR:
            if d["k"] == "rock":
                sx, sy, sz = d["sx"], d["sy"], d["sz"]
                g = 0.55 + d["seed"] * 0.15
                blob(rocks, (d["x"], d["y"], sz * 0.35), (sx * 0.62, sy * 0.62, sz * 0.72),
                     (g, g * 0.98, g * 0.93, 1), d["seed"], 7, 11, 0.14)
                # moss on top
                blob(rocks, (d["x"], d["y"], sz * 0.62), (sx * 0.45, sy * 0.45, sz * 0.4),
                     (0.3, 0.42, 0.2, 1), d["seed"] + 0.3, 5, 9, 0.2)
            elif d["k"] == "log":
                hcyl(logs, (d["x"], d["y"], 0.45), 0.45, d["len"], d["axis"],
                     (0.45, 0.34, 0.24, 1), 12, cap=(0.75, 0.6, 0.42, 1))
        _node(rocks, self.static_np, self.tex.get("rock"), MAT_ROCK)
        _node(logs, self.static_np, self.tex.get("bark"), MAT_WOOD)

    # ------------------------------------------------------------------ cabin
    def _build_cabin(self):
        wood = geom.MeshBuilder("cabin")
        wall_col = (0.62, 0.45, 0.3, 1)
        dark = (0.38, 0.27, 0.18, 1)
        for b in L.STATIC_BOXES:
            kind = b[6]
            if kind in ("cabin", "roof", "rail", "table", "crate", "shelf", "post", "deck"):
                col = {"roof": (0.5, 0.38, 0.27, 1), "rail": dark, "post": dark,
                       "deck": (0.55, 0.42, 0.3, 1), "crate": (0.6, 0.48, 0.3, 1)}.get(kind, wall_col)
                wood.box(b[:3], b[3:6], col, uv_scale=0.5)
        # corner logs, door & window frames, roof edge
        for sx in (-1, 1):
            for sy in (-1, 1):
                wood.cylinder((sx * 5.0, sy * 3.5, 0), 0.28, 3.3, dark, 8)
        for sy in (-3.5, 3.5):
            wood.box((-1.05, sy - 0.25, 0), (-0.9, sy + 0.25, 2.4), dark)
            wood.box((0.9, sy - 0.25, 0), (1.05, sy + 0.25, 2.4), dark)
            wood.box((-1.05, sy - 0.25, 2.3), (1.05, sy + 0.25, 2.45), dark)
        for sx in (-5.0, 5.0):
            wood.box((sx - 0.25, -1.1, 1.0), (sx + 0.25, 1.1, 1.1), dark)
            wood.box((sx - 0.25, -1.1, 2.0), (sx + 0.25, 1.1, 2.1), dark)
        # chimney-free roof deck planks (visual seams)
        for i in range(-5, 6):
            wood.box((i - 0.02, -3.9, 3.3), (i + 0.02, 3.9, 3.31), dark)
        _node(wood, self.static_np, self.tex.get("wood"), MAT_WOOD)
        # warm lanterns by both doors
        em = geom.MeshBuilder("lanterns")
        for sy in (-3.8, 3.8):
            em.cbox((1.4, sy, 2.2), (0.18, 0.18, 0.28), (1.0, 0.7, 0.35, 1))
            self._light((1.4, sy * 1.1, 2.3), (1.0, 0.62, 0.3), 9.0, 0.9)
        # lamp inside
        em.cbox((0, 0, 2.85), (0.3, 0.3, 0.15), (1.0, 0.8, 0.5, 1))
        self._light((0, 0, 2.6), (1.0, 0.72, 0.42), 8.0, 1.0)
        _node(em, self.static_np, self.tex.white, MAT_EMIT)

    # ------------------------------------------------------------------ towers
    def _build_towers(self):
        mb = geom.MeshBuilder("towers")
        dark = (0.4, 0.3, 0.21, 1)
        em = geom.MeshBuilder("tower_lamps")
        for d in self.theme_decor("tower"):
            x, y = d["x"], d["y"]
            # cross braces between the posts
            for sx in (-1, 1):
                mb.box((x + sx * 1.9 - 0.06, y - 1.9, 1.2), (x + sx * 1.9 + 0.06, y + 1.9, 1.35), dark)
                mb.box((x - 1.9, y + sx * 1.9 - 0.06, 2.6), (x + 1.9, y + sx * 1.9 + 0.06, 2.75), dark)
            # ladder rungs on the outside post pair
            ox = x + (2.15 if x > 0 else -2.15)
            for k in range(1, 9):
                mb.box((ox - 0.04, y - 0.4, k * 0.5), (ox + 0.04, y + 0.4, k * 0.5 + 0.06), dark)
            em.cbox((x, y, L.CATWALK_Z + 1.9), (0.2, 0.2, 0.3), (1.0, 0.75, 0.4, 1))
            mb.cbox((x, y, L.CATWALK_Z + 1.0), (0.1, 0.1, 1.8), dark)
            self._light((x, y, L.CATWALK_Z + 1.7), (1.0, 0.7, 0.4), 9.0, 0.8)
        _node(mb, self.static_np, self.tex.get("wood"), MAT_WOOD)
        _node(em, self.static_np, self.tex.white, MAT_EMIT)

    # ------------------------------------------------------------------ fence
    def _build_fence(self):
        mb = geom.MeshBuilder("fence")
        col = (0.5, 0.39, 0.28, 1)
        H = L.HALF - 0.15
        n = 16
        for i in range(n + 1):
            a = -H + 2 * H * i / n
            for (x, y) in ((a, H), (a, -H), (H, a), (-H, a)):
                mb.cbox((x, y, 0.6), (0.16, 0.16, 1.2), col)
        for z in (0.45, 0.95):
            mb.box((-H, H - 0.04, z), (H, H + 0.04, z + 0.1), col)
            mb.box((-H, -H - 0.04, z), (H, -H + 0.04, z + 0.1), col)
            mb.box((H - 0.04, -H, z), (H + 0.04, H, z + 0.1), col)
            mb.box((-H - 0.04, -H, z), (-H + 0.04, H, z + 0.1), col)
        _node(mb, self.static_np, self.tex.get("wood"), MAT_WOOD)

    # ------------------------------------------------------------------ campfire
    def _build_campfire(self):
        d = self.theme_decor("campfire")[0]
        x, y = d["x"], d["y"]
        mb = geom.MeshBuilder("campfire")
        for i in range(9):
            a = math.tau * i / 9
            blob(mb, (x + math.cos(a) * 0.6, y + math.sin(a) * 0.6, 0.1), (0.2, 0.2, 0.16),
                 (0.45, 0.44, 0.42, 1), i * 0.37, 4, 6, 0.2)
        hcyl(mb, (x, y, 0.18), 0.1, 1.0, "x", (0.3, 0.2, 0.12, 1), 6)
        hcyl(mb, (x, y, 0.28), 0.1, 1.0, "y", (0.3, 0.2, 0.12, 1), 6)
        _node(mb, self.static_np, self.tex.get("rock"), MAT_ROCK)
        # flames: soft additive billboards
        self.flames = []
        for i in range(3):
            c = geom.card(0.9, 1.3)
            c.reparentTo(self.root)
            c.setPos(x, y, 0.75)
            c.setBillboardPointEye()
            fx_node(c, 5, hue_lock=True)
            c.setColorScale(1.6, 0.55 + 0.2 * i, 0.12, 1)
            self.flames.append(c)
        self.fire_light = self._light((x, y, 1.2), (1.0, 0.5, 0.18), 11.0, 1.4)

    # ------------------------------------------------------------------ sky
    def _build_sky(self):
        self.sky = None
        self.sun = geom.card(1, 1)
        self.sun.reparentTo(self.floor)
        d = Vec3(*self.theme["sun_dir"])
        d.normalize()
        self.sun_dir = d
        self.sun.setPos(d * 170)
        self.sun.setScale(26)
        self.sun.setBillboardPointEye()
        fx_node(self.sun, 5, hue_lock=True)
        self.sun.setBin("background", 2)
        self.sun.setDepthWrite(False)
        self.clouds = []
        rng = random.Random(9)
        for i in range(9 if self.quality == "high" else 4):
            c = geom.card(1, 1)
            c.reparentTo(self.floor)
            c.setP(-90)
            a = rng.uniform(0, math.tau)
            dist = rng.uniform(20, 120)
            c.setPos(math.cos(a) * dist, math.sin(a) * dist, rng.uniform(55, 75))
            c.setScale(rng.uniform(40, 70), 1, rng.uniform(18, 30))
            fx_node(c, 5, additive=False, hue_lock=True)
            c.setDepthWrite(False)
            c.setBin("background", 3)
            self.clouds.append((c, rng.uniform(0.6, 1.2)))
        self._rebuild_sky(0.0)

    def _rebuild_sky(self, k):
        th = self.theme
        mix = self.lights._mix
        top = mix(th["sky_top"], th["dusk_sky_top"], k)
        hor = mix(th["sky_horizon"], th["dusk_sky_horizon"], k)
        if self.sky is not None:
            self.sky.removeNode()
        sky = make_sky(self.floor, self.tex, top, hor)
        self.sky = sky
        sun_col = mix((1.6, 1.5, 1.2), (2.2, 0.9, 0.4), k)
        self.sun.setColorScale(sun_col[0], sun_col[1], sun_col[2], 1)
        cloud = mix((0.95, 0.97, 1.0), (0.95, 0.62, 0.52), k)
        for c, _ in self.clouds:
            c.setColorScale(cloud[0] * 0.55, cloud[1] * 0.55, cloud[2] * 0.55, 0.55)

    def _build_fireflies(self):
        self.flies = []
        if self.quality != "high":
            return
        rng = random.Random(3)
        for i in range(40):
            c = geom.card(0.09, 0.09)
            c.reparentTo(self.root)
            c.setBillboardPointEye()
            fx_node(c, 5, hue_lock=True)
            base = (rng.uniform(-28, 28), rng.uniform(-28, 28), rng.uniform(0.5, 2.5))
            self.flies.append((c, base, rng.uniform(0, 10)))

    # ------------------------------------------------------------------ per frame
    def update(self, t):
        k = self.lights.dusk
        if abs(k - self._sky_k) > 0.02:
            self._sky_k = k
            self._rebuild_sky(k)
        for c, sp in self.clouds:
            c.setX(((c.getX() + 150 + sp * 0.02) % 300) - 150)
        fl = 0.8 + 0.2 * math.sin(t * 13.0) + 0.12 * math.sin(t * 31.0 + 1.3)
        for i, c in enumerate(self.flames):
            c.setScale(0.9 + 0.25 * math.sin(t * (9 + i * 3) + i), 1,
                       1.0 + 0.3 * math.sin(t * (11 + i * 2) + i * 2))
        self._set_light(self.fire_light, 1.3 * fl)
        a = max(0.0, (k - 0.35) * 2.0)
        for c, (bx, by, bz), ph in self.flies:
            if a <= 0:
                c.hide()
                continue
            c.show()
            c.setPos(bx + math.sin(t * 0.4 + ph) * 1.5, by + math.cos(t * 0.33 + ph) * 1.5,
                     bz + math.sin(t * 0.9 + ph * 2) * 0.4)
            g = a * (0.5 + 0.5 * math.sin(t * 3 + ph * 5))
            c.setColorScale(1.2 * g, 1.8 * g, 0.4 * g, 1)


# ============================================================================ BACKROOMS
WALLPAPER = (0.86, 0.77, 0.42, 1)
CARPET = (0.64, 0.55, 0.33, 1)
CEILING = (0.8, 0.77, 0.62, 1)


class BackroomsVisuals(_MapVisuals):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.flicker = []        # (node, light idx, phase)
        self.police = []         # (red node, blue node, light idx, phase)
        self.tvs = []
        self._build_shell()
        self._build_panels()
        self._build_props()

    # ------------------------------------------------------------------ floor, walls, ceiling
    def _build_shell(self):
        H = L.HALF
        mb = geom.MeshBuilder("carpet")
        n = 8
        step = 2 * H / n
        s = 0.25
        for i in range(n):
            for j in range(n):
                x0, y0 = -H + i * step, -H + j * step
                x1, y1 = x0 + step, y0 + step
                mb.quad((x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0), CARPET, (0, 0, 1),
                        ((x0 * s, y0 * s), (x1 * s, y0 * s), (x1 * s, y1 * s), (x0 * s, y1 * s)))
        _node(mb, self.static_np, self.tex.get("carpet"), MAT_MATTE, two_sided=False)
        mb = geom.MeshBuilder("ceiling")
        z = L.CEILING_Z
        s = 1 / 1.2
        for i in range(n):
            for j in range(n):
                x0, y0 = -H + i * step, -H + j * step
                x1, y1 = x0 + step, y0 + step
                mb.quad((x0, y1, z), (x1, y1, z), (x1, y0, z), (x0, y0, z), CEILING, (0, 0, -1),
                        ((x0 * s, y1 * s), (x1 * s, y1 * s), (x1 * s, y0 * s), (x0 * s, y0 * s)))
        _node(mb, self.static_np, self.tex.get("ceiling"), MAT_MATTE, two_sided=False)
        walls = geom.MeshBuilder("walls")
        trim = geom.MeshBuilder("baseboards")
        tcol = (0.42, 0.33, 0.2, 1)
        for b in L.STATIC_BOXES:
            kind = b[6]
            if kind in ("wall", "wall_in", "pillar"):
                x0, y0, z0, x1, y1, z1 = b[:6]
                walls.box((x0, y0, z0), (x1, y1, min(z1, L.CEILING_Z)), WALLPAPER, uv_scale=0.25)
                if z0 < 0.1:
                    e = 0.025
                    trim.box((x0 - e, y0 - e, 0), (x1 + e, y1 + e, 0.13), tcol, uv_scale=1.0,
                             faces="s")
        _node(walls, self.static_np, self.tex.get("wallpaper"), MAT_WALL)
        _node(trim, self.static_np, self.tex.get("wood"), MAT_WOOD)

    # ------------------------------------------------------------------ fluorescent panels
    def _build_panels(self):
        steady = geom.MeshBuilder("panels")
        dead = geom.MeshBuilder("dead_panels")
        z = L.CEILING_Z
        for d in L.DECOR:
            if d["k"] != "panel":
                continue
            x, y = d["x"], d["y"]
            for (ox, oy) in ((-1.6, 0.0), (1.6, 0.0)):
                mn = (x + ox - 0.62, y + oy - 0.32, z - 0.03)
                mx = (x + ox + 0.62, y + oy + 0.32, z - 0.005)
                if d["state"] == "off":
                    dead.box(mn, mx, (0.55, 0.55, 0.5, 1), faces="b")
                elif d["state"] == "flicker":
                    mb = geom.MeshBuilder("flicker")
                    mb.box(mn, mx, (1.0, 0.95, 0.78, 1), faces="b")
                    node = _node(mb, self.static_np, self.tex.white, MAT_EMIT)
                    idx = self._light((x + ox, y, z - 0.4), (1.0, 0.9, 0.62), 8.0, 0.75)
                    self.flicker.append((node, idx, d["v"] * 100))
                else:
                    steady.box(mn, mx, (1.0, 0.95, 0.78, 1), faces="b")
                    if ox < 0:
                        self._light((x, y, z - 0.4), (1.0, 0.9, 0.62), 9.5, 0.85)
        _node(steady, self.static_np, self.tex.white, MAT_EMIT)
        _node(dead, self.static_np, self.tex.white, MAT_MATTE)

    # ------------------------------------------------------------------ props
    def _build_props(self):
        self.mb = {
            "matte": geom.MeshBuilder("props_matte"),
            "wood": geom.MeshBuilder("props_wood"),
            "paint": geom.MeshBuilder("props_paint"),
            "emit": geom.MeshBuilder("props_emit"),
            "decal": geom.MeshBuilder("decals"),
        }
        for d in L.DECOR:
            fn = getattr(self, "_p_" + d["k"], None)
            if fn is not None:
                fn(Xf(d["x"], d["y"], d.get("h", 0)), d)
        _node(self.mb["matte"], self.static_np, self.tex.white, MAT_MATTE)
        _node(self.mb["wood"], self.static_np, self.tex.get("wood"), MAT_WOOD)
        _node(self.mb["paint"], self.static_np, self.tex.white, MAT_PAINT)
        _node(self.mb["emit"], self.static_np, self.tex.white, MAT_EMIT_SOFT)
        dec = _node(self.mb["decal"], self.static_np, self.tex.white, MAT_MATTE)
        dec.setDepthOffset(2)

    # individual props (local coords: x right, y forward, z up)
    def _p_police(self, X, d):
        m, p = self.mb["matte"], self.mb["paint"]
        black, white = (0.04, 0.04, 0.05, 1), (0.9, 0.9, 0.92, 1)
        X.box(p, (1.25, -0.95, 0.3), (2.35, 0.95, 0.95), black)
        X.box(p, (-1.25, -0.95, 0.3), (1.25, 0.95, 0.98), white)
        X.box(p, (-2.35, -0.95, 0.3), (-1.25, 0.95, 0.95), black)
        X.box(p, (-1.3, -0.97, 0.55), (1.3, 0.97, 0.65), (0.1, 0.2, 0.7, 1))   # side stripe
        X.box(p, (-1.2, -0.82, 0.98), (0.95, 0.82, 1.42), (0.05, 0.07, 0.1, 1))  # cabin glass
        X.box(p, (-1.1, -0.84, 1.36), (0.85, 0.84, 1.44), white)                # roof
        X.box(m, (2.3, -0.95, 0.25), (2.45, 0.95, 0.5), (0.12, 0.12, 0.13, 1))  # bumpers
        X.box(m, (-2.45, -0.95, 0.25), (-2.3, 0.95, 0.5), (0.12, 0.12, 0.13, 1))
        for wx in (-1.45, 1.45):
            for wy in (-0.86, 0.86):
                X.hcyl(m, (wx, wy, 0.36), 0.36, 0.26, "y", (0.05, 0.05, 0.05, 1), 10,
                       cap=(0.5, 0.5, 0.52, 1))
        e = self.mb["emit"]
        X.box(e, (2.36, -0.8, 0.62), (2.42, -0.45, 0.75), (1.0, 0.95, 0.8, 1))  # headlights
        X.box(e, (2.36, 0.45, 0.62), (2.42, 0.8, 0.75), (1.0, 0.95, 0.8, 1))
        X.box(e, (-2.42, -0.8, 0.62), (-2.36, -0.5, 0.75), (1.0, 0.1, 0.05, 1))
        X.box(e, (-2.42, 0.5, 0.62), (-2.36, 0.8, 0.75), (1.0, 0.1, 0.05, 1))
        # light bar: red and blue halves flash alternately
        red, blue = geom.MeshBuilder("bar_r"), geom.MeshBuilder("bar_b")
        X.box(red, (-0.2, -0.7, 1.44), (0.15, -0.02, 1.58), (1.0, 0.08, 0.05, 1))
        X.box(blue, (-0.2, 0.02, 1.44), (0.15, 0.7, 1.58), (0.08, 0.25, 1.0, 1))
        rn = _node(red, self.static_np, self.tex.white, MAT_EMIT)
        bn = _node(blue, self.static_np, self.tex.white, MAT_EMIT)
        idx = self._light(X.p(0, 0, 2.0), (1.0, 0.1, 0.05), 7.0, 1.0)
        self.police.append((rn, bn, idx, d["v"] * 10))

    def _p_table(self, X, d):
        w = self.mb["wood"]
        c = (0.55, 0.4, 0.26, 1)
        X.box(w, (-0.9, -0.45, 0.72), (0.9, 0.45, 0.78), c)
        for sx in (-0.82, 0.82):
            for sy in (-0.38, 0.38):
                X.box(w, (sx - 0.03, sy - 0.03, 0), (sx + 0.03, sy + 0.03, 0.72), c)

    def _p_chair(self, X, d):
        m = self.mb["matte"]
        c = (0.25, 0.3, 0.45, 1) if d["v"] < 0.5 else (0.45, 0.22, 0.2, 1)
        leg = (0.2, 0.2, 0.22, 1)
        X.box(m, (-0.22, -0.22, 0.42), (0.22, 0.22, 0.48), c)
        X.box(m, (-0.22, -0.24, 0.48), (0.22, -0.18, 0.95), c)
        for sx in (-0.19, 0.19):
            for sy in (-0.19, 0.19):
                X.box(m, (sx - 0.02, sy - 0.02, 0), (sx + 0.02, sy + 0.02, 0.42), leg)

    def _p_desk(self, X, d):
        w, m, e = self.mb["wood"], self.mb["matte"], self.mb["emit"]
        c = (0.6, 0.5, 0.36, 1)
        X.box(w, (-0.8, -0.4, 0.7), (0.8, 0.4, 0.76), c)
        X.box(w, (-0.8, -0.4, 0), (-0.74, 0.4, 0.7), c)
        X.box(w, (0.74, -0.4, 0), (0.8, 0.4, 0.7), c)
        X.box(m, (-0.28, 0.1, 0.76), (0.28, 0.3, 1.14), (0.75, 0.73, 0.66, 1))  # CRT monitor
        X.box(e, (-0.22, 0.08, 0.82), (0.22, 0.1, 1.08), (0.25, 0.45, 0.6, 1))
        X.box(m, (-0.25, -0.2, 0.76), (0.25, -0.05, 0.79), (0.7, 0.68, 0.62, 1))

    def _p_office_chair(self, X, d):
        m = self.mb["matte"]
        c = (0.12, 0.12, 0.14, 1)
        X.box(m, (-0.3, -0.03, 0.05), (0.3, 0.03, 0.09), c)
        X.box(m, (-0.03, -0.3, 0.05), (0.03, 0.3, 0.09), c)
        X.box(m, (-0.03, -0.03, 0.09), (0.03, 0.03, 0.45), c)
        X.box(m, (-0.25, -0.25, 0.45), (0.25, 0.25, 0.53), c)
        X.box(m, (-0.23, -0.28, 0.55), (0.23, -0.22, 1.05), c)

    def _p_cabinet(self, X, d):
        m = self.mb["paint"]
        X.box(m, (-0.25, -0.3, 0), (0.25, 0.3, 1.32), (0.5, 0.52, 0.5, 1))
        for k in range(4):
            z = 0.12 + k * 0.31
            X.box(m, (-0.2, 0.3, z), (0.2, 0.32, z + 0.26), (0.42, 0.44, 0.42, 1))
            X.box(m, (-0.06, 0.32, z + 0.18), (0.06, 0.34, z + 0.21), (0.75, 0.75, 0.72, 1))

    def _p_couch(self, X, d):
        m = self.mb["matte"]
        c = (0.35, 0.42, 0.25, 1) if d["v"] < 0.5 else (0.48, 0.2, 0.2, 1)
        X.box(m, (-1.0, -0.43, 0.1), (1.0, 0.43, 0.45), c)
        X.box(m, (-1.0, -0.43, 0.45), (1.0, -0.2, 0.85), _shade(c, 0.9))
        X.box(m, (-1.0, -0.43, 0.45), (-0.8, 0.43, 0.65), _shade(c, 0.95))
        X.box(m, (0.8, -0.43, 0.45), (1.0, 0.43, 0.65), _shade(c, 0.95))
        X.box(m, (-0.95, -0.4, 0), (0.95, 0.4, 0.1), (0.15, 0.1, 0.08, 1))

    def _p_tv(self, X, d):
        w, m = self.mb["wood"], self.mb["matte"]
        X.box(w, (-0.6, -0.22, 0), (0.6, 0.22, 0.5), (0.4, 0.3, 0.2, 1))
        X.box(m, (-0.4, -0.2, 0.5), (0.4, 0.22, 1.1), (0.15, 0.14, 0.13, 1))
        scr = geom.MeshBuilder("tv_screen")
        X.box(scr, (-0.32, 0.22, 0.58), (0.32, 0.24, 1.02), (0.7, 0.75, 0.85, 1))
        n = _node(scr, self.static_np, self.tex.white, MAT_EMIT)
        self.tvs.append((n, d["v"] * 50))

    def _p_coffee_table(self, X, d):
        w = self.mb["wood"]
        c = (0.45, 0.32, 0.2, 1)
        X.box(w, (-0.5, -0.3, 0.36), (0.5, 0.3, 0.42), c)
        for sx in (-0.45, 0.45):
            for sy in (-0.25, 0.25):
                X.box(w, (sx - 0.03, sy - 0.03, 0), (sx + 0.03, sy + 0.03, 0.36), c)

    def _p_boxes(self, X, d):
        m = self.mb["matte"]
        c = (0.62, 0.47, 0.3, 1)
        X.box(m, (-0.55, -0.45, 0), (0.55, 0.45, 0.6), c)
        X.box(m, (-0.5, -0.4, 0.6), (0.3, 0.35, 1.05), _shade(c, 1.08))
        X.box(m, (-0.35, -0.3, 1.05), (0.15, 0.2, 1.5), _shade(c, 0.95))
        X.box(m, (-0.56, -0.05, 0.25), (0.56, 0.05, 0.35), (0.75, 0.7, 0.55, 1))  # tape

    def _p_cone(self, X, d):
        m = self.mb["paint"]
        X.box(m, (-0.18, -0.18, 0), (0.18, 0.18, 0.04), (0.1, 0.1, 0.1, 1))
        cone(m, X.p(0, 0, 0.04), 0.14, 0.66, (1.0, 0.36, 0.05, 1), 10)
        m.cylinder(X.p(0, 0, 0.3), 0.095, 0.1, (0.95, 0.95, 0.95, 1), 10, caps=False)

    def _p_barrel(self, X, d):
        m = self.mb["paint"]
        c = (0.12, 0.3, 0.6, 1) if d["v"] < 0.5 else (0.55, 0.25, 0.12, 1)
        X.cyl(m, (0, 0, 0), 0.3, 0.92, c)
        for z in (0.2, 0.7):
            X.cyl(m, (0, 0, z), 0.31, 0.04, _shade(c, 0.7))

    def _p_cart(self, X, d):
        m = self.mb["paint"]
        c = (0.7, 0.72, 0.75, 1)
        X.box(m, (-0.45, -0.28, 0.45), (0.45, 0.28, 0.48), c)
        for sx in (-0.45, 0.42):
            X.box(m, (sx, -0.28, 0.48), (sx + 0.03, 0.28, 0.95), c)
        for sy in (-0.28, 0.25):
            X.box(m, (-0.45, sy, 0.48), (0.45, sy + 0.03, 0.95), c)
        X.box(m, (-0.55, -0.26, 0.95), (-0.45, 0.26, 1.0), (0.8, 0.1, 0.1, 1))  # handle
        for sx in (-0.38, 0.38):
            for sy in (-0.22, 0.22):
                X.box(m, (sx - 0.02, sy - 0.02, 0.05), (sx + 0.02, sy + 0.02, 0.45), c)
                X.cyl(m, (sx, sy, 0), 0.05, 0.08, (0.1, 0.1, 0.1, 1), 6)

    def _p_vending(self, X, d):
        m, e = self.mb["paint"], self.mb["emit"]
        c = (0.7, 0.1, 0.1, 1) if d["v"] < 0.5 else (0.1, 0.25, 0.65, 1)
        X.box(m, (-0.5, -0.4, 0), (0.5, 0.4, 1.9), c)
        X.box(e, (-0.4, 0.4, 0.6), (0.15, 0.42, 1.75), (0.8, 0.85, 0.9, 1))
        X.box(m, (0.22, 0.4, 0.9), (0.42, 0.43, 1.4), (0.2, 0.2, 0.22, 1))
        X.box(m, (-0.4, 0.4, 0.15), (0.15, 0.43, 0.45), (0.05, 0.05, 0.06, 1))

    def _p_cooler(self, X, d):
        m = self.mb["paint"]
        X.box(m, (-0.18, -0.18, 0), (0.18, 0.18, 0.9), (0.88, 0.88, 0.86, 1))
        X.cyl(m, (0, 0, 0.9), 0.15, 0.36, (0.45, 0.65, 0.9, 1))

    def _p_arcade(self, X, d):
        m, e = self.mb["paint"], self.mb["emit"]
        c = (0.18, 0.08, 0.3, 1)
        X.box(m, (-0.35, -0.4, 0), (0.35, 0.4, 1.8), c)
        X.box(m, (-0.35, 0.4, 0.8), (0.35, 0.62, 0.95), c)                      # control deck
        X.box(e, (-0.28, 0.4, 1.05), (0.28, 0.42, 1.5), (0.2, 0.9, 0.5, 1))     # screen
        X.box(e, (-0.33, 0.4, 1.6), (0.33, 0.42, 1.76), (1.0, 0.3, 0.8, 1))     # marquee
        X.box(m, (-0.2, 0.55, 0.95), (-0.14, 0.61, 1.05), (0.9, 0.1, 0.1, 1))   # joystick

    def _p_duck(self, X, d):
        m = self.mb["paint"]
        yel = (1.0, 0.82, 0.1, 1)
        blob(m, X.p(0, 0, 0.45), (0.55, 0.45, 0.42), yel, 0.3, 6, 10, 0.03)
        blob(m, X.p(0.3, 0, 0.95), (0.28, 0.28, 0.28), yel, 0.7, 6, 10, 0.02)
        X.box(m, (0.52, -0.1, 0.88), (0.72, 0.1, 0.98), (1.0, 0.45, 0.05, 1))
        for sy in (-0.14, 0.14):
            X.box(m, (0.5, sy - 0.04, 1.02), (0.55, sy + 0.04, 1.1), (0.05, 0.05, 0.05, 1))

    def _p_booth(self, X, d):
        m, e = self.mb["paint"], self.mb["emit"]
        red = (0.75, 0.08, 0.06, 1)
        for sx in (-0.47, 0.47):
            for sy in (-0.47, 0.47):
                X.box(m, (sx - 0.05, sy - 0.05, 0), (sx + 0.05, sy + 0.05, 2.3), red)
        X.box(m, (-0.5, -0.5, 2.15), (0.5, 0.5, 2.3), red)
        X.box(m, (-0.42, -0.45, 0.05), (0.42, -0.43, 2.1), (0.2, 0.25, 0.3, 1))
        X.box(m, (-0.45, -0.42, 0.05), (-0.43, 0.42, 2.1), (0.2, 0.25, 0.3, 1))
        X.box(m, (0.43, -0.42, 0.05), (0.45, 0.42, 2.1), (0.2, 0.25, 0.3, 1))
        X.box(e, (-0.4, 0.5, 2.17), (0.4, 0.52, 2.28), (1.0, 0.95, 0.85, 1))

    def _p_mattress(self, X, d):
        m = self.mb["matte"]
        X.box(m, (-1.0, -0.7, 0), (1.0, 0.7, 0.28), (0.82, 0.8, 0.74, 1))
        X.box(m, (-0.3, -0.2, 0.28), (0.4, 0.3, 0.285), (0.62, 0.52, 0.34, 1))

    def _p_plant(self, X, d):
        m = self.mb["matte"]
        X.cyl(m, (0, 0, 0), 0.22, 0.45, (0.55, 0.3, 0.18, 1))
        for i in range(3):
            a = i * 2.1
            blob(m, X.p(math.cos(a) * 0.1, math.sin(a) * 0.1, 0.8 + i * 0.15), (0.3, 0.3, 0.35),
                 (0.2, 0.42, 0.16, 1), d["v"] + i, 4, 7, 0.25)

    def _p_lamp(self, X, d):
        m, e = self.mb["matte"], self.mb["emit"]
        X.cyl(m, (0, 0, 0), 0.15, 0.04, (0.2, 0.2, 0.2, 1))
        X.cyl(m, (0, 0, 0.04), 0.02, 1.25, (0.2, 0.2, 0.2, 1), 6)
        X.cyl(e, (0, 0, 1.25), 0.2, 0.3, (1.0, 0.85, 0.6, 1))

    def _p_paper(self, X, d):
        mb = self.mb["decal"]
        a = math.radians(d["h"])
        ca, sa = math.cos(a), math.sin(a)
        w, h = 0.21, 0.3
        pts = []
        for (lx, ly) in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
            pts.append((d["x"] + lx * ca - ly * sa, d["y"] + lx * sa + ly * ca, 0.01))
        g = 0.85 + d["v"] * 0.1
        mb.quad(pts[0], pts[1], pts[2], pts[3], (g, g, g * 0.95, 1), (0, 0, 1))

    def _p_stain(self, X, d):
        disc(self.mb["decal"], (d["x"], d["y"], 0.008), d["s"] * 0.6, (0.35, 0.3, 0.17, 1), 12)

    # ------------------------------------------------------------------ per frame
    def update(self, t):
        for node, idx, ph in self.flicker:
            x = math.sin(t * 23.0 + ph) * math.sin(t * 3.7 + ph * 2.0)
            on = x > -0.35 or (int(t * 8 + ph) % 7) == 0
            node.setColorScale((1, 1, 1, 1) if on else (0.12, 0.12, 0.12, 1))
            self._set_light(idx, 0.75 if on else 0.05)
        for rn, bn, idx, ph in self.police:
            red = int(t * 3.2 + ph) % 2 == 0
            rn.setColorScale((1.6, 1.6, 1.6, 1) if red else (0.15, 0.15, 0.15, 1))
            bn.setColorScale((0.15, 0.15, 0.15, 1) if red else (1.6, 1.6, 1.6, 1))
            self._set_light(idx, 1.1, (1.0, 0.1, 0.05) if red else (0.1, 0.3, 1.0))
        for n, ph in self.tvs:
            g = 0.6 + 0.4 * abs(math.sin(t * 17 + ph)) * abs(math.sin(t * 5.3 + ph))
            n.setColorScale(g, g, g * 1.05, 1)

# ============================================================================ CORAL TOWN
class CoralVisuals(_MapVisuals):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        th = self.theme
        self.sky = make_sky(self.floor, self.tex, th["sky_top"], th["sky_horizon"])
        ground(self.static_np, self.tex.get("sand"), L.HALF + 44, (0.86, 0.79, 0.6), mat=MAT_MATTE)
        self.mb = {"matte": geom.MeshBuilder("c_matte"), "stone": geom.MeshBuilder("c_stone"),
                   "pine": geom.MeshBuilder("c_pine"), "wood": geom.MeshBuilder("c_wood"),
                   "paint": geom.MeshBuilder("c_paint"), "emit": geom.MeshBuilder("c_emit"),
                   "glass": geom.MeshBuilder("c_glass"), "leaf": geom.MeshBuilder("c_leaf")}
        for d in L.DECOR:
            fn = getattr(self, "_c_" + d["k"], None)
            if fn is not None:
                fn(d)
        m = self.mb
        _node(m["matte"], self.static_np, self.tex.get("rock"), MAT_ROCK)
        _node(m["stone"], self.static_np, self.tex.get("stone"), MAT_ROCK)
        _node(m["pine"], self.static_np, self.tex.get("pineapple"), MAT_MATTE)
        _node(m["wood"], self.static_np, self.tex.get("wood"), MAT_WOOD)
        _node(m["paint"], self.static_np, self.tex.white, MAT_PAINT)
        _node(m["leaf"], self.static_np, self.tex.get("foliage"), MAT_LEAF)
        _node(m["emit"], self.static_np, self.tex.white, MAT_EMIT_SOFT)
        g = _node(m["glass"], self.static_np, self.tex.white, Vec4(120, 1.5, 0.6, 0.05))
        g.setTransparency(TransparencyAttrib.M_alpha)
        g.setDepthWrite(False)
        g.setBin("fixed", 1)
        self._build_water_fx()

    # ---------------------------------------------------------------- houses
    def _c_pineapple(self, d):
        x, y = d["x"], d["y"]
        blob(self.mb["pine"], (x, y, 3.7), (3.2, 3.2, 4.0), (1.0, 0.62, 0.12, 1), 0.2, 10, 16,
             0.03)
        leaf = self.mb["leaf"]
        rng = random.Random(4)
        for i in range(11):
            a = math.tau * i / 11 + rng.uniform(-0.1, 0.1)
            ln = rng.uniform(2.4, 3.6)
            tilt = rng.uniform(0.35, 0.8)
            base = Vec3(x, y, 7.2)
            tip = base + Vec3(math.cos(a) * ln * tilt, math.sin(a) * ln * tilt, ln)
            side = Vec3(-math.sin(a), math.cos(a), 0) * 0.38
            col = (0.15, 0.5 + 0.1 * (i % 2), 0.16, 1)
            leaf.tri(base - side, base + side, tip, col, (math.cos(a), math.sin(a), 0.4))
        # front door, porthole windows and a chimney-ish pipe (faces the town centre: -y)
        p = self.mb["paint"]
        vdisc(p, (x, y - 3.25, 1.2), 0.95, ("y", "-"), (0.25, 0.45, 0.7, 1))
        vdisc(p, (x + 1.4, y - 3.0, 4.2), 0.55, ("y", "-"), (0.55, 0.85, 1.0, 1))
        vdisc(p, (x - 1.5, y - 2.9, 3.0), 0.45, ("y", "-"), (0.55, 0.85, 1.0, 1))
        vdisc(p, (x - 3.25, y, 3.6), 0.5, ("x", "-"), (0.55, 0.85, 1.0, 1))
        p.cylinder((x + 2.2, y + 1.0, 5.8), 0.25, 1.4, (0.6, 0.6, 0.62, 1), 10)

    def _c_tiki(self, d):
        x, y = d["x"], d["y"]
        s = self.mb["stone"]
        c = (0.42, 0.5, 0.55, 1)
        dark = (0.12, 0.14, 0.16, 1)
        s.box((x - 2.3, y - 2.3, 0), (x + 2.3, y + 2.3, 7.0), c, uv_scale=0.4)
        f = y - 2.3                                                # face is on the -y side
        s.box((x - 2.4, f - 0.5, 4.6), (x + 2.4, f, 5.3), c)       # brow
        s.box((x - 0.45, f - 0.9, 2.6), (x + 0.45, f, 4.7), c)     # long nose
        s.box((x - 1.6, f - 0.35, 1.7), (x + 1.6, f, 2.1), c)      # lips
        s.box((x - 2.6, y - 1.0, 3.0), (x - 2.3, y + 0.6, 5.4), c)  # ears
        s.box((x + 2.3, y - 1.0, 3.0), (x + 2.6, y + 0.6, 5.4), c)
        p = self.mb["paint"]
        for sx in (-1, 1):
            p.box((x + sx * 1.25 - 0.55, f - 0.06, 3.7), (x + sx * 1.25 + 0.55, f, 4.4), dark)
        p.box((x - 0.7, f - 0.06, 0), (x + 0.7, f, 1.5), (0.35, 0.22, 0.12, 1))   # door
        e = self.mb["emit"]
        for sx in (-1, 1):
            e.box((x + sx * 1.25 - 0.4, f - 0.08, 3.8), (x + sx * 1.25 + 0.4, f - 0.06, 4.25),
                  (1.0, 0.8, 0.4, 1))
        self._light((x, f - 1.5, 4.0), (1.0, 0.75, 0.4), 8.0, 0.7)

    def _c_rockhouse(self, d):
        x, y = d["x"], d["y"]
        blob(self.mb["matte"], (x, y, 0.0), (3.7, 3.7, 2.25), (0.55, 0.42, 0.33, 1), 0.6, 8, 14,
             0.06)
        w = self.mb["paint"]
        w.cylinder((x, y, 2.0), 0.05, 1.6, (0.4, 0.4, 0.4, 1), 6)
        w.box((x - 0.7, y - 0.05, 3.45), (x + 0.5, y + 0.05, 3.55), (0.4, 0.4, 0.4, 1))
        w.tri((x + 0.5, y, 3.35), (x + 0.5, y, 3.65), (x + 0.9, y, 3.5), (0.8, 0.2, 0.1, 1),
              (0, -1, 0))

    def _c_dome(self, d):
        x, y, r = d["x"], d["y"], d["r"]
        g = self.mb["glass"]
        col = (0.75, 0.95, 1.0, 0.16)
        seg = 44
        for i in range(seg):
            a0 = math.tau * i / seg
            a1 = math.tau * (i + 1) / seg
            deg = math.degrees((a0 + a1) / 2) % 360
            if abs(deg - 90) < 14 or abs(deg - 270) < 14:
                continue                                         # doorways
            p0 = (x + math.cos(a0) * r, y + math.sin(a0) * r)
            p1 = (x + math.cos(a1) * r, y + math.sin(a1) * r)
            n = (math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0)
            g.quad((p0[0], p0[1], 0), (p1[0], p1[1], 0), (p1[0], p1[1], 4.5), (p0[0], p0[1], 4.5),
                   col, n)
        blob(g, (x, y, 4.5), (r, r, r * 0.6), col, 0.0, 8, 22, 0.0)
        # metal frame: base band, top band and meridian ribs
        p = self.mb["paint"]
        band = (0.55, 0.6, 0.65, 1)
        for i in range(seg):
            a = math.tau * (i + 0.5) / seg
            deg = math.degrees(a) % 360
            if abs(deg - 90) < 14 or abs(deg - 270) < 14:
                continue
            cx, cy = x + math.cos(a) * r, y + math.sin(a) * r
            p.box((cx - 0.12, cy - 0.12, 0), (cx + 0.12, cy + 0.12, 0.35), band)
            p.box((cx - 0.08, cy - 0.08, 4.45), (cx + 0.08, cy + 0.08, 4.6), band)
            if i % 4 == 0:
                p.box((cx - 0.05, cy - 0.05, 0), (cx + 0.05, cy + 0.05, 4.5), band)
        # the tree inside and a picnic table
        tr = self.mb["wood"]
        tr.cylinder((x + 3.0, y + 1.5, 0), 0.45, 5.5, (0.45, 0.33, 0.22, 1), 10)
        for (ox, oy, oz, rr) in ((3.0, 1.5, 6.4, 2.2), (1.6, 0.5, 5.6, 1.5), (4.3, 2.4, 5.7, 1.6)):
            blob(self.mb["leaf"], (x + ox, y + oy, oz), (rr, rr, rr * 0.8), (0.25, 0.55, 0.2, 1),
                 ox, 5, 9, 0.18)
        tr.box((x - 4.2, y - 2.45, 0.7), (x - 2.2, y - 1.55, 0.76), (0.6, 0.45, 0.3, 1))
        for sx in (-4.05, -2.35):
            tr.box((x + sx - 0.05, y - 2.4, 0), (x + sx + 0.05, y - 1.6, 0.7), (0.5, 0.38, 0.25, 1))
        self._light((x, y, 5.0), (0.8, 1.0, 0.9), 12.0, 0.6)

    def _c_diner(self, d):
        x, y = d["x"], d["y"]
        w = self.mb["wood"]
        hull = (0.55, 0.38, 0.24, 1)
        w.box((x - 5, y - 3, 0), (x + 5, y + 3, 4.2), hull, uv_scale=0.5)
        w.box((x - 5.3, y - 3.3, 4.2), (x + 5.3, y + 3.3, 4.45), (0.45, 0.3, 0.2, 1))
        for k in range(-4, 5):
            w.box((x + k - 0.05, y - 3.35, 4.45), (x + k + 0.05, y - 3.25, 5.2), hull)
        w.box((x - 5.3, y - 3.35, 5.1), (x + 5.3, y - 3.25, 5.2), hull)
        w.cylinder((x + 2.0, y, 4.45), 0.18, 5.0, (0.4, 0.28, 0.18, 1), 8)       # mast
        p = self.mb["paint"]
        for k in (-3.2, -1.1, 1.1, 3.2):
            vdisc(p, (x + k, y - 3.02, 2.6), 0.5, ("y", "-"), (0.55, 0.85, 1.0, 1))
            vdisc(p, (x + k, y + 3.02, 2.6), 0.5, ("y", "+"), (0.55, 0.85, 1.0, 1))
        p.box((x - 0.8, y - 3.06, 0), (x + 0.8, y - 3.0, 2.2), (0.25, 0.15, 0.1, 1))
        e = self.mb["emit"]
        e.box((x - 1.6, y - 3.12, 3.0), (x + 1.6, y - 3.06, 3.7), (1.0, 0.85, 0.3, 1))  # sign
        self._light((x, y - 4.5, 3.2), (1.0, 0.8, 0.4), 9.0, 0.8)

    def _c_boat(self, d):
        X = Xf(d["x"], d["y"], d.get("h", 0))
        p = self.mb["paint"]
        X.box(p, (-1.8, -0.9, 0.25), (1.8, 0.9, 0.95), (0.92, 0.92, 0.95, 1))
        X.box(p, (-1.8, -0.92, 0.55), (1.8, 0.92, 0.65), (0.2, 0.45, 0.9, 1))
        X.box(p, (-0.2, -0.8, 0.95), (0.7, 0.8, 1.3), (0.4, 0.7, 0.9, 1))
        X.box(p, (-1.9, -0.6, 0.6), (-1.75, 0.6, 1.5), (0.9, 0.2, 0.2, 1))        # fin
        for wx in (-1.1, 1.1):
            X.hcyl(p, (wx, 0, 0.28), 0.28, 2.0, "y", (0.1, 0.1, 0.1, 1), 8)

    def _c_coral(self, d):
        cols = [(1.0, 0.4, 0.5, 1), (1.0, 0.6, 0.2, 1), (0.7, 0.35, 1.0, 1), (1.0, 0.85, 0.3, 1)]
        col = cols[d["c"]]
        p = self.mb["paint"]
        x, y, r, h = d["x"], d["y"], d["r"], d["h"]
        p.cylinder((x, y, 0), r * 0.6, h, col, 8)
        rng = random.Random(d["seed"])
        for i in range(4):
            a = rng.uniform(0, math.tau)
            z = h * rng.uniform(0.35, 0.8)
            bx, by = x + math.cos(a) * r * 0.9, y + math.sin(a) * r * 0.9
            p.cylinder((bx, by, z), r * 0.25, h * 0.45, col, 6)
            blob(p, (bx, by, z + h * 0.45), (r * 0.3, r * 0.3, r * 0.3), col, i, 4, 6, 0.1)
        blob(p, (x, y, h), (r * 0.7, r * 0.7, r * 0.5), col, d["seed"], 4, 8, 0.15)

    def _c_boulder(self, d):
        g = 0.45 + d["seed"] * 0.15
        blob(self.mb["matte"], (d["x"], d["y"], d["h"] * 0.35),
             (d["r"] * 1.1, d["r"] * 1.1, d["h"] * 0.75), (g, g * 1.02, g * 1.05, 1), d["seed"],
             7, 11, 0.15)

    def _c_clam(self, d):
        p = self.mb["paint"]
        x, y = d["x"], d["y"]
        blob(p, (x, y, 0.25), (1.15, 0.85, 0.35), (0.85, 0.55, 0.75, 1), d["seed"], 5, 12, 0.05)
        blob(p, (x, y + 0.2, 0.75), (1.1, 0.8, 0.3), (0.9, 0.6, 0.8, 1), d["seed"] + 1, 5, 12, 0.05)
        blob(self.mb["emit"], (x, y - 0.1, 0.55), (0.2, 0.2, 0.2), (1.0, 0.95, 0.9, 1), 0, 5, 8,
             0.0)

    def _c_anchor(self, d):
        p = self.mb["paint"]
        x, y = d["x"], d["y"]
        c = (0.3, 0.32, 0.35, 1)
        p.box((x - 0.15, y - 0.15, 0.3), (x + 0.15, y + 0.15, 3.0), c)
        p.box((x - 0.12, y - 1.2, 2.5), (x + 0.12, y + 1.2, 2.7), c)
        p.box((x - 0.15, y - 1.8, 0.0), (x + 0.15, y + 1.8, 0.35), c)
        for sy in (-1, 1):
            p.box((x - 0.15, y + sy * 1.8 - 0.15, 0.0), (x + 0.15, y + sy * 1.8 + 0.15, 1.0), c)
        p.cylinder((x, y, 3.0), 0.35, 0.2, c, 10)

    def _c_kelp(self, d):
        leaf = self.mb["leaf"]
        x, y, h = d["x"], d["y"], d["h"]
        rng = random.Random(d["seed"])
        for k in range(3):
            ox, oy = rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4)
            a = rng.uniform(0, math.tau)
            sx, sy = math.cos(a) * 0.18, math.sin(a) * 0.18
            seg = 6
            for i in range(seg):
                z0 = h * i / seg
                z1 = h * (i + 1) / seg
                w0 = math.sin(i * 0.9 + d["seed"] * 6) * 0.35
                w1 = math.sin((i + 1) * 0.9 + d["seed"] * 6) * 0.35
                col = (0.2, 0.42 + 0.05 * k, 0.15, 1)
                leaf.quad((x + ox - sx + w0, y + oy - sy, z0), (x + ox + sx + w0, y + oy + sy, z0),
                          (x + ox + sx + w1, y + oy + sy, z1), (x + ox - sx + w1, y + oy - sy, z1),
                          col, (math.sin(a), -math.cos(a), 0))

    def _c_smallcoral(self, d):
        cols = [(1.0, 0.45, 0.55, 1), (1.0, 0.65, 0.25, 1), (0.75, 0.4, 1.0, 1), (0.4, 0.9, 0.8, 1)]
        blob(self.mb["paint"], (d["x"], d["y"], 0.2), (0.45, 0.45, 0.4), cols[d["c"]],
             d["seed"], 4, 7, 0.3)

    def _c_farrock(self, d):
        g = 0.35 + d["seed"] * 0.1
        blob(self.mb["matte"], (d["x"], d["y"], 0), (d["r"], d["r"], d["r"] * 0.7),
             (g, g * 1.05, g * 1.1, 1), d["seed"], 4, 8, 0.2)

    # ---------------------------------------------------------------- water effects
    def _build_water_fx(self):
        hq = self.quality == "high"
        rng = random.Random(12)
        self.rays = []
        proto = geom.cone_mesh(12)
        for i in range(8 if hq else 3):
            c = proto.copyTo(self.root)
            c.setPos(rng.uniform(-24, 24), rng.uniform(-24, 24), L.CEILING_Z)
            c.setScale(rng.uniform(3, 5), rng.uniform(3, 5), L.CEILING_Z)
            c.setP(rng.uniform(-8, 8))
            fx_node(c, 1, hue_lock=True)
            c.setColorScale(0.05, 0.22, 0.25, 1)
            self.rays.append((c, rng.uniform(0, 10)))
        self.bubbles = []
        for i in range(60 if hq else 20):
            b = geom.card(0.12, 0.12)
            b.reparentTo(self.root)
            b.setBillboardPointEye()
            fx_node(b, 5, hue_lock=True)
            b.setColorScale(0.5, 0.8, 0.9, 1)
            self.bubbles.append([b, rng.uniform(-30, 30), rng.uniform(-30, 30),
                                 rng.uniform(0, 18), rng.uniform(0.8, 2.0), rng.uniform(0, 6)])
        self.jellies = []
        for d in L.DECOR:
            if d["k"] != "jelly":
                continue
            j = geom.card(1.4, 1.4)
            j.reparentTo(self.root)
            j.setBillboardPointEye()
            fx_node(j, 5, hue_lock=True)
            j.setColorScale(1.4, 0.4, 1.2, 1)
            self.jellies.append((j, d))

    def update(self, t):
        for c, ph in self.rays:
            c.setColorScale(0.05 + 0.02 * math.sin(t * 0.5 + ph), 0.22, 0.25, 1)
            c.setR(math.sin(t * 0.2 + ph) * 3)
        for b in self.bubbles:
            node, x, y, z, sp, ph = b
            z += sp * 0.016
            if z > 20:
                z = 0.0
            b[3] = z
            node.setPos(x + math.sin(t * 2 + ph) * 0.2, y, z)
        for j, d in self.jellies:
            j.setPos(d["x"] + math.sin(t * 0.3 + d["seed"] * 9) * 2, d["y"],
                     d["z"] + math.sin(t * 0.8 + d["seed"] * 5) * 0.8)
            k = 0.8 + 0.3 * math.sin(t * 2 + d["seed"] * 7)
            j.setScale(k, 1, 1.2 - 0.2 * k)


# ============================================================================ SKYLINE
class SkylineVisuals(_MapVisuals):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        th = self.theme
        self.sky = make_sky(self.floor, self.tex, th["sky_top"], th["sky_horizon"])
        g = ground(self.static_np, self.tex.get("rock"), L.HALF + 110, (0.12, 0.12, 0.14), uv=0.1)
        g.setShaderInput("u_mat", MAT_MATTE)
        self.blinks = []
        self.mb = {"facade": geom.MeshBuilder("s_facade"), "roof": geom.MeshBuilder("s_roof"),
                   "metal": geom.MeshBuilder("s_metal"), "wood": geom.MeshBuilder("s_wood"),
                   "paint": geom.MeshBuilder("s_paint"), "emit": geom.MeshBuilder("s_emit"),
                   "neon": geom.MeshBuilder("s_neon")}
        m = self.mb
        for b in L.STATIC_BOXES:
            kind = b[6]
            mn, mx = b[:3], b[3:6]
            if kind == "tower":
                m["facade"].box(mn, mx, (1, 1, 1, 1), uv_scale=1 / 6.0, faces="s")
                m["roof"].box(mn, mx, (0.42, 0.42, 0.45, 1), uv_scale=0.25, faces="t")
                # glowing roof edge trim
                x0, y0, _, x1, y1, z1 = b[:6]
                e = 0.06
                for (a0, a1) in (((x0, y0), (x1, y0 + e)), ((x0, y1 - e), (x1, y1)),
                                 ((x0, y0), (x0 + e, y1)), ((x1 - e, y0), (x1, y1))):
                    m["neon"].box((a0[0], a0[1], z1 - 0.5), (a1[0], a1[1], z1 - 0.4),
                                  (0.2, 0.8, 1.0, 1))
            elif kind in ("parapet", "stair"):
                m["roof"].box(mn, mx, (0.5, 0.5, 0.52, 1), uv_scale=0.5)
            elif kind == "bridge":
                m["metal"].box(mn, mx, (0.35, 0.37, 0.4, 1), uv_scale=0.5)
            elif kind in ("house", "house_roof"):
                m["paint"].box(mn, mx, (0.85, 0.82, 0.76, 1) if kind == "house" else
                               (0.35, 0.2, 0.15, 1))
            elif kind in ("table", "couch"):
                m["wood"].box(mn, mx, (0.55, 0.35, 0.22, 1) if kind == "table" else
                              (0.4, 0.12, 0.15, 1))
        for d in L.DECOR:
            fn = getattr(self, "_s_" + d["k"], None)
            if fn is not None:
                fn(d)
        _node(m["facade"], self.static_np, self.tex.get("windows"), Vec4(30, 0.4, 0.0, 1.0))
        _node(m["roof"], self.static_np, self.tex.get("rock"), MAT_ROCK)
        _node(m["metal"], self.static_np, self.tex.metal, MAT_PAINT)
        _node(m["wood"], self.static_np, self.tex.get("wood"), MAT_WOOD)
        _node(m["paint"], self.static_np, self.tex.white, MAT_PAINT)
        _node(m["emit"], self.static_np, self.tex.white, MAT_EMIT)
        _node(m["neon"], self.static_np, self.tex.white, Vec4(1, 0, 0, 2.2))
        self._build_night()

    # ---------------------------------------------------------------- props
    def _s_tower(self, d):
        # a warm rooftop lamp per tower so the roofs read at night
        self._light((d["x"], d["y"], d["h"] + 4.0), (1.0, 0.82, 0.6), 14.0, 0.9)

    def _s_house(self, d):
        x, y, z = d["x"], d["y"], L.CATWALK_Z
        e = self.mb["emit"]
        for sx in (-1, 1):
            e.box((x + sx * 4.02 - 0.03, y - 1.6, z + 1.05), (x + sx * 4.02 + 0.03, y - 0.7,
                                                               z + 2.05), (1.0, 0.85, 0.55, 1))
            e.box((x + sx * 4.02 - 0.03, y + 0.7, z + 1.05), (x + sx * 4.02 + 0.03, y + 1.6,
                                                               z + 2.05), (1.0, 0.85, 0.55, 1))
        self._light((x, y, z + 2.5), (1.0, 0.8, 0.5), 9.0, 1.0)
        # chimney + TV antenna on the roof
        p = self.mb["paint"]
        p.box((x + 2.5, y + 1.5, z + 3.25), (x + 3.1, y + 2.1, z + 4.3), (0.5, 0.25, 0.2, 1))

    def _s_stairs(self, d):
        pass

    def _s_ac(self, d):
        p = self.mb["metal"]
        x, y, z = d["x"], d["y"], d["z"]
        p.box((x - 1.1, y - 0.8, z), (x + 1.1, y + 0.8, z + 1.3), (0.6, 0.62, 0.64, 1))
        p.cylinder((x, y, z + 1.3), 0.55, 0.06, (0.2, 0.2, 0.22, 1), 14)

    def _s_vent(self, d):
        p = self.mb["metal"]
        x, y, z = d["x"], d["y"], d["z"]
        p.box((x - 0.6, y - 0.6, z), (x + 0.6, y + 0.6, z + 1.0), (0.5, 0.52, 0.55, 1))
        p.cylinder((x, y, z + 1.0), 0.35, 0.5, (0.45, 0.47, 0.5, 1), 10)

    def _s_watertower(self, d):
        w = self.mb["wood"]
        x, y, z = d["x"], d["y"], d["z"]
        w.cylinder((x, y, z + 2.6), 1.6, 3.2, (0.5, 0.36, 0.25, 1), 16)
        cone(w, (x, y, z + 5.8), 1.75, 1.0, (0.35, 0.25, 0.18, 1), 16)
        for sx in (-1, 1):
            for sy in (-1, 1):
                w.box((x + sx * 1.1 - 0.08, y + sy * 1.1 - 0.08, z),
                      (x + sx * 1.1 + 0.08, y + sy * 1.1 + 0.08, z + 2.6), (0.3, 0.3, 0.32, 1))

    def _s_billboard(self, d):
        x, y, z = d["x"], d["y"], d["z"]
        self.mb["metal"].box((x - 0.2, y - 3.0, z), (x + 0.2, y + 3.0, z + 3.6),
                             (0.25, 0.25, 0.28, 1))
        hot = (1.0, 0.25, 0.75, 1) if d["seed"] < 0.5 else (0.2, 0.9, 1.0, 1)
        for sx in (-1, 1):
            self.mb["neon"].box((x + sx * 0.21 - 0.01, y - 2.8, z + 1.0),
                                (x + sx * 0.21 + 0.01, y + 2.8, z + 3.4), hot)
        self._light((x, y, z + 2.5), hot[:3], 10.0, 0.9)

    def _s_antenna(self, d):
        x, y, z = d["x"], d["y"], d["z"]
        self.mb["metal"].box((x - 0.08, y - 0.08, z), (x + 0.08, y + 0.08, z + 7.0),
                             (0.4, 0.4, 0.42, 1))
        mb = geom.MeshBuilder("beacon")
        mb.sphere((x, y, z + 7.1), 0.18, (1.0, 0.1, 0.05, 1), 4, 6)
        n = _node(mb, self.static_np, self.tex.white, MAT_EMIT)
        self.blinks.append((n, d["seed"] * 3))

    def _s_helipad(self, d):
        e = self.mb["neon"]
        x, y, z = d["x"], d["y"], d["z"] + 0.02
        e.box((x - 1.3, y - 0.15, z), (x + 1.3, y + 0.15, z + 0.01), (1.0, 0.9, 0.3, 1))
        e.box((x - 1.3, y - 1.5, z), (x - 1.0, y + 1.5, z + 0.01), (1.0, 0.9, 0.3, 1))
        e.box((x + 1.0, y - 1.5, z), (x + 1.3, y + 1.5, z + 0.01), (1.0, 0.9, 0.3, 1))
        mb = geom.MeshBuilder("ring")
        mb.ring(3.6, 3.8, (1.0, 0.9, 0.3, 1), 40, z=0)
        r = _node(mb, self.static_np, self.tex.white, Vec4(1, 0, 0, 2.0))
        r.setPos(x, y, z)

    def _s_fartower(self, d):
        x, y, h, w = d["x"], d["y"], d["h"], d["w"]
        self.mb["facade"].box((x - w / 2, y - w / 2, 0), (x + w / 2, y + w / 2, h), (1, 1, 1, 1),
                              uv_scale=1 / 6.0, faces="s")
        self.mb["roof"].box((x - w / 2, y - w / 2, 0), (x + w / 2, y + w / 2, h),
                            (0.3, 0.3, 0.33, 1), faces="t")
        if d["seed"] < 0.4:
            mb = geom.MeshBuilder("beacon")
            mb.sphere((x, y, h + 0.4), 0.4, (1.0, 0.1, 0.05, 1), 4, 6)
            n = _node(mb, self.static_np, self.tex.white, MAT_EMIT)
            self.blinks.append((n, d["seed"] * 7))

    def _s_plane(self, d):
        mb = geom.MeshBuilder("plane")
        white = (0.85, 0.87, 0.9, 1)
        hcyl(mb, (0, 0, 0), 0.9, 12.0, "y", white, 12)
        cone(mb, (0, 6.0, 0), 0.9, 0.0001, white, 12)
        mb.box((-7.5, -0.8, -0.15), (7.5, 1.6, 0.15), white)            # wings
        mb.box((-2.8, -5.8, -0.1), (2.8, -4.6, 0.1), white)            # tail plane
        mb.box((-0.1, -6.0, 0.0), (0.1, -4.4, 2.6), white)             # fin
        self.plane = _node(mb, self.floor, self.tex.metal, MAT_PAINT)
        self.plane.setShader(shaders.get("world"))
        lm = geom.MeshBuilder("plane_lights")
        lm.sphere((-7.5, 0.4, 0), 0.25, (1.0, 0.1, 0.1, 1), 4, 6)
        lm.sphere((7.5, 0.4, 0), 0.25, (0.1, 1.0, 0.2, 1), 4, 6)
        lm.sphere((0, -6.0, 2.7), 0.25, (1, 1, 1, 1), 4, 6)
        self.plane_lights = _node(lm, self.plane, self.tex.white, MAT_EMIT)

    # ---------------------------------------------------------------- night sky & street
    def _build_night(self):
        rng = random.Random(21)
        self.stars = geom.MeshBuilder("stars")
        for _ in range(260 if self.quality == "high" else 120):
            a = rng.uniform(0, math.tau)
            el = rng.uniform(0.12, 1.4)
            r = 185
            p = Vec3(math.cos(el) * math.cos(a) * r, math.cos(el) * math.sin(a) * r,
                     math.sin(el) * r)
            s = rng.uniform(0.25, 0.6)
            g = rng.uniform(0.6, 1.0)
            self.stars.cbox((p.x, p.y, p.z), (s, s, s), (g, g, g * 1.1, 1))
        st = self.stars.node()
        st.reparentTo(self.floor)
        st.setShader(shaders.get("world"))
        st.setTexture(self.tex.white)
        st.setShaderInput("u_mat", Vec4(1, 0, 0, 1.6))
        st.setShaderInput("u_fog", Vec4(0, 0, 0, 0))
        st.setBin("background", 2)
        st.setDepthWrite(False)
        moon = geom.card(1, 1)
        moon.reparentTo(self.floor)
        moon.setPos(-70, 120, 110)
        moon.setScale(16)
        moon.setBillboardPointEye()
        fx_node(moon, 5, hue_lock=True)
        moon.setColorScale(1.2, 1.2, 1.4, 1)
        moon.setBin("background", 3)
        # car lights crawling along the streets far below
        self.cars = []
        lanes = [("x", -10.0), ("x", 10.0), ("y", -10.0), ("y", 10.0), ("x", 30.0),
                 ("y", -30.0)]
        for i in range(30 if self.quality == "high" else 12):
            ax, off = lanes[i % len(lanes)]
            c = geom.card(0.7, 0.35)
            c.reparentTo(self.root)
            c.setBillboardPointEye()
            fx_node(c, 5, hue_lock=True)
            head = i % 2 == 0
            c.setColorScale(*((1.6, 1.5, 1.2, 1) if head else (1.8, 0.15, 0.1, 1)))
            self.cars.append((c, ax, off + (0.8 if head else -0.8), rng.uniform(-60, 60),
                              rng.uniform(8, 16) * (1 if head else -1)))

    def update(self, t):
        for n, ph in self.blinks:
            on = (t + ph) % 1.6 < 0.25
            n.setColorScale((1, 1, 1, 1) if on else (0.15, 0.15, 0.15, 1))
        a = t * 0.08
        r = 85.0
        self.plane.setPos(math.cos(a) * r, math.sin(a) * r, 52 + math.sin(t * 0.3) * 2)
        self.plane.setH(math.degrees(a))
        self.plane.setR(-12)
        on = int(t * 1.5) % 2 == 0
        self.plane_lights.setColorScale((1, 1, 1, 1) if on else (0.3, 0.3, 0.3, 1))
        for c, ax, off, start, sp in self.cars:
            p = ((start + t * sp + 80) % 160) - 80
            c.setPos((p, off, 0.4) if ax == "x" else (off, p, 0.4))


def create(render, world_root, textures, lights, quality, font, reflections):
    """Pick the visual builder for the current map (arena_layout.CURRENT)."""
    if L.CURRENT == "forest":
        return ForestVisuals(render, world_root, textures, lights, quality, font, reflections)
    if L.CURRENT == "backrooms":
        return BackroomsVisuals(render, world_root, textures, lights, quality, font, reflections)
    if L.CURRENT == "coral":
        return CoralVisuals(render, world_root, textures, lights, quality, font, reflections)
    if L.CURRENT == "skyline":
        return SkylineVisuals(render, world_root, textures, lights, quality, font, reflections)
    from .arena import ArenaVisuals
    lights.set_theme(None)
    return ArenaVisuals(render, world_root, textures, lights, quality, font, reflections)

