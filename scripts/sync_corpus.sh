#!/usr/bin/env bash
# Rebuild corpus/ from the local skill tree and llms exports, then reindex.
# Sources are the author's machine; edit the paths below for your own copies.
set -euo pipefail
cd "$(dirname "$0")/.."
SKILLS="${MDBX_SKILLS_SRC:-$HOME/.claude/skills}"
LLMS_SRC="${MDBX_LLMS_SRC:-$HOME/dev/skills-explorer/llms}"
DOCS_SRC="${MDBX_MONGODB_DOCS_LLMS:-$HOME/dev/llms-explorer/outputs/exports/mongodb.com.llms}"

mkdir -p corpus/skills corpus/llms
for d in "$SKILLS"/mongodb-* "$SKILLS"/atlas-diagnostics-expert "$SKILLS"/atlas-vector-search-pii-isolation; do
  rsync -aL --exclude .DS_Store --exclude .skillfish.json "$d" corpus/skills/
done
for n in atlas-cli atlas-triage-workflows diagnostic-tool-design error-codes-and-troubleshooting \
         ftdc-and-log-tooling kb-backed-troubleshooting mongodb-atlas-data-federation \
         mongodb-drivers mongosh-reference ts-diag-and-diagnostic-workflows; do
  [ -d "$LLMS_SRC/$n.llms" ] && rsync -a --exclude .DS_Store "$LLMS_SRC/$n.llms" corpus/llms/
done
[ -d "$DOCS_SRC" ] && rsync -a --exclude .DS_Store "$DOCS_SRC" corpus/llms/
.venv/bin/mdbx index
