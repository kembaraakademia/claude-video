# Memory projek: claude-video

## Tujuan
Buat **motion graphic sepenuhnya tanpa video** (tiada footage/rakaman). Semua visual dijana
dengan kod HTML/CSS/JS dan dirender frame demi frame ke MP4.

## Peraturan kerja
- Komunikasi dengan pengguna dalam **Bahasa Melayu**.
- Setiap scene ialah satu `scene.html` 1920×1080 dalam `video-claude-motion/end-project/<nama-projek>/`.
- Animasi MESTI deterministik: semua keadaan dikira daripada masa `t` dalam `window.seek(t)`.
  Jangan guna CSS animation/transition, `setTimeout`, atau `Math.random()` tanpa seed.
- Setiap scene mesti set `window.DURATION` (saat) dan `window.FPS`.
- Warna/font dikongsi melalui `video-claude-motion/style/tema.css`.
- Render: `cd video-claude-motion && node render.js end-project/<projek>/scene.html end-project/<projek>/<nama>.mp4`
  (render.js guna CommonJS `require('playwright')` + ffmpeg libx264 yuv420p).
- Templat rujukan: `video-claude-motion/end-project/contoh-intro/`.
- Panduan penuh: `video-claude-motion/PANDUAN-MOTION-GRAPHIC.md`.
- Selepas render, semak satu frame (`ffmpeg -ss <saat> -i x.mp4 -frames:v 1 f.png`) sebelum serah kepada pengguna.
- Commit hasil (scene.html + mp4) supaya pengguna boleh muat turun dari GitHub.
