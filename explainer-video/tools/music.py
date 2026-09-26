#!/usr/bin/env python3
"""
tools/music.py — Upbeat music bed + sound effects, synthesised offline (no samples, no licences).

Reads build/timings.json (scene layout + BPM) and, when present, build/sfx.json
(animation events exported from src/index.html by `render.cjs events`). Writes:

  build/music.wav   pop/corporate groove (default 118 BPM) arranged around the scenes:
                    a filtered build under the hook, an impact on the logo, a full groove
                    for the five steps with fills + crashes on every scene change, a lifted
                    "chorus" for the recap and a clean ending on the outro.
  build/sfx.wav     whooshes on scene changes, pops/ticks/chimes/hits synced to the visuals.

  python tools/music.py
"""

import json
import pathlib

import numpy as np
import soundfile as sf
from scipy import signal

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
SR = 48000
RNG = np.random.default_rng(7)

# Scene → arrangement section
SECTION = {
    "hook": "build", "intro": "lite", "idea": "groove", "universe": "groove", "data": "groove",
    "score": "groove", "example": "groove", "screener": "groove", "risk": "groove",
    "recap": "chorus", "outro": "end",
}
FILL_BEFORE = {"universe", "data", "score", "example", "screener", "risk", "recap"}

# vi–IV–I–V in D major, one chord per bar: (bass root, pad voicing, arp notes) as MIDI
PROG = [
    (35, [62, 66, 71], [66, 71, 74, 78]),   # Bm
    (31, [62, 67, 71], [67, 71, 74, 79]),   # G
    (38, [62, 66, 69], [66, 69, 74, 78]),   # D
    (33, [61, 64, 69], [64, 69, 73, 76]),   # A
]
ARP = [0, 2, 1, 3, 2, 1, 3, 2, 0, 2, 1, 3, 2, 3, 1, 2]


# ── DSP helpers ─────────────────────────────────────────────────
def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tax(n):
    return np.arange(n) / SR


def saw(freq, n, phase=0.0):
    """Band-limited sawtooth (polyBLEP)."""
    dt = freq / SR
    ph = (phase + dt * np.arange(n)) % 1.0
    y = 2 * ph - 1
    m = ph < dt
    x = ph[m] / dt
    y[m] -= x + x - x * x - 1
    m = ph > 1 - dt
    x = (ph[m] - 1) / dt
    y[m] -= x * x + x + x + 1
    return y


def filt(x, kind, fc, order=2):
    sos = signal.butter(order, fc, kind, fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=0)


def peaking(x, f0, gain_db, q):
    a = 10 ** (gain_db / 40)
    w = 2 * np.pi * f0 / SR
    al = np.sin(w) / (2 * q)
    b = [1 + al * a, -2 * np.cos(w), 1 - al * a]
    d = [1 + al / a, -2 * np.cos(w), 1 - al / a]
    return signal.lfilter(np.array(b) / d[0], np.array(d) / d[0], x, axis=0)


def env(n, a=0.005, r=0.05):
    e = np.ones(n)
    na, nr = min(int(a * SR), n // 2), min(int(r * SR), n // 2)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr) ** 2
    return e


def place(buf, x, t, gain=1.0, pan=0.0):
    """Add mono or stereo x into stereo buf at time t (equal-power pan for mono)."""
    i = int(round(t * SR))
    if i >= len(buf) or i + len(x) <= 0:
        return
    if i < 0:
        x, i = x[-i:], 0
    x = x[: len(buf) - i]
    if x.ndim == 1:
        p = (pan + 1) * np.pi / 4
        buf[i:i + len(x), 0] += x * gain * np.cos(p)
        buf[i:i + len(x), 1] += x * gain * np.sin(p)
    else:
        buf[i:i + len(x)] += x * gain


def noise(n):
    return RNG.standard_normal(n)


# ── Drums ───────────────────────────────────────────────────────
def kick():
    n = int(0.42 * SR)
    t = tax(n)
    f = 46 + 120 * np.exp(-t / 0.03)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.17)
    click = filt(noise(n), "high", 1500) * np.exp(-t / 0.004) * 0.25
    return np.tanh(1.8 * (body + click)) / np.tanh(1.8)


def clap():
    n = int(0.35 * SR)
    t = tax(n)
    e = np.zeros(n)
    for k, d in enumerate([0, 0.010, 0.021, 0.033]):
        e += (t >= d) * np.exp(-np.clip(t - d, 0, None) / (0.006 if k < 3 else 0.11))
    x = filt(noise(n), "bandpass", [900, 6000]) * e
    return x / np.max(np.abs(x))


def snare():
    n = int(0.22 * SR)
    t = tax(n)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)
    body = filt(noise(n), "bandpass", [1200, 8000]) * np.exp(-t / 0.07)
    x = 0.5 * tone + body
    return x / np.max(np.abs(x))


def hat(open_=False):
    n = int((0.3 if open_ else 0.06) * SR)
    t = tax(n)
    x = filt(noise(n), "high", 7500) * np.exp(-t / (0.11 if open_ else 0.022))
    return x / np.max(np.abs(x))


def crash():
    n = int(2.2 * SR)
    t = tax(n)
    x = filt(noise(n), "high", 4000) * np.exp(-t / 0.7)
    x += 0.3 * filt(noise(n), "bandpass", [2500, 6000]) * np.exp(-t / 0.25)
    return x / np.max(np.abs(x))


# ── Tonal ───────────────────────────────────────────────────────
def bass_note(m, dur):
    n = int(dur * SR)
    f = hz(m)
    x = saw(f, n) * 0.6 + np.sin(2 * np.pi * f * tax(n)) * 0.7
    x = filt(x, "low", 420)
    return x * env(n, 0.004, 0.04)


def pad_chord(notes, dur, seed):
    n = int((dur + 0.35) * SR)
    r = np.random.default_rng(seed)
    out = np.zeros((n, 2))
    for m in notes:
        for c in range(2):
            for d in (-0.0032, -0.0012, 0.0, 0.0014, 0.0035):
                out[:, c] += saw(hz(m) * (1 + d + r.uniform(-4e-4, 4e-4)), n, r.uniform())
    out = filt(out, "low", 2100)
    e = env(n, 0.02, 0.35)
    return out * e[:, None] / (len(notes) * 5)


def pluck(m, dur=0.3):
    n = int(dur * SR)
    t = tax(n)
    f = hz(m)
    x = np.zeros(n)
    for k in range(1, 24):
        if f * k > 9000:
            break
        x += np.sin(2 * np.pi * f * k * t) / k * np.exp(-t * (7 + 5.5 * k))
    return x * env(n, 0.002, 0.03)


# ── FX ──────────────────────────────────────────────────────────
def sweep_noise(dur, f_from, f_to, shape):
    """Noise through a band-pass whose centre moves from f_from to f_to; shape = amplitude curve."""
    n = int(dur * SR)
    f, tt, Z = signal.stft(noise(n), fs=SR, nperseg=1024)
    prog = np.clip(tt / dur, 0, 1)
    centre = f_from * (f_to / f_from) ** prog
    mask = np.exp(-0.5 * (np.log2((f[:, None] + 1) / centre[None, :]) / 0.7) ** 2)
    _, y = signal.istft(Z * mask, fs=SR, nperseg=1024)
    y = y[:n]
    y /= np.max(np.abs(y)) + 1e-9
    return y * shape(np.linspace(0, 1, len(y)))


def riser(dur):
    x = sweep_noise(dur, 250, 9000, lambda p: p ** 2.2)
    t = tax(len(x))
    tone = np.sin(2 * np.pi * np.cumsum(180 * (1 + 5 * (t / dur) ** 2)) / SR) * (t / dur) ** 3
    return 0.8 * x + 0.25 * tone


def whoosh(dur=0.75):
    return sweep_noise(dur, 400, 5000, lambda p: np.sin(np.pi * p) ** 2 * (0.6 + 0.4 * p))


def impact():
    n = int(2.5 * SR)
    t = tax(n)
    f = 38 + 60 * np.exp(-t / 0.08)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.7)
    hit = filt(noise(n), "low", 3500) * np.exp(-t / 0.12)
    x = np.tanh(1.4 * (boom + 0.5 * hit))
    return x / np.max(np.abs(x))


def pop():
    n = int(0.09 * SR)
    t = tax(n)
    f = 520 + 420 * (1 - np.exp(-t / 0.012))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.025) * env(n, 0.001, 0.01)


def tick():
    n = int(0.03 * SR)
    t = tax(n)
    return np.sin(2 * np.pi * 2300 * t) * np.exp(-t / 0.006)


def chime():
    n = int(1.4 * SR)
    t = tax(n)
    x = np.zeros(n)
    for m, delay in ((86, 0.0), (93, 0.09)):
        tt = np.clip(t - delay, 0, None)
        on = t >= delay
        for k, a in ((1, 1.0), (2.76, 0.35), (5.4, 0.12)):
            x += on * a * np.sin(2 * np.pi * hz(m) * k * tt) * np.exp(-tt / (0.5 / k ** 0.5))
    return x / np.max(np.abs(x)) * env(n, 0.002, 0.2)


def hit():
    n = int(0.9 * SR)
    t = tax(n)
    f = 60 + 90 * np.exp(-t / 0.05)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.25)
    x += 0.35 * filt(noise(n), "bandpass", [800, 5000]) * np.exp(-t / 0.05)
    return np.tanh(1.5 * x) / np.tanh(1.5)


def reverb(x, seconds=2.4, decay=0.55, seed=11):
    r = np.random.default_rng(seed)
    n = int(seconds * SR)
    tail = np.exp(-tax(n) / decay)
    out = np.zeros_like(x)
    for c in range(x.shape[1]):
        ir = filt(r.standard_normal(n), "low", 6000) * tail
        ir /= np.sqrt(np.sum(ir ** 2))
        out[:, c] = signal.fftconvolve(x[:, c], ir)[: len(x)]
    return out


# ── Arrangement ─────────────────────────────────────────────────
def build_music(T):
    bpm = T.get("bpm", 118)
    beat = 60.0 / bpm
    bar = 4 * beat
    dur = T["duration"]
    n = int((dur + 3) * SR)
    scenes = [(sid, T["scenes"][sid]["start"], T["scenes"][sid]["end"]) for sid in T["order"]]

    def scene_at(t):
        for sid, s, e in scenes:
            if s <= t < e:
                return sid
        return scenes[-1][0]

    drums, tonal, fx, send = (np.zeros((n, 2)) for _ in range(4))
    K, CL, SN, HC, HO, CR = kick(), clap(), snare(), hat(), hat(True), crash()
    kicks = []

    hook_end = T["scenes"]["hook"]["end"] if "hook" in T["scenes"] else 0.0
    outro_start = T["scenes"]["outro"]["start"] if "outro" in T["scenes"] else dur

    nbars = int(np.ceil(dur / bar)) + 1
    for b in range(nbars):
        t0 = b * bar
        if t0 >= dur:
            break
        root, voicing, arp = PROG[b % 4]
        sec = SECTION.get(scene_at(t0 + 0.01), "groove")
        # the bar that starts the outro still carries the final chord
        if sec == "end" and t0 >= outro_start + 2 * bar:
            continue

        # Pad (always) — filtered during the build, opening up towards the drop
        p = pad_chord(voicing, bar, seed=b)
        if sec == "build":
            prog = min(1.0, t0 / max(hook_end, bar))
            p = filt(p, "low", 500 + 2500 * prog ** 2)
        g_pad = {"build": 0.55, "lite": 0.5, "groove": 0.42, "chorus": 0.5, "end": 0.6}[sec]
        place(tonal, p, t0, g_pad)
        place(send, p, t0, g_pad * 0.5)

        # Bass: driving eighths with an octave pop
        if sec in ("lite", "groove", "chorus"):
            for k in range(8):
                m = root + (12 if k in (3, 7) else 0)
                place(tonal, bass_note(m, beat / 2 * 0.82), t0 + k * beat / 2, 0.55)

        # Arp: 16ths, ping-pong
        if sec in ("build", "groove", "chorus", "end"):
            g = {"build": 0.1 + 0.18 * min(1.0, t0 / max(hook_end, bar)), "groove": 0.17, "chorus": 0.22, "end": 0.2}[sec]
            steps = 16 if sec != "end" else 8
            for k in range(steps):
                m = arp[ARP[k]]
                x = pluck(m)
                pan = -0.45 if k % 2 == 0 else 0.45
                place(tonal, x, t0 + k * beat / 4, g, pan)
                place(send, x, t0 + k * beat / 4, g * 0.6, -pan)
                if sec == "chorus":
                    place(tonal, pluck(m + 12, 0.22), t0 + k * beat / 4, g * 0.35, pan * 0.5)

        # Drums
        if sec in ("groove", "chorus"):
            for k in range(4):
                place(drums, K, t0 + k * beat, 0.95)
                kicks.append(t0 + k * beat)
            for k in (1, 3):
                place(drums, CL, t0 + k * beat, 0.42, 0.05)
                place(send, CL, t0 + k * beat, 0.18)
            for k in range(16):
                tt = t0 + k * beat / 4
                if k % 4 == 2:
                    place(drums, HO if sec == "chorus" else HC, tt, 0.2 if sec == "chorus" else 0.26, 0.3)
                elif k % 2 == 1:
                    place(drums, HC, tt, 0.09, 0.3)
        elif sec == "lite":
            for k in (0, 2):
                place(drums, K, t0 + k * beat, 0.85)
                kicks.append(t0 + k * beat)
            for k in range(8):
                place(drums, HC, t0 + k * beat / 2, 0.16 if k % 2 else 0.08, 0.3)
        elif sec == "build":
            # 16th hats and a snare roll in the last two bars of the hook
            if hook_end - t0 <= 2 * bar + 1e-6:
                for k in range(16):
                    tt = t0 + k * beat / 4
                    lvl = (tt - (hook_end - 2 * bar)) / (2 * bar)
                    place(drums, HC, tt, 0.05 + 0.15 * lvl, 0.3)
            if hook_end - t0 <= bar + 1e-6:
                for k in range(16):
                    tt = t0 + k * beat / 4
                    place(drums, SN, tt, 0.1 + 0.35 * (k / 15) ** 1.5, -0.1)

    # Transitions: fill + crash into every step, riser + impact into the logo and the outro
    for sid, s, _ in scenes[1:]:
        if sid in FILL_BEFORE:
            for k in range(4):
                place(drums, SN, s - beat + k * beat / 4, 0.12 + 0.1 * k, -0.1)
            place(drums, CR, s, 0.3)
            place(send, CR, s, 0.15)
    if hook_end:
        r = riser(2 * bar)
        place(fx, r, hook_end - len(r) / SR, 0.35)
        place(fx, impact(), hook_end, 0.75)
        place(drums, CR, hook_end, 0.4)
        place(send, impact(), hook_end, 0.3)
    if "outro" in T["scenes"]:
        r = riser(bar)
        place(fx, r, outro_start - len(r) / SR, 0.3)
        place(fx, impact(), outro_start, 0.7)
        place(drums, CR, outro_start, 0.35)
        place(send, CR, outro_start, 0.2)

    # Sidechain "pump" on tonal elements from the kick
    t = tax(n)
    pump = np.ones(n)
    for tk in kicks:
        i = int(tk * SR)
        m = min(n - i, int(0.4 * SR))
        pump[i:i + m] = np.minimum(pump[i:i + m], 1 - 0.5 * np.exp(-t[:m] / 0.09))
    tonal *= pump[:, None]

    mix = drums + tonal + fx + 0.32 * reverb(send)
    mix = filt(mix, "high", 32)
    mix = peaking(mix, 2600, -4.0, 0.8)  # leave room for the voice
    mix = np.tanh(1.2 * mix / (np.max(np.abs(mix)) + 1e-9)) / np.tanh(1.2)

    # Clean ending
    end = int((dur + 0.2) * SR)
    fade = int(3.0 * SR)
    mix[end - fade:end] *= np.linspace(1, 0, fade)[:, None] ** 2
    mix = mix[: int(dur * SR)]
    rms = np.sqrt(np.mean(mix ** 2))
    return mix * (0.1 / rms)  # ≈ −20 dBFS RMS; level against the voice is set in build.sh


def build_sfx(T, events):
    dur = T["duration"]
    n = int((dur + 2) * SR)
    out = np.zeros((n, 2))
    W = whoosh()
    for sid in T["order"][1:]:
        s = T["scenes"][sid]["start"]
        place(out, W, s - 0.5 * len(W) / SR, 0.3)
    make = {"pop": pop, "tick": tick, "chime": chime, "hit": hit}
    cache = {k: f() for k, f in make.items()}
    for ev in events:
        typ, t0, g = ev["type"], ev["t"], ev.get("gain", 1.0)
        if typ == "cascade":
            for k in range(ev["count"]):
                place(out, cache["tick"], t0 + k * ev["each"], 0.1 * g, np.sin(k * 1.3) * 0.5)
        elif typ in cache:
            base = {"pop": 0.22, "tick": 0.14, "chime": 0.2, "hit": 0.5}[typ]
            place(out, cache[typ], t0, base * g, ev.get("pan", 0.0))
    out = out + 0.25 * reverb(out, seconds=1.2, decay=0.25, seed=5)
    return out[: int(dur * SR)]


def main():
    T = json.loads((BUILD / "timings.json").read_text())
    music = build_music(T)
    sf.write(BUILD / "music.wav", music.astype("float32"), SR, subtype="PCM_16")
    ev_path = BUILD / "sfx.json"
    events = json.loads(ev_path.read_text()) if ev_path.exists() else []
    sfx = build_sfx(T, events)
    peak = np.max(np.abs(sfx))
    if peak > 0.95:
        sfx *= 0.95 / peak
    sf.write(BUILD / "sfx.wav", sfx.astype("float32"), SR, subtype="PCM_16")
    print(f"[music] {T['duration']:.1f}s @ {T.get('bpm', 118)} BPM, {len(events)} sfx events")


if __name__ == "__main__":
    main()
