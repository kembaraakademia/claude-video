"""All editable settings for the IMG_3434 Islamic cinematic edit: palette, timeline, audio levels."""
import json
import pathlib

ROOT = pathlib.Path(__file__).parent
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"
ICONS = ASSETS / "icons"

# ---------------- source (analysed with ffprobe) ----------------
SRC_NAME = "IMG_3434.mov"   # 3840x2160 16:9 landscape, HEVC 10-bit HLG (HDR), ~30 fps (VFR), 72.96 s
W, H = 3840, 2160
FPS = 30
DURATION = 72.956

# Title-safe area (90%) for 16:9 delivery; all text/graphics stay inside it.
SAFE = (192, 108, W - 192, H - 108)  # x0, y0, x1, y1

# ---------------- palette ----------------
EMERALD = (6, 78, 59)
GOLD = (212, 175, 55)
GOLD_LIGHT = (241, 217, 138)
IVORY = (248, 245, 236)
NAVY = (16, 24, 40)

# ---------------- fonts ----------------
F_ARABIC = FONTS / "noto-naskh-arabic-arabic-700-normal.woff"   # clean harakat stacking
F_ARABIC_REG = FONTS / "noto-naskh-arabic-arabic-400-normal.woff"
F_SANS = FONTS / "poppins-latin-500-normal.woff"
F_SANS_SB = FONTS / "poppins-latin-600-normal.woff"
F_SANS_LIGHT = FONTS / "poppins-latin-300-normal.woff"

# ---------------- Arabic recitation cards (lower third, captions hidden meanwhile) ----------------
# (start, end, arabic text, reference or None). Text = standard Qur'anic wording with full harakat.
ARABIC = [
    (4.25, 8.05, "أَعُوذُ بِاللَّهِ مِنَ الشَّيْطَانِ الرَّجِيمِ", None),
    (8.35, 12.45, "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ", None),
    (12.70, 19.25, "مَا عَلَى الْمُحْسِنِينَ مِن سَبِيلٍ", "Surah At-Taubah  ·  9:91"),
    (19.30, 20.90, "صَدَقَ اللَّهُ الْعَظِيمُ", None),
    (43.90, 46.70, "إِنَّ اللَّهَ لَا يُضِيعُ أَجْرَ الْمُحْسِنِينَ", "Surah At-Taubah  ·  9:120"),
]

# ---------------- side panel scenes (left side, beside the speaker) ----------------
# Each: start, end, icon (assets/icons/<name>.png), kicker (small gold label), body text,
#       arabic (optional single word/phrase), highlight words in body (gold)
PANELS = [
    dict(start=0.35, end=4.10, icon="crescent_star", kicker="TAZKIRAH", body="Surah At-Taubah", arabic=None),
    dict(start=12.70, end=20.85, icon="quran_rehal", kicker="AL-QURAN", body="Surah At-Taubah\nAyat 91", arabic=None),
    dict(start=21.00, end=29.20, icon="star8", kicker="AL-MUHSININ",
         body="Orang-orang yang berusaha\nmemperbaiki amalannya", arabic="الْمُحْسِنِينَ"),
    dict(start=29.35, end=36.85, icon="tasbih", kicker="PENGAJARAN",
         body="Setiap amalan kebaikan\npasti ada cacat dan celanya", arabic=None, highlight=["cacat", "celanya"]),
    dict(start=40.15, end=51.50, icon="quran_rehal", kicker="AYAT SELEPASNYA", body="Surah At-Taubah\nAyat 120",
         arabic=None,
         swap=(46.72, "Allah tidak akan sesekali\nmenyia-nyiakan amalan\nyang kita buat", ["menyia-nyiakan"])),
    dict(start=51.65, end=56.70, icon="lantern", kicker="PESANAN", body="Dr. Fauzi", arabic=None),
    dict(start=56.85, end=65.40, icon="lantern", kicker="PESANAN",
         body="Walaupun amalan kita ini ada\ncacat dan celanya, tetapi jangan\nlupa untuk berusaha memperbaiki\ndemi hari seterusnya",
         arabic=None, highlight=["berusaha", "memperbaiki"], icon_swap=(63.55, "sunrise")),
]

# ---------------- Malay captions (from Whisper large-v3 word timestamps) ----------------
CAPTION_EXCLUDE = [(0.0, 20.9), (44.0, 46.70)]   # Arabic recitation -> shown as Arabic cards instead
CAPTION_FIX = {"celah": "cela", "Ikhraq": None, "Yuniza": None}  # None = hide (name unclear)
CAPTION_HIGHLIGHT = {"berusaha", "memperbaiki", "amalan", "amalannya", "kebaikan", "Allah", "menyia-nyiakan"}


def caption_words():
    """Whisper words grouped per spoken sentence (segment): [[ [text, start, end], ... ], ...]"""
    data = json.loads((ROOT / "transcript" / "IMG_3434_whisper.json").read_text())
    sentences = []
    for seg in data["segments"]:
        words = []
        for w in seg["words"]:
            txt, st, en = w["word"].strip(), w["start"], w["end"]
            if any(a <= st < b for a, b in CAPTION_EXCLUDE):
                continue
            key = txt.strip(".,?!")
            if key in CAPTION_FIX:
                if CAPTION_FIX[key] is None:
                    continue
                txt = txt.replace(key, CAPTION_FIX[key])
            if txt.startswith("-") and words:  # "orang" "-orang" -> "orang-orang"
                words[-1][0] += txt
                words[-1][2] = en
                continue
            words.append([txt, st, en])
        if words:
            sentences.append(words)
    return sentences


def caption_chunks(max_words=6):
    """Split each sentence into balanced chunks of <= max_words (never mixes two sentences)."""
    chunks = []
    for sent in caption_words():
        n = -(-len(sent) // max_words)
        size = -(-len(sent) // n)
        for i in range(0, len(sent), size):
            chunks.append(sent[i:i + size])
    return chunks


# ---------------- camera ----------------
FOCUS = (1920, 760)       # speaker's face (zoom anchor)
ZOOM_KEYS = [(0, 1.00), (12.7, 1.03), (20.9, 1.035), (21.5, 1.02), (43.9, 1.045), (51.6, 1.03),
             (56.8, 1.04), (65.4, 1.06), (72.96, 1.07)]

# ---------------- intro / outro ----------------
FADE_IN = (0.0, 1.2)
OUTRO_START = 68.3     # emerald veil + mosque silhouette
FADE_OUT = (72.05, 72.95)

# ---------------- transitions (soft light sweep + whoosh), placed in narrator pauses ----------------
TRANSITIONS = [4.15, 12.55, 20.95, 29.25, 36.9, 51.55, 65.6]

# ---------------- audio ----------------
AUDIO = dict(
    target_lufs=-16.0,
    true_peak=-1.0,
    music_gap_db=-14.0,       # music level (relative to voice LUFS) in narrator pauses
    music_duck_db=-23.0,      # music level under dialogue (18-25 dB below voice)
    duck_attack_ms=180,
    duck_release_ms=800,
    vad_threshold_db=-42.0,   # voice activity threshold on processed voice (dBFS RMS)
    vad_hold_ms=350,
    sfx_db=-20.0,             # SFX bus relative to voice
)
