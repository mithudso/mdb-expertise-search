<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-cdc-architecture` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

# MongoDB CDC Architecture

Authoritative reference for Change Data Capture (CDC) patterns that propagate MongoDB changes to downstream systems. Covers transport selection, outbox pattern, event sourcing, data warehouse pipelines, Debezium configuration, Atlas Stream Processing, exactly-once semantics, schema evolution, pipeline monitoring, and anti-patterns.

## Overview

Change Data Capture captures every insert, update, and delete that occurs in MongoDB and delivers those changes—in order, reliably—to downstream consumers. MongoDB provides four native transport mechanisms, each with distinct trade-offs for latency, ordering, replay, and operational complexity.

**When CDC is the right approach:**
- Real-time analytics or search index synchronization (sub-second freshness required)
- Microservice event publishing without dual-write risk (outbox pattern)
- Data warehouse replication from an operational MongoDB store
- Event sourcing where MongoDB is the durable event store
- Cross-service consistency where distributed transactions are undesirable

**When CDC is NOT the right approach:**
- Batch ETL jobs running on a schedule are sufficient
- Source collections are time-series collections (change streams not supported)
- Eventual consistency windows of hours are acceptable (use periodic snapshots instead)
- You need only change stream API syntax with no downstream pipeline (use [[mongodb-change-streams]])
- Simple serverless reactive workflows (notifications, small syncs) without a message broker (use [[mongodb-atlas-triggers-functions]])

---

## 1. CDC Transport Options

### Comparison Matrix

| Transport | Latency | Ordering | Delivery | Replay | Ops Complexity | Cost Model |
|---|---|---|---|---|---|---|
| Native Change Streams | Sub-100ms | Per-collection total; no cross-collection guarantee | At-least-once (with resume token) | Resume from token (oplog window) | Low (in-process) | Included in MongoDB |
| MongoDB Kafka Connector | 100ms–1s | Per-topic partition (partition by `_id`) | At-least-once; EOS with Kafka transactions | Full Kafka topic replay | Medium (Kafka + Connect) | Kafka infra cost |
| Debezium MongoDB Connector | 100ms–1s | Oplog-ordered per replica set | At-least-once | Resume from offset/oplog | Medium-High (Kafka + ZK + Connect) | Open source + Kafka infra |
| Atlas Stream Processing | Sub-500ms | Per stream processor (single-threaded by default) | At-least-once with DLQ | startAfter / startAtOperationTime | Low (fully managed) | ASP instance pricing |
| Atlas Triggers | 1–5s (invocation overhead) | Sequential (ordered) or concurrent (unordered, 10K events max) | At-least-once | No native replay | Very Low (serverless) | App Services invocation |

### 1.1 Native Change Streams

Change streams are MongoDB's recommended CDC primitive. They watch the oplog and surface an ordered, resumable stream of change events.

**Watch levels:**
```javascript
// Collection level — most common for CDC
const stream = db.collection('orders').watch(pipeline, options);

// Database level — all non-system collections in one stream
const stream = db.watch(pipeline, options);

// Deployment level — all databases/collections
const stream = client.watch(pipeline, options);
```

**Key guarantees:**
- Only notifies on majority-committed changes — durability is assured
- Resume tokens reference the oplog `_id`; store them durably after each processed batch
- Cross-collection ordering on database/deployment streams is NOT guaranteed
- Requires WiredTiger storage engine + replica set or sharded cluster

**Sources:** [MongoDB Change Streams Manual](https://www.mongodb.com/docs/manual/changestreams/), [Streamkap CDC Guide](https://streamkap.com/resources-and-guides/mongodb-change-data-capture)

### 1.2 MongoDB Kafka Connector (Source)

The official MongoDB Kafka Connector uses change streams internally and publishes events to Kafka topics. Resume tokens are stored as Kafka Connect offsets.

**Key source connector config:**
```properties
connector.class=com.mongodb.kafka.connect.MongoSourceConnector
connection.uri=mongodb+srv://user:pass@cluster.mongodb.net/
database=mydb
collection=orders
# Publish the full current document on every update
publish.full.document.only=true
# Pipeline to filter/project events
pipeline=[{"$match": {"operationType": {"$in": ["insert","update","replace"]}}}]
# Partition by document _id to preserve per-document ordering in Kafka
topic.partition.strategy=com.mongodb.kafka.connect.source.topic.mapping.PartitionByKey
# Error handling
errors.tolerance=all
errors.deadletterqueue.topic.name=cdc-errors-dlq
```

**Offset management:** On first start, opens a new change stream. After the first event, stores the resume token as the Kafka Connect offset in the offsets topic. On restart, resumes from that token. If the token is invalid (oplog rolled), set `offset.partition.name` to a new value to force a fresh start.

**Sources:** [MongoDB Kafka Connector Change Streams Docs](https://www.mongodb.com/docs/kafka-connector/current/source-connector/fundamentals/change-streams/), [Invalid Resume Token Recovery](https://www.mongodb.com/docs/kafka-connector/current/troubleshooting/recover-from-invalid-resume-token/)

### 1.3 Debezium MongoDB Connector

Debezium uses MongoDB's change streams (not direct oplog tailing in recent versions) and provides a consistent CDC event envelope across all supported databases.

**When to prefer Debezium over MongoDB Kafka Connector:**
- You need a unified CDC platform across multiple database types (Postgres, MySQL, MongoDB)
- You need the Debezium Outbox Event Router SMT
- You want the full Debezium event envelope (source metadata, transaction ID, ts_ms)
- You use Confluent Schema Registry with Avro/JSON Schema serialization

**When to prefer MongoDB Kafka Connector:**
- MongoDB-only source, no multi-DB requirement
- You want MongoDB-native support and guarantees
- Simpler operational profile preferred

### 1.4 Atlas Stream Processing

Atlas Stream Processing (ASP) is a fully managed stream processing engine that natively ingests Atlas change streams or Kafka topics using familiar aggregation pipeline syntax. ASP is available on AWS and Azure as of March 2025.

```javascript
// Create a stream processor: change stream → filter → sink to Atlas
sp.createStreamProcessor("order-cdc", [
  {
    "$source": {
      "connectionName": "cluster0-connection",
      "db": "shop",
      "coll": "orders",
      "config": {
        "fullDocument": "updateLookup",
        "fullDocumentBeforeChange": "whenAvailable",
        "pipeline": [
          { "$match": { "operationType": { "$in": ["insert","update","replace"] } } }
        ]
      }
    }
  },
  { "$match": { "fullDocument.status": "PENDING" } },
  {
    "$merge": {
      "into": {
        "connectionName": "analytics-connection",
        "db": "analytics",
        "coll": "pending_orders"
      }
    }
  }
]);
```

**ASP $source configuration options:**

| Option | Values | Notes |
|---|---|---|
| `config.fullDocument` | `default`, `updateLookup`, `required`, `whenAvailable` | Controls post-image content |
| `config.fullDocumentBeforeChange` | `off`, `required`, `whenAvailable` | Pre-image (MongoDB 6.0+) |
| `config.startAfter` | resume token | Resume from specific event |
| `config.startAtOperationTime` | BSON timestamp | Time-based start |
| `config.pipeline` | aggregation array | Pre-filter before processing stages |
| `initialSync.enable` | boolean | Backfill existing documents on start |

**Important:** Configure source cluster with oplog window of at least 24 hours. Do not modify `wallTime` or `clusterTime` in source pipeline stages.

**Caution — `updateLookup` on high-delete collections:** The `fullDocument: "updateLookup"` option performs a post-update read. If the document is deleted between the update and the lookup, `fullDocument` is null. Combined with a `$match` that requires `fullDocument`, the cursor can fault with `Resume Token Not Found`. On MongoDB 6.0+ with `changeStreamPreAndPostImages` enabled, prefer `fullDocument: "whenAvailable"` instead (see Section 10.5).

**New in 2025:** ASP `$iceberg` sink stage (private preview) writes directly to Iceberg tables in cloud object storage, readable natively by Snowflake and Databricks.

**Sources:** [ASP $source Stage Docs](https://www.mongodb.com/docs/atlas/atlas-stream-processing/sp-agg-source/), [ASP Medium Intro](https://medium.com/mongodb/mongodb-atlas-stream-processing-your-first-steps-bcb2814034ca)

### 1.5 Atlas Triggers

Atlas Triggers are serverless, declarative event handlers built on top of change streams via Atlas App Services.

**Best for:** Simple reactive workflows — sending notifications, syncing small datasets, calling external APIs — where sub-second latency is not required and exactly-once delivery is handled by idempotent Functions.

**Limitations:** No native replay, invocation overhead (1–5s), max 10,000 concurrent unordered executions, not suitable for high-throughput CDC pipelines.

**Sources:** [Atlas Triggers Docs](https://www.mongodb.com/docs/atlas/atlas-ui/triggers/), [Triggers vs Change Streams Community](https://www.mongodb.com/community/forums/t/question-regarding-changestreams-vs-triggers-and-limitations-in-concurrent-connections/16379)

---

## 2. Outbox Pattern

The transactional outbox pattern solves the dual-write problem: atomically writing a business change and its corresponding event to the same MongoDB replica set, then asynchronously publishing to the message broker via CDC.

### 2.1 Core Pattern

```javascript
// Write business document + outbox event in a single MongoDB transaction
const session = client.startSession();
await session.withTransaction(async () => {
  await db.collection('orders').insertOne(
    { _id: orderId, customerId, items, status: 'PLACED', total },
    { session }
  );

  await db.collection('outbox').insertOne({
    _id: new ObjectId(),
    aggregatetype: 'Order',       // Maps to Kafka topic
    aggregateid: orderId.toString(), // Kafka message key
    type: 'OrderPlaced',           // Event type
    payload: { orderId, customerId, items, total },
    createdAt: new Date()
  }, { session });
});
```

**Outbox collection schema (Debezium-compatible default):**

| Field | Type | Description |
|---|---|---|
| `_id` | ObjectId | Event identifier |
| `aggregatetype` | String | Maps to Kafka topic (e.g., `Order`) |
| `aggregateid` | String/ObjectId | Kafka message key (e.g., order ID) |
| `type` | String | Event type name (e.g., `OrderPlaced`) |
| `payload` | Object | Event data (serialized as BSON) |
| `createdAt` | Date | Used for TTL cleanup |
| `processed` | Boolean | Optional flag; set to `true` after relay confirms delivery |

### 2.2 Debezium Outbox Event Router SMT

The `MongoEventRouter` Single Message Transformation routes outbox collection events to topic-per-aggregate-type and extracts the payload as the Kafka message value.

```properties
# Kafka Connect connector config with Outbox SMT
transforms=outbox
transforms.outbox.type=io.debezium.connector.mongodb.transforms.outbox.MongoEventRouter
transforms.outbox.route.by.field=aggregatetype
transforms.outbox.table.field.event.id=_id
transforms.outbox.table.field.event.key=aggregateid
transforms.outbox.table.field.event.payload=payload
# Optional: route to specific topic prefix
transforms.outbox.route.topic.replacement=outbox.event.${routedByValue}
```

**Routing behavior:**
1. Debezium captures the insert to `outbox` collection
2. SMT extracts `aggregatetype` → routes to topic `outbox.event.Order`
3. SMT sets message key to `aggregateid` value
4. SMT sets message value to `payload` field content
5. Delete events from outbox are filtered out (tombstone suppression)

**Sources:** [Debezium MongoDB Outbox Event Router](https://debezium.io/documentation/reference/stable/transformations/mongodb-outbox-event-router.html), [Outbox Pattern Implementation](https://vkontech.com/the-outbox-pattern-with-mongo-kafka-and-debezium-in-c/)

### 2.3 TTL Cleanup

Add a TTL index on `createdAt` to automatically delete processed outbox events. The cleanup is a correctness-independent concern — Debezium only reads inserts, not the current state of the outbox collection.

```javascript
// TTL index: delete outbox documents after 7 days
db.outbox.createIndex(
  { createdAt: 1 },
  { expireAfterSeconds: 604800, name: 'outbox_ttl' }
);

// Optional: partial index for efficiency — only index unprocessed events
db.outbox.createIndex(
  { createdAt: 1, processed: 1 },
  {
    partialFilterExpression: { processed: false },
    expireAfterSeconds: 86400,
    name: 'outbox_pending_ttl'
  }
);
```

### 2.4 Outbox vs Change Stream Direct Publish

| | Outbox Pattern | Direct Change Stream Publish |
|---|---|---|
| Atomicity | Guaranteed (single transaction) | Requires two writes; risk of partial failure |
| Infrastructure | Requires Debezium/CDC consumer | Application publishes directly to Kafka |
| Replay | Replay from Kafka | Must re-query MongoDB or re-run business logic |
| Schema coupling | Decoupled (payload is explicit) | Event shape tied to document structure |
| Latency | +50–200ms (extra hop) | Lower (direct) |
| Best for | Microservices, strict ordering | Simple notifications, lower throughput |

**Sources:** [Kafka Idempotent Consumer & Transactional Outbox](https://www.lydtechconsulting.com/blog/kafka-idempotent-consumer-transactional-outbox), [Change Streams vs Outbox DEV Community](https://dev.to/deyanp/use-change-streams-instead-of-traditional-outbox-or-distributed-transactions-cdb)

---

## 3. Event Sourcing with MongoDB

### 3.1 Event Store Collection Design

Store event streams as documents (one document per aggregate stream) using optimistic concurrency via stream position.

```javascript
// Event stream document structure
{
  streamName: "Order:ord-12345",        // {streamType}:{streamId}
  metadata: {
    streamType: "Order",
    streamId: "ord-12345",
    streamPosition: 7,                   // Version / event count
    createdAt: ISODate("2025-01-10T..."),
    updatedAt: ISODate("2025-06-01T...")
  },
  events: [
    {
      type: "OrderPlaced",
      data: { customerId: "c-99", items: [...], total: 149.99 },
      timestamp: ISODate("2025-01-10T10:00:00Z"),
      version: 1
    },
    {
      type: "OrderShipped",
      data: { trackingNumber: "UPS-123", carrier: "UPS" },
      timestamp: ISODate("2025-01-11T08:30:00Z"),
      version: 2
    }
    // ... up to 16MB per document
  ]
}
```

**Recommended indexes:**
```javascript
// Primary lookup by stream
db.events.createIndex({ streamName: 1 }, { unique: true });

// Optional: per-type partitioning for large collections
// Store in separate collections: orders_events, inventory_events
```

### 3.2 Atomic Append with Optimistic Concurrency

```javascript
async function appendEvents(streamName, expectedPosition, newEvents) {
  const result = await db.collection('events').updateOne(
    {
      streamName,
      "metadata.streamPosition": expectedPosition  // Optimistic lock
    },
    {
      $push: { events: { $each: newEvents } },
      $inc: { "metadata.streamPosition": newEvents.length },
      $set: { "metadata.updatedAt": new Date() },
      $setOnInsert: {
        "metadata.streamType": streamName.split(':')[0],
        "metadata.streamId": streamName.split(':')[1],
        "metadata.createdAt": new Date()
      }
    },
    { upsert: true }
  );

  if (result.matchedCount === 0 && result.upsertedCount === 0) {
    throw new Error(`Concurrency conflict on stream ${streamName} at position ${expectedPosition}`);
  }
}
```

### 3.3 Snapshot Pattern

Snapshots capture aggregate state every N events to avoid full replay on load. Use the memento pattern.

```javascript
// Snapshot document
{
  streamName: "Order:ord-12345",
  snapshotVersion: 50,              // streamPosition at snapshot time
  state: { status: "SHIPPED", total: 149.99, items: [...] },
  createdAt: ISODate("2025-06-01T...")
}

// Load aggregate: read snapshot + replay events after snapshot
async function loadAggregate(streamName) {
  const snapshot = await db.snapshots.findOne(
    { streamName },
    { sort: { snapshotVersion: -1 } }
  );

  const fromVersion = snapshot ? snapshot.snapshotVersion : 0;
  const stream = await db.events.findOne({ streamName });
  const eventsToReplay = stream.events.slice(fromVersion);

  return applyEvents(snapshot?.state ?? {}, eventsToReplay);
}
```

### 3.4 Atlas Stream Processing for Event Stream Materialization

Use ASP to continuously rebuild read-model projections from event streams. Because the event store document contains the full `events` array and is updated on every append, use `$match` on `operationType` to process only the change event, then project the specific fields needed for the read model rather than unwinding the entire array (which would re-project all historical events on each append):

```javascript
sp.createStreamProcessor("order-projection", [
  {
    "$source": {
      "connectionName": "cluster0",
      "db": "eventstore",
      "coll": "events",
      "config": { "fullDocument": "updateLookup" }
    }
  },
  {
    // Process inserts and updates (appended events trigger updates)
    "$match": { "operationType": { "$in": ["insert", "update"] } }
  },
  {
    // Project only the latest stream position and last event for the read model
    "$project": {
      "streamName": "$fullDocument.streamName",
      "streamPosition": "$fullDocument.metadata.streamPosition",
      // Use $arrayElemAt to get only the last event, not $unwind (which re-processes all)
      "lastEvent": { "$arrayElemAt": ["$fullDocument.events", -1] },
      "updatedAt": "$fullDocument.metadata.updatedAt"
    }
  },
  {
    "$merge": {
      "into": { "connectionName": "cluster0", "db": "readmodels", "coll": "order_status" },
      "on": "streamName",
      "whenMatched": "merge",
      "whenNotMatched": "insert"
    }
  }
]);
```

**Sources:** [MongoDB Event Store Design](https://event-driven.io/en/mongodb_event_store/), [Picking the Event Store](https://blog.jaykmr.com/picking-the-event-store-for-event-sourcing-988246a896bf), [Go EventSourcing CQRS](https://dev.to/aleksk1ng/go-eventsourcing-and-cqrs-with-postgresql-kafka-mongodb-and-elasticsearch-44d7)

---

## 4. CDC to Data Warehouses

### 4.1 MongoDB → Snowflake

**Architecture:** MongoDB → Kafka (source connector) → Kafka topic → Snowflake Kafka Connector → Snowflake staging table → autoMerge into target table.

```properties
# Snowflake Kafka Sink Connector config
connector.class=com.snowflake.kafka.connector.SnowflakeSinkConnector
snowflake.url.name=account.snowflakecomputing.com
snowflake.user.name=kafka_user
snowflake.private.key=<RSA_PRIVATE_KEY>
snowflake.database.name=PROD
snowflake.schema.name=MONGODB_CDC
topics=mongo.shop.orders
# Table name mapping
snowflake.topic2table.map=mongo.shop.orders:ORDERS
# Merge interval: how often staged events are merged
buffer.flush.time=30
# Schema evolution: Snowflake auto-detects new fields
```

**Key challenge — schema mapping:** MongoDB's flexible documents must be mapped to Snowflake columns. Options:
1. **VARIANT column**: Store the entire document as VARIANT — queryable with `:` accessor, no schema management needed
2. **Flattened columns**: Use a Kafka Streams or ksqlDB transformation to project a fixed schema before the Snowflake sink
3. **Hybrid**: Core fields as typed columns + `_extra` VARIANT for dynamic fields

**Sources:** [MongoDB to Snowflake CDC Streamkap](https://streamkap.com/resources-and-guides/mongodb-to-snowflake-cdc), [Confluent Production Best Practices](https://www.confluent.io/blog/mongodb-atlas-connectors-production-best-practices/), [Step-by-Step Guide Medium](https://medium.com/@santhoshkashyap1812/synchronizing-mongodb-data-with-snowflake-through-kafka-a-step-by-step-guide-0576782bb173)

### 4.2 MongoDB → BigQuery

**Option A — Google Dataflow (managed):** Use the `MongoDB_to_BigQuery_CDC` Dataflow template. Parameters: `mongoDbUri`, `database`, `collection`, `outputTableSpec`. Handles schema inference and streaming inserts.

**Option B — Kafka + BigQuery Kafka Connector:** MongoDB Kafka Connector → Kafka → BigQuery Kafka Sink Connector. Use `autoCreateTables=true` and `allowBigQueryRequiredFieldRelaxation=true` for schema flexibility.

**Option C — Airbyte/Fivetran:** Managed ELT platforms with pre-built MongoDB source and BigQuery destination connectors. Suitable for lower-frequency sync (minutes) without Kafka infrastructure.

**Sources:** [MongoDB to BigQuery Dataflow README](https://github.com/GoogleCloudPlatform/DataflowTemplates/blob/main/v2/mongodb-to-googlecloud/README_MongoDB_to_BigQuery_CDC.md), [Google Cloud Dataflow MongoDB Template](https://docs.cloud.google.com/dataflow/docs/guides/templates/provided/mongodb-to-bigquery)

### 4.3 MongoDB → Databricks / Delta Lake

**Architecture:** MongoDB → Kafka → Kafka consumer (Spark Structured Streaming) → Delta Lake with `autoMerge`.

```python
# Spark Structured Streaming: Kafka → Delta Lake with CDC merge
from delta.tables import DeltaTable

def upsertToDelta(microBatch, batchId):
    deltaTable = DeltaTable.forPath(spark, "/mnt/delta/orders")
    (deltaTable.alias("target")
      .merge(microBatch.alias("source"), "target._id = source._id")
      .whenMatchedUpdateAll()
      .whenNotMatchedInsertAll()
      .whenNotMatchedBySourceDelete()   # Handle CDC deletes
      .execute())

# Enable schema evolution globally
spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")

stream = (spark.readStream
  .format("kafka")
  .option("kafka.bootstrap.servers", "broker:9092")
  .option("subscribe", "mongo.shop.orders")
  .load()
  .writeStream
  .foreachBatch(upsertToDelta)
  .option("checkpointLocation", "/mnt/checkpoints/orders")
  .start())
```

**Delta Lake autoMerge for schema evolution:** `mergeSchema=true` adds new fields from incoming data. For type changes, use STRING or VARIANT columns for unstable fields.

**ASP $iceberg sink (2025 preview):** Atlas Stream Processing can write directly to Iceberg tables readable by both Databricks and BigQuery, eliminating the Kafka hop for Atlas-to-lakehouse pipelines.

**Sources:** [Databricks Schema Evolution](https://docs.databricks.com/aws/en/data-engineering/schema-evolution), [Airbyte Databricks Connector](https://docs.airbyte.com/integrations/destinations/databricks), [ASP Iceberg Preview](https://medium.com/towards-data-engineering/atlas-stream-processing-iceberg-private-preview-bfc163e09522)

### 4.4 MongoDB → Redshift

**Architecture:** MongoDB → Kafka → S3 Sink Connector → S3 → Redshift COPY command, OR MongoDB → Kafka → Redshift Kafka Sink Connector (direct streaming).

Use Confluent's Redshift Sink Connector with `insert.mode=UPSERT` and `pk.fields=_id` for CDC-style merges. For the S3 approach, configure Redshift Spectrum or `COPY` jobs to load from the S3 staging bucket on a schedule.

---

## 5. Debezium MongoDB Connector

### 5.1 Core Configuration

```properties
# Minimal Debezium MongoDB source connector
connector.class=io.debezium.connector.mongodb.MongoDbConnector
tasks.max=1

# Connection
mongodb.connection.string=mongodb+srv://user:pass@cluster.mongodb.net/
topic.prefix=dbserver1

# Scope
database.include.list=shop,inventory
collection.include.list=shop.orders,inventory.products

# Capture mode (MongoDB 6.0+: use change_streams_update_full_with_pre_image)
capture.mode=change_streams_update_full_with_pre_image

# Snapshot
snapshot.mode=initial

# Output format
output.schema.key.format=json
output.schema.value.format=json
```

### 5.2 capture.mode Options

| Mode | Description | MongoDB Version |
|---|---|---|
| `change_streams` | Default; update events contain only changed fields (delta) | 3.6+ |
| `change_streams_update_full` | Update events include full post-image via `updateLookup` | 3.6+ |
| `change_streams_with_transaction_metadata` | Includes transaction metadata | 4.0+ |
| `change_streams_update_full_with_pre_image` | Full pre-image + post-image (requires `changeStreamPreAndPostImages` enabled) | 6.0+ |

### 5.3 Change Event Structure

```json
{
  "schema": { ... },
  "payload": {
    "before": null,                    // Pre-image (null for inserts; populated with 6.0+ mode)
    "after": "{\"_id\":\"...\",\"status\":\"PLACED\"}",  // Post-image as JSON string
    "patch": null,                     // Deprecated; use after instead
    "filter": null,
    "updateDescription": {
      "removedFields": [],
      "updatedFields": "{\"status\":\"SHIPPED\"}",
      "truncatedArrays": []
    },
    "source": {
      "version": "3.x.x",
      "connector": "mongodb",
      "name": "dbserver1",
      "ts_ms": 1718000000000,
      "snapshot": "false",
      "db": "shop",
      "rs": "rs0",
      "collection": "orders",
      "ord": 1,
      "lsid": null,
      "txnNumber": null
    },
    "op": "u",                         // c=create, u=update, d=delete, r=read(snapshot)
    "ts_ms": 1718000001234,
    "transaction": null
  }
}
```

**Important limitation:** For `op: u` (update), the `before` field is `null` unless `capture.mode=change_streams_update_full_with_pre_image` with `changeStreamPreAndPostImages` enabled on the collection (MongoDB 6.0+). Earlier versions cannot provide atomic before-state for updates.

### 5.4 Snapshot Modes

| Mode | Behavior |
|---|---|
| `initial` | Snapshot all matching collections on first connect; switch to streaming after |
| `always` | Snapshot every time the connector starts (expensive; avoid in production) |
| `never` | Skip snapshot; start streaming from current oplog position (data loss risk if collections have existing data) |
| `when_needed` | Snapshot only if no valid offset exists or offset is invalid |
| `initial_only` | Snapshot only, no streaming (one-time backfill) |

### 5.5 Enabling Pre- and Post-Images (MongoDB 6.0+)

Before using `capture.mode=change_streams_update_full_with_pre_image`, enable pre/post-images on each source collection:

```javascript
// Enable changeStreamPreAndPostImages on a collection
db.runCommand({
  collMod: "orders",
  changeStreamPreAndPostImages: { enabled: true }
});

// Set expiry for the config.system.preimages collection (cluster-level)
db.adminCommand({
  setClusterParameter: {
    changeStreamOptions: {
      preAndPostImages: { expireAfterSeconds: 3600 }  // 1 hour; tune to your oplog window
    }
  }
});
```

Pre-images are stored in `config.system.preimages` and consume additional storage proportional to write throughput. Set `expireAfterSeconds` to at most the oplog window to avoid unbounded growth.

### 5.6 Resume Token and Offset Management

Debezium stores its offset (resume token equivalent) in the Kafka Connect offset topic. On restart, it resumes from the stored position. If the oplog has rolled past the stored position, the connector logs `InvalidResumeTokenException` and you must trigger a new snapshot.

**New in Debezium 3.x (2025):** `capture.start.op.time` property allows starting the connector at a specific oplog timestamp, useful for point-in-time recovery.

**Sources:** [Debezium MongoDB Connector Docs](https://debezium.io/documentation/reference/stable/connectors/mongodb.html), [Debezium 3.4.0 Release](https://debezium.io/blog/2025/12/16/debezium-3-4-final-released/), [Confluent Debezium MongoDB Config](https://docs.confluent.io/kafka-connectors/debezium-mongodb-source/current/mongodb_source_connector_config.html), [OLake CDC Guide](https://olake.io/blog/mongodb-cdc-using-debezium-and-kafka/)

---

## 6. Atlas Stream Processing for CDC

Atlas Stream Processing (ASP) provides a fully managed, MongoDB-native stream processing runtime. It uses familiar aggregation pipeline syntax extended with streaming-specific stages.

### 6.1 Connection Registry

Before creating stream processors, register source and sink connections via the Atlas UI (**Stream Processing → Connections**) or the Atlas Admin API. The `mongosh` `sp` object provides `sp.listConnections()` to inspect registered connections, but connection creation is done out-of-band through the UI or API — not via a `sp.addConnection()` call.

Once registered, reference connections by their label name in `$source` and `$merge`/`$emit` stages:

```javascript
// List registered connections (mongosh)
sp.listConnections();

// Reference a registered connection in a pipeline
{ "$source": { "connectionName": "cluster0-connection", "db": "shop", "coll": "orders" } }
```

### 6.2 CDC Pipeline Patterns

**Pattern A: Change stream → filter → write to another Atlas collection**
```javascript
sp.createStreamProcessor("orders-cdc", [
  {
    "$source": {
      "connectionName": "cluster0-connection",
      "db": "shop",
      "coll": "orders",
      "config": {
        "fullDocument": "updateLookup",
        "fullDocumentBeforeChange": "whenAvailable"
      }
    }
  },
  {
    "$match": {
      "operationType": { "$in": ["insert", "update", "replace"] }
    }
  },
  {
    "$project": {
      "_id": 1,
      "operationType": 1,
      "fullDocument": 1,
      "clusterTime": 1
    }
  },
  {
    "$merge": {
      "into": {
        "connectionName": "analytics-connection",
        "db": "analytics",
        "coll": "order_events"
      }
    }
  }
]);
```

**Pattern B: Change stream → windowed aggregation → Kafka**
```javascript
sp.createStreamProcessor("order-rollup", [
  {
    "$source": {
      "connectionName": "cluster0",
      "db": "shop",
      "coll": "orders",
      "config": { "fullDocument": "updateLookup" }
    }
  },
  {
    "$tumblingWindow": {
      "interval": { "size": 60, "unit": "second" },
      "pipeline": [
        { "$group": {
          "_id": "$fullDocument.status",
          "count": { "$sum": 1 },
          "totalRevenue": { "$sum": "$fullDocument.total" }
        }}
      ]
    }
  },
  {
    "$emit": {
      "connectionName": "kafka-connection",
      "topic": "order-rollup-1min"
    }
  }
]);
```

### 6.3 Dead Letter Queue (DLQ) Configuration

```javascript
const dlqConfig = {
  dlq: {
    connectionName: "cluster0-connection",
    db: "asp_errors",
    coll: "orders_cdc_dlq"
  }
};

sp.createStreamProcessor("orders-cdc-safe", pipeline, dlqConfig);
```

**DLQ document structure:**
```json
{
  "_id": ObjectId("..."),
  "doc": {
    "_id": { "_data": "resume-token-hex" },
    "operationType": "update",
    "fullDocument": { ... },
    "clusterTime": Timestamp(...)
  },
  "errInfo": {
    "reason": "Document failed $validate stage: field 'total' must be positive"
  }
}
```

**DLQ routing triggers:**
- Serialization failure (JSON → BSON conversion error)
- `$validate` stage violations
- Late-arriving data past `allowedLateness` at window stages
- Processing errors (divide-by-zero, type mismatch)

**Monitoring and replay:**
```javascript
// Set an Atlas Alert on DLQ collection document count
// Index errInfo for root cause analysis
db.orders_cdc_dlq.createIndex({ "errInfo.reason": 1 });

// Re-introduce corrected documents via a Database Trigger on the DLQ
```

**Sources:** [ASP DLQ Medium](https://kennygorman.medium.com/mongodb-atlas-stream-processing-dead-letter-queues-3b07fb5dfe5c), [ASP Docs](https://www.mongodb.com/docs/atlas/atlas-stream-processing/), [ASP Aggregation Stages](https://www.mongodb.com/docs/atlas/atlas-stream-processing/stream-aggregation-stages/)

---

## 7. Exactly-Once Semantics

True exactly-once delivery across MongoDB → Kafka → consumer requires a combination of producer idempotence, consumer idempotence, and durable offset management.

### 7.1 Delivery Guarantees by Transport

| Transport | Native Guarantee | How to Achieve EOS |
|---|---|---|
| Change Streams | At-least-once | Store resume token after confirmed delivery; idempotent consumer |
| MongoDB Kafka Connector | At-least-once | `enable.idempotence=true` on producer + idempotent consumer |
| Debezium | At-least-once | Kafka Streams EOS (`processing.guarantee=exactly_once_v2`) |
| Atlas Stream Processing | At-least-once with DLQ | DLQ + idempotent sink operations |

### 7.2 Producer-Side Idempotence (Kafka)

```properties
# Kafka producer settings for idempotent delivery
enable.idempotence=true
acks=all
retries=2147483647
max.in.flight.requests.per.connection=5
```

For transactional writes across multiple topics:
```properties
transactional.id=mongodb-cdc-producer-1
```

### 7.3 Idempotent Consumer Pattern

The safest pattern: deduplicate on a processed-event ledger in the consumer's database.

```javascript
// Consumer deduplication table (MongoDB)
// Schema: { eventId: string, processedAt: Date }
db.processed_events.createIndex({ eventId: 1 }, { unique: true });
db.processed_events.createIndex(
  { processedAt: 1 },
  { expireAfterSeconds: 604800 }  // 7-day TTL on dedup records
);

// Consumer logic (Node.js / kafkajs style)
async function processEvent(event) {
  const session = client.startSession();
  await session.withTransaction(async () => {
    // Try to insert the processed-event marker (will throw DuplicateKeyError if already seen)
    await db.processed_events.insertOne(
      { eventId: event.id, processedAt: new Date() },
      { session }
    );
    // If we get here, event is new — apply business logic
    await applyBusinessLogic(event, session);
  });
  // Commit Kafka offset only after the MongoDB transaction succeeds
  // kafkajs: await consumer.commitOffsets([{ topic, partition, offset: (event.offset + 1).toString() }])
  // node-rdkafka: consumer.commit(event)
}
```

**Key rule:** Save the resume token (or commit the Kafka offset) only after confirming delivery to the destination. If you save early and crash before delivery, you lose events. If you save late, you get at-most-one duplicate — which the dedup table handles.

### 7.4 Resume Token Durability

```javascript
// Persist resume token to MongoDB (durable, crash-safe)
async function persistResumeToken(token) {
  await db.cdc_offsets.updateOne(
    { _id: 'orders-stream' },
    { $set: { resumeToken: token, updatedAt: new Date() } },
    { upsert: true }
  );
}

// On startup, load token and resume
const offset = await db.cdc_offsets.findOne({ _id: 'orders-stream' });
const stream = offset
  ? collection.watch([], { resumeAfter: offset.resumeToken })
  : collection.watch([]);
```

**Sources:** [Kafka Exactly-Once Semantics Conduktor](https://www.conduktor.io/glossary/exactly-once-semantics-in-kafka), [Idempotent Consumer Medium](https://medium.com/@zdb.dashti/exactly-once-semantics-using-the-idempotent-consumer-pattern-927b2595f231), [AutoMQ Kafka EOS](https://www.automq.com/blog/kafka-exactly-once-semantics-implementation-idempotence-and-transactional-messages)

---

## 8. Schema Registry and Evolution

### 8.1 Confluent Schema Registry with MongoDB CDC

Confluent Schema Registry stores Avro, JSON Schema, or Protobuf schemas and enforces compatibility on publish. Configure the MongoDB Kafka Source connector to serialize with Avro:

```properties
# Source connector: serialize change events as Avro via Confluent Schema Registry
# Use AvroConverter (Kafka Connect converter), NOT KafkaAvroSerializer (producer-only)
key.converter=io.confluent.connect.avro.AvroConverter
key.converter.schema.registry.url=https://schema-registry:8081
value.converter=io.confluent.connect.avro.AvroConverter
value.converter.schema.registry.url=https://schema-registry:8081
# Auto-register schemas on first publish
value.converter.auto.register.schemas=true
```

**Compatibility modes:**

| Mode | What the new schema can do | Guarantee |
|---|---|---|
| `BACKWARD` (default) | Add optional fields; remove previously required fields | New consumers can read data written with the old schema |
| `FORWARD` | Add required fields; remove optional fields | Old consumers can read data written with the new schema |
| `FULL` | Add/remove optional fields only | Both old and new consumers can read both schema versions |
| `NONE` | Any change | No compatibility enforcement — use only in development |

### 8.2 Handling MongoDB's Flexible Schema in CDC

MongoDB's schemaless design means new fields can appear in documents at any time. Strategies:

**1. JSON Schema (recommended for MongoDB CDC):** Use JSON Schema serialization instead of Avro. New fields are silently accepted; Schema Registry tracks them for documentation.

**2. `$unset` operations:** When MongoDB removes a field with `$unset`, the CDC update event's `updateDescription.removedFields` will list the field name. Downstream consumers must treat missing fields as `null` rather than errors.

**3. Schema evolution strategies by field type:**

| Change Type | Safe Approach |
|---|---|
| New optional field added | `BACKWARD` compatible — add with default value |
| Field renamed | Treat as add new + deprecate old (never rename in Avro) |
| Type change (e.g., string → int) | Add new field, deprecate old, migrate gradually |
| Field removed | Mark deprecated, remove after all consumers updated |
| Polymorphic field | Use `string` or Avro `union` type |

### 8.3 Debezium ExtractNewDocumentState SMT

Debezium's change event wraps documents in an envelope. Use the `ExtractNewDocumentState` (EDS) SMT to flatten the envelope and produce a simple key/value record suitable for most sink connectors:

```properties
transforms=unwrap
transforms.unwrap.type=io.debezium.connector.mongodb.transforms.ExtractNewDocumentState
transforms.unwrap.drop.tombstones=false
transforms.unwrap.delete.handling.mode=rewrite
transforms.unwrap.add.fields=op,source.ts_ms
```

**Sources:** [Confluent Schema Registry Docs](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html), [Confluent MongoDB Atlas Connectors](https://www.confluent.io/blog/mongodb-atlas-connectors-production-best-practices/), [Debezium New Doc State Extraction](https://debezium.io/documentation/reference/stable/transformations/mongodb-event-flattening.html)

---

## 9. Pipeline Monitoring

### 9.1 Key Metrics to Monitor

| Metric | Source | Alert Threshold |
|---|---|---|
| Consumer group lag (`records-lag-max`) | Kafka JMX / Prometheus | >10K records sustained |
| Consumer group lag (`records-lag-avg`) | Kafka JMX / Prometheus | Growing trend >5 min |
| Change stream cursor age | MongoDB serverStatus | Approaching oplog window |
| Connector task status | Kafka Connect REST API | Any `FAILED` state |
| Throughput (records/sec) | Kafka JMX | Drop >20% from baseline |
| DLQ collection document count | MongoDB Atlas Alerts | Any documents present |
| ASP processor state | Atlas UI / API | `STOPPED` or `FAILED` |

### 9.2 Lag Monitoring Patterns

```bash
# Check consumer group lag via Kafka CLI
kafka-consumer-groups.sh \
  --bootstrap-server broker:9092 \
  --describe \
  --group mongodb-cdc-consumer

# Prometheus JMX metrics (add to Kafka JMX scrape config)
# kafka_consumer_fetch_manager_records_lag_max
# kafka_consumer_fetch_manager_records_lag_avg
```

**Lag interpretation:**
- **Linear growth**: Sustained throughput mismatch → scale out consumers or reduce batch size
- **Spike then recovery**: Transient burst → increase `max.poll.records` or consumer memory
- **Exponential growth**: Cascading failure → check downstream system health, circuit break

### 9.3 Backpressure Handling

When MongoDB emits changes faster than consumers can process:

1. **Kafka as buffer**: The Kafka topic naturally absorbs bursts. Tune `fetch.min.bytes`, `fetch.max.wait.ms`, and `max.poll.records` on consumers.
2. **Bounded queues**: In direct change stream consumers, use a bounded `BlockingQueue` with a backpressure signal back to the stream cursor.
3. **Pause/resume**: Kafka consumer `pause(partitions)` + `resume(partitions)` lets slow downstream systems signal backpressure.
4. **ASP**: Atlas Stream Processing handles backpressure internally; route overflow to DLQ.

### 9.4 Dead Letter Queue Operations

```javascript
// Query DLQ for error patterns
db.orders_cdc_dlq.aggregate([
  { $group: { _id: "$errInfo.reason", count: { $sum: 1 } } },
  { $sort: { count: -1 } }
]);

// Atlas Alert: notify when DLQ grows
// Threshold: document count > 0
// Action: PagerDuty / Slack webhook

// Replay: re-introduce corrected documents to the stream
// Use a Database Trigger on DLQ collection: when a document is updated
// with { "retryAt": new Date() }, re-publish to the source pipeline
```

**Sources:** [Streamkap Backpressure Guide](https://streamkap.com/resources-and-guides/backpressure-stream-processing), [CDC Advanced Notes MongoDB Kafka](https://medium.com/@sukanyam.014/change-data-capture-cdc-advanced-notes-with-mongodb-and-kafka-bb1645831ee0), [Debezium Striim Replication Guide](https://www.striim.com/blog/data-replication-for-mongodb-guide-to-real-time-cdc/)

---

## 10. Sharded Cluster CDC Considerations

Change streams on sharded clusters behave differently from replica sets and require explicit attention to avoid silent data loss or ordering violations.

### 10.1 Opening Change Streams on Sharded Clusters

Open change streams at the `mongos` level, not directly on shards. `mongos` multiplexes streams from all shards and merges events by `clusterTime`:

```javascript
// Correct: open on mongos client — events from all shards are merged
const stream = client.db('shop').collection('orders').watch(pipeline, options);

// Wrong: opening directly on a shard misses events from other shards
```

**Ordering caveat:** `mongos` sorts merged shard events by `clusterTime`, but `clusterTime` granularity is per-second. Two events on different shards within the same second may arrive in non-deterministic order. For strict cross-shard ordering, use `lsid` + `txnNumber` (transactions) or add an application-level sequence field.

### 10.2 Change Stream Behavior on Sharded Collections

| Scenario | Behavior |
|---|---|
| Insert on any shard | Event emitted from that shard's oplog; `mongos` forwards |
| Update touching shard key | Two events: `delete` on old shard + `insert` on new shard |
| Chunk migration | No CDC events for migrated orphan documents (MongoDB 5.3+) |
| `$lookup` in stream pipeline | Expensive on sharded clusters; avoid or project before lookup |

### 10.3 Resume Tokens on Sharded Clusters

Resume tokens on sharded clusters encode a `clusterTime` plus per-shard position. They are valid across `mongos` restarts but **not** portable between different cluster topologies (e.g., after a resharding operation). After resharding, resume from `startAtOperationTime` rather than a stored token.

---

## 11. Anti-Patterns

### 11.1 Not Persisting the Resume Token

**Problem:** Application opens a change stream without storing the resume token. On restart (crash, deploy, scale-down), it starts a new stream and misses all changes that occurred during downtime.

**Fix:** Persist the resume token to a durable store (MongoDB document, Redis, Kafka Connect offset topic) after every confirmed delivery. Use `startAfter` on resume.

```javascript
// WRONG: Stateless change stream — loses position on restart
const stream = collection.watch([]);
for await (const event of stream) {
  await processEvent(event);
  // Resume token never saved
}

// RIGHT: Persist token after each confirmed delivery
for await (const event of stream) {
  await processEventAndPersistToken(event, event._id);
}
```

### 11.2 Tailing the Oplog Directly

**Problem:** Accessing `local.oplog.rs` directly is unsupported and fragile. Oplog format is internal and changes across MongoDB versions. It breaks on replica set elections and primary failovers.

**Fix:** Always use the Change Streams API (`collection.watch()`). Change streams are the supported, stable abstraction over the oplog.

### 11.3 Insufficient Oplog Window

**Problem:** The oplog is a capped collection. Under high write load, it can roll within hours. If a CDC consumer is down for longer than the oplog window, the resume token becomes invalid and a full re-snapshot is required.

**Fix:** Configure oplog retention:
```javascript
// Set minimum oplog retention (MongoDB 4.4+)
db.adminCommand({
  replSetResizeOplog: 1,
  size: 10240,           // 10 GB minimum
  minRetentionHours: 72  // 72-hour minimum window
});
```

Recommended production values: ≥10 GB, ≥72 hours. For CDC pipelines specifically, 24 hours at minimum, 7+ days preferred.

### 11.4 Missing TTL on Outbox Collection

**Problem:** Outbox collection grows unboundedly because Debezium only reads inserts — it never deletes documents from the outbox. Without a TTL index, the collection fills disk.

**Fix:** Add TTL index on `createdAt` as shown in Section 2.3. TTL cleanup is independent of correctness.

### 11.5 `updateLookup` + Rapid Deletions

**Problem:** Using `fullDocument: "updateLookup"` on high-delete collections causes `Resume Token Not Found` errors. When an update event is captured but the document is deleted before the lookup executes, `fullDocument` is null. With a `$match` filter that requires `fullDocument`, the change stream cursor faults.

**Fix:** Upgrade to MongoDB 6.0+ and use pre/post-images:
```javascript
// Enable pre/post-images on the collection
db.runCommand({ collMod: 'orders', changeStreamPreAndPostImages: { enabled: true } });

// Then use whenAvailable instead of updateLookup
const stream = collection.watch([], {
  fullDocument: 'whenAvailable',
  fullDocumentBeforeChange: 'whenAvailable'
});
```

### 11.6 CDC on Time-Series Collections

**Problem:** MongoDB time-series collections do not support change streams. Attempting to open a change stream on a time-series collection throws an error.

**Fix:** If you need CDC from time-series data, route writes through a regular collection first (e.g., via an Atlas Trigger or application layer) and apply the time-series collection as a materialized copy.

### 11.7 No Idempotency in Consumers

**Problem:** At-least-once delivery from change streams means duplicate events during restarts. Without idempotent consumer logic, duplicate processing causes double-counting, duplicate records, or inconsistent state.

**Fix:** Implement a deduplication table keyed on event `_id` or a composite key (see Section 7.3). Always make downstream writes idempotent (upsert instead of insert, atomic `updateOne` with `$set` instead of `$inc`).

### 11.8 Global Change Streams Without Ordering Guarantees

**Problem:** Database-level or deployment-level change streams do not guarantee ordering across collections. If your consumer assumes global ordering (e.g., updating a denormalized cache), race conditions occur.

**Fix:** Use collection-level change streams per collection. If cross-collection ordering is required, use logical timestamps (`clusterTime` field) and process events with a per-entity ordering guarantee via Kafka topic partitioning on entity ID.

**Sources:** [OLake MongoDB Sync Strategies](https://olake.io/blog/mongodb-synchronization-strategies/), [Alex Bevilacqua Change Stream Resume Performance](https://alexbevi.com/blog/2022/03/02/performance-analysis-of-resuming-a-mongodb-change-stream/), [MongoDB Change Stream Manual](https://www.mongodb.com/docs/manual/changestreams/), [Oplog Retention](https://oneuptime.com/blog/post/2026-03-31-mongodb-set-oplog-retention-period/view)

---

## References and Sources Cited

1. [MongoDB Change Streams Manual](https://www.mongodb.com/docs/manual/changestreams/) — official change stream API, resume tokens, pre/post-images
2. [Atlas Stream Processing $source Stage](https://www.mongodb.com/docs/atlas/atlas-stream-processing/sp-agg-source/) — ASP $source syntax and options
3. [Atlas Stream Processing Docs](https://www.mongodb.com/docs/atlas/atlas-stream-processing/) — full ASP reference
4. [MongoDB Kafka Connector Change Streams](https://www.mongodb.com/docs/kafka-connector/current/source-connector/fundamentals/change-streams/) — source connector offset management
5. [Invalid Resume Token Recovery](https://www.mongodb.com/docs/kafka-connector/current/troubleshooting/recover-from-invalid-resume-token/) — connector recovery guide
6. [Debezium MongoDB Connector Docs](https://debezium.io/documentation/reference/stable/connectors/mongodb.html) — capture modes, event structure, snapshot modes
7. [Debezium MongoDB Outbox Event Router](https://debezium.io/documentation/reference/stable/transformations/mongodb-outbox-event-router.html) — SMT configuration
8. [Debezium New Document State Extraction](https://debezium.io/documentation/reference/stable/transformations/mongodb-event-flattening.html) — event flattening SMT
9. [Debezium 3.4.0 Release Notes](https://debezium.io/blog/2025/12/16/debezium-3-4-final-released/) — 2025 Debezium updates
10. [Confluent Schema Registry Schema Evolution](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html) — compatibility modes
11. [Confluent MongoDB Atlas Connectors Production Best Practices](https://www.confluent.io/blog/mongodb-atlas-connectors-production-best-practices/) — networking, idempotency, schema
12. [MongoDB Event Store Design (event-driven.io)](https://event-driven.io/en/mongodb_event_store/) — event sourcing collection design
13. [ASP Dead Letter Queues (Medium)](https://kennygorman.medium.com/mongodb-atlas-stream-processing-dead-letter-queues-3b07fb5dfe5c) — DLQ configuration and monitoring
14. [ASP Iceberg Private Preview](https://medium.com/towards-data-engineering/atlas-stream-processing-iceberg-private-preview-bfc163e09522) — 2025 Iceberg sink
15. [MongoDB to Snowflake CDC (Streamkap)](https://streamkap.com/resources-and-guides/mongodb-to-snowflake-cdc) — Snowflake CDC architecture
16. [Streamkap Backpressure Guide](https://streamkap.com/resources-and-guides/backpressure-stream-processing) — backpressure patterns
17. [Streamkap MongoDB CDC Complete Guide](https://streamkap.com/resources-and-guides/mongodb-change-data-capture) — CDC overview
18. [Alex Bevilacqua Change Stream Resume Performance](https://alexbevi.com/blog/2022/03/02/performance-analysis-of-resuming-a-mongodb-change-stream/) — oplog resume performance analysis
19. [Outbox Pattern C# (vkontech)](https://vkontech.com/the-outbox-pattern-with-mongo-kafka-and-debezium-in-c/) — full outbox implementation walkthrough
20. [Kafka Idempotent Consumer & Transactional Outbox (Lydtech)](https://www.lydtechconsulting.com/blog/kafka-idempotent-consumer-transactional-outbox) — idempotency implementation
21. [Kafka Exactly-Once Semantics (Conduktor)](https://www.conduktor.io/glossary/exactly-once-semantics-in-kafka) — Kafka EOS reference
22. [OLake MongoDB CDC with Debezium](https://olake.io/blog/mongodb-cdc-using-debezium-and-kafka/) — Debezium connector walkthrough
23. [Estuary MongoDB to Kafka Methods](https://estuary.dev/blog/mongodb-to-kafka/) — three-method comparison with latency data
24. [MongoDB Dataflow BigQuery CDC Template](https://github.com/GoogleCloudPlatform/DataflowTemplates/blob/main/v2/mongodb-to-googlecloud/README_MongoDB_to_BigQuery_CDC.md) — Dataflow CDC template
25. [Databricks Schema Evolution](https://docs.databricks.com/aws/en/data-engineering/schema-evolution) — Delta Lake autoMerge
26. [MongoDB Time-Series Collection Limitations](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-limitations/) — change stream exclusion
27. [Oplog Retention Configuration](https://oneuptime.com/blog/post/2026-03-31-mongodb-set-oplog-retention-period/view) — oplog window sizing

## See Also

- [[mongodb-change-streams]] — deep dive on change stream API, filtering, and watch levels
- [[mongodb-kafka-connector]] — MongoDB Kafka Connector source and sink reference
- [[mongodb-spark-connector]] — Spark Structured Streaming with MongoDB
- [[mongodb-atlas-stream-processing]] — Atlas Stream Processing full reference
- [[mongodb-transactions]] — MongoDB multi-document transactions for outbox atomicity
- [[mongodb-schema-design]] — document schema patterns relevant to event store design
