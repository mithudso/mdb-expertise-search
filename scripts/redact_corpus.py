#!/usr/bin/env python3
"""Redact customer and internal-tooling references from the corpus copies, in place.

Idempotent. Run by scripts/sync_corpus.sh after copying. Two rule sets:

* generic rules (this file): local paths, private ticket keys, internal hostnames, generator comments;
* private rules (NOT in the repo): ``$MDBX_REDACTIONS`` or ``~/.config/mdbx/redactions.py`` defining
  ``RULES`` (exact-phrase pairs, may name customers) and optionally ``PATCH`` (path to a unified diff of
  hand edits, applied last with ``patch -p1`` from the repo root).

Files that cannot be redacted are listed in PRIVATE_FILES and in .gitignore; they are never committed.
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"

#: Exact files/dirs that stay local-only because redaction cannot make them safe.
PRIVATE_FILES = [
    "corpus/llms/uber-mongodb-skill.md",
    "corpus/llms/memory-central/",
    "corpus/skills/atlas-diagnostics-expert/SKILL.md",
    "corpus/skills/atlas-diagnostics-expert/references/atlas-diagnostics-package.md",
    "corpus/skills/mongodb-ts-diag-and-diagnostic-workflows/",
    "corpus/llms/ts-diag-and-diagnostic-workflows.llms/",
    "corpus/skills/mongodb-kb-backed-troubleshooting/",
    "corpus/llms/kb-backed-troubleshooting.llms/",
]

#: (pattern, replacement) applied with re.sub to every text file.
GENERIC_REGEX: list[tuple[re.Pattern, str]] = [
    (re.compile(r"/Users/[A-Za-z0-9._-]+/\S*"), "<local-path>"),
    (re.compile(r"~/\.(?:claude|global-ai-hub)/\S*"), "<local-path>"),
    (re.compile(r"\s*\(HELP-\d+\)"), ""),
    (re.compile(r"\bHELP-\d+\b"), "<ticket>"),
    (re.compile(r"\b[\w.-]*\.corp\.mongodb\.com\b"), "internal.example.com"),
    (re.compile(r"^<!--[^\n]*skill-to-llms-txt[^\n]*-->\n", re.MULTILINE), ""),
]


def load_private() -> tuple[list[tuple[str, str]], str | None]:
    path = Path(os.environ.get("MDBX_REDACTIONS", Path.home() / ".config/mdbx/redactions.py"))
    if not path.is_file():
        print(f"note: no private redaction rules at {path}; generic rules only", file=sys.stderr)
        return [], None
    spec = importlib.util.spec_from_file_location("mdbx_private_redactions", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return list(getattr(mod, "RULES", [])), getattr(mod, "PATCH", None)


def redact_text(text: str, rules: list[tuple[str, str]]) -> str:
    for old, new in rules:
        text = text.replace(old, new)
    for pat, new in GENERIC_REGEX:
        text = pat.sub(new, text)
    return text


def is_private(rel: str) -> bool:
    return any(rel == f or rel.startswith(f) for f in PRIVATE_FILES)


def main() -> int:
    rules, patch = load_private()
    changed = 0
    for p in sorted(CORPUS.rglob("*")):
        rel = str(p.relative_to(ROOT))
        if not p.is_file() or p.suffix not in {".md", ".txt", ".json", ".jsonl", ".yaml"}:
            continue
        if is_private(rel) or rel.startswith(("corpus/recipes/", "corpus/llms/mongodb.com.llms/")):
            continue
        old = p.read_text(encoding="utf-8", errors="replace")
        new = redact_text(old, rules)
        if new != old:
            p.write_text(new, encoding="utf-8")
            changed += 1
            print(f"redacted {rel}", file=sys.stderr)
    if patch and Path(patch).is_file():
        cmd = ["patch", "-p1", "--forward", "-s", "-i", str(patch)]
        r = subprocess.run(cmd, check=False, cwd=ROOT, capture_output=True, text=True)
        status = "applied" if r.returncode == 0 else "FAILED/partial"
        print(f"patch {status}: {r.stdout.strip() or r.stderr.strip()}", file=sys.stderr)
    print(f"{changed} file(s) changed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
