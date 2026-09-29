"""Navigation graph for bots.

A 1 m grid over the arena where every cell can hold several walkable levels
(floor, crate tops, central platform, catwalks).  Edges connect neighbours
that can be stepped up/down, jump pads add one-way links to the catwalks, and
drops from ledges are one-way.  A* runs on demand (cheap: ~5k nodes).
"""

import heapq
import math

from neon_shared import arena_layout as L
from neon_shared.hitmath import STAND_HEIGHT

from ..world.collision import STEP_HEIGHT, _circle_rect

CELL = 1.0
N = int(2 * L.HALF / CELL)
BODY_R = 0.45


def cell_center(ix, iy):
    return (-L.HALF + (ix + 0.5) * CELL, -L.HALF + (iy + 0.5) * CELL)


def to_cell(x, y):
    ix = int((x + L.HALF) / CELL)
    iy = int((y + L.HALF) / CELL)
    return min(max(ix, 0), N - 1), min(max(iy, 0), N - 1)


class NavGraph:
    def __init__(self, coll):
        self.coll = coll
        self.levels = {}       # (ix, iy) -> list of z heights
        self.edges = {}        # node -> list of (node, cost)
        self._build()

    def _walkable(self, x, y, z):
        """Can a body stand at (x, y) with feet at z?"""
        for b in self.coll.static:
            if b[5] <= z + STEP_HEIGHT or b[2] >= z + STAND_HEIGHT:
                continue
            if _circle_rect(x, y, BODY_R, b):
                return False
        return True

    def _build(self):
        boxes = self.coll.static
        for ix in range(N):
            for iy in range(N):
                x, y = cell_center(ix, iy)
                cand = {0.0}
                for b in boxes:
                    if b[0] <= x <= b[3] and b[1] <= y <= b[4] and b[5] < L.CEILING_Z - 2:
                        cand.add(round(b[5], 2))
                lv = []
                for z in sorted(cand):
                    # the surface under the centre must actually be this z
                    g = self.coll.ground_height(x, y, 0.05, z + 0.01)
                    if abs(g - z) > 0.02:
                        continue
                    if self._walkable(x, y, z):
                        lv.append(z)
                if lv:
                    self.levels[(ix, iy)] = lv
        for (ix, iy), lv in self.levels.items():
            for li, z in enumerate(lv):
                node = (ix, iy, li)
                out = []
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nb = self.levels.get((ix + dx, iy + dy))
                        if not nb:
                            continue
                        # diagonal moves require both orthogonal cells walkable
                        if dx and dy and (not self.levels.get((ix + dx, iy)) or
                                          not self.levels.get((ix, iy + dy))):
                            continue
                        base = math.sqrt(2) if dx and dy else 1.0
                        for lj, z2 in enumerate(nb):
                            dz = z2 - z
                            if dz <= STEP_HEIGHT + 0.01 and dz >= -STEP_HEIGHT - 0.01:
                                out.append(((ix + dx, iy + dy, lj), base))
                            elif dz < -STEP_HEIGHT and dz > -6.0 and not (dx and dy):
                                out.append(((ix + dx, iy + dy, lj), base + 1.5))  # drop down
                self.edges[node] = out
        # jump pads
        for (x, y, tx, ty, tz) in L.JUMP_PADS:
            a = self.nearest_node(x, y, 0.0)
            b = self.nearest_node(tx, ty, tz)
            if a and b:
                self.edges.setdefault(a, []).append((b, 6.0))

    def node_pos(self, node):
        ix, iy, li = node
        x, y = cell_center(ix, iy)
        return (x, y, self.levels[(ix, iy)][li])

    def nearest_node(self, x, y, z):
        ix, iy = to_cell(x, y)
        best = None
        bd = 1e9
        for r in range(0, 4):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    lv = self.levels.get((ix + dx, iy + dy))
                    if not lv:
                        continue
                    for li, lz in enumerate(lv):
                        d = abs(lz - z) * 3 + abs(dx) + abs(dy)
                        if lz > z + 1.0:
                            d += 10
                        if d < bd:
                            bd = d
                            best = (ix + dx, iy + dy, li)
            if best is not None:
                return best
        return best

    def path(self, start, goal, max_expand=6000):
        """A* from world pos ``start`` to ``goal``; returns list of (x, y, z)."""
        s = self.nearest_node(*start)
        g = self.nearest_node(*goal)
        if s is None or g is None:
            return []
        gx, gy, gz = self.node_pos(g)

        def h(n):
            x, y, z = self.node_pos(n)
            return math.hypot(x - gx, y - gy) + abs(z - gz) * 0.5

        openq = [(h(s), 0.0, s)]
        came = {s: None}
        cost = {s: 0.0}
        expanded = 0
        while openq:
            _, c, n = heapq.heappop(openq)
            if n == g:
                break
            if c > cost.get(n, 1e9):
                continue
            expanded += 1
            if expanded > max_expand:
                break
            for nb, w in self.edges.get(n, ()):
                nc = c + w
                if nc < cost.get(nb, 1e9):
                    cost[nb] = nc
                    came[nb] = n
                    heapq.heappush(openq, (nc + h(nb), nc, nb))
        if g not in came:
            return []
        out = []
        n = g
        while n is not None:
            out.append(self.node_pos(n))
            n = came[n]
        out.reverse()
        return self._smooth(out)

    def _smooth(self, pts):
        """Drop intermediate waypoints on straight same-level runs."""
        if len(pts) <= 2:
            return pts
        res = [pts[0]]
        for i in range(1, len(pts) - 1):
            a = res[-1]
            b = pts[i]
            c = pts[i + 1]
            if abs(b[2] - a[2]) > 0.01 or abs(c[2] - b[2]) > 0.01:
                res.append(b)
                continue
            d1 = (b[0] - a[0], b[1] - a[1])
            d2 = (c[0] - b[0], c[1] - b[1])
            cross = d1[0] * d2[1] - d1[1] * d2[0]
            if abs(cross) > 1e-6 or math.hypot(b[0] - a[0], b[1] - a[1]) > 6:
                res.append(b)
        res.append(pts[-1])
        return res

    def random_node_pos(self, rng, min_z=None):
        keys = list(self.levels.keys())
        for _ in range(20):
            k = rng.choice(keys)
            lv = self.levels[k]
            z = rng.choice(lv)
            if min_z is not None and z < min_z:
                continue
            x, y = cell_center(*k)
            return (x, y, z)
        x, y = cell_center(*keys[0])
        return (x, y, self.levels[keys[0]][0])
