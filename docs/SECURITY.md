# Security

## Chrome extension (`editors/chrome/`)
- Runs the optimizer entirely in the extension; no `fetch`/XHR, no remote code (MV3 CSP `script-src 'self'`).
- Permissions: `activeTab` + `scripting` (read the selection only after a user click, shortcut or menu
  item), `contextMenus`, `storage` (`chrome.storage.session`: last input and right-click handoffs,
  memory-only; `chrome.storage.local`: the Ollama setting). No host permissions, no content scripts.
  Optional, runtime-requested `http://127.0.0.1/*` / `http://localhost/*` for a local Ollama (query
  embeddings only); Ollama's own origin check stays in force (users allow the extension via OLLAMA_ORIGINS).
- Packaged corpus: `mdbx export-web` exports git-tracked corpus files only and refuses a corpus outside
  git, so private local files never ship. The corpus includes MongoDB docs extracts (CC BY-NC-SA 3.0 US)
  and some third-party passages: distribute the extension internally (Private Web Store listing or
  admin force-install), not publicly.
- Page text is rendered with `textContent` only; a unit test fails on `innerHTML`/`eval` in popup code.
- The Markdown case note contains the highlighted query text (may include customer values); users review
  it before pasting.

- **Local only**: no network listener. The only outbound call is to the configured Ollama host
  (`/api/embed`), sending corpus chunk text and query text. Point it at a trusted host.
- **Path safety**: `mdbx show` resolves the path and refuses anything outside the corpus root.
- **SQL**: all queries are parameterised; FTS terms are tokenised to `\w+` and quoted.
- **Secrets**: none are used or stored. Corpus connection-string examples are placeholders.
- **MCP/LSP**: both run locally over stdio. `mdb_show` is confined to the corpus root. The LSP never executes
  or evaluates user text; it only parses it. Hover reads the local mdbx index if present.
- **Confidentiality**: the committed corpus must not contain customer names, account figures or
  internal tooling notes. Files that do are listed in `.gitignore` and stay local.
- Report issues via GitHub private vulnerability reporting (see `.github/SECURITY.md`).
