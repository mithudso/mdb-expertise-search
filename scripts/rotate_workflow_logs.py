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
import os
import re
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maintenance_safety import atomic_write, lock, replace_preserving, safe_bytes

ROOT = Path(__file__).resolve().parent.parent
LOGS = ["memory.md", "prompts.md"]
SECTION = re.compile(r"^## v[0-9]+(?:[.][0-9A-Za-z_-]+)*(?:[ \t].*)?$")


def swap_files(p: Path) -> list[Path]:
    return [q for q in (p.with_name(f".{p.name}.swp"), p.with_name(f".{p.name}.swo"), p.with_name(f"{p.name}~"),
                        p.with_name(f".#{p.name}")) if q.exists() or q.is_symlink()]


def rotate(p: Path, max_bytes: int, keep: int, check: bool) -> bool:
    if keep < 0 or max_bytes < 0: raise ValueError("keep and max-bytes must be nonnegative")
    if not p.is_file() or p.stat().st_size <= max_bytes: return False
    if p.is_symlink(): raise ValueError("refusing symlinked workflow log")
    original = safe_bytes(p, ROOT); text = original.decode("utf-8")
    starts = []
    offset = 0
    fence = None
    fence_pattern = r"^ {0,3}(" + chr(96) + r"{3,}|~{3,})"
    for line in text.splitlines(keepends=True):
        marker = re.match(fence_pattern, line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        elif fence is None and SECTION.fullmatch(line.rstrip("\r\n")):
            starts.append(offset)
        offset += len(line)
    if len(starts) <= keep: return False
    if check:
        print(f"{p.name}: rotation due"); return True
    if swap_files(p): raise RuntimeError("workflow log has an editor lock; close it first")
    with lock(p.with_name("." + p.name + ".rotate.lock")):
        if safe_bytes(p, ROOT) != original: raise RuntimeError("workflow log changed; retry rotation")
        before = p.stat()
        kept_until = starts[keep]; retained = text[:starts[0]] + text[starts[0]:kept_until]
        archive = ROOT / "docs/archive" / f"{p.stem}-{dt.date.today().isoformat()}.md"
        if not archive.parent.resolve().is_relative_to(ROOT.resolve()): raise ValueError("archive directory is outside the repository")
        archive.parent.mkdir(parents=True, exist_ok=True)
        if archive.is_symlink() or (archive.exists() and os.path.samefile(p, archive)):
            raise ValueError("archive aliases the workflow log")
        previous = safe_bytes(archive, ROOT) if archive.exists() else b""
        import hashlib
        identity = hashlib.sha256(original).hexdigest()
        snapshot = archive.with_name(archive.name + ".source-" + identity[:16])
        if not snapshot.exists():
            atomic_write(snapshot, original, stat.S_IMODE(before.st_mode), root=ROOT)
        marker = ("<!-- mdbx-rotation:" + identity + ":" + str(kept_until) + " -->\n").encode()
        separator = b"\n" if previous and not previous.endswith(b"\n") else b""
        archive_mode = stat.S_IMODE(before.st_mode)
        if archive.exists():
            archive_mode &= stat.S_IMODE(archive.stat().st_mode)
        if marker not in previous:
            atomic_write(archive, previous + separator + marker + text[kept_until:].encode(), archive_mode, root=ROOT)
        # Atomic exchange retains the actual displaced inode, including a concurrent editor save.
        replace_preserving(p, retained.encode(), ROOT, original, stat.S_IMODE(before.st_mode))
    print(f"{p.name}: moved {len(starts) - keep} section(s)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-bytes", type=int, default=200_000)
    ap.add_argument("--keep", type=int, default=3)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.keep < 0 or a.max_bytes < 0: ap.error("keep and max-bytes must be nonnegative")
    due = [rotate(ROOT / n, a.max_bytes, a.keep, a.check) for n in LOGS]
    return 1 if a.check and any(due) else 0


if __name__ == "__main__":
    raise SystemExit(main())
