#!/usr/bin/env python3
"""Redact customer and internal-tooling references from the corpus copies, in place.

Idempotent. Run by scripts/sync_corpus.sh after copying. Rules are exact-phrase replacements so
generic words ("session cookie") are untouched. Files that cannot be redacted are listed in
.gitignore (PRIVATE_FILES) and never committed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"

# Order matters: longer phrases first.
RULES: list[tuple[str, str]] = [
    ('Active customer context (2026): **Goldman Sachs "Cookie" 7.0 → 8.0** and',
     "Large-customer upgrade programs (2026): **a 7.0 → 8.0 fleet upgrade** and"),
    ('Goldman Sachs "Cookie" cluster upgrades from 7.0 → 8.0', "Large-fleet cluster upgrades from 7.0 → 8.0"),
    ("Goldman Sachs Cookie 7.0→8.0 risk review", "a large-fleet 7.0→8.0 risk review"),
    ("Goldman Sachs Cookie upgrade", "large-fleet upgrade"),
    ("Goldman Sachs operators", "customer operators"),
    ("Goldman Sachs", "a large customer"),
    ("(Cookie 7.0→8.0)", "(large-fleet 7.0→8.0)"),
    ("(Cookie 7.0 → 8.0 lesson)", "(7.0 → 8.0 lesson)"),
    ("Cookie 7.0 → 8.0 lesson", "7.0 → 8.0 lesson"),
    ("Cookie-style", "large-fleet-style"),
    ("Cookie pre-warm SOP", "pre-warm SOP"),
    ("cookie pre-warm SOP", "pre-warm SOP"),
    ("(Cookie 7.0→8.0 lesson)", "(7.0→8.0 lesson)"),
    ("GS Rewards Production Failover Test", "a customer's Production Failover Test"),
    ("concept from GS Rewards PFT", "concept from a customer PFT"),
    ("GS Rewards PFT", "customer PFT"),
    ("GS/JPMC-class procurement", "large-bank-class procurement"),
    ("the customer's GS docs", "the customer's own docs"),
    ("case 01574262 pattern", "a real support-case pattern"),
    ("Case 01574262 takeaway", "Support-case takeaway"),
    ("case 01574262", "a support case"),
    ("01581027", "0000000"),
    ("`10gen/mdb-tam`", "an internal repository"),
    ("10gen/mdb-tam", "an internal repository"),
    ("the mdb-tam repository", "an internal repository"),
    ("references/10gen.md", "references/internal-repos.md"),
    ("10gen repos", "internal repos"),
    ("10gen repo", "internal repo"),
]

# Exact files that stay local-only because redaction cannot make them safe.
PRIVATE_FILES = [
    "corpus/llms/uber-mongodb-skill.md",
    "corpus/llms/memory-central/",
    "corpus/skills/atlas-diagnostics-expert/SKILL.md",
    "corpus/skills/atlas-diagnostics-expert/references/atlas-diagnostics-package.md",
]


def redact_text(text: str) -> str:
    for old, new in RULES:
        text = text.replace(old, new)
    return text


def main() -> int:
    changed = 0
    for p in sorted(CORPUS.rglob("*")):
        rel = str(p.relative_to(ROOT))
        if not p.is_file() or p.suffix not in {".md", ".txt"}:
            continue
        if any(rel == f or rel.startswith(f) for f in PRIVATE_FILES):
            continue
        old = p.read_text(encoding="utf-8", errors="replace")
        new = redact_text(old)
        if new != old:
            p.write_text(new, encoding="utf-8")
            changed += 1
            print(f"redacted {rel}", file=sys.stderr)
    print(f"{changed} file(s) changed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
