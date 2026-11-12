"""Adversarial synthetic checks for focused repairs after the two blind gates."""
import builtins
import errno
import importlib.util
import json
import os
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from mdbx import embed, embed_onnx, index, safety, search, webexport

SOURCE = Path(__file__).resolve().parents[1]


def script(name):
    before = sys.path[:]
    spec = importlib.util.spec_from_file_location('postgate_' + name, SOURCE / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    try:
        sys.path.insert(0, str(SOURCE / 'scripts'))
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = before
    return module


def seed(tmp_path, monkeypatch):
    root = tmp_path / 'corpus'; root.mkdir()
    for n in range(3):
        (root / f'{n}.md').write_text(f'alpha synthetic unique {n}')
    monkeypatch.setattr(embed, 'model', lambda: 'synthetic-model')
    monkeypatch.setattr(embed, 'embed', lambda texts, **kw: np.tile([1., 0.], (len(texts), 1)))
    monkeypatch.setattr(embed, 'embed_query', lambda text: np.array([1., 0.]))
    con = index.connect(tmp_path / 'test.sqlite')
    index.build_keyword(con, root); index.build_semantic(con)
    return con, root


def test_hybrid_uses_one_generation_after_embedding(tmp_path, monkeypatch):
    con, _ = seed(tmp_path, monkeypatch)
    with closing(con), closing(index.connect(tmp_path / 'test.sqlite')) as other:
        con.execute('PRAGMA journal_mode=WAL')
        def query(text):
            other.execute("UPDATE chunks SET text='beta replacement', path='new.md', digest='replacement'")
            other.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('delete-all')")
            other.execute('INSERT INTO chunks_fts(rowid,heading,text,source) SELECT id,heading,text,source FROM chunks')
            other.execute("INSERT INTO vectors VALUES('replacement',2,?)", (np.array([0.,1.], dtype=np.float32).tobytes(),))
            other.commit()
            return np.array([1., 0.])
        monkeypatch.setattr(embed, 'embed_query', query)
        hits = search.hybrid(con, 'alpha')
        assert hits and all(hit.path == 'new.md' and hit.text == 'beta replacement' for hit in hits)


def test_vector_cache_does_not_reuse_rolled_back_revision(tmp_path, monkeypatch):
    con, _ = seed(tmp_path, monkeypatch)
    with closing(con):
        store = search.VectorStore(con)
        con.execute('BEGIN')
        con.execute('UPDATE vectors SET vec=?', (np.array([0.,1.], dtype=np.float32).tobytes(),))
        assert all(hit.score == 0 for hit in search.semantic(con, 'alpha', store=store))
        con.rollback()
        con.execute('UPDATE vectors SET vec=?', (np.array([-1.,0.], dtype=np.float32).tobytes(),))
        con.commit()
        assert all(hit.score == -1 for hit in search.semantic(con, 'alpha', store=store))


def test_mixed_dimensions_reindex_repairs_current_rows(tmp_path, monkeypatch):
    con, root = seed(tmp_path, monkeypatch)
    with closing(con):
        digest = con.execute('SELECT digest FROM vectors LIMIT 1').fetchone()[0]
        con.execute('UPDATE vectors SET dim=3,vec=? WHERE digest=?', (np.array([1.,0.,0.], dtype=np.float32).tobytes(),digest))
        con.execute("INSERT INTO vectors VALUES('unreferenced',7,?)", (np.ones(7,dtype=np.float32).tobytes(),))
        con.commit(); index.build_keyword(con, root)
        assert index.build_semantic(con) == 1
        assert {row[0] for row in con.execute('SELECT v.dim FROM vectors v JOIN chunks c ON c.digest=v.digest')} == {2}


def test_legacy_mixed_dimensions_stage_full_generation(tmp_path, monkeypatch):
    con, root = seed(tmp_path, monkeypatch)
    with closing(con):
        con.execute("DELETE FROM meta WHERE key='embed_dim'")
        con.execute('UPDATE vectors SET dim=3,vec=? WHERE digest=(SELECT digest FROM vectors LIMIT 1)', (np.array([1.,0.,0.],dtype=np.float32).tobytes(),))
        con.commit(); index.build_keyword(con, root)
        assert index.build_semantic(con) == 3


def test_model_change_aborts_complete_generation(tmp_path, monkeypatch):
    con, _ = seed(tmp_path, monkeypatch)
    with closing(con):
        before = list(con.execute('SELECT digest,dim,vec FROM vectors ORDER BY digest'))
        model = ['synthetic-new-a']
        monkeypatch.setattr(embed, 'model', lambda: model[0])
        def progress(message):
            if 'embedded 1/' in message:
                model[0] = 'synthetic-new-b'
        with pytest.raises(embed.EmbedError, match='model changed'):
            index.build_semantic(con, say=progress, batch=1)
        assert list(con.execute('SELECT digest,dim,vec FROM vectors ORDER BY digest')) == before


def test_explicit_embedding_model_is_bound_once(monkeypatch):
    calls=[]
    monkeypatch.setattr(embed,'_client',lambda *args: SimpleNamespace(embed=lambda texts,**kw:(calls.append(kw),[[1.,0.]])[1]))
    monkeypatch.setenv('MDBX_EMBED_BACKEND','ollama')
    monkeypatch.setenv('MDBX_EMBED_MODEL','different-live-selection')
    embed.embed(['synthetic'],model_name='captured-synthetic')
    assert calls == [{'model':'captured-synthetic'}]


def test_optional_native_import_failure_preserves_fallback(monkeypatch):
    original = builtins.__import__
    def fail(name,*args,**kwargs):
        if name == 'onnxruntime':
            raise OSError('synthetic loader failure')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',fail)
    assert embed_onnx.available() is False


def test_expected_update_needs_no_hardlink(tmp_path, monkeypatch):
    target=tmp_path/'query.mql'; target.write_bytes(b'original')
    def fail(*args,**kwargs): raise OSError(errno.EOPNOTSUPP,'synthetic no hardlinks')
    monkeypatch.setattr(os,'link',fail)
    safety.atomic_write(target,b'rewritten',expected=b'original')
    assert target.read_bytes() == b'rewritten'
    assert any(p.read_bytes() == b'original' for p in tmp_path.glob('.mdbx-recovery-*'))


def test_directory_substitution_retains_original_path(tmp_path, monkeypatch):
    target=tmp_path/'query.mql'; target.write_bytes(b'original')
    real=safety._exchange
    swapped=[]
    def exchange(parent,left,right):
        if not swapped:
            swapped.append(True); target.unlink(); target.mkdir(); (target/'sentinel').write_text('directory save')
        return real(parent,left,right)
    monkeypatch.setattr(safety,'_exchange',exchange)
    with pytest.raises((ValueError,OSError)):
        safety.atomic_write(target,b'rewritten',expected=b'original')
    assert (target/'sentinel').read_text() == 'directory save'


def test_expected_compare_is_bounded(tmp_path, monkeypatch):
    target=tmp_path/'query.mql'; target.write_bytes(b'x'*100000)
    original=os.fdopen; reads=[]
    class Stream:
        def __init__(self,value): self.value=value
        def __enter__(self): self.value.__enter__(); return self
        def __exit__(self,*args): return self.value.__exit__(*args)
        def read(self,*args): reads.append(args); return self.value.read(*args)
        def __getattr__(self,name): return getattr(self.value,name)
    monkeypatch.setattr(os,'fdopen',lambda *a,**kw:Stream(original(*a,**kw)))
    with pytest.raises(ValueError): safety.atomic_write(target,b'new',expected=b'old')
    assert reads == [(4,)]


def test_macos_verified_tmp_alias(tmp_path):
    if sys.platform != 'darwin' or not Path('/tmp').is_symlink(): pytest.skip('macOS system alias')
    import uuid
    target=Path('/tmp')/('mdbx-synthetic-'+uuid.uuid4().hex)
    try:
        safety.atomic_write(target,b'synthetic')
        assert target.read_bytes() == b'synthetic'
    finally: target.unlink(missing_ok=True)


def test_reference_limit_validation_precedes_empty_data(tmp_path):
    root=tmp_path/'corpus';root.mkdir();(root/'a.md').write_text('alpha')
    out=tmp_path/'out';webexport.export(root,out,vectors=False,allow_untracked=True)
    wi=webexport.WebIndex(out)
    for limit in (True,-1,1.5):
        for call in (lambda limit=limit:wi.semantic_vec([],limit),lambda limit=limit:wi.hybrid_vec('alpha',None,limit)):
            with pytest.raises(ValueError,match='limit'):call()


def test_reference_source_filter_matches_ascii_sqlite_like(tmp_path):
    root=tmp_path/'corpus';(root/'skills/ä').mkdir(parents=True);(root/'skills/ä/a.md').write_text('alpha')
    out=tmp_path/'out';webexport.export(root,out,vectors=False,allow_untracked=True)
    wi=webexport.WebIndex(out)
    assert wi.keyword('alpha',source='ä')
    assert not wi.keyword('alpha',source='Ä')


def test_reference_hydration_stops_at_unique_limit(tmp_path,monkeypatch):
    root=tmp_path/'corpus';root.mkdir()
    for n in range(40):(root/f'{n}.md').write_text(f'alpha {n}')
    out=tmp_path/'out';webexport.export(root,out,vectors=False,allow_untracked=True)
    wi=webexport.WebIndex(out);calls=[];real=wi.hit
    monkeypatch.setattr(wi,'hit',lambda *args:(calls.append(args),real(*args))[1])
    assert len(wi.keyword('alpha',1)) == 1
    assert len(calls) == 1


def test_overflowing_weight_fails_without_publishing_new_format(tmp_path):
    root=tmp_path/'corpus';root.mkdir();source=root/'a.md';source.write_text('alpha original')
    out=tmp_path/'out';webexport.export(root,out,vectors=False,allow_untracked=True)
    before={p.name:p.read_bytes() for p in out.iterdir()}
    source.write_text('# '+('alpha '*17000)+'\nbody')
    with pytest.raises(ValueError,match='frequency exceeds'):webexport.export(root,out,vectors=False,allow_untracked=True)
    assert before == {p.name:p.read_bytes() for p in out.iterdir()}


def test_scrub_uppercase_and_repeated_url_starts():
    module=script('maintenance_safety')
    result=module.scrub('HTTPS://alice:SYNTH_SECRET@example.invalid/path?token=SYNTH_TOKEN')
    assert 'SYNTH_SECRET' not in result and 'SYNTH_TOKEN' not in result
    nested = module.scrub('https://x/HTTPS://alice:SYNTH_SECRET@example.invalid/path?token=SYNTH_TOKEN')
    assert 'SYNTH_SECRET' not in nested and 'SYNTH_TOKEN' not in nested
    assert module.scrub('https://x/'*5000) == 'https://x/'*5000


def test_safe_bytes_has_explicit_bound(tmp_path):
    module=script('maintenance_safety');target=tmp_path/'a';target.write_bytes(b'x'*20)
    with pytest.raises(ValueError,match='byte limit'):module.safe_bytes(target,tmp_path,max_bytes=5)
    assert module.safe_bytes(target,tmp_path,max_bytes=20) == b'x'*20


def test_clone_dirty_check_cannot_hide_untracked(tmp_path):
    module=script('maintenance_safety');clone=tmp_path/'clone';(clone/'.git').mkdir(parents=True)
    (clone/'.git/mdbx-maintenance-owner.json').write_text(json.dumps({'path':str(clone),'repo':'synthetic'}))
    seen=[]
    def git(args,cwd):
        seen.append(args)
        return SimpleNamespace(returncode=0,stdout='synthetic' if args[0]=='remote' else ('?? mine\n' if '--untracked-files=all' in args else ''))
    with pytest.raises(RuntimeError,match='changes'):module.verify_clone(clone,'synthetic',tmp_path/'working',git)
    assert '--untracked-files=all' in seen[-1]


def test_doc_index_requires_real_record_list(tmp_path):
    checker = tmp_path / 'scripts/check_doc_indexes.py'
    checker.parent.mkdir()
    checker.write_bytes((SOURCE / 'scripts/check_doc_indexes.py').read_bytes())
    docs = tmp_path / 'docs'; docs.mkdir()
    for bad in ({}, [], [{'path':'','purpose':'x','bytes':1}]):
        (docs / 'high_signal_file_index.json').write_text(json.dumps(bad))
        result = subprocess.run([sys.executable, str(checker)], capture_output=True, text=True, timeout=10, check=False)
        assert result.returncode != 0, 'malformed record was accepted'
    (tmp_path / 'safe').write_text('synthetic')
    (docs / 'high_signal_file_index.json').write_text(json.dumps([{'path':'safe','purpose':'fixture','bytes':9}]))
    result = subprocess.run([sys.executable,str(checker)],capture_output=True,text=True,timeout=10,check=False)
    assert result.returncode == 0


def test_static_filename_literal_preserves_ampersand():
    module=script('gen_file_index')
    assert '&amp;' not in module.literal('a&b')
    assert 'a&b' in module.literal('a&b')


def test_recovery_follows_pinned_parent_after_move(tmp_path):
    module=script('maintenance_safety');parent=tmp_path/'parent';parent.mkdir();target=parent/'x';target.write_bytes(b'old')
    recovery=module.replace_preserving(target,b'new',parent,b'old')
    parent.rename(tmp_path/'renamed')
    private=tmp_path/'private';private.mkdir(mode=0o700)
    try: recovery.move_to(private)
    finally: recovery.close()
    assert [p.read_bytes() for p in private.iterdir()] == [b'old']
    assert (tmp_path/'renamed/x').read_bytes() == b'new'


def test_offline_signal_status_is_shell_conventional(monkeypatch):
    module=script('offline_test')
    monkeypatch.setattr(module,'prepare_environment',lambda path:None)
    monkeypatch.setattr(module.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(returncode=-15))
    monkeypatch.setattr(sys,'argv',['offline_test','--','synthetic-no-execution'])
    assert module.main() == 143


def test_fixture_pair_restores_independent_member_after_failed_restore(tmp_path, monkeypatch):
    module=script('gen_search_golden');monkeypatch.setattr(module,'FIX',tmp_path)
    (tmp_path/'index').mkdir();(tmp_path/'index/value').write_bytes(b'old index');(tmp_path/'golden.json').write_bytes(b'old golden')
    staged=tmp_path/'candidate';(staged/'index').mkdir(parents=True);(staged/'index/value').write_bytes(b'new index');(staged/'golden.json').write_bytes(b'new golden')
    real=safety._rename_exclusive;reached=[]
    def fail(source,target,*args,**kwargs):
        source_name=Path(source).name;target_name=Path(target).name
        if source_name=='golden.json' and target_name=='golden.json' and kwargs.get('src_dir_fd')!=kwargs.get('dst_dir_fd'):
            reached.append('publish');raise OSError('synthetic golden publish failure')
        if source_name.startswith('.mdbx-recovery-') and target_name=='golden.json':
            reached.append('restore');raise OSError('synthetic golden restore failure')
        return real(source,target,*args,**kwargs)
    monkeypatch.setattr(safety,'_rename_exclusive',fail)
    with pytest.raises(OSError,match='publish failure'):module.publish_pair(staged)
    assert reached==['publish','restore']
    assert (tmp_path/'index/value').read_bytes()==b'old index'
    assert any(p.is_file() and p.read_bytes()==b'old golden' for p in tmp_path.glob('.mdbx-recovery-*'))


def test_fixture_parent_swap_cannot_redirect_rollback(tmp_path,monkeypatch):
    module=script('gen_search_golden');fix=tmp_path/'fix';fix.mkdir();outside=tmp_path/'outside';outside.mkdir()
    for root,value in ((fix,b'old'),(outside,b'outside sentinel')):
        (root/'index').mkdir();(root/'index/value').write_bytes(value);(root/'golden.json').write_bytes(value)
    staged=tmp_path/'candidate';(staged/'index').mkdir(parents=True);(staged/'index/value').write_bytes(b'new');(staged/'golden.json').write_bytes(b'new')
    monkeypatch.setattr(module,'FIX',fix);real=safety._rename_exclusive;swapped=[]
    def swap(source,target,*args,**kwargs):
        result=real(source,target,*args,**kwargs)
        if Path(source).name=='index' and Path(target).name=='index' and not swapped:
            swapped.append(True);fix.rename(tmp_path/'saved');fix.symlink_to(outside,target_is_directory=True)
        return result
    monkeypatch.setattr(safety,'_rename_exclusive',swap)
    try:module.publish_pair(staged)
    except (OSError,ValueError):pass
    assert swapped
    assert (outside/'index/value').read_bytes()==b'outside sentinel'
    assert (outside/'golden.json').read_bytes()==b'outside sentinel'


def test_reference_reader_waits_for_one_export_generation(tmp_path,monkeypatch):
    import threading
    root=tmp_path/'corpus';root.mkdir();(root/'a.md').write_text('old alpha')
    out=tmp_path/'out';webexport.export(root,out,vectors=False,allow_untracked=True)
    (root/'b.md').write_text('new beta')
    loads=json.loads;started=[];finished=threading.Event();errors=[]
    def writer():
        try:webexport.export(root,out,vectors=False,allow_untracked=True)
        except (OSError, ValueError, RuntimeError) as error:errors.append(error)
        finally:finished.set()
    worker=threading.Thread(target=writer)
    def pause(payload,*args,**kwargs):
        result=loads(payload,*args,**kwargs)
        if isinstance(result,dict) and 'total_tokens' in result and not started:
            started.append(True);worker.start();finished.wait(.2)
        return result
    monkeypatch.setattr(json,'loads',pause)
    wi=webexport.WebIndex(out)
    worker.join(5)
    assert not worker.is_alive() and not errors
    assert wi.meta['chunks']==len(wi.rows)
    assert wi.meta['chunks'] in (1,2)


def test_reference_query_frequency_does_not_rescan_terms(tmp_path,monkeypatch):
    root=tmp_path/'corpus';root.mkdir();(root/'a.md').write_text('alpha beta')
    out=tmp_path/'out';webexport.export(root,out,vectors=False,allow_untracked=True)
    class Terms(list):
        def count(self,*args):raise AssertionError('repeated query term rescanned')
    monkeypatch.setattr(webexport,'query_terms',lambda query:Terms(['alpha','beta']*100))
    assert webexport.WebIndex(out).keyword('synthetic')


def test_fixture_vectors_use_canonical_duplicate_body_heading(tmp_path,monkeypatch):
    module=script('gen_search_golden');monkeypatch.setattr(module,'FIX',tmp_path)
    root=tmp_path/'corpus';root.mkdir()
    for name in ('A','Z'):(root/(name+'.md')).write_text('# '+name+'\n'+'alpha body '*500)
    out=tmp_path/'index';module.build(out)
    rows=json.loads((out/'chunks.json').read_text())['rows']
    assert rows and all(row[6]>=0 for row in rows)


def test_unicode_generator_checks_survive_optimized_python(tmp_path):
    # A fake SQL oracle supplies a contradictory standalone scalar. No model/data loads.
    code=r'''
import importlib.util,sys
from types import SimpleNamespace
spec=importlib.util.spec_from_file_location('generator',sys.argv[1]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Connection:
    def execute(self,sql,*args):return [(195,'axz'),(196,'wrong')] if sql.startswith('SELECT doc,term') else []
    def executemany(self,*args):pass
    def close(self):pass
module.sqlite3.connect=lambda *args:Connection()
module.range=lambda *args:[0] if args==(0,0x110000,module.BATCH) else [97]
try:module.derive()
except ValueError:sys.exit(0)
else:sys.exit(1)
'''
    result=subprocess.run([sys.executable,'-O','-c',code,str(SOURCE/'scripts/gen_unicode61.py')],capture_output=True,text=True,timeout=10,check=False)
    assert result.returncode==0,result.stderr


def test_package_rejects_missing_manifest_icon(tmp_path,monkeypatch):
    module=script('package_chrome_extension');ext=tmp_path/'editors/chrome';ext.mkdir(parents=True)
    for name in module.RUNTIME:
        (ext/name).write_text('{}' if name=='manifest.json' else 'synthetic')
    (ext/'manifest.json').write_text(json.dumps({'version':'1.0.0','icons':{'128':'icons/icon128.png'}}))
    (ext/'package.json').write_text(json.dumps({'version':'1.0.0'}))
    (ext/'icons').mkdir();(ext/'lib').mkdir();(ext/'lib/a.js').write_text('synthetic')
    monkeypatch.setattr(module,'ROOT',tmp_path);monkeypatch.setattr(module,'EXT',ext)
    monkeypatch.setattr(module,'git_commit',lambda **kw:'a'*40)
    monkeypatch.setattr(sys,'argv',['package','--no-data'])
    assert module.main()==1
    assert not list((tmp_path/'dist').glob('*.zip'))


def test_fixture_git_preserves_destination_after_separator(tmp_path):
    scratch=tmp_path/'scratch';scratch.mkdir()
    code="""import importlib.util,pathlib,subprocess,sys
spec=importlib.util.spec_from_file_location('isolation',sys.argv[1]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.prepare_environment(pathlib.Path(sys.argv[2]))
subprocess.run(['git','init','-q','--','--template=repo'],check=True,capture_output=True)
assert pathlib.Path('--template=repo/.git').is_dir()
assert not pathlib.Path('.git').exists()
"""
    subprocess.run([sys.executable,'-c',code,str(SOURCE/'scripts/test_isolation.py'),str(scratch)],cwd=tmp_path,check=True,capture_output=True,text=True,timeout=10)


def test_cleanup_failure_still_closes_pinned_descriptor(tmp_path,monkeypatch):
    module=script('maintenance_safety');real_open=os.open;real_close=os.close;opened=[];closed=[]
    def opened_fd(*args,**kwargs):
        fd=real_open(*args,**kwargs);opened.append(fd);return fd
    def closed_fd(fd):closed.append(fd);return real_close(fd)
    def fail(*args,**kwargs):raise OSError('synthetic publication/cleanup failure')
    monkeypatch.setattr(os,'open',opened_fd);monkeypatch.setattr(os,'close',closed_fd)
    monkeypatch.setattr(os,'replace',fail);monkeypatch.setattr(os,'unlink',fail)
    with pytest.raises(OSError):module.atomic_write(tmp_path/'out',b'synthetic',root=tmp_path)
    assert opened[0] in closed


def test_package_archive_and_stamp_use_one_captured_commit(tmp_path,monkeypatch):
    import zipfile
    module=script('package_chrome_extension');ext=tmp_path/'editors/chrome';ext.mkdir(parents=True)
    for name in module.RUNTIME:(ext/name).write_text('synthetic')
    (ext/'manifest.json').write_text(json.dumps({'version':'1.0.0','icons':{'128':'icons/icon128.png'}}))
    (ext/'package.json').write_text(json.dumps({'version':'1.0.0'}));(ext/'icons').mkdir();(ext/'icons/icon128.png').write_bytes(b'synthetic PNG')
    (ext/'lib').mkdir();(ext/'lib/a.js').write_text('synthetic')
    monkeypatch.setattr(module,'ROOT',tmp_path);monkeypatch.setattr(module,'EXT',ext)
    calls=[];captured=[]
    def commit(**kwargs):calls.append(kwargs);return ('a' if len(calls)==1 else 'b')*40
    def data(vectors,out,**kwargs):
        captured.append(kwargs.get('commit'));return SimpleNamespace(vectors=0)
    monkeypatch.setattr(module,'git_commit',commit);monkeypatch.setattr(module,'build_data',data)
    monkeypatch.setattr(sys,'argv',['package','--no-vectors'])
    assert module.main()==0
    with zipfile.ZipFile(next((tmp_path/'dist').glob('*.zip'))) as archive:
        stamp=json.loads(archive.read('data/build.json'));manifest=json.loads(archive.read('manifest.json'))
    assert captured==['a'*40] and calls==[{'full':True}]
    assert stamp['commit']=='a'*12 and manifest['mdbx_data'] is True


def test_committed_archive_ignores_inherited_git_selectors(tmp_path,monkeypatch):
    import io
    import tarfile
    module=script('package_chrome_extension');payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w') as archive:
        info=tarfile.TarInfo('corpus/a.md');body=b'synthetic alpha';info.size=len(body);archive.addfile(info,io.BytesIO(body))
    calls=[]
    def run(args,**kwargs):calls.append((args,kwargs));return SimpleNamespace(stdout=payload.getvalue())
    monkeypatch.setattr(module.subprocess,'run',run);monkeypatch.setenv('GIT_DIR','/synthetic-unrelated');monkeypatch.setenv('GIT_WORK_TREE','/synthetic-unrelated')
    monkeypatch.setattr(webexport,'export',lambda *args,**kwargs:SimpleNamespace(chunks=1,files=1,terms=1,vectors=0,skipped_untracked=0))
    module.build_data(False,tmp_path/'out',commit='a'*40)
    assert calls[0][0]==['git','archive','a'*40,'corpus']
    assert all(key not in calls[0][1]['env'] for key in ('GIT_DIR','GIT_WORK_TREE'))


def test_unproven_legacy_vectors_do_not_constrain_candidate_dimension(tmp_path, monkeypatch):
    con, _root = seed(tmp_path, monkeypatch)
    with closing(con):
        con.execute("DELETE FROM meta WHERE key='embed_dim'")
        con.execute('DELETE FROM vector_inputs')
        con.execute('UPDATE vectors SET dim=3,vec=?', (np.array([1.,0.,0.],dtype=np.float32).tobytes(),))
        con.commit()
        assert index.build_semantic(con) == 3
        assert {r[0] for r in con.execute('SELECT dim FROM vectors')} == {2}
