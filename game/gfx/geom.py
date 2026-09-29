"""Procedural mesh construction.

``MeshBuilder`` batches many primitives into a single Geom so the static arena
renders in a handful of draw calls.
"""

import math

from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat,
                          GeomVertexWriter, NodePath, Vec3)


class MeshBuilder:
    def __init__(self, name="mesh"):
        self.name = name
        self.vdata = GeomVertexData(name, GeomVertexFormat.getV3n3c4t2(), Geom.UHStatic)
        self.vw = GeomVertexWriter(self.vdata, "vertex")
        self.nw = GeomVertexWriter(self.vdata, "normal")
        self.cw = GeomVertexWriter(self.vdata, "color")
        self.tw = GeomVertexWriter(self.vdata, "texcoord")
        self.tris = GeomTriangles(Geom.UHStatic)
        self.count = 0

    # -- primitives ---------------------------------------------------------
    def quad(self, p0, p1, p2, p3, color, n=None, uvs=((0, 0), (1, 0), (1, 1), (0, 1))):
        """Counter-clockwise quad p0..p3 (seen from the front)."""
        if n is None:
            a = Vec3(*p1) - Vec3(*p0)
            b = Vec3(*p3) - Vec3(*p0)
            n = a.cross(b)
            n.normalize()
        base = self.count
        for p, uv in zip((p0, p1, p2, p3), uvs):
            self.vw.addData3(p[0], p[1], p[2])
            self.nw.addData3(n[0], n[1], n[2])
            self.cw.addData4(*color)
            self.tw.addData2(uv[0], uv[1])
        self.tris.addVertices(base, base + 1, base + 2)
        self.tris.addVertices(base, base + 2, base + 3)
        self.count += 4

    def box(self, mn, mx, color, uv_scale=0.25, faces="all", top_color=None):
        """Axis-aligned box with world-space UVs (``uv_scale`` tiles per metre)."""
        x0, y0, z0 = mn
        x1, y1, z1 = mx
        s = uv_scale
        tc = top_color or color
        f = faces
        if f == "all" or "t" in f:
            self.quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), tc, (0, 0, 1),
                      ((x0 * s, y0 * s), (x1 * s, y0 * s), (x1 * s, y1 * s), (x0 * s, y1 * s)))
        if f == "all" or "b" in f:
            self.quad((x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0), color, (0, 0, -1),
                      ((x0 * s, y1 * s), (x1 * s, y1 * s), (x1 * s, y0 * s), (x0 * s, y0 * s)))
        if f == "all" or "s" in f:
            # -Y face
            self.quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), color, (0, -1, 0),
                      ((x0 * s, z0 * s), (x1 * s, z0 * s), (x1 * s, z1 * s), (x0 * s, z1 * s)))
            # +Y face
            self.quad((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), color, (0, 1, 0),
                      ((x1 * s, z0 * s), (x0 * s, z0 * s), (x0 * s, z1 * s), (x1 * s, z1 * s)))
            # +X face
            self.quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), color, (1, 0, 0),
                      ((y0 * s, z0 * s), (y1 * s, z0 * s), (y1 * s, z1 * s), (y0 * s, z1 * s)))
            # -X face
            self.quad((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), color, (-1, 0, 0),
                      ((y1 * s, z0 * s), (y0 * s, z0 * s), (y0 * s, z1 * s), (y1 * s, z1 * s)))

    def cbox(self, center, size, color, **kw):
        cx, cy, cz = center
        sx, sy, sz = size
        self.box((cx - sx / 2, cy - sy / 2, cz - sz / 2), (cx + sx / 2, cy + sy / 2, cz + sz / 2),
                 color, **kw)

    def cylinder(self, center, radius, height, color, segments=16, caps=True):
        cx, cy, cz = center
        for i in range(segments):
            a0 = math.tau * i / segments
            a1 = math.tau * (i + 1) / segments
            p0 = (cx + math.cos(a0) * radius, cy + math.sin(a0) * radius)
            p1 = (cx + math.cos(a1) * radius, cy + math.sin(a1) * radius)
            n = (math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0)
            self.quad((p0[0], p0[1], cz), (p1[0], p1[1], cz), (p1[0], p1[1], cz + height),
                      (p0[0], p0[1], cz + height), color, n,
                      ((i / segments, 0), ((i + 1) / segments, 0), ((i + 1) / segments, 1),
                       (i / segments, 1)))
            if caps:
                self.tri((cx, cy, cz + height), (p0[0], p0[1], cz + height),
                         (p1[0], p1[1], cz + height), color, (0, 0, 1))

    def tri(self, p0, p1, p2, color, n=(0, 0, 1)):
        base = self.count
        for p in (p0, p1, p2):
            self.vw.addData3(*p)
            self.nw.addData3(*n)
            self.cw.addData4(*color)
            self.tw.addData2(0.5, 0.5)
        self.tris.addVertices(base, base + 1, base + 2)
        self.count += 3

    def ring(self, radius_in, radius_out, color, segments=48, z=0.0):
        """Flat annulus in the XY plane; v = 0 inner edge, 1 outer edge."""
        for i in range(segments):
            a0 = math.tau * i / segments
            a1 = math.tau * (i + 1) / segments
            c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
            self.quad((c0 * radius_in, s0 * radius_in, z), (c1 * radius_in, s1 * radius_in, z),
                      (c1 * radius_out, s1 * radius_out, z), (c0 * radius_out, s0 * radius_out, z),
                      color, (0, 0, 1),
                      ((i / segments, 0), ((i + 1) / segments, 0), ((i + 1) / segments, 1),
                       (i / segments, 1)))

    def sphere(self, center, radius, color, rings=8, segments=12):
        cx, cy, cz = center
        for r in range(rings):
            t0 = math.pi * r / rings - math.pi / 2
            t1 = math.pi * (r + 1) / rings - math.pi / 2
            for s in range(segments):
                p0 = math.tau * s / segments
                p1 = math.tau * (s + 1) / segments

                def pt(t, p):
                    return (math.cos(t) * math.cos(p), math.cos(t) * math.sin(p), math.sin(t))
                a, b, c, d = pt(t0, p0), pt(t0, p1), pt(t1, p1), pt(t1, p0)
                verts = [(cx + v[0] * radius, cy + v[1] * radius, cz + v[2] * radius)
                         for v in (a, b, c, d)]
                base = self.count
                for v, n in zip(verts, (a, b, c, d)):
                    self.vw.addData3(*v)
                    self.nw.addData3(*n)
                    self.cw.addData4(*color)
                    self.tw.addData2(0.5, 0.5)
                self.tris.addVertices(base, base + 1, base + 2)
                self.tris.addVertices(base, base + 2, base + 3)
                self.count += 4

    # -- output ---------------------------------------------------------------
    def node(self):
        geom = Geom(self.vdata)
        geom.addPrimitive(self.tris)
        gn = GeomNode(self.name)
        gn.addGeom(geom)
        return NodePath(gn)


def beam_mesh():
    """Unit laser beam along +Y (0..1): two crossed quads, u across width."""
    mb = MeshBuilder("beam")
    w = (1, 1, 1, 1)
    mb.quad((-0.5, 0, 0), (0.5, 0, 0), (0.5, 1, 0), (-0.5, 1, 0), w, (0, 0, 1))
    mb.quad((0, 0, -0.5), (0, 0, 0.5), (0, 1, 0.5), (0, 1, -0.5), w, (1, 0, 0))
    return mb.node()


def cone_mesh(segments=20):
    """Unit light cone: apex at origin, opening down -Z to radius 1 at z=-1.
    Built as a fan of camera-agnostic quads with u across, v along."""
    mb = MeshBuilder("cone")
    w = (1, 1, 1, 1)
    for i in range(segments):
        a = math.tau * i / segments
        ca, sa = math.cos(a), math.sin(a)
        # a vertical quad through the axis gives a volumetric look from any angle
        mb.quad((-ca * 0.05, -sa * 0.05, 0), (ca * 0.05, sa * 0.05, 0), (ca, sa, -1), (-ca, -sa, -1),
                w, (sa, -ca, 0), ((0, 0), (1, 0), (1, 1), (0, 1)))
        if i >= segments // 2:
            break
    return mb.node()


def card(w, h, color=(1, 1, 1, 1), centered=True):
    mb = MeshBuilder("card")
    x0, x1 = (-w / 2, w / 2) if centered else (0, w)
    z0, z1 = (-h / 2, h / 2) if centered else (0, h)
    mb.quad((x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1), color, (0, -1, 0))
    return mb.node()
