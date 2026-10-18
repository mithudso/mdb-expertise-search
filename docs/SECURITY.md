# Security

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
