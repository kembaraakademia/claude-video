"""Hand-authored Islamic SVG icons (gold line-art) -> transparent PNGs via headless Chromium.

usage: python icons.py   (writes assets/icons/*.svg, then runs render_icons.js -> *.png)
"""
import math
import pathlib
import subprocess

OUT = pathlib.Path(__file__).parent / "assets" / "icons"
GOLD = "#D4AF37"
GOLD_LIGHT = "#F1D98A"
IVORY = "#F8F5EC"

DEFS = f"""
<defs>
  <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{GOLD_LIGHT}"/><stop offset="1" stop-color="{GOLD}"/>
  </linearGradient>
  <radialGradient id="glow" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="#FFE7A3" stop-opacity="0.9"/>
    <stop offset="1" stop-color="#FFE7A3" stop-opacity="0"/>
  </radialGradient>
</defs>"""


def svg(body, vb="0 0 512 512"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="512" height="512">'
            f'{DEFS}<g fill="none" stroke="url(#g)" stroke-width="10" stroke-linecap="round" '
            f'stroke-linejoin="round">{body}</g></svg>')


def star_points(cx, cy, r_out, r_in, n, rot=-90):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 180 / n)
        pts.append(f"{cx + r * math.cos(a):.1f},{cy + r * math.sin(a):.1f}")
    return " ".join(pts)


ICONS = {}

# Crescent + star
ICONS["crescent_star"] = svg(f"""
  <mask id="cm"><rect width="512" height="512" fill="white"/><circle cx="318" cy="222" r="148" fill="black"/></mask>
  <circle cx="236" cy="262" r="176" fill="url(#g)" stroke="none" mask="url(#cm)"/>
  <polygon points="{star_points(372, 230, 56, 23, 5)}" fill="url(#g)" stroke="none"/>
""")

# Open Quran on a rehal (folding stand)
ICONS["quran_rehal"] = svg("""
  <circle cx="256" cy="200" r="150" fill="url(#glow)" stroke="none" opacity="0.55"/>
  <path d="M256 168 C212 140 150 136 96 152 L96 300 C150 284 212 288 256 316 Z" fill="url(#g)" fill-opacity="0.16"/>
  <path d="M256 168 C300 140 362 136 416 152 L416 300 C362 284 300 288 256 316 Z" fill="url(#g)" fill-opacity="0.16"/>
  <path d="M256 168 L256 316"/>
  <path d="M128 186 C168 176 206 180 232 194" stroke-width="6" opacity="0.8"/>
  <path d="M128 214 C168 204 206 208 232 222" stroke-width="6" opacity="0.8"/>
  <path d="M128 242 C168 232 206 236 232 250" stroke-width="6" opacity="0.8"/>
  <path d="M384 186 C344 176 306 180 280 194" stroke-width="6" opacity="0.8"/>
  <path d="M384 214 C344 204 306 208 280 222" stroke-width="6" opacity="0.8"/>
  <path d="M384 242 C344 232 306 236 280 250" stroke-width="6" opacity="0.8"/>
  <path d="M86 304 L322 452 M426 304 L190 452"/>
  <path d="M86 304 L130 300 M426 304 L382 300"/>
  <path d="M170 452 L210 452 M302 452 L342 452"/>
""")

# Tasbih (prayer beads): 33 beads + imam bead + tassel
beads = []
for i in range(33):
    a = math.radians(-90 + 360 * (i + 0.5) / 34 + 5)
    beads.append(f'<circle cx="{256 + 150 * math.cos(a):.1f}" cy="{220 + 130 * math.sin(a):.1f}" r="12" '
                 f'fill="url(#g)" fill-opacity="0.45" stroke-width="5"/>')
ICONS["tasbih"] = svg("".join(beads) + """
  <ellipse cx="256" cy="372" rx="16" ry="22" fill="url(#g)" fill-opacity="0.5" stroke-width="6"/>
  <path d="M256 394 L256 420"/>
  <path d="M240 420 L272 420 L282 486 M248 420 L246 490 M264 420 L266 490 M240 420 L230 486" stroke-width="6"/>
""")

# Islamic lantern (fanous)
ICONS["lantern"] = svg("""
  <circle cx="256" cy="300" r="190" fill="url(#glow)" stroke="none" opacity="0.7"/>
  <circle cx="256" cy="46" r="18"/>
  <path d="M256 64 L256 92"/>
  <path d="M196 150 C200 110 226 92 256 92 C286 92 312 110 316 150 Z" fill="url(#g)" fill-opacity="0.25"/>
  <path d="M180 150 L332 150 L352 176 L160 176 Z" fill="url(#g)" fill-opacity="0.3"/>
  <path d="M170 176 L342 176 L320 380 L192 380 Z" fill="#FFE7A3" fill-opacity="0.12"/>
  <path d="M256 176 L256 380 M213 176 L224 380 M299 176 L288 380"/>
  <path d="M176 230 L336 230 M184 320 L328 320" stroke-width="6"/>
  <path d="M236 270 a20 26 0 0 1 40 0 l0 30 l-40 0 z" fill="#FFF3C4" fill-opacity="0.8" stroke-width="5"/>
  <path d="M192 380 L320 380 L300 420 L212 420 Z" fill="url(#g)" fill-opacity="0.3"/>
  <path d="M232 420 L256 462 L280 420"/>
""")

# Mosque silhouette (filled)
ICONS["mosque"] = svg("""
  <g fill="url(#g)" stroke="none">
    <path d="M150 300 C150 210 210 170 256 120 C302 170 362 210 362 300 Z"/>
    <rect x="252" y="80" width="8" height="44"/>
    <path d="M268 70 A16 16 0 1 0 268 98 A12 12 0 1 1 268 70 Z"/>
    <rect x="120" y="300" width="272" height="160"/>
    <rect x="52" y="200" width="36" height="260"/>
    <path d="M44 204 L96 204 L70 150 Z"/>
    <rect x="66" y="128" width="8" height="24"/>
    <rect x="424" y="200" width="36" height="260"/>
    <path d="M416 204 L468 204 L442 150 Z"/>
    <rect x="438" y="128" width="8" height="24"/>
    <rect x="40" y="456" width="432" height="16"/>
  </g>
  <g fill="#101828" fill-opacity="0.55" stroke="none">
    <path d="M232 460 L232 400 A24 24 0 0 1 280 400 L280 460 Z"/>
    <path d="M160 360 L160 336 A14 14 0 0 1 188 336 L188 360 Z"/>
    <path d="M324 360 L324 336 A14 14 0 0 1 352 336 L352 360 Z"/>
  </g>
""")

# Rub el Hizb style 8-point star with inner rosette (decorative)
ICONS["star8"] = svg(f"""
  <rect x="106" y="106" width="300" height="300" />
  <rect x="106" y="106" width="300" height="300" transform="rotate(45 256 256)"/>
  <polygon points="{star_points(256, 256, 120, 70, 8, -90)}" stroke-width="6" opacity="0.8"/>
  <circle cx="256" cy="256" r="46" stroke-width="6"/>
""")

# Sunrise (for "hari seterusnya" — hope / a new day)
rays = "".join(
    f'<path d="M{256 + 150 * math.cos(math.radians(a)):.1f} {330 + 150 * math.sin(math.radians(a)):.1f} '
    f'L{256 + 215 * math.cos(math.radians(a)):.1f} {330 + 215 * math.sin(math.radians(a)):.1f}"/>'
    for a in range(-170, -9, 20))
ICONS["sunrise"] = svg(f"""
  <circle cx="256" cy="330" r="200" fill="url(#glow)" stroke="none" opacity="0.6"/>
  {rays}
  <path d="M136 330 A120 120 0 0 1 376 330 Z" fill="url(#g)" fill-opacity="0.3"/>
  <path d="M60 330 L452 330"/>
  <path d="M120 380 L392 380" stroke-width="7" opacity="0.7"/>
  <path d="M180 424 L332 424" stroke-width="6" opacity="0.5"/>
""")


# ---- Surah At-Tin set
# Fig (at-tin): round fruit with stem, leaf and a cut-open half showing seeds
ICONS["fig"] = svg("""
  <path d="M236 150 C170 160 120 230 128 310 C136 392 196 440 256 440 C316 440 376 392 384 310 C392 230 342 160 276 150 Z"
        fill="url(#g)" fill-opacity="0.22"/>
  <path d="M236 150 C240 120 250 100 256 84 C262 100 272 120 276 150"/>
  <path d="M262 96 C300 50 370 48 410 70 C380 110 320 128 270 112 Z" fill="url(#g)" fill-opacity="0.35"/>
  <path d="M272 108 C320 86 360 76 400 72" stroke-width="5"/>
  <ellipse cx="256" cy="318" rx="70" ry="86" fill="#101828" fill-opacity="0.35" stroke-width="6"/>
  <g fill="url(#g)" stroke="none">
    <circle cx="236" cy="290" r="7"/><circle cx="270" cy="282" r="7"/><circle cx="252" cy="318" r="7"/>
    <circle cx="282" cy="320" r="7"/><circle cx="230" cy="338" r="7"/><circle cx="262" cy="352" r="7"/>
    <circle cx="244" cy="372" r="6"/><circle cx="276" cy="376" r="6"/><circle cx="226" cy="306" r="5"/>
  </g>
""")

# Olive branch (az-zaitun): leaves alternate on both sides of a curved twig
leaves = []
bx0, by0, bx1, by1 = 110, 430, 410, 100
ang = math.degrees(math.atan2(by1 - by0, bx1 - bx0))
for i, k in enumerate([0.18, 0.3, 0.42, 0.54, 0.66, 0.78, 0.9]):
    px, py = bx0 + (bx1 - bx0) * k, by0 + (by1 - by0) * k
    side = 1 if i % 2 == 0 else -1
    la = ang + side * 50
    lx = px + 48 * math.cos(math.radians(la))
    ly = py + 48 * math.sin(math.radians(la))
    leaves.append(f'<path d="M{px:.0f} {py:.0f} L{(px + lx) / 2:.0f} {(py + ly) / 2:.0f}" stroke-width="5"/>'
                  f'<ellipse cx="{lx:.0f}" cy="{ly:.0f}" rx="44" ry="15" transform="rotate({la:.0f} {lx:.0f} {ly:.0f})" '
                  f'fill="url(#g)" fill-opacity="0.35" stroke-width="6"/>')
ICONS["olive"] = svg(f'<path d="M{bx0} {by0} Q 230 300 {bx1} {by1}"/>' + "".join(leaves) + """
  <ellipse cx="196" cy="372" rx="19" ry="26" fill="url(#g)" fill-opacity="0.9" stroke-width="5" transform="rotate(35 196 372)"/>
  <ellipse cx="318" cy="246" rx="17" ry="24" fill="url(#g)" fill-opacity="0.9" stroke-width="5" transform="rotate(35 318 246)"/>
""")

# Mountain (Tur Sinin) with sun glow
ICONS["mountain"] = svg("""
  <circle cx="330" cy="170" r="150" fill="url(#glow)" stroke="none" opacity="0.6"/>
  <circle cx="330" cy="170" r="44" fill="url(#g)" fill-opacity="0.35"/>
  <path d="M40 430 L200 190 L262 270 L310 214 L472 430 Z" fill="url(#g)" fill-opacity="0.22"/>
  <path d="M200 190 L172 246 L196 236 L214 258 L232 230" stroke-width="7"/>
  <path d="M310 214 L292 246 L312 240 L330 256" stroke-width="7"/>
  <path d="M30 430 L482 430"/>
""")

# Kaaba (al-balad al-amin)
ICONS["kaaba"] = svg("""
  <circle cx="256" cy="260" r="210" fill="url(#glow)" stroke="none" opacity="0.4"/>
  <path d="M120 170 L256 120 L392 170 L392 400 L256 450 L120 400 Z" fill="#101828" fill-opacity="0.75"/>
  <path d="M120 170 L256 220 L392 170 M256 220 L256 450"/>
  <path d="M120 228 L256 278 L392 228" stroke-width="16" stroke="url(#g)"/>
  <path d="M292 300 L352 278 L352 392 L292 414 Z" fill="url(#g)" fill-opacity="0.5" stroke-width="6"/>
""")

# Heart with light (iman)
ICONS["heart_light"] = svg("""
  <circle cx="256" cy="260" r="200" fill="url(#glow)" stroke="none" opacity="0.55"/>
  <path d="M256 420 C140 340 90 280 90 210 C90 150 136 110 188 110 C222 110 246 130 256 156
           C266 130 290 110 324 110 C376 110 422 150 422 210 C422 280 372 340 256 420 Z" fill="url(#g)" fill-opacity="0.25"/>
  <path d="M256 196 L256 300 M204 248 L308 248" stroke-width="8"/>
  <path d="M220 212 L292 284 M292 212 L220 284" stroke-width="5" opacity="0.7"/>
""")

# Seedling (amal soleh — good deeds that grow)
ICONS["seedling"] = svg("""
  <path d="M256 430 L256 250"/>
  <path d="M256 290 C200 290 150 250 140 180 C210 176 256 220 256 290 Z" fill="url(#g)" fill-opacity="0.35"/>
  <path d="M256 250 C262 180 320 120 400 120 C400 200 340 250 256 250 Z" fill="url(#g)" fill-opacity="0.35"/>
  <path d="M150 430 C200 400 312 400 362 430" />
  <path d="M110 452 L402 452" stroke-width="7" opacity="0.6"/>
""")

# Human form abstract: balance / "ahsan taqwim" — shown as a balanced scale (no figurative depiction)
ICONS["balance"] = svg("""
  <path d="M256 90 L256 420 M180 420 L332 420"/>
  <circle cx="256" cy="84" r="14" fill="url(#g)"/>
  <path d="M110 150 L402 150"/>
  <path d="M110 150 L70 270 L150 270 Z M402 150 L362 270 L442 270 Z" stroke-width="7"/>
  <path d="M62 270 C80 310 140 310 158 270 Z M354 270 C372 310 432 310 450 270 Z" fill="url(#g)" fill-opacity="0.4"/>
""")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, s in ICONS.items():
        (OUT / f"{name}.svg").write_text(s)
    subprocess.run(["node", str(pathlib.Path(__file__).parent / "render_icons.js"), str(OUT)], check=True)


if __name__ == "__main__":
    main()
