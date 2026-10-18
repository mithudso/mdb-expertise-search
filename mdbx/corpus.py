"""corpus — discover corpus files, classify them, and split them into chunks."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

TEXT_SUFFIXES = {".md", ".txt"}
MAX_CHUNK_CHARS = 1600
MIN_CHUNK_CHARS = 120

#: Corpus top-level directory -> human label shown in the CLI and TUI.
KIND_LABELS = {
    "skills": "skill",
    "llms": "llms",
    "recipes": "recipe",
}

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


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


def classify(rel: Path) -> tuple[str, str]:
    """Return ``(kind, source)`` for a corpus-relative path."""
    parts = rel.parts
    if parts[0] == "recipes":
        return "recipe", rel.stem
    if parts[0] == "skills":
        return "skill", parts[1]
    if len(parts) > 1 and parts[1] == "memory-central":
        return "memory", rel.stem.removesuffix("_llms")
    if parts[0] == "llms" and len(parts) > 2:
        return "llms", parts[1].removesuffix(".llms")
    return "llms", rel.stem


def iter_files(root: Path) -> Iterator[Path]:
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix in TEXT_SUFFIXES and not p.name.startswith("."):
            yield p


def chunk_text(text: str, *, max_chars: int = MAX_CHUNK_CHARS) -> list[tuple[str, int, str]]:
    """Split ``text`` into ``(heading_path, first_line, body)`` pieces.

    Pieces break at markdown headings and are packed up to ``max_chars``; a single
    oversized paragraph is split on line boundaries, then hard-wrapped.
    """
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

    in_fence = False
    for i, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
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
            if buf_len + len(piece) + 1 > max_chars and buf_len >= MIN_CHUNK_CHARS:
                flush()
                buf_line = i
            if not buf:
                buf_line = i
            buf.append(piece)
            buf_len += len(piece) + 1
    flush()
    return _merge_tiny(out)


def _merge_tiny(pieces: list[tuple[str, int, str]]) -> list[tuple[str, int, str]]:
    merged: list[tuple[str, int, str]] = []
    for head, line, body in pieces:
        if merged and len(body) < MIN_CHUNK_CHARS and len(merged[-1][2]) + len(body) < MAX_CHUNK_CHARS:
            ph, pl, pb = merged[-1]
            merged[-1] = (ph, pl, pb + "\n" + body)
        else:
            merged.append((head, line, body))
    return merged


def iter_chunks(root: Path) -> Iterator[Chunk]:
    for path in iter_files(root):
        rel = path.relative_to(root)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        kind, source = classify(rel)
        for head, line, body in chunk_text(text):
            yield Chunk(str(rel), source, kind, head or path.stem, line, body)
