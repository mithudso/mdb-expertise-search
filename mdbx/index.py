"""index — build and open the SQLite store (FTS5 keyword index + embedding vectors)."""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

from . import corpus as corpusmod
from . import embed as embedmod

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY,
  path TEXT NOT NULL,
  source TEXT NOT NULL,
  kind TEXT NOT NULL,
  heading TEXT NOT NULL,
  line INTEGER NOT NULL,
  text TEXT NOT NULL,
  digest TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_digest ON chunks(digest);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  heading, text, source,
  content='chunks', content_rowid='id',
  tokenize="porter unicode61 remove_diacritics 2 tokenchars '_'"
);
CREATE TABLE IF NOT EXISTS vectors (
  digest TEXT PRIMARY KEY,
  dim INTEGER NOT NULL,
  vec BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS vector_inputs (digest TEXT PRIMARY KEY, input_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS invalid_vectors (digest TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

log = logging.getLogger("mdbx.index")

Progress = Callable[[str], None]


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_corpus() -> Path:
    return Path(os.environ.get("MDBX_CORPUS", repo_root() / "corpus"))


def default_db() -> Path:
    return Path(os.environ.get("MDBX_DB", repo_root() / "data" / "mdbx.sqlite"))


def connect(db: Path | None = None) -> sqlite3.Connection:
    db = db or default_db()
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def build_keyword(con: sqlite3.Connection, root: Path, say: Progress = lambda _: None) -> int:
    """Rebuild the chunk table and FTS5 index from ``root``. Returns chunk count."""
    if not root.is_dir():  # a typo'd path would otherwise wipe the index and every embedding
        raise FileNotFoundError(f"corpus directory not found: {root}")
    known_inputs = dict(con.execute("SELECT digest, input_hash FROM vector_inputs"))
    cached = {r[0] for r in con.execute("SELECT digest FROM vectors")}
    con.execute("SAVEPOINT keyword_rebuild")
    try:
        con.execute("DELETE FROM chunks")
        con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('delete-all')")
        rows = (
            (c.path, c.source, c.kind, c.heading, c.line, c.text, c.digest)
            for c in corpusmod.iter_chunks(root)
        )
        con.executemany(
            "INSERT INTO chunks(path, source, kind, heading, line, text, digest) VALUES (?,?,?,?,?,?,?)",
            rows,
        )
        con.execute(
            "INSERT INTO chunks_fts(rowid, heading, text, source) "
            "SELECT id, heading, text, source FROM chunks"
        )
        n = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if n == 0:
            log.warning("no chunks found under %s; index is now empty", root)
        for digest, heading, text in con.execute("SELECT digest, MIN(heading), MIN(text) FROM chunks GROUP BY digest"):
            if digest in cached and known_inputs.get(digest) != _input_hash(heading, text):
                con.execute("INSERT OR IGNORE INTO invalid_vectors VALUES(?)", (digest,))
        con.execute("INSERT OR REPLACE INTO meta VALUES('built_at', ?)", (time.strftime("%Y-%m-%d %H:%M:%S"),))
        con.execute("INSERT OR REPLACE INTO meta VALUES('corpus', ?)", (str(root),))
        con.execute("RELEASE keyword_rebuild")
    except BaseException:
        con.execute("ROLLBACK TO keyword_rebuild")
        con.execute("RELEASE keyword_rebuild")
        raise
    con.commit()
    say(f"keyword index: {n} chunks")
    return n


def build_semantic(
    con: sqlite3.Connection, say: Progress = lambda _: None, *, batch: int = 24
) -> int:
    """Embed every chunk digest that has no vector yet. Returns number embedded."""
    if isinstance(batch, bool) or not isinstance(batch, int) or batch < 1 or batch > 10000:
        raise ValueError("batch must be between 1 and 10000")
    model = embedmod.model()
    previous = con.execute("SELECT value FROM meta WHERE key='embed_model'").fetchone()
    vectors = con.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
    if vectors and not previous:
        raise embedmod.EmbedError("indexed vectors have no model identity; explicit migration is required")
    changing = previous is not None and previous[0] != model
    # Keep the old generation intact until every replacement vector has been validated.
    todo = con.execute(
        "SELECT digest, MIN(heading) AS h, MIN(text) AS t FROM chunks "
        + ("" if changing else "WHERE (digest NOT IN (SELECT digest FROM vectors) OR digest IN (SELECT digest FROM invalid_vectors)) ")
        + "GROUP BY digest"
    ).fetchall()
    total = len(todo)
    say(f"semantic index: {total} chunks to embed")
    expected = tuple((r['digest'], r['h'], r['t']) for r in todo)
    prepared = []
    dimensions = set() if changing else {r[0] for r in con.execute("SELECT DISTINCT dim FROM vectors WHERE digest NOT IN (SELECT digest FROM invalid_vectors)")}
    for i in range(0, total, batch):
        part = todo[i:i + batch]
        matrix = embedmod.validate_vectors(embedmod.embed([f"{r['h']}\n{r['t']}"[:2400] for r in part]), len(part))
        dimensions.add(matrix.shape[1])
        if len(dimensions) > 1:
            raise embedmod.EmbedError("inconsistent embedding dimensions for the active model")
        prepared.extend((r['digest'], matrix.shape[1], matrix[j].tobytes()) for j, r in enumerate(part))
        say(f"  embedded {min(i + batch, total)}/{total}")
    con.execute("SAVEPOINT semantic_publish")
    try:
        current = con.execute("SELECT value FROM meta WHERE key='embed_model'").fetchone()
        if (current[0] if current else None) != (previous[0] if previous else None):
            raise embedmod.EmbedError("index model changed during embedding; retry")
        now = con.execute(
            "SELECT digest, MIN(heading) AS h, MIN(text) AS t FROM chunks "
            + ("" if changing else "WHERE (digest NOT IN (SELECT digest FROM vectors) OR digest IN (SELECT digest FROM invalid_vectors)) ")
            + "GROUP BY digest"
        ).fetchall()
        if tuple(tuple(r) for r in now) != expected:
            raise embedmod.EmbedError("index contents changed during embedding; retry")
        if changing:
            con.execute("DELETE FROM vectors")
        con.executemany("INSERT OR REPLACE INTO vectors VALUES(?,?,?)", prepared)
        con.executemany("DELETE FROM invalid_vectors WHERE digest=?", [(r[0],) for r in prepared])
        con.executemany("INSERT OR REPLACE INTO vector_inputs VALUES(?,?)", [(r[0], _input_hash(r[1], r[2])) for r in expected])
        con.execute("INSERT OR REPLACE INTO meta VALUES('embed_model', ?)", (model,))
        con.execute("RELEASE semantic_publish")
    except BaseException:
        con.execute("ROLLBACK TO semantic_publish")
        con.execute("RELEASE semantic_publish")
        raise
    con.commit()
    return total


def stats(con: sqlite3.Connection) -> dict:
    by_kind = {
        r["kind"]: r["n"]
        for r in con.execute("SELECT kind, COUNT(*) n FROM chunks GROUP BY kind")
    }
    meta = {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM meta")}
    return {
        "chunks": sum(by_kind.values()),
        "by_kind": by_kind,
        "sources": con.execute("SELECT COUNT(DISTINCT source) FROM chunks").fetchone()[0],
        "files": con.execute("SELECT COUNT(DISTINCT path) FROM chunks").fetchone()[0],
        "vectors": con.execute("SELECT COUNT(*) FROM vectors").fetchone()[0],
        **meta,
    }


def _input_hash(heading: str, text: str) -> str:
    return hashlib.sha256(f"{heading}\n{text}"[:2400].encode("utf-8")).hexdigest()
