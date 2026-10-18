# Logging

The CLI writes progress and errors to **stderr** (`index` progress, "semantic index skipped: …",
"no results") and results to stdout, so `--json` output stays pipe-safe. There is no log file and no
secret or query logging. The TUI surfaces status and Ollama failures in its status line. Embedding
failures are raised as `EmbedError` and handled at the CLI/TUI boundary (keyword fallback).
