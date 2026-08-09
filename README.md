# 🦉 Super MCP OCR for DeepSeek (teks-only LLM)

Memberi **"mata"** ke model AI yang tidak punya vision (mis. **DeepSeek v4 Flash**, DeepSeek R1, atau LLM teks-only lain) — semua gambar & dokumen dibaca jadi **teks murni** yang bisa langsung dianalisa.

```
Gambar / PDF / Word / Excel / PPT
        │
        ▼
   [ MCP OCR Server ]  ──►  teks murni  ──►  LLM bisa baca & jawab
```

---

## ✨ Fitur

| Format | Cara baca |
|---|---|
| 🖼️ Gambar — png, jpg/jpeg, webp, bmp, gif, tif/tiff | OCR (RapidOCR + pre-process) |
| 📄 PDF | teks asli diekstrak; halaman **scan otomatis di-OCR** per halaman (max 25 hal) |
| 📝 Office — docx, xlsx/xlsm, pptx, rtf | ekstrak paragraf, tabel, slide |
| 📃 Teks — txt, md, csv, json, xml, log, yaml, toml, html | baca langsung |

**Tidak didukung:** `.doc` / `.xls` versi lama → simpan ulang sebagai `.docx` / `.xlsx`.

**Tool yang tersedia:**
- `read_document(file_path, mode, enhance)` — nama penuh (teks)
- `ocr_image(image_path, mode, enhance)` — alias kompatibel (teks)
- `read_colors(file_path, top_n=8, merge=true)` — 🎨 **ekstrak warna dominan dari gambar**

---

## 🎨 Baca Warna dari Gambar (`read_colors`)

Model teks-only juga **tidak bisa melihat warna**. `read_colors` terjemahkan warna gambar jadi teks berstruktur — hex, rgb, nama, shade, persentase area, dan posisi region. Cocok buat: copy-paste screenshot halaman web, mau ganti warna desain, cari nilai hex yang dipakai.

```
read_colors(file_path="web-design.png")
read_colors(file_path="ui.png", top_n=12)        # lebih banyak warna
read_colors(file_path="ui.png", merge=false)     # tanpa gabung shade dekat
```

| Param | Nilai | Fungsi |
|---|---|---|
| `file_path` | path gambar lokal / URL | wajib |
| `top_n` | `8` (default) | jumlah warna teratas |
| `merge` | `true` (default) | gabung warna nyaris-sama (<30 delta) |

Contoh output:

```
[COLORS] web-design.png — 1280x800px — top 6 warna dominan
1. #FFFFFF  rgb(255, 255, 255)  ~white (light)  53.1%  posisi: background
2. #1F2937  rgb(31, 41, 55)  ~custom (dark)  19.8%  posisi: header/navbar
3. #3B82F6  rgb(59, 130, 246)  ~custom (dark)  6.5%  posisi: accent/panel
```

Region label: `background`, `header/navbar`, `footer`, `sidebar`, `panel/card`, `accent/button/text`, `band`. Nilai hex sudah siap tempel ke CSS/Tailwind. Warna tanpa nama umum (Tailwind dll) dilabel `~custom` — pakai hex/rgb-nya.

> **Flow copas web:** gambar di-paste di chat → `extract-pasted-image.py` → `read_colors(...)` → dapat hex → edit warna.

---

## 🎯 Kenapa ini penting?

Banyak LLM yang **murah/cepat hanya teks-only** — mereka menolak gambar (`Cannot read image / model does not support image input`). Padahal pengguna sering paste **screenshot error, stack trace, scan dokumen, proposal PDF**.

Skill ini menjembatani: **file → OCR → teks → LLM**, tanpa perlu model vision yang mahal.

---

## 🚀 Cara Setup

### 1. Install dependensi

```bash
cd mcp-ocr
# pakai uv (disarankan)
uv sync

# atau pakai pip langsung
pip install -r pyproject.toml
```

Butuh **Python 3.10 – 3.13**. Dependensi utama:
`mcp`, `rapidocr-onnxruntime`, `Pillow`, `numpy`, `pypdfium2`, `python-docx`, `openpyxl`, `python-pptx`, `striprtf`.

> Model OCR RapidOCR (ONNX) di-download **otomatis saat pertama kali dipakai**.

### 2. Daftarkan sebagai MCP server

Tambahkan ke config MCP klien kamu (opencode, Claude Code, dst):

```json
{
  "mcpServers": {
    "ocr": {
      "command": "python",
      "args": ["/path/ke/server.py"],
      "env": { "PYTHONIOENCODING": "utf-8" }
    }
  }
}
```

### 3. Selftest (tanpa MCP)

```bash
python server.py --selftest                    # buat sample gambar lalu OCR
python server.py --selftest "folder/file"      # test file atau folder
```

---

## 📖 Cara Pakai

Panggil tool dari LLM:

```
read_document(file_path="C:/Users/.../test-failed-1.png")
read_document(file_path="proposal.pdf")
read_document(file_path="laporan-bug.docx", mode="text", enhance=true)
```

| Param | Nilai | Fungsi |
|---|---|---|
| `file_path` | path lokal / URL http(s) / file:// | wajib |
| `mode` | `auto` \| `text` \| `code` | urutan baris OCR (`code` terbaik utk stack trace) |
| `enhance` | `true` (default) | autocontrast + upscale teks kecil |

Hasilnya teks murni + metadata singkat, contoh:

```
[OCR] pasted-XXXX.png — 1658x605px — 21 baris — avg confidence 0.98 — 18.5s
----------------------------------------------------
Models
# Model Provider Source Input Output ...
1 cx/gpt-5.5 9router Codex 16.5M 685K ...
...
```

---

## 🔗 Bonus: Baca gambar yang DI-PASTE langsung di chat

Ada satu masalah unik di **opencode**: gambar yang di-paste di kolom chat **tidak disimpan sebagai file** — opencode menyimpannya di database SQLite (`opencode.db`, tabel `part`) sebagai base64 data-URL. Model teks-only tidak bisa melihat bytes-nya.

Helper `extract-pasted-image.py` menjembatani ini:

```
User paste gambar di chat
        │
        ▼
[extract-pasted-image.py]  ──►  ambil gambar terbaru dari opencode.db
        │                          (base64 → file temp)
        ▼
[read_document]  ──►  OCR  ──►  teks  ──►  LLM jawab
```

### Pakai

```bash
python extract-pasted-image.py
# → {"paths": ["C:/.../pasted-XXXX.png"], "count": 1}
```

Lalu OCR hasilnya:
```
read_document(file_path="C:/.../pasted-XXXX.png")
```

Opsi:
| Flag | Fungsi |
|---|---|
| `--n <N>` | ekstrak N gambar terakhir (default 1) |
| `--session <id>` | filter session tertentu |
| `--outdir <dir>` | folder output (default temp) |
| `--db <path>` | lokasi `opencode.db` (auto-detect) |

> Butuh Python + stdlib saja (sqlite3, base64, json). Lokasi DB auto-detect dari `~/.local/share/opencode/` lalu `~/.config/opencode/`.

### Alur kerja agent (otomatis)

1. User paste gambar → model dapat error `Cannot read image`.
2. Agent jalankan `extract-pasted-image.py` → ambil file temp.
3. Agent panggil `read_document(file_path=<hasil>)` → teks.
4. Agent analisa & jawab. **Tanpa minta user simpan manual.**

---

## 🧩 Struktur Project

```
Super-MCP-OCR-Deepseek/
├── README.md                      ← dokumentasi ini
├── SKILL.md                       ← skill instruction (untuk agent)
├── server.py                      ← MCP OCR server (inti + read_colors)
├── extract-pasted-image.py        ← helper gambar tempelan opencode
├── pyproject.toml                 ← dependensi
└── .python-version                ← versi Python
```

---

## 🧠 Alur Kerja Teknis (server.py)

1. **`_resolve_path`** — terima path lokal / URL http(s) / file:// → file lokal.
2. **Routing per ekstensi** — gambar → OCR; pdf → ekstrak+OCR; office → ekstrak; teks → baca.
3. **`_ocr_pil`** (gambar) — pre-process (grayscale + autocontrast + upscale teks kecil) → RapidOCR ONNX → susun hasil jadi baris visual (urut `y` lalu `x`).
4. **`_extract_palette` / `_read_colors`** (gambar) — flatten RGBA→RGB → downscale → kuantisasi median-cut (PIL) → cluster warna dominan → gabung shade dekat → hitung % area + region.
5. **Confidence filter** — buang hasil OCR dengan skor < 0.35.
6. **Output** — header metadata + teks murni, siap dianalisa LLM.

### Kenapa preprocessing?

- Teks kecil (< 900px) di-**upscale** 2–3× agar OCR akurat.
- Gambar raksasa (> 3200px) di-**cap** agar tidak boros memory.
- **Autocontrast** meningkatkan kontras teks di screenshot gelap/terang.

---

## 🔧 Troubleshooting

| Masalah | Solusi |
|---|---|
| `API Error 500 max instances` / `401 Insufficient balance` | Masalah **kuota gateway model**, bukan MCP OCR. Top up saldo, lalu ulangi. |
| Tool tidak muncul di klien | Restart sesi / `mcp` reconnect. Cek `claude mcp get ocr` → harus `Connected`. |
| OCR hasil jelek | Pakai `mode="code"` untuk stack trace; cek file dinaikkan resolusi. |
| `.doc`/`.xls` tidak terbaca | Simpan ulang sebagai `.docx`/`.xlsx`. |

---

## 📄 Lisensi

MIT — bebas dipakai, diubah, disebarluaskan.

Dibuat untuk mengaktifkan DeepSeek & LLM teks-only lainnya di ekosistem MCP (opencode, Claude Code, dll).
