"""TRAINING RANGE: neon shooting hall used by Training mode.

You start behind a waist-high counter on the south side.  Downrange there are
lanes with static targets (10-55 m), sliding targets, pop-up targets and a
few high targets on a gantry.  Built with the GRID's visual style.
"""

HALF = 32.0
WALL_H = 12.0
CEILING_Z = 12.0
CATWALK_Z = 4.5
LINE_Y = -22.0           # firing line


def box(cx, cy, z0, sx, sy, sz, kind):
    return (cx - sx / 2, cy - sy / 2, z0, cx + sx / 2, cy + sy / 2, z0 + sz, kind)


# targets: (kind, x, y, z, extra)
#   static   - stands still
#   slide    - moves left/right, extra = travel (m)
#   popup    - hides and pops up at random
#   strafe   - sprints across a lane like a player, extra = travel
TARGETS = [
    ("static", -12, -12, 0, 0), ("static", -4, -12, 0, 0), ("static", 4, -12, 0, 0),
    ("static", 12, -12, 0, 0),
    ("static", -18, -2, 0, 0), ("static", 18, -2, 0, 0),
    ("slide", 0, -2, 0, 10.0), ("slide", 0, 8, 0, 14.0),
    ("popup", -10, 8, 0, 0), ("popup", 10, 8, 0, 0), ("popup", -20, 16, 0, 0),
    ("popup", 20, 16, 0, 0), ("popup", 0, 18, 0, 0),
    ("strafe", 0, 24, 0, 22.0),
    ("static", -14, 30, 4.5, 0), ("static", 0, 30, 4.5, 0), ("static", 14, 30, 4.5, 0),
]


def build():
    b = []
    t = 1.0
    b.append(box(0, HALF + t / 2, 0, 2 * HALF + 2 * t, t, WALL_H + 1, "wall"))
    b.append(box(0, -HALF - t / 2, 0, 2 * HALF + 2 * t, t, WALL_H + 1, "wall"))
    b.append(box(HALF + t / 2, 0, 0, t, 2 * HALF, WALL_H + 1, "wall"))
    b.append(box(-HALF - t / 2, 0, 0, t, 2 * HALF, WALL_H + 1, "wall"))
    b.append(box(0, 0, CEILING_Z, 2 * HALF + 2, 2 * HALF + 2, 1.0, "ceiling"))
    # firing-line counter with two gaps to walk downrange
    b.append(box(-17, LINE_Y + 2, 0, 26, 0.6, 1.1, "cover"))
    b.append(box(17, LINE_Y + 2, 0, 26, 0.6, 1.1, "cover"))
    # lane dividers
    for x in (-24, -8, 8, 24):
        b.append(box(x, 2, 0, 0.4, 10, 0.9, "cover"))
    # high gantry for the far targets
    b.append(box(0, 30, CATWALK_Z - 0.3, 40, 2.4, 0.3, "catwalk"))
    for x in (-18, 0, 18):
        b.append(box(x, 30, 0, 0.6, 0.6, CATWALK_Z - 0.3, "support"))
    # crates downrange for cover practice
    for (x, y) in ((-14, 12), (14, 12), (-26, 22), (26, 22), (-6, 20), (6, 20)):
        b.append(box(x, y, 0, 1.8, 1.8, 1.2, "crate"))
    spawns = [(0, -27, 0), (-6, -27, 0), (6, -27, 0), (-14, -27, 0), (14, -27, 0)]
    return {
        "HALF": HALF, "WALL_H": WALL_H, "CEILING_Z": CEILING_Z, "CATWALK_Z": CATWALK_Z,
        "STATIC_BOXES": b, "SLIDING_WALLS": [], "SPAWNS": spawns,
        "LOOT_BOXES": [(-10, -26), (10, -26)], "CHARGE_PORTS": [(0, -24)], "JUMP_PADS": [],
        "TURRETS": [], "TRAP_SPOTS": [], "DRONE_SPAWNS": [(0, 0, 9)], "GRAVITY_ZONES": [],
        "LASER_SWEEPERS": [], "MINE_FIELD": [],
        "HOLO_SIGNS": [(0, HALF - 0.3, 8.5, 180, "sign_range")],
        "DECOR": [], "THEME": {"sky": False}, "HEAL_SPOTS": [(-20, -26), (20, -26)],
        "TARGETS": TARGETS,
    }
