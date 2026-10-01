"""Cosmetic skins.  Unlocked through the battle pass or bought with coins
(earned in-game only; there are no real-money purchases anywhere)."""

# body = main colour, accent = neon colour, pattern = viewmodel decoration
WEAPON_SKINS = [
    {"id": "default", "name": "Standard Issue", "body": (0.16, 0.17, 0.2), "accent": (0.1, 0.9, 1.0),
     "pattern": "solid", "price": 0, "source": "default"},
    {"id": "carbon", "name": "Carbon Ghost", "body": (0.06, 0.06, 0.07), "accent": (0.7, 1.0, 1.0),
     "pattern": "stripes", "price": 400, "source": "shop"},
    {"id": "ice", "name": "Cryo Line", "body": (0.55, 0.65, 0.72), "accent": (0.3, 0.8, 1.0),
     "pattern": "solid", "price": 600, "source": "shop"},
    {"id": "abyss", "name": "Abyss Blue", "body": (0.03, 0.06, 0.16), "accent": (0.1, 0.4, 1.0),
     "pattern": "digital", "price": 800, "source": "shop"},
    {"id": "toxic", "name": "Toxic Current", "body": (0.08, 0.12, 0.08), "accent": (0.3, 1.0, 0.4),
     "pattern": "stripes", "price": 900, "source": "shop"},
    {"id": "sunset", "name": "Outrun Sunset", "body": (0.18, 0.05, 0.14), "accent": (1.0, 0.3, 0.7),
     "pattern": "digital", "price": 0, "source": "pass"},
    {"id": "volt", "name": "Volt Rider", "body": (0.12, 0.12, 0.02), "accent": (1.0, 0.9, 0.1),
     "pattern": "stripes", "price": 0, "source": "pass"},
    {"id": "gridline", "name": "Gridline", "body": (0.02, 0.02, 0.03), "accent": (0.1, 1.0, 1.0),
     "pattern": "digital", "price": 0, "source": "pass"},
    {"id": "chrome", "name": "Liquid Chrome", "body": (0.75, 0.78, 0.82), "accent": (0.9, 1.0, 1.0),
     "pattern": "solid", "price": 0, "source": "pass"},
    {"id": "crimson", "name": "Crimson Protocol", "body": (0.14, 0.02, 0.03), "accent": (1.0, 0.15, 0.2),
     "pattern": "stripes", "price": 0, "source": "pass"},
    {"id": "aurora", "name": "Aurora", "body": (0.05, 0.08, 0.12), "accent": (0.5, 0.5, 1.0),
     "pattern": "digital", "price": 0, "source": "pass"},
    {"id": "gold", "name": "Neon Gold", "body": (0.55, 0.42, 0.12), "accent": (1.0, 0.85, 0.4),
     "pattern": "solid", "price": 0, "source": "pass"},
]

# Character outfits.  head: helmet / hood / cap / astro / banana / shark / skull / knight /
# cat / crown / mohawk / pirate / ninja.  back: pack / cape / wings / katana / tank / none.
# skin = face colour where the face shows.
CHAR_SKINS = [
    {"id": "default", "name": "Grid Runner", "body": (0.14, 0.15, 0.18), "accent": (0.1, 0.9, 1.0),
     "visor": (0.2, 1.0, 1.0), "head": "helmet", "back": "pack", "price": 0, "source": "default"},
    {"id": "shadow", "name": "Shadow Op", "body": (0.05, 0.05, 0.06), "accent": (0.3, 0.5, 1.0),
     "visor": (0.5, 0.7, 1.0), "head": "hood", "back": "cape", "price": 500, "source": "shop"},
    {"id": "medic", "name": "Field Tech", "body": (0.5, 0.55, 0.6), "accent": (0.2, 1.0, 0.6),
     "visor": (0.2, 1.0, 0.6), "head": "cap", "skin": (0.85, 0.65, 0.5), "back": "pack",
     "price": 700, "source": "shop"},
    {"id": "ronin", "name": "Neon Ronin", "body": (0.1, 0.03, 0.05), "accent": (1.0, 0.2, 0.4),
     "visor": (1.0, 0.3, 0.4), "head": "ninja", "back": "katana", "price": 1000, "source": "shop"},
    {"id": "banana", "name": "Peel Agent", "body": (0.95, 0.82, 0.15), "accent": (0.35, 0.25, 0.1),
     "visor": (0.1, 0.1, 0.1), "head": "banana", "skin": (0.95, 0.82, 0.15), "back": "none",
     "price": 1200, "source": "shop"},
    {"id": "shark", "name": "Chomp Squad", "body": (0.35, 0.45, 0.55), "accent": (1.0, 1.0, 1.0),
     "visor": (0.1, 0.1, 0.12), "head": "shark", "skin": (0.85, 0.65, 0.5), "back": "none",
     "price": 1200, "source": "shop"},
    {"id": "astro", "name": "Star Walker", "body": (0.85, 0.86, 0.88), "accent": (1.0, 0.45, 0.1),
     "visor": (1.0, 0.75, 0.2), "head": "astro", "back": "tank", "price": 1500, "source": "shop"},
    {"id": "bones", "name": "Bone Rider", "body": (0.08, 0.08, 0.09), "accent": (0.95, 0.95, 0.9),
     "visor": (1.0, 0.3, 0.1), "head": "skull", "back": "cape", "price": 1500, "source": "shop"},
    {"id": "knight", "name": "Iron Knight", "body": (0.55, 0.57, 0.6), "accent": (0.9, 0.15, 0.15),
     "visor": (0.05, 0.05, 0.05), "head": "knight", "back": "cape", "price": 1800,
     "source": "shop"},
    {"id": "pirate", "name": "Deep Pirate", "body": (0.35, 0.12, 0.1), "accent": (1.0, 0.8, 0.3),
     "visor": (0.1, 0.1, 0.1), "head": "pirate", "skin": (0.75, 0.55, 0.42), "back": "none",
     "price": 1300, "source": "shop"},
    {"id": "kitty", "name": "Neon Kitty", "body": (0.95, 0.5, 0.75), "accent": (1.0, 1.0, 1.0),
     "visor": (0.4, 1.0, 1.0), "head": "cat", "back": "wings", "price": 1600, "source": "shop"},
    {"id": "synth", "name": "Synthwave", "body": (0.12, 0.04, 0.16), "accent": (1.0, 0.4, 0.9),
     "visor": (0.3, 1.0, 1.0), "head": "mohawk", "skin": (0.6, 0.42, 0.32), "back": "pack",
     "price": 0, "source": "pass"},
    {"id": "hazmat", "name": "Hazmat", "body": (0.3, 0.28, 0.05), "accent": (1.0, 0.9, 0.1),
     "visor": (1.0, 0.6, 0.1), "head": "astro", "back": "tank", "price": 0, "source": "pass"},
    {"id": "ghost", "name": "Ghost Signal", "body": (0.7, 0.75, 0.8), "accent": (0.8, 1.0, 1.0),
     "visor": (0.9, 1.0, 1.0), "head": "hood", "back": "wings", "price": 0, "source": "pass"},
    {"id": "cobalt", "name": "Cobalt Guard", "body": (0.04, 0.08, 0.2), "accent": (0.2, 0.5, 1.0),
     "visor": (0.4, 0.8, 1.0), "head": "knight", "back": "pack", "price": 0, "source": "pass"},
    {"id": "emerald", "name": "Emerald Code", "body": (0.02, 0.1, 0.06), "accent": (0.2, 1.0, 0.5),
     "visor": (0.5, 1.0, 0.6), "head": "cat", "back": "pack", "price": 0, "source": "pass"},
    {"id": "legend", "name": "Grid Legend", "body": (0.02, 0.02, 0.02), "accent": (1.0, 1.0, 1.0),
     "visor": (0.1, 1.0, 1.0), "head": "crown", "back": "wings", "price": 0, "source": "pass"},
]

WEAPON_SKIN_BY_ID = {s["id"]: s for s in WEAPON_SKINS}
CHAR_SKIN_BY_ID = {s["id"]: s for s in CHAR_SKINS}

BOT_SKIN_POOL = ["default", "shadow", "medic", "ronin", "synth", "hazmat", "cobalt", "emerald",
                 "banana", "shark", "astro", "bones", "knight", "pirate", "kitty"]

TEAM_COLORS = {0: (0.1, 0.9, 1.0), 1: (1.0, 0.18, 0.3)}


def weapon_skin(sid):
    return WEAPON_SKIN_BY_ID.get(sid, WEAPON_SKINS[0])


def char_skin(sid):
    return CHAR_SKIN_BY_ID.get(sid, CHAR_SKINS[0])
