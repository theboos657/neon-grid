"""JSON persistence for settings, profile, stats and high scores.

Every file is written atomically (temp file + replace) and loaded by deep
merging on top of the defaults, so adding new settings in an update never
breaks an old save file and a corrupt file falls back to defaults (the bad
file is kept as ``*.corrupt`` for inspection).
"""

import copy
import json
import logging
import os

from . import paths

log = logging.getLogger("storage")

DEFAULT_BINDINGS = {
    "forward": "w", "back": "s", "left": "a", "right": "d",
    "jump": "space", "sprint": "lshift", "crouch": "lcontrol",
    "fire": "mouse1", "ads": "mouse3", "reload": "r",
    "ability1": "q", "ability2": "e", "melee": "v",
    "weapon1": "1", "weapon2": "2", "weapon3": "3",
    "scoreboard": "tab", "interact": "f",
}

# HUD element defaults.  x/y are fractions of the half-screen (-1..1);
# x is multiplied by the aspect ratio when placed.
DEFAULT_HUD_ELEMENTS = {
    "health":    {"x": -0.95, "y": -0.86, "scale": 1.0, "opacity": 1.0, "visible": True},
    "energy":    {"x": -0.95, "y": -0.955, "scale": 1.0, "opacity": 1.0, "visible": True},
    "ammo":      {"x": 0.95, "y": -0.88, "scale": 1.0, "opacity": 1.0, "visible": True},
    "abilities": {"x": 0.0, "y": -0.88, "scale": 1.0, "opacity": 1.0, "visible": True},
    "crosshair": {"x": 0.0, "y": 0.0, "scale": 1.0, "opacity": 1.0, "visible": True},
    "killfeed":  {"x": 0.95, "y": 0.9, "scale": 1.0, "opacity": 1.0, "visible": True},
    "matchinfo": {"x": 0.0, "y": 0.92, "scale": 1.0, "opacity": 1.0, "visible": True},
    "notices":   {"x": 0.0, "y": -0.45, "scale": 1.0, "opacity": 1.0, "visible": True},
    "damage_dir": {"x": 0.0, "y": 0.0, "scale": 1.0, "opacity": 1.0, "visible": True},
}

DEFAULT_SETTINGS = {
    "version": 1,
    "language": "en",
    "video": {
        "quality": "high",          # "high" | "low"
        "fullscreen": False,
        "resolution": [1600, 900],
        "vsync": True,
        "fps_cap": 144,
        "fov": 95,
        "show_fps": False,
        "bloom": 1.0,
        "reflections": True,
    },
    "audio": {"master": 0.8, "music": 0.55, "effects": 0.9, "voice": 0.85, "announcer": True},
    "controls": {"sensitivity": 1.0, "ads_sensitivity": 0.7, "invert_y": False,
                 "toggle_crouch": False, "bindings": dict(DEFAULT_BINDINGS)},
    "gameplay": {"screen_shake": True, "crosshair_style": 0, "crosshair_color": 0,
                 "crosshair_size": 1.0, "crosshair_thickness": 1.0, "crosshair_gap": 0.0,
                 "crosshair_outline": True, "crosshair_dynamic": True,
                 "hit_markers": True, "damage_numbers": False},
    "hud": {"scale": 1.0, "opacity": 0.95, "elements": copy.deepcopy(DEFAULT_HUD_ELEMENTS)},
    "network": {"server": "127.0.0.1:47777", "player_name": "Runner"},
}

DEFAULT_PROFILE = {
    "version": 1,
    "xp_total": 0,
    "coins": 0,
    "upgrade_chips": 0,
    "pass": {"season": 1, "premium": False, "claimed_free": [], "claimed_premium": []},
    "weapon_xp": {},          # weapon id -> xp
    "weapon_bonus_tiers": {}, # tiers unlocked with upgrade chips
    "weapon_tier_sel": {},    # player-selected tier (<= unlocked)
    "owned_weapons": ["ar7", "vx9", "katana"],     # bought with coins (progression/shop.py)
    "owned_abilities": ["dash", "shield"],
    "owned_mods": [],                 # attachments bought with coins
    "boosts": {},                     # boost id -> matches remaining
    "weapon_mods": {},                # weapon id -> {slot: mod id}
    "owned_weapon_skins": ["default"],
    "owned_char_skins": ["default"],
    "equipped": {"weapon_skin": "default", "char_skin": "default", "title": "Rookie"},
    "owned_titles": ["Rookie"],
    "loadout": {"primary": "ar7", "secondary": "vx9", "melee": "katana",
                "abilities": ["dash", "shield"]},
    "achievements": {},
    "challenges": {"date": "", "list": []},
    "last_mode": {"mode": "ffa", "bots": 5, "difficulty": "normal", "lives": False,
                  "lives_count": 3, "chaos": False, "time_limit": 8, "score_limit": 25},
}

DEFAULT_STATS = {
    "version": 1, "kills": 0, "deaths": 0, "headshots": 0, "melee_kills": 0, "matches": 0,
    "wins": 0, "time_played": 0.0, "shots_fired": 0, "shots_hit": 0, "damage": 0,
    "abilities_used": 0, "slides": 0, "loot_boxes": 0, "turrets_destroyed": 0,
    "drones_destroyed": 0, "best_streak": 0, "coins_earned": 0, "weapon_kills": {},
    "team_wins": 0, "chaos_wins": 0, "duel_hard_wins": 0, "flawless_ffa": 0,
    "mp_matches": 0, "port_charges": 0,
}

DEFAULT_HIGHSCORES = {
    "version": 1, "endless_wave": 0, "endless_kills": 0, "ffa_kills": 0,
    "coop_wave": 0, "duel_wins": {"easy": 0, "normal": 0, "hard": 0, "nightmare": 0}, "best_streak": 0,
}


def deep_merge(defaults, loaded):
    """Return defaults updated recursively with values from ``loaded``."""
    out = copy.deepcopy(defaults)
    if not isinstance(loaded, dict):
        return out
    for k, v in loaded.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            # dicts with free-form keys (weapon_xp etc.) merge naturally
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class JsonStore:
    """A dict-like JSON document persisted in the AppData folder."""

    read_only = False       # set by automated test runs so they never touch real saves

    def __init__(self, filename, defaults):
        self.path = paths.data_file(filename)
        self.defaults = defaults
        self.data = copy.deepcopy(defaults)
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = deep_merge(self.defaults, json.load(f))
        except (OSError, ValueError) as e:
            log.warning("Could not read %s (%s); using defaults", self.path, e)
            try:
                os.replace(self.path, self.path + ".corrupt")
            except OSError:
                pass
            self.data = copy.deepcopy(self.defaults)

    def save(self):
        if JsonStore.read_only:
            return
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError as e:
            log.error("Could not save %s: %s", self.path, e)

    def reset(self):
        self.data = copy.deepcopy(self.defaults)
        self.save()

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v

    def get(self, k, default=None):
        return self.data.get(k, default)


class Storage:
    """Bundle of all persistent documents."""

    def __init__(self):
        self.settings = JsonStore("settings.json", DEFAULT_SETTINGS)
        self.profile = JsonStore("profile.json", DEFAULT_PROFILE)
        self.stats = JsonStore("stats.json", DEFAULT_STATS)
        self.highscores = JsonStore("highscores.json", DEFAULT_HIGHSCORES)

    def save_all(self):
        for s in (self.settings, self.profile, self.stats, self.highscores):
            s.save()
