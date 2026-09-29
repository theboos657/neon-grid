"""Scripted network client used by `main.py --nettest` for end-to-end tests.

Joins a room, runs around and shoots at the nearest player using only the
public protocol, exactly like a real (well-behaved) client would.
"""
import json
import math
import random
import socket
import threading
import time


def run(port, code, name="NetBot", duration=40.0):
    def worker():
        s = socket.create_connection(("127.0.0.1", port), timeout=5)
        f = s.makefile("rb")
        lock = threading.Lock()

        def send(m):
            with lock:
                s.sendall((json.dumps(m) + "\n").encode())
        send({"t": "hello", "name": name, "skin": "ronin",
              "loadout": {"primary": "ar7", "secondary": "vx9", "melee": "katana"}, "tiers": {}})
        send({"t": "join", "code": code})
        state = {"me": None, "pos": None, "others": {}, "alive": False, "live": False}

        def reader():
            s.settimeout(None)
            for line in f:
                m = json.loads(line)
                t = m["t"]
                if t == "welcome":
                    state["me"] = m["id"]
                elif t == "start":
                    sp = m["spawns"].get(str(state["me"]))
                    if sp:
                        state["pos"] = [sp[0], sp[1], 0.0]
                    state["live"] = True
                    state["alive"] = True
                elif t == "respawn" and m["id"] == state["me"]:
                    state["pos"] = m["p"][:3]
                    state["alive"] = True
                elif t == "kill" and m["v"] == state["me"]:
                    state["alive"] = False
                elif t == "snap":
                    for row in m["pl"]:
                        if row[0] != state["me"]:
                            state["others"][row[0]] = (row[1], row[2], row[3], row[7])
                elif t == "correct":
                    state["pos"] = m["p"]
        threading.Thread(target=reader, daemon=True).start()
        end = time.time() + duration
        ang = random.uniform(0, 6.28)
        last_fire = 0.0
        shots = 0
        while time.time() < end:
            time.sleep(0.05)
            if not state["live"] or not state["alive"] or state["pos"] is None:
                continue
            p = state["pos"]
            ang += 0.03
            nx = max(-30, min(30, p[0] + math.cos(ang) * 0.3))
            ny = max(-30, min(30, p[1] + math.sin(ang) * 0.3))
            state["pos"] = [nx, ny, 0.0]
            tgt = None
            for (x, y, z, alive) in state["others"].values():
                if alive:
                    tgt = (x, y, z)
            yaw = 0.0
            if tgt:
                dx, dy = tgt[0] - nx, tgt[1] - ny
                yaw = math.degrees(math.atan2(-dx, dy))
            send({"t": "st", "p": state["pos"], "yaw": yaw, "pitch": 0, "cr": 0, "w": "ar7"})
            if tgt and time.time() - last_fire > 0.4 and shots < 30:
                last_fire = time.time()
                o = [nx, ny, 1.62]
                d = [tgt[0] - nx, tgt[1] - ny, tgt[2] + 1.2 - 1.62]
                ln = math.sqrt(sum(v * v for v in d)) or 1
                d = [v / ln for v in d]
                send({"t": "fire", "w": "ar7", "o": o, "d": d, "ds": [d], "seq": None})
                shots += 1
                if shots >= 30:
                    send({"t": "reload", "w": "ar7"})
                    shots = 0
                    last_fire = time.time() + 2.0
        s.close()
    threading.Thread(target=worker, daemon=True).start()
