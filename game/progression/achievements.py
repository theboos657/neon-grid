"""Achievements (permanent) and daily challenges (3 per day, seeded by date)."""

import datetime
import random

# id -> predicate(stats, highscores, profile_level, pass_tier)
ACHIEVEMENTS = [
    ("first_blood", lambda s, h, lv, pt: s["kills"] >= 1),
    ("centurion", lambda s, h, lv, pt: s["kills"] >= 100),
    ("sharpshooter", lambda s, h, lv, pt: s["headshots"] >= 50),
    ("arsenal", lambda s, h, lv, pt: len([k for k, v in s["weapon_kills"].items() if v > 0]) >= 10),
    ("blade_runner", lambda s, h, lv, pt: s["melee_kills"] >= 25),
    ("survivor", lambda s, h, lv, pt: h["endless_wave"] >= 10),
    ("untouchable", lambda s, h, lv, pt: s["flawless_ffa"] >= 1),
    ("hazard_hunter", lambda s, h, lv, pt: s["turrets_destroyed"] + s["drones_destroyed"] >= 20),
    ("chaos_theory", lambda s, h, lv, pt: s["chaos_wins"] >= 1),
    ("duelist", lambda s, h, lv, pt: s["duel_hard_wins"] >= 1),
    ("team_player", lambda s, h, lv, pt: s["team_wins"] >= 5),
    ("slider", lambda s, h, lv, pt: s["slides"] >= 200),
    ("power_user", lambda s, h, lv, pt: s["abilities_used"] >= 100),
    ("rich", lambda s, h, lv, pt: s["coins_earned"] >= 5000),
    ("level10", lambda s, h, lv, pt: lv >= 10),
    ("pass_complete", lambda s, h, lv, pt: pt >= 50),
    ("streak5", lambda s, h, lv, pt: s["best_streak"] >= 5),
    ("streak10", lambda s, h, lv, pt: s["best_streak"] >= 10),
    ("online", lambda s, h, lv, pt: s["mp_matches"] >= 1),
    ("recharged", lambda s, h, lv, pt: s["port_charges"] >= 30),
]
ACH_IDS = [a[0] for a in ACHIEVEMENTS]
ACH_REWARD_XP = 400
ACH_REWARD_COINS = 100

# challenge templates: (id, match-stat key, amounts)
CHALLENGES = [
    ("kills", "kills", (15, 25, 40)),
    ("headshots", "headshots", (5, 10, 15)),
    ("melee", "melee_kills", (3, 6, 10)),
    ("drones", "hazards", (3, 6, 10)),
    ("matches", "matches", (2, 3, 5)),
    ("abilities", "abilities", (10, 20, 35)),
    ("loot", "loot", (5, 10, 15)),
    ("slides", "slides", (15, 30, 50)),
    ("wins", "wins", (1, 2, 3)),
    ("damage", "damage", (1500, 3000, 5000)),
]
CH_REWARD = [(400, 40), (700, 70), (1000, 100)]


def check_achievements(profile, stats, highscores, level, pass_tier):
    """Unlock new achievements; returns list of newly unlocked ids."""
    new = []
    have = profile["achievements"]
    for aid, pred in ACHIEVEMENTS:
        if aid in have:
            continue
        try:
            ok = pred(stats, highscores, level, pass_tier)
        except (KeyError, TypeError):
            ok = False
        if ok:
            have[aid] = datetime.date.today().isoformat()
            new.append(aid)
    return new


def today():
    return datetime.date.today().isoformat()


def ensure_daily(profile):
    ch = profile["challenges"]
    if ch.get("date") == today() and ch.get("list"):
        return ch["list"]
    rnd = random.Random(today())
    picks = rnd.sample(CHALLENGES, 3)
    lst = []
    for i, (cid, key, amounts) in enumerate(picks):
        diff = rnd.randint(0, 2)
        lst.append({"id": cid, "key": key, "target": amounts[diff], "progress": 0,
                    "done": False, "xp": CH_REWARD[diff][0], "coins": CH_REWARD[diff][1]})
    ch["date"] = today()
    ch["list"] = lst
    return lst


def progress_challenges(profile, match_stats):
    """Advance today's challenges with a match's stats; returns completed ones."""
    done = []
    for c in ensure_daily(profile):
        if c["done"]:
            continue
        c["progress"] = min(c["target"], c["progress"] + int(match_stats.get(c["key"], 0)))
        if c["progress"] >= c["target"]:
            c["done"] = True
            done.append(c)
    return done
