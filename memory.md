# memory.md — operator log

## v0.5.0 — 2026-10-19
- Chrome extension `editors/chrome/` for the TSE team: highlight a query / log line, click (or Alt+Shift+O, or
  right-click "Optimize selected MQL"), get findings, log evidence, safe rewrites, index advice and "Copy as
  Markdown" case note. MV3, `activeTab`+`scripting`+`contextMenus`+`storage` only, no host permissions, no
  network. Zip: `scripts/package_chrome_extension.py` (33 KB). Verified in real Chromium 156 via
  `test/e2e.mjs` (Playwright 1.64 borrowed from ~/dev/mess-organizer; branded Chrome 137+ cannot --load-extension).
- Optimizer input normalization `mdbx/mql/normalize.py`: slow-query log lines (getMore -> originatingCommand),
  profiler entries (incl. update/delete {q,u} shape), command documents, bare filters/pipelines; EJSON to
  mongosh literals. P9 evidence findings: log-collscan, log-scan-ratio, log-blocking-sort, log-spill,
  log-replanned, log-timeout-bound. Index rationale no longer lists a sort key as a range key too.
- JS port (`lib/parser.js`, `normalize.js`, `optimize.js`) pinned to Python by `tests/fixtures/optimizer/*.golden.json`
  (`scripts/gen_optimizer_golden.py`, includes the text report) and `tests/test_js_parity.py` (395 inputs incl.
  truncated prefixes, both modes): identical. 103 pytest + 37 node tests.
- Docs links (28 public MongoDB URLs) verified 200 with `scripts/check_chrome_doc_links.py`.
- ~/.config/mdbx copy: not on this box, chezmoi, or reachable peers (m5/5080 off this hotspot network);
  background rsync retry ran for 2 h. Never route it through the mitchlists repo (denylist names customers).

## v0.4.0 — 2026-10-19
- Static MQL query optimizer `mdbx/mql/optimize.py` (offline subset of the deep MQL optimizer skill v1.4: passes
  P2/P4/P5/P6/P7/P8, ~30 rule codes, ESR index recommender incl. per-$or-branch and $lookup indexes, covered-query
  hints). Result-preserving rewrites auto-applied in a <=3-iteration loop (or->in, degenerate range->eq, $match
  hoist, countDocuments({})->estimatedDocumentCount); blocking findings reported only. Surfaces: `mdbx optimize`
  (alias `opt`, --read-only/--write/--json, exit 1 on high/blocking), MCP `mql_optimize`, mql-lsp diagnostics
  (source mql-optimizer, codes opt/*, MDBX_LSP_OPTIMIZE=0 disables). 22 tests; examples/slow-queries.mql.
- Corpus: 6 mongodb-expert + 2 atlas-diagnostics-expert MQL-optimization spokes, hub routing rows ported by hand
  into the redacted SKILL.md, optimizer reference rebuilt from v1.4 with the earlier redaction transforms, 19
  `corpus/llms/mongodb-*.llms` fact packs (llms.txt, llms-facts, vocabulary, manifest; ~6.4 MB). Private redaction
  config (~/.config/mdbx) was NOT on this box: re-syncing existing skill dirs was reverted to keep earlier hand
  redactions; a session denylist + an independent reviewer agent cleared all new files (0 sweep hits / 329 files).
- Fact packs carry "private reading aid; never publish" provenance notes: fine for this PRIVATE repo, must be
  excluded from any public release.
- Fixed scripts/redact_corpus.py path regex eating JSON quotes / link parens (19 manifests were invalid JSON).
- repo-bootstrapper: audit ledger docs/repo-bootstrap-audit-2026-10-19.md; added scripts/rotate_workflow_logs.py,
  scripts/watch_and_index.sh, .vscode/mcp.json, CI rotation + optimizer smoke steps; version drift fixed (0.4.0).
  cdo pass: 16 Medium+ fixes (Ollama error/log handling, semantic filter-before-rank, vector purge on model change,
  TUI worker errors, sweep fails on zero files) + 9 tests.
- README rewritten with why-use-it table and real examples; customer demo docs/DEMO-mql-optimizer.md; recipe
  optimize-an-mql-query (25 recipes). 92 tests, ruff clean.

### Next
- Re-run `scripts/sync_corpus.sh` only on a box with ~/.config/mdbx (it overwrites hand-redacted skill files).
- Semantic vectors for the new fact packs: run `mdbx index` with Ollama up.
- Optional browser extension (proposed 2026-10-19, not built): right-click "optimize this MQL" on Atlas Data
  Explorer / docs / tickets, backed by the local `mdbx` (native messaging) or a WASM/JS port of the rules.

## v0.3.0 — 2026-10-17
- Full confidentiality pass: 9 reviewer agents read all 207 non-public-docs corpus files (3.4 MB); ~60 findings fixed
  (customer program names, an account's savings target, private ticket id, internal tools/hosts/paths, pricing
  negotiation text). Sweep (built-in markers + private denylist) reports 0 hits. Second independent review of the
  edits and of the recipes was run after the fixes.
- Customer-name rules moved out of the repo: ~/.config/mdbx/redactions.py (RULES, PATCH) and denylist.txt.
  Hand edits are captured as a private patch applied by `scripts/redact_corpus.py` after a re-sync.
- Added 24+ recipes (`corpus/recipes/`, `mdbx recipes|recipe`, TUI Ctrl+R, MCP `mdb_recipes`/`mdb_recipe`),
  docs/RECIPES.md, and a VS Code extension (`editors/vscode`, packaged, unit-tested; not exercised in a live VS Code).
- Repo stays PRIVATE; history contains an old redaction script with customer names -> publish via fresh squashed repo.

## v0.2.0 — 2026-10-17
- Repo made private pending a full customer-info sweep (user request).
- Redaction: `scripts/redact_corpus.py` (exact-phrase rules) + `scripts/sweep_customers.py` (built-in markers +
  denylist at ~/.config/mdbx/denylist.txt). Still local-only: uber-mongodb-skill.md, memory-central rows,
  atlas-diagnostics-expert SKILL.md + atlas-diagnostics-package.md (internal hosts/repos).
- Added MCP server `mdbx mcp` (mcp 2.x `MCPServer`; v1 `FastMCP` import fails) with 5 tools.
- Added MQL language server `mql-lsp` (pygls 2.1, Full sync) + `mdbx lint`; 280-operator table, tolerant parser,
  ~25 lint rules, completion, hover (+ corpus hits), outline, quick fixes. 52+ tests incl. stdio e2e.

## v0.1.0 — 2026-10-17
- Created project: corpus copied (MongoDB skills + llms exports), FTS5 + Ollama semantic indexes,
  `mdbx` CLI (`index`, `search`, `show`, `stats`, `tui`), Textual TUI, tests, CI.
- Withheld from the public repo: `uber-mongodb-skill.md`, memory-central rows and skill files that
  mention customers or internal tooling (see `.gitignore`). They are still indexed locally.
- Bootstrapped docs to the mdb-tam standard (Python-applicable subset).

### Next
- Add `mdbx` MCP server (see `docs/known-issues.md`).
- Redact private skill files so they can ship publicly.
