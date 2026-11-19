"""Original instrumental score for the merged QH video (synthesized: oud, ney, strings, pads, soft daf).
Maqam Nahawand on D. Melodic ney phrases are placed only where nobody speaks (intro, chapter
interstitials, outro); under the talk the music is a soft bed (it is ducked again in mix.py).

usage: python music.py <out.wav>
"""
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, lfilter, sosfilt

import config as C

SR = 48000
TL = C.timeline()
DUR = TL["duration"] + 0.2
N = int(SR * DUR)
BPM = 72
BEAT = 60 / BPM
BAR = BEAT * 4
rng = np.random.default_rng(21)

D, E, F, G, A, Bb, Cs = 62, 64, 65, 67, 69, 70, 73          # Nahawand (harmonic-minor colour)
SCALE = [D, E, F, G, A, Bb, Cs, D + 12]
CHORDS = [(50, 53, 57), (46, 50, 53), (48, 52, 55), (45, 49, 52)]  # Dm, Bb, C, A


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def sos(kind, f):
    return butter(2, f, btype=kind, fs=SR, output="sos")


def env_curve(points):
    ts, gs = zip(*sorted(points))
    return np.interp(np.arange(N) / SR, ts, gs)


def add(buf, x, at, pan=0.0, gain=1.0):
    i = int(at * SR)
    if i >= N or i + len(x) <= 0:
        return
    j = min(N, i + len(x))
    l, r = np.cos((pan + 1) * np.pi / 4) * 1.414, np.sin((pan + 1) * np.pi / 4) * 1.414
    buf[i:j, 0] += x[: j - i] * gain * l
    buf[i:j, 1] += x[: j - i] * gain * r


def chord_layer(octave_shift, harmonics, level, attack):
    out = np.zeros((N, 2))
    t = np.arange(N) / SR
    seg = BAR * 2
    for k in range(int(DUR / seg) + 2):
        chord = CHORDS[k % 4]
        st, ln = k * seg - attack, seg + 2 * attack
        i0, i1 = max(0, int(st * SR)), min(N, int((st + ln) * SR))
        if i1 <= i0:
            continue
        tt = t[i0:i1] - st
        fade = np.minimum(1, tt / attack) * np.minimum(1, (ln - tt) / attack)
        for m in chord:
            for ch, det in ((0, -0.07), (1, 0.07)):
                f = hz(m + octave_shift) * 2 ** (det / 12)
                ph = 2 * np.pi * f * tt + rng.uniform(0, 6.28) + 0.15 * np.sin(2 * np.pi * 5.3 * tt)
                x = sum(a * np.sin(h * ph) for h, a in harmonics)
                out[i0:i1, ch] += x * fade * level
    return out


def oud_note(m, dur=2.0, vel=1.0):
    f = hz(m)
    p = int(round(SR / f))
    n = int(SR * dur)
    exc = np.zeros(n)
    exc[:p] = lfilter([0.6, 0.4], [1], rng.uniform(-1, 1, p)) * vel
    a = np.zeros(p + 2)
    a[0] = 1
    g = 0.995 if f < 200 else 0.992
    a[p] -= g / 2
    a[p + 1] -= g / 2
    y = lfilter([1], a, exc)
    y = y * 0.7 + sosfilt(sos("band", [150, 320]), y) * 0.6 + sosfilt(sos("band", [1800, 3200]), y) * 0.25
    return y * np.minimum(1, (n - np.arange(n)) / (SR * 0.05)) * 0.3


def ney(notes, start, buf, pan=0.1):
    total = sum(d for _, d in notes) + 0.6
    n = int(SR * total)
    tt = np.arange(n) / SR
    f = np.concatenate([np.full(int(SR * d), hz(m)) for m, d in notes])
    f = np.concatenate([f, np.full(n - len(f), f[-1])])
    f = lfilter([0.0025], [1, -0.9975], f, zi=[f[0] * 0.9975])[0]
    amp = np.minimum(1, tt / 0.3) * np.minimum(1, (total - tt) / 0.8)
    vib = 1 + 0.006 * np.minimum(1, tt / 1.0) * np.sin(2 * np.pi * 5.2 * tt)
    ph = 2 * np.pi * np.cumsum(f * vib) / SR
    tone = np.sin(ph) + 0.22 * np.sin(2 * ph) + 0.09 * np.sin(3 * ph)
    breath = sosfilt(sos("band", [900, 3800]), rng.standard_normal(n)) * 0.35
    add(buf, (tone * 0.75 + breath * (0.6 + 0.4 * np.sin(ph) ** 2)) * amp * 0.22, start, pan)


def daf(buf, t0, t1, level):
    t = t0
    while t < t1:
        for off, kind in ((0, "dum"), (1.5, "tek"), (2, "dum"), (3, "tek"), (3.5, "tek")):
            tt = t + off * BEAT
            if tt >= t1:
                break
            n = int(SR * 0.35)
            s = np.arange(n) / SR
            if kind == "dum":
                ph = 2 * np.pi * np.cumsum(90 * np.exp(-s * 6) + 60) / SR
                x = np.sin(ph) * np.exp(-s * 9) * 0.45
            else:
                x = sosfilt(sos("band", [1500, 5000]), rng.standard_normal(n)) * np.exp(-s * 55) * 0.16
            add(buf, x * level * rng.uniform(0.85, 1.0), tt, 0.15)
        t += BAR


def reverb(x, rt, wet):
    n = int(SR * rt)
    s = np.arange(n) / SR
    ir = sosfilt(sos("low", 5000), rng.standard_normal((n, 2)) * np.exp(-6.9 * s / rt)[:, None], axis=0)
    ir[: int(SR * 0.02)] = 0
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    y = np.stack([fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], axis=1)
    return x * (1 - wet) + y * wet


PHRASES = [
    [(A, 0.8), (Bb, 0.35), (A, 0.35), (G, 0.4), (F, 0.5), (E, 0.4), (F, 0.4), (D, 1.4)],
    [(D + 12, 0.9), (Cs, 0.35), (Bb, 0.35), (A, 1.2)],
    [(F, 0.5), (G, 0.4), (A, 0.5), (Bb, 0.4), (A, 1.3)],
    [(E, 0.5), (F, 0.4), (G, 0.4), (A, 0.6), (D + 12, 1.2)],
    [(A, 1.0), (G, 0.4), (F, 0.4), (E, 0.5), (D, 2.4)],
]


def build():
    pads = chord_layer(0, [(1, 1), (2, .28), (3, .08)], 0.07, 2.0)
    strings = chord_layer(12, [(h, 1 / h) for h in range(1, 8)], 0.026, 1.6)
    oud = np.zeros((N, 2))
    neyb = np.zeros((N, 2))
    drums = np.zeros((N, 2))

    # oud arpeggios throughout (sparser under the talk)
    pats = [[(0, 0), (1, 4), (1.5, 2), (2, 4), (3, 3), (3.5, 2)], [(0, 5), (1, 2), (2, 4), (3, 2)],
            [(0, 6), (1, 4), (2, 2), (2.5, 1), (3, 2)], [(0, 4), (1, 6), (2, 1), (3, 4), (3.5, 6)]]
    t, b = 0.6, 0
    speech = [(s["start"], s["end"]) for s in TL["clips"]]
    while t < DUR - 3:
        talking = any(a <= t < e for a, e in speech)
        for off, deg in pats[(b // 2) % 4]:
            if talking and off % 1:
                continue
            add(oud, oud_note(SCALE[deg] - 12 + (12 if deg < 2 else 0), vel=rng.uniform(.7, 1) * (0.75 if talking else 1)),
                t + off * BEAT + rng.uniform(-.01, .01), -0.25)
        t += BAR
        b += 1

    # ney + daf lift on every non-speech section
    k = 0
    for s in TL["segments"]:
        if s["kind"] == "clip":
            continue
        ney(PHRASES[k % len(PHRASES)], s["start"] + 0.25, neyb)
        k += 1
    daf(drums, 0.0, DUR - 4, 1.0)

    lift = [(0, 1.0)]
    for s in TL["segments"]:
        if s["kind"] == "clip":
            lift += [(s["start"] - 0.01, 1.0), (s["start"] + 1.5, 0.55), (s["end"] - 1.0, 0.55), (s["end"], 1.0)]
    lift.append((DUR, 1.0))
    lift = env_curve(lift)
    strings_auto = env_curve([(0, 0.6), (DUR, 1.0)]) * lift

    mix = (reverb(pads, 3.2, .35) + reverb(strings, 3.0, .4) * strings_auto[:, None]
           + reverb(oud, 2.2, .28) * 0.9 + reverb(neyb, 3.0, .42) * 1.1 + reverb(drums, 1.4, .2) * 0.55 * lift[:, None])
    mix = sosfilt(sos("high", 60), mix, axis=0)
    mix *= env_curve([(0, 0), (0.8, 1), (DUR - 2.0, 1), (DUR - 0.2, 0), (DUR, 0)])[:, None]
    return mix / (np.abs(mix).max() / 0.89)


if __name__ == "__main__":
    wavfile.write(sys.argv[1], SR, (build() * 32767).astype(np.int16))
    print("music", round(DUR, 1), "s")
