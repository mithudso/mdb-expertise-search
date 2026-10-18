---
name: fcv-and-rollback-plan
title: Plan FCV changes and the rollback path for a MongoDB upgrade
summary: Understand featureCompatibilityVersion as the gate between binary upgrade and feature activation, hold it back for a burn-in, and use a decision table to choose between binary downgrade, FCV lowering and restore.
applies_to: [atlas, self-managed]
sources:
  - skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-managed-upgrades.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-tiers-upgrades.md
  - skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md
---
# Plan FCV changes and the rollback path for a MongoDB upgrade

## When to use
- Before any major-version upgrade, to decide when (and whether) to advance featureCompatibilityVersion (FCV) and what rollback you are promising.
- During a post-upgrade regression, to decide whether a downgrade is still possible.
- When you must explain to a stakeholder why an upgrade cannot simply be undone.

## Prerequisites (checklist)
- [ ] You know the running binary version and the current FCV of the deployment (they are separate values).
- [ ] You know whether the platform is Atlas (FCV pin limited to 4 weeks, auto-unpin at the next maintenance) or self-managed (no enforced limit).
- [ ] The upgrade procedure for your topology is chosen: `upgrade-atlas-cluster-major-version`, `upgrade-self-managed-replica-set` or `upgrade-self-managed-sharded-cluster`.
- [ ] Someone with authority (the application owner) is named to sign off on irreversibility.
- [ ] You can list which new-version-only features the application might start using (new index types, encrypted ranges, time-series resharding on 8.0.10+).

## Steps

1. **Read the current state.**
   ```javascript
   db.version();
   db.adminCommand({ getParameter: 1, featureCompatibilityVersion: 1 });
   ```
   Expect: binary version and FCV. After upgrading binaries to N, FCV stays at N-1 until someone sets it. If FCV lags the binary by more than one major version, stop: walk FCV forward one hop at a time before any further binary change.

2. **Choose the policy: hold FCV during a burn-in.** Upgrade binaries first and run with FCV at N-1 for a deliberate burn-in, 1 to 4 weeks. While FCV is N-1, new backwards-incompatible features stay disabled, so no persisted data blocks a binary downgrade.
   Expect: a calendar date written in the runbook for the end of the burn-in. On Atlas, that date must be within 4 weeks of the pin.

3. **Define the exit criteria for advancing FCV.** Require all of:
   - drivers upgraded and steady for 7 or more days;
   - no production incident traced to the new binary;
   - backup verification on the new binaries succeeded;
   - written sign-off from the application owner that the change is irreversible.
   Expect: a checklist attached to the change ticket.

4. **Pre-check anything that can block the FCV step.** For FCV 8.0, invalid time-series bucket collections (SERVER-99290) can prevent completion. On a sharded cluster with a config shard, note the downgrade gate (step 8).
   Expect: no known blockers, or a remediation plan.

5. **Advance FCV.** Run on the primary (replica set) or through a `mongos` (sharded cluster).
   ```javascript
   db.adminCommand({ setFeatureCompatibilityVersion: "8.0", confirm: true });
   ```
   Use the target version in place of "8.0". `confirm: true` has been required since 7.0 and remains required in 8.0.
   Expect: `{ ok: 1 }`. Re-read FCV with step 1's `getParameter`. This is the Point of No Return for the simple rollback path.
   On Atlas, if the cluster is not pinned, or the pin expires, Atlas advances FCV for you at the next maintenance. Verify in the current MongoDB docs: how to pin FCV and see the pin expiry in the Atlas UI.

6. **If a regression appears, classify it with the decision table below** before changing anything.
   Expect: one row of the table selected and recorded in the ticket.

   | Situation | Action | Notes |
   | --- | --- | --- |
   | Binary at N, FCV still N-1, no new features used | Rolling binary downgrade | Replica set: primary last. Sharded: `mongos`, then shards, then config servers. |
   | Binary at N, FCV advanced, no new-version-only features used | Lower FCV (`setFeatureCompatibilityVersion: "N-1", confirm: true`), then binary downgrade | Run the audit in step 7 first. |
   | FCV advanced and new-version-only features in use | Not supported until that data or those features are removed | Open a Support case before touching anything. |
   | Atlas, FCV unpinned or pin expired | No in-place downgrade | Re-baseline on a new cluster on the old major, from snapshot or migration. |
   | Config shard topology, downgrading below 8.0 | Run `transitionToDedicatedConfigServer` first | No path back through FCV downgrade alone. |
   | Data damaged or other failure not tied to version | Restore from backup | Verified backup is the last resort. |

7. **Audit for new-version-only features** before lowering FCV. Look for indexes that depend on new operators or new index types, queryable encryption range queries, and sharded time-series collections that were resharded.
   Expect: a clean list, or a decision to involve Support.

8. **Execute the chosen action.** For FCV lowering:
   ```javascript
   db.adminCommand({ setFeatureCompatibilityVersion: "7.0", confirm: true });
   ```
   Use the previous version in place of "7.0". Then perform the rolling binary downgrade in reverse order. For the config shard case, run the transition first.
   Verify in the current MongoDB docs: the full `transitionToDedicatedConfigServer` procedure and any prerequisites.
   Expect: FCV reads the lower value before any binary is swapped.

9. **Record the event.** Log the rollback or the decision not to roll back as a near-miss, with timestamps, the table row chosen and the outcome.

## Verify
- `getParameter` for `featureCompatibilityVersion` returns exactly the value you intended after each change.
- After a downgrade, `db.version()` is the old major on every node and the application passes smoke tests.
- Atlas: the cluster's version and any FCV pin expiry date are recorded in your own documentation.
- Sign-off is on the ticket before FCV advance; without it the event is not closed.

## Rollback / abort
- To abort an FCV advance: you cannot cancel a completed `setFeatureCompatibilityVersion`; you can only lower it again if the table allows.
- To abort before advancing: simply leave FCV at N-1 and either keep running (burn-in) or do the rolling binary downgrade.
- If `setFeatureCompatibilityVersion` fails part way, do not retry blindly: capture the error text, check for blockers (step 4) and open a Support case if unexplained.

## Pitfalls
- **Advancing FCV too early.** The most common regret: the operator, or Atlas auto-unpin, advanced FCV before burn-in ended and an unrelated incident then needs a rollback that is closed.
- **Treating the 4-week Atlas window as a soft guideline.** After expiry Atlas auto-unpins and advances FCV at the next maintenance, which closes the rollback path.
- **Assuming self-managed has no deadline.** There is no enforcement, so long-pinned FCV blocks feature adoption and leaves the cluster half-upgraded. Review FCV state at every weekly check until it is advanced.
- **Confusing binary and FCV.** `db.version()` returns the binary; FCV is a separate admin parameter.
- **Forgetting `confirm: true`** (required from 7.0).
- **Atlas 2-major ceiling.** You cannot choose a target version more than 2 major versions above the pinned FCV; a stale pin from an earlier upgrade blocks the next one.
- **Skipping majors "to save time".** rapid sequential upgrade is an operational pattern of back-to-back one-major hops with FCV held at the source version, not a supported skip.
- **Adopting new-version-only features right after FCV advance.** Once such features are in use, the simple downgrade is unsupported. Hold adoption until the rollback window is no longer needed.
- **Config shard downgrade.** Forgetting `transitionToDedicatedConfigServer` before lowering FCV below 8.0.

## Sources
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:150 (read binary and FCV, lag rule)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:161 (FCV key facts, `confirm: true`, preservation window, burn-in)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:334 (rollback table)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:346 (Point of No Return)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:353 (rollback playbook)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:466 (FCV unpinned too early)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:140 (rapid sequential upgrade)
- skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:257 (config shard caveat)
- skills/mongodb-atlas-expert/references/mongodb-atlas-managed-upgrades.md:144 (2-major ceiling, no downgrade without pin)
- skills/mongodb-atlas-expert/references/mongodb-atlas-managed-upgrades.md:266 (SERVER-99290)
- skills/mongodb-atlas-expert/references/mongodb-atlas-tiers-upgrades.md:46 (cannot A/B old version in place)
- skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md:228 (config shard transition commands)
