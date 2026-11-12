# Repository instructions

## Architecture

Python 3.11+ implements local search, MQL parsing and stdio MCP/LSP. Chrome ports
MQL and static search to JavaScript; VS Code launches the Python language server.
Use Node 26 for editor checks. Start with docs/wiki/README.md and CLAUDE.md.

## Verification

Read docs/TESTING.md. On macOS, run checks through scripts/offline_test.py.
Dependencies install separately; tests use synthetic inputs and embedding mocks.

## Rules

1. Preserve customer material, credentials, corpus data and frozen vectors.
2. Keep Python and JavaScript MQL behavior paired; refresh only relevant synthetic goldens.
3. Do not evaluate query text or call real models/providers from tests.
4. Match package versions in pyproject.toml and mdbx/__init__.py.
5. Update factual documentation, memory.md and prompts.md for completed work.
6. Deliver task-owned changes through a checked PR; preserve unrelated worktrees.
