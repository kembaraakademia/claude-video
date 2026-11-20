"""Muzik ambien sinematik (pad + piano) + kesan bunyi untuk "24 Jam Hakim". Sintetik sepenuhnya.

Guna: python3 bunyi.py <folder_output>   ->  muzik.wav, sfx.wav (70 s, 48 kHz stereo)
Masa = masa babak dalam scene.html (TIMEMAP identiti).
"""
import sys, os
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR, DUR = 48000, 70.0
N = int(SR * DUR); t = np.arange(N) / SR
rng = np.random.default_rng(24)
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
def seg_env(points):  # [(masa, nilai)] -> sampul linear
    xs, ys = zip(*points); return np.interp(t, xs, ys)

# ================= MUZIK =================
music = np.zeros((N, 2))
# Kord pad (D minor -> Bb -> F -> C ; berubah suasana ikut cerita)
CH = [(0, [50, 57, 62, 65]), (11, [46, 53, 58, 62]), (18, [53, 57, 60, 65]), (26, [48, 55, 60, 64]),
      (32, [50, 53, 57, 62]), (40, [46, 53, 58, 65]), (44, [53, 57, 60, 65]), (48, [50, 57, 62, 66]),
      (57, [46, 53, 58, 62]), (63, [50, 57, 62, 66])]
pad = np.zeros((N, 2))
for k, (st, notes) in enumerate(CH):
    en = CH[k + 1][0] if k + 1 < len(CH) else DUR
    i0, i1 = int(st * SR), int(min(en + 1.5, DUR) * SR); tt = np.arange(i1 - i0) / SR
    e = np.minimum(tt / 1.5, 1) * np.clip((en + 1.5 - st - tt) / 1.5, 0, 1)
    for m in notes:
        for side, det in ((0, -.7), (1, .7)):
            w = np.sin(2 * np.pi * (hz(m) + det) * tt) + .3 * np.sin(2 * np.pi * (hz(m) * 2 + det) * tt)
            pad[i0:i1, side] += w * e * .12
pad[:, 0] = lp(pad[:, 0], 1400); pad[:, 1] = lp(pad[:, 1], 1400)
# sampul keamatan: senyap di permulaan, gelap semasa ujian, naik semasa pertolongan
inten = seg_env([(0, .5), (5, .8), (26, .9), (32, .55), (40, .6), (42, 1.0), (48, .7), (63, .9), (68, .8), (70, 0)])
music += pad * inten[:, None]
# Piano: nada arpeggio lembut
def piano(f, d=2.5):
    n = int(SR * d); tt = np.arange(n) / SR
    s = sum(a * np.sin(2 * np.pi * f * h * tt) * np.exp(-tt * (1.5 + h)) for h, a in ((1, 1), (2, .35), (3, .15), (4, .05)))
    return s * np.minimum(tt / .004, 1)
piano_on = [(1.0, 31.5), (40.5, 70)]   # tiada piano semasa babak ujian
cache = {}
for k, (st, notes) in enumerate(CH):
    en = CH[k + 1][0] if k + 1 < len(CH) else DUR - 2
    tm = st + .2; j = 0; pat = [0, 2, 3, 1, 2, 3]
    while tm < en - .2:
        if any(a <= tm < b for a, b in piano_on):
            m = notes[pat[j % 6]] + 12
            if m not in cache: cache[m] = piano(hz(m))
            add(music, cache[m], tm, .09 if 48 <= tm < 63 else .13, pan=.25 * np.sin(j))
        tm += .75; j += 1
music *= np.clip((DUR - t) / 2.0, 0, 1)[:, None]

# ================= KESAN BUNYI =================
sfx = np.zeros((N, 2))
def tick(f=2200): n = int(SR * .06); return np.sin(2 * np.pi * f * np.arange(n) / SR) * env(n, .0005, .01)
def click(): n = int(SR * .08); return bp(rng.standard_normal(n), 800, 4000) * env(n, .0005, .008)
def ping(f=1320):
    n = int(SR * .9); tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * tt) + .4 * np.sin(2 * np.pi * f * 1.5 * tt)) * np.exp(-tt * 6) * np.minimum(tt / .003, 1)
def swish(d=.5): n = int(SR * d); return bp(rng.standard_normal(n), 1200, 6000) * np.sin(np.pi * np.linspace(0, 1, n)) ** 2
def whoosh(d=1.2):
    n = int(SR * d); x = rng.standard_normal(n); c = np.linspace(0, 1, n)
    return (bp(x, 200, 900) * (1 - c) + bp(x, 1200, 6000) * c * .7) * np.sin(np.pi * c) ** 2
def rumble(d=1.3):
    n = int(SR * d); tt = np.arange(n) / SR
    return lp(rng.standard_normal(n), 180) * (0.5 + 0.5 * np.sin(2 * np.pi * 9 * tt)) * np.sin(np.pi * tt / d)
def chime():
    n = int(SR * 3); tt = np.arange(n) / SR; s = np.zeros(n)
    for j, m in enumerate([74, 78, 81, 86]):
        o = int(j * .09 * SR); s[o:] += (np.sin(2 * np.pi * hz(m) * tt) * np.exp(-tt * 1.4))[:n - o] * .25
    return s
def heartbeat():
    n = int(SR * .5); tt = np.arange(n) / SR; b = np.sin(2 * np.pi * 55 * tt) * np.exp(-tt * 18)
    out = np.zeros(int(SR * .9)); out[:n] += b; out[int(.22 * SR):int(.22 * SR) + n] += b * .7; return out

# S1: tik jam setiap tanda menyala
for i in range(24): add(sfx, tick(2000 + (i % 6 == 0) * 600), .5 + i * .12, .25)
add(sfx, chime(), 3.6, .3)
# Peralihan babak
for st in [5.0, 11.0, 18.0, 26.0, 40.0, 48.0, 57.0, 63.0]: add(sfx, whoosh(), st - .3, .18)
# S2: klik lampu
add(sfx, click(), 5.6, .5); add(sfx, click(), 5.8, .3); add(sfx, click(), 6.0, .5)
# S3: telefon naik + tanda senarai
add(sfx, swish(.7), 11.2, .3)
for i in range(4): add(sfx, tick(1500), 14.4 + i * .7, .35)
# S4: kad
for i in range(3): add(sfx, swish(), 18.4 + i * 1.3, .35, pan=(-.5, .5, -.5)[i])
# S5: hari berlalu (tik pantas)
for k in range(30): add(sfx, tick(1800), 26.3 + k * .1, .1)
add(sfx, chime(), 30.4, .25)
# S6: hujan + panggilan + enjin gagal + degup jantung
rain = hp(rng.standard_normal(N), 2500) * .05; rain = lp(rain, 9000)
renv = seg_env([(0, 0), (31.8, 0), (32.5, 1), (41.5, .9), (44, 0), (70, 0)])
sfx[:, 0] += rain * renv; sfx[:, 1] += np.roll(rain, 300) * renv
for k in range(3): add(sfx, ping(990), 32.6 + k * .7, .25)
for k in range(3): add(sfx, rumble(.4), 36.4 + k * .5, .5)
for k in range(3): add(sfx, heartbeat(), 37.9 + k * .9, .45)
# S7: kereta tiba + notifikasi
add(sfx, lp(rng.standard_normal(int(SR * 1.6)), 300) * np.sin(np.pi * np.linspace(0, 1, int(SR * 1.6))), 40.3, .4)
for i in range(3): add(sfx, ping(1320 + i * 220), 41.8 + i * 1.2, .35)
# S8–S10: kilauan
add(sfx, chime(), 48.3, .3); add(sfx, chime(), 59.0, .25); add(sfx, chime(), 66.4, .3)

out = sys.argv[1] if len(sys.argv) > 1 else '.'
os.makedirs(out, exist_ok=True)
def norm(x, p): return x / (np.max(np.abs(x)) or 1) * p
wavfile.write(os.path.join(out, 'muzik.wav'), SR, (norm(music, .8) * 32767).astype(np.int16))
wavfile.write(os.path.join(out, 'sfx.wav'), SR, (norm(sfx, .9) * 32767).astype(np.int16))
print('Siap: muzik.wav, sfx.wav')
