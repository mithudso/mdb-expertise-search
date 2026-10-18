<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-query-performance` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-query-performance
version: "1.2"
updated: "2026-05-29"
description: >
  MongoDB query performance expert covering index optimization (ESR rule, compound, partial, wildcard, sparse, collation),
  aggregation framework tuning, query planning and explain analysis, WiredTiger caching and eviction,
  profiling and slow-query diagnostics, and internal storage engine algorithms (B-tree, MVCC, skip lists, hazard pointers).
  Applicable to MongoDB 5.0 through 8.x (Atlas and self-managed).
  TRIGGER: diagnosing slow queries or COLLSCANs, designing compound indexes, reading explain() output, tuning aggregation
  pipelines, configuring WiredTiger cache or eviction, setting up the database profiler, reviewing Atlas Performance Advisor,
  understanding storage-engine internals, totalDocsExamined ratio analysis, plan cache management, or SBE eligibility.
  SKIP: schema design decisions without a query-performance angle (use mongodb-schema-design); sharding topology or
  scatter-gather routing (use mongodb-sharding); security, authentication, or encryption (use mongodb-encryption);
  host- and cluster-level performance diagnostics beyond query level (use mongodb-performance-troubleshooting);
  deep $lookup join-strategy internals or $setWindowFields memory limits (use mongodb-aggregation-stages-deep);
  index design on time-series collections (use mongodb-time-series).
triggers:
  - MongoDB query optimization
  - MongoDB slow query
  - MongoDB explain
  - MongoDB index strategy
  - MongoDB aggregation performance
  - MongoDB WiredTiger cache
  - MongoDB profiling
  - MongoDB query planner
  - MongoDB SBE
  - ESR rule
  - covered query MongoDB
  - MongoDB plan cache
  - MongoDB $lookup optimization
  - MongoDB $vectorSearch
  - MongoDB query profiler
  - MongoDB cache eviction
  - mongotop
  - mongostat
keywords:
  - mongodb
  - query optimization
  - index
  - compound index
  - ESR rule
  - covered query
  - partial index
  - wildcard index
  - sparse index
  - collation index
  - aggregation pipeline
  - $match
  - $group
  - $lookup
  - $unwind
  - $setWindowFields
  - $densify
  - $fill
  - $graphLookup
  - $vectorSearch
  - $facet
  - explain
  - queryPlanner
  - executionStats
  - allPlansExecution
  - SBE
  - slot-based execution engine
  - plan cache
  - query shape
  - WiredTiger
  - cache
  - eviction
  - cacheSizeGB
  - profiling
  - system.profile
  - $currentOp
  - Performance Advisor
  - slowms
  - mongotop
  - mongostat
  - B-tree
  - MVCC
  - skip list
  - hazard pointer
  - document-level concurrency
  - read concern
  - read preference
  - $indexStats
  - hint
  - unused indexes
when_to_use:
  - Diagnosing slow MongoDB queries or collection scans
  - Designing compound indexes or evaluating index strategies
  - Tuning aggregation pipelines for performance
  - Interpreting explain() output or query plans
  - Configuring or troubleshooting WiredTiger cache
  - Setting up or analyzing database profiling
  - Understanding MongoDB internal storage engine behavior
  - Evaluating read concern / read preference performance trade-offs
  - Reviewing Atlas Performance Advisor recommendations
when_not_to_use:
  - Schema design decisions without a query-performance angle (use mongodb-schema-design)
  - Sharding topology, chunk balancing, or scatter-gather query routing (use mongodb-sharding)
  - Security, authentication, or field-level encryption (use mongodb-encryption)
  - Host- and cluster-level performance diagnostics beyond query-level (use mongodb-performance-troubleshooting)
  - Deep $lookup join-strategy internals or $setWindowFields memory limits (use mongodb-aggregation-stages-deep)
  - Index design constraints on time-series collections (use mongodb-time-series)
  - Application-level connection pooling or driver retry configuration (use mongodb-driver-internals)
  - Backup and restore operations (use mongodb-backup-restore)
related_skills:
  - mongodb-schema-design
  - mongodb-performance-troubleshooting
  - mongodb-aggregation-stages-deep
  - mongodb-indexes-deep
  - mongodb-wiredtiger
  - mongodb-encryption
  - mongodb-time-series
---

# MongoDB Query Performance

Reference for MongoDB query optimization, aggregation framework tuning, query planning, WiredTiger caching, profiling, and internal storage-engine algorithms. Covers MongoDB 5.0 through 8.x on Atlas and self-managed deployments.

---

## 1. Query Optimization

### 1.1 Index Fundamentals

MongoDB indexes are B-tree data structures that store a subset of the collection's data in an ordered form, enabling the query engine to narrow the search space without scanning every document (COLLSCAN). A well-chosen index converts a collection scan into an index scan (IXSCAN), reducing documents examined by orders of magnitude.

**Index types relevant to performance:**

| Index Type | Use Case | Key Consideration |
|---|---|---|
| Single-field | Equality or range on one field | Simplest; covers sort on that field |
| Compound | Multi-field queries | Field order matters (ESR rule) |
| Multikey | Array fields | One array field per compound index |
| Text | Full-text search | Weight tuning, language stemming |
| Wildcard | Dynamic/polymorphic schemas | Cannot support compound queries or sorts |
| Partial | Subset of documents | Queries must match partialFilterExpression |
| Sparse | Only documents with the field | Skips docs missing the indexed field |
| Collation | Language-aware string comparison | Query must specify matching collation |
| TTL | Auto-expire documents | Single-field only; runs every 60s |

Source: [MongoDB Docs - Query Optimization](https://www.mongodb.com/docs/manual/core/query-optimization/)

### 1.2 The ESR Rule (Equality, Sort, Range)

The ESR rule is the foundational guideline for compound index field ordering:

1. **Equality** fields first -- fields tested with exact match (`{ status: "active" }`)
2. **Sort** fields second -- fields used in `.sort()` operations
3. **Range** fields last -- fields tested with `$gt`, `$lt`, `$in`, `$gte`, `$lte`

**Why this order matters:**

- Equality fields narrow the search space immediately to a small, contiguous range of index entries.
- Sort fields within that narrowed range allow MongoDB to return results in order without an in-memory sort (avoiding the 100 MB sort memory limit).
- Range fields come last because they create a scan within the already-narrowed result set; placing them earlier would fragment the sort order.

**Example:**

```javascript
// Query pattern
db.orders.find({
  customerId: "abc123",     // Equality
  total: { $gte: 100 }      // Range
}).sort({ createdAt: -1 })   // Sort

// Optimal compound index following ESR
db.orders.createIndex({ customerId: 1, createdAt: -1, total: 1 })
```

**Caveat with $in:** The `$in` operator is technically an equality operator, but when it contains multiple values it behaves more like a range scan. For `$in` with many values, treat the field as Range in ESR ordering.

Source: [MongoDB Docs - ESR Guideline](https://www.mongodb.com/docs/manual/tutorial/equality-sort-range-guideline/), [OneUptime - ESR Rule](https://oneuptime.com/blog/post/2026-03-31-mongodb-esr-rule-compound-index/view)

### 1.3 Covered Queries

A covered query is satisfied entirely from the index without touching documents on disk:

- All fields in the query filter are part of the index
- All fields in the projection are part of the index
- No field in the projection is an array (multikey indexes cannot cover)

In `explain()` output, a covered query shows `totalDocsExamined: 0`. This is the fastest possible query path because it eliminates all document fetches and associated I/O.

```javascript
// Index
db.users.createIndex({ email: 1, name: 1, status: 1 })

// Covered query -- only returns indexed fields, excludes _id
db.users.find(
  { email: "user@example.com" },
  { name: 1, status: 1, _id: 0 }
)
```

Source: [MongoDB Docs - Query Optimization](https://www.mongodb.com/docs/manual/core/query-optimization/)

### 1.4 Index Intersection

MongoDB can use the intersection of multiple indexes to fulfill a single query. The query planner evaluates whether combining two single-field indexes is more efficient than a collection scan.

**When intersection helps:** Queries with AND conditions on fields that each have separate single-field indexes but no compound index.

**When compound is better:** In most production workloads, a purpose-built compound index outperforms index intersection. The planner's trial period may select intersection, but it adds overhead from merging result sets.

**Guideline:** Prefer compound indexes for known, frequent query patterns. Rely on intersection only as a fallback for ad-hoc queries.

Source: [Studio 3T - MongoDB Index Strategy](https://studio3t.com/knowledge-base/articles/mongodb-index-strategy/)

### 1.5 Partial Indexes

Partial indexes index only documents matching a `partialFilterExpression`. Benefits:

- Smaller index size (less storage, less RAM in WiredTiger cache)
- Faster index maintenance on writes
- Can enforce unique constraints on a subset of documents

```javascript
db.orders.createIndex(
  { orderId: 1 },
  { partialFilterExpression: { status: { $eq: "active" } } }
)
```

**Critical rule:** Queries must include a filter that matches or is a subset of the `partialFilterExpression`; otherwise MongoDB will not use the partial index.

Source: [MongoDB Docs - Partial Indexes](https://www.mongodb.com/docs/manual/core/index-partial/)

### 1.6 Wildcard Indexes

Wildcard indexes (`{ "$**": 1 }`) support queries against fields with arbitrary or unpredictable names. They are useful for polymorphic schemas where field names vary per document.

**Limitations:**

- Cannot support compound queries across multiple fields
- Cannot support sort operations
- Cannot be used as a shard key index
- Higher write overhead than targeted indexes

**Guideline:** Use wildcard indexes for exploratory or ad-hoc queries on dynamic fields. For known query patterns, always prefer explicit compound indexes.

Source: [Grizzly Peak Software - MongoDB Indexing Best Practices](https://www.grizzlypeaksoftware.com/library/mongodb-indexing-best-practices-mgh2xkpd)

### 1.7 Sparse and Collation Indexes

**Sparse indexes** skip documents that do not contain the indexed field (or where it is null). They produce smaller indexes but will not be used for queries that need to match documents where the field is missing.

**Collation indexes** enable language-aware string comparison (case-insensitive, accent-insensitive). A query must specify the **exact same collation** as the index to use it. Indexes created with default parameters do not include collation and cannot serve collation-aware queries.

```javascript
// Case-insensitive index
db.users.createIndex(
  { username: 1 },
  { collation: { locale: "en", strength: 2 } }
)

// Query MUST specify matching collation
db.users.find({ username: "JohnDoe" }).collation({ locale: "en", strength: 2 })
```

Source: [Medium - MongoDB query ignores indexes? Check collation](https://aleksandr-matiev.medium.com/mongodb-query-ignores-indexes-check-collation-ae326f6fa96f)

### 1.8 Detecting Unused Indexes with $indexStats

The `$indexStats` aggregation stage returns usage statistics for each index on a collection. Use it to identify indexes that are never queried and can be safely dropped, reducing write overhead and cache consumption.

```javascript
db.orders.aggregate([{ $indexStats: {} }])
```

Each document in the result contains:
- `name`: The index name
- `accesses.ops`: Total number of operations that used this index
- `accesses.since`: Timestamp when the counter was last reset (typically server start)

**Decision rule:** If `accesses.ops` is 0 and the index has been tracked for at least 7 days of representative traffic, the index is a candidate for removal. Before dropping, verify it is not used by infrequent batch jobs or reporting queries that run less often than the monitoring window.

### 1.9 Forcing Index Selection with hint()

The `hint()` method forces the query planner to use a specific index, bypassing cost-based plan selection.

```javascript
db.orders.find({ customerId: "abc123" }).hint({ customerId: 1, createdAt: -1 })
```

**When to use hint():**
- Benchmarking: comparing two index candidates on the same query
- Working around a known planner regression where the wrong index is selected
- Testing whether a new index would improve a slow query before committing to it

**When not to use hint():**
- In production application code as a permanent fixture -- it prevents the planner from adapting to data distribution changes
- Prefer index filters (Section 3.5) for persistent overrides, since they are server-side and do not require application changes

### 1.10 Read Concern and Read Preference Impact

**Read preference** controls which replica set member serves the query:

| Mode | Behavior | Performance Trade-off |
|---|---|---|
| `primary` | Always reads from primary | Highest consistency, single-node bottleneck |
| `primaryPreferred` | Primary, fallback to secondary | Marginal availability gain |
| `secondary` | Only secondaries | Offloads primary; may return stale data |
| `secondaryPreferred` | Secondary, fallback to primary | Common for analytics workloads |
| `nearest` | Lowest network latency member | Best latency; no consistency guarantee |

Use `maxStalenessSeconds` to avoid reading from excessively lagged secondaries.

**Read concern** controls the consistency/isolation level of returned data:

| Level | Behavior | Latency Impact |
|---|---|---|
| `local` | Returns most recent data on the queried node | Lowest latency (default) |
| `available` | Like local, but may return orphaned docs in sharded clusters | Lowest latency |
| `majority` | Returns data acknowledged by majority of members | Slightly higher latency |
| `linearizable` | Confirms no stale reads (primary only) | Highest latency; use maxTimeMS |
| `snapshot` | Point-in-time snapshot (multi-doc transactions) | Transaction overhead |

**Causal consistency sessions** allow reading your own writes from secondaries by combining `majority` write concern with `majority` read concern in a causal session.

Source: [MongoDB Docs - Read Preference](https://www.mongodb.com/docs/manual/core/read-preference/), [MongoDB Docs - Read Concern](https://www.mongodb.com/docs/manual/reference/read-concern/), [MongoDB - Performance Best Practices](https://www.mongodb.com/resources/products/capabilities/performance-best-practices-transactions-and-read-write-concerns)

---

## 2. Aggregation Framework Optimization

### 2.1 Pipeline Stage Reference

Key aggregation stages and their performance characteristics:

| Stage | Purpose | Index-Eligible | Notes |
|---|---|---|---|
| `$match` | Filter documents | Yes | Place as early as possible |
| `$project` / `$addFields` | Reshape documents | No | Reduces downstream payload |
| `$group` | Aggregate values | No (but benefits from preceding $match) | Memory-intensive for large cardinalities |
| `$sort` | Order results | Yes (if first or after $match) | 100 MB memory limit without allowDiskUse |
| `$limit` | Cap result count | No | Place after `$sort` to enable sort-limit coalescence |
| `$skip` | Offset results | No | Combine with $limit for pagination |
| `$lookup` | Left outer join | Yes (on foreign collection) | Index the foreignField; can be expensive |
| `$unwind` | Deconstruct arrays | No | Multiplies document count; use preserveNullAndEmptyArrays |
| `$facet` | Parallel sub-pipelines | No | Each facet processes the full input; use $match before |
| `$merge` / `$out` | Write results | No | $merge supports incremental; $out replaces collection |
| `$unionWith` | Combine collections | Partial | Pipeline within $unionWith can use indexes |
| `$graphLookup` | Recursive graph traversal | Yes (on connectToField) | 100 MB RAM default; auto-spills to disk |
| `$densify` | Fill gaps in sequences | No | Useful for time-series data |
| `$fill` | Fill missing values | No | Window-based or linear interpolation |
| `$setWindowFields` | Window functions | No | Supports $sum, $avg, $rank, $denseRank, $shift, etc. |
| `$vectorSearch` | Semantic vector search | Uses vector index | Must be first stage; Atlas or 8.2+ required |

Source: [MongoDB Docs - Aggregation Stages](https://www.mongodb.com/docs/manual/reference/operator/aggregation-pipeline/), [Practical MongoDB Aggregations](https://www.practical-mongodb-aggregations.com/guides/performance.html)

### 2.2 Pipeline Optimization Strategies

**1. Filter early with $match:**
Place `$match` as the first stage whenever possible. When `$match` is at the start, the query planner can use indexes to avoid collection scans. The optimizer automatically moves `$match` stages forward when safe (pipeline coalescence).

**2. Project early to reduce payload:**
Use `$project` or `$addFields` early to drop unnecessary fields, reducing memory consumption in downstream stages.

**3. Pipeline coalescence:**
MongoDB's optimizer automatically combines adjacent compatible stages:
- `$match` + `$match` -> single `$match`
- `$sort` + `$sort` -> single `$sort` (last wins)
- `$sort` + `$limit` -> combined sort-limit (reduces memory)
- `$project` + `$project` -> single `$project`

**4. allowDiskUse:**
When pipeline stages exceed the 100 MB memory limit, set `{ allowDiskUse: true }` to spill to disk. This prevents OOM errors but adds I/O latency. Starting in MongoDB 6.0, `allowDiskUseByDefault` is true.

**5. $sort + $limit optimization:**
When `$sort` is followed by `$limit`, the optimizer combines them so only the top N documents are tracked in memory, drastically reducing memory consumption.

**6. Index-backed $sort:**
If `$sort` immediately follows `$match` (or is the first stage), and an index covers the sort fields, MongoDB uses the index order and avoids an in-memory sort.

Source: [MongoDB Docs - Aggregation Pipeline Optimization](https://www.mongodb.com/docs/manual/core/aggregation-pipeline-optimization/), [GeeksforGeeks - Aggregation Pipeline Optimization](https://www.geeksforgeeks.org/mongodb/aggregation-pipeline-optimization/)

### 2.3 $lookup Optimization

`$lookup` performs a left outer join and can be the most expensive stage in a pipeline.

**Optimization techniques:**

1. **Index the foreign field:** Create an index on the `foreignField` in the joined collection. Without it, every `$lookup` performs a collection scan on the foreign collection.
2. **Filter before $lookup:** Use `$match` before `$lookup` to reduce the number of documents that trigger lookups.
3. **Use $unwind + $match coalescence:** When `$lookup` is followed by `$unwind` and `$match` on the joined array, MongoDB can optimize this into an internal pipeline that filters during the join.
4. **Correlated subpipeline:** Use the `let` + `pipeline` form of `$lookup` for complex join conditions, and include a `$match` using `$expr` in the sub-pipeline to use indexes.
5. **Avoid $lookup in loops:** If you find yourself doing repeated lookups, consider denormalization or embedding.

Source: [OneUptime - Optimize $lookup](https://oneuptime.com/blog/post/2026-03-31-mongodb-optimize-lookup-aggregation/view)

### 2.4 $graphLookup Performance

`$graphLookup` performs recursive traversal (graph walking) within or across collections.

- **Memory limit:** 100 MB by default; automatically spills to disk when exceeded
- **Index requirement:** Create an index on the `connectToField` for efficient traversal
- **maxDepth:** Always set `maxDepth` to prevent unbounded recursion
- **restrictSearchWithMatch:** Use this option to prune branches early and reduce traversal scope

Source: [MongoDB Docs - $graphLookup](https://www.mongodb.com/docs/manual/reference/operator/aggregation/graphlookup/)

### 2.5 $vectorSearch in Pipelines

`$vectorSearch` enables approximate nearest neighbor (ANN) search using the HNSW (Hierarchical Navigable Small Worlds) algorithm.

**Constraints:**
- Must be the **first stage** in the pipeline
- Requires a vector search index (Atlas Search or MongoDB 8.2+ Enterprise/Community)
- Cannot be used inside `$lookup`
- Optimal recall is 90-95% overlap with exact search, with significantly lower latency

**Pattern:**
```javascript
db.products.aggregate([
  {
    $vectorSearch: {
      index: "vector_index",
      path: "embedding",
      queryVector: [0.1, 0.2, ...],
      numCandidates: 200,
      limit: 10
    }
  },
  { $match: { status: "published" } },
  { $project: { title: 1, score: { $meta: "vectorSearchScore" } } }
])
```

Source: [MongoDB Docs - $vectorSearch](https://www.mongodb.com/docs/manual/reference/operator/aggregation/vectorsearch/)

---

## 3. Query Planning

### 3.1 explain() Output

The `explain()` method reveals how MongoDB executes a query. Three verbosity modes:

| Mode | What It Shows | Use Case |
|---|---|---|
| `queryPlanner` (default) | Winning plan, rejected plans, index used | Quick check of plan selection |
| `executionStats` | Actual execution metrics (docs examined, keys examined, time) | Performance analysis |
| `allPlansExecution` | Stats for all candidate plans during the trial period | Deep plan comparison |

**Key metrics in executionStats:**

```javascript
{
  executionStats: {
    nReturned: 42,              // Documents returned
    totalKeysExamined: 42,      // Index keys scanned
    totalDocsExamined: 42,      // Documents fetched from disk/cache
    executionTimeMillis: 3,     // Total execution time
    executionStages: {
      stage: "IXSCAN",         // Index scan (good)
      // vs "COLLSCAN"         // Collection scan (bad for large collections)
    }
  }
}
```

**Performance indicators:**

| Ratio | Ideal | Problem Indicator |
|---|---|---|
| `nReturned / totalKeysExamined` | Close to 1.0 | Low ratio = scanning excess keys |
| `nReturned / totalDocsExamined` | Close to 1.0 | Low ratio = fetching excess docs |
| `totalDocsExamined` | 0 for covered queries | Non-zero means document fetch required |

Source: [MongoDB Docs - Explain Results](https://www.mongodb.com/docs/manual/reference/explain-results/)

### 3.2 Plan Cache

MongoDB caches winning query plans to avoid re-evaluating candidates on every execution.

**Plan cache lifecycle:**
1. First execution of a query shape triggers a trial period evaluating all candidate plans
2. The winning plan is cached, keyed by the query shape (combination of query predicate structure, sort, and projection)
3. Subsequent queries with the same shape reuse the cached plan
4. Cache entries are invalidated when: indexes are created/dropped, the collection receives a certain number of writes, or the server restarts

**Plan cache commands:**
```javascript
// View cached plans for a collection
db.orders.aggregate([{ $planCacheStats: {} }])

// Clear the plan cache for a collection
db.orders.getPlanCache().clear()

// Clear a specific plan cache entry
db.orders.getPlanCache().clearPlansByQueryShape(queryShape)
```

**Note:** `explain()` never reads from or writes to the plan cache. It always generates fresh candidate plans.

Source: [MongoDB Docs - Query Plans](https://www.mongodb.com/docs/manual/core/query-plans/), [MongoDB Docs - $planCacheStats](https://www.mongodb.com/docs/manual/reference/operator/aggregation/plancachestats/)

### 3.3 Query Shapes and Hashes

A **query shape** is the normalized form of a query -- it captures the structure of the predicate, sort, and projection while ignoring specific values. Two queries with the same shape share a plan cache entry.

**Identifying query shapes:**
- `queryHash`: A hex hash of the query shape (deprecated in MongoDB 8.0+)
- `planCacheShapeHash`: Replacement for queryHash starting in MongoDB 8.0
- `planCacheKey`: Hash of both the query shape AND the available indexes; changes when indexes change

Source: [MongoDB Docs - Explain Results v8.0](https://www.mongodb.com/docs/v8.0/reference/explain-results/)

### 3.4 SBE (Slot-Based Execution Engine)

The Slot-Based Execution Engine (SBE) is MongoDB's modern query execution engine, replacing the classic engine for eligible queries.

**Architecture:**
- Uses "slots" to represent intermediate data during execution, similar to CPU registers
- Enables better CPU cache utilization and reduced memory allocations
- More modular query plan building with composable operators

**SBE eligibility (MongoDB 7.0+):**
- SBE handles `find`, `count`, `distinct`, and aggregation pipelines with supported stages
- Falls back to the classic engine for unsupported stages or complex aggregation patterns
- Controlled by the `internalQueryFrameworkControl` parameter

**SBE vs Classic engine in explain:**
The explain output structure differs depending on which engine runs the query. SBE output shows slot-based plan stages (`sbe_plan` section) rather than the classic tree of stages.

**Performance impact:**
SBE can deliver significant performance improvements for eligible queries, particularly those with multiple predicates, complex sorts, or group operations, due to reduced per-document processing overhead.

Source: [MongoDB Docs - Slot-Based Execution Engine](https://www.mongodb.com/docs/manual/reference/sbe/), [Mydbops - Unlocking Performance: MongoDB SBE](https://www.mydbops.com/blog/unlocking-performance-mongodbs-slot-based-query-execution-engine-sbe)

### 3.5 Index Filters

Index filters override the query planner's index selection for a given query shape. They force MongoDB to only consider specific indexes.

```javascript
db.runCommand({
  planCacheSetFilter: "orders",
  query: { customerId: 1, status: 1 },
  indexes: [{ customerId: 1, status: 1 }]
})
```

**Use sparingly:** Index filters bypass the optimizer's cost-based selection. Use them only to work around known planner regressions, and document the reason.

Source: [MongoDB Docs - Query Plans](https://www.mongodb.com/docs/manual/core/query-plans/)

---

## 4. WiredTiger Caching

### 4.1 Cache Architecture

WiredTiger uses two layers of caching:

1. **WiredTiger internal cache** -- An in-memory B-tree representation of data pages, controlled by `cacheSizeGB`
2. **Filesystem cache** -- The OS page cache that buffers compressed on-disk data; managed by the operating system

Data flows: disk (compressed) -> filesystem cache (compressed) -> WiredTiger cache (uncompressed, with dirty modifications).

**Default cache size:**
```
max(256 MB, (totalRAM - 1 GB) / 2)
```

For a 16 GB server, the default WiredTiger cache is ~7.5 GB. The remaining memory is available for the filesystem cache, connections, and the operating system.

Source: [MongoDB Docs - WiredTiger Storage Engine](https://www.mongodb.com/docs/manual/core/wiredtiger/), [Percona - Tuning WiredTiger Cache](https://www.percona.com/blog/mongodb-101-how-to-tune-your-mongodb-configuration-after-upgrading-to-more-memory/)

### 4.2 Cache Sizing Guidance

| Scenario | Recommended cacheSizeGB | Rationale |
|---|---|---|
| Dedicated MongoDB server | 50-60% of RAM | Leaves room for filesystem cache and OS |
| Shared server | 25-40% of RAM | Prevents starving other processes |
| Atlas M10-M40 | Managed by Atlas | Atlas auto-tunes; do not override |
| Atlas M50+ | Configurable via cluster config | Monitor before changing |

**Rule of thumb:** The default formula `(RAM - 1 GB) / 2` yields ~50% of RAM, which is already in the recommended range. Override `cacheSizeGB` only when the default does not fit your workload -- for example, on a shared server where 50% is too generous, or when monitoring shows the working set exceeds the default cache. If the cache hit ratio drops below 95%, consider increasing `cacheSizeGB` or reducing the working set.

**Configuration:**
```yaml
# mongod.conf
storage:
  wiredTiger:
    engineConfig:
      cacheSizeGB: 8
```

Or at startup: `mongod --wiredTigerCacheSizeGB 8`

Source: [OneUptime - Configure WiredTiger Cache Size](https://oneuptime.com/blog/post/2026-03-31-mongodb-how-to-configure-wiredtiger-cache-size-in-mongodb/view), [OneUptime - Memory and Cache Tuning](https://oneuptime.com/blog/post/2026-03-31-mongodb-memory-cache-tuning/view)

### 4.3 Eviction

WiredTiger eviction reclaims cache space by writing dirty pages to disk and removing clean pages.

**Eviction thresholds:**

| Parameter | Default | Behavior |
|---|---|---|
| `eviction_target` | 80% | Cache usage level WiredTiger tries to maintain |
| `eviction_trigger` | 95% | Application threads start evicting (causes latency spikes) |
| `eviction_dirty_target` | 5% | Target for dirty data percentage |
| `eviction_dirty_trigger` | 20% | Application threads evict dirty pages (severe latency) |

**When application threads evict:** If cache usage exceeds `eviction_trigger` or dirty data exceeds `eviction_dirty_trigger`, application threads are forced to perform eviction work before their own operations, causing latency spikes in user-facing queries.

**Tuning eviction:**
- If you see spikes correlated with eviction, lower `eviction_dirty_target` to force earlier background eviction
- Increase eviction threads (`eviction=(threads_min=4,threads_max=8)`) for write-heavy workloads
- Hard ceiling: never set `cacheSizeGB` above 70% of RAM (the filesystem cache and OS need the remaining 30%+). The 50-60% recommendation in Section 4.2 is the optimal target; 70% is the absolute maximum.

Source: [WiredTiger Docs - Cache and Eviction Tuning](https://source.wiredtiger.com/mongodb-3.4/tune_cache.html), [OneUptime - WiredTiger Cache Full](https://oneuptime.com/blog/post/2026-03-31-mongodb-how-to-fix-mongoerror-wiredtiger-error-cache-full-in-mongodb/view)

### 4.4 Cache Diagnostics

Monitor cache health via `serverStatus`:

```javascript
db.serverStatus().wiredTiger.cache
```

**Key metrics:**

| Metric | Healthy Value | Action If Unhealthy |
|---|---|---|
| `bytes currently in the cache` / `maximum bytes configured` | < 80% | Increase cacheSizeGB or reduce working set |
| `pages read into cache` vs `pages requested from the cache` | Hit ratio > 95% | Low hit ratio = cache too small |
| `tracked dirty bytes in the cache` / `maximum bytes configured` | < 5% | High dirty ratio = write pressure; tune eviction |
| `pages evicted by application threads` | Near 0 | Non-zero means cache pressure is throttling queries |
| `cache overflow table entries` | 0 | Non-zero indicates severe cache pressure |

**Atlas-specific:** In Atlas, cache metrics are available in the Metrics tab under "WiredTiger Cache" and "WiredTiger Tickets." Atlas alerts can be configured for cache utilization thresholds.

Source: [MongoDB Docs - FAQ Diagnostics](https://www.mongodb.com/docs/manual/faq/diagnostics/), [OneUptime - WiredTiger Statistics Performance Tuning](https://oneuptime.com/blog/post/2026-03-31-mongodb-wiredtiger-statistics-performance-tuning/view)

---

## 5. Query Profiling

### 5.1 Database Profiler

The MongoDB database profiler captures operation data in the `system.profile` capped collection.

**Profiling levels:**

| Level | Behavior | Overhead |
|---|---|---|
| 0 | Off | None |
| 1 | Log operations slower than `slowms` | Low (production-safe) |
| 2 | Log all operations | High (testing/debugging only) |

**Configuration:**
```javascript
// Enable profiling for slow queries (> 200ms)
db.setProfilingLevel(1, { slowms: 200 })

// Enable profiling for all operations (level 2)
db.setProfilingLevel(2)

// Disable profiling
db.setProfilingLevel(0)

// Check current profiling level
db.getProfilingStatus()
```

**At startup:**
```yaml
# mongod.conf
operationProfiling:
  mode: slowOp
  slowOpThresholdMs: 200
```

**Important:** Profiling settings are per-database. Setting via command line or config file applies the default to all databases. Level 2 profiling ignores `slowms` and `filter` settings.

Source: [MongoDB Docs - Database Profiler](https://www.mongodb.com/docs/manual/tutorial/manage-the-database-profiler/), [MongoDB Docs - db.setProfilingLevel()](https://www.mongodb.com/docs/manual/reference/method/db.setprofilinglevel/)

### 5.2 Querying system.profile

```javascript
// Find the 5 slowest queries in the last hour
db.system.profile.find({
  ts: { $gt: new Date(Date.now() - 3600000) }
}).sort({ millis: -1 }).limit(5)

// Find collection scans (COLLSCAN)
db.system.profile.find({
  "planSummary": "COLLSCAN"
})

// Find queries that examined many documents relative to returned
db.system.profile.find({
  $expr: { $gt: ["$docsExamined", { $multiply: ["$nreturned", 10] }] }
})
```

**Key fields in system.profile documents:**

| Field | Description |
|---|---|
| `op` | Operation type (query, insert, update, remove, command) |
| `ns` | Namespace (database.collection) |
| `millis` | Execution time in milliseconds |
| `planSummary` | Summary of the execution plan (IXSCAN, COLLSCAN) |
| `keysExamined` | Number of index keys scanned |
| `docsExamined` | Number of documents examined |
| `nreturned` | Number of documents returned |
| `command` | The full command/query document |

Source: [MongoDB Docs - Find Slow Queries](https://www.mongodb.com/docs/manual/tutorial/find-slow-queries-with-database-profiler/)

### 5.3 $currentOp

`$currentOp` shows currently running operations, useful for identifying long-running queries in real time:

```javascript
// Find operations running longer than 10 seconds
db.adminCommand({
  currentOp: true,
  "active": true,
  "secs_running": { "$gt": 10 }
})

// Or via aggregation (more flexible)
db.aggregate([
  { $currentOp: { allUsers: true, localOps: true } },
  { $match: { active: true, microsecs_running: { $gt: 10000000 } } }
])
```

**Kill a long-running operation:**
```javascript
db.killOp(<opId>)
```

Source: [MongoDB Docs - Database Profiler](https://www.mongodb.com/docs/manual/tutorial/manage-the-database-profiler/)

### 5.4 Atlas Performance Advisor

**What it does:**
- Continuously monitors queries slower than the slow operation threshold
- Analyzes execution plans and identifies missing indexes
- Provides specific `createIndex()` recommendations with projected impact
- Available on M10+ dedicated tiers

**Atlas managed slow operation threshold:**
Atlas uses a dynamic threshold that adjusts based on the average operation execution time. If you opt out, it falls back to a fixed 100 ms threshold.

**Atlas Query Profiler:**
A web UI that surfaces slow operation data without requiring direct access to `system.profile`. It shows:
- Operation type and namespace
- Execution time distribution
- Index usage and scan types
- Filter and sort patterns

Source: [MongoDB Docs - Analyze Slow Queries](https://www.mongodb.com/docs/atlas/analyze-slow-queries/), [MongoDB Docs - Query Profiler](https://www.mongodb.com/docs/atlas/tutorial/query-profiler/?presentation=true), [OneUptime - Atlas Performance Advisor](https://oneuptime.com/blog/post/2026-03-31-mongodb-how-to-use-mongodb-atlas-performance-advisor/view)

### 5.5 mongotop and mongostat

**mongostat:** Real-time server statistics dashboard:
```bash
mongostat --host localhost:27017 --authenticationDatabase admin -u admin -p
```
Displays: insert/query/update/delete ops/sec, getmore, command, dirty%, used%, flushes, vsize, res, qrw, arw, net_in, net_out, conn, time.

**mongotop:** Per-collection time breakdown:
```bash
mongotop 5  # Refresh every 5 seconds
```
Shows time spent reading and writing to each collection, useful for identifying hot collections.

Source: [OneUptime - Monitor MongoDB Performance](https://oneuptime.com/blog/post/2025-12-15-monitor-mongodb-performance/view)

### 5.6 Log-Based Slow Query Analysis

MongoDB logs all operations exceeding the slow operation threshold to the mongod log. Log entries include:

- `planSummary` for quick identification of COLLSCAN vs IXSCAN
- `durationMillis` for execution time
- `keysExamined` and `docsExamined` for efficiency ratios
- The query filter and sort specification

**Structured log format (MongoDB 4.4+):** Logs are JSON-formatted, making them parseable with tools like `jq`:

```bash
# Find all slow queries with collection scans
cat mongod.log | jq 'select(.attr.planSummary == "COLLSCAN")'
```

Source: [Medium - Diagnose Slow Queries in MongoDB](https://medium.com/mongodb/your-guide-to-diagnose-slow-queries-in-mongodb-e1ff19bf74f6), [Foojay - Complete Guide to Diagnose Slow Queries](https://foojay.io/today/your-complete-guide-to-diagnose-slow-queries-in-mongodb/)

---

## 6. Internal Algorithms

### 6.1 WiredTiger B-Tree Structure

WiredTiger organizes data as B-tree structures on disk and in memory.

**Page types:**

| Page Type | Contents | Role |
|---|---|---|
| Root page | Keys + child page references | Entry point; single page |
| Internal pages | Keys + child page references (WT_REF) | Guide traversal to leaf pages |
| Leaf pages | Keys + values (WT_ROW for row-store) | Store actual document data |
| Overflow pages | Large keys or values | Stored separately when exceeding page size limits |

**Page configuration:**

| Parameter | Default | Purpose |
|---|---|---|
| `internal_page_max` | 4 KB | Maximum internal page size |
| `leaf_page_max` | 32 KB | Maximum leaf page size |
| `leaf_value_max` | 64 MB | Maximum value size before overflow |

Larger page sizes can improve sequential read performance but increase memory consumption and eviction cost. Smaller pages improve random read performance but increase tree depth.

Source: [WiredTiger Docs - B-Trees Architecture Guide](https://source.wiredtiger.com/mongodb-5.0/arch-btree.html), [WiredTiger Docs - Data File Format](http://source.wiredtiger.com/mongodb-4.4/arch-data-file.html)

### 6.2 Lock-Free Reads and Skip Lists

WiredTiger uses lock-free data structures for in-memory page modifications:

**Skip lists for inserts:**
- Newly inserted elements are stored in skip lists (WT_INSERT structures)
- A separate skip list exists for the gap between each pair of keys on a page, plus the gaps before the first key and after the last key
- Skip lists are search-optimized singly linked lists with multiple levels, providing O(log n) search, insert, and delete
- Almost all operations on these structures are lock-free, enabling high concurrency

**Hazard pointers for reads:**
- Read operations use hazard pointers to mark pages they are actively accessing
- The cache eviction system checks hazard pointers before evicting a page; if a hazard pointer references a page, eviction skips it
- This mechanism allows readers to proceed without acquiring locks, while preventing the eviction system from reclaiming pages still in use

**Result:** Readers never block writers, and writers never block readers. Only concurrent writers to the same document contend.

Source: [MongoDB Engineering Blog - Lock-Free B-Tree](https://www.mongodb.com/company/blog/engineering/to-lock-or-not-mongodbs-lock-free-b-tree-unlocks-throughput), [WiredTiger Docs - Cache Architecture](https://source.wiredtiger.com/develop/arch-cache.html)

### 6.3 MVCC (Multi-Version Concurrency Control)

WiredTiger implements MVCC to provide snapshot isolation:

**How it works:**
1. At the start of every read operation, WiredTiger captures a point-in-time snapshot of the data
2. The snapshot provides a consistent view -- the operation sees all data committed before the snapshot and none committed after
3. Write operations create new versions of documents rather than modifying in place
4. Old versions are retained until no active snapshot references them, then garbage collected

**Transaction visibility:**
- Each transaction has a read timestamp that determines which versions are visible
- WiredTiger maintains a list of all active transactions and their read timestamps
- The oldest active read timestamp determines the "oldest reader" -- versions older than this can be garbage collected

**Implications for performance:**
- Long-running transactions or cursors prevent garbage collection, increasing cache pressure
- The `oldest_timestamp` and `stable_timestamp` in WiredTiger control version retention
- Monitor `serverStatus().wiredTiger.transaction` for "transaction range of IDs currently pinned" growing large

Source: [MongoDB Docs - WiredTiger Storage Engine](https://www.mongodb.com/docs/manual/core/wiredtiger/), [Database of Databases - WiredTiger](https://dbdb.io/db/wiredtiger)

### 6.4 Document-Level Concurrency

WiredTiger provides document-level concurrency control:

- Multiple clients can modify **different documents** in the same collection simultaneously
- Concurrent writes to the **same document** are serialized via optimistic concurrency control: if a write conflict is detected, MongoDB transparently retries the operation
- This is a major improvement over earlier storage engines (MMAPv1) that used collection-level locking

**Write tickets:**
WiredTiger uses a ticketing system to limit the number of concurrent read and write operations:
- Before MongoDB 7.0: a static default of 128 read + 128 write tickets. MongoDB 7.0+ replaces the fixed cap with a dynamic, self-tuning concurrency algorithm; override with `storageEngineConcurrentReadTransactions` / `storageEngineConcurrentWriteTransactions` only when instructed.
- When tickets are exhausted, operations queue, creating backpressure
- Monitor via `serverStatus().wiredTiger.concurrentTransactions`

Source: [MongoDB Docs - WiredTiger Storage Engine](https://www.mongodb.com/docs/manual/core/wiredtiger/), [Severalnines - Overview of WiredTiger](https://severalnines.com/blog/overview-wiredtiger-storage-engine-mongodb/)

### 6.5 Compression

WiredTiger supports multiple compression algorithms that affect query performance through I/O reduction:

| Algorithm | Ratio | CPU Cost | Use Case |
|---|---|---|---|
| snappy (default) | Moderate | Low | General purpose; good balance |
| zlib | High | Moderate | Storage-constrained; archival data |
| zstd | High | Low-Moderate | Best ratio-to-CPU for most workloads |
| none | 1:1 | None | Maximum read performance; RAM-rich environments |

**Important:** Compression applies to data on disk and in the filesystem cache. Data in the WiredTiger internal cache is always uncompressed. This means the WiredTiger cache holds larger representations than what is on disk, and the cache-to-disk size ratio is not 1:1.

Prefix compression is enabled by default for indexes, reducing index size and improving cache efficiency.

Source: [MongoDB Docs - WiredTiger Storage Engine](https://www.mongodb.com/docs/manual/core/wiredtiger/), [WiredTiger Docs - Page Size and Compression](https://source.wiredtiger.com/mongodb-3.4/tune_page_size_and_comp.html)

---

## 7. Quick-Reference Checklists

### 7.1 Index Design Checklist

- [ ] Identify top 5 query patterns from profiler or Performance Advisor
- [ ] Apply ESR rule to each pattern for compound index field ordering
- [ ] Verify covered queries where possible (projection matches index)
- [ ] Check for unused indexes (`$indexStats`) and drop them
- [ ] Use partial indexes for queries that always filter on a subset
- [ ] Set collation on indexes if queries use case-insensitive comparison
- [ ] Test with `explain("executionStats")` to verify index usage
- [ ] Confirm `nReturned / totalKeysExamined` ratio is close to 1.0

### 7.2 Aggregation Performance Checklist

- [ ] `$match` is the first stage (or immediately follows `$vectorSearch`)
- [ ] Unnecessary fields are dropped via `$project` before expensive stages
- [ ] `$lookup` foreignField is indexed in the foreign collection
- [ ] `$sort` is backed by an index or followed by `$limit`
- [ ] `$graphLookup` has `maxDepth` and `restrictSearchWithMatch` set
- [ ] `allowDiskUse` is enabled for pipelines that may exceed 100 MB
- [ ] Pipeline is tested with `explain()` to check for COLLSCAN stages

### 7.3 Cache Health Checklist

- [ ] `cacheSizeGB` is set to 50-60% of available RAM (dedicated server)
- [ ] Cache hit ratio > 95% (`serverStatus().wiredTiger.cache`)
- [ ] Dirty bytes < 5% of cache (`tracked dirty bytes in the cache`)
- [ ] Application-thread evictions near zero (`pages evicted by application threads`)
- [ ] No long-running transactions pinning old snapshots
- [ ] WiredTiger tickets (read/write) are not exhausted

### 7.4 Profiling Setup Checklist

- [ ] Profiling level 1 enabled on production databases
- [ ] `slowms` tuned to application SLA (e.g., 100-200 ms)
- [ ] `system.profile` collection is reviewed weekly for COLLSCAN patterns
- [ ] Atlas Performance Advisor recommendations are reviewed monthly
- [ ] Structured logs are aggregated for trend analysis
- [ ] `$currentOp` monitoring is available for on-call incident response

---

## 8. Common Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| Missing index on `$lookup` foreignField | Every lookup triggers a COLLSCAN on the foreign collection | Index the foreignField |
| `$sort` without `$limit` on large result sets | 100 MB memory limit, spill to disk | Add `$limit` after `$sort`; use index-backed sort |
| Range field before sort field in compound index | In-memory sort required; ESR violation | Reorder index fields: Equality -> Sort -> Range |
| Profiling level 2 in production | Logs every operation; significant overhead | Use level 1 with appropriate `slowms` |
| Oversized WiredTiger cache (>70% RAM) | Starves filesystem cache and OS | Set to 50-60% of RAM |
| Long-running cursors or transactions | Pin old MVCC snapshots; cache pressure grows | Set timeouts; batch processing |
| Unused indexes left in place | Extra write overhead on every insert/update | Audit with `$indexStats`; drop unused indexes |
| Querying with collation but index lacks collation | Index is ignored; falls back to COLLSCAN | Create index with matching collation |

---

## Sources

1. [MongoDB Docs - Query Optimization](https://www.mongodb.com/docs/manual/core/query-optimization/)
2. [MongoDB Docs - ESR Guideline](https://www.mongodb.com/docs/manual/tutorial/equality-sort-range-guideline/)
3. [MongoDB Docs - Partial Indexes](https://www.mongodb.com/docs/manual/core/index-partial/)
4. [MongoDB Docs - Compound Indexes](https://www.mongodb.com/docs/manual/core/indexes/index-types/index-compound/)
5. [MongoDB Docs - Aggregation Pipeline Optimization](https://www.mongodb.com/docs/manual/core/aggregation-pipeline-optimization/)
6. [MongoDB Docs - Aggregation Stages](https://www.mongodb.com/docs/manual/reference/operator/aggregation-pipeline/)
7. [MongoDB Docs - Explain Results](https://www.mongodb.com/docs/manual/reference/explain-results/)
8. [MongoDB Docs - Slot-Based Execution Engine](https://www.mongodb.com/docs/manual/reference/sbe/)
9. [MongoDB Docs - Query Plans](https://www.mongodb.com/docs/manual/core/query-plans/)
10. [MongoDB Docs - WiredTiger Storage Engine](https://www.mongodb.com/docs/manual/core/wiredtiger/)
11. [MongoDB Docs - Database Profiler](https://www.mongodb.com/docs/manual/tutorial/manage-the-database-profiler/)
12. [MongoDB Docs - Find Slow Queries](https://www.mongodb.com/docs/manual/tutorial/find-slow-queries-with-database-profiler/)
13. [MongoDB Docs - Analyze Slow Queries (Atlas)](https://www.mongodb.com/docs/atlas/analyze-slow-queries/)
14. [MongoDB Docs - Read Preference](https://www.mongodb.com/docs/manual/core/read-preference/)
15. [MongoDB Docs - Read Concern](https://www.mongodb.com/docs/manual/reference/read-concern/)
16. [MongoDB Docs - $vectorSearch](https://www.mongodb.com/docs/manual/reference/operator/aggregation/vectorsearch/)
17. [MongoDB Docs - $graphLookup](https://www.mongodb.com/docs/manual/reference/operator/aggregation/graphlookup/)
18. [MongoDB Docs - $planCacheStats](https://www.mongodb.com/docs/manual/reference/operator/aggregation/plancachestats/)
19. [MongoDB Engineering Blog - Lock-Free B-Tree](https://www.mongodb.com/company/blog/engineering/to-lock-or-not-mongodbs-lock-free-b-tree-unlocks-throughput)
20. [MongoDB - Performance Best Practices: Transactions and Read/Write Concerns](https://www.mongodb.com/resources/products/capabilities/performance-best-practices-transactions-and-read-write-concerns)
21. [WiredTiger Docs - B-Trees Architecture Guide](https://source.wiredtiger.com/mongodb-5.0/arch-btree.html)
22. [WiredTiger Docs - Cache and Eviction Tuning](https://source.wiredtiger.com/mongodb-3.4/tune_cache.html)
23. [WiredTiger Docs - Cache Architecture](https://source.wiredtiger.com/develop/arch-cache.html)
24. [WiredTiger Docs - Data File Format](http://source.wiredtiger.com/mongodb-4.4/arch-data-file.html)
25. [Percona - Tuning WiredTiger Cache After Memory Upgrade](https://www.percona.com/blog/mongodb-101-how-to-tune-your-mongodb-configuration-after-upgrading-to-more-memory/)
26. [Mydbops - Unlocking Performance: MongoDB SBE](https://www.mydbops.com/blog/unlocking-performance-mongodbs-slot-based-query-execution-engine-sbe)
27. [Severalnines - Overview of WiredTiger Storage Engine](https://severalnines.com/blog/overview-wiredtiger-storage-engine-mongodb/)
28. [Database of Databases - WiredTiger](https://dbdb.io/db/wiredtiger)
29. [Practical MongoDB Aggregations - Performance](https://www.practical-mongodb-aggregations.com/guides/performance.html)
30. [OneUptime - ESR Rule for Compound Index Design](https://oneuptime.com/blog/post/2026-03-31-mongodb-esr-rule-compound-index/view)
31. [OneUptime - Optimize $lookup Performance](https://oneuptime.com/blog/post/2026-03-31-mongodb-optimize-lookup-aggregation/view)
32. [OneUptime - WiredTiger Cache Configuration](https://oneuptime.com/blog/post/2026-03-31-mongodb-how-to-configure-wiredtiger-cache-size-in-mongodb/view)
33. [OneUptime - Atlas Performance Advisor](https://oneuptime.com/blog/post/2026-03-31-mongodb-how-to-use-mongodb-atlas-performance-advisor/view)
34. [Medium - Diagnose Slow Queries in MongoDB](https://medium.com/mongodb/your-guide-to-diagnose-slow-queries-in-mongodb-e1ff19bf74f6)
35. [Foojay - Complete Guide to Diagnose Slow Queries](https://foojay.io/today/your-complete-guide-to-diagnose-slow-queries-in-mongodb/)
36. [Medium - MongoDB Query Ignores Indexes? Check Collation](https://aleksandr-matiev.medium.com/mongodb-query-ignores-indexes-check-collation-ae326f6fa96f)
37. [Mydbops - Read Concerns in MongoDB](https://www.mydbops.com/blog/read-concerns-in-mongodb)

---

## See also

- **`mongodb-aggregation-stages-deep`** — for `$lookup` join-strategy tuning (IndexedLoopJoin vs NestedLoopJoin vs HashJoin vs DynamicIndexedLoopJoin), `$graphLookup` index requirements, `$facet` 16 MB output ceiling, `$setWindowFields` partition memory limits, and the full 100 MB-per-stage / `allowDiskUse` / `usedDisk` triage table for `explain("executionStats")` output.
