# Offline verification

Use Python 3.11+ and Node 26 (`.node-version`). Install dependencies separately:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
npm ci --ignore-scripts --prefix editors/vscode
```

On macOS run every test/check through the process-tree egress wrapper:

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
Other platforms require an equivalent network sandbox; the wrapper fails closed
when macOS sandbox-exec is unavailable.

Before collection, tests/conftest.py assigns scratch application paths, clears only
its own cached ONNX runtime and replaces loading with a synthetic unavailable
runtime. Backend tests use synthetic vectors/sessions. Real ONNX inference is
excluded from the conventional suite even if the host has a downloaded model.
The known semantic-only Git post-commit hook is filtered in inherited command
scope; other validation hooks are preserved. Synthetic commits disable signing
and reject inherited foreign Git repository selectors. No HOME/CODEX_HOME override
or persistent Git configuration is needed.

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
semantics or measured performance gains.
