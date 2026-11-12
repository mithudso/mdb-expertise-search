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
    calls=[]
    class Client:
        def embed(self, texts, **kwargs):
            calls.append(list(texts))
            raise embed.OllamaUnavailable('synthetic malformed JSON response')
    monkeypatch.setattr(embed, '_client', lambda *_: Client())
    with caplog.at_level(logging.WARNING, logger='mdbx.embed'), pytest.raises(embed.EmbedError):
        embed.embed(['x'])
    assert calls == [['search_document: x']] and 'failed' in caplog.text


def test_embed_ragged_vectors_is_embed_error(monkeypatch):
    calls=[]
    class Client:
        def embed(self, texts, **kwargs):
            calls.append(list(texts))
            return [[1.,2.],[1.]]
    monkeypatch.setattr(embed, '_client', lambda *_: Client())
    with pytest.raises(embed.EmbedError, match='malformed'):
        embed.embed(['a','b'])
    assert calls == [['search_document: a','search_document: b']]


def test_embed_unreachable_is_logged(monkeypatch, caplog):
    def down(*args):
        raise embed.OllamaUnavailable('synthetic unavailable provider')
    monkeypatch.setattr(embed, '_client', down)
    with caplog.at_level(logging.WARNING, logger="mdbx.embed"), pytest.raises(embed.EmbedError):
        embed.embed(["x"], timeout=1)
    assert "failed" in caplog.text


def test_build_keyword_missing_root_keeps_index(tmp_path, monkeypatch):
    con=index.connect(tmp_path/'t.sqlite')
    index.build_keyword(con,make_corpus(tmp_path))
    monkeypatch.setattr(embed,'embed',_fake_embed(2))
    index.build_semantic(con)
    before={table: list(map(tuple,con.execute('SELECT * FROM '+table))) for table in ('chunks','vectors','vector_inputs','invalid_vectors','meta')}
    hits=[(h.id,h.text,h.score) for h in search.keyword(con,'shard')]
    with pytest.raises(FileNotFoundError):
        index.build_keyword(con,tmp_path/'typo')
    assert before == {table: list(map(tuple,con.execute('SELECT * FROM '+table))) for table in before}
    assert hits == [(h.id,h.text,h.score) for h in search.keyword(con,'shard')]


def _fake_embed(dim):
    def fake(texts, prefix="search_document: ", timeout=0, **kwargs):
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
    with pytest.raises(embed.EmbedError, match="query embedding has 5 dims but the index has 2"):
        search.semantic(con, "shard key")
    notes = []
    hits = search.hybrid(con, 'shard key cardinality', notes=notes)
    assert hits and all(hit.via == 'keyword (semantic unavailable)' for hit in hits)
    assert len(notes) == 1


def test_vector_store_ignores_mixed_dims(tmp_path, monkeypatch):
    con = index.connect(tmp_path / "t.sqlite")
    index.build_keyword(con, make_corpus(tmp_path))
    monkeypatch.setattr("mdbx.embed.embed", _fake_embed(2))
    index.build_semantic(con)
    digest = con.execute("SELECT digest FROM vectors LIMIT 1").fetchone()[0]
    con.execute(
        "UPDATE vectors SET dim = 3, vec = ? WHERE digest = ?",
        (np.array([1., 0., 0.], dtype=np.float32).tobytes(), digest),
    )
    store = search.VectorStore(con)
    good = con.execute(
        "SELECT COUNT(*) FROM chunks c JOIN vectors v ON v.digest = c.digest WHERE v.dim = 2"
    ).fetchone()[0]
    assert store.matrix.shape[1] == 2 and len(store) == good


def test_semantic_filter_not_starved_by_global_top(tmp_path,monkeypatch):
    import hashlib
    con=index.connect(tmp_path/'t.sqlite')
    monkeypatch.setattr(embed,'model',lambda:'synthetic')
    monkeypatch.setattr(embed,'embed_query',lambda _:np.array([1.,0.],dtype=np.float32))
    for i in range(17):
        body=f'body {i}'
        digest=hashlib.sha1(body.encode()).hexdigest()
        con.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?)',(i+1,f'{i}.md','s','skill' if i<12 else 'llms','H',1,body,digest))
        vector=[1.,0.] if i<12 else [0.,1.]
        con.execute('INSERT INTO vectors VALUES(?,?,?)',(digest,2,np.array(vector,dtype=np.float32).tobytes()))
    con.execute("INSERT INTO meta VALUES('embed_model','synthetic')")
    con.commit()
    assert len(search.semantic(con,'anything',5)) == 5
    hits=search.semantic(con,'anything',5,kind='llms')
    assert {h.id for h in hits} == set(range(13,18))
    assert all(h.kind=='llms' and h.score==0. for h in hits)


def test_recipe_text_reads_from_load_root(tmp_path, monkeypatch):
    other = tmp_path / "other"
    (other / "recipes").mkdir(parents=True)
    (other / "recipes" / "r.md").write_text("---\nname: r\ntitle: R\n---\nbody-from-other\n")
    monkeypatch.setenv("MDBX_CORPUS", str(tmp_path / "elsewhere"))
    (item,) = recipes.load(other)
    assert "body-from-other" in item.text
