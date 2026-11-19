"""Jana muzik latar ala Arab + kesan bunyi untuk video selawat (sepenuhnya sintetik, tiada sampel).

Guna:  python3 bunyi.py <folder_output>
Hasil: muzik.wav, sfx.wav (48 kHz stereo, 64.4 s)
"""
import sys, os
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR = 48000
DUR = 64.4
N = int(SR * DUR)
rng = np.random.default_rng(7)

# Peta masa animasi asal -> masa video (sama dengan TIMEMAP dalam scene.html)
TIMEMAP = [(0, 0), (17.0, 17.0), (27.3, 22.0), (50.9, 45.6), (58.0, 54.6), (64.4, 61.0)]
def T(old):
    for (n0, o0), (n1, o1) in zip(TIMEMAP, TIMEMAP[1:]):
        if old <= o1:
            return n0 + (n1 - n0) * (old - o0) / (o1 - o0)
    return DUR

def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], btype='band', fs=SR, output='sos'), x)
def lp(x, f, order=2):
    return sosfilt(butter(order, f, btype='low', fs=SR, output='sos'), x)
def hp(x, f, order=2):
    return sosfilt(butter(order, f, btype='high', fs=SR, output='sos'), x)
def env_ad(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(t / max(a, 1e-4), 1) * np.exp(-np.maximum(t - a, 0) / d)
def add(buf, sig, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= len(buf): return
    sig = sig[:len(buf) - i]
    l, r = np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2)
    buf[i:i + len(sig), 0] += sig * gain * l * 1.414
    buf[i:i + len(sig), 1] += sig * gain * r * 1.414
def hz(midi): return 440 * 2 ** ((midi - 69) / 12)

# Bahagian video (masa baharu): bila gendang/petikan aktif
def active_full(t):
    # senyapkan rentak semasa ayat Al-Ahzab (S3) dan lafaz selawat (S7)
    if T(11.6) <= t < T(22.0): return 0.0
    if T(45.6) <= t < T(54.6): return 0.0
    if t < T(6.0): return 0.0          # pembuka: dengung + petikan sahaja
    return 1.0
def active_melody(t):
    if T(11.6) <= t < T(22.0) or T(45.6) <= t < T(54.6): return 0.0
    return 1.0

# ================= MUZIK =================
music = np.zeros((N, 2))
t = np.arange(N) / SR

# 1) Dengung (drone) D2 + A2 + D3, ala tanpura/ney lembut
drone = np.zeros(N)
for f, a in [(hz(38), .5), (hz(45), .3), (hz(50), .22), (hz(57), .08)]:
    for det in (-0.6, 0.6):
        drone += a * np.sin(2 * np.pi * (f + det) * t + rng.uniform(0, 6))
drone *= 0.55 + 0.45 * np.sin(2 * np.pi * 0.08 * t) ** 2
drone = lp(drone, 900)
fade = np.clip(t / 3, 0, 1) * np.clip((DUR - t) / 2.5, 0, 1)
music[:, 0] += drone * fade * 0.20
music[:, 1] += drone * fade * 0.20

# 2) Petikan ala oud (Karplus-Strong) dalam maqam Hijaz atas D
def pluck(freq, dur=1.4, bright=0.5):
    n = int(SR * dur); p = int(SR / freq)
    buf = rng.uniform(-1, 1, p); buf = lp(buf, 1500 + bright * 4000, 1) if p > 20 else buf
    out = np.zeros(n); idx = 0
    for i in range(n):
        out[i] = buf[idx]
        nxt = (idx + 1) % p
        buf[idx] = 0.994 * 0.5 * (buf[idx] + buf[nxt])
        idx = nxt
    out = hp(out, 90) * env_ad(n, 0.002, dur * 0.45)
    return out
HIJAZ = [62, 63, 66, 67, 69, 70, 72, 74]  # D Eb F# G A Bb C D
BPM = 84; beat = 60 / BPM
# Frasa melodi (indeks skala, panjang dalam ketukan)
phrase_a = [(4, 1), (5, 1), (4, .5), (3, .5), (2, 1), (1, 1), (2, 1), (0, 2)]
phrase_b = [(0, .5), (1, .5), (2, 1), (3, .5), (4, .5), (5, 1), (4, 1), (2, 1), (1, .5), (0, 1.5)]
phrase_c = [(7, 1), (6, .5), (5, .5), (4, 1), (5, .5), (4, .5), (2, 1), (1, 1), (0, 2)]
cache = {}
tm = 0.6; k = 0
phrases = [phrase_a, phrase_b, phrase_c, phrase_b]
while tm < DUR - 3:
    for deg, ln in phrases[k % len(phrases)]:
        m = HIJAZ[deg] - 12 + (12 if k % 4 == 2 else 0)
        if active_melody(tm) > 0:
            if m not in cache: cache[m] = pluck(hz(m))
            g = 0.30 if tm > T(6.0) else 0.22
            add(music, cache[m], tm, g, pan=-0.25)
            if ln >= 1 and tm > T(6.0):  # tremolo kecil (ciri oud)
                add(music, cache[m] * .5, tm + beat * .5, g * .5, pan=-0.25)
        tm += ln * beat
    k += 1
    tm += beat

# 3) Daf / gendang bingkai: dum (rendah) & tak (tinggi), rentak maqsum
def dum():
    n = int(SR * .5); tt = np.arange(n) / SR
    f = 70 + 60 * np.exp(-tt * 30)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_ad(n, .002, .16)
    s += lp(rng.standard_normal(n), 400) * env_ad(n, .001, .04) * .5
    return s
def tak(bright=1.0):
    n = int(SR * .25)
    s = bp(rng.standard_normal(n), 1800, 7000) * env_ad(n, .001, .045 * bright)
    s += np.sin(2 * np.pi * 420 * np.arange(n) / SR) * env_ad(n, .001, .03) * .3
    return s
def jingle():
    n = int(SR * .35)
    return hp(rng.standard_normal(n), 6000) * env_ad(n, .002, .09)
DUM, TAK, JIN = dum(), tak(), jingle()
# maqsum: D T - T D - T -  (8 x 1/2 ketukan)
pattern = ['D', 'T', None, 'T', 'D', None, 'T', None]
step = beat / 2; tm = T(6.0) - 0.2; i = 0
while tm < DUR - 2.5:
    a = active_full(tm)
    if a > 0:
        p = pattern[i % 8]
        bar = (i // 8)
        if p == 'D': add(music, DUM, tm, .55)
        if p == 'T': add(music, TAK, tm, .22, pan=.3)
        if p == 'T' or (bar % 2 == 1 and i % 8 == 7): add(music, JIN, tm, .07, pan=.4)
        if bar % 4 == 3 and i % 8 in (5, 7): add(music, TAK, tm, .15, pan=.3)  # isian
    tm += step; i += 1

# ================= KESAN BUNYI =================
sfx = np.zeros((N, 2))
def whoosh(d=0.9, up=True):
    n = int(SR * d); tt = np.linspace(0, 1, n)
    x = rng.standard_normal(n)
    c = tt if up else 1 - tt
    out = bp(x, 200, 900) * (1 - c) + bp(x, 1200, 7000) * c * .8
    return out * np.sin(np.pi * tt) ** 2
def impact():
    n = int(SR * 1.6); tt = np.arange(n) / SR
    f = 45 + 90 * np.exp(-tt * 18)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_ad(n, .002, .45)
    s += lp(rng.standard_normal(n), 1200) * env_ad(n, .001, .12) * .6
    s += hp(rng.standard_normal(n), 2500) * env_ad(n, .001, .03) * .3
    return np.tanh(s * 1.6)
def pop(f=900):
    n = int(SR * .15); tt = np.arange(n) / SR
    fr = f * (1 + 1.5 * np.exp(-tt * 60))
    return np.sin(2 * np.pi * np.cumsum(fr) / SR) * env_ad(n, .001, .035)
def tick(f=1800):
    n = int(SR * .08)
    return np.sin(2 * np.pi * f * np.arange(n) / SR) * env_ad(n, .0005, .012) + bp(rng.standard_normal(n), 3000, 8000) * env_ad(n, .0005, .006) * .5
def chime(base=hz(74)):
    n = int(SR * 3.0); tt = np.arange(n) / SR; s = np.zeros(n)
    for j, m in enumerate([0, 4, 7, 12]):
        f = base * 2 ** (m / 12)
        s[int(j * .07 * SR):] += (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 1.6))[:n - int(j * .07 * SR)] * .3
        s[int(j * .07 * SR):] += (np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt * 4))[:n - int(j * .07 * SR)] * .08
    return s
WH, IMP, CH = whoosh(), impact(), chime()

# Peralihan babak
for old in [6.0, 11.6, 22.0, 29.8, 37.0, 45.6, 54.6]:
    add(sfx, WH, T(old) - 0.15, .35, pan=rng.uniform(-.3, .3))
# Hentakan tajuk besar
for old in [7.4, 23.75, 31.7, 38.7, 27.2]:
    add(sfx, IMP, T(old), .38)
# Pop (lencana, hati, banner)
for old, f in [(0.3, 600), (0.9, 900), (2.8, 700), (24.0, 500), (27.3, 700), (46.6, 500), (46.9, 650), (47.2, 800), (55.8, 700), (10.0, 700), (30.3, 500)]:
    add(sfx, pop(f), T(old), .35)
# Huruf jatuh (tik lembut)
for st, n, stag in [(1.8, 7, .06), (8.0, 12, .045), (40.9, 6, .07), (56.2, 11, .05)]:
    for i in range(n):
        add(sfx, tick(1400 + 80 * i), T(st + i * stag + .25), .12, pan=-.5 + i / max(n - 1, 1))
# Kiraan 1 -> 10
for k in range(10):
    add(sfx, tick(1200 + k * 110), T(24.6 + k * .26), .35)
# Kilauan
for old in [0.05, 12.6, 47.7, 57.2]:
    add(sfx, CH, T(old), .22)

def norm(x, peak):
    m = np.max(np.abs(x)) or 1
    return x / m * peak

os.makedirs(sys.argv[1] if len(sys.argv) > 1 else '.', exist_ok=True)
out = sys.argv[1] if len(sys.argv) > 1 else '.'
music *= np.clip((DUR - t) / 2.5, 0, 1)[:, None]
wavfile.write(os.path.join(out, 'muzik.wav'), SR, (norm(music, .8) * 32767).astype(np.int16))
wavfile.write(os.path.join(out, 'sfx.wav'), SR, (norm(sfx, .9) * 32767).astype(np.int16))
print('Siap: muzik.wav, sfx.wav')
