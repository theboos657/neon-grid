"""Weapon catalogue: 20 ranged guns, 10 melee weapons and 5 upgrade tiers.

Balance notes
-------------
* Base health is 100.  Most automatic guns kill in 5-8 body shots, precision
  guns reward headshots, and every high-damage weapon pays for it with a
  slow fire rate, small magazine or long reload.
* Upgrade tiers are *side-grades*: each one gives a small bonus paired with a
  small cost, so a tier-5 weapon is only ~6-8% stronger than tier 0 overall.
* The server imports this module to validate fire rate, magazine usage and
  damage, so values here are authoritative for multiplayer too.
"""

from copy import deepcopy

# --------------------------------------------------------------------------
# Field reference
#   dmg        damage per bullet/pellet            rps     rounds per second
#   mag        magazine size                       reload  seconds
#   spread     cone half-angle in degrees (hip)    pellets bullets per shot
#   range      full-damage distance (m)            maxr    max hit distance
#   falloff    damage multiplier at maxr           auto    hold-to-fire
#   burst      rounds per trigger pull             speed   projectile m/s (0 = hitscan)
#   splash / splash_dmg  explosion radius/damage   pierce  rail passes through bodies
#   hs         headshot multiplier                 move    move speed multiplier
#   swap       draw time (s)                       recoil  view kick in degrees
#   zoom       ADS FOV multiplier                  color   beam/tracer RGB
#   reserve    max spare ammo                      sfx     sound bank key
# --------------------------------------------------------------------------

_BASE = dict(dmg=10, rps=5.0, mag=20, reload=2.0, spread=1.0, pellets=1, range=30.0,
             maxr=120.0, falloff=0.6, auto=False, burst=1, speed=0.0, splash=0.0,
             splash_dmg=0, pierce=False, hs=1.5, move=1.0, swap=0.45, recoil=1.0,
             zoom=0.85, color=(0.2, 1.0, 1.0), reserve=120, sfx="rifle", scoped=False)


def _w(wid, name, cls, **kw):
    d = dict(_BASE)
    d.update(kw)
    d["id"] = wid
    d["name"] = name
    d["cls"] = cls
    d["melee"] = False
    return d


RANGED = [
    # ---- Pistols -----------------------------------------------------------
    _w("vx9", "VX-9 Spark", "pistol", dmg=22, rps=5.0, mag=12, reload=1.2, spread=0.8,
       range=25, maxr=90, reserve=96, swap=0.3, recoil=1.4, sfx="pistol", color=(0.3, 1.0, 1.0)),
    _w("hammer50", "Hammer .50", "pistol", dmg=44, rps=2.0, mag=7, reload=1.7, spread=0.6,
       range=30, maxr=100, reserve=56, swap=0.35, recoil=3.2, sfx="heavy_pistol", hs=1.6,
       color=(0.4, 0.9, 1.0)),
    _w("flicker", "Twin Flicker", "pistol", dmg=12, rps=13.0, mag=24, reload=1.4, spread=2.3,
       range=14, maxr=60, auto=True, reserve=144, swap=0.3, recoil=0.7, sfx="pistol",
       color=(0.2, 0.9, 1.0)),
    # ---- SMGs ----------------------------------------------------------------
    _w("hornet", "Hornet SMG", "smg", dmg=13, rps=14.0, mag=32, reload=1.8, spread=2.0,
       range=16, maxr=70, auto=True, reserve=192, move=1.05, recoil=0.6, sfx="smg"),
    _w("wasp", "Wasp-K", "smg", dmg=16, rps=11.0, mag=28, reload=1.9, spread=1.6,
       range=18, maxr=75, auto=True, reserve=168, move=1.04, recoil=0.8, sfx="smg",
       color=(0.3, 0.8, 1.0)),
    _w("buzz", "Static Buzz", "smg", dmg=11, rps=17.0, mag=45, reload=2.2, spread=2.6,
       range=13, maxr=60, auto=True, reserve=225, move=1.05, recoil=0.45, sfx="energy_smg",
       color=(0.5, 0.9, 1.0)),
    # ---- Rifles --------------------------------------------------------------
    _w("ar7", "AR-7 Pulse", "rifle", dmg=20, rps=9.5, mag=30, reload=2.1, spread=1.0,
       range=35, maxr=130, auto=True, reserve=180, recoil=0.9, sfx="rifle"),
    _w("longbow", "Longbow DMR", "rifle", dmg=42, rps=3.5, mag=15, reload=2.4, spread=0.3,
       range=60, maxr=180, reserve=90, recoil=2.2, sfx="dmr", zoom=0.6, hs=1.7, move=0.95,
       scoped=True),
    _w("triburst", "Tri-Burst", "rifle", dmg=24, rps=3.0, mag=24, reload=2.2, spread=0.7,
       range=40, maxr=140, burst=3, reserve=144, recoil=1.1, sfx="rifle", color=(0.2, 1.0, 0.9)),
    _w("lmg", "Neon LMG", "rifle", dmg=18, rps=11.0, mag=80, reload=4.0, spread=1.8,
       range=30, maxr=120, auto=True, reserve=240, move=0.85, swap=0.8, recoil=0.8, sfx="lmg"),
    # ---- Shotguns --------------------------------------------------------------
    _w("breaker", "Breaker Pump", "shotgun", dmg=11, pellets=10, rps=1.1, mag=6, reload=2.8,
       spread=6.0, range=8, maxr=35, falloff=0.25, reserve=36, recoil=4.0, sfx="shotgun",
       hs=1.25),
    _w("riot", "Riot Auto", "shotgun", dmg=8, pellets=8, rps=3.0, mag=10, reload=2.6,
       spread=7.0, range=7, maxr=30, falloff=0.25, auto=True, reserve=50, recoil=2.6,
       sfx="shotgun", hs=1.2),
    _w("scatter", "Scatter Coil", "shotgun", dmg=7, pellets=12, rps=1.6, mag=8, reload=2.4,
       spread=8.0, range=9, maxr=35, falloff=0.3, reserve=48, recoil=3.0, sfx="energy_shotgun",
       hs=1.2, color=(0.4, 1.0, 1.0)),
    # ---- Snipers ---------------------------------------------------------------
    _w("needle", "Needle Bolt", "sniper", dmg=95, rps=0.8, mag=5, reload=3.0, spread=0.05,
       range=120, maxr=250, falloff=0.9, hs=2.0, reserve=25, move=0.9, swap=0.7, recoil=5.5,
       zoom=0.3, sfx="sniper", scoped=True, color=(0.6, 1.0, 1.0)),
    _w("viper", "Viper Semi", "sniper", dmg=62, rps=1.8, mag=8, reload=2.8, spread=0.1,
       range=100, maxr=220, falloff=0.85, hs=1.8, reserve=40, move=0.92, swap=0.6, recoil=4.0,
       zoom=0.4, sfx="sniper", scoped=True),
    # ---- Plasma (projectiles) --------------------------------------------------
    _w("caster", "Plasma Caster", "plasma", dmg=26, rps=4.0, mag=20, reload=2.3, spread=0.6,
       speed=75, splash=1.6, splash_dmg=10, range=200, maxr=200, falloff=1.0, reserve=100,
       recoil=1.2, sfx="plasma", hs=1.3, color=(0.2, 0.8, 1.0)),
    _w("nova", "Nova Launcher", "plasma", dmg=55, rps=0.9, mag=4, reload=3.0, spread=0.3,
       speed=38, splash=3.6, splash_dmg=55, range=200, maxr=200, falloff=1.0, reserve=16,
       move=0.9, swap=0.7, recoil=4.5, sfx="nova", hs=1.0, color=(0.5, 0.9, 1.0)),
    _w("photon", "Photon Repeater", "plasma", dmg=14, rps=10.0, mag=40, reload=2.2, spread=1.3,
       speed=110, splash=0.0, range=200, maxr=200, falloff=1.0, auto=True, reserve=200,
       recoil=0.6, sfx="photon", hs=1.4, color=(0.3, 1.0, 0.95)),
    # ---- Rail (short laser pulses, pierce) --------------------------------------
    _w("lance", "Rail Lance", "rail", dmg=78, rps=1.0, mag=4, reload=2.9, spread=0.05,
       range=200, maxr=200, falloff=1.0, pierce=True, hs=1.6, reserve=24, move=0.92, swap=0.6,
       recoil=4.2, zoom=0.55, sfx="rail", color=(0.1, 1.0, 1.0)),
    _w("arcrail", "Arc Rail", "rail", dmg=26, rps=4.0, mag=12, reload=2.3, spread=0.4,
       range=80, maxr=160, falloff=0.8, pierce=True, hs=1.5, reserve=84, recoil=1.8,
       sfx="rail_light", color=(0.3, 0.95, 1.0)),
]

# --------------------------------------------------------------------------
# Melee: rps = swings/second, range metres, arc = degrees of the hit cone.
# --------------------------------------------------------------------------


def _m(wid, name, dmg, rps, rng, arc=70, knock=2.0, back=1.0, stun=0.0, color=(0.2, 1, 1),
       move=1.1, style="slash"):
    d = dict(_BASE)
    d.update(id=wid, name=name, cls="melee", melee=True, dmg=dmg, rps=rps, range=rng,
             maxr=rng, arc=arc, knock=knock, backstab=back, stun=stun, color=color, move=move,
             mag=0, reserve=0, reload=0.0, swap=0.25, sfx="melee", hs=1.0, auto=True,
             style=style)
    return d


# ``move`` scales with weight while the melee weapon is held: the smaller the
# weapon, the faster you run (knife 1.5x ... grav hammer 0.7x).
MELEE = [
    _m("knife", "Mono Knife", 35, 3.0, 1.8, arc=60, back=2.0, move=1.5, style="stab"),
    _m("claws", "Twin Claws", 25, 4.0, 1.9, arc=70, move=1.4, style="slash"),
    _m("fist", "Pulse Fist", 45, 2.0, 1.9, knock=6.0, move=1.3, style="bash",
       color=(0.5, 0.9, 1.0)),
    _m("baton", "Shock Baton", 40, 2.2, 2.0, stun=0.35, move=1.25, color=(0.4, 0.8, 1.0),
       style="bash"),
    _m("katana", "Neon Katana", 55, 1.6, 2.4, arc=80, move=1.15, style="slash"),
    _m("whip", "Laser Whip", 38, 1.8, 3.6, arc=45, move=1.1, style="slash",
       color=(0.2, 1.0, 0.85)),
    _m("chainblade", "Chain Blade", 30, 3.2, 2.2, arc=75, move=1.05, style="slash"),
    _m("spear", "Photon Spear", 50, 1.4, 3.2, arc=35, move=0.95, style="stab"),
    _m("axe", "Plasma Axe", 75, 0.9, 2.3, arc=60, knock=4.0, move=0.85, style="chop"),
    _m("gravhammer", "Grav Hammer", 85, 0.7, 2.4, arc=70, knock=9.0, move=0.7, style="chop"),
]

ALL = RANGED + MELEE
BY_ID = {w["id"]: w for w in ALL}
RANGED_IDS = [w["id"] for w in RANGED]
MELEE_IDS = [w["id"] for w in MELEE]

# --------------------------------------------------------------------------
# Upgrade tiers.  Effects are cumulative (tier 3 includes tiers 1-3).
# Multipliers apply to the named stat; each tier trades something away.
# --------------------------------------------------------------------------
TIERS = [
    {"key": "tier1", "name": "Tuned Barrel", "desc": "+6% damage, +6% spread",
     "mods": {"dmg": 1.06, "spread": 1.06}},
    {"key": "tier2", "name": "Rapid Cycler", "desc": "+8% fire rate, +10% recoil",
     "mods": {"rps": 1.08, "recoil": 1.10}},
    {"key": "tier3", "name": "Quick Mag", "desc": "-15% reload time, -5% handling",
     "mods": {"reload": 0.85, "swap": 1.05}},
    {"key": "tier4", "name": "Extended Cell", "desc": "+20% magazine, -3% move speed",
     "mods": {"mag": 1.20, "move": 0.97}},
    {"key": "tier5", "name": "Balanced Grip", "desc": "-12% spread, +10% handling, -2% damage",
     "mods": {"spread": 0.88, "swap": 0.90, "dmg": 0.98}},
]
# Melee tiers reuse the slots with melee-appropriate stats.
MELEE_TIERS = [
    {"key": "tier1", "name": "Honed Edge", "desc": "+6% damage, -3% swing speed",
     "mods": {"dmg": 1.06, "rps": 0.97}},
    {"key": "tier2", "name": "Light Alloy", "desc": "+8% swing speed, -3% damage",
     "mods": {"rps": 1.08, "dmg": 0.97}},
    {"key": "tier3", "name": "Long Reach", "desc": "+8% range, -4% swing speed",
     "mods": {"range": 1.08, "rps": 0.96}},
    {"key": "tier4", "name": "Servo Grip", "desc": "+5% move speed, -2% damage",
     "mods": {"move": 1.05, "dmg": 0.98}},
    {"key": "tier5", "name": "Overcharge", "desc": "+5% damage, +5% swing speed, -5% range",
     "mods": {"dmg": 1.05, "rps": 1.05, "range": 0.95}},
]

# Weapon XP (damage dealt / 10 + kills*10) required to unlock each tier.
TIER_XP = [150, 450, 900, 1600, 2600]
MAX_TIER = 5


def weapon_stats(wid, tier=0, mods=None):
    """Return a fresh dict of effective stats for weapon ``wid`` at ``tier``
    with the attachment ``mods`` ({slot: mod_id}) applied."""
    base = BY_ID.get(wid) or BY_ID["vx9"]
    s = deepcopy(base)
    table = MELEE_TIERS if s["melee"] else TIERS
    tier = max(0, min(MAX_TIER, int(tier)))
    for t in table[:tier]:
        for stat, mult in t["mods"].items():
            s[stat] = s[stat] * mult
    s["mods"] = {}
    s["flags"] = []
    s["reticle"] = "scope" if s.get("scoped") else None
    if mods and not s["melee"]:
        for slot, mid in clean_mods(s["id"], mods).items():
            m = MOD_BY_ID[mid]
            for stat, mult in m["mods"].items():
                s[stat] = s[stat] * mult
            s.update(m.get("set", {}))
            s["flags"] += m.get("flags", [])
            if m.get("reticle"):
                s["reticle"] = m["reticle"]
            s["mods"][slot] = mid
    if not s["melee"]:
        s["mag"] = max(1, int(round(s["mag"])))
    s["tier"] = tier
    return s


def damage_at(stats, dist):
    """Damage for one bullet/pellet at ``dist`` metres (linear falloff)."""
    if dist <= stats["range"]:
        return stats["dmg"]
    if dist >= stats["maxr"]:
        return stats["dmg"] * stats["falloff"]
    k = (dist - stats["range"]) / max(0.001, stats["maxr"] - stats["range"])
    return stats["dmg"] * (1.0 + (stats["falloff"] - 1.0) * k)


def tier_for_xp(xp):
    t = 0
    for need in TIER_XP:
        if xp >= need:
            t += 1
    return t


def dps(stats):
    """Rough body-shot DPS used by the loadout comparison bars."""
    if stats["melee"]:
        return stats["dmg"] * stats["rps"]
    cyc = stats["mag"] / stats["rps"]
    return stats["dmg"] * stats["pellets"] * stats["mag"] / (cyc + stats["reload"])


# --------------------------------------------------------------------------
# Weapon mods (attachments).  One mod per slot; each is a small trade-off.
#   mods     multipliers applied to stats (after upgrade tiers)
#   set      stats replaced outright (optic zoom / scoped flag)
#   flags    special behaviour: suppressed, laser
#   classes  weapon classes the mod fits
# Prices are in coins (see game/progression/shop.py).
# --------------------------------------------------------------------------
MOD_SLOTS = ["optic", "muzzle", "magazine", "underbarrel", "stock"]

_GUNS = ("pistol", "smg", "rifle", "shotgun", "sniper", "plasma", "rail")
_BALLISTIC = ("pistol", "smg", "rifle", "shotgun", "sniper")

MODS = [
    # ---- optics: change the aim-down-sights zoom and the ADS reticle
    {"id": "reddot", "slot": "optic", "name": "Red Dot Sight", "price": 300,
     "desc": "Clean red dot, slight zoom.", "reticle": "dot",
     "set": {"zoom": 0.8, "scoped": False}, "mods": {}, "classes": _GUNS},
    {"id": "holo", "slot": "optic", "name": "Holo Sight", "price": 400,
     "desc": "Holographic ring reticle, wider view.", "reticle": "holo",
     "set": {"zoom": 0.75, "scoped": False}, "mods": {}, "classes": _GUNS},
    {"id": "acog", "slot": "optic", "name": "2.5x Scope", "price": 650,
     "desc": "Mid-range magnified scope. Slower handling.", "reticle": "scope",
     "set": {"zoom": 0.5, "scoped": True}, "mods": {"swap": 1.1},
     "classes": ("rifle", "smg", "plasma", "rail", "sniper")},
    {"id": "sniperscope", "slot": "optic", "name": "8x Sniper Scope", "price": 900,
     "desc": "Extreme zoom for long lanes.", "reticle": "scope",
     "set": {"zoom": 0.22, "scoped": True}, "mods": {"swap": 1.15},
     "classes": ("sniper", "rail")},
    # ---- muzzle
    {"id": "suppressor", "slot": "muzzle", "name": "Suppressor", "price": 550,
     "desc": "Silent shots, tiny flash; enemies can't hear you. -12% range.",
     "flags": ["suppressed"], "mods": {"range": 0.88, "maxr": 0.92}, "classes": _BALLISTIC},
    {"id": "compensator", "slot": "muzzle", "name": "Compensator", "price": 400,
     "desc": "-25% recoil, louder and brighter.", "mods": {"recoil": 0.75},
     "classes": _GUNS},
    {"id": "choke", "slot": "muzzle", "name": "Tight Choke", "price": 450,
     "desc": "-25% pellet spread, -8% range falloff.", "mods": {"spread": 0.75, "falloff": 0.92},
     "classes": ("shotgun",)},
    {"id": "flashhider", "slot": "muzzle", "name": "Flash Hider", "price": 300,
     "desc": "-8% spread, smaller muzzle flash.", "flags": ["lowflash"],
     "mods": {"spread": 0.92}, "classes": _GUNS},
    # ---- magazine
    {"id": "extmag", "slot": "magazine", "name": "Extended Mag", "price": 500,
     "desc": "+35% magazine, +15% reload time.", "mods": {"mag": 1.35, "reload": 1.15},
     "classes": ("pistol", "smg", "rifle", "shotgun", "plasma", "rail", "sniper")},
    {"id": "fastmag", "slot": "magazine", "name": "Fast Mag", "price": 450,
     "desc": "-25% reload time, -15% magazine.", "mods": {"reload": 0.75, "mag": 0.85},
     "classes": _GUNS},
    # ---- underbarrel
    {"id": "vgrip", "slot": "underbarrel", "name": "Vertical Grip", "price": 350,
     "desc": "-15% recoil and spread bloom, -5% handling.",
     "mods": {"recoil": 0.85, "swap": 1.05}, "classes": ("smg", "rifle", "shotgun", "plasma", "rail")},
    {"id": "angled", "slot": "underbarrel", "name": "Angled Grip", "price": 350,
     "desc": "+15% handling (faster draw / ADS).", "mods": {"swap": 0.85},
     "classes": ("smg", "rifle", "shotgun", "plasma", "rail", "sniper")},
    {"id": "laser", "slot": "underbarrel", "name": "Laser Sight", "price": 500,
     "desc": "-25% hip-fire spread. Visible laser beam.", "flags": ["laser"],
     "mods": {"spread": 0.75}, "classes": _GUNS},
    # ---- stock
    {"id": "lightstock", "slot": "stock", "name": "Light Stock", "price": 300,
     "desc": "+6% move speed, +8% spread.", "mods": {"move": 1.06, "spread": 1.08},
     "classes": ("smg", "rifle", "shotgun", "sniper", "plasma", "rail")},
    {"id": "heavystock", "slot": "stock", "name": "Heavy Stock", "price": 350,
     "desc": "-15% recoil, -4% move speed.", "mods": {"recoil": 0.85, "move": 0.96},
     "classes": ("smg", "rifle", "shotgun", "sniper", "plasma", "rail")},
]
MOD_BY_ID = {m["id"]: m for m in MODS}


def mod_fits(mod_id, wid):
    m = MOD_BY_ID.get(mod_id)
    w = BY_ID.get(wid)
    return m is not None and w is not None and not w["melee"] and w["cls"] in m["classes"]


def mods_for(wid, slot):
    return [m for m in MODS if m["slot"] == slot and mod_fits(m["id"], wid)]


def clean_mods(wid, mods):
    """Validate a {slot: mod_id} dict from untrusted input (client or server)."""
    out = {}
    if not isinstance(mods, dict):
        return out
    for slot in MOD_SLOTS:
        mid = mods.get(slot)
        if mid and mod_fits(mid, wid) and MOD_BY_ID[mid]["slot"] == slot:
            out[slot] = mid
    return out
