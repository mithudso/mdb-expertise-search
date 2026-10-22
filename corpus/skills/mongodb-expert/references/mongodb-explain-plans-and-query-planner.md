<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Created by `/dr` deep research 2026-10-19; research dir `<local-path>`.

---
name: mongodb-explain-plans-and-query-planner
description: "MongoDB explain plans, query planner and plan cache: reading explain() stage trees and executionStats counters (nReturned vs totalKeysExamined vs totalDocsExamined), multi-planning and plan-cache lifecycle (replanning, eviction, 8.3 CBR), query shapes (queryShapeHash vs planCacheShapeHash), $queryStats, 8.0 setQuerySettings persistent hints vs deprecated index filters, hint()/$natural, $indexStats unused-index detection, profiler and slow-query log fields (planSummary, slowms), index-effectiveness ratios. TRIGGER: 'read this explain output', 'why did the planner pick this index', 'plan cache stale', 'pin an index across restarts', '$queryStats', 'find unused indexes', 'planSummary in slow query log'. SKIP: index key order/ESR/covering -> mongodb-compound-index-design; query-shape rewrites -> mongodb-query-shape-optimization; fix-loop on one query -> deep-mongodb-mql-query-optimizer; Compass/Atlas UI -> atlas-diagnostics-expert (references/mongodb-query-optimization-tooling.md)."
version: "1.0.0"
updated: "2026-10-19"
category: "research"
whenToUse:
  - "read or interpret a MongoDB explain() plan"
  - "diagnose a bad plan choice or stale plan cache"
  - "pin or force an index with query settings or hint()"
  - "find slow or unindexed queries from logs, profiler or $queryStats"
keywords: ["explain", "executionStats", "query planner", "plan cache", "query shape", "queryStats", "setQuerySettings", "hint", "indexStats", "profiler", "slow query log", "planSummary", "totalKeysExamined", "replanning", "queryShapeHash"]
tags: ["mongodb", "query-optimization", "explain", "plan-cache", "profiling"]
provenance: "/dr · <local-path>"
---

# MongoDB Explain Plans, Query Planner and Plan Cache

## Overview

Reading explain() output means walking the stage tree (COLLSCAN, IXSCAN, FETCH, SORT, PROJECTION) and comparing counters across the three verbosity modes. queryPlanner shows the winning and rejected plans without running them. executionStats runs the winner and reports nReturned, totalKeysExamined, totalDocsExamined and executionTimeMillis. allPlansExecution adds partial trial-phase stats for rejected plans. MongoDB's heuristic: totalDocsExamined far above nReturned means an ineffective index, and equal values mean an effective one. Caveats: keysExamined includes out-of-bounds keys for multi-range scans, executionTimeMillis includes plan-selection time and is not steady-state latency, and slot-based-engine plans nest under winningPlan.queryPlan. Numeric ratio thresholds in the third-party sources are rules of thumb, not official limits.

For each query shape, the MongoDB planner enumerates candidate indexed plans, runs them in a bounded trial (multi-planning), and caches the winner per collection. Later queries with the same shape reuse it and skip planning. Entries move Inactive to Active, are demoted or replanned when the cached plan does much more work than expected, and are cleared by DDL, restart, LRU eviction or manual clear. The cache is in memory and local to each mongod. Stale or flip-flopping plans cause regressions and replanning loops. From 8.3 a cost-based ranker backs up multi-planning for some queries. SBE and classic caches key differently, so SBE can multi-plan more often.

A query shape groups queries that differ only in literal values (filter, sort, projection, pipeline stages, namespace). MongoDB 8.0 added a new query shape identified by queryShapeHash (a hex SHA-style string), and renamed the older plan-cache hash queryHash to planCacheShapeHash. The new shape backs query settings and $queryStats. $queryStats (run on admin, first stage) returns per-shape runtime metrics from an in-memory store capped at 1% of RAM, normalising literal values to types and optionally HMAC-hashing identifiers. The stage is documented as unsupported with an unstable output format. Collection is sampled: 8.x Atlas rate-limits reads to 100/s per host; 9.0 samples 1% of reads and writes. Atlas Query Shape Insights and the Datadog integration consume these metrics.

MongoDB 8.0 added setQuerySettings: a cluster-wide, restart-persistent store of per-query-shape settings (index hints, reject flag, queryFramework, comment) for find, distinct and aggregate. The planner treats them as an extra input; hints restrict the candidate index set but do not force use, and a collection scan can still win. Cluster settings override command-level hints. They replace index filters (planCacheSetFilter), deprecated in 8.0 because filters were not persistent and hard to apply across nodes. Settings are listed with the $querySettings stage and removed with removeQuerySettings; explain output shows a querySettings block. Later versions add comment (8.0.4/8.1), representativeQuery backfill (8.3), queryKnobs and maxTimeMS (9.0). Early bugs (concurrent set/remove invariant) were fixed in 8.0 RCs. Caveat: all sources found are MongoDB-authored; no independent third-party coverage surfaced.

cursor.hint() (and the hint field on find/aggregate/count) overrides MongoDB's planner and forces a named or key-pattern index, or {$natural: 1|-1} for a collection scan. It is not a SQL-style suggestion: the hinted index is the only one used, with no fallback, and it changes results for sparse and partial indexes. A hint on a missing or hidden index errors. Hints cannot be combined with $text, are ignored when an index filter exists, and lose to cluster query settings (8.0+). Used to bypass a stale plan or bad choice, but a hardcoded hint becomes a liability when data or indexes change. Evidence here is thin on independent sources: mostly MongoDB-authored.

$indexStats is an aggregation stage that returns one document per index with accesses.ops (count of user operations that used the index) and accesses.since (when counting began), plus host, shard, spec and a building flag. Zero ops over a long enough window flags a drop candidate, but the counters are per node, reset on restart, collMod, hideIndex and drop/recreate, and exclude TTL deletes and chunk migration. Unique-index enforcement on insert does not count. Safe practice: observe a full workload cycle, query every node (primaries, secondaries, each shard), exclude _id_, check prefix redundancy, hide the index (7.0+ FCV) to trial removal, then drop and watch for COLLSCAN. Independent non-MongoDB coverage is vendor/practitioner blogs (Percona 2018, Netdata) whose caveats mostly agree with the docs.

MongoDB records slow operations in two places: the diagnostic log (a 'Slow query' message) and, if enabled per database, the capped system.profile collection. Both use the same slow threshold (slowms, default 100 ms) and sampling (sampleRate / slowOpSampleRate). Each entry carries planSummary (e.g. COLLSCAN, IXSCAN {a:1}), keysExamined, docsExamined, nreturned, durationMillis and plan-cache hashes. These let you spot missing indexes and wasteful scans without running explain. Profiling costs performance and disk; level 2 is discouraged in production, and mongos has no profiler. Atlas adds a managed dynamic threshold on paid tiers. Nearly all authoritative detail is MongoDB-authored; the independent corroboration is two blogs.

Index effectiveness is judged by comparing three executionStats counters from explain: nReturned, totalKeysExamined and totalDocsExamined. The ideal is keys and docs examined close to nReturned (1:1:1); a COLLSCAN shows totalKeysExamined 0 and docs examined equal to the collection size. MongoDB docs use hint() plus explain('executionStats') to compare candidate indexes by keys scanned. Atlas applies the same ratio server-wide: Query Targeting alerts fire on scanned/returned above 1000:1 by default, and a second alert counts index keys. The ratio is a heuristic: Pythian shows a 1:1 docs ratio with 40k+ keys examined and slower runtime, and Percona shows fewer docs examined but worse time because of an added sort. Treat ratios as a screening signal, then confirm with executionTimeMillis and SORT/FETCH stages. Numeric thresholds other than Atlas's default are community rules of thumb.

## Core Concepts

### Explain Plan Interpretation

- Stage meanings per MongoDB: COLLSCAN is a collection scan, IXSCAN an index scan, FETCH reads full documents, PROJECTION filters returned fields in memory, and SORT means documents were sorted in memory (or a covered index was used). A filter or sort that shows COLLSCAN would benefit from an index; docsExamined appears on COLLSCAN and FETCH stages and keysExamined on IXSCAN.[^c1-2][^c1-1][^c1-4]
- Explain output shape depends on the engine: classic-engine plans put the stage tree at winningPlan.stage with nested inputStage, while slot-based-engine (SBE) plans put it under winningPlan.queryPlan and carry a planNodeId per stage. The docs warn that examples mix both shapes and real output may differ significantly. (two sources)[^c1-1][^c1-2]
- From 8.0 the explain output carries planCacheShapeHash (a copy of queryHash, which is deprecated and slated for removal) and planCacheKey. planCacheKey depends on both the plan cache query shape and the available indexes. (two sources) verified-as-of: 2026-10-14[^c1-1][^c1-2]

### Query Planning and Plan Cache

- Classic multi-planning picks the winner as the plan that returns the most results in the trial period while doing the least work. The winner is stored in the plan cache and reused for queries with the same plan cache query shape.[^c2-1][^c2-2]
- Plan cache entries have three states. Missing: no entry exists, so plans are evaluated and an Inactive placeholder with a work value is created. Inactive: placeholder, not used to generate plans. Active: used to generate plans. A newly selected plan whose work value is less than or equal to the placeholder's replaces it and becomes Active. If the value is greater, the placeholder stays and its value is incremented. An Active entry whose work no longer meets the selection criterion drops to Inactive. (two sources)[^c2-1][^c2-7]
- Any DDL event clears the plan cache for the relevant collection (drop collection; create, delete or hide an index). The cache is in memory only and is lost on mongod restart or shutdown. LRU eviction removes the least recently used entry regardless of state. Manual clearing uses getPlanCache().clear() or clearPlansByQuery().[^c2-1][^c2-2]
- The plan cache is local to each mongod, with no cluster-wide cache. Shards and replica set members can therefore choose different plans for the same shape. (two sources)[^c2-2][^c2-1]
- planCacheShapeHash (new in 8.0, a duplicate of the deprecated queryHash) depends only on query shape. planCacheKey depends on shape and the available indexes, so adding or dropping a supporting index can change planCacheKey but not planCacheShapeHash. (two sources) verified-as-of: 2026-10-18[^c2-1][^c2-2]
- Tentative: Starting in MongoDB 8.3, multi-planning with a cost-based ranker (CBR) backup is the default plan selection mechanism for eligible queries. A short trial looks for a plan that returns a result in time. If that fails, rules decide whether multi-planning continues or CBR ranks the plans by cost function and cardinality estimates. MongoDB currently invokes CBR for only a small number of queries. verified-as-of: 2026-10-18[^c2-1]
- The classic multi-planner's trial is bounded to the larger of 10,000 storage reads or 30% of the collection (internalQueryPlanEvaluationCollFraction). SERVER-62981, fixed in 5.2.1/5.3.0, proposed internalQueryPlanEvaluationCollFractionSbe (default 0, meaning 10,000 reads per candidate) for SBE. The shipped SBE default was not confirmed. (two sources) verified-as-of: 2022-01-27[^c2-4][^c2-7]
- A cached plan is replanned when its re-run trial does more than internalQueryCacheEvictionRatio (reported default 10) times the work of the original trial. In SBE, SERVER-85238 uses this ratio as a multiplier on the winner's totalKeysExamined + totalDocsExamined as the replanning read budget. The default of 10 comes only from a third-party slide deck, not official docs. (two sources) verified-as-of: 2026-10-18[^c2-7][^c2-5]
- Per SERVER-90880, queries run in SBE use the classic plan cache by default; the SBE plan cache is used only when featureFlagSbeFull is on. In 8.0 only $group/$lookup-type queries tend to run in SBE. (two sources) verified-as-of: 2026-10-18[^c2-6][^c2-3]

### Query Shapes and Query Hash and $queryStats

- A query shape groups similar queries by filters, sorts, projections, aggregation pipeline stages and namespace, ignoring literal values; queries with the same specification share one shape.[^c3-2][^c3-1]
- In MongoDB 8.0 the pre-existing query shape was renamed the plan cache query shape and its queryHash field was renamed planCacheShapeHash; the new query shape is identified by queryShapeHash. The two hashes differ in form (queryShapeHash is a 64-char hex string, planCacheShapeHash an 8-char hex string in the docs example).[^c3-2][^c3-5]
- The new 8.0 query shape covers find, distinct and aggregate (the entire pipeline) and powers setQuerySettings, operation rejection filters and $queryStats; the plan cache query shape supports plan caching, deprecated index filters and only a subset of aggregation.[^c3-2][^c3-1]
- Changing any shape component (e.g. the sort field from totalNumber to price) yields a different queryShapeHash and planCacheShapeHash; changing only literal values (dates) does not.[^c3-2][^c3-1]
- $queryStats stores entries in an in-memory virtual collection limited to 1% of system memory. Each entry is keyed by query shape plus client info, read concern and collection type, so one shape can produce several entries; keyHash identifies the entry and queryShapeHash groups entries by shape. (two sources)[^c3-1][^c3-6]

### Query Settings and Persistent Index Hints (8.0)

- setQuerySettings (new in 8.0) defines settings for find, distinct and aggregate commands, applied to all executions of a query shape on the cluster; settings persist across restarts and are retrievable with a $querySettings aggregation stage.[^c4-1][^c4-2]
- Index hints in query settings (indexHints.allowedIndexes: index name, key pattern or $natural) only restrict the indexes available to the planner; they do not guarantee use, and the planner can still pick a collection scan.[^c4-1][^c4-4]
- Cluster query settings take precedence over index hints passed as command fields; MongoDB ignores a command-level hint if a matching query setting already contains index hints. Index hints do not alter the query shape.[^c4-1][^c4-4]
- Index filters (planCacheSetFilter) are deprecated from 8.0; docs say use query settings instead because index filters are not persistent and cannot easily be created for all cluster nodes. verified-as-of: 2026-10-14[^c4-3][^c4-1][^c4-4]

### hint() and Index Forcing

- cursor.hint() overrides MongoDB's default index selection and query optimization; the index is given by name or key specification document, or {$natural: 1} / {$natural: -1} forces a forward or reverse collection scan.[^c5-1][^c5-4]
- If an index filter exists for the query shape, MongoDB ignores hint(). Cluster query settings also take precedence: index hints in command fields are ignored if a matching query setting already contains index hints. Index hints do not affect query shape. verified-as-of: 2026-10-14[^c5-1][^c5-3]
- Tentative: hint() cannot select the index for a query containing a $text expression.[^c5-1]
- Tentative: On time series collections a hint may be given only by index name, not key pattern. verified-as-of: 2026-10-14[^c5-1]
- Tentative: A hinted query skips plan-cache trial and is planned directly from the hinted index (stated by one MongoDB author; not confirmed in official docs).[^c5-3]

### Index Analysis with $indexStats and Unused-Index Detection

- $indexStats takes an empty document ({ $indexStats: {} }), must be the first stage of an aggregation pipeline, is not allowed in transactions, and with access control requires at least the clusterMonitor role. (two sources)[^c6-1][^c6-5]
- Each $indexStats result document carries name, key, host, accesses {ops, since}, spec, and shard (sharded clusters only); building appears only when true and spec.hidden only when true. accesses.ops counts user operations that used the index; accesses.since is when statistics gathering began. (two sources)[^c6-1][^c6-4]
- accesses reports usage only for the node where the query runs, and only user-driven access. TTL-index deletions and chunk split/migration operations do not increment ops. MongoDB documents say to run $indexStats on each node for comprehensive stats.[^c6-1][^c6-3][^c6-4]
- Unneeded indexes cost write performance and cache: every extra index adds work to each write, and in WiredTiger index pages compete with documents for cache. MongoDB recommends $indexStats, Atlas Performance Advisor (M10+) or Compass to find them, then hideIndex before dropping. (two sources)[^c6-3][^c6-5]

### Slow Query Monitoring (profiler and slow-query log and planSummary)

- Profiler level 0 is off, level 1 records operations slower than slowms (or matching a filter), and level 2 records all operations; at level 2 the profiler ignores user-supplied slowms and filter values.[^c7-1][^c7-5]
- The default slowms threshold is 100 ms and default sampleRate is 1.0. slowms and sampleRate are global (all databases in the process); profiling level and filter are per database when set via db.setProfilingLevel() but process-wide when set on the command line or config file.[^c7-1][^c7-5]
- The slow operation threshold is shared by the profiler and the diagnostic log. With logLevel 0, slow operations are logged at a rate set by slowOpSampleRate; at higher log verbosity all operations are logged regardless of latency.[^c7-1][^c7-3]
- Profiling cannot be enabled on mongos. In a sharded cluster, enable it on each mongod. On mongos, slowms, sampleRate and filter affect only the diagnostic log.[^c7-1][^c7-3]

### Index Effectiveness Measurement

- The three explain('executionStats') counters used to judge an index are nReturned, totalKeysExamined and totalDocsExamined. A COLLSCAN shows totalKeysExamined 0 and totalDocsExamined equal to the collection size (21349 docs scanned to return 3809 in the MongoDB docs example).[^c8-1][^c8-3]
- An efficient indexed query examines about as many keys and documents as it returns. In the MongoDB docs example, an index on year gives nReturned = totalKeysExamined = totalDocsExamined = 3809, which the docs call 'a very efficient query'.[^c8-1][^c8-4]

## Tools & Frameworks

- rejectedPlans entries have the same fields as winningPlan. Starting in MongoDB 8.0 they contain only the find portion of the query; before 8.0 they could include aggregation stages such as $group. Partial execution data for winning and rejected plans appears in executionStats.allPlansExecution, present only in allPlansExecution verbosity. (two sources) verified-as-of: 2026-10-14[^c1-1][^c1-2] _(Explain Plan Interpretation)_
- explain ignores existing plan cache entries and does not create a new one. A plan taken from the cache shows isCached: true in explain("executionStats") (per Percona), and fromPlanCache: true in the profiler. (two sources)[^c2-1][^c2-2] _(Query Planning and Plan Cache)_
- Tentative: Full $planCacheStats debug info (createdFromQuery, cachedPlan, creationExecStats, candidatePlanScores) is kept only while total plan cache size across all collections is under 0.5 GB (since 5.0). Since 6.3 the planCacheSize parameter sets the cache size, with a default of 5% of memory (per Percona). verified-as-of: 2026-10-18[^c2-1][^c2-2] _(Query Planning and Plan Cache)_
- Explain exposes queryShapeHash and planCacheShapeHash at the top level; SERVER-91954 added it (fixed in 8.0.4 and 8.1.0-rc0, resolved 2024-09-20). Before that, the hash was only available from the slow query log/profiler or via setQuerySettings plus $querySettings. (two sources) verified-as-of: 2024-09-20[^c3-5][^c3-2] _(Query Shapes and Query Hash and $queryStats)_
- $queryStats must run on the admin database as the first pipeline stage, cannot target a single collection, and needs the queryStatsRead privilege (queryStatsReadTransformed too when using transformIdentifiers); clusterMonitor grants both.[^c3-1][^c3-3] _(Query Shapes and Query Hash and $queryStats)_
- Per-entry metrics include execCount, totalExecMicros, firstResponseExecMicros, docsReturned (sum/max/min/sumOfSquares), and cpuNanos (Linux only, new in 8.2); sumOfSquares exposes variance. Aggregate stage counters are available in the newer output. (two sources) verified-as-of: 2026-10-14[^c3-1][^c3-3] _(Query Shapes and Query Hash and $queryStats)_
- Atlas Query Shape Insights (M10+, MongoDB 8.0+) ranks shapes by total execution time, filterable by host/shard over 7 days; users without PII-viewing roles see only the queryShapeHash instead of the shape. verified-as-of: 2026-10-14[^c3-3][^c3-4] _(Query Shapes and Query Hash and $queryStats)_
- Datadog's Atlas integration streams query shape metrics under the mongodb.atlas.querystats prefix with samplingstrategy (sampled | rate_limited) and samplingrate tags; M10+ only. (two sources) verified-as-of: 2026-10-18[^c3-4][^c3-3] _(Query Shapes and Query Hash and $queryStats)_
- Settings can be set by passing a full find/distinct/aggregate command plus $db, or by passing an existing query shape hash string; the hash is obtainable from $querySettings (queryShapeHash), the profiler, or slow query logs. Hash-created settings lack representativeQuery until 8.3 (FCV 8.3+), which backfills it asynchronously, best effort. (two sources) verified-as-of: 2026-10-14[^c4-1][^c4-2] _(Query Settings and Persistent Index Hints (8.0))_
- The settings document accepts indexHints, queryFramework (classic or sbe), reject, comment (8.0.4 and 8.1+), and in 9.0 queryKnobs (per-shape server parameter overrides, merged not replaced) and maxTimeMS (takes precedence over command-level maxTimeMS). Query knobs are part of the plan cache key; an FCV downgrade from 9.0 removes knobs and they are not restored on re-upgrade. (two sources) verified-as-of: 2026-10-14[^c4-1][^c4-2] _(Query Settings and Persistent Index Hints (8.0))_
- Tentative: Percona PMM can retain index-usage metrics across restarts when the exporter is started with -collect.indexusage (not on by default); as of the 2018 post, the metrics lacked database and collection labels, so collection-level filtering was not possible. Likely outdated. verified-as-of: 2018-11-21[^c6-4] _(Index Analysis with $indexStats and Unused-Index Detection)_
- If a profiling filter is set, slowms and sampleRate no longer apply to the profiler or the diagnostic log. A filter such as { op: 'query', millis: { $gt: 2000 } } controls which operations are profiled and logged.[^c7-1][^c7-3] _(Slow Query Monitoring (profiler and slow-query log and planSummary))_
- Slow-query entries and profiler documents include planCacheShapeHash (duplicate of queryHash since 8.0; queryHash is deprecated) and planCacheKey, to group slow queries by plan cache query shape. planCacheKey changes when supporting indexes are added or dropped; the shape hash does not. verified-as-of: 2026-10-14[^c7-2][^c7-3] _(Slow Query Monitoring (profiler and slow-query log and planSummary))_
- Slow-query log fields have grown by version: queryFramework (6.2), cpuNanos on Linux (6.3), queues and queryShapeHash (8.0), spill metrics (8.1), originalQueryShapeHash, slow in-progress entries via slowOpInProgressThresholdMs and a deadline field (8.3), and queryKnobs (9.0). (two sources) verified-as-of: 2026-10-14[^c7-3][^c7-2] _(Slow Query Monitoring (profiler and slow-query log and planSummary))_
- Atlas dynamically adjusts its slow query threshold by default (used by Performance Advisor and Query Profiler); users can opt out to a fixed 100 ms and MongoDB advises against going lower. Free (M0) clusters have the managed threshold disabled and it cannot be enabled; clusters with MongoDB Search do not support it. Toggling needs Project Owner. (two sources) verified-as-of: 2026-10-14[^c7-4][^c7-1] _(Slow Query Monitoring (profiler and slow-query log and planSummary))_
- Atlas 'Query Targeting: Scanned Objects / Returned' alerts when average documents scanned divided by average documents returned, server-wide over a sampling period, exceeds a threshold. The default threshold is 1000:1 and the docs say the ideal ratio is close to 1. verified-as-of: 2026-10-14[^c8-2][^c8-1] _(Index Effectiveness Measurement)_
- Tentative: Atlas also offers 'Query Targeting: Scanned / Returned', which counts index keys examined relative to documents returned against a user-defined threshold. It is not enabled by default. verified-as-of: 2026-10-14[^c8-2] _(Index Effectiveness Measurement)_

## Methodology

- MongoDB documents a two-counter heuristic for a bad filter: if executionStats.totalDocsExamined is much greater than executionStats.nReturned, the index is ineffective; if the two are equal, MongoDB examined only the documents it returned, which indicates an effective index.[^c1-2][^c1-4] _(Explain Plan Interpretation)_
- Third-party guides add numeric thresholds to the docsExamined/nReturned ratio: Netdata calls 1:1 ideal and above 100:1 severe inefficiency. These figures are blog rules of thumb; the MongoDB docs give no numeric cutoff. (two sources)[^c1-3][^c1-2] _(Explain Plan Interpretation)_
- When totalKeysExamined is far lower than totalDocsExamined, the docs say to inspect each stage in executionStats.executionStages and compare keysExamined with docsExamined per stage to find which stage failed to use the index. A totalKeysExamined of 0 with large totalDocsExamined indicates a pure collection scan. (two sources)[^c1-2][^c1-3] _(Explain Plan Interpretation)_
- $queryStats normalises literal values to types (e.g. {item:'card'} becomes {item:'?string'}) but keeps readConcern/readPreference literal. With transformIdentifiers (algorithm hmac-sha-256, hmacKey) it HMACs field, collection and database names but not operators or parameter names.[^c3-1][^c3-3] _(Query Shapes and Query Hash and $queryStats)_
- Recommended practice: compare explain('executionStats') (totalDocsExamined, executionTimeMillis) for hinted vs unhinted runs; use a hint to work around a stale cached plan or misleading selectivity, not as a permanent fix without addressing the missing or poorly designed index, since a forced index can worsen as data changes. (two sources)[^c5-4][^c5-3] _(hint() and Index Forcing)_
- Detection recipe: run $indexStats then filter accesses.ops equal to 0 (excluding _id_); treat as candidates only after a representative window. Netdata suggests at least 24h uptime under representative load and a full workload cycle if a restart happened after the since timestamp; Percona warns monthly or end-of-day reporting indexes can be missed by short windows. (two sources)[^c6-5][^c6-4] _(Index Analysis with $indexStats and Unused-Index Detection)_
- Tentative: Before dropping, check prefix redundancy (a compound index { a:1, b:1 } serves queries on { a:1 }), and after dropping watch the slow-query log for COLLSCAN and verify critical query shapes with explain('executionStats'), since the planner may switch to a different existing index.[^c6-5] _(Index Analysis with $indexStats and Unused-Index Detection)_
- planSummary is a string in both system.profile documents and slow-query log entries that summarises the winning plan (e.g. 'COLLSCAN' or 'IXSCAN { a: 1, _id: -1 }'). A COLLSCAN with keysExamined 0 and docsExamined far above nreturned signals a missing index; the docsExamined:docsReturned ratio near 1:1 is ideal.[^c7-2][^c7-5] _(Slow Query Monitoring (profiler and slow-query log and planSummary))_
- To compare candidate indexes, run the same query with hint() and explain('executionStats') and compare totalKeysExamined. In the MongoDB docs example, {year:1, rated:1} scanned 246 keys for 235 results while {rated:1, year:1} scanned 235, so the second is more efficient (equality field before range field).[^c8-1][^c8-4] _(Index Effectiveness Measurement)_
- Percona treats the gap between examined and returned counts as the signal: 325 docs examined for 6 returned, and 2517 examined for 493 returned, are called not optimal. A better compound index brings examined equal to returned. (two sources)[^c8-3][^c8-1] _(Index Effectiveness Measurement)_

## Practical Patterns

- A SORT stage means an in-memory sort. In stages that can spill, usedDisk true (added in 5.3) shows the sort went to disk, which is slow; the usual fix is a compound index whose order supports the sort so the SORT stage disappears. (two sources)[^c1-4][^c1-1] _(Explain Plan Interpretation)_
- Mitigations for plan instability: add more selective indexes, avoid generic queries, cap $or/$in value counts, use hint() as a short-term stabilizer, or use 8.0 query settings for a cluster-wide hint. Index filters (planCacheSetFilter) are deprecated from 8.0 in favor of query settings, and they do not persist across shutdown. (two sources) verified-as-of: 2026-10-18[^c2-2][^c2-1] _(Query Planning and Plan Cache)_
- reject: true rejects new matching queries but not in-progress ones. To re-enable, run setQuerySettings with reject:false alongside other settings; a settings document containing only reject:false returns an error, so use removeQuerySettings then set again.[^c4-1][^c4-4] _(Query Settings and Persistent Index Hints (8.0))_
- Tentative: Hinted index is the only index used, with no fallback to another index or collection scan; hinting by key pattern fails when several indexes share that pattern, so hint by name. min() and max() require a hint.[^c5-3] _(hint() and Index Forcing)_
- Hidden indexes let you trial a drop: db.collection.hideIndex() (collMod index.hidden) removes the index from planner selection but keeps maintaining it, so unhide is instant. Requires featureCompatibilityVersion 7.0 or greater per the current manual; the _id index cannot be hidden; needs collMod privilege (dbAdmin). (two sources) verified-as-of: 2026-10-14[^c6-2][^c6-3] _(Index Analysis with $indexStats and Unused-Index Detection)_
- Since MongoDB 5.0, changes to profiler level, slowms, sampleRate or filter are written to the log file. Secondaries also log oplog applications slower than the threshold; the profiler does not capture slow oplog entries. (two sources)[^c7-1][^c7-3] _(Slow Query Monitoring (profiler and slow-query log and planSummary))_
- Tentative: Percona's rule for field order in a compound index is most selective field first; it gives no formal selectivity definition or numeric threshold. MongoDB's docs example instead shows equality-before-range ordering winning, so selectivity alone is not the ordering rule.[^c8-3][^c8-1] _(Index Effectiveness Measurement)_

## Anti-Patterns

- Tentative: A low docsExamined/nReturned ratio does not guarantee a fast query: a non-selective index can be slower than a scan, and a query that returns a large share of the collection may rightly choose a COLLSCAN. IXSCAN with high cost usually points to index selectivity rather than a missing index.[^c1-3] _(Explain Plan Interpretation)_
- Classic caching keys on a broadly parameterized query shape and stores only the index choice. SBE caching keys on a more conservative shape and stores a full SBE plan. SBE does not parameterize arrays, so find({a:'foo',b:[1]}) and find({a:'bar',b:[2]}) share a classic key but not an SBE key, and each new array value causes a miss and another multi-plan. SERVER-89436 (Needs Scheduling, no fix version) proposes layering the classic cache behind the SBE cache. (two sources) verified-as-of: 2026-10-18[^c2-3][^c2-6] _(Query Planning and Plan Cache)_
- The manual warns $queryStats is unsupported and not guaranteed stable; output format may change (9.0 restructured the metrics output), so code should not depend on specific field paths. verified-as-of: 2026-10-14[^c3-1][^c3-4] _(Query Shapes and Query Hash and $queryStats)_
- Tentative: Early 8.0 bugs: SERVER-89118 (setQuerySettings could trip invariant 8758500 under concurrent removal, or removeQuerySettings then setQuerySettings via different mongoses) was fixed in 8.0.0-rc4; SERVER-89340 (setQuerySettings on an aggregate with $bucket failing with error 40199) was closed Won't Fix. verified-as-of: 2026-10-18[^c4-5][^c4-6] _(Query Settings and Persistent Index Hints (8.0))_
- A hinted sparse index is used even when it would omit documents: the planner normally avoids a sparse index that gives incomplete results, but an explicit hint forces it and the query returns only documents containing the field. A hinted countDocuments with an empty predicate on a sparse index returns an incorrect count.[^c5-2][^c5-3] _(hint() and Index Forcing)_
- Tentative: Hinting a partial index limits results to documents matching its filter expression; the index becomes part of the query's semantics.[^c5-3] _(hint() and Index Forcing)_
- Tentative: Hint is applicable beyond find(): aggregate takes it as an options field, and update/delete/count accept it; a hardcoded hint naming a dropped or renamed index becomes a hard failure.[^c5-4] _(hint() and Index Forcing)_
- Zero ops can be a false negative for unique indexes: a uniqueness check on insert does not increment the ops counter, so an unused-for-reads unique index still enforces a constraint and must not be dropped on stats alone. (two sources)[^c6-4][^c6-5] _(Index Analysis with $indexStats and Unused-Index Detection)_
- MongoDB warns the profiler can degrade performance and disk use, especially at level 2 or with a low slowms at level 1, and points to Atlas Query Profiler / Performance Advisor as alternatives. Blogs advise level 1 with a tuned slowms and a lowered sampleRate on busy systems; avoid level 2 in production.[^c7-1][^c7-5][^c7-6] _(Slow Query Monitoring (profiler and slow-query log and planSummary))_
- A 1:1 docs-examined to returned ratio does not prove an index is cheap. Pythian's index {certificate_number, address.zip, date} had docs examined equal to returned but over 40k keys examined, and execution time rose 10% versus no index, because the range field came first and the zip filter ran after the fetch. (two sources)[^c8-4][^c8-1] _(Index Effectiveness Measurement)_
- Fewer documents examined does not guarantee a faster query. Percona's sort example examined fewer documents but ran slower because an extra in-memory SORT stage was needed; Pythian's final index (129 keys vs 82) removed the SORT stage at the cost of a worse key ratio and ran 3 ms vs 2 ms. Check execution time and SORT stages alongside the ratios. (two sources)[^c8-3][^c8-4] _(Index Effectiveness Measurement)_

## Troubleshooting

- keysExamined counts both in-bounds and out-of-bounds keys. When index bounds have several key ranges, the scan examines out-of-bounds keys to skip from one range to the next, so keysExamined can exceed the matching key count without the index being bad.[^c1-1][^c1-4] _(Explain Plan Interpretation)_
- executionStats.executionTimeMillis covers plan selection (including the trial phase) plus execution, excludes network transfer, and is not necessarily representative of real query time: with a cached plan or cursor.hint(), plan selection is bypassed and actual time is lower than the reported value.[^c1-1][^c1-2] _(Explain Plan Interpretation)_
- Tentative: A replanning loop occurs when data changes faster than the planner adapts. Causes: data-dependent filter values, non-selective indexes, near-tied plans, rapid cardinality change (bulk insert/delete, TTL, capped overwrite), and $or/$in/$regex with variable item counts. Diagnose with slow-log fields replanned: true, replanReason, planningTimeMicros, fromMultiPlanner, queryHash and planCacheKey. verified-as-of: 2026-04-13[^c2-2] _(Query Planning and Plan Cache)_
- The docs state queryShapeHash is derived from the shape itself and is expected to be identical on every node and on replica sets vs sharded clusters in current versions, but advise verifying before reusing it across clusters, versions or after migration. (two sources) verified-as-of: 2026-10-14[^c3-2][^c3-5] _(Query Shapes and Query Hash and $queryStats)_
- Sampling differs by version: Atlas on 8.x records up to 100 read queries/s per host and no writes; from MongoDB 9.0 $queryStats samples 1% of reads and writes by default (internalQueryStatsSampleRate, internalQueryStatsWriteCmdSampleRate, 0.0-1.0). Infrequent shapes may be missing and totals jump after an 8.x to 9.0 upgrade. verified-as-of: 2026-10-14[^c3-1][^c3-3][^c3-4] _(Query Shapes and Query Hash and $queryStats)_
- Tentative: In sharded clusters (new in 8.3) mongod and mongos each record query stats and shards also record stats for queries originating at mongos. Change-stream stats update on cursor creation, getMore and close. verified-as-of: 2026-10-14[^c3-1] _(Query Shapes and Query Hash and $queryStats)_
- Tentative: Historical bugs: $queryStats on mongos could fail if the stats store did not fit in memory because the sort could not spill (SERVER-93832, fixed 8.0.4/8.1.0-rc0); memory mis-accounting in the store was fixed in 7.3.0-rc0 (SERVER-84298). verified-as-of: 2026-10-18[^c3-7] _(Query Shapes and Query Hash and $queryStats)_
- Verify applied settings via explain: queryPlanner output includes a querySettings block (indexHints, queryFramework, comment) and indexFilterSet:false; $querySettings with showDebugQueryShape:true also returns debugQueryShape for the shape. (two sources)[^c4-1][^c4-2] _(Query Settings and Persistent Index Hints (8.0))_
- setQuerySettings and $querySettings are not supported on Atlas M0 and Flex clusters; they are available on Atlas, Enterprise and Community. verified-as-of: 2026-10-14[^c4-1][^c4-2] _(Query Settings and Persistent Index Hints (8.0))_
- Hinting a hidden index or an index that does not exist returns an error rather than being ignored; the server error text is 'bad hint'. (two sources)[^c5-1][^c5-5] _(hint() and Index Forcing)_
- Tentative: Since MongoDB 7.0, passing any $natural hint value other than 1 or -1 returns an error; earlier versions accepted invalid values such as 0, NaN, 'X' and -0.01. verified-as-of: 2026-10-14[^c5-1] _(hint() and Index Forcing)_
- Index statistics reset on mongod restart, on index drop and recreation, and on any collMod modification of the index. Hiding an unhidden index also resets its $indexStats, so a hide-then-measure window starts at the hide time.[^c6-1][^c6-2][^c6-5] _(Index Analysis with $indexStats and Unused-Index Detection)_
- On sharded clusters $indexStats is local to each shard primary and a mongos does not aggregate it; an index can show zero on one shard and serve queries on another, so sum accesses.ops across all shards before calling an index unused (Netdata's guide; MongoDB docs state the per-node scope). (two sources)[^c6-5][^c6-1] _(Index Analysis with $indexStats and Unused-Index Detection)_
- Profiler output goes to system.profile, a capped collection per database with a default size of 1 MB (roughly several thousand documents). To resize it, disable profiling, drop it, recreate it with db.createCollection('system.profile', {capped:true, size:N}), then re-enable profiling.[^c7-1][^c7-6] _(Slow Query Monitoring (profiler and slow-query log and planSummary))_
- If keysExamined is much higher than nreturned, the query scans many index keys; consider adjusting the index. For writes, keysExamined and docsExamined include reads from write-conflict retries, so they can exceed documents matched or modified. (two sources)[^c7-2][^c7-3] _(Slow Query Monitoring (profiler and slow-query log and planSummary))_
- planSummary alone does not show whether planning was expensive. Profiler entries carry fromMultiPlanner (true only when multiple candidate plans were evaluated) and replanned (true only when a cached plan was evicted and re-evaluated); both are omitted when false, e.g. for plan-cache hits. (two sources)[^c7-2][^c7-7] _(Slow Query Monitoring (profiler and slow-query log and planSummary))_
- Tentative: Before MongoDB 7.0.22, 8.0.5 and 8.1.0, planningTimeMicros could include pre-retry work such as a sharding metadata refresh, so it should not be used alone to judge planning cost. verified-as-of: 2026-10-14[^c7-2] _(Slow Query Monitoring (profiler and slow-query log and planSummary))_
- Tentative: The Atlas docs' worked example: a log line with planSummary COLLSCAN, keysExamined 0, docsExamined 10000, nreturned 4 gives a ratio of 2500. Atlas names a missing index or an index that only partially supports the query as the typical cause, and recommends Performance Advisor, Query Shape Reports and Query Targeting metrics for follow-up. verified-as-of: 2026-10-14[^c8-2] _(Index Effectiveness Measurement)_
- Tentative: MongoDB's docs warn that explain plan results are subject to change between MongoDB versions, so stored ratio baselines should be re-measured after upgrades. verified-as-of: 2026-10-14[^c8-1] _(Index Effectiveness Measurement)_

## Disagreements & Open Questions

- Disagreement (Explain Plan Interpretation): The Explain Slow Queries tutorial says totalDocsExamined should not exceed totalKeysExamined, while the explain-results reference says keysExamined includes out-of-bounds keys, so a key count above the match count is normal for multi-range scans. The simple key/doc comparison is a screen, not a verdict.[^c1-2][^c1-1]
- Disagreement (Explain Plan Interpretation): Netdata's 100:1 severity cutoff and OneUptime's examples are not backed by MongoDB documentation, which gives only 'much greater' versus 'equal'.[^c1-3][^c1-2]
- Open (Explain Plan Interpretation): Exact conditions that make a query run on SBE rather than the classic engine, and how this changes the interpretation of stage-level counters.
- Open (Explain Plan Interpretation): Whether per-stage works/advanced/needTime counters have documented thresholds for diagnosing a bad plan.
- Open (Explain Plan Interpretation): Covered-query detection (docsExamined 0 with IXSCAN and no FETCH) was not verified in an official source in this run.
- Disagreement (Query Planning and Plan Cache): The official docs page describes only Active-to-Inactive demotion and does not state the eviction-ratio replanning rule. The replanning threshold (10x) is documented only in a third-party slide deck and the SBE Jira ticket. Percona describes replanning as deviation of a different order of magnitude, and its log example shows 2 works expected vs at least 20 observed.[^c2-1][^c2-7][^c2-2]
- Open (Query Planning and Plan Cache): Current official defaults for internalQueryCacheEvictionRatio and internalQueryPlanEvaluationWorks (not confirmed from the server parameters reference).
- Open (Query Planning and Plan Cache): Shipped default of internalQueryPlanEvaluationCollFractionSbe.
- Open (Query Planning and Plan Cache): Whether featureFlagSbeFull or SBE plan cache behavior changed in 8.1-8.3.
- Open (Query Planning and Plan Cache): Which queries are 'eligible' for the 8.3 CBR backup, and its work thresholds.
- Open (Query Planning and Plan Cache): The Alibaba Cloud docs page returned empty on fetch, so it was not used.
- Disagreement (Query Shapes and Query Hash and $queryStats): Docs describe rate limiting as unlimited by default while a 2024 Jira ticket reported internalQueryStatsRateLimit defaulted to -1 (logging stopped); 9.0 docs now describe 1% sampling default, so the default capture state is version-dependent.[^c3-1]
- Open (Query Shapes and Query Hash and $queryStats): Whether currentOp output carries queryShapeHash in 8.0 (not confirmed).
- Open (Query Shapes and Query Hash and $queryStats): Exact 8.0.x/8.1 status of default $queryStats capture on self-managed deployments (docs say Atlas M10+ enablement).
- Open (Query Shapes and Query Hash and $queryStats): SERVER-84298 and SERVER-93832 were read only via search snippets, not fetched.
- Open (Query Settings and Persistent Index Hints (8.0)): No independent (non-MongoDB) source found: web searches returned only MongoDB docs and Jira; all claims rest on one organisation.
- Open (Query Settings and Persistent Index Hints (8.0)): How a command-level cursor hint interacts with reject:true is not documented in sources read.
- Open (Query Settings and Persistent Index Hints (8.0)): Exact FCV/version gating of representativeQuery backfill and queryKnobs beyond docs wording (8.3, 9.0) is unverified against release notes.
- Disagreement (hint() and Index Forcing): PyMongo docs once claimed a hint on a nonexistent index is a no-op; the server returns 'bad hint' errors (ticket reported against drivers, since fixed).[^c5-6][^c5-5]
- Open (hint() and Index Forcing): Depth contract missed: only oneuptime.com is independent of MongoDB (docs, DEV post by a MongoDB author, Jira); no independent measurement of hint() slowdowns.
- Open (hint() and Index Forcing): Whether hinted queries bypass plan-cache trial is confirmed only by one blog; no official statement found.
- Open (hint() and Index Forcing): Jira ticket contents (SERVER-18411, PYTHON-1615) were seen only via search snippets, not fetched.
- Open (hint() and Index Forcing): Behaviour of count with a bad hint and empty filter (SERVER-14792) in current versions is unverified.
- Disagreement (Index Analysis with $indexStats and Unused-Index Detection): Netdata sets a 24h-uptime threshold for zero-ops candidates; Percona and the MongoDB docs give no number and say the window must cover the full application cycle (monthly/weekly jobs), so 24h is a floor, not a safe window.[^c6-5][^c6-4]
- Open (Index Analysis with $indexStats and Unused-Index Detection): Search snippets (not fetched pages) claimed secondary-read workloads need $indexStats run on secondaries via read preference; the MongoDB docs only say per-node, so replica-set secondary handling is unverified beyond the per-node warning.
- Open (Index Analysis with $indexStats and Unused-Index Detection): Whether queries using hint() or covered queries register in accesses.ops was not addressed by any source found.
- Open (Index Analysis with $indexStats and Unused-Index Detection): Jira SERVER-44478 (request for a manual counter reset) appeared in search only; its current status was not fetched.
- Open (Index Analysis with $indexStats and Unused-Index Detection): Negation round found no source contradicting the headline claims; it only scoped them (false zeros for unique indexes, restarts, per-node scope).
- Open (Slow Query Monitoring (profiler and slow-query log and planSummary)): Independent corroboration is limited to two blogs (Netdata, OneUptime); no non-MongoDB, non-blog primary source such as a research paper or third-party vendor doc was found.
- Open (Slow Query Monitoring (profiler and slow-query log and planSummary)): SERVER-18468 was not fetched; its claims come from a search summary, so the fromMultiPlanner Jira detail is backed by the profiler doc page only.
- Open (Slow Query Monitoring (profiler and slow-query log and planSummary)): Negation round found no source contradicting the headline claims. Search did not find documented cases of planSummary misleading, nor Atlas Query Profiler specifics beyond the Performance Advisor page.
- Open (Slow Query Monitoring (profiler and slow-query log and planSummary)): The OneUptime post advice (slowms 2-5x typical latency) is opinion, not MongoDB guidance.
- Disagreement (Index Effectiveness Measurement): Percona advises most-selective field first in a compound index; MongoDB's docs example favours the equality field (rated) before the range field (year) regardless of selectivity.[^c8-3][^c8-1]
- Open (Index Effectiveness Measurement): Community docsExamined/nReturned cutoffs (good under 5, investigate above 10, problem above 100) appear only in OneUptime blog posts (2026-03) that were not fetched; no official MongoDB source gives them, apart from the Atlas 1000:1 default alert.
- Open (Index Effectiveness Measurement): Percona and Pythian posts are dated (2018 and undated); behaviour on MongoDB 8.x with the slot-based execution engine was not verified.
- Open (Index Effectiveness Measurement): Whether the Performance Advisor uses a documented effectiveness metric beyond slow-query threshold plus ratio was not checked.

## References

### Explain Plan Interpretation

[^c1-1]: https://www.mongodb.com/docs/manual/reference/explain-results/ — Explain Results (docs)
[^c1-2]: https://www.mongodb.com/docs/manual/tutorial/explain-slow-queries/ — Explain Slow Queries (docs)
[^c1-3]: https://www.netdata.cloud/guides/mongodb/mongodb-slow-query-collscan/ — MongoDB slow query COLLSCAN: collection scans and the missing index (blog)
[^c1-4]: https://oneuptime.com/blog/post/2026-03-31-mongodb-read-executionstats-output-explain/view — How to Read the executionStats Output in MongoDB explain() (blog)

### Query Planning and Plan Cache

[^c2-1]: https://www.mongodb.com/docs/current/core/query-plans/ — MongoDB query plans (docs)
[^c2-2]: https://www.percona.com/blog/mongodb-query-plan-cache-explained-performance-pitfalls-and-re-planning/ — Percona: MongoDB query plan cache explained (blog)
[^c2-3]: https://jira.mongodb.org/browse/SERVER-89436 — SERVER-89436 multi-planning SBE vs classic (repo)
[^c2-4]: https://jira.mongodb.org/browse/SERVER-62981 — SERVER-62981 trial period bounds (repo)
[^c2-5]: https://jira.mongodb.com/browse/SERVER-85238 — SERVER-85238 SBE replanning (repo)
[^c2-6]: https://jira.mongodb.com/browse/SERVER-90880 — SERVER-90880 SBE plan cache (repo)
[^c2-7]: https://www.slideshare.net/slideshow/query-planner-88498371/88498371 — Nieto: Query planner slides (Percona) (blog)

### Query Shapes and Query Hash and $queryStats

[^c3-1]: https://www.mongodb.com/docs/manual/reference/operator/aggregation/queryStats/ — $queryStats (aggregation stage) (docs)
[^c3-2]: https://www.mongodb.com/docs/manual/core/query-shapes/ — Query Shapes (docs)
[^c3-3]: https://www.mongodb.com/docs/atlas/query-shape-insights/ — Atlas Query Shape Insights (docs)
[^c3-4]: https://docs.datadoghq.com/integrations/mongodb-atlas/ — Datadog MongoDB Atlas integration (docs)
[^c3-5]: https://jira.mongodb.org/browse/SERVER-91954 — SERVER-91954 expose queryShapeHash in explain (repo)
[^c3-6]: https://jira.mongodb.org/browse/SERVER-84298 — SERVER-84298 query stats store memory accounting (from search snippet) (repo)
[^c3-7]: https://jira.mongodb.com/browse/SERVER-93832 — SERVER-93832 mongos queryStats sort spill (from search snippet) (repo)

### Query Settings and Persistent Index Hints (8.0)

[^c4-1]: https://www.mongodb.com/docs/manual/reference/command/setQuerySettings.md — setQuerySettings (database command) (docs)
[^c4-2]: https://www.mongodb.com/docs/manual/reference/operator/aggregation/querySettings.md — $querySettings (aggregation stage) (docs)
[^c4-3]: https://www.mongodb.com/docs/manual/reference/command/planCacheSetFilter.md — planCacheSetFilter (docs)
[^c4-4]: https://www.mongodb.com/docs/manual/release-notes/8.0.md — Release Notes for MongoDB 8.0 (docs)
[^c4-5]: https://jira.mongodb.org/browse/SERVER-89118 — SERVER-89118 setQuerySettings invariant on concurrent removal (forum)
[^c4-6]: https://jira.mongodb.org/browse/SERVER-89340 — SERVER-89340 setQuerySettings fails on $bucket (forum)

### hint() and Index Forcing

[^c5-1]: https://www.mongodb.com/docs/manual/reference/method/cursor.hint.md — cursor.hint() (mongosh method) (docs)
[^c5-2]: https://www.mongodb.com/docs/current/core/index-sparse/ — Sparse indexes (docs)
[^c5-3]: https://dev.to/mongodb/hint-in-mongodb-is-different-that-sql-optimizer-hints-they-force-indexes-4c33 — hint() in MongoDB is different than SQL optimizer hints: they force indexes (blog)
[^c5-4]: https://oneuptime.com/blog/post/2026-03-31-mongodb-hint-force-index/view — How to Use hint() to Force an Index in MongoDB (blog)
[^c5-5]: https://jira.mongodb.org/browse/SERVER-18411 — bad hint when using named indexes (forum)
[^c5-6]: https://jira.mongodb.org/browse/PYTHON-1615 — Cursor.hint doc says a bad hint is a no-op (forum)

### Index Analysis with $indexStats and Unused-Index Detection

[^c6-1]: https://www.mongodb.com/docs/manual/reference/operator/aggregation/indexStats/ — $indexStats (aggregation stage) (docs)
[^c6-2]: https://www.mongodb.com/docs/manual/reference/method/db.collection.hideIndex/ — db.collection.hideIndex() (mongosh method) (docs)
[^c6-3]: https://www.mongodb.com/docs/manual/data-modeling/design-antipatterns/unnecessary-indexes/ — Remove Unnecessary Indexes (docs)
[^c6-4]: https://www.percona.com/blog/identifying-unused-indexes-in-mongodb/ — Identifying Unused Indexes in MongoDB (Percona, 2018-11-21) (blog)
[^c6-5]: https://www.netdata.cloud/guides/mongodb/mongodb-unused-indexes/ — Netdata: MongoDB unused indexes (blog)

### Slow Query Monitoring (profiler and slow-query log and planSummary)

[^c7-1]: https://www.mongodb.com/docs/manual/tutorial/manage-the-database-profiler/ — Database Profiler (MongoDB manual) (docs)
[^c7-2]: https://www.mongodb.com/docs/manual/reference/database-profiler/ — Database Profiler Output (MongoDB manual) (docs)
[^c7-3]: https://www.mongodb.com/docs/manual/reference/log-messages/ — MongoDB Log Messages (manual) (docs)
[^c7-4]: https://www.mongodb.com/docs/atlas/performance-advisor/ — Monitor and Improve Slow Queries with the Performance Advisor (docs)
[^c7-5]: https://www.netdata.cloud/guides/mongodb/mongodb-slow-query-collscan/ — MongoDB slow query COLLSCAN guide (Netdata) (blog)
[^c7-6]: https://oneuptime.com/blog/post/2026-03-31-mongodb-slowms-samplerate-production-profiling/markdown — How to Use slowms and sampleRate for Profiling in Production MongoDB (OneUptime, 2026-03-31) (blog)
[^c7-7]: https://jira.mongodb.org/browse/SERVER-18468 — SERVER-18468 fromMultiPlanner / replanned in slow log (search-result summary only) (forum)

### Index Effectiveness Measurement

[^c8-1]: https://www.mongodb.com/docs/manual/tutorial/analyze-query-plan/ — Interpret Explain Plan Results (docs)
[^c8-2]: https://www.mongodb.com/docs/atlas/reference/alert-resolutions/query-targeting/ — Atlas: Fix Query Issues (Query Targeting) (docs)
[^c8-3]: https://www.percona.com/blog/2018/09/06/mongodb-investigate-queries-with-explain-index-usage-part-2/ — Percona: Investigate Queries with explain() - Index Usage Part 2 (2018) (blog)
[^c8-4]: https://www.pythian.com/blog/choosing-best-index-mongodb-query — Pythian: Choosing best index for your MongoDB query (blog)
