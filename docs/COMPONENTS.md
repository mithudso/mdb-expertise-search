# Components

| Module | Purpose | Key API |
|---|---|---|
| `mdbx/corpus.py` | Discover, classify and chunk corpus files | `iter_chunks`, `chunk_text`, `classify`, `Chunk` |
| `mdbx/embed.py` | Ollama `/api/embed` client (stdlib `urllib`), L2-normalised output | `embed`, `embed_query`, `EmbedError` |
| `mdbx/index.py` | SQLite schema, keyword and semantic index builds, stats | `connect`, `build_keyword`, `build_semantic`, `stats` |
| `mdbx/search.py` | Keyword, semantic and hybrid ranking | `search`, `keyword`, `semantic`, `hybrid`, `VectorStore`, `Hit` |
| `mdbx/cli.py` | `mdbx` command (`index`, `search`, `show`, `stats`, `lint`, `optimize`/`opt`, `tui`, ...) | `main`, `cmd_optimize` |
| `mdbx/tui.py` | Textual app: results table, detail pane, MongoDB-area facets | `MdbxApp`, `run` |
| `mdbx/recipes.py` | Frontmatter parser and lookup for `corpus/recipes/*.md` | `load`, `find`, `Recipe` |
| `editors/chrome/` | MV3 "MongoDB Expertise" extension: popup (optimize the highlighted query, or corpus passages for non-query text), full app (`app.html`: Search with area facets and document view, Recipes, Optimize, Lint, Operators, About), right-click items, `mdb` omnibox keyword; JS ports of search, optimizer, normalizer, parser and linter; packaged search data in `data/`; no network except optional local Ollama | `lib/textsearch.js` (`SearchIndex`, `queryTerms`, `snippet`, `embedQuery`), `lib/store.js`, `lib/optimize.js`, `lib/analyze.js`, `lib/ui.js`, `app.js`, `popup.js` |
| `mdbx/webexport.py` | `mdbx export-web`: writes chunks, BM25 postings/weights, doc lengths and int8 vectors as static files from git-tracked corpus files only; `WebIndex` is the pure-Python reference search (equal to SQLite FTS5 ranking) | `export`, `WebIndex`, `tokens`, `porter`, `query_terms` |
| `editors/vscode/` | VS Code extension (grammar + launcher for `mql-lsp`), packaged with `vsce` | `extension.js`, `server-path.js` |
| `scripts/gen_recipes_index.py` | Regenerates `docs/RECIPES.md` | — |
| `mdbx/mcp_server.py` | MCP server (`MCPServer`, stdio): 8 tools: search, show, recipes (2), stats, MQL lint, MQL optimize, operator lookup | `server`, `run` |
| `mdbx/mql/operators.py` | Built-in table of ~280 MQL operators with categories, argument kinds and docs | `OPERATORS`, `get`, `suggest` |
| `mdbx/mql/parser.py` | Tolerant mongosh/relaxed-JSON parser with offsets | `parse`, `Node`, `Statement` |
| `mdbx/mql/analyze.py` | Context-aware lint, completion contexts, outline | `analyze`, `Diag`, `Result` |
| `mdbx/mql/optimize.py` | Static MQL query optimizer (offline subset of the deep MQL query optimizer audit: P2 index/ESR, P4 operator anti-patterns, P5 stage order, P6 sort/cursor, P7 projection, P8 pagination); applies result-preserving rewrites in a convergence loop | `optimize`, `format_report`, `to_dict`, `Report`, `Finding`, `IndexRec` |
| `mdbx/mql/normalize.py` | Turns pasted case text into mongosh calls: slow-query log lines (incl. `getMore` via `originatingCommand`), profiler entries, command documents, bare filters/pipelines; extended JSON to mongosh literals; keeps log measurements as evidence | `normalize`, `Normalized`, `Query` |
| `mdbx/mql/features.py` | Completion and hover over an analysis | `completions`, `hover_markdown`, `word_at` |
| `mdbx/mql/server.py` | `mql-lsp` language server (pygls); also publishes optimizer findings as diagnostics | `build_server`, `optimizer_diagnostics`, `main` |
| `scripts/redact_corpus.py` | Exact-phrase redaction of customer/internal references | `RULES`, `PRIVATE_FILES` |
| `scripts/sweep_customers.py` | Fails on customer/internal markers in committed corpus files | — |
| `scripts/sync_corpus.sh` | Rebuild `corpus/` from a local skill tree, then reindex | — |
| `scripts/rotate_workflow_logs.py` | Move old `## v...` sections of `memory.md`/`prompts.md` over 200 KB to `docs/archive/`; `--check` for CI | `rotate` |
| `scripts/watch_and_index.sh` | fswatch/inotifywait loop that re-runs `mdbx index` on corpus changes | — |
| `scripts/gen_file_index.py` | Regenerate `docs/high_signal_file_index.json` and `docs/codebase-overview.md` | — |
| `scripts/gen_optimizer_golden.py` | Writes `tests/fixtures/optimizer/*.golden.json` from the Python optimizer (the JS port's contract); `--check` fails on stale goldens | — |
| `scripts/package_chrome_extension.py` | Exports search data, then builds `dist/mongodb-expertise-chrome-<version>.zip` (runtime files + data); `--no-vectors`, `--no-data` | — |
| `scripts/gen_search_golden.py` | Exports `tests/fixtures/search/index/` and writes `golden.json` (keyword/semantic/hybrid reference results); `--check` | — |
| `scripts/gen_lint_golden.py`, `scripts/gen_chrome_operators.py` | Lint goldens and the JS operator table; `--check` | — |
| `scripts/make_chrome_icons.py` | Renders the extension icons with no image library | — |
| `scripts/check_chrome_doc_links.py` | Checks the extension's MongoDB docs links resolve (network) | — |
| `scripts/check_doc_indexes.py` | CI check that every indexed path exists | — |
