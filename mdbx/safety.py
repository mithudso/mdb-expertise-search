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
    absolute = _normalized_directory(path)
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


def _normalized_directory(path):
    absolute = Path(os.path.abspath(path))
    # macOS exposes standard temporary/configuration roots through fixed system
    # aliases. Resolve only these verified aliases; user-controlled links still
    # fail the descriptor walk below.
    if sys.platform == 'darwin' and len(absolute.parts) > 1 and absolute.parts[1] in ('var', 'tmp', 'etc'):
        alias = '/' + absolute.parts[1]
        if os.path.islink(alias) and os.readlink(alias) in ('private' + alias, '/private' + alias):
            absolute = Path('/private').joinpath(*absolute.parts[1:])
    return absolute


def _regular_info(parent, name):
    try:
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('output must be a regular file, not a link')
    return info


def _read_bytes(parent, name, maximum=None):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('output must be a regular file')
        return stream.read() if maximum is None else stream.read(maximum)


def _same_directory(parent, path):
    try:
        actual = os.stat(_normalized_directory(path), follow_symlinks=False)
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
            if expected is not None and (previous is None or _read_bytes(parent, path.name, len(expected) + 1) != expected):
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
                # Exchange cannot leave a gap, even on filesystems without hard links.
                os.rename(temporary, recovery, src_dir_fd=parent, dst_dir_fd=parent)
                try:
                    _exchange(parent, recovery, path.name)
                except BaseException:
                    os.unlink(recovery, dir_fd=parent)
                    raise
                try:
                    if _read_bytes(parent, recovery, len(expected) + 1) != expected:
                        raise ValueError('file changed; displaced version retained in .mdbx-recovery-*')
                except BaseException:
                    # Another save is retained in recovery even if it wins this exchange.
                    _exchange(parent, recovery, path.name)
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


def _exchange(parent, left, right):
    """Atomically exchange entries in a pinned directory, or change neither."""
    import ctypes
    import errno
    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, 'renameatx_np', None) or getattr(libc, 'renameat2', None)
    if function is None:
        raise RuntimeError('atomic exchange unavailable; destination preserved')
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    if function(parent, os.fsencode(left), parent, os.fsencode(right), 2):
        number = ctypes.get_errno()
        if number in (errno.ENOSYS, errno.ENOTSUP, errno.EINVAL):
            raise RuntimeError('atomic exchange unavailable; destination preserved')
        raise OSError(number, 'atomic exchange failed')


def _remove_entry(parent, name):
    import shutil
    try:
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return
    if stat.S_ISDIR(info.st_mode):
        shutil.rmtree(name, dir_fd=parent)
    else:
        os.unlink(name, dir_fd=parent)


def _rename_exclusive(source, target, *, src_dir_fd, dst_dir_fd):
    """Move one descriptor-relative entry without replacing an existing name."""
    import ctypes
    import errno
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == 'darwin':
        function, flag = getattr(libc, 'renameatx_np', None), 4  # RENAME_EXCL
    elif sys.platform.startswith('linux'):
        function, flag = getattr(libc, 'renameat2', None), 1  # RENAME_NOREPLACE
    else:
        function, flag = None, None
    if function is None:
        raise RuntimeError('exclusive generation rename unavailable; generation preserved')
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    if function(src_dir_fd, os.fsencode(source), dst_dir_fd, os.fsencode(target), flag):
        number = ctypes.get_errno()
        if number in (errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EINVAL):
            raise RuntimeError('exclusive generation rename unavailable; generation preserved')
        raise OSError(number, 'exclusive generation rename failed')


def _publication_rename_probe(source, parent):
    """Exercise collision refusal and file/directory moves using owned entries only."""
    token = '.mdbx-probe-' + uuid.uuid4().hex
    held = []
    created = []
    try:
        for directory in (source, parent):
            os.mkdir(token, 0o700, dir_fd=directory)
            created.append(directory)
            held.append(os.open(token, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory))
        left, right = held
        for name, directory in (('file', False), ('directory', True)):
            for descriptor in held:
                if directory:
                    os.mkdir(name, 0o700, dir_fd=descriptor)
                else:
                    fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=descriptor)
                    os.close(fd)
            before = [os.stat(name, dir_fd=fd, follow_symlinks=False) for fd in held]
            try:
                _rename_exclusive(name, name, src_dir_fd=left, dst_dir_fd=right)
            except FileExistsError:
                pass
            else:
                raise RuntimeError('exclusive generation rename did not preserve the collision')
            after = [os.stat(name, dir_fd=fd, follow_symlinks=False) for fd in held]
            if any((old.st_dev, old.st_ino) != (new.st_dev, new.st_ino) for old, new in zip(before, after)):
                raise RuntimeError('exclusive generation rename changed a collision')
            (os.rmdir if directory else os.unlink)(name, dir_fd=right)
            _rename_exclusive(name, name, src_dir_fd=left, dst_dir_fd=right)
            moved = os.stat(name, dir_fd=right, follow_symlinks=False)
            if (moved.st_dev, moved.st_ino) != (before[0].st_dev, before[0].st_ino):
                raise RuntimeError('exclusive generation rename lost the probe entry')
    finally:
        for descriptor in held:
            os.close(descriptor)
        for directory in created:
            _remove_entry(directory, token)


def publish_entries(directory, staged, names, *, lock_name):
    """Publish under pinned descriptors without replacing an uncooperative writer.

    Probe exclusive rename before changing generation members. Keep every moved
    version in recovery, including successful previous generations and late inode
    writes. On failure, restore every available member without replacing a live
    name. Cooperating readers and publishers share the same directory lock.
    """
    names = tuple(names)
    if len(set(names)) != len(names) or any(not isinstance(name, str) or Path(name).name != name or name in ('', '.', '..') for name in names):
        raise ValueError('invalid generation member')
    parent = _directory(directory, create=True)
    source = None
    backups, published = {}, {}
    generation = uuid.uuid4().hex
    def recovery(position, kind):
        return f'.mdbx-recovery-{generation}-{position}-{kind}'
    try:
        source = _directory(staged)
        if (os.fstat(source).st_dev, os.fstat(source).st_ino) == (os.fstat(parent).st_dev, os.fstat(parent).st_ino):
            raise ValueError('staging and publication directories must differ')
        with directory_lock(parent, lock_name):
            if not _same_directory(parent, directory):
                raise ValueError('publication directory changed')
            candidates = {}
            for name in names:
                candidate = os.stat(name, dir_fd=source, follow_symlinks=False)
                if not (stat.S_ISREG(candidate.st_mode) or stat.S_ISDIR(candidate.st_mode)):
                    raise ValueError('unsupported generation member')
                candidates[name] = (candidate.st_dev, candidate.st_ino)
            _publication_rename_probe(source, parent)
            if not _same_directory(parent, directory):
                raise ValueError('publication directory changed')
            try:
                for position, name in enumerate(names):
                    try:
                        old = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    except FileNotFoundError:
                        old = None
                    if old is not None:
                        if not (stat.S_ISREG(old.st_mode) or stat.S_ISDIR(old.st_mode)):
                            raise ValueError('unsupported previous generation member')
                        backup = recovery(position, 'previous')
                        _rename_exclusive(name, backup, src_dir_fd=parent, dst_dir_fd=parent)
                        backups[name] = backup
                    _rename_exclusive(name, name, src_dir_fd=source, dst_dir_fd=parent)
                    published[name] = candidates[name]
                os.fsync(parent)
                if not _same_directory(parent, directory):
                    raise ValueError('publication directory moved; held generation retained')
            except BaseException as error:
                for position in reversed(range(len(names))):
                    name = names[position]
                    if name in published:
                        try:
                            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                            if (current.st_dev, current.st_ino) == published[name]:
                                _rename_exclusive(name, recovery(position, 'published'), src_dir_fd=parent, dst_dir_fd=parent)
                        except (OSError, RuntimeError):
                            pass  # Keep the live version when evacuation cannot complete.
                    if name in backups:
                        try:
                            _rename_exclusive(backups[name], name, src_dir_fd=parent, dst_dir_fd=parent)
                        except (OSError, RuntimeError):
                            pass  # A concurrent live entry and the backup both remain intact.
                # A caller may clean its staging directory after this exception. Preserve remaining
                # named entries beside the held generation whenever the filesystem permits it.
                for position, name in enumerate(names):
                    try:
                        _rename_exclusive(name, recovery(position, 'staged'), src_dir_fd=source, dst_dir_fd=parent)
                    except (OSError, RuntimeError):
                        pass  # publish_files also retains any non-empty staging directory.
                try:
                    os.fsync(parent)
                except OSError:
                    pass
                error.add_note(f'preserved recovery prefix .mdbx-recovery-{generation}-; member slots follow publication order')
                raise
    finally:
        try:
            if source is not None:
                os.close(source)
        finally:
            os.close(parent)


def publish_files(directory, values, *, lock_name):
    import tempfile
    # Never recursively delete this directory: on failure it may hold a replacement
    # or a candidate that could not be moved to a destination recovery name.
    staged = Path(tempfile.mkdtemp(prefix='mdbx-publish-'))
    try:
        for name, data in values.items():
            if not isinstance(name, str) or Path(name).name != name or name in ('', '.', '..'):
                raise ValueError('invalid generation member')
            (staged / name).write_bytes(data)
        publish_entries(directory, staged, tuple(values), lock_name=lock_name)
    except BaseException as error:
        error.add_note(f'unpublished entries may remain in staging at {staged}')
        raise
    finally:
        try:
            staged.rmdir()  # Remove only an empty, owned directory.
        except OSError:
            pass


def _directory_at(root_fd: int, parts: tuple[str, ...]) -> int:
    """Open a relative directory in a held root generation with constant descriptors."""
    current = os.dup(root_fd)
    try:
        for name in parts:
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = child
        return current
    except BaseException:
        os.close(current)
        raise


@contextmanager
def open_confined_at(root_fd: int, relative: str):
    """Read a regular UTF-8 file from an already-held directory generation."""
    _require_descriptors()
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or any(p in ('..', '') for p in parts):
        raise ValueError('path must be relative to the corpus')
    current = fd = None
    stream = None
    try:
        try:
            current = _directory_at(root_fd, parts[:-1])
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
