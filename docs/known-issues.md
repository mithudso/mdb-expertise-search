# Known issues

- `mdbx index` rebuilds the keyword index from scratch every run (fast) but does not drop vectors for
  changed text until the rebuild finishes; stale digests are pruned automatically.
- Semantic search brute-forces all vectors; fine at ~10k chunks, would need an ANN index at 1M+.
- Four corpus files cannot be redacted and stay local-only (`uber-mongodb-skill.md`, memory-central rows,
  two internal-tooling skill files). The repo is private until a full customer-information sweep is done;
  the sweep tool only checks built-in markers plus a denylist kept outside the repo.
- `mql-lsp` is static: no server connection, schema or index awareness; the operator table is not versioned
  per MongoDB release, so brand-new operators warn as "not in table". Completion offers operators by context but
  not field names. `$function`/`$where` JavaScript bodies are not parsed.
- The parser handles mongosh-style statements, not full JavaScript (no arrow functions, template expressions,
  spread, or loops).
- MCP uses the v2 SDK (`mcp.server.mcpserver.MCPServer`); v1 `FastMCP` code does not run on it.
- Natural-language queries fall back from AND to OR keyword matching; very long queries can be noisy.
- The TUI test covers keyword mode only (no Ollama in CI).
