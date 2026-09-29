"""The 10 loadout abilities.  Each costs energy and has a cooldown.

Energy (max 100) refills slowly on its own and fully at charging ports.
"""

ABILITIES = [
    {"id": "shield", "name": "Aegis Shield", "cooldown": 18.0, "energy": 30, "duration": 4.0,
     "desc": "Absorbs up to 60 damage for 4 s.", "icon": "S"},
    {"id": "dash", "name": "Phase Dash", "cooldown": 5.0, "energy": 15, "duration": 0.18,
     "desc": "Burst 8 m in your move direction.", "icon": "D"},
    {"id": "scan", "name": "Scan Pulse", "cooldown": 20.0, "energy": 25, "duration": 4.0,
     "desc": "Reveals enemies through walls within 40 m.", "icon": "P"},
    {"id": "decoy", "name": "Holo Decoy", "cooldown": 20.0, "energy": 25, "duration": 6.0,
     "desc": "Spawns a hologram that draws enemy fire.", "icon": "H"},
    {"id": "heal", "name": "Heal Burst", "cooldown": 22.0, "energy": 35, "duration": 1.0,
     "desc": "Restores 45 health over 1 s.", "icon": "+"},
    {"id": "speed", "name": "Overdrive", "cooldown": 16.0, "energy": 20, "duration": 5.0,
     "desc": "+35% movement speed for 5 s.", "icon": ">"},
    {"id": "jets", "name": "Jump Jets", "cooldown": 8.0, "energy": 15, "duration": 1.2,
     "desc": "Launch upward and hover briefly.", "icon": "^"},
    {"id": "emp", "name": "EMP Blast", "cooldown": 24.0, "energy": 40, "duration": 5.0,
     "desc": "Disables drones, turrets and enemy abilities within 9 m.", "icon": "E"},
    {"id": "cloak", "name": "Optic Cloak", "cooldown": 25.0, "energy": 35, "duration": 5.0,
     "desc": "Near invisibility for 5 s. Firing breaks it.", "icon": "C"},
    {"id": "gravity", "name": "Gravity Well", "cooldown": 22.0, "energy": 35, "duration": 2.5,
     "desc": "Singularity that pulls and damages enemies.", "icon": "G"},
]

BY_ID = {a["id"]: a for a in ABILITIES}
IDS = [a["id"] for a in ABILITIES]

MAX_ENERGY = 100.0
ENERGY_REGEN = 1.5          # per second, passive
PORT_CHARGE_TIME = 3.0      # seconds standing on a port for a full refill
