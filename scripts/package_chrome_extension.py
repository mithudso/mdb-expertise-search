#!/usr/bin/env python3
"""Build the installable Chrome extension zip: dist/mongodb-expertise-chrome-<version>.zip.

Steps: export the committed corpus and its search index into editors/chrome/data/ (``mdbx export-web``:
chunks, BM25 postings, and int8 vectors when the local index has embeddings), then zip the runtime files
(manifest, popup, app, background worker, lib/, icons/, data/). Tests, package.json, the README and
screenshots stay out. Fails if manifest.json and package.json versions differ.

    python scripts/package_chrome_extension.py                 # full build (search data + vectors if indexed)
    python scripts/package_chrome_extension.py --no-vectors    # keyword search only (smaller)
    python scripts/package_chrome_extension.py --no-data       # code only, reuse nothing (search disabled)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "editors" / "chrome"
DATA = EXT / "data"
RUNTIME = ["manifest.json", "background.js", "popup.html", "popup.css", "popup.js", "app.html", "app.css", "app.js"]
RUNTIME_DIRS = {"lib": {".js"}, "icons": {".png"}, "data": {".json", ".bin"}}


def build_data(vectors: bool) -> None:
    sys.path.insert(0, str(ROOT))
    from mdbx import index as idx
    from mdbx.webexport import export

    if DATA.exists():
        shutil.rmtree(DATA)
    r = export(idx.default_corpus(), DATA, db=idx.default_db(), vectors=vectors)
    note = f"; skipped {r.skipped_untracked} untracked (private) files" if r.skipped_untracked else ""
    print(f"search data: {r.chunks} chunks from {r.files} files, {r.terms} terms, {r.vectors} vectors{note}")
    if vectors and not r.vectors:
        print("note: no embeddings found in the local index (run `mdbx index` with Ollama); keyword search only")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-vectors", action="store_true", help="omit embeddings (keyword search only)")
    ap.add_argument("--no-data", action="store_true", help="package without search data")
    a = ap.parse_args()
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    pkg = json.loads((EXT / "package.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    if pkg["version"] != version:
        print(f"error: manifest.json {version} != package.json {pkg['version']}", file=sys.stderr)
        return 1
    if a.no_data:
        if DATA.exists():
            shutil.rmtree(DATA)
    else:
        try:
            build_data(vectors=not a.no_vectors)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    files = [EXT / f for f in RUNTIME]
    for d, suffixes in RUNTIME_DIRS.items():
        if (EXT / d).is_dir():
            files += sorted(p for p in (EXT / d).iterdir() if p.suffix in suffixes)
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        print("error: missing " + ", ".join(missing), file=sys.stderr)
        return 1
    out = ROOT / "dist" / f"mongodb-expertise-chrome-{version}.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            info = zipfile.ZipInfo(f.relative_to(EXT).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))  # reproducible
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, f.read_bytes())
    raw = sum(f.stat().st_size for f in files)
    print(f"wrote {out.relative_to(ROOT)} ({len(files)} files, {raw / 1e6:.1f} MB unpacked, "
          f"{out.stat().st_size / 1e6:.1f} MB zipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
