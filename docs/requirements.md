# Requirements

Functional: index a directory of `.md`/`.txt`; keyword, semantic and hybrid search with kind/source
filters; JSON output; browse in a TUI; validated explicit embedding generations; static MQL query optimization (`mdbx optimize`, MCP
`mql_optimize`, LSP `opt/*` diagnostics): report findings by severity, recommend ESR indexes, apply only
result-preserving rewrites, exit 1 on high/blocking findings, never connect to a cluster.
Non-functional: no server; works offline for keyword search; index of ~11k chunks builds keyword-only in
seconds; embedding failures are logged and degrade to keyword search. Dependencies: `numpy` (runtime), `textual`/`rich` (TUI extra), `pytest`, `pytest-asyncio`, `ruff` (dev).


Maintenance requirements: preserve corpus data/frozen vectors; test only synthetic
state with descendant egress isolation and collection-time embedding mocks; deliver
through passing CI and verified remote contents. Static code navigation lives in
docs/wiki/README.md and high_signal_file_index.json. This CLI/editor architecture
has no HTTP application server, dashboard or remote remediation service to scaffold.
