"""video1 — podium speech reel (9:16, TikTok/IG safe zone), modern UI-card motion graphics.

Style (inspired by the reference reel, not copied): top word-by-word captions with boxed / italic
keywords, white UI cards over a blurred background, left vertical progress line with step chips,
camera punch-ins on the speaker, playful SFX, light modern music bed.

usage:
  python edit.py                      # full render -> ../../export/video1_reel.mp4 (+ _nomusic)
  python edit.py --preview 2.5,6.7    # QC stills (with safe-zone guides) -> ../../export/qc/
"""
import argparse
import math
import pathlib
import subprocess
import sys
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent.parent
SRC = ROOT / "raw_footage" / "video1.mov"
EXPORT = ROOT / "export"
FONTS = ROOT / "assets" / "fonts"

W, H, FPS = 1080, 1920, 30
DUR = 13.48
SW, SH = 576, 1024                       # source (after rotation)

# TikTok / IG Reels safe zone for 1080x1920
SAFE = dict(top=250, bottom=1920 - 440, left=60, right=1080 - 150)

# palette
NAVY = (14, 22, 46)
BLUE = (37, 99, 235)
BLUE_L = (96, 165, 250)
YELLOW = (255, 214, 10)
RED = (232, 54, 66)
WHITE = (255, 255, 255)
GREY = (226, 230, 238)

F_BLACK = FONTS / "inter-latin-900-normal.woff"
F_XB = FONTS / "inter-latin-800-normal.woff"
F_B = FONTS / "inter-latin-700-normal.woff"
F_M = FONTS / "inter-latin-500-normal.woff"
F_SERIF = FONTS / "playfair-display-latin-700-italic.woff"

# ---------------------------------------------------------------- transcript (Whisper large-v3, checked)
WORDS = [("Kepada", 0.00), ("barisan", 0.22), ("MT", 0.60), ("yang", 0.90), ("dirancang", 1.64), ("dalam", 2.44),
         ("keadaan", 3.16), ("kalut", 3.64), ("gitu-gitu", 4.08), ("tu,", 5.34), ("rancang,", 5.50), ("saya", 6.22),
         ("kata", 6.36), ("apa?", 6.64), ("Bila", 6.90), ("kita", 7.42), ("pegang", 7.62), ("jawatan,", 8.20),
         ("tak", 8.70), ("kisahlah", 8.84), ("MT", 9.28), ("ke", 9.52), ("hatta", 9.90), ("yang", 10.64),
         ("paling", 10.78), ("kecil,", 10.94), ("janganlah", 11.38), ("kita", 12.02), ("menjadikan", 12.18),
         ("diri", 12.86), ("kita…", 13.12)]
GROUPS = [(0, 3), (3, 5), (5, 8), (8, 10), (10, 11), (11, 14), (14, 16), (16, 18), (18, 22), (22, 26), (26, 28),
          (28, 31)]
HIDE_GROUPS = {5}                                 # "saya kata apa?" is shown as big kinetic text instead
BOXED = {"MT", "jawatan,", "kecil,", "janganlah"}  # white box, navy text
SERIF = {"dirancang", "kalut", "rancang,"}         # italic serif, yellow

STEPS = [(0.25, "Barisan MT"), (1.60, "Rancang"), (6.90, "Jawatan"), (8.70, "Semua peringkat"), (11.38, "Jangan…")]

# camera: (time, zoom); focus = speaker's face in source px
FOCUS_SRC = (236, 420)
FOCUS_OUT = (0.52, 0.47)
CAM = [(0.0, 1.0), (1.0, 1.45), (5.40, 1.5), (5.62, 1.95), (6.85, 1.95), (7.10, 1.55), (11.25, 1.6), (11.5, 1.85),
       (13.48, 1.92)]
# blur (background focus) windows for the big cards
BLUR = [(1.50, 5.42), (6.98, 11.30)]


# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def back(x, s=1.7):
    x = clamp(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def win(t, t0, t1, fi=0.25, fo=0.25):
    if t < t0 or t > t1:
        return 0.0
    return ease((t - t0) / fi) * ease((t1 - t) / fo)


@lru_cache(None)
def font(p, s):
    return ImageFont.truetype(str(p), s)


def alpha_mul(im, a):
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
    im = alpha_mul(im, a)
    x, y = round(cx - im.width / 2), round(cy - im.height / 2)
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + im.width), min(H, y + im.height)
    if x1 <= x0 or y1 <= y0:
        return
    cv.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


@lru_cache(None)
def txt(s, fp, size, color, pad=8):
    f = font(fp, size)
    bb = f.getbbox(s)
    asc, desc = f.getmetrics()
    im = Image.new("RGBA", (bb[2] - bb[0] + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - bb[0], pad), s, font=f, fill=color)
    return im


def drop_shadow(im, blur=14, alpha=0.45, dy=10):
    pad = blur * 3
    out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad + dy), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 255))
    sh.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    out.alpha_composite(sh, (pad, pad + dy))
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(im, (pad, pad))
    return out


def rrect(w, h, r, fill, outline=None, width=0, ss=2):
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=fill, outline=outline,
                                         width=width * ss)
    return im.resize((w, h), Image.LANCZOS)


# ---------------------------------------------------------------- camera + blur
def camera(frame, t):
    z = CAM[-1][1]
    for (t0, z0), (t1, z1) in zip(CAM, CAM[1:]):
        if t0 <= t <= t1:
            z = z0 + (z1 - z0) * ease((t - t0) / (t1 - t0))
            break
    # source crop with the output aspect (9:16), keeping the face at FOCUS_OUT
    cw, ch = SW / z, SH / z
    x0 = clamp(FOCUS_SRC[0] - cw * FOCUS_OUT[0], 0, SW - cw)
    y0 = clamp(FOCUS_SRC[1] - ch * FOCUS_OUT[1], 0, SH - ch)
    # subtle handheld drift
    x0 = clamp(x0 + 2.0 * math.sin(t * 0.9), 0, SW - cw)
    y0 = clamp(y0 + 1.5 * math.cos(t * 0.7), 0, SH - ch)
    img = frame.transform((W, H), Image.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.BICUBIC)
    return img.filter(ImageFilter.UnsharpMask(radius=2, percent=70 if z > 1.3 else 40, threshold=2))


def blur_amount(t):
    return max(win(t, a, b, 0.35, 0.3) for a, b in BLUR)


def apply_blur(img, k):
    if k <= 0.01:
        return img
    small = img.resize((W // 6, H // 6), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4 * k + 0.5))
    bl = small.resize((W, H), Image.BICUBIC)
    out = Image.blend(img, bl, min(1, k * 1.15))
    dark = Image.new("RGB", (W, H), NAVY)
    return Image.blend(out, dark, 0.38 * k)


# ---------------------------------------------------------------- captions (top)
@lru_cache(None)
def word_sprite(w, state):
    """state: 'dim' | 'on' | 'active'"""
    if w in BOXED:
        t = txt(w.strip(",.?"), F_BLACK, 62, NAVY if state != "dim" else (90, 100, 120), pad=6)
        box = rrect(t.width + 26, t.height + 6, 14, WHITE + ((255,) if state != "dim" else (90,)))
        box.alpha_composite(t, (13, 3))
        return box
    if w in SERIF:
        col = YELLOW if state != "dim" else (255, 255, 255)
        return txt(w, F_SERIF, 70, col + (255,), pad=6)
    col = WHITE if state != "dim" else (255, 255, 255)
    return txt(w, F_XB, 62, col + (255,), pad=6)


def draw_captions(cv, t):
    for gi, (a, b) in enumerate(GROUPS):
        st = WORDS[a][1] - 0.08
        en = WORDS[b][1] - 0.081 if b < len(WORDS) else DUR   # ends exactly before the next group starts
        if gi in HIDE_GROUPS or not (st <= t < en):
            continue
        words = WORDS[a:b]
        sprites = []
        for i, (w, ws) in enumerate(words):
            we = words[i + 1][1] if i + 1 < len(words) else en
            state = "dim" if t < ws else ("active" if t < we else "on")
            sprites.append((word_sprite(w, state), ws, state))
        gap = 14
        total = sum(s.width for s, _, _ in sprites) + gap * (len(sprites) - 1)
        x = W / 2 - total / 2
        y = SAFE["top"] + 95
        for s, ws, state in sprites:
            p = clamp((t - ws + 0.06) / 0.18)
            sc = 1.0 + (0.08 * (1 - ease_out(p)) if state != "dim" else 0)
            a = 0.33 if state == "dim" else 1.0
            ds = drop_shadow(s, 10, 0.55, 6)
            paste(cv, ds, x + s.width / 2, y + 6 + (ds.height - s.height) / 2 - 18, a, sc)
            x += s.width + gap


# ---------------------------------------------------------------- left progress line + step chips
def draw_progress(cv, t):
    a = ease(t / 0.5)
    x, y0, y1 = 84, 560, 1380
    d = ImageDraw.Draw(cv)
    d.rounded_rectangle((x - 2, y0, x + 2, y1), 2, fill=(255, 255, 255, int(110 * a)))
    yp = y0 + (y1 - y0) * clamp(t / DUR)
    d.rounded_rectangle((x - 2, y0, x + 2, yp), 2, fill=YELLOW + (int(255 * a),))
    d.ellipse((x - 11, yp - 11, x + 11, yp + 11), outline=WHITE + (int(255 * a),), width=4, fill=BLUE + (int(255 * a),))
    # current step chip next to the moving dot
    cur = None
    for st, label in STEPS:
        if t >= st:
            cur = (st, label)
    if cur:
        st, label = cur
        k = back((t - st) / 0.35)
        chip = step_chip(label)
        paste(cv, chip, x + 26 + chip.width / 2 - (1 - k) * 20, yp, a * clamp((t - st) / 0.2), 0.9 + 0.1 * k)


@lru_cache(None)
def step_chip(label):
    t = txt(label, F_B, 24, NAVY, pad=4)
    chip = rrect(t.width + 54, 42, 21, (255, 255, 255, 235))
    d = ImageDraw.Draw(chip)
    d.ellipse((14, 14, 28, 28), fill=BLUE)
    chip.alpha_composite(t, (36, (42 - t.height) // 2))
    return chip


# ---------------------------------------------------------------- cards
def card_base(w, h, r=34):
    return rrect(w, h, r, WHITE + (255,))


@lru_cache(None)
def plan_card():
    w, h = 700, 560
    c = card_base(w, h)
    d = ImageDraw.Draw(c)
    chip = rrect(230, 46, 23, (232, 240, 255, 255))
    chip.alpha_composite(txt("PERANCANGAN", F_B, 22, BLUE, pad=4), (24, 7))
    c.alpha_composite(chip, (40, 40))
    c.alpha_composite(txt("Barisan MT", F_BLACK, 50, NAVY, pad=4), (36, 104))
    for i in range(4):
        y = 210 + i * 80
        d.rounded_rectangle((44, y, 84, y + 40), 10, outline=(170, 180, 200), width=4)
        d.rounded_rectangle((110, y + 8, 110 + [430, 360, 470, 300][i], y + 30), 11, fill=GREY)
    return c


def plan_scribble(c, k):
    """Red chaotic scribbles over the checklist, k = 0..1 progress."""
    d = ImageDraw.Draw(c)
    rng = np.random.default_rng(3)
    for i in range(4):
        y = 230 + i * 80
        n = int(26 * clamp(k * 1.3 - i * 0.15))
        pts = [(110 + j * 18 + rng.uniform(-8, 8), y + rng.uniform(-14, 14)) for j in range(n)]
        if len(pts) > 1:
            d.line(pts, fill=RED + (230,), width=5, joint="curve")
        if k > 0.25 + i * 0.12:
            d.line((48, y - 14, 80, y + 18), fill=RED, width=6)
            d.line((80, y - 14, 48, y + 18), fill=RED, width=6)


@lru_cache(None)
def stamp():
    t = txt("KALUT!", F_BLACK, 96, RED, pad=6)
    w, h = t.width + 60, t.height + 30
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((4, 4, w - 5, h - 5), 22, outline=RED, width=10)
    im.alpha_composite(t, (30, 15))
    return im


def draw_plan(cv, t):
    t0, t1 = 1.55, 5.42
    a = win(t, t0, t1, 0.3, 0.25)
    if a <= 0:
        return
    c = plan_card().copy()
    if t > 3.6:
        plan_scribble(c, (t - 3.6) / 1.4)
    k = back((t - t0) / 0.5, 1.4)
    shake = 0.0
    dx = 0.0
    if 3.62 <= t < 5.2:
        e = math.exp(-(t - 3.62) * 1.6)
        shake = 3.5 * math.sin((t - 3.62) * 38) * e
        dx = 12 * math.sin((t - 3.62) * 47) * e
    paste(cv, drop_shadow(c, 22, 0.5, 18), W / 2 + dx, 1010 + (1 - k) * 80, a, 0.85 + 0.15 * k, shake)
    if t >= 3.70:   # stamp slams down
        p = (t - 3.70) / 0.22
        sc = 1.9 - 0.9 * ease_out(p)
        paste(cv, stamp(), W / 2 + 150 + dx, 1180, a * clamp(p * 2), sc, -12)


@lru_cache(None)
def big_word(w, color, boxed):
    if boxed:
        t = txt(w, F_BLACK, 150, NAVY, pad=6)
        box = rrect(t.width + 50, t.height + 10, 28, YELLOW + (255,))
        box.alpha_composite(t, (25, 5))
        return box
    return txt(w, F_BLACK, 150, color, pad=6)


def draw_question(cv, t):
    t0, t1 = 6.15, 7.02
    a = win(t, t0, t1, 0.1, 0.14)
    if a <= 0:
        return
    rows = [("SAYA", 6.22, False, 940), ("KATA", 6.36, False, 1090), ("APA?", 6.64, True, 1260)]
    for w, ws, boxed, y in rows:
        if t < ws - 0.03:
            continue
        p = (t - ws + 0.03) / 0.22
        sc = 0.4 + 0.6 * back(p, 2.2)
        rot = (6 * math.sin((t - ws) * 20) * math.exp(-(t - ws) * 5)) if boxed else 0
        s = big_word(w, WHITE, boxed)
        paste(cv, drop_shadow(s, 16, 0.6, 10), W / 2, y, a, sc, rot)


@lru_cache(None)
def badge():
    w, h = 500, 640
    c = card_base(w, h, 40)
    d = ImageDraw.Draw(c)
    hdr = rrect(w, 150, 40, BLUE + (255,))
    c.alpha_composite(hdr.crop((0, 0, w, 150)), (0, 0))
    d.rectangle((0, 110, w, 150), fill=BLUE)
    d.rounded_rectangle((w / 2 - 50, 26, w / 2 + 50, 44), 9, fill=(255, 255, 255, 200))   # lanyard slot
    t = txt("JAWATAN", F_BLACK, 52, WHITE, pad=4)
    c.alpha_composite(t, ((w - t.width) // 2, 66))
    # avatar silhouette
    d.ellipse((w / 2 - 95, 190, w / 2 + 95, 380), fill=(232, 240, 255))
    d.ellipse((w / 2 - 38, 222, w / 2 + 38, 298), fill=BLUE_L)
    d.pieslice((w / 2 - 75, 300, w / 2 + 75, 440), 180, 360, fill=BLUE_L)
    d.rounded_rectangle((90, 430, w - 90, 456), 13, fill=GREY)
    d.rounded_rectangle((130, 480, w - 130, 500), 10, fill=GREY)
    d.rounded_rectangle((170, 540, w - 170, 590), 25, fill=(232, 240, 255))
    return c


def draw_badge(cv, t):
    t0, t1 = 7.02, 8.66
    a = win(t, t0, t1, 0.15, 0.25)
    if a <= 0:
        return
    drop = ease_out((t - t0) / 0.45)
    swing = 9 * math.sin((t - t0) * 6.5) * math.exp(-(t - t0) * 1.8)
    y = 1040 - (1 - drop) * 900
    b = drop_shadow(badge(), 22, 0.5, 18)
    # lanyard straps from the top safe line to the badge
    d = ImageDraw.Draw(cv)
    top = (W / 2 + swing * 6, y - 330)
    for sx in (-60, 60):
        d.line((W / 2 + sx * 1.6, 450, top[0] + sx * 0.6, top[1] + 10), fill=BLUE + (int(255 * a),), width=14)
    paste(cv, b, W / 2 + swing * 6, y, a, 1.0, swing)


@lru_cache(None)
def bar(w, label, highlight):
    b = rrect(w, 104, 26, (BLUE if not highlight else YELLOW) + (255,))
    if label:
        t = txt(label, F_BLACK, 40 if w > 300 else 26, WHITE if not highlight else NAVY, pad=4)
        b.alpha_composite(t, ((w - t.width) // 2, (104 - t.height) // 2))
    return b


def draw_levels(cv, t):
    t0, t1 = 8.66, 11.30
    a = win(t, t0, t1, 0.2, 0.25)
    if a <= 0:
        return
    title = txt("Tak kisahlah…", F_SERIF, 64, WHITE, pad=6)
    paste(cv, drop_shadow(title, 10, 0.5, 6), W / 2, 700, a * ease((t - 8.75) / 0.3))
    levels = [(760, "MT", 9.28), (600, "", 9.62), (440, "", 9.95), (260, "PALING KECIL", 10.78)]
    all_equal = ease((t - 11.0) / 0.2)       # at the end every level glows the same: every post matters
    for i, (w, label, ts) in enumerate(levels):
        if t < ts - 0.05:
            continue
        p = (t - ts + 0.05) / 0.35
        y = 860 + i * 135
        hl = (label == "MT" and t < 9.9) or label == "PALING KECIL" or all_equal > 0.5
        b = drop_shadow(bar(w, label, hl), 14, 0.45, 8)
        paste(cv, b, W / 2, y - (1 - ease_out(p)) * 120, a * clamp(p * 2), 0.9 + 0.1 * back(p, 2))


@lru_cache(None)
def warn_pill():
    t = txt("JANGANLAH…", F_BLACK, 72, WHITE, pad=6)
    w, h = t.width + 150, t.height + 40
    im = rrect(w, h, h // 2, RED + (255,))
    d = ImageDraw.Draw(im)
    cx, cy, r = 60, h / 2, 30
    d.polygon([(cx, cy - r), (cx + r * 1.05, cy + r * 0.8), (cx - r * 1.05, cy + r * 0.8)], fill=WHITE)
    d.rounded_rectangle((cx - 4, cy - 12, cx + 4, cy + 8), 3, fill=RED)
    d.ellipse((cx - 4, cy + 12, cx + 4, cy + 20), fill=RED)
    im.alpha_composite(t, (110, 20))
    return im


def draw_warning(cv, t):
    t0 = 11.36
    a = win(t, t0, DUR + 1, 0.12, 0.2)
    if a <= 0:
        return
    p = (t - t0) / 0.3
    shake = 4 * math.sin((t - t0) * 30) * math.exp(-(t - t0) * 4)
    paste(cv, drop_shadow(warn_pill(), 16, 0.5, 10), W / 2 + 20 + shake * 3, 1150, a, 0.6 + 0.4 * back(p, 2.4), shake)


# ---------------------------------------------------------------- frame
def render(frame, t, guides=False):
    img = camera(frame, t)
    img = apply_blur(img, blur_amount(t)).convert("RGBA")
    # soft vignette for depth
    img.alpha_composite(vignette())
    draw_plan(img, t)
    draw_badge(img, t)
    draw_levels(img, t)
    draw_question(img, t)
    draw_warning(img, t)
    draw_progress(img, t)
    draw_captions(img, t)
    # punch flash on big moments
    for tt in (5.62, 11.38):
        k = 1 - abs(t - tt) / 0.12
        if k > 0:
            img.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(90 * k))))
    if t < 0.25:
        img.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - t / 0.25)))))
    if t > DUR - 0.25:
        img.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * clamp((t - DUR + 0.25) / 0.25)))))
    if guides:
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        red = (255, 0, 0, 80)
        d.rectangle((0, 0, W, SAFE["top"]), fill=red)
        d.rectangle((0, SAFE["bottom"], W, H), fill=red)
        d.rectangle((SAFE["right"], SAFE["top"], W, SAFE["bottom"]), fill=red)
        d.rectangle((0, SAFE["top"], SAFE["left"], SAFE["bottom"]), fill=red)
        img.alpha_composite(ov)
    return img.convert("RGB")


@lru_cache(None)
def vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W / 2) / (W * 0.62), (yy - H / 2) / (H * 0.62))
    a = (np.clip(r - 0.55, 0, 1) ** 1.6 * 200).astype(np.uint8)
    top = (np.clip(1 - yy / 520, 0, 1) ** 2 * 120).astype(np.uint8)   # darker top for caption contrast
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., 3] = np.maximum(a, top)
    return Image.fromarray(arr, "RGBA")


# ---------------------------------------------------------------- audio
SR = 48000


def sfx_track(n):
    rng = np.random.default_rng(8)
    from scipy.signal import butter, sosfilt

    def bp(lo, hi):
        return butter(2, [lo, hi], btype="band", fs=SR, output="sos")

    def whoosh(d=0.5, up=True):
        m = int(SR * d)
        t = np.arange(m) / SR
        x = np.zeros(m)
        pos = np.sin(np.pi * t / d)
        nz = rng.standard_normal(m)
        for k, (lo, hi) in enumerate([(300, 900), (800, 2400), (2000, 6000), (4000, 11000)]):
            x += sosfilt(bp(lo, hi), nz) * np.exp(-(((pos if up else 1 - pos) * 3 - k) ** 2))
        return x * np.sin(np.pi * t / d) ** 2 * 0.6

    def pop(f=900, d=0.1, g=0.6):
        t = np.arange(int(SR * d)) / SR
        return np.sin(2 * np.pi * np.cumsum(f * np.exp(-t * 18) + 200) / SR) * np.exp(-t * 35) * g

    def tick():
        t = np.arange(int(SR * 0.03)) / SR
        return (np.sin(2 * np.pi * 3000 * t) + rng.standard_normal(len(t)) * 0.4) * np.exp(-t * 200) * 0.5

    def thud(d=0.5):
        t = np.arange(int(SR * d)) / SR
        body = np.sin(2 * np.pi * np.cumsum(90 * np.exp(-t * 10) + 50) / SR) * np.exp(-t * 9)
        slap = sosfilt(bp(500, 3000), rng.standard_normal(len(t))) * np.exp(-t * 60) * 0.5
        return (body + slap) * 0.8

    def scribble(d=1.2):
        t = np.arange(int(SR * d)) / SR
        x = sosfilt(bp(1500, 6000), rng.standard_normal(len(t)))
        am = (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 9 * t + 3 * np.sin(2 * np.pi * 2.3 * t)))) * np.exp(-t * 0.8)
        return x * am * 0.35

    def boing(d=0.45):
        t = np.arange(int(SR * d)) / SR
        f = 220 + 380 * (t / d) + 40 * np.sin(2 * np.pi * 14 * t)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4) * 0.5

    def ding(f=1568, d=1.0):
        t = np.arange(int(SR * d)) / SR
        return sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * dc) for k, a, dc in
                   [(1, 1, 3), (2.76, .35, 5), (5.4, .12, 8)]) * 0.3

    def click():
        t = np.arange(int(SR * 0.05)) / SR
        return sosfilt(bp(1000, 5000), rng.standard_normal(len(t))) * np.exp(-t * 120) * 0.8

    def bwomp(d=0.6):
        t = np.arange(int(SR * d)) / SR
        return np.sign(np.sin(2 * np.pi * np.cumsum(140 * np.exp(-t * 2)) / SR)) * np.exp(-t * 5) * 0.18

    ev = [(0.0, whoosh(0.6), -8), (0.60, pop(1100), -10),
          (1.35, whoosh(0.45), -6), (1.62, pop(700), -9),
          (2.0, tick(), -8), (2.35, tick(), -8), (2.7, tick(), -8), (3.05, tick(), -8),
          (3.60, scribble(), -9), (3.70, thud(), -4),
          (5.28, whoosh(0.4, False), -8),
          (6.22, pop(800), -6), (6.36, pop(950), -6), (6.62, pop(1200), -5), (6.66, boing(), -8),
          (6.85, whoosh(0.4), -8), (7.20, click(), -7), (7.25, ding(1318), -14),
          (8.60, whoosh(0.4), -8),
          (9.26, thud(0.35), -10), (9.28, ding(1568), -12), (9.62, thud(0.3), -12), (9.95, thud(0.3), -12),
          (10.78, pop(1500, 0.08), -7), (11.0, ding(2093, 0.8), -15),
          (11.22, whoosh(0.35, False), -8), (11.36, bwomp(), -10)]
    out = np.zeros((n, 2))
    for at, x, g in ev:
        i = int(at * SR)
        j = min(n, i + len(x))
        out[i:j] += (x[: j - i] * 10 ** (g / 20))[:, None]
    return out


def music_track(n):
    """Light modern bed: soft pad + pluck arpeggio + gentle kick/hat, 100 bpm, C major-ish."""
    from scipy.signal import butter, sosfilt
    rng = np.random.default_rng(2)
    t = np.arange(n) / SR
    beat = 60 / 100
    chords = [(48, 52, 55, 59), (45, 48, 52, 55), (41, 45, 48, 52), (43, 47, 50, 55)]   # Cmaj7 Am F G
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    out = np.zeros(n)
    bar = beat * 4
    for k in range(int(n / SR / bar) + 1):
        ch = chords[k % 4]
        i0, i1 = int(k * bar * SR), min(n, int((k + 1) * bar * SR))
        tt = t[i0:i1] - k * bar
        env = np.minimum(1, tt / 0.3) * np.minimum(1, (bar - tt) / 0.3)
        for m in ch:
            out[i0:i1] += (np.sin(2 * np.pi * hz(m + 12) * tt) + 0.3 * np.sin(4 * np.pi * hz(m + 12) * tt)) * env * 0.05
        for s in range(8):   # pluck arpeggio on 8ths
            st = k * bar + s * beat / 2
            m = ch[[0, 2, 1, 3, 2, 1, 3, 2][s]] + 24
            pi = int(st * SR)
            ln = int(SR * 0.4)
            if pi + ln > n:
                continue
            pt = np.arange(ln) / SR
            out[pi:pi + ln] += np.sin(2 * np.pi * hz(m) * pt) * np.exp(-pt * 9) * 0.07
    for b in range(int(n / SR / beat) + 1):
        st = int(b * beat * SR)
        if b % 2 == 0 and st + 9000 < n:   # kick
            kt = np.arange(9000) / SR
            out[st:st + 9000] += np.sin(2 * np.pi * np.cumsum(110 * np.exp(-kt * 30) + 48) / SR) * np.exp(-kt * 14) * 0.25
        hs = int((b + 0.5) * beat * SR)    # hat
        if hs + 3000 < n:
            out[hs:hs + 3000] += sosfilt(butter(2, 7000, "high", fs=SR, output="sos"), rng.standard_normal(3000)) * \
                np.exp(-np.arange(3000) / SR * 60) * 0.05
    out = sosfilt(butter(2, 70, "high", fs=SR, output="sos"), out)
    out *= np.minimum(1, t / 0.4) * np.minimum(1, (t[-1] - t) / 0.5)
    return np.stack([out, out], 1) / (np.abs(out).max() + 1e-9) * 0.8


def build_audio(outdir):
    import pyloudnorm as pyln
    from scipy.io import wavfile
    voice_wav = outdir / "_voice.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(SRC), "-t", f"{DUR}", "-af",
                    "highpass=f=90,afftdn=nf=-30,equalizer=f=300:t=q:w=1:g=-3,equalizer=f=3200:t=q:w=1.2:g=3,"
                    "acompressor=threshold=-20dB:ratio=3:attack=6:release=120:makeup=3,aresample=48000",
                    "-ac", "1", str(voice_wav)], check=True)
    _, v = wavfile.read(voice_wav)
    voice_wav.unlink()
    v = v.astype(np.float64) / 32768
    n = len(v)
    meter = pyln.Meter(SR)
    v *= 10 ** ((-14 - meter.integrated_loudness(v)) / 20)
    voice = np.stack([v, v], 1)
    sfx = sfx_track(n)
    sfx *= 10 ** ((-14 - 12 - meter.integrated_loudness(sfx)) / 20)
    mus = music_track(n)
    mus *= 10 ** ((-14 - 21 - meter.integrated_loudness(mus)) / 20)   # bed ~21 dB under the voice
    mixes = {}
    for tag, mix in [("", voice + sfx + mus), ("_nomusic", voice + sfx)]:
        mix *= 10 ** ((-14 - meter.integrated_loudness(mix)) / 20)
        raw = outdir / f"_mix{tag}.wav"
        wavfile.write(raw, SR, mix.astype(np.float32))
        lim = outdir / f"_mix{tag}_lim.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
                        "aresample=192000,alimiter=limit=0.84:attack=3:release=60:level=disabled,aresample=48000",
                        "-c:a", "pcm_s24le", str(lim)], check=True)
        raw.unlink()
        mixes[tag] = lim
    return mixes


# ---------------------------------------------------------------- main
def frames():
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(SRC), "-t", f"{DUR}", "-vf", f"fps={FPS},format=rgb24",
                          "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    n = 0
    while True:
        b = p.stdout.read(SW * SH * 3)
        if len(b) < SW * SH * 3:
            break
        yield n / FPS, Image.frombuffer("RGB", (SW, SH), b)
        n += 1
    p.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    a = ap.parse_args()
    EXPORT.mkdir(exist_ok=True)
    if a.preview:
        qc = EXPORT / "qc"
        qc.mkdir(exist_ok=True)
        for ts in a.preview.split(","):
            t = float(ts)
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(SRC), "-frames:v", "1",
                                  "-vf", "format=rgb24", "-f", "rawvideo", "-"], capture_output=True).stdout
            render(Image.frombuffer("RGB", (SW, SH), raw[:SW * SH * 3]), t, True).save(qc / f"video1_{t:05.2f}.jpg")
            print("still", t)
        return
    tmp = EXPORT / "_video1_video.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp)], stdin=subprocess.PIPE)
    for i, (t, fr) in enumerate(frames()):
        enc.stdin.write(render(fr, t).tobytes())
        if i % 60 == 0:
            print(f"frame {i} t={t:.1f}", flush=True)
    enc.stdin.close()
    enc.wait()
    mixes = build_audio(EXPORT)
    for tag, wav in mixes.items():
        out = EXPORT / f"video1_reel{tag}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)],
                       check=True)
        wav.unlink()
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
        print(out.name, " ".join(r[r.rfind("Integrated loudness"):].split())[:160])
    tmp.unlink()


if __name__ == "__main__":
    sys.exit(main())
