<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongosync` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongosync
title: mongosync — MongoDB's Native Live Migration Tool
category: mongodb
version: "1.1.0"
updated: "2026-05-29"
description: >
  Use when the user mentions a MongoDB live migration, cluster-to-cluster sync, mongosync,
  Atlas Live Migration, ongoing CDC between two MongoDB clusters, or any cutover/rollback
  involving two MongoDB clusters — even when they don't name the tool. Covers the mongosync
  binary end-to-end: initial sync + change-stream-based CDC, includeNamespaces/excludeNamespaces
  filtering with regex, namespace remap, resume from durable checkpoint, four verification
  modes (embedded, dbHash, document count, migration-verifier), reverse sync for rollback
  (reversible+enableUserWriteBlocking), the IDLE/RUNNING/PAUSED/COMMITTING/COMMITTED/REVERSING
  state machine, oplog window sizing and ChangeStreamHistoryLost recovery, sharded topologies
  (one mongosync per shard, balancerStop), loadLevel/host-sizing tuning, TLS + x.509 auth,
  and the decision framework for mongosync vs Atlas Live Migration vs Cluster-to-Cluster Sync.
  TRIGGER: any MongoDB migration/sync planning, "moving cluster to Atlas", "MongoDB CDC between
  clusters", debugging a stalled or failed sync, writing a migration runbook, or comparing
  C2C/Live-Migration/mongosync.
  SKIP: single-cluster backup/restore (use mongodb-backup-restore), pure replica-set topology
  design (use mongodb-replication), general migration strategy unrelated to MongoDB (use
  mongodb-migration-patterns), schema transformation during migration (use mongodb-migration-patterns).
tags:
  - mongodb
  - mongosync
  - migration
  - live-migration
  - cluster-to-cluster-sync
  - cdc
  - change-streams
  - atlas-migration
keywords:
  - mongosync
  - cluster-to-cluster sync
  - c2c sync
  - live migration
  - Atlas Live Migration
  - initial sync
  - CDC
  - change data capture
  - change streams
  - oplog tailing
  - resume token
  - includeNamespaces
  - excludeNamespaces
  - filtered sync
  - namespace remapping
  - reverse sync
  - reversible
  - enableUserWriteBlocking
  - canWrite
  - cutover
  - commit endpoint
  - pause endpoint
  - resume endpoint
  - start endpoint
  - mongosync states
  - IDLE
  - RUNNING
  - PAUSED
  - COMMITTING
  - COMMITTED
  - REVERSING
  - loadLevel
  - oplogSizeMB
  - replSetResizeOplog
  - minRetentionHours
  - oplog window
  - ChangeStreamHistoryLost
  - embedded verifier
  - migration verifier
  - dbHash
  - migration-verifier
  - x509
  - TLS
  - cluster0
  - cluster1
  - migration host
  - 8 CPU 24 GB
  - sharded sync
  - balancerStop
  - replica set to sharded
  - Atlas push migration
  - Atlas pull migration
whenToUse:
  - "Planning a MongoDB live migration to Atlas or between any two clusters"
  - "Choosing between Atlas Live Migration, standalone mongosync, or Cluster-to-Cluster Sync"
  - "Sizing the mongosync migration host or oplog window before a sync"
  - "Building a config file with includeNamespaces / excludeNamespaces filters or namespace remap"
  - "Debugging a stalled, paused, or failing mongosync session (oplog rollover, network partition)"
  - "Verifying a completed migration with hash, embedded verifier, or migration-verifier"
  - "Designing a cutover and rollback plan with reverse sync"
  - "Tuning loadLevel, parallel workers, or shard-level mongosync instances"
  - "Configuring TLS and x.509 auth for mongosync to reach both clusters"
  - "Recovering from ChangeStreamHistoryLost or invalid resume token errors"
  - "Writing or reviewing a customer's mongosync-driven migration runbook"
whenNotToUse:
  - "Single-cluster backup/restore — use mongodb-backup-restore"
  - "Pure replica-set topology design without migration — use mongodb-replication"
  - "General migration strategy unrelated to MongoDB clusters — use mongodb-migration-patterns"
  - "Schema transformation during migration — use mongodb-migration-patterns for the broader playbook"
related_skills:
  - mongodb-migration-patterns
  - mongodb-backup-restore
  - mongodb-replication
  - mongodb-sharding
  - mongodb-atlas-expert
  - incident-response
---

# mongosync — MongoDB's Native Live Migration Tool

mongosync is MongoDB's official utility for continuous, real-time replication between two MongoDB
clusters. It performs a full initial sync followed by change-stream-based CDC (no Kafka, no
Debezium) and supports cutover with sub-minute downtime, reverse sync for rollback, and filtered
namespace replication. mongosync powers Atlas Live Migration and Cluster-to-Cluster Sync.

## 1. Architecture — Initial Sync + Ongoing CDC

mongosync runs as a standalone Go binary outside of mongod/mongos. It opens connections to two
clusters and moves data in two phases:

1. **Initial sync** — mongosync reads collection data from the source cluster in parallel
   workers, applies inserts to the destination cluster, builds indexes, and tracks progress
   per-collection.
2. **Change Event Application (CEA)** — once initial sync completes, mongosync tails the source
   via **change streams**, applies operations to the destination, and stays in lockstep until
   you commit or pause. mongosync does **not** read the oplog directly — it relies on the
   change-streams API.

Because CDC runs over change streams, mongosync's resumability depends on the source oplog
window. If un-applied operations age out of the source oplog, the change stream returns
`ChangeStreamHistoryLost` and mongosync fails — see Section 6.

### Topology notes

- **Replica set → replica set**: one mongosync instance.
- **Sharded → sharded**: run **one mongosync per shard** on the source. mongosync replicates
  individual shards in parallel from source to destination.
- **Replica set → sharded** and **sharded → replica set**: supported with a single mongosync
  for the all-to-one cases, with caveats; check the version-specific topology page.
- Both clusters must run MongoDB **6.0 or later** and share the **same major version**
  (mongosync also supports certain version-cross migrations — confirm against the version
  matrix for your mongosync release).

### Migration host sizing

For a production sync, MongoDB recommends a dedicated migration host with **at least 8 CPUs and
24 GB of RAM**. The host needs network reachability to both clusters and enough disk for logs
and the local progress state.

## 2. Configuration

### CLI vs config file

mongosync accepts CLI flags or a YAML/JSON config file via `--config`. The config file is the
**production-grade path** because:

- Passwords on the command line are visible to `ps`, `top`, and audit logs.
- The config file can be reloaded mid-migration to change settings like `loadLevel`.

### Core connection options

| Option | Purpose |
| --- | --- |
| `--cluster0` | Connection URI for the first cluster (source or destination). |
| `--cluster1` | Connection URI for the second cluster (source or destination). |
| `--config` | Path to YAML/JSON config file. Preferred for secrets. |
| `--logPath` | Directory where mongosync writes log files. |
| `--loadLevel` | Aggressiveness 1–4. Default 3. Higher = faster + more destination load. |
| `--verbosity` | Log verbosity (TRACE, DEBUG, INFO, WARN, ERROR, FATAL). |

> Cluster role (source vs destination) is **not** set on the binary — it's decided by the call
> to the `/api/v1/start` endpoint. The same mongosync process can be reversed; see Section 8.

### Example minimal config (YAML)

```yaml
cluster0: "mongodb+srv://migrator:<password>@source.example.com/?authSource=admin"
cluster1: "mongodb+srv://migrator:<password>@dest.example.com/?authSource=admin"
logPath: "/var/log/mongosync"
loadLevel: 3
verbosity: "INFO"
port: 27182
```

### REST API surface

mongosync exposes an HTTP API on `127.0.0.1:27182` (default port). Key endpoints:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/start` | Begin the sync. Body specifies source, destination, filters, options. |
| `GET  /api/v1/progress` | Current state, copy phase progress, lag, errors. |
| `POST /api/v1/pause` | Pause sync (entering PAUSED). |
| `POST /api/v1/resume` | Resume from PAUSED. Can take ~2 minutes before transitioning. |
| `POST /api/v1/commit` | Begin cutover (COMMITTING → COMMITTED). |
| `POST /api/v1/reverse` | Reverse sync direction (requires `reversible:true` at start). |

### `start` body — the essential fields

```json
{
  "source": "cluster0",
  "destination": "cluster1",
  "reversible": true,
  "enableUserWriteBlocking": true,
  "includeNamespaces": [
    { "database": "sales", "collections": ["EMEA", "APAC"] },
    { "database": "marketing" }
  ]
}
```

- `reversible:true` + `enableUserWriteBlocking:true` are **both required** to support reverse
  sync later.
- `enableUserWriteBlocking` tells mongosync to block writes on the destination during the sync
  so reverse sync remains safe.

## 3. Filtering — includeNamespaces / excludeNamespaces / namespace remap

### Basic filters

`includeNamespaces` and `excludeNamespaces` are mutually exclusive arrays of filter objects.
Each object has a `database` and optionally a `collections` array. With no filter mongosync
performs a **full cluster sync** (every non-system database/collection).

```json
"includeNamespaces": [
  { "database": "sales", "collections": ["EMEA", "APAC"] },
  { "database": "marketing" }
]
```

This includes only `sales.EMEA`, `sales.APAC`, and every collection under `marketing`.

### Regex filters (mongosync 1.6+)

Filter values can be regular expressions, so you can match many databases/collections at once:

```json
"includeNamespaces": [
  { "database": "/^tenant_[0-9]+$/", "collections": ["/^orders.*/"] }
]
```

### Namespace remapping

`namespaceRemap` lets you rewrite the destination namespace, useful for tenant consolidation
or rename-during-migration. The destination database and/or collection name can differ from
the source.

### Filter immutability

**You cannot change a filter on a running sync.** Stop mongosync, prepare the destination
(drop any partially-synced collections), and start a new sync with the updated filter. There
is no in-place filter edit.

### Items mongosync never replicates

- `local`, `config`, `admin` database internals (system collections).
- User credentials and roles — you must recreate roles/users on the destination.
- Any collection mongosync flags as "unsupported" for the version (e.g., certain time-series
  edge cases — check the FAQ for your release).

## 4. Resumability — Checkpoint State and Resume

### Where state lives

mongosync writes progress and resume tokens to the **destination** cluster (in a metadata
collection mongosync owns). That is why `resume` after a process crash works even on a brand-
new mongosync host: the durable checkpoint lives next to the data.

### Resume rules

- `resume` only works if mongosync is in PAUSED state (or the process was killed in RUNNING
  and you bring it back).
- After `resume`, mongosync may take **at least 2 minutes** before re-entering RUNNING — it
  re-validates the resume token and reopens the change stream.
- The resume token is a change-stream `_data` value. If the oplog has rolled past it, the
  change stream errors with `ChangeStreamHistoryLost` and the sync **cannot** resume — you
  must drop the destination and start over.

### When you cannot resume

- Long pause + small source oplog → window exhausted.
- Destination collection dropped/altered while mongosync was paused.
- Filter change attempted (filters are immutable — see Section 3).

## 5. Verification

mongosync ships four verification methods. Pick based on cluster shape and downtime budget.

### 5.1 Embedded verifier (default, replica sets)

- On by default for replica-set clusters.
- Runs in the background after initial sync, comparing documents on the destination as they
  are written.
- No locks, no extra downtime.

### 5.2 Hash comparison (dbHash MD5)

- `dbHash` MD5 over each collection on source vs destination.
- **Locks the cluster** for the duration of the hash — no writes can land.
- **Not available on sharded clusters**.
- Slow on large collections; precise.

### 5.3 Document counts

- Cheapest method: `db.coll.countDocuments()` on both sides.
- **Only safe for insert-only workloads** — it cannot detect document drift from updates.

### 5.4 Migration Verifier (`mongodb-labs/migration-verifier`)

- Standalone open-source tool from MongoDB Labs.
- Connects to source and destination, compares documents/views/indexes.
- **Can run concurrently with mongosync** — no need to pause.
- The right choice for large, heavily-mutated, or sharded migrations.

### Verification decision tree

```
sharded cluster?           → migration-verifier
replica set, low-mutation? → embedded verifier (default) is enough
need cryptographic proof?  → dbHash, but pause writes first
insert-only data?          → document counts
```

## 6. Failure Modes & Troubleshooting

### Oplog window exhaustion

Symptom: mongosync exits with `ChangeStreamHistoryLost` or similar — the source oplog rolled
past mongosync's resume point.

Causes:
- Initial sync taking too long on a high-write source.
- Long pause while CDC is suspended.
- Source oplog sized too small (default 5% of disk can be tiny on busy servers).

Fixes:
- **Pre-sync**: increase `oplogSizeMB` (or `replSetResizeOplog` with `minRetentionHours` >
  expected sync duration).
- **During sync**: scale up the mongosync host (more CPU/RAM) so CDC keeps up.
- **Post-failure**: drop destination collections and restart — there is no recovery once the
  oplog window is gone.

Rule of thumb: set `minRetentionHours` to **2–3× the expected initial-sync duration plus any
pause window**.

### Network partitions

mongosync retries transient network errors with exponential backoff. Sustained partitions
cause mongosync to surface errors via `/progress` and eventually stop. Restart picks up from
the last checkpoint **iff** the oplog window is still intact.

### Schema drift

mongosync replicates DDL via change events — collection creates, drops, index builds. It does
**not** repair manual drift on the destination. If someone writes directly to the destination
while a sync runs, you've corrupted the migration; restart from scratch. `enableUserWriteBlocking`
on the destination is the guardrail.

### Stalled progress

- Check `/api/v1/progress` for `lagTimeSeconds`.
- Check destination index builds — slow index builds back up CDC.
- Check destination CPU/IOPS — `loadLevel` may be too high.

### Cannot reverse / reverse refused

- `reversible` was not `true` at start.
- `enableUserWriteBlocking` was not `true`.
- Source and destination MongoDB **major versions differ**.
- Topologies differ (e.g., replica set vs sharded).
- Destination oplog rolled past the moment mongosync went `canWrite=true`.

## 7. mongosync vs Atlas Live Migration vs Cluster-to-Cluster Sync

All three use the **same underlying mongosync engine**. The difference is the operating
envelope:

| Tool | Best for | Manages host? | Filters? | Network |
| --- | --- | --- | --- | --- |
| **Atlas Live Migration (pull)** | ≤5 TB, ≤3 shards, into Atlas | Yes — Atlas provisions migration servers | No filtering, full cluster | Public network only — **no VPC peering, no private link** |
| **Atlas Live Migration (push)** | Cloud Manager / Ops Manager source | Yes — Atlas drives Ops Manager agents | No filtering | Public + Cloud/Ops Manager visibility |
| **Standalone mongosync** | Any size, filtered sync, private networking, version cross | No — you operate the host | Full include/exclude/regex | Any (VPC peering, private link) |
| **Cluster-to-Cluster Sync (MongoDB 7.0+)** | Continuous sync between two clusters (DR, multi-cloud) | No | Yes | Any |

### Decision rules

- Need filtered sync, namespace remap, private link, or cross-version → **standalone mongosync**.
- Smaller cluster going into Atlas with public network → **Atlas Live Migration** (one-click).
- Long-lived ongoing replication between two clusters (DR, multi-region, active-passive) →
  **Cluster-to-Cluster Sync** (same binary, configured to never reach COMMITTED).

## 8. Reverse Sync — Cutover & Rollback

### Cutover process

1. mongosync is RUNNING with `lagTimeSeconds` low (sub-second on healthy networks).
2. Quiesce application writes on the **source**.
3. Call `POST /api/v1/commit`.
4. mongosync moves to COMMITTING — drains remaining change events.
5. mongosync reaches COMMITTED — final state. The destination is now authoritative.
6. Flip application connection strings to the destination cluster.

Healthy production cutovers complete in **under 60 seconds** because mongosync already had CDC
caught up before `commit`.

### Reverse sync — rollback

If the destination misbehaves post-cutover, you can flip the direction:

```http
POST /api/v1/reverse
```

This requires:
- `reversible:true` set at original start.
- `enableUserWriteBlocking:true` set at original start.
- Same major version on both clusters.
- Same topology (replica set ↔ replica set, or sharded ↔ sharded).
- The destination cluster's oplog has **not** rolled past the `canWrite=true` moment.

After `reverse`, the original destination becomes source, and writes on the new source flow
back to the original source. **Filtered Sync is not supported during reverse** — reverse
syncs the full cluster.

### State machine summary

```
   IDLE ──start──▶ RUNNING ──pause──▶ PAUSED ──resume──▶ RUNNING
                       │                    │
                       │ commit             │ (auto from RUNNING/PAUSED)
                       ▼                    
                  COMMITTING ──(auto)──▶ COMMITTED
                       │
                       │ reverse (only with reversible=true)
                       ▼
                  REVERSING ──(auto)──▶ RUNNING (reverse direction)
```

State transitions are mostly API-driven; **COMMITTING→COMMITTED** and **REVERSING→RUNNING**
are automatic.

## 9. Performance Tuning

### loadLevel

- 1–4 scale. Default 3.
- Higher means more parallelism on both sides → faster initial sync, **more load on the
  destination**.
- Can be changed mid-sync by editing the config file and signaling mongosync.

### One mongosync per shard

For sharded sources, run one mongosync instance per shard for true parallel copy. Coordinate
them so they share the destination cluster's URI.

### Index builds

- Allocate 100 MB–1 GB of memory **per concurrent index build**.
- Keep total concurrent-index-build memory **under 20% of destination RAM**.
- mongosync defers some index builds until after initial sync to avoid contention.

### Balancer

**Disable the balancer on the sharded destination** (`sh.stopBalancer()` / `balancerStop`)
before starting the migration. The balancer fighting with mongosync inflates the migration
window and can cause chunk-move-vs-CDC races.

### Other tuning knobs

- Increase migration host CPU/RAM if CDC lag grows.
- Increase source oplog window proactively for long initial syncs.
- Use connection pooling URIs (`maxPoolSize`, `socketTimeoutMS`) tuned for your cluster.

## 10. Security — TLS & x.509

mongosync inherits MongoDB's standard auth. For production:

### TLS

- Use TLS for every connection — both `cluster0` and `cluster1` URIs should be `mongodb+srv`
  with TLS implied, or include `tls=true`.
- The mongosync host needs to trust the CA bundle for both clusters. Use the CA file via the
  URI parameter `tlsCAFile=`.
- mongod logs a warning if the presented certificate expires within 30 days — monitor cert
  expiry on the migration host as part of pre-flight checks.

### x.509 auth (recommended for self-managed source ↔ Atlas dest)

- Authentication mechanism: `MONGODB-X509`.
- `authSource=$external` in the connection URI.
- The DN of the migration host's client certificate must exist as a user in `$external` on
  both clusters with sufficient privileges.

### Required roles

The mongosync user on each cluster needs broad read/write across the synced namespaces plus:

- On source: read on every synced namespace, plus permission to open change streams.
- On destination: readWrite on every synced namespace, plus index creation, plus the
  metadata collections mongosync writes to.

Atlas exposes a built-in role specifically for mongosync (`Atlas Admin` is sufficient but
overpowered — use the documented minimal role set).

### Network security

- Migration host inside a VPC with private link or VPC peering to both clusters when
  possible.
- Lock the mongosync HTTP API to `127.0.0.1` (default) — it has no built-in auth.
- If you must expose the API, front it with a TLS-terminating reverse proxy + auth.

## Quick-reference checklist for a new mongosync migration

Pre-flight:
- [ ] Both clusters on MongoDB 6.0+, same major version.
- [ ] Migration host with ≥ 8 CPU, ≥ 24 GB RAM, network access to both.
- [ ] Source oplog window ≥ 2–3× expected initial sync duration.
- [ ] Destination cluster sized to absorb both sync load and post-cutover production load.
- [ ] TLS + x.509 (or strong password auth) wired up on both URIs.
- [ ] Balancer disabled on sharded destination.
- [ ] Users/roles recreated on destination (mongosync does NOT migrate them).

Configuration:
- [ ] Config file (not CLI password) — secrets out of `ps`.
- [ ] `reversible: true` and `enableUserWriteBlocking: true` if rollback is required.
- [ ] Filters reviewed — `includeNamespaces`/`excludeNamespaces` (cannot be changed later).
- [ ] `loadLevel` chosen for destination capacity.

Operate:
- [ ] Monitor `/api/v1/progress` for state + `lagTimeSeconds`.
- [ ] Watch source oplog window vs sync ETA.
- [ ] Run migration-verifier in parallel for sharded or high-mutation workloads.

Cutover:
- [ ] Quiesce source writes.
- [ ] `POST /commit`, wait for COMMITTED.
- [ ] Verify counts/hashes on destination.
- [ ] Flip app connection strings.
- [ ] Keep mongosync available for `reverse` until you're confident in the destination.

## Sources

- [Mongosync — MongoDB Docs (current)](https://www.mongodb.com/docs/mongosync/current/)
- [mongosync Quickstart](https://www.mongodb.com/docs/mongosync/current/quickstart/)
- [mongosync Configuration Reference](https://www.mongodb.com/docs/mongosync/current/reference/configuration/)
- [mongosync Binary Reference](https://www.mongodb.com/docs/cluster-to-cluster-sync/current/reference/mongosync/)
- [start API endpoint](https://www.mongodb.com/docs/mongosync/current/reference/api/start/)
- [resume API endpoint](https://www.mongodb.com/docs/mongosync/current/reference/api/resume/)
- [mongosync States](https://www.mongodb.com/docs/cluster-to-cluster-sync/current/reference/mongosync-states/)
- [Filtered Sync](https://www.mongodb.com/docs/mongosync/current/reference/collection-level-filtering/)
- [Regular Expressions in Filters](https://www.mongodb.com/docs/mongosync/current/reference/collection-level-filtering/filter-regex/)
- [Verify Data Transfer](https://www.mongodb.com/docs/mongosync/current/reference/verification/)
- [Verify with Hash Comparison](https://www.mongodb.com/docs/mongosync/current/reference/verification/hash/)
- [Verify with Migration Verifier](https://www.mongodb.com/docs/mongosync/current/reference/verification/verifier/)
- [migration-verifier (mongodb-labs)](https://github.com/mongodb-labs/migration-verifier)
- [oplog Sizing](https://www.mongodb.com/docs/mongosync/current/reference/oplog-sizing/)
- [Reverse Sync Direction](https://www.mongodb.com/docs/mongosync/current/reverse-sync/)
- [Finalize Cutover Process](https://www.mongodb.com/docs/mongosync/current/reference/cutover-process/)
- [Sync Sharded Clusters](https://www.mongodb.com/docs/cluster-to-cluster-sync/current/multiple-mongosyncs/)
- [Atlas Live Migration vs Mongosync](https://www.mongodb.com/docs/atlas/import/live-migration-comparison-modes/)
- [Mongosync product page](https://www.mongodb.com/products/tools/mongosync)
- [Mongosync FAQ](https://www.mongodb.com/docs/mongosync/current/faq/)
- [Provision a Migration Host for MongoDB Agent (Ops Manager)](https://www.mongodb.com/docs/ops-manager/v7.0/tutorial/provision-migration-host/)
- [X.509 Client Authentication on Self-Managed MongoDB](https://www.mongodb.com/docs/manual/tutorial/configure-x509-client-authentication/)
