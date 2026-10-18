---
name: shard-a-collection
title: Shard a collection
summary: Choose a shard key, check the prerequisites, create the supporting index, run shardCollection, and verify chunk distribution and balancer health.
applies_to: [atlas, self-managed]
sources:
  - skills/mongodb-expert/references/mongodb-sharding.md
  - skills/mongodb-expert/references/mongodb-time-series.md
  - skills/mongodb-expert/references/mongodb-multi-tenancy.md
  - skills/mongodb-expert/references/mongodb-indexes-deep.md
  - skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md
  - skills/mongodb-operations-expert/references/mongodb-mongosync.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md
  - llms/mongodb.com.llms/llms-full.txt
---
# Shard a collection

## When to use
- A single replica set cannot keep up with write throughput, the working set no longer fits in RAM, or the data volume needs to be spread across nodes.
- You have already exhausted vertical scaling, indexing and schema fixes. The corpus calls "sharding too early" an anti-pattern because it adds operational complexity.
- The cluster is already a sharded cluster (Atlas `SHARDED` type, or self-managed with `mongos`, config servers and 2+ shards). If it is still a replica set, run the recipe `convert-replica-set-to-sharded-cluster` first.

## Prerequisites (checklist)
- [ ] You connect through `mongos`, never directly to a shard. Check: `db.hello()` returns `"msg": "isdbgrid"`.
- [ ] Config servers are a dedicated 3-member replica set and you run 2+ `mongos` instances (production-readiness checklist in the corpus).
- [ ] The collection and database names are known (placeholders below: `mydb.orders`).
- [ ] You have a shard key candidate and know the top read and write query shapes (which filters appear most often).
- [ ] You have checked that the candidate key passes the four criteria in step 1.
- [ ] For unique indexes: every unique index includes the shard key as a prefix.
- [ ] You understand the shard key is hard to change: refine (4.4+) or reshard (5.0+) exist, but resharding is a heavy operation. See the recipe `reshard-a-collection`.
- [ ] Atlas only: a dedicated tier with cluster type `SHARDED`, and a database user allowed to run sharding commands.

## Steps

### 1. Pick the shard key
Score each candidate on the four criteria from the corpus: cardinality (many distinct values), frequency (even spread, no dominant value), monotonicity (not monotonically increasing, or hashed), and query pattern (the key or a prefix appears in common filters).

```text
Decision guide (from the corpus)
- Monotonic field such as ObjectId or a timestamp, write-heavy  -> hashed:   { _id: "hashed" }
- Range scans on one field are the main read path               -> ranged:   { orderId: 1 }
- Multi-tenant, tenant-scoped reads                             -> compound: { tenantId: 1, _id: 1 }
- Need distribution plus per-entity range reads                 -> compound with hashed prefix: { tenantId: "hashed", createdAt: 1 }
Compound design rules: equality fields first, high cardinality before low, range fields last.
```
Expect: one candidate key whose first field appears in most filters and is not low-cardinality (for example `status` or `continent`, which cap the chunk count at the number of distinct values).

Limits stated in the corpus: a shard key size limit of 512 bytes (Verify in the current MongoDB docs: this older limit may be stale in current versions); a compound key can contain one hashed field (4.4+); hashed indexes truncate floating-point values to 64-bit integers, so 2.3, 2.2 and 2.9 hash to the same value (use integer or Decimal128 for hashed numeric fields).

### 2. Sample the workload and analyze the key (MongoDB 7.0+)
```javascript
// mongosh, connected to mongos
db.adminCommand({ configureQueryAnalyzer: "mydb.orders", mode: "full" })

// after enough real traffic has been sampled
db.adminCommand({ analyzeShardKey: "mydb.orders", key: { customerId: 1, createdAt: 1 } })
```
Expect: output with `keyCharacteristics` (cardinality, frequency, monotonicity metrics) and `readWriteDistribution` (how reads and writes would route across shards). Reject keys with low cardinality, a dominant value, or monotonic writes. On versions below 7.0 do a manual workload analysis instead.

Verify in the current MongoDB docs: the sampling options for `configureQueryAnalyzer` (for example a sample rate) and how to switch sampling off afterwards (`mode: "off"`).

### 3. Create the supporting index
A non-empty collection needs an index that starts with the shard key before you shard it. For a hashed key, build a hashed index.
```javascript
use mydb
// ranged or compound key
db.orders.createIndex({ customerId: 1, createdAt: 1 })
// hashed key (alternative)
db.orders.createIndex({ _id: "hashed" })
```
Expect: `createIndexes` returns `ok: 1`. On a large collection the build takes time; wait for it to finish before step 5.

Verify in the current MongoDB docs: the exact rule on when `shardCollection` creates the index for you (empty collections) versus failing (non-empty collections without a usable index). The mongosync reference in this corpus shows a tool-level `createSupportingIndexes: true` option, which confirms the index is a separate requirement.

### 4. Enable sharding on the database
```javascript
sh.enableSharding("mydb")
```
Expect: `ok: 1`. On Atlas you may also do this from the collection UI flow ("Create, View, Drop, and Shard Collections" in the Atlas docs index); the mongosh path below works the same.

### 5. (Optional) Define zones before sharding an empty collection
Pre-defining zones lets MongoDB create chunks for the zone ranges at shard time.
```javascript
sh.addShardToZone("shard0001", "zone-alpha")
sh.addShardToZone("shard0002", "zone-beta")
sh.updateZoneKeyRange("mydb.orders", { customerId: "A" }, { customerId: "M" }, "zone-alpha")
sh.updateZoneKeyRange("mydb.orders", { customerId: "M" }, { customerId: "Z" }, "zone-beta")
```
The zone range bounds must use the shard key or a prefix of it; here they use `customerId`, the leading field of the example key `{ customerId: 1, createdAt: 1 }`. Do not use a field that is not in the shard key (such as `region`).
Expect: each call returns `ok: 1`. Zone ranges are inclusive lower, exclusive upper, and cannot overlap. For a hashed key the ranges must use hashed values (use `convertShardKeyToHashed("someValue")` to compute one). Zone sharding is not supported for time series collections.

### 6. Shard the collection
```javascript
// ranged
sh.shardCollection("mydb.orders", { customerId: 1, createdAt: 1 })
// or hashed
sh.shardCollection("mydb.orders", { _id: "hashed" })
// or hashed prefix + ranged suffix
sh.shardCollection("mydb.events", { tenantId: "hashed", createdAt: 1 })
```
Expect: `collectionsharded: "mydb.orders"` and `ok: 1`.

MongoDB 8.0+ alternative that distributes data immediately instead of waiting for the balancer (the corpus says it wraps `shardCollection` plus `reshardCollection` and recommends it when the deployment meets the resharding resource requirements):
```javascript
sh.shardAndDistributeCollection("mydb.orders", { customerId: "hashed" })
```
Expect: `ok: 1`; see the `reshard-a-collection` recipe for the resource requirements.

Pre-splitting notes from the corpus: `shardCollection` accepts a `numInitialChunks` option for an empty collection sharded with a hashed key (the `reshard-a-collection` recipe also uses it). Verify in the current MongoDB docs: the default initial chunk count for an empty hashed-key collection (the corpus says 1 chunk per shard since 8.0, and 2 per shard in 7.0). To pre-split manually on a ranged key, use `sh.splitAt()` and `moveRange` (the Database Manual index lists "Create Ranges in a Sharded Cluster" for pre-splitting with `moveRange`).

### 7. Check the balancer
```javascript
sh.getBalancerState()
sh.balancerCollectionStatus("mydb.orders")
```
Expect: `true`, and a status for the collection that reports `balanced` once migrations settle. The balancer starts moving chunks when the difference between the largest and smallest shard exceeds 3x the chunk size (default chunk size 128 MB). At most one migration runs per shard at a time.

Optional: restrict migrations to off-peak hours.
```javascript
use config
db.settings.updateOne(
  { _id: "balancer" },
  { $set: { activeWindow: { start: "22:00", stop: "06:00" } } },
  { upsert: true }
)
```
Expect: `matchedCount`/`upsertedCount` of 1. Times follow the config server primary's local timezone.

## Verify
```javascript
sh.status()                              // collection listed with its shard key
sh.status(true)                          // verbose: chunks, zones, jumbo flags
db.orders.getShardDistribution()         // data and document counts per shard
use config
db.chunks.aggregate([{ $match: { ns: "mydb.orders" } }, { $group: { _id: "$shard", count: { $sum: 1 } } }])
db.chunks.find({ jumbo: true })          // should be empty
```
Expect:
- `sh.status()` shows the shard key you chose and chunks on more than one shard after migrations finish.
- `getShardDistribution()` shows a roughly even split. A strong skew means a frequency or monotonicity problem.
- Targeting check: `db.orders.explain("executionStats").find({ customerId: "C123" })` should hit one shard; a `SHARD_MERGE` stage on common queries means scatter-gather.
- On a hashed key, equality queries on the key stay targeted, range queries become scatter-gather.

Atlas path: the Atlas UI "Review Sharded Clusters" metrics page (linked in the Atlas docs index) and the commands above (run through the cluster's `mongos` connection string) give the same view.

## Rollback / abort
- Before data is large: the corpus covers reversing the key, not unsharding on older versions. In MongoDB 8.0+, `unshardCollection` converts a sharded collection back to unsharded (named in the 7.0-vs-8.0 reference).
- To change the key later: `refineCollectionShardKey` (4.4+, adds suffix fields, no data movement) or `reshardCollection` (5.0+); see the `reshard-a-collection` recipe.
- If the balancer floods production: set an `activeWindow` (step 7) or run `sh.stopBalancer()`, then re-enable with `sh.startBalancer()`. Do not leave it off indefinitely.
- For cluster-level migration off a poor design, a rebuild via mongosync with a `sharding` entry is described in the corpus; that is a migration, not an in-place rollback.

Verify in the current MongoDB docs: whether `unshardCollection` is available and permitted on your deployment (for example Atlas tier and version restrictions) before you rely on it.

## Pitfalls
- ObjectId or a timestamp as a ranged key: all inserts go to the MaxKey chunk. Use `{ _id: "hashed" }` or a compound key with a high-cardinality or hashed prefix.
- Low-cardinality keys (`status`, `continent`): the maximum chunk count equals the number of distinct values.
- One dominant value: creates jumbo chunks that cannot be split or moved. Add a unique or high-cardinality suffix.
- Key not present in common filters: every query becomes scatter-gather and does not scale with shard count.
- Sharding on a field that gets updated: the corpus lists this as a schema anti-pattern because it forces documents to move between shards.
- Unique indexes that do not include the shard key as a prefix.
- Leaving the balancer disabled indefinitely: data skews over time. Use an active window instead.
- Connecting directly to a shard: bypasses routing. In 8.0+ only an allowlist of commands works against a shard directly, so audit health-check and backup scripts.
- Time series collections: the shard key may contain only the `metaField`, its sub-fields, or (deprecated in 8.0) the `timeField`; zone sharding is not supported; time series resharding needs 8.0.10+.
- Large `skip()` on sharded queries: `mongos` fetches and discards; use range-based pagination on the shard key.

## Sources
- Four selection criteria and failure modes: `skills/mongodb-expert/references/mongodb-sharding.md:164`
- analyzeShardKey and configureQueryAnalyzer (7.0+): `skills/mongodb-expert/references/mongodb-sharding.md:173`
- Key limits (512 bytes, unique index prefix): `skills/mongodb-expert/references/mongodb-sharding.md:193`
- Ranged, hashed (float truncation caveat), compound rules: `skills/mongodb-expert/references/mongodb-sharding.md:206`, `:217`, `:235`
- Jumbo chunks and detection: `skills/mongodb-expert/references/mongodb-sharding.md:312`
- Balancer threshold, migration limits, active window, state commands: `skills/mongodb-expert/references/mongodb-sharding.md:339`
- Zones and pre-defining zones, time series limitation: `skills/mongodb-expert/references/mongodb-sharding.md:426`, `:490`
- shardAndDistributeCollection (8.0+): `skills/mongodb-expert/references/mongodb-sharding.md:628`
- Diagnostics (sh.status, config.chunks, checklist): `skills/mongodb-expert/references/mongodb-sharding.md:656`
- Anti-patterns and readiness checklist: `skills/mongodb-expert/references/mongodb-sharding.md:724`, `:756`
- Quick-reference commands (`enableSharding`, `shardCollection`, `getShardDistribution`): `skills/mongodb-expert/references/mongodb-sharding.md:785`
- `numInitialChunks` claim (unverified, see Pre-splitting note), 1 chunk per shard default, `unshardCollection`, direct-to-shard restriction: `skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md:163`, `:241`, `:235`, `:293`, `:306`
- Time series shard key rules: `skills/mongodb-expert/references/mongodb-time-series.md:525`
- Compound tenant-prefixed keys: `skills/mongodb-expert/references/mongodb-multi-tenancy.md:201`
- `createSupportingIndexes` and shard key remapping on migration: `skills/mongodb-operations-expert/references/mongodb-mongosync.md:495`
- Atlas CLI sharded cluster creation (`--type SHARDED`, `--shards`): `skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md:307`
- Command and tutorial index entries (`sh.shardCollection`, `sh.enableSharding`, `moveRange` ranges, Atlas shard-collection UI): `llms/mongodb.com.llms/llms-full.txt:4962`, `:4979`, `:5526`, `:5809`
