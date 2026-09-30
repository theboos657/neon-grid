"""Room browser: finds every open room.

Sources
  * LAN   - hosts on the local network announce themselves with UDP beacons
            (see lan.py); each announcing server is then asked for its rooms.
  * Relay - the relay server in Settings > Multiplayer is asked for its rooms.
Every server is queried with the protocol's ``list`` request over a short TCP
connection, so player counts and match state are always live.

All networking runs on a background thread; the UI reads ``rooms`` / ``status``.
"""

import json
import socket
import threading
import time

from neon_shared import protocol as P
from neon_shared.protocol import LAN_BEACON_PORT

from .lan import query_address, query_server, scan_lan

REFRESH = 3.0
SCAN_EVERY = 12.0         # full subnet scan (catches hosts whose broadcasts are blocked)


class RoomBrowser:
    def __init__(self, relay_addr):
        self.relay = relay_addr            # address string (host:port / ws:// / wss://) or None
        self.rooms = []                    # list of dicts (see _refresh)
        self.lan_servers = {}              # (ip, port) -> last seen
        self.status = "searching"
        self.relay_ok = None
        self.running = True
        self.lock = threading.Lock()
        self.version = 0                   # bumps whenever the list changes
        self.scanning = False
        threading.Thread(target=self._listen_lan, name="browser-lan", daemon=True).start()
        threading.Thread(target=self._loop, name="browser-query", daemon=True).start()

    def stop(self):
        self.running = False

    def refresh_now(self):
        self._scan_force = True
        self._force = True

    _scan_force = True

    _force = False

    # ------------------------------------------------------------------ LAN beacons
    def _listen_lan(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("", LAN_BEACON_PORT))
        except OSError:
            s.close()
            return
        s.settimeout(0.5)
        try:
            while self.running:
                try:
                    data, addr = s.recvfrom(2048)
                except socket.timeout:
                    continue
                except OSError:
                    break
                try:
                    msg = json.loads(data.decode())
                except ValueError:
                    continue
                if msg.get("game") != "neongrid":
                    continue
                key = (addr[0], int(msg.get("port", P.DEFAULT_PORT)))
                with self.lock:
                    new = key not in self.lan_servers
                    self.lan_servers[key] = time.monotonic()
                if new:
                    self._force = True
        finally:
            s.close()

    # ------------------------------------------------------------------ queries
    def _loop(self):
        next_t = 0.0
        next_scan = 0.0
        while self.running:
            now = time.monotonic()
            if now >= next_scan or self._scan_force:
                self._scan_force = False
                self.scanning = True
                for ip, port, _rooms, _ping in scan_lan():
                    with self.lock:
                        self.lan_servers[(ip, port)] = time.monotonic() + 3600   # keep it
                self.scanning = False
                next_scan = time.monotonic() + SCAN_EVERY
                self._force = True
            if now >= next_t or self._force:
                self._force = False
                self._refresh()
                next_t = time.monotonic() + REFRESH
            time.sleep(0.1)

    def _refresh(self):
        found = []
        seen_codes = set()
        # LAN servers seen in the last 5 s (a PC hosting shows up as 127.0.0.1 too)
        with self.lock:
            lan = [k for k, t in self.lan_servers.items() if time.monotonic() - t < 5.0]
            # scanned servers stay listed until they stop answering
            self.lan_servers = {k: t for k, t in self.lan_servers.items()
                                if time.monotonic() - t < 5.0 or t > time.monotonic()}
        lan.sort(key=lambda k: k[0] == "127.0.0.1")         # prefer the real LAN IP
        for host, port in lan:
            rooms, ping = query_server(host, port)
            if rooms is None:
                with self.lock:
                    self.lan_servers.pop((host, port), None)      # host went away
            for r in rooms or []:
                if r["code"] in seen_codes:
                    continue
                seen_codes.add(r["code"])
                found.append(dict(r, source="lan", addr="%s:%d" % (host, port), ping=ping))
        if self.relay is not None:
            # sleeping free-tier relays can take a while to answer the first time
            rooms, ping = query_address(self.relay, timeout=20.0 if "://" in self.relay else 1.5)
            self.relay_ok = rooms is not None
            for r in rooms or []:
                if r["code"] in seen_codes:
                    continue
                seen_codes.add(r["code"])
                found.append(dict(r, source="online", addr=self.relay, ping=ping))
        found.sort(key=lambda r: (r["state"] != "lobby", r["source"] != "lan", -r["players"]))
        def sig(rs):
            return [(r["code"], r["players"], r["state"], r["source"], r.get("map")) for r in rs]
        with self.lock:
            if sig(found) != sig(self.rooms) or self.status != "done":
                self.version += 1
            self.rooms = found
            self.status = "done"
