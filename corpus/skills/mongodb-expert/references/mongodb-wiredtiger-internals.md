<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-wiredtiger-internals` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-wiredtiger-internals
title: MongoDB WiredTiger Storage Engine Internals
version: 1.1.0
updated: "2026-05-29"
category: mongodb
tags:
  - mongodb
  - wiredtiger
  - storage-engine
  - cache
  - eviction
  - checkpoint
  - mvcc
  - history-store
  - compression
  - btree
  - reconciliation
  - journal
  - in-memory
  - performance
  - ftdc
  - tickets
  - concurrency
description: >
  Deep internals reference for the WiredTiger storage engine — covering cache
  architecture, eviction (clean/dirty/updates targets and triggers, worker threads,
  urgent queue, application-thread eviction), checkpoint and journal interaction,
  MVCC with snapshot isolation and timestamp management, the durable history store
  (WiredTigerHS.wt), reconciliation and page splitting, block manager and page sizing,
  snappy/zlib/zstd block compression and prefix index compression, in-memory storage
  engine (Enterprise), encryption at rest (KMIP/AES256), read/write tickets and dynamic
  concurrency (7.0+), diagnostic surface (db.serverStatus().wiredTiger, FTDC, verbose
  component flags), tunables (wiredTigerEngineRuntimeConfig), and 8.0+ performance
  improvements.

  TRIGGER: user asks about WiredTiger cache pressure, eviction, cache sizing,
  application-thread eviction, dirty bytes, history store growth, long-running
  transactions pinning cache, WT_CACHE_FULL errors, checkpoint or journal durability,
  block compression (snappy/zlib/zstd), FTDC cache metrics, read/write ticket
  exhaustion, dynamic ticketing (7.0+), in-memory storage engine, WiredTiger
  encryption at rest (KMIP), or wiredTigerEngineRuntimeConfig tunables.

  SKIP: query performance issues not related to storage internals (use
  mongodb-performance-troubleshooting); index design (use mongodb-indexes-deep);
  general Atlas monitoring (use mongodb-monitoring-observability); backup/restore
  (use mongodb-backup-restore); disaster recovery (use mongodb-disaster-recovery).

whenToUse:
  - "WiredTiger cache is filling up — how do I diagnose and fix it?"
  - "Pages evicted by application threads is non-zero — what does that mean?"
  - "How do I size the WiredTiger cache for my workload?"
  - "Which block compressor should I use — snappy, zlib, or zstd?"
  - "History store is growing unbounded — how do I find the pinned transaction?"
  - "WT_CACHE_FULL error — what causes it and how do I fix it?"
  - "How do checkpoint and journal interact for durability?"
  - "Read/write ticket exhaustion on MongoDB 7.0+ dynamic ticketing"
  - "How do I tune eviction worker threads via wiredTigerEngineRuntimeConfig?"
  - "Should I use the in-memory storage engine for my workload?"
  - "Configure encryption at rest with KMIP at the WiredTiger layer"
  - "How do I interpret FTDC cache and eviction metrics?"

whenNotToUse:
  - Query performance analysis not tied to cache/eviction (slow query log, explain output) — use mongodb-performance-troubleshooting
  - Index design and selectivity — use mongodb-indexes-deep
  - Atlas cluster monitoring dashboards and alerts — use mongodb-monitoring-observability
  - Backup snapshot mechanics — use mongodb-backup-restore
  - Data file corruption recovery and validate()/repair — use mongodb-disaster-recovery
  - Transaction isolation semantics from the application perspective — use mongodb-transactions

related_skills:
  - mongodb-performance-troubleshooting
  - mongodb-indexes-deep
  - mongodb-monitoring-observability
  - mongodb-capacity-planning
  - mongodb-transactions
  - mongodb-encryption
  - mongodb-backup-restore
  - mongodb-disaster-recovery
  - mongodb-time-series
  - atlas-diagnostics-expert

references:
  - https://www.mongodb.com/docs/manual/core/wiredtiger/
  - https://www.mongodb.com/docs/v8.2/core/wiredtiger/
  - https://source.wiredtiger.com/develop/arch-eviction.html
  - https://source.wiredtiger.com/develop/arch-cache.html
  - https://source.wiredtiger.com/11.0.0/arch-hs.html
  - https://source.wiredtiger.com/develop/arch-transaction.html
  - https://source.wiredtiger.com/develop/arch-timestamp.html
  - https://source.wiredtiger.com/develop/tune_durability.html
  - https://source.wiredtiger.com/develop/debugging.html
  - https://source.wiredtiger.com/mongodb-6.0/tune_cache.html
  - https://www.percona.com/blog/wiredtiger-logging-and-checkpoint-mechanism/
  - https://www.percona.com/blog/compression-methods-in-mongodb-snappy-vs-zstd/
  - https://www.percona.com/blog/mongodb-101-how-to-tune-your-mongodb-configuration-after-upgrading-to-more-memory/
  - https://www.datadoghq.com/blog/monitoring-mongodb-performance-metrics-wiredtiger/
  - https://www.mongodb.com/company/blog/mongodb-8-0-improving-performance-avoiding-regressions
  - https://foojay.io/today/inside-the-engine-the-sub-millisecond-performance-relay-of-mongodb-8-0/
  - https://www.mydbops.com/blog/mongodb-7-wiredtiger-tickets
  - https://dev.to/mongodb/mongodb-mvcc-durable-history-store-wiredtigerhswt-mn2
  - https://github.com/wiredtiger/wiredtiger/wiki/Reconciliation-overview
  - https://github.com/mongodb/mongo/blob/master/src/mongo/db/storage/wiredtiger/README.md
---

# MongoDB WiredTiger Storage Engine Internals

WiredTiger has been MongoDB's default storage engine since **3.2** (replacing MMAPv1). It is a B-tree backed, MVCC, copy-on-write engine with document-level concurrency, configurable in-memory cache, block-level compression, and a write-ahead journal. Everything below the document model — durability, concurrency, compression, eviction, checkpoints — is WiredTiger.

This skill is the deep internals reference. For surface-level performance triage, see `mongodb-performance-troubleshooting`. For diagnostic packaging, see `atlas-diagnostics-expert`.

---

## 1. Architecture Overview

WiredTiger has a **hybrid architecture optimized for multi-core CPUs and large memory**:

```
                     Application threads (mongod query/index ops)
                                       |
                                       v
+----------------------------------------------------------------+
|                       WiredTiger Cache                          |
|  (In-memory B-trees w/ hazard pointers; LRU approximation)      |
|                                                                 |
|   +-----------+   +-----------+   +-----------+   +---------+   |
|   | Collection|   | Collection|   |  Index    |   | History |   |
|   |   B-tree  |   |   B-tree  |   |   B-tree  |   |  Store  |   |
|   +-----------+   +-----------+   +-----------+   +---------+   |
+--------|----------------|----------------|-----------|----------+
         |  reconcile     |   evict        |           | spill old
         v                v                v           v   versions
+----------------------------------------------------------------+
|                       Block Manager                             |
|         (allocates, writes, compresses on-disk pages)           |
+----------------------------------------------------------------+
         |                                            |
         v                                            v
   On-disk B-tree files                       Write-Ahead Log
   (collection-*.wt, index-*.wt,              (journal/WiredTigerLog.*)
    WiredTigerHS.wt, WiredTiger.wt)
```

### Three layers

1. **In-memory cache** — uncompressed B-tree pages. Working set lives here. Default size: `max(0.5 × (RAM − 1 GiB), 256 MiB)`.
2. **Block manager** — translates pages to/from disk, owns checksums, compression, encryption, free-list.
3. **OS filesystem cache** — holds compressed data blocks. Often roughly the same size as the WT cache (uncompressed) because of compression ratios.

### File layout under `dbPath`

| File | Contents |
| --- | --- |
| `WiredTiger.wt` | WT metadata (catalog of every B-tree in the deployment) |
| `WiredTiger.turtle` | Bootstrap metadata pointer |
| `WiredTigerHS.wt` | **History store** (MVCC older versions, post-4.4) |
| `collection-*.wt` | One B-tree per collection |
| `index-*.wt` | One B-tree per index |
| `journal/WiredTigerLog.<n>` | Write-ahead log files, ~100 MB each |
| `_mdb_catalog.wt` | MongoDB's logical → WT name mapping |
| `sizeStorer.wt` | Cached collection counts/sizes |

`mongod` exposes WiredTiger via a single `WT_CONNECTION` (per-process), holding one `WT_CACHE` struct and N `WT_SESSION` objects for application threads.

---

## 2. Cache: The Heart of the Engine

### 2.1 Default sizing

The cache size formula (since 3.4): `max(0.5 × (RAM − 1 GiB), 256 MiB)`, capped at **10 000 GiB**.

Override with one of (mutually exclusive):

```yaml
storage:
  wiredTiger:
    engineConfig:
      cacheSizeGB: 32          # absolute size in GiB
      # cacheSizePct: 60       # OR percent of RAM (≤ 80%); since 6.0
```

Or at the command line: `--wiredTigerCacheSizeGB 32` / `--wiredTigerCacheSizePct 60`.

**Containers and cgroups**: WT's default sizing was historically based on **host** RAM. Always pin `cacheSizeGB` explicitly when running in a container with a memory limit, or you will OOM. Newer MongoDB versions detect cgroup limits in some configurations, but pinning is still safest.

**Sizing rule of thumb (dedicated host)**: target ~50% of RAM for the WT cache and leave the rest for the OS filesystem cache plus mongod overhead (connections, plan cache, TCMalloc fragmentation). On shared hosts or multi-`mongod` deployments, reduce proportionally per instance.

### 2.2 What lives in the cache

- Uncompressed B-tree pages for collections and indexes that were touched recently
- Dirty pages awaiting reconciliation
- Update structures (per-key linked lists of in-progress modifications)
- The history store (recent MVCC versions)
- WT session metadata, transaction structures

### 2.3 Two caches at once

WiredTiger uses **two memory tiers**:

| Layer | What | Sized by |
| --- | --- | --- |
| WiredTiger cache | Uncompressed working set | `cacheSizeGB` |
| OS filesystem cache | Compressed `.wt` blocks | What the kernel reclaims |

A common rule of thumb: leave ~50% of RAM for the OS filesystem cache. Setting `cacheSizeGB` too high starves the OS cache, increasing disk reads after a page is evicted from WT but before being purged from the FS cache.

---

## 3. Eviction (the hottest topic in production)

Eviction reclaims cache space by either dropping clean pages or reconciling dirty pages (writing them to the data file). Done well: invisible. Done poorly: the source of 80% of WiredTiger production pain.

### 3.1 Eviction subsystem

- **One eviction server** thread — walks the B-trees in fairness order, finds candidates
- **N eviction worker threads** — pop pages from queues and actually evict them
- **Three queues**: two ordinary + one **urgent** queue (priority queue)

The server samples a portion of each B-tree, scores pages by access recency, takes the **one-third oldest** of evictable candidates, and pushes them onto the queues. This approximates an LRU policy — true LRU would be too expensive for a multi-million-page cache.

The urgent queue holds pages flagged for forced eviction (sessions disabling eviction/splitting, large in-memory pages exceeding the maximum size, etc.).

### 3.2 The four thresholds you must know

| Parameter | Default | Meaning |
| --- | --- | --- |
| `eviction_target` | **80%** | Worker threads start evicting clean pages |
| `eviction_trigger` | **95%** | **Application threads** are conscripted into eviction (latency spike!) |
| `eviction_dirty_target` | **5%** | Worker threads start evicting dirty pages |
| `eviction_dirty_trigger` | **20%** | Application threads stall on dirty eviction |

Additional thresholds (newer versions):

| Parameter | Default | Meaning |
| --- | --- | --- |
| `eviction_updates_target` | 2.5% | Update bytes target (in-progress update lists) |
| `eviction_updates_trigger` | 10% | Update bytes hard limit |
| `eviction.threads_min` | 4 | Minimum eviction worker threads |
| `eviction.threads_max` | 4 | Maximum eviction worker threads |

**Invariant**: `target < trigger` for every pair. The engine will refuse a config that violates this.

### 3.3 Application thread eviction — the smoking gun

Normal mode: only background eviction workers do reconciliation. Pressure mode: when cache used ≥ `eviction_trigger` (or dirty ≥ `eviction_dirty_trigger`), **application threads must perform eviction before they're allowed to do their own work**. This shows up in `serverStatus()` as:

```
wiredTiger.cache.pages evicted by application threads > 0
```

A non-zero value means writes are being throttled and latency is climbing. A persistent non-zero rate (per-second, derived from FTDC deltas) signals chronic under-sizing or under-threaded eviction.

### 3.4 Tuning eviction at runtime

Use `wiredTigerEngineRuntimeConfig` to change cache/eviction parameters **without restart**:

```js
db.adminCommand({
  setParameter: 1,
  wiredTigerEngineRuntimeConfig:
    "eviction=(threads_min=8,threads_max=12),eviction_target=75,eviction_trigger=90,eviction_dirty_target=5,eviction_dirty_trigger=15"
})
```

Persist in `mongod.conf` under `setParameter:` (not `storage.wiredTiger`):

```yaml
setParameter:
  wiredTigerEngineRuntimeConfig: "eviction=(threads_min=8,threads_max=12)"
```

**Gotcha**: forum users have reported `db.adminCommand` with this parameter not taking effect on certain versions — verify with `db.serverStatus().wiredTiger` after applying, and prefer setting it in `mongod.conf` for sticky deployments.

### 3.5 Reconciliation (how dirty eviction actually works)

When a dirty page is evicted, WT performs **reconciliation**:

1. Walk the in-memory page, collect committed values (newest visible to all readers)
2. Build a new on-disk image with one entry per key (newest committed value)
3. Push older committed versions to the **history store** (`WiredTigerHS.wt`)
4. If the resulting image exceeds the configured max page size, **split** into multiple pages
5. Compress, checksum, write via the block manager
6. If page is small enough to merge with a neighbor on the next pass, leave a hint

Reconciliation is the single most CPU-expensive operation in the engine. It's why:

- Hot pages with massive update lists pin the cache
- Long-running transactions inflate the history store
- Cache pressure under heavy write workloads is fundamentally a reconciliation throughput problem

---

## 4. Checkpoint and Journal — Two Durability Mechanisms

WiredTiger combines **checkpoints** (point-in-time consistent snapshots flushed to disk) and **a write-ahead log** (the journal). Recovery uses both.

### 4.1 Checkpoint

- Default interval: **60 seconds** (`storage.syncPeriodSecs`, or via `wiredTigerEngineRuntimeConfig` as `checkpoint=(wait=60)`)
- Alternative trigger: **2 GiB of journal accumulated since last checkpoint**
- The checkpoint thread creates a consistent snapshot of all B-trees, writes new on-disk root pointers, and only after successful write does it consider the checkpoint complete
- Crash mid-checkpoint: the previous checkpoint stays valid; the new one is discarded
- Storage is **copy-on-write**: new pages are written to free space, then the root pointer is flipped — the old pages become free list candidates after the checkpoint completes

### 4.2 Journal (write-ahead log)

- Compressed with **snappy** by default. Configure via:
  ```yaml
  storage:
    wiredTiger:
      engineConfig:
        journalCompressor: zstd   # or snappy / zlib / none
  ```
- Files are pre-allocated 100 MB segments named `WiredTigerLog.<n>` under `dbPath/journal/`
- Records ≤ 128 bytes are **not** compressed (minimum log record size)
- Default flush cadence: every **100 ms** (group commit) — this is your data loss window in a crash
- `j: true` write concern forces an immediate journal flush before acknowledging
- `disableJournal=true` (NOT for replica-set members) skips the journal entirely

### 4.3 Recovery

On restart:

1. Find the latest valid checkpoint in `WiredTiger.wt`
2. Replay journal records from the checkpoint LSN forward
3. For each table, resolve outstanding transactions (commit or roll back per stable timestamp)
4. Open `WT_CONNECTION`, expose to mongod

**Worst case data loss** in a clean crash (no replica set): up to **100 ms** of acknowledged writes from non-`j:true` clients. With `j:true`, zero.

### 4.4 Group commit and syncdelay

WiredTiger batches journal flushes via group commit. `--syncdelay` (or `storage.syncPeriodSecs`) controls the **checkpoint** cadence, not the journal flush. Many older blog posts conflate the two — be precise:

- `syncPeriodSecs` (default 60) → checkpoint interval
- Journal flush → every 100 ms (hard-coded, plus `j:true` triggers)

---

## 5. MVCC, Timestamps, and the History Store

MongoDB layered **timestamp-based MVCC** on top of WiredTiger's transaction subsystem to support snapshot isolation, causal consistency, and `readConcern: "snapshot"`.

### 5.1 Snapshot isolation

Every operation acquires a read snapshot at start. WT guarantees that the operation sees a consistent point-in-time view, regardless of concurrent writes. Readers never block writers; writers never block readers.

### 5.2 Timestamp APIs

WT exposes a small set of global timestamps:

| Timestamp | Meaning |
| --- | --- |
| **commit_timestamp** | Per-transaction; the timestamp at which the writes become visible |
| **stable_timestamp** | The point below which no rollback can occur — set by replication majority commit |
| **oldest_timestamp** | The point below which WT can discard history — set by MongoDB based on majority + min snapshot window |
| **pinned_timestamp** | `min(oldest_timestamp, all active reader timestamps, running checkpoint timestamp)` — the **real** lower bound; nothing older can be removed |

The **pinned timestamp** is the crucial concept: even if MongoDB advances `oldest_timestamp`, an active long-running snapshot pins the floor and forces WT to keep history.

### 5.3 The history store (WiredTigerHS.wt)

Introduced in 4.4 (replacing the old **lookaside file**). When reconciliation evicts a page with non-current committed versions, those older values **spill into the history store**. The current value stays in the data file.

History store key format: `(table_id, record_id, start_timestamp, counter)` — i.e., one entry per old version, per key, per timestamp.

The history store is itself a B-tree, lives in the cache, gets reconciled and evicted like any other table. Pages become reclaimable when **all rows on the page are obsolete** (no reader can see them, all are older than the pinned timestamp).

### 5.4 Long-running transactions — the cardinal sin

A snapshot pinned by a long transaction stalls cleanup:

- All updates in the transaction's view must remain available → history store grows
- All in-progress updates accumulate in update lists → cache pressure
- Reconciliation can't compress update lists into a single value

**Mitigations**:

1. Keep transactions short (MongoDB aborts multi-doc transactions after **60 s** by default, controlled by `transactionLifetimeLimitSeconds`)
2. Set `minSnapshotHistoryWindowInSeconds` (default 300 s) sensibly — every second held forces history retention
3. Watch `cache.history store on-disk size`, `cache.history store table updates inserted into history store`, and `transaction.read timestamp of the oldest active reader` in FTDC
4. Don't run `mongodump` against a hot collection with a low `snapshotHistoryWindow` — it pins the snapshot

---

## 6. Compression

Three knobs, three layers.

### 6.1 Block compression (collection data)

```yaml
storage:
  wiredTiger:
    collectionConfig:
      blockCompressor: zstd   # snappy (default) | zlib | zstd | none
```

| Algorithm | Speed | Ratio | When to use |
| --- | --- | --- | --- |
| **snappy** | 300–500 MB/s, very low CPU | ~2× | Default; latency-critical OLTP |
| **zlib** | Slowest (~3–4× CPU vs. snappy) | Best classic ratio | Cold archival data, infrequent reads |
| **zstd** | Near snappy speed | Near zlib ratio | **Best general-purpose choice** for new deployments; default for time series |
| **none** | Bypass | None | Benchmarking, in-memory engine |

Defaults:
- Regular collections: `snappy`
- Time-series collections (5.0+): `zstd`
- Journal: `snappy`

Per-collection override at creation:

```js
db.createCollection("archival_events", {
  storageEngine: {
    wiredTiger: { configString: "block_compressor=zlib" }
  }
})
```

### 6.2 Prefix compression (indexes only)

Indexes use **prefix compression**: shared key prefixes are stored once. This is on by default and almost never worth turning off — it both saves space and speeds up scans (more keys per page).

```yaml
storage:
  wiredTiger:
    indexConfig:
      prefixCompression: true   # default
```

### 6.3 Journal compression

```yaml
storage:
  wiredTiger:
    engineConfig:
      journalCompressor: snappy   # default
```

Records ≤ 128 bytes skip compression regardless.

---

## 7. Block Manager and Page Sizing

The block manager owns the on-disk layout. Pages are the unit of I/O.

### 7.1 Default page sizes

| Parameter | Default | Notes |
| --- | --- | --- |
| `internal_page_max` | 16 KiB | Max in-memory internal (non-leaf) page size |
| `leaf_page_max` | 32 KiB | Max in-memory leaf page size (the working unit) |
| `memory_page_max` | 5 MiB (capped) | Max grown in-memory page before forced split |
| `split_pct` | 90% | Page is split when reconciled image exceeds this fraction of max |
| `allocation_size` | 4 KiB | On-disk allocation unit (file alignment) |

Larger pages → better compression ratio (more data per block), worse cache granularity. Smaller pages → vice versa. MongoDB ships sensible defaults; touch only with profiling evidence.

### 7.2 In-memory page splits

When an application thread is updating a hot page and the in-memory size crosses `memory_page_max`, the thread is conscripted to **forcefully split** the page so reconciliation doesn't see an unbounded image. This shows up as elevated `cache.pages split during eviction`.

### 7.3 The free list

When pages are written via copy-on-write, old extents become free-list candidates. The block manager tracks these for reuse. Periodic **compaction** (`db.runCommand({ compact: "<coll>" })`) consolidates free space — useful after big deletes, mostly irrelevant during steady-state operation.

---

## 8. Read/Write Tickets and Concurrency

WT enforces a hard cap on **concurrent storage-engine transactions**: read tickets and write tickets.

### 8.1 Pre-7.0 behavior

- **128** read tickets, **128** write tickets, per-node, fixed
- Configurable via `storageEngineConcurrentReadTransactions` and `storageEngineConcurrentWriteTransactions`
- Exhaustion: new operations queue, latency climbs
- `db.serverStatus().wiredTiger.concurrentTransactions.{read,write}.available` shows current free tickets

### 8.2 7.0+ dynamic ticketing

MongoDB 7.0 introduced a **dynamic algorithm** that adjusts ticket counts based on observed throughput and contention. Defaults are lower than 128 during normal operation — this is intentional.

```js
db.serverStatus().queues.execution
// {
//   read:  { in: 0, out: 0, totalTickets: 64 },
//   write: { in: 0, out: 0, totalTickets: 64 }
// }
```

**Manually setting** `storageEngineConcurrentReadTransactions` or `storageEngineConcurrentWriteTransactions` (or the older aliases `wiredTigerConcurrentReadTransactions` / `wiredTigerConcurrentWriteTransactions`) to a non-default value **disables the dynamic algorithm** on 7.0+. Don't override unless you have hard evidence of ticket starvation. Look at queue depth (`queues.execution.*.in`) not at `available` alone.

### 8.3 Document-level locking

WT uses **optimistic concurrency control**. Multiple writers can hit different documents simultaneously. Same-document concurrent writes → one wins, the other gets `WT_ROLLBACK` and MongoDB retries transparently. This is per-document, not per-collection — a fundamental advantage over MMAPv1's collection-level lock.

---

## 9. In-Memory Storage Engine (Enterprise)

MongoDB Enterprise ships an alternative WT configuration with **no disk persistence**.

### 9.1 Configuration

```yaml
storage:
  engine: inMemory
  inMemory:
    engineConfig:
      inMemorySizeGB: 32
```

Data lives only in memory. No data files, no journal, no checkpoint. Restart = empty database.

### 9.2 Use cases

- Cache layer in front of a primary store
- Real-time analytics with TTL'd ephemeral data
- Test/CI environments that need MongoDB but not persistence
- Session storage

### 9.3 Trade-offs

- Same MVCC, document concurrency, indexes, aggregation as on-disk WT
- Sustains higher write throughput (no journal/checkpoint cost)
- Can act as a replica-set secondary alongside on-disk primaries — but every secondary needs enough RAM
- `WT_CACHE_FULL` errors are **explicit** and abort the operation (vs. on-disk where they'd just throttle)

---

## 10. Encryption at Rest

MongoDB Enterprise integrates encryption-at-rest at the WT block manager layer.

### 10.1 Cipher

- Default: **AES-256-CBC** via OpenSSL
- Linux only: also supports **AES-256-GCM** (authenticated encryption — strongly preferred)
- The cipher is applied per-page after compression but before disk write

### 10.2 Key management

Two options for the master key:

1. **KMIP**: integration with an external KMIP-compliant appliance (HashiCorp Vault Enterprise, Thales CipherTrust, Fortanix, etc.)
   - Default protocol version 1.2; configurable to 1.0/1.1 with `security.kmip.useLegacyProtocol: true`
2. **Local keyfile**: read from a file on disk (test/dev only)

The master key encrypts per-database keys (DEKs). DEKs are stored in `WiredTiger.wt` and encrypted with the master key. Master-key rotation re-wraps DEKs without re-encrypting data.

### 10.3 Atlas behavior

Atlas always uses encryption-at-rest; cloud-provider key (CMK) integration via AWS KMS, Azure Key Vault, GCP KMS is available at the cluster level — that's BYOK over the same WiredTiger layer.

---

## 11. Diagnostic Surface

### 11.1 db.serverStatus().wiredTiger — what to look at

```js
const wt = db.serverStatus().wiredTiger;

// Cache utilization
wt.cache["bytes currently in the cache"]
wt.cache["maximum bytes configured"]
wt.cache["tracked dirty bytes in the cache"]

// Eviction pressure
wt.cache["pages evicted by application threads"]   // !!! > 0 = throttling
wt.cache["eviction worker thread evicting pages"]
wt.cache["unmodified pages evicted"]
wt.cache["modified pages evicted"]

// History store
wt.cache["history store table on-disk size"]
wt.cache["history store table updates inserted into history store"]

// Transactions / concurrency
wt.concurrentTransactions   // pre-7.0
wt.transaction["transaction read timestamp of the oldest active reader"]

// Checkpoint
wt["checkpoint"]["most recent time (msecs)"]
```

### 11.2 FTDC — the post-incident truth source

FTDC writes to `dbPath/diagnostic.data/` at ~1 Hz: hundreds of metrics, ~1 MiB/hour, < 1% CPU overhead. **Every metric above is captured here as a time series.**

Tools:
- `mongo-ftdc` — Grafana-fed dashboards
- `keyhole` (Percona) — Go CLI parser, prints WT cache/eviction/checkpoint summaries
- `tsdiag` (MongoDB internal) — bundles FTDC + logs + serverStatus for support cases

Key derived metrics to compute from FTDC deltas:
- `pages evicted by application threads` / second → throttling rate
- `history store table on-disk size` slope → long-txn pressure
- `cache.bytes currently in the cache / maximum bytes configured` → cache used %
- `tracked dirty bytes / maximum bytes configured` → dirty %

### 11.3 Verbose component logging

For deep-dive investigation, enable WT-component log verbosity in `mongod.conf`:

```yaml
systemLog:
  component:
    storage:
      wt:
        verbosity: 1
        verbose:
          WTCHKPT: { verbosity: 2 }
          WTEVICT: { verbosity: 2 }
          WTHS: { verbosity: 2 }
          WTRECOV: { verbosity: 1 }
          WTRTS: { verbosity: 1 }
          WTCMPCT: { verbosity: 1 }
```

This bloats logs fast — turn off when done. Diagnostic categories: `WTCHKPT` (checkpoint), `WTEVICT` (eviction), `WTHS` (history store), `WTRECOV` (recovery), `WTRTS` (rollback-to-stable), `WTCMPCT` (compaction).

### 11.4 wt CLI tool

The WT distribution ships a `wt` command that opens a `.wt` file directly. Useful in disaster recovery and Percona-style forensics. Not in the mongod binary — you build it from the WT source tree. Common commands:

```
wt -h <dbPath> list
wt -h <dbPath> dump file:collection-0--<ulid>.wt
wt -h <dbPath> printlog -u   # decode journal
wt -h <dbPath> stat file:collection-0--<ulid>.wt
```

---

## 12. Practical Tunables (the short list)

| Knob | mongod.conf | What it changes | When to touch |
| --- | --- | --- | --- |
| `cacheSizeGB` | `storage.wiredTiger.engineConfig.cacheSizeGB` | Internal cache size | Cgroup mismatch; container deployments; multi-`mongod` hosts |
| `journalCompressor` | `storage.wiredTiger.engineConfig.journalCompressor` | snappy/zlib/zstd/none | CPU-vs-IO trade for write-heavy workloads |
| `blockCompressor` | `storage.wiredTiger.collectionConfig.blockCompressor` | Default for new collections | New deployments; switch existing collections via collMod |
| `prefixCompression` | `storage.wiredTiger.indexConfig.prefixCompression` | Index prefix dedup | Almost never |
| `engineConfigString` | `--wiredTigerEngineConfigString` (CLI) or `setParameter: { wiredTigerEngineConfigString: "..." }` | Raw WT config string passed at startup | Last resort, when nothing else exposes the knob (no equivalent under `storage.wiredTiger`) |
| `wiredTigerEngineRuntimeConfig` | `setParameter:` | Runtime eviction/checkpoint config | Live ops without restart |
| `syncPeriodSecs` | `storage.syncPeriodSecs` | Checkpoint interval | Rarely; longer = larger journal, more recovery time |
| `transactionLifetimeLimitSeconds` | `setParameter:` | Max multi-doc transaction age | Bumping for long ETL jobs |
| `minSnapshotHistoryWindowInSeconds` | `setParameter:` | History store retention floor | PITR planning, change-stream requirements |
| `storageEngineConcurrent{Read,Write}Transactions` | `setParameter:` | Override dynamic tickets | Pre-7.0 only; disables dynamic algorithm in 7.0+ |

Raw WT config string passthrough (for parameters MongoDB doesn't expose directly):

```yaml
storage:
  wiredTiger:
    engineConfig:
      configString: "cache_size=64GB,eviction=(threads_min=8,threads_max=16),checkpoint=(wait=120,log_size=2GB)"
```

---

## 13. Practical Patterns

### 13.1 Cache sizing

1. Estimate **working set** — the set of pages touched in a typical hour. Often << total data.
2. Target: WT cache ≥ working set, with 20% headroom.
3. Leave ~50% of RAM for OS filesystem cache.
4. On containers, **pin `cacheSizeGB`** to a value that respects the cgroup limit.
5. Don't blindly set `cacheSizePct: 80` — that leaves nothing for the rest of mongod (connections, plan cache, query operators, TCMalloc fragmentation) and nothing for the kernel.

### 13.2 Diagnose cache pressure (decision tree)

```
1. Is cache used % > 80% sustained?
     YES → potential under-sizing or working-set blow-up
     NO  → maybe dirty pressure only

2. Is dirty % > 5% sustained?
     YES → reconciliation can't keep up:
            a. Check eviction worker count vs. dirty pages backlog
            b. Check disk write latency (FTDC: disk write time)
            c. Check for long-running transactions (oldest active reader)

3. Is pages evicted by application threads > 0?
     YES → application threads are doing eviction, latency is climbing
            → bump threads_min/threads_max
            → consider larger cache
            → look for write amplification (over-indexing, bad ESR)

4. Is history store on-disk size growing unboundedly?
     YES → long-running transactions or readers are pinning history
            → query for active sessions, kill if needed
            → audit mongodump, change streams, snapshot reads
            → tighten minSnapshotHistoryWindowInSeconds
```

### 13.3 Switching block compression on a live collection

```js
// Switch new pages to zstd; existing pages stay snappy until rewritten
db.runCommand({
  collMod: "events",
  storageEngine: {
    wiredTiger: { configString: "block_compressor=zstd" }
  }
})

// To re-compress existing data, do a logical rewrite or compact:
db.runCommand({ compact: "events", force: true })
```

### 13.4 Switching the journal compressor to zstd

```yaml
storage:
  wiredTiger:
    engineConfig:
      journalCompressor: zstd   # snappy (default) | zlib | zstd | none
```

Takes effect on next `mongod` restart. Pre-existing journal files keep their original compressor until they roll over (every ~100 MB or at checkpoint boundaries).

### 13.5 Estimating compressed footprint

```js
db.events.stats({ scale: 1024*1024 }).wiredTiger["block-manager"]
// On-disk bytes vs. uncompressed sizes → effective compression ratio
db.events.stats({ scale: 1024*1024 }).size               // uncompressed (logical)
db.events.stats({ scale: 1024*1024 }).storageSize        // compressed (on-disk)
```

Index footprint:

```js
db.events.stats().indexSizes   // per-index on-disk bytes (post prefix compression)
```

---

## 14. Anti-Patterns

| Anti-pattern | Why it's bad | Fix |
| --- | --- | --- |
| Setting `cacheSizeGB` to 80% of RAM | Starves OS FS cache, TCMalloc, plan cache; cgroup OOMs in containers | Aim for ~50% in dedicated, lower in shared hosts; never exceed `cacheSizePct: 80` |
| Disabling the journal in a replica set | No durability between checkpoints; PSS still survives but loses recovery resilience | Always keep journal on; use `j:false` write concern only when truly safe |
| Disabling prefix compression on indexes | Burns disk and cache for no benefit; slower scans (fewer keys/page) | Leave it on |
| Long multi-document transactions | Pin history store; bloat cache; throttle eviction | Keep transactions < 60 s; raise `transactionLifetimeLimitSeconds` reluctantly |
| Manually pinning ticket counts on 7.0+ | Disables the dynamic algorithm; under-throughput | Leave defaults; tune only with hard evidence and queue-depth data |
| Forgetting `cacheSizeGB` in containers | Sizes against host RAM, exceeds cgroup, OOMKilled | Pin explicitly to ≤ 50% of cgroup limit |
| Treating snappy as obsolete | It's still fastest; perfectly fine for OLTP | Use zstd only when ratio matters and CPU headroom exists |
| Running `mongodump` against busy collection without `--snapshotHistoryWindow` planning | Pins old snapshot → history store explodes | Use Atlas snapshots or quiescent windows |
| Reading FTDC by eye | Easy to miss multi-hour trends | Use mongo-ftdc / keyhole / tsdiag for time-series view |
| Confusing `syncPeriodSecs` with journal flush | They're different mechanisms | `syncPeriodSecs` = checkpoint; journal = 100 ms group commit |

---

## 15. Troubleshooting Recipes

### 15.1 "Cache full" / WT_CACHE_FULL

**Symptoms**: `WT_CACHE_FULL` in mongod log; high latency; ops timing out.

**Investigation**:
```js
db.serverStatus().wiredTiger.cache
// Look for: bytes currently in cache, tracked dirty bytes, application thread evictions
```

**Action ladder** (cheap → expensive):
1. Increase `eviction.threads_min/max`
2. Lower `eviction_target` from 80 to 75 (start evicting sooner)
3. Increase `cacheSizeGB` if there's RAM headroom
4. Audit indexes — fewer indexes = fewer dirty pages on write
5. Audit long transactions — kill any pinning history
6. Move to a larger Atlas tier or instance type

### 15.2 Persistent dirty % above 20%

**Cause**: reconciliation can't keep up. Either disk write throughput is the bottleneck, or update lists are pinned by long transactions.

**Investigation**:
```js
// FTDC: disk write time per second
// FTDC: cache.history store on-disk size delta
// db.currentOp({ "$or":[{secs_running:{$gt:60}},{"command.lsid":{$exists:true}}] })
```

**Action**:
1. Increase eviction threads
2. Verify disk IOPS / throughput against tier
3. Kill long transactions or readers
4. Move to provisioned IOPS storage

### 15.3 History store growing unbounded

**Symptom**: `WiredTigerHS.wt` file size growing; `cache.history store on-disk size` climbing.

**Cause**: oldest active reader is pinned far in the past.

**Investigation**:
```js
db.serverStatus().wiredTiger.transaction["transaction read timestamp of the oldest active reader"]
// Compare to current cluster time — if it's hours old, you have a problem.
db.currentOp({ "$or":[
  { secs_running:{$gt:60} },
  { active:true, "lsid":{$exists:true} }
] })
```

**Action**: kill the offending reader, lower `minSnapshotHistoryWindowInSeconds` if appropriate, audit long-running aggregations, mongodumps, and change-stream consumers.

### 15.4 Read/write ticket starvation

**Pre-7.0 symptom**: `wiredTiger.concurrentTransactions.read.available` → 0 sustained.

**7.0+ symptom**: `queues.execution.read.in > 0` sustained (queue depth, not available count).

**Action**:
1. Speed up the operations holding tickets (slow queries / locked writes)
2. Profile with `db.currentOp({ active:true, secs_running:{$gt:1} })`
3. Do **not** raise ticket count blindly — it disables the dynamic algorithm and often makes throughput worse

### 15.5 Slow startup / recovery

**Cause**: checkpoint was old, journal is large, recovery must replay a lot.

**Investigation**: look at the WT recovery message at startup — it prints how many records were replayed.

**Action**:
1. Lower `syncPeriodSecs` to make checkpoints more frequent
2. Pre-warm the cache on an upgraded node before serving traffic (see `mongodb-upgrade-paths` cookie pre-warm SOP)

### 15.6 Cold-cache after restart / failover

**Symptom**: latency spike, query queue blowup, replica catch-up slow.

**Cause**: Working set has to be re-read from disk.

**Action**:
1. Pre-warm via touch/find on hot collections in a scripted warm-up
2. Use Atlas pre-warmed disks (newer tiers cache more of the working set)
3. Don't restart all nodes at once

### 15.7 Corruption: validate, repair, and forensics

WiredTiger pages are checksummed (CRC32C by default); the block manager will reject a torn page on read with `WT_ERROR`. Symptoms: `corrupt WT page`, `checksum mismatch`, `WT_PANIC`, or mongod refusing to start.

**Triage path** (in order of escalating risk):

1. **Stop the node** if it's still up — further writes can amplify damage
2. **Run `db.collection.validate({ full: true })`** on a healthy replica to confirm the issue is local to the affected node
3. **Re-sync from a healthy replica** (initial sync) — the safest path for a single-node corruption in a replica set
4. **`--repair`**: `mongod --repair --dbpath <dbPath>` — last-resort rewrite that drops any unrecoverable data. Always back up `dbPath/` before running. Repair does not preserve replica-set membership; the node must be re-added afterward.
5. **`wt verify`**: low-level forensic check on individual `.wt` files using the standalone WT CLI tool (built from the WT source tree)

`WT_PANIC` is unrecoverable in-process. The node has to be restarted; if it panics again on startup, treat it as data-file corruption and follow the path above. Never run `--repair` on a node still serving traffic.

### 15.8 Index builds inflating the cache

Background index builds (post-4.2) hold uncommitted entries in the WiredTiger cache until commit. Symptoms during a build:
- Cache used % climbs and stays high
- Dirty % climbs
- `serverStatus().wiredTiger.cache["bytes belonging to the cache overhead"]` grows

**Action**:
- Throttle with `maxIndexBuildMemoryUsageMegabytes` (default 200 MB per build)
- Schedule large index builds in low-traffic windows
- For very large collections, consider rolling index builds across replica-set members

---

## 16. Version-Specific Notes

| Version | WiredTiger-relevant change |
| --- | --- |
| 3.2 | WT becomes default storage engine; supersedes MMAPv1 |
| 3.4 | Cache size formula changes to `max(50% × (RAM - 1 GiB), 256 MiB)` |
| 3.6 | Causal consistency, snapshot reads; deeper timestamp use |
| 4.0 | Multi-doc transactions on replica sets — heavier MVCC use |
| 4.2 | Distributed transactions; introduces durable history store work |
| 4.4 | **History store (`WiredTigerHS.wt`)** replaces lookaside; major rewrite of the MVCC retention layer |
| 5.0 | `minSnapshotHistoryWindowInSeconds` parameter introduced; time-series collections default to zstd |
| 6.0 | `cacheSizePct` configuration; queryable encryption GA built on the WT layer |
| 7.0 | **Dynamic ticketing algorithm** for concurrent transactions; lower baseline ticket usage |
| 8.0 | TCMalloc switch (lower fragmentation); SBE/ExpressPlan integration with WT B-tree traversal; reader-writer mutex improvements; 36% read perf, 32% mixed perf gains |
| 8.2 | Continued tuning; minor WT subsystem improvements |

---

## 17. Related Skills

- `mongodb-performance-troubleshooting` — surface-level triage; this skill is the deep dive
- `mongodb-capacity-planning` — uses WT cache sizing formulas
- `mongodb-monitoring-observability` — FTDC parsing, Atlas metrics
- `atlas-diagnostics-expert` — ts-diag and diagnostic packaging
- `mongodb-upgrade-paths` — references cache pre-warm SOP (Cookie 7.0→8.0 lesson)
- `mongodb-transactions` — multi-doc transaction layer above WT
- `mongodb-encryption` — CSFLE/QE complement to WT encryption-at-rest
- `mongodb-indexes-deep` — prefix compression interaction with index design
- `mongodb-time-series` — bucket columnar layout sits on WT zstd default
- `mongodb-backup-restore` — checkpoint/journal interaction with backup snapshots
- `mongodb-disaster-recovery` — `--repair` workflow, validate(), and forensic recovery from data-file corruption

---

## 18. References

Primary documentation:
1. **MongoDB Manual — WiredTiger Storage Engine**: <https://www.mongodb.com/docs/manual/core/wiredtiger/>
2. **MongoDB Manual v8.2 — WiredTiger Storage Engine**: <https://www.mongodb.com/docs/v8.2/core/wiredtiger/>
3. **WiredTiger Source — Eviction Architecture**: <https://source.wiredtiger.com/develop/arch-eviction.html>
4. **WiredTiger Source — Cache Architecture**: <https://source.wiredtiger.com/develop/arch-cache.html>
5. **WiredTiger Source — History Store**: <https://source.wiredtiger.com/11.0.0/arch-hs.html>
6. **WiredTiger Source — Transactions**: <https://source.wiredtiger.com/develop/arch-transaction.html>
7. **WiredTiger Source — Timestamps**: <https://source.wiredtiger.com/develop/arch-timestamp.html>
8. **WiredTiger Source — Commit-level Durability Tuning**: <https://source.wiredtiger.com/develop/tune_durability.html>
9. **WiredTiger Source — Debugging**: <https://source.wiredtiger.com/develop/debugging.html>
10. **WiredTiger Source — Cache and Eviction Tuning (6.0)**: <https://source.wiredtiger.com/mongodb-6.0/tune_cache.html>

Engineering blogs:
11. **MongoDB Engineering — 8.0 Performance Improvements**: <https://www.mongodb.com/company/blog/mongodb-8-0-improving-performance-avoiding-regressions>
12. **Foojay / MongoDB — Inside the Engine: 8.0 Performance Relay**: <https://foojay.io/today/inside-the-engine-the-sub-millisecond-performance-relay-of-mongodb-8-0/>
13. **Percona — WiredTiger Logging and Checkpoint Mechanism**: <https://www.percona.com/blog/wiredtiger-logging-and-checkpoint-mechanism/>
14. **Percona — Compression Methods: Snappy vs. Zstd**: <https://www.percona.com/blog/compression-methods-in-mongodb-snappy-vs-zstd/>
15. **Percona — MongoDB 101: Tuning WiredTiger Cache**: <https://www.percona.com/blog/mongodb-101-how-to-tune-your-mongodb-configuration-after-upgrading-to-more-memory/>
16. **Datadog — Monitoring WiredTiger Performance Metrics**: <https://www.datadoghq.com/blog/monitoring-mongodb-performance-metrics-wiredtiger/>
17. **Mydbops — MongoDB 7.0 Dynamic WiredTiger Tickets**: <https://www.mydbops.com/blog/mongodb-7-wiredtiger-tickets>
18. **MongoDB Dev.to — Durable History Store (WiredTigerHS.wt)**: <https://dev.to/mongodb/mongodb-mvcc-durable-history-store-wiredtigerhswt-mn2>
19. **WiredTiger Wiki — Reconciliation Overview**: <https://github.com/wiredtiger/wiredtiger/wiki/Reconciliation-overview>
20. **MongoDB Repo — WT Storage Engine README**: <https://github.com/mongodb/mongo/blob/master/src/mongo/db/storage/wiredtiger/README.md>
