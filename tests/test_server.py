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

    def drain(self, secs):
        """Read everything that arrives within ``secs`` into self.msgs."""
        try:
            self.wait("__none__", secs)
        except AssertionError:
            pass


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
    maps()
    modes()
    gadgets()
    print("ALL SERVER TESTS PASSED")


def maps():
    """Room maps: chosen at create, changed by the host in the lobby, sent with start."""
    from neon_shared import arena_layout as L
    h = Client("Host", {"primary": "needle", "secondary": "vx9", "melee": "katana"})
    g = Client("Guest", {"primary": "ar7", "secondary": "vx9", "melee": "katana"})
    h.wait("welcome")
    g.wait("welcome")
    h.send({"t": "create", "config": {"time_limit": 5, "score_limit": 3, "map": "forest"}})
    room = h.wait("room")
    assert room["map"] == "forest", room
    g.send({"t": "join", "code": room["code"]})
    assert g.wait("room")["map"] == "forest"
    h.wait("room")
    g.send({"t": "map", "map": "backrooms"})                 # guests cannot change it
    h.send({"t": "map", "map": "nonsense"})                  # unknown -> THE GRID
    assert g.wait("room")["map"] == "grid"
    h.wait("room")
    h.send({"t": "map", "map": "backrooms"})
    assert g.wait("room")["map"] == "backrooms"
    h.wait("room")
    g.send({"t": "list"})
    listed = [r for r in g.wait("rooms")["rooms"] if r["code"] == room["code"]]
    assert listed and listed[0]["map"] == "backrooms", listed
    h.send({"t": "start"})
    st = g.wait("start")
    assert st["map"] == "backrooms", st
    spawns = {(x, y) for (x, y, _) in L.get("backrooms").SPAWNS}
    for sp in st["spawns"].values():
        assert (sp[0], sp[1]) in spawns, sp
    h.send({"t": "map", "map": "grid"})                      # locked once live
    g.drain(0.4)
    assert not [m for m in g.msgs if m["t"] == "room" and m.get("map") == "grid"]
    print("maps: create/change/list/start OK (backrooms spawns)")


def modes():
    """Online modes: teams with bot fill, host-driven bots, no friendly fire, team score."""
    h = Client("Host", {"primary": "needle", "secondary": "vx9", "melee": "katana"})
    g = Client("Guest", {"primary": "needle", "secondary": "vx9", "melee": "katana"})
    hid = h.wait("welcome")["id"]
    gid = g.wait("welcome")["id"]
    h.send({"t": "create", "config": {"time_limit": 5, "score_limit": 2, "map": "grid",
                                      "mode": "team", "size": 2, "difficulty": "hard"}})
    room = h.wait("room")
    assert room["mode"] == "team" and room["size"] == 2 and room["max"] == 4, room
    g.send({"t": "settings", "mode": "duel"})               # guests cannot change settings
    g.send({"t": "join", "code": room["code"]})
    g.wait("room")
    h.wait("room")
    h.send({"t": "settings", "size": 3})
    assert g.wait("room")["size"] == 3
    h.wait("room")
    h.send({"t": "settings", "size": 2})
    g.wait("room")
    h.wait("room")
    h.send({"t": "start"})
    st = h.wait("start")
    g.wait("start")
    pl = {q["id"]: q for q in st["players"]}
    assert st["mode"] == "team" and len(pl) == 4, st
    assert pl[hid]["team"] != pl[gid]["team"], "humans split across teams"
    bots = [q for q in pl.values() if q["bot"]]
    assert len(bots) == 2 and all(b["owner"] == hid for b in bots), bots
    mate = next(b for b in bots if b["team"] == pl[hid]["team"])
    enemy = next(b for b in bots if b["team"] != pl[hid]["team"])
    # only the owner may drive a bot
    g.send({"t": "st", "as": mate["id"], "p": [0, 0, 0], "yaw": 0, "pitch": 0, "cr": 0,
            "w": mate["w"][0]})
    # line everyone up on the south lane: host bot at x=-6, guest at x=+6
    sp = st["spawns"]
    time.sleep(1.6)                                        # spawn protection
    lane = {mate["id"]: [-6.0, -29.0, 0.0], gid: [6.0, -29.0, 0.0], hid: [-10.0, -29.0, 0.0]}
    for _ in range(36):
        for pid, pos in lane.items():
            cur = sp[str(pid)]
            k = min(1.0, _ / 28.0)
            p = [cur[0] + (pos[0] - cur[0]) * k, cur[1] + (pos[1] - cur[1]) * k, 0.0]
            msg = {"t": "st", "p": p, "yaw": 0, "pitch": 0, "cr": 0}
            if pid == mate["id"]:
                h.send(dict(msg, **{"as": pid, "w": mate["w"][0]}))
            elif pid == hid:
                h.send(dict(msg, w="needle"))
            else:
                g.send(dict(msg, w="needle"))
        time.sleep(0.12)
    # the host's bot shoots the guest (enemy team) through "as"
    d = [1.0, 0.0, -0.005]
    from neon_shared.weapons import weapon_stats
    bw = next((w for w in mate["w"] if not weapon_stats(w)["melee"] and
               weapon_stats(w)["speed"] == 0), None)
    if bw is not None:
        h.send({"t": "fire", "as": mate["id"], "w": bw, "o": [-6.0, -29.0, 1.62], "d": d,
                 "ds": [d], "seq": None})
        hit = g.wait("hit", 3.0, lambda m: m["v"] == gid)
        assert hit["a"] == mate["id"], hit
        print("modes: host-driven bot hit the guest for", hit["dmg"])
    # the host fires along the lane: the shot passes its own bot (no friendly fire)
    h.send({"t": "fire", "w": "needle", "o": [-10.0, -29.0, 1.62], "d": d, "ds": [d],
            "seq": None})
    kill = g.wait("kill", 3.0, lambda m: m["v"] == gid)
    assert kill["k"] in (hid, mate["id"]), kill
    assert not [m for m in h.msgs + g.msgs if m["t"] == "hit" and m.get("v") == mate["id"]],         "friendly fire must be off"
    snap = g.wait("snap", 3.0, lambda m: sum(m.get("team", [0, 0])) == 1)
    assert snap["team"][pl[hid]["team"]] == 1, snap["team"]
    print("modes: team 2v2 with bots, no friendly fire, team score", snap["team"])
    del enemy
    h.send({"t": "leave"})
    gone = g.wait("gone", 3.0)
    assert gone["id"] in (hid, mate["id"])
    print("modes: host leaving removes its bots OK")


def gadgets():
    """Hotbar: bombs (fuse, count, blast damage) and the drone (cooldown, hits)."""
    from neon_shared import gadgets as G
    a = Client("Bomber", {"primary": "ar7", "secondary": "vx9", "melee": "katana"})
    b = Client("Target", {"primary": "ar7", "secondary": "vx9", "melee": "katana"})
    ida = a.wait("welcome")["id"]
    idb = b.wait("welcome")["id"]
    a.send({"t": "create", "config": {"time_limit": 5, "score_limit": 10, "map": "grid"}})
    code = a.wait("room")["code"]
    b.send({"t": "join", "code": code})
    b.wait("room")
    a.send({"t": "start"})
    st = a.wait("start")
    b.wait("start")
    sa, sb = st["spawns"][str(ida)], st["spawns"][str(idb)]
    eye = [sa[0], sa[1], 1.62]
    # walk the target to within throwing range (respecting the server speed limit)
    goal = [sa[0] + (8.0 if sa[0] < 20 else -8.0), sa[1], 0.0]
    cur = [sb[0], sb[1], 0.0]
    time.sleep(1.6)                                    # spawn protection
    for _ in range(200):
        dx, dy = goal[0] - cur[0], goal[1] - cur[1]
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 0.05:
            break
        step = min(dist, 1.6)
        cur = [cur[0] + dx / dist * step, cur[1] + dy / dist * step, 0.0]
        b.send({"t": "st", "p": cur, "yaw": 0, "pitch": 0, "cr": 0, "w": "ar7"})
        time.sleep(0.1)
    sb = cur
    # drone: deploy once, hits limited by the fire interval, second deploy on cooldown
    a.send({"t": "drone"})
    b.wait("drone")
    a.send({"t": "dhit", "tgt": idb})
    a.send({"t": "dhit", "tgt": idb})                               # too fast: ignored
    b.drain(0.4)
    dshots = [m for m in b.msgs if m["t"] == "dshot"]
    assert len(dshots) == 1, dshots
    a.send({"t": "drone"})
    b.drain(0.4)
    assert not [m for m in b.msgs if m["t"] == "drone"], "drone cooldown"
    b.drain(0.3)
    b.msgs.clear()                     # forget the drone's hit before testing bombs
    # early blast is refused, a real one 1.8 s later hurts the target standing on it
    a.send({"t": "bomb", "seq": 1, "o": eye, "v": [0, 10, 3]})
    bomb = b.wait("bomb")
    assert bomb["id"] == ida
    a.send({"t": "boom", "seq": 1, "pos": [sb[0], sb[1], 0.3]})
    b.drain(0.4)
    assert not [m for m in b.msgs if m["t"] == "hit"], "instant blast must be refused"
    a.send({"t": "bomb", "seq": 2, "o": eye, "v": [0, 10, 3]})
    time.sleep(G.BOMB_FUSE)
    a.send({"t": "boom", "seq": 2, "pos": [sb[0], sb[1], 0.3]})
    hit = b.wait("hit", 3.0, lambda m: m["v"] == idb)
    assert hit["a"] == ida and hit["dmg"] > 50, hit
    b.msgs = [m for m in b.msgs if m["t"] != "bomb"]
    a.send({"t": "bomb", "seq": 3, "o": eye, "v": [0, 10, 3]})     # third bomb: none left
    b.drain(0.4)
    assert len([m for m in b.msgs if m["t"] == "bomb"]) == 0, "only 2 bombs per life"
    print("gadgets: bomb fuse/count/blast %.0f dmg, drone rate + cooldown OK" % hit["dmg"])


if __name__ == "__main__":
    main()
