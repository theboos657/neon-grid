"""Season 1 battle pass: 50 tiers driven by XP.

Free track rewards everyone; the premium track is unlocked with in-game coins
(never real money).  Rewards are weapon skins, suits, titles, coins and
Upgrade Chips (each chip instantly unlocks the next upgrade tier of a weapon
of your choice in the Loadout screen).
"""

TIERS = 50
XP_PER_TIER = 1200
PREMIUM_COST = 2500

_PASS_WSKINS = ["sunset", "volt", "gridline", "chrome", "crimson", "aurora", "gold"]
_PASS_CSKINS = ["synth", "hazmat", "ghost", "cobalt", "emerald", "legend"]
_TITLES = ["Glitch", "Runner", "Voltage", "Overclocked", "Neon Saint", "Gridmaster"]


def _build():
    free = {}
    prem = {}
    wi = ci = ti = 0
    for t in range(1, TIERS + 1):
        # free track
        if t % 10 == 0:
            free[t] = ("cskin", _PASS_CSKINS[ci % len(_PASS_CSKINS)])
            ci += 1
        elif t % 5 == 0:
            free[t] = ("wskin", _PASS_WSKINS[wi % len(_PASS_WSKINS)])
            wi += 1
        elif t % 3 == 0:
            free[t] = ("chip", 1)
        elif t % 2 == 0:
            free[t] = ("coins", 100 + t * 5)
        # premium track: something every tier
        if t % 8 == 0:
            prem[t] = ("title", _TITLES[ti % len(_TITLES)])
            ti += 1
        elif t % 4 == 0:
            prem[t] = ("chip", 2)
        elif t in (7, 22, 37):
            prem[t] = ("wskin", _PASS_WSKINS[(wi + t) % len(_PASS_WSKINS)])
        elif t in (15, 45):
            prem[t] = ("cskin", _PASS_CSKINS[(ci + t) % len(_PASS_CSKINS)])
        else:
            prem[t] = ("coins", 60 + t * 4)
    prem[TIERS] = ("cskin", "legend")
    return free, prem


FREE, PREMIUM = _build()


def tier_for_xp(xp_total):
    return min(TIERS, xp_total // XP_PER_TIER)


def tier_progress(xp_total):
    t = tier_for_xp(xp_total)
    if t >= TIERS:
        return t, XP_PER_TIER, XP_PER_TIER
    return t, xp_total - t * XP_PER_TIER, XP_PER_TIER


def account_level(xp_total):
    """Account level: gently increasing XP per level."""
    lvl = 1
    need = 800
    xp = xp_total
    while xp >= need and lvl < 999:
        xp -= need
        lvl += 1
        need = int(need * 1.06)
    return lvl, xp, need


def grant(profile, reward):
    """Apply a reward tuple to the profile dict."""
    kind, val = reward
    if kind == "coins":
        profile["coins"] += val
    elif kind == "chip":
        profile["upgrade_chips"] += val
    elif kind == "wskin":
        if val not in profile["owned_weapon_skins"]:
            profile["owned_weapon_skins"].append(val)
    elif kind == "cskin":
        if val not in profile["owned_char_skins"]:
            profile["owned_char_skins"].append(val)
    elif kind == "title":
        if val not in profile["owned_titles"]:
            profile["owned_titles"].append(val)


def claimable(profile):
    """List of (track, tier) rewards unlocked but not yet claimed."""
    t = tier_for_xp(profile["xp_total"])
    p = profile["pass"]
    out = []
    for tier in range(1, t + 1):
        if tier in FREE and tier not in p["claimed_free"]:
            out.append(("free", tier))
        if p["premium"] and tier in PREMIUM and tier not in p["claimed_premium"]:
            out.append(("premium", tier))
    return out


def claim(profile, track, tier):
    p = profile["pass"]
    if tier > tier_for_xp(profile["xp_total"]):
        return False
    if track == "free":
        if tier not in FREE or tier in p["claimed_free"]:
            return False
        grant(profile, FREE[tier])
        p["claimed_free"].append(tier)
        return True
    if not p["premium"] or tier not in PREMIUM or tier in p["claimed_premium"]:
        return False
    grant(profile, PREMIUM[tier])
    p["claimed_premium"].append(tier)
    return True


def claim_all(profile):
    n = 0
    for track, tier in claimable(profile):
        if claim(profile, track, tier):
            n += 1
    return n


def unlock_premium(profile):
    if profile["pass"]["premium"] or profile["coins"] < PREMIUM_COST:
        return False
    profile["coins"] -= PREMIUM_COST
    profile["pass"]["premium"] = True
    return True
