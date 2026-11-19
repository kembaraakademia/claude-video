"""QH3 reel — "Sebab Nuzul Surah At-Tin" (Arabic talk) as a 9:16 reel, following reference/ref2 style
(inspiration only): dark cinematic talking head, glitch-in hook, big title + green pill, bright UI screens
with the speaker inside a video card, chat-bubble questions, handwritten green annotations, blur-to-title
for the ayah, radar rings + bracket label, short word-synced captions with green active word.

Source: raw_footage/VID_QH_3.MOV -> tools/cut_pauses.py -> qh3_tight.mp4 (+ .cuts.json)
Text: reviewed Arabic + Malay translation from youtube_qh/transcript/clips.json (no new message added).

usage: python edit.py [--preview 3,15,40] [--guides]
"""
import argparse
import json
import math
import pathlib
import subprocess
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent.parent
CLIP = HERE / "qh3_tight.mp4"
CUTS = json.loads((HERE / "qh3_tight.cuts.json").read_text())
EXPORT = ROOT / "export"
FONTS = ROOT / "assets" / "fonts"

W, H, FPS = 1080, 1920, 30
SW, SH = 848, 464
DUR = CUTS["duration"]
SAFE = dict(top=250, bottom=1920 - 440, left=60, right=1080 - 150)
UI_CX, UI_W = (60 + 930) // 2 + 5, 860          # UI column centred inside the TikTok/IG safe width

DARK = (10, 12, 16)
GREEN = (52, 211, 120)
GREEN_D = (22, 163, 74)
GREEN_BG = (226, 247, 233)
PAPER = (246, 247, 244)
INK = (20, 24, 31)
GREY = (120, 128, 140)
WHITE = (255, 255, 255)

F_BLACK = FONTS / "inter-latin-900-normal.woff"
F_XB = FONTS / "inter-latin-800-normal.woff"
F_B = FONTS / "inter-latin-700-normal.woff"
F_M = FONTS / "inter-latin-500-normal.woff"
F_HAND = FONTS / "caveat-latin-700-normal.woff"
F_AR = FONTS / "noto-naskh-arabic-arabic-700-normal.woff"


# ---------------------------------------------------------------- time remap (pause cuts)
def remap(t):
    out = 0.0
    for s, e in CUTS["keep"]:
        if t <= e:
            return out + max(0.0, t - s)
        out += e - s
    return out


SRC = [c for c in json.loads((ROOT.parent / "youtube_qh" / "transcript" / "clips.json").read_text())
       if c["file"] == "qh3.mov"][0]
CAPS = [dict(start=remap(c["start"]), end=remap(c["end"]), ms=c["ms"],
             ar=[(w, remap(s), remap(e)) for w, s, e in c["ar"]]) for c in SRC["captions"]]
R = remap   # shorthand for scene timings below (given in ORIGINAL clip seconds)

# scenes (original seconds): talk | ui_chat | ui_reward | ayah
SCENES = [("talk", 0.0, 12.33), ("ui_chat", 12.33, 29.6), ("talk", 29.6, 34.78), ("ui_reward", 34.78, 46.05),
          ("ayah", 46.05, 51.78), ("talk", 51.78, 57.0)]
SCENES = [(k, R(a), R(b)) for k, a, b in SCENES]


def scene_at(t):
    for k, a, b in SCENES:
        if a <= t < b:
            return k, a, b
    return SCENES[-1]


# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def eout(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def back(x, s=1.6):
    x = clamp(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def win(t, a, b, fi=0.25, fo=0.25):
    return 0.0 if t < a or t > b else ease((t - a) / fi) * ease((b - t) / fo)


@lru_cache(None)
def font(p, s):
    return ImageFont.truetype(str(p), s, layout_engine=ImageFont.Layout.RAQM)


def amul(im, a):
    if a >= 0.999:
        return im
    arr = np.asarray(im).copy()
    arr[..., 3] = (arr[..., 3] * a).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def paste(cv, im, cx, cy, a=1.0, sc=1.0, rot=0.0):
    if a <= 0.004 or sc <= 0.01:
        return
    if abs(sc - 1) > 1e-3:
        im = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.BICUBIC)
    if abs(rot) > 0.05:
        im = im.rotate(rot, Image.BICUBIC, expand=True)
    im = amul(im, a)
    x, y = round(cx - im.width / 2), round(cy - im.height / 2)
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + im.width), min(H, y + im.height)
    if x1 > x0 and y1 > y0:
        cv.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


@lru_cache(None)
def txt(s, fp, size, color, pad=8):
    f = font(fp, size)
    kw = dict(direction="rtl", language="ar") if fp == F_AR else {}
    bb = f.getbbox(s, **kw)
    asc, desc = f.getmetrics()
    p = int(size * 0.3) if fp == F_AR else pad
    im = Image.new("RGBA", (bb[2] - bb[0] + 2 * p, asc + desc + 2 * p), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((p - bb[0], p), s, font=f, fill=color, **kw)
    return im


def shadowed(im, blur=12, alpha=0.5, dy=8):
    pad = blur * 3
    out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad + dy), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 255))
    sh.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    out.alpha_composite(sh, (pad, pad + dy))
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(im, (pad, pad))
    return out


@lru_cache(None)
def sh_txt(s, fp, size, color, blur=10, alpha=0.6):
    return shadowed(txt(s, fp, size, color), blur, alpha, 6)


def rrect(w, h, r, fill, outline=None, width=0):
    s = 2
    im = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * s - 1, h * s - 1), r * s, fill=fill, outline=outline,
                                         width=width * s)
    return im.resize((w, h), Image.LANCZOS)


@lru_cache(None)
def pill(s, size=56, fg=INK, bg=GREEN):
    t = txt(s, F_BLACK, size, fg, pad=4)
    p = rrect(t.width + size, t.height + int(size * 0.35), (t.height + int(size * 0.35)) // 2, bg + (255,))
    p.alpha_composite(t, (size // 2, int(size * 0.175)))
    return p


@lru_cache(None)
def check_pill(s, size=34):
    """Green pill with a drawn check mark (Inter has no ✓ glyph)."""
    t = txt(s, F_BLACK, size, WHITE, pad=4)
    h = t.height + int(size * 0.35)
    w = t.width + size + h
    p = rrect(w, h, h // 2, GREEN_D + (255,))
    d = ImageDraw.Draw(p)
    cx, cy, r = size // 2 + h * 0.35, h / 2, h * 0.28
    d.line([(cx - r, cy), (cx - r * 0.25, cy + r * 0.7), (cx + r, cy - r * 0.75)], fill=WHITE, width=max(3, size // 9),
           joint="curve")
    p.alpha_composite(t, (int(size // 2 + h * 0.75), int(size * 0.175)))
    return p


@lru_cache(None)
def arrow_note(left, right, color=GREEN):
    """Handwritten 'left  ->  right' with a drawn arrow (Caveat has no → glyph)."""
    a, b = txt(left, F_HAND, 62, color), txt(right, F_HAND, 62, color)
    gap = 90
    im = Image.new("RGBA", (a.width + gap + b.width, max(a.height, b.height)), (0, 0, 0, 0))
    im.alpha_composite(a, (0, 0))
    im.alpha_composite(b, (a.width + gap, 0))
    d = ImageDraw.Draw(im)
    y = im.height * 0.55
    x0, x1 = a.width + 10, a.width + gap - 14
    d.line([(x0, y + 4), ((x0 + x1) / 2, y - 6), (x1, y)], fill=color, width=6, joint="curve")
    d.line([(x1 - 18, y - 14), (x1, y), (x1 - 20, y + 12)], fill=color, width=6, joint="curve")
    return shadowed(im, 8, 0.6, 4)


# ---------------------------------------------------------------- source frames -> looks
def grade_talk(fr):
    """Moody cinematic grade (darker, contrast, teal shadows) — hides upscale softness."""
    a = np.asarray(fr).astype(np.float32) / 255
    a = np.clip((a - 0.5) * 1.12 + 0.5 - 0.06, 0, 1) ** 1.08
    lum = a.mean(axis=2, keepdims=True)
    tint = np.array([0.94, 1.0, 1.05], np.float32)            # cool shadows
    a = a * (tint * (1 - lum) + lum) * 0.92
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def talk_frame(fr, t):
    """9:16 crop around the speaker with a slow push."""
    z = 1.0 + 0.06 * ease(((t % 12) / 12))
    ch = SH / z
    cw = ch * 9 / 16
    cx, cy = 415, 232
    x0 = clamp(cx - cw / 2 + 4 * math.sin(t * 0.6), 0, SW - cw)
    y0 = clamp(cy - ch / 2, 0, SH - ch)
    img = fr.transform((W, H), Image.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.BICUBIC)
    img = img.filter(ImageFilter.UnsharpMask(2, 80, 2))
    return grade_talk(img)


@lru_cache(None)
def vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W / 2) / (W * 0.6), (yy - H * 0.45) / (H * 0.6))
    a = (np.clip(r - 0.45, 0, 1) ** 1.4 * 230).astype(np.uint8)
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., 3] = a
    return Image.fromarray(arr, "RGBA")


GRAIN = [Image.fromarray(np.random.default_rng(i).integers(0, 255, (H // 2, W // 2), dtype=np.uint8), "L")
         .resize((W, H), Image.NEAREST) for i in range(6)]


def add_grain(img, t, amount=10):
    g = GRAIN[int(t * FPS) % 6]
    noise = Image.merge("RGB", (g, g, g))
    return Image.blend(img, Image.blend(img, noise, 0.5), amount / 255 * 2)


@lru_cache(None)
def card_mask(w, h, r):
    return rrect(w, h, r, (255, 255, 255, 255)).getchannel("A")


def video_card(fr, w, h, r=34):
    """Speaker clip inside a rounded card (cropped to w:h)."""
    ar = w / h
    if ar > SW / SH:
        cw, ch = SW, SW / ar
    else:
        ch, cw = SH, SH * ar
    x0, y0 = clamp(415 - cw / 2, 0, SW - cw), clamp(232 - ch / 2, 0, SH - ch)
    im = fr.transform((w, h), Image.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.BICUBIC)
    im = im.filter(ImageFilter.UnsharpMask(1.5, 60, 2)).convert("RGBA")
    im.putalpha(card_mask(w, h, r))
    return shadowed(im, 22, 0.28, 16)


# ---------------------------------------------------------------- captions
def cap_groups():
    out = []
    for c in CAPS:
        ws = c["ar"]
        n = max(1, math.ceil(len(ws) / 3))
        size = math.ceil(len(ws) / n)
        for i in range(0, len(ws), size):
            g = ws[i:i + size]
            nxt = ws[i + size][1] if i + size < len(ws) else c["end"] + 0.25
            out.append(dict(words=g, start=g[0][1] - 0.06, end=nxt - 0.061, ms=c["ms"], cap=c))
    for a, b in zip(out, out[1:]):
        a["end"] = min(a["end"], b["start"] - 0.001)
    return out


GROUPS = cap_groups()


def draw_captions(cv, t, mode):
    """mode 'dark' (white text, lower-middle) or 'light' (ink text, top)."""
    for g in GROUPS:
        if not (g["start"] <= t <= g["end"]):
            continue
        y = 1250 if mode == "dark" else SAFE["top"] + 90
        base = WHITE if mode == "dark" else INK
        act = GREEN if mode == "dark" else GREEN_D
        sprites = []
        for i, (w, ws, we) in enumerate(g["words"]):
            nxt = g["words"][i + 1][1] if i + 1 < len(g["words"]) else g["end"]
            col = act if ws - 0.04 <= t < nxt else (base if t >= ws else base)
            a = 1.0 if t >= ws - 0.04 else 0.35
            sprites.append((txt(w, F_AR, 66, col), a, ws))
        gap = 14
        total = sum(s.width for s, _, _ in sprites) + gap * (len(sprites) - 1)
        x = W / 2 + total / 2                                   # right-to-left
        for s, a, ws in sprites:
            p = clamp((t - ws + 0.08) / 0.18)
            sc = 1 + 0.12 * (1 - eout(p)) * (a > 0.5)
            if mode == "dark":
                paste(cv, shadowed(s, 10, 0.7, 5), x - s.width / 2, y + 5, a, sc)
            else:
                paste(cv, s, x - s.width / 2, y, a, sc)
            x -= s.width + gap
    # Malay translation (whole sentence) under the Arabic line
    for c in CAPS:
        if c["start"] - 0.06 <= t <= c["end"] + 0.25:
            a = win(t, c["start"] - 0.06, c["end"] + 0.25, 0.15, 0.15)
            col = (225, 230, 235) if mode == "dark" else GREY
            y = 1338 if mode == "dark" else SAFE["top"] + 172
            n, fs, lh = (34, 34, 46) if mode == "dark" else (44, 30, 40)
            for li, line in enumerate(wrap(c["ms"], n)[:3 if mode == "dark" else 2]):
                s = txt(line, F_B, fs, col)
                paste(cv, shadowed(s, 8, 0.7, 4) if mode == "dark" else s, W / 2, y + li * lh, a)


def wrap(s, n):
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    return lines


# ---------------------------------------------------------------- talk overlays
def hook_title(cv, t):
    """0-6 s: 'Pernah tanya…' -> 'KENAPA SURAH' + green pill 'AT-TIN DITURUNKAN?' (from the spoken question)."""
    a = win(t, R(0.3), R(6.1), 0.2, 0.3)
    if a <= 0:
        return
    k1 = clamp((t - R(0.3)) / 0.3)
    paste(cv, sh_txt("Pernah tanya diri sendiri…", F_B, 40, WHITE), W / 2, 560, a * k1)
    if t >= R(2.96):
        p = (t - R(2.96)) / 0.35
        paste(cv, sh_txt("Kenapa Surah", F_BLACK, 104, WHITE, 14, 0.7), W / 2, 660, a, 0.8 + 0.2 * back(p))
    if t >= R(4.6):
        p = (t - R(4.6)) / 0.35
        paste(cv, shadowed(pill("At-Tin diturunkan?", 62), 14, 0.5, 8), W / 2, 790, a, 0.6 + 0.4 * back(p, 2.2),
              -3 * (1 - eout(p)))


def nuzul_title(cv, t):
    a = win(t, R(6.3), R(11.9), 0.2, 0.3)
    if a <= 0:
        return
    p = (t - R(6.3)) / 0.35
    paste(cv, sh_txt("Kisahnya bermula…", F_B, 40, WHITE), W / 2, 560, a * clamp(p))
    paste(cv, sh_txt("SEBAB NUZUL", F_BLACK, 112, WHITE, 14, 0.7), W / 2, 665, a, 0.85 + 0.15 * back(p))
    if t >= R(8.86):   # handwritten note: "sahabat -> Nabi s.a.w."
        q = (t - R(8.86)) / 0.4
        note = arrow_note("para sahabat", "Nabi s.a.w.")
        paste(cv, note, W / 2 + 60, 790, a * clamp(q * 2), 0.8 + 0.2 * back(q), -4)


@lru_cache(None)
def hand_note(s, color=GREEN):
    return shadowed(txt(s, F_HAND, 62, color), 8, 0.6, 4)


def answer_title(cv, t):
    a = win(t, R(29.9), R(34.75), 0.2, 0.3)
    if a <= 0:
        return
    p = (t - R(29.9)) / 0.35
    paste(cv, sh_txt("Lalu turunlah surah ini sebagai", F_B, 38, WHITE), W / 2, 560, a * clamp(p))
    if t >= R(32.4):
        q = (t - R(32.4)) / 0.35
        paste(cv, sh_txt("Jawapan", F_BLACK, 120, WHITE, 14, 0.7), W / 2, 670, a, 0.8 + 0.2 * back(q))
    if t >= R(33.3):
        q = (t - R(33.3)) / 0.35
        paste(cv, shadowed(pill("& khabar gembira", 60), 14, 0.5, 8), W / 2, 800, a, 0.6 + 0.4 * back(q, 2.2), 3 * (1 - eout(q)))


def radar(cv, t):
    """End: radar rings around the speaker + bracket label 'Pahala kekal' + note 'kemurahan Ilahi'."""
    t0 = R(51.8)
    a = win(t, t0, DUR + 1, 0.3, 0.3)
    if a <= 0:
        return
    d = ImageDraw.Draw(cv)
    cx, cy = W / 2, 900
    for i in range(4):
        ph = ((t - t0) * 0.55 + i / 4) % 1
        r = 140 + 520 * ph
        al = int(170 * (1 - ph) * a)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=GREEN + (al,), width=4)
    if t >= R(52.18):
        q = (t - R(52.18)) / 0.35
        paste(cv, bracket_label("Pahala kekal"), W / 2, 520, a, 0.7 + 0.3 * back(q, 2))
    if t >= R(54.5):
        q = (t - R(54.5)) / 0.4
        paste(cv, hand_note("kemurahan Ilahi!"), W / 2 + 140, 640, a * clamp(q * 2), 0.8 + 0.2 * back(q), -5)


@lru_cache(None)
def bracket_label(s):
    t = txt(s, F_BLACK, 84, WHITE, pad=6)
    w, h = t.width + 60, t.height + 30
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    L, th = 34, 6
    for (x, y, dx, dy) in [(0, 0, 1, 1), (w - 1, 0, -1, 1), (0, h - 1, 1, -1), (w - 1, h - 1, -1, -1)]:
        d.line((x, y, x + dx * L, y), fill=WHITE, width=th)
        d.line((x, y, x, y + dy * L), fill=WHITE, width=th)
    for x, y in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        d.rectangle((x - 7, y - 7, x + 7, y + 7), fill=GREEN)
    im.alpha_composite(t, (30, 15))
    return shadowed(im, 12, 0.6, 6)


def glitch(img, t):
    """Opening glitch-in (0-0.45 s): RGB split + slice offsets + blur."""
    k = 1 - clamp(t / 0.45)
    if k <= 0:
        return img
    r, g, b = img.split()
    off = int(28 * k)
    r = r.transform(img.size, Image.AFFINE, (1, 0, off, 0, 1, 0))
    b = b.transform(img.size, Image.AFFINE, (1, 0, -off, 0, 1, 0))
    img = Image.merge("RGB", (r, g, b))
    rng = np.random.default_rng(int(t * 100))
    arr = np.asarray(img).copy()
    for _ in range(int(10 * k)):
        y = rng.integers(0, H - 80)
        hgt = rng.integers(20, 80)
        arr[y:y + hgt] = np.roll(arr[y:y + hgt], rng.integers(-90, 90), axis=1)
    return Image.fromarray(arr).filter(ImageFilter.GaussianBlur(6 * k))


# ---------------------------------------------------------------- UI screens
@lru_cache(None)
def paper_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    g = np.exp(-((xx - W * 1.05) / (W * 0.45)) ** 2) * 0.9                 # green glow on the right
    base = np.array(PAPER, np.float32)
    tint = np.array(GREEN_BG, np.float32)
    arr = base[None, None] * (1 - g[..., None]) + tint[None, None] * g[..., None]
    img = Image.fromarray(arr.astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img)
    for x in range(0, W, 60):        # faint dot grid
        for y in range(0, H, 60):
            d.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=(210, 214, 208, 255))
    return img


@lru_cache(None)
def app_header(title, sub):
    w, h = UI_W, 120
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 18, 76, 94), 22, fill=GREEN_D)
    d.polygon([(26, 40), (26, 72), (54, 56)], fill=WHITE)
    im.alpha_composite(txt(title, F_BLACK, 44, INK, pad=2), (96, 12))
    im.alpha_composite(txt(sub, F_M, 28, GREY, pad=2), (98, 66))
    return im


@lru_cache(None)
def bubble(s, hi=False, w=700):
    lines = wrap(s, 30)
    th = [txt(l, F_B if hi else F_M, 38, INK, pad=2) for l in lines]
    h = 44 + sum(x.height for x in th)
    bg = (GREEN_BG if hi else WHITE) + (255,)
    b = rrect(w, h, 30, bg, (GREEN_D + (255,)) if hi else ((228, 230, 226, 255)), 3 if hi else 2)
    y = 22
    for x in th:
        b.alpha_composite(x, (30, y))
        y += x.height
    return shadowed(b, 14, 0.12, 8)


def ui_chat(fr, t, a0, b0):
    img = paper_bg().copy()
    k_in = eout((t - a0) / 0.45)
    paste(img, app_header("Sebab Nuzul", "Soalan para sahabat kepada Nabi s.a.w."), UI_CX, 585 - (1 - k_in) * 40,
          k_in)
    paste(img, video_card(fr, UI_W, 400), UI_CX, 862 - (1 - k_in) * 80, k_in, 0.92 + 0.08 * k_in)
    items = [(12.36, "Orang beriman yang semakin lanjut usianya…", False),
             (16.52, "…ditimpa kelemahan teruk pada tubuh atau akal", False),
             (20.36, "…tak mampu solat berdiri, atau puasa seperti ketika muda", False),
             (26.26, "Adakah pahalanya berkurang di sisi Allah?", True)]
    shown = [(R(ts), s, hi) for ts, s, hi in items if t >= R(ts) - 0.05]
    # chat feel: newest bubble at the bottom (ends above the safe line), previous one above it; keep 2
    bottom = SAFE["bottom"] - 10
    for i, (ts, s, hi) in enumerate(reversed(shown[-2:])):
        bb = bubble(s, hi)
        p = (t - ts) / 0.35
        cy = bottom - bb.height / 2 + 30
        x = UI_CX - 40 if not hi else UI_CX
        paste(img, bb, x, cy + ((1 - eout(p)) * 40 if i == 0 else 0), clamp(p * 2.5) * (1 - 0.3 * i), 0.9 + 0.1 * back(p))
        bottom = cy - bb.height / 2 + 30 - 4
    return img


@lru_cache(None)
def reward_card():
    w, h = UI_W, 400
    c = rrect(w, h, 36, WHITE + (255,), (228, 230, 226, 255), 2)
    c.alpha_composite(txt("Pahala orang beriman", F_BLACK, 44, INK, pad=2), (44, 36))
    c.alpha_composite(txt("Allah memberitahu kita…", F_M, 28, GREY, pad=2), (46, 94))
    return c


def ui_reward(fr, t, a0, b0):
    img = paper_bg().copy()
    k_in = eout((t - a0) / 0.45)
    paste(img, app_header("At-Tin", "Jawapan & khabar gembira daripada Allah"), UI_CX, 585 - (1 - k_in) * 40, k_in)
    paste(img, video_card(fr, UI_W, 400), UI_CX, 862 - (1 - k_in) * 80, k_in, 0.92 + 0.08 * k_in)
    cy = 1262
    c = reward_card().copy()
    d = ImageDraw.Draw(c)
    # two bars: "Ketika muda" (full) and "Ketika tua & tak mampu beramal" (fills to full too)
    rows = [("Ketika muda", 1.0, R(34.9)), ("Bila tua & tak mampu beramal", 1.0, R(38.2))]
    for i, (label, full, ts) in enumerate(rows):
        y = 140 + i * 82
        c.alpha_composite(txt(label, F_B, 30, INK, pad=2), (46, y))
        d.rounded_rectangle((46, y + 46, UI_W - 46, y + 78), 16, fill=(236, 238, 234))
        p = eout((t - ts) / 1.2) * full
        if p > 0.01:
            d.rounded_rectangle((46, y + 46, 46 + (UI_W - 92) * p, y + 78), 16, fill=GREEN_D)
    paste(img, shadowed(c, 16, 0.12, 10), UI_CX, cy, k_in)
    # check pills as he says: tetap, berterusan, tidak terputus
    x = UI_CX - UI_W / 2 + 46                       # pills laid out left -> right by their real widths
    for ts, s in [(41.4, "Tetap"), (42.8, "Berterusan"), (44.68, "Tidak terputus")]:
        pl = check_pill(s, 30)
        if t >= R(ts):
            q = (t - R(ts)) / 0.3
            paste(img, pl, x + pl.width / 2, cy - 200 + 345, clamp(q * 2), 0.7 + 0.3 * back(q, 2.4))
        x += pl.width + 14
    return img


def ayah_scene(fr, t, a0, b0):
    base = talk_frame(fr, t)
    k = ease((t - a0) / 0.5) * ease((b0 - t) / 0.4)
    small = base.resize((W // 8, H // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
    img = Image.blend(base, small.resize((W, H), Image.BICUBIC), k)
    img = Image.blend(img, Image.new("RGB", (W, H), DARK), 0.45 * k).convert("RGBA")
    a = k
    paste(img, sh_txt("Firman Allah Ta'ala", F_B, 40, WHITE), W / 2, 700, a * clamp((t - a0) / 0.4))
    if t >= R(48.98) - 0.1:
        p = (t - R(48.98) + 0.1) / 0.6
        ay = shadowed(txt("فَلَهُمْ أَجْرٌ غَيْرُ مَمْنُونٍ", F_AR, 96, WHITE), 14, 0.7, 6)
        paste(img, ay, W / 2, 860, a * clamp(p * 1.5), 0.9 + 0.1 * eout(p))
        paste(img, shadowed(pill("At-Tin : 6", 46), 12, 0.5, 6), W / 2, 1010, a * clamp(p * 1.5 - 0.3),
              0.7 + 0.3 * back(p, 2))
        for li, line in enumerate(wrap("“Maka bagi mereka pahala yang tidak putus-putus”", 30)):
            paste(img, sh_txt(line, F_B, 42, (230, 236, 240)), W / 2, 1120 + li * 56, a * clamp(p * 1.5 - 0.6))
    return img


# ---------------------------------------------------------------- frame
def render(fr, t, guides=False):
    kind, a0, b0 = scene_at(t)
    if kind == "talk":
        img = talk_frame(fr, t).convert("RGBA")
        img.alpha_composite(vignette())
        hook_title(img, t)
        nuzul_title(img, t)
        answer_title(img, t)
        radar(img, t)
        draw_captions(img, t, "dark")
    elif kind == "ui_chat":
        img = ui_chat(fr, t, a0, b0)
        draw_captions(img, t, "light")
    elif kind == "ui_reward":
        img = ui_reward(fr, t, a0, b0)
        draw_captions(img, t, "light")
    else:
        img = ayah_scene(fr, t, a0, b0)
        img.alpha_composite(vignette())
    out = img.convert("RGB")
    # scene transitions: quick whip (blur + push) at each boundary
    for k, a, b in SCENES[1:]:
        d = t - a
        if -0.12 < d < 0.18:
            m = 1 - abs(d) / 0.18
            out = out.filter(ImageFilter.BoxBlur(int(18 * m))) if m > 0.05 else out
    if kind == "talk":
        out = add_grain(out, t, 8)
    out = glitch(out, t)
    if t > DUR - 0.35:
        out = Image.blend(out, Image.new("RGB", (W, H), DARK), clamp((t - DUR + 0.35) / 0.35))
    if guides:
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        red = (255, 0, 0, 70)
        d.rectangle((0, 0, W, SAFE["top"]), fill=red)
        d.rectangle((0, SAFE["bottom"], W, H), fill=red)
        d.rectangle((SAFE["right"], SAFE["top"], W, SAFE["bottom"]), fill=red)
        d.rectangle((0, SAFE["top"], SAFE["left"], SAFE["bottom"]), fill=red)
        out = out.convert("RGBA")
        out.alpha_composite(ov)
        out = out.convert("RGB")
    return out


# ---------------------------------------------------------------- audio
SR = 48000


def audio(outdir):
    import pyloudnorm as pyln
    from scipy.io import wavfile
    from scipy.signal import butter, sosfilt
    rng = np.random.default_rng(5)
    vw = outdir / "_v.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(CLIP), "-af",
                    "highpass=f=80,afftdn=nf=-28,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3000:t=q:w=1.2:g=2.5,"
                    "acompressor=threshold=-22dB:ratio=2.5:attack=8:release=150:makeup=2,aresample=48000",
                    "-ac", "1", str(vw)], check=True)
    _, v = wavfile.read(vw)
    vw.unlink()
    v = v.astype(np.float64) / 32768
    n = len(v)
    meter = pyln.Meter(SR)

    def sos(kind, f):
        return butter(2, f, btype=kind, fs=SR, output="sos")

    def whoosh(d=0.4):
        t = np.arange(int(SR * d)) / SR
        x = np.zeros(len(t))
        nz = rng.standard_normal(len(t))
        pos = np.sin(np.pi * t / d)
        for k, (lo, hi) in enumerate([(300, 900), (800, 2400), (2000, 6000), (4000, 11000)]):
            x += sosfilt(sos("band", [lo, hi]), nz) * np.exp(-((pos * 3 - k) ** 2))
        return x * np.sin(np.pi * t / d) ** 2 * 0.6

    def pop(f=900, d=0.1):
        t = np.arange(int(SR * d)) / SR
        return np.sin(2 * np.pi * np.cumsum(f * np.exp(-t * 18) + 200) / SR) * np.exp(-t * 35) * 0.6

    def glitch_s(d=0.45):
        t = np.arange(int(SR * d)) / SR
        x = sosfilt(sos("band", [500, 6000]), rng.standard_normal(len(t)))
        gate = (np.sin(2 * np.pi * 30 * t) > 0).astype(float)
        return x * gate * np.exp(-t * 5) * 0.5

    def shimmer(d=2.0):
        t = np.arange(int(SR * d)) / SR
        x = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * rng.uniform(2.5, 4)) * rng.uniform(.3, .6)
                for f in [2093, 2637, 3136, 3951, 4699])
        return x * np.clip(t / 0.03, 0, 1) * 0.3

    def ping(f=1760, d=1.2):
        t = np.arange(int(SR * d)) / SR
        return np.sin(2 * np.pi * f * t) * np.exp(-t * 4) * 0.35

    def riser(d=1.0):
        t = np.arange(int(SR * d)) / SR
        return sosfilt(sos("band", [800, 7000]), rng.standard_normal(len(t))) * (t / d) ** 2.2 * 0.5

    ev = [(0.0, glitch_s(), -6), (R(2.96), pop(800), -10), (R(4.6), pop(1100), -8)]
    for k, a, b in SCENES[1:]:
        ev.append((a - 0.2, whoosh(), -6))
    ev += [(R(6.3), pop(700), -10), (R(8.86), pop(1300, 0.08), -12)]
    for ts in (12.36, 16.52, 20.36, 26.26):
        ev.append((R(ts), pop(1000 + 150 * (ts > 26), 0.09), -10))
    ev += [(R(32.4), pop(800), -9), (R(33.3), pop(1100), -9)]
    for ts in (41.4, 42.8, 44.68):
        ev.append((R(ts), pop(1500, 0.07), -11))
    ev += [(R(47.9), riser(), -12), (R(48.9), shimmer(), -8), (R(52.18), ping(), -12), (R(54.5), pop(1200), -11)]
    sfx = np.zeros(n)
    for at, x, g in ev:
        i = int(max(0, at) * SR)
        j = min(n, i + len(x))
        sfx[i:j] += x[: j - i] * 10 ** (g / 20)

    # gentle modern ambient bed (pad + soft pulse), A minor-ish; lowered under the ayah
    t = np.arange(n) / SR
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    chords = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)]
    mus = np.zeros(n)
    bar = 4 * 60 / 84
    for k in range(int(n / SR / bar) + 1):
        ch = chords[k % 4]
        i0, i1 = int(k * bar * SR), min(n, int((k + 1) * bar * SR))
        tt = t[i0:i1] - k * bar
        env = np.minimum(1, tt / 0.5) * np.minimum(1, (bar - tt) / 0.5)
        for m in ch:
            mus[i0:i1] += (np.sin(2 * np.pi * hz(m) * tt) + 0.25 * np.sin(4 * np.pi * hz(m) * tt)) * env * 0.06
        for s in range(8):
            st = k * bar + s * bar / 8
            pi, ln = int(st * SR), int(SR * 0.5)
            if pi + ln < n:
                pt = np.arange(ln) / SR
                mus[pi:pi + ln] += np.sin(2 * np.pi * hz(ch[s % 3] + 12) * pt) * np.exp(-pt * 7) * 0.05
    mus = sosfilt(sos("high", 80), mus)
    auto = np.ones(n)
    a0, a1 = R(46.0), R(51.8)
    auto *= 1 - 0.85 * np.clip(np.minimum((t - a0) / 0.6, (a1 - t) / 0.6), 0, 1)   # near-silent under the ayah
    mus *= auto * np.minimum(1, t / 0.5) * np.minimum(1, (t[-1] - t) / 0.8)

    v *= 10 ** ((-14 - meter.integrated_loudness(v)) / 20)
    sfx *= 10 ** ((-14 - 13 - meter.integrated_loudness(sfx)) / 20)
    mus *= 10 ** ((-14 - 21 - meter.integrated_loudness(mus)) / 20)
    res = {}
    for tag, mix in [("", v + sfx + mus), ("_nomusic", v + sfx)]:
        mix = mix * 10 ** ((-14 - meter.integrated_loudness(mix)) / 20)
        raw = outdir / f"_m{tag}.wav"
        wavfile.write(raw, SR, np.stack([mix, mix], 1).astype(np.float32))
        lim = outdir / f"_m{tag}_l.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
                        "aresample=192000,alimiter=limit=0.84:attack=3:release=60:level=disabled,aresample=48000",
                        "-c:a", "pcm_s24le", str(lim)], check=True)
        raw.unlink()
        res[tag] = lim
    return res


# ---------------------------------------------------------------- main
def frames():
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(CLIP), "-vf", f"fps={FPS},format=rgb24", "-f", "rawvideo",
                          "-"], stdout=subprocess.PIPE)
    n = 0
    while True:
        b = p.stdout.read(SW * SH * 3)
        if len(b) < SW * SH * 3:
            break
        yield n / FPS, Image.frombuffer("RGB", (SW, SH), b)
        n += 1
    p.wait()


def _work(job):
    t, b = job
    return render(Image.frombuffer("RGB", (SW, SH), b), t).tobytes()


def main():
    import multiprocessing as mp
    from collections import deque
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    ap.add_argument("--guides", action="store_true")
    a = ap.parse_args()
    EXPORT.mkdir(exist_ok=True)
    if a.preview:
        (EXPORT / "qc").mkdir(exist_ok=True)
        for ts in a.preview.split(","):
            t = float(ts)
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(CLIP), "-frames:v", "1",
                                  "-vf", "format=rgb24", "-f", "rawvideo", "-"], capture_output=True).stdout
            render(Image.frombuffer("RGB", (SW, SH), raw[:SW * SH * 3]), t, a.guides).save(
                EXPORT / "qc" / f"qh3_{t:05.2f}.jpg", quality=88)
            print("still", t, scene_at(t)[0])
        return
    tmp = EXPORT / "_qh3_video.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp)], stdin=subprocess.PIPE)
    with mp.Pool(3) as pool:
        pend = deque()
        i = 0
        for t, fr in frames():
            pend.append(pool.apply_async(_work, ((t, fr.tobytes()),)))
            while len(pend) > 9:
                enc.stdin.write(pend.popleft().get())
                i += 1
        while pend:
            enc.stdin.write(pend.popleft().get())
    enc.stdin.close()
    enc.wait()
    for tag, wav in audio(EXPORT).items():
        out = EXPORT / f"qh3_reel{tag}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                        str(out)], check=True)
        wav.unlink()
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
        s = " ".join(r[r.rfind("Summary:"):].split())
        print(out.name, s[s.find("I:"):s.find("I:") + 14], s[s.find("Peak:"):s.find("Peak:") + 18])
    tmp.unlink()


if __name__ == "__main__":
    main()
