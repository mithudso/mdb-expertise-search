"""Confined file access and publication that preserves concurrent edits."""
from __future__ import annotations

import hashlib
import io
import os
import stat
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

_DIR_FD = os.open in os.supports_dir_fd


def _require_descriptors():
    if not _DIR_FD or not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY'):
        raise ValueError('secure file access requires POSIX no-follow directory descriptors')


def _directory(path: Path, *, create=False):
    """Hold the resolved parent without reopening an ancestor by pathname."""
    _require_descriptors()
    absolute = Path(os.path.abspath(path))
    # macOS exposes standard temporary/configuration roots through fixed system
    # aliases. Resolve only these verified aliases; user-controlled links still
    # fail the descriptor walk below.
    if sys.platform == 'darwin' and len(absolute.parts) > 1 and absolute.parts[1] in ('var', 'tmp', 'etc'):
        alias = '/' + absolute.parts[1]
        if os.path.islink(alias) and os.readlink(alias) in ('private' + alias, '/private' + alias):
            absolute = Path('/private').joinpath(*absolute.parts[1:])
    current = os.open(absolute.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name in absolute.parts[1:]:
            try:
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(name, mode=0o755, dir_fd=current)
                except FileExistsError:
                    pass
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = child
        return current
    except BaseException:
        os.close(current)
        raise


def _regular_info(parent, name):
    try:
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('output must be a regular file, not a link')
    return info


def _read_bytes(parent, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('output must be a regular file')
        return stream.read()


def _same_directory(parent, path):
    try:
        actual = os.stat(path, follow_symlinks=False)
    except OSError:
        return False
    held = os.fstat(parent)
    return stat.S_ISDIR(actual.st_mode) and (actual.st_dev, actual.st_ino) == (held.st_dev, held.st_ino)


@contextmanager
def directory_lock(parent, name):
    """Serialize cooperating publishers; the stable lock inode remains in place."""
    import fcntl
    token = hashlib.sha256(name.encode()).hexdigest()[:24]
    fd = os.open('.mdbx-lock-' + token, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('publication lock must be a regular file')
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def atomic_write(path: Path, data: bytes, *, expected: bytes | None = None) -> None:
    """Publish a regular file through a held parent descriptor.

    With ``expected``, move the actual displaced version to a unique recovery
    file, then publish exclusively. An uncooperative editor's new file is never
    overwritten. Recovery versions remain available, including late writes to
    the displaced inode. Cooperating writers share a stable destination lock.
    """
    path = Path(path)
    parent = _directory(path.parent, create=True)
    temporary = '.mdbx-temporary-' + uuid.uuid4().hex
    recovery = '.mdbx-recovery-' + uuid.uuid4().hex
    try:
        with directory_lock(parent, path.name):
            if not _same_directory(parent, path.parent):
                raise ValueError('output directory changed during preparation')
            previous = _regular_info(parent, path.name)
            if expected is not None and (previous is None or _read_bytes(parent, path.name) != expected):
                raise ValueError('file changed while preparing the update')
            fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(fd, 'wb') as stream:
                if previous:
                    os.fchmod(stream.fileno(), stat.S_IMODE(previous.st_mode))
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            _regular_info(parent, path.name)
            if expected is None:
                os.replace(temporary, path.name, src_dir_fd=parent, dst_dir_fd=parent)
            else:
                os.rename(path.name, recovery, src_dir_fd=parent, dst_dir_fd=parent)
                try:
                    if _read_bytes(parent, recovery) != expected:
                        raise ValueError('file changed; displaced version retained in .mdbx-recovery-*')
                    os.link(temporary, path.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                except BaseException:
                    try:
                        os.link(recovery, path.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                    except FileExistsError:
                        pass
                    raise
            os.fsync(parent)
            if not _same_directory(parent, path.parent):
                raise ValueError('output directory moved during publication; held directory retains the result')
    finally:
        try:
            try:
                os.unlink(temporary, dir_fd=parent)
            except FileNotFoundError:
                pass
        finally:
            os.close(parent)


@contextmanager
def open_confined(root: Path, relative: str):
    """Open a regular UTF-8 file below root with constant descriptor usage."""
    _require_descriptors()
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or any(p in ('..', '') for p in parts):
        raise ValueError('path must be relative to the corpus')
    current = fd = None
    stream = None
    try:
        try:
            current = _directory(root)
            for name in parts[:-1]:
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
                os.close(current)
                current = child
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError('corpus entry must be a regular file')
            stream = io.TextIOWrapper(os.fdopen(fd, 'rb'), encoding='utf-8')
            fd = None
        except OSError as exc:
            raise ValueError('corpus file unavailable or unsafe') from exc
        yield stream
    finally:
        try:
            if stream is not None:
                stream.close()
        finally:
            try:
                if fd is not None:
                    os.close(fd)
            finally:
                if current is not None:
                    os.close(current)


def read_range(root: Path, relative: str, start: int = 1, end: int | None = None, *, max_chars: int = 12000) -> str:
    if start < 1 or (end is not None and end < start) or max_chars < 1:
        raise ValueError('invalid line range or character limit')
    out = []
    used, line = 0, 1
    separators = '\n\v\f\x1c\x1d\x1e\x85\u2028\u2029'
    with open_confined(root, relative) as stream:
        while chunk := stream.read(8192):
            for char in chunk:
                if line >= start:
                    out.append(char)
                    used += 1
                    if used >= max_chars:
                        return ''.join(out).rstrip(separators)
                if char in separators:
                    if end is not None and line >= end:
                        return ''.join(out).rstrip(separators)
                    line += 1
    return ''.join(out).rstrip(separators)
