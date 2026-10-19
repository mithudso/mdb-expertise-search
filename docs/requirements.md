# Requirements

Functional: index a directory of `.md`/`.txt`; keyword, semantic and hybrid search with kind/source
filters; JSON output; browse in a TUI; resumable embedding; static MQL query optimization (`mdbx optimize`, MCP
`mql_optimize`, LSP `opt/*` diagnostics): report findings by severity, recommend ESR indexes, apply only
result-preserving rewrites, exit 1 on high/blocking findings, never connect to a cluster.
Non-functional: no server; works offline for keyword search; index of ~11k chunks builds keyword-only in
seconds; embedding failures are logged and degrade to keyword search. Dependencies: `numpy` (runtime), `textual`/`rich` (TUI extra), `pytest`, `pytest-asyncio`, `ruff` (dev).
