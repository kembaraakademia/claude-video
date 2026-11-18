# IMG_3434 — Premium Islamic Cinematic Motion Graphic

Penaiktarafan video tazkirah IMG_3434 (Surah At-Taubah 9:91 & 9:120). Suara, mesej, susunan dan
komposisi asal dikekalkan.

## Analisis video asal

| Item | Nilai |
|---|---|
| Resolusi | 3840×2160 (4K UHD) |
| Nisbah / orientasi | 16:9 landskap |
| FPS | ~30 (iPhone VFR, avg 30.004) → output CFR 30 |
| Tempoh | 72.96 s |
| Warna | HEVC 10-bit **HLG HDR** (BT.2020) → ditonemap ke SDR BT.709 untuk keserasian media sosial |
| Audio | AAC mono 48 kHz. Bahagian 69–71 s ialah senyap digital (dalam fail asal) |

## Struktur

```
islamic/
  config.py        # SEMUA tetapan: palet, font, timeline ayat/panel/kapsyen, zoom, tahap audio
  render.py        # motion graphics (PIL + numpy, berbilang proses) -> video tanpa audio
  music.py         # muzik instrumental Arab asli (disintesis: oud, ney, strings, pad, daf lembut)
  mix.py           # SFX + mixing voice-first (ducking) + mux -> MP4 dengan/tanpa muzik
  icons.py         # ikon Islamik SVG (vektor) -> render_icons.js (Chromium) -> PNG
  assets/fonts/    # Noto Naskh Arabic, Amiri, Poppins (lesen OFL disertakan)
  assets/icons/    # *.svg (sumber boleh diedit) + *.png
  transcript/      # output Whisper large-v3 (timestamp perkataan) + transkrip disemak
```

## Cara jana semula

```bash
cd islamic
python3 icons.py                                   # (perlu NODE_PATH=$(npm root -g) untuk playwright)
python3 render.py IMG_3434.mov out/video_only.mp4 --workers 3
python3 render.py IMG_3434.mov out/qc --preview 15,33,62 --guides   # still QC + garis safe area
python3 music.py out/music.wav
python3 mix.py IMG_3434.mov out/video_only.mp4 out/music.wav out/
```

Untuk guna muzik/SFX berlesen anda sendiri: gantikan `music.wav` dengan fail anda (stereo 48 kHz)
sebelum `mix.py` — ducking dikira automatik daripada suara narator.

## Tetapan audio (config.AUDIO)

- Suara: EQ sederhana (HPF 75 Hz, −2 dB @220 Hz, +2 dB @3.2 kHz), kompresor 2.5:1; sasaran **−16 LUFS**.
- Muzik: −23 dB relatif suara ketika bercakap, −14 dB ketika jeda; attack 180 ms, release 800 ms.
  Ketika bacaan ayat al-Quran (4.2–21 s, 43.8–46.8 s) muzik ditahan lebih rendah lagi, tiada melodi.
- SFX: whoosh lembut, shimmer, chime, impact lembut, angin — di jeda / isyarat visual.
- Limiter true-peak (oversampled 4×) → ≤ −1 dBTP.
