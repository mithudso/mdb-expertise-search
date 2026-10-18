---
name: reshard-a-collection
title: Reshard a collection to change its shard key
summary: Change the shard key of a live sharded collection with reshardCollection, monitor it with $currentOp, and commit or abort it safely.
applies_to: [atlas, self-managed]
sources:
  - skills/mongodb-expert/references/mongodb-sharding.md
  - skills/mongodb-operations-expert/references/mongodb-migration-patterns.md
  - skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md
  - skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md
  - skills/mongodb-expert/references/mongodb-time-series.md
  - llms/mongodb.com.llms/llms-full.txt
---
# Reshard a collection to change its shard key

## When to use
- The current shard key causes hot shards, jumbo chunks, or scatter-gather on your main queries, and adding suffix fields is not enough.
- You want to move to a hashed key, a different field, or a different compound key.
- MongoDB 8.0+: you added shards or zones and want data redistributed faster than the balancer would do it, without changing the key (same-key resharding).
- Try the lighter option first: `refineCollectionShardKey` (4.4+) appends suffix fields to the existing key with no data movement and raises cardinality. Reshard only if refining cannot fix the problem.

## Prerequisites (checklist)
- [ ] Connected through `mongos` as a user allowed to run sharding admin commands.
- [ ] MongoDB 5.0+ for `reshardCollection`. The corpus is inconsistent on the minimum version (5.0 in the sharding reference, 6.0+ in the migration-patterns reference). Verify in the current MongoDB docs: the minimum version for your release series.
- [ ] New key chosen and analyzed (`analyzeShardKey`, 7.0+). See the recipe `shard-a-collection`, steps 1 and 2.
- [ ] Free disk on each shard of at least `((collection_size + index_size) * 2) / shard_count` (corpus formula).
- [ ] I/O utilization below 50% and CPU load below 80% on the shards.
- [ ] No other resharding operation running (one per cluster at a time).
- [ ] Oplog sized for the duration of the operation (the corpus readiness checklist calls this out).
- [ ] No shard is being added or removed during the run (8.0+ makes add/remove wait for in-flight DDL such as `reshardCollection`).
- [ ] The application can tolerate a short write block at commit (the corpus says approximately 2 seconds in one place and "sub-second" in another).
- [ ] A recent backup or snapshot exists.
- [ ] Time series collection? It needs 8.0.10+ and the key must follow the time series shard key rules.

## Steps

### 1. Record the starting state
```javascript
sh.status()
db.orders.getShardDistribution()
use config
db.chunks.find({ jumbo: true })
```
Expect: the current shard key, per-shard data size, and any jumbo chunks. Save the output so you can compare after the change.

### 2. Check capacity numbers
```javascript
use mydb
db.orders.stats()      // size and totalIndexSize
```
Expect: compute `((size + totalIndexSize) * 2) / shard_count` and compare it with free disk per shard. If it does not fit, stop and add disk or shards first.

### 3. Create the supporting index for the new key (if your version needs it)
```javascript
db.orders.createIndex({ customerId: "hashed" })
```
Expect: `ok: 1`. The corpus says the 8.0 resharding path builds the required indexes on the recipient shard after cloning, so this step may be unnecessary on 8.0+.

Verify in the current MongoDB docs: whether you must pre-create the index for the new key on your version.

### 4. Decide on the balancer
The corpus lists "disable the balancer" as a requirement.
```javascript
sh.stopBalancer()
sh.getBalancerState()
```
Expect: `sh.getBalancerState()` returns `false`.

Verify in the current MongoDB docs: whether disabling the balancer is still required on your version. If you stop it, re-enable it in step 8.

### 5. Start the resharding operation
Change the key:
```javascript
db.adminCommand({
  reshardCollection: "mydb.orders",
  key: { customerId: "hashed" }
})
```
With the optional settings seen in the corpus:
```javascript
db.adminCommand({
  reshardCollection: "mydb.orders",
  key: { customerId: "hashed" },
  numInitialChunks: 90,
  collation: { locale: "simple" }
})
```
Same-key redistribution (MongoDB 8.0+):
```javascript
db.adminCommand({
  reshardCollection: "mydb.orders",
  key: { customerId: 1 },
  forceRedistribution: true
})
```
Expect: the command blocks while the operation runs, so run it in a session you can leave open and monitor from a second session (step 6). Resharding has three phases: clone (recipient shards copy data from donors), catch-up (recipients apply writes from donors via the oplog), commit (atomic cut-over to the new key). The corpus gives a minimum duration of 5 minutes for any resharding operation.

The 8.0 notes in the corpus say resharding reads source data in natural order, clones everything first, and builds indexes afterwards, described as an "orders of magnitude" speedup over earlier versions. The migration-patterns reference quotes roughly 1 GB per second on Atlas M60+ clusters; treat that as a best case.

Verify in the current MongoDB docs: the full option list for `reshardCollection` (for example zones and shard distribution) before you use any option not shown above.

### 6. Monitor with $currentOp
From a second mongosh session:
```javascript
db.getSiblingDB("admin").aggregate([
  { $currentOp: { allUsers: true, localOps: false } },
  { $match: { type: "op", "originatingCommand.reshardCollection": "mydb.orders" } }
])
```
Expect: one document per participant with progress fields. The migration-patterns reference names `remainingOperationTimeEstimatedSecs`, `approxBytesToCopy` and `bytesCopied` as the fields to watch. A second view: `db.adminCommand({ currentOp: true, $all: true, desc: /moveRange|moveChunk|reshardCollection/ })`.

Re-run every few minutes. `bytesCopied` should climb toward `approxBytesToCopy` and the remaining-time estimate should fall.

### 7. Commit, or abort
Normally the operation commits by itself when it has caught up. The mongosh helper index in the corpus lists `sh.commitReshardCollection()` to force completion by blocking writes early, and `sh.abortReshardCollection()` to abort before the commit phase.
```javascript
// Force the commit early (blocks writes on the collection until done)
sh.commitReshardCollection("mydb.orders")

// Abort before commit
db.adminCommand({ abortReshardCollection: "mydb.orders" })
```
Expect: on commit, the original `reshardCollection` call returns `ok: 1`. On abort, the original call fails with an abort error and the collection keeps its old shard key.

Verify in the current MongoDB docs: the exact argument form of `sh.commitReshardCollection()`. The corpus shows only the `abortReshardCollection` admin command form with a namespace string.

### 8. Restore normal operation
```javascript
sh.startBalancer()
sh.getBalancerState()
```
Expect: `true`. Skip this step if you did not stop the balancer.

## Verify
```javascript
sh.status()                              // collection now shows the new shard key
db.orders.getShardDistribution()         // compare with step 1
sh.balancerCollectionStatus("mydb.orders")
use config
db.chunks.find({ jumbo: true })          // expect none, or fewer than before
```
Expect:
- The new shard key appears in `sh.status()`.
- Data spreads evenly across shards.
- The `$currentOp` query from step 6 returns no resharding documents.
- Run your top application queries with `explain("executionStats")` and confirm they are targeted when the new key matches their filters.
- Change streams on the collection receive a `reshardCollection` event (the corpus change-event index lists it).

## Rollback / abort
- Before commit: `abortReshardCollection` (step 7). The old key stays in place.
- After commit: there is no undo. To go back, run a second `reshardCollection` with the old key and plan for the same disk and time cost.
- If you stopped the balancer: re-enable it (step 8) in every outcome.
- If the run is hurting production (I/O or CPU high): abort first, fix capacity, then retry in a quieter window.

## Pitfalls
- Starting with too little disk. The operation temporarily holds a second copy of data and indexes, which is why the corpus uses a 2x formula.
- Running while I/O is above 50% or CPU above 80%: the catch-up phase falls behind and the commit stalls.
- Starting a second resharding run: only one resharding operation per cluster is allowed at a time.
- Adding or removing a shard mid-run: on 8.0+ the topology change waits for the DDL operation; on earlier versions it can race it. Schedule topology changes before or after.
- Forgetting to re-enable the balancer.
- Skipping the lighter option: if a jumbo chunk is the only problem, `refineCollectionShardKey` or a split (`sh.splitAt()`) may be enough.
- Choosing another monotonic key. Re-run key analysis before you start; a bad new key means another reshard.
- Assuming a time series collection can be resharded on any version: the feature matrix lists 8.0.10+, and `timeField` as a shard key component is deprecated in 8.0.
- Treating the commit block as zero: the application sees a brief write pause. Use retryable writes and sensible driver timeouts.
- Resharding during a migration: the corpus says to reshard on the destination after mongosync commits, not during the sync.

## Sources
- Phases, requirements, monitoring, abort: `skills/mongodb-expert/references/mongodb-sharding.md:576`
- refineCollectionShardKey as the lighter option: `skills/mongodb-expert/references/mongodb-sharding.md:615`
- shardAndDistributeCollection and reshard to same key (`forceRedistribution`): `skills/mongodb-expert/references/mongodb-sharding.md:628`, `:638`
- currentOp filter for `reshardCollection`: `skills/mongodb-expert/references/mongodb-sharding.md:698`
- Oplog and disk headroom in the readiness checklist: `skills/mongodb-expert/references/mongodb-sharding.md:775`
- Feature matrix (5.0 reshard, 8.0 same-key, time series 8.0.10+): `skills/mongodb-expert/references/mongodb-sharding.md:822`
- `numInitialChunks` and `collation` options, `currentOp` resharding fields, throughput note, reshard after mongosync: `skills/mongodb-operations-expert/references/mongodb-migration-patterns.md:645`
- 8.0 resharding speedups, same-key resharding, DDL ordering with topology changes: `skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md:214`
- Time series resharding gated by FCV and version: `skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:169`
- Time series shard key rules, `timeField` deprecation: `skills/mongodb-expert/references/mongodb-time-series.md:525`
- Helper and tutorial index (`sh.abortReshardCollection`, `sh.commitReshardCollection`, `sh.reshardCollection`, "Reshard a Collection back to the Same Shard Key", change-event entry): `llms/mongodb.com.llms/llms-full.txt:4454`, `:4594`, `:4945`, `:4953`, `:4976`, `:5624`
