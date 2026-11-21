"""Muzik bersemangat (124 BPM, darbuka + melodi Hijaz) + kesan bunyi untuk Muthallathat Al-Jadd. Sintetik sepenuhnya.

Guna: python3 bunyi.py <folder_output>  -> muzik.wav, sfx.wav (45 s)
"""
import sys, os
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR, DUR = 48000, 45.0
N = int(SR * DUR); t = np.arange(N) / SR
rng = np.random.default_rng(124)
def bp(x, lo, hi): return sosfilt(butter(2, [lo, hi], btype='band', fs=SR, output='sos'), x)
def lp(x, f): return sosfilt(butter(2, f, btype='low', fs=SR, output='sos'), x)
def hp(x, f): return sosfilt(butter(2, f, btype='high', fs=SR, output='sos'), x)
def env(n, a, d): tt = np.arange(n) / SR; return np.minimum(tt / max(a, 1e-4), 1) * np.exp(-np.maximum(tt - a, 0) / d)
def add(buf, sig, t0, g=1.0, pan=0.0):
    i = int(t0 * SR)
    if i < 0 or i >= len(buf): return
    sig = sig[:len(buf) - i]
    buf[i:i + len(sig), 0] += sig * g * np.sqrt((1 - pan) / 2) * 1.414
    buf[i:i + len(sig), 1] += sig * g * np.sqrt((1 + pan) / 2) * 1.414
def hz(m): return 440 * 2 ** ((m - 69) / 12)

# ---------- bunyi asas ----------
def kick():
    n = int(SR * .35); tt = np.arange(n) / SR; f = 48 + 130 * np.exp(-tt * 38)
    return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .001, .13) * 2)
def clap():
    n = int(SR * .25); x = bp(rng.standard_normal(n), 900, 5000); e = env(n, .001, .07)
    for d in (.009, .018): e[int(d * SR):] += env(n - int(d * SR), .001, .01) * .6
    return x * e
def dum():   # darbuka 'dum'
    n = int(SR * .4); tt = np.arange(n) / SR; f = 90 + 60 * np.exp(-tt * 25)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .001, .18) + lp(rng.standard_normal(n), 500) * env(n, .001, .02) * .4
def tak():   # darbuka 'tak'
    n = int(SR * .15); tt = np.arange(n) / SR
    return bp(rng.standard_normal(n), 2000, 8000) * env(n, .0005, .03) + np.sin(2 * np.pi * 620 * tt) * env(n, .0005, .02) * .5
def hat(): n = int(SR * .05); return hp(rng.standard_normal(n), 8000) * env(n, .0005, .012)
def lead(f, d):  # bunyi melodi ala mizmar/synth
    n = int(SR * d); tt = np.arange(n) / SR; vib = 1 + .006 * np.sin(2 * np.pi * 5.5 * tt) * np.minimum(tt / .15, 1)
    ph = 2 * np.pi * np.cumsum(f * vib) / SR
    s = np.sin(ph) + .5 * np.sin(2 * ph) + .3 * np.sin(3 * ph) + .15 * np.sin(5 * ph)
    return lp(s, 4000) * np.minimum(tt / .02, 1) * np.clip((d - tt) / .06, 0, 1) * .5
def pluck(f, d=.3):
    n = int(SR * d); tt = np.arange(n) / SR
    return lp(np.sin(2 * np.pi * f * tt) + .4 * np.sign(np.sin(2 * np.pi * f * tt)), 3000) * env(n, .002, .08)
def bass(f, d):
    n = int(SR * d); tt = np.arange(n) / SR
    return lp(np.sin(2 * np.pi * f * tt) + .5 * np.sin(2 * np.pi * 2 * f * tt), 450) * np.minimum(tt / .01, 1) * np.clip((d - tt) / .05, 0, 1)
def whoosh(d=.7, up=True):
    n = int(SR * d); x = rng.standard_normal(n); c = np.linspace(0, 1, n); c = c if up else 1 - c
    return (bp(x, 200, 900) * (1 - c) + bp(x, 1500, 9000) * c * .8) * np.sin(np.pi * np.linspace(0, 1, n)) ** 2
def riser(d):
    n = int(SR * d); tt = np.arange(n) / SR; c = tt / d
    return bp(rng.standard_normal(n), 300, 9000) * c ** 2 * .6 + np.sin(2 * np.pi * np.cumsum(200 + 1600 * c ** 2) / SR) * c ** 2 * .3
def impact(big=True):
    n = int(SR * (2.0 if big else .9)); tt = np.arange(n) / SR; f = 38 + 90 * np.exp(-tt * 12)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .002, .6 if big else .25) + lp(rng.standard_normal(n), 2500) * env(n, .001, .2) * .5
    return np.tanh(s * 1.6)
def pop(f=800):
    n = int(SR * .16); tt = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(f * (1 + 1.4 * np.exp(-tt * 55))) / SR) * env(n, .001, .045)
def tick(f=2600): n = int(SR * .05); return np.sin(2 * np.pi * f * np.arange(n) / SR) * env(n, .0005, .01)
def shimmer():
    n = int(SR * 2.5); tt = np.arange(n) / SR; s = np.zeros(n)
    for j, m in enumerate([86, 87, 90, 93, 98]):   # arpeggio Hijaz
        o = int(j * .05 * SR); s[o:] += (np.sin(2 * np.pi * hz(m) * tt) * np.exp(-tt * 2.5))[:n - o] * .2
    return s

# ---------- MUZIK ----------
music = np.zeros((N, 2))
BPM = 124; beat = 60 / BPM; bar = 4 * beat
HIJ = [62, 63, 66, 67, 69, 70, 72, 74]       # D Hijaz
PROG = [(50, [62, 66, 69]), (48, [60, 63, 67]), (46, [58, 62, 65]), (50, [62, 66, 69])]  # D, Cm, Bb, D
FULL = 5.0
# pad
pad = np.zeros(N)
for k in range(int(DUR / bar) + 1):
    root, ch = PROG[k % 4]; i0 = int(k * bar * SR); i1 = min(N, int((k + 1) * bar * SR + .3 * SR))
    if i0 >= N: break
    tt = np.arange(i1 - i0) / SR
    for m in ch: pad[i0:i1] += (np.sin(2 * np.pi * hz(m - 12) * tt) + .4 * np.sin(2 * np.pi * hz(m) * 1.004 * tt)) * np.minimum(tt / .2, 1) * .07
music += lp(pad, 1600)[:, None]
# corak darbuka (maqsum 8 x 1/2 ketukan)
PAT = ['D', 'T', None, 'T', 'D', None, 'T', None]
step = beat / 2; k = 0
while k * step < DUR - .8:
    tb = k * step; p = PAT[k % 8]; full = tb >= FULL
    if p == 'D': add(music, dum(), tb, .45)
    if p == 'T': add(music, tak(), tb, .28, .3)
    if k % 2 == 1 and full: add(music, tak(), tb + step / 2, .12, -.3)
    if full:
        if k % 2 == 0: add(music, kick(), tb, .55)
        if k % 4 == 2: add(music, clap(), tb, .3)
        add(music, hat(), tb + step / 2, .1)
    k += 1
# bass + melodi
mel = [4, 5, 4, 3, 2, 1, 2, 0, 0, 1, 2, 3, 4, 5, 6, 7, 7, 6, 5, 4, 5, 4, 2, 1, 2, 3, 2, 1, 0, 1, 0, 0]
for bi in range(int(DUR / bar) + 1):
    tb = bi * bar
    if tb >= DUR - 1: break
    root, ch = PROG[bi % 4]
    if tb >= FULL - .01:
        for q in range(4): add(music, bass(hz(root - 12), beat * .9), tb + q * beat, .3)
        for e in range(8):
            deg = mel[(bi * 8 + e) % len(mel)]
            add(music, lead(hz(HIJ[deg]), beat * .48), tb + e * beat / 2, .11, pan=-.15)
    else:
        for e in range(8): add(music, pluck(hz(ch[e % 3] + 12)), tb + e * beat / 2, .1, pan=(.3 if e % 2 else -.3))
music *= np.clip((DUR - t) / 1.2, 0, 1)[:, None]
# reda sedikit ketika transisi utama (ruang untuk kesan bunyi)
for s0 in (9.5, 18.1, 26.7, 35.3):
    m = 1 - .5 * np.exp(-((t - s0 - .3) / .25) ** 2); music *= m[:, None]

# ---------- KESAN BUNYI ----------
sfx = np.zeros((N, 2))
WS = [10.0, 18.6, 27.2]
add(sfx, impact(), .3, .8); add(sfx, shimmer(), .6, .4); add(sfx, pop(700), 1.2, .35); add(sfx, impact(False), 1.6, .6)
for i in range(3): add(sfx, pop(650 + i * 150), 3.0 + i * .2, .4, (-.5, 0, .5)[i])
add(sfx, whoosh(.5), 4.25, .5)
add(sfx, impact(), 5.0, .7); add(sfx, pop(900), 5.6, .45)
for i in range(3): add(sfx, tick(2000 + i * 300), 6.1 + i * .25, .4)
for i in range(3): add(sfx, pop(500 + i * 120), 7.2 + i * .25, .45, (-.6, 0, .6)[i])
add(sfx, shimmer(), 8.6, .4); add(sfx, riser(1.2), 8.9, .45)
for s in WS:
    add(sfx, impact(), s, .65); add(sfx, pop(800), s + .2, .3); add(sfx, impact(False), s + .35, .5)
    add(sfx, whoosh(.6), s + .6, .45); add(sfx, pop(600), s + 1.2, .45); add(sfx, shimmer(), s + 1.6, .25)
    add(sfx, impact(False), s + 2.0, .65)
    for k in range(4): add(sfx, tick(2200 + k * 200), s + 2.8 + k * .22, .25)
    add(sfx, riser(1.0), s + 7.6, .4); add(sfx, whoosh(.5), s + 8.15, .5)
add(sfx, impact(), 35.8, .7); add(sfx, pop(800), 36.0, .4); add(sfx, impact(False), 36.2, .55)
for i in range(3): add(sfx, whoosh(.5), 36.6 + i * .25, .35, (-.5, 0, .5)[i])
for i in range(3): add(sfx, tick(1800 + i * 400), 38.0 + i * .7, .45); add(sfx, shimmer(), 38.0 + i * .7, .15)
add(sfx, pop(900), 40.0, .4); add(sfx, whoosh(.5), 40.35, .45)
add(sfx, impact(), 40.8, .6); add(sfx, pop(700), 42.0, .4)
for i in range(5): add(sfx, tick(2400 + i * 150), 42.4 + i * .12, .3)
add(sfx, shimmer(), 43.4, .45)

out = sys.argv[1] if len(sys.argv) > 1 else '.'
os.makedirs(out, exist_ok=True)
def norm(x, p): return x / (np.max(np.abs(x)) or 1) * p
wavfile.write(os.path.join(out, 'muzik.wav'), SR, (norm(music, .85) * 32767).astype(np.int16))
wavfile.write(os.path.join(out, 'sfx.wav'), SR, (norm(sfx, .9) * 32767).astype(np.int16))
print('Siap: muzik.wav, sfx.wav')
