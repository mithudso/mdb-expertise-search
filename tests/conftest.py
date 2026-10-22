"""Tests assume Ollama is the embedder unless a test opts into another backend."""
import pytest


@pytest.fixture(autouse=True)
def _ollama_backend(monkeypatch):
    monkeypatch.setenv("MDBX_EMBED_BACKEND", "ollama")
