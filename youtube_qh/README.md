# Surah At-Tin — gabungan VID QH 2–6 (YouTube 1920×1080)

Lima klip (848×464, 30 fps, Bahasa Arab) digabung menjadi satu video YouTube dengan latar animasi
(aurora emerald–emas, corak geometri, partikel), kad video berbingkai, kapsyen Arab + terjemahan Melayu,
panel callout, tajuk bab, intro/outro, muzik instrumental Arab asli, SFX dan mixing −14 LUFS.

## Susunan

| Bab | Sumber | Catatan |
|---|---|---|
| Intro | — | "Tadabbur Al-Quran · Surah At-Tin" |
| 1 Pengenalan | VID QH 2, 1.2–20.55 s | QH 2 selepas 20.55 s ialah versi awal sebab nuzul — diganti QH 3 (rakaman ulang yang lebih jelas) |
| 2 Sebab Nuzul | VID QH 3 | At-Tin 6 |
| 3 Pengajaran 1 & 2 | VID QH 4 | At-Tin 1–4 |
| 4 Pengajaran 3, 4 & 5 | VID QH 5 | At-Tin 5, 8 |
| 5 Penutup | VID QH 6 | Doa & salam |
| Outro | — | "Jumpa lagi" |

## Fail

```
content.py       # SUNTING DI SINI: teks Arab (disemak), terjemahan Melayu, tajuk bab, callout
config.py        # reka letak, warna, fon, tempoh intro/inter/outro, safe area
build_clips.py   # content.py + masa perkataan Whisper -> transcript/clips.json
render.py        # video (tanpa audio). --preview t1,t2 --guides untuk still QC
music.py         # muzik asli (oud, ney, strings, pad, daf) — maqam Nahawand
mix.py           # suara + muzik (ducking) + SFX -> MP4 dengan/tanpa muzik
transcript/      # output Whisper large-v3 (bahasa Arab) + clips.json
```

```bash
python3 build_clips.py <folder_klip>
python3 render.py <folder_klip> out/video_only.mp4 --workers 3
python3 music.py out/music.wav
python3 mix.py <folder_klip> out/video_only.mp4 out/music.wav output/
```

Fail klip dinamakan `qh2.mov` … `qh6.mov` (salinan "VID QH 2.MOV" … "VID QH 6.MOV").

## Safe area YouTube
Semua teks/grafik dalam title-safe 90% (96 px kiri/kanan, 54 px atas/bawah). Kapsyen & bar progres
di atas 1026 px.

## Audio
Suara: HPF, denoise ringan, EQ, kompresor 2.5:1, setiap klip dipadankan kenyaringannya.
Muzik: −22 dB di bawah suara semasa bercakap, naik pada jeda dan penuh pada intro/bab/outro.
Akhir: −14 LUFS, true peak ≤ −1 dBTP (limiter oversampled).
