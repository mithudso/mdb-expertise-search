# memory.md — operator log

## 2026-10-22 — corpus refresh + scheduled updater
- Corpus refreshed from the skill tree and `~/.global-ai-hub/llms-concepts`: six new `mongodb-*.llms` families
  (cost-optimization, counts/cursors/read path, sort and pagination, MCP read-only/permissions, two dated Atlas
  frontier families), ~35 new skill references (index builds, bucket catalog, hidden indexes, Atlas cost and
  topology), many updated Atlas/expert references. `sync_corpus.sh` now globs concept families instead of a list.
- The sweep flagged 22 re-synced files whose hand-redacted text the rsync had overwritten; they were put back to the
  committed text, as were three files naming customers. `~/.config/mdbx/denylist.txt` now exists on this box (it did
  not; customer names were slipping past the built-in markers).
- New `scripts/corpus_autoupdate.py` (launchd agent, own clone, sweep gate, commit + push) with tests in
  `tests/test_corpus_autoupdate.py`.
- Shipped the in-process embedder: `mdbx/embed_onnx.py`, `MDBX_EMBED_BACKEND=auto|ollama|onnx`, `mdbx embed-fetch`,
  `onnx` extra, `tests/test_embed_backend.py`, `tests/conftest.py` (forces `ollama` in tests). Denylist now also holds
  the customer names from the TAM assignments sheet (OpenAI/Splunk/Stripe/Wise left out: they are products in public docs).
- Finding: in-process query embedding is feasible. nomic-embed-text-v1.5 fp32 ONNX (onnxruntime + tokenizers,
  mean pooling) matches the stored Ollama vectors at mean cosine 0.999 (13 ms/query); the int8 ONNX only 0.94.

## v0.7.0 — 2026-10-20
- AI providers via the new shared library `ai-auth` (`~/dev/libraries/ai-auth`, https://github.com/mithudso/ai-auth,
  private; optional extra `ai`): `mdbx auth status|set-key|login|unset|mode|prefer|test` (= `ai-auth --app mdbx …`),
  `mdbx ask` (corpus passages → first available provider, Apple Intelligence fallback), `mdbx glean` (token → PKCE
  OAuth → Glean CLI helper). Adapter: `mdbx/providers.py`; helper shim: `scripts/glean_cli_helper.py` (the
  implementation lives in `ai_auth/glean_helper.py`, same contract as the tam-dashboard / case-assistant native
  hosts: binary resolution, auth probe, login, transient retry, JSON out, exit 2/3).
- Credential chain per provider: stored key (Keychain `ai-auth/mdbx`) → env → vendor OAuth (`claude auth login` →
  `claude -p`; `codex login` → `codex exec`; `agy`/`gemini` sign-in → `-p`). Anthropic/OpenAI/Google have no
  third-party OAuth for their APIs, so the CLIs' own logins are the OAuth path; Claude Code's Keychain tokens are not
  read. Live-verified on this Mac: claude (oauth, 17–22 s with haiku), codex exec (34 s), agy -p (21 s), Apple
  Intelligence (macOS 27.0.1, helper built by `swiftc` in ~1 s, answers in ~1.5 s). Gemini CLI headless needs
  `GEMINI_CLI_TRUST_WORKSPACE=true`; `claude -p --bare` cannot see the Keychain login (do not use `--bare`).
- Chrome extension auto-update (ext 0.3.0, `alarms` permission): `scripts/chrome_extension_autoupdate.py
  install-agent` = launchd agent (default 10 min) that fetches its own clone, rebuilds via
  `package_chrome_extension.py` (now writes `data/build.json` {version, commit, built_at}), swaps the unpacked folder
  atomically; `editors/chrome/lib/autoupdate.js` re-reads `build.json` every 5 min and `chrome.runtime.reload()`s.
  `--source release` consumes the rolling `chrome-latest` GitHub release that CI now publishes on every push to main
  (keyword-only build; job `chrome-release` in ci.yml, `contents: write`).
- Semantic fallback is now signalled everywhere: `search.hybrid(notes=…)` records why the embedder was skipped and
  marks hits `via="keyword (semantic unavailable)"`; CLI prints `warning: semantic search unavailable (…)` to stderr
  (semantic mode: error + "start Ollama" hint, exit 1); TUI status shows `⚠ …`; MCP `mdb_search` adds
  `degraded: true` + `warning` to every hit (semantic mode raises). The Chrome app already noted it in the status line.
- Known gaps: `ai-auth` is a private repo, so CI cannot install the `ai` extra (provider tests `importorskip`);
  Glean PKCE login is implemented against the tenant's RFC 8414 metadata (verified discoverable) but the browser
  flow and whether REST accepts those tokens are not yet exercised — the Glean CLI fallback is the proven path.

## v0.6.0 — 2026-10-19
- Chrome extension grew from the optimizer into "MongoDB Expertise" (ext 0.2.0): packaged corpus + search index
  (10.2 MB zip / 28.5 MB unpacked: 12,402 chunks, 14,672 terms, 867k postings, 10,820 int8 vectors), full app
  (`app.html`: Search with area facets + document view, Recipes, Optimize, Lint, Operators, About), popup falls
  back to corpus passages for non-query selections, right-click Search/Lint, omnibox `mdb`.
- `mdbx export-web` (`mdbx/webexport.py`): git-tracked corpus files only (refuses corpus outside git, errors when
  everything is untracked). Pure-Python `WebIndex` reproduces SQLite FTS5 exactly (unicode61 + porter + bm25 with
  weights 4/1/2): identical top-10 and order on 41/41 real queries. JS port (`lib/textsearch.js`) identical to
  Python on 87/87 real query×mode runs; fixture goldens in tests/fixtures/search/.
- Semantic/hybrid in the browser needs a local Ollama: optional host permission for 127.0.0.1/localhost; Ollama
  returns 403 to chrome-extension origins until OLLAMA_ORIGINS allows the extension id (About tab shows the
  command). Live hybrid check: embed 240-590 ms, rank 15-25 ms.
- Linter port `lib/analyze.js` + operator table (subagent): 14/14 diagnostic codes, 859 prefix inputs identical,
  difflib `suggest()` port verified on 1,137 words.
- Fact packs "never publish" label = the hub pipeline's blanket rule for third-party snapshots, not a licence
  finding. MongoDB docs are CC BY-NC-SA 3.0 US (98.4% of fact lines cite www.mongodb.com; ~100 lines cite
  third-party blogs). Public release would need a CC carve-out licence file + filtering non-MongoDB lines.
- e2e (Playwright 1.64 + Chromium 156): popup optimizer, corpus fallback, app search/facets/doc view, recipes,
  lint, operators, about, optimizer corpus links, right-click lint handoff. 119 pytest + 130 node tests.

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
