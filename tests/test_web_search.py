"""Web index export (mdbx export-web) and the browser search engine's contract."""
import json
import shutil
import subprocess
import sys
from array import array
from pathlib import Path

import pytest

from mdbx import index, search
from mdbx.cli import main
from mdbx.webexport import WebIndex, export, porter, query_terms, tokens, tracked_files

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "search"
BATCH = ROOT / "editors" / "chrome" / "test" / "search-batch.mjs"

QUERIES = ["compound index sort", "shard key chunk", "why is my compound index not used for sort", "private endpoint",
           "vector search numCandidates", "regex anchored", "balancer jumbo chunks", "$in 201 SORT_MERGE",
           "hidden index hideIndex", "scatter gather mongos", "the and of", "zzzznotaword", "index", "sort"]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path):
    """A git repo holding the fixture corpus, plus one untracked 'private' file."""
    if shutil.which("git") is None:
        pytest.skip("git not installed")
    corpus = tmp_path / "corpus"
    shutil.copytree(FIX / "corpus", corpus)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "corpus")
    _git(tmp_path, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "fixture")
    private = corpus / "skills" / "mongodb-expert" / "PRIVATE-notes.md"
    private.write_text("# Private\n\nsecretcustomerword lives only in an untracked file.\n")
    return corpus


def test_untracked_files_never_exported(repo, tmp_path):
    assert "skills/mongodb-expert/PRIVATE-notes.md" not in tracked_files(repo)
    r = export(repo, tmp_path / "web", vectors=False)
    assert r.skipped_untracked == 1
    chunks = (tmp_path / "web" / "chunks.json").read_text()
    assert "secretcustomerword" not in chunks and "PRIVATE-notes" not in chunks
    assert not WebIndex(tmp_path / "web").keyword("secretcustomerword")


def test_refuses_corpus_outside_git(tmp_path):
    plain = tmp_path / "plain"
    shutil.copytree(FIX / "corpus", plain)
    with pytest.raises(RuntimeError, match="not in a git checkout"):
        export(plain, tmp_path / "web")
    assert export(plain, tmp_path / "web2", allow_untracked=True).chunks > 0


def test_keyword_ranking_equals_sqlite_fts5(tmp_path):
    corpus = FIX / "corpus"
    con = index.connect(tmp_path / "x.sqlite")
    index.build_keyword(con, corpus)
    export(corpus, tmp_path / "web", allow_untracked=True, vectors=False)
    wi = WebIndex(tmp_path / "web")
    rows = {r["id"]: (r["path"], r["line"]) for r in con.execute("SELECT id, path, line FROM chunks")}
    for q in QUERIES:
        for kw in ({}, {"kind": "skill"}, {"source": "atlas"}):
            want = [rows[h.id] for h in search.keyword(con, q, 10, **kw)]
            got = [(h.path, h.line) for h in wi.keyword(q, 10, **kw)]
            assert got == want, (q, kw)
            sq = search.keyword(con, q, 10, **kw)
            for a, b in zip(sq, wi.keyword(q, 10, **kw), strict=True):
                assert abs(a.score - b.score) < 1e-6 * max(1.0, abs(a.score))  # same bm25() value


def test_vectors_roundtrip_int8(tmp_path):
    corpus = FIX / "corpus"
    db = tmp_path / "v.sqlite"
    con = index.connect(db)
    index.build_keyword(con, corpus)
    digests = [r[0] for r in con.execute("SELECT DISTINCT digest FROM chunks")]
    vec = array("f", [0.6, -0.8] + [0.0] * 6)
    con.executemany("INSERT INTO vectors VALUES (?,?,?)", [(d, 8, vec.tobytes()) for d in digests])
    con.execute("INSERT OR REPLACE INTO meta VALUES('embed_model','m8')")
    con.commit()
    r = export(corpus, tmp_path / "web", db=db, allow_untracked=True)
    assert r.vectors == len(digests)
    wi = WebIndex(tmp_path / "web")
    assert wi.meta["vectors"] == {"count": len(digests), "dim": 8, "model": "m8", "scale": 127}
    q = [0.6, -0.8] + [0.0] * 6
    hits = wi.semantic_vec(q, 3)
    assert hits and abs(hits[0].score - (76 * 0.6 + 102 * 0.8) / 127) < 1e-9  # round(0.6*127)=76, round(0.8*127)=102


def test_tokenizer_and_stemmer():
    assert tokens("Café SORT_MERGE $match") == ["cafe", "sort_merg", "match"]
    assert porter("agreed") == "agre" and porter("indexes") == "index" and porter("sharding") == "shard"
    assert query_terms("why is the index slow") == ["index", "slow"]
    assert query_terms("the and of") == ["the", "and", "of"]


def test_meta_recipes_and_sources(tmp_path):
    export(FIX / "corpus", tmp_path / "web", allow_untracked=True, vectors=False)
    meta = json.loads((tmp_path / "web" / "meta.json").read_text())
    assert [r["name"] for r in meta["recipes"]] == ["shard-a-collection"]
    assert meta["recipes"][0]["path"] == "recipes/shard-a-collection.md"
    assert {s["source"] for s in meta["sources"]} >= {"mongodb-expert", "mongodb-atlas-expert", "shard-a-collection"}
    assert meta["chunks"] == sum(s["chunks"] for s in meta["sources"])


def test_cli_export_web(repo, tmp_path, capsys):
    assert main(["export-web", str(tmp_path / "out"), "--corpus", str(repo), "--no-vectors"]) == 0
    out = capsys.readouterr().out
    assert "skipped 1 untracked (private) files" in out
    assert (tmp_path / "out" / "postings.bin").is_file() and not (tmp_path / "out" / "vectors.bin").exists()
    untracked = repo.parent / "untracked-corpus"  # inside the fixture repo, never added: nothing may ship
    shutil.copytree(FIX / "corpus", untracked)
    assert main(["export-web", str(tmp_path / "o2"), "--corpus", str(untracked)]) == 2


def test_search_goldens_are_current():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "gen_search_golden.py"), "--check"],
                       check=False, capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_search_matches_python(tmp_path):
    corpus = FIX / "corpus"
    export(corpus, tmp_path / "web", allow_untracked=True, vectors=False)
    wi = WebIndex(tmp_path / "web")
    specs = [{"q": q} for q in QUERIES] + [{"q": q, "kind": "skill"} for q in QUERIES[:5]] + \
        [{"q": "sort", "source": "query-shape"}, {"q": "shard", "kind": "recipe"}]
    r = subprocess.run(["node", str(BATCH), str(tmp_path / "web")], input=json.dumps(specs), capture_output=True,
                       text=True, check=True, timeout=120)
    for spec, got in zip(specs, json.loads(r.stdout), strict=True):
        kw = {k: v for k, v in spec.items() if k != "q"}
        want = [[h.id, h.score] for h in wi.keyword(spec["q"], 10, **kw)]
        assert [g[0] for g in got["keyword"]] == [w[0] for w in want], spec
        assert all(abs(a[1] - b[1]) <= 1e-8 * max(1, abs(b[1])) for a, b in zip(got["keyword"], want, strict=True))
