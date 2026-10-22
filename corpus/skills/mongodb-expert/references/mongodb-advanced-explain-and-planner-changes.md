<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Created by `/dr` deep research 2026-10-19; research dir `<local-path>`.

---
name: mongodb-advanced-explain-and-planner-changes
description: "Advanced MongoDB explain output and query-planner behaviour — spill statistics in explain, sharded explain, DISTINCT_SCAN, the 8.3 cost-based ranker: aggregation spill statistics (usedDisk/spilledBytes, 8.1 peakTrackedMemBytes, 9.0 per-op memory cap), sharded explain (SHARD_MERGE root with winningPlan.shards, splitPipeline shardsPart/mergerPart, mergeType), the $sort+$group $first/$last loose index scan (DISTINCT_SCAN, SERVER-9507/37304) and 8.3 multi-planning with the cost-based ranker (costEstimate/cardinalityEstimate, 9.0 knobs). TRIGGER: 'spill stats in explain', 'which shards did my query hit', 'splitPipeline mergerPart', 'DISTINCT_SCAN for $group $first', 'cost-based ranker 8.3', 'costEstimate in explain'. SKIP: basic explain/plan cache/hint -> mongodb-explain-plans-and-query-planner; sort/pagination/operator rewrites -> mongodb-query-shape-optimization; shard-key design -> mongodb-sharding; time-series DISTINCT_SCAN -> mongodb-time-series-query-optimization."
version: "1.0.0"
updated: "2026-10-19"
category: "research"
whenToUse:
  - "read spill or memory statistics in aggregation explain"
  - "see which shards and merge location a sharded query used"
  - "get DISTINCT_SCAN for a sort-group-first pipeline"
  - "understand cost-based ranking fields in an 8.3+ explain"
keywords: ["spill statistics", "usedDisk", "spilledBytes", "allowDiskUseByDefault", "SHARD_MERGE", "splitPipeline", "mergerPart", "shardsPart", "DISTINCT_SCAN", "loose index scan", "$group $first", "cost-based ranker", "CBR", "costEstimate", "cardinalityEstimate", "MongoDB 8.3"]
tags: ["mongodb", "explain", "aggregation", "sharding", "query-planner", "8.3"]
provenance: "/dr · <local-path>"
---

# MongoDB Advanced Explain: Aggregation, Sharded Plans, Loose Index Scans and the 8.3 Cost-Based Ranker

## Overview

Blocking aggregation stages ($group, $sort, $bucket, $bucketAuto, $setWindowFields, $sortByCount) are limited to 100 MB of RAM per stage. Since 6.0 allowDiskUseByDefault is true, so they spill to temporary files instead of failing. In executionStats or allPlansExecution explain, spill-capable stages report usedDisk, spills, spilledBytes, spilledRecords and spilledDataStorageSize; 8.1 added peakTrackedMemBytes and 9.0 adds a per-operation memory cap plus expressionEvaluationPeakMemoryBytes. $lookup reports its own execution stats since 5.0, and spill metrics only when the slot-based engine runs it. Hash-based $lookup spilling is rare by design and was the subject of CVE-2026-4358. $push and $addToSet inside $group have separate 100 MB accumulator caps that do not spill, so allowDiskUse does not rescue them.

When an aggregation or find runs against a sharded collection, explain shows how work was divided. Find-style explain uses a SHARD_MERGE root stage whose winningPlan.shards array holds one entry per accessed shard (shardName, connectionString, per-shard plan and, with executionStats, per-shard executionStages). Aggregation explain shows a splitPipeline with shardsPart (stages run on every shard) and mergerPart (stages run once after), a mergeType (mongos or anyShard in the documented examples, plus specificShard/router per search summaries), and a shards section. Merge placement: mongos by default; a random shard when allowDiskUse is on and blocking stages exist; the shard owning the unsharded/output collection for $lookup/$out (older docs say primary shard); and no split at all when an exact shard-key $match targets one shard. Merge-sort visibility via $mergeCursors was restored in explain in 5.3. MongoDB says explain format is for humans and may change between releases.

When an aggregation pipeline has $sort followed by $group whose accumulators are only $first (or only $last), and an index matches the sort and group key, the planner can replace a full index scan with a DISTINCT_SCAN that seeks to roughly one index entry per group (a loose index scan / skip scan), then FETCHes only the needed documents. SERVER-9507 added it (4.1.4); SERVER-37304 added $last by scanning in reverse (6.3). Explain shows a DISTINCT_SCAN stage with keysExamined near the group count. Limits: the group key cannot be multikey, a prior bug (SERVER-97238, fixed 8.1.0) mishandled array projections, $unwind in front blocks it, and the index sort order forces result order, so recency ordering needs a second $sort after $group. A backlog proposal (SERVER-85213) would rewrite to $top/$bottom instead.

MongoDB 8.3 (GA May 2026) makes multi-planning with a cost-based ranker (CBR) backup the default plan selection for eligible queries. The classic multi-planner runs a short trial; if it cannot settle, rules decide whether it continues or CBR scores each plan node with a cost function and cardinality estimates and picks the lowest cost. Docs say CBR is currently invoked for only a small number of queries. Explain gains costEstimate, cardinalityEstimate, numKeysEstimate, numDocsEstimate and estimatesMetadata.ceSource (8.3.3+), plus serverStatus metrics.query.cbr and $queryStats metrics. Both rankers share the plan cache. 9.0 adds no documented ranker change; its planner-relevant additions are per-command querySettings, queryKnobs and per-shape maxTimeMS. Third-party sources flag CBR as the main upgrade regression risk, but no measured benchmark exists.

## Core Concepts

### Aggregation Explain and Spill Statistics ($lookup and $group and memory limits)

- Since MongoDB 6.0 the allowDiskUseByDefault parameter decides whether stages needing more than 100 MB of memory write temporary files (true) or raise an error (false). Per-command {allowDiskUse: true|false} overrides it. verified-as-of: 2026-10-14[^c1-1][^c1-3]
- Stages that can spill when allowDiskUse is on: $bucket, $bucketAuto, $group, $setWindowFields, $sort (when no index supports it), $sortByCount.[^c1-1][^c1-3]
- Tentative: Starting in MongoDB 9.0 a per-operation memory limit (internalQueryMaxMemoryUsageBytesPerOperation, default max of 1 GB or 20% of server memory) covers combined tracked memory of blocking stages and expressions. It does not change per-stage spilling. Overruns return QueryExceededMemoryLimitNoDiskUseAllowed (292, when allowDiskUse is false) or ExceededMemoryLimit (146). verified-as-of: 2026-10-14[^c1-1]

### Sharded Explain and Split Pipelines (SHARD_MERGE and per-shard stats and merge shard selection)

- In sharded explain, the SHARD_MERGE stage merges results from shards, and queryPlanner.winningPlan.shards is an array with one entry per accessed shard carrying shardName, connectionString, serverInfo, namespace, parsedQuery, planCacheShapeHash and the per-shard winning plan. (two sources)[^c2-3][^c2-6]
- Aggregation explain on a multi-shard run reports a splitPipeline with shardsPart (stages executed on each shard) and mergerPart (stages executed once at the merge point), plus a shards section keyed by shard name; a single-shard or unsharded run shows only a flat stages array with no splitPipeline. (two sources)[^c2-6][^c2-4]
- Tentative: The explain field mergeType reports where the merger part runs; the documented examples show mongos and anyShard. Search summaries of the docs also list specificShard (with a mergeShard field naming the shard) and router, but the page text for those was not directly verified. verified-as-of: 2026-10-19[^c2-4]
- Merge location rules: if the pipeline starts with an exact $match on the shard key and has no $out or $lookup, the whole pipeline runs on the one matching shard (no split); otherwise results merge on mongos, except $out/$lookup cases and a randomly selected shard when a sort or group stage runs with allowDiskUse enabled.[^c2-1][^c2-2][^c2-4]
- Tentative: The older explain boolean needsPrimaryShardMerger was targeted for replacement by a merger-type field (SERVER-30480, fixed 3.5.12, 2017-08-21); the ticket notes the exact merging shard may be unknown at explain time.[^c2-7]

### $group $first Loose Index Scan (DISTINCT_SCAN for sort-group-first)

- A pipeline starting with $sort and then $group using only $first (or only $last) can be planned as a DISTINCT_SCAN over a matching index. It reads about one index entry per group instead of the whole index. The original ticket's example: index {x:1,y:1}, $sort {x:1,y:1}, $group by x with $first y, which previously did a full index scan.[^c3-1][^c3-6]
- SERVER-9507 (the $first optimization) was fixed in 4.1.4 (resolved 2018-09-26). SERVER-37304 extended it to $group expressions using exclusively $last by running the DISTINCT_SCAN in reverse; fixed in 6.3.0-rc0 (resolved 2022-12-08). verified-as-of: 2026-10-19[^c3-1][^c3-2]
- Tentative: Planner conditions (per a MongoDB author's description): a matching index with the right sort order (scan direction may be flipped), and group fields not multikey. If met, the pipeline is rewritten to DISTINCT_SCAN plus a $groupByDistinct. This is a single-author description, not the manual.[^c3-6]
- Tentative: Rewrite from $sort+$group($first/$last) to $group with $top/$bottom (dropping the blocking $sort) is only a proposal: SERVER-85213 is Backlog with no fix version (last updated 2025-10-24), split into SERVER-87590 ($first/$last) and SERVER-87591 ($firstN/$lastN). DISTINCT_SCAN with $top/$bottom (SERVER-84347) is closed. verified-as-of: 2025-10-24[^c3-4]

### Cost-Based Ranker and Multi-Planning Changes (8.3 and 9.0)

- Starting in MongoDB 8.3, multi-planning with a CBR backup is the default plan selection mechanism for eligible queries. The multi-planner gets a short trial; if unsuccessful, rules decide whether it continues or CBR evaluates each plan node.[^c4-1][^c4-5][^c4-7]
- CBR scores each plan node with a cost function and cardinality estimates and picks the plan with the lowest top-level costEstimate. The docs state MongoDB currently invokes CBR for only a small number of queries; eligibility rules and the continue-vs-CBR fallback rules are not published in the query-plans page. (two sources) verified-as-of: 2026-10-19[^c4-1][^c4-2]
- Both the classic multi-planner and CBR store the chosen plan in the plan cache and reuse it for the same plan cache query shape; explain ignores existing plan cache entries and creates none. A bad plan chosen once can therefore persist for a shape until a DDL event, LRU eviction, restart or manual clear.[^c4-1][^c4-2]
- Tentative: Classic multi-planner winner is the plan that produces the most results during the trial while doing the least work; the winning multi-planner score is reported in explain executionStats-era fields, distinct from CBR costEstimate.[^c4-1]
- Tentative: Percona lists reduced multi-planning cost among 8.3 performance improvements and says the new serverStatus counters and explain output show when CBR was used and how often it won; it gives no CBR-specific benchmark. verified-as-of: 2026-07-30[^c4-5]

## Tools & Frameworks

- With executionStats or allPlansExecution, spill-capable stages ($sort, $group, $setWindowFields, $bucketAuto, $graphLookup, and $lookup only under the slot-based engine) report usedDisk, spills, spilledBytes (estimate before compression), spilledRecords and spilledDataStorageSize. MongoDB 8.1 adds $text queries using the TextOr stage. (two sources) verified-as-of: 2026-10-18[^c1-2][^c1-1] _(Aggregation Explain and Spill Statistics ($lookup and $group and memory limits))_
- Tentative: The explain results page also documents peakTrackedMemBytes (8.1 table) and, from MongoDB 9.0, expressionEvaluationPeakMemoryBytes for classic-engine stages ($addFields, $bucketAuto, $graphLookup, $lookup, among others) at executionStats verbosity or higher. verified-as-of: 2026-10-18[^c1-2] _(Aggregation Explain and Spill Statistics ($lookup and $group and memory limits))_
- A $lookup stage in executionStats or allPlansExecution explain (since 5.0) reports totalDocsExamined, totalKeysExamined, collectionScans, indexesUsed and executionTimeMillisEstimate, so inner-side collection scans are visible. (two sources)[^c1-2][^c1-1] _(Aggregation Explain and Spill Statistics ($lookup and $group and memory limits))_
- Tentative: Planning time (optimizationTimeMillis) excludes time spent optimizing inner $lookup queries. Since 8.0 rejectedPlans contain only the find portion; earlier versions could include aggregation stages such as $group. verified-as-of: 2026-10-18[^c1-2] _(Aggregation Explain and Spill Statistics ($lookup and $group and memory limits))_
- Explain evidence: with index {a:1,b:1,c:1}, $match a:1, $sort {b:1,c:1}, $group _id:$b with $first accumulators, executionStats show FETCH over DISTINCT_SCAN with keysExamined 11, totalDocsExamined 10, nReturned 10 for 10 groups (indexBounds a:[1,1], b and c full range). Compare with PostgreSQL, which read ~200,000 rows for the same result. (two sources)[^c3-6][^c3-7] _($group $first Loose Index Scan (DISTINCT_SCAN for sort-group-first))_
- Explain output for CBR plans adds costEstimate, cardinalityEstimate, numKeysEstimate, numDocsEstimate and estimatesMetadata.ceSource per stage, marked new in 8.3.3. ceSource values: sampling, heuristics (only when sampling fails), mixed, metadata, code. A large gap between numKeysEstimate and costEstimate can indicate a problem with the winning plan. verified-as-of: 2026-10-19[^c4-2][^c4-3] _(Cost-Based Ranker and Multi-Planning Changes (8.3 and 9.0))_
- 8.3.3 (June 9, 2026) added CBR observability: explain output (SERVER-115402), serverStatus metrics (SERVER-120369, under metrics.query.cbr incl. count, choseWinningPlan, numPlans, numPlansFailedCostEstimation, numPlansTiedCostEstimation, samplingMicros) and $queryStats metrics (SERVER-117199); SERVER-118434 made CBR eligible during query planning. (two sources) verified-as-of: 2026-10-19[^c4-3][^c4-5] _(Cost-Based Ranker and Multi-Planning Changes (8.3 and 9.0))_
- planCacheShapeHash (added 8.0, duplicate of deprecated queryHash) depends only on query shape; planCacheKey depends on shape plus available indexes, so adding or dropping an index changes the key but not the shape hash.[^c4-1][^c4-2] _(Cost-Based Ranker and Multi-Planning Changes (8.3 and 9.0))_
- MongoDB 9.0 release notes document no change to CBR or multi-planner selection. Planner-adjacent 9.0 additions: querySettings passable per find/distinct/aggregate command (not stored; stored cluster settings win on conflict), queryKnobs to override internal server parameters per query shape, and per-shape maxTimeMS, all requiring FCV 9.0 for the latter two. (two sources) verified-as-of: 2026-10-19[^c4-4][^c4-6] _(Cost-Based Ranker and Multi-Planning Changes (8.3 and 9.0))_

## Methodology

- Profiler and diagnostic log lines carry a usedDisk indicator when any stage wrote temporary files, so spills show up in slow-query logs without re-running explain. (two sources)[^c1-1][^c1-3] _(Aggregation Explain and Spill Statistics ($lookup and $group and memory limits))_

## Practical Patterns

- Mitigations for memory pressure: use an index-backed sort, put $limit after $sort, and filter with $match early. On sharded clusters, allowDiskUse on a sorting or grouping stage may move the merge to a randomly selected shard. (two sources)[^c1-1][^c1-3] _(Aggregation Explain and Spill Statistics ($lookup and $group and memory limits))_
- The random-shard merge exists so the merger part has more disk space available for spilling blocking stages when allowDiskUse is true; with allowDiskUse false, streaming-only mergers stay on mongos. (two sources)[^c2-4][^c2-2] _(Sharded Explain and Split Pipelines (SHARD_MERGE and per-shard stats and merge shard selection))_
- Official $group docs advise: if a pipeline sorts and groups on the same field and $group uses only $first/$last, add an index on the grouped field matching the sort order. They also say $group of the form {_id:'$<field>'} can result in DISTINCT_SCAN, and to confirm via explain results. (two sources)[^c3-7][^c3-1] _($group $first Loose Index Scan (DISTINCT_SCAN for sort-group-first))_
- Index key order must fit the group key: the index {user:1,timestamp:-1,request:1} did not give DISTINCT_SCAN for $group by request after $sort by timestamp. Reindexing to {user:1,request:1,timestamp:-1} with $sort {request:1,timestamp:-1} did, but the output came back ordered by request. A MongoDB engineer's fix was a second $sort by timestamp after $group, followed by $limit, which the optimizer coalesces into a top-k. (two sources)[^c3-5][^c3-6] _($group $first Loose Index Scan (DISTINCT_SCAN for sort-group-first))_

## Anti-Patterns

- $push and $addToSet inside $group cannot spill: each hits a separate 100 MB cap and fails with 'used too much memory and cannot spill to disk. Memory limit: 104857600 bytes' even with allowDiskUse: true. Fix by restructuring (filter or limit first, two-step group, $topN), not by flag. (two sources)[^c1-3][^c1-6] _(Aggregation Explain and Spill Statistics ($lookup and $group and memory limits))_
- MongoDB documents explain output as intended for humans, subject to change between releases, and says split-pipeline optimizations can change; do not hard-code parsers against field layout, and note output differs between classic and slot-based engines. (two sources)[^c2-1][^c2-3] _(Sharded Explain and Split Pipelines (SHARD_MERGE and per-shard stats and merge shard selection))_
- Correctness bug SERVER-97238: with data {mk:[1,2,3], notMk:4}, index {notMk:1, mk:1}, and $group _id:$notMk acc:{$first:'$mk'}, a distinct scan returned acc:1 instead of [1,2,3]. The planner only checked for multikey fields before the distinct key, not the projected field. Affected 4.2 through 8.0; fixed in 8.1.0-rc0 (resolved 2025-02-08). On older servers, a $first over an array field covered by a multikey index entry is a result-correctness risk. (two sources) verified-as-of: 2026-10-19[^c3-3][^c3-1] _($group $first Loose Index Scan (DISTINCT_SCAN for sort-group-first))_
- Tentative: Third-party guidance calls CBR the primary plan-regression risk in an 8.0 to 8.3 upgrade (claimed 5-50x slowdowns on some shapes) and recommends capturing plan shapes before upgrade and diffing after. This is an unquantified vendor-blog opinion, not measured evidence; no independent benchmark of CBR plan quality was found. verified-as-of: 2026-10-19[^c4-7] _(Cost-Based Ranker and Multi-Planning Changes (8.3 and 9.0))_

## Troubleshooting

- MongoDB 6.0+ can run $lookup in the slot-based engine only if all preceding stages are also SBE-eligible, so the same pipeline may or may not produce $lookup spill metrics depending on engine selection. (two sources) verified-as-of: 2026-10-18[^c1-2][^c1-5] _(Aggregation Explain and Spill Statistics ($lookup and $group and memory limits))_
- Tentative: Hash-based $lookup (HashLookupStage in SBE) is chosen by heuristics only for small data, so spilling is possible but very unlikely; the regular SBE HashJoinStage did not support spilling. The improvement ticket SERVER-74293 is unresolved with a proposal to close it Won't Do. verified-as-of: 2023-03-14[^c1-5] _(Aggregation Explain and Spill Statistics ($lookup and $group and memory limits))_
- Tentative: CVE-2026-4358 (published 2026-03-17): a crafted $lookup aggregation by an authenticated user with write privileges can trigger a double-free or use-after-free in the SBE engine when an in-memory hash table is spilled to disk. CVSS v4 6.1 medium, v3 7.5. verified-as-of: 2026-04-02[^c1-4] _(Aggregation Explain and Spill Statistics ($lookup and $group and memory limits))_
- Merge-sort visibility: from 4.2 the merge sort moved into $mergeCursors and vanished from explain's mergerPart (4.0 showed a $sort with mergePresorted:true); SERVER-57383 restored it by showing $mergeCursors at the front of mergerPart, fixed in 5.3.0 (resolved 2022-01-20). The practical-aggregations guide describes the omission as affecting 4.2 to 5.2 only. (two sources) verified-as-of: 2026-10-19[^c2-5][^c2-4] _(Sharded Explain and Split Pipelines (SHARD_MERGE and per-shard stats and merge shard selection))_
- Tentative: Single-shard targeted aggregations: SERVER-18444 (fixed 3.1.4, 2015) asked that explain state the pipeline ran directly on one shard and name its host; before that such runs showed no shard identity.[^c2-6] _(Sharded Explain and Split Pipelines (SHARD_MERGE and per-shard stats and merge shard selection))_
- Index filters are deprecated since 8.0; docs direct users to query settings (setQuerySettings) instead, which is the supported way to pin or steer a plan if CBR or the multi-planner picks badly. (two sources)[^c4-1][^c4-4] _(Cost-Based Ranker and Multi-Planning Changes (8.3 and 9.0))_

## Disagreements & Open Questions

- Disagreement (Aggregation Explain and Spill Statistics ($lookup and $group and memory limits)): Netdata says $graphLookup spills when allowDiskUse permits, and the current explain page lists it among spill-metric stages. A search snippet of an older ticket (SERVER-23980) suggested Won't Do; not verified by fetch.[^c1-3][^c1-2]
- Disagreement (Aggregation Explain and Spill Statistics ($lookup and $group and memory limits)): Netdata's older-version note ties a legacy error code to $group (16945) and $sort (16819) while current docs name 292 and 146; version boundaries are not documented by MongoDB in the fetched pages.[^c1-3][^c1-1]
- Open (Aggregation Explain and Spill Statistics ($lookup and $group and memory limits)): Whether allowDiskUse governs spilling in the SBE hash-lookup plan; no official page found.
- Open (Aggregation Explain and Spill Statistics ($lookup and $group and memory limits)): Affected and fixed versions of CVE-2026-4358 (tracked in SERVER-118849, not fetched).
- Open (Aggregation Explain and Spill Statistics ($lookup and $group and memory limits)): Whether the 8.1 peakTrackedMemBytes and 9.0 per-operation limit are GA or preview in current releases.
- Open (Aggregation Explain and Spill Statistics ($lookup and $group and memory limits)): Exact $group accumulator memory parameters (internalQueryMaxPushBytes, internalQueryMaxAddToSetBytes) were seen only in a search snippet of SERVER-73315.
- Disagreement (Sharded Explain and Split Pipelines (SHARD_MERGE and per-shard stats and merge shard selection)): Docs v4.4-v7.0 say $out/$lookup merges run on the primary shard; v8.2 says $out merges on the shard holding the output collection and $lookup on the shard holding the unsharded collection. Unclear whether behavior changed or wording was refined.[^c2-1][^c2-2]
- Disagreement (Sharded Explain and Split Pipelines (SHARD_MERGE and per-shard stats and merge shard selection)): Docs-page order/priority of merge rules: the practical-aggregations guide says its rule order does not set priority, and lists primary-shard merge for unsharded references, whereas the manual lists primary shard for $out/$lookup generally.[^c2-4][^c2-1]
- Open (Sharded Explain and Split Pipelines (SHARD_MERGE and per-shard stats and merge shard selection)): Exact mergeType enum (mongos, anyShard, specificShard, router) and mergeShard field were not confirmed on a primary manual page; verify on a live explain.
- Open (Sharded Explain and Split Pipelines (SHARD_MERGE and per-shard stats and merge shard selection)): Whether top-level SHARD_MERGE nReturned equals the sum of per-shard nReturned was not documented.
- Open (Sharded Explain and Split Pipelines (SHARD_MERGE and per-shard stats and merge shard selection)): All sources are MongoDB-authored (manual, MongoDB staff guide, MongoDB Jira); no independent-organisation source was found, so independence requirement is not met.
- Open (Sharded Explain and Split Pipelines (SHARD_MERGE and per-shard stats and merge shard selection)): Whether 8.x changed actual $out/$lookup merge placement vs docs wording only.
- Disagreement ($group $first Loose Index Scan (DISTINCT_SCAN for sort-group-first)): The blog says the planner requires non-multikey group fields; SERVER-97238 showed that check was insufficient for projected array fields until 8.1.0.[^c3-6][^c3-3]
- Open ($group $first Loose Index Scan (DISTINCT_SCAN for sort-group-first)): Whether SERVER-97238's fix was backported to 7.0/8.0 (only 8.1.0-rc0 fix version seen).
- Open ($group $first Loose Index Scan (DISTINCT_SCAN for sort-group-first)): Whether SBE vs classic engine selection changes DISTINCT_SCAN availability (SERVER-88044, cannot-reproduce report, not read).
- Open ($group $first Loose Index Scan (DISTINCT_SCAN for sort-group-first)): Search snippets mention SERVER-37715 ($unwind blocks DISTINCT_SCAN), SERVER-69359 and SERVER-40465 but those pages were not fetched.
- Disagreement (Cost-Based Ranker and Multi-Planning Changes (8.3 and 9.0)): 8.3 GA date differs: community forum post May 5, 2026, MongoDB product page May 7, 2026, MinervaDB May 4, 2026.[^c4-7]
- Disagreement (Cost-Based Ranker and Multi-Planning Changes (8.3 and 9.0)): MinervaDB frames CBR as the main regression risk; MongoDB docs say CBR runs for only a small number of queries and the classic multi-planner is retained, implying limited blast radius.[^c4-7][^c4-1]
- Open (Cost-Based Ranker and Multi-Planning Changes (8.3 and 9.0)): Exact eligibility criteria and fallback rules for CBR (not in public docs).
- Open (Cost-Based Ranker and Multi-Planning Changes (8.3 and 9.0)): Exact planRankerMode-style query knob names and values (SERVER-92587 appeared Unresolved in search snippets; not verified).
- Open (Cost-Based Ranker and Multi-Planning Changes (8.3 and 9.0)): No independent benchmark of CBR plan quality found.
- Open (Cost-Based Ranker and Multi-Planning Changes (8.3 and 9.0)): Whether 9.0 changes CBR default eligibility; release notes silent.

## References

### Aggregation Explain and Spill Statistics ($lookup and $group and memory limits)

[^c1-1]: https://www.mongodb.com/docs/manual/core/aggregation-pipeline-limits.md — Aggregation Pipeline Limits (docs)
[^c1-2]: https://www.mongodb.com/docs/manual/reference/explain-results/ — Explain Results (docs)
[^c1-3]: https://www.netdata.cloud/guides/mongodb/mongodb-exceeded-memory-limit-group-sort/ — MongoDB exceeded memory limit for $group (blog)
[^c1-4]: https://www.tenable.com/cve/CVE-2026-4358 — CVE-2026-4358 (docs)
[^c1-5]: https://jira.mongodb.org/browse/SERVER-74293 — SERVER-74293 Improve spilling algorithm for HashLookupStage (repo)
[^c1-6]: https://www.mongodb.com/community/forums/t/push-used-too-much-memory-and-cannot-spill-to-disk-even-though-allowdiskuse-true/325640 — $push used too much memory forum thread (forum)

### Sharded Explain and Split Pipelines (SHARD_MERGE and per-shard stats and merge shard selection)

[^c2-1]: https://www.mongodb.com/docs/v7.0/core/aggregation-pipeline-sharded-collections/ — Aggregation Pipeline and Sharded Collections (v7.0) (docs)
[^c2-2]: https://www.mongodb.com/docs/v8.2/core/aggregation-pipeline-sharded-collections/ — Aggregation Pipeline and Sharded Collections (v8.2) (docs)
[^c2-3]: https://www.mongodb.com/docs/manual/reference/explain-results/ — Explain Results (docs)
[^c2-4]: https://www.practical-mongodb-aggregations.com/guides/sharding.html — Practical MongoDB Aggregations: Sharding Considerations (blog)
[^c2-5]: https://jira.mongodb.org/browse/SERVER-57383 — SERVER-57383 merge sort in sharded aggregation explain (forum)
[^c2-6]: https://jira.mongodb.org/browse/SERVER-18444 — SERVER-18444 improve explain of aggregation in sharded cluster (forum)
[^c2-7]: https://jira.mongodb.org/browse/SERVER-30480 — SERVER-30480 explain needsPrimaryShardMerger (forum)

### $group $first Loose Index Scan (DISTINCT_SCAN for sort-group-first)

[^c3-1]: https://jira.mongodb.org/browse/SERVER-9507 — SERVER-9507 Optimize sort+group+first (docs)
[^c3-2]: https://jira.mongodb.org/browse/SERVER-37304 — SERVER-37304 Extend to $last (docs)
[^c3-3]: https://jira.mongodb.org/browse/SERVER-97238 — SERVER-97238 distinct scan may unwind arrays (docs)
[^c3-4]: https://jira.mongodb.org/browse/SERVER-85213 — SERVER-85213 Rewrite to $top/$bottom (docs)
[^c3-5]: https://www.mongodb.com/community/forums/t/poor-performance-of-getting-most-recent-distinct-values-full-index-scan/208264 — Poor performance of most recent distinct values (forum)
[^c3-6]: https://dev.to/franckpachot/firstlast-per-group-postgresql-distinct-on-and-mongodb-distinctscan-performance-1e9d — First/last per group: DISTINCT ON and DISTINCT_SCAN (blog)
[^c3-7]: https://www.mongodb.com/docs/manual/reference/operator/aggregation/group.md — $group (aggregation stage) (docs)

### Cost-Based Ranker and Multi-Planning Changes (8.3 and 9.0)

[^c4-1]: https://www.mongodb.com/docs/v8.3/core/query-plans/ — Query plans (8.3) (docs)
[^c4-2]: https://www.mongodb.com/docs/manual/reference/explain-results/ — Explain Results (docs)
[^c4-3]: https://www.mongodb.com/docs/manual/release-notes/8.3/ — Release Notes for MongoDB 8.3 (docs)
[^c4-4]: https://www.mongodb.com/docs/manual/release-notes/9.0/ — Release Notes for MongoDB 9.0 (docs)
[^c4-5]: https://www.percona.com/blog/percona-server-for-mongodb-8-3-technical-preview-is-now-available/ — Percona Server for MongoDB 8.3 Technical Preview (blog)
[^c4-6]: https://percona.com/blog/mongodb-9-0-more-8-4-than-9-0 — MongoDB 9.0: More 8.4 than 9.0? (blog)
[^c4-7]: https://minervadb.com/mongodb-performance-troubleshooting/ — MongoDB Performance Troubleshooting: 7 Proven Fixes (blog)
