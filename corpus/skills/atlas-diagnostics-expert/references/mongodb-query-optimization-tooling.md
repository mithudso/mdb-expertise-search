<!-- hub-reference-banner -->
> **Reference file — part of the `atlas-diagnostics-expert` hub.** Created by `/dr` deep research 2026-10-19; research dir `<local-path>`.

---
name: mongodb-query-optimization-tooling
description: "MongoDB query-optimization tooling and platform surfaces: Compass Explain Plan (Visual Tree, Raw JSON, Query Performance Summary), Atlas Query Insights (Query Shapes, Namespace Insights, log-based Query Profiler on M10+), Atlas Performance Advisor (create/drop/schema suggestions, Impact score), post-8.0 query-engine changes (8.1/8.2 $queryStats and spill metrics; 9.0 major release), LLM-assisted optimization (Compass assistant, MCP Server) and the $regex vs $text vs Atlas Search decision. TRIGGER: 'read explain in Compass', 'Query Insights or Query Profiler', 'Performance Advisor suggestions', 'what changed in 8.1/8.2/9.0 for queries', 'MCP server index recommendation', 'Atlas Search instead of $text or $regex'. SKIP: raw explain/plan cache -> mongodb-expert (mongodb-explain-plans-and-query-planner); index design -> mongodb-expert; Atlas Search configuration -> mongodb-atlas-expert; fix-loop on one query -> deep-mongodb-mql-query-optimizer."
version: "1.0.0"
updated: "2026-10-19"
category: "research"
whenToUse:
  - "read or share an explain plan through Compass"
  - "find slow query shapes with Atlas Query Insights or the Query Profiler"
  - "act on Performance Advisor index, drop-index or schema suggestions"
  - "decide between $regex, $text and Atlas Search"
keywords: ["Compass explain plan", "Visual Tree", "Query Insights", "Query Profiler", "Namespace Insights", "Performance Advisor", "index suggestions", "Impact score", "MongoDB 8.2", "MongoDB 9.0", "queryStats", "MCP server", "Compass assistant", "Atlas Search vs $text", "$regex vs $text"]
tags: ["mongodb", "atlas", "compass", "query-optimization", "tooling", "llm"]
provenance: "/dr · <local-path>"
---

# MongoDB Query Optimization Tooling: Compass Explain, Atlas Query Insights and Performance Advisor

## Overview

The Compass Explain Plan modal is a GUI over MongoDB's explain output. Clicking Explain in the query bar, or in the aggregation pipeline builder, opens a Visual Tree (default; one node per stage, click for detail) or a Raw Output JSON view, plus a Query Performance Summary of execution time, returned documents, examined documents and examined index keys. It is used to spot COLLSCAN stages and large examined-vs-returned gaps. Limits: $merge/$out are stripped before explaining, vector search has no tree view, and the summary can mislead for pipelines with $lookup on the classic engine (open bug COMPASS-7062). A past bug inflated aggregation execution time (fixed in 1.38.0). Third-party claims of colour-coded nodes and index advisors in the tab are not backed by the official docs.

Query Insights is the Atlas cluster-sidebar section (launched May 2024) that groups Query Shapes, Namespace Insights and the Query Profiler. The Query Profiler is a log-based scatterplot of slow operations on M10+ clusters. It reads mongod slow-query log entries, not the Database Profiler. Atlas manages the slow-operation threshold per host (opt-out: fixed 100 ms via Admin API). The view is sampled: about 100,000 logs or chart points, a bucketing algorithm, up to five minutes of lag, bulk operations excluded, and ingestion may pause during log spikes. Namespace Insights charts per-collection latency (P50/P95/P99, op counts) for up to five namespaces over up to seven days. Query Shape Insights needs MongoDB 8.0+ and, from 9.0, samples about 1% of operations. Caveat: only one non-MongoDB source was found, and it is a low-authority blog with internal inconsistencies.

Performance Advisor is the Atlas feature that watches slow operations on M10+ and Flex clusters and produces three recommendation types: create-index suggestions ranked by an 'Impact' score (total wasted bytes read), drop-index suggestions (unused, redundant, hidden), and schema suggestions (anti-patterns found by sampling active collections). Index suggestions come from grouping slow queries into query shapes, with documented guards (max 16 fields, scanned-minus-returned over 500, prefix de-duplication). It is rule-based on log-derived samples, not a data-aware optimizer, so suggestions are estimates: they can miss low-cardinality fields, reflect a short log window, and need validation with explain and $indexStats before and after building. Programmatic access exists via the Atlas Admin API and CLI (listSuggestedIndexes, listSchemaAdvice, public preview).

MongoDB 8.1 and 8.2 are minor rapid releases; 9.0 is the next major release (announced October 2026). The changes that matter for query-optimization tooling are mostly observability: $queryStats coverage and output shape, explain fields for spills and memory, query settings, and slow-log metrics. 8.1 added count/distinct queryStats, search-stage explain stats and spill metrics in slow logs. 8.2 standardized spill metrics in explain and reduced multi-planning cost. 9.0 adds a per-operation memory cap, $queryStats on by default (1% sampling) including writes, a restructured $queryStats output, per-command querySettings, queryKnobs and per-shape maxTimeMS. Vendor performance numbers for 9.0 are unverified. The 9.0 memory cap can make previously working queries fail.

MongoDB ships two LLM-facing optimization surfaces: the Compass intelligent assistant (interprets explain plans, recommends indexes, runs read-only tools with per-call approval) and the MongoDB MCP Server (lets Claude, Cursor or Copilot call explain, collection-indexes, create-index and the Atlas Performance Advisor). Performance Advisor itself is rule/score based, not an LLM; the LLM only fronts it. Independent research (Microsoft Research, 2026, relational DBs) shows LLM index tuning has high run-to-run variance and can regress workloads, so LLM index suggestions need validation before production. No MongoDB-specific accuracy benchmark for LLM index advice was found. Pre-LLM academic work (ADBIS 2023) shows query-only index suggestion for MongoDB is feasible without usage data.

Decision between three ways to match text in MongoDB: $regex on a B-tree index, a $text text index, or an Atlas Search ($search) Lucene index. $regex only uses an index range efficiently for case-sensitive anchored prefixes; case-insensitive and unanchored patterns scan. $text is limited to one text index per collection, with no hint(), no sort help and binary collation only. MongoDB documentation recommends moving $text-heavy workloads to $search for relevance, fuzzy matching, autocomplete and larger data, while calling $text adequate for simple, narrow searches. All primary evidence found comes from MongoDB itself, and no head-to-head benchmark numbers were found, so the offload threshold must be measured on the user's own data with explain and the profiler.

## Core Concepts

### Compass Explain Plan Visualizer

- Clicking Explain in the Compass query bar opens the Explain Plan modal. It shows a Visual Tree by default, with one node per query operation. Clicking a node shows detailed execution information. A Raw Output view shows the full explain plan as JSON.[^c1-1][^c1-6]
- The Query Performance Summary reports execution time, number of returned documents, number of examined documents and number of examined index keys. The aggregation pipeline builder's Explain button opens the same modal, with one tree node per pipeline stage, and shows the same four summary metrics.[^c1-1][^c1-2]

### Atlas Query Insights and Query Profiler

- Query Insights is a section in the Atlas cluster sidebar that combines Namespace Insights (collection-level latency) and the upgraded cluster-centric Query Profiler; Query Shapes is the default tab. The launch blog is dated 2024-05-02.[^c2-3][^c2-2]
- The Query Profiler is available only on M10+ clusters. It is enabled by default. Disabling it requires Project Owner (or Organization Owner); viewing requires Project Read Only or Project Observability Viewer. It is toggled together with Performance Advisor under Project Settings > Database Monitoring Tools. verified-as-of: 2026-10-14[^c2-1][^c2-5]
- The Query Profiler is built from mongod slow-query log entries, not from the Database Profiler. Changing db.setProfilingLevel does not alter which slow queries the Query Profiler displays, and the UI works independently of profiling settings.[^c2-1][^c2-5]
- Tentative: Query Shape Insights (Query Shapes tab) requires a dedicated cluster (M10+) on MongoDB 8.0+. On 9.0+ Atlas randomly samples 1% of reads and writes by default, so shown metrics reflect about 1% of operations, infrequent shapes may be missing, and totals shift after an 8.x to 9.0 upgrade because of the sampling change. verified-as-of: 2026-10-18[^c2-4]

### Atlas Performance Advisor (index and schema suggestions)

- Performance Advisor is only available on M10+ clusters and Flex clusters; the Atlas-managed slow-query threshold is disabled on Free (M0) clusters and unsupported on clusters with MongoDB Search enabled. verified-as-of: 2026-10-19[^c3-1][^c3-4]
- The advisor monitors operations slower than 100 ms (docs for index ranking) and groups them into query shapes. In the UI the threshold is Atlas-managed (dynamic) by default and can be switched to a fixed value; MongoDB advises not setting a fixed threshold below 100 ms. Changing it needs Project Owner. (two sources) verified-as-of: 2026-10-19[^c3-2][^c3-1]
- Guards on suggestions: no index with more than 16 fields; an index is suggested only if scanned documents minus returned documents exceeds 500 for impacted queries; overlapping candidates are de-duplicated so that prefix { a:1 } is dropped in favour of { a:1, b:1 }. (two sources) verified-as-of: 2026-10-19[^c3-2][^c3-1]

### Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0)

- MongoDB 9.0 caps total memory per query operation at 1 GB or 20% of memory available to the server process, whichever is greater. Operations over the cap fail with ExceededMemoryLimit or QueryExceededMemoryLimitNoDiskUseAllowed; the 100 MB per-stage limit and per-stage spilling are unchanged. Tunable via internalQueryMaxMemoryUsageBytesPerOperation. verified-as-of: 2026-10-14[^c4-1][^c4-3]

### AI and LLM-Assisted MongoDB Query and Index Optimization

- Compass natural-language querying (v1.40.x+) generates filter queries and aggregation pipelines from prompts; MongoDB labels it experimental and says it may give inaccurate results, and prompt text plus schema details are sent to Microsoft/OpenAI (Azure OpenAI provider) without being stored or used for training. (two sources) verified-as-of: 2026-10-19[^c5-2][^c5-1]
- The Performance Advisor's recommendations come from MongoDB's own slow-query analysis; the LLM layer (MCP or Compass assistant) is an interface to those endpoints (suggestedIndexes, dropIndexSuggestions, schemaAdvice), not a separate LLM-based recommender. (two sources)[^c5-3][^c5-4]

### Atlas Search vs $text vs $regex (search offload decision)

- A case-sensitive $regex can use an index range scan only when the pattern is an anchored simple prefix (starts with ^ or \A followed by simple characters); the scan stops once the prefix no longer matches. Unanchored patterns and patterns with leading wildcards cannot narrow the index range. (two sources)[^c6-1][^c6-4]
- A collection can have at most one text index. Atlas Search supports multiple full-text search indexes on one collection.[^c6-2][^c6-3]
- Tentative: The $text restrictions page itself points users to MongoDB Search or Vector Search indexes instead of text indexes, so $text is positioned as the legacy option for self-managed deployments. verified-as-of: 2026-10-19[^c6-2]

## Tools & Frameworks

- Profiler views: scatterplot plus table over the last 24 hours by default, filterable by host or primary/secondary group and operation type. Selectable metrics: execution time, response length, docs/keys examined, docs returned, numYields, tokens used ($rerank), and docs-examined:returned and keys-examined:returned ratios. Operations are binned by type, namespace, hasSort, usedIndex and timestamp. Clicking a point shows query shape, execution stats, log and improvement suggestions. verified-as-of: 2026-10-14[^c2-1][^c2-3] _(Atlas Query Insights and Query Profiler)_
- Namespace Insights is M10+ only. It charts one metric (total/average latency, P50, P95, P99, operation count) for up to five namespaces, filterable by read/write/command, with presets from 1 hour to 7 days (default 24 h). Time series collections are not supported and Queryable Encryption collections are redacted. The launch blog says it ranks the top 20 collections by total latency. verified-as-of: 2026-10-18[^c2-2][^c2-3] _(Atlas Query Insights and Query Profiler)_
- Drop-index recommendations cover unused indexes (no query support for 7+ days since creation or server restart; only the 20 most active collections inspected), redundant indexes (prefix of another index in the same collection), and hidden indexes (always recommended for drop). Docs advise hiding an index before dropping it to test impact. (two sources) verified-as-of: 2026-10-19[^c3-3][^c3-1] _(Atlas Performance Advisor (index and schema suggestions))_
- Schema suggestions flag anti-patterns: unbounded arrays, too many collections, unnecessary indexes, excessively large (bloated) documents, and excessive $lookup use. They come from sampling documents in the most active collections and collections with slow queries, exposed via the Admin API listSchemaAdvice endpoint (Public Preview, Project Read Only role). (two sources) verified-as-of: 2026-10-19[^c3-4][^c3-5] _(Atlas Performance Advisor (index and schema suggestions))_
- Tentative: Access control: Project Read Only sees slow queries and suggested indexes; seeing field values in sample queries needs a data-access role (Observability Viewer, Data Access Read Only/Read-Write/Admin), otherwise values are redacted. Creating an index from the advisor needs Data Explorer enabled for the project. verified-as-of: 2026-10-19[^c3-1] _(Atlas Performance Advisor (index and schema suggestions))_
- In 9.0 the classic engine reports expressionEvaluationPeakMemoryBytes in explain at executionStats verbosity or higher for $project, $addFields, $set, $unset, $replaceRoot, $replaceWith, $match, $bucketAuto, $graphLookup and $lookup. A failed operation logs 'Query exceeded the memory limit' with code 12932700. (two sources) verified-as-of: 2026-10-14[^c4-1][^c4-3] _(Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0))_
- 9.0 enables $queryStats collection by default for reads and writes by sampling: internalQueryStatsSampleRate and internalQueryStatsWriteCmdSampleRate both default to 0.01 (1%), so output is a subset of operations. Update, insert and delete commands now get query shapes (8.1 added count and distinct). verified-as-of: 2026-10-14[^c4-1][^c4-4] _(Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0))_
- 9.0 lets a querySettings document be passed directly on a command (applies to that execution only, stored cluster settings win on conflict), adds a queryKnobs setting (requires FCV 9.0) to override internal parameters for one query shape, and a per-shape maxTimeMS via setQuerySettings. 8.1 (and 8.0.4) added comments on setQuerySettings. verified-as-of: 2026-10-14[^c4-1][^c4-2][^c4-3] _(Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0))_
- 8.1 added query statistics for count and distinct commands, explain execution stats for $search, $searchMeta and $vectorSearch stages, per-stage spill metrics (e.g. sortSpills) in slow query logs, and made slow-log durationMillis include authorization and command parsing time. (two sources)[^c4-2][^c4-1] _(Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0))_
- 8.2 standardized explain output for disk-spilling stages with consistent fields spills, spilledBytes, spilledRecords and spilledDataStorageSize, added delinquent-ticket and cpuNanos metrics to $queryStats, and lists 'reduced query multi-planning costs' among performance improvements. The 8.2 notes caveat that gains vary by workload. (two sources) verified-as-of: 2026-10-14[^c4-2][^c4-1] _(Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0))_
- Tentative: 8.1 added serverStatus counters query.planning.fastPath.express and query.planning.fastPath.idHack, showing how many queries took the planning fast paths.[^c4-2] _(Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0))_
- The Compass intelligent assistant interprets explain plan output for a Compass query: in MongoDB's example it flags partial index use and high documents examined, recommends a compound index and proposes a revised pipeline. (two sources) verified-as-of: 2026-10-19[^c5-1][^c5-2] _(AI and LLM-Assisted MongoDB Query and Index Optimization)_
- Tentative: Compass assistant tools are read-only (e.g. find, count, aggregate, explain, collection-indexes, db-stats, mongodb-logs); $out and $merge are unsupported, every tool run needs user confirmation via a Run/Cancel card, and tool results can return live deployment data. verified-as-of: 2026-10-19[^c5-1] _(AI and LLM-Assisted MongoDB Query and Index Optimization)_
- The MongoDB MCP Server exposes an `atlas-get-performance-advisor` tool (suggested indexes, drop-index suggestions, slow query logs, schema advice) plus database tools `explain`, `collection-indexes`, `create-index` and `drop-index`, letting AI clients such as Claude, Cursor and GitHub Copilot drive index analysis in natural language. verified-as-of: 2026-10-14[^c5-4][^c5-3] _(AI and LLM-Assisted MongoDB Query and Index Optimization)_

## Methodology

- A COLLSCAN node means mongod scanned the whole collection document by document. The official tutorial's no-index example shows 0 index keys examined and documents examined equal to the collection size. After an index is added, examined keys approach returned documents. A large gap between examined and returned counts signals a missing or unselective index.[^c1-3][^c1-6] _(Compass Explain Plan Visualizer)_
- The Compass docs page does not state which explain verbosity Compass uses. The summary's runtime figures imply executionStats-level data, but this is inference. The equivalent shell call is db.collection.find(...).explain('executionStats'). Compass presents the same data as the shell in a GUI. (two sources)[^c1-1][^c1-3] _(Compass Explain Plan Visualizer)_
- Triage heuristics from the docs: planSummary COLLSCAN or keysExamined 0 on a filtered query suggests a missing index; docsExamined much larger than docsReturned suggests an unselective index; usedIndex=false and hasSort=true flag unindexed sorts; large response length suggests adding projections. usedIndex does not reflect MongoDB Search index usage.[^c2-1][^c2-5] _(Atlas Query Insights and Query Profiler)_
- Suggested indexes are ranked by 'Impact', defined as total wasted bytes read, computed from per-shape execution time, documents scanned, documents returned and average object size.[^c3-2][^c3-1] _(Atlas Performance Advisor (index and schema suggestions))_
- Tentative: Index field order is chosen by operator type: equality, then $in array, range, $type, $exists, other operators, then sort last; fields are generally ranked by cardinality. This differs from the ESR rule (equality, sort, range) that manual design uses, so check suggested order against sort-bearing queries.[^c3-2] _(Atlas Performance Advisor (index and schema suggestions))_
- Tentative: The same study recommends validating LLM-recommended indexes with performance tests before production, treating the LLM as complementary to cost-based advisors rather than a replacement, and distilling LLM heuristics into deterministic rules; with more queries in the prompt the LLM 'distracts' from the costliest query (about 50% of runs matched DTA on it alone vs below 5% with four queries).[^c5-5] _(AI and LLM-Assisted MongoDB Query and Index Optimization)_
- Tentative: Query-only automatic index suggestion for MongoDB, derived from aggregation pipelines without data or usage statistics, was shown feasible in ADBIS 2023 (Espona et al., FHNW): on TPC-H all suggested indexes were used. This is non-LLM prior art.[^c5-6] _(AI and LLM-Assisted MongoDB Query and Index Optimization)_
- MongoDB documentation recommends rewriting $text-heavy queries as $search to gain flexibility and performance (language awareness, fuzzy matching, highlighting, autocomplete, synonyms, relevance scoring), with the gain growing as data size and query breadth grow. The same page calls $text adequate for simple, narrow searches, so migration is not advised for every query. (two sources)[^c6-3][^c6-2] _(Atlas Search vs $text vs $regex (search offload decision))_

## Practical Patterns

- The MCP Performance Advisor tool requires Atlas Project Read Only role or higher and an M10+ cluster, and MongoDB recommends running it with the --readonly flag; read-only mode and disabling tool categories restrict the server so an agent cannot call create-index or drop-index. (two sources) verified-as-of: 2026-10-14[^c5-4][^c5-3] _(AI and LLM-Assisted MongoDB Query and Index Optimization)_
- Tentative: Practical guardrail for any AI-suggested MongoDB index: confirm with explain that the winning plan uses an IXSCAN and that totalDocsExamined is close to nReturned, since a plausible-looking index or query can still run badly (planner can pick poor indexes; ratios mislead for pipelines after $group).[^c5-4] _(AI and LLM-Assisted MongoDB Query and Index Optimization)_

## Anti-Patterns

- COMPASS-7062 (open, unassigned, Minor, reported against Compass 1.39.0 and MongoDB 6.0.7): for an aggregation with $match plus $lookup running on the classic (non-SBE) engine, the Compass explain summary counts only the documents and keys examined by the $match. It hides $lookup work such as collection scans, so a slow pipeline can look efficient. With SBE the summary is accurate. Check Raw Output when a pipeline contains $lookup. (two sources) verified-as-of: 2026-10-08[^c1-4][^c1-2] _(Compass Explain Plan Visualizer)_
- Bulk operations (bulkWrite(), updateMany with multiple stmtIds, similar multi-document operations) are excluded from Query Profiler sampling and analysis, so a bulk-write-heavy workload is under-represented. (two sources)[^c2-1][^c2-2] _(Atlas Query Insights and Query Profiler)_
- Docs warn that every extra index slows writes and that the user should weigh read frequency against write cost; the docs also tell users to understand the specific schema warning before changing the schema. Applying every suggestion blindly is an antipattern. (two sources)[^c3-1][^c3-4] _(Atlas Performance Advisor (index and schema suggestions))_
- MongoDB's 9.0 performance claims versus 8.0: up to 35% faster find-one, 30% faster update-one, 20% higher transactional throughput, nearly 2x throughput on large deployments. The vendor says these come from internal testing and vary by workload. Percona could not find methodology or raw data, and press coverage reports no benchmark configuration. verified-as-of: 2026-10-09[^c4-4][^c4-3][^c4-5] _(Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0))_
- Tentative: Microsoft Research (Wang, Wu, Narasayya, Chaudhuri, Mar 2026) found GPT-5 index tuning on relational workloads has substantial run-to-run variance: worst runs underperformed Microsoft DTA and caused severe query regressions (TPC-H Q20; timeouts on Real-R), while best single-query runs sometimes beat DTA. Not MongoDB-specific.[^c5-5] _(AI and LLM-Assisted MongoDB Query and Index Optimization)_
- Case-insensitive $regex (the i option) is not collation-aware and cannot use case-insensitive indexes efficiently, so indexes typically do not improve it. This is the pattern that most often forces a collection or full index scan and is the main trigger for offloading to Atlas Search. (two sources)[^c6-1][^c6-3] _(Atlas Search vs $text vs $regex (search offload decision))_
- Other $text restrictions: a query with $text cannot use hint(); text indexes do not improve sort performance; a multi-word phrase mixed with single terms matches only documents containing the full phrase; text indexes accept only binary comparison, so a collection with a non-simple collation needs collation {locale: 'simple'} on the text index; compound text indexes need equality conditions on key prefixes. (two sources)[^c6-2][^c6-3] _(Atlas Search vs $text vs $regex (search offload decision))_

## Troubleshooting

- Compass explain plan omits $merge and $out stages: Compass drops all out stages from the aggregation before running explain. Vector search queries cannot be shown in the Visual Tree format. (two sources) verified-as-of: 2026-10-19[^c1-1][^c1-2] _(Compass Explain Plan Visualizer)_
- Tentative: COMPASS-6496 reported that 'Actual query execution time' for aggregations was inflated because it summed per-stage times that already included earlier stages. It was reported on Compass 1.35.0 with MongoDB 6.0.4 and fixed in Compass 1.38.0 (resolved 2023-06-07). Older Compass builds may over-report aggregation time.[^c1-5] _(Compass Explain Plan Visualizer)_
- Atlas manages the slow-operation threshold per mongod host from that host's average operation execution time, so a query that is slow for the workload but under that host's managed threshold will not appear. Opt out to a fixed 100 ms threshold via the Atlas Administration API (disableManagedSlowMs). Free and Flex clusters have the managed threshold disabled and it cannot be enabled. Settings changed with db.setProfilingLevel reset on node restart. verified-as-of: 2026-10-14[^c2-1][^c2-5] _(Atlas Query Insights and Query Profiler)_
- The Query Profiler data is sampled and lossy: about 100,000 sampled logs and at most 100,000 chart points at once; a bucketing algorithm means a wider time range can show fewer sampled operations than a narrower one; data can lag real time by up to five minutes; during an activity spike Atlas may stop collecting new logs for a period. For exact counts, download the mongod logs, which are always complete. verified-as-of: 2026-10-14[^c2-1][^c2-6] _(Atlas Query Insights and Query Profiler)_
- A high-latency $lookup whose foreign-collection read is local to the shard can raise Namespace Insights latency and operation counts without producing a slow-query log for the foreign collection, so Namespace Insights and the Query Profiler can disagree. (two sources)[^c2-1][^c2-2] _(Atlas Query Insights and Query Profiler)_
- Tentative: Scope limits: not supported for databases using the ctime timestamp format or for time series collections; during extreme log spikes Atlas may stop collecting logs; consecutive $match stages can coalesce so the displayed shape can differ from the query as written. Suggested indexes are created cluster-wide even when viewing one shard. verified-as-of: 2026-10-19[^c3-1] _(Atlas Performance Advisor (index and schema suggestions))_
- Tentative: Suggestions are based on a sample of recent log lines, not full workload history; a community reply says roughly the last 200k log lines. A suggested index can therefore show zero use in $indexStats if the query stopped running or if a mongod restart reset the counters. Validate with explain and db.collection.aggregate([{$indexStats:{}}]) before trusting or removing it. verified-as-of: 2022-12-04[^c3-6] _(Atlas Performance Advisor (index and schema suggestions))_
- 9.0 restructures $queryStats output, grouping metrics under new fields such as metrics.queryExec and metrics.queryPlanner. Tooling that parses $queryStats output must be re-checked before upgrading. verified-as-of: 2026-10-14[^c4-1][^c4-3] _(Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0))_
- Tentative: Percona advises testing 9.0 before upgrading: queries that worked on 8.x may fail under the new memory cap, and null comparisons on dotted paths reportedly changed behavior, so test null queries on production-like heterogeneous data. verified-as-of: 2026-10-09[^c4-3] _(Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0))_
- Tentative: Known issue at FCV 9.0: listIndexes reports collation { locale: 'simple' } for simple-collation indexes (SERVER-89953), so Mongoose syncIndexes() (also Doctrine ODM, Beanie) drops and rebuilds unchanged indexes. Workaround: do not call syncIndexes() at startup, or use Mongoose 9.10.4 / 8.24.5. Fix targeted for a future 9.0 patch. verified-as-of: 2026-10-14[^c4-1] _(Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0))_
- Tentative: 8.2.0 known issues: up to 15% change-stream performance degradation versus 8.0, and a $group distinct-scan-on-sparse-index bug that hides null/missing results (SERVER-110423) fixed in 8.2.2. verified-as-of: 2026-10-14[^c4-2] _(Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0))_
- Tentative: Via MCP, slow-query analysis is capped at a sample of the 50 most recent slow queries matching the prompt; this cap does not apply to the Performance Advisor UI in Atlas. verified-as-of: 2026-10-14[^c5-3] _(AI and LLM-Assisted MongoDB Query and Index Optimization)_
- Tentative: A community-forum case (Nov 2024): a $regex query across 3-4 text fields was CPU-bound on a single core on an M50 Atlas cluster after migration from on-prem 4.2. A single query runs on one core, so a bigger tier does not help; a MongoDB community member recommended Atlas Search. No root cause or resolution was recorded.[^c6-4] _(Atlas Search vs $text vs $regex (search offload decision))_

## Disagreements & Open Questions

- Disagreement (Compass Explain Plan Visualizer): OneUptime (2026-03-31) describes green/orange/red node colouring, an 'Index Used' metric and Compass index suggestions in the Explain tab. The official Compass docs list none of these; they name only four summary metrics and no colour scheme.[^c1-6][^c1-1]
- Open (Compass Explain Plan Visualizer): Which explain verbosity Compass sends (executionStats vs allPlansExecution) is not documented.
- Open (Compass Explain Plan Visualizer): Whether COMPASS-7062 is fixed in current Compass: the ticket was still unresolved on 2026-10-08.
- Open (Compass Explain Plan Visualizer): Whether the Compass UI shows rejected plans or only the winning plan.
- Open (Compass Explain Plan Visualizer): Sharded and $lookup inner-side explain gaps are server-side (SERVER-22622, SERVER-88883); they were only seen in search snippets, not fetched.
- Disagreement (Atlas Query Insights and Query Profiler): Sampling cap changed: current docs say about 100,000 sampled logs; older docs and a 2020 feedback post cite a 10,000-operation limit that left earlier periods looking empty. Treat 10,000 as outdated.[^c2-1][^c2-6]
- Disagreement (Atlas Query Insights and Query Profiler): The third-party blog lists a 24-hour rolling window for Query Profiler history and implies system.profile access is needed; the official page defaults to 24 h view, says it is log-based and independent of profiling, and an older official page cites up to five days of history.[^c2-5][^c2-1]
- Open (Atlas Query Insights and Query Profiler): Actual Query Profiler history retention: a five-day figure appeared only in search snippets of the analyze-slow-queries page, not in a fetched page.
- Open (Atlas Query Insights and Query Profiler): Namespace Insights data retention is not stated in the docs.
- Open (Atlas Query Insights and Query Profiler): Whether the Query Profiler on 9.0 clusters is also affected by the 1% sampling that Query Shape Insights uses; the docs describe it as log-based.
- Open (Atlas Query Insights and Query Profiler): No independent (non-MongoDB) critical evaluation of profiler completeness was found.
- Disagreement (Atlas Performance Advisor (index and schema suggestions)): Docs describe a fixed 100 ms slow-query threshold on the index-ranking page, but the main page says the default threshold is Atlas-managed and dynamic, with 100 ms only as the fixed option.[^c3-2][^c3-1]
- Open (Atlas Performance Advisor (index and schema suggestions)): Exact schema-suggestion trigger thresholds (e.g. index count, document size) were not found; the dedicated Atlas schema-suggestions page URL guessed returned 404.
- Open (Atlas Performance Advisor (index and schema suggestions)): Search snippets (not fetched) indicated feedback.mongodb.com requests about suggestions that cannot be dismissed, ignore custom collation, or suggest unbuildable multi-array indexes; the pages returned 404, so unverified and not claimed.
- Open (Atlas Performance Advisor (index and schema suggestions)): Whether the 200k-log-line sample size is still current; the only source is a 2022 community reply.
- Open (Atlas Performance Advisor (index and schema suggestions)): Only vendor and one community source found; no independent third-party evaluation of suggestion accuracy.
- Disagreement (Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0)): MongoDB claims up to 2x throughput and 35% faster find-one for 9.0; Percona and press coverage say methodology and configurations are undisclosed, and the 2x baseline is unnamed.[^c4-4][^c4-3][^c4-5]
- Open (Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0)): Whether Percona's claim of changed dotted-path null comparison semantics in 9.0 appears in the official compatibility notes; not found in the 9.0 release notes text searched.
- Open (Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0)): Cost-based ranker (CBR) and further multi-planner work appear to land in 8.3, outside this concept; not verified here.
- Open (Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0)): Exact effect of 8.2 'reduced multi-planning costs': no benchmark or SERVER ticket found.
- Disagreement (AI and LLM-Assisted MongoDB Query and Index Optimization): The Compass assistant docs page carries no accuracy caveat or preview label itself, while a search summary and the NL-querying page describe the AI features as experimental/may be inaccurate; preview status of the assistant is unconfirmed from the fetched page.[^c5-1][^c5-2]
- Open (AI and LLM-Assisted MongoDB Query and Index Optimization): No MongoDB-specific benchmark of LLM index/ESR-rule accuracy or hallucinated indexes was found; the Microsoft study is relational (SQL Server DTA).
- Open (AI and LLM-Assisted MongoDB Query and Index Optimization): Whether the Compass intelligent assistant is still labelled public preview as of 2026-10.
- Open (AI and LLM-Assisted MongoDB Query and Index Optimization): Exact data-handling terms for the intelligent assistant (docs defer to an 'AI and Data Usage Information' page not fetched).
- Open (AI and LLM-Assisted MongoDB Query and Index Optimization): MongoDB's own MCP performance blog posts and third-party anecdotes (Medium, OneUptime) were not deep-read.
- Disagreement (Atlas Search vs $text vs $regex (search offload decision)): A web-search summary of the MongoDB developer article 'Atlas Search vs regex' said it concludes $regex wins for simple text matching, while Atlas docs push $text/$regex-heavy workloads toward $search. The article URL returned 404 on fetch, so this was not verified.[^c6-3]
- Open (Atlas Search vs $text vs $regex (search offload decision)): No independent (non-MongoDB) source or numeric benchmark comparing $regex, $text and $search was found; the depth contract of 3 independent organisations was not met.
- Open (Atlas Search vs $text vs $regex (search offload decision)): The Atlas Search query-performance page (regex and wildcard operators are resource-intensive in $search) and the Atlas Search regex/wildcard operator docs were only seen as search snippets, not fetched; their claims are not included.
- Open (Atlas Search vs $text vs $regex (search offload decision)): Whether $search is available on self-managed deployments (older MongoDB article says $text/$regex are the only options there; newer docs suggest otherwise) was not resolved.
- Open (Atlas Search vs $text vs $regex (search offload decision)): Search-node cost, index sync lag and eventual consistency of $search versus transactional $regex/$text reads were not researched.

## References

### Compass Explain Plan Visualizer

[^c1-1]: https://www.mongodb.com/docs/compass/current/query-plan/ — View Query Performance (Compass) (docs)
[^c1-2]: https://mongodb.com/docs/compass/master/agg-pipeline-builder/view-pipeline-explain-plan — View Explain Plans for a Pipeline (Compass) (docs)
[^c1-3]: https://www.mongodb.com/docs/manual/tutorial/analyze-query-plan/ — Interpret Explain Plan Results (docs)
[^c1-4]: https://jira.mongodb.org/browse/COMPASS-7062 — COMPASS-7062 Explain summary inaccurate for $lookup pre-SBE (forum)
[^c1-5]: https://jira.mongodb.org/browse/COMPASS-6496 — COMPASS-6496 Incorrect Actual query execution time (forum)
[^c1-6]: https://oneuptime.com/blog/post/2026-03-31-mongodb-how-to-analyze-query-performance-in-mongodb-compass/markdown — How to Analyze Query Performance in MongoDB Compass (blog)

### Atlas Query Insights and Query Profiler

[^c2-1]: https://www.mongodb.com/docs/atlas/tutorial/query-profiler/ — Monitor Query Performance with the Query Profiler (docs)
[^c2-2]: https://mongodb.com/docs/atlas/namespace-insights — Monitor Collection-Level Query Latency (Namespace Insights) (docs)
[^c2-3]: https://mongodb.com/blog/post/elevating-database-performance-introducing-query-insights-mongodb-atlas — Introducing Query Insights in MongoDB Atlas (blog)
[^c2-4]: https://www.mongodb.com/docs/atlas/query-shape-insights/ — Query Shape Insights (docs)
[^c2-5]: https://oneuptime.com/blog/post/2026-03-31-mongodb-atlas-query-profiler-cloud/view — How to Use Atlas Query Profiler for Cloud MongoDB Deployments (blog)
[^c2-6]: https://feedback.mongodb.com/forums/924145-atlas/suggestions/40018885-profiler-window-should-auto-zoom-to-sampling-perio — Profiler window should auto zoom to sampling period (forum)

### Atlas Performance Advisor (index and schema suggestions)

[^c3-1]: https://mongodb.com/docs/atlas/performance-advisor — Performance Advisor (Atlas docs) (docs)
[^c3-2]: https://www.mongodb.com/docs/atlas/performance-advisor/index-ranking/ — Review Index Ranking (docs)
[^c3-3]: https://www.mongodb.com/docs/atlas/performance-advisor/drop-indexes.md — Review Drop Index Recommendations (docs)
[^c3-4]: https://mongodb.com/docs/manual/data-modeling/design-antipatterns — Schema design anti-patterns (docs)
[^c3-5]: https://www.mongodb.com/docs/atlas/cli/current/command/atlas-api-performanceAdvisor-listSchemaAdvice.md — atlas api performanceAdvisor listSchemaAdvice (docs)
[^c3-6]: https://www.mongodb.com/community/forums/t/are-mongo-atlas-index-recommendations-reliable/129276 — Are Mongo Atlas index recommendations reliable (forum)

### Post-8.0 Query Engine Changes (8.1 and 8.2 rapid releases and 9.0)

[^c4-1]: https://www.mongodb.com/docs/manual/release-notes/9.0/ — Release Notes for MongoDB 9.0 (docs)
[^c4-2]: https://www.mongodb.com/docs/manual/release-notes/8.2 — Release Notes for MongoDB 8.2 (includes 8.1 changes) (docs)
[^c4-3]: https://percona.com/blog/mongodb-9-0-more-8-4-than-9-0 — MongoDB 9.0: More 8.4 than 9.0? (blog)
[^c4-4]: https://mongodb.com/company/blog/product-release-announcements/mongodb-9-0-this-is-what-a-database-should-be — MongoDB 9.0 announcement blog (blog)
[^c4-5]: https://letsdatascience.com/news/mongodb-releases-90-and-atlas-ai-updates-c18a3b57 — MongoDB Releases 9.0 and Atlas AI Updates (blog)

### AI and LLM-Assisted MongoDB Query and Index Optimization

[^c5-1]: https://mongodb.com/docs/compass/query-with-natural-language/compass-ai-assistant — Intelligent Assistant in Compass (docs)
[^c5-2]: https://www.mongodb.com/docs/compass/query-with-natural-language.md — Compass: Query with Natural Language (docs)
[^c5-3]: https://www.mongodb.com/docs/atlas/performance-advisor/access-with-mcp.md — Access Performance Advisor with the MongoDB MCP Server (docs)
[^c5-4]: https://www.mongodb.com/docs/mcp-server/tools.md — MongoDB MCP Server tools (docs)
[^c5-5]: https://arxiv.org/html/2603.09181v1 — Evaluating Practical Effectiveness of LLM-Driven Index Tuning with Microsoft DTA (paper)
[^c5-6]: https://irf.fhnw.ch/handle/11654/43460 — Automatic indexing for MongoDB (ADBIS 2023) (paper)

### Atlas Search vs $text vs $regex (search offload decision)

[^c6-1]: https://www.mongodb.com/docs/current/reference/operator/query/regex/ — $regex (MongoDB manual) (docs)
[^c6-2]: https://mongodb.com/docs/manual/core/indexes/index-types/index-text/text-index-restrictions/ — Text index restrictions (MongoDB manual) (docs)
[^c6-3]: https://mongodb.com/docs/atlas/performance-advisor/recommend-search-text — Rewrite $text queries as $search (Atlas docs) (docs)
[^c6-4]: https://www.mongodb.com/community/forums/t/low-perf-on-regex-search-even-on-m50-instance/305111 — Low perf on regex search even on M50 instance (MongoDB community forum) (forum)
