# Integrations and assumptions

- Ollama with `nomic-embed-text` (768-dim, needs `search_document:` / `search_query:` prefixes, which `embed.py` adds).
- Corpus is plain `.md`/`.txt`; `.json`/`.jsonl` files are ignored.
- Corpus layout: `corpus/skills/<skill>/…` → kind `skill`; `corpus/llms/<set>.llms/…` → kind `llms`;
  `corpus/llms/memory-central/…` → kind `memory`.
- Corpus input must be valid UTF-8. Unsafe or unreadable files fail the rebuild, preserving the previous generation.
- AI providers (optional `ai` extra) come from the shared [ai-auth](https://github.com/mithudso/ai-auth) library
  (`~/dev/libraries/ai-auth`), app namespace `mdbx`: Claude / Codex / Antigravity resolve stored key → env var →
  the vendor CLI's own OAuth login (`claude -p`, `codex exec`, `agy -p`); Glean resolves token → PKCE OAuth session →
  the Glean CLI helper (`scripts/glean_cli_helper.py`, needs `glean` installed). Apple Intelligence is the last
  fallback for `mdbx ask` and assumes macOS 26+, Apple silicon, Apple Intelligence enabled and `swiftc` from the
  Command Line Tools.
- The optional shared ai-auth facade owns vendor CLI arguments, authentication and
  credential discovery. MDBx tests its maintained adapter with synthetic facades;
  private-library internals and live vendor authentication are outside these checks.
- Chrome extension auto-update assumes the extension is loaded unpacked from a folder the updater owns
  (`~/Library/Application Support/mdbx/chrome-extension` by default) and that the service worker can re-read its
  own `data/build.json`; a Web Store / force-installed copy updates through Chrome instead.
