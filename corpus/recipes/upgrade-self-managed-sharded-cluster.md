---
name: upgrade-self-managed-sharded-cluster
title: Upgrade a self-managed sharded cluster to the next MongoDB major version
summary: Strict-order rolling upgrade of a sharded cluster (stop balancer, config servers, shards, mongos, re-enable balancer, then FCV) with version-skew rules and validation.
applies_to: [self-managed]
sources:
  - skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md
  - skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-managed-upgrades.md
---
# Upgrade a self-managed sharded cluster to the next MongoDB major version

## When to use
- You operate your own sharded cluster (config server replica set, shard replica sets, `mongos` routers) and are moving one major version up (for example 7.0 to 8.0).
- You need the component order and the version-skew rules, not just the per-replica-set procedure.
- For each replica set inside the cluster, the per-node procedure is the one in `upgrade-self-managed-replica-set`.

## Prerequisites (checklist)
- [ ] All components are on the prerequisite major version with FCV equal to it (check through a `mongos`).
- [ ] The per-replica-set safety gates passed on the config server replica set and every shard: no in-flight index builds, lag under 5 seconds, oplog window at least 4 times the maintenance window, 25% free disk.
- [ ] Drivers supporting the target version are deployed and steady for 7 or more days.
- [ ] A tested backup of the cluster exists (restored into scratch and smoke-queried).
- [ ] No direct application, backup or health-check connections to shard `mongod` processes that bypass `mongos` (on 8.0 a command allowlist breaks them; audit before upgrading).
- [ ] You know whether the cluster uses a config shard (config server also acting as a data shard, introduced in 7.0).
- [ ] No migration or resharding operation you cannot afford to interrupt is scheduled in the window.
- [ ] A rehearsal on a non-production cluster of the same topology has been done.

## Steps

1. **Record the starting state.** Connect to a `mongos`.
   ```javascript
   db.version();
   db.adminCommand({ getParameter: 1, featureCompatibilityVersion: 1 });
   sh.status();
   db.adminCommand({ listShards: 1 });
   ```
   Expect: all components on the old binary, FCV at the old value, every shard listed and healthy.

2. **Check index consistency across shards before touching binaries.** Use the official MongoDB shard index inconsistency script (named in the corpus as the "Shard Index Inconsistent Script") and `listIndexes` per shard.
   ```javascript
   db.runCommand({ listIndexes: "<coll>" });
   ```
   Expect: identical indexes on every shard. Resolve discrepancies now; they are a recurring upgrade failure.

3. **Disable the balancer.** Do this before any binary change.
   ```javascript
   sh.stopBalancer();
   sh.isBalancerRunning();
   ```
   Expect: `sh.isBalancerRunning()` returns `false`. If a chunk migration is in progress, `stopBalancer` waits for it to finish; re-run the check until it reports false.

4. **Upgrade the config server replica set (CSRS) first.** Apply the rolling procedure: each secondary in turn, then `rs.stepDown()` on the primary, then the former primary. Do not change FCV.
   ```javascript
   rs.status();
   ```
   Expect: each member returns to `SECONDARY` before the next starts; the CSRS ends with one primary and all members healthy. Config servers must never be older than the shards, so this tier must finish before any shard.

5. **Upgrade the shards, one shard replica set at a time.** For each shard use the rolling procedure (secondaries, arbiters, then primary via `rs.stepDown()`). Start with the least critical shards; most incidents in the corpus originate in the shard phase.
   Expect: after each shard, a health gate: all members healthy, lag under 5 seconds, application error rate unchanged. Pause if more than one unexplained warning accumulates.

6. **Upgrade the `mongos` routers last.** `mongos` is stateless: drain connections and restart in parallel groups. A mixed-version `mongos` pool is tolerated during the window only.
   ```javascript
   db.version();
   ```
   Run it on each `mongos`.
   Expect: every `mongos` reports the new version. Run a health gate after the last `mongos` and before any FCV change.

7. **Re-enable the balancer.**
   ```javascript
   sh.startBalancer();
   sh.status();
   ```
   Expect: `sh.status()` shows the balancer enabled and no errors. FCV is still the old value.

8. **Burn in with FCV held back** for 1 to 4 weeks. Monitor latency percentiles, error rate, replication lag on every shard, and chunk balance.
   Expect: metrics at baseline. While FCV is old, binary downgrade is still possible. A 7.0 `mongos` can still talk to an 8.0 cluster that is pinned at FCV 7.0.

9. **Advance FCV** once sign-off is in hand. Run it through a `mongos`.
   ```javascript
   db.adminCommand({ setFeatureCompatibilityVersion: "8.0", confirm: true });
   db.adminCommand({ getParameter: 1, featureCompatibilityVersion: 1 });
   ```
   Use the target version in place of "8.0". Expect: `{ ok: 1 }` and the new FCV value. A 7.0 `mongos` can no longer connect once FCV is 8.0.
   If the step fails unexpectedly on a cluster with time-series collections created before the fix for SERVER-99290, check for invalid time-series bucket collections.

10. **Capture sign-off.** Post-event metric snapshot, smoke tests from each application team (read, write, change stream, aggregation, index build), written customer or owner sign-off.
    Expect: a ticket with the executed runbook and the change log attached.

## Verify
- `db.version()` is the target on config servers, all shards and all `mongos`.
- `sh.status()` is clean and the balancer is running (unless you intentionally delayed it).
- FCV equals your plan: old during burn-in, new after step 9.
- Index definitions are consistent across shards (re-run step 2 checks).
- Application smoke tests pass and latency, error rate, lag, oplog window return to baseline within 72 hours.
- No application or tool is connecting directly to shard `mongod` processes on 8.0.

## Rollback / abort
- Before FCV advance: rolling binary downgrade in reverse order, `mongos` first, then shards (primary last in each replica set), then config servers. Re-enable the balancer only when all components are back on one version.
- After FCV advance with no new-version-only features: lower FCV (`setFeatureCompatibilityVersion: "N-1", confirm: true`), then binary downgrade in the order above.
- Config shard topology: you must run `transitionToDedicatedConfigServer` before downgrading FCV below 8.0; there is no path back through an FCV downgrade alone. Verify in the current MongoDB docs: the full `transitionToDedicatedConfigServer` procedure before attempting it.
- With new-version-only features in use (for example resharding of time-series collections on 8.0.10+), open a Support case before changing anything.
- Abort during the window: leave the balancer off until all components are on a single version, and never leave a shard on a newer binary than its config server.
- See `fcv-and-rollback-plan` for the decision table.

## Pitfalls
- **Wrong order.** Config servers, then shards, then `mongos`, then FCV. Skipping the order causes `IncompatibleServerVersion` or routing errors that appear intermittently.
- **Forgetting to stop the balancer**, or re-enabling it before the last `mongos` is upgraded.
- **Version skew.** A `mongos` at version M can only talk to `mongod` processes with FCV no greater than M. Advance FCV only after the last `mongos` is upgraded and stable.
- **Mixed `mongos` pools left running** beyond the maintenance event.
- **Index inconsistencies across shards** surface during or after the upgrade; check beforehand with the official script.
- **Direct shard connections** from backup scripts or tools break under the 8.0 command allowlist.
- **Combining a major upgrade with other changes** (resharding, shard additions, DDL) in the same window. On 8.0 a shard add or remove now waits for an in-flight DDL operation such as `reshardCollection`, so a combined window can stall; keep topology static.
- **Driver mismatch** and **FCV advanced too early** are the same top failure modes as for a replica set.
- **Treating cold cache as a regression.** Restarted nodes warm gradually; plan the pre-warm step from the replica-set recipe for latency-critical shards.

## Sources
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:225 (strict order, balancer commands, FCV after all tiers)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:251 (version-skew rules)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:257 (config shard caveat)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:295 (pre-upgrade gates)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:357 (reverse order for downgrade)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:477 (index inconsistency), :492 (mongos skew)
- skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md:225 (DDL ordering), :388 (direct-shard-connection audit)
- skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md:231 (config shard downgrade gate)
- skills/mongodb-atlas-expert/references/mongodb-atlas-managed-upgrades.md:266 (SERVER-99290)
