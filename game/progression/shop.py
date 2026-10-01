"""Coin shop: weapons, melee weapons, abilities and weapon upgrade tiers.

Coins are earned in matches from kills (a coin reward per elimination plus
the coin orbs enemies drop), destroyed drones/turrets, daily challenges,
achievements and the battle pass.  Nothing is ever bought with real money.

A starter kit (AR-7, VX-9, Neon Katana, Phase Dash, Aegis Shield) is free.
Prices scale with how specialised / strong an item is.
"""

from neon_shared.weapons import MAX_TIER, tier_for_xp

STARTER_WEAPONS = ["ar7", "vx9", "katana"]
STARTER_ABILITIES = ["dash", "shield"]

KILL_COINS = 12          # per elimination
HEADSHOT_BONUS = 5
HAZARD_COINS = 15        # destroying a drone or turret

WEAPON_PRICES = {
    # pistols
    "vx9": 0, "hammer50": 450, "flicker": 500,
    # SMGs
    "hornet": 600, "wasp": 650, "buzz": 750,
    # rifles
    "ar7": 0, "longbow": 900, "triburst": 800, "lmg": 1000,
    # shotguns
    "breaker": 750, "riot": 900, "scatter": 950,
    # snipers
    "needle": 1400, "viper": 1200, "executioner": 2500,
    # plasma
    "caster": 1000, "nova": 1600, "photon": 1100,
    # rail
    "lance": 1800, "arcrail": 1500,
    # melee
    "katana": 0, "baton": 350, "axe": 600, "knife": 300, "whip": 500,
    "gravhammer": 800, "claws": 450, "spear": 550, "fist": 400, "chainblade": 650,
}

ABILITY_PRICES = {"shield": 0, "dash": 0, "scan": 700, "decoy": 600, "heal": 800,
                  "speed": 500, "jets": 550, "emp": 1100, "cloak": 1000, "gravity": 1200}

# price of upgrade tier 1..5 (bought one at a time, on owned weapons)
TIER_PRICES = [250, 450, 700, 1000, 1400]


def weapon_price(wid):
    return WEAPON_PRICES.get(wid, 800)


def ability_price(aid):
    return ABILITY_PRICES.get(aid, 800)


def owns_weapon(profile, wid):
    return wid in profile["owned_weapons"] or weapon_price(wid) == 0


def owns_ability(profile, aid):
    return aid in profile["owned_abilities"] or ability_price(aid) == 0


def _spend(profile, cost):
    if profile["coins"] < cost:
        return False
    profile["coins"] -= cost
    return True


def buy_weapon(profile, wid):
    if owns_weapon(profile, wid):
        return True
    if not _spend(profile, weapon_price(wid)):
        return False
    profile["owned_weapons"].append(wid)
    return True


def buy_ability(profile, aid):
    if owns_ability(profile, aid):
        return True
    if not _spend(profile, ability_price(aid)):
        return False
    profile["owned_abilities"].append(aid)
    return True


def unlocked_tier(profile, wid):
    """Tiers come from weapon XP, upgrade chips and coin purchases."""
    xp = profile["weapon_xp"].get(wid, 0)
    return min(MAX_TIER, tier_for_xp(xp) + profile["weapon_bonus_tiers"].get(wid, 0))


def next_tier_price(profile, wid):
    t = unlocked_tier(profile, wid)
    if t >= MAX_TIER:
        return None
    return TIER_PRICES[t]


def buy_tier(profile, wid):
    if not owns_weapon(profile, wid):
        return False
    price = next_tier_price(profile, wid)
    if price is None or not _spend(profile, price):
        return False
    t = unlocked_tier(profile, wid)
    profile["weapon_bonus_tiers"][wid] = profile["weapon_bonus_tiers"].get(wid, 0) + 1
    profile["weapon_tier_sel"][wid] = t + 1
    return True


def mod_price(mod_id):
    from neon_shared.weapons import MOD_BY_ID
    return MOD_BY_ID[mod_id]["price"]


def owns_mod(profile, mod_id):
    return mod_id in profile["owned_mods"]


def buy_mod(profile, mod_id):
    """Mods are bought once and can then be fitted to any compatible weapon."""
    if owns_mod(profile, mod_id):
        return True
    if not _spend(profile, mod_price(mod_id)):
        return False
    profile["owned_mods"].append(mod_id)
    return True


def fit_mod(profile, wid, slot, mod_id):
    """Fit (or with mod_id=None remove) an owned mod on an owned weapon."""
    from neon_shared.weapons import MOD_BY_ID, mod_fits
    wm = profile["weapon_mods"].setdefault(wid, {})
    if mod_id is None:
        wm.pop(slot, None)
        return True
    if not owns_mod(profile, mod_id) or not mod_fits(mod_id, wid) or \
            MOD_BY_ID[mod_id]["slot"] != slot:
        return False
    wm[slot] = mod_id
    return True


def sanitize_loadout(profile):
    """Make sure the saved loadout only contains owned items."""
    lo = profile["loadout"]
    for slot, fallback in (("primary", "ar7"), ("secondary", "vx9"), ("melee", "katana")):
        if not owns_weapon(profile, lo.get(slot, fallback)):
            lo[slot] = fallback
    abil = [a for a in lo.get("abilities", []) if owns_ability(profile, a)]
    for a in STARTER_ABILITIES:
        if len(abil) >= 2:
            break
        if a not in abil:
            abil.append(a)
    lo["abilities"] = abil[:2]
    # drop mods that are no longer owned / valid
    from neon_shared.weapons import clean_mods
    for wid, wm in list(profile["weapon_mods"].items()):
        good = {s: m for s, m in clean_mods(wid, wm).items() if owns_mod(profile, m)}
        profile["weapon_mods"][wid] = good


# ---------------------------------------------------------------- boosts
# Consumables: each purchase adds ``matches`` uses; one use is spent per
# finished offline match while the boost is active.
BOOSTS = [
    {"id": "xp2", "price": 400, "matches": 3},        # double match XP
    {"id": "coins15", "price": 500, "matches": 3},    # +50% match coins
    {"id": "shield", "price": 300, "matches": 3},     # 40 shield on every spawn
    {"id": "ammo", "price": 250, "matches": 3},       # +50% spare ammo
]
BOOST_BY_ID = {b["id"]: b for b in BOOSTS}


def buy_boost(profile, bid):
    b = BOOST_BY_ID[bid]
    if not _spend(profile, b["price"]):
        return False
    profile["boosts"][bid] = profile["boosts"].get(bid, 0) + b["matches"]
    return True


def boost_active(profile, bid):
    return profile["boosts"].get(bid, 0) > 0


def consume_boosts(profile):
    """Spend one use of every active boost; returns the ids that were active."""
    used = []
    for bid, left in list(profile["boosts"].items()):
        if left > 0:
            profile["boosts"][bid] = left - 1
            used.append(bid)
    return used


def buy_skin(profile, owned_key, sid, price):
    if sid in profile[owned_key]:
        return True
    if not _spend(profile, price):
        return False
    profile[owned_key].append(sid)
    return True
