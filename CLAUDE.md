# Projek video — panduan untuk Claude

Pengguna berbahasa Melayu; balas dalam Bahasa Melayu.

## Aliran kerja edit video (ikut `ai-video-editor/README.md`)
1. Footage dalam `ai-video-editor/raw_footage/` (atau `python3 ai-video-editor/tools/fetch_drive.py <link Drive>`).
2. Baca `ai-video-editor/reference/STYLE.md` + rujukan di situ: ambil inspirasi, jangan tiru.
3. Transkrip dengan Whisper large-v3 (`condition_on_previous_text=False`). Kenal pasti bahasa sebenar
   dahulu — klip QH ternyata Bahasa Arab walaupun Whisper meneka "ms".
4. Buang jeda janggal: `ai-video-editor/tools/cut_pauses.py` (semak `--dry-run` dulu).
5. Skrip edit setiap projek dalam `ai-video-editor/projects/<nama>/edit.py`; output ke `ai-video-editor/export/`.
6. QC wajib: still dengan garis safe zone, semak glyph font (fonttools), tiada kapsyen bertindih,
   −14 LUFS (TikTok/YouTube) / −16 LUFS (Islamik tenang), true peak ≤ −1 dBTP, A/V sync.
7. Jangan tambah teks/mesej yang tidak disebut penceramah; tanda bahagian yang kurang pasti.

## Projek lain dalam repo
- `edit/` — IMG_5030 (reel pertama).
- `islamic/` — IMG_3434, Islamic cinematic 4K (Surah At-Taubah).
- `youtube_qh/` — VID QH 2–6 digabung, YouTube 1080p (Surah At-Tin, Bahasa Arab).
