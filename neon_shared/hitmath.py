"""Ray intersection helpers on plain 3-sequences (tuples, lists or Panda Vec3).

Used by the client for hitscan and by the server for hit validation.
All ray directions are expected to be normalised.
"""

import math

# Hit volume of a combatant relative to its feet position.
BODY_RADIUS = 0.36
BODY_BOTTOM = 0.25
STAND_HEIGHT = 1.8
CROUCH_HEIGHT = 1.2
HEAD_RADIUS = 0.24


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def length(a):
    return math.sqrt(dot(a, a))


def normalize(a):
    ln = length(a)
    if ln < 1e-9:
        return (0.0, 1.0, 0.0)
    return (a[0] / ln, a[1] / ln, a[2] / ln)


def ray_aabb(o, d, box, tmax=1e9):
    """Slab test.  ``box`` = (minx, miny, minz, maxx, maxy, maxz, ...).
    Returns (t, axis_index, sign) of the entry point or None."""
    tmin = 0.0
    axis = -1
    sign = 0.0
    for i in range(3):
        di = d[i]
        lo = box[i]
        hi = box[i + 3]
        if abs(di) < 1e-12:
            if o[i] < lo or o[i] > hi:
                return None
            continue
        inv = 1.0 / di
        t1 = (lo - o[i]) * inv
        t2 = (hi - o[i]) * inv
        s = -1.0
        if t1 > t2:
            t1, t2 = t2, t1
            s = 1.0
        if t1 > tmin:
            tmin = t1
            axis = i
            sign = s
        if t2 < tmax:
            tmax = t2
        if tmin > tmax:
            return None
    if axis < 0:          # origin inside the box
        return (0.0, 2, 1.0)
    return (tmin, axis, sign)


def ray_sphere(o, d, c, r):
    oc = sub(o, c)
    b = dot(oc, d)
    cc = dot(oc, oc) - r * r
    h = b * b - cc
    if h < 0:
        return None
    h = math.sqrt(h)
    t = -b - h
    if t < 0:
        t = -b + h
        if t < 0:
            return None
    return t


def ray_capsule(o, d, pa, pb, r):
    """Ray vs capsule (segment pa-pb, radius r).  Returns t or None."""
    ba = sub(pb, pa)
    oa = sub(o, pa)
    baba = dot(ba, ba)
    bard = dot(ba, d)
    baoa = dot(ba, oa)
    rdoa = dot(d, oa)
    oaoa = dot(oa, oa)
    a = baba - bard * bard
    b = baba * rdoa - baoa * bard
    c = baba * oaoa - baoa * baoa - r * r * baba
    h = b * b - a * c
    if h >= 0.0 and abs(a) > 1e-9:
        t = (-b - math.sqrt(h)) / a
        y = baoa + t * bard
        if 0.0 < y < baba and t >= 0.0:
            return t
        # caps
        oc = oa if y <= 0.0 else sub(o, pb)
        return _cap(d, oc, r)
    # parallel to axis: test both caps
    ts = [x for x in (_cap(d, oa, r), _cap(d, sub(o, pb), r)) if x is not None]
    return min(ts) if ts else None


def _cap(d, oc, r):
    b = dot(d, oc)
    c = dot(oc, oc) - r * r
    h = b * b - c
    if h <= 0.0:
        return None
    t = -b - math.sqrt(h)
    return t if t >= 0.0 else None


def hit_combatant(o, d, feet, crouched, max_t=1e9):
    """Test a ray against a combatant standing at ``feet``.
    Returns (t, is_headshot) or None."""
    h = CROUCH_HEIGHT if crouched else STAND_HEIGHT
    head_c = (feet[0], feet[1], feet[2] + h - HEAD_RADIUS - 0.02)
    th = ray_sphere(o, d, head_c, HEAD_RADIUS)
    pa = (feet[0], feet[1], feet[2] + BODY_BOTTOM + BODY_RADIUS * 0.5)
    pb = (feet[0], feet[1], feet[2] + h - 0.66)      # capsule top ends below the head
    tb = ray_capsule(o, d, pa, pb, BODY_RADIUS)
    best = None
    if th is not None and th <= max_t:
        best = (th, True)
    if tb is not None and tb <= max_t and (best is None or tb < best[0] - 0.05):
        best = (tb, False)
    return best


def first_static_hit(o, d, boxes, max_t):
    """Closest static box hit along the ray (t, box) or (None, None)."""
    best_t = max_t
    best = None
    for bx in boxes:
        r = ray_aabb(o, d, bx, best_t)
        if r is not None and r[0] < best_t:
            best_t = r[0]
            best = bx
    if best is None:
        return None, None
    return best_t, best


def spread_dir(d, spread_deg, rnd):
    """Randomly perturb direction ``d`` inside a cone (uniform disc)."""
    if spread_deg <= 0.0:
        return d
    # orthonormal basis
    up = (0.0, 0.0, 1.0) if abs(d[2]) < 0.95 else (1.0, 0.0, 0.0)
    rx = normalize((d[1] * up[2] - d[2] * up[1], d[2] * up[0] - d[0] * up[2],
                    d[0] * up[1] - d[1] * up[0]))
    ry = (d[1] * rx[2] - d[2] * rx[1], d[2] * rx[0] - d[0] * rx[2], d[0] * rx[1] - d[1] * rx[0])
    ang = math.radians(spread_deg) * math.sqrt(rnd.random())
    phi = rnd.random() * math.tau
    s = math.tan(ang)
    ox = math.cos(phi) * s
    oy = math.sin(phi) * s
    return normalize((d[0] + rx[0] * ox + ry[0] * oy, d[1] + rx[1] * ox + ry[1] * oy,
                      d[2] + rx[2] * ox + ry[2] * oy))
