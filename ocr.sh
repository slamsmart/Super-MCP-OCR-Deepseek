#!/usr/bin/env bash
# ocr — extract text from images and PDFs, offline, without any Python env.
#
# Companion to the MCP OCR server (server.py) for machines where installing
# Python deps (RapidOCR/onnxruntime) is awkward — e.g. CI runners, plain
# Linux servers, instabox/Hermes sandboxes.
#
# Install (Debian/Ubuntu):
#   sudo apt-get install -y tesseract-ocr tesseract-ocr-ind tesseract-ocr-eng poppler-utils
#   install -m 0755 ocr.sh /usr/local/bin/ocr        # or ~/.local/bin/ocr
#
# Usage:
#   ocr photo.png                 # text to stdout (default languages: ind+eng)
#   ocr scan.pdf report.docx-ish  # PDF: native text layer, else 300dpi OCR per page
#   OCR_LANG=eng ocr chart.jpg    # override languages
#   ocr a.png b.pdf c.jpg         # several files at once
#
set -uo pipefail

lang="${OCR_LANG:-ind+eng}"
dpi="${OCR_DPI:-300}"

if [ $# -eq 0 ]; then
  echo "usage: ocr <file.png|file.jpg|file.pdf|...> [more files]" >&2
  exit 2
fi

if ! command -v tesseract >/dev/null 2>&1; then
  echo "ocr: tesseract not found — install it first:" >&2
  echo "  sudo apt-get install -y tesseract-ocr tesseract-ocr-ind poppler-utils" >&2
  exit 3
fi

for f in "$@"; do
  if [ ! -f "$f" ]; then
    echo "ocr: no such file: $f" >&2
    continue
  fi
  case "${f##*.}" in
    png|PNG|jpg|JPG|jpeg|JPEG|webp|WEBP|tif|TIF|tiff|TIFF|bmp|BMP|gif|GIF)
      tesseract "$f" stdout -l "$lang" 2>/dev/null
      ;;
    pdf|PDF)
      # a digital PDF has a text layer: read it directly (fast, exact)
      text="$(pdftotext -layout "$f" - 2>/dev/null || true)"
      if printf '%s' "$text" | grep -q '[[:alnum:]]'; then
        printf '%s\n' "$text"
      else
        # scanned/image-only PDF: rasterise, then OCR page by page
        tmp="$(mktemp -d)"
        pdftoppm -r "$dpi" -png "$f" "$tmp/page" 2>/dev/null
        for page in "$tmp"/page-*.png; do
          [ -e "$page" ] || continue
          echo "----- ${f} :: $(basename "$page") -----"
          tesseract "$page" stdout -l "$lang" 2>/dev/null
        done
        rm -rf "$tmp"
      fi
      ;;
    *)
      # unknown extension: let tesseract try (it reads many raster formats)
      tesseract "$f" stdout -l "$lang" 2>/dev/null \
        || echo "ocr: unsupported file type: $f" >&2
      ;;
  esac
done
