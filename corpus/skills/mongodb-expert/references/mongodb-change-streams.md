<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-change-streams` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-change-streams
title: MongoDB Change Streams
version: 1.1.0
updated: "2026-05-29"
category: mongodb
tags: [mongodb, change-streams, cdc, real-time, oplog, resume-token, watch, pre-image, post-image, drivers, kafka, sharding, atlas-triggers, atlas-stream-processing]
description: >
  Deep reference for MongoDB change streams: oplog architecture, change event
  structure (all operationTypes, updateDescription, pre/post images), resume
  token persistence strategies, aggregation pipeline filtering, sharded cluster
  behavior (cold shard problem, periodicNoopIntervalSecs), driver patterns
  (Node.js, Python, Go, Java, C#), Atlas Triggers vs manual streams, Atlas Stream
  Processing integration, Kafka CDC connector patterns, and production
  troubleshooting (ChangeStreamHistoryLost, oplog window sizing, large event splitting).

  TRIGGER: user asks about change streams, watch() API, CDC from MongoDB,
  resume tokens, ChangeStreamHistoryLost, oplog window sizing, pre-image or
  post-image (fullDocumentBeforeChange), fullDocument updateLookup, sharded
  cluster change stream latency, cold shard problem, $changeStreamSplitLargeEvent,
  Kafka connector change stream config, Atlas Triggers vs manual change stream
  consumption, or driver-specific watch() patterns.

  SKIP: Atlas Triggers configuration and App Services functions (use
  mongodb-atlas-triggers-functions); Atlas Stream Processing windowing and
  $source/$emit stages (use mongodb-atlas-stream-processing); Kafka connector
  setup beyond change stream config (use mongodb-kafka-connector); oplog
  internals not related to change streams (use mongodb-replication).

whenToUse:
  - "How do I watch for changes to a MongoDB collection in real time?"
  - "My change stream is getting ChangeStreamHistoryLost — how do I fix it?"
  - "How do I persist a resume token so I can restart my change stream?"
  - "How do I get the full document on update events (fullDocument)?"
  - "Pre-image and post-image setup for change streams (MongoDB 6.0+)"
  - "Change stream on a sharded cluster is slow — cold shard problem"
  - "How do I filter change stream events server-side with $match?"
  - "Node.js / Python / Go / Java / C# change stream driver pattern"
  - "Kafka connector CDC setup with MongoDB as a source"
  - "Atlas Triggers vs manual change stream — which should I use?"
  - "Large change events exceeding 16MB — $changeStreamSplitLargeEvent"
  - "How do I size the oplog for reliable change stream consumers?"

whenNotToUse:
  - User needs Atlas Database Trigger setup (managed, serverless JS) — use mongodb-atlas-triggers-functions
  - User needs Atlas Stream Processing ($source, windowing, $emit, Kafka sink) — use mongodb-atlas-stream-processing
  - User needs Kafka connector configuration beyond change stream options — use mongodb-kafka-connector
  - User needs oplog replication internals (replication lag, oplog sizing for replication) — use mongodb-replication
  - User needs Spark Structured Streaming from MongoDB — use mongodb-spark-connector

related_skills:
  - mongodb-atlas-triggers-functions
  - mongodb-atlas-stream-processing
  - mongodb-kafka-connector
  - mongodb-replication
  - mongodb-spark-connector
  - mongodb-cdc-architecture
  - mongodb-indexes-deep
---

# MongoDB Change Streams

## Overview

Change streams are MongoDB's mechanism for subscribing to real-time data change notifications without the complexity of directly tailing the oplog. Available on replica sets and sharded clusters since MongoDB 3.6, they provide an idiomatic, driver-integrated API that abstracts oplog internals, guarantees majority-committed events, and supports automatic resumability via resume tokens.

**Not to confuse with:**
- **Atlas Database Triggers** — serverless JS functions built on top of change streams (Atlas App Services layer)
- **Atlas Stream Processing** — a full stream-processing engine with `$source`, `$merge`/`$emit` stages, windowing, and Kafka integration; uses change streams as one of its sources
- **oplog tailing** — the low-level mechanism change streams wrap; direct tailing is unsupported and fragile

**Availability requirements:**
- Replica set or sharded cluster (WiredTiger storage engine, pv1 protocol)
- NOT supported on standalone deployments or time-series collections

---

## Architecture: How Change Streams Work

### Oplog Foundation

Every write on a MongoDB replica set is recorded in `local.oplog.rs`, an append-only capped collection. Change streams open a **TAILABLE_AWAIT cursor** against the oplog, translate raw oplog entries into structured change event documents, and deliver them to the application.

Key architectural properties:
- **Majority committed only** — events fire only after writes are durable on a majority of replica set members, protecting against notification for rolled-back writes
- **Single cursor abstraction** — even on sharded clusters, the application sees one logical cursor; `mongos` fans out to per-shard streams and merges results
- **Total ordering guarantee** — MongoDB uses a global logical clock to ensure events arrive in a consistent total order, even across multiple shards

### Feature Evolution by Version

| Version | Change |
|---------|--------|
| 3.6 | Introduced (collection-level, replica sets only) |
| 4.0 | Database-level and deployment-level streams; multi-document transaction support |
| 4.2 | Modifying `_id` in pipeline throws exception |
| 5.1 | Optimized resource utilization and pipeline execution |
| 5.3 | Orphaned document events excluded during chunk migrations |
| 6.0 | Pre/post images (`fullDocumentBeforeChange`), `showExpandedEvents`, `wallTime` field |
| 6.0.9 | `$changeStreamSplitLargeEvent` stage added |
| 6.1 | `disambiguatedPaths`, `refineCollectionShardKey`, `reshardCollection` events |

### Watch Scopes

```javascript
// Collection-level — most common, lowest overhead
const stream = collection.watch(pipeline, options);

// Database-level — all non-system collections in a database
const stream = db.watch(pipeline, options);

// Deployment-level — all non-system collections across all dbs
// (excludes admin, local, config)
const stream = client.watch(pipeline, options);
```

In **mongosh**:
```javascript
db.orders.watch()         // collection
db.watch()                // database
db.getMongo().watch()     // deployment
```

---

## Change Event Document Structure

Every notification is a BSON document with the following top-level fields:

```javascript
{
  _id: { /* resume token — BSON object, do not modify */ },
  operationType: "insert" | "update" | "replace" | "delete" |
                 "drop" | "rename" | "dropDatabase" | "invalidate" |
                 "create" | "createIndexes" | "dropIndexes" |
                 "modify" | "shardCollection" | "reshardCollection" |
                 "refineCollectionShardKey",
  clusterTime: Timestamp({ t: 1680529003, i: 1 }),
  wallTime: ISODate("2023-04-03T12:30:03.000Z"), // MongoDB 6.0+
  ns: { db: "mydb", coll: "orders" },
  documentKey: { _id: ObjectId("..."), /* shard key fields on sharded collections */ },

  // Varies by operationType — see below
  fullDocument: { /* ... */ },
  fullDocumentBeforeChange: { /* ... */ },
  updateDescription: { /* ... */ },

  // Multi-document transactions only
  lsid: { id: UUID("..."), uid: BinData(...) },
  txnNumber: NumberLong(1),

  // MongoDB 6.0+ with showExpandedEvents
  collectionUUID: UUID("...")
}
```

### Per-OperationType Field Matrix

| operationType | fullDocument | updateDescription | documentKey |
|---------------|-------------|-------------------|-------------|
| `insert` | Always present (the inserted doc) | — | Present |
| `update` | Optional (requires `updateLookup` or pre/post images) | Always present | Present |
| `replace` | Always present (the replacement doc) | — | Present |
| `delete` | Not present (document is gone) | — | Present |
| `drop` | — | — | — |
| `rename` | — | — | — |
| `invalidate` | — | — | — |

### updateDescription Structure (update events only)

```javascript
updateDescription: {
  updatedFields: {
    "email": "alice@example.com",     // new value of each modified field
    "address.city": "Seattle"
  },
  removedFields: ["phoneNumber", "fax"],
  truncatedArrays: [
    { field: "tags", newSize: 3 }     // only from pipeline-based updates
  ],
  // MongoDB 6.1+ with showExpandedEvents
  disambiguatedPaths: {
    "home.town": ["home.town"]         // clarifies dotted key vs nested path
  }
}
```

**Critical distinction:** `updatedFields` shows the *new values*, not the update operators. A `$inc` on `counter` shows the resulting integer, not `{ $inc: { counter: 1 } }`.

### Expanded Events (MongoDB 6.0+)

DDL events require `showExpandedEvents: true` in the `$changeStream` stage options:

```javascript
collection.watch([], { showExpandedEvents: true })
```

This enables: `create`, `createIndexes`, `dropIndexes`, `modify`, `shardCollection`, `reshardCollection`.

---

## Resume Tokens

### What They Are

Every change event's `_id` field is a BSON resume token. There are two types:
- **Event tokens** — generated for each change event, reference a specific oplog entry
- **Highwatermark tokens** — server-generated periodically to indicate time advancement without an associated event; available on the cursor as `postBatchResumeToken`

### Accessing Resume Tokens

```javascript
// Node.js — from a change event
changeStream.on('change', (event) => {
  const token = event._id;  // persist this
});

// Node.js — post-batch token (latest seen, even between events)
changeStream.on('resumeTokenChanged', (token) => {
  persistToken(token);
});

// Python (PyMongo) — access after any iteration
token = stream.resume_token

// From cursor metadata
const token = cursor.postBatchResumeToken;
```

### Resuming a Stream

```javascript
// resumeAfter — resume after a specific event (cannot use on invalidate token)
const stream = collection.watch([], { resumeAfter: savedToken });

// startAfter — resume after any event including invalidate (MongoDB 4.1.1+)
const stream = collection.watch([], { startAfter: savedToken });

// startAtOperationTime — resume from a cluster time point (no prior token needed)
const stream = collection.watch([], {
  startAtOperationTime: Timestamp({ t: 1680529003, i: 1 })
});
```

**Rule:** Use the same pipeline and options when resuming that you used originally. Different pipeline = unpredictable behavior.

### Persistence Strategy

```javascript
// Pattern: checkpoint token after each successful event processing
async function consumeChangeStream(collection, initialToken = null) {
  const options = initialToken ? { startAfter: initialToken } : {};
  const stream = collection.watch([], options);

  try {
    for await (const event of stream) {
      await processEvent(event);
      await saveToken(event._id);  // atomic checkpoint after successful processing
    }
  } catch (err) {
    if (err.code === 286) {  // ChangeStreamHistoryLost
      // Oplog window exceeded — restart from scratch or handle data gap
      await handleHistoryLost();
    } else {
      throw err;
    }
  }
}
```

**Token storage options:**
1. **Same MongoDB collection** — atomic with business data using transactions
2. **Dedicated tokens collection** — simple upsert on a well-known key
3. **Redis/external cache** — low-latency, but adds dependency and consistency risk
4. **Kafka offset** — when using the Kafka connector, it stores the token as the Kafka offset automatically

**Checkpoint frequency:** checkpoint after every event for exactly-once-like guarantees, or batch-checkpoint for throughput with at-least-once semantics.

### Invalidate Events and Recovery

An `invalidate` event fires when the watched namespace is dropped, renamed, or the database is dropped. The cursor closes automatically after delivering the invalidate event.

```javascript
changeStream.on('change', async (event) => {
  if (event.operationType === 'invalidate') {
    // Token from invalidate event is only usable with startAfter, not resumeAfter
    const token = event._id;
    // Option 1: wait and reopen
    await waitForCollectionRecreation(event.ns.coll);
    reopenStream(token);  // use startAfter
    // Option 2: treat as terminal, alert, escalate
  }
});
```

---

## Pre- and Post-Images (MongoDB 6.0+)

### What They Are

- **Post-image** (`fullDocument: 'whenAvailable'` or `'required'`): the full document state *after* an update
- **Pre-image** (`fullDocumentBeforeChange: 'whenAvailable'` or `'required'`): the full document state *before* an update

These are distinct from the basic `fullDocument: 'updateLookup'` option (which fetches current state at read time, potentially stale).

### Configuration

**Step 1: Enable on the collection**

```javascript
// New collection
db.createCollection("orders", {
  changeStreamPreAndPostImages: { enabled: true }
});

// Existing collection
db.runCommand({
  collMod: "orders",
  changeStreamPreAndPostImages: { enabled: true }
});
```

**Step 2: Set retention policy (optional)**

```javascript
// Cluster-level parameter — default retains until oplog removes the event
db.adminCommand({
  setClusterParameter: {
    changeStreamOptions: {
      preAndPostImages: { expireAfterSeconds: 3600 }  // 1 hour
    }
  }
});

// Check current setting
db.adminCommand({ getClusterParameter: "changeStreamOptions" });
```

**Step 3: Request in watch()**

```javascript
const stream = collection.watch([], {
  fullDocument: 'whenAvailable',              // post-image
  fullDocumentBeforeChange: 'whenAvailable'   // pre-image
});
// 'required' throws error if image is unavailable
// 'whenAvailable' returns null if image has expired or was never stored
```

### Storage Details

Pre-images are stored in `config.system.preimages` (a system collection). Monitor its size:

```javascript
db.getSiblingDB("config").system.preimages.stats()
```

**Warning:** Pre-image storage can grow significantly on write-heavy collections. Always configure `expireAfterSeconds` in production.

---

## Filtering Change Streams with Aggregation Pipeline

### Supported Stages

Change streams support a **subset** of aggregation stages:

| Stage | Use |
|-------|-----|
| `$match` | Filter events by any field |
| `$project` | Shape the output document |
| `$addFields` / `$set` | Add computed fields |
| `$unset` | Remove fields |
| `$replaceRoot` / `$replaceWith` | Restructure document |
| `$redact` | Field-level access control |

**NOT supported:** `$group`, `$sort`, `$limit`, `$skip`, `$lookup`, `$facet`, `$bucket`.

**IMPORTANT:** Do NOT modify or remove the `_id` field (resume token). MongoDB 4.2+ throws an exception if you attempt to project out `_id`.

### Filtering Patterns

```javascript
// Filter by operation type
collection.watch([
  { $match: { operationType: { $in: ['insert', 'update'] } } }
]);

// Filter by field value on inserts
collection.watch([
  { $match: {
    operationType: 'insert',
    'fullDocument.status': 'PENDING'
  }}
]);

// Filter by updated field
collection.watch([
  { $match: { 'updateDescription.updatedFields.priority': { $exists: true } } }
]);

// Project only needed fields (reduces network payload)
collection.watch([
  { $project: {
    operationType: 1,
    'fullDocument._id': 1,
    'fullDocument.status': 1,
    'documentKey': 1
  }}
]);

// Combined filter and projection
collection.watch([
  { $match: { operationType: { $ne: 'delete' } } },
  { $project: {
    operationType: 1,
    documentKey: 1,
    'fullDocument.userId': 1,
    'fullDocument.action': 1
  }}
]);
```

### Server-Side vs. Client-Side Filtering

**Always filter server-side** (in the pipeline) rather than in application code. The server evaluates the pipeline against oplog entries — unmatched events are never transmitted, saving bandwidth and CPU. This is especially important on high-write collections.

---

## Collection vs. Database vs. Deployment-Level Streams

| Scope | Command | Watches | Use When |
|-------|---------|---------|----------|
| Collection | `collection.watch()` | Single collection | Most common; lowest overhead |
| Database | `db.watch()` | All non-system collections in one DB | Multi-collection CDC within a DB |
| Deployment | `client.watch()` | All non-system collections across all DBs | Full database audit; cross-database sync |

**Deployment-level streams exclude:** `admin`, `local`, `config` databases.

**Performance note:** Wider scope = more events = higher overhead. Prefer collection-level with server-side `$match` filters over deployment-level with application-side filtering.

---

## Sharded Cluster Change Streams

### How `mongos` Orchestrates Streams

When `watch()` is called against a sharded cluster:
1. `mongos` opens **individual change streams on each shard**
2. Results arrive at `mongos` from all shards independently
3. `mongos` sorts and merges by global logical clock timestamp
4. `mongos` performs `fullDocument` lookups if requested
5. Total ordering is guaranteed across all shards

### Cold Shard Problem

Shards with little or no activity ("cold shards") delay the `mongos` merge — it must wait for confirmation from all shards before advancing the stream. This causes latency spikes.

**Mitigation:**

```javascript
// Reduce noop interval so idle shards heartbeat more frequently (default: 10s)
// Run on each shard primary (or mongos to broadcast)
db.adminCommand({ setParameter: 1, periodicNoopIntervalSecs: 2 });

// Manually write a no-op oplog entry to advance a specific shard's token.
// IMPORTANT: run this on the PRIMARY of the cold shard, not on mongos.
db.adminCommand({ appendOplogNote: 1, data: { msg: "heartbeat" } });
```

### Orphaned Documents

In MongoDB 5.3+, change stream events are **not generated** for writes to orphaned documents (documents that are in the process of being migrated between shards). This is expected behavior — the stream will eventually receive the event from the shard that owns the document.

### Resume Token Advancement on Idle Shards

On sharded clusters, highwatermark tokens on idle shards may not advance. Use `periodicNoopIntervalSecs` tuning or `appendOplogNote` to force advancement.

---

## Performance Considerations

### Connection Pool

Each open change stream consumes **one connection** (a persistent `getMore` request). If the number of open streams exceeds `maxPoolSize`, new change events will be delayed until a connection is available.

```javascript
// Ensure pool size exceeds number of concurrent streams
const client = new MongoClient(uri, { maxPoolSize: 50 });
```

### Oplog Window Sizing

The oplog is a capped collection. If the consumer falls behind the oplog window, the resume token becomes invalid and the stream cannot be resumed.

```javascript
// Check oplog status
rs.printReplicationInfo()
// Output shows:
// configured oplog size: N MB
// log length start to end: N secs (N hrs)
// oplog last event time: ...

// Resize oplog (replica set member) — size is in MB
db.adminCommand({ replSetResizeOplog: 1, size: 51200 })  // 51200 MB = 50 GB
```

**Rule of thumb:** Size the oplog to retain at least 72 hours of operations — longer than your expected maximum consumer downtime or maintenance window.

### $changeStreamSplitLargeEvent (MongoDB 6.0.9+)

Change events are subject to the 16MB BSON document limit. Large documents on insert/replace, or `fullDocument: updateLookup` on large docs, can exceed this limit.

```javascript
collection.watch([
  { $changeStreamSplitLargeEvent: {} }
]);
// Events exceeding 16MB are split into fragments with:
// splitEvent: { fragment: 1, of: N }
```

### Index Limitations

**Change streams cannot use indexes.** The oplog is a capped collection with no indexes. This means you cannot accelerate change stream filtering with indexes — server-side `$match` in the pipeline is the only optimization lever.

### Anti-Patterns

- Opening many highly-specific change streams on the same collection — each stream opens a cursor; prefer one stream with `$match` filters
- Using `fullDocument: 'updateLookup'` on large documents without filtering — adds a secondary read per event, may return stale data, and risks hitting 16MB limit
- Client-side filtering instead of pipeline `$match` — wastes network and CPU
- Missing `expireAfterSeconds` on pre-image collections in production — pre-image storage grows unbounded

---

## Driver Patterns

### Node.js — Event Emitter Pattern

```javascript
const { MongoClient } = require('mongodb');

async function startChangeStream(uri, dbName, collName) {
  const client = new MongoClient(uri, { maxPoolSize: 20 });
  await client.connect();

  const collection = client.db(dbName).collection(collName);
  let resumeToken = await loadPersistedToken();

  const options = resumeToken ? { startAfter: resumeToken } : {};
  const changeStream = collection.watch(
    [{ $match: { operationType: { $in: ['insert', 'update', 'replace'] } } }],
    options
  );

  changeStream.on('change', async (event) => {
    try {
      await processEvent(event);
      resumeToken = event._id;
      await persistToken(resumeToken);
    } catch (err) {
      console.error('Processing error:', err);
      // Do not advance token on processing failure
    }
  });

  changeStream.on('error', async (err) => {
    if (err.code === 286) {
      console.error('ChangeStreamHistoryLost — oplog window exceeded');
      resumeToken = null;  // must restart from scratch
      await changeStream.close();
      // Re-open without token, handle data gap
    } else {
      console.error('Change stream error:', err);
    }
  });

  changeStream.on('close', () => {
    console.log('Change stream closed');
  });

  return changeStream;
}
```

### Node.js — Async Iterator Pattern (preferred for back-pressure)

```javascript
async function* watchOrders(collection) {
  const changeStream = collection.watch([
    { $match: { operationType: 'insert' } }
  ]);

  try {
    for await (const event of changeStream) {
      yield event;
    }
  } finally {
    await changeStream.close();
  }
}

// Usage
for await (const event of watchOrders(ordersCollection)) {
  await processOrder(event.fullDocument);
  await persistToken(event._id);
}
```

### Python (PyMongo) — with Statement Pattern

```python
from pymongo import MongoClient
from pymongo.errors import PyMongoError

client = MongoClient(uri)
collection = client["mydb"]["orders"]

resume_token = load_persisted_token()

pipeline = [{"$match": {"operationType": {"$in": ["insert", "update"]}}}]
options = {"start_after": resume_token} if resume_token else {}

try:
    with collection.watch(pipeline, **options) as stream:
        for event in stream:
            process_event(event)
            persist_token(stream.resume_token)  # always read from stream, not event._id
except PyMongoError as e:
    if "ChangeStreamHistoryLost" in str(e):
        handle_history_lost()
    else:
        raise
```

**PyMongo note:** Read the resume token from `stream.resume_token` (the stream object), not `event["_id"]`. PyMongo advances `resume_token` using `postBatchResumeToken` for more accurate position tracking.

### Go Driver Pattern

```go
import (
    "context"
    "go.mongodb.org/mongo-driver/bson"
    "go.mongodb.org/mongo-driver/mongo"
    "go.mongodb.org/mongo-driver/mongo/options"
)

func watchCollection(ctx context.Context, collection *mongo.Collection, token bson.Raw) error {
    pipeline := mongo.Pipeline{
        {{"$match", bson.D{{"operationType", bson.D{{"$in", bson.A{"insert", "update"}}}}}}},
    }

    opts := options.ChangeStream().SetFullDocument(options.UpdateLookup)
    if token != nil {
        opts.SetStartAfter(token)
    }

    stream, err := collection.Watch(ctx, pipeline, opts)
    if err != nil {
        return err
    }
    defer stream.Close(ctx)

    for stream.Next(ctx) {
        var event bson.M
        if err := stream.Decode(&event); err != nil {
            return err
        }
        if err := processEvent(event); err != nil {
            return err
        }
        persistToken(stream.ResumeToken())
    }
    return stream.Err()
}
```

### Java Driver Pattern

```java
import com.mongodb.client.model.Aggregates;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.changestream.FullDocument;

MongoCollection<Document> collection = db.getCollection("orders");

// Use Aggregates.match() for pipeline stages, not Filters.eq("$match", ...)
List<Bson> pipeline = Arrays.asList(
    Aggregates.match(Filters.in("operationType", Arrays.asList("insert", "update")))
);

ChangeStreamIterable<Document> changeStream = collection.watch(pipeline)
    .fullDocument(FullDocument.UPDATE_LOOKUP);

// If resuming
if (savedToken != null) {
    changeStream = changeStream.startAfter(savedToken);
}

try (MongoCursor<ChangeStreamDocument<Document>> cursor = changeStream.iterator()) {
    while (cursor.hasNext()) {
        ChangeStreamDocument<Document> event = cursor.next();
        processEvent(event);
        persistToken(event.getResumeToken());
    }
}
```

### C# / .NET Driver Pattern

```csharp
using MongoDB.Driver;
using MongoDB.Bson;

var collection = database.GetCollection<BsonDocument>("orders");

var pipeline = new EmptyPipelineDefinition<ChangeStreamDocument<BsonDocument>>()
    .Match(change =>
        change.OperationType == ChangeStreamOperationType.Insert ||
        change.OperationType == ChangeStreamOperationType.Update ||
        change.OperationType == ChangeStreamOperationType.Replace);

var options = new ChangeStreamOptions
{
    FullDocument = ChangeStreamFullDocumentOption.UpdateLookup,
    ResumeAfter = savedToken  // BsonDocument resume token, or null for new stream
};

using var cursor = collection.Watch(pipeline, options);
foreach (var change in cursor.ToEnumerable())
{
    ProcessEvent(change);
    PersistToken(change.ResumeToken);
}
```

**C# notes:**
- `ResumeAfter` accepts a `BsonDocument` token; use `StartAfter` instead when recovering from an `invalidate` event.
- `ChangeStreamFullDocumentOption.WhenAvailable` and `Required` correspond to the pre/post image options (MongoDB 6.0+).
- For async consumption, use `cursor.MoveNextAsync()` in a loop or wrap with `IAsyncCursor`.

---

## Access Control

```javascript
// Collection-level change stream privilege
{
  resource: { db: "mydb", collection: "orders" },
  actions: ["find", "changeStream"]
}

// Database-level
{ resource: { db: "mydb", collection: "" }, actions: ["find", "changeStream"] }

// Deployment-level
{ resource: { db: "", collection: "" }, actions: ["find", "changeStream"] }
```

---

## Atlas Triggers vs. Manual Change Streams

| | Database Triggers (Atlas) | Manual Change Streams |
|---|---|---|
| **Infrastructure** | Serverless (Atlas App Services manages) | Self-managed (your process) |
| **Language** | JavaScript only | Any driver language |
| **Resume** | Automatic (managed by App Services) | Manual (you persist tokens) |
| **Scale** | Up to trigger limits per project | Only limited by your app |
| **Latency** | Higher (serverless cold start) | Lower (persistent process) |
| **Cost** | App Services pricing (compute + invocations) | Your infra cost |
| **Use when** | Simple serverless automation, notifications | Complex logic, multi-language, low latency |

**Trigger limitations to know:**
- Each trigger opens a change stream; too many triggers per project degrades performance
- Triggers run in Atlas App Services JavaScript runtime (not full Node.js)
- Functions have a max execution time (default 90s, configurable up to 300s)

---

## Atlas Stream Processing Integration

Atlas Stream Processing (ASP) uses change streams as one of its native source types. Unlike manual change stream consumption, ASP provides:

- Windowing operations (tumbling, hopping, session windows)
- Joins between streams and Atlas collections
- Dead Letter Queue (DLQ) for failed messages
- Built-in resumability managed by ASP
- Writing results to Atlas collections (`$merge`) or Kafka topics (`$emit`)

```javascript
// Atlas Stream Processing — change stream source
{
  $source: {
    connectionName: "myAtlasConnection",
    db: "mydb",
    coll: "orders",
    // Optional: filter with $match-equivalent
    pipeline: [
      { $match: { operationType: "insert" } }
    ]
  }
}
```

**Recommendation:** Size the source cluster's oplog window to at least 24 hours when using ASP change stream sources.

---

## Kafka Connector CDC Pattern

The MongoDB Kafka Source Connector wraps change streams to provide production-grade CDC:

```properties
# Source connector configuration
connector.class=com.mongodb.kafka.connect.MongoSourceConnector
connection.uri=mongodb://...
database=mydb
collection=orders

# Pipeline filter
pipeline=[{"$match": {"operationType": {"$in": ["insert", "update", "replace", "delete"]}}}]

# Full document on updates
change.stream.full.document=updateLookup

# Startup behavior when no offset exists
startup.mode=latest  # or: earliest, timestamp, copy_existing

# Heartbeat to prevent resume token staleness
heartbeat.interval.ms=10000
```

**Resume token persistence:** The Kafka connector stores the change stream resume token as its Kafka consumer offset. On restart, it uses the stored offset (= resume token) to continue exactly where it left off. If the oplog window is exceeded, use `startup.mode=copy_existing` to re-snapshot.

---

## Common Use Cases

### 1. Cache Invalidation

```javascript
// Invalidate Redis cache entries when documents change
collection.watch([{ $match: { operationType: { $in: ['update', 'replace', 'delete'] } } }])
  .on('change', async (event) => {
    const docId = event.documentKey._id.toString();
    await redis.del(`doc:${docId}`);
    console.log(`Cache invalidated for ${docId}`);
  });
```

### 2. Audit Logging

```javascript
// Write immutable audit trail for every change
collection.watch([], {
  fullDocument: 'whenAvailable',
  fullDocumentBeforeChange: 'whenAvailable'
}).on('change', async (event) => {
  await auditLog.insertOne({
    timestamp: new Date(),
    collection: event.ns.coll,
    operation: event.operationType,
    documentId: event.documentKey._id,
    before: event.fullDocumentBeforeChange,
    after: event.fullDocument,
    user: event.lsid  // session info if within transaction
  });
});
```

### 3. Search Index Synchronization (Elasticsearch)

```javascript
// Only watch DML operations — drop/rename events have no documentKey/_id
collection.watch([{
  $match: { operationType: { $in: ['insert', 'update', 'replace', 'delete'] } }
}]).on('change', async (event) => {
  const id = event.documentKey._id.toString();
  if (event.operationType === 'delete') {
    await esClient.delete({ index: 'orders', id });
  } else {
    // fullDocument is present for insert/replace; use updateLookup for update events
    await esClient.index({ index: 'orders', id, document: event.fullDocument });
  }
});
```

### 4. Event Sourcing / CQRS Read Model Updates

```javascript
// Write side: normal MongoDB writes
// Read side: change stream updates denormalized read models
ordersCollection.watch([
  { $match: { operationType: { $in: ['insert', 'update', 'replace'] } } }
]).on('change', async (event) => {
  // Rebuild denormalized read model in a separate collection
  await orderSummaryCollection.updateOne(
    { _id: event.documentKey._id },
    { $set: buildOrderSummary(event.fullDocument) },
    { upsert: true }
  );
});
```

### 5. Cross-Collection / Cross-Service Sync

```javascript
// Keep a secondary collection in sync (poor-man's materialized view)
sourceCollection.watch([{
  $match: { operationType: { $in: ['insert', 'update', 'replace', 'delete'] } }
}]).on('change', async (event) => {
  const { operationType, documentKey, fullDocument } = event;
  if (operationType === 'insert' || operationType === 'replace') {
    await mirrorCollection.replaceOne({ _id: documentKey._id }, fullDocument, { upsert: true });
  } else if (operationType === 'update') {
    // Guard: updateDescription may be null in some edge cases (e.g. retryable write replay)
    const updatedFields = event.updateDescription?.updatedFields ?? {};
    const removedFields = event.updateDescription?.removedFields ?? [];
    const unsetDoc = removedFields.reduce((acc, f) => ({ ...acc, [f]: '' }), {});
    const updateOp = {};
    if (Object.keys(updatedFields).length) updateOp.$set = updatedFields;
    if (Object.keys(unsetDoc).length) updateOp.$unset = unsetDoc;
    if (Object.keys(updateOp).length) {
      await mirrorCollection.updateOne({ _id: documentKey._id }, updateOp);
    }
  } else if (operationType === 'delete') {
    await mirrorCollection.deleteOne({ _id: documentKey._id });
  }
});
```

---

## Troubleshooting Reference

| Error / Symptom | Cause | Resolution |
|---|---|---|
| `ChangeStreamHistoryLost` (code 286) | Resume token no longer in oplog | Increase oplog size; restart stream without token; handle data gap |
| Stream sends no events after cluster change | PSA topology with the secondary down: only 1 data-bearing node available (the arbiter holds no data), so no write can be majority-committed | Restore/add a data-bearing node so majority is met; check `writeConcernMajorityJournalDefault` |
| High latency on sharded cluster | Cold shards blocking `mongos` merge | Lower `periodicNoopIntervalSecs`; run `appendOplogNote` on cold shards |
| `16MB document limit exceeded` | Large `fullDocument` or event on big document | Use `$changeStreamSplitLargeEvent`; filter fields with `$project` |
| Pre-image is `null` with `'required'` | Pre-images not enabled on collection, or expired | Enable `changeStreamPreAndPostImages`; configure `expireAfterSeconds` |
| `InvalidResumeToken` after collection drop | Trying `resumeAfter` on an invalidate event token | Use `startAfter` instead of `resumeAfter` |
| Stream opens but `fullDocument` is `null` on update | Default behavior — update events don't include full document | Use `fullDocument: 'updateLookup'` option, or enable pre/post images |
| `getMore` errors, stream drops | Network timeout, idle stream | Drivers auto-resume; ensure retry logic wraps outer cursor creation |

---

## Version Compatibility Quick Reference

| Feature | Min Version |
|---------|-------------|
| Change streams (collection-level) | MongoDB 3.6 |
| Database + deployment-level streams | MongoDB 4.0 |
| Transaction support in streams | MongoDB 4.0 |
| `startAfter` option | MongoDB 4.1.1 |
| `startAtOperationTime` | MongoDB 4.0 |
| 5.1 optimizations | MongoDB 5.1 |
| Pre/post images (`fullDocumentBeforeChange`) | MongoDB 6.0 |
| `showExpandedEvents` | MongoDB 6.0 |
| `wallTime` field | MongoDB 6.0 |
| `$changeStreamSplitLargeEvent` | MongoDB 6.0.9 |
| `disambiguatedPaths` | MongoDB 6.1 |
| Orphaned document event exclusion | MongoDB 5.3 |

---

## Sources

1. [MongoDB Change Streams — Database Manual](https://www.mongodb.com/docs/manual/changestreams/) — canonical architecture, watch() signatures, resume tokens, pre/post images
2. [Change Events — Database Manual](https://www.mongodb.com/docs/manual/reference/change-events/) — all operationType values
3. [Update Event — Database Manual](https://www.mongodb.com/docs/manual/reference/change-events/update/) — updateDescription, disambiguatedPaths
4. [Change Streams Production Recommendations — MongoDB Docs](https://www.mongodb.com/docs/manual/administration/change-streams-production-recommendations/) — oplog sizing, sharded cluster cold shard problem, anti-patterns
5. [MongoDB Kafka Connector — Change Stream Configuration](https://www.mongodb.com/docs/kafka-connector/current/source-connector/fundamentals/change-streams/) — CDC resume token as Kafka offset, startup modes
6. [changeStreamOptions Cluster Parameter](https://www.mongodb.com/docs/manual/reference/cluster-parameters/changestreamoptions/) — pre/post image TTL
7. [Severalnines: Tips for Running MongoDB Change Streams in Production](https://severalnines.com/blog/tips-running-mongodb-production-using-change-streams/) — real-world sharded cluster notes
8. [Tinybird: Practical Guide to Real-Time CDC with MongoDB](https://www.tinybird.co/blog/mongodb-cdc) — CDC architecture patterns
9. [MongoDB Blog: Introducing Atlas Stream Processing](https://www.mongodb.com/blog/post/introducing-atlas-stream-processing-simplifying-path-reactive-responsive-even-driven-apps) — ASP change stream source integration
10. [GeeksforGeeks: MongoDB Realm Triggers vs Change Streams](https://www.geeksforgeeks.org/mongodb/what-are-the-differences-between-mongodb-realm-triggers-and-change-streams-in-nodejs/) — triggers vs streams comparison
11. [MongoDB Specs: change-streams.md](https://github.com/mongodb/specifications/blob/master/source/change-streams/change-streams.md) — driver spec for resumption behavior

## See also: MongoDB Spark Connector (change streams as a Spark source)

When a change stream feeds a **Spark Structured Streaming** pipeline (Databricks, EMR, or stand-alone Spark), load `mongodb-spark-connector`. The connector wraps the change stream cursor in a Spark streaming source and persists the resume token in Spark's `checkpointLocation` instead of an application-managed store.

Key interaction points:
- The Spark checkpoint becomes the resume-token store. If the checkpoint is deleted or expires past the oplog window, the stream restarts with `ChangeStreamHistoryLost` — the same failure mode as a stale application-side resume token, but the recovery flow is different (delete checkpoint + restart with `change.stream.startup.mode=latest`).
- `change.stream.publish.full.document.only=true` emits the post-image directly to Spark, matching the rule "design the consumer for `fullDocument`, not the change envelope" recommended here.
- `change.stream.full.document=updateLookup` triggers the same post-image lookup behavior described in this skill.
- Server-side filtering belongs in `aggregation.pipeline` (Spark Connector option), which maps to the same change-stream `$match` stage covered in this skill's "Filter changes server-side" section.

Use `mongodb-spark-connector` when the consumer is Spark; stay in `mongodb-change-streams` when the consumer is a driver-level application (Node/Python/Go/Java) outside Spark.
