import pytest

pytest.importorskip("mcp")

from mdbx import index
from mdbx import mcp_server as m

from .test_core import make_corpus


@pytest.fixture()
def env(tmp_path, monkeypatch):
    root = make_corpus(tmp_path)
    db = tmp_path / "m.sqlite"
    monkeypatch.setenv("MDBX_DB", str(db))
    monkeypatch.setenv("MDBX_CORPUS", str(root))
    monkeypatch.setenv("MDBX_OLLAMA_HOST", "http://127.0.0.1:9")
    con = index.connect(db)
    try:
        index.build_keyword(con, root)
    finally:
        con.close()
    return root


def test_tools_registered():
    import asyncio

    names = {t.name for t in asyncio.run(m.server.list_tools()).tools} if hasattr(
        asyncio.run(m.server.list_tools()), "tools") else {t.name for t in asyncio.run(m.server.list_tools())}
    assert {"mdb_search", "mdb_show", "mdb_stats", "mql_lint", "mql_operator", "mql_optimize"} <= names


def test_mql_optimize_tool():
    out = m.mql_optimize("db.c.find({ $or: [{ a: 1 }, { a: 2 }] })")
    assert out["applied"][0]["code"] == "or-to-in"
    assert "$in" in out["rewritten"]
    assert out["indexes"][0]["shell"] == 'db.getCollection("c").createIndex({ a: 1 })'


def test_search_and_show(env):
    hits = m.mdb_search("shard key cardinality", mode="keyword")
    assert hits and hits[0]["source"] == "mongodb-expert"
    assert "shard key" in m.mdb_show(hits[0]["path"], hits[0]["line"], hits[0]["line"] + 3).lower()
    with pytest.raises(ValueError):
        m.mdb_show("../../etc/passwd")
    outside = env.parent / 'outside.txt'
    outside.write_text('synthetic outside content')
    for path in ['../outside.txt', str(outside)]:
        with pytest.raises(ValueError):
            m.mdb_show(path)


def test_hybrid_degrades_with_missing_vectors(env):
    degraded = m.mdb_search("lucene analyzer")
    assert degraded and all(h["degraded"] is True for h in degraded)
    assert degraded[0]["warning"].startswith("semantic search unavailable (")
    assert degraded[0]["via"] == "keyword (semantic unavailable)"
    assert "degraded" not in m.mdb_search("lucene analyzer", mode="keyword")[0]  # asked for keyword: not degraded
    with pytest.raises(ValueError, match="semantic search unavailable"):
        m.mdb_search("lucene analyzer", mode="semantic")


def test_stats_lint_operator(env):
    assert m.mdb_stats()["chunks"] > 0
    out = m.mql_lint("db.c.find({ a: { $gtt: 1 } })")
    assert out[0]["code"] == "unknown-operator" and out[0]["suggestion"] == "$gt"
    assert m.mql_operator("match")["found"] and not m.mql_operator("$nope")["found"]


def test_review_mcp_count_options_and_empty_degradation(env, monkeypatch):
    out = m.mql_optimize('db.c.countDocuments({}, {limit:1})')
    assert not out['applied'] and out['rewritten'] is None
    def degraded(*args,**kwargs):
        kwargs['notes'].append('semantic search unavailable (http://u:SYNTHETIC_SECRET@localhost:9)')
        return []
    monkeypatch.setattr(m.srch,'search',degraded)
    with pytest.raises(ValueError,match='semantic search unavailable') as exc:
        m.mdb_search('synthetic')
    assert 'SYNTHETIC_SECRET' not in str(exc.value)


def test_review_mcp_semantic_failure_is_sanitized(env, monkeypatch):
    def unavailable(*args,**kwargs):
        raise m.embedmod.EmbedError('http://u:SYNTHETIC_SECRET@localhost:9')
    monkeypatch.setattr(m.srch,'search',unavailable)
    with pytest.raises(ValueError,match='semantic search unavailable') as exc:
        m.mdb_search('synthetic',mode='semantic')
    assert 'SYNTHETIC_SECRET' not in str(exc.value) and exc.value.__suppress_context__


def test_review_mcp_show_validates_range_and_bounds_reads(env):
    with pytest.raises(ValueError):
        m.mdb_show('skills/mongodb-expert/SKILL.md',1,-1)
    path = env / 'huge.md'
    path.write_text('head\n'+'tail\n'*10000)
    assert m.mdb_show('huge.md',1,1) == 'head'
    path.unlink()
    path.symlink_to(env.parent/'outside.txt')
    with pytest.raises(ValueError):
        m.mdb_show('huge.md')


def test_review_mcp_embedding_outage_reaches_mock(env, monkeypatch):
    from contextlib import closing

    import numpy as np
    calls=[]
    monkeypatch.setattr(m.embedmod,'embed',lambda texts,**kw: np.tile([[1.,0.]],(len(texts),1)).astype(np.float32))
    with closing(index.connect()) as con:
        assert index.build_semantic(con)>0
    def unavailable(query,**kw):
        calls.append(query)
        raise m.embedmod.EmbedError('synthetic outage')
    monkeypatch.setattr(m.embedmod,'embed_query',unavailable)
    assert m.mdb_search('lucene analyzer')[0]['degraded']
    assert calls == ['lucene analyzer']
    with pytest.raises(ValueError,match='semantic search unavailable'):
        m.mdb_search('lucene analyzer',mode='semantic')
    assert calls == ['lucene analyzer','lucene analyzer']


def test_review_mcp_show_does_not_consume_unrequested_tail(env,monkeypatch):
    import io
    from contextlib import contextmanager

    from mdbx import safety
    class Budget(io.StringIO):
        used=0
        def readline(self,size=-1):
            text=super().readline(size)
            self.used+=len(text)
            assert self.used<=4096
            return text
    stream=Budget('head\n'+'tail\n'*10000)
    @contextmanager
    def opened(*args):
        yield stream
    monkeypatch.setattr(safety,'open_confined',opened)
    assert m.mdb_show('synthetic.md',1,1)=='head'
    assert stream.used==5
