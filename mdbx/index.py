"""index — build and open the SQLite store (FTS5 keyword index + embedding vectors)."""
from __future__ import annotations

import itertools
import logging
import os
import sqlite3
import tempfile
import time
from collections.abc import Callable
from contextlib import closing, contextmanager
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
CREATE TABLE IF NOT EXISTS store_revision (id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL);
INSERT OR IGNORE INTO store_revision VALUES(1, 0);
"""
for _table in ('chunks', 'vectors', 'vector_inputs', 'invalid_vectors', 'meta'):
    for _event in ('INSERT', 'UPDATE', 'DELETE'):
        SCHEMA += f"CREATE TRIGGER IF NOT EXISTS revision_{_table}_{_event.lower()} AFTER {_event} ON {_table} BEGIN UPDATE store_revision SET value=value+1 WHERE id=1; END;\n"

_snapshots = itertools.count()


@contextmanager
def read_snapshot(con):
    """Use one read generation without committing a caller-owned transaction."""
    name = f'mdbx_snapshot_{next(_snapshots)}'
    con.execute(f'SAVEPOINT {name}')
    try:
        yield
    except BaseException:
        con.execute(f'ROLLBACK TO {name}')
        raise
    finally:
        con.execute(f'RELEASE {name}')

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
    try:
        con.row_factory = sqlite3.Row
        con.executescript(SCHEMA)
    except BaseException:
        con.close()
        raise
    return con


def build_keyword(con: sqlite3.Connection, root: Path, say: Progress = lambda _: None) -> int:
    """Rebuild the chunk table and FTS5 index from ``root``. Returns chunk count."""
    if not root.is_dir():  # a typo'd path would otherwise wipe the index and every embedding
        raise FileNotFoundError(f"corpus directory not found: {root}")
    con.execute("SAVEPOINT keyword_rebuild")
    try:
        con.execute("DELETE FROM chunks")
        # The first write owns the writer lock before cache provenance is read.
        known_inputs = dict(con.execute("SELECT digest, input_hash FROM vector_inputs"))
        cached = {r[0] for r in con.execute("SELECT digest FROM vectors")}
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
            log.warning("no chunks found; index is now empty")
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
    say(f"keyword index: {n} chunks")
    return n


def build_semantic(
    con: sqlite3.Connection, say: Progress = lambda _: None, *, batch: int = 24
) -> int:
    """Build missing, stale or malformed vectors; replace a changed model atomically.

    Validated batches stage on disk. Existing vector bytes stay intact until the
    complete candidate generation and its original input identities are verified.
    Return the number of embedded digests.
    """
    if isinstance(batch, bool) or not isinstance(batch, int) or batch < 1 or batch > 10000:
        raise ValueError("batch must be between 1 and 10000")
    model = embedmod.model()
    with tempfile.TemporaryDirectory(prefix='mdbx-vector-stage-') as tmp, closing(sqlite3.connect(Path(tmp) / 'candidate.sqlite')) as stage:
        stage.execute('PRAGMA cache_size=-2048')
        stage.execute('CREATE TABLE pending(digest TEXT PRIMARY KEY, h TEXT, t TEXT, dim INTEGER, vec BLOB)')
        with read_snapshot(con):
            previous = con.execute("SELECT value FROM meta WHERE key='embed_model'").fetchone()
            vectors = con.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
            if vectors and not previous:
                raise embedmod.EmbedError('indexed vectors have no model identity; explicit migration is required')
            changing = previous is not None and previous[0] != model
            stage.executemany('INSERT INTO pending(digest,h,t) VALUES(?,?,?)', _pending(con, changing))
            dimensions = set()
            if not changing:
                for dim, vec in con.execute('SELECT dim,vec FROM vectors WHERE digest NOT IN (SELECT digest FROM invalid_vectors)'):
                    if _valid_cached(dim, vec):
                        dimensions.add(dim)
        stage.commit()
        total = stage.execute('SELECT COUNT(*) FROM pending').fetchone()[0]
        say(f'semantic index: {total} chunks to embed')
        cursor = stage.execute('SELECT digest,h,t FROM pending ORDER BY digest')
        done = 0
        while part := cursor.fetchmany(batch):
            matrix = embedmod.validate_vectors(embedmod.embed([corpusmod.embedding_input(h, t) for _, h, t in part]), len(part))
            dimensions.add(matrix.shape[1])
            if len(dimensions) > 1:
                raise embedmod.EmbedError('inconsistent embedding dimensions for the active model')
            stage.executemany('UPDATE pending SET dim=?,vec=? WHERE digest=?', ((matrix.shape[1], matrix[j].tobytes(), row[0]) for j, row in enumerate(part)))
            done += len(part)
            say(f'  embedded {done}/{total}')
        stage.commit()
        con.execute('SAVEPOINT semantic_publish')
        try:
            # Obtain the writer lock before rechecking the candidate's generation.
            con.execute('UPDATE store_revision SET value=value WHERE id=1')
            current = con.execute("SELECT value FROM meta WHERE key='embed_model'").fetchone()
            if (current[0] if current else None) != (previous[0] if previous else None):
                raise embedmod.EmbedError('index model changed during embedding; retry')
            expected = stage.execute('SELECT digest,h,t FROM pending ORDER BY digest')
            sentinel = object()
            if any(a != b for a, b in itertools.zip_longest(_pending(con, changing), expected, fillvalue=sentinel)):
                raise embedmod.EmbedError('index contents changed during embedding; retry')
            if changing:
                con.execute('DELETE FROM vectors')
            con.executemany('INSERT OR REPLACE INTO vectors VALUES(?,?,?)', stage.execute('SELECT digest,dim,vec FROM pending'))
            con.executemany('DELETE FROM invalid_vectors WHERE digest=?', stage.execute('SELECT digest FROM pending'))
            con.executemany('INSERT OR REPLACE INTO vector_inputs VALUES(?,?)', ((d, _input_hash(h, t)) for d, h, t in stage.execute('SELECT digest,h,t FROM pending')))
            con.execute("INSERT OR REPLACE INTO meta VALUES('embed_model',?)", (model,))
            con.execute('RELEASE semantic_publish')
        except BaseException:
            con.execute('ROLLBACK TO semantic_publish')
            con.execute('RELEASE semantic_publish')
            raise
        return total


def _valid_cached(dim, blob):
    if not isinstance(dim, int) or dim < 1 or not isinstance(blob, (bytes, bytearray, memoryview)) or len(blob) != 4 * dim:
        return False
    import numpy as np
    vector = np.frombuffer(blob, dtype=np.float32)
    return bool(np.isfinite(vector).all() and np.any(vector))


def _pending(con, changing):
    sql = ('SELECT c.digest,MIN(c.heading),MIN(c.text),v.dim,v.vec,i.digest,vi.input_hash '
           'FROM chunks c LEFT JOIN vectors v ON v.digest=c.digest '
           'LEFT JOIN invalid_vectors i ON i.digest=c.digest '
           'LEFT JOIN vector_inputs vi ON vi.digest=c.digest GROUP BY c.digest ORDER BY c.digest')
    for digest, heading, text, dim, blob, invalid, known in con.execute(sql):
        if changing or invalid is not None or known != _input_hash(heading, text) or not _valid_cached(dim, blob):
            yield digest, heading, text


def stats(con: sqlite3.Connection) -> dict:
    with read_snapshot(con):
        return _stats(con)


def _stats(con: sqlite3.Connection) -> dict:
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
    return corpusmod.embedding_input_hash(heading, text)
