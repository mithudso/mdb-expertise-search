<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Created by `/dr` via `concept-family-explorer` (2026-06-13).
> This is **vendor-neutral, public** cloud-database architecture scaffolding — the industry pattern of separating
> compute from storage in operational databases. Load it from the owning hub; ignore any "use the X skill" pointers
> that name a bare sibling — read that topic's `references/<name>.md` from its hub instead.

---
name: cloud-native-database-disaggregation
title: "Cloud-Native Database Storage Disaggregation"
description: >
  Vendor-neutral architecture reference for compute–storage disaggregation in cloud databases — how operational (OLTP)
  databases separate stateless compute from a shared, durable storage layer.
  TRIGGER: user asks how Aurora / Azure Hyperscale (Socrates) / AlloyDB / PolarDB / Huawei Taurus / Neon separate compute
  and storage; "log is the database"; durability-vs-availability separation; page server / GetPage@LSN; object-storage-backed
  OLTP (S3 / S3 Express One Zone); serverless database, scale-to-zero, cold starts; copy-on-write database branching;
  disaggregation performance overhead, latency amplification, or cost economics; why OLAP (Snowflake/Databricks) disaggregated
  before OLTP; whether to choose a disaggregated vs shared-nothing database.
  SKIP: MongoDB query/index/schema/engine internals (use mongodb-expert); live cluster diagnostics/perf (use atlas-diagnostics-expert);
  Atlas platform features (use mongodb-atlas-expert); general analytics-platform/OLAP engine selection (use da-data-engineering-platform,
  references/da-28-realtime-olap-databases).
category: mongodb
version: "1.0.0"
updated: "2026-06-13"
whenToUse:
  - "explaining how Aurora / Socrates-Hyperscale / PolarDB / Taurus / Neon separate compute from storage"
  - "reasoning about the 'log is the database' write path and storage-local page materialization"
  - "evaluating object-storage-backed OLTP, serverless databases, scale-to-zero, or cold-start latency"
  - "explaining copy-on-write database branching and instant point-in-time restore"
  - "setting realistic performance expectations for a disaggregated database (latency amplification, cache dependence)"
  - "deciding when disaggregation wins vs when a shared-nothing cluster is better"
  - "contrasting analytical (Snowflake/Databricks) vs operational storage-compute separation"
whenNotToUse:
  - "MongoDB query/index/schema/aggregation/engine work — use mongodb-expert"
  - "Diagnosing a live cluster's metrics/perf/capacity — use atlas-diagnostics-expert"
  - "Atlas platform features/config — use mongodb-atlas-expert"
  - "Choosing an OLAP/real-time analytics engine — use da-data-engineering-platform (da-28)"
keywords:
  - compute storage separation
  - disaggregated storage
  - cloud-native database
  - log is the database
  - page server
  - GetPage@LSN
  - durability vs availability
  - object storage OLTP
  - serverless database
  - scale to zero
  - database branching
  - copy-on-write clone
  - Aurora
  - Socrates Hyperscale
  - PolarDB
  - Neon
  - Snowflake
  - storage disaggregation performance
tags:
  - database-architecture
  - cloud-native
  - disaggregation
  - storage-compute-separation
  - serverless-database
  - distributed-systems
related_skills:
  - mongodb-operations-expert
  - mongodb-atlas-expert
  - da-data-engineering-platform
  - aws-cloud
---

# Cloud-Native Database Storage Disaggregation

> **Scope:** the public, vendor-neutral architecture pattern of separating compute from storage in cloud databases —
> the systems concepts, canonical implementations, performance/cost trade-offs, and the decision criteria for adopting it.
> **`verified-as-of: 2026-06-13`** for all version-, pricing-, and vendor-landscape claims (see footnotes); the durable
> systems principles are stable, but specific products, prices, and benchmark numbers move.

## Contents
- [Overview](#overview)
- [Core concepts](#core-concepts)
- [Canonical implementations](#canonical-implementations)
- [Object storage as primary tier & serverless databases](#object-storage-as-primary-tier--serverless-databases)
- [Copy-on-write branching](#copy-on-write-branching)
- [Performance implications](#performance-implications)
- [Cost economics](#cost-economics)
- [When disaggregation wins vs loses](#when-disaggregation-wins-vs-loses)
- [Analytical contrast: why OLAP disaggregated first](#analytical-contrast-why-olap-disaggregated-first)
- [Anti-patterns](#anti-patterns)
- [References](#references)

## Overview

"Disaggregation" (a.k.a. compute–storage separation) decouples a database's **stateless compute** tier from a
**shared, independently scalable, durable storage** tier, connected over a fast network.[^yu] The motivation is an
economic mismatch: compute is expensive and its demand is bursty, while storage is cheap and grows slowly — so coupling
them (the classic shared-nothing replica, each node owning its local disk) forces you to size both for peak load, leaving
most capacity idle.[^yu] Decoupling lets each scale on its own: add read compute without copying data, shrink compute to
zero when idle, and pool storage across many tenants for economies of scale.

The pattern is the architecture behind AWS Aurora, Azure SQL Hyperscale (Socrates), Google AlloyDB, Alibaba PolarDB,
Huawei Taurus, and Neon. Analytical systems (Snowflake, Databricks, BigQuery) adopted it earlier and more easily;
operational/OLTP systems came later because OLTP's latency-sensitive random I/O makes disaggregation much harder to do
without regressing performance.[^openaurora]

## Core concepts

- **Durability ≠ availability — separate them.** The single most important idea (made explicit in Socrates[^socrates]):
  a committed transaction's survival is guaranteed by the **log**, replicated across failure domains; **page copies** in
  the storage tier exist for read **availability** and performance, not durability. Durability needs copies across AZs but
  not fast storage; availability needs memory + fast storage but not a fixed copy count. Splitting them lets each layer be
  optimized and scaled independently.[^socrates][^taurus]
- **"The log is the database."** On the write path, compute ships **redo/WAL log records** — small, sequential — instead of
  full data pages — large, random. Aurora's framing: "the log is the database, and any pages the storage system
  materializes are simply a cache of log applications."[^aurora] This cuts write network I/O by roughly an order of
  magnitude vs page-shipping.[^aurora]
- **Storage-local replay / page materialization.** The storage tier consumes the log stream and **materializes pages**
  itself, in the background, off the transaction's critical path. Readers request a page **at a log offset** —
  `GetPage@LSN` — and the storage node returns a version replayed to at least that point.[^socrates]
- **Quorum durability.** Commit latency is bounded by achieving a **write quorum on the log**, not by page writes. Aurora
  uses 4-of-6 across 3 AZs;[^aurora] designs vary (Taurus requires all 3 log replicas to ack; PolarFS uses ParallelRaft
  2/3).[^taurus][^polarfs]
- **Recovery off the critical path.** Because the log is durably replicated and the storage tier replays continuously,
  there is no long compute-side crash recovery — a replacement compute node attaches to already-consistent storage and
  serves in seconds, not minutes.[^aurora][^yu]
- **Multi-tenant storage pooling.** A shared storage service amortizes hardware across many tenants, raising utilization
  and lowering cost vs dedicated per-node disks.[^yu]

## Canonical implementations

**AWS Aurora** (SIGMOD 2017).[^aurora] The archetype. Compute ships only redo log records; the storage volume is segmented
into 10 GB protection groups, each 6-way replicated across 3 AZs (4/6 write quorum, 3/6 read quorum). Storage nodes apply
the log locally and materialize pages; no pages are ever written from compute (no double-write buffer, no checkpoint
flush). The WAL is effectively partitioned across the storage fleet.

**Azure SQL Hyperscale / "Socrates"** (SIGMOD 2019).[^socrates][^azuredocs] Four explicitly decoupled tiers:
**Compute → Log service (XLOG) → Page servers → XStore (Azure object storage)**. A **Landing Zone** takes synchronous
3-replica log writes for durability; XLOG then *asynchronously* disseminates only **hardened** (durably-landed) log blocks
to page servers and secondaries for availability. Each **page server** owns a partition, consumes the log, and serves
`GetPage@LSN`; compute caches hot pages in local SSD (RBPEX). Contrast with Aurora: Socrates centralizes the WAL in XLOG
rather than partitioning it.[^transactional]

**Alibaba PolarDB** (PolarFS, VLDB 2018).[^polarfs] A **shared-storage** variant: one read-write primary and up to 15
read-only nodes mount the same distributed block device (PolarFS), which uses **RDMA + SPDK** user-space I/O for
near-local-NVMe latency and **ParallelRaft** (out-of-order-commit Raft) for 3-way chunk replication. The primary ships
physical redo to RO nodes, which use a per-page **LogIndex** to replay outstanding records on read.[^alibabadocs]

**Huawei Taurus** (SIGMOD 2020).[^taurus] Makes the **Log Store / Page Store** split a first-class boundary. A Storage
Abstraction Layer writes log records to 3 Log Store replicas (all must ack → commit); it then forwards records to Page
Stores where only **1 of 3** need ack (durability is already guaranteed by the log). Reads go to the fastest Page Store
holding the requested LSN. Append-only Page Store writes enable constant-time snapshots.

**Neon** (serverless Postgres) — see next section; it extends the pattern to object storage and adds branching.

## Object storage as primary tier & serverless databases

**Neon's architecture**[^neonarch][^neonpage][^neonpitr] separates stateless Postgres compute from a storage layer of two
services: **Safekeepers** (a Paxos quorum that durably buffers the WAL — commit is acked when a majority accept, bounded by
network RTT not fsync) and the **Pageserver** (ingests WAL, repartitions it by page, writes immutable **layer files** in an
LSM-tree-like structure, and answers `GetPage@LSN` by replaying deltas over a base image). Layer files are uploaded
asynchronously to **S3** as immutable history; the Pageserver is a reconstructable cache over S3. **Scale-to-zero**
suspends idle compute (default ~5 min) and reattaches a fresh node to existing storage on the next connection; median cold
start was ~1.8 s as of May 2026 (improving).[^neonarch]

**Object storage as the primary durable tier.** **S3 Express One Zone** (GA late 2023; ~85% GET / 55% PUT price cuts in
April 2025[^s3express]) brought single-digit-ms object latency, narrowing the "object storage is too slow for OLTP" gap —
though only as the *durable/cold* tier behind a local cache, never directly on the synchronous hot-read path.[^turso][^clickhouse]
The broader "zero-disk" pattern (WarpStream = Kafka-on-S3;[^warpstream] Turso = SQLite-on-S3;[^turso] RisingWave on S3[^risingwave])
makes compute fully stateless, eliminating inter-AZ replication traffic — but every one of them depends on an aggressive
local cache + write batching, because naive object-storage reads run 50–500 ms p99.[^clickhouse]

**Serverless database mechanics.** Scale-to-zero requires full storage disaggregation (compute can vanish; data persists).
The hard parts are **cold starts** (provisioning + cache warm-up; empty buffer pools regress query plans[^clickhouse]) and
**connection handling** for ephemeral compute — Postgres's ~5 MB-per-connection backends force transaction-mode pooling
(PgBouncer) or HTTP/WebSocket serverless drivers in front of scale-to-zero compute.[^neonarch]

## Copy-on-write branching

Disaggregation's immutable, LSN-addressed storage enables a **Git-like workflow for data**: create an instant branch (a
metadata pointer to a parent LSN — zero data copied), diverge it with writes (stored as deltas over the shared parent base),
then discard or reset.[^neonbranch] Storage consumed equals only the diverged pages. The same model gives **O(1)
point-in-time restore** (attach compute to any historical LSN) instead of an O(data) restore from backups.[^neonpitr] Uses:
per-PR preview databases, per-developer isolated DBs reset from prod, parallel test suites. Neon reports ~500k branches/day;
Databricks **Lakebase** (Neon-based, GA Feb 2026) ships branching as a headline feature.[^lakebase] PlanetScale (Vitess) and
Dolt offer branch-like workflows at the query/row layer, but only storage-disaggregated designs get O(1) branch creation
independent of dataset size.[^lakebase]

## Performance implications

The honest trade-off, quantified by the SIGMOD 2024 **OpenAurora** study (Pang & Wang, Purdue):[^openaurora]

- **Latency amplification.** A buffer-pool miss becomes a network `GetPage@LSN` RPC instead of a local disk read. With **no
  mitigations**, disaggregation imposed **~16x read and ~18x write** throughput reduction vs a local-SSD baseline.
- **Cache dependence.** At an 80% buffer hit ratio the read gap narrowed to **1.8x** — performance is dominated by cache hit
  rate. Disaggregated databases live and die by the local cache.
- **Writes don't benefit from caching.** Every commit ships log over the network regardless of buffer fullness, so even a
  99.5% hit ratio can't improve write latency. The **log-as-the-database** optimization (ship log, not pages) gives **~2.6x**
  write improvement under heavy load — that's what makes OLTP disaggregation viable at all.
- **Tail latency** is the residual structural problem: unreplayed pages force an on-demand replay chain at query time,
  spiking p99 with no in-path fix.[^raas]
- Versus a **highly-optimized shared-nothing** database, disaggregation can still cost up to **~10x** throughput from the
  extra network traffic.[^yu]

## Cost economics

- The core thesis: compute expensive + bursty, storage cheap + slow-growing → decouple so compute scales/pauses
  independently while cheap storage persists.[^yu] Object storage runs ~3–5x cheaper than provisioned block storage at list
  price.[^greptime]
- **Scale-to-zero** means idle hours cost nothing — only possible with full disaggregation.
- **Multi-tenant pooling** amortizes storage hardware across tenants (raises utilization).[^yu]
- **Hidden cost: cross-AZ egress.** Every inter-AZ hop is billed (~$0.01/GB each way on AWS); at high write rates,
  synchronous cross-AZ log replication + `GetPage@LSN` traffic can erode the storage savings.[^egress]

## When disaggregation wins vs loses

**Wins:** bursty/elastic load (pay proportionally); independent read-scaling (add compute, don't copy data); fast
failover/recovery (attach to durable storage in seconds); scale-to-zero / serverless billing; large mostly-cold datasets;
multi-tenant fleets that amortize shared storage.[^yu][^openaurora]

**Loses:** latency-sensitive, uniformly-hot small-random-I/O OLTP (the network hop is never amortized); steady-state
workloads with no elasticity need (a tuned shared-nothing cluster is ~10x cheaper/faster); workloads demanding the absolute
minimum p99 (replay-chain tail spikes); very high write rates where cross-AZ egress dominates.[^yu][^raas][^egress]

## Analytical contrast: why OLAP disaggregated first

Snowflake (SIGMOD 2016)[^snowflake][^snowflakeprod] popularized storage-compute separation: **virtual warehouses**
(stateless elastic compute) over centralized cloud object storage, with local-SSD caching to approach shared-nothing speed
once warm. Databricks/Delta Lake (the lakehouse, CIDR 2021)[^lakehouse] and BigQuery (Dremel + Colossus + Jupiter)[^bigquery]
follow the same shape. OLAP disaggregated **first** because analytical workloads suit it: immutable/append-heavy writes (no
MVCC or torn-page complexity), scan-oriented queries over large data (the per-fetch network cost amortizes across a
gigabyte scan), high latency tolerance (seconds-to-minutes), columnar segments that cache as large contiguous units, and a
single-writer/many-reader model that needs no `GetPage@LSN` coherence. OLTP has the opposite profile — small random reads,
millisecond budgets, many writers — which is exactly why the log-as-the-database and multi-version page techniques above had
to be invented to make operational disaggregation work.[^openaurora]

## Anti-patterns

- **Treating object storage as a hot random-read tier.** S3 Standard p99 of 200–500 ms makes naive 4 KB OLTP reads
  unusable; always front it with NVMe/SSD cache + write batching.[^clickhouse]
- **Ignoring cache sizing.** A disaggregated DB with an undersized buffer pool pays the full ~16x miss penalty; capacity
  planning must center the working-set hit ratio.[^openaurora]
- **Assuming disaggregation is universally faster.** For steady, latency-sensitive, non-elastic OLTP, a shared-nothing
  design is usually faster and cheaper.[^yu]
- **Forgetting cross-AZ egress** in the cost model — it can exceed the storage savings at high write throughput.[^egress]
- **Expecting scale-to-zero to be free of latency** — cold starts and empty caches regress the first queries after
  resume.[^clickhouse]

## References

[^aurora]: Verbitski et al., "Amazon Aurora: Design Considerations for High Throughput Cloud-Native Relational Databases," SIGMOD 2017. https://assets.amazon.science/dc/2b/4ef2b89649f9a393d37d3e042f4e/amazon-aurora-design-considerations-for-high-throughput-cloud-native-relational-databases.pdf — *paper; log-is-the-database, 6-way/4-of-6 quorum.*
[^socrates]: Antonopoulos et al., "Socrates: The New SQL Server in the Cloud," SIGMOD 2019. https://www.microsoft.com/en-us/research/wp-content/uploads/2019/05/socrates.pdf — *paper; Landing Zone/XLOG, durability vs availability, GetPage@LSN.*
[^azuredocs]: Microsoft Azure Docs, "Hyperscale distributed functions architecture." https://learn.microsoft.com/en-us/azure/azure-sql/database/hyperscale-architecture — *docs; current Hyperscale tier description.*
[^polarfs]: Cao et al., "PolarFS: An Ultra-low Latency and Failure Resilient Distributed File System for Shared Storage Cloud Database," VLDB 2018. https://www.vldb.org/pvldb/vol11/p1849-cao.pdf — *paper; shared storage, ParallelRaft, RDMA/SPDK.*
[^alibabadocs]: Alibaba Cloud Docs, "PolarDB buffer and WAL architecture / data consistency." https://www.alibabacloud.com/help/en/polardb/polardb-for-oracle/buffer-management — *docs; LogIndex, consistency LSN, primary→RO WAL replay.*
[^taurus]: Depoutovitch et al., "Taurus Database: How to be Fast, Available, and Frugal in the Cloud," SIGMOD 2020. https://arxiv.org/html/2412.02792v1 — *paper; Log Store/Page Store split, write/read path.*
[^openaurora]: Pang & Wang, "Understanding the Performance Implications of the Design Principles in Storage-Disaggregated Databases" (OpenAurora), SIGMOD 2024. https://www.cs.purdue.edu/homes/csjgwang/pubs/SIGMOD24_OpenAurora.pdf — *paper; the headline overhead numbers (16x/18x, 1.8x@80% cache, ~2.6x LogDB).*
[^yu]: Yu, "Disaggregation: A New Architecture for Cloud Databases," PVLDB 18(12), 2025. https://www.vldb.org/pvldb/vol18/p5527-xiangyao.pdf — *paper; cost-mismatch rationale, ~10x vs shared-nothing, taxonomy.*
[^raas]: Pang & Wang, "Reducing Tail Latency in Storage-Disaggregated Database Systems" (RaaS), SIGMOD 2026 preview. https://par.nsf.gov/biblio/10657054 — *paper (preprint); replay-chain tail latency.*
[^snowflake]: Dageville et al., "The Snowflake Elastic Data Warehouse," SIGMOD 2016. https://event.cwi.nl/lsde/papers/snowflake-sigmod.pdf — *paper; virtual warehouses + S3, local-SSD cache.*
[^snowflakeprod]: Vuppalapati et al., "Building an Elastic Query Engine on Disaggregated Storage," NSDI 2020. https://par.nsf.gov/biblio/10189403 — *paper; production Snowflake at scale.*
[^lakehouse]: Armbrust et al., "Lakehouse: A New Generation of Open Platforms…," CIDR 2021. https://www.databricks.com/sites/default/files/2020/12/cidr_lakehouse.pdf — *paper; Delta Lake on object storage.*
[^bigquery]: "Separation of Storage and Compute in BigQuery," Google Cloud Blog, 2017. https://cloud.google.com/blog/products/bigquery/separation-of-storage-and-compute-in-bigquery — *vendor; Dremel/Colossus/Jupiter.*
[^neonarch]: Neon Docs, "Architecture overview." https://neon.com/docs/introduction/architecture-overview — *docs; compute/storage split, Safekeepers, Pageserver, S3, scale-to-zero.*
[^neonpage]: Linnakangas, "Deep dive into Neon storage engine (get_page@lsn)," Neon Blog, 2023. https://neon.com/blog/get-page-at-lsn — *blog (primary); LSM-style immutable layers, GetPage@LSN.*
[^neonpitr]: "A Deep Dive Into Neon's Instant PITR," Neon Blog, 2025. https://neon.com/blog/pitr-deep-dive — *blog (primary); WAL buffer → reconstruction → instant PITR.*
[^neonbranch]: Neon Docs, "Branching." https://neon.com/docs/introduction/branching — *docs; copy-on-write branch semantics.*
[^s3express]: "Up to 85% price reductions for Amazon S3 Express One Zone," AWS Blog, 2025-04. https://aws.amazon.com/blogs/aws/up-to-85-price-reductions-for-amazon-s3-express-one-zone/ — *vendor; S3 Express pricing (verified-as-of 2026-06-13).*
[^turso]: "Turso Cloud Goes Diskless," Turso Blog, 2025-04. https://turso.tech/blog/turso-cloud-goes-diskless — *blog (primary); SQLite-on-S3, S3 Express latency benchmarks.*
[^warpstream]: "How WarpStream enables cost-effective low-latency streaming with Amazon S3 Express One Zone," AWS Storage Blog, 2024-06. https://aws.amazon.com/blogs/storage/how-warpstream-enables-cost-effective-low-latency-streaming-with-amazon-s3-express-one-zone/ — *vendor; stateless Kafka-on-S3.*
[^risingwave]: "How We Built RisingWave on S3," RisingWave Blog, 2025-05. https://risingwave.com/blog/how-we-built-risingwave-on-s3-a-deep-dive-into-s3-as-primary-storage-architecture/ — *blog (primary); three-tier S3/EBS/memory.*
[^clickhouse]: "Unifying OLTP and OLAP: HTAP databases," ClickHouse Engineering, 2026. https://clickhouse.com/resources/engineering/unifying-oltp-and-olap — *vendor analysis (disconfirming); S3 tail latency, random-I/O incompatibility.*
[^lakebase]: "Databricks Lakebase is now Generally Available," Databricks Blog, 2026-02. https://www.databricks.com/blog/databricks-lakebase-generally-available — *vendor; Neon-based serverless Postgres, branching GA.*
[^transactional]: "Disaggregated OLTP Systems," transactional.blog, 2024. https://transactional.blog/notes-on/disaggregated-oltp — *independent analysis; Aurora-vs-Socrates WAL partitioning.*
[^egress]: "Cloud Egress Costs Explained," rack2cloud.com, 2026. https://www.rack2cloud.com/cloud-egress-costs-architecture/ — *practitioner; cross-AZ $0.01/GB egress.*
[^greptime]: "Object Storage Economics," GreptimeDB, 2026-05. https://greptime.com/tech-content/2026-05-16-object-storage-economics-time-series — *vendor analysis; object vs block storage price differential.*
