"""Premium Islamic cinematic motion-graphics pass over IMG_3434 (keeps 3840x2160 16:9).

usage:
  python render.py <src.mov> <out_video_only.mp4> [--workers 3] [--preview t1,t2,...] [--guides]
The output has no audio; mix.py muxes the mixed audio (with / without music) afterwards.
"""
import argparse
import math
import multiprocessing as mp
import subprocess
import sys
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config as C

W, H, FPS = C.W, C.H, C.FPS

# HLG (BT.2020) -> SDR BT.709 tonemap, gentle warm cinematic grade + vignette
DECODE_VF = (
    "zscale=tin=arib-std-b67:min=bt2020nc:pin=bt2020:t=linear:npl=203,format=gbrpf32le,"
    "zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,"
    f"fps={FPS},"
    "eq=contrast=1.05:saturation=1.04:gamma=0.98,"
    "colorbalance=rs=0.015:gs=0.0:bs=-0.02:rm=0.02:bm=-0.015:rh=0.015:bh=-0.02,"
    "vignette=angle=PI/4.6,format=rgb24"
)


# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(x):  # smooth in-out
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def window(t, t0, t1, fin=0.6, fout=0.5):
    """0..1 envelope: fade in after t0, fade out before t1."""
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
    if alpha <= 0.004:
        return
    if abs(scale - 1) > 1e-3:
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.BICUBIC)
    im = with_alpha(im, alpha)
    x, y = round(cx - im.width / 2), round(cy - im.height / 2)
    # clip to canvas
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + im.width), min(H, y + im.height)
    if x1 <= x0 or y1 <= y0:
        return
    if (x0, y0, x1, y1) != (x, y, x + im.width, y + im.height):
        im = im.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    canvas.alpha_composite(im, (x0, y0))


def shadowed(im, blur=18, opacity=0.65, offset=(0, 8), pad=40):
    """Return sprite with soft drop shadow (adds padding)."""
    out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    a = im.getchannel("A").point(lambda v: int(v * opacity))
    sh = Image.new("RGBA", im.size, C.NAVY + (0,))
    sh.putalpha(a)
    tmp = Image.new("RGBA", out.size, (0, 0, 0, 0))
    tmp.alpha_composite(sh, (pad + offset[0], pad + offset[1]))
    out.alpha_composite(tmp.filter(ImageFilter.GaussianBlur(blur)))
    out.alpha_composite(im, (pad, pad))
    return out


@lru_cache(None)
def text_sprite(text, fpath, size, color, arabic=False, tracking=0):
    f = font(fpath, size)
    kw = dict(direction="rtl", language="ar") if arabic else {}
    if tracking and not arabic:
        widths = [f.getlength(ch) + tracking for ch in text]
        tw = int(sum(widths)) + 4
        asc, desc = f.getmetrics()
        im = Image.new("RGBA", (tw, asc + desc + 10), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        x = 0
        for ch, w in zip(text, widths):
            d.text((x, 4), ch, font=f, fill=color)
            x += w
        return im
    bbox = f.getbbox(text, **kw)
    asc, desc = f.getmetrics()
    pad = int(size * 0.35) if arabic else 6
    im = Image.new("RGBA", (bbox[2] - bbox[0] + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - bbox[0], pad), text, font=f, fill=color, **kw)
    return im


@lru_cache(None)
def icon(name, size):
    im = Image.open(C.ICONS / f"{name}.png").convert("RGBA")
    return im.resize((size, size), Image.LANCZOS)


@lru_cache(None)
def soft_dot(r, color):
    s = r * 6
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((s / 2 - r, s / 2 - r, s / 2 + r, s / 2 + r), fill=color + (255,))
    im = im.filter(ImageFilter.GaussianBlur(r * 0.9))
    d = ImageDraw.Draw(im)
    d.ellipse((s / 2 - r * 0.45, s / 2 - r * 0.45, s / 2 + r * 0.45, s / 2 + r * 0.45), fill=(255, 246, 214, 255))
    return im.filter(ImageFilter.GaussianBlur(max(1, r * 0.25)))


# ---------------------------------------------------------------- static layers
@lru_cache(None)
def bottom_gradient():
    """Dark navy gradient on the lower third for caption contrast."""
    h = 760
    a = (np.linspace(0, 1, h) ** 1.6 * 175).astype(np.uint8)
    arr = np.zeros((h, W, 4), np.uint8)
    arr[..., :3] = C.NAVY
    arr[..., 3] = a[:, None]
    return Image.fromarray(arr, "RGBA")


@lru_cache(None)
def light_rays():
    """Soft god-rays from top-left (half-res, upscaled when used)."""
    w, h = W // 2, H // 2
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ox, oy = -w * 0.08, -h * 0.25
    ang = np.arctan2(yy - oy, xx - ox)
    dist = np.hypot(xx - ox, yy - oy)
    beams = (0.5 + 0.5 * np.sin(ang * 23)) ** 6 + 0.6 * (0.5 + 0.5 * np.sin(ang * 9 + 1.3)) ** 8
    fall = np.exp(-dist / (w * 0.55))
    a = np.clip(beams * fall * 255, 0, 255).astype(np.uint8)
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = 255, 236, 190
    arr[..., 3] = a
    return Image.fromarray(arr, "RGBA").filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)


@lru_cache(None)
def sweep_band():
    w = 900
    x = np.linspace(-1, 1, w)
    a = (np.exp(-x * x * 5) * 120).astype(np.uint8)
    arr = np.zeros((H, w, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = 255, 238, 196
    arr[..., 3] = a[None, :]
    return Image.fromarray(arr, "RGBA").rotate(-14, resample=Image.BICUBIC, expand=True)


@lru_cache(None)
def veil(color, top_alpha, bottom_alpha):
    a = np.linspace(top_alpha, bottom_alpha, H).astype(np.uint8)
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = a[:, None]
    return Image.fromarray(arr, "RGBA")


# ---------------------------------------------------------------- glass panel
def glass(frame, box, alpha, radius=60, tint=C.EMERALD, tint_a=150):
    """Frosted emerald glass with gold hairline border, composited in place."""
    if alpha <= 0.004:
        return
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    region = frame.crop((x0, y0, x1, y1)).convert("RGB")
    small = region.resize((max(1, w // 10), max(1, h // 10)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
    blur = small.resize((w, h), Image.BICUBIC).convert("RGBA")
    blur.alpha_composite(Image.new("RGBA", (w, h), tint + (tint_a,)))
    # subtle top sheen
    sheen = np.zeros((h, w, 4), np.uint8)
    sheen[..., :3] = 255
    sheen[..., 3] = (np.clip(1 - np.linspace(0, 1, h) * 2.5, 0, 1) * 22).astype(np.uint8)[:, None]
    blur.alpha_composite(Image.fromarray(sheen, "RGBA"))
    mask = rounded_mask(w, h, radius)
    blur.putalpha(mask.point(lambda v: int(v * alpha)))
    frame.alpha_composite(blur, (x0, y0))
    border = rounded_border(w, h, radius)
    frame.alpha_composite(with_alpha(border, alpha), (x0, y0))


@lru_cache(None)
def rounded_mask(w, h, r):
    m = Image.new("L", (w * 2, h * 2), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 2 - 1, h * 2 - 1), r * 2, fill=255)
    return m.resize((w, h), Image.LANCZOS)


@lru_cache(None)
def rounded_border(w, h, r):
    s = 2
    m = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((3, 3, w * s - 4, h * s - 4), r * s, outline=C.GOLD + (200,), width=5)
    d.rounded_rectangle((22, 22, w * s - 23, h * s - 23), r * s - 18, outline=C.GOLD + (70,), width=2)
    return m.resize((w, h), Image.LANCZOS)


@lru_cache(None)
def ornament_line(width):
    """Gold hairline with a small 8-point star in the middle."""
    h = 60
    im = Image.new("RGBA", (width * 2, h * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = width, h
    for side in (-1, 1):
        d.line((cx + side * 46, cy, cx + side * width * 0.98, cy), fill=C.GOLD + (220,), width=4)
    pts = []
    for i in range(16):
        r = 34 if i % 2 == 0 else 15
        a = math.radians(-90 + i * 22.5)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=C.GOLD + (255,))
    return im.resize((width, h), Image.LANCZOS)


# ---------------------------------------------------------------- layers
def draw_atmosphere(frame, t):
    # light rays: breathing opacity, brighter during "hari seterusnya" (sunrise moment)
    k = 0.30 + 0.08 * math.sin(t * 0.6)
    k += 0.35 * window(t, 63.4, 66.2, 0.8, 1.2)
    k *= 1 - 0.6 * window(t, C.OUTRO_START, 99, 1.5, 0.1)
    paste(frame, light_rays(), W / 2 + 40 * math.sin(t * 0.15), H / 2, alpha=k)

    # floating geometric stars (parallax, very faint)
    for (bx, by, size, speed, a) in [(3560, 330, 760, 2.2, 0.16), (250, 1930, 620, -1.6, 0.12)]:
        star = icon("star8", size)
        rot = star.rotate(t * speed, resample=Image.BILINEAR)
        paste(frame, rot, bx + 30 * math.sin(t * 0.21), by + 22 * math.cos(t * 0.17), alpha=a)

    # gold dust particles (two parallax layers, rising)
    rng = np.random.default_rng(3)
    n = 64
    xs, ys = rng.uniform(0, W, n), rng.uniform(0, H, n)
    speeds = rng.uniform(18, 70, n)
    rs = rng.choice([4, 6, 9, 13], n, p=[0.35, 0.3, 0.22, 0.13])
    ph = rng.uniform(0, 6.28, n)
    for i in range(n):
        y = (ys[i] - t * speeds[i]) % (H + 200) - 100
        x = xs[i] + 40 * math.sin(t * 0.4 + ph[i])
        tw = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 1.3 + ph[i] * 3))
        # keep the speaker's face clean
        if 1350 < x < 2500 and 150 < y < 1350:
            tw *= 0.15
        paste(frame, soft_dot(int(rs[i]), C.GOLD_LIGHT), x, y, alpha=tw * 0.75)


def draw_transitions(frame, t):
    for tt in C.TRANSITIONS:
        p = (t - tt) / 0.9
        if 0 <= p <= 1:
            band = sweep_band()
            x = -band.width / 2 + ease(p) * (W + band.width)
            paste(frame, band, x, H / 2, alpha=math.sin(p * math.pi) * 0.9)


# ---- side panel
PANEL_BOX = (250, 300, 1330, 1560)


def draw_panel(frame, t):
    for P in C.PANELS:
        a = window(t, P["start"], P["end"], 0.7, 0.55)
        if a <= 0:
            continue
        x0, y0, x1, y1 = PANEL_BOX
        cx = (x0 + x1) / 2
        rise = (1 - ease_out((t - P["start"]) / 0.8)) * 40
        glass(frame, (x0, y0 + rise, x1, y1 + rise), a)
        local = t - P["start"]
        # icon (gentle float), with optional cross-fade swap
        ic_name = P["icon"]
        isz = 440
        icy = y0 + 300 + rise + 10 * math.sin(t * 1.1)
        ia = a * ease((local - 0.15) / 0.7)
        sw = P.get("icon_swap")
        if sw and t >= sw[0]:
            k = ease((t - sw[0]) / 0.8)
            paste(frame, icon(ic_name, isz), cx, icy, alpha=ia * (1 - k), scale=1 + 0.05 * k)
            paste(frame, icon(sw[1], isz), cx, icy, alpha=ia * k, scale=0.95 + 0.05 * k)
        else:
            paste(frame, icon(ic_name, isz), cx, icy, alpha=ia, scale=0.92 + 0.08 * ease_out((local - 0.15) / 0.9))
        # kicker + ornament
        ka = a * ease((local - 0.35) / 0.6)
        ky = y0 + 600 + rise
        paste(frame, text_sprite(P["kicker"], C.F_SANS_SB, 50, C.GOLD, tracking=10), cx, ky, alpha=ka)
        paste(frame, ornament_line(760), cx, ky + 62, alpha=ka)
        y = ky + 150
        if P.get("arabic"):
            aa = a * ease((local - 0.55) / 0.7)
            spr = text_sprite(P["arabic"], C.F_ARABIC, 120, C.GOLD_LIGHT, arabic=True)
            paste(frame, spr, cx, y + 40, alpha=aa)
            y += 190
        body, hl = P["body"], P.get("highlight", [])
        if P.get("swap") and t >= P["swap"][0] - 0.4:
            st = P["swap"][0]
            if t < st:  # fade old body out
                draw_body(frame, body, hl, cx, y, a * (1 - ease((t - (st - 0.4)) / 0.4)), local, 0.6)
                continue
            body, hl = P["swap"][1], P["swap"][2]
            draw_body(frame, body, hl, cx, y, a, t - st, 0.0)
        else:
            draw_body(frame, body, hl, cx, y, a, local, 0.6)


def draw_body(frame, body, hl, cx, y, a, local, delay):
    for li, line in enumerate(body.split("\n")):
        la = a * ease((local - delay - 0.14 * li) / 0.6)
        if la <= 0:
            continue
        words = line.split(" ")
        sprs = [text_sprite(w, C.F_SANS, 62, C.GOLD_LIGHT if w.strip(",.") in hl else C.IVORY) for w in words]
        space = 18
        total = sum(s.width for s in sprs) + space * (len(sprs) - 1)
        x = cx - total / 2
        dy = (1 - ease_out((local - delay - 0.14 * li) / 0.7)) * 24
        for s in sprs:
            paste(frame, s, x + s.width / 2, y + li * 92 + dy, alpha=la)
            x += s.width + space


# ---- Arabic recitation card (lower third)
def draw_arabic(frame, t):
    for (t0, t1, text, ref) in C.ARABIC:
        a = window(t, t0, t1, 0.6, 0.45)
        if a <= 0:
            continue
        spr = text_sprite(text, C.F_ARABIC, 150, C.IVORY, arabic=True)
        cx, cy = W / 2, 1745
        bw = max(1500, spr.width + 380)
        bh = 330 if ref else 270
        rise = (1 - ease_out((t - t0) / 0.7)) * 30
        glass(frame, (cx - bw / 2, cy - bh / 2 + rise, cx + bw / 2, cy + bh / 2 + rise), a, radius=50,
              tint=C.NAVY, tint_a=165)
        # right-to-left soft wipe reveal, follows recitation pace
        dur = max(0.9, min(2.2, (t1 - t0) * 0.35))
        p = ease((t - t0 - 0.15) / dur)
        arr = np.asarray(spr).copy()
        w = arr.shape[1]
        edge = w * (1 - p * 1.25)
        xs = np.arange(w, dtype=np.float32)
        m = np.clip((xs - edge) / (w * 0.25), 0, 1)
        arr[..., 3] = (arr[..., 3] * m[None, :]).astype(np.uint8)
        ty = cy - (32 if ref else 8) + rise
        paste(frame, Image.fromarray(arr, "RGBA"), cx, ty, alpha=a)
        # gold ornaments at both ends
        orn = icon("star8", 110)
        for sx in (-1, 1):
            paste(frame, orn.rotate(t * 8 * sx, resample=Image.BILINEAR), cx + sx * (bw / 2 - 95), cy + rise, alpha=a * 0.9)
        if ref:
            ra = a * ease((t - t0 - 0.9) / 0.6)
            paste(frame, text_sprite(ref, C.F_SANS_SB, 46, C.GOLD, tracking=4), cx, cy + 110 + rise, alpha=ra)


# ---- Malay captions (word-synced)
CHUNKS = C.caption_chunks()


def draw_captions(frame, t):
    for ci, ch in enumerate(CHUNKS):
        st = ch[0][1] - 0.12
        nxt = CHUNKS[ci + 1][0][1] - 0.12 if ci + 1 < len(CHUNKS) else 999
        en = min(ch[-1][2] + 0.6, nxt)
        if not (st <= t <= en):
            continue
        out = ease((en - t) / 0.18) if en < nxt else 1.0
        sprs = []
        for (wtxt, ws, we) in ch:
            key = wtxt.strip(",.?!")
            active = ws - 0.05 <= t <= we + 0.05
            col = C.GOLD if active else (C.GOLD_LIGHT if key in C.CAPTION_HIGHLIGHT else C.IVORY)
            sprs.append((text_sprite(wtxt, C.F_SANS, 96, col), ws, wtxt, col))
        space = 28
        total = sum(sp[0].width for sp in sprs) + space * (len(sprs) - 1)
        x = W / 2 - total / 2
        cy = 1890
        for s, ws, wtxt, col in sprs:
            p = (t - ws + 0.12) / 0.28
            if p > 0:
                wa = ease(p) * out
                sh = caption_shadow(wtxt, col)
                paste(frame, sh, x + s.width / 2, cy + 10 + (1 - ease_out(p)) * 18, alpha=wa * 0.8)
                paste(frame, s, x + s.width / 2, cy + (1 - ease_out(p)) * 18, alpha=wa)
            x += s.width + space


@lru_cache(None)
def caption_shadow(wtxt, col):
    s = text_sprite(wtxt, C.F_SANS, 96, col)
    a = s.getchannel("A")
    sh = Image.new("RGBA", (s.width + 60, s.height + 60), (0, 0, 0, 0))
    blk = Image.new("RGBA", s.size, C.NAVY + (255,))
    blk.putalpha(a)
    sh.alpha_composite(blk, (30, 30))
    return sh.filter(ImageFilter.GaussianBlur(14)).crop((30, 30, 30 + s.width, 30 + s.height))


# ---- intro / outro
def draw_intro_outro(frame, t):
    # intro emerald veil dissolving
    va = 1 - ease((t - 0.2) / 2.6)
    if va > 0:
        paste(frame, veil(C.EMERALD, 150, 210), W / 2, H / 2, alpha=va * 0.75)
    # outro: emerald veil + rising mosque silhouette + crescent
    if t >= C.OUTRO_START:
        p = ease((t - C.OUTRO_START) / 1.6)
        paste(frame, veil(C.EMERALD, 120, 235), W / 2, H / 2, alpha=p * 0.85)
        # mosque sits on the right, clear of the speaker's face, inside the title-safe area
        m = icon("mosque", 1000)
        mp_ = ease_out((t - C.OUTRO_START - 0.3) / 2.2)
        mx, my = 3060, C.SAFE[3] - 530
        paste(frame, m, mx, my + (1 - mp_) * 140, alpha=mp_ * 0.95)
        cs = icon("crescent_star", 300)
        cp = ease_out((t - C.OUTRO_START - 1.2) / 1.6)
        paste(frame, cs, mx + 330, 520 + (1 - cp) * 40 + 8 * math.sin(t), alpha=cp * 0.95)
        paste(frame, ornament_line(900), mx, C.SAFE[3] - 70, alpha=cp)


def zoom_at(t):
    ks = C.ZOOM_KEYS
    for (t0, z0), (t1, z1) in zip(ks, ks[1:]):
        if t0 <= t <= t1:
            return z0 + (z1 - z0) * ease((t - t0) / (t1 - t0))
    return ks[-1][1]


def apply_zoom(img, z):
    if z <= 1.0005:
        return img
    fx, fy = C.FOCUS
    # affine: output (x,y) samples input (fx + (x - fx)/z, fy + (y - fy)/z)
    return img.transform((W, H), Image.AFFINE, (1 / z, 0, fx - fx / z, 0, 1 / z, fy - fy / z), Image.BILINEAR)


def draw_guides(frame):
    d = ImageDraw.Draw(frame)
    x0, y0, x1, y1 = C.SAFE
    d.rectangle((x0, y0, x1, y1), outline=(0, 255, 0, 255), width=6)
    d.rectangle(PANEL_BOX, outline=(255, 0, 255, 255), width=4)


def render_frame(img, t, guides=False):
    img = apply_zoom(img, zoom_at(t)).convert("RGBA")
    paste(img, bottom_gradient(), W / 2, H - bottom_gradient().height / 2, alpha=1.0)
    draw_atmosphere(img, t)
    draw_intro_outro(img, t)
    draw_transitions(img, t)
    draw_panel(img, t)
    draw_arabic(img, t)
    draw_captions(img, t)
    if t < C.FADE_IN[1]:
        img.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - ease(t / C.FADE_IN[1]))))))
    fo = ease((t - C.FADE_OUT[0]) / (C.FADE_OUT[1] - C.FADE_OUT[0]))
    if fo > 0:
        img.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * fo))))
    if guides:
        draw_guides(img)
    return img.convert("RGB")


# ---------------------------------------------------------------- driver
def _work(args):
    n, buf = args
    img = Image.frombuffer("RGB", (W, H), buf)
    return render_frame(img, n / FPS).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--preview", default="")
    ap.add_argument("--guides", action="store_true")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--dur", type=float, default=0)
    a = ap.parse_args()

    if a.preview:  # render selected stills (for QC)
        for ts in a.preview.split(","):
            t = float(ts)
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", a.src, "-frames:v", "1",
                                  "-vf", DECODE_VF, "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
            img = Image.frombuffer("RGB", (W, H), raw[: W * H * 3])
            render_frame(img, t, a.guides).save(f"{a.out}_{t:05.2f}.jpg", quality=88)
            print("still", t, flush=True)
        return

    dec_cmd = ["ffmpeg", "-v", "error"]
    if a.start:
        dec_cmd += ["-ss", f"{a.start:.3f}"]
    dec_cmd += ["-i", a.src]
    if a.dur:
        dec_cmd += ["-t", f"{a.dur:.3f}"]
    dec_cmd += ["-vf", DECODE_VF, "-f", "rawvideo", "-"]
    dec = subprocess.Popen(dec_cmd, stdout=subprocess.PIPE, bufsize=W * H * 3 * 2)
    enc = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-level", "5.1",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
    fsz = W * H * 3
    start_n = round(a.start * FPS)

    def frames():
        n = start_n
        while True:
            buf = dec.stdout.read(fsz)
            if len(buf) < fsz:
                return
            yield n, buf
            n += 1

    with mp.Pool(a.workers) as pool:
        for i, out in enumerate(pool.imap(_work, frames(), chunksize=1)):
            enc.stdin.write(out)
            if i % 60 == 0:
                print(f"frame {i + start_n} t={(i + start_n) / FPS:.1f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    dec.wait()
    print("done")


if __name__ == "__main__":
    sys.exit(main())
