# Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'   # public development extras; provider/model extras are opt-in
python3 scripts/offline_test.py -- .venv/bin/python -m pytest -q
python3 scripts/offline_test.py -- .venv/bin/python -m ruff check .
```

| Env var | Default | Meaning |
|---|---|---|
| `MDBX_DB` | `./data/mdbx.sqlite` | Index file |
| `MDBX_CORPUS` | `./corpus` | Corpus root |
| `MDBX_OLLAMA_HOST` / `OLLAMA_HOST` | `http://127.0.0.1:11434` | Embedding backend |
| `MDBX_EMBED_MODEL` | `nomic-embed-text` | Embedding model; an explicitly requested semantic build stages and validates a replacement generation before publication |
| `MDBX_LSP_OPTIMIZE` | `1` | Set `0` to stop `mql-lsp` publishing optimizer (`opt/*`) diagnostics |
| `MDBX_CONCEPTS_SRC` | `~/.global-ai-hub/llms-concepts` | `scripts/sync_corpus.sh` only: source of the `mongodb-*.llms` fact families |

Explicit corpus synchronization and semantic indexing operate on data. They are separate
from offline development checks; use them only for an authorized data refresh. See
[TESTING.md](TESTING.md) for scratch-state, fixture-hook and no-model protections.

## Scripts
- `python scripts/rotate_workflow_logs.py [--check] [--max-bytes N] [--keep N]` — moves all but the newest 3 `## v...`
  sections of `memory.md` and `prompts.md` to `docs/archive/<name>-<date>.md` once a file passes 200 KB; refuses while
  an editor swap file exists. `--check` writes nothing and exits 1 when a rotation is due (CI runs it).
- `scripts/watch_and_index.sh` — needs `fswatch` or `inotifywait`; re-runs `.venv/bin/mdbx index` when `MDBX_CORPUS`
  (default `corpus`) changes.
- `scripts/sync_corpus.sh` — also copies every `mongodb-*.llms` fact family found in `MDBX_CONCEPTS_SRC`
  (`llms.txt`, `llms-facts.txt`, `llms-vocabulary.txt`, `manifest.json`; new families need no script edit). The deep MQL
  optimizer reference ships only in redacted form; re-redact it by hand after a re-sync.
- `scripts/corpus_autoupdate.py install-agent` — keeps the committed corpus current. The corpus is a copy (clones of the
  repo must work without your skill tree), so a launchd agent on the machine that holds the sources runs a refresh in
  its own clone (`~/Library/Caches/mdbx/corpus-autoupdate/repo`) every 6 h by default: sync, redact, sweep (flagged
  files are reverted to their committed text, or dropped when new), commit `corpus/`, push. It aborts without
  `~/.config/mdbx/denylist.txt`. Log: `~/Library/Logs/mdbx-corpus-autoupdate.log`; `run --dry-run` to preview.
- `mdbx optimize FILE|- [--read-only] [--write] [--json]` — static optimizer; `examples/slow-queries.mql` is a sample input.
- `.vscode/mcp.json` — registers `.venv/bin/mdbx mcp` for VS Code.

## Adding an MQL operator or rule
Add a row to `_TABLE` in `mdbx/mql/operators.py` (`name|categories|arg kind|doc`). Context rules live in
`mdbx/mql/analyze.py`; add a case to `tests/test_mql.py::test_diagnostics`. Optimizer rules live in
`mdbx/mql/optimize.py` (`_Audit`); give each a `code`, a pass id and a corpus `ref`, and add a case to `tests/test_optimize.py`.
Customer-safety: `scripts/redact_corpus.py` then `scripts/sweep_customers.py` before committing corpus changes
(put customer-name regexes in `~/.config/mdbx/denylist.txt`, never in the repo).

## VS Code extension
`npm ci --ignore-scripts --prefix editors/vscode`, then the guarded checks in [TESTING.md](TESTING.md), and `editors/vscode/node_modules/.bin/vsce package` builds `mql-vscode-0.1.0.vsix` (git-ignored).

## Troubleshooting
- `semantic index skipped: cannot reach Ollama` — start Ollama and run `ollama pull nomic-embed-text`.
- Empty results — run `mdbx stats`; zero chunks means `mdbx index` has not run or `MDBX_CORPUS` is wrong.
- Changed the embedding model — run `mdbx index`; the explicit semantic build validates a complete replacement before changing stored vectors.
- `corpus directory not found` — `build_keyword` now refuses a missing `MDBX_CORPUS` instead of emptying the index.
- Refresh the file index docs: `python scripts/gen_file_index.py`; verify with `python scripts/check_doc_indexes.py`.
