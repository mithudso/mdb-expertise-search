"""Synthetic operational regressions for corroborated gate1 failures."""
import ctypes
import importlib.util
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]

def module(name):
    spec=importlib.util.spec_from_file_location('iteration2_'+name,ROOT/'scripts'/f'{name}.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def test_safe_reads_reject_replaced_root_fifo_and_credentials(tmp_path):
    m=module('maintenance_safety')
    corpus=tmp_path/'corpus';corpus.mkdir();(corpus/'note.md').write_text('original')
    other=tmp_path/'other';other.mkdir();(other/'note.md').write_text('outside')
    corpus.rename(tmp_path/'retained');corpus.symlink_to(other,target_is_directory=True)
    with pytest.raises((ValueError,OSError)):
        m.safe_bytes(corpus/'note.md',corpus)
    assert (other/'note.md').read_text()=='outside'
    fifo=other/'pipe';os.mkfifo(fifo)
    command=[sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from maintenance_safety import safe_bytes;safe_bytes(sys.argv[2],sys.argv[3])',str(ROOT/'scripts'),str(fifo),str(other)]
    assert subprocess.run(command,timeout=2,capture_output=True,check=False).returncode!=0
    assert 'SYNTH_SECRET' not in m.scrub('https://git.invalid/r.git?access_token=SYNTH_SECRET')


def test_atomic_write_rejects_parent_swap_and_exchange_preserves_concurrent_save(tmp_path,monkeypatch):
    m=module('maintenance_safety');directory=tmp_path/'owned';directory.mkdir();outside=tmp_path/'outside';outside.mkdir()
    directory.rename(tmp_path/'old');directory.symlink_to(outside,target_is_directory=True)
    with pytest.raises(OSError):m.atomic_write(directory/'note.md',b'new',root=tmp_path)
    assert not list(outside.iterdir())
    path=tmp_path/'note.md';path.write_bytes(b'original')
    real=ctypes.CDLL(None,use_errno=True)
    method=getattr(real,'renameatx_np',None) or getattr(real,'renameat2',None)
    if method is None:pytest.skip('atomic exchange unsupported')
    calls=[]
    def swap(*args):
        if not calls:
            replacement=tmp_path/'editor-save';replacement.write_bytes(b'intervening editor save');os.replace(replacement,path)
        calls.append(1);return method(*args)
    proxy=SimpleNamespace(renameatx_np=swap)
    monkeypatch.setattr(ctypes,'CDLL',lambda *a,**kw:proxy)
    with pytest.raises(RuntimeError,match='concurrent save'):
        m.replace_preserving(path,b'candidate',tmp_path,b'original')
    assert path.read_bytes()==b'intervening editor save'


def test_rotation_retry_is_idempotent_and_archive_permissions_stay_private(tmp_path,monkeypatch):
    m=module('rotate_workflow_logs');monkeypatch.setattr(m,'ROOT',tmp_path)
    path=tmp_path/'memory.md';path.write_text('## v2\nnew\n## v1\nold\n');path.chmod(0o600)
    real=m.replace_preserving
    monkeypatch.setattr(m,'replace_preserving',lambda *a,**kw:(_ for _ in ()).throw(OSError('synthetic')))
    with pytest.raises(OSError):m.rotate(path,0,1,False)
    archive=next((tmp_path/'docs/archive').glob('memory-*.md'));first=archive.read_bytes()
    monkeypatch.setattr(m,'replace_preserving',real)
    assert m.rotate(path,0,1,False)
    assert archive.read_bytes()==first and archive.stat().st_mode&0o777==0o600
    assert path.read_text()=='## v2\nnew\n'


def test_redaction_private_configuration_errors_and_json_escapes_are_safe(tmp_path,monkeypatch,capsys):
    m=module('redact_corpus');config=tmp_path/'rules.py';config.write_text('raise RuntimeError("SYNTH_PRIVATE")\n')
    monkeypatch.setenv('MDBX_REDACTIONS',str(config));monkeypatch.setattr(m,'ROOT',tmp_path)
    corpus=tmp_path/'corpus';corpus.mkdir();monkeypatch.setattr(m,'CORPUS',corpus)
    assert m.main()==1
    assert 'SYNTH_PRIVATE' not in ''.join(capsys.readouterr())
    config.write_text('RULES=[("SYNTH_PRIVATE",)]\n')
    assert m.main()==1
    assert 'SYNTH_PRIVATE' not in ''.join(capsys.readouterr())
    source=json.dumps({'path':'/Users/synthetic/name"tail'})
    redacted=m.redact_text(source,[])
    assert json.loads(redacted)['path']=='<local-path>"tail'


def test_redaction_mixed_file_patch_state_is_accepted(tmp_path,monkeypatch):
    m=module('redact_corpus');corpus=tmp_path/'corpus';corpus.mkdir()
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'CORPUS',corpus)
    a=corpus/'a.md';b=corpus/'b.md';a.write_text('after\n');b.write_text('before\n')
    patch=tmp_path/'mixed.patch';patch.write_text(''.join(f'diff --git a/corpus/{name}.md b/corpus/{name}.md\n--- a/corpus/{name}.md\n+++ b/corpus/{name}.md\n@@ -1 +1 @@\n-before\n+after\n' for name in ['a','b']))
    monkeypatch.setattr(m,'load_private',lambda:([],str(patch)))
    assert m.main()==0
    assert a.read_text()==b.read_text()=='after\n'
    assert m.main()==0


def test_sweep_regex_runtime_and_carriage_return_names_are_bounded(tmp_path,monkeypatch):
    m=module('sweep_customers');corpus=tmp_path/'corpus';corpus.mkdir()
    name='corpus/a\rname.md';(tmp_path/name).write_text('a'*40+'!')
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'MATCH_TIMEOUT',0.02)
    monkeypatch.setattr(m,'load_patterns',lambda:[re.compile('(a+)+$')])
    monkeypatch.setattr(m.subprocess,'run',lambda argv,**kw:SimpleNamespace(stdout=b'' if '-o' in argv else os.fsencode(name)+b'\0'))
    assert m.main(['--json'])==2
    monkeypatch.setattr(m,'load_patterns',lambda:[re.compile('never')])
    assert m.main(['--json'])==0


def test_source_sync_transitions_and_partial_copy_ownership(tmp_path,monkeypatch):
    m=module('sync_corpus_sources');source=tmp_path/'source';source.mkdir();destination=tmp_path/'out';state=tmp_path/'state.json'
    (source/'entry.md').mkdir();(source/'entry.md/a.md').write_text('a');m.sync_tree(source,destination,state)
    (source/'entry.md/a.md').unlink();(source/'entry.md').rmdir();(source/'entry.md').write_text('b');m.sync_tree(source,destination,state)
    assert (destination/'entry.md').read_text()=='b' and (destination/'entry.md').is_file()
    real=m.shutil.copy2
    def fail(*args,**kwargs):
        real(*args,**kwargs);raise OSError('synthetic')
    monkeypatch.setattr(m.shutil,'copy2',fail);(source/'new.md').write_text('new')
    with pytest.raises(OSError):m.sync_tree(source,destination,state)
    assert 'new.md' in next(iter(json.loads(state.read_text()).values()))
    monkeypatch.setattr(m.shutil,'copy2',real);(source/'new.md').unlink();m.sync_tree(source,destination,state)
    assert not (destination/'new.md').exists()


def test_updater_preserves_pending_commits_and_uses_configured_sweep_environment(tmp_path,monkeypatch):
    m=module('corpus_autoupdate');calls=[]
    monkeypatch.setattr(m,'must_git',lambda args,*other:calls.append(args) or '')
    monkeypatch.setattr(m,'git',lambda args,*other:SimpleNamespace(returncode=1 if args[0]=='merge-base' else 0))
    with pytest.raises(RuntimeError,match='unpublished'):m.reset_to_origin(tmp_path,'main')
    assert not any(args[0]=='reset' for args in calls)
    seen=[]
    monkeypatch.setattr(m.subprocess,'run',lambda *a,**kw:(seen.append(kw),SimpleNamespace(stdout='{"status":"clean","files":[]}',returncode=0))[1])
    assert m.sweep(tmp_path,sys.executable,{'MDBX_DENYLIST':'synthetic-configured'})==(0,[])
    assert seen[-1]['env']['MDBX_DENYLIST']=='synthetic-configured'
    monkeypatch.setenv('GIT_DIR','synthetic-redirect')
    assert 'GIT_DIR' not in m.git_environment()


def fake_runtime(module,path):
    path.mkdir(parents=True)
    for name in module.RUNTIME_FILES:(path/name).write_text('synthetic')
    for name in ['lib','icons','data']:(path/name).mkdir()
    (path/'manifest.json').write_text(json.dumps({'manifest_version':3,'version':'1.0','background':{'service_worker':'background.js'},'icons':{'16':'icons/icon.png'}}))
    (path/'icons/icon.png').write_bytes(b'png')
    (path/'data/build.json').write_text(json.dumps({'version':'1.0','commit':'new'}))


@pytest.mark.parametrize('section,value',[('icons',[]),('action',None),('background',[])])
def test_extension_runtime_rejects_nested_shape(tmp_path,section,value):
    m=module('chrome_extension_autoupdate');fake_runtime(m,tmp_path/'source')
    path=tmp_path/'source/manifest.json';manifest=json.loads(path.read_text());manifest[section]=value;path.write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError,match='invalid'):m.validate_runtime(tmp_path/'source')


def test_extension_recovery_precedes_fetch_and_symlink_settings_are_preserved(tmp_path,monkeypatch):
    m=module('chrome_extension_autoupdate');install=tmp_path/'install';backup=tmp_path/'.install.backup-test';stage=tmp_path/'.install.stage-test'
    backup.mkdir();(backup/'keep').write_text('old');stage.mkdir();journal=tmp_path/'.install.swap.json';journal.write_text(json.dumps({'backup':str(backup),'stage':str(stage)}))
    def fetch(cfg):
        assert (install/'keep').read_text()=='old' and not journal.exists()
        raise RuntimeError('synthetic unavailable')
    monkeypatch.setattr(m,'upstream_commit',fetch)
    with pytest.raises(RuntimeError,match='unavailable'):m.run_update({'clone_dir':str(tmp_path/'clone'),'install_dir':str(install),'source':'git'})
    link=tmp_path/'link';link.symlink_to(install,target_is_directory=True)
    cfg={'repo':'synthetic','branch':'main','clone_dir':str(tmp_path/'clone'),'install_dir':str(link),'python':sys.executable,'source':'git','no_vectors':True,'interval_min':1}
    m.validate_config(cfg);assert cfg['install_dir']==str(link)
    with pytest.raises(RuntimeError,match='symlink'):m.run_update(cfg)


def test_release_metadata_archive_and_identity_fail_controlled(tmp_path,monkeypatch):
    m=module('chrome_extension_autoupdate')
    def download(argv,**kwargs):
        Path(argv[argv.index('--dir')+1],'build.json').write_text('{}')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(m.subprocess,'run',download)
    with pytest.raises(RuntimeError,match='metadata'):m.release_commit({'repo':'synthetic'})
    corrupt=tmp_path/'bad.zip';corrupt.write_bytes(b'not zip')
    with pytest.raises(RuntimeError,match='corrupt'):m.unpack_archive(corrupt,tmp_path/'out')
    source=tmp_path/'runtime';fake_runtime(m,source)
    monkeypatch.setattr(m,'release_commit',lambda cfg:'different')
    monkeypatch.setattr(m,'download_release',lambda *a:source)
    with pytest.raises(RuntimeError,match='disagree'):m.run_update({'clone_dir':str(tmp_path/'clone'),'install_dir':str(tmp_path/'install'),'source':'release'})
    assert not (tmp_path/'install').exists()


def test_package_requires_directories_captures_manifest_and_rolls_back_pair(tmp_path,monkeypatch):
    m=module('package_chrome_extension');ext=tmp_path/'editors/chrome';ext.mkdir(parents=True)
    for name in m.RUNTIME:(ext/name).write_text('synthetic')
    for name in ['lib','icons']:(ext/name).mkdir()
    (ext/'manifest.json').write_text('{"version":"1.0"}');(ext/'package.json').write_text('{"version":"1.0"}')
    monkeypatch.setattr(m,'ROOT',tmp_path);monkeypatch.setattr(m,'EXT',ext);monkeypatch.setattr(m,'git_commit',lambda:'synthetic');monkeypatch.setattr(sys,'argv',['package','--no-data'])
    assert m.main()==0
    output=tmp_path/'dist/mongodb-expertise-chrome-1.0.zip';metadata=tmp_path/'dist/build.json';old=(output.read_bytes(),metadata.read_bytes())
    real=m.atomic_write;failed=[]
    def publish(path,data,*args,**kwargs):
        if path==metadata and not failed:failed.append(1);raise OSError('synthetic')
        return real(path,data,*args,**kwargs)
    monkeypatch.setattr(m,'atomic_write',publish);assert m.main()==1
    assert (output.read_bytes(),metadata.read_bytes())==old
    (ext/'lib').rmdir();assert m.main()==1
    (ext/'lib').mkdir();(ext/'manifest.json').write_text('{"version":"0.0"}');(ext/'package.json').write_text('{"version":"0.0"}')
    assert m.main()==1 and not (tmp_path/'dist/mongodb-expertise-chrome-0.0.zip').exists()


def test_generators_preserve_path_bytes_sources_and_position_contract(tmp_path,monkeypatch):
    m=module('gen_recipes_index');item=SimpleNamespace(name='same',path=r'recipes/a\b.md',summary='',applies_to=[])
    assert 'a%5Cb.md' in m.row(item)
    monkeypatch.setattr(m,'ROOT',tmp_path);(tmp_path/'corpus/recipes').mkdir(parents=True);(tmp_path/'docs').mkdir()
    output=tmp_path/'docs/RECIPES.md';output.write_text('old')
    monkeypatch.setattr(m.recipes,'load',lambda *a:[item,SimpleNamespace(name='SAME',path='recipes/c.md')])
    with pytest.raises(ValueError,match='duplicate'):m.main()
    assert output.read_text()=='old'
    (tmp_path/'corpus/recipes').rmdir()
    with pytest.raises(ValueError,match='missing'):m.main()
    positions=module('gen_lint_golden')
    assert positions.position('a\r\n😀\r\ud800',2)==(0,1)
    assert positions.position('a\r\n😀\r\ud800',4)==(1,2)
    links=module('check_chrome_doc_links');links.SRC='const M=`https://www.mongodb.com/docs/`; const a=M+`manual/`; const b=`https://www.mongodb.com/docs/other/`;'
    assert links.urls()==['https://www.mongodb.com/docs/manual/','https://www.mongodb.com/docs/other/']


def executable(path,body):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text('#!/bin/bash\n'+body+'\n');path.chmod(0o755)


@pytest.mark.parametrize('event',['','printf "CLOSE_WRITE\\n";'])
def test_watcher_failure_returns_nonzero(tmp_path,event):
    script=tmp_path/'scripts/watch_and_index.sh';script.parent.mkdir();shutil.copyfile(ROOT/'scripts/watch_and_index.sh',script)
    executable(tmp_path/'bin/inotifywait',event+'exit 2')
    executable(tmp_path/'.venv/bin/mdbx','exit 0')
    result=subprocess.run(['/bin/bash',str(script)],env={**os.environ,'PATH':str(tmp_path/'bin')+':/usr/bin:/bin'},timeout=3,capture_output=True,check=False)
    assert result.returncode==2


def test_watcher_observes_and_coalesces_changes_during_indexing(tmp_path):
    script=tmp_path/'scripts/watch_and_index.sh';script.parent.mkdir();shutil.copyfile(ROOT/'scripts/watch_and_index.sh',script)
    executable(tmp_path/'bin/inotifywait','printf "CLOSE_WRITE\\n"; while [ ! -f "$CASE_ROOT/emit" ]; do sleep .01; done; for i in {1..20}; do printf "CLOSE_WRITE\\n"; done; while :; do sleep 1; done')
    executable(tmp_path/'.venv/bin/mdbx','cat "$CASE_ROOT/input" >> "$CASE_ROOT/snapshots"; touch "$CASE_ROOT/ready"; while [ ! -f "$CASE_ROOT/release" ]; do sleep .01; done')
    (tmp_path/'input').write_text('v1\n')
    process=subprocess.Popen(['/bin/bash',str(script)],env={**os.environ,'PATH':str(tmp_path/'bin')+':/usr/bin:/bin','CASE_ROOT':str(tmp_path)},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    def wait_for(predicate):
        deadline=time.monotonic()+4
        while not predicate():
            if time.monotonic()>deadline:raise AssertionError('synthetic watcher deadline')
            time.sleep(.01)
    try:
        wait_for(lambda:(tmp_path/'ready').exists())
        (tmp_path/'input').write_text('v2\n');(tmp_path/'emit').touch();(tmp_path/'release').touch()
        wait_for(lambda:(tmp_path/'snapshots').read_text().splitlines()==['v1','v2'])
        time.sleep(.15)
        assert (tmp_path/'snapshots').read_text().splitlines()==['v1','v2']
    finally:
        os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=3)

def test_packaging_exports_committed_snapshot_without_working_edits(tmp_path, monkeypatch):
    m = module("package_chrome_extension")
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        content = b"committed synthetic note"
        item = tarfile.TarInfo("corpus/note.md")
        item.size = len(content)
        archive.addfile(item, io.BytesIO(content))
    calls = []
    def git(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(stdout=payload.getvalue())
    monkeypatch.setattr(m.subprocess, "run", git)
    from mdbx import webexport
    def export(corpus, output, **kwargs):
        assert (corpus / "note.md").read_bytes() == b"committed synthetic note"
        assert kwargs["allow_untracked"] is True
        return SimpleNamespace(chunks=1, files=1, terms=1, vectors=0, skipped_untracked=0)
    monkeypatch.setattr(webexport, "export", export)
    m.build_data(vectors=False, out=tmp_path/"output")
    assert calls == [["git", "archive", "HEAD", "corpus"]]

def test_updater_timeout_cleans_owned_changes_and_chrome_preserves_pending_head(tmp_path, monkeypatch):
    m = module("corpus_autoupdate")
    clone = tmp_path/"clone"
    clone.mkdir()
    deny = tmp_path/"deny"
    deny.write_text("synthetic")
    monkeypatch.setenv("MDBX_DENYLIST", str(deny))
    monkeypatch.setattr(m, "ensure_clone", lambda cfg: clone)
    resets = []
    monkeypatch.setattr(m, "reset_to_origin", lambda *args: resets.append(args))
    monkeypatch.setattr(m, "LOG_PATH", tmp_path/"log")
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("synthetic", 1)
    monkeypatch.setattr(m.subprocess, "run", timeout)
    assert m.run_update({"clone_dir": str(clone), "branch": "main", "python": sys.executable}) == 1
    assert len(resets) == 2
    chrome = module("chrome_extension_autoupdate")
    monkeypatch.setattr(chrome, "ensure_clone", lambda cfg: clone)
    commands = []
    monkeypatch.setattr(chrome, "git", lambda args, *a: (commands.append(args), SimpleNamespace(returncode=1))[1])
    with pytest.raises(RuntimeError, match="unpublished"):
        chrome.checkout_upstream({"branch": "main"})
    assert not any(args[0] == "reset" for args in commands)
