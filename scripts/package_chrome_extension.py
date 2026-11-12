#!/usr/bin/env python3
"""Build the installable Chrome extension zip: dist/mongodb-expertise-chrome-<version>.zip.

Steps: export the committed corpus and its search index into invocation-owned scratch storage (``mdbx export-web``:
chunks, BM25 postings, and int8 vectors when the local index has embeddings), then zip the runtime files
(manifest, popup, app, background worker, lib/, icons/, data/). Tests, package.json, the README and
screenshots stay out. Fails if manifest.json and package.json versions differ.

    python scripts/package_chrome_extension.py                 # full build (search data + vectors if indexed)
    python scripts/package_chrome_extension.py --no-vectors    # keyword search only (smaller)
    python scripts/package_chrome_extension.py --no-data       # code only, reuse nothing (search disabled)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maintenance_safety import atomic_write, lock, safe_bytes

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "editors" / "chrome"
DATA = EXT / "data"
RUNTIME = ["manifest.json", "background.js", "popup.html", "popup.css", "popup.js", "app.html", "app.css", "app.js"]
RUNTIME_DIRS = {"lib": {".js"}, "icons": {".png"}, "data": {".json", ".bin"}}


def build_data(vectors: bool, out: Path | None = None):
    sys.path.insert(0, str(ROOT))
    from mdbx import index as idx
    from mdbx.webexport import export

    r = export(idx.default_corpus(), out or DATA, db=idx.default_db(), vectors=vectors)
    note = f"; skipped {r.skipped_untracked} untracked (private) files" if r.skipped_untracked else ""
    print(f"search data: {r.chunks} chunks from {r.files} files, {r.terms} terms, {r.vectors} vectors{note}")
    if vectors and not r.vectors:
        print("note: no embeddings found in the local index; keyword search only")
    return r


def git_commit() -> str:
    """Short SHA of HEAD, or "unknown" outside a git checkout."""
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short=12", "HEAD"], capture_output=True,
                             text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip() or "unknown"


def write_build_stamp(version: str, *, data: bool, vectors: bool, out: Path | None = None) -> dict:
    """data/build.json: what the extension's self-reload check compares (see lib/autoupdate.js)."""
    directory = out or DATA
    directory.mkdir(parents=True, exist_ok=True)
    stamp = {"version": version, "commit": git_commit(),
             "built_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "search_data": data, "vectors": vectors}
    (directory / "build.json").write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return stamp


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-vectors", action="store_true", help="omit embeddings (keyword search only)")
    ap.add_argument("--no-data", action="store_true", help="package without search data")
    a = ap.parse_args()
    try:
        if EXT.is_symlink(): raise ValueError("extension directory is a symlink")
        manifest = json.loads(safe_bytes(EXT / "manifest.json", EXT))
        pkg = json.loads(safe_bytes(EXT / "package.json", EXT))
        version = manifest["version"]
        if not isinstance(version, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,4})(?:\.(?:0|[1-9][0-9]{0,4})){0,3}", version) or any(int(n) > 65535 for n in version.split(".")):
            raise ValueError("invalid extension version")
        if pkg.get("version") != version: raise ValueError("manifest and package versions differ")
        out = ROOT / "dist" / f"mongodb-expertise-chrome-{version}.zip"
        out.parent.mkdir(exist_ok=True)
        if out.parent.is_symlink(): raise ValueError("dist directory is a symlink")
        with lock(out.parent / ".chrome-package.lock"), tempfile.TemporaryDirectory(prefix="mdbx-package-") as scratch:
            scratch = Path(scratch); exported = scratch / "data"; exported.mkdir()
            result = None if a.no_data else build_data(vectors=not a.no_vectors, out=exported)
            stamp = write_build_stamp(version, data=not a.no_data, vectors=bool(result and result.vectors), out=exported)
            files = {name: safe_bytes(EXT / name, EXT) for name in RUNTIME}
            for name, suffixes in RUNTIME_DIRS.items():
                directory = exported if name == "data" else EXT / name
                if directory.is_symlink(): raise ValueError("runtime input directory is a symlink")
                if not directory.exists(): continue
                for entry in sorted(directory.iterdir()):
                    if entry.suffix not in suffixes: continue
                    files[name + "/" + entry.name] = safe_bytes(entry, exported if name == "data" else EXT)
            temporary = scratch / "extension.zip"
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, content in files.items():
                    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o644 << 16
                    archive.writestr(info, content)
            atomic_write(out, temporary.read_bytes())
            atomic_write(out.parent / "build.json", json.dumps(stamp, indent=2).encode() + b"\n")
        print(f"wrote {out.relative_to(ROOT)} ({len(files)} files)")
        return 0
    except (OSError, ValueError, RuntimeError, KeyError):
        print("error: extension package build failed; previous outputs preserved until publication", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
