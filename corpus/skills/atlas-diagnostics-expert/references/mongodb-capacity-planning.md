<!-- hub-reference-banner -->
> **Reference file — part of `atlas-diagnostics-expert` hub.** Formerly standalone `mongodb-capacity-planning` skill.
> Sibling MongoDB sub-topics now reference files under four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore "use the X skill" / `related_skills` / SKIP pointers below naming
> bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from owning hub (see hub's "Cross-hub map").

---

---
name: mongodb-capacity-planning
description: >-
  MongoDB Atlas capacity planning — working set sizing, IOPS forecasting,
  storage growth modeling, connection capacity per tier, oplog sizing, cluster
  tier selection, sharding triggers, Performance Advisor, growth signals, and
  common sizing mistakes. TRIGGER: sizing a new Atlas cluster; debugging capacity
  exhaustion (disk full, CPU pegged, replication lag spiking); planning storage or
  tier growth over a 12-month horizon; reviewing autoscaling configuration and
  alert thresholds; evaluating whether sharding is the right next step; Flex tier
  limits (500 ops/sec, 5 GB storage). SKIP: Atlas Search or Vector Search sizing
  (mongodb-atlas-search-nodes); pure query/index tuning with no sizing angle
  (mongodb-query-performance, mongodb-indexes-deep); time-series collection design
  with no RAM/storage question (mongodb-time-series).
category: mongodb
version: "1.1.0"
updated: "2026-05-29"
tags:
  - mongodb
  - atlas
  - capacity
  - sizing
  - iops
  - storage
  - sharding
  - performance
keywords:
  - working set sizing
  - WiredTiger cache
  - IOPS forecasting
  - storage growth
  - connection limits
  - oplog window
  - cluster tier selection
  - sharding triggers
  - shard key
  - Performance Advisor
  - autoscaling
  - Atlas M10 M30 M50 M80
  - Flex 500 ops/sec
  - mongoperf
  - replication lag
  - cache eviction
whenToUse:
  - "what Atlas tier should I use for my workload"
  - "how much RAM does my working set need"
  - "WiredTiger cache is full — pages are being evicted"
  - "disk is growing fast — forecast storage for the next 12 months"
  - "connection pool exhausted on M30 — how many connections does it support"
  - "oplog window is under 24 hours — how do I fix it"
  - "should I shard or scale vertically to M80"
  - "Performance Advisor is recommending indexes — should I apply them"
  - "autoscaling triggered unexpectedly — what thresholds are recommended"
  - "Flex cluster hitting 500 ops/sec — when should I move to M10"
whenNotToUse:
  - "Atlas Search Node sizing — use mongodb-atlas-search-nodes"
  - "Slow query tuning with no sizing question — use mongodb-query-performance"
  - "Index creation or index design — use mongodb-indexes-deep"
  - "Time-series schema design with no RAM/storage question — use mongodb-time-series"
related_skills:
  - mongodb-atlas-search-nodes
  - mongodb-sharding
  - mongodb-performance-troubleshooting
  - mongodb-monitoring-observability
  - mongodb-cost-optimization
  - mongodb-time-series
  - mongodb-atlas-flex-serverless
---

# MongoDB Capacity Planning

Use when:
- Sizing new Atlas cluster for customer workload
- Debugging capacity exhaustion (disk full, CPU pegged, replication lag spiking)
- Planning storage or tier growth over 12-month horizon
- Reviewing autoscaling config and alert thresholds
- Evaluating whether sharding is right next step

---

## 1. Working Set Sizing

**Working set** = subset of data + indexes app touches in steady-state. When working set fits in WiredTiger's in-memory cache, reads serve from RAM — no disk I/O.

**WiredTiger cache default:** 50% of total RAM (min 1 GB).
Rule: working set must fit in cache to avoid eviction pressure and latency spikes.

```javascript
// Estimate working set from the shell
use myDatabase

// Data size of hot collection (bytes)
const stats = db.orders.stats();
const dataSize = stats.storageSize;       // compressed on-disk
const indexSize = stats.totalIndexSize;   // all indexes for this collection

// WiredTiger internal cache holds uncompressed data -- inflate by ~3x for
// snappy-compressed collections when estimating RAM pressure.
const inflationFactor = 3;
const estimatedRAMPressure = (dataSize * inflationFactor) + indexSize;

print(`On-disk data:        ${(dataSize / 1e9).toFixed(2)} GB`);
print(`Index size:          ${(indexSize / 1e9).toFixed(2)} GB`);
print(`Est. RAM pressure:   ${(estimatedRAMPressure / 1e9).toFixed(2)} GB`);

// Compare against available WiredTiger cache:
// Atlas M30 = 8 GB RAM → cache = 4 GB
// Atlas M40 = 16 GB RAM → cache = 8 GB
// Atlas M50 = 32 GB RAM → cache = 16 GB
// Atlas M80 = 64 GB RAM → cache = 32 GB
```

```javascript
// Check current cache utilization (run on primary)
db.serverStatus().wiredTiger.cache["bytes currently in the cache"]
db.serverStatus().wiredTiger.cache["maximum bytes configured"]
db.serverStatus().wiredTiger.cache["pages read into cache"]    // high = eviction pressure
db.serverStatus().wiredTiger.cache["unmodified pages evicted"] // rising = working set > cache
```

**Actionable threshold:** "unmodified pages evicted" growing consistently = working set exceeds cache. Upsize RAM (next tier) before disk IOPS saturate.

---

## 2. IOPS Forecasting

IOPS come from write throughput (every write hits journal + data file) and reads missing WiredTiger cache.

**Disk types on Atlas:**

| Type            | Baseline IOPS         | Burst / Max IOPS  | Notes                        |
|-----------------|-----------------------|-------------------|------------------------------|
| AWS gp3         | 3,000 (always)        | up to 16,000      | Provisioned separately       |
| AWS io2         | Provisioned           | up to 256,000     | High-performance workloads   |
| Atlas NVMe      | ~millions (local SSD) | N/A               | Available on M80+ NVMe tiers |
| Azure Premium   | 3,000–20,000+         | Varies by disk    | P-series disks               |

```javascript
// Estimate write IOPS from opcounters
const st = db.serverStatus().opcounters;
// Writes land in journal (sync) + data files (async).
// Journal writes: 1 IOPS per write doc in default durability mode.
// Checkpoint flushes: every 60s by default -- burst of dirty page writes.
const writesPerSec = st.insert + st.update + st.delete;
print(`Write ops/sec: ${writesPerSec}`);
// Rule of thumb: allocate 2x write ops/sec in provisioned IOPS to absorb checkpoints.

// Read IOPS from cache miss rate
const cacheReads = db.serverStatus().wiredTiger.cache["pages read into cache"];
// Track this over a 5-minute window; delta = read IOPS from disk.
```

```bash
# Atlas Metrics API v2 -- retrieve disk IOPS over last 24h
# HOST format: "hostname:port" e.g. "cluster0-shard-00-00.abc12.mongodb.net:27017"
# Find valid HOST values via: GET /api/atlas/v2/groups/$PROJECT_ID/processes
curl -s -u "$ATLAS_PUBLIC_KEY:$ATLAS_PRIVATE_KEY" --digest \
  "https://cloud.mongodb.com/api/atlas/v2/groups/$PROJECT_ID/processes/$HOST/measurements?granularity=PT5M&period=P1D&m=DISK_PARTITION_IOPS_READ&m=DISK_PARTITION_IOPS_WRITE" \
  -H "Accept: application/vnd.atlas.2023-01-01+json" \
  | jq '.measurements[] | {name: .name, max: [.dataPoints[].value | numbers] | max}'
```

**Sizing rule:** sustained IOPS at 80%+ of provisioned limit = time to provision more IOPS (gp3/io2) or move to NVMe-backed tiers.

---

## 3. Storage Growth Modeling

Total on-disk = data files + indexes + journal + oplog + diagnostic logs.

**Index overhead:** 10–30% of raw data size depending on field count and index types. Geospatial and text indexes trend higher.

```javascript
// Current database footprint (MongoDB 4.4+; totalSize available from 4.4 onward)
use admin
const dbStats = db.runCommand({ dbStats: 1, scale: 1073741824 }); // scale to GB
// All numeric fields are already divided by scale — values are in GB
printjson({
  dataGB:    dbStats.dataSize.toFixed(2),
  indexGB:   dbStats.indexSize.toFixed(2),
  storageGB: dbStats.storageSize.toFixed(2),  // compressed on-disk
  totalGB:   (dbStats.totalSize ?? dbStats.storageSize + dbStats.indexSize).toFixed(2)
});
```

```javascript
// 12-month storage forecast
function forecastStorage(currentGB, monthlyGrowthPct, months = 12) {
  const results = [];
  let size = currentGB;
  for (let m = 1; m <= months; m++) {
    size = size * (1 + monthlyGrowthPct / 100);
    results.push({ month: m, projectedGB: +size.toFixed(1) });
  }
  return results;
}

// Example: 500 GB today growing at 8% per month
const forecast = forecastStorage(500, 8);
forecast.forEach(r => print(`Month ${r.month}: ${r.projectedGB} GB`));
// Month 6: ~793 GB  |  Month 12: ~1,259 GB

// Add index overhead (20% of projected data) for full disk estimate
const withIndexes = forecast.map(r => ({
  ...r,
  totalWithIndexesGB: +(r.projectedGB * 1.20).toFixed(1)
}));
```

**Real-world example:** Large e-commerce cluster at 85 TB across 13 shards on M80. Autoscaling triggered at 90% disk used. Without forecast, team surprised by scale events mid-cycle.

---

## 4. Connection Capacity

Every driver connection consumes server-side socket + thread (or async slot on 6.0+). Atlas enforces hard connection limits per tier.

**Atlas connection limits (per replica set node):**

| Tier | Max Connections |
|------|-----------------|
| M10  | 500             |
| M20  | 1,500           |
| M30  | 3,000           |
| M40  | 6,000           |
| M50  | 16,000          |
| M80  | 32,000          |

```javascript
// Check current connection usage
db.serverStatus().connections
// { current: 284, available: 4716, totalCreated: 10482 }
// Alert if current > 80% of tier limit.

// Tier limit lookup (match to your actual tier):
const tierLimits = { M10: 500, M20: 1500, M30: 3000, M40: 6000, M50: 16000, M80: 32000 };
const tierLimit = tierLimits["M30"]; // set to your cluster's tier
const connPct = (db.serverStatus().connections.current / tierLimit) * 100;
print(`Connection utilization: ${connPct.toFixed(1)}%`);

// Atlas Metrics API for connection trend
// m=CONNECTIONS gives the timeseries
```

```javascript
// Driver pool sizing guidance (Node.js example)
const { MongoClient } = require('mongodb');
const client = new MongoClient(uri, {
  maxPoolSize: 50,       // per app instance; multiply by replica count
  minPoolSize: 5,        // keep-warm connections
  maxIdleTimeMS: 30000,  // reclaim idle sockets quickly
  waitQueueTimeoutMS: 5000, // surface backpressure rather than queuing forever
  serverSelectionTimeoutMS: 5000
});

// Total connections = maxPoolSize * app_replicas * 3 (one per RS node)
// For 10 app pods with maxPoolSize=50: 10 * 50 * 3 = 1,500 connections
// That exhausts an M20. Use M30+ or reduce pool size.
```

**Sharded clusters:** `mongos` routers each maintain own connection pools to every shard. Topology with 4 mongos x 6 shards x 3 nodes = 72 connections per mongos before counting app's own pool. Size mongos count conservatively.

---

## 5. Oplog Sizing

Oplog = capped collection on each replica set member recording all writes. Secondaries replay oplog to stay in sync. Oplog window (how far back ops retained) determines how long secondary can lag before going stale and requiring full resync.

**Minimum recommended oplog window: 24 hours.**
For clusters with heavy maintenance windows (index builds, migrations), 72 hours safer.

```javascript
// Check current oplog window and size
rs.printReplicationInfo()
// Output:
// configured oplog size:   51200 MB
// log length start to end: 91600 secs (25.44 hrs)
// oplog first event time:  Wed May 27 2026 ...
// oplog last event time:   Thu May 28 2026 ...
// now:                     Thu May 28 2026 ...
```

```javascript
// Check secondary lag (run on primary)
rs.printSecondaryReplicationInfo()
// Lists each secondary with lag in seconds.
// Alert if lag > 30s under normal conditions.
// Alert if lag > 3600s (1 hr) — secondary may fall off oplog if window is small.
```

```javascript
// Estimate required oplog size from write rate
const oplogStats = db.getSiblingDB('local').oplog.rs.stats();
const oplogSizeGB = oplogStats.maxSize / 1e9;
const opcounters = db.serverStatus().opcounters;
const writesPerSec = opcounters.insert + opcounters.update + opcounters.delete;
const avgDocSizeBytes = 512; // tune per workload
// Oplog entries include full document + metadata — typically 2-3x raw doc size.
// Use a conservative 2.5x multiplier to avoid underestimating window size.
const oplogOverheadMultiplier = 2.5;
const oplogBytesPerSec = writesPerSec * avgDocSizeBytes * oplogOverheadMultiplier;
const windowHrs = (oplogSizeGB * 1e9) / oplogBytesPerSec / 3600;
print(`Estimated oplog window: ${windowHrs.toFixed(1)} hours`);
// If < 24, increase oplog size via Atlas cluster configuration.
```

Atlas default oplog size is 5% of disk. For write-heavy workloads this may produce windows well under 24 hours. Explicitly configure larger oplog via Atlas UI (Cluster > Configuration > Oplog Size).

---

## 6. Cluster Tier Selection

Choose tier whose RAM accommodates working set and whose CPU handles write/query concurrency. Storage scales independently on most tiers.

| Tier | RAM   | vCPUs | Max Storage | Typical Use                            |
|------|-------|-------|-------------|----------------------------------------|
| M10  | 2 GB  | 2     | 128 GB      | Dev/test, small apps                   |
| M20  | 4 GB  | 2     | 256 GB      | Small production (< 2 GB working set)  |
| M30  | 8 GB  | 2     | 512 GB      | Standard production start              |
| M40  | 16 GB | 4     | 1 TB        | Growing workloads, analytics           |
| M50  | 32 GB | 8     | 4 TB        | Large working sets, moderate write load|
| M80  | 64 GB | 32    | 4 TB        | High-throughput, large working sets    |

**Vertical vs horizontal scaling:**

- Scale **vertically** (upsize tier) when: RAM is constraint (cache misses), or CPU bottleneck for single-document operations.
- Scale **horizontally** (shard) when: single node can't serve write throughput, storage exceeds ~4 TB, or working set won't fit in M80 RAM.

```bash
# Atlas CLI: resize cluster tier (requires Atlas CLI >= 1.x)
# Use --instanceSize, not --tier (--tier is not a valid flag)
atlas clusters update MY_CLUSTER \
  --instanceSize M40 \
  --projectId $PROJECT_ID
```

---

## 7. Sharding Triggers

Sharding distributes data and write load across multiple replica sets (shards). Introduce proactively — migrating unsharded collection later is disruptive.

**Start sharding when any apply:**
- Storage per node approaches 4 TB (practical single-shard limit before management overhead)
- Working set exceeds M80 RAM (64 GB) and can't be reduced by indexing or data tiering
- Write throughput saturates single primary's CPU or disk IOPS
- Single collection grows beyond ~500 GB and access pattern is range or scatter-gather heavy

```javascript
// Enable sharding on a database
sh.enableSharding("orders_db")

// Shard a collection — choose the shard key carefully (see below)
sh.shardCollection("orders_db.orders", { customerId: 1, createdAt: 1 })

// Check shard distribution
sh.status()
// Look for: "currently enabled" shards, chunk counts per shard (should be balanced)
```

**Shard key criteria:**

| Property    | Requirement                                   | Anti-pattern              |
|-------------|-----------------------------------------------|---------------------------|
| Cardinality | High (many distinct values)                   | Boolean, status enum      |
| Frequency   | Even distribution of writes across key values | "active" flag (hot shard) |
| Monotonicity| Avoid monotonically increasing keys alone     | ObjectId or timestamp only|

```javascript
// Compound shard key to break monotonicity: prefix with low-cardinality bucket
// then append the high-cardinality natural key
sh.shardCollection("events_db.events", { tenantId: 1, _id: 1 })
// tenantId distributes across shards; _id ensures uniqueness within shard.

// Hashed shard key: good for even write distribution, bad for range scans
sh.shardCollection("logs_db.logs", { _id: "hashed" })
```

**Real-world example:** Large-scale sharded deployment — 13 shards, 85 TB total, M80 per shard. Autoscaling triggers at 90% disk. Shard key selection was critical design decision enabling balanced chunk distribution at this scale.

---

## 8. Read vs Write Distribution

Replica set topology lets you route reads to secondaries to offshift read load from primary. Write concern controls durability vs latency trade-off.

```javascript
// Read preference options
const { MongoClient } = require('mongodb');
const client = new MongoClient(uri, {
  readPreference: 'secondaryPreferred', // reads go to secondaries when available
  // Options: primary | primaryPreferred | secondary | secondaryPreferred | nearest
});

// Collection-level override for analytics queries (Node.js driver >= 4.x)
const col = db.collection('reports').withReadPreference(
  new ReadPreference('secondary')
);
// Note: passing readPreference as a second arg to .collection() is deprecated
// in driver v6+. Use .withReadPreference() or set it on the query instead.
const rows = await col.find({ quarter: 'Q1' }).toArray(); // reads from secondary

// Read preference tag sets -- route analytics to nodes tagged 'analytics'
// Configure in Atlas: add custom tag to specific replica set member
const analyticsClient = new MongoClient(uri, {
  readPreference: new ReadPreference('secondary', [{ workload: 'analytics' }])
});
```

```javascript
// Write concern: majority vs w:1 trade-off
// majority: waits for acknowledgment from quorum -- durability guaranteed, +latency
// w:1: acks from primary only -- lower latency, risk of rollback on primary failure

const col = db.collection('orders');

// Critical financial writes: use majority + journal
await col.insertOne(doc, { writeConcern: { w: 'majority', j: true } });

// High-volume event ingestion where some loss is acceptable
await col.insertMany(events, { writeConcern: { w: 1, j: false } });
```

**Rule:** `secondaryPreferred` effectively doubles read throughput for 3-node RS at zero additional cost. Use for reporting, dashboards, analytics queries. Reserve `primary` read preference only for reads requiring absolute latest write.

---

## 9. Atlas Performance Advisor

Performance Advisor analyzes slow queries (> 100ms default) and suggests indexes without manual explain-plan analysis. Also flags schema issues like unbounded array growth.

**Access:** Atlas UI → Cluster → Performance Advisor tab.

```javascript
// Confirm slow query threshold (adjustable)
db.setProfilingLevel(1, { slowms: 100 })

// View recent slow ops directly in the shell
db.system.profile.find({}, { op: 1, ns: 1, millis: 1, ts: 1 })
  .sort({ ts: -1 })
  .limit(10)
  .pretty()
```

**Performance Advisor capabilities:**
- **Slow query log analysis:** surfaces operations exceeding threshold, grouped by query shape.
- **Index recommendations:** suggests covering indexes based on query patterns; includes estimated impact score.
- **Schema suggestions:** flags missing indexes, collection scans, excessive in-memory sorts.
- **Drop redundant indexes:** identifies unused indexes consuming write overhead and RAM.

```javascript
// Validate a Performance Advisor index recommendation before applying
// Note: { background: true } is a no-op in MongoDB 4.2+ — all index builds
// are already non-blocking. Use { comment: "..." } for tracking instead.
db.orders.createIndex(
  { customerId: 1, status: 1, createdAt: -1 },
  { comment: "pa_orders_customer_status_created" }
)

// Verify the index is used
db.orders.find({ customerId: "C123", status: "pending" })
         .sort({ createdAt: -1 })
         .explain("executionStats")
// Confirm: winningPlan.inputStage.stage === "IXSCAN"
```

For large Atlas footprints with hundreds of clusters, Performance Advisor runs independently per cluster. Prioritize clusters with high query latency percentiles (p99 > 500ms) for index review.

---

## 10. Growth Signals

Monitor these Atlas metrics to detect capacity pressure before incident:

| Signal                    | Threshold to Act                      | Atlas Metric                         |
|---------------------------|---------------------------------------|--------------------------------------|
| Disk used %               | > 75% sustained; 90% = autoscale now  | `DISK_PARTITION_UTILIZATION`         |
| Sustained IOPS at limit   | > 80% of provisioned IOPS             | `DISK_PARTITION_IOPS_TOTAL`          |
| Replication lag growth    | Lag > 60s or trending upward          | `REPLICATION_LAG`                    |
| Connection pool pressure  | Connections > 80% of tier limit       | `CONNECTIONS`                        |
| Query latency degradation | p95 latency doubling week-over-week   | `OP_EXECUTION_TIME` / query targeting ratio |
| Cache eviction rate       | Evictions > 10% of cache pages/min    | `CACHE_DIRTY_BYTES` / serverStatus   |
| Oplog window shrinking    | Window < 24 hours                     | `OPLOG_SLAVE_LAG_MASTER_TIME`        |

```javascript
// Shell-based growth signal check
// Set tierLimit to your cluster's actual tier (see §4 connection table)
const tierLimits = { M10: 500, M20: 1500, M30: 3000, M40: 6000, M50: 16000, M80: 32000 };
const tierLimit = tierLimits["M30"]; // replace with your tier
const connPct = (db.serverStatus().connections.current / tierLimit) * 100;
print(`Connection utilization: ${connPct.toFixed(1)}%`);

const cache = db.serverStatus().wiredTiger.cache;
const cacheUsedPct = (cache["bytes currently in the cache"] /
                      cache["maximum bytes configured"]) * 100;
print(`Cache used: ${cacheUsedPct.toFixed(1)}%`);
print(`Pages evicted (unmodified): ${cache["unmodified pages evicted"]}`);
```

**Recommended Atlas Alerts:**

```text
Disk used % > 75%     → Warn   (plan resize)
Disk used % > 90%     → Critical (autoscale or emergency upsize)
Connections > 80%     → Warn
Replication lag > 60s → Warn
Query p95 > 500ms     → Warn
```

---

## 11. Capacity Testing

Load test before launch to find saturation point, not after production incident.

```bash
# mongoperf: disk I/O benchmark included with MongoDB tools
# Test sequential vs random I/O on the data volume
echo '{"nThreads": 16, "fileSizeMB": 10000, "r": true}' | mongoperf
echo '{"nThreads": 16, "fileSizeMB": 10000, "w": true}' | mongoperf
# Look for: IOPS plateau = disk saturation point
```

```javascript
// Application-level ramp-up pattern (Node.js pseudo-code)
// runAtRPS() is illustrative — implement with your load framework (k6, Artillery, etc.)
async function rampLoad(targetRPS, rampMinutes, durationMinutes) {
  const stepRPS = targetRPS / (rampMinutes * 6); // increase every 10s
  let currentRPS = stepRPS;
  while (currentRPS <= targetRPS) {
    await runAtRPS(currentRPS, 10_000); // 10s window
    currentRPS += stepRPS;
    // Sample: db.serverStatus().opcounters, .connections, .wiredTiger.cache
  }
  await runAtRPS(targetRPS, durationMinutes * 60_000); // sustain
}
```

**What to measure during load test:**
1. WiredTiger cache hit ratio — stay > 95% for read-heavy workloads
2. Disk IOPS vs provisioned limit — find knee of curve
3. Replication lag on secondaries — stay < 10s under target load
4. Connection count — verify pool sizing doesn't exhaust tier limit
5. p95/p99 query latency — establish baseline and saturation threshold

**Ramp-up pattern:** increase load 10% every 5 minutes. Watch for latency inflection point — RPS where p99 latency doubles. That's saturation threshold; target 50-60% as steady-state operating point for headroom.

---

## 12. Common Sizing Mistakes

**Mistake 1: Undersized RAM — working set spills to disk**

Symptom: cache eviction rate rising, disk read IOPS increasing, latency degrading under normal load. Fix: upsize tier to bring working set into WiredTiger cache.

**Mistake 2: Ignoring index growth**

Indexes grow at same rate as underlying data. 1 TB collection with 8 compound indexes can carry 250+ GB index data. Must be accounted for in both storage and RAM planning.

**Mistake 3: No oplog headroom**

Atlas default 5% oplog on 500 GB disk = 25 GB oplog. At 1 GB/hr write throughput, window is only 25 hours — barely above 24-hour recommendation. Scheduled maintenance or index build pausing replication 2 hours can push secondary off oplog, requiring full resync.

**Mistake 4: Forgetting analytics workload impact**

Analytics queries (aggregations, full collection scans, large sort stages) can evict hot working-set pages from cache, causing sudden latency spikes for OLTP workloads. Isolate analytics reads to tagged secondaries or dedicated Analytics Nodes in Atlas.

```javascript
// Analytics Node: route long-running aggregations explicitly
const analyticsDB = client.db("orders_db", {
  readPreference: new ReadPreference("secondary", [{ nodeType: "ANALYTICS" }])
});
await analyticsDB.collection("orders").aggregate([
  { $match: { status: "completed", year: 2025 } },
  { $group: { _id: "$region", revenue: { $sum: "$total" } } }
]).toArray();
```

**Mistake 5: Monotonic shard key causing hot shard**

Using `_id` (ObjectId) or `createdAt` alone as shard key routes all new inserts to last chunk on one shard. All write load concentrates there until chunk migration catches up — which often can't happen under high write rates.

**Mistake 6: Over-provisioning mongos on sharded clusters**

Each mongos maintains connection pools to every shard node. 10 mongos x 6 shards x 3 nodes = 180 server-side connections per app instance (before app's own pool). Start with 2-3 mongos instances; add based on measured mongos CPU, not guesswork.

**Mistake 7: Sizing for average load, not peak**

Atlas autoscaling reacts to sustained load (typically 15-30 minute window). Sharp traffic spike lasting 10 minutes can saturate disk IOPS and connections before autoscaling kicks in. Provision for 2x expected peak, not average.

---

## Quick Reference Checklist

When starting capacity sizing engagement:

```text
[ ] What is the working set size? (indexes + hot data)
[ ] Does the working set fit in the target tier's WiredTiger cache?
[ ] What are current/projected IOPS? Which disk type is provisioned?
[ ] What is the monthly storage growth rate? 12-month projection?
[ ] How many app instances x maxPoolSize? Does it fit within tier connection limit?
[ ] Is the oplog window >= 24 hours under peak write load?
[ ] Is there an analytics or reporting workload? Is it isolated to secondaries?
[ ] Is there a load test plan? What is the saturation threshold?
[ ] Are Atlas Alerts configured for disk > 75%, connections > 80%, lag > 60s?
[ ] Is autoscaling enabled, and are the thresholds appropriate?
[ ] If using time series collections: is metaField cardinality bounded? (each unique value = one open bucket ~125 KB in working set)
[ ] If using time series collections: is MongoDB 8.0 available? (10-20x cache reduction from block processing vs 7.0)
```

---

## Time Series Collection Capacity Considerations

Time series collections (MongoDB 5.0+) have distinct working set model from regular collections.

**Working set formula:**
```
Open bucket RAM   = (unique metaField values) × ~125 KB
Recent query RAM  = (query lookback / granularity bucket span) × (unique metaField values) × ~125 KB

Granularity spans: seconds → 3,600 s | minutes → 86,400 s | hours → 2,592,000 s
```

**Example — 10,000 IoT sensors, `minutes` granularity, 1-hour query lookback:**
```
Open buckets   = 10,000 × 125 KB = ~1.2 GB
Recent queries = (3,600 / 86,400) × 10,000 × 125 KB = ~54 MB
Total ≈ 1.3 GB WiredTiger cache pressure
```

**Storage savings:** 70-94% compression vs regular collections for numeric sensor data. Factor into storage growth projections — workload needing 10 TB in regular collection typically needs 0.6-3 TB as time series.

**MongoDB 8.0 block processing:** Direct columnar writes reduce cache usage 10-20x vs MongoDB 7.0. Customer on 7.0 with time series workload hitting cache limits — upgrading to 8.0 is lowest-friction capacity intervention before scaling up.

**High-cardinality metaField anti-pattern:** Each unique `metaField` value holds one open bucket in cache. metaField with 1M+ unique values (e.g., per-user UUIDs) generates ~125 GB open-bucket working set pressure. Diagnose with:
```javascript
db.getCollection("system.buckets.my_collection").countDocuments({ "control.closed": false })
```

For full time series sizing guidance including granularity bucket span reference and working set formulas, see `mongodb-time-series`.

---

## Atlas Flex Tier Sizing Reference

*Cross-pollinated from `mongodb-atlas-flex-serverless` — researched 2026-05-28.*

Flex is now standard entry-level paid Atlas cluster (replaced M2/M5 and Serverless as of January 22, 2026). Sizing decisions must account for Flex's hard limits before recommending dedicated tier.

### Flex hard limits (sizing thresholds)

| Resource | Flex limit | When it triggers upgrade |
|----------|-----------|--------------------------|
| Throughput | 500 ops/sec (combined R+W) | Sustained traffic approaching 400–500 ops/sec |
| Storage | 5 GB (hard cap, auto-managed) | Data projected to exceed 5 GB within 6 months |
| Connections | 500 max | App instances × maxPoolSize approaching 400 |
| Collections | 500 total | Schema designs with many tenant collections |
| Sort memory | 32 MB | Heavy aggregation or sort-heavy queries |
| Aggregation stages | 50 max | Complex pipeline workloads |

### Sizing decision: Flex vs. M10+

Use Flex when:
- Peak throughput < 500 ops/sec with headroom
- Data < 5 GB (development, staging, light production)
- No private networking requirement

Move to M10 dedicated when any single threshold above is hit, or workload requires:
- Performance Advisor access (needed for capacity optimization work)
- PITR backup (compliance/DR requirement)
- Private Endpoints or VPC Peering

### Flex autoscaling behavior
Flex does NOT autoscale beyond 500 ops/sec — it throttles. Unlike dedicated clusters with elastic compute autoscaling, Flex has fixed ceiling. Capacity planning for Flex must treat 500 ops/sec as hard ceiling, not elastic limit.

For full Flex billing model, unsupported features list, and tooling migration, see `mongodb-atlas-flex-serverless`.