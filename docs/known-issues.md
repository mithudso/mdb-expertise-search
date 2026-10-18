# Known issues

- `mdbx index` rebuilds the keyword index from scratch every run (fast) but does not drop vectors for
  changed text until the rebuild finishes; stale digests are pruned automatically.
- Semantic search brute-forces all vectors; fine at ~10k chunks, would need an ANN index at 1M+.
- No MCP server yet (agents use `mdbx search --json`).
- Published corpus omits private files (customer/internal-flavoured); redacting them would let them ship.
- Natural-language queries fall back from AND to OR keyword matching; very long queries can be noisy.
- The TUI test covers keyword mode only (no Ollama in CI).
