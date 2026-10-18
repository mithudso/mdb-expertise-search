---
name: upgrade-self-managed-replica-set
title: Roll a self-managed replica set to the next MongoDB major version
summary: Rolling binary upgrade of a replica set one major version at a time (secondaries, arbiters, then the primary via stepDown), with FCV held back for a burn-in period and a documented rollback path.
applies_to: [self-managed]
sources:
  - skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md
  - skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md
---
# Roll a self-managed replica set to the next MongoDB major version

## When to use
- You run your own `mongod` processes in a replica set and must move from major version N-1 to N (for example 7.0 to 8.0).
- You want a rolling procedure that keeps a writable primary and a voting majority at every moment.
- For a sharded cluster use `upgrade-self-managed-sharded-cluster`. For an Atlas cluster use `upgrade-atlas-cluster-major-version`.

## Prerequisites (checklist)
- [ ] Every member is on the prerequisite major version AND its FCV equals that version. You cannot jump 5.0 to 7.0 or 6.0 to 8.0.
- [ ] Driver versions that support the target server are deployed and steady for 7 or more days (Java 5.1+ for 8.0, recommended 5.4+; Node.js driver 6.x; PyMongo 4.9+; C# 3.0+; Go 1.17+ are the corpus minimums for 8.0. Confirm exact patch levels in the driver docs).
- [ ] Operating system is supported by the target version (8.0 needs RHEL 8.8+/9.3+, SLES 15 SP5+, or Amazon Linux 2023.3+).
- [ ] No in-flight index builds.
- [ ] Change-stream consumers store resume tokens durably.
- [ ] Oplog window is at least 4 times the expected maintenance duration.
- [ ] Every secondary has replication lag under 5 seconds.
- [ ] Free disk space of at least 25% on every member.
- [ ] A backup was restored into a scratch environment and passed a smoke query.
- [ ] Topology is not PSA (primary, secondary, arbiter). If it is, convert to three data-bearing voters first.
- [ ] A single change owner and a rollback decision are written into the change ticket.

## Steps

1. **Record the starting state on every member.**
   ```javascript
   db.version();
   db.adminCommand({ getParameter: 1, featureCompatibilityVersion: 1 });
   rs.status();
   ```
   Expect: all members on the same binary and FCV, one `PRIMARY`, others `SECONDARY` (or `ARBITER`). If FCV lags the binary by more than one major version, stop and walk FCV forward one hop first.

2. **Run the safety gates.**
   ```javascript
   db.currentOp({ "command.createIndexes": { $exists: true } });
   db.currentOp({ msg: /Index Build/ });
   rs.printReplicationInfo();
   rs.printSecondaryReplicationInfo();
   ```
   Expect: no index build output; oplog length at least 4 times the maintenance window; lag under 5 seconds. An interrupted index build can leave a collection inconsistent, so wait for it to finish or drop it and rebuild after the upgrade.

3. **Enlarge the oplog if the window is short.**
   ```javascript
   db.adminCommand({ replSetResizeOplog: 1, size: 102400 });   // size in MB (100 GB here)
   ```
   Expect: `{ ok: 1 }`. A secondary that falls behind the oplog window enters a full initial sync after restart.

4. **Optionally set a preferred post-upgrade primary.** Raise `members[n].priority` for the member you want elected after the stepDown. Lowering `electionTimeoutMillis` (default 10 seconds) to 5000 ms can shorten the outage, but it changes failover semantics; review it and revert afterwards.
   Expect: `rs.conf()` shows the intended priority.

5. **Upgrade the first secondary.** Shut it down cleanly, install the new binaries, start it with its existing configuration. Do not change FCV.
   ```javascript
   rs.status();
   ```
   Expect: the member passes through `STARTUP2` or `RECOVERING` and returns to `SECONDARY`. Do not start the next node until this is true.

6. **Repeat for each remaining secondary, one at a time.**
   Expect: after each node, `rs.status()` shows all members healthy and lag back under 5 seconds.

7. **Upgrade arbiters (if any).** Stop, swap binaries, start, confirm `ARBITER` state. Arbiters hold no data and need no FCV consideration. Upgrade them after the secondaries and before the primary; their vote matters during the stepDown.
   Expect: `rs.status()` shows `ARBITER`.

8. **Optionally pre-warm each upgraded secondary** (latency-sensitive workloads). The corpus documents a manual procedure, not a MongoDB tool: after the node reaches `SECONDARY`, hold it out of routing (for example `hidden: true, priority: 0`, or remove it from read-preference rotation), run a scripted read workload against the hot indexes, and watch cache growth.
   ```javascript
   db.serverStatus().wiredTiger.cache;
   ```
   Expect: "bytes currently in the cache" and "pages read into cache" flatten, cache is around 70% of the configured cache size, and p99 latency of the touch workload matches the pre-upgrade baseline. Only then restore `hidden: false` and the original priority.

9. **Step down the primary.** Connect `mongosh` to the primary.
   ```javascript
   rs.stepDown();
   ```
   Expect: a clean election in roughly 10 to 12 seconds with a brief write pause; the default freeze (the period the stepped-down member cannot seek election) is 60 seconds. Retryable writes with default drivers resume on the new primary. Prefer stepDown to killing the process.

10. **Upgrade the former primary** exactly like a secondary (step 5).
    Expect: it rejoins as `SECONDARY`; all members run the new binary.

11. **Hold FCV at the old value and burn in.** Do not run `setFeatureCompatibilityVersion` yet. Run for 1 to 4 weeks, watching latency percentiles, error rate, replication lag and oplog window.
    Expect: metrics at baseline; no incident attributed to the new binary. While FCV is still N-1 you can binary-downgrade.

12. **Advance FCV after sign-off.** Proceed only when drivers have been steady 7+ days, there are no incidents, backup verification on the new binaries succeeded, and the application owner approved irreversibility.
    ```javascript
    db.adminCommand({ setFeatureCompatibilityVersion: "8.0", confirm: true });
    ```
    Use the target version in place of "8.0". `confirm: true` is required from 7.0 onward.
    Expect: `{ ok: 1 }`, and `getParameter` for `featureCompatibilityVersion` returns the new value.

13. **Restore any temporary settings** (election timeout, priorities, oplog size if disk pressure demands) and capture the post-event metrics and sign-off.

## Verify
- `db.version()` is the target on every member; `rs.status()` shows one primary and all others healthy.
- FCV matches the plan (old during burn-in, new after step 12).
- Application smoke tests pass: read, write, change stream, aggregation, index build. Each application team confirms connect/read/write.
- `listIndexes` output is consistent between primary and secondaries.
- Latency, error rate, lag and oplog window are back at baseline within 72 hours.

## Rollback / abort
| State | Can you roll back? |
| --- | --- |
| Binary upgraded, FCV still N-1, no new features used | Yes. Rolling binary downgrade, primary last (use stepDown). |
| FCV advanced to N, no new-version-only features used | Only by lowering FCV first (`setFeatureCompatibilityVersion: "N-1", confirm: true`), then binary downgrade. |
| FCV advanced and new-version-only features used | Not supported until that data/feature is removed; open a Support case before touching anything. |
- Abort mid-roll: stop after the current node is healthy; a replica set with mixed N-1 and N binaries and FCV N-1 is a supported state during the window, but do not leave it that way beyond the maintenance event.
- Record every rollback as a near-miss.
- See `fcv-and-rollback-plan` for the full decision table.

## Pitfalls
- **Driver mismatch** is the most common day-one incident; app teams discover they cannot connect after the primary steps down.
- **Advancing FCV too early** closes the rollback path. Self-managed clusters have no automatic enforcement; write the burn-in end date into the runbook.
- **Starting the next node too soon.** Wait for `SECONDARY`, not just a running process.
- **PSA topology.** With the data secondary down and the primary stepping down, no eligible primary exists and the set goes read-only. Convert to three data-bearing voters first, or leave 24+ hours between the secondary and primary upgrades.
- **Interrupted index builds** leave a secondary stuck in `RECOVERING` or rejected by `replSetReconfig`.
- **Short oplog.** A long maintenance window pushes a secondary beyond the oplog and forces a full initial sync.
- **Cold cache.** A restarted `mongod` starts with an empty WiredTiger cache; when reads shift to a freshly upgraded secondary, latency spikes until it warms. This is an undocumented-upstream operational gap, so use the pre-warm step for latency-critical workloads.
- **Pausing rule.** If the change log collects more than one unexplained warning, pause rather than push through.
- **7.0 to 8.0 behavior changes.** Majority-write acknowledgment on 8.0 happens after the secondary journals the oplog entry (before apply), which widens the staleness window for reads from secondaries right after a majority write. Audit causal-consistency usage.

## Sources
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:123 (sequential path, hard rules)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:161 (FCV, preservation window, burn-in)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:196 (rolling order, election timing, arbiters)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:263 (driver matrix)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:295 (pre-upgrade gates, oplog resize)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:334 (rollback table, playbook)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:365 (disk pre-warming SOP)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:451 (common failures)
- skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md:383 (OS minimums, risk checklist)
