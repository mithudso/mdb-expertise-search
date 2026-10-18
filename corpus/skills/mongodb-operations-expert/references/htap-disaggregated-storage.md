<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Created by `/dr` via `concept-family-explorer` (2026-06-13).
> Vendor-neutral, **public** architecture scaffolding. Sibling to `references/cloud-native-database-disaggregation.md` (the disaggregation
> substrate) and cross-links `da-data-engineering-platform` ▸ `da-28-realtime-olap-databases` (OLAP engines). Load from the owning hub.

---
name: htap-disaggregated-storage
title: "HTAP on Disaggregated Storage"
description: >
  Vendor-neutral reference for HTAP (Hybrid Transactional/Analytical Processing) and how compute–storage disaggregation enables
  serving OLTP and OLAP from one shared store without ETL.
  TRIGGER: user asks what HTAP is or why it's hard; row-store vs column-store on the same data; single-engine/dual-format HTAP
  (SAP HANA, Oracle In-Memory, SQL Server columnstore, SingleStore, MySQL HeatWave); separate row/column replicas (TiDB TiKV+TiFlash,
  Raft Learner); "one copy of data, many engines"; zero-ETL (Aurora→Redshift); Snowflake Unistore/Hybrid Tables; PolarDB-IMCI;
  AlloyDB columnar engine; lakehouse engine interoperability; HTAP isolation/freshness tradeoffs; whether HTAP or a dedicated warehouse wins.
  SKIP: the disaggregation substrate itself — log-is-the-database, page servers, object-storage OLTP (use references/cloud-native-database-disaggregation.md);
  choosing/tuning a standalone OLAP engine like ClickHouse/Druid/Pinot (use da-data-engineering-platform, references/da-28-realtime-olap-databases);
  MongoDB query/index/schema/engine internals (use mongodb-expert); live cluster diagnostics (use atlas-diagnostics-expert).
category: mongodb
version: "1.0.0"
updated: "2026-06-13"
whenToUse:
  - "explaining what HTAP is and the row-vs-column physical-design conflict that makes it hard"
  - "comparing single-engine/dual-format HTAP (HANA, Oracle In-Memory, SQL Server, SingleStore, HeatWave)"
  - "explaining TiDB's separate row/column replica model (TiKV + TiFlash via Raft Learner)"
  - "explaining how disaggregated/shared storage lets many compute engines read one copy without ETL"
  - "evaluating zero-ETL (Aurora→Redshift), Snowflake Unistore, PolarDB-IMCI, or AlloyDB columnar engine"
  - "setting expectations on HTAP isolation and data-freshness tradeoffs"
  - "deciding when HTAP/zero-ETL wins vs when a dedicated OLAP warehouse still wins"
whenNotToUse:
  - "The disaggregation substrate (log/page servers, object-storage OLTP) — use cloud-native-database-disaggregation"
  - "Standalone OLAP engine selection/tuning (ClickHouse/Druid/Pinot/StarRocks) — use da-data-engineering-platform (da-28)"
  - "MongoDB query/index/schema/engine work — use mongodb-expert"
keywords:
  - HTAP
  - hybrid transactional analytical processing
  - translytical
  - OLTP vs OLAP
  - dual-format
  - columnstore index
  - TiDB TiFlash
  - Raft Learner
  - zero-ETL
  - Snowflake Unistore
  - hybrid tables
  - PolarDB-IMCI
  - AlloyDB columnar engine
  - one copy many engines
  - workload isolation
  - data freshness
  - SAP HANA
  - MySQL HeatWave
tags:
  - database-architecture
  - htap
  - oltp-olap
  - disaggregation
  - zero-etl
  - analytics
related_skills:
  - mongodb-operations-expert
  - da-data-engineering-platform
  - mongodb-atlas-expert
---

# HTAP on Disaggregated Storage

> **Scope:** what HTAP is, the two architectural families that implement it, and — the reason this lives next to the
> disaggregation reference — how a shared/disaggregated storage layer turns "one durable copy of data" into "many compute
> engines (OLTP + OLAP + search)" without ETL. Vendor-neutral. **`verified-as-of: 2026-06-13`** for all product/vendor-landscape
> claims (footnotes); the architectural principles are stable, the products and benchmark numbers move.
> For the storage substrate itself (log-is-the-database, page servers, object-storage OLTP) read the sibling
> `references/cloud-native-database-disaggregation.md`; for standalone OLAP engines read `da-28-realtime-olap-databases`.

## Contents
- [Overview](#overview)
- [Why HTAP is hard](#why-htap-is-hard)
- [Family 1 — single-engine / dual-format](#family-1--single-engine--dual-format)
- [Family 2 — separate row/column replicas](#family-2--separate-rowcolumn-replicas)
- [How disaggregation enables HTAP](#how-disaggregation-enables-htap)
- [Zero-ETL and "one copy, many engines"](#zero-etl-and-one-copy-many-engines)
- [Tradeoffs](#tradeoffs)
- [When HTAP/zero-ETL wins vs when a dedicated system wins](#when-htapzero-etl-wins-vs-when-a-dedicated-system-wins)
- [Anti-patterns](#anti-patterns)
- [References](#references)

## Overview

**HTAP** (Hybrid Transactional/Analytical Processing) — Gartner's 2014 term[^gartner] — is the goal of running analytics on
live transactional data in **one system, without ETL** to a separate warehouse. ("Translytical" is a synonym.) The payoff is
real-time analytics and one less pipeline to operate; the difficulty is that OLTP and OLAP want opposite physical layouts.
Two architectural families answer it, and a third path — **composition over convergence** — argues you often shouldn't try.
Disaggregation matters here because once storage is detached and durable on its own, the *same* write stream can feed both a
transactional engine and a columnar analytical engine, which is the cleanest way to get HTAP-like behavior at cloud scale.

## Why HTAP is hard

- **Opposite physical designs.** OLTP is **row-oriented** — point reads/writes, low latency, high concurrency, small random
  I/O. OLAP is **column-oriented** — sequential scans, aggregations over millions of rows, heavy compression, vectorized
  execution. One physical layout penalizes the other.[^survey]
- **Resource interference.** Analytical scans are bandwidth-hungry and thrash the last-level cache; co-locating them on the
  same socket measured **up to 42% OLTP throughput loss**, and if columnar-propagation throughput falls behind OLTP's write
  rate, OLAP execution time grows *exponentially*.[^sirin]
- **Freshness vs isolation is a fundamental tension.** You cannot simultaneously maximize analytical throughput and the
  freshness of the analytical copy; every design picks a point on that curve.[^survey]

## Family 1 — single-engine / dual-format

One instance keeps both a row and a column representation, and the optimizer routes each query:

- **SAP HANA** — column-store-first in-memory DB with a "Unified Table": an L1-delta (write-optimized row buffer) → L2-delta →
  compressed main column store; OLTP hits the delta, OLAP the main, with asynchronous delta-merge.[^hana]
- **Oracle Database In-Memory** — true **dual-format**: the buffer cache keeps row blocks (OLTP) while an optional In-Memory
  column store holds a second columnar copy (OLAP); the optimizer routes per query. The column copy need not cover the whole
  dataset, so it doesn't simply double memory.[^oracle]
- **SQL Server columnstore indexes** — a nonclustered **columnstore index** over a rowstore table; OLTP uses the rowstore, OLAP
  the columnstore; a deltastore buffers fresh DML. Kept in sync automatically as an index (~10% storage overhead).[^sqlserver]
- **SingleStore Universal Storage** — converged toward a columnstore-native format with LSM layout, hash secondary indexes,
  and row-level locking so a single store serves both patterns.[^singlestore]
- **MySQL HeatWave** — an attached in-memory **MPP columnar accelerator**; InnoDB runs row-format OLTP, changes propagate to
  HeatWave automatically, and the optimizer offloads qualifying analytical queries.[^heatwave]

Single-engine designs get tighter freshness (same-engine MVCC) but weaker hardware isolation (shared CPU/memory).

## Family 2 — separate row/column replicas

Keep the two formats on **separate nodes**, linked by replication — strong isolation, some lag. The canonical design is
**TiDB**:[^tidb][^tiflashdocs]

- **TiKV** — distributed transactional row store; data in ~96 MB Regions, each Raft-replicated; RocksDB on disk; serves all OLTP.
- **TiFlash** — columnar store on **Raft Learner** nodes that receive the Raft log but **don't vote** (zero overhead on the OLTP
  write path), transforming rows to columns as they apply.
- **Consistency** — TiFlash serves **Snapshot Isolation**: before a read it issues a progress-validation RPC to the TiKV leader
  to confirm it has applied logs up to the read timestamp, so analytics see strongly-consistent data (at a small per-query cost).
- **Routing & isolation** — the optimizer sends point queries to TiKV, scans/aggregations to TiFlash (and can split a plan
  across both); physical node separation means analytics can't starve transactions, and learner lag never blocks commits.

## How disaggregation enables HTAP

The link to the sibling reference: once storage is **disaggregated** — durable and independent of compute — a single storage
layer (or shared log) can serve **multiple compute engines** at once. A row-oriented OLTP engine writes; a column-oriented OLAP
engine reads the same underlying data, or a continuously-maintained columnar projection derived from the *same write path* (the
REDO log / WAL / async copy) rather than from a bespoke ETL job.[^clickhouse] This turns the storage/replication layer — not an
ETL scheduler — into the thing that controls freshness, and lets analytical compute scale, pause, or be added independently of
OLTP (e.g., a new read-only analytical node bootstraps by pulling a checkpoint straight from shared storage).[^polardb]

**Vendor instantiations of the shared-storage path:**
- **Snowflake Unistore / Hybrid Tables** — a row store is the primary for low-latency point reads, row locks, and PK
  enforcement; data is asynchronously copied into Snowflake's columnar object-storage micro-partitions; the optimizer routes by
  access pattern — both within one platform/governance model.[^unistore]
- **Alibaba PolarDB-IMCI** — an In-Memory Column Index on dedicated read-only nodes over PolarDB's **shared** PolarFS storage;
  the RW node writes rows, REDO propagates to RO nodes that maintain columnar projections — full CPU/memory isolation, no
  separate copy infra, reported up to **149× TPC-H** speedup vs row-only.[^polardb]
- **Google AlloyDB columnar engine** — a vectorized columnar accelerator embedded *inside* a disaggregated Postgres-compatible
  instance (compute separate from Google's storage engine); auto-columnarizes hot columns, reports up to ~**100×** on analytical
  queries, no ETL/second system.[^alloydb]
- **Databricks / lakehouse** — open table formats (Delta, Iceberg, Hudi) on object storage with ACID metadata give **engine
  interoperability**: Spark, Trino, Flink, ClickHouse, DuckDB read the *same* files concurrently, no copy.[^lakehouse][^iceberg]

## Zero-ETL and "one copy, many engines"

**Zero-ETL** is the managed, vendor-integrated expression of the same principle: the platform replicates transactional data to
the analytical engine automatically (seconds of latency) instead of you building CDC/ETL. **AWS Aurora→Redshift zero-ETL**
(GA for Aurora PostgreSQL Oct 2024; also Aurora→SageMaker Lakehouse, RDS MySQL→Redshift) keeps Aurora row-oriented and Redshift
columnar but manages schema replication and format conversion between them[^awszeroetl] — the "architecturally purest composed
model," in one independent analysis.[^clickhouse]

## Tradeoffs

- **Isolation isn't free.** "Marrying OLAP to OLTP breaks performance isolation" — analytical queries run hundreds to thousands
  of times longer and contend for caches, memory bandwidth, and storage I/O queues. Dedicated RO nodes (PolarDB), a separate
  Redshift cluster (zero-ETL), or separate TiFlash nodes (TiDB) fix it, but cost capacity planning.[^survey][^sirin]
- **Freshness lag is real and variable.** Async columnar copies lag the OLTP write. Aurora→Redshift is seconds normally but
  lags under high write volume; DynamoDB zero-ETL has a documented **15-minute** minimum refresh.[^awslimits] Sub-second
  freshness still favors co-located in-memory HTAP (HANA/SingleStore/HeatWave).
- **Dual-format maintenance cost.** Every commit must eventually update both representations — write amplification, storage
  overhead, and background merge/compaction.[^hana][^sqlserver]
- **Zero-ETL ≠ no data work.** It replicates *as-is*: transformations, normalization, semantic layers, dedup, and quality
  checks remain yours; AWS explicitly does **not** support transformations during replication, and source schema changes need
  manual reconfiguration. Vendor lock-in is structural (Aurora→Redshift only works within Aurora).[^awslimits][^zeroetlmyth]

## When HTAP/zero-ETL wins vs when a dedicated system wins

**Wins:** real-time operational analytics on fresh transactional data; eliminating a brittle CDC/ETL pipeline; teams that value
one system + one copy over peak performance; independent, cheap analytical scale-out on shared storage.[^clickhouse][^polardb]

**A dedicated system still wins:** high-concurrency, latency-sensitive reporting at petabyte scale (hundreds of analysts,
sub-second dashboards). HTAP's structural trade-off is "less OLAP than a specialized MPP, less OLTP than a finely-tuned OLTP
system"; at scale, composed best-of-breed engines connected by real-time replication often beat a converged engine — the
"rise and fall" critique of one-system HTAP.[^clickhouse][^infoq]

## Anti-patterns

- **Co-locating analytics on OLTP nodes with no isolation** — scan-heavy queries silently degrade transaction throughput (up to
  ~42%).[^sirin]
- **Assuming zero-ETL means zero data engineering** — modeling, governance, and quality work remain.[^zeroetlmyth]
- **Treating the analytical copy as real-time** — budget for replication lag; don't promise sub-second freshness on an async
  columnar projection.[^awslimits]
- **Forcing one engine to do everything at petabyte scale** — past a point, a dedicated warehouse + CDC beats a converged
  HTAP engine.[^infoq]

## References

[^gartner]: Pezzini et al., "Hybrid Transaction/Analytical Processing Will Foster Opportunities for Dramatic Business Innovation," Gartner, 2014. https://www.gartner.com/en/documents/2657815 — *origin of the HTAP term. tier: primary (gated).*
[^survey]: Zhang et al., "A survey on hybrid transactional and analytical processing," The VLDB Journal 33:1485–1515, 2024. https://link.springer.com/article/10.1007/s00778-024-00858-9 — *HTAP taxonomy; isolation/freshness tension. tier: paper (survey).*
[^sirin]: Sirin, Dwarkadas, Ailamaki, "Workload Interference Analysis for HTAP," CIDR 2021. https://par.nsf.gov/servlets/purl/10294943 — *up-to-42% OLTP loss; exponential OLAP slowdown when propagation lags. tier: paper.*
[^hana]: Sikka et al., "Efficient Transaction Processing in SAP HANA: The End of a Column Store Myth," (SIGMOD 2012). https://15721.courses.cs.cmu.edu/spring2016/papers/p731-sikka.pdf — *Unified Table, L1/L2-delta → main. tier: paper (vendor).*
[^oracle]: Oracle Docs, "Introduction to Oracle Database In-Memory." https://docs.oracle.com/en/database/oracle/oracle-database/26/inmem/intro-to-in-memory-column-store.html — *dual-format buffer cache + IM column store. tier: docs.*
[^sqlserver]: Microsoft Learn, "Columnstore for real-time operational analytics." https://learn.microsoft.com/en-us/sql/relational-databases/indexes/get-started-with-columnstore-for-real-time-operational-analytics — *nonclustered columnstore index + deltastore, ~10% overhead. tier: docs.*
[^singlestore]: Cao et al., "Cloud-Native Transactions and Analytics in SingleStore," SIGMOD 2022. https://dl.acm.org/doi/10.1145/3514221.3526055 — *Universal Storage: columnstore-native with row-level locking + hash indexes. tier: paper (vendor).*
[^heatwave]: Oracle Docs, "Overview of HeatWave Cluster." https://docs.oracle.com/en-us/iaas/mysql-database/doc/overview-heatwave.html — *in-memory MPP accelerator attached to InnoDB; auto change propagation. tier: docs.*
[^tidb]: Huang et al., "TiDB: A Raft-based HTAP Database," PVLDB 13(12), 2020. https://www.vldb.org/pvldb/vol13/p3072-huang.pdf — *TiKV row + TiFlash columnar via Raft Learner; SI consistency. tier: paper.*
[^tiflashdocs]: PingCAP, "TiFlash Overview." https://docs.pingcap.com/tidb/stable/tiflash-overview — *Raft Learner replication, progress-validation, ClickHouse-based coprocessor. tier: docs.*
[^clickhouse]: ClickHouse Engineering, "Unifying OLTP and OLAP: HTAP, Zero-ETL, and Best-of-Breed." https://clickhouse.com/resources/engineering/unifying-oltp-and-olap — *composed-vs-converged analysis; zero-ETL composed-model framing. tier: vendor analysis (incl. disconfirming).*
[^polardb]: Wei et al., "PolarDB-IMCI: A Cloud-Native HTAP Database System at Alibaba," (SIGMOD 2023) arXiv:2305.08468. https://arxiv.org/pdf/2305.08468 — *In-Memory Column Index on RO nodes over shared PolarFS; ~149× TPC-H. tier: paper.*
[^alloydb]: Google Cloud Blog, "AlloyDB for PostgreSQL columnar engine." https://cloud.google.com/blog/products/databases/alloydb-for-postgresql-columnar-engine — *vectorized columnar engine in a disaggregated Postgres; ~100× analytics. tier: vendor blog.*
[^unistore]: Snowflake Docs, "Hybrid Tables." https://docs.snowflake.com/en/user-guide/tables-hybrid-read-query-profiles — *row store primary + async copy to columnar object storage; optimizer routing. tier: docs.*
[^awszeroetl]: AWS, "Aurora zero-ETL integration with Amazon Redshift." https://aws.amazon.com/rds/aurora/zero-etl/ — *near-real-time Aurora→Redshift, no CDC pipeline. tier: vendor.*
[^awslimits]: AWS Docs, "Zero-ETL integrations — considerations and limitations." https://docs.aws.amazon.com/redshift/latest/mgmt/zero-etl.reqs-lims.html — *no transforms during replication; DynamoDB 15-min min; schema-change reconfig. tier: docs (disconfirming).*
[^lakehouse]: Armbrust et al., "Lakehouse: A New Generation of Open Platforms," CIDR 2021. https://vldb.org/cidrdb/papers/2021/cidr2021_paper17.pdf — *"one copy of data, many engines." tier: paper.*
[^iceberg]: Apache Iceberg lakehouse — "engine interoperability." https://iceberglakehouse.com/iceberg/data-lakehouse/ — *any engine reads the same Iceberg tables concurrently. tier: community.*
[^zeroetlmyth]: "Zero ETL: Hype or Hope?" https://sneha-dq.github.io/posts/zero-etl/ — *zero-ETL still needs modeling/governance/lineage; best within one cloud. tier: practitioner (disconfirming).*
[^infoq]: InfoQ, "HTAP: The Rise and Fall of Unified Database Systems?" 2025. https://www.infoq.com/news/2025/06/htap-databases/ — *composition-over-convergence critique at scale. tier: industry analysis (disconfirming).*
