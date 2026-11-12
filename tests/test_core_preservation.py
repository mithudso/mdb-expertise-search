"""Synthetic corroboration only; no source changes and no live providers."""
import logging
from contextlib import closing
from types import SimpleNamespace

import numpy as np
import pytest

from mdbx import corpus, embed, embed_onnx, index, search


def seed(tmp_path, monkeypatch):
    root = tmp_path / 'corpus'
    root.mkdir()
    (root / 'a.md').write_text('alpha', encoding='utf-8')
    con = index.connect(tmp_path / 'fixture.sqlite')
    monkeypatch.setattr(embed, 'model', lambda: 'synthetic')
    monkeypatch.setattr(embed, 'embed', lambda texts: np.tile([1., 0.], (len(texts), 1)))
    index.build_keyword(con, root)
    return con, root








def test_unreadable_subtree_is_not_authoritative_empty(tmp_path):
    root = tmp_path / 'corpus'
    child = root / 'skills' / 'demo'
    child.mkdir(parents=True)
    (child / 'safe.md').write_text('alpha', encoding='utf-8')
    child.chmod(0)
    try:
        with pytest.raises((OSError, ValueError)):
            list(corpus.iter_chunks(root))
    finally:
        child.chmod(0o700)




def test_onnx_path_resolution_is_typed(monkeypatch):
    def failed(_):
        raise RuntimeError('synthetic unknown user')
    monkeypatch.setenv('MDBX_ONNX_MODEL', '~synthetic_nonexistent/model')
    monkeypatch.setattr(embed_onnx.Path, 'expanduser', failed)
    with pytest.raises(embed_onnx.OnnxUnavailable):
        embed_onnx._resolve(download=False)


def test_missing_model_diagnostic_does_not_echo_path(tmp_path, monkeypatch):
    marker = 'SYNTHETIC_PRIVATE_MARKER\nFORGED_STATUS'
    monkeypatch.setenv('MDBX_ONNX_MODEL', str(tmp_path / marker))
    with pytest.raises(embed_onnx.OnnxUnavailable) as error:
        embed_onnx._resolve(download=False)
    assert marker not in str(error.value)


def test_keyword_cache_snapshot_after_write_lock(tmp_path, monkeypatch):
    con, root = seed(tmp_path, monkeypatch)
    with closing(con), closing(index.connect(tmp_path / 'fixture.sqlite')) as other:
        class Paused:
            def execute(self, sql, *args):
                if sql == 'SAVEPOINT keyword_rebuild':
                    index.build_semantic(other)
                    (root / 'a.md').rename(root / 'b.md')
                return con.execute(sql, *args)
            def __getattr__(self, name):
                return getattr(con, name)
        index.build_keyword(Paused(), root)
        assert len(search.VectorStore(con)) == 0


def test_index_repair_schedules_malformed_cache(tmp_path, monkeypatch):
    con, root = seed(tmp_path, monkeypatch)
    with closing(con):
        index.build_semantic(con)
        con.execute("UPDATE vectors SET vec=x''")
        con.commit()
        index.build_keyword(con, root)
        assert index.build_semantic(con) == 1
        assert len(search.VectorStore(con)) == 1


def test_connection_closes_on_schema_failure(tmp_path, monkeypatch):
    closed = []
    def fail(_):
        raise OSError('synthetic schema failure')
    con = SimpleNamespace(executescript=fail, close=lambda: closed.append(True))
    monkeypatch.setattr(index.sqlite3, 'connect', lambda _: con)
    with pytest.raises(OSError):
        index.connect(tmp_path / 'fixture.sqlite')
    assert closed == [True]


def test_empty_warning_has_no_raw_controls(tmp_path, caplog):
    root = tmp_path / 'synthetic\x1b[2J'
    root.mkdir()
    with closing(index.connect(tmp_path / 'fixture.sqlite')) as con, caplog.at_level(logging.WARNING, logger='mdbx.index'):
        index.build_keyword(con, root)
    assert '\x1b' not in caplog.text


def test_semantic_batches_bound_python_vector_payload(tmp_path, monkeypatch):
    import tracemalloc
    module=index
    monkeypatch.setattr(embed,'model',lambda:'synthetic-memory-fixture')
    def fake(texts):
        matrix=np.zeros((len(texts),768),dtype=np.float32)
        matrix[:,0]=1.
        return matrix
    monkeypatch.setattr(embed,'embed',fake)
    with closing(module.connect(tmp_path/'synthetic.sqlite')) as con:
        for number in range(4096):
            text=f'synthetic text {number}'
            digest=hashlib.sha1(text.encode()).hexdigest()
            con.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?)',(number+1,f'{number}.md','s','skill','H',1,text,digest))
        con.commit()
        tracemalloc.start()
        try:
            assert module.build_semantic(con,batch=24)==4096
            _,peak=tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        # The fixture generates12MiB of payload; batching must not retain it all
        # as Python bytes until publication. SQLite's bounded native page cache
        # is separate from this Python-allocation regression contract.
        assert peak < 6*1024*1024, f'Python candidate payload peak={peak}'


def test_stats_uses_single_snapshot(tmp_path, monkeypatch):
    con, _root = seed(tmp_path, monkeypatch)
    with closing(con), closing(index.connect(tmp_path / 'fixture.sqlite')) as other:
        con.execute('PRAGMA journal_mode=WAL')
        class Interleaved:
            triggered = False
            def execute(self, sql, *args):
                if sql == 'SELECT key, value FROM meta' and not self.triggered:
                    self.triggered = True
                    other.execute('DELETE FROM chunks')
                    other.commit()
                return con.execute(sql, *args)
            def __getattr__(self, name):
                return getattr(con, name)
        result = index.stats(Interleaved())
        assert (result['chunks'], result['files'], result['sources']) in ((1, 1, 1), (0, 0, 0))

"""Additional synthetic corroboration for collected core gate1 findings."""
import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from mdbx import safety, webexport


def seeded(tmp_path, monkeypatch, count=1):
    monkeypatch.setattr(embed, 'model', lambda: 'synthetic')
    monkeypatch.setattr(embed, 'embed_query', lambda _: np.array([1., 0.], dtype=np.float32))
    con = index.connect(tmp_path / 'fixture.sqlite')
    for n in range(count):
        text = f'alpha body {n}'
        digest = hashlib.sha1(text.encode()).hexdigest()
        con.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?)', (n + 1, f'{n}.md', 'synthetic', 'skill', 'Heading', 1, text, digest))
        con.execute('INSERT INTO vectors VALUES(?,?,?)', (digest, 2, np.array([1., 0.], dtype=np.float32).tobytes()))
    con.execute('INSERT INTO chunks_fts(rowid, heading, text, source) SELECT id, heading, text, source FROM chunks')
    con.execute("INSERT INTO meta VALUES('embed_model','synthetic')")
    con.commit()
    return con


def test_hybrid_accepts_declared_public_limit(tmp_path, monkeypatch):
    with closing(seeded(tmp_path, monkeypatch)) as con:
        assert search.hybrid(con, 'alpha', limit=3334)


def test_semantic_generation_changes_during_query_embedding(tmp_path, monkeypatch):
    with closing(seeded(tmp_path, monkeypatch)) as con, closing(index.connect(tmp_path / 'fixture.sqlite')) as other:
        con.execute('PRAGMA journal_mode=WAL')
        def query(_):
            other.execute("UPDATE chunks SET text='beta', digest='replacement'")
            other.execute("INSERT INTO vectors VALUES('replacement',2,?)", (np.array([0., 1.], dtype=np.float32).tobytes(),))
            other.commit()
            return np.array([1., 0.], dtype=np.float32)
        monkeypatch.setattr(embed, 'embed_query', query)
        hits = search.semantic(con, 'alpha')
        assert hits[0].text == 'beta' and hits[0].score == 0.


def test_semantic_hydration_stops_after_unique_limit(tmp_path, monkeypatch):
    calls = []
    original = search._lead
    monkeypatch.setattr(search, '_lead', lambda text: (calls.append(text), original(text))[1])
    with closing(seeded(tmp_path, monkeypatch, 64)) as con:
        assert len(search.semantic(con, 'alpha', limit=1)) == 1
        assert len(calls) <= 4


def test_refresh_updates_retained_store(tmp_path, monkeypatch):
    with closing(seeded(tmp_path, monkeypatch)) as con:
        store = search.VectorStore(con)
        con.execute("UPDATE vectors SET vec=?", (np.array([0., 1.], dtype=np.float32).tobytes(),))
        con.commit()
        search.semantic(con, 'alpha', store=store)
        assert store.revision == search._revision(con)
        assert np.array_equal(store.matrix[0], [0., 1.])


def test_vector_store_revision_matches_loaded_rows(tmp_path, monkeypatch):
    with closing(seeded(tmp_path, monkeypatch)) as con, closing(index.connect(tmp_path / 'fixture.sqlite')) as other:
        con.execute('PRAGMA journal_mode=WAL')
        class Proxy:
            triggered = False
            def execute(self, sql, *args):
                result = con.execute(sql, *args)
                if sql.startswith('SELECT c.id, c.digest, v.dim, v.vec') and not self.triggered:
                    self.triggered = True
                    rows = result.fetchall()
                    other.execute("UPDATE chunks SET text='beta', digest='replacement'")
                    other.execute("INSERT INTO vectors VALUES('replacement',2,?)", (np.array([0., 1.], dtype=np.float32).tobytes(),))
                    other.commit()
                    class Rows:
                        def fetchall(self):
                            return rows
                    return Rows()
                return result
            def __getattr__(self, name):
                return getattr(con, name)
        reader = Proxy()
        store = search.VectorStore(reader)
        hits = search.semantic(reader, 'alpha', store=store)
        assert hits[0].text == 'beta' and hits[0].score == 0.


def test_export_rejects_source_overlap(tmp_path):
    root = tmp_path / 'corpus'
    root.mkdir()
    source = root / 'safe.md'
    source.write_text('synthetic alpha')
    with pytest.raises((ValueError, RuntimeError)):
        webexport.export(root, root, vectors=False, allow_untracked=True)
    assert source.read_text() == 'synthetic alpha'


def test_export_rejects_destination_containing_database(tmp_path):
    root = tmp_path / 'corpus'
    root.mkdir()
    (root / 'safe.md').write_text('synthetic alpha')
    out = tmp_path / 'published'
    out.mkdir()
    db = out / 'input.sqlite'
    with closing(index.connect(db)):
        pass
    before = db.read_bytes()
    with pytest.raises((ValueError, RuntimeError)):
        webexport.export(root, out, db=db, vectors=False, allow_untracked=True)
    assert db.read_bytes() == before


def test_export_retains_recovery_after_failed_restore(tmp_path, monkeypatch):
    root = tmp_path / 'corpus'
    root.mkdir()
    (root / 'safe.md').write_text('synthetic alpha')
    out = tmp_path / 'published'
    webexport.export(root, out, vectors=False, allow_untracked=True)
    before = (out / 'chunks.json').read_bytes()
    original = os.replace
    def failing(src, dst, *args, **kwargs):
        if Path(src).name.startswith(('.mdbx-export-', '.mdbx-previous-')):
            raise OSError('synthetic publication/restoration failure')
        return original(src, dst, *args, **kwargs)
    monkeypatch.setattr(os, 'replace', failing)
    with pytest.raises(OSError):
        webexport.export(root, out, vectors=False, allow_untracked=True)
    assert any((path / 'chunks.json').read_bytes() == before for path in tmp_path.glob('.mdbx-previous-*'))


def test_export_rejects_missing_source_preserves_previous(tmp_path):
    out = tmp_path / 'published'
    out.mkdir()
    (out / 'prior.txt').write_text('previous generation')
    with pytest.raises((ValueError, RuntimeError, FileNotFoundError)):
        webexport.export(tmp_path / 'missing', out, vectors=False, allow_untracked=True)
    assert (out / 'prior.txt').read_text() == 'previous generation'


def test_export_checks_current_embedding_input(tmp_path, monkeypatch):
    root = tmp_path / 'corpus'
    root.mkdir()
    source = root / 'safe.md'
    source.write_text('# Alpha\n' + 'synthetic alpha text ' * 200)
    monkeypatch.setattr(embed, 'model', lambda: 'synthetic')
    monkeypatch.setattr(embed, 'embed', lambda texts: np.tile([1., 0.], (len(texts), 1)))
    db = tmp_path / 'fixture.sqlite'
    with closing(index.connect(db)) as con:
        index.build_keyword(con, root)
        index.build_semantic(con)
    old = {c.digest: index._input_hash(c.heading, c.text) for c in corpus.iter_chunks(root)}
    source.write_text(source.read_text().replace('Alpha', 'Beta', 1))
    stale = {c.text for c in corpus.iter_chunks(root) if c.digest in old and index._input_hash(c.heading, c.text) != old[c.digest]}
    assert stale
    out = tmp_path / 'published'
    webexport.export(root, out, db=db, allow_untracked=True)
    import json
    rows = json.loads((out / 'chunks.json').read_text())['rows']
    assert all(r[6] == -1 for r in rows if r[5] in stale)


def test_git_tracking_timeout_is_typed(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('synthetic git', 1)
    monkeypatch.setattr(webexport.subprocess, 'run', timeout)
    with pytest.raises(RuntimeError):
        webexport.tracked_files(tmp_path)


def test_atomic_write_parent_swap_cannot_redirect(tmp_path, monkeypatch):
    docs, outside = tmp_path / 'docs', tmp_path / 'outside'
    docs.mkdir()
    outside.mkdir()
    (docs / 'index.json').write_bytes(b'original')
    (outside / 'index.json').write_bytes(b'outside sentinel')
    original = os.open
    swapped = []
    def swap(path, *args, **kwargs):
        if Path(path).name.startswith('.mdbx-') and not swapped:
            docs.rename(tmp_path / 'saved-docs')
            docs.symlink_to(outside, target_is_directory=True)
            swapped.append(True)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(os, 'open', swap)
    try:
        safety.atomic_write(docs / 'index.json', b'rewritten')
    except (ValueError, OSError):
        pass
    assert swapped
    assert (outside / 'index.json').read_bytes() == b'outside sentinel'


def test_atomic_expected_retains_intervening_editor_bytes(tmp_path, monkeypatch):
    target = tmp_path / 'query.mql'
    target.write_bytes(b'original')
    changed = []
    replace, link = os.replace, os.link
    def intercept(fn):
        def publish(src, dst, *args, **kwargs):
            if Path(dst).name == target.name and Path(src).name.startswith('.mdbx-') and not changed:
                target.write_bytes(b'editor change')
                changed.append(True)
            return fn(src, dst, *args, **kwargs)
        return publish
    monkeypatch.setattr(os, 'replace', intercept(replace))
    monkeypatch.setattr(os, 'link', intercept(link))
    try:
        safety.atomic_write(target, b'rewritten', expected=b'original')
    except (ValueError, OSError):
        pass
    assert changed
    assert any(p.is_file() and p.read_bytes() == b'editor change' for p in tmp_path.iterdir())


def test_confined_context_does_not_relabel_caller_error(tmp_path):
    (tmp_path / 'safe.md').write_text('alpha')
    with pytest.raises(BrokenPipeError), safety.open_confined(tmp_path, 'safe.md'):
        raise BrokenPipeError('synthetic caller failure')


def test_range_uses_indexed_unicode_line_boundaries(tmp_path):
    (tmp_path / 'safe.md').write_text('x' * 120 + '\u2028# Needle\n' + 'y' * 120 + '\n')
    assert safety.read_range(tmp_path, 'safe.md', 2, 2) == '# Needle'


def test_confined_deep_path_uses_bounded_descriptors(tmp_path):
    root = tmp_path / 'corpus'
    child = root.joinpath(*(['d'] * 80))
    child.mkdir(parents=True)
    (child / 'safe.md').write_text('synthetic alpha')
    code = "import resource,sys;from pathlib import Path;from mdbx.safety import open_confined;root=Path(sys.argv[1]);rel='/'.join(['d']*80+['safe.md']);resource.setrlimit(resource.RLIMIT_NOFILE,(64,64));assert (root/rel).read_text()=='synthetic alpha';\nwith open_confined(root,rel) as f:assert f.read()=='synthetic alpha'"
    result = subprocess.run([sys.executable, '-c', code, str(root)], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, 'synthetic confined read failed under64-FD limit'


def test_export_reads_only_relevant_vector_payload(tmp_path, monkeypatch):
    root = tmp_path / 'corpus'
    root.mkdir()
    (root / 'safe.md').write_text('synthetic alpha')
    monkeypatch.setattr(embed, 'model', lambda: 'synthetic')
    monkeypatch.setattr(embed, 'embed', lambda texts: np.tile([1., 0.], (len(texts), 1)))
    db = tmp_path / 'fixture.sqlite'
    with closing(index.connect(db)) as con:
        index.build_keyword(con, root)
        index.build_semantic(con)
        con.executemany('INSERT INTO vectors VALUES(?,?,?)', ((f'unrelated-{n}', 2, np.array([0., 1.], dtype=np.float32).tobytes()) for n in range(80)))
        con.commit()
    payload = []
    connect = sqlite3.connect
    class Cursor:
        def __init__(self, value):
            self.value = value
        def __iter__(self):
            for row in self.value:
                payload.extend(len(value) for value in row if isinstance(value, bytes))
                yield row
        def fetchall(self):
            return list(self)
        def __getattr__(self, name):
            return getattr(self.value, name)
    class Connection:
        def __init__(self, value):
            self.value = value
        def execute(self, *args, **kwargs):
            return Cursor(self.value.execute(*args, **kwargs))
        def __getattr__(self, name):
            return getattr(self.value, name)
    monkeypatch.setattr(webexport.sqlite3, 'connect', lambda *args, **kwargs: Connection(connect(*args, **kwargs)))
    result = webexport.export(root, tmp_path / 'published', db=db, allow_untracked=True)
    assert result.vectors == 1
    assert sum(payload) == 8


def test_semantic_cache_still_obeys_cosine_contract(tmp_path, monkeypatch):
    with closing(seeded(tmp_path, monkeypatch)) as con:
        con.execute('UPDATE vectors SET vec=?', (np.array([1e38, 1e38], dtype=np.float32).tobytes(),))
        con.commit()
        hit = search.semantic(con, 'alpha')[0]
        assert 0. <= hit.score <= 1.


def test_semantic_text_blob_is_rejected_as_corrupt(tmp_path, monkeypatch):
    with closing(seeded(tmp_path, monkeypatch)) as con:
        con.execute("UPDATE vectors SET vec='fakefake'")
        con.commit()
        with pytest.raises(embed.EmbedError):
            search.semantic(con, 'alpha')
