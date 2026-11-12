#!/usr/bin/env bash
# Rebuild corpus/ from the local skill tree and llms exports, then reindex.
# Sources are the author's machine; edit the paths below for your own copies.
set -euo pipefail
cd "$(dirname "$0")/.."
SKILLS="${MDBX_SKILLS_SRC:-$HOME/.claude/skills}"
LLMS_SRC="${MDBX_LLMS_SRC:-$HOME/dev/skills-explorer/llms}"
DOCS_SRC="${MDBX_MONGODB_DOCS_LLMS:-$HOME/dev/llms-explorer/outputs/exports/mongodb.com.llms}"

gate_log="$(mktemp)"
trap 'rm -f "$gate_log"' EXIT
if [ ! -f "${MDBX_DENYLIST:-$HOME/.config/mdbx/denylist.txt}" ]; then
  echo "corpus privacy denylist is missing; nothing synced" >&2
  exit 1
fi
python3 scripts/sync_corpus_sources.py --check-destination "$PWD/corpus"
mkdir -p corpus/skills corpus/llms
sync_tree() {
  if ! python3 scripts/sync_corpus_sources.py -- "$1" "$2" >"$gate_log" 2>&1; then
    echo "corpus source copy failed; private diagnostics withheld" >&2
    return 1
  fi
}
for d in "$SKILLS"/mongodb-* "$SKILLS"/atlas-diagnostics-expert "$SKILLS"/atlas-vector-search-pii-isolation; do
  [ -d "$d" ] || continue
  sync_tree "$d" "corpus/skills/$(basename "$d")"
done
for n in atlas-cli atlas-triage-workflows diagnostic-tool-design error-codes-and-troubleshooting \
         ftdc-and-log-tooling kb-backed-troubleshooting mongodb-atlas-data-federation \
         mongodb-drivers mongosh-reference ts-diag-and-diagnostic-workflows; do
  [ ! -d "$LLMS_SRC/$n.llms" ] || sync_tree "$LLMS_SRC/$n.llms" "corpus/llms/$n.llms"
done
[ ! -d "$DOCS_SRC" ] || sync_tree "$DOCS_SRC" "corpus/llms/$(basename "$DOCS_SRC")"
# MQL query-optimization fact families (source-anchored extracts of public MongoDB docs). llms-small and
# llms-full are omitted: small is a subset of facts (duplicate hits), full repeats facts with context.
CONCEPTS_SRC="${MDBX_CONCEPTS_SRC:-$HOME/.global-ai-hub/llms-concepts}"
# Every mongodb-*.llms family the concept builder has produced is picked up (no hard-coded list), except
# the two already synced above from the skills export. Dated "-frontier-YYYYMMDD" research families
# are public-docs extracts too; the redact/sweep step below is the gate for anything sensitive.
for d in "$CONCEPTS_SRC"/mongodb-*.llms; do
  [ -d "$d" ] || continue
  b="$(basename "$d")"
  case "$b" in mongodb-atlas-data-federation.llms|mongodb-drivers.llms) continue ;; esac
  if ! python3 scripts/sync_corpus_sources.py --facts-only -- "$d" "corpus/llms/$b" >"$gate_log" 2>&1; then
    echo "corpus source copy failed; private diagnostics withheld" >&2
    exit 1
  fi
done
# NOTE: the deep MQL optimizer skill ships only as the redacted mongodb-expert reference
# (corpus/skills/mongodb-expert/references/deep-mongodb-mql-query-optimizer.md); re-redact it by hand
# after a re-sync — its live SKILL.md cites workload analyses that must not be committed.
if ! python3 scripts/redact_corpus.py >"$gate_log" 2>&1; then
  echo "corpus redaction failed; private diagnostics withheld" >&2
  exit 1
fi
if ! python3 scripts/sync_corpus_sources.py --check-publication "$PWD/corpus" >"$gate_log" 2>&1; then
  echo "corpus has publication candidates outside the privacy gate types" >&2
  exit 1
fi
if python3 scripts/sweep_customers.py >"$gate_log" 2>&1; then
  :
else
  sweep_status=$?
  if [ "${MDBX_UPDATER_HOLDBACK:-0}" = 1 ] && [ "$sweep_status" = 1 ]; then
    exit 3 # The updater restores flagged files, then repeats the mandatory sweep.
  fi
  echo "corpus privacy sweep failed; private diagnostics withheld" >&2
  exit 1
fi
[ "${MDBX_SKIP_INDEX:-0}" = 1 ] || .venv/bin/mdbx index --corpus "$PWD/corpus"
