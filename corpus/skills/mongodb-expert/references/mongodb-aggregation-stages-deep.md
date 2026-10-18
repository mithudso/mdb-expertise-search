<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-aggregation-stages-deep` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-aggregation-stages-deep
description: Deep reference for MongoDB aggregation stages — $lookup, $graphLookup, $facet, $bucket/$bucketAuto, $merge/$out, $setWindowFields, $densify/$fill, $unionWith. Use when joining collections, traversing hierarchies, building materialized views, running window functions, gap-filling time-series, diagnosing 100MB-per-stage memory limits and allowDiskUse spills, or comparing $lookup vs denormalization and $out vs $merge.
category: mongodb
version: 1.0.0
---

# MongoDB Aggregation Stages — Deep Reference

This skill is the deep-dive companion to `mongodb-aggregation-pipeline`. It
covers the highest-impact stages where most aggregation bugs and performance
problems hide: cross-collection joins, recursive graph traversal, parallel
facets, materialized-view writes, window functions, and time-series gap
filling. Each section gives syntax, index/memory requirements, working
examples, and the trade-offs that decide whether you should reach for the
stage at all.

Coverage map:

| Stage                       | Purpose                                                | Minimum version |
|-----------------------------|--------------------------------------------------------|-----------------|
| `$lookup`                   | Left outer join — equality, pipeline, sub-search       | 3.2 (pipeline 3.6, search 6.0) |
| `$graphLookup`              | Recursive traversal of a single collection             | 3.4             |
| `$facet`                    | Parallel sub-pipelines over the same input             | 3.4             |
| `$bucket` / `$bucketAuto`   | Explicit / automatic histogram bucketing               | 3.4             |
| `$merge`                    | Insert / update / upsert into any collection           | 4.2             |
| `$out`                      | Replace a target collection wholesale                  | 2.6 (cannot target a sharded collection) |
| `$setWindowFields`          | SQL-style window functions over partitions             | 5.0             |
| `$densify`                  | Insert synthetic documents to close numeric/time gaps  | 5.1             |
| `$fill`                     | Populate null/missing values (constant, linear, LOCF)  | 5.3             |
| `$unionWith`                | UNION ALL across collections / pipelines               | 4.4             |

When to use this skill:

- Designing a pipeline that joins collections, traverses a hierarchy, runs
  parallel facets, materializes a view, computes window functions, or
  fills time-series gaps.
- Diagnosing stage-level memory limits, disk spills, `BSONObjectTooLarge`
  errors, or `$lookup` NestedLoopJoin warnings in `explain` output.
- Choosing between `$lookup` vs denormalization, `$out` vs `$merge`, or
  `$bucket` vs `$bucketAuto`.

When NOT to use this skill:

- Basic pipeline mechanics (`$match`, `$project`, `$group`, `$sort`,
  `$addFields`, `$unwind`) — see `mongodb-aggregation-pipeline`.
- Index design and query planner reads — see `mongodb-indexes-deep` and
  `mongodb-query-performance`.
- Atlas-specific features (Search, Data Federation, Online Archive,
  Charts) outside aggregation — see the corresponding `mongodb-atlas-*`
  skills.
- Document-level schema modeling decisions unrelated to a specific
  aggregation stage — see `mongodb-schema-design`.

Cross-link reading list:

- `mongodb-aggregation-pipeline` — pipeline mental model, optimizer rewrites,
  `$match`/`$project`/`$group`/`$sort` basics.
- `mongodb-query-performance` — `$lookup` join tuning, equality vs hash join
  hints, INDEXED vs NLJ in `explain` output.
- `mongodb-schema-design` — denormalize-vs-`$lookup` decision tree.
- `mongodb-views-materialized-views` — on-demand materialized views via
  `$merge`, `db.createView` semantics.
- `mongodb-time-series` — when to use `$densify` and `$fill` with bucketed
  time-series collections.
- `mongodb-indexes-deep` — covering indexes for the `foreignField` /
  `connectToField` of `$lookup` and `$graphLookup`.

---

## 1. `$lookup` — left outer join

`$lookup` performs an unsharded-style left outer join from the input
collection (the "local" side) to a foreign collection. The optimizer picks
between four physical operators based on input cardinality, index presence,
and pipeline shape:

| Operator                | When                                          |
|-------------------------|-----------------------------------------------|
| Indexed nested loop     | `foreignField` is indexed, equality-style     |
| Non-indexed nested loop | No usable index, small foreign side           |
| Hash join (HJ)          | MongoDB 6.0+, both sides scanned once         |
| Dynamic indexed (DI)    | Pipeline with `$match` matching index prefix  |

`explain("executionStats")` exposes the choice under
`$lookup.strategy` / `eqLookupStrategy`. **Treat `NestedLoopJoin` over
hundreds of thousands of documents as a red flag** — it scans the foreign
collection once per input document.

### 1.1 Equality form (`localField`/`foreignField`)

```js
db.orders.aggregate([
  { $lookup: {
      from: "inventory",
      localField: "sku",
      foreignField: "sku",
      as: "stock"
  } }
]);
```

Rules:

- The `as` field is always an array, even when at most one document matches.
  Add `{ $unwind: { path: "$stock", preserveNullAndEmptyArrays: true } }` to
  flatten while keeping unmatched rows.
- If `localField` is an array, MongoDB matches **any element** of the array
  against the scalar `foreignField` (no `$unwind` required since 3.4).
- The foreign collection must live in the **same database**.
- Index the foreign side on the `foreignField` (or compound index where
  `foreignField` is the leading key for the optimizer to choose indexed
  nested loop).

### 1.2 Pipeline form with `let`

The pipeline form unlocks correlated subqueries, multi-key joins,
projection, sorting, and limiting on the joined side:

```js
db.orders.aggregate([
  { $lookup: {
      from: "inventory",
      let: { orderSku: "$sku", orderQty: "$qty" },
      pipeline: [
        { $match: { $expr: {
            $and: [
              { $eq: ["$sku", "$$orderSku"] },
              { $gte: ["$stock", "$$orderQty"] }
            ]
        } } },
        { $project: { _id: 0, sku: 1, stock: 1, warehouse: 1 } },
        { $limit: 5 }
      ],
      as: "candidates"
  } }
]);
```

Key points:

- Variables bound in `let` are referenced with the `$$` prefix inside the
  sub-pipeline; fields of the foreign documents use the normal `$` prefix.
- `localField`/`foreignField` and `let`/`pipeline` can coexist — when both
  are present, the equality join runs first and the pipeline filters the
  matched documents, which can make the optimizer choose
  `IndexedLoopJoin` + `NLJ` for the second predicate.
- For the indexed nested loop to engage on `$expr` pipeline joins, the
  foreign index must cover the equality side; range predicates inside the
  pipeline are evaluated post-fetch.

### 1.3 Atlas Search inside `$lookup` (6.0+)

```js
{ $lookup: {
    from: "products",
    let: { q: "$searchTerm" },
    pipeline: [
      { $search: {
          index: "products_text",
          text: { query: "$$q", path: ["name", "description"] }
      } },
      { $limit: 10 }
    ],
    as: "matches"
} }
```

`$search` (and `$searchMeta`) must be the **first** stage in the inner
pipeline. The `from` collection must have an Atlas Search index.

### 1.4 Sharded collections

Before MongoDB 5.1, `$lookup` could not target a sharded foreign collection.
From 5.1 onward, sharded `$lookup` is supported but the optimizer routes
through the primary shard of the join collection for non-equality joins,
which can serialize throughput. Strategies:

- Keep the foreign collection unsharded if it is small (a few hundred MB).
- Use a covering index on the shard key so `$lookup` can target a single
  shard.
- For analytics, materialize via `$merge` to a denormalized collection.

### 1.5 `$lookup` vs denormalization decision tree

| Signal                                              | Choose         |
|-----------------------------------------------------|----------------|
| Foreign side is small (< few hundred MB), changes slowly | Denormalize / embed |
| Foreign side is large, mostly read                  | `$lookup` + index |
| One-to-many with extreme fan-out (> 16 MB joined doc) | Reference + on-demand `$lookup` |
| Need search relevance on foreign side               | `$lookup` w/ `$search` |
| Reporting / dashboards, repeated query              | Materialize via `$merge` |
| Real-time write-heavy with strict consistency       | Embed (avoid join across collections) |

See `mongodb-schema-design` for the embed-vs-reference framework.

### 1.6 Common `$lookup` pitfalls

- **The `as` array grows large**: a `$lookup` that joins to a 50 000-document
  parent will return a 50 000-element array per input document, which can
  push the result over 16 MB. Use the pipeline form with `$match`/`$limit`,
  or add a `$lookup`-then-`$unwind`-then-aggregate sequence.
- **Type mismatch silently returns empty arrays**: `localField` `ObjectId`
  vs `foreignField` `string` will never match. Normalize types first or
  use `$expr` with `$toObjectId` / `$toString`.
- **`$lookup` placed before `$match` loses pushdown**: if the post-lookup
  `$match` is on the input side, move it before the `$lookup` so it
  shrinks the input set. The optimizer does this automatically only when
  the predicate is on a field that exists pre-lookup.

---

## 2. `$graphLookup` — recursive single-collection traversal

`$graphLookup` performs a recursive walk over the same (or another)
collection, accumulating every reachable document into a single output
array. It is MongoDB's answer to SQL `CONNECT BY` / recursive CTEs.

### 2.1 Syntax

```js
db.employees.aggregate([
  { $match: { _id: 1 } },          // start from CEO
  { $graphLookup: {
      from: "employees",
      startWith: "$_id",
      connectFromField: "_id",
      connectToField: "managerId",
      as: "reports",
      maxDepth: 5,
      depthField: "level",
      restrictSearchWithMatch: { active: true }
  } }
]);
```

- `startWith` — expression evaluated against the input document; can be a
  scalar or array. Each value becomes a starting point.
- `connectFromField` — the field on the **matched** documents whose value
  feeds the next iteration's lookup.
- `connectToField` — the field on the **foreign** documents to match
  against. **Index this field.**
- `maxDepth` — inclusive upper bound on recursion depth. `0` means a
  single non-recursive lookup. Always set this on production queries to
  guard against cycles.
- `depthField` — when present, every output document gets a numeric
  `depthField` indicating how many hops away from the start it is.
- `restrictSearchWithMatch` — pre-filter applied at every recursion step;
  cannot reference `$$ROOT` of the originating document but can use
  standard query operators against the foreign collection.

### 2.2 Tree / hierarchy patterns

The classic org-chart query:

```js
// All subordinates beneath an arbitrary employee, with depth.
db.employees.aggregate([
  { $match: { _id: targetEmployeeId } },
  { $graphLookup: {
      from: "employees",
      startWith: "$_id",
      connectFromField: "_id",
      connectToField: "managerId",
      as: "subordinates",
      depthField: "depth"
  } },
  { $project: {
      name: 1,
      subordinates: {
        $sortArray: { input: "$subordinates", sortBy: { depth: 1, name: 1 } }
      }
  } }
]);
```

### 2.3 Category trees and bill-of-materials

For category taxonomies, traverse from child to root via `parentId`:

```js
db.categories.aggregate([
  { $match: { slug: "wireless-headphones" } },
  { $graphLookup: {
      from: "categories",
      startWith: "$parentId",
      connectFromField: "parentId",
      connectToField: "_id",
      as: "ancestry",
      depthField: "depth"
  } }
]);
```

For bill-of-materials (BOM), the inverse direction reveals all sub-parts:

```js
db.parts.aggregate([
  { $match: { sku: "ASSEMBLY-001" } },
  { $graphLookup: {
      from: "parts",
      startWith: "$components.sku",   // array of child SKUs
      connectFromField: "components.sku",
      connectToField: "sku",
      as: "fullBom",
      maxDepth: 20,
      depthField: "level"
  } }
]);
```

### 2.4 Cycle protection

`$graphLookup` is naturally cycle-safe: it tracks already-visited documents
by `_id` and will not revisit them. However, **without `maxDepth`** a deep
or wide graph can still allocate huge intermediate state. Cap `maxDepth`
at the deepest meaningful value (org chart: 10–12 levels; permission
graph: 4–6 typical).

### 2.5 Memory and performance

- Memory limit: like every aggregation stage, 100 MB before spill.
  `$graphLookup` automatically writes temporary files to disk when it
  exceeds 100 MB **only** if `allowDiskUse: true` is set on the
  aggregation call (or `allowDiskUseByDefault` is true at server level).
  Otherwise the stage errors out.
- Index `connectToField`. Without an index every recursion step is a
  collection scan.
- `restrictSearchWithMatch` runs against the index when possible — use it
  to prune dead branches early (e.g. `{ active: true }`,
  `{ tenantId: "..." }`).
- The result is one array per input document. Use `$match` upstream to
  bound starting points.

### 2.6 Common use cases

- **Org charts**: who reports (directly or transitively) to a manager?
- **Category trees**: ancestry from leaf to root, or all descendants of a
  category node.
- **Permission inheritance**: which groups grant a user a permission via
  nested group membership?
- **Friend-of-friend / social graph**: limited-depth neighbors.
- **Bill of materials**: all sub-parts beneath an assembly.
- **Dependency graphs**: transitive package dependencies, file imports.

---

## 3. `$facet` — parallel sub-pipelines

`$facet` runs multiple independent aggregation sub-pipelines over **the
same input set** in a single stage, returning a single document whose
fields are the array results of each branch.

### 3.1 Syntax and structure

```js
db.products.aggregate([
  { $match: { active: true } },
  { $facet: {
      summary: [
        { $group: { _id: null, total: { $sum: 1 }, avgPrice: { $avg: "$price" } } }
      ],
      byCategory: [
        { $group: { _id: "$category", count: { $sum: 1 } } },
        { $sort: { count: -1 } },
        { $limit: 10 }
      ],
      priceBuckets: [
        { $bucket: {
            groupBy: "$price",
            boundaries: [0, 25, 50, 100, 250, 1000],
            default: "1000+",
            output: { count: { $sum: 1 } }
        } }
      ]
  } }
]);
```

Output is exactly **one document** with three fields, each containing the
sub-pipeline's array of result documents.

### 3.2 Constraints

- **One document, ≤16 MB**: the entire output document must fit in BSON's
  16 MB limit. If sub-pipelines return large arrays, the aggregation fails
  with `BSONObjectTooLarge`. Bound each branch with `$limit`, `$project`
  to drop fields, or move heavy branches outside `$facet` and union the
  results.
- **No cross-branch references**: sub-pipelines cannot read each other's
  output. They share only the upstream input.
- **No `$facet` nesting**: you cannot put a `$facet` stage inside another
  `$facet`.
- **Disallowed sub-stages**: `$out`, `$merge`, `$collStats`, `$indexStats`,
  `$planCacheStats`, `$facet` (no nesting), `$geoNear`, `$search`,
  `$searchMeta`, and `$vectorSearch` cannot appear inside a `$facet` branch.
- **Memory limit per branch**: each branch is independent and subject to
  its own 100 MB / `allowDiskUse` ceiling.

### 3.3 When to reach for `$facet`

| Use case                                           | Pattern |
|----------------------------------------------------|---------|
| Faceted search UI (counts by category, brand, etc.) | One branch per facet, each a `$group` over the filtered input |
| Dashboards with multiple aggregates from one query | One branch per tile |
| Histograms + summary stats together               | `$bucket` branch + `$group` branch |
| Pagination with total count                       | `data` branch with `$skip`/`$limit`, `total` branch with `$count` |

The pagination idiom:

```js
db.posts.aggregate([
  { $match: filter },
  { $facet: {
      data: [
        { $sort: { createdAt: -1 } },
        { $skip: page * pageSize },
        { $limit: pageSize }
      ],
      meta: [ { $count: "total" } ]
  } },
  { $project: {
      data: 1,
      total: { $arrayElemAt: ["$meta.total", 0] }
  } }
]);
```

### 3.4 Faceted classification example

```js
db.products.aggregate([
  { $match: { active: true, inStock: true } },
  { $facet: {
      byBrand: [
        { $group: { _id: "$brand", count: { $sum: 1 } } },
        { $sort: { count: -1 } },
        { $limit: 20 }
      ],
      byPriceRange: [
        { $bucket: {
            groupBy: "$price",
            boundaries: [0, 50, 100, 200, 500, 1000],
            default: "1000+",
            output: { count: { $sum: 1 }, examples: { $push: "$name" } }
        } }
      ],
      byRating: [
        { $bucketAuto: { groupBy: "$rating", buckets: 5 } }
      ]
  } }
]);
```

### 3.5 `$facet` vs running pipelines in parallel from the client

Because every branch shares the same upstream input, `$facet` avoids the
duplicated work of running N independent pipelines that each repeat the
filter and projection stages. Trade-offs:

- `$facet` wins when the upstream pipeline is expensive and shared.
- Multiple client-side pipelines win when each branch needs different
  pre-filters or when the 16 MB output ceiling is at risk.

---

## 4. `$bucket` and `$bucketAuto` — histograms

Both stages bucket documents into ranges of a numeric (or date) expression
and emit one document per bucket.

### 4.1 `$bucket` — explicit boundaries

```js
db.products.aggregate([
  { $bucket: {
      groupBy: "$price",
      boundaries: [0, 25, 50, 100, 250, 1000],
      default: "1000+",
      output: {
        count: { $sum: 1 },
        avgRating: { $avg: "$rating" },
        examples: { $push: "$name" }
      }
  } }
]);
```

Rules:

- `boundaries` must be strictly increasing values of the **same type** as
  the `groupBy` expression results.
- Each bucket covers `[boundaries[i], boundaries[i+1])` — lower-inclusive,
  upper-exclusive.
- A document falls into the `default` bucket when its `groupBy` value is
  outside the explicit range or its type does not match boundary type.
  Without `default`, out-of-range documents cause an error.
- The `_id` of each output document is the **lower bound** of the bucket
  (or the literal `default` value for the catch-all).

### 4.2 `$bucketAuto` — automatic boundaries

```js
db.products.aggregate([
  { $bucketAuto: {
      groupBy: "$price",
      buckets: 5,
      granularity: "R20",
      output: { count: { $sum: 1 } }
  } }
]);
```

`$bucketAuto` distributes documents as evenly as possible across the
requested number of buckets. `granularity` (optional) snaps boundaries to
a "preferred number" series:

| Granularity | Series                                            |
|-------------|---------------------------------------------------|
| `R5`        | Renard 5: 1.0, 1.6, 2.5, 4.0, 6.3                  |
| `R10`       | Renard 10: 1.0, 1.25, 1.6, 2.0, ..., 8.0            |
| `R20`       | Renard 20: finer-grained Renard                    |
| `R40`/`R80` | Even finer Renard                                  |
| `1-2-5`     | 1, 2, 5, 10, 20, 50, 100, ...                       |
| `E6`/`E12`/`E24`/`E48`/`E96`/`E192` | IEC E-series (electronics) |
| `POWERSOF2` | 1, 2, 4, 8, 16, 32, 64, ... — good for byte sizes |

Boundary values are multiplied by powers of 10 so they cover the actual
data range. Use `POWERSOF2` for log-scale histograms (latency, file
size). Use Renard for engineering-style "nice number" bin edges.

### 4.3 When to use which

| Need                                                     | Stage |
|----------------------------------------------------------|-------|
| You know the meaningful break points (price tiers)       | `$bucket` |
| You want equal-population buckets                        | `$bucketAuto` (no granularity) |
| You want equal-population buckets on a log scale         | `$bucketAuto` + `POWERSOF2` |
| You need labeled buckets ("cheap", "mid", "premium")     | `$bucket` + post-`$project` |

### 4.4 Histogram + summary together

Combine with `$facet` to render a dashboard widget in one round-trip:

```js
db.requests.aggregate([
  { $match: { ts: { $gte: ISODate("2026-05-01") } } },
  { $facet: {
      latencyHistogram: [
        { $bucketAuto: { groupBy: "$durationMs", buckets: 20, granularity: "POWERSOF2" } }
      ],
      summary: [
        { $group: {
            _id: null,
            p50: { $percentile: { input: "$durationMs", p: [0.5], method: "approximate" } },
            p95: { $percentile: { input: "$durationMs", p: [0.95], method: "approximate" } },
            p99: { $percentile: { input: "$durationMs", p: [0.99], method: "approximate" } }
        } }
      ]
  } }
]);
```

---

## 5. `$out` vs `$merge` — writing pipeline results

Both are **terminal** stages: they must appear last in the pipeline.

### 5.1 `$out` — wholesale collection replacement

```js
db.sales.aggregate([
  { $group: { _id: "$region", revenue: { $sum: "$amount" } } },
  { $out: "regionRevenue" }
]);

// Or to a different database:
{ $out: { db: "analytics", coll: "regionRevenue" } }
```

Semantics:

- Drops or atomically replaces the target collection.
- Preserves indexes on the target collection if it already exists (MongoDB
  re-creates the same indexes after the replacement).
- Fails if the target is the source collection.
- **Cannot output to a sharded collection** (on any version). The input/source
  collection may be sharded, but the `$out` target must be unsharded — use
  `$merge` to write into a sharded collection.
- Does not allow you to write conditionally — every run is an unconditional
  overwrite.

### 5.2 `$merge` — incremental upsert

```js
db.orders.aggregate([
  { $match: { date: { $gte: yesterday } } },
  { $group: {
      _id: { customer: "$customerId", date: { $dateTrunc: { date: "$date", unit: "day" } } },
      revenue: { $sum: "$total" },
      orders: { $sum: 1 }
  } },
  { $merge: {
      into: { db: "analytics", coll: "dailyCustomerRevenue" },
      on: "_id",
      whenMatched: "merge",
      whenNotMatched: "insert"
  } }
]);
```

Required key:

- `into` — target collection (string or `{ db, coll }`).

Optional keys:

- `on` — single field name or array used as the unique key. Default is
  `_id`. If you supply a custom `on`, a **unique index** must back it.
- `let` — variables usable by the `whenMatched` pipeline.
- `whenMatched` — behavior when a document with the same `on` value
  exists in the target:
  - `"merge"` (default) — `$set`-style field merge (incoming fields
    overwrite; existing-only fields are kept).
  - `"replace"` — replace the matched document entirely (preserves `_id`).
  - `"keepExisting"` — keep target untouched.
  - `"fail"` — error on any collision.
  - `[ ...pipeline ]` — custom update pipeline. Reference incoming fields
    via `$$new` and existing fields with normal `$` paths.
- `whenNotMatched` — behavior when no match:
  - `"insert"` (default) — insert the incoming document.
  - `"discard"` — drop unmatched results silently.
  - `"fail"` — error if any input has no match in the target.

### 5.3 Materialized view refresh patterns

**Full rebuild on schedule** (use `$out`):

```js
// nightly
db.events.aggregate([
  { $match: { ts: { $gte: ISODate("2020-01-01") } } },
  { $group: { _id: { day: { $dateTrunc: { date: "$ts", unit: "day" } } },
              events: { $sum: 1 } } },
  { $out: "dailyEventCounts" }
]);
```

**Incremental refresh** (use `$merge` with a watermark):

```js
// every 5 minutes, only the latest window
db.events.aggregate([
  { $match: { ts: { $gte: ISODate(lastRun) } } },
  { $group: { _id: { day: { $dateTrunc: { date: "$ts", unit: "day" } } },
              events: { $sum: 1 } } },
  { $merge: { into: "dailyEventCounts", on: "_id",
              whenMatched: [
                { $set: { events: { $add: ["$events", "$$new.events"] } } }
              ],
              whenNotMatched: "insert" } }
]);
```

The custom `whenMatched` pipeline lets the new run **add** to the
existing total rather than replace it — essential for additive rollups
where you process only the delta.

### 5.4 Idempotency rules

- Set `_id` (or the `on` key) **deterministically** from the source data
  so re-running the same window produces identical keys.
- For additive metrics with incremental refresh, the math must compensate
  if the same source documents are seen twice. Either (a) use a strict
  watermark that never overlaps, or (b) make `whenMatched` `"replace"` and
  aggregate over the full window each run.
- For `whenMatched: "merge"`, missing fields in the new document do not
  remove existing fields. Use `"replace"` if you want hard overwrite.

### 5.5 Pitfalls

- **Same-collection `$merge` can loop**: writing back to the source
  collection in a way that changes document size or shard-key value can
  cause documents to be re-read by the same pipeline. MongoDB docs
  explicitly warn that this can result in documents being processed
  multiple times or an infinite loop. Prefer `$out` or write to a
  separate collection.
- **Unique index required for non-default `on`**: without it, `$merge`
  fails at execution time.
- **`$merge`/`$out` are not transactional with the source reads**: a
  client reading the source mid-merge sees a mix. Wrap downstream
  consumers around a "last refresh at" marker.
- **Sharding**: `$merge` is supported into sharded targets; the `on` key
  must include the shard key (or be the shard key). `$out` cannot target a
  sharded collection on any version — use `$merge` when the destination is
  sharded.

---

## 6. `$setWindowFields` — window functions

Introduced in 5.0, `$setWindowFields` brings SQL-style window functions
to MongoDB: running totals, moving averages, lead/lag, ranks, derivatives,
integrals — all computed over a window of documents while every input
document survives in the output (unlike `$group`).

### 6.1 Anatomy

```js
{ $setWindowFields: {
    partitionBy: <expression>,           // optional, defaults to all-one-partition
    sortBy: { <field>: 1|-1, ... },      // required for most window operators
    output: {
      <newField>: {
        <accumulator>: <expression>,
        window: {
          documents: [ <lower>, <upper> ]   // OR
          range:     [ <lower>, <upper> ], unit: <"second"|"minute"|...>
        }
      },
      ...
    }
} }
```

- `partitionBy` — segments the input into independent groups. Each
  partition gets its own sliding window.
- `sortBy` — orders documents within a partition. Window boundaries are
  defined relative to this order.
- `window` — defines the inclusive range of documents/values the
  accumulator covers:
  - `documents: [a, b]` — position-based, where `"current"`, integers, or
    `"unbounded"` are valid bounds.
  - `range: [a, b]` — value-based on the `sortBy` field; for date sort
    fields, supply `unit` (e.g. `"day"`).

You cannot mix `documents` and `range` in the same window.

### 6.2 Operator catalog

Accumulators usable inside `$setWindowFields.output`:

| Operator       | Returns                                                     |
|----------------|-------------------------------------------------------------|
| `$sum`         | Running / windowed sum                                      |
| `$avg`         | Running / windowed average                                  |
| `$min`/`$max`  | Window min / max                                            |
| `$count`       | Document count in window                                    |
| `$stdDevPop` / `$stdDevSamp` | Population / sample standard deviation       |
| `$covariancePop` / `$covarianceSamp` | Covariance between two fields         |
| `$expMovingAvg`| Exponentially weighted moving average                       |
| `$derivative`  | Rate of change between window endpoints                     |
| `$integral`    | Trapezoidal integral over the window                        |
| `$rank`        | Rank within partition, with gaps after ties                 |
| `$denseRank`   | Rank within partition, **no** gaps after ties               |
| `$documentNumber` | Position within partition (unique per doc)              |
| `$shift`       | Value from another document by offset, with default         |
| `$linearFill`  | Linear interpolation across missing values                  |
| `$locf`        | Last observation carried forward (within partition)         |
| `$first` / `$last` | First / last document's expression value in the window |
| `$top` / `$topN` / `$bottom` / `$bottomN` / `$firstN` / `$lastN` | N-of order operators |
| `$percentile` / `$median` | Quantile estimates                                |

### 6.3 Ranking semantics

For sortBy values `[7, 9, 9, 10]`:

- `$rank` → `1, 2, 2, 4` (gap after tie)
- `$denseRank` → `1, 2, 2, 3` (no gap)
- `$documentNumber` → `1, 2, 3, 4` (always unique)

### 6.4 Running totals and moving averages

```js
// Daily cumulative revenue per customer.
db.orders.aggregate([
  { $setWindowFields: {
      partitionBy: "$customerId",
      sortBy: { orderDate: 1 },
      output: {
        cumulativeRevenue: {
          $sum: "$total",
          window: { documents: ["unbounded", "current"] }
        },
        sevenDayAvg: {
          $avg: "$total",
          window: { range: [-6, 0], unit: "day" }
        }
      }
  } }
]);
```

### 6.5 Lead / lag with `$shift`

```js
// Compare each order to the previous order from the same customer.
db.orders.aggregate([
  { $setWindowFields: {
      partitionBy: "$customerId",
      sortBy: { orderDate: 1 },
      output: {
        prevTotal: { $shift: { output: "$total", by: -1, default: null } },
        nextTotal: { $shift: { output: "$total", by: 1,  default: null } }
      }
  } },
  { $addFields: { deltaVsPrev: { $subtract: ["$total", "$prevTotal"] } } }
]);
```

### 6.6 Derivative and integral for time-series

```js
// Speed (derivative of distance) and total distance (integral of speed)
// across each device's reading stream.
db.telemetry.aggregate([
  { $setWindowFields: {
      partitionBy: "$deviceId",
      sortBy: { ts: 1 },
      output: {
        speedKmh: {
          $derivative: { input: "$distanceKm", unit: "hour" },
          window: { documents: [-1, 0] }
        },
        cumulativeExposure: {
          $integral: { input: "$radiation", unit: "minute" },
          window: { documents: ["unbounded", "current"] }
        }
      }
  } }
]);
```

`$derivative` requires `unit` for time-based sortBy fields and returns the
rate per that unit. `$integral` returns the trapezoidal area under the
curve over the window.

### 6.7 Memory limit

`$setWindowFields` is subject to the 100 MB / `allowDiskUse` rule per
partition, not per pipeline overall. Very wide partitions with unbounded
windows can spill. Reduce partition size by adding `partitionBy` keys, or
bound the window with `documents` / `range`.

---

## 7. `$densify` — close gaps in numeric / time ranges

`$densify` (5.1+) inserts synthetic documents to make a sequence dense
along a numeric or date field. The synthetic documents carry only the
densified field (and any partition fields); other fields are absent and
typically populated by a following `$fill` stage.

### 7.1 Syntax

```js
{ $densify: {
    field: <numeric or date field>,
    partitionByFields: [ <field>, ... ],   // optional
    range: {
      step: <number>,
      unit: <"second"|"minute"|"hour"|"day"|"week"|"month"|"quarter"|"year">,
      bounds: <"full"|"partition"|[ <lower>, <upper> ]>
    }
} }
```

`bounds` values:

- `"full"` — span the global min/max of the `field` across all input
  documents (one synthetic sequence covers every partition).
- `"partition"` — span the min/max within each partition independently.
- `[lower, upper]` — explicit literal bounds.

`unit` is required when `field` is a date and optional for numeric fields.

### 7.2 Hourly observations example

```js
db.readings.aggregate([
  { $match: { deviceId: { $in: deviceList } } },
  { $densify: {
      field: "ts",
      partitionByFields: ["deviceId"],
      range: { step: 1, unit: "hour", bounds: "partition" }
  } }
]);
```

Result: every device gets one document per hour from its earliest to its
latest reading. Missing hours appear as `{ deviceId, ts }` with no other
fields.

### 7.3 Numeric densification example

```js
db.weeklySales.aggregate([
  { $densify: {
      field: "week",
      partitionByFields: ["region"],
      range: { step: 1, bounds: [1, 52] }
  } }
]);
```

Use cases: tax periods, fiscal weeks, leaderboard rank slots — anywhere a
key is expected to be contiguous but real data has holes.

### 7.4 Rules

- `$densify` does not modify existing documents; it only **adds** new ones.
- Inserted documents inherit only `partitionByFields` and the densified
  `field`. Use `$fill` next to populate value fields.
- If two existing documents collide with the same generated key, the
  existing documents survive — `$densify` is a no-op for those positions.
- `$densify` must precede operations that assume dense input
  (`$setWindowFields` for moving averages, charts, time-aligned joins).

---

## 8. `$fill` — populate null and missing values

`$fill` (5.3+) sets a value for fields that are null or missing. It is
typically paired with `$densify` to fill in the synthetic gap rows, but
works on any pipeline.

### 8.1 Methods

| Method                              | Behavior                                       |
|-------------------------------------|------------------------------------------------|
| `{ value: <expr> }`                 | Constant or computed value                     |
| `{ method: "linear" }`              | Linear interpolation between non-null values   |
| `{ method: "locf" }`                | Last Observation Carried Forward               |

For `linear` and `locf`, you must supply `sortBy` so ordering is defined.

### 8.2 Syntax

```js
{ $fill: {
    partitionByFields: [ <field>, ... ],   // optional
    partitionBy: <expression>,             // optional, exclusive with partitionByFields
    sortBy: { <field>: 1|-1, ... },        // required for linear/locf
    output: {
      <field>: { method: "linear" },
      <field>: { method: "locf" },
      <field>: { value: <expression> }
    }
} }
```

### 8.3 Time-series gap fill (densify + fill)

The canonical pattern from the MongoDB blog:

```js
db.storageRoom.aggregate([
  // Bucket to the hour.
  { $group: {
      _id: { room: "$room", hour: { $dateTrunc: { date: "$ts", unit: "hour" } } },
      tempC:    { $avg: "$tempC" },
      motion:   { $max: "$motion" },
      inventory:{ $last: "$inventory" }
  } },
  { $set: { room: "$_id.room", ts: "$_id.hour" } },
  { $unset: "_id" },

  // Make sure every hour exists for every room.
  { $densify: {
      field: "ts",
      partitionByFields: ["room"],
      range: { step: 1, unit: "hour", bounds: "partition" }
  } },

  // Fill the holes.
  { $fill: {
      partitionByFields: ["room"],
      sortBy: { ts: 1 },
      output: {
        tempC:     { method: "linear" },
        motion:    { value: 0 },
        inventory: { method: "locf" }
      }
  } },

  { $sort: { room: 1, ts: 1 } }
]);
```

### 8.4 `$linearFill` expression (vs `$fill`'s `linear` method)

`$linearFill` is also available as a window function inside
`$setWindowFields`. Use the standalone `$fill` stage when you want a
self-contained gap-fill step; use `$linearFill` inside `$setWindowFields`
when you are already partitioning / sorting for other window operators.

### 8.5 Rules

- For `locf`, the first run of nulls before any non-null value remains
  null — there is no value to carry forward.
- For `linear`, the same boundary rule applies and additionally: leading
  and trailing nulls (before the first or after the last non-null)
  remain null because interpolation requires two endpoints.
- `$fill` only writes the **output** fields you specify. Other fields are
  untouched.
- `$fill`'s `partitionBy` / `partitionByFields` must match the upstream
  `$densify` partition keys, or you will see synthetic rows that never
  get filled.

---

## 9. `$unionWith` — UNION ALL across collections

`$unionWith` (4.4+) appends documents from another collection (and
optionally its own pipeline) to the running stream. It is MongoDB's
equivalent of SQL `UNION ALL`.

### 9.1 Syntax

```js
{ $unionWith: { coll: <name>, pipeline: [ ... ] } }
// or shorthand
{ $unionWith: <collectionName> }
```

`pipeline` is optional and runs on the union'd collection's documents
before they are appended. The current pipeline's documents pass through
untouched and the union'd documents are appended **at this point in the
pipeline**.

### 9.2 Multi-year sales example

```js
db.sales2024.aggregate([
  { $unionWith: { coll: "sales2025" } },
  { $unionWith: { coll: "sales2026" } },
  { $group: {
      _id: "$item",
      qty: { $sum: "$qty" },
      revenue: { $sum: "$total" }
  } },
  { $sort: { revenue: -1 } }
]);
```

### 9.3 Removing duplicates (`UNION` not `UNION ALL`)

`$unionWith` includes duplicates. To deduplicate, follow it with `$group`:

```js
db.suppliers.aggregate([
  { $project: { state: 1, _id: 0 } },
  { $unionWith: { coll: "warehouses",
                  pipeline: [ { $project: { state: 1, _id: 0 } } ] } },
  { $group: { _id: "$state" } }
]);
```

### 9.4 Rules

- All collections involved must be in the same database.
- The combined stream of documents may have heterogeneous shapes. Project
  to a common shape before grouping or merging.
- `$unionWith` cannot be used inside a multi-document transaction.
- Disallowed stages inside the inner `pipeline`: `$out`, `$merge`.
- Each collection scan inside `$unionWith` is independent — index it
  appropriately if you push down a `$match`.

### 9.5 Use cases

- **Sharded archive + hot collection**: union an archive collection with
  the live collection for unified reporting.
- **Cross-tenant report**: union per-tenant collections (when the schema
  forbids a single collection).
- **Migration**: dual-read from old and new collections during cutover.
- **Heterogeneous corpora**: union "cases", "slack", "meetings" into a
  single search/scoring pipeline.

---

## 10. Memory limits, `allowDiskUse`, and `explain`

### 10.1 The 100 MB-per-stage rule

Each blocking aggregation stage may use up to **100 MB of RAM** for its
in-memory state. Blocking stages include `$sort`, `$group`, `$bucket`,
`$bucketAuto`, `$setWindowFields`, `$facet` (per branch), `$graphLookup`,
and `$lookup` (when buffering).

When a stage exceeds the limit:

- **MongoDB 6.0+ with `allowDiskUseByDefault: true`** (the default for
  Atlas / current community builds) — the stage spills to temporary
  files transparently.
- **`allowDiskUseByDefault: false`** — the stage errors out with
  `QueryExceededMemoryLimitNoDiskUseAllowed` unless the call explicitly
  passes `allowDiskUse: true`.
- **Pre-6.0** — the stage always errors unless `allowDiskUse: true` is
  set on the aggregation command.

### 10.2 Enabling disk spill

```js
db.collection.aggregate(pipeline, { allowDiskUse: true });
```

Equivalent settings:

- **Server**: `db.adminCommand({ setParameter: 1, allowDiskUseByDefault: true })`
- **Atlas**: `allowDiskUseByDefault` is enabled by default; it can be
  toggled per cluster.
- **Drivers**: `AggregateOptions.allowDiskUse(true)` (Java),
  `aggregate({ allowDiskUse: true })` (Node), `aggregate(..., allowDiskUse=True)` (Python).

### 10.3 `explain("executionStats")` for spill detection

```js
db.collection.explain("executionStats").aggregate(pipeline);
```

Key signals in the output:

- `usedDisk: true` — at least one stage spilled to temporary files.
- `spillFileSize` / `spilledBytes` / `spilledRecords` — magnitude of the
  spill (newer versions).
- `executionTimeMillisEstimate` per stage — locate the slow stage.
- `nReturned`, `totalKeysExamined`, `totalDocsExamined` — index health.
- `$lookup.strategy` / `eqLookupStrategy` —
  `"IndexedLoopJoin"` (good), `"NestedLoopJoin"` (bad on large input),
  `"HashJoin"`, or `"DynamicIndexedLoopJoin"`.

### 10.4 The 16 MB document limit

- Every document at every stage must fit in 16 MB.
- `$facet` output is **one document** containing every branch's array —
  this is where the 16 MB ceiling hits hardest. Bound each branch.
- `$group` with `$push` can blow up an array beyond 16 MB. Use
  `$accumulator` chunks, `$bucket` + `$group`, or write to a collection
  with `$merge` instead of returning to the client.
- Pipelines that join with `$lookup` and then `$unwind` are fine; pipelines
  that `$lookup` and then leave the joined array intact may overflow.

### 10.5 Stage ordering for memory and performance

The optimizer reorders stages where it can, but you should write
pipelines that already minimize the working set:

1. `$match` first — filter early, ideally on an indexed field.
2. `$project` / `$unset` next — drop fields you do not need.
3. `$sort` before `$group` only if the sort is needed for output, and
   only after the dataset is reduced.
4. `$lookup` / `$graphLookup` after pruning — every joined document
   multiplies cost.
5. Terminal `$out` / `$merge` last.

### 10.6 Sharded aggregation specifics

- Stages run on each shard up to the first **split point** (a stage that
  requires a global view, like `$group` without the shard key in `_id`,
  `$sort` over the full result, or `$facet`).
- After the split point, intermediate results stream to the mongos (or
  the merging shard) for the rest of the pipeline.
- `$out` / `$merge` execute on the merging side; the target collection
  may need to be unsharded or `$merge.on` must include the shard key.

### 10.7 Quick spill triage

| Symptom                                              | Action |
|------------------------------------------------------|--------|
| `usedDisk: true` on `$sort`                          | Add a `$match` upstream, add an index supporting the sort, or pre-filter |
| `usedDisk: true` on `$group`                         | Reduce `_id` cardinality, project away fields before `$group`, run nightly with `$merge` |
| `usedDisk: true` on `$setWindowFields`               | Narrow partitions, bound the window, or split the pipeline |
| `BSONObjectTooLarge` on `$facet`                     | `$limit` every branch; move heavy branches outside `$facet` |
| `BSONObjectTooLarge` on `$group` + `$push`           | Use `$bucket` or `$merge` to a collection |
| `$lookup` NestedLoopJoin                             | Add index on `foreignField`, or rewrite as pipeline form |
| `$graphLookup` blows memory                          | Set `maxDepth`, add `restrictSearchWithMatch`, index `connectToField` |

---

## 11. Stage interaction cheat sheet

| Goal                                                 | Composition |
|------------------------------------------------------|-------------|
| Pagination with total                                | `$match` -> `$facet({ data: [$sort,$skip,$limit], meta: [$count] })` |
| Daily revenue rollup, incremental                    | `$match(watermark)` -> `$group` -> `$merge(on=_id, whenMatched=pipeline-add)` |
| Time-series gap-filled chart                         | `$group(bucket)` -> `$densify` -> `$fill(linear/locf)` -> `$sort` |
| Moving average + rank                                | `$setWindowFields({ partitionBy, sortBy, output: { ma:$avg, rk:$denseRank } })` |
| Hierarchy with depth                                 | `$match(root)` -> `$graphLookup(maxDepth,depthField)` |
| Faceted dashboard widget                             | `$match` -> `$facet({ summary, buckets, top })` |
| Multi-source union for search                        | `$unionWith*` -> `$project(common)` -> `$group(dedupe)` |
| Join with index pushdown                             | `$match(local)` -> `$lookup(localField/foreignField + index)` -> `$unwind` |
| Correlated subquery join                             | `$lookup({ let, pipeline:[ $match($expr), $project, $limit ] })` |

---

## 12. Practical recipes

### 12.1 Top-N per group (without `$group` + `$slice` 16 MB risk)

```js
// Top 3 highest-priced products per category.
db.products.aggregate([
  { $setWindowFields: {
      partitionBy: "$category",
      sortBy: { price: -1 },
      output: { rank: { $denseRank: {} } }
  } },
  { $match: { rank: { $lte: 3 } } }
]);
```

### 12.2 Bucketed latency report

```js
db.requests.aggregate([
  { $match: { ts: { $gte: oneHourAgo } } },
  { $facet: {
      hist: [
        { $bucket: {
            groupBy: "$durationMs",
            boundaries: [0, 50, 100, 250, 500, 1000, 2000, 5000],
            default: "5000+",
            output: { count: { $sum: 1 } }
        } }
      ],
      pct:  [
        { $group: { _id: null,
            p50: { $percentile: { input: "$durationMs", p: [0.5],  method: "approximate" } },
            p95: { $percentile: { input: "$durationMs", p: [0.95], method: "approximate" } },
            p99: { $percentile: { input: "$durationMs", p: [0.99], method: "approximate" } }
        } }
      ]
  } }
]);
```

### 12.3 Materialized daily-revenue refresh job

```js
function refreshDailyRevenue(lastRun) {
  return db.orders.aggregate([
    { $match: { updatedAt: { $gt: lastRun } } },
    { $group: {
        _id: { c: "$customerId", d: { $dateTrunc: { date: "$orderDate", unit: "day" } } },
        revenue: { $sum: "$total" },
        orders:  { $sum: 1 }
    } },
    { $merge: {
        into: "dailyCustomerRevenue",
        on: "_id",
        whenMatched: [
          { $set: {
              revenue: { $add: [ "$revenue", "$$new.revenue" ] },
              orders:  { $add: [ "$orders",  "$$new.orders"  ] }
          } }
        ],
        whenNotMatched: "insert"
    } }
  ]);
}
```

### 12.4 Hierarchical permission resolution

```js
// All permissions for a user via nested group membership.
db.users.aggregate([
  { $match: { _id: userId } },
  { $graphLookup: {
      from: "groups",
      startWith: "$groupIds",
      connectFromField: "memberOfGroupIds",
      connectToField: "_id",
      as: "allGroups",
      maxDepth: 10
  } },
  { $project: {
      _id: 1,
      effectivePermissions: {
        $setUnion: {
          $reduce: {
            input: "$allGroups",
            initialValue: [],
            in: { $concatArrays: ["$$value", "$$this.permissions"] }
          }
        }
      }
  } }
]);
```

### 12.5 Gap-filled per-device hourly chart data

```js
db.telemetry.aggregate([
  { $match: { ts: { $gte: dayAgo }, deviceId: { $in: deviceList } } },
  { $group: {
      _id: { d: "$deviceId", h: { $dateTrunc: { date: "$ts", unit: "hour" } } },
      tempC: { $avg: "$tempC" },
      battery: { $last: "$battery" }
  } },
  { $project: { _id: 0, deviceId: "$_id.d", ts: "$_id.h", tempC: 1, battery: 1 } },
  { $densify: {
      field: "ts",
      partitionByFields: ["deviceId"],
      range: { step: 1, unit: "hour", bounds: "partition" }
  } },
  { $fill: {
      partitionByFields: ["deviceId"],
      sortBy: { ts: 1 },
      output: { tempC: { method: "linear" }, battery: { method: "locf" } }
  } },
  { $sort: { deviceId: 1, ts: 1 } }
]);
```

---

## 13. Anti-patterns

- **`$lookup` without an index on `foreignField`** — turns every join
  into an `O(N*M)` collection scan. Always index the foreign side.
- **`$graphLookup` without `maxDepth`** — unbounded recursion can hit the
  100 MB ceiling or, with disk spill, run for hours on dense graphs.
- **`$facet` branches without `$limit`** — easiest way to hit
  `BSONObjectTooLarge`. Cap arrays in every branch.
- **`$merge` into the source collection** — risk of infinite loops if
  the merge changes document size or shard key. Write to a separate
  collection.
- **`$out` to a sharded target** — unsupported on any version; `$out` cannot
  write to a sharded collection. Use `$merge` when the destination is sharded.
- **`$setWindowFields` over one giant partition** — single-partition
  window over millions of documents will spill. Add a `partitionBy` key
  or split by tenant / day.
- **`$densify` without a following `$fill`** — produces ghost rows with
  missing fields that downstream code may not expect.
- **`$unionWith` followed by a `$lookup`** — the join may need to scan
  twice, once per input branch, without index pushdown for one side.
- **Pipelines that ignore `explain`** — without `executionStats`, you
  cannot detect `usedDisk`, NestedLoopJoin, or unindexed sorts.

---

## 14. Version reference

| Capability                                           | Minimum MongoDB version |
|------------------------------------------------------|--------------------------|
| `$lookup` equality form                              | 3.2                      |
| `$graphLookup`                                       | 3.4                      |
| `$facet`, `$bucket`, `$bucketAuto`                   | 3.4                      |
| `$lookup` pipeline form with `let`                   | 3.6                      |
| `$merge`                                             | 4.2                      |
| `$unionWith`                                         | 4.4                      |
| Sharded foreign collection in `$lookup`              | 5.1                      |
| `$setWindowFields` and window functions              | 5.0                      |
| `$densify`                                           | 5.1                      |
| `$fill`, `$linearFill`, `$locf`                      | 5.3                      |
| `$lookup` containing `$search` / `$searchMeta`       | 6.0                      |
| `allowDiskUseByDefault = true`                       | 6.0                      |
| Hash join optimizer strategy for `$lookup`           | 6.0                      |

---

## 15. Sources

1. MongoDB Docs — [$lookup (aggregation stage)](https://www.mongodb.com/docs/manual/reference/operator/aggregation/lookup/)
2. MongoDB Docs — [$graphLookup (aggregation stage)](https://www.mongodb.com/docs/manual/reference/operator/aggregation/graphlookup/)
3. MongoDB Docs — [$facet (aggregation stage)](https://www.mongodb.com/docs/manual/reference/operator/aggregation/facet/)
4. MongoDB Docs — [$bucket (aggregation stage)](https://www.mongodb.com/docs/manual/reference/operator/aggregation/bucket/)
5. MongoDB Docs — [$bucketAuto (aggregation stage)](https://www.mongodb.com/docs/manual/reference/operator/aggregation/bucketauto/)
6. MongoDB Docs — [$merge (aggregation stage)](https://www.mongodb.com/docs/manual/reference/operator/aggregation/merge/)
7. MongoDB Docs — [$out (aggregation stage)](https://www.mongodb.com/docs/manual/reference/operator/aggregation/out/)
8. MongoDB Docs — [$setWindowFields (aggregation stage)](https://www.mongodb.com/docs/manual/reference/operator/aggregation/setwindowfields/)
9. MongoDB Docs — [$densify (aggregation stage)](https://www.mongodb.com/docs/manual/reference/operator/aggregation/densify/)
10. MongoDB Docs — [$fill (aggregation stage)](https://www.mongodb.com/docs/manual/reference/operator/aggregation/fill/)
11. MongoDB Docs — [$linearFill (expression)](https://www.mongodb.com/docs/manual/reference/operator/aggregation/linearfill/)
12. MongoDB Docs — [$unionWith (aggregation stage)](https://www.mongodb.com/docs/manual/reference/operator/aggregation/unionwith/)
13. MongoDB Docs — [Aggregation Pipeline Limits](https://www.mongodb.com/docs/manual/core/aggregation-pipeline-limits/)
14. MongoDB Blog — [Introducing Gap Filling For Time Series Data in MongoDB 5.3](https://www.mongodb.com/company/blog/product-release-announcements/introducing-gap-filling-time-series-data-mongodb-5-3)
15. MongoDB Developer Hub — [Preparing time-series data with $densify and $fill](https://www.mongodb.com/developer/products/mongodb/preparing-tsdata-with-densify-and-fill/)
16. Practical MongoDB Aggregations Book — [Faceted Classification](https://www.practical-mongodb-aggregations.com/examples/trend-analysis/faceted-classifications.html)
17. MongoDB Performance Tuning (Guy Harrison) — [Getting started with MongoDB 5.0 window functions](https://medium.com/mongodb-performance-tuning/getting-started-with-mongodb-5-0-window-functions-5477f911908b)
18. Percona — [Window Functions in MongoDB 5.0](https://www.percona.com/blog/window-functions-in-mongodb-5-0/)
