"""YouTube 1920x1080 edit: merges the QH clips into one video on an animated premium background.

Layout: each clip plays inside a framed "card" over an animated aurora background, word-synced captions
below it, chapter chips, key-point callouts, chapter title interstitials between clips, intro + outro.
Everything stays inside the YouTube title-safe area (config.SAFE).

usage:
  python render.py <clipdir> <out_video_only.mp4> [--workers 3] [--preview t1,t2,..] [--guides]
"""
import argparse
import math
import multiprocessing as mp
import subprocess
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config as C

W, H, FPS = C.W, C.H, C.FPS
CW, CH = C.CARD_W, C.CARD_H
CARD_CX, CARD_CY = W / 2, C.CARD_Y + CH / 2
TL = C.timeline()


# ---------------------------------------------------------------- utils
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_out_back(x, s=1.4):
    x = clamp(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def window(t, t0, t1, fin=0.4, fout=0.35):
    if t < t0 or t > t1:
        return 0.0
    return ease((t - t0) / fin) * ease((t1 - t) / fout)


@lru_cache(None)
def font(path, size):
    return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM)


def with_alpha(im, a):
    if a >= 0.999:
        return im
    arr = np.asarray(im).copy()
    arr[..., 3] = (arr[..., 3].astype(np.float32) * a).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def paste(canvas, im, cx, cy, alpha=1.0, scale=1.0):
    if alpha <= 0.004 or scale <= 0.01:
        return
    if abs(scale - 1) > 1e-3:
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.BICUBIC)
    im = with_alpha(im, alpha)
    x, y = round(cx - im.width / 2), round(cy - im.height / 2)
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + im.width), min(H, y + im.height)
    if x1 <= x0 or y1 <= y0:
        return
    if (x0, y0, x1, y1) != (x, y, x + im.width, y + im.height):
        im = im.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    canvas.alpha_composite(im, (x0, y0))


def is_arabic(text):
    return any("\u0600" <= ch <= "\u06ff" for ch in text)


@lru_cache(None)
def text_sprite(text, fpath, size, color, tracking=0):
    if is_arabic(text):
        f = font(C.F_ARABIC, size)
        kw = dict(direction="rtl", language="ar")
        bbox = f.getbbox(text, **kw)
        asc, desc = f.getmetrics()
        pad = int(size * 0.3)
        im = Image.new("RGBA", (bbox[2] - bbox[0] + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((pad - bbox[0], pad), text, font=f, fill=color, **kw)
        return im
    f = font(fpath, size)
    asc, desc = f.getmetrics()
    if tracking:
        ws = [f.getlength(ch) + tracking for ch in text]
        im = Image.new("RGBA", (int(sum(ws)) + 8, asc + desc + 8), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        x = 2
        for ch, w in zip(text, ws):
            d.text((x, 2), ch, font=f, fill=color)
            x += w
        return im
    bbox = f.getbbox(text)
    im = Image.new("RGBA", (bbox[2] - bbox[0] + 12, asc + desc + 12), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((6 - bbox[0], 6), text, font=f, fill=color)
    return im


@lru_cache(None)
def shadow_of(text, fpath, size, color, blur=10, tracking=0):
    s = text_sprite(text, fpath, size, color, tracking)
    pad = blur * 3
    out = Image.new("RGBA", (s.width + 2 * pad, s.height + 2 * pad), (0, 0, 0, 0))
    blk = Image.new("RGBA", s.size, (0, 0, 0, 255))
    blk.putalpha(s.getchannel("A"))
    out.alpha_composite(blk, (pad, pad))
    return out.filter(ImageFilter.GaussianBlur(blur))


def shadow_text(canvas, text, fpath, size, color, cx, cy, alpha=1.0, tracking=0, sh=0.7):
    paste(canvas, shadow_of(text, fpath, size, color, 10, tracking), cx, cy + 5, alpha * sh)
    paste(canvas, text_sprite(text, fpath, size, color, tracking), cx, cy, alpha)


@lru_cache(None)
def icon(name, size):
    im = Image.open(C.ICONS / f"{name}.png").convert("RGBA")
    return im.resize((size, size), Image.LANCZOS)


@lru_cache(None)
def soft_dot(r, color):
    s = r * 6
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((s / 2 - r, s / 2 - r, s / 2 + r, s / 2 + r), fill=color + (255,))
    im = im.filter(ImageFilter.GaussianBlur(r * 0.9))
    ImageDraw.Draw(im).ellipse((s / 2 - r * .4, s / 2 - r * .4, s / 2 + r * .4, s / 2 + r * .4), fill=(255, 250, 230, 255))
    return im.filter(ImageFilter.GaussianBlur(max(1, r * .25)))


# ---------------------------------------------------------------- background
BG_SMALL = (384, 216)


@lru_cache(None)
def bg_grid():
    yy, xx = np.mgrid[0:BG_SMALL[1], 0:BG_SMALL[0]].astype(np.float32)
    return xx / BG_SMALL[0], yy / BG_SMALL[1]


def aurora(t):
    """Animated aurora gradient, computed small and upscaled (smooth)."""
    xx, yy = bg_grid()
    base0, base1 = np.array(C.BG_TOP, np.float32), np.array(C.BG_BOTTOM, np.float32)
    img = base0[None, None] * (1 - yy[..., None]) + base1[None, None] * yy[..., None]
    for i, (col, amp) in enumerate(C.AURORA):
        ph = i * 1.7
        cx = 0.5 + 0.42 * math.sin(t * 0.07 + ph) * math.cos(t * 0.031 + ph * 2)
        cy = 0.45 + 0.38 * math.sin(t * 0.053 + ph * 1.3)
        sx, sy = 0.28 + 0.08 * math.sin(t * 0.09 + ph), 0.22 + 0.06 * math.cos(t * 0.11 + ph)
        g = np.exp(-(((xx - cx) / sx) ** 2 + ((yy - cy) / sy) ** 2))
        img += g[..., None] * np.array(col, np.float32)[None, None] * amp
    # diagonal light ribbon
    rib = np.exp(-((yy - 0.25 - 0.5 * xx - 0.12 * np.sin(t * 0.2 + xx * 4)) / 0.06) ** 2) * 0.22
    img += rib[..., None] * np.array(C.ACCENT, np.float32)[None, None]
    img = np.clip(img, 0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGB").resize((W, H), Image.BICUBIC)


@lru_cache(None)
def pattern_tile():
    """Faint geometric line pattern (8-point stars lattice), larger than frame for slow drift."""
    pw, ph = W + 240, H + 240
    im = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    step = 120
    col = C.ACCENT + (26,)
    for y in range(0, ph + step, step):
        for x in range(0, pw + step, step):
            ox = (step // 2) if (y // step) % 2 else 0
            cx, cy = x + ox, y
            r1, r2 = 34, 15
            pts = [(cx + (r1 if k % 2 == 0 else r2) * math.cos(math.radians(-90 + k * 22.5)),
                    cy + (r1 if k % 2 == 0 else r2) * math.sin(math.radians(-90 + k * 22.5))) for k in range(16)]
            d.polygon(pts, outline=col, width=2)
    # radial fade so the pattern sits mostly at the edges
    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    r = np.hypot((xx - pw / 2) / (pw / 2), (yy - ph / 2) / (ph / 2))
    a = np.asarray(im)[..., 3].astype(np.float32) * np.clip(r * 1.1 - 0.15, 0, 1)
    arr = np.asarray(im).copy()
    arr[..., 3] = a.astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def draw_background(t):
    bg = aurora(t).convert("RGBA")
    pt = pattern_tile()
    bg.alpha_composite(pt.crop((int(120 + 100 * math.sin(t * 0.05)), int(120 + 80 * math.cos(t * 0.04)),
                                int(120 + 100 * math.sin(t * 0.05)) + W, int(120 + 80 * math.cos(t * 0.04)) + H)))
    rng = np.random.default_rng(9)
    n = 46
    xs, ys = rng.uniform(0, W, n), rng.uniform(0, H, n)
    sp = rng.uniform(10, 40, n)
    rs = rng.choice([2, 3, 5, 7], n, p=[.35, .3, .22, .13])
    ph = rng.uniform(0, 6.28, n)
    for i in range(n):
        y = (ys[i] - t * sp[i]) % (H + 80) - 40
        x = xs[i] + 25 * math.sin(t * .35 + ph[i])
        a = (0.3 + 0.7 * (0.5 + 0.5 * math.sin(t * 1.4 + ph[i] * 3))) * 0.8
        paste(bg, soft_dot(int(rs[i]), C.PARTICLE), x, y, a)
    return bg


# ---------------------------------------------------------------- card
@lru_cache(None)
def card_mask():
    s = 2
    m = Image.new("L", (CW * s, CH * s), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, CW * s - 1, CH * s - 1), C.CARD_R * s, fill=255)
    return m.resize((CW, CH), Image.LANCZOS)


@lru_cache(None)
def card_chrome():
    """Glow + shadow + gradient border around the card (pre-rendered)."""
    pad = 90
    w, h = CW + 2 * pad, CH + 2 * pad
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 26, pad + CW, pad + CH + 26), C.CARD_R, fill=(0, 0, 0, 170))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(30)))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle((pad - 6, pad - 6, pad + CW + 6, pad + CH + 6), C.CARD_R + 6,
                                           outline=C.ACCENT + (150,), width=10)
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))
    return im, pad


@lru_cache(None)
def card_border():
    s = 2
    pad = 4
    w, h = (CW + 2 * pad) * s, (CH + 2 * pad) * s
    # gradient stroke: accent -> accent2 diagonally
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    k = (xx / w + yy / h) / 2
    c0, c1 = np.array(C.ACCENT, np.float32), np.array(C.ACCENT2, np.float32)
    rgb = c0[None, None] * (1 - k[..., None]) + c1[None, None] * k[..., None]
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((1, 1, w - 2, h - 2), (C.CARD_R + pad) * s, outline=255, width=3 * s)
    arr = np.dstack([rgb.astype(np.uint8), np.asarray(m)])
    return Image.fromarray(arr, "RGBA").resize((CW + 2 * pad, CH + 2 * pad), Image.LANCZOS)


def draw_card(canvas, frame, t, scale=1.0, alpha=1.0, dy=0.0, cx=None):
    if alpha <= 0.004 or frame is None:
        return
    fl = 3 * math.sin(t * 0.8)  # gentle float
    cy = CARD_CY + dy + fl
    CARD_CX = W / 2 if cx is None else cx
    chrome, _ = card_chrome()
    paste(canvas, chrome, CARD_CX, cy, alpha, scale)
    card = frame.convert("RGBA")
    card.putalpha(card_mask())
    paste(canvas, card, CARD_CX, cy, alpha, scale)
    paste(canvas, card_border(), CARD_CX, cy, alpha, scale)


# ---------------------------------------------------------------- dynamic layout
SPLIT_SCALE, SPLIT_CX = 0.78, 96 + 1380 * 0.78 / 2 + 8


def split_amount(t, seg):
    """0 = card centred, 1 = card left + callout panel right (eased)."""
    k = 0.0
    for (ts, te, *_r) in seg.get("callouts", []):
        t0, t1 = seg["start"] + ts, seg["start"] + te
        k = max(k, ease((t - t0) / 0.7) * ease((t1 - t) / 0.7) if t0 <= t <= t1 else 0)
    return k


def card_geom(t, seg):
    k = split_amount(t, seg)
    return W / 2 + (SPLIT_CX - W / 2) * k, 1 - (1 - SPLIT_SCALE) * k, k


# ---------------------------------------------------------------- overlays
def draw_chip(canvas, t, seg):
    """Chapter chip on the card's top-left corner."""
    a = window(t, seg["start"] + 0.3, seg["start"] + 6.0, 0.5, 0.6)
    if a <= 0:
        return
    label = f"BAHAGIAN {seg['index']}"
    title = seg["title"].upper()
    f1, f2 = C.F_TITLE, C.F_SANS_SB
    s1 = text_sprite(label, f2, 22, C.BG_TOP, tracking=3)
    s2 = text_sprite(title, f1, 30, C.WHITE, tracking=1)
    w = s1.width + s2.width + 70
    h = 58
    ccx, sc, _ = card_geom(t, seg)
    x0 = ccx - CW * sc / 2 + 34 - (1 - ease_out((t - seg["start"] - 0.3) / 0.6)) * 60
    y0 = CARD_CY - CH * sc / 2 + 30
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), 29, fill=(10, 14, 30, 210))
    d.rounded_rectangle((4, 4, s1.width + 30, h - 5), 25, fill=C.ACCENT + (255,))
    im.alpha_composite(s1, (17, (h - s1.height) // 2))
    im.alpha_composite(s2, (s1.width + 44, (h - s2.height) // 2))
    paste(canvas, im, x0 + w / 2, y0 + h / 2, a)


PANEL_W = 470


@lru_cache(None)
def callout_sprite(icon_name, title, body, arabic=None):
    """Vertical glass panel shown to the right of the (shrunk) card."""
    pad = 34
    ic = icon(icon_name, 170)
    s_t = text_sprite(title.upper(), C.F_TITLE, 30, C.ACCENT, tracking=2)
    lines = body.split("\n")
    s_b = [text_sprite(l, C.F_SANS_SB, 36, C.WHITE) for l in lines]
    s_a = None
    if arabic:
        size = 46
        s_a = text_sprite(arabic, C.F_ARABIC, size, C.ACCENT)
        while s_a.width > PANEL_W - 40 and size > 26:
            size -= 2
            s_a = text_sprite(arabic, C.F_ARABIC, size, C.ACCENT)
    h = pad + 170 + 26 + s_t.height + 22 + sum(sb.height - 4 for sb in s_b) + pad + (s_a.height + 6 if s_a else 0)
    w = PANEL_W
    im = Image.new("RGBA", (w + 80, h + 80), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((40, 58, 40 + w, 58 + h), 30, fill=(0, 0, 0, 160))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle((36, 36, 44 + w, 44 + h), 34, outline=C.ACCENT + (120,), width=8)
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(12)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((40, 40, 40 + w, 40 + h), 30, fill=(10, 20, 34, 225), outline=C.ACCENT + (220,), width=3)
    y = 40 + pad
    im.alpha_composite(ic, (40 + (w - 170) // 2, y))
    y += 170 + 26
    im.alpha_composite(s_t, (40 + (w - s_t.width) // 2, y))
    y += s_t.height
    d.rounded_rectangle((40 + w / 2 - 50, y + 4, 40 + w / 2 + 50, y + 9), 3, fill=C.ACCENT + (255,))
    y += 22
    if s_a:
        im.alpha_composite(s_a, (40 + (w - s_a.width) // 2, y - 8))
        y += s_a.height + 6
    for sb in s_b:
        im.alpha_composite(sb, (40 + (w - sb.width) // 2, y))
        y += sb.height - 4
    return im


def draw_callouts(canvas, t, seg):
    for (ts, te, ic, title, body, arabic) in seg.get("callouts", []):
        t0, t1 = seg["start"] + ts, seg["start"] + te
        a = window(t, t0 + 0.25, t1 - 0.1, 0.45, 0.4)
        if a <= 0:
            continue
        spr = callout_sprite(ic, title, body, arabic)
        p = ease_out_back((t - t0 - 0.25) / 0.7, 1.2)
        x = C.SAFE[2] - PANEL_W / 2 - 20 + (1 - p) * 160
        paste(canvas, spr, x, CARD_CY, a)


def draw_captions(canvas, t, seg):
    """Arabic words (as spoken, right-to-left, active word in gold) + Malay translation underneath."""
    caps = seg.get("captions", [])
    for ci, cap in enumerate(caps):
        st = seg["start"] + cap["start"] - 0.12
        nxt = seg["start"] + caps[ci + 1]["start"] - 0.12 if ci + 1 < len(caps) else 1e9
        en = min(seg["start"] + cap["end"] + 0.45, nxt, seg["end"] - 0.05)
        if not (st <= t <= en):
            continue
        out = ease((en - t) / 0.16)
        fin = ease((t - st) / 0.25)
        # Arabic line, laid out right -> left
        words = cap["ar"]
        sprs = []
        for (wt, ws, we) in words:
            gws, gwe = seg["start"] + ws, seg["start"] + we
            col = ACCENT_WORD if gws - 0.04 <= t <= gwe + 0.04 else C.WHITE
            sprs.append((text_sprite(wt, C.F_ARABIC, C.CAPTION_SIZE, col), wt, col, gws))
        sp = 14
        total = sum(x[0].width for x in sprs) + sp * (len(sprs) - 1)
        x = W / 2 + total / 2
        for spr, wt, col, gws in sprs:
            p = (t - gws + 0.12) / 0.22
            a = (0.35 + 0.65 * ease(p)) * out * fin
            cx = x - spr.width / 2
            paste(canvas, shadow_of(wt, C.F_ARABIC, C.CAPTION_SIZE, col), cx, C.AR_CAPTION_Y + 4, a * 0.85)
            paste(canvas, spr, cx, C.AR_CAPTION_Y, a)
            x -= spr.width + sp
        # Malay translation
        ms = cap["ms"]
        a = out * ease((t - st - 0.1) / 0.3)
        paste(canvas, shadow_of(ms, C.F_SANS, 30, C.ACCENT2), W / 2, C.MS_CAPTION_Y + 3, a * 0.85)
        paste(canvas, text_sprite(ms, C.F_SANS, 30, C.ACCENT2), W / 2, C.MS_CAPTION_Y, a)


ACCENT_WORD = (255, 214, 92)


def draw_progress(canvas, t):
    """Thin chapter progress bar under the captions (inside title safe)."""
    x0, x1 = C.CARD_X, C.CARD_X + CW
    y = C.PROGRESS_Y
    total = TL["duration"]
    d = ImageDraw.Draw(canvas)
    a = int(255 * window(t, 2.5, total - 3.5, 0.8, 0.8))
    if a <= 2:
        return
    d.rounded_rectangle((x0, y - 3, x1, y + 3), 3, fill=(255, 255, 255, int(a * 0.18)))
    px = x0 + (x1 - x0) * clamp(t / total)
    d.rounded_rectangle((x0, y - 3, px, y + 3), 3, fill=C.ACCENT + (a,))
    for seg in TL["clips"]:
        mx = x0 + (x1 - x0) * seg["start"] / total
        d.ellipse((mx - 7, y - 7, mx + 7, y + 7), fill=(C.ACCENT if t >= seg["start"] else (90, 100, 130)) + (a,))


# ---------------------------------------------------------------- titles
def draw_title_block(canvas, t, t0, t1, kicker, title, sub=None, big=96):
    a = window(t, t0, t1, 0.5, 0.45)
    if a <= 0:
        return
    p = ease_out((t - t0) / 0.9)
    cy = H / 2 - 20
    # kicker
    shadow_text(canvas, kicker, C.F_SANS_SB, 30, C.ACCENT, W / 2, cy - 110 + (1 - p) * 20, a * ease((t - t0) / 0.5),
                tracking=8)
    # title with letter reveal (scale from 1.08 -> 1)
    sc = 1.08 - 0.08 * p
    paste(canvas, shadow_of(title, C.F_TITLE, big, C.WHITE, 16), W / 2, cy + 8, a * 0.7, sc)
    paste(canvas, text_sprite(title, C.F_TITLE, big, C.WHITE), W / 2, cy, a, sc)
    # underline sweep
    lw = 520 * ease_out((t - t0 - 0.25) / 0.8)
    d = ImageDraw.Draw(canvas)
    if lw > 2:
        d.rounded_rectangle((W / 2 - lw / 2, cy + big * 0.72, W / 2 + lw / 2, cy + big * 0.72 + 6), 3,
                            fill=C.ACCENT + (int(255 * a),))
    if sub:
        sa = a * ease((t - t0 - 0.5) / 0.6)
        ss = 60 if is_arabic(sub) else 36
        shadow_text(canvas, sub, C.F_SANS, ss, C.ACCENT if is_arabic(sub) else C.WHITE, W / 2, cy + big * 0.72 + 74, sa)


def draw_flash(canvas, t):
    for tt in TL["cuts"]:
        k = 1 - abs(t - tt) / 0.25
        if k > 0:
            canvas.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(70 * k * k))))


# ---------------------------------------------------------------- frame
def render(t, frame, hold_prev, hold_next, guides=False):
    canvas = draw_background(t)
    seg = TL["at"](t)
    kind = seg["kind"]
    if kind == "clip":
        ccx, sc, _ = card_geom(t, seg)
        draw_card(canvas, frame, t, scale=sc, cx=ccx)
        draw_chip(canvas, t, seg)
        draw_callouts(canvas, t, seg)
        draw_captions(canvas, t, seg)
    else:
        local = t - seg["start"]
        dur = seg["end"] - seg["start"]
        if hold_prev is not None and local < 0.7:          # card exits: shrink + drop + fade
            k = ease(local / 0.7)
            draw_card(canvas, hold_prev, t, scale=1 - 0.25 * k, alpha=1 - k, dy=80 * k)
        if hold_next is not None and local > dur - 0.8:    # next card enters: zoom in from small
            k = ease_out((local - (dur - 0.8)) / 0.8)
            draw_card(canvas, hold_next, t, scale=0.75 + 0.25 * k, alpha=k, dy=-60 * (1 - k))
        if kind == "intro":
            draw_title_block(canvas, t, seg["start"] + 0.3, seg["end"] - 0.75, C.INTRO_KICKER, C.INTRO_TITLE,
                             C.INTRO_SUB, big=104)
        elif kind == "inter":
            draw_title_block(canvas, t, seg["start"] + 0.5, seg["end"] - 0.75, f"BAHAGIAN {seg['next_index']}",
                             seg["next_title"].upper(), None, big=88)
        elif kind == "outro":
            draw_title_block(canvas, t, seg["start"] + 0.6, seg["end"] - 0.2, C.OUTRO_KICKER, C.OUTRO_TITLE,
                             C.OUTRO_SUB, big=96)
    draw_progress(canvas, t)
    draw_flash(canvas, t)
    # global fade in / out
    if t < 0.6:
        canvas.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - ease(t / 0.6))))))
    if t > TL["duration"] - 0.8:
        canvas.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * ease((t - TL["duration"] + 0.8) / 0.8)))))
    if guides:
        d = ImageDraw.Draw(canvas)
        d.rectangle(C.SAFE, outline=(0, 255, 0, 255), width=3)
        d.rectangle(C.ACTION_SAFE, outline=(255, 0, 255, 255), width=2)
    return canvas.convert("RGB")


# ---------------------------------------------------------------- driver
VF = (f"scale={CW}:{CH}:flags=lanczos,unsharp=5:5:0.6:5:5:0.0,"
      "eq=contrast=1.06:saturation=1.12:gamma=0.98,format=rgb24")


def decode_frames(path, start=0.0, nframes=None, dur=None):
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-i", str(path)]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vf", f"fps={FPS}," + VF, "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = 0
    fsz = CW * CH * 3
    while nframes is None or n < nframes:
        buf = p.stdout.read(fsz)
        if len(buf) < fsz:
            break
        yield buf
        n += 1
    p.stdout.close()
    p.wait()


def still(path, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", str(path), "-frames:v", "1",
                          "-vf", VF, "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return raw[: CW * CH * 3]


def job_stream(clipdir):
    """Yields (frame_index, t, frame_bytes|None, prev_bytes|None, next_bytes|None) in order."""
    clips = TL["clips"]
    firsts = [still(clipdir / c["file"], c["inp"]) for c in clips]
    lasts = [still(clipdir / c["file"], c["inp"] + c["dur"] - 0.1) for c in clips]
    n_total = int(round(TL["duration"] * FPS))
    gen, cur = None, None
    for n in range(n_total):
        t = n / FPS
        seg = TL["at"](t)
        if seg["kind"] == "clip":
            if cur is not seg:
                gen, cur = decode_frames(clipdir / seg["file"], seg["inp"], dur=seg["dur"]), seg
            buf = next(gen, None)
            if buf is None:
                buf = lasts[seg["index"] - 1]
            yield n, t, buf, None, None
        else:
            pi = seg.get("prev_index")
            ni = seg.get("next_index")
            yield n, t, None, lasts[pi - 1] if pi else None, firsts[ni - 1] if ni else None


def _img(b):
    return None if b is None else Image.frombuffer("RGB", (CW, CH), b)


def _work(job):
    n, t, f, p, q = job
    return render(t, _img(f), _img(p), _img(q)).tobytes()


def main():
    import pathlib
    ap = argparse.ArgumentParser()
    ap.add_argument("clipdir")
    ap.add_argument("out")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--preview", default="")
    ap.add_argument("--guides", action="store_true")
    a = ap.parse_args()
    clipdir = pathlib.Path(a.clipdir)

    if a.preview:
        for ts in a.preview.split(","):
            t = float(ts)
            seg = TL["at"](t)
            f = p = q = None
            if seg["kind"] == "clip":
                f = _img(still(clipdir / seg["file"], seg["inp"] + t - seg["start"]))
            else:
                if seg.get("prev_index"):
                    c = TL["clips"][seg["prev_index"] - 1]
                    p = _img(still(clipdir / c["file"], c["inp"] + c["dur"] - 0.1))
                if seg.get("next_index"):
                    nc = TL["clips"][seg["next_index"] - 1]
                    q = _img(still(clipdir / nc["file"], nc["inp"]))
            render(t, f, p, q, a.guides).save(f"{a.out}_{t:06.2f}.jpg", quality=90)
            print("still", t, seg["kind"], flush=True)
        return

    enc = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-profile:v", "high",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-movflags", "+faststart", a.out],
        stdin=subprocess.PIPE)
    # bounded in-flight window: never buffer more than a few frames (avoids running out of memory)
    from collections import deque
    window_n = a.workers * 3
    with mp.Pool(a.workers) as pool:
        pending = deque()
        i = 0

        def drain(keep):
            nonlocal i
            while len(pending) > keep:
                enc.stdin.write(pending.popleft().get())
                if i % 300 == 0:
                    print(f"frame {i} t={i / FPS:.1f}s / {TL['duration']:.1f}s", flush=True)
                i += 1

        for job in job_stream(clipdir):
            pending.append(pool.apply_async(_work, (job,)))
            drain(window_n)
        drain(0)
    enc.stdin.close()
    enc.wait()
    print("done")


if __name__ == "__main__":
    main()
