---
name: upgrade-atlas-cluster-major-version
title: Upgrade an Atlas cluster to the next MongoDB major version
summary: Pre-check, schedule, perform, monitor and validate a one-major-version upgrade of a dedicated Atlas cluster, including how automatic and end-of-life-forced upgrades interact with a manual one.
applies_to: [atlas]
sources:
  - skills/mongodb-atlas-expert/references/mongodb-atlas-managed-upgrades.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-tiers-upgrades.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md
  - skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md
  - skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md
---
# Upgrade an Atlas cluster to the next MongoDB major version

## When to use
- A dedicated (M10+) cluster is pinned to a major version (for example 7.0) and you want to move it to the next one (for example 8.0) on your schedule.
- You received an Atlas end-of-life (EOL) notice for the cluster's major version and must upgrade before the cut-off.
- You need to understand why a cluster upgraded without a change ticket (auto-upgrade or EOL-forced upgrade).

## Prerequisites (checklist)
- [ ] Cluster is a Dedicated tier (M10 or larger). Free and Flex clusters have no version choice; Atlas upgrades them on its own schedule.
- [ ] You know the current major version and the current Feature Compatibility Version (FCV). The target is exactly one major version above (no skipping).
- [ ] The target is not more than 2 major versions above the cluster's pinned FCV. If FCV is pinned at 6.0, the Atlas UI only offers 7.0.
- [ ] Cluster is healthy and a recent snapshot exists (take an on-demand one, see step 3).
- [ ] Application drivers are already on a version that supports the target server version, deployed for at least 7 days.
- [ ] Free disk headroom is confirmed (write-blocking and Search index rebuild need space, see step 2).
- [ ] You have a staging cluster, or can clone production data into one, to rehearse the upgrade.
- [ ] You are a Project Owner (or have equivalent rights) and know the project's maintenance window.

## Steps

1. **Record the starting state.** Check the cluster's current version and FCV.
   ```bash
   atlas clusters describe <cluster-name> --projectId <project-id>
   ```
   ```javascript
   db.version();
   db.adminCommand({ getParameter: 1, featureCompatibilityVersion: 1 });
   ```
   Expect: the binary version and FCV are the source major (for example both 7.0). If FCV lags the binary by a major version, stop and fix that first.

2. **Run the pre-checks specific to the target version.**
   - Read the target version's compatibility changes and grep the application for removed or deprecated commands. For a 7.0 to 8.0 move the corpus lists, among others: LDAP authentication, index filters (`planCacheSetFilter`, replace with `setQuerySettings`), `$accumulator`/`$function`/`$where`, `cleanupOrphaned`, and BSON `undefined` handling.
   - Confirm disk headroom. On 8.0 dedicated clusters Atlas blocks writes on the primary when free space falls below a size-dependent threshold. Verify in the current MongoDB docs: the thresholds and whether they apply on 8.0 (the corpus gives 600 MB on disks under 20 GB, 4% on disks under 1.25 TB, 50 GB on 1.25 TB or larger). Enable storage auto-scaling or grow the disk before the upgrade.
   - If the cluster uses Atlas Search or Vector Search, leave room for two copies of each search index: Atlas builds the new index version beside the old one.
   - Check for time-series collections created before the fix for SERVER-99290; invalid time-series bucket collections can make the later FCV 8.0 step fail.
   Expect: a written list of risks with an owner for each; free disk comfortably above the thresholds.

3. **Take and verify a snapshot.**
   ```bash
   atlas backups snapshots create --clusterName <cluster-name> --projectId <project-id> --desc "pre-upgrade snapshot"
   atlas backups snapshots watch <snapshot-id> --clusterName <cluster-name> --projectId <project-id>
   ```
   Expect: the snapshot reaches a completed state. Restore it into a scratch cluster and run a smoke query; an untested backup is not a backup.

4. **Rehearse on a staging cluster.** Clone production data into a staging cluster, upgrade it with the same steps below, run application tests and a failover test, and upgrade drivers if needed.
   Expect: application passes functional and failover tests on the new major version. If staging surfaces version-specific issues, open a high-priority support ticket before touching production.

5. **Decide on the FCV pin before upgrading.** A downgrade after a major upgrade is only possible if FCV was pinned beforehand, and the pin lasts at most 4 weeks. Decide now whether you need that rollback path.
   Verify in the current MongoDB docs: the exact UI or API control used to pin FCV during the version-change dialog.
   Expect: a written decision, with the pin expiry date on the calendar if you pin.

6. **Check and set the maintenance window.** Review the project's maintenance window, protected hours and sequence settings. A manual defer is allowed up to twice per scheduled event; Atlas gives 48 to 72 hours notice before required maintenance.
   Expect: the window is at a low-traffic time, and you know whether the upgrade starts now or at the window.

7. **Start the upgrade.** In the Atlas UI open the cluster, choose the version-change action, select the next major version, and confirm. Alternatively use the CLI, which the corpus shows for one-major upgrades:
   ```bash
   atlas clusters update <cluster-name> --projectId <project-id> --mdbVersion 8.0
   ```
   Expect: the cluster shows an updating state. If the UI offers no version beyond one major, the 2-major FCV ceiling or the no-skip rule applies.

8. **Watch the rollout.** Atlas upgrades secondaries first, steps the primary down, elects a new primary, then upgrades the former primary. At least one election occurs and writes pause for a few seconds.
   ```bash
   atlas clusters watch <cluster-name> --projectId <project-id>
   ```
   Expect: the command prints "Cluster available." when the cluster returns to IDLE. Application drivers with retryable writes reconnect to the new primary.

9. **Validate immediately.** Re-run the version and FCV checks from step 1, then run application smoke tests (read, write, change stream, aggregation, index build).
   ```javascript
   db.version();
   db.adminCommand({ getParameter: 1, featureCompatibilityVersion: 1 });
   ```
   Expect: binary at the new major. FCV stays at the old major if you pinned it; otherwise Atlas advances it.

10. **Run the burn-in.** Operate for 1 to 4 weeks (never beyond the 4-week Atlas pin) watching p50/p95/p99 latency, error rate, replication lag, oplog window and disk free space.
    Expect: metrics return to the pre-upgrade baseline once caches are warm.

11. **Close the rollback path deliberately.** Before the pin expires, get written application-owner sign-off, then let FCV advance (or advance it yourself).
    Expect: FCV equals the new major; downgrade in place is no longer available.

## Verify
- `db.version()` reports the target major on every node, and `atlas clusters describe` shows the cluster idle.
- FCV matches your plan (old major during burn-in, new major after sign-off).
- Application error rate and latency match baseline after warm-up. A persistent regression after warm-up is a real regression to diagnose, not an expected upgrade effect.
- No open alerts for disk space, write-blocking or "Insufficient disk space to support rebuilding search indexes".
- Search and Vector Search indexes report ready.

## Rollback / abort
- Before you start step 7: abort freely; nothing has changed.
- After the upgrade, FCV still pinned and inside the 4-week window: a downgrade is possible. Use the Atlas major-version downgrade procedure. Verify in the current MongoDB docs: the current steps and any limits in "Downgrade Major MongoDB Version for a Cluster".
- After FCV has advanced (your action, or auto-unpin at the next maintenance after the pin expires): no in-place downgrade. The only clean re-baseline is a new cluster on the old major version, restored from a snapshot or populated by migration.
- If new-version-only features are in use (new index types, encrypted ranges, and similar), the downgrade needs removal of that data first and may need a Support case.
- Treat any rollback as a near-miss and record it, even when it succeeds.

## Pitfalls
- **Assuming you can turn auto-upgrade off.** There is no setting that disables automatic version updates. A pinned cluster is still upgraded by Atlas when its major version hits EOL (at least 6 months notice by email to project owners). Maintenance controls only shift timing.
- **Choosing "Latest Version With Auto Upgrades" casually.** Atlas then moves the cluster through major and minor versions on its own timetable, you cannot pick a specific version, and Live Migration and Mongosync do not support such clusters.
- **Upgrading while disk is nearly full.** Write-blocking on 8.0 appears as `MongoServerError: User writes blocked, reason: DiskUseThresholdExceeded` with no application change. Once blocked, Atlas also refuses drops that would free space. Fix capacity before the upgrade.
- **Forgetting Search index double copies.** Index rebuilds need space for both copies and compound the disk risk.
- **Pinned FCV then a late jump.** If FCV stayed at 6.0 from an earlier upgrade, the UI only offers 7.0 until FCV advances.
- **Drivers upgraded the same day.** Driver mismatch is the most common day-one incident. Upgrade drivers at least 7 days earlier.
- **Expecting zero impact.** Each restarted node starts with an empty WiredTiger cache and a reset plan cache, and there is one election of write pause. Do not diagnose warm-up latency as a regression.
- **Mixing up the App Services end-of-life with the server upgrade.** Database Triggers are not deprecated; the two timelines are independent.
- **Turning on `defaultMaxTimeMS` during the rollout.** The parameter defaults to 0 (off). Setting it can make existing long analytics queries fail with `MaxTimeMSExpired`.

## Sources
- skills/mongodb-atlas-expert/references/mongodb-atlas-managed-upgrades.md:78 (cadence models, EOL forced upgrade)
- skills/mongodb-atlas-expert/references/mongodb-atlas-managed-upgrades.md:109 (maintenance window, protected hours, defer limits)
- skills/mongodb-atlas-expert/references/mongodb-atlas-managed-upgrades.md:135 (no way to disable automatic version updates)
- skills/mongodb-atlas-expert/references/mongodb-atlas-managed-upgrades.md:144 (2-major FCV ceiling, no downgrade without pin, staging-first workflow)
- skills/mongodb-atlas-expert/references/mongodb-atlas-managed-upgrades.md:179 (write-blocking thresholds and error string)
- skills/mongodb-atlas-expert/references/mongodb-atlas-managed-upgrades.md:217 (Search index dual-copy rebuild)
- skills/mongodb-atlas-expert/references/mongodb-atlas-managed-upgrades.md:195 (`defaultMaxTimeMS`)
- skills/mongodb-atlas-expert/references/mongodb-atlas-managed-upgrades.md:266 (SERVER-99290)
- skills/mongodb-atlas-expert/references/mongodb-atlas-tiers-upgrades.md:39 (rolling process, one election)
- skills/mongodb-atlas-expert/references/mongodb-atlas-tiers-upgrades.md:56 (post-upgrade cache expectations)
- skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md:391 (`--mdbVersion` upgrade), :356 (`clusters watch`), :460 (snapshot create)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:346 (Point of No Return, 4-week window), :451 (failure modes)
- skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md:288 (deprecations table)
