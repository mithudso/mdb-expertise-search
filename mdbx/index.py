"""index — build and open the SQLite store (FTS5 keyword index + embedding vectors)."""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

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
    con.execute("DELETE FROM vectors WHERE digest NOT IN (SELECT digest FROM chunks)")
    con.execute("INSERT OR REPLACE INTO meta VALUES('built_at', ?)", (time.strftime("%Y-%m-%d %H:%M:%S"),))
    con.execute("INSERT OR REPLACE INTO meta VALUES('corpus', ?)", (str(root),))
    con.commit()
    say(f"keyword index: {n} chunks")
    return n


def build_semantic(
    con: sqlite3.Connection, say: Progress = lambda _: None, *, batch: int = 24
) -> int:
    """Embed every chunk digest that has no vector yet. Returns number embedded."""
    model = embedmod.model()
    prev = con.execute("SELECT value FROM meta WHERE key = 'embed_model'").fetchone()
    if prev and prev["value"] != model:
        # Vectors from another model live in a different space (and maybe dimension); never mix them.
        log.warning("embed model changed %s -> %s; discarding existing vectors", prev["value"], model)
        say(f"embed model changed ({prev['value']} -> {model}); re-embedding everything")
        con.execute("DELETE FROM vectors")
        con.execute("INSERT OR REPLACE INTO meta VALUES('embed_model', ?)", (model,))
        con.commit()  # recorded now so a failed run does not re-purge vectors already embedded
    todo = con.execute(
        "SELECT digest, MIN(heading) AS h, MIN(text) AS t FROM chunks "
        "WHERE digest NOT IN (SELECT digest FROM vectors) GROUP BY digest"
    ).fetchall()
    total = len(todo)
    say(f"semantic index: {total} chunks to embed with {model}")
    done = 0
    for i in range(0, total, batch):
        part = todo[i : i + batch]
        vecs = embedmod.embed([f"{r['h']}\n{r['t']}"[:2400] for r in part])
        con.executemany(
            "INSERT OR REPLACE INTO vectors(digest, dim, vec) VALUES (?,?,?)",
            [(r["digest"], vecs.shape[1], vecs[j].astype(np.float32).tobytes()) for j, r in enumerate(part)],
        )
        con.commit()
        done += len(part)
        if (i // batch) % 10 == 0 or done == total:
            say(f"  embedded {done}/{total}")
    con.execute("INSERT OR REPLACE INTO meta VALUES('embed_model', ?)", (model,))
    con.commit()
    return done


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
