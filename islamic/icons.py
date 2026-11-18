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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, s in ICONS.items():
        (OUT / f"{name}.svg").write_text(s)
    subprocess.run(["node", str(pathlib.Path(__file__).parent / "render_icons.js"), str(OUT)], check=True)


if __name__ == "__main__":
    main()
