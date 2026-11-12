# Repository maintenance audit — 2026-11-12

Status: supported repairs are pushed in draft PR7 at `a96aee5`. Final blind review,
final pushed-head CI and verified delivery are pending. This ledger replaces the
older checkpoint claims; the2026-10-19 audit remains historical, including its
retractions. This is the full bootstrap, not a quick or changed-only audit.

## Scope and architecture

The Python CLI/TUI uses SQLite/FTS5 and optional embedding providers. MCP and LSP
communicate over stdio. Chrome is an MV3 extension with packaged resources and an
optional explicit local provider; VS Code launches the LSP. There is no application
HTTP service, shared dashboard, remote remediation daemon or MongoDB connection
to invent. See the [maintained wiki](wiki/README.md), [source coverage](source-coverage-2026-11-12.md)
and [optimizer ledger](code-deep-optimizer-2026-11-12.md).

Initial coverage is112 maintained files (109 external reports and3 native reports),
plus2 extra archive/license reports outside runtime scope. Gate1 has129 unique
files and130 substantive reports across two generator hashes. All277 original
Medium+ candidate rows received dispositions before iteration2; the supplemental
generator publication finding was deduplicated and its counterexample retained.
Final gate2 covers145 files, including16 subsequent maintained additions.
All444 protected identities retain baseline hashes. The514 exclusions are explicit
data/generated/binary/lock records; their census is not source inspection.

## Manifest audit

Every applicable manifest family was inspected. Presence does not imply every
aspirational standard is met; exceptions and maintainer choices follow the table.

| File | Present | Lines | Disposition |
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

Actual repair-checkpoint checks:487 Python tests passed,6 optional tests skipped;
249 Chrome and10 VS Code tests passed. Ruff, Python compilation, workflow-log size
check, wheel, code-only Chrome ZIP and VSIX builds passed. VSIX's first invocation
used the wrong working directory and failed; the corrected package-directory
invocation passed. Final checks and actual CI still must run on the final pushed
head. Exact commands and evidence remain in the external machine receipt.

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
- Original owned clean-checkout disposition, hub metadata readback and actual
  merge/default-tree verification remain delivery work, not presumed completion.

## Empirical eligibility and incident record

The offline parity/golden suites are regression checks. They are not heldout model
quality benchmarks. Real ONNX/provider execution and corpus re-embedding are not
authorized, so no empirical model-quality promotion, global champion or throughput
improvement is claimed. The meaningful bounded-memory regression uses synthetic
vectors and tracemalloc, with a preserved failing old implementation counterexample.

Early Python baselines had insufficient isolation. Fixture commits inherited a
semantic post-commit template before filtering was added. Exact metadata-only audit
confirmed4 Git commit vectors,2 marks,2 hub file rows joining1 distinct synthetic
file embedding and0 queue rows. These actual additions were preserved after discovery;
no bodies or vector values were selected and no cleanup/re-embedding followed.
Broader batch effects are outside this repository-specific count. The native resolver
reviewer separately ran5 pure Node tests; that was not a Python-suite execution.

Subsequent local checks use the verified process-tree sandbox denying outbound and
loopback for parent/descendants; scratch HOME/config/data/auth/models; synthetic cached
runtime/provider factories before imports; and fixture Git isolation. The fixture
shim removes inherited GIT selectors/config overrides, uses empty owned system/global
configuration and explicit empty templates, disables terminal prompts and inventories
physical/effective empty hooks before each synthetic commit. Hostile template/global-
hook regressions cover root and later commits. Actual task commits preserve Git
validation/registry behavior and suppress only the hash-verified paused semantic
post-commit hook through a per-command task-local filter. No global hooks changed.

## Delivery ledger

PR: https://github.com/mithudso/mdb-expertise-search/pull/7 (draft at checkpoint).
Final gate2, final pushed-head CI, merge SHA, remote full-content proof, postmerge CI,
safe primary disposition, own-worktree cleanup and supported hub readback are pending.
The external machine receipt is authoritative for phase changes and exact evidence.
