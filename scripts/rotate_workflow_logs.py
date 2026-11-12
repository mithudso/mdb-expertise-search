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
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maintenance_safety import atomic_write, lock, safe_bytes

ROOT = Path(__file__).resolve().parent.parent
LOGS = ["memory.md", "prompts.md"]
SECTION = re.compile(r"^## v", re.MULTILINE)


def swap_files(p: Path) -> list[Path]:
    return [q for q in (p.with_name(f".{p.name}.swp"), p.with_name(f".{p.name}.swo"), p.with_name(f"{p.name}~"),
                        p.with_name(f".#{p.name}")) if q.exists() or q.is_symlink()]


def rotate(p: Path, max_bytes: int, keep: int, check: bool) -> bool:
    if keep < 0 or max_bytes < 0: raise ValueError("keep and max-bytes must be nonnegative")
    if not p.is_file() or p.stat().st_size <= max_bytes: return False
    if p.is_symlink(): raise ValueError("refusing symlinked workflow log")
    original = safe_bytes(p, ROOT); text = original.decode("utf-8")
    starts = [m.start() for m in SECTION.finditer(text)]
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
        # Keep a copied snapshot and retain the original inode. A writer with an already-open
        # descriptor can append after publication; the inode backup preserves those bytes too.
        import hashlib
        snapshot = archive.with_name(archive.name + ".source-" + hashlib.sha256(original).hexdigest()[:16])
        if not snapshot.exists(): atomic_write(snapshot, original, stat.S_IMODE(before.st_mode))
        separator = b"\n" if previous and not previous.endswith(b"\n") else b""
        atomic_write(archive, previous + separator + text[kept_until:].encode())
        inode_backup = archive.with_name(archive.name + ".inode-" + uuid.uuid4().hex)
        os.link(p, inode_backup, follow_symlinks=False)
        retained_inode = inode_backup.lstat()
        current_inode = p.lstat()
        expected = (before.st_dev, before.st_ino)
        if not stat.S_ISREG(retained_inode.st_mode) or (retained_inode.st_dev, retained_inode.st_ino) != expected or (current_inode.st_dev, current_inode.st_ino) != expected:
            inode_backup.unlink()
            raise RuntimeError("workflow log inode changed; source preserved")
        if safe_bytes(p, ROOT) != original or p.stat().st_ino != before.st_ino:
            raise RuntimeError("workflow log changed during rotation; source preserved")
        atomic_write(p, retained.encode(), stat.S_IMODE(before.st_mode))
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
