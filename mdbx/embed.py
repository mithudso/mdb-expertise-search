"""embed — Ollama embedding client (stdlib only)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import numpy as np

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
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EmbedError(f"cannot reach Ollama at {host()}: {exc}") from exc
    vecs = data.get("embeddings")
    if not vecs or len(vecs) != len(texts):
        raise EmbedError(f"unexpected /api/embed response: {str(data)[:200]}")
    arr = np.asarray(vecs, dtype=np.float32)
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
