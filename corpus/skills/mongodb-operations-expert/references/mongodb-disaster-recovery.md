<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-disaster-recovery` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-disaster-recovery
title: MongoDB Disaster Recovery Expert
version: "1.1.0"
last-updated: "2026-05-29"
category: mongodb
description: >
  MongoDB Atlas and self-managed disaster recovery — RTO/RPO modeling and calculation,
  multi-region replica set topology (electable nodes, election priorities, latency
  tradeoffs), Atlas Global Clusters with zone sharding for geo-resilient DR,
  backup-based DR as worst-case fallback, Point-in-Time Restore (PITR) with continuous
  cloud backup, cross-region snapshot copy schedules and their RPO impact, AWS region
  outage scenarios (me-central-1 / me-south-1 case study, customer migration patterns,
  rs.reconfigForPSASet during outages), failover testing methodology (Error Envelope
  concept from a customer PFT, chaos engineering for DR validation), DR runbook
  structure (pre-event checklist, mid-event decision tree, post-event blameless
  postmortem), and DR anti-patterns (single-region production, untested failover,
  missing backup verification, weak decision authority, single-region snapshot copies).
  TRIGGER: designing or reviewing DR strategy for a MongoDB workload, sizing RTO/RPO,
  configuring Atlas continuous backup or cross-region snapshot copy, responding to a
  regional outage, authoring or auditing a DR runbook, planning a failover test or
  Error Envelope, conducting a DR postmortem, or spotting DR anti-patterns in a
  customer deployment. SKIP: routine replica-set tuning without a DR framing (use
  mongodb-replication), generic backup-restore mechanics without DR planning (use
  mongodb-backup-restore), full-incident response process beyond the database
  (use incident-response), or sharding mechanics unrelated to Global-Cluster DR
  (use mongodb-sharding).
tags:
  - mongodb
  - mongodb-atlas
  - disaster-recovery
  - business-continuity
  - high-availability
  - replication
  - backup-restore
  - aws
  - failover
  - chaos-engineering
keywords:
  - mongodb-disaster-recovery
  - RTO
  - RPO
  - failover testing
  - cross-region snapshot
  - PITR
  - Global Clusters
  - regional outage
  - rs.reconfigForPSASet
  - Error Envelope
  - blameless postmortem
  - customer PFT
  - decision authority
  - DR runbook
  - chaos engineering
  - continuous cloud backup
whenToUse:
  - Designing or reviewing a MongoDB DR strategy for a customer account
  - Calculating realistic RTO/RPO targets for a tiered application
  - Choosing between multi-region replica set vs Global Cluster vs warm-standby restore
  - Configuring Atlas cross-region snapshot copy and continuous cloud backup
  - Responding to an AWS regional outage that affects an Atlas customer
  - Writing or auditing a DR runbook (pre-event / mid-event / post-event)
  - Planning a customer failover test using the Error Envelope methodology
  - Conducting a blameless postmortem after a DR exercise or real failover
  - Spotting DR anti-patterns in a customer's deployment (single-region, untested, etc.)
  - Scoring a customer's DR readiness using the five-question gut check
whenNotToUse:
  - Routine replica-set topology tuning without a DR framing — use mongodb-replication
  - Generic backup-restore mechanics (mongodump, mongorestore, snapshot schedule) without DR planning — use mongodb-backup-restore
  - Full incident response process beyond the database layer — use incident-response
  - Sharding mechanics unrelated to Global-Cluster DR — use mongodb-sharding
  - Atlas cost optimization or billing questions — use mongodb-cost-optimization
related_skills:
  - mongodb-replication
  - mongodb-backup-restore
  - mongodb-sharding
  - mongodb-atlas-expert
  - mongodb-aws-networking
  - incident-response
  - tam-reference
  - tam-expertise
---

# MongoDB Disaster Recovery Expert

This skill captures the patterns, vocabulary, and decision frameworks needed to
design, operate, test, and recover MongoDB deployments under regional or platform
failure. It is biased toward MongoDB Atlas (the Premium Services TAM operating
surface) but the underlying replica-set and DR theory applies to self-managed
clusters as well.

## TL;DR — operational summary

- **DR strategy ladder (cheapest → most resilient):** single-region backups → 
  cross-region snapshot copy → multi-region replica set → multi-region replica 
  set with continuous PITR → Atlas Global Cluster across regions.
- **For Tier-0 workloads:** 3-region replica set + `w:majority` + Continuous 
  Cloud Backup + cross-region snapshot copy with PITR enabled.
- **RPO floors:** ~0 with `w:majority` multi-region; ~1 min with PITR; 
  snapshot-interval + 15–60 min for cross-region copy without PITR.
- **RTO floors:** seconds for auto-failover; <15 min for optimized PITR 
  restore; minutes-to-hours for snapshot restore.
- **The five questions** that test customer readiness: documented RTO/RPO, last 
  failover test, last restore test, named decision authority, runbook last 
  edit. See §11.2.
- **In a live outage:** if auto-failover is running, do not reconfig — let it 
  finish. If quorum is lost, the named decision authority chooses between 
  waiting and `rs.reconfigForPSASet` / Atlas regional-outage reconfig.

## Output contract

When this skill activates, the agent should deliver one of these artifact 
types, named explicitly in the response:

| Artifact | Structure |
| --- | --- |
| **DR design recommendation** | (1) workload tier, (2) RTO/RPO target, (3) recommended topology with rationale, (4) backup config, (5) cost-vs-resilience trade-off, (6) test cadence |
| **DR posture audit** | Five-question checklist filled out, anti-pattern table marked, top-3 gaps with severity, action items with owners |
| **Outage response plan** | Scope assessment, decision-tree branch selected, named owner per step, comms cadence, rollback procedure, success criteria |
| **Runbook draft** | Pre-event checklist, mid-event decision tree (§9.2 shape), post-event review schedule, decision-authority matrix, comms tree |
| **Failover-test plan** | Hypothesis, steady-state metrics, Error Envelope, injection method, observation plan, rollback, success criteria (§5.3 shape) |
| **Postmortem skeleton** | Timeline, contributing factors, what worked, what did not, action items with owners and due dates, runbook edit list |

If the user request does not clearly map to one of these, ask which artifact 
they want before producing prose.

## Escalation and hand-off rules

The agent should **stop and request explicit human authorization** before 
recommending any of the following — these are not autonomous decisions:

- Authorizing a **production restore** (logical-corruption recovery, 
  ransomware response, or any restore that overwrites live state).
- Triggering a **production failover** outside an agreed test window.
- Running `rs.reconfigForPSASet` or any forced replica-set reconfig that may 
  roll back committed writes.
- Cancelling or aborting an active DR test mid-run if the Error Envelope is 
  ambiguous.
- Committing the customer to a permanent region migration during an active 
  outage.

For any of these, output the recommendation and the named decision authority 
who must approve. Do not assume approval from prior context.

---

## 1. RTO / RPO modeling

### 1.1 Definitions

- **RTO (Recovery Time Objective)** — the maximum amount of time the workload
  can be down before the business takes unacceptable damage. Measured from the
  moment the outage is detected to the moment the workload is verified healthy
  on the replacement topology.
- **RPO (Recovery Point Objective)** — the maximum amount of data loss the
  business can tolerate, expressed as a time interval (e.g. "5 minutes of
  writes"). RPO=0 implies synchronous replication of every committed write to
  every recovery target. RPO measured against the most recent durable state on
  the recovered cluster.

### 1.2 Atlas reference numbers (May 2026)

| Configuration | Typical RTO | Typical RPO |
| --- | --- | --- |
| Single-region 3-node replica set, single AZ failure | seconds (auto-failover) | ~0 (majority writes) |
| Multi-region 3+ region replica set, primary-region loss | seconds to ~1 min | ~0 if w:majority |
| Global Cluster, zone failure | seconds (per-shard failover) | ~0 for the affected zone |
| Continuous Cloud Backup PITR restore | <15 min (optimized restore) | ~1 min within PITR window |
| Snapshot restore from same region | minutes to hours (size-dependent) | bound by snapshot interval (e.g. 6h, 24h) |
| Cross-region snapshot restore | minutes to hours + inter-region transfer | snapshot interval + 15-60 min copy lag |

These are *MongoDB-side* targets only. End-to-end customer RTO must add DNS
propagation, app-tier failover, connection-string rotation, cache warm-up, and
human decision time.

### 1.3 Calculation methodology

For every Tier-0 / Tier-1 application:

1. **Inventory the dependencies** — database, app servers, queues, caches, DNS,
   identity, secrets store. The recovery objective is bounded by the slowest
   component.
2. **Convert business impact into time** — cost of downtime per hour and cost
   per record of data loss. This produces *defensible* RTO/RPO, not aspirational
   ones.
3. **Map the chosen DR strategy** to expected RTO/RPO (see table above).
4. **Validate with a measured test** — actual RTO/RPO comes from a real failover
   exercise, never from a vendor datasheet. The gap between paper and measured
   numbers is itself an action item.
5. **Re-measure on every major change** — index rebuild, schema migration,
   cluster tier change, region addition. Each invalidates prior test data.

### 1.4 Common mistakes

- Quoting Atlas's "near-zero" RTO/RPO without accounting for the app tier.
- Treating the snapshot interval as RPO when continuous backup is not enabled.
- Assuming PITR window covers the disaster window — it does not if the
  disaster pre-dates the window's start.

---

## 2. Multi-region replica sets

### 2.1 Topology fundamentals

- A replica set needs a **majority of voting members** online to elect or
  retain a primary. For a 3-node set, that is 2 nodes; for 5-node, 3; for
  7-node, 4.
- To survive a full regional outage, members must be distributed across **at
  least three regions**, so that the loss of one region still leaves a
  majority.
- A two-region split (e.g. 2+1 or 3+2) cannot survive the loss of the larger
  region while preserving write availability.

### 2.2 Election priorities

- Each member has a `priority` between 0 and 1000 (default 1). Higher priority
  members call elections sooner and are more likely to win.
- `priority: 0` members can never become primary but still replicate, serve
  reads, and vote. Useful for analytics nodes or DR-only members where
  failover into that region is undesirable.
- The "preferred primary region" pattern: assign priority 7 (or higher) to the
  members in the primary region and priority 1 (or lower) to members in the DR
  regions. Atlas exposes this as the "Preferred" region in the UI.
- Median election time should be under ~12 seconds with default settings. If
  it is longer in your environment, investigate `heartbeatTimeoutSecs`,
  `electionTimeoutMillis`, and network jitter between regions.

### 2.3 Latency trade-offs

- `w:majority` writes wait for acknowledgment from a majority of *data-bearing
  voting members*. If the majority spans regions, the write incurs at least
  one inter-region round trip.
- Atlas's `j:true` adds journal-flush latency on each acknowledging member.
- Co-locating the application with the primary region minimizes write latency
  but concentrates risk; co-locating with a DR region inverts the problem.
- Read preference `nearest` plus `readConcern: majority` lets you absorb read
  latency locally while maintaining strong write guarantees globally.

### 2.4 Election priority recipes

- **Preferred-region active-passive:** 3 voting members in primary region at
  priority 7, 2 voting members in DR region at priority 1. Survives one
  member loss; loses write availability if the whole primary region drops
  (manual reconfig required).
- **Three-region symmetric:** 1 or 2 members in each of 3 regions, all at
  equal priority. Survives the loss of one full region with automatic
  failover. This is the default Atlas recommendation for Tier-0.
- **Read-only DR replica:** add a `priority:0, hidden:true` member in a
  fourth region used only for snapshots or analytics. Does not contribute to
  HA but bounds RPO if the primary regions go away.

---

## 3. Atlas Global Clusters (zone sharding)

### 3.1 What they are

Global Clusters use **zone sharding** to pin documents to a geographic
location based on a `location` field embedded in the shard key. Each zone is
itself a multi-region-aware replica set, so each zone has its own
primary, its own electable members, and its own failover behavior.

### 3.2 DR characteristics

- Per-zone failover means a regional outage in one zone does **not** require
  failover of the other zones. The blast radius is the affected zone only.
- Reads and writes for documents bound to a healthy zone continue without
  interruption during another zone's outage.
- Documents pinned to the affected zone become unavailable until that zone's
  replica set recovers — which means **zone selection is itself a DR
  decision**, not just a latency one.

### 3.3 When Global Clusters are the right answer

- The dataset is naturally partitionable by geography (per-country user
  accounts, per-region game shards, per-continent IoT telemetry).
- Regulatory residency requires hard pinning of data to a jurisdiction.
- The customer wants low local-read latency *and* survives losing remote
  data during a regional outage.

### 3.4 When they are the wrong answer

- The dataset has no natural geographic key.
- The customer expects full availability of the *entire* dataset during a
  regional outage — that is a multi-region replica set requirement, not a
  Global Cluster one.
- Cross-zone queries (no `location` in the predicate) fan out to every zone
  and lose the benefit.

---

## 4. Backup-based DR (worst-case fallback)

### 4.1 Why it still matters

Even with multi-region replica sets, snapshot restore is the floor of any DR
strategy. It is the answer to:

- Logical corruption — a bad migration or DELETE that replicated everywhere.
- Ransomware or credential compromise — the bad actor can mutate every
  replica, so replication alone is not protection.
- Provider-wide outage — multi-AZ and multi-region within one cloud do not
  protect against a control-plane incident affecting the whole provider.

### 4.2 RTO implications

- Atlas snapshot restore time scales with cluster size; large clusters can
  exceed one hour even within the same region.
- Cross-region restore adds inter-region transfer time. For multi-TB clusters
  this can be hours.
- A "snapshot restore" RTO target is honest only after a measured restore on
  a same-shape test cluster.

### 4.3 Restore mechanics

- **Same-region snapshot restore** — fastest. Source snapshot and target
  cluster live in the same region.
- **Cross-region restore from a copied snapshot** — slower, but the only
  option if the primary region is gone.
- **Automated restore** vs **download restore** — the Atlas API will provision
  a new cluster from a snapshot, while the download path is for hand-managed
  restores into self-managed clusters or for forensic snapshots.

### 4.4 Verification

A backup that has never been restored is not a backup. Every restore policy
must include a scheduled verification restore on a non-production cluster,
followed by data-integrity queries documented in the runbook. The cadence
should be at least quarterly for Tier-0 workloads.

---

## 5. Failover testing (Error Envelope methodology)

### 5.1 Why testing is non-optional

The actual RTO/RPO a customer can defend in a steering committee is the one
measured in the last test, not the one the architecture diagram implies.
Untested DR is theatre.

### 5.2 The "Error Envelope" concept

The Error Envelope (popularized by the a customer's Production Failover Test
playbook in 2025) is the *pre-declared* set of conditions under which the test
is allowed to continue running. It typically includes:

- **Hard error ceiling** — e.g. "if customer-facing error rate exceeds 2% for
  more than 60 seconds, abort the test and roll back."
- **Latency ceiling** — e.g. "if p99 read latency exceeds 1500 ms for more
  than 2 minutes, abort."
- **Replication-lag floor** — e.g. "if oplog lag on the failover target
  exceeds 30 seconds, abort before triggering the cutover."
- **Time box** — e.g. "if the test has not reached steady state within 20
  minutes of trigger, abort."

The envelope is agreed in writing between the customer's DBA, app owner, and
TAM *before* the test starts. Anything inside the envelope is acceptable
test noise; anything outside is grounds for immediate rollback. This pre-
declaration eliminates mid-event debate about whether the test is "still
going well" and converts the failover into an experiment with a deterministic
abort criterion.

### 5.3 Test plan structure

1. **Hypothesis** — one sentence describing what the test will prove. Example:
   "If the eu-west-1 primary region becomes unavailable, the
   shopping-cart-write API recovers within 90 seconds with no more than 5
   seconds of lost writes."
2. **Steady-state metrics** — the dashboards / queries that prove "normal."
3. **Error envelope** — the abort conditions above.
4. **Injection method** — Atlas API "test failover," explicit region disable,
   AWS Fault Injection Simulator, chaos tooling, or a managed real failover.
5. **Observation plan** — who is watching which dashboard, with timestamps.
6. **Rollback procedure** — explicit steps to restore the original topology.
7. **Success criteria** — what evidence is acceptable as proof.

### 5.4 Chaos-engineering parallel

The chaos engineering loop (steady state → hypothesis → inject → observe →
improve) maps directly onto DR testing. Chaos tooling like AWS FIS, Gremlin,
or LitmusChaos can automate the injection step; the human work is in the
hypothesis, envelope, and observation. Treat each DR test as a chaos
experiment run against a real system with a real abort gate.

### 5.5 Cadence

- **Tier-0 workloads:** full multi-region failover at least twice per year,
  plus continuous in-region instance kills.
- **Tier-1:** annual failover, with quarterly snapshot-restore verification.
- **Tier-2:** annual snapshot-restore verification, paper drill for failover.

---

## 6. Point-in-Time Restore (PITR) for DR

### 6.1 PITR vs full DR

PITR is **logical-corruption insurance**, not **regional-outage insurance**.
It answers "the migration at 14:32 corrupted half the orders collection — get
me to 14:31." It does not answer "the primary region is offline for two
days."

### 6.2 How PITR works in Atlas

- Continuous Cloud Backup retains the oplog alongside scheduled snapshots
  inside the PITR window.
- A PITR restore selects the most recent snapshot before the target
  timestamp, then replays oplog entries forward to that exact timestamp.
- Tighter snapshot intervals shorten the oplog replay step and therefore the
  restore RTO.
- PITR RPO is as low as **one minute** within the window.

### 6.3 PITR window sizing

- Choose the window based on the worst-case time-to-detect for a logical
  corruption. If your data-integrity alarms might take 36 hours to trip, the
  window must exceed 36 hours.
- Longer windows cost more — the oplog and snapshot retention storage scales
  with the window.

### 6.4 PITR and cross-region

Setting "Point-in-Time Restore" to On for a snapshot copy policy item also
copies the oplog to the copy region, enabling PITR from the secondary region
during a primary-region outage. Without this, the secondary region can only
restore to discrete snapshot points.

---

## 7. Cross-region snapshot copy

### 7.1 What it is

Atlas can asynchronously copy snapshots (and optionally oplogs) from the
cluster's primary region to one or more additional regions. The copy is
schedule-driven: you choose which snapshot frequencies (hourly, daily,
weekly, monthly) get copied, and to which target region.

### 7.2 Copy lag and RPO impact

- Copy lag is typically **15-60 minutes** after the primary snapshot
  completes.
- Effective RPO from the copy region = primary snapshot interval + copy lag,
  unless cross-region PITR is enabled, in which case RPO drops back to the
  PITR floor (~1 minute).
- A daily-only copy policy yields an effective RPO measured in days from the
  copy region — almost always wrong for a Tier-0 workload.

### 7.3 Cost vs RPO trade-off

Each copy frequency increases storage and inter-region transfer cost. A
defensible policy:

- **Hourly + daily copies** to the same cloud, different region — primary DR.
- **Weekly copies** to a different cloud provider or distant region — black-
  swan protection (provider-wide event).
- **Monthly copies** retained for a year — compliance and ransomware recovery.

### 7.4 Operational warnings

- The copy region is **not** a replica — you cannot point an app at it
  without first restoring a new cluster from a copied snapshot.
- The copy region must be supported by the cluster's cloud provider; some
  cross-cloud combinations have throughput limits.

---

## 8. AWS region outage scenarios

### 8.1 The me-central-1 / me-south-1 case (March 2026)

In March 2026, a localized power event in AWS me-central-1 (UAE) and damage
in me-south-1 (Bahrain) left two AZs in me-central-1 significantly impaired
and me-south-1 workloads unable to migrate, backup, or restore. AWS estimated
"several months" to full recovery.

MongoDB Atlas presented affected customers three options:

1. **Move the cluster** to an unaffected region (most disruptive, most
   defensible).
2. **Add electable nodes** in an unaffected region to re-establish a viable
   majority and restore write availability.
3. **Wait** for AWS to recover the AZs (only acceptable for non-critical
   workloads).

MongoDB **strongly recommended option 1 or 2** rather than waiting. This is
the same recommendation TAMs should default to in any "extended region
event."

### 8.2 Recovery toolkit

- `rs.reconfigForPSASet()` — safely reconfigures a replica set into a
  primary-secondary-arbiter topology in two steps that avoid rolling back
  committed writes. Used when you must rebuild quorum after losing voting
  members.
- **Atlas UI "reconfigure replica set during regional outage"** — guided flow
  that excludes affected regions from the new topology. Documented at
  https://www.mongodb.com/docs/atlas/reconfigure-replica-set-during-regional-outage/.
- **Manual reconfig caveat:** if you reconfigure before all writes have
  replicated, writes on the dropped nodes may roll back when those nodes
  return. Always check `rs.printSecondaryReplicationInfo()` before forcing a
  reconfig.

### 8.3 Customer migration patterns

For a customer hit by a regional event:

1. **Stop the bleeding** — pause non-critical writes, fail the app over to a
   read-only mode if necessary.
2. **Re-establish quorum** — add electable nodes in unaffected regions; the
   majority will elect a new primary automatically.
3. **Restore write path** — point the app at the new primary; rotate any
   region-pinned connection strings.
4. **Plan the long-term move** — if the AWS region will be out for weeks,
   schedule a permanent move of the cluster to a new region during a
   maintenance window.
5. **Audit blast radius** — any downstream service that hard-coded the old
   region (analytics, BI exports, cross-cloud mirrors) must also be updated.

---

## 9. DR runbook structure

### 9.1 Pre-event checklist

Reviewed and signed off **before** the runbook is considered live:

- [ ] Inventory of every Tier-0 / Tier-1 cluster, with documented RTO/RPO.
- [ ] Confirmed multi-region or multi-AZ topology for every Tier-0 cluster.
- [ ] Continuous Cloud Backup enabled, PITR window sized to detect-time.
- [ ] Cross-region snapshot copy configured to a region likely to survive
      the primary region's worst-case event.
- [ ] Snapshot retention verified against compliance window.
- [ ] Backup-restore verification test completed within the last quarter.
- [ ] Failover test completed within the last 6 months for Tier-0.
- [ ] Decision-authority matrix written and acknowledged: who authorizes a
      production restore, a region cutover, a forced reconfig.
- [ ] Communication tree: paging chain, status-page owner, customer-comms
      template, exec-update template.
- [ ] App-tier readiness: connection-string rotation tested, retry-with-
      backoff verified, circuit breakers configured.
- [ ] Out-of-band access: at least two operators with break-glass admin
      credentials in a separate identity provider.

### 9.2 Mid-event decision tree

```
Incident detected
  │
  ▼
Is the cluster's write path healthy?
  ├── Yes → monitor; do not act
  └── No
       │
       ▼
Is this a single-node / single-AZ event?
  ├── Yes → let auto-failover complete; verify; do not reconfig
  └── No
       │
       ▼
Is the affected region likely to recover within RTO?
  ├── Yes → wait; communicate; pre-stage cross-region restore
  └── No
       │
       ▼
Are unaffected regions reachable and healthy?
  ├── Yes → reconfigure replica set excluding affected regions
  │        (Atlas UI flow OR rs.reconfigForPSASet for self-managed)
  └── No  → declare provider-wide event; restore from
            cross-region snapshot copy into a fresh cluster
            in a different provider/region
```

Each branch in the tree must name the decision authority and the maximum
time the operator may spend in that branch before escalating.

### 9.3 Post-event review

- **Timeline reconstruction** within 24 hours — what happened, what we did,
  what time each thing happened.
- **Blameless postmortem** within 5 business days — root cause(s),
  contributing factors, what worked, what did not, action items with owners
  and due dates.
- **Action item review cadence** — postmortem actions are tracked like
  P1 work, with a named owner and a due date. Stale action items invalidate
  the postmortem.
- **Runbook update** — every postmortem must produce a concrete edit to the
  runbook. If no edit is needed, the runbook is suspect.

### 9.4 Communication discipline

- One source of truth (status page) updated at agreed intervals (e.g. every
  30 minutes during an active event).
- Executive updates use a different cadence and template than operator
  updates — do not flood execs with packet-level detail.
- Customer-facing language is reviewed by the comms lead before publication.
- Internal Slack channels are read-only during the event except for the
  incident commander and named operators.

---

## 10. DR anti-patterns

| Anti-pattern | Why it fails | Fix |
| --- | --- | --- |
| Single-region production for a Tier-0 workload | One regional event = full outage with no automatic recovery path | Multi-region replica set or Global Cluster across at least 3 regions |
| Two-region split (e.g. 2+1) | Loss of the larger region loses quorum; no automatic failover | Move to 3-region symmetric, or add a tie-breaker member in a third region |
| No documented RTO/RPO | DR design is aspirational; the team argues during the event | Inventory every Tier-0 app, document objectives, validate by test |
| Backups never restored | "Backup" that has never been restored is unproven storage cost | Quarterly verification restores on a test cluster, scripted and timed |
| PITR window shorter than detect-time | Logical corruption discovered after the window expires; no recovery | Size the window to worst-case detection latency, not vendor default |
| Cross-region copy of weekly snapshots only | Effective DR RPO measured in days | Copy hourly + daily to a real DR region; reserve weekly/monthly for compliance |
| Single-region cross-region snapshot copy | Copy lives next door to the original; one wide event takes both | Copy across an actual fault domain (different region group or cloud) |
| Failover test scheduled but never run | "Tested annually" on paper, never actually exercised | Calendar the test as a real change; treat skipped tests as P1 risk |
| No Error Envelope on failover tests | Mid-event debate about whether to abort; test runs too long, real impact | Pre-declare abort criteria in writing; rehearse the rollback first |
| Decision authority undefined | The on-call escalates twice before anyone says "yes, restore prod" | Decision matrix signed off; on-call has explicit pre-authorization for tier-0 actions |
| App tier not in the test | Database fails over in 30 seconds; app takes 20 minutes to find it | Include connection-string rotation, retry logic, and cache warm-up in every test |
| Runbook last edited 18 months ago | Steps reference deprecated UI, retired tooling, ex-employees | Runbook is updated after every test and every postmortem; stale runbook = audit finding |
| Encryption key kept only in the lost region | The data restores fine, but no key to decrypt it | KMS keys replicated to the DR region; key-availability tested with the data |
| Treat HA as DR | Auto-failover protects against a node loss, not against logical corruption or provider-wide events | Layer backup-based DR underneath replication; never rely on one mechanism |

---

## 11. Quick decision frames

### 11.1 "What DR strategy do I recommend?"

| Customer profile | Recommendation |
| --- | --- |
| Tier-0 global app, RTO < 1 min, RPO ~0 | Multi-region 3+ region replica set, w:majority, cross-region snapshot copy + continuous PITR |
| Tier-0 geo-partitioned (per-country) | Atlas Global Cluster, zone per geography, per-zone multi-region replica sets |
| Tier-1 regional app, RTO ~15 min, RPO ~5 min | Multi-region replica set within one cloud, continuous PITR enabled, cross-region snapshot copy |
| Tier-2 internal tool, RTO ~hours, RPO ~24h | Single-region cluster + daily snapshot copy to a second region |
| Dev / non-prod | Single-region, default backups, no PITR |

### 11.2 "Are they actually ready?"

Five-question gut check for any account:

1. What is your documented RTO and RPO for this workload?
2. When was your last successful failover test?
3. When was your last successful restore test?
4. If your primary region is unavailable, who authorizes a cutover and how long do they have to decide?
5. Show me the runbook — when was it last edited?

If any answer is "we don't know," "more than a year ago," or "we don't have one," the account has a DR gap that should be on the engagement plan.

### 11.3 "We're in the middle of an event — what now?"

1. Confirm scope: single node, AZ, region, provider, or app.
2. Check the Atlas status page and AWS Service Health Dashboard.
3. If auto-failover is in progress, **do not** reconfig — let it finish.
4. If quorum is lost, decide between waiting and reconfiguring; the decision is owned by the named decision authority, not the on-call.
5. Communicate at the agreed cadence; do not let comms gaps invite escalation.
6. After the dust settles, schedule the postmortem within 24 hours.

---

## 12. Worked example — applying the framework end-to-end

**Scenario:** Tier-0 fintech customer running a 5-node Atlas replica set in
AWS us-east-1 across three AZs. M60 cluster, ~3 TB, daily snapshots, no
cross-region copy, no continuous backup. Customer asks for a DR review ahead
of a regulator audit.

**Step 1 — RTO/RPO discovery (§1).**
Customer states: "RTO 30 minutes, RPO 5 minutes." Convert to design
constraints: RTO 30 min eliminates same-region snapshot restore as the
primary mechanism (3 TB restore alone will exceed it); RPO 5 min eliminates
daily snapshots as the floor.

**Step 2 — Posture audit (§11.2 five questions).**
1. Documented RTO/RPO — yes, just stated.
2. Last failover test — never.
3. Last restore test — never.
4. Decision authority — undefined; on-call escalates to "the architect."
5. Runbook last edit — 14 months ago, references retired tooling.

Four of five answers are red flags. Posture is well below target.

**Step 3 — Anti-pattern scan (§10).**
- Single-region production for Tier-0 — yes, all 5 nodes in us-east-1.
- Backups never restored — yes.
- Failover scheduled but never run — yes.
- Decision authority undefined — yes.
- Runbook stale — yes.

Five anti-patterns active simultaneously. The cluster is a regulator finding
waiting to be written.

**Step 4 — Strategy recommendation (§11.1).**
Tier-0 with 30-min RTO and 5-min RPO maps to: multi-region replica set,
continuous PITR, cross-region snapshot copy. Specifically:

- Add 2 electable nodes in us-west-2; reshape to a 5-region-aware topology
  with priorities biased toward us-east-1 as preferred primary.
- Enable Continuous Cloud Backup, PITR window 7 days (covers worst-case
  weekend detection lag).
- Configure cross-region snapshot copy with PITR enabled to us-west-2,
  hourly + daily frequencies copied.
- Keep weekly snapshot copy to a distant region (e.g. eu-west-1) for
  black-swan protection.

**Step 5 — Test plan (§5.3) and Error Envelope (§5.2).**

- Hypothesis: "If us-east-1 primary fails, the order-write API recovers
  within 90 s with no more than 5 s of lost writes."
- Error envelope: abort if customer-facing error rate >2% for >60 s, p99
  >1500 ms for >2 min, or oplog lag on us-west-2 >30 s before trigger.
- Injection: Atlas test-failover API.
- Cadence: twice yearly for Tier-0.

**Step 6 — Runbook update (§9).**
Refresh decision authority matrix (named human, named deputy, max decision
time per branch). Rewrite mid-event decision tree per §9.2. Add postmortem
template per §9.3.

**Step 7 — Output.**
Deliver a **DR posture audit** artifact (per Output contract table) with:
five-question scorecard, anti-pattern matrix, top-3 gaps ranked by severity,
proposed topology diagram, projected RTO/RPO under the new design, and
action items with owners and due dates. Flag for human authorization: the
permanent topology change and the first scheduled failover test.

---

## See also (sibling skills)

- **mongodb-replication** — replica-set internals, election mechanics,
  read/write concern, oplog sizing. Use when the question is replica-set
  tuning without a DR framing.
- **mongodb-backup-restore** — backup tooling, snapshot mechanics, restore
  procedures at the command level. Use when the question is "how do I run
  this backup," not "what is my DR strategy."
- **mongodb-sharding** — shard architecture and zone configuration. Use when
  the question is sharding mechanics; this skill covers Global-Cluster DR
  specifically.
- **mongodb-atlas-expert** — broad Atlas surface (orgs, projects, billing,
  configuration). Use for non-DR Atlas questions.
- **mongodb-aws-networking** — VPC peering, PrivateLink, cross-region
  networking. Use when the DR design hinges on network topology.
- **incident-response** — incident lifecycle (severity, IC, comms templates,
  postmortems) generic to any system. Use for incident-process questions
  beyond the database.
- **tam-reference** / **tam-expertise** — TAM operating model, account
  review structure, escalation paths. Use when the DR conversation feeds
  into an EBR/QBR or account-health discussion.

---

## Sources

- [Guidance for Atlas Disaster Recovery — MongoDB Docs](https://www.mongodb.com/docs/atlas/architecture/current/disaster-recovery/)
- [Guidance for Atlas Backups — MongoDB Docs](https://www.mongodb.com/docs/atlas/architecture/current/backups/)
- [Guidance for Atlas High Availability — MongoDB Docs](https://www.mongodb.com/docs/atlas/architecture/current/high-availability/)
- [Multi-Region Deployment Paradigm — MongoDB Docs](https://www.mongodb.com/docs/atlas/architecture/current/deployment-paradigms/multi-region/)
- [Data Resilience With MongoDB Atlas — MongoDB Blog](https://www.mongodb.com/company/blog/data-resilience-with-mongodb-atlas)
- [Reliability in the Atlas Well-Architected Framework — MongoDB Docs](https://www.mongodb.com/docs/atlas/architecture/current/reliability/)
- [Replica Set Elections — MongoDB Manual](https://www.mongodb.com/docs/manual/core/replica-set-elections/)
- [Replica Sets Distributed Across Two or More Data Centers — MongoDB Manual](https://www.mongodb.com/docs/manual/core/replica-set-architecture-geographically-distributed/)
- [Deploy a Geographically Redundant Self-Managed Replica Set — MongoDB Manual](https://www.mongodb.com/docs/manual/tutorial/deploy-geographically-distributed-replica-set/)
- [MongoDB: High Availability Topology for a Multi-Region Setting — Percona](https://www.percona.com/blog/mongodb-high-availability-topology-for-a-multi-region-setting/)
- [MongoDB Atlas HA & Disaster Recovery — Replica Sets (2026) — JusDB](https://www.jusdb.com/databases/mongodb/high-availability)
- [Shard a Global Collection — Atlas Docs](https://www.mongodb.com/docs/atlas/shard-global-collection/)
- [Create a Global Cluster — Atlas Docs](https://www.mongodb.com/docs/atlas/tutorial/create-global-cluster/)
- [MongoDB Atlas Global Clusters — An Advanced Guide (Surfside Media)](https://www.surfsidemedia.in/post/mongodb-atlas-global-clusters-an-advanced-guide)
- [Recover a Point In Time with Continuous Cloud Backup — Atlas Docs](https://www.mongodb.com/docs/atlas/recover-pit-continuous-cloud-backup/)
- [Choosing the Right Atlas Backup Policy — MongoDB Learn](https://learn.mongodb.com/learn/article/choosing-the-right-atlas-backup-policy)
- [Copy Snapshots to Additional Regions — Atlas Docs](https://www.mongodb.com/docs/atlas/backup/cloud-backup/snapshot-distribution/)
- [Optimizing Disaster Recovery: Enhanced Control for Cross-Region Snapshots — MongoDB Blog](https://www.mongodb.com/company/blog/product-release-announcements/introducing-enhanced-control-for-cross-region-snapshots)
- [Introducing Snapshot Distribution in MongoDB Atlas — MongoDB Blog](https://www.mongodb.com/blog/post/introducing-snapshot-distribution-atlas)
- [Reconfigure a Replica Set During a Regional Outage — Atlas Docs](https://www.mongodb.com/docs/atlas/reconfigure-replica-set-during-regional-outage/)
- [Simulate Regional Outage — Atlas Docs](https://www.mongodb.com/docs/atlas/tutorial/test-resilience/simulate-regional-outage/)
- [rs.reconfigForPSASet() — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/method/rs.reconfigforpsaset/)
- [MongoDB Impaired Cluster Operations – AWS me-central-1 (Mar 2026)](https://isdown.app/status/mongodb/incidents/544473-delayed-cluster-operations-aws-me-central-1-united-arab-emirates)
- [MongoDB Cloud Status](https://status.mongodb.com/)
- [Multi-Cloud Data Resilience With MongoDB Atlas — MongoDB Blog](https://www.mongodb.com/company/blog/multi-cloud-data-resilience-mongodb-atlas)
- [Disaster Recovery (Basics) — MongoDB](https://www.mongodb.com/resources/basics/disaster-recovery)
- [Disaster Recovery Runbooks: Proactive Crisis Management — Solvaria](https://solvaria.com/disaster-recovery-runbooks-proactive-crisis-management/)
- [Guide to runbook examples for IT DR and cloud migration — Cutover](https://cutover.com/blog/runbook-examples-it-disaster-recovery-cloud-migration-and-technology-implementation)
- [Building Disaster Recovery Solution on MongoDB Atlas Clusters — Cambay Solutions](https://cambaysolutions.com/building-disaster-recovery-solution-on-mongodb-atlas-clusters/)
- [Using chaos engineering to test DR plans — Google Cloud Blog](https://cloud.google.com/blog/products/devops-sre/using-chaos-engineering-to-test-dr-plans)
- [Chaos Engineering for Proactive Cloud Disaster Recovery — Oracle Cloud](https://blogs.oracle.com/cloud-infrastructure/chaos-engineering-cloud-disaster-recovery)
- [Testing disaster recovery with Chaos Engineering — Gremlin](https://www.gremlin.com/community/tutorials/testing-disaster-recovery-with-chaos-engineering)
- [REL12-BP04 Test resiliency using chaos engineering — AWS Well-Architected](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel_testing_resiliency_failure_injection_resiliency.html)
- [REL13-BP02 Use defined recovery strategies — AWS Reliability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_planning_for_recovery_disaster_recovery.html)
- [Disaster recovery options in the cloud — AWS Whitepaper](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html)
- [DR Architecture on AWS, Part III: Pilot Light and Warm Standby — AWS Architecture Blog](https://aws.amazon.com/blogs/architecture/disaster-recovery-dr-architecture-on-aws-part-iii-pilot-light-and-warm-standby/)
- [AWS Disaster Recovery — 2026 Strategy Guide — Rubrik](https://www.rubrik.com/insights/aws-disaster-recovery-strategy-guide)
- [Google SRE — Postmortem Culture](https://sre.google/sre-book/postmortem-culture/)
- [Incident postmortem process — Atlassian](https://www.atlassian.com/incident-management/postmortem/templates)
- [Our simple-to-use incident post-mortem template — incident.io](https://incident.io/hubs/post-mortem/incident-post-mortem-template)
