"""Adversarial, synthetic regression cases for maintenance findings."""
from contextlib import closing
from pathlib import Path

import numpy as np
import pytest

from mdbx import embed, index, search


def database(tmp_path):
    con = index.connect(tmp_path / 'fixture.sqlite')
    con.execute("INSERT INTO chunks VALUES(1,'a.md','a_b','skill','Heading',1,'alpha','old')")
    con.execute("INSERT INTO chunks_fts(rowid,heading,text,source) SELECT id,heading,text,source FROM chunks")
    con.execute("INSERT INTO vectors VALUES('old',2,?)", (np.array([1., 0.], dtype=np.float32).tobytes(),))
    con.execute("INSERT INTO meta VALUES('embed_model','synthetic-a')")
    con.commit()
    return con


def test_failed_keyword_rebuild_preserves_searchable_index(tmp_path, monkeypatch):
    with closing(database(tmp_path)) as con:
        def broken(_):
            raise RuntimeError('synthetic reader failure')
            yield
        monkeypatch.setattr(index.corpusmod, 'iter_chunks', broken)
        with pytest.raises(RuntimeError):
            index.build_keyword(con, tmp_path)
        assert search.keyword(con, 'alpha')[0].text == 'alpha'
        assert con.execute('SELECT COUNT(*) FROM vectors').fetchone()[0] == 1


def test_keyword_limit_counts_unique_complete_content(tmp_path):
    with closing(database(tmp_path)) as con:
        con.execute('DELETE FROM chunks')
        con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('delete-all')")
        common = 'alpha boilerplate ' * 30
        for i in range(12):
            body = common + ('first' if i < 10 else str(i))
            con.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?)', (i + 1, f'{i}.md', 's', 'skill', 'H', 1, body, str(i)))
        con.execute('INSERT INTO chunks_fts(rowid,heading,text,source) SELECT id,heading,text,source FROM chunks')
        hits=search.keyword(con, 'alpha', limit=3)
        assert len(hits) == 3
        assert {h.text for h in hits} == {common+'first', common+'10', common+'11'}
        assert search.keyword(con, 'alpha', limit=0) == []
        with pytest.raises(ValueError, match='limit'):
            search.keyword(con, 'alpha', limit=-1)


def test_model_identity_cache_and_literal_filter(tmp_path, monkeypatch):
    monkeypatch.setattr(embed, 'model', lambda: 'synthetic-a')
    monkeypatch.setattr(embed, 'embed_query', lambda _: np.array([1., 0.], dtype=np.float32))
    with closing(database(tmp_path)) as con:
        store = search.VectorStore(con)
        assert search.semantic(con, 'alpha', source='a_b')
        assert not search.semantic(con, 'alpha', source='a%b')
        con.execute("UPDATE chunks SET digest='new', text='replacement'")
        con.execute("INSERT INTO vectors VALUES('new',2,?)", (np.array([0., 1.], dtype=np.float32).tobytes(),))
        assert search.semantic(con, 'alpha', store=store)[0].score == 0.
        monkeypatch.setattr(embed, 'model', lambda: 'synthetic-b')
        with pytest.raises(embed.EmbedError, match='model'):
            search.semantic(con, 'alpha', store=store)


@pytest.mark.parametrize('bad', [[[float('nan'), 1]], [[0, 0]], [[1, 2], [3, 4]], [1, 2]])
def test_malformed_embeddings_fail_closed(monkeypatch, bad):
    class Client:
        def embed(self, *args, **kwargs):
            return bad
    monkeypatch.setattr(embed, '_client', lambda *args: Client())
    with pytest.raises(embed.EmbedError):
        embed.embed(['synthetic'])


def test_fallback_never_echoes_provider_exception():
    note = search.fallback_note(embed.EmbedError('https://user:synthetic-secret@invalid/\nforged'))
    assert 'synthetic-secret' not in note
    assert '\n' not in note


def test_invalid_batch_and_corrupt_vectors_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(embed, 'model', lambda: 'synthetic-b')
    with closing(database(tmp_path)) as con:
        with pytest.raises(ValueError, match='batch'):
            index.build_semantic(con, batch=0)
        assert con.execute('SELECT COUNT(*) FROM vectors').fetchone()[0] == 1
        con.execute('UPDATE vectors SET vec=?', (np.array([np.nan, 0.], dtype=np.float32).tobytes(),))
        assert len(search.VectorStore(con)) == 0


def test_heading_change_preserves_bytes_but_invalidates_cached_use(tmp_path, monkeypatch):
    from mdbx import corpus
    with closing(database(tmp_path)) as con:
        before = con.execute('SELECT vec FROM vectors').fetchone()[0]
        item = corpus.Chunk('a.md', 's', 'skill', 'Changed', 1, 'alpha')
        # Synthetic digest identity lets this test exercise the historical cache key.
        con.execute('UPDATE chunks SET digest=?', (item.digest,))
        con.execute('UPDATE vectors SET digest=?', (item.digest,))
        con.execute('INSERT INTO vector_inputs VALUES(?,?)', (item.digest, corpus.embedding_input_hash('Heading', 'alpha')))
        con.commit()
        unchanged = corpus.Chunk('a.md', 's', 'skill', 'Heading', 1, 'alpha')
        monkeypatch.setattr(corpus, 'iter_chunks', lambda _: iter([unchanged]))
        index.build_keyword(con, tmp_path)
        assert len(search.VectorStore(con)) == 1
        monkeypatch.setattr(corpus, 'iter_chunks', lambda _: iter([item]))
        index.build_keyword(con, tmp_path)
        assert con.execute('SELECT vec FROM vectors').fetchone()[0] == before
        assert len(search.VectorStore(con)) == 0


def test_corpus_confinement_limits_and_fences(tmp_path):
    from mdbx import corpus
    outside = tmp_path / 'outside.txt'
    outside.write_text('synthetic protected fixture')
    root = tmp_path / 'corpus'
    root.mkdir()
    (root / 'link.md').symlink_to(outside)
    assert list(corpus.iter_chunks(root)) == []
    for maximum in (1, 100, 200, 1600):
        pieces=corpus.chunk_text('# H\n'+'x'*2000,max_chars=maximum)
        assert pieces and all(len(body)<=maximum for _,_,body in pieces)
        assert sum(body.count('x') for _,_,body in pieces)==2000
    for fence in ('~~~', '````'):
        pieces=corpus.chunk_text(f'{fence}\n# literal\n{fence}\n'+'x'*120)
        assert pieces and all(not heading for heading,_,_ in pieces)
        assert '# literal' in '\n'.join(body for _,_,body in pieces)


def test_onnx_cold_initialization_serialized_and_invalid_artifacts_typed(tmp_path):
    import subprocess
    import sys
    script = r"""
import sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS
from mdbx import embed_onnx as module
sessions=[]
def tokenizer(_):
    time.sleep(.02)
    return NS(enable_truncation=lambda **_:None, enable_padding=lambda:None)
def session(*args,**kwargs):
    value=NS(get_inputs=list)
    sessions.append(value)
    return value
sys.modules['tokenizers']=NS(Tokenizer=NS(from_file=tokenizer))
sys.modules['onnxruntime']=NS(InferenceSession=session)
root=Path(sys.argv[1])
module._resolve=lambda **_:(root/'model.onnx',root/'tokenizer.json')
module._clear_runtime()
try:
    with ThreadPoolExecutor(max_workers=2) as pool:
        values=list(pool.map(lambda _:module._locked_runtime(),range(2)))
    assert len(sessions)==1 and values[0] is values[1]
    module._clear_runtime()
    def broken(_):raise ValueError('synthetic invalid tokenizer')
    sys.modules['tokenizers']=NS(Tokenizer=NS(from_file=broken))
    try:module._locked_runtime()
    except module.OnnxUnavailable:pass
    else:raise AssertionError('invalid artifacts accepted')
finally:module._clear_runtime()
"""
    # A blocked initializer is confined to this child, with a real parent deadline.
    result=subprocess.run([sys.executable,'-c',script,str(tmp_path)],capture_output=True,text=True,timeout=5,check=False)
    assert result.returncode==0,result.stderr


def test_web_export_failure_retains_complete_previous_generation(tmp_path, monkeypatch):
    from mdbx import webexport
    root=tmp_path/'corpus'; root.mkdir()
    source=root/'safe.md'; source.write_text('# Synthetic\nalpha text')
    out=tmp_path/'export'
    webexport.export(root,out,vectors=False,allow_untracked=True)
    before={p.name:p.read_bytes() for p in out.iterdir()}
    source.write_text('# Changed\nbeta text')
    real=webexport._write_file
    calls=[]
    def broken(parent,name,data):
        calls.append(name)
        if name=='terms.json':
            assert 'chunks.json' in calls
            raise OSError('synthetic second artifact failure')
        return real(parent,name,data)
    monkeypatch.setattr(webexport,'_write_file',broken)
    with pytest.raises(OSError):webexport.export(root,out,vectors=False,allow_untracked=True)
    assert 'terms.json' in calls
    assert {p.name:p.read_bytes() for p in out.iterdir()} == before


def test_fixture_git_uses_only_owned_empty_configuration():
    import os
    import subprocess
    hooks=Path(os.environ['GIT_CONFIG_VALUE_0'])
    assert os.environ['GIT_CONFIG_KEY_0']=='core.hooksPath'
    assert not list(hooks.iterdir())
    assert Path(os.environ['GIT_CONFIG_GLOBAL']).read_bytes()==b''
    assert Path(os.environ['GIT_CONFIG_SYSTEM']).read_bytes()==b''
    result=subprocess.run(['git','config','--path','--get','core.hooksPath'],capture_output=True,text=True,check=True,timeout=10)
    assert Path(result.stdout.strip())==hooks
