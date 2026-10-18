<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-sharding` skill.
> Sibling topics in this family are now reference files under the hubs (`mongodb-expert`, `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not** standalone
> skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that name a bare sibling
> skill; load that topic's `references/<name>.md` from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-sharding
title: MongoDB Sharding Expert
version: 1.1.0
updated: "2026-05-29"
description: >
  MongoDB sharding architecture, shard key selection (ranged, hashed, compound),
  chunk management, balancer configuration, zone sharding, targeted vs scatter-gather
  queries, resharding operations, jumbo chunk remediation, and sharded cluster
  diagnostics. Use when designing, operating, troubleshooting, or optimizing
  MongoDB sharded clusters.
  TRIGGER: choosing or refining a shard key; unbalanced data or hot-spot shards;
  balancer, zone, or chunk-size configuration; scatter-gather or slow sharded
  queries; resharding or refineCollectionShardKey; jumbo chunks; sharded cluster
  architecture review; ranged vs hashed vs compound key comparison.
  SKIP: single-replica-set index design or query tuning (use mongodb-indexes-deep
  or mongodb-query-performance); non-sharded schema modeling (use
  mongodb-schema-design); cluster sizing/capacity math (use
  mongodb-capacity-planning).
tags:
  - mongodb
  - sharding
  - distributed-systems
  - database
keywords:
  - mongodb-sharding
  - shard key
  - mongos
  - config server
  - chunk
  - balancer
  - zone sharding
  - hashed sharding
  - ranged sharding
  - compound shard key
  - resharding
  - scatter-gather
  - targeted query
  - jumbo chunk
  - moveChunk
  - chunk migration
  - sh.status
  - refineCollectionShardKey
  - reshardCollection
  - sh.shardAndDistributeCollection
  - horizontal scaling
  - data distribution
when_to_use:
  - Designing a MongoDB sharding strategy or choosing a shard key
  - Troubleshooting unbalanced data distribution or hot-spot shards
  - Configuring the balancer, zones, or chunk sizes
  - Diagnosing scatter-gather query patterns or slow sharded queries
  - Planning or executing resharding or shard key refinement operations
  - Investigating jumbo chunks, chunk splitting, or migration failures
  - Reviewing sharded cluster architecture for production readiness
  - Comparing ranged vs hashed vs compound shard key strategies
whenNotToUse:
  - Single-replica-set index design or query tuning — use mongodb-indexes-deep or mongodb-query-performance
  - Non-sharded schema modeling — use mongodb-schema-design
  - Cluster sizing and capacity math — use mongodb-capacity-planning
  - Replication and election internals for individual shards — use mongodb-replication
related_skills:
  - mongodb-expert
  - mongodb-atlas-expert
  - mongodb-replication
  - mongodb-indexes-deep
  - mongodb-query-performance
  - mongodb-schema-design
  - mongodb-capacity-planning
  - mongodb-performance-troubleshooting
references:
  - title: "MongoDB Sharding Manual"
    url: "https://www.mongodb.com/docs/manual/sharding/"
  - title: "Choose a Shard Key - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/sharding-choose-a-shard-key/"
  - title: "Hashed Sharding - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/hashed-sharding/"
  - title: "Zone Sharding - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/zone-sharding/"
  - title: "Sharded Cluster Balancer - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/sharding-balancer-administration/"
  - title: "Reshard a Collection - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/sharding-reshard-a-collection/"
  - title: "Routing with mongos - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/sharded-cluster-query-router/"
  - title: "Data Partitioning with Chunks - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/data-partitioning/"
  - title: "Troubleshoot Shard Keys - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/sharding-troubleshooting-shard-keys/"
  - title: "Performance Best Practices: Sharding - MongoDB Blog"
    url: "https://www.mongodb.com/company/blog/mongodb/performance-best-practices-sharding"
  - title: "Percona: When Should I Enable MongoDB Sharding"
    url: "https://www.percona.com/blog/when-should-i-enable-mongodb-sharding/"
  - title: "Percona: Zone Based Sharding in MongoDB"
    url: "https://www.percona.com/blog/zone-based-sharding-in-mongodb/"
  - title: "Percona: Dealing with Jumbo Chunks in MongoDB"
    url: "https://www.percona.com/blog/dealing-with-jumbo-chunks-in-mongodb/"
  - title: "MongoDB Sharding Internals Wiki"
    url: "https://github.com/mongodb/mongo/wiki/Sharding-Internals"
---

# MongoDB Sharding Expert

## 1. Overview

MongoDB sharding is the mechanism for horizontally scaling data across multiple machines. A sharded cluster distributes documents across shards based on a shard key, enabling deployments to handle datasets and throughput that exceed the capacity of a single server. This skill covers the full lifecycle: architecture, shard key design, chunk management, balancer tuning, zone-based routing, query optimization in sharded environments, resharding operations, and production diagnostics.

**When to shard:** Shard when a single replica set cannot handle the write throughput, the working set exceeds available RAM, or data volume requires distributing storage across nodes. Sharding adds operational complexity -- exhaust vertical scaling and indexing improvements first.

**When NOT to use this skill:** For single-replica-set index design or query tuning, use `mongodb-indexes-deep` or `mongodb-query-performance`. For non-sharded data modeling, use `mongodb-schema-design`. For cluster sizing and capacity math, use `mongodb-capacity-planning`. This skill assumes a sharded cluster (or a decision to build one) is already in scope.

**Source:** [MongoDB Sharding Manual](https://www.mongodb.com/docs/manual/sharding/), [Percona: When Should I Enable MongoDB Sharding](https://www.percona.com/blog/when-should-i-enable-mongodb-sharding/)

---

## 2. Sharding Architecture

### 2.1 Core Components

A MongoDB sharded cluster consists of three component types:

| Component | Role | Deployment |
|-----------|------|------------|
| **Shards** | Store the actual data partitions. Each shard is a replica set. | 2+ shards (replica sets) |
| **Config Servers (CSRS)** | Store cluster metadata: shard map, chunk ranges, zone definitions, balancer state. Must be a replica set. | 3-member replica set (dedicated) |
| **mongos** | Query router. Directs client operations to the correct shard(s) using cached metadata from config servers. Stateless -- deploy multiple for HA. | 1+ instances (co-located with app or dedicated) |

**Architecture flow:**
```
Client -> mongos -> config servers (metadata lookup)
                 -> shard1 (replica set)
                 -> shard2 (replica set)
                 -> shardN (replica set)
```

Applications connect exclusively to mongos. Never connect directly to individual shards or config servers for application operations.

### 2.2 Metadata and Routing

mongos caches the chunk-to-shard mapping from config servers. When a query arrives, mongos inspects the query filter against the shard key to determine which shard(s) hold relevant data. If the query contains the shard key or its prefix, mongos performs a **targeted operation** to specific shards. Otherwise, it broadcasts to all shards (**scatter-gather**).

To verify you are connected to a mongos instance:
```javascript
db.hello()
// Look for "msg": "isdbgrid" in the response
```

**Source:** [Routing with mongos - MongoDB Docs](https://www.mongodb.com/docs/manual/core/sharded-cluster-query-router/)

---

## 3. Shard Key Selection

The shard key is the most consequential decision in a sharding deployment. A poor shard key causes hot-spots, jumbo chunks, and scatter-gather queries that negate the benefits of horizontal scaling. The shard key is immutable once set (though it can be refined or the collection can be resharded starting in MongoDB 5.0+).

### 3.1 Four Selection Criteria

| Criterion | Goal | Failure Mode |
|-----------|------|-------------|
| **Cardinality** | High number of distinct values | Low cardinality limits maximum chunk count (e.g., sharding on `continent` caps at 7 chunks) |
| **Frequency** | Even distribution of values | High-frequency values create hot chunks and potential jumbo chunks |
| **Monotonicity** | Non-monotonic or hashed | Monotonically increasing keys (timestamps, ObjectId) route all inserts to the MaxKey chunk |
| **Query pattern** | Shard key appears in common queries | Queries without shard key become broadcast scatter-gather operations |

### 3.2 analyzeShardKey (MongoDB 7.0+)

Before committing to a shard key, use the built-in analysis tool:

```javascript
// Enable query sampling
db.adminCommand({
  configureQueryAnalyzer: "myDb.myCollection",
  mode: "full"
})

// Wait for sufficient samples, then analyze
db.adminCommand({
  analyzeShardKey: "myDb.myCollection",
  key: { userId: 1, createdAt: 1 }
})
```

The output provides `keyCharacteristics` (cardinality, frequency, monotonicity metrics) and `readWriteDistribution` (how queries and writes would route across shards).

### 3.3 Shard Key Limitations

- The shard key cannot exceed 512 bytes.
- The shard key value for a document is immutable (the document can be updated, but the shard key fields cannot change in a way that moves the document to a different chunk range -- except via `moveChunk`/resharding).
- Unique indexes must include the shard key as a prefix.
- The `_id` index is not automatically the shard key; `_id` uniqueness is per-shard unless the shard key is `_id`.

**Source:** [Choose a Shard Key - MongoDB Docs](https://www.mongodb.com/docs/manual/core/sharding-choose-a-shard-key/), [Troubleshoot Shard Keys - MongoDB Docs](https://www.mongodb.com/docs/manual/core/sharding-troubleshooting-shard-keys/)

---

## 4. Ranged vs Hashed vs Compound Shard Keys

### 4.1 Ranged Sharding

Documents are distributed based on contiguous ranges of shard key values. Documents with adjacent shard key values end up on the same shard or adjacent chunks.

**Strengths:** Efficient range queries, data locality for adjacent values.
**Weaknesses:** Monotonically increasing keys create write hot-spots; uneven distribution with skewed data.

```javascript
sh.shardCollection("myDb.orders", { orderId: 1 })
```

### 4.2 Hashed Sharding

The shard key value is hashed before determining chunk placement. MongoDB computes the hash automatically.

**Strengths:** Even write distribution regardless of key pattern; ideal for monotonically increasing keys (ObjectId, timestamps).
**Weaknesses:** Range queries become scatter-gather; equality queries on the hashed field are still targeted.

```javascript
sh.shardCollection("myDb.logs", { _id: "hashed" })
```

**Critical caveat:** Hashed indexes truncate floating-point numbers to 64-bit integers before hashing. Values like 2.3, 2.2, and 2.9 all hash to the same value. Use integer or Decimal128 types for hashed fields with numeric data.

To see a hashed value:
```javascript
convertShardKeyToHashed("user_id_12345")
```

### 4.3 Compound Shard Keys

Combine multiple fields to balance distribution with query targeting. A compound shard key can include one hashed field (at any position) starting in MongoDB 4.4+.

**Design rules for compound shard keys:**
1. Fields used in equality filters come first.
2. High-cardinality fields before low-cardinality fields.
3. Fields used in range queries come last.
4. A hashed prefix with a ranged suffix works well for high-insert workloads that also need per-entity range queries.

```javascript
// Hashed prefix for distribution, ranged suffix for query locality
sh.shardCollection("myDb.events", { tenantId: "hashed", createdAt: 1 })

// Ranged compound key for multi-tenant with time-based queries
sh.shardCollection("myDb.metrics", { customerId: 1, timestamp: 1 })
```

### 4.4 Comparison Table

| Aspect | Ranged | Hashed | Compound |
|--------|--------|--------|----------|
| Write distribution | Skewed with monotonic keys | Even | Depends on field choices |
| Range queries | Targeted | Scatter-gather | Targeted if prefix matches |
| Equality queries | Targeted | Targeted | Targeted on prefix fields |
| Monotonic key handling | Poor (hot-spot) | Excellent | Good with hashed prefix |
| Best for | Range-scan workloads | High-insert, even distribution | Mixed read/write patterns |

**Source:** [Hashed Sharding - MongoDB Docs](https://www.mongodb.com/docs/manual/core/hashed-sharding/), [Choose a Shard Key - MongoDB Docs](https://www.mongodb.com/docs/manual/core/sharding-choose-a-shard-key/)

---

## 5. Chunks: Splitting, Migration, and Jumbo Chunks

### 5.1 Chunk Fundamentals

A chunk is a contiguous range of shard key values assigned to a single shard. Each chunk has an inclusive lower bound and exclusive upper bound.

- **Default chunk size:** 128 MB
- **Smallest unit:** A single unique shard key value (cannot be split further)

| Chunk Size | Pros | Cons |
|------------|------|------|
| Smaller | More even distribution | More frequent migrations, higher routing overhead |
| Larger | Fewer migrations, better network efficiency | Potentially uneven distribution |

### 5.2 Chunk Splitting

MongoDB automatically splits chunks when they exceed the configured chunk size. Splits are metadata-only operations (no data movement) -- they divide a chunk's range into two sub-ranges.

To manually split:
```javascript
sh.splitAt("myDb.orders", { orderId: 1000 })
sh.splitFind("myDb.orders", { orderId: 500 })
```

### 5.3 Chunk Migration

The balancer moves chunks between shards to maintain even distribution. Migration is a multi-step process:

1. Balancer issues `moveRange` to the source shard.
2. Destination shard builds any missing indexes.
3. Destination requests and receives document copies from source.
4. Destination synchronizes changes that occurred during migration.
5. Source updates config server metadata with the new chunk location.
6. Source asynchronously deletes its copy of migrated documents.

Manual migration:
```javascript
db.adminCommand({
  moveRange: "myDb.orders",
  min: { orderId: MinKey },
  max: { orderId: 1000 },
  to: "shard2"
})
```

### 5.4 Jumbo Chunks

A jumbo chunk exceeds the configured chunk size but cannot be split -- typically because all documents share the same shard key value (cardinality exhaustion).

**Detection:**
```javascript
sh.status(true)  // Look for chunks labeled "jumbo"

// Or query config directly
use config
db.chunks.find({ jumbo: true })
```

**Remediation strategies:**

| Strategy | When to Use | Command |
|----------|-------------|---------|
| **Split the chunk** | If the chunk is divisible (multiple distinct shard key values) | `sh.splitAt()` -- clears jumbo flag on success |
| **Refine shard key** | Add suffix fields to increase cardinality (MongoDB 4.4+) | `refineCollectionShardKey` |
| **Reshard collection** | Change the shard key entirely (MongoDB 5.0+) | `reshardCollection` |
| **Manual move** | Redistribute load without fixing root cause | `sh.moveChunk()` |
| **Clear jumbo flag** | After manual data cleanup | See [Clear Jumbo Flag tutorial](https://www.mongodb.com/docs/manual/tutorial/clear-jumbo-flag/) |

**Source:** [Data Partitioning with Chunks - MongoDB Docs](https://www.mongodb.com/docs/manual/core/sharding-data-partitioning/), [Percona: Dealing with Jumbo Chunks in MongoDB](https://www.percona.com/blog/dealing-with-jumbo-chunks-in-mongodb/)

---

## 6. Balancer Configuration

The balancer is a background process running on the config server replica set primary. It monitors data distribution and migrates chunks to maintain balance.

### 6.1 Migration Threshold

The balancer triggers when the data difference between the largest and smallest shard exceeds **3x the configured chunk size** (default: 3 x 128 MB = 384 MB).

```javascript
sh.balancerCollectionStatus("myDb.orders")
// Returns whether the collection is balanced
```

### 6.2 Parallel Migration Limits

- **Per shard:** At most 1 active migration at a time.
- **Cluster-wide:** At most n/2 simultaneous migrations (where n = number of shards).
- Example: A 4-shard cluster runs a maximum of 2 concurrent migrations.

### 6.3 Balancer State Management

```javascript
sh.getBalancerState()    // Check if enabled (true/false)
sh.stopBalancer()        // Disable
sh.startBalancer()       // Enable
sh.waitForBalancer()     // Wait for active migrations to complete
```

### 6.4 Active Window

Restrict the balancer to off-peak hours to minimize production impact:

```javascript
use config
db.settings.updateOne(
  { _id: "balancer" },
  { $set: { activeWindow: { start: "22:00", stop: "06:00" } } },
  { upsert: true }
)

// Remove the window (run anytime)
db.settings.updateOne(
  { _id: "balancer" },
  { $unset: { activeWindow: "" } }
)
```

Times are relative to the config server primary's local timezone.

### 6.5 Secondary Throttle

Control replication behavior during migrations:

```javascript
use config
db.settings.updateOne(
  { _id: "balancer" },
  { $set: { _secondaryThrottle: { w: "majority", wtimeout: 5000 } } },
  { upsert: true }
)
```

### 6.6 Range Deletion Tuning

Tune the performance impact of post-migration cleanup:

```javascript
db.adminCommand({ setParameter: 1, rangeDeleterBatchSize: 32 })
db.adminCommand({ setParameter: 1, rangeDeleterBatchDelayMS: 50 })
db.adminCommand({ setParameter: 1, chunkDefragmentationThrottlingMS: 100 })
```

### 6.7 Chunk Size Modification

```javascript
use config
db.settings.updateOne(
  { _id: "chunksize" },
  { $set: { value: 256 } },  // Set to 256 MB
  { upsert: true }
)
```

**Source:** [Sharded Cluster Balancer - MongoDB Docs](https://www.mongodb.com/docs/manual/core/sharding-balancer-administration/), [Manage Sharded Cluster Balancer - MongoDB Docs](https://www.mongodb.com/docs/manual/tutorial/manage-sharded-cluster-balancer/)

---

## 7. Zone Sharding

Zones (formerly called tags) let you associate shard key ranges with specific shards, enabling data locality, tiered storage, and geographic distribution.

### 7.1 Core Concepts

- A **zone** is a logical grouping associated with one or more shards.
- A shard can belong to multiple zones.
- Each zone covers one or more shard key ranges (inclusive lower, exclusive upper).
- Zone ranges cannot overlap.
- The balancer respects zones: chunks falling within a zone range migrate only to shards associated with that zone.

### 7.2 Configuration Commands

```javascript
// Associate a shard with a zone
sh.addShardToZone("shard0001", "US-East")
sh.addShardToZone("shard0002", "EU-West")

// Define zone ranges
sh.updateZoneKeyRange(
  "myDb.users",
  { region: "US", _id: MinKey },
  { region: "US", _id: MaxKey },
  "US-East"
)

sh.updateZoneKeyRange(
  "myDb.users",
  { region: "EU", _id: MinKey },
  { region: "EU", _id: MaxKey },
  "EU-West"
)

// Remove a zone association
sh.removeShardFromZone("shard0001", "US-East")
```

### 7.3 Use Cases

| Use Case | Pattern |
|----------|---------|
| **Geographic data locality** | Route user data to shards in the user's region (GDPR, latency) |
| **Tiered storage** | Route hot data to SSD-backed shards, cold data to HDD shards |
| **Data isolation** | Isolate tenant data on dedicated shards for security/compliance |
| **Write locality** | Distribute writes across zones for insert-heavy workloads |

### 7.4 Hashed Shard Keys with Zones

For hashed shard keys, zone ranges must use hashed values, not raw values:

```javascript
// Compute hash value
convertShardKeyToHashed("someValue")

// Use MinKey/MaxKey to restrict all data to a single zone
sh.updateZoneKeyRange(
  "myDb.collection",
  { _id: MinKey },
  { _id: MaxKey },
  "zone_name"
)
```

### 7.5 Pre-defining Zones

Define zones before sharding an empty collection for faster initial distribution:

```javascript
// 1. Add shards to zones
sh.addShardToZone("shard0001", "zone-alpha")
sh.addShardToZone("shard0002", "zone-beta")

// 2. Define zone ranges
sh.updateZoneKeyRange("myDb.collection", { region: "A" }, { region: "M" }, "zone-alpha")
sh.updateZoneKeyRange("myDb.collection", { region: "M" }, { region: "Z" }, "zone-beta")

// 3. Shard the collection -- chunks are created for zone ranges automatically
sh.shardCollection("myDb.collection", { region: 1, _id: 1 })
```

**Limitation:** Zone sharding is not supported for time series collections.

**Source:** [Zone Sharding - MongoDB Docs](https://www.mongodb.com/docs/manual/core/zone-sharding/), [Percona: Zone Based Sharding in MongoDB](https://www.percona.com/blog/zone-based-sharding-in-mongodb/)

---

## 8. Targeted vs Scatter-Gather Queries

### 8.1 Targeted Operations

mongos routes to a single shard or subset of shards when the query includes the shard key or a prefix of a compound shard key.

For compound shard key `{ a: 1, b: 1, c: 1 }`:

| Query Filter | Routing |
|-------------|---------|
| `{ a: 1 }` | Targeted (shard key prefix) |
| `{ a: 1, b: 5 }` | Targeted (shard key prefix) |
| `{ a: 1, b: 5, c: 10 }` | Targeted (full shard key) |
| `{ b: 5 }` | Scatter-gather (missing prefix `a`) |
| `{ c: 10 }` | Scatter-gather (missing prefix `a`, `b`) |

### 8.2 Broadcast (Scatter-Gather) Operations

When the query does not include the shard key, mongos broadcasts to all shards, waits for all responses, then merges results. These queries are inherently slower and do not scale linearly with shard count.

```javascript
// Targeted (shard key in filter)
db.orders.find({ customerId: "C123" })

// Scatter-gather (no shard key)
db.orders.find({ status: "shipped" })
```

### 8.3 Write Operation Routing

| Operation | Routing Behavior |
|-----------|-----------------|
| `insertOne` | Always targeted (shard key in document) |
| `updateOne` / `replaceOne` | Must include shard key or `_id`; targeted |
| `updateMany` / `deleteMany` | Broadcast unless full shard key specified |
| `deleteOne` | Must include shard key or `_id`; targeted |

### 8.4 Aggregation Pipeline Routing

Aggregation pipelines are split between shard execution and merge execution. Use `explain: true` to see where merge happens:

```javascript
db.collection.aggregate([
  { $match: { region: "US" } },
  { $group: { _id: "$category", total: { $sum: "$amount" } } }
], { explain: true })
// Check "mergeType": "router" | "anyShard" | "specificShard"
```

Merge runs on `specificShard` when the pipeline uses `$lookup` against an unsharded collection or writes temporary data with `allowDiskUse: true`.

### 8.5 Sort, Limit, Skip Behavior

- **Sort:** Each shard sorts locally; mongos merge-sorts the results.
- **Limit:** mongos passes the limit to each shard, then re-applies on merged results.
- **Skip:** mongos retrieves all results and skips locally (inefficient for large skips). When combined with limit, mongos optimizes by sending skip+limit to each shard.

**Source:** [Routing with mongos - MongoDB Docs](https://www.mongodb.com/docs/manual/core/sharded-cluster-query-router/), [Distributed Queries - MongoDB Docs](https://www.mongodb.com/docs/manual/core/distributed-queries/)

---

## 9. Resharding Operations

### 9.1 reshardCollection (MongoDB 5.0+)

Change the shard key for a collection online while the cluster continues serving reads and writes:

```javascript
db.adminCommand({
  reshardCollection: "myDb.orders",
  key: { newShardKey: "hashed" }
})
```

**Phases:**
1. **Clone:** Recipient shards clone data from donor shards.
2. **Catch-up:** Recipients apply write operations from donors via oplog.
3. **Commit:** Atomic cut-over to the new shard key (approximately 2-second write block).

**Requirements:**
- Disable the balancer: `sh.stopBalancer()`
- Sufficient disk space: `((collection_size + index_size) * 2) / shard_count` per shard
- I/O utilization below 50%, CPU load below 80%
- Only one resharding operation per cluster at a time
- Minimum 5-minute duration for any resharding operation

**Monitoring progress:**
```javascript
db.getSiblingDB("admin").aggregate([
  { $currentOp: { allUsers: true, localOps: false } },
  { $match: {
      type: "op",
      "originatingCommand.reshardCollection": "myDb.orders"
  }}
])
```

**Abort if needed:**
```javascript
db.adminCommand({ abortReshardCollection: "myDb.orders" })
```

### 9.2 refineCollectionShardKey (MongoDB 4.4+)

Add suffix fields to the existing shard key without redistributing data:

```javascript
db.adminCommand({
  refineCollectionShardKey: "myDb.orders",
  key: { customerId: 1, orderId: 1 }  // Added orderId as suffix
})
```

This is less disruptive than resharding -- it increases cardinality by appending fields, enabling finer-grained chunk splits. No data movement occurs.

### 9.3 sh.shardAndDistributeCollection (MongoDB 8.0+)

Shard a collection and immediately redistribute data without waiting on the balancer:

```javascript
sh.shardAndDistributeCollection("myDb.newCollection", { userId: "hashed" })
```

This wraps `shardCollection` + `reshardCollection` for faster initial data distribution. Recommended over `sh.shardCollection()` when the deployment meets the resource requirements.

### 9.4 Reshard to Same Key (MongoDB 8.0+)

Force data redistribution without changing the shard key:

```javascript
db.adminCommand({
  reshardCollection: "myDb.orders",
  key: { customerId: 1 },
  forceRedistribution: true
})
```

Useful after adding/removing shards to rebalance data faster than the balancer.

**Source:** [Reshard a Collection - MongoDB Docs](https://www.mongodb.com/docs/manual/core/sharding-reshard-a-collection/), [Percona: Resharding in MongoDB 5.0](https://www.percona.com/blog/resharding-in-mongodb-5-0/)

---

## 10. Sharded Cluster Diagnostics

### 10.1 sh.status()

The primary diagnostic command for sharded clusters:

```javascript
sh.status()          // Summary view
sh.status(true)      // Verbose (shows all chunks, zones, and jumbo flags)
```

Output sections:
- **Sharding version:** Config server protocol version
- **Shards:** List of all shards with hostnames and state
- **Balancer:** Current state, active window, last error, migration counts
- **Databases:** Partitioned status, primary shard
- **Collections:** Shard key, chunk count per shard, zone tag ranges

### 10.2 Config Database Queries

```javascript
use config

// List all shards
db.shards.find()

// View chunk distribution for a collection
db.chunks.aggregate([
  { $match: { ns: "myDb.orders" } },
  { $group: { _id: "$shard", count: { $sum: 1 } } }
])

// Find jumbo chunks
db.chunks.find({ jumbo: true })

// View zone ranges
db.tags.find()

// View active migrations
db.locks.find({ state: { $ne: 0 } })
```

### 10.3 currentOp for Active Operations

```javascript
db.adminCommand({
  currentOp: true,
  $all: true,
  desc: /moveRange|moveChunk|reshardCollection/
})
```

### 10.4 Diagnostic Checklist

| Check | Command | What to Look For |
|-------|---------|-----------------|
| Cluster balance | `sh.balancerCollectionStatus("db.coll")` | `"balanced": true` |
| Balancer running | `sh.getBalancerState()` | `true` |
| Chunk distribution | `sh.status(true)` | Even chunk counts across shards |
| Jumbo chunks | `db.chunks.find({ jumbo: true })` | Should be empty |
| Migration errors | `sh.status()` balancer section | No `last-reported-error` |
| Scatter-gather queries | `explain("executionStats")` on queries | `SHARD_MERGE` stage = scatter-gather |
| Orphaned documents | `db.collection.count()` on each shard | Counts should match config metadata |

**Source:** [View Cluster Configuration - MongoDB Docs](https://www.mongodb.com/docs/manual/tutorial/view-sharded-cluster-configuration/), [Troubleshoot Sharded Clusters - MongoDB Docs](https://www.mongodb.com/docs/manual/tutorial/troubleshoot-sharded-clusters/)

---

## 11. Anti-Patterns and Common Mistakes

### 11.1 Shard Key Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| **ObjectId as ranged shard key** | Monotonically increasing; all writes go to last chunk | Use `{ _id: "hashed" }` |
| **Low-cardinality key** (e.g., `status`, `continent`) | Maximum chunks = number of distinct values | Use compound key or choose higher-cardinality field |
| **High-frequency single value** | One value dominates; creates permanent jumbo chunks | Compound key with a unique suffix |
| **Shard key not in common queries** | All queries become scatter-gather | Choose key that appears in most-frequent filters |
| **Sharding too early** | Adds complexity before it's needed | Exhaust vertical scaling, indexing, and schema optimizations first |

### 11.2 Operational Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| **Disabling balancer indefinitely** | Data becomes increasingly skewed | Use active windows instead; re-enable after maintenance |
| **Ignoring jumbo chunk warnings** | Chunks grow unbounded, unmigratable | Address root cause: refine key, reshard, or split |
| **Large skip() on sharded queries** | mongos fetches all results and discards; O(n) cost | Use range-based pagination with shard key |
| **Connecting directly to shards** | Bypasses routing, causes inconsistent reads | Always connect through mongos |
| **No mongos HA** | Single point of failure | Deploy 2+ mongos instances behind load balancer |

### 11.3 Schema Anti-Patterns in Sharded Environments

- **Unbounded arrays in shard key path:** Documents can grow past 16MB BSON limit.
- **Shard key on a field that gets updated:** Causes document migration between shards, degrading performance.
- **Multi-collection transactions spanning many shards:** Cross-shard transactions have higher latency; design schema to localize transactions to fewer shards.

**Source:** [Troubleshoot Shard Keys - MongoDB Docs](https://www.mongodb.com/docs/manual/core/sharding-troubleshooting-shard-keys/), [Performance Best Practices: Sharding - MongoDB Blog](https://www.mongodb.com/company/blog/mongodb/performance-best-practices-sharding)

---

## 12. Production Readiness Checklist

### Pre-Sharding

- [ ] Vertical scaling, indexing, and schema design optimized first
- [ ] Shard key analyzed with `analyzeShardKey` (MongoDB 7.0+) or workload analysis
- [ ] Shard key has high cardinality, low frequency skew, and appears in common queries
- [ ] Unique indexes include the shard key as a prefix
- [ ] Application queries rewritten to include shard key where possible
- [ ] Test environment validated with realistic data distribution

### Deployment

- [ ] Config servers deployed as 3-member replica set on dedicated hosts
- [ ] 2+ mongos instances deployed (HA)
- [ ] Balancer active window configured for off-peak hours
- [ ] Monitoring dashboards for chunk distribution, balancer state, and migration errors
- [ ] Backup strategy accounts for sharded topology (consistent snapshots across shards)

### Ongoing Operations

- [ ] `sh.status()` reviewed regularly for jumbo chunks and imbalanced distributions
- [ ] Scatter-gather queries identified and optimized (add shard key to filters or create covered indexes)
- [ ] Oplog sized appropriately for resharding operations
- [ ] Disk headroom maintained for chunk migrations (2x collection size during resharding)
- [ ] Zone configuration reviewed when adding/removing shards or regions

---

## 13. Quick Reference: Essential Commands

```javascript
// === Sharding Setup ===
sh.enableSharding("myDb")
sh.shardCollection("myDb.coll", { key: 1 })
sh.shardCollection("myDb.coll", { key: "hashed" })
sh.shardAndDistributeCollection("myDb.coll", { key: 1 })  // MongoDB 8.0+

// === Shard Key Changes ===
db.adminCommand({ refineCollectionShardKey: "myDb.coll", key: { key: 1, suffix: 1 } })
db.adminCommand({ reshardCollection: "myDb.coll", key: { newKey: 1 } })
db.adminCommand({ analyzeShardKey: "myDb.coll", key: { candidateKey: 1 } })

// === Balancer ===
sh.getBalancerState()
sh.startBalancer()
sh.stopBalancer()
sh.balancerCollectionStatus("myDb.coll")

// === Zones ===
sh.addShardToZone("shard0001", "US")
sh.updateZoneKeyRange("myDb.coll", { region: "US" }, { region: "US~" }, "US")
sh.removeShardFromZone("shard0001", "US")

// === Chunks ===
sh.splitAt("myDb.coll", { key: 1000 })
sh.moveChunk("myDb.coll", { key: 500 }, "shard0002")

// === Diagnostics ===
sh.status(true)
db.collection.getShardDistribution()
db.collection.explain("executionStats").find({ ... })
```

---

## 14. Version-Specific Feature Matrix

| Feature | Minimum Version | Notes |
|---------|----------------|-------|
| Basic sharding | 1.6 | Original sharding support |
| Zone sharding (tags) | 3.4 | Renamed from tag-aware sharding |
| Compound hashed shard keys | 4.4 | Single hashed field in compound key |
| refineCollectionShardKey | 4.4 | Add suffix fields to shard key |
| Online reshardCollection | 5.0 | Change shard key without downtime |
| analyzeShardKey | 7.0 | Data-driven shard key analysis |
| sh.shardAndDistributeCollection | 8.0 | Faster initial distribution |
| Reshard to same key (forceRedistribution) | 8.0 | Rebalance without key change |
| moveCollection | 8.0 | Move unsharded collection to specific shard |
| Time series resharding | 8.0.10+ | Reshard time series collections |
