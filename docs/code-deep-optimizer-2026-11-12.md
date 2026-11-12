# Code deep optimizer ledger — 2026-11-12

This is the full maintained-source run. Neither quick triage nor changed-only scope
was used. Status at this pushed repair checkpoint: **final blind gate2 in progress**.
PR7 remains draft. No CLEAN or completed-delivery claim is made.

## 1. Per-iteration severity accounting

| Collection / repair iteration | Critical | High | Medium | Low | Nit | Meaning |
|---|---:|---:|---:|---:|---:|---|
| Initial diagnostics / iteration1 input |75|69|211|12|0|112 maintained files; includes1 native Medium |
| Blind gate1 / iteration2 input |16|29|232|10|0|129 frozen files;277 Medium+ candidate rows |
| Gate1 current-generator continuation |0|0|1|0|0|one changed-hash report; duplicate publication finding, not a new gate |
| Owner-retained before final gate2 |0|0|6|unresolved raw Low rows|0|four chunk-format issues and paired schema-advice issue; not a blind verdict |
| Final blind gate2 |pending|pending|pending|pending|pending|145 maintained files; collection still running |

Counts above are raw report rows, not unique defects. Duplicate passes and paired
implementations must not inflate a claim of independently fixed bugs. All277
original gate1 Medium+ rows were corroborated/dispositioned before iteration2.
The supplemental generator report is retained, deduplicated, and covered by a
specific failure-after-export regression. Lower-severity rows are not silently
converted to fixed/clean status.

Original budgets remain5 repair iterations and2 blind gates. Iterations1 and2
have been applied. Gate1 was resumed missing-only; gate2 is the second and final
gate. Source ownership never overlapped. Allocation history is2→4→8 bounded
read-only contexts after other selected owners drained, with a single admitted
dispatcher, per-file hashes and per-gate exclusive lock. There is no third gate.

## 2. Findings and dispositions (representative, capped)

Line references below identify reviewed snapshots; current source may have moved.
Complete raw reports, hashes, exact counterexamples, duplicate relations and
dispositions remain in the retained external evidence. This table is intentionally
capped; it does not replace the145-file coverage inventory.

| Pass | File:line | Severity | Finding | Fix / evidence | Status |
|---|---|---|---|---|---|
| C1/C2 | mdbx/index.py:118 | Critical/High | partial or stale semantic generations and mixed model/input identities | bounded SQLite staging, validation, input/revision recheck and atomic publication; synthetic preservation tests | repaired |
| P2/C1 | mdbx/search.py:135 | High | vectors, metadata and hydration could span revisions | immutable revision state and coherent read snapshots; two-connection tests | repaired |
| S1/S2 | mdbx/safety.py:1 | Critical/High | path races and replacement could lose a displaced writer version | no-follow directory descriptors, atomic exchange and retained recovery inode; adversarial local writers | repaired |
| C1/S2 | mdbx/webexport.py:1 | High | exports could mix metadata/vector provenance or overwrite source state | overlap checks, bounded validation, held destination descriptors, recoverable publish | repaired |
| S2 | scripts/gen_search_golden.py:122 | Medium | later keyword failure could leave index/golden generations mismatched | stage both before pair publication; forced keyword exception preserves sentinel pair (old implementation RED) | repaired; supplemental duplicate retained |
| S1/S3 | scripts/test_isolation.py:1 | High | inherited Git templates/config/hooks and local runtimes escape a socket-only guard | scratch process state, preimport fake factories, empty owned Git configs/templates/hooks and per-commit inventories | repaired |
| C1/C2 | mdbx/mql/normalize.py:1 | Critical/High | BSON wrappers/options or unknown receiver identity could be lost | conservative paired normalization with exact synthetic behavior assertions | repaired |
| C1 | mdbx/mql/optimize.py:713 | Critical | unresolved predicates could become illegal or inequivalent $in rewrites | proven-equality operands only; result-changing alternatives remain advisory | repaired |
| C1/C2 | editors/chrome/lib/optimize.js:1 | High/Medium | unknown collections and change-stream envelopes received invented index advice | null unknown identity, human unspecified wording and no ordinary watch-envelope index command | repaired |
| C1/M4 | mdbx/mql/optimize.py:1 | Medium | unqualified sort/coverage promises | conditional index/schema/explain wording and known null/array blockers; independent primary semantics | repaired within four authorized expectations |
| C1/C2 | mdbx/mql/analyze.py:1 | High/Medium | documents expression shape and tolerant shell statements drifted | global shape/separator fixes plus12 regression inputs; all lint expectations unchanged | repaired |
| C2 | mdbx/mql/server.py:1 | High | codepoint/UTF-16 and document-version contracts | paired range and stale-version handling; stdio assertions with deadlines | repaired |
| P2 | editors/chrome/app.js:1 | High | obsolete async tasks could publish after newer state | request ownership and stale completion assertions | repaired |
| C1/P1 | editors/chrome/lib/textsearch.js:1 | High/Medium | duplicate query weighting and Unicode/Porter differences | codepoint-aware Unicode61 tables, frequency Map and cross-runtime oracle cases | repaired |
| C2/S4 | editors/vscode/server-path.js:1 | Medium | launcher/grammar portability boundaries | pure command resolution and grammar-pairing checks | repaired; interactive host remains untested |
| C1/S2 | scripts/maintenance_safety.py:1 | High | privacy/maintenance output replacement could lose concurrent source edits | pinned identities, atomic exchange and recovery preservation | repaired |
| T1/T4 | tests/test_core_preservation.py:1 | Medium | local implementation assertions did not prove bounded payload behavior | synthetic12MiB vectors, tracemalloc limit6MiB; old peak16,732,961 bytes RED | repaired |
| C1 | mdbx/corpus.py:105 | Medium | parent-stub line origin can omit an earlier source anchor | historical serialization preserved under KNOW-1855 | BLOCKED: separately authorized migration |
| C2 | mdbx/corpus.py:124 | Medium | tiny sibling sections can retain prior breadcrumb | historical packing preserved under KNOW-1855 | BLOCKED: separately authorized migration |
| C3 | mdbx/corpus.py:93 | Medium | inline backticks can open a false fence | exact chunk_text retained | BLOCKED: separately authorized migration |
| P1 | mdbx/corpus.py:104 | Medium | oversized breadcrumbs can cause quadratic aggregate allocation | exact chunk representation retained | BLOCKED: separately authorized migration |
| C1 | mdbx/mql/optimize.py:326 | Medium | intentional dotted embedded-object and string-schema comparisons can receive strong warnings | correction deferred wholesale; affects two expectations outside exact scope | BLOCKED: ordinary fixture scope (paired JS retained) |

Production chunk_text and _merge_tiny are exact to592db43. Native production
verification covers64 synthetic serialized outputs, selected constants/functions,
and absence of a legacy codec or monkeypatch. Rejected migration proposals remain
external for history; they are not product or fixture-generation code.

Exactly four ordinary optimizer expectation files changed. Independent primary
MongoDB documentation and specific RED examples established null unknown collection,
no watch-envelope index advice, conditional sort support and conditional coverage
before expected values changed. Separate behavior assertions remain. Conditional
permission for three lint files was unused: all20 lint expectation artifacts are
fresh and byte-identical after implementation repair. Every search/chunk/vector and
private corpus fixture remains unchanged.

## 3. Verify gate

All ordinary local commands below ran through the task-owned process-tree egress
runner, scratch HOME/config/data/model/auth, pre-import synthetic factories and
fixture Git isolation. The exact expanded commands were logged before execution.
`python` below denotes the task test interpreter. CI uses `scripts/offline_test.py`.
Dependency metadata calls were separate network-enabled operations, never tests.

| Command | Baseline | After iteration2 | Verdict |
|---|---|---|---|
| python -m pytest -p collection_guard -q --tb=short -ra |141 baseline passes with later-confirmed fixture-hook effects; checkpoint285/6 skips |487 passed,6 optional skips | PASS on repair checkpoint |
| npm test --prefix editors/chrome | baseline passed; checkpoint182 passed |249 passed | PASS |
| npm test --prefix editors/vscode | missing baseline test script failed; checkpoint7 passed |10 passed | PASS |
| python -m ruff check . --output-format concise | PASS | PASS | PASS |
| python -m compileall -q mdbx scripts tests | PASS | PASS | PASS |
| python scripts/rotate_workflow_logs.py --check | PASS | PASS | PASS |
| python scripts/check_doc_indexes.py | PASS | final refresh pending | pending |
| python -m pip wheel . --no-deps --no-build-isolation --wheel-dir TASK_OUTPUT | checkpoint PASS | PASS | PASS |
| python scripts/package_chrome_extension.py --no-data | checkpoint PASS | PASS | PASS |
| ./node_modules/.bin/vsce package --out TASK_OUTPUT (cwd editors/vscode) | checkpoint PASS | PASS after correcting initial wrong cwd | PASS |
| npm audit --json --ignore-scripts --prefix editors/vscode | checkpoint0 advisories |0 vulnerabilities,144 records | PASS; metadata only |
| python -m pip_audit --format=json | not asserted |0 known vulnerabilities;71 records, editable project skipped | limited metadata PASS |
| final pushed-head GitHub CI matrix3.11/3.12/3.13 | checkpoint9caed9c passed | pending on final head | pending |

Six current skips are one real-ONNX and five optional private-auth integrations.
Synthetic ONNX fallback and mocked auth paths remain asserted. The141-test early
baselines used only a function-scoped socket guard and did not isolate collection-
time inference or descendant Git hooks. They are not no-effect proof; the actual
incident is recorded in the bootstrap ledger. No live model, corpus sync/index build,
provider benchmark, browser profile or service activation was used in final checks.

Empirical eligibility: offline parity/golden tests are regression gates, not a
heldout model-quality evaluation. Baseline parity already passed. Intentional
contract repairs change output semantics within authorized scope. No global
champion, unchanged-API quality promotion or measured production speedup is claimed.

## 4. Activated skills and repo passes

The named repo-bootstrapper and code-deep-optimizer were applied in full, with their
required audit/coding/report/status/language/empirical references and the read-only
canonical bootstrap prompt. The canonical convergence/severity contract supplies
the per-file checker. Stage0 detected Python>=3.11, SQLite/numpy, JavaScript/Node,
HTML/CSS, Chrome MV3, VS Code/LSP, stdio MCP, shell tooling and CI. Primary MongoDB
documentation grounds MQL contracts; no live MongoDB/Atlas query was executed.
The Stage0 language activation map was consulted. This report credits only skills
and references with actual retained context; it does not invent additional skill
engine activations or external security certification.

Repo M3: coherent central embedding-input/provenance helpers, search revisions,
shared publication/synthetic isolation boundaries and Python/JS parity contracts
address cross-component coupling. The paired MQL implementations remain separate
by runtime, with explicit parity rather than an unsupported language merger.
Cross-file M2: shared no-follow/publication helpers and source-bound test isolation
replace divergent unsafe code. Frozen serialization helpers remain unchanged.
T2: every manifest family was audited (Python base/optional/dev, Chrome zero-dep
package/MV3 manifest, VS Code package/lock/grammar and CI action dependencies).
Private-auth upstream implementation and floating future dependency versions remain
explicit limits. No breaking vscode-languageclient11 migration is smuggled in.
T3: Python Ruff/pytest/compile, both Node runners, locked editor dependencies,
strict command JSON assertions, static indexes, code-only packaging and guarded CI
are available. No invented app server, dashboard or external service was scaffolded.
T4: meaningful tests use synthetic mocks/local pipes with deadlines and no paid APIs.
Node uses one managed runner; read-only review pools obey shared admission limits.
No redundant full-suite repetition is credited as additional independent evidence.

## 5. Unified diff per file (capped)

The following excerpts cover every task-modified tracked path at this checkpoint
relative to base8cc61b1. Each is capped at8 diff lines; all omitted remainder is
explicitly truncated. The full patch is reviewable in PR7. Protected-data additions
are forbidden; privacy-rule assignments were independently verified unchanged.

### `.env.example`

```diff
diff --git a/.env.example b/.env.example
index 03e9b13..ba9faab 100644
--- a/.env.example
+++ b/.env.example
@@ -1,3 +1,4 @@
-# All optional. Defaults shown.
-MDBX_DB=./data/mdbx.sqlite
-MDBX_CORPUS=./corpus
```

Truncated: 4 further diff lines; see PR7.

### `.github/copilot-instructions.md`

```diff
diff --git a/.github/copilot-instructions.md b/.github/copilot-instructions.md
index 43ae7a5..2c925f2 100644
--- a/.github/copilot-instructions.md
+++ b/.github/copilot-instructions.md
@@ -1 +1 @@
-## Default Execution Strategy
+# Repository instructions
@@ -3,2 +3,19 @@
```

Truncated: 21 further diff lines; see PR7.

### `.github/workflows/ci.yml`

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index 1ee1e85..0dc85d6 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -5,0 +6,6 @@ on:
+  workflow_dispatch:
+permissions:
+  contents: read
```

Truncated: 107 further diff lines; see PR7.

### `.gitignore`

```diff
diff --git a/.gitignore b/.gitignore
index 1b9ab47..13ff1b9 100644
--- a/.gitignore
+++ b/.gitignore
@@ -32,0 +33,3 @@ editors/chrome/data/
+
+# Owned atomic publication staging, locks and recoverable displaced versions
+.mdbx-*
```

### `.node-version`

```diff
diff --git a/.node-version b/.node-version
new file mode 100644
index 0000000..6f4247a
--- /dev/null
+++ b/.node-version
@@ -0,0 +1 @@
+26
```

### `AGENTS.md`

```diff
diff --git a/AGENTS.md b/AGENTS.md
index 6213c3f..6eb6643 100644
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -7,0 +8,5 @@ Agent rules: see [CLAUDE.md](CLAUDE.md). Search first with `mdbx search`, then r
+
+Repository maintenance uses [docs/TESTING.md](docs/TESTING.md) before running checks.
+Ordinary verification uses synthetic state and does not search or re-index live
```

Truncated: 2 further diff lines; see PR7.

### `CLAUDE.md`

```diff
diff --git a/CLAUDE.md b/CLAUDE.md
index e35bc44..01eee67 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -7 +7 @@ Project: `mdb-expertise-search` (`mdbx`) — hybrid search CLI/TUI over a MongoD
-- Test: `.venv/bin/pytest -q` · Lint: `.venv/bin/ruff check .`
+- Offline macOS tests: `python3 scripts/offline_test.py -- .venv/bin/python -m pytest -q`; lint: `python3 scripts/offline_test.py -- .venv/bin/ruff check .`. See docs/TESTING.md before executing checks.
@@ -10 +10 @@ Project: `mdb-expertise-search` (`mdbx`) — hybrid search CLI/TUI over a MongoD
```

Truncated: 31 further diff lines; see PR7.

### `README.md`

```diff
diff --git a/README.md b/README.md
index 9f36315..ff039d5 100644
--- a/README.md
+++ b/README.md
@@ -28,13 +28 @@ Everything runs locally. Search works without network access (keyword mode); sem
-$ echo 'db.events.find({ $or: [{ type: "click" }, { type: "view" }], ts: { $gte: 5, $lte: 5 } }).sort({ ts: -1 }).limit(50)' | mdbx optimize -
-MQL optimizer (static audit) — -: 1 query, no open findings; 2 rewrite(s) applied in 1 iteration(s)
-
```

Truncated: 39 further diff lines; see PR7.

### `docs/DEVELOPMENT.md`

```diff
diff --git a/docs/DEVELOPMENT.md b/docs/DEVELOPMENT.md
index a6c4f47..ceccf12 100644
--- a/docs/DEVELOPMENT.md
+++ b/docs/DEVELOPMENT.md
@@ -4,5 +4,3 @@
-python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'   # dev pulls in all extras
-.venv/bin/pytest -q
-.venv/bin/ruff check .
```

Truncated: 19 further diff lines; see PR7.

### `docs/INSTALLATION.md`

```diff
diff --git a/docs/INSTALLATION.md b/docs/INSTALLATION.md
index 37b622a..8324db9 100644
--- a/docs/INSTALLATION.md
+++ b/docs/INSTALLATION.md
@@ -15 +15 @@ Manual steps:
-python3 -m venv .venv && .venv/bin/pip install -e '.[all]'   # extras: tui, lsp, mcp
+python3 -m venv .venv && .venv/bin/pip install -e '.[all]'   # extras: tui, lsp, mcp; optional private Ollama client: ollama
@@ -65,2 +65 @@ When neither a Glean API token nor an OAuth session is configured, `mdbx glean`
```

Truncated: 11 further diff lines; see PR7.

### `docs/SECURITY.md`

```diff
diff --git a/docs/SECURITY.md b/docs/SECURITY.md
index 32bc06b..00e48e2 100644
--- a/docs/SECURITY.md
+++ b/docs/SECURITY.md
@@ -1 +1 @@
-# Security
+# Security boundaries
@@ -3,14 +3,3 @@
```

Truncated: 49 further diff lines; see PR7.

### `docs/TESTING.md`

```diff
diff --git a/docs/TESTING.md b/docs/TESTING.md
index 26d8eb7..732cc22 100644
--- a/docs/TESTING.md
+++ b/docs/TESTING.md
@@ -1,33 +1,61 @@
-# Testing
-
-`pytest -q` (asyncio auto mode). Suites:
```

Truncated: 91 further diff lines; see PR7.

### `docs/caching-and-optimization.md`

```diff
diff --git a/docs/caching-and-optimization.md b/docs/caching-and-optimization.md
index 62076dd..30df5c4 100644
--- a/docs/caching-and-optimization.md
+++ b/docs/caching-and-optimization.md
@@ -3,4 +3,18 @@
-- Vectors are cached in SQLite keyed by chunk text digest; re-indexing embeds only new text.
-- `VectorStore` loads the vector matrix once per process (TUI keeps one per session).
-- FTS5 `bm25()` weights: heading 4, text 1, source 2.
```

Truncated: 19 further diff lines; see PR7.

### `docs/codebase-overview.md`

```diff
diff --git a/docs/codebase-overview.md b/docs/codebase-overview.md
index b2102cd..02b65a9 100644
--- a/docs/codebase-overview.md
+++ b/docs/codebase-overview.md
@@ -6,15 +6,16 @@ Generated by `scripts/gen_file_index.py`. `corpus/` is data, not code.
-- `.editorconfig` — docs/config
-- `.env.example` — docs/config
-- `.gitattributes` — docs/config
```

Truncated: 538 further diff lines; see PR7.

### `docs/external-calls.md`

```diff
diff --git a/docs/external-calls.md b/docs/external-calls.md
index 5a4373a..18f1409 100644
--- a/docs/external-calls.md
+++ b/docs/external-calls.md
@@ -1 +1 @@
-# External calls
+# External operations
@@ -3,10 +3,10 @@
```

Truncated: 38 further diff lines; see PR7.

### `docs/high_signal_file_index.json`

```diff
diff --git a/docs/high_signal_file_index.json b/docs/high_signal_file_index.json
index 2c60e17..524f870 100644
--- a/docs/high_signal_file_index.json
+++ b/docs/high_signal_file_index.json
@@ -2,15 +1,0 @@
-  {
-    "path": "mdbx/embed_onnx.py",
-    "purpose": "In-process nomic-embed-text ONNX embedder",
```

Truncated: 624 further diff lines; see PR7.

### `docs/integrations-and-assumptions.md`

```diff
diff --git a/docs/integrations-and-assumptions.md b/docs/integrations-and-assumptions.md
index 8cb4ddb..52e8dee 100644
--- a/docs/integrations-and-assumptions.md
+++ b/docs/integrations-and-assumptions.md
@@ -7 +7 @@
-- Assumes UTF-8 text; undecodable bytes are replaced.
+- Corpus input must be valid UTF-8. Unsafe or unreadable files fail the rebuild, preserving the previous generation.
@@ -14,4 +14,3 @@
```

Truncated: 7 further diff lines; see PR7.

### `docs/known-issues.md`

```diff
diff --git a/docs/known-issues.md b/docs/known-issues.md
index bbdebab..b18ab8c 100644
--- a/docs/known-issues.md
+++ b/docs/known-issues.md
@@ -16,2 +16,2 @@
-  changed text until the rebuild finishes; stale digests are pruned automatically.
-  Changing `MDBX_EMBED_MODEL` discards every vector on the next run (full re-embed).
+  changed text during preparation. Historical vector bytes are retained; changed heading inputs are marked ineligible for retrieval.
```

Truncated: 53 further diff lines; see PR7.

### `docs/logging.md`

```diff
diff --git a/docs/logging.md b/docs/logging.md
index 3d0925b..4b6fa11 100644
--- a/docs/logging.md
+++ b/docs/logging.md
@@ -3,4 +3,2 @@
-The CLI writes progress and errors to **stderr** (`index` progress, "semantic index skipped: …",
-"no results") and results to stdout, so `--json` output stays pipe-safe. There is no log file and no
-secret or query logging. The TUI surfaces status and Ollama failures in its status line. Embedding
```

Truncated: 26 further diff lines; see PR7.

### `docs/repo-bootstrap-audit-2026-11-12.md`

```diff
diff --git a/docs/repo-bootstrap-audit-2026-11-12.md b/docs/repo-bootstrap-audit-2026-11-12.md
new file mode 100644
index 0000000..7fdc909
--- /dev/null
+++ b/docs/repo-bootstrap-audit-2026-11-12.md
@@ -0,0 +1,62 @@
+# Repository maintenance audit — 2026-11-12
+
```

Truncated: 60 further diff lines; see PR7.

### `docs/requirements.md`

```diff
diff --git a/docs/requirements.md b/docs/requirements.md
index afa5d7a..46c4c3b 100644
--- a/docs/requirements.md
+++ b/docs/requirements.md
@@ -4 +4 @@ Functional: index a directory of `.md`/`.txt`; keyword, semantic and hybrid sear
-filters; JSON output; browse in a TUI; resumable embedding; static MQL query optimization (`mdbx optimize`, MCP
+filters; JSON output; browse in a TUI; validated explicit embedding generations; static MQL query optimization (`mdbx optimize`, MCP
@@ -7,2 +7,8 @@ result-preserving rewrites, exit 1 on high/blocking findings, never connect to a
```

Truncated: 10 further diff lines; see PR7.

### `docs/wiki/README.md`

```diff
diff --git a/docs/wiki/README.md b/docs/wiki/README.md
new file mode 100644
index 0000000..ff2d5c6
--- /dev/null
+++ b/docs/wiki/README.md
@@ -0,0 +1,20 @@
+# Maintained documentation index
+
```

Truncated: 18 further diff lines; see PR7.

### `editors/chrome/README.md`

```diff
diff --git a/editors/chrome/README.md b/editors/chrome/README.md
index 0468e8f..a0fd3f7 100644
--- a/editors/chrome/README.md
+++ b/editors/chrome/README.md
@@ -22 +22 @@ beyond the extension:
-| Check a query or log line on the page | Highlight it → click the toolbar icon (or **Alt+Shift+O**, or right-click → **Optimize selected MQL**) |
+| Check a query or log line on the page | Highlight it → click the toolbar icon (or **Alt+Shift+O**). Right-click → **Optimize selected MQL** opens an identified handoff in a new tab |
@@ -63 +63 @@ Only the query text goes to that local Ollama; nothing leaves the machine.
```

Truncated: 5 further diff lines; see PR7.

### `editors/chrome/app.css`

```diff
diff --git a/editors/chrome/app.css b/editors/chrome/app.css
index 7b1f3ec..2f92fc6 100644
--- a/editors/chrome/app.css
+++ b/editors/chrome/app.css
@@ -110 +110 @@ textarea { font: 13px/1.45 var(--mono); width: 100%; resize: vertical; }
-.cards { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }
+.cards { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 280px), 1fr)); gap: 10px; }
```

### `editors/chrome/app.html`

```diff
diff --git a/editors/chrome/app.html b/editors/chrome/app.html
index 46c4117..5b2353d 100644
--- a/editors/chrome/app.html
+++ b/editors/chrome/app.html
@@ -14,6 +14,6 @@
-      <a role="tab" href="#search" data-tab="search">Search</a>
-      <a role="tab" href="#recipes" data-tab="recipes">Recipes</a>
-      <a role="tab" href="#optimize" data-tab="optimize">Optimize</a>
```

Truncated: 33 further diff lines; see PR7.

### `editors/chrome/app.js`

```diff
diff --git a/editors/chrome/app.js b/editors/chrome/app.js
index 435d90e..ce050fe 100644
--- a/editors/chrome/app.js
+++ b/editors/chrome/app.js
@@ -1,0 +2 @@
+import { consumeHandoff, truncateText } from "./lib/capture.js";
@@ -26,0 +28,6 @@ let index = null;
+let indexProblem = "";
```

Truncated: 233 further diff lines; see PR7.

### `editors/chrome/background.js`

```diff
diff --git a/editors/chrome/background.js b/editors/chrome/background.js
index 74b551c..725f08a 100644
--- a/editors/chrome/background.js
+++ b/editors/chrome/background.js
@@ -3,2 +3,2 @@
-// Selected text reaches the popup / app through session storage (memory only, cleared when the browser
-// closes); nothing is sent over the network.
+// Optimize and lint use unique session-storage handoffs, cleared when the browser closes.
```

Truncated: 35 further diff lines; see PR7.

### `editors/chrome/lib/analyze.js`

```diff
diff --git a/editors/chrome/lib/analyze.js b/editors/chrome/lib/analyze.js
index a7dead6..def2a6f 100644
--- a/editors/chrome/lib/analyze.js
+++ b/editors/chrome/lib/analyze.js
@@ -68,0 +69 @@ function kindOk(node, kind) {
+      if (!Number.isFinite(v)) continue;
@@ -70,3 +71,10 @@ function kindOk(node, kind) {
-      if (!Number.isInteger(v)) continue;
```

Truncated: 210 further diff lines; see PR7.

### `editors/chrome/lib/autoupdate.js`

```diff
diff --git a/editors/chrome/lib/autoupdate.js b/editors/chrome/lib/autoupdate.js
index 945f271..86c738d 100644
--- a/editors/chrome/lib/autoupdate.js
+++ b/editors/chrome/lib/autoupdate.js
@@ -35 +35 @@ export async function readBuild(fetchImpl, runtime) {
-    return null; // packaged without data/ (--no-data) or a transient read error
+    return null; // missing metadata, invalid JSON, or a transient local read error
@@ -41 +41 @@ export async function readBuild(fetchImpl, runtime) {
```

Truncated: 63 further diff lines; see PR7.

### `editors/chrome/lib/capture.js`

```diff
diff --git a/editors/chrome/lib/capture.js b/editors/chrome/lib/capture.js
index 2010848..78dcca5 100644
--- a/editors/chrome/lib/capture.js
+++ b/editors/chrome/lib/capture.js
@@ -31 +31,11 @@ export function clamp(text) {
-  return t.length > MAX_INPUT ? { text: t.slice(0, MAX_INPUT), truncated: true } : { text: t, truncated: false };
+  return { text: truncateText(t, MAX_INPUT), truncated: t.length > MAX_INPUT };
+}
```

Truncated: 32 further diff lines; see PR7.

### `editors/chrome/lib/docs.js`

```diff
diff --git a/editors/chrome/lib/docs.js b/editors/chrome/lib/docs.js
index 88dcaea..ccedb2b 100644
--- a/editors/chrome/lib/docs.js
+++ b/editors/chrome/lib/docs.js
@@ -7,0 +8 @@ export const DOCS = {
+  "index-too-wide": M + "reference/limits/#number-of-fields-in-a-compound-index",
@@ -48 +49 @@ export function docFor(code) {
-  return DOCS[code] ?? null;
```

Truncated: 1 further diff lines; see PR7.

### `editors/chrome/lib/normalize.js`

```diff
diff --git a/editors/chrome/lib/normalize.js b/editors/chrome/lib/normalize.js
index 8d9bfce..ac18673 100644
--- a/editors/chrome/lib/normalize.js
+++ b/editors/chrome/lib/normalize.js
@@ -4,0 +5 @@
+// Unsafe int64 evidence uses exact decimal strings in both ports; nonfinite measurements are omitted.
@@ -8,3 +9,3 @@ import { parse } from "./parser.js";
-const MONGOSH_CALL =
```

Truncated: 268 further diff lines; see PR7.

### `editors/chrome/lib/operators-data.js`

```diff
diff --git a/editors/chrome/lib/operators-data.js b/editors/chrome/lib/operators-data.js
index bb91d3d..913b171 100644
--- a/editors/chrome/lib/operators-data.js
+++ b/editors/chrome/lib/operators-data.js
@@ -78 +78 @@ export default {
-   "arg": "array",
+   "arg": "any",
@@ -446 +445,0 @@ export default {
```

Truncated: 10 further diff lines; see PR7.

### `editors/chrome/lib/operators.js`

```diff
diff --git a/editors/chrome/lib/operators.js b/editors/chrome/lib/operators.js
index 12e8b6b..ae15315 100644
--- a/editors/chrome/lib/operators.js
+++ b/editors/chrome/lib/operators.js
@@ -23 +23 @@ export class Operator {
-/** name -> Operator, in table order (the order drives suggest() tie-breaking like Python's dict). */
+/** name -> Operator, in table order; suggest() breaks ties by descending Unicode code-point order. */
@@ -114,0 +115,8 @@ function quickMatches(a, b) {
```

Truncated: 13 further diff lines; see PR7.

### `editors/chrome/lib/operators.json`

```diff
diff --git a/editors/chrome/lib/operators.json b/editors/chrome/lib/operators.json
index c46a98c..4976b9f 100644
--- a/editors/chrome/lib/operators.json
+++ b/editors/chrome/lib/operators.json
@@ -77 +77 @@
-   "arg": "array",
+   "arg": "any",
@@ -445 +444,0 @@
```

Truncated: 10 further diff lines; see PR7.

### `editors/chrome/lib/optimize.js`

```diff
diff --git a/editors/chrome/lib/optimize.js b/editors/chrome/lib/optimize.js
index d05af12..f2f9ac0 100644
--- a/editors/chrome/lib/optimize.js
+++ b/editors/chrome/lib/optimize.js
@@ -12 +12 @@ import { parse } from "./parser.js";
-import { normalize } from "./normalize.js";
+import { collRef, normalize, pyJsonStr } from "./normalize.js";
@@ -47,8 +46,0 @@ const has = Object.prototype.hasOwnProperty;
```

Truncated: 392 further diff lines; see PR7.

### `editors/chrome/lib/parser.js`

```diff
diff --git a/editors/chrome/lib/parser.js b/editors/chrome/lib/parser.js
index c00c78c..afcc59b 100644
--- a/editors/chrome/lib/parser.js
+++ b/editors/chrome/lib/parser.js
@@ -10,2 +10,2 @@
-const IDENT = /[A-Za-z_$][\w$]*/y;
-const NUMBER = /[-+]?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|Infinity|NaN)/y;
+const IDENT = /[A-Za-z_$][\p{L}\p{N}_$]*/uy;
```

Truncated: 168 further diff lines; see PR7.

### `editors/chrome/lib/report.js`

```diff
diff --git a/editors/chrome/lib/report.js b/editors/chrome/lib/report.js
index 99af4a2..14cc1a6 100644
--- a/editors/chrome/lib/report.js
+++ b/editors/chrome/lib/report.js
@@ -10 +10 @@ export function kindLabel(kind) {
-  return KIND_LABEL[kind] ?? kind;
+  return Object.hasOwn(KIND_LABEL, kind) ? KIND_LABEL[kind] : kind;
@@ -22 +22 @@ export function scanRatio(ev) {
```

Truncated: 47 further diff lines; see PR7.

### `editors/chrome/lib/store.js`

```diff
diff --git a/editors/chrome/lib/store.js b/editors/chrome/lib/store.js
index 37afeb9..40f32bd 100644
--- a/editors/chrome/lib/store.js
+++ b/editors/chrome/lib/store.js
@@ -9,2 +9,9 @@ export async function loadIndex(read) {
-  const meta = await read("meta.json", "json");
-  if (!meta) return null;
+  const safeRead = async (name, kind) => {
```

Truncated: 87 further diff lines; see PR7.

### `editors/chrome/lib/textsearch.js`

```diff
diff --git a/editors/chrome/lib/textsearch.js b/editors/chrome/lib/textsearch.js
index 1217c3f..495e8d7 100644
--- a/editors/chrome/lib/textsearch.js
+++ b/editors/chrome/lib/textsearch.js
@@ -8,0 +9,3 @@
+import { rawTokenSpans } from "./unicode61.js";
+export { rawTokenSpans };
+
```

Truncated: 128 further diff lines; see PR7.

### `editors/chrome/lib/ui.js`

```diff
diff --git a/editors/chrome/lib/ui.js b/editors/chrome/lib/ui.js
index ac93573..ba5971e 100644
--- a/editors/chrome/lib/ui.js
+++ b/editors/chrome/lib/ui.js
@@ -25,0 +26,2 @@ export function h(tag, attrs = {}, ...children) {
+const copies = new WeakMap();
+
@@ -27 +29,5 @@ export async function copyText(text, btn) {
```

Truncated: 61 further diff lines; see PR7.

### `editors/chrome/lib/unicode61.js`

```diff
diff --git a/editors/chrome/lib/unicode61.js b/editors/chrome/lib/unicode61.js
new file mode 100644
index 0000000..29407b5
--- /dev/null
+++ b/editors/chrome/lib/unicode61.js
@@ -0,0 +1,39 @@
+// Generated Unicode61 classification and simple folds. Regenerate with scripts/gen_unicode61.py.
+export const UNICODE61_PROVENANCE = {
```

Truncated: 37 further diff lines; see PR7.

### `editors/chrome/manifest.json`

```diff
diff --git a/editors/chrome/manifest.json b/editors/chrome/manifest.json
index ce1ba6a..abb749c 100644
--- a/editors/chrome/manifest.json
+++ b/editors/chrome/manifest.json
@@ -5 +5 @@
-  "version": "0.3.0",
+  "version": "0.7.1",
@@ -26,3 +26,14 @@
```

Truncated: 22 further diff lines; see PR7.

### `editors/chrome/package.json`

```diff
diff --git a/editors/chrome/package.json b/editors/chrome/package.json
index 3c1afd1..dadc261 100644
--- a/editors/chrome/package.json
+++ b/editors/chrome/package.json
@@ -3 +3 @@
-  "version": "0.3.0",
+  "version": "0.7.1",
@@ -9 +9 @@
```

Truncated: 2 further diff lines; see PR7.

### `editors/chrome/popup.html`

```diff
diff --git a/editors/chrome/popup.html b/editors/chrome/popup.html
index 328c200..61455a3 100644
--- a/editors/chrome/popup.html
+++ b/editors/chrome/popup.html
@@ -14 +14 @@
-    <span class="local" title="Search, lint and the optimizer run inside the extension. Nothing is sent anywhere.">runs locally</span>
+    <span class="local" title="Search, lint and the optimizer run inside the extension. Popup analysis and keyword search stay in the extension. Optional semantic or hybrid search in the app sends query text to your configured local Ollama service.">runs locally</span>
```

### `editors/chrome/popup.js`

```diff
diff --git a/editors/chrome/popup.js b/editors/chrome/popup.js
index c7c29f5..25bdd4a 100644
--- a/editors/chrome/popup.js
+++ b/editors/chrome/popup.js
@@ -2 +2 @@
-import { clamp, freshPending, grabSelection, pickSelection } from "./lib/capture.js";
+import { clamp, consumeHandoff, grabSelection, pickSelection, truncateText } from "./lib/capture.js";
@@ -12,0 +13,2 @@ const EXAMPLE = '{"t":{"$date":"2026-10-14T09:12:44.118+00:00"},"s":"I","c":"COM
```

Truncated: 69 further diff lines; see PR7.

### `editors/chrome/test/autoupdate.test.mjs`

```diff
diff --git a/editors/chrome/test/autoupdate.test.mjs b/editors/chrome/test/autoupdate.test.mjs
index a6ca0c5..e3190e6 100644
--- a/editors/chrome/test/autoupdate.test.mjs
+++ b/editors/chrome/test/autoupdate.test.mjs
@@ -26 +26,5 @@ test("readBuild tolerates a missing file and non-OK responses", async () => {
-  assert.deepEqual(await readBuild(async () => ({ ok: true, json: async () => ({ commit: "c1" }) }), runtime), { commit: "c1" });
+  assert.deepEqual(await readBuild(async (url, options) => {
+    assert.equal(url, "chrome-extension://x/data/build.json");
```

Truncated: 52 further diff lines; see PR7.

### `editors/chrome/test/browser-context.mjs`

```diff
diff --git a/editors/chrome/test/browser-context.mjs b/editors/chrome/test/browser-context.mjs
new file mode 100644
index 0000000..c5a2c30
--- /dev/null
+++ b/editors/chrome/test/browser-context.mjs
@@ -0,0 +1,26 @@
+// Lifecycle shared by opt-in browser scripts, also exercised with a synthetic Chromium API.
+import { mkdtempSync, rmSync } from "node:fs";
```

Truncated: 24 further diff lines; see PR7.

### `editors/chrome/test/browser-context.test.mjs`

```diff
diff --git a/editors/chrome/test/browser-context.test.mjs b/editors/chrome/test/browser-context.test.mjs
new file mode 100644
index 0000000..fc8707b
--- /dev/null
+++ b/editors/chrome/test/browser-context.test.mjs
@@ -0,0 +1,36 @@
+import { test } from "node:test";
+import assert from "node:assert/strict";
```

Truncated: 34 further diff lines; see PR7.

### `editors/chrome/test/debug-app.mjs`

```diff
diff --git a/editors/chrome/test/debug-app.mjs b/editors/chrome/test/debug-app.mjs
index 6e9f058..98e3f9a 100644
--- a/editors/chrome/test/debug-app.mjs
+++ b/editors/chrome/test/debug-app.mjs
@@ -3,3 +3 @@
-import { mkdtempSync, rmSync } from "node:fs";
-import { tmpdir } from "node:os";
-import { dirname, join, resolve } from "node:path";
```

Truncated: 35 further diff lines; see PR7.

### `editors/chrome/test/dom-fixture.mjs`

```diff
diff --git a/editors/chrome/test/dom-fixture.mjs b/editors/chrome/test/dom-fixture.mjs
new file mode 100644
index 0000000..e59529e
--- /dev/null
+++ b/editors/chrome/test/dom-fixture.mjs
@@ -0,0 +1,113 @@
+// Minimal synthetic DOM for executing the maintained page sources. No browser, profiles or network.
+import vm from "node:vm";
```

Truncated: 111 further diff lines; see PR7.

### `editors/chrome/test/e2e.mjs`

```diff
diff --git a/editors/chrome/test/e2e.mjs b/editors/chrome/test/e2e.mjs
index 0b26304..c6c367c 100644
--- a/editors/chrome/test/e2e.mjs
+++ b/editors/chrome/test/e2e.mjs
@@ -3 +3 @@
-//   PLAYWRIGHT=/path/to/node_modules/playwright node test/e2e.mjs [screenshot.png]
+//   PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs node test/e2e.mjs [screenshot.png]
@@ -7 +7 @@
```

Truncated: 93 further diff lines; see PR7.

### `editors/chrome/test/integrity.test.mjs`

```diff
diff --git a/editors/chrome/test/integrity.test.mjs b/editors/chrome/test/integrity.test.mjs
new file mode 100644
index 0000000..3c16adf
--- /dev/null
+++ b/editors/chrome/test/integrity.test.mjs
@@ -0,0 +1,139 @@
+import { test } from "node:test";
+import assert from "node:assert/strict";
```

Truncated: 137 further diff lines; see PR7.

### `editors/chrome/test/language-boundaries.test.mjs`

```diff
diff --git a/editors/chrome/test/language-boundaries.test.mjs b/editors/chrome/test/language-boundaries.test.mjs
new file mode 100644
index 0000000..e67d3fe
--- /dev/null
+++ b/editors/chrome/test/language-boundaries.test.mjs
@@ -0,0 +1,127 @@
+import { test } from "node:test";
+import assert from "node:assert/strict";
```

Truncated: 125 further diff lines; see PR7.

### `editors/chrome/test/lint-parity.test.mjs`

```diff
diff --git a/editors/chrome/test/lint-parity.test.mjs b/editors/chrome/test/lint-parity.test.mjs
index 50346b3..8af5c2f 100644
--- a/editors/chrome/test/lint-parity.test.mjs
+++ b/editors/chrome/test/lint-parity.test.mjs
@@ -33 +33 @@ for (const name of goldens) {
-  const text = readFileSync(join(ROOT, golden.source), "utf8");
+  const text = readFileSync(join(ROOT, golden.source), "utf8").replace(/\r\n?/g, "\n");
```

### `editors/chrome/test/normalization-boundaries.test.mjs`

```diff
diff --git a/editors/chrome/test/normalization-boundaries.test.mjs b/editors/chrome/test/normalization-boundaries.test.mjs
new file mode 100644
index 0000000..e291c8e
--- /dev/null
+++ b/editors/chrome/test/normalization-boundaries.test.mjs
@@ -0,0 +1,71 @@
+import {test} from 'node:test';
+import assert from 'node:assert/strict';
```

Truncated: 69 further diff lines; see PR7.

### `editors/chrome/test/optimizer-boundaries.test.mjs`

```diff
diff --git a/editors/chrome/test/optimizer-boundaries.test.mjs b/editors/chrome/test/optimizer-boundaries.test.mjs
new file mode 100644
index 0000000..34259c7
--- /dev/null
+++ b/editors/chrome/test/optimizer-boundaries.test.mjs
@@ -0,0 +1,140 @@
+import {test} from 'node:test';
+import assert from 'node:assert/strict';
```

Truncated: 138 further diff lines; see PR7.

### `editors/chrome/test/page-races.test.mjs`

```diff
diff --git a/editors/chrome/test/page-races.test.mjs b/editors/chrome/test/page-races.test.mjs
new file mode 100644
index 0000000..26eb927
--- /dev/null
+++ b/editors/chrome/test/page-races.test.mjs
@@ -0,0 +1,219 @@
+import { test } from "node:test";
+import assert from "node:assert/strict";
```

Truncated: 217 further diff lines; see PR7.

### `editors/chrome/test/parity.test.mjs`

```diff
diff --git a/editors/chrome/test/parity.test.mjs b/editors/chrome/test/parity.test.mjs
index e85b73b..a1d56cb 100644
--- a/editors/chrome/test/parity.test.mjs
+++ b/editors/chrome/test/parity.test.mjs
@@ -5 +5 @@ import assert from "node:assert/strict";
-import { readFileSync, readdirSync } from "node:fs";
+import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
@@ -7,0 +8,2 @@ import { fileURLToPath } from "node:url";
```

Truncated: 168 further diff lines; see PR7.

### `editors/chrome/test/rendering.test.mjs`

```diff
diff --git a/editors/chrome/test/rendering.test.mjs b/editors/chrome/test/rendering.test.mjs
new file mode 100644
index 0000000..689643e
--- /dev/null
+++ b/editors/chrome/test/rendering.test.mjs
@@ -0,0 +1,41 @@
+import { test } from "node:test";
+import assert from "node:assert/strict";
```

Truncated: 39 further diff lines; see PR7.

### `editors/chrome/test/run-tests.mjs`

```diff
diff --git a/editors/chrome/test/run-tests.mjs b/editors/chrome/test/run-tests.mjs
new file mode 100644
index 0000000..1c39da7
--- /dev/null
+++ b/editors/chrome/test/run-tests.mjs
@@ -0,0 +1,11 @@
+// Enumerate only the unit suites; do not include opt-in browser scripts or batch helpers.
+import { readdirSync } from "node:fs";
```

Truncated: 9 further diff lines; see PR7.

### `editors/chrome/test/search-batch.mjs`

```diff
diff --git a/editors/chrome/test/search-batch.mjs b/editors/chrome/test/search-batch.mjs
index 8b1a4c2..508ca10 100644
--- a/editors/chrome/test/search-batch.mjs
+++ b/editors/chrome/test/search-batch.mjs
@@ -20,5 +20,12 @@ const pairs = (hits) => hits.map((h) => [h.id, h.score]);
-const out = JSON.parse(raw).map(({ q, qvec, ...opts }) => ({
-  keyword: pairs(idx.keyword(q, 10, opts)),
-  semantic: qvec ? pairs(idx.semanticVec(qvec, 10, opts)) : [],
```

Truncated: 14 further diff lines; see PR7.

### `editors/chrome/test/search-parity.test.mjs`

```diff
diff --git a/editors/chrome/test/search-parity.test.mjs b/editors/chrome/test/search-parity.test.mjs
index d6215b6..5486fb8 100644
--- a/editors/chrome/test/search-parity.test.mjs
+++ b/editors/chrome/test/search-parity.test.mjs
@@ -10 +10 @@ import { loadIndex } from "../lib/store.js";
-import { porter, queryTerms, snippet, tokens } from "../lib/textsearch.js";
+import { SearchIndex, porter, queryTerms, snippet, tokens } from "../lib/textsearch.js";
@@ -33,2 +33,5 @@ function same(actual, expected, label) {
```

Truncated: 30 further diff lines; see PR7.

### `editors/chrome/test/search-rendering-boundaries.test.mjs`

```diff
diff --git a/editors/chrome/test/search-rendering-boundaries.test.mjs b/editors/chrome/test/search-rendering-boundaries.test.mjs
new file mode 100644
index 0000000..92f97f9
--- /dev/null
+++ b/editors/chrome/test/search-rendering-boundaries.test.mjs
@@ -0,0 +1,16 @@
+import { fileURLToPath } from "node:url";
+// Additional completed gate1 candidates, with in-memory data and real maintained source only.
```

Truncated: 14 further diff lines; see PR7.

### `editors/chrome/test/ui-boundaries.test.mjs`

```diff
diff --git a/editors/chrome/test/ui-boundaries.test.mjs b/editors/chrome/test/ui-boundaries.test.mjs
new file mode 100644
index 0000000..c456ce5
--- /dev/null
+++ b/editors/chrome/test/ui-boundaries.test.mjs
@@ -0,0 +1,40 @@
+import { fileURLToPath } from "node:url";
+// Regressions use synthetic data and the maintained runtime modules.
```

Truncated: 38 further diff lines; see PR7.

### `editors/chrome/test/ui.test.mjs`

```diff
diff --git a/editors/chrome/test/ui.test.mjs b/editors/chrome/test/ui.test.mjs
index fd70585..5acbb86 100644
--- a/editors/chrome/test/ui.test.mjs
+++ b/editors/chrome/test/ui.test.mjs
@@ -40,0 +41,9 @@ test("freshPending accepts only recent, non-blank handoffs", () => {
+// A syntactic coverage guard for literal finding codes, including multiline ternary severity arguments.
+function findingCodes(source) {
+  return new Set([...source.matchAll(/(?:\b(?:BLOCKING|HIGH|MEDIUM|LOW)|\?\s*(?:HIGH|MEDIUM|LOW)\s*:\s*(?:HIGH|MEDIUM|LOW))\s*,\s*["']([a-z0-9-]+)["']/g)].map(m => m[1]));
```

Truncated: 33 further diff lines; see PR7.

### `editors/vscode/extension.js`

```diff
diff --git a/editors/vscode/extension.js b/editors/vscode/extension.js
index ce1c0d4..c93b6ae 100644
--- a/editors/vscode/extension.js
+++ b/editors/vscode/extension.js
@@ -6,0 +7,2 @@ let client;
+let active = false;
+let transition = Promise.resolve();
@@ -8 +10,16 @@ let client;
```

Truncated: 51 further diff lines; see PR7.

### `editors/vscode/language-configuration.json`

```diff
diff --git a/editors/vscode/language-configuration.json b/editors/vscode/language-configuration.json
index 6568379..4f41611 100644
--- a/editors/vscode/language-configuration.json
+++ b/editors/vscode/language-configuration.json
@@ -2,2 +2,21 @@
-  "comments": { "lineComment": "//", "blockComment": ["/*", "*/"] },
-  "brackets": [["{", "}"], ["[", "]"], ["(", ")"]],
+  "comments": {
```

Truncated: 76 further diff lines; see PR7.

### `editors/vscode/package-lock.json`

```diff
diff --git a/editors/vscode/package-lock.json b/editors/vscode/package-lock.json
index 14c59af..775d0b3 100644
--- a/editors/vscode/package-lock.json
+++ b/editors/vscode/package-lock.json
@@ -15 +15 @@
-        "@vscode/vsce": "^3.0.0"
+        "@vscode/vsce": "^4.1.0"
@@ -21,17 +20,0 @@
```

Truncated: 3047 further diff lines; see PR7.

### `editors/vscode/package.json`

```diff
diff --git a/editors/vscode/package.json b/editors/vscode/package.json
index 36b6f15..1cc712b 100644
--- a/editors/vscode/package.json
+++ b/editors/vscode/package.json
@@ -8,4 +8,18 @@
-  "repository": { "type": "git", "url": "https://github.com/mithudso/mdb-expertise-search.git", "directory": "editors/vscode" },
-  "engines": { "vscode": "^1.85.0" },
-  "categories": ["Programming Languages", "Linters"],
```

Truncated: 88 further diff lines; see PR7.

### `editors/vscode/server-path.js`

```diff
diff --git a/editors/vscode/server-path.js b/editors/vscode/server-path.js
index bae3d72..5f5734e 100644
--- a/editors/vscode/server-path.js
+++ b/editors/vscode/server-path.js
@@ -9 +9 @@ const path = require('path');
-function resolveServerCommand(configured, workspaceFolders, platform = process.platform, exists = fs.existsSync) {
+function resolveServerCommand(configured, workspaceFolders, platform = process.platform, exists = candidate => { try { if (!fs.statSync(candidate).isFile()) return false; if (platform !== "win32") fs.accessSync(candidate, fs.constants.X_OK); return true; } catch { return false; } }) {
```

### `editors/vscode/syntaxes/mql.tmLanguage.json`

```diff
diff --git a/editors/vscode/syntaxes/mql.tmLanguage.json b/editors/vscode/syntaxes/mql.tmLanguage.json
index e1c64df..4540661 100644
--- a/editors/vscode/syntaxes/mql.tmLanguage.json
+++ b/editors/vscode/syntaxes/mql.tmLanguage.json
@@ -5 +5,11 @@
-  "patterns": [{ "include": "#comment" }, { "include": "#value" }, { "include": "#statement-words" }],
+  "patterns": [
+    {
```

Truncated: 158 further diff lines; see PR7.

### `editors/vscode/test/server-path.test.js`

```diff
diff --git a/editors/vscode/test/server-path.test.js b/editors/vscode/test/server-path.test.js
index 3c00b0b..1414008 100644
--- a/editors/vscode/test/server-path.test.js
+++ b/editors/vscode/test/server-path.test.js
@@ -22,0 +23 @@ test('manifest and grammar are valid JSON and consistent', () => {
+  const fs = require('node:fs');
@@ -24,3 +25,7 @@ test('manifest and grammar are valid JSON and consistent', () => {
-  const g = require('../syntaxes/mql.tmLanguage.json');
```

Truncated: 136 further diff lines; see PR7.

### `examples/slow-queries.mql`

```diff
diff --git a/examples/slow-queries.mql b/examples/slow-queries.mql
index 54a8bdd..c1e95b0 100644
--- a/examples/slow-queries.mql
+++ b/examples/slow-queries.mql
@@ -17 +17 @@ db.orders.find(
-  { customerId: 1, total: 1, createdAt: 1 }
+  { customerId: 1, total: 1, createdAt: 1, _id: 0 }
@@ -28 +28 @@ db.events.aggregate([
```

Truncated: 2 further diff lines; see PR7.

### `mdbx/__init__.py`

```diff
diff --git a/mdbx/__init__.py b/mdbx/__init__.py
index 938472b..8e0a18f 100644
--- a/mdbx/__init__.py
+++ b/mdbx/__init__.py
@@ -3 +3 @@
-__version__ = "0.7.0"
+__version__ = "0.7.1"
```

### `mdbx/cli.py`

```diff
diff --git a/mdbx/cli.py b/mdbx/cli.py
index dab3007..c8db464 100644
--- a/mdbx/cli.py
+++ b/mdbx/cli.py
@@ -6,0 +7,3 @@ import sys
+import unicodedata
+from bisect import bisect_right
+from contextlib import closing
```

Truncated: 243 further diff lines; see PR7.

### `mdbx/corpus.py`

```diff
diff --git a/mdbx/corpus.py b/mdbx/corpus.py
index 99e6ddb..4af7498 100644
--- a/mdbx/corpus.py
+++ b/mdbx/corpus.py
@@ -5,0 +6 @@ import logging
+import os
@@ -10,0 +12,2 @@ from pathlib import Path
+from .safety import open_confined
```

Truncated: 70 further diff lines; see PR7.

### `mdbx/embed.py`

```diff
diff --git a/mdbx/embed.py b/mdbx/embed.py
index 709a520..fe0d7ff 100644
--- a/mdbx/embed.py
+++ b/mdbx/embed.py
@@ -17 +17,10 @@ import numpy as np
-from ollama_client import OllamaClient, OllamaPool, OllamaUnavailable
+
+try:
```

Truncated: 46 further diff lines; see PR7.

### `mdbx/embed_onnx.py`

```diff
diff --git a/mdbx/embed_onnx.py b/mdbx/embed_onnx.py
index 0b29944..26c303f 100644
--- a/mdbx/embed_onnx.py
+++ b/mdbx/embed_onnx.py
@@ -15,0 +16 @@ import os
+import threading
@@ -35 +36,4 @@ def _local_dir() -> Path | None:
-    return Path(raw).expanduser() if raw else None
```

Truncated: 59 further diff lines; see PR7.

### `mdbx/index.py`

```diff
diff --git a/mdbx/index.py b/mdbx/index.py
index 4638077..6327edd 100644
--- a/mdbx/index.py
+++ b/mdbx/index.py
@@ -3,0 +4 @@ from __future__ import annotations
+import itertools
@@ -6,0 +8 @@ import sqlite3
+import tempfile
```

Truncated: 215 further diff lines; see PR7.

### `mdbx/mcp_server.py`

```diff
diff --git a/mdbx/mcp_server.py b/mdbx/mcp_server.py
index f5185fc..774fb02 100644
--- a/mdbx/mcp_server.py
+++ b/mdbx/mcp_server.py
@@ -3,0 +4,2 @@ from __future__ import annotations
+from bisect import bisect_right
+
@@ -13,0 +16 @@ from .mql.optimize import optimize, to_dict
```

Truncated: 44 further diff lines; see PR7.

### `mdbx/mql/analyze.py`

```diff
diff --git a/mdbx/mql/analyze.py b/mdbx/mql/analyze.py
index e94fc9d..437beb6 100644
--- a/mdbx/mql/analyze.py
+++ b/mdbx/mql/analyze.py
@@ -8,0 +9,2 @@ from __future__ import annotations
+import math
+import unicodedata
@@ -66,2 +68,2 @@ class Result:
```

Truncated: 222 further diff lines; see PR7.

### `mdbx/mql/features.py`

```diff
diff --git a/mdbx/mql/features.py b/mdbx/mql/features.py
index 12103af..0848fb8 100644
--- a/mdbx/mql/features.py
+++ b/mdbx/mql/features.py
@@ -3 +3 @@
-Pure functions over text offsets so they can be unit-tested without any LSP machinery.
+Features use text offsets and need no LSP machinery. Optional hover enrichment may perform I/O.
@@ -12,0 +13 @@ from .analyze import METHODS, Result
```

Truncated: 148 further diff lines; see PR7.

### `mdbx/mql/normalize.py`

```diff
diff --git a/mdbx/mql/normalize.py b/mdbx/mql/normalize.py
index f146b05..7a55547 100644
--- a/mdbx/mql/normalize.py
+++ b/mdbx/mql/normalize.py
@@ -12 +12 @@ Accepted input, in the order it is recognised:
-  placeholder collection named ``collection``.
+  unknown collection; recommendations omit ordinary source indexes.
@@ -16,0 +17,2 @@ Log and profiler measurements are kept as ``evidence`` for the optimizer's P9 fi
```

Truncated: 328 further diff lines; see PR7.

### `mdbx/mql/operators.py`

```diff
diff --git a/mdbx/mql/operators.py b/mdbx/mql/operators.py
index 4bab366..d111579 100644
--- a/mdbx/mql/operators.py
+++ b/mdbx/mql/operators.py
@@ -29 +29 @@ $densify|stage|object|Creates missing documents in a sequence of values.
-$documents|stage|array|Returns literal documents as the pipeline input (first stage).
+$documents|stage|any|Returns literal documents as the pipeline input (first stage).
@@ -75 +75 @@ $jsonSchema|qtop|object|Matches documents that validate against a JSON Schema.
```

Truncated: 17 further diff lines; see PR7.

### `mdbx/mql/optimize.py`

```diff
diff --git a/mdbx/mql/optimize.py b/mdbx/mql/optimize.py
index 16485dd..1cad565 100644
--- a/mdbx/mql/optimize.py
+++ b/mdbx/mql/optimize.py
@@ -17,0 +18,2 @@ from __future__ import annotations
+import json
+import math
@@ -18,0 +21,2 @@ import re
```

Truncated: 404 further diff lines; see PR7.

### `mdbx/mql/parser.py`

```diff
diff --git a/mdbx/mql/parser.py b/mdbx/mql/parser.py
index 0c93a09..e8adf2f 100644
--- a/mdbx/mql/parser.py
+++ b/mdbx/mql/parser.py
@@ -16 +16 @@ _IDENT = re.compile(r"[A-Za-z_$][\w$]*")
-_NUMBER = re.compile(r"[-+]?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|Infinity|NaN)")
+_NUMBER = re.compile(r"[-+]?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|(?:Infinity|NaN)(?![\w$]))")
@@ -18,0 +19 @@ _DECL = {"const", "let", "var"}
```

Truncated: 176 further diff lines; see PR7.

### `mdbx/mql/server.py`

```diff
diff --git a/mdbx/mql/server.py b/mdbx/mql/server.py
index 443b8ee..bb1a5e4 100644
--- a/mdbx/mql/server.py
+++ b/mdbx/mql/server.py
@@ -11,0 +12 @@ import os
+import re
@@ -12,0 +14,3 @@ import sys
+from array import array
```

Truncated: 139 further diff lines; see PR7.

### `mdbx/providers.py`

```diff
diff --git a/mdbx/providers.py b/mdbx/providers.py
index 28b6a8b..6507ee8 100644
--- a/mdbx/providers.py
+++ b/mdbx/providers.py
@@ -12,0 +13 @@ from __future__ import annotations
+import json
@@ -26 +27,4 @@ SYSTEM_PROMPT = (
-    "explain() checks over generalities. Never invent option names or version numbers."
```

Truncated: 39 further diff lines; see PR7.

### `mdbx/recipes.py`

```diff
diff --git a/mdbx/recipes.py b/mdbx/recipes.py
index 6bd2615..6584e13 100644
--- a/mdbx/recipes.py
+++ b/mdbx/recipes.py
@@ -12,0 +13 @@ from . import index as idx
+from .safety import open_confined
@@ -30 +31,2 @@ class Recipe:
-        return (base / self.path).read_text(encoding="utf-8", errors="replace")
```

Truncated: 33 further diff lines; see PR7.

### `mdbx/safety.py`

```diff
diff --git a/mdbx/safety.py b/mdbx/safety.py
new file mode 100644
index 0000000..3258c74
--- /dev/null
+++ b/mdbx/safety.py
@@ -0,0 +1,204 @@
+"""Confined file access and publication that preserves concurrent edits."""
+from __future__ import annotations
```

Truncated: 202 further diff lines; see PR7.

### `mdbx/search.py`

```diff
diff --git a/mdbx/search.py b/mdbx/search.py
index 13896e0..8979a6a 100644
--- a/mdbx/search.py
+++ b/mdbx/search.py
@@ -5 +5 @@ import logging
-import re
+import os
@@ -6,0 +7 @@ import sqlite3
```

Truncated: 236 further diff lines; see PR7.

### `mdbx/tui.py`

```diff
diff --git a/mdbx/tui.py b/mdbx/tui.py
index 4e25df1..e88d34b 100644
--- a/mdbx/tui.py
+++ b/mdbx/tui.py
@@ -14,0 +15 @@ try:
+    from rich.cells import cell_len, set_cell_size
@@ -46,3 +47,6 @@ def facet_label(source: str, n: int, width: int | None = None) -> Text:
-    if width is not None and len(source) + len(count) > width:
```

Truncated: 116 further diff lines; see PR7.

### `mdbx/unicode61.py`

```diff
diff --git a/mdbx/unicode61.py b/mdbx/unicode61.py
new file mode 100644
index 0000000..1345a61
--- /dev/null
+++ b/mdbx/unicode61.py
@@ -0,0 +1,1733 @@
+"""Generated Unicode61 classification and simple folds. Regenerate with scripts/gen_unicode61.py."""
+from bisect import bisect_right
```

Truncated: 1731 further diff lines; see PR7.

### `mdbx/webexport.py`

```diff
diff --git a/mdbx/webexport.py b/mdbx/webexport.py
index 805c63d..67350b8 100644
--- a/mdbx/webexport.py
+++ b/mdbx/webexport.py
@@ -25 +25,2 @@ import math
-import re
+import os
+import shutil
```

Truncated: 221 further diff lines; see PR7.

### `memory.md`

```diff
diff --git a/memory.md b/memory.md
index 36fd62a..05a813d 100644
--- a/memory.md
+++ b/memory.md
@@ -145,0 +146,12 @@
+
+
+## v0.7.1 — 2026-11-12 maintenance
```

Truncated: 9 further diff lines; see PR7.

### `prompts.md`

```diff
diff --git a/prompts.md b/prompts.md
index b789ad7..0e0b4c8 100644
--- a/prompts.md
+++ b/prompts.md
@@ -47,0 +48,12 @@
+
+
+## v0.7.1 — 2026-11-12 maintenance
```

Truncated: 9 further diff lines; see PR7.

### `pyproject.toml`

```diff
diff --git a/pyproject.toml b/pyproject.toml
index cfdfbc6..b4cf4cb 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -7 +7 @@ name = "mdb-expertise-search"
-version = "0.7.0"
+version = "0.7.1"
@@ -14 +14 @@ keywords = ["mongodb", "atlas", "semantic-search", "fts5", "tui", "llms.txt"]
```

Truncated: 4 further diff lines; see PR7.

### `scripts/check_chrome_doc_links.py`

```diff
diff --git a/scripts/check_chrome_doc_links.py b/scripts/check_chrome_doc_links.py
index edd644f..c07cfde 100755
--- a/scripts/check_chrome_doc_links.py
+++ b/scripts/check_chrome_doc_links.py
@@ -19,3 +19,11 @@ def urls() -> list[str]:
-    base = re.search(r'const M = "([^"]+)"', SRC).group(1)
-    found = {base + m for m in re.findall(r'M \+ "([^"]+)"', SRC)}
-    found |= set(re.findall(r'"(https://[^"]+)"', SRC)) - {base}
```

Truncated: 11 further diff lines; see PR7.

### `scripts/check_doc_indexes.py`

```diff
diff --git a/scripts/check_doc_indexes.py b/scripts/check_doc_indexes.py
index 8507c4e..bd78ede 100755
--- a/scripts/check_doc_indexes.py
+++ b/scripts/check_doc_indexes.py
@@ -8 +8 @@ ROOT = Path(__file__).resolve().parent.parent
-missing = [e["path"] for e in json.loads((ROOT / "docs" / "high_signal_file_index.json").read_text())
+missing = [e["path"] for e in json.loads((ROOT / "docs" / "high_signal_file_index.json").read_text(encoding="utf-8"))
```

### `scripts/chrome_extension_autoupdate.py`

```diff
diff --git a/scripts/chrome_extension_autoupdate.py b/scripts/chrome_extension_autoupdate.py
index f560f4a..b7b13f8 100755
--- a/scripts/chrome_extension_autoupdate.py
+++ b/scripts/chrome_extension_autoupdate.py
@@ -31,0 +32 @@ import plistlib
+import re
@@ -38,0 +40,11 @@ from pathlib import Path
+sys.path.insert(0, str(Path(__file__).resolve().parent))
```

Truncated: 290 further diff lines; see PR7.

### `scripts/corpus_autoupdate.py`

```diff
diff --git a/scripts/corpus_autoupdate.py b/scripts/corpus_autoupdate.py
index 227f7e6..fef83c2 100755
--- a/scripts/corpus_autoupdate.py
+++ b/scripts/corpus_autoupdate.py
@@ -22 +22 @@ rules and the customer denylist stay in ``~/.config/mdbx/`` (``redactions.py``,
-pass warns when they are missing, because then only the built-in markers are checked. Log:
+pass aborts if the denylist is missing and warns if private redaction rules are missing. Log:
@@ -36,0 +37,10 @@ from pathlib import Path
```

Truncated: 186 further diff lines; see PR7.

### `scripts/gen_chrome_operators.py`

```diff
diff --git a/scripts/gen_chrome_operators.py b/scripts/gen_chrome_operators.py
index 4cd5195..00c1254 100755
--- a/scripts/gen_chrome_operators.py
+++ b/scripts/gen_chrome_operators.py
@@ -62 +62 @@ def main() -> int:
-             if not p.is_file() or p.read_text(encoding="utf-8") != text]
+             if not p.is_file() or p.read_bytes() != text.encode("utf-8")]
@@ -69 +69 @@ def main() -> int:
```

Truncated: 2 further diff lines; see PR7.

### `scripts/gen_file_index.py`

```diff
diff --git a/scripts/gen_file_index.py b/scripts/gen_file_index.py
index deffd0f..27cb13e 100755
--- a/scripts/gen_file_index.py
+++ b/scripts/gen_file_index.py
@@ -3,0 +4,3 @@ import json
+import os
+import re
+import stat
```

Truncated: 46 further diff lines; see PR7.

### `scripts/gen_lint_golden.py`

```diff
diff --git a/scripts/gen_lint_golden.py b/scripts/gen_lint_golden.py
index e9141fa..14e6541 100755
--- a/scripts/gen_lint_golden.py
+++ b/scripts/gen_lint_golden.py
@@ -22,0 +23,3 @@ import sys
+from array import array
+from bisect import bisect_left, bisect_right
+from functools import lru_cache
```

Truncated: 40 further diff lines; see PR7.

### `scripts/gen_optimizer_golden.py`

```diff
diff --git a/scripts/gen_optimizer_golden.py b/scripts/gen_optimizer_golden.py
index 5847c53..671c743 100755
--- a/scripts/gen_optimizer_golden.py
+++ b/scripts/gen_optimizer_golden.py
@@ -29,2 +29,3 @@ def golden(text: str, name: str) -> str:
-    data = {"apply": to_dict(optimize(text)), "read_only": to_dict(optimize(text, apply=False)),
-            "report": format_report(optimize(text), name)}
+    applied = optimize(text)
```

Truncated: 6 further diff lines; see PR7.

### `scripts/gen_recipes_index.py`

```diff
diff --git a/scripts/gen_recipes_index.py b/scripts/gen_recipes_index.py
index 62eb929..3ad3f1b 100755
--- a/scripts/gen_recipes_index.py
+++ b/scripts/gen_recipes_index.py
@@ -6 +6,2 @@ import sys
-from pathlib import Path
+from pathlib import Path, PurePosixPath
+from urllib.parse import quote
```

Truncated: 42 further diff lines; see PR7.

### `scripts/gen_search_golden.py`

```diff
diff --git a/scripts/gen_search_golden.py b/scripts/gen_search_golden.py
index 8fd7be3..8c9a283 100755
--- a/scripts/gen_search_golden.py
+++ b/scripts/gen_search_golden.py
@@ -18,0 +19 @@ import math
+import os
@@ -21,0 +23,2 @@ import tempfile
+import uuid
```

Truncated: 93 further diff lines; see PR7.

### `scripts/gen_unicode61.py`

```diff
diff --git a/scripts/gen_unicode61.py b/scripts/gen_unicode61.py
new file mode 100644
index 0000000..e24dcb0
--- /dev/null
+++ b/scripts/gen_unicode61.py
@@ -0,0 +1,115 @@
+"""Regenerate the Unicode61 lookup using synthetic single-scalar in-memory SQLite rows only."""
+from __future__ import annotations
```

Truncated: 113 further diff lines; see PR7.

### `scripts/glean_cli_helper.py`

```diff
diff --git a/scripts/glean_cli_helper.py b/scripts/glean_cli_helper.py
index 61fe35c..6c30da2 100755
--- a/scripts/glean_cli_helper.py
+++ b/scripts/glean_cli_helper.py
@@ -14 +14 @@ Same contract as the Glean native-messaging hosts in mdb-[REDACTED] / [REDACTED]-da
-Exit codes: 0 ok · 1 failed · 2 glean CLI not installed · 3 not authenticated (run login).
+Exit codes: 0 ok · 1 failed · 2 glean CLI or ai-auth library not installed · 3 not authenticated (run login).
@@ -25,4 +25,7 @@ try:
```

Truncated: 11 further diff lines; see PR7.

### `scripts/install.sh`

```diff
diff --git a/scripts/install.sh b/scripts/install.sh
index 32b398b..c4fe799 100755
--- a/scripts/install.sh
+++ b/scripts/install.sh
@@ -9 +9,2 @@ set -euo pipefail
-cd "$(dirname "$0")/.."
+SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
+cd "$(dirname "$SCRIPT_PATH")/.."
```

Truncated: 40 further diff lines; see PR7.

### `scripts/maintenance_safety.py`

```diff
diff --git a/scripts/maintenance_safety.py b/scripts/maintenance_safety.py
new file mode 100644
index 0000000..be67d14
--- /dev/null
+++ b/scripts/maintenance_safety.py
@@ -0,0 +1,178 @@
+"""Small preservation primitives shared by local maintenance commands."""
+import fcntl
```

Truncated: 176 further diff lines; see PR7.

### `scripts/offline_test.py`

```diff
diff --git a/scripts/offline_test.py b/scripts/offline_test.py
new file mode 100755
index 0000000..99e14d8
--- /dev/null
+++ b/scripts/offline_test.py
@@ -0,0 +1,33 @@
+#!/usr/bin/env python3
+"""macOS offline checks with process-tree egress denial and scratch-only test state."""
```

Truncated: 31 further diff lines; see PR7.

### `scripts/package_chrome_extension.py`

```diff
diff --git a/scripts/package_chrome_extension.py b/scripts/package_chrome_extension.py
index d4cab2b..77ec112 100755
--- a/scripts/package_chrome_extension.py
+++ b/scripts/package_chrome_extension.py
@@ -4 +4 @@
-Steps: export the committed corpus and its search index into editors/chrome/data/ (``mdbx export-web``:
+Steps: export the committed corpus and its search index into invocation-owned scratch storage (``mdbx export-web``:
@@ -16,0 +17 @@ import datetime as dt
```

Truncated: 131 further diff lines; see PR7.

### `scripts/redact_corpus.py`

```diff
diff --git a/scripts/redact_corpus.py b/scripts/redact_corpus.py
index e6a0cf8..793f1c7 100755
--- a/scripts/redact_corpus.py
+++ b/scripts/redact_corpus.py
@@ -14,0 +15 @@ from __future__ import annotations
+import contextlib
@@ -15,0 +17 @@ import importlib.util
+import io
```

Truncated: 115 further diff lines; see PR7.

### `scripts/rotate_workflow_logs.py`

```diff
diff --git a/scripts/rotate_workflow_logs.py b/scripts/rotate_workflow_logs.py
index 47df2a3..f2bfd6a 100755
--- a/scripts/rotate_workflow_logs.py
+++ b/scripts/rotate_workflow_logs.py
@@ -14,0 +15 @@ import datetime as dt
+import os
@@ -15,0 +17 @@ import re
+import stat
```

Truncated: 62 further diff lines; see PR7.

### `scripts/sweep_customers.py`

```diff
diff --git a/scripts/sweep_customers.py b/scripts/sweep_customers.py
index 551ddf2..ffbb382 100755
--- a/scripts/sweep_customers.py
+++ b/scripts/sweep_customers.py
@@ -6 +6,2 @@ denylist file OUTSIDE this repo (one regex per line): $MDBX_DENYLIST or ~/.confi
-Checks every non-ignored file under corpus/ (git ls-files), so private local-only files do not trip it.
+Checks tracked and non-ignored untracked files under corpus/. Ignored private files are excluded.
+All selected files must be readable UTF-8 text; unsupported or symlink entries fail the gate.
```

Truncated: 94 further diff lines; see PR7.

### `scripts/sync_corpus.sh`

```diff
diff --git a/scripts/sync_corpus.sh b/scripts/sync_corpus.sh
index 110996c..a09f691 100755
--- a/scripts/sync_corpus.sh
+++ b/scripts/sync_corpus.sh
@@ -9,0 +10,7 @@ DOCS_SRC="${MDBX_MONGODB_DOCS_LLMS:-$HOME/dev/llms-explorer/outputs/exports/mong
+gate_log="$(mktemp)"
+trap 'rm -f "$gate_log"' EXIT
+if [ ! -f "${MDBX_DENYLIST:-$HOME/.config/mdbx/denylist.txt}" ]; then
```

Truncated: 53 further diff lines; see PR7.

### `scripts/sync_corpus_sources.py`

```diff
diff --git a/scripts/sync_corpus_sources.py b/scripts/sync_corpus_sources.py
new file mode 100644
index 0000000..8e836d6
--- /dev/null
+++ b/scripts/sync_corpus_sources.py
@@ -0,0 +1,129 @@
+"""Copy publication text from one available source family and reconcile prior owned files."""
+from __future__ import annotations
```

Truncated: 127 further diff lines; see PR7.

### `scripts/test_isolation.py`

```diff
diff --git a/scripts/test_isolation.py b/scripts/test_isolation.py
new file mode 100644
index 0000000..3e2f3e1
--- /dev/null
+++ b/scripts/test_isolation.py
@@ -0,0 +1,214 @@
+"""Fixture-only scratch state and synthetic factories for offline test processes.
+
```

Truncated: 212 further diff lines; see PR7.

### `scripts/watch_and_index.sh`

```diff
diff --git a/scripts/watch_and_index.sh b/scripts/watch_and_index.sh
index 988d419..a4b39d0 100755
--- a/scripts/watch_and_index.sh
+++ b/scripts/watch_and_index.sh
@@ -7 +7,2 @@ cd "$(dirname "$0")/.."
-CORPUS="${MDBX_CORPUS:-corpus}"
+export MDBX_CORPUS="${MDBX_CORPUS:-corpus}"
+CORPUS="$MDBX_CORPUS"
```

Truncated: 30 further diff lines; see PR7.

### `tests/conftest.py`

```diff
diff --git a/tests/conftest.py b/tests/conftest.py
index 7001c7f..fd4b3ac 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -1 +1,19 @@
-"""Tests assume Ollama is the embedder unless a test opts into another backend."""
+"""Synthetic offline tests: isolate state and factories before product imports.
+
```

Truncated: 46 further diff lines; see PR7.

### `tests/fixtures/lint/facet-and-update-pipelines.lint.json`

```diff
diff --git a/tests/fixtures/lint/facet-and-update-pipelines.lint.json b/tests/fixtures/lint/facet-and-update-pipelines.lint.json
index ac69796..6504229 100644
--- a/tests/fixtures/lint/facet-and-update-pipelines.lint.json
+++ b/tests/fixtures/lint/facet-and-update-pipelines.lint.json
@@ -102,0 +103,10 @@
+    {
+      "code": "bad-argument",
+      "column": 33,
```

Truncated: 18 further diff lines; see PR7.

### `tests/fixtures/lint/garbage.lint.json`

```diff
diff --git a/tests/fixtures/lint/garbage.lint.json b/tests/fixtures/lint/garbage.lint.json
index 278a3eb..0ea6898 100644
--- a/tests/fixtures/lint/garbage.lint.json
+++ b/tests/fixtures/lint/garbage.lint.json
@@ -3,10 +2,0 @@
-    {
-      "code": "syntax",
-      "column": 14,
```

Truncated: 110 further diff lines; see PR7.

### `tests/fixtures/lint/optimizer-slowlog-multi.lint.json`

```diff
diff --git a/tests/fixtures/lint/optimizer-slowlog-multi.lint.json b/tests/fixtures/lint/optimizer-slowlog-multi.lint.json
index 4cd4a83..0797fb2 100644
--- a/tests/fixtures/lint/optimizer-slowlog-multi.lint.json
+++ b/tests/fixtures/lint/optimizer-slowlog-multi.lint.json
@@ -2 +2,12 @@
-  "diagnostics": [],
+  "diagnostics": [
+    {
```

Truncated: 10 further diff lines; see PR7.

### `tests/fixtures/lint/pipeline-positions.lint.json`

```diff
diff --git a/tests/fixtures/lint/pipeline-positions.lint.json b/tests/fixtures/lint/pipeline-positions.lint.json
index 9bf41cd..2c9a7c7 100644
--- a/tests/fixtures/lint/pipeline-positions.lint.json
+++ b/tests/fixtures/lint/pipeline-positions.lint.json
@@ -282,0 +283,10 @@
+    {
+      "code": "bad-argument",
+      "column": 24,
```

Truncated: 18 further diff lines; see PR7.

### `tests/fixtures/lint/query-operators.lint.json`

```diff
diff --git a/tests/fixtures/lint/query-operators.lint.json b/tests/fixtures/lint/query-operators.lint.json
index 1a931fe..3f681eb 100644
--- a/tests/fixtures/lint/query-operators.lint.json
+++ b/tests/fixtures/lint/query-operators.lint.json
@@ -9 +9 @@
-      "message": "$or requires a non-empty array.",
+      "message": "$or expects a non-empty array, got array.",
@@ -39 +39 @@
```

Truncated: 71 further diff lines; see PR7.

### `tests/fixtures/lint/sort-and-accumulators.lint.json`

```diff
diff --git a/tests/fixtures/lint/sort-and-accumulators.lint.json b/tests/fixtures/lint/sort-and-accumulators.lint.json
index 87ac0de..a1829fe 100644
--- a/tests/fixtures/lint/sort-and-accumulators.lint.json
+++ b/tests/fixtures/lint/sort-and-accumulators.lint.json
@@ -232,0 +233,10 @@
+    {
+      "code": "misplaced-operator",
+      "column": 44,
```

Truncated: 18 further diff lines; see PR7.

### `tests/fixtures/lint/variables-and-bare.lint.json`

```diff
diff --git a/tests/fixtures/lint/variables-and-bare.lint.json b/tests/fixtures/lint/variables-and-bare.lint.json
index c51bddd..dadc757 100644
--- a/tests/fixtures/lint/variables-and-bare.lint.json
+++ b/tests/fixtures/lint/variables-and-bare.lint.json
@@ -29 +29 @@
-      "message": "$or requires a non-empty array.",
+      "message": "$or expects a non-empty array, got array.",
@@ -239 +239 @@
```

Truncated: 2 further diff lines; see PR7.

### `tests/fixtures/optimizer/bare-filter.golden.json`

```diff
diff --git a/tests/fixtures/optimizer/bare-filter.golden.json b/tests/fixtures/optimizer/bare-filter.golden.json
index 071210a..13180b4 100644
--- a/tests/fixtures/optimizer/bare-filter.golden.json
+++ b/tests/fixtures/optimizer/bare-filter.golden.json
@@ -3 +3,2 @@
-    "applied": [
+    "applied": [],
+    "findings": [
```

Truncated: 79 further diff lines; see PR7.

### `tests/fixtures/optimizer/bare-pipeline.golden.json`

```diff
diff --git a/tests/fixtures/optimizer/bare-pipeline.golden.json b/tests/fixtures/optimizer/bare-pipeline.golden.json
index 55d5ea0..c0f211e 100644
--- a/tests/fixtures/optimizer/bare-pipeline.golden.json
+++ b/tests/fixtures/optimizer/bare-pipeline.golden.json
@@ -45,10 +45,2 @@
-        "rationale": "$lookup from collection probes stores.storeId once per input document; without this index each probe is a collection scan.",
-        "shell": "db.stores.createIndex({ storeId: 1 })"
-      },
```

Truncated: 23 further diff lines; see PR7.

### `tests/fixtures/optimizer/command-find.golden.json`

```diff
diff --git a/tests/fixtures/optimizer/command-find.golden.json b/tests/fixtures/optimizer/command-find.golden.json
index 3c6df18..01ad2af 100644
--- a/tests/fixtures/optimizer/command-find.golden.json
+++ b/tests/fixtures/optimizer/command-find.golden.json
@@ -7 +7 @@
-        "column": 17,
+        "column": 34,
@@ -33 +33 @@
```

Truncated: 17 further diff lines; see PR7.

### `tests/fixtures/optimizer/mongosh-examples.golden.json`

```diff
diff --git a/tests/fixtures/optimizer/mongosh-examples.golden.json b/tests/fixtures/optimizer/mongosh-examples.golden.json
index 46d41f8..25fd775 100644
--- a/tests/fixtures/optimizer/mongosh-examples.golden.json
+++ b/tests/fixtures/optimizer/mongosh-examples.golden.json
@@ -6,6 +6 @@
-        "message": "$or of equalities on one field (region) is an $in: one index scan with point bounds instead of a subplan per branch, and sort-compatible.",
-        "pass": "P4"
-      },
```

Truncated: 96 further diff lines; see PR7.

### `tests/fixtures/optimizer/mongosh-orders.golden.json`

```diff
diff --git a/tests/fixtures/optimizer/mongosh-orders.golden.json b/tests/fixtures/optimizer/mongosh-orders.golden.json
index fba781c..e5f5952 100644
--- a/tests/fixtures/optimizer/mongosh-orders.golden.json
+++ b/tests/fixtures/optimizer/mongosh-orders.golden.json
@@ -22 +22 @@
-        "shell": "db.orders.createIndex({ status: 1 })"
+        "shell": "db.getCollection(\"orders\").createIndex({ status: 1 })"
@@ -70 +70 @@
```

Truncated: 5 further diff lines; see PR7.

### `tests/fixtures/optimizer/mongosh-rules.golden.json`

```diff
diff --git a/tests/fixtures/optimizer/mongosh-rules.golden.json b/tests/fixtures/optimizer/mongosh-rules.golden.json
index fc04413..90e5f31 100644
--- a/tests/fixtures/optimizer/mongosh-rules.golden.json
+++ b/tests/fixtures/optimizer/mongosh-rules.golden.json
@@ -6 +6 @@
-        "message": "$or of equalities on one field (a) is an $in: one index scan with point bounds instead of a subplan per branch, and sort-compatible.",
+        "message": "$or of equalities on one field (a) is an $in: one index scan with point bounds instead of a subplan per branch. Sort support depends on the operand count and index.",
@@ -9,10 +8,0 @@
```

Truncated: 298 further diff lines; see PR7.

### `tests/fixtures/optimizer/profiler-update.golden.json`

```diff
diff --git a/tests/fixtures/optimizer/profiler-update.golden.json b/tests/fixtures/optimizer/profiler-update.golden.json
index 64e2077..b57e2c3 100644
--- a/tests/fixtures/optimizer/profiler-update.golden.json
+++ b/tests/fixtures/optimizer/profiler-update.golden.json
@@ -7 +7 @@
-        "column": 72,
+        "column": 89,
@@ -25 +25 @@
```

Truncated: 23 further diff lines; see PR7.

### `tests/fixtures/optimizer/slowlog-find.golden.json`

```diff
diff --git a/tests/fixtures/optimizer/slowlog-find.golden.json b/tests/fixtures/optimizer/slowlog-find.golden.json
index f842e04..d148f95 100644
--- a/tests/fixtures/optimizer/slowlog-find.golden.json
+++ b/tests/fixtures/optimizer/slowlog-find.golden.json
@@ -52 +52 @@
-        "column": 45,
+        "column": 62,
@@ -54 +54 @@
```

Truncated: 23 further diff lines; see PR7.

### `tests/fixtures/optimizer/slowlog-multi.golden.json`

```diff
diff --git a/tests/fixtures/optimizer/slowlog-multi.golden.json b/tests/fixtures/optimizer/slowlog-multi.golden.json
index 8974436..a8dfde6 100644
--- a/tests/fixtures/optimizer/slowlog-multi.golden.json
+++ b/tests/fixtures/optimizer/slowlog-multi.golden.json
@@ -8,5 +7,0 @@
-      },
-      {
-        "code": "degenerate-range",
```

Truncated: 46 further diff lines; see PR7.

### `tests/test_cdo_hardening.py`

```diff
diff --git a/tests/test_cdo_hardening.py b/tests/test_cdo_hardening.py
index 118d348..e84ea46 100644
--- a/tests/test_cdo_hardening.py
+++ b/tests/test_cdo_hardening.py
@@ -25,4 +25,9 @@ def test_embed_non_json_body_is_embed_error(monkeypatch, caplog):
-    monkeypatch.setattr("urllib.request.urlopen", _urlopen_returning(b"<html>502</html>"))
-    with caplog.at_level(logging.WARNING, logger="mdbx.embed"), pytest.raises(embed.EmbedError):
-        embed.embed(["x"])
```

Truncated: 78 further diff lines; see PR7.

### `tests/test_chrome_autoupdate.py`

```diff
diff --git a/tests/test_chrome_autoupdate.py b/tests/test_chrome_autoupdate.py
index 9dc8dfd..3c48e00 100644
--- a/tests/test_chrome_autoupdate.py
+++ b/tests/test_chrome_autoupdate.py
@@ -40,0 +41 @@ def _fake_ext(src: Path) -> None:
+    (src / "manifest.json").write_text(json.dumps({"manifest_version": 3, "version": "0.3.0", "background": {"service_worker": "background.js"}, "action": {"default_popup": "popup.html"}}))
@@ -103 +104 @@ def test_run_update_builds_and_installs(tmp_path, monkeypatch):
-    monkeypatch.setattr(au, "build_from_clone", lambda cfg: src)
```

Truncated: 111 further diff lines; see PR7.

### `tests/test_core.py`

```diff
diff --git a/tests/test_core.py b/tests/test_core.py
index f1d7a39..1c5e8c1 100644
--- a/tests/test_core.py
+++ b/tests/test_core.py
@@ -0,0 +1 @@
+import json
@@ -34 +35 @@ def test_chunk_headings_and_size():
-    assert pieces and all(len(b) <= corpus.MAX_CHUNK_CHARS + 200 for _, _, b in pieces)
```

Truncated: 168 further diff lines; see PR7.

### `tests/test_core_preservation.py`

```diff
diff --git a/tests/test_core_preservation.py b/tests/test_core_preservation.py
new file mode 100644
index 0000000..1b3b1e6
--- /dev/null
+++ b/tests/test_core_preservation.py
@@ -0,0 +1,438 @@
+"""Synthetic corroboration only; no source changes and no live providers."""
+import logging
```

Truncated: 436 further diff lines; see PR7.

### `tests/test_corpus_autoupdate.py`

```diff
diff --git a/tests/test_corpus_autoupdate.py b/tests/test_corpus_autoupdate.py
index 810d2bd..804581f 100644
--- a/tests/test_corpus_autoupdate.py
+++ b/tests/test_corpus_autoupdate.py
@@ -27 +27 @@ def run(cwd: Path, *args: str) -> str:
-    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout
+    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True, timeout=30).stdout
@@ -34,0 +35 @@ def make_origin(tmp: Path) -> Path:
```

Truncated: 79 further diff lines; see PR7.

### `tests/test_embed_backend.py`

```diff
diff --git a/tests/test_embed_backend.py b/tests/test_embed_backend.py
index a5bb836..c2abed1 100644
--- a/tests/test_embed_backend.py
+++ b/tests/test_embed_backend.py
@@ -9,0 +10,5 @@ from mdbx import embed, embed_onnx
[REDACTED](autouse=True)
+def _default_model(monkeypatch):
+    monkeypatch.setenv('MDBX_EMBED_MODEL',embed.DEFAULT_MODEL)
```

Truncated: 32 further diff lines; see PR7.

### `tests/test_generator_preservation.py`

```diff
diff --git a/tests/test_generator_preservation.py b/tests/test_generator_preservation.py
new file mode 100644
index 0000000..31e96c6
--- /dev/null
+++ b/tests/test_generator_preservation.py
@@ -0,0 +1,103 @@
+import importlib.util
+import sys
```

Truncated: 101 further diff lines; see PR7.

### `tests/test_iteration2_python.py`

```diff
diff --git a/tests/test_iteration2_python.py b/tests/test_iteration2_python.py
new file mode 100644
index 0000000..8ef7ee6
--- /dev/null
+++ b/tests/test_iteration2_python.py
@@ -0,0 +1,165 @@
+"""Synthetic gate1 regression contracts; no corpus, model, or service calls."""
+import json
```

Truncated: 163 further diff lines; see PR7.

### `tests/test_iteration2_scripts.py`

```diff
diff --git a/tests/test_iteration2_scripts.py b/tests/test_iteration2_scripts.py
new file mode 100644
index 0000000..9fc2379
--- /dev/null
+++ b/tests/test_iteration2_scripts.py
@@ -0,0 +1,299 @@
+"""Synthetic operational regressions for corroborated gate1 failures."""
+import ctypes
```

Truncated: 297 further diff lines; see PR7.

### `tests/test_js_lint_parity.py`

```diff
diff --git a/tests/test_js_lint_parity.py b/tests/test_js_lint_parity.py
index b7adf82..ca9f712 100644
--- a/tests/test_js_lint_parity.py
+++ b/tests/test_js_lint_parity.py
@@ -43 +43,3 @@ def _inputs() -> list[str]:
-        for src in sorted(fixtures.glob("*.txt")):
+        sources = sorted(fixtures.glob("*.txt"))
+        assert sources, f"missing or empty fixture directory: {fixtures}"
```

Truncated: 88 further diff lines; see PR7.

### `tests/test_js_parity.py`

```diff
diff --git a/tests/test_js_parity.py b/tests/test_js_parity.py
index b203210..54907e1 100644
--- a/tests/test_js_parity.py
+++ b/tests/test_js_parity.py
@@ -24 +24,3 @@ def _inputs() -> list[str]:
-    for src in sorted(FIX.glob("*.txt")):
+    sources = sorted(FIX.glob("*.txt"))
+    assert sources, f"missing or empty fixture directory: {FIX}"
```

Truncated: 35 further diff lines; see PR7.

### `tests/test_lint_preservation.py`

```diff
diff --git a/tests/test_lint_preservation.py b/tests/test_lint_preservation.py
new file mode 100644
index 0000000..6c2ef41
--- /dev/null
+++ b/tests/test_lint_preservation.py
@@ -0,0 +1,30 @@
+"""Preserve tolerant shell/header parsing while validating structured query input."""
+import pytest
```

Truncated: 28 further diff lines; see PR7.

### `tests/test_lsp_e2e.py`

```diff
diff --git a/tests/test_lsp_e2e.py b/tests/test_lsp_e2e.py
index fd77bc7..f3a3951 100644
--- a/tests/test_lsp_e2e.py
+++ b/tests/test_lsp_e2e.py
@@ -2,0 +3,3 @@ import json
+import os
+import queue
+import re
```

Truncated: 203 further diff lines; see PR7.

### `tests/test_maintenance.py`

```diff
diff --git a/tests/test_maintenance.py b/tests/test_maintenance.py
new file mode 100644
index 0000000..cdefbcd
--- /dev/null
+++ b/tests/test_maintenance.py
@@ -0,0 +1,193 @@
+"""Adversarial, synthetic regression cases for maintenance findings."""
+from contextlib import closing
```

Truncated: 191 further diff lines; see PR7.

### `tests/test_mcp.py`

```diff
diff --git a/tests/test_mcp.py b/tests/test_mcp.py
index c0d4b3c..f42eac3 100644
--- a/tests/test_mcp.py
+++ b/tests/test_mcp.py
@@ -19,2 +19,4 @@ def env(tmp_path, monkeypatch):
-    index.build_keyword(con, root)
-    con.close()
+    try:
```

Truncated: 94 further diff lines; see PR7.

### `tests/test_mql.py`

```diff
diff --git a/tests/test_mql.py b/tests/test_mql.py
index f8bc5bb..bdd4107 100644
--- a/tests/test_mql.py
+++ b/tests/test_mql.py
@@ -129,0 +130,270 @@ def test_word_at():
+
+
[REDACTED]("source", ["[1 2]", "{a:1 b:2}", "f(1 2)", "{,a:1}", "f(,1)", "@\n{x:1}"])
```

Truncated: 267 further diff lines; see PR7.

### `tests/test_normalize.py`

```diff
diff --git a/tests/test_normalize.py b/tests/test_normalize.py
index 34d1e58..b193d26 100644
--- a/tests/test_normalize.py
+++ b/tests/test_normalize.py
@@ -28 +28 @@ def test_slow_log_line_find():
-    assert q.text.startswith('db.orders.find({"customerId":4711')
+    assert q.text.startswith('db.getCollection("orders").find({"customerId":4711')
@@ -48 +48 @@ def test_profiler_write_entry():
```

Truncated: 110 further diff lines; see PR7.

### `tests/test_optimize.py`

```diff
diff --git a/tests/test_optimize.py b/tests/test_optimize.py
index 10cba38..2fdcfd1 100644
--- a/tests/test_optimize.py
+++ b/tests/test_optimize.py
@@ -54,2 +54,4 @@ def test_degenerate_range():
-    rep = optimize("db.c.find({ t: { $gte: 5, $lte: 5 } })")
-    assert rep.text == "db.c.find({ t: 5 })"
+    source = "db.c.find({ t: { $gte: 5, $lte: 5 } })"
```

Truncated: 168 further diff lines; see PR7.

### `tests/test_providers.py`

```diff
diff --git a/tests/test_providers.py b/tests/test_providers.py
index 5518733..516813c 100644
--- a/tests/test_providers.py
+++ b/tests/test_providers.py
@@ -26 +26 @@ def test_build_context_numbers_and_caps():
-    assert text.startswith("[1] skill-1 · H1 (skills/s1/SKILL.md:11)")
+    assert json.loads(text.splitlines()[0])["citation"] == 1
@@ -28 +28 @@ def test_build_context_numbers_and_caps():
```

Truncated: 81 further diff lines; see PR7.

### `tests/test_recipes.py`

```diff
diff --git a/tests/test_recipes.py b/tests/test_recipes.py
index ec06b33..009fd05 100644
--- a/tests/test_recipes.py
+++ b/tests/test_recipes.py
@@ -25 +25 @@ def root(tmp_path, monkeypatch):
-        RECIPE.replace("shard-a-collection", "atlas-private-link").replace("Shard a collection", "Add Atlas Private Link")
+        RECIPE.replace("shard-a-collection", "atlas-private-link").replace("Shard a collection", "Add Atlas Private Link").replace('sh.shardCollection("mydb.orders", { customerId: "hashed" })', 'atlas networking privateLink create')
@@ -49,0 +50,2 @@ def test_recipes_are_searchable_by_kind(root, tmp_path):
```

Truncated: 37 further diff lines; see PR7.

### `tests/test_test_isolation.py`

```diff
diff --git a/tests/test_test_isolation.py b/tests/test_test_isolation.py
new file mode 100644
index 0000000..9c6e918
--- /dev/null
+++ b/tests/test_test_isolation.py
@@ -0,0 +1,198 @@
+"""Synthetic regressions for preimport state, fixture Git, and the CI report contract."""
+from __future__ import annotations
```

Truncated: 196 further diff lines; see PR7.

### `tests/test_tooling_integrity.py`

```diff
diff --git a/tests/test_tooling_integrity.py b/tests/test_tooling_integrity.py
new file mode 100644
index 0000000..49ebbd6
--- /dev/null
+++ b/tests/test_tooling_integrity.py
@@ -0,0 +1,183 @@
+"""Adversarial preservation and privacy checks use only owned synthetic trees."""
+import importlib.util
```

Truncated: 181 further diff lines; see PR7.

### `tests/test_tooling_regressions.py`

```diff
diff --git a/tests/test_tooling_regressions.py b/tests/test_tooling_regressions.py
new file mode 100644
index 0000000..8b35d19
--- /dev/null
+++ b/tests/test_tooling_regressions.py
@@ -0,0 +1,215 @@
+"""Synthetic regression fixtures for the maintenance scripts. No live sources or services."""
+from __future__ import annotations
```

Truncated: 213 further diff lines; see PR7.

### `tests/test_tui.py`

```diff
diff --git a/tests/test_tui.py b/tests/test_tui.py
index ef9c4b2..8902d44 100644
--- a/tests/test_tui.py
+++ b/tests/test_tui.py
@@ -15,2 +15,4 @@ async def test_tui_keyword_search(tmp_path):
-    index.build_keyword(con, make_corpus(tmp_path))
-    con.close()
+    try:
```

Truncated: 132 further diff lines; see PR7.

### `tests/test_unicode61.py`

```diff
diff --git a/tests/test_unicode61.py b/tests/test_unicode61.py
new file mode 100644
index 0000000..49d4450
--- /dev/null
+++ b/tests/test_unicode61.py
@@ -0,0 +1,113 @@
+"""Differential Unicode61 tokenization and query ranking against in-memory SQLite."""
+import json
```

Truncated: 111 further diff lines; see PR7.

### `tests/test_web_search.py`

```diff
diff --git a/tests/test_web_search.py b/tests/test_web_search.py
index 8d1489c..487266e 100644
--- a/tests/test_web_search.py
+++ b/tests/test_web_search.py
@@ -25 +25 @@ def _git(cwd: Path, *args: str) -> None:
-    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)
+    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, timeout=10)
@@ -78,16 +78,16 @@ def test_vectors_roundtrip_int8(tmp_path):
```

Truncated: 35 further diff lines; see PR7.

## 6. Blind re-audit result

N/A for a non-clean exit. Gate2 collection is pending; six owner-retained Medium
defects already prohibit CLEAN. The frozen gate1 evidence remains129/129 unique
files with a separate current-generator report, all15 substantive pass rows and
completed turns. Gate2 has145 targets. Partial raw events and receipts are preserved;
a Stop-hook footer alone is not substantive diagnostic evidence. No cross-model
review was requested or claimed. No third blind gate may be started.

## 7. Recommendations

N/A: --suggest was not requested. Explicit migration/fixture scope blockers and
maintainer policy choices are recorded as limits, not invented feature requests.

## 8. Implemented features

N/A: --implement-features was not requested. Repairs enforce existing contracts.

## 9. Summary

2 iterations of5 ·15 per-file passes plus repo M3/T2/T3/cross-file M2/T4 · standard
profile · final C/H/M/L pending final collection; owner retains0/0/6/unresolved Low
rows before gate2 · Verify: repair checkpoint PASS, final CI pending · Status:
BLIND-AUDIT-DISSENT (provisional retained-defect status; never CLEAN).

## 10. Snapshot and rollback

Do not run rollback against active work. The external receipt retains exact snapshot
paths, before/after source hashes and all original/partial reports. Iteration2 used
pre-write snapshots for all129 existing maintained files plus four authorized
expectations, and atomic run stubs. The following literal commands restore selected
iteration2 originals and remove each source file created in iteration2. The snapshot
is local audit evidence, not distributed with the package. Git history preserves
docs and iteration1 rollback; reverting a delivered change requires its own review.

```sh
MDBX_ITER2_SNAPSHOT="$HOME/.claude/skill-consolidation/backups/mdbx-cdo-20261112T100000Z.iter2"
cp "$MDBX_ITER2_SNAPSHOT/.editorconfig" ".editorconfig"
cp "$MDBX_ITER2_SNAPSHOT/.env.example" ".env.example"
cp "$MDBX_ITER2_SNAPSHOT/.gitattributes" ".gitattributes"
cp "$MDBX_ITER2_SNAPSHOT/.github/CODEOWNERS" ".github/CODEOWNERS"
cp "$MDBX_ITER2_SNAPSHOT/.github/dependabot.yml" ".github/dependabot.yml"
cp "$MDBX_ITER2_SNAPSHOT/.github/workflows/ci.yml" ".github/workflows/ci.yml"
cp "$MDBX_ITER2_SNAPSHOT/.gitignore" ".gitignore"
cp "$MDBX_ITER2_SNAPSHOT/.mcp.json" ".mcp.json"
cp "$MDBX_ITER2_SNAPSHOT/.node-version" ".node-version"
cp "$MDBX_ITER2_SNAPSHOT/.vscode/extensions.json" ".vscode/extensions.json"
cp "$MDBX_ITER2_SNAPSHOT/.vscode/launch.json" ".vscode/launch.json"
cp "$MDBX_ITER2_SNAPSHOT/.vscode/mcp.json" ".vscode/mcp.json"
cp "$MDBX_ITER2_SNAPSHOT/.vscode/settings.json" ".vscode/settings.json"
cp "$MDBX_ITER2_SNAPSHOT/docs/archive/.gitkeep" "docs/archive/.gitkeep"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/app.css" "editors/chrome/app.css"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/app.html" "editors/chrome/app.html"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/app.js" "editors/chrome/app.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/background.js" "editors/chrome/background.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/lib/analyze.js" "editors/chrome/lib/analyze.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/lib/autoupdate.js" "editors/chrome/lib/autoupdate.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/lib/capture.js" "editors/chrome/lib/capture.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/lib/docs.js" "editors/chrome/lib/docs.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/lib/normalize.js" "editors/chrome/lib/normalize.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/lib/operators.js" "editors/chrome/lib/operators.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/lib/optimize.js" "editors/chrome/lib/optimize.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/lib/parser.js" "editors/chrome/lib/parser.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/lib/report.js" "editors/chrome/lib/report.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/lib/store.js" "editors/chrome/lib/store.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/lib/textsearch.js" "editors/chrome/lib/textsearch.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/lib/ui.js" "editors/chrome/lib/ui.js"
rm -- "editors/chrome/lib/unicode61.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/manifest.json" "editors/chrome/manifest.json"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/package.json" "editors/chrome/package.json"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/popup.css" "editors/chrome/popup.css"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/popup.html" "editors/chrome/popup.html"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/popup.js" "editors/chrome/popup.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/autoupdate.test.mjs" "editors/chrome/test/autoupdate.test.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/batch.mjs" "editors/chrome/test/batch.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/browser-context.mjs" "editors/chrome/test/browser-context.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/browser-context.test.mjs" "editors/chrome/test/browser-context.test.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/debug-app.mjs" "editors/chrome/test/debug-app.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/dom-fixture.mjs" "editors/chrome/test/dom-fixture.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/e2e.mjs" "editors/chrome/test/e2e.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/integrity.test.mjs" "editors/chrome/test/integrity.test.mjs"
rm -- "editors/chrome/test/language-boundaries.test.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/lint-batch.mjs" "editors/chrome/test/lint-batch.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/lint-parity.test.mjs" "editors/chrome/test/lint-parity.test.mjs"
rm -- "editors/chrome/test/normalization-boundaries.test.mjs"
rm -- "editors/chrome/test/optimizer-boundaries.test.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/page-races.test.mjs" "editors/chrome/test/page-races.test.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/parity.test.mjs" "editors/chrome/test/parity.test.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/rendering.test.mjs" "editors/chrome/test/rendering.test.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/run-tests.mjs" "editors/chrome/test/run-tests.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/search-batch.mjs" "editors/chrome/test/search-batch.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/search-parity.test.mjs" "editors/chrome/test/search-parity.test.mjs"
rm -- "editors/chrome/test/search-rendering-boundaries.test.mjs"
rm -- "editors/chrome/test/ui-boundaries.test.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/chrome/test/ui.test.mjs" "editors/chrome/test/ui.test.mjs"
cp "$MDBX_ITER2_SNAPSHOT/editors/helix-languages.toml" "editors/helix-languages.toml"
cp "$MDBX_ITER2_SNAPSHOT/editors/neovim.lua" "editors/neovim.lua"
cp "$MDBX_ITER2_SNAPSHOT/editors/vscode/.vscodeignore" "editors/vscode/.vscodeignore"
cp "$MDBX_ITER2_SNAPSHOT/editors/vscode/LICENSE" "editors/vscode/LICENSE"
cp "$MDBX_ITER2_SNAPSHOT/editors/vscode/extension.js" "editors/vscode/extension.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/vscode/language-configuration.json" "editors/vscode/language-configuration.json"
cp "$MDBX_ITER2_SNAPSHOT/editors/vscode/package.json" "editors/vscode/package.json"
cp "$MDBX_ITER2_SNAPSHOT/editors/vscode/server-path.js" "editors/vscode/server-path.js"
cp "$MDBX_ITER2_SNAPSHOT/editors/vscode/syntaxes/mql.tmLanguage.json" "editors/vscode/syntaxes/mql.tmLanguage.json"
cp "$MDBX_ITER2_SNAPSHOT/editors/vscode/test/server-path.test.js" "editors/vscode/test/server-path.test.js"
cp "$MDBX_ITER2_SNAPSHOT/examples/orders.mql" "examples/orders.mql"
cp "$MDBX_ITER2_SNAPSHOT/examples/slow-queries.mql" "examples/slow-queries.mql"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/__init__.py" "mdbx/__init__.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/cli.py" "mdbx/cli.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/corpus.py" "mdbx/corpus.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/embed.py" "mdbx/embed.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/embed_onnx.py" "mdbx/embed_onnx.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/index.py" "mdbx/index.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/mcp_server.py" "mdbx/mcp_server.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/mql/__init__.py" "mdbx/mql/__init__.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/mql/analyze.py" "mdbx/mql/analyze.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/mql/features.py" "mdbx/mql/features.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/mql/normalize.py" "mdbx/mql/normalize.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/mql/operators.py" "mdbx/mql/operators.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/mql/optimize.py" "mdbx/mql/optimize.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/mql/parser.py" "mdbx/mql/parser.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/mql/server.py" "mdbx/mql/server.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/providers.py" "mdbx/providers.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/recipes.py" "mdbx/recipes.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/safety.py" "mdbx/safety.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/search.py" "mdbx/search.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/tui.py" "mdbx/tui.py"
rm -- "mdbx/unicode61.py"
cp "$MDBX_ITER2_SNAPSHOT/mdbx/webexport.py" "mdbx/webexport.py"
cp "$MDBX_ITER2_SNAPSHOT/pyproject.toml" "pyproject.toml"
cp "$MDBX_ITER2_SNAPSHOT/scripts/check_chrome_doc_links.py" "scripts/check_chrome_doc_links.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/check_doc_indexes.py" "scripts/check_doc_indexes.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/chrome_extension_autoupdate.py" "scripts/chrome_extension_autoupdate.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/corpus_autoupdate.py" "scripts/corpus_autoupdate.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/gen_chrome_operators.py" "scripts/gen_chrome_operators.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/gen_file_index.py" "scripts/gen_file_index.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/gen_lint_golden.py" "scripts/gen_lint_golden.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/gen_optimizer_golden.py" "scripts/gen_optimizer_golden.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/gen_recipes_index.py" "scripts/gen_recipes_index.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/gen_search_golden.py" "scripts/gen_search_golden.py"
rm -- "scripts/gen_unicode61.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/glean_cli_helper.py" "scripts/glean_cli_helper.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/install.sh" "scripts/install.sh"
cp "$MDBX_ITER2_SNAPSHOT/scripts/maintenance_safety.py" "scripts/maintenance_safety.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/make_chrome_icons.py" "scripts/make_chrome_icons.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/offline_test.py" "scripts/offline_test.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/package_chrome_extension.py" "scripts/package_chrome_extension.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/redact_corpus.py" "scripts/redact_corpus.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/rotate_workflow_logs.py" "scripts/rotate_workflow_logs.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/sweep_customers.py" "scripts/sweep_customers.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/sync_corpus.sh" "scripts/sync_corpus.sh"
cp "$MDBX_ITER2_SNAPSHOT/scripts/sync_corpus_sources.py" "scripts/sync_corpus_sources.py"
rm -- "scripts/test_isolation.py"
cp "$MDBX_ITER2_SNAPSHOT/scripts/watch_and_index.sh" "scripts/watch_and_index.sh"
cp "$MDBX_ITER2_SNAPSHOT/tests/__init__.py" "tests/__init__.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/conftest.py" "tests/conftest.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_cdo_hardening.py" "tests/test_cdo_hardening.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_chrome_autoupdate.py" "tests/test_chrome_autoupdate.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_core.py" "tests/test_core.py"
rm -- "tests/test_core_preservation.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_corpus_autoupdate.py" "tests/test_corpus_autoupdate.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_embed_backend.py" "tests/test_embed_backend.py"
rm -- "tests/test_generator_preservation.py"
rm -- "tests/test_iteration2_python.py"
rm -- "tests/test_iteration2_scripts.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_js_lint_parity.py" "tests/test_js_lint_parity.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_js_parity.py" "tests/test_js_parity.py"
rm -- "tests/test_lint_preservation.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_lsp_e2e.py" "tests/test_lsp_e2e.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_maintenance.py" "tests/test_maintenance.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_mcp.py" "tests/test_mcp.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_mql.py" "tests/test_mql.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_normalize.py" "tests/test_normalize.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_optimize.py" "tests/test_optimize.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_providers.py" "tests/test_providers.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_recipes.py" "tests/test_recipes.py"
rm -- "tests/test_test_isolation.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_tooling_integrity.py" "tests/test_tooling_integrity.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_tooling_regressions.py" "tests/test_tooling_regressions.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_tui.py" "tests/test_tui.py"
rm -- "tests/test_unicode61.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/test_web_search.py" "tests/test_web_search.py"
cp "$MDBX_ITER2_SNAPSHOT/tests/fixtures/optimizer/bare-filter.golden.json" "tests/fixtures/optimizer/bare-filter.golden.json"
cp "$MDBX_ITER2_SNAPSHOT/tests/fixtures/optimizer/bare-pipeline.golden.json" "tests/fixtures/optimizer/bare-pipeline.golden.json"
cp "$MDBX_ITER2_SNAPSHOT/tests/fixtures/optimizer/mongosh-examples.golden.json" "tests/fixtures/optimizer/mongosh-examples.golden.json"
cp "$MDBX_ITER2_SNAPSHOT/tests/fixtures/optimizer/mongosh-rules.golden.json" "tests/fixtures/optimizer/mongosh-rules.golden.json"
```

Canonical convergence measurements are per file, never one concatenated repository
artifact. Iteration1 has112 exact measurements; iteration2 has145. Local checker
outputs142 CLEAN and3 CONTINUE use raw277 before-candidates and six retained owner
defects; they are not an overall CLEAN verdict. Exact commands, stdout, source hashes
and per-file ratios are preserved in convergence-iteration2.json. No distance was
estimated. Gate2 may add corroborated findings and does not reset either budget.

| File | Exact edit-distance ratio | Exact checker verdict |
|---|---:|---|
| `.editorconfig` | 0.0000 | CLEAN |
| `.env.example` | 0.2639 | CLEAN |
| `.gitattributes` | 0.0000 | CLEAN |
| `.github/CODEOWNERS` | 0.0000 | CLEAN |
| `.github/dependabot.yml` | 0.0000 | CLEAN |
| `.github/workflows/ci.yml` | 0.4366 | CLEAN |
| `.gitignore` | 0.0888 | CLEAN |
| `.mcp.json` | 0.0000 | CLEAN |
| `.node-version` | 0.0000 | CLEAN |
| `.vscode/extensions.json` | 0.0000 | CLEAN |
| `.vscode/launch.json` | 0.0000 | CLEAN |
| `.vscode/mcp.json` | 0.0000 | CLEAN |
| `.vscode/settings.json` | 0.0000 | CLEAN |
| `docs/archive/.gitkeep` | 0.0000 | CLEAN |
| `editors/chrome/app.css` | 0.0011 | CLEAN |
| `editors/chrome/app.html` | 0.0102 | CLEAN |
| `editors/chrome/app.js` | 0.0607 | CLEAN |
| `editors/chrome/background.js` | 0.1421 | CLEAN |
| `editors/chrome/lib/analyze.js` | 0.0357 | CLEAN |
| `editors/chrome/lib/autoupdate.js` | 0.1637 | CLEAN |
| `editors/chrome/lib/capture.js` | 0.0294 | CLEAN |
| `editors/chrome/lib/docs.js` | 0.0000 | CLEAN |
| `editors/chrome/lib/normalize.js` | 0.0966 | CLEAN |
| `editors/chrome/lib/operators.js` | 0.0000 | CLEAN |
| `editors/chrome/lib/optimize.js` | 0.0724 | CONTINUE |
| `editors/chrome/lib/parser.js` | 0.0669 | CLEAN |
| `editors/chrome/lib/report.js` | 0.0002 | CLEAN |
| `editors/chrome/lib/store.js` | 0.2299 | CLEAN |
| `editors/chrome/lib/textsearch.js` | 0.0954 | CLEAN |
| `editors/chrome/lib/ui.js` | 0.0469 | CLEAN |
| `editors/chrome/lib/unicode61.js` | 1.0000 | CLEAN |
| `editors/chrome/manifest.json` | 0.0000 | CLEAN |
| `editors/chrome/package.json` | 0.0000 | CLEAN |
| `editors/chrome/popup.css` | 0.0000 | CLEAN |
| `editors/chrome/popup.html` | 0.0705 | CLEAN |
| `editors/chrome/popup.js` | 0.0781 | CLEAN |
| `editors/chrome/test/autoupdate.test.mjs` | 0.0144 | CLEAN |
| `editors/chrome/test/batch.mjs` | 0.0000 | CLEAN |
| `editors/chrome/test/browser-context.mjs` | 0.1125 | CLEAN |
| `editors/chrome/test/browser-context.test.mjs` | 0.4478 | CLEAN |
| `editors/chrome/test/debug-app.mjs` | 0.3902 | CLEAN |
| `editors/chrome/test/dom-fixture.mjs` | 0.0200 | CLEAN |
| `editors/chrome/test/e2e.mjs` | 0.0360 | CLEAN |
| `editors/chrome/test/integrity.test.mjs` | 0.0366 | CLEAN |
| `editors/chrome/test/language-boundaries.test.mjs` | 1.0000 | CLEAN |
| `editors/chrome/test/lint-batch.mjs` | 0.0000 | CLEAN |
| `editors/chrome/test/lint-parity.test.mjs` | 0.0084 | CLEAN |
| `editors/chrome/test/normalization-boundaries.test.mjs` | 1.0000 | CLEAN |
| `editors/chrome/test/optimizer-boundaries.test.mjs` | 1.0000 | CLEAN |
| `editors/chrome/test/page-races.test.mjs` | 0.2594 | CLEAN |
| `editors/chrome/test/parity.test.mjs` | 0.0342 | CLEAN |
| `editors/chrome/test/rendering.test.mjs` | 0.1200 | CLEAN |
| `editors/chrome/test/run-tests.mjs` | 0.0000 | CLEAN |
| `editors/chrome/test/search-batch.mjs` | 0.0721 | CLEAN |
| `editors/chrome/test/search-parity.test.mjs` | 0.1181 | CLEAN |
| `editors/chrome/test/search-rendering-boundaries.test.mjs` | 1.0000 | CLEAN |
| `editors/chrome/test/ui-boundaries.test.mjs` | 1.0000 | CLEAN |
| `editors/chrome/test/ui.test.mjs` | 0.0243 | CLEAN |
| `editors/helix-languages.toml` | 0.0000 | CLEAN |
| `editors/neovim.lua` | 0.0000 | CLEAN |
| `editors/vscode/.vscodeignore` | 0.0000 | CLEAN |
| `editors/vscode/LICENSE` | 0.0000 | CLEAN |
| `editors/vscode/extension.js` | 0.0698 | CLEAN |
| `editors/vscode/language-configuration.json` | 0.4000 | CLEAN |
| `editors/vscode/package.json` | 0.0000 | CLEAN |
| `editors/vscode/server-path.js` | 0.1878 | CLEAN |
| `editors/vscode/syntaxes/mql.tmLanguage.json` | 0.1633 | CLEAN |
| `editors/vscode/test/server-path.test.js` | 0.4822 | CLEAN |
| `examples/orders.mql` | 0.0000 | CLEAN |
| `examples/slow-queries.mql` | 0.0000 | CLEAN |
| `mdbx/__init__.py` | 0.0000 | CLEAN |
| `mdbx/cli.py` | 0.0161 | CLEAN |
| `mdbx/corpus.py` | 0.1089 | CONTINUE |
| `mdbx/embed.py` | 0.0000 | CLEAN |
| `mdbx/embed_onnx.py` | 0.0575 | CLEAN |
| `mdbx/index.py` | 0.4690 | CLEAN |
| `mdbx/mcp_server.py` | 0.0495 | CLEAN |
| `mdbx/mql/__init__.py` | 0.0000 | CLEAN |
| `mdbx/mql/analyze.py` | 0.0429 | CLEAN |
| `mdbx/mql/features.py` | 0.1550 | CLEAN |
| `mdbx/mql/normalize.py` | 0.0726 | CLEAN |
| `mdbx/mql/operators.py` | 0.0034 | CLEAN |
| `mdbx/mql/optimize.py` | 0.0922 | CONTINUE |
| `mdbx/mql/parser.py` | 0.0461 | CLEAN |
| `mdbx/mql/server.py` | 0.1678 | CLEAN |
| `mdbx/providers.py` | 0.1006 | CLEAN |
| `mdbx/recipes.py` | 0.1716 | CLEAN |
| `mdbx/safety.py` | 0.8812 | CLEAN |
| `mdbx/search.py` | 0.4672 | CLEAN |
| `mdbx/tui.py` | 0.0713 | CLEAN |
| `mdbx/unicode61.py` | 1.0000 | CLEAN |
| `mdbx/webexport.py` | 0.2962 | CLEAN |
| `pyproject.toml` | 0.0000 | CLEAN |
| `scripts/check_chrome_doc_links.py` | 0.1269 | CLEAN |
| `scripts/check_doc_indexes.py` | 0.0000 | CLEAN |
| `scripts/chrome_extension_autoupdate.py` | 0.0555 | CLEAN |
| `scripts/corpus_autoupdate.py` | 0.0661 | CLEAN |
| `scripts/gen_chrome_operators.py` | 0.0042 | CLEAN |
| `scripts/gen_file_index.py` | 0.2114 | CLEAN |
| `scripts/gen_lint_golden.py` | 0.1768 | CLEAN |
| `scripts/gen_optimizer_golden.py` | 0.0000 | CLEAN |
| `scripts/gen_recipes_index.py` | 0.1039 | CLEAN |
| `scripts/gen_search_golden.py` | 0.2881 | CLEAN |
| `scripts/gen_unicode61.py` | 1.0000 | CLEAN |
| `scripts/glean_cli_helper.py` | 0.0000 | CLEAN |
| `scripts/install.sh` | 0.1647 | CLEAN |
| `scripts/maintenance_safety.py` | 0.5753 | CLEAN |
| `scripts/make_chrome_icons.py` | 0.0000 | CLEAN |
| `scripts/offline_test.py` | 0.3860 | CLEAN |
| `scripts/package_chrome_extension.py` | 0.2364 | CLEAN |
| `scripts/redact_corpus.py` | 0.3488 | CLEAN |
| `scripts/rotate_workflow_logs.py` | 0.3001 | CLEAN |
| `scripts/sweep_customers.py` | 0.1760 | CLEAN |
| `scripts/sync_corpus.sh` | 0.1909 | CLEAN |
| `scripts/sync_corpus_sources.py` | 0.2170 | CLEAN |
| `scripts/test_isolation.py` | 1.0000 | CLEAN |
| `scripts/watch_and_index.sh` | 0.3693 | CLEAN |
| `tests/__init__.py` | 0.0000 | CLEAN |
| `tests/conftest.py` | 0.7284 | CLEAN |
| `tests/test_cdo_hardening.py` | 0.3655 | CLEAN |
| `tests/test_chrome_autoupdate.py` | 0.0128 | CLEAN |
| `tests/test_core.py` | 0.1866 | CLEAN |
| `tests/test_core_preservation.py` | 1.0000 | CLEAN |
| `tests/test_corpus_autoupdate.py` | 0.0833 | CLEAN |
| `tests/test_embed_backend.py` | 0.1006 | CLEAN |
| `tests/test_generator_preservation.py` | 1.0000 | CLEAN |
| `tests/test_iteration2_python.py` | 1.0000 | CLEAN |
| `tests/test_iteration2_scripts.py` | 1.0000 | CLEAN |
| `tests/test_js_lint_parity.py` | 0.0408 | CLEAN |
| `tests/test_js_parity.py` | 0.2925 | CLEAN |
| `tests/test_lint_preservation.py` | 1.0000 | CLEAN |
| `tests/test_lsp_e2e.py` | 0.2007 | CLEAN |
| `tests/test_maintenance.py` | 0.3469 | CLEAN |
| `tests/test_mcp.py` | 0.0263 | CLEAN |
| `tests/test_mql.py` | 0.0168 | CLEAN |
| `tests/test_normalize.py` | 0.0286 | CLEAN |
| `tests/test_optimize.py` | 0.0361 | CLEAN |
| `tests/test_providers.py` | 0.0000 | CLEAN |
| `tests/test_recipes.py` | 0.1116 | CLEAN |
| `tests/test_test_isolation.py` | 1.0000 | CLEAN |
| `tests/test_tooling_integrity.py` | 0.1175 | CLEAN |
| `tests/test_tooling_regressions.py` | 0.0259 | CLEAN |
| `tests/test_tui.py` | 0.2427 | CLEAN |
| `tests/test_unicode61.py` | 1.0000 | CLEAN |
| `tests/test_web_search.py` | 0.1162 | CLEAN |

## 11. Index

index: static navigation refresh pending final documentation; semantic generation
paused. Existing semantic stores, frozen vectors and corpus bytes are preserved.
No post-commit embedding hook runs for task or synthetic fixture commits.

## 12. Memory and durable context

memory-central: prior maintenance conventions consulted; exact count of historic
consultations is not asserted. Stele decisions preserve serialized identities,
synthetic Git/model isolation, narrow expectation permission and deferred schema
advice. Existing tasks are reused; neither is completed before actual delivery.
No global memory or installed skill files were modified by this repository task.
The maintained wiki links this ledger, the bootstrap ledger and source inventory.
