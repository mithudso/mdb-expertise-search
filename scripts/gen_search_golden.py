#!/usr/bin/env python3
"""Build the search fixture index and the reference results the Chrome extension's search is tested against.

From tests/fixtures/search/corpus/ this writes:
* tests/fixtures/search/index/  — the exported web index (``mdbx export-web`` format), with deterministic
  fake 32-dimension embeddings so semantic and hybrid ranking can be checked without Ollama;
* tests/fixtures/search/golden.json — keyword / semantic / hybrid results of the Python reference
  (``mdbx.webexport.WebIndex``) for a fixed list of queries and filters.

    python scripts/gen_search_golden.py           # regenerate
    python scripts/gen_search_golden.py --check   # exit 1 when anything is stale
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mdbx import corpus as corpusmod
from mdbx import index as idx
from mdbx.webexport import WebIndex, export

FIX = ROOT / "tests" / "fixtures" / "search"
DIM = 32
QUERIES = [
    {"q": "compound index sort"},
    {"q": "shard key chunk"},
    {"q": "why is my compound index not used for sort"},
    {"q": "private endpoint"},
    {"q": "vector search numCandidates recall"},
    {"q": "regex anchored index bounds"},
    {"q": "balancer jumbo chunks", "kind": "skill"},
    {"q": "sort", "source": "query-shape"},
    {"q": "shard", "kind": "recipe"},
    {"q": "the and of"},
    {"q": "zzzznotaword"},
    {"q": "$in 201 SORT_MERGE"},
    {"q": "hidden index hideIndex"},
    {"q": "scatter gather mongos shard"},
]


def fake_vec(text: str) -> list[float]:
    """Deterministic pseudo-embedding: hashed bag of stemmed tokens, L2-normalised."""
    from mdbx.webexport import tokens

    v = [0.0] * DIM
    for t in tokens(text):
        h = hashlib.sha1(t.encode()).digest()
        v[h[0] % DIM] += 1.0 + h[1] / 255.0
        v[h[2] % DIM] -= 0.5
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def build(out_index: Path) -> dict:
    corpus_root = FIX / "corpus"
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "fx.sqlite"
        con = idx.connect(db)
        idx.build_keyword(con, corpus_root)
        import array

        for c in corpusmod.iter_chunks(corpus_root):
            vec = array.array("f", fake_vec(f"{c.heading}\n{c.text}"))
            con.execute("INSERT OR REPLACE INTO vectors(digest, dim, vec) VALUES (?,?,?)",
                        (c.digest, DIM, vec.tobytes()))
        con.execute("INSERT OR REPLACE INTO meta VALUES('embed_model', 'fake-hash-32')")
        con.commit()
        con.close()
        if out_index.exists():
            shutil.rmtree(out_index)
        export(corpus_root, out_index, db=db, allow_untracked=True)
    meta = json.loads((out_index / "meta.json").read_text())
    meta["built_at"] = meta["mdbx_version"] = "fixture"  # keep the committed fixture stable across builds/releases
    (out_index / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    wi = WebIndex(out_index)

    def dump(hits):
        return [{"id": h.id, "path": h.path, "line": h.line, "source": h.source, "kind": h.kind,
                 "score": round(h.score, 9), "via": h.via} for h in hits]

    results = []
    for spec in QUERIES:
        q, kw = spec["q"], {k: v for k, v in spec.items() if k != "q"}
        qv = fake_vec(q)
        results.append({
            "query": spec,
            "qvec": qv,
            "keyword": dump(wi.keyword(q, 10, **kw)),
            "semantic": dump(wi.semantic_vec(qv, 10, **kw)),
            "hybrid": dump(wi.hybrid_vec(q, qv, 10, **kw)),
        })
    return {"dim": DIM, "results": results}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_index = Path(tmp) / "index"
            want = json.dumps(build(tmp_index), indent=1) + "\n"
            stale = []
            if (FIX / "golden.json").read_text() != want:
                stale.append("golden.json")
            for f in sorted(tmp_index.iterdir()):
                cur = FIX / "index" / f.name
                if not cur.is_file() or cur.read_bytes() != f.read_bytes():
                    stale.append(f"index/{f.name}")
        if stale:
            print("stale search fixtures (run scripts/gen_search_golden.py):", ", ".join(stale))
            return 1
        return 0
    data = build(FIX / "index")
    (FIX / "golden.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {FIX / 'golden.json'} ({len(data['results'])} queries) and {FIX / 'index'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
