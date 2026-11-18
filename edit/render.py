"""Render motion graphics + captions over the source video (1080x1920, TikTok/IG safe zones).

usage: python render.py <input.mov> <sfx.wav> <output.mp4> [--guides]
"""
import math
import subprocess
import sys
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30000 / 1001
DUR = 15.98

# ---- Safe zone (common TikTok + IG Reels area at 1080x1920) ----
SAFE_TOP, SAFE_BOTTOM = 260, 1920 - 440  # top UI / bottom caption+buttons
SAFE_LEFT, SAFE_RIGHT = 120, 1080 - 160  # right action buttons
SAFE_CX = (SAFE_LEFT + SAFE_RIGHT) // 2

YELLOW = (255, 214, 10)
NAVY = (11, 27, 63)
WHITE = (255, 255, 255)
GREEN = (46, 204, 113)

FONT_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
FONT_XB = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"


@lru_cache(None)
def font(path, size):
    return ImageFont.truetype(path, size)


# ---------------- easing ----------------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_back(x, s=1.7):
    x = clamp(x) - 1
    return 1 + (s + 1) * x**3 + s * x**2


def ease_out_cubic(x):
    return 1 - (1 - clamp(x)) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 3 * x * x - 2 * x * x * x


def prog(t, start, dur):
    return clamp((t - start) / dur)


# ---------------- transcript-driven caption groups ----------------
# (text words, word start times, group end)
CAPTIONS = [
    (["LAJNAH", "DAKWAH"], [1.54, 2.10], 3.45),
    (["KEMUDIAN"], [3.60], 5.50),
    (["KITA", "MAKLUMLAH"], [5.66, 6.22], 6.72),
    (["LAJNAH", "EKONOMI"], [6.74, 7.04], 7.40),
    (["PUN", "BERAPA", "HARI?"], [7.42, 7.68, 7.94], 8.26),
    (["4", "HARI"], [8.28, 8.48], 8.74),
    (["4", "HARI", "BUAT", "PERKONGSIAN"], [8.76, 9.10, 9.84, 10.12], 10.64),
    (["4", "HARI,", "5", "HARI"], [10.66, 10.88, 11.12, 11.32], 12.60),
    (["6", "HARI?"], [12.78, 13.34], 14.02),
    (["6", "HARI", "KAN?"], [14.08, 14.48, 14.80], 15.98),
]
HIGHLIGHT = {"DAKWAH", "EKONOMI", "4", "5", "6", "PERKONGSIAN", "HARI?"}


@lru_cache(None)
def word_img(word, size, color):
    f = font(FONT_BLACK, size)
    stroke = max(4, size // 9)
    bbox = f.getbbox(word, stroke_width=stroke)
    w, h = bbox[2] - bbox[0] + 30, bbox[3] - bbox[1] + 40
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    # soft shadow
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((15 - bbox[0] + 4, 20 - bbox[1] + 8), word, font=f, fill=(0, 0, 0, 150),
                            stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    ImageDraw.Draw(im).text((15 - bbox[0], 20 - bbox[1]), word, font=f, fill=color,
                            stroke_width=stroke, stroke_fill=(0, 0, 0))
    return im


def paste_center(canvas, im, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    if alpha <= 0.01 or scale <= 0.01:
        return
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BICUBIC)
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 1.0:
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im = im.copy()
        im.putalpha(a)
    canvas.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def draw_captions(canvas, t):
    cy = 1330  # bottom edge of text ~1390 < SAFE_BOTTOM
    for words, starts, end in CAPTIONS:
        if not (starts[0] - 0.05 <= t < end):
            continue
        size = 92
        # layout: wrap into lines that fit the safe width
        imgs = [word_img(w, size, WHITE) for w in words]
        gap = 6
        maxw = SAFE_RIGHT - SAFE_LEFT
        total_w = sum(im.width for im in imgs) + gap * (len(imgs) - 1)
        if total_w <= maxw or len(imgs) == 1:
            lines = [list(range(len(imgs)))]
        else:  # split into two balanced lines
            half = (len(imgs) + 1) // 2
            lines = [list(range(half)), list(range(half, len(imgs)))]
        # shrink font until every line fits inside the safe width
        while size > 50:
            imgs = [word_img(w, size, WHITE) for w in words]
            widest = max(sum(imgs[i].width for i in ln) + gap * (len(ln) - 1) for ln in lines)
            if widest <= maxw:
                break
            size -= 4
        line_h = imgs[0].height - 22
        y0 = cy - (len(lines) - 1) * line_h / 2
        fade_out = 1 - prog(t, end - 0.08, 0.08)
        for li, line in enumerate(lines):
            total = sum(imgs[i].width for i in line) + gap * (len(line) - 1)
            x = SAFE_CX - total / 2
            for i in line:
                st = starts[i]
                active_until = starts[i + 1] if i + 1 < len(starts) else end
                p = prog(t, st, 0.18)
                if t < st:
                    x += imgs[i].width + gap
                    continue
                active = st <= t < active_until
                w = words[i]
                color = YELLOW if (w in HIGHLIGHT or active) else WHITE
                im = word_img(w, size, color)  # same size as layout
                sc = 0.6 + 0.4 * ease_out_back(p) + (0.06 if active else 0)
                paste_center(canvas, im, x + imgs[i].width / 2, y0 + li * line_h + (1 - ease_out_cubic(p)) * 30,
                             scale=sc, alpha=min(1, p * 3) * fade_out)
                x += imgs[i].width + gap


# ---------------- topic card (top) ----------------
@lru_cache(None)
def topic_card(label, top):
    f_small = font(FONT_XB, 34)
    f_big = font(FONT_BLACK, 76)
    tw = max(f_big.getlength(label), f_small.getlength(top)) + 110
    w, h = int(tw), 190
    im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((24, 30, w + 24, h + 30), 34, fill=(0, 0, 0, 140))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((20, 20, w + 20, h + 20), 34, fill=NAVY + (235,))
    d.rounded_rectangle((20, 20, 40, h + 20), 10, fill=YELLOW)
    d.text((70, 42), top, font=f_small, fill=YELLOW)
    d.text((68, 82), label, font=f_big, fill=WHITE)
    return im


def draw_topic(canvas, t):
    cy = SAFE_TOP + 120
    # card 1: 1.4 -> 6.5, card 2: 6.6 -> end
    for label, t_in, t_out in [("DAKWAH", 1.30, 6.50), ("EKONOMI", 6.62, 99)]:
        if t < t_in or t > t_out + 0.3:
            continue
        p_in = ease_out_back(prog(t, t_in, 0.45), 1.3)
        p_out = ease_in_out(prog(t, t_out, 0.25))
        card = topic_card(label, "LAJNAH")
        x = SAFE_CX + (1 - p_in) * -900 + p_out * 900
        paste_center(canvas, card, x, cy, alpha=1 - p_out)


# ---------------- day counter (left, beside speaker) ----------------
@lru_cache(None)
def calendar_base():
    w, h = 300, 330
    im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((24, 32, w + 24, h + 32), 36, fill=(0, 0, 0, 150))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((20, 20, w + 20, h + 20), 36, fill=WHITE)
    d.rounded_rectangle((20, 20, w + 20, 110), 36, fill=YELLOW)
    d.rectangle((20, 80, w + 20, 110), fill=YELLOW)
    for rx in (95, w - 55):
        d.rounded_rectangle((rx, 4, rx + 22, 52), 11, fill=NAVY)
    f = font(FONT_BLACK, 44)
    d.text((20 + w / 2, 68), "HARI", font=f, fill=NAVY, anchor="mm")
    return im


@lru_cache(None)
def number_img(txt, color):
    f = font(FONT_BLACK, 190)
    bbox = f.getbbox(txt)
    im = Image.new("RGBA", (bbox[2] - bbox[0] + 20, bbox[3] - bbox[1] + 20), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10 - bbox[0], 10 - bbox[1]), txt, font=f, fill=color)
    return im


@lru_cache(None)
def chip(text):
    f = font(FONT_BLACK, 40)
    w = int(f.getlength(text)) + 56
    im = Image.new("RGBA", (w, 76), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, 75), 38, fill=NAVY + (240,))
    d.text((w / 2, 38), text, font=f, fill=YELLOW, anchor="mm")
    return im


def draw_counter(canvas, t):
    T_IN = 8.10
    if t < T_IN:
        return
    cx, cy = SAFE_LEFT + 175, 760  # left of speaker's head, inside safe area
    p = ease_out_back(prog(t, T_IN, 0.4), 1.6)
    base = calendar_base()
    # wobble on "6?"
    rot = 0.0
    if 12.78 <= t < 14.08:
        rot = 6 * math.sin((t - 12.78) * 18) * math.exp(-(t - 12.78) * 2.5)
    card = base.copy()
    # number states
    states = [(8.28, "4", NAVY), (11.12, "5", NAVY), (12.78, "6?", (220, 60, 60)), (14.08, "6", NAVY)]
    cur, prev, ts = None, None, 0
    for st, txt, col in states:
        if t >= st:
            prev, cur, ts = cur, (txt, col), st
    if cur:
        k = ease_out_cubic(prog(t, ts, 0.22))
        inner = Image.new("RGBA", (300, 220), (0, 0, 0, 0))
        n_new = number_img(*cur)
        if prev and k < 1:  # flip/slide: old slides up, new rises in
            n_old = number_img(*prev)
            inner.alpha_composite(n_old, (150 - n_old.width // 2, int(110 - n_old.height / 2 - k * 220)))
        inner.alpha_composite(n_new, (150 - n_new.width // 2, int(110 - n_new.height / 2 + (1 - k) * 220)))
        card.alpha_composite(inner, (20, 126))
    paste_center(canvas, card, cx, cy, scale=p, rot=rot)

    # progress dots: days filled
    filled = 0
    for st, n in [(8.28, 4), (11.12, 5), (14.08, 6)]:
        if t >= st:
            filled, last = n, st
    dot_y = cy + 220
    d = ImageDraw.Draw(canvas)
    for i in range(6):
        dx = cx - 125 + i * 50
        r = 17
        if i < filled:
            pop_k = ease_out_back(prog(t, last, 0.3), 3) if i == filled - 1 else 1
            rr = r * (0.4 + 0.6 * pop_k) * p
            col = GREEN if filled == 6 else YELLOW
            d.ellipse((dx - rr, dot_y - rr, dx + rr, dot_y + rr), fill=col, outline=(0, 0, 0), width=4)
        else:
            rr = r * p
            d.ellipse((dx - rr, dot_y - rr, dx + rr, dot_y + rr), fill=(255, 255, 255, 90), outline=(0, 0, 0), width=4)

    # "PERKONGSIAN" chip
    if 9.84 <= t < 12.6:
        pc = ease_out_back(prog(t, 9.84, 0.3), 2)
        fade = 1 - prog(t, 12.4, 0.2)
        paste_center(canvas, chip("PERKONGSIAN"), cx, dot_y + 75, scale=pc, alpha=fade)

    # confirm check + burst ring at "6 hari kan?"
    if t >= 14.08:
        k = prog(t, 14.08, 0.5)
        ring = ImageDraw.Draw(canvas)
        rr = 120 + 160 * ease_out_cubic(k)
        a = int(255 * (1 - k))
        if a > 0:
            ring.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=GREEN + (a,), width=10)
        ck = ease_out_back(prog(t, 14.15, 0.35), 2.5)
        bx, by, br = cx + 140, cy - 150, 46 * ck
        if br > 1:
            ring.ellipse((bx - br, by - br, bx + br, by + br), fill=GREEN, outline=WHITE, width=6)
            s = br / 46
            ring.line([(bx - 20 * s, by), (bx - 5 * s, by + 16 * s), (bx + 22 * s, by - 16 * s)], fill=WHITE,
                      width=max(1, int(10 * s)), joint="curve")


# ---------------- camera moves ----------------
ZOOM_KEYS = [  # (time, zoom)
    (0.0, 1.00), (1.45, 1.03), (1.75, 1.10), (6.6, 1.10), (6.9, 1.04), (12.0, 1.06),
    (12.85, 1.14), (13.9, 1.15), (14.2, 1.20), (15.98, 1.22),
]
FOCUS = (600, 700)  # speaker's face in the frame


def zoom_at(t):
    for (t0, z0), (t1, z1) in zip(ZOOM_KEYS, ZOOM_KEYS[1:]):
        if t0 <= t <= t1:
            return z0 + (z1 - z0) * ease_in_out((t - t0) / (t1 - t0))
    return ZOOM_KEYS[-1][1]


def apply_zoom(frame, z):
    if z <= 1.0001:
        return frame
    cw, ch = W / z, H / z
    fx, fy = FOCUS
    x0 = clamp(fx - cw * fx / W, 0, W - cw)
    y0 = clamp(fy - ch * fy / H, 0, H - ch)
    return frame.transform((W, H), Image.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.BICUBIC)


def draw_guides(canvas):
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    red = (255, 0, 0, 90)
    d.rectangle((0, 0, W, SAFE_TOP), fill=red)
    d.rectangle((0, SAFE_BOTTOM, W, H), fill=red)
    d.rectangle((0, SAFE_TOP, SAFE_LEFT, SAFE_BOTTOM), fill=red)
    d.rectangle((SAFE_RIGHT, SAFE_TOP, W, SAFE_BOTTOM), fill=red)
    d.rectangle((SAFE_LEFT, SAFE_TOP, SAFE_RIGHT, SAFE_BOTTOM), outline=(0, 255, 0, 255), width=4)
    canvas.alpha_composite(ov)


def render_frame(frame, t, guides=False):
    frame = apply_zoom(frame, zoom_at(t)).convert("RGBA")
    draw_topic(frame, t)
    draw_counter(frame, t)
    draw_captions(frame, t)
    if guides:
        draw_guides(frame)
    return frame.convert("RGB")


def main():
    src, sfx, out = sys.argv[1:4]
    guides = "--guides" in sys.argv
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-vf", f"scale={W}:{H}", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "30000/1001", "-i", "-",
        "-i", src, "-i", sfx,
        "-filter_complex",
        "[1:a]aresample=48000,highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=5:release=80,"
        "volume=2[v];[2:a]volume=0.9[s];[v][s]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=9[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out,
    ], stdin=subprocess.PIPE)
    n, fsz = 0, W * H * 3
    while True:
        buf = dec.stdout.read(fsz)
        if len(buf) < fsz:
            break
        img = Image.frombuffer("RGB", (W, H), buf)
        enc.stdin.write(render_frame(img, n / FPS, guides).tobytes())
        n += 1
        if n % 60 == 0:
            print(f"frame {n}", flush=True)
    enc.stdin.close()
    enc.wait()
    dec.wait()
    print("done", n, "frames")


if __name__ == "__main__":
    main()
