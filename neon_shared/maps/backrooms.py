"""BACKROOMS: endless-feeling yellow office maze under a low ceiling of buzzing
fluorescent lights, cluttered with abandoned furniture, parked police cars and
random junk.

The floor is split into 8 x 8 m rooms.  Each internal wall segment is either
open, a wall with a doorway, or a short stub, so every room connects to its
neighbours.  Props keep a clear strip along the walls and around each room's
centre (spawns and pickups sit there).  Seeded: identical on every machine.
"""

import random

HALF = 32.0
CEILING_Z = 3.6
WALL_H = CEILING_Z
CATWALK_Z = 4.5          # unused (no catwalks down here)
ROOM = 8.0
N = int(2 * HALF / ROOM)
WALL_T = 0.08         # drywall; thin so the 1 m bot nav grid keeps lanes along walls


def box(cx, cy, z0, sx, sy, sz, kind):
    return (cx - sx / 2, cy - sy / 2, z0, cx + sx / 2, cy + sy / 2, z0 + sz, kind)


# Prop collision shapes in local coordinates (x right, y forward) around the
# prop origin: list of (minx, miny, maxx, maxy, height).
PROPS = {
    "police": [(-2.35, -0.95, 2.35, 0.95, 1.45)],
    "table": [(-0.9, -0.45, 0.9, 0.45, 0.78)],
    "chair": [(-0.24, -0.24, 0.24, 0.24, 0.95)],
    "desk": [(-0.8, -0.4, 0.8, 0.4, 0.76)],
    "office_chair": [(-0.3, -0.3, 0.3, 0.3, 1.05)],
    "cabinet": [(-0.25, -0.3, 0.25, 0.3, 1.32)],
    "couch": [(-1.0, -0.43, 1.0, 0.43, 0.85)],
    "tv": [(-0.6, -0.22, 0.6, 0.22, 1.25)],
    "coffee_table": [(-0.5, -0.3, 0.5, 0.3, 0.42)],
    "boxes": [(-0.55, -0.45, 0.55, 0.45, 1.5)],
    "cone": [(-0.18, -0.18, 0.18, 0.18, 0.7)],
    "barrel": [(-0.3, -0.3, 0.3, 0.3, 0.92)],
    "cart": [(-0.45, -0.28, 0.45, 0.28, 1.0)],
    "vending": [(-0.5, -0.4, 0.5, 0.4, 1.9)],
    "cooler": [(-0.18, -0.18, 0.18, 0.18, 1.25)],
    "arcade": [(-0.35, -0.4, 0.35, 0.4, 1.8)],
    "duck": [(-0.55, -0.45, 0.55, 0.45, 1.2)],
    "booth": [(-0.5, -0.5, 0.5, 0.5, 2.3)],
    "mattress": [(-1.0, -0.7, 1.0, 0.7, 0.3)],
    "plant": [(-0.25, -0.25, 0.25, 0.25, 1.4)],
    "lamp": [(-0.15, -0.15, 0.15, 0.15, 1.6)],
}

# Room furnishings: (prop, local x, local y, heading) relative to the room centre.
# Nothing inside |x|,|y| < 0.9 (centre spot) or beyond 2.6 (wall strip).
SETS = {
    "police": [("police", 0.0, 1.75, 0), ("cone", -2.2, -1.6, 0), ("cone", -1.2, -2.2, 0),
               ("cone", 1.6, -2.1, 0)],
    "police2": [("police", 1.75, 0.0, 90), ("cone", -2.0, 2.0, 0), ("barrel", -2.1, -2.0, 0)],
    "dining": [("table", 0.0, 2.0, 0), ("chair", -0.55, 1.35, 0), ("chair", 0.55, 1.35, 0),
               ("chair", -0.55, 2.62, 180), ("chair", 0.55, 2.62, 180),
               ("chair", -1.9, -1.8, 35), ("plant", 2.2, -2.2, 0)],
    "office": [("desk", -1.6, 1.9, 0), ("office_chair", -1.6, 1.15, 180),
               ("desk", 1.6, 1.9, 0), ("office_chair", 1.7, 1.2, 160),
               ("cabinet", 2.35, -1.6, 90), ("cabinet", 2.35, -2.25, 90),
               ("cooler", -2.3, -2.3, 0)],
    "lounge": [("couch", 0.0, -2.0, 0), ("coffee_table", 0.0, -1.2, 0), ("tv", 0.0, 2.25, 180),
               ("lamp", -1.6, -2.3, 0), ("plant", 2.2, 2.2, 0)],
    "junk": [("boxes", -1.9, 1.9, 0), ("boxes", -1.9, 0.95, 90), ("barrel", 1.8, 2.1, 0),
             ("barrel", 2.2, 1.4, 0), ("cart", 1.6, -1.9, 30), ("cone", -1.4, -2.0, 0),
             ("mattress", -1.4, -1.9, 0)],
    "vending": [("vending", -1.9, 2.1, 0), ("vending", -0.85, 2.1, 0), ("cooler", 1.2, 2.3, 0),
                ("chair", 2.0, -1.9, 200)],
    "weird": [("duck", -1.6, 1.6, 30), ("booth", 1.9, 1.9, 0), ("arcade", 1.9, -1.9, 90),
              ("cone", -2.1, -1.7, 0)],
    "arcade": [("arcade", -1.6, 2.1, 180), ("arcade", -0.6, 2.1, 180), ("arcade", 0.4, 2.1, 180),
               ("couch", 0.0, -2.0, 0), ("lamp", 2.3, -2.3, 0)],
    "empty": [],
}
SET_WEIGHTS = [("empty", 10), ("police", 7), ("police2", 5), ("dining", 10), ("office", 11),
               ("lounge", 8), ("junk", 10), ("vending", 6), ("weird", 5), ("arcade", 4)]


def room_center(i, j):
    return (-HALF + (i + 0.5) * ROOM, -HALF + (j + 0.5) * ROOM)


def _rot(x, y, hdg):
    """Rotate a local offset by a multiple of 90 degrees (counter-clockwise)."""
    q = int(round(hdg / 90.0)) % 4
    for _ in range(q):
        x, y = -y, x
    return x, y


def prop_boxes(kind, px, py, hdg):
    """World-space collision boxes of one prop (headings snap to 90 degrees)."""
    out = []
    for (x0, y0, x1, y1, h) in PROPS[kind]:
        pts = [_rot(x, y, hdg) for (x, y) in ((x0, y0), (x1, y1))]
        xs = sorted(p[0] for p in pts)
        ys = sorted(p[1] for p in pts)
        out.append((px + xs[0], py + ys[0], 0.0, px + xs[1], py + ys[1], h, "prop"))
    return out


# rooms (i, j) used for spawns, pickups and hazards
SPAWN_ROOMS = [(0, 0), (7, 7), (0, 7), (7, 0), (3, 0), (4, 7), (0, 4), (7, 3),
               (2, 2), (5, 5), (2, 5), (5, 2)]
LOOT_ROOMS = [(1, 1), (6, 6), (1, 6), (6, 1), (3, 3), (4, 4), (3, 5), (4, 2), (0, 2), (7, 5)]
PORT_ROOMS = [(2, 0), (5, 7), (0, 5), (7, 2)]
TRAP_ROOMS = [(1, 3), (6, 4), (3, 1), (4, 6), (2, 7), (5, 0), (1, 5), (6, 2)]
MINE_ROOMS = [(3, 2), (4, 5), (2, 3), (5, 4), (1, 2), (6, 5), (2, 6), (5, 1), (3, 6), (4, 1),
              (0, 3), (7, 4)]
PUBLIC_ROOMS = set(SPAWN_ROOMS + LOOT_ROOMS + PORT_ROOMS)


def build():
    rng = random.Random(90210)
    b = []
    t = 1.0
    b.append(box(0, HALF + t / 2, 0, 2 * HALF + 2 * t, t, WALL_H + 1, "wall"))
    b.append(box(0, -HALF - t / 2, 0, 2 * HALF + 2 * t, t, WALL_H + 1, "wall"))
    b.append(box(HALF + t / 2, 0, 0, t, 2 * HALF, WALL_H + 1, "wall"))
    b.append(box(-HALF - t / 2, 0, 0, t, 2 * HALF, WALL_H + 1, "wall"))
    b.append(box(0, 0, CEILING_Z, 2 * HALF + 2, 2 * HALF + 2, 1.0, "ceiling"))
    decor = []

    # pillars at every internal grid intersection
    for i in range(1, N):
        for j in range(1, N):
            x = -HALF + i * ROOM
            y = -HALF + j * ROOM
            b.append(box(x, y, 0, 0.7, 0.7, CEILING_Z, "pillar"))

    # internal walls: along x = const lines (segments run along y) and y = const lines
    def segment(fixed, a0, axis):
        """One 8 m wall segment between two pillars, from a0 to a0 + ROOM."""
        r = rng.random()
        s0, s1 = a0 + 0.35, a0 + ROOM - 0.35
        if r < 0.28:
            return                                   # open
        pieces = []
        if r < 0.78:                                 # doorway (2.2 m) somewhere
            g0 = rng.uniform(s0 + 0.8, s1 - 3.0)
            pieces = [(s0, g0), (g0 + 2.2, s1)]
            lintel = (g0, g0 + 2.2)
        else:                                        # stub from one end
            ln = rng.uniform(2.0, 3.2)
            pieces = [(s0, s0 + ln)] if rng.random() < 0.5 else [(s1 - ln, s1)]
            lintel = None
        for (p0, p1) in pieces:
            if p1 - p0 < 0.2:
                continue
            if axis == "y":
                b.append((fixed - WALL_T / 2, p0, 0.0, fixed + WALL_T / 2, p1, CEILING_Z, "wall_in"))
            else:
                b.append((p0, fixed - WALL_T / 2, 0.0, p1, fixed + WALL_T / 2, CEILING_Z, "wall_in"))
        if lintel:
            p0, p1 = lintel
            if axis == "y":
                b.append((fixed - WALL_T / 2, p0, 2.5, fixed + WALL_T / 2, p1, CEILING_Z, "wall_in"))
            else:
                b.append((p0, fixed - WALL_T / 2, 2.5, p1, fixed + WALL_T / 2, CEILING_Z, "wall_in"))

    for i in range(1, N):
        x = -HALF + i * ROOM
        for j in range(N):
            segment(x, -HALF + j * ROOM, "y")
    for j in range(1, N):
        y = -HALF + j * ROOM
        for i in range(N):
            segment(y, -HALF + i * ROOM, "x")

    # furnish every room
    names = [n for n, _ in SET_WEIGHTS]
    weights = [w for _, w in SET_WEIGHTS]
    police_left = 7
    for i in range(N):
        for j in range(N):
            cx, cy = room_center(i, j)
            name = rng.choices(names, weights)[0]
            if name.startswith("police"):
                if police_left <= 0:
                    name = "junk"
                police_left -= 1
            if (i, j) in PUBLIC_ROOMS and name == "empty":
                name = "dining"
            rot = rng.choice((0, 90, 180, 270))
            for (kind, lx, ly, hdg) in SETS[name]:
                ox, oy = _rot(lx, ly, rot)
                px, py = cx + ox, cy + oy
                h = (hdg + rot) % 360
                # snap the collision heading, keep the visual heading free-ish
                hc = round(h / 90.0) * 90
                b.extend(prop_boxes(kind, px, py, hc))
                decor.append({"k": kind, "x": px, "y": py, "h": hc, "v": rng.random()})
            # ceiling light: a few are dead or flickering
            r = rng.random()
            state = "off" if r < 0.1 else ("flicker" if r < 0.28 else "on")
            decor.append({"k": "panel", "x": cx, "y": cy, "state": state, "v": rng.random()})
            # floor junk that does not collide: papers, stains
            for _ in range(rng.randint(0, 3)):
                decor.append({"k": "paper", "x": cx + rng.uniform(-3.4, 3.4),
                              "y": cy + rng.uniform(-3.4, 3.4), "h": rng.uniform(0, 360),
                              "v": rng.random()})
            if rng.random() < 0.35:
                decor.append({"k": "stain", "x": cx + rng.uniform(-2.5, 2.5),
                              "y": cy + rng.uniform(-2.5, 2.5), "s": rng.uniform(0.8, 2.2),
                              "v": rng.random()})

    def at(rooms, z=None):
        out = []
        for (i, j) in rooms:
            x, y = room_center(i, j)
            out.append((x, y) if z is None else (x, y, z))
        return out

    spawns = []
    for (i, j) in SPAWN_ROOMS:
        x, y = room_center(i, j)
        yaw = [0, 90, 180, 270][(i * 3 + j) % 4]
        spawns.append((x, y, yaw))
    theme = {
        "sky": False, "ground": "carpet", "reflections": False, "hue_cycle": False,
        "ambient": (0.30, 0.27, 0.15), "fog": (0.34, 0.30, 0.15, 0.034),
        "sun_dir": (0.0, 0.0, 1.0), "sun_col": (0.10, 0.09, 0.05),
    }
    return {
        "HALF": HALF, "WALL_H": WALL_H, "CEILING_Z": CEILING_Z, "CATWALK_Z": CATWALK_Z,
        "STATIC_BOXES": b, "SLIDING_WALLS": [], "SPAWNS": spawns,
        "LOOT_BOXES": at(LOOT_ROOMS), "CHARGE_PORTS": at(PORT_ROOMS), "JUMP_PADS": [],
        "TURRETS": [(-4.0, HALF - 0.4, 2.2, 180), (4.0, -HALF + 0.4, 2.2, 0)],
        "TRAP_SPOTS": at(TRAP_ROOMS), "DRONE_SPAWNS": at([(1, 1), (6, 6), (3, 4)], 2.1),
        "GRAVITY_ZONES": at([(2, 4), (5, 3)], 2.4), "LASER_SWEEPERS": at([(3, 2), (4, 5)], 3.2),
        "MINE_FIELD": at(MINE_ROOMS), "HOLO_SIGNS": [], "DECOR": decor, "THEME": theme,
    }
