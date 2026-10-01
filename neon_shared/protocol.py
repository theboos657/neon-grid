"""Wire protocol: newline-delimited JSON over TCP.

Client -> server
    hello   {name, ver, skin, loadout{primary,secondary,melee}, tiers{wid:tier}}
    create  {config{time_limit, score_limit, map}} join {code}      start {}
    map     {map}   (host, lobby only: grid / forest / backrooms)
    settings {map, mode(ffa/duel/team/coop), size(1-4), bots(0-7), difficulty}   (host, lobby)
    bomb {seq, o, v}   boom {seq, pos}   drone {}   dhit {tgt}       (hotbar 4 / 5)
    any gameplay message + "as": bot_id  -> the host acting for a bot it simulates
    st      {p[x,y,z], yaw, pitch, cr, w}           (20 Hz movement state)
    fire    {w, o[3], d[3], ds[[3]...], seq}        (hitscan or projectile launch)
    reload  {w}          melee {w, o, d}          phit {seq, tgt|None, pos[3]}
    ping    {t}          leave {}
Server -> client
    welcome {id}         room {code, host, players[{id,name,skin}], state, map, mode}
    start   {spawns{id:[x,y,z,yaw]}, time_limit, score_limit, map, mode}
    snap    {t, left, pl[[id,x,y,z,yaw,pitch,cr,alive,hp,w,score,kills,deaths,ping]]}
    shot    {id, w, o, e[[3]...]}    hit {a, v, dmg, hs, hp}    kill {k, v, w, hs}
    respawn {id, p[x,y,z,yaw]}       correct {p}      end {scores[[id,name,k,d,s]], winner}
    error   {msg}    kick {msg}      pong {t}      gone {id}
    bomb {id, o, v}  boom {id, pos}  drone {id}  dshot {id, v}   (others' gadgets)
"""

import json

DEFAULT_PORT = 47777
LAN_BEACON_PORT = 47778
TICK_RATE = 20
MAX_PLAYERS = 8
CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # no I / O to avoid confusion
MAX_LINE = 16384


def encode(msg):
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def decode(line):
    if isinstance(line, bytes):
        line = line.decode("utf-8", "replace")
    msg = json.loads(line)
    if not isinstance(msg, dict) or "t" not in msg:
        raise ValueError("bad message")
    return msg


def vec3(v, default=(0.0, 0.0, 0.0)):
    """Coerce untrusted input into a finite 3-tuple of floats."""
    try:
        x, y, z = float(v[0]), float(v[1]), float(v[2])
    except (TypeError, ValueError, IndexError):
        return default
    for c in (x, y, z):
        if c != c or c in (float("inf"), float("-inf")) or abs(c) > 1e5:
            return default
    return (x, y, z)
