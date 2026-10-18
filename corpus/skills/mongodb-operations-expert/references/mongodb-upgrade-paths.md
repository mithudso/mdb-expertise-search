<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-upgrade-paths` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-upgrade-paths
category: mongodb
version: "1.1.1"
updated: "2026-07-14"
description: >
  MongoDB self-managed upgrade-path expert — sequential 4.4→5.0→6.0→7.0→8.0 paths,
  "Straight-to-8" same-cluster rollout, Feature Compatibility Version (FCV) pinning,
  downgrade preservation window, "Point of No Return", rolling replica-set procedure
  (secondaries→primary, arbiter handling, election timing), sharded-cluster ordering
  (balancer→config servers→shards→mongos→FCV), driver compatibility matrix (Java 5.x,
  Node 6.x, PyMongo 4.9+, C# 3.0+, Go 1.17+), pre-upgrade safety checks (in-flight
  index builds, change-stream resumability, oplog window), disk pre-warming SOP gap
  (large-fleet 7.0→8.0), upgrade-event coverage (pre/during/post checklist, Error Envelope,
  customer sign-off), and common failure modes (driver mismatch, FCV unpin too early,
  index build conflicts, mongos version skew, PSA stepdown).
  TRIGGER: planning/executing/troubleshooting any MongoDB major-version upgrade; FCV
  questions; rolling upgrade runbook; driver compatibility for upgrade; "can I skip a
  version"; sharded cluster upgrade ordering; PSA stepdown failure; oplog window sizing
  for maintenance; "Straight-to-8"; large-fleet upgrade; cold cache after
  rolling upgrade.
  SKIP: Atlas-managed upgrades driven purely through the Atlas UI — auto-upgrade
  cadence, maintenance windows, EOL forced upgrades, 7.0->8.0 Atlas-only gotchas
  (use mongodb-atlas-expert references/mongodb-atlas-managed-upgrades.md);
  patch-revision upgrades within a major version with no FCV
  change; schema migration or aggregation changes (use mongodb-migration-patterns);
  backup/restore design (use mongodb-backup-restore).
tags:
  - mongodb
  - upgrade
  - fcv
  - replica-set
  - sharding
  - driver-compatibility
  - maintenance
whenToUse:
  - "Planning, scoping, or sequencing any MongoDB major-version upgrade (especially 7.0→8.0 or multi-hop)"
  - "Drafting or reviewing an upgrade runbook, change ticket, or maintenance-window plan"
  - "Designing the FCV pin/unpin schedule and the binary-downgrade rollback window"
  - "Diagnosing an upgrade-related incident (driver mismatch, FCV refusal, mongos skew, PSA stepdown)"
  - "Coaching a customer DBA team through their first 8.0 rollout"
  - "Determining whether a version hop is supported or requires sequential steps"
  - "Sizing oplog window before a maintenance window"
  - "Auditing driver versions across application teams before a binary upgrade"
  - "Producing post-event sign-off artefacts (Error Envelope, metric snapshots, customer sign-off)"
whenNotToUse:
  - "Atlas-managed upgrades driven entirely through the Atlas UI — use mongodb-atlas-expert"
  - "Patch-revision upgrades within a major (e.g., 8.0.3→8.0.10) with no FCV change"
  - "Driver-internal questions unrelated to server upgrades — use mongodb-drivers-k8s or mongodb-driver-internals"
  - "Schema migration or aggregation pipeline changes — use mongodb-migration-patterns"
  - "Backup/restore design — use mongodb-backup-restore"
related_skills:
  - mongodb-atlas-expert
  - mongodb-replication
  - mongodb-sharding
  - mongodb-backup-restore
  - mongodb-performance-troubleshooting
  - atlas-diagnostics-expert
  - incident-response
---

# MongoDB Upgrade Paths

Operational reference for MongoDB major-version upgrades on self-managed deployments. Covers the supported version sequence, Feature Compatibility Version (FCV) lifecycle, rolling replica-set and sharded-cluster procedures, driver matrices, pre-/post-upgrade verification, and the common failure modes that show up in real customer upgrades.

Large-customer upgrade programs (2026): **a 7.0 → 8.0 fleet upgrade** and **Straight-to-8 self-managed** initiatives. Both rely on every section below being correct.

## When to use this skill

- Planning, scoping, or sequencing any MongoDB major-version upgrade (especially 7.0 → 8.0 or multi-hop from 4.4 / 5.0 / 6.0).
- Drafting or reviewing an upgrade runbook, change ticket, or maintenance-window plan.
- Designing the FCV pin / unpin schedule and the binary-downgrade rollback window.
- Diagnosing an upgrade-related incident (driver mismatch, FCV refusal, mongos skew, cold-cache regression, PSA stepdown failure).
- Coaching a customer DBA team through their first 8.0 rollout.
- Producing post-event sign-off artefacts (Error Envelope, metric snapshots, customer sign-off).

## When NOT to use this skill

- Atlas-managed upgrades driven entirely through the Atlas UI — point at `mongodb-atlas-expert` references/mongodb-atlas-managed-upgrades.md instead (this skill covers Atlas-specific FCV pin behaviour but not the auto-upgrade cadence, maintenance windows, or 7.0->8.0 Atlas-only gotchas covered there).
- Patch-revision upgrades within a major (e.g., 8.0.3 → 8.0.10) when no FCV change is needed — the procedure is the same rolling pattern minus FCV, and is documented inline only as a reference.
- Driver-internal questions unrelated to server upgrades — point at the driver-specific skill (`mongodb-drivers-k8s`, etc.).
- Schema migration or aggregation changes — use `mongodb-migration-patterns` or `mongodb-aggregation-pipeline`.
- Backup / restore design — use `mongodb-backup-restore`.

## Related skills

- `mongodb-7.0-vs-8.0-differences` (this hub) — what actually changed technically between 7.0 and 8.0 (engine internals, new APIs, deprecations, default-value changes, performance benchmarks) — the behavior-risk counterpart to this file's procedure; read it for pre-upgrade *what will be different* risk assessment.
- `mongodb-atlas-expert` — Atlas UI flows, Atlas-managed FCV pin window, Atlas-only safety rails.
- `mongodb-replication` — replica-set internals, election theory, write-concern semantics that this skill assumes.
- `mongodb-sharding` — sharded-cluster topology, config-shard vs dedicated-config-server, balancer internals.
- `mongodb-backup-restore` — backup verification expected by Section 6 pre-upgrade checks.
- `mongodb-performance-troubleshooting` — root-causing the cold-cache regression in Section 8.
- `atlas-diagnostics-expert` — diagnostics package collection during upgrade incidents.
- `incident-response` — severity / IC handling if an upgrade goes wrong.

## Quick reference

| Question | Answer |
| --- | --- |
| Supported upgrade hop | One major version at a time: 4.4 → 5.0 → 6.0 → 7.0 → 8.0 |
| Can I skip a major version? | **No.** Even "Straight-to-8" walks through each hop sequentially. |
| Replica-set upgrade order | Secondaries (one at a time) → arbiters → primary (via `rs.stepDown()`) |
| Sharded-cluster order | Stop balancer → config servers → shards → mongos → re-enable balancer → FCV |
| FCV command | `db.adminCommand({ setFeatureCompatibilityVersion: "8.0", confirm: true })` |
| Atlas FCV pin window | **4 weeks** — auto-unpins on next maintenance after expiry |
| Self-managed FCV pin window | No enforced limit — burn-in 1–4 weeks recommended by policy |
| Java driver for 8.0 | **5.1+** (recommended 5.4+), JRE 11+ recommended |
| Top failure mode | Driver mismatch (Section 10.1) |
| Customer-visible regression that has no upstream SOP | Cold WiredTiger cache after rolling upgrade (Section 8) |

---

## 1. Version upgrade paths

MongoDB enforces **strictly sequential major-version upgrades**. You cannot skip a major release on a single cluster. The supported sequence today is:

```
4.4  →  5.0  →  6.0  →  7.0  →  8.0
```

Each arrow above is one full upgrade cycle: bump binaries → wait for cluster to stabilize → set FCV → only then start the next hop.

### Hard rules

- To upgrade to **8.0**, every member must already be on a **7.0** binary with `featureCompatibilityVersion: "7.0"`.
- To upgrade to **7.0**, every member must be on **6.0** with FCV `"6.0"`.
- The same chain holds for 5.0 ← 4.4. You cannot jump 5.0 → 7.0 or 6.0 → 8.0.
- Patch-level (revision) upgrades within a major (e.g., `8.0.3 → 8.0.10`) are unrestricted and use the same rolling pattern but never require FCV changes.

### "Straight-to-8" jump pattern

"Straight-to-8" is a customer-facing label for **rapid sequential** upgrades on the same cluster, not a literal skip. The pattern compresses the 4.4 → 8.0 ladder into a small number of well-rehearsed maintenance windows by:

1. Doing back-to-back **binary-only** upgrades through 5.0, 6.0, 7.0 with the **FCV held at the source version** for each hop (so each hop remains downgrade-eligible until validation).
2. Validating workload + drivers between hops, but **deferring `setFeatureCompatibilityVersion`** until the cluster is sitting on the 8.0 binary set with all health and driver tests passing.
3. Pinning FCV to `"7.0"` before the 7.0 → 8.0 hop so you retain a full 4-week binary-downgrade window from 8.0 back to 7.0 if 8.0 misbehaves under production load.

Straight-to-8 is **not** a documented MongoDB product feature — it is an operational rollout pattern. The supported upgrade matrix is unchanged: 4.4 → 5.0 → 6.0 → 7.0 → 8.0.

### Pre-flight: identify your starting version honestly

```javascript
db.version();                                            // binary
db.adminCommand({ getParameter: 1, featureCompatibilityVersion: 1 });  // FCV
```

If FCV lags binary by more than one major version (e.g., binary 7.0 with FCV `"5.0"`), **stop**. You must walk FCV forward one hop at a time before any further binary change.

---

## 2. Feature Compatibility Version (FCV)

FCV is the gate between **binary upgrade** and **feature activation**. It exists so customers can roll new binaries first, verify stability, then opt into the new on-disk and protocol features once they are confident no downgrade is needed.

### Key facts

- FCV is **separate from binary version**. `db.version()` returns the binary; `featureCompatibilityVersion` is its own admin parameter.
- After upgrading every node's binary to N, the FCV remains `"N-1"` until you explicitly run `setFeatureCompatibilityVersion`.
- New backwards-incompatible features (queryable encryption range queries, new index types, resharding of time-series in 8.0.10+, etc.) **stay disabled** while FCV is on the older value.
- `setFeatureCompatibilityVersion` requires `confirm: true` starting in 7.0 and remains required in 8.0:

```javascript
db.adminCommand({ setFeatureCompatibilityVersion: "8.0", confirm: true });
```

- Downgrade requires the inverse: FCV must be moved back **first**, then binaries.

### Downgrade preservation window

- Once binaries are at N and FCV is still `"N-1"`, you can **binary-downgrade** to N-1 safely. This is the "preservation window".
- **Self-managed**: the preservation window is open as long as you keep FCV pinned and no backward-incompatible features have been used.
- **Atlas-managed**: FCV pinning is bounded to a **4-week window** from the pin date. Atlas auto-unpins on the next maintenance window after expiry; once unpinned, FCV is auto-upgraded to match the binary and the rollback path closes (this is the Atlas "Point of No Return").
- Self-managed customers should mirror the 4-week discipline as a policy even though no automation enforces it — long-pinned FCV blocks feature adoption and leaves the cluster perpetually "half-upgraded."

### Burn-in recommendation

After binary upgrade, run **without** advancing FCV for a deliberate burn-in (1–4 weeks is typical). Only set FCV to the new value when:

- Driver upgrades have been deployed and steady-state for 7+ days.
- No production incidents traced to the new binary.
- Backup verification on the new binaries succeeded.
- The application owner has explicitly signed off on irreversibility.

---

## 3. Rolling upgrades — replica sets

The rolling upgrade contract: at any moment, the replica set retains a writable primary and a majority of voters.

### Order

1. **Secondaries**, one at a time. Shut down `mongod`, swap the binary, restart. Wait for the node to return to `SECONDARY` (it may transit `STARTUP2` or `RECOVERING` first — this is normal). **Do not** start the next node until `rs.status()` shows the current one back in `SECONDARY`.
2. **Arbiters** (if any). Arbiters are stateless and have priority 0 by default. Upgrade them at any point after the secondaries but before the primary. Treat them like a tiny secondary: stop, swap, start, confirm `ARBITER` state. **Do not** make the arbiter the last node — its election votes matter when the primary steps down.
3. **Primary, last.** Connect `mongosh` to the primary and run:

```javascript
rs.stepDown();   // default freeze: 60s on 6.0+, 120s on older versions
```

Stepping down is preferable to a hard shutdown because it triggers a clean election. Then upgrade the now-secondary former primary.

### Election timing

- Median election time with default settings is **~10–12 seconds**. Plan for a brief write outage when the primary steps down.
- Election priority is configurable per node via `members[n].priority`. Setting your preferred upgrade-last node to high priority before stepDown gives you a predictable post-upgrade primary.
- `electionTimeoutMillis` (default 10s) controls how long secondaries wait before calling an election. Some customers lower this in pre-upgrade maintenance windows to **5000ms** to compress outage, then revert post-upgrade. Document and review with the customer — it changes failover semantics in production.

### Arbiter handling

- Arbiters cannot become primary and hold no data, so they do **not** require FCV considerations on upgrade.
- Three-node replica sets with one arbiter (PSA topology) are the most fragile during rolling upgrades because losing the data secondary while the primary is stepping down leaves no eligible primary. Recommend customers move arbiters off PSA topologies before any major upgrade.

---

## 4. Sharded cluster upgrades

Sharded clusters have three component classes — config servers, shards, mongos — and the upgrade ordering is **strict**.

### Order (8.0 example, applies to every major hop)

**Pre-step 0 — Disable the balancer** before any binary change:

```javascript
sh.stopBalancer();
sh.isBalancerRunning();   // confirm "false"
```

Then walk the tiers in this strict order:

1. **Config server replica set** (CSRS). Apply the rolling replica-set procedure (Section 3) to the config servers.
2. **Shards** next. For each shard (replica set), repeat the rolling procedure. Upgrade least-critical shards first if possible — most v8 sharded upgrade incidents originate in the shard phase, and walking from least to most critical limits blast radius.
3. **`mongos`** routers last. mongos is stateless, so you can drain connections and restart them in parallel groups.

**Post-step — Re-enable balancer**, then **set FCV** only after all three tiers are upgraded and stable:

```javascript
sh.startBalancer();
db.adminCommand({ setFeatureCompatibilityVersion: "8.0", confirm: true });
```

### Version-skew rules

- A `mongos` running version M can **only** talk to mongods with FCV ≤ M. Concretely: a 7.0 mongos cannot connect to a sharded cluster whose FCV has been advanced to `"8.0"`. It **can** connect to an 8.0 cluster that is still pinned at FCV `"7.0"`.
- Mixed-version mongos pools are tolerated **during** the upgrade window but should not be left in production beyond the maintenance event.
- Config servers must be on the same or newer version as the shards. Never let a shard run a newer binary than its config server.

### Config shard caveat (8.0+)

If your cluster uses the **config shard** topology (config server doubling as a data shard, introduced in 7.0), you must run `transitionToDedicatedConfigServer` before downgrading FCV below 8.0. There is no equivalent path forward — this is a downgrade-only gate.

---

## 5. Driver compatibility

A driver mismatch is the most common day-1 production incident after a server upgrade. The driver must support the target server version **before** binaries change.

### Java driver (the matrix that matters for most enterprise customers)

| MongoDB Server | Minimum Java driver | Notes |
| --- | --- | --- |
| 4.4 | 4.1+ | |
| 5.0 | 4.3+ | First version supporting timeseries and load-balanced topology. |
| 6.0 | 4.7+ | Required for queryable encryption beta. |
| 7.0 | 4.10+ | 4.10.x is the LTS line that paves the way to 5.x. |
| 8.0 | **5.1+** (recommended **5.4+**) | Requires Java 8 minimum; **Java 11+ recommended**; Java 17 LTS supported. |

### Retry semantics

- `retryWrites=true` is **default** on 4.2+ drivers; do not disable it for upgrade convenience.
- `retryReads=true` is default on 4.0+ drivers.
- During a primary stepdown, an in-flight write with `retryWrites=true` is automatically retried against the new primary once the driver's server selection timeout (default 30s) discovers the new topology. This is why a clean `rs.stepDown()` is preferable to `kill -9` — kill-9 invalidates connection state in ways that break some retry paths.
- For **5.x Java drivers**, `MongoClientSettings` exposes finer-grained `serverApi` and `serverSelectionTimeout`. Default is fine for upgrades.

### Other drivers — quick rules

- **Node.js**: driver 6.x supports MongoDB 8.0. Driver 5.x maxes at 7.0. Always confirm against `mongodb` package `peerDependencies` vs the connected server.
- **Python (PyMongo)**: 4.7+ for 7.0, **4.9+** for 8.0.
- **C# / .NET**: 2.28+ for 7.0, **3.0+** for 8.0.
- **Go**: 1.13+ for 7.0, **1.17+** for 8.0.

The canonical matrix lives at `https://www.mongodb.com/docs/drivers/` — verify there for the exact patch level before any production upgrade.

---

## 6. Pre-upgrade checks

Run these checks before touching binaries. Missing any one of them is how upgrades fail in the middle of the maintenance window.

### Required gates

1. **All nodes on the prerequisite version**, FCV matches:
   ```javascript
   db.adminCommand({ getParameter: 1, featureCompatibilityVersion: 1 });
   ```
2. **No in-flight index builds**:
   ```javascript
   db.currentOp({ "command.createIndexes": { $exists: true } });
   db.currentOp({ msg: /Index Build/ });
   ```
   An interrupted index build leaves the collection in `unfinished` state. Either let the build complete or `dropIndex` and restart it after the upgrade.
3. **Change-stream consumers are resumable**: confirm every consumer is storing `_id` (resume token) durably so it can resume past the maintenance window. If oplog rolls beyond the last-seen token during upgrade, the consumer must do a full reseed — surface this risk to the customer in writing.
4. **Oplog window** comfortably exceeds expected maintenance duration:
   ```javascript
   rs.printReplicationInfo();   // shows oplog length
   ```
   Aim for **≥ 4× the expected maintenance window** (e.g., 4-hour oplog for a 1-hour upgrade). If short, raise oplog size before upgrade with `replSetResizeOplog`.
5. **Backup verified, not just taken**. Restore the latest snapshot into a scratch cluster and run a smoke query. Untested backups are not backups.
6. **Driver compatibility deployed**. Drivers should be on the target-server-compatible version for at least 7 days before the upgrade.
7. **Replica lag < 5 seconds** on every secondary:
   ```javascript
   rs.printSecondaryReplicationInfo();
   ```
8. **Disk free space**: at minimum 25% headroom. WiredTiger needs room for the new on-disk format files even when FCV is held.
9. **Compatibility scan**: review the target version's "Compatibility Changes" doc and grep the application for any removed/deprecated command names (e.g., `$listLocalSessions` semantics, `geoNear` aggregation pipeline equivalents).

### Index builds and commit quorum (8.0 nuance)

Starting in **MongoDB 8.0**, the **commit quorum** specifies how many nodes must be **ready to finish** the index build before the primary commits, while the **write concern** specifies how many nodes must **replicate the commit oplog entry** before the command returns success. This is a semantic change vs. 7.0 and earlier. If your application sets `commitQuorum` explicitly, audit those calls.

Default `commitQuorum` is `votingMembers` (all voting data-bearing members). Lowering it (e.g., `majority`) can prevent index builds from stalling on a lagging secondary during the upgrade window.

---

## 7. Upgrade rollback

### Binary downgrade window

The rollback path depends entirely on **whether FCV was pinned before the upgrade**.

| State | Downgrade possible? |
| --- | --- |
| Binary upgraded, FCV still at N-1, no new features used | Yes — binary downgrade is safe and reversible. |
| Binary upgraded, FCV advanced to N, no new features used | Possible only by reversing FCV first (`setFeatureCompatibilityVersion: "N-1", confirm: true`) then binary downgrade. |
| Binary upgraded, FCV advanced to N, new features used (encrypted ranges, new index types, etc.) | **Not** supported without removing the persisted feature data first. May require MongoDB Support assistance. |

### The "Point of No Return" command

`setFeatureCompatibilityVersion` with the new version **is** the Point of No Return for the rollback window. Once executed and confirmed, the FCV gate closes:

- On **Atlas**, the 4-week pin window starts at FCV pin time. After expiry, Atlas auto-advances FCV at the next maintenance window — explicit and visible in the Atlas UI.
- On **self-managed**, there is no automation. Operator discipline is the only enforcement. Add the burn-in calendar reminder to your runbook.

### Practical rollback playbook

1. Detect regression (latency, error rate, missing feature support in application).
2. Confirm FCV state. If FCV is still `"N-1"`:
   - Apply rolling **binary downgrade** in reverse order: primary last for replica sets; mongos → shards → config servers for sharded clusters.
3. If FCV has been advanced:
   - Audit for use of new-version-only features. Atlas indexes that depend on new operators, new index types, sharded time-series with reshardCollection, etc.
   - If clean, run `setFeatureCompatibilityVersion: "N-1", confirm: true`. If features are in use, open a Premium Support case before touching anything.
4. Document the rollback as a near-miss event regardless of whether downgrade succeeded. The data is the most valuable input for the next upgrade.

---

## 8. Disk pre-warming (7.0 → 8.0 lesson)

**Status**: known operational gap, manual SOP, **not** documented in upstream MongoDB upgrade procedures.

### The problem

Large-fleet cluster upgrades from 7.0 → 8.0 exposed a recurring symptom: secondaries that come back online after the binary swap return to `SECONDARY` state quickly, but their **WiredTiger block cache is cold**. When the load balancer (or a stepDown on the primary) shifts read traffic onto a freshly upgraded secondary, query latency spikes 10–100× until the cache rewarms. For latency-sensitive workloads (Cookie's read SLA is sub-10ms p99), this looks like a production incident.

### Why MongoDB docs don't cover it

The WiredTiger cache is in-process memory; it always starts empty after `mongod` restart and warms naturally with traffic. Standard MongoDB guidance is "let it warm". For most workloads that is fine. For low-latency, predictable-workload customers it is **not** fine — the natural warm-up takes minutes and the latency degradation is customer-visible.

### Pre-warming SOP (manual, customer-driven)

This is the pattern customer operators developed. There is no automated tool from MongoDB.

1. After binary swap and `SECONDARY` state, **hold the node out of routing** (e.g., `hidden: true, priority: 0`, or remove from driver readPreference rotation).
2. Run a **scripted touch query workload** that mimics the production read pattern — typically a parallel sweep over the most-frequently-accessed indexes (covered queries against the hot collections), constrained to a small key range so the OS cache and WT cache fill in a controlled order.
3. Monitor cache pressure with:
   ```javascript
   db.serverStatus().wiredTiger.cache;
   ```
   Watch `bytes currently in the cache` and `pages read into cache` — when growth flattens, warm-up is complete.
4. Reset `hidden: false` (or re-add to routing rotation) only after the cache fills to ~70% of `cacheSizeGB` and p99 latency from the touch workload matches pre-upgrade baseline.

### Recommendation to MongoDB Engineering

This SOP is a documentation and tooling gap. The TAM team should propose:

- A documented "pre-warming after rolling upgrade" appendix in the upgrade tutorial.
- A built-in `cacheWarmup` admin command that walks the hot indexes for the calling user — opt-in, time-boxed, and observable via `currentOp`.

Until then, the manual SOP above is the supported pattern for latency-critical customers.

---

## 9. Upgrade event coverage

An upgrade is a **scheduled maintenance event**, not a deploy. TAM-owned upgrades follow a three-phase template with explicit sign-offs.

### Pre-event (T-7 days through T-0)

- Driver compatibility verified and deployed (Section 5).
- All pre-upgrade checks (Section 6) green and documented.
- Backup tested via restore (not just taken).
- Customer change ticket approved with explicit start/end timestamps.
- Rollback decision matrix (Section 7) attached to the change ticket.
- On-call rotation: TAM + MongoDB Premium Support + customer DBA, contact tree pre-shared.
- Communication template ready: customer status page, internal Slack channel, exec summary email.

### During event (T-0 → T-end)

- Single change owner (DRI) running the runbook step-by-step. Every step gets a timestamped status post in the shared channel.
- Health gates between each component group (after every secondary, after primary, after each shard, after mongos pool).
- **Error Envelope** logged in real time. Every non-fatal warning gets:
  - Timestamp
  - Component (mongod hostname, mongos node, driver, etc.)
  - Error text verbatim
  - Decision: continue / pause / rollback
  - Sign-off by DRI
- If the Error Envelope accumulates more than one **unexplained** entry, the default decision is **pause**, not push through.

### Post-event (T-end → T+72 hours)

- Application smoke tests (read, write, change-stream, aggregation, index builds).
- Driver-level smoke tests — each app team confirms they can connect, read, write, listen.
- Metrics baseline restored: p50/p95/p99 latency, error rate, replication lag, oplog window.
- Burn-in monitoring window opens (1–4 weeks before FCV advance).
- Customer sign-off captured in writing, attached to the change ticket. Without sign-off the event is **not** closed even if the binaries are upgraded.
- Post-event review within 5 business days: what worked, what surprised us, what changes the runbook for the next upgrade. Append to the customer's `customer-files/.../upgrade-history.md`.

### Sign-off artefacts

A complete upgrade event produces:

- The change ticket with start/end timestamps and DRI.
- The runbook as executed (mark each step with timestamp + initials).
- The Error Envelope log.
- Pre- and post-event metric snapshots (latency, lag, oplog).
- Customer sign-off (email or ticket reply).
- Post-event review document.

Anything less and the event is not auditable.

---

## 10. Common upgrade failures

The recurring failure modes, ranked by frequency from real customer post-mortems:

### 10.1 Driver mismatch

**Symptom**: application throws connection errors immediately after the primary steps down, or after the cluster is fully on the new binary.

**Root cause**: driver was not updated to a server-compatible version before the upgrade. Common in environments where multiple application teams share a database — one team upgrades, ten others discover they can't connect.

**Mitigation**:
- Driver upgrade as a **mandatory** pre-step, completed 7+ days before binary upgrade.
- Connection-string validation across all app teams.
- Audit `currentOp().clientMetadata.driver.version` on the cluster before upgrade to enumerate every driver version in production.

### 10.2 FCV unpinned too early

**Symptom**: customer wants to roll back after the upgrade because of unrelated production incident; rollback path is closed.

**Root cause**: operator (or Atlas auto-unpin) advanced FCV before the burn-in window completed.

**Mitigation**:
- Burn-in window written into the runbook with explicit calendar dates.
- Atlas customers: track FCV pin expiration in the customer's own docs.
- Self-managed: review FCV state at every weekly cadence call until burn-in expires; do not advance silently.

### 10.3 Index build conflicts

**Symptom**: secondary returns to `RECOVERING` and never reaches `SECONDARY`, or `replSetReconfig` rejects the new member set because of inconsistent indexes.

**Root cause**: an in-flight index build was interrupted by the binary swap, leaving the collection in an inconsistent state across members. Or, the new version changed default index behavior (e.g., 4.2 → 4.4 wildcard index, 7.0 → 8.0 commit-quorum semantics).

**Mitigation**:
- Pre-upgrade check: no `currentOp` matching index build (Section 6).
- Post-upgrade: scan each member for inconsistent indexes:
  ```javascript
  db.runCommand({ listIndexes: "<coll>" });
  ```
  Compare across primary and secondaries.
- Use the official MongoDB **Shard Index Inconsistent Script** for sharded clusters.

### 10.4 mongos version skew

**Symptom**: queries fail intermittently with `IncompatibleServerVersion` or routing errors after partial upgrade.

**Root cause**: mongos pool contains a mix of N-1 and N binaries while FCV has been advanced to N, or shards on mixed versions.

**Mitigation**:
- Strict component-order discipline (Section 4): config → shards → mongos → FCV.
- Health gate after the **last** mongos restart, before any FCV change.
- Verify all mongos versions match:
  ```javascript
  db.adminCommand({ listShards: 1 });  // run on each mongos
  ```

### 10.5 PSA topology stepdown failure

**Symptom**: during the upgrade of the data secondary in a Primary-Secondary-Arbiter (PSA) topology, the primary steps down and cannot find a majority for a new election. Cluster is read-only.

**Root cause**: PSA only has two data-bearing voters. While the secondary is offline for upgrade, the primary alone cannot achieve majority for any write that requires `w: majority`, and the arbiter cannot help. If the primary then steps down, the cluster has no eligible primary until the secondary returns.

**Mitigation**:
- Pre-upgrade: convert PSA to PSS (three data-bearing voters) before the major upgrade. This is the single most impactful PSA recommendation TAMs can make.
- If conversion is impossible, do **not** combine the secondary upgrade with the primary upgrade in the same window — leave 24+ hours between them.

### 10.6 Oplog window overflow during long maintenance

**Symptom**: secondary returns from upgrade and immediately enters full initial sync because its lag exceeded the oplog window.

**Root cause**: maintenance ran longer than expected; oplog size was sized for steady-state replication lag, not for a multi-hour maintenance window.

**Mitigation**:
- Section 6 oplog window check.
- Resize oplog **upward** as a pre-upgrade step:
  ```javascript
  db.adminCommand({ replSetResizeOplog: 1, size: 102400 });   // 100 GB
  ```
- Restore oplog size post-burn-in if disk pressure requires it.

### 10.7 Cold-cache latency regression (Section 8)

**Symptom**: post-upgrade p99 read latency spikes for minutes after each rolling upgrade step.

**Root cause**: WiredTiger cache reset on `mongod` restart; default warm-up is uncontrolled.

**Mitigation**: pre-warming SOP from Section 8. Document gap; advocate for upstream tooling.

---

## Quick command reference

```javascript
// Identify state
db.version();
db.adminCommand({ getParameter: 1, featureCompatibilityVersion: 1 });
rs.status();
rs.printReplicationInfo();
rs.printSecondaryReplicationInfo();

// Replica set upgrade
rs.stepDown();        // step down primary cleanly

// FCV — the Point of No Return
db.adminCommand({ setFeatureCompatibilityVersion: "8.0", confirm: true });

// Sharded cluster
sh.stopBalancer();
sh.startBalancer();
sh.status();

// Index / op state
db.currentOp({ "command.createIndexes": { $exists: true } });
db.adminCommand({ listShards: 1 });

// Oplog resize
db.adminCommand({ replSetResizeOplog: 1, size: 102400 });

// WiredTiger cache state (pre-warm SOP)
db.serverStatus().wiredTiger.cache;
```

---

## Sources

- [Upgrade a Replica Set to 8.0 — MongoDB Docs](https://www.mongodb.com/docs/manual/release-notes/8.0-upgrade-replica-set/)
- [Upgrade a Standalone to 8.0 — MongoDB Docs](https://www.mongodb.com/docs/manual/release-notes/8.0-upgrade-standalone/)
- [Upgrade a Sharded Cluster to 8.0 — MongoDB Docs](https://www.mongodb.com/docs/manual/release-notes/8.0-upgrade-sharded-cluster/)
- [Upgrade a Replica Set to 7.0 — MongoDB Docs](https://www.mongodb.com/docs/manual/release-notes/7.0-upgrade-replica-set/)
- [setFeatureCompatibilityVersion command — MongoDB Docs](https://www.mongodb.com/docs/manual/reference/command/setfeaturecompatibilityversion/)
- [Replica Set Elections — MongoDB Docs](https://www.mongodb.com/docs/manual/core/replica-set-elections/)
- [Config Servers — MongoDB Docs](https://www.mongodb.com/docs/manual/core/sharded-cluster-config-servers/)
- [Config Shard — MongoDB Docs v8.0](https://www.mongodb.com/docs/v8.0/core/config-shard/)
- [Java Sync Driver Compatibility — MongoDB Docs](https://www.mongodb.com/docs/drivers/java/sync/current/compatibility/)
- [Java Reactive Streams Driver Compatibility — MongoDB Docs](https://www.mongodb.com/docs/languages/java/reactive-streams-driver/current/compatibility/)
- [Index Builds on Populated Collections — MongoDB Docs](https://www.mongodb.com/docs/manual/core/index-creation/)
- [setIndexCommitQuorum — MongoDB Docs](https://www.mongodb.com/docs/manual/reference/command/setindexcommitquorum/)
- [Change Streams Production Recommendations — MongoDB Docs](https://www.mongodb.com/docs/manual/administration/change-streams-production-recommendations/)
- [Release Notes for MongoDB 8.0 — MongoDB Docs](https://www.mongodb.com/docs/manual/release-notes/8.0/)
- [MongoDB 8.0 Upgrade Guide (Medium)](https://medium.com/mongodb/mongodb-8-0-migration-guide-what-you-need-to-know-before-upgrading-9fc577ab02e6)
- [Downgrade Major MongoDB Version for a Cluster — Atlas Docs](https://www.mongodb.com/docs/atlas/tutorial/major-version-downgrade/)
- [WiredTiger Storage Engine — MongoDB Docs](https://www.mongodb.com/docs/manual/core/wiredtiger/)
- [Troubleshooting MongoDB Shard Upgrades — Mydbops](https://www.mydbops.com/blog/troubleshooting-mongodb-shard-upgrades-resolving-index-discrepancies)
- [FCV and Feature Flag Internals — mongodb/mongo on GitHub](https://github.com/mongodb/mongo/blob/master/src/mongo/db/repl/FCV_AND_FEATURE_FLAG_README.md)
- [Faster Elections During Rolling Maintenance — Shyam Arjarapu / HackerNoon](https://medium.com/hackernoon/mastering-mongodb-faster-elections-during-rolling-maintenance-a567ae5416f5)
