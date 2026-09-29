"""Per-combatant runtime state of one equipped weapon."""

from neon_shared.weapons import weapon_stats

BURST_INTERVAL = 0.065


class WeaponState:
    def __init__(self, wid, tier=0, reserve_mult=1.0, mods=None):
        self.id = wid
        self.stats = weapon_stats(wid, tier, mods)
        self.tier = self.stats["tier"]
        self.melee = self.stats["melee"]
        self.mag = self.stats["mag"]
        self.max_reserve = int(self.stats["reserve"] * reserve_mult)
        self.reserve = self.max_reserve
        self.cooldown = 0.0
        self.reload_left = 0.0
        self.burst_left = 0
        self.burst_t = 0.0
        self.swap_left = 0.0
        self.bloom = 0.0           # extra spread from sustained fire (0..1)
        self.shots_fired = 0

    @property
    def name(self):
        return self.stats["name"]

    @property
    def reloading(self):
        return self.reload_left > 0

    def reload_fraction(self):
        if self.reload_left <= 0:
            return 1.0
        return 1.0 - self.reload_left / max(0.01, self.stats["reload"])

    def draw(self):
        self.swap_left = self.stats["swap"]
        self.reload_left = 0.0
        self.burst_left = 0

    def start_reload(self):
        if self.melee or self.reload_left > 0 or self.reserve <= 0:
            return False
        if self.mag >= self.stats["mag"]:
            return False
        self.reload_left = self.stats["reload"]
        self.burst_left = 0
        return True

    def refill(self, frac):
        """Add ``frac`` of max reserve; returns rounds added."""
        if self.melee:
            return 0
        add = min(self.max_reserve - self.reserve, int(self.max_reserve * frac) + 1)
        add = max(0, add)
        self.reserve += add
        return add

    def needs_ammo(self):
        return not self.melee and self.reserve + self.mag < (self.max_reserve + self.stats["mag"]) * 0.5

    def update(self, dt):
        if self.cooldown > 0:
            self.cooldown -= dt
        if self.swap_left > 0:
            self.swap_left -= dt
        if self.burst_t > 0:
            self.burst_t -= dt
        self.bloom = max(0.0, self.bloom - dt * 2.2)
        if self.reload_left > 0:
            self.reload_left -= dt
            if self.reload_left <= 0:
                need = self.stats["mag"] - self.mag
                take = min(need, self.reserve)
                self.mag += take
                self.reserve -= take
                self.reload_left = 0.0

    def tick_trigger(self, held, pressed, infinite=False):
        """Returns 'fire', 'empty' or None for this frame."""
        if self.swap_left > 0:
            return None
        s = self.stats
        if self.melee:
            if (held or pressed) and self.cooldown <= 0:
                self.cooldown = 1.0 / s["rps"]
                return "fire"
            return None
        if self.reload_left > 0:
            if pressed and self.mag > 0 and s["cls"] == "shotgun":
                self.reload_left = 0.0        # shotguns may interrupt a reload
            else:
                return None
        # continuing burst
        if self.burst_left > 0:
            if self.burst_t <= 0 and self.mag > 0:
                self.burst_left -= 1
                self.burst_t = BURST_INTERVAL
                self._consume(infinite)
                return "fire"
            if self.mag <= 0:
                self.burst_left = 0
            return None
        want = pressed or (held and s["auto"])
        if not want or self.cooldown > 0:
            return None
        if self.mag <= 0:
            if pressed:
                return "empty"
            return None
        self.cooldown = 1.0 / s["rps"]
        if s["burst"] > 1:
            self.burst_left = s["burst"] - 1
            self.burst_t = BURST_INTERVAL
        self._consume(infinite)
        return "fire"

    def _consume(self, infinite):
        self.shots_fired += 1
        if not infinite:
            self.mag -= 1
        self.bloom = min(1.0, self.bloom + 0.07 * self.stats["recoil"])
