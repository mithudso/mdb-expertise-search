# CLAUDE.md

Project: `mdb-expertise-search` (`mdbx`) — hybrid search CLI/TUI over a MongoDB expertise corpus.

## Commands
- Setup: `python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
- Test: `.venv/bin/pytest -q` · Lint: `.venv/bin/ruff check .`
- Index: `.venv/bin/mdbx index` · Search: `.venv/bin/mdbx search "..."` · TUI: `.venv/bin/mdbx tui`

## Rules
- Code lives in `mdbx/`; version in `pyproject.toml` and `mdbx/__init__.py` must match.
- Run `python3 scripts/redact_corpus.py && python3 scripts/sweep_customers.py` after any corpus change.
- MQL LSP/lint code is in `mdbx/mql/`; the MCP server is `mdbx/mcp_server.py` (mcp v2 SDK, `MCPServer`).
- Never commit `data/`, `.venv/`, or the private corpus paths listed in `.gitignore`.
- Never put customer names, account figures or internal tooling notes into `corpus/` files that are committed.
- Keep `pytest` and `ruff` green before committing; update `docs/` when behavior changes.
- Log every completed change in `memory.md`; append every user request to `prompts.md`.
- Do not invent commands, paths or env vars — read the code.
