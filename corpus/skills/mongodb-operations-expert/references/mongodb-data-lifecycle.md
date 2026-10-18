<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-data-lifecycle` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-data-lifecycle
description: "MongoDB data lifecycle — Change Streams (resume tokens, pre/post images, split events, CDC), TTL Indexes (expireAfterSeconds, partial TTL, monitor thread), Time Series Collections (buckets, metaField, granularity, $densify/$fill, downsampling). TRIGGER when the request involves: change stream setup or debugging, resume token persistence, fullDocumentBeforeChange pre/post images, $changeStreamSplitLargeEvent, CDC pipelines from MongoDB, TTL index creation or troubleshooting (expireAfterSeconds, partial TTL, TTL monitor thread rate limiting), time series collection design (timeField, metaField, granularity, custom bucketing), or gap-filling and downsampling with $densify/$fill/$setWindowFields. SKIP for Atlas Stream Processing pipelines (use mongodb-atlas-stream-processing), Kafka Connector CDC configuration (use mongodb-kafka-connector), Spark Connector change stream reads (use mongodb-spark-connector), or purely read-side time series query optimization (use mongodb-query-performance)."
version: 1.3.0
origin: local
updated: 2026-05-29
category: mongodb
autoTrigger: true
when_to_use:
  - Setting up or debugging a MongoDB change stream consumer
  - Persisting resume tokens for crash-safe change stream recovery
  - Configuring pre-image and post-image capture (fullDocumentBeforeChange)
  - Handling $changeStreamSplitLargeEvent for near-16MB documents
  - Designing a CDC pipeline from MongoDB to Kafka, data warehouse, or search index
  - Creating or troubleshooting TTL indexes (expireAfterSeconds, partial TTL)
  - Diagnosing TTL monitor thread lag or deletion storms
  - Designing a time series collection with appropriate timeField/metaField/granularity
  - Custom bucket sizing with bucketMaxSpanSeconds / bucketRoundingSeconds (6.3+)
  - Gap-filling and downsampling with $densify, $fill, $setWindowFields
  - Migrating a regular collection to a time series collection
  - Understanding the change stream event types and nsType field
when_not_to_use:
  - Atlas Stream Processing pipelines ($source/$emit processors) — use mongodb-atlas-stream-processing
  - Kafka Connector CDC configuration — use mongodb-kafka-connector
  - Spark Connector change stream reads — use mongodb-spark-connector
  - Purely read-side time series query optimization — use mongodb-query-performance
  - MongoDB Ops Manager backup oplog — use mongodb-backup-restore
triggers:
  - MongoDB change streams
  - change stream resume token
  - pre-image post-image
  - fullDocumentBeforeChange
  - CDC MongoDB
  - event sourcing MongoDB
  - real-time sync MongoDB
  - TTL index
  - expireAfterSeconds
  - time to live MongoDB
  - TTL monitor thread
  - partial TTL index
  - time series collection
  - MongoDB time series
  - bucket pattern MongoDB
  - metaField timeField
  - granularity time series
  - $densify $fill
  - downsampling MongoDB
  - split large event
  - oplog tailing
  - change stream pipeline
  - ChangeStreamHistoryLost
  - changeStreamPreAndPostImages
  - $changeStreamSplitLargeEvent
  - nsType change stream
  - bucketMaxSpanSeconds
  - bucketRoundingSeconds
keywords:
  - mongodb
  - change-streams
  - cdc
  - event-sourcing
  - ttl-index
  - time-series
  - oplog
  - resume-token
  - pre-image
  - post-image
  - bucket-pattern
  - granularity
  - densify
  - fill
  - downsampling
  - real-time
  - data-lifecycle
  - expiration
  - split-events
  - ChangeStreamHistoryLost
  - TTLMonitor
  - invalidate event
  - startAfter
  - startAtOperationTime
related_skills:
  - mongodb-atlas-stream-processing
  - mongodb-kafka-connector
  - mongodb-spark-connector
  - mongodb-time-series
  - mongodb-aggregation-pipeline
  - mongodb-cdc-architecture
  - mongodb-performance-troubleshooting
  - mongodb-backup-restore
  - mongodb-expert
  - mongodb-atlas-expert
  - mongodb-encryption
---

# MongoDB Data Lifecycle: Change Streams, TTL Indexes, and Time Series Collections

This skill covers three foundational MongoDB capabilities that govern how data enters, lives in, and exits a MongoDB deployment. Together they form the backbone of event-driven architectures, automatic data expiration, and high-volume time-stamped data ingestion.

## Quick Decision Matrix

| I need to... | Use | Key section |
|---|---|---|
| React to document changes in real time | **Change Streams** | 1.1 |
| Pipe MongoDB changes to Kafka / data warehouse | **Change Streams (CDC)** | 1.9 |
| Get the before/after state of a changed document | **Change Streams (pre/post images)** | 1.4 |
| Automatically delete old documents after N days | **TTL Indexes** | 2.1 |
| Expire only a subset of documents (e.g., inactive sessions) | **Partial TTL Indexes** | 2.4 |
| Store high-volume time-stamped measurements efficiently | **Time Series Collections** | 3.1 |
| Fill gaps or downsample time series data | **$densify / $fill / $setWindowFields** | 3.7 |
| Combine real-time capture with retention and analytics | **Cross-Cutting Patterns** | 4.1-4.3 |

## 1. Change Streams

### 1.1 Architecture: Oplog Tailing Made Safe

Change streams provide a high-level, resumable API over the MongoDB oplog (operations log). They expose document-level change notifications without the fragility of direct oplog tailing.

**How it works:**
- The server opens a tailable cursor against the oplog on behalf of the client.
- Events are filtered, transformed, and delivered as structured change documents.
- On sharded clusters, `mongos` coordinates events from every shard using a global logical clock to guarantee total ordering across shards.
- Change streams require a **replica set** or **sharded cluster** (standalone `mongod` is not supported).

**Scope levels (3.6+):**
| Scope | Opens on | Use case |
|---|---|---|
| Collection | `db.collection.watch()` | Focused per-entity tracking |
| Database | `db.watch()` | Cross-collection workflows |
| Deployment | `client.watch()` | Full cluster CDC |

> **Performance note (sharded clusters):** Shards with little or no write activity ("cold shards") can slow change stream response time because `mongos` must still query them to maintain total ordering. [Source: MongoDB Production Recommendations](https://www.mongodb.com/docs/manual/administration/change-streams-production-recommendations/)

### 1.2 Resume Tokens

Every change event contains an `_id` field that serves as the **resume token**. This token enables crash-safe resumability.

**Resumption methods:**
| Method | Purpose | When to use |
|---|---|---|
| `resumeAfter` | Resume from the event **after** the given token | Normal crash recovery |
| `startAfter` | Resume from the event **after** the given token, including after `invalidate` events | Recovering after drop/rename |
| `startAtOperationTime` | Resume from a cluster time | When no token is available (e.g., cold start with known timestamp) |

**Critical considerations:**
- Resume tokens are only valid while the corresponding oplog entry exists. If the oplog rolls past the token, resumption fails with a `ChangeStreamHistoryLost` error.
- **Persist resume tokens externally** (database, file, Redis) after each successfully processed event to enable recovery.
- On sharded clusters, resume tokens encode shard-specific positions; the driver handles this transparently.

**Token expiration and the oplog window:**
- The oplog is a capped collection. Its retention window depends on available disk space and write volume.
- Atlas clusters expose a configurable **oplog minimum retention** (default: 1 hour for shared, configurable for dedicated).
- Rule of thumb: process events faster than the oplog rotates, or risk losing your resume position.

### 1.3 Pipeline Filtering

Change streams accept an aggregation pipeline as the first argument, allowing server-side filtering before events reach the application.

```javascript
// Only watch for inserts and updates on orders with total > 100
const pipeline = [
  { $match: {
    $or: [
      { operationType: "insert" },
      { operationType: "update" }
    ],
    "fullDocument.total": { $gt: 100 }
  }}
];
const changeStream = db.collection("orders").watch(pipeline);
```

**Allowed pipeline stages:** `$match`, `$project`, `$addFields`, `$replaceRoot`, `$replaceWith`, `$redact`, `$set`, `$unset`, and (7.0+) `$changeStreamSplitLargeEvent`.

> **Optimization:** Applying selective `$match` filters can reduce data transfer overhead by up to 50%, as the server only transmits matching events. [Source: Scaling Applications with MongoDB Change Streams](https://moldstud.com/articles/p-scaling-applications-with-mongodb-change-streams-top-strategies-tips)

### 1.4 fullDocument Options

The `fullDocument` option controls what document snapshot is included in update events.

| Option | Behavior | Version |
|---|---|---|
| `"default"` | Update events contain only the delta (updateDescription) | 3.6+ |
| `"updateLookup"` | Server performs a find after the update to include the current document | 3.6+ |
| `"whenAvailable"` | Returns post-image if available, null otherwise | 6.0+ |
| `"required"` | Returns post-image, fails the change event if unavailable | 6.0+ |

**Pre-images with `fullDocumentBeforeChange`:**

| Option | Behavior | Version |
|---|---|---|
| `"off"` (default) | No pre-image | 6.0+ |
| `"whenAvailable"` | Returns pre-image if stored, null otherwise | 6.0+ |
| `"required"` | Returns pre-image, fails the event if unavailable | 6.0+ |

**Enabling pre/post images:**
```javascript
// Enable at collection level
db.createCollection("orders", {
  changeStreamPreAndPostImages: { enabled: true }
});

// Or modify existing collection
db.runCommand({
  collMod: "orders",
  changeStreamPreAndPostImages: { enabled: true }
});
```

**Pre/post image storage:**
- Images are stored in the `config.system.preimages` collection.
- They are subject to a retention policy controlled by the `changeStreamOptions.preAndPostImages.expireAfterSeconds` cluster parameter.
- **Warning:** Enabling images on high-write collections increases storage significantly. Monitor the `config.system.preimages` collection size.

> **Best practice:** Prefer `whenAvailable` over `updateLookup` for update events. `updateLookup` performs a separate read that can return a document modified by a later operation, creating a race condition. Pre/post images are point-in-time consistent. [Source: MongoDB Blog -- Change Streams in 6.0](https://www.mongodb.com/company/blog/product-release-announcements/change-streams-mongodb-6-0-support-pre-post-image-retrieval-ddl-operations)

### 1.5 Change Stream Events

**Core operation types:**
| Event | Trigger | Key fields |
|---|---|---|
| `insert` | New document | `fullDocument` |
| `update` | Document modified | `updateDescription`, `fullDocument` (if configured) |
| `replace` | Document replaced | `fullDocument` |
| `delete` | Document removed | `documentKey` |
| `drop` | Collection dropped | -- |
| `rename` | Collection renamed | `to` namespace |
| `dropDatabase` | Database dropped | -- |
| `invalidate` | Stream can no longer continue | Terminal event |
| `createIndexes` | Index created (6.0+) | -- |
| `dropIndexes` | Index dropped (6.0+) | -- |
| `create` | Collection created (6.0+) | -- |
| `modify` | Collection modified (6.0+) | -- |
| `shardCollection` | Collection sharded (6.0+) | -- |
| `reshardCollection` | Collection resharded (6.0+) | -- |
| `refineCollectionShardKey` | Shard key refined (6.0+) | -- |

**nsType field (2025+):** The `nsType` field was added to the ChangeStreamDocument specification (January 2025) to indicate the namespace type involved in the event. [Source: MongoDB Specifications](https://github.com/mongodb/specifications/blob/master/source/change-streams/change-streams.md)

### 1.6 Split Events ($changeStreamSplitLargeEvent)

Starting in MongoDB 7.0 (backported to 6.0.9), the `$changeStreamSplitLargeEvent` aggregation stage handles change events that exceed the 16 MB BSON document limit.

**How it works:**
- Must be the **last stage** in the change stream pipeline.
- Only one `$changeStreamSplitLargeEvent` stage is allowed per pipeline.
- Splits oversized events into sequential fragments delivered through the cursor.
- The first fragment contains the maximum number of fields; subsequent fragments carry the remainder.
- Each fragment includes a `splitEvent` field with `{ fragment: N, of: M }` metadata.

```javascript
const pipeline = [
  { $match: { operationType: "update" } },
  { $changeStreamSplitLargeEvent: {} }
];
const cs = db.collection("largedocs").watch(pipeline);
```

**When needed:** Collections with documents near the 16 MB limit where updates produce large `fullDocument` or pre/post image payloads. [Source: MongoDB $changeStreamSplitLargeEvent docs](https://www.mongodb.com/docs/manual/reference/operator/aggregation/changestreamsplitlargeevent/)

### 1.7 Error Handling and Resumability

**Automatic retry:** Most MongoDB drivers automatically attempt to resume a change stream once on transient errors (`ChangeStreamHistoryLost` is NOT transient).

**Error categories:**
| Error | Cause | Recovery |
|---|---|---|
| `ChangeStreamHistoryLost` | Resume token fell off the oplog | Must re-initialize; optionally use `startAtOperationTime` with a known timestamp |
| Network timeout | Transient connectivity | Driver auto-resumes using last resume token |
| `invalidate` event | Drop/rename/dropDatabase | Use `startAfter` with the invalidate event's token to open a new stream |
| Cursor not found | Server-side cursor timeout | Resume with last persisted token |

**Robust consumer pattern:**
```javascript
async function watchWithRecovery(collection, pipeline, resumeToken) {
  while (true) {
    try {
      const options = resumeToken ? { resumeAfter: resumeToken } : {};
      const cs = collection.watch(pipeline, options);
      for await (const event of cs) {
        await processEvent(event);
        resumeToken = event._id;
        await persistToken(resumeToken); // External store
      }
    } catch (err) {
      if (err.code === 286) { // ChangeStreamHistoryLost
        console.error("Oplog rolled past resume token; full re-sync needed");
        resumeToken = null; // Or handle with startAtOperationTime
      }
      await sleep(1000); // Back off before retry
    }
  }
}
```

### 1.8 Scaling Patterns

**Connection pool sizing:** Each open change stream consumes one connection and a persistent `getMore` operation. The connection pool size must exceed the number of active change streams to avoid notification latency. [Source: MongoDB Production Recommendations](https://www.mongodb.com/docs/manual/administration/change-streams-production-recommendations/)

**Sharded cluster tips:**
- Avoid cold shards: ensure every shard has some write activity, or accept increased latency.
- Use pipeline `$match` to limit which shards contribute events where possible.
- Monitor change stream lag through the `operationTime` field vs. wall clock.

**Horizontal fan-out:**
- For high-throughput use cases, partition processing by collection or namespace prefix.
- Multiple change streams on the same collection are independent; each gets its own cursor.

### 1.9 Use Cases: CDC, Event Sourcing, Real-Time Sync

**Change Data Capture (CDC):**
The canonical architecture is: MongoDB (Change Streams) --> CDC Connector --> Message Broker / Direct Delivery --> Destination.

Implementation options:
- **Self-managed:** Kafka Connect + Debezium MongoDB connector. Requires Kafka infrastructure, connector monitoring, and offset management.
- **Managed platforms:** Streamkap, Airbyte, Estuary, Hevo -- wrap change streams in a hosted service eliminating Kafka operational burden.
- **Direct consumer:** Application-level change stream processing for simpler pipelines (e.g., update a search index, push to a cache).

**Event sourcing via CDC:**
CDC bridges database-backed services and event-sourced consumers without modifying the application. Database changes become events that downstream services consume, providing event-sourced semantics without rewriting the write path. [Source: Streamkap -- Event Sourcing with CDC](https://streamkap.com/resources-and-guides/event-sourcing-cdc)

**Production CDC checklist:**
- **Deduplication:** Change streams and Kafka can produce duplicate events on retries, connector restarts, or consumer rebalancing. Downstream consumers must be idempotent.
- **Event ordering:** Events are keyed by primary key (document `_id`), so all changes to a single entity land on the same Kafka partition in order.
- **Backpressure:** MongoDB may emit changes faster than consumers can process. Use bounded queues, reactive streams, or backpressure-aware consumers.
- **Schema evolution:** fullDocument shapes can change over time. Use schema registries or versioned event wrappers for downstream consumers.

[Sources: Streamkap CDC Guide](https://streamkap.com/resources-and-guides/mongodb-change-data-capture), [Tinybird Practical CDC Guide](https://www.tinybird.co/blog/mongodb-cdc), [Reintech CDC Guide](https://reintech.io/blog/mongodb-change-data-capture-cdc-real-time-data-synchronization)

## 2. TTL Indexes

### 2.1 TTL Index Fundamentals

TTL (Time-To-Live) indexes instruct MongoDB to automatically remove documents after a specified duration, measured from a date-typed field.

```javascript
// Documents expire 30 days after the createdAt field
db.sessions.createIndex(
  { "createdAt": 1 },
  { expireAfterSeconds: 2592000 } // 30 * 24 * 60 * 60
);
```

**Requirements:**
- The indexed field **must** contain a value of BSON `Date` type (or an array of dates; the lowest date value is used).
- If the field is missing or not a date, the document is **never** expired.
- TTL indexes are **single-field indexes only**. Compound indexes ignore the `expireAfterSeconds` option.

**Special case -- `expireAfterSeconds: 0`:**
Documents expire at the exact date specified in the field itself, enabling per-document TTL:
```javascript
db.events.createIndex({ "expireAt": 1 }, { expireAfterSeconds: 0 });
// Each document controls its own lifetime:
db.events.insertOne({
  data: "temporary",
  expireAt: new Date("2026-07-01T00:00:00Z")
});
```

### 2.2 TTL Monitor Thread Behavior

The TTL background task (**TTLMonitor**) runs as a single thread on the primary member.

**Execution cycle:**
- The TTLMonitor wakes every **60 seconds** (configurable via `ttlMonitorSleepSecs` starting in certain versions).
- For **each TTL index**, it deletes expired documents until one of these limits is hit:
  - 50,000 documents deleted from the current index, OR
  - 1 second elapsed deleting from the current index, OR
  - All expired documents from the current index are deleted.
- It then moves to the next TTL index and repeats.

**Implications:**
- Deletion is **not instantaneous**. Documents may persist for up to 60 seconds (or longer under load) past their expiration time.
- Under heavy write loads or large backlogs of expired documents, the TTLMonitor may not keep up in a single pass.
- **Resource impact:** Each TTLMonitor cycle consumes disk I/O and CPU. During peak hours, large batch deletions can affect foreground workload performance.

> **Operational tip:** If you reduce `expireAfterSeconds` on an existing index, many documents may become eligible for immediate deletion. This can cause a deletion storm. **Manually batch-delete in small increments first**, then update the index. [Source: MongoDB TTL Index Docs](https://www.mongodb.com/docs/manual/core/index-ttl/)

### 2.3 Replica Set Behavior and Clock Skew

- The TTLMonitor **only runs on the primary**. Secondary members replicate the resulting delete operations through the oplog.
- Because TTL deletion depends on comparing the indexed date field against the server's system clock, **clock skew between replica set members does not affect deletion correctness** -- only the primary's clock matters for the deletion decision.
- However, if a primary election occurs and the new primary's clock is significantly different, the effective TTL can shift. **Use NTP synchronization** across all replica set members.

### 2.4 Partial TTL Indexes

Starting in MongoDB 3.2 (general availability), partial indexes combined with TTL provide targeted expiration:

```javascript
// Only expire documents where status is "inactive", after 24 hours
db.sessions.createIndex(
  { "lastActive": 1 },
  {
    expireAfterSeconds: 86400,
    partialFilterExpression: { status: "inactive" }
  }
);
```

**Use cases:**
- Expire only failed/abandoned records while keeping successful ones indefinitely.
- Apply different retention policies to different document subsets (use multiple partial TTL indexes on different fields/conditions).
- Reduce TTLMonitor workload by narrowing the scan scope.

**Caveat:** A document must match the partial filter expression **at query time** for the TTL to apply. If a document transitions from matching to not matching (e.g., status changes from "inactive" to "active"), it will no longer be subject to TTL deletion.

### 2.5 Compound TTL Indexes

**TTL indexes do NOT support compound keys.** As of MongoDB 8.0, this limitation remains. Creating a compound index with `expireAfterSeconds` silently ignores the TTL behavior.

**Workaround patterns:**
- Use a separate single-field TTL index for expiration, plus compound indexes for query performance.
- Use partial TTL indexes to approximate compound filtering behavior.
- Implement application-level expiration for complex multi-field TTL logic.

### 2.6 Modifying TTL Values

Use `collMod` to change the expiration time on an existing TTL index:

```javascript
db.runCommand({
  collMod: "sessions",
  index: {
    keyPattern: { "createdAt": 1 },
    expireAfterSeconds: 604800 // Change to 7 days
  }
});
```

**Warning:** Decreasing the value makes a potentially large set of documents immediately eligible for deletion. The TTLMonitor will process them subject to its per-cycle limits (50K documents or 1 second per index), which may take multiple cycles.

### 2.7 When NOT to Use TTL Indexes

| Scenario | Why not TTL | Alternative |
|---|---|---|
| Archival before deletion | TTL deletes permanently; no archive step | Scheduled job that copies then deletes |
| Complex expiration logic (multi-field) | TTL is single-field only | Application-level cron/scheduled task |
| Large-scale bulk expiration | TTL monitor is single-threaded, rate-limited | Manual batched deletes with `deleteMany` |
| Audit/compliance retention | TTL deletions are hard to audit precisely | Application-managed retention with logging |
| Mixed retention per document type | Multiple partial TTLs become unwieldy | Application logic with explicit delete |

[Sources: MongoDB TTL Docs](https://www.mongodb.com/docs/manual/core/index-ttl/), [Mydbops TTL Guide](https://www.mydbops.com/blog/mongodb-ttl-indexes), [OneUptime TTL Strategies](https://oneuptime.com/blog/post/2026-01-30-mongodb-ttl-index/view), [VDBA Stalled TTL Monitor Case Study](https://virtual-dba.com/blog/case-study-diagnosing-a-stalled-mongodb-ttl-monitor/)

## 3. Time Series Collections

### 3.1 Fundamentals

Time series collections (MongoDB 5.0+) are purpose-built for efficiently storing and querying sequences of measurements over time.

```javascript
db.createCollection("sensor_readings", {
  timeseries: {
    timeField: "timestamp",       // Required: the Date field
    metaField: "sensorId",        // Optional: identifies the data source
    granularity: "minutes"        // Optional: hint for bucket sizing
  },
  expireAfterSeconds: 7776000    // Optional: TTL for automatic expiration (90 days)
});
```

**Core fields:**
| Field | Role | Constraints |
|---|---|---|
| `timeField` | The Date field for each measurement | Required, must be BSON Date |
| `metaField` | Identifies the source of measurements (sensor ID, device, host) | Optional, should rarely change per source |
| `granularity` | Hint for bucket time span | `"seconds"`, `"minutes"` (default), `"hours"` |

### 3.2 Bucket Pattern and Internal Storage

MongoDB does **not** store each time series document as an individual BSON document on disk. Instead, it transparently groups measurements into **buckets**.

**How bucketing works:**
- Documents with the same `metaField` value and close `timeField` values are grouped into one internal bucket document.
- Each bucket has a time span governed by `granularity` (or custom bucketing parameters).
- Bucket rotation occurs when: the time span is exceeded, the document count limit is hit (currently ~1000 measurements per bucket), or the bucket size limit is reached.

**Bucket catalog:**
The in-memory bucket catalog tracks open buckets. When a new measurement arrives, the server checks the catalog for an open bucket matching the `metaField` and time range. If found, the measurement is appended; otherwise, a new bucket is created.

> **Key insight (2026):** Under high ingestion rates, buckets rotate quickly as size thresholds are reached, making granularity largely irrelevant. Under low ingestion rates, bucket rotation becomes time-driven, and granularity plays a critical role in determining bucket lifespan, query fan-out, and memory efficiency. [Source: MongoDB Blog -- High vs Low Ingestion Bucket Behavior](https://www.mongodb.com/company/blog/technical/a-practical-study-of-mongodb-time-series-bucket-behavior)

### 3.3 Granularity and Custom Bucketing

**Standard granularity options:**
| Granularity | Max bucket span | Best for |
|---|---|---|
| `"seconds"` | 1 hour | Sub-second / per-second telemetry |
| `"minutes"` | 24 hours | Per-minute aggregations |
| `"hours"` | 30 days | Hourly or daily summaries |

**Custom bucketing (MongoDB 6.3+):**
For finer control, use `bucketMaxSpanSeconds` and `bucketRoundingSeconds` instead of `granularity`:

```javascript
db.createCollection("metrics", {
  timeseries: {
    timeField: "ts",
    metaField: "source",
    bucketMaxSpanSeconds: 3600,    // 1-hour buckets
    bucketRoundingSeconds: 3600    // Align to hour boundaries
  }
});
```

`bucketRoundingSeconds` must be equal to `bucketMaxSpanSeconds`. These parameters and `granularity` are mutually exclusive.

**Choosing the right granularity:**
- Match the granularity to the typical interval between consecutive measurements from the same source.
- Too coarse = buckets stay open too long, increasing memory pressure and potentially mixing unrelated time ranges.
- Too fine = many small buckets, increased metadata overhead, wider query fan-out.

### 3.4 MetaField Optimization

The `metaField` has significant impact on storage efficiency and query performance.

**Best practices:**
- Keep metaField **cardinality manageable**. Fine-grained or frequently changing metaField values generate many sparsely packed, short-lived buckets, decreasing storage and query efficiency.
- When querying on `metaField`, query on **scalar sub-fields** rather than the entire metaField object for index utilization.
- The metaField value for a given source should remain stable. Changing it creates new bucket series.

```javascript
// Good: stable, low-cardinality metaField
{ sensorId: "temp-sensor-042" }

// Bad: high-cardinality, causes bucket explosion
{ requestId: "unique-uuid-per-request" }
```

### 3.5 Compression and Storage Engine Optimization

Time series collections achieve significant compression through columnar storage of bucket internals.

**Compression ratios:**
- Numeric sensor data typically compresses at **5-20x** compared to regular collections when buckets are well-packed.
- Delta and delta-of-delta encoding is applied within buckets for timestamps and numeric values.

**Maximizing compression:**
1. Choose a granularity that matches your write frequency (full buckets compress better).
2. Keep metaField cardinality manageable (fewer, fuller buckets).
3. Insert data in **chronological order** whenever possible (out-of-order inserts still work but may reduce bucket packing efficiency).
4. Use **Zstd** as the block compressor (default for WiredTiger in recent versions) for best ratio.
5. Avoid sparse measurements with many null fields; they waste bucket slots.

> [Source: OneUptime -- Optimize Compression for Time Series](https://oneuptime.com/blog/post/2026-03-31-mongodb-time-series-compression/view)

### 3.6 Secondary Indexes

Time series collections support secondary indexes with version-specific capabilities:

| Version | Capability |
|---|---|
| 5.0 | Indexes on `timeField` and `metaField` (or sub-fields) |
| 6.0 | Secondary indexes on **any field** in the collection |
| 6.3+ | Automatic compound index on `{ metaField: 1, timeField: 1 }` for new collections |

```javascript
// Index on a measurement field (6.0+)
db.sensor_readings.createIndex({ "temperature": 1 });

// Compound index on meta sub-field and time
db.sensor_readings.createIndex({ "metadata.region": 1, "timestamp": 1 });
```

**Index considerations:**
- Indexes are built on the underlying bucket documents, not individual measurements.
- Adding secondary indexes improves query performance but increases storage and write overhead.
- If downgrading FCV (Feature Compatibility Version), drop incompatible secondary indexes first.

### 3.7 Downsampling with $densify, $fill, and Window Functions

Time series data often needs gap filling and downsampling for visualization and analysis.

**$densify -- Fill time gaps with placeholder documents:**
```javascript
db.sensor_readings.aggregate([
  { $densify: {
    field: "timestamp",
    partitionByFields: ["sensorId"],
    range: {
      step: 1,
      unit: "minute",
      bounds: "full"
    }
  }}
]);
```

**$fill -- Populate missing values:**
```javascript
db.sensor_readings.aggregate([
  { $densify: { /* as above */ } },
  { $fill: {
    sortBy: { timestamp: 1 },
    partitionBy: { sensorId: "$sensorId" },
    output: {
      temperature: { method: "linear" },  // Linear interpolation
      status: { method: "locf" }           // Last observation carried forward
    }
  }}
]);
```

**$fill methods:**
| Method | Behavior |
|---|---|
| `"linear"` | Linear interpolation between known values (numeric only) |
| `"locf"` | Last Observation Carried Forward |
| `{ value: <expr> }` | Static fill value |

**Downsampling with $dateTrunc and $group:**
```javascript
// Downsample per-second data to 5-minute averages
db.sensor_readings.aggregate([
  { $group: {
    _id: {
      sensor: "$sensorId",
      bucket: { $dateTrunc: { date: "$timestamp", unit: "minute", binSize: 5 } }
    },
    avgTemp: { $avg: "$temperature" },
    maxTemp: { $max: "$temperature" },
    minTemp: { $min: "$temperature" },
    count: { $sum: 1 }
  }},
  { $merge: { into: "sensor_readings_5min" } }  // Persist downsampled data
]);
```

**Window functions for time series analysis:**
```javascript
db.sensor_readings.aggregate([
  { $setWindowFields: {
    partitionBy: "$sensorId",
    sortBy: { timestamp: 1 },
    output: {
      movingAvg: {
        $avg: "$temperature",
        window: { documents: [-5, 0] }  // 6-point moving average
      },
      diff: {
        $derivative: {
          input: "$temperature",
          unit: "minute"
        },
        window: { documents: [-1, 0] }
      }
    }
  }}
]);
```

[Sources: MongoDB $densify docs](https://www.mongodb.com/developer/products/mongodb/preparing-tsdata-with-densify-and-fill/), [MongoDB Gap Filling Blog](https://www.mongodb.com/blog/post/introducing-gap-filling-time-series-data-mongodb-5-3)

### 3.8 Migration from Regular Collections

**Steps to migrate existing time-stamped data:**

1. **Create the time series collection** with appropriate `timeField`, `metaField`, and `granularity`.
2. **Bulk insert** from the old collection using an aggregation pipeline with `$out` or `$merge`, or use `mongodump`/`mongorestore` (note: `mongorestore` does not preserve time series collection options; create the collection first).
3. **Insert in chronological order** where possible for optimal bucket packing.
4. **Recreate necessary indexes** on the new time series collection.
5. **Validate** row counts and sample queries before dropping the original collection.

```javascript
// Migration via aggregation
db.old_metrics.aggregate([
  { $addFields: {
    // Ensure date field is proper BSON Date
    timestamp: { $toDate: "$timestamp" }
  }},
  { $merge: {
    into: "ts_metrics",
    whenMatched: "keepExisting"
  }}
]);
```

**Limitations to be aware of:**
- Time series collections do not support multi-document transactions.
- `update` and `delete` operations have restrictions (no multi-document updates with arbitrary filters before 7.0; limited `delete` support).
- Schema validation on measurement fields is not supported; only `metaField` and `timeField` are enforced.

### 3.9 Sizing and Performance

**Write throughput:**
- Time series collections handle high-volume inserts efficiently due to bucket batching.
- Ordered bulk inserts perform best; unordered inserts with mixed timestamps may cause bucket contention.

**Query patterns:**
- Queries filtering on `timeField` and `metaField` benefit from the default compound index (6.3+).
- Range scans on time are bucket-aware: the server skips entire buckets outside the range.
- Aggregations that align with bucket boundaries (e.g., hourly rollups on hourly-granularity collections) are optimized.

**Memory:**
- The bucket catalog consumes memory proportional to the number of **open buckets** (one per unique metaField value within the current time window).
- High metaField cardinality = high memory usage. Monitor with `serverStatus.bucketCatalog`.

[Sources: MongoDB Time Series Best Practices](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-best-practices/), [MongoDB Time Series Considerations](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-considerations/), [OneUptime Time Series Granularity Guide](https://oneuptime.com/blog/post/2026-03-31-mongodb-time-series-granularity/view)

## 4. Cross-Cutting Patterns

### 4.1 Change Streams + Time Series

Use change streams on a regular collection as the ingestion trigger, then write processed/enriched data into a time series collection:

```javascript
const cs = db.collection("raw_events").watch();
for await (const event of cs) {
  if (event.operationType === "insert") {
    const enriched = enrich(event.fullDocument);
    await db.collection("ts_metrics").insertOne(enriched);
  }
}
```

### 4.2 TTL + Time Series

Time series collections natively support `expireAfterSeconds` at creation time, providing built-in TTL without a separate index:

```javascript
db.createCollection("logs", {
  timeseries: { timeField: "ts", metaField: "host", granularity: "minutes" },
  expireAfterSeconds: 2592000  // 30-day retention
});
```

The TTL is applied against the `timeField`. This is the recommended approach for time series data retention rather than creating a separate TTL index.

### 4.3 CDC Pipeline with TTL Cleanup

A common pattern combines all three features:
1. **Change stream** captures mutations from the source collection.
2. Processed events are written to a **time series collection** for analytics.
3. **TTL** on both the source (for transient data) and time series collection (for retention) ensures automatic cleanup.

### 4.4 Common Pitfalls and Troubleshooting

| Symptom | Root cause | Fix |
|---|---|---|
| Change stream stops receiving events | Resume token expired (oplog rolled over) | Increase oplog size; persist tokens more frequently; use `startAtOperationTime` for recovery |
| `updateLookup` returns null for fullDocument | Document was deleted between the update and the lookup | Switch to pre/post images (`whenAvailable`) for point-in-time consistency |
| TTL not deleting expired documents | Indexed field is not a BSON Date type | Verify field type with `typeof` check; re-insert with proper `new Date()` values |
| TTL deleting documents too slowly | TTLMonitor rate limit (50K/s per index per cycle) | Pre-delete large backlogs manually with batched `deleteMany`; then lower `expireAfterSeconds` |
| Time series insert performance degrading | High metaField cardinality causing bucket explosion | Reduce metaField cardinality; use stable identifiers; monitor `serverStatus.bucketCatalog` |
| Time series queries scanning too many buckets | Granularity mismatch with actual measurement interval | Adjust granularity or use custom bucketing (`bucketMaxSpanSeconds`) to match write frequency |
| Change stream latency on sharded cluster | Cold shards delaying global ordering | Ensure all shards have write activity; add pipeline `$match` to narrow shard participation |
| Pre/post images consuming excessive storage | High-write collection with images enabled | Set `changeStreamOptions.preAndPostImages.expireAfterSeconds`; disable on collections that do not need it |

## 5. Version Compatibility Matrix

| Feature | Minimum Version | Notable Upgrades |
|---|---|---|
| Change streams (collection) | 3.6 | -- |
| Change streams (database/deployment) | 4.0 | -- |
| Pre/post images | 6.0 | -- |
| DDL events in change streams | 6.0 | createIndexes, dropIndexes, etc. |
| $changeStreamSplitLargeEvent | 7.0 (backported 6.0.9) | -- |
| nsType field | 8.0+ (spec Jan 2025) | -- |
| TTL indexes | 2.2 | -- |
| Partial TTL indexes | 3.2 | -- |
| Time series collections | 5.0 | -- |
| Secondary indexes on any TS field | 6.0 | -- |
| Custom bucketing (bucketMaxSpanSeconds) | 6.3 | -- |
| Auto compound index on TS | 6.3 | -- |

---

## Sources

1. [MongoDB Change Streams Documentation](https://www.mongodb.com/docs/manual/changestreams/)
2. [MongoDB Change Streams Specification (GitHub)](https://github.com/mongodb/specifications/blob/master/source/change-streams/change-streams.md)
3. [Change Streams in MongoDB 6.0 -- Pre/Post Images, DDL Operations (MongoDB Blog)](https://www.mongodb.com/company/blog/product-release-announcements/change-streams-mongodb-6-0-support-pre-post-image-retrieval-ddl-operations)
4. [Change Streams Production Recommendations (MongoDB Docs)](https://www.mongodb.com/docs/manual/administration/change-streams-production-recommendations/)
5. [$changeStreamSplitLargeEvent (MongoDB Docs)](https://www.mongodb.com/docs/manual/reference/operator/aggregation/changestreamsplitlargeevent/)
6. [MongoDB Change Data Capture -- Complete Guide (Streamkap)](https://streamkap.com/resources-and-guides/mongodb-change-data-capture)
7. [Practical Guide to Real-Time CDC with MongoDB (Tinybird)](https://www.tinybird.co/blog/mongodb-cdc)
8. [Event Sourcing with CDC (Streamkap)](https://streamkap.com/resources-and-guides/event-sourcing-cdc)
9. [Scaling Applications with MongoDB Change Streams (MoldStud)](https://moldstud.com/articles/p-scaling-applications-with-mongodb-change-streams-top-strategies-tips)
10. [MongoDB TTL Indexes Documentation](https://www.mongodb.com/docs/manual/core/index-ttl/)
11. [The Ultimate Guide to MongoDB TTL Indexes (Mydbops)](https://www.mydbops.com/blog/mongodb-ttl-indexes)
12. [MongoDB TTL Index Strategies (OneUptime, 2026)](https://oneuptime.com/blog/post/2026-01-30-mongodb-ttl-index/view)
13. [Diagnosing a Stalled MongoDB TTL Monitor (VDBA)](https://virtual-dba.com/blog/case-study-diagnosing-a-stalled-mongodb-ttl-monitor/)
14. [Expire Data from Collections by Setting TTL (MongoDB Docs)](https://www.mongodb.com/docs/manual/tutorial/expire-data/)
15. [MongoDB Time Series Collections Documentation](https://www.mongodb.com/docs/manual/core/timeseries-collections/)
16. [Time Series Best Practices (MongoDB Docs)](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-best-practices/)
17. [High vs Low Ingestion: Bucket Behavior Study (MongoDB Blog, 2026)](https://www.mongodb.com/company/blog/technical/a-practical-study-of-mongodb-time-series-bucket-behavior)
18. [Time Series Granularity Configuration (MongoDB Docs)](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-granularity/)
19. [Optimize Compression for Time Series (OneUptime, 2026)](https://oneuptime.com/blog/post/2026-03-31-mongodb-time-series-compression/view)
20. [Secondary Indexes on Time Series Collections (MongoDB Docs)](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-secondary-index/)
21. [Gap Filling for Time Series Data (MongoDB Blog)](https://www.mongodb.com/blog/post/introducing-gap-filling-time-series-data-mongodb-5-3)
22. [Pre-Image and Post-Image in Change Streams (OneUptime, 2026)](https://oneuptime.com/blog/post/2026-03-31-mongodb-change-stream-pre-post-image/view)
23. [MongoDB CDC with Debezium and Kafka (OLake)](https://olake.io/blog/mongodb-cdc-using-debezium-and-kafka/)
