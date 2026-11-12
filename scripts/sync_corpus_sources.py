"""Copy publication text from one available source family and reconcile prior owned files."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from maintenance_safety import atomic_write, lock

ROOT = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonl"}  # inspected by both privacy gates


def reject_destination_symlinks(destination: Path) -> None:
    for parent in (destination, *destination.parents):
        if parent.is_symlink():
            raise ValueError("destination symlink is not allowed")
    if destination.exists() and any(p.is_symlink() for p in destination.rglob("*")):
        raise ValueError("destination symlink is not allowed")


def sync_tree(source: Path, destination: Path, state_path: Path, *, facts_only: bool = False) -> None:
    with lock(Path(state_path).with_suffix(".lock")):
        _sync_tree(source, destination, state_path, facts_only=facts_only)


def _sync_tree(source: Path, destination: Path, state_path: Path, *, facts_only: bool = False) -> None:
    source, destination, state_path = Path(source), Path(destination), Path(state_path)
    if not source.is_dir():
        return  # an unavailable source does not authorize deletion
    reject_destination_symlinks(destination)
    resolved_source = source.resolve()
    files = []
    for path in sorted(source.rglob("*")):
        if path.is_symlink() and (path.is_dir() or not path.resolve().is_relative_to(resolved_source)):
            raise ValueError("source symlink escapes the selected source family")
        permitted_name = not facts_only or path.relative_to(source).as_posix() in {"llms.txt", "llms-facts.txt", "llms-vocabulary.txt", "manifest.json"}
        if path.is_file() and path.suffix in TEXT_SUFFIXES and path.name != ".skillfish.json" and permitted_name:
            files.append(path)
    if any(parent.is_symlink() for parent in (state_path, *state_path.parents)):
        raise ValueError("ownership state symlink is not allowed")
    manifest = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    if not isinstance(manifest, dict) or any(not isinstance(names, list) or any(not isinstance(name, str) for name in names) for names in manifest.values()):
        raise ValueError("invalid source ownership state")
    key = str(destination.absolute())
    previous = manifest.get(key, [])
    current = {path.relative_to(source).as_posix() for path in files}
    for name in previous:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("invalid source ownership state")
    # Reserve every path before copying. A failed copy remains owned and recoverable next time.
    manifest[key] = sorted(set(previous) | current)
    atomic_write(state_path, (json.dumps(manifest, sort_keys=True) + "\n").encode(), 0o600)
    for name in sorted(set(previous) - current, key=lambda value: (-len(Path(value).parts), value)):
        obsolete = destination / name
        if obsolete.is_file():
            obsolete.unlink()
        parent = obsolete.parent
        while parent != destination and parent.is_relative_to(destination):
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    destination.mkdir(parents=True, exist_ok=True)
    for path in files:
        target = destination / path.relative_to(source)
        if target.is_dir():
            target.rmdir()  # Never delete unowned contents during a directory-to-file transition.
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target, follow_symlinks=True)
    manifest[key] = sorted(current)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=state_path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(manifest, stream, sort_keys=True)
            stream.write("\n")
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, state_path)
    finally:
        temporary.unlink(missing_ok=True)


def check_publication(corpus: Path) -> None:
    """Reject publishable files that neither text privacy gate inspects."""
    corpus = corpus.absolute()
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", corpus.name],
        cwd=corpus.parent, capture_output=True, check=True, timeout=30,
    )
    for relative in os.fsdecode(result.stdout).split("\0"):
        if not relative:
            continue
        candidate = corpus.parent / relative
        if candidate.is_file() and candidate.suffix not in TEXT_SUFFIXES:
            raise ValueError("publication candidate type is not inspected by both privacy gates")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-destination", type=Path)
    parser.add_argument("--check-publication", type=Path)
    parser.add_argument("--facts-only", action="store_true")
    parser.add_argument("source", type=Path, nargs="?")
    parser.add_argument("destination", type=Path, nargs="?")
    args = parser.parse_args()
    if args.check_publication is not None:
        check_publication(args.check_publication)
        return 0
    if args.check_destination is not None:
        reject_destination_symlinks(args.check_destination)
        return 0
    if args.source is None or args.destination is None:
        parser.error("source and destination are required")
    sync_tree(args.source, args.destination, ROOT / "data/corpus-sync-owned.json", facts_only=args.facts_only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
