"""Copy publication text from one available source family and reconcile prior owned files."""
from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
from contextlib import contextmanager
from pathlib import Path

from maintenance_safety import atomic_write, git_environment, lock, safe_bytes

ROOT = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonl"}  # inspected by both privacy gates


def reject_destination_symlinks(destination: Path) -> None:
    for parent in (destination, *destination.parents):
        if parent.is_symlink():
            raise ValueError("destination symlink is not allowed")
    if destination.exists() and any(p.is_symlink() for p in destination.rglob("*")):
        raise ValueError("destination symlink is not allowed")


def _directory(path: Path, *, create=False):
    path = Path(path).absolute()
    current = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            if create:
                try:
                    os.mkdir(part, dir_fd=current)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = child
        return current
    except BaseException:
        os.close(current)
        raise


@contextmanager
def _parent(root, relative):
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or any(part in {".", ".."} for part in parts):
        raise ValueError("invalid owned path")
    current = _directory(root)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = child
        yield current, parts[-1]
    finally:
        os.close(current)


def sync_tree(source: Path, destination: Path, state_path: Path, *, facts_only: bool = False, identity_destination: Path | None = None) -> None:
    with lock(Path(state_path).with_suffix(".lock")):
        _sync_tree(source, destination, state_path, facts_only=facts_only, identity_destination=identity_destination)


def _sync_tree(source: Path, destination: Path, state_path: Path, *, facts_only: bool = False, identity_destination: Path | None = None) -> None:
    source, destination, state_path = Path(source), Path(destination), Path(state_path)
    if source.is_symlink():
        raise ValueError("source symlink is not allowed")
    if not source.is_dir():
        return  # an unavailable source does not authorize deletion
    reject_destination_symlinks(destination)
    files = []
    def traversal_error(error):
        raise error
    for directory, folders, names in os.walk(source, onerror=traversal_error, followlinks=False):
        if any((Path(directory) / name).is_symlink() for name in folders):
            raise ValueError("source symlink is not allowed")
        for name in sorted(names):
            path = Path(directory) / name
            permitted = not facts_only or path.relative_to(source).as_posix() in {"llms.txt", "llms-facts.txt", "llms-vocabulary.txt", "manifest.json"}
            if path.suffix in TEXT_SUFFIXES and path.name != ".skillfish.json" and permitted:
                if path.is_symlink():
                    raise ValueError("source symlink is not allowed")
                content = safe_bytes(path, source, max_bytes=16 * 1024 * 1024)
                mode = (path.stat(follow_symlinks=False).st_mode & 0o666) | 0o200
                files.append((path, content, mode))
    if any(parent.is_symlink() for parent in (state_path, *state_path.parents)):
        raise ValueError("ownership state symlink is not allowed")
    manifest = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    if not isinstance(manifest, dict) or any(not isinstance(names, list) or any(not isinstance(name, str) for name in names) for names in manifest.values()):
        raise ValueError("invalid source ownership state")
    key = str((identity_destination or destination).absolute())
    previous = manifest.get(key, [])
    current = {path.relative_to(source).as_posix() for path, _, _ in files}
    for name in previous:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("invalid source ownership state")
    # Reserve every path before copying. A failed copy remains owned and recoverable next time.
    manifest[key] = sorted(set(previous) | current)
    state_directory = _directory(state_path.parent, create=True)
    os.close(state_directory)
    atomic_write(state_path, (json.dumps(manifest, sort_keys=True) + "\n").encode(), 0o600, root=state_path.parent)
    descriptor = _directory(destination, create=True)
    os.close(descriptor)
    for name in sorted(set(previous) - current, key=lambda value: (-len(Path(value).parts), value)):
        with _parent(destination, name) as (parent, leaf):
            try:
                info = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("owned obsolete path is not regular")
            os.unlink(leaf, dir_fd=parent)
        parent = Path(name).parent
        while str(parent) != ".":
            try:
                with _parent(destination, parent) as (parent_fd, leaf):
                    os.rmdir(leaf, dir_fd=parent_fd)
            except OSError:
                break
            parent = parent.parent
    for path, content, mode in files:
        relative = path.relative_to(source)
        # Only an empty old owned directory may be removed during a type transition.
        try:
            with _parent(destination, relative) as (parent, leaf):
                info = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    os.rmdir(leaf, dir_fd=parent)
                elif not stat.S_ISREG(info.st_mode):
                    raise ValueError("destination path is not regular")
                else:
                    mode &= stat.S_IMODE(info.st_mode) | 0o200
        except FileNotFoundError:
            pass
        atomic_write(destination / relative, content, mode, root=destination)
    manifest[key] = sorted(current)
    atomic_write(state_path, (json.dumps(manifest, sort_keys=True) + "\n").encode(), 0o600,
                 root=state_path.parent)


def check_publication(corpus: Path, *, repository: Path | None = None) -> None:
    """Reject publishable files that neither text privacy gate inspects."""
    corpus = corpus.absolute()
    result = subprocess.run(
        ["git", "-C", str(repository or corpus.parent), "--work-tree", str(corpus.parent), "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", corpus.name],
        cwd=corpus.parent, capture_output=True, check=True, timeout=30, env=git_environment(),
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
