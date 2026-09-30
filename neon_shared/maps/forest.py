"""FOREST: an open woodland clearing with a log cabin (rooftop deck), two
watchtowers, boulders, fallen logs, lots of trees and bushes to hide in.

Everything is generated from a fixed seed so the client, the bots and the
server all build exactly the same map.
"""

import math
import random

HALF = 32.0
WALL_H = 12.0
CEILING_Z = 22.0
CATWALK_Z = 4.5          # watchtower deck height
ROOF_Z = 3.3             # cabin roof deck
TRUNK_H = 8.0


def box(cx, cy, z0, sx, sy, sz, kind):
    return (cx - sx / 2, cy - sy / 2, z0, cx + sx / 2, cy + sy / 2, z0 + sz, kind)


def _cabin(b):
    """10 x 7 m log cabin centred on the origin: doors north/south, windows east/west."""
    x0, x1, y0, y1, t, h = -5.0, 5.0, -3.5, 3.5, 0.35, 3.0
    for (yy, sgn) in ((y0, 1), (y1, -1)):
        wy = yy + sgn * t / 2
        # door gap 1.8 m wide in the middle
        b.append(box((x0 - 0.9) / 2, wy, 0, -0.9 - x0, t, h, "cabin"))
        b.append(box((x1 + 0.9) / 2, wy, 0, x1 - 0.9, t, h, "cabin"))
        b.append(box(0, wy, 2.3, 1.8, t, h - 2.3, "cabin"))       # lintel
    for xx, sgn in ((x0, 1), (x1, -1)):
        wx = xx + sgn * t / 2
        # window 2 m wide between z 1.1 and 2.0
        b.append(box(wx, (y0 + t - 1.0) / 2, 0, t, -1.0 - y0 - t, h, "cabin"))
        b.append(box(wx, (y1 - t + 1.0) / 2, 0, t, y1 - t - 1.0, h, "cabin"))
        b.append(box(wx, 0, 0, t, 2.0, 1.1, "cabin"))
        b.append(box(wx, 0, 2.0, t, 2.0, h - 2.0, "cabin"))
    b.append(box(0, 0, h, 10.8, 7.8, ROOF_Z - h, "roof"))
    # low railing around the roof deck (gaps where the jump pads land)
    for sgn in (1, -1):
        b.append(box(0, sgn * 3.8, ROOF_Z, 10.8, 0.2, 0.5, "rail"))
        b.append(box(sgn * 5.3, sgn * 2.4, ROOF_Z, 0.2, 3.0, 0.5, "rail"))
        b.append(box(sgn * 5.3, -sgn * 2.4, ROOF_Z, 0.2, 3.0, 0.5, "rail"))
    # furniture inside
    b.append(box(-2.4, 1.6, 0, 1.8, 0.9, 0.78, "table"))
    b.append(box(3.4, -2.4, 0, 1.4, 1.4, 1.0, "crate"))
    b.append(box(3.8, 2.6, 0, 1.2, 0.6, 1.6, "shelf"))


def _tower(b, cx, cy):
    """Wooden watchtower: four posts, a 4.4 m deck at CATWALK_Z, rails with one open side."""
    for sx in (1, -1):
        for sy in (1, -1):
            b.append(box(cx + sx * 1.9, cy + sy * 1.9, 0, 0.35, 0.35, CATWALK_Z - 0.3, "post"))
    b.append(box(cx, cy, CATWALK_Z - 0.3, 4.4, 4.4, 0.3, "deck"))
    # rails on three sides; the side facing the arena centre stays open (jump pad landing)
    open_side = "x" if abs(cx) > abs(cy) else "y"
    sgn_x = -1 if cx > 0 else 1
    sgn_y = -1 if cy > 0 else 1
    for s in (1, -1):
        if not (open_side == "y" and s == sgn_y):
            b.append(box(cx, cy + s * 2.1, CATWALK_Z, 4.4, 0.15, 1.0, "rail"))
        if not (open_side == "x" and s == sgn_x):
            b.append(box(cx + s * 2.1, cy, CATWALK_Z, 0.15, 4.4, 1.0, "rail"))


TOWERS = [(-22.0, 20.0), (22.0, -20.0)]
BIG_OAKS = [(-13.0, -17.0), (13.0, 17.0)]

SPAWNS = [(-28, -28, 45), (28, 28, 225), (-28, 28, 315), (28, -28, 135),
          (0, -28, 0), (0, 28, 180), (-28, 0, 270), (28, 0, 90),
          (-12, -9, 30), (12, 9, 210), (-17, 10, 300), (17, -10, 120)]
LOOT_BOXES = [(-9, -6), (9, 6), (-24, 8), (24, -8), (0, 0), (-16, -26), (16, 26),
              (20, 4), (-20, -4), (-22, 20, CATWALK_Z), (22, -20, CATWALK_Z),
              (0, 0, ROOF_Z)]
CHARGE_PORTS = [(-20, 26), (20, -26), (-6, -13), (6, 13)]
JUMP_PADS = [  # (x, y, target_x, target_y, target_z)
    (-9.0, 0.0, -3.5, 0.0, ROOF_Z), (9.0, 0.0, 3.5, 0.0, ROOF_Z),
    (-16.5, 20.0, -21.5, 20.0, CATWALK_Z), (16.5, -20.0, 21.5, -20.0, CATWALK_Z),
]
TURRETS = [(BIG_OAKS[0][0], BIG_OAKS[0][1] + 0.7, 3.4, 0),
           (BIG_OAKS[1][0], BIG_OAKS[1][1] - 0.7, 3.4, 180)]
TRAP_SPOTS = [(-8, 9), (8, -9), (-18, 23), (18, -23), (-3, -21), (3, 21), (-26, -4), (26, 4)]
DRONE_SPAWNS = [(-20, -20, 11), (20, 20, 11), (-20, 20, 11), (20, -20, 11), (0, 0, 12)]
GRAVITY_ZONES = [(-24, -14, 3.0), (24, 14, 3.0)]
LASER_SWEEPERS = [(-12, 22, 6.0), (12, -22, 6.0)]
MINE_FIELD = [(-6, -9), (6, 9), (-12, 12), (12, -12), (-26, 20), (26, -20), (-4, 24),
              (4, -24), (-20, -12), (20, 12), (-2, 11), (2, -11)]
CAMPFIRE = (0.0, -9.5)


def _clear_spots():
    """Points trees/rocks must keep away from: (x, y, radius)."""
    pts = [(x, y, 3.0) for (x, y, _) in SPAWNS]
    pts += [(p[0], p[1], 2.2) for p in LOOT_BOXES]
    pts += [(p[0], p[1], 2.2) for p in CHARGE_PORTS]
    pts += [(p[0], p[1], 2.6) for p in JUMP_PADS]
    pts += [(p[0], p[1], 2.0) for p in TRAP_SPOTS]
    pts += [(p[0], p[1], 1.6) for p in MINE_FIELD]
    pts += [(p[0], p[1], p[2] + 1.0) for p in LASER_SWEEPERS]
    pts += [(CAMPFIRE[0], CAMPFIRE[1], 3.0)]
    # jump-pad flight lanes
    for (x, y, tx, ty, _) in JUMP_PADS:
        for k in range(1, 5):
            f = k / 5.0
            pts.append((x + (tx - x) * f, y + (ty - y) * f, 2.0))
    return pts


def build():
    rng = random.Random(4471)
    b = []
    t = 1.0
    # invisible boundary (the visuals put a dense tree line and a fence here)
    b.append(box(0, HALF + t / 2, 0, 2 * HALF + 2 * t, t, WALL_H + 1, "wall"))
    b.append(box(0, -HALF - t / 2, 0, 2 * HALF + 2 * t, t, WALL_H + 1, "wall"))
    b.append(box(HALF + t / 2, 0, 0, t, 2 * HALF, WALL_H + 1, "wall"))
    b.append(box(-HALF - t / 2, 0, 0, t, 2 * HALF, WALL_H + 1, "wall"))
    b.append(box(0, 0, CEILING_Z, 2 * HALF + 2, 2 * HALF + 2, 1.0, "ceiling"))
    _cabin(b)
    for (x, y) in TOWERS:
        _tower(b, x, y)

    decor = [{"k": "cabin", "x": 0.0, "y": 0.0}, {"k": "campfire", "x": CAMPFIRE[0],
                                                     "y": CAMPFIRE[1]}]
    for (x, y) in TOWERS:
        decor.append({"k": "tower", "x": x, "y": y})
    b.append(box(CAMPFIRE[0], CAMPFIRE[1], 0, 1.3, 1.3, 0.3, "rock"))

    blocked = [(-7.0, 7.0, -5.5, 5.5)]           # cabin + porch
    blocked += [(x - 3.5, x + 3.5, y - 3.5, y + 3.5) for (x, y) in TOWERS]
    clear = _clear_spots()

    def free(x, y, r):
        if abs(x) > HALF - 1.2 - r or abs(y) > HALF - 1.2 - r:
            return False
        for (x0, x1, y0, y1) in blocked:
            if x0 - r < x < x1 + r and y0 - r < y < y1 + r:
                return False
        for (cx, cy, cr) in clear:
            if math.hypot(x - cx, y - cy) < cr + r:
                return False
        return True

    # big oaks carrying the sentry turrets
    for (x, y) in BIG_OAKS:
        b.append(box(x, y, 0, 1.2, 1.2, TRUNK_H + 1, "trunk"))
        decor.append({"k": "oak", "x": x, "y": y, "s": 1.5, "r": 0.6})
        blocked.append((x - 1.5, x + 1.5, y - 1.5, y + 1.5))

    # boulders
    for (x, y, sx, sy, sz) in [(-6, -19, 3.0, 2.2, 1.6), (6, 19, 3.0, 2.2, 1.6),
                               (-25, -13, 2.4, 3.2, 1.9), (25, 13, 2.4, 3.2, 1.9),
                               (-15, 2, 2.0, 1.6, 1.2), (15, -2, 2.0, 1.6, 1.2),
                               (-27, 26, 3.0, 2.6, 2.4), (27, -26, 3.0, 2.6, 2.4),
                               (11, -15, 1.4, 1.4, 1.0), (-11, 15, 1.4, 1.4, 1.0)]:
        b.append(box(x, y, 0, sx, sy, sz, "rock"))
        decor.append({"k": "rock", "x": x, "y": y, "sx": sx, "sy": sy, "sz": sz,
                      "seed": rng.random()})
        blocked.append((x - sx / 2 - 0.8, x + sx / 2 + 0.8, y - sy / 2 - 0.8, y + sy / 2 + 0.8))

    # fallen logs (waist-high cover)
    for (x, y, axis, ln) in [(-18, -20, "x", 5.0), (18, 20, "x", 5.0), (-4, 16, "y", 4.0),
                             (4, -16, "y", 4.0), (-26, -22, "y", 4.5), (26, 22, "y", 4.5),
                             (-9, 24, "x", 4.0), (9, -24, "x", 4.0)]:
        sx, sy = (ln, 0.9) if axis == "x" else (0.9, ln)
        b.append(box(x, y, 0, sx, sy, 0.9, "log"))
        decor.append({"k": "log", "x": x, "y": y, "axis": axis, "len": ln})
        blocked.append((x - sx / 2 - 0.9, x + sx / 2 + 0.9, y - sy / 2 - 0.9, y + sy / 2 + 0.9))

    # trees
    trees = []
    tries = 0
    while len(trees) < 78 and tries < 6000:
        tries += 1
        x = rng.uniform(-HALF + 1.5, HALF - 1.5)
        y = rng.uniform(-HALF + 1.5, HALF - 1.5)
        r = rng.uniform(0.22, 0.42)
        if not free(x, y, 1.0):
            continue
        if any(math.hypot(x - tx, y - ty) < 3.4 for (tx, ty, _) in trees):
            continue
        trees.append((x, y, r))
    for (x, y, r) in trees:
        b.append(box(x, y, 0, 2 * r, 2 * r, TRUNK_H, "trunk"))
        kind = "pine" if rng.random() < 0.62 else "oak"
        decor.append({"k": kind, "x": x, "y": y, "r": r, "s": rng.uniform(0.85, 1.25),
                      "h": rng.uniform(0, 360)})

    # bushes: no collision - walk into them and hide
    n = 0
    tries = 0
    while n < 60 and tries < 4000:
        tries += 1
        x = rng.uniform(-HALF + 1.5, HALF - 1.5)
        y = rng.uniform(-HALF + 1.5, HALF - 1.5)
        if not free(x, y, 0.2):
            continue
        if any(math.hypot(x - tx, y - ty) < r + 1.0 for (tx, ty, r) in trees):
            continue
        decor.append({"k": "bush", "x": x, "y": y, "s": rng.uniform(0.8, 1.35),
                      "seed": rng.random()})
        n += 1

    # scenery outside the play area (no collision needed)
    for i in range(150):
        a = rng.uniform(0, math.tau)
        d = rng.uniform(HALF + 2.0, HALF + 26.0)
        x, y = math.cos(a) * d, math.sin(a) * d
        x = max(-HALF - 30, min(HALF + 30, x))
        y = max(-HALF - 30, min(HALF + 30, y))
        if max(abs(x), abs(y)) < HALF + 1.5:
            continue
        decor.append({"k": "pine" if rng.random() < 0.7 else "oak", "x": x, "y": y,
                      "r": rng.uniform(0.3, 0.5), "s": rng.uniform(1.0, 1.6),
                      "h": rng.uniform(0, 360), "far": True})
    decor.append({"k": "fence"})

    theme = {
        "sky": True, "ground": "grass", "reflections": False, "hue_cycle": False,
        "ambient": (0.36, 0.40, 0.38), "sun_dir": (0.45, -0.35, 0.82),
        "sun_col": (0.95, 0.86, 0.70), "fog": (0.62, 0.72, 0.76, 0.0135),
        "sky_top": (0.22, 0.44, 0.80), "sky_horizon": (0.70, 0.80, 0.86),
        # evening end of the day cycle
        "dusk_ambient": (0.20, 0.17, 0.22), "dusk_sun_col": (1.0, 0.52, 0.26),
        "dusk_fog": (0.46, 0.36, 0.38, 0.016), "dusk_sky_top": (0.16, 0.14, 0.34),
        "dusk_sky_horizon": (0.92, 0.50, 0.32), "cycle": 300.0,
    }
    return {
        "HALF": HALF, "WALL_H": WALL_H, "CEILING_Z": CEILING_Z, "CATWALK_Z": CATWALK_Z,
        "STATIC_BOXES": b, "SLIDING_WALLS": [], "SPAWNS": SPAWNS, "LOOT_BOXES": LOOT_BOXES,
        "CHARGE_PORTS": CHARGE_PORTS, "JUMP_PADS": JUMP_PADS, "TURRETS": TURRETS,
        "TRAP_SPOTS": TRAP_SPOTS, "DRONE_SPAWNS": DRONE_SPAWNS, "GRAVITY_ZONES": GRAVITY_ZONES,
        "LASER_SWEEPERS": LASER_SWEEPERS, "MINE_FIELD": MINE_FIELD, "HOLO_SIGNS": [],
        "DECOR": decor, "THEME": theme,
    }
