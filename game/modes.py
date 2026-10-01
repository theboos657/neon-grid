"""Game mode rules.

Mode       | Teams | Win condition                       | Threats
-----------|-------|-------------------------------------|-------------------------------
FFA        | no    | first to score limit / best at time | turrets, drones, traps
Duel       | no    | first to score limit vs 1 bot       | traps only
Team       | 4v4   | team score limit / time             | turrets, traps
Co-op      | vs AI | survive waves with AI wingmen       | waves of bots + drones, traps
Endless    | solo  | survive as long as possible         | waves of bots + drones, traps
Showcase   | -     | attract-mode behind the main menu   | everything, no player

Modifiers: Lives (limited lives, last one standing) and Chaos (lasers, mines,
gravity zones) apply to any mode.
"""

import random

from neon_shared.weapons import tier_for_xp

from . import i18n
from .entities.bot import BOT_NAMES, random_loadout
from .progression.skins import BOT_SKIN_POOL

RESPAWN_DELAY = 3.0


def player_tiers(profile):
    """Effective tier per weapon: min(selected, unlocked)."""
    xp = profile["weapon_xp"]
    bonus = profile["weapon_bonus_tiers"]
    sel = profile["weapon_tier_sel"]
    out = {}
    for wid in set(list(xp.keys()) + list(bonus.keys()) + list(sel.keys())):
        unlocked = min(5, tier_for_xp(xp.get(wid, 0)) + bonus.get(wid, 0))
        out[wid] = min(unlocked, sel.get(wid, unlocked))
    return out


def player_loadout(app):
    """The local player's effective loadout (owned items, fitted mods, test hooks).
    Used for offline matches *and* for what we declare to a multiplayer server."""
    from .progression.shop import sanitize_loadout
    prof = app.storage.profile
    sanitize_loadout(prof.data)                 # only owned weapons/abilities can be used
    lo = dict(prof["loadout"])
    lo["mods"] = dict(prof["weapon_mods"])
    if app.args.get("weapon"):                  # test hook: --weapon <id>
        lo["primary"] = app.args["weapon"]
    if app.args.get("mods"):                    # test hook: --mods slot=id,slot=id
        lo["mods"][lo["primary"]] = dict(kv.split("=") for kv in app.args["mods"].split(","))
    return lo


class Mode:
    key = "ffa"
    team_based = False
    waves = False

    def __init__(self, match, cfg):
        self.m = match
        self.cfg = cfg
        self.time_limit = cfg.get("time_limit", 8) * 60.0 if cfg.get("time_limit") else 0.0
        self.score_limit = cfg.get("score_limit", 25)
        self.lives = cfg.get("lives_count", 3) if cfg.get("lives") else None
        self.chaos = bool(cfg.get("chaos"))
        self.difficulty = cfg.get("difficulty", "normal")
        self.elapsed = 0.0
        self.one_min_called = False
        self.names = list(BOT_NAMES)
        random.shuffle(self.names)

    # -------------------------------------------------------------- setup
    def hazard_config(self):
        return {"turrets": True, "drones": 2, "traps": True, "chaos": self.chaos,
                "drone_interval": 40.0}

    def add_player(self, team=0):
        app = self.m.app
        prof = app.storage.profile
        name = app.storage.settings["network"]["player_name"] or "Runner"
        lo = player_loadout(app)
        c = self.m.add_combatant(name, team, "player", lo,
                                 prof["equipped"]["char_skin"], player_tiers(prof.data))
        c.lives = self.lives
        self.m.spawn(c)
        return c

    def add_bot(self, team, difficulty=None, show_name=False):
        diff = difficulty or self.difficulty
        name = self.names.pop() if self.names else "BOT"
        c = self.m.add_combatant(name, team, "bot", random_loadout(self.m.rng, diff),
                                 random.choice(BOT_SKIN_POOL), None, diff, show_name)
        c.lives = self.lives
        self.m.spawn(c)
        return c

    def setup(self):
        self.add_player()
        for _ in range(max(1, min(7, self.cfg.get("bots", 5)))):
            self.add_bot(1)

    # -------------------------------------------------------------- rules
    def on_kill(self, victim, killer):
        if killer is not None and killer is not victim:
            killer.score += 1
        victim.respawn_timer = RESPAWN_DELAY
        if self.lives is not None:
            victim.lives = (victim.lives or 0) - 1

    def on_hazard_destroyed(self, h, source):
        pass

    def can_respawn(self, c):
        if self.lives is None:
            return True
        return (c.lives or 0) > 0

    def time_left(self):
        if not self.time_limit:
            return None
        return max(0.0, self.time_limit - self.elapsed)

    def update(self, dt):
        m = self.m
        if m.state != "live":
            return
        self.elapsed += dt
        tl = self.time_left()
        if tl is not None:
            if tl < 60 and not self.one_min_called and self.time_limit > 90:
                self.one_min_called = True
                m._announce("one_minute")
            if tl <= 0:
                self.finish()
                return
        self.check_end()

    def check_end(self):
        m = self.m
        best = max(m.combatants, key=lambda c: c.score)
        if self.score_limit and best.score >= self.score_limit:
            self.finish()
            return
        if self.lives is not None:
            standing = [c for c in m.combatants if not c.eliminated]
            if len(standing) <= 1 or (m.player and m.player.eliminated):
                self.finish()

    def ranking(self):
        return sorted(self.m.combatants, key=lambda c: (-c.score, c.deaths))

    def finish(self):
        m = self.m
        rank = self.ranking()
        if self.lives is not None:
            rank = sorted(m.combatants, key=lambda c: (c.eliminated, -c.score, c.deaths))
        place = rank.index(m.player) + 1 if m.player in rank else 0
        won = place == 1
        m.end({"won": won, "place": place, "mode": self.key, "subtitle": i18n.t("place", n=place),
               "score": m.player.score if m.player else 0})

    # -------------------------------------------------------------- HUD
    def hud_info(self):
        """(center big text, center small text)"""
        m = self.m
        tl = self.time_left()
        timer = ""
        if tl is not None:
            timer = "%d:%02d" % (int(tl) // 60, int(tl) % 60)
        p = m.player
        if p is None:
            return timer, ""
        rank = self.ranking()
        lead = rank[0]
        place = rank.index(p) + 1
        small = "%s   #%d   %d / %d" % (i18n.t("first_to", n=self.score_limit), place, p.score,
                                       lead.score if lead is not p else
                                       (rank[1].score if len(rank) > 1 else 0))
        if self.lives is not None:
            small += "   " + i18n.t("lives_left", n=max(0, p.lives or 0))
        return timer, small

    def scoreboard(self):
        return [(c.name, c.kills, c.deaths, c.score, c.ping, c is self.m.player, c.team,
                 c.eliminated) for c in self.ranking()]


class FFA(Mode):
    key = "ffa"


class Duel(Mode):
    key = "duel"

    def __init__(self, match, cfg):
        super().__init__(match, cfg)
        if not cfg.get("score_limit"):
            self.score_limit = 10

    def hazard_config(self):
        return {"turrets": False, "drones": 0, "traps": True, "chaos": self.chaos}

    def setup(self):
        self.add_player()
        self.add_bot(1, self.difficulty)

    def finish(self):
        m = self.m
        bot = [c for c in m.combatants if c is not m.player][0]
        p = m.player
        if self.lives is not None:
            won = not p.eliminated and (bot.eliminated or p.score > bot.score)
        else:
            won = p.score > bot.score
        draw = p.score == bot.score and self.lives is None
        m.end({"won": None if draw else won, "place": 1 if won else 2, "mode": "duel",
               "difficulty": self.difficulty, "subtitle": "%d - %d" % (p.score, bot.score),
               "score": p.score})


class Team(Mode):
    key = "team"
    team_based = True

    def __init__(self, match, cfg):
        super().__init__(match, cfg)
        self.team_score = [0, 0]
        if not cfg.get("score_limit"):
            self.score_limit = 30

    def hazard_config(self):
        return {"turrets": True, "drones": 0, "traps": True, "chaos": self.chaos}

    def setup(self):
        size = max(1, min(5, int(self.cfg.get("team_size", 4))))
        self.add_player(0)
        for _ in range(size - 1):
            self.add_bot(0, {"easy": "easy", "nightmare": "hard"}.get(self.difficulty, "normal"))
        for _ in range(size):
            self.add_bot(1)

    def on_kill(self, victim, killer):
        super().on_kill(victim, killer)
        if killer is not None and killer.team != victim.team:
            self.team_score[killer.team] += 1

    def check_end(self):
        m = self.m
        if self.score_limit and max(self.team_score) >= self.score_limit:
            self.finish()
            return
        if self.lives is not None:
            alive_teams = {c.team for c in m.combatants if not c.eliminated}
            if len(alive_teams) <= 1:
                self.finish()

    def finish(self):
        m = self.m
        a, b = self.team_score
        if self.lives is not None:
            alive_teams = {c.team for c in m.combatants if not c.eliminated}
            if len(alive_teams) == 1:
                a, b = (1, 0) if 0 in alive_teams else (0, 1)
        won = None if a == b else a > b
        m.end({"won": won, "place": 1 if won else 2, "mode": "team",
               "subtitle": "%d - %d" % tuple(self.team_score), "score": m.player.score})

    def hud_info(self):
        timer, _ = super().hud_info()
        small = "%s %d   :   %d %s" % (i18n.t("team_blue"), self.team_score[0],
                                        self.team_score[1], i18n.t("team_red"))
        if self.lives is not None:
            small += "   " + i18n.t("lives_left", n=max(0, self.m.player.lives or 0))
        return timer, small


class Waves(Mode):
    """Endless survival (solo) and Co-op survival (with AI wingmen)."""
    key = "endless"
    waves = True
    team_based = True

    def __init__(self, match, cfg, coop=False):
        super().__init__(match, cfg)
        self.coop = coop
        self.key = "coop" if coop else "endless"
        self.wave = 0
        self.queue = 0
        self.break_t = 4.0
        self.in_break = True
        self.time_limit = 0.0
        self.score_limit = 0
        if self.lives is None:
            self.lives = 3 if not coop else None
        self.kills_total = 0

    def hazard_config(self):
        return {"turrets": False, "drones": 0, "traps": True, "chaos": self.chaos}

    def setup(self):
        self.add_player(0)
        if self.coop:
            for _ in range(2):
                self.add_bot(0, "normal", show_name=True)

    def _enemy_difficulty(self):
        from .entities.bot import DIFF_ORDER
        ramp = 0 if self.wave < 3 else (1 if self.wave < 7 else 2)
        base = DIFF_ORDER.index(self.difficulty) - 1 if self.difficulty in DIFF_ORDER else 0
        return DIFF_ORDER[max(0, min(3, ramp + base))]

    def _start_wave(self):
        m = self.m
        self.wave += 1
        m.stats["wave"] = self.wave
        self.in_break = False
        self.queue = min(3 + self.wave * (2 if self.coop else 1), 18)
        drones = min(self.wave // 2, 5)
        for _ in range(drones):
            m.hazards.spawn_drone(1.0 + self.wave * 0.08)
        if m.hud:
            m.hud.big_message(i18n.t("wave_incoming", n=self.wave), "", 2.2)
        m._announce("wave_incoming")
        m.audio.bump(0.4)

    def _spawn_enemy(self):
        m = self.m
        # recycle dead enemy bots instead of growing the list forever
        diff = self._enemy_difficulty()
        for c in m.combatants:
            if c.team == 1 and not c.alive and c.respawn_timer <= -900:
                c.controller.set_difficulty(diff)
                c.eliminated = False
                m.spawn(c)
                return
        self.add_bot(1, diff)

    def on_kill(self, victim, killer):
        if killer is not None and killer is not victim:
            killer.score += 1
        if victim.team == 1:
            victim.respawn_timer = -999      # enemies never respawn on their own
            victim.eliminated = False
            self.kills_total += 1
            return
        victim.respawn_timer = RESPAWN_DELAY * 2
        if self.lives is not None and victim.is_player:
            victim.lives = (victim.lives or 0) - 1

    def on_hazard_destroyed(self, h, source):
        pass

    def can_respawn(self, c):
        if c.team == 1:
            return False
        if c.is_player and self.lives is not None:
            return (c.lives or 0) > 0
        if self.coop:
            # respawn only while at least one teammate still fights
            return any(o.alive for o in self.m.combatants if o.team == 0)
        return True

    def update(self, dt):
        m = self.m
        if m.state != "live":
            return
        self.elapsed += dt
        enemies_alive = [c for c in m.combatants if c.team == 1 and c.alive]
        drones = len(m.hazards.drones) if m.hazards else 0
        if self.in_break:
            self.break_t -= dt
            if self.break_t <= 0:
                self._start_wave()
        else:
            max_active = 6 if self.coop else 5
            if self.queue > 0 and len(enemies_alive) < max_active:
                self.queue -= 1
                self._spawn_enemy()
            if self.queue == 0 and not enemies_alive and drones == 0:
                self.in_break = True
                self.break_t = 8.0
                m.stats["xp"] += 150
                if m.hud:
                    m.hud.big_message(i18n.t("wave_cleared", n=self.wave), "", 2.5)
                m._announce("wave_cleared")
                # regroup: revive teammates, top up everyone
                for c in m.combatants:
                    if c.team == 0:
                        if not c.alive and (not c.is_player or self.can_respawn(c)):
                            c.eliminated = False
                            m.spawn(c)
                        elif c.alive:
                            c.health = c.max_health
                            c.refill_ammo(1.0)
        # defeat
        team_alive = [c for c in m.combatants if c.team == 0 and (c.alive or not c.eliminated)]
        p = m.player
        if p is not None and (p.eliminated or not team_alive):
            self.finish()

    def finish(self):
        m = self.m
        m.end({"won": None, "place": 0, "mode": self.key, "wave": self.wave,
               "subtitle": i18n.t("wave", n=self.wave), "score": self.kills_total,
               "kills": m.player.kills if m.player else 0})

    def hud_info(self):
        m = self.m
        big = i18n.t("wave", n=self.wave) if self.wave else ""
        if self.in_break and self.wave >= 0 and m.state == "live":
            small = i18n.t("next_wave", n=int(self.break_t) + 1)
        else:
            left = self.queue + len([c for c in m.combatants if c.team == 1 and c.alive])
            small = i18n.t("enemies_left", n=left)
        if self.lives is not None and m.player is not None:
            small += "   " + i18n.t("lives_left", n=max(0, m.player.lives or 0))
        return big, small


class Showcase(Mode):
    """Bots fighting behind the menus (no player, no end)."""
    key = "showcase"

    def hazard_config(self):
        return {"turrets": True, "drones": 1, "traps": True, "chaos": False,
                "drone_interval": 25.0}

    def setup(self):
        for _ in range(5):
            self.add_bot(1, random.choice(["normal", "hard"]))
        self.m.state = "live"
        self.m.frozen = False

    def check_end(self):
        pass

    def update(self, dt):
        self.elapsed += dt


class NetFFA(Mode):
    """Online / LAN matches (free-for-all, 1v1, teams, co-op vs bots).  The server owns
    score, health and the clock; this mode builds the roster, runs the AI of the bots
    this game hosts, and presents server state."""
    key = "ffa"

    def __init__(self, match, cfg):
        super().__init__(match, cfg)
        self.session = cfg["session"]
        self.start = cfg["start"]
        self.net_mode = cfg.get("net_mode", "ffa")
        self.team_based = self.net_mode in ("team", "coop")
        self.score_limit = self.session.score_limit
        self.time_limit = 0.0
        self.loadouts = {pl["id"]: pl.get("w") or [] for pl in self.start.get("players", [])}

    def hazard_config(self):
        return {"turrets": False, "drones": 0, "traps": False, "chaos": False}

    def _spawn_from_msg(self, c, sid):
        sp = self.start.get("spawns", {}).get(str(sid))
        if sp:
            self.m.spawn_at(c, (sp[0], sp[1], sp[2]), sp[3])
        else:
            self.m.spawn(c)

    def _team(self, team, me=False):
        """Server team (-1 in free-for-all) -> local team (everyone else is hostile)."""
        if self.team_based and team in (0, 1):
            return team
        return 0 if me else 1

    def setup(self):
        s = self.session
        for pl in self.start.get("players", []):
            sid = pl["id"]
            if sid == s.my_id:
                c = self.add_player(self._team(pl.get("team", -1), True))
                c.net_id = sid
                c.net_local = True
                self.m.net_ids[sid] = c
                self._spawn_from_msg(c, sid)
            elif pl.get("bot") and pl.get("owner") == s.my_id:
                self.add_local_bot(sid, pl)
            else:
                self.add_remote(sid, pl.get("name", "?"), pl.get("skin", "default"),
                                pl.get("team", -1))

    def _loadout(self, sid):
        from neon_shared.weapons import BY_ID
        ws = [w for w in self.loadouts.get(sid, []) if w in BY_ID]
        ranged = [w for w in ws if not BY_ID[w]["melee"]] + ["vx9", "vx9"]
        melee = [w for w in ws if BY_ID[w]["melee"]] + ["katana"]
        return {"primary": ranged[0], "secondary": ranged[1], "melee": melee[0],
                "abilities": ["dash", "shield"]}

    def add_local_bot(self, sid, pl):
        """A bot the server asked this game (the host) to simulate."""
        diff = self.cfg.get("difficulty", "normal")
        c = self.m.add_combatant(pl.get("name", "BOT"), self._team(pl.get("team", -1)), "bot",
                                 self._loadout(sid), pl.get("skin", "default"), None, diff,
                                 show_name=True)
        c.net_id = sid
        c.net_local = True
        c.respawn_timer = 1e9
        self.m.net_ids[sid] = c
        self.session.local_bots.append(c)
        self._spawn_from_msg(c, sid)
        return c

    def add_remote(self, sid, name, skin, team=-1):
        c = self.m.add_combatant(name, self._team(team), "remote", self._loadout(sid), skin, None,
                                 show_name=True)
        c.net_id = sid
        c.respawn_timer = 1e9
        self.m.net_ids[sid] = c
        self._spawn_from_msg(c, sid)
        return c

    def hud_info(self):
        timer, small = super().hud_info()
        if self.team_based:
            ts = self.session.team_score
            small = "%s %d   :   %d %s" % (i18n.t("team_blue"), ts[0], ts[1], i18n.t("team_red"))
        return timer, small

    def on_kill(self, victim, killer):
        victim.respawn_timer = 1e9

    def can_respawn(self, c):
        return False

    def time_left(self):
        return self.session.time_left

    def update(self, dt):
        self.elapsed += dt

    def finish(self):
        pass


def create(match, cfg, showcase=False):
    if showcase:
        return Showcase(match, cfg)
    mode = cfg.get("mode", "ffa")
    if mode == "online":
        return NetFFA(match, cfg)
    if mode == "duel":
        return Duel(match, cfg)
    if mode == "team":
        return Team(match, cfg)
    if mode == "coop":
        return Waves(match, cfg, coop=True)
    if mode == "endless":
        return Waves(match, cfg, coop=False)
    return FFA(match, cfg)
