<!-- hub-reference-banner -->
> **Reference file — part of the `atlas-diagnostics-expert` hub.** Formerly standalone `mql-perf-harness` skill.
> Sibling topics now reference files under hubs (`mongodb-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not** standalone skills. Ignore "use the X skill" / `related_skills` / SKIP pointers naming bare sibling skills; load `references/<name>.md` from owning hub (see hub's "Cross-hub map").

---

---
name: mql-perf-harness
description: >-
  Heuristic, index-aware perf scorer + 50-query anti-pattern benchmark corpus for MongoDB MQL find()/aggregation. Detects COLLSCANs, in-memory sorts, ESR violations, $where/regex/negation/$in/$size anti-patterns, late $match, unindexed $lookup, deep $skip, missed covering indexes; assigns weighted cost score (proxy for docsExamined/blocking-stage risk, NOT latency) to quantify query cost before/after optimization and prove delta.
  TRIGGER: "score/benchmark this MQL query", "how bad is this aggregation", "before/after delta for query optimization", "run the mql perf harness", build anti-pattern test corpus, measure /dmqo impact across many queries.
  SKIP: rewriting query to convergence -> deep-mongodb-mql-query-optimizer (/dmqo); live cluster explain/latency profiling -> atlas-diagnostics-expert; index/aggregation theory -> mongodb-expert; SQL -> deep-query-optimizer (/dqo).
version: 1.0.1
category: developer
updated: 2026-06-18
metadata:
  changelog:
    - "2026-06-18 sko v1.0.0->1.0.1: iter1 fixed 1 Medium (Pass A dead reference -> created references/scoring-model.md); iter2 blind re-audit clean. Pass M desc 974/1000; Pass K em-dash 0.73/100w; Pass H predicted 10/10 pos, 1/10 neg."
keywords:
  - mql performance
  - query anti-patterns
  - heuristic scorer
  - COLLSCAN detection
  - ESR index
  - in-memory sort
  - aggregation pipeline cost
  - before/after benchmark
  - dmqo benchmark
related_skills:
  - deep-mongodb-mql-query-optimizer
  - mongodb-expert
  - mongodb-query-optimizer
  - atlas-diagnostics-expert
whenToUse:
  - "score/benchmark MQL find() or aggregation pipeline for perf risk"
  - "produce before/after cost delta to show optimization paid off"
  - "generate corpus of bad MQL queries to test optimizer"
  - "measure /dmqo impact across many queries at once"
whenNotToUse:
  - "rewrite/optimize single query to convergence (use deep-mongodb-mql-query-optimizer /dmqo)"
  - "measure real latency/explain on live cluster (use atlas-diagnostics-expert + MongoDB MCP)"
  - "learn index/aggregation theory (use mongodb-expert)"
  - "score SQL (use deep-query-optimizer /dqo)"
---

# MQL Performance Harness

Reproducible **index-aware heuristic** for scoring MongoDB MQL queries by perf risk, plus bundled **50-query anti-pattern corpus** (each bad query paired with optimized form). One question: *did optimizing queries help, and by how much?*

Score = **transparent proxy for executor work** (docsExamined/blocking-stage risk), not measured latency. Deterministic, needs no live cluster. Rewards `/dmqo` moves: adding usable index, ordering Equality→Sort→Range, anchoring regex, inverting negation, pushing `$match` early, fusing `$sort`+`$limit`, keyset-paginating, indexing `$lookup` foreign key.

## Files

- `scripts/mql-perf-tester.mjs` — scorer (Node, zero deps).
- `corpus/corpus.mjs` — 50-query corpus; each entry has `bad`, `opt` (optimized query + recommended indexes), available `idx`, anti-pattern tags.
- `references/scoring-model.md` — full penalty table, detector rules, limitations.

## Run it

```bash
T=~/.claude/skills/mql-perf-harness/scripts/mql-perf-tester.mjs

# baseline: score every bad query against its pre-existing indexes
node "$T" --mode baseline  --out baseline.json

# after: score every optimized query against pre-existing + recommended indexes
node "$T" --mode optimized --out after.json

# delta: per-query + aggregate before/after improvement
node "$T" --compare baseline.json after.json --out delta.json
```

Each run prints one-line summary, writes JSON report + CSV. `--compare` writes per-query delta table. Point at different corpus with `--corpus <path.mjs>`.

## How a query is scored

`scoreEntry(entry, mode)` picks query (`bad` or `opt`) and indexes in scope (baseline = available; optimized = available ∪ recommended), runs find/aggregation detectors, sums weighted penalties. Higher = worse; indexed point query floors near `BASE` cost. Detectors implement `/dmqo` pass taxonomy (P2 index/ESR, P3 selectivity, P4 operators, P5 stage ordering, P6 sort/limit, P7 covered queries, P8 pagination). Full table in `references/scoring-model.md`.

## Limitations (read before quoting a number)

- **Heuristic, not profiler.** Cost units not milliseconds/docsExamined — weighted anti-pattern proxy. Use for *relative* before/after, not absolute capacity planning.
- **Index-awareness is structural.** Checks index-prefix/ESR alignment, not real cardinality/selectivity stats — can't see data skew.
- **Some optimizations assume schema support** (e.g., precomputed boolean to replace `$where`/`$size`/`$mod`); flagged in corpus `note`.
- **For ground truth, validate on live cluster.** Run `/dmqo` with MongoDB MCP connected to confirm COLLSCAN→IXSCAN and real docsExamined drop via `explain()`.