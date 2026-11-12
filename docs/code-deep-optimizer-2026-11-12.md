# Code deep optimizer ledger — 2026-11-12

Final blind status: **BLIND-AUDIT-DISSENT**. Gate 2 is complete and drained.
Focused post-gate repairs and ordinary CI integration followed it. No third
blind gate or audit pool was started. Green tests and local per-file CLEAN
labels do not replace the global blind verdict.

## 1. Severity accounting and budgets
| Collection / phase | Critical | High | Medium | Low | Nit | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| Initial diagnostics / iteration 1 input | 75 | 69 | 211 | 12 | 0 | 112 maintained targets: 109 external plus 3 native; 2 extra reports excluded |
| Gate 1 / iteration 2 input | 16 | 29 | 232 | 10 | 0 | 129 unique targets; 277 original Medium+ rows |
| Gate 1 changed-generator continuation | 0 | 0 | 1 | 0 | 0 | current-hash duplicate publication report retained, not a new gate |
| Owner-retained before gate 2 | 0 | 0 | 6 | retained raw Low rows | 0 | four representation defects and paired schema-advice rows; not a blind verdict |
| Final blind gate 2 | 2 | 26 | 223 | 13 | 0 | 145 valid completed 15-pass reports; 251 raw Medium+ rows |

Counts are raw report rows, not independently unique defects. All original 277
gate-1 Medium+ rows were dispositioned before iteration 2. Lower-severity rows
remain retained, not silently fixed or waived. Partial raw events, exact hashes,
completed turns and the supplemental changed-generator counterexample remain
external evidence.

| Post-gate execution ledger | Rows | Real | Duplicate | Blocked |
|---|---:|---:|---:|---:|
| Core/tooling | 61 | 59 | 0 | 2 |
| MQL | 68 | 63 | 5 | 0 |
| Python interfaces/scripts | 76 | 76 | 0 | 0 |
| Editors | 47 | 46 | 1 | 0 |
| Total | 252 | 244 | 6 | 2 |

The 252nd execution row is ordinary upstream helper/caller candidate
UPSTREAM-CI-F1, supported by the synthetic public-dev-install failure. Core has
60 gate-2 rows plus this row. It is not an extra blind report. The original
244-real execution classification remains archived. Native adjudication
reclassifies gen_file_index.py#2 as Low/bootstrap consistency hygiene: independent
pair writes were real, but no prior atomic-pair contract supported Medium severity.
The supported static-index pair repair remains. Shared fix units,
duplicates and paired implementations must not inflate bug/reproduction counts.

The original cap remains 5 repair iterations and 2 blind gates. Iterations 1/2
preceded a96aee5409964dbf45cdef0b18b6708970a53280. Iteration 3 contains focused
post-gate repairs, publication preservation and ordinary integration. It does
not reset either budget. Allocation history is 2→4 gate-1 contexts and 8 gate-2
contexts after prior owners drained, with one admitted dispatcher, per-file
source hashes and an exclusive gate lock. Both blind slots are spent.

## 2. Findings and dispositions
The following representative table retains reviewed snapshot line references;
current lines may move. Full candidate-level source/caller corroboration and
repair receipts remain in the external ledgers. These historical rows do not
replace final verification or the separately inventoried additions.

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

Focused iteration-3 work strengthens vector/model/dimension identity, revisions
and caches; bounded/confined snapshots and source publication; parser/MQL parity;
editor request/lifecycle/capture identity; updater ownership and pending retry;
staged privacy-gated corpus generation; bounded scanner/preview work; and tests
that independently detect stale state and interrupted publication.

The two blocked post-gate rows are not the complete inherited-defect census.
Four distinct corpus representation defects remain blocked: the two historical
short-section line/breadcrumb issues, inline-backtick fence recognition and
unbounded oversized breadcrumbs. Production chunk_text and _merge_tiny remain
exact to 592db43 under KNOW-1855. No copied codec, monkeypatch or alternate
generator hides serialization drift.

Schema-dependent key/value/numeric-string advice keeps its prior behavior because
its correction changes two unapproved ordinary expected-output fixtures. The
production change is deferred globally, without fixture-specific bypasses.
Exactly four authorized optimizer expectation files changed before a96aee5.
Post-gate work changed none of the 49 ordinary expected-output fixtures; all
search/chunk/vector fixtures and lint expectations remain unchanged.
Cross-origin ancestry remains incomplete and the language-client major upgrade
from 9 to 11 is deferred.

The short Alpha/Zulu gen_search proposal was an invalid digest witness because
headings change the digest. The retained actual RED regression uses long,
identical continuations; an explicit assertion now proves that one digest spans
multiple headings. Its focused GREEN result does not validate the short witness. The original raw
report and rejected witness remain historical evidence.

## 3. Verify gates and ordinary evidence
All current tests/imports/probes use parent/child outbound and loopback denial,
preimport synthetic cached runtime/provider factories, scratch HOME/TMPDIR/
configuration/data/model/auth, and fixture Git with removed inherited selectors,
empty owned config/template/hooks and pre-commit inventory. Exact commands are
logged before execution. Actual task commits suppress only the hash-verified
paused semantic hook through a per-command filter; global hooks are unchanged.

The early 141-pass baseline had incomplete isolation. MDBx accounting found
4 Git vectors plus 1 distinct file embedding through 2 rows, 2 marks and 0 queue
rows. Those additions remain preserved without cleanup or re-embedding. Broader
batch effects are outside that exact count. Five native Node resolver tests were
not a Python run. There is no blanket no-effects claim.

Historical repair checkpoint: Python 487 passed/6 optional skipped, Chrome 249
and VS Code 10 passed. Interim integration included 624/1, a 68/1 focused repair,
then 666/2. Actual post-upstream source checks at 08708f0 recorded Python
668 passed/2 skipped in 27.07 seconds: unavailable real ONNX and Linux namespace
proof inapplicable on macOS. Ruff, compilation, shell syntax and all five search/
optimizer/lint/operator/Unicode freshness checks passed. Wheel 0.7.1, code-only
Chrome (27 members) and VSIX (325 files/467.11 KB) builds passed. Fresh Chrome
280 and VS Code 20 tests passed. The 64-output production serialization/AST proof
passed again as one test. The independent main-integration subset had also
passed 50/1 plus Ruff. Exact evidence is retained in final-local-checks.json;
none of these observations alone establishes final pushed-head CI or delivery.

Linux creates a privileged empty network namespace, then setpriv selects the
nonroot IDs, clears supplementary groups and capabilities, and sets NoNewPrivs
before env -i starts scratch execution. Nested runs require kernel evidence of
that same unprivileged empty namespace, including down loopback-only interfaces
and no delivery routes; environment flags are insufficient. Local mocked state/
command checks and maintained nesting tests pass on macOS. Actual inherited
Linux parent/Python/Node egress denial belongs to final Ubuntu CI.

**FINAL_VALIDATION:** Actual integrated source at08708f0:668 Python tests passed,2 skipped (real ONNX unavailable and Linux-only proof on macOS); Chrome280 and VS Code20 passed. Ruff, compilation, shell syntax, five generator freshness checks, wheel, code-only Chrome ZIP and VSIX builds passed. Exact commands/results and later CI-repair checks are retained in the external delivery receipt. The independent production scope proof passed64 synthetic outputs and exact selected source/AST checks.

**FINAL_CI:** [PR7 checks](https://github.com/mithudso/mdb-expertise-search/pull/7/checks) cover macOS and Ubuntu on Python3.11/3.12/3.13. First integrated run43312948550 exposed Linux inherited-guard self-recognition and nested-runner failures; its failed result is retained. Final pushed-head CI must pass before merge; actual run IDs/results are recorded in the delivery receipt.

Final evidence identifies actual source/check heads, exact commands, pass/skip/
warning counts, required CI jobs, static indexes and packages. Offline parity
and golden checks are regressions, not heldout model-quality or production
performance benchmarks. No real model, customer corpus indexing, service,
browser profile or provider benchmark is credited as synthetic verification.


### Required CI repair appendix

Run43312948550 exposed Linux inherited-isolation self-recognition failures.
Diagnostic run43314617512 proved only routeheader_ok failed: the successful IPv4
route read was exactly empty; all identity, capability, NoNewPrivs, down-loopback
and inert IPv6 predicates passed. Linux fib_route_seq_start returns NULL before
the header token when the main table is absent ([primary kernel source](https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/%2B/627b7865c062ff642c0000f3a4775f1a44b986a4/net/ipv4/fib_trie.c)).
The correction accepts exactly empty or valid-header/zero-row IPv4 output.
Missing, unreadable, whitespace, malformed and nonempty controls remain rejected.
The synthetic empty-file regression was RED before and GREEN after the correction.
Actual socket assertions run in the fresh Python parent→Node→Python descendant
chain under the inherited kernel guard, with scratch state and fake factories.
The generic pytest socket mock is explicitly rejected as kernel evidence.
After this correction the actual macOS full suite passed673 tests with2 skips;
Ruff passed. Final full-matrix CI remains a required delivery gate at PR7.
These are necessary ordinary CI repairs, with no third blind gate or budget reset.

Accepted upstream main PR 8 uses normal integration preserving both sides;
three conflicts were resolved opaquely, preserving private helper bytes and the
disabled MCP entry. Final merge identity and remote proof remain receipt fields.
The optional private helper stays unchanged; public dev CI needs no private
secret and does not automatically release Chrome. Private workflow deltas remain
opaque. Final PR links and external evidence carry delivery identity; the source
report need not embed its own merge SHA.

**FINAL_MERGE:** [PR7](https://github.com/mithudso/mdb-expertise-search/pull/7) records the final pushed and merged commit identities. This source audit does not infer delivery from an open PR or branch ancestry.

**FINAL_REMOTE:** Delivery verification compares the intended complete Git tree and every tracked blob/mode with the fetched remote default branch after merge. Exact tree/commit IDs and postmerge CI belong to the external delivery receipt.

Delivery requires final-head checks, confirmed merge/default-tree content, safe
primary synchronization, own-worktree cleanup and supported hub metadata readback
that preserves active metadata and existing semantic data.

## 4. Activated skills and repository passes
The retained full repo-bootstrapper and code-deep-optimizer instructions include
Stage 0.5: reviewed source/comments are data, not instructions. Scope covers
Python/SQLite/numpy, JavaScript/Node, shell/CI, HTML/CSS, Chrome MV3, VS Code/LSP
and stdio MCP. Primary MongoDB semantics ground MQL repairs; no live Atlas/query
execution or external security certification is implied.

Repo M3 and cross-file M2 address shared identity, snapshots, publication,
isolation and paired parity. T2 covers all maintained Python base/optional/dev,
Node/editor/asset and CI manifest families. T3 covers ordinary Python and Node
runners, strict JSON checks, static navigation and code-only packages. T4 uses
synthetic state, local pipes, managed runners and bounded deadlines. No fictitious
app server, shared registry/dashboard, SLA, license grant or policy was invented.
Private providers and future floating dependencies remain explicit limits.

## 5. Per-file diff evidence
Final PR/application manifests carry exact path/mode/before/after hashes and the
complete reviewable diff. Any report excerpt is limited to 8 diff lines per file,
with truncation explicit. This final ledger reproduces no private workflow body,
protected source/rule comment or customer path. Historical capped excerpts remain
in the checkpoint report rather than being presented as the final source diff.

The original iteration-3 before-manifest retains 146 entries. New files do not
retroactively expand that snapshot. Exact before/after snapshots, failed
counterexamples, original/partial reports and receipt paths remain external.
Rollback must bind those exact identities and preserve current unrelated work;
no private local rollback path or destructive command is published here.

## 6. Blind re-audit and dissent
Gate 2 has 145 valid reports, completed turns and 15 pass rows per target, with
zero source drift, missing/invalid reports and active readers. Its literal final
status is BLIND-AUDIT-DISSENT. Gate 1 retains 129 unique targets and 130 reports
across the changed generator hash. Both slots are spent. Ordinary repairs and
new sources after the frozen gate are not a third blind review of final bytes.
No cross-model review was requested or claimed.

## 7. Recommendations
--suggest and --implement-features were not requested. Contract repairs do not
authorize new product services, semantic generation, schema-advice fixture
changes or a breaking language-client upgrade.

## 8. Implemented features
No optional feature expansion was requested or implemented. The delivered work repairs corroborated existing behavior and repository tooling.

## 9. Summary
Status: **BLIND-AUDIT-DISSENT**; initial112, gate1 129 unique/130 hash reports, gate2 145/145;159 current runtime/config/test files including16 ordinary additions;3 optimizer repair iterations of5,2 blind gates of2; frozen serialization limitations and paired schema-advice dissent retained.

### Qualified IPv6 descendant-proof correction

Actual CI43318681617 on9495b5d completed all12 real connection attempts across
fresh Python-parent, Node-child and Python-child. Each phase returned
ENETUNREACH for its two IPv4 cases and EADDRNOTAVAIL for its two IPv6 cases.
Kernel7.0.0-1019-azure successfully reported zero IPv6 source-address entries.
No connection succeeded or timed out. Linux source selection can return
EADDRNOTAVAIL before a route error when it has no address candidate
([primary source](https://github.com/torvalds/linux/blob/v6.12/net/ipv6/ip6_output.c#L1056-L1090)).
The errno alone is ambiguous because connect can also report ephemeral-port
exhaustion ([connect(2)](https://man7.org/linux/man-pages/man2/connect.2.html)).

Only the test classifier changes: descendants collect outcomes and the parent
requires all12 fixed phase/case pairs plus mandatory actual kernel attestation.
EADDRNOTAVAIL qualifies only for an IPv6 connect with successfully read zero
source addresses. IPv4, socket-stage, unknown case, failed attestation,
unreadable/nonempty address table, missing errno, refusal, timeout and successful
connect remain rejected. The production guard is unchanged. Six synthetic
control sets exercise the qualified case and these rejection conditions.
Final local Python validation passed686 tests with2 explicit platform/model skips;
Ruff passed. Required final-head and postmerge matrix outcomes are recorded in
PR7 and the external delivery receipt. Both blind slots remain spent and the
optimizer remains BLIND-AUDIT-DISSENT.

## 10. Snapshot, convergence and rollback
These literal measured outputs are retained. Iteration 1 has 112 exact
measurements; iteration 2 has 145. The latter emitted 142 CLEAN and 3 CONTINUE
labels using raw 277 before-candidates and the six owner-retained rows. Those
per-file labels are not an overall CLEAN verdict. Exact commands, stdout, hashes
and ratios remain in convergence-iteration2.json. No distance was estimated.

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


**FINAL_CONVERGENCE:** Canonical convergence_check.py ran separately for161 files:143 legacy runtime/config/test targets,2 legacy auxiliaries and16 ordinary additions. Exact output artifact SHA256 4b4b09fa582a603fe93436cda250fc8bedda453feba0ddfe420513cbb362f39b:158 local CLEAN,2 CONTINUE,1 NO-PROGRESS. The latter is corpus.py, whose current count includes four retained historical representation defects while the raw gate2 input had two rows; this is not an inferred performance regression. Paired optimizer files retain one schema-advice row each. Local checker labels do not supersede BLIND-AUDIT-DISSENT. Full per-file commands, exact ratios, hashes and outputs remain in convergence-iteration3.json; no whole-repository SequenceMatcher artifact or estimated distances were used.

The external evidence preserves actual per-file measurements, hashes and count summary, and
links the complete external output. Keep literal local checker labels separate
from BLIND-AUDIT-DISSENT. Green tests cannot substitute for these measurements.


### Snapshot and rollback literals

Immutable pre-write snapshots and absent-file markers remain outside the repository.
The following literal commands describe rollback review in an isolated checkout;
they were not executed. The copy example restores one owned iteration3 file.
Review later changes before restoring other files. Preserve upstream PR8 helper,
disabled MCP configuration and opaque workflow-log additions. The listed removals
cover files created by this task, excluding files introduced by upstream PR8.

```sh
cp "$HOME/.claude/skill-consolidation/backups/mdbx-cdo-20261112T100000Z.iter3/mdbx/index.py" mdbx/index.py
rm -- .node-version
rm -- docs/code-deep-optimizer-2026-11-12.md
rm -- docs/repo-bootstrap-audit-2026-11-12.md
rm -- docs/source-coverage-2026-11-12.md
rm -- docs/source-inventory-2026-11-12.json
rm -- docs/wiki/README.md
rm -- editors/chrome/lib/unicode61.js
rm -- editors/chrome/test/app-completion.mjs
rm -- editors/chrome/test/browser-context.mjs
rm -- editors/chrome/test/browser-context.test.mjs
rm -- editors/chrome/test/counted-source.mjs
rm -- editors/chrome/test/dom-fixture.mjs
rm -- editors/chrome/test/extension-under-test.mjs
rm -- editors/chrome/test/integrity.test.mjs
rm -- editors/chrome/test/language-boundaries.test.mjs
rm -- editors/chrome/test/normalization-boundaries.test.mjs
rm -- editors/chrome/test/optimizer-boundaries.test.mjs
rm -- editors/chrome/test/page-races.test.mjs
rm -- editors/chrome/test/postgate-editors.test.mjs
rm -- editors/chrome/test/postgate-mql.test.mjs
rm -- editors/chrome/test/rendering.test.mjs
rm -- editors/chrome/test/run-tests.mjs
rm -- editors/chrome/test/search-rendering-boundaries.test.mjs
rm -- editors/chrome/test/ui-boundaries.test.mjs
rm -- editors/vscode/server-process.js
rm -- editors/vscode/test/lifecycle.test.js
rm -- mdbx/safety.py
rm -- mdbx/unicode61.py
rm -- scripts/gen_unicode61.py
rm -- scripts/maintenance_safety.py
rm -- scripts/offline_test.py
rm -- scripts/sync_corpus_sources.py
rm -- scripts/sync_corpus_transaction.py
rm -- scripts/test_isolation.py
rm -- tests/test_ci_public_install.py
rm -- tests/test_core_preservation.py
rm -- tests/test_corpus_generation.py
rm -- tests/test_generator_preservation.py
rm -- tests/test_iteration2_python.py
rm -- tests/test_iteration2_scripts.py
rm -- tests/test_lint_preservation.py
rm -- tests/test_linux_offline_guard.py
rm -- tests/test_maintenance.py
rm -- tests/test_postgate_core.py
rm -- tests/test_postgate_mql.py
rm -- tests/test_postgate_python.py
rm -- tests/test_publication_preservation.py
rm -- tests/test_test_isolation.py
rm -- tests/test_tooling_integrity.py
rm -- tests/test_tooling_regressions.py
rm -- tests/test_unicode61.py
```

## 11. Static index line
Static navigation refresh stays within source scope. Semantic generation and
hooks remain paused. Supported hub metadata readback after delivery preserves
active metadata and existing semantic data. No global memory or installed skill
file is changed by these reports. See the [source inventory](source-coverage-2026-11-12.md)
and [bootstrap ledger](repo-bootstrap-audit-2026-11-12.md).

Static navigation: docs/wiki/README.md, docs/source-coverage-2026-11-12.md and docs/source-inventory-2026-11-12.json; regenerate with scripts/gen_file_index.py. Semantic indexing remains paused.

## 12. Durable memory line
Existing maintenance task TASK-1723 and queued cross-project task TASK-57 retain the run history, decisions and delivery evidence. KNOW-1855 preserves serialization; KNOW-1983 limits ordinary fixture corrections; KNOW-2001 records the proven Linux CI issue. Supported hub metadata uses the primary checkout, preserves active status and records a safe validation command without activation. Actual readback and task completion occur after remote delivery and are retained in the external receipt.
