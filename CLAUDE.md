# CLAUDE.md

Project: `mdb-expertise-search` (`mdbx`) — hybrid search CLI/TUI over a MongoDB expertise corpus.

## Commands
- Setup: `python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
- Offline macOS tests: `python3 scripts/offline_test.py -- .venv/bin/python -m pytest -q`; lint: `python3 scripts/offline_test.py -- .venv/bin/ruff check .`. See docs/TESTING.md before executing checks.
- Index: `.venv/bin/mdbx index` · Search: `.venv/bin/mdbx search "..."` · TUI: `.venv/bin/mdbx tui`
- MQL: `.venv/bin/mdbx lint FILE` · `.venv/bin/mdbx optimize FILE|- [--read-only] [--write] [--json]` (exit 1 on high/blocking)
- Chrome extension: `cd editors/chrome && npm test` · package (exports search data to `editors/chrome/data/`): `python3 scripts/package_chrome_extension.py` · export only: `mdbx export-web DIR`
- Logs: `python3 scripts/rotate_workflow_logs.py --check` (rotate `memory.md`/`prompts.md` over 200 KB) · Reindex on change: `scripts/watch_and_index.sh`
- AI providers (optional `ai` extra = the `ai-auth` library at `~/dev/libraries/ai-auth`, app namespace `mdbx`): `mdbx auth status|set-key|login|test` · `mdbx ask "..."` (corpus RAG, Apple Intelligence fallback) · `mdbx glean "..."` (token → OAuth → `scripts/glean_cli_helper.py`). Provider logic lives in the library, not here; `mdbx/providers.py` is the adapter.
- Chrome extension auto-update: `python3 scripts/chrome_extension_autoupdate.py install-agent` (launchd, polls GitHub, rebuilds, swaps the unpacked folder; the extension reloads itself from `data/build.json`).

## Rules
- Code lives in `mdbx/`; version in `pyproject.toml` and `mdbx/__init__.py` must match.
- Run `python3 scripts/redact_corpus.py && python3 scripts/sweep_customers.py` after any corpus change.
- MQL LSP/lint/optimizer code is in `mdbx/mql/` (`optimize.py`; `MDBX_LSP_OPTIMIZE=0` disables LSP optimizer diagnostics); the MCP server is `mdbx/mcp_server.py` (mcp v2 SDK, `MCPServer`).
- Browser search is a port too: `mdbx/webexport.py` (`WebIndex`, equal to SQLite FTS5 ranking) is the reference for `editors/chrome/lib/textsearch.js`; after changing tokenizing, ranking or the export format run `python3 scripts/gen_search_golden.py`. The linter port (`lib/analyze.js`) follows `mdbx/mql/analyze.py` via `python3 scripts/gen_lint_golden.py` and `gen_chrome_operators.py`. Never export untracked corpus files.
- The optimizer has two implementations: Python (`mdbx/mql/optimize.py`, `normalize.py`) is the reference; `editors/chrome/lib/*.js` is a port. After any rule change run `python3 scripts/gen_optimizer_golden.py`, port the change to JS, and keep `cd editors/chrome && npm test` and `tests/test_js_parity.py` green.
- Never commit `data/`, `.venv/`, or the private corpus paths listed in `.gitignore`.
- Recipes live in `corpus/recipes/*.md` with frontmatter (name, title, summary, applies_to, sources); regenerate `docs/RECIPES.md` with `python3 scripts/gen_recipes_index.py`.
- Customer-name redaction rules and the denylist stay OUTSIDE the repo (`~/.config/mdbx/`); never add customer names to any committed file.
- Never put customer names, account figures or internal tooling notes into `corpus/` files that are committed.
- Keep `pytest` and `ruff` green before committing; update `docs/` when behavior changes.
- Log every completed change in `memory.md`; append every user request to `prompts.md`.
- Do not invent commands, paths or env vars — read the code.

## Repository shape and runtime

Python 3.11+ owns parsing, indexing, CLI, optional Textual UI and stdio MCP/LSP.
Chrome uses native JavaScript modules; VS Code uses a Node language client. Node 26
is the tested tool runtime (`.node-version`). There is no application HTTP server,
central dashboard or operations registry. See [docs/wiki/README.md](docs/wiki/README.md).

## Maintenance boundaries

Use synthetic fixtures for tests. Do not run corpus sync, live indexing, model
fetches, provider authentication, service installation or extension activation as
part of routine verification. Tests isolate model/data paths before collection,
block Python sockets and inherit a narrow filter for the known semantic Git hook;
macOS checks also use `scripts/offline_test.py` for descendant egress isolation.
Preserve every other validation/registry hook. Dependency installation is separate.

The default install supports keyword search. Install the private `ollama` extra
when authorized and authenticated; `onnx` and `ai` remain explicit extras. Static
retrieval indexes may be regenerated; semantic indexes require separate approval.
