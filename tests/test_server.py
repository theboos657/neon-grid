"""Protocol-level test of the authoritative server (no Panda3D needed).

    python tests/test_server.py
"""
import json
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from neon_shared.server_core import run_in_thread  # noqa: E402

PORT = 47790


class Client:
    def __init__(self, name, loadout):
        self.s = socket.create_connection(("127.0.0.1", PORT), timeout=3)
        self.f = self.s.makefile("rb")
        self.msgs = []
        self.send({"t": "hello", "name": name, "skin": "default", "loadout": loadout, "tiers": {}})

    def send(self, m):
        self.s.sendall((json.dumps(m) + "\n").encode())

    def wait(self, t, timeout=3.0, pred=lambda m: True):
        end = time.time() + timeout
        self.s.settimeout(0.2)
        while time.time() < end:
            for i, m in enumerate(self.msgs):
                if m["t"] == t and pred(m):
                    return self.msgs.pop(i)
            try:
                line = self.f.readline()
            except socket.timeout:
                continue
            if not line:
                break
            self.msgs.append(json.loads(line))
        raise AssertionError("timeout waiting for %s" % t)


def main():
    run_in_thread("127.0.0.1", PORT)
    a = Client("Alpha", {"primary": "needle", "secondary": "vx9", "melee": "katana"})
    b = Client("Bravo", {"primary": "ar7", "secondary": "vx9", "melee": "katana"})
    ida = a.wait("welcome")["id"]
    idb = b.wait("welcome")["id"]
    a.send({"t": "create", "config": {"time_limit": 5, "score_limit": 3}})
    code = a.wait("room")["code"]
    assert len(code) == 4, code
    b.send({"t": "join", "code": code})
    room = b.wait("room")
    assert len(room["players"]) == 2
    a.send({"t": "start"})
    st = a.wait("start")
    b.wait("start")
    print("room", code, "started")
    # place both players on a clear line (x = -6 and +6 at y = -29, south lane)
    time.sleep(0.3)
    for c, x in ((a, -6.0), (b, 6.0)):
        # move in small steps so the speed limiter accepts it
        sp = st["spawns"][str(ida if c is a else idb)]
        px, py = sp[0], sp[1]
        import math
        n = int(math.hypot(x - px, -29 - py) / 0.4) + 1     # ~8 m/s, under the limit
        for i in range(1, n + 1):
            k = i / n
            c.send({"t": "st", "p": [px + (x - px) * k, py + (-29 - py) * k, 0], "yaw": 0,
                    "pitch": 0, "cr": 0, "w": "needle" if c is a else "ar7"})
            time.sleep(0.05)
            c.msgs = [m for m in c.msgs if m["t"] != "snap"]
    time.sleep(0.4)
    # Alpha snipes Bravo in the head: from (-6,-29,1.62) toward (6,-29,1.56)
    o = [-6.0, -29.0, 1.62]
    d = [1.0, 0.0, -0.005]
    a.send({"t": "fire", "w": "needle", "o": o, "d": d, "ds": [d], "seq": None})
    hit = a.wait("hit")
    print("hit:", hit)
    assert hit["v"] == idb and hit["hs"] is True
    kill = b.wait("kill")
    assert kill["k"] == ida and kill["v"] == idb
    print("kill confirmed:", kill)
    # anti-cheat: firing again immediately violates the fire rate -> no hit
    a.send({"t": "fire", "w": "needle", "o": o, "d": d, "ds": [d], "seq": None})
    # weapon not owned
    a.send({"t": "fire", "w": "lance", "o": o, "d": d, "ds": [d], "seq": None})
    # teleport -> correction
    a.send({"t": "st", "p": [25, 25, 0], "yaw": 0, "pitch": 0, "cr": 0, "w": "needle"})
    corr = a.wait("correct")
    print("teleport corrected to", corr["p"])
    # respawn arrives after 3 s
    rs = b.wait("respawn", 5.0, lambda m: m["id"] == idb)
    print("respawn:", rs)
    print("ALL SERVER TESTS PASSED")


if __name__ == "__main__":
    main()
