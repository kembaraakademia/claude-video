# AI Video Editor

Letak video mentah, beri satu arahan, Claude edit sampai siap.

```
ai-video-editor/
  raw_footage/     <- letak video mentah di sini (atau beri link folder Google Drive)
  reference/       <- video / link rujukan gaya + STYLE.md (nota gaya: inspirasi, bukan tiru)
  export/          <- video siap (+ export/qc/ untuk still semakan safe zone)
  projects/<nama>/ <- skrip edit setiap projek (boleh disunting & dijana semula)
  tools/           <- alat kongsi: fetch_drive.py, cut_pauses.py
  assets/fonts/    <- font (lesen OFL disertakan)
  PROMPT.md        <- templat arahan "satu prompt"
```

## Aliran kerja

1. **Footage** — letak video dalam `raw_footage/`, atau:
   ```bash
   python3 tools/fetch_drive.py "<link folder Google Drive>"
   ```
2. **Gaya** — letak video rujukan dalam `reference/` (atau link). Claude tulis ringkasan gaya dalam
   `reference/STYLE.md` dan *ambil inspirasi sahaja — jangan tiru*.
3. **Prompt** — salin `PROMPT.md`, isi platform & mesej, hantar kepada Claude.
4. **Edit** — Claude akan: transkrip (Whisper) → buang jeda janggal (`cut_pauses.py`) → subtitle →
   motion graphic & SFX → muzik (ducking) → semak safe zone → `export/`.
5. **Feedback** — contoh: "hook terlalu kecil, besarkan sikit" → Claude betulkan & render semula.

## Buang jeda janggal

```bash
python3 tools/cut_pauses.py raw_footage/klip.mov export/klip_tight.mp4 --lang ms
python3 tools/cut_pauses.py raw_footage/klip.mov export/klip_tight.mp4 --dry-run       # senarai potongan sahaja
python3 tools/cut_pauses.py raw_footage/klip.mov export/klip_tight.mp4 --fillers       # buang "err/emm/aaa" juga
```

- Jeda lebih `--max-gap` (0.6 s) dipendekkan kepada `--keep-gap` (0.25 s) — bukan dibuang terus, supaya
  rentak masih semula jadi.
- Perkataan tak akan terpotong: masa perkataan Whisper + semakan tenaga bunyi + padding.
- `export/klip_tight.cuts.json` = senarai potongan + masa setiap perkataan pada timeline baharu
  (terus boleh guna untuk subtitle).

## Safe zone

| Platform | Kawasan selamat (1080×1920 / 1920×1080) |
|---|---|
| TikTok / IG Reels | atas 250 px, bawah 440 px, kanan 150 px, kiri 60 px dikosongkan |
| YouTube 16:9 | title-safe 90% (96 px kiri/kanan, 54 px atas/bawah) |

`python3 projects/<nama>/edit.py --preview 2.5,6.0` hasilkan still dengan garis safe zone dalam `export/qc/`.
