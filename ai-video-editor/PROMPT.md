# Templat "satu prompt"

Salin, isi bahagian `< >`, dan hantar kepada Claude.

---

Edit video dalam `ai-video-editor/raw_footage/` (atau folder Drive ini: `<link>`).

- Platform: `<TikTok/IG Reels 9:16 | YouTube 16:9>` — ikut safe zone platform itu.
- Bahasa ucapan: `<Melayu | Arab | Inggeris>`; subtitle dalam `<bahasa>`.
- Mesej / topik: `<ringkas>`
- Gaya: rujuk `ai-video-editor/reference/` (`STYLE.md` + video/link di situ). **Ambil inspirasi sahaja,
  jangan tiru** — supaya editing kita nampak lain daripada orang lain.
- Langkah:
  1. Transkrip dulu (Whisper), semak & betulkan teks.
  2. Buang jeda janggal (`tools/cut_pauses.py`), jangan potong perkataan.
  3. Subtitle ikut perkataan, kata kunci ditonjolkan.
  4. Motion graphic yang relevan dengan setiap ayat + SFX selari.
  5. Muzik latar sesuai (tanpa hak cipta), ducking bawah suara.
  6. Gabung klip jika lebih dari satu; buang rakaman berulang.
  7. Semak safe zone, kenyaringan (−14 LUFS), tiada teks terpotong.
  8. Export ke `ai-video-editor/export/` — versi dengan & tanpa muzik.
