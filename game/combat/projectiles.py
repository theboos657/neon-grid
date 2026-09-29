"""Plasma projectiles (player plasma weapons and hunter-drone bolts)."""

from panda3d.core import Vec3, Vec4

from ..gfx import geom


class Projectile:
    __slots__ = ("pos", "vel", "owner", "dmg", "splash", "splash_dmg", "color", "life", "np",
                 "size", "weapon", "kind", "hs", "seq")

    def __init__(self):
        self.np = None
        self.life = 0.0


class ProjectileManager:
    def __init__(self, match, capacity=96):
        self.match = match
        mb = geom.MeshBuilder("bolt")
        mb.sphere((0, 0, 0), 1.0, (1, 1, 1, 1), 6, 8)
        proto = mb.node()
        self.pool = []
        for _ in range(capacity):
            p = Projectile()
            p.np = proto.copyTo(match.world_root)
            p.np.setTexture(match.textures.white)
            p.np.setShaderInput("u_mat", Vec4(1, 0, 0, 4.0))
            p.np.hide()
            self.pool.append(p)
        self.active = []

    def _take(self):
        for p in self.pool:
            if p.life <= 0:
                return p
        return None

    def spawn(self, owner, pos, direction, stats, weapon_name, seq=None):
        p = self._take()
        if p is None:
            return
        p.pos = Vec3(pos)
        p.vel = Vec3(direction) * stats["speed"]
        p.owner = owner
        p.dmg = stats["dmg"]
        p.splash = stats["splash"]
        p.splash_dmg = stats["splash_dmg"]
        p.color = stats["color"]
        p.life = 3.0
        p.size = 0.22 if stats["splash"] > 2 else (0.12 if stats["id"] == "photon" else 0.16)
        p.weapon = weapon_name
        p.kind = "nova" if stats["splash"] > 2 else "plasma"
        p.hs = stats["hs"]
        p.seq = seq
        p.np.show()
        p.np.setScale(p.size)
        c = p.color
        p.np.setColorScale(c[0] * 2, c[1] * 2, c[2] * 2, 1)
        p.np.setShaderInput("u_hue", 0.0 if owner is None else 0.0)
        self.active.append(p)

    def spawn_hazard_bolt(self, drone, pos, direction):
        p = self._take()
        if p is None:
            return
        p.pos = Vec3(pos)
        p.vel = Vec3(direction) * 30.0
        p.owner = drone
        p.dmg = 14
        p.splash = 1.2
        p.splash_dmg = 6
        p.color = (1.0, 0.25, 0.1)
        p.life = 3.0
        p.size = 0.2
        p.weapon = "DRONE"
        p.kind = "hazard"
        p.hs = 1.0
        p.seq = None
        p.np.show()
        p.np.setScale(p.size)
        p.np.setColorScale(3.0, 0.6, 0.2, 1)
        self.active.append(p)

    def update(self, dt):
        m = self.match
        still = []
        for p in self.active:
            p.life -= dt
            if p.life <= 0:
                p.np.hide()
                continue
            step = p.vel * dt
            ln = step.length()
            d = step / ln if ln > 0 else Vec3(0, 1, 0)
            t_wall, n_wall = m.coll.raycast(p.pos, d, ln)
            limit = t_wall if t_wall is not None else ln
            best = None
            for tgt in m.shootables(p.owner):
                r = tgt.ray_hit(p.pos, d, limit + p.size)
                if r is not None and (best is None or r[0] < best[0]):
                    best = (r[0], tgt, r[1])
            if best is not None:
                hit = p.pos + d * best[0]
                dmg = p.dmg * (p.hs if best[2] else 1.0)
                m.damage(best[1], dmg, p.owner, p.weapon, hit, best[2], kind="plasma", dir_=d)
                self._impact(p, hit, Vec3(0, 0, 1), best[1])
                continue
            if t_wall is not None:
                hit = p.pos + d * t_wall
                self._impact(p, hit, n_wall, None)
                continue
            p.pos += step
            p.np.setPos(p.pos)
            m.fx.trail(p.pos, p.color, p.size * 2.2)
            still.append(p)
        self.active = still

    def _impact(self, p, pos, normal, direct):
        m = self.match
        p.life = 0.0
        p.np.hide()
        if m.net is not None and p.seq is not None and p.owner is m.player:
            m.net.projectile_hit(p.seq, direct, pos)
        if p.splash > 0:
            m.radial_damage(pos + normal * 0.2, p.splash, p.splash_dmg, p.owner, p.weapon,
                            kind="plasma", exclude=direct)
        if p.kind == "nova":
            m.fx.explosion(pos + normal * 0.2, 3.2, "plasma")
            m.audio.play3d("explosion", pos)
        else:
            m.fx.impact(pos, normal, p.color, strong=True)
            m.fx.shockwave(pos + normal * 0.05, 1.2, p.color, 0.2, up=abs(normal[2]) > 0.5)
            m.audio.play3d("plasma_hit", pos, 0.6)

    def clear(self):
        for p in self.active:
            p.life = 0
            p.np.hide()
        self.active = []
