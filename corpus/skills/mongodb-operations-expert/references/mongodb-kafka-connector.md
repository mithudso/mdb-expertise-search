<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-kafka-connector` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-kafka-connector
description: >
  Expert reference for the MongoDB Connector for Apache Kafka — covers both the source connector
  (MongoDB change streams → Kafka topics) and the sink connector (Kafka topics → MongoDB).
  Use this skill whenever someone asks about: configuring the MongoDB Kafka connector, change stream
  source connectors, Kafka sink to MongoDB, write model strategies (ReplaceOneBusinessKeyStrategy,
  InsertOneDefaultStrategy, UpdateOneTimestampsStrategy), dead letter queue (DLQ) setup,
  resume token errors (ChangeStreamHistoryLost, InvalidResumeToken), CDC (change data capture)
  pipelines, schema registry (Avro, JSON Schema, Protobuf) with MongoDB, connector performance tuning
  (batch size, poll interval, bulk write ordering), deploying on Confluent Cloud or Amazon MSK Connect,
  SCRAM/x509/AWS IAM auth to Atlas from Kafka, or comparing Kafka Connector vs Atlas Stream Processing.
  Also use when debugging connector lag, duplicate events, connector restarts, schema evolution failures,
  or designing MongoDB→Elasticsearch/S3/Snowflake pipelines via Kafka.
  TRIGGER: MongoSourceConnector or MongoSinkConnector configuration; write model strategy selection;
  DLQ (dead letter queue) for sink connector; ChangeStreamHistoryLost or InvalidResumeToken errors;
  heartbeat.interval.ms; startup.mode=copy_existing; bulk.write.ordered; Debezium CDC handler;
  schema registry Avro with MongoDB; MSK Connect MongoDB plugin; Confluent Cloud MongoDB connector;
  outbox pattern with Kafka; Atlas Stream Processing vs Kafka Connector decision.
  SKIP: Atlas Change Streams without Kafka (use mongodb-change-streams); Atlas Stream Processing
  without Kafka (use mongodb-atlas-stream-processing); MongoDB replication internals (use
  mongodb-replication); general Kafka broker or Kafka Streams setup without MongoDB.
category: mongodb
tags: [mongodb, kafka, kafka-connect, CDC, change-streams, streaming, ETL, integration, Confluent, MSK]
version: 1.2.0
updated: "2026-05-29"
audience: Data engineers, solution architects, and developers building Kafka pipelines that read from or write to MongoDB
whenNotToUse:
  - Atlas Change Streams without Kafka — use mongodb-change-streams
  - Atlas Stream Processing pipelines without Kafka — use mongodb-atlas-stream-processing
  - MongoDB replication internals (oplog, elections) — use mongodb-replication
  - General Kafka broker or Kafka Streams setup not involving MongoDB
related_skills:
  - mongodb-change-streams
  - mongodb-atlas-stream-processing
  - mongodb-replication
  - mongodb-data-lifecycle
  - mongodb-atlas-expert
  - mongodb-aggregation-pipeline
---

# MongoDB Connector for Apache Kafka

## Scope

This reference covers the MongoDB Kafka Connector (official MongoDB connector, `com.mongodb.kafka.connect`) from architecture through production operations. After reading it you will be able to:

- Configure source and sink connectors with all critical properties
- Choose and configure write model strategies for idempotent sinks
- Set up DLQ error handling and schema registry integration
- Tune for throughput and recover from common failures
- Decide between Kafka Connector and Atlas Stream Processing

**Intended audience:** Data engineers, platform engineers, and MongoDB solution architects designing CDC pipelines, event-driven data movement, or operational data synchronization across Kafka and MongoDB.

---

## 1. Overview

The MongoDB Connector for Apache Kafka is a **Confluent-verified** Kafka Connect plugin maintained by MongoDB Inc. It provides two connectors:

- **Source Connector** — Reads from a MongoDB change stream and publishes change event documents to one or more Kafka topics.
- **Sink Connector** — Reads records from Kafka topics and writes them to MongoDB collections.

**Key facts:**
- GitHub: `https://github.com/mongodb/mongo-kafka`
- Confluent Hub: `mongodb/kafka-connect-mongodb`
- Current stable: v1.14 / v1.16 (check [What's New](https://www.mongodb.com/docs/kafka-connector/current/whats-new/) for latest)
- License: Apache 2.0
- Minimum MongoDB: 4.0 (change streams require replica set or sharded cluster)
- Java driver: bundled; uses `org.mongodb.mongodb-driver-sync`

**Source:** [MongoDB Kafka Connector Docs](https://www.mongodb.com/docs/kafka-connector/current/), [GitHub](https://github.com/mongodb/mongo-kafka), [Confluent Hub](https://www.confluent.io/hub/mongodb/kafka-connect-mongodb)

---

## 2. Architecture

### High-Level Flow

```
MongoDB Replica Set / Sharded Cluster
  ↓  (change stream — oplog-backed)
Source Connector (Kafka Connect worker)
  ↓  (change event documents as JSON/BSON/Avro)
Kafka Topics
  ↓  (records consumed by sink)
Sink Connector (Kafka Connect worker)
  ↓  (bulk writes)
MongoDB Collection(s)
```

### Source Connector Architecture

The source connector opens **one change stream** per configured namespace (collection, database, or deployment-wide). It:

1. Opens a MongoDB change stream cursor against the target namespace
2. Converts each change event document into a Kafka `SourceRecord`
3. Publishes to the configured topic
4. Stores the **resume token** (change stream position) as its Kafka Connect offset

The resume token is persisted to the Kafka Connect offset storage topic (not to MongoDB). On restart, the connector uses the stored resume token to resume the change stream without missing events. If no offset exists, it starts a new change stream from the current position (or from a configured timestamp/copy_existing mode).

**Change streams require a replica set or sharded cluster** — standalone `mongod` cannot produce change streams.

**Source:** [Source Connector Docs](https://www.mongodb.com/docs/kafka-connector/current/source-connector/), [Change Streams Fundamentals](https://www.mongodb.com/docs/kafka-connector/current/source-connector/fundamentals/change-streams/)

### Sink Connector Architecture

The sink connector:

1. Subscribes to one or more Kafka topics
2. Polls batches of records
3. Applies **post-processors** (field projection, ID extraction, field renaming)
4. Executes **write model strategies** to construct MongoDB write operations
5. Issues **bulk write** operations to the target collection

The sink can be configured to handle CDC events (Debezium-format or MongoDB native change stream format) via CDC handlers, allowing it to replicate full insert/update/replace/delete operations.

**Source:** [Sink Connector Docs](https://www.mongodb.com/docs/kafka-connector/current/sink-connector/)

---

## 3. Source Connector Configuration

### Essential Properties

```properties
# Connector class
connector.class=com.mongodb.kafka.connect.MongoSourceConnector

# MongoDB connection
connection.uri=mongodb+srv://user:pass@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority

# Topic to publish to (default: <database>.<collection>)
topic.prefix=my-prefix        # optional — produces <prefix>.<database>.<collection>
topic.separator=.             # separator between parts; default "."

# Namespace to watch
database=myDatabase           # watch a single database (omit for deployment-wide)
collection=myCollection       # watch a single collection (omit for db-wide watch)
```

### Polling and Batch Settings

| Property | Default | Description |
|---|---|---|
| `poll.await.time.ms` | 5000 | Max ms the server waits for new data before returning empty batch |
| `poll.max.batch.size` | 1000 | Max change event documents per poll batch |
| `batch.size` | 0 | Change stream cursor batch size (0 = driver default) |

### Change Stream Options

| Property | Default | Values / Description |
|---|---|---|
| `change.stream.full.document` | `""` | `updateLookup` — fetch full post-image on update; `whenAvailable` / `required` — use change stream pre/post image (MongoDB 6.0+) |
| `change.stream.full.document.before.change` | `""` | `whenAvailable` / `required` — include pre-image (requires pre-image collection on MongoDB 6.0+) |
| `publish.full.document.only` | false | Publish only `fullDocument` field, not the full change event envelope |
| `publish.full.document.only.tombstone.on.delete` | false | Emit tombstone (null-value) record when document is deleted |
| `pipeline` | `"[]"` | JSON array of aggregation pipeline stages to filter/transform change events |
| `change.stream.show.expanded.events` | false | Include DDL events (createIndexes, dropIndexes, etc.) |
| `change.stream.document.key.as.key` | true | Use `documentKey` as Kafka record key |
| `collation` | `""` | JSON collation document for change stream ordering |

### Heartbeat Settings

Heartbeats prevent **invalid resume token** errors for low-traffic namespaces where the oplog rotates past the last resume token while the connector is idle.

| Property | Default | Description |
|---|---|---|
| `heartbeat.interval.ms` | 0 | Milliseconds between heartbeat messages. 0 = disabled. Recommended: 30000–60000 for low-volume namespaces |
| `heartbeat.topic.name` | `__mongodb_heartbeats` | Topic for heartbeat messages (requires positive `heartbeat.interval.ms`) |

### Startup Modes

| Mode | Description |
|---|---|
| `latest` (default) | Start from the current position; skip historical data |
| `timestamp` | Start from a specific operation time (epoch seconds, ISO-8601, or BSON Timestamp) |
| `copy_existing` | Snapshot all existing documents first, then watch for new changes |

```properties
# Copy existing data before streaming new changes
startup.mode=copy_existing
startup.mode.copy.existing.namespace.regex=myDatabase\..*   # regex filter
startup.mode.copy.existing.pipeline=[{"$match": {"status": "active"}}]
startup.mode.copy.existing.max.threads=4                    # default: CPU count
startup.mode.copy.existing.queue.size=16000
startup.mode.copy.existing.allow.disk.use=true

# Start from a specific timestamp
startup.mode=timestamp
startup.mode.timestamp.start.at.operation.time=2024-01-01T00:00:00Z
```

### Offset / Resume Token Control

```properties
# Use a custom partition name to reset the offset (force new change stream)
offset.partition.name=my-connector-v2
```

**When to use:** Change the partition name after an invalid resume token to force a fresh start without re-creating the connector.

### Error Handling (Source)

| Property | Default | Description |
|---|---|---|
| `mongo.errors.tolerance` | `"none"` | `"none"` — stop on error; `"all"` — continue |
| `mongo.errors.log.enable` | false | Log all errors |
| `mongo.errors.deadletterqueue.topic.name` | `""` | DLQ topic for invalid messages (requires `errors.tolerance=all`) |

### Full Source Connector Example

```properties
connector.class=com.mongodb.kafka.connect.MongoSourceConnector
connection.uri=mongodb+srv://kafkauser:secret@cluster0.abc.mongodb.net/?authSource=admin
database=ecommerce
collection=orders
topic.prefix=mongo
poll.max.batch.size=1000
poll.await.time.ms=5000
change.stream.full.document=updateLookup
publish.full.document.only=true
publish.full.document.only.tombstone.on.delete=true
heartbeat.interval.ms=30000
pipeline=[{"$match": {"operationType": {"$in": ["insert","update","replace","delete"]}}}]
key.converter=org.apache.kafka.connect.storage.StringConverter
value.converter=org.apache.kafka.connect.json.JsonConverter
value.converter.schemas.enable=false
```

**Source:** [All Source Properties](https://www.mongodb.com/docs/kafka-connector/current/source-connector/configuration-properties/all-properties/), [Change Stream Properties](https://www.mongodb.com/docs/kafka-connector/current/source-connector/configuration-properties/change-stream/)

---

## 4. Sink Connector Configuration

### Essential Properties

```properties
connector.class=com.mongodb.kafka.connect.MongoSinkConnector
connection.uri=mongodb+srv://user:pass@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
database=myDatabase
collection=myCollection
topics=my-kafka-topic          # or use topics.regex for multi-topic matching
```

### Write Model Strategies

A write model strategy defines how each Kafka record is mapped to a MongoDB write operation. The `writemodel.strategy` property takes a fully-qualified Java class name — short names in the table below are aliases for readability.

**Full class path prefix:** `com.mongodb.kafka.connect.sink.writemodel.strategy.`

| Short Name (append to prefix above) | Operation | Use Case |
|---|---|---|
| `InsertOneDefaultStrategy` | `insertOne` | Append-only; fails on duplicate `_id` — avoid in replay-able pipelines |
| `ReplaceOneDefaultStrategy` **(default)** | `replaceOne` upsert on `_id` | General-purpose upsert when Kafka key = MongoDB `_id` |
| `ReplaceOneBusinessKeyStrategy` | `replaceOne` upsert on custom fields | **Recommended for idempotency** — replace by composite business key |
| `UpdateOneTimestampsStrategy` | `updateOne` with `$set` + `_insertedTS`/`_modifiedTS` | Audit trail tracking create/modify times |
| `UpdateOneBusinessKeyTimestampStrategy` | `updateOne` by business key + timestamps | Audit trail with custom business key |
| `DeleteOneDefaultStrategy` | `deleteOne` by `_id` | Handle tombstone (null-value) records |
| `DeleteOneBusinessKeyStrategy` | `deleteOne` by custom fields | Handle delete events keyed by business field(s) |

**Configuration example** (replace by business key — recommended for production):

```properties
# Extract business key from record value fields
document.id.strategy=com.mongodb.kafka.connect.sink.processor.id.strategy.PartialValueStrategy
document.id.strategy.partial.value.projection.list=orderId,customerId
document.id.strategy.partial.value.projection.type=AllowList
writemodel.strategy=com.mongodb.kafka.connect.sink.writemodel.strategy.ReplaceOneBusinessKeyStrategy

# Parallelism — set equal to or less than topic partition count
tasks.max=4
```

**Idempotency note:** Use `ReplaceOneBusinessKeyStrategy` with a unique index on the business key fields to handle Kafka's at-least-once delivery safely. Replayed messages become no-op upserts rather than duplicates. Create the index before starting the connector:

```javascript
db.orders.createIndex({ orderId: 1, customerId: 1 }, { unique: true })
```

### Bulk Write Ordering

| Property | Default | Description |
|---|---|---|
| `bulk.write.ordered` | true | Ordered = stops on first error; unordered = continues, better throughput |

Set `bulk.write.ordered=false` with `errors.tolerance=all` and DLQ to maximize throughput while routing failures to the DLQ rather than stopping the connector.

### CDC Handler (Debezium / Native)

The sink connector can consume CDC event payloads and replicate operations into MongoDB:

```properties
# For Debezium CDC events
change.data.capture.handler=com.mongodb.kafka.connect.sink.cdc.debezium.rdbms.postgres.PostgresCdcHandler

# For MongoDB source connector native change events
change.data.capture.handler=com.mongodb.kafka.connect.sink.cdc.mongodb.ChangeStreamHandler
```

Supported Debezium CDC handlers: MySQL, PostgreSQL, MongoDB, SQL Server.

**Source:** [Write Model Strategies](https://www.mongodb.com/docs/kafka-connector/current/sink-connector/fundamentals/write-strategies/), [CDC Handlers](https://www.mongodb.com/docs/kafka-connector/current/sink-connector/fundamentals/change-data-capture/)

### Full Sink Connector Example

```properties
connector.class=com.mongodb.kafka.connect.MongoSinkConnector
connection.uri=mongodb+srv://kafkawriter:secret@cluster0.abc.mongodb.net/?authSource=admin
database=analytics
collection=events
topics=mongo.ecommerce.orders
document.id.strategy=com.mongodb.kafka.connect.sink.processor.id.strategy.PartialValueStrategy
document.id.strategy.partial.value.projection.list=orderId
document.id.strategy.partial.value.projection.type=AllowList
writemodel.strategy=com.mongodb.kafka.connect.sink.writemodel.strategy.ReplaceOneBusinessKeyStrategy
bulk.write.ordered=false
errors.tolerance=all
errors.deadletterqueue.topic.name=analytics-events-dlq
errors.deadletterqueue.context.headers.enable=true
errors.log.enable=true
errors.log.include.messages=true
key.converter=org.apache.kafka.connect.storage.StringConverter
value.converter=org.apache.kafka.connect.json.JsonConverter
value.converter.schemas.enable=false
```

---

## 5. Error Handling and Dead Letter Queue

### Error Tolerance Levels

| Mode | Config | Behavior |
|---|---|---|
| **Stop on all errors** (default) | `errors.tolerance=none` | Connector halts; requires manual restart after fixing the issue |
| **Tolerate all errors** | `errors.tolerance=all` | Connector continues; errant records are silently dropped unless DLQ is configured |
| **Tolerate data errors only** | `errors.tolerance=data` | Continues on data conversion/format errors; stops on framework errors |

### Dead Letter Queue Configuration

```properties
# Enable DLQ routing
errors.tolerance=all
errors.deadletterqueue.topic.name=my-connector-dlq
errors.deadletterqueue.context.headers.enable=true   # adds error metadata headers

# Logging
errors.log.enable=true
errors.log.include.messages=true

# MongoDB-level errors (separate from Kafka Connect framework errors)
mongo.errors.tolerance=all
mongo.errors.log.enable=true
```

**DLQ context headers** include:
- `__connect.errors.exception.class.name`
- `__connect.errors.exception.message`
- `__connect.errors.topic` (original topic)
- `__connect.errors.partition` (original partition)
- `__connect.errors.offset` (original offset)

### Bulk Write Error Handling

When `bulk.write.ordered=false`, individual failed writes are routed to the DLQ while successful writes proceed. When `bulk.write.ordered=true` (default), an error stops the entire batch at the failure point.

**Recommendation:** Use `bulk.write.ordered=false` + `errors.tolerance=all` + DLQ for production pipelines requiring high throughput and resilience.

**Source:** [Error Handling Strategies](https://www.mongodb.com/docs/kafka-connector/current/sink-connector/fundamentals/error-handling-strategies/), [Error Handling Properties](https://www.mongodb.com/docs/kafka-connector/current/sink-connector/configuration-properties/error-handling/)

---

## 6. Schema Registry Integration

### Supported Data Formats

| Format | Converter | Schema Registry Required |
|---|---|---|
| JSON (schemaless) | `JsonConverter` | No |
| JSON with schema | `JsonConverter` (schemas.enable=true) | No |
| Avro | `AvroConverter` | Yes |
| JSON Schema | `JsonSchemaConverter` | Yes |
| Protobuf | `ProtobufConverter` | Yes |
| BSON | `BsonConverter` (MongoDB-provided) | No |
| String | `StringConverter` | No |

### Avro with Confluent Schema Registry

```properties
# Source connector — publish as Avro
key.converter=io.confluent.connect.avro.AvroConverter
key.converter.schema.registry.url=https://schema-registry.example.com
value.converter=io.confluent.connect.avro.AvroConverter
value.converter.schema.registry.url=https://schema-registry.example.com

# Sink connector — consume Avro
key.converter=io.confluent.connect.avro.AvroConverter
key.converter.schema.registry.url=https://schema-registry.example.com
value.converter=io.confluent.connect.avro.AvroConverter
value.converter.schema.registry.url=https://schema-registry.example.com
```

### BSON Pass-Through

To pass BSON documents without JSON serialization overhead:

```properties
value.converter=com.mongodb.kafka.connect.source.converter.BsonConverter
```

### Schema Evolution Considerations

- **Avro backward compatibility:** Add fields with defaults; never remove or rename required fields.
- **Schema evolution failures:** If the sink receives an Avro record with an incompatible schema version, it routes to DLQ (if configured) or halts the connector.
- **JSON Schema mode** in Confluent Registry (`JSON_SR`) is preferred over plain JSON when you need schema validation without JVM Avro serialization overhead.

**Source:** [Data Formats](https://www.mongodb.com/docs/kafka-connector/current/introduction/data-formats/), [Specify a Schema](https://www.mongodb.com/docs/kafka-connector/current/source-connector/usage-examples/schema/)

---

## 7. CDC Patterns and Delivery Semantics

### Delivery Guarantees

| Guarantee | How to Achieve |
|---|---|
| **At-least-once** (default) | Default behavior; connector may re-deliver on restart |
| **Effectively-once (idempotent sink)** | `ReplaceOneBusinessKeyStrategy` + unique index on business key |
| **Exactly-once (Kafka-level)** | Kafka idempotent producer (`enable.idempotence=true`) + Kafka transactions (`transactional.id`) — not natively exposed in connector; use Kafka Streams or external framework on top |

**The MongoDB Kafka Connector advertises at-least-once delivery.** To make your pipeline effectively idempotent:
1. Use `ReplaceOneBusinessKeyStrategy` with a field that uniquely identifies each logical entity.
2. Create a unique index on that field in MongoDB.
3. Retried/replayed messages will `replaceOne` on the same document rather than creating duplicates.

### Ordering Guarantees

- **Per-partition ordering** is guaranteed by Kafka. Assign a partition key that maps to the logical entity (e.g., `documentKey._id` for the source connector default).
- **Cross-partition ordering** is not guaranteed — design your pipeline so that operations on the same document always route to the same partition.
- Source connector default: uses `documentKey` as the Kafka record key, which (with default hash partitioning) routes all changes to the same document to the same partition.

### Outbox Pattern

For exactly-once-semantics style CDC without Kafka transactions:

```javascript
// Write operation + outbox event in one transaction
await session.withTransaction(async () => {
  await db.orders.insertOne(order, { session });
  await db.outbox.insertOne({
    aggregateType: "Order",
    aggregateId: order._id,
    eventType: "OrderCreated",
    payload: order,
    createdAt: new Date()
  }, { session });
});
```

The source connector watches the `outbox` collection, publishes to Kafka, and a separate process (or scheduled Atlas trigger) marks events as processed. This guarantees the event is published if and only if the database write succeeds.

### MongoDB → MongoDB Replication via Kafka

```
Source cluster (change stream)
  → Source connector → Kafka topic
  → Sink connector (ChangeStreamHandler CDC handler)
  → Target cluster (replicated collection)
```

```properties
# Sink: MongoDB CDC handler for native change stream events
change.data.capture.handler=com.mongodb.kafka.connect.sink.cdc.mongodb.ChangeStreamHandler
```

**Source:** [CDC Handler Docs](https://www.mongodb.com/docs/kafka-connector/current/sink-connector/fundamentals/change-data-capture/), [Replicate with CDC Tutorial](https://www.mongodb.com/docs/kafka-connector/current/tutorials/replicate-with-cdc/)

---

## 8. Authentication

### MongoDB Authentication

The connector authenticates to MongoDB via the connection URI. All standard MongoDB authentication mechanisms are supported.

#### SCRAM-SHA-256 (default for Atlas)

```
connection.uri=mongodb+srv://user:password@cluster.mongodb.net/?authSource=admin
```

#### x509 Certificate Authentication

```
connection.uri=mongodb+srv://cluster.mongodb.net/?authMechanism=MONGODB-X509&authSource=%24external&ssl=true
# Additional SSL properties in the connector or JVM system properties:
# -Djavax.net.ssl.keyStore=/path/to/keystore.jks
# -Djavax.net.ssl.keyStorePassword=changeit
# -Djavax.net.ssl.trustStore=/path/to/truststore.jks
```

#### AWS IAM (MONGODB-AWS)

Requires MongoDB Kafka Connector v1.5+. Uses AWS credentials from environment, EC2 instance profile, ECS task role, or explicit config:

```
connection.uri=mongodb+srv://cluster.mongodb.net/?authMechanism=MONGODB-AWS&authSource=%24external
# Credentials from environment: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
```

**Source:** [MongoDB AWS Auth](https://www.mongodb.com/docs/kafka-connector/current/security-and-authentication/mongodb-aws-auth/)

### Kafka / MSK Authentication

When the Kafka cluster uses IAM (Amazon MSK):

```properties
# Kafka Connect worker properties for MSK IAM
security.protocol=SASL_SSL
sasl.mechanism=AWS_MSK_IAM
sasl.jaas.config=software.amazon.msk.auth.iam.IAMLoginModule required;
sasl.client.callback.handler.class=software.amazon.msk.auth.iam.IAMClientCallbackHandler
```

When using SASL/SCRAM with MSK:

```properties
security.protocol=SASL_SSL
sasl.mechanism=SCRAM-SHA-512
sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required \
  username="myuser" password="mypassword";
```

**Source:** [AWS MSK Auth](https://aws.amazon.com/blogs/big-data/build-a-serverless-streaming-pipeline-with-amazon-msk-serverless-amazon-msk-connect-and-mongodb-atlas/)

---

## 9. Deployment Options

### Self-Hosted Kafka Connect

Install the connector JAR into the Kafka Connect plugin path:

```bash
# Download from Confluent Hub
confluent-hub install mongodb/kafka-connect-mongodb:latest

# Or manually add to KAFKA_CONNECT_PLUGINS_DIR
cp mongo-kafka-connect-*.jar /opt/kafka/plugins/
```

**Advantages:** Full access to all configuration properties; custom write model strategies; full schema registry control; on-premises deployments.

**Overhead:** You manage worker scaling, upgrades, monitoring, and failover.

### Confluent Cloud Managed Connector

Confluent Cloud offers fully managed MongoDB Atlas Source and Sink Connectors.

**Advantages:** Zero infrastructure management; UI-based configuration; elastic scaling; multi-cloud (AWS/Azure/GCP).

**Limitations:** Subset of self-hosted configuration options; some advanced properties (custom write model strategies, custom CDC handlers) are not available.

**Setup:** In Confluent Cloud → Connectors → Add Connector → MongoDB Atlas Source/Sink.

**Source:** [Confluent Cloud MongoDB Source](https://docs.confluent.io/cloud/current/connectors/cc-mongo-db-source.html), [Confluent Cloud MongoDB Sink](https://docs.confluent.io/cloud/current/connectors/cc-mongo-db-sink/cc-mongo-db-sink.html)

### Amazon MSK Connect

Deploy as an MSK Connect custom plugin:

1. Upload the connector JAR to S3.
2. Create a custom plugin in MSK Connect from the S3 object.
3. Create a connector using the plugin with worker configuration for IAM or SCRAM auth.

For MSK IAM auth to both MSK and Atlas, ensure the IAM role has:
- MSK IAM connect permissions on the cluster/topic ARNs
- Network access to Atlas (VPC peering or Atlas Private Endpoint)

**Source:** [AWS MSK + MongoDB Atlas](https://aws.amazon.com/blogs/big-data/build-a-serverless-streaming-pipeline-with-amazon-msk-serverless-amazon-msk-connect-and-mongodb-atlas/)

---

## 10. Performance Tuning

### Source Connector Throughput

| Parameter | Default | Tuning Guidance |
|---|---|---|
| `poll.max.batch.size` | 1000 | Increase for high-volume change streams; decrease to reduce latency |
| `poll.await.time.ms` | 5000 | Decrease for lower end-to-end latency; increase to reduce empty polls |
| `batch.size` | 0 | Set to match `poll.max.batch.size` for cursor-level batching |
| `startup.mode.copy.existing.max.threads` | CPU count | Increase for faster initial snapshot of large collections |

### Sink Connector Throughput

| Parameter | Default | Tuning Guidance |
|---|---|---|
| `bulk.write.ordered` | true | Set to `false` for maximum throughput when order doesn't matter |
| `max.num.retries` | 3 | Increase for transient network failures |
| `retries.defer.timeout` | 5000 | Backoff between retries (ms) |

**Kafka Connect worker settings** (in the Connect worker `connect-distributed.properties`, not the connector JSON):

```properties
# Task parallelism — set in connector config, not worker config
# tasks.max is a connector-level property (goes in the connector POST body)
# For sink: tasks.max should equal the number of topic partitions (no benefit exceeding it)
# For source: tasks.max=1 is the only supported value (single change stream cursor)

# Consumer fetch tuning (worker config)
consumer.max.poll.records=1000     # records fetched per poll cycle
consumer.fetch.max.bytes=52428800  # 50MB max fetch per request

# Producer settings for source connector (worker config)
producer.batch.size=131072         # 128KB batching before send
producer.linger.ms=5               # wait up to 5ms to fill batches
producer.compression.type=snappy   # compress Kafka records
```

> **Note:** `tasks.max` for the **source connector** must be 1 — the connector opens a single change stream cursor and cannot be split across tasks. For the **sink connector**, set `tasks.max` equal to the topic's partition count for full parallelism.

### Index Strategy for Sink Performance

- Create targeted indexes that match your write model strategy before running the sink.
- For `ReplaceOneBusinessKeyStrategy`: unique index on business key fields.
- For `UpdateOneTimestampsStrategy`: index on `_id` is sufficient.
- Avoid unnecessary indexes on write-heavy collections (they slow bulk writes).

**Source:** [MongoDB Kafka Connector Tuning](https://www.mongodb.com/developer/products/connectors/tuning-mongodb-kafka-connector/)

---

## 11. Kafka Connector vs Atlas Stream Processing

| Dimension | Kafka Connector | Atlas Stream Processing (ASP) |
|---|---|---|
| **Deployment model** | Self-hosted Kafka Connect, Confluent Cloud, or MSK Connect | Fully managed, Atlas-native |
| **Processing capabilities** | Simple field mapping, SMTs, custom Java strategies | Full MongoDB aggregation pipeline + streaming extensions |
| **Windowing** | No native support (need Kafka Streams/Flink) | Tumbling, hopping, session windows built-in |
| **State management** | Stateless by default | Managed, checkpointed state |
| **Connectivity** | Kafka + MongoDB | Kafka + MongoDB + HTTPS |
| **Security** | SSL/TLS, x509, AWS IAM, custom | SSL/TLS, x509, VPC Peering, Private Link (AWS/Azure) |
| **Pricing model** | Per task-hour on host (Confluent/MSK) | Per Stream Processing Instance (SPI) hour; ~25% of Kafka Connector cost per MongoDB claim |
| **Kafka expertise required** | Yes | MongoDB/MQL knowledge sufficient |
| **Custom processing logic** | Custom Java plugin possible | Limited to MQL aggregation operators |
| **Use case fit** | Multi-system Kafka ecosystems; custom strategies | Atlas-centric pipelines; teams already using Atlas |

**Decision guide:**

- **Choose Kafka Connector** when you have an existing Kafka Connect infrastructure, need custom Java write model strategies, need Debezium CDC handlers for non-MongoDB sources, or require multi-cloud/multi-vendor flexibility.
- **Choose Atlas Stream Processing** when you want a fully managed solution, need windowing and stateful aggregations, your team knows MQL but not JVM, or when cost-efficiency on Atlas-to-Atlas pipelines is a priority.

**Source:** [ASP vs Kafka Connector Comparison](https://www.mongodb.com/docs/kafka-connector/current/kafka-connector-atlas-stream-processing-comparison/), [ASP Blog Post](https://www.mongodb.com/blog/post/atlas-stream-processing-cost-effective-way-integrate-kafka-mongodb)

---

## 12. Common Integration Patterns

### MongoDB → Kafka → Elasticsearch

```
[MongoDB orders collection]
  → Source connector (change stream, full document)
  → Kafka topic: mongo.ecommerce.orders
  → Elasticsearch Sink Connector (Confluent Hub: confluentinc/kafka-connect-elasticsearch)
  → Elasticsearch index: orders
```

Key consideration: Use `publish.full.document.only=true` in the source connector so Elasticsearch receives complete documents, not change event envelopes.

### MongoDB → Kafka → S3 (Data Lake)

```
[MongoDB events collection]
  → Source connector
  → Kafka topic: mongo.app.events
  → S3 Sink Connector (Confluent Hub: confluentinc/kafka-connect-s3)
  → S3 bucket: s3://my-datalake/events/
```

Use Avro format with schema registry for compact, schema-evolved storage in S3. Partition by date/hour via `TimeBasedPartitioner` in the S3 connector.

### MongoDB → Kafka → Snowflake

```
[MongoDB] → Source → Kafka topic → Snowflake Kafka Connector → Snowflake table
```

Use `JsonConverter` with `schemas.enable=false` or Avro. Enable `publish.full.document.only=true` for clean Snowflake ingestion.

### Cross-Cluster MongoDB Replication

```
[Source MongoDB]
  → Source connector → Kafka topic
  → Sink connector (ChangeStreamHandler CDC handler)
  → [Target MongoDB]
```

This pattern replicates data between MongoDB clusters without mongosync — useful for region-local read replicas, data lake synchronization, or heterogeneous version environments.

### Outbox Pattern for Reliable Event Publishing

```
[Application]
  → MongoDB transaction: write domain + outbox collection
  → Source connector watches outbox collection
  → Kafka topic: domain-events
  → Downstream consumers
```

Guarantees events are published if and only if the domain write succeeds. Add a TTL index on `outbox.createdAt` to auto-expire processed events:

```javascript
db.outbox.createIndex({ createdAt: 1 }, { expireAfterSeconds: 86400 })
```

---

## 13. Troubleshooting

### Invalid Resume Token

**Symptom:** Source connector fails with `Command failed with error 286 (ChangeStreamHistoryLost)` or `InvalidResumeToken`.

**Cause:** The MongoDB oplog has rotated past the stored resume token while the connector was paused or idle.

**Remedies:**
1. **Renew via heartbeats (prevention):** Set `heartbeat.interval.ms=30000` for low-volume namespaces to keep the resume token fresh.
2. **Rename the connector:** Change the `name` property to force a new consumer group and fresh change stream start.
3. **Change offset partition name:** Set `offset.partition.name=<new-unique-name>` to abandon the old offset and start a new change stream.
4. **Reset to timestamp:** Set `startup.mode=timestamp` with `startup.mode.timestamp.start.at.operation.time` to replay from a known-good point.

**Source:** [Invalid Resume Token Recovery](https://www.mongodb.com/docs/kafka-connector/current/troubleshooting/recover-from-invalid-resume-token/)

### Connector Stuck / Not Consuming

- Check Kafka Connect worker logs for task-level errors.
- Verify MongoDB connectivity from the Connect worker (DNS, network ACL, Atlas IP allowlist).
- Check `tasks.max` vs partition count — a sink with fewer tasks than partitions will under-consume.
- Look for task restarts due to DLQ misconfiguration (if DLQ topic doesn't exist and `errors.deadletterqueue.topic.name` is set, the connector will fail).

### Schema Evolution Failures

- **Avro incompatibility:** Add fields with defaults; never remove required fields without evolving the schema to a new subject version.
- **Schema registry connection failure:** Verify the schema registry URL is accessible from the Connect workers.
- **JSON → BSON type mismatches:** Use the MongoDB BSON converter or ensure your JSON payloads have consistent types. Numeric types in JSON default to `Double`; use `$numberInt`/`$numberLong` extended JSON notation for precise integer types.

### High Consumer Lag on Sink

- Increase `tasks.max` to match topic partition count.
- Set `bulk.write.ordered=false` to allow parallel bulk writes.
- Increase `consumer.max.poll.records` in worker config.
- Check MongoDB write latency: run `db.collection.explain("executionStats")` on a sample write to verify index usage.
- Check network latency between Kafka Connect workers and MongoDB (should be sub-5ms for optimal performance).

### Source Connector Producing Duplicate Events

- Kafka Connect exactly-once semantics require Kafka 2.6+ and specific worker configuration (`exactly.once.source.support=enabled`). Without this, duplicates can occur on task restart.
- For sink idempotency, use `ReplaceOneBusinessKeyStrategy` with a unique index — duplicates become no-op upserts.

---

## 14. Anti-Patterns

| Anti-pattern | Risk | Mitigation |
|---|---|---|
| Using `InsertOneDefaultStrategy` in a replay-able pipeline | Duplicate key errors on message replay | Use `ReplaceOneDefaultStrategy` or `ReplaceOneBusinessKeyStrategy` |
| No heartbeat on low-volume change streams | Invalid resume token on connector restart | Set `heartbeat.interval.ms=30000` |
| Watching deployment-wide change stream in high-write environments | Single change stream cursor becomes a bottleneck | Watch at collection level; use `pipeline` to filter |
| Omitting DLQ configuration | Transient errors halt the connector silently | Always configure `errors.tolerance=all` + DLQ topic in production |
| Mismatch between `tasks.max` and topic partitions | Under-utilization of parallelism | Set `tasks.max` equal to the number of topic partitions (for sink) |
| Using ordered bulk writes at high throughput | Single error stops entire batch | Set `bulk.write.ordered=false` for write-heavy sinks |
| Fetching `updateLookup` full document on high-update collection | Extra read per update event; increases read load on MongoDB | Use pre/post images (MongoDB 6.0+ `change.stream.full.document=whenAvailable`) instead |
| Storing connector credentials in plaintext connector config | Security exposure | Use Kafka Connect secret providers (filesystem, vault, or AWS Secrets Manager) |
| Not creating indexes before running sink | Upserts are slow without index on business key | Create unique index on business key before starting sink |

---

## 15. Quick Reference: Configuration Cheat Sheet

### Minimal Source (watch a collection, publish JSON)

```properties
connector.class=com.mongodb.kafka.connect.MongoSourceConnector
connection.uri=mongodb+srv://user:pass@cluster.mongodb.net/
database=mydb
collection=mycollection
topic.prefix=mongo
value.converter=org.apache.kafka.connect.json.JsonConverter
value.converter.schemas.enable=false
heartbeat.interval.ms=30000
```

### Minimal Sink (consume JSON, upsert by _id)

```properties
connector.class=com.mongodb.kafka.connect.MongoSinkConnector
connection.uri=mongodb+srv://user:pass@cluster.mongodb.net/
database=mydb
collection=mycollection
topics=mongo.mydb.mycollection
value.converter=org.apache.kafka.connect.json.JsonConverter
value.converter.schemas.enable=false
```

### Production Sink (business key, DLQ, unordered writes)

```properties
connector.class=com.mongodb.kafka.connect.MongoSinkConnector
connection.uri=mongodb+srv://...
database=mydb
collection=mycollection
topics=mongo.mydb.mycollection
document.id.strategy=com.mongodb.kafka.connect.sink.processor.id.strategy.PartialValueStrategy
document.id.strategy.partial.value.projection.list=businessId
document.id.strategy.partial.value.projection.type=AllowList
writemodel.strategy=com.mongodb.kafka.connect.sink.writemodel.strategy.ReplaceOneBusinessKeyStrategy
bulk.write.ordered=false
errors.tolerance=all
errors.deadletterqueue.topic.name=mydb-mycollection-dlq
errors.deadletterqueue.context.headers.enable=true
errors.log.enable=true
value.converter=org.apache.kafka.connect.json.JsonConverter
value.converter.schemas.enable=false
```

---

## Key Documentation Links

- [MongoDB Kafka Connector Overview](https://www.mongodb.com/docs/kafka-connector/current/)
- [Source Connector](https://www.mongodb.com/docs/kafka-connector/current/source-connector/)
- [Sink Connector](https://www.mongodb.com/docs/kafka-connector/current/sink-connector/)
- [All Source Properties](https://www.mongodb.com/docs/kafka-connector/current/source-connector/configuration-properties/all-properties/)
- [Write Model Strategies](https://www.mongodb.com/docs/kafka-connector/current/sink-connector/fundamentals/write-strategies/)
- [Error Handling](https://www.mongodb.com/docs/kafka-connector/current/sink-connector/fundamentals/error-handling-strategies/)
- [Data Formats](https://www.mongodb.com/docs/kafka-connector/current/introduction/data-formats/)
- [CDC Handlers](https://www.mongodb.com/docs/kafka-connector/current/sink-connector/fundamentals/change-data-capture/)
- [Invalid Resume Token Recovery](https://www.mongodb.com/docs/kafka-connector/current/troubleshooting/recover-from-invalid-resume-token/)
- [Troubleshooting](https://www.mongodb.com/docs/kafka-connector/current/troubleshooting/)
- [ASP vs Kafka Connector Comparison](https://www.mongodb.com/docs/kafka-connector/current/kafka-connector-atlas-stream-processing-comparison/)
- [GitHub: mongodb/mongo-kafka](https://github.com/mongodb/mongo-kafka)
- [Confluent Hub](https://www.confluent.io/hub/mongodb/kafka-connect-mongodb)
- [Tuning Guide](https://www.mongodb.com/developer/products/connectors/tuning-mongodb-kafka-connector/)
- [AWS MSK + Atlas Blog](https://aws.amazon.com/blogs/big-data/build-a-serverless-streaming-pipeline-with-amazon-msk-serverless-amazon-msk-connect-and-mongodb-atlas/)
