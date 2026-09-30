# NEON GRID

A fast, ground-based first-person arena shooter for Windows. You fight in a sealed
cyberpunk arena of black surfaces, cyan neon, wet reflective floors and holographic signs.
Built with Python 3.11 and Panda3D, with custom GLSL shaders for lighting, reflections and bloom.

Everything is generated procedurally at runtime: the arena, the weapons, the textures, the
synthwave soundtrack and the sound effects. The only bundled assets are the icon and the
announcer voice lines.

---

## Quick start (from source)

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The first launch takes a few extra seconds while the game synthesizes its audio into
`%APPDATA%\NeonGrid\cache`. Later launches load it from there.

Useful flags:

| Flag | Effect |
|---|---|
| `--mode ffa\|duel\|team\|coop\|endless` | Skip the menus and start a match |
| `--chaos`, `--lives` | Turn on these modifiers for `--mode` |
| `--quality low` | Force Low Quality for this run |
| `--lang he` | Start in Hebrew |

## Building the Windows .exe and installer

```bash
pip install -r requirements.txt
python build.py
```

| Output | What it is |
|---|---|
| `dist\NeonGrid\NeonGrid.exe` | Standalone game folder built by PyInstaller. Zip this folder or run it directly. |
| `installer\NeonGrid-Setup-1.0.0.exe` | Windows installer. Built only if **Inno Setup 6** is installed ([download](https://jrsoftware.org/isdl.php)). |

Options: `--onefile` builds one self-extracting exe, `--no-installer` skips Inno Setup, and
`--clean` wipes `build/` and `dist/` first. If `build.py` can't find Inno Setup, you can
compile `setup.iss` yourself with `ISCC.exe /DAppVersion=1.0.0 setup.iss`.

The script also regenerates `assets\icon.ico` (`tools/make_icon.py`) and the announcer
voice lines (`tools/gen_voice.ps1`, which uses the Windows speech synthesizer) when they
are missing.

---

## Controls (rebindable in Settings > Controls)

| Action | Default |
|---|---|
| Move | W A S D |
| Jump | Space |
| Sprint | Left Shift |
| Crouch, or slide while sprinting | Left Ctrl |
| Fire / Aim (zoom on scoped weapons) | Left / Right mouse |
| Reload | R |
| Primary / Secondary / Melee | 1 / 2 / 3 (mouse wheel cycles) |
| Quick melee | V |
| Ability 1 / Ability 2 | Q / E |
| Scoreboard | Tab |
| Pause | Esc |
| **Hidden debug menu** | **Ctrl + Shift + F10** |

## Game modes

- **Free For All.** The main mode. Timed and/or score-limited, with respawns, a kill feed
  and a scoreboard. Bots fill the empty slots (1–7).
- **1v1 vs Bot.** Easy, Normal, Hard or Nightmare. Difficulty changes the bot's reaction time, aim
  error, turn speed, tracking and tactics. It never changes the bot's stats.
- **Team Battle.** 4v4: you and 3 AI wingmen against a bot squad.
- **Co-op Survival.** You and 2 AI wingmen against endless waves of bots and hunter
  drones. Fallen teammates return between waves.
- **Endless Survival.** Solo waves that get harder. Your best wave is saved as a high
  score.
- **Difficulty pays coins (every offline mode):** Easy 0.5x, Normal 1x, Hard 2x, Nightmare
  2.5x. In Co-op and Endless, the chosen difficulty shifts the whole enemy ramp.
- **Modifiers (any mode):** **Lives** (limited lives, last one standing wins) and
  **Chaos** (sweeping lasers, proximity mines, low-gravity lift zones).
- **Multiplayer:** see below.
- **Match briefing:** when a match starts (offline START or the host's START MATCH), a
  panel shows the mode, the map, the objective (score and time limits, lives, chaos) and a
  "where to go" tip for that map while the countdown runs.
- **Story:** the menu button calls a clean plug-in hook (`game/story/__init__.py`). Ship a
  `neongrid_story` package with `launch(app)` and it takes over. Until then the button
  shows a "coming soon" panel.

## Maps

Pick the map under **Play → Match options → MAP** (or RANDOM). Online, the host changes it
with the **MAP** button in the lobby.

- **The Grid.** The neon arena: centre platform, catwalks reached by jump pads, sliding
  walls, a wet reflective floor and the day/night neon cycle.
- **Forest.** Open woods in daylight that slowly turns to dusk (fireflies come out). A log
  cabin with a rooftop deck and two wooden watchtowers, both reached by jump pads. Boulders,
  fallen logs, a campfire and dozens of trees. Bushes have no collision, so you can crouch
  inside them to hide.
- **Backrooms.** An 8 x 8 maze of yellow-wallpapered office rooms under a low ceiling of
  buzzing, sometimes flickering fluorescent lights. The rooms are full of junk: parked police
  cars with flashing light bars, dining tables and chairs, office desks with CRT monitors,
  filing cabinets, couches and TVs, vending machines, arcade cabinets, traffic cones,
  barrels, shopping carts, a phone booth and a giant rubber duck.

All maps are generated from fixed seeds (`neon_shared/maps/`), so every player and the
server build exactly the same collision.

## Weapons, abilities and progression

- **20 guns**: 3 pistols, 3 SMGs, 4 rifles, 3 shotguns, 2 snipers, 3 plasma projectile
  weapons, and 2 rail weapons that fire short, piercing laser pulses.
- **10 melee weapons**: katana, shock baton, plasma axe, mono knife (backstab), laser
  whip, grav hammer (knockback), twin claws, photon spear, pulse fist and chain blade.
- **5 upgrade tiers per weapon.** Each tier is a small trade-off, for example +6% damage
  for +6% spread. Tiers unlock from weapon XP (damage and kills you deal with that weapon)
  or from battle-pass Upgrade Chips. You can pick any unlocked tier in the Loadout screen.
- **10 abilities.** You equip 2. Each costs energy and has a cooldown: Aegis Shield,
  Phase Dash, Scan Pulse, Holo Decoy, Heal Burst, Overdrive, Jump Jets, EMP Blast, Optic
  Cloak and Gravity Well.
- **Coin shop.** Weapons, melee weapons, abilities and upgrade tiers are bought with
  coins in the Loadout screen. The starter kit (AR-7, VX-9, Neon Katana, Phase Dash, Aegis
  Shield) is free. Weapons cost 300–1800, abilities 500–1200, and tiers 250–1400 each.
  Prices are in `game/progression/shop.py`.
- **Earning coins.** In a match, coins come from kills: 12 per elimination (+5 for a
  headshot), the coin orbs enemies drop, and 15 per drone or turret destroyed. Daily
  challenges, achievements and the battle pass also pay coins. Loot crates refill ammo,
  and charging ports refill energy after 3 seconds.
- **Shop** (main menu, or the SHOP button in Loadout). Its tabs are Weapons, Melee,
  Abilities, Attachments, Upgrades (buy the next tier for each owned weapon, with a
  shortcut to Edit Weapon), Boosts and Cosmetics. **Boosts** are consumables that last 3
  matches each:
  - Double XP (400 ¢).
  - Coin Rush, +50% coins (500 ¢).
  - Spawn Shield, 40 HP on every spawn (300 ¢).
  - Ammo Surplus, +50% spare ammo (250 ¢).

  One use of each active boost is spent per finished offline match.
- **Weapon mods (Edit Weapon).** Click **Loadout → EDIT WEAPON** on any owned gun. Each gun has 5
  attachment slots, and each attachment is a small trade-off:

  | Slot | Attachments |
  |---|---|
  | Optic | Red Dot, Holo (own ADS reticles), 2.5x Scope, 8x Sniper Scope (real picture-in-picture scopes) |
  | Muzzle | **Suppressor** (quiet shots and a tiny flash; bots only hear you within 7 m instead of 38 m), Compensator, Tight Choke (shotguns), Flash Hider |
  | Magazine | Extended Mag, Fast Mag |
  | Underbarrel | Vertical Grip, Angled Grip, **Laser Sight** (tighter hip fire, visible beam) |
  | Stock | Light Stock, Heavy Stock |

  You buy an attachment once with coins (300–900) and can then fit it to any compatible
  gun. Attachments show up on the first-person weapon. The multiplayer server validates
  fitted mods and uses the modded stats for its fire-rate and magazine checks.
- **Battle pass.** Season 1 has 50 tiers driven by XP. The free track and the premium
  track hold weapon skins, suits, titles, coins and Upgrade Chips. The premium track is
  unlocked with in-game coins. **There are no real-money purchases.**
- **Real scopes.** When you aim with a scope (sniper rifles, the Longbow, or the 2.5x and 8x
  optics), the gun comes up to your eye and a second camera renders the magnified arena
  into the scope lens, with a reticle. You still see the gun and the arena around it. If
  the GPU can't create the extra buffer, the game falls back to a flat scope overlay.
- **Also:** 20 achievements, 3 daily challenges, a stats page, high scores and a Locker
  for equipping or buying cosmetics with coins.

## Threats

Every threat warns you before it attacks:

| Threat | Warning | Attack |
|---|---|---|
| Wall turrets | Red laser sight and a beep that speeds up (1.2 s), plus **TURRET LOCK** on the HUD with a direction arrow | 5-round burst |
| Hunter drones | Glow and a charging whine (0.9 s), plus **DRONE CHARGING** on the HUD | Plasma bolt |
| Grenade traps | Colored floor ring and a floating icon (2 s) | Explosive (red), flashbang (white) or fire bomb (orange) |
| Sliding walls | Hazard stripes flash before and during each move | — |
| Chaos lasers | The beam blinks yellow before it switches between jump height and slide height | — |

## Multiplayer

The host creates a **4-letter room code**. Friends can join with that code, or open
**Multiplayer → FIND ROOMS**. The room finder lists every open room on your local network
(found automatically) and on the relay server, with host, player count, lobby or in-match
status, map and ping. Click JOIN on any room; no code needed. The list refreshes every
3 seconds. If the relay server can't be reached, **Host Online** hosts the room on your own
PC instead.

- **Online:** run the relay server (`server/relay_server.py`, standard library only) on
  any cheap VPS. Everyone enters `ip:port` under Multiplayer > Relay server. Setup,
  systemd and Docker instructions are in [server/README.md](server/README.md).
- **LAN fallback:** *Host LAN* runs the same server inside the game and broadcasts the
  room code over UDP. *Join LAN* finds it without typing an IP. Windows Firewall may ask
  to allow NEON GRID on private networks the first time.
- **Server-authoritative:** the server owns health, damage, kills and the clock.
  - It re-traces hitscan shots against lag-compensated positions and checks reported
    projectile hits.
  - It checks fire rate, magazine size, weapon ownership, shot origin and pellet spread.
  - A speed limit on movement allows dashes, slides and jump pads but snaps speed-hackers
    back. Players who keep breaking the rules are kicked.

### Playing with friends in other houses

Home routers block incoming connections, so players in different houses need a **relay server**
on the internet. Steam games use Valve's relays for the same reason. The relay is included
(`server/relay_server.py`, standard library only) and speaks raw TCP and WebSocket. The easiest
free option is **Render**: follow [server/README.md](server/README.md), then put the
`wss://...` address in `assets/config.json` and rebuild. Every installed copy then connects
automatically, with no port forwarding.

### If friends can't see or join your room

1. **Same network?** Both PCs must be on the same router or Wi-Fi. Guest Wi-Fi often isolates devices.
2. **Direct join (most reliable):** the host reads their address off the lobby screen (e.g. `192.168.7.10:47777`).
   The friend types it into **SERVER / HOST IP**, types the room code, and presses **JOIN ONLINE**.
3. **Firewall:** reinstall with the **"Allow NEON GRID through Windows Firewall"** option ticked
   on *both* PCs, or click **Allow** when Windows asks.
4. **Discovery:** the room finder listens for room announcements, which are sent to every network
   adapter because VPN and VM adapters can swallow broadcasts. It also scans the local /24
   network for hosts, so it still works where broadcasts are blocked.

## Audio

The music is an adaptive synthwave track split into 4 layers (pad, bass, drums, arp).
Combat intensity fades the layers in and out. Sound effects are punchy and positional
(OpenAL 3D). The robotic announcer is optional. Master, Music, Effects and Voice each have
a volume slider.

## Graphics and performance

- **High quality.**
  - Up to 8 dynamic point lights, rim lighting and fog.
  - A mirrored scene shows through a wet, puddled floor shader.
  - HDR bloom (bright pass plus two blur levels), ACES tone mapping and FXAA.
  - Volumetric-looking light cones and flickering holograms.
  - The neon hue and brightness drift slowly over each match, day/night style, but stay
    black and cyan.
- **Low quality** turns off reflections, light cones and bloom, uses 4 lights, and uses
  about 35% of the particles. Switching bloom on or off takes effect after a restart.
- Particles are simulated with numpy and drawn as point sprites (one draw call per system).
  Static geometry is batched into a few meshes. Offscreen test runs on the development PC
  held 170–400 FPS.

## HUD and UI

- **Minimal HUD:** health and shield, energy, ammo with reload bar and tier pips, ability
  cooldowns, a crosshair, hit markers, kill feed, match info, pickup notices and
  damage-direction arcs. There is no minimap or radar.
- **Crosshair editor** (Settings → Gameplay, with a live preview): 9 styles (Classic,
  Circle, Dot, Cross, T-Shape, X, Chevron, Ring, Static Plus), 8 colors, size, thickness,
  center gap, outline on/off and dynamic spread on/off. Red Dot and Holo optics swap in
  their own reticle while you aim down sights.
- **Customizable:** Settings > HUD has per-element toggles and global scale and opacity.
  **Edit HUD Layout** lets you drag elements, resize them with the mouse wheel, and
  right-click to hide or show them.
- **English and Hebrew.** Hebrew switches to a mirrored right-to-left layout with correct
  bidirectional text. Game text is drawn through a small custom bidi routine, because
  Panda3D renders glyphs left-to-right only.

## Saved data

Everything is saved as JSON in `%APPDATA%\NeonGrid\`:

| File | Contents |
|---|---|
| `settings.json` | Video, audio, controls and bindings, gameplay, HUD layout, language, network |
| `profile.json` | XP, coins, battle pass, loadout, weapon XP and tiers, skins, achievements, challenges |
| `stats.json` | Lifetime statistics |
| `highscores.json` | Best waves, kills and duel wins |
| `logs\neongrid.log`, `logs\crash_*.log`, `crash.log` | Session log and crash reports |

Files are written atomically. If a file is corrupt, the game moves it aside and uses the
defaults instead of crashing. If a match raises an error, the game writes a crash log and
returns to the menu instead of closing.

## Project layout

```
main.py                 entry point, CLI flags, fatal-error dialog
build.py / setup.iss    PyInstaller + Inno Setup packaging
neon_shared/            pure-Python data shared with the server: weapons, abilities,
                        arena layout, hit math, protocol, authoritative server core
server/                 relay server launcher, Dockerfile, systemd unit
game/
  app.py                window, subsystems, state machine, crash-safe main loop
  match.py, modes.py    combat rules and all game modes
  entities/             combatant, movement, player controller, bot AI, nav graph, models
  combat/               weapon state, firing and hit resolution, projectiles,
                        abilities, view-model
  world/                collision, arena visuals, loot/ports/pads/sliding walls, hazards
  gfx/                  shaders, bloom, lighting and day/night cycle, particles, effects
  audio/                numpy synthesizer (SFX and music stems), playback manager
  ui/                   HUD, menus, widgets, theme, debug menu
  progression/          battle pass, skins, achievements and challenges, rewards
  net/                  multiplayer session, LAN discovery
  story/                story-mode hook
tests/                  server protocol test and the scripted network bot
tools/                  icon and voice generators
```

## Development and testing

```bash
python tests/test_server.py                         # server: hits, headshots, kills, anti-cheat
python main.py --autotest ffa --autoplay --offscreen --duration 30 --shots out/
python main.py --autotest endless --autoplay --offscreen --chaos
python main.py --nettest --autoplay --offscreen     # LAN end to end: host + scripted net bot
python main.py --menutest --offscreen --shots out/  # screenshots of every menu in EN and HE
python main.py --autotest duel --fxtest --offscreen --shots out/   # explosion showcase
```

Test runs never write to your save files.
