<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-online-archive` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-online-archive
description: >-
  Automated data tiering from Atlas clusters (M10+) to cloud object storage
  (S3/Azure Blob/GCS) — archive rules (DATE/CUSTOM criteria), partitionFields
  strategy, federated queries via Data Federation, $merge restore, cost model
  ($5/TB query processing), limitations, and anti-patterns. TRIGGER: configuring
  online archive rules; troubleshooting archive backlog, partition field queries,
  or slow archive queries; estimating cost of data tiering; restore/rehydration
  workflows; deciding between Online Archive, TTL, and manual S3 export.
  SKIP: general Atlas Data Federation not involving Online Archive
  (mongodb-atlas-data-federation); TTL-only data deletion (no archival needed);
  time-series collection lifecycle (use expireAfterSeconds); Atlas Backup or
  snapshot export.
category: mongodb
version: "1.1.0"
updated: "2026-05-29"
tags:
  - mongodb
  - atlas
  - online-archive
  - data-tiering
  - data-lifecycle
  - data-federation
  - cold-storage
  - cost-optimization
keywords:
  - online archive
  - atlas archive
  - archive rule
  - archiveAfterDays
  - partitionFields
  - data tiering
  - cold data
  - federated archive
  - archive backlog
  - DATE criteria
  - CUSTOM criteria
  - $merge restore
  - reduce Atlas storage cost
  - move data to S3 from Atlas
  - rehydrate archive
whenToUse:
  - "configure an online archive rule on an Atlas collection"
  - "archiveAfterDays: how old must a document be before it archives"
  - "partitionFields: which fields should I choose for the archive"
  - "archive query is slow — why is it doing a full scan"
  - "archive backlog is growing — how do I drain it"
  - "how much does querying archived data cost ($5/TB)"
  - "restore archived data back to the live cluster"
  - "should I use Online Archive or a TTL index"
  - "is Online Archive available on Flex or M0"
  - "cross-cloud archive limitation: Azure cluster + AWS S3"
whenNotToUse:
  - "General Atlas Data Federation not involving Online Archive — use mongodb-atlas-data-federation"
  - "Permanently deleting old data with no recovery need — TTL index, no skill needed"
  - "Time-series collection expiry — use expireAfterSeconds directly"
  - "Atlas Cloud Backup, snapshots, or restore — separate product"
  - "M0/Flex tier archiving questions — Online Archive requires M10+; state the blocker and stop"
related_skills:
  - mongodb-atlas-data-federation
  - mongodb-data-lifecycle
  - mongodb-cost-optimization
  - mongodb-atlas-expert
---

# MongoDB Atlas Online Archive

**Automated data tiering from Atlas clusters to cloud object storage — move cold data to S3/Azure Blob/GCS while keeping it queryable via Atlas Data Federation.**

## When to Use This Skill

**Trigger phrases / keywords** (activate on any of these):
- "online archive", "atlas archive", "archive rule", "data tiering", "cold data", "archive old data"
- "archiveAfterDays", "partitionFields", "federated archive", "archive backlog"
- "move data to S3 from Atlas", "reduce Atlas storage cost", "tiering cold documents"
- "restore from archive", "rehydrate archive", "unarchive", "$merge restore"

**Activate when a task involves:**
- Reducing Atlas cluster storage costs by offloading infrequently accessed data
- Configuring date-based or custom-criteria archive rules
- Designing partition fields for efficient federated queries on archived data
- Explaining the Online Archive / Data Federation relationship
- Troubleshooting archive backlog, field-not-found errors, or slow archive queries
- Evaluating whether Online Archive fits a given use case vs. TTL, manual S3 export, or a secondary cluster
- Planning restore/rehydration workflows (there is no automated restore)
- Estimating cost impact of archiving cold data

**Do NOT use this skill for:**
- General Atlas Data Federation configuration not involving Online Archive — use [[mongodb-atlas-data-federation]]
- TTL-based data deletion (TTL deletes; Online Archive moves) — clarify the distinction, then route accordingly
- Time-series collection lifecycle — Online Archive does not support time-series collections; use the time-series `expireAfterSeconds` option instead
- M0/Flex/Serverless tier questions about archiving — Online Archive requires M10+; recommend tier upgrade or a manual S3 export pattern
- Atlas Backup or snapshot export — separate product, separate docs

## What This Skill Produces

When invoked, produce one or more of the following based on the request type:

| Request type | Produce |
|---|---|
| "How does Online Archive work?" | Prose explanation + data flow diagram (text) |
| "Help me configure an archive rule" | JSON config snippet + parameter explanation |
| "Why is my archive query slow?" | Diagnosis checklist + partition pruning analysis |
| "Is Online Archive right for my use case?" | Decision table comparison + recommendation |
| "How do I restore archived data?" | Step-by-step `$merge` restore procedure |
| "What does this cost?" | Cost breakdown table + rule-of-thumb threshold |
| "What are the limits / gotchas?" | Bulleted limitations list + relevant anti-patterns |

Always cite the specific section of this skill used and call out any [ASSUMED] values when cluster tier, cloud provider, or data volume are not stated by the user.

## How to Respond When This Skill Is Active

Follow this sequence for every invocation:

1. **Classify the request** using the "What This Skill Produces" table above — identify which output type applies.
2. **Check eligibility** using the Quick-Decision table below. If the user's setup is ineligible (M0, time-series, etc.), state the blocker first and redirect before continuing.
3. **State any [ASSUMED] values** if the user hasn't specified cluster tier, cloud provider, collection type, or data volume — these affect the answer materially.
4. **Produce the requested output** — use code blocks for configs/queries, tables for comparisons, prose for explanations.
5. **Call out the top 1–2 relevant anti-patterns** from Section 10 that apply to the user's specific situation.
6. **Self-validate before responding** (see checklist below).

### Self-validation checklist

Before delivering any response, confirm:
- [ ] Cluster tier eligibility checked (M10+ required)
- [ ] Partition field immutability mentioned if configuration is being recommended
- [ ] "No automated restore" caveat included if restore is discussed
- [ ] $5/TB query processing cost noted if archived query patterns are involved
- [ ] Cross-cloud limitation noted if multi-cloud topology is mentioned
- [ ] No writes on archived data limitation noted if user implies update/delete on archive

---

## Quick-Decision: Should You Use Online Archive?

Use this table to decide before diving into configuration:

| Condition | Verdict |
|---|---|
| Cluster is M10 or higher, dedicated | Supported |
| Cluster is M0, Flex, or Serverless | Not supported — upgrade tier first |
| Collection is a standard collection | Supported |
| Collection is time-series | Not supported — use `expireAfterSeconds` |
| Collection is capped | Not supported |
| Data is queried < ~1×/week | Good fit — cost savings outweigh query charges |
| Data is queried daily or more | Marginal or negative ROI — keep in cluster |
| Need to run `$lookup` across archive + live | Not supported — denormalize before archiving |
| Need to write/update archived documents | Not supported — archive is read-only |
| Need cross-cloud federation (e.g., Azure cluster + AWS S3) | Not supported |

---

## 1. How Online Archive Works

Atlas Online Archive is an automated data-tiering service that moves documents from a live Atlas cluster (M10+) to fully managed cloud object storage without application changes. The archived data remains queryable through Atlas Data Federation.

### Core mechanism

1. You define an **archive rule** on a collection (date-based or custom-query).
2. Atlas evaluates the rule every **5 minutes** (default continuous mode) or on a **scheduled window** (daily/weekly/monthly, minimum 2-hour window).
3. Matching documents are staged in a temporary internal collection, then written to object storage in Parquet-like files up to **100 MB** each.
4. Each 5-minute cycle can archive up to **2 GB** of data. Larger backlogs are processed across multiple cycles.
5. Once archived, documents are **deleted from the live cluster** — the cluster's working set shrinks.
6. Atlas automatically provisions a **federated database instance** (one per cluster) that spans both the live cluster and the archive, so queries can target hot + cold data transparently.

### Minimum viable data threshold

For continuous archiving, Atlas will not archive if less than **5 MiB** of matching data exists after the first 7 days. This prevents pathologically small archive files.

### Supported tiers

- **M10 and higher dedicated clusters** on AWS, Azure, and GCP.
- Not available on free/shared (`M0`), Flex clusters, or serverless instances.
- Up to **50 online archives per cluster**, with up to **20 active** simultaneously.
- Only **one active archive per namespace** (database + collection combination) at a time.

### Object storage backends by cloud

| Atlas Cluster Cloud | Archive Storage |
|---|---|
| AWS | Atlas-managed S3 bucket (same region) |
| Azure | Azure Blob Storage (same region) |
| GCP | Google Cloud Storage (same region) |

Cross-cloud archive is **not supported** — the archive storage backend must match the cloud provider of the Atlas cluster.

---

## 2. Archive Rules

Every online archive requires exactly one rule, applied to one collection. You cannot apply a single rule to multiple collections.

### Rule type 1: DATE

Archives documents based on a date field value exceeding a retention age.

```json
{
  "criteria": {
    "type": "DATE",
    "dateField": "createdAt",
    "archiveAfterDays": 90
  },
  "partitionFields": [
    { "fieldName": "createdAt", "order": 0 },
    { "fieldName": "region",    "order": 1 }
  ]
}
```

**Key parameters:**
- `dateField` — must be an **already-indexed** BSON Date or date-equivalent field in the collection. Index it first.
- `archiveAfterDays` — documents older than this value (measured from the field's date value) are archived. Minimum: **7 days**. Maximum: **9,215 days** (~25 years).
- For DATE rules, the `dateField` **must** appear as the first `partitionField`.

### Rule type 2: CUSTOM

Archives documents matching an arbitrary MQL filter expression.

```json
{
  "criteria": {
    "type": "CUSTOM",
    "query": "{ \"status\": \"closed\", \"resolved\": true }"
  },
  "partitionFields": [
    { "fieldName": "accountId", "order": 0 },
    { "fieldName": "closedAt",  "order": 1 }
  ]
}
```

**Key parameters:**
- `query` — any valid `db.collection.find(query)` filter expression as a JSON string.
- Not limited to date fields — useful for status-based, tenant-based, or flag-based archiving.
- `partitionFields` are recommended but not required to match the query filter. Choose fields that match how archived data will later be queried.

### Partition fields

Partition fields control how archived data is organized in object storage and are critical for query performance.

- **Up to 2 partition fields** per archive rule.
- The **order matters** exactly like a compound index: queries that omit the first partition field trigger a full archive scan.
- Partition fields **cannot be changed** after archiving begins. Plan carefully.
- Supported partition field types: **date, string, and numeric** types. Nested fields (dot notation) are supported.
- Each unique combination of partition field values creates a separate data partition in object storage.

```
// DATE rule — partition order: createdAt (0), region (1)
// Efficient: { createdAt: { $gte: ... } }             — uses partition 0
// Efficient: { createdAt: ..., region: "us-east-1" }  — uses both partitions
// Inefficient: { region: "us-east-1" }                — full archive scan
```

### Archiving window (scheduled mode)

Introduced to avoid archiving during peak hours. Configure with:
- **Recurrence**: daily, weekly, or monthly
- **Minimum window**: 2 hours (to allow backlog clearing)

Scheduled mode uses the same archiving logic; it just restricts when the 5-minute evaluation loop is active.

### Data expiration (deletion from archive)

An optional `dataExpirationRule` automatically deletes data from the archive after a specified number of days:
- **Range**: 7 to 9,125 days
- Configurable via Atlas UI or Admin API after archive creation
- Deleted data **cannot be recovered** — use with caution for compliance use cases

---

## 3. Storage Backends

### AWS S3

- Atlas creates and manages the S3 bucket — you do not need to provision or configure it.
- Bucket names follow Atlas-internal conventions; you cannot specify a custom bucket name.
- Data resides in the **same AWS region** as the Atlas cluster.
- Files are stored as compressed columnar objects (Parquet-compatible format) enabling efficient column-level pruning during federation queries.

### Azure Blob Storage

- Generally available as of 2024 for both Online Archive and Data Federation.
- Enables customers running Atlas on Azure to keep archived data within the Azure ecosystem (data residency, egress cost avoidance).
- Blob container managed by Atlas in the same Azure region as the cluster.

### GCP Cloud Storage

- Supported for clusters running on Google Cloud.
- GCS bucket managed by Atlas in the same GCP region as the cluster.

### Cross-cloud note

Atlas Data Federation **cannot** run federated queries across cloud providers in a single query. For example, you cannot combine an Azure Blob archive with an AWS S3 data source in one federated database instance. Each federated instance is region- and cloud-scoped.

---

## 4. Querying Archived Data

### Connection strings

When Online Archive is active on a cluster, Atlas creates two read-only connection strings accessible from the Atlas UI (cluster connect dialog → "Online Archive"):

| Endpoint | What it queries |
|---|---|
| **Archive-only** | Archive data only; no live cluster I/O |
| **Cluster + Archive (federated)** | Both live cluster and archive; Atlas routes per document location |

Use the archive-only endpoint for analytics/reporting workloads to avoid impacting live cluster IOPS. Use the combined endpoint when you need a seamless view of all data regardless of age.

### Query language

Both MQL and SQL are supported via the federated endpoint. Standard MongoDB drivers work unchanged — connect to the federated URI instead of the cluster URI.

### Partition pruning

Query performance on archived data depends almost entirely on whether the query predicate includes the leading partition field(s).

```javascript
// Archive partitioned on: createdAt (0), customerId (1)

// FAST — pruned to matching date partitions
db.orders.find({ createdAt: { $gte: ISODate("2023-01-01"), $lt: ISODate("2023-04-01") } })

// FASTER — pruned to both partition dimensions
db.orders.find({ createdAt: { $gte: ISODate("2023-01-01") }, customerId: "acct_123" })

// SLOW — full archive scan (skips partition 0)
db.orders.find({ customerId: "acct_123" })
```

Atlas runs the minimum number of partition-lookup operations needed; each operation finds up to 1,000 partitions.

### Performance expectations

Queries against archived data are **materially slower** than live cluster queries. Blocking operations (sorts, groupings) that process all input documents are particularly expensive because they must read from object storage. Budget seconds to minutes for typical archive queries, not milliseconds.

### Limitations on archived queries

- **Read-only** — no inserts, updates, deletes, or replace operations on archived data.
- **No `$lookup`** across federated data sources (standard federated limitation).
- **No change streams** on federated sources.
- **No multi-document ACID transactions** on federated sources.
- **Maximum 30 concurrent queries** per federated database instance.
- **Maximum 120 simultaneous client connections** per federated instance per region.
- **Query timeout**: 6 hours or `maxTimeMS`, whichever is lower.
- **Document size**: 16 MB maximum (same as standard MongoDB).
- Result ordering is not guaranteed without an explicit `$sort`.

---

## 5. Data Federation Integration

### How Online Archive uses Data Federation under the hood

When you create an Online Archive on a cluster, Atlas automatically:
1. Provisions a **federated database instance** in the same cloud + region.
2. Configures a `stores` entry pointing to the Atlas-managed object storage bucket.
3. Maps a virtual database + collection in the federated instance that mirrors the archived collection's namespace.
4. Optionally maps the live cluster as a second store for the combined endpoint.

The federated instance's storage configuration (`stores` + `databases`) looks conceptually like:

```json
{
  "stores": [
    {
      "name":     "archiveStore",
      "provider": "online_archive",
      "clusterName": "MyCluster",
      "projectId": "<project-id>"
    },
    {
      "name":       "liveCluster",
      "provider":   "atlas",
      "clusterName": "MyCluster"
    }
  ],
  "databases": [
    {
      "name": "mydb",
      "collections": [
        {
          "name":        "orders",
          "dataSources": [
            { "storeName": "archiveStore", "path": "/{createdAt}/{customerId}/" },
            { "storeName": "liveCluster",  "database": "mydb", "collection": "orders" }
          ]
        }
      ]
    }
  ]
}
```

### Combining archive + live + external S3

You can extend a manually configured federated database instance to include additional data sources beyond the auto-created archive:

- **External S3/GCS/Blob** — add another `stores` entry with `provider: "s3"` and your bucket details.
- **Additional Atlas clusters** — add more cluster stores to join data across environments.
- **Multiple online archives** — each archive appears as a separate `dataSources` entry under the collection.

This enables a single MQL query to transparently span: live documents + archived documents + external S3 data. For example, combining an application's Online Archive with a separate data lake export in S3.

**Important**: federated queries across cloud providers are not supported within a single federated instance. All stores must use the same cloud provider.

---

## 6. Archive Monitoring

### Status states

Each online archive reports one of the following states in the Atlas UI and Admin API:

| State | Meaning |
|---|---|
| `PENDING` | Archive created, awaiting first evaluation cycle |
| `ARCHIVING` | Active — currently moving documents to object storage |
| `IDLE` | Active — waiting for next evaluation cycle |
| `PAUSED` | Manually paused; no archiving occurs |
| `DELETED` | Archive and its stored data have been removed |
| `ORPHANED` | Associated cluster no longer exists |

### Key metrics (Atlas UI / Metrics API)

- **Bytes Archived** — total data volume moved to object storage over time
- **Archival Backlog** — documents queued but not yet archived; rising backlog indicates the archive is not keeping up (cap is 2 GB/5 min)
- **Archival Errors** — count of documents that failed to archive; surface field-not-found and type-mismatch issues

### Common archival errors

| Error | Cause | Fix |
|---|---|---|
| Field not found | `dateField` missing from some documents | Add the field or use a `CUSTOM` criteria with `$exists` check |
| Type mismatch | `dateField` is not a valid BSON Date in some documents | Validate and migrate field types |
| Backlog growing | Archive throughput (2 GB/5 min) insufficient for write rate | Enable scheduled archiving during off-peak hours; reduce write rate or scale cluster |

### Atlas alerts

Configure Atlas alerts for:
- **Online Archive state transitions** (e.g., transitions to `ORPHANED`)
- **Billing threshold** — Online Archive query processing at $5/TB can spike unexpectedly

Metrics for online archives created before the June 2023 release may display N/A for some time-series metrics in the Atlas UI. Post-2023 archives have full metric history.

---

## 7. Restore from Archive

**There is no automated restore mechanism.** Atlas does not provide a one-click "move data back" operation. Restoration requires a manual aggregation pipeline using `$merge`.

### Restore procedure

1. **Pause the online archive** to prevent newly matching documents from being archived during restoration.

2. **Connect using the archive-only connection string** (not the combined endpoint) to target archived data directly.

3. **Run a `$merge` aggregation** from the archive back to the live cluster:

```javascript
// Basic restore — insert archived docs not already in cluster
db.orders.aggregate([
  {
    $match: {
      createdAt: { $gte: ISODate("2023-01-01"), $lt: ISODate("2023-04-01") }
    }
  },
  {
    $merge: {
      into: {
        atlas: {
          clusterName: "MyCluster",
          db:          "mydb",
          coll:        "orders"
        }
      },
      on:           ["_id"],
      whenMatched:  "keepExisting",
      whenNotMatched: "insert"
    }
  }
])
```

4. **Handle duplicates** — if the same document exists in both the archive and live cluster (because it was re-inserted after archival), use `$sort` before `$merge` to prefer the most recent version:

```javascript
db.orders.aggregate([
  { $sort:  { _id: 1, updatedAt: -1 } },
  { $merge: { ... } }
])
```

5. **Required permissions**: `Project Data Access Admin` or higher role. The `$merge` stage needs `readWrite` on the target database.

6. **Verify** data in the live cluster, then **delete the online archive** if no longer needed.

### Caveats

- Not recommended for datasets approaching 1 TB+ with many partitions — the federated query layer introduces significant overhead.
- Run the restore as a background operation: `db.runCommand({ aggregate: ..., pipeline: [...], cursor: {}, background: true })`.
- Ensure adequate disk space on the target cluster before restoring large datasets.
- A compound unique index on the `on` fields is required when using multiple merge fields:
  ```javascript
  db.orders.createIndex({ item: 1, source: 1 }, { unique: true })
  ```

---

## 8. Cost Model

### Storage cost

Archived data is billed at **object storage rates** (S3/Blob/GCS pricing in the same region) rather than Atlas cluster storage rates. Object storage is typically 10–20x cheaper per GB than NVMe-backed Atlas cluster storage.

- Exact rates vary by cloud provider and region — see the [MongoDB pricing page](https://www.mongodb.com/pricing) under "Online Archive".
- MongoDB does not add a markup on top of the underlying cloud object storage rate for archive storage itself.

### Query processing cost

- **$5.00 per TB** of data processed by Atlas Data Federation queries against the archive.
- **10 MB minimum** charged per query, even for queries returning small result sets.
- The 10 MB minimum makes very high query rates expensive even if individual queries are small.

Cost control mechanisms:
- Use `explain()` before running archive queries to estimate data processed.
- Always include leading partition fields in query predicates to minimize scan volume.
- Configure **query limits** in the federated database instance settings to cap per-query data processed.
- Set **billing alerts** in Atlas to catch unexpected spikes.

### Data transfer / egress

- No egress cost when querying from within the **same cloud + region** as the archive.
- Cross-region or cross-cloud queries incur cloud provider egress charges.
- Restoring data (`$merge` back to cluster) from the archive in the same region is generally free for inbound data.

### Cost comparison

| Scenario | Relative Cost |
|---|---|
| Hot data in M10+ cluster | Highest (NVMe storage + IOPS + cluster uptime) |
| Cold data in Online Archive (rarely queried) | Much lower — object storage rates only |
| Cold data in Online Archive (frequently queried) | Can exceed cluster cost at $5/TB query rate |
| Cold data in S3 Glacier/Archive tier (no federation) | Lowest storage cost, but hours-to-days rehydration latency |

**Rule of thumb**: Online Archive is cost-optimal for data accessed less than roughly once per week at the collection level. Data accessed more frequently than that may be cheaper to keep in the cluster.

---

## 9. Limitations

### Cluster tier

- **M10 minimum** — not available on Free (`M0`), Flex, or serverless instances.

### Collection types

- **Standard collections only** — time-series collections are not supported; use the `expireAfterSeconds` option on the time-series collection itself instead.
- **Capped collections**: not supported.
- **Views**: cannot create an archive rule on a view.

### Archive configuration limits

- Maximum **50 online archives per cluster**, with **20 active** at a time.
- One active archive per namespace.
- Cannot archive the same fields in the same collection with multiple rules.
- Partition fields are **immutable** once archiving begins.
- `archiveAfterDays` minimum is **7 days**; maximum is **9,215 days**.

### Federated query limitations

- **Read-only**: no write operations (insert, update, delete, replace) on archived data.
- **No `$lookup`** across federated stores — cannot join archived data with live data or other stores in a single pipeline stage.
- **No transactions** — multi-document ACID transactions are not supported on federated sources.
- **No change streams** on federated database instances.
- **No indexes** on federated data — query performance is entirely dependent on partition pruning.
- **30 concurrent queries** maximum per federated instance.
- **120 simultaneous connections** per region per federated instance.
- **6-hour query timeout**.
- **Cross-cloud federation not supported** — all stores in a federated instance must share the same cloud provider.
- `$unionWith` across federated sources has limited support — verify behavior for your specific pipeline.

### Partition field constraints

- Up to **2 partition fields**.
- Supported types: **date, string, numeric**. Arrays, objects, and booleans cannot be partition fields.
- For DATE rules, the `dateField` must be partition field 0.
- High-cardinality fields (e.g., `_id`, UUID) as partition fields create excessive small partitions, degrading query and aggregation performance.

### Archival throughput cap

- **2 GB per 5-minute cycle** hard cap. Collections with very high write rates may accumulate backlog faster than the archive can drain.

---

## 10. Anti-Patterns

### Archiving hot data

**Problem**: Archiving data that is still frequently queried incurs $5/TB query processing charges on every access. At high query rates this costs more than keeping the data in the live cluster.

**Detection**: Check if archive query processing costs are rising faster than cluster storage savings. Use `explain()` on typical queries to see bytes processed.

**Fix**: Increase `archiveAfterDays` so only genuinely cold data is archived. Use Atlas Query Profiler to confirm access patterns before choosing the cutoff.

---

### Missing or wrong partition fields

**Problem**: Omitting partition fields, or choosing fields that don't match query filters, causes every archive query to perform a full scan across all archived files.

**Example**:
```javascript
// Archive partitioned on: createdAt only
// This query scans the entire archive — extremely expensive
db.events.find({ userId: "u_abc123" })
```

**Fix**: Choose partition fields that exactly match the most common filter predicates. For multi-tenant data, `tenantId` or `customerId` as the second partition field often provides major cost and latency improvements.

---

### Treating TTL indexes as archival

**Problem**: TTL indexes permanently delete documents — they do not move data anywhere. Engineers sometimes confuse TTL with Online Archive.

**Fix**: Use TTL only for genuine data deletion with no recovery requirement. Use Online Archive when deleted data must remain queryable.

---

### Using `$lookup` on archived data

**Problem**: `$lookup` across federated stores (e.g., joining the archive with a live collection) is not supported in Atlas Data Federation.

**Example** (broken):
```javascript
// Fails on federated endpoint — $lookup not supported across stores
db.orders.aggregate([
  { $lookup: {
      from: "customers",   // live cluster collection
      localField: "customerId",
      foreignField: "_id",
      as: "customer"
  }}
])
```

**Fix**: Denormalize the data before archiving (embed the lookup fields), or perform the lookup on the live cluster before querying the archive, or restructure the pipeline to avoid cross-store joins.

---

### Not monitoring archive backlog

**Problem**: If the archive backlog grows undetected, the live cluster's storage is not being freed as expected, and the operational assumption that old data has been tiered may be incorrect.

**Fix**: Set up Atlas alerts on archival backlog metrics and review the Online Archive status panel regularly. If backlog is growing, switch to scheduled archiving during off-peak hours to allow the backlog to drain.

---

### Re-querying archive after restore without pausing

**Problem**: Running `$merge` to restore archived data while the archive rule is still active causes a race condition — restored documents may immediately be re-archived if they still match the archival criteria.

**Fix**: Always pause the online archive before beginning a restore operation. Resume or delete the archive only after the restored data has been verified.

---

### Expecting sub-millisecond latency on archive queries

**Problem**: Applications built for live cluster performance will break SLA expectations if they transparently query the combined (cluster + archive) endpoint without understanding the latency difference.

**Fix**: Route archive-dependent queries to the archive-only endpoint with appropriate timeouts and user-facing loading states. Never substitute the federated endpoint for the live cluster endpoint in latency-sensitive code paths.

---

### Using high-cardinality fields as partition fields

**Problem**: Using `_id` or a UUID as a partition field creates one partition per document. This massively increases the number of partition metadata lookups Atlas must perform, especially for aggregations and range queries.

**Fix**: Choose low-to-medium cardinality fields that group documents naturally: date bucket (year/month), region, tenant ID, status category. The goal is partitions containing many documents, not one document per partition.

---

## References

- [MongoDB Atlas Online Archive — Official Docs](https://www.mongodb.com/docs/atlas/online-archive/)
- [Configure Online Archive](https://www.mongodb.com/docs/atlas/online-archive/configure-online-archive/)
- [Manage Online Archives](https://www.mongodb.com/docs/atlas/online-archive/manage-online-archive/)
- [Restore Archived Data with $merge](https://www.mongodb.com/docs/atlas/online-archive/restore-archived-data-with-merge/)
- [Online Archive Costs](https://www.mongodb.com/docs/atlas/billing/online-archive/)
- [Atlas Data Federation Limitations](https://www.mongodb.com/docs/atlas/data-federation/supported-unsupported/limitations/)
- [Atlas Data Federation Overview](https://www.mongodb.com/docs/atlas/data-federation/adf-overview/overview/)
- [Enhancing Online Archive: Data Expiration and Scheduled Archiving](https://www.mongodb.com/blog/post/enhancing-atlas-online-archive-data-expiration-scheduled-archiving)
- [Atlas Data Federation and Online Archive on Azure (GA)](https://www.mongodb.com/blog/post/atlas-data-federation-online-archive-can-now-be-deployed-in-azure)
- [Atlas Online Archive: Efficiently Manage the Data Lifecycle (foojay.io)](https://foojay.io/today/atlas-online-archive-efficiently-manage-the-data-lifecycle/)
- [Evaluating Data Archiving Solutions for MongoDB (Medium)](https://medium.com/@agrim.kandoria/evaluating-data-archiving-solutions-for-historical-data-from-mongodb-dfce40266f63)
- [Terraform mongodbatlas_online_archive resource](https://registry.terraform.io/providers/mongodb/mongodbatlas/latest/docs/resources/online_archive)

## See Also

- [[mongodb-atlas-data-federation]] — the query engine that powers Online Archive; configure multi-source stores and databases
- [[mongodb-data-lifecycle]] — broader data lifecycle patterns: TTL, archival, expiration, schema evolution
- [[mongodb-cost-optimization]] — cluster right-sizing, storage optimization, and reducing Atlas spend
