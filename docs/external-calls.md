# External calls

| Call | Where | Purpose | Error handling | Test |
|---|---|---|---|---|
| `POST {OLLAMA}/api/embed` | `mdbx/embed.py:embed` | Embed chunks and queries | `EmbedError`; CLI exits 1 with message; hybrid/TUI fall back to keyword | `test_hybrid_falls_back_without_ollama` |

No retries (a failed batch aborts; re-run `mdbx index` to resume). Timeout 120 s per batch.
