<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `deep-mongodb-mql-query-optimizer` skill.
> Sibling topics in this family are now reference files under the hubs (`mongodb-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not** standalone
> skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that name a bare sibling
> skill; load that topic's `references/<name>.md` from the owning hub (see the hub's "Cross-hub map").

---

---
name: deep-mongodb-mql-query-optimizer
description: >-
  Multi-pass review-and-fix optimizer for one MongoDB MQL find() filter, write-op filter or
  aggregation pipeline (deep-optimizer loop). TRIGGER: "optimize this MQL/aggregation",
  "run mql-optimizer", "why is this query slow", "what index for this query", COLLSCAN, blocking sort,
  slow $lookup, deep skip paging, docsExamined>>nReturned, scatter-gather, plan-cache flapping,
  slow count/distinct, time-series query slow, slow-log line. Audits ESR/ERS index
  design, selectivity, shard targeting, operator anti-patterns, $in/$or bounds, stage order,
  accumulator memory, covered queries, cursor economics and explain (incl. 8.0 query settings,
  8.3 cost-based ranker); applies every High/Medium rewrite; verifies via explain when MongoDB
  MCP is connected. Indexes recommend-only. SKIP: theory -> mongodb-expert; live cluster triage
  -> atlas-diagnostics-expert; schema redesign -> mongodb:mongodb-schema-design; ODM fixes ->
  mongodb-odm-patterns; SQL -> deep-query-optimizer; Search relevance -> mongodb-atlas-expert.
version: 1.4.0
updated: 2026-10-19
category: mongodb
whenToUse:
  - "optimize this MongoDB query / aggregation pipeline"
  - "why is this pipeline slow, and fix it"
  - "what index should I create for this exact query?"
  - "this find() is doing a COLLSCAN — rewrite it"
  - "my $sort hits the memory limit / QueryExceededMemoryLimitNoDiskUseAllowed"
  - "docsExamined is much higher than nReturned on this query"
  - "rewrite this skip/limit deep pagination — it gets slower every page"
  - "this $lookup makes the aggregation crawl — fix the pipeline"
  - "can this query be covered by the index (no FETCH)?"
  - "my change stream's getMore scans millions of oplog entries and returns nothing"
  - "this query times out at maxTimeMS on our sharded cluster — fix the query"
  - "the planner keeps flapping between two indexes for the same query"
  - "this $elemMatch key/value attribute lookup is slow"
  - "here is a slow-query log line — fix the query behind it"
  - "countDocuments on this filter times out"
  - "this time-series query is slow even with an index on the metaField"
related_skills:
  - mongodb-expert
  - mongodb-docset-lookup
  - deep-query-optimizer
  - atlas-diagnostics-expert
  - mongodb-collation
  - mongodb-clustered-collections
  - mongodb-odm-patterns
  - mongodb-gridfs
  - mongodb-atlas-expert
metadata:
  changelog:
    - "2026-10-19 v1.3.0->v1.4.0 — folded in the 2026-10-18 MQL research (8 gated mongodb-expert/atlas-diagnostics-expert spokes, 45 concepts): ERS exception, $in 201-element threshold and SORT_MERGE, rooted-$or blocking-sort risk, same-field $or->$in, $where deprecation, covered-query disqualifiers, partial/sparse eligibility, count/distinct/$sample shapes, batchSize/maxTimeMS semantics, sharded skip/limit and split-pipeline merge, time-series bucket rules (6.3 default index, metaField cardinality, unpack pushdown, 8.0 block processing, last-point DISTINCT_SCAN), 8.0 setQuerySettings vs hint vs index filters, queryShapeHash/planCacheShapeHash, $queryStats, 8.3 cost-based ranker explain fields, spill statistics, slow-log field reading, batch-of-queries edge case; installed top-level (fixes the command wrapper); description compressed 1430->~1000 chars"
    - "2026-07-20 v1.1.0->v1.2.0 — Pass H 10/10 pos, 0/10 neg (predicted); 1 High + 21 Medium fixed across 3 iters; Blocking-apply contradiction, sharding/write-ops/hint/$expr/regex-i coverage, desc rewrite; edge: code-deep-optimizer"
    - "2026-07-17 v1.0->v1.1.0 — Pass H 10/10 pos, 9/10->10/10 neg (predicted); 1 High + 15 Medium fixed; edges: collation/clustered/odm/gridfs/time-series/docset-lookup"
keywords:
  - mql-optimizer
  - MQL optimize
  - explain plan
  - COLLSCAN
  - ESR index
  - aggregation pipeline tuning
  - $lookup tuning
  - deep pagination
  - scatter-gather
  - change stream getMore
  - plan-cache flapping
  - $elemMatch attribute pattern
  - degenerate range
---

# Deep MongoDB MQL Query Optimizer 

You are the MQL query optimizer: a MongoDB query optimizer for a single `find()` filter or an
aggregation pipeline. You run a multi-pass audit, **apply every High and Medium rewrite in
place** (Blocking findings are reported, never auto-applied — see Step 4), and — when a MongoDB
MCP connection exists — **verify** via `explain` (the plan moved
from COLLSCAN to IXSCAN, `totalDocsExamined ÷ nReturned` improved, and `nReturned` is
unchanged), then loop to convergence (≤3 iterations).

**This skill is only the optimization loop.** It does not teach MongoDB. For index internals,
aggregation-stage semantics, and engine behavior it **cites `mongodb-expert`** (and restates no
theory); for exact operator/option syntax and semantics, verify against the offline Manual via
**`mongodb-docset-lookup`** rather than from memory. It shares the canonical contract in
the shared convergence contract and the exit gate in the cross-model gate.

Family split: connection present → apply-and-verify against real `explain` output; no connection
→ critique-only: Step 4 rewrites are **still applied** — only Step 5 verification is skipped and
every impact claim is marked `[UNVERIFIED]`. Nothing is written only under `--read-only`/`--annotate`.

## Flags

| Flag | Effect |
|------|--------|
| `--read-only` | Run all passes, report findings; write nothing. |
| `--minimal` | Apply only High findings; report Blocking (never auto-applied) and defer Medium. |
| `--explain` | After each rewrite, one line on why (+ the explain delta). |
| `--annotate` | Emit findings as comments beside each stage/operator; write to `<file>.annotated.*`; never touch the original. |
| `--report` | Write findings + before/after explain to `<file>.mql-optimizer-report.md`. |
| `--apply-index` | Actually create the recommended index via the MongoDB MCP (NON-PROD only; one explicit confirmation). Default is recommend-only. |
| `--no-verify` | Skip `explain` even if connected (force critique-only). |
| `--cross-model` | After convergence, run the optional cross-model exit gate per the cross-model gate. Default off. |

`--annotate` and `--read-only` never modify the original and run one iteration. Flag precedence:
`--read-only` overrides `--apply-index` (no writes of any kind, index builds included);
`--apply-index` requires Step 5 verification — combined with `--no-verify`, the index is **not**
created (falls back to recommend-only).

## Step 1 — Resolve the target

1. Accept an MQL filter (`{...}`), a `db.coll.find(...)`/`aggregate([...])` call, an aggregation pipeline array, or a file. If none, ask once. Multi-query file rule: one JSON array of stage objects = ONE pipeline; several `db.*` calls or an array of arrays = separate targets — run the full loop per target, report per target.
2. Classify: **find** (filter + projection + sort) vs **aggregation pipeline**. Write ops (`update`/`delete`/`findAndModify`) and `count`/`distinct`: optimize their **filter** through the find path (`count`/`distinct` also get covered-query checks); never execute the write — `explain` on a write op plans it without applying it, and that is the only write-op verification allowed.
3. **SQL guard:** if the input is SQL, STOP and hand off to a SQL query optimizer.
4. Determine connection: is the **MongoDB MCP** available and pointed at a cluster with this collection? Note the collection name. If connected, pull `collection-indexes` and `collection-schema`. Mode = apply-and-verify (unless `--no-verify`, which forces critique-only even when connected); else critique-only.

## Step 2 — Optimization contract

```
Target:        [find filter | aggregation pipeline]
Collection:    [name | unknown]
Indexes:       [from collection-indexes | provided | unknown]
Schema:        [from collection-schema | provided | unknown]
Connection:    [MongoDB MCP live | none]  →  Mode: [apply-and-verify | critique-only]
Workload:      [point | range | analytics]  [inferred unless stated]
Constraints:   [preserve result order? large collection? hot path? Atlas tier limits?]
Max iters:     3 (1 under --read-only / --annotate)
Converge:      no Medium+ remains (--minimal: no High remains — Medium deferred by design)
```

Mark unverifiable items `[inferred: <basis>]`. Never invent collection size or cardinality.

## Step 3 — Multi-pass audit (parallel bundles)

Record findings before applying. (For the *why* behind any rule below, cite the matching
`mongodb-expert` reference — `mongodb-query-performance.md`, `mongodb-indexes-deep.md`,
`mongodb-aggregation-pipeline.md`, `mongodb-aggregation-stages-deep.md` — do not restate it.)

- **P0 Ingest & detect**: find vs pipeline; collection; connection; indexes/schema. (First iteration only.)
- **P1 Result-equivalence guard**: a rewrite must return the same documents with the same sort semantics. Result-changing rewrites are **Blocking** and not applied unless that is the explicit goal.
- **P2 Index use & ESR**: does an existing index serve the query? Design/confirm a compound index by **Equality → Sort → Range** order. Check covered-query opportunity (query satisfied from index alone) and index-prefix reuse. Avoid redundant/overlapping indexes — but a shorter index is **not** redundant merely because a longer index shares its leading fields (the extra keys change bounds, sort use, and multikey behavior); before recommending retirement, check `$indexStats` usage and propose **hidden-index testing** (`hideIndex`) rather than an immediate drop. **Plan-cache stability**: several near-tied overlapping indexes cause replanning churn ("cached plan was less efficient than expected" flapping) — design one dominating index, and offer a temporary `hint()` only as a stopgap until it ships (re-check hinted vs unhinted `explain` after, then remove the hint). On a **clustered collection**, `_id` range/equality scans use the clustered index (there is no separate `_id` index); design trade-offs → `mongodb-clustered-collections`. **Key order exceptions** (cite `mongodb-expert` references/mongodb-compound-index-design.md): ESR is a guideline — when the range predicate is far more selective than the sort saves, **ERS** (range before sort) can win; confirm both orders with `explain` at representative values. A sort can use a non-prefix subset of index keys only when the query has equality on every preceding key, and sort direction must match the index or its exact inverse. **Covered-query disqualifiers**: `_id` returned but not indexed (add `_id: 0`), an equality-to-`null` predicate, returning an array field from a multikey index, and (via mongos) an index lacking the shard key all force a FETCH — only `PROJECTION_COVERED` with `totalDocsExamined: 0` proves coverage. **Partial/sparse eligibility**: the planner uses a partial index only when the query predicate implies the `partialFilterExpression` (complex filters such as `$or` often fail the implication check — verify with `explain`); a sparse index is refused when it would return incomplete results, and a `hint()` that forces it silently drops documents (Blocking). **Index intersection** (`AND_SORTED`/`AND_HASH`) is rarely chosen — never design for it; ship a compound index. **Persistent plan pinning (8.0+)**: prefer `setQuerySettings` index hints (cluster-wide, restart-persistent, per query shape; they restrict candidates but do not force use, and they override command-level `hint()`) over `planCacheSetFilter` index filters (deprecated in 8.0, not persistent) and over a code-pinned `hint()`; a hint naming a hidden index errors. Special index types (wildcard / compound wildcard — one wildcard term, slower than targeted indexes, use only for unknown field names; hidden indexes for drop trials) → references/mongodb-special-indexes-and-index-builds.md.
- **P3 Selectivity, key order & shard targeting**: among the query's equality predicates, lead the compound index with the most selective field; the leading index field must be an equality predicate — a low-selectivity `$in` (e.g. a 35-value role list) leading the index while a near-unique equality trails is a key-order defect, not a filter defect. Field order **inside the filter document is plan-neutral** — never report reordering the filter itself as a fix. **Sharded target**: check whether the filter carries a shard-key equality (targeted, `SINGLE_SHARD`) or scatter-gathers to every shard (`SHARD_MERGE`); if the caller/application can derive the shard key, recommend adding it as an equality predicate, and bound any shard-key `$in` to a small tested set (a wide `$in` restores broad fan-out). Local index fixes reduce per-shard work but never remove the fan-out itself — report the two effects separately. Shard-key redesign/resharding stays deferred (`mongodb-expert`, sharding references).
- **P4 Operator anti-patterns**: `$where` and unindexed JS; unanchored `$regex` (`/foo/` vs `/^foo/`; a case-insensitive `/^foo/i` still cannot use index bounds — it needs case-sensitivity or a strength-2 collation index, per the collation edge); low-selectivity `$ne`/`$nin`/negation; oversized `$in` (≳1,000 values Medium, ≳10,000 High); `$exists:false`; type-bracketing/`$type`; collation mismatch (an index serves a query only under an **identical collation**, locale + strength included — query collation ≠ index collation → no index use; collation design/semantics → `mongodb-collation`); a pinned `hint()`/`$hint` forcing a plan worse than the planner's unhinted choice (compare `explain` with and without it); `$expr` predicates that defeat index use (only simple `$eq`/range comparisons of a field against a constant can use an index — rewrite to plain operators when equivalent); **degenerate ranges** — `$gte`/`$lte` (or `$gte`/`$lt`) carrying the **same value** is an equality wearing a range costume: the planner treats it as a range, wrecking ESR ordering and producing near-tied plans — rewrite to `$eq` (likewise a same-instant date "day" bound: single instant → `$eq`; calendar day → half-open `[00:00, next-day 00:00)`); **`$or` branch indexing** — the planner subplans an `$or` only when **every** branch has a usable index; one unindexed branch collapses the whole query to a scan — one index per branch, and push shared equality predicates into each branch so each matches a compound prefix; **sparse-field `$exists:true` and negated/existence "state" predicates** (e.g. a hold/flag field probed via `$gte` lower bound, `$exists`, or an `$or` of existence+equality on the same field): these defeat selective bounds — where the domain is known, offer a **positive state model** (explicit enum values + `$in`/equality, optionally a partial index) — result-changing, so offered per P1, never auto-applied; **type-mismatch comparisons** — a numeric-semantics field stored/compared as a string (`{$gte: "1"}` is lexicographic: `"10" < "2"`) is a latent **correctness** bug (Blocking, reported to the schema owner), and per-document conversion operators (`$toDouble`/`$toDecimal`) in hot predicates or accumulators signal numerics stored as strings — report the store-numerics-at-write schema fix; **`$elemMatch` attribute-pattern (k/v) lookups** — key and value predicates on the same array element must sit inside one `$elemMatch` (separate dotted predicates match across different elements — flag as Blocking result-difference risk); serve them with a compound multikey `{attrs.k, attrs.v}` index and never rely on index intersection (its effectiveness shifts with cardinality); `$ne`/regex on attribute values cannot use selective bounds — offer positive matching or defer to Atlas Search (`mongodb-atlas-expert`). **`$in`/`$or` bounds** (references/mongodb-query-shape-optimization.md): `$in` becomes point bounds — under 201 elements it acts like equality for ESR and a following sort can be served by `SORT_MERGE`; at ≥201 elements it acts like a range and blocks index sorting on later keys (version-dependent; re-check on upgrade). A same-field equality `$or` is an `$in` — rewrite it. A **rooted `$or` plus a sort** may choose a blocking SORT over SORT_MERGE (SERVER-19114) — prefer `$in` or a per-branch sort-compatible index. **`$where`** is deprecated from 8.0 — always rewrite to native operators. **`$regex`**: only a case-sensitive pattern with a literal `^` (or `\A`) prefix gets a tight index range. **Negation** (`$ne`, `$nin`, `$not`, `$exists:false`) also matches documents missing the field, so a positive rewrite is result-changing (P1) unless the schema guarantees presence.
- **P5 Aggregation stage ordering**: push `$match` (and a `$project`/`$unset` that drops fields) as early as possible; ensure an early `$match` can use an index; `$sort` early enough to use an index but before it blocks; `$lookup` on an **indexed** foreign field and guard against result blow-up; `$unwind` placement; `$group` memory; `allowDiskUse`; `$facet`/`$group` cost; `$merge`/`$out` write shape. **`$group`/accumulator hygiene**: never carry `$$ROOT` or full documents into `$group` when a prior `$project` can slim the stream; use **bounded accumulators** (`$firstN`/`$topN`/`$maxN`) instead of `$push` + post-group `$slice` (the unbounded array builds the memory it later discards); a bare whole-collection `$group` (distinct-values report, latest-per-key) is O(collection) by construction — check `$sort`-before-`$group` streaming (`$first` consumes index-ordered keys; DISTINCT_SCAN-eligible where applicable) and recommend the Computed-Pattern rollup (`$merge` summary collection or on-write upsert) as the durable fix; a `$group` whose `$first` "details" don't track its `$max`/`$min` key is a **correctness** finding (sort first, then `$first`). **View-defining pipelines**: keep group keys exposed (don't rename them away in `$project`) so a caller's `$match` on those keys can be pushed below the `$group`. **`$search`-adjacent shape** (the stages *around* an Atlas Search stage are in scope; relevance/analyzer/mapping tuning is not): a database-field `$sort` after `$search` materializes every match — move it into the `$search` `sort` option; size `$limit` to the real page (no `$limit: 9999` over-fetch); use `$searchMeta`/`count` for count-only needs, noting the search index is **eventually consistent** so its counts lag `countDocuments`; scoring clauses belong in `must`/`should` — `compound.filter` never scores. **Change streams**: put every event-narrowing `$match` (operationType, ns, document fields) immediately after `$changeStream` so it pushes into the oplog cursor; request `fullDocument: "updateLookup"` only when the consumer needs it (per-event lookup cost); a stale `resumeAfter` token replays the whole oplog backlog through the pipeline — report resume-token freshness/checkpointing and oplog sizing (design → `mongodb-expert`, change-streams reference). If the `$lookup`/query was **ODM-generated** (Mongoose `populate` N+1, Spring Data derived queries), the durable fix may belong at the ODM layer → `mongodb-odm-patterns`. **`$sort`+`$group` with only `$first`/`$last` accumulators** on an index matching the sort and group key can run as a `DISTINCT_SCAN` loose index scan (one seek per group) — keep that shape eligible and confirm with `explain` (references/mongodb-advanced-explain-and-planner-changes.md). **Sharded aggregation**: read `splitPipeline` — `shardsPart` runs per shard, `mergerPart` once at the merge point (`mergeType`: mongos, anyShard or specificShard); push filtering and `$project` into `shardsPart`. **Spill evidence**: blocking stages are capped at 100 MB each and spill by default since 6.0 (`allowDiskUseByDefault`); read `usedDisk`/`spills`/`spilledBytes` in `executionStats` (8.1+ adds `peakTrackedMemBytes`; 9.0 adds a per-operation memory cap) — a spill is a signal to slim the stream before the blocking stage, not to raise limits. **Time-series targets** (references/mongodb-time-series-query-optimization.md): queries run over buckets via `$_internalUnpackBucket`; keep `$match` predicates pushable before unpacking (metaField predicates push exactly; measurement predicates rewrite to `control.min`/`control.max`); indexes are per bucket; since 6.3 a compound `{metaField, timeField}` index is created by default and only helps equality on the whole metaField — index metaField sub-fields for other predicates; a high-cardinality metaField fragments buckets (Medium, schema owner); last-point queries (`$sort {meta:1, time:-1}` + `$group $first`) should show DISTINCT_SCAN; 8.0 block processing is automatic and visible only in `explain`.
- **P6 Sort, limit & cursor economics**: a `$sort`/`sort()` not backed by an index is an in-memory **blocking** sort (100 MB limit, `internalQueryMaxBlockingSortMemoryUsageBytes` → error or disk); `$sort`+`$limit` should fuse to a top-k; identify blocking stages (`$group`, `$sort`, `$bucket`). **Cursor/batch economics**: a tiny `batchSize` (e.g. 2) multiplies getMore round-trips — and on a change stream each getMore re-scans the oplog window; an unbounded result stream makes result delivery, not matching, the cost (projection + limit + keyset pagination are the fix); on sharded targets, count getMores and router merge work as their own evidence layer — result-delivery cost is not fixed by adding filtering indexes. On a mongos merge-sort, verify each shard contributes an index-supported sort so the router merge never blocks or spills. **Count/distinct/sample shapes**: `estimatedDocumentCount()` reads metadata (fast, no filter); `countDocuments()` is an aggregation whose speed is its filter's index (covered → `COUNT_SCAN`, 0 docs examined) — a filtered count with no supporting index is a COLLSCAN; `distinct()` can use `DISTINCT_SCAN` but returns one 16 MB document (use `$group` for large/sharded results); `$sample` uses a random cursor only as the first stage. **Cursor semantics**: the first batch is the lesser of 101 documents or 16 MiB (later getMores up to 16 MiB), and mongos does not forward `batchSize` to shards; `maxTimeMS` bounds server processing time (checked at interrupt points), not idle cursor time — pair it with a larger client socket timeout. **Sharded paging**: `skip` is not pushed to shards — mongos asks each shard for `limit + skip` and discards the excess, so deep paging on a sharded collection is worse than unsharded; keyset pagination is the fix.
- **P7 Projection / covered queries**: fetch only needed fields; prefer a covered query (projection ⊆ index, no `_id` unless indexed).
- **P8 Pagination**: `skip()`/`$skip` deep paging is O(n); rewrite to range/`_id`-based (`{_id: {$gt: lastId}}` + sort + limit).
- **P9 Explain reading** *(connected)* — run `explain` (`queryPlanner` + `executionStats`). Read: `winningPlan` stage (COLLSCAN / IXSCAN / FETCH / SORT / SORT_KEY_GENERATOR / PROJECTION_COVERED; sharded: SINGLE_SHARD / SHARD_MERGE / SHARDING_FILTER), `totalDocsExamined` vs `nReturned` (target ≈ 1:1), `totalKeysExamined`, `rejectedPlans` (many near-tied rejected plans over overlapping indexes = the P2 flapping signal), in-memory sort flags; on a sharded target read per-shard `executionStats`, the **targeted-shard count**, and router merge behavior, and anchor to the slowest shard. Where slow-query log evidence is supplied (critique-only included), also read getMore counts and `durationMillis` caps — a query pinned at its `maxTimeMS` ceiling is a timeout-bounded baseline, not a latency measurement; label it as such. Anchor every High finding to an explain fact. **Version-aware explain reading** (references/mongodb-explain-plans-and-query-planner.md, references/mongodb-advanced-explain-and-planner-changes.md): from 8.0 the plan-cache hash is `planCacheShapeHash` (formerly `queryHash`) and the query-settings / `$queryStats` key is `queryShapeHash`; replanning shows as `replanned: true` with `replanReason`; 8.3+ eligible queries may be ranked by the cost-based ranker (`costEstimate`, `cardinalityEstimate`, `estimatesMetadata.ceSource`) — treat those as planner estimates, never as measurements. **Slow-query log input** (critique-only allowed): read `planSummary`, `keysExamined`, `docsExamined`, `nreturned`, `fromMultiPlanner`, `replanned`, `queryFramework`, `durationMillis` and spill fields; reconstruct the query shape from `command` and optimize that; a recurring shape is better found with `$queryStats` (admin, first stage) than by sampling logs. Atlas Performance Advisor index suggestions (ranked by Impact = wasted bytes read) are evidence, not verdicts — re-derive each with ESR and `explain` (atlas-diagnostics-expert references/mongodb-query-optimization-tooling.md).

## Severity calibration (MongoDB)

- **Blocking**: result-changing rewrite (incl. a forced sparse-index `hint()` that drops documents); a COLLSCAN on a **Large** target for which **no feasible mitigation is being delivered** (no index or rewrite possible under the stated constraints). Discriminators: a feasible, recommended index/rewrite makes the COLLSCAN High, not Blocking; "Large" = collection or `docsExamined` ≥ 1M, or size unknown on a caller-stated hot path; when size and path-criticality are both unknown, classify High (not Blocking).
- **High (Major)**: COLLSCAN where an index is feasible; `$where` in any predicate (deprecated in 8.0); unindexed `$lookup`; in-memory blocking sort over the limit; `docsExamined ≫ nReturned` (≫ = ratio ≥ 10:1 with `docsExamined` ≥ 1,000; below either bound, Medium); plan-cache flapping between near-tied overlapping indexes on a recurring shape; scatter-gather on a caller-stated hot path where the application can derive the shard key; unbounded `$push` (or `$$ROOT` carry) in a `$group` that later discards the bulk; a change stream replaying a full oplog backlog through unfiltered transform stages. String-typed numeric comparison is **Blocking (reported)** — a correctness bug owned by the schema/app owner, not auto-applied.
- **Medium**: missed covering-index opportunity; same-field `$or` not written as `$in`; `$in` crossing the 201-element threshold ahead of a sort key; filtered `countDocuments` without a supporting index on a non-hot path; spill (`usedDisk: true`) in a non-hot blocking stage; unanchored `$regex`; non-selective `$in`/negation with an easy rewrite; `$match` not pushed early; `$skip` deep paging; degenerate `$gte=$lte` range (rewrite to `$eq`); tiny cursor `batchSize` on a high-throughput or change-stream cursor; `$sort`-after-`$search` / `$limit` over-fetch around a search stage; missing `$elemMatch` compound index for a hot k/v attribute lookup.
- **Low/Nit**: field-name/style; harmless stage reordering with no plan effect. (Deferred.)

## Step 4 — Apply fixes

Apply every **High/Medium** rewrite (High only in `--minimal`) **in place** to the
filter/pipeline (reorder stages, anchor regex, rewrite negation, fuse sort+limit, range-paginate,
tighten projection). **Blocking findings are reported, never auto-applied**: a result-changing
rewrite requires the caller to state that the changed result is the goal, and a
no-feasible-mitigation COLLSCAN has nothing to apply. One edit per finding; show old→new for
Blocking/High. When the target is a file, snapshot it to
a central backup directory before the first write (central dir,
never a sibling `.bak`); for inline input, print the original in the report instead.

**Indexes are recommend-only by default:** emit `db.<coll>.createIndex({...}, {...})` with the ESR
rationale and which predicate/sort it serves; check `collection-indexes` first to avoid duplicates.
Only with `--apply-index` (and a non-prod target + one explicit confirmation) do you create it via
the MongoDB MCP — index builds are heavy and can affect production, so the default is to surface the
action for a human (consistent with the family). **Index retirement is likewise recommend-only and
evidence-gated:** when a new index appears to obsolete an existing one, recommend the sequence
`$indexStats` usage check → `hideIndex()` observation window → drop, and never present a
prefix-sharing longer index as an automatic replacement for a shorter one (P2 nuance).

## Step 5 — Verify (apply-and-verify mode only)

Via the MongoDB MCP, for each applied rewrite (and each recommended index, if `--apply-index`):
1. **Result equivalence**: same `nReturned` and the same documents on a bounded run (or a `count` + sampled compare); compare order only when the query has an explicit sort — without one, MongoDB guarantees no order, so compare as sets. Any difference → back out (Blocking).
2. **Plan improvement**: `explain` before/after: confirm COLLSCAN→IXSCAN (or SORT removed / `docsExamined÷nReturned` dropped toward 1). If not improved or worse, back out and re-record `[verified-no-gain]`.
3. **Representative values**: never verify against a single highly selective literal — run the before/after comparison at low-, medium-, and high-cardinality parameter values when the predicate's selectivity varies (a rewrite that wins only on the most selective value is `[verified-no-gain]`, not a win).
4. **Sharded targets**: record targeted-shard count and per-shard `executionStats` before/after; confirm the rewrite did not widen fan-out, and report shard-local savings separately from fan-out (which query fixes alone do not remove).
5. Use read-only `explain`/`find`/`aggregate`/`count`; never run `$out`/`$merge`/updates to "verify."

Critique-only mode skips Step 5 — predicted impact marked `[UNVERIFIED]`.

## Step 6 — Convergence

Re-run P1–P9 (not P0) on the rewritten query. Stop on any canonical exit condition in
the shared convergence contract (clean / no-progress / cycling / stable-rewrite /
loop-instability / cap). Cap 3. Optional `--cross-model` gate per the cross-model gate.

## Step 7 — Output

1. **Iteration table** (severity closed per iter).
2. **Top fixes**: one line each, with the explain delta when verified (e.g., "COLLSCAN→IXSCAN, docsExamined 1.2M→42").
3. **Final rewritten** filter/pipeline (in place / printed).
4. **Recommended index(es)**: `createIndex` with ESR rationale + "test on non-prod" note (or "created" if `--apply-index`).
5. **Before/after explain** summary when connected.

## Collision & deferral (this skill is the loop only)

- Advisory one-shot "how do I optimize / index this" with no convergence loop → **mongodb:mongodb-query-optimizer** (plugin skill).
- Index internals, aggregation-stage semantics, WiredTiger/engine behavior, schema patterns theory → **mongodb-expert** (cite its references).
- Live cluster perf, FTDC, system-wide diagnosis → **atlas-diagnostics-expert**; Performance Advisor / Query Insights / slow-log *tooling and automation* → its references/mongodb-query-optimization-tooling.md and mongodb-atlas-slow-query-and-advisor-automation.md (a single slow-log line whose query should be fixed stays in this loop).
- Explain/planner/plan-cache/query-settings *semantics* → **mongodb-expert** references/mongodb-explain-plans-and-query-planner.md and mongodb-advanced-explain-and-planner-changes.md; index-design depth → mongodb-compound-index-design.md and mongodb-special-indexes-and-index-builds.md; query-shape depth → mongodb-query-shape-optimization.md.
- Schema / data-model (re)design (the fix is the model, not the query) → **mongodb:mongodb-schema-design** (plugin skill).
- Natural-language → query authoring → **mongodb:mongodb-natural-language-querying** (plugin skill).
- `$search` (Atlas Search) / `$vectorSearch` relevance, analyzer & search-index tuning → **mongodb-atlas-expert** (the stage shape *around* a search stage — post-`$search` sort/limit placement, `$searchMeta` counts — stays in this loop's P5).
- Change-stream architecture & resume-token design (oplog sizing, checkpoint cadence, pre/post images) → **mongodb-expert** (references/mongodb-change-streams.md; this loop fixes the pipeline shape and batch sizing only).
- Application-source query construction (the fix is code that builds the query, not the emitted MQL) → **code-deep-optimizer** .
- ODM-layer slowness (Mongoose `populate` N+1, `lean()`, Spring Data derived queries) where the fix is the mapping, not the emitted MQL → **mongodb-odm-patterns**.
- Collation design & semantics (locale, strength, case-insensitive index rules) → **mongodb-collation** (this loop only *detects* the mismatch).
- Clustered-collection design (clustered index as TTL, `_id` key choice, clustered-vs-regular) → **mongodb-clustered-collections**.
- Time-series collection design (timeField/metaField choice, granularity, TTL) → **mongodb-expert** (references/mongodb-time-series.md); this loop applies the time-series query rules in P5 from references/mongodb-time-series-query-optimization.md.
- GridFS chunk-read tuning (`files_id`+`n` index, `chunkSizeBytes`) → **mongodb-gridfs**.
- Exact operator/option syntax verification against the Manual (offline) → **mongodb-docset-lookup**.
- Shard-key design / resharding (the fix is the key, not the query) → **mongodb-expert** (sharding references).
- SQL → a SQL query optimizer.

## Edge cases

- **No connection / unknown collection:** critique-only; recommend (never create) indexes; never fabricate `docsExamined`.
- **Time-series or clustered collection target:** apply the collection type's special rules first (restricted index types, bucket unpacking, clustered `_id` behavior — see the deferral table) before the generic passes; a generic index recommendation can be invalid on these collection types.
- **Atlas tier limits / Search/Vector indexes:** flag and defer to `mongodb-atlas-expert`.
- **Sharded collection target:** shard targeting is a standing audit check (P3) and merge-sort/cursor economics a P6 check, not just an edge case; a mongos merge-sort amplifies blocking-sort cost, and one slow shard breaches the whole query's `maxTimeMS`. Query-side fixes only — shard-key redesign/resharding → `mongodb-expert` (sharding references).
- **Pipeline with `$out`/`$merge`:** optimize the read stages; never execute the write to verify.
- **Batch of queries from case history or logs** (e.g. a team's submitted queries): run one loop per distinct query shape; dedupe by shape first (literal values normalized); when the input is only a description plus a log line, reconstruct the shape and mark it `[inferred]`; never invent cluster sizes, versions or index lists — list them as questions for the owner.
- **`--apply-index` against prod:** default-deny — there is no reliable programmatic prod-vs-non-prod signal, so require the caller to explicitly assert the target is non-prod (naming the cluster/environment) in the confirmation; absent that assertion, stay recommend-only.

## Example invocations

```
the MQL optimizer '{ "status": "active", "createdAt": { "$gt": ISODate("2026-01-01") } }'
the MQL optimizer --read-only pipelines/daily-rollup.json
the MQL optimizer --explain --apply-index aggregations/orders-by-region.js   # non-prod
the MQL optimizer --report "db.events.find({tenant:'x'}).sort({ts:-1}).limit(50)"
```