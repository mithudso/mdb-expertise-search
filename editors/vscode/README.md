# MQL for VS Code

Highlighting and language-server features for `*.mql` files (mongosh-style queries, aggregation pipelines,
updates), backed by `mql-lsp` from [mdb-expertise-search](../../docs/LSP.md): diagnostics, completion, hover,
outline, quick fixes.

## Install
1. Install the server: `pip install -e '.[lsp]'` in the repo (creates `.venv/bin/mql-lsp`).
2. Build the extension: `cd editors/vscode && npm install && npx vsce package` → `mql-vscode-0.1.0.vsix`.
3. VS Code → Extensions → `…` → *Install from VSIX…* (or `code --install-extension mql-vscode-0.1.0.vsix`).
4. Open `examples/orders.mql`.

## Settings
| Setting | Default | Meaning |
|---|---|---|
| `mql.server.path` | `""` | Path to `mql-lsp`. Empty: `<workspace>/.venv/bin/mql-lsp` if present, else `mql-lsp` on PATH |
| `mql.server.args` | `[]` | Extra arguments |
| `mql.trace.server` | `off` | LSP trace in the "MQL Language Server" output channel |

Command: **MQL: Restart Language Server**.

## Status
The pure parts (server path resolution, manifest/grammar consistency) have unit tests (`npm test`). The
extension host itself has not been exercised in an interactive VS Code session by the author's automation.
