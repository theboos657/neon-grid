"""Lightweight box-world collision.

The arena is built from axis-aligned boxes, so a hand-rolled solver is both
simpler and much faster than a general physics engine: bodies are vertical
cylinders resolved against boxes, with automatic step-up for stairs.
"""

import math

from panda3d.core import Vec3

from neon_shared import arena_layout as L
from neon_shared.hitmath import ray_aabb

STEP_HEIGHT = 0.45
CELL = 4.0


class Body:
    """Kinematic cylinder used by players, bots and remote avatars."""

    def __init__(self, pos=(0, 0, 0), radius=0.4, height=1.8):
        self.pos = Vec3(*pos)
        self.vel = Vec3(0, 0, 0)
        self.radius = radius
        self.height = height
        self.on_ground = False
        self.ground_z = 0.0


class CollisionWorld:
    def __init__(self, static_boxes=None):
        boxes = static_boxes if static_boxes is not None else L.STATIC_BOXES
        self.ceiling_z = L.CEILING_Z
        self.static = [b for b in boxes if b[6] != "ceiling"]
        self.dynamic = []            # lists [minx, miny, minz, maxx, maxy, maxz, kind]
        self.grid = {}
        for b in self.static:
            for key in self._cells(b[0], b[1], b[3], b[4]):
                self.grid.setdefault(key, []).append(b)
        # everything for raycasts (ceiling included)
        self.ray_boxes = list(boxes)
        self.ray_always = [b for b in boxes if b[6] == "ceiling"]
        self.grid_lim = int(math.ceil((L.HALF + 8) / CELL))

    @staticmethod
    def _cells(x0, y0, x1, y1):
        for cx in range(int(math.floor(x0 / CELL)), int(math.floor(x1 / CELL)) + 1):
            for cy in range(int(math.floor(y0 / CELL)), int(math.floor(y1 / CELL)) + 1):
                yield (cx, cy)

    def add_dynamic(self, box_list):
        self.dynamic.append(box_list)
        return box_list

    def nearby(self, x, y, r):
        seen = set()
        out = []
        for key in self._cells(x - r, y - r, x + r, y + r):
            for b in self.grid.get(key, ()):
                i = id(b)
                if i not in seen:
                    seen.add(i)
                    out.append(b)
        out.extend(self.dynamic)
        return out

    # ------------------------------------------------------------------ queries
    def raycast(self, o, d, max_t, dynamic=True):
        """Returns (t, normal Vec3) of the first box hit, or (None, None)."""
        best_t = max_t
        best = None
        boxes = self.ray_always + self.dynamic if dynamic else self.ray_always
        for b in boxes:
            r = ray_aabb(o, d, b, best_t)
            if r is not None and r[0] < best_t:
                best_t, best = r[0], r
        # walk the XY grid cells along the ray (maps can have hundreds of boxes)
        ox, oy, dx, dy = o[0], o[1], d[0], d[1]
        cx = int(math.floor(ox / CELL))
        cy = int(math.floor(oy / CELL))
        sx = 1 if dx > 0 else -1
        sy = 1 if dy > 0 else -1
        inf = float("inf")
        tdx = CELL / abs(dx) if abs(dx) > 1e-9 else inf
        tdy = CELL / abs(dy) if abs(dy) > 1e-9 else inf
        tmx = ((cx + (1 if dx > 0 else 0)) * CELL - ox) / dx if abs(dx) > 1e-9 else inf
        tmy = ((cy + (1 if dy > 0 else 0)) * CELL - oy) / dy if abs(dy) > 1e-9 else inf
        seen = set()
        lim = self.grid_lim
        grid = self.grid
        for _ in range(4 * lim + 4):
            for b in grid.get((cx, cy), ()):
                i = id(b)
                if i in seen:
                    continue
                seen.add(i)
                r = ray_aabb(o, d, b, best_t)
                if r is not None and r[0] < best_t:
                    best_t, best = r[0], r
            if tmx < tmy:
                if best_t <= tmx:
                    break
                cx += sx
                tmx += tdx
            else:
                if best_t <= tmy:
                    break
                cy += sy
                tmy += tdy
            if abs(cx) > lim or abs(cy) > lim:
                break
        best_n = None
        if best is not None:
            best_n = Vec3(0, 0, 0)
            best_n[best[1]] = best[2]
        # floor plane
        if d[2] < -1e-6:
            tf = -o[2] / d[2]
            if 0 <= tf < best_t:
                best_t = tf
                best_n = Vec3(0, 0, 1)
        if best_n is None:
            return None, None
        return best_t, best_n

    def line_of_sight(self, a, b):
        d = Vec3(b) - Vec3(a)
        ln = d.length()
        if ln < 1e-4:
            return True
        d /= ln
        t, _ = self.raycast(a, d, ln - 0.05)
        return t is None

    def ground_height(self, x, y, r, max_z):
        g = 0.0
        for b in self.nearby(x, y, r):
            top = b[5]
            if top > max_z or top <= g:
                continue
            if _circle_rect(x, y, r, b):
                g = top
        return g

    def ceiling_height(self, x, y, r, min_z):
        c = self.ceiling_z
        for b in self.nearby(x, y, r):
            bot = b[2]
            if bot < min_z or bot >= c:
                continue
            if _circle_rect(x, y, r, b):
                c = bot
        return c

    def point_blocked(self, p, r=0.0):
        for b in self.nearby(p[0], p[1], r + 0.1):
            if (b[0] - r <= p[0] <= b[3] + r and b[1] - r <= p[1] <= b[4] + r
                    and b[2] <= p[2] <= b[5]):
                return True
        return False

    # ------------------------------------------------------------------ movement
    def move(self, body, dt):
        p = body.pos
        v = body.vel
        r = body.radius
        h = body.height
        hs = math.sqrt(v.x * v.x + v.y * v.y) * dt
        steps = max(1, int(hs / 0.25) + 1)
        sx = v.x * dt / steps
        sy = v.y * dt / steps
        for _ in range(steps):
            p.x += sx
            p.y += sy
            self._push_out(body)
        # vertical
        was_ground = body.on_ground
        new_z = p.z + v.z * dt
        ground = self.ground_height(p.x, p.y, r * 0.75, p.z + STEP_HEIGHT)
        body.ground_z = ground
        if new_z <= ground:
            new_z = ground
            if v.z < 0:
                v.z = 0.0
            body.on_ground = True
        elif was_ground and v.z <= 0.0 and new_z - ground < STEP_HEIGHT:
            new_z = ground          # stick to stairs when walking down
            v.z = 0.0
            body.on_ground = True
        else:
            body.on_ground = False
        ceil = self.ceiling_height(p.x, p.y, r * 0.75, p.z + h * 0.5)
        if new_z + h > ceil:
            new_z = ceil - h
            if v.z > 0:
                v.z = 0.0
        p.z = new_z
        lim = L.HALF - r
        p.x = min(max(p.x, -lim), lim)
        p.y = min(max(p.y, -lim), lim)

    def _push_out(self, body):
        p = body.pos
        r = body.radius
        feet = p.z
        head = p.z + body.height
        for _ in range(2):
            moved = False
            for b in self.nearby(p.x, p.y, r + 0.5):
                if b[5] <= feet + STEP_HEIGHT or b[2] >= head:
                    continue
                cx = min(max(p.x, b[0]), b[3])
                cy = min(max(p.y, b[1]), b[4])
                dx = p.x - cx
                dy = p.y - cy
                d2 = dx * dx + dy * dy
                if d2 >= r * r:
                    continue
                if d2 > 1e-10:
                    d = math.sqrt(d2)
                    push = r - d
                    p.x += dx / d * push
                    p.y += dy / d * push
                else:
                    # centre inside the box: exit along the shallowest axis
                    pens = [(p.x - b[0] + r, -1, 0), (b[3] - p.x + r, 1, 0),
                            (p.y - b[1] + r, 0, -1), (b[4] - p.y + r, 0, 1)]
                    pen, ax, ay = min(pens)
                    p.x += ax * pen
                    p.y += ay * pen
                moved = True
            if not moved:
                break


def _circle_rect(x, y, r, b):
    cx = min(max(x, b[0]), b[3])
    cy = min(max(y, b[1]), b[4])
    dx = x - cx
    dy = y - cy
    return dx * dx + dy * dy < r * r
