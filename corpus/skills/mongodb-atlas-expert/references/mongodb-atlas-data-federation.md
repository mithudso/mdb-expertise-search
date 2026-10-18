<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-data-federation` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-data-federation
title: "MongoDB Atlas Data Federation and Online Archive"
category: mongodb
version: "1.1.0"
updated: "2026-05-29"
description: >
  Authoritative reference for MongoDB Atlas Data Federation and Online Archive —
  covering Federated Database Instance (FDI) architecture and configuration,
  supported data sources (S3, Azure Blob, GCS, Atlas clusters, HTTP), virtual
  collection mapping, path-based partitioning and pushdown optimization, Parquet
  performance patterns, Atlas Online Archive tiering rules and query routing,
  Atlas SQL Interface with JDBC/ODBC for BI tools (Tableau, Power BI), IAM role
  assumption and OIDC workload identity, cost model ($5/TB data processed),
  known limitations (read-only object storage, 30-query concurrency, no JS engine,
  field-order loss in Parquet), anti-patterns, and sequenced troubleshooting.
  TRIGGER: "federated database instance", "query S3 from MongoDB", "Atlas Data
  Federation", "Online Archive", "FDI", "data lake MongoDB", "Atlas SQL Interface",
  "JDBC MongoDB", "ODBC MongoDB", "Tableau MongoDB SQL", "Power BI MongoDB",
  "data tiering Atlas", "Parquet MongoDB", "cross-cluster query Atlas",
  "IAM role MongoDB", "$out to S3".
  SKIP: Atlas Stream Processing real-time pipelines (use mongodb-atlas-stream-processing),
  BI Connector legacy setup (use mongodb-bi-connector), Spark/Databricks pipelines
  against Atlas (use mongodb-spark-connector), general Atlas cluster administration
  (use mongodb-atlas-expert).
tags:
  - mongodb
  - atlas
  - data-federation
  - online-archive
  - sql-interface
  - s3
  - parquet
  - bi-tools
  - cost-optimization
  - iam
whenToUse:
  - "Designing or architecting a federated data lake on Atlas spanning S3, Azure Blob, GCS, or multiple Atlas clusters"
  - "Querying across live Atlas cluster data and cold object storage in a single pipeline"
  - "Configuring or troubleshooting Atlas Online Archive — archive rules, partition fields, job failures, or query routing"
  - "Integrating Tableau, Power BI, or other BI tools via the Atlas SQL Interface (JDBC/ODBC)"
  - "Analyzing or optimizing Data Federation costs — data processed charges, partition strategy, Parquet conversion"
  - "Setting up AWS IAM role assumption or OIDC Workload Identity Federation for FDI access to S3"
  - "Comparing Atlas Data Federation (batch/ad-hoc analytics) vs. Atlas Stream Processing (real-time streaming)"
  - "Troubleshooting FDI query timeouts, high data-processed costs, concurrency limit errors, or private endpoint connectivity"
  - "Designing hot-warm-cold data tiering with Online Archive"
  - "Exporting Atlas collection data to S3 as Parquet via $out"
whenNotToUse:
  - "Real-time/streaming pipelines — use mongodb-atlas-stream-processing"
  - "Legacy BI Connector (mongosqld) setup or migration — use mongodb-bi-connector"
  - "Spark/Databricks reading from Atlas — use mongodb-spark-connector"
  - "General Atlas cluster administration unrelated to data federation — use mongodb-atlas-expert"
  - "Kafka-based data pipelines — use mongodb-kafka-connector"
related_skills:
  - mongodb-atlas-expert
  - mongodb-cost-optimization
  - mongodb-aws-networking
  - mongodb-atlas-stream-processing
  - mongodb-migration-patterns
  - mongodb-spark-connector
  - mongodb-bi-connector
---

# MongoDB Atlas Data Federation and Online Archive

## Overview

Atlas Data Federation is MongoDB's serverless distributed query engine that enables native querying, transformation, and movement of data across multiple heterogeneous sources — both inside and outside Atlas — using standard MongoDB Query Language (MQL) and an optional SQL interface. Data Federation exposes a **Federated Database Instance (FDI)** that maps **virtual collections** to underlying physical data stores; clients connect to the FDI and query as if operating against a standard MongoDB cluster.

Atlas Online Archive is Atlas's integrated data tiering feature that automatically moves infrequently accessed documents from a live Atlas cluster to cost-efficient object storage (S3), while keeping the data queryable via the same FDI endpoint as the source cluster.

### When to use this skill

Use when the task involves any of: designing or troubleshooting a federated data lake; querying across live Atlas clusters + object storage; configuring Online Archive tiering rules; integrating BI tools via Atlas SQL; analyzing Data Federation costs; or comparing Data Federation vs. Atlas Stream Processing. Stop if the task is about Atlas cluster administration unrelated to data federation — use `mongodb-atlas-expert` instead.

---

## Core Concepts

### Federated Database Instance (FDI)

The central configuration object for Data Federation. An FDI:
- Has a unique connection string (separate from any Atlas cluster)
- Contains a **storage configuration JSON** (`storageSetConfig`) defining:
  - `stores` — named references to data sources (S3 bucket, GCS bucket, Azure container, Atlas cluster, Online Archive, HTTP URL)
  - `databases` — virtual databases containing virtual collections/views
  - Virtual collection `sources` — mapping from a virtual collection to one or more store paths
- Supports wildcard (`*`) collection names for S3 and Atlas cluster stores, dynamically naming collections from path segments
- Resides in a specific cloud provider + region (cannot span regions)
- Default limit: 25 FDIs per project (up to 100 on request)

### Supported Data Sources

| Source Type | Read | Write ($out / $merge) |
|---|---|---|
| AWS S3 | Yes | Yes (with `outToS3` privilege) |
| Azure Blob Storage | Yes | Yes (with `outToAzure` privilege) |
| Google Cloud Storage | Yes | Yes (with `outToGCP` privilege) |
| Atlas Cluster | Yes | Yes (with `$merge` into) |
| Atlas Online Archive | Yes | No |
| HTTP / HTTPS URL | Yes | No |

**Supported file formats for object storage:** JSON, BSON, CSV, TSV, Avro, ORC, and Parquet. Parquet is the preferred format for large analytical workloads due to columnar pushdown and row group selection optimizations.

### Three-Plane Architecture

```
Client (MQL or SQL)
        |
  [Control Plane]
  ├─ TLS termination
  ├─ Query parsing + planning
  ├─ Cursor management
  └─ Result aggregation
        |
  [Compute Plane]
  ├─ Elastic agent pool (region-nearest to data store)
  ├─ Partition pruning + filter pushdown
  ├─ Parquet column projection + row group selection
  └─ Cross-source join processing
        |
  [Data Plane]
  ├─ S3 / Azure Blob / GCS buckets
  ├─ Atlas clusters
  ├─ Online Archives
  └─ HTTP endpoints
```

**Single-cluster optimization:** If the only data source is a single Atlas cluster, the Control Plane bypasses the Compute Plane and issues the query directly to the cluster.

**Data locality:** The Compute Plane's elastic agents are positioned in the nearest cloud region to minimize cross-region data transfer. When source and FDI are on the same cloud provider, the provider's internal network is used; cross-provider traffic traverses the public internet.

---

## Atlas Online Archive

### What it does

Online Archive automatically moves documents matching an archival rule out of the live Atlas cluster into Atlas-managed S3-compatible object storage, while keeping those documents queryable through the cluster's FDI endpoint (transparent to the application).

### Requirements

- Dedicated cluster M10 or higher (not available on M0/M2/M5 shared tier)
- MongoDB 5.0+ on the source cluster

### Archive Rule Types

**1. Date-Based (most common)**
```json
{
  "criteria": {
    "type": "DATE",
    "dateField": "createdAt",
    "dateFormat": "ISODATE",
    "expireAfterDays": 90
  }
}
```

**2. Custom Query**
```json
{
  "criteria": {
    "type": "CUSTOM",
    "query": "{ \"status\": \"completed\", \"updatedAt\": { \"$lt\": { \"$date\": { \"$numberLong\": \"1700000000000\" } } } }"
  }
}
```

### Partition Fields

Partition fields organize archived data into S3 prefix paths and are critical for query performance against archived data. Choose fields commonly used in query filters:
```json
{
  "partitionFields": [
    { "fieldName": "region",     "order": 0 },
    { "fieldName": "createdAt",  "order": 1 },
    { "fieldName": "customerId", "order": 2 }
  ]
}
```

### Archive Job Timing & Processing

- Archive jobs run every **5 minutes**
- Matching documents are staged in a temporary collection, then written to object storage in files up to **100 MB**
- Maximum throughput: **2 GB per 5-minute interval**
- Archived documents are deleted from the live cluster after successful write to object storage
- **Schedule window:** Archive jobs can be limited to a configured time window (e.g., off-hours) to reduce impact on production workloads

### Query Routing

When an application queries the cluster's Online Archive endpoint (same FDI connection string as the live cluster), Atlas routes:
- Recent data → live cluster
- Archived data → Online Archive (object storage)
- Combined queries → both, results merged transparently

This is the key value: applications do not need to change query patterns after data is archived.

---

## Atlas SQL Interface

Atlas SQL Interface uses Data Federation as its query engine to expose a standard SQL-92 dialect over Atlas data. It is the primary integration path for BI tools.

### Supported Connections

| Connection Type | Supported Tools |
|---|---|
| JDBC Driver | Tableau Desktop/Server, custom Java apps, DBeaver |
| ODBC Driver | Power BI Desktop/Service, Excel, generic ODBC clients |
| Direct SQL | mongosh SQL mode, custom integrations |

### Driver Versions (as of 2025)
- **JDBC Driver**: 3.0.1+ (added on-premises connectivity for MongoDB Enterprise 6.0+)
- **ODBC Driver**: 2.0.0+ (added on-premises + Kerberos/GSSAPI for Windows and Linux)

### Power BI Integration
- Certified by Microsoft
- Supports DirectQuery mode (live queries to Atlas) and Import mode
- Available via Microsoft AppSource or direct download

### Tableau Integration
- Custom connector developed with Tableau
- Supports Tableau Desktop, Tableau Server, Tableau Prep
- Tableau Cloud support (expected H1 2025)

### Atlas Cluster Requirements for SQL Interface
- Atlas clusters: MongoDB 5.0+
- Self-managed Enterprise: MongoDB 6.0+

### Schema Management

The SQL Interface requires a schema definition to map BSON document structure to tabular columns. Schemas can be:
- **Auto-inferred** from a sample of documents
- **Manually set** with `sqlSetSchema` command
- **Retrieved** with `sqlGetSchema` command

---

## Query Syntax and Capabilities

### Connecting to a Federated Database Instance

The FDI has its own connection string, separate from any Atlas cluster. Retrieve it from Atlas UI → Data Federation → [instance] → Connect → Connect with MongoDB Driver.

```bash
# mongosh
mongosh "mongodb+srv://<fdi-hostname>/admin" \
  --username <db-user> --password <password>

# Node.js driver (same as any MongoClient)
const client = new MongoClient(
  "mongodb+srv://<fdi-hostname>/admin",
  { auth: { username, password } }
);
await client.connect();
const db = client.db("analytics");    // virtual database name from storageSetConfig
const coll = db.collection("events"); // virtual collection name
```

The FDI does **not** share an IP allowlist with Atlas clusters — allowlist rules on the cluster do not apply to the FDI endpoint.

### MQL on Federated Data

All standard MQL operations work against virtual collections. Important behavioral differences from regular clusters:

- **No guaranteed document order** on object storage sources unless `$sort` is specified
- **`$sample` is not truly random** — returns first N documents encountered (not random selection from full dataset)
- **`$skip` does not reduce data scan** — all relevant partitions are still read before skipping
- **Field order not preserved** in columnar storage (Parquet) — avoid embedded document equality queries relying on field order

### Supported Aggregation Stages

Most aggregation pipeline stages are supported. Key exceptions and caveats:

| Stage | Status | Notes |
|---|---|---|
| `$match` | Supported | Partition pruning only for `$eq`, `$gt`, `$lt`, `$gte`, `$lte`, `$ne`, `$and`, `$or`, `$in` |
| `$group` | Supported | Empty string keys for accumulator fields not supported |
| `$lookup` | Supported | Cross-database join via alternate syntax |
| `$out` | Supported | Alternate syntax required for S3 writes; MongoDB 7.0+ for cross-database same-cluster writes |
| `$merge` | Supported | Alternate `into` field syntax for Atlas cluster targets |
| `$sample` | Partial | Returns first N documents, not a random sample |
| `$skip` | Supported | Does NOT reduce data scan |
| `$geoNear` | Atlas clusters only | Not available for S3/HTTP sources |
| `$graphLookup` | Atlas clusters only | Single-collection Atlas mappings only |
| `$search` | Atlas clusters only | Full-text search indexes required |
| `$text` | Atlas clusters only | |
| `$where` | Not supported | No server-side JavaScript engine |
| `$function` | Not supported | No server-side JavaScript engine |
| `$accumulator` | Not supported | No server-side JavaScript engine |
| `$indexStats` | Not supported | |
| `$listSessions` | Not supported | |
| `$planCacheStats` | Not supported | |

### `$out` to Object Storage (Data Export Pattern)

```javascript
db.orders.aggregate([
  { $match: { status: "completed", createdAt: { $lt: new Date("2024-01-01") } } },
  { $out: {
      s3: {
        bucket: "my-archive-bucket",
        region: "us-east-1",
        filename: "completed-orders-2023",
        format: { name: "parquet" }
      }
    }
  }
])
```

---

## Performance: Pushdown Optimization and Partitioning

### Path-Based Partitioning (S3)

Design S3 key prefixes to match query patterns. The FDI configuration maps a path template with **partition attributes** so the engine can prune irrelevant prefixes:

```json
{
  "stores": [{
    "name": "s3Store",
    "provider": "s3",
    "bucket": "my-data-lake",
    "region": "us-east-1"
  }],
  "databases": [{
    "name": "analytics",
    "collections": [{
      "name": "events",
      "dataSources": [{
        "store": "s3Store",
        "path": "/events/{region string}/{year int}/{month int}/{day int}/*.parquet"
      }]
    }]
  }]
}
```

With this configuration, a query `{ region: "us-east-1", year: 2024, month: 3 }` skips all S3 prefixes not matching those values.

**Supported partition attribute comparison operators for pruning:**
`$eq`, `$gt`, `$lt`, `$gte`, `$lte`, `$ne`, `$and`, `$or`, `$in`

### Parquet Optimization

For Parquet files, the engine applies:
- **Row group selection** — uses Parquet metadata min/max statistics to skip irrelevant row groups without reading them
- **Column projection** — only the columns referenced in the query are read from storage

**Recommendation:** Store data as Parquet with appropriate row group sizes (128 MB) and sorted by the most common filter columns.

### Query Pushdown to Atlas Clusters

For Atlas cluster data stores, `$match` stages that can be processed on the cluster are pushed down before data is returned to the federated layer. This reduces inter-service data transfer.

### Cost Implication of Partitioning

Data processed is charged at **$5.00/TB** (10 MB minimum per query). Partition pruning is the largest cost lever: a well-partitioned 10 GB collection with a targeted query incurs 1 GB of "Data Processed" vs. 10 GB without partitions — a 10x reduction. A blank `$match` (`{}`) always scans the entire collection regardless of partitions. Run `explain()` before production queries to see how many partitions will be accessed.

---

## Security Model

### Authentication Methods

Data Federation (FDI) supports:
- **SCRAM** (username/password)
- **X.509 Certificates**
- **OIDC / Workload Identity Federation** — secretless auth using external IdP (AWS, Azure, GCP IAM; requires M10+, MongoDB 7.0.11+)
- **AWS IAM** — passwordless auth using IAM user/role; MongoDB strongly recommends IAM roles over IAM users

### AWS IAM Role Assumption (Unified AWS Access)

For S3 access, Atlas uses a cross-account IAM role assumption pattern:
1. Create an IAM role in your AWS account with S3 read permissions
2. Trust policy allows the Atlas AWS account to assume the role
3. Register the role ARN in Atlas via the "Unified AWS Access" configuration
4. Data Federation uses `sts:AssumeRole` to obtain temporary credentials for each query

This avoids storing long-term AWS credentials in Atlas. For Lambda/EC2 applications, the application assumes a role; Atlas separately assumes its role — neither needs a shared secret.

### Network Security

- All data traffic between FDI and data stores uses **TLS encryption**
- FDIs reside in regional VPCs
- **Private endpoint support** available for FDIs (AWS PrivateLink)
- No IP allowlist is required for FDI connections (IP allowlist applies to Atlas clusters only)
- For data sovereignty: deploy FDI in same region as data sources so cursor data stays in-region

### Atlas RBAC for FDI

Custom database roles control FDI access with granular privilege actions:
- `storageGetConfig` / `storageSetConfig` — read/write storage configuration
- `outToS3` / `outToAzure` / `outToGCP` — write via `$out`
- `sqlGetSchema` / `sqlSetSchema` — manage SQL interface schema
- `viewAllHistory` — access `$queryHistory`

---

## Cost Model

### Data Federation Costs

| Cost Component | Rate |
|---|---|
| Data Processed | $5.00 / TB (10 MB minimum per query) |
| Data Returned (same-region AWS) | $0.01 / GB |
| Data Returned (cross-region or internet) | Standard cloud egress rates |
| $out / $merge writes | Same "data returned" rate |

**Data Processed** = bytes read from underlying storage to answer the query. This is the primary cost driver. Partition pruning and Parquet column projection directly reduce this.

**Data Returned** = bytes sent back to the client. Secondary cost for large result sets.

### Online Archive Costs

| Cost Component | Rate |
|---|---|
| Archive Storage | Per GB-day (varies by cloud region; see Atlas pricing page) |
| Data Processed (archive queries) | $5.00 / TB (same as Data Federation) |
| Data Returned | Standard cloud egress |

**Online Archive vs. dedicated cluster storage:**
- M30 cluster storage: ~$0.25/GB-month (NVMe, estimate; confirm on Atlas pricing page)
- Online Archive storage: materially cheaper per GB-day — typically 80-90% lower than dedicated cluster storage (confirm on Atlas pricing page under Tools & Services → Online Archive)
- Decision threshold: data accessed less than once per week is a candidate for Online Archive

### Cost Optimization Tactics

1. **Partition by query filter fields** — single biggest lever; see §Performance for mechanics
2. **Use Parquet format** — columnar compression + row group pruning cuts data processed ~60-80% vs. JSON
3. **Set query byte limits** — configure `maxBytesProcessed` per-query and per-project to hard-cap runaway scans
4. **Never run `{}` match on large collections** — always scans 100% of data regardless of partitions
5. **Schedule Online Archive jobs during off-hours** — limits staging-collection I/O impact on production cluster
6. **Check dollar costs on the billing page only** — the FDI metrics page shows bytes and query counts but no dollar amounts; dollar totals appear only under Atlas Billing → Data Federation

---

## Common Use Cases

### 1. Hot-Warm-Cold Data Tiering

```
Hot (M30+ cluster, NVMe):  last 30 days
Warm (M10 cluster, GP3):   30-180 days
Cold (Online Archive, S3): 180+ days → queryable via same FDI endpoint
```

### 2. Multi-Source Analytics (Data Lake Query)

Query live cluster data alongside historical S3 archives and external data files using `$lookup` or `$unionWith`:
```javascript
db.recentOrders.aggregate([
  { $unionWith: { coll: "archivedOrders" } },   // archivedOrders maps to S3
  { $group: { _id: "$customerId", total: { $sum: "$amount" } } },
  { $sort: { total: -1 } }
])
```

### 3. BI Tool Integration (Atlas SQL)

Connect Tableau or Power BI to the FDI via JDBC/ODBC, auto-infer schema, and run SQL queries over live Atlas + archived S3 data without ETL.

### 4. Workload-Isolated Reporting

Export cluster data to S3 via `$out` on a schedule, then run heavy analytical queries against the S3 copy via Data Federation — completely isolating analytical load from production OLTP workloads.

### 5. Data Export and ETL Source

Use `$out` to S3 as a scheduled Parquet export:
```javascript
db.transactions.aggregate([
  { $match: { date: { $gte: yesterday } } },
  { $out: { s3: { bucket: "datalake", filename: "txn-{date}", format: { name: "parquet" } } } }
])
```
Downstream systems (Spark, Athena, BigQuery) consume the Parquet files.

### 6. Cross-Cluster Join

Compare data across two Atlas clusters in the same federated namespace:
```javascript
db.clusterA_users.aggregate([
  { $lookup: {
      from: "clusterB_orders",
      localField: "_id",
      foreignField: "userId",
      as: "orders"
  }}
])
```

---

## Anti-Patterns

### AP1: Full-Collection Scans on Large Object Storage

Using `{}` or a non-partition-aligned `$match` against a multi-terabyte S3 collection will scan all files and incur significant "data processed" costs. Always design partitions for the expected query shapes.

### AP2: Using Data Federation for OLTP Write Traffic

Data Federation is read-only for object storage sources. Do not route insert/update/delete operations through an FDI endpoint — they will fail. Use FDI only for analytical/read workloads.

### AP3: Expecting Random Sampling

`$sample` on object storage does not return a statistically random sample — it returns the first N documents from the first files read. For true random sampling, add a `random` field to documents at write time and use `$match` on that field.

### AP4: Field-Order-Dependent Queries

Parquet uses columnar storage which does not preserve intra-document field order. Embedded document equality queries (`{ "address": { "city": "NYC", "zip": "10001" } }`) may fail to match because field order is not guaranteed. Use individual field queries instead.

### AP5: Missing `$sort` on Object Storage Queries

Results from object storage are returned in partition read order (concurrent, non-deterministic). Always add `$sort` if ordered results are needed.

### AP6: Running Data Federation as an Atlas Cluster Replacement

Data Federation has a 6-hour query timeout, 30-query concurrency limit, 16 MB document limit, and no index support on object storage. It is an analytics engine, not a transactional database replacement.

### AP7: Relying on Partition Pruning for Aggregation Operators Not in the Pruning Set

Only `$eq`, `$gt`, `$lt`, `$gte`, `$lte`, `$ne`, `$and`, `$or`, `$in` trigger partition pruning. Using `$regex` or `$exists` in a `$match` will not prune partitions and will scan all files.

### AP8: Ignoring Archive Partition Field Selection

If Online Archive partition fields do not match query patterns, every archived-data query triggers a full archive scan. Choose partition fields that mirror the most common query filter fields (`customerId`, `region`, `createdAt` in order of selectivity).

---

## Troubleshooting

### FDI Query Timeout (6-hour limit)

**Symptom:** `MongoServerError: operation exceeded time limit`
**Diagnosis:**
1. Run `db.currentOp()` or check `$queryHistory` on the FDI to confirm elapsed time and bytes processed.
2. Identify whether the query is hitting object storage (scan-bound) or an Atlas cluster (index-bound).

**Resolution:**
1. Add a partition-aligned `$match` as the first pipeline stage to prune irrelevant S3 prefixes.
2. If the scan is still too large, split it into time-bounded sub-queries (e.g., process one month at a time).
3. Convert source files from JSON/CSV to Parquet to enable row group + column pruning.
4. Set `maxTimeMS` to a value well under 6 hours so failures surface early during development.

### High "Data Processed" Costs

**Symptom:** Unexpectedly large Data Federation line item on Atlas invoice.
**Diagnosis:**
1. Open Atlas → Billing → current invoice → Data Federation section; identify which FDI and date range drove the cost.
2. Run `db.collection.explain("executionStats").aggregate([...pipeline...])` on the FDI to see `nPartitionsScanned`.

**Resolution:**
1. Re-design S3 path template so the highest-selectivity filter field is the first partition attribute.
2. Switch source files from JSON/CSV to Parquet.
3. Set a project-level byte limit: Atlas UI → Data Federation → Query Limits → max bytes processed.
4. Add per-query `maxBytesProcessed` option to the aggregation to hard-cap individual queries.

### Online Archive Not Moving Data

**Symptom:** Documents matching the archive rule remain on the live cluster after 15+ minutes.
**Diagnosis:**
1. Check Atlas → Online Archive → [collection] → Activity tab for archive job status and error messages.
2. Verify the `dateField` value in the archive rule matches the exact field name in documents (case-sensitive).
3. Confirm the field stores an ISODate (not a Unix timestamp string) if `dateFormat: "ISODATE"` is set.
4. Confirm the cluster tier is M10+ and the MongoDB version is 5.0+.

**Resolution:**
1. Correct the `dateField` name or `dateFormat` in the archive rule to match actual document structure.
2. If the field is a Unix epoch integer, change `dateFormat` to `"EPOCH_MILLISECONDS"` or `"EPOCH_SECONDS"`.
3. Adding an index on the date field is not required but improves archive job scan speed.

### SQL Interface Schema Mismatch

**Symptom:** BI tool returns no columns, no data, or wrong column types after connecting.
**Diagnosis:**
1. Confirm the FDI has a schema set: run `db.runCommand({ sqlGetSchema: "collectionName" })` — empty result means no schema.
2. Check whether the schema was inferred from a small or non-representative sample.

**Resolution:**
1. Set an explicit schema: `db.runCommand({ sqlSetSchema: "collectionName", schema: { version: 1, jsonSchema: {...} } })`.
2. After collection structure changes, re-infer: Atlas UI → Data Federation → [instance] → SQL → Refresh Schema.
3. For Power BI DirectQuery mode, ensure the schema includes all columns referenced in the report.

### Concurrency Limit Errors (30-query limit)

**Symptom:** `MongoServerError: too many concurrent queries`
**Diagnosis:**
1. Confirm the FDI has reached its 30-simultaneous-query limit (check Atlas FDI metrics page → Active Queries).
2. Determine whether the cause is many short queries or a few long-running scans blocking slots.

**Resolution:**
1. Implement a client-side queue so at most 25 queries are in flight simultaneously (leave headroom).
2. Break complex multi-source pipelines into sequential steps, persisting intermediate results with `$out` to reduce per-query duration.
3. Contact your MongoDB account team to request a higher concurrency limit (up to 100 FDIs per project; per-FDI concurrency increases require discussion).

### Private Endpoint Connectivity

**Symptom:** Connection to FDI times out or refuses from within a VPC.
**Diagnosis:**
1. Confirm you are using the FDI connection string (not the cluster connection string — they are different).
2. Check Atlas → Network Access → Private Endpoints → **Federated Database / Online Archive** tab (separate from the Clusters tab).

**Resolution:**
1. Create a private endpoint specifically for the FDI — cluster private endpoints do not cover FDI traffic.
2. Navigate: Atlas → Network Access → Private Endpoints → Federated Database / Online Archive → Add Private Endpoint.
3. Update your application's connection string to use the private endpoint hostname after provisioning.

---

## Data Federation vs. Atlas Stream Processing

| Dimension | Data Federation | Atlas Stream Processing |
|---|---|---|
| Workload type | Batch / ad-hoc analytics | Real-time / continuous streaming |
| Data source | S3, Azure Blob, GCS, Atlas clusters, Online Archives, HTTP | Kafka, Atlas change streams |
| Query model | MQL aggregation pipeline (on-demand) | Continuous pipeline (always running) |
| Latency | Seconds to minutes | Sub-second to seconds |
| State | Stateless query per execution | Stateful windows + watermarks |
| Write output | $out to S3 / Atlas cluster | $emit to Atlas collection or Kafka |
| Pricing | Per TB of data processed | Per SPI (Stream Processing Instance) hour |
| Use case fit | Cold data lake, BI reporting, data export, archival | IoT alerting, fraud detection, real-time aggregations, CDC fan-out |

**Decision rule:** Use Data Federation when you need to query data at rest (including cold archives). Use Atlas Stream Processing when you need to react to or aggregate a continuous data stream with low latency.

**Hybrid pattern:** Use Atlas Stream Processing to enrich/filter a Kafka stream and write results to Atlas, then use Data Federation / Online Archive for historical querying of that Atlas data.

---

## References

- [Atlas Data Federation Overview](https://www.mongodb.com/docs/atlas/data-federation/adf-overview/overview/)
- [Atlas Data Federation Architecture](https://www.mongodb.com/docs/atlas/data-federation/adf-overview/architecture/)
- [Configure Data Stores for a Federated Database Instance](https://www.mongodb.com/docs/atlas/data-federation/config/config-data-stores/)
- [Data Federation Query Performance Optimization](https://www.mongodb.com/docs/atlas/data-federation/adf-overview/query-performance-optimization/)
- [Partition Attribute Types](https://www.mongodb.com/docs/atlas/data-federation/supported-unsupported/supported-partition-attributes/)
- [Supported Aggregation Stages](https://www.mongodb.com/docs/atlas/data-federation/supported-unsupported/supported-aggregation/)
- [Data Federation Limitations](https://www.mongodb.com/docs/atlas/data-federation/supported-unsupported/limitations/)
- [Data Federation Costs (Billing)](https://www.mongodb.com/docs/atlas/billing/data-federation/)
- [Online Archive Costs (Billing)](https://www.mongodb.com/docs/atlas/billing/online-archive/)
- [Atlas SQL Interface Overview](https://www.mongodb.com/docs/atlas/data-federation/query/connect-with-sql-overview/)
- [Connect with JDBC Driver](https://www.mongodb.com/docs/atlas/data-federation/query/sql/drivers/jdbc/connect/)
- [Connect with ODBC Driver](https://www.mongodb.com/docs/atlas/data-federation/query/sql/drivers/odbc/connect/)
- [Set Up Unified AWS Access (IAM Role)](https://www.mongodb.com/docs/atlas/security/set-up-unified-aws-access/)
- [Online Archive — Automated Data Tiering](https://www.mongodb.com/products/platform/atlas-online-archive)
- [Atlas SQL Interface — GA Blog Post](https://www.mongodb.com/company/blog/product-release-announcements/real-time-insights-through-atlas-sql-interface)
- [Online Archive Terraform Resource](https://registry.terraform.io/providers/mongodb/mongodbatlas/latest/docs/resources/online_archive)

## See also: MongoDB Spark Connector

When the workload is **Spark/Databricks reading from Data Federation** (not direct SQL), load `mongodb-spark-connector`. Since connector v10.5, batch reads against a Federated Database Instance work with `AutoBucketPartitioner`, `SamplePartitioner`, or `PaginateBySizePartitioner` (other partitioners are unsupported on Federation sources). The decision split is roughly:
- **Use Data Federation directly** (SQL Interface, BI tools, ad-hoc analytics, JDBC/ODBC) when the consumer speaks SQL and the query is interactive.
- **Use Spark Connector against Federation** when the consumer is a Spark/Databricks pipeline that needs DataFrame transforms, ML feature extraction, or joins with non-Mongo Spark sources.
- **Use Spark Connector against the underlying Atlas cluster directly** when there's no S3/Federation layer in between — Federation adds query-time cost per TB scanned.

See `mongodb-spark-connector` section 5 ("Partitioner strategies") and section 11 ("Spark Connector vs alternatives") for the full decision matrix.
