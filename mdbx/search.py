"""search — keyword (BM25), semantic (cosine) and hybrid (reciprocal-rank fusion) search."""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, field

import numpy as np

from . import embed as embedmod
from .index import _valid_cached, read_snapshot
from .unicode61 import raw_tokens

log = logging.getLogger("mdbx.search")

RRF_K = 60


@dataclass
class Hit:
    id: int
    path: str
    source: str
    kind: str
    heading: str
    line: int
    text: str
    score: float
    via: str = ""
    snippet: str = field(default="")

    @property
    def location(self) -> str:
        return f"{self.path}:{self.line}"


_STOP = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "but", "by", "do", "does", "for", "from", "how", "i", "if", "in", "is", "it", "my", "of", "on", "or", "so", "that", "the", "this", "to", "was", "what", "when", "where", "which", "why", "with", "you", "your", "can", "not"]
)


def _terms(query: str) -> list[str]:
    """Word tokens of ``query`` minus stopwords; keeps all tokens if nothing else remains."""
    words = raw_tokens(query)
    kept = [w for w in words if w not in _STOP]
    return kept or words


def _fts_query(terms: list[str], op: str) -> str:
    return f" {op} ".join(f'"{t}"' for t in terms)


def _filters(kind: str | None, source: str | None, source_exact: bool = False) -> tuple[str, list]:
    clauses, params = [], []
    if kind:
        clauses.append("c.kind = ?")
        params.append(kind)
    if source and source_exact:
        clauses.append("c.source = ?")
        params.append(source)
    elif source:
        clauses.append("c.source LIKE ? ESCAPE '!'")
        params.append("%" + source.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%")
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


def keyword(
    con: sqlite3.Connection,
    query: str,
    limit: int = 10,
    *,
    kind: str | None = None,
    source: str | None = None,
    source_exact: bool = False,
) -> list[Hit]:
    _limit(limit)
    if limit == 0:
        return []
    terms = _terms(query)
    if not terms:
        return []
    extra, fparams = _filters(kind, source, source_exact)
    sql = (
        "SELECT c.*, bm25(chunks_fts, 4.0, 1.0, 2.0) AS rank, "
        "snippet(chunks_fts, 1, '[', ']', ' … ', 24) AS snip "
        "FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid "
        f"WHERE chunks_fts MATCH ?{extra} ORDER BY rank, c.id"
    )
    for op in ("AND", "OR"):
        with closing(con.execute(sql, [_fts_query(terms, op), *fparams])) as cursor:
            hits = _dedupe(
                (Hit(r["id"], r["path"], r["source"], r["kind"], r["heading"], r["line"], r["text"],
                     -r["rank"], "keyword", r["snip"]) for r in cursor), limit,
            )
        if hits:
            return hits
    return []



class VectorStore:
    """In-memory matrix of chunk vectors, loaded once per process."""

    def __init__(self, con: sqlite3.Connection):
        self._lock = threading.RLock()
        self.refresh(con)

    def refresh(self, con: sqlite3.Connection):
        with self._lock:
            self._refresh(con)

    def _refresh(self, con):
        with read_snapshot(con):
            revision = _revision(con)
            rows = con.execute(
            "SELECT c.id, c.digest, v.dim, v.vec FROM chunks c JOIN vectors v ON v.digest = c.digest WHERE c.digest NOT IN (SELECT digest FROM invalid_vectors) ORDER BY c.id"
            ).fetchall()
        # Skip corrupt blobs and vectors left over from a model with another dimension.
        good = [r for r in rows if _valid_cached(r['dim'], r['vec'])]
        if good:
            dim = Counter(r["dim"] for r in good).most_common(1)[0][0]
            good = [r for r in good if r["dim"] == dim]
        if len(good) != len(rows):
            log.warning("ignored %d inconsistent vector(s); re-run `mdbx index`", len(rows) - len(good))
        rows = good
        ids = np.array([r["id"] for r in rows], dtype=np.int64)
        matrix = (
            np.vstack([_unit_vector(np.frombuffer(r['vec'], dtype=np.float32)) for r in rows])
            if rows
            else np.zeros((0, 0), dtype=np.float32)
        )
        self._state = (revision, ids, matrix)

    @property
    def revision(self):
        return self._state[0]

    @property
    def ids(self):
        return self._state[1]

    @property
    def matrix(self):
        return self._state[2]

    def state_for(self, con):
        with self._lock:
            if self.revision != _revision(con):
                self._refresh(con)
            return self._state

    def __len__(self) -> int:
        return len(self.ids)


def semantic(
    con: sqlite3.Connection,
    query: str,
    limit: int = 10,
    *,
    kind: str | None = None,
    source: str | None = None,
    source_exact: bool = False,
    store: VectorStore | None = None,
) -> list[Hit]:
    _limit(limit)
    if limit == 0:
        return []
    model = embedmod.model()
    with read_snapshot(con):
        store, _ = _ready_store(con, store)
    # The external call does not hold a database snapshot or a writer lock.
    qv = embedmod.embed_query(query)
    if embedmod.model() != model:
        raise embedmod.EmbedError('query model changed during embedding; retry')
    with read_snapshot(con):
        return _semantic_snapshot(con, qv, limit, kind=kind, source=source, source_exact=source_exact, store=store)


def _semantic_snapshot(con, qv, limit, *, kind, source, source_exact, store):
    store, (_, ids, matrix) = _ready_store(con, store)
    if qv.ndim != 1 or not np.isfinite(qv).all() or not np.any(qv):
        raise embedmod.EmbedError("query embedding is invalid")
    if qv.shape[0] != matrix.shape[1]:
        raise embedmod.EmbedError(
            f"query embedding has {qv.shape[0]} dims but the index has {matrix.shape[1]} — "
            "was the embed model changed? re-run `mdbx index`"
        )
    sims = np.clip(matrix @ _unit_vector(qv), -1., 1.)
    order = np.argsort(-sims)
    extra, fparams = _filters(kind, source, source_exact)
    if extra:
        allowed = [r[0] for r in con.execute(f"SELECT c.id FROM chunks c WHERE 1=1{extra}", fparams)]
        order = order[np.isin(ids, allowed)[order]]
    def hits():
        batch = min(500, max(32, limit * 2))
        for offset in range(0, len(order), batch):
            part = order[offset:offset + batch]
            wanted = [int(ids[i]) for i in part]
            marks = ','.join('?' * len(wanted))
            rows = {r['id']: r for r in con.execute(f'SELECT * FROM chunks WHERE id IN ({marks})', wanted)}
            for i in part:
                row = rows.get(int(ids[i]))
                if row is not None:
                    yield Hit(row['id'], row['path'], row['source'], row['kind'], row['heading'], row['line'], row['text'], float(sims[i]), 'semantic', _lead(row['text']))
    return _dedupe(hits(), limit)


def _ready_store(con, store):
    identity = con.execute("SELECT value FROM meta WHERE key='embed_model'").fetchone()
    if identity is None or identity[0] != embedmod.model():
        raise embedmod.EmbedError("index model identity does not match the active model")
    if store is None:
        store = VectorStore(con)
    state = store.state_for(con)
    if not len(state[1]):
        raise embedmod.EmbedError("no vectors indexed — run `mdbx index`")
    return store, state


def _unit_vector(vector):
    wide = np.asarray(vector, dtype=np.float64)
    scaled = wide / np.max(np.abs(wide))
    return (scaled / np.linalg.norm(scaled)).astype(np.float32)


def hybrid(
    con: sqlite3.Connection,
    query: str,
    limit: int = 10,
    *,
    kind: str | None = None,
    source: str | None = None,
    source_exact: bool = False,
    store: VectorStore | None = None,
    notes: list[str] | None = None,
) -> list[Hit]:
    """Fuse keyword and semantic rankings.

    Falls back to keyword when embeddings are unavailable (Ollama down, no vectors indexed, model
    mismatch). The fallback is never silent: it is logged at WARNING and, when the caller passes a
    ``notes`` list, the reason is appended there so the CLI / TUI / MCP surface can show it.
    """
    _limit(limit)
    if limit == 0:
        return []
    candidates = min(10000, limit * 3)
    try:
        model = embedmod.model()
        with read_snapshot(con):
            store, _ = _ready_store(con, store)
        qv = embedmod.embed_query(query)
        if embedmod.model() != model:
            raise embedmod.EmbedError('query model changed during embedding; retry')
        with read_snapshot(con):
            kw = keyword(con, query, candidates, kind=kind, source=source, source_exact=source_exact)
            sm = _semantic_snapshot(con, qv, candidates, kind=kind, source=source, source_exact=source_exact, store=store)
    except embedmod.EmbedError as exc:
        kw = keyword(con, query, candidates, kind=kind, source=source, source_exact=source_exact)
        msg = fallback_note(exc)
        # a caller that passed `notes` will show the message itself; only silent callers get the WARNING
        log.log(logging.INFO if notes is not None else logging.WARNING, "%s", msg)
        if notes is not None:
            notes.append(msg)
        for h in kw[:limit]:
            h.via = "keyword (semantic unavailable)"
        return kw[:limit]
    fused: dict[int, Hit] = {}
    scores: dict[int, float] = {}
    for hits in (kw, sm):
        for rank, h in enumerate(hits, start=1):
            scores[h.id] = scores.get(h.id, 0.0) + 1.0 / (RRF_K + rank)
            if h.id in fused:
                fused[h.id].via = "keyword+semantic"
                if h.via == "keyword":
                    fused[h.id].snippet = h.snippet
            else:
                fused[h.id] = h
    out = []
    for hid, h in fused.items():
        h.score = scores[hid]
        out.append(h)
    out.sort(key=lambda h: -h.score)
    return _dedupe(out, limit)


def fallback_note(exc: Exception) -> str:
    """One line telling the user that semantic search did not run and why."""
    # Never include provider exception text: URLs may contain credentials or forged log lines.
    return "semantic search unavailable (embedding backend or index incompatible); showing keyword results only"


def search(con, query, mode="hybrid", limit=10, *, notes: list[str] | None = None, **kw) -> list[Hit]:
    """Dispatch on ``mode``. ``notes`` (hybrid only) collects the semantic-fallback message, if any.

    In ``semantic`` mode an unreachable embedder raises ``EmbedError`` — there is nothing to fall back to.
    """
    if mode == "hybrid":
        return hybrid(con, query, limit, notes=notes, **kw)
    fn = {"keyword": keyword, "semantic": semantic}[mode]
    return fn(con, query, limit, **kw)


def _lead(text: str, n: int = 220) -> str:
    flat = " ".join(text.split())
    return flat[:n] + (" …" if len(flat) > n else "")


def _dedupe(hits: list[Hit], limit: int) -> list[Hit]:
    _limit(limit)
    if limit == 0:
        return []
    seen: set[str] = set()
    out: list[Hit] = []
    for h in hits:
        key = " ".join(h.text.split())
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
        if len(out) >= limit:
            break
    return out


def _limit(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10000:
        raise ValueError("limit must be between 0 and 10000")


def _revision(con):
    # A persistent revision covers every relevant table mutation across readers,
    # including changes made by other connections. Legacy read-only stores use
    # the conservative connection-specific token until upgraded by connect().
    if con.execute("SELECT 1 FROM sqlite_master WHERE name='store_revision'").fetchone():
        value = con.execute('SELECT value FROM store_revision WHERE id=1').fetchone()[0]
        filename = con.execute('PRAGMA database_list').fetchone()[2]
        if filename:
            info = os.stat(filename)
            return (info.st_dev, info.st_ino, id(con), value, con.total_changes, con.execute('PRAGMA data_version').fetchone()[0])
        return (id(con), value, con.total_changes, con.execute('PRAGMA data_version').fetchone()[0])
    return (id(con), con.total_changes, con.execute('PRAGMA data_version').fetchone()[0])
