---
name: build-index-safely-in-production
title: Build an index safely on a live production cluster
summary: Design a compound index with the ESR rule, build it on a live replica set or Atlas cluster, watch progress, prove it with explain, then retire the redundant index by hiding it before dropping it.
applies_to: [atlas, self-managed]
sources:
  - skills/mongodb-expert/references/mongodb-indexes-deep.md
  - skills/mongodb-expert/references/mongodb-query-performance.md
  - skills/mongodb-expert/references/mongodb-wiredtiger-internals.md
  - skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md
  - skills/mongodb-operations-expert/references/mongodb-cost-optimization.md
  - skills/mongodb-operations-expert/references/database-migrations.md
  - skills/mongodb-expert/references/mongodb-compass.md
  - skills/atlas-diagnostics-expert/references/mongodb-monitoring-observability.md
---
# Build an index safely on a live production cluster

## When to use
- A hot query does a COLLSCAN or an in-memory sort and you need a new compound index on a collection that is taking traffic.
- You are replacing an older index with a better one and want to remove the old one without a blind drop.
- You need to decide between the default build and a rolling build.

## Prerequisites (checklist)
- [ ] You have the exact query shape: filter fields, sort fields, range fields, projection.
- [ ] You can run `explain("executionStats")` against production or a copy with realistic data.
- [ ] You know the server version (`db.version()`). Builds since 4.2 use the hybrid approach; hidden indexes need 4.4+.
- [ ] You checked free disk and WiredTiger cache headroom before starting.
- [ ] You know the current index count and sizes (`db.orders.getIndexes()`, `db.orders.stats().indexSizes`).
- [ ] For a unique index: you already proved there are no duplicates.
- [ ] Atlas only: a role that can create indexes and, if you use the API, an API key for the project.

## Steps

1. **Capture the baseline plan.** Save the "before" numbers so you can prove the gain.
   ```js
   db.orders.find({ status: "active", customerId: "abc123", price: { $gte: 50, $lte: 200 } })
     .sort({ createdAt: -1 })
     .explain("executionStats")
   ```
   Expect: `winningPlan` shows `COLLSCAN` (or a poor `IXSCAN`), and `totalDocsExamined` is far larger than `nReturned`. Write down `executionTimeMillis`, `totalKeysExamined`, `totalDocsExamined`, `nReturned`.

2. **Design the key with ESR (Equality, Sort, Range).** Put equality fields first, then sort fields (same direction as the sort), then range fields.
   ```js
   // Equality: status, customerId   Sort: createdAt desc   Range: price
   // Proposed index:
   { status: 1, customerId: 1, createdAt: -1, price: 1 }
   ```
   Expect: a key whose prefix matches your equality predicates. Treat `$in` with many values as a range field. For sorts on several fields, the index directions must match the sort or be the exact inverse of it.

3. **Check selectivity and redundancy before you build.**
   ```js
   const total = db.orders.countDocuments();
   const matching = db.orders.countDocuments({ status: "active" });
   matching / total
   db.orders.getIndexes()
   ```
   Expect: a low ratio (the corpus rule of thumb is an index helps when under roughly 20-30% of documents match). Note any existing index that is a prefix of the new key. That index becomes redundant after the build.

4. **Choose the build method.**
   - Default: the plain `createIndex` hybrid build. It takes an intent lock for the bulk phase, so reads and writes continue, with a brief exclusive lock at start and end. Progress replicates through the oplog.
   - Rolling build: use when the cluster is already stressed. The corpus says to consider it when CPU is very high or the WiredTiger cache is above about 90% full. It lowers load but reduces resiliency while it runs, because members are taken out one at a time.
   - Sharded clusters: Verify in the current MongoDB docs: the exact procedure and shard-key interaction for building indexes on a sharded collection.

5. **Build with the default method (replica set or Atlas).** Name the index so it is easy to hide and drop later.
   ```js
   db.orders.createIndex(
     { status: 1, customerId: 1, createdAt: -1, price: 1 },
     { name: "status_customerId_createdAt_price" }
   )
   ```
   Expect: the command returns after the index is built and committed. Do not pass `{ background: true }`; it is ignored since 4.2.

6. **(Optional) Build it hidden first** so the planner will not use it until you are ready.
   ```js
   db.orders.createIndex({ status: 1 }, { hidden: true })
   ```
   Expect: `db.orders.getIndexes()` shows `"hidden": true` for the new index. Use `db.orders.unhideIndex("<name>")` when you want it live.

7. **(Rolling build, self-managed) Follow the documented member-by-member procedure**, secondaries first, primary last. Do not use `rs.freeze` or `rs.remove`; the member is never removed from the replica set configuration.
   For each secondary, one at a time:
   1. Shut the member down cleanly (`db.shutdownServer()` from mongosh on that member).
   2. Restart it as a standalone on a different port, without the `--replSet` option (and without `replication.replSetName` in its config file), keeping the same data path.
   3. Connect to the standalone and build the index: `db.orders.createIndex({ status: 1, customerId: 1 })`.
   4. Shut the standalone down cleanly and restart it with its original port and replica set options so it rejoins the set.
   5. Wait until it is `SECONDARY` and caught up (`rs.status()`, replication lag near zero) before starting the next member.
   Then step down the primary (`rs.stepDown()`), wait for a new primary to be elected, and repeat steps 1-4 on the former primary.
   Oplog window warning: while a member is out of the set it falls behind. It must finish the index build and rejoin before the oplog window on the other members is exceeded; otherwise it can no longer catch up by replication and needs a full resync. Check the window with `rs.printReplicationInfo()` and size the oplog first if the build is long.
   Expect: each member rejoins and catches up before you move to the next. Confirm the exact steps in the current MongoDB docs before running them on production.

8. **(Rolling build, Atlas) Use the rolling-index option** in the Atlas UI (Index creation has a rolling-build toggle) or the Admin API.
   ```bash
   atlas api rollingIndex createRollingIndex \
     --projectId <project-id> --clusterName <cluster-name> \
     --key '{"field": "customerId", "type": "1"}'
   ```
   Expect: the build is queued per member. Verify in the current MongoDB docs: the full request body for a multi-field index and the current CLI syntax, since the corpus shows a single-field example only.

9. **Monitor build progress from a second shell.**
   ```js
   db.currentOp({ op: "command", "command.createIndexes": { $exists: true } })
   ```
   Expect: an entry with the `createIndexes` command and a `msg` progress string while the build runs. On a replica set, run it on each member to see secondary progress. To abort a build you started by mistake (4.4+), abort it through the primary, not by `killOp` on a secondary (not supported for index builds on secondaries):
   ```js
   db.orders.dropIndex("<index-name>")                     // on the primary
   db.adminCommand({ abortIndexBuild: ... })               // Verify in the current MongoDB docs: exact form of this command, if available in your version
   ```
   Verify in the current MongoDB docs: the supported ways to abort an in-progress index build in your version.
   While the build runs, also watch cache pressure: the corpus says builds hold uncommitted entries in the WiredTiger cache until commit, and `maxIndexBuildMemoryUsageMegabytes` (default 200 MB per build) throttles memory.

10. **Prove the plan changed.** Re-run the Step 1 explain.
    ```js
    db.orders.find({ status: "active", customerId: "abc123", price: { $gte: 50, $lte: 200 } })
      .sort({ createdAt: -1 })
      .explain("executionStats")
    ```
    Expect: `IXSCAN` on the new index, no separate `SORT` stage, `totalKeysExamined` and `totalDocsExamined` close to `nReturned`.

11. **If the planner picks a different index, test with hint, but do not keep the hint.**
    ```js
    db.orders.find({ status: "active" }).hint("status_customerId_createdAt_price").explain("executionStats")
    ```
    Expect: the hinted plan beats the other. Then fix the root cause (key order or a stale redundant index) rather than shipping `hint()`.

12. **Retire the redundant index: hide it first.**
    ```js
    db.orders.aggregate([{ $indexStats: {} }])      // run on each member; check accesses.ops
    db.orders.hideIndex("status_1")
    ```
    Expect: `getIndexes()` shows `"hidden": true`. The index is still maintained on writes, so the cost stays until you drop it.

13. **Watch for one full business cycle** (the corpus says 24-72 hours at minimum; the cost guide suggests one to two weeks and a 14-day `$indexStats` window to catch monthly jobs). Check p95 latency, slow-query logs and `$indexStats`.
    Expect: no regression and no `accesses.ops` increase on the hidden index name.

14. **Drop it.**
    ```js
    db.orders.dropIndex("status_1")
    ```
    Expect: the index is gone from `getIndexes()`, index size falls in `stats().indexSizes`.

## Verify
- `explain("executionStats")` shows `IXSCAN`, no in-memory `SORT`, and `nReturned / totalKeysExamined` close to 1.0.
- `db.orders.getIndexes()` lists the new index, visible (not hidden), with the intended name and key.
- `db.currentOp({ "command.createIndexes": { $exists: true } })` returns nothing on every member.
- On Atlas, Performance Advisor no longer suggests the index for this query shape.
- Write latency and cache dirty percentage are back at baseline.

## Rollback / abort
- Build in progress and unwanted: abort it via the primary (`dropIndex` / `dropIndexes` on the index name, or `abortIndexBuild` per the current docs); `killOp` on a secondary's index build is not supported in 4.4+. Verify in the current MongoDB docs.
- New index built but harmful: hide it (`db.orders.hideIndex("<name>")`), or drop it with `dropIndex`.
- Removed-index regression: `db.orders.unhideIndex("status_1")` restores it instantly with no rebuild. This only works if you hid it and have not yet dropped it.
- Rolling build gone wrong: rejoin the standalone member with `rs.add` and let it resync before touching the next member.

## Pitfalls
- Passing `{ background: true }` and thinking it changes anything. Since 4.2 it is ignored. (Some migration notes in the corpus still say to use it; trust the 4.2+ behavior.)
- Putting the range field before the sort field. The planner then needs an in-memory sort.
- Keeping the old prefix index "just in case". Duplicate and unused indexes cost write IOPS and cache.
- Hiding an index and assuming it is free. Hidden indexes still cost writes and storage, still count toward the index limit, and `_id` cannot be hidden.
- Reading `$indexStats` on one member only. Check every member; secondaries may serve different reads.
- Short observation windows. Monthly reports may be the only users of an index.
- Decreasing index count by guessing. Use `$indexStats` since the last restart, and remember the counters reset on restart.
- Treating `hint()` as the fix. The corpus says to redesign the index instead.
- Since 4.4 (not only 8.0): `commitQuorum` controls how many nodes must be ready to finish a build; the default is all voting data-bearing members. A lagging secondary can stall a build. Verify in the current MongoDB docs before lowering it.

## Sources
- skills/mongodb-expert/references/mongodb-indexes-deep.md:148 (ESR rule), :174 (prefix matching), :189 (sort direction)
- skills/mongodb-expert/references/mongodb-indexes-deep.md:640 (4.2+ hybrid build, `background` ignored, currentOp, killOp)
- skills/mongodb-expert/references/mongodb-indexes-deep.md:667 and :689 (rolling builds, manual steps, resiliency trade-off, Atlas rolling example)
- skills/mongodb-expert/references/mongodb-indexes-deep.md:701 (selectivity), :740 (reading explain)
- skills/mongodb-expert/references/mongodb-indexes-deep.md:767-800 (hidden indexes, safe-removal workflow, constraints)
- skills/mongodb-expert/references/mongodb-indexes-deep.md:844-870 (anti-patterns, unused indexes)
- skills/mongodb-expert/references/mongodb-wiredtiger-internals.md:873 (index builds inflate cache, `maxIndexBuildMemoryUsageMegabytes`)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:326 (8.0 commit quorum)
- skills/mongodb-operations-expert/references/mongodb-cost-optimization.md:341-358 (14-day `$indexStats` window, hide then drop)
- skills/mongodb-operations-expert/references/database-migrations.md:767 (unique index duplicate check, monitoring)
- skills/mongodb-expert/references/mongodb-query-performance.md:274 (`$indexStats` decision rule), :289 (hint caveats)
- skills/atlas-diagnostics-expert/references/mongodb-monitoring-observability.md:223 (`$currentOp` `msg` field shows progress for index builds)
