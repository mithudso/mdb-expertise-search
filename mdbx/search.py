"""search — keyword (BM25), semantic (cosine) and hybrid (reciprocal-rank fusion) search."""
from __future__ import annotations

import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from . import embed as embedmod

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
    words = re.findall(r"\w+", query)
    kept = [w for w in words if w.lower() not in _STOP]
    return kept or words


def _fts_query(terms: list[str], op: str) -> str:
    return f" {op} ".join(f'"{t}"' for t in terms)


def _filters(kind: str | None, source: str | None) -> tuple[str, list]:
    clauses, params = [], []
    if kind:
        clauses.append("c.kind = ?")
        params.append(kind)
    if source:
        clauses.append("c.source LIKE ?")
        params.append(f"%{source}%")
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


def keyword(
    con: sqlite3.Connection,
    query: str,
    limit: int = 10,
    *,
    kind: str | None = None,
    source: str | None = None,
) -> list[Hit]:
    terms = _terms(query)
    if not terms:
        return []
    extra, fparams = _filters(kind, source)
    sql = (
        "SELECT c.*, bm25(chunks_fts, 4.0, 1.0, 2.0) AS rank, "
        "snippet(chunks_fts, 1, '[', ']', ' … ', 24) AS snip "
        "FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid "
        f"WHERE chunks_fts MATCH ?{extra} ORDER BY rank LIMIT ?"
    )
    rows: list[sqlite3.Row] = []
    for op in ("AND", "OR"):
        rows = con.execute(sql, [_fts_query(terms, op), *fparams, limit * 3]).fetchall()
        if rows:
            break
    return _dedupe(
        [
            Hit(r["id"], r["path"], r["source"], r["kind"], r["heading"], r["line"], r["text"],
                -r["rank"], "keyword", r["snip"])
            for r in rows
        ],
        limit,
    )


class VectorStore:
    """In-memory matrix of chunk vectors, loaded once per process."""

    def __init__(self, con: sqlite3.Connection):
        rows = con.execute(
            "SELECT c.id, v.dim, v.vec FROM chunks c JOIN vectors v ON v.digest = c.digest"
        ).fetchall()
        # Skip corrupt blobs and vectors left over from a model with another dimension.
        good = [r for r in rows if len(r["vec"]) == 4 * r["dim"]]
        if good:
            dim = Counter(r["dim"] for r in good).most_common(1)[0][0]
            good = [r for r in good if r["dim"] == dim]
        if len(good) != len(rows):
            log.warning("ignored %d inconsistent vector(s); re-run `mdbx index`", len(rows) - len(good))
        rows = good
        self.ids = np.array([r["id"] for r in rows], dtype=np.int64)
        self.matrix = (
            np.vstack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
            if rows
            else np.zeros((0, 0), dtype=np.float32)
        )

    def __len__(self) -> int:
        return len(self.ids)


def semantic(
    con: sqlite3.Connection,
    query: str,
    limit: int = 10,
    *,
    kind: str | None = None,
    source: str | None = None,
    store: VectorStore | None = None,
) -> list[Hit]:
    store = store or VectorStore(con)
    if not len(store):
        raise embedmod.EmbedError("no vectors indexed — run `mdbx index`")
    qv = embedmod.embed_query(query)
    if qv.shape[0] != store.matrix.shape[1]:
        raise embedmod.EmbedError(
            f"query embedding has {qv.shape[0]} dims but the index has {store.matrix.shape[1]} — "
            "was the embed model changed? re-run `mdbx index`"
        )
    sims = store.matrix @ qv
    order = np.argsort(-sims)
    extra, fparams = _filters(kind, source)
    if extra:  # restrict before ranking so a filter cannot be starved by unrelated top matches
        allowed = [r[0] for r in con.execute(f"SELECT c.id FROM chunks c WHERE 1=1{extra}", fparams)]
        order = order[np.isin(store.ids, allowed)[order]]
    ranked = [(int(store.ids[i]), float(sims[i])) for i in order[: limit * 3]]
    rows: dict[int, sqlite3.Row] = {}
    for i in range(0, len(ranked), 500):  # stay under SQLite's bound-variable limit
        ids = [rid for rid, _ in ranked[i : i + 500]]
        marks = ",".join("?" * len(ids))
        for row in con.execute(f"SELECT * FROM chunks WHERE id IN ({marks})", ids):
            rows[row["id"]] = row
    hits = [
        Hit(row["id"], row["path"], row["source"], row["kind"], row["heading"], row["line"],
            row["text"], sim, "semantic", _lead(row["text"]))
        for rid, sim in ranked
        if (row := rows.get(rid)) is not None
    ]
    return _dedupe(hits, limit)


def hybrid(
    con: sqlite3.Connection,
    query: str,
    limit: int = 10,
    *,
    kind: str | None = None,
    source: str | None = None,
    store: VectorStore | None = None,
) -> list[Hit]:
    """Fuse keyword and semantic rankings. Falls back to keyword if embeddings are unavailable."""
    kw = keyword(con, query, limit * 3, kind=kind, source=source)
    try:
        sm = semantic(con, query, limit * 3, kind=kind, source=source, store=store)
    except embedmod.EmbedError:
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


def search(con, query, mode="hybrid", limit=10, **kw) -> list[Hit]:
    fn = {"hybrid": hybrid, "keyword": keyword, "semantic": semantic}[mode]
    return fn(con, query, limit, **kw)


def _lead(text: str, n: int = 220) -> str:
    flat = " ".join(text.split())
    return flat[:n] + (" …" if len(flat) > n else "")


def _dedupe(hits: list[Hit], limit: int) -> list[Hit]:
    seen: set[str] = set()
    out: list[Hit] = []
    for h in hits:
        key = " ".join(h.text.split())[:300]
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
        if len(out) >= limit:
            break
    return out
