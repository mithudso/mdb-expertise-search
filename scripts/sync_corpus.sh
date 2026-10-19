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
# MQL query-optimization fact families (source-anchored extracts of public MongoDB docs). llms-small and
# llms-full are omitted: small is a subset of facts (duplicate hits), full repeats facts with context.
CONCEPTS_SRC="${MDBX_CONCEPTS_SRC:-$HOME/.global-ai-hub/llms-concepts}"
for n in advanced-explain-and-planner-changes atlas-and-compass-query-tooling \
         atlas-slow-query-and-advisor-automation compound-index-design explain-output-and-stages \
         explain-plans-and-query-planner query-engine-releases-and-ai-tooling \
         query-operators-bounds-and-projection query-optimization-tooling \
         query-planner-plan-cache-and-query-settings query-shape-optimization \
         query-shapes-profiler-and-index-usage sharded-query-targeting special-indexes-and-index-builds \
         time-series-indexes-and-metafield time-series-query-execution time-series-query-optimization \
         time-series-sizing-and-sharding mql-query-optimization-family; do
  d="$CONCEPTS_SRC/mongodb-$n.llms"
  [ -d "$d" ] || continue
  mkdir -p "corpus/llms/mongodb-$n.llms"
  for f in llms.txt llms-facts.txt llms-vocabulary.txt manifest.json; do
    [ -f "$d/$f" ] && cp "$d/$f" "corpus/llms/mongodb-$n.llms/"
  done
done
# NOTE: the deep MQL optimizer skill ships only as the redacted mongodb-expert reference
# (corpus/skills/mongodb-expert/references/deep-mongodb-mql-query-optimizer.md); re-redact it by hand
# after a re-sync — its live SKILL.md cites workload analyses that must not be committed.
python3 scripts/redact_corpus.py
python3 scripts/sweep_customers.py
.venv/bin/mdbx index
