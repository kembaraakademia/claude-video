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

## Format menegak (TikTok/Reels)
- Set `window.WIDTH = 1080; window.HEIGHT = 1920;` dalam scene — render.js ikut saiz ini.
- render.js guna `-crf 23 -maxrate 10M` (tekstur grain tanpa had bitrate = fail >1GB).

## Gaya "vintage flat kinetic" (rujukan: end-project/selawat/)
- Palet: navy #1d2434, hijau zaitun #6e8c4c, mustard #e0b44c, krim #f4e4be, merah #b5392f, teal #2c7a7b.
- Fon (dalam style/fonts/): Bebas Neue (tajuk besar), Oswald (teks kecil/caps), Yellowtail (skrip), Amiri (Arab, termasuk ﷺ).
- Unsur: tekstur grain berubah ikut frame, vignet, bintang berkelip, bulan sabit, lencana bulat dengan sinar berputar,
  banner berhujung chevron, masjid siluet, tanglung berayun, gelang konsentrik + teks bulat (textPath).
- Kesan teks: rise, pop, smash (+shake), blurIn, whip (motion blur), huruf jatuh berperingkat, perkataan berselerak lalu berkumpul.
- Peralihan scene: chevDown, chevUp, iris, slideUp (clip-path / transform).
- Kandungan Islamik: jangan gambarkan Nabi ﷺ; guna dalil sahih dengan sumber (ayat + nombor, nama perawi hadis).

## Suara latar (voice-over)
- Pengguna jana suara di ElevenLabs (satu MP3 untuk semua babak, dengan `<break>` antara babak).
- Cari jeda: `ffmpeg -i x.mp3 -af silencedetect=noise=-35dB:d=0.6 -f null -`, padankan setiap segmen dengan skrip.
- Jika suara lebih panjang daripada babak, guna `TIMEMAP` + `mapTime()` dalam scene (lihat selawat/scene.html)
  untuk memanjangkan babak dengan gerak perlahan, bukan ubah semua masa animasi.
- Susun segmen dengan `atrim` + `adelay` + `amix`, `loudnorm=I=-16`, kemudian gabung: `-c:v copy -c:a aac`.
- Lafaz Arab: minta pengguna rakam suara sendiri (bukan AI).
