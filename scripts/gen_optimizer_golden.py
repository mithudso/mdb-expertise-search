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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mdbx.mql.optimize import format_report, optimize, to_dict

FIXTURES = ROOT / "tests" / "fixtures" / "optimizer"


def golden(text: str, name: str) -> str:
    data = {"apply": to_dict(optimize(text)), "read_only": to_dict(optimize(text, apply=False)),
            "report": format_report(optimize(text), name)}
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--print", action="store_true", dest="show")
    a = ap.parse_args()
    stale = []
    for src in sorted(FIXTURES.glob("*.txt")):
        text = src.read_text(encoding="utf-8")
        out = src.with_suffix(".golden.json")
        want = golden(text, src.name)
        if a.show:
            print(f"=========== {src.name}\n{format_report(optimize(text), src.name)}\n")
        if a.check:
            if not out.is_file() or out.read_text(encoding="utf-8") != want:
                stale.append(out.name)
        else:
            out.write_text(want, encoding="utf-8")
    if a.check and stale:
        print("stale goldens (run scripts/gen_optimizer_golden.py):", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
