<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Created 2026-07-14.
> Sibling MongoDB sub-topics are reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" pointers that name a bare sibling; instead
> load that topic's `references/<name>.md` from the owning hub (see the hub's "Cross-hub map").

---
name: mongodb-7.0-vs-8.0-differences
title: "MongoDB 7.0 vs 8.0 — Engine, Feature & Behavior Differences"
description: >
  What actually CHANGED technically between MongoDB 7.0 and 8.0 — query-execution internals
  (ExpressPlan, TCMalloc per-CPU caches, autoCompact), the new client-level bulkWrite API, Queryable
  Encryption range queries, replication behavior (majority write-concern ack timing, oplog writer/
  applier split), sharding (same-key resharding, config shard, direct-shard-command restriction),
  index-build nuances, deprecations/removed features, default-value changes, and MongoDB's own vs.
  independently (Percona) measured performance deltas.
  TRIGGER: "what changed between MongoDB 7.0 and 8.0"; risk-assessing a 7.0→8.0 upgrade for behavior
  changes (not procedure); bulkWrite/client bulk write API; Queryable Encryption range queries; majority
  write-concern ack semantics; oplog buffer write/apply split; ExpressPlan; null-vs-undefined matching
  change; $rank/$denseRank null handling; same-key resharding; config shard; MongoDB 8.0 performance
  claims (36%/56%/200%) and their credibility; a multi-cluster 7.0→8.0 risk review.
  SKIP: HOW to execute the upgrade — FCV lifecycle, rolling upgrade runbook, driver matrix,
  rapid sequential upgrade, disk pre-warming SOP → `references/mongodb-upgrade-paths.md` (this hub); live
  performance troubleshooting of an already-upgraded cluster → `atlas-diagnostics-expert`; WiredTiger
  cache/eviction/checkpoint mechanics in general → `mongodb-expert` (references/mongodb-wiredtiger-internals.md).
category: mongodb
version: "1.0.0"
updated: "2026-07-14"
whenToUse:
  - "assessing technical risk for a MongoDB 7.0→8.0 upgrade (what could break or behave differently, not how to run the upgrade)"
  - "explaining the new client-level bulkWrite command and how it differs from the legacy collection-level bulkWrite"
  - "explaining what changed in Queryable Encryption between 7.0 and 8.0 (range queries)"
  - "explaining the majority write-concern acknowledgment timing change and its causal-consistency implication"
  - "auditing an application for the null-vs-undefined query-matching change or other 8.0 compatibility breaks"
  - "evaluating MongoDB's own 8.0 performance claims (36% read throughput, 56% bulk writes, 200% time series) against independent benchmarks"
  - "identifying deprecated/removed 8.0 features an app might depend on (LDAP auth, index filters, rangePreview QE, cleanupOrphaned)"
  - "explaining resharding-to-the-same-key or config shard behavior introduced/changed in 8.0"
whenNotToUse:
  - "FCV pinning schedule, rolling upgrade procedure, driver compatibility matrix, rapid sequential upgrade pattern, disk pre-warming SOP — use references/mongodb-upgrade-paths.md"
  - "Diagnosing a live cluster's current performance/metrics — use atlas-diagnostics-expert"
  - "General WiredTiger cache/eviction/checkpoint mechanics with no version-diff angle — use mongodb-expert (references/mongodb-wiredtiger-internals.md)"
  - "Atlas platform config/UI upgrade flow — use mongodb-atlas-expert"
keywords:
  - MongoDB 7.0 vs 8.0
  - MongoDB 8.0 changes
  - bulkWrite command
  - client bulk write API
  - Queryable Encryption range queries
  - ExpressPlan
  - TCMalloc per-CPU cache
  - majority write concern
  - oplog writer applier split
  - same-key resharding
  - config shard
  - block processing time series
  - MongoDB 8.0 performance benchmark
  - MongoDB 8.0 deprecations
  - MongoDB 8.0 compatibility changes
tags:
  - mongodb
  - version-differences
  - upgrade-risk
  - engine-internals
  - performance
  - queryable-encryption
  - sharding
  - replication
related_skills:
  - mongodb-operations-expert
  - mongodb-expert
  - mongodb-atlas-expert
  - atlas-diagnostics-expert
---

# MongoDB 7.0 vs 8.0 — Engine, Feature & Behavior Differences

> **Scope:** this reference answers "what changed" — the technical, behavioral, and default-value
> deltas between MongoDB 7.0 and 8.0. It deliberately does **not** cover upgrade procedure (FCV
> sequencing, rolling-upgrade runbook, driver matrices, rapid sequential upgrade, disk pre-warming) — that
> content lives in `references/mongodb-upgrade-paths.md` in this same hub. Use that file for *how*
> to upgrade; use this file for *what will be different* once you're on 8.0, for upgrade risk
> assessment.
> **`verified-as-of: 2026-07-14`** for all version numbers, defaults, and benchmark figures below —
> re-verify against current MongoDB release notes before quoting numbers in a customer-facing risk
> document, since patch releases (8.0.x) continue to land fixes and clarifications.

## Contents
- [Overview](#overview)
- [1. Query execution & storage-layer performance changes](#1-query-execution--storage-layer-performance-changes)
- [2. New/changed APIs — client-level bulkWrite](#2-newchanged-apis--client-level-bulkwrite)
- [3. Queryable Encryption changes](#3-queryable-encryption-changes)
- [4. Replication behavior changes](#4-replication-behavior-changes)
- [5. Sharding behavior changes](#5-sharding-behavior-changes)
- [6. Index build nuances (beyond commit quorum)](#6-index-build-nuances-beyond-commit-quorum)
- [7. Query/aggregation behavior changes](#7-queryaggregation-behavior-changes)
- [8. Deprecations and removed features](#8-deprecations-and-removed-features)
- [9. Default-value changes](#9-default-value-changes)
- [10. Time-series performance (block processing)](#10-time-series-performance-block-processing)
- [11. Performance claims: MongoDB's own numbers vs independent benchmarks](#11-performance-claims-mongodbs-own-numbers-vs-independent-benchmarks)
- [12. Known 8.0-specific regressions and platform gotchas](#12-known-80-specific-regressions-and-platform-gotchas)
- [Risk-assessment checklist for a 7.0→8.0 upgrade](#risk-assessment-checklist-for-a-70--80-upgrade)
- [References](#references)

## Overview

MongoDB 8.0 (GA September 2024) is framed by MongoDB as primarily a **performance and efficiency**
release rather than a new-surface-area release: the headline engineering work was a dedicated
internal effort (an initial "tiger team," later scaled to roughly 75 engineers) that shipped 8+
major performance projects plus 140+ smaller tickets against the query-execution and replication
paths.[^perfblog] There is no WiredTiger on-disk format change between 7.0 and 8.0 — the storage
engine's cache/eviction/checkpoint *mechanics* are unchanged (see `mongodb-expert` for those
internals); what changed is **how MongoDB decides to execute work** (query planning fast paths,
memory allocation, write acknowledgment timing) and a set of **new commands and behavior changes**
layered on top of the same engine. This file catalogs those deltas.

## 1. Query execution & storage-layer performance changes

- **ExpressPlan (fast-path query execution).** Simple queries — `_id`-equality lookups, updates/
  deletes on a unique-index field, and other unique-index lookups — previously spent measurable time
  in the general-purpose query planner before reaching the actual index-scan (IDHACK) execution
  stage. MongoDB 8.0 introduces an "ExpressPlan" code path that bypasses full query planning for
  these patterns entirely, cutting per-operation overhead for the single most common workload
  shape.[^perfblog] Rejected/cached query-plan output also changed shape: rejected plans now contain
  only the `find` portion of a query, whereas earlier versions could include aggregation stages such
  as `$group` in the rejected-plan record.[^rn80]
- **TCMalloc upgraded to per-CPU caching.** 8.0 ships an upgraded TCMalloc allocator that uses
  per-CPU caches instead of per-thread caches, reducing memory fragmentation and improving behavior
  under high-concurrency stress.[^rn80][^compat80] New `serverStatus` fields expose this directly:
  `tcmalloc.usingPerCPUCaches`, `tcmalloc.generic.peak_memory_usage`, `tcmalloc.tcmalloc.cpu_free`,
  and per-CPU cache overflow/underflow counters.[^rn80]
  - `tcmallocReleaseRate` default changed from `1` to `0` (units also changed to bytes/second) —
    see [§9](#9-default-value-changes).
  - `tcmallocAggressiveMemoryDecommit` is deprecated.[^compat80]
  - **Known platform gotcha:** MongoDB 8.0+ is incompatible with Linux kernel 6.19 due to a TCMalloc
    interaction bug and will crash on startup — check target kernel versions before upgrading.[^rn80]
- **Background compaction: new `autoCompact`.** 8.0 adds an `autoCompact` command for automated
  background compaction that keeps free space per collection/index under a configurable
  `freeSpaceTargetMB` threshold, plus a `dryRun` option on `compact` that estimates reclaimable space
  without performing the compaction.[^rn80] A **breaking change**: running multiple concurrent
  `compact` commands against the *same* collection now returns an error (previously tolerated).[^compat80]
- **Admission control: new ingress queue.** A new queue stage sits between the network layer and
  database execution, with a configurable maximum to bound concurrent operation admission; unrestricted
  by default.[^rn80]
- **Concurrent DDL on different collections.** Multiple DDL operations (e.g., index builds, collection
  creation) against *different* collections in the same database can now execute concurrently — new
  `DDLDatabase`/`DDLCollection` lock types back this (first landed in 7.1, carried into 8.0).[^rn80]

## 2. New/changed APIs — client-level bulkWrite

- **New `bulkWrite` server command (8.0).** Unlike the pre-existing `db.collection.bulkWrite()`
  method, which is scoped to a single collection, the new **client-level** `bulkWrite` command lets a
  driver batch insert/update/delete operations across **multiple collections and multiple
  databases** in one server round trip.[^bwspec][^bwcmd] Each driver exposes it at the client object
  level, not the collection level (e.g., `MongoClient::bulkWrite()` in PHP, `client.bulk_write()` in
  PyMongo, `Client.BulkWrite()` in Go). **Driver minimums**: Node.js driver 6.10+, PyMongo (server
  8.0+ required regardless of driver version), similar floors for other drivers — verify the specific
  driver's compatibility page before relying on it.[^bwcmd]
- **Performance**: MongoDB reports up to **56% faster bulk writes** on 8.0 vs 7.0, attributed largely
  to fewer round trips for mixed-namespace batches.[^rn80][^sdtimes] Treat this as workload-dependent
  (see [§11](#11-performance-claims-mongodbs-own-numbers-vs-independent-benchmarks)).
- **New collection-management commands**: `moveCollection` (move an *unsharded* collection between
  shards) and `unshardCollection` (convert a sharded collection back to unsharded) are new in
  8.0.[^rn80]

## 3. Queryable Encryption changes

- **Range queries on encrypted fields are new in 8.0.** Before 8.0, Queryable Encryption (QE)
  supported only equality (`$eq`) queries on encrypted fields. MongoDB 8.0 adds range comparison
  support (`$lt`, `$lte`, `$gt`, `$gte`) directly against encrypted data, without server-side
  decryption — the motivating use case is workloads like "find transactions in amount range X–Y"
  while keeping the amount field encrypted end-to-end.[^qeoverview][^qeblog] Both equality and range
  queries are GA/production-supported as of 8.0.[^qeoverview]
- **`rangePreview` removed.** The pre-GA `rangePreview` QE algorithm used in earlier previews is
  deprecated and removed in 8.0 — use the GA `range` algorithm instead. Any pilot/PoC code written
  against `rangePreview` must be migrated.[^compat80]
- Prefix/suffix/substring encrypted-field query types exist only as **public preview starting in
  8.2**, not 8.0 — do not assume they are available on 8.0 GA.[^qeoverview] (Flag this explicitly in
  any customer-facing capability matrix; it is an easy point of confusion since it's frequently
  bundled together with "range queries" in vendor summaries.)
- For CSFLE/QE mechanics that are unchanged between the two majors (KMS providers, `crypt_shared`,
  DEK rotation, contention factor/sparsity), defer to `references/mongodb-encryption.md` in this hub
  — this section covers only the 7.0→8.0 delta.

## 4. Replication behavior changes

- **Majority write-concern acknowledgment timing changed — this is the single most consequential
  behavioral change for application correctness.** Previously, a `{ w: "majority" }` write returned
  acknowledgment only after a majority of replica-set members had both journaled **and applied** the
  write to their in-memory collection state. Starting in 8.0, the server acknowledges a majority write
  as soon as a majority of members have **journaled the oplog entry** — before those members have
  necessarily applied it to the queryable collection state.[^compat80][^rn80] This was deliberately
  engineered to cut replication-acknowledgment latency and was validated with roughly three months of
  TLA+ formal verification before shipping.[^perfblog]
  - **Practical implication**: an application that issues a majority write and then immediately reads
    from a secondary (without causal consistency / read-your-own-writes session guarantees) can now
    observe a **larger window** where that secondary does not yet reflect the write, compared to 7.0.
    Durability is unaffected (the entry is journaled before ack) — this is a **visibility/causal-
    consistency** change, not a durability regression. Applications relying on implicit "majority write
    ack implies readable everywhere" behavior without explicit causally-consistent sessions are the
    ones at risk; this is a natural audit item for a multi-cluster 7.0→8.0 risk review.
- **Oplog buffer split into separate write and apply stages.** Secondaries previously used a single
  oplog buffer; 8.0 splits this into a writer thread (reads from the primary, appends to the local
  oplog) and an applier thread (asynchronously applies the buffered entries), running in
  parallel.[^rn80][^compat80] This is part of what enables the earlier-ack behavior above.
  - `metrics.repl.buffer.count`, `.maxSizeBytes`, `.sizeBytes` are **deprecated** in favor of two new
    metric families: `metrics.repl.buffer.apply.*` and `metrics.repl.buffer.write.*`.[^rn80][^compat80]
  - New `replSetGetStatus` fields track this split explicitly: `electionCandidateMetrics.
    lastSeenWrittenOpTimeAtElection`, `electionParticipantMetrics.lastWrittenOpTimeAtElection`,
    `members[n].optimeWritten`/`optimeWrittenDate`, `members[n].lastWrittenWallTime`.[^rn80]
- **Performance claim**: MongoDB reports up to **20% faster concurrent writes during replication** on
  8.0 attributable to this change.[^rn80][^sdtimes]

## 5. Sharding behavior changes

- **Resharding to the same shard key (new in 8.0).** You can now reshard a collection using its
  *existing* shard key — useful for redistributing data across newly added shards/zones without a
  shard-key change — via `reshardCollection`, and it's substantially faster than the prior
  range-migration-based redistribution path.[^reshardsamekey] A new `forceRedistribution` option
  speeds same-key redistribution further.[^rn80]
- **Resharding performance overhaul.** Starting in 8.0, resharding reads source data using a natural-
  order scan, clones all data first, and only then builds the required indexes on the recipient
  shard — MongoDB describes this as an "orders of magnitude" speed improvement over the prior
  resharding implementation.[^reshard][^rn80]
- **DDL vs. shard-topology-change ordering.** If a shard is added or removed while a DDL operation
  (e.g., `reshardCollection`) is in flight, the add/remove now waits until the concurrent DDL
  operation finishes, rather than racing it.[^rn80]
- **Config shard topology (introduced 7.0, expanded in 8.0).** Config servers can now double as a data
  shard ("config shard"). New commands `transitionToDedicatedConfigServer` and
  `transitionFromDedicatedConfigServer` move between topologies, and a new `directShardOperations`
  role exists for shard-level maintenance access.[^rn80] Note the **downgrade gate**: if a cluster
  uses config-shard topology, `transitionToDedicatedConfigServer` must run *before* downgrading FCV
  below 8.0 — there is no path back through FCV downgrade alone (cross-reference:
  `references/mongodb-upgrade-paths.md` §4, "Config shard caveat").
- **Direct-to-shard command restriction (breaking change).** Starting in 8.0, only a curated allowlist
  of commands can be run by connecting directly to a shard's mongod instead of through `mongos`; other
  commands now return an explicit error directing you to connect via the router.[^compat80] Any
  internal tooling, health-check script, or backup automation that bypasses `mongos` and talks to a
  shard node directly should be audited before upgrade — this is a realistic break point for
  home-grown operational scripts.
- **Default empty-collection chunk count changed**: 1 chunk per shard (was 2) for empty collections
  sharded with a hashed shard key — see [§9](#9-default-value-changes).
- **`$lookup` now permitted inside a transaction against a sharded collection** (previously
  restricted).[^rn80]
- **`findAndModify` and `deleteOne()` now accept partial shard-key queries.**[^rn80]
- **`$shardedDataDistribution` output narrowed**: only returns a collection's primary-shard entry if
  that shard actually has chunks or orphaned documents for the collection (previously could report an
  empty/zero entry).[^compat80]

## 6. Index build nuances (beyond commit quorum)

`references/mongodb-upgrade-paths.md` §6 already documents the 8.0 **commit-quorum vs write-concern**
semantic split for index builds — that content is not repeated here. Additional 8.0 index-related
changes not covered there:

- **Index builds now explicitly check for failed/aborted build state** as part of build-lifecycle
  handling, tightening how aborted builds interact with `commitQuorum`.[^rn80]
- **Compound wildcard indexes cannot back a shard key** — disallowed as of 8.0 where previously this
  was either unsupported silently or inconsistently enforced.[^rn80]
- **Index filters are deprecated** in favor of `setQuerySettings`/query settings, which persist more
  durably and offer more control — see [§8](#8-deprecations-and-removed-features). Any customer
  automation that manages `planCacheSetFilter` should plan a migration to query settings.
- **`queryHash` is being superseded by `planCacheShapeHash`** — both are emitted for now, but
  `queryHash` is slated for removal in a later release; tooling keyed on `queryHash` should migrate.[^compat80]

## 7. Query/aggregation behavior changes

- **`null` no longer matches `undefined` in equality contexts (breaking change).** Comparisons to
  `null` in `$eq`, `$in`, and `$lookup` no longer match fields with the BSON `undefined` type; they
  match only fields that are literally `null` or absent. Applications that stored `undefined` values
  (common from older Node.js drivers/ODMs) and relied on `{ field: null }` queries to catch them will
  see a behavior change on 8.0 — MongoDB publishes an explicit migration guide for this.[^compat80]
  This is a strong candidate for a pre-upgrade application-code and data audit, not just a server
  config check.
- **`$rank` / `$denseRank` now treat `null` and missing fields identically** when computing rank over
  a `sortBy` — aligning their behavior with `$sort`'s existing null/missing handling (previously they
  could diverge).[^rn80]
- **Geospatial queries reject malformed input (breaking change).** Certain geospatial query shapes
  that were previously silently accepted despite being malformed now throw an error.[^compat80]
- **`$convert` gains binData ⇄ string conversion**, plus a new `$toUUID` helper for string→UUID
  conversion.[^rn80]
- **Sorting on a field that doesn't exist across all documents** carries no guaranteed output
  ordering, and that ordering may legitimately differ between versions — documented explicitly as a
  compatibility note for 8.0.[^compat80]
- **Hedged reads no longer used by default** for `nearest` read preference; explicit opt-in now logs a
  warning. (Also see [§9](#9-default-value-changes).)[^compat80]

## 8. Deprecations and removed features

| Feature | Status in 8.0 | Notes |
| --- | --- | --- |
| `storeFindAndModifyImagesInSideCollection` parameter | **Removed** | No replacement needed if not in use.[^compat80] |
| `numInitialChunks` option on `shardCollection` | **Removed** | Superseded by the new default chunk-count behavior (§9).[^compat80] |
| `rangePreview` QE algorithm | **Removed** | Use the GA `range` algorithm — see [§3](#3-queryable-encryption-changes).[^compat80] |
| LDAP authentication/authorization | **Deprecated** | Will be removed in a future major release — plan migration off LDAP auth for MongoDB if in use.[^compat80] |
| Index filters (`planCacheSetFilter`) | **Deprecated** | Migrate to `setQuerySettings`.[^compat80] |
| `$accumulator`, `$function`, `$where` (server-side JS) | **Deprecated** | Server logs a warning on use; no removal date published yet.[^compat80] |
| `cleanupOrphaned` command | **Deprecated** | Use `$shardedDataDistribution` instead.[^compat80] |
| `timeField` as (part of) a shard key on time-series collections | **Deprecated** | Plan shard-key redesign if in use.[^compat80] |
| `tcmallocAggressiveMemoryDecommit` parameter | **Deprecated** | Superseded by per-CPU TCMalloc behavior.[^compat80] |
| `enableFinerGrainedCatalogCacheRefresh` parameter | **Deprecated** | — [^compat80] |
| BSON `undefined` type | **Deprecated** | Inserting a JS `undefined` value now stores `null`; combined with the §7 null-matching change, audit any code relying on the old `undefined` semantics.[^compat80] |
| `metrics.repl.buffer.{count,maxSizeBytes,sizeBytes}` | **Deprecated** | Replaced by split write/apply buffer metrics — see [§4](#4-replication-behavior-changes).[^rn80] |
| `queryHash` | **Being superseded** | `planCacheShapeHash` is the forward path; both present for now.[^compat80] |

## 9. Default-value changes

| Parameter / behavior | 7.0 default | 8.0 default | Source |
| --- | --- | --- | --- |
| `tcmallocReleaseRate` | `1` (unitless scale 0–10) | `0` (reinterpreted as bytes/second) | [^compat80] |
| Empty-collection initial chunks per shard (hashed shard key) | 2 chunks/shard | **1 chunk/shard** | [^rn80] |
| Hedged reads for `nearest` read preference | used automatically | **not used by default**; explicit opt-in logs a warning | [^compat80] |
| `serverStatus.wiredTiger.concurrentTransactions` field name | `wiredTiger.concurrentTransactions` | renamed to `queues.execution` | [^compat80] |
| Majority write-concern ack point | after apply to secondary collection state | after oplog journal on secondary (before apply) | [^compat80][^rn80] — see [§4](#4-replication-behavior-changes) |

## 10. Time-series performance (block processing)

- **Block processing** is a new, automatic query-execution model for time-series collections: instead
  of unpacking each compressed bucket into individual documents and processing them one at a time, the
  engine operates on **blocks of column-level data** directly, extending the same architectural idea
  behind columnar analytical engines into MongoDB's time-series storage.[^blockproc] It requires no
  application changes — engagement is automatic for eligible query shapes; check
  `explain().queryPlanner.winningPlan.slotBasedPlan.stages` for a block-processing plan to confirm
  it's in play for a given query.[^rn80]
- **Performance claims**: MongoDB reports **200%+** improvement for `$group`-style analytical queries
  on time-series collections vs 7.0, with some individual benchmarked queries showing operations/sec
  gains as high as ~20x (2000%) and cache-usage reductions of 10–20x for specific analytical
  patterns.[^blockproc][^rn80] These are best-case, benchmark-specific numbers — treat them as an
  upper bound, not a guaranteed uplift, for a given customer's actual query mix.
- **Known 8.0.0–8.0.3 regressions specific to time series** (fixed by 8.0.4): a time-series insert-
  batching issue (SERVER-95067) and a time-series measurement-delete issue (SERVER-94559).[^rn80] Any
  customer with heavy time-series write/delete workloads upgrading to early 8.0.x point releases
  should target **8.0.4 or later**, not 8.0.0–8.0.3.

## 11. Performance claims: MongoDB's own numbers vs independent benchmarks

MongoDB's official messaging for 8.0 (documentation and the engineering blog) states, relative to
7.0:[^rn80][^sdtimes][^perfblog]

- Up to **36% better read throughput**
- Up to **32% faster** for "typical web application" mixed read/write workloads
- Up to **56% faster bulk writes**
- Up to **20% faster concurrent writes during replication**
- **200%+** faster time-series `$group`/analytical operations (see §10)

These figures come from MongoDB's own YCSB-based benchmark suite and marketing materials. An
**independent** benchmark from Percona (using `mongo-perf`, a different tool than MongoDB's official
YCSB harness, comparing Percona Server for MongoDB 8.0.4 vs 7.0.15) found materially smaller — though
still positive and non-negative — gains:[^percona]

- **~12% faster** on average at 1 thread (some individual tests 20–30% faster)
- **~7% faster** on average at 4 threads
- **~9% faster** on average at 8 threads
- **No performance regressions observed** in any Percona test, though a few very-low-operation-volume
  tests showed slower 8.0 numbers judged "not representative"

**Risk-assessment takeaway**: MongoDB's headline percentages are workload-shape-dependent (YCSB
profiles, bulk-write-heavy, or time-series-analytics-heavy workloads see the largest gains) and were
generated on MongoDB's own benchmark harness. A customer whose workload looks more like general OLTP
CRUD under moderate concurrency should expect gains closer to Percona's ~7–12% range than to the
32–56% headline figures. Do not repeat the vendor percentages to a customer as an expected outcome
without workload-specific validation — this is exactly the kind of claim `atlas-diagnostics-expert`'s
regression-testing methodology (canary/shadow-traffic comparison, change-point detection) exists to
validate empirically pre- and post-upgrade for a specific customer's traffic.

## 12. Known 8.0-specific regressions and platform gotchas

Distinct from the deliberate behavior changes above — these are **bugs/platform incompatibilities**
relevant to upgrade risk assessment, not intentional design changes:

- **Linux kernel 6.19 incompatibility**: MongoDB 8.0+ crashes on startup on kernel 6.19 due to a
  TCMalloc interaction bug. Verify target OS/kernel before upgrade.[^rn80]
- **TLS + `openssl-3.2.2-6.el9_5` high-CPU bug**: versions before 8.0.5 running TLS against this
  specific OpenSSL package show high CPU usage even under light load. Workaround: disable TLS or use a
  different OpenSSL build until upgrading past 8.0.5.[^rn80]
- **`mongocryptd` message-size limit regression (8.0.18–8.0.19 only)**: a 16 KiB max message size bug;
  workaround is to use the `crypt_shared` library instead of `mongocryptd` on affected point
  releases.[^rn80]
- **Pre-auth DoS / buffer over-read (CVE-2025-6709, CVE-2025-6710)**: fixed; confirm target patch
  level is past the fix.[^rn80]
- **Time-series insert-batching and measurement-delete bugs (8.0.0–8.0.3, fixed 8.0.4)**: see
  [§10](#10-time-series-performance-block-processing).[^rn80]
- **Minimum supported OS bump**: RHEL 8.8+/9.3+, SUSE SLES 15 SP5+, Amazon Linux 2023.3+ required for
  8.0 — verify OS compatibility as part of pre-upgrade checks (this is additive to, not a replacement
  for, the pre-upgrade checklist in `references/mongodb-upgrade-paths.md` §6).[^rn80]

## Risk-assessment checklist for a 7.0→8.0 upgrade

This is a *behavior-change* audit list — pair it with the procedural pre-upgrade checklist in
`references/mongodb-upgrade-paths.md` §6, which covers FCV/index-build/oplog/backup gates.

1. **Causal consistency audit**: does any application path read from a secondary immediately after a
   majority write without an explicit causally-consistent session? The earlier-ack timing change
   (§4) widens the staleness window on 8.0.
2. **`null`/`undefined` query audit**: grep for `{ field: null }`-style queries and confirm no code
   path relies on matching BSON `undefined` values (§7, §8).
3. **Direct-shard-connection audit**: any backup script, health check, or internal tool that connects
   directly to a shard mongod (bypassing `mongos`) will break under the new command allowlist (§5).
4. **Index filter / `queryHash` dependency audit**: any tooling keyed on `planCacheSetFilter` or raw
   `queryHash` values needs a migration path to `setQuerySettings`/`planCacheShapeHash` (§6, §8).
5. **LDAP auth dependency**: flag for future-proofing even though only deprecated, not removed, in
   8.0 (§8).
6. **Queryable Encryption `rangePreview` usage**: any pilot code against the removed preview algorithm
   must migrate to GA `range` before upgrade (§3, §8).
7. **Time-series shard-key-on-`timeField` usage**: flag for redesign (deprecated, §8).
8. **Point-release floor for time-series-heavy workloads**: target ≥8.0.4, not 8.0.0–8.0.3 (§10, §12).
9. **Kernel/OS compatibility**: confirm target OS is not kernel 6.19 and meets the new minimum-OS bar
   (§12).
10. **Performance-expectation calibration**: present the Percona-range (~7–12%) as the conservative
    case and the vendor range (32–56%) as the best case for the customer's specific workload shape
    (§11) — do not promise vendor headline numbers without empirical validation.

## References

[^rn80]: [Release Notes for MongoDB 8.0 — MongoDB Docs](https://www.mongodb.com/docs/manual/release-notes/8.0/)
[^compat80]: [Compatibility Changes in MongoDB 8.0 — MongoDB Docs](https://www.mongodb.com/docs/manual/release-notes/8.0-compatibility/)
[^perfblog]: [MongoDB 8.0: Improving Performance, Avoiding Regressions — MongoDB Engineering Blog](https://www.mongodb.com/company/blog/engineering/mongodb-8-0-improving-performance-avoiding-regressions)
[^percona]: [MongoDB 8.0 Performance; Does It Live Up to the Hype? — Percona](https://www.percona.com/blog/mongodb-8-0-performance-does-it-live-up-to-the-hype/)
[^sdtimes]: [MongoDB 8.0 offers significant performance improvements to read throughput, bulk writes, and more — SD Times](https://sdtimes.com/data/mongodb-8-0-offers-significant-performance-improvements-to-read-throughput-bulk-writes-and-more/)
[^bwspec]: [Bulk Write specification — mongodb/specifications on GitHub](https://github.com/mongodb/specifications/blob/master/source/crud/bulk-write.md)
[^bwcmd]: [bulkWrite (database command) — MongoDB Docs](https://www.mongodb.com/docs/manual/reference/command/bulkwrite/)
[^qeoverview]: [Queryable Encryption — MongoDB Docs](https://www.mongodb.com/docs/manual/core/queryable-encryption/)
[^qeblog]: [How to Use New Features in MongoDB 8.0 — Improved Queryable Encryption](https://oneuptime.com/blog/post/2026-03-31-mongodb-how-to-use-new-features-in-mongodb-80-improved-queryable-enc/view)
[^reshard]: [Reshard a Collection — MongoDB Docs](https://www.mongodb.com/docs/manual/core/sharding-reshard-a-collection/)
[^reshardsamekey]: [Reshard to the Same Shard Key — MongoDB Docs](https://www.mongodb.com/docs/manual/core/reshard-to-same-key/)
[^blockproc]: [Key Enhancements in MongoDB 8.0 with Block Processing — MongoDB](https://www.mongodb.com/company/blog/technical/key-enhancements-mongodb-8-0-block-processing)

Cross-reference: `references/mongodb-upgrade-paths.md` (this hub) for FCV lifecycle, rolling-upgrade
runbook, driver compatibility matrix, rapid sequential upgrade, and the disk pre-warming SOP — the procedural
counterpart to this file.
