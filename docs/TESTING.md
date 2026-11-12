# Offline verification

Use Python 3.11+ and Node 26 (`.node-version`). Install dependencies separately:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
npm ci --ignore-scripts --prefix editors/vscode
```

On macOS and supported Linux CI runners, run every test/check through the process-tree egress wrapper:

```sh
python3 scripts/offline_test.py -- .venv/bin/python -m pytest -q
python3 scripts/offline_test.py -- .venv/bin/python -m ruff check .
python3 scripts/offline_test.py -- .venv/bin/python -m compileall -q mdbx scripts tests
python3 scripts/offline_test.py -- npm test --prefix editors/chrome
python3 scripts/offline_test.py -- npm test --prefix editors/vscode
python3 scripts/offline_test.py -- .venv/bin/python scripts/package_chrome_extension.py --no-data
python3 scripts/offline_test.py -- .venv/bin/python scripts/check_doc_indexes.py
python3 scripts/offline_test.py -- .venv/bin/python scripts/rotate_workflow_logs.py --check
```

The wrapper denies outbound traffic for descendants, including loopback. An exact
owned synthetic listener port may be allowed explicitly; never allow a real model,
service or index endpoint. Python socket patches alone do not cover descendants.
macOS uses sandbox-exec. Linux requires a non-root runner with passwordless sudo
and unshare; the child gets an isolated network namespace with no configured
interfaces and drops back to the runner uid/gid. Linux does not accept host fixture-
port exceptions. Unsupported platforms fail closed. CI covers macOS and Ubuntu
on Python 3.11, 3.12 and 3.13; dependency downloads precede isolated checks.

Before product imports, scripts/test_isolation.py assigns a fresh process-only HOME,
XDG/config/data/auth/model and temporary locations, forces cached synthetic ONNX/client factories,
and installs the same protection for Python descendants. Artifact-validation tests
explicitly restore the real loader with synthetic dependency factories and empty
model directories; no real inference runs. No shared configuration is changed.

Synthetic Git fixtures use owned empty system/global configuration, empty hooks and
an explicit empty init/clone template. The shim strips every inherited GIT_* selector
and numbered override before each command, then inspects effective and physical
hooks before every fixture commit. Hostile-template regressions cover both initial
and later commits. Repository delivery commits are separate: they preserve validation
and registry hooks and suppress only the independently paused, hash-verified semantic
post-commit action through command-scoped filtering.

The suite covers index rollback/model identity, full-content deduplication, stale
vector caches, finite embeddings, confined files and atomic writes; paired Python
and JavaScript normalization/optimizer/lint contracts; stdio LSP deadlines and
UTF-16 edits; CLI/MCP/TUI/provider-adapter behavior; synthetic updater, redaction,
package promotion, rotation and source-ownership failures. Chrome tests evaluate
actual app/popup scripts with controlled asynchronous DOM fixtures. VS Code tests
exercise restart ownership, grammar and launcher resolution.

Current exact results belong to the maintenance ledger and CI, rather than a
hardcoded test count here. Optional private ai-auth integration can skip when the
library is absent. A browser/interactive editor session, real provider credentials,
model benchmarks, live corpus publication and service activation are separate
checks and were not performed in this maintenance.

Only static catalogs and relevant synthetic MQL goldens are refreshed. Frozen
search fixtures and vectors remain byte-identical. Full pre-existing suites are
must-pass gates; passing paired implementations alone does not establish query
semantics or measured performance gains. The search fixture generator always uses
the actual production chunker; frozen expectations have no compatibility codec.
The four ordinary optimizer expectations changed under the narrow maintenance
authorization; subsequent post-gate repairs preserve all expectation bytes.
