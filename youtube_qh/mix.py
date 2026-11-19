"""Audio for the merged YouTube edit: voice timeline (from the clips) + ducked music + SFX, mux with video.

usage: python mix.py <clipdir> <video_only.mp4> <music.wav> <outdir>
writes <outdir>/SurahAtTin_QH_youtube.mp4 (+ _nomusic.mp4), stems/, audio_report.json
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
TL = C.timeline()
N = int(TL["duration"] * SR)
rng = np.random.default_rng(4)

AUDIO = dict(target_lufs=-14.0,          # YouTube reference loudness
             music_gap_db=-12.0, music_duck_db=-22.0,
             duck_attack_ms=160, duck_release_ms=700, vad_threshold_db=-40.0, vad_hold_ms=350,
             sfx_db=-17.0)


def sos(kind, f):
    return butter(2, f, btype=kind, fs=SR, output="sos")


def db(x):
    return 10 ** (x / 20)


# ---------------------------------------------------------------- SFX
def whoosh(d=0.9, airy=False):
    n = int(SR * d)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    x = np.zeros(n)
    pos = np.sin(np.pi * t / d)
    for k, (lo, hi) in enumerate([(300, 900), (700, 2000), (1500, 4500), (3000, 9000)]):
        x += sosfilt(sos("band", [lo, hi]), noise) * np.exp(-((pos * 3 - k) ** 2) * 1.2)
    return x * np.sin(np.pi * t / d) ** (1.5 if airy else 2.5) * (0.5 if airy else 0.7)


def shimmer(d=2.2):
    n = int(SR * d)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for f in [2093, 2637, 3136, 3951, 4699, 5274]:
        st = rng.uniform(0, 0.45)
        e = np.where(t > st, np.exp(-(t - st) * rng.uniform(2.5, 4)), 0) * np.clip((t - st) / 0.01, 0, 1)
        x += np.sin(2 * np.pi * f * t) * e * rng.uniform(0.3, 0.6)
    return (x + sosfilt(sos("high", 6000), rng.standard_normal(n)) * np.exp(-t * 2.5) * 0.15) * 0.35


def chime(f=1174.7, d=2.6):
    t = np.arange(int(SR * d)) / SR
    x = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * dec)
            for k, a, dec in [(1, 1, 1.4), (2.76, .4, 2.5), (5.4, .18, 4), (8.9, .07, 6)])
    return x * np.clip(t / 0.004, 0, 1) * 0.35


def impact(d=2.2):
    t = np.arange(int(SR * d)) / SR
    ph = 2 * np.pi * np.cumsum(70 + 40 * np.exp(-t * 8)) / SR
    x = np.sin(ph) * np.exp(-t * 3.2) * 0.5 + sosfilt(sos("low", 1200), rng.standard_normal(len(t))) * np.exp(-t * 2) * 0.2
    return sosfilt(sos("high", 45), x)


def pop(d=0.12):
    t = np.arange(int(SR * d)) / SR
    ph = 2 * np.pi * np.cumsum(900 * np.exp(-t * 20) + 300) / SR
    return np.sin(ph) * np.exp(-t * 30) * 0.5


def riser(d=1.2):
    t = np.arange(int(SR * d)) / SR
    x = sosfilt(sos("band", [800, 6000]), rng.standard_normal(len(t)))
    return x * (t / d) ** 2.2 * 0.5


def sfx_events():
    ev = [(0.2, impact, -3, 0), (0.5, shimmer, -6, 0), (1.0, lambda: chime(1174.7), -8, 0)]
    for s in TL["segments"]:
        if s["kind"] == "inter":
            ev += [(s["start"] - 0.05, lambda: whoosh(0.8, True), -5, -0.3),     # card exits
                   (s["start"] + 0.45, lambda: chime(880.0), -9, 0),             # chapter title
                   (s["end"] - 1.1, riser, -11, 0.2),
                   (s["end"] - 0.75, lambda: whoosh(0.8), -6, 0.3)]               # next card enters
        if s["kind"] == "outro":
            ev += [(s["start"] - 0.05, lambda: whoosh(0.9, True), -5, 0), (s["start"] + 0.6, shimmer, -6, 0),
                   (s["start"] + 0.65, lambda: chime(1174.7), -8, 0)]
        if s["kind"] == "clip":
            for (a, b, *_r) in s["callouts"]:
                ev += [(s["start"] + a + 0.15, lambda: whoosh(0.6, True), -12, 0.5),
                       (s["start"] + a + 0.5, pop, -13, 0.5)]
            for cap in s["captions"]:   # soft shimmer when a Qur'an quote appears (has harakat)
                if any("ً" <= ch <= "ْ" for w in cap["ar"] for ch in w[0]) and "“" in cap["ms"]:
                    ev.append((s["start"] + cap["start"] - 0.2, shimmer, -10, 0))
    return ev


def build_sfx():
    out = np.zeros((N, 2))
    for at, gen, g, pan in sfx_events():
        x = gen() * db(g)
        i = int(max(0, at) * SR)
        j = min(N, i + len(x))
        l, r = np.cos((pan + 1) * np.pi / 4) * 1.414, np.sin((pan + 1) * np.pi / 4) * 1.414
        out[i:j, 0] += x[: j - i] * l
        out[i:j, 1] += x[: j - i] * r
    return out


# ---------------------------------------------------------------- voice
def build_voice(clipdir, stems):
    """Each clip: EQ + gentle compression, loudness-matched, placed on the timeline with short fades."""
    meter = pyln.Meter(SR)
    v = np.zeros(N)
    af = ("highpass=f=80,afftdn=nf=-28,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3000:t=q:w=1.2:g=2,"
          "acompressor=threshold=-22dB:ratio=2.5:attack=8:release=150:makeup=2,aresample=48000")
    for s in TL["clips"]:
        tmp = stems / f"_v_{s['index']}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s['inp']:.3f}", "-t", f"{s['dur']:.3f}",
                        "-i", str(clipdir / s["file"]), "-af", af, "-ac", "1", str(tmp)], check=True)
        _, x = wavfile.read(tmp)
        tmp.unlink()
        x = x.astype(np.float64) / 32768
        x *= db(-16 - meter.integrated_loudness(x))      # match clips to each other
        f = int(SR * 0.04)
        x[:f] *= np.linspace(0, 1, f)
        x[-f:] *= np.linspace(1, 0, f)
        i = int(s["start"] * SR)
        j = min(N, i + len(x))
        v[i:j] += x[: j - i]
    return v


def duck_envelope(v):
    hop = int(SR * 0.02)
    frames = len(v) // hop
    lvl = 20 * np.log10(np.sqrt(np.mean(v[: frames * hop].reshape(frames, hop) ** 2, axis=1)) + 1e-9)
    active = lvl > AUDIO["vad_threshold_db"]
    held = active.copy()
    for k in range(1, int(AUDIO["vad_hold_ms"] / 20) + 1):
        held[k:] |= active[:-k]
    held[:-3] |= active[3:]
    target = np.where(held, AUDIO["music_duck_db"], AUDIO["music_gap_db"])
    tt = np.arange(frames) * 0.02
    for s in TL["segments"]:         # music lifts fully on intro / interstitials / outro
        if s["kind"] != "clip":
            sel = (tt >= s["start"] + 0.2) & (tt <= s["end"] - 0.2)
            target[sel] = -6.0
    att, rel = np.exp(-20 / AUDIO["duck_attack_ms"]), np.exp(-20 / AUDIO["duck_release_ms"])
    g = np.empty(frames)
    cur = target[0]
    for i, tg in enumerate(target):
        c = att if tg < cur else rel
        cur = c * cur + (1 - c) * tg
        g[i] = cur
    return np.interp(np.arange(N) / SR, tt, g)


def main():
    clipdir, video, music_path, outdir = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3], pathlib.Path(sys.argv[4])
    stems = outdir / "stems"
    stems.mkdir(parents=True, exist_ok=True)
    meter = pyln.Meter(SR)
    T = AUDIO["target_lufs"]

    v = build_voice(clipdir, stems)
    v *= db(T - meter.integrated_loudness(v))
    voice = np.stack([v, v], 1)

    _, m = wavfile.read(music_path)
    m = m.astype(np.float64) / 32768
    m = np.pad(m, ((0, max(0, N - len(m))), (0, 0)))[:N]
    m *= db(T - meter.integrated_loudness(m))
    music = m * db(duck_envelope(v))[:, None]

    sfx = build_sfx()
    sfx *= db(T + AUDIO["sfx_db"] - meter.integrated_loudness(sfx + 1e-9))

    for name, x in [("voice", voice), ("music_ducked", music), ("sfx", sfx)]:
        wavfile.write(stems / f"{name}.wav", SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))

    report = {}
    for tag, mix in [("", voice + music + sfx), ("_nomusic", voice + sfx)]:
        mix = mix * db(T - meter.integrated_loudness(mix))
        raw = stems / "_pre.wav"
        wavfile.write(raw, SR, mix.astype(np.float32))
        final = stems / f"mix{tag or '_music'}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
                        "aresample=192000,alimiter=limit=0.84:attack=3:release=60:level=disabled,aresample=48000",
                        "-c:a", "pcm_s24le", str(final)], check=True)
        raw.unlink()
        out = outdir / f"SurahAtTin_QH_youtube{tag}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", str(final), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-shortest",
                        "-movflags", "+faststart", str(out)], check=True)
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(final), "-af", "ebur128=peak=true", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
        report[tag or "music"] = " ".join(r[r.rfind("Summary:"):].split())
        print(tag or "music", report[tag or "music"])
    (outdir / "audio_report.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
