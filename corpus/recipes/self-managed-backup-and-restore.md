---
name: self-managed-backup-and-restore
title: Back up and restore a self-managed MongoDB deployment
summary: Choose between mongodump/mongorestore, filesystem snapshots and Ops Manager or Cloud Manager backup, take a consistent backup of a replica set or sharded cluster, and prove it restores.
applies_to: [self-managed]
sources:
  - skills/mongodb-expert/references/mongodb-database-tools.md
  - skills/mongodb-operations-expert/references/mongodb-backup-restore.md
  - skills/mongodb-operations-expert/references/mongodb-ops-manager.md
  - llms/mongodb.com.llms/llms-full.txt
  - llms/mongodb.com.llms/llms-facts.txt
---
# Back up and restore a self-managed MongoDB deployment

## When to use
- You run `mongod` yourself (VMs, bare metal, containers) and need a backup you can actually restore.
- You must pick a method: logical dump (`mongodump`), storage-level snapshot, or a managed backup system (Ops Manager / Cloud Manager).
- You need a restore runbook for a replica set, or you need to know why a sharded-cluster backup is harder.

## Prerequisites (checklist)
- [ ] You know the topology: standalone, replica set, or sharded cluster. `--oplog` works only against replica sets, not standalones.
- [ ] Database Tools installed (`mongodump`, `mongorestore`). They ship as a separate `mongodb-database-tools` package with `100.x` versions and are not bundled with `mongosh`. Use the same tools version for dump and restore.
- [ ] A user with the `backup` role for dumping and the `restore` role for restoring. `--oplogReplay` needs a custom role with `anyAction` on `anyResource`.
- [ ] A secondary to read from (to protect primary I/O) and enough free disk and bandwidth for the output.
- [ ] A scratch host or cluster to rehearse the restore. A backup that has never been restored is an assumption.

## Steps
1. Pick the method with this table.
   ```text
   Replica set, up to a few hundred GB, downtime-tolerant restore -> mongodump --oplog
   Large deployment or tight restore time (RTO < 1 hour)          -> filesystem (block) snapshots
   Sharded cluster                                                 -> Ops Manager / Cloud Manager, or filesystem snapshots with the documented lock procedure
   Need point-in-time to an arbitrary second                       -> Ops Manager / Cloud Manager continuous backup
   Single collection / staging refresh / data portability          -> mongodump + mongorestore
   ```
   Expect: one method chosen. The corpus says `mongodump` is a poor fit for large production clusters because it reads all data and evicts the working set from the WiredTiger cache.

2a. Logical backup of a replica set (consistent via the oplog).
   ```bash
   mongodump \
     --uri="mongodb://<user>:<password>@<host1>:27017,<host2>:27017/?replicaSet=<rs-name>&authSource=admin" \
     --readPreference=secondary \
     --oplog --gzip --out=/backup/$(date +%Y%m%d)
   ```
   Expect: one directory per database with `.bson.gz` and `.metadata.json.gz` files, plus `oplog.bson` at the root. `--oplog` captures writes that happen during the dump so the restore can reach the state at dump completion. It cannot be combined with `--db`, `--collection` or `--query`, and it fails if a resharding operation is in progress.

2b. Logical backup to a single compressed archive (portable, can be streamed).
   ```bash
   mongodump --uri="<connection-string>" --readPreference=secondary --oplog --archive --gzip > /backup/mydb-$(date +%Y%m%d).archive.gz
   ```
   Expect: a single opaque archive file. Dump size is uncompressed data regardless of storage compression; `--gzip` only compresses output.

3. (Alternative) Filesystem snapshot of a replica set member.
   ```javascript
   // mongosh, on the member you will snapshot (prefer a secondary)
   db.fsyncLock()
   // ... take the volume / LVM snapshot with your storage tooling ...
   db.fsyncUnlock()
   ```
   Expect: `fsyncLock()` flushes pending writes to disk and blocks further writes until `fsyncUnlock()`. Always unlock, and confirm the snapshot completed before unlocking. Verify in the current MongoDB docs: the journal and data-file layout requirements for a consistent snapshot on your storage engine and volume setup.

4. (Sharded cluster) Back up with the documented procedure, never with a bare per-shard dump.
   ```text
   Stop the balancer, pause DDL, then back up config server metadata and every shard
   (either mongodump with the cluster locked, or filesystem snapshots with writes stopped / cluster locked).
   ```
   Expect: a backup set from one consistent moment. The corpus warns that `mongodump` on a sharded cluster does not guarantee cross-shard transaction consistency, and recommends Ops Manager / Cloud Manager (or Atlas Cloud Backup) for sharded backups. Verify in the current MongoDB docs: the exact lock/stop sequence in "Back Up a Self-Managed Sharded Cluster with a Database Dump" and "... with File System Snapshots".

5. (Alternative) Ops Manager / Cloud Manager continuous backup.
   ```text
   Ops Manager UI -> project -> Backup -> start backup for the deployment
   Set Sync Source to a designated secondary
   Choose snapshot store: blockstore, S3 blockstore, or filesystem store
   ```
   Expect: the agent tails the oplog from the secondary into the Backup Daemon's head database, and scheduled snapshots (the corpus says typically every 6 hours) land in the snapshot store. Oplogs are kept in an oplog store for point-in-time restore. Do not back up from the primary.

6. Copy the backup off the host and record what you took.
   ```bash
   aws s3 cp /backup/<date> s3://<bucket>/<path>/ --recursive
   ```
   Expect: the artifact exists outside the failure domain of the source servers. Record date, method, tools version, topology and shard count.

7. Restore from a logical dump into a rehearsal replica set.
   ```bash
   mongorestore \
     --uri="mongodb://<user>:<password>@<restore-host>:27017/?authSource=admin" \
     --oplogReplay --drop --gzip /backup/<date>
   ```
   Expect: collections are restored with inserts only (existing `_id`s are skipped unless `--drop` is used), indexes are rebuilt after the data load, and the oplog is replayed so the data matches the moment the dump finished. Use `--preserveUUID` together with `--drop` if change streams consumers depend on collection UUIDs.

8. Restore a single namespace instead of everything.
   ```bash
   mongorestore --uri="<restore-uri>" --nsInclude="mydb.orders" --drop /backup/<date>
   ```
   Expect: only `mydb.orders` is restored. Use `--nsFrom`/`--nsTo` to restore under a different name.

9. Restore from filesystem snapshots or Ops Manager.
   ```text
   Filesystem: stop mongod, replace the data directory from the snapshot volume, start mongod, then rejoin / reseed the replica set.
   Ops Manager: Backup -> select snapshot or a point in time -> Restore -> choose target host or download.
   ```
   Expect: Ops Manager picks the newest snapshot before the target time, streams it to the target through the Backup Restore Utility, then replays oplog entries from the oplog store up to the exact time. Restore time depends on the oplog volume between the snapshot and the target. Verify in the current MongoDB docs: the restore tutorials listed under Sources for your server version and feature compatibility version.

## Verify
```javascript
// mongosh against the restored deployment
db.getSiblingDB('app').orders.countDocuments()
db.getSiblingDB('app').orders.getIndexes()
db.getSiblingDB('app').orders.validate({ full: true })
rs.status()   // replica set healthy after reseeding
```
Expect: document counts and index lists match the source at backup time, `validate` is clean, and every member reaches PRIMARY or SECONDARY. Run an application smoke test against the restored copy. Time the whole restore: that is your real recovery time. Repeat on a schedule (weekly scripted restore to staging, quarterly tabletop is the cadence the corpus suggests).

## Rollback / abort
- Restore into a separate host or cluster first so production stays untouched. `mongorestore --drop` deletes the target collections before restoring, so never point it at production by habit.
- If `fsyncLock()` was run, always run `db.fsyncUnlock()` on abort. A locked member blocks writes.
- If a restore goes wrong, discard the rehearsal target and redo it. Keep the previous backup until the new restore is verified.

## Pitfalls
- Using `mongodump` without `--oplog` on a busy replica set. The dump is not point-in-time consistent.
- Expecting `--oplogReplay` to give arbitrary point-in-time recovery. It brings data to the moment the dump completed, not to a chosen timestamp. Arbitrary-time recovery on self-managed needs Ops Manager / Cloud Manager continuous backup. Verify in the current MongoDB docs: any `mongorestore` option for limiting oplog replay to a chosen time.
- Dumping a sharded cluster per shard and calling it a backup. Cross-shard consistency is not guaranteed, and restoring a sharded cluster requires the same number of shards on source and target.
- Backing up from the primary. It competes with application I/O and cache; read from a secondary (`--readPreference=secondary`, or Ops Manager Sync Source).
- Restoring without `--preserveUUID` when change streams are in use. New UUIDs break active change stream cursors and resume tokens.
- Treating `mongoexport` as a backup. Extended JSON loses BSON type fidelity; use `mongodump`.
- Mixing dump and restore tool versions.
- On case-insensitive file systems, collections that differ only by case overwrite each other in a dump directory. Use `--archive`.
- Never testing the restore, never monitoring backup success (agent stops, snapshots fail silently), or keeping all copies in the same region or rack.
- Ops Manager capacity: a full blockstore or Daemon disk causes backup failures across many deployments at once. Watch for "No daemon has space to bind". If the "Backup Oplog Is Behind" alert fires, check the agent, resize the oplog if undersized, and Resync if the gap is too large.

## Sources
- `skills/mongodb-expert/references/mongodb-database-tools.md:118-169` mongodump options, `--oplog` constraints, dump layout, behavior notes.
- `skills/mongodb-expert/references/mongodb-database-tools.md:206-283` mongorestore options, `--drop`, `--oplogReplay`, `--preserveUUID`, required roles.
- `skills/mongodb-expert/references/mongodb-database-tools.md:761-801` method decision guide and the sharded-cluster consistency warning.
- `skills/mongodb-expert/references/mongodb-database-tools.md:805-819` package separation and same-version rule.
- `skills/mongodb-operations-expert/references/mongodb-ops-manager.md:366-405` continuous backup flow, point-in-time mechanics, backup from a secondary.
- `skills/mongodb-operations-expert/references/mongodb-ops-manager.md:903-921` Daemon disk pressure and oplog-behind failure modes.
- `skills/mongodb-operations-expert/references/mongodb-backup-restore.md:173-219` Ops Manager components and snapshot store types.
- `skills/mongodb-operations-expert/references/mongodb-backup-restore.md:429-443` backup anti-patterns.
- `llms/mongodb.com.llms/llms-full.txt:5482-5486` and `:5627-5628` index of the manual tutorials for dump, filesystem-snapshot and sharded backup and restore.
- `llms/mongodb.com.llms/llms-full.txt:4879` `db.fsyncLock()`; `llms/mongodb.com.llms/llms-facts.txt:1516` sharded restore shard-count rule.
