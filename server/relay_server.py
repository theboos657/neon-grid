#!/usr/bin/env python3
"""NEON GRID relay / matchmaking server.

Runs the authoritative match server for internet play.  Players create a room
(receiving a 4-letter code) and friends join with that code.

Requirements: Python 3.9+ and nothing else (standard library only).

    python3 relay_server.py --host 0.0.0.0 --port 47777

Deploy on any cheap VPS (1 vCPU / 512 MB is plenty for dozens of rooms); see
server/README.md for a systemd unit and a Dockerfile.
"""

import argparse
import asyncio
import logging
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# neon_shared lives next to this folder in the repo, or inside it when deployed alone
for cand in (os.path.dirname(HERE), HERE):
    if os.path.isdir(os.path.join(cand, "neon_shared")):
        sys.path.insert(0, cand)
        break

from neon_shared import GAME_VERSION  # noqa: E402
from neon_shared.protocol import DEFAULT_PORT  # noqa: E402
from neon_shared.server_core import GameServer  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="NEON GRID relay server")
    ap.add_argument("--host", default=os.environ.get("NEONGRID_HOST", "0.0.0.0"))
    # hosting platforms (Render, Railway, Fly.io...) tell the app its port via $PORT
    ap.add_argument("--port", type=int, default=int(os.environ.get(
        "NEONGRID_PORT", os.environ.get("PORT", DEFAULT_PORT))))
    ap.add_argument("--max-rooms", type=int, default=500)
    ap.add_argument("--log", default=os.environ.get("NEONGRID_LOG", "INFO"))
    args = ap.parse_args()
    logging.basicConfig(level=getattr(logging, args.log.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.info("NEON GRID server %s", GAME_VERSION)
    srv = GameServer(max_rooms=args.max_rooms)
    try:
        asyncio.run(srv.serve(args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
