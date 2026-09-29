"""LAN discovery.

Two independent ways to find hosts on the local network, so it still works on
networks that block one of them:

1. **Beacons** - the host announces its room over UDP every second, sent to
   the global broadcast address *and* to every local adapter's subnet
   broadcast (Windows otherwise often sends 255.255.255.255 out a VPN /
   virtual adapter instead of the Wi-Fi).
2. **Subnet scan** - the joiner asks every address on its /24 network(s) for
   rooms over TCP.  Works even when routers or firewalls drop broadcasts;
   only needs the host's TCP port to be reachable.
"""

import concurrent.futures
import json
import socket
import threading
import time

from neon_shared import protocol as P
from neon_shared.protocol import LAN_BEACON_PORT


# ---------------------------------------------------------------------------
# local addresses
# ---------------------------------------------------------------------------
def local_ipv4s():
    """Usable IPv4 addresses of this PC (no loopback / link-local)."""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    # the address used for the default route (most likely the real LAN adapter)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
    except OSError:
        pass
    finally:
        s.close()
    return sorted(ip for ip in ips if not ip.startswith(("127.", "169.254.", "0.")))


def primary_ip():
    ips = local_ipv4s()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return ips[0] if ips else "127.0.0.1"
    finally:
        s.close()


def _subnet(ip):
    return ip.rsplit(".", 1)[0]          # assume the common /24 home network


def broadcast_targets():
    return ["255.255.255.255"] + ["%s.255" % _subnet(ip) for ip in local_ipv4s()] + ["127.0.0.1"]


# ---------------------------------------------------------------------------
# querying a server
# ---------------------------------------------------------------------------
def query_server(host, port, timeout=1.5, connect_timeout=None):
    return query_address("%s:%d" % (host, port), timeout, connect_timeout)


def query_address(address, timeout=1.5, connect_timeout=None):
    """Ask one server (any address format) for its open rooms.
    Returns (rooms list or None, ping ms)."""
    from neon_shared import transport
    t0 = time.monotonic()
    try:
        conn = transport.connect(address, timeout=timeout, connect_timeout=connect_timeout)
    except (OSError, ConnectionError, ValueError):
        return None, None
    try:
        conn.send_line(P.encode({"t": "list"}))
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            line = conn.readline(P.MAX_LINE)
            if not line:
                break
            msg = json.loads(line)
            if msg.get("t") == "rooms":
                return msg.get("rooms", []), int((time.monotonic() - t0) * 1000)
    except (OSError, ConnectionError, ValueError):
        pass
    finally:
        conn.close()
    return None, None


def scan_lan(port=P.DEFAULT_PORT, connect_timeout=0.35, workers=96):
    """Probe every address on each local /24 for a NEON GRID server.
    Returns a list of (ip, port, rooms, ping)."""
    targets = []
    own = set(local_ipv4s())
    for net in sorted({_subnet(ip) for ip in own}):
        targets += ["%s.%d" % (net, i) for i in range(1, 255)]
    if not targets:
        targets = ["127.0.0.1"]
    found = []

    def probe(ip):
        rooms, ping = query_server(ip, port, timeout=1.2, connect_timeout=connect_timeout)
        if rooms is not None:
            return (ip, port, rooms, ping)
        return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(probe, targets):
            if r is not None:
                found.append(r)
    return found


# ---------------------------------------------------------------------------
# host side: beacon
# ---------------------------------------------------------------------------
class Beacon:
    def __init__(self, code_fn, port, name):
        self.code_fn = code_fn
        self.port = port
        self.name = name
        self.running = True
        self.thread = threading.Thread(target=self._run, name="lan-beacon", daemon=True)
        self.thread.start()

    def _run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        targets = broadcast_targets()
        n = 0
        try:
            while self.running:
                code = self.code_fn()
                if code:
                    msg = json.dumps({"game": "neongrid", "code": code, "port": self.port,
                                      "name": self.name}).encode()
                    for addr in targets:
                        try:
                            s.sendto(msg, (addr, LAN_BEACON_PORT))
                        except OSError:
                            pass
                n += 1
                if n % 10 == 0:                   # adapters can change (Wi-Fi reconnect)
                    targets = broadcast_targets()
                time.sleep(1.0)
        finally:
            s.close()

    def stop(self):
        self.running = False


# ---------------------------------------------------------------------------
# joiner side
# ---------------------------------------------------------------------------
def find_host(code, timeout=5.0):
    """Wait up to ``timeout`` s for a beacon announcing ``code``; returns (ip, port) or None."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("", LAN_BEACON_PORT))
    except OSError:
        s.close()
        return None
    s.settimeout(0.5)
    end = time.monotonic() + timeout
    try:
        while time.monotonic() < end:
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
            if msg.get("game") == "neongrid" and str(msg.get("code", "")).upper() == code.upper():
                return addr[0], int(msg.get("port", 0))
    finally:
        s.close()
    return None


def find_room(code, beacon_timeout=3.0):
    """Find the server hosting ``code``: beacons first, then a subnet scan."""
    found = find_host(code, beacon_timeout)
    if found is not None:
        return found
    for ip, port, rooms, _ in scan_lan():
        if any(r.get("code", "").upper() == code.upper() for r in rooms):
            return ip, port
    return None
