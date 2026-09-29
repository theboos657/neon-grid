"""Static layout of THE GRID arena (shared by client rendering, bot navigation
and server-side line-of-sight validation).

Coordinates: metres, Z up, floor at z = 0, arena spans [-HALF, HALF] on X/Y.
Boxes are tuples ``(minx, miny, minz, maxx, maxy, maxz, kind)``.
"""

HALF = 32.0
WALL_H = 12.0
CEILING_Z = 12.0
CATWALK_Z = 4.5


def box(cx, cy, z0, sx, sy, sz, kind):
    return (cx - sx / 2, cy - sy / 2, z0, cx + sx / 2, cy + sy / 2, z0 + sz, kind)


def _build():
    b = []
    t = 1.0
    # Outer shell + ceiling -------------------------------------------------
    b.append(box(0, HALF + t / 2, 0, 2 * HALF + 2 * t, t, WALL_H + 1, "wall"))
    b.append(box(0, -HALF - t / 2, 0, 2 * HALF + 2 * t, t, WALL_H + 1, "wall"))
    b.append(box(HALF + t / 2, 0, 0, t, 2 * HALF, WALL_H + 1, "wall"))
    b.append(box(-HALF - t / 2, 0, 0, t, 2 * HALF, WALL_H + 1, "wall"))
    b.append(box(0, 0, CEILING_Z, 2 * HALF + 2, 2 * HALF + 2, 1.0, "ceiling"))

    # Central platform with two staircases (north / south) -------------------
    b.append(box(0, 0, 0, 10, 10, 2.0, "platform"))
    for k in range(1, 5):
        h = 0.4 * k
        d0 = 5 + (4 - k) * 0.7
        for sgn in (1, -1):
            cy = sgn * (d0 + 0.35)
            b.append(box(0, cy, 0, 3.2, 0.7, h, "step"))
    # Low parapets on the platform edge (cover while on top)
    for sx in (1, -1):
        b.append(box(sx * 4.6, 0, 2.0, 0.6, 6.0, 1.0, "cover"))

    # Four big pillars --------------------------------------------------------
    for sx in (1, -1):
        for sy in (1, -1):
            b.append(box(sx * 14, sy * 14, 0, 2.4, 2.4, WALL_H, "pillar"))

    # Catwalks along east/west walls, reached by jump pads ---------------------
    for sx in (1, -1):
        b.append(box(sx * (HALF - 1.75), 0, CATWALK_Z - 0.3, 3.5, 40, 0.3, "catwalk"))
        # railing (low) on the inner edge with gaps to drop down
        for cy in (-15, 0, 15):
            b.append(box(sx * (HALF - 3.4), cy, CATWALK_Z, 0.2, 7, 1.0, "rail"))
        # support columns
        for cy in (-18, -6, 6, 18):
            b.append(box(sx * (HALF - 3.2), cy, 0, 0.5, 0.5, CATWALK_Z - 0.3, "support"))

    # Cover crates ------------------------------------------------------------
    crates = [(-8, -12, 2, 2, 1.2), (8, 12, 2, 2, 1.2), (-20, 6, 2.5, 2.5, 1.4),
              (20, -6, 2.5, 2.5, 1.4), (-6, 22, 3, 1.6, 1.3), (6, -22, 3, 1.6, 1.3),
              (-24, -24, 2.2, 2.2, 2.2), (24, 24, 2.2, 2.2, 2.2), (-24, 25, 2, 3, 1.2),
              (24, -25, 2, 3, 1.2), (12, 2, 1.6, 1.6, 1.1), (-12, -2, 1.6, 1.6, 1.1)]
    for (cx, cy, sx, sy, sz) in crates:
        b.append(box(cx, cy, 0, sx, sy, sz, "crate"))
    # Stacked crate for a high perch
    b.append(box(-24, -24, 2.2, 1.6, 1.6, 1.2, "crate"))
    b.append(box(24, 24, 2.2, 1.6, 1.6, 1.2, "crate"))

    # Low walls (waist-high cover lanes)
    for (cx, cy, sx, sy) in [(-14, 0, 0.6, 6), (14, 0, 0.6, 6), (0, -26, 7, 0.6),
                             (0, 26, 7, 0.6)]:
        b.append(box(cx, cy, 0, sx, sy, 1.3, "cover"))
    return b


STATIC_BOXES = _build()

# Sliding walls: (center_x, center_y, size_x, size_y, height, axis, travel, period, phase)
SLIDING_WALLS = [
    (0.0, 17.0, 7.0, 0.8, 3.4, "x", 8.0, 14.0, 0.0),
    (0.0, -17.0, 7.0, 0.8, 3.4, "x", 8.0, 14.0, 7.0),
    (-19.0, -14.0, 0.8, 6.0, 3.4, "y", 6.0, 12.0, 3.0),
    (19.0, 14.0, 0.8, 6.0, 3.4, "y", 6.0, 12.0, 9.0),
]

SPAWNS = [(-28, -28, 45), (28, 28, 225), (-28, 28, 315), (28, -28, 135),
          (0, -29, 0), (0, 29, 180), (-29, 0, 270), (29, 0, 90),
          (-10, -20, 20), (10, 20, 200), (-18, 18, 300), (18, -18, 120)]
# yaw in degrees (Panda heading: 0 faces +Y)

LOOT_BOXES = [(-10, -8), (10, 8), (-26, 12), (26, -12), (0, 0, 2.0), (-16, -26), (16, 26),
              (22, 2), (-22, -2), (30.0, 10.0, CATWALK_Z), (-30.0, -10.0, CATWALK_Z)]
CHARGE_PORTS = [(-20, 20), (20, -20), (-4, -14), (4, 14)]
JUMP_PADS = [  # (x, y, target_x, target_y, target_z)
    (-25.5, -7.5, -30.0, -7.5, CATWALK_Z), (-25.5, 7.5, -30.0, 7.5, CATWALK_Z),
    (25.5, -7.5, 30.0, -7.5, CATWALK_Z), (25.5, 7.5, 30.0, 7.5, CATWALK_Z),
]
TURRETS = [(0, HALF - 0.4, 6.5, 180), (0, -HALF + 0.4, 6.5, 0),
           (HALF - 0.4, -24, 7.5, 90), (-HALF + 0.4, 24, 7.5, 270)]
TRAP_SPOTS = [(-9, 4), (9, -4), (-17, 22), (17, -22), (-3, -22), (3, 22), (-26, -3), (26, 3)]
DRONE_SPAWNS = [(-20, -20, 9), (20, 20, 9), (-20, 20, 9), (20, -20, 9), (0, 0, 10)]
GRAVITY_ZONES = [(-22, 14, 3.0), (22, -14, 3.0)]
LASER_SWEEPERS = [(-17, 0, 7.0), (17, 0, 7.0)]  # pivot x, y, arm length
MINE_FIELD = [(-6, -6), (6, 6), (-12, 12), (12, -12), (-26, 20), (26, -20), (-4, 26),
              (4, -26), (-20, -10), (20, 10), (0, 9), (0, -9)]

HOLO_SIGNS = [  # x, y, z, heading, text key
    (0, HALF - 0.3, 8.5, 180, "sign_grid"), (0, -HALF + 0.3, 8.5, 0, "sign_arena"),
    (HALF - 0.3, 8, 9.0, 90, "sign_sponsor"), (-HALF + 0.3, -8, 9.0, 270, "sign_danger"),
]
