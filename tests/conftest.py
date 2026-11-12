"""Synthetic offline tests. Isolate state and pause semantic hooks before collection.

Use process-tree egress isolation too: socket patches do not cover descendants.
"""
import hashlib
import os
import shutil
import socket
import subprocess
import tempfile
import threading
from pathlib import Path

import pytest

_STATE = tempfile.TemporaryDirectory(prefix='mdbx-tests-')
_ROOT = Path(_STATE.name)
_SEMANTIC_HOOK = 'ff844623f0c625388097eb1e94665cb7989f054413afc03ace89d9864a56dbce'


def _git(*args):
    result = subprocess.run(['git', *args], capture_output=True, text=True, timeout=10, check=False)
    return result.stdout.strip() if result.returncode == 0 else ''


def _pause_semantic_hooks():
    hooks = _ROOT / 'hooks'
    hooks.mkdir()
    paths = [_git('config', '--path', '--get', 'core.hooksPath') or _git('rev-parse', '--git-path', 'hooks')]
    template = _git('config', '--path', '--get', 'init.templateDir')
    if template:
        paths.append(str(Path(template).expanduser() / 'hooks'))
    for raw in paths:
        directory = Path(raw).expanduser()
        if not raw or not directory.is_dir():
            continue
        for path in directory.iterdir():
            if not path.is_file() or path.name.endswith('.sample'):
                continue
            data = path.read_bytes()
            if path.name == 'post-commit' and hashlib.sha256(data).hexdigest() == _SEMANTIC_HOOK:
                continue
            dest = hooks / path.name
            if dest.exists() and dest.read_bytes() != data:
                raise RuntimeError('conflicting validation hooks; isolate the test configuration')
            shutil.copy2(path, dest)
    count = int(os.environ.get('GIT_CONFIG_COUNT', '0'))
    for key, value in [('core.hooksPath', str(hooks)), ('commit.gpgsign', 'false')]:
        os.environ[f'GIT_CONFIG_KEY_{count}'] = key
        os.environ[f'GIT_CONFIG_VALUE_{count}'] = value
        count += 1
    os.environ['GIT_CONFIG_COUNT'] = str(count)
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES'):
        os.environ.pop(key, None)


for _key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES'):
    os.environ.pop(_key, None)
_pause_semantic_hooks()
for key, value in {
    'MDBX_DB': str(_ROOT / 'test.sqlite'), 'MDBX_CORPUS': str(_ROOT / 'corpus'),
    'MDBX_ONNX_MODEL': str(_ROOT / 'empty-model'), 'MDBX_OLLAMA_HOST': 'http://127.0.0.1:9',
    'MDBX_AUTOUPDATE_CONFIG': str(_ROOT / 'chrome.json'),
    'MDBX_CORPUS_AUTOUPDATE_CONFIG': str(_ROOT / 'corpus.json'),
}.items():
    os.environ[key] = value
(_ROOT / 'empty-model').mkdir()
(_ROOT / 'corpus').mkdir()

from mdbx import embed_onnx

embed_onnx._runtime.cache_clear()


def _no_real_runtime():
    raise embed_onnx.OnnxUnavailable('model.onnx is not installed in the synthetic test environment')


_no_real_runtime.cache_clear = lambda: None
embed_onnx._runtime = _no_real_runtime


@pytest.fixture(autouse=True)
def _offline_backend(monkeypatch):
    monkeypatch.setenv('MDBX_EMBED_BACKEND', 'ollama')

    def denied(*args, **kwargs):
        raise OSError('network disabled in synthetic tests')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'connect_ex', denied)


@pytest.fixture(autouse=True)
def _close_test_databases(monkeypatch):
    from mdbx import index
    connections = []
    original = index.connect
    owner_thread = threading.get_ident()

    def connect(*args, **kwargs):
        con = original(*args, **kwargs)
        if threading.get_ident() == owner_thread:
            connections.append(con)
        return con

    monkeypatch.setattr(index, 'connect', connect)
    yield
    for con in reversed(connections):
        con.close()
