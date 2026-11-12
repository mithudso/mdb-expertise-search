"""Synthetic offline tests: isolate state and factories before product imports.

Use scripts/offline_test.py for process-tree egress protection too.
"""
import importlib.util
import socket
import tempfile
import threading
from pathlib import Path

_STATE = tempfile.TemporaryDirectory(prefix='mdbx-tests-')
_ROOT = Path(_STATE.name)
_SPEC = importlib.util.spec_from_file_location(
    '_mdbx_test_isolation', Path(__file__).resolve().parents[1] / 'scripts' / 'test_isolation.py')
_ISOLATION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_ISOLATION)
_ISOLATION.prepare_environment(_ROOT)
_ISOLATION.install_fake_factories()

import pytest


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
