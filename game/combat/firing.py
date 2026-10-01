"""Turning a trigger pull into hits: hitscan bullets, rail pulses, pellets,
projectiles and melee swings."""

import math
import random

from panda3d.core import Vec3

from neon_shared.hitmath import spread_dir
from neon_shared.weapons import damage_at

_rng = random.Random()

ENERGY_CLASSES = ("rail", "plasma")
LASER_WEAPONS = ("buzz", "scatter", "lance", "arcrail")


def effective_spread(shooter, ws):
    s = ws.stats["spread"]
    b = shooter.body
    hs = math.hypot(b.vel.x, b.vel.y)
    mult = 1.0 + ws.bloom * 1.2
    if shooter.input.ads:
        mult *= 0.35 if ws.stats["scoped"] else 0.55
    if hs > 3.0:
        mult *= 1.0 + min(1.0, (hs - 3.0) / 6.0) * 0.8
    if not b.on_ground:
        mult *= 1.7
    if shooter.crouching and b.on_ground:
        mult *= 0.8
    # snipers are inaccurate unless scoped
    if ws.stats["scoped"] and not shooter.input.ads:
        mult *= 12.0 if ws.stats["cls"] == "sniper" else 4.0
    return s * mult + shooter.aim_error


def fire(match, shooter, ws):
    """Fire one round (or one shotgun blast) of ``ws`` from ``shooter``."""
    stats = ws.stats
    shooter.on_fire()
    if stats["melee"]:
        melee(match, shooter, ws)
        return
    origin = shooter.eye_pos()
    fwd = shooter.aim_dir()
    muzzle = shooter.muzzle_pos()
    color = stats["color"]
    spread = effective_spread(shooter, ws)
    flags = stats.get("flags", ())
    suppressed = "suppressed" in flags
    flash = 0.45 if stats["cls"] != "shotgun" else 0.7
    if suppressed:
        flash *= 0.3
    elif "lowflash" in flags:
        flash *= 0.55
    match.fx.muzzle(muzzle, fwd, color, flash,
                    light=not suppressed and (shooter.is_player or _rng.random() < 0.5))
    match.audio.play_weapon("suppressed" if suppressed else stats["sfx"], muzzle, shooter,
                            quiet=suppressed)
    if shooter.is_player:
        match.shake(0.04 * stats["recoil"])
    dirs = [Vec3(*spread_dir(tuple(fwd), spread, _rng)) for _ in range(stats["pellets"])]
    seq = None
    if match.net is not None and getattr(shooter, "net_local", False):
        seq = match.net.local_fire(ws, origin, fwd, dirs, shooter)
    for d in dirs:
        if stats["speed"] > 0:
            match.projectiles.spawn(shooter, muzzle + d * 0.2, d, stats, stats["name"], seq)
        else:
            _hitscan(match, shooter, origin, muzzle, d, stats)
    match.stat_shot(shooter, stats)


def _hitscan(match, shooter, origin, muzzle, d, stats):
    maxr = stats["maxr"]
    t_wall, n_wall = match.coll.raycast(origin, d, maxr)
    limit = t_wall if t_wall is not None else maxr
    hits = []
    for tgt in match.shootables(shooter):
        r = tgt.ray_hit(origin, d, limit)
        if r is not None:
            hits.append((r[0], tgt, r[1]))
    hits.sort(key=lambda h: h[0])
    if not stats["pierce"]:
        hits = hits[:1]
    end_t = limit
    for (t, tgt, head) in hits:
        dmg = damage_at(stats, t) * (stats["hs"] if head else 1.0)
        hp = origin + d * t
        match.damage(tgt, dmg, shooter, stats["name"], hp, head, kind="bullet", dir_=d)
        if not stats["pierce"]:
            end_t = t
    end = origin + d * end_t
    # visuals
    wid = stats["id"]
    if stats["cls"] == "rail":
        w = 0.14 if wid == "lance" else 0.08
        match.fx.beam(muzzle, end, stats["color"], width=w, life=0.14, intensity=4.0)
        match.fx.beam(muzzle, end, (1, 1, 1), width=w * 0.3, life=0.08, intensity=3.0)
        if wid == "lance":
            # spiral sparks along the rail path
            seg = end - muzzle
            ln = seg.length()
            n = int(min(40, ln * 1.2) * match.fx.q) + 2
            for i in range(n):
                p = muzzle + seg * (i / n)
                match.fx.sparks.emit(1, p, (_rng.uniform(-1, 1), _rng.uniform(-1, 1),
                                            _rng.uniform(-1, 1)), 0.3, 0.07, 0.0,
                                     (0.6, 3, 3.5, 1), (0, 0.3, 0.5, 0), drag=2.0)
    elif wid in LASER_WEAPONS:
        match.fx.beam(muzzle, end, stats["color"], width=0.05, life=0.07, intensity=3.0)
    else:
        match.fx.tracer(muzzle, end, stats["color"])
    if t_wall is not None and (not hits or stats["pierce"] or end_t >= t_wall - 0.01):
        match.fx.impact(end, n_wall, stats["color"], strong=stats["cls"] in ("rail", "sniper"))
        if _rng.random() < 0.35:
            match.audio.play3d("ricochet", end, 0.35)


def melee(match, shooter, ws):
    stats = ws.stats
    eye = shooter.eye_pos()
    fwd = shooter.aim_dir()
    rng_ = stats["range"]
    half_arc = math.radians(stats["arc"] * 0.5)
    hit_any = False
    if match.net is not None and getattr(shooter, "net_local", False):
        match.net.local_melee(ws, eye, fwd, shooter)
    match.audio.play3d("melee_swing", eye, 0.7, source=shooter)
    for tgt in match.shootables(shooter):
        c = tgt.center() if hasattr(tgt, "center") and tgt.is_hazard else tgt.chest_pos()
        d = c - eye
        dist = d.length()
        reach = rng_ + (0.45 if not tgt.is_hazard else tgt.radius)
        if dist > reach or dist < 0.01:
            continue
        dn = d / dist
        if math.acos(max(-1.0, min(1.0, dn.dot(fwd)))) > half_arc and dist > 0.9:
            continue
        if not match.coll.line_of_sight(eye, c):
            continue
        dmg = stats["dmg"]
        if not tgt.is_hazard and stats["backstab"] > 1.0:
            if tgt.facing_dir().dot(Vec3(fwd.x, fwd.y, 0).normalized()) > 0.5:
                dmg *= stats["backstab"]
        match.damage(tgt, dmg, shooter, stats["name"], c, False, kind="melee", dir_=dn)
        if not tgt.is_hazard:
            k = Vec3(dn.x, dn.y, 0.25) * stats["knock"]
            tgt.body.vel += k
            if stats["stun"] > 0:
                tgt.stun_until = max(tgt.stun_until, match.time + stats["stun"])
        match.fx.sparks_at(c, -dn, 22, stats["color"], 8)
        hit_any = True
    if hit_any:
        match.audio.play3d("melee_hit", eye, 0.9, source=shooter)
        if shooter.is_player:
            match.shake(0.1)
