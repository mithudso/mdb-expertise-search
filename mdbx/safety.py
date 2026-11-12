"""Small file-preservation primitives used by local tooling."""
from __future__ import annotations

import io
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path


def atomic_write(path: Path, data: bytes, *, expected: bytes | None = None) -> None:
    """Publish a complete regular file beside its destination; reject symlinks/conflicts."""
    path = Path(path)
    if any(parent.is_symlink() for parent in path.absolute().parents):
        raise ValueError('refusing a symlink output ancestor')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('refusing a symlink output')
    previous = path.stat() if path.exists() else None
    if previous and not stat.S_ISREG(previous.st_mode):
        raise ValueError('output must be a regular file')
    if expected is not None and path.read_bytes() != expected:
        raise ValueError('file changed while preparing the update')
    fd, raw = tempfile.mkstemp(prefix='.mdbx-', dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if previous:
            os.chmod(temporary, stat.S_IMODE(previous.st_mode))
        if path.is_symlink() or (expected is not None and path.read_bytes() != expected):
            raise ValueError('file changed while preparing the update')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def open_confined(root: Path, relative: str):
    """Open a regular UTF-8 file below root without traversing child symlinks."""
    if not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY') or os.open not in os.supports_dir_fd:
        raise ValueError('secure corpus reads require POSIX no-follow directory descriptors')
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or any(p in ('..', '') for p in parts):
        raise ValueError('path must be relative to the corpus')
    descriptors = []
    stream = None
    try:
        current = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        descriptors.append(current)
        for name in parts[:-1]:
            current = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            descriptors.append(current)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
        descriptors.append(fd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('corpus entry must be a regular file')
        stream = io.TextIOWrapper(os.fdopen(os.dup(fd), 'rb'), encoding='utf-8')
        yield stream
    except OSError as exc:
        raise ValueError('corpus file unavailable or unsafe') from exc
    finally:
        if stream:
            stream.close()
        for fd in reversed(descriptors):
            os.close(fd)


def read_range(root: Path, relative: str, start: int = 1, end: int | None = None, *, max_chars: int = 12000) -> str:
    if start < 1 or (end is not None and end < start):
        raise ValueError('invalid line range')
    out = []
    used = 0
    with open_confined(root, relative) as stream:
        line = 1
        while used < max_chars:
            chunk = stream.readline(max_chars - used + 1)
            if not chunk:
                break
            if line >= start:
                out.append(chunk[:max_chars - used])
                used += len(out[-1])
            if chunk.endswith('\n'):
                if end is not None and line >= end:
                    break
                line += 1
    return ''.join(out).rstrip('\n')
