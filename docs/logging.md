# Logging

The CLI writes progress and errors to **stderr** (`index` progress, "semantic index skipped: …",
"no results") and results to stdout, so `--json` output stays pipe-safe. There is no log file and no
secret or query logging. The TUI surfaces status and Ollama failures in its status line. Embedding
failures are raised as `EmbedError` and handled at the CLI/TUI boundary (keyword fallback).

Python `logging` loggers (the package configures no handlers; the host application or `logging.basicConfig`
decides where records go):

| Logger | Records |
|---|---|
| `mdbx.embed` | DEBUG per Ollama request (`POST <host>/api/embed model=... inputs=N`); WARNING when the request fails, the body is not JSON, or the response shape is wrong |
| `mdbx.index` | WARNING when the embed model changed (vectors discarded) or when no chunks were found under the corpus |
| `mdbx.search` | WARNING when inconsistent vectors are ignored (re-run `mdbx index`) |
| `mdbx.tui` | WARNING when semantic search is unavailable (keyword fallback); exception log when a sqlite error aborts a search |
| `mql-lsp` | Server events; WARNING (with traceback) if the optimizer fails and only lint diagnostics are published |

Request bodies (corpus text, queries) are never logged, only the model name and the number of inputs.
