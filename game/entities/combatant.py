"""Combatant: anything with health that fights (local player, bots,
wingmen, remote players).  Controllers write into ``input``; the combatant
turns that into movement, weapon use and abilities identically for everyone,
so bots obey exactly the same rules as the player."""

import math

from panda3d.core import Vec3

from neon_shared.abilities import ENERGY_REGEN, MAX_ENERGY
from neon_shared.hitmath import hit_combatant

from . import movement
from ..combat import firing
from ..combat.abilities import AbilityState, try_activate
from ..combat.weapon_state import WeaponState

REGEN_DELAY = 6.0
REGEN_RATE = 9.0


class InputState:
    __slots__ = ("move_x", "move_y", "jump", "sprint", "crouch", "fire", "fire_pressed", "ads",
                 "reload", "melee", "ability", "switch_to", "cycle", "bomb", "drone")

    def __init__(self):
        self.clear()

    def clear(self):
        self.move_x = 0.0
        self.move_y = 0.0
        self.jump = False
        self.sprint = False
        self.crouch = False
        self.fire = False
        self.fire_pressed = False
        self.ads = False
        self.reload = False
        self.melee = False
        self.ability = [False, False]
        self.switch_to = -1
        self.cycle = 0
        self.bomb = False           # hotbar 4
        self.drone = False          # hotbar 5


class Combatant:
    is_hazard = False
    is_decoy = False

    def __init__(self, match, cid, name, team, kind, loadout, skin="default", tiers=None,
                 reserve_mult=1.0):
        self.match = match
        self.cid = cid
        self.name = name
        self.team = team
        self.kind = kind                       # 'player' | 'bot' | 'remote'
        self.is_player = kind == "player"
        self.is_bot = kind == "bot"
        self.is_remote = kind == "remote"
        self.skin = skin
        self.body = movement_body()
        self.yaw = 0.0
        self.pitch = 0.0
        self.input = InputState()
        self.controller = None
        self.visual = None
        self.collects_pickups = self.is_player
        tiers = tiers or {}
        self.loadout = loadout
        mods = loadout.get("mods") or {}        # {weapon id: {slot: mod id}}
        self.weapons = [WeaponState(loadout["primary"], tiers.get(loadout["primary"], 0), reserve_mult,
                                    mods.get(loadout["primary"])),
                        WeaponState(loadout["secondary"], tiers.get(loadout["secondary"], 0),
                                    reserve_mult, mods.get(loadout["secondary"])),
                        WeaponState(loadout["melee"], tiers.get(loadout["melee"], 0))]
        self.slot = 0
        self.bombs = 0              # hotbar 4, refilled on spawn
        self.drone_ready_at = 0.0   # hotbar 5 cooldown (match time)
        self.prev_slot = 1
        self.abilities = [AbilityState(a) for a in loadout["abilities"][:2]]
        # scores
        self.kills = 0
        self.deaths = 0
        self.score = 0
        self.streak = 0
        self.best_streak = 0
        self.multi = 0
        self.last_kill_time = -99.0
        self.lives = None
        self.eliminated = False
        self.ping = 0
        # cheats / debug
        self.god = False
        self.infinite_ammo = False
        self.infinite_energy = False
        self.no_cooldowns = False
        self.aim_error = 0.0
        self.reset_state()
        self.alive = False
        self.respawn_timer = 0.0

    # ------------------------------------------------------------------ lifecycle
    def reset_state(self):
        self.health = 100.0
        self.max_health = 100.0
        self.shield_hp = 0.0
        self.shield_until = 0.0
        self.energy = MAX_ENERGY
        self.crouching = False
        self.sliding = 0.0
        self.slide_cd = 0.0
        self.sprinting = False
        self.air_time = 0.0
        self.jump_lock = 0.0
        self.launched = 0.0
        self.step_phase = 0.0
        self.flash_until = 0.0
        self.flash_strength = 0.0
        self.burn_until = 0.0
        self.burn_source = None
        self.burn_tick = 0.0
        self.stun_until = 0.0
        self.speed_until = 0.0
        self.cloak_until = 0.0
        self.reveal_until = 0.0
        self.revealed_to_team = None
        self.revealed_by = None
        self.ability_lock_until = 0.0
        self.heal_left = 0.0
        self.heal_rate = 0.0
        self.jets_until = 0.0
        self.dash_until = 0.0
        self.last_damage_time = -99.0
        self.last_attacker = None
        self.damage_from = {}
        self.port_progress = 0.0
        self.spawn_protect_until = 0.0

    def spawn(self, pos, yaw):
        self.reset_state()
        self.body.pos = Vec3(*pos)
        self.body.vel = Vec3(0, 0, 0)
        self.body.on_ground = True
        self.yaw = yaw
        self.pitch = 0.0
        self.alive = True
        self.spawn_protect_until = self.match.time + 1.5
        for w in self.weapons:
            w.mag = w.stats["mag"]
            w.reserve = w.max_reserve
            w.reload_left = 0.0
            w.cooldown = 0.0
            w.burst_left = 0
        for a in self.abilities:
            a.cooldown_left = 0.0
        from neon_shared.gadgets import BOMBS_PER_LIFE
        self.bombs = BOMBS_PER_LIFE
        self.slot = 0
        self.weapons[0].draw()
        self.input.clear()
        if self.visual:
            self.visual.show()

    # ------------------------------------------------------------------ geometry
    def eye_height(self):
        return 1.05 if self.crouching else 1.62

    def eye_pos(self):
        return self.body.pos + Vec3(0, 0, self.eye_height())

    def chest_pos(self):
        return self.body.pos + Vec3(0, 0, 0.8 if self.crouching else 1.2)

    def center(self):
        return self.chest_pos()

    def aim_dir(self):
        y = math.radians(self.yaw)
        p = math.radians(self.pitch)
        return Vec3(-math.sin(y) * math.cos(p), math.cos(y) * math.cos(p), math.sin(p))

    def facing_dir(self):
        y = math.radians(self.yaw)
        return Vec3(-math.sin(y), math.cos(y), 0)

    def muzzle_pos(self):
        if self.is_player:
            y = math.radians(self.yaw)
            right = Vec3(math.cos(y), math.sin(y), 0)
            return self.eye_pos() + self.aim_dir() * 0.7 + right * 0.16 - Vec3(0, 0, 0.14)
        if self.visual is not None:
            return self.visual.muzzle_world()
        return self.eye_pos() + self.aim_dir() * 0.6

    def ray_hit(self, o, d, max_t):
        if not self.alive:
            return None
        return hit_combatant(o, d, self.body.pos, self.crouching, max_t)

    @property
    def cloaked(self):
        return self.match.time < self.cloak_until

    @property
    def radius(self):
        return self.body.radius

    def weapon(self):
        return self.weapons[self.slot]

    # ------------------------------------------------------------------ state changes
    def needs_loot(self):
        return any(w.needs_ammo() for w in self.weapons)

    def refill_ammo(self, frac):
        total = 0
        for w in self.weapons:
            total += w.refill(frac)
        return total

    def ignite(self, source, duration):
        self.burn_until = max(self.burn_until, self.match.time + duration)
        self.burn_source = source

    def flash(self, strength, duration):
        self.flash_until = max(self.flash_until, self.match.time + duration)
        self.flash_strength = max(self.flash_strength if self.match.time < self.flash_until
                                  else 0.0, strength)

    def on_fire(self):
        if self.cloaked:
            self.cloak_until = 0.0

    def on_land(self, fall_speed):
        if fall_speed > 7.0:
            self.match.audio.play3d("land", self.body.pos, min(1.0, fall_speed / 14), source=self)

    def take_damage(self, amount, source, headshot=False):
        """Apply damage; returns (applied, killed)."""
        m = self.match
        if not self.alive or self.god or m.time < self.spawn_protect_until:
            return 0.0, False
        if m.time < self.shield_until and self.shield_hp > 0:
            absorbed = min(self.shield_hp, amount)
            self.shield_hp -= absorbed
            amount -= absorbed
            if self.shield_hp <= 0:
                self.shield_until = 0
        self.health -= amount
        self.last_damage_time = m.time
        if source is not None and source is not self and not getattr(source, "is_hazard", False):
            self.last_attacker = source
            self.damage_from[source.cid] = self.damage_from.get(source.cid, 0) + amount
        if self.health <= 0:
            self.health = 0
            self.alive = False
            return amount, True
        return amount, False

    def die(self):
        self.alive = False
        self.deaths += 1
        self.streak = 0
        self.crouching = False
        if self.visual:
            self.visual.hide()

    # ------------------------------------------------------------------ per frame
    def update(self, dt):
        if not self.alive:
            return
        m = self.match
        now = m.time
        inp = self.input
        # status effects
        if now < self.burn_until:
            self.burn_tick -= dt
            if self.burn_tick <= 0:
                self.burn_tick = 0.5
                m.damage(self, 6, self.burn_source, "FIRE", self.chest_pos(), False, kind="fire")
                if m.fx.q > 0.5 or self.is_player:
                    m.fx.glow.emit(4, self.body.pos + Vec3(0, 0, 0.8), (0, 0, 2.5), 0.5, 0.45,
                                   0.1, (3.5, 1.2, 0.2, 1), (0.5, 0.05, 0, 0), pos_jitter=0.35)
            if not self.alive:
                return
        if self.heal_left > 0:
            h = min(self.heal_left, self.heal_rate * dt)
            self.heal_left -= h
            self.health = min(self.max_health, self.health + h)
        elif now - self.last_damage_time > REGEN_DELAY and self.health < self.max_health:
            self.health = min(self.max_health, self.health + REGEN_RATE * dt)
        if self.energy < MAX_ENERGY:
            self.energy = min(MAX_ENERGY, self.energy + ENERGY_REGEN * dt)
        if now >= self.shield_until:
            self.shield_hp = 0.0

        if not self.is_remote:
            movement.update(self, dt)
            self._weapons(dt, inp)
            for i, ab in enumerate(self.abilities):
                ab.update(dt)
                if inp.ability[i]:
                    r = try_activate(m, self, ab)
                    if r is not True and self.is_player:
                        m.ability_denied(r)
            if inp.bomb or inp.drone:
                err = m.gadgets.throw(self) if inp.bomb else m.gadgets.deploy(self)
                if err and self.is_player:
                    m.gadget_denied(err, self)
                inp.bomb = inp.drone = False
        if self.visual is not None:
            hs = math.hypot(self.body.vel.x, self.body.vel.y)
            cloak = 1.0
            if self.cloaked:
                cloak = 0.06 + 0.05 * math.sin(now * 9)
            revealed = now < self.reveal_until and m.player is not None and \
                self.revealed_to_team == m.player.team and self.team != m.player.team
            self.visual.update(dt, self.body.pos, self.yaw, self.pitch, hs, self.crouching,
                               cloak, revealed, False)
        inp.jump = False
        inp.fire_pressed = False
        inp.reload = False
        inp.melee = False
        inp.ability = [False, False]
        inp.switch_to = -1
        inp.cycle = 0

    def _weapons(self, dt, inp):
        m = self.match
        for w in self.weapons:
            w.update(dt)
        # switching
        target = -1
        if inp.melee:
            target = 2
        elif inp.switch_to >= 0:
            target = inp.switch_to
        elif inp.cycle:
            target = (self.slot + inp.cycle) % 3
        if target >= 0 and target != self.slot:
            self.prev_slot = self.slot
            self.slot = target
            self.weapons[target].draw()
            m.on_weapon_switch(self)
        ws = self.weapon()
        if inp.reload and ws.start_reload():
            m.on_reload(self, ws)
        fired = ws.tick_trigger(inp.fire, inp.fire_pressed or (inp.melee and ws.melee),
                                self.infinite_ammo)
        if fired == "fire":
            firing.fire(m, self, ws)
            m.on_fired(self, ws)
        elif fired == "empty":
            m.audio.play3d("empty", self.eye_pos(), 0.6, source=self)
            if ws.reserve > 0 and ws.start_reload():
                m.on_reload(self, ws)
        # auto reload when empty
        if not ws.melee and ws.mag <= 0 and ws.reload_left <= 0 and ws.reserve > 0 \
                and ws.burst_left == 0 and ws.cooldown <= 0:
            if ws.start_reload():
                m.on_reload(self, ws)
        # auto-switch to melee when completely dry
        if not ws.melee and ws.mag <= 0 and ws.reserve <= 0 and not self.is_player:
            other = self.weapons[1 - self.slot] if self.slot < 2 else None
            tgt = 1 - self.slot if other and (other.mag > 0 or other.reserve > 0) else 2
            self.prev_slot = self.slot
            self.slot = tgt
            self.weapons[tgt].draw()


def movement_body():
    from ..world.collision import Body
    return Body()
