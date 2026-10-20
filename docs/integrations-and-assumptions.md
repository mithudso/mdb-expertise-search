# Integrations and assumptions

- Ollama with `nomic-embed-text` (768-dim, needs `search_document:` / `search_query:` prefixes, which `embed.py` adds).
- Corpus is plain `.md`/`.txt`; `.json`/`.jsonl` files are ignored.
- Corpus layout: `corpus/skills/<skill>/…` → kind `skill`; `corpus/llms/<set>.llms/…` → kind `llms`;
  `corpus/llms/memory-central/…` → kind `memory`.
- Assumes UTF-8 text; undecodable bytes are replaced.
- AI providers (optional `ai` extra) come from the shared [ai-auth](https://github.com/mithudso/ai-auth) library
  (`~/dev/libraries/ai-auth`), app namespace `mdbx`: Claude / Codex / Antigravity resolve stored key → env var →
  the vendor CLI's own OAuth login (`claude -p`, `codex exec`, `agy -p`); Glean resolves token → PKCE OAuth session →
  the Glean CLI helper (`scripts/glean_cli_helper.py`, needs `glean` installed). Apple Intelligence is the last
  fallback for `mdbx ask` and assumes macOS 26+, Apple silicon, Apple Intelligence enabled and `swiftc` from the
  Command Line Tools.
- Assumed vendor CLI behaviours: `claude auth status --json` reports `loggedIn`; `claude -p` needs the `CLAUDE*`
  environment stripped when run inside Claude Code; `codex exec -o FILE` writes the last message; `agy -p
  --output-format json` returns `{"response": ...}`; Gemini CLI headless needs `GEMINI_CLI_TRUST_WORKSPACE=true`;
  `glean auth status` prints "Token expired" when the session lapsed.
- Chrome extension auto-update assumes the extension is loaded unpacked from a folder the updater owns
  (`~/Library/Application Support/mdbx/chrome-extension` by default) and that the service worker can re-read its
  own `data/build.json`; a Web Store / force-installed copy updates through Chrome instead.
