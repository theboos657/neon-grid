"""Offline synthesis of every sound in the game (numpy only).

Style: punchy, bass-heavy synth weapons over an 110 BPM A-minor synthwave
soundtrack split into four loopable stems (pad, bass, drums, arp) so the
music can react to the action by fading layers in and out.

Results are written as 16-bit mono WAVs to the AppData cache the first time
the game runs (about 2-4 seconds), then simply loaded on later launches.
"""

import os
import wave

import numpy as np

SR = 44100
VERSION = 5          # bump to regenerate cached audio after changing recipes
rng = np.random.default_rng(7)


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------
def T(dur):
    return np.arange(int(dur * SR)) / SR


def noise(dur):
    return rng.uniform(-1, 1, int(dur * SR))


def env(dur, attack=0.002, decay=10.0):
    t = T(dur)
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t * decay)


def glide(f0, f1, dur, curve=3.0):
    t = T(dur)
    k = 1 - np.exp(-t * curve / dur) if curve else t / dur
    k = k / (k[-1] if len(k) and k[-1] != 0 else 1)
    return f0 + (f1 - f0) * k


def osc(freq, dur, shape="sine"):
    n = int(dur * SR)
    f = np.broadcast_to(np.asarray(freq, float), (n,)) if np.ndim(freq) == 0 else freq[:n]
    ph = np.cumsum(f) / SR
    if shape == "sine":
        return np.sin(2 * np.pi * ph)
    if shape == "saw":
        return 2 * (ph % 1.0) - 1
    if shape == "square":
        return np.sign(np.sin(2 * np.pi * ph))
    if shape == "tri":
        return 2 * np.abs(2 * (ph % 1.0) - 1) - 1
    raise ValueError(shape)


def lowpass(x, fc, order=2):
    if len(x) == 0:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    H = 1 / np.sqrt(1 + (f / max(fc, 1)) ** (2 * order))
    return np.fft.irfft(X * H, len(x))


def highpass(x, fc, order=2):
    if len(x) == 0:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    H = 1 / np.sqrt(1 + (max(fc, 1) / np.maximum(f, 1e-3)) ** (2 * order))
    return np.fft.irfft(X * H, len(x))


def bandpass(x, lo, hi):
    return highpass(lowpass(x, hi), lo)


def pad(x, dur):
    n = int(dur * SR)
    if len(x) >= n:
        return x[:n]
    return np.concatenate([x, np.zeros(n - len(x))])


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def reverb(x, decay=1.5, wet=0.3, circular=False, tail=None):
    """Convolution with decaying filtered noise.  ``circular`` wraps the tail
    around (perfect for seamless music loops)."""
    ir_len = int(min(decay * 1.2, 3.0) * SR)
    ir = rng.uniform(-1, 1, ir_len) * np.exp(-np.arange(ir_len) / SR * (6.9 / decay))
    ir = lowpass(ir, 5000)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    if circular:
        n = len(x)
        irp = np.zeros(n)
        irp[:min(n, ir_len)] = ir[:min(n, ir_len)]
        w = np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(irp), n)
        return x * (1 - wet) + w * wet
    if tail is None:
        tail = decay
    n = len(x) + int(tail * SR)
    nfft = 1 << int(np.ceil(np.log2(n + ir_len)))
    w = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[:n]
    return mix(x * (1 - wet), w * wet)


def dist(x, drive=2.0):
    return np.tanh(x * drive) / np.tanh(drive)


def norm(x, peak=0.9):
    m = np.max(np.abs(x)) if len(x) else 0
    return x * (peak / m) if m > 1e-9 else x


def fade_out(x, dur=0.02):
    n = min(len(x), int(dur * SR))
    if n > 0:
        x = x.copy()
        x[-n:] *= np.linspace(1, 0, n)
    return x


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    data = (x * 32767).astype("<i2").tobytes()
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data)
    os.replace(tmp, path)


def read_wav(path):
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        raw = w.readframes(n)
    if sw != 2:
        return None, sr
    x = np.frombuffer(raw, "<i2").astype(float) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def resample(x, sr_from, sr_to=SR):
    if sr_from == sr_to:
        return x
    n = int(len(x) * sr_to / sr_from)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


# ---------------------------------------------------------------------------
# weapon & impact sounds
# ---------------------------------------------------------------------------
def thump(f0, f1, dur, decay):
    return osc(glide(f0, f1, dur, 6), dur) * env(dur, 0.001, decay)


def gun(crack=0.8, body=0.7, f0=180, f1=55, dur=0.4, tail=0.6, bright=7000, rev=0.25):
    n = noise(dur) * env(dur, 0.0005, 45)
    n = lowpass(n, bright) * crack
    b = thump(f0, f1, dur, 16) * body
    click = noise(0.01) * 0.6
    x = mix(n, b, click)
    x = dist(x, 2.5)
    x = mix(x, lowpass(noise(dur) * env(dur, 0.001, 9), 1200) * 0.25 * tail)
    x = reverb(x, 0.8, rev, tail=0.4)
    return fade_out(norm(x))


def laser(f0, f1, dur, shape="saw", decay=12.0, bright=6000, zap=0.4):
    x = osc(glide(f0, f1, dur, 5), dur, shape) * env(dur, 0.001, decay)
    x = lowpass(x, bright)
    z = highpass(noise(dur), 3000) * env(dur, 0.0005, 60) * zap
    return fade_out(norm(dist(mix(x, z), 1.8)))


def build_sfx():
    s = {}
    s["pistol"] = gun(0.9, 0.7, 220, 70, 0.35, 0.5, 8000)
    s["heavy_pistol"] = gun(1.0, 1.0, 160, 45, 0.55, 0.9, 6000, 0.3)
    s["smg"] = gun(0.8, 0.5, 260, 90, 0.18, 0.3, 9000, 0.15)
    s["energy_smg"] = norm(mix(laser(1400, 500, 0.12, "square", 35, 5000, 0.3) * 0.6,
                               gun(0.4, 0.4, 240, 90, 0.12, 0.2, 6000, 0.1) * 0.6))
    s["rifle"] = gun(0.9, 0.8, 200, 55, 0.32, 0.7, 7500, 0.22)
    s["dmr"] = gun(1.0, 1.0, 170, 45, 0.6, 1.0, 9000, 0.35)
    s["lmg"] = gun(0.9, 0.9, 170, 50, 0.3, 0.8, 6000, 0.2)
    shot = gun(1.0, 1.0, 120, 38, 0.8, 1.4, 3500, 0.35)
    s["shotgun"] = shot
    s["energy_shotgun"] = norm(mix(shot * 0.7, laser(2400, 300, 0.35, "saw", 14, 7000, 0.6) * 0.5))
    crack = highpass(noise(0.04), 2500) * env(0.04, 0.0003, 80)
    boom = thump(110, 32, 1.4, 5)
    sn = reverb(dist(mix(crack * 1.2, boom, lowpass(noise(1.4) * env(1.4, 0.001, 4), 900) * 0.4),
                     2), 2.2, 0.35)
    s["sniper"] = fade_out(norm(sn))
    s["plasma"] = norm(mix(laser(1300, 180, 0.3, "sine", 10, 5000, 0.2),
                           osc(glide(2600, 400, 0.3), 0.3, "tri") * env(0.3, 0.001, 18) * 0.3))
    s["nova"] = norm(reverb(mix(laser(320, 55, 0.7, "saw", 5, 1800, 0.6),
                                thump(90, 35, 0.7, 5)), 1.2, 0.3))
    s["photon"] = laser(2000, 700, 0.12, "square", 30, 6000, 0.2)
    # rail: charge-snap + zap
    chirp = osc(glide(500, 4000, 0.05, 0), 0.05, "saw") * np.linspace(0.2, 1, int(0.05 * SR))
    zap = osc(glide(900, 120, 0.7, 4), 0.7, "saw") * env(0.7, 0.001, 7)
    zap = lowpass(zap, 4000)
    crackle = highpass(noise(0.7), 2000) * env(0.7, 0.001, 9) * (rng.random(int(0.7 * SR)) > 0.7)
    rail = mix(chirp * 0.6, np.concatenate([np.zeros(int(0.03 * SR)), zap]), crackle * 0.5,
               thump(140, 40, 0.5, 8) * 0.8)
    s["rail"] = fade_out(norm(reverb(dist(rail, 2.5), 1.5, 0.3)))
    s["rail_light"] = fade_out(norm(reverb(dist(mix(chirp[:1200] * 0.5,
                                                    laser(1400, 300, 0.3, "saw", 12, 5000, 0.5)),
                                                2.0), 0.8, 0.2)))
    # suppressed shot: soft thump + airy "pfft", almost no crack
    pf = bandpass(noise(0.18), 900, 5000) * env(0.18, 0.0008, 38) * 0.6
    s["suppressed"] = fade_out(norm(mix(pf, thump(160, 70, 0.15, 30) * 0.7,
                                        highpass(noise(0.03), 4000) * env(0.03, 0.0003, 120) * 0.3)))
    s["ricochet"] = norm(osc(glide(2600, 900, 0.3, 2), 0.3) * env(0.3, 0.001, 9) * 0.6 +
                         pad(highpass(noise(0.05), 3000) * env(0.05, 0.0003, 60), 0.3))
    s["plasma_hit"] = norm(mix(highpass(noise(0.25), 2500) * env(0.25, 0.001, 18),
                               thump(300, 80, 0.2, 18) * 0.6))
    # melee
    wn = bandpass(noise(0.3), 400, 3500) * np.sin(np.linspace(0, np.pi, int(0.3 * SR))) ** 2
    s["melee_swing"] = norm(wn)
    ring = sum(osc(f, 0.5) * env(0.5, 0.001, d) * a for f, d, a in
               ((830, 10, 0.5), (1370, 14, 0.35), (2210, 20, 0.2)))
    s["melee_hit"] = norm(mix(thump(160, 50, 0.4, 14), ring * 0.6, noise(0.03) * 0.5))
    # feedback
    s["hitmarker"] = norm(osc(3200, 0.05, "tri") * env(0.05, 0.0005, 70))
    s["headshot"] = norm(mix(osc(1760, 0.4) * env(0.4, 0.001, 10), osc(2640, 0.4) *
                             env(0.4, 0.001, 12) * 0.6, s["hitmarker"] * 0.5))
    s["kill"] = norm(np.concatenate([osc(880, 0.07, "square") * env(0.07, 0.001, 20),
                                     osc(1320, 0.18, "square") * env(0.18, 0.001, 12)]) * 0.5)
    click = highpass(noise(0.015), 2000) * env(0.015, 0.0002, 200)
    s["empty"] = norm(pad(click, 0.08))
    rl = np.zeros(int(0.5 * SR))
    for at, a in ((0.0, 0.8), (0.22, 1.0), (0.3, 0.6)):
        i = int(at * SR)
        rl[i:i + len(click)] += click * a
    rl += pad(bandpass(noise(0.2), 800, 3000) * env(0.2, 0.05, 12) * 0.15, 0.5)
    s["reload"] = norm(rl)
    s["switch"] = norm(mix(pad(click, 0.15), bandpass(noise(0.15), 500, 2500) * env(0.15, 0.01, 25) * 0.4))
    # movement
    s["step"] = norm(lowpass(noise(0.12), 700) * env(0.12, 0.002, 40) +
                     thump(90, 50, 0.12, 30) * 0.5) * 0.8
    s["jump"] = norm(bandpass(noise(0.2), 300, 2000) * env(0.2, 0.02, 14)) * 0.6
    s["land"] = norm(mix(thump(110, 40, 0.3, 18), lowpass(noise(0.2), 900) * env(0.2, 0.001, 25)))
    s["slide"] = norm(bandpass(noise(0.7), 300, 3000) * env(0.7, 0.03, 4))
    # explosions
    def explosion(dur=2.0, size=1.0):
        n1 = noise(dur)
        low = lowpass(n1, 600 * size) * env(dur, 0.002, 2.5 / size)
        mid = lowpass(n1, 3000) * env(dur, 0.001, 8)
        sub = thump(70, 28, dur, 2.5) * 1.4
        crack = highpass(noise(dur), 1500) * env(dur, 0.001, 5) * (rng.random(int(dur * SR)) > 0.85)
        x = mix(low * 1.2, mid * 0.5, sub, crack * 0.4)
        return fade_out(norm(reverb(dist(x, 3.0), 2.0, 0.3)))
    s["explosion"] = explosion(2.2, 1.0)
    s["explosion_small"] = explosion(1.2, 0.7)
    fb = explosion(1.0, 0.6)
    s["flashbang"] = norm(mix(fb, osc(3600, 2.5) * env(2.5, 0.01, 1.5) * 0.35))
    fire = lowpass(noise(1.4), 1500) * np.clip(T(1.4) / 0.3, 0, 1) * np.exp(-T(1.4) * 1.5)
    cr = highpass(noise(1.4), 3000) * (rng.random(int(1.4 * SR)) > 0.97) * 0.8
    s["fire_bomb"] = norm(mix(fire, cr, thump(120, 40, 0.5, 8) * 0.8))
    # hazards
    s["beep"] = norm(osc(1250, 0.07, "square") * env(0.07, 0.001, 20)) * 0.6
    s["turret_lock"] = norm(osc(glide(500, 1500, 0.45, 0), 0.45, "square") * env(0.45, 0.01, 2)) * 0.6
    s["turret_fire"] = gun(0.8, 0.6, 300, 100, 0.2, 0.3, 5000, 0.1)
    s["drone_charge"] = norm(lowpass(osc(glide(250, 2000, 0.9, 0), 0.9, "saw"), 4000) *
                             np.clip(T(0.9) / 0.1, 0, 1)) * 0.7
    s["drone_shot"] = laser(900, 150, 0.35, "saw", 9, 3000, 0.5)
    mb = np.zeros(int(0.5 * SR))
    for i in range(3):
        b = osc(1800, 0.06, "square") * env(0.06, 0.001, 30)
        j = int(i * 0.14 * SR)
        mb[j:j + len(b)] += b
    s["mine_beep"] = norm(mb) * 0.7
    al = np.concatenate([osc(880, 0.15, "square"), osc(660, 0.15, "square"),
                         osc(880, 0.15, "square"), osc(660, 0.15, "square")])
    s["trap_warn"] = norm(lowpass(al, 3000) * 0.5)
    rumble = lowpass(noise(1.6), 200) * np.sin(np.linspace(0, np.pi, int(1.6 * SR)))
    servo = osc(glide(180, 260, 1.6, 0), 1.6, "saw") * 0.15 * np.sin(np.linspace(0, np.pi, int(1.6 * SR)))
    s["wall_slide"] = norm(mix(rumble, lowpass(servo, 1200)))
    s["jumppad"] = norm(mix(osc(glide(90, 500, 0.4, 3), 0.4) * env(0.4, 0.005, 6),
                            bandpass(noise(0.4), 500, 4000) * env(0.4, 0.01, 8) * 0.5))
    # pickups & abilities
    def arp(notes, step=0.06, shape="square", decay=18):
        out = np.zeros(int((len(notes) * step + 0.3) * SR))
        for i, f in enumerate(notes):
            b = osc(f, 0.3, shape) * env(0.3, 0.001, decay)
            j = int(i * step * SR)
            out[j:j + len(b)] += b
        return norm(lowpass(out, 5000))
    s["pickup"] = arp([880, 1109, 1319, 1760]) * 0.6
    s["coin"] = arp([1319, 1976], 0.05, "tri") * 0.6
    s["energy_full"] = norm(reverb(arp([440, 554, 659, 880, 1109], 0.05, "saw", 8), 1.0, 0.3))
    s["shield"] = norm(reverb(mix(osc(glide(200, 800, 0.5), 0.5, "saw") * env(0.5, 0.05, 5),
                                  osc(glide(300, 1200, 0.5), 0.5, "sine") * env(0.5, 0.05, 5)), 1.0, 0.3))
    s["dash"] = norm(bandpass(noise(0.3), 600, 6000) * env(0.3, 0.005, 10) +
                     osc(glide(300, 1500, 0.3), 0.3) * env(0.3, 0.001, 14) * 0.4)
    ping = osc(1500, 1.2) * env(1.2, 0.001, 6)
    s["scan"] = norm(reverb(mix(ping, osc(750, 1.2) * env(1.2, 0.001, 6) * 0.5), 2.0, 0.5))
    gl = osc(glide(400, 1600, 0.4, 0), 0.4, "square") * (rng.random(int(0.4 * SR)) > 0.3)
    s["decoy"] = norm(lowpass(gl, 5000) * env(0.4, 0.01, 6))
    s["heal"] = norm(reverb(arp([523, 659, 784, 1047], 0.08, "tri", 6), 1.2, 0.4))
    s["speed"] = norm(osc(glide(200, 1200, 0.5), 0.5, "saw") * env(0.5, 0.01, 6) * 0.5 +
                      bandpass(noise(0.5), 1000, 6000) * env(0.5, 0.01, 6) * 0.5)
    s["jets"] = norm(lowpass(noise(0.9), 1800) * env(0.9, 0.01, 3) + thump(80, 50, 0.9, 5) * 0.4)
    s["emp"] = norm(reverb(mix(laser(3000, 60, 1.0, "saw", 4, 6000, 1.0),
                               osc(55, 1.0) * env(1.0, 0.01, 3)), 1.5, 0.35))
    shim = osc(glide(2400, 300, 0.6), 0.6, "tri") * env(0.6, 0.3, 4)
    s["cloak"] = norm(reverb(shim[::-1].copy(), 1.0, 0.4))
    s["gravity"] = norm(reverb(mix(osc(glide(300, 30, 1.2, 2), 1.2, "saw") * env(1.2, 0.02, 3),
                                   thump(60, 25, 1.2, 3)), 1.5, 0.3))
    s["ability_denied"] = norm(osc(220, 0.15, "square") * env(0.15, 0.001, 20)) * 0.5
    # UI
    s["ui_hover"] = norm(osc(2400, 0.03, "tri") * env(0.03, 0.0005, 120)) * 0.35
    s["ui_click"] = norm(mix(osc(1200, 0.08, "square") * env(0.08, 0.001, 40),
                             osc(1800, 0.08) * env(0.08, 0.001, 30) * 0.5)) * 0.5
    s["ui_back"] = norm(osc(glide(900, 500, 0.1), 0.1, "square") * env(0.1, 0.001, 30)) * 0.45
    s["countdown"] = norm(osc(880, 0.2, "square") * env(0.2, 0.001, 12)) * 0.5
    s["match_start"] = norm(reverb(mix(osc(440, 0.8, "saw"), osc(660, 0.8, "saw"),
                                       osc(880, 0.8, "saw")) * env(0.8, 0.01, 3), 1.2, 0.3))
    s["level_up"] = norm(reverb(arp([523, 659, 784, 1047, 1319, 1568], 0.07, "saw", 7), 1.5, 0.35))
    s["achievement"] = norm(reverb(arp([659, 988, 1319], 0.1, "square", 6), 1.5, 0.35))
    return s


# ---------------------------------------------------------------------------
# music (4 seamless stems)
# ---------------------------------------------------------------------------
BPM = 110
BEAT = 60.0 / BPM
BARS = 8
LOOP = BARS * 4 * BEAT
A4 = 440.0


def midi(n):
    return A4 * 2 ** ((n - 69) / 12)


# chord progression i - VI - III - VII in A minor (2 bars each)
CHORDS = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)]


def build_music():
    n = int(LOOP * SR)
    t = np.arange(n) / SR
    beat_pos = (t / BEAT) % 1.0
    side = 1 - 0.55 * np.exp(-beat_pos * BEAT * 9)     # sidechain pump
    chord_idx = ((t / (BEAT * 8)).astype(int)) % 4
    # ---- pad
    pad_ = np.zeros(n)
    for ci, ch in enumerate(CHORDS):
        mask = chord_idx == ci
        for note in ch:
            for det in (-0.08, 0.0, 0.08):
                f = midi(note + det)
                pad_ += mask * (2 * ((t * f) % 1.0) - 1) * 0.12
            pad_ += mask * np.sin(2 * np.pi * t * midi(note - 12)) * 0.15
    # smooth chord edges
    edge = np.minimum(1, np.minimum((t % (BEAT * 8)) / 0.08, (BEAT * 8 - (t % (BEAT * 8))) / 0.08))
    pad_ = lowpass(pad_ * edge, 1400) * side
    pad_ = reverb(pad_, 2.5, 0.45, circular=True)
    # ---- bass: eighth-note octave pulse
    bass = np.zeros(n)
    eighth = (t / (BEAT / 2)).astype(int)
    e_pos = (t % (BEAT / 2)) / (BEAT / 2)
    for ci, ch in enumerate(CHORDS):
        mask = chord_idx == ci
        root = ch[0] - 24
        oct_up = (eighth % 2 == 1)
        f = np.where(oct_up, midi(root + 12), midi(root))
        ph = t * f
        wave_ = (2 * (ph % 1.0) - 1) * 0.6 + np.sign(np.sin(2 * np.pi * ph)) * 0.25
        bass += mask * wave_ * np.exp(-e_pos * 3.0)
    bass = lowpass(bass, 520, 3) * side
    bass = dist(bass * 1.3, 1.5)
    # ---- drums
    drums = np.zeros(n)
    kick = mix(thump(150, 42, 0.35, 11), noise(0.005) * 0.3)
    snare_len = 0.3
    snare = lowpass(noise(snare_len), 7000) * env(snare_len, 0.001, 16) * 0.7 + \
        osc(glide(220, 160, snare_len), snare_len) * env(snare_len, 0.001, 22) * 0.5
    snare = reverb(snare, 0.8, 0.35, tail=0.3)[:int(0.45 * SR)]
    hat = highpass(noise(0.05), 7000) * env(0.05, 0.0005, 70) * 0.35
    ohat = highpass(noise(0.2), 6000) * env(0.2, 0.001, 14) * 0.25
    beats = int(round(LOOP / BEAT))

    def place(buf, sample, at):
        i = int(at * SR) % n
        L = len(sample)
        end = i + L
        if end <= n:
            buf[i:end] += sample
        else:
            buf[i:] += sample[:n - i]
            buf[:end - n] += sample[n - i:]
    for b in range(beats):
        place(drums, kick, b * BEAT)
        if b % 2 == 1:
            place(drums, snare, b * BEAT)
        place(drums, hat, b * BEAT)
        place(drums, ohat, b * BEAT + BEAT / 2)
        if b % 8 == 7:
            place(drums, hat, b * BEAT + BEAT * 0.75)
            place(drums, kick * 0.6, b * BEAT + BEAT * 0.75)
    drums = dist(drums, 1.4)
    # ---- arp: 16ths across chord tones
    arp_ = np.zeros(n)
    sixteenth = BEAT / 4
    steps = int(round(LOOP / sixteenth))
    pattern = [0, 1, 2, 1, 0, 2, 1, 2]
    pluck = int(0.18 * SR)
    for s_ in range(steps):
        at = s_ * sixteenth
        ci = int(at / (BEAT * 8)) % 4
        note = CHORDS[ci][pattern[s_ % 8]] + 12 + (12 if s_ % 16 in (6, 14) else 0)
        f = midi(note)
        tt = np.arange(pluck) / SR
        w = (np.sign(np.sin(2 * np.pi * f * tt)) * 0.5 + (2 * ((tt * f * 1.005) % 1) - 1) * 0.5)
        w *= np.exp(-tt * 14)
        place(arp_, w * 0.35, at)
    arp_ = lowpass(arp_, 3200)
    # ping-pong style delay (dotted eighth), circular
    d = int(BEAT * 0.75 * SR)
    arp_ = arp_ + np.roll(arp_, d) * 0.4 + np.roll(arp_, 2 * d) * 0.18
    arp_ = reverb(arp_, 1.5, 0.25, circular=True) * side
    stems = {"music_pad": pad_, "music_bass": bass, "music_drums": drums, "music_arp": arp_}
    return {k: norm(v, 0.85) for k, v in stems.items()}


def robotize(x, sr):
    """Announcer processing: band-limit, ring-mod shimmer, slight crush, reverb."""
    x = resample(x, sr, SR)
    x = bandpass(x, 180, 6000)
    t = np.arange(len(x)) / SR
    x = x * (0.75 + 0.25 * np.sin(2 * np.pi * 45 * t))
    x = np.round(x * 48) / 48
    x = dist(x, 1.8)
    x = reverb(x, 0.9, 0.22, tail=0.5)
    return norm(x, 0.95)


# ---------------------------------------------------------------------------
def generate_all(out_dir, progress=None):
    """Generate every WAV into ``out_dir`` (skips when the version matches)."""
    os.makedirs(out_dir, exist_ok=True)
    stamp = os.path.join(out_dir, "version.txt")
    if os.path.exists(stamp):
        try:
            if open(stamp).read().strip() == str(VERSION):
                return False
        except OSError:
            pass
    if progress:
        progress(0.05)
    sfx = build_sfx()
    for i, (name, data) in enumerate(sfx.items()):
        write_wav(os.path.join(out_dir, name + ".wav"), data)
    if progress:
        progress(0.5)
    music = build_music()
    for name, data in music.items():
        write_wav(os.path.join(out_dir, name + ".wav"), data)
    if progress:
        progress(1.0)
    with open(stamp, "w") as f:
        f.write(str(VERSION))
    return True


def process_voice(src_dir, out_dir):
    """Robotise announcer WAVs from ``src_dir`` into ``out_dir``."""
    if not os.path.isdir(src_dir):
        return 0
    os.makedirs(out_dir, exist_ok=True)
    count = 0
    for fn in os.listdir(src_dir):
        if not fn.lower().endswith(".wav"):
            continue
        dst = os.path.join(out_dir, "vo_" + fn)
        if os.path.exists(dst):
            count += 1
            continue
        x, sr = read_wav(os.path.join(src_dir, fn))
        if x is None:
            continue
        write_wav(dst, robotize(x, sr))
        count += 1
    return count
