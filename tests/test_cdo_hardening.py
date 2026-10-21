"""Regression tests for the code-deep-optimizer hardening pass (embed, index, search, recipes)."""
import io
import logging

import numpy as np
import pytest

from mdbx import embed, index, recipes, search
from tests.test_core import make_corpus


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _urlopen_returning(payload: bytes):
    return lambda req, timeout=None: _Resp(payload)


def test_embed_non_json_body_is_embed_error(monkeypatch, caplog):
    monkeypatch.setattr("urllib.request.urlopen", _urlopen_returning(b"<html>502</html>"))
    with caplog.at_level(logging.WARNING, logger="mdbx.embed"), pytest.raises(embed.EmbedError):
        embed.embed(["x"])
    assert "failed" in caplog.text  # ollama-client folds bad JSON into OllamaUnavailable; shim logs it


def test_embed_ragged_vectors_is_embed_error(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen", _urlopen_returning(b'{"embeddings": [[1.0, 2.0], [1.0]]}')
    )
    with pytest.raises(embed.EmbedError):
        embed.embed(["a", "b"])


def test_embed_unreachable_is_logged(monkeypatch, caplog):
    monkeypatch.setenv("MDBX_OLLAMA_HOST", "http://127.0.0.1:9")
    with caplog.at_level(logging.WARNING, logger="mdbx.embed"), pytest.raises(embed.EmbedError):
        embed.embed(["x"], timeout=1)
    assert "failed" in caplog.text


def test_build_keyword_missing_root_keeps_index(tmp_path):
    con = index.connect(tmp_path / "t.sqlite")
    index.build_keyword(con, make_corpus(tmp_path))
    before = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    with pytest.raises(FileNotFoundError):
        index.build_keyword(con, tmp_path / "typo")
    assert con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == before


def _fake_embed(dim):
    def fake(texts, prefix="search_document: ", timeout=0):
        v = np.zeros((len(texts), dim), dtype=np.float32)
        v[:, 0] = 1
        return v

    return fake


def test_model_change_discards_old_vectors(tmp_path, monkeypatch):
    con = index.connect(tmp_path / "t.sqlite")
    index.build_keyword(con, make_corpus(tmp_path))
    monkeypatch.setattr("mdbx.embed.embed", _fake_embed(2))
    monkeypatch.setenv("MDBX_EMBED_MODEL", "model-a")
    first = index.build_semantic(con)
    assert first > 0
    monkeypatch.setattr("mdbx.embed.embed", _fake_embed(3))
    monkeypatch.setenv("MDBX_EMBED_MODEL", "model-b")
    assert index.build_semantic(con) == first  # everything re-embedded, none mixed
    assert {r["dim"] for r in con.execute("SELECT dim FROM vectors")} == {3}


def test_semantic_query_dim_mismatch_falls_back(tmp_path, monkeypatch):
    con = index.connect(tmp_path / "t.sqlite")
    index.build_keyword(con, make_corpus(tmp_path))
    monkeypatch.setattr("mdbx.embed.embed", _fake_embed(2))
    index.build_semantic(con)
    monkeypatch.setattr("mdbx.embed.embed_query", lambda q: np.ones(5, dtype=np.float32))
    with pytest.raises(embed.EmbedError):
        search.semantic(con, "shard key")
    assert search.hybrid(con, "shard key cardinality")  # keyword fallback


def test_vector_store_ignores_mixed_dims(tmp_path, monkeypatch):
    con = index.connect(tmp_path / "t.sqlite")
    index.build_keyword(con, make_corpus(tmp_path))
    monkeypatch.setattr("mdbx.embed.embed", _fake_embed(2))
    index.build_semantic(con)
    digest = con.execute("SELECT digest FROM vectors LIMIT 1").fetchone()[0]
    con.execute(
        "UPDATE vectors SET dim = 3, vec = ? WHERE digest = ?",
        (np.zeros(3, dtype=np.float32).tobytes(), digest),
    )
    store = search.VectorStore(con)
    good = con.execute(
        "SELECT COUNT(*) FROM chunks c JOIN vectors v ON v.digest = c.digest WHERE v.dim = 2"
    ).fetchone()[0]
    assert store.matrix.shape[1] == 2 and len(store) == good


def test_semantic_filter_not_starved_by_global_top(tmp_path, monkeypatch):
    """A kind filter must rank within the filtered set, not within the global top-N."""
    con = index.connect(tmp_path / "t.sqlite")
    index.build_keyword(con, make_corpus(tmp_path))
    monkeypatch.setattr("mdbx.embed.embed", _fake_embed(2))
    index.build_semantic(con)
    monkeypatch.setattr("mdbx.embed.embed_query", lambda q: np.array([1.0, 0.0], dtype=np.float32))
    hits = search.semantic(con, "anything", 5, kind="llms")
    assert hits and {h.kind for h in hits} == {"llms"}


def test_recipe_text_reads_from_load_root(tmp_path, monkeypatch):
    other = tmp_path / "other"
    (other / "recipes").mkdir(parents=True)
    (other / "recipes" / "r.md").write_text("---\nname: r\ntitle: R\n---\nbody-from-other\n")
    monkeypatch.setenv("MDBX_CORPUS", str(tmp_path / "elsewhere"))
    (item,) = recipes.load(other)
    assert "body-from-other" in item.text
