# External calls

| Call | Where | Purpose | Error handling | Test |
|---|---|---|---|---|
| `POST {OLLAMA}/api/embed` | `mdbx/embed.py:embed` | Embed chunks and queries | `EmbedError`; CLI exits 1 with message; hybrid/TUI fall back to keyword | `test_hybrid_falls_back_without_ollama` |
| `POST https://api.anthropic.com/v1/messages` | ai-auth `providers/claude.py` via `mdbx/providers.py:ask` | `mdbx ask` with a Claude API key | `AIAuthError` → exit 1 | ai-auth `test_chat_routes_to_provider` |
| `claude -p`, `codex exec`, `agy -p` / `gemini -p` (subprocess) | ai-auth providers | `mdbx ask` through a vendor OAuth login | non-zero exit → `AIAuthError` | ai-auth tests (stubbed) |
| `POST https://api.openai.com/v1/responses` | ai-auth `providers/codex.py` | `mdbx ask` with an OpenAI key | `AIAuthError` | ai-auth |
| `POST https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent` | ai-auth `providers/antigravity.py` | `mdbx ask` with a Gemini key | `AIAuthError` | ai-auth |
| `POST {GLEAN}/rest/api/v1/search`, `/chat`; `{GLEAN}/oauth/*` | ai-auth `providers/glean.py`, `oauth.py` | `mdbx glean`, `mdbx auth login glean` | `AIAuthError`; `NotConfigured` prints the CLI-fallback hint | ai-auth `test_glean_search_via_rest`, `test_login_end_to_end_with_fake_server` |
| `glean search --json`, `glean api`, `glean auth status/login` (subprocess) | `scripts/glean_cli_helper.py` → ai-auth `glean_helper.py` | Glean CLI fallback | JSON error object; exit 2 not installed, 3 not authenticated; transient-network retry ×2 | ai-auth `test_glean_helper.py` |
| `~/Library/Caches/ai-auth/apple-llm-*` (subprocess, on-device) | ai-auth `providers/apple.py` | Apple Intelligence fallback for `mdbx ask` | `AIAuthError`; `NotConfigured` when unavailable | ai-auth `test_pick_order_and_apple_fallback` |

Ollama: no retries (a failed batch aborts; re-run `mdbx index` to resume). Timeout 120 s per batch.

Every Ollama request is logged on logger `mdbx.embed` (DEBUG per call: host, model, input count; WARNING on failure;
no payload text). A non-JSON body, a missing or wrong-length `embeddings` list, ragged vectors and non-2-D arrays are
all converted to `EmbedError` (`http.client.HTTPException` is caught with the URL/OS errors). The MQL optimizer, the
search CLI, the TUI and the MCP/LSP servers make no network calls.

AI provider calls happen only in `mdbx ask`, `mdbx glean` and `mdbx auth` (the optional `ai` extra). `mdbx ask`
sends the question plus the selected corpus passages (committed, redacted corpus text) to the chosen provider; with
the Apple Intelligence fallback nothing leaves the machine. Credentials never appear in logs (`mdbx.providers` logs
provider name, model and context size only). Chrome extension auto-update: `scripts/chrome_extension_autoupdate.py`
runs `git fetch`/`git pull` on its own clone of this repository (or `gh release download` for the release channel);
the extension itself makes no network request, it re-reads its own `data/build.json`.
