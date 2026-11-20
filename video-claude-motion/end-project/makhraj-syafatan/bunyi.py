"""Muzik latar lembut ala Arab + kesan bunyi untuk video Makhraj Asy-Syafatan (sintetik, tiada sampel).

Guna:  python3 bunyi.py <folder_output> [timemap.json]
Hasil: muzik.wav, sfx.wav (48 kHz stereo)
timemap.json (pilihan): [[masa_video, masa_animasi], ...] sama dengan TIMEMAP dalam scene.html
"""
import sys, os, json
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR = 48000
TIMEMAP = [(0, 0), (56, 56)]
if len(sys.argv) > 2:
    TIMEMAP = [tuple(x) for x in json.load(open(sys.argv[2]))]
DUR = TIMEMAP[-1][0]
N = int(SR * DUR)
rng = np.random.default_rng(11)

def T(old):
    for (n0, o0), (n1, o1) in zip(TIMEMAP, TIMEMAP[1:]):
        if old <= o1:
            return n0 + (n1 - n0) * (old - o0) / (o1 - o0)
    return DUR
def bp(x, lo, hi): return sosfilt(butter(2, [lo, hi], btype='band', fs=SR, output='sos'), x)
def lp(x, f): return sosfilt(butter(2, f, btype='low', fs=SR, output='sos'), x)
def hp(x, f): return sosfilt(butter(2, f, btype='high', fs=SR, output='sos'), x)
def env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(t / max(a, 1e-4), 1) * np.exp(-np.maximum(t - a, 0) / d)
def add(buf, sig, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= len(buf) or i < 0: return
    sig = sig[:len(buf) - i]
    buf[i:i + len(sig), 0] += sig * gain * np.sqrt((1 - pan) / 2) * 1.414
    buf[i:i + len(sig), 1] += sig * gain * np.sqrt((1 + pan) / 2) * 1.414
def hz(m): return 440 * 2 ** ((m - 69) / 12)

t = np.arange(N) / SR
# ================= MUZIK (lembut: dengung + petikan oud, tiada gendang) =================
music = np.zeros((N, 2))
drone = np.zeros(N)
for f, a in [(hz(38), .5), (hz(45), .28), (hz(50), .2)]:
    for det in (-0.5, 0.5):
        drone += a * np.sin(2 * np.pi * (f + det) * t + rng.uniform(0, 6))
drone = lp(drone * (0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t) ** 2), 800)
fade = np.clip(t / 3, 0, 1) * np.clip((DUR - t) / 2.5, 0, 1)
music += (drone * fade * .22)[:, None]

def pluck(freq, dur=1.6):
    n = int(SR * dur); p = int(SR / freq)
    buf = lp(rng.uniform(-1, 1, p + 64), 3500)[:p]
    out = np.zeros(n); idx = 0
    for i in range(n):
        out[i] = buf[idx]; nx = (idx + 1) % p
        buf[idx] = 0.995 * 0.5 * (buf[idx] + buf[nx]); idx = nx
    return hp(out, 90) * env(n, .002, dur * .45)
HIJAZ = [62, 63, 66, 67, 69, 70, 72, 74]
beat = 60 / 76
phrases = [[(4, 1), (3, .5), (2, .5), (1, 1), (0, 2)], [(0, 1), (1, .5), (2, .5), (3, 1), (4, 2)],
           [(7, 1), (5, 1), (4, .5), (3, .5), (2, 1), (0, 2)], [(2, 1), (1, 1), (0, 3)]]
cache = {}; tm = 1.0; k = 0
while tm < DUR - 3:
    for deg, ln in phrases[k % 4]:
        m = HIJAZ[deg] - 12
        if m not in cache: cache[m] = pluck(hz(m))
        add(music, cache[m], tm, .26, pan=-.2)
        tm += ln * beat
    k += 1; tm += beat * 2
music *= np.clip((DUR - t) / 2.5, 0, 1)[:, None]

# ================= KESAN BUNYI =================
sfx = np.zeros((N, 2))
def whoosh(d=.9, up=True):
    n = int(SR * d); tt = np.linspace(0, 1, n); x = rng.standard_normal(n); c = tt if up else 1 - tt
    return (bp(x, 200, 900) * (1 - c) + bp(x, 1200, 7000) * c * .8) * np.sin(np.pi * tt) ** 2
def pop(f=800):
    n = int(SR * .16); tt = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(f * (1 + 1.4 * np.exp(-tt * 55))) / SR) * env(n, .001, .04)
def bubble(f=600):  # pop lembut "blup" untuk huruf
    n = int(SR * .3); tt = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(f * (1 + .8 * tt / .3)) / SR) * env(n, .002, .07)
def chime(base=hz(74)):
    n = int(SR * 3); tt = np.arange(n) / SR; s = np.zeros(n)
    for j, m in enumerate([0, 4, 7, 12]):
        o = int(j * .08 * SR); f = base * 2 ** (m / 12)
        s[o:] += (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 1.6) * .3 + np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt * 4) * .08)[:n - o]
    return s
def scribble(d=1.6):  # bunyi pen melukis
    n = int(SR * d); x = bp(rng.standard_normal(n), 2500, 6000)
    am = 0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 7 * np.arange(n) / SR))
    return x * am * np.sin(np.pi * np.linspace(0, 1, n)) ** .5
def swish(d=.45):
    n = int(SR * d); tt = np.linspace(0, 1, n)
    return bp(rng.standard_normal(n), 1500, 6000) * np.sin(np.pi * tt) ** 2

for old in [5.5, 16.2, 46.7]: add(sfx, whoosh(1.0), T(old), .35)
for i in range(5): add(sfx, pop(600 + i * 90), T(1.4 + i * .22), .3, pan=-.6 + i * .3)
add(sfx, scribble(), T(6.6), .12)
for i in range(5): add(sfx, pop(700 + i * 70), T(9.3 + i * 1.15), .32)
for i in range(4): add(sfx, bubble(500 + i * 80), T(17.6 + i * .8), .4)
for old in [24.7, 26.6, 33.2, 40.6]: add(sfx, bubble(420), T(old), .45)
for old in [22.4, 31.6, 38.6, 50.0]: add(sfx, swish(), T(old), .25)
for i in range(4): add(sfx, pop(650 + i * 90), T(48.6 + i * .25), .32)
add(sfx, pop(1100), T(50.6), .3)
for old in [0.4, 47.6]: add(sfx, chime(), T(old), .25)

out = sys.argv[1] if len(sys.argv) > 1 else '.'
os.makedirs(out, exist_ok=True)
def norm(x, p): return x / (np.max(np.abs(x)) or 1) * p
wavfile.write(os.path.join(out, 'muzik.wav'), SR, (norm(music, .8) * 32767).astype(np.int16))
wavfile.write(os.path.join(out, 'sfx.wav'), SR, (norm(sfx, .9) * 32767).astype(np.int16))
print('Siap: muzik.wav, sfx.wav', round(DUR, 2), 's')
