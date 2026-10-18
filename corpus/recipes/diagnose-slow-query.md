---
name: diagnose-slow-query
title: Diagnose a slow MongoDB query from signal to root cause
summary: Start from a slow-query signal (Atlas Performance Advisor, profiler or logs), read explain("executionStats") to find the root cause, apply the right fix, and re-verify.
applies_to: [atlas, self-managed]
sources:
  - skills/mongodb-expert/references/mongodb-query-performance.md
  - skills/mongodb-expert/references/mongodb-indexes-deep.md
  - skills/mongodb-expert/references/mongodb-compass.md
  - skills/atlas-diagnostics-expert/references/mongodb-performance-troubleshooting.md
  - skills/atlas-diagnostics-expert/references/mongodb-performance-benchmarking.md
---
# Diagnose a slow MongoDB query from signal to root cause

## When to use
- A user, alert or dashboard says an operation is slow, and you need to find why.
- Performance Advisor, Query Profiler, the profiler collection or the mongod log shows a query shape with a high scanned-to-returned ratio.
- Latency jumped after a deploy, an index change, or data growth.

## Prerequisites (checklist)
- [ ] You can connect with mongosh to the cluster (a secondary is fine for read-only diagnosis if the query is a read).
- [ ] You know the namespace (`mydb.orders`) and ideally the exact filter, sort and projection.
- [ ] You know whether you are on Atlas (Performance Advisor needs an M10 or larger dedicated tier) or self-managed.
- [ ] You have a way to capture a before/after record of the numbers.
- [ ] You will not run profiling level 2 on production.

## Steps

1. **Get the slow-query signal and the exact query shape.** Pick the source that fits your deployment.
   - Atlas: Performance Advisor, then Query Profiler. Look at Average Query Targeting (docs scanned per doc returned) and the Impact score.
     ```
     Atlas UI -> Cluster -> Performance Advisor (or Query Profiler)
     ```
     Expect: a ranked list of slow query shapes and suggested indexes. A targeting score above about 10 means the query reads far more than it returns.
   - Profiler (self-managed or Atlas with profiling enabled):
     ```js
     db.setProfilingLevel(1, { slowms: 200 })
     db.system.profile.find({ ts: { $gt: new Date(Date.now() - 3600000) } }).sort({ millis: -1 }).limit(5)
     ```
     Expect: entries with `ns`, `millis`, `planSummary`, `keysExamined`, `docsExamined`, `nreturned`, `command`.
   - Log: structured JSON logs (4.4+) carry `planSummary`, `durationMillis`, `keysExamined`, `docsExamined`.
     ```bash
     cat mongod.log | jq 'select(.attr.planSummary == "COLLSCAN")'
     ```
     Expect: one line per slow operation that scanned the whole collection.

2. **Look for COLLSCAN and bad ratios in the profiler directly.**
   ```js
   db.system.profile.find({ planSummary: "COLLSCAN" })
   db.system.profile.find({ $expr: { $gt: ["$docsExamined", { $multiply: ["$nreturned", 10] }] } })
   ```
   Expect: the shapes that examine ten or more documents per returned document.

3. **Rule out a one-off blocker: look at live operations and locks.**
   ```js
   db.adminCommand({ currentOp: true, active: true, secs_running: { $gt: 10 } })
   db.serverStatus().globalLock
   ```
   Expect: either nothing unusual (go on to explain) or an operation waiting on locks, or a high `globalLock.currentQueue.total`, which points at concurrency rather than a single query. Use `db.killOp(<opId>)` only for an operation you have confirmed is runaway.

4. **Run explain with execution stats on the exact query.**
   ```js
   db.orders.find({ customerId: "abc123", total: { $gte: 100 } })
     .sort({ createdAt: -1 })
     .explain("executionStats")
   ```
   Expect: a document with `executionStats.nReturned`, `totalKeysExamined`, `totalDocsExamined`, `executionTimeMillis` and a stage tree. Verbosity modes: `queryPlanner` (plan only), `executionStats` (runs the query, adds counts), `allPlansExecution` (also shows rejected plans). Explain output can change between versions.

5. **Read the stage tree and the ratios.**
   | You see | It means | Next move |
   |---|---|---|
   | `COLLSCAN` | No usable index; full collection read | Step 6, add or fix an index |
   | `IXSCAN` then `FETCH`, `totalDocsExamined` much greater than `nReturned` | Index is only partly selective; the rest is filtered after the fetch | Extend the index so the filter fields are in the key |
   | `totalKeysExamined` much greater than `nReturned` | Index key order lets the scan read many entries that fail the range | Reorder with ESR (Equality, Sort, Range) |
   | `SORT` stage | In-memory sort; costs memory and can hit the 100 MB limit | Put the sort field after equality fields in the index, same direction |
   | `totalDocsExamined: 0` and `PROJECTION_COVERED` | Covered query, best case | Nothing to fix |
   | `SHARD_MERGE` or `SHARDING_FILTER` | Sharded plan; look at per-shard `executionStats` | Check whether the query includes the shard key |
   Expect: you can name one root cause from this table. The ideal ratios of `nReturned / totalKeysExamined` and `nReturned / totalDocsExamined` are close to 1.0.

6. **Choose the fix.**
   - Missing or wrong index: design with ESR and build it safely (see the recipe `build-index-safely-in-production`).
     ```js
     db.orders.createIndex({ customerId: 1, createdAt: -1, total: 1 })
     ```
   - Query wants only indexed fields: make it covered by projecting only indexed fields and excluding `_id`.
     ```js
     db.users.find({ email: "user@example.com" }, { name: 1, status: 1, _id: 0 })
     ```
   - Filter touches only a subset: consider a partial index (queries must match the `partialFilterExpression`).
   - Case-insensitive match with a collated query: the index must carry the same collation, or it is ignored and the query falls back to COLLSCAN.
   - Aggregation: put `$match` first, index the `$lookup` `foreignField`, and add `$limit` after `$sort`.
   - Low-selectivity filter (most documents match): the corpus says an index may not help when more than about 20-30% of documents match.
   Expect: one specific change you can test.

7. **Test the candidate index with a hint, without changing application code.**
   ```js
   db.orders.find({ customerId: "abc123", total: { $gte: 100 } })
     .sort({ createdAt: -1 })
     .hint({ customerId: 1, createdAt: -1, total: 1 })
     .explain("executionStats")
   ```
   Expect: `IXSCAN` on the hinted index and lower `totalDocsExamined`. If the planner would not choose it unprompted, the key order is likely wrong.

8. **Apply the change** (build the index, or rewrite the query), using the safe build steps for production.

9. **If the query is still slow after the index exists, check the plan cache.** Plans are cached by query shape and invalidated when indexes are created or dropped.
   ```js
   db.orders.aggregate([{ $planCacheStats: {} }])
   db.orders.getPlanCache().clear()
   ```
   Expect: the next run re-plans and picks the better index. Clear the cache for this collection only, not as a habit.

10. **Re-run explain and compare to the baseline.**
    ```js
    db.orders.find({ customerId: "abc123", total: { $gte: 100 } }).sort({ createdAt: -1 }).explain("executionStats")
    ```
    Expect: `IXSCAN`, no `SORT`, `totalKeysExamined` and `totalDocsExamined` near `nReturned`, lower `executionTimeMillis`.

11. **Confirm in production telemetry.** Watch the slow-query list and Performance Advisor for the same shape over the next day.
    Expect: the shape drops out of the slow list.

## Verify
- Explain for the exact production query shows an index scan and no in-memory `SORT`.
- The profiler or log no longer reports this shape as `COLLSCAN` or with a high `docsExamined` to `nreturned` ratio.
- Atlas Performance Advisor's recommendation for the shape clears, and Average Query Targeting for the shape falls toward 1.
- The p95 latency chart for the operation returns to baseline.
- Write latency has not regressed (new indexes add write cost).

## Rollback / abort
- Index made things worse: `db.orders.hideIndex("<name>")` first, then `dropIndex` once you are sure.
- You set `slowms` very low or profiling level 2 for diagnosis: reset with `db.setProfilingLevel(1, { slowms: 200 })` or `db.setProfilingLevel(0)`.
- A hinted query went into production code: remove the hint; the corpus says `hint()` is not a permanent fix.
- Wrongly killed operation: re-run the application-level retry; killing is not reversible.

## Pitfalls
- Running explain with the default `queryPlanner` verbosity and concluding the plan is fine. It does not run the query, so you get no counts.
- Judging by `executionTimeMillis` alone. The scanned-to-returned ratios are the stable signal.
- Running unfiltered explain on a very large collection. It executes the query.
- Leaving profiling at level 2 on production. It logs every operation and has high overhead.
- Trusting Performance Advisor blindly. It samples only operations above the slow threshold (default 100 ms), is Atlas-only, does not analyse write cost, can suggest redundant prefix indexes, and cannot suggest indexes if the log timestamp format is `ctime`.
- Ignoring the version: `queryHash` is deprecated in 8.0 in favour of `planCacheShapeHash`; index filters are deprecated in favour of query settings. Tools keyed on the old names break.
- A range field before the sort field in the compound index. This is the classic cause of a `SORT` stage.
- Index exists but unusable: collation mismatch, or the query does not match a partial index filter.
- A single member's `$indexStats` or Compass usage counters. They reflect only the node you are connected to.

## Sources
- skills/atlas-diagnostics-expert/references/mongodb-performance-troubleshooting.md:93-100 (diagnostic workflow, explain bypasses plan cache), :119-130 (planner, stages, version drift)
- skills/mongodb-expert/references/mongodb-query-performance.md:155 (ESR), :186 (covered queries), :289 (hint)
- skills/mongodb-expert/references/mongodb-query-performance.md:447-483 (explain modes, executionStats keys, ratios)
- skills/mongodb-expert/references/mongodb-query-performance.md:484-520 (plan cache, `planCacheShapeHash`)
- skills/mongodb-expert/references/mongodb-query-performance.md:653-806 (profiler levels, `system.profile` queries, `$currentOp`, Performance Advisor, log analysis)
- skills/mongodb-expert/references/mongodb-query-performance.md:911-968 (checklists, anti-patterns)
- skills/mongodb-expert/references/mongodb-compass.md:353-395 (stage meanings, SORT is in-memory, explain-driven index creation)
- skills/atlas-diagnostics-expert/references/mongodb-performance-benchmarking.md:386-420 (Performance Advisor tiers, Average Query Targeting, limitations)
- skills/mongodb-expert/references/mongodb-indexes-deep.md:189 (sort direction), :701 (selectivity), :829 (hint caution)
- skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md:250 (`queryHash`, index filters deprecations)
