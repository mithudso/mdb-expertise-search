# MCP server

`mdbx mcp` serves MCP over stdio (install the extra: `pip install -e '.[mcp]'`, uses the `mcp` v2 SDK's
`MCPServer`). Eight tools:

| Tool | Purpose |
|---|---|
| `mdb_search(query, mode="hybrid", limit=8, kind=None, source=None)` | Search the corpus; returns `path`, `line`, `heading`, `source`, `kind`, `score`, `via`, `text`. Hybrid falls back to keyword if Ollama is down |
| `mdb_show(path, start_line=1, end_line=None)` | Read corpus file lines (capped at 20k chars; path must be inside the corpus) |
| `mdb_recipes(topic=None)` | List step-by-step recipes, optionally filtered by words |
| `mdb_recipe(name)` | Full text of one recipe (exact name or unique words) |
| `mdb_stats()` | Chunk counts by kind, sources, vectors, embedding model |
| `mql_lint(text)` | Lint MQL; returns 1-based line/column, severity, code, message, suggestion |
| `mql_optimize(text, apply=True)` | Static MQL query optimizer: findings (`severity` blocking/high/medium/low, `code`, `pass` P2-P8, `ref` for `mdb_show`), ESR index recommendations (recommend-only), and with `apply` the text with result-preserving rewrites (`rewritten`, `applied`, `iterations`) |
| `mql_operator(name)` | Operator categories, argument kind, description, or close matches |

`mql_optimize` example (arguments, then the shape of the result):
```json
{ "text": "db.orders.find({ $or: [{ status: 'a' }, { status: 'b' }] }).sort({ ts: -1 })", "apply": true }
```
```json
{ "queries": [...], "findings": [{ "severity": "medium", "code": "...", "pass": "P4", "message": "...", "ref": "skills/mongodb-expert/references/...", "line": 1, "column": 1 }],
  "applied": [{ "code": "or-to-in", "pass": "P4", "message": "..." }],
  "indexes": [{ "collection": "orders", "keys": { "status": 1, "ts": -1 }, "shell": "db.orders.createIndex(...)", "rationale": "..." }],
  "rewritten": "db.orders.find({ status: { $in: ['a', 'b'] } })...", "iterations": 2 }
```
Results are static: confirm with `explain('executionStats')` on a cluster before building an index.

Client config (Claude Code / Claude Desktop style):
```json
{ "mcpServers": { "mdbx": { "command": "/ABS/PATH/.venv/bin/mdbx", "args": ["mcp"],
  "env": { "MDBX_DB": "/ABS/PATH/data/mdbx.sqlite" } } } }
```
A project-level `.mcp.json` with the same entry (relative to the repo) is checked in.
