"""Adversarial, synthetic regression cases for maintenance findings."""
from contextlib import closing

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
        assert len(search.keyword(con, 'alpha', limit=3)) == 3
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
        con.commit()
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
        assert all(len(body) <= maximum for _, _, body in corpus.chunk_text('# H\n' + 'x' * 2000, max_chars=maximum))
    for fence in ('~~~', '````'):
        assert all(not heading for heading, _, _ in corpus.chunk_text(f'{fence}\n# literal\n{fence}\n' + 'x' * 120))


def test_onnx_cold_initialization_serialized_and_invalid_artifacts_typed(tmp_path, monkeypatch):
    import sys
    import time
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace as NS

    from mdbx import embed_onnx as module
    sessions = []
    def tokenizer(_):
        time.sleep(.02)
        return NS(enable_truncation=lambda **_: None, enable_padding=lambda: None)
    def session(*args, **kwargs):
        value = NS(get_inputs=list)
        sessions.append(value)
        return value
    monkeypatch.setitem(sys.modules, 'tokenizers', NS(Tokenizer=NS(from_file=tokenizer)))
    monkeypatch.setitem(sys.modules, 'onnxruntime', NS(InferenceSession=session))
    monkeypatch.setattr(module, '_resolve', lambda **_: (tmp_path / 'model.onnx', tmp_path / 'tokenizer.json'))
    module._clear_runtime()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(module._locked_runtime) for _ in range(2)]
            values = [f.result(timeout=5) for f in futures]
        assert len(sessions) == 1 and values[0] is values[1]
        module._clear_runtime()
        def broken(_):
            raise ValueError('synthetic invalid tokenizer')
        monkeypatch.setitem(sys.modules, 'tokenizers', NS(Tokenizer=NS(from_file=broken)))
        with pytest.raises(module.OnnxUnavailable):
            module._locked_runtime()
    finally:
        module._clear_runtime()


def test_web_export_failure_retains_complete_previous_generation(tmp_path, monkeypatch):
    from mdbx import webexport
    root = tmp_path / 'corpus'
    root.mkdir()
    (root / 'safe.md').write_text('# Synthetic\nalpha text')
    out = tmp_path / 'export'
    webexport.export(root, out, vectors=False, allow_untracked=True)
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    def broken(_):
        raise RuntimeError('synthetic generation failure')
    monkeypatch.setattr(webexport, 'tokens', broken)
    with pytest.raises(RuntimeError):
        webexport.export(root, out, vectors=False, allow_untracked=True)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_fixture_hook_filter_preserves_validation_and_inherits_command_scope(tmp_path, monkeypatch):
    import hashlib
    import os

    from tests import conftest as config
    source = tmp_path / 'original-hooks'
    source.mkdir()
    semantic = b'#!/bin/sh\nprintf synthetic-semantic\n'
    validation = b'#!/bin/sh\nexit 0\n'
    (source / 'post-commit').write_bytes(semantic)
    (source / 'pre-commit').write_bytes(validation)
    monkeypatch.setattr(config, '_ROOT', tmp_path)
    monkeypatch.setattr(config, '_SEMANTIC_HOOK', hashlib.sha256(semantic).hexdigest())
    monkeypatch.setattr(config, '_git', lambda *args: str(source) if args[-1] == 'core.hooksPath' else '')
    # monkeypatch restores only this test process's inherited command-scope environment.
    for key in ('GIT_CONFIG_COUNT', 'GIT_CONFIG_KEY_0', 'GIT_CONFIG_VALUE_0', 'GIT_CONFIG_KEY_1', 'GIT_CONFIG_VALUE_1'):
        monkeypatch.setenv(key, os.environ.get(key, ''))
    monkeypatch.setenv('GIT_CONFIG_COUNT', '0')
    config._pause_semantic_hooks()
    assert not (tmp_path / 'hooks/post-commit').exists()
    assert (tmp_path / 'hooks/pre-commit').read_bytes() == validation
    assert os.environ['GIT_CONFIG_KEY_0'] == 'core.hooksPath'
    assert os.environ['GIT_CONFIG_VALUE_0'] == str(tmp_path / 'hooks')
