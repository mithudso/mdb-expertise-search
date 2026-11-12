"""corpus — discover corpus files, classify them, and split them into chunks."""
from __future__ import annotations

import hashlib
import logging
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .safety import _directory, _directory_at, open_confined_at

log = logging.getLogger("mdbx.corpus")

TEXT_SUFFIXES = {".md", ".txt"}
MAX_CHUNK_CHARS = 1600
MIN_CHUNK_CHARS = 120

#: Corpus top-level directory -> human label shown in the CLI and TUI.
KIND_LABELS = {
    "skills": "skill",
    "llms": "llms",
    "recipes": "recipe",
}

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+)$")


@dataclass(frozen=True)
class Chunk:
    path: str  # corpus-relative path
    source: str  # skill or llms set name, e.g. "mongodb-expert"
    kind: str  # skill | llms | memory
    heading: str  # heading breadcrumb
    line: int  # 1-based first line of the chunk
    text: str

    @property
    def digest(self) -> str:
        return hashlib.sha1(self.text.encode("utf-8")).hexdigest()


def embedding_input(heading: str, text: str) -> str:
    return f'{heading}\n{text}'[:2400]


def embedding_input_hash(heading: str, text: str) -> str:
    return hashlib.sha256(embedding_input(heading, text).encode('utf-8')).hexdigest()


def classify(rel: Path) -> tuple[str, str]:
    """Return ``(kind, source)`` for a corpus-relative path."""
    parts = rel.parts
    if parts[0] == "recipes":
        return "recipe", rel.stem
    if parts[0] == "skills" and len(parts) > 1:
        return "skill", parts[1]
    if len(parts) > 1 and parts[1] == "memory-central":
        return "memory", rel.stem.removesuffix("_llms")
    if parts[0] == "llms" and len(parts) > 2:
        return "llms", parts[1].removesuffix(".llms")
    return "llms", rel.stem


class _ReadGeneration:
    def __init__(self, root: Path, descriptor: int):
        self.root = root
        self.descriptor = descriptor

    def files(self) -> Iterator[Path]:
        pending = [()]
        paths = []
        while pending:
            parts = pending.pop()
            directory = _directory_at(self.descriptor, parts)
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        relative = (*parts, entry.name)
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(relative)
                        elif (entry.is_file(follow_symlinks=False)
                              and Path(entry.name).suffix in TEXT_SUFFIXES
                              and not entry.name.startswith('.')):
                            paths.append(self.root.joinpath(*relative))
            finally:
                os.close(directory)
        yield from sorted(paths)

    def open(self, relative: str):
        return open_confined_at(self.descriptor, relative)


@contextmanager
def read_generation(root: Path):
    """Hold the corpus directory across traversal and all descriptor-relative reads."""
    descriptor = _directory(root)
    try:
        yield _ReadGeneration(root, descriptor)
    finally:
        os.close(descriptor)


def iter_files(root: Path) -> Iterator[Path]:
    with read_generation(root) as generation:
        yield from generation.files()


def chunk_text(text: str, *, max_chars: int = MAX_CHUNK_CHARS) -> list[tuple[str, int, str]]:
    """Split ``text`` into ``(heading_path, first_line, body)`` pieces.

    Pieces break at markdown headings and are packed up to ``max_chars``; a single
    oversized paragraph is split on line boundaries, then hard-wrapped.
    """
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 1:
        raise ValueError("max_chars must be positive")
    out: list[tuple[str, int, str]] = []
    stack: list[tuple[int, str]] = []
    buf: list[str] = []
    buf_len = 0
    buf_line = 1

    def crumb() -> str:
        return " > ".join(h for _, h in stack)

    def flush() -> None:
        nonlocal buf, buf_len
        body = "\n".join(buf).strip()
        if body:
            out.append((crumb(), buf_line, body))
        buf, buf_len = [], 0

    fence = None
    for i, line in enumerate(text.splitlines(), start=1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        was_fenced = fence is not None
        if marker:
            run = marker.group(1)
            if fence is None:
                fence = (run[0], len(run))
            elif run[0] == fence[0] and len(run) >= fence[1] and not marker.group(2).strip():
                fence = None
        m = None if was_fenced or marker else _HEADING.match(line)
        if m:
            if buf_len >= MIN_CHUNK_CHARS:
                flush()  # a heading-only stub is carried into the next chunk instead
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2)))
            buf_line = i
        pieces = [line[k : k + max_chars] for k in range(0, len(line), max_chars)] or [""]
        for piece in pieces:
            if buf and buf_len + len(piece) + 1 > max_chars:
                flush()
                buf_line = i
            if not buf:
                buf_line = i
            buf.append(piece)
            buf_len += len(piece) + 1
    flush()
    return _merge_tiny(out, max_chars)


def _merge_tiny(pieces: list[tuple[str, int, str]], max_chars: int = MAX_CHUNK_CHARS) -> list[tuple[str, int, str]]:
    merged: list[tuple[str, int, str]] = []
    for head, line, body in pieces:
        if merged and len(body) < MIN_CHUNK_CHARS and len(merged[-1][2]) + len(body) + 1 <= max_chars:
            ph, pl, pb = merged[-1]
            merged[-1] = (ph, pl, pb + "\n" + body)
        else:
            merged.append((head, line, body))
    return merged


def iter_chunks(root: Path) -> Iterator[Chunk]:
    with read_generation(root) as generation:
        for path in generation.files():
            rel = path.relative_to(root)
            try:
                with generation.open(rel.as_posix()) as stream:
                    text = stream.read()
            except (OSError, ValueError, UnicodeError) as exc:
                raise ValueError("corpus contains an unreadable or unsafe text file") from exc
            kind, source = classify(rel)
            for head, line, body in chunk_text(text):
                yield Chunk(str(rel), source, kind, head or path.stem, line, body)
