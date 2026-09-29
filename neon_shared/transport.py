"""Transports for the line-based JSON protocol (standard library only).

Addresses the client understands:
    host:port                 raw TCP (LAN / VPS relay)
    ws://host[:port][/path]   WebSocket
    wss://host[:port][/path]  WebSocket over TLS (free hosts like Render, Fly.io, Railway)

The server accepts raw TCP *and* WebSocket clients on the same port, and
answers plain HTTP GETs with a health page (hosting platforms probe that).
Each protocol message travels as one WebSocket text frame.
"""

import asyncio
import base64
import hashlib
import os
import socket
import ssl
import struct

from . import protocol as P

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def parse_address(addr, default_port=P.DEFAULT_PORT):
    """-> (scheme, host, port, path).  scheme is 'tcp', 'ws' or 'wss'."""
    addr = (addr or "").strip()
    scheme = "tcp"
    path = "/"
    low = addr.lower()
    if low.startswith("wss://"):
        scheme, addr = "wss", addr[6:]
    elif low.startswith("ws://"):
        scheme, addr = "ws", addr[5:]
    elif low.startswith("https://"):
        scheme, addr = "wss", addr[8:]
    elif low.startswith("http://"):
        scheme, addr = "ws", addr[7:]
    if "/" in addr:
        addr, rest = addr.split("/", 1)
        path = "/" + rest
    host, _, port = addr.partition(":")
    if port:
        try:
            port = int(port)
        except ValueError:
            port = default_port
    else:
        port = {"wss": 443, "ws": 80}.get(scheme, default_port)
    return scheme, host or "127.0.0.1", port, path


# ===========================================================================
# client side (blocking sockets, used on background threads by the game)
# ===========================================================================
class Connection:
    """Blocking connection with ``send_line(bytes)`` / ``readline()`` / ``close()``."""

    def __init__(self, sock):
        self.sock = sock
        self._file = sock.makefile("rb")

    def send_line(self, data):
        self.sock.sendall(data)

    def readline(self, limit=P.MAX_LINE):
        return self._file.readline(limit)

    def settimeout(self, t):
        self.sock.settimeout(t)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class WSConnection(Connection):
    """Minimal RFC 6455 client: masked text frames out, lines split from frames in."""

    def __init__(self, sock):
        super().__init__(sock)
        self._buf = b""

    def _recv_exact(self, n):
        data = self._file.read(n)
        if data is None or len(data) < n:
            raise ConnectionError("websocket closed")
        return data

    def send_line(self, data):
        payload = data
        head = bytearray([0x81])                   # FIN + text
        n = len(payload)
        if n < 126:
            head.append(0x80 | n)
        elif n < 65536:
            head.append(0x80 | 126)
            head += struct.pack(">H", n)
        else:
            head.append(0x80 | 127)
            head += struct.pack(">Q", n)
        mask = os.urandom(4)
        head += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(head) + masked)

    def _send_control(self, opcode, payload=b""):
        mask = os.urandom(4)
        frame = bytes([0x80 | opcode, 0x80 | len(payload)]) + mask + \
            bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        try:
            self.sock.sendall(frame)
        except OSError:
            pass

    def _read_message(self):
        data = b""
        while True:
            b1, b2 = self._recv_exact(2)
            fin = b1 & 0x80
            opcode = b1 & 0x0F
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if b2 & 0x80 else None
            payload = self._recv_exact(n) if n else b""
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x8:                       # close
                raise ConnectionError("websocket closed")
            if opcode == 0x9:                       # ping -> pong
                self._send_control(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            data += payload
            if fin:
                return data

    def readline(self, limit=P.MAX_LINE):
        try:
            while b"\n" not in self._buf:
                self._buf += self._read_message()
        except (ConnectionError, OSError, struct.error, ValueError):
            rest, self._buf = self._buf, b""
            return rest
        line, _, self._buf = self._buf.partition(b"\n")
        return line + b"\n"

    def close(self):
        self._send_control(0x8)
        super().close()


def connect(address, timeout=5.0, connect_timeout=None):
    """Open a Connection to ``address`` (any supported format)."""
    scheme, host, port, path = parse_address(address)
    sock = socket.create_connection((host, port), timeout=connect_timeout or timeout)
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass
    if scheme == "tcp":
        sock.settimeout(timeout)
        return Connection(sock)
    if scheme == "wss":
        ctx = ssl.create_default_context()
        sock = ctx.wrap_socket(sock, server_hostname=host)
    sock.settimeout(timeout)
    key = base64.b64encode(os.urandom(16)).decode()
    host_hdr = host if port in (80, 443) else "%s:%d" % (host, port)
    req = ("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
           "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n"
           "User-Agent: NEONGRID\r\n\r\n" % (path, host_hdr, key))
    sock.sendall(req.encode())
    conn = WSConnection(sock)
    status = conn._file.readline(4096)
    if b" 101 " not in status:
        conn.close()
        raise ConnectionError("server did not accept the WebSocket (%s)" %
                              status.decode(errors="replace").strip())
    while True:                                     # skip response headers
        line = conn._file.readline(4096)
        if line in (b"\r\n", b"\n", b""):
            break
    return conn


# ===========================================================================
# server side (asyncio) - adapters so GameServer sees reader/writer objects
# ===========================================================================
class _PrefixReader:
    """Raw TCP reader that replays the first line we peeked at."""

    def __init__(self, first, reader):
        self.first = first
        self.reader = reader

    async def readline(self):
        if self.first is not None:
            line, self.first = self.first, None
            return line
        return await self.reader.readline()


class _WSReader:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.buf = b""

    async def _message(self):
        data = b""
        while True:
            b1, b2 = await self.reader.readexactly(2)
            fin = b1 & 0x80
            opcode = b1 & 0x0F
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", await self.reader.readexactly(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", await self.reader.readexactly(8))[0]
            if n > P.MAX_LINE * 4:
                raise ConnectionError("frame too large")
            mask = await self.reader.readexactly(4) if b2 & 0x80 else b"\0\0\0\0"
            payload = await self.reader.readexactly(n) if n else b""
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x8:
                raise ConnectionError("closed")
            if opcode == 0x9:
                self.writer.transport.write(bytes([0x8A, len(payload)]) + payload)
                continue
            if opcode == 0xA:
                continue
            data += payload
            if fin:
                return data

    async def readline(self):
        try:
            while b"\n" not in self.buf:
                self.buf += await self._message()
        except (ConnectionError, asyncio.IncompleteReadError, OSError):
            rest, self.buf = self.buf, b""
            return rest
        line, _, self.buf = self.buf.partition(b"\n")
        return line + b"\n"


class _WSWriter:
    """Writer that frames each protocol message as one WebSocket text frame."""

    def __init__(self, writer):
        self.w = writer

    def write(self, data):
        n = len(data)
        if n < 126:
            head = bytes([0x81, n])
        elif n < 65536:
            head = bytes([0x81, 126]) + struct.pack(">H", n)
        else:
            head = bytes([0x81, 127]) + struct.pack(">Q", n)
        self.w.write(head + data)

    async def drain(self):
        await self.w.drain()

    def close(self):
        try:
            self.w.write(b"\x88\x00")
        except Exception:
            pass
        self.w.close()

    def get_extra_info(self, name, default=None):
        return self.w.get_extra_info(name, default)


async def accept(reader, writer, handler):
    """Detect raw TCP / WebSocket / plain HTTP on a fresh connection and hand the
    game connection to ``handler(reader, writer)``."""
    try:
        first = await asyncio.wait_for(reader.readline(), 15.0)
    except (asyncio.TimeoutError, ConnectionError, asyncio.LimitOverrunError, ValueError):
        writer.close()
        return
    if not first:
        writer.close()
        return
    if not first.startswith((b"GET ", b"HEAD ")):
        await handler(_PrefixReader(first, reader), writer)
        return
    headers = {}
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):
            break
        k, _, v = line.decode("latin-1").partition(":")
        headers[k.strip().lower()] = v.strip()
    if "websocket" not in headers.get("upgrade", "").lower():
        body = b"NEON GRID relay server OK\n"
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: %d\r\n"
                     b"Connection: close\r\n\r\n%s" % (len(body), body))
        try:
            await writer.drain()
        finally:
            writer.close()
        return
    accept_key = base64.b64encode(hashlib.sha1(
        (headers.get("sec-websocket-key", "") + WS_GUID).encode()).digest()).decode()
    writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                  "Connection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n\r\n" % accept_key).encode())
    await writer.drain()
    await handler(_WSReader(reader, writer), _WSWriter(writer))
