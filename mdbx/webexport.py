"""webexport — package the corpus and its search index for the Chrome extension (`mdbx export-web`).

The extension cannot run SQLite FTS5 or Python, so this module writes the same index as static files
that editors/chrome/lib/textsearch.js loads:

* ``meta.json``     counts, sources (per kind), recipes, embed model, build time
* ``chunks.json``   every chunk (path, source, kind, heading, line, text) in columnar form
* ``terms.json``    the stemmed vocabulary: term -> [document frequency, postings offset]
* ``postings.bin``  little-endian uint32 chunk ids, one run per term, ordered like terms.json
* ``weights.bin``   little-endian uint16 weighted term frequency per posting: 4*heading + text + 2*source
* ``doclen.bin``    little-endian uint32 tokens per chunk (all columns), for BM25 length normalisation
* ``vectors.bin``   optional int8 embeddings (L2-normalised, scaled by 127), one row per unique text

Ranking reproduces the keyword search in ``search.py``: SQLite FTS5's tokenizer
(``porter unicode61 remove_diacritics 2 tokenchars '_'``) and its ``bm25()`` with column weights
heading 4, text 1, source 2, k1 1.2, b 0.75, AND first and OR as the fallback. ``WebIndex`` is the
pure-Python reference over the exported files; the JavaScript port is tested against it.

Only files tracked by git are exported, so private, git-ignored corpus files never ship.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sqlite3
import subprocess
import time
import uuid
from array import array
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from . import corpus as corpusmod
from . import recipes as recipemod
from .safety import _directory, _same_directory, directory_lock, open_confined
from .unicode61 import raw_tokens

#: column weights of bm25(chunks_fts, 4.0, 1.0, 2.0) in search.py (heading, text, source)
W_HEADING, W_TEXT, W_SOURCE = 4, 1, 2
K1, B = 1.2, 0.75
STOPWORDS = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "but", "by", "do", "does", "for", "from", "how", "i", "if", "in",
     "is", "it", "my", "of", "on", "or", "so", "that", "the", "this", "to", "was", "what", "when", "where",
     "which", "why", "with", "you", "your", "can", "not"]
)
PORTER_MAX = 64  # FTS5's porter tokenizer leaves longer tokens unstemmed
FORMAT = 1


# ---- tokenizer: FTS5 unicode61 (remove_diacritics 2, tokenchars '_') + porter

def tokens(text: str) -> list[str]:
    return [porter(t) for t in raw_tokens(text)]


# Porter (1980) stemmer, as in Martin Porter's reference implementation (which FTS5's porter follows).
_V = "aeiou"


def _cons(w: str, i: int) -> bool:
    c = w[i]
    if c in _V:
        return False
    if c == "y":
        return i == 0 or not _cons(w, i - 1)
    return True


def _m(w: str) -> int:
    """Number of VC sequences in w."""
    n, i, ln = 0, 0, len(w)
    while i < ln and _cons(w, i):
        i += 1
    while i < ln:
        while i < ln and not _cons(w, i):
            i += 1
        if i >= ln:
            break
        n += 1
        while i < ln and _cons(w, i):
            i += 1
    return n


def _has_vowel(w: str) -> bool:
    return any(not _cons(w, i) for i in range(len(w)))


def _double_cons(w: str) -> bool:
    return len(w) >= 2 and w[-1] == w[-2] and _cons(w, len(w) - 1)


def _cvc(w: str) -> bool:
    if len(w) < 3:
        return False
    return _cons(w, len(w) - 3) and not _cons(w, len(w) - 2) and _cons(w, len(w) - 1) and w[-1] not in "wxy"


def _replace(w: str, suffix: str, rep: str, cond) -> tuple[str, bool]:
    """If w ends with suffix: (stem+rep if cond(stem) else w, True). Else (w, False)."""
    if w.endswith(suffix):
        stem = w[: len(w) - len(suffix)]
        return (stem + rep if cond(stem) else w), True
    return w, False


_STEP2 = [("ational", "ate"), ("tional", "tion"), ("enci", "ence"), ("anci", "ance"), ("izer", "ize"),
          ("bli", "ble"), ("alli", "al"), ("entli", "ent"), ("eli", "e"), ("ousli", "ous"), ("ization", "ize"),
          ("ation", "ate"), ("ator", "ate"), ("alism", "al"), ("iveness", "ive"), ("fulness", "ful"),
          ("ousness", "ous"), ("aliti", "al"), ("iviti", "ive"), ("biliti", "ble"), ("logi", "log")]
_STEP3 = [("icate", "ic"), ("ative", ""), ("alize", "al"), ("iciti", "ic"), ("ical", "ic"), ("ful", ""),
          ("ness", "")]
_STEP4 = ["al", "ance", "ence", "er", "ic", "able", "ible", "ant", "ement", "ment", "ent", "ion", "ou", "ism",
          "ate", "iti", "ous", "ive", "ize"]


def porter(w: str) -> str:
    if len(w.encode("utf-8")) < 3 or len(w.encode("utf-8")) > PORTER_MAX:  # FTS5 measures tokens in bytes
        return w
    # step 1a
    if w.endswith(("sses", "ies")):
        w = w[:-2]
    elif w.endswith("ss"):
        pass
    elif w.endswith("s"):
        w = w[:-1]
    # step 1b
    extra = False
    if w.endswith("eed"):
        if _m(w[:-3]) > 0:
            w = w[:-1]
    else:
        for suf in ("ed", "ing"):
            if w.endswith(suf) and _has_vowel(w[: -len(suf)]):
                w = w[: -len(suf)]
                extra = True
                break
    if extra:
        if w.endswith(("at", "bl", "iz")):
            w += "e"
        elif _double_cons(w) and w[-1] not in "lsz":
            w = w[:-1]
        elif _m(w) == 1 and _cvc(w):
            w += "e"
    # step 1c
    if w.endswith("y") and _has_vowel(w[:-1]):
        w = w[:-1] + "i"
    # step 2
    for suf, rep in _STEP2:
        w, hit = _replace(w, suf, rep, lambda s: _m(s) > 0)
        if hit:
            break
    # step 3
    for suf, rep in _STEP3:
        w, hit = _replace(w, suf, rep, lambda s: _m(s) > 0)
        if hit:
            break
    # step 4
    for suf in _STEP4:
        if w.endswith(suf):
            stem = w[: len(w) - len(suf)]
            if suf == "ion":
                if _m(stem) > 1 and stem and stem[-1] in "st":
                    w = stem
            elif _m(stem) > 1:
                w = stem
            break
    # step 5a
    if w.endswith("e"):
        stem = w[:-1]
        m = _m(stem)
        if m > 1 or (m == 1 and not _cvc(stem)):
            w = stem
    # step 5b
    if _m(w) > 1 and _double_cons(w) and w.endswith("l"):
        w = w[:-1]
    return w


# ---- query handling (mirrors search._terms)

def query_terms(query: str) -> list[str]:
    """Unicode61 lexemes minus stopwords, then Porter stems; keep all-stopword queries."""
    words = raw_tokens(query)
    kept = [word for word in words if word not in STOPWORDS] or words
    return [porter(word) for word in kept]


# ---- export

def tracked_files(corpus_root: Path) -> set[str] | None:
    """Corpus-relative paths tracked by git, or None when the corpus is not inside a git checkout."""
    try:
        r = subprocess.run(["git", "-C", str(corpus_root), "ls-files", "-z", "--", "."],
                           check=True, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('tracking enumeration timed out; export refused') from exc
    except (OSError, subprocess.CalledProcessError):
        return None
    return {p for p in r.stdout.split("\0") if p}


@dataclass
class ExportResult:
    out: Path
    chunks: int
    terms: int
    postings: int
    vectors: int
    files: int
    skipped_untracked: int


def export(corpus_root: Path, out: Path, *, db: Path | None = None, vectors: bool = True,
           allow_untracked: bool = False) -> ExportResult:
    """Prepare a complete generation before replacing the previous output."""
    corpus_root = Path(corpus_root)
    if not corpus_root.is_dir():
        raise RuntimeError('corpus directory is missing or unavailable')
    source = corpus_root.resolve()
    destination = Path(out).absolute()
    resolved = destination.resolve()
    if source.is_relative_to(resolved) or resolved.is_relative_to(source):
        raise RuntimeError('export destination must not overlap its source corpus')
    if db is not None and Path(db).resolve().is_relative_to(resolved):
        raise RuntimeError('export destination must not contain the input database')
    out = destination
    parent = _directory(out.parent, create=True)
    candidate = '.mdbx-export-' + uuid.uuid4().hex
    backup = '.mdbx-previous-' + uuid.uuid4().hex
    candidate_fd = None
    published = False
    try:
        os.mkdir(candidate, mode=0o700, dir_fd=parent)
        candidate_fd = os.open(candidate, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        result = _export(source, out.parent / candidate, db=db, vectors=vectors, allow_untracked=allow_untracked, directory_fd=candidate_fd)
        os.fsync(candidate_fd)
        with directory_lock(parent, out.name):
            if not _same_directory(parent, out.parent):
                raise RuntimeError('export output parent changed during preparation')
            try:
                info = os.stat(out.name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                info = None
            import stat
            if info is not None and not stat.S_ISDIR(info.st_mode):
                raise RuntimeError('export output must be a regular directory')
            if info is not None:
                os.replace(out.name, backup, src_dir_fd=parent, dst_dir_fd=parent)
            try:
                os.replace(candidate, out.name, src_dir_fd=parent, dst_dir_fd=parent)
                os.fsync(parent)
                if not _same_directory(parent, out.parent):
                    raise RuntimeError('export output parent moved; held directory retains the generation')
                published = True
            except BaseException:
                if info is not None:
                    try:
                        os.stat(out.name, dir_fd=parent, follow_symlinks=False)
                    except FileNotFoundError:
                        os.replace(backup, out.name, src_dir_fd=parent, dst_dir_fd=parent)
                raise
        result.out = out
        return result
    finally:
        try:
            if candidate_fd is not None:
                os.close(candidate_fd)
            shutil.rmtree(candidate, dir_fd=parent, ignore_errors=True)
            if published:
                shutil.rmtree(backup, dir_fd=parent, ignore_errors=True)
        finally:
            os.close(parent)


def _export(corpus_root: Path, out: Path, *, db: Path | None = None, vectors: bool = True,
           allow_untracked: bool = False, directory_fd: int) -> ExportResult:
    """Write the web index for ``corpus_root`` into ``out``. Vectors come from ``db`` (by text digest)."""
    corpus_root = corpus_root.resolve()
    tracked = None if allow_untracked else tracked_files(corpus_root)
    if tracked is None and not allow_untracked:
        raise RuntimeError(f"{corpus_root} is not in a git checkout; refusing to export (private files could "
                           "leak). Pass allow_untracked=True / --allow-untracked for a corpus that is all public.")
    rows, skipped, files = [], 0, set()
    for path in corpusmod.iter_files(corpus_root):
        rel = path.relative_to(corpus_root).as_posix()
        if tracked is not None and rel not in tracked:
            skipped += 1
            continue
        files.add(rel)
        kind, source = corpusmod.classify(Path(rel))
        with open_confined(corpus_root, rel) as stream:
            text = stream.read()
        for head, line, body in corpusmod.chunk_text(text):
            rows.append((rel, source, kind, head or path.stem, line, body))
    if not files and skipped:
        raise RuntimeError(f"all {skipped} corpus files under {corpus_root} are untracked by git; commit them first "
                           "(or pass allow_untracked=True / --allow-untracked if every file may be shared)")

    # inverted index
    postings: dict[str, list[tuple[int, int]]] = {}
    doclen = array("I")
    for i, (_rel, source, _kind, head, _line, body) in enumerate(rows):
        counts: dict[str, int] = {}
        n = 0
        for col, weight in ((head, W_HEADING), (body, W_TEXT), (source, W_SOURCE)):
            toks = tokens(col)
            n += len(toks)
            for t in toks:
                counts[t] = counts.get(t, 0) + weight
        doclen.append(n)
        for t, w in counts.items():
            postings.setdefault(t, []).append((i, min(w, 65535)))
    terms = sorted(postings)
    ids, wts = array("I"), array("H")
    vocab = {}
    for t in terms:
        vocab[t] = [len(postings[t]), len(ids)]
        for i, w in postings[t]:
            ids.append(i)
            wts.append(w)

    # vectors by digest
    digests: list[str] = []
    vec_index: dict[str, int] = {}
    row_vec = []
    vec_bytes = bytearray()
    dim = 0
    model = None
    if vectors and db is not None and Path(db).is_file():
        current_inputs = {}
        for r in rows:
            digest = corpusmod.Chunk(*r).digest
            head, text = r[3], r[5]
            if digest not in current_inputs or head < current_inputs[digest][0]:
                current_inputs[digest] = (head, text)
        expected = {digest: corpusmod.embedding_input_hash(head, text) for digest, (head, text) in current_inputs.items()}
        model, stored = _cached_vectors(Path(db), expected)
        dims = Counter(dm for dm, _ in stored.values())
        dim = dims.most_common(1)[0][0] if dims else 0
        for r in rows:
            d = corpusmod.Chunk(*r).digest
            if d in vec_index:
                row_vec.append(vec_index[d])
                continue
            hit = stored.get(d)
            if hit is None or hit[0] != dim or len(hit[1]) != 4 * dim:
                row_vec.append(-1)
                continue
            vec_index[d] = len(digests)
            digests.append(d)
            row_vec.append(vec_index[d])
            fl = array("f")
            fl.frombytes(hit[1])
            vec_bytes += bytes((max(-127, min(127, round(x * 127))) & 0xFF) for x in fl)
    else:
        row_vec = [-1] * len(rows)

    paths = sorted({r[0] for r in rows})
    sources = sorted({r[1] for r in rows})
    kinds = sorted({r[2] for r in rows})
    pi = {p: i for i, p in enumerate(paths)}
    si = {s: i for i, s in enumerate(sources)}
    ki = {k: i for i, k in enumerate(kinds)}
    chunks_doc = {
        "paths": paths, "sources": sources, "kinds": kinds,
        "rows": [[pi[r[0]], si[r[1]], ki[r[2]], r[4], r[3], r[5], row_vec[i]] for i, r in enumerate(rows)],
    }
    _write_file(directory_fd, 'chunks.json', json.dumps(chunks_doc, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    _write_file(directory_fd, 'terms.json', json.dumps(vocab, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    for name, arr in (("postings.bin", ids), ("weights.bin", wts), ("doclen.bin", doclen)):
        a = array(arr.typecode, arr)
        if a.itemsize > 1 and _big_endian():
            a.byteswap()
        _write_file(directory_fd, name, a.tobytes())
    if digests:
        _write_file(directory_fd, 'vectors.bin', bytes(vec_bytes))

    by_source: dict[tuple[str, str], int] = {}
    for r in rows:
        by_source[(r[2], r[1])] = by_source.get((r[2], r[1]), 0) + 1
    recipes = [
        {"name": rc.name, "title": rc.title, "summary": rc.summary, "applies_to": rc.applies_to,
         "path": rc.path if rc.path in pi else None}
        for rc in recipemod.load(corpus_root)
        if (rc.path in files)
    ]
    meta_doc = {
        "format": FORMAT,
        "mdbx_version": __version__,
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "chunks": len(rows),
        "files": len(files),
        "terms": len(terms),
        "postings": len(ids),
        "total_tokens": int(sum(doclen)),
        "by_kind": {k: sum(1 for r in rows if r[2] == k) for k in kinds},
        "sources": [{"kind": k, "source": s, "chunks": n}
                    for (k, s), n in sorted(by_source.items(), key=lambda kv: (-kv[1], kv[0][1]))],
        "recipes": recipes,
        "vectors": {"count": len(digests), "dim": dim, "model": model, "scale": 127} if digests else None,
        "bm25": {"k1": K1, "b": B, "weights": {"heading": W_HEADING, "text": W_TEXT, "source": W_SOURCE}},
    }
    _write_file(directory_fd, 'meta.json', json.dumps(meta_doc, indent=1, ensure_ascii=False).encode('utf-8'))
    return ExportResult(out, len(rows), len(terms), len(ids), len(digests), len(files), skipped)


def _write_file(directory_fd, name, data):
    fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644, dir_fd=directory_fd)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _cached_vectors(db, expected):
    """Read only relevant, proven inputs from a single read-only generation."""
    con = None
    try:
        con = sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)
        con.execute('BEGIN')
        meta = dict(con.execute('SELECT key,value FROM meta'))
        model = meta.get('embed_model')
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not model or 'vector_inputs' not in tables:
            return model, {}
        stored = {}
        digests = list(expected)
        for offset in range(0, len(digests), 500):
            part = digests[offset:offset + 500]
            marks = ','.join('?' * len(part))
            invalid = ' AND v.digest NOT IN (SELECT digest FROM invalid_vectors)' if 'invalid_vectors' in tables else ''
            sql = f'SELECT v.digest,v.dim,v.vec,vi.input_hash FROM vectors v JOIN vector_inputs vi ON vi.digest=v.digest WHERE v.digest IN ({marks}){invalid}'
            for digest, dim, blob, known in con.execute(sql, part):
                if known != expected[digest] or not isinstance(dim, int) or dim < 1 or not isinstance(blob, bytes) or len(blob) != dim * 4:
                    continue
                vector = array('f', blob)
                if all(math.isfinite(x) for x in vector) and any(vector):
                    norm = math.sqrt(math.fsum(float(x) * x for x in vector))
                    if not math.isclose(norm, 1., rel_tol=1e-5, abs_tol=1e-8):
                        blob = array('f', (x / norm for x in vector)).tobytes()
                    stored[digest] = (dim, blob)
        return model, stored
    except sqlite3.Error as exc:
        raise RuntimeError('vector cache unavailable; export refused') from exc
    finally:
        if con is not None:
            con.close()


def _big_endian() -> bool:
    import sys

    return sys.byteorder == "big"


# ---- reference search over the exported files (the JS port's contract)

@dataclass
class WebHit:
    id: int
    path: str
    source: str
    kind: str
    heading: str
    line: int
    text: str
    score: float
    via: str


class WebIndex:
    def __init__(self, out: Path):
        self.meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
        c = json.loads((out / "chunks.json").read_text(encoding="utf-8"))
        self.paths, self.sources, self.kinds, self.rows = c["paths"], c["sources"], c["kinds"], c["rows"]
        self.vocab = json.loads((out / "terms.json").read_text(encoding="utf-8"))
        self.ids = array("I", (out / "postings.bin").read_bytes())
        self.wts = array("H", (out / "weights.bin").read_bytes())
        self.doclen = array("I", (out / "doclen.bin").read_bytes())
        if _big_endian():
            for a in (self.ids, self.wts, self.doclen):
                a.byteswap()
        self.n = len(self.rows)
        self.avgdl = (self.meta["total_tokens"] / self.n) if self.n else 0.0
        vf = out / "vectors.bin"
        self.vectors = vf.read_bytes() if vf.is_file() else b""
        self.dim = (self.meta.get("vectors") or {}).get("dim", 0)

    def hit(self, i: int, score: float, via: str) -> WebHit:
        r = self.rows[i]
        return WebHit(i, self.paths[r[0]], self.sources[r[1]], self.kinds[r[2]], r[4], r[3], r[5], score, via)

    def _allowed(self, i: int, kind: str | None, source: str | None) -> bool:
        r = self.rows[i]
        if kind and self.kinds[r[2]] != kind:
            return False
        return not (source and source.lower() not in self.sources[r[1]].lower())

    def keyword_ranked(self, query: str, kind: str | None = None, source: str | None = None) -> list[tuple[int, float]]:
        terms = query_terms(query)
        if not terms:
            return []
        uniq = list(dict.fromkeys(terms))
        lists = []
        for t in uniq:
            v = self.vocab.get(t)
            lists.append((t, v))
        for mode in ("AND", "OR"):
            scores: dict[int, float] = {}
            present: dict[int, int] = {}
            for t, v in lists:
                if v is None:
                    continue
                df, off = v
                idf = math.log((self.n - df + 0.5) / (df + 0.5))
                if idf <= 0:
                    idf = 1e-6
                qtf = terms.count(t)  # a repeated query term counts once per occurrence, like repeated phrases
                for j in range(off, off + df):
                    i = self.ids[j]
                    w = self.wts[j]
                    denom = w + K1 * (1 - B + B * self.doclen[i] / self.avgdl)
                    scores[i] = scores.get(i, 0.0) + qtf * idf * (w * (K1 + 1)) / denom
                    present[i] = present.get(i, 0) + 1
            need = len(uniq) if mode == "AND" else 1
            ranked = [(i, s) for i, s in scores.items() if present[i] >= need and self._allowed(i, kind, source)]
            if ranked:
                ranked.sort(key=lambda x: (-x[1], x[0]))
                return ranked
        return []

    def keyword(self, query: str, limit: int = 10, *, kind: str | None = None, source: str | None = None) -> list[WebHit]:
        ranked = self.keyword_ranked(query, kind, source)
        return dedupe([self.hit(i, s, "keyword") for i, s in ranked], limit)

    def semantic_vec(self, qv: list[float], limit: int = 10, *, kind: str | None = None,
                     source: str | None = None) -> list[WebHit]:
        """Rank by dot product of the int8 vectors with an L2-normalised query vector."""
        if not self.vectors:
            return []
        if len(qv) != self.dim or not all(math.isfinite(x) for x in qv):
            raise ValueError("query vector dimension or values invalid")
        dim = self.dim
        best: dict[int, float] = {}
        mv = memoryview(self.vectors).cast("b")
        for i, r in enumerate(self.rows):
            vi = r[6]
            if vi < 0 or not self._allowed(i, kind, source):
                continue
            base = vi * dim
            best[i] = sum(mv[base + k] * qv[k] for k in range(dim)) / 127.0
        ranked = sorted(best.items(), key=lambda x: (-x[1], x[0]))
        return dedupe([self.hit(i, s, "semantic") for i, s in ranked], limit)

    def hybrid_vec(self, query: str, qv: list[float] | None, limit: int = 10, *, kind: str | None = None,
                   source: str | None = None) -> list[WebHit]:
        kw = self.keyword(query, limit * 3, kind=kind, source=source)
        if qv is None:
            return kw[:limit]
        sm = self.semantic_vec(qv, limit * 3, kind=kind, source=source)
        fused: dict[int, WebHit] = {}
        scores: dict[int, float] = {}
        for hits in (kw, sm):
            for rank, h in enumerate(hits, start=1):
                scores[h.id] = scores.get(h.id, 0.0) + 1.0 / (60 + rank)
                if h.id in fused:
                    fused[h.id].via = "keyword+semantic"
                else:
                    fused[h.id] = WebHit(**h.__dict__)
        out = list(fused.values())
        for h in out:
            h.score = scores[h.id]
        out.sort(key=lambda h: (-h.score, h.id))
        return dedupe(out, limit)


def dedupe(hits: list[WebHit], limit: int) -> list[WebHit]:
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
        raise ValueError("limit must be nonnegative")
    if not limit:
        return []
    seen: set[str] = set()
    out = []
    for h in hits:
        key = " ".join(h.text.split())
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
        if len(out) >= limit:
            break
    return out
