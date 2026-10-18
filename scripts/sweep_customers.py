#!/usr/bin/env python3
"""Fail if committed-corpus files contain customer or internal-tooling markers.

Built-in markers cover internal hosts, repos and support-case numbers. Add customer names to a
denylist file OUTSIDE this repo (one regex per line): $MDBX_DENYLIST or ~/.config/mdbx/denylist.txt.
Checks every non-ignored file under corpus/ (git ls-files), so private local-only files do not trip it.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILTIN = [
    r"corp\.mongodb\.com",
    r"10gen",
    r"mdb-tam",
    r"case-assistant",
    r"[Cc]ase[ #:-]*0\d{7}\b",
    r"\bARR\b",
]


def load_patterns() -> list[re.Pattern]:
    pats = list(BUILTIN)
    path = Path(os.environ.get("MDBX_DENYLIST", Path.home() / ".config/mdbx/denylist.txt"))
    if path.is_file():
        pats += [ln.strip() for ln in path.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    else:
        print(f"note: no denylist at {path}; only built-in markers checked", file=sys.stderr)
    return [re.compile(p, re.IGNORECASE if p not in BUILTIN else 0) for p in pats]


def main() -> int:
    files = subprocess.run(
        ["git", "ls-files", "corpus"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    # Also check files staged-but-untracked by including `git ls-files -o --exclude-standard`.
    files += subprocess.run(
        ["git", "ls-files", "-o", "--exclude-standard", "corpus"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    pats = load_patterns()
    hits = 0
    for rel in sorted(set(files)):
        p = ROOT / rel
        if p.suffix not in {".md", ".txt", ".json", ".jsonl"} or not p.is_file():
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for pat in pats:
                if pat.search(line):
                    print(f"{rel}:{n}: /{pat.pattern}/ {line.strip()[:120]}")
                    hits += 1
    print(f"{hits} marker hit(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
