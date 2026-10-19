#!/usr/bin/env python3
"""Build the installable Chrome extension zip: dist/mql-optimizer-chrome-<version>.zip.

Only runtime files go in (manifest, popup, background worker, lib/, icons/); tests, package.json,
the README and screenshots stay out. Fails if manifest.json and package.json versions differ.
The zip is what you upload to the Chrome Web Store, or unzip and "Load unpacked".

    python scripts/package_chrome_extension.py
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "editors" / "chrome"
RUNTIME = ["manifest.json", "background.js", "popup.html", "popup.css", "popup.js"]
RUNTIME_DIRS = {"lib": ".js", "icons": ".png"}


def main() -> int:
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    pkg = json.loads((EXT / "package.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    if pkg["version"] != version:
        print(f"error: manifest.json {version} != package.json {pkg['version']}", file=sys.stderr)
        return 1
    files = [EXT / f for f in RUNTIME]
    for d, suffix in RUNTIME_DIRS.items():
        files += sorted(p for p in (EXT / d).iterdir() if p.suffix == suffix)
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        print("error: missing " + ", ".join(missing), file=sys.stderr)
        return 1
    out = ROOT / "dist" / f"mql-optimizer-chrome-{version}.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            info = zipfile.ZipInfo(str(f.relative_to(EXT)), date_time=(2026, 1, 1, 0, 0, 0))  # reproducible
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, f.read_bytes())
    print(f"wrote {out.relative_to(ROOT)} ({len(files)} files, {out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
