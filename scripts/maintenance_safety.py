"""Small preservation primitives shared by local maintenance commands."""
import fcntl
import json
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path


def scrub(value):
    def clean(match):
        url = match.group(0)
        head, separator, authority = url.partition('://')
        authority, slash, tail = authority.partition('/')
        if '@' in authority:
            authority = '<credentials>@' + authority.rsplit('@', 1)[1]
        url = head + separator + authority + slash + tail
        cut = min((url.find(mark) for mark in ('?', '#') if mark in url), default=-1)
        return url[:cut] + '<query omitted>' if cut >= 0 else url
    return re.sub(r'https?://(?:(?!https?://)[^\s])*', clean, str(value), flags=re.IGNORECASE)


@contextmanager
def lock(path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError("maintenance operation is busy") from None
        yield
    finally: os.close(fd)


def safe_bytes(path, root, *, max_bytes=None):
    """Pin the lexical root and walk without symlinks. The caller trusts its root ancestors."""
    if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 0):
        raise ValueError('invalid input byte limit')
    lexical_root = Path(root).absolute(); root = lexical_root; path = Path(path).absolute()
    try: parts = path.relative_to(lexical_root).parts
    except ValueError: raise ValueError("input is outside the allowed directory") from None
    if not parts or any(p in {"", ".", ".."} for p in parts): raise ValueError("invalid input path")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd); os.close(fd); fd = child
        data_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(data_fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode): raise ValueError("input is not a regular file")
            data = stream.read() if max_bytes is None else stream.read(max_bytes + 1)
            if max_bytes is not None and len(data) > max_bytes:
                raise ValueError('input exceeds the byte limit')
            return data
    finally: os.close(fd)


def atomic_write(path, data, mode=0o644, *, root=None):
    path = Path(path).absolute()
    if root is None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="." + path.name + "-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), mode)
            os.replace(temporary, path)
        finally:
            if os.path.lexists(temporary): os.unlink(temporary)
        return
    import uuid
    relative = path.relative_to(Path(root).absolute())
    if not relative.parts or any(part in {".", ".."} for part in relative.parts):
        raise ValueError("invalid output path")
    directory = os.open(Path(root).absolute(), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = "." + path.name + "-" + uuid.uuid4().hex
    created = False
    try:
        for part in relative.parts[:-1]:
            try: os.mkdir(part, dir_fd=directory)
            except FileExistsError: pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory); directory = child
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, mode, dir_fd=directory)
        created = True
        with os.fdopen(fd, "wb") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), mode)
        os.replace(temporary, relative.name, src_dir_fd=directory, dst_dir_fd=directory)
        created = False
    finally:
        try:
            if created: os.unlink(temporary, dir_fd=directory)
        finally:
            os.close(directory)


def confined_corpus_path(root, value):
    root = Path(root).resolve(); rel = Path(value)
    if rel.is_absolute() or not rel.parts or rel.parts[0] != "corpus" or any(p in {"..", "."} for p in rel.parts):
        raise RuntimeError("invalid scanner corpus path")
    candidate = root / rel
    if not candidate.resolve().is_relative_to(root / "corpus") or any(p.is_symlink() for p in [candidate, *candidate.parents] if p != root and p.is_relative_to(root)):
        raise RuntimeError("scanner path escapes corpus")
    return candidate


def clone_marker(clone): return Path(clone) / ".git" / "mdbx-maintenance-owner.json"


def verify_clone(clone, repo, working_root, git):
    clone = Path(clone).resolve()
    if clone == Path(working_root).resolve(): raise RuntimeError("refusing the working checkout as a maintenance clone")
    marker = clone_marker(clone)
    try: info = json.loads(marker.read_text())
    except (OSError, ValueError): raise RuntimeError("existing clone is not owned by this updater; choose an empty clone directory") from None
    if info != {"path": str(clone), "repo": repo}: raise RuntimeError("maintenance clone ownership or repository mismatch")
    origin = git(["remote", "get-url", "origin"], clone)
    if origin.returncode or origin.stdout.strip() != repo: raise RuntimeError("maintenance clone origin does not match configuration")
    status = git(["status", "--porcelain", "--untracked-files=all"], clone)
    if status.returncode or status.stdout.strip(): raise RuntimeError("maintenance clone contains changes; preserve them before updating")
    return clone


def mark_clone(clone, repo):
    atomic_write(clone_marker(clone), json.dumps({"path": str(Path(clone).resolve()), "repo": repo}).encode(), 0o600)


_GIT_SELECTORS = {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"}


def git_environment(environment=None):
    return {key: value for key, value in (os.environ if environment is None else environment).items()
            if key not in _GIT_SELECTORS}


def _primitives():
    # These primitives import no providers or model runtimes.
    import sys
    source = str(Path(__file__).resolve().parent.parent)
    if source not in sys.path:
        sys.path.insert(0, source)
    from mdbx.safety import _directory, _exchange, _read_bytes, _same_directory
    return _directory, _exchange, _read_bytes, _same_directory


def exchange_entries(left, right, root):
    """Exchange two existing no-follow sibling files/directories under root."""
    directory, exchange, _, same = _primitives()
    root = Path(root).absolute()
    left, right = Path(left).absolute(), Path(right).absolute()
    for path in (left, right):
        rel = path.relative_to(root)
        if not rel.parts or any(part in {'.', '..'} for part in rel.parts):
            raise ValueError('invalid exchange path')
    if left.parent != right.parent:
        raise ValueError('exchange entries must share a parent')
    parent = directory(left.parent)
    try:
        if not same(parent, left.parent):
            raise RuntimeError('exchange parent changed')
        for name in (left.name, right.name):
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise ValueError('exchange input must be a regular file or directory')
        exchange(parent, left.name, right.name)
        os.fsync(parent)
    finally:
        os.close(parent)


class Recovery:
    """Own a retained entry by directory descriptor, independently of its path."""
    def __init__(self, parent, name):
        self.parent = os.dup(parent)
        self.name = name

    def unlink(self):
        os.unlink(self.name, dir_fd=self.parent)

    def move_to(self, directory):
        import ctypes
        import errno
        open_directory, _, _, same = _primitives()
        target = open_directory(directory)
        try:
            if not same(target, directory) or stat.S_IMODE(os.fstat(target).st_mode) & 0o077:
                raise ValueError('recovery destination must be a private pinned directory')
            libc = ctypes.CDLL(None, use_errno=True)
            function = getattr(libc, 'renameatx_np', None)
            flags = 4
            if function is None:
                function = getattr(libc, 'renameat2', None)
                flags = 1
            if function is None:
                raise RuntimeError('exclusive recovery move unavailable; recovery retained')
            function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            function.restype = ctypes.c_int
            if function(self.parent, os.fsencode(self.name), target, os.fsencode(self.name), flags):
                number = ctypes.get_errno()
                if number in (errno.ENOSYS, errno.ENOTSUP, errno.EINVAL):
                    raise RuntimeError('exclusive recovery move unavailable; recovery retained')
                raise OSError(number, 'recovery move failed; recovery retained')
            os.fsync(target)
        finally:
            os.close(target)

    def close(self):
        if self.parent is not None:
            os.close(self.parent)
            self.parent = None

    def __del__(self):
        self.close()


def replace_preserving(path, data, root, expected, mode=0o600):
    """Exchange a staged file and retain the displaced inode in a pinned Recovery."""
    import uuid
    directory, exchange, read, same = _primitives()
    path, root = Path(path).absolute(), Path(root).absolute()
    relative = path.relative_to(root)
    if not relative.parts or any(part in {'.', '..'} for part in relative.parts):
        raise ValueError('invalid replacement path')
    parent = directory(path.parent)
    temporary = '.' + path.name + '.recovery-' + uuid.uuid4().hex
    staged = exchanged = False
    try:
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, mode, dir_fd=parent)
        staged = True
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), mode)
        if not same(parent, path.parent) or read(parent, path.name, len(expected) + 1) != expected:
            raise RuntimeError('replacement input changed; source preserved')
        exchange(parent, temporary, path.name)
        exchanged = True
        try:
            if read(parent, temporary, len(expected) + 1) != expected:
                raise RuntimeError('concurrent save detected; displaced data preserved')
        except BaseException:
            exchange(parent, temporary, path.name)
            raise
        return Recovery(parent, temporary)
    finally:
        try:
            if staged and not exchanged:
                os.unlink(temporary, dir_fd=parent)
        finally:
            os.close(parent)
