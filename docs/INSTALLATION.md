# Installation

Prerequisites: Python ≥ 3.11; optional [Ollama](https://ollama.com) with `nomic-embed-text` for semantic search.

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[all]'   # extras: tui, lsp, mcp
.venv/bin/mdbx index && .venv/bin/mdbx stats     # expect chunks > 0 (and vectors > 0 with Ollama)
```
## Semantic search without Ollama

Search embeds only the query at run time; document vectors are already in the index. Install the `onnx` extra
(Python 3.11–3.13; `onnxruntime` has no wheel for 3.15) and download the model once (~550 MB, Hugging Face cache):

```bash
.venv/bin/pip install -e '.[onnx]' && .venv/bin/mdbx embed-fetch
```

`MDBX_EMBED_BACKEND` = `auto` (default: Ollama first, in-process model when Ollama is unreachable), `ollama`, or
`onnx` (never contacts Ollama). The model is nomic-embed-text v1.5 fp32, the same model Ollama serves; vectors match
an Ollama-built index (mean cosine 0.999), so no reindex. `MDBX_ONNX_MODEL=DIR` points at a folder with
`model.onnx` + `tokenizer.json` for offline installs. Do not swap in the int8 export: its vectors differ (0.94).

Upgrade: `git pull && .venv/bin/pip install -e '.[tui]' && .venv/bin/mdbx index`.
Uninstall: `pip uninstall mdb-expertise-search` and delete `data/`.

## AI providers (`mdbx ask`, `mdbx glean`, `mdbx auth`)

The `ai` extra installs the [ai-auth](https://github.com/mithudso/ai-auth) library (private repo; from a
local checkout use `.venv/bin/pip install -e ~/dev/libraries/ai-auth`). It gives `mdbx` one credential layer
for Claude, Codex (OpenAI), Antigravity (Gemini) and Glean, plus an on-device Apple Intelligence fallback.
Settings live in `~/.config/mdbx/config.json`; secrets go to the macOS Keychain (service `ai-auth/mdbx`),
or `~/.config/mdbx/secrets.json` (0600) when there is no Keychain.

```bash
.venv/bin/pip install -e '.[ai]'            # or: pip install -e ~/dev/libraries/ai-auth
mdbx auth status                             # what each provider would use right now
mdbx auth set-key claude                     # API key (prompted; or --stdin / VALUE)       ANTHROPIC_API_KEY also works
mdbx auth login claude                       # OAuth: `claude auth login` (Claude.ai or --mode console)
mdbx auth set-key codex | login codex        # OPENAI_API_KEY, or `codex login` (ChatGPT)
mdbx auth set-key antigravity | login antigravity   # GEMINI_API_KEY, or the agy / gemini CLI sign-in
mdbx auth set-key glean --base-url https://<tenant>-be.glean.com    # GLEAN_API_TOKEN + base URL
mdbx auth login glean                        # OAuth (PKCE) against the tenant; tokens stored + refreshed
mdbx auth login glean --mode cli             # Glean CLI fallback: `glean auth login`
mdbx auth prefer codex claude                # LLM fallback order (Apple Intelligence is always last)
mdbx auth test                               # one-line probe through every provider
```

Resolution order per provider: stored key → env var → OAuth session / vendor CLI login. `mdbx ask` walks
claude → codex → antigravity (or your `prefer` order) and falls back to Apple Intelligence on a Mac
running macOS 26+ with Apple Intelligence enabled (needs the Xcode Command Line Tools once:
`xcode-select --install`; the Swift helper is built on first use into `~/Library/Caches/ai-auth/`).

### Glean CLI fallback

When neither a Glean API token nor an OAuth session is configured, `mdbx glean` uses the Glean CLI through
the helper script `scripts/glean_cli_helper.py` (same contract as the native-messaging hosts in
mdb-case-assistant and tam-dashboard):

```bash
brew install gleanwork/tap/glean-cli          # the CLI; `glean auth login` signs in through the browser
python scripts/glean_cli_helper.py check      # {"installed": true, "authenticated": ..., "version": ...}
python scripts/glean_cli_helper.py login      # runs `glean auth login`, re-checks
python scripts/glean_cli_helper.py search "Atlas Private Link" --page-size 5
```

Exit codes: 0 ok · 1 failed · 2 CLI not installed · 3 not authenticated. The helper retries transient
network errors (i/o timeout, connection reset) and always prints one JSON object.
