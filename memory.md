# memory.md — operator log

## v0.2.0 — 2026-10-17
- Repo made private pending a full customer-info sweep (user request).
- Redaction: `scripts/redact_corpus.py` (exact-phrase rules) + `scripts/sweep_customers.py` (built-in markers +
  denylist at ~/.config/mdbx/denylist.txt). Still local-only: uber-mongodb-skill.md, memory-central rows,
  atlas-diagnostics-expert SKILL.md + atlas-diagnostics-package.md (internal hosts/repos).
- Added MCP server `mdbx mcp` (mcp 2.x `MCPServer`; v1 `FastMCP` import fails) with 5 tools.
- Added MQL language server `mql-lsp` (pygls 2.1, Full sync) + `mdbx lint`; 280-operator table, tolerant parser,
  ~25 lint rules, completion, hover (+ corpus hits), outline, quick fixes. 52+ tests incl. stdio e2e.

## v0.1.0 — 2026-10-17
- Created project: corpus copied (MongoDB skills + llms exports), FTS5 + Ollama semantic indexes,
  `mdbx` CLI (`index`, `search`, `show`, `stats`, `tui`), Textual TUI, tests, CI.
- Withheld from the public repo: `uber-mongodb-skill.md`, memory-central rows and skill files that
  mention customers or internal tooling (see `.gitignore`). They are still indexed locally.
- Bootstrapped docs to the mdb-tam standard (Python-applicable subset).

### Next
- Add `mdbx` MCP server (see `docs/known-issues.md`).
- Redact private skill files so they can ship publicly.
