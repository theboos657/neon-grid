"""Turns a finished match into XP, coins, stats, high scores, challenge and
achievement progress.  Everything is saved to AppData immediately."""

from neon_shared.weapons import BY_ID, tier_for_xp

from . import achievements as ACH
from . import battlepass as BP


def apply_match(app, m):
    st = app.storage
    prof = st.profile.data
    stats = st.stats.data
    hs = st.highscores.data
    ms = m.stats
    res = m.result or {}
    won = res.get("won")
    mode = res.get("mode", m.mode.key)

    # ---- XP / coins
    xp = int(ms["xp"]) + 250 + min(600, int(ms["time"]))
    coins = int(ms["coins"])          # earned from kills during the match
    if won:
        xp += 500
    if mode in ("endless", "coop"):
        xp += res.get("wave", 0) * 40
    level_before = BP.account_level(prof["xp_total"])[0]
    tier_before = BP.tier_for_xp(prof["xp_total"])

    # ---- weapon XP and upgrade tier unlocks
    tier_unlocks = []
    for wid, wxp in ms["weapon_xp"].items():
        before = prof["weapon_xp"].get(wid, 0)
        after = before + wxp
        prof["weapon_xp"][wid] = after
        if tier_for_xp(after) > tier_for_xp(before):
            tier_unlocks.append((BY_ID[wid]["name"], tier_for_xp(after)))

    # ---- aggregate stats
    stats["kills"] += ms["kills"]
    stats["deaths"] += ms["deaths"]
    stats["headshots"] += ms["headshots"]
    stats["melee_kills"] += ms["melee_kills"]
    stats["matches"] += 1
    stats["time_played"] += ms["time"]
    stats["shots_fired"] += ms["shots"]
    stats["shots_hit"] += ms["hits"]
    stats["damage"] += int(ms["damage"])
    stats["abilities_used"] += ms["abilities"]
    stats["slides"] += ms["slides"]
    stats["loot_boxes"] += ms["loot"]
    stats["turrets_destroyed"] += ms["turrets"]
    stats["drones_destroyed"] += ms["drones"]
    stats["port_charges"] += ms["ports"]
    stats["best_streak"] = max(stats["best_streak"], ms["best_streak"])
    for wid, k in ms["weapon_kills"].items():
        stats["weapon_kills"][wid] = stats["weapon_kills"].get(wid, 0) + k
    if won:
        stats["wins"] += 1
        if mode == "team":
            stats["team_wins"] += 1
        if m.mode.chaos:
            stats["chaos_wins"] += 1
        if mode == "duel" and res.get("difficulty") in ("hard", "nightmare"):
            stats["duel_hard_wins"] += 1
        if mode == "ffa" and ms["deaths"] == 0 and ms["kills"] > 0:
            stats["flawless_ffa"] += 1
    if m.config.get("online"):
        stats["mp_matches"] += 1

    # ---- high scores
    new_best = False
    if mode == "endless":
        if res.get("wave", 0) > hs["endless_wave"]:
            hs["endless_wave"] = res.get("wave", 0)
            new_best = True
        hs["endless_kills"] = max(hs["endless_kills"], ms["kills"])
    elif mode == "coop":
        if res.get("wave", 0) > hs["coop_wave"]:
            hs["coop_wave"] = res.get("wave", 0)
            new_best = True
    elif mode == "ffa":
        if ms["kills"] > hs["ffa_kills"]:
            hs["ffa_kills"] = ms["kills"]
            new_best = True
    elif mode == "duel" and won:
        d = res.get("difficulty", "normal")
        hs["duel_wins"][d] = hs["duel_wins"].get(d, 0) + 1
    hs["best_streak"] = max(hs["best_streak"], ms["best_streak"])

    # ---- daily challenges
    ch_stats = dict(ms)
    ch_stats["matches"] = 1
    ch_stats["wins"] = 1 if won else 0
    done = ACH.progress_challenges(prof, ch_stats)
    for c in done:
        xp += c["xp"]
        coins += c["coins"]

    # difficulty coin multiplier (offline matches against bots)
    diff_mult = 1.0
    if not m.config.get("online"):
        from ..entities.bot import COIN_MULT
        diff_mult = COIN_MULT.get(m.config.get("difficulty", "normal"), 1.0)
        coins = int(round(coins * diff_mult))
    boosts_used = []
    if not m.config.get("online"):
        from . import shop as SH
        if SH.boost_active(prof, "xp2"):
            xp *= 2
        if SH.boost_active(prof, "coins15"):
            coins = int(coins * 1.5)
        boosts_used = SH.consume_boosts(prof)
    prof["xp_total"] += xp
    prof["coins"] += coins
    stats["coins_earned"] += coins

    level_after = BP.account_level(prof["xp_total"])[0]
    tier_after = BP.tier_for_xp(prof["xp_total"])
    new_ach = ACH.check_achievements(prof, stats, hs, level_after, tier_after)
    for _ in new_ach:
        prof["xp_total"] += ACH.ACH_REWARD_XP
        prof["coins"] += ACH.ACH_REWARD_COINS
    if not app.is_test_run():
        st.save_all()
    if level_after > level_before:
        app.audio.play2d("level_up")
    elif new_ach:
        app.audio.play2d("achievement")
    return {"won": won, "mode": mode, "subtitle": res.get("subtitle", ""), "xp": xp,
            "coins": coins, "level_before": level_before, "level_after": level_after,
            "tier_before": tier_before, "tier_after": BP.tier_for_xp(prof["xp_total"]),
            "achievements": new_ach, "challenges": done, "tier_unlocks": tier_unlocks,
            "new_best": new_best, "boosts": boosts_used, "diff_mult": diff_mult,
            "difficulty": m.config.get("difficulty", "normal"), "kills": ms["kills"], "deaths": ms["deaths"],
            "wave": res.get("wave", 0), "place": res.get("place", 0)}
