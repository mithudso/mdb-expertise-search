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
    index.build_keyword(con, root)
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
    assert out["indexes"][0]["shell"] == "db.c.createIndex({ a: 1 })"


def test_search_and_show(env):
    hits = m.mdb_search("shard key cardinality", mode="keyword")
    assert hits and hits[0]["source"] == "mongodb-expert"
    assert "shard key" in m.mdb_show(hits[0]["path"], hits[0]["line"], hits[0]["line"] + 3).lower()
    with pytest.raises(ValueError):
        m.mdb_show("../../etc/passwd")


def test_hybrid_degrades_to_keyword(env):
    assert m.mdb_search("lucene analyzer")  # Ollama unreachable -> keyword results


def test_stats_lint_operator(env):
    assert m.mdb_stats()["chunks"] > 0
    out = m.mql_lint("db.c.find({ a: { $gtt: 1 } })")
    assert out[0]["code"] == "unknown-operator" and out[0]["suggestion"] == "$gt"
    assert m.mql_operator("match")["found"] and not m.mql_operator("$nope")["found"]
