"""CORAL TOWN: an underwater neighbourhood on the sea floor.

A pineapple house, a stone tiki-head house (sniper perch on top, reached by
jump pads), a low rock house you can climb, a glass air dome with a tree
inside, a ship-hull diner, coral spires, kelp, clams and boulders.
Seeded so every machine and the server build the same collision.
"""

import math
import random

HALF = 32.0
WALL_H = 14.0
CEILING_Z = 24.0
CATWALK_Z = 7.0           # tiki head top
PINEAPPLE = (-17.0, 13.0)
TIKI = (0.0, 19.0)
ROCK = (17.0, 13.0)
DOME = (0.0, -13.0)
DOME_R = 8.0
DINER = (-19.0, -16.0)


def box(cx, cy, z0, sx, sy, sz, kind):
    return (cx - sx / 2, cy - sy / 2, z0, cx + sx / 2, cy + sy / 2, z0 + sz, kind)


SPAWNS = [(-28, -28, 45), (28, 28, 225), (-28, 28, 315), (28, -28, 135),
          (0, -29, 0), (0, 29, 180), (-29, 0, 270), (29, 0, 90),
          (-6, 0, 60), (9, -6.5, 240), (0, -13, 0), (14, -20, 30)]
LOOT_BOXES = [(-8, -4), (8, 4), (-25, 6), (25, -6), (0, -9), (0, 19, CATWALK_Z),
              (-12, -26), (12, 26), (20, -14), (-22, 22)]
CHARGE_PORTS = [(-24, -6), (24, 6), (-6, 26), (6, -26)]
HEAL_SPOTS = [(-10, 18), (10, 18), (-26, -20), (26, 20), (3, -16), (-4, 4), (22, -24),
              (-14, -6)]
JUMP_PADS = [(-4.5, 12.0, -0.8, 18.6, CATWALK_Z), (4.5, 12.0, 0.8, 18.6, CATWALK_Z)]
TURRETS = [(-17.0, 16.3, 3.5, 0), (17.0, 9.3, 1.6, 180)]
TRAP_SPOTS = [(-8, 10), (8, -10), (-20, 26), (20, -26), (-4, -25), (4, 25), (-27, -2), (27, 2)]
DRONE_SPAWNS = [(-20, -20, 11), (20, 20, 11), (-20, 20, 11), (20, -20, 11), (0, 0, 12)]
GRAVITY_ZONES = [(-24, -14, 3.0), (24, 14, 3.0)]
LASER_SWEEPERS = [(-12, 24, 6.0), (12, -24, 6.0)]
MINE_FIELD = [(-6, -6), (6, 6), (-12, 6), (12, -6), (-26, 14), (26, -14), (-4, 26),
              (4, -26), (-20, -8), (20, 8), (-2, 9), (2, -2)]


def build():
    rng = random.Random(1999)
    b = []
    t = 1.0
    b.append(box(0, HALF + t / 2, 0, 2 * HALF + 2 * t, t, WALL_H + 1, "wall"))
    b.append(box(0, -HALF - t / 2, 0, 2 * HALF + 2 * t, t, WALL_H + 1, "wall"))
    b.append(box(HALF + t / 2, 0, 0, t, 2 * HALF, WALL_H + 1, "wall"))
    b.append(box(-HALF - t / 2, 0, 0, t, 2 * HALF, WALL_H + 1, "wall"))
    b.append(box(0, 0, CEILING_Z, 2 * HALF + 2, 2 * HALF + 2, 1.0, "ceiling"))
    decor = []
    # houses
    b.append(box(PINEAPPLE[0], PINEAPPLE[1], 0, 6.2, 6.2, 7.6, "house"))
    decor.append({"k": "pineapple", "x": PINEAPPLE[0], "y": PINEAPPLE[1]})
    b.append(box(TIKI[0], TIKI[1], 0, 4.6, 4.6, CATWALK_Z, "house"))
    decor.append({"k": "tiki", "x": TIKI[0], "y": TIKI[1]})
    b.append(box(ROCK[0], ROCK[1], 0, 7.0, 7.0, 1.0, "rock"))
    b.append(box(ROCK[0], ROCK[1], 1.0, 4.0, 4.0, 1.0, "rock"))
    decor.append({"k": "rockhouse", "x": ROCK[0], "y": ROCK[1]})
    # glass dome: a ring of posts (two doorways, north and south) + a tree inside
    n = 44
    for i in range(n):
        a = math.tau * i / n
        deg = math.degrees(a) % 360
        if abs(deg - 90) < 14 or abs(deg - 270) < 14:
            continue
        x = DOME[0] + math.cos(a) * DOME_R
        y = DOME[1] + math.sin(a) * DOME_R
        b.append(box(x, y, 0, 1.25, 1.25, 4.5, "glass"))
    b.append(box(DOME[0] + 3.0, DOME[1] + 1.5, 0, 0.9, 0.9, 6.0, "trunk"))
    b.append(box(DOME[0] - 3.2, DOME[1] - 2.0, 0, 2.0, 1.0, 0.76, "table"))
    decor.append({"k": "dome", "x": DOME[0], "y": DOME[1], "r": DOME_R})
    # ship-hull diner
    b.append(box(DINER[0], DINER[1], 0, 10.0, 6.0, 4.2, "house"))
    decor.append({"k": "diner", "x": DINER[0], "y": DINER[1]})
    # little boat-car parked in the street
    b.append(box(9.0, -3.5, 0, 3.6, 1.8, 1.3, "prop"))
    decor.append({"k": "boat", "x": 9.0, "y": -3.5})
    b.append(box(-10.0, 3.0, 0, 1.8, 3.6, 1.3, "prop"))
    decor.append({"k": "boat", "x": -10.0, "y": 3.0, "h": 90})

    clear = [(x, y, 2.8) for (x, y, _) in SPAWNS]
    clear += [(p[0], p[1], 2.2) for p in LOOT_BOXES + CHARGE_PORTS + HEAL_SPOTS]
    clear += [(p[0], p[1], 2.4) for p in JUMP_PADS + TRAP_SPOTS]
    clear += [(p[0], p[1], 1.6) for p in MINE_FIELD]
    clear += [(p[0], p[1], p[2] + 1.0) for p in LASER_SWEEPERS]
    for (x, y, tx, ty, _) in JUMP_PADS:
        for k in range(1, 5):
            clear.append((x + (tx - x) * k / 5, y + (ty - y) * k / 5, 2.0))
    blocked = [(PINEAPPLE[0] - 5, PINEAPPLE[0] + 5, PINEAPPLE[1] - 5, PINEAPPLE[1] + 5),
               (TIKI[0] - 4, TIKI[0] + 4, TIKI[1] - 4, TIKI[1] + 4),
               (ROCK[0] - 5.5, ROCK[0] + 5.5, ROCK[1] - 5.5, ROCK[1] + 5.5),
               (DOME[0] - 10, DOME[0] + 10, DOME[1] - 10, DOME[1] + 10),
               (DINER[0] - 7, DINER[0] + 7, DINER[1] - 5, DINER[1] + 5),
               (6, 12, -6, -1), (-12, -8, 0, 6)]

    def free(x, y, r):
        if abs(x) > HALF - 1.5 - r or abs(y) > HALF - 1.5 - r:
            return False
        for (x0, x1, y0, y1) in blocked:
            if x0 - r < x < x1 + r and y0 - r < y < y1 + r:
                return False
        return all(math.hypot(x - cx, y - cy) >= cr + r for (cx, cy, cr) in clear)

    # coral spires and boulders (cover)
    placed = 0
    tries = 0
    while placed < 22 and tries < 3000:
        tries += 1
        x = rng.uniform(-HALF + 2, HALF - 2)
        y = rng.uniform(-HALF + 2, HALF - 2)
        big = rng.random() < 0.45
        r = rng.uniform(1.0, 1.6) if big else rng.uniform(0.5, 0.8)
        if not free(x, y, r + 0.8):
            continue
        h = rng.uniform(1.4, 2.6) if big else rng.uniform(2.0, 4.5)
        kind = "boulder" if big else "coral"
        b.append(box(x, y, 0, 2 * r, 2 * r, h, "rock" if big else "coral"))
        decor.append({"k": kind, "x": x, "y": y, "r": r, "h": h, "seed": rng.random(),
                      "c": rng.randrange(4)})
        blocked.append((x - r - 1, x + r + 1, y - r - 1, y + r + 1))
        placed += 1
    # giant clams (low cover) and an anchor
    for (x, y) in [(-6, -22), (14, 2), (-24, 14), (24, -16)]:
        if free(x, y, 1.2):
            b.append(box(x, y, 0, 2.2, 1.6, 0.9, "rock"))
            decor.append({"k": "clam", "x": x, "y": y, "seed": rng.random()})
    b.append(box(-27.0, -10.0, 0, 1.0, 3.6, 3.2, "prop"))
    decor.append({"k": "anchor", "x": -27.0, "y": -10.0})
    # kelp and small coral: no collision, you can hide in the kelp
    for _ in range(70):
        x = rng.uniform(-HALF + 1, HALF - 1)
        y = rng.uniform(-HALF + 1, HALF - 1)
        if not free(x, y, 0.3):
            continue
        decor.append({"k": "kelp", "x": x, "y": y, "h": rng.uniform(2.5, 6.5),
                      "seed": rng.random()})
    for _ in range(40):
        x = rng.uniform(-HALF + 1, HALF - 1)
        y = rng.uniform(-HALF + 1, HALF - 1)
        if not free(x, y, 0.2):
            continue
        decor.append({"k": "smallcoral", "x": x, "y": y, "seed": rng.random(),
                      "c": rng.randrange(4)})
    # scenery beyond the play area: dunes, far coral and jellyfish
    for _ in range(60):
        a = rng.uniform(0, math.tau)
        d = rng.uniform(HALF + 3, HALF + 30)
        decor.append({"k": "farrock", "x": math.cos(a) * d, "y": math.sin(a) * d,
                      "r": rng.uniform(2, 6), "seed": rng.random()})
    for _ in range(14):
        decor.append({"k": "jelly", "x": rng.uniform(-30, 30), "y": rng.uniform(-30, 30),
                      "z": rng.uniform(7, 16), "seed": rng.random()})
    theme = {
        "sky": True, "water": True, "ground": "sand", "reflections": False, "hue_cycle": False,
        "ambient": (0.30, 0.42, 0.47), "sun_dir": (0.15, 0.25, 0.95),
        "sun_col": (0.55, 0.68, 0.62), "fog": (0.06, 0.30, 0.42, 0.026),
        "sky_top": (0.35, 0.72, 0.85), "sky_horizon": (0.05, 0.25, 0.36),
    }
    return {
        "HALF": HALF, "WALL_H": WALL_H, "CEILING_Z": CEILING_Z, "CATWALK_Z": CATWALK_Z,
        "STATIC_BOXES": b, "SLIDING_WALLS": [], "SPAWNS": SPAWNS, "LOOT_BOXES": LOOT_BOXES,
        "CHARGE_PORTS": CHARGE_PORTS, "JUMP_PADS": JUMP_PADS, "TURRETS": TURRETS,
        "TRAP_SPOTS": TRAP_SPOTS, "DRONE_SPAWNS": DRONE_SPAWNS, "GRAVITY_ZONES": GRAVITY_ZONES,
        "LASER_SWEEPERS": LASER_SWEEPERS, "MINE_FIELD": MINE_FIELD, "HOLO_SIGNS": [],
        "DECOR": decor, "THEME": theme, "HEAL_SPOTS": HEAL_SPOTS, "NAV_TOP": 7.5,
    }
