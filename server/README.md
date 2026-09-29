# NEON GRID relay server

A small, dependency-free (standard library only) authoritative match server.
It hands out 4-letter room codes, runs the match clock, validates every shot
and movement update, and broadcasts 20 Hz snapshots.

## Run locally

```bash
python3 server/relay_server.py --port 47777
```

In the game: **Multiplayer → Relay server** = `127.0.0.1:47777` → **Host online**.

## Free hosting on Render (no VPS, no port forwarding)

The server speaks raw TCP **and** WebSocket on the same port, so it runs on free web hosts.

1. Put this project on GitHub (a private repository is fine).
2. Go to https://dashboard.render.com, choose **New > Blueprint**, and pick the repository.
   `render.yaml` sets everything up.
3. When it is live, copy the URL, for example `https://neongrid-relay-ab12.onrender.com`.
4. Open `assets/config.json`, set `"default_server": "wss://neongrid-relay-ab12.onrender.com"`,
   and run `python build.py`. Everyone who installs that build uses the relay automatically.
   You can also type the address in **Multiplayer > SERVER / HOST IP**.

Free services sleep after about 15 idle minutes. The first person to connect then waits up to
about a minute while it wakes up. Railway, Fly.io and Koyeb work the same way (they all set
`$PORT`).

## Deploy on a VPS (Ubuntu/Debian)

```bash
sudo mkdir -p /opt/neongrid
sudo cp -r neon_shared server /opt/neongrid/
sudo cp server/neongrid.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now neongrid
sudo ufw allow 47777/tcp        # if ufw is enabled
```

Players then set **Relay server** to `your.vps.ip:47777`.

### Docker

```bash
docker build -f server/Dockerfile -t neongrid-server .
docker run -d --restart unless-stopped -p 47777:47777 neongrid-server
```

## What the server enforces

| Check | Rule |
|---|---|
| Damage / health / kills | Computed only on the server |
| Hitscan | Re-traced server-side vs. static geometry and lag-compensated positions (rewind ≤ 350 ms) |
| Projectiles | Client-reported impacts must match a real shot, lie on its ray and have a plausible flight time |
| Fire rate / magazine | Per-weapon minimum interval; shots since last reload ≤ magazine |
| Weapon ownership | Only the three weapons declared at join may fire |
| Shot origin | Must be within 3 m of the server's view of the shooter's eyes |
| Pellet cone | Each pellet must lie inside the weapon's spread cone |
| Movement | Token-bucket speed limit (allows dash/slide/jump pads) + arena bounds; violators are snapped back |
| Kick | 10 violations within 10 seconds |

Environment variables `NEONGRID_HOST`, `NEONGRID_PORT`, `NEONGRID_LOG` override defaults.
