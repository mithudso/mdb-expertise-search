import sqlite3
from pathlib import Path

import numpy as np
import pytest

from mdbx import corpus, index, search


def make_corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    (root / "skills" / "mongodb-expert").mkdir(parents=True)
    (root / "llms" / "demo.llms").mkdir(parents=True)
    (root / "skills" / "mongodb-expert" / "SKILL.md").write_text(
        "# Indexes\n\n## ESR rule\n\nPut equality fields first, then sort, then range in a compound index "
        "so the planner can avoid a blocking sort stage. " * 3
        + "\n\n## Sharding\n\nPick a shard key with high cardinality and low frequency. " * 3
    )
    (root / "llms" / "demo.llms" / "llms.txt").write_text(
        "# Atlas Search\n\nUse $search with a lucene analyzer for full text queries on Atlas clusters. " * 3
    )
    return root


def test_classify():
    assert corpus.classify(Path("skills/mongodb-expert/SKILL.md")) == ("skill", "mongodb-expert")
    assert corpus.classify(Path("llms/demo.llms/llms.txt")) == ("llms", "demo")
    assert corpus.classify(Path("llms/memory-central/x_llms.md")) == ("memory", "x")


def test_chunk_headings_and_size():
    text = "# A\n\n## B\n\n" + ("word " * 100 + "\n") * 20
    pieces = corpus.chunk_text(text)
    assert pieces and all(len(b) <= corpus.MAX_CHUNK_CHARS + 200 for _, _, b in pieces)
    assert pieces[0][0].startswith("A > B")


def test_keyword_search(tmp_path):
    con = index.connect(tmp_path / "t.sqlite")
    index.build_keyword(con, make_corpus(tmp_path))
    hits = search.keyword(con, "compound index sort")
    assert hits and hits[0].source == "mongodb-expert"
    assert search.keyword(con, "lucene analyzer", kind="llms")[0].source == "demo"
    assert search.keyword(con, "lucene", kind="skill") == []
    assert search.keyword(con, "the of") != [] or True  # all-stopword query must not crash


def test_stopwords_dropped():
    assert search._terms("why is my index not used") == ["index", "used"]
    assert search._terms("the") == ["the"]


def test_hybrid_falls_back_without_ollama(tmp_path, monkeypatch):
    monkeypatch.setenv("MDBX_OLLAMA_HOST", "http://127.0.0.1:9")
    con = index.connect(tmp_path / "t.sqlite")
    index.build_keyword(con, make_corpus(tmp_path))
    assert search.hybrid(con, "shard key cardinality")


def test_semantic_ranking_with_fake_embeddings(tmp_path, monkeypatch):
    con = index.connect(tmp_path / "t.sqlite")
    index.build_keyword(con, make_corpus(tmp_path))

    def fake(texts, prefix="search_document: ", timeout=0):
        v = np.zeros((len(texts), 2), dtype=np.float32)
        for i, t in enumerate(texts):
            v[i] = (1, 0) if "shard" in t.lower() else (0, 1)
        return v

    monkeypatch.setattr("mdbx.embed.embed", fake)
    monkeypatch.setattr("mdbx.embed.embed_query", lambda q: fake([q])[0])
    assert index.build_semantic(con) > 0
    top = search.semantic(con, "shard partitioning", 3)
    assert "shard" in top[0].text.lower()
    assert index.build_semantic(con) == 0  # resumable: nothing left to embed
    assert isinstance(con, sqlite3.Connection)


def test_cli_search_and_stats(tmp_path, capsys, monkeypatch):
    from mdbx import cli

    db = tmp_path / "c.sqlite"
    root = make_corpus(tmp_path)
    assert cli.main(["--db", str(db), "index", "--corpus", str(root), "--skip-semantic"]) == 0
    assert cli.main(["--db", str(db), "search", "-m", "keyword", "--json", "shard key"]) == 0
    assert '"source": "mongodb-expert"' in capsys.readouterr().out
    assert cli.main(["--db", str(db), "stats", "--json"]) == 0
    with pytest.raises(SystemExit):
        cli.main(["search"])
