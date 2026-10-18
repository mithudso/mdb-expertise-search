---
description: "MongoDB data-plane & engine hub. TRIGGER: CRUD/MQL query/projection/update; aggregation pipelines & deep stages ($lookup, $graphLookup, $setWindowFields); index design (compound/multikey/partial/wildcard/TTL); query optimization, explain plans, slow queries; schema design (embed vs reference); transactions; change streams/resume tokens; time-series; geospatial/2dsphere; views; BSON types; error codes; connection strings; driver internals (CMAP/SDAM); WiredTiger (cache/eviction/checkpoint/MVCC); mongosh; dump/restore; multi-tenancy; sharding; replication; Compass. SKIP: evals -> deep-eval-optimizer; Atlas platform/config \u2192 mongodb-atlas-expert; live perf/diagnostics \u2192 atlas-diagnostics-expert; backup/DR/migration/security/encryption \u2192 mongodb-operations-expert; ODM/Mongoose \u2192 mongodb-odm-patterns; optimize/fix this pipeline (fix-loop) \u2192 deep-mongodb-mql-query-optimizer; clustered collections \u2192 mongodb-clustered-collections; KB lookup/repo install\
  \ \u2192 misc-catch-all; University/certification \u2192..."
name: mongodb-expert
whenToUse:
- how do I write an aggregation pipeline that groups by date and computes totals?
- what index should I create for this query filter?
- should I embed or reference this relationship in my schema?
- "my explain plan shows COLLSCAN \u2014 how do I fix it?"
- how do I design a schema for a multi-tenant SaaS app in MongoDB?
- how do transactions work in MongoDB across multiple collections?
- how do I set up change streams with resume tokens?
- what are the BSON type comparison rules?
- how does WiredTiger cache eviction work?
- what does error code 11000 mean and how do I handle it?
- how do I use $lookup, $graphLookup, or $setWindowFields?
- how do I pick a shard key and set up zones?
- how does replica set election and oplog work?
- how do I use mongosh to run admin scripts?
- how do I configure connection string options for TLS or auth?
- "why does my MongoDB driver keep timing out \u2014 how do connection pooling (CMAP) and server selection work?"
whenNotToUse:
- "Atlas cloud-platform / control-plane work (orgs, projects, deployments, Admin API, CLI, Terraform, AKO, Atlas Search/Vector Search, networking) \u2014 use mongodb-atlas-expert"
- "Live cluster diagnostics, performance troubleshooting, benchmarking, monitoring, capacity planning \u2014 use atlas-diagnostics-expert"
- "Backup/DR, Ops Manager, migration/mongosync/relational-migrator, upgrades, security/encryption/compliance, Kafka/Spark connectors \u2014 use mongodb-operations-expert"
- "KB / troubleshooting article lookup \u2014 use misc-catch-all"
- "Install / run MongoDB locally from a repo \u2014 use misc-catch-all"
- "Generic (non-MongoDB) schema/data-migration patterns (expand-contract, backfill, zero-downtime) \u2014 use database-migrations"
- "MongoDB as a data source in analytics pipelines, lakehouse, or warehouse loading where data engineering is the primary concern \u2014 use da-data-engineering-platform"
- "Okta + MongoDB auth integration (OIDC, LDAP, workforce IdP federated to Atlas or mongod) \u2014 use security-review (references/okta-expert.md)"
- "Security architecture review, GDPR/CCPA compliance, audit posture \u2014 use security-review (references/security-compliance-auditor.md)"
- "GridFS large-file storage spec (chunk/bucket model, 16 MB limit, fs.files/fs.chunks) \u2014 use mongodb-gridfs"
- "ODM / application-data-modeling layer (Mongoose, Spring Data MongoDB, Beanie, ODMantic, Prisma MongoDB connector) \u2014 use mongodb-odm-patterns"
- "MongoDB University courses, learning paths, or the certification program \u2014 use technical-instruction (references/mongodb-university-certification.md)"
- "Case-insensitive/accent-insensitive/locale-aware string comparison, sort, or collation-strength index design \u2014 use mongodb-collation"
- "Clustered collections (clusteredIndex on _id, single-file storage, TTL on _id, IoT/log workloads keyed on _id) \u2014 use mongodb-clustered-collections"
- "Generate a query from natural language against a live connected database (MCP) \u2014 use mongodb:mongodb-natural-language-querying"
- "One-shot \"optimize this query / recommend an index\" against a live cluster via MCP \u2014 use mongodb:mongodb-query-optimizer"
related_skills:
- mongodb-atlas-expert
- atlas-diagnostics-expert
- mongodb-operations-expert
- misc-catch-all
- da-data-engineering-platform
- security-review
origin: local
category: mongodb
version: 1.7.0
updated: '2026-09-29'
metadata:
  changelog:
  - "2026-07-20 sko v1.5.4->v1.6.0 \u2014 Pass H pos 10/10->10/10, neg FP 2/10->0/10; 13 Medium fixed (desc SKIP edges ODM/dmqo/clustered, category added, routing rows disambiguated, context extracted to references/, no-match fallback, peer seed atlas-diagnostics-expert); residual: 7-vs-8 perf-spoke routing edge (BLIND-AUDIT-DISSENT)"
model: claude-opus-5
effort: high
---

# MongoDB Expert

This local skill is generated from `docs/mongodb-expert-context.md` in an internal repository.

This skill consolidates 27 MongoDB data-plane/engine sub-skills as on-demand reference files under `references/`. It is the **primary, first-choice skill** for core MongoDB questions — not a fallback. Match the task to the **Sub-skill routing table** below and **Read the listed `references/…md` file before answering deep questions** — the table alone is not enough for depth. Route to a sibling hub (`mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`, `misc-catch-all`) only when the question falls into one of those domains (see frontmatter `SKIP`).

## When to use this skill

Use this skill when the user needs help with core MongoDB data-plane or database-engine topics. Start from the bundled context below for fundamentals, load the relevant `references/` file for depth, and defer to the cited official documentation for exact APIs, commands, and edge-case behavior.

## Sub-skill routing table

This hub absorbs 27 former standalone skills as on-demand reference files. When a task matches a row, **Read the listed `references/` file** before answering — do not rely on this table alone for depth. For domains not listed here (Atlas cloud platform, live diagnostics, ops/backup/migration/security, KB lookup), route to the sibling hub named in the frontmatter `SKIP` line.

| Sub-topic | When to load | Reference file |
| --- | --- | --- |
| `mongodb-developer` | How to USE a driver — idiomatic API usage in any official driver (Node.js, Python, Java, Go, C#, Rust, …): CRUD calls, transactions API, bulk ops, cursors (how drivers WORK inside → `mongodb-driver-internals`) | `references/mongodb-developer.md` |
| `mongodb-aggregation-pipeline` | Aggregation pipeline fundamentals — stage order, operators, materialization | `references/mongodb-aggregation-pipeline.md` |
| `mongodb-aggregation-stages-deep` | Deep aggregation stages — `$lookup`, `$graphLookup`, `$facet`, `$bucket`/`$bucketAuto`, `$merge`/`$out`, `$setWindowFields`, `$densify`/`$fill`, `$unionWith` | `references/mongodb-aggregation-stages-deep.md` |
| `mongodb-indexes-deep` | Every index type — single-field, compound, multikey, partial, wildcard, hidden, TTL, hashed | `references/mongodb-indexes-deep.md` |
| `mongodb-query-performance` | Query optimization, explain plans, ESR rule, slow-query diagnosis, index hints | `references/mongodb-query-performance.md` |
| `mongodb-clustered-collections` | Clustered collections — documents stored in `_id` order in one WiredTiger file, no separate `_id` index | `references/mongodb-clustered-collections.md` |
| `mongodb-collation` | Locale-aware string comparison/ordering, case-insensitive queries/indexes | `references/mongodb-collation/mongodb-collation.md` |
| `mongodb-gridfs` | Storing files >16MB (files+chunks collections, default 255KiB chunks) | `references/mongodb-gridfs.md` |
| `mongodb-odm-patterns` | ODM layer above drivers — Mongoose, Spring Data MongoDB, Beanie/ODMantic, Prisma connector | `references/mongodb-odm-patterns.md` |
| `mongodb-80-performance-changes` | MongoDB 8.0 vs 7.0 performance changes & regressions — express path, SBE/classic engine default flip (7.0.17+ classic vs 8.0 SBE), TCMalloc per-CPU, majority-ack change, official benchmark claims + caveats, known SERVER regression tickets, 7→8 read-regression diagnostic checklist | `references/mongodb-80-performance-changes.md` |
| `mongodb-schema-design` | Embedding vs referencing trade-offs, 12 canonical design patterns, tree structures, validation | `references/mongodb-schema-design.md` |
| `mongodb-transactions` | Multi-document transactions — replica-set and sharded, callback API, retry, read/write concerns | `references/mongodb-transactions.md` |
| `mongodb-change-streams` | Change streams — oplog architecture, resume tokens, pre/post images, split events | `references/mongodb-change-streams.md` |
| `mongodb-time-series` | Time-series collections — `timeField`/`metaField`, granularity, bucketing, TTL, downsampling | `references/mongodb-time-series.md` |
| `mongodb-geospatial` | Geospatial queries, indexes, and data model — 2dsphere, GeoJSON, near/within, polygons | `references/mongodb-geospatial.md` |
| `mongodb-views-materialized-views` | Standard read-only views and on-demand `$merge`-backed materialized views | `references/mongodb-views-materialized-views.md` |
| `mongodb-bson-types` | BSON type system — type table with codes/aliases, comparison order, edge cases | `references/mongodb-bson-types.md` |
| `mongodb-error-codes` | Numeric server error codes and correct driver retry behavior | `references/mongodb-error-codes.md` |
| `mongodb-connection-string` | Connection-string URI formats and options — SRV, TLS, authSource, appName | `references/mongodb-connection-string.md` |
| `mongodb-driver-internals` | How drivers WORK underneath — CMAP pool spec, SDAM topology/server selection, retryable-writes protocol, OCSP; Java driver 5.x version timeline & 8.0 compatibility | `references/mongodb-driver-internals.md` |
| `mongodb-drivers-k8s` | Driver behavior under the MongoDB Kubernetes operator — connection management, transactions, change streams, retry amid pod churn/failover | `references/mongodb-drivers-k8s.md` |
| `mongodb-wiredtiger` | Operator-facing WiredTiger tuning — cache-sizing knobs, eviction/checkpoint tuning parameters, compression options | `references/mongodb-wiredtiger.md` |
| `mongodb-wiredtiger-internals` | WiredTiger mechanism internals — MVCC, snapshot reads, reconciliation, eviction algorithm, checkpoint lifecycle (read for root-cause depth) | `references/mongodb-wiredtiger-internals.md` |
| `mongodb-mongosh` | mongosh shell — methods, scripts, snippets, `db.*` admin commands | `references/mongodb-mongosh.md` |
| `mongodb-database-tools` | Database tools — mongodump, mongorestore, mongoimport, mongoexport, archive/BSON streaming | `references/mongodb-database-tools.md` |
| `mongodb-multi-tenancy` | Multi-tenancy data layout — tenant-per-DB, tenant-per-collection, shared collection | `references/mongodb-multi-tenancy.md` |
| `mongodb-sharding` | Sharding architecture, shard-key selection (ranged, hashed, compound), balancer, zones, resharding | `references/mongodb-sharding.md` |
| `mongodb-replication` | Replica-set architecture — primaries/secondaries/arbiters/hidden/delayed, elections, oplog, failover | `references/mongodb-replication.md` |
| `mongodb-compass` | Compass GUI — query builder, schema analysis, performance tab | `references/mongodb-compass.md` |
| `deep-mongodb-mql-query-optimizer` | Multi-pass find/aggregation query review-and-fix optimizer that applies every Medium+ rewrite in place and verifies via explain (the MongoDB member of the deep-optimizer family) | `references/deep-mongodb-mql-query-optimizer.md` |
| `mongodb-docset-lookup` | Offline MongoDB Manual lookup via the local Dash docset — exact page/command lookup without a network call | `references/mongodb-docset-lookup.md` |

## Cross-hub routing (domains this hub does NOT own)

The **Sub-skill routing table** above is the authoritative map of the reference files this hub owns (27 routed sub-topics plus `mongodb-mql-quick-reference.md` and `mongodb-expert-context.md`) — route data-plane/engine depth through `references/<name>.md`. Most former standalone spokes exist only as these reference files; a few are hot-tiered and also installed top-level (`deep-mongodb-mql-query-optimizer`, `mongodb-docset-lookup`) — for those, prefer the live top-level skill when the task needs its full workflow (e.g. the dmqo fix-loop), and the reference file for background depth.

For domains outside this hub, route to the **sibling hub** that owns them. Each sibling hub has its own internal routing table for its sub-areas — do not name individual sub-skills here:

| Domain area | Route to sibling hub |
|-------------|----------------------|
| Atlas cloud platform / control plane — orgs, projects, deployments, Admin API, Atlas CLI, Terraform, Kubernetes Operator (AKO), tiers, IAM/RBAC, federated auth, service accounts, Atlas Search / $search, Vector Search / $vectorSearch, Search Nodes, Stream Processing, Charts, Data Federation, Online Archive, App Services, Triggers/Functions, Device SDK / Realm sync, BI Connector, analytics nodes, global clusters, Flex/Serverless, multicloud + AWS/Azure/GCP networking | `mongodb-atlas-expert` |
| Live cluster diagnostics, performance troubleshooting, benchmarking, monitoring/observability, capacity planning | `atlas-diagnostics-expert` |
| Backup/restore, disaster recovery, Ops Manager, migration (mongosync, Relational Migrator, Live Migration, cutover), upgrade paths, security architecture, encryption (CSFLE/Queryable Encryption), compliance, cost optimization, Kafka/Spark connectors, CDC architecture | `mongodb-operations-expert` |
| KB / troubleshooting article lookup; install/run MongoDB locally from a repo | `misc-catch-all` |
| Generic schema/data-migration patterns (expand-contract, backfill, zero-downtime) | `database-migrations` |
| GridFS large-file storage spec (chunk/bucket model, 16 MB limit, fs.files/fs.chunks) | `mongodb-gridfs` |
| ODM / application-data-modeling layer — Mongoose, Spring Data MongoDB, Beanie, ODMantic, Prisma MongoDB connector, ODM-vs-raw-driver decision | `mongodb-odm-patterns` |
| Clustered collections — `clusteredIndex` on `_id`, single-file storage, TTL on `_id`, IoT/log workloads keyed on `_id` | `mongodb-clustered-collections` |
| Case-/accent-insensitive or locale-aware comparison, sort, collation-strength index design | `mongodb-collation` |
| MongoDB as an analytics data source — lakehouse/warehouse loading, data-engineering pipelines | `da-data-engineering-platform` |
| Security architecture review, GDPR/CCPA compliance posture, Okta↔MongoDB auth integration | `security-review` |
| MongoDB University courses, learning paths, certification program | `technical-instruction` |
| Natural-language query generation or one-shot "optimize this query / recommend an index" against a live connected cluster (MCP) | `mongodb:mongodb-natural-language-querying` / `mongodb:mongodb-query-optimizer` |

When a question crosses categories, pick the deepest reference that covers the primary concern, load it, then cross-link to the relevant sibling hub for the secondary concern.

## Skill guidance

- Treat `docs/mongodb-expert-context.md` as the source document for this skill.
- Prefer the workflows, checklists, and constraints captured in the bundled context before improvising.
- If the request is outside this topic, choose a more appropriate skill instead of forcing this one.
- For deep data-plane/engine questions, **Read the matching `references/<name>.md` file** from the Sub-skill routing table rather than improvising from this overview. For out-of-domain questions, route to the sibling hub named in the cross-hub routing table above.
- If no routing-table row matches but the question is still core data-plane/engine (e.g. capped collections, read/write concerns, causal consistency, `$jsonSchema` validation, rollback), answer from `references/mongodb-expert-context.md` plus the Manual links it cites — do not force a sibling-hub handoff.

## Bundled context

The full MongoDB fundamentals context — quick rules, core document/MQL model, CRUD and write-atomicity semantics, transactions, data-modeling and embed-vs-reference guidance, index and aggregation principles, driver-vs-mongosh guidance, and version-sensitivity notes — lives in `references/mongodb-expert-context.md` (**Read it** when a question needs grounding in fundamentals rather than one sub-skill's depth; it is also the no-match fallback target named in Skill guidance). Source: `docs/mongodb-expert-context.md` in an internal repository.

<!-- cross-hub-map -->
## Cross-hub map — where every MongoDB topic lives

All MongoDB knowledge is split across **four hubs** (plus `misc-catch-all` for KB-article
lookups and repo install/run, and `mongodb-docset-lookup` for offline Manual page lookup from the
local Dash docset). If a task's deep material is **not** in this hub's Sub-skill routing
table, it is either a reference file under a sibling hub — **activate that hub or Read its
`references/<name>.md` directly** — or a standalone top-level skill for a narrower topic
(`mongodb-gridfs`, `mongodb-odm-patterns`); see the frontmatter `whenNotToUse` for those cases.

| Hub | Owns | Example reference files |
| --- | --- | --- |
| `mongodb-expert` | Core data plane + **engine internals**: CRUD/MQL, aggregation, indexes, query performance, schema design, transactions, change streams, time-series, geospatial, views, BSON, error codes, connection strings, driver internals, **WiredTiger cache/eviction/checkpoint internals**, mongosh, database tools, multi-tenancy, sharding, replication, Compass | `references/mongodb-wiredtiger-internals.md`, `mongodb-indexes-deep.md`, `mongodb-sharding.md`, `mongodb-replication.md` |
| `mongodb-atlas-expert` | Atlas **cloud platform**: control plane, Atlas Search, Vector Search, Stream Processing, Charts, Data Federation, App Services, Triggers, Online Archive, Flex, networking, IAM/RBAC, Terraform, AKO | `mongodb-atlas-expert/references/mongodb-atlas-search.md`, `mongodb-atlas-vector-search.md` |
| `atlas-diagnostics-expert` | Live **diagnostics & performance**: ts-diag, FTDC, performance-troubleshooting symptom triage, benchmarking, monitoring/observability, capacity planning | `atlas-diagnostics-expert/references/mongodb-performance-troubleshooting.md` |
| `mongodb-operations-expert` | **Ops & data movement**: backup/restore, DR, Ops Manager, upgrades, migration, mongosync, relational migrator, CDC, data lifecycle, security architecture, encryption, compliance, cost, Kafka/Spark connectors | `mongodb-operations-expert/references/mongosync.md`, `mongodb-backup-restore.md` |

**High-overlap routing notes:**
- Performance **symptom triage** (high CPU, cache pressure, slow queries, latency spikes) starts at `atlas-diagnostics-expert`, but **storage-engine root-cause internals** (WiredTiger cache fill / dirty trigger / eviction threads / reconciliation / checkpoints) are owned by `mongodb-expert` — cross-load `mongodb-expert/references/mongodb-wiredtiger-internals.md` (and `mongodb-wiredtiger.md`) for depth.
- Migration symptoms vs migration **execution**: live-cluster diagnosis → `atlas-diagnostics-expert`; the migration/mongosync runbook → `mongodb-operations-expert`.
- Atlas Search/Vector **query syntax & index design** → `mongodb-atlas-expert`; the slowness *triage* of a running search → `atlas-diagnostics-expert`.
