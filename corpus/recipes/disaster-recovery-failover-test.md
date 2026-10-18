---
name: disaster-recovery-failover-test
title: Plan and run a disaster recovery failover test
summary: Define RTO and RPO, write a test plan with a pre-declared abort envelope, trigger a primary failover (Atlas test failover or rs.stepDown), verify the application, and write up measured results.
applies_to: [atlas, self-managed]
sources:
  - skills/mongodb-operations-expert/references/mongodb-disaster-recovery.md
  - skills/atlas-diagnostics-expert/references/mongodb-stress-and-resilience-testing.md
  - skills/atlas-diagnostics-expert/references/mongodb-monitoring-observability.md
  - skills/mongodb-expert/references/mongodb-replication.md
  - skills/mongodb-operations-expert/references/mongodb-backup-restore.md
  - skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md
---
# Plan and run a disaster recovery failover test

## When to use
- You have a documented (or assumed) RTO/RPO and have never measured it.
- A regulator, audit, steering committee or architecture review asks for evidence that failover works.
- You changed topology, tier, region set, driver version, or connection settings since the last test. The corpus says each of these invalidates earlier test data.
- You want to find out whether the application tier, not just the database, recovers in time.

## Prerequisites (checklist)
- [ ] A named decision authority who approves running the test, aborting it, and any forced reconfiguration. The corpus says not to assume approval from earlier context.
- [ ] A dedicated test cluster that mirrors production tier, region layout and settings, or an agreed production test window. Atlas test failover needs a dedicated cluster (M10 or larger); it is unavailable on Free and Flex tiers and on shared infrastructure.
- [ ] Atlas role for the person running it: Organization Owner, Project Owner, or Project Cluster Manager. Verify in the current MongoDB docs: which Atlas roles may run a test failover.
- [ ] Atlas pre-flight conditions met: all members healthy with current monitoring. Verify in the current MongoDB docs: the pre-flight numbers (replication lag under 10 seconds, at least 5% free disk on all nodes, oplog headroom for a 3-hour operation on the primary) and whether Atlas rejects the test when they are not met.
- [ ] A load generator that issues writes with the write concern the real application uses, running during the test.
- [ ] Dashboards for steady-state metrics and a named observer per dashboard.
- [ ] A recent restore test (the DR ladder bottoms out in backups; see the restore recipes).
- [ ] The current runbook is open and will be edited afterwards.

## Steps
1. Define the objectives in writing.
   ```text
   RTO = maximum tolerable downtime, measured from outage detection to verified healthy workload.
   RPO = maximum tolerable data loss as a time interval (RPO 0 means every committed write survives).
   Include app tier, DNS, connection-string rotation, cache warm-up and human decision time. Database-only numbers are not end-to-end RTO.
   ```
   Expect: one RTO and one RPO per workload tier. Reference points from the corpus: single-region AZ failure is seconds with RPO about 0 under `w:majority`; multi-region primary-region loss is seconds to about 1 minute; Continuous Cloud Backup restore is under 15 minutes with about 1 minute RPO (Verify in the current MongoDB docs: both the restore time and the RPO claim); snapshot restore is minutes to hours.

2. Write the test plan (seven parts).
   ```text
   1 Hypothesis      "If the primary fails, the order-write API recovers within <N> seconds with at most <M> seconds of lost writes."
   2 Steady state    dashboards/queries that define normal (error rate, p99 latency, replication lag, connections)
   3 Error envelope  pre-declared abort conditions (Step 3)
   4 Injection       Atlas test failover, or rs.stepDown() on self-managed
   5 Observation     who watches what, with timestamps
   6 Rollback        explicit steps to restore the original topology and traffic
   7 Success         evidence that counts as proof
   ```
   Expect: a plan agreed by the DBA, application owner and technical lead before the test starts.

3. Declare the error envelope before touching anything.
   ```text
   Abort if customer-facing error rate > 2% for > 60 seconds
   Abort if p99 read latency > 1500 ms for > 2 minutes
   Abort before triggering if oplog lag on the failover target > 30 seconds
   Abort if steady state is not reached within 20 minutes of the trigger
   ```
   Expect: written thresholds. The numbers above are the corpus examples; set your own, but write them down first so nobody debates mid-test whether to abort.

4. Prepare the application and the connection string.
   ```text
   retryWrites=true
   retryReads=true
   serverSelectionTimeoutMS=30000
   connectTimeoutMS=10000
   socketTimeoutMS=0
   ```
   Expect: SRV-style connection string on a current driver. The corpus explains that elections can take 10-30 seconds in the worst case and a 3000 ms server-selection timeout makes the driver give up before a primary exists.

5. Capture the steady-state baseline (at least 15 minutes) and start the load generator.
   ```javascript
   // mongosh
   rs.status()
   rs.printSecondaryReplicationInfo()
   ```
   Expect: all members healthy, secondaries with small lag, and baseline numbers for error rate, p99 latency and write throughput recorded with timestamps.

6. Check the pre-flight gate and confirm the target is NOT production (unless the window is approved).
   ```bash
   atlas clusters describe <cluster-name> --projectId <project-id>
   ```
   Expect: the cluster name and project id match the explicit non-prod allowlist in the plan. The corpus recommends tagging test clusters and refusing to run destructive calls unless the tag matches. Verify in the current MongoDB docs: the exact output fields of this command.

7. Trigger the failure.
   ```bash
   # Atlas: shuts down the current primary and forces an election
   atlas clusters failover <cluster-name> --projectId <project-id>

   # Self-managed: step the primary down and allow an election (default 60 s step-down period)
   mongosh "<connection-string>" --eval 'rs.stepDown()'
   ```
   Expect: the old primary becomes a secondary, an election runs (typically about 5 seconds under normal conditions, up to 10-30 seconds worst case), and the secondary with the most complete oplog wins. The old primary rejoins and resyncs. In the Atlas UI the same action is Cluster, then Test Resilience, then Primary Failover, then Restart Primary. Note the exact trigger time in UTC.

8. Observe and record while the load generator keeps writing.
   ```javascript
   rs.status().members.map(m => ({ name: m.name, state: m.stateStr }))
   ```
   Expect: a timeline with timestamps for: trigger, first application error, new primary elected, last application error, error rate back to baseline, latency back to baseline. Watch whether writes with `w:majority` block and retry instead of failing, whether the driver reconnects without application errors, and whether a reconnect burst (thundering herd) re-saturates the cluster.

9. Evaluate the abort conditions continuously. If the envelope is breached, stop and roll back.
   ```text
   Rollback: stop injecting faults, let the replica set re-stabilize, restore original priorities and traffic routing per the plan.
   ```
   Expect: a deterministic decision. Do not run `rs.reconfig` or forced reconfiguration while auto-failover is in progress; let it finish.

10. For a regional-outage rehearsal, extend the test beyond a single primary failover.
    ```text
    Verify in the current MongoDB docs: the Atlas "Simulate Regional Outage" tutorial and the "Reconfigure a Replica Set During a Regional Outage" procedure.
    ```
    Expect: you understand which topologies survive a region loss. A replica set needs a majority of voting members online, so surviving one full region requires members in at least three regions; a 2+1 two-region split loses quorum if the larger region fails.

11. Run the post-test checks (see Verify), then write up the results (checklist below).

## Verify
```javascript
rs.status()                              // one PRIMARY, all other members SECONDARY
rs.printSecondaryReplicationInfo()       // lag back to normal
db.getSiblingDB('app').orders.countDocuments({ _id: { $gte: <first-test-id> } })  // compare with writes the load generator acknowledged
```
Expect:
- Every write the load generator saw acknowledged with `w:majority` exists after the failover. Writes acknowledged with a weaker concern (such as `w:1`) can be rolled back when the old primary rejoins; quantify any rollback and note it as measured RPO.
- Application health checks pass, error rate and p99 latency are back within steady-state bounds, and connection pools recovered without restarting the application. A cold cache after election may be slower for 30-60 seconds; that is normal.
- Measured RTO and RPO are compared to the targets from Step 1. The gap between paper and measured numbers is itself an action item.

Write-up checklist:
- [ ] Hypothesis, and whether it was confirmed.
- [ ] Envelope and whether it was breached.
- [ ] Timeline with UTC timestamps (trigger to recovery).
- [ ] Measured RTO and RPO versus targets; app-tier contribution separated from database contribution.
- [ ] What worked, what did not, contributing factors, written blamelessly.
- [ ] Action items with owners and due dates, tracked like P1 work.
- [ ] A concrete edit to the runbook (if no edit is needed, the runbook is suspect).
- [ ] Next test date. Corpus cadence: Tier-0 at least twice a year, Tier-1 annually with quarterly restore verification, Tier-2 annual restore verification plus a paper drill.

## Rollback / abort
- Abort when any envelope condition is breached, the cluster fails the pre-flight checks, or the decision authority calls it.
- Stop adding load and fault injection, then measure recovery time and completeness (secondaries caught up, queues drained, pools recovered).
- Do not use forced reconfiguration to "speed up" recovery. The corpus warns that forced reconfiguration can roll back committed writes, and must be approved by the decision authority.
- If the test uncovered logical damage, fall back to the restore recipes (snapshot or point-in-time).

## Pitfalls
- Treating HA as DR. Failover protects against node loss, not logical corruption or provider-wide events; layer backups under it.
- Quoting near-zero RTO/RPO without the app tier: the database fails over in seconds while the application takes minutes to find it.
- No pre-declared abort criteria; the team argues during the test.
- Testing an idle cluster. A fault under no load is an easier scenario than the same fault under peak writes.
- Short `serverSelectionTimeoutMS` (for example 3000 ms) producing false application failures during the election.
- Only the database in scope: skip DNS, connection-string rotation, retry logic and cache warm-up and the result is meaningless.
- Scheduling the test and never running it, or leaving the runbook unedited for a year or more.
- Encryption keys available only in the lost region. Test key availability together with the data.
- Pointing destructive calls at the wrong project. Verify cluster and project ids against an allowlist first.
- Treating a stepDown as a regional outage. It only tests primary election, not region loss or provider events.

## Sources
- `skills/mongodb-operations-expert/references/mongodb-disaster-recovery.md:157-208` RTO/RPO definitions, reference table, measurement method, common mistakes.
- `skills/mongodb-operations-expert/references/mongodb-disaster-recovery.md:212-224` quorum and three-region rule.
- `skills/mongodb-operations-expert/references/mongodb-disaster-recovery.md:344-401` failover testing, error envelope, test plan structure, cadence.
- `skills/mongodb-operations-expert/references/mongodb-disaster-recovery.md:501-513` forced reconfiguration and rollback risk.
- `skills/mongodb-operations-expert/references/mongodb-disaster-recovery.md:588-599` post-event review and runbook update.
- `skills/mongodb-operations-expert/references/mongodb-disaster-recovery.md:613-630` anti-patterns.
- `skills/atlas-diagnostics-expert/references/mongodb-stress-and-resilience-testing.md:295-321` Atlas Test Failover behavior, prerequisites, invocation surfaces, tier limits, retryable writes.
- `skills/atlas-diagnostics-expert/references/mongodb-stress-and-resilience-testing.md:382-392` thundering-herd check.
- `skills/atlas-diagnostics-expert/references/mongodb-stress-and-resilience-testing.md:419-437` guardrails against targeting production, required roles, pre-flight gate.
- `skills/atlas-diagnostics-expert/references/mongodb-monitoring-observability.md:820-838` recommended connection string options and election timing.
- `skills/mongodb-expert/references/mongodb-replication.md:686-696` `rs.stepDown()` semantics.
- `skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:277-281` retry semantics and why a clean stepDown is preferred over killing the process.
