# Maintained documentation index

This index links authoritative maintained documentation. Corpus data and generated
semantic stores are outside this documentation-maintenance surface.

| Topic | Start here |
|---|---|
| Product and commands | [README](../../README.md) |
| Install and optional backends | [Installation](../INSTALLATION.md) |
| Development | [Development](../DEVELOPMENT.md), [CLAUDE.md](../../CLAUDE.md) |
| Architecture and components | [Architecture](../ARCHITECTURE.md), [Components](../COMPONENTS.md) |
| Verification and safety | [Testing](../TESTING.md), [Security](../SECURITY.md) |
| External operations | [External calls](../external-calls.md), [Logging](../logging.md) |
| Editor and agent tools | [LSP](../LSP.md), [MCP](../MCP.md), [Chrome](../../editors/chrome/README.md), [VS Code](../../editors/vscode/README.md) |
| Runbooks and recipes | [Recipe index](../RECIPES.md), [Rebuild index](../runbooks/rebuild-index.md) |
| Retrieval navigation | [Codebase overview](../codebase-overview.md), [Static file index](../high_signal_file_index.json) |
| Limits and maintenance evidence | [Known issues](../known-issues.md), [2026-11-12 audit](../repo-bootstrap-audit-2026-11-12.md) |

Regenerate code navigation with `python scripts/gen_file_index.py`; validate with
`python scripts/check_doc_indexes.py`. These operations do not create embeddings.
