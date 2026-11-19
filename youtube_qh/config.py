"""Editable settings for the merged YouTube edit of VID QH 2-6 (Arabic talk on Surah At-Tin)."""
import json
import pathlib

ROOT = pathlib.Path(__file__).parent
SHARED = ROOT.parent / "islamic" / "assets"
FONTS = SHARED / "fonts"
ICONS = SHARED / "icons"

# ---------------- output (YouTube 16:9) ----------------
W, H, FPS = 1920, 1080, 30
SAFE = (96, 54, W - 96, H - 54)          # title-safe 90%
ACTION_SAFE = (48, 27, W - 48, H - 27)   # action-safe 95%

# Card holding the source video (848x464 -> scaled, aspect kept, no crop)
CARD_W, CARD_H = 1380, 755
CARD_X, CARD_Y = (W - CARD_W) // 2, 66
CARD_R = 30

# Captions under the card: Arabic (spoken) + Malay translation
AR_CAPTION_Y = 866
MS_CAPTION_Y = 934
CAPTION_SIZE = 44
PROGRESS_Y = 996

# ---------------- palette ----------------
BG_TOP = (6, 14, 30)
BG_BOTTOM = (4, 32, 30)
AURORA = [((16, 185, 129), 0.55), ((212, 175, 55), 0.38), ((20, 120, 160), 0.45), ((6, 78, 59), 0.7)]
ACCENT = (212, 175, 55)      # gold
ACCENT2 = (110, 231, 183)    # mint highlight
WHITE = (248, 245, 236)      # ivory
PARTICLE = (241, 217, 138)

F_TITLE = ROOT / "fonts" / "montserrat-latin-800-normal.woff"
F_SANS = FONTS / "poppins-latin-500-normal.woff"
F_SANS_SB = FONTS / "poppins-latin-600-normal.woff"
F_ARABIC = FONTS / "noto-naskh-arabic-arabic-700-normal.woff"

HIGHLIGHT = set()

# ---------------- titles ----------------
INTRO_KICKER = "TADABBUR AL-QURAN"
INTRO_TITLE = "SURAH AT-TIN"
INTRO_SUB = "سُورَةُ التِّين"
OUTRO_KICKER = "TERIMA KASIH KERANA MENONTON"
OUTRO_TITLE = "JUMPA LAGI"
OUTRO_SUB = "Insya-Allah, di video seterusnya"

INTRO_DUR, INTER_DUR, OUTRO_DUR = 4.2, 2.6, 4.8

# ---------------- clips (filled from transcript/clips.json) ----------------
CLIPS = json.loads((ROOT / "transcript" / "clips.json").read_text())


def timeline():
    segs, clips, cuts = [], [], []
    t = 0.0
    segs.append(dict(kind="intro", start=t, end=t + INTRO_DUR, next_index=1))
    t += INTRO_DUR
    for i, c in enumerate(CLIPS, 1):
        if i > 1:
            segs.append(dict(kind="inter", start=t, end=t + INTER_DUR, prev_index=i - 1, next_index=i,
                             next_title=c["title"]))
            t += INTER_DUR
        seg = dict(kind="clip", start=t, end=t + c["dur"], index=i, **c)
        segs.append(seg)
        clips.append(seg)
        cuts.append(t)
        t += c["dur"]
    segs.append(dict(kind="outro", start=t, end=t + OUTRO_DUR, prev_index=len(CLIPS)))
    t += OUTRO_DUR

    def at(tt):
        for s in segs:
            if s["start"] <= tt < s["end"]:
                return s
        return segs[-1]

    return dict(segments=segs, clips=clips, cuts=cuts, duration=t, at=at)
