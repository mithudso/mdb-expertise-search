"""embed — embedding client for mdbx: Ollama (thin shim over the shared ``ollama-client`` library) or in-process ONNX.

Backend (``MDBX_EMBED_BACKEND``): ``auto`` (default) uses Ollama and, when it is unreachable, the in-process model
(``mdbx.embed_onnx``) if its files are already downloaded; ``ollama`` and ``onnx`` force one. The ONNX backend only
serves ``nomic-embed-text`` and produces vectors compatible with the Ollama-built index.

The model is pinned to ``nomic-embed-text`` (the model the ~12,000-chunk index was built with;
the library default is ``mxbai-embed-large``, whose vectors are not comparable). The
``search_document:`` / ``search_query:`` prefixes stay here: Ollama does not add them.
"""
from __future__ import annotations

import logging
import os

import numpy as np

try:
    from ollama_client import OllamaClient, OllamaPool, OllamaUnavailable
except ModuleNotFoundError as exc:
    if exc.name != 'ollama_client':
        raise
    OllamaClient = OllamaPool = None

    class OllamaUnavailable(RuntimeError):
        pass

from . import embed_onnx

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
    if OllamaClient is None:
        raise OllamaUnavailable("install the optional ollama extra")
    spec = os.environ.get("MDBX_OLLAMA_HOST") or None
    return OllamaClient(OllamaPool(spec, timeout=timeout, retries=retries), embed_model=model())


BACKENDS = ("auto", "ollama", "onnx")


def backend() -> str:
    b = os.environ.get("MDBX_EMBED_BACKEND", "auto").strip().lower() or "auto"
    return b if b in BACKENDS else "auto"


def _embed_onnx(texts: list[str], prefix: str) -> np.ndarray:
    if model() != DEFAULT_MODEL:
        raise EmbedError(f"the onnx backend only serves {DEFAULT_MODEL}, not {model()}")
    try:
        return validate_vectors(embed_onnx.embed(texts, prefix=prefix), len(texts))
    except Exception as exc:
        raise EmbedError("ONNX model.onnx unavailable or invalid; verify the local model installation") from exc


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
    mode = backend()
    if mode == "onnx":
        return _embed_onnx(texts, prefix)
    try:
        return _embed_ollama(texts, prefix, timeout, retries)
    except EmbedError:
        if mode == "auto" and model() == DEFAULT_MODEL and embed_onnx.available():
            log.info("Ollama unreachable; embedding in-process with ONNX")
            return _embed_onnx(texts, prefix)
        raise


def _embed_ollama(texts: list[str], prefix: str, timeout: float, retries: int) -> np.ndarray:
    log.debug("embed model=%s inputs=%d", model(), len(texts))
    try:
        vecs = _client(timeout, retries).embed([prefix + t for t in texts], model=model())
    except OllamaUnavailable as exc:
        log.warning("Ollama embed request failed (%s)", type(exc).__name__)
        raise EmbedError("cannot reach Ollama; verify the local service and optional ollama extra") from exc
    return validate_vectors(vecs, len(texts))


def validate_vectors(vecs, count: int) -> np.ndarray:
    """Reject malformed provider data before normalizing in overflow-safe float64."""
    try:
        arr = np.asarray(vecs, dtype=np.float64)
    except (ValueError, TypeError, OverflowError) as exc:
        raise EmbedError("malformed embeddings: expected numeric matrix") from exc
    if arr.ndim != 2 or arr.shape[0] != count or arr.shape[1] == 0 or not np.isfinite(arr).all():
        raise EmbedError("malformed embeddings: invalid shape or nonfinite values")
    scale = np.max(np.abs(arr), axis=1, keepdims=True)
    if np.any(scale == 0):
        raise EmbedError("malformed embeddings: zero vector")
    arr = arr / scale
    return (arr / np.linalg.norm(arr, axis=1, keepdims=True)).astype(np.float32)


def embed_query(text: str, *, retries: int = 0) -> np.ndarray:
    # Queries fail fast (no retry rounds), as before: the caller falls back to keyword search.
    return embed([text], prefix="search_query: ", retries=retries)[0]


def available() -> bool:
    try:
        embed_query("ping")
        return True
    except EmbedError:
        return False
