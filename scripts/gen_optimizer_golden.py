#!/usr/bin/env python3
"""Write golden optimizer output for every input in tests/fixtures/optimizer/.

The Python optimizer is the reference implementation. For each ``<name>.txt`` this writes
``<name>.golden.json`` holding ``to_dict(optimize(text))`` for both ``apply=True`` and ``apply=False``.
The Chrome extension's JavaScript port is tested against these files (editors/chrome/test/), and
tests/test_optimize_golden.py fails when the goldens are stale, so the two implementations cannot drift.

    python scripts/gen_optimizer_golden.py            # regenerate
    python scripts/gen_optimizer_golden.py --check    # exit 1 if any golden is stale
    python scripts/gen_optimizer_golden.py --print    # also print the human-readable reports
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mdbx.mql.optimize import format_report, optimize, to_dict

FIXTURES = ROOT / "tests" / "fixtures" / "optimizer"


def golden(text: str, name: str) -> str:
    applied = optimize(text)
    data = {"apply": to_dict(applied), "read_only": to_dict(optimize(text, apply=False)),
            "report": format_report(applied, name)}
    return (json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8", "backslashreplace").decode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="." + path.name + ".", delete=False) as stream:
            name = stream.name
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        name = None
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--print", action="store_true", dest="show")
    a = ap.parse_args()
    if not FIXTURES.is_dir() or not list(FIXTURES.glob("*.txt")):
        print("missing or empty optimizer fixtures")
        return 1
    stale = []
    for src in sorted(FIXTURES.glob("*.txt")):
        text = src.read_text(encoding="utf-8")
        out = src.with_suffix(".golden.json")
        want = golden(text, src.name)
        if a.show:
            print(f"=========== {src.name.encode('unicode_escape').decode('ascii')}\n{format_report(optimize(text), src.name)}\n")
        if a.check:
            if not out.is_file() or out.read_text(encoding="utf-8") != want:
                stale.append(out.name)
        else:
            _atomic_write(out, want.encode("utf-8"))
    if a.check and stale:
        print("stale goldens (run scripts/gen_optimizer_golden.py):", ", ".join(name.encode("unicode_escape").decode("ascii") for name in stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
