---
name: restore-atlas-snapshot-or-pitr
title: Restore an Atlas cluster from a cloud backup snapshot or point in time
summary: Pick the right restore mode (automated, point-in-time, download), restore into a new cluster first, validate the data, then swap the application over.
applies_to: [atlas]
sources:
  - skills/mongodb-operations-expert/references/mongodb-backup-restore.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md
  - skills/mongodb-operations-expert/references/mongodb-disaster-recovery.md
  - llms/mongodb.com.llms/llms-full.txt
  - llms/mongodb.com.llms/llms-facts.txt
---
# Restore an Atlas cluster from a cloud backup snapshot or point in time

## When to use
- A bad migration, bad deploy, accidental `dropDatabase()` or mass delete reached production and replication copied it everywhere.
- You need yesterday's (or last week's) dataset in a sandbox cluster.
- You need raw data files for off-platform forensics or an on-prem copy (download mode).
- You only need to look at old data. In that case use a Queryable Backup instead of a restore (Step 2).

## Prerequisites (checklist)
- [ ] Dedicated cluster (M10 or larger) with Cloud Backup enabled. Flex clusters take daily snapshots only, so no point-in-time restore, and only automated restore is available through the CLI.
- [ ] For point-in-time: Continuous Cloud Backup is enabled and the target time is inside the configured `restoreWindowDays` window.
- [ ] Project Owner role (the Atlas CLI reference lists this for restore jobs).
- [ ] A target cluster exists (preferably a NEW cluster of equal or larger size). The target's data is deleted before the restore.
- [ ] The incident time is known as precisely as possible. If it is not, bisect it with Queryable Backups first.
- [ ] A named decision authority has approved any restore that overwrites live state.
- [ ] Atlas CLI installed and authenticated, with `<project-id>` and `<cluster-name>` known.

## Steps
1. Stop the damage and record the incident time.
   ```text
   Pause the bad job / deploy / writer. Note the UTC time of the first bad write.
   ```
   Expect: a UTC timestamp you can convert to Unix seconds, and no new bad writes arriving.

2. (Optional) Find the last clean state with a Queryable Backup instead of restoring.
   ```text
   Atlas UI -> cluster -> Backup -> Snapshots -> Query (on the snapshot)
   Connect with the temporary connection string Atlas provides and run reads.
   ```
   Expect: the queryable deployment takes roughly 1-5 minutes to appear, accepts reads only (no writes, no index builds, no `$out`/`$merge`), and tears itself down after an idle timeout. Query consecutive snapshots to bisect the corruption window.

3. List the available snapshots and confirm the one you want is `completed`.
   ```bash
   atlas backups snapshots list --clusterName <cluster-name> --projectId <project-id> --output json
   ```
   Expect: a list with snapshot ids, timestamps and status. Pick the newest snapshot taken before the incident.

4. Make sure no snapshot is in flight if you also plan topology changes, and take a safety snapshot of the current (damaged) state if you may need it for forensics.
   ```bash
   atlas backups snapshots list --clusterName <cluster-name> --projectId <project-id> --output json   # inspect each snapshot's status field (or check the Atlas UI)
   atlas backups snapshots create --clusterName <cluster-name> --projectId <project-id> --desc "pre-restore $(date -u +%FT%TZ)" --retentionInDays 30
   ```
   Expect: no snapshot in the JSON output (or the UI) shows a `queued` or `inProgress` status when the pipeline is idle. Atlas refuses a second on-demand snapshot while one is `queued` or `inProgress`.

5. Choose the restore mode.
   ```text
   Need a clean copy to validate, zero risk to production -> automated restore to a NEW cluster
   Need an exact moment (e.g. 1 minute before a bad updateMany) -> point-in-time restore
   Need raw .tar.gz data files -> download restore
   Need a single collection -> restore the snapshot to a new cluster, then mongodump/mongorestore that collection back
   ```
   Expect: one mode chosen and written in the incident log.

6a. Snapshot restore to a target cluster.
   ```bash
   atlas backups restores start automated \
     --clusterName <cluster-name> \
     --snapshotId <snapshot-id> \
     --targetClusterName <restored-cluster-name> \
     --targetProjectId <target-project-id>
   ```
   Expect: a restore job id is returned. The target cluster is unavailable while the job runs and all of its existing data is wiped first.

6b. Point-in-time restore (needs Continuous Cloud Backup).
   ```bash
   # Unix seconds, 1-second granularity
   atlas backups restores start pointInTime \
     --clusterName <cluster-name> \
     --pointInTimeUTCSeconds <unix-seconds> \
     --targetClusterName <restored-cluster-name> \
     --targetProjectId <target-project-id>

   # Or land on an exact oplog entry
   atlas backups restores start pointInTime \
     --clusterName <cluster-name> \
     --oplogTs <oplog-ts> --oplogInc <oplog-inc> \
     --targetClusterName <restored-cluster-name> \
     --targetProjectId <target-project-id>
   ```
   Expect: a restore job id. Atlas picks the latest snapshot at or before the target and replays the oplog forward to it. Choose a time a little before the first bad write (for example the migration start minus one minute).

6c. Download restore.
   ```bash
   atlas backups restores start download --clusterName <cluster-name> --snapshotId <snapshot-id>
   ```
   Expect: a one-time URL to a `.tar.gz` of the raw data files. The corpus says it expires after 1 hour, so start the download immediately.

7. Watch the job to completion.
   ```bash
   atlas backups restores watch <restore-job-id> --clusterName <cluster-name> --projectId <project-id>
   atlas backups restores list --clusterName <cluster-name> --projectId <project-id> --output json
   ```
   Expect: the job moves to a finished state. Timing depends on cluster size: the corpus gives "minutes to hours" for snapshot restore and under 15 minutes for an optimized point-in-time restore. Treat both as untested until you measure on your own cluster shape.

8. Validate the restored cluster (see Verify), then point the application at it, or restore only the damaged data back into production.
   ```text
   Swap the connection string (or promote) only after Verify passes.
   ```
   Expect: application health checks pass against the restored cluster.

## Verify
Connect with mongosh to the restored cluster and compare against the pre-incident expectations.
```javascript
// Document count parity (per collection)
db.getSiblingDB('app').orders.countDocuments()
// Index parity
db.getSiblingDB('app').orders.getIndexes()
// Spot-check the newest documents and the boundary around the incident time
db.getSiblingDB('app').orders.find().sort({_id:-1}).limit(10)
// Corruption check
db.getSiblingDB('app').orders.validate({ full: true })
```
Expect: counts and indexes match what you recorded or what Queryable Backup showed; no document written after the incident time exists on a point-in-time restore; `validate` reports valid. Run an application smoke test against the restored cluster before any cutover. Record the elapsed time from restore request to validated data: that is your measured recovery time.

## Rollback / abort
- If the restore target was a new cluster, abort by discarding it. Production was never touched.
- A restore over an existing cluster cannot be undone, because the target's data is deleted. Take the safety snapshot in Step 4 first, and prefer a new cluster.
- If the chosen time or snapshot was wrong, start another restore into a fresh target with a different snapshot id or timestamp.
- If a Backup Compliance Policy is active, the extra clusters and snapshots from test restores cannot be deleted early. Do rehearsals in a separate project that is not under the policy.

## Pitfalls
- Restoring directly over production without a rehearsal. The target is unavailable and wiped during the restore, and it takes longer than expected. Restore to a new cluster, validate, then swap.
- Doing a full restore to answer "what did the data look like at T". Queryable Backup answers that without burning RTO.
- Point-in-time target outside the window. Outside `restoreWindowDays` you fall back to the nearest snapshot. If the corruption was detected after the window expired there is no point-in-time recovery.
- Setting the window to the vendor default instead of the worst-case detection time, or to "as long as possible" (oplog storage cost grows with window times write rate).
- Assuming replication is a backup. A bad delete replicates to every secondary within milliseconds.
- Starting a topology change (resize, version upgrade, maintenance) while a snapshot is `inProgress`; the change can queue behind it. Check in-flight snapshots first.
- Missing the 1-hour download link expiry.
- Sharded restores: the corpus notes the source and target must have the same number of shards for a self-managed sharded restore. Verify in the current MongoDB docs: whether the same constraint applies to your Atlas target.
- The CLI reference comments a point-in-time example as "within last 24 hours". Verify in the current MongoDB docs: the exact allowed range for `--pointInTimeUTCSeconds`; use the configured window as your planning number.
- Flex and shared tiers: restore options are reduced (automated only on Flex; no point-in-time).

## Sources
- `skills/mongodb-operations-expert/references/mongodb-backup-restore.md:81-91` on-demand snapshots and the one-in-flight rule.
- `skills/mongodb-operations-expert/references/mongodb-backup-restore.md:99-141` continuous backup, 1-minute vs 1-second granularity, `restoreWindowDays`.
- `skills/mongodb-operations-expert/references/mongodb-backup-restore.md:145-169` Queryable Backup limits and workflow.
- `skills/mongodb-operations-expert/references/mongodb-backup-restore.md:223-276` three restore modes, wipe and unavailability, download expiry, mode cheat-sheet.
- `skills/mongodb-operations-expert/references/mongodb-backup-restore.md:356-378` verification checks.
- `skills/mongodb-operations-expert/references/mongodb-backup-restore.md:396-421` snapshots in flight versus topology changes.
- `skills/mongodb-operations-expert/references/mongodb-backup-restore.md:429-443` anti-patterns (restore over production, replication is not backup).
- `skills/mongodb-operations-expert/references/mongodb-backup-restore.md:748-750` compliance policy blocks cleanup of test restores.
- `skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md:477-527` restore commands, `--oplogTs/--oplogInc`, watch/list, wipe warning, Flex limits, Project Owner.
- `skills/mongodb-operations-expert/references/mongodb-disaster-recovery.md:171-180` and `:405-437` typical restore times and point-in-time semantics.
- `llms/mongodb.com.llms/llms-facts.txt:1516` sharded restore shard-count rule.
