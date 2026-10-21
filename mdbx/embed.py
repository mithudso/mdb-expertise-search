"""embed — Ollama embedding client for mdbx, a thin shim over the shared ``ollama-client`` library.

The model is pinned to ``nomic-embed-text`` (the model the ~12,000-chunk index was built with;
the library default is ``mxbai-embed-large``, whose vectors are not comparable). The
``search_document:`` / ``search_query:`` prefixes stay here: Ollama does not add them.
"""
from __future__ import annotations

import logging
import os

import numpy as np
from ollama_client import OllamaClient, OllamaPool, OllamaUnavailable

log = logging.getLogger("mdbx.embed")

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "nomic-embed-text"


class EmbedError(RuntimeError):
    """Raised when the embedding backend is unreachable or returns bad data."""


def host() -> str:
    h = os.environ.get("MDBX_OLLAMA_HOST") or os.environ.get("OLLAMA_HOST") or DEFAULT_HOST
    return h if h.startswith("http") else f"http://{h}"


def model() -> str:
    return os.environ.get("MDBX_EMBED_MODEL", DEFAULT_MODEL)


def _client(timeout: float, retries: int) -> OllamaClient:
    # MDBX_OLLAMA_HOST wins; otherwise the library reads OLLAMA_URLS / OLLAMA_HOST / OLLAMA_URL.
    spec = os.environ.get("MDBX_OLLAMA_HOST") or None
    return OllamaClient(OllamaPool(spec, timeout=timeout, retries=retries), embed_model=model())


def embed(
    texts: list[str],
    *,
    prefix: str = "search_document: ",
    timeout: float = 120.0,
    retries: int = 2,
) -> np.ndarray:
    """Embed ``texts`` and return an L2-normalised float32 matrix."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    log.debug("embed model=%s inputs=%d", model(), len(texts))
    try:
        vecs = _client(timeout, retries).embed([prefix + t for t in texts], model=model())
    except OllamaUnavailable as exc:
        log.warning("Ollama embed request failed: %s", exc)
        raise EmbedError(f"cannot reach Ollama at {host()}: {exc}") from exc
    try:
        arr = np.asarray(vecs, dtype=np.float32)
    except ValueError as exc:  # ragged or non-numeric vectors
        raise EmbedError(f"malformed embeddings from Ollama: {exc}") from exc
    if arr.ndim != 2:
        raise EmbedError(f"malformed embeddings from Ollama: expected 2-D, got shape {arr.shape}")
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return arr / np.maximum(norms, 1e-12)


def embed_query(text: str, *, retries: int = 0) -> np.ndarray:
    # Queries fail fast (no retry rounds), as before: the caller falls back to keyword search.
    return embed([text], prefix="search_query: ", retries=retries)[0]


def available() -> bool:
    try:
        embed_query("ping")
        return True
    except EmbedError:
        return False
