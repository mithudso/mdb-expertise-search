#!/usr/bin/env python3
"""Rotate the append-forever workflow logs (memory.md, prompts.md) into docs/archive/.

When a log grows past --max-bytes (default 200 KB), every version section (``## v...``) except the
newest --keep (default 3) moves to ``docs/archive/<name>-<date>.md``. Refuses to run while an editor
swap file for the log exists, so a half-saved buffer is never split.

    python scripts/rotate_workflow_logs.py            # rotate what is over the limit
    python scripts/rotate_workflow_logs.py --check    # exit 1 if a rotation is due, write nothing
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ["memory.md", "prompts.md"]
SECTION = re.compile(r"^## v", re.MULTILINE)


def swap_files(p: Path) -> list[Path]:
    return [q for q in (p.with_name(f".{p.name}.swp"), p.with_name(f".{p.name}.swo"), p.with_name(f"{p.name}~"),
                        p.with_name(f".#{p.name}")) if q.exists()]


def rotate(p: Path, max_bytes: int, keep: int, check: bool) -> bool:
    if not p.is_file() or p.stat().st_size <= max_bytes:
        return False
    if check:
        print(f"{p.name}: {p.stat().st_size} bytes > {max_bytes}; rotation due")
        return True
    if swap_files(p):
        sys.exit(f"error: {p.name} is open in an editor ({', '.join(map(str, swap_files(p)))}); close it first")
    text = p.read_text(encoding="utf-8")
    starts = [m.start() for m in SECTION.finditer(text)]
    if len(starts) <= keep:
        print(f"{p.name}: over the limit but only {len(starts)} version section(s); nothing to move")
        return False
    head, kept_until = text[: starts[0]], starts[keep]
    archive = ROOT / "docs" / "archive" / f"{p.stem}-{dt.date.today().isoformat()}.md"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("a", encoding="utf-8") as fh:
        fh.write(text[kept_until:])
    p.write_text(head + text[starts[0] : kept_until], encoding="utf-8")
    print(f"{p.name}: moved {len(starts) - keep} section(s) to {archive.relative_to(ROOT)}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-bytes", type=int, default=200_000)
    ap.add_argument("--keep", type=int, default=3)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    due = [rotate(ROOT / n, a.max_bytes, a.keep, a.check) for n in LOGS]
    return 1 if a.check and any(due) else 0


if __name__ == "__main__":
    raise SystemExit(main())
