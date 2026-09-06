---
name: mcp-ocr
description: Baca teks dari GAMBAR dan DOKUMEN via MCP OCR (tool mcp__ocr__read_document, alias mcp__ocr__ocr_image) DAN ekstrak WARNA dominan dari gambar (mcp__ocr__read_colors). Gunakan SAAT user memberikan gambar/screenshot/foto/scan/PDF/Word/Excel/PPT untuk dibaca, dianalisa, atau diperbaiki (screenshot error, stack trace, pesan bug, dokumen scan, proposal PDF, laporan docx, data xlsx, slide pptx), ATAU saat gambar DI-PASTE langsung di kolom chat opencode (error "Cannot read image / model does not support image input") — ekstrak dulu dari DB opencode via extract-pasted-image.py. Juga saat user ingin mengetahui/mengedit WARNA dari screenshot web (copas tampilan web, ganti warna, cari hex): gunakan read_colors. Memberi "mata" ke model teks-only tanpa vision (mis. DeepSeek v4 Flash, DeepSeek R1): semua format diubah menjadi teks murni yang bisa dianalisa. Triggers: baca gambar ini, lihat screenshot, ocr, gambar error, analisa screenshot, fix bug dari gambar, scan dokumen, baca pdf/docx/xlsx/pptx, image to text, mata, vision, paste gambar, gambar tempelan, cannot read image, warna apa, cari hex warna, color palette, warna dominan, edit warna.
---

# MCP-OCR — Baca Gambar & Dokumen Jadi Teks + Ekstrak Warna

Memberi "mata" ke model AI teks-only (mis. DeepSeek v4 Flash, DeepSeek R1): semua
gambar & dokumen dibaca menjadi teks murni yang bisa langsung dianalisa.

```
Gambar / PDF / Word / Excel / PPT
        │
        ▼
[ MCP OCR Server ] ──► teks murni ──► LLM bisa baca & jawab
```

## Tools

- **`mcp__ocr__read_document(file_path, mode="auto", enhance=true)`** — nama utama (teks)
- `mcp__ocr__ocr_image(...)` — alias kompatibel (fungsi sama)
- **`mcp__ocr__read_colors(file_path, top_n=8, merge=true)`** — warna dominan dari gambar

## Format didukung

| Format | Cara baca |
|---|---|
| Gambar: png, jpg/jpeg, webp, bmp, gif, tif/tiff | OCR (RapidOCR) + pre-process |
| PDF | teks asli diekstrak; halaman scan otomatis di-OCR per halaman (max 25 hal) |
| docx | paragraf + tabel |
| xlsx/xlsm | semua sheet, baris → tab-separated |
| pptx | semua slide, teks + tabel |
| rtf | teks |
| txt, md, csv, json, xml, log, yaml, toml, html | baca langsung |

**Tidak didukung:** `.doc`/`.xls` versi lama → minta user simpan ulang sebagai
`.docx`/`.xlsx` terlebih dahulu.

## Cara pakai

1. Terima path gambar/dokumen (absolut atau relatif ke working dir), atau URL `http(s)`/`file://`.
2. Panggil `read_document(file_path="<path-atau-url>")`.
3. Hasil = header metadata + teks murni → analisa, cari bug, perbaiki.

Contoh:

```
read_document(file_path="C:/Users/.../test-failed-1.png")
read_document(file_path="proposal.pdf")
read_document(file_path="laporan-bug.docx", mode="text", enhance=true)
```


## Gambar yang DI-PASTE di chat (opencode) — WAJIB ekstrak dulu

**Situasi:** user paste gambar langsung di kolom chat opencode lalu minta dibaca
(atau muncul error "Cannot read image / model does not support image input").
Gambar **tidak** tersimpan sebagai file — opencode menyimpannya di database SQLite
(`opencode.db`, tabel `part`) sebagai base64 data-URL. Model teks-only tidak bisa
melihat bytes-nya.

**Solusi (WAJIB dijalankan, jangan minta user simpan manual):**

1. Ekstrak gambar terakhir dari DB → file temp:
   ```bash
   python <skill-dir>/extract-pasted-image.py
   ```
   Output JSON: `{"paths": ["/.../pasted-XXXX.png"], "count": 1}`. Ambil `paths[0]`.
   - Opsi: `--session <id>` (filter session), `--n <N>` (ekstrak N gambar terakhir, default 1), `--outdir <dir>` (default temp), `--db <path>` (lokasi opencode.db, auto-detect dari `~/.local/share/opencode/` lalu `~/.config/opencode/`).
   - Script hanya butuh Python + stdlib (sqlite3, base64, json). Support: png/jpg/webp/bmp/gif/tiff (deteksi dari MIME part).
2. OCR file hasil ekstrak:
   ```
   read_document(file_path="<path hasil ekstrak>")
   ```
3. Analisa teksnya seperti biasa.

**Catatan:** jika hasil ekstrak salah gambar (terlalu lama), gunakan `--n 3` lalu
OCR satu per satu sampai menemukan gambar yang dimaksud user.

## Parameter

| Param | Nilai | Fungsi |
|---|---|---|
| `file_path` | path lokal / URL | wajib |
| `mode` | `auto` \| `text` \| `code` | urutan baris OCR (`code` terbaik untuk stack trace) |
| `enhance` | `true` (default) | autocontrast + upscale teks kecil |


## Baca warna dari gambar (`read_colors`) — untuk edit warna / copas web

Model teks-only **tidak bisa melihat warna**. `read_colors` menerjemahkan warna
gambar menjadi teks berstruktur: hex + rgb + nama + shade + % area + region.
Cocok untuk: copy-paste screenshot halaman web, ingin mengganti warna, mencari
nilai hex yang dipakai desain.

```
read_colors(file_path="web-design.png")
read_colors(file_path="ui.png", top_n=12)        # lebih banyak warna
read_colors(file_path="ui.png", merge=false)     # tanpa menggabungkan shade dekat
```

Contoh output:

```
[COLORS] web-design.png — 1280x800px — top 6 warna dominan
1. #FFFFFF  rgb(255, 255, 255)  ~white (light)  53.1%  posisi: background
2. #1F2937  rgb(31, 41, 55)  ~custom (dark)  19.8%  posisi: header/navbar
3. #3B82F6  rgb(59, 130, 246)  ~custom (dark)  6.5%  posisi: accent/panel
```

Region label: `background`, `header/navbar`, `footer`, `sidebar`, `panel/card`,
`accent/button/text`, `band`. Nilai hex siap tempel ke CSS/Tailwind. Warna dengan
nama yang bukan warna umum dilabel `~custom` — gunakan hex/rgb-nya, bukan namanya.

## Instalasi server (sekali, sebelum skill dipakai)

```bash
git clone https://github.com/slamsmart/Super-MCP-OCR-Deepseek ~/.claude/mcp-ocr
cd ~/.claude/mcp-ocr && uv sync          # Python 3.12 via uv
claude mcp add ocr --scope user -- ~/.claude/mcp-ocr/.venv/Scripts/python.exe ~/.claude/mcp-ocr/server.py
```

Di Linux/macOS gunakan `.venv/bin/python` alih-alih `.venv/Scripts/python.exe`.

## Verifikasi / troubleshooting

- Tes cepat semua format (tanpa MCP): `python <skill-dir>/server.py --selftest <file-atau-folder>`
- `claude mcp get ocr` → Status harus `Connected` (scope user = semua project).
- Tool belum muncul? Restart sesi klien (atau `/mcp` reconnect).
- Update deps: `cd <skill-dir> && uv sync`.
- OCR hasil jelek → pakai `mode="code"` untuk stack trace; pastikan `enhance=true`.
- "API Error 500 max instances / 401 Insufficient balance" → masalah kuota gateway
  model, BUKAN MCP OCR. Top up saldo lalu ulangi.
