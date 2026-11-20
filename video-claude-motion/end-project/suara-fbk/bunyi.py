"""Muzik promo korporat bersemangat (112 BPM) + kesan bunyi untuk Suara FBK. Sintetik sepenuhnya.

Guna: python3 bunyi.py <folder_output> [timemap.json]
"""
import sys, os, json
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR = 48000
TIMEMAP = [(0, 0), (36, 36)]
if len(sys.argv) > 2: TIMEMAP = [tuple(x) for x in json.load(open(sys.argv[2]))]
DUR = TIMEMAP[-1][0]; N = int(SR * DUR); t = np.arange(N) / SR
rng = np.random.default_rng(112)
def T(old):
    for (n0, o0), (n1, o1) in zip(TIMEMAP, TIMEMAP[1:]):
        if old <= o1: return n0 + (n1 - n0) * (old - o0) / (o1 - o0)
    return DUR
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
    n = int(SR * .4); tt = np.arange(n) / SR; f = 50 + 120 * np.exp(-tt * 35)
    return np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .001, .14) * 1.8)
def clap():
    n = int(SR * .25); x = bp(rng.standard_normal(n), 900, 5000); e = env(n, .001, .06)
    for d in (.008, .016): e[int(d * SR):] += env(n - int(d * SR), .001, .01) * .6
    return x * e
def hat(o=False): n = int(SR * (.2 if o else .06)); return hp(rng.standard_normal(n), 7000) * env(n, .001, .05 if o else .015)
def pluck(f, d=.35):
    n = int(SR * d); tt = np.arange(n) / SR
    s = sum(a * np.sign(np.sin(2 * np.pi * f * h * tt)) for h, a in ((1, 1), (2, .3))) * .3 + np.sin(2 * np.pi * f * tt)
    return lp(s, 3500) * env(n, .002, .09)
def bass(f, d):
    n = int(SR * d); tt = np.arange(n) / SR
    return lp(np.sin(2 * np.pi * f * tt) + .4 * np.sin(2 * np.pi * f * 2 * tt), 500) * np.minimum(tt / .01, 1) * np.clip((d - tt) / .05, 0, 1)
def whoosh(d=.8, up=True):
    n = int(SR * d); x = rng.standard_normal(n); c = np.linspace(0, 1, n); c = c if up else 1 - c
    return (bp(x, 200, 900) * (1 - c) + bp(x, 1500, 8000) * c * .8) * np.sin(np.pi * np.linspace(0, 1, n)) ** 2
def riser(d):
    n = int(SR * d); tt = np.arange(n) / SR; c = tt / d
    s = bp(rng.standard_normal(n), 400, 9000) * c ** 2 * .6 + np.sin(2 * np.pi * np.cumsum(200 + 1400 * c ** 2) / SR) * c ** 2 * .3
    return s
def impact():
    n = int(SR * 2.2); tt = np.arange(n) / SR; f = 40 + 80 * np.exp(-tt * 12)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .002, .7) + lp(rng.standard_normal(n), 2000) * env(n, .001, .25) * .5
    return np.tanh(s * 1.5)
def shimmer():
    n = int(SR * 2.5); tt = np.arange(n) / SR; s = np.zeros(n)
    for j, m in enumerate([84, 88, 91, 96, 100]):
        o = int(j * .05 * SR); s[o:] += (np.sin(2 * np.pi * hz(m) * tt) * np.exp(-tt * 2.5))[:n - o] * .2
    return s
def tick(f=2600): n = int(SR * .05); return np.sin(2 * np.pi * f * np.arange(n) / SR) * env(n, .0005, .01)

# ---------- MUZIK ----------
music = np.zeros((N, 2))
BPM = 112; beat = 60 / BPM; bar = beat * 4
PROG = [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [55, 60, 64]), (55, [55, 59, 62])]   # Am F C G
start_beat = T(4.0)               # dentuman masuk bila logo muncul
end_music = DUR - 1.0
# Pad sepanjang video
pad = np.zeros(N)
for k in range(int(DUR / bar) + 2):
    root, ch = PROG[k % 4]; t0 = k * bar; i0 = int(t0 * SR); i1 = min(N, int((t0 + bar + .3) * SR))
    if i0 >= N: break
    tt = np.arange(i1 - i0) / SR
    for m in ch:
        pad[i0:i1] += (np.sin(2 * np.pi * hz(m) * tt) + .5 * np.sin(2 * np.pi * hz(m + 12) * 1.003 * tt)) * np.minimum(tt / .3, 1) * .08
pad = lp(pad, 1800)
music += pad[:, None] * np.clip(t / 2, 0, 1)[:, None]
# Rentak + bass + arpeggio selepas 'drop'
k = 0
while True:
    tb = start_beat + k * beat
    if tb >= end_music: break
    barno = int(k // 4); root, ch = PROG[barno % 4]; b4 = k % 4
    focus_quiet = T(10.0) <= tb < T(12.4)   # sedikit reda semasa banner
    add(music, kick(), tb, .55 if not focus_quiet else .3)
    if b4 in (1, 3): add(music, clap(), tb, .32)
    add(music, hat(), tb + beat / 2, .12); add(music, hat(), tb + beat / 4, .05)
    if b4 == 0: add(music, bass(hz(root - 24), bar * .95), tb, .35)
    for s16 in range(4):
        note = ch[(k * 4 + s16) % 3] + 12 * (s16 % 2)
        add(music, pluck(hz(note)), tb + s16 * beat / 4, .09, pan=(-.4 if s16 % 2 else .4))
    k += 1
music *= np.clip((DUR - t) / 1.5, 0, 1)[:, None]

# ---------- KESAN BUNYI ----------
sfx = np.zeros((N, 2))
add(sfx, riser(3.6), T(0.3), .5)
add(sfx, impact(), T(4.0), .8); add(sfx, shimmer(), T(4.3), .4)
add(sfx, whoosh(.6), T(4.95), .5, -.5); add(sfx, impact(), T(5.55), .65); add(sfx, shimmer(), T(6.5), .35)
for i in range(3): add(sfx, tick(2400 + i * 300), T(7.2 + i * .75), .4)
add(sfx, whoosh(.9, False), T(9.9), .4); add(sfx, whoosh(.5), T(10.55), .4)
for st in (12.6, 17.4, 22.2):
    add(sfx, whoosh(.6), T(st) - .1, .5, .6); add(sfx, tick(1800), T(st + .5), .4); add(sfx, shimmer(), T(st + .9), .25)
add(sfx, whoosh(.6), T(27.3), .4); add(sfx, riser(1.6), T(29.0), .4)
add(sfx, impact(), T(30.6), .75); add(sfx, shimmer(), T(30.8), .45); add(sfx, tick(2200), T(32.4), .4); add(sfx, shimmer(), T(33.2), .3)

out = sys.argv[1] if len(sys.argv) > 1 else '.'
os.makedirs(out, exist_ok=True)
def norm(x, p): return x / (np.max(np.abs(x)) or 1) * p
wavfile.write(os.path.join(out, 'muzik.wav'), SR, (norm(music, .85) * 32767).astype(np.int16))
wavfile.write(os.path.join(out, 'sfx.wav'), SR, (norm(sfx, .9) * 32767).astype(np.int16))
print('Siap: muzik.wav, sfx.wav', DUR, 's')
