"""Pure-Python data and math shared by the game client and the relay server.

Nothing in this package may import Panda3D: the dedicated server runs on a
headless VPS with only the Python standard library installed.
"""

GAME_VERSION = "1.0.7"
PROTOCOL_VERSION = 3
