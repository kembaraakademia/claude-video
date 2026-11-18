"""Original Arabic / Islamic cinematic ambient instrumental, synthesized from scratch (no samples, no
copyrighted material, no vocals): warm pads + drone, Karplus-Strong oud, breathy ney, soft strings and a
very light frame drum. Maqam Hijaz on D. Arrangement follows the IMG_3434 narration structure.

usage: python music.py <out.wav>
"""
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, lfilter, sosfilt

import config as C

SR = 48000
DUR = C.DURATION + 0.3
N = int(SR * DUR)
BPM = 66
BEAT = 60 / BPM
BAR = BEAT * 4
rng = np.random.default_rng(11)

# Hijaz on D
D, Eb, Fs, G, A, Bb, Cn = 62, 63, 66, 67, 69, 70, 72
CHORDS = [(50, 54, 57), (55, 58, 62), (48, 51, 55), (50, 54, 57)]   # D, Gm, Cm, D (octave 3)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def sos_bp(lo, hi):
    return butter(2, [lo, hi], btype="band", fs=SR, output="sos")


def sos_lp(f):
    return butter(2, f, btype="low", fs=SR, output="sos")


def sos_hp(f):
    return butter(2, f, btype="high", fs=SR, output="sos")


def env_curve(points):
    """piecewise-linear automation [(t, gain), ...] -> array of length N"""
    ts, gs = zip(*points)
    return np.interp(np.arange(N) / SR, ts, gs)


def add(buf, x, at, pan=0.0, gain=1.0):
    i = int(at * SR)
    if i >= N:
        return
    j = min(N, i + len(x))
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[i:j, 0] += x[: j - i] * gain * l * 1.414
    buf[i:j, 1] += x[: j - i] * gain * r * 1.414


# ---------------------------------------------------------------- instruments
def pad_layer():
    out = np.zeros((N, 2))
    t = np.arange(N) / SR
    seg = BAR * 2
    nseg = int(DUR / seg) + 2
    for k in range(nseg):
        chord = CHORDS[k % 4]
        st = k * seg - 1.5
        ln = seg + 3.0
        i0, i1 = max(0, int(st * SR)), min(N, int((st + ln) * SR))
        if i1 <= i0:
            continue
        tt = t[i0:i1] - st
        fade = np.minimum(1, tt / 2.0) * np.minimum(1, (ln - tt) / 2.0)
        for m in chord + (chord[0] + 12,):
            for ch, det in ((0, -0.06), (1, 0.06)):
                f = hz(m) * 2 ** (det / 12)
                ph = 2 * np.pi * f * tt + rng.uniform(0, 6.28)
                x = np.sin(ph) + 0.28 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)
                x *= 1 + 0.12 * np.sin(2 * np.pi * 0.11 * tt + m)
                out[i0:i1, ch] += x * fade * 0.07
    # drone on D2 + A2 (kept light to avoid excess bass)
    for m, g in ((38, 0.05), (45, 0.035)):
        ph = 2 * np.pi * hz(m) * t
        x = (np.sin(ph) + 0.35 * np.sin(2 * ph)) * g * (1 + 0.15 * np.sin(2 * np.pi * 0.07 * t))
        out[:, 0] += x
        out[:, 1] += x
    return sosfilt(sos_lp(2600), out, axis=0)


def oud_note(m, dur=2.2, vel=1.0):
    f = hz(m)
    p = int(round(SR / f))
    n = int(SR * dur)
    exc = np.zeros(n)
    burst = rng.uniform(-1, 1, p) * vel
    burst = lfilter([0.6, 0.4], [1], burst)          # plectrum softness
    exc[:p] = burst
    g = 0.996 if f < 200 else 0.993
    a = np.zeros(p + 2)
    a[0] = 1
    a[p] -= g * 0.5
    a[p + 1] -= g * 0.5
    y = lfilter([1], a, exc)
    body = sosfilt(sos_bp(150, 320), y) * 0.6 + sosfilt(sos_bp(1800, 3200), y) * 0.25
    y = y * 0.7 + body
    y *= np.minimum(1, (n - np.arange(n)) / (SR * 0.05))
    return y * 0.32


def oud_part(buf):
    scale = [D, Eb, Fs, G, A, Bb, Cn, D + 12]
    patterns = [  # (beat offset, scale degree index, octave shift, velocity)
        [(0, 0, -12, 1.0), (1, 4, -12, 0.6), (1.5, 2, -12, 0.5), (2, 4, -12, 0.7), (3, 3, -12, 0.6), (3.5, 2, -12, 0.5)],
        [(0, 3, -12, 0.9), (1, 5, -12, 0.6), (2, 7, -12, 0.7), (2.5, 5, -12, 0.5), (3, 4, -12, 0.6)],
        [(0, 6, -24, 0.9), (1, 1, -12, 0.6), (2, 3, -12, 0.7), (3, 1, -12, 0.55), (3.5, 0, -12, 0.5)],
        [(0, 0, -12, 1.0), (1, 2, -12, 0.6), (2, 4, -12, 0.7), (2.75, 2, -12, 0.45), (3, 1, -12, 0.6), (3.5, 2, -12, 0.55)],
    ]
    sections = [(0.6, 4.3, 0.55), (21.0, 51.4, 0.8), (51.4, 65.4, 1.0), (65.4, 70.5, 0.6)]
    bar_i = 0
    t = 0.0
    while t < DUR:
        dens = next((g for a, b, g in sections if a <= t < b), 0)
        if dens:
            pat = patterns[(bar_i // 2) % 4]
            for off, deg, octv, vel in pat:
                if dens < 0.7 and off % 1:  # sparse in intro / outro
                    continue
                tt = t + off * BEAT + rng.uniform(-0.01, 0.01)
                add(buf, oud_note(scale[deg] + octv + 12, vel=vel * dens * rng.uniform(0.85, 1.0)), tt, pan=-0.25)
        t += BAR
        bar_i += 1


def ney_phrase(notes, start):
    """notes: [(midi, dur)], legato with portamento; breathy tone + vibrato."""
    total = sum(d for _, d in notes) + 0.6
    n = int(SR * total)
    tt = np.arange(n) / SR
    f = np.zeros(n)
    amp = np.zeros(n)
    pos = 0.0
    for idx, (m, d) in enumerate(notes):
        i0, i1 = int(pos * SR), int((pos + d) * SR)
        f[i0:i1] = hz(m)
        pos += d
    f[int(pos * SR):] = f[int(pos * SR) - 1]
    # portamento
    f = lfilter([0.0025], [1, -0.9975], f, zi=[f[0] * 0.9975])[0]
    amp = np.minimum(1, tt / 0.35) * np.minimum(1, (total - tt) / 0.9)
    vib = 1 + 0.006 * np.minimum(1, tt / 1.2) * np.sin(2 * np.pi * 5.2 * tt)
    ph = 2 * np.pi * np.cumsum(f * vib) / SR
    tone = np.sin(ph) + 0.22 * np.sin(2 * ph) + 0.09 * np.sin(3 * ph)
    breath = sosfilt(sos_bp(900, 3800), rng.standard_normal(n)) * 0.35
    x = (tone * 0.75 + breath * (0.6 + 0.4 * np.sin(ph) ** 2)) * amp
    return x * 0.22, start


def strings_part():
    out = np.zeros((N, 2))
    t = np.arange(N) / SR
    seg = BAR * 2
    automation = env_curve([(0, 0), (20.5, 0), (24, 0.45), (51, 0.5), (56.5, 0.8), (62, 1.0), (65.5, 0.6),
                            (70, 0.25), (DUR, 0)])
    for k in range(int(DUR / seg) + 2):
        chord = CHORDS[k % 4]
        st = k * seg - 1.0
        ln = seg + 2.0
        i0, i1 = max(0, int(st * SR)), min(N, int((st + ln) * SR))
        if i1 <= i0:
            continue
        tt = t[i0:i1] - st
        fade = np.minimum(1, tt / 1.8) * np.minimum(1, (ln - tt) / 1.8)
        for m in (chord[1] + 12, chord[2] + 12, chord[0] + 24):
            for ch, det in ((0, -0.08), (1, 0.08)):
                f = hz(m) * 2 ** (det / 12)
                ph = 2 * np.pi * f * tt + 0.004 * np.sin(2 * np.pi * 5.5 * tt) * 40 + rng.uniform(0, 6.28)
                x = sum(np.sin(h * ph) / h for h in range(1, 8))
                out[i0:i1, ch] += x * fade * 0.03
    out = sosfilt(sos_lp(3200), out, axis=0)
    return out * automation[:, None]


def frame_drum(buf):
    t = 21.0
    automation = env_curve([(0, 0), (21, 0), (29, 0.6), (51, 0.7), (60, 0.9), (64.5, 0.0), (DUR, 0)])
    while t < 65:
        for off, kind in ((0, "dum"), (2, "tek"), (3.5, "tek")):
            tt = t + off * BEAT
            i = int(tt * SR)
            g = automation[min(i, N - 1)]
            if g <= 0.01:
                continue
            n = int(SR * 0.35)
            s = np.arange(n) / SR
            if kind == "dum":
                ph = 2 * np.pi * np.cumsum(95 * np.exp(-s * 6) + 62) / SR
                x = np.sin(ph) * np.exp(-s * 9) * 0.5 + sosfilt(sos_bp(300, 900), rng.standard_normal(n)) * np.exp(-s * 40) * 0.1
            else:
                x = sosfilt(sos_bp(1500, 5000), rng.standard_normal(n)) * np.exp(-s * 55) * 0.18
            add(buf, x * g, tt, pan=0.15)
        t += BAR


def reverb(x, rt=2.8, wet=0.3):
    n = int(SR * rt)
    s = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-6.9 * s / rt)[:, None]
    ir = sosfilt(sos_lp(5000), ir, axis=0)
    ir[: int(SR * 0.02)] = 0  # pre-delay
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    y = np.stack([fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], axis=1)
    return x * (1 - wet) + y * wet


def build():
    pads = pad_layer()
    oud = np.zeros((N, 2))
    oud_part(oud)
    ney = np.zeros((N, 2))
    for notes, st in [
        ([(A, 1.0), (Bb, 0.35), (A, 0.35), (G, 0.45), (Fs, 0.6), (G, 0.4), (A, 1.4)], 0.7),
        ([(D + 12, 1.4), (Cn, 0.45), (Bb, 0.45), (A, 0.9), (Bb, 0.35), (A, 0.35), (G, 0.4), (Fs, 0.6),
          (G, 0.5), (A, 1.8)], 65.5),
        ([(G, 0.6), (Fs, 0.5), (Eb, 0.5), (D, 2.2)], 70.0),
    ]:
        x, s0 = ney_phrase(notes, st)
        add(ney, x, s0, pan=0.12)
    strings = strings_part()
    drums = np.zeros((N, 2))
    frame_drum(drums)

    # arrangement automation per stem
    pad_auto = env_curve([(0, 0), (1.5, 0.9), (4.2, 0.8), (6, 0.55), (20.5, 0.55), (23, 0.8), (65, 0.85),
                          (68, 1.0), (DUR - 1.2, 0.8), (DUR, 0)])
    mix = (reverb(pads, 3.5, 0.35) * pad_auto[:, None]
           + reverb(oud, 2.4, 0.28) * 0.9
           + reverb(ney, 3.2, 0.42) * 1.1
           + reverb(strings, 3.0, 0.4)
           + reverb(drums, 1.6, 0.2) * 0.8)
    mix = sosfilt(sos_hp(60), mix, axis=0)        # no excess sub-bass
    end = env_curve([(0, 1), (DUR - 1.4, 1), (DUR - 0.2, 0), (DUR, 0)])
    mix *= end[:, None]
    mix /= np.abs(mix).max() / 0.89
    return mix


if __name__ == "__main__":
    wavfile.write(sys.argv[1], SR, (build() * 32767).astype(np.int16))
    print("music written")
