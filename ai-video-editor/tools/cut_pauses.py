"""Remove awkward pauses (and optional filler words) from a talking-head clip.

How it decides what to cut:
  1. Whisper word timestamps say where words are (never cut inside a word, + small padding).
  2. An energy (loudness) check confirms a gap is really quiet, so breaths/quiet words that Whisper
     missed are not cut.
  3. Every quiet gap longer than --max-gap is shortened to --keep-gap (a natural short beat),
     instead of being removed completely.
  4. Optional: filler words ("err", "emm", "aaa", ...) are removed.

Outputs (next to <output>):
  <output>.mp4                 the tightened clip (same resolution/fps, H.264 + AAC)
  <output>.cuts.json           kept segments + every word re-timed to the new timeline (for captions)
  report printed: original vs new duration, number of pauses shortened

usage:
  python cut_pauses.py raw.mov export/clip_tight.mp4 [--lang ms] [--words whisper.json]
                       [--max-gap 0.6] [--keep-gap 0.25] [--fillers] [--dry-run]
"""
import argparse
import json
import pathlib
import re
import subprocess

import numpy as np

SR = 16000
FILLERS = re.compile(r"^(e+r+m*|e+m+|u+m+|a+h*|a+a+|h+m+|err+|emm+|aaa+|uh+|eh+)[.,!?…]*$", re.I)


def load_audio(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def transcribe(path, lang, model_name, out_json):
    import whisper
    m = whisper.load_model(model_name)
    r = m.transcribe(str(path), language=lang, word_timestamps=True, condition_on_previous_text=False)
    out_json.write_text(json.dumps(r, ensure_ascii=False, indent=1))
    return r


def words_from(result):
    return [(w["word"].strip(), float(w["start"]), float(w["end"]))
            for s in result["segments"] for w in s.get("words", [])]


def quiet_mask(audio, hop=0.01):
    """True where the 10 ms frame is quiet (adaptive threshold from the clip's own levels)."""
    n = int(SR * hop)
    frames = len(audio) // n
    rms = np.sqrt(np.mean(audio[: frames * n].reshape(frames, n) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    speech = np.percentile(db, 90)
    floor = np.percentile(db, 10)
    thr = max(floor + 6, speech - 28)          # quiet = well below speech, a bit above the noise floor
    return db < thr, hop, thr


def plan_cuts(words, audio, dur, a):
    quiet, hop, thr = quiet_mask(audio)
    protect = np.zeros_like(quiet)              # frames that belong to (padded) words
    drop = np.zeros_like(quiet)                 # frames of filler words to remove
    for (w, s, e) in words:
        # Whisper often stretches a word's end up to the next word's start: shrink each word to the
        # frames inside it that actually have sound, so the silence after it becomes visible.
        f0, f1 = max(0, int(s / hop)), min(len(quiet), int(e / hop) + 1)
        loud = np.nonzero(~quiet[f0:f1])[0]
        if len(loud):
            s, e = (f0 + loud[0]) * hop, (f0 + loud[-1] + 1) * hop
        else:
            continue  # no sound at all inside this "word": nothing to protect
        i0 = max(0, int((s - a.pad_start) / hop))
        i1 = min(len(quiet), int((e + a.pad_end) / hop) + 1)
        if a.fillers and FILLERS.match(w):
            drop[int(s / hop):int(e / hop) + 1] = True
        else:
            protect[i0:i1] = True
    cuttable = (quiet & ~protect) | drop

    # find runs of cuttable frames; shorten long ones to keep_gap (centre of the gap is removed)
    cuts = []
    i = 0
    n = len(cuttable)
    while i < n:
        if not cuttable[i]:
            i += 1
            continue
        j = i
        while j < n and cuttable[j]:
            j += 1
        s, e = i * hop, j * hop
        length = e - s
        is_filler = drop[i:j].any()
        edge = s <= 0.02 or e >= dur - 0.02
        if is_filler or length > a.max_gap or (edge and length > a.keep_gap):
            keep = 0.0 if is_filler else a.keep_gap
            if edge:   # leading/trailing silence: keep a short lead-in / tail only
                cs, ce = (0.0, max(0.0, e - a.keep_gap / 2)) if s <= 0.02 else (s + a.keep_gap / 2, dur)
            else:
                cs, ce = s + keep / 2, e - keep / 2
            if ce - cs > 0.05:
                cuts.append((round(cs, 3), round(ce, 3), "filler" if is_filler else "pause"))
        i = j

    keep_segs, t = [], 0.0
    for cs, ce, _ in cuts:
        if cs - t > a.min_keep:
            keep_segs.append((t, cs))
        t = ce
    if dur - t > a.min_keep:
        keep_segs.append((t, dur))
    return keep_segs, cuts, thr


def remap(t, segs):
    """Source time -> output time (None if t falls in a removed part)."""
    out = 0.0
    for s, e in segs:
        if s <= t <= e:
            return out + (t - s)
        out += e - s
    return None


def render(src, dst, segs, fade=0.015):
    parts, labels = [], []
    for k, (s, e) in enumerate(segs):
        d = e - s
        parts.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{k}]")
        parts.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:st=0:d={fade},afade=t=out:st={max(0, d - fade):.3f}:d={fade}[a{k}]")
        labels.append(f"[v{k}][a{k}]")
    graph = ";".join(parts) + f";{''.join(labels)}concat=n={len(segs)}:v=1:a=1[v][a]"
    script = pathlib.Path(dst).with_suffix(".filter.txt")
    script.write_text(graph)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-filter_complex_script", str(script),
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dst)],
                   check=True)
    script.unlink()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--lang", default="ms", help="Whisper language code (ms, ar, en, ...)")
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--words", help="existing Whisper JSON (skip transcription)")
    ap.add_argument("--max-gap", type=float, default=0.6, help="pauses longer than this are shortened (s)")
    ap.add_argument("--keep-gap", type=float, default=0.25, help="length a long pause is shortened to (s)")
    ap.add_argument("--pad-start", type=float, default=0.10)
    ap.add_argument("--pad-end", type=float, default=0.15)
    ap.add_argument("--min-keep", type=float, default=0.15)
    ap.add_argument("--fillers", action="store_true", help="also remove filler words (err, emm, aaa...)")
    ap.add_argument("--dry-run", action="store_true", help="only print the cut list")
    a = ap.parse_args()

    src, dst = pathlib.Path(a.src), pathlib.Path(a.dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    audio = load_audio(src)
    dur = len(audio) / SR
    if a.words:
        result = json.loads(pathlib.Path(a.words).read_text())
    else:
        result = transcribe(src, a.lang, a.model, dst.with_suffix(".whisper.json"))
    words = words_from(result)

    segs, cuts, thr = plan_cuts(words, audio, dur, a)
    new_dur = sum(e - s for s, e in segs)
    print(f"{src.name}: {dur:.2f}s -> {new_dur:.2f}s  (-{dur - new_dur:.2f}s, {len(cuts)} cuts, quiet<{thr:.1f} dBFS)")
    for cs, ce, kind in cuts:
        print(f"  cut {cs:7.2f} - {ce:7.2f}  ({ce - cs:.2f}s {kind})")

    mapped = []
    for (w, s, e) in words:
        ns, ne = remap(s, segs), remap(e, segs)
        if ns is not None and ne is not None:
            mapped.append([w, round(ns, 3), round(ne, 3)])
    dst.with_suffix(".cuts.json").write_text(json.dumps(dict(
        source=str(src.name), source_duration=round(dur, 3), duration=round(new_dur, 3),
        keep=[[round(s, 3), round(e, 3)] for s, e in segs],
        removed=[[cs, ce, k] for cs, ce, k in cuts], words=mapped), ensure_ascii=False, indent=1))
    if not a.dry_run:
        render(src, dst, segs)
        print("wrote", dst)


if __name__ == "__main__":
    main()
