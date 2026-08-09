#!/usr/bin/env python3
"""Extract the most recently pasted image from opencode's database and write it to disk.

opencode stores images pasted into the chat as `file` parts in its SQLite DB
(`opencode.db`, table `part`, JSON `data` column, base64 data-URL in `url`).
The LLM cannot see these bytes (no vision), but the OCR server CAN read the
image if it is a file on disk. This script bridges that gap.

Usage:
    python extract-pasted-image.py [--db PATH] [--session ID] [--outdir DIR] [--n N]

Defaults:
    --db      ~/.local/share/opencode/opencode.db (falls back to ~/.config/opencode/opencode.db)
    --session any (picks the most recent image overall)
    --outdir  <temp>/opencode-pasted/
    --n       1 (number of most recent images to extract)

Output (JSON on stdout):
    {"paths": ["C:/.../image.png"], "count": 1}
"""
import argparse
import base64
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


def default_db_path():
    candidates = [
        Path.home() / ".local" / "share" / "opencode" / "opencode.db",
        Path.home() / ".config" / "opencode" / "opencode.db",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return str(candidates[0])


def read_db(db_path, session, n):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    params = []
    where = "data LIKE '%\"type\":\"file\"%' AND data LIKE '%data:image%'"
    if session:
        where += " AND session_id = ?"
        params.append(session)
    rows = cur.execute(
        f"SELECT id, message_id, session_id, data FROM part "
        f"WHERE {where} ORDER BY time_created DESC LIMIT {int(n)}",
        params,
    ).fetchall()
    con.close()
    return rows


def extract(row, outdir):
    data = row["data"]
    import json as _json

    try:
        obj = _json.loads(data)
    except Exception:
        return None
    url = obj.get("url", "") if isinstance(obj, dict) else ""
    if not url.startswith("data:"):
        return None
    mime = obj.get("mime", "")
    ext_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/gif": ".gif",
        "image/tiff": ".tiff",
    }
    ext = ext_map.get(mime, ".png")
    if url.startswith("data:") and "," in url:
        b64 = url.split(",", 1)[1]
    else:
        b64 = url
    raw = base64.b64decode(b64)
    fname = Path(outdir) / f"pasted-{row['id'][-12:]}{ext}"
    fname.write_bytes(raw)
    return {"path": str(fname), "mime": mime, "session": row["session_id"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--session", default=None)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--n", type=int, default=1)
    args = ap.parse_args()

    db_path = args.db or default_db_path()
    outdir = args.outdir or str(Path(tempfile.gettempdir()) / "opencode-pasted")
    os.makedirs(outdir, exist_ok=True)

    rows = read_db(db_path, args.session, args.n)
    results = []
    for row in rows:
        r = extract(row, outdir)
        if r:
            results.append(r)

    print(json.dumps({"paths": [r["path"] for r in results], "count": len(results)}))


if __name__ == "__main__":
    main()
