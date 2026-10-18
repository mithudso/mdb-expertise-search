# Testing

`pytest -q` (asyncio auto mode). Suites:
- `tests/test_core.py` — classification, chunking, FTS filters, stopwords, hybrid fallback without
  Ollama, semantic ranking and resumability with fake embeddings, CLI index/search/stats.
- `tests/test_tui.py` — Textual pilot: submits a keyword query and asserts hits (skipped without Textual).

- `tests/test_mql.py` — operator table, parser recovery, ~25 diagnostic rules (one test per rule), valid
  queries produce no diagnostics, completion contexts, hover, outline.
- `tests/test_lsp_e2e.py` — spawns `python -m mdbx.mql.server` and drives real stdio JSON-RPC: initialize,
  didOpen → publishDiagnostics, codeAction, hover, completion, documentSymbol.
- `tests/test_recipes.py` — recipe frontmatter, lookup, `-k recipe` search, CLI and MCP recipe tools.
- `editors/vscode/test/` — `cd editors/vscode && npm test` (node:test): server-path resolution, manifest/grammar consistency.
- `tests/test_mcp.py` — calls the MCP tool functions against a temp index (Ollama unreachable → keyword fallback).

Target: meaningful coverage of ranking, filtering and fallback paths, asserting on behaviour
(returned sources, kinds, resumability), not a line-coverage percentage. CI (`.github/workflows/ci.yml`)
gates on `ruff check .`, `pytest -q` on Python 3.11–3.13 and the doc-index path check.
Real Ollama is never required by tests.
