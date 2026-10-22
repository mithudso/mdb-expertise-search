"""embed_onnx — in-process nomic-embed-text-v1.5 (ONNX Runtime), so semantic search needs no Ollama process.

Ollama's ``nomic-embed-text`` is nomic-embed-text v1.5. The fp32 ONNX export of the same model, mean-pooled and
L2-normalised, matches the vectors already stored in the index (mean cosine 0.999 on a 64-chunk sample), so
switching backends needs no reindex. The int8 export does not match (0.94); it is deliberately not used.

Needs the ``onnx`` extra (``onnxruntime``, ``tokenizers``, ``huggingface_hub``) and a one-time ~550 MB download
(``mdbx embed-fetch``) into the Hugging Face cache. ``MDBX_ONNX_MODEL`` may name a directory that already holds
``model.onnx`` and ``tokenizer.json`` (offline installs).
"""
from __future__ import annotations

import functools
import logging
import os
from pathlib import Path

import numpy as np

log = logging.getLogger("mdbx.embed_onnx")

REPO = "nomic-ai/nomic-embed-text-v1.5"
MODEL_FILE = "onnx/model.onnx"
TOKENIZER_FILE = "tokenizer.json"
MAX_TOKENS = 2048  # Ollama's nomic-embed-text context; the index truncates chunks to 2,400 characters anyway
BATCH = 8


class OnnxUnavailable(RuntimeError):
    """The optional dependencies or the model files are missing."""


def _local_dir() -> Path | None:
    raw = os.environ.get("MDBX_ONNX_MODEL")
    return Path(raw).expanduser() if raw else None


def _resolve(*, download: bool) -> tuple[Path, Path]:
    """Return (model.onnx, tokenizer.json), downloading only when ``download`` is true."""
    local = _local_dir()
    if local is not None:
        model, tok = local / "model.onnx", local / TOKENIZER_FILE
        if not (model.is_file() and tok.is_file()):
            raise OnnxUnavailable(f"MDBX_ONNX_MODEL={local} must contain model.onnx and tokenizer.json")
        return model, tok
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise OnnxUnavailable("huggingface_hub is not installed; pip install 'mdb-expertise-search[onnx]'") from exc
    try:
        return (Path(hf_hub_download(REPO, MODEL_FILE, local_files_only=not download)),
                Path(hf_hub_download(REPO, TOKENIZER_FILE, local_files_only=not download)))
    except Exception as exc:  # hub raises several types for "not cached" / "offline"
        raise OnnxUnavailable(f"embedding model not downloaded ({type(exc).__name__}); run `mdbx embed-fetch`") from exc


def fetch() -> Path:
    """Download the model into the Hugging Face cache (or validate ``MDBX_ONNX_MODEL``). Returns the model path."""
    return _resolve(download=True)[0]


def available() -> bool:
    """True when the dependencies import and the model files are already on disk (never downloads)."""
    try:
        import onnxruntime  # noqa: F401
        import tokenizers  # noqa: F401

        _resolve(download=False)
    except (ImportError, OnnxUnavailable):
        return False
    return True


@functools.lru_cache(maxsize=1)
def _runtime():
    try:
        import onnxruntime as ort
        from tokenizers import Tokenizer
    except ImportError as exc:
        raise OnnxUnavailable("onnxruntime/tokenizers are not installed; pip install 'mdb-expertise-search[onnx]'") from exc
    model, tok_path = _resolve(download=False)
    tok = Tokenizer.from_file(str(tok_path))
    tok.enable_truncation(max_length=MAX_TOKENS)
    tok.enable_padding()
    sess = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    log.debug("loaded %s", model)
    return sess, tok, {i.name for i in sess.get_inputs()}


def embed(texts: list[str], *, prefix: str = "search_document: ") -> np.ndarray:
    """Embed ``texts`` (with the nomic task ``prefix``) and return an L2-normalised float32 matrix."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    sess, tok, names = _runtime()
    out: list[np.ndarray] = []
    for i in range(0, len(texts), BATCH):
        enc = tok.encode_batch([prefix + t for t in texts[i:i + BATCH]])
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in names:
            feed["token_type_ids"] = np.zeros_like(ids)
        hidden = sess.run(None, feed)[0]  # (batch, tokens, dim)
        m = mask[..., None].astype(np.float32)
        pooled = (hidden * m).sum(1) / np.maximum(m.sum(1), 1.0)  # mean pooling over real tokens
        out.append(pooled / np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12))
    return np.concatenate(out).astype(np.float32)
