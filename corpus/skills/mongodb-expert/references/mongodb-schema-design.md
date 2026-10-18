<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-schema-design` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-schema-design
version: "1.1"
updated: "2026-05-29"
description: >-
  MongoDB schema design expert -- embedding vs referencing trade-offs, 12 canonical design patterns
  (polymorphic, bucket, outlier, attribute, computed, extended reference, subset, approximation,
  schema versioning, document versioning, pre-allocation, tree), tree structures (parent reference,
  child reference, materialized paths, nested sets), schema versioning strategies, $jsonSchema
  document validation, anti-patterns (massive arrays, unbounded growth, bloated documents, excessive
  $lookup, unnecessary indexes), time-series collection design, and domain-specific modeling for
  e-commerce, social media, and IoT use cases.
  TRIGGER: designing a MongoDB schema, choosing between embedding and referencing, applying design
  patterns (bucket, outlier, computed, extended reference, subset, attribute, polymorphic),
  modeling tree or hierarchical data, setting up $jsonSchema validation, avoiding anti-patterns
  (unbounded arrays, bloated documents, excessive $lookup), modeling e-commerce, social media,
  or IoT data, or deciding between native time-series collections and the manual bucket pattern.
  SKIP: query optimization and index design without a schema-design angle (use mongodb-query-performance);
  sharding key selection (use mongodb-sharding); native time-series collection internals and TTL
  beyond schema decisions (use mongodb-time-series); field-level encryption impact on schema
  (use mongodb-encryption); general MQL or aggregation questions (use mongodb-expert).
triggers:
  - mongodb schema
  - schema design
  - data model mongodb
  - embedding vs referencing
  - document model
  - mongodb patterns
  - polymorphic pattern
  - bucket pattern
  - outlier pattern
  - attribute pattern
  - computed pattern
  - extended reference
  - subset pattern
  - tree structure mongodb
  - materialized paths
  - nested sets
  - schema versioning
  - $jsonSchema
  - document validation
  - mongodb anti-pattern
  - unbounded array
  - 16MB limit
  - e-commerce schema
  - social media schema
  - IoT schema
  - time-series schema
  - mongodb data modeling
when_not_to_use:
  - Query optimization and index design without a schema-design angle (use mongodb-query-performance)
  - Sharding key selection or chunk distribution strategy (use mongodb-sharding)
  - Native time-series collection internals, TTL mechanics, or migration (use mongodb-time-series)
  - Field-level encryption impact on schema structure (use mongodb-encryption)
  - General MQL queries, aggregation pipelines, or explain analysis (use mongodb-expert)
  - Atlas Search or Vector Search index design (use mongodb-search-ai)
related_skills:
  - mongodb-query-performance
  - mongodb-time-series
  - mongodb-sharding
  - mongodb-encryption
  - mongodb-search-ai
  - mongodb-data-lifecycle
  - mongodb-performance-troubleshooting
  - mongodb-aggregation-stages-deep
---

# MongoDB Schema Design -- Expert Reference

## Overview

MongoDB schema design is fundamentally different from relational database design. Instead of normalizing data into tables and joining at query time, MongoDB encourages designing schemas around application access patterns -- how data is read and written most frequently. The document model provides flexibility to embed related data, reference across collections, or use hybrid approaches depending on the workload.

The cardinal rule: **design for your queries, not just your data.** Start by listing the most frequent queries, then design the schema to serve those queries with minimal operations.

### Key Principles

- **Embed first.** Only introduce references and patterns when a specific problem arises -- document size, update complexity, or query performance.
- **Analyze read/write ratios.** Embed for read-heavy workloads; reference for write-heavy workloads.
- **Respect the 16 MB document size limit.** This is a hard BSON limit; design accordingly.
- **Data that is accessed together should be stored together.** Co-locate data that is always read in the same query.
- **Avoid premature optimization.** Start simple, measure, then apply patterns as bottlenecks emerge.

---

## 1. Embedding vs. Referencing

### When to Embed

Embedding stores related data within a single document, eliminating the need for joins.

**Embed when:**
- Data is always accessed together (1:1 or 1:few relationships)
- The embedded data is relatively small and bounded
- The embedded data does not change independently
- Read performance is the priority
- Data has a clear ownership hierarchy (child data belongs to one parent)

```javascript
// Embedded: address belongs to a single user
{
  _id: ObjectId("..."),
  name: "Alice Chen",
  email: "alice@example.com",
  address: {
    street: "123 Main St",
    city: "Portland",
    state: "OR",
    zip: "97201"
  }
}
```

**Advantages:** Single read operation, atomic updates, no joins needed, strong data locality.

**Disadvantages:** Document size grows, duplicate data if shared across documents, cannot query embedded data independently at scale.

### When to Reference

Referencing stores a foreign key (_id) pointing to data in another collection.

**Reference when:**
- Data is shared across many documents (many-to-many relationships)
- The related data is large, changes frequently, or grows without bounds
- You need to query the related data independently
- Write performance is critical and updates would cascade to many embedded copies
- The related data exceeds what is practical for a single document

```javascript
// Referenced: orders reference a customer
// customers collection
{ _id: ObjectId("c1"), name: "Alice Chen", email: "alice@example.com" }

// orders collection
{
  _id: ObjectId("o1"),
  customerId: ObjectId("c1"),
  items: [ { sku: "WIDGET-01", qty: 3, price: 12.99 } ],
  total: 38.97,
  status: "shipped"
}
```

**Advantages:** Smaller documents, no duplication, independent queryability, supports unbounded growth.

**Disadvantages:** Requires $lookup or multiple queries, no atomic cross-document updates (without transactions), higher read latency for related data.

### Hybrid Approach

The most effective schemas often combine both strategies. Embed frequently accessed summary data while referencing the full details.

```javascript
// Order embeds a product snapshot but references the canonical product
{
  _id: ObjectId("o1"),
  customerId: ObjectId("c1"),
  items: [
    {
      productId: ObjectId("p1"),         // reference for full details
      name: "Premium Widget",            // embedded snapshot
      sku: "WIDGET-01",                  // embedded snapshot
      priceAtPurchase: 12.99,            // immutable snapshot
      qty: 3
    }
  ]
}
```

### Decision Matrix

| Factor | Embed | Reference |
|--------|-------|-----------|
| Relationship cardinality | 1:1, 1:few | 1:many, many:many |
| Data access pattern | Always together | Independently queried |
| Data size | Small, bounded | Large, unbounded |
| Update frequency | Rarely changes | Frequently changes |
| Data sharing | Belongs to one parent | Shared across documents |
| Consistency need | Atomic with parent | Eventual is acceptable |

Sources:
- [MongoDB Docs: Data Modeling](https://www.mongodb.com/docs/manual/data-modeling/)
- [Embedding vs Referencing Guide 2026](https://www.perfectiongeeks.com/blogs/mongodb-schema-design-patterns-2026)
- [How to Choose Between Embedding and Referencing](https://oneuptime.com/blog/post/2025-12-15-how-to-choose-between-embedding-and-referencing-in-mongodb/view)
- [MongoDB Schema Design Best Practices 2026](https://dbschema.com/blog/mongodb/mongodb-schema-design-2026/)

---

## 2. Canonical Design Patterns

MongoDB recognizes 12+ design patterns that address common data modeling challenges. Each pattern solves a specific problem; patterns are often combined.

### 2.1 Polymorphic Pattern

**Problem:** Documents with more similarities than differences need to be stored in a single collection despite structural variation.

**Solution:** Keep all document shapes in one collection, using a discriminator field (e.g., `type`) to distinguish shapes. Common fields are shared; type-specific fields vary.

```javascript
// Single "vehicles" collection with polymorphic documents
{ type: "car", make: "Toyota", model: "Camry", doors: 4, trunkCapacity: 15.1 }
{ type: "truck", make: "Ford", model: "F-150", towingCapacity: 13000, bedLength: 6.5 }
{ type: "motorcycle", make: "Harley", model: "Sportster", engineCC: 1200 }
```

**Use cases:** Product catalogs with varied attributes, activity feeds with mixed event types, multi-tenant systems, content management (articles, videos, podcasts in one collection).

**Trade-offs:** Simple to implement; queries run across a single collection; type-specific indexes may be needed using partial indexes.

### 2.2 Attribute Pattern

**Problem:** Large documents have many similar fields, but only a subset is commonly queried or sorted. Creating separate indexes for each field is expensive.

**Solution:** Restructure similar fields into an array of key-value pairs, then create a single compound index on the key and value fields.

```javascript
// Before: many top-level fields
{ title: "Film A", director: "X", release_USA: "2024-01-15", release_UK: "2024-02-01", release_JP: "2024-03-10" }

// After: attribute pattern
{
  title: "Film A",
  director: "X",
  releases: [
    { territory: "USA", date: ISODate("2024-01-15") },
    { territory: "UK",  date: ISODate("2024-02-01") },
    { territory: "JP",  date: ISODate("2024-03-10") }
  ]
}
// One index: db.films.createIndex({ "releases.territory": 1, "releases.date": 1 })
```

**Use cases:** Products with variable specifications, documents with many date/metric fields, localization fields.

**Trade-offs:** Fewer indexes needed, simpler queries; requires restructuring existing data.

### 2.3 Bucket Pattern

**Problem:** High-frequency streaming data (IoT sensors, logs, financial ticks) generates millions of small documents, increasing storage overhead and index size.

**Solution:** Group measurements into time-bounded bucket documents. Each bucket holds an array of readings for a fixed interval.

```javascript
{
  sensorId: "A1234",
  startTime: ISODate("2025-01-15T10:00:00Z"),
  endTime:   ISODate("2025-01-15T10:59:59Z"),
  count: 60,
  measurements: [
    { ts: ISODate("2025-01-15T10:00:00Z"), temp: 22.1, humidity: 45 },
    { ts: ISODate("2025-01-15T10:01:00Z"), temp: 22.3, humidity: 44 },
    // ... up to 60 readings per bucket
  ],
  summary: { avgTemp: 22.4, minTemp: 21.8, maxTemp: 23.1 }
}
```

**Use cases:** IoT sensor data, application logs, financial time-series, clickstream analytics.

**Trade-offs:** Dramatically reduces document count and index size; pre-aggregated summaries speed reads; requires application logic to manage bucket boundaries. Consider MongoDB 5.0+ native time-series collections as a first choice.

### 2.4 Computed Pattern

**Problem:** Read-intensive queries repeatedly compute the same aggregations (totals, averages, counts) from raw data, wasting CPU cycles.

**Solution:** Pre-compute and store derived values, updating them incrementally on writes rather than recalculating on every read.

```javascript
// Store pre-computed stats on the product document
{
  _id: ObjectId("p1"),
  name: "Premium Widget",
  reviews: [ /* ... */ ],
  stats: {
    totalReviews: 1247,
    averageRating: 4.3,
    ratingDistribution: { 1: 23, 2: 45, 3: 112, 4: 389, 5: 678 },
    lastReviewDate: ISODate("2025-06-01")
  }
}

// On new review, increment counters with $inc; recompute averageRating from totals in a separate step
db.products.updateOne(
  { _id: ObjectId("p1") },
  {
    $inc: { "stats.totalReviews": 1, "stats.ratingDistribution.5": 1 },
    $set: { "stats.lastReviewDate": new Date() }
  }
)
```

**Use cases:** Dashboard metrics, product ratings, leaderboards, report summaries, real-time counters.

**Trade-offs:** Dramatically faster reads; slightly more complex writes; may need periodic reconciliation to prevent drift.

### 2.5 Outlier Pattern

**Problem:** A schema works for 99.9% of documents, but rare outliers (e.g., a celebrity user with millions of followers) would break the design.

**Solution:** Keep the standard schema for normal documents. For outliers, set a flag and overflow to a separate collection.

```javascript
// Normal user: followers fit in document
{ _id: "user123", name: "Regular User", followers: ["u1", "u2", "u3"], hasOverflow: false }

// Celebrity: followers overflow to separate collection
{ _id: "celeb1", name: "Celebrity", followers: ["u1", "u2", /* first 1000 */], hasOverflow: true }

// overflow collection
{ userId: "celeb1", batch: 2, followers: ["u1001", "u1002", /* next 1000 */] }
```

**Use cases:** Social media follower lists, bestseller book reviews, viral content with extreme engagement, event attendee lists.

**Trade-offs:** Keeps 99.9% of queries simple and fast; outlier handling adds application complexity; ad hoc queries on outliers may be slower.

### 2.6 Extended Reference Pattern

**Problem:** Frequently accessed related data lives in a different collection, requiring expensive $lookup joins on every read.

**Solution:** Duplicate the most frequently accessed fields from the referenced document into the referencing document.

```javascript
// Instead of $lookup to get customer name on every order render:
{
  _id: ObjectId("o1"),
  customerId: ObjectId("c1"),
  customerName: "Alice Chen",        // denormalized from customers
  customerEmail: "alice@example.com", // denormalized from customers
  items: [ /* ... */ ],
  total: 89.97
}
```

**Use cases:** Orders referencing customer details, invoices referencing product info, notifications referencing user names.

**Trade-offs:** Eliminates joins for common reads; introduces data duplication; requires update strategy when source data changes (accept staleness or propagate updates).

### 2.7 Subset Pattern

**Problem:** Documents contain large amounts of data, but most queries only need a small portion. The working set exceeds available RAM.

**Solution:** Split the document: keep the most-accessed subset in the main collection and the full data in a secondary collection.

```javascript
// Main product document: lean, fits in working set
{
  _id: ObjectId("p1"),
  name: "Premium Widget",
  price: 29.99,
  topReviews: [
    { user: "alice", rating: 5, text: "Amazing!", date: ISODate("2025-06-01") },
    { user: "bob", rating: 4, text: "Great value", date: ISODate("2025-05-28") }
  ],
  totalReviews: 1247
}

// Full reviews collection
{ productId: ObjectId("p1"), user: "alice", rating: 5, text: "Amazing!", date: ISODate("2025-06-01") }
// ... 1247 review documents
```

**Use cases:** Product pages showing top reviews, user profiles showing recent activity, dashboards showing latest metrics.

**Trade-offs:** Reduces working set size and improves cache hit ratio; requires managing two collections; additional query for full data.

### 2.8 Approximation Pattern

**Problem:** Exact counters on hot documents create write contention (every page view, every like).

**Solution:** Use probabilistic or batched updates to approximate counts, periodically reconciling with exact values.

```javascript
// Instead of incrementing on every view:
// Only write 1 in 10 views, multiply by 10 for display
if (Math.random() < 0.1) {
  db.posts.updateOne({ _id: postId }, { $inc: { viewCount: 10 } });
}
```

**Use cases:** Page view counters, social media like counts, analytics dashboards where exact precision is not critical.

**Trade-offs:** Dramatically reduces write load; statistically valid at scale; not suitable for financial or compliance-critical counts.

### 2.9 Schema Versioning Pattern

**Problem:** Schema requirements change over the application lifetime. Migrating millions of documents at once causes downtime.

**Solution:** Add a `schemaVersion` field. Application code handles multiple versions simultaneously. Migrate lazily, predictively, or incrementally.

```javascript
// Version 1: original schema
{ schemaVersion: 1, name: "Alice", address: "123 Main St, Portland, OR" }

// Version 2: structured address
{
  schemaVersion: 2,
  name: "Alice",
  address: { street: "123 Main St", city: "Portland", state: "OR", zip: "97201" }
}

// Application normalizes based on version
function normalizeUser(doc) {
  if (doc.schemaVersion === 1) {
    // parse string address into structured form
    return { ...doc, address: parseAddress(doc.address), schemaVersion: 2 };
  }
  return doc;
}
```

**Migration strategies:**
- **Eager**: Migrate all documents immediately (downtime risk)
- **Lazy**: Migrate when a document is read, write back the updated version
- **Predictive**: Migrate during low-load periods
- **Incremental**: Background batch migration of remaining old documents
- **None**: Permanently support multiple versions in application code

**Use cases:** Any long-lived application with evolving requirements, multi-version API support, zero-downtime deployments.

**Trade-offs:** Zero downtime for schema changes; multiple versions may coexist; may need duplicate indexes during migration.

Sources:
- [MongoDB Building with Patterns Summary](https://www.mongodb.com/company/blog/building-with-patterns-a-summary)
- [12 Key Design Patterns in MongoDB](https://lamthanhnguyen.github.io/database/12-key-design-pattern-in-mongodb-with-real-world-use-case/)
- [6 Patterns Every Developer Should Master](https://dev.to/piteradyson/mongodb-schema-design-6-patterns-every-developer-should-master-1dha)
- [MongoDB Schema Versioning Docs](https://www.mongodb.com/docs/manual/data-modeling/design-patterns/data-versioning/schema-versioning/)
- [Building with Patterns: Outlier Pattern](https://www.mongodb.com/company/blog/building-with-patterns-the-outlier-pattern)
- [Building with Patterns: Extended Reference](https://www.mongodb.com/company/blog/building-with-patterns-the-extended-reference-pattern)

---

## 3. Tree Structures

MongoDB supports four patterns for hierarchical data. Choose based on read/write ratio and query requirements.

### 3.1 Parent References

Each document stores its parent's `_id`. Simplest pattern; good for write-heavy trees.

```javascript
db.categories.insertMany([
  { _id: "MongoDB",      parent: "Databases" },
  { _id: "dbm",          parent: "Databases" },
  { _id: "Databases",    parent: "Programming" },
  { _id: "Languages",    parent: "Programming" },
  { _id: "Programming",  parent: "Books" },
  { _id: "Books",        parent: null }
])
db.categories.createIndex({ parent: 1 })

// Find children of "Databases"
db.categories.find({ parent: "Databases" })

// Find all descendants using $graphLookup
db.categories.aggregate([
  { $match: { _id: "Databases" } },
  { $graphLookup: {
      from: "categories",
      startWith: "$_id",
      connectFromField: "_id",
      connectToField: "parent",
      as: "descendants"
  }}
])
```

**Best for:** Frequently updated trees, simple parent lookups, org charts.

### 3.2 Child References

Each document stores an array of its children's `_id`s.

```javascript
db.categories.insertMany([
  { _id: "MongoDB",     children: [] },
  { _id: "Databases",   children: ["MongoDB", "dbm"] },
  { _id: "Programming", children: ["Databases", "Languages"] },
  { _id: "Books",       children: ["Programming"] }
])
```

**Best for:** Trees where you frequently need a node's immediate children; good for rendering menus or navigation.

### 3.3 Materialized Paths

Each document stores the full ancestry path as a string, enabling powerful regex queries.

```javascript
db.categories.insertMany([
  { _id: "Books",       path: null },
  { _id: "Programming", path: ",Books," },
  { _id: "Databases",   path: ",Books,Programming," },
  { _id: "MongoDB",     path: ",Books,Programming,Databases," }
])

// Find all descendants of "Programming"
db.categories.find({ path: /,Programming,/ })

// Find all ancestors of "MongoDB"
// Parse the path string: ",Books,Programming,Databases,"
```

**Best for:** Breadcrumb navigation, finding all descendants efficiently, category hierarchies.

### 3.4 Nested Sets

Each document stores left and right boundary values representing its position in a depth-first traversal.

```javascript
db.categories.insertMany([
  { _id: "Books",       left: 1,  right: 12 },
  { _id: "Programming", left: 2,  right: 11 },
  { _id: "Databases",   left: 3,  right: 6 },
  { _id: "MongoDB",     left: 4,  right: 5 },
  { _id: "Languages",   left: 7,  right: 10 }
])

// Find all descendants of "Programming" (left > 2 AND right < 11)
db.categories.find({ left: { $gt: 2 }, right: { $lt: 11 } })
```

**Best for:** Static or rarely-changing trees where subtree queries are frequent (product taxonomies, org charts). Very fast reads but expensive to update because moving a node requires recalculating boundary values for many nodes.

### Tree Pattern Comparison

| Pattern | Insert/Move | Find Children | Find Descendants | Find Ancestors |
|---------|-------------|---------------|------------------|----------------|
| Parent Reference | Fast | Index scan | $graphLookup | Recursive query |
| Child Reference | Moderate | Single read | Recursive | Not direct |
| Materialized Path | Moderate | Regex | Regex (fast) | Parse path string |
| Nested Sets | Slow (recalculate) | Range query | Range query (fast) | Range query |

Sources:
- [MongoDB Docs: Model Tree Structures](https://www.mongodb.com/docs/manual/applications/data-models-tree-structures/)
- [MongoDB Docs: Parent References](https://www.mongodb.com/docs/manual/tutorial/model-tree-structures-with-parent-references/)
- [How to Build MongoDB Tree Structures](https://oneuptime.com/blog/post/2026-01-30-mongodb-tree-structures/view)
- [Storing Tree Hierarchy Structures with MongoDB](https://medium.com/@V_Voronenko/storing-tree-like-hierarchy-structures-with-mongodb-part-2-bf35ad1f25ef)

---

## 4. Document Validation with $jsonSchema

MongoDB supports JSON Schema Draft 4 for enforcing document structure at the collection level. Validation occurs on insert and update operations.

### Creating a Validated Collection

```javascript
db.createCollection("users", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      title: "User Validation",
      required: ["name", "email", "role"],
      properties: {
        _id: { bsonType: "objectId" },
        name: {
          bsonType: "string",
          minLength: 1,
          maxLength: 100,
          description: "Full name, required"
        },
        email: {
          bsonType: "string",
          pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
          description: "Valid email address, required"
        },
        role: {
          bsonType: "string",
          enum: ["admin", "editor", "viewer"],
          description: "User role, must be one of admin/editor/viewer"
        },
        age: {
          bsonType: "int",
          minimum: 0,
          maximum: 150,
          description: "Age in years, optional"
        },
        address: {
          bsonType: "object",
          properties: {
            street: { bsonType: "string" },
            city: { bsonType: "string" },
            zip: { bsonType: "string", pattern: "^[0-9]{5}$" }
          }
        },
        tags: {
          bsonType: "array",
          items: { bsonType: "string" },
          maxItems: 20
        }
      },
      additionalProperties: false
    }
  }
})
```

### Supported Keywords

| Keyword | Purpose | Example |
|---------|---------|---------|
| `bsonType` | BSON data type constraint | `"string"`, `"int"`, `"objectId"`, `["string", "null"]` |
| `required` | Mandatory field list | `["name", "email"]` |
| `properties` | Per-field schema definitions | `{ name: { bsonType: "string" } }` |
| `enum` | Restrict to specific values | `["active", "inactive", "suspended"]` |
| `minimum` / `maximum` | Numeric range | `minimum: 0, maximum: 100` |
| `minLength` / `maxLength` | String length constraints | `minLength: 1, maxLength: 255` |
| `pattern` | Regular expression match | `"^[A-Z]{2}[0-9]{4}$"` |
| `additionalProperties` | Block unlisted fields | `false` (must include `_id` in properties) |
| `items` | Array element schema | `{ bsonType: "string" }` |
| `title` / `description` | Documentation in error messages | Human-readable validation rule context |

### Validation Levels and Actions

```javascript
// Moderate validation: only validates inserts and updates to already-valid documents
db.runCommand({
  collMod: "users",
  validationLevel: "moderate",   // "strict" (default) | "moderate"
  validationAction: "warn"       // "error" (default) | "warn"
})
```

- **strict** (default): Validates all inserts and updates
- **moderate**: Validates inserts and updates only when the existing document is already valid; silently allows updates to previously invalid documents
- **error** (default): Rejects invalid operations with a validation error
- **warn**: Allows the operation but logs a warning

### Combining with Query Operators

```javascript
db.createCollection("sales", {
  validator: {
    $and: [
      { $expr: { $lt: ["$discountedPrice", "$price"] } },
      { $jsonSchema: {
          bsonType: "object",
          required: ["price", "discountedPrice"],
          properties: {
            price: { bsonType: "decimal" },
            discountedPrice: { bsonType: "decimal" }
          }
      }}
    ]
  }
})
```

### Important Caveats

- When using `additionalProperties: false`, you **must** include `_id` in the `properties` object since MongoDB auto-generates it
- Validation cannot be applied to `admin`, `local`, or `config` database collections
- CSFLE and Queryable Encryption collections cannot use $jsonSchema on encrypted fields
- Use `title` and `description` fields to produce helpful error messages
- Allow null with array syntax: `bsonType: ["string", "null"]` for optional fields

Sources:
- [MongoDB Docs: Specify JSON Schema Validation](https://www.mongodb.com/docs/manual/core/schema-validation/specify-json-schema/)
- [MongoDB Docs: Schema Validation](https://www.mongodb.com/docs/manual/core/schema-validation/)
- [MongoDB Schema Validation Tutorial (DataCamp)](https://www.datacamp.com/tutorial/mongodb-schema-validation)
- [JSON Schema Validation Tips (MongoDB Docs)](https://www.mongodb.com/docs/manual/core/schema-validation/specify-json-schema/json-schema-tips/)

---

## 5. Anti-Patterns

MongoDB officially identifies five schema design anti-patterns. Detecting and correcting these is critical for production performance.

### 5.1 Unbounded Arrays (Massive Arrays)

**Problem:** Storing continuously growing arrays within a document. As the array grows, the document approaches the 16 MB BSON limit, indexes become bloated, and every append forces MongoDB to rewrite the entire document.

**Detection:** Documents with arrays containing thousands of elements; `$size` checks in monitoring queries.

**Fix:** Move array items to a child collection with a parent reference. Use the Bucket Pattern for time-series data. Use the Outlier Pattern for rare cases that exceed normal bounds.

```javascript
// ANTI-PATTERN: unbounded comments array
{ _id: "post1", comments: [ /* grows to 100,000+ */ ] }

// FIX: separate collection
// posts: { _id: "post1", commentCount: 87432 }
// comments: { postId: "post1", text: "...", author: "...", date: ... }
```

### 5.2 Bloated Documents

**Problem:** Storing all data about an entity in a single massive document when most queries only need a fraction of the fields. This wastes RAM and network bandwidth.

**Fix:** Apply the Subset Pattern. Keep frequently accessed fields in the main document; move the rest to a detail collection.

### 5.3 Excessive Collections

**Problem:** Creating too many collections (e.g., one per user or one per day) increases WiredTiger metadata overhead and storage engine resource consumption.

**Fix:** Use the Polymorphic Pattern to consolidate similar document types. Use the Bucket Pattern for time-partitioned data instead of per-period collections.

### 5.4 Excessive $lookup Operations

**Problem:** Over-normalizing data into many collections and relying on $lookup (the aggregation join) for every query. $lookup is expensive compared to embedded reads.

**Fix:** Denormalize frequently joined data using the Extended Reference Pattern. Embed data that is read together.

### 5.5 Unnecessary Indexes

**Problem:** Every index consumes RAM and slows down writes (inserts, updates, deletes). Unused indexes waste resources.

**Fix:** Audit indexes with `db.collection.aggregate([{ $indexStats: {} }])`. Drop indexes with zero or near-zero usage. Use compound indexes to cover multiple query patterns with fewer indexes.

### Additional Anti-Patterns (Common in Practice)

- **Deeply nested documents:** Beyond 3-4 levels of nesting, queries become unwieldy and updates require complex dot-notation paths. Flatten or restructure.
- **Storing large binaries inline:** Files over a few KB should use GridFS rather than inline BSON binary fields.
- **Using ObjectId as a business key:** ObjectIds are opaque identifiers. Use meaningful, indexed business keys alongside `_id` when needed.
- **Ignoring the working set:** If your most-queried data does not fit in RAM, performance degrades. Monitor with `db.serverStatus().wiredTiger.cache`.

Sources:
- [MongoDB Docs: Schema Design Anti-Patterns](https://www.mongodb.com/docs/manual/data-modeling/design-antipatterns/)
- [MongoDB Docs: Avoid Unbounded Arrays](https://www.mongodb.com/docs/manual/data-modeling/design-antipatterns/unbounded-arrays/)
- [Escaping MongoDB Schema Anti-Patterns (Medium)](https://medium.com/the-quick-learners/future-proofing-your-database-escaping-mongodb-schema-anti-patterns-b8dc6e7ed35d)
- [Optimizing MongoDB Schemas: Massive Arrays (Medium)](https://medium.com/@louistrinh/optimizing-mongodb-schemas-why-massive-arrays-can-cause-issues-4ebf8b715e31)

---

## 6. Time-Series Data Design

### Native Time-Series Collections (MongoDB 5.0+)

MongoDB provides purpose-built time-series collections that automatically bucket, compress, and index temporal data.

```javascript
db.createCollection("sensorReadings", {
  timeseries: {
    timeField: "timestamp",
    metaField: "metadata",
    granularity: "minutes"        // "seconds" | "minutes" | "hours"
  },
  expireAfterSeconds: 7776000     // 90-day TTL
})

// Insert a measurement
db.sensorReadings.insertOne({
  timestamp: new Date(),
  metadata: { sensorId: "A1234", location: "Building-3", floor: 2 },
  temperature: 22.4,
  humidity: 48.2,
  pressure: 1012.5
})
```

### Granularity Selection

| Granularity | Best For | Example |
|-------------|----------|---------|
| `seconds` | High-frequency data (> 1 reading/second) | Stock ticks, real-time telemetry |
| `minutes` | Moderate frequency (1 reading/minute) | Application monitoring, weather stations |
| `hours` | Low-frequency data (hourly or less) | Daily aggregates, utility meters |

Choose the granularity closest to the interval between consecutive measurements from the same source.

### Key Behaviors and Limitations

- MongoDB automatically creates a compound index on `metaField` + `timeField` (6.3+)
- Internally stored as columnar-optimized buckets (not visible to the user)
- **Update restrictions**: Only the `metaField` can be targeted in match expressions for updates
- **Sharding**: Use `metaField` for shard keys (using `timeField` is deprecated in MongoDB 8.0)
- Significant storage savings (often 5-10x) compared to standard collections for the same data

### Bucket Pattern Alternative (Pre-5.0)

For MongoDB versions before 5.0, or for custom bucketing needs, manually implement the Bucket Pattern:

```javascript
{
  sensorId: "A1234",
  bucket: "2025-01-15T10",        // hourly bucket key
  count: 60,
  measurements: [
    { ts: ISODate("2025-01-15T10:00:00Z"), temp: 22.1 },
    { ts: ISODate("2025-01-15T10:01:00Z"), temp: 22.3 }
  ],
  stats: { avg: 22.4, min: 21.8, max: 23.1, sum: 1344 }
}
```

Sources:
- [MongoDB Docs: Time Series Collections](https://www.mongodb.com/docs/manual/core/timeseries-collections/)
- [MongoDB Time Series Best Practices](https://www.mongodb.com/resources/products/capabilities/time-series-best-practices)
- [MongoDB Docs: Model IoT Data](https://www.mongodb.com/docs/manual/tutorial/model-iot-data/)

---

## 7. Domain-Specific Schema Design

### 7.1 E-Commerce

**Core collections:** products, users, carts, orders, reviews, inventory

```javascript
// Product catalog: polymorphic with embedded variants
{
  _id: ObjectId("p1"),
  type: "clothing",
  name: "Classic T-Shirt",
  slug: "classic-tshirt",
  brand: "Acme",
  price: { amount: 29.99, currency: "USD" },
  images: [{ url: "...", alt: "Front view", isPrimary: true }],
  variants: [
    { sku: "TS-BLK-M", color: "Black", size: "M", stock: 42 },
    { sku: "TS-BLK-L", color: "Black", size: "L", stock: 18 }
  ],
  attributes: [
    { k: "material", v: "100% Cotton" },
    { k: "weight", v: "180gsm" }
  ],
  stats: { avgRating: 4.3, totalReviews: 87, totalSold: 1243 }
}

// Order: immutable snapshot of purchase
{
  _id: ObjectId("o1"),
  userId: ObjectId("u1"),
  customerSnapshot: { name: "Alice", email: "alice@example.com" },
  items: [
    {
      productId: ObjectId("p1"),
      sku: "TS-BLK-M",
      nameAtPurchase: "Classic T-Shirt",
      priceAtPurchase: 29.99,
      qty: 2
    }
  ],
  total: 59.98,
  status: "shipped",
  shippingAddress: { /* embedded */ },
  timeline: [
    { status: "placed", at: ISODate("2025-06-01T10:00:00Z") },
    { status: "shipped", at: ISODate("2025-06-02T14:30:00Z") }
  ]
}
```

**Key decisions:**
- **Embed product snapshots in orders** -- prices and names change over time; orders must reflect what was purchased
- **Use the Attribute Pattern** for product specifications across categories
- **Separate reviews** into their own collection; embed a top-review subset on the product document
- **Shopping carts** can be a separate collection with TTL index for abandoned cart cleanup

### 7.2 Social Media

**Core collections:** users, posts, follows, reactions, feeds

```javascript
// User profile
{
  _id: ObjectId("u1"),
  username: "alice_dev",
  displayName: "Alice Chen",
  avatar: "https://...",
  bio: "Software engineer",
  stats: { followers: 1247, following: 342, posts: 89 },
  createdAt: ISODate("2024-01-15")
}

// Post with embedded author snapshot
{
  _id: ObjectId("post1"),
  author: {
    userId: ObjectId("u1"),
    username: "alice_dev",
    avatar: "https://..."
  },
  content: "Just shipped a new feature!",
  media: [{ type: "image", url: "https://...", alt: "Screenshot" }],
  stats: { likes: 42, comments: 7, shares: 3 },
  topComments: [
    { userId: ObjectId("u2"), username: "bob", text: "Nice work!", at: ISODate("...") }
  ],
  totalComments: 7,
  createdAt: ISODate("2025-06-15T09:30:00Z")
}

// Follow relationship (separate collection, compound unique index)
{
  followerId: ObjectId("u2"),
  followeeId: ObjectId("u1"),
  createdAt: ISODate("2025-03-10")
}
// Index: { followerId: 1, followeeId: 1 } unique
// Index: { followeeId: 1 } for "who follows me" queries
```

**Feed strategies:**
- **Fan-out on read**: Query posts from followed users at read time. Simple but slow for users following thousands.
- **Fan-out on write**: Push post references to each follower's feed at write time. Fast reads but expensive writes for popular users.
- **Hybrid**: Fan-out on write for normal users; fan-out on read for celebrities (Outlier Pattern).

### 7.3 IoT / Sensor Networks

**Core collections:** devices, readings (time-series), alerts, configurations

```javascript
// Device registry
{
  _id: "sensor-A1234",
  type: "environmental",
  location: { building: "HQ", floor: 3, zone: "A" },
  firmware: "2.1.4",
  lastSeen: ISODate("2025-06-15T12:00:00Z"),
  status: "active",
  thresholds: { tempMax: 30, tempMin: 10, humidityMax: 80 }
}

// Time-series collection for readings (MongoDB 5.0+)
db.createCollection("readings", {
  timeseries: {
    timeField: "ts",
    metaField: "device",
    granularity: "seconds"
  },
  expireAfterSeconds: 2592000   // 30-day retention
})

// Alert document (triggered by threshold breach)
{
  _id: ObjectId("..."),
  deviceId: "sensor-A1234",
  type: "threshold_breach",
  metric: "temperature",
  value: 31.2,
  threshold: 30,
  severity: "warning",
  acknowledgedBy: null,
  createdAt: ISODate("2025-06-15T12:05:00Z")
}
```

**Key decisions:**
- Use native **time-series collections** for readings with appropriate granularity
- **TTL indexes** for automatic data expiration based on retention policy
- Bucket pattern for custom aggregation windows
- **Computed pattern** for real-time dashboard metrics (hourly/daily summaries)
- Device metadata rarely changes -- embed or use extended reference in alerts

Sources:
- [MongoDB Retail Reference Architecture](https://www.mongodb.com/resources/solutions/industries/retail-reference-architecture-part-1-building-flexible-searchable-low-latency-product)
- [Data Modeling: E-Commerce System with MongoDB (InfoQ)](https://www.infoq.com/articles/data-model-mongodb/)
- [How to Model a Social Network in MongoDB](https://oneuptime.com/blog/post/2026-03-31-mongodb-model-social-network/view)
- [MongoDB Docs: Model IoT Data](https://www.mongodb.com/docs/manual/tutorial/model-iot-data/)
- [3 Practical MongoDB Schema Examples](https://www.dragonflydb.io/databases/schema/mongodb)

---

## 8. Schema Design Checklist

Use this checklist when reviewing or designing a MongoDB schema:

1. **Access patterns documented?** List the top 10 queries and their frequency.
2. **Embedding vs. referencing justified?** Each relationship should have a documented reason for the chosen approach.
3. **Arrays bounded?** No array should grow without an application-enforced limit. Use the Outlier or Bucket Pattern for exceptions.
4. **Document size estimated?** Calculate worst-case document size and ensure it stays well under 16 MB.
5. **Working set fits in RAM?** The most-queried data should fit in the WiredTiger cache (50% of (RAM minus 1 GB) by default).
6. **Indexes aligned to queries?** Every frequent query should be covered by an index. Use `explain()` to verify.
7. **Schema validation applied?** $jsonSchema rules enforce data integrity at the database level.
8. **Schema versioning planned?** If the schema will evolve, include a `schemaVersion` field from day one.
9. **Denormalization staleness acceptable?** For every denormalized field, document the acceptable staleness window and update strategy.
10. **Anti-patterns checked?** Verify no unbounded arrays, bloated documents, excessive collections, excessive $lookup, or unused indexes.

---

## 9. Troubleshooting Common Schema Issues

### Document Too Large (16 MB exceeded)
- **Symptom:** `BSONObjectTooLarge` error on insert/update
- **Cause:** Unbounded array growth or storing large binaries inline
- **Fix:** Move arrays to child collection; use GridFS for large files; apply Subset or Bucket patterns

### Slow Queries on Embedded Arrays
- **Symptom:** Full collection scans when querying by array element fields
- **Cause:** Missing multikey index on embedded array fields
- **Fix:** Create a multikey index on the queried field within the array

### Write Contention on Hot Documents
- **Symptom:** High lock wait times, slow writes to popular documents
- **Cause:** Many concurrent updates to the same document (e.g., incrementing a counter)
- **Fix:** Apply Approximation Pattern; shard the collection; use separate counter documents

### Working Set Exceeds RAM
- **Symptom:** High cache eviction rate, increased disk I/O, slow reads
- **Cause:** Documents too large or too many fields loaded for common queries
- **Fix:** Apply Subset Pattern; archive old data; add appropriate indexes to reduce scan size

### $lookup Performance Degradation
- **Symptom:** Aggregation pipelines with $lookup are slow
- **Cause:** Over-normalized schema requiring joins for basic reads
- **Fix:** Denormalize with Extended Reference Pattern; embed frequently accessed data

---

## Cross-References

- **mongodb-expert** -- General MongoDB architecture, replication, storage engine internals
- **mongodb-developer** -- Driver usage, CRUD operations, aggregation framework
- **mongodb-query-performance** -- Query optimization, explain plans, ESR rule, index strategies
- **mongodb-data-lifecycle** -- Change Streams, TTL indexes, time-series collections, CDC patterns
- **mongodb-sharding** -- Shard key selection, chunk management, zone sharding
- **mongodb-atlas-expert** -- Atlas-specific features, Performance Advisor for anti-pattern detection
- **mongodb-encryption** -- CSFLE and Queryable Encryption impact on schema design
- **mongodb-search-ai** -- Atlas Search and Vector Search index design considerations
- **mongodb-performance-troubleshooting** -- Profiler, FTDC, diagnostic workflows for schema-related issues
- **mongodb-time-series** -- Native time series collection type (MongoDB 5.0+); supersedes the manual bucket pattern for new IoT/metrics workloads

---

## Time Series Collections vs. Manual Bucket Pattern

When designing schemas for time-stamped data, choose between the **manual bucket pattern** (regular collection) and the **native time series collection type** (MongoDB 5.0+):

| Criteria | Manual Bucket Pattern | Native Time Series Collection |
|----------|----------------------|-------------------------------|
| MongoDB version | Any | 5.0+ |
| Storage optimization | Manual (you control bucket size) | Automatic columnar compression (70-90% reduction) |
| Schema validation | Full $jsonSchema support | Not supported |
| Transactions | Supported | Writes not allowed in transactions |
| Change streams / Triggers | Supported | Not supported |
| Update flexibility | Any field updatable | Only `metaField` updatable |
| Unique indexes | Supported | Not supported |
| Atlas Search | Supported | Not supported |
| Setup complexity | Higher (application manages bucketing) | Lower (MongoDB handles bucketing automatically) |
| Query API | Standard CRUD | Standard CRUD (bucket layer is transparent) |

**Rule of thumb:** Use native time series collections for new IoT/metrics/observability workloads on MongoDB 5.0+ unless you need schema validation, transactions, change streams, or Atlas Search on the time series data. Use the manual bucket pattern when those features are required.

For full native time series collection reference, see `mongodb-time-series`.

---

## See also

- **`mongodb-aggregation-stages-deep`** — when you choose `$lookup` over denormalization, this skill covers the equality vs pipeline form, index requirements for the foreign side, the `as`-array 16 MB risk, type-mismatch silent-failure pattern, and the `$lookup` vs denormalization vs materialize-via-`$merge` decision tree. Also covers `$graphLookup` for hierarchies that you cannot reasonably embed.
