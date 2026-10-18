# Known issues

- `mdbx index` rebuilds the keyword index from scratch every run (fast) but does not drop vectors for
  changed text until the rebuild finishes; stale digests are pruned automatically.
- Semantic search brute-forces all vectors; fine at ~10k chunks, would need an ANN index at 1M+.
- Local-only corpus files (cannot be redacted): `uber-mongodb-skill.md`, memory-central rows, two internal
  Atlas-diagnostics skill files, the ts-diag skill/llms set and the kb-backed-troubleshooting stubs.
- Git history of this private repo contains an early version of `scripts/redact_corpus.py` with customer
  names in its rules. **Do not flip this repo to public.** Publish by creating a fresh repository from a
  squashed snapshot (no history) after the final manual review.
- Recipe citations are `path:line` against the corpus as of the redaction pass; line numbers drift if corpus
  files are re-synced or edited. Recipes mark unconfirmed steps with "Verify in the current MongoDB docs:". The repo is private until a full customer-information sweep is done;
  the sweep tool only checks built-in markers plus a denylist kept outside the repo.
- The VS Code extension is packaged and its pure logic is unit-tested, but it has not been exercised in an
  interactive VS Code session by automation; report problems with `mql.trace.server = verbose`.
- `mql-lsp` is static: no server connection, schema or index awareness; the operator table is not versioned
  per MongoDB release, so brand-new operators warn as "not in table". Completion offers operators by context but
  not field names. `$function`/`$where` JavaScript bodies are not parsed.
- The parser handles mongosh-style statements, not full JavaScript (no arrow functions, template expressions,
  spread, or loops).
- MCP uses the v2 SDK (`mcp.server.mcpserver.MCPServer`); v1 `FastMCP` code does not run on it.
- Natural-language queries fall back from AND to OR keyword matching; very long queries can be noisy.
- The TUI test covers keyword mode only (no Ollama in CI).
