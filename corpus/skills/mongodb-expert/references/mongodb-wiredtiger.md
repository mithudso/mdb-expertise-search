<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-wiredtiger` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-wiredtiger
title: MongoDB WiredTiger Storage Engine
version: "1.1.0"
last-updated: "2026-05-29"
category: mongodb
description: >
  Deep expertise in WiredTiger internals, cache tuning, eviction mechanics, checkpoint behavior,
  journaling, compression, and storage diagnostics for MongoDB deployments.
  TRIGGER: questions containing "wiredtiger", "cache pressure", "cache full", "eviction",
  "checkpoint stall", "dirty bytes", "application thread eviction", "cache miss",
  "compact collection", "cacheSizeGB", "cache utilization", "WiredTigerHS",
  "MVCC history store", "journal commit", "compression snappy/zstd/zlib",
  "serverStatus wiredTiger", "FTDC wiredtiger", "storage engine", "block compressor",
  "eviction_dirty_target", "eviction_trigger", "autoCompact", or diagnosing why
  MongoDB RAM usage is unexpectedly high, checkpoint spikes every 60 seconds,
  or application-thread eviction appearing in metrics.
  SKIP: general query performance unrelated to storage engine (use mongodb-query-performance),
  replication lag diagnosis (use mongodb-replication), Atlas capacity-planning tier selection
  (use mongodb-capacity-planning), index strategy and type selection (use mongodb-indexes-deep).
tags:
  - wiredtiger
  - storage-engine
  - cache
  - eviction
  - checkpoint
  - journal
  - compression
  - diagnostics
  - performance
  - mongodb
keywords:
  - wiredtiger
  - cache pressure
  - cache full
  - eviction
  - checkpoint stall
  - dirty bytes
  - application thread eviction
  - cache miss
  - compact collection
  - cacheSizeGB
  - cache utilization
  - WiredTigerHS
  - MVCC history store
  - journal commit
  - compression snappy zstd
  - serverStatus wiredTiger
  - FTDC wiredtiger
  - storage engine
  - block compressor
  - eviction_dirty_target
  - eviction_trigger
  - autoCompact
  - directoryPerDB
  - directoryForIndexes
whenToUse:
  - Cache pressure alerts (high utilization, dirty bytes climbing, app thread evictions)
  - Checkpoint stalls causing latency spikes under heavy write load
  - Diagnosing slow queries that stem from cache misses rather than missing indexes
  - Choosing or changing compression algorithm (snappy vs zstd vs zlib vs none)
  - Interpreting db.serverStatus().wiredTiger output or FTDC diagnostic files
  - Planning storage layout (directoryPerDB, directoryForIndexes) for new deployments
  - Compacting collections to reclaim disk space after large bulk deletes
  - Long-running transactions causing history store growth or checkpoint slowdowns
  - Container/Kubernetes deployments where cacheSizeGB must be set explicitly
  - Sharded clusters with per-shard cache sizing requirements
whenNotToUse:
  - General query performance not related to the storage engine — use mongodb-query-performance
  - Replication lag diagnosis — use mongodb-replication
  - Atlas tier selection and capacity planning — use mongodb-capacity-planning
  - Index type and strategy selection — use mongodb-indexes-deep
  - Multi-document transaction design — use mongodb-transactions (unless the question is specifically about MVCC interaction)
  - WiredTiger source-code internals or custom builds — use mongodb-wiredtiger-internals
related_skills:
  - mongodb-expert
  - mongodb-performance-troubleshooting
  - mongodb-capacity-planning
  - mongodb-monitoring-observability
  - mongodb-indexes-deep
  - mongodb-transactions
  - mongodb-wiredtiger-internals
---

# MongoDB WiredTiger Storage Engine

Deep expertise in WiredTiger internals, cache tuning, eviction mechanics, checkpoint behavior, journaling, compression, and storage diagnostics for MongoDB deployments.

## Overview

WiredTiger has been MongoDB's default storage engine since MongoDB 3.2. It replaced the original MMAPv1 engine and delivers document-level locking, MVCC-based concurrency, configurable compression, and a write-ahead journal. Understanding WiredTiger internals is essential for diagnosing performance bottlenecks, right-sizing cache, interpreting `serverStatus` metrics, and planning capacity.

## When to Use This Skill

**Activation triggers**: "wiredtiger", "cache pressure", "cache full", "eviction", "checkpoint stall", "dirty bytes", "application thread eviction", "cache miss", "compact collection", "storage engine", "cacheSizeGB", "cache utilization", "WiredTigerHS", "MVCC history store", "journal commit", "compression snappy zstd", "serverStatus wiredTiger", "FTDC wiredtiger"

- Cache pressure alerts (high cache utilization, "bytes dirty" climbing, application thread evictions appearing)
- Checkpoint stalls causing latency spikes under heavy write load
- Diagnosing slow queries that stem from cache misses rather than missing indexes
- Choosing compression algorithm for a new collection or migrating an existing one
- Interpreting `db.serverStatus().wiredTiger.*` output or FTDC diagnostics files
- Planning storage layout (directoryPerDB, directoryForIndexes) for new deployments
- Compacting collections to reclaim disk space after large bulk deletes
- Understanding why a long-running transaction is holding back cache eviction or checkpoint progress
- Sharding deployments where per-shard cache sizing differs from single-node guidance

**Output contract**: Provide diagnosis first (metric values + threshold comparison), then root cause, then ordered remediation steps. Include copy-pasteable `db.serverStatus()` snippets for verification. Flag Atlas-specific constraints (no direct cacheSizeGB tuning) where relevant.

---

## 1. WiredTiger Architecture

### Data Model: B-Trees and Pages

WiredTiger stores all data — collections and indexes — in B-tree structures on disk. Each collection maps to a dedicated `.wt` file (e.g., `collection-7-123456789.wt`). Each index has its own `.wt` file as well. The catalog mapping MongoDB namespaces to WiredTiger URIs is stored in `_mdb_catalog.wt`.

A B-tree in WiredTiger is composed of three page types:

| Page Type | Description |
|-----------|-------------|
| Root page | Entry point of the tree; contains root checksum, size, offset |
| Internal pages | Key-only pages used for B-tree traversal |
| Leaf pages | Actual key-value pairs; the bulk of data storage |

Pages are the unit of I/O between disk and the WiredTiger cache. When a page is needed, it is read from the `.wt` file into the cache in its compressed, on-disk format, then decompressed into the in-memory (uncompressed) representation. Reads from the OS page cache can serve the compressed form without disk I/O; decompression still occurs.

### MVCC: Multi-Version Concurrency Control

WiredTiger implements MVCC using a **No-Force / No-Steal** policy:

- **No-Force**: Committed data need not be immediately flushed to disk (checkpoint handles eventual persistence).
- **No-Steal**: Uncommitted changes are not written to disk (they cannot "steal" page slots from committed data in data files).

When a document is updated, WiredTiger does not overwrite the existing on-disk record. Instead, it creates a new version in the cache. Readers snapshot a consistent view via a 64-bit logical timestamp. This eliminates the transaction-ID wraparound risk that PostgreSQL must manage with `VACUUM`.

**Update chain**: When a dirty page is reconciled (written out during eviction or checkpoint), WiredTiger examines the update chain and chooses the latest committed version as the on-disk value. Older committed versions that are still needed by open snapshots are written to the **history store** (`WiredTigerHS.wt`). Obsolete versions are discarded.

### Durable History Store (WiredTigerHS.wt)

`WiredTigerHS.wt` is a special B-tree that holds older committed document versions for MVCC. Its composite key is:

```
(table_id: u32, record_key: variable, start_ts: u64, counter: u64)
```

Its value stores: stop timestamp, durable timestamp, update type, full BSON document (before-image).

Historical versions are retained for up to `minSnapshotHistoryWindowInSeconds` (default: 300 seconds / 5 minutes). Long-running transactions prevent version eviction from the history store, causing it to grow and consume cache. This is a common root cause of cache pressure that does not resolve by simply enlarging `wiredTigerCacheSizeGB`.

### Document-Level Locking

WiredTiger achieves document-level write locking through its optimistic concurrency model:

- Each write acquires an **intent lock** at the database and collection level.
- An **exclusive lock** is taken only on the specific document being modified.
- Multiple threads can concurrently modify different documents in the same collection without contention.

This is a fundamental improvement over MMAPv1's collection-level locking. In practice, write contention in MongoDB workloads today is far more likely to manifest as WiredTiger ticket exhaustion (`wiredTiger.concurrentTransactions.write.available → 0`) than as document-level lock conflicts.

### File Layout on Disk

Default layout with `dbPath: /data/db`:

```
/data/db/
  WiredTiger               # WiredTiger metadata
  WiredTiger.lock          # Process lock
  WiredTiger.turtle        # Root of the WiredTiger metadata B-tree
  WiredTigerHS.wt          # MVCC history store
  _mdb_catalog.wt          # Namespace → storage URI catalog
  collection-*.wt          # Collection data files
  index-*.wt               # Index data files
  journal/                 # Write-ahead log files
  diagnostic.data/         # FTDC files
```

With `storage.directoryPerDB: true`, each database gets its own subdirectory. With `storage.wiredTiger.engineConfig.directoryForIndexes: true`, indexes are separated into a `collection/` and `index/` subdirectory per database — useful for placing indexes on faster storage.

**Important**: Changing `directoryPerDB` or `directoryForIndexes` on an existing deployment requires a full resync of the affected node.

---

## 2. Cache Sizing

### Default Formula

```
wiredTigerCacheSize = max(0.5 × (RAM − 1 GB), 256 MB)
```

Examples:
- 8 GB RAM → cache = max(3.5 GB, 256 MB) = **3.5 GB**
- 16 GB RAM → cache = max(7.5 GB, 256 MB) = **7.5 GB**
- 4 GB RAM → cache = max(1.5 GB, 256 MB) = **1.5 GB**
- 512 MB RAM → cache = max(−244 MB, 256 MB) = **256 MB** (floor)

The valid configuration range is 256 MB to 10,000 GB.

### Why 50% and Not More

MongoDB operates a **two-layer caching architecture**:

1. **WiredTiger cache**: Holds decompressed pages (the "hot" working set).
2. **OS page cache**: Holds compressed `.wt` file blocks read from or written to disk.

Leaving ~40–50% of RAM to the OS page cache allows reads to be served from compressed blocks in OS memory rather than triggering disk I/O. This is the primary reason the WiredTiger cache should not be set above ~70% of RAM: the freed memory benefits the OS page cache more than it would benefit a larger WiredTiger cache.

### Configuration

In `mongod.conf`:

```yaml
storage:
  wiredTiger:
    engineConfig:
      cacheSizeGB: 14  # for a 32 GB RAM server dedicated to MongoDB
```

Or at runtime (no restart required):

```javascript
db.adminCommand({ setParameter: 1, wiredTigerEngineRuntimeConfig: "cache_size=14G" });
```

### Cache vs. Resident Set Size

The WiredTiger cache size is **not** the same as MongoDB's RSS (Resident Set Size) reported by the OS. RSS includes:

- WiredTiger cache (decompressed pages)
- OS page cache pages mapped into mongod's address space
- tcmalloc allocator overhead (free lists, thread caches)
- Stack, heap, code segments

A node can show RSS of 20 GB with a WiredTiger cache of 14 GB. Confusing the two leads to over- or under-sizing. Always monitor `wiredTiger.cache.maximum bytes configured` and `wiredTiger.cache.bytes currently in the cache` directly.

### Containers and Kubernetes

The default formula reads `/proc/meminfo` (or `sysconf`) for total RAM. In containers with memory limits set via cgroups, mongod may read the host's total RAM and compute a cache size exceeding the container limit. Always set `cacheSizeGB` explicitly in containerized environments. The Percona Operator for MongoDB exposes this via `resources.wiredTiger.engineConfig.cacheSizeGB`.

---

## 3. Eviction Mechanics

### Purpose

When the WiredTiger cache fills, pages must be evicted to make room for new reads and writes. Clean pages (unmodified since last checkpoint) are evicted cheaply — they are simply dropped because the on-disk version is current. Dirty pages must be **reconciled** first: the update chain is processed, the latest committed version is written to disk, and older versions go to the history store.

### Eviction Thresholds (Defaults)

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `eviction_target` | 80% | Background eviction workers activate when cache reaches this level |
| `eviction_trigger` | 95% | Application threads begin doing eviction work at this level |
| `eviction_dirty_target` | 5% | Background workers aim to keep dirty bytes below this % of cache |
| `eviction_dirty_trigger` | 20% | Application threads throttled when dirty data reaches this % |

These map to MongoDB parameters via `wiredTiger.engineConfig.configString` or the `setParameter` command.

### Worker Thread Configuration

WiredTiger dynamically scales eviction worker threads between `threads_min` and `threads_max`. Default: 1 minimum, 4 maximum background eviction threads (these are in addition to the main eviction thread).

To tune for heavy write workloads:

```yaml
storage:
  wiredTiger:
    engineConfig:
      configString: "eviction=(threads_min=4,threads_max=8)"
```

Or at runtime:

```javascript
db.adminCommand({
  setParameter: 1,
  wiredTigerEngineRuntimeConfig: "eviction=(threads_min=4,threads_max=8)"
});
```

### Application Thread Eviction — The Critical Symptom

When background eviction workers cannot keep up with demand:

1. Cache climbs toward the `eviction_trigger` (95%).
2. Application threads (the threads serving read/write requests) are **pressed into service as eviction workers**.
3. These threads cannot serve requests while performing eviction.
4. Result: **sudden latency spikes** — operations that normally complete in microseconds take milliseconds or seconds.

**Diagnostic signal**: `wiredTiger.cache["application threads page read from disk to cache count"]` or `wiredTiger.cache["application threads doing evictions"]` > 0 in `db.serverStatus()`.

In Datadog: monitor `mongodb.wiredtiger.cache.app_threads_evictions`. In Atlas: this surfaces as "application doing eviction work" in the WiredTiger diagnostics panel.

### Dirty Data Eviction and Checkpoint Interaction

The `eviction_dirty_target` (5%) and `eviction_dirty_trigger` (20%) exist because dirty pages are more expensive to evict — they require reconciliation and potentially writing to the history store. High dirty percentages also force checkpoints to do more work. If dirty data consistently exceeds 5–10% of cache size, the checkpoint subsystem is falling behind write throughput.

---

## 4. Checkpoint Behavior

### Checkpoint Triggers

MongoDB configures WiredTiger to create a checkpoint **every 60 seconds** (`storage.syncPeriodSecs`). That is the only documented trigger in the current Manual (`core/wiredtiger`: "at intervals of 60 seconds"). The older "or 2 GB of journal data, whichever comes first" wording is **not** a checkpoint trigger; the Manual's journaling page says "the default maximum size for a checkpoint is 2 GB" only in the context of sizing journal disk space.

Other things that force a checkpoint outside the 60 s cadence: `fsync`/`db.fsyncLock()`, clean shutdown, and `compact`/`autoCompact` ("Compaction regularly checkpoints the database").

The checkpoint makes all dirty pages from the previous interval durable on disk. Until the checkpoint completes, MongoDB cannot remove the journal files that cover that interval ("WiredTiger automatically removes old journal files and maintains only the files needed to recover from the last checkpoint").

### What Happens During a Checkpoint

1. WiredTiger takes a consistent snapshot of all in-memory dirty pages.
2. Each dirty page is **reconciled**: the latest committed version is written to the `.wt` file; older committed versions go to `WiredTigerHS.wt`.
3. The `WiredTiger.turtle` metadata file is updated atomically to point to the new checkpoint.
4. Journal files older than the new checkpoint are eligible for deletion.

### Performance Impact

In write-heavy workloads, checkpoints can cause significant I/O bursts every 60 seconds. Percona benchmarks have shown throughput drops from ~7,500 ops/sec to ~40 ops/sec during checkpoint flushes on spinning disks — a 1,800× degradation. NVMe SSDs dramatically reduce this impact. The root cause is that the block manager must write pages in a random-access pattern determined by B-tree layout, stressing random write I/O.

### Long-Running Transactions and Checkpoint Stalls

A long-running transaction holds a **snapshot** open. WiredTiger cannot discard dirty pages that are visible to this snapshot. This causes:

- The history store (`WiredTigerHS.wt`) to grow as reconciled versions accumulate rather than being freed.
- Checkpoint duration to increase because more pages must be processed.
- Cache to fill with pages pinned by the open snapshot.

**Diagnostic metric**: `db.serverStatus().wiredTiger.transaction["transaction checkpoint total time (msecs)"]` and `wiredTiger.transaction["transaction checkpoint currently running"]`.

### Monitoring Checkpoint Health

```javascript
const wt = db.serverStatus().wiredTiger;

// Last checkpoint duration
wt.transaction["transaction checkpoint total time (msecs)"]

// Is a checkpoint currently running?
wt.transaction["transaction checkpoint currently running"]

// Pages written during last checkpoint
wt.transaction["transaction checkpoint scrub dirty target"]
```

Atlas exposes checkpoint duration in the "WiredTiger" performance panel. FTDC captures `wt.transaction.transaction checkpoint total time (msecs)` at 1-second resolution.

### Mitigations for Checkpoint Stalls

- Use fast NVMe storage; spinning disks magnify checkpoint latency.
- Lower `eviction_dirty_target` to keep fewer dirty pages in cache at any time (reduces per-checkpoint write volume).
- Increase eviction worker threads so dirty pages are flushed more aggressively between checkpoints.
- Investigate and kill long-running transactions that pin snapshots.
- Monitor FTDC for recurring 60-second I/O spikes.

---

## 5. Journal and Write-Ahead Log

### Journal Purpose

The WiredTiger journal (write-ahead log / WAL) bridges the gap between checkpoints. It records every committed write operation as it occurs. On crash recovery, MongoDB:

1. Identifies the last successful checkpoint.
2. Replays journal entries from that checkpoint forward.
3. Re-applies those writes to reconstruct the pre-crash state.

This ensures no committed writes are lost between checkpoints.

### Journal Commit Interval

By default, WiredTiger commits the journal buffer to disk **every 100 milliseconds**. Configurable range: 1–500ms.

```yaml
storage:
  journal:
    commitIntervalMs: 100  # default
```

This means a crash can lose up to 100ms of writes for replica set members using the default `w:1, j:false` write concern.

### Journal Sync Triggers

WiredTiger bypasses the 100ms interval and syncs immediately when:

- A write operation uses `j: true` write concern.
- A primary replica set node acknowledges a write that requires `j: true`.
- `writeConcernMajorityJournalDefault: true` is set (default for replica sets with WiredTiger).

### Journal File Rotation

Journal files live in `<dbPath>/journal/`. WiredTiger creates new journal files as needed and rotates them when a checkpoint completes: files preceding the checkpoint are no longer needed for recovery and are deleted. Each journal file is pre-allocated to 100 MB by default.

Journal entries contain:
- Log Sequence Number (LSN)
- Transaction ID
- Operation type (`row_put`, `row_modify`, `row_remove`)
- File identifier (maps to `.wt` file)
- Key, value data
- Checksum

### Disabling the Journal (--nojournal)

**Removed in MongoDB 6.1** for WiredTiger: journaling is always enabled, and the `storage.journal.enabled` option along with the `--journal` / `--nojournal` command-line flags were removed. Starting a MongoDB 6.1+ node with any of these options is a startup error. Before 6.1, journaling could be disabled only on **standalone** (non-replica-set) WiredTiger nodes; replica set members always required it.

If you encounter this on a pre-6.1 deployment: disabling journaling means that a crash loses all writes since the last checkpoint (up to 60 seconds). **Never disable journaling on replica set members** — it violates the durability contract. Treat any pre-6.1 standalone with journaling disabled as unacceptably risky in production.

### j:true Write Concern Performance

Using `j: true` forces a synchronous fsync of the journal before acknowledging the write to the client. This guarantees single-server durability but introduces latency proportional to journal sync time (typically 1–5ms on NVMe; 5–20ms on HDDs). For most production workloads, `w: "majority"` with `writeConcernMajorityJournalDefault: true` provides the right balance.

---

## 6. Compression

### Supported Compressors

WiredTiger supports block-level compression for collection data files. MongoDB ships with four options:

| Algorithm | Since | Ratio | Speed | CPU | Use Case |
|-----------|-------|-------|-------|-----|----------|
| `none` | 2.6 | 1× | Fastest | Lowest | Analytics, already-compressed data |
| `snappy` | 3.0 | ~28% reduction | 300–500 MB/s | Low | **Default. General purpose.** |
| `zlib` | 3.0 | ~45% reduction | ~100 MB/s | 3-4× snappy | Archival, cold data |
| `zstd` | 4.2 | ~49% reduction | ~250 MB/s | ~= snappy | **Best choice for new deployments** |

Percona benchmarks (120M document dataset, 14.95 GB uncompressed):
- Snappy: 10.75 GB compressed, 16K inserts/sec, 34% CPU
- Zstd: 7.69 GB compressed, 14.8K inserts/sec, 31.7% CPU

Zstd achieves ~3 GB more savings with slightly lower CPU in this benchmark.

### Index Compression

Indexes use **prefix compression** by default (not block compression). Prefix compression deduplicates common key prefixes within index pages, which is highly effective for monotonically increasing keys (ObjectId, timestamps). Prefix compression is a WiredTiger-internal mechanism and cannot be changed per-index.

Block compression can be enabled for indexes but is rarely used; the benefit is marginal because index pages are typically well-utilized and frequently accessed (hot in cache).

### Configuring Compression

**Default for all new collections** (mongod.conf):

```yaml
storage:
  wiredTiger:
    collectionConfig:
      blockCompressor: zstd   # or snappy, zlib, none
    indexConfig:
      prefixCompression: true
```

**Per-collection at creation time**:

```javascript
db.createCollection("events", {
  storageEngine: {
    wiredTiger: {
      configString: "block_compressor=zstd"
    }
  }
});
```

**Important**: Compression applies to on-disk storage and the OS page cache. Data in the WiredTiger cache (RAM) is always **decompressed**. Compression directly reduces disk usage and disk I/O bandwidth but does not reduce the WiredTiger cache footprint.

### Changing Compression on Existing Collections

WiredTiger compression is set at collection creation and cannot be changed in-place. To migrate:
1. Create a new collection with the desired compressor.
2. Copy data (aggregation `$out` or bulk write).
3. Drop the old collection and rename the new one.
4. Rebuild indexes.

Alternatively, use `mongodump` / `mongorestore` with the target node reconfigured for the new compressor.

---

## 7. Storage Statistics and Diagnostics

### serverStatus().wiredTiger Breakdown

`db.serverStatus().wiredTiger` is the primary diagnostic surface. Key subsections:

#### Cache

```javascript
const c = db.serverStatus().wiredTiger.cache;

c["bytes currently in the cache"]           // Current cache usage (bytes)
c["maximum bytes configured"]               // Configured cache limit
c["tracked dirty bytes in the cache"]       // Unwritten modified data
c["bytes read into cache"]                  // Pages read from disk (cumulative)
c["pages evicted by application threads"]   // CRITICAL: app thread eviction
c["modified pages evicted"]                 // Dirty page eviction count
c["unmodified pages evicted"]               // Clean page eviction count
c["pages currently held in the cache"]      // Total cached pages count
```

**Key ratios to watch**:
- `tracked dirty bytes / maximum bytes configured` → dirty ratio; alarm if > 5–10%
- `bytes currently in the cache / maximum bytes configured` → utilization; alarm if > 80%
- `pages evicted by application threads` → should be 0 or near 0

#### Transactions / Concurrency

```javascript
const t = db.serverStatus().wiredTiger.concurrentTransactions;

t.read.out       // Read tickets in use
t.read.available // Read tickets available (alarm if → 0)
t.write.out      // Write tickets in use
t.write.available // Write tickets available (alarm if → 0)
```

Default ticket pool: MongoDB 7.0+ uses dynamic ticket sizing (removed the static 128-ticket cap; controlled via `storageEngineConcurrentWriteTransactions` / `storageEngineConcurrentReadTransactions`). Prior to 7.0 the default was 128 read + 128 write tickets.

#### Checkpoint

```javascript
const tx = db.serverStatus().wiredTiger.transaction;

tx["transaction checkpoint total time (msecs)"]  // Duration of last checkpoint
tx["transaction checkpoint currently running"]   // 1 if checkpoint in progress
tx["transaction checkpoint min time (msecs)"]    // Min checkpoint duration
tx["transaction checkpoint max time (msecs)"]    // Max checkpoint duration
```

#### Log (Journal)

```javascript
const log = db.serverStatus().wiredTiger.log;

log["log bytes written"]           // Total journal bytes written (cumulative)
log["log sync operations"]         // Total fsync calls to journal
log["log sync_dir operations"]     // Directory fsync for durability
log["log records compressed"]      // Journal entries compressed
```

### mongostat WiredTiger Columns

```bash
mongostat --discover
```

Key WiredTiger columns in mongostat output:

| Column | Meaning |
|--------|---------|
| `faults` | OS-level major page faults (correlates with cache misses but is not a 1:1 WiredTiger metric) |
| `dirty` | % of WiredTiger cache that is dirty |
| `used` | % of WiredTiger cache in use |
| `vsize` | Virtual memory size of the mongod process |

### FTDC (Full-Time Diagnostic Data Capture)

MongoDB captures `serverStatus` at 1-second intervals into `diagnostic.data/` as FTDC (Full-Time Diagnostic Data Capture) files. FTDC data is the source of truth for support cases and retrospective analysis.

Tools to read FTDC:
- `ftdc-utils` (Go-based, open source)
- MongoDB Atlas integrated FTDC viewer
- Percona Monitoring and Management (PMM) WiredTiger dashboard

FTDC is particularly valuable for detecting checkpoint spikes, which are often invisible in longer-window metric averages (e.g., 1-minute Datadog intervals may average away a 5-second checkpoint stall).

### Pinned Bytes

`wiredTiger.cache["bytes belonging to page images in the cache"]` tracks pages currently pinned by open cursors or transactions. High pinned bytes alongside high overall cache usage often indicates long-running transactions preventing eviction.

### Diagnostic Query Patterns

```javascript
// Full WiredTiger cache snapshot
const wt = db.adminCommand({ serverStatus: 1 }).wiredTiger;
const cache = wt.cache;
const cacheUsedPct = (cache["bytes currently in the cache"] / cache["maximum bytes configured"] * 100).toFixed(1);
const dirtyPct = (cache["tracked dirty bytes in the cache"] / cache["maximum bytes configured"] * 100).toFixed(1);
print(`Cache: ${cacheUsedPct}% used, ${dirtyPct}% dirty`);
print(`App thread evictions: ${cache["pages evicted by application threads"]}`);

// Checkpoint duration
const tx = wt.transaction;
print(`Last checkpoint: ${tx["transaction checkpoint total time (msecs)"]}ms`);
print(`Max checkpoint: ${tx["transaction checkpoint max time (msecs)"]}ms`);
```

---

## 8. Cache Pressure Patterns

### Pattern 1: Working Set Exceeds Cache Size

**Symptoms**: High cache utilization (>80%), elevated `pages read into cache` rate, high `faults` in mongostat.

**Cause**: The application's active working set (the data touched by queries) is larger than `wiredTigerCacheSizeGB`. Each cache miss requires a disk read, decompression, and insertion into cache, evicting another page.

**Resolution**:
- Increase `wiredTigerCacheSizeGB` (or upgrade instance tier in Atlas).
- Ensure indexes fit in cache; unindexed queries force full collection scans.
- Use covered queries to reduce document fetch from cache.

### Pattern 2: Application Thread Eviction

**Symptoms**: `wiredTiger.cache["pages evicted by application threads"]` > 0; latency spikes with no increase in query count.

**Cause**: Background eviction workers cannot keep pace with write throughput. Cache fills to the eviction_trigger (95%), forcing application threads to do eviction work.

**Resolution**:
- Increase eviction worker threads: `eviction=(threads_min=4,threads_max=8)`
- Lower `eviction_dirty_target` to push more eviction earlier: `eviction_dirty_target=2,eviction_dirty_trigger=10`
- Increase cache size.
- Investigate if long-running transactions are pinning pages.

### Pattern 3: Dirty Data Accumulation

**Symptoms**: `tracked dirty bytes / maximum bytes configured` consistently > 5–10%; checkpoint durations growing.

**Cause**: Write throughput exceeds the rate at which WiredTiger can flush dirty pages. Common in bulk load scenarios.

**Resolution**:
- Reduce write batch sizes to allow eviction to keep pace.
- Increase eviction workers.
- For bulk loads: disable the index builds during load, rebuild afterward.
- Use aggressive eviction tuning (values well below the defaults of dirty_target=5%/dirty_trigger=20%): `eviction_dirty_trigger=5,eviction_dirty_target=1`

### Pattern 4: tcmalloc Heap Fragmentation

MongoDB uses Google's tcmalloc allocator by default. tcmalloc maintains per-thread free lists and a central heap cache that does not immediately return freed memory to the OS. This means:

- RSS can appear significantly larger than the WiredTiger cache size.
- After large bulk deletes, RSS may not decrease even after compaction.

**Diagnostic**: Compare `db.serverStatus().tcmalloc` with `wiredTiger.cache["maximum bytes configured"]`. If `tcmalloc.generic.heap_size` is significantly larger than expected, fragmentation may be occurring.

**Workarounds**:
- MongoDB 4.4+ includes mitigations for tcmalloc fragmentation (WT-2764 limits fragmentation overhead to ~20% of cache size + 1 GB).
- Consider `MALLOC_CONF=background_thread:true` (jemalloc alternative) in specialized deployments.
- Regular mongod restarts can reclaim fragmented memory in extreme cases.

### Pattern 5: History Store Growth from Long Transactions

**Symptoms**: `WiredTigerHS.wt` grows rapidly; cache fills with "pinned pages"; checkpoint duration grows.

**Cause**: A long-running transaction or open cursor holds an MVCC snapshot open. WiredTiger cannot discard historical versions visible to that snapshot.

**Resolution**:
- Identify long-running operations: `db.currentOp({ secs_running: { $gt: 30 } })`.
- Kill problematic operations: `db.killOp(opId)`.
- Set `maxTimeMS` on all application queries.
- Reduce `minSnapshotHistoryWindowInSeconds` from the default 300 if flashback is not needed.

### Atlas-Specific Monitoring

On Atlas, WiredTiger cache pressure surfaces as:

- **"System Memory" metric** climbing toward instance RAM ceiling.
- **"Page Faults"** counter increasing.
- Cluster tier auto-scaling triggers if enabled.

Atlas does not expose `wiredTigerCacheSizeGB` as a user-settable parameter — it is derived from the cluster tier. To resolve persistent cache pressure in Atlas: upgrade tier, enable auto-scaling, or optimize queries via the Performance Advisor.

---

## 9. Compaction and Storage Reclamation

### How WiredTiger Handles Deletes

When documents are deleted in MongoDB, WiredTiger marks those pages as available for reuse internally but **does not immediately return the disk space to the operating system**. The freed blocks are maintained in WiredTiger's internal **free list** (tracked per `.wt` file). New inserts can reuse this space, but the file size on disk does not shrink.

Monitor available free space:

```javascript
db.myCollection.stats().wiredTiger["block-manager"]["file bytes available for reuse"]
```

A high "file bytes available for reuse" relative to `storageSize` indicates fragmentation that compaction can address.

### The compact Command

```javascript
db.runCommand({ compact: "myCollection" });
db.runCommand({ compact: "myCollection", freeSpaceTargetMB: 100 });
```

`compact` rewrites the entire collection `.wt` file and all associated index `.wt` files. It:

1. Reads all live documents from the existing file.
2. Writes them to a new, defragmented file.
3. Releases empty pages back to the OS.

**Key behaviors by version**:

| MongoDB Version | compact Behavior |
|----------------|-----------------|
| < 4.4 | Blocks all reads/writes; run on secondaries |
| 4.4+ | Runs on primary; blocks writes but allows reads |
| 6.0.2+ | Secondaries can replicate while compact runs |

In MongoDB 6.0, the `force: true` option (previously needed to run on a primary) was removed entirely.

### autoCompact (MongoDB 8.0+)

```javascript
db.adminCommand({
  autoCompact: true,
  freeSpaceTargetMB: 500
});
```

Background compaction that continuously keeps free space per collection/index file below `freeSpaceTargetMB` (default 20 MB). `runOnce: true` does a single pass over every collection/index on the node and stops; `autoCompact: false` stops a continuous run. Verified facts (Manual `autoCompact`, WiredTiger source, Jira):

- **Per node, not replicated.** "The primary node does not replicate the autoCompact command to the secondary nodes." A node compacts only if the command is issued on that node. Sharded: run on each shard's mongods directly; cannot be issued to `mongos`.
- **Non-blocking.** "Reads and writes are permitted while background compaction is running"; no `force` needed on a primary. Calling `autoCompact` again while one is active returns an error — disable first.
- **Mechanism.** WiredTiger first-fit compaction moves blocks from the tail of the file into free extents near the front and truncates; it only attempts files with >=20% free in the first 80% (or >=10% free in the first 90%), skips files <1 MB. Cost scales with reclaimable tail bytes and passes ("two checkpoints per pass, up to 100 passes per file"), not with total file size.
- **Checkpoint overhead.** "Compaction regularly checkpoints the database." Manual guidance: run in low-traffic periods; disable before backups.
- **Atlas.** Not supported on M0/Flex; supported on dedicated tiers. Requires the Atlas `autoCompact` built-in role (`atlasAdmin` alone got an auth error on 8.0 RCs — SERVER-90459). Atlas storage auto-scales **up only**; reclaimed bytes save money only after a manual disk decrease, which is a volume-replacement with per-node sync (`cluster-autoscaling`, `customize-storage`).
- **Sizing.** `db.runCommand({compact: "<coll>", dryRun: true})` (8.0+) returns `estimatedBytesFreed`; `db.stats({freeStorage: 1})` returns `freeStorageSize` / `indexFreeStorageSize`.
- **Observability.** `serverStatus().wiredTiger["background-compact"]`: `running`, `recovered bytes`, `files tracked`, `skipped file, not meeting requirements`, `failed calls due to cache pressure`, `sleeps due to cache pressure`, `timeout`. Checkpoint timings are `wiredTiger.checkpoint["total time (msecs)"]` (WT 11+ / MongoDB 7.0+), not the pre-7.0 `transaction checkpoint ...` names. Atlas has no checkpoint chart.
- **Known tickets.** WT-18413 (open): background compaction bypasses the eviction-assist check and kept running while a secondary hit the 20% dirty trigger on a very large collection. WT-13216 (fixed 8.0.10/7.0.21) added eviction assistance to foreground `compact` only. WT-13340 (fixed 8.1.0): on 8.0.x, truncation can wait for a later non-skipped checkpoint. WT-13447 (fixed 8.0.5): `runOnce` stats. WT-15258 (open): memory fragmentation after autoCompact. SERVER-106156 (backlog): no time-window/throttle knob exists. Recommend >=8.0.10 before piloting.
- No `incrementalCompactionMaxFileSizeMB` / `freeSpaceTargetPercent` parameters exist.

### When compaction Does Not Help

- If the application immediately re-inserts data after deletes (the free list is quickly reclaimed).
- If fragmentation is at the OS filesystem level rather than within WiredTiger files.
- If the primary concern is RAM usage (compaction only affects disk, not cache).

### Storage Sizing After Compaction

After `compact`, verify reclamation:

```javascript
// Before compact
const before = db.myCollection.stats().storageSize;
db.runCommand({ compact: "myCollection" });
// After compact
const after = db.myCollection.stats().storageSize;
print(`Reclaimed: ${((before - after) / 1024 / 1024).toFixed(1)} MB`);
```

### Replica Set Compaction Workflow

For replica sets, compact one node at a time to avoid availability impact:

```bash
# 1. Step down primary if compacting primary (optional, prefer secondary)
# 2. Run compact on one secondary at a time
# 3. Let secondary resync if compact takes too long and it falls off oplog
```

---

## 10. WiredTiger and Sharding

### Per-Shard WiredTiger Instances

In a sharded cluster, **each shard is an independent replica set** with its own WiredTiger instance. There is no shared WiredTiger cache across shards. Each shard:

- Has its own `wiredTigerCacheSizeGB` (configured via the shard mongod.conf).
- Has its own checkpoint cycle, eviction workers, and journal.
- Should be sized independently based on the data it holds.

Config server replica sets (CSRS) also run WiredTiger but typically hold only metadata; their cache requirements are minimal (<1 GB in most deployments).

### Balancer and Cache Impact

The MongoDB balancer moves chunks between shards to equalize data distribution. During chunk migration:

1. The **source shard** reads all documents in the migrating chunk — these reads populate its WiredTiger cache. On large migrations, this can evict hot working-set data.
2. Documents are streamed to the **destination shard**, which writes them to its WiredTiger cache (dirty pages) and journal.
3. After migration, the source shard **deletes the migrated documents** asynchronously (orphan cleanup).

**Cache pressure during migrations**: Migrating a 2 GB chunk effectively forces 2 GB of sequential reads on the source shard and 2 GB of writes on the destination. This can trigger eviction pressure on both shards. Monitor cache utilization during balancer windows and consider scheduling migrations during low-traffic periods.

### Orphan Cleanup and Cache

After chunk migration, source shards perform orphan document cleanup (deletion of the migrated range). This is handled by the range deleter background process. Large orphan cleanups:

- Generate dirty pages in the source shard's WiredTiger cache.
- Can cause checkpoint pressure as dirty data accumulates.
- MongoDB 8.2+ may automatically terminate long-running secondary reads that conflict with orphan deletion.

**Mitigation**: Monitor `db.adminCommand({ currentOp: true, desc: "range_deleter" })` and ensure the range deleter is not starved of I/O.

### directoryPerDB in Sharding

For sharded deployments with many databases, `storage.directoryPerDB: true` separates each database's `.wt` files into subdirectories. This is useful for:

- Mounting per-database volumes on separate disks/NVMe devices.
- Simplifying backup procedures (per-database filesystem snapshots).
- Isolating I/O for hot databases from cold ones.

Note: mongos (the query router) does not use WiredTiger; it holds no data files and has no WiredTiger cache. Cache sizing guidance applies only to mongod instances (shards + config servers).

### Shard-Specific Tuning

Because each shard is independent, WiredTiger tuning can differ per shard:

- Hot shards (high query volume, large working set) may need larger `wiredTigerCacheSizeGB`.
- Cold shards (archival data) may benefit from `zstd` compression and smaller cache.
- Shards running heavy aggregations should have more eviction worker threads.

Use `sh.status()` to identify chunk distribution imbalance that may explain why one shard has higher cache pressure than others.

---

## Quick Reference: Key Parameters

```yaml
storage:
  dbPath: /data/db
  directoryPerDB: false            # true to isolate databases to subdirectories
  journal:
    enabled: true                  # Never disable on replica sets
    commitIntervalMs: 100          # 1–500ms; lower = more durable, more I/O
  wiredTiger:
    engineConfig:
      cacheSizeGB: 14              # Explicit cache; omit to use default formula
      journalCompressor: snappy    # Journal compression
      directoryForIndexes: false   # true to separate index files
      configString: "eviction=(threads_min=4,threads_max=8)"
    collectionConfig:
      blockCompressor: zstd        # snappy (default), zlib, zstd, none
    indexConfig:
      prefixCompression: true      # Always leave enabled
```

---

## Quick Reference: Critical serverStatus Fields

```javascript
const wt = db.serverStatus().wiredTiger;

// Cache health
wt.cache["bytes currently in the cache"]           // Used cache bytes
wt.cache["maximum bytes configured"]               // Cache limit
wt.cache["tracked dirty bytes in the cache"]       // Dirty bytes
wt.cache["pages evicted by application threads"]   // ALARM if > 0

// Checkpoint health
wt.transaction["transaction checkpoint total time (msecs)"]
wt.transaction["transaction checkpoint currently running"]

// Concurrency
wt.concurrentTransactions.read.available           // ALARM if → 0
wt.concurrentTransactions.write.available          // ALARM if → 0

// Journal
wt.log["log sync operations"]                      // fsync calls
```

---

## References

### Official Documentation
- [WiredTiger Storage Engine — MongoDB Manual](https://www.mongodb.com/docs/manual/core/wiredtiger/)
- [Configure Journaling — MongoDB Manual](https://www.mongodb.com/docs/manual/core/journaling/)
- [compact Command — MongoDB Manual](https://docs.mongodb.com/manual/reference/command/compact/)
- [Cache and Eviction Tuning — WiredTiger Source](https://source.wiredtiger.com/mongodb-6.0/tune_cache.html)
- [WiredTiger Eviction Architecture](https://source.wiredtiger.com/11.0.0/arch-eviction.html)
- [History Store Architecture — WiredTiger](https://source.wiredtiger.com/11.0.0/arch-hs.html)

### Deep Dives
- [WiredTigerHS.wt: MongoDB MVCC Durable History Store — DEV Community](https://dev.to/mongodb/mongodb-mvcc-durable-history-store-wiredtigerhswt-mn2)
- [MongoDB Internals: Collections and Indexes in WiredTiger — DEV Community](https://dev.to/mongodb/mongodb-internals-how-collections-and-indexes-are-stored-in-wiredtiger-2ed)
- [WiredTiger Logging and Checkpoint Mechanism — Percona](https://www.percona.com/blog/wiredtiger-logging-and-checkpoint-mechanism/)
- [MongoDB Checkpointing Woes — Percona](https://www.percona.com/blog/mongodb-checkpointing-woes/)
- [Compression Methods: Snappy vs Zstd — Percona](https://www.percona.com/blog/compression-methods-in-mongodb-snappy-vs-zstd/)
- [Monitoring MongoDB WiredTiger Metrics — Datadog](https://www.datadoghq.com/blog/monitoring-mongodb-performance-metrics-wiredtiger/)
- [Identifying and Reclaiming Disk Space — Alex Bevilacqua](https://alexbevi.com/blog/2020/03/15/identifying-and-reclaiming-disk-space-in-mongodb/)
- [Tuning MongoDB for Bulk Loads — Percona](https://www.percona.com/blog/tuning-mongodb-for-bulk-loads/)
- [Configure WiredTiger CacheSize in Percona Operator — Percona](https://www.percona.com/blog/configure-wiredtiger-cachesize-inside-percona-distribution-for-mongodb-kubernetes-operator/)

### See Also

- [[mongodb-expert]] — General MongoDB expertise, query patterns, and deployment guidance
- [[mongodb-performance-troubleshooting]] — End-to-end performance diagnosis including query, index, and replication lag analysis
- [[mongodb-capacity-planning]] — Sizing storage, compute, and memory for MongoDB deployments
- [[mongodb-monitoring-observability]] — Full monitoring stack setup, FTDC analysis, and alerting
- [[mongodb-indexes-deep]] — Index types, strategies, and their WiredTiger storage implications
- [[mongodb-transactions]] — Multi-document transactions and their interaction with WiredTiger MVCC and checkpoint behavior
