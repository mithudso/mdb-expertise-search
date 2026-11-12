# External operations

| Family | Entry points | Payload/state | Failures and verification |
|---|---|---|---|
| Ollama embedding | mdbx/embed.py, Chrome lib/ollama.js | Query text; explicit indexing also sends chunks. Optional private Python client, explicit Chrome permission. | Bounded client timeout/retries; safe EmbedError and observable keyword fallback. Synthetic provider responses and failure tests. |
| ONNX artifacts/runtime | mdbx/embed_onnx.py | Explicit embed-fetch downloads from Hugging Face; ordinary availability uses local files only. Inference stays in process. | Loading/inference errors become typed unavailable errors. Tests replace runtime before collection. No download/inference benchmark in CI. |
| AI/auth/Glean | mdbx/providers.py, scripts/glean_cli_helper.py | Optional ai-auth facade owns provider selection, remote requests, vendor subprocesses and credential stores. ask sends selected context. | Missing optional dependency produces an install hint; facade calls tested with mocks. Upstream private library behavior is outside this audit. |
| Git/GitHub updates | scripts/*autoupdate.py | Explicit update commands and separately installed agents fetch clones/releases; no agent is installed or restarted by maintenance. | Owned clone/destination checks, bounded subprocesses and safe diagnostics; temporary local repositories in tests. |
| Local source synchronization | scripts/sync_corpus.sh and helpers | Reads selected local source families; privacy gates precede optional explicit indexing. | Synthetic files only in tests. No live sync was executed during maintenance. |
| Packaged resources | Chrome fetches data and docs | Extension-relative static resources; no remote code. | Input validation, finite vectors, stale-request and missing-document tests. |
| Packaging/dependency metadata | pip/npm, GitHub Actions | Separate dependency installation and audit metadata queries; package builds use --no-data in CI. | Lockfile and pinned CI actions; no package publication or rolling release on merge. |
| Stdio editors | MCP/LSP and VS Code launcher | Local pipes; LSP may read a local keyword index for hover. | Synthetic stdio sessions with deadlines, UTF-16 positions and cleanup checks. |

Logging records categories, counts and safe error classes, not request bodies,
credentials or raw provider errors. This table is the operations inventory for this
local CLI/editor architecture; a service dashboard or HTTP operations registry would
not represent its runtime. See logging.md and TESTING.md for checks and limitations.
