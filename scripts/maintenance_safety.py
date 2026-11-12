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
    text = str(value)
    text = re.sub(r"(https?://)[^/@\s]+@", r"\1<credentials>@", text)
    text = re.sub(r"(https?://[^\s?#]+)[?#][^\s]*", r"\1<query omitted>", text)
    return text


@contextmanager
def lock(path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError("maintenance operation is busy") from None
        yield
    finally: os.close(fd)


def safe_bytes(path, root):
    """Pin the lexical root and walk without symlinks. The caller trusts its root ancestors."""
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
            return stream.read()
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
        if created: os.unlink(temporary, dir_fd=directory)
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
    status = git(["status", "--porcelain"], clone)
    if status.returncode or status.stdout.strip(): raise RuntimeError("maintenance clone contains changes; preserve them before updating")
    return clone


def mark_clone(clone, repo):
    atomic_write(clone_marker(clone), json.dumps({"path": str(Path(clone).resolve()), "repo": repo}).encode(), 0o600)


_GIT_SELECTORS = {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"}


def git_environment(environment=None):
    return {key: value for key, value in (os.environ if environment is None else environment).items()
            if key not in _GIT_SELECTORS}


def replace_preserving(path, data, root, expected, mode=0o600):
    """Exchange a staged file with the pinned destination, retaining the displaced inode.

    A concurrent editor save remains in the returned recovery file, including writes through an
    already-open descriptor. If its content differs from expected, restore it when possible and
    report a conflict. Platforms without an atomic exchange fail before changing the destination.
    """
    import ctypes
    import errno
    import uuid
    path, root = Path(path).absolute(), Path(root).absolute()
    relative = path.relative_to(root)
    if not relative.parts or any(part in {".", ".."} for part in relative.parts):
        raise ValueError("invalid replacement path")
    parent_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = "." + path.name + ".recovery-" + uuid.uuid4().hex
    staged = False
    exchanged = False
    try:
        for part in relative.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            os.close(parent_fd); parent_fd = child
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, mode, dir_fd=parent_fd)
        staged = True
        with os.fdopen(fd, "wb") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), mode)
        libc = ctypes.CDLL(None, use_errno=True)
        exchange = getattr(libc, "renameatx_np", None) or getattr(libc, "renameat2", None)
        if exchange is None:
            raise RuntimeError("atomic exchange is unavailable; source preserved")
        exchange.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        exchange.restype = ctypes.c_int
        def swap():
            if exchange(parent_fd, os.fsencode(temporary), parent_fd, os.fsencode(relative.name), 2):
                number = ctypes.get_errno()
                if number in {errno.ENOSYS, errno.ENOTSUP, errno.EINVAL}:
                    raise RuntimeError("atomic exchange is unavailable; source preserved")
                raise OSError(number, "atomic publication failed")
        # Validate through the pinned parent before changing either entry.
        def current(name):
            handle = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent_fd)
            with os.fdopen(handle, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError("replacement input is not regular")
                return stream.read()
        if current(relative.name) != expected:
            raise RuntimeError("replacement input changed; source preserved")
        swap(); exchanged = True
        if current(temporary) != expected:
            if current(relative.name) == data:
                swap()
            raise RuntimeError("concurrent save detected; displaced data preserved in recovery file")
        return path.parent / temporary
    finally:
        if staged and not exchanged:
            os.unlink(temporary, dir_fd=parent_fd)
        os.close(parent_fd)
