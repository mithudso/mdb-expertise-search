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
| `editors/vscode/` | VS Code extension (grammar + launcher for `mql-lsp`), packaged with `vsce` | `extension.js`, `server-path.js` |
| `scripts/gen_recipes_index.py` | Regenerates `docs/RECIPES.md` | — |
| `mdbx/mcp_server.py` | MCP server (`MCPServer`, stdio): 8 tools: search, show, recipes (2), stats, MQL lint, MQL optimize, operator lookup | `server`, `run` |
| `mdbx/mql/operators.py` | Built-in table of ~280 MQL operators with categories, argument kinds and docs | `OPERATORS`, `get`, `suggest` |
| `mdbx/mql/parser.py` | Tolerant mongosh/relaxed-JSON parser with offsets | `parse`, `Node`, `Statement` |
| `mdbx/mql/analyze.py` | Context-aware lint, completion contexts, outline | `analyze`, `Diag`, `Result` |
| `mdbx/mql/optimize.py` | Static MQL query optimizer (offline subset of the deep MQL query optimizer audit: P2 index/ESR, P4 operator anti-patterns, P5 stage order, P6 sort/cursor, P7 projection, P8 pagination); applies result-preserving rewrites in a convergence loop | `optimize`, `format_report`, `to_dict`, `Report`, `Finding`, `IndexRec` |
| `mdbx/mql/features.py` | Completion and hover over an analysis | `completions`, `hover_markdown`, `word_at` |
| `mdbx/mql/server.py` | `mql-lsp` language server (pygls); also publishes optimizer findings as diagnostics | `build_server`, `optimizer_diagnostics`, `main` |
| `scripts/redact_corpus.py` | Exact-phrase redaction of customer/internal references | `RULES`, `PRIVATE_FILES` |
| `scripts/sweep_customers.py` | Fails on customer/internal markers in committed corpus files | — |
| `scripts/sync_corpus.sh` | Rebuild `corpus/` from a local skill tree, then reindex | — |
| `scripts/rotate_workflow_logs.py` | Move old `## v...` sections of `memory.md`/`prompts.md` over 200 KB to `docs/archive/`; `--check` for CI | `rotate` |
| `scripts/watch_and_index.sh` | fswatch/inotifywait loop that re-runs `mdbx index` on corpus changes | — |
| `scripts/gen_file_index.py` | Regenerate `docs/high_signal_file_index.json` and `docs/codebase-overview.md` | — |
| `scripts/check_doc_indexes.py` | CI check that every indexed path exists | — |
