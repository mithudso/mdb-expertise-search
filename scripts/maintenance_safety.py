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
    """Walk with dir_fd and O_NOFOLLOW so a replaced parent cannot redirect a read."""
    lexical_root = Path(root).absolute(); root = lexical_root.resolve(); path = Path(path).absolute()
    try: parts = path.relative_to(lexical_root).parts
    except ValueError: raise ValueError("input is outside the allowed directory") from None
    if not parts or any(p in {"", ".", ".."} for p in parts): raise ValueError("invalid input path")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd); os.close(fd); fd = child
        data_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        with os.fdopen(data_fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode): raise ValueError("input is not a regular file")
            return stream.read()
    finally: os.close(fd)


def atomic_write(path, data, mode=0o644):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + "-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), mode)
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp): os.unlink(tmp)


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
