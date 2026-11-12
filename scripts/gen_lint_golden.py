#!/usr/bin/env python3
"""Write golden lint output for every analyzer input.

The Python analyzer (mdbx/mql/analyze.py) is the reference implementation. For each input this writes
a ``<name>.lint.json`` under tests/fixtures/lint/ holding the diagnostics exactly as ``analyze()``
returns them (start, end, line, column, severity, code, message, fix) plus the nested symbol outline.
The Chrome extension's JavaScript port (editors/chrome/lib/analyze.js) is tested against these files
by editors/chrome/test/lint-parity.test.mjs, and tests/test_js_lint_parity.py fails when they are
stale, so the two implementations cannot drift.

Inputs:
  tests/fixtures/lint/<name>.txt       -> tests/fixtures/lint/<name>.lint.json
  tests/fixtures/optimizer/<name>.txt  -> tests/fixtures/lint/optimizer-<name>.lint.json

    python scripts/gen_lint_golden.py            # regenerate
    python scripts/gen_lint_golden.py --check    # exit 1 if any golden is stale or orphaned
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from array import array
from bisect import bisect_left, bisect_right
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mdbx.mql.analyze import Symbol, analyze

LINT = ROOT / "tests" / "fixtures" / "lint"
OPTIMIZER = ROOT / "tests" / "fixtures" / "optimizer"


@lru_cache(maxsize=1)
def _positions(text: str):
    starts, ends, astral = array("Q", [0]), array("Q"), array("Q")
    i = 0
    while i < len(text):
        if ord(text[i]) > 0xFFFF:
            astral.append(i)
        if text[i] in "\r\n":
            ends.append(i)
            if text[i:i + 2] == "\r\n":
                i += 1
            starts.append(i + 1)
        i += 1
    ends.append(len(text))
    return starts, ends, astral


def position(text: str, offset: int) -> tuple[int, int]:
    """0-based line and UTF-16 column, preserving CRLF and lone surrogates."""
    starts, ends, astral = _positions(text)
    offset = max(0, min(offset, len(text)))
    line = bisect_right(starts, offset) - 1
    end = min(offset, ends[line])
    return line, end - starts[line] + bisect_left(astral, end) - bisect_left(astral, starts[line])


def symbol_dict(s: Symbol) -> dict:
    return {"name": s.name, "kind": s.kind, "start": s.start, "end": s.end,
            "children": [symbol_dict(c) for c in s.children]}


def lint_dict(text: str) -> dict:
    """The comparable summary of ``analyze(text)``; the JS port must reproduce it exactly."""
    result = analyze(text)
    diagnostics = []
    for d in result.diagnostics:
        line, column = position(text, d.start)
        diagnostics.append({"start": d.start, "end": d.end, "line": line, "column": column,
                            "severity": d.severity, "code": d.code, "message": d.message, "fix": d.fix})
    return {"diagnostics": diagnostics, "symbols": [symbol_dict(s) for s in result.symbols]}


def inputs() -> list[tuple[Path, Path]]:
    """(input .txt, golden .lint.json) pairs."""
    pairs = [(src, LINT / f"{src.stem}.lint.json") for src in sorted(LINT.glob("*.txt"))]
    pairs += [(src, LINT / f"optimizer-{src.stem}.lint.json") for src in sorted(OPTIMIZER.glob("*.txt"))]
    return pairs


def golden(src: Path) -> str:
    data = {"source": src.relative_to(ROOT).as_posix(), **lint_dict(src.read_bytes().decode("utf-8"))}
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
    a = ap.parse_args()
    if not LINT.is_dir() or not OPTIMIZER.is_dir():
        print("missing fixture directory")
        return 1
    pairs = inputs()
    if not pairs or len({out for _, out in pairs}) != len(pairs):
        print("empty or colliding fixture outputs")
        return 1
    wanted = {out for _, out in pairs}
    orphans = sorted(p for p in LINT.glob("*.lint.json") if p not in wanted)
    stale = []
    for src, out in pairs:
        want = golden(src)
        if a.check:
            if not out.is_file() or out.read_text(encoding="utf-8") != want:
                stale.append(out.name)
        else:
            _atomic_write(out, want.encode("utf-8"))
    if a.check and (stale or orphans):
        if stale:
            print("stale goldens (run scripts/gen_lint_golden.py):", ", ".join(stale))
        if orphans:
            print("orphaned goldens (no input):", ", ".join(p.name for p in orphans))
        return 1
    if not a.check:
        for p in orphans:
            p.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
