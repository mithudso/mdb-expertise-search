# Known issues

- The optimizer exists twice (Python reference, JS port for the Chrome extension). Goldens plus the
  ~400-input parity test keep them identical; offsets differ only for astral-plane characters (Python
  counts code points, JS counts UTF-16 units), which affects line/column of findings after such characters.
- Chrome extension: toolbar clicks cannot be automated, so `test/e2e.mjs` opens the popup as a tab and
  feeds the right-click handoff; the activeTab selection path is covered by running `grabSelection` in a
  real page. Virtualized editors (Monaco) expose only visible text to `getSelection()`; paste instead.
- `chrome.action.openPopup()` needs Chrome 127+; older versions open the report in a tab instead.

- `mdbx index` rebuilds the keyword index from scratch every run (fast) but does not drop vectors for
  changed text until the rebuild finishes; stale digests are pruned automatically.
  Changing `MDBX_EMBED_MODEL` discards every vector on the next run (full re-embed).
- Semantic search brute-forces all vectors; fine at ~10k chunks, would need an ANN index at 1M+.
- Local-only corpus files (cannot be redacted): `uber-mongodb-skill.md`, memory-central rows, two internal
  Atlas-diagnostics skill files, the ts-diag skill/llms set and the kb-backed-troubleshooting stubs.
- Git history of this private repo contains an early version of `scripts/redact_corpus.py` with customer
  names in its rules. **Do not flip this repo to public.** Publish by creating a fresh repository from a
  squashed snapshot (no history) after the final manual review.
- Recipe citations are `path:line` against the corpus as of the redaction pass; line numbers drift if corpus
  files are re-synced or edited. Recipes mark unconfirmed steps with "Verify in the current MongoDB docs:". The repo is private until a full customer-information sweep is done;
  the sweep tool only checks built-in markers plus a denylist kept outside the repo.
- The VS Code extension is packaged and its pure logic is unit-tested, but it has not been exercised in an
  interactive VS Code session by automation; report problems with `mql.trace.server = verbose`.
- `mql-lsp` is static: no server connection, schema or index awareness; the operator table is not versioned
  per MongoDB release, so brand-new operators warn as "not in table". Completion offers operators by context but
  not field names. `$function`/`$where` JavaScript bodies are not parsed.
- `mdbx optimize` / `mql_optimize` / the `opt/*` LSP diagnostics are static: no cardinality, no existing-index
  list, no explain output. Index recommendations are ESR-ordered guesses (recommend-only), and impact claims are
  unmeasured; confirm with `explain('executionStats')` on a cluster. Only result-preserving rewrites are applied;
  everything else is reported. JavaScript is not evaluated.
- The private redaction config is absent on the box that built this corpus, so the deep MQL query optimizer
  reference (`corpus/skills/mongodb-expert/references/deep-mongodb-mql-query-optimizer.md`, v1.4) was redacted by a
  one-off session script, not `scripts/redact_corpus.py`. Re-running `scripts/sync_corpus.sh` does not refresh it
  (see the NOTE in the script); redo the redaction by hand and run `scripts/sweep_customers.py`.
- The `mongodb-*.llms` fact families are copied from `MDBX_CONCEPTS_SRC`; only `llms.txt`, `llms-facts.txt`,
  `llms-vocabulary.txt` and `manifest.json` are kept (not `llms-small.txt` or `llms-full.txt`).
- `scripts/rotate_workflow_logs.py` splits on `## v` headings; a log with 3 or fewer such sections is never rotated.
- The parser handles mongosh-style statements, not full JavaScript (no arrow functions, template expressions,
  spread, or loops).
- MCP uses the v2 SDK (`mcp.server.mcpserver.MCPServer`); v1 `FastMCP` code does not run on it.
- Natural-language queries fall back from AND to OR keyword matching; very long queries can be noisy.
- The TUI test covers keyword mode only (no Ollama in CI).
