import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location('probe_' + name, SOURCE/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    before = list(sys.path)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = before
    return module

def test_git_filename_carriage_return_is_preserved(tmp_path, monkeypatch):
    module = load('gen_file_index')
    path = 'scripts/a\rb.py'
    payload = (path+'\0').encode()
    def listing(*args, **kwargs):
        return SimpleNamespace(stdout=payload.decode().replace('\r', '\n') if kwargs.get('text') else payload)
    monkeypatch.setattr(module.subprocess, 'run', listing)
    assert module.tracked() == [path]

def test_index_excludes_transient_publication_files(monkeypatch):
    module = load('gen_file_index')
    payload = b'docs/.mdbx-recovery-123\0docs/kept.md\0'
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **kw: SimpleNamespace(stdout=payload.decode() if kw.get('text') else payload))
    assert module.tracked() == ['docs/kept.md']

def test_filename_markdown_is_literal():
    module = load('gen_file_index')
    result = module.literal('docs/a`b\r\n## <forged>.md')
    assert '\n' not in result and '\r' not in result
    assert '<forged>' in result and '&amp;' not in module.literal('a&b')
    assert result.startswith('`` ') and result.endswith(' ``')

def test_golden_generation_failure_preserves_pair(tmp_path, monkeypatch):
    module = load('gen_search_golden')
    monkeypatch.setattr(module, 'FIX', tmp_path)
    (tmp_path/'index').mkdir()
    (tmp_path/'index/chunks.json').write_bytes(b'previous index')
    (tmp_path/'golden.json').write_bytes(b'previous golden')
    def failure(out):
        out.mkdir(exist_ok=True)
        (out/'chunks.json').write_bytes(b'new incomplete index')
        raise RuntimeError('synthetic reference failure')
    monkeypatch.setattr(module, 'build', failure)
    monkeypatch.setattr(sys, 'argv', ['generator'])
    with pytest.raises(RuntimeError):
        module.main()
    assert (tmp_path/'index/chunks.json').read_bytes() == b'previous index'
    assert (tmp_path/'golden.json').read_bytes() == b'previous golden'

def test_second_publication_failure_restores_pair(tmp_path, monkeypatch):
    module = load('gen_search_golden')
    monkeypatch.setattr(module, 'FIX', tmp_path)
    (tmp_path/'index').mkdir()
    (tmp_path/'index/chunks.json').write_bytes(b'previous index')
    (tmp_path/'golden.json').write_bytes(b'previous golden')
    staged = tmp_path/'candidate'
    (staged/'index').mkdir(parents=True)
    (staged/'index/chunks.json').write_bytes(b'new index')
    (staged/'golden.json').write_bytes(b'new golden')
    from mdbx import safety
    real = safety._rename_exclusive
    reached = []
    def fail(source, target, *args, **kwargs):
        if Path(source).name == 'golden.json' and Path(target).name == 'golden.json' and kwargs.get('src_dir_fd') != kwargs.get('dst_dir_fd'):
            reached.append(True)
            assert (tmp_path/'index/chunks.json').read_bytes() == b'new index'
            raise OSError('synthetic second publication failure')
        return real(source, target, *args, **kwargs)
    monkeypatch.setattr(safety, '_rename_exclusive', fail)
    with pytest.raises(OSError, match='synthetic second publication failure'):
        module.publish_pair(staged)
    assert reached == [True]
    assert (tmp_path/'index/chunks.json').read_bytes() == b'previous index'
    assert (tmp_path/'golden.json').read_bytes() == b'previous golden'


def test_reference_search_failure_preserves_previous_pair(tmp_path, monkeypatch):
    module=load('gen_search_golden')
    monkeypatch.setattr(module,'FIX',tmp_path)
    monkeypatch.setattr(module,'QUERIES',[{'q':'synthetic'}])
    (tmp_path/'corpus').mkdir()
    (tmp_path/'corpus/a.md').write_text('# Synthetic\nnew source body')
    (tmp_path/'index').mkdir()
    (tmp_path/'index/chunks.json').write_bytes(b'previous index sentinel')
    (tmp_path/'golden.json').write_bytes(b'previous golden sentinel')
    called=[]
    def failure(*args,**kwargs):
        called.append(True)
        raise RuntimeError('synthetic reference keyword failure')
    monkeypatch.setattr(module.WebIndex,'keyword',failure)
    monkeypatch.setattr(sys,'argv',['generator'])
    with pytest.raises(RuntimeError,match='reference keyword'):
        module.main()
    assert called==[True]
    assert (tmp_path/'index/chunks.json').read_bytes()==b'previous index sentinel'
    assert (tmp_path/'golden.json').read_bytes()==b'previous golden sentinel'
