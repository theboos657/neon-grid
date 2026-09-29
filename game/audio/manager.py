"""Audio playback: pooled positional SFX, adaptive music stems, announcer.

* 3D sounds use OpenAL through Panda's sfx manager with the camera as the
  listener; each sound name owns a small round-robin pool of voices so rapid
  fire never cuts itself off.
* The soundtrack is four synchronised loops.  ``intensity`` (0..1, driven by
  combat events) fades layers in: pad -> bass -> drums -> arp.
"""

import logging
import os

from panda3d.core import Filename

from .. import paths
from . import synth

log = logging.getLogger("audio")

POOL = {"default": 3, "step": 6, "smg": 8, "energy_smg": 8, "rifle": 6, "lmg": 6, "pistol": 5,
        "photon": 8, "hitmarker": 4, "turret_fire": 6, "explosion": 4, "beep": 4, "plasma": 5,
        "ricochet": 4, "shotgun": 4, "melee_swing": 4}
STEM_ORDER = ["music_pad", "music_bass", "music_drums", "music_arp"]
# (intensity at which the layer starts, full) - pad always plays
STEM_RAMP = {"music_pad": (-1, 0), "music_bass": (0.12, 0.3), "music_drums": (0.3, 0.5),
             "music_arp": (0.55, 0.8)}
MAX_DIST = 70.0


class AudioManager:
    def __init__(self, base, settings):
        self.base = base
        self.settings = settings
        self.mgr = base.sfxManagerList[0] if base.sfxManagerList else None
        self.music_mgr = base.musicManager
        self.ok = self.mgr is not None and self.mgr.isValid()
        self.sounds = {}
        self.cursor = {}
        self.stems = {}
        self.stem_vol = {k: 0.0 for k in STEM_ORDER}
        self.music_on = False
        self.intensity = 0.0
        self.intensity_target = 0.0
        self.menu_music = True
        self.listener_pos = (0, 0, 0)
        self.cache = paths.cache_dir("audio_v%d" % synth.VERSION)
        self.vo_dir = paths.cache_dir("voice_v%d" % synth.VERSION)
        self.announcer_queue = []
        self.announcer_busy = 0.0
        if self.ok:
            self.mgr.audio3dSetDistanceFactor(1.0)
            self.mgr.audio3dSetDopplerFactor(0.0)
            self.mgr.audio3dSetDropOffFactor(0.6)
            self.mgr.setConcurrentSoundLimit(48)
        if self.music_mgr is not None:
            self.music_mgr.setConcurrentSoundLimit(0)

    # ------------------------------------------------------------------ setup
    def generate(self, progress=None):
        """Synthesise all audio into the cache (first run only)."""
        try:
            synth.generate_all(self.cache, progress)
            synth.process_voice(paths.asset("voice"), self.vo_dir)
        except Exception:
            log.exception("Audio generation failed")

    def load(self):
        if not self.ok:
            log.warning("No audio device; running silent")
            return
        for fn in os.listdir(self.cache):
            if fn.endswith(".wav") and not fn.startswith("music_"):
                self._load_pool(fn[:-4], os.path.join(self.cache, fn))
        if os.path.isdir(self.vo_dir):
            for fn in os.listdir(self.vo_dir):
                if fn.endswith(".wav"):
                    self._load_pool(fn[:-4], os.path.join(self.vo_dir, fn), 1)
        for stem in STEM_ORDER:
            p = os.path.join(self.cache, stem + ".wav")
            if os.path.exists(p) and self.music_mgr is not None:
                s = self.music_mgr.getSound(Filename.fromOsSpecific(p), False)
                s.setLoop(True)
                s.setVolume(0.0)
                self.stems[stem] = s

    def _load_pool(self, name, path, count=None):
        n = count or POOL.get(name, POOL["default"])
        fn = Filename.fromOsSpecific(path)
        pool = []
        for _ in range(n):
            s = self.mgr.getSound(fn, True)
            if s is None:
                break
            s.set3dMinDistance(4.0)
            s.set3dMaxDistance(200.0)
            pool.append(s)
        if pool:
            self.sounds[name] = pool
            self.cursor[name] = 0

    # ------------------------------------------------------------------ volumes
    def _vol(self, cat):
        a = self.settings["audio"]
        return a["master"] * a.get(cat, 1.0)

    # ------------------------------------------------------------------ playback
    def _next(self, name):
        pool = self.sounds.get(name)
        if not pool:
            return None
        i = self.cursor[name]
        self.cursor[name] = (i + 1) % len(pool)
        return pool[i]

    def play2d(self, name, volume=1.0, rate=1.0, cat="effects"):
        s = self._next(name)
        if s is None:
            return
        lx, ly, lz = self.listener_pos
        s.set3dAttributes(lx, ly, lz, 0, 0, 0)
        s.setVolume(volume * self._vol(cat))
        s.setPlayRate(rate)
        s.play()

    def play3d(self, name, pos, volume=1.0, source=None, rate=1.0):
        """Positional sound.  If ``source`` is the local player it plays 2D."""
        if source is not None and getattr(source, "is_player", False):
            self.play2d(name, volume, rate)
            return
        lx, ly, lz = self.listener_pos
        dx, dy, dz = pos[0] - lx, pos[1] - ly, pos[2] - lz
        if dx * dx + dy * dy + dz * dz > MAX_DIST * MAX_DIST:
            return
        s = self._next(name)
        if s is None:
            return
        s.set3dAttributes(pos[0], pos[1], pos[2], 0, 0, 0)
        s.setVolume(volume * self._vol("effects"))
        s.setPlayRate(rate)
        s.play()

    def play_weapon(self, sfx, pos, shooter, quiet=False):
        import random
        rate = random.uniform(0.94, 1.06)
        vol = 0.55 if quiet else 1.0
        if getattr(shooter, "is_player", False):
            self.play2d(sfx, 0.85 * vol, rate)
        else:
            self.play3d(sfx, pos, vol, rate=rate)
        self.bump(0.02 if quiet else 0.06)

    def ui(self, name):
        self.play2d(name, 1.0)

    def announce(self, key, caption_cb=None):
        """Queue an announcer line (voice volume, optional toggle)."""
        if not self.settings["audio"].get("announcer", True):
            return
        self.announcer_queue.append(key)
        if len(self.announcer_queue) > 3:
            self.announcer_queue.pop(0)

    # ------------------------------------------------------------------ music
    def start_music(self, menu=True):
        self.menu_music = menu
        if not self.stems or self.music_on:
            return
        for s in self.stems.values():
            s.setVolume(0.0)
            s.play()
        self.music_on = True

    def stop_music(self):
        for s in self.stems.values():
            s.stop()
        self.music_on = False

    def bump(self, amount):
        """Raise combat intensity (decays automatically)."""
        self.intensity_target = min(1.0, self.intensity_target + amount)

    def set_floor_intensity(self, v):
        self.floor_intensity = v

    floor_intensity = 0.0

    def update(self, dt, cam=None):
        if not self.ok:
            return
        if cam is not None:
            p = cam.getPos(self.base.render)
            q = cam.getQuat(self.base.render)
            f = q.getForward()
            u = q.getUp()
            self.listener_pos = (p.x, p.y, p.z)
            self.mgr.audio3dSetListenerAttributes(p.x, p.y, p.z, 0, 0, 0, f.x, f.y, f.z,
                                                  u.x, u.y, u.z)
        # announcer
        if self.announcer_busy > 0:
            self.announcer_busy -= dt
        elif self.announcer_queue:
            key = self.announcer_queue.pop(0)
            name = "vo_" + key
            if name in self.sounds:
                s = self.sounds[name][0]
                lx, ly, lz = self.listener_pos
                s.set3dAttributes(lx, ly, lz, 0, 0, 0)
                s.setVolume(self._vol("voice") * 1.2)
                s.play()
                self.announcer_busy = s.length() * 0.9
        # adaptive music
        self.intensity_target = max(self.floor_intensity, self.intensity_target - dt * 0.06)
        k = min(1.0, dt * (1.5 if self.intensity_target > self.intensity else 0.4))
        self.intensity += (self.intensity_target - self.intensity) * k
        if self.music_on:
            mv = self._vol("music")
            inten = 0.45 if self.menu_music else self.intensity
            for name, s in self.stems.items():
                lo, hi = STEM_RAMP[name]
                if self.menu_music and name in ("music_drums",):
                    target = 0.0
                elif lo < 0:
                    target = 1.0
                else:
                    target = max(0.0, min(1.0, (inten - lo) / max(0.01, hi - lo)))
                if name == "music_arp" and self.menu_music:
                    target = 0.55
                cur = self.stem_vol[name]
                cur += (target - cur) * min(1.0, dt * 1.2)
                self.stem_vol[name] = cur
                s.setVolume(cur * mv * 0.8)
