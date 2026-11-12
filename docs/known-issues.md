# Known issues

- The optimizer exists twice (Python reference, JS port for the Chrome extension). Goldens plus the
  ~400-input parity test keep them identical; offsets differ only for astral-plane characters (Python
  counts code points, JS counts UTF-16 units), which affects line/column of findings after such characters.
- Chrome extension: toolbar clicks cannot be automated, so `test/e2e.mjs` opens the popup as a tab and
  feeds the right-click handoff; the activeTab selection path is covered by running `grabSelection` in a
  real page. Virtualized editors (Monaco) expose only visible text to `getSelection()`; paste instead.
- Extension search data is a snapshot taken at packaging time; rebuild the zip after corpus changes.
- Hybrid/semantic search in the extension uses int8-quantised vectors, so its semantic ranking can differ
  slightly from `mdbx search -m semantic` (float32); keyword ranking is identical.
- Ollama answers HTTP 403 to extension origins until `OLLAMA_ORIGINS` allows `chrome-extension://<id>`.
- `chrome.action.openPopup()` needs Chrome 127+; older versions open the report in a tab instead.

- `mdbx index` rebuilds the keyword index from scratch every run (fast) but does not drop vectors for
  changed text during preparation. Historical vector bytes are retained; changed heading inputs are marked ineligible for retrieval.
  An explicit semantic build validates a complete candidate generation before replacing a different model.
- Semantic search brute-forces all vectors; fine at ~10k chunks, would need an ANN index at 1M+.
- Local-only corpus files (cannot be redacted): `uber-mongodb-skill.md`, memory-central rows, two internal
  Atlas-diagnostics skill files, the [private reference omitted] skill/llms set and the kb-backed-troubleshooting stubs.
- GitHub currently reports this repository as public. Older notes assumed private
  visibility and identify historical privacy concerns. This maintenance did not
  inspect customer corpus/history, change visibility or establish redistribution
  clearance. Maintainer review remains necessary before new corpus publication.
- Recipe citations are `path:line` against the corpus as of the redaction pass; line numbers drift if corpus
  files are re-synced or edited. Recipes mark unconfirmed steps with "Verify in the current MongoDB docs:". The sweep checks configured markers; it is not proof of exhaustive privacy review.
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

- Short-section chunk metadata retains the historical format used by the frozen
  search fixtures. A section can share a chunk with an adjacent section, so the
  heading/line is an approximate anchor. A precise per-section format needs an
  explicit cache/fixture migration; this maintenance preserves frozen vector bytes.
- Existing unlabelled semantic vectors require an explicit provenance migration;
  the builder refuses to assign them an inferred model identity. No live migration
  or embedding generation was performed.
- macOS offline checks use sandbox-exec to deny process-tree outbound traffic.
  Other platforms need equivalent isolation; the Python socket fixture alone does
  not isolate child processes or prevent in-process inference.
- Hub registry registration for this maintenance is delegated to the batch supervisor.

- Secure corpus reads currently require POSIX no-follow directory descriptors and fail closed on unsupported platforms. Windows launcher resolution tests do not establish Windows corpus-read support.

## Preserved serialization boundary (2026-11-12)

Short parent-heading sections can report an approximate starting line, and tiny
sibling sections can retain the previous breadcrumb. These two corroborated
metadata defects are **BLOCKED: scope requires a separately authorized serialization
migration**. Historical chunk_text and _merge_tiny remain exact; frozen search
fixtures continue to verify production behavior. No copied legacy codec or fixture
monkeypatch is used. The same scope also retains the current treatment of inline
backtick fence openers and unbounded oversized breadcrumbs. Changing those chunk
representations requires the same migration decision.

Secure publication retains `.mdbx-recovery-*` displaced versions when an explicit
expected-content update runs, including writes made later through an editor-held
old inode. Stable `.mdbx-lock-*` files coordinate publishers. These ignored local
artifacts preserve recovery evidence; users may inspect them before manual removal.

The static optimizer also retains its existing strong warning for dotted key/value
predicates without `$elemMatch` and numeric-looking string comparisons. Such input
can be intentional for embedded objects or string schemas. The corroborated message/
severity correction changes two ordinary optimizer expectation files outside the
four-file authorization, so it is **BLOCKED by the current fixture scope**. Treat
that advice as a prompt to inspect schema, rather than proof that a query is wrong.
