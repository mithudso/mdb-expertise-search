<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-aggregation-pipeline` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-aggregation-pipeline
category: mongodb
tags: [mongodb, aggregation, pipeline, lookup, group, performance, window-functions, time-series, optimization]
version: 1.3.0
updated: 2026-05-29
description: |
  Expert reference for MongoDB aggregation pipelines.
  TRIGGER: building or reviewing any aggregation pipeline; $match/$group/$lookup/$project/$sort/$unwind stages;
  writing $lookup joins (equality or correlated subquery); building materialized views with $merge or $out;
  profiling with explain("executionStats"); implementing window functions ($setWindowFields, 5.0+);
  time-series gap-filling ($densify/$fill); $accumulator/$function custom logic; troubleshooting memory
  spills, allowDiskUse, scatter-gather on sharded clusters, or slow aggregation queries; any question
  about how to join, transform, aggregate, or summarise MongoDB data.
  SKIP: raw CRUD (find/insert/update/delete) without aggregation — use mongodb-expert or mongodb-developer;
  Atlas Search pipelines — use mongodb-atlas-search; Spark aggregation jobs — use mongodb-spark-connector;
  streaming aggregation — use mongodb-atlas-stream-processing; sharded-cluster scatter-gather tuning beyond
  pipeline shape — use mongodb-sharding.
when_to_use:
  - Writing an aggregation pipeline in any driver (Node.js, Python, Java, Go, C#)
  - Designing a $lookup join with equality or correlated sub-pipeline
  - Choosing between $out and $merge for materialized views
  - Profiling a slow aggregation with explain("executionStats")
  - Implementing window functions ($setWindowFields) or time-series gap-filling ($densify/$fill)
  - Troubleshooting OOM or allowDiskUse errors in aggregation
  - Understanding per-stage memory limits (100 MB) and when to use allowDiskUse
  - Optimizing pipeline stage order for index utilization
  - Using $accumulator or $function for custom aggregation logic
  - Aggregating data in time series collections
whenNotToUse:
  - Query tuning for simple find() without aggregation — use mongodb-query-performance
  - Schema design decisions without an aggregation component — use mongodb-schema-design
  - Spark connector pipelines processed as DataFrames — use mongodb-spark-connector
  - Atlas Stream Processing windowed pipelines — use mongodb-atlas-stream-processing
related_skills:
  - mongodb-aggregation-stages-deep
  - mongodb-query-performance
  - mongodb-indexes-deep
  - mongodb-spark-connector
  - mongodb-time-series
  - mongodb-schema-design
  - mongodb-expert
---

# MongoDB Aggregation Pipeline

## 1. Pipeline Stages Reference

Stages execute left-to-right; each stage receives the document stream from the previous
stage. Order matters enormously for performance (see Section 4).

| Stage | Purpose |
|---|---|
| `$match` | Filter documents — uses index when placed first |
| `$project` | Shape output: include, exclude, or compute fields |
| `$addFields` / `$set` | Add/overwrite fields without dropping others (`$set` is an alias) |
| `$unset` | Remove fields by name |
| `$group` | Aggregate by `_id` key — one doc per group |
| `$sort` | Order documents; uses index when directly after `$match` |
| `$limit` | Keep first N documents |
| `$skip` | Drop first N documents |
| `$count` | Return `{ <field>: <count> }` |
| `$unwind` | Deconstruct array into one document per element |
| `$lookup` | Left-outer join from another collection |
| `$replaceRoot` / `$replaceWith` | Promote an embedded document to the top level |
| `$sample` | Random reservoir sample of N documents |
| `$facet` | Run multiple sub-pipelines in parallel on the same input |
| `$bucket` | Group into manually-defined ranges |
| `$bucketAuto` | Group into N evenly-distributed buckets |
| `$merge` | Write results to a collection, merging with existing docs (4.2+) |
| `$out` | Write results to a collection, replacing it entirely |
| `$setWindowFields` | Window/analytical functions over a sorted partition (5.0+) |
| `$densify` | Insert synthetic docs to fill gaps in numeric/date sequences (5.1+) |
| `$fill` | Populate null/missing fields via interpolation or LOCF (5.3+) |

### Minimal examples

```js
// $group — total sales per category, filtered first
db.orders.aggregate([
  { $match: { status: "completed" } },                    // filter before grouping
  { $group: { _id: "$category", total: { $sum: "$amount" }, count: { $sum: 1 } } },
  { $sort: { total: -1 } }
])

// $unwind + $group — count tag occurrences (note: $match comes BEFORE $unwind)
db.posts.aggregate([
  { $match: { published: true } },                        // filter the parent docs first
  { $unwind: "$tags" },                                   // then explode the array
  { $group: { _id: "$tags", count: { $sum: 1 } } },
  { $sort: { count: -1 } },
  { $limit: 20 }
])

// $facet — category counts AND price-range buckets in one pass
db.products.aggregate([
  { $match: { inStock: true } },
  {
    $facet: {
      byCategory: [{ $group: { _id: "$category", n: { $sum: 1 } } }],
      byPriceBucket: [
        { $bucket: { groupBy: "$price", boundaries: [0, 25, 50, 100, 250], default: "250+" } }
      ]
    }
  }
])
```

---

## 2. $lookup Patterns

### 2a. Equality join (localField / foreignField)

MongoDB performs a hash-lookup on the foreign collection for each input document.
**Always index the `foreignField`** — without an index MongoDB scans the entire
foreign collection per input document (an O(N×M) table scan).

One important footgun: if the `as` field name already exists on the input document,
**it is silently overwritten**. Choose an `as` name that does not collide.

```js
// Join orders → customers on orders.customerId = customers._id
db.orders.aggregate([
  {
    $lookup: {
      from: "customers",
      localField: "customerId",
      foreignField: "_id",
      as: "customer"          // ⚠ silently overwrites if "customer" already exists
    }
  },
  // $lookup always returns an array; unwrap for 1-to-1 cardinality
  { $unwind: { path: "$customer", preserveNullAndEmptyArrays: true } }
])
```

Required index on the foreign side:

```js
db.customers.createIndex({ _id: 1 })   // _id index already exists
db.customers.createIndex({ email: 1 }) // create explicitly for any other join field
```

### 2b. Correlated sub-query (let + pipeline)

Use when you need filtering beyond a simple equality, or when joining on multiple fields.
`let` binds local document variables; reference them inside the sub-pipeline with `$$varName`.

```js
db.orders.aggregate([
  {
    $lookup: {
      from: "products",
      let: { orderSku: "$sku", orderQty: "$quantity" },
      pipeline: [
        // Both $match conditions can use the bound variables via $expr
        { $match: { $expr: {
            $and: [
              { $eq: ["$sku", "$$orderSku"] },
              { $gte: ["$stock", "$$orderQty"] }
            ]
        }}},
        { $project: { name: 1, price: 1, _id: 0 } }
      ],
      as: "product"
    }
  }
])
```

### 2c. Performance checklist for $lookup

- Index every `foreignField` (or the first field in the sub-pipeline `$match`).
- Place `$match` **inside** the sub-pipeline to push filtering before the join materialises.
- Avoid interleaving `$unwind` → `$lookup` → `$unwind`; chain all lookups, then unwind.
- On sharded clusters, joining a **sharded** foreign collection is supported (MongoDB 5.1+),
  but each input document fans out to every shard holding the foreign collection
  (scatter-gather). Co-locate the collections on the same shard key, or use Atlas Data
  Federation, to avoid the fan-out.

---

## 3. $merge and $out — Materialized Views

### 3a. $out — full collection replacement

`$out` atomically replaces the target collection after the full pipeline completes.
Use for nightly full rebuilds where brief stale reads are acceptable.

```js
db.events.aggregate([
  { $match: { ts: { $gte: ISODate("2025-01-01") } } },
  { $group: { _id: { $dateTrunc: { date: "$ts", unit: "day" } }, count: { $sum: 1 } } },
  { $out: "daily_event_summary" }
])
```

- Target must be in the **same database** unless using `{ db, coll }` object form (4.4+).
- Reads see the old collection until the atomic swap completes.

### 3b. $merge — incremental / upsert update

`$merge` (introduced in **4.2**) writes into an existing collection with
per-document conflict control. Ideal for incrementally updating materialized views.

```js
db.pageViews.aggregate([
  { $match: { date: { $gte: startOfToday } } },
  { $group: { _id: "$pageId", views: { $sum: 1 } } },
  {
    $merge: {
      into: "page_view_totals",
      on: "_id",                       // match key — must be unique and indexed
      whenMatched: "merge",            // merge new fields into existing doc
      whenNotMatched: "insert"         // insert pages seen for the first time
    }
  }
])
```

`whenMatched` options: `"replace"` | `"merge"` | `"keepExisting"` | `"fail"` | `[pipeline]`
`whenNotMatched` options: `"insert"` | `"discard"` | `"fail"`

The `[pipeline]` form for `whenMatched` allows complex update logic:

```js
whenMatched: [
  { $set: { views: { $add: ["$views", "$$new.views"] }, lastUpdated: "$$NOW" } }
]
```

### 3c. On-demand vs scheduled materialized views

```js
// On-demand: call after a bulk import or significant write batch
async function rebuildSummary(db) {
  await db.collection("raw_events").aggregate([
    { $group: { _id: "$userId", eventCount: { $sum: 1 } } },
    { $merge: { into: "user_event_summary", on: "_id",
                whenMatched: "replace", whenNotMatched: "insert" } }
  ]).toArray(); // .toArray() forces the cursor to drain and the $merge to execute
}

// Scheduled: Atlas Scheduled Trigger or a cron job calling the same pipeline
// exports = async function() { await db.collection("raw_events").aggregate([...]).toArray(); }
```

---

## 4. Pipeline Optimization

### 4a. Place $match (and $sort) early

The query planner can push a leading `$match` into the collection scan using an index.
A `$match` + `$sort` sharing an index prefix eliminates the in-memory sort stage entirely.

```js
// BAD — $project strips fields before the planner can use an index on ts
db.logs.aggregate([
  { $project: { userId: 1, ts: 1 } },
  { $match: { ts: { $gte: cutoff } } }
])

// GOOD — $match first; index on { ts: 1 } is used; $sort reuses the same index
db.logs.aggregate([
  { $match: { ts: { $gte: cutoff } } },
  { $sort: { ts: -1 } },
  { $project: { userId: 1, ts: 1 } }
])
```

### 4b. Project down early to shrink per-document size

Large documents amplify memory usage across every downstream stage.

```js
db.orders.aggregate([
  { $match: { status: "shipped" } },
  { $project: { customerId: 1, amount: 1, _id: 0 } }, // drop large embedded arrays immediately
  { $group: { _id: "$customerId", total: { $sum: "$amount" } } }
])
```

### 4c. explain("executionStats")

```js
// Node.js driver
const plan = await db.collection("orders").aggregate(pipeline).explain("executionStats");
console.log(JSON.stringify(plan, null, 2));

// mongosh
db.orders.explain("executionStats").aggregate(pipeline)

// Key fields:
// stages[0].$cursor.executionStats.totalDocsExamined  — should be close to nReturned
// stages[0].$cursor.executionStats.executionTimeMillis
// stages[N].memUsage                                  — signals a spill risk
// "COLLSCAN" in winningPlan                           — missing index
```

### 4d. Index strategies

```js
// Compound index covering $match + $sort prefix + projected field
db.orders.createIndex({ status: 1, ts: -1, customerId: 1 })

// Covered projection: every projected field is in the index → zero FETCH stage
db.orders.createIndex({ status: 1, amount: 1 })
db.orders.aggregate([
  { $match: { status: "completed" } },
  { $project: { amount: 1, _id: 0 } }
  // No document reads — pure index scan
])
```

---

## 5. Aggregation Expressions

### 5a. $expr in $match — field-to-field comparisons

`$expr` unlocks aggregation operators inside `$match`. An index can still be used when
the expression references an indexed field at the top level.

```js
// Orders where discount > 20% of amount
db.orders.aggregate([
  { $match: { $expr: { $gt: ["$discount", { $multiply: ["$amount", 0.20] }] } } }
])
```

### 5b. $cond and $switch — conditional expressions

```js
db.users.aggregate([
  {
    $addFields: {
      tier: {
        $switch: {
          branches: [
            { case: { $gte: ["$score", 90] }, then: "gold" },
            { case: { $gte: ["$score", 60] }, then: "silver" }
          ],
          default: "bronze"
        }
      },
      isVip: { $cond: { if: { $gte: ["$purchases", 10] }, then: true, else: false } }
    }
  }
])
```

### 5c. $let — intermediate variables within an expression

```js
db.products.aggregate([
  {
    $addFields: {
      netRevenue: {
        $let: {
          vars: {
            gross: { $multiply: ["$price", "$unitsSold"] },
            cogs:  { $multiply: ["$costPerUnit", "$unitsSold"] }
          },
          in: { $subtract: ["$$gross", "$$cogs"] }
        }
      }
    }
  }
])
```

### 5d. $accumulator — custom group-level accumulation

`$accumulator` (4.4+) lets you write a fully custom accumulator using JavaScript.
Use only when no native accumulator fits — it is significantly slower than built-ins
and requires `javascriptEnabled: true`.

```js
db.orders.aggregate([
  {
    $group: {
      _id: "$customerId",
      // Weighted average: sum(price*qty) / sum(qty)
      weightedAvgPrice: {
        $accumulator: {
          init: function() { return { totalValue: 0, totalQty: 0 }; },
          accumulate: function(state, price, qty) {
            return { totalValue: state.totalValue + price * qty,
                     totalQty:   state.totalQty + qty };
          },
          accumulateArgs: ["$price", "$quantity"],
          merge: function(s1, s2) {
            return { totalValue: s1.totalValue + s2.totalValue,
                     totalQty:   s1.totalQty + s2.totalQty };
          },
          finalize: function(state) {
            return state.totalQty === 0 ? 0 : state.totalValue / state.totalQty;
          },
          lang: "js"
        }
      }
    }
  }
])
```

### 5e. $function — inline custom JavaScript per document

Runs arbitrary JS inside mongod per document (not per group). Slower than `$accumulator`
for grouped work; avoid in hot paths.

```js
db.strings.aggregate([
  {
    $addFields: {
      slug: {
        $function: {
          body: function(name) { return name.toLowerCase().replace(/\s+/g, "-"); },
          args: ["$name"],
          lang: "js"
        }
      }
    }
  }
])
```

### 5f. Arithmetic and string operators (quick reference)

```js
// Arithmetic
{ $add: ["$a", "$b", 10] }        { $subtract: ["$revenue", "$cost"] }
{ $multiply: ["$price", "$qty"] } { $divide: ["$total", "$count"] }
{ $mod: ["$value", 7] }           { $round: ["$price", 2] }
{ $abs: "$delta" }                { $sqrt: "$variance" }
{ $pow: ["$base", 2] }            { $ln: "$value" }

// String
{ $concat: ["$firstName", " ", "$lastName"] }
{ $toUpper: "$status" }           { $toLower: "$email" }
{ $substr: ["$code", 0, 3] }      { $strLenCP: "$name" }
{ $split: ["$csv", ","] }
{ $regexFind:    { input: "$text", regex: /\d{4}/, options: "i" } }
{ $regexFindAll: { input: "$text", regex: /\w+/ } }
```

---

## 6. Window Functions ($setWindowFields)

Introduced in MongoDB 5.0. Analogous to SQL `OVER (PARTITION BY … ORDER BY …)`.
Does not reduce the document count (unlike `$group`).

### 6a. Basic syntax

```js
{
  $setWindowFields: {
    partitionBy: "$region",           // optional — omit for a single global partition
    sortBy: { date: 1 },             // required for most operators
    output: {
      <newField>: {
        <windowOperator>: <expression>,
        window: {
          documents: ["unbounded", "current"],  // row-offset bounds
          // OR
          range: [-6, 0], unit: "day"           // value/time-based bounds
        }
      }
    }
  }
}
```

### 6b. Running total, moving average, rank, lead/lag

```js
db.sales.aggregate([
  {
    $setWindowFields: {
      partitionBy: "$region",
      sortBy: { date: 1 },
      output: {
        runningTotal: {
          $sum: "$amount",
          window: { documents: ["unbounded", "current"] }
        },
        movingAvg7d: {
          $avg: "$amount",
          window: { range: [-6, 0], unit: "day" }
        },
        rank:       { $denseRank: {} },
        nextAmount: { $shift: { output: "$amount", by: 1, default: null } }
      }
    }
  }
])
```

### 6c. Window bound reference

| Bound | Meaning |
|---|---|
| `"unbounded"` | First (or last) document in the partition |
| `"current"` | The current document |
| `N` (integer) | N rows before (negative) or after (positive) current |

### 6d. Supported window operators

| Category | Operators |
|---|---|
| Accumulators | `$sum`, `$avg`, `$min`, `$max`, `$stdDevPop`, `$stdDevSamp`, `$count` |
| Ranking | `$rank`, `$denseRank`, `$documentNumber` |
| Navigation | `$first`, `$last`, `$shift` |
| Gap-filling | `$linearFill`, `$locf` |

---

## 7. Time Series Aggregation

### 7a. $densify — fill temporal gaps

`$densify` (5.1+) inserts synthetic documents for missing date/numeric values.
Combine with `$fill` (5.3+) to interpolate values into those synthetic docs.

```js
// bounds accepts:
//   [<lowerDate>, <upperDate>]  — explicit range (as below)
//   "full"                      — span the full range of values in the collection
//   "partition"                 — span the range within each partition independently
db.sensorReadings.aggregate([
  {
    $densify: {
      field: "ts",
      range: {
        step: 1,
        unit: "hour",
        bounds: [ISODate("2025-01-01T00:00:00Z"), ISODate("2025-01-02T00:00:00Z")]
      },
      partitionByFields: ["sensorId"]
    }
  },
  {
    $fill: {
      sortBy: { ts: 1 },
      partitionByFields: ["sensorId"],
      output: {
        temperature: { method: "linear" },  // linear interpolation between known values
        humidity:    { method: "locf" }     // last observation carried forward
      }
    }
  }
])
```

### 7b. Time bucketing with $dateTrunc

```js
db.events.aggregate([
  { $match: { ts: { $gte: startDate, $lt: endDate } } },
  {
    $group: {
      _id: {
        hour:   { $dateTrunc: { date: "$ts", unit: "hour" } },
        region: "$region"
      },
      eventCount: { $sum: 1 },
      avgLatency: { $avg: "$latencyMs" }
    }
  },
  { $sort: { "_id.hour": 1 } }
])
```

### 7c. Native time series collections

With `timeseries` collection type (5.0+), `$match` on `timeField` or `metaField`
pushes down into bucket metadata — MongoDB skips entire buckets without unpacking them.

```js
db.createCollection("weather", {
  timeseries: { timeField: "ts", metaField: "location", granularity: "minutes" }
})

db.weather.aggregate([
  { $match: { "location.city": "NYC", ts: { $gte: start, $lt: end } } },
  { $group: { _id: { $dateTrunc: { date: "$ts", unit: "hour" } }, avgTemp: { $avg: "$temp" } } }
])
```

---

## 8. Anti-Patterns

| Anti-Pattern | Severity | Problem | Fix |
|---|---|---|---|
| `$unwind` on large array before `$match` | **Critical** | Explodes N docs × array length before filtering | Move `$match` before `$unwind`, or use `$filter` expression to filter the array in place |
| Missing index on `$lookup` foreignField | **Critical** | Full collection scan per input document — O(N×M) | `createIndex({ foreignField: 1 })` on the joined collection |
| `$sort` without index on large collection | **High** | In-memory sort; aborts at 100 MB | Add compound index matching the `$sort` key order |
| `$group` with `$push`/`$addToSet` on high-cardinality data | **High** | Unbounded array growth → OOM | Use `$firstN`/`$lastN` accumulators, or paginate upstream |
| `$project` only at the end of a long pipeline | **High** | All intermediate stages carry full document weight | Project to minimal fields immediately after `$match` |
| Chained `$unwind` → `$lookup` → `$unwind` | **High** | N² document explosion | Flatten arrays after all lookups, not between them |
| Scatter-gather `$lookup` on sharded cluster | **Medium** | Every shard hit per input document | Co-locate on the same shard key, or use Atlas Data Federation |
| `$function`/`$accumulator` in hot paths | **Medium** | Single-threaded JS engine; 10-100× slower than native | Replace with native operators (`$regexFind`, `$split`, `$sum`, etc.) |
| `allowDiskUse: true` as a first resort | **Low** | Masks the real problem; adds I/O latency | Fix indexes/projections first; use `allowDiskUse` only as a safety net |
| `explain()` without `"executionStats"` | **Low** | `"queryPlanner"` verbosity hides actual row counts | Always use `explain("executionStats")` |

---

## 9. Memory Limits and allowDiskUse

### 9a. Default per-stage limit

Each pipeline **stage** is limited to **100 MB of RAM** (raised from 32 MB in 4.4).
Stages most likely to hit this: `$sort`, `$group`, `$bucket`, `$setWindowFields`.
When the limit is exceeded, MongoDB aborts with:

```
MongoServerError: $sort used too much RAM. Memory limit: 104857600 bytes.
Pass allowDiskUse:true to opt in to writing spill files.
```

### 9b. allowDiskUse

```js
// Node.js
const cursor = db.collection("bigData").aggregate(pipeline, { allowDiskUse: true });

// PyMongo
results = list(db.big_data.aggregate(pipeline, allowDiskUse=True))

// mongosh
db.bigData.aggregate(pipeline, { allowDiskUse: true })
```

Spilled data is written to `<dbPath>/_tmp`. Increases latency; fix root cause first.

Atlas tiers: `allowDiskUse` is **disabled on M0/M2/M5** (shared) tiers; requires M10+.

### 9c. Monitoring in-flight aggregations

```js
// $currentOp must be run against the admin database via adminCommand.
// It returns one doc per in-flight operation across all users.
db.adminCommand({
  aggregate: 1,          // "1" means run against admin, not a named collection
  pipeline: [
    { $currentOp: { allUsers: true } },
    { $match: { "command.pipeline": { $exists: true }, active: true } },
    { $project: { opid: 1, secs_running: 1, "command.aggregate": 1, memUsage: 1 } }
  ],
  cursor: {}
})
// secs_running + memUsage together tell you if a stage is about to spill.
// To kill a runaway op: db.killOp(<opid>)
```

---

## 10. Driver Examples — Node.js, Python, Java

### 10a. Node.js (mongodb driver 6.x)

```js
import { MongoClient } from "mongodb";

const client = new MongoClient(process.env.MONGODB_URI);
await client.connect();
const db = client.db("mydb");

const pipeline = [
  { $match: { status: "active", createdAt: { $gte: new Date("2024-01-01") } } },
  {
    $lookup: {
      from: "profiles",
      let: { uid: "$userId" },
      pipeline: [
        { $match: { $expr: { $eq: ["$_id", "$$uid"] } } },
        { $project: { name: 1, email: 1, _id: 0 } }
      ],
      as: "profile"
    }
  },
  { $unwind: { path: "$profile", preserveNullAndEmptyArrays: false } },
  { $project: { status: 1, createdAt: 1, "profile.name": 1, "profile.email": 1 } },
  { $sort: { createdAt: -1 } },
  { $limit: 100 }
];

// Stream results with for-await — avoids loading all docs into memory
const cursor = db.collection("users").aggregate(pipeline, { allowDiskUse: false });
for await (const doc of cursor) {
  console.log(doc);
}
await cursor.close();
await client.close();

// Explain plan
const plan = await db.collection("users").aggregate(pipeline).explain("executionStats");
console.log(JSON.stringify(plan.stages, null, 2));
```

### 10b. Python — PyMongo 4.x

```python
from pymongo import MongoClient
from datetime import datetime, timezone
import os

client = MongoClient(os.environ["MONGODB_URI"])
db = client["mydb"]

pipeline = [
    {"$match": {
        "status": "active",
        "createdAt": {"$gte": datetime(2024, 1, 1, tzinfo=timezone.utc)}
    }},
    {"$lookup": {
        "from": "profiles",
        "let": {"uid": "$userId"},
        "pipeline": [
            {"$match": {"$expr": {"$eq": ["$_id", "$$uid"]}}},
            {"$project": {"name": 1, "email": 1, "_id": 0}}
        ],
        "as": "profile"
    }},
    {"$unwind": {"path": "$profile", "preserveNullAndEmptyArrays": False}},
    {"$group": {"_id": "$profile.name", "total": {"$sum": 1}}},
    {"$sort": {"total": -1}},
    {"$limit": 50}
]

# Iterate lazily — don't wrap in list() for large result sets
for doc in db.users.aggregate(pipeline, allowDiskUse=True):
    print(doc)

# Explain
plan = db.command("aggregate", "users", pipeline=pipeline, explain=True, cursor={})
import pprint; pprint.pprint(plan)
```

### 10c. Java — MongoDB Driver 5.x (sync)

The raw `Document` API works but is verbose. The idiomatic 5.x approach uses the
`Aggregates` and `Filters` builder classes for type-safety and readability:

```java
import com.mongodb.client.*;
import com.mongodb.client.model.*;
import org.bson.Document;
import org.bson.conversions.Bson;
import java.util.Arrays;
import java.util.List;

public class AggregationExample {
    public static void main(String[] args) {
        try (MongoClient client = MongoClients.create(System.getenv("MONGODB_URI"))) {
            MongoCollection<Document> users =
                client.getDatabase("mydb").getCollection("users");

            // Builder-style pipeline (idiomatic Java driver 5.x)
            List<Bson> pipeline = Arrays.asList(
                Aggregates.match(Filters.eq("status", "active")),
                Aggregates.lookup(
                    "profiles",
                    List.of(new Variable<>("uid", "$userId")),
                    List.of(
                        Aggregates.match(Filters.expr(Filters.eq("$_id", "$$uid"))),
                        Aggregates.project(Projections.fields(
                            Projections.include("name", "email"),
                            Projections.excludeId()
                        ))
                    ),
                    "profile"
                ),
                Aggregates.unwind("$profile"),
                Aggregates.group("$profile.name", Accumulators.sum("total", 1)),
                Aggregates.sort(Sorts.descending("total")),
                Aggregates.limit(50)
            );

            try (MongoCursor<Document> cursor = users.aggregate(pipeline)
                    .allowDiskUse(true).iterator()) {
                while (cursor.hasNext()) System.out.println(cursor.next().toJson());
            }
        }
    }
}
```

---

## References

1. [Aggregation Pipeline Stages — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/mql/aggregation-stages/)
2. [$lookup (aggregation) — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/operator/aggregation/lookup/)
3. [$merge (aggregation stage) — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/operator/aggregation/merge/)
4. [$setWindowFields — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/operator/aggregation/setwindowfields/)
5. [$densify (aggregation stage) — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/operator/aggregation/densify/)
6. [$fill (aggregation stage) — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/operator/aggregation/fill/)
7. [Aggregation Pipeline Optimization — MongoDB Manual](https://www.mongodb.com/docs/manual/core/aggregation-pipeline-optimization/)
8. [Explain Results — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/explain-results/)
9. [Time Series Collections — MongoDB Manual](https://www.mongodb.com/docs/manual/core/timeseries-collections/)
10. [$accumulator — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/operator/aggregation/accumulator/)
11. [Aggregation with the Java Driver — MongoDB Docs](https://www.mongodb.com/docs/drivers/java/sync/current/builders/aggregates/)

---

## Time Series Collection Aggregation Notes

When running aggregation pipelines against **time series collections** (MongoDB 5.0+), the following behaviors differ from regular collections:

**Bucket-level pruning:** The query planner uses `control.min`/`control.max` metadata on internal buckets to skip entire buckets that don't match time-range or metaField predicates. Always place `$match` on the `metaField` and `timeField` as the **first stage** to maximise pruning.

**$densify / $fill on time series:** `$densify` `partitionByFields` supports dotted paths into `metaField` sub-fields but not measurement fields. For measurement field partitioning, use `$addFields` to promote the field before `$densify`.

**$setWindowFields performance:** Window functions do not push down through bucket storage. A tight `$match` before `$setWindowFields` is critical — without it, MongoDB unpacks and scans all buckets.

**$dateTrunc for downsampling:** Use `$dateTrunc` with `binSize` to downsample raw measurements into fixed time buckets (hourly/daily OHLCV, hourly averages). It is more efficient than `$dateToString` + `$group` for time-bucket aggregations.

**$out to time series (MongoDB 7.0.3+):** `$out` can write directly into a time series collection. `$merge` into a time series collection is not supported — use `$out` instead.

**Cannot use `distinct()` on time series** — use `$group` with a supporting metaField compound index instead.

For full time series aggregation patterns including IoT multi-sensor, financial OHLCV, gap-fill dashboards, and working set sizing, see `mongodb-time-series`.

---

## See also

- **`mongodb-aggregation-stages-deep`** — deep-dive reference for high-value stages: `$lookup` (equality, pipeline-with-let, Atlas Search), `$graphLookup` (recursive joins, tree/BOM patterns), `$facet` (16 MB ceiling, pagination idiom), `$bucket`/`$bucketAuto` (Renard / POWERSOF2 granularity), `$merge`/`$out` (materialized-view refresh, idempotency), `$setWindowFields` (rank, shift, derivative, integral), `$densify`/`$fill` (gap filling), `$unionWith`, plus 100 MB-per-stage memory limits, `allowDiskUse`, and `explain("executionStats")` spill detection.

- **`mongodb-operations-expert` (references/mongodb-spark-connector.md)** — when an aggregation pipeline runs as part of a Spark/Databricks job. The connector accepts the same MQL aggregation pipeline syntax via the `aggregation.pipeline` read option, and Catalyst pushes Spark filters/projections/limit down by prepending `$match`/`$project`/`$limit` stages to the user-supplied pipeline. Pipeline tuning rules from this skill (index-backed `$match` first, `$project` early, `allowDiskUse` for large `$sort`/`$group`) apply identically. Use the Spark connector reference when the pipeline result becomes a DataFrame for downstream Spark work; stay in this skill for pipelines that run only inside the Mongo cluster.
