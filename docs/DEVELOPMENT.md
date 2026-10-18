# Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'   # dev pulls in all extras
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

## Adding an MQL operator or rule
Add a row to `_TABLE` in `mdbx/mql/operators.py` (`name|categories|arg kind|doc`). Context rules live in
`mdbx/mql/analyze.py`; add a case to `tests/test_mql.py::test_diagnostics`.
Customer-safety: `scripts/redact_corpus.py` then `scripts/sweep_customers.py` before committing corpus changes
(put customer-name regexes in `~/.config/mdbx/denylist.txt`, never in the repo).

## VS Code extension
`cd editors/vscode && npm install && npm test && npx vsce package` builds `mql-vscode-0.1.0.vsix` (git-ignored).

## Troubleshooting
- `semantic index skipped: cannot reach Ollama` — start Ollama and run `ollama pull nomic-embed-text`.
- Empty results — run `mdbx stats`; zero chunks means `mdbx index` has not run or `MDBX_CORPUS` is wrong.
- Changed the embedding model — delete `data/mdbx.sqlite` (vectors from different models are incompatible).
- Refresh the file index docs: `python scripts/gen_file_index.py`; verify with `python scripts/check_doc_indexes.py`.
