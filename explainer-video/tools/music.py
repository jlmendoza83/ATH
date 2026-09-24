#!/usr/bin/env python3
"""
tools/music.py — Soft ambient music bed, synthesised offline (no samples, no licences).

A slow four-chord progression of warm, detuned sine pads with a light
synthetic reverb. It sits far below the voice and is ducked under it at mix time.

  python tools/music.py <duration_seconds>   →  build/music.wav (48 kHz stereo)
"""

import pathlib
import sys

import numpy as np
import soundfile as sf

ROOT = pathlib.Path(__file__).resolve().parent.parent
SR = 48000
CHORD_LEN = 8.0  # seconds per chord

# D major colour: Dmaj9 → Bm9 → Gmaj7(#11) → A6sus  (MIDI notes)
PROGRESSION = [
    [38, 50, 57, 61, 64, 66],
    [35, 47, 54, 57, 61, 62],
    [31, 43, 50, 54, 57, 61],
    [33, 45, 52, 54, 57, 59],
]


def midi_hz(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def pad_voice(freq, n, rng):
    t = np.arange(n) / SR
    out = np.zeros(n)
    # Three slightly detuned partials per note → gentle chorus
    for detune, amp in ((-0.0018, 0.5), (0.0, 0.7), (0.0021, 0.5)):
        f = freq * (1 + detune)
        phase = rng.uniform(0, 2 * np.pi)
        out += amp * np.sin(2 * np.pi * f * t + phase)
        out += amp * 0.18 * np.sin(2 * np.pi * 2 * f * t + phase)  # soft octave
    # Slow amplitude shimmer
    out *= 1 + 0.12 * np.sin(2 * np.pi * rng.uniform(0.05, 0.12) * t + rng.uniform(0, 6))
    return out


def envelope(n, attack, release):
    env = np.ones(n)
    a, r = min(int(attack * SR), n // 2), min(int(release * SR), n // 2)
    if a:
        env[:a] = np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    if r:
        env[-r:] = np.cos(np.linspace(0, np.pi / 2, r)) ** 2
    return env


def reverb(x, seconds=3.2, decay=1.1, seed=7):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / (decay * SR))
    ir /= np.sqrt(np.sum(ir ** 2))
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x)]
    return wet


def main():
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 150.0
    total = int((duration + 2) * SR)
    rng = np.random.default_rng(11)
    left, right = np.zeros(total), np.zeros(total)

    chord_n = int(CHORD_LEN * SR)
    overlap = int(2.5 * SR)
    start, k = 0, 0
    while start < total:
        notes = PROGRESSION[k % len(PROGRESSION)]
        n = min(chord_n + overlap, total - start)
        env = envelope(n, attack=2.2, release=2.8)
        for j, note in enumerate(notes):
            v = pad_voice(midi_hz(note), n, rng) * env
            gain = 0.28 if note < 40 else 0.32
            pan = 0.5 + 0.35 * ((j / max(1, len(notes) - 1)) - 0.5)
            left[start:start + n] += v * gain * (1 - pan)
            right[start:start + n] += v * gain * pan
        start += chord_n
        k += 1

    stereo = []
    for ch, seed in ((left, 7), (right, 8)):
        dry = ch
        wet = reverb(ch, seed=seed)
        stereo.append(0.55 * dry + 0.9 * wet)
    mix = np.stack(stereo, axis=1)

    # Gentle tilt: soften the highs with a vectorised FFT low-pass
    size = mix.shape[0]
    freqs = np.fft.rfftfreq(size, 1 / SR)
    tilt = 1 / np.sqrt(1 + (freqs / 1800.0) ** 4)
    for c in range(2):
        mix[:, c] = np.fft.irfft(np.fft.rfft(mix[:, c]) * tilt, size)

    # Fade in / out and normalise to a quiet peak
    fade_in, fade_out = int(3 * SR), int(5 * SR)
    mix[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    mix[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None] ** 1.5
    mix = mix[: int(duration * SR)]
    mix *= 0.5 / np.max(np.abs(mix))

    out = ROOT / "build" / "music.wav"
    out.parent.mkdir(exist_ok=True)
    sf.write(out, mix.astype("float32"), SR, subtype="PCM_16")
    print(f"[music] {duration:.1f}s → {out}")


if __name__ == "__main__":
    main()
