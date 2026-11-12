#!/usr/bin/env python3
"""Fail if committed-corpus files contain customer or internal-tooling markers.

Built-in markers cover internal hosts, repos and support-case numbers. Add customer names to a
denylist file OUTSIDE this repo (one regex per line): $MDBX_DENYLIST or ~/.config/mdbx/denylist.txt.
Checks tracked and non-ignored untracked files under corpus/. Ignored private files are excluded.
All selected files must be readable UTF-8 text; unsupported or symlink entries fail the gate.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maintenance_safety import safe_bytes

ROOT = Path(__file__).resolve().parent.parent
BUILTIN = [
    r"corp\.mongodb\.com",
    r"10gen",
    r"mdb-tam",
    r"case-assistant",
    r"[Cc]ase[ #:-]*0\d{7}\b",
    r"\bARR\b",
    r"HELP-\d+",
    r"/Users/[A-Za-z0-9._-]+",
    r"~/\.claude",
    r"Premium Services",
    r"ts-?diag",
    r"skill-to-llms-txt",
    r"\bTAMs?\b",
]


def load_patterns() -> list[re.Pattern]:
    pats = list(BUILTIN)
    path = Path(os.environ.get("MDBX_DENYLIST", Path.home() / ".config/mdbx/denylist.txt"))
    if path.is_file():
        pats += [ln.strip() for ln in path.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    else:
        print(f"note: no denylist at {path}; only built-in markers checked", file=sys.stderr)
    compiled = []
    for number, p in enumerate(pats, 1):
        try:
            compiled.append(re.compile(p, re.IGNORECASE if p not in BUILTIN else 0))
        except re.error:
            sys.exit(f"error: invalid denylist rule {number}")
    return compiled


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0]); ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    corpus = ROOT / "corpus"
    if corpus.is_symlink() or not corpus.resolve().is_relative_to(ROOT.resolve()):
        print("error: corpus scan root is outside the repository", file=sys.stderr); return 2
    files = []
    for extra in ([], ["-o", "--exclude-standard"]):
        result = subprocess.run(["git", "ls-files", "-z", *extra, "--", "corpus"], cwd=ROOT, capture_output=True, text=True, check=True)
        files.extend(x for x in result.stdout.split("\0") if x)
    pats = load_patterns(); hits = []; errors = []; scanned = 0
    for rel in sorted(set(files)):
        p = ROOT / rel
        try:
            text = safe_bytes(p, ROOT / "corpus").decode("utf-8")
        except (OSError, ValueError, UnicodeError):
            errors.append(rel); continue
        scanned += 1
        for number, line in enumerate(text.splitlines(), 1):
            for rule, pat in enumerate(pats, 1):
                if pat.search(line): hits.append({"path": rel, "line": number, "rule": rule})
    status = "error" if errors or not scanned else "markers" if hits else "clean"
    if args.json:
        print(json.dumps({"status": status, "files": sorted({hit["path"] for hit in hits}), "hits": hits, "errors": errors, "scanned": scanned}))
    else:
        for hit in hits: print(f"{json.dumps(hit['path'])}:{hit['line']}: rule-{hit['rule']}")
        print(f"{len(hits)} marker hit(s) in {scanned} file(s)")
        if errors: print(f"error: {len(errors)} unreadable, unsupported or symlink input(s)", file=sys.stderr)
        if not scanned: print("error: no corpus files scanned", file=sys.stderr)
    return 2 if status == "error" else 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
