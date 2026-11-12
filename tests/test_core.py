import json
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
    assert pieces and all(len(b) <= corpus.MAX_CHUNK_CHARS for _, _, b in pieces)
    assert pieces[0][0].startswith("A > B")
    pieces = corpus.chunk_text('# A\n\n## B\n\n' + 'x' * corpus.MAX_CHUNK_CHARS)
    assert pieces and all(len(b) <= corpus.MAX_CHUNK_CHARS for _,_,b in pieces)


def test_keyword_search(tmp_path):
    con = index.connect(tmp_path / "t.sqlite")
    index.build_keyword(con, make_corpus(tmp_path))
    hits = search.keyword(con, "compound index sort")
    assert hits and hits[0].source == "mongodb-expert"
    assert search.keyword(con, "lucene analyzer", kind="llms")[0].source == "demo"
    assert search.keyword(con, "lucene", kind="skill") == []
    assert isinstance(search.keyword(con, "the of"), list)  # all-stopword query must not crash


def test_stopwords_dropped():
    assert search._terms("why is my index not used") == ["index", "used"]
    assert search._terms("the") == ["the"]


def test_hybrid_falls_back_without_vectors(tmp_path, monkeypatch):
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
    monkeypatch.setattr("mdbx.embed.embed_query", lambda q: np.array([1,0],dtype=np.float32))
    assert index.build_semantic(con) > 0
    assert search.keyword(con,'partitioning') == []
    top = search.semantic(con, "partitioning", 3)
    assert "shard" in top[0].text.lower()
    assert index.build_semantic(con) == 0  # resumable: nothing left to embed
    assert isinstance(con, sqlite3.Connection)


def test_cli_search_and_stats(tmp_path, capsys, monkeypatch):
    from mdbx import cli

    db = tmp_path / "c.sqlite"
    root = make_corpus(tmp_path)
    assert cli.main(["--db", str(db), "index", "--corpus", str(root), "--skip-semantic"]) == 0
    capsys.readouterr()
    assert cli.main(["--db", str(db), "search", "-m", "keyword", "--json", "shard key"]) == 0
    hits = json.loads(capsys.readouterr().out)
    assert hits and hits[0]['source'] == 'mongodb-expert'
    assert cli.main(["--db", str(db), "stats", "--json"]) == 0
    stats = json.loads(capsys.readouterr().out)
    assert stats['chunks']>0 and stats['files']==stats['sources']==2 and stats['vectors']==0
    with pytest.raises(SystemExit):
        cli.main(["search"])


def test_missing_vector_fallback_is_signalled(tmp_path, monkeypatch, capsys):
    """A missing semantic index must produce a visible fallback signal."""
    monkeypatch.setenv("MDBX_OLLAMA_HOST", "http://127.0.0.1:9")
    db = tmp_path / "t.sqlite"
    con = index.connect(db)
    index.build_keyword(con, make_corpus(tmp_path))
    notes: list[str] = []
    hits = search.search(con, "shard key cardinality", "hybrid", notes=notes)
    assert hits and all(h.via == "keyword (semantic unavailable)" for h in hits)
    assert len(notes) == 1 and notes[0].startswith("semantic search unavailable (")
    assert "showing keyword results only" in notes[0]
    # keyword mode is what was asked for: no note
    notes.clear()
    assert search.search(con, "shard key", "keyword", notes=notes) and notes == []
    # semantic mode has nothing to fall back to
    with pytest.raises(search.embedmod.EmbedError):
        search.search(con, "shard key", "semantic")
    con.close()

    from mdbx import cli
    assert cli.main(["--db", str(db), "search", "shard", "key"]) == 0
    err = capsys.readouterr().err
    assert "warning: semantic search unavailable" in err
    assert cli.main(["--db", str(db), "search", "-m", "semantic", "shard", "key"]) == 1
    err = capsys.readouterr().err
    assert "error:" in err and "start Ollama" in err
    assert cli.main(["--db", str(db), "search", "-m", "keyword", "shard", "key"]) == 0
    assert "warning" not in capsys.readouterr().err


@pytest.mark.parametrize('command',['search','ask'])
@pytest.mark.parametrize('value',['-1','0','9223372036854775808'])
def test_review_cli_rejects_invalid_limits(command,value):
    from mdbx import cli
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args([command,'-n',value,'synthetic'])
    assert exc.value.code == 2


def test_review_cli_atomic_rewrite_preserves_original(tmp_path,monkeypatch):
    import os

    from mdbx import cli
    path=tmp_path/'q.mql'
    source='db.c.find({$or:[{a:1},{a:2}]})'
    path.write_text(source)
    def fail(*args,**kwargs):
        raise OSError('synthetic replace failure')
    monkeypatch.setattr(os,'replace',fail)
    assert cli.main(['optimize','--write',str(path)]) == 2
    assert path.read_text() == source
    assert list(tmp_path.iterdir()) == [path]


def test_review_cli_connections_close_and_controls_escape(tmp_path,monkeypatch,capsys):
    from mdbx import cli
    con=index.connect(tmp_path/'probe.sqlite')
    monkeypatch.setattr(cli.idx,'connect',lambda _:con)
    assert cli.main(['stats','--json']) == 0
    with pytest.raises(sqlite3.ProgrammingError,match='closed'):
        con.execute('SELECT 1')
    hit=search.Hit(1,'synthetic.md','synthetic','skill','title\x1b[2J',1,'body\x1b[1Gforged',1.)
    cli._print_hit(1,hit,False)
    assert '\x1b' not in capsys.readouterr().out


def test_review_cli_show_replacement_cannot_escape(tmp_path,monkeypatch,capsys):
    from mdbx import cli
    root=tmp_path/'corpus'; root.mkdir()
    inside=root/'a.md'; inside.write_text('inside')
    outside=tmp_path/'outside.txt'; outside.write_text('SYNTHETIC_OUTSIDE_CONTENT')
    real=Path.is_file
    def swap(path):
        result=real(path)
        if path==inside and result:
            inside.unlink(); inside.symlink_to(outside)
        return result
    monkeypatch.setattr(Path,'is_file',swap)
    assert cli.main(['show','a.md','--corpus',str(root)]) in (0,2)
    assert 'SYNTHETIC_OUTSIDE_CONTENT' not in capsys.readouterr().out


def test_review_lint_positions_are_linear(monkeypatch,capsys):
    import importlib
    from types import SimpleNamespace

    from mdbx import cli
    analyzer=importlib.import_module('mdbx.mql.analyze')
    class Meter(str):
        work=0
        def count(self,sub,start=0,end=None):
            end=len(self) if end is None else end
            self.work+=end-start
            return super().count(sub,start,end)
    text=Meter('x\n'*1000)
    diagnostics=[SimpleNamespace(start=i*2,severity='error',code='synthetic',message='bad',fix=None) for i in range(1000)]
    monkeypatch.setattr(cli.sys,'stdin',SimpleNamespace(read=lambda:text))
    monkeypatch.setattr(analyzer,'analyze',lambda _:SimpleNamespace(diagnostics=diagnostics))
    assert cli.main(['lint','-']) == 1
    assert capsys.readouterr().out.splitlines() == [f'-:{i+1}:1: error: bad [synthetic]' for i in range(1000)]
    assert text.work<=4*len(text)
    try:
        from mdbx import mcp_server as m
    except ImportError:
        return
    text.work=0
    monkeypatch.setattr(m,'analyze',lambda _:SimpleNamespace(diagnostics=diagnostics))
    assert m.mql_lint(text)[-1]['line']==1000
    assert text.work<=4*len(text)


def test_review_hybrid_outage_with_synthetic_vectors(tmp_path,monkeypatch,capsys):
    from contextlib import closing
    calls=[]
    monkeypatch.setattr(search.embedmod,'embed',lambda texts,**kw:np.tile([[1.,0.]],(len(texts),1)).astype(np.float32))
    def unavailable(query,**kw):
        calls.append(query)
        raise search.embedmod.EmbedError('synthetic outage')
    monkeypatch.setattr(search.embedmod,'embed_query',unavailable)
    with closing(index.connect(tmp_path/'outage.sqlite')) as con:
        index.build_keyword(con,make_corpus(tmp_path))
        assert index.build_semantic(con)>0
        notes=[]
        hits=search.search(con,'shard key','hybrid',notes=notes)
        assert hits and calls==['shard key'] and notes
        with pytest.raises(search.embedmod.EmbedError,match='synthetic outage'):
            search.search(con,'shard key','semantic')
        assert calls==['shard key','shard key']
    from mdbx import cli
    assert cli.main(['--db',str(tmp_path/'outage.sqlite'),'search','shard','key'])==0
    assert 'warning: semantic search unavailable' in capsys.readouterr().err
    assert cli.main(['--db',str(tmp_path/'outage.sqlite'),'search','-m','semantic','shard','key'])==1
    assert 'error: semantic search unavailable' in capsys.readouterr().err
    assert calls==['shard key']*4
