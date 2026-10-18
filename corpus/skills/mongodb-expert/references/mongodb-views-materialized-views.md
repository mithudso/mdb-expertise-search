<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-views-materialized-views` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-views-materialized-views
category: mongodb
tags: [mongodb, views, materialized-views, createview, merge, out, aggregation, schema-design, security, performance, atlas-triggers]
version: 1.2.0
updated: 2026-05-29
description: |
  Expert reference for MongoDB standard views and on-demand materialized views.
  TRIGGER when the request involves db.createView(), MongoDB view definitions, the
  read-only view contract, view permissions and $$USER_ROLES projection filtering,
  $merge or $out as the persistence mechanism for materialized views, refresh
  scheduling via Atlas Triggers, indexed-view performance on the underlying
  collection vs disk-backed materialized views, denormalized $lookup-in-view
  patterns, time-series collections as internal materialized views, the
  materialized-view vs Atlas Stream Processing vs Atlas Charts caching choice,
  or avoiding the over-materialization / stale-view anti-patterns. Trigger
  phrases: "createView", "materialized view", "MongoDB view", "view on a
  collection", "$merge into another collection", "rollup collection",
  "summary collection", "refresh the summary", "pre-computed report",
  "denormalize for read", "hide a column from a role", "row-level filter via
  $$USER_ROLES". SKIP when the request is about UI views (React/Vue/HTML
  views), calendar views, log views, code review, GitHub PR views, file
  previews, IDE views, or any non-MongoDB use of the word "view".
when_to_use:
  - Creating or modifying a standard view with db.createView()
  - Using $$USER_ROLES for row-level or column-level security via a view
  - Designing an on-demand materialized view refresh pattern with $merge or $out
  - Scheduling materialized view refreshes via Atlas Triggers or cron
  - Choosing between standard view, materialized view, Atlas Stream Processing, and Atlas Charts cache
  - Debugging $merge identifier field requirements and unique index constraints
  - Building CQRS-style denormalized read models with $merge
  - Rolling up time-series data to a summary collection
  - Understanding $out atomic rename vs $merge incremental semantics
  - Implementing versioned/immutable snapshot materialized views
when_not_to_use:
  - React/Vue/HTML frontend views or any UI rendering
  - One-time aggregation for exploratory analysis (just use aggregate())
  - Sub-second freshness requirements — use Atlas Stream Processing or change streams
  - Atlas Charts caching or dashboard refresh intervals (Charts product config)
  - Atlas Online Archive or cold storage tiering — use mongodb-atlas-online-archive
  - Cross-cluster or S3 federated queries — use mongodb-atlas-data-federation
related_skills:
  - mongodb-aggregation-stages-deep
  - mongodb-time-series
  - mongodb-atlas-stream-processing
  - mongodb-atlas-triggers-functions
  - mongodb-schema-design
  - mongodb-indexes-deep
---

# MongoDB Views and On-Demand Materialized Views

> Two related but distinct features: a **standard view** is a saved aggregation pipeline,
> computed at query time, with no storage. An **on-demand materialized view** is the
> *result* of an aggregation, persisted to a real collection via `$merge` or `$out`,
> with its own indexes. Confusing them — or refreshing them at the wrong cadence — is
> the single most common source of pain.

## When to Use This Skill

**TRIGGER** when the request involves: `db.createView()`, MongoDB view definitions, the read-only view contract, `$$USER_ROLES` projection filtering, `$merge` or `$out` as the persistence mechanism for materialized views, refresh scheduling via Atlas Triggers, indexed-view performance on the underlying collection vs disk-backed materialized views, denormalized `$lookup`-in-view patterns, time-series collections as internal materialized views, the materialized-view vs Atlas Stream Processing vs Atlas Charts caching choice, or avoiding the over-materialization / stale-view anti-patterns.

**Trigger phrases:** "createView", "materialized view", "MongoDB view", "view on a collection", "$merge into another collection", "rollup collection", "summary collection", "refresh the summary", "pre-computed report", "denormalize for read", "hide a column from a role", "row-level filter via $$USER_ROLES".

**SKIP** when the request is about: UI views (React/Vue/HTML views), calendar views, log views in a monitoring tool, code review, GitHub PR views, file previews, IDE views, or any non-MongoDB use of the word "view".

## When NOT to Use This Skill

- The request is about **React/Vue component views, HTML views, or any frontend rendering** — that is UI territory, not MongoDB.
- The user only needs a **one-time aggregation** for exploratory analysis — a standard `aggregate()` call is simpler than a view.
- The workload requires **sub-second freshness** — use Atlas Stream Processing (`$emit` to a collection) or change streams with a driver-side worker. Materialized views scheduled every 5+ minutes are not appropriate for real-time requirements.
- The question is about **Atlas Charts caching or dashboard refresh intervals** — that is Charts product configuration, not view or materialized-view design.
- The question is fundamentally about **Atlas Online Archive** or cold storage tiering — that belongs with `mongodb-atlas-online-archive`.
- The team wants to **query across multiple Atlas clusters or S3 buckets** — that is Atlas Data Federation territory (`mongodb-atlas-data-federation`), not views.

## 1. Standard Views (`db.createView`)

### 1a. Definition and syntax

A standard view is a read-only virtual collection defined by an aggregation pipeline
over a source collection (or another view in the same database). The pipeline runs
**every time the view is queried** — nothing is stored on disk.

```javascript
// Helper form
db.createView(
  "<viewName>",
  "<sourceCollectionOrView>",
  [ <pipelineStages> ],
  { collation: { locale: "en", strength: 2 } }   // optional
)

// Equivalent low-level form
db.runCommand({
  create:    "<viewName>",
  viewOn:    "<source>",
  pipeline:  [ <stages> ],
  collation: { ... }
})

// Or via createCollection
db.createCollection("<viewName>", {
  viewOn:    "<source>",
  pipeline:  [ <stages> ],
  collation: { ... }
})
```

**Examples — three canonical shapes:**

```javascript
// 1. Filtered view — first-year students only
db.createView("firstYears", "students", [
  { $match: { year: 1 } }
]);

// 2. Projection view — PII-redacted employee listing
db.createView("employee_public", "employees", [
  { $match: { status: "active" } },
  { $project: { name: 1, email: 1, department: 1, ssn: 0, salary: 0 } }
]);

// 3. Joined view — denormalized sales (orders + inventory)
db.createView("sales", "orders", [
  { $lookup: {
      from: "inventory",
      localField: "prodId",
      foreignField: "prodId",
      as: "inventoryDocs"
  } },
  { $project: {
      _id: 0, prodId: 1, orderId: 1, numPurchased: 1,
      price: "$inventoryDocs.price"
  } },
  { $unwind: "$price" }
]);
```

### 1b. Modifying and dropping a view

Views cannot be **renamed**. To change a pipeline:

```javascript
// Option A — collMod (MongoDB 4.4+, preserves the name)
db.runCommand({
  collMod: "firstYears",
  viewOn:  "students",
  pipeline: [ { $match: { year: 1, gpa: { $gte: 3.0 } } } ]
});

// Option B — drop + recreate
db.firstYears.drop();
db.createView("firstYears", "students", [ { $match: { year: 1 } } ]);
```

### 1c. Read-only contract — every write fails

Writes against a view always error. There is no "instead-of trigger". The application
must target the underlying collection.

```javascript
db.firstYears.insertOne({ ... });   // ERROR: Namespace ... is a view
db.firstYears.updateOne(...);       // ERROR
db.firstYears.deleteOne(...);       // ERROR
db.firstYears.createIndex(...);     // ERROR — standard views cannot hold indexes
```

### 1d. Limitations and restrictions (memorize this list)

| Limitation | Detail |
| --- | --- |
| Same database only | View and source collection must share the same DB. No cross-DB views. |
| No `$out` / `$merge` in the pipeline | View definitions cannot terminate in write stages. |
| No `$out` / `$merge` in **embedded** pipelines either | Inside a `$lookup`, `$facet`, or `$unionWith` sub-pipeline of a view definition — also forbidden. |
| No indexes on the view itself | A standard view uses indexes of the underlying collection. You cannot `createIndex`, `dropIndex`, or `listIndexes` on the view. |
| No renaming | `renameCollection` against a view is unsupported. Use drop + recreate. |
| No `mapReduce` | The legacy `mapReduce` command is not supported on views. |
| `$text` only as the first stage | If the view's pipeline already starts with something else, you cannot push a `$text` query into the view at query time. |
| `find` projection operators | Queries against a view via `find()` cannot use `$`, `$elemMatch`, `$slice`, or `$meta` in the projection (rewrite the query as an aggregation). |
| Time-series source | Cannot create a standard view directly over a time-series collection in older releases; current releases allow it but with the same write restrictions. |
| Search/Vector Search indexes | Only views whose pipelines use a restricted set of stages (`$addFields`, `$set`, `$match` with `$expr`, `$project`) are eligible for Atlas Search indexes. |
| View definitions are not secret | The pipeline is stored in `system.views` and is visible to anyone with sufficient metadata access — do **not** embed credentials or sensitive constants. |
| 100 MB blocking stage limit | `$group` / `$sort` in the view pipeline are still subject to the in-memory limit; callers can opt into `allowDiskUse` on the read. |

### 1e. Indexed view performance — how the query planner sees it

A query against a standard view is rewritten into a combined pipeline:
`(view pipeline) + (caller's pipeline)`. The query planner then optimizes the whole
thing, pushing `$match` stages earlier when safe so that indexes on the underlying
collection can satisfy them.

Practical rules of thumb:

- **Index on the underlying collection on fields used by the view's `$match`.** If
  the view filters by `status` and queries filter by `tenantId`, you want a compound
  index `{ tenantId: 1, status: 1 }` on the source so both filters are index-served.
- **`$lookup` joins inside a view still need an index on the foreign key in the
  joined collection.** Without it the planner falls back to a collection scan per
  outer document.
- **Use `db.<view>.explain("executionStats").find(...)`** to confirm `IXSCAN` rather
  than `COLLSCAN`. The explain output flattens the view pipeline + caller pipeline.
- **A `$group` or `$sort` in the view pipeline is a blocking stage** that runs at
  query time on every read. If the read rate is high, that is a strong signal you
  want a materialized view instead.

### 1f. Sharded views and routing

When the source collection is sharded, the view's pipeline is broadcast to every
shard, results are merged at the mongos, and the caller's pipeline is then applied.
If the view's first `$match` does not include the shard key, every query is a
scatter-gather. Cluster the shard key into the view's `$match` whenever possible.

### 1g. Collation

A view inherits the source collection's collation by default. To override (for
case-insensitive name comparisons, etc.), pass `collation` at `createView` time.
**Once set, the view's collation is fixed** — to change it, drop and recreate.
Sub-pipelines (e.g., `$lookup`) inherit the view's collation; you cannot mix.

## 2. Views as a Security Boundary

The most under-used view feature is **role-based projection**. A view can:

- Filter rows by user role (`$$USER_ROLES`).
- Redact fields based on role.
- Be granted to a role that does **not** have `find` privilege on the underlying
  collection — the caller queries the view, the server reads the source on their
  behalf.

### 2a. Row-level filtering with `$$USER_ROLES`

`$$USER_ROLES` is available from **MongoDB 7.0+**. It is an array of objects, each with `_id`, `role`, and `db` fields (`_id` is the `"<db>.<role>"` identifier). The `$in` check below matches documents whose `tenantId` field equals the *name* of any role the authenticated user holds — so you must name Atlas roles after tenant IDs for this pattern to work (e.g., custom role `"acme"` grants access to all documents where `tenantId: "acme"`).

```javascript
// Tenants only see their own documents (MongoDB 7.0+)
// Requires a custom Atlas role named after each tenantId
db.createView("tenantOrders", "orders", [
  { $match: { $expr: { $in: ["$tenantId", "$$USER_ROLES.role"] } } }
]);
```

### 2b. Column-level redaction

```javascript
// Providers see diagnosisCode, billing-only roles do not
db.createView("medicalView", "medical", [
  { $set: {
      diagnosisCode: {
        $cond: {
          if:   { $in: ["Provider", "$$USER_ROLES.role"] },
          then: "$diagnosisCode",
          else: "$$REMOVE"
        }
      }
  } }
]);
```

### 2c. Permission model

| To do this | You need |
| --- | --- |
| `createView` | `createCollection` on the database **and** `find` on every collection or view the pipeline references |
| Query a view | `find` on the **view** namespace only — no privilege required on the source collection |
| Drop a view | `dropCollection` on the view namespace |

The built-in `readWrite` role covers the create path; the built-in `read` role covers
the query path. To grant view access **without** source access, create a custom role
with `find` privilege only on the view.

## 3. On-Demand Materialized Views (`$merge` / `$out`)

An on-demand materialized view is a normal collection whose contents are produced by
an aggregation that ends in `$merge` or `$out`. You schedule the refresh; reads hit
disk; indexes work normally.

### 3a. When to materialize (decision rules)

Materialize if any of the following is true:

- The view's pipeline contains a `$group` or `$sort` that runs on every read.
- The read rate is much higher than the data-change rate (read-mostly).
- The pipeline joins three or more collections with `$lookup`.
- The view feeds dashboards or scheduled reports where freshness can lag minutes/hours.
- You need **indexes on the result** (only materialized views support direct indexes).

Do **not** materialize if:

- Reads must reflect every write immediately (use a standard view or query directly).
- The result set churns faster than you can refresh.
- The source data is small enough that recomputation is cheap.

### 3b. `$merge` — incremental, sharded-safe persistence (preferred)

```javascript
{
  $merge: {
    into:           <collection> | { db: <db>, coll: <collection> },
    on:             <identifierField> | [ <fieldA>, <fieldB>, ... ],
    let:            { <var>: <expr>, ... },
    whenMatched:    "merge" | "replace" | "keepExisting" | "fail" | [ <updatePipeline> ],
    whenNotMatched: "insert" | "discard" | "fail"
  }
}
```

Key semantics:

- **`into`** creates the target collection if it does not exist (replica set /
  standalone only — on sharded clusters the target database must already exist).
- **`on`** defaults to `_id`. Any other field set requires a **unique** (and
  non-partial) index that matches the aggregation's collation. `on` may be a
  single field or a list of fields, but a field named in `on` cannot hold an
  array value.
- **`whenMatched: "merge"`** is the default — fields on the new doc overwrite,
  others are kept.
- **`whenMatched: [pipeline]`** allows custom update logic referencing the existing
  doc as `$$ROOT` and the new doc as `$$new`. Allowed stages inside this pipeline:
  `$addFields`, `$set`, `$project`, `$unset`, `$replaceRoot`, `$replaceWith`.
- **Must be the final stage** of the pipeline. No transactions, no nested-pipeline
  (`$lookup`, `$facet`, `$unionWith`) usage, no `linearizable` read concern, no
  appearance inside view definitions.

### 3c. `$out` — atomic full-replace (simpler, more restrictive)

```javascript
{ $out: "<collection>" }
{ $out: { db: "<db>", coll: "<collection>" } }
{ $out: { db: "<db>", coll: "<ts>", timeseries: { timeField: "ts", metaField: "meta", granularity: "minutes" } } }   // MongoDB 7.0.3+
```

- Replaces the entire target collection **atomically** (writes to a temp collection,
  then `renameCollection` with `dropTarget: true`). Existing indexes are recreated.
- **Cannot output to a sharded collection.** Use `$merge`.
- **Cannot output to a capped collection.**
- Cannot run in a transaction. Cannot appear in a view definition.
- If the target already has an Atlas Search index, that index must be dropped and
  recreated after the `$out`.

### 3d. Choosing between `$merge` and `$out`

| Need | Stage |
| --- | --- |
| Incremental updates / accumulate-over-time | `$merge` |
| Sharded target collection | `$merge` |
| Time-series target collection | `$out` (7.0.3+) |
| Full rebuild on every refresh, target fits in time budget | `$out` |
| Custom update logic per row | `$merge` with pipeline-form `whenMatched` |
| Want change streams to fire on the output | `$merge` (insert/update); `$out` rewrites the whole collection and breaks change streams |
| Want to read the *previous* materialized version while the new one builds | `$out` (atomic rename) |

### 3e. Canonical incremental-refresh pattern

```javascript
function refreshMonthlySales(sinceDate) {
  return db.bakesales.aggregate([
    { $match: { date: { $gte: sinceDate } } },
    { $group: {
        _id:            { $dateToString: { format: "%Y-%m", date: "$date" } },
        sales_quantity: { $sum: "$quantity" },
        sales_amount:   { $sum: "$amount" }
    } },
    { $merge: {
        into:           "monthly_bakesales",
        on:             "_id",
        whenMatched:    "replace",
        whenNotMatched: "insert"
    } }
  ]);
}

// First run — recompute everything
refreshMonthlySales(new ISODate("1970-01-01"));

// Hourly refresh — only recompute the *current* month and let
// whenMatched: "replace" overwrite the open bucket
refreshMonthlySales(new ISODate("2026-05-01"));
```

### 3f. Counter-merge pattern (running totals)

When you need to **add to** rather than **replace** an aggregate:

```javascript
db.events.aggregate([
  { $match: { ts: { $gte: lastRunStart, $lt: lastRunEnd } } },
  { $group: {
      _id:   { $dateToString: { format: "%Y-%m-%d", date: "$ts" } },
      count: { $sum: 1 }
  } },
  { $merge: {
      into: "daily_event_counts",
      on:   "_id",
      whenMatched: [
        { $set: { count: { $add: ["$count", "$$new.count"] }, updatedAt: "$$NOW" } }
      ],
      whenNotMatched: "insert"
  } }
]);
```

Caveat: only safe when each batch is processed **exactly once**. If your scheduler
can run a window twice (e.g., catchup after Atlas Trigger downtime), persist a
high-water mark per bucket and use it to make refreshes idempotent — or fall back
to `whenMatched: "replace"` and recompute the window from scratch.

### 3g. Sharded materialized view target

To `$merge` into a sharded collection, the `on` identifier must contain every shard
key field, and a matching unique index must exist:

```javascript
db.moviesByYearAndRating.createIndex(
  { rated: 1, year: 1 },
  { unique: true }
);

db.movies.aggregate([
  { $group: {
      _id:        { rated: "$rated", year: "$year" },
      movieCount: { $sum: 1 }
  } },
  { $project: { _id: 0, rated: "$_id.rated", year: "$_id.year", movieCount: 1 } },
  { $merge: {
      into: "moviesByYearAndRating",
      on:   ["rated", "year"],
      whenMatched: "replace",
      whenNotMatched: "insert"
  } }
]);
```

### 3h. Indexes on materialized views

Because a materialized view is a normal collection:

```javascript
db.monthly_bakesales.createIndex({ sales_amount: -1 });
db.monthly_bakesales.createIndex({ "_id": 1, sales_quantity: -1 });
```

Create indexes that match the **read pattern** of the application that reads the view,
not the refresh pipeline. The refresh path doesn't need them (it's an `$merge` write).

## 4. Refreshing Materialized Views — Scheduling

### 4a. Atlas Scheduled Triggers (Atlas-only, no infrastructure)

```javascript
// In an Atlas App Services Function
exports = async function() {
  const db = context.services.get("mongodb-atlas").db("store");

  return db.collection("orders").aggregate([
    { $match: { orderDate: { $gte: yesterdayMorningUTC(), $lt: thisMorningUTC() } } },
    { $unwind: "$items" },
    { $group: {
        _id:               "$orderDate",
        numItemsOrdered:   { $sum: "$items.qty" },
        totalSales:        { $sum: "$items.price" },
        averageOrderSales: { $avg: "$items.price" }
    } },
    { $addFields: { refreshedAt: new Date() } },
    { $merge: { into: "daily_reports", whenMatched: "replace", whenNotMatched: "insert" } }
  ]).toArray();
};
```

Trigger configuration (`/triggers/refresh_daily_reports.json`):

```json
{
  "type": "SCHEDULED",
  "name": "refresh_daily_reports",
  "function_name": "refreshDailyReports",
  "config": { "schedule": "0 2 * * *" },
  "skip_catchup_event": true,
  "disabled": false
}
```

CRON expressions run in **UTC** and use the standard 5-field syntax:
`minute hour dayOfMonth month dayOfWeek`. Always think about timezone shift —
"2 AM UTC" is "6 PM PT", not 2 AM local.

### 4b. Self-hosted alternatives

| Mechanism | Notes |
| --- | --- |
| `cron` / `systemd` timers on a worker box running a `mongosh --eval` or driver script | Simplest; you own retries/alerting. |
| Kubernetes `CronJob` running a Node/Python container | Works for multi-tenant fleets; horizontal-scale by sharding refresh windows. |
| Application-level scheduler (e.g., BullMQ, Quartz, Celery beat) | Use when the refresh is *part of* an application transaction (e.g., refresh on order-completed event). |
| MongoDB Atlas Stream Processing | For **near-real-time** materialized views — see §6. |
| Change streams + driver-side worker | Consume change events from the source, run an incremental `$merge`. Suitable when refresh latency must be < 1s and ASP is not available. |

### 4c. Refresh-cadence cheat sheet

| Pattern | Cadence | Mechanism |
| --- | --- | --- |
| Daily reporting | Once / day, off-peak | Atlas Scheduled Trigger nightly |
| Hourly dashboards | Every 1h or 30m | Atlas Trigger, incremental window |
| 5-minute leaderboards | `*/5 * * * *` | Atlas Trigger; consider ASP if traffic warrants |
| Near-real-time (<5s) | Continuous | Atlas Stream Processing with `$merge` (§6) |
| On-event refresh | On write | Change streams → worker → `$merge` |

### 4d. Versioned (immutable-snapshot) materialized views

Downstream consumers — BI, ML training jobs, regulators — often need a *stable*
snapshot, not the latest refresh. Pattern:

```javascript
const version = `2026-05-28T02:00:00Z`;

db.orders.aggregate([
  /* ... aggregate ... */
  { $addFields: { _version: version } },
  { $merge: {
      into: "daily_reports_versioned",
      on:   ["_id", "_version"],
      whenMatched:    "fail",          // an entry for this (_id, _version) must not exist
      whenNotMatched: "insert"
  } }
]);
```

Readers query `db.daily_reports_versioned.find({ _version: "<frozen-version>" })`.
TTL or a retention job purges old versions. Use `whenMatched: "fail"` defensively —
it catches double-refresh bugs immediately rather than silently corrupting history.

## 5. Time-Series Collections — Internal Materialized Views

MongoDB time-series collections are documented as **"writable non-materialized views
backed by an internal collection"**. The internal bucketing collection is hidden;
you read and write the time-series namespace as if it were a normal collection.

Practical implications:

- **A standard view *over* a time-series collection is fine** — useful for filtering
  by `metaField` or projecting `measurements`. Same write-forbidden rule still
  applies.
- **`$out` to a time-series collection** is supported from **MongoDB 7.0.3+** with
  the `timeseries:` option in `$out` (§3c). `$merge` is **not** supported into a
  time-series target.
- **Updates to time-series documents** can only match on `metaField`. This is a
  property of the source, not of the view over it — wrapping a time-series source
  in a view does not unlock additional update freedom.
- **Automatic compound index on `(metaField, timeField)`** (MongoDB 6.3+) means
  views over time-series often already have a useful index without extra work.
- **Sharding caveat (8.0+)**: shard keys containing `timeField` are deprecated;
  zone sharding is unsupported. Design materialized rollups *out of* the
  time-series collection into a normal sharded collection when you need flexible
  shard-key choice.

Typical pattern — roll up high-frequency sensor data into a smaller normal collection:

```javascript
db.sensor_raw.aggregate([
  { $match: { ts: { $gte: lastHour } } },
  { $group: {
      _id:    { sensorId: "$meta.sensorId", hour: { $dateTrunc: { date: "$ts", unit: "hour" } } },
      avgTemp: { $avg: "$temp" },
      maxTemp: { $max: "$temp" },
      minTemp: { $min: "$temp" },
      n:       { $sum: 1 }
  } },
  { $merge: {
      into: "sensor_hourly",
      on:   "_id",
      whenMatched:    "replace",
      whenNotMatched: "insert"
  } }
]);
```

## 6. Decision Matrix — Views vs Materialized Views vs Stream Processing vs Charts Cache

| Requirement | Standard view | On-demand materialized view | Atlas Stream Processing materialized view | Atlas Charts cached data |
| --- | --- | --- | --- | --- |
| **Storage** | None (computed on read) | Full result on disk | Full result on disk | Chart-internal cache (managed) |
| **Freshness** | Always live | Stale by refresh interval | Sub-second / event-driven | Per-chart refresh interval |
| **Indexes** | Inherit source | Direct indexes | Direct indexes | N/A (caller is Charts) |
| **Write API** | None (read-only) | Yes (via refresh pipeline) | Yes (continuous `$merge`) | None (Charts owns it) |
| **Setup cost** | Trivial | Trivial + scheduler | Higher (ASP instance, connection registry) | Trivial (UI checkbox) |
| **Operational cost** | None | Compute on refresh | Continuous compute | Cached fetch on chart load |
| **Best for** | Security, simple shaping, low read rate | Read-mostly aggregates, reports, denormalized read models | CQRS, real-time dashboards, microservice fan-out | Dashboards specifically built in Charts |
| **Worst for** | High read rate of `$group`/`$sort` pipelines | Sub-minute freshness | Simple low-traffic rollups | Anything outside a chart UI |

The cross-skill picks: prefer **standard view** for security and shaping; **on-demand
materialized view** for reporting and read-mostly aggregates; **Atlas Stream
Processing** for real-time CQRS; **Atlas Charts cache** only when the consumer is
literally a chart.

## 7. Common Use Cases — Recipes

### 7a. PII redaction (compliance-friendly read path)

Application code reads `customer_public`, never `customers`. Auditors verify role
binding: `read` on `customer_public` granted broadly, `read` on `customers` granted
only to a small group.

```javascript
db.createView("customer_public", "customers", [
  { $project: { ssn: 0, dob: 0, payment_methods: 0 } }
]);
```

### 7b. Multi-tenant row filter

```javascript
db.createView("tenant_invoices", "invoices", [
  { $match: { $expr: { $in: ["$tenantId", "$$USER_ROLES.role"] } } }
]);
```

Grant tenant users a custom role whose `roles[].role` matches their tenant ID. The
view filters server-side; no chance of the client forgetting a `WHERE tenant_id =`.

### 7c. Denormalized read model (CQRS-lite, materialized)

```javascript
// Refresh every 5 minutes via Atlas Trigger
db.orders.aggregate([
  { $lookup: { from: "customers", localField: "customerId", foreignField: "_id", as: "customer" } },
  { $lookup: { from: "items",     localField: "itemIds",   foreignField: "_id", as: "items" } },
  { $project: { /* flatten what reads need */ } },
  { $merge: { into: "orders_read_model", whenMatched: "replace", whenNotMatched: "insert" } }
]);
db.orders_read_model.createIndex({ customerId: 1, createdAt: -1 });
```

### 7d. Pre-aggregated rollup for dashboards

```javascript
db.events.aggregate([
  { $match: { ts: { $gte: today } } },
  { $group: { _id: { type: "$type", hour: { $dateTrunc: { date: "$ts", unit: "hour" } } }, n: { $sum: 1 } } },
  { $merge: { into: "events_hourly", whenMatched: "replace", whenNotMatched: "insert" } }
]);
```

### 7e. View over a view (composition)

A view can read from another view in the same database — useful for layering
projection-redaction over filter-views, etc. Watch collation: a child view inherits
its parent's collation and cannot override it.

```javascript
db.createView("active_customers",       "customers",        [ { $match: { status: "active" } } ]);
db.createView("active_customer_public", "active_customers", [ { $project: { ssn: 0, dob: 0 } } ]);
```

## 8. Anti-Patterns

| Anti-pattern | Why it bites | Fix |
| --- | --- | --- |
| **Over-materialization** | Every aggregation becomes its own collection; storage and refresh cost explode. | Materialize only when reads outpace writes *and* the query is expensive. Otherwise a standard view is enough. |
| **Stale view never refreshed** | A materialized view diverges from the source; consumers ship wrong numbers. | Each materialized view MUST have a documented refresh cadence and a monitor. Store `refreshedAt` in every doc and alert when it goes stale. |
| **Refreshing too often** | Every refresh is a full re-scan; you saturate the primary. | Process only the changed window (`$match` on a time field, use a high-water mark). |
| **Materialized view as a transactional read path** | The view lags reality; the user reads their own write and doesn't see it. | Either read the source directly for write-followed-by-read, or move to Atlas Stream Processing for sub-second freshness. |
| **`$out` to a busy target** | `$out` does a `dropTarget: true` rename — drops Atlas Search indexes, breaks change-stream consumers, briefly invalidates cached cursors. | Use `$merge` with `whenMatched: "replace"` instead — no full-collection rebuild. Note `$merge` keeps target docs absent from the new result, whereas `$out` drops them; if you need those removed, keep `$out` or delete stale keys explicitly. |
| **`$merge` into a sharded target with a non-matching `on`** | Pipeline fails or, worse, writes to the wrong shard. | The `on` set MUST include every shard key field, backed by a unique index with the same collation. |
| **No unique index for non-`_id` `on`** | `$merge` fails with `IllegalOperation`. | `createIndex(..., { unique: true })` before the first `$merge` run. |
| **Sensitive constants in view definitions** | `system.views` is readable; pipelines may leak secrets. | Never put API keys or salts in `pipeline`. Reference data via `$lookup` from a collection that has its own ACL. |
| **`$lookup` in a view without a foreign-key index** | Every read does a collection scan on the joined collection. | Index the `foreignField` on the joined collection. |
| **Standard view with a heavy `$group`** | Every read recomputes the group — fine at 1 QPS, ruinous at 100 QPS. | Materialize it. The break-even is roughly where (read rate × pipeline cost) > (refresh interval cost). |
| **Time-series source confused for a materialized view** | Engineers try `$merge` into a time-series target and the pipeline fails. | Use `$out` with the `timeseries:` option (7.0.3+); `$merge` is not supported into time-series. |
| **Renaming a view** | Unsupported — `renameCollection` against a view errors. | Drop and recreate. Update consumers in the same change. |
| **Forgetting refresh skew across daylight saving** | Cron in UTC moves relative to local-time business hours twice a year. | Always document schedules in UTC and validate with an "expected next-run-at" comment alongside the cron expression. |

## 9. Operational Checklist (Pre-Production)

Before declaring a view or materialized view production-ready, confirm:

1. **Naming convention** — prefix indicates kind: e.g., `v_customer_public` for
   standard views, `m_orders_daily` for materialized views. Consumers can tell at
   a glance which guarantees apply.
2. **Source-of-truth comment** — store a comment on the collection metadata
   (`db.runCommand({ collMod: <ns>, ... })` or in the deployment repo) describing
   refresh cadence, owner, retention, and downstream consumers.
3. **Refresh monitor** — every materialized view emits `refreshedAt`. An alert
   fires when `now() - refreshedAt > 2 * expected_interval`.
4. **Index plan** — for materialized views, `db.<view>.getIndexes()` matches the
   queries the application actually issues, verified via `explain`.
5. **Backfill plan** — first refresh from `1970-01-01` (or the earliest source
   data). Confirm runtime is bounded; if it isn't, refactor into chunks before
   shipping.
6. **Failure mode** — what happens if the refresh is missed for 24h? 7 days?
   Tested in staging.
7. **Sharded target?** — unique index on the shard-key columns confirmed; `on`
   set in `$merge` matches.
8. **Security** — for views used as a security boundary, the read role does **not**
   have `find` on the source collection. Verified with the actual role bound to a
   test user.
9. **Atlas Trigger** — `skip_catchup_event: true` if you don't want a queue of
   missed refreshes to fire when the trigger is re-enabled.
10. **Idempotency** — the refresh pipeline produces the same output for the same
    input window twice in a row.

## 10. Quick Reference

```javascript
// CREATE standard view
db.createView(<name>, <source>, [<pipeline>], { collation });

// MODIFY standard view (preserve name)
db.runCommand({ collMod: <name>, viewOn: <source>, pipeline: [...] });

// DROP view
db.<name>.drop();

// CREATE materialized view (one-shot)
db.<source>.aggregate([
  <stages...>,
  { $merge: { into: <name>, on: <id>, whenMatched: "replace", whenNotMatched: "insert" } }
]);

// CREATE materialized view via $out (full rebuild)
db.<source>.aggregate([
  <stages...>,
  { $out: <name> }
]);

// INDEX on materialized view (NOT supported on standard view)
db.<name>.createIndex({ ... });

// EXPLAIN against a view (combined pipeline + caller pipeline)
db.<name>.explain("executionStats").aggregate([ ... ]);

// LIST views
db.getCollectionInfos({ type: "view" });

// PERMISSION model
//   create: createCollection + find on every referenced source
//   read:   find on view namespace only (no source privilege needed)
//   drop:   dropCollection on view namespace
```

## Sources

1. [MongoDB Manual — Views](https://www.mongodb.com/docs/manual/core/views/)
2. [MongoDB Manual — On-Demand Materialized Views](https://www.mongodb.com/docs/manual/core/materialized-views/)
3. [MongoDB Manual — `db.createView()` reference](https://www.mongodb.com/docs/manual/reference/method/db.createView/)
4. [MongoDB Manual — `$merge` aggregation stage](https://www.mongodb.com/docs/manual/reference/operator/aggregation/merge/)
5. [MongoDB Manual — `$out` aggregation stage](https://www.mongodb.com/docs/manual/reference/operator/aggregation/out/)
6. [MongoDB Manual — Create and Query a View](https://www.mongodb.com/docs/manual/core/views/create-view/)
7. [MongoDB Manual — Use a View to Join Two Collections](https://www.mongodb.com/docs/manual/core/views/join-collections-with-view/)
8. [MongoDB Manual — Time Series Collections](https://www.mongodb.com/docs/manual/core/timeseries-collections/)
9. [MongoDB Atlas — Scheduled Triggers](https://www.mongodb.com/docs/atlas/atlas-ui/triggers/scheduled-triggers/)
10. [MongoDB Blog — Real-Time Materialized Views with Atlas Stream Processing](https://www.mongodb.com/company/blog/technical/real-time-materialized-views-with-atlas-stream-processing)
11. [MongoDB Manual — Schema Design Anti-Patterns](https://www.mongodb.com/docs/manual/data-modeling/design-antipatterns/)
12. [Mydbops — MongoDB View vs Materialized View](https://www.mydbops.com/blog/view-and-materialized-view-in-mongodb)

---

## See also

- **`mongodb-aggregation-stages-deep`** — full `$merge` / `$out` reference: `whenMatched` variants, `$$new`, idempotency rules, same-collection-`$merge` infinite-loop pitfall, and sharded-target requirements.
- **`mongodb-time-series`** — time-series collection internals, bucketing, `metaField` cardinality, and downsampling patterns that complement or replace materialized rollups.
- **`mongodb-atlas-stream-processing`** — for near-real-time materialized views via continuous `$emit`; use when refresh latency must be < 5 seconds.
- **`mongodb-atlas-triggers-functions`** — scheduled Atlas Trigger setup, CRON syntax, Function runtime, and retry behavior for refresh scheduling.
- **`mongodb-schema-design`** — when to pre-compute vs. compute on read; the extended reference pattern and subset pattern as alternatives to full materialization.
- **`mongodb-indexes-deep`** — indexing the read path on materialized view collections; compound index design for the `on` field in `$merge`.
