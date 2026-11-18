"""SFX design + voice-first mix with music ducking, then mux with the rendered video.

usage: python mix.py <src.mov> <video_only.mp4> <music.wav> <outdir>
writes: stems/voice.wav, stems/music_ducked.wav, stems/sfx.wav,
        IMG_3434_islamic_music.mp4 (voice+music+sfx), IMG_3434_islamic_nomusic.mp4 (voice+sfx)
"""
import json
import pathlib
import subprocess
import sys

import numpy as np
import pyloudnorm as pyln
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

import config as C

SR = 48000
A = C.AUDIO
rng = np.random.default_rng(5)


def sos(kind, f, order=2):
    return butter(order, f, btype=kind, fs=SR, output="sos")


def db(x):
    return 10 ** (x / 20)


# ---------------------------------------------------------------- SFX
def whoosh(d=1.1, airy=False):
    n = int(SR * d)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    # sweep a band-pass up then down by mixing several fixed bands with moving weights
    bands = [(300, 900), (700, 2000), (1500, 4500), (3000, 9000)]
    x = np.zeros(n)
    pos = np.sin(np.pi * t / d)
    for k, (lo, hi) in enumerate(bands):
        w = np.exp(-((pos * 3 - k) ** 2) * 1.2)
        x += sosfilt(sos("band", [lo, hi]), noise) * w
    shape = np.sin(np.pi * t / d) ** (1.5 if airy else 2.5)
    return x * shape * (0.5 if airy else 0.7)


def shimmer(d=2.4):
    n = int(SR * d)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for f in [2093, 2637, 3136, 3951, 4699, 5274]:   # C7-ish bell partials, pentatonic sparkle
        st = rng.uniform(0, 0.5)
        e = np.where(t > st, np.exp(-(t - st) * rng.uniform(2.5, 4)), 0) * np.minimum(1, np.maximum(0, t - st) / 0.01)
        x += np.sin(2 * np.pi * f * t * (1 + 0.002 * np.sin(2 * np.pi * 6 * t))) * e * rng.uniform(0.3, 0.6)
    air = sosfilt(sos("high", 6000), rng.standard_normal(n)) * np.exp(-t * 2.5) * 0.15
    return (x + air) * np.minimum(1, t / 0.05) * 0.35


def chime(f=1174.7, d=3.0):  # D6, fits Hijaz-on-D
    n = int(SR * d)
    t = np.arange(n) / SR
    x = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * dec)
            for k, a, dec in [(1, 1, 1.4), (2.76, 0.4, 2.5), (5.4, 0.18, 4), (8.9, 0.07, 6)])
    return x * np.minimum(1, t / 0.004) * 0.35


def impact(d=2.5):
    n = int(SR * d)
    t = np.arange(n) / SR
    ph = 2 * np.pi * np.cumsum(70 + 40 * np.exp(-t * 8)) / SR
    body = np.sin(ph) * np.exp(-t * 3.2) * 0.5
    swell = sosfilt(sos("low", 1200), rng.standard_normal(n)) * np.exp(-t * 2) * 0.2
    return sosfilt(sos("high", 45), body + swell)   # soft, not boomy


def wind(d):
    n = int(SR * d)
    t = np.arange(n) / SR
    x = sosfilt(sos("band", [250, 1400]), rng.standard_normal(n))
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.23 * t) * np.sin(2 * np.pi * 0.07 * t + 1)
    fade = np.minimum(1, t / 1.5) * np.minimum(1, (d - t) / 1.5)
    return x * lfo * fade * 0.25


SFX_EVENTS = [  # (time, generator, gain dB, pan) — placed on pauses / visual cues
    (0.0, lambda: wind(5.5), -6, 0.0),
    (0.35, impact, -4, 0.0),
    (0.45, lambda: chime(1174.7), -8, -0.2),
    (4.05, lambda: whoosh(0.9, airy=True), -6, 0.3),
    (4.25, shimmer, -10, 0.0),           # ta'awwudh card
    (8.35, shimmer, -11, 0.0),           # basmalah card
    (12.5, lambda: whoosh(0.9, airy=True), -6, -0.3),
    (12.65, impact, -9, 0.0),
    (12.7, shimmer, -8, 0.0),            # At-Taubah 9:91
    (20.75, lambda: whoosh(0.8), -9, 0.3),
    (29.2, lambda: chime(880.0), -13, -0.3),   # "pengajaran" panel (soft, under speech)
    (36.85, lambda: whoosh(0.8, airy=True), -10, -0.3),
    (40.1, shimmer, -14, -0.4),          # "ayat selepas ini" panel
    (43.85, shimmer, -9, 0.0),           # At-Taubah 9:120
    (51.5, lambda: whoosh(0.8, airy=True), -10, 0.3),
    (63.5, shimmer, -12, -0.4),          # sunrise icon
    (65.35, lambda: chime(1174.7), -7, 0.0),  # end of the message (pause)
    (65.55, lambda: whoosh(0.9, airy=True), -9, -0.3),
    (66.0, lambda: wind(7.0), -8, 0.0),
    (68.3, impact, -10, 0.0),
    (68.5, shimmer, -10, 0.2),
]


def build_sfx(n):
    out = np.zeros((n, 2))
    for at, gen, g, pan in SFX_EVENTS:
        x = gen() * db(g)
        i = int(at * SR)
        j = min(n, i + len(x))
        l, r = np.cos((pan + 1) * np.pi / 4) * 1.414, np.sin((pan + 1) * np.pi / 4) * 1.414
        out[i:j, 0] += x[: j - i] * l
        out[i:j, 1] += x[: j - i] * r
    return out


# ---------------------------------------------------------------- voice + ducking
def process_voice(src, out):
    """Moderate EQ + compression; keeps Arabic articulation clear."""
    af = ("highpass=f=75,equalizer=f=220:t=q:w=1.0:g=-2,equalizer=f=3200:t=q:w=1.2:g=2.0,"
          "equalizer=f=9000:t=q:w=1.0:g=1.0,"
          "acompressor=threshold=-24dB:ratio=2.5:attack=8:release=160:makeup=2,"
          "aresample=48000")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-map", "0:a:0", "-af", af, "-ac", "1", out],
                   check=True)


def duck_envelope(voice, n):
    """Gain curve (linear) for the music: low while the narrator speaks, up in pauses."""
    hop = int(SR * 0.02)
    frames = len(voice) // hop
    rms = np.sqrt(np.mean(voice[: frames * hop].reshape(frames, hop) ** 2, axis=1) + 1e-12)
    lvl = 20 * np.log10(rms)
    active = lvl > A["vad_threshold_db"]
    hold = int(A["vad_hold_ms"] / 20)
    held = active.copy()
    for k in range(1, hold + 1):  # extend speech flags forward (hold) and slightly backward (pre-roll)
        held[k:] |= active[:-k]
    held[:-3] |= active[3:]
    target_db = np.where(held, A["music_duck_db"], A["music_gap_db"])
    # extra respect during Qur'anic recitation: keep music very low between those phrases too
    tt = np.arange(frames) * 0.02
    for a, b in [(4.2, 21.0), (43.8, 46.8)]:
        sel = (tt >= a) & (tt <= b)
        target_db[sel] = np.minimum(target_db[sel], A["music_duck_db"] - 4)
    # asymmetric smoothing: attack (going down) / release (going up)
    att = np.exp(-20 / A["duck_attack_ms"])
    rel = np.exp(-20 / A["duck_release_ms"])
    g = np.empty(frames)
    cur = target_db[0]
    for i, tgt in enumerate(target_db):
        c = att if tgt < cur else rel
        cur = c * cur + (1 - c) * tgt
        g[i] = cur
    env = np.interp(np.arange(n) / SR, tt, g)
    return env  # in dB relative to voice loudness


def main():
    src, video, music_path, outdir = sys.argv[1:5]
    outdir = pathlib.Path(outdir)
    stems = outdir / "stems"
    stems.mkdir(parents=True, exist_ok=True)
    meter = pyln.Meter(SR)

    vpath = stems / "voice.wav"
    process_voice(src, str(vpath))
    _, v = wavfile.read(vpath)
    v = v.astype(np.float64) / 32768
    n = len(v)
    v_lufs = meter.integrated_loudness(v)
    v *= db(A["target_lufs"] - v_lufs)           # voice sits at the target loudness
    voice = np.stack([v, v], axis=1)

    _, m = wavfile.read(music_path)
    m = m.astype(np.float64) / 32768
    m = np.pad(m, ((0, max(0, n - len(m))), (0, 0)))[:n]
    m_lufs = meter.integrated_loudness(m)
    m *= db(A["target_lufs"] - m_lufs)           # music normalised to the voice level, then ducked
    env_db = duck_envelope(v, n)
    music = m * db(env_db)[:, None]

    sfx = build_sfx(n)
    s_lufs = meter.integrated_loudness(sfx + 1e-9)
    sfx *= db(A["target_lufs"] + A["sfx_db"] - s_lufs)

    for name, x in [("music_ducked", music), ("sfx", sfx)]:
        wavfile.write(stems / f"{name}.wav", SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))

    report = {}
    for tag, mix in [("music", voice + music + sfx), ("nomusic", voice + sfx)]:
        g = A["target_lufs"] - meter.integrated_loudness(mix)
        mix *= db(g)
        raw = stems / f"mix_{tag}_pre.wav"
        wavfile.write(raw, SR, mix.astype(np.float32))
        final = stems / f"mix_{tag}.wav"
        # true-peak safety limiter (4x oversampled) -> <= -1 dBTP
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
                        "aresample=192000,alimiter=limit=0.84:attack=3:release=60:level=disabled,aresample=48000",
                        "-c:a", "pcm_s24le", str(final)], check=True)
        raw.unlink()
        out = outdir / f"IMG_3434_islamic_{tag}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", str(final), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-shortest",
                        "-movflags", "+faststart", str(out)], check=True)
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(final), "-af", "ebur128=peak=true", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
        summ = r[r.rfind("Summary:"):]
        report[tag] = " ".join(summ.split())
        print(tag, report[tag])
    (outdir / "audio_report.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
