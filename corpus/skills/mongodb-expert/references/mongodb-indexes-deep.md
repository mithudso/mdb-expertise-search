<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-indexes-deep` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-indexes-deep
title: MongoDB Indexes Deep Dive
version: 1.2.0
updated: "2026-05-29"
category: mongodb
tags: [mongodb, indexes, compound, partial, esr, geospatial, ttl, text, wildcard, hashed, multikey, sparse, unique, covering, hidden, btree, index-build, rolling-index, selectivity]
description: >
  Deep reference covering every MongoDB index type (single-field, compound, multikey,
  partial, sparse, TTL, text, wildcard, hashed, 2dsphere, unique, hidden), build
  strategies (hybrid, rolling Atlas), selectivity analysis, covering indexes, and
  production anti-patterns — with code examples and the ESR (Equality→Sort→Range) rule.

  TRIGGER: user asks about indexes, compound index design, ESR rule, slow queries or
  COLLSCAN, explain() output, covering queries, partial/sparse/TTL/wildcard/hidden index
  choice, index build on live cluster, index anti-patterns, $indexStats, hint(), index
  intersection, rolling index build, time-series index constraints, or index size/memory.

  SKIP: query performance issues not related to indexes (use mongodb-performance-troubleshooting);
  full-text search design (use mongodb-atlas-search); schema design questions without
  indexing context (use mongodb-schema-design); sharding shard-key selection without
  indexing sub-questions (use mongodb-sharding).

whenToUse:
  - "How do I design a compound index for this query?"
  - "My query is doing a COLLSCAN — what index should I add?"
  - "What is the ESR rule and how do I apply it?"
  - "Choosing between partial, sparse, TTL, wildcard, or hidden index"
  - "How do I build an index on a live Atlas cluster without downtime?"
  - "Should I use a covering index / index-only query?"
  - "How do I safely remove an index using hideIndex()?"
  - "My explain() shows totalDocsExamined is high — how do I fix it?"
  - "What are the anti-patterns for MongoDB indexes?"
  - "How do text indexes compare to Atlas Search?"
  - "Compound hashed shard key design"
  - "Index constraints on time-series collections"

whenNotToUse:
  - User needs full-text search architecture (fuzzy, facets, autocomplete) — use mongodb-atlas-search
  - User needs Atlas Search index configuration (not B-tree indexes) — use mongodb-atlas-search
  - User is asking about WiredTiger cache or storage internals unrelated to index design — use mongodb-wiredtiger-internals
  - User is designing a sharding topology and only incidentally mentions indexes — use mongodb-sharding
  - User needs query performance profiling beyond explain() (FTDC, slow query log) — use mongodb-performance-troubleshooting

related_skills:
  - mongodb-performance-troubleshooting
  - mongodb-atlas-search
  - mongodb-schema-design
  - mongodb-sharding
  - mongodb-wiredtiger-internals
  - mongodb-query-performance
  - mongodb-time-series
  - mongodb-aggregation-pipeline

references:
  - https://www.mongodb.com/docs/manual/indexes/
  - https://www.mongodb.com/docs/manual/core/indexes/index-types/
  - https://www.mongodb.com/docs/manual/core/index-compound/
  - https://www.mongodb.com/docs/manual/core/indexes/index-types/index-multikey/
  - https://www.mongodb.com/docs/manual/core/indexes/index-types/index-partial/
  - https://www.mongodb.com/docs/manual/core/indexes/index-types/index-sparse/
  - https://www.mongodb.com/docs/manual/core/indexes/index-types/index-ttl/
  - https://www.mongodb.com/docs/manual/core/indexes/index-types/index-text/
  - https://www.mongodb.com/docs/manual/core/indexes/index-types/index-wildcard/
  - https://www.mongodb.com/docs/manual/core/indexes/index-types/index-hashed/
  - https://www.mongodb.com/docs/manual/core/indexes/index-types/index-2dsphere/
  - https://www.mongodb.com/docs/manual/core/index-unique/
  - https://www.mongodb.com/docs/manual/core/index-intersection/
  - https://www.mongodb.com/docs/manual/core/index-creation/
  - https://www.mongodb.com/docs/manual/core/rolling-index-builds/
---

# MongoDB Indexes Deep Dive

Reference for every MongoDB index type, ordering strategies, build mechanics,
and production anti-patterns. Use this alongside `explain()` output when diagnosing query plans.

> **Audience:** MongoDB developers and DBAs working on query optimization, schema design, or
> production index management.

## Quick-Reference Cheat Sheet

```
Single-field  : { field: 1 }
Compound      : { eq1: 1, eq2: 1, sortField: -1, rangeField: 1 }  ← ESR order
Multikey      : automatic when field is array; no parallel arrays in compound
Partial       : { field: 1 }, { partialFilterExpression: { status: "active" } }
Sparse        : { field: 1 }, { sparse: true }  ← prefer partial instead
TTL           : { dateField: 1 }, { expireAfterSeconds: N }
Text          : { field: "text" }  / { "$**": "text" }
Wildcard      : { "$**": 1 }  / { "sub.$**": 1 }
Hashed        : { _id: "hashed" }  ← even distribution shard key
2dsphere      : { location: "2dsphere" }  ← GeoJSON [lng, lat]
Unique        : { field: 1 }, { unique: true }
Unique+Partial: { field: 1 }, { unique: true, partialFilterExpression: {...} }
Hidden        : createIndex(..., { hidden: true })  ← test removal without drop
```

Sections: §1 Single-field · §2 Compound/ESR · §3 Multikey · §4 Partial · §5 Sparse ·
§6 TTL · §7 Text · §8 Wildcard · §9 Hashed · §10 2dsphere · §11 Unique ·
§12 Intersection · §13 Build Strategies · §14 Selectivity & Covering ·
§15 Hidden Indexes · §16 hint() & Forcing · §17 Anti-Patterns

---

## 1. Single-Field Indexes

The most common index type. MongoDB automatically creates a unique index on `_id`.

```js
// Ascending index on a single field
db.orders.createIndex({ customerId: 1 });

// Descending — functionally equivalent for single-field indexes
// (MongoDB traverses B-tree in either direction)
db.orders.createIndex({ createdAt: -1 });

// Explicit _id index already exists; do not recreate it
// db.orders.createIndex({ _id: 1 }); // no-op
```

**When single-field is enough:**
- Query filters only one field with high selectivity (e.g., UUID, email).
- Sort is on the same field as the filter and no range condition is involved.
- Write throughput is a concern — every extra index adds write overhead.

**Ascending vs descending matters** only for compound indexes. For a solo field, both
directions serve equality and range queries equally well. Direction only becomes load-bearing
when combining fields in a compound index (see §2) or when serving sort-heavy queries where
the sort order must align with the index direction.

---

## 2. Compound Indexes — The ESR Rule

Compound indexes cover multiple fields in a declared order. **Order is everything.**

### ESR Rule (Equality → Sort → Range)

Place fields in this sequence to maximize the index's usefulness:

1. **E**quality predicates first — fields compared with `$eq` or `$in` (point lookups).
2. **S**ort fields next — fields in the `sort()` clause, preserving their direction.
3. **R**ange fields last — fields with `$gt`, `$lt`, `$gte`, `$lte`, `$ne`, `$nin`, regex.

```js
// Query: find active orders for a customer, sort by date, filter price range
db.orders.find(
  { status: "active", customerId: "abc123", price: { $gte: 50, $lte: 200 } }
).sort({ createdAt: -1 });

// ESR compound index:
// Equality: status, customerId
// Sort:     createdAt (descending matches the sort direction)
// Range:    price
db.orders.createIndex({
  status: 1,
  customerId: 1,
  createdAt: -1,
  price: 1
});
```

### Prefix Matching

Any prefix of a compound index can serve queries on that prefix alone:

```js
db.users.createIndex({ country: 1, state: 1, city: 1 });
// Serves: { country } queries
// Serves: { country, state } queries
// Serves: { country, state, city } queries
// Does NOT serve: { state } or { city } queries alone
```

A single compound index replaces multiple single-field indexes when queries consistently
filter on prefix subsets. Avoid creating redundant `{ country: 1 }` if the compound exists.

### Sort Direction in Compound Indexes

For compound indexes that serve sorts, each field's direction in the index must match the
sort direction **or** every field's direction must be reversed:

```js
// Index
db.events.createIndex({ category: 1, ts: -1 });

// Served sorts:
// .sort({ category: 1, ts: -1 })   ✅ exact match
// .sort({ category: -1, ts: 1 })   ✅ full inversion
// .sort({ category: 1, ts: 1 })    ❌ COLLSCAN or in-memory sort
```

---

## 3. Multikey Indexes — Indexing Arrays

MongoDB automatically creates a **multikey index** when any indexed field contains an array.
Each array element gets its own index entry.

```js
// Documents have shape: { tags: ["mongodb", "indexing", "performance"] }
db.articles.createIndex({ tags: 1 });
// MongoDB creates one entry per element — "mongodb", "indexing", "performance" all get entries.

// Works with array of subdocuments too
// { scores: [{ subject: "math", grade: 90 }, { subject: "english", grade: 85 }] }
db.students.createIndex({ "scores.grade": 1 });
```

### Multikey Bounds

When a query has predicates on an array field, MongoDB intersects multikey bounds:

```js
// { $elemMatch: { $gte: 70, $lte: 90 } } — bounds applied to the SAME element
db.students.find({ scores: { $elemMatch: { $gte: 70, $lte: 90 } } });
// vs
// { scores: { $gte: 70 } }, { scores: { $lte: 90 } } — separate bounds, may produce false positives
// that are filtered during FETCH stage
```

### Parallel Arrays Restriction

A compound index **cannot** index two fields that are both arrays in the same document:

```js
// Document: { a: [1,2], b: [3,4] }
db.col.createIndex({ a: 1, b: 1 });
// ❌ MongoServerError: cannot index parallel arrays [b] [a]
// MongoDB rejects document insertion OR the index build fails
```

Design around this: embed the array relationship inside a single subdocument array field.

---

## 4. Partial Indexes

A partial index only indexes documents that match a `partialFilterExpression`. This is the
preferred modern alternative to sparse indexes.

```js
// Only index orders that are "pending" — ignores completed and cancelled orders
db.orders.createIndex(
  { customerId: 1, createdAt: -1 },
  { partialFilterExpression: { status: "pending" } }
);
```

**Requirements:** queries that use a partial index must include the filter expression
(or a superset of it) in their predicate, otherwise MongoDB will not use the index.

```js
// Will use the index — query matches the partialFilterExpression
db.orders.find({ customerId: "abc", status: "pending" }).sort({ createdAt: -1 });

// Will NOT use the index — status is absent from query filter
db.orders.find({ customerId: "abc" }).sort({ createdAt: -1 });
```

### Use Cases

| Use Case | partialFilterExpression |
|---|---|
| Active users only | `{ active: true }` |
| Non-null emails | `{ email: { $exists: true } }` |
| High-value orders | `{ amount: { $gt: 1000 } }` |
| Pending queue | `{ status: { $in: ["pending","retry"] } }` |

### Storage Savings

A partial index on 10% of documents is ~90% smaller than a full index, with proportionally
faster builds, lower memory pressure, and reduced write amplification.

---

## 5. Sparse Indexes

A sparse index omits documents where the indexed field does not exist (or is `null`).

```js
db.users.createIndex({ phoneNumber: 1 }, { sparse: true });
// Documents without phoneNumber are excluded from the index
```

### Sparse vs Partial

| Feature | Sparse | Partial |
|---|---|---|
| Definition | Exclude docs where field is missing/null | Exclude docs not matching expression |
| Expressiveness | Limited — field existence only | Full query expression (`$gt`, `$in`, etc.) |
| Recommendation | Legacy; use partial instead | **Preferred** |
| Unique constraint | Can enforce uniqueness among docs that have the field | Can enforce uniqueness among filtered docs |

**When to prefer sparse:** you must support MongoDB < 3.2 (partial indexes require 3.2+)
or need a quick "skip nulls" index without a filter expression. For MongoDB 3.2+, use partial.

**Gotcha:** a sparse index will not be used for queries that include a sort on the sparse
field unless the query predicate also restricts that field to non-null values.

---

## 6. TTL Indexes — Automatic Document Expiration

TTL (Time-To-Live) indexes let MongoDB automatically delete documents after a specified
number of seconds past a date field.

```js
// Expire session documents 30 minutes after their createdAt timestamp
db.sessions.createIndex(
  { createdAt: 1 },
  { expireAfterSeconds: 1800 }
);

// Expire at an absolute date stored in the document (set expireAfterSeconds: 0)
// Document: { expireAt: ISODate("2026-06-01T00:00:00Z") }
db.jobs.createIndex(
  { expireAt: 1 },
  { expireAfterSeconds: 0 }
);
```

### Requirements

- The indexed field must be a **BSON Date** type or an array of Date values.
- If the field is an array, the earliest (minimum) date is used for expiration.
- Documents are deleted by a background task that runs **every 60 seconds** — do not
  rely on sub-minute precision.
- TTL indexes cannot be compound indexes.
- TTL indexes cannot be created on capped collections.

### Changing TTL

```js
db.runCommand({
  collMod: "sessions",
  index: { keyPattern: { createdAt: 1 }, expireAfterSeconds: 3600 }
});
```

### Atlas Consideration

On Atlas, TTL deletions count against your oplog and IOPS budget. For high-volume
expiration, consider sharding on the TTL field so deletions are distributed.

---

## 7. Text Indexes — Full-Text Search

Text indexes tokenize string content, apply language-specific stemming, and support
the `$text` / `$search` query operator.

```js
// Single field
db.articles.createIndex({ body: "text" });

// Multiple fields with weights (higher weight = more relevant in score)
db.articles.createIndex(
  { title: "text", body: "text", tags: "text" },
  { weights: { title: 10, tags: 5, body: 1 }, default_language: "english" }
);

// Wildcard text index — all string fields
db.articles.createIndex({ "$**": "text" });
```

### Querying

```js
// Basic search
db.articles.find({ $text: { $search: "mongodb indexing" } });

// Exact phrase
db.articles.find({ $text: { $search: "\"compound index\"" } });

// Exclude term
db.articles.find({ $text: { $search: "indexes -sharding" } });

// Sort by relevance score
db.articles.find(
  { $text: { $search: "performance" } },
  { score: { $meta: "textScore" } }
).sort({ score: { $meta: "textScore" } });
```

### Text Index vs Atlas Search

| Feature | Text Index | Atlas Search (Lucene) |
|---|---|---|
| Deployment | Self-managed & Atlas | Atlas only |
| Languages | ~15 built-in stemmers | 40+ analyzers, custom |
| Fuzzy matching | No | Yes (`fuzzy`) |
| Autocomplete | No | Yes (`autocomplete`) |
| Facets | No | Yes |
| Relevance tuning | Weight per field | Full scoring control |
| Query syntax | `$text` operator | `$search` aggregation stage |
| Recommendation | Simple substring search | Production full-text |

Only **one text index** per collection is allowed.

---

## 8. Wildcard Indexes — Flexible Schema Indexing

Wildcard indexes use `$**` to index all fields (or a projection subset) in a document,
useful for workloads with unpredictable or polymorphic field sets.

```js
// Index every field in every document
db.catalog.createIndex({ "$**": 1 });

// Index only fields under "attributes" subtree
db.catalog.createIndex({ "attributes.$**": 1 });

// Wildcard projection — include specific fields, exclude others
db.catalog.createIndex(
  { "$**": 1 },
  { wildcardProjection: { "attributes": 1, "metadata": 1 } }
);

// Compound wildcard index (MongoDB 7.0+)
// Fixed prefix fields + wildcard suffix
db.catalog.createIndex({ category: 1, "attributes.$**": 1 });
```

### How Wildcard Indexes Work

Each leaf field in a document generates a separate index entry. A document with
`{ a: 1, b: { c: 2, d: 3 } }` produces entries for `a`, `b.c`, and `b.d`.

### Restrictions

- Cannot replace a compound index for queries filtering multiple specific fields —
  the planner will only use the wildcard index for **one field** per query.
- Wildcard indexes are always **sparse** (missing fields are not indexed).
- Multikey semantics apply — arrays create multiple entries.
- `_id` is excluded by default; include explicitly in `wildcardProjection`.

### Performance Trade-offs

| Aspect | Wildcard Index | Targeted Compound |
|---|---|---|
| Index size | Very large (all fields) | Small (specific fields) |
| Build time | Long | Short |
| Query coverage | Any single field | ESR-optimized multi-field |
| Best fit | Polymorphic, dynamic schemas | Known query patterns |

---

## 9. Hashed Indexes — Sharding by Hash

Hashed indexes store a hash of the field value rather than the value itself. They are
primarily used as shard keys for even data distribution.

```js
// Create a hashed index on _id (common shard key pattern)
db.events.createIndex({ _id: "hashed" });

// Use as shard key
sh.shardCollection("mydb.events", { _id: "hashed" });
```

### Characteristics

- Support **equality queries only** — range queries (`$gt`, `$lt`) cannot use hashed indexes.
- Hash is computed deterministically; queries with `$eq` resolve to one hash bucket.
- A hashed index on `_id` distributes writes evenly across shards, avoiding hotspots.
- **Compound hashed shard keys (MongoDB 4.4+):** a shard key may combine a range prefix
  with one hashed component — e.g., `{ country: 1, _id: "hashed" }` — giving locality on
  the range field while distributing the hash field evenly. Only **one** field in a shard key
  may be hashed; you cannot hash two fields in the same key.
- Do not use hashed indexes for range-heavy workloads — switch to ranged sharding instead.

```js
// Equality queries work fine
db.events.find({ _id: ObjectId("...") });  // uses hashed index

// Range query — full shard scatter
db.events.find({ _id: { $gt: ObjectId("...") } });  // COLLSCAN on each shard
```

---

## 10. 2dsphere Indexes — Geospatial Queries

2dsphere indexes support queries on GeoJSON geometry objects and legacy coordinate pairs
on a spherical Earth model.

```js
// GeoJSON document shape
// { location: { type: "Point", coordinates: [lng, lat] } }
db.places.createIndex({ location: "2dsphere" });

// Compound with 2dsphere
db.places.createIndex({ category: 1, location: "2dsphere" });
```

### Core Geospatial Operators

```js
// $geoNear — nearest points (requires 2dsphere index)
db.places.aggregate([
  {
    $geoNear: {
      near: { type: "Point", coordinates: [-73.9857, 40.7484] },
      distanceField: "dist.calculated",
      maxDistance: 5000,           // meters
      spherical: true,
      query: { category: "restaurant" }
    }
  }
]);

// $geoWithin — points inside a polygon
db.places.find({
  location: {
    $geoWithin: {
      $geometry: {
        type: "Polygon",
        coordinates: [[ [-74, 40], [-73, 40], [-73, 41], [-74, 41], [-74, 40] ]]
      }
    }
  }
});

// $nearSphere — near a point, sorted by distance
db.places.find({
  location: {
    $nearSphere: {
      $geometry: { type: "Point", coordinates: [-73.9857, 40.7484] },
      $maxDistance: 1000
    }
  }
});
```

### GeoJSON Types Supported

`Point`, `LineString`, `Polygon`, `MultiPoint`, `MultiLineString`, `MultiPolygon`,
`GeometryCollection`.

### Notes

- Coordinates are `[longitude, latitude]` (GeoJSON order — opposite of most map UIs).
- 2dsphere supports Big Polygon (> 180°). Legacy `2d` indexes (flat earth) do not.
- `$geoNear` must be the **first stage** in an aggregation pipeline.

---

## 11. Unique Indexes

Unique indexes enforce that no two documents share the same value for the indexed field(s).

```js
// Simple unique
db.users.createIndex({ email: 1 }, { unique: true });

// Compound unique — combination must be unique, individual fields need not be
db.teamMembers.createIndex({ teamId: 1, userId: 1 }, { unique: true });

// Partial unique — uniqueness only among documents matching the filter
// (allows multiple docs with null email, but unique among those with email)
db.users.createIndex(
  { email: 1 },
  {
    unique: true,
    partialFilterExpression: { email: { $exists: true } }
  }
);
```

### Unique + Sparse

A sparse unique index allows multiple documents to **omit** the field entirely while
enforcing uniqueness among those that have it. Partial unique is more expressive.

```js
db.users.createIndex({ phoneNumber: 1 }, { unique: true, sparse: true });
```

### Duplicate Key Errors

```
MongoServerError: E11000 duplicate key error collection: mydb.users index: email_1
dup key: { email: "user@example.com" }
```

Handle with `{ upsert: true }` + `$setOnInsert` pattern, or use `writeConcern` + retry logic
for optimistic-concurrency scenarios.

---

## 12. Index Intersection

MongoDB can combine two separate indexes at query time to satisfy a query that filters
on two different fields — without a compound index.

```js
// Two single-field indexes
db.orders.createIndex({ status: 1 });
db.orders.createIndex({ customerId: 1 });

// Query may trigger intersection
db.orders.find({ status: "pending", customerId: "abc" });
// explain() IXSCAN on each, then AND_SORTED or AND_HASH stage
```

### Compound Index vs Intersection

| Aspect | Compound Index | Index Intersection |
|---|---|---|
| Performance | Faster — single B-tree traversal | Slower — two traversals + merge |
| Storage | One index structure | Two separate structures |
| Write overhead | One write per doc | Two writes per doc |
| Flexibility | Fixed field order required | Any two single-field indexes |
| Recommendation | **Prefer compound** for known access patterns | Useful when write patterns favor separate indexes |

MongoDB's query planner will choose intersection only when it estimates it to be faster
than either single index alone. In practice, a well-designed compound index almost always
outperforms intersection. Use `explain("executionStats")` to verify.

**Index intersection does not work for sort.** If a query needs to sort, a compound index
covering equality + sort is required.

---

## 13. Index Build Strategies

### Modern Index Builds (MongoDB 4.2+)

Since 4.2, all index builds use a **hybrid** approach that replaced the old
foreground/background distinction:

- Takes an intent lock (not exclusive) during the bulk phase — reads and writes continue.
- Briefly takes an exclusive lock at the start and end to set up/commit the index.
- Progress is written to the oplog and replicated to secondaries automatically.

> **`{ background: true }` is deprecated and ignored since MongoDB 4.2.** The option is
> accepted without error but has no effect — all builds now use the hybrid approach. Remove
> it from any legacy scripts to avoid confusion.

```js
// Default — hybrid build, replicated
db.orders.createIndex({ customerId: 1 });

// LEGACY (no-op since 4.2 — remove from new code):
// db.orders.createIndex({ customerId: 1 }, { background: true });

// Check build progress
db.currentOp({ op: "command", "command.createIndexes": { $exists: true } });

// Kill a running build
db.killOp(<opId>);
```

### Rolling Index Builds (Replica Sets)

Rolling builds build the index on one member at a time (starting with secondaries),
avoiding the performance impact of a coordinated build:

**Manual rolling build steps:**
1. Run `rs.freeze(300)` on the secondary to prevent it from calling elections during the procedure.
2. Remove it from the replica set with `rs.remove("<host:port>")`.
3. Restart `mongod` in standalone mode on a different port: `mongod --port 27217`.
4. Build the index: `db.collection.createIndex(...)` against the standalone instance.
5. Shut it down and restart as a replica set member; rejoin with `rs.add("<host:port>")`.
6. Repeat for each remaining secondary, then step down and reconfigure the primary.

**Atlas rolling index:**
```bash
# Atlas CLI
atlas api rollingIndex createRollingIndex \
  --projectId <projectId> \
  --clusterName <clusterName> \
  --key '{"field": "customerId", "type": "1"}'
```

Rolling builds: lower performance impact, but reduced cluster resiliency during build.
Use when CPU > (N-1)/N-10% or WiredTiger cache fill > 90%.

### Atlas Index Management UI

Atlas provides in-UI index creation with rolling build toggle, performance advisor
recommendations, and redundant/unused index reporting.

---

## 14. Index Size, Selectivity, and Covering Indexes

### Selectivity

Selectivity measures what fraction of the collection an index scan must touch to answer a
query. **A highly selective index returns very few documents** (small fraction = high selectivity
= good). A low-selectivity index touches most of the collection, at which point a full
collection scan is often cheaper.

```js
// Estimate selectivity ratio
const total = db.orders.countDocuments();
const matching = db.orders.countDocuments({ status: "pending" });
const ratio = matching / total;
// ratio = 0.05 (5% of docs match) → high selectivity, index helps a lot
// ratio = 0.80 (80% of docs match) → low selectivity, COLLSCAN may be faster
```

**Rule of thumb:** an index is beneficial when the ratio < ~20-30% of the collection.
Below that threshold, a collection scan is often faster due to document prefetching.

### Covering Indexes (Index-Only Queries)

A query is "covered" when all requested fields — both filter and projection — exist in
the index. MongoDB returns results **without touching the collection** (no FETCH stage).

```js
// Index
db.users.createIndex({ country: 1, email: 1, name: 1 });

// Covered query — all projected fields are in the index
db.users.find(
  { country: "US" },
  { email: 1, name: 1, _id: 0 }   // _id must be explicitly excluded
);
// explain() shows: "totalDocsExamined": 0, stage: "PROJECTION_COVERED"
```

**_id caveat:** `_id` is returned by default. If `_id` is not in the index, you must
exclude it with `_id: 0` to achieve a covering query.

### Reading explain() Output

```js
db.orders.find({ customerId: "abc" }).explain("executionStats");
// Key fields:
// executionStats.totalDocsExamined — 0 means covered
// executionStats.totalKeysExamined — index entries scanned
// executionStats.executionTimeMillis — wall time
// winningPlan.stage — COLLSCAN, IXSCAN, FETCH, PROJECTION_COVERED
// winningPlan.inputStage.indexName — which index was chosen
```

### Index Memory Footprint

WiredTiger stores indexes in a B-tree. The working set of the index (frequently accessed
pages) should fit in the WiredTiger cache. Check:

```js
db.orders.stats().indexSizes;
// { "_id_": 12345, "customerId_1": 98765, ... }
```

Indexes that do not fit in cache will cause disk I/O on every lookup — a common cause of
p99 latency spikes under load.

---

## 15. Hidden Indexes — Safe Removal Testing

Hidden indexes (MongoDB 4.4+) allow you to prevent the query planner from using an index
**without dropping it**. This lets you safely evaluate the impact of removing an index in
production before committing.

```js
// Hide an existing index — query planner ignores it immediately
db.orders.hideIndex("customerId_1");

// Create a new index already hidden (build it, but don't activate it yet)
db.orders.createIndex({ status: 1 }, { hidden: true });

// Un-hide (re-activate) the index
db.orders.unhideIndex("status_1");

// Verify visibility — check "hidden" field in listIndexes output
db.orders.getIndexes();
// Hidden index shows: { ..., "hidden": true }
```

### Workflow for Safe Index Removal

1. Hide the candidate index with `hideIndex()`.
2. Monitor query performance for 24–72 hours (cover at least one full business cycle).
3. Check `$indexStats` — confirm no queries are using the index.
4. If performance is acceptable: drop it with `dropIndex()`.
5. If performance degrades: `unhideIndex()` to restore instantly — no rebuild needed.

### Constraints

- Hidden indexes still consume write overhead and storage — they are not free.
- `_id` index cannot be hidden.
- Hidden indexes still count toward collection index limits — hiding is for testing removal impact, not for bypassing limits.

---

## 16. hint() — Forcing a Specific Index

Use `hint()` to override the query planner and force a specific index. Useful when the
planner makes a suboptimal choice or when testing index effectiveness.

```js
// Force by index key pattern
db.orders.find({ status: "pending" }).hint({ status: 1, createdAt: -1 });

// Force by index name
db.orders.find({ status: "pending" }).hint("status_1_createdAt_-1");

// Force a collection scan (no index)
db.orders.find({ status: "pending" }).hint({ $natural: 1 });
```

### When to Use hint()

| Situation | Action |
|---|---|
| Planner picks wrong index on complex query | `hint()` the correct ESR compound index |
| Testing a new index against an existing one | `hint()` each and compare `explain("executionStats")` |
| Verifying a covering index is actually used | `hint()` + check `totalDocsExamined === 0` |
| Benchmarking collection scan vs index scan | `hint({ $natural: 1 })` for baseline |

### Caution

`hint()` bypasses the query planner entirely — if the hinted index does not contain the
query fields, MongoDB will still return correct results but may perform a full index scan
instead of an efficient point lookup, degrading performance. Always validate with `explain()`
after adding `hint()` to application code.

> **Do not use `hint()` as a permanent fix.** If the planner consistently picks the wrong
> index, the root cause is usually a missing or mis-ordered compound index. Redesign the
> index using the ESR rule rather than patching with `hint()`.

---

## 17. Anti-Patterns

### Anti-Patterns Table

| Anti-Pattern | Problem | Remedy |
|---|---|---|
| **Too many indexes** | Write amplification; every insert/update writes to all indexes | Audit with `$indexStats`; drop unused indexes |
| **Low-selectivity indexes** | Index scan touches most of the collection; COLLSCAN may be faster | Check selectivity; add compound fields to improve discrimination |
| **Missing compound index** | Relying on index intersection instead of a proper ESR compound | Create compound index matching the query's equality+sort+range pattern |
| **Wrong ESR order** | Range field before sort field — in-memory sort required | Reorder fields: Equality → Sort → Range |
| **Indexing all fields** | Wildcard index used when specific fields are known | Replace with targeted compound indexes |
| **Unused indexes** | Stale indexes from removed query patterns still cost write IOPS | `db.collection.aggregate([{ $indexStats: {} }])` → drop `accesses.ops == 0` |
| **Duplicate indexes** | `{ a: 1 }` and `{ a: 1, b: 1 }` — the single-field is redundant | Drop the shorter prefix if the compound covers all its use cases |
| **Indexing large BLOBs** | Indexing a field with large strings wastes index memory | Index a hash or truncated form; store raw value in document only |
| **No TTL on ephemeral data** | Sessions, tokens, queue entries accumulate forever | Add TTL index on date field; set appropriate `expireAfterSeconds` |
| **Unique without partial on optional field** | Multiple null-field docs violate unique constraint | Use `{ unique: true, partialFilterExpression: { field: { $exists: true } } }` |
| **Parallel array compound** | Two array fields in same compound index — insert error | Denormalize or embed related arrays into subdocument array |
| **Text index on high-cardinality field** | Text index on millions of unique tokens — huge index, poor relevance | Use Atlas Search for production full-text; keep text index for simple cases |
| **Foreground builds on production** | (Pre-4.2 habit) Locks collection during build | Use default hybrid build or rolling build on Atlas |
| **Hashed index for range queries** | Hashed indexes only serve equality — range causes scatter-gather | Use ranged index or ranged shard key for range-heavy access patterns |
| **Ignoring explain() before shipping** | Query uses wrong index or COLLSCAN on hot path | Always run `explain("executionStats")` on new queries before deploying |

### Detecting Unused Indexes

```js
// List all indexes with access stats — run on each replica set member
db.orders.aggregate([{ $indexStats: {} }]);
// Fields: name, host, accesses.ops (query count), accesses.since (reset timestamp)

// Zero-ops indexes that have existed for > 24h are candidates for removal
// Always check on secondaries too — replica sets may route reads differently
```

### Index Bloat and Fragmentation

Long-running update-heavy workloads can fragment B-tree pages. Use:

```js
db.runCommand({ compact: "orders" });
// WARNING: Takes an exclusive lock on self-managed; avoid on primary
// Atlas: compact is triggered via Atlas UI or API without downtime
```

---

## 18. Time Series Collection Index Constraints

Time series collections (MongoDB 5.0+) have a fundamentally different index model. **Use this section as a quick-reference when advising on indexes for a time series collection; defer to `mongodb-time-series` for full context.**

**Key differences from regular collection indexes:**

| Index Type | Regular Collection | Time Series Collection |
|------------|-------------------|----------------------|
| Default `_id` index | Auto-created | Not created |
| Unique indexes | Supported | **Not supported** |
| Text indexes | Supported | **Not supported** |
| Multikey | On any array field | `metaField` only |
| Sparse | On any field | `metaField` only |
| 2d / 2dsphere | On any field | `metaField` only |
| Partial (`partialFilterExpression`) | Any field | `metaField` only (MongoDB 7.0+) |
| Hashed on timeField | Supported | **Not supported as secondary index; also deprecated as shard key in 8.0** |
| TTL (`expireAfterSeconds`) | Via `createIndex` | Via `createCollection` or `collMod` — **not `createIndex`** |

**Clustered range index (automatic):** MongoDB creates a compound clustered index on `(metaField, timeField)` automatically. This drives bucket-level pruning — queries that filter on `metaField` + `timeField` range use this index at the bucket level without needing an explicit secondary index.

**Adding secondary indexes (compound pattern):**
```javascript
// Best pattern: metaField sub-field first, timeField last
db.sensor_readings.createIndex({ "metadata.sensorId": 1, "timestamp": 1 })

// Measurement field index (supported but rarely needed — bucket pruning handles time ranges)
db.sensor_readings.createIndex({ "metadata.location": 1, "temperature": 1 })
```

**ESR rule still applies** to time series compound indexes on `metaField` sub-fields + measurement fields. Place equality fields first, sort fields second, range fields last.

**TTL on time series** is set at collection level (`expireAfterSeconds` in `createCollection`) or modified via `collMod` — never via `createIndex`. Tiered TTL with `partialFilterExpression` on `metaField` is supported from MongoDB 7.0.

---

## References

1. [MongoDB Indexes Overview](https://www.mongodb.com/docs/manual/indexes/)
2. [Compound Indexes](https://www.mongodb.com/docs/manual/core/index-compound/)
3. [ESR Rule](https://www.mongodb.com/docs/manual/tutorial/equality-sort-range-rule/)
4. [Multikey Indexes](https://www.mongodb.com/docs/manual/core/indexes/index-types/index-multikey/)
5. [Partial Indexes](https://www.mongodb.com/docs/manual/core/indexes/index-types/index-partial/)
6. [Sparse Indexes](https://www.mongodb.com/docs/manual/core/indexes/index-types/index-sparse/)
7. [TTL Indexes](https://www.mongodb.com/docs/manual/core/indexes/index-types/index-ttl/)
8. [Text Indexes](https://www.mongodb.com/docs/manual/core/indexes/index-types/index-text/)
9. [Wildcard Indexes](https://www.mongodb.com/docs/manual/core/indexes/index-types/index-wildcard/)
10. [Hashed Indexes](https://www.mongodb.com/docs/manual/core/indexes/index-types/index-hashed/)
11. [2dsphere Indexes](https://www.mongodb.com/docs/manual/core/indexes/index-types/index-2dsphere/)
12. [Unique Indexes](https://www.mongodb.com/docs/manual/core/index-unique/)
13. [Index Intersection](https://www.mongodb.com/docs/manual/core/index-intersection/)
14. [Index Builds on Populated Collections](https://www.mongodb.com/docs/manual/core/index-creation/)
15. [Rolling Index Builds](https://www.mongodb.com/docs/manual/core/rolling-index-builds/)
16. [Atlas Rolling Index API](https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/group/endpoint-rolling-index)
17. [Hidden Indexes](https://www.mongodb.com/docs/manual/core/index-hidden/)
18. [cursor.hint()](https://www.mongodb.com/docs/manual/reference/method/cursor.hint/)
19. [Compound Hashed Shard Keys](https://www.mongodb.com/docs/manual/core/hashed-sharding/#compound-hashed-shard-keys)
