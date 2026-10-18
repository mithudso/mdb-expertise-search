# MCP server

`mdbx mcp` serves MCP over stdio (install the extra: `pip install -e '.[mcp]'`, uses the `mcp` v2 SDK's
`MCPServer`). Tools:

| Tool | Purpose |
|---|---|
| `mdb_search(query, mode="hybrid", limit=8, kind=None, source=None)` | Search the corpus; returns `path`, `line`, `heading`, `source`, `kind`, `score`, `via`, `text`. Hybrid falls back to keyword if Ollama is down |
| `mdb_show(path, start_line=1, end_line=None)` | Read corpus file lines (capped at 20k chars; path must be inside the corpus) |
| `mdb_recipes(topic=None)` | List step-by-step recipes, optionally filtered by words |
| `mdb_recipe(name)` | Full text of one recipe (exact name or unique words) |
| `mdb_stats()` | Chunk counts by kind, sources, vectors, embedding model |
| `mql_lint(text)` | Lint MQL; returns 1-based line/column, severity, code, message, suggestion |
| `mql_operator(name)` | Operator categories, argument kind, description, or close matches |

Client config (Claude Code / Claude Desktop style):
```json
{ "mcpServers": { "mdbx": { "command": "/ABS/PATH/.venv/bin/mdbx", "args": ["mcp"],
  "env": { "MDBX_DB": "/ABS/PATH/data/mdbx.sqlite" } } } }
```
A project-level `.mcp.json` with the same entry (relative to the repo) is checked in.
