# Testing

`pytest -q` (asyncio auto mode). Suites:
- `tests/test_core.py` — classification, chunking, FTS filters, stopwords, hybrid fallback without
  Ollama, semantic ranking and resumability with fake embeddings, CLI index/search/stats.
- `tests/test_tui.py` — Textual pilot: submits a keyword query and asserts hits (skipped without Textual).

- `tests/test_mql.py` — operator table, parser recovery, ~25 diagnostic rules (one test per rule), valid
  queries produce no diagnostics, completion contexts, hover, outline.
- `tests/test_lsp_e2e.py` — spawns `python -m mdbx.mql.server` and drives real stdio JSON-RPC: initialize,
  didOpen → publishDiagnostics, codeAction, hover, completion, documentSymbol.
- `tests/test_optimize.py` — static optimizer: one test per rule family (`$where`, regex, negation, `$in` thresholds,
  `$or` -> `$in` rewrite, rooted `$or` + sort, degenerate range, `$expr`, cursor and group rules, `$match` hoisting),
  ESR index recommendations, LSP `opt/` diagnostics and the `MDBX_LSP_OPTIMIZE=0` toggle, report/dict output,
  `mdbx optimize`, no exception on garbage input, every `ref` exists in the corpus.
- `tests/test_cdo_hardening.py` — embed (non-JSON body, ragged vectors, logged failures), `build_keyword` on a
  missing corpus keeps the index, embed-model change purges vectors, query/index dimension mismatch falls back,
  mixed-dimension vectors ignored, semantic filters not starved, recipe text read from the load root.
- `tests/test_recipes.py` — recipe frontmatter, lookup, `-k recipe` search, CLI and MCP recipe tools.
- `tests/test_normalize.py` — log line / getMore / profiler / command / bare-input normalization, extended JSON, P9 evidence findings, `to_dict` input block, goldens current.
- `tests/test_js_parity.py` — runs `editors/chrome/test/batch.mjs` on ~400 inputs (every fixture cut at ~40 points, so half-typed queries exercise parser recovery) and requires identical output to Python; skipped without Node.
- `tests/test_web_search.py` — `export-web`: untracked files never exported, corpus outside git refused, keyword ranking and bm25 scores equal SQLite FTS5, int8 vector round-trip, meta/recipes, CLI, search goldens current, JS search equals Python.
- `tests/test_js_lint_parity.py` — JS linter equals Python on ~860 inputs (fixtures cut at ~40 points), `suggest()` equals difflib on 1,137 words, every diagnostic code has a golden, generated files current.
- `editors/chrome/test/` — `cd editors/chrome && npm test` (node:test, 130 tests): search parity with `tests/fixtures/search/golden.json` (keyword, semantic, hybrid, filters), lint parity, optimizer parity, stemmer/tokenizer/snippet units, Ollama client errors, runtime-script syntax, manifest permissions, no HTML injection; earlier (optimizer extension): JS optimizer equals every golden (`apply`, `read_only` and the text report), selection picking, context-menu handoff, Markdown case note, docs-link coverage, manifest permissions, no HTML injection. `test/e2e.mjs` (opt-in, Playwright + Chromium) loads the unpacked extension and checks selection capture, the handoff, rendering and the clipboard, then (with packaged data) the popup corpus fallback, app search/facets/document view, recipes, lint, operators, about, optimizer corpus links and the right-click lint handoff.
- `editors/vscode/test/` — `cd editors/vscode && npm test` (node:test): server-path resolution, manifest/grammar consistency.
- `tests/test_mcp.py` — calls the MCP tool functions against a temp index (Ollama unreachable → keyword fallback); asserts the registered tool list and `mql_optimize`.

Target: meaningful coverage of ranking, filtering and fallback paths, asserting on behaviour
(returned sources, kinds, resumability), not a line-coverage percentage. CI (`.github/workflows/ci.yml`)
gates on `ruff check .`, `pytest -q` on Python 3.11–3.13, `sweep_customers.py`, `rotate_workflow_logs.py --check`, an optimizer smoke test
(`mdbx optimize --read-only examples/slow-queries.mql`, exit 1 allowed) the Chrome extension tests and zip build, and the doc-index path check.
Current count: 150+ tests passing (`.venv/bin/pytest -q`).
Real Ollama is never required by tests.
