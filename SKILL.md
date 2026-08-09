---
name: mcp-ocr
description: Baca teks dari GAMBAR dan DOKUMEN via MCP OCR (tool mcp__ocr__read_document, alias mcp__ocr__ocr_image) DAN ekstrak WARNA dari gambar (mcp__ocr__read_colors). Gunakan SAAT user kasih gambar/screenshot/foto/scan/PDF/Word/Excel/PPT dan minta dibaca, dianalisa, atau di-fix (screenshot error, stack trace, pesan bug, dokumen scan, proposal PDF, laporan docx, data xlsx, slide pptx), ATAU saat gambar DI-PASTE langsung di kolom chat opencode (error "Cannot read image / model does not support image input") — ekstrak dulu dari DB opencode via extract-pasted-image.py. Juga saat user mau tahu/ngedit WARNA dari screenshot web (copas tampilan web, ganti warna, cari hex): pakai read_colors. Memberi 'mata' ke model tanpa vision (mis. DeepSeek v4 Flash): semua format diubah jadi teks murni yang bisa dianalisa. Triggers: baca gambar ini, lihat screenshot, ocr, gambar error, analisa screenshot, fix bug dari gambar, scan dokumen, baca pdf/docx/xlsx/pptx, image to text, mata, vision, paste gambar, gambar tempelan, cannot read image, warna apa, cari hex warna, color palette, warna dominan, edit warna.
---

# MCP-OCR — Baca Gambar & Dokumen Jadi Teks + Ekstrak Warna

Tools:
- **`mcp__ocr__read_document(file_path, mode="auto", enhance=true)`** — nama utama (teks)
- `mcp__ocr__ocr_image(...)` — alias kompatibel (fungsi sama)
- **`mcp__ocr__read_colors(file_path, top_n=8, merge=true)`** — warna dominan dari gambar

## Format didukung
| Format | Cara baca |
|---|---|
| Gambar: png, jpg/jpeg, webp, bmp, gif, tif/tiff | OCR (RapidOCR) + pre-process |
| **PDF** | teks asli diekstrak; **halaman scan otomatis di-OCR** per halaman (max 25 hal) |
| **docx** | paragraf + tabel |
| **xlsx/xlsm** | semua sheet, baris → tab-separated |
| **pptx** | semua slide, teks + tabel |
| **rtf** | teks |
| txt, md, csv, json, xml, log, yaml, toml, html | baca langsung |

Tidak didukung: `.doc`/`.xls` versi lama → suruh user simpan ulang sebagai `.docx`/`.xlsx`.

## Cara pakai
1. Path gambar/dokumen (absolut/relatif ke working dir) atau URL http(s)/file://.
2. `read_document(file_path="<path-atau-url>")`
3. Hasil = teks murni + metadata → analisa, cari bug, fix.

Contoh:
```
read_document(file_path="C:/Users/.../test-failed-1.png")
read_document(file_path="proposal.pdf")
read_document(file_path="laporan-bug.docx", mode="text", enhance=true)
```

## Gambar yang DI-PASTE di chat (opencode) — WAJIB ekstrak dulu

**Situasi:** user paste gambar langsung di kolom chat opencode, lalu minta dibaca (atau kamu dapat error "Cannot read image.png / model does not support image input"). Gambar **tidak** tersimpan sebagai file — opencode simpan di database SQLite sebagai base64, model tanpa vision tidak bisa lihat bytes-nya.

**Solusi (WAJIB jalanin, jangan minta user simpan manual):**

1. Ekstrak gambar terakhir dari DB → file temp:
   ```
   python <skill-dir>/extract-pasted-image.py
   ```
   Output JSON: `{"paths": ["C:/.../pasted-XXXX.png"], "count": 1}`. Ambil `paths[0]`.
   - Opsi: `--session <id>` (filter session), `--n <N>` (ekstrak N gambar terakhir), `--outdir <dir>`.
2. OCR file hasil ekstrak:
   ```
   read_document(file_path="<path hasil ekstrak>")
   ```
3. Analisa teksnya seperti biasa.

**Verifikasi path skill:** `C:\Users\Organizer1\.claude\skills\mcp-ocr\extract-pasted-image.py`. Script butuh Python + stdlib saja (sqlite3, base64, json). Support: png/jpg/webp/bmp/gif/tiff (deteksi dari MIME part).

**Catatan:** kalau ekstrak ambil gambar salah (misal terlalu lama), gunakan `--n 3` lalu OCR satu-satu sampai ketemu gambar yang dimaksud user.

## Parameter
| Param | Nilai | Fungsi |
|---|---|---|
| `file_path` | path lokal / URL | wajib |
| `mode` | `auto` \| `text` \| `code` | urutan baris OCR (`code` terbaik utk stack trace) |
| `enhance` | `true` (default) | autocontrast + upscale teks kecil |

## Baca warna dari gambar (`read_colors`) — untuk edit warna / copas web

DeepSeek & model teks-only **tidak bisa lihat warna**. `read_colors` terjemahkan warna gambar jadi teks: hex + rgb + nama + shade + % area + region. Cocok buat: copy-paste screenshot halaman web, mau ganti warna, cari nilai hex yang dipakai desain.

```
read_colors(file_path="web-design.png")
read_colors(file_path="ui.png", top_n=12)        # lebih banyak warna
read_colors(file_path="ui.png", merge=false)     # tanpa gabung shade dekat
```

Contoh output:
```
[COLORS] web-design.png — 1280x800px — top 6 warna dominan
1. #FFFFFF  rgb(255, 255, 255)  ~white (light)  53.1%  posisi: background
2. #1F2937  rgb(31, 41, 55)  ~custom (dark)  19.8%  posisi: header/navbar
3. #3B82F6  rgb(59, 130, 246)  ~custom (dark)  6.5%  posisi: accent/panel
```

Region label: `background`, `header/navbar`, `footer`, `sidebar`, `panel/card`, `accent/button/text`, `band`. Nilai hex sudah siap tempel ke CSS/Tailwind. Warna yang namanya bukan warna umum (Tailwind dll) dilabel `~custom` — pakai hex/rgb-nya, bukan namanya.

## Verifikasi / troubleshooting
- Tes cepat semua format (tanpa MCP): `.venv/Scripts/python.exe server.py --selftest <file-atau-folder>`
- `claude mcp get ocr` → Status harus `Connected` (scope user = semua project).
- Restart sesi Claude Code kalau tool belum muncul (atau `/mcp` reconnect).
- Kalau model jawab "API Error 500 max instances / 401 Insufficient balance" → itu masalah kuota gateway model (cc.freemodel.dev), BUKAN MCP. Top up saldo lalu ulangi:
  `echo "Baca <file> via mcp__ocr__read_document lalu rangkum" | claude -p --allowedTools "mcp__ocr__*"`
- Server: `~/.claude/mcp-ocr/server.py` (venv Python 3.12 via uv). Update deps: `cd ~/.claude/mcp-ocr && uv sync`. Selftest: `.venv/Scripts/python.exe server.py --selftest <path>`.
