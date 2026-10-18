# Components

| Module | Purpose | Key API |
|---|---|---|
| `mdbx/corpus.py` | Discover, classify and chunk corpus files | `iter_chunks`, `chunk_text`, `classify`, `Chunk` |
| `mdbx/embed.py` | Ollama `/api/embed` client (stdlib `urllib`), L2-normalised output | `embed`, `embed_query`, `EmbedError` |
| `mdbx/index.py` | SQLite schema, keyword and semantic index builds, stats | `connect`, `build_keyword`, `build_semantic`, `stats` |
| `mdbx/search.py` | Keyword, semantic and hybrid ranking | `search`, `keyword`, `semantic`, `hybrid`, `VectorStore`, `Hit` |
| `mdbx/cli.py` | `mdbx` command (`index`, `search`, `show`, `stats`, `tui`) | `main` |
| `mdbx/tui.py` | Textual app: results table, detail pane, MongoDB-area facets | `MdbxApp`, `run` |
| `scripts/sync_corpus.sh` | Rebuild `corpus/` from a local skill tree, then reindex | — |
| `scripts/gen_file_index.py` | Regenerate `docs/high_signal_file_index.json` and `docs/codebase-overview.md` | — |
| `scripts/check_doc_indexes.py` | CI check that every indexed path exists | — |
