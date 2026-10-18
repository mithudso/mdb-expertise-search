# Testing

`pytest -q` (asyncio auto mode). Suites:
- `tests/test_core.py` — classification, chunking, FTS filters, stopwords, hybrid fallback without
  Ollama, semantic ranking and resumability with fake embeddings, CLI index/search/stats.
- `tests/test_tui.py` — Textual pilot: submits a keyword query and asserts hits (skipped without Textual).

Target: meaningful coverage of ranking, filtering and fallback paths, asserting on behaviour
(returned sources, kinds, resumability), not a line-coverage percentage. CI (`.github/workflows/ci.yml`)
gates on `ruff check .`, `pytest -q` on Python 3.11–3.13 and the doc-index path check.
Real Ollama is never required by tests.
