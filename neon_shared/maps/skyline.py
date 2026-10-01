"""SKYLINE: rooftop fight over a night city.

Nine skyscrapers in a 3 x 3 grid.  The four corner towers are 3 m lower than
the others.  Some gaps have bridges (flat between the centre and the edge
towers, stair bridges down to the corners); the rest you have to jump.
Jump pads on the corner roofs launch you back up.  A small house stands on
the centre tower.  Fall to the street and you die.
"""

import math
import random

HALF = 32.0
WALL_H = 60.0
CEILING_Z = 60.0
CATWALK_Z = 24.0
HIGH = 24.0                 # centre + edge towers
LOW = 21.0                  # corner towers
KILL_Z = 12.0
SIZE = 16.0                 # tower footprint (gaps between towers are 4 m)
CENTERS = (-20.0, 0.0, 20.0)
HOUSE = (0.0, 2.0)          # penthouse on the centre roof
HOUSE_W, HOUSE_D, HOUSE_H = 8.0, 6.0, 3.0


def box(cx, cy, z0, sx, sy, sz, kind):
    return (cx - sx / 2, cy - sy / 2, z0, cx + sx / 2, cy + sy / 2, z0 + sz, kind)


def roof(i, j):
    """Roof height of tower (i, j), i/j in -1..1."""
    return LOW if (i != 0 and j != 0) else HIGH


def build():
    rng = random.Random(7070)
    b = []
    decor = []
    t = 1.0
    # invisible walls keep everyone over the city
    b.append(box(0, HALF + t / 2, 0, 2 * HALF + 2 * t, t, WALL_H + 1, "wall"))
    b.append(box(0, -HALF - t / 2, 0, 2 * HALF + 2 * t, t, WALL_H + 1, "wall"))
    b.append(box(HALF + t / 2, 0, 0, t, 2 * HALF, WALL_H + 1, "wall"))
    b.append(box(-HALF - t / 2, 0, 0, t, 2 * HALF, WALL_H + 1, "wall"))
    b.append(box(0, 0, CEILING_Z, 2 * HALF + 2, 2 * HALF + 2, 1.0, "ceiling"))
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            x, y = CENTERS[i + 1], CENTERS[j + 1]
            h = roof(i, j)
            b.append(box(x, y, 0, SIZE, SIZE, h, "tower"))
            decor.append({"k": "tower", "x": x, "y": y, "h": h, "seed": rng.random()})
            # low parapet on the outer edges only (the inner edges are open for jumping)
            for (dx, dy) in ((i, 0), (0, j)):
                if dx == 0 and dy == 0:
                    continue
                if dx:
                    b.append(box(x + dx * (SIZE / 2 - 0.15), y, h, 0.3, SIZE, 0.7, "parapet"))
                if dy:
                    b.append(box(x, y + dy * (SIZE / 2 - 0.15), h, SIZE, 0.3, 0.7, "parapet"))
    # flat bridges: centre <-> edge towers (2.4 m wide, across the 4 m gap)
    for (dx, dy) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if dx:
            b.append(box(dx * 10.0, 0, HIGH - 0.3, 4.4, 2.4, 0.3, "bridge"))
        else:
            b.append(box(0, dy * 10.0, HIGH - 0.3, 2.4, 4.4, 0.3, "bridge"))
    # stair bridges down to each corner (one per corner; the other gap is a jump)
    stairs = [((-1, -1), "x"), ((1, 1), "x"), ((-1, 1), "y"), ((1, -1), "y")]
    for (i, j), axis in stairs:
        cx, cy = CENTERS[i + 1], CENTERS[j + 1]
        n = 7
        for k in range(n):
            f = (k + 0.5) / n
            z = HIGH - (HIGH - LOW) * (k + 1) / n
            if axis == "x":
                # from the edge tower (0, j) down to the corner, along x
                x = i * (8.0 + 4.0 * f)
                b.append(box(x, cy, z - 0.3, 4.0 / n + 0.02, 2.4, 0.3, "stair"))
            else:
                y = j * (8.0 + 4.0 * f)
                b.append(box(cx, y, z - 0.3, 2.4, 4.0 / n + 0.02, 0.3, "stair"))
        decor.append({"k": "stairs", "x": cx, "y": cy, "i": i, "j": j, "axis": axis})
    # penthouse house on the centre roof (doors front and back, windows on the sides)
    hx, hy = HOUSE
    w, d, hh = HOUSE_W, HOUSE_D, HOUSE_H
    th = 0.25
    z0 = HIGH
    for sy in (-1, 1):
        wy = hy + sy * (d / 2 - th / 2)
        b.append(box(hx - (w / 4 + 0.45), wy, z0, w / 2 - 0.9, th, hh, "house"))
        b.append(box(hx + (w / 4 + 0.45), wy, z0, w / 2 - 0.9, th, hh, "house"))
        b.append(box(hx, wy, z0 + 2.3, 1.8, th, hh - 2.3, "house"))
    for sx in (-1, 1):
        wx = hx + sx * (w / 2 - th / 2)
        b.append(box(wx, hy, z0, th, d - 2 * th, 1.0, "house"))
        b.append(box(wx, hy, z0 + 2.1, th, d - 2 * th, hh - 2.1, "house"))
        b.append(box(wx, hy - (d / 2 - 0.7), z0 + 1.0, th, 1.4 - th, 1.1, "house"))
        b.append(box(wx, hy + (d / 2 - 0.7), z0 + 1.0, th, 1.4 - th, 1.1, "house"))
    b.append(box(hx, hy, z0 + hh, w + 0.4, d + 0.4, 0.25, "house_roof"))
    b.append(box(hx - 2.0, hy + 1.2, z0, 1.6, 0.8, 0.75, "table"))
    b.append(box(hx + 2.6, hy - 1.6, z0, 2.0, 0.9, 0.8, "couch"))
    decor.append({"k": "house", "x": hx, "y": hy})
    # stairs up to the house roof (outside, west wall)
    for k in range(7):
        b.append(box(hx - w / 2 - 0.9, hy - d / 2 + 0.4 + k * 0.72, z0, 1.6, 0.72,
                     0.43 * (k + 1), "stair"))
    # rooftop clutter: AC units, vents, water towers, billboards, antennas
    props = [
        (-20, 0, "ac"), (20, 0, "ac"), (0, -20, "ac"), (0, 20, "ac"),
        (-25, -5, "vent"), (25, 5, "vent"), (4, 24, "vent"), (-4, -24, "vent"),
        (-17, -17, "watertower"), (17, 17, "watertower"),
        (-24, 20, "billboard"), (24, -20, "billboard"),
        (-6, -6, "ac"), (6, -6, "vent"), (-20, -24, "antenna"), (20, 24, "antenna"),
        (-15, 22, "ac"), (15, -22, "ac"), (22, 15, "vent"), (-22, -15, "vent"),
    ]
    for (x, y, kind) in props:
        i = 0 if abs(x) < 10 else (1 if x > 0 else -1)
        j = 0 if abs(y) < 10 else (1 if y > 0 else -1)
        z = roof(i, j)
        if kind == "ac":
            b.append(box(x, y, z, 2.2, 1.6, 1.3, "prop"))
        elif kind == "vent":
            b.append(box(x, y, z, 1.2, 1.2, 1.0, "prop"))
        elif kind == "watertower":
            b.append(box(x, y, z + 2.6, 3.2, 3.2, 3.2, "prop"))       # tank on stilts
        elif kind == "billboard":
            b.append(box(x, y, z, 0.4, 6.0, 3.6, "prop"))
        elif kind == "antenna":
            b.append(box(x, y, z, 0.4, 0.4, 7.0, "prop"))
        decor.append({"k": kind, "x": x, "y": y, "z": z, "seed": rng.random()})
    decor.append({"k": "helipad", "x": 20.0, "y": 0.0, "z": HIGH})
    # the city around and below
    for _ in range(70):
        a = rng.uniform(0, math.tau)
        dist = rng.uniform(HALF + 10, HALF + 90)
        decor.append({"k": "fartower", "x": math.cos(a) * dist, "y": math.sin(a) * dist,
                      "h": rng.uniform(20, 75), "w": rng.uniform(8, 18), "seed": rng.random()})
    decor.append({"k": "plane"})

    def at(i, j, dx=0.0, dy=0.0, dz=0.0):
        return (CENTERS[i + 1] + dx, CENTERS[j + 1] + dy, roof(i, j) + dz)

    spawns = []
    for (i, j, yaw) in [(-1, -1, 45), (1, 1, 225), (-1, 1, 315), (1, -1, 135),
                        (0, -1, 0), (0, 1, 180), (-1, 0, 270), (1, 0, 90)]:
        x, y, z = at(i, j, -3.0 * i if i else 3.0, -3.0 * j if j else 3.0)
        spawns.append((x, y, yaw, z))
    spawns += [(at(0, 0)[0] - 5.5, -4.5, 0, HIGH), (5.5, -4.5, 0, HIGH),
               (-24.0, 5.0, 270, HIGH), (24.0, -5.0, 90, HIGH)]
    loot = [at(-1, -1, 3, 3), at(1, 1, -3, -3), at(-1, 1, 3, -3), at(1, -1, -3, 3),
            (HOUSE[0], HOUSE[1], HIGH), (HOUSE[0] + 2.0, HOUSE[1] - 1.0, HIGH + HOUSE_H + 0.25),
            at(0, -1, -4, 2), at(0, 1, 4, -2)]
    ports = [at(-1, 0, 3, -4), at(1, 0, -3, 4)]
    heals = [at(-1, -1, -4, 4), at(1, 1, 4, -4), at(-1, 1, 4, 4), at(1, -1, -4, -4),
             at(0, -1, 5, -3), at(0, 1, -5, 3), at(-1, 0, 2, 4), at(1, 0, -2, -4)]
    # jump pads on the corner roofs fling you up onto the neighbouring edge tower
    # (corners whose stairs lead along x get a pad towards the other neighbour)
    pads = []
    for (i, j), axis in stairs:
        if axis == "x":
            pads.append((19.0 * i, 15.0 * j, 18.0 * i, 4.0 * j, HIGH, LOW))
        else:
            pads.append((15.0 * i, 19.0 * j, 4.0 * i, 18.0 * j, HIGH, LOW))
    theme = {
        "sky": True, "night": True, "ground": "city", "reflections": False, "hue_cycle": False,
        "ambient": (0.16, 0.16, 0.24), "sun_dir": (-0.3, 0.4, 0.86),
        "sun_col": (0.22, 0.24, 0.38), "fog": (0.07, 0.06, 0.13, 0.010),
        "sky_top": (0.02, 0.02, 0.07), "sky_horizon": (0.28, 0.12, 0.30),
    }
    return {
        "HALF": HALF, "WALL_H": WALL_H, "CEILING_Z": CEILING_Z, "CATWALK_Z": CATWALK_Z,
        "STATIC_BOXES": b, "SLIDING_WALLS": [], "SPAWNS": spawns, "LOOT_BOXES": loot,
        "CHARGE_PORTS": ports, "JUMP_PADS": pads,
        "TURRETS": [(-24.0, 20.0 - 3.2, HIGH + 2.2, 180), (24.0, -20.0 + 3.2, HIGH + 2.2, 0)],
        "TRAP_SPOTS": [], "DRONE_SPAWNS": [(-20, -20, 32), (20, 20, 32), (0, 0, 34)],
        "GRAVITY_ZONES": [], "LASER_SWEEPERS": [], "MINE_FIELD": [], "HOLO_SIGNS": [],
        "DECOR": decor, "THEME": theme, "KILL_Z": KILL_Z, "NAV_TOP": 30.0,
        "HEAL_SPOTS": heals,
    }
