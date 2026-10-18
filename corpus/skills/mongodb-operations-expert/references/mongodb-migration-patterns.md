<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-migration-patterns` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-migration-patterns
title: MongoDB Migration Patterns
version: 1.2.0
updated: 2026-05-29
category: mongodb
tags: [mongodb, migration, mongosync, atlas-live-migration, relational-migrator, mongomirror, cutover, validation, sharded-clusters]
description: >
  Strategy and tooling reference for migrating data into, out of, and between MongoDB clusters.
  Covers mongosync, Atlas Live Migration, Relational Migrator, mongomirror (deprecated),
  cutover strategies (blue-green, dual-write, DNS flip), validation patterns, schema
  transformation, sharded-cluster specifics, and a failure taxonomy.

  TRIGGER: customer planning a MongoDB-to-MongoDB migration (on-prem → Atlas, cloud-to-cloud,
  version upgrade, topology change); migrating from a relational DB to MongoDB; designing a
  cutover strategy; troubleshooting mongosync, Atlas Live Migration, or Relational Migrator;
  asking which migration tool to use; advising on oplog window sizing, validation, or rollback.

  SKIP: live cluster-to-cluster operational runbook (use `mongosync` skill); Relational Migrator
  deep-dive for RDBMS schema mapping (use `mongodb-relational-migrator`); Kafka-based CDC
  pipeline design (use `mongodb-kafka-connector`); Spark/Databricks migration (use
  `mongodb-spark-connector`); BI Connector EOL migration to Atlas SQL (use `mongodb-bi-connector`).
keywords: [mongosync, atlas live migration, relational migrator, mongomirror, cutover, blue-green, dual-write, oplog, resharding, mongodump, mongorestore, sharded cluster migration, schema transformation, data validation, BSON, GridFS]
whenToUse:
  - Planning a MongoDB-to-MongoDB migration (on-prem → Atlas, cloud-to-cloud, version upgrade)
  - Migrating from a relational database (Postgres, Oracle, MySQL, SQL Server, DB2, Sybase) to MongoDB
  - Designing a cutover strategy (blue-green, dual-write, DNS flip, write throttle)
  - Validating data integrity before and after a migration
  - Troubleshooting mongosync, Atlas Live Migration, or Relational Migrator failures
  - Planning a sharded cluster migration or resharding operation
  - Advising a customer on tool selection (mongosync vs Atlas Live Migration vs mongodump)
  - Sizing the oplog window for a long-running migration
whenNotToUse:
  - Operational runbook for a live mongosync job (use `mongosync` skill — it covers the full state machine, resumption, verification modes, and rollback via `reversible:true`)
  - Deep RDBMS schema mapping with Relational Migrator (use `mongodb-relational-migrator`)
  - CDC pipeline architecture with Kafka (use `mongodb-kafka-connector`)
  - Spark or Databricks migration paths (use `mongodb-spark-connector`)
  - BI Connector EOL → Atlas SQL Interface transition (use `mongodb-bi-connector`)
related_skills:
  - mongosync
  - mongodb-relational-migrator
  - mongodb-kafka-connector
  - mongodb-spark-connector
  - mongodb-bi-connector
  - mongodb-schema-design
  - mongodb-sharding
---

# MongoDB Migration Patterns

## Tool Selection Decision Tree

```
Is source a relational DB (Postgres, Oracle, MySQL, SQL Server, DB2, Sybase)?
  YES → Use Relational Migrator
  NO (source is MongoDB):
    Is the destination Atlas, and can Atlas reach the source network?
      YES, and source is MongoDB 6.0.8+:
        → Use Atlas Live Migration (guided, managed)
      YES, but air-gapped / strict firewall:
        → Use mongosync (self-managed) with Atlas as destination
      NO, source < 6.0:
        → Upgrade source to 6.0+ first, then use Atlas Live Migration or mongosync
        → For source < 4.x: mongodump/mongorestore + manual validation
    Is it a cluster-to-cluster move (no Atlas involvement)?
      → Use mongosync
    Is mongomirror currently in use?
      → Migrate to mongosync (mongomirror is deprecated)
```

---

## Description

A comprehensive reference for migrating data into, out of, and between MongoDB clusters.
Covers the full toolchain — mongosync (GA), Atlas Live Migration, Relational Migrator,
the deprecated mongomirror — plus cutover strategies, validation patterns, schema
transformation guidance, sharded-cluster specifics, and a taxonomy of common failure
modes.

---

## 1. MongoSync (GA Tool)

mongosync is MongoDB's **generally available** cluster-to-cluster synchronization binary.
It replaced mongomirror as the recommended migration path for MongoDB-to-MongoDB moves.

### What it does

- Performs an initial full-copy of all databases, collections, indexes, and views from
  source to destination.
- After the full copy completes, enters **CDC mode**: tails the source oplog and applies
  change events (inserts, updates, deletes, DDL) to the destination continuously.
- Keeps source and destination logically in sync until the operator issues `commit`.

### Supported topologies

| Source              | Destination          | Supported |
|---------------------|----------------------|-----------|
| Replica set         | Replica set          | Yes       |
| Replica set         | Atlas (any tier M10+)| Yes       |
| Sharded cluster     | Sharded cluster      | Yes       |
| Sharded cluster     | Atlas sharded        | Yes       |
| Standalone          | Anything             | No — convert to single-node replica set first |

Minimum MongoDB version: **6.0** on both sides (some features require 7.0+).
Atlas Free (M0), Flex (M2/M5) tiers are **not supported** as destinations.

### Configuration skeleton

```json
{
  "source": {
    "cluster0": {
      "connectionString": "mongodb+srv://user:pass@source.example.mongodb.net",
      "tls": true
    }
  },
  "destination": {
    "cluster0": {
      "connectionString": "mongodb+srv://user:pass@dest.example.mongodb.net",
      "tls": true
    }
  }
}
```

Note: use `"tls": true`, not the deprecated `"ssl": true`.

Launch:
```bash
mongosync \
  --config /etc/mongosync/config.json \
  --logPath /var/log/mongosync
```

### HTTP API (localhost:27182)

```bash
# Start sync
curl -X POST http://localhost:27182/api/v1/start \
  -H 'Content-Type: application/json' \
  -d '{"source":"cluster0","destination":"cluster0"}'

# Monitor progress
curl http://localhost:27182/api/v1/progress

# Pause / resume / commit
curl -X POST http://localhost:27182/api/v1/pause
curl -X POST http://localhost:27182/api/v1/resume
curl -X POST http://localhost:27182/api/v1/commit
```

### Key monitoring fields from `/api/v1/progress`

- `canCommit` — true once lag is near zero; **must be true before issuing commit**.
- `lagTimeSeconds` — replication lag vs. source oplog head. Target < 10 s before cutover.
- `state` — `IDLE | RUNNING | PAUSED | COMMITTING | COMMITTED | FAILED`.
- `collectionCopy.estimatedTotalBytes` / `estimatedCopiedBytes` — full-copy progress.

### Important limitations

- Not suitable for Disaster Recovery or live analytics (read-replica) use cases.
- Filtering is supported (include/exclude namespaces) but cannot transform documents.
- Destination must have **no data** in namespaces being synced before sync starts.
- After `commit`, mongosync is one-directional; rollback requires a reverse sync set up
  in advance (see Section 2) or a blue-green approach (see Section 6).

---

## 2. Cluster-to-Cluster Sync — Phases and Cutover

### Phase 1: Full sync (collection copy)

mongosync issues collection scans in parallel (default 4 concurrent collections, tunable
via `numParallelCollections`). Each document batch is bulk-inserted into the destination.
Indexes are built after collection copy, not during, to maximise write throughput.

Estimate copy time: `totalDataBytes / networkBandwidthBytesPerSec + indexBuildTime`.

```bash
# Tune parallelism for large migrations (more = more source read IOPS)
mongosync --numParallelCollections 8 --config config.json
```

### Phase 2: Change event application (CDC)

After the full copy, mongosync tails the source oplog and replays events in order.
The critical metric is `lagTimeSeconds`. Lag spikes when:

- Source write rate exceeds mongosync's apply rate (network / CPU / destination write
  capacity).
- Large batch inserts generate many oplog entries in a burst.
- TTL deletes generate a sustained stream of delete events.

### Phase 3: Cutover

**Standard cutover sequence:**

1. Verify `canCommit: true` and `lagTimeSeconds < 10` (stricter for low-tolerance apps).
2. Stop writes to the source cluster (application-level write gate or DNS flip).
3. Wait for `lagTimeSeconds == 0` or `state` to indicate fully caught up.
4. Issue `POST /api/v1/commit`. mongosync applies remaining buffered events and stops.
5. Redirect application connection strings to destination.
6. Validate (see Section 7) then decommission source.

### Reverse sync for rollback

mongosync does not automatically support bidirectional sync. To preserve rollback
capability, set up a second mongosync instance **before** committing the forward sync,
running in the opposite direction (destination → source), paused. If anomalies are found
after forward commit, you can resume the reverse instance. This requires:
- Double the connection pool quota on both clusters.
- The reverse instance is started **before** forward commit and kept paused.
- Resume reverse only if rollback is triggered; otherwise abort it after the soak window.

Prefer the simpler blue-green approach (Section 6) unless the data volume makes running
two mongosync instances impractical.

---

## 3. Relational Migrator

MongoDB Relational Migrator converts relational schemas to MongoDB document models and
migrates data from RDBMS sources into MongoDB or Atlas.

### Supported sources (as of 2025-2026)

- PostgreSQL (including TimescaleDB hypertables, PointZ → GeoJSON Point)
- Oracle
- Sybase / SAP ASE
- IBM DB2
- MySQL / MariaDB
- SQL Server

### Core workflow

1. **Connect** — provide JDBC connection to source and Atlas/MongoDB connection string.
2. **Discover** — Migrator inspects table schemas, foreign keys, and constraints.
3. **Design** — AI-assisted suggestions for embedding vs. referencing, array rollups,
   type mappings. Operators review and approve each design decision.
4. **Map** — column-to-field mappings, type conversions, computed fields.
5. **Migrate** — snapshot or continuous CDC migration (CDC requires Debezium connector
   on supported sources). Error threshold is now optional (as of Nov 2025): leaving
   it unchecked allows the migration to continue past errors.
6. **Validate** — Migrator generates post-migration count and error reports.

### Schema suggestion rules (embedded by default when)

- Child table has a 1:1 or 1:few (< ~20) FK relationship to parent.
- Child is never queried independently (no standalone `SELECT` on the child table).
- Child rows are always deleted with the parent (CASCADE DELETE pattern).

Referencing is preferred when the child entity is queried independently or shared
across multiple parents.

### Code conversion

Relational Migrator can convert SQL queries, stored procedures, and DML triggers to:
- MongoDB aggregation pipeline (JavaScript)
- C# (LINQ / MongoDB driver)
- Java (MongoDB driver)

### Example: trigger conversion

Source SQL trigger:
```sql
AFTER INSERT ON orders
BEGIN
  UPDATE customers SET order_count = order_count + 1
  WHERE id = NEW.customer_id;
END;
```

Migrator generates an equivalent Atlas Trigger in JavaScript targeting the `orders`
collection, which increments `orderCount` on the customer document.

### Time-series migration

TimescaleDB hypertables and standard time-series tables can be mapped to MongoDB native
Time Series collections (with `timeField` and `metaField` designations) for optimal
storage compression and query performance.

---

## 4. Atlas Live Migration

> **Ops Manager / Cloud Manager source?** Live Migration also works as a **push** flow when the source is monitored by Ops Manager or Cloud Manager — a migration host runs mongosync next to the source. See `mongodb-ops-manager` for the migration host sizing (8 CPU / 24 GB RAM), source oplog window requirement (must exceed migration duration × 2), and 5.0-and-earlier deprecation matrix.

Atlas Live Migration is the **Atlas-managed** migration service for pulling a source
MongoDB deployment into an Atlas cluster. It uses mongosync under the hood but exposes
the process through the Atlas UI/API with guided steps.

### Prerequisites

- Source: MongoDB **6.0.8+** replica set or sharded cluster.
- Destination: Atlas cluster **M10 or higher** (M0/Flex/M2/M5 not supported).
- Source must be network-accessible from Atlas migration servers (IP allowlist or VPC
  peering / Private Link).
- Source user requires `readAnyDatabase`, `clusterMonitor`, and `backup` roles.

### Pull migration flow (Atlas-initiated)

```
Atlas Migration UI
  → "Migrate Data to this Cluster"
  → Provide source connection string + credentials
  → Atlas provisions a migration host
  → Full copy phase (Atlas UI shows progress %)
  → CDC phase begins; lag indicator drops to green
  → "Prepare to Cut Over" — application stops writes to source
  → "Cut Over" — Atlas commits sync, promotes destination as primary
  → Verify counts and indexes, then close migration
```

### Push migration (self-managed mongosync → Atlas)

When Atlas cannot reach the source (air-gapped, strict firewall), run mongosync locally
with the destination set to the Atlas connection string. Monitor via local HTTP API then
commit manually.

### Version-specific constraints

- Atlas Live Migration requires destination to be on the **same major version** as source
  or one major version ahead (e.g., source 6.0 → dest 6.0 or 7.0).
- Downgrade is not supported via live migration; use mongodump/mongorestore instead.

### Validation after Atlas migration

Atlas generates a migration report with document counts per collection, index counts,
and a checksum sample. Always run an independent count verification (Section 7) — Atlas
reports can miss TTL-expired documents that were deleted between commit and report generation.

---

## 5. mongomirror (Deprecated)

mongomirror was the predecessor to mongosync for MongoDB Community → Atlas migrations.

### Status

**Deprecated.** MongoDB Inc. ended active development. Existing binaries still function
for MongoDB 4.x/5.x sources but mongomirror will not receive new releases for 6.0+.

### Comparison: mongomirror vs. mongosync

| Aspect              | mongomirror                   | mongosync                         |
|---------------------|-------------------------------|-----------------------------------|
| Control plane       | CLI flags only                | HTTP API (localhost:27182)        |
| Sharded support     | Limited                       | Full                              |
| Min source version  | 2.6+                          | 6.0+                              |
| Filtering           | `--includeNamespace` flag     | `includeNamespaces` in start body |
| Active development  | No (deprecated)               | Yes (GA, actively maintained)     |

### Guidance for legacy users

If source cluster is MongoDB 4.x or 5.x: **upgrade source to 6.0+ first**, then use
mongosync. For sources older than 4.0: use mongodump/mongorestore for the initial load,
then apply oplog replay manually or use a staging cluster as an intermediate hop.

---

## 6. Cutover Strategies

### Write throttling

Before cutover, reduce source write rate to shrink the oplog lag window:

1. Identify top write collections: `db.currentOp({op:"insert"})`.
2. Work with the application team to implement a temporary write rate limiter
   (token bucket, feature flag, or connection pool reduction).
3. Target < 100 write ops/sec on source so mongosync lag drops to < 5 s.

### Application-side dual-writes

For zero-downtime migrations where reverting to source must remain possible:

```javascript
// Dual-write middleware (Node.js example)
async function dualWrite(collection, doc) {
  // Write to source is authoritative; destination write is best-effort during soak
  await sourceDb.collection(collection).insertOne(doc);
  // Fire-and-forget to destination during soak period to avoid latency doubling
  destDb.collection(collection).insertOne(doc).catch(err =>
    console.warn("dest write failed, will reconcile:", err.message)
  );
}
```

Run dual-writes for a soak period (1–7 days), validating destination parity continuously.
Flip reads to destination, monitor for errors, then flip writes and disable dual-write.

**Downsides:** source remains authoritative, so partial dest failures require reconciliation;
code complexity; risk of divergence on partial failures. Prefer blue-green unless the
application team cannot tolerate connection string changes.

### Blue-green deployment

Maintain two environments, both running, with mongosync keeping Green current:

```
Blue (source)  ← 100% live traffic
Green (destination, synced via mongosync, lagTimeSeconds < 10)

Cutover sequence:
  1. Shift 5% of reads to Green (shadow / canary traffic).
  2. Verify no errors or data discrepancies over 30–60 min.
  3. Shift 50%, then 100% of reads to Green.
  4. Stop writes to Blue (write gate / feature flag).
  5. Commit mongosync (stops CDC from Blue).
  6. Shift 100% of writes to Green.
  7. Monitor Green for 24 h; decommission Blue.
```

Rollback: revert load-balancer weights to Blue within the soak window (before Blue is
decommissioned). This is why decommissioning Blue is the last step.

### DNS-flip cutover

Fastest option, highest risk. Lower the CNAME/SRV TTL to 30–60 s at least 24 h before
cutover. At cutover time, update the DNS record to point to the destination cluster. Use
only when:
- The application has robust connection retry with exponential backoff.
- Rollback window is acceptable (TTL propagation delay).
- You have confirmed `lagTimeSeconds == 0` immediately before the flip.

---

## 7. Validation Patterns

### Document count verification

```javascript
// Run on both source and destination immediately after commit
const collections = await db.listCollections().toArray();
for (const col of collections) {
  const srcCount = await sourceDb.collection(col.name).countDocuments();
  const dstCount = await destDb.collection(col.name).countDocuments();
  if (srcCount !== dstCount) {
    console.error(`MISMATCH ${col.name}: src=${srcCount} dst=${dstCount}`);
  } else {
    console.log(`OK ${col.name}: ${srcCount} docs`);
  }
}
```

### Index verification

```javascript
// Compare index names per collection
async function verifyIndexes(srcDb, dstDb, collectionName) {
  const srcIdxs = await srcDb.collection(collectionName).listIndexes().toArray();
  const dstIdxs = await dstDb.collection(collectionName).listIndexes().toArray();
  const srcNames = new Set(srcIdxs.map(i => i.name));
  const dstNames = new Set(dstIdxs.map(i => i.name));
  for (const n of srcNames) {
    if (!dstNames.has(n)) console.error(`Missing index on dest: ${n}`);
  }
  for (const n of dstNames) {
    if (!srcNames.has(n)) console.warn(`Extra index on dest (not in src): ${n}`);
  }
}
```

### Sampling-based data verification

For large collections where full comparison is impractical:

```javascript
// Sample 1000 random documents and compare field-by-field
const samples = await sourceDb.collection("orders")
  .aggregate([{ $sample: { size: 1000 } }])
  .toArray();

// Helper: sort object keys for stable JSON serialization
function stableStringify(obj) {
  if (obj === null || typeof obj !== "object") return JSON.stringify(obj);
  if (Array.isArray(obj)) return "[" + obj.map(stableStringify).join(",") + "]";
  const keys = Object.keys(obj).sort();
  return "{" + keys.map(k => JSON.stringify(k) + ":" + stableStringify(obj[k])).join(",") + "}";
}

const crypto = require("crypto");
for (const doc of samples) {
  const dest = await destDb.collection("orders").findOne({ _id: doc._id });
  if (!dest) { console.error(`DOC MISSING on dest: _id=${doc._id}`); continue; }
  const srcHash = crypto.createHash("sha256").update(stableStringify(doc)).digest("hex");
  const dstHash = crypto.createHash("sha256").update(stableStringify(dest)).digest("hex");
  if (srcHash !== dstHash) console.error(`DOC MISMATCH _id=${doc._id}`);
}
```

### dbHash-based collection checksum

The `dbHash` admin command computes a per-collection MD5 fingerprint over all documents
in storage order. It is the recommended way to compare entire collections deterministically:

```javascript
// mongosh — run on source, then on destination; compare the per-collection hash
const srcHash = db.adminCommand({ dbHash: 1, collections: ["orders"] });
// returns: { collections: { orders: "<md5-hex>" }, md5: "<overall-db-md5>", ... }

const dstHash = db.adminCommand({ dbHash: 1, collections: ["orders"] });

if (srcHash.collections.orders !== dstHash.collections.orders) {
  console.error("Collection checksum MISMATCH for orders");
} else {
  console.log("Collection checksum OK for orders");
}
```

Note: `dbHash` acquires a brief read lock and works on both replica sets and sharded
clusters. For sharded clusters run it per-shard (connect to each shard's primary
directly) — the top-level `md5` field reflects all compared collections. Not suitable
while writes are in flight — run only after stopping writes on source (post-cutover).

### Oplog window verification (pre-migration)

Before starting mongosync, ensure the source oplog window covers the full-copy phase.
Run all of the following in **mongosh** (not the Node.js driver):

```javascript
// mongosh — check current minimum retention setting
db.adminCommand({ getParameter: 1, oplogMinRetentionHours: 1 });

// mongosh — set minimum retention window (preferred; WiredTiger honoured at next cycle)
db.adminCommand({ setParameter: 1, oplogMinRetentionHours: 48 });

// mongosh — also resize the physical oplog cap to 50 GB if needed
db.adminCommand({ replSetResizeOplog: 1, size: 51200 }); // size in MB

// mongosh — estimate current oplog window empirically
const first = db.getSiblingDB("local").oplog.rs
  .find({}, { ts: 1 }).sort({ $natural:  1 }).limit(1).next();
const last  = db.getSiblingDB("local").oplog.rs
  .find({}, { ts: 1 }).sort({ $natural: -1 }).limit(1).next();
const windowHours = (last.ts.t - first.ts.t) / 3600;
print(`Current oplog window: ~${windowHours.toFixed(1)} hours`);
// Target: window > 2× estimated full-copy duration
```

---

## 8. Schema Transformation

### Embedding vs. referencing decision matrix

| Signal                              | Embed child in parent | Reference (separate collection) |
|-------------------------------------|-----------------------|---------------------------------|
| Always accessed together            | Yes                   | No                              |
| Child count bounded (< ~100)        | Yes                   | No                              |
| Child updated independently         | No                    | Yes                             |
| Child shared across multiple parents| No                    | Yes                             |
| Need to paginate child list         | No                    | Yes                             |
| Child is a large sub-document       | No (16 MB doc limit)  | Yes                             |
| Child count unbounded over time     | No                    | Yes                             |

### Denormalization opportunities during migration

Migration is the best time to denormalize because data is already being transformed.

**Lookup elimination:**
```javascript
// Relational: orders JOIN order_lines JOIN products
// MongoDB: embed product snapshot into each order line
{
  _id: ObjectId("..."),
  orderId: "ORD-001",
  lines: [
    {
      productId: "P-42",
      productName: "Widget",      // denormalized snapshot
      productSku: "WDG-42",       // denormalized snapshot
      qty: 3,
      unitPrice: 9.99
    }
  ]
}
```

**Counter caching:**
```javascript
// Instead of COUNT(*) from child table at query time:
{ _id: "customer-123", orderCount: 47, totalSpend: 4391.22 }
// Maintained via Atlas Triggers or application-level atomic increment
```

**Polymorphic pattern for type hierarchies:**
```javascript
// Single SQL table with nullable columns per type → MongoDB discriminated union
{ _id: "...", type: "credit_card", last4: "4242", expiry: "12/27" }
{ _id: "...", type: "bank_account", routing: "021000021", accountLast4: "6789" }
// Index on `type` for efficient type-specific queries
```

### Type mapping reference

| SQL type              | MongoDB BSON type             | Notes                                       |
|-----------------------|-------------------------------|---------------------------------------------|
| INT / BIGINT          | Int32 / Int64                 | Match precision to avoid overflow           |
| VARCHAR / TEXT        | String                        | Strip collation constraints                 |
| DECIMAL(p,s)          | Decimal128                    | Preserves precision; use for money          |
| TIMESTAMP / DATETIME  | Date                          | Store as UTC; apply timezone in app layer   |
| BOOLEAN               | Bool                          | Direct mapping                              |
| BLOB / BYTEA          | BinData                       | Large blobs → GridFS if > 16 MB             |
| UUID                  | UUID (BinData subtype 4)      | String is simpler for cross-driver compat   |
| POINT / GEOMETRY      | GeoJSON                       | Use GeoJSON for 2dsphere index support      |
| ARRAY (PG)            | Array                         | Direct; nested arrays supported             |
| JSONB (PG)            | Document (embedded)           | Natural fit; no change needed               |
| SERIAL / SEQUENCE     | ObjectId or Int64 counter     | ObjectId preferred for distributed inserts  |

---

## 9. Sharded Cluster Migrations

### Pre-migration planning

1. **Shard key audit**: Inspect existing shard keys for cardinality, write distribution,
   and query routing. Migration is the lowest-cost time to reselect a poor shard key.
2. **Chunk distribution**: Run `sh.status()` on source; note jumbo chunks (cannot be
   moved and may require manual splitting before migration).
3. **Config server metadata**: Sharded config metadata (databases, collections, chunks)
   must also be migrated — mongosync handles this automatically.

```javascript
// Find jumbo chunks before migration
use config;
db.chunks.find({ jumbo: true }).forEach(c =>
  print(`${c.ns} shard=${c.shard} min=${JSON.stringify(c.min)}`)
);
// Split jumbo chunks manually before starting mongosync:
sh.splitAt("mydb.orders", { customerId: "split-point-value" });
```

### mongosync with sharded clusters

mongosync spawns one sync worker **per shard**. Each worker independently copies its
shard's data and tails its shard's oplog. The config server is synced separately.

Key constraint: the destination sharded cluster must have **the same number of shards
or more** as the source. If re-sharding is desired, do it on the destination **after**
mongosync commits (online resharding does not interrupt traffic).

### Resharding after migration

MongoDB 6.0+ supports online resharding without downtime:

```javascript
// Reshard a collection to a better shard key (non-blocking online operation)
db.adminCommand({
  reshardCollection: "mydb.orders",
  key: { customerId: "hashed" },
  numInitialChunks: 90,
  collation: { locale: "simple" }
});

// Monitor resharding progress
db.adminCommand({ currentOp: true, type: "resharding" });
// Look for: remainingOperationTimeEstimatedSecs, approxBytesToCopy, bytesCopied
```

Resharding creates a new physical collection, syncs from existing shards, then performs
a sub-second commit. Duration scales with data volume (~1 GB/sec on Atlas M60+).

### Zone sharding for geographic migrations

When migrating to a multi-region Atlas cluster:

```javascript
// mongosh — assign shards to zones
sh.addShardToZone("atlas-shard-0", "US-EAST");
sh.addShardToZone("atlas-shard-1", "EU-WEST");

// Define key ranges that route to each zone.
// MinKey() / MaxKey() are mongosh constructor calls that produce BSON sentinels.
sh.updateZoneKeyRange(
  "mydb.users",
  { region: "US", _id: MinKey() },   // open lower bound for US region
  { region: "US", _id: MaxKey() },   // open upper bound for US region
  "US-EAST"
);
sh.updateZoneKeyRange(
  "mydb.users",
  { region: "EU", _id: MinKey() },
  { region: "EU", _id: MaxKey() },
  "EU-WEST"
);
// Note: the shard key must include { region: 1, _id: 1 } (or hashed variant)
// for zone ranges keyed on { region, _id } to be valid.
```

### Chunk balancer management

Pause the balancer on the destination during the initial full-copy phase to reduce
competing write amplification:

```javascript
sh.stopBalancer();     // before mongosync start (or at minimum before commit)
// Verify balancer is stopped:
sh.getBalancerState(); // should return false

sh.startBalancer();    // after commit and initial validation complete
```

---

## 10. Common Failures and Remediation

### Oplog window exhaustion

**Symptom:** mongosync logs `oplog required timestamp is no longer available` or
`ChangeStreamHistoryLost`.

**Cause:** The full-copy phase takes longer than the oplog retention window on the source.

**Remediation:**
1. **Pre-migration:** set minimum retention before starting.
   ```javascript
   db.adminCommand({ setParameter: 1, oplogMinRetentionHours: 48 });
   ```
2. **Already exhausted:** stop mongosync, resize oplog, restart from `start` (full restart,
   not resume). There is no way to resume a sync after oplog gap — always start fresh.

### Connection limit exhaustion

**Symptom:** `too many connections` errors; mongosync workers failing to connect.

**Cause:** mongosync opens one connection pool per shard per parallelism thread. Large
sharded clusters with high `numParallelCollections` exhaust Atlas connection limits.

**Remediation:**
```bash
# Reduce parallelism — default is 4, try 2 for large sharded clusters
mongosync --numParallelCollections 2 --config config.json

# Check current Atlas connection limit (scales with tier):
# M10: 1500, M20: 3000, M30: 3000, M40: 6000, M60: 16000
# Upgrade cluster tier if needed, or reduce numParallelCollections further
```

### Network bottlenecks

**Symptom:** `lagTimeSeconds` rises steadily; full-copy throughput < 10 MB/s.

**Diagnosis:**
```bash
# Check mongosync throughput in logs
grep "bytesWritten\|throughput" /var/log/mongosync/mongosync.log | tail -20

# Test raw network bandwidth source → destination host
iperf3 -c <destination-ip> -t 30 -P 4
```

**Remediation:** Colocate the mongosync host with the source in the same
datacenter/VPC. Use Atlas Private Link or VPC peering to eliminate public internet
transit. Cross-region migrations: expect 50–200 MB/s; plan copy duration accordingly.

### Large document errors (> 16 MB)

**Symptom:** `BSONObjectTooLarge` errors during copy phase.

**Cause:** Source documents exceed BSON's 16 MB document limit (common after migrating
large JSON blobs from a relational system into MongoDB without size management).

**Remediation:**
1. Identify offending documents before migration:
   ```javascript
   db.collection.find().forEach(doc => {
     const size = Object.bsonsize(doc);
     if (size > 15 * 1024 * 1024) {
       print(`Large doc: _id=${doc._id} size=${(size/1024/1024).toFixed(1)} MB`);
     }
   });
   ```
2. Migrate large binary payloads to GridFS before running mongosync:
   ```javascript
   const { GridFSBucket } = require("mongodb");
   const bucket = new GridFSBucket(db, { bucketName: "attachments" });
   const uploadStream = bucket.openUploadStream("filename.pdf", {
     metadata: { sourceDocId: doc._id }
   });
   uploadStream.end(largeBuffer);
   // Replace the large field on the source document with a GridFS fileId reference
   await db.collection("docs").updateOne(
     { _id: doc._id },
     { $set: { attachmentRef: uploadStream.id }, $unset: { largePayload: "" } }
   );
   ```

### Duplicate key errors on destination

**Symptom:** mongosync fails with `E11000 duplicate key error`.

**Cause:** Unique indexes on destination already contain conflicting data from a partial
prior run, or the destination was not fully cleaned before restart.

**Remediation:**
```javascript
// Drop all migrated namespaces and restart from scratch
// (do NOT attempt to resume after a partial clean)
use mydb;
db.getCollectionNames().forEach(name => {
  db.getCollection(name).drop();
  print(`Dropped: ${name}`);
});
// Then restart mongosync from 'start' (not 'resume')
```

### Atlas Live Migration fails at validation phase

**Symptom:** Atlas reports count mismatch after live migration.

**Common causes:**
- TTL deletes ran on source during/after commit (documents expired between snapshot
  and validation).
- Multi-document transactions were in flight at commit time.

**Remediation:**
1. Disable TTL indexes on source before the "Prepare to Cut Over" step:
   ```javascript
   // Record TTL index definitions, then disable them
   db.runCommand({ collMod: "sessions", index: { keyPattern: { expireAt: 1 }, expireAfterSeconds: 0 } });
   // (Set to 0 disables deletion but keeps the index structure)
   ```
2. Ensure no long-running transactions span the commit window.
3. Re-enable TTL on destination after validation passes.

---

## Anti-Patterns

| Anti-pattern                                        | Why it fails                                                     | Correct approach                                            |
|-----------------------------------------------------|------------------------------------------------------------------|-------------------------------------------------------------|
| Running mongosync against a standalone mongod       | mongosync requires replica set; standalone has no oplog          | Convert to single-node replica set first                    |
| Starting mongosync with data already in destination | Duplicate key errors; undefined sync behavior                    | Drop destination namespaces before starting                 |
| Using mongomirror on MongoDB 6.0+ source            | mongomirror is deprecated and untested against 6.0+              | Use mongosync                                               |
| Committing before `canCommit: true`                 | Destination may be missing recent writes                         | Wait for `canCommit` and `lagTimeSeconds < 10`              |
| Not resizing oplog before a large migration         | Oplog window exhausted mid-copy; must restart from scratch       | Pre-set `oplogMinRetentionHours` to 2× estimated copy time  |
| Skipping post-migration count validation            | Silent data loss goes undetected                                 | Always run count + index + sampling validation              |
| Migrating without a defined rollback path           | No rollback if anomalies found post-cutover                      | Plan blue-green or reverse sync before cutover              |
| Embedding unbounded arrays                          | Document hits 16 MB BSON limit as array grows                    | Reference child collection when child count is unbounded    |
| Keeping a poor shard key after migration            | Cardinality / hotspot issues carry forward into Atlas            | Audit shard key; run reshardCollection post-migration       |
| Running balancer during full-copy phase             | Chunk moves compete with sync writes, increasing lag             | `sh.stopBalancer()` before copy; restart after commit       |
| Ignoring TTL indexes at cutover                     | Documents expire on source post-commit, causing count mismatches | Disable TTL on source before "Prepare to Cut Over"          |
| Using `"ssl": true` in mongosync config             | Deprecated key; may not work in future releases                  | Use `"tls": true`                                           |

---

## References

1. [mongosync Documentation — MongoDB Docs](https://www.mongodb.com/docs/mongosync/current/)
2. [Cluster-to-Cluster Sync FAQ — MongoDB Docs](https://www.mongodb.com/docs/cluster-to-cluster-sync/current/faq/)
3. [Mongosync Quickstart — MongoDB Docs](https://www.mongodb.com/docs/mongosync/current/quickstart/)
4. [Atlas Live Migration (Pull) — MongoDB Docs](https://www.mongodb.com/docs/atlas/import/c2c-pull-live-migration/)
5. [Migrate or Import Data — Atlas Docs](https://www.mongodb.com/docs/atlas/import/index.html)
6. [Relational Migrator Release Notes — MongoDB Docs](https://www.mongodb.com/docs/relational-migrator/release-notes/)
7. [Migrate to MongoDB Atlas on AWS with Relational Migrator — MongoDB Blog](https://www.mongodb.com/blog/post/migrate-mongodb-atlas-aws-relational-migrator)
8. [Migration to MongoDB Atlas: Your Options — MongoDB Products](https://www.mongodb.com/products/platform/migrate-to-atlas-options)
9. [Atlas Architecture Center: Migration — MongoDB Docs](https://www.mongodb.com/docs/atlas/architecture/current/migration/)
10. [Resharding a Collection — MongoDB Docs](https://www.mongodb.com/docs/manual/core/sharding-reshard-a-collection/)

---

## Cross-Cluster Replication via Kafka (addendum)

The **MongoDB Kafka Connector** provides an alternative to mongosync for cross-cluster replication when Kafka is already in the pipeline, or when heterogeneous MongoDB versions, region-local fan-out, or intermediate transformation are required:

```
Source MongoDB (change stream)
  → MongoDB Source Connector → Kafka topic
  → MongoDB Sink Connector (ChangeStreamHandler CDC handler)
  → Target MongoDB cluster
```

Use `change.data.capture.handler=com.mongodb.kafka.connect.sink.cdc.mongodb.ChangeStreamHandler` on the sink to faithfully replay insert/update/replace/delete operations from the source change stream. This is distinct from mongosync — it adds Kafka as a durable intermediary and enables fan-out to multiple sinks (e.g., Atlas + Elasticsearch + S3 from the same topic).

**When to prefer mongosync over Kafka Connector for migration:** Full-fidelity copy with oplog replay, no transformation needed, one-time cutover. **When to prefer Kafka Connector:** Ongoing CDC replication, existing Kafka infrastructure, multi-sink fan-out, or intermediate processing.

See `mongodb-kafka-connector` skill for full connector configuration.

## See Also: BI Connector Migration

When migrating from BI Connector to Atlas SQL Interface (EOL Sept 2026), use the `mongodb-bi-connector` skill — it covers the MongoSQL Transition Readiness Tool, DRDL schema porting decisions, driver swap procedures, and SQL-92 dialect compatibility assessment.

## See Also: mongosync Operational Runbook

When the chosen migration pattern is a **live cluster-to-cluster move with continuous CDC** — Atlas Live Migration, standalone mongosync, or MongoDB 7.0 Cluster-to-Cluster Sync — load the `mongosync` skill for the operational depth: cluster URI setup (`--cluster0`/`--cluster1`), `includeNamespaces`/`excludeNamespaces` filters with regex, the IDLE/RUNNING/PAUSED/COMMITTING/COMMITTED/REVERSING state machine, oplog window sizing to avoid `ChangeStreamHistoryLost`, one-mongosync-per-shard topology, verification modes (embedded, dbHash, document count, migration-verifier), reverse sync for rollback (`reversible:true` + `enableUserWriteBlocking:true`), and the decision matrix for which mongosync variant fits a given cluster size, network constraint, and version delta. This skill (`mongodb-migration-patterns`) stays at the strategy/comparison layer; `mongosync` is the runbook layer.

## See Also: MongoDB Spark Connector (Spark/Databricks migration paths)

When the migration target is **a Spark or Databricks-based analytics platform** (Delta Lake, lakehouse, ML feature store) rather than another MongoDB cluster, load `mongodb-spark-connector`. Migration patterns:

- **Mongo → Delta Lake (one-time backfill + ongoing CDC)** — Spark Connector for the historical batch read; Spark Connector change-stream source for the incremental tail. Resume-token loss requires snapshot recovery.
- **Mongo → Delta Lake (production CDC, strict ordering)** — Kafka Source Connector → Confluent → Spark/Delta Live Tables. Better backpressure and replay than direct Spark Connector.
- **Mongo → Snowflake / BigQuery via Spark** — Spark Connector reads Mongo, Spark writes the warehouse; less common than Federation-based or CDC-based pipelines but useful when transform logic lives in PySpark.

The decision rule mirrors the Kafka-vs-Spark Connector trade-offs in this skill: choose Spark Connector for ad-hoc/medium-volume transformations and ML feature jobs; choose Kafka + Source Connector for production CDC with strict ordering, multi-consumer fan-out, or replay semantics. See `mongodb-spark-connector` section 11 for the full Spark-side comparison matrix.
