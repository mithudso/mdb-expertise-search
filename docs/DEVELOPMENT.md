# Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[tui,dev]'
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/mdbx index --skip-semantic     # fast: keyword only
.venv/bin/mdbx index                      # + embeddings (needs Ollama + nomic-embed-text)
```

| Env var | Default | Meaning |
|---|---|---|
| `MDBX_DB` | `./data/mdbx.sqlite` | Index file |
| `MDBX_CORPUS` | `./corpus` | Corpus root |
| `MDBX_OLLAMA_HOST` / `OLLAMA_HOST` | `http://127.0.0.1:11434` | Embedding backend |
| `MDBX_EMBED_MODEL` | `nomic-embed-text` | Embedding model |

## Troubleshooting
- `semantic index skipped: cannot reach Ollama` — start Ollama and run `ollama pull nomic-embed-text`.
- Empty results — run `mdbx stats`; zero chunks means `mdbx index` has not run or `MDBX_CORPUS` is wrong.
- Changed the embedding model — delete `data/mdbx.sqlite` (vectors from different models are incompatible).
- Refresh the file index docs: `python scripts/gen_file_index.py`; verify with `python scripts/check_doc_indexes.py`.
