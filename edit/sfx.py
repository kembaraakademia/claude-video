"""Synthesize sound effects and lay them on a timeline -> sfx.wav (48 kHz stereo)."""
import sys
import wave

import numpy as np

SR = 48000
DUR = 16.0
rng = np.random.default_rng(7)


def env(n, a=0.005, r=0.1):
    t = np.arange(n) / SR
    e = np.minimum(1, t / a) * np.exp(-t / r)
    return e


def lowpass(x, alpha):
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += alpha[i] * (v - acc) if hasattr(alpha, "__len__") else alpha * (v - acc)
        y[i] = acc
    return y


def whoosh(d=0.45, up=True):
    n = int(SR * d)
    noise = rng.standard_normal(n)
    sweep = np.linspace(0.02, 0.35, n) if up else np.linspace(0.35, 0.02, n)
    x = lowpass(noise, sweep)
    x -= lowpass(x, 0.01)  # remove rumble
    shape = np.sin(np.linspace(0, np.pi, n)) ** 2
    return x * shape * 1.6


def pop(f=900, d=0.09):
    n = int(SR * d)
    t = np.arange(n) / SR
    freq = f * np.exp(-t * 18)  # pitch drop
    ph = 2 * np.pi * np.cumsum(freq) / SR
    return np.sin(ph) * env(n, 0.001, 0.025) * 0.8


def tick(d=0.04):
    n = int(SR * d)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 2400 * t) + 0.5 * rng.standard_normal(n)) * env(n, 0.0005, 0.006) * 0.6


def ding(f=1320, d=1.2):
    n = int(SR * d)
    t = np.arange(n) / SR
    x = sum(a * np.sin(2 * np.pi * f * k * t) for k, a in [(1, 1), (2.0, 0.35), (3.01, 0.15), (4.2, 0.08)])
    return x * env(n, 0.002, 0.35) * 0.45


def success(d=0.9):
    a = ding(1046.5, d)
    b = ding(1568, d)
    out = np.zeros(int(SR * (d + 0.09)))
    out[: len(a)] += a
    off = int(SR * 0.09)
    out[off: off + len(b)] += b
    return out * 0.8


def question(d=0.32):
    n = int(SR * d)
    t = np.arange(n) / SR
    freq = 500 + 500 * (t / d) ** 1.5  # rising "huh?"
    ph = 2 * np.pi * np.cumsum(freq) / SR
    vib = 1 + 0.15 * np.sin(2 * np.pi * 14 * t)
    return np.sin(ph) * np.sin(np.linspace(0, np.pi, n)) * vib * 0.4


def riser(d=0.7):
    n = int(SR * d)
    t = np.arange(n) / SR
    noise = lowpass(rng.standard_normal(n), np.linspace(0.02, 0.5, n))
    tone = np.sin(2 * np.pi * np.cumsum(300 + 900 * (t / d) ** 2) / SR)
    return (noise * 0.6 + tone * 0.25) * (t / d) ** 2


def place(track, clip, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    j = min(len(track), i + len(clip))
    l, r = (1 - max(0, pan)), (1 + min(0, pan))
    track[i:j, 0] += clip[: j - i] * gain * l
    track[i:j, 1] += clip[: j - i] * gain * r


def build(out):
    tr = np.zeros((int(SR * DUR), 2))
    # Topic card "LAJNAH DAKWAH"
    place(tr, whoosh(0.45), 1.15, 0.5)
    place(tr, pop(700), 1.54, 0.55)
    # caption pops
    for t in [3.60, 5.66, 7.42]:
        place(tr, pop(1100, 0.07), t, 0.3)
    # topic switch to "LAJNAH EKONOMI"
    place(tr, whoosh(0.4, up=False), 6.45, 0.5)
    place(tr, pop(800), 6.74, 0.5)
    # calendar card appears with "4"
    place(tr, whoosh(0.35), 7.98, 0.4, pan=-0.3)
    place(tr, ding(1320, 0.8), 8.28, 0.35, pan=-0.3)
    place(tr, pop(1000, 0.07), 9.84, 0.3)  # "perkongsian" chip
    # 4 -> 5 counter tick
    place(tr, tick(), 11.12, 0.6, pan=-0.3)
    place(tr, pop(1200, 0.08), 11.14, 0.35, pan=-0.3)
    # build-up then "6?"
    place(tr, riser(0.7), 12.08, 0.35)
    place(tr, question(), 12.78, 0.5, pan=-0.3)
    # "6 hari kan?" confirmed
    place(tr, tick(), 14.08, 0.6, pan=-0.3)
    place(tr, success(), 14.1, 0.45)

    peak = np.abs(tr).max()
    if peak > 0.95:
        tr *= 0.95 / peak
    data = (tr * 32767).astype("<i2")
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


if __name__ == "__main__":
    build(sys.argv[1])
