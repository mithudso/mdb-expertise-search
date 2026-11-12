# Repository maintenance audit — 2026-11-12

Status: supported source repairs are in final integration. The frozen final blind
result is **BLIND-AUDIT-DISSENT**; both blind slots are spent. Ordinary regression
checks do not replace that verdict with CLEAN. Final validation and delivery
evidence are supplied in the fields below. The 2026-10-19 audit and earlier
checkpoint results remain historical, including their retractions.

## Scope and architecture

The Python CLI/TUI uses SQLite/FTS5 and optional embedding providers. MCP and LSP
communicate over stdio. Chrome is an MV3 extension with packaged resources and an
optional explicit local provider; VS Code launches the LSP. There is no application
HTTP service, shared dashboard, remote remediation daemon or MongoDB connection
to invent. See the [maintained wiki](wiki/README.md), [source coverage](source-coverage-2026-11-12.md)
and [optimizer ledger](code-deep-optimizer-2026-11-12.md).

Initial coverage is 112 maintained targets: 109 external plus 3 native reports,
with 2 extra archive/license reports excluded from that denominator. Gate 1 has
129 unique targets and 130 substantive reports because one generator received a
second current-hash report. All 277 original Medium+ rows were dispositioned before
iteration 2; the supplemental generator publication row was deduplicated.

Gate 2 is complete and drained: 145/145 valid completed 15-pass reports, zero
frozen-source drift, missing or invalid reports, and no active readers. Its raw
Medium+ count is 251 (2 Critical, 26 High, 223 Medium); 13 Low rows remain retained.
The execution ledgers account for 252 corroborated rows: core 61, MQL 68, Python
76 and editors 47, initially classified as 244 real, 6 duplicates and 2 blocked. Native adjudication
retains that historical ledger and now classifies 243 corroborated Medium+ real
manifestations, 1 Low source observation, 6 duplicates and 2 blocked. Rows and
shared/paired fixes are not independently unique bugs. The extra execution row,
UPSTREAM-CI-F1, is the ordinary upstream helper/caller public-install defect with
a retained synthetic failure, not an extra blind report.

The 145 legacy targets comprise 143 runtime/configuration/test records, one LICENSE
prose record and one auxiliary .gitkeep. New repair helpers/tests and additional
generated catalog assets are inventoried separately without claiming 15-pass
coverage of their final bytes. The original iteration-3 before-manifest retains
146 records, including the then-absent core regression test.

All 444 protected identities retain metadata-only baseline preservation proof.
The historical 514 exclusions comprise those identities plus 70 generated,
fixture, lockfile or binary records. Census preservation is not source inspection
or redistribution clearance.

## Manifest audit

Every applicable maintained manifest family was inspected: Python base/optional/dev,
Node packages/dependency metadata, CI, shell, editor configuration and assets.
The following line counts are historical checkpoint metadata, not refreshed counts.
Private workflow deltas are preserved opaquely; their bodies were not inspected
for this final report. Presence does not imply every
aspirational standard is met; exceptions and maintainer choices follow the table.

| File | Present at checkpoint | Historical lines | Disposition |
|---|---|---:|---|
| `.github/copilot-instructions.md` | yes | 21 | factual repo-specific content retained or updated |
| `CLAUDE.md` | yes | 50 | factual repo-specific content retained or updated |
| `AGENTS.md` | yes | 12 | factual repo-specific content retained or updated |
| `GEMINI.md` | yes | 3 | factual repo-specific content retained or updated |
| `memory.md` | yes | 157 | factual repo-specific content retained or updated |
| `prompts.md` | yes | 59 | factual repo-specific content retained or updated |
| `scripts/rotate_workflow_logs.py` | yes | 84 | factual repo-specific content retained or updated |
| `.editorconfig` | yes | 12 | factual repo-specific content retained or updated |
| `.gitignore` | yes | 35 | factual repo-specific content retained or updated |
| `.gitattributes` | yes | 3 | factual repo-specific content retained or updated |
| `.node-version` | yes | 1 | factual repo-specific content retained or updated |
| `.env.example` | yes | 10 | factual repo-specific content retained or updated |
| `.vscode/settings.json` | yes | 6 | factual repo-specific content retained or updated |
| `.vscode/extensions.json` | yes | 1 | factual repo-specific content retained or updated |
| `.vscode/launch.json` | yes | 8 | factual repo-specific content retained or updated |
| `.vscode/mcp.json` | yes | 9 | factual repo-specific content retained or updated |
| `.mcp.json` | yes | 8 | factual repo-specific content retained or updated |
| `.github/workflows/ci.yml` | yes | 62 | factual repo-specific content retained or updated |
| `.github/dependabot.yml` | yes | 8 | factual repo-specific content retained or updated |
| `.github/CODEOWNERS` | yes | 1 | factual repo-specific content retained or updated |
| `.github/PULL_REQUEST_TEMPLATE.md` | yes | 6 | factual repo-specific content retained or updated |
| `.github/ISSUE_TEMPLATE/bug_report.md` | yes | 9 | factual repo-specific content retained or updated |
| `.github/ISSUE_TEMPLATE/feature_request.md` | yes | 7 | factual repo-specific content retained or updated |
| `.github/SECURITY.md` | yes | 4 | factual repo-specific content retained or updated |
| `LICENSE` | yes | 21 | factual repo-specific content retained or updated |
| `CONTRIBUTING.md` | yes | 5 | factual repo-specific content retained or updated |
| `CODE_OF_CONDUCT.md` | yes | 5 | factual repo-specific content retained or updated |
| `docs/ARCHITECTURE.md` | yes | 47 | factual repo-specific content retained or updated |
| `docs/DEVELOPMENT.md` | yes | 54 | factual repo-specific content retained or updated |
| `docs/COMPONENTS.md` | yes | 42 | factual repo-specific content retained or updated |
| `docs/SECURITY.md` | yes | 27 | factual repo-specific content retained or updated |
| `docs/MCP.md` | yes | 34 | factual repo-specific content retained or updated |
| `docs/TESTING.md` | yes | 61 | factual repo-specific content retained or updated |
| `README.md` | yes | 243 | factual repo-specific content retained or updated |
| `docs/codebase-overview.md` | yes | 291 | factual repo-specific content retained or updated |
| `docs/high_signal_file_index.json` | yes | 1202 | factual repo-specific content retained or updated |
| `scripts/gen_file_index.py` | yes | 92 | factual repo-specific content retained or updated |
| `scripts/check_doc_indexes.py` | yes | 13 | factual repo-specific content retained or updated |
| `docs/integrations-and-assumptions.md` | yes | 19 | factual repo-specific content retained or updated |
| `docs/known-issues.md` | yes | 84 | factual repo-specific content retained or updated |
| `docs/onboarding.md` | yes | 7 | factual repo-specific content retained or updated |
| `docs/INSTALLATION.md` | yes | 82 | factual repo-specific content retained or updated |
| `docs/requirements.md` | yes | 14 | factual repo-specific content retained or updated |
| `docs/logging.md` | yes | 17 | factual repo-specific content retained or updated |
| `docs/caching-and-optimization.md` | yes | 20 | factual repo-specific content retained or updated |
| `docs/runbooks/rebuild-index.md` | yes | 6 | factual repo-specific content retained or updated |
| `docs/external-calls.md` | yes | 17 | factual repo-specific content retained or updated |
| `docs/wiki/README.md` | yes | 20 | factual repo-specific content retained or updated |

## Changes and conventional verification

Repairs address conservative paired MQL rewrites/analysis, editor UTF-16 and async
ownership, Unicode/FTS ranking parity, coherent versioned search snapshots, finite
vector/provenance validation, bounded on-disk semantic staging, no-follow reads,
recoverable descriptor-based publication, owned update clones, source-preserving
maintenance, safe diagnostics and isolated synthetic tests. Production chunk_text
and _merge_tiny remain exact to checkpoint592db43; a64-output synthetic production
proof checks serialized identities and metadata. No copied codec or generator
monkeypatch hides fixture drift.

Historical repair-checkpoint checks recorded 487 Python passes/6 optional skips,
249 Chrome and 10 VS Code passes. Interim integration recorded 624/1, a 68/1
focused fault-injector repair, then 666/2. Those observations remain history.

Actual post-upstream source checks at 08708f0 recorded 668 Python passes and
2 skips in 27.07 seconds: unavailable real ONNX and Linux namespace proof
inapplicable on macOS. Ruff, compilation, shell syntax and all five search/
optimizer/lint/operator/Unicode freshness checks passed. The wheel 0.7.1 build
passed (SHA256 46f2efa2bd7957f0471aa0206001f5065c033fc2e98ad53192a115ec9b8f8906);
the code-only Chrome package had 27 members and VSIX had 325 files/467.11 KB.
Fresh Chrome 280 and VS Code 20 tests passed. The 64-output production
serialization/AST proof also passed again as one test. Exact local commands
and artifact evidence are retained in final-local-checks.json. These source-head
results do not assert completed final-head CI or remote delivery.

**FINAL_VALIDATION:** Actual integrated source at08708f0:668 Python tests passed,2 skipped (real ONNX unavailable and Linux-only proof on macOS); Chrome280 and VS Code20 passed. Ruff, compilation, shell syntax, five generator freshness checks, wheel, code-only Chrome ZIP and VSIX builds passed. Exact commands/results and later CI-repair checks are retained in the external delivery receipt. The independent production scope proof passed64 synthetic outputs and exact selected source/AST checks.

**FINAL_CI:** [PR7 checks](https://github.com/mithudso/mdb-expertise-search/pull/7/checks) cover macOS and Ubuntu on Python3.11/3.12/3.13. First integrated run43312948550 exposed Linux inherited-guard self-recognition and nested-runner failures; its failed result is retained. Final pushed-head CI must pass before merge; actual run IDs/results are recorded in the delivery receipt.

Dependency metadata: npm audit reports0 vulnerabilities over144 VS Code dependency
records. npm outdated reports vscode-languageclient9.0.1 installed/wanted versus
11.0.0 latest; adopting its breaking API/runtime requirements is deferred. Chrome
has no npm dependencies. Python pip-audit reports0 known vulnerabilities in the
installed71-record environment; the editable project0.7.0 itself is not on PyPI and
was skipped. This is an installed-environment audit, not proof over every future
version allowed by open dependency ranges. The optional private auth/client packages
remain upstream boundaries. Packaging preserves the existing license; no new grant.

## External-call standards and adaptations

The [operations inventory](external-calls.md) identifies provider requests, ONNX
artifacts/inference, optional auth/Glean, Git/GitHub updates, source sync, extension
resources, packaging metadata and stdio editors. Each has a concrete command/tool
entry, safe failure behavior and relevant mocked tests. Tests use no real remote
service or in-process model. Persisted index/export changes have structural readback
and identity checks. The source census also includes local subprocess boundaries.

The canonical dashboard standard's shared registry, central JSONL sink, automatic
remediation UI and generated dashboard cards are not implemented here. A local
CLI/editor architecture does not supply those services. The family table is a
factual inventory, not a claim of per-call five-standard compliance. A new shared
operations service would require a separately chosen architecture. No fictitious
server, database, dashboard or remediation policy was added to meet a template.

The MCP surface has8 registered tools, documented and exercised through synthetic
tool/stdio tests. No live corpus MCP health query was run. No native-messaging host
or offscreen document exists. Auth is optional and delegated to ai-auth; no actual
credentials, Keychain or vendor login was read/exercised. Interactive Chrome/VS Code
activation and real provider performance remain unverified. No repository-local
agents or context-skill installation target exists; no global skills/configuration
or concept tree was changed. Static file navigation replaces semantic regeneration
for this authorized maintenance. Embeddings and semantic hooks remain paused.

## Exact exceptions and maintainer choices

- Four corroborated chunk representation defects remain: parent-stub line origin,
  sibling breadcrumb merging, inline-backtick fence recognition and unbounded
  oversized breadcrumbs. All are **BLOCKED: separately authorized serialization
  migration required**. The first two are the historical short-section metadata
  defects. Frozen chunk/search/vector contracts are preserved.
- Schema-dependent key/value and numeric-string advice retains its existing strong
  warning. Its correction affects two expectations outside the exact authorized
  four-file optimizer scope. The production correction is deferred wholesale.
  No fixture-specific bypass is used. All lint expectations remain unchanged.
- Existing public-repository corpus provenance/redistribution concerns are not
  resolved by this source audit. Protected corpus contents/history were not read,
  removed, untracked, republished or represented as privacy-cleared.
- Secure corpus reads require POSIX no-follow descriptors. Interactive platform
  support and private-auth integrations are excluded from the synthetic results.
- No enforced numeric coverage percentage, performance SLO, security-response SLA,
  normative policy or additional legal promise is invented. Maintainers must choose
  such commitments explicitly. Existing contribution/conduct/security text remains.
- `.env.example` is an introductory subset; detailed optional backend/auth/update
  overrides live in installation/development docs and source. This is a documented
  manifest-completeness gap, not an assertion that every environment key is listed.
- The cross-origin frame ancestry API cannot establish every ancestry chain.
  Interactive Chrome/VS Code activation and real optional providers remain unverified.
- Original checkout disposition, supported hub metadata readback, final-head CI
  and remote/default-tree verification are delivery evidence, not presumed results.

## Empirical eligibility and incident record

The offline parity/golden suites are regression checks. They are not heldout model
quality benchmarks. Real ONNX/provider execution and corpus re-embedding are not
authorized, so no empirical model-quality promotion, global champion or throughput
improvement is claimed. The meaningful bounded-memory regression uses synthetic
vectors and tracemalloc, with a preserved failing old implementation counterexample.

Early Python baselines had insufficient isolation. Fixture commits inherited a
semantic post-commit template before filtering was added. Exact metadata-only audit
confirmed 4 Git commit vectors plus 1 distinct synthetic file embedding represented
by 2 rows, with 2 marks and 0 queue rows. These actual additions were preserved after discovery;
no bodies or vector values were selected and no cleanup/re-embedding followed.
Broader batch effects are outside this repository-specific count. The native resolver
reviewer separately ran5 pure Node tests; that was not a Python-suite execution.

Subsequent local checks use the verified process-tree sandbox denying outbound and
loopback for parent/descendants; scratch HOME/TMPDIR/config/data/auth/models; synthetic cached
runtime/provider factories before imports; and fixture Git isolation. The fixture
shim removes inherited GIT selectors/config overrides, uses empty owned system/global
configuration and explicit empty templates, disables terminal prompts and inventories
physical/effective empty hooks before each synthetic commit. Hostile template/global-
hook regressions cover root and later commits. Actual task commits preserve Git
validation/registry behavior and suppress only the hash-verified paused semantic
post-commit hook through a per-command task-local filter. No global hooks changed.

## Final integration and delivery ledger

The source-bound Linux launcher uses privileged empty network-namespace creation,
then setpriv drops IDs, supplementary groups and capabilities and sets
NoNewPrivs before env -i executes a scrubbed scratch command. Nested execution
requires actual kernel attestation: nonroot current/saved/fs IDs, zero capability
sets, empty groups, down loopback-only interfaces and no delivery routes. Only
inert reject IPv6 entries on down loopback may remain. No environment flag attests
isolation. Real Linux parent/Python/Node inheritance is a final-CI proof, not a
claim inferred from local macOS mocks. Host network/configuration is unchanged.

Accepted upstream main PR 8 uses normal integration preserving both sides.
Three merge conflicts were resolved without exposing private workflow bodies;
helper bytes and the disabled MCP entry remain preserved. Final merge identity
and remote confirmation belong in the receipt.
The private dependency helper remains unchanged for explicit optional installs;
public dev CI requires no private secret and does not automatically release
Chrome. Private workflow deltas stay opaque.

PR 7: https://github.com/mithudso/mdb-expertise-search/pull/7
Upstream PR 8: https://github.com/mithudso/mdb-expertise-search/pull/8

**FINAL_MERGE:** [PR7](https://github.com/mithudso/mdb-expertise-search/pull/7) records the final pushed and merged commit identities. This source audit does not infer delivery from an open PR or branch ancestry.

**FINAL_REMOTE:** Delivery verification compares the intended complete Git tree and every tracked blob/mode with the fetched remote default branch after merge. Exact tree/commit IDs and postmerge CI belong to the external delivery receipt.

**FINAL_PRIMARY_DISPOSITION:** The original main checkout was clean at4d482894b80cad4cd720058a9894956e745da1be during preflight. A later fast-forward is permitted only after fresh cleanliness, divergence and hook/activation checks; actual disposition and owned-worktree cleanup are recorded in the delivery receipt.

**FINAL_HUB_METADATA:** After remote delivery, supported project_manager get/upsert/set-activation/get metadata calls preserve the existing active status. The validate command must refer to the primary scripts/check_doc_indexes.py, with no service/model/index activation. Actual supported API readback is retained in the delivery receipt.

Delivery requires passing checks on the last pushed head, confirmed merge and
remote default-tree content, safe checkout synchronization and task-owned cleanup.
A queued merge or local/pushed checkpoint alone is insufficient. Supported hub
metadata readback after delivery must preserve active metadata and existing
semantic data; it is not semantic generation. This source report need not embed
its own merge SHA: final PR links and the external receipt carry that evidence.


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
