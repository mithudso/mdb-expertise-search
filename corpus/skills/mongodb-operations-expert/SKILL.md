---
description: "MongoDB/Atlas operations hub \u2014 reliability & data movement. 20 references. TRIGGER: backup/restore & PITR; disaster recovery & RTO/RPO; Ops Manager/Cloud Manager; upgrade paths & FCV; 7.0-vs-8.0 changes (not procedure); migration patterns (mongosync, Relational Migrator, CDC, expand-contract/backfill/rollback); change streams/TTL/lifecycle; security architecture & network-hardening posture; encryption at-rest/in-transit/CSFLE/Queryable Encryption; compliance; Atlas cost optimization; Kafka/Spark connectors; cloud-native disaggregation & HTAP. SKIP: evals -> deep-eval-optimizer; query/index/schema/engine \u2192 mongodb-expert; Atlas platform features/networking config \u2192 mongodb-atlas-expert; live diagnostics/perf \u2192 atlas-diagnostics-expert; KB lookup/repo install \u2192 misc-catch-all."
name: mongodb-operations-expert
category: mongodb
tags:
- mongodb
- operations
- backup
- disaster-recovery
- migration
- security
- encryption
- compliance
- data-movement
whenToUse:
- designing a backup and restore strategy or doing point-in-time recovery
- 'disaster-recovery planning: RTO/RPO modeling, failover, multi-region posture'
- Ops Manager or Cloud Manager control-plane setup and operations
- planning a major-version upgrade path and FCV sequencing
- live migration with mongosync or migrating data between clusters
- migrating a relational database to MongoDB with Relational Migrator
- 'encryption design: at-rest, in-transit, CSFLE, or Queryable Encryption'
- compliance, security architecture, cost optimization, or Kafka/Spark connectors
whenNotToUse:
- "Query, index, schema, aggregation, or engine-internals work \u2014 use mongodb-expert"
- "Atlas platform features or networking config (Search, Vector Search, Charts, App Services, IaC, PrivateLink/VPC/IP access list) \u2014 use mongodb-atlas-expert"
- "Diagnosing a live cluster's performance, metrics, or capacity \u2014 use atlas-diagnostics-expert"
- "Looking up a knowledge-base article \u2014 use misc-catch-all (references/mongodb-kb.md)"
related_skills:
- mongodb-expert
- mongodb-atlas-expert
- atlas-diagnostics-expert
- misc-catch-all
model: claude-opus-5
effort: high
version: 1.1.0
updated: '2026-09-29'
---

# MongoDB Operations Expert

The operations, reliability, and data-movement hub for MongoDB and Atlas. This
skill covers the parts of running MongoDB that sit *around* the data plane:
keeping data safe (backup, restore, point-in-time recovery, disaster recovery),
moving data (migration patterns, mongosync live migration, Relational Migrator,
CDC, Kafka and Spark connectors), governing data (lifecycle, archival, security
architecture, encryption, compliance), and controlling spend (cost
optimization). It spans both Atlas-managed and self-managed deployments, plus
the Ops Manager / Cloud Manager control planes that automate them.

Use it when the task is about reliability or data movement rather than writing
queries, designing Atlas platform features, or diagnosing a live cluster. For a
single deep sub-area, match the routing table below and read the corresponding
reference file before answering.

## How to use this skill

This skill consolidates 17 MongoDB operations sub-skills as on-demand reference
files. Match the task to the routing table below and **Read the listed
`references/…md` file before answering deep questions** — the table alone is not
enough for depth. For exact command, option, version, and endpoint details,
defer to the official MongoDB Manual, Atlas docs, and connector docs as the
source of truth.

## Sub-skill routing table

This hub absorbs 17 former standalone skills plus 3 researched architecture references (20 total) as on-demand reference files. When a
task matches a row, **Read the listed `references/` file** before answering — do
not rely on this table alone for depth.

| Sub-topic | When to load | Reference file |
| --- | --- | --- |
| `mongodb-backup-restore` | MongoDB backup and restore — Atlas Cloud Backup snapshot policies, Continuous Cloud Backup PIT windows and oplog sizing, Queryable Backups, Ops Manager / self-managed backup, `mongodump`/`mongorestore`. | `references/mongodb-backup-restore.md` |
| `mongodb-disaster-recovery` | MongoDB Atlas and self-managed disaster recovery — RTO/RPO modeling and calculation, failover and multi-region/multi-cloud topology, recovery runbooks. | `references/mongodb-disaster-recovery.md` |
| `mongodb-ops-manager` | MongoDB Ops Manager (self-hosted) and Cloud Manager (hosted SaaS) control plane — automation, monitoring, and backup of self-managed deployments. | `references/mongodb-ops-manager.md` |
| `mongodb-upgrade-paths` | MongoDB self-managed upgrade paths — sequential 4.4→5.0→6.0→7.0→8.0 paths, FCV management, binary upgrade ordering, and rollback. | `references/mongodb-upgrade-paths.md` |
| `mongodb-7.0-vs-8.0-differences` | What actually changed between MongoDB 7.0 and 8.0 — ExpressPlan/TCMalloc, client-level bulkWrite, Queryable Encryption range queries, replication/sharding behavior changes, deprecations, default-value changes, and vendor-vs-independent performance benchmarks. | `references/mongodb-7.0-vs-8.0-differences.md` |
| `mongodb-migration-patterns` | Strategy and tooling reference for migrating data into, out of, and between MongoDB clusters. | `references/mongodb-migration-patterns.md` |
| `mongosync` | mongosync / Atlas Live Migration — decision framework (mongosync vs Atlas Live Migration vs C2C), setup, filtering, reverse sync, state machine, and cutover. Overlaps substantially with `mongodb-mongosync`; read either first, both cross-reference the other. | `references/mongosync.md` |
| `mongodb-mongosync` | mongosync / Atlas Live Migration — the same topic from an operational-reference angle (config, monitoring, sharded topologies). Overlaps substantially with `mongosync`; read either first, both cross-reference the other. | `references/mongodb-mongosync.md` |
| `mongodb-relational-migrator` | MongoDB Relational Migrator (free GUI tool) — migrating RDBMS schemas and data to MongoDB, mapping rules, and sync jobs. | `references/mongodb-relational-migrator.md` |
| `mongodb-cdc-architecture` | Change-data-capture pipeline architecture for MongoDB — patterns, delivery semantics, and downstream integration. | `references/mongodb-cdc-architecture.md` |
| `mongodb-data-lifecycle` | MongoDB data lifecycle — Change Streams (resume tokens, pre/post images, split events, CDC), TTL Indexes (expireAfterSeconds, partial TTL, monitor thread), and Time Series Collections (buckets, metaField, granularity). | `references/mongodb-data-lifecycle.md` |
| `database-migrations` | Safe production schema/data migrations — expand-contract, backfill, online schema change (gh-ost/pt-osc/pgroll), rollback, migration-tool selection (Flyway/Liquibase/Prisma/Atlas/goose), MongoDB document schema versioning. | `references/database-migrations.md` |
| `mongodb-security-architecture` | MongoDB security architecture — authentication, authorization/RBAC, network hardening, auditing, and defense-in-depth posture. | `references/mongodb-security-architecture.md` |
| `mongodb-encryption` | MongoDB in-use encryption — CSFLE and Queryable Encryption (QE), plus encryption at-rest and in-transit. | `references/mongodb-encryption.md` |
| `mongodb-compliance` | MongoDB Atlas compliance certifications, regulatory frameworks, and audit/posture mapping. | `references/mongodb-compliance.md` |
| `mongodb-cost-optimization` | MongoDB Atlas cost optimization — cluster right-sizing, storage tier selection, archival, and spend reduction. | `references/mongodb-cost-optimization.md` |
| `mongodb-kafka-connector` | MongoDB Connector for Apache Kafka — both the source connector (CDC into Kafka) and the sink connector (Kafka into MongoDB). | `references/mongodb-kafka-connector.md` |
| `mongodb-spark-connector` | MongoDB Spark Connector V10 and Databricks integration — batch/streaming reads from change streams, batch/streaming writes with upsert/insert/replace. | `references/mongodb-spark-connector.md` |
| `cloud-native-database-disaggregation` | Vendor-neutral **compute–storage disaggregation** in cloud databases — Aurora / Hyperscale-Socrates / PolarDB / Taurus / Neon, "log is the database", object-storage-backed OLTP, serverless / scale-to-zero, copy-on-write branching, disaggregation performance & cost trade-offs, OLAP-vs-OLTP contrast. | `references/cloud-native-database-disaggregation.md` |
| `htap-disaggregated-storage` | **HTAP** (Hybrid Transactional/Analytical Processing) and how shared/disaggregated storage serves OLTP + OLAP from one copy — single-engine dual-format (HANA, Oracle In-Memory, SQL Server, SingleStore, HeatWave), separate row/column replicas (TiDB TiKV+TiFlash), zero-ETL (Aurora→Redshift), Snowflake Unistore, PolarDB-IMCI, AlloyDB columnar; isolation/freshness trade-offs. | `references/htap-disaggregated-storage.md` |

## Cross-hub boundaries

This hub owns operations, reliability, and data movement. Hand off when the task
falls into a sibling hub:

- **Data-plane query/index/schema/aggregation/engine work** → `mongodb-expert`.
- **Atlas platform features and configuration, including networking config**
  (Search, Vector Search, Charts, App Services, Triggers/Functions, Stream
  Processing, IaC / Terraform / AKO, PrivateLink / VPC / IP access list) →
  `mongodb-atlas-expert`.
- **Live cluster diagnostics, performance, monitoring, capacity** →
  `atlas-diagnostics-expert`.
- **Knowledge-base article lookup** → `misc-catch-all` (references/mongodb-kb.md).

Some topics legitimately touch two hubs (e.g., Atlas Cloud Backup is both an
operations concern here and an Atlas platform feature). Lead with the hub that
matches the user's intent — reliability/data-movement intent stays here.

<!-- cross-hub-map -->
## Cross-hub map — where every MongoDB topic lives

All MongoDB knowledge is split across **four hubs**, plus `misc-catch-all` for KB-article
lookups (`misc-catch-all/references/mongodb-kb.md`). If a task's
deep material is **not** in this hub's Sub-skill routing table, it is a reference file under a
sibling hub — **activate that hub or Read its `references/<name>.md` directly**. (`database-migrations`
is a sibling skill covering the same schema-migration patterns generically across databases;
this hub's own `references/database-migrations.md` row above is the MongoDB-relevant folded
copy — it is not a separate hub in this map.)

| Hub | Owns | Example reference files |
| --- | --- | --- |
| `mongodb-expert` | Core data plane + **engine internals**: CRUD/MQL, aggregation, indexes, query performance, schema design, transactions, change streams, time-series, geospatial, views, BSON, error codes, connection strings, driver internals, **WiredTiger cache/eviction/checkpoint internals**, mongosh, database tools, multi-tenancy, sharding, replication, Compass | `mongodb-expert/references/mongodb-wiredtiger-internals.md`, `mongodb-indexes-deep.md`, `mongodb-sharding.md`, `mongodb-replication.md` |
| `mongodb-atlas-expert` | Atlas **cloud platform**: control plane, Atlas Search, Vector Search, Stream Processing, Charts, Data Federation, App Services, Triggers, Online Archive, Flex, networking, IAM/RBAC, Terraform, AKO | `mongodb-atlas-expert/references/mongodb-atlas-search.md`, `mongodb-atlas-vector-search.md` |
| `atlas-diagnostics-expert` | Live **diagnostics & performance**: FTDC, performance-troubleshooting symptom triage, benchmarking, monitoring/observability, capacity planning | `atlas-diagnostics-expert/references/mongodb-performance-troubleshooting.md` |
| `mongodb-operations-expert` | **Ops & data movement**: backup/restore, DR, Ops Manager, upgrades, migration, mongosync, relational migrator, CDC, data lifecycle, security architecture, encryption, compliance, cost, Kafka/Spark connectors | `references/mongosync.md`, `mongodb-backup-restore.md` |

**High-overlap routing notes:**
- Performance **symptom triage** (high CPU, cache pressure, slow queries, latency spikes) starts at `atlas-diagnostics-expert`, but **storage-engine root-cause internals** (WiredTiger cache fill / dirty trigger / eviction threads / reconciliation / checkpoints) are owned by `mongodb-expert` — cross-load `mongodb-expert/references/mongodb-wiredtiger-internals.md` (and `mongodb-wiredtiger.md`) for depth.
- Migration symptoms vs migration **execution**: live-cluster diagnosis → `atlas-diagnostics-expert`; the migration/mongosync runbook → `mongodb-operations-expert`.
- Atlas Search/Vector **query syntax & index design** → `mongodb-atlas-expert`; the slowness *triage* of a running search → `atlas-diagnostics-expert`.
