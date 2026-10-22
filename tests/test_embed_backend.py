"""Embedding backend selection: Ollama first, in-process ONNX as the fallback or by choice."""
from __future__ import annotations

import numpy as np
import pytest

from mdbx import embed, embed_onnx


def _fake_onnx(texts, *, prefix="search_document: "):
    return np.tile(np.array([[1.0, 0.0]], dtype=np.float32), (len(texts), 1))


def _ollama_down(*_a, **_k):
    raise embed.EmbedError("cannot reach Ollama")


def test_backend_env_values(monkeypatch):
    monkeypatch.delenv("MDBX_EMBED_BACKEND", raising=False)
    assert embed.backend() == "auto"
    monkeypatch.setenv("MDBX_EMBED_BACKEND", "ONNX")
    assert embed.backend() == "onnx"
    monkeypatch.setenv("MDBX_EMBED_BACKEND", "nonsense")
    assert embed.backend() == "auto"


def test_auto_falls_back_to_onnx_when_ollama_is_down(monkeypatch):
    monkeypatch.setenv("MDBX_EMBED_BACKEND", "auto")
    monkeypatch.setattr(embed, "_embed_ollama", _ollama_down)
    monkeypatch.setattr(embed_onnx, "available", lambda: True)
    monkeypatch.setattr(embed_onnx, "embed", _fake_onnx)
    assert embed.embed(["a", "b"]).shape == (2, 2)


def test_auto_without_onnx_files_keeps_the_ollama_error(monkeypatch):
    monkeypatch.setenv("MDBX_EMBED_BACKEND", "auto")
    monkeypatch.setattr(embed, "_embed_ollama", _ollama_down)
    monkeypatch.setattr(embed_onnx, "available", lambda: False)
    with pytest.raises(embed.EmbedError, match="cannot reach Ollama"):
        embed.embed(["a"])


def test_ollama_mode_never_uses_onnx(monkeypatch):
    monkeypatch.setenv("MDBX_EMBED_BACKEND", "ollama")
    monkeypatch.setattr(embed, "_embed_ollama", _ollama_down)
    monkeypatch.setattr(embed_onnx, "available", lambda: True)
    monkeypatch.setattr(embed_onnx, "embed", _fake_onnx)
    with pytest.raises(embed.EmbedError):
        embed.embed(["a"])


def test_onnx_mode_skips_ollama_and_rejects_other_models(monkeypatch):
    monkeypatch.setenv("MDBX_EMBED_BACKEND", "onnx")
    monkeypatch.setattr(embed, "_embed_ollama", lambda *a, **k: pytest.fail("Ollama must not be called"))
    monkeypatch.setattr(embed_onnx, "embed", _fake_onnx)
    assert embed.embed_query("q").shape == (2,)
    monkeypatch.setenv("MDBX_EMBED_MODEL", "mxbai-embed-large")
    with pytest.raises(embed.EmbedError, match="only serves"):
        embed.embed(["a"])


def test_missing_model_files_surface_as_embed_error(monkeypatch, tmp_path):
    monkeypatch.setenv("MDBX_EMBED_BACKEND", "onnx")
    monkeypatch.setenv("MDBX_ONNX_MODEL", str(tmp_path))  # empty dir: no model.onnx
    embed_onnx._runtime.cache_clear()
    with pytest.raises(embed.EmbedError, match=r"model\.onnx|not installed"):
        embed.embed(["a"])
    assert embed_onnx.available() is False


@pytest.mark.skipif(not embed_onnx.available(), reason="onnx extra or model not installed (mdbx embed-fetch)")
def test_real_onnx_vectors_are_unit_length_and_semantic(monkeypatch):
    monkeypatch.setenv("MDBX_EMBED_BACKEND", "onnx")
    docs = embed.embed(["Create a compound index on status and createdAt", "Bake sourdough bread at 230C"])
    assert np.allclose(np.linalg.norm(docs, axis=1), 1.0, atol=1e-4)
    q = embed.embed_query("how do I index two fields together")
    assert q @ docs[0] > q @ docs[1]
