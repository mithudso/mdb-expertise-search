# Installation

Prerequisites: Python ≥ 3.11; optional [Ollama](https://ollama.com) with `nomic-embed-text` for semantic search.

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[tui]'
.venv/bin/mdbx index && .venv/bin/mdbx stats     # expect chunks > 0 (and vectors > 0 with Ollama)
```
Upgrade: `git pull && .venv/bin/pip install -e '.[tui]' && .venv/bin/mdbx index`.
Uninstall: `pip uninstall mdb-expertise-search` and delete `data/`.
