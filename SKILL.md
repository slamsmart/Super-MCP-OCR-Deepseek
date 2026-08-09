---
name: mcp-ocr
description: Baca teks dari GAMBAR dan DOKUMEN via MCP OCR (tool mcp__ocr__read_document, alias mcp__ocr__ocr_image). Gunakan SAAT user kasih gambar/screenshot/foto/scan/PDF/Word/Excel/PPT dan minta dibaca, dianalisa, atau di-fix (screenshot error, stack trace, pesan bug, dokumen scan, proposal PDF, laporan docx, data xlsx, slide pptx), ATAU saat gambar DI-PASTE langsung di kolom chat opencode (error "Cannot read image / model does not support image input") — ekstrak dulu dari DB opencode via extract-pasted-image.py. Memberi 'mata' ke model tanpa vision (mis. DeepSeek v4 Flash): semua format diubah jadi teks murni yang bisa dianalisa. Triggers: baca gambar ini, lihat screenshot, ocr, gambar error, analisa screenshot, fix bug dari gambar, scan dokumen, baca pdf/docx/xlsx/pptx, image to text, mata, vision, paste gambar, gambar tempelan, cannot read image.
---

# MCP-OCR — Baca Gambar & Dokumen Jadi Teks

Tools:
- **`mcp__ocr__read_document(file_path, mode="auto", enhance=true)`** — nama utama
- `mcp__ocr__ocr_image(...)` — alias kompatibel (fungsi sama)

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

## Verifikasi / troubleshooting
- Tes cepat semua format (tanpa MCP): `.venv/Scripts/python.exe server.py --selftest <file-atau-folder>`
- `claude mcp get ocr` → Status harus `Connected` (scope user = semua project).
- Restart sesi Claude Code kalau tool belum muncul (atau `/mcp` reconnect).
- Kalau model jawab "API Error 500 max instances / 401 Insufficient balance" → itu masalah kuota gateway model (cc.freemodel.dev), BUKAN MCP. Top up saldo lalu ulangi:
  `echo "Baca <file> via mcp__ocr__read_document lalu rangkum" | claude -p --allowedTools "mcp__ocr__*"`
- Server: `~/.claude/mcp-ocr/server.py` (venv Python 3.12 via uv). Update deps: `cd ~/.claude/mcp-ocr && uv sync`. Selftest: `.venv/Scripts/python.exe server.py --selftest <path>`.
