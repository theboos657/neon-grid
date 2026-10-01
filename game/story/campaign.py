"""LAST LIGHT - the built-in story campaign.

Kade's wife Lena and daughter Mia were murdered by the Null Syndicate.  Three
years later he hunts the people who did it, one chapter per map.  Each mission:
two waves of Syndicate gunmen, then the chapter's boss joins the second wave.
You have three lives; enemies don't respawn.  Clear everyone to win.
"""

import random

from .. import i18n
from ..modes import Mode

GOONS = ["KNUCKLES", "SLIM", "TANK", "MOTH", "CROW", "HOLLOW", "JINX", "SNAKE", "MUTT",
         "SPIKE", "DIESEL", "WIRE", "SHADE", "COPPER", "LOCKJAW", "RUST", "GRIM", "PATCH"]

# map, enemy difficulty, wave sizes, boss (name, health, skin), threats
CHAPTERS = [
    {"id": "ashes", "map": "grid", "diff": "normal", "waves": (5, 3),
     "boss": ("BRICK", 260, "knight"), "turrets": True, "drones": 0},
    {"id": "maze", "map": "backrooms", "diff": "normal", "waves": (6, 3),
     "boss": ("ROOK", 300, "bones"), "turrets": True, "drones": 0},
    {"id": "pines", "map": "forest", "diff": "hard", "waves": (6, 4),
     "boss": ("MARA VOSS", 360, "ronin"), "turrets": True, "drones": 1},
    {"id": "below", "map": "coral", "diff": "hard", "waves": (6, 4),
     "boss": ("DUTCH", 420, "pirate"), "turrets": True, "drones": 1},
    {"id": "lastlight", "map": "skyline", "diff": "hard", "waves": (7, 5),
     "boss": ("SILAS CRANE", 600, "legend"), "turrets": True, "drones": 2},
]
REWARD_COINS = 500

TEXT = {
    "en": {
        "title": "LAST LIGHT",
        "subtitle": "A story of loss and revenge",
        "ashes": ("1. ASHES", [
            "Three years ago, the Null Syndicate came to my house at night.",
            "They were looking for money my brother owed them. They didn't find it. "
            "They found Lena, and our daughter Mia.",
            "The police called it a gas leak. The file was closed in a week.",
            "I spent three years learning to be quiet. Learning to be patient. Learning to kill.",
            "Their enforcers train in an old arena at the edge of the city. A man called Brick "
            "runs it. Brick was there that night.",
            "Tonight, it starts.",
        ], [
            "Brick talked before the end. They always do.",
            "The Syndicate keeps its books with a man called Rook. He hides in a maze of empty "
            "offices that never seems to end.",
        ]),
        "maze": ("2. THE MAZE", [
            "Rook's offices. Yellow walls, humming lights, rooms that repeat until you forget "
            "which way is out.",
            "His men drive stolen police cars. Fitting. The police never came for us either.",
            "Rook knows every name. I need his ledger.",
        ], [
            "The ledger has five names. Two are crossed out now. I did that.",
            "The third is Mara Voss. She poured the gasoline. She hides in a cabin deep in the "
            "pines.",
        ]),
        "pines": ("3. SMOKE IN THE PINES", [
            "The woods are quiet. Smoke rises from Mara's campfire.",
            "Rook kept a recording of her laughing about that night.",
            "No more laughing.",
        ], [
            "Mara's radio was still on when it was over. A voice asked for her by name: Dutch, "
            "the driver.",
            "He runs the Syndicate's smuggling post on the sea floor.",
        ]),
        "below": ("4. BELOW", [
            "Under the sea there is a town nobody remembers: strange houses, kelp forests and a "
            "glass dome full of air.",
            "Dutch moves the Syndicate's money through here. That night he waited in the car with "
            "the engine running while my house burned.",
            "He isn't driving away this time.",
        ], [
            "Dutch had one thing left to give me: an address.",
            "A penthouse on top of the tallest tower in the city. Silas Crane. The man who gave "
            "the order.",
        ]),
        "lastlight": ("5. LAST LIGHT", [
            "The city at night. Twenty-four floors of glass and steel, and a little house built "
            "on the roof like a joke.",
            "Silas Crane watches the city from up here. He thinks the height keeps him safe.",
            "Every gap between these towers is a fall. I'm not afraid of falling anymore.",
            "This is for Lena. This is for Mia.",
        ], [
            "It's over.",
            "The city still glows below, as if nothing happened. For the city, nothing did.",
            "I sat on the edge of Crane's roof until the sun came up. For the first time in three "
            "years, I slept.",
            "THE END",
        ]),
        "locked": "LOCKED - finish the previous chapter",
        "play": "PLAY CHAPTER", "replay": "PLAY AGAIN", "done": "COMPLETED",
        "next": "CLICK OR PRESS SPACE TO CONTINUE", "skip": "SKIP",
        "goal": "Kill every Syndicate gunman. {boss} arrives with the second wave. "
                "You have 3 lives.",
        "left": "TARGETS LEFT {n}   |   LIVES {l}",
        "boss_hp": "{boss} {p}%",
        "boss_in": "{boss} HAS ARRIVED",
        "reward": "+{n} coins for finishing the chapter",
        "failed": "MISSION FAILED",
        "done_sub": "MISSION COMPLETE",
    },
    "he": {
        "title": "האור האחרון",
        "subtitle": "סיפור של אובדן ונקמה",
        "ashes": ("1. אפר", [
            "לפני שלוש שנים, סינדיקט האפס הגיע לבית שלי בלילה.",
            "הם חיפשו כסף שאח שלי היה חייב להם. הם לא מצאו אותו. הם מצאו את לנה ואת הבת שלנו, "
            "מיה.",
            "המשטרה קראה לזה דליפת גז. התיק נסגר תוך שבוע.",
            "שלוש שנים למדתי להיות שקט. ללמוד סבלנות. ללמוד להרוג.",
            "המוציאים לפועל שלהם מתאמנים בזירה ישנה בקצה העיר. איש בשם בריק מנהל אותה. בריק "
            "היה שם באותו לילה.",
            "הלילה, זה מתחיל.",
        ], [
            "בריק דיבר לפני הסוף. כולם מדברים.",
            "הסינדיקט מנהל את החשבונות אצל איש בשם רוק. הוא מסתתר במבוך של משרדים ריקים שלא "
            "נגמר.",
        ]),
        "maze": ("2. המבוך", [
            "המשרדים של רוק. קירות צהובים, אורות מזמזמים, חדרים שחוזרים על עצמם עד ששוכחים "
            "איפה היציאה.",
            "האנשים שלו נוסעים בניידות משטרה גנובות. מתאים. גם המשטרה לא באה בשבילנו.",
            "רוק מכיר כל שם. אני צריך את הפנקס שלו.",
        ], [
            "בפנקס יש חמישה שמות. שניים כבר מחוקים. אני מחקתי אותם.",
            "השלישית היא מארה ווס. היא שפכה את הבנזין. היא מסתתרת בבקתה עמוק ביער.",
        ]),
        "pines": ("3. עשן בין האורנים", [
            "היער שקט. עשן עולה מהמדורה של מארה.",
            "רוק שמר הקלטה שלה צוחקת על אותו לילה.",
            "לא עוד צחוק.",
        ], [
            "הקשר של מארה עוד היה פתוח כשזה נגמר. קול ביקש אותה בשם: דאץ', הנהג.",
            "הוא מנהל את תחנת ההברחות של הסינדיקט על קרקעית הים.",
        ]),
        "below": ("4. מתחת", [
            "מתחת לים יש עיירה שאף אחד לא זוכר: בתים מוזרים, יערות אצות וכיפת זכוכית מלאה "
            "אוויר.",
            "דאץ' מעביר כאן את הכסף של הסינדיקט. באותו לילה הוא חיכה ברכב עם מנוע דולק בזמן "
            "שהבית שלי נשרף.",
            "הפעם הוא לא בורח.",
        ], [
            "לדאץ' נשאר רק דבר אחד לתת לי: כתובת.",
            "פנטהאוז על גג המגדל הגבוה בעיר. סיילס קריין. האיש שנתן את הפקודה.",
        ]),
        "lastlight": ("5. האור האחרון", [
            "העיר בלילה. עשרים וארבע קומות של זכוכית ופלדה, ובית קטן שנבנה על הגג כמו בדיחה.",
            "סיילס קריין צופה על העיר מכאן. הוא חושב שהגובה שומר עליו.",
            "כל רווח בין המגדלים האלה הוא נפילה. אני כבר לא מפחד ליפול.",
            "זה בשביל לנה. זה בשביל מיה.",
        ], [
            "זה נגמר.",
            "העיר עדיין זוהרת למטה, כאילו כלום לא קרה. בשביל העיר, כלום לא קרה.",
            "ישבתי על קצה הגג של קריין עד שהשמש עלתה. בפעם הראשונה מזה שלוש שנים, ישנתי.",
            "סוף",
        ]),
        "locked": "נעול - סיימו את הפרק הקודם",
        "play": "שחקו את הפרק", "replay": "שחקו שוב", "done": "הושלם",
        "next": "לחצו או הקישו רווח כדי להמשיך", "skip": "דילוג",
        "goal": "חסלו את כל אנשי הסינדיקט. {boss} מגיע עם הגל השני. יש לכם 3 חיים.",
        "left": "מטרות נותרו {n}   |   חיים {l}",
        "boss_hp": "{boss} {p}%",
        "boss_in": "{boss} הגיע",
        "reward": "+{n} מטבעות על סיום הפרק",
        "failed": "המשימה נכשלה",
        "done_sub": "המשימה הושלמה",
    },
}


def tx(key, **fmt):
    """Story text in the current language (logical order)."""
    lang = "he" if i18n.is_rtl() else "en"
    s = TEXT[lang].get(key, TEXT["en"].get(key, key))
    if fmt and isinstance(s, str):
        s = s.format(**fmt)
    return s


def chapter_text(i):
    """(title, intro paragraphs, outro paragraphs) for chapter index i."""
    return tx(CHAPTERS[i]["id"])


def progress(app):
    return int(app.storage.profile.data.get("story_progress", 0))


class StoryMission(Mode):
    key = "story"
    team_based = True

    def __init__(self, match, cfg):
        super().__init__(match, cfg)
        self.index = max(0, min(len(CHAPTERS) - 1, int(cfg.get("chapter", 0))))
        self.ch = CHAPTERS[self.index]
        self.difficulty = self.ch["diff"]
        self.lives = 3
        self.time_limit = 0.0
        self.score_limit = 0
        self.wave = 0
        self.boss = None
        self.enemies = []
        self.names = list(GOONS)
        random.shuffle(self.names)

    def hazard_config(self):
        return {"turrets": self.ch["turrets"], "drones": self.ch["drones"], "traps": True,
                "chaos": False, "drone_interval": 45.0}

    def setup(self):
        self.add_player(0)
        self._spawn_wave(self.ch["waves"][0])
        self.wave = 1

    def _spawn_wave(self, n, boss=False):
        for _ in range(n):
            c = self.add_bot(1, self.ch["diff"], show_name=False)
            c.lives = 0
            self.enemies.append(c)
        if boss:
            name, hp, skin = self.ch["boss"]
            from ..entities.bot import random_loadout
            c = self.m.add_combatant(name, 1, "bot", random_loadout(self.m.rng, "hard"), skin,
                                     None, "hard" if self.ch["diff"] != "nightmare" else
                                     "nightmare", show_name=True)
            self.m.spawn(c)
            c.lives = 0
            c.max_health = c.health = float(hp)
            self.boss = c
            self.enemies.append(c)
            if self.m.hud:
                self.m.hud.big_message(i18n.visual(tx("boss_in", boss=name)), "", 3.0)
            self.m.audio.play2d("countdown", 0.8)

    def on_kill(self, victim, killer):
        super().on_kill(victim, killer)
        if victim.team == 1:
            victim.lives = 0

    def can_respawn(self, c):
        if c.team == 1:
            return False
        return (c.lives or 0) > 0

    def update(self, dt):
        m = self.m
        if m.state != "live":
            return
        self.elapsed += dt
        alive = [e for e in self.enemies if e.alive]
        if self.wave == 1 and len(alive) <= 1:
            self.wave = 2
            self._spawn_wave(self.ch["waves"][1], boss=True)
        self.check_end()

    def check_end(self):
        m = self.m
        if m.player is not None and m.player.eliminated:
            self.finish(False)
            return
        if self.wave == 2 and not any(e.alive for e in self.enemies):
            self.finish(True)

    def finish(self, won=None):
        m = self.m
        if won is None:
            won = False
        sub = tx("done_sub") if won else tx("failed")
        prof = m.app.storage.profile
        first = won and self.index >= int(prof.data.get("story_progress", 0))
        if first:
            prof.data["story_progress"] = self.index + 1
            prof.data["coins"] = prof.data.get("coins", 0) + REWARD_COINS
            sub += "   " + tx("reward", n=REWARD_COINS)
            prof.save()
        m.end({"won": won, "place": 1 if won else 2, "mode": "story",
               "subtitle": i18n.visual(sub), "score": m.player.score if m.player else 0,
               "story": {"chapter": self.index, "won": won}})

    def hud_info(self):
        m = self.m
        left = sum(1 for e in self.enemies if e.alive) + \
            (self.ch["waves"][1] + 1 if self.wave == 1 else 0)
        lives = max(0, m.player.lives or 0) if m.player else 0
        small = tx("left", n=left, l=lives)
        if self.boss is not None and self.boss.alive:
            pct = int(100 * self.boss.health / max(1.0, self.boss.max_health))
            small += "   |   " + tx("boss_hp", boss=self.boss.name, p=pct)
        title = chapter_text(self.index)[0]
        return i18n.visual(title), i18n.visual(small)
