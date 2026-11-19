"""content.py + Whisper word timings -> transcript/clips.json (times relative to the trimmed clip).

usage: python build_clips.py <dir with qh*.mov and qh*_ar.json>
"""
import json
import pathlib
import subprocess
import sys

from content import CLIPS

ROOT = pathlib.Path(__file__).parent


def whisper_words(d, stem):
    words = []
    if stem == "qh2":  # first 30 s re-transcribed in two chunks
        for f, off, lo, hi in [("qh2_ar_0.json", 0, 0, 13.0), ("qh2_ar_13.json", 13, 13.0, 30), ("qh2_ar.json", 0, 30, 1e9)]:
            for s in json.loads((d / f).read_text())["segments"]:
                for w in s["words"]:
                    st = w["start"] + off
                    if lo <= st < hi:
                        words.append((w["word"].strip(), st, w["end"] + off))
        return words
    for s in json.loads((d / f"{stem}_ar.json").read_text())["segments"]:
        for w in s["words"]:
            words.append((w["word"].strip(), w["start"], w["end"]))
    return words


def duration(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout)


def align(tokens, ws, c0, c1):
    """Assign (start, end) to each corrected token."""
    if len(ws) == len(tokens):
        out = []
        for i, (tok, (_, s, e)) in enumerate(zip(tokens, ws)):
            nxt = ws[i + 1][1] if i + 1 < len(ws) else c1
            out.append([tok, s, min(max(e, s + 0.12), nxt, c1)])
        return out
    s0 = ws[0][1] if ws else c0
    total = sum(len(t) for t in tokens)
    out, t = [], s0
    for tok in tokens:
        d = (c1 - s0) * len(tok) / total
        out.append([tok, t, t + d])
        t += d
    return out


def main():
    d = pathlib.Path(sys.argv[1])
    clips = []
    for c in CLIPS:
        stem = c["file"][:-4]
        ws = whisper_words(d, stem)
        inp = c["inp"]
        out = c["out"] if c["out"] else duration(d / c["file"])
        caps = []
        for (c0, c1, ar, ms) in c["captions"]:
            tokens = ar.split()
            inside = [w for w in ws if c0 - 0.05 <= w[1] < c1]
            words = align(tokens, inside, c0, c1)
            caps.append(dict(start=c0 - inp, end=c1 - inp, ms=ms,
                             ar=[[w, round(s - inp, 3), round(e - inp, 3)] for w, s, e in words]))
        clips.append(dict(file=c["file"], inp=inp, dur=round(out - inp, 3), title=c["title"], captions=caps,
                          callouts=[[a - inp, b - inp, ic, ti, bo, arb] for a, b, ic, ti, bo, arb in c["callouts"]]))
        print(f'{c["file"]}: {out - inp:.2f}s, {len(caps)} captions')
    (ROOT / "transcript" / "clips.json").write_text(json.dumps(clips, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
