# Repository maintenance audit — 2026-11-12

Delivery status: active checkpoint; independent review and final CI are pending.
This ledger supersedes current-behavior claims in the historical 2026-10-19 audit.

The initial inventory contains112 maintained source/config/test files.109 external
one-file reports plus3 native reports cover those exact pre-edit source hashes.
Two additional archive/license reports are outside maintained runtime scope. The
first final-review inventory contains129 maintained files, including17 new files.
All444 protected-data identities retain their original hashes. Tracked corpus
and frozen search fixture bytes match baseline. The earlier fixture-hook effects
on live semantic stores are recorded below; stores were left intact after discovery.
Only static navigation and relevant synthetic MQL goldens are refreshed.

The full bootstrap covers root Python packaging, Chrome MV3 modules/manifest,
VS Code package/lock/grammar, CI/editor configuration, existing agent entry points,
workflow logs, documentation, privacy tooling and external-operation boundaries.
There is no app HTTP server, central dashboard or remote remediation service to
scaffold. Existing license/conduct terms are retained without new legal promises
or security-response SLA. Hub registration is delegated to the batch supervisor.
The maintained entry point is [docs/wiki/README.md](wiki/README.md).

Initial reports contained75 Critical,69 High,210 Medium and12 Low candidate rows;
these are reviewer reports, not354 independent corroborated defects. Native review
added an offline-fixture finding. Separate disposition ledgers record duplicate,
corroborated, repaired and retained cases; source coverage is not a clean verdict.

Repairs cover paired MQL normalization/parser/optimizer contracts, conservative
rewrites, UTF-16 editor operations, stale UI tasks, full-text search deduplication,
model/cache identity, finite-vector validation, confined reads, atomic publication,
owned update clones, safe privacy diagnostics and source/rotation preservation.
CI installs without private-library credentials, uses locked editor dependencies,
pinned actions and offline checks, and builds code-only Chrome artifacts. Merge
no longer publishes a rolling corpus release or activates an update.

Pre-checkpoint verification:285 Python tests passed with6 optional skips;182 Chrome
tests passed;7 VS Code tests passed; Ruff and Python compilation passed. Python
wheel and VS Code package builds passed. The VS Code dependency audit reports0
advisories after updating tooling and overriding its vulnerable minimatch dependency.
Final pushed-commit CI and independent review remain pending at this checkpoint.

Known limits: historical short-section chunk headings/lines are approximate and
need an explicit frozen-format migration; legacy copied files without ownership
provenance are preserved; secure corpus reads require POSIX no-follow descriptors;
optional private-auth integration and interactive browser/editor sessions were not
exercised. No model benchmark or live provider evaluation was performed. Default
empirical evaluation cannot claim improvement: baseline parity already passed,
its harness was strengthened and intentional contract fixes prevent an unchanged-
API promotion claim. No global champion or semantic store was updated.

The early Python baselines were insufficiently isolated: synthetic Git fixture
commits dispatched the inherited semantic post-commit hook before filtering was
added. Metadata-only review confirmed4 commit vectors,2 marks and2 hub rows joining
1 file embedding, all from synthetic fixtures;0 matching queue rows. Existing
stores/services were preserved after discovery. Future checks use process-tree
egress isolation, command-scoped filtered hooks, scratch application state and
pre-collection synthetic embedding guards. The native resolver reviewer separately
ran5 pure Node tests; that was not a Python-suite execution.

The external machine receipt retains exact commands, source hashes, substantive
review logs, convergence measurements, incident evidence and delivery state. Final
review status, CI/PR and merge verification will replace this checkpoint status.
