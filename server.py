"""
MCP OCR Server — memberi "mata" ke LLM teks-only (DeepSeek v4 Flash, dll).

Tool (2 nama, fungsi sama):
    ocr_image(image_path, mode, enhance)     <- alias, kompatibel
    read_document(file_path, mode, enhance)  <- nama penuh

Bisa baca:
  - GAMBAR : png, jpg/jpeg/jfif, webp, bmp, gif, tif/tiff  -> OCR (RapidOCR)
  - PDF    : teks asli diekstrak; halaman scan otomatis di-OCR (pdfium)
  - OFFICE : docx, xlsx/xlsm, pptx, rtf -> ekstrak teks
  - TEXT   : txt, md, csv, json, xml, log, yaml, ini, cfg, toml, html

Jalankan sebagai MCP stdio server:
    python server.py

Selftest (tanpa MCP, dukung file ATAU folder):
    python server.py --selftest <path-file-atau-folder>
"""

import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mcp-ocr")

_engine = None

_IMG_EXTS = {".png", ".jpg", ".jpeg", ".jfif", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
_TEXT_EXTS = {".txt", ".md", ".markdown", ".csv", ".json", ".xml", ".log", ".yaml", ".yml", ".ini", ".cfg", ".env", ".toml", ".html", ".htm"}
_OFFICE_KIND = {".docx": "DOCX", ".xlsx": "XLSX", ".xlsm": "XLSX", ".pptx": "PPTX", ".rtf": "RTF"}
_MAX_TEXT_CHARS = 600_000


def _sanitize(text: str) -> str:
    """Buang noncharacter (U+FFFE/U+FFFF), surrogate, dan control aneh.
    Jaga \n \t \r. Teks PDF kadang berisi U+FFFE yang bisa bikin error encode."""
    out = []
    for ch in text:
        o = ord(ch)
        if ch in "\n\t\r" or (32 <= o != 0xFFFE and o != 0xFFFF and not (0xD800 <= o <= 0xDFFF)):
            out.append(ch)
    return "".join(out)


def _get_engine():
    """Lazy-init RapidOCR (model onnx di-download otomatis saat pertama kali)."""
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def _resolve_path(file_path: str):
    """Terima path lokal atau URL http(s)/file://, return (display_name, local_path)."""
    s = str(file_path).strip()
    if s.startswith(("http://", "https://")):
        fd, tmp = tempfile.mkstemp(suffix=".img")
        os.close(fd)
        try:
            with urllib.request.urlopen(s, timeout=60) as resp, open(tmp, "wb") as fh:
                fh.write(resp.read())
            return (Path(s).name or "remote-file"), Path(tmp)
        except Exception as e:
            Path(tmp).unlink(missing_ok=True)
            raise ValueError(f"Gagal download URL {s}: {e}")
    if s.startswith("file://"):
        s = s[len("file://"):]
        if s.startswith("localhost"):
            s = s[len("localhost"):]
    s = os.path.expanduser(s)
    p = Path(s)
    if not p.is_absolute():
        p = Path.cwd() / p
    if not p.exists():
        raise ValueError(f"File tidak ditemukan: {file_path}")
    return p.name, p


def _preprocess(img: Image.Image, enhance: bool) -> Image.Image:
    """Grayscale + autocontrast + upscale teks kecil / cap gambar raksasa."""
    if img.mode not in ("L", "1"):
        img = img.convert("L")
    if not enhance:
        return img
    img = ImageOps.autocontrast(img)
    w, h = img.size
    scale = 1.0
    m = max(w, h)
    if m < 400:
        scale = 3.0
    elif m < 900:
        scale = 2.0
    if m > 3200:
        scale = min(scale, 3200 / m)
    if scale != 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img


def _sort_into_lines(items):
    """Susun hasil OCR jadi baris visual (urut y, lalu x)."""
    if not items:
        return []
    boxes = [it[0] for it in items]
    ys = [(b[0][1] + b[2][1]) / 2 for b in boxes]
    xs = [min(p[0] for p in b) for b in boxes]
    heights = [max(p[1] for p in b) - min(p[1] for p in b) for b in boxes]
    med_h = sorted(heights)[len(heights) // 2] if heights else 1

    order = sorted(range(len(items)), key=lambda i: ys[i])
    groups = []
    for i in order:
        if groups and ys[i] - ys[groups[-1][-1]] <= med_h * 0.5:
            groups[-1].append(i)
        else:
            groups.append([i])
    lines = []
    for g in groups:
        g_sorted = sorted(g, key=lambda i: xs[i])
        lines.append([items[i] for i in g_sorted])
    return lines


def _ocr_pil(img: Image.Image):
    """OCR satu PIL image -> (body_text, avg_confidence)."""
    img = _preprocess(img, True)
    result, _elapse = _get_engine()(np.array(img))
    if not result:
        return "", 0.0
    items = [(r[0], r[1], float(r[2])) for r in result if float(r[2]) >= 0.35]
    if not items:
        return "", 0.0
    lines = _sort_into_lines(items)
    body = "\n".join(" ".join(it[1] for it in ln) for ln in lines)
    conf = sum(it[2] for it in items) / len(items)
    return body, conf


# ---------- color extraction ----------

_NAMED_COLORS = {
    "black": (0, 0, 0), "white": (255, 255, 255), "gray": (128, 128, 128),
    "lightgray": (211, 211, 211), "darkgray": (169, 169, 169), "dimgray": (105, 105, 105),
    "silver": (192, 192, 192), "slate": (112, 128, 144), "darkslategray": (47, 79, 79),
    "red": (255, 0, 0), "maroon": (128, 0, 0), "darkred": (139, 0, 0),
    "orange": (255, 165, 0), "darkorange": (255, 140, 0), "gold": (255, 215, 0),
    "yellow": (255, 255, 0), "olive": (128, 128, 0), "khaki": (240, 230, 140),
    "green": (0, 128, 0), "lime": (0, 255, 0), "darkgreen": (0, 100, 0),
    "seagreen": (46, 139, 87), "forestgreen": (34, 139, 34), "mediumseagreen": (60, 179, 113),
    "teal": (0, 128, 128), "cyan": (0, 255, 255), "darkcyan": (0, 139, 139),
    "aqua": (0, 255, 255), "blue": (0, 0, 255), "navy": (0, 0, 128),
    "royalblue": (65, 105, 225), "steelblue": (70, 130, 180), "skyblue": (135, 206, 235),
    "lightblue": (173, 216, 230), "darkblue": (0, 0, 139), "mediumblue": (0, 0, 205),
    "purple": (128, 0, 128), "magenta": (255, 0, 255), "fuchsia": (255, 0, 255),
    "violet": (238, 130, 238), "indigo": (75, 0, 130), "mediumpurple": (147, 112, 219),
    "plum": (221, 160, 221), "pink": (255, 192, 203), "hotpink": (255, 105, 180),
    "deeppink": (255, 20, 147), "brown": (165, 42, 42), "chocolate": (210, 105, 30),
    "saddlebrown": (139, 69, 19), "tomato": (255, 99, 71), "coral": (255, 127, 80),
    "salmon": (250, 128, 114), "beige": (245, 245, 220), "cream": (255, 253, 208),
    "ivory": (255, 255, 240), "mint": (245, 255, 250),
}


def _nearest_name(rgb):
    best, bd = "custom", 1e9
    for name, (r, g, b) in _NAMED_COLORS.items():
        d = (r - rgb[0]) ** 2 + (g - rgb[1]) ** 2 + (b - rgb[2]) ** 2
        if d < bd:
            bd, best = d, name
    return best if bd < 900 else "custom"


def _flatten_rgb(img: Image.Image) -> Image.Image:
    """Transparency/alpha → komposit di atas putih, balikin RGB."""
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "RGBA":
            bg.paste(img, mask=img.split()[3])
        else:
            bg.paste(img.convert("RGBA"), mask=img.split()[1])
        return bg
    return img.convert("RGB")


def _region_label(w, h, x0, y0, x1, y1, coverage):
    bw, bh = x1 - x0, y1 - y0
    if coverage > 0.35:
        return "background"
    if bh <= h * 0.21 and bw > w * 0.6:
        return "header/navbar" if y0 < h * 0.15 else ("footer" if y1 > h * 0.85 else "band")
    if bw < w * 0.25 and bh > h * 0.5:
        return "sidebar"
    if bw > w * 0.5 and bh > h * 0.4:
        return "panel/card"
    if coverage < 0.03:
        return "accent/button/text"
    return "accent/panel"


def _extract_palette(img, top_n, merge=True):
    w, h = img.size
    m = max(w, h)
    if m > 640:
        img = img.resize((int(w * 640 / m), int(h * 640 / m)), Image.LANCZOS)
    w, h = img.size
    n_colors = min(256, max(top_n * 6, 64))
    q = img.quantize(colors=n_colors, method=Image.MEDIANCUT)
    pal = q.getpalette()
    arr = np.asarray(q)
    idxs, counts = np.unique(arr, return_counts=True)
    total = arr.size
    entries = []
    for i, c in zip(idxs, counts):
        entries.append({"rgb": [pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]], "count": int(c), "idx": int(i)})
    entries.sort(key=lambda e: -e["count"])
    if not merge:
        return entries[:top_n], arr, w, h, total
    merged = []
    for e in entries:
        placed = False
        for me in merged:
            r, g, b = me["rgb"]
            dist = ((r - e["rgb"][0]) ** 2 + (g - e["rgb"][1]) ** 2 + (b - e["rgb"][2]) ** 2) ** 0.5
            small = me["count"] / total < 0.02 or e["count"] / total < 0.02
            if dist < 30 and (dist < 12 or small):
                n = me["count"]
                me["rgb"] = [int((r * n + e["rgb"][0] * e["count"]) / (n + e["count"])) for _ in range(3)]
                me["count"] = n + e["count"]
                me["idx"] = me["idx"] + [e["idx"]]
                placed = True
                break
        if not placed:
            e["idx"] = [e["idx"]]
            merged.append(e)
    merged.sort(key=lambda me: -me["count"])
    return merged[:top_n], arr, w, h, total


def _read_colors(name, path, top_n=8, merge=True) -> str:
    t0 = time.time()
    img = Image.open(path)
    ow, oh = img.size
    img = _flatten_rgb(img)
    palette, arr, w, h, total = _extract_palette(img, top_n, merge)
    lines = []
    for rank, e in enumerate(palette, 1):
        r, g, b = e["rgb"]
        hexs = "#%02X%02X%02X" % (r, g, b)
        pct = 100.0 * e["count"] / total
        ys, xs = np.where(np.isin(arr, e["idx"]))
        if len(ys):
            x0, y0, x1, y1 = xs.min(), ys.min(), xs.max(), ys.max()
            region = _region_label(w, h, int(x0), int(y0), int(x1), int(y1), e["count"] / total)
        else:
            region = "unknown"
        shade = "light" if (0.299 * r + 0.587 * g + 0.114 * b) > 160 else "dark"
        lines.append(
            f"{rank}. {hexs}  rgb({r}, {g}, {b})  ~{_nearest_name(e['rgb'])} ({shade})  "
            f"{pct:.1f}%  posisi: {region}"
        )
    header = (
        f"[COLORS] {name} — {ow}x{oh}px — top {len(palette)} warna dominan "
        f"(quantized {w}x{h}) — {time.time() - t0:.1f}s\n" + "-" * 52
    )
    return header + "\n" + "\n".join(lines)


# ---------- reader per format ----------

def _read_image(name, path) -> str:
    t0 = time.time()
    img = Image.open(path)
    w, h = img.size
    body, conf = _ocr_pil(img)
    if not body:
        return f"[OCR] {name} ({w}x{h}px): tidak ada teks terdeteksi."
    header = (
        f"[OCR] {name} — {w}x{h}px — {len(body.splitlines())} baris — "
        f"avg confidence {conf:.2f} — {time.time() - t0:.1f}s\n" + "-" * 52
    )
    return header + "\n" + body


def _read_text_file(path) -> str:
    raw = path.read_bytes()[:_MAX_TEXT_CHARS * 2]
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return _sanitize(raw.decode(enc))
        except (UnicodeDecodeError, UnicodeError):
            continue
    return _sanitize(raw.decode("utf-8", errors="replace"))


def _read_pdf(path) -> str:
    import pypdfium2 as pdfium
    t0 = time.time()
    pdf = pdfium.PdfDocument(str(path))
    n = len(pdf)
    max_pages = 25
    parts, ocr_pages = [], 0
    for i in range(min(n, max_pages)):
        page = pdf[i]
        try:
            tp = page.get_textpage()
            txt = _sanitize(tp.get_text_range() or "").strip()
        except Exception:
            txt = ""
        if txt:
            parts.append(f"--- Halaman {i + 1} ---\n{txt}")
        else:
            bitmap = page.render(scale=2.0)
            body, _conf = _ocr_pil(bitmap.to_pil())
            ocr_pages += 1
            parts.append(f"--- Halaman {i + 1} (OCR) ---\n" + (body or "(halaman kosong/tanpa teks)"))
    header = (
        f"[PDF] {path.name} — {n} halaman ({ocr_pages} hal scan di-OCR) — "
        f"{time.time() - t0:.1f}s\n" + "-" * 52
    )
    return header + "\n\n".join(parts)


def _read_docx(path) -> str:
    from docx import Document
    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    for i, table in enumerate(doc.tables, 1):
        rows = []
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            parts.append(f"[Tabel {i}]\n" + "\n".join(rows))
    return "\n".join(parts)


def _read_xlsx(path) -> str:
    from openpyxl import load_workbook
    wb = load_workbook(str(path), read_only=True, data_only=True)
    parts = []
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = ["" if v is None else str(v) for v in row]
            if any(c.strip() for c in cells):
                rows.append("\t".join(cells))
        if rows:
            parts.append(f"[Sheet: {ws.title}]\n" + "\n".join(rows))
    wb.close()
    return "\n".join(parts)


def _read_pptx(path) -> str:
    from pptx import Presentation
    prs = Presentation(str(path))
    parts = []
    for i, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                texts.append(shape.text_frame.text.strip())
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if any(cells):
                        texts.append(" | ".join(cells))
        if texts:
            parts.append(f"[Slide {i}]\n" + "\n".join(texts))
    return "\n".join(parts)


def _read_rtf(path) -> str:
    from striprtf.striprtf import rtf_to_text
    return rtf_to_text(path.read_text("cp1252", errors="replace"))


def _read_any(file_path: str, _mode: str = "auto", _enhance: bool = True) -> str:
    name, path = _resolve_path(file_path)
    ext = path.suffix.lower()
    if ext in _IMG_EXTS:
        return _read_image(name, path)
    if ext == ".pdf":
        return _read_pdf(path)
    if ext in _TEXT_EXTS:
        text = _read_text_file(path)
        return f"[TEXT] {name} — {len(text)} karakter\n" + "-" * 52 + "\n" + text[:_MAX_TEXT_CHARS]
    kind = _OFFICE_KIND.get(ext)
    if kind == "DOCX":
        body = _read_docx(path)
    elif kind == "XLSX":
        body = _read_xlsx(path)
    elif kind == "PPTX":
        body = _read_pptx(path)
    elif kind == "RTF":
        body = _read_rtf(path)
    else:
        raise ValueError(
            f"Format tidak didukung: {ext or '(tanpa ekstensi)'}. "
            "Didukung: gambar (png/jpg/webp/bmp/gif/tiff), pdf, docx, xlsx/xlsm, pptx, "
            "rtf, txt/md/csv/json/xml/log/yaml/toml/html. "
            "Untuk .doc/.xls versi lama: simpan ulang sebagai .docx/.xlsx dulu."
        )
    body = _sanitize(body)
    if not body or not body.strip():
        return f"[{kind}] {name}: tidak ada teks ditemukan (file kosong atau isinya murni gambar)."
    return f"[{kind}] {name}\n" + "-" * 52 + "\n" + body[:_MAX_TEXT_CHARS]


# ---------- MCP tools ----------

@mcp.tool()
def read_document(file_path: str, mode: str = "auto", enhance: bool = True) -> str:
    """Baca SEMUA teks dari gambar ATAU dokumen, lalu kembalikan sebagai teks murni.

    Ini memberi 'mata' ke model yang TIDAK punya vision (mis. DeepSeek v4 Flash):
    hasilnya teks yang bisa langsung dianalisa / dipakai untuk fix bug.

    Format didukung:
      - Gambar: png, jpg/jpeg, webp, bmp, gif, tif/tiff (OCR otomatis — cocok untuk
        screenshot error, stack trace, scan dokumen, diagram, foto).
      - PDF: teks asli diekstrak; halaman scan di-OCR otomatis per halaman.
      - Office: docx, xlsx/xlsm, pptx, rtf (ekstrak paragraf, tabel, slide).
      - Teks: txt, md, csv, json, xml, log, yaml, toml, html.

    Args:
        file_path: Path file lokal (absolut/relatif ke working dir) atau URL http(s)/file://.
        mode: "auto" | "text" | "code" — pengaruh utama ke urutan baris hasil OCR.
        enhance: Pre-process gambar (autocontrast + upscale teks kecil). Default True.

    Returns:
        Teks hasil baca + metadata singkat. Error jelas kalau format tidak didukung.
    """
    return _read_any(file_path, mode, enhance)


@mcp.tool()
def ocr_image(image_path: str, mode: str = "auto", enhance: bool = True) -> str:
    """Baca teks dari gambar atau dokumen. Sama persis dengan read_document
    (nama ini dipertahankan agar kompatibel). Lihat read_document untuk detail."""
    return _read_any(image_path, mode, enhance)


@mcp.tool()
def read_colors(file_path: str, top_n: int = 8, merge: bool = True) -> str:
    """Ekstrak WARNA DOMINAN dari gambar dan kembalikan sebagai teks berstruktur.

    Untuk model teks-only (DeepSeek v4 Flash dll) biar bisa 'melihat' warna:
    misal screenshot/`copas` halaman web lalu mau edit warna — tool ini terjemahkan
    tiap warna jadi hex + rgb + nama + posisi region (background, header, sidebar,
    accent/button, dll) yang bisa langsung dipakai di CSS/Tailwind.

    Algoritma: kuantisasi median-cut (PIL) di gambar yang di-downscale → cluster
    warna dominan, gabung shade nyaris-duplikat, hitung persentase area + lokasi.

    Args:
        file_path: Path gambar lokal atau URL http(s)/file://.
        top_n: Berapa warna teratas (default 8).
        merge: Gabung warna nyaris-sama (< 30 delta). Default True.

    Returns:
        Daftar warna dominan: hex, rgb(), nama, shade light/dark, % area, region.
    """
    name, path = _resolve_path(file_path)
    if path.suffix.lower() not in _IMG_EXTS:
        raise ValueError(f"read_colors hanya untuk gambar, bukan: {path.suffix}")
    return _read_colors(name, path, top_n, merge)


# ---------- selftest ----------

def _selftest(target: str | None = None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("== MCP-OCR selftest ==")
    if target and (Path(target).is_dir()):
        files = sorted(Path(target).iterdir())
        ok, fail = 0, 0
        for f in files:
            if not f.is_file():
                continue
            try:
                out = _read_any(str(f))
                print(f"\n>>> {f.name} — OK ({len(out)} chars)")
                print("\n".join(out.splitlines()[:12]))
                ok += 1
                if f.suffix.lower() in _IMG_EXTS:
                    try:
                        print("\n" + _read_colors(f.name, f, top_n=6))
                    except Exception as ce:
                        print(f"--- colors GAGAL: {ce}")
            except Exception as e:
                print(f"\n>>> {f.name} — GAGAL: {e}")
                fail += 1
        print(f"\n== MATRIX DONE: {ok} OK, {fail} GAGAL ==")
        return
    if target is None:
        from PIL import ImageDraw, ImageFont
        font = ImageFont.load_default()
        for cand in ("C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"):
            if os.path.exists(cand):
                font = ImageFont.truetype(cand, 30)
                break
        img = Image.new("L", (1150, 400), 255)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 1150, 48], fill=25)
        d.text((18, 10), "TEST ERROR SCREENSHOT - JANGAN DIHAPUS", fill=255, font=font)
        y = 78
        for ln in [
            "TypeError: Cannot read properties of undefined (reading 'map')",
            "   at renderUserList (src/components/UserList.jsx:42:17)",
            "npm ERR! code ELIFECYCLE",
        ]:
            d.text((18, y), ln, fill=18, font=font)
            y += 62
        target = os.path.join(tempfile.gettempdir(), "mcp-ocr-selftest.png")
        img.save(target)
        print("sample image dibuat:", target)
    out = _read_any(target)
    print(out)
    print("\n--- warna dominan ---")
    print(_read_colors(target, target, top_n=6))
    print("\n== DONE ==")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _t = None
        if len(sys.argv) > 2 and not sys.argv[2].startswith("-"):
            _t = sys.argv[2]
        _selftest(_t)
    else:
        mcp.run()
