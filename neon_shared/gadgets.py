"""Hotbar gadgets (slot 4: bombs, slot 5: drone).  Shared by the game and the server
so damage, counts and cooldowns agree online."""

BOMBS_PER_LIFE = 2
BOMB_FUSE = 1.8            # seconds from throw to blast
BOMB_RADIUS = 5.5
BOMB_DMG = 110.0
BOMB_THROW_SPEED = 17.0

DRONE_LIFE = 20.0          # seconds a deployed drone fights for you
DRONE_COOLDOWN = 35.0      # from deploy to the next drone
DRONE_DMG = 14.0
DRONE_FIRE_INTERVAL = 1.2
DRONE_RANGE = 32.0
