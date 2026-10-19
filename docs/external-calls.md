# External calls

| Call | Where | Purpose | Error handling | Test |
|---|---|---|---|---|
| `POST {OLLAMA}/api/embed` | `mdbx/embed.py:embed` | Embed chunks and queries | `EmbedError`; CLI exits 1 with message; hybrid/TUI fall back to keyword | `test_hybrid_falls_back_without_ollama` |

No retries (a failed batch aborts; re-run `mdbx index` to resume). Timeout 120 s per batch.

Every request is logged on logger `mdbx.embed` (DEBUG per call: host, model, input count; WARNING on failure; no
payload text). A non-JSON body, a missing or wrong-length `embeddings` list, ragged vectors and non-2-D arrays are
all converted to `EmbedError` (`http.client.HTTPException` is caught with the URL/OS errors). Ollama HTTP is the
repo's only external call family; the MQL optimizer, the CLI and the MCP/LSP servers make no other network calls.
