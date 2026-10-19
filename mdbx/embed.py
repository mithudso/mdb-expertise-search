"""embed — Ollama embedding client (stdlib only)."""
from __future__ import annotations

import http.client
import json
import logging
import os
import urllib.error
import urllib.request

import numpy as np

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


def embed(texts: list[str], *, prefix: str = "search_document: ", timeout: float = 120.0) -> np.ndarray:
    """Embed ``texts`` and return an L2-normalised float32 matrix."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    body = json.dumps({"model": model(), "input": [prefix + t for t in texts]}).encode()
    req = urllib.request.Request(
        f"{host()}/api/embed", data=body, headers={"Content-Type": "application/json"}
    )
    log.debug("POST %s/api/embed model=%s inputs=%d", host(), model(), len(texts))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
        log.warning("Ollama embed request to %s failed: %s", host(), exc)
        raise EmbedError(f"cannot reach Ollama at {host()}: {exc}") from exc
    except ValueError as exc:  # non-JSON body (proxy error page, truncated response)
        log.warning("Ollama embed response from %s was not valid JSON: %s", host(), exc)
        raise EmbedError(f"invalid JSON from Ollama at {host()}: {exc}") from exc
    vecs = data.get("embeddings") if isinstance(data, dict) else None
    if not vecs or len(vecs) != len(texts):
        log.warning("unexpected /api/embed response for model %s: %.200s", model(), data)
        raise EmbedError(f"unexpected /api/embed response: {str(data)[:200]}")
    try:
        arr = np.asarray(vecs, dtype=np.float32)
    except ValueError as exc:  # ragged or non-numeric vectors
        raise EmbedError(f"malformed embeddings from Ollama: {exc}") from exc
    if arr.ndim != 2:
        raise EmbedError(f"malformed embeddings from Ollama: expected 2-D, got shape {arr.shape}")
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return arr / np.maximum(norms, 1e-12)


def embed_query(text: str) -> np.ndarray:
    return embed([text], prefix="search_query: ")[0]


def available() -> bool:
    try:
        embed_query("ping")
        return True
    except EmbedError:
        return False
