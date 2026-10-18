<!-- hub-reference-banner -->
> **Reference file — part of the `atlas-diagnostics-expert` hub.** Formerly the standalone `mongodb-performance-benchmarking` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-performance-benchmarking
title: MongoDB Performance Benchmarking and Load Testing
version: "1.1.1"
last-updated: "2026-07-14"
category: mongodb
description: >
  MongoDB performance benchmarking and load testing — proactive methodology, tool selection, and
  workload characterization for MongoDB Atlas and self-managed deployments.
  TRIGGER: benchmarking MongoDB throughput or latency, YCSB workloads (A–F), Atlas tier selection
  backed by performance data, load testing with Locust/PyMongo/sysbench/k6, connection pool sizing
  under load, interpreting explain() output for index effectiveness measurement, Atlas Performance
  Advisor recommendations, establishing pre-change baselines before index changes or schema migrations,
  or when a customer asks "how many ops/second can we handle", "will M30 be enough",
  "did this index actually help", or "what benchmark methodology should I use".
  SKIP: diagnosing an already-running production system's slowness (use mongodb-performance-troubleshooting),
  pure query optimization without benchmarking context (use mongodb-query-performance),
  Atlas tier cost comparison without performance data (use mongodb-cost-optimization),
  connection pool exhaustion in production (use mongodb-performance-troubleshooting or mongodb-connection-string).
tags:
  - benchmarking
  - performance
  - load-testing
  - ycsb
  - atlas
  - capacity-planning
  - wiredtiger
  - connection-pool
keywords:
  - mongodb benchmarking
  - YCSB MongoDB
  - workload A B C D E F
  - Atlas tier selection
  - Locust PyMongo
  - sysbench-mongo
  - k6 MongoDB
  - connection pool benchmarking
  - explain executionStats
  - Atlas Performance Advisor
  - ops per second MongoDB
  - M30 vs M50 benchmark
  - baseline methodology
  - cold cache warm cache
  - query targeting ratio
  - IXSCAN vs COLLSCAN
  - thread sweep saturation
  - writecon majority latency
  - mongolocust
  - idealo mongodb-performance-test
whenToUse:
  - Before recommending an Atlas tier upgrade or downgrade
  - Customer asks "how many ops/second can our cluster handle?"
  - Validating that an index change improved (not degraded) performance
  - Investigating whether a reported slowdown is application, driver, or server-side
  - Pre-migration baseline: capture current performance before moving to Atlas
  - Capacity planning for a new workload or product launch
  - Explaining or presenting benchmark results to stakeholders
  - Selecting the right benchmark tool (YCSB, Locust, sysbench, k6)
  - Understanding YCSB workload archetypes A–F and when to use each
  - Connection pool sizing experiments under realistic concurrency
whenNotToUse:
  - Diagnosing slowness in an already-running production system — use mongodb-performance-troubleshooting
  - Pure query optimization without a benchmarking or baseline context — use mongodb-query-performance
  - Atlas tier cost comparison without performance validation — use mongodb-cost-optimization
  - Connection pool exhaustion debugging in production — use mongodb-performance-troubleshooting or mongodb-connection-string
  - Atlas Performance Advisor in isolation (without benchmarking context) — use mongodb-monitoring-observability
related_skills:
  - mongodb-performance-troubleshooting
  - mongodb-query-performance
  - mongodb-capacity-planning
  - mongodb-wiredtiger
  - mongodb-connection-string
  - mongodb-monitoring-observability
  - mongodb-atlas-expert
  - mongodb-stress-and-resilience-testing
---

# MongoDB Performance Benchmarking and Load Testing

## Overview

This skill covers proactive benchmarking methodology, load testing tools, and workload characterization for MongoDB deployments — both self-hosted and Atlas. It enables TAMs and engineers to establish performance baselines, validate infrastructure decisions before production, and present benchmark results to stakeholders.

Benchmarking MongoDB is fundamentally different from benchmarking relational databases: document size variance, write concern levels, read preference, and working-set-to-RAM ratios each produce non-linear effects on throughput and latency that simple micro-benchmarks miss.

## When to Use

- Before recommending an Atlas tier upgrade or downgrade
- When a customer asks "how many ops/second can our cluster handle?"
- To validate that an index change improved (not degraded) performance
- When investigating whether a reported slowdown is application, driver, or server-side
- Pre-migration baseline: capture current system performance before moving to Atlas
- Capacity planning for a new workload or product launch

## Tool Quick-Select

| Goal | Best Tool |
|------|-----------|
| Standardized NoSQL benchmark (A–F workloads) | YCSB |
| Raw sustained write/insert throughput | sysbench-mongo |
| Realistic Python workloads / aggregation pipelines | Locust + PyMongo |
| Full-stack app benchmark (REST layer + MongoDB) | k6 |
| Post-hoc slow query analysis on Atlas | Atlas Performance Advisor |
| Quick multi-threaded throughput test, zero config | idealo/mongodb-performance-test |

---

## 1. Benchmarking Tools

### YCSB (Yahoo Cloud Serving Benchmark)

The industry-standard benchmark for NoSQL and cloud databases. The MongoDB binding is mature and widely used for comparative testing.

- **Repo**: https://github.com/brianfrankcooper/YCSB
- **Language**: Java (requires JDK 8+, Maven)
- **Strengths**: Well-defined workload taxonomy (A-F), widely cited in academic and vendor comparisons, supports Atlas via connection string
- **Weaknesses**: Java-only driver, synthetic key-value access patterns may not match complex document queries

**Build the MongoDB binding:**
```bash
git clone https://github.com/brianfrankcooper/YCSB.git
cd YCSB
mvn -pl site.ycsb:mongodb-binding -am clean package
```

**Key YCSB MongoDB parameters:**
```
mongodb.url           MongoDB connection string (Atlas: full SRV URI)
mongodb.auth          true/false — enable authentication
mongodb.writeConcern  majority | w1 | w0
mongodb.readPreference primary | secondaryPreferred | nearest
mongodb.batchsize     Documents per batch for bulk inserts
mongodb.maxconnections Connection pool cap
```

### sysbench-mongo

Percona's sysbench fork adapted for MongoDB. Lower overhead than YCSB for raw insert/update throughput tests. Lua-scriptable for custom workloads.

- **Repo**: https://github.com/tmcallaghan/sysbench-mongodb
- Best suited for: sustained write throughput, insert-heavy benchmarks, replica set write amplification tests

### Locust + PyMongo

Python-based load testing framework. Write realistic mixed workloads with full Python flexibility — aggregation pipelines, multi-document transactions, custom document structures.

```python
from locust import User, task, between
from pymongo import MongoClient

class MongoUser(User):
    wait_time = between(0.01, 0.05)
    
    def on_start(self):
        self.client = MongoClient(
            "mongodb+srv://...",
            maxPoolSize=50,
            serverSelectionTimeoutMS=5000
        )
        self.col = self.client["bench"]["orders"]
    
    @task(8)
    def read_order(self):
        self.col.find_one({"orderId": random_id()})
    
    @task(2)
    def insert_order(self):
        self.col.insert_one(new_order())
```

**Advantages over YCSB**: Realistic document structures, Python ecosystem for data generation, built-in web UI for real-time metrics, Kubernetes-native with Locust distributed mode.

### k6

JavaScript-based load testing tool (Grafana k6). Does not have a native MongoDB driver — typically used against a REST/GraphQL layer in front of MongoDB, making it useful for end-to-end application benchmarks rather than raw driver-level tests.

- Use k6 when benchmarking the full stack (application server + MongoDB)
- Use YCSB/Locust when benchmarking MongoDB directly

### mongolocust (sabyadi/mongolocust)

Thin wrapper that exposes standard MongoDB CRUD operations as Locust tasks with configurable read/write ratios. Good starting point for teams already using Python.

- **Repo**: https://github.com/sabyadi/mongolocust

### Atlas Performance Advisor (post-hoc)

Not a load testing tool — a monitoring surface. Analyzes the slow operations log to surface index recommendations ranked by impact. Used after a benchmark or in production to identify optimization opportunities. Covered in depth in Section 4.

### idealo/mongodb-performance-test

Simple Java multi-threaded tool for throughput and latency measurement. Less configurable than YCSB but requires zero setup beyond a JAR.

- **Repo**: https://github.com/idealo/mongodb-performance-test

---

## 2. YCSB Workload Reference

YCSB defines six canonical workloads (A–F). Each targets a specific application archetype. When benchmarking MongoDB, run all six to produce a complete performance profile.

### Workload A — Session Store (50/50 Read/Update)
```
readproportion=0.5
updateproportion=0.5
```
Simulates a session store for a web container. 50% reads, 50% updates on existing records. Most demanding on write performance and WiredTiger cache pressure.

**Use when**: Testing write amplification, replication lag under mixed load, or impact of `writeConcern: majority`.

### Workload B — Read-Mostly (95/5 Read/Update)
```
readproportion=0.95
updateproportion=0.05
```
Models a photo tagging application where most operations are reads. Good for validating read scale-out with `readPreference: secondaryPreferred`.

**Use when**: Testing secondary read offloading, replica set read scaling.

### Workload C — Read-Only Cache (100% Read)
```
readproportion=1.0
```
Exercises pure read throughput. Establishes the maximum theoretical read ops/sec. Always warm the cache before recording Workload C numbers.

**Use when**: Establishing peak read throughput baseline, validating index coverage.

### Workload D — Read-Latest (95/5 Read/Insert)
```
readproportion=0.95
insertproportion=0.05
```
Inserts new records and reads the most **recently inserted** ones — reads are skewed toward the tail of the dataset, not uniformly distributed. This is the key distinction from Workload B. Models social network status updates or event streams where users read fresh content. Tests monotonically growing collections, insertion hotspots, and cache pressure from constantly-changing hot pages.

**Use when**: Testing time-ordered data, TTL collection performance, insert scaling, or validating that recently-inserted documents remain cache-hot.

### Workload E — Scan-Heavy (95/5 Scan/Insert)
```
scanproportion=0.95
insertproportion=0.05
```
Short range scans (typically 1–100 records). Most demanding on index range-scan efficiency. Exercises `$gte/$lte` style queries.

**Use when**: Testing range queries, index scan efficiency, cursor performance.

### Workload F — Read-Modify-Write (50/50 Read/Read-Modify-Write)
```
readproportion=0.5
readmodifywriteproportion=0.5
```
Read a record, modify it, write it back — a common pattern for counters and state machines. Tests the full read-modify-write cycle including network round-trips.

**Use when**: Testing document-level locking behavior, counter patterns, update performance.

### Running YCSB Against Atlas

**Phase 1: Load data**
```bash
./bin/ycsb load mongodb -s \
  -P workloads/workloada \
  -p recordcount=5000000 \
  -p mongodb.url="mongodb+srv://user:pass@cluster.mongodb.net/bench?w=majority&readPreference=primary" \
  -p mongodb.auth=true \
  -threads 16
```

**Phase 2: Run benchmark**
```bash
./bin/ycsb run mongodb -s \
  -P workloads/workloada \
  -p operationcount=1000000 \
  -p mongodb.url="mongodb+srv://user:pass@cluster.mongodb.net/bench" \
  -threads 32 \
  2>&1 | tee workloada-t32.txt
```

### Parsing YCSB Output

YCSB outputs per-operation statistics. Key lines to extract:

```
[OVERALL], Throughput(ops/sec), 12847.3        <- aggregate ops/s
[READ], AverageLatency(us), 345.2
[READ], Percentile95thLatency(us), 892.0       <- p95
[READ], Percentile99thLatency(us), 2341.0      <- p99
[READ], Percentile99.9thLatency(us), 8920.0    <- p999
[UPDATE], AverageLatency(us), 1203.7
[UPDATE], Percentile99thLatency(us), 4500.0
```

Always report latency in **microseconds** from YCSB output but convert to **milliseconds** when presenting to stakeholders.

**Recommended thread sweep**: Run at 2, 4, 8, 16, 32, 64, 128 threads. Plot throughput vs. thread count to find the saturation knee. The knee is where adding threads no longer increases throughput and latency begins rising sharply.

---

## 3. Workload Characterization

Before benchmarking, characterize the production workload so synthetic tests reflect reality. Benchmarking the wrong workload produces misleading results.

### Read/Write Ratio
Profile production using `db.serverStatus().opcounters`. Take two samples separated by a known interval — mongosh does not have a built-in `sleep()`, so use a shell loop or run the command twice manually:
```js
// Sample 1 — run this, wait 60 seconds, then run Sample 2
const before = db.serverStatus().opcounters;
// ... wait 60 seconds ...

// Sample 2
const after = db.serverStatus().opcounters;
const elapsed = 60; // seconds between samples
const readRate  = (after.query - before.query) / elapsed;
const writeRate = (after.insert + after.update + after.delete -
                   before.insert - before.update - before.delete) / elapsed;
print(`Reads/s: ${readRate.toFixed(0)}, Writes/s: ${writeRate.toFixed(0)}`);
print(`Read/write ratio: ${(readRate / writeRate).toFixed(1)}:1`);
```

Alternatively, use `mongostat --rowcount 2 --sleep 60` from the shell to get two consecutive 60-second samples.

### Document Size Distribution
Sample the hot collection to understand document size:
```js
db.orders.aggregate([
  { $sample: { size: 1000 } },
  { $project: { size: { $bsonSize: "$$ROOT" } } },
  { $group: {
    _id: null,
    avgBytes: { $avg: "$size" },
    p95Bytes: { $percentile: { input: "$size", p: [0.95], method: "approximate" } },
    maxBytes: { $max: "$size" }
  }}
])
```
Document size directly affects WiredTiger cache efficiency. A 100KB average document means 10,000 documents fill 1GB of RAM.

### Working Set Size Estimation
The working set is the subset of data (indexes + hot documents) that must fit in RAM for optimal performance.

```js
// Check if working set fits in cache
const status = db.serverStatus();
const cacheUsed = status.wiredTiger.cache["bytes currently in the cache"];
const cacheMax  = status.wiredTiger.cache["maximum bytes configured"];
const readInto  = status.wiredTiger.cache["pages read into cache"];
const evictions = status.wiredTiger.cache["unmodified pages evicted"];

// High evictions relative to reads = working set exceeds cache
print(`Cache utilization: ${(cacheUsed/cacheMax*100).toFixed(1)}%`);
print(`Pages read into cache: ${readInto}, Unmodified pages evicted: ${evictions}`);
print(`Eviction ratio: ${(evictions/readInto*100).toFixed(1)}%`);
```

**Rule of thumb**: If `unmodified pages evicted` > 5% of `pages read into cache`, the working set does not fit in RAM and you will see cache-miss-driven I/O under load.

### Index Selectivity
Low selectivity indexes (e.g., boolean field) waste cache space and slow writes without helping reads:
```js
// Check index usage stats
db.orders.aggregate([{ $indexStats: {} }])
// Focus on: accesses.ops (how often), since (last reset)
```

### Hotspot Patterns
Monotonically increasing `_id` (ObjectId) creates insertion hotspots on the rightmost shard/chunk. Use hashed shard keys or time-bucketed keys for even distribution in sharded clusters.

### Connection Pool Requirements
Estimate required connections:
```
Required connections = (peak concurrent threads per app server) × (number of app servers)
Each mongod in a 3-node replica set receives: maxPoolSize × number of app servers connections
```

---

## 4. Atlas Performance Advisor

### How It Works

The Performance Advisor monitors all queries against the slow operations log (default threshold: 100ms, adjustable in Atlas UI). It analyzes query execution plans and identifies patterns where missing indexes cause full collection scans or large document examinations.

**Availability**: M10 and above dedicated tiers only. Not available on shared (M0/M2/M5) tiers.

**Analysis window options**: 1 hour, 24 hours, 7 days.

### Index Ranking

Recommendations are ranked by two scores:
- **Impact**: High or Medium — based on total wasted bytes read across all queries matching that pattern
- **Average Query Targeting**: Lower is better — ratio of keys examined to documents returned

The most actionable recommendations have **High impact + low query targeting**.

### Reading Recommendations

```
Suggested index: { customerId: 1, orderDate: -1 }
Impact: High
Avg Query Targeting: 1842.3  <- Very bad (examining 1842x more docs than returned)
Queries analyzed: 47 shapes
```

An `avgQueryTargeting` score above 10 indicates the query is examining far more data than it returns. Atlas considers queries with a score above 1000 high-priority.

### Limitations and When to Question Suggestions

1. **Sampled data only**: Advisor analyzes queries exceeding the threshold — fast queries that run billions of times per day are invisible to it
2. **Atlas-only**: No equivalent for self-hosted (use `db.currentOp()` + `system.profile` instead)
3. **No write overhead analysis**: A suggested compound index may improve reads but significantly slow writes on high-ingest collections — always test the suggested index under write load before applying in production
4. **Redundant indexes**: Advisor may suggest `{ a: 1, b: 1 }` when `{ a: 1, b: 1, c: 1 }` already exists
5. **Cannot suggest indexes for ctime timestamp format** — set timestamp format to `iso8601-utc` first

### Using Performance Advisor in Benchmark Analysis

After running a benchmark, increase the Atlas slow query threshold to 0ms temporarily to capture all query shapes:
```
Atlas UI → Cluster → Performance Advisor → Configure → Slow Query Threshold: Custom (0ms)
```
This surfaces patterns that complete quickly in isolation but degrade under load.

---

## 5. Connection Pool Benchmarking

### Default Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `maxPoolSize` | 100 | Max connections per mongod in replica set |
| `minPoolSize` | 0 | Min connections kept warm |
| `waitQueueTimeoutMS` | 0 (no limit) | Max wait time for a connection from pool |
| `connectTimeoutMS` | 30000 | Timeout for new connection establishment |
| `socketTimeoutMS` | 0 (no limit) | Timeout for socket reads/writes — **avoid setting this**; use `maxTimeMS()` on queries instead to let the server cancel gracefully |

### Connection Math

For a 3-node replica set with 4 app servers, each with `maxPoolSize=100`:
- **From one app server**: 100 × 3 = 300 outgoing connections
- **At each mongod**: 100 × 4 = 400 incoming connections
- **Total across cluster**: 400 × 3 = 1,200 connections

MongoDB's `maxIncomingConnections` is very high by default (effectively unbounded on modern Linux), but the practical ceiling is OS file descriptor limits — typically 65,536 on default Linux configurations (`ulimit -n`). Atlas manages this automatically; self-hosted deployments must tune `ulimit` and `net.maxIncomingConnections` in `mongod.conf`.

### Benchmarking Optimal Pool Size

Use a thread sweep to find the saturation point:

```python
# Locust config: vary users from 10 → 1000
# Watch these metrics at each concurrency level:
# 1. Throughput (ops/s) — should increase then plateau
# 2. p99 latency — should be stable then spike
# 3. db.serverStatus().connections.current — pool exhaustion signal
# 4. db.serverStatus().globalLock.currentQueue.total — queue buildup
```

**Pool exhaustion symptoms**:
- `waitQueueTimeoutMS` errors in driver logs
- `db.serverStatus().connections.current` ≈ `maxPoolSize × replica-set-members`
- p99 latency rises sharply while p50 stays stable (timeout-driven outliers)

### Tiered Pool Sizing Strategy (2025 best practice)

```javascript
// Critical OLTP operations (user-facing, <100ms SLA)
const criticalClient = new MongoClient(uri, {
  maxPoolSize: 50,
  minPoolSize: 10,
  waitQueueTimeoutMS: 1000,    // Fail fast — surface pool exhaustion quickly
  connectTimeoutMS: 5000
});

// Analytics / reporting operations (relaxed SLA)
// Note: readPreference must be specified in the URI or as a ReadPreference object,
// not as a bare string in the options object.
const analyticsClient = new MongoClient(
  uri + "?readPreference=secondaryPreferred",
  {
    maxPoolSize: 10,
    minPoolSize: 2,
    waitQueueTimeoutMS: 30000   // Allow queuing for long-running aggregations
  }
);
```

### Monitoring Pool During Benchmark

```js
// Run this during benchmark to detect pool saturation
db.serverStatus().connections
// {
//   current: 387,          <- active connections
//   available: 51413,      <- OS-level slots remaining
//   totalCreated: 412,
//   active: 156,           <- connections with in-flight operations
//   threadsAwaitingConnection: 0   <- queue depth (danger if > 0 consistently)
// }
```

---

## 6. Index Effectiveness Measurement

### explain() Verbosity Levels

```js
// executionStats — what you actually ran
db.orders.find({ customerId: "C123", status: "pending" })
         .explain("executionStats")

// allPlansExecution — all plans considered (helps understand rejection)
db.orders.find({ customerId: "C123", status: "pending" })
         .explain("allPlansExecution")
```

### Key explain() Fields for Benchmarking

| Field | Meaning | Target |
|-------|---------|--------|
| `executionStats.nReturned` | Documents returned | — |
| `executionStats.totalDocsExamined` | Documents scanned | ≈ nReturned |
| `executionStats.totalKeysExamined` | Index keys scanned | ≈ nReturned for selective queries |
| `executionStats.executionTimeMillis` | Wall time | < SLA threshold |
| `queryPlanner.winningPlan.stage` | Top-level stage | `IXSCAN` preferred over `COLLSCAN` |

### IXSCAN vs COLLSCAN

```js
// Bad: COLLSCAN — scans entire collection
{
  "stage": "COLLSCAN",
  "docsExamined": 2847392,
  "nReturned": 47
}
// Ratio = 60,583:1 — catastrophically inefficient

// Good: IXSCAN
{
  "stage": "IXSCAN",
  "keysExamined": 51,
  "docsExamined": 47,
  "nReturned": 47
}
// Ratio = 1.09:1 — nearly optimal

// Optimal: Covered query (IXSCAN with no FETCH stage)
{
  "stage": "PROJECTION_COVERED",
  "inputStage": { "stage": "IXSCAN" }
}
// totalDocsExamined: 0 — data served entirely from index
```

### Query Targeting Ratio

```
queryTargetingRatio = totalKeysExamined / nReturned
```

- **1.0–2.0**: Excellent — index is highly selective
- **2.0–10.0**: Good — minor index key scanning overhead
- **10.0–100.0**: Investigate — consider compound index refinement
- **>100.0**: Poor — index may be wrong field order or low cardinality

### Measuring Index Effectiveness Under Load

Run YCSB Workload C (read-only) before and after adding an index:

```bash
# Baseline: no index on customerId
./bin/ycsb run mongodb -P workloads/workloadc -threads 32 > baseline.txt

# Add index (use mongosh; legacy mongo shell removed in MongoDB 6.0+)
mongosh --eval 'db.orders.createIndex({ customerId: 1 })'

# After index: warm cache, then measure
./bin/ycsb run mongodb -P workloads/workloadc -threads 32 > after_index.txt

# Compare throughput and p99
grep "Percentile99" baseline.txt after_index.txt
```

---

## 7. Baseline Methodology

### The Core Principle

**Measure everything, assume nothing.** A baseline is a frozen snapshot of system behavior under a defined workload. Without it, "improvement" is unmeasurable.

### Establishing a Baseline

1. **Match production data volume**: Use a dataset at least 10% of production size (ideally 100%). Benchmarking with 10,000 documents when production has 100M produces invalid results.

2. **Match production schema and indexes**: Export production index definitions:
   ```js
   db.orders.getIndexes()
   ```
   Apply them to the benchmark cluster before running any tests.

3. **Match document structure**: Use production-representative documents, not synthetic uniform data. Skewed field distributions, nested arrays, and large string fields all affect performance differently.

4. **Warm the cache first**: Always run a "warm-up" pass before recording baseline numbers:
   ```bash
   # Warm-up: run 200k ops to fill WiredTiger cache, discard results
   ./bin/ycsb run mongodb -P workloads/workloadc -p operationcount=200000 -threads 16 > /dev/null
   
   # Now record baseline
   ./bin/ycsb run mongodb -P workloads/workloadc -p operationcount=1000000 -threads 32 > baseline.txt
   ```

5. **Run for at least 30 minutes**: Short runs (< 5 minutes) miss WiredTiger checkpoint storms, TTL deletes, background compaction, and replication lag spikes.

6. **Run at consistent times**: Atlas shared infrastructure can show 20–30% throughput variance between peak and off-peak hours. Run benchmarks at the same time of day across comparisons.

### A/B Testing with Identical Workloads

To isolate the effect of a single change (new index, schema change, tier upgrade):

```text
Test A: baseline configuration, 30-minute run, record p50/p95/p99 + throughput
Change ONE variable
Test B: same workload, same thread count, same data, 30-minute run
```

Never change multiple variables between A and B. If you upgrade the tier AND add an index simultaneously, you cannot attribute the improvement.

### Statistical Significance

For latency comparisons:
- Run each configuration at least 3 times
- Report median of the 3 runs (not best)
- If p99 varies by >15% across runs, investigate variance sources before declaring a winner
- MongoDB's own benchmark specifications use 100 timing samples and take the median

### Controlling for Cache Effects

| Test Type | Cache State | When to Use |
|-----------|------------|-------------|
| Cold cache | Empty (after mongod restart) | Disaster recovery scenarios, first-query latency |
| Warm cache | Pre-populated to steady state | Production read performance (most common) |
| Cache churn | Working set > RAM | Memory-constrained tier validation |

```bash
# Force cold cache (Atlas: resize cluster to flush, or use separate benchmark cluster)
# Self-hosted: restart mongod
# Then measure Time-to-First-Query for specific operations
```

---

## 8. Atlas Tier Selection Guide

### Tier Overview

| Tier | RAM | Storage | vCPU | Storage Type | Use Case |
|------|-----|---------|------|-------------|----------|
| M10 | 2GB | 10GB | Dedicated (low) | SSD | Dev, small non-critical |
| M20 | 4GB | 20GB | Dedicated (low) | SSD | Pre-prod, light read workloads |
| M30 | 8GB | 40GB | Dedicated | SSD | Production-ready baseline |
| M40 | 16GB | 80GB | Dedicated | NVMe | High-throughput OLTP |
| M50 | 32GB | 160GB | Dedicated | NVMe | Large working sets |
| M60 | 64GB | 320GB | Dedicated | NVMe | Memory-heavy analytics |
| M80 | 122GB | 760GB | Dedicated | NVMe | Large replica sets |
| M200 | 244GB | 3.1TB | Dedicated | NVMe | Very large datasets |
| M400 | 488GB | 4TB+ | Dedicated | NVMe | Maximum single-node scale |

Note: M0/M2/M5 are the true shared-tier clusters (free/low-cost, multi-tenant). M10+ are all dedicated. M10/M20 have lower vCPU allocations than M30+ but are not shared infrastructure.

### NVMe vs Standard SSD Impact on Benchmarks

NVMe tiers (M40+) provide 5–10x higher I/O throughput vs standard SSDs. This only matters when the **working set does not fit in RAM**. If working set fits in WiredTiger cache (typically 50% of RAM), storage type is irrelevant for read latency.

**Benchmark implication**: Benchmarks on M30 with warm cache and small working set may show similar latency to M50 NVMe. The NVMe advantage appears when:
- Working set > available RAM (cache misses hit disk)
- High write throughput with large checkpoints
- Bulk insert/bulk delete operations

### Atlas Autoscaling Impact on Benchmark Consistency

Autoscaling can resize the cluster mid-benchmark, invalidating results. **Always disable autoscaling before benchmarking**:

```
Atlas UI → Cluster → Edit → Auto-Scaling → Disable Cluster Tier Scaling
```

Re-enable after benchmarking completes.

### Multi-Region Latency Benchmarks

For multi-region clusters, the dominant latency contributor is replication round-trip. With `writeConcern: majority`:
- US-East to US-West electable secondary: ~70ms added to write latency
- US-East to EU-West: ~100ms added to write latency
- Use `readPreference: nearest` to measure local vs. remote read latency difference

```js
// Measure write latency with different write concerns
const t = Date.now();
await collection.insertOne(doc, { writeConcern: { w: "majority" } });
console.log(`majority write: ${Date.now() - t}ms`);

const t2 = Date.now();
await collection.insertOne(doc, { writeConcern: { w: 1 } });
console.log(`w:1 write: ${Date.now() - t2}ms`);
```

---

## 9. Anti-Patterns

### 1. Benchmarking with Cold Cache and Calling It "Production Performance"

Production MongoDB runs with a warm WiredTiger cache. A cold-cache benchmark measures worst-case startup performance, not steady-state. Always warm the cache and discard the warm-up phase results.

### 2. Using Localhost Instead of Real Network

Driver latency over loopback (~0.05ms) vs. real network (~0.5–5ms) can make a 10x difference on low-operation-count benchmarks. Always benchmark from a client on the same network segment as production (same VPC/VNet for Atlas).

### 3. Unrealistic Document Sizes

YCSB default document size is 1KB (10 fields × ~100 bytes each). If production documents average 50KB (embedded arrays, large text fields), YCSB throughput numbers overstate performance by 10–50x. Override with:
```
-p fieldlength=5000    # 5KB average field size
-p fieldcount=20       # 20 fields per document
```

### 4. Single-Threaded Testing

MongoDB WiredTiger is designed for concurrent access. Single-thread benchmarks understate throughput by 5–20x. Always test at production-representative concurrency levels (100+ concurrent connections is common for production apps).

### 5. Not Matching Production Index Configuration

Running benchmarks without production indexes makes writes appear faster (no index maintenance overhead) and reads either deceptively fast (full scan over a warm small dataset) or slower (no index to accelerate lookups). Export index definitions and apply them to the benchmark cluster before running:
```js
// Export from production
db.orders.getIndexes()
// Recreate each index on the benchmark cluster before any test run
```

### 6. Ignoring Replication Lag

Benchmarks targeting only the primary with `writeConcern: w:1` do not reflect production replica sets using `writeConcern: majority`. The latency difference can be 2–10x. Always use the same write concern as production.

### 7. Misinterpreting Throughput Plateau as Maximum Capacity

When throughput stops increasing with more threads, it often means the **client** is saturated (CPU, network bandwidth, connection pool), not MongoDB. Verify by:
- Monitoring Atlas CPU (< 70% = MongoDB not the bottleneck)
- Checking driver-side queue depth (`threadsAwaitingConnection`)
- Adding more client machines

### 8. Using the Wrong Request Distribution

YCSB defaults to Zipfian distribution (a small number of hot keys receive most traffic — like a typical web app). If your production access pattern is truly uniform (every document accessed equally), the default overestimates cache hit rate and understates average latency. Match the distribution to your actual access pattern:
```
-p requestdistribution=uniform    # All records equally likely
-p requestdistribution=zipfian    # Default: hot records (power law)
-p requestdistribution=latest     # Newest records most likely
```

### 9. Not Running Long Enough for WiredTiger Checkpoints

WiredTiger performs checkpoints every 60 seconds by default. A 5-minute benchmark will include ~5 checkpoint events, which temporarily spike write latency. A 30-minute benchmark averages these out for a representative p99.

### 10. Comparing Benchmarks Across Different Atlas Regions

AWS us-east-1 consistently outperforms AWS ap-southeast-1 for MongoDB Atlas benchmarks due to infrastructure generation differences. Always run baseline and comparison benchmarks in the same region.

---

## 10. Reporting Benchmark Results

### Core Metrics to Report

| Metric | How to Measure | Why It Matters |
|--------|---------------|----------------|
| Throughput (ops/s) | YCSB `[OVERALL], Throughput` | Peak capacity |
| p50 latency | YCSB `Percentile50thLatency` | Typical user experience |
| p95 latency | YCSB `Percentile95thLatency` | Near-worst-case user experience |
| p99 latency | YCSB `Percentile99thLatency` | SLA compliance threshold |
| p999 latency | YCSB `Percentile99.9thLatency` | Tail latency / outlier detection |
| Error rate | YCSB `[READ/UPDATE/INSERT], Return=ERROR` count / total ops | Stability under load |
| CPU utilization | Atlas Metrics tab | Headroom remaining |
| Cache hit ratio | `wiredTiger.cache` | Working set fit |

### Latency Reporting Convention

Always report as a table across thread counts, not just the best result:

| Threads | Throughput (ops/s) | p50 (ms) | p95 (ms) | p99 (ms) |
|---------|--------------------|----------|----------|----------|
| 8 | 4,200 | 1.2 | 3.4 | 8.7 |
| 16 | 7,800 | 1.4 | 4.1 | 12.3 |
| 32 | 13,400 | 2.1 | 6.8 | 28.4 |
| 64 | 18,900 | 4.2 | 14.1 | 67.2 |
| 128 | 19,100 | 8.9 | 42.3 | 198.0 |

The row where throughput plateaus and p99 spikes is the saturation point — the practical operating maximum for that configuration.

### Stakeholder Presentation Structure

1. **Executive summary** (1 slide): "M30 handles 13,400 ops/s at <30ms p99. M50 handles 22,100 ops/s at <30ms p99. Peak projected load of 18,000 ops/s requires M50."

2. **Methodology slide**: State exact tool, workload type, dataset size, thread count, Atlas tier, region, writeConcern. Without this, benchmarks are unverifiable.

3. **Comparison table**: Before/after or tier A vs. tier B. Never present a single benchmark in isolation.

4. **Resource utilization**: CPU and cache charts from Atlas Metrics during the benchmark window. High throughput at 90% CPU means no headroom; high throughput at 40% CPU means room to grow.

5. **Caveats**: State what the benchmark does NOT test (complex aggregations, transactions, multi-collection joins, production schema complexity).

### Correlation with Infrastructure Metrics

Use Atlas Metrics during benchmark runs to correlate:
- **Disk IOPS spikes** → checkpoint intervals or working set exceeds cache
- **CPU spikes** → aggregation pipelines, sort stages, full collection scans
- **Network throughput** → may cap before MongoDB does (especially on M10/M20)
- **Replication lag** → write concern `majority` latency inflation

### db.collection.latencyStats() for In-Production Benchmarking

For production performance sampling without a benchmark harness:
```js
// Captures latency histograms for actual production traffic
db.orders.latencyStats({ histograms: true })
// Returns read, write, commands latency buckets
// Compare p50/p99 before and after an index change
```

---

## References

- [YCSB GitHub — brianfrankcooper/YCSB](https://github.com/brianfrankcooper/YCSB)
- [YCSB MongoDB README](https://github.com/brianfrankcooper/YCSB/blob/master/mongodb/README.md)
- [How to Benchmark MongoDB with YCSB — ScaleGrid](https://scalegrid.io/blog/how-to-benchmark-mongodb-with-ycsb/)
- [MongoDB Performance Benchmarking — benchant.com](https://benchant.com/blog/mongodb-benchmarking)
- [Benchmarking MongoDB: Tools and Methodologies — Reintech](https://reintech.io/blog/benchmarking-mongodb-performance-tools-methods)
- [Atlas Performance Advisor — MongoDB Docs](https://www.mongodb.com/docs/atlas/analyze-slow-queries/)
- [Optimizing MongoDB with Performance Advisor — MongoDB Blog](https://www.mongodb.com/blog/post/optimizing-mongodb-deployment-performance-advisor)
- [Connection Pool Performance Tuning — MongoDB Docs](https://www.mongodb.com/docs/manual/tutorial/connection-pool-performance-tuning/)
- [MongoDB Connection Pool Overview — MongoDB Docs](https://www.mongodb.com/docs/manual/administration/connection-pool-overview/)
- [Connection Pooling Optimization Strategies — QueryLeaf Blog](https://www.queryleaf.com/blog/2025/10/21/mongodb-connection-pooling-optimization-strategies-advanced-connection-management-and-performance-tuning-for-high-throughput-applications/)
- [Explain Results — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/explain-results/)
- [IXSCAN vs COLLSCAN — oneuptime.com](https://oneuptime.com/blog/post/2026-03-31-mongodb-ixscan-vs-collscan-explain/view)
- [Performance Best Practices: Data Modeling and Memory Sizing — MongoDB](https://www.mongodb.com/resources/products/capabilities/performance-best-practices-mongodb-data-modeling-and-memory-sizing)
- [MongoDB Performance Advisor — oneuptime.com](https://oneuptime.com/blog/post/2026-03-31-mongodb-atlas-performance-advisor/view)
- [MongoDB sysbench benchmark — Percona Blog](https://www.percona.com/blog/benchmark-mongodb-sysbench/)
- [Load Testing MongoDB with Locust — DEV Community](https://dev.to/herjean7/load-testing-mongodb-with-locust-518)
- [mongolocust — sabyadi/mongolocust](https://github.com/sabyadi/mongolocust)
- [Best Load Testing Tools 2025 — DEV Community](https://dev.to/_d7eb1c1703182e3ce1782/best-load-testing-tools-for-developers-in-2025-k6-jmeter-locust-and-more-4513)
- [MongoDB Benchmark Specifications — MongoDB Specs](https://specifications.readthedocs.io/en/latest/benchmarking/benchmarking/)

## See Also

- [[mongodb-performance-troubleshooting]] — Diagnosing performance issues in running systems
- [[mongodb-query-performance]] — Query optimization, index strategies, aggregation pipeline tuning
- [[mongodb-capacity-planning]] — Right-sizing Atlas clusters, storage growth forecasting
