# Panduan: Buat Motion Graphic Sepenuhnya Tanpa Video

Semua visual dijana dengan **kod** (HTML + CSS + JavaScript). Tiada footage, tiada
rakaman kamera, tiada screen-record. Setiap frame dilukis, ditangkap sebagai gambar,
dan digabung menjadi MP4 dengan ffmpeg.

## Konsep utama

1. **Scene = satu fail HTML** bersaiz 1920×1080.
2. **Animasi deterministik**: semua gerakan dikira daripada masa `t` (saat) dalam
   fungsi `window.seek(t)`. Jangan guna CSS `animation`/`transition` atau `setTimeout`
   — masa sebenar tidak dipakai semasa render.
3. **Render frame demi frame**: `render.js` buka scene dalam Chromium (Playwright),
   panggil `seek(i / FPS)` untuk setiap frame, screenshot PNG, hantar ke ffmpeg.
4. Hasil: MP4 H.264 yang licin dan tepat 30/60 fps, tanpa frame tercicir.

## Struktur folder

```
video-claude-motion/
├── render.js                 # enjin render HTML -> MP4
├── style/tema.css            # warna, font, saiz kanvas (ubah di sini)
├── video/                    # (pilihan) aset tambahan: SVG, PNG, audio
└── end-project/
    └── contoh-intro/
        ├── scene.html        # contoh scene
        └── contoh-intro.mp4  # hasil render
```

## Cara guna

1. Salin `end-project/contoh-intro/` ke folder baharu, cth `end-project/projek-saya/`.
2. Ubah `scene.html`:
   - `window.DURATION` (saat) dan `window.FPS`.
   - Tambah elemen dalam `<div id="stage">`.
   - Animasikan dalam `window.seek(t)` guna helper:
     - `prog(t, mula, tempoh)` → nilai 0..1
     - `lerp(a, b, p)` → interpolasi
     - `ease.outCubic / inOutCubic / outBack` → easing
3. Pratonton: buka `scene.html` terus di browser (animasi loop automatik).
4. Render:
   ```bash
   node render.js end-project/projek-saya/scene.html end-project/projek-saya/hasil.mp4
   ```

## Corak animasi biasa

| Kesan | Kod dalam `seek(t)` |
|---|---|
| Fade in | `el.style.opacity = prog(t, 1, 0.5)` |
| Slide naik | `el.style.transform = \`translateY(${lerp(80,0,ease.outCubic(p))}px)\`` |
| Pop/scale | `el.style.transform = \`scale(${ease.outBack(p)})\`` |
| Putar | `el.style.transform = \`rotate(${t*90}deg)\`` |
| Stagger huruf | pecah teks jadi `<span>`, mula setiap huruf `+ i*0.07` saat |
| Garisan memanjang | animasi `width` dari 0 ke nilai akhir |
| Kiraan nombor | `el.textContent = Math.round(lerp(0, 1000, p))` |

## Tambah audio (pilihan)

```bash
ffmpeg -i hasil.mp4 -i muzik.mp3 -c:v copy -c:a aac -shortest hasil-audio.mp4
```

## Format lain

- Menegak (Reels/TikTok/Shorts): tukar 1920×1080 → 1080×1920 dalam `tema.css` dan `render.js` (viewport).
- GIF: `ffmpeg -i hasil.mp4 -vf "fps=15,scale=640:-1" hasil.gif`

## Keperluan

- Node.js + Playwright (Chromium)
- ffmpeg

Pemasangan di komputer sendiri:
```bash
npm install playwright && npx playwright install chromium
```
(ffmpeg: `brew install ffmpeg` di Mac, `sudo apt install ffmpeg` di Linux, atau muat turun dari ffmpeg.org di Windows.)

## Alternatif lain (tanpa video juga)

- **Remotion** (React → MP4) — konsep sama (`useCurrentFrame()`), lebih sesuai projek besar.
- **Manim** (Python) — sesuai untuk animasi matematik/diagram.
- **Lottie / After Effects** — jika guna alat GUI.
