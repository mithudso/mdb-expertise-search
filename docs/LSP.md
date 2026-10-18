# MQL language server (`mql-lsp`)

A Language Server Protocol server for MQL — mongosh-style queries, aggregation pipelines and updates —
installed with the `lsp` extra: `pip install -e '.[lsp]'`. It speaks LSP over stdio (`mql-lsp`).
Files: `*.mql` (language id `mql`). The parser is tolerant, so features keep working while you type.

## What it understands
- Statements: `db.coll.find({...}).sort({...})`, `aggregate([...])`, `updateOne(filter, update)`, `const p = [...]`
  (a pipeline variable passed to `aggregate(p)` is analysed with that context), bare pipelines/queries,
  `ObjectId(...)`, `ISODate(...)`, regex literals, comments, `use db` lines.
- Contexts: query documents, field operators, aggregation expressions, projections, `$group` accumulators,
  `$sort`, `$lookup`, update documents and `$push` modifiers, pipelines (including `$facet`, `$unionWith`,
  `$lookup.pipeline`, update pipelines).

## Features
| Feature | Details |
|---|---|
| Diagnostics | Syntax errors; unknown operators (with did-you-mean); operators in the wrong context; bad argument types/arity; missing `$group._id`, `$lookup` fields, `$replaceRoot.newRoot`, `$vectorSearch` fields; stage position rules (`$out`/`$merge` last, `$geoNear`/`$search`/`$vectorSearch` first, none allowed in `$facet`, update-pipeline stage whitelist, `$text` first); `$unwind` path without `$`; `$sort` order values; inclusion/exclusion mixing in projections; mixed operators and plain fields in updates; removed operators (`$pushAll`, `$isolated`); duplicate keys; `$where` performance warning |
| Completion | Operators filtered by context (stages in a pipeline stage object, `$gt`… inside a field, `$set`… in an update, `$each`… in `$push`, accumulators in `$group`), `$$` system variables, collection methods after `db.coll.`, stage snippets inside a pipeline array |
| Hover | Operator docs and argument kind; system variables; when an mdbx index exists, up to two related corpus passages (`path:line`) |
| Document symbols | One symbol per statement with pipeline stages as children |
| Code actions | Quick fix to replace a misspelled operator with the suggested one |

Severity: unknown operators with a close match are errors; unrecognised names with no close match are
warnings (the built-in table may lag new server releases).

## Editor setup
Neovim (0.11+):
```lua
vim.filetype.add({ extension = { mql = "mql" } })
vim.lsp.config("mql", { cmd = { "/ABS/PATH/.venv/bin/mql-lsp" }, filetypes = { "mql" } })
vim.lsp.enable("mql")
```
Helix (`languages.toml`):
```toml
[language-server.mql-lsp]
command = "/ABS/PATH/.venv/bin/mql-lsp"
[[language]]
name = "mql"
scope = "source.mql"
file-types = ["mql"]
language-servers = ["mql-lsp"]
```
Emacs (eglot): `(add-to-list 'eglot-server-programs '(mql-mode . ("/ABS/PATH/.venv/bin/mql-lsp")))`.
Any editor with a generic LSP client works: point it at the `mql-lsp` command for `*.mql` files.

CLI equivalent: `mdbx lint file.mql` prints the same diagnostics (exit 1 on errors); `-` reads stdin.

## Limits
Static analysis only — no connection to a server, no schema or index awareness, no JavaScript evaluation
(`$function`/`$where` bodies are not parsed). Operator knowledge is a built-in table
(`mdbx/mql/operators.py`), not tied to a server version.
