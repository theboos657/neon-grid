"""A running match: owns the arena, combatants, hazards and all combat rules.

Everything that damages anything goes through ``Match.damage`` so kill
credit, feedback (hit markers, damage direction, kill feed, announcer) and
stats are handled in one place.
"""

import logging
import math
import random

from panda3d.core import Vec3

from neon_shared import arena_layout as L
from neon_shared.hitmath import hit_combatant

from . import i18n
from .combat.projectiles import ProjectileManager
from .combat.viewmodel import ViewModel
from .entities.combatant import Combatant
from .entities.player import PlayerController
from .entities.visuals import CharacterVisual
from .gfx import shaders
from .gfx.effects import Effects
from .gfx.lighting import LightRig
from .world import map_visuals
from .world.collision import Body, CollisionWorld
from .world.hazards import HazardManager
from .world.interactables import Interactables

log = logging.getLogger("match")

STREAK_CALLS = {3: "killing_spree", 5: "rampage", 8: "unstoppable"}
MULTI_CALLS = {2: "double_kill", 3: "triple_kill", 4: "multi_kill"}


class Decoy:
    """Holographic clone that walks forward and attracts enemy fire."""
    is_hazard = False
    is_decoy = True

    def __init__(self, match, owner, duration):
        self.match = match
        self.owner = owner
        self.team = owner.team
        self.cid = -1000 - int(match.time * 1000) % 100000
        self.name = owner.name
        self.body = Body(owner.body.pos + owner.facing_dir() * 1.2)
        self.body.on_ground = True
        self.yaw = owner.yaw
        self.pitch = 0.0
        self.health = 60.0
        self.alive = True
        self.crouching = False
        self.cloaked = False
        self.life = duration
        self.reveal_until = 0.0
        self.revealed_to_team = None
        self.last_attacker = None
        self.visual = CharacterVisual(match, owner.skin, hologram=True)
        self.dir = owner.facing_dir()

    radius = 0.4

    def chest_pos(self):
        return self.body.pos + Vec3(0, 0, 1.2)

    def eye_pos(self):
        return self.body.pos + Vec3(0, 0, 1.62)

    def center(self):
        return self.chest_pos()

    def facing_dir(self):
        return self.dir

    def ray_hit(self, o, d, max_t):
        if not self.alive:
            return None
        return hit_combatant(o, d, self.body.pos, False, max_t)

    def take_damage(self, amount, source, headshot=False):
        self.health -= amount
        if self.health <= 0:
            self.expire()
            return amount, True
        return amount, False

    def update(self, dt):
        if not self.alive:
            return
        self.life -= dt
        if self.life <= 0:
            self.expire()
            return
        self.body.vel.x = self.dir.x * 4.5
        self.body.vel.y = self.dir.y * 4.5
        self.body.vel.z -= 18 * dt
        before = Vec3(self.body.pos)
        self.match.coll.move(self.body, dt)
        if (self.body.pos - before).length() < 1.0 * dt:
            # blocked: turn
            a = random.uniform(90, 270)
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            self.dir = Vec3(self.dir.x * ca - self.dir.y * sa, self.dir.x * sa + self.dir.y * ca, 0)
            self.yaw = math.degrees(math.atan2(-self.dir.x, self.dir.y))
        flicker = 1.0 if random.random() > 0.05 else 0.3
        self.visual.update(dt, self.body.pos, self.yaw, 0, 4.5, False, flicker)

    def expire(self):
        if not self.alive:
            return
        self.alive = False
        self.match.fx.sparks_at(self.chest_pos(), (0, 0, 1), 40, (0.2, 0.9, 1.0), 5)
        self.visual.destroy()


class Match:
    def __init__(self, app, config, showcase=False):
        self.app = app
        self.config = config
        self.showcase = showcase
        self.online = bool(config.get("online"))
        self.net = config.get("session")
        self.net_ids = {}
        self.render = app.render
        self.textures = app.textures
        self.font = app.fonts.get("display")
        quality = app.storage.settings["video"]["quality"]
        self.quality = quality
        # scene roots
        self.world_root = self.render.attachNewNode("world")
        self.world_root.setShader(shaders.get("world"))
        self.world_root.setTexture(self.textures.white)
        self.overlay_root = self.render.attachNewNode("overlay")
        max_lights = 8 if quality == "high" else 4
        self.lights = LightRig(self.render, max_lights)
        # the map must be current before collision, navigation and visuals are built
        self.map_id = "grid" if showcase else L.valid(config.get("map", "grid"))
        L.load(self.map_id)
        self.coll = CollisionWorld()
        self.audio = app.audio
        self.fx = Effects(self.world_root, self.lights, quality, self.audio)
        self.fx.set_screen_height(app.win.getYSize() if app.win else 900)
        self.arena = map_visuals.create(self.render, self.world_root, self.textures, self.lights,
                                        quality, self.font,
                                        app.storage.settings["video"]["reflections"])
        self.nav = app.get_nav(self.coll)
        self.time = 0.0
        self.frozen = True
        self.state = "countdown"
        # long enough to read the briefing (mode, map, objective); 3-2-1 plays at the end
        self.state_t = 0.0 if showcase else (4.5 if self.online else 5.5)
        self.combatants = []
        self.decoys = []
        self.wells = []
        self.player = None
        self.player_ctrl = None
        self.crosshair_target = None
        self.first_blood = False
        self.leader_cid = None
        self.next_cid = 1
        self.rng = random.Random()
        self.hud = None if showcase else app.hud
        self.events = []
        self.result = None
        self.stats = {"kills": 0, "deaths": 0, "headshots": 0, "melee_kills": 0,
                      "weapon_kills": {}, "abilities": 0, "loot": 0, "hazards": 0, "drones": 0,
                      "turrets": 0, "slides": 0, "damage": 0.0, "shots": 0, "hits": 0,
                      "best_streak": 0, "xp": 0, "coins": 0, "weapon_xp": {}, "ports": 0,
                      "wave": 0, "time": 0.0}
        self.interact = Interactables(self)
        self.projectiles = ProjectileManager(self)
        from .combat.gadgets import GadgetManager
        self.gadgets = GadgetManager(self)
        self.viewmodel = ViewModel(app.postfx.vm_root, self.textures, self.lights)
        self.viewmodel.set_scope_view(app.scope)
        vm_amb = {"forest": Vec3(0.75, 0.72, 0.62), "backrooms": Vec3(0.72, 0.64, 0.42)}
        self.viewmodel.anchor.setShaderInput("u_ambient", vm_amb.get(self.map_id,
                                                                     Vec3(0.55, 0.62, 0.7)))
        from .gfx import geom as _geom
        from .gfx.effects import fx_node as _fx_node
        self.laser_np = _geom.beam_mesh()
        self.laser_np.reparentTo(self.world_root)
        _fx_node(self.laser_np, 0, hue_lock=True)
        self.laser_np.setColorScale(3.0, 0.1, 0.08, 1)
        self.laser_np.hide()
        # mode decides combatants and hazards
        from . import modes
        self.mode = modes.create(self, config, showcase)
        hz = self.mode.hazard_config()
        self.hazards = None
        self.hazards = HazardManager(self, **hz)
        self.mode.setup()
        if self.hud:
            self.hud.begin_match(self)
        if not showcase:
            self.audio.menu_music = False
            self.audio.intensity_target = 0.15
        self.countdown_last = 4

    # ================================================================== setup helpers
    def add_combatant(self, name, team, kind, loadout, skin="default", tiers=None,
                      difficulty="normal", show_name=False):
        from .entities.bot import BotBrain
        from .progression.skins import TEAM_COLORS
        c = Combatant(self, self.next_cid, name, team, kind, loadout, skin, tiers,
                      reserve_mult=2.0 if kind == "bot" else 1.0)
        self.next_cid += 1
        if kind == "player":
            self.player = c
            self.player_ctrl = PlayerController(self.app, self, c)
            c.controller = self.player_ctrl
        else:
            team_col = TEAM_COLORS.get(team) if self.mode.team_based else None
            friendly = self.player is not None and self.mode.team_based and team == self.player.team
            c.visual = CharacterVisual(self, skin, team_col, name, show_name=friendly or show_name)
            c.visual.hide()
            if kind == "bot":
                c.controller = BotBrain(self, c, difficulty)
        self.combatants.append(c)
        return c

    def choose_spawn(self, c):
        best = None
        best_d = -1
        enemies = [e for e in self.combatants if e.alive and e is not c and self.hostile(c, e)]
        pts = list(L.SPAWNS)
        self.rng.shuffle(pts)
        for sp in pts:
            x, y, yaw = sp[:3]
            p = Vec3(x, y, L.spawn_z(sp))
            if self.mode.team_based:
                # stay on your team's half
                if (c.team == 0) != (y < 0):
                    continue
            d = min([(e.body.pos - p).length() for e in enemies] or [99])
            if d > best_d:
                best_d = d
                best = sp
        if best is None:
            best = pts[0]
        return (best[0], best[1], L.spawn_z(best)), best[2]

    def spawn(self, c):
        pos, yaw = self.choose_spawn(c)
        self.spawn_at(c, pos, yaw)

    def spawn_at(self, c, pos, yaw):
        c.spawn(pos, yaw)
        if c is self.player and not self.online and not self.showcase:
            boosts = self.app.storage.profile["boosts"]
            if boosts.get("shield", 0) > 0:          # Boost: spawn shield
                c.shield_hp = 40.0
                c.shield_until = self.time + 6.0
            if boosts.get("ammo", 0) > 0:            # Boost: +50% spare ammo
                for w in c.weapons:
                    if not w.melee:
                        w.max_reserve = int(w.stats["reserve"] * 1.5)
                        w.reserve = w.max_reserve
        self.fx.shockwave(Vec3(*pos) + Vec3(0, 0, 0.1), 3.0, (0.2, 1.0, 1.0), 0.5)
        self.fx.sparks_at(Vec3(*pos) + Vec3(0, 0, 1), (0, 0, 1), 20, (0.2, 1.0, 1.0), 4)
        if c.is_player:
            self.player_ctrl.eye_z = c.eye_height()
            self._set_viewmodel()

    # ================================================================== queries
    def living_combatants(self):
        return [c for c in self.combatants if c.alive]

    def hostile(self, a, b):
        if a is b:
            return False
        if getattr(a, "is_hazard", False) or getattr(b, "is_hazard", False):
            return True
        if getattr(b, "is_decoy", False) and b.owner is a:
            return False
        if getattr(a, "is_decoy", False) and a.owner is b:
            return False
        if self.mode.team_based:
            return a.team != b.team
        return True

    def enemies_of(self, c):
        return [e for e in self.combatants if e.alive and self.hostile(c, e)]

    def targets_for(self, c):
        out = self.enemies_of(c)
        out += [d for d in self.decoys if d.alive and self.hostile(c, d)]
        return out

    def hazard_targets(self):
        out = [c for c in self.combatants if c.alive and not c.cloaked]
        out += [d for d in self.decoys if d.alive]
        if self.mode.waves:
            # in survival modes the drones hunt the defenders only
            out = [c for c in out if c.team == 0]
        return out

    def shootables(self, shooter):
        if shooter is None or getattr(shooter, "is_hazard", False):
            return [c for c in self.combatants if c.alive] + [d for d in self.decoys if d.alive]
        out = [c for c in self.combatants if c.alive and self.hostile(shooter, c)]
        out += [d for d in self.decoys if d.alive and self.hostile(shooter, d)]
        if self.hazards:
            out += self.hazards.all_shootable()
        out += self.mode.extra_shootables()
        return out

    def is_targeted(self, c):
        return c is self.crosshair_target

    # ================================================================== damage
    def damage(self, tgt, amount, source, wname, pos=None, headshot=False, kind="bullet",
               dir_=None):
        if amount <= 0 or tgt is None:
            return
        if self.online and kind != "net":
            return          # the server decides all damage in online matches
        if source is not None and getattr(source, "cheats", None) and source.cheats.get("onehit"):
            amount = 9999.0
        player = self.player
        src_is_player = source is not None and source is player
        if getattr(tgt, "is_hazard", False):
            killed = tgt.apply_hit(amount, source, headshot, pos, wname)
            if src_is_player and self.hud:
                self.hud.hit_marker(kill=killed, head=False)
                self.audio.play2d("hitmarker", 0.6)
            return
        if getattr(tgt, "is_decoy", False):
            tgt.take_damage(amount, source)
            if pos is not None:
                self.fx.blood(pos, (0.2, 0.9, 1.0))
            if src_is_player and self.hud:
                self.hud.hit_marker(kill=False, head=headshot)
            return
        if not tgt.alive:
            return
        # friendly fire off (self damage from own explosions is allowed, reduced)
        if source is not None and source is not tgt and not getattr(source, "is_hazard", False) \
                and not getattr(source, "is_decoy", False) and not self.hostile(source, tgt):
            return
        if source is tgt:
            amount *= 0.4
        applied, killed = tgt.take_damage(amount, source, headshot)
        if applied <= 0:
            return
        if pos is not None:
            self.fx.blood(pos, (1.0, 0.3, 0.2) if headshot else (0.2, 0.95, 1.0))
        if src_is_player and tgt is not player:
            self.stats["damage"] += applied
            self.stats["hits"] += 1
            wx = self.stats["weapon_xp"]
            wid = player.weapon().id
            wx[wid] = wx.get(wid, 0) + applied / 10.0
            if self.hud:
                self.hud.hit_marker(kill=killed, head=headshot)
            self.audio.play2d("headshot" if headshot else "hitmarker", 0.8 if headshot else 0.55)
        if tgt is player and self.hud:
            ang = None
            origin = None
            if source is not None and hasattr(source, "center") and source is not tgt:
                try:
                    origin = source.center() if getattr(source, "is_hazard", False) \
                        else source.chest_pos()
                except Exception:
                    origin = None
            if origin is None and dir_ is not None:
                origin = tgt.chest_pos() - Vec3(dir_) * 5
            if origin is not None:
                d = origin - tgt.body.pos
                ang = math.degrees(math.atan2(-d.x, d.y)) - tgt.yaw
            self.hud.damage_taken(applied, ang)
            self.player_ctrl.add_shake(min(0.25, applied / 120.0))
            self.audio.bump(0.1)
        if killed:
            self.on_kill(tgt, source, wname, headshot, kind)

    def radial_damage(self, pos, radius, dmg, source, wname, kind="explosive", exclude=None):
        pos = Vec3(pos)
        for c in list(self.combatants) + list(self.decoys):
            if not c.alive or c is exclude:
                continue
            cp = c.chest_pos()
            d = (cp - pos).length()
            if d > radius + 0.4:
                continue
            if not self.coll.line_of_sight(pos, cp) and not self.coll.line_of_sight(pos, c.eye_pos()):
                continue
            k = max(0.0, 1.0 - max(0.0, d - 0.5) / radius * 0.7)
            self.damage(c, dmg * k, source, wname, cp, False, kind=kind, dir_=(cp - pos))
            if not c.is_decoy and c.alive:
                push = cp - pos
                if push.length() > 0.01:
                    push.normalize()
                c.body.vel += push * 7.0 * k + Vec3(0, 0, 3.5 * k)
                if kind == "fire":
                    c.ignite(source, 3.0)
        if self.hazards and kind in ("explosive", "plasma"):
            for h in self.hazards.all_shootable():
                if h is source or h is exclude:
                    continue
                d = (h.center() - pos).length()
                if d < radius + h.radius:
                    self.damage(h, dmg * 0.8, source, wname, h.center(), kind=kind)
        # screen shake from nearby explosions
        if self.player is not None and self.player.alive:
            d = (self.player.chest_pos() - pos).length()
            if d < radius * 4:
                self.player_ctrl.add_shake(0.5 * (1 - d / (radius * 4)))

    def flashbang(self, pos, radius, source):
        for c in self.combatants:
            if not c.alive:
                continue
            e = c.eye_pos()
            d = (e - pos).length()
            if d > radius or not self.coll.line_of_sight(pos, e):
                continue
            to = pos - e
            to.normalize()
            facing = max(0.0, to.dot(c.aim_dir()))
            strength = (1 - d / radius) * (0.35 + 0.65 * facing)
            c.flash(min(1.0, strength * 1.4), 1.0 + 2.5 * strength)
            if c is self.player and self.hud:
                self.hud.flash(min(1.0, strength * 1.5), 1.0 + 2.5 * strength)

    def hazard_shot(self, hz, origin, d, dmg, color):
        t_wall, n_wall = self.coll.raycast(origin, d, 80)
        limit = t_wall if t_wall is not None else 80
        best = None
        for c in self.shootables(hz):
            r = c.ray_hit(origin, d, limit)
            if r is not None and (best is None or r[0] < best[0]):
                best = (r[0], c)
        end_t = best[0] if best else limit
        end = origin + d * end_t
        self.fx.beam(origin, end, color, 0.06, 0.07, 3.0)
        self.fx.muzzle(origin, d, color, 0.4, light=False)
        if best:
            self.damage(best[1], dmg, hz, hz.name, end, False, kind="bullet", dir_=d)
        elif t_wall is not None:
            self.fx.impact(end, n_wall, color)

    # ================================================================== events
    def on_kill(self, victim, killer, wname, headshot, kind):
        victim.die()
        self.fx.explosion(victim.chest_pos(), 1.6, "plasma", big=False)
        self.fx.sparks_at(victim.chest_pos(), (0, 0, 1), 50, (0.2, 1.0, 1.0), 8)
        self.audio.play3d("explosion_small", victim.chest_pos(), 0.5)
        killer_c = killer if isinstance(killer, Combatant) else None
        # assist-less credit: environment kills go to the last attacker within 5 s
        if killer_c is None and victim.last_attacker is not None and \
                self.time - victim.last_damage_time < 5.0 and victim.last_attacker is not victim:
            killer_c = victim.last_attacker if isinstance(victim.last_attacker, Combatant) else None
        if killer_c is victim:
            killer_c = None
        kname = killer_c.name if killer_c else (getattr(killer, "name", "") or "ARENA")
        if self.hud:
            self.hud.add_kill(kname, victim.name, wname, headshot,
                              killer_c is self.player, victim is self.player,
                              self._team_color(killer_c), self._team_color(victim))
        if killer_c is not None:
            killer_c.kills += 1
            killer_c.streak += 1
            killer_c.best_streak = max(killer_c.best_streak, killer_c.streak)
            if self.time - killer_c.last_kill_time < 4.0:
                killer_c.multi += 1
            else:
                killer_c.multi = 1
            killer_c.last_kill_time = self.time
            # drops from bots killed by the player
            if killer_c is self.player:
                self.interact.drop(victim.body.pos, self.rng.randint(4, 9), 60)
        if not self.first_blood and killer_c is not None and not self.showcase:
            self.first_blood = True
            if killer_c is self.player:
                self._announce("first_blood")
        if killer_c is not None and killer_c is self.player:   # no player in the menu showcase
            st = self.stats
            st["kills"] += 1
            st["xp"] += 100 + (25 if headshot else 0)
            if not self.showcase:
                from .progression.shop import HEADSHOT_BONUS, KILL_COINS
                earned = KILL_COINS + (HEADSHOT_BONUS if headshot else 0)
                st["coins"] += earned
                if self.hud:
                    self.hud.notice(i18n.t("pickup_coins", n=earned), (1.0, 0.85, 0.3, 1), 1.4)
            if headshot:
                st["headshots"] += 1
                if self.player.multi <= 1:
                    self._announce("headshot", voice=False)
            wid = self.player.weapon().id
            st["weapon_kills"][wid] = st["weapon_kills"].get(wid, 0) + 1
            st["weapon_xp"][wid] = st["weapon_xp"].get(wid, 0) + 10
            if kind == "melee":
                st["melee_kills"] += 1
            st["best_streak"] = max(st["best_streak"], self.player.streak)
            call = MULTI_CALLS.get(min(self.player.multi, 4)) if self.player.multi >= 2 else None
            if call:
                self._announce(call)
            elif self.player.streak in STREAK_CALLS:
                self._announce(STREAK_CALLS[self.player.streak])
            if self.hud:
                self.hud.notice(i18n.t("kill_confirm", name=victim.name), (0.3, 1.0, 1.0, 1), 1.5)
            self.audio.play2d("kill", 0.7)
            self.audio.bump(0.25)
        if victim is self.player:
            self.stats["deaths"] += 1
            if self.hud:
                self.hud.notice(i18n.t("killed_by", name=kname), (1.0, 0.3, 0.3, 1), 3.0)
        self.mode.on_kill(victim, killer_c)
        self._check_lead()

    def _team_color(self, c):
        if c is None:
            return (1.0, 0.5, 0.2, 1)
        if c is self.player:
            return (0.3, 1.0, 1.0, 1)
        if self.mode.team_based and self.player is not None:
            return (0.3, 0.9, 1.0, 1) if c.team == self.player.team else (1.0, 0.3, 0.4, 1)
        return (0.85, 0.85, 0.9, 1)

    def _check_lead(self):
        if self.mode.team_based or self.player is None or self.showcase:
            return
        leader = max(self.combatants, key=lambda c: (c.score, -c.deaths))
        if leader.cid != self.leader_cid:
            prev = self.leader_cid
            self.leader_cid = leader.cid
            if leader is self.player and leader.score > 0:
                self._announce("lead_taken")
            elif prev == self.player.cid:
                self._announce("lead_lost")

    def _announce(self, key, voice=True):
        if self.showcase:
            return
        if voice:
            self.audio.announce(key)
        if self.hud:
            cap = i18n.t("ann_" + key) if ("ann_" + key) in i18n.STRINGS["en"] else ""
            if key == "headshot":
                cap = i18n.t("headshot")
            if cap:
                self.hud.announcer_caption(cap)

    def on_hazard_destroyed(self, h, source):
        if source is not None and source is self.player:
            self.stats["hazards"] += 1
            self.stats["xp"] += 60
            from .progression.shop import HAZARD_COINS
            self.stats["coins"] += HAZARD_COINS
            if h.name == "DRONE":
                self.stats["drones"] += 1
            elif h.name == "TURRET":
                self.stats["turrets"] += 1
                self.interact.drop(h.center(), 10, 40)
        self.mode.on_hazard_destroyed(h, source)

    def spawn_decoy(self, owner, duration):
        self.decoys.append(Decoy(self, owner, duration))

    def warn_player(self, kind, pos):
        if self.hud:
            self.hud.warn(kind, pos)

    def ability_denied(self, reason):
        if self.hud and reason == "energy":
            self.hud.notice(i18n.t("not_enough_energy"), (1.0, 0.5, 0.3, 1), 0.8)
            self.audio.play2d("ability_denied")
        elif reason in ("cooldown", "locked"):
            self.audio.play2d("ability_denied", 0.5)

    def gadget_denied(self, reason, c):
        if not self.hud:
            return
        if reason == "no_bombs":
            self.hud.notice(i18n.t("no_bombs"), (1.0, 0.5, 0.3, 1), 1.0)
        elif reason == "drone_cd":
            self.hud.notice(i18n.t("drone_cd", n=int(math.ceil(c.drone_ready_at - self.time))),
                            (1.0, 0.5, 0.3, 1), 1.0)
        self.audio.play2d("ability_denied", 0.6)

    def on_loot(self, c, ammo, coins):
        if not self.online:
            from neon_shared.gadgets import BOMBS_PER_LIFE
            c.bombs = min(BOMBS_PER_LIFE + 1, c.bombs + 1)      # loot boxes carry a spare bomb
        if c is self.player:
            self.stats["loot"] += 1
            if self.hud:
                self.hud.notice(i18n.t("pickup_ammo", n=ammo), (1.0, 0.85, 0.3, 1), 1.6)

    def on_pickup(self, c, kind, amount):
        if c is self.player:
            if kind == "coin":
                self.stats["coins"] += amount
                self.audio.play2d("coin", 0.5)
            else:
                self.stats["xp"] += amount
                self.audio.play2d("pickup", 0.35)

    def on_port_charge(self, c):
        if c is self.player:
            self.stats["ports"] += 1
            if self.hud:
                self.hud.notice(i18n.t("energy_full"), (0.3, 1.0, 0.6, 1), 1.2)

    def on_slide(self, c):
        self.audio.play3d("slide", c.body.pos, 0.6, source=c)
        if c is self.player:
            self.stats["slides"] += 1

    def on_ability(self, c, aid):
        if c is self.player:
            self.stats["abilities"] += 1
            self.audio.bump(0.1)

    def on_weapon_switch(self, c):
        self.audio.play3d("switch", c.body.pos, 0.5, source=c)
        if c is self.player:
            self._set_viewmodel()

    def on_reload(self, c, ws):
        self.audio.play3d("reload", c.body.pos, 0.6, source=c)
        if self.net is not None and getattr(c, "net_local", False):
            self.net.local_reload(ws, c)

    def on_fired(self, c, ws):
        # gunfire gives away your position to nearby bots - unless suppressed
        if not ws.melee:
            hear = 7.0 if "suppressed" in ws.stats.get("flags", ()) else 38.0
            for b in self.combatants:
                brain = b.controller
                if b is c or not b.alive or not b.is_bot or brain is None or \
                        not self.hostile(b, c) or brain.target is not None:
                    continue
                if (b.body.pos - c.body.pos).lengthSquared() < hear * hear:
                    brain.last_seen_pos = Vec3(c.body.pos)
                    brain.last_seen_time = self.time
                    brain.repath_t = 0.0
        if c is self.player:
            if ws.melee:
                self.viewmodel.start_swing()
            else:
                self.viewmodel.kick(0.35 + ws.stats["recoil"] * 0.18)

    def stat_shot(self, shooter, stats):
        if shooter is self.player:
            self.stats["shots"] += 1

    def shake(self, amount):
        if self.player_ctrl is not None:
            self.player_ctrl.add_shake(amount)

    def _set_viewmodel(self):
        if self.player is None:
            return
        skin = self.app.storage.profile["equipped"]["weapon_skin"]
        self.viewmodel.set_weapon(self.player.weapon().stats, skin)

    # ================================================================== update
    def update(self, dt):
        self.time += dt
        if self.state == "countdown":
            self.state_t -= dt
            n = int(math.ceil(self.state_t))
            if n != self.countdown_last and n >= 1 and n <= 3:
                self.countdown_last = n
                self._announce({3: "three", 2: "two", 1: "one"}[n])
                self.audio.play2d("countdown")
            if self.state_t <= 0:
                self.state = "live"
                self.frozen = False
                self._announce("fight")
                self.audio.play2d("match_start", 0.7)
        elif self.state == "ended":
            self.state_t -= dt
        # controllers
        if self.player_ctrl is not None:
            self.player_ctrl.update(dt)
            ch = getattr(self.player, "cheats", None)
            if ch and self.player.alive:
                from .ui import hack_menu
                if ch.get("aimbot"):
                    hack_menu.aimbot(self, self.player, dt)
                if ch.get("esp"):
                    hack_menu.esp(self, self.player)
        if not self.frozen:
            for c in self.combatants:
                if c.controller is not None and not c.is_player:
                    c.controller.update(dt)
        for c in self.combatants:
            if c.alive and (not self.frozen or c.is_player):
                if self.frozen:
                    # allow looking around during the countdown only
                    c.input.clear()
                c.update(dt)
        if L.KILL_Z is not None and not self.frozen:
            for c in self.combatants:
                if c.alive and c.body.pos.z < L.KILL_Z:
                    if self.online:
                        c.body.vel = Vec3(0, 0, 0)      # the server registers the fall
                    else:
                        c.spawn_protect_until = 0.0
                        c.shield_hp = 0.0
                        self.damage(c, 999, None, "FALL", c.chest_pos(), kind="fall")
        for d in self.decoys:
            d.update(dt)
        self.decoys = [d for d in self.decoys if d.alive]
        if not self.frozen:
            self.wells = [w for w in self.wells if w.update(dt)]
            self.projectiles.update(dt)
            self.gadgets.update(dt)
            if self.hazards:
                self.hazards.update(dt, self.time)
            self.interact.update(dt, self.time)
            self.mode.update(dt)
            # respawns
            for c in self.combatants:
                if not c.alive and not c.eliminated:
                    c.respawn_timer -= dt
                    if c.respawn_timer <= 0:
                        if self.mode.can_respawn(c):
                            self.spawn(c)
                        else:
                            c.eliminated = True
            self.stats["time"] += dt
        else:
            self.interact.update(0.0, self.time)
        # visuals
        cam = self.app.camera
        if self.player_ctrl is not None:
            self.player_ctrl.update_camera(dt)
            self._update_crosshair_target()
        self.lights.update(dt, cam.getPos(self.render), self.time)
        self.fx.update(dt)
        self.arena.update(self.time)
        self._update_laser()
        if self.player is not None:
            mdx = self.app.input.mouse_dx
            mdy = self.app.input.mouse_dy
            self.viewmodel.update(dt, self.player, self.player.weapon(), mdx, mdy,
                                  self.lights.hue, self.lights.gain)
        if self.hud:
            self.hud.update(dt, self)

    def _update_laser(self):
        p = self.player
        ws = p.weapon() if p is not None else None
        if p is None or not p.alive or ws.melee or "laser" not in ws.stats.get("flags", ()) \
                or (ws.stats["scoped"] and p.input.ads) or ws.reloading:
            self.laser_np.hide()
            return
        o = p.muzzle_pos()
        d = p.aim_dir()
        t, n = self.coll.raycast(o, d, 60.0)
        best = t if t is not None else 60.0
        for c in self.combatants:
            if c is not p and c.alive:
                r = c.ray_hit(o, d, best)
                if r is not None:
                    best = r[0]
        end = o + d * best
        self.laser_np.show()
        self.laser_np.setPos(o)
        self.laser_np.lookAt(end)
        self.laser_np.setScale(0.012, best, 0.012)
        self.fx.glow.emit(1, end - d * 0.05, (0, 0, 0), 0.03, 0.09, 0.09, (4, 0.2, 0.1, 1),
                          (4, 0.2, 0.1, 1))

    def _update_crosshair_target(self):
        p = self.player
        self.crosshair_target = None
        if p is None or not p.alive:
            return
        o = p.eye_pos()
        d = p.aim_dir()
        t_wall, _ = self.coll.raycast(o, d, 60)
        lim = t_wall if t_wall is not None else 60
        best = None
        for c in self.combatants:
            if c is p or not c.alive or c.cloaked:
                continue
            r = c.ray_hit(o, d, lim)
            if r is not None and (best is None or r[0] < best[0]):
                best = (r[0], c)
        if best:
            self.crosshair_target = best[1]

    def end(self, result):
        if self.state == "ended":
            return
        self.state = "ended"
        self.state_t = 3.5
        self.frozen = True
        self.result = result
        won = result.get("won")
        if won is True:
            self._announce("victory")
        elif won is False:
            self._announce("defeat")
        if self.hud:
            txt = i18n.t("you_win") if won else (i18n.t("draw") if won is None else i18n.t("you_lose"))
            self.hud.big_message(txt, result.get("subtitle", ""), 3.5)
        log.info("Match ended: %s", result)

    def cleanup(self):
        self.app.scope.set_active(False)
        if self.hazards:
            self.hazards.cleanup()
        for c in self.combatants:
            if c.visual:
                c.visual.destroy()
        for d in self.decoys:
            if d.alive:
                d.visual.destroy()
        for w in self.wells:
            w.remove()
        self.fx.clear()
        self.gadgets.cleanup()
        self.mode.cleanup()
        if self.viewmodel.current is not None:
            self.viewmodel.current.detachNode()
        self.viewmodel.anchor.removeNode()
        for n in (self.world_root, self.overlay_root, self.arena.floor):
            n.removeNode()
        if self.arena.mirror is not None:
            self.arena.mirror.removeNode()
        self.render.clearShaderInput("u_lightPos")
        if self.hud:
            self.hud.end_match()
