<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-mongosync` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

# mongosync and Atlas Live Migration

Cluster-to-cluster synchronization for MongoDB-to-MongoDB migrations, DR patterns, and cross-cluster replication using mongosync and Atlas Live Migration Service.

## Overview

**mongosync** is a standalone binary that continuously replicates data from a source MongoDB cluster to a destination cluster with minimal downtime. It supports replica set to replica set, replica set to sharded cluster, and sharded cluster to sharded cluster topologies.

**Atlas Live Migration** is an Atlas-managed service that internally uses mongosync to perform pull-based migrations into Atlas. It trades flexibility for operational simplicity.

### When to Use mongosync

- Source cluster exceeds 5 TB or 3 shards (Atlas Live Migration threshold)
- You need pause/resume capability during migration
- Reverse sync (failback capability) is required
- Destination is on-premises or a non-Atlas MongoDB cluster
- Private networking / VPC peering with no third-party cluster access
- You need detailed progress logs and tunable parameters
- Source cluster has no authentication (Atlas Live Migration requires auth)
- Destination cluster has pre-existing data (with `preExistingDestinationData: true`)

### When to Use Atlas Live Migration

- Source cluster is at or below 5 TB / 3 shards
- Destination is Atlas and you want minimal infrastructure management
- MongoDB manages the migration infrastructure entirely
- Simpler cutover procedure with Atlas-guided wizard

### What mongosync Cannot Do

- Maintain a permanent DR secondary — it requires a `commit` to accept application traffic safely; destination is NOT safe for reads until `canWrite: true`
- Replicate `admin` database, user credentials, or roles
- Replicate system collections
- Guarantee destination matches source at any moment during sync (eventual consistency until commit)
- Perform rolling index builds on destination during sync

---

## 1. Architecture and Version Matrix

### Binary and Deployment Model

mongosync is a **single self-contained binary** (`mongosync`). It does not embed into your application server — it runs as a separate process on any machine that has network access to both clusters. Common deployment patterns:

- **Standalone process** — run on a dedicated migration host, a jump host, or a cloud VM
- **Sidecar** — run alongside the application in containerized environments (not recommended for production scale migrations due to resource contention)

The binary exposes an **HTTP REST API** on `127.0.0.1:27182` by default (configurable via `--port`). All control — start, pause, resume, commit, reverse — goes through this API. There is no separate CLI control; you drive it with `curl` or any HTTP client.

### Connection Model

mongosync connects to both clusters at startup using connection strings defined in its configuration file:

```yaml
# mongosync.conf (YAML format)
cluster0:
  connectionString: "mongodb+srv://user:pass@source-cluster.mongodb.net/?readConcern=majority&w=majority"
cluster1:
  connectionString: "mongodb://user:pass@dest-host:27017/?readConcern=majority&w=majority"
logPath: /var/log/mongosync.log
```

- `cluster0` and `cluster1` are logical names referenced in the `/start` body (`"source": "cluster0"`)
- Connection strings must include `readConcern=majority` and `writeConcern=majority` (or `w=majority`)
- Read preference must be `primary` for both clusters

### Version Compatibility Matrix

mongosync uses semantic versioning (`X.Y.Z`). Only the latest patch of each minor version is supported.

| mongosync Version | Supported MongoDB Source | Supported MongoDB Destination | Notes |
|---|---|---|---|
| 1.15.x (current) | 6.0, 7.0, 8.0 | 6.0, 7.0, 8.0 | Latest stable; live upgrades NOT supported from 1.14 |
| 1.14.x | 6.0, 7.0, 8.0 | 6.0, 7.0, 8.0 | Added `estimatedSecondsToCEACatchup` to /progress |
| 1.13.x | 6.0, 7.0, 8.0 | 6.0, 7.0, 8.0 | |
| 1.10.x | 5.0, 6.0, 7.0 | 5.0, 6.0, 7.0 | Last version supporting MongoDB 5.0 |
| 1.7.x+ | 5.0, 6.0, 7.0 | 5.0, 6.0, 7.0 | First version with live upgrade support |

Key rules:
- Supported MongoDB versions are defined per mongosync release (see table above); do not assume a version is supported by major-number comparison alone
- Source and destination do NOT need to be the same MongoDB version
- Pre-6.0 source: reverse sync not supported; write blocking on source not supported
- Versions not listed (e.g., 1.11, 1.12) follow the same MongoDB support range as the nearest listed minor; only milestone releases are shown above

### Process Management

mongosync does **not** auto-restart after a crash. Use a process supervisor to ensure it restarts automatically:

```ini
# /etc/systemd/system/mongosync.service
[Unit]
Description=mongosync migration process
After=network.target

[Service]
ExecStart=/usr/local/bin/mongosync --config /etc/mongosync.conf
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/mongosync.log
StandardError=append:/var/log/mongosync.log

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable mongosync && systemctl start mongosync
```

Health check: poll `/progress` — if it returns state `RUNNING` and `lagTimeSeconds` is not growing unboundedly, the process is healthy. A restart resumes from the last checkpoint (may take 2+ minutes before `/progress` responds).

### Load Level (Tunable Throughput)

The `loadLevel` configuration setting controls how aggressively mongosync uses source and destination cluster resources. Values: `1` (lowest) to `4` (highest). Default is `3`; setting it higher may negatively impact destination-cluster performance (see `references/mongosync.md` for the same tuning knob). For Atlas-managed migrations via Atlas Live Migration service, resource usage is tuned automatically; for standalone mongosync pointed at Atlas clusters, you set `loadLevel` explicitly.

```yaml
# mongosync.conf
cluster0:
  connectionString: "..."
cluster1:
  connectionString: "..."
loadLevel: 3
logPath: /var/log/mongosync.log
```

- Increase `loadLevel` to speed up Collection Copy when clusters have headroom
- Decrease `loadLevel` if source cluster latency increases during migration
- To change `loadLevel` mid-migration: call `/pause`, stop mongosync, edit the config file, restart mongosync, then call `/resume`. It cannot be changed by re-calling `/start` (which is only valid from IDLE state)

### Embedded Verifier

Starting with v1.9, mongosync ships with an **embedded verifier** (enabled by default). It performs hash-based verification comparing source and destination collections in parallel with CEA. Starting in v1.15, it also validates collection metadata, indexes, and views. It adds load to the destination and may require a larger oplog on the destination.

Disable only when you have an external validation strategy:
```json
{ "verification": { "enabled": false } }
```

---

## 2. Sync Phases Explained

mongosync moves through a defined state machine. Each state maps to a sync phase:

```
IDLE → (POST /start) → RUNNING [Collection Copy] → RUNNING [CEA] → (POST /commit) → COMMITTING → COMMITTED
                                                         ↑                                              ↓
                                                  (POST /pause)                             (POST /reverse)
                                                         ↓                                              ↓
                                                       PAUSED                               REVERSING → RUNNING [CEA]
                                                         ↓
                                                  (POST /resume)
```

### Phase 1: Collection Copy (RUNNING, info: "collection copy")

The initial bulk transfer. mongosync:

1. Enumerates all collections on source
2. **Partitions each collection** into segments (based on `_id` range or natural order)
3. Copies partitions in parallel to destination using bulk write operations
4. Simultaneously **opens a change stream** on source to buffer events that arrive during copy
5. Temporarily modifies destination collections: unique indexes become non-unique, TTL `expireAfterSeconds` set to MAX_INT, hidden indexes become visible — all restored at commit

Progress monitoring during Collection Copy:
```bash
curl -s localhost:27182/api/v1/progress | jq '.progress.collectionCopy'
# {"estimatedTotalBytes": 100000000, "estimatedCopiedBytes": 45000000}
```

**Large collection optimization:** For collections > 20 GiB with random-looking `_id` fields, mongosync detects this with `detectRandomId: true` (default) and switches to natural order copy, which is faster for random ObjectId distributions.

**Resource scaling:** For clusters ≤64 GB data / ≤4 CPUs, mongosync throttles concurrent writes automatically to prevent resource exhaustion.

### Phase 2: Change Event Application / CEA (RUNNING, info: "change event application")

After collection copy completes, CEA begins:

1. mongosync first **drains the buffered change events** captured during collection copy
2. Then switches to **live change stream** — oplog tailing in practice, since change streams are backed by the oplog
3. Applies all source write events (inserts, updates, deletes, DDL) to destination in near-real time

The key metric in CEA is **`lagTimeSeconds`** — the time difference between the most recently applied event on destination and the most recent event on source. When `lagTimeSeconds` approaches 0 and stays there, you are caught up.

mongosync sets `canCommit: true` once `lagTimeSeconds` reaches 0 (or near 0) and — if the embedded verifier is enabled — both `verification.source.phase` and `verification.destination.phase` show `"stream hashing"` with near-zero lag. `canCommit: true` is the signal to proceed with cutover.

**Index building during CEA:** When `buildIndexes: "afterDataCopy"` (default for MongoDB 6.0+), indexes are built during CEA rather than during collection copy. The `/progress` endpoint returns `indexBuilding` progress:
```json
"indexBuilding": {
  "indexesBuilt": 5,
  "totalIndexesToBuild": 10,
  "collectionsFinished": 2,
  "collectionsTotal": 4
}
```

**`estimatedSecondsToCEACatchup`** (added in v1.14) gives a countdown estimate:
```bash
curl -s localhost:27182/api/v1/progress | jq '.progress.estimatedSecondsToCEACatchup'
```

### Phase 3: Commit / Cutover (COMMITTING → COMMITTED)

Triggered by `POST /commit`. mongosync:

1. Records the **commit timestamp** — the time of the most recent operation on source
2. Continues applying CEA events until that timestamp is reached (draining any remaining lag)
3. Transitions to `COMMITTED`
4. Sets `canWrite: true` — destination is now safe for application traffic
5. Converts unique indexes from non-unique back to unique (resource-intensive; write latency may increase temporarily)
6. Restores TTL and hidden index settings

**Timeline note:** `canWrite: true` appears before the `COMMITTED` state is reached. Applications can start writing immediately at `canWrite: true`. Index conversion completes asynchronously.

### State Machine Summary

| State | Meaning | Valid Next API Calls |
|---|---|---|
| IDLE | Not started | /start |
| RUNNING | Syncing (copy or CEA) | /pause, /commit (if canCommit=true) |
| PAUSED | Sync paused | /resume |
| COMMITTING | Draining to commit timestamp | (automatic → COMMITTED) |
| COMMITTED | Sync finalized | /reverse (if reversible=true) |
| REVERSING | Reversing direction | (automatic → RUNNING) |

---

## 3. REST API Reference

All endpoints use `POST` (except `/progress` which is `GET`). Base URL: `http://localhost:27182/api/v1/`

### GET /progress

Poll this endpoint repeatedly to monitor all phases.

```bash
curl -s localhost:27182/api/v1/progress
```

**Key response fields:**

| Field | Type | Description |
|---|---|---|
| `state` | string | Current state: IDLE, RUNNING, PAUSED, COMMITTING, COMMITTED, REVERSING |
| `canCommit` | boolean | Safe to call /commit (CEA caught up) |
| `canWrite` | boolean | Destination accepts application writes |
| `info` | string | Sub-phase: "collection copy", "change event application", "waiting for commit to complete", "commit completed" |
| `lagTimeSeconds` | integer | Seconds behind source (null when PAUSED) |
| `totalEventsApplied` | integer | Cumulative change events applied |
| `collectionCopy.estimatedTotalBytes` | integer | Total bytes to copy |
| `collectionCopy.estimatedCopiedBytes` | integer | Bytes copied so far |
| `estimatedSecondsToCEACatchup` | integer | Estimated seconds until CEA is caught up (v1.14+) |
| `estimatedOplogTimeRemaining` | string | Human-readable oplog window remaining (e.g., "12 hours") |
| `indexBuilding.indexesBuilt` | integer | Indexes built in CEA phase |
| `indexBuilding.totalIndexesToBuild` | integer | Total indexes to build |
| `source.pingLatencyMs` | integer | Latency to source (refreshed every 30s; -1 means last ping failed) |
| `destination.pingLatencyMs` | integer | Latency to destination |
| `mongosyncID` | string | Instance identifier (needed for multi-shard setups) |
| `coordinatorID` | string | Coordinator instance ID |
| `warnings` | array | Non-fatal warnings (oplog concerns, write blocking issues) |

Full example response:
```json
{
  "progress": {
    "state": "RUNNING",
    "canCommit": true,
    "canWrite": false,
    "info": "change event application",
    "lagTimeSeconds": 0,
    "totalEventsApplied": 15240,
    "estimatedSecondsToCEACatchup": 0,
    "collectionCopy": {
      "estimatedTotalBytes": 694000000,
      "estimatedCopiedBytes": 694000000
    },
    "directionMapping": {
      "Source": "cluster0: source.mongodb.net",
      "Destination": "cluster1: dest.mongodb.net"
    }
  },
  "success": true
}
```

### POST /start

Initiates sync from IDLE state.

```bash
curl localhost:27182/api/v1/start -XPOST --data '{
  "source": "cluster0",
  "destination": "cluster1"
}'
```

**Key parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `source` | string | required | Logical cluster name from config file |
| `destination` | string | required | Logical cluster name from config file |
| `includeNamespaces` | array | (all) | Namespaces to include (see Section 5) |
| `excludeNamespaces` | array | (none) | Namespaces to exclude (v1.6+) |
| `reversible` | boolean | false | Enable reverse sync capability (requires MongoDB 6.0+ source) |
| `buildIndexes` | string | "afterDataCopy" | When to build indexes: `"afterDataCopy"`, `"beforeDataCopy"`, `"excludeHashed"`, `"excludeHashedAfterCopy"`, `"never"` |
| `detectRandomId` | boolean | true | Auto-detect random _id for natural order copy |
| `copyInNaturalOrder` | array | — | Force specific collections to copy in insertion order |
| `preExistingDestinationData` | boolean | false | Allow namespaces to exist on destination (requires namespace filter; Public Preview) |
| `verification.enabled` | boolean | true | Enable/disable embedded verifier |
| `sharding` | object | — | Shard configuration when syncing RS → sharded cluster |
| `enableUserWriteBlocking` | boolean | true (MongoDB 6.0+) | Block writes to source during sync; set false only for pre-6.0 or filtered-sync scenarios |

### POST /pause

Pauses an active sync. CEA stops applying events. `lagTimeSeconds` becomes null. Source writes continue accumulating.

```bash
curl localhost:27182/api/v1/pause -XPOST --data '{}'
```

Caution: while paused, oplog events on source continue to age. A very long pause may exhaust the oplog window.

### POST /resume

Resumes from PAUSED state. CEA restarts and catches up from where it paused.

```bash
curl localhost:27182/api/v1/resume -XPOST --data '{}'
```

### POST /commit

Initiates final cutover. Transitions to COMMITTING, then automatically to COMMITTED.

```bash
curl localhost:27182/api/v1/commit -XPOST --data '{}'
```

Only call when `canCommit: true`. This is irreversible unless `reversible: true` was set at start time.

### POST /reverse

Swaps source and destination after a committed migration. Requires `reversible: true` in the original `/start` call.

```bash
curl localhost:27182/api/v1/reverse -XPOST --data '{}'
```

### POST /stop

Stops mongosync entirely. Does not clean up destination data. Use to abandon a migration before commit.

```bash
curl localhost:27182/api/v1/stop -XPOST --data '{}'
```

---

## 4. Reverse Sync

Reverse sync lets you sync data from the destination back to the original source after cutover. The primary use case is **rollback** — if issues are discovered post-migration, you can fail back to the original cluster without losing any writes made to the destination.

### How It Works

After `POST /commit` completes:
1. Applications begin writing to destination (new source)
2. Call `POST /reverse`
3. mongosync enters REVERSING state, swaps cluster roles:
   - Original destination → new **source**
   - Original source → new **destination**
4. Automatically transitions back to RUNNING and starts CEA in the opposite direction
5. All writes that occurred on the destination after `canWrite: true` are now replicated back to the original source

### How to Enable

Set `reversible: true` in the `/start` body:

```bash
curl localhost:27182/api/v1/start -XPOST --data '{
  "source": "cluster0",
  "destination": "cluster1",
  "reversible": true
}'
```

### Calling /reverse

```bash
curl localhost:27182/api/v1/reverse -XPOST --data '{}'
```

After a successful /reverse call, mongosync enters RUNNING state syncing from destination → source. To finalize the reverse, call /commit again.

### Critical Gotchas and Limitations

**1. Oplog rollover risk**
The destination cluster's oplog must not roll over between `canWrite: true` and your `/reverse` call. If the destination oplog fills up before you call `/reverse`, the reverse sync cannot start. Monitor the destination oplog window and call `/reverse` promptly if rollback is needed.

**2. `reversible: true` must be set at start time**
You cannot enable reverse sync after sync has started. If you did not set `reversible: true` in `/start`, reverse is not available.

**3. Pre-6.0 source clusters**
Reverse sync is not supported when the original source was a MongoDB version older than 6.0.

**4. No filtered sync support during reverse**
If the original sync used `includeNamespaces` or `excludeNamespaces`, reverse sync is not supported.

**5. Legacy unique index format**
All unique indexes on the original source must use the current (non-legacy) format. Validate before calling /reverse by inspecting indexes on all collections:
```bash
# Check for legacy unique indexes on source
mongosh --uri "<source-connection-string>" --eval '
db.adminCommand({listDatabases:1}).databases.forEach(function(d){
  db.getSiblingDB(d.name).getCollectionNames().forEach(function(c){
    db.getSiblingDB(d.name).getCollection(c).getIndexes().forEach(function(i){
      if(i.unique && i.v < 2) print(d.name+"."+c+": legacy index "+i.name);
    });
  });
});'
```

**6. Metadata databases are point-of-no-return**
mongosync creates `__mdb_internal_mongosync` and `__mdb_internal_mongosync_verifier*` databases on the destination. Dropping these after migration makes reverse sync permanently impossible. Do not drop them until you have confirmed no rollback is needed.

**7. Topology constraint**
Source and destination must have the same number of shards. Different topologies (replica set vs sharded) cannot be reversed.

**8. Dual write blocking**
If you configured `enableUserWriteBlocking: true` in the original start call (the default for MongoDB 6.0+ replica sets), both clusters have write blocking managed by mongosync. Reverse sync will re-configure this appropriately. But if you configured non-default write blocking, validate behavior before using /reverse in production.

---

## 5. Sync Filters

Filters let you restrict what mongosync replicates. They are set in the `/start` body and cannot be changed once sync is running (stop, reset destination, restart with new filter).

### includeNamespaces

Only the listed databases/collections are replicated. Everything else on source is ignored.

```json
{
  "includeNamespaces": [
    { "database": "sales" },
    { "database": "marketing", "collections": ["campaigns", "leads"] },
    {
      "database": "analytics",
      "collectionsRegex": {
        "pattern": "^events_2024.*",
        "options": "i"
      }
    }
  ]
}
```

Filter syntax options (mutually exclusive within each entry):
- `"database": "name"` — entire database
- `"database": "name", "collections": ["c1","c2"]` — specific collections
- `"database": "name", "collectionsRegex": {"pattern":"...","options":"..."}` — regex match on collection names
- `"databaseRegex": {"pattern":"..."}` — regex match on database names

### excludeNamespaces (v1.6+)

Exclude specific databases or collections from an otherwise full sync. Can be combined with `includeNamespaces`: inclusion is applied first, then exclusions are removed from that set.

```json
{
  "excludeNamespaces": [
    { "database": "logs" },
    { "database": "app", "collections": ["sessions", "cache"] }
  ]
}
```

### Rename Collections During Filtered Sync

mongosync supports renaming collections on the destination through the `renameCollections` parameter. Restrictions:

- You can only rename a collection if the entire database is included in the filter, OR if both the old and new collection names are in the filter
- Cannot rename across databases when syncing RS → sharded cluster
- Rename violations cause mongosync to stop and report an error

### Shard Key Remapping (RS → Sharded Cluster)

When syncing from a replica set to a sharded cluster, use the `sharding` parameter to define shard keys for specific collections:

```json
{
  "source": "cluster0",
  "destination": "cluster1",
  "sharding": {
    "createSupportingIndexes": true,
    "shardingEntries": [
      {
        "database": "accounts",
        "collection": "transactions",
        "shardCollection": {
          "key": [
            { "customerId": 1 },
            { "region": 1 }
          ]
        }
      }
    ]
  }
}
```

- `createSupportingIndexes: true` — mongosync creates the required index for the shard key if it doesn't exist on source
- Each collection in `shardingEntries` is sharded on the destination using the specified key
- Collections not listed in `shardingEntries` land on the primary shard (unsharded)

### Filter Limitations

- Once started, filters are immutable — stop and restart to change them
- Views: if a view is included but its base collection is excluded, only view metadata is replicated (no documents)
- System collections and databases (`admin`, `config`, `local`) cannot be specified in filters
- `$out` aggregation and `mapReduce` output collections: must filter the entire database, not individual collections
- Filtered sync is incompatible with reverse sync

---

## 6. CEA Lag Monitoring

**`lagTimeSeconds`** is the most important operational metric during a live migration. It measures the time gap between the most recent operation on source and the most recent event mongosync has applied to destination.

### Reading the Metric

```bash
# Poll every 5 seconds
while true; do
  LAG=$(curl -s localhost:27182/api/v1/progress | jq '.progress.lagTimeSeconds')
  echo "$(date): lagTimeSeconds=$LAG"
  sleep 5
done
```

Target states:
- **Collection Copy phase**: `lagTimeSeconds` grows as events buffer (normal)
- **Early CEA phase**: `lagTimeSeconds` is elevated while catching up buffered events
- **Steady-state CEA**: `lagTimeSeconds` should drop to 0–5 seconds for a healthy migration
- **canCommit: true**: mongosync has determined lag is low enough to commit

### What Causes High CEA Lag

1. **High source write rate** — more events per second than mongosync can apply
2. **Undersized destination** — destination disk I/O, CPU, or write throughput is insufficient
3. **Large transactions on source** — cross-shard or large multi-document transactions take longer to apply
4. **Slow destination writes** — check destination CPU, IOPS, network latency; `destination.pingLatencyMs` in /progress
5. **Index building contention** — if `buildIndexes: "afterDataCopy"`, index builds compete with CEA writes
6. **Network latency** — high round-trip time between mongosync host and either cluster

### Sizing the Destination to Keep Up

Key rule: **destination must have at least as much CPU and I/O capacity as the source at peak write load**. Since mongosync writes with `w: majority, j: true`, destination writes are durability-constrained.

Recommended destination sizing:
- CPU: match or exceed source
- Memory: match source (WiredTiger cache)
- Disk: data size × 2 (data + oplog entries from initial sync) + additional buffer if using embedded verifier
- Network: 10 Gbps or dedicated VPC peering for clusters in cloud environments

### Oplog Window Monitoring

mongosync's `/progress` reports `estimatedOplogTimeRemaining` — how much oplog history remains on the source before events mongosync needs are evicted:

```bash
curl -s localhost:27182/api/v1/progress | jq '.progress.estimatedOplogTimeRemaining'
# "5 hours"
```

If this value drops below 1 hour, take action immediately:

**Option A: Increase source oplog** (self-managed)
```javascript
db.adminCommand({
  replSetResizeOplog: 1,
  minRetentionHours: 24
})
```

**Option B: Increase source oplog** (Atlas)
— Atlas → Cluster → Additional Settings → Minimum Oplog Window

**Option C: Scale up mongosync host** — more CPU/memory allows faster copy and CEA processing

**Option D: Reduce source write load** — throttle application writes if possible

### Oplog Window Calculation

To estimate the required oplog window before starting:

```javascript
// Run on each shard (use smallest value)
db.getReplicationInfo()
// Shows: log length start to end: N secs (X hrs)
// oplog first event time, oplog last event time
```

Rule of thumb: source oplog window should cover at minimum `(data size in GB / expected copy throughput in GB/hr)` + safety margin of 2× the expected Collection Copy duration. Example: migrating 500 GB at ~50 GB/hr copy throughput = 10 hours copy time → set oplog window to at least 20–24 hours. Typical mongosync copy throughput on a dedicated VM with low network latency is 20–100 GB/hr depending on document size, index count, and cluster tier. If throughput is unknown, start with a 48-hour oplog window.

---

## 7. mongosync vs Atlas Live Migration

### Architecture Difference

| Dimension | Atlas Live Migration | Standalone mongosync |
|---|---|---|
| **Who runs it** | MongoDB / Atlas infrastructure | You (on your own VM or host) |
| **Direction** | Pull (Atlas connects to source) | You connect to both; mongosync runs on your infrastructure |
| **Destination** | Must be Atlas cluster | Atlas or any MongoDB cluster |
| **Source location** | On-premises or Atlas | On-premises or Atlas |
| **Size limit** | ≤ 5 TB, ≤ 3 shards | No hard limits (tunable) |

### Feature Comparison

| Feature | Atlas Live Migration | Standalone mongosync |
|---|---|---|
| Pause / Resume | No | Yes |
| Reverse sync | No | Yes (if reversible=true) |
| Tunable parameters | No | Yes (load level, buildIndexes, etc.) |
| Direct log access | No (limited Atlas logs) | Yes |
| Pre-existing destination data | No | Yes (preExistingDestinationData) |
| Unauthenticated source | No | Yes |
| Namespace filtering | Yes | Yes (more granular) |
| Post-migration verification | Yes (built-in) | Yes (embedded verifier) |
| VPC Peering / Private Link | Yes | Yes |
| Geographic availability | Limited Atlas regions | Anywhere |
| Setup complexity | Low (wizard-driven) | Higher (manual config) |

### Cutover Procedure Differences

**Atlas Live Migration cutover:**
1. Atlas shows migration status in the UI
2. When lag is low, Atlas UI enables "Start Cutover" button
3. You confirm cutover in Atlas UI
4. Atlas stops source writes (or you stop them manually)
5. Atlas completes the migration and removes the link to source
6. No ability to reverse

**Standalone mongosync cutover:**
1. Poll `/progress` until `canCommit: true` and `lagTimeSeconds` is near 0
2. Stop application writes to source
3. Call `POST /commit`
4. Poll `/progress` until `canWrite: true`
5. Update connection strings to point to destination
6. Optional: call `POST /reverse` within the oplog window if rollback is needed

### Migration Decision Tree

```
Source > 5 TB OR > 3 shards?
  YES → Use standalone mongosync
  NO  →
    Need rollback / reverse sync?
      YES → Use standalone mongosync
      NO  →
        Want minimal setup?
          YES → Use Atlas Live Migration
          NO  → Use standalone mongosync (more control)
```

---

## 8. Common Failure Modes

### Failure 1: Oplog Window Overflow

**Symptom:** mongosync exits with an error like "change stream event has been lost" or "resume token no longer available"

**Cause:** Source oplog rolled past the point mongosync last read. This can happen during:
- Very long Collection Copy on large clusters
- Extended pause periods
- Mongosync crash followed by delayed restart

**Remediation:**
1. Increase source oplog size (`replSetResizeOplog` or Atlas Minimum Oplog Window)
2. Restart mongosync from scratch: delete all migrated data on destination (including `__mdb_internal_mongosync` and any `__mdb_internal_mongosync_verifier*` databases), reset destination, relaunch
3. For prevention: monitor `estimatedOplogTimeRemaining` and alert at < 2 hours

### Failure 2: Write Concern Errors on Destination

**Symptom:** mongosync logs contain write concern timeout or `WriteConcernFailed` errors

**Cause:** Destination replica set members falling behind primary (secondary lag). mongosync uses `w: majority, j: true` — all writes must be acknowledged by a majority of the replica set.

**Remediation:**
- Check destination secondary replication lag: `rs.printSecondaryReplicationInfo()`
- Ensure destination has sufficient disk I/O for journaling
- Check network between primary and secondaries
- Consider temporarily scaling up destination instance size

### Failure 3: Authentication Failures

**Symptom:** mongosync fails to connect at startup or transitions to an error state with auth errors

**Common causes:**
- Connection string credentials expired or rotated
- SCRAM auth challenge/response timeout
- X.509 certificate expiry
- LDAP server unreachable

**Remediation:**
- Verify credentials by connecting directly: `mongosh "<connection-string>"`
- For X.509: check certificate expiry dates
- For LDAP: verify LDAP server connectivity from mongosync host
- For Atlas: ensure IP Access List includes the mongosync host IP

### Failure 4: Duplicate Key Errors

**Symptom:** mongosync logs contain `E11000 duplicate key error` entries

**Cause:** This is **normal and expected** behavior, not a fatal error. Duplicate key errors occur because:
- During Collection Copy, mongosync copies documents directly AND may apply a redundant insert from the buffered change stream
- After pause/resume cycles, events may be replayed
- Retryable error recovery replays writes

mongosync deduplicates these gracefully. Only stop if you see fatal errors.

### Failure 5: Conflicting Indexes / Index Build Failures

**Symptom:** mongosync stops with an index-related error

**Common causes:**
- Inconsistent indexes across shards on source (v1.14+ reports these as fatal)
- Destination already has an incompatible index on the same key
- Rolling index builds running on source during migration

**Remediation:**
- Run `db.collection.getIndexes()` on all shards to find inconsistencies
- Fix inconsistent indexes on source before restarting
- Avoid rolling index builds on source during migration; schedule them before or after
- Use `buildIndexes: "never"` to skip index creation and build manually post-migration

### Failure 6: Network Timeout During Collection Copy

**Symptom:** `MaxTimeMSExpired` errors in mongosync logs during Collection Copy

**Cause:** mongosync read or write operations exceeding timeout thresholds, often due to:
- Large documents causing slow cursor iteration
- Network packet loss between mongosync host and cluster
- Source cluster under heavy CPU load slowing cursor responses

**Remediation:** (v1.14+ has improved retry logic for these errors)
- Move mongosync host closer to both clusters (same cloud region/VPC)
- Check source cluster CPU and connection pool utilization
- Increase VM resources for mongosync host
- Reduce source cluster write load if possible

### Failure 7: Fatal Errors — Recovery Procedure

When mongosync encounters a fatal error and exits:

```bash
# Step 1: Identify the error in logs
grep -i "fatal" /var/log/mongosync.log | tail -20

# Step 2: Address root cause (see failure modes above)

# Step 3: Clean destination cluster — drop ALL migrated data including metadata
# Run in mongosh (JavaScript):
mongosh --uri "<destination-connection-string>" --eval '
  // Drop all synced user databases (NOT admin, config, local)
  db.getMongo().getDBNames().forEach(function(dbName) {
    if (!["admin","config","local"].includes(dbName)) {
      print("Dropping: " + dbName);
      db.getMongo().getDB(dbName).dropDatabase();
    }
  });
  // Drop mongosync internal metadata databases
  ["__mdb_internal_mongosync"].concat(
    db.getMongo().getDBNames().filter(n => n.startsWith("__mdb_internal_mongosync_verifier"))
  ).forEach(function(dbName) {
    print("Dropping metadata db: " + dbName);
    db.getMongo().getDB(dbName).dropDatabase();
  });
'

# Step 4: Relaunch mongosync and POST /start again
mongosync --config /etc/mongosync.conf
curl localhost:27182/api/v1/start -XPOST --data '{ "source": "cluster0", "destination": "cluster1" }'
```

### Failure 8: movePrimary / moveChunk During Migration

**Symptom:** mongosync enters a fatal error state after a `movePrimary` or `moveChunk` on source

**Cause:** These operations alter chunk distribution during an in-flight migration, which can corrupt mongosync's tracking state.

**Remediation:** Never run `movePrimary`, `moveChunk`, or `moveRange` on either cluster during an active mongosync migration. Disable the balancer on both clusters before starting.

---

## 9. Sharded Cluster Sync

Syncing sharded clusters requires running **one mongosync instance per shard** on the source. Each instance is identified by an `--id` parameter that maps to a specific shard.

### Instance Count and ID Assignment

```bash
# For a 3-shard source cluster, run 3 mongosync processes
# Each process has its own config file and unique --id

# Shard 0
mongosync --id "shard0" --config /etc/mongosync-shard0.conf

# Shard 1
mongosync --id "shard1" --config /etc/mongosync-shard1.conf

# Shard 2
mongosync --id "shard2" --config /etc/mongosync-shard2.conf
```

Each instance connects to its specific shard (not the mongos). The connection string in each config points to the shard's replica set:

```yaml
# mongosync-shard0.conf
cluster0:
  connectionString: "mongodb://shard0-rs/host1:27017,host2:27017,host3:27017/?replicaSet=shard0-rs&readConcern=majority&w=majority"
cluster1:
  connectionString: "mongodb://dest-shard0-rs/desthost1:27017,.../?replicaSet=dest-shard0-rs&readConcern=majority&w=majority"
```

### Coordinator Pattern

One instance is designated the **coordinator**. The coordinator synchronizes the other instances and controls state transitions across all shards. State-mutation endpoints (`/start`, `/pause`, `/resume`, `/commit`, `/reverse`, `/stop`) must be called on the coordinator — it propagates the action to all shard instances. Calling these endpoints on a non-coordinator instance returns an error. The `/progress` endpoint can be called on any instance. To identify the coordinator, call `/progress` on each instance and find the one whose `mongosyncID` matches its own `coordinatorID`.

You can identify the coordinator via the `coordinatorID` field in `/progress`.

### Config Server Handling (MongoDB 8.0+)

Starting in MongoDB 8.0, config shards (embedded config server clusters) are supported. mongosync supports sync between:
- Dedicated config server sharded cluster → embedded config server sharded cluster
- Embedded → dedicated

This allows migrations between pre-8.0 and 8.0+ Atlas clusters without topology changes.

### Zone Mapping Behavior

**Critical:** mongosync does NOT replicate zone (shard tag) configurations. Zones on source are not created on destination.

Pre-migration procedure:
```javascript
// On DESTINATION cluster — remove all zone ranges from namespaces mongosync will migrate into
// Signature: sh.removeRangeFromZone(namespace, minimum, maximum, zone)
sh.removeRangeFromZone("mydb.mycoll", { shardKey: MinKey }, { shardKey: MaxKey }, "ZoneName");
// Repeat for every zone range on every namespace being migrated
```

After `COMMITTED`, manually re-add the desired zone ranges on destination:
```javascript
// Signature: sh.addTagRange(namespace, minimum, maximum, zone)
sh.addTagRange("mydb.mycoll", { shardKey: MinKey }, { shardKey: MaxKey }, "ZoneName");
```

### Balancer Management

Before starting mongosync on sharded clusters:
```javascript
// Disable balancer on destination
use admin
db.adminCommand({ balancerStop: {} })
// Wait for in-flight migrations to complete (up to 15 minutes)

// Verify balancer stopped
sh.isBalancerRunning()
```

Starting in v1.17, mongosync auto-disables the balancer during initialization. For earlier versions, disable manually.

Do NOT run `moveChunk`, `moveRange`, or `movePrimary` on either cluster during migration.

### Cutover for Sharded Clusters

Same procedure as replica sets, but call commit on the coordinator instance. mongosync coordinates commit across all shards:

1. Call `POST /commit` on the coordinator
2. All shard instances enter COMMITTING simultaneously
3. Poll coordinator's `/progress` for `canWrite: true`
4. Update application connection strings (point to destination mongos)

---

## 10. Production Cutover Checklist

A systematic pre/during/post cutover procedure for production migrations.

### T-minus 1 Week: Pre-Migration Preparation

- [ ] Verify mongosync version compatibility with source and destination MongoDB versions
- [ ] Provision mongosync host in same cloud region/VPC as clusters (minimize latency)
- [ ] Confirm destination cluster is sized at ≥ source (CPU, RAM, IOPS)
- [ ] Estimate destination disk: `(source data size × 2) + 20% buffer`
- [ ] **Recreate users, roles, and `admin` database objects on destination** — mongosync does NOT replicate admin DB
- [ ] Disable balancer on destination sharded cluster (or verify v1.17+)
- [ ] Remove zone ranges from destination namespaces
- [ ] Pre-stage DNS: lower TTL on database DNS aliases to 60s or less (so failover is fast)
- [ ] Document all application connection strings and driver config (need exact values for cutover)
- [ ] Set up monitoring for `lagTimeSeconds` and `estimatedOplogTimeRemaining`

### T-minus 1 Day: Sync Initiation

```bash
# Start mongosync
mongosync --config /etc/mongosync.conf &

# Initiate sync
curl localhost:27182/api/v1/start -XPOST --data '{
  "source": "cluster0",
  "destination": "cluster1",
  "reversible": true
}'
```

- [ ] Confirm state transitions to RUNNING
- [ ] Verify Collection Copy progress is advancing: `collectionCopy.estimatedCopiedBytes` increasing
- [ ] Set up alerting: if `estimatedOplogTimeRemaining < 2 hours`, page on-call

### T-minus Hours: Approach Cutover

Monitor until CEA is healthy:
```bash
watch -n5 'curl -s localhost:27182/api/v1/progress | jq ".progress | {state: .state, canCommit: .canCommit, lagTimeSeconds: .lagTimeSeconds, estimatedOplogTimeRemaining: .estimatedOplogTimeRemaining}"'
```

- [ ] `lagTimeSeconds` is consistently ≤ 5 across multiple polling intervals
- [ ] `canCommit: true`
- [ ] `estimatedOplogTimeRemaining` is comfortable (> 4 hours ideally)
- [ ] If using embedded verifier: both `verification.source.phase` and `verification.destination.phase` show `"stream hashing"` with near-zero lag
- [ ] Communicate maintenance window to stakeholders

### Cutover Sequence

**Step 1: Stop application writes**
- Stop or fence all application instances that write to source cluster
- Or: set `readOnly: true` in application config and roll out
- Verify no writes are reaching source: check `db.currentOp()` on source

**Step 2: Wait for lag to reach 0**
```bash
while true; do
  PROGRESS=$(curl -s localhost:27182/api/v1/progress)
  LAG=$(echo "$PROGRESS" | jq '.progress.lagTimeSeconds')
  CAN_COMMIT=$(echo "$PROGRESS" | jq '.progress.canCommit')
  echo "$(date): lagTimeSeconds=$LAG canCommit=$CAN_COMMIT"
  [[ "$LAG" == "0" ]] && [[ "$CAN_COMMIT" == "true" ]] && break
  sleep 2
done
```

**Step 3: Issue commit**
```bash
curl localhost:27182/api/v1/commit -XPOST --data '{}'
```

**Step 4: Wait for canWrite**
```bash
until [[ "$(curl -s localhost:27182/api/v1/progress | jq '.progress.canWrite')" == "true" ]]; do
  echo "Waiting for canWrite..."; sleep 2
done
echo "Destination is ready for writes"
```

**Step 5: Update connection strings**
- Update application configuration to point to destination cluster
- For Atlas: use the new SRV connection string
- For on-prem: update `mongodb://` URI or DNS alias

**Step 6: Start applications**
- Restart application instances pointing to destination
- Verify traffic is flowing to destination: check Atlas metrics or `db.currentOp()` on destination

**Step 7: Post-cutover validation**
```javascript
// Spot-check document counts
db.getSiblingDB("mydb").myCollection.countDocuments()
// Compare with source count captured before cutover

// Verify recently modified documents
db.myCollection.find({ updatedAt: { $gte: new Date(Date.now() - 3600000) } }).limit(10)
```

- [ ] Application health checks pass
- [ ] Error rates are nominal
- [ ] Query latency is within expected range
- [ ] Document counts match source (captured pre-cutover)

**Step 8: Wait for COMMITTED state**
```bash
until [[ "$(curl -s localhost:27182/api/v1/progress | jq -r '.progress.state')" == "COMMITTED" ]]; do
  echo "Waiting for COMMITTED..."; sleep 5
done
echo "Migration COMMITTED"
```

### Post-Cutover: Reverse Sync Window (if reversible=true)

After cutover, you have a **limited window** to call `/reverse` before the destination oplog fills:

```bash
# Decision point: commit to migration or roll back?
# If rollback is needed:
curl localhost:27182/api/v1/reverse -XPOST --data '{}'
# Then wait for RUNNING state and repeat cutover procedure back to source

# If migration is confirmed successful:
# 1. Leave mongosync metadata databases intact until fully confident
# 2. When permanently done, drop metadata databases
mongosh --eval 'db.getMongo().getDB("__mdb_internal_mongosync").dropDatabase()'
# This makes the migration irreversible
```

### DNS TTL Staging

Pre-stage DNS changes before cutover to minimize application reconnection time:

```bash
# T-1 day: lower TTL
# e.g., Route53 record for db.internal → source-cluster
# Change TTL from 300s → 30s (takes 5 minutes to propagate)

# At cutover: update DNS record to point to destination
# Applications reconnect within 30s as their cached DNS entries expire
```

For Atlas SRV strings (`mongodb+srv://`), the SRV TTL is controlled by Atlas. Prefer using the Atlas connection string directly rather than a DNS alias for the most reliable behavior.

### Rollback Decision Criteria

Execute rollback (call `/reverse`) while still within the reverse sync window (before the destination oplog rolls over — monitor `estimatedOplogTimeRemaining` on the destination) if you observe:
- Application error rate > 5%
- Critical query returning wrong results
- Data integrity check failing
- Performance > 3× worse than source baseline

Do NOT roll back for:
- Temporary connection pool reconvergence (normal for first 2–5 minutes)
- Cold cache performance (WiredTiger cache needs warm-up on destination)
- DNS propagation lag (wait 60s before declaring failure)

---

## References and See Also

### Official Documentation
- [mongosync Overview](https://www.mongodb.com/docs/mongosync/current/) — current version landing page
- [mongosync About Page](https://www.mongodb.com/docs/mongosync/current/about-mongosync/) — architecture and design
- [REST API Reference](https://www.mongodb.com/docs/mongosync/current/reference/api/) — all endpoints
- [Finalize Cutover Process](https://www.mongodb.com/docs/mongosync/current/reference/cutover-process/) — official cutover guide
- [Reverse Sync Direction](https://www.mongodb.com/docs/mongosync/current/reverse-sync/) — reverse sync procedure
- [Filtered Sync (Collection Level)](https://www.mongodb.com/docs/mongosync/current/reference/collection-level-filtering/) — namespace filters
- [Sync Sharded Clusters](https://www.mongodb.com/docs/cluster-to-cluster-sync/current/multiple-mongosyncs/) — multi-instance setup
- [oplog Sizing](https://www.mongodb.com/docs/mongosync/current/reference/oplog-sizing/) — oplog calculations
- [mongosync FAQ](https://www.mongodb.com/docs/mongosync/v1.15/faq/) — common questions
- [mongosync Behavior](https://www.mongodb.com/docs/mongosync/current/reference/mongosync-behavior/) — limitations and behavior details
- [Versioning](https://www.mongodb.com/docs/mongosync/current/reference/versioning/) — compatibility matrix
- [Atlas Live Migration vs mongosync Comparison](https://www.mongodb.com/docs/atlas/import/live-migration-comparison-modes/) — decision guide
- [Atlas Pull Live Migration](https://www.mongodb.com/docs/atlas/import/c2c-pull-live-migration/) — Atlas-managed migration guide
- [Release Notes 1.15](https://www.mongodb.com/docs/mongosync/current/release-notes/1.15/) — latest version changes
- [Release Notes 1.14](https://www.mongodb.com/docs/mongosync/current/release-notes/1.14/) — v1.14 changes

### Related Skills
- **mongodb-migration-patterns** — broader MongoDB migration strategies, tooling overview
- **mongodb-relational-migrator** — relational-to-MongoDB migrations with schema conversion
- **mongodb-replication** — replica set internals, oplog mechanics, replication lag
- **mongodb-sharding** — sharded cluster architecture, balancer, zone configuration
- **mongodb-disaster-recovery** — DR strategies including mongosync-based DR patterns
