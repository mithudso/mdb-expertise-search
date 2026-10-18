# mdb-expertise-search

Hybrid **keyword + semantic** search, as a CLI and a terminal UI, over a curated MongoDB / Atlas
expertise corpus: expert skills (indexes, aggregation, schema design, replication, sharding,
operations, Atlas, diagnostics, drivers, error codes) plus `llms.txt` exports of the MongoDB docs.

- **Keyword**: SQLite FTS5 with BM25 ranking and Porter stemming.
- **Semantic**: [Ollama](https://ollama.com) `nomic-embed-text` embeddings, cosine similarity in NumPy.
- **Hybrid** (default): reciprocal-rank fusion of both. Falls back to keyword when Ollama is down.
- **TUI**: Textual browser with mode/kind cycling, MongoDB-area facets and topic hotkeys.

## Quick start

```bash
git clone https://github.com/mithudso/mdb-expertise-search && cd mdb-expertise-search
python3 -m venv .venv && .venv/bin/pip install -e '.[tui]'
ollama pull nomic-embed-text            # optional; enables semantic search
.venv/bin/mdbx index                    # builds data/mdbx.sqlite (keyword + vectors)
.venv/bin/mdbx search "why is my compound index not used for sort"
.venv/bin/mdbx tui
```

## Commands

| Command | Purpose |
|---|---|
| `mdbx index [--skip-semantic]` | Build the FTS5 index and embed any new chunks (resumable) |
| `mdbx search QUERY [-m hybrid\|keyword\|semantic] [-k skill\|llms\|memory] [-s SOURCE] [-n N] [--full] [--json]` | Search |
| `mdbx show PATH` | Print a corpus file (path as shown in results) |
| `mdbx stats [--sources]` | Index statistics |
| `mdbx tui` | Interactive browser |

TUI keys: `Enter` search, `Ctrl+T` cycle mode, `Ctrl+K` cycle kind, `Ctrl+F` focus MongoDB areas,
`/` focus search, `1`-`9` topic shortcuts, `Esc` clear scope, `q` quit.

## Configuration

`MDBX_DB` (index path), `MDBX_CORPUS` (corpus dir), `MDBX_OLLAMA_HOST` / `OLLAMA_HOST`,
`MDBX_EMBED_MODEL`. See `.env.example`.

## Corpus

`corpus/` holds MongoDB skills (`corpus/skills/`) and `llms.txt`-family exports (`corpus/llms/`).
Some source material is private to the author and is excluded from this repository by
`.gitignore`; `scripts/sync_corpus.sh` rebuilds a full local corpus from your own skill tree.
Point `MDBX_CORPUS` at any directory of `.md` / `.txt` files to index your own material.

## Docs

[Architecture](docs/ARCHITECTURE.md) · [Development](docs/DEVELOPMENT.md) ·
[Components](docs/COMPONENTS.md) · [Testing](docs/TESTING.md) · [Installation](docs/INSTALLATION.md) ·
[Security](docs/SECURITY.md) · [Known issues](docs/known-issues.md) · [Onboarding](docs/onboarding.md)

## License

MIT
