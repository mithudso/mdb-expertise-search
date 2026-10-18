---
name: migrate-with-mongosync
title: Migrate between MongoDB clusters with mongosync
summary: Prepare two clusters, start a mongosync session, monitor initial copy and change application, cut over with commit, verify, and keep reverse sync available for rollback.
applies_to: [atlas, self-managed]
sources:
  - skills/mongodb-operations-expert/references/mongodb-mongosync.md
  - skills/mongodb-operations-expert/references/mongosync.md
  - skills/mongodb-operations-expert/references/mongodb-ops-manager.md
  - skills/mongodb-operations-expert/references/mongodb-migration-patterns.md
---
# Migrate between MongoDB clusters with mongosync

## When to use
- You need continuous cluster-to-cluster replication with a cutover measured in seconds to a minute (replica set to replica set, sharded to sharded, and the replica set to sharded cases the corpus lists).
- You need a filtered sync (include/exclude namespaces), private networking, a pause/resume capability, or a reverse-sync rollback path. These are reasons to prefer standalone mongosync over Atlas Live Migration.
- Per the corpus, Atlas Live Migration (pull) suits smaller sources (up to 5 TB and 3 shards) into Atlas over the public network, with no filtering. Both are built on the same mongosync engine.
- Do NOT use it as a permanent DR secondary or when the goal is a point-in-time backup. See the backup and restore recipes for that.

## Prerequisites (checklist)
- [ ] Source and destination run MongoDB versions supported by your mongosync release. Verify in the current MongoDB docs: the version matrix for your mongosync release; the corpus has the two sources disagreeing on whether both clusters must share a major version.
- [ ] A dedicated migration host with at least 8 CPUs and 24 GB RAM, in the same region/VPC as the clusters, with network reach to both. Run mongosync under a process supervisor, because it does not restart itself after a crash.
- [ ] Connection strings that use `readConcern=majority` and `w=majority`, read preference `primary`, and TLS. Keep credentials in a config file, not on the command line.
- [ ] Source oplog window of at least 2 to 3 times the expected initial-copy duration plus any planned pause. Check and resize before starting (Step 1).
- [ ] Destination sized at or above the source for CPU, memory and IOPS; plan for disk of about 2 times the source data size plus a buffer.
- [ ] Users, roles and `admin` database objects recreated on the destination. mongosync does not replicate them.
- [ ] Balancer stopped on a sharded destination (versions before 1.17 do not do it for you) and no `moveChunk`, `moveRange` or `movePrimary` planned on either cluster during the sync. Zone ranges removed from destination namespaces.
- [ ] If you want rollback: you will start with `reversible: true`, both clusters on the same topology and shard count, and no filters.
- [ ] Nobody writes to the destination namespaces while the sync runs.
- [ ] Lowered DNS TTLs and the list of every application connection string.

## Steps
1. Size the source oplog window.
   ```javascript
   // mongosh on the source (each shard: use the smallest)
   db.getReplicationInfo()
   // set a minimum retention window (hours) at runtime, per replica set member
   db.adminCommand({ replSetResizeOplog: 1, minRetentionHours: 48 })
   // or resize explicitly (size in MB)
   db.adminCommand({ replSetResizeOplog: 1, size: 51200 })
   // alternatively set the storage.oplogMinRetentionHours config file option and restart
   ```
   `oplogMinRetentionHours` is not a runtime `setParameter`. On Atlas, check oplog size and retention through the cluster settings (and the Atlas UI/API oplog settings) rather than running these commands directly.
   Expect: the window shown is larger than 2 to 3 times the expected copy time. The corpus rule of thumb: copy time = data size / throughput (20 to 100 GB/hour is typical); if throughput is unknown, start with a 48-hour window. On Atlas the setting is Cluster, then Additional Settings, then Minimum Oplog Window.

2. Write the mongosync config file.
   ```yaml
   # /etc/mongosync.conf
   cluster0: "mongodb+srv://<migrator>:<password>@<source-host>/?authSource=admin&readConcern=majority&w=majority"
   cluster1: "mongodb+srv://<migrator>:<password>@<destination-host>/?authSource=admin&readConcern=majority&w=majority"
   logPath: /var/log/mongosync
   loadLevel: 3
   verbosity: INFO
   port: 27182
   ```
   Expect: a file readable only by the service user. Verify in the current MongoDB docs: the exact key layout (one source shows plain URI strings, another shows nested `connectionString` keys) and the log setting names for your mongosync release.

3. Start the process under a supervisor.
   ```bash
   systemctl enable mongosync && systemctl start mongosync
   curl -s localhost:27182/api/v1/progress
   ```
   Expect: the HTTP API on `127.0.0.1:27182` returns state `IDLE`. The API has no authentication; keep it bound to localhost.

4. Start the sync with rollback enabled.
   ```bash
   curl localhost:27182/api/v1/start -XPOST --data '{
     "source": "cluster0",
     "destination": "cluster1",
     "reversible": true,
     "enableUserWriteBlocking": true
   }'
   ```
   Expect: state moves to `RUNNING` with info `collection copy`. `reversible` must be set now; it cannot be turned on later. Add `includeNamespaces` or `excludeNamespaces` only if you need a filtered sync, and know that filters cannot be changed on a running sync and that reverse sync is not supported after a filtered sync. Verify in the current MongoDB docs: the default and requirements of `enableUserWriteBlocking` for your release, because the two corpus sources describe it differently.

5. Monitor the copy phase.
   ```bash
   curl -s localhost:27182/api/v1/progress | jq '.progress | {state, info, collectionCopy, lagTimeSeconds, estimatedOplogTimeRemaining}'
   ```
   Expect: `collectionCopy.estimatedCopiedBytes` keeps rising. During copy, `lagTimeSeconds` grows as events buffer; that is normal. If `estimatedOplogTimeRemaining` drops below about 1 to 2 hours, act (resize the oplog, scale the migration host, or reduce source write load).

6. Monitor change event application until caught up.
   ```bash
   watch -n5 'curl -s localhost:27182/api/v1/progress | jq ".progress | {state, canCommit, lagTimeSeconds, estimatedSecondsToCEACatchup, estimatedOplogTimeRemaining}"'
   ```
   Expect: info becomes `change event application`, `lagTimeSeconds` settles at 0 to 5 seconds across several polls, and `canCommit` is `true`. With the embedded verifier on, both verification phases should read `stream hashing` with near-zero lag. The destination keeps indexes temporarily modified (unique indexes non-unique, TTL set to a maximum) until commit.

7. Verify the data before cutover (choose by cluster shape).
   ```text
   Replica set, light mutation   -> embedded verifier (default)
   Sharded or heavy mutation     -> mongodb-labs/migration-verifier (can run while mongosync runs)
   Cryptographic proof needed    -> dbHash (locks the cluster, not available on sharded clusters)
   Insert-only data              -> document counts
   ```
   Expect: no differences reported. Rehearse the application against the destination in a staging copy if you can.

8. Cutover: fence application writes on the source.
   ```text
   Stop or fence every writer to the source (or deploy a read-only config). Confirm with db.currentOp() on the source that no writes arrive.
   ```
   Expect: source write traffic reaches zero.

9. Wait for zero lag, then commit.
   ```bash
   until [ "$(curl -s localhost:27182/api/v1/progress | jq '.progress.canCommit')" = "true" ] && [ "$(curl -s localhost:27182/api/v1/progress | jq '.progress.lagTimeSeconds')" = "0" ]; do sleep 2; done
   curl localhost:27182/api/v1/commit -XPOST --data '{}'
   ```
   Expect: state moves to `COMMITTING`, then automatically to `COMMITTED`. For sharded clusters call commit on the coordinator instance; all shard instances commit together. The corpus says healthy cutovers finish in under 60 seconds.

10. Wait for the destination to accept writes, then switch applications.
    ```bash
    until [ "$(curl -s localhost:27182/api/v1/progress | jq '.progress.canWrite')" = "true" ]; do sleep 2; done
    ```
    Expect: `canWrite: true`, which appears before `COMMITTED`. Update connection strings (or DNS alias) to the destination and restart applications. Unique-index restoration and TTL restoration finish asynchronously, so write latency can rise briefly.

11. Wait for `COMMITTED` and keep mongosync running for the rollback window.
    ```bash
    until [ "$(curl -s localhost:27182/api/v1/progress | jq -r '.progress.state')" = "COMMITTED" ]; do sleep 5; done
    ```
    Expect: `COMMITTED`. Do not drop the `__mdb_internal_mongosync` and `__mdb_internal_mongosync_verifier*` databases yet; dropping them makes reverse sync impossible.

## Verify
```javascript
// mongosh, destination (compare with counts captured on the source before the fence)
db.getSiblingDB('app').orders.countDocuments()
db.getSiblingDB('app').orders.getIndexes()
db.getSiblingDB('app').orders.find({ updatedAt: { $gte: new Date(Date.now() - 3600000) } }).limit(10)
```
Expect: counts and indexes match the source; recent updates are present; application error rate and latency are within baseline. Do not judge in the first 2 to 5 minutes: connection pool reconvergence, a cold WiredTiger cache and DNS propagation are normal and are not rollback triggers.

## Rollback / abort
- Before commit: `POST /api/v1/pause` to hold, or stop mongosync and discard the destination data. Nothing was cut over, so the source is still authoritative. Remember a long pause consumes source oplog window.
- After commit, while the destination oplog has not rolled past the `canWrite: true` moment:
  ```bash
  curl localhost:27182/api/v1/reverse -XPOST --data '{}'
  ```
  Expect: state `REVERSING`, then `RUNNING` in the opposite direction, replaying post-cutover writes from the new source back to the original. Repeat the fence-and-commit cutover procedure back to the original cluster.
- Rollback triggers the corpus suggests: error rate above 5%, a critical query returning wrong results, a failed data-integrity check, or performance more than 3 times worse than the source baseline.
- Reverse needs: `reversible: true` at start, same topology and shard count, no filtered sync, and (per the corpus) the same major version on both sides.
- Unrecoverable sync failure (such as `ChangeStreamHistoryLost`): drop all migrated user databases on the destination plus the mongosync metadata databases, fix the cause (usually oplog size), and start over.

## Pitfalls
- Oplog window too small. A 36-hour migration with a 24-hour window ends with a lost change stream and a restart from zero. Size it first; alert at less than 2 hours remaining.
- Forgetting `reversible: true` at start. It cannot be added later, and filtered syncs cannot be reversed.
- Writing to the destination during the sync, or running `movePrimary`/`moveChunk`/`moveRange`, which corrupt the migration state.
- Leaving the balancer on for sharded destinations (before 1.17) or leaving zone ranges on destination namespaces.
- Expecting users and roles to migrate. They do not.
- Dropping the mongosync metadata databases too early, which removes the rollback option.
- Treating `E11000 duplicate key` log lines as fatal. The corpus calls them normal during copy and after resume; only fatal errors matter.
- Changing `loadLevel` mid-sync by re-calling start. Pause, stop, edit the config, restart, then resume. `resume` can take at least 2 minutes to return to RUNNING.
- Inconsistent indexes across shards on the source (reported as fatal from v1.14), or rolling index builds on the source during the sync.
- Choosing `dbHash` verification without realizing it locks the cluster and is unavailable on sharded clusters.
- Using public-network Atlas Live Migration when you need private link or VPC peering. Use standalone mongosync there.
- Underpowered migration host or high network latency: the cause of most "stalled lag" reports along with destination IOPS and index-build contention.

## Sources
- `skills/mongodb-operations-expert/references/mongodb-mongosync.md:17-45` when to choose mongosync versus Atlas Live Migration, and what mongosync cannot do.
- `skills/mongodb-operations-expert/references/mongodb-mongosync.md:58-147` host model, REST API port, connection settings, supervisor, `loadLevel`, embedded verifier.
- `skills/mongodb-operations-expert/references/mongodb-mongosync.md:165-236` copy phase, change event application, commit sequence, `canWrite` timing, state table.
- `skills/mongodb-operations-expert/references/mongodb-mongosync.md:296-366` `/start` parameters and the pause, resume, commit and reverse calls.
- `skills/mongodb-operations-expert/references/mongodb-mongosync.md:370-440` reverse sync requirements and limits.
- `skills/mongodb-operations-expert/references/mongodb-mongosync.md:535-612` lag monitoring and oplog window sizing.
- `skills/mongodb-operations-expert/references/mongodb-mongosync.md:678-803` failure modes and the clean-restart procedure.
- `skills/mongodb-operations-expert/references/mongodb-mongosync.md:869-1052` balancer handling, cutover checklist, rollback decision criteria.
- `skills/mongodb-operations-expert/references/mongosync.md:303-338` four verification methods and decision tree.
- `skills/mongodb-operations-expert/references/mongosync.md:389-406` mongosync versus Atlas Live Migration versus Cluster-to-Cluster Sync.
- `skills/mongodb-operations-expert/references/mongodb-ops-manager.md:714-724` the source oplog window as the main migration risk.
- `skills/mongodb-operations-expert/references/mongodb-migration-patterns.md:529-545` oplog retention commands.
