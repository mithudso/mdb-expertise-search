<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-spark-connector` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-spark-connector
category: mongodb
version: 1.2.0
updated: 2026-05-29
tags: [mongodb, spark, databricks, streaming, cdc, etl, delta-lake, data-engineering]
description: "MongoDB Spark Connector V10 and Databricks integration — batch/streaming reads from change streams, batch/streaming writes with upsert/insert/replace, aggregation pushdown (predicates, projections, sort, limit), partitioner strategies (AutoBucket/Sample/PaginateBySize/Sharded), Databricks workspace setup (cluster libraries, secret scopes, VPC peering), schema inference vs explicit schema, structured streaming with resume tokens and checkpoints, Atlas Federated Database trade-offs, and common failure modes (schema drift, type coercion, partition skew). TRIGGER when designing, implementing, debugging, or reviewing MongoDB ↔ Spark/Databricks pipelines. SKIP for non-Spark ingest (Kafka Connect alone), pure aggregation pipeline questions, Atlas Data Federation without Spark, Atlas Stream Processing pipelines that never leave MongoDB, or change stream semantics without a Spark consumer."
when_to_use:
  - Designing or reviewing a MongoDB ↔ Spark/Databricks data pipeline
  - Debugging a Spark Connector job that is slow, memory-bound, hitting skew, or failing schema inference
  - Choosing between Spark Connector, Kafka + Source Connector, Atlas Data Federation, or Delta Live Tables for ingest
  - Writing PySpark/Scala code that reads change streams into Delta Lake (CDC pipelines)
  - Tuning partitioner choice, batch sizes, or connection pool sizing for high-volume reads
  - Setting up Databricks cluster libraries, secret scopes, and Atlas network access
  - Migrating from V2.x (com.mongodb.spark.sql.DefaultSource) to V10+
when_not_to_use:
  - Non-Spark MongoDB ingest (Kafka Connect alone) — use mongodb-kafka-connector
  - Aggregation pipeline syntax with no Spark involvement — use mongodb-aggregation-pipeline
  - Atlas Data Federation SQL queries without Spark — use mongodb-atlas-data-federation
  - Atlas Stream Processing pipelines that never leave MongoDB — use mongodb-atlas-stream-processing
  - Change stream semantics without a Spark consumer — use mongodb-change-streams
related_skills:
  - mongodb-change-streams
  - mongodb-aggregation-pipeline
  - mongodb-atlas-data-federation
  - mongodb-migration-patterns
  - mongodb-kafka-connector
  - mongodb-indexes-deep
  - mongodb-sharding
  - mongodb-atlas-iac
  - mongodb-atlas-terraform
  - mongodb-atlas-stream-processing
  - mongodb-cdc-architecture
---

# MongoDB Spark Connector and Databricks Integration

Expert reference for the MongoDB Spark Connector V10+ (post-2022 rewrite) and its use inside Databricks. The connector is the canonical bridge between MongoDB (Atlas, self-managed, or Federated) and Apache Spark — both for offline analytics (batch DataFrame reads/writes) and real-time pipelines (Structured Streaming with change streams). This skill covers the full operating surface: setup, partitioning, pushdown, write semantics, streaming checkpoints, Databricks-specific wiring, and the failure patterns that bite production pipelines.

## When to use this skill

Trigger when:
- Designing or reviewing a MongoDB ↔ Spark/Databricks data pipeline.
- Debugging a Spark Connector job that is slow, memory-bound, hitting skew, or failing schema inference.
- Choosing between **Spark Connector**, **Kafka + Source Connector**, **Atlas Data Federation `$out`**, or **Delta Live Tables** for ingest.
- Writing PySpark/Scala code that reads change streams into Delta Lake (CDC pipelines).
- Tuning partitioner choice, batch sizes, or connection pool sizing for high-volume reads.
- Setting up Databricks cluster libraries, secret scopes, and Atlas network access (IP allowlist, VPC peering, PrivateLink).
- Migrating from V2.x (`com.mongodb.spark.sql.DefaultSource`) to V10+ (`com.mongodb.spark.sql.connector.MongoTableProvider`).

## When NOT to use

- Questions about non-Spark MongoDB ingest (Kafka Connect alone) → `mongodb-kafka-connector`.
- Aggregation pipeline syntax with no Spark involvement → `mongodb-aggregation-pipeline`.
- Atlas Data Federation SQL queries without Spark → `mongodb-atlas-data-federation`.
- Atlas Stream Processing pipelines that never leave MongoDB → `mongodb-atlas-stream-processing`.
- Mongo change stream semantics without a Spark consumer → `mongodb-change-streams`.

## Quick start (5-minute PySpark batch read)

```python
from pyspark.sql import SparkSession

spark = (SparkSession.builder
    .appName("mongo-quickstart")
    .config("spark.jars.packages", "org.mongodb.spark:mongo-spark-connector_2.12:10.5.0")
    .getOrCreate())

df = (spark.read
    .format("mongodb")
    .option("connection.uri", "mongodb+srv://USER:PASS@cluster.mongodb.net/")
    .option("database", "sales")
    .option("collection", "orders")
    .load())

df.printSchema()
df.show(5)
```

Replace `10.5.0` with the artifact that matches your DBR Scala version — see the "Pick the right artifact for Databricks" table in section 1. On Databricks, install the JAR as a cluster library instead of using `spark.jars.packages`. On Spark Connect / Databricks Serverless SQL (no cluster library UI), declare the dependency via `spark.jars.packages` in the session config or pre-build a custom container image with the connector JAR.

---

## 1. Connector versions and architecture (V10 vs legacy)

The connector has two lineages. Most production code in 2024+ should be on V10.x.

### Legacy V2.x (`com.mongodb.spark.sql.DefaultSource`)
- Package: `org.mongodb.spark:mongo-spark-connector_2.12:3.0.x` (3.x is V2 lineage despite the major-version look).
- Configures via `spark.mongodb.input.uri` / `spark.mongodb.output.uri`.
- Pre-Spark-3.2 DataSourceV1 API. Less efficient pushdown. No first-class Structured Streaming.
- Still in use on older Databricks runtimes (DBR 9.x and earlier).

### V10.x (`com.mongodb.spark.sql.connector.MongoTableProvider`)
- Maven: `org.mongodb.spark:mongo-spark-connector_2.12:10.x.y` (Scala 2.12) or `_2.13:10.x.y` (Scala 2.13).
- **Rebuilt on Spark 3 DataSourceV2 API** — first-class catalog, batch, and streaming sources.
- Configures via `spark.mongodb.read.*` / `spark.mongodb.write.*` namespaces (separate read/write URIs are now standard).
- Tighter Structured Streaming integration: streaming source reads from change streams, streaming sink writes via `MongoMicroBatchWriter`.
- Namespace is intentionally distinct so V10 and V2 can coexist in the same SparkSession during migration.
- Version compatibility (verify against the release notes for your exact build):
  - **10.0.x** — Spark 3.1+
  - **10.1.x** — adds Spark Connect support, schema inference improvements
  - **10.2.x** — performance fixes, configurable partitioner improvements
  - **10.3.x** — Spark 3.3 / 3.4 / 3.5 compatibility, AutoBucketPartitioner introduced
  - **10.4.x** — streaming write microbatch mode, expanded write options
  - **10.5.x** — `AutoBucketPartitioner` becomes the default; Atlas Data Federation supported for batch reads with sample/paginate/auto-bucket partitioners
  - **10.6.x** — Scala 2.13 builds; further Spark 3.5+ hardening

### Pick the right artifact for Databricks
| DBR runtime | Scala | Recommended connector |
| --- | --- | --- |
| 10.x – 11.x | 2.12 | `mongo-spark-connector_2.12:10.3.x` |
| 12.x – 13.x | 2.12 | `mongo-spark-connector_2.12:10.4.x` |
| 14.x – 15.x Scala 2.12 (Spark 3.5) | 2.12 | `mongo-spark-connector_2.12:10.5.x` (default) or `10.6.x` |
| 14.x+ Scala-2.13 images | 2.13 | `mongo-spark-connector_2.13:10.6.x` |
| 16.x+ (Spark 4.0+) | 2.13 | `mongo-spark-connector_2.13:10.6.x` — verify release notes for Spark 4.0 compatibility before use |

Decision rule: match the runtime's Scala major version exactly. If `_2.13` is loaded on a 2.12 cluster (or vice versa), classloading fails at job start with `NoClassDefFoundError: scala/Product$class`. Check the DBR release notes for the exact Scala version of your runtime.

### Spark Connect support (DBR Serverless SQL, 10.1+)
V10.1 added Spark Connect compatibility, enabling the connector to run inside Databricks Serverless SQL warehouses and Spark Connect clusters. In Spark Connect mode, all driver-side connector logic (schema inference, partitioning) runs on the connect server rather than the client. Behavior is otherwise identical to classic Spark.

---

## 2. Configuration namespaces

V10 uses three top-level namespaces. Mixing them with V2's `input.uri`/`output.uri` is a common migration bug.

```python
# Connection (shared)
"spark.mongodb.connection.uri": "mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority"

# Read
"spark.mongodb.read.database": "analytics"
"spark.mongodb.read.collection": "events"
"spark.mongodb.read.partitioner": "com.mongodb.spark.sql.connector.read.partitioner.AutoBucketPartitioner"
"spark.mongodb.read.partitioner.options.partition.size": "64"
"spark.mongodb.read.aggregation.pipeline": "[{ $match: { tenant: 'acme' } }]"
"spark.mongodb.read.inferSchema.sampleSize": "10000"
"spark.mongodb.read.outputExtendedJson": "false"

# Write
"spark.mongodb.write.database": "analytics"
"spark.mongodb.write.collection": "events_processed"
"spark.mongodb.write.operationType": "update"
"spark.mongodb.write.idFieldList": "tenant,event_id"
"spark.mongodb.write.upsertDocument": "true"
"spark.mongodb.write.writeConcern.w": "majority"
"spark.mongodb.write.maxBatchSize": "512"
```

Configuration can be applied at three scopes — each later layer overrides the previous:

1. **SparkSession** — `spark.conf.set("spark.mongodb.read.collection", "events")` (use the full `spark.mongodb.<read|write>.<key>` prefix).
2. **DataFrame reader/writer options** — `.option("collection", "events")` (drop the `spark.mongodb.read.` / `spark.mongodb.write.` prefix; the reader/writer infers it from the format and read-vs-write direction).
3. **Per-operation overrides** — passed in `.options({...})`.

**Consistency rule for examples in this document:** all `.option("...")` and `.options({...})` calls use the **short** key form (no `spark.mongodb.` prefix). All `spark.conf.set("...")` calls and Spark properties use the **full** prefix. Mixing them inside `.option()` is harmless but inconsistent and will confuse readers maintaining the code.

Read and write URIs can target different clusters (e.g., read from a secondary in a regional Atlas cluster, write to a primary in another region) by setting `spark.mongodb.read.connection.uri` and `spark.mongodb.write.connection.uri` independently.

---

## 3. Batch reads

### Minimal PySpark batch read

```python
df = (spark.read
    .format("mongodb")
    .option("connection.uri", uri)
    .option("database", "sales")
    .option("collection", "orders")
    .load())
df.printSchema()
df.count()
```

### Explicit schema (recommended for production)

Schema inference samples the collection (default 1000 docs) on driver startup. For collections with sparse fields, mixed types, or 100M+ documents, **always supply an explicit schema** — inference adds 30–120 seconds to job startup and can produce `MatchError` on mixed-type fields.

```python
from pyspark.sql.types import StructType, StructField, StringType, LongType, TimestampType, ArrayType

schema = StructType([
    StructField("_id", StringType(), False),
    StructField("tenant", StringType(), False),
    StructField("event_ts", TimestampType(), False),
    StructField("amount", LongType(), True),
    StructField("tags", ArrayType(StringType()), True),
])

df = (spark.read
    .format("mongodb")
    .option("connection.uri", uri)
    .option("database", "sales")
    .option("collection", "orders")
    .schema(schema)
    .load())
```

### Pre-filter with an aggregation pipeline

The `aggregation.pipeline` option is the single biggest knob for read performance. It runs on the MongoDB server before any data leaves the cluster:

```python
pipeline = """[
    { "$match": { "tenant": "acme", "status": "completed" } },
    { "$project": { "_id": 1, "amount": 1, "event_ts": 1 } }
]"""

df = (spark.read
    .format("mongodb")
    .option("connection.uri", uri)
    .option("database", "sales")
    .option("collection", "orders")
    .option("aggregation.pipeline", pipeline)
    .option("aggregation.allowDiskUse", "true")
    .load())
```

Setting `aggregation.allowDiskUse=true` lets the server spill stages over the 100MB in-memory limit — necessary for large `$sort` or `$group` stages embedded in the pipeline.

---

## 4. Aggregation pushdown

Spark's Catalyst optimizer pushes predicates, projections, and (in V10) `LIMIT` and column ordering down to the MongoDB server. The connector translates each pushed operation into an aggregation pipeline stage prepended to the user-supplied pipeline.

### What gets pushed
| Spark operation | Pushed as | Notes |
| --- | --- | --- |
| `.filter(col("x") === lit("a"))` | `$match: { x: "a" }` | Equality, ranges, `$in`, `$or`/`$and`, `$exists` |
| `.select("a", "b")` | `$project: { a: 1, b: 1, _id: 0 }` | Top-level fields only; nested struct selection projects parent |
| `.limit(N)` | `$limit: N` | V10.1+; honored only when no shuffle is inserted |
| `.where("x is null")` | `$match: { x: null }` | BSON null vs missing — see type coercion notes |

### What does NOT push down
- Spark UDFs (always run client-side after data arrives in executors).
- Joins between two MongoDB DataFrames (the connector reads both collections independently; the join runs in Spark).
- Window functions, `groupBy` aggregations (Spark performs aggregation client-side unless you express it explicitly in `aggregation.pipeline`).
- Type-cast filters where Spark inserts implicit `cast` (e.g., comparing a numeric column to a string literal — Spark wraps the literal in `cast` and may not push it).

### Verify what got pushed
Set `spark.sql.adaptive.enabled=true` and inspect the physical plan:
```python
df.filter("amount > 100").select("tenant", "amount").explain(True)
# Look for: PushedFilters: [GreaterThan(amount,100)]
# And:      PushedAggregates: [], PushedGroupBy: []
```

If `PushedFilters` is empty but you expected pushdown, the filter likely references a nested field with a type the connector cannot map; refactor to a top-level field or push it explicitly via `aggregation.pipeline`.

### Manual override
If Catalyst refuses to push a complex condition, encode it yourself:

```python
df = (spark.read.format("mongodb")
    .option("aggregation.pipeline",
            '[{"$match": {"amount": {"$gt": 100}, "tags": {"$in": ["vip","gold"]}}}]')
    .load())
```

---

## 5. Partitioner strategies

Partitioners split the source collection into parallel reads. They run **only for batch reads** — Structured Streaming uses a single change-stream cursor per source.

### `AutoBucketPartitioner` (default in 10.5+)
Samples the collection, then uses `$bucketAuto` to slice into equal-sized partitions. Works on single or multiple fields, including nested fields. **Best default for general workloads** because partition boundaries adapt to actual data distribution.

```python
.option("partitioner", "com.mongodb.spark.sql.connector.read.partitioner.AutoBucketPartitioner")
.option("partitioner.options.partition.field.list", "tenant,event_ts")
.option("partitioner.options.partition.size", "64")  # MB target per partition
.option("partitioner.options.samples.per.partition", "10")
```

### `SamplePartitioner`
Sample-based but uses `$gte`/`$lt` ranges on one field instead of `$bucketAuto`. Lower overhead than AutoBucket. **Use when** you have a single, well-distributed numeric or date partition field with a known index.

```python
.option("partitioner", "com.mongodb.spark.sql.connector.read.partitioner.SamplePartitioner")
.option("partitioner.options.partition.field", "event_ts")
.option("partitioner.options.partition.size", "64")
```

### `PaginateBySizePartitioner`
Counts documents, divides by max partitions, paginates by `$skip`/`$limit`. **Use when** the partition field is not indexed and the collection is small-to-medium (<10M docs) — `$skip` performance degrades on large collections.

### `PaginateIntoPartitionsPartitioner`
Like PaginateBySize but lets you target a fixed partition count instead of a per-partition size.

### `ShardedPartitioner`
Reads each shard's chunks as separate partitions. **Avoid on MongoDB 6.0+** — sharded collections now initialize with a single jumbo chunk that covers all keys until splits are triggered by the balancer, making this partitioner produce one giant partition until the chunks split. For sharded clusters on 6.0+, use `AutoBucketPartitioner` and let the connector route reads through `mongos`.

### Picking a partitioner
| Workload | Recommended | Why |
| --- | --- | --- |
| Atlas, mixed access pattern | `AutoBucketPartitioner` | Distribution-aware, default |
| Single indexed timestamp field | `SamplePartitioner` | Less overhead, predictable |
| Small collection (<1M), ad-hoc | `PaginateBySizePartitioner` | No sampling cost |
| Atlas Federated Database source | `AutoBucketPartitioner`, `SamplePartitioner`, or `PaginateBySizePartitioner` only | Supported set since 10.5 |
| Self-managed sharded 5.x | `ShardedPartitioner` | Chunk-aware |
| MongoDB 6.0+ sharded | `AutoBucketPartitioner` | On 6.0+, sharding now creates one large initial chunk per shard that does not split until the balancer triggers, so `ShardedPartitioner` produces one giant partition until splits land |
| AWS DocumentDB | `SamplePartitioner` or `SinglePartitionPartitioner` | `collStats` not supported by some partitioners |

### Default `partition.size` decision rule
- Documents < 1 KB average → start at **128 MB** (more docs per partition, fewer tasks).
- Documents 1–100 KB average → start at **64 MB** (the default).
- Documents > 100 KB average or embedded arrays > 1 MB → start at **32 MB**.
- Halve the size if any executor OOMs; double it if the Spark UI shows excessive small tasks (<200 ms each).

### Partition skew remediation
1. Inspect partition sizes via Spark UI → SQL → "Read MongoDB" stage.
2. If one task takes 10x longer than the median, switch to `AutoBucketPartitioner` with `partition.size` halved.
3. For low-cardinality partition fields, prepend an aggregation pipeline that filters down before partitioning.
4. As a last resort, disable partitioning (`partitioner=com.mongodb.spark.sql.connector.read.partitioner.SinglePartitionPartitioner`) and use `df.repartition(N)` in Spark — moves the parallelism boundary out of MongoDB.

---

## 6. Schema inference

The connector samples documents to build a `StructType` because BSON is schemaless. Schema inference runs **on the driver** once, before partitions are computed.

### Control sample size
```python
.option("inferSchema.sampleSize", "10000")  # default 1000
.option("inferSchema.mapTypes.enabled", "true")  # map BSON nested docs as MapType vs StructType
```

A larger sample catches more sparse fields but slows job startup linearly. On a collection with 100M docs and `sampleSize=10000`, inference takes ~30–90 seconds.

### Type promotion rules
When mixed types appear within the sample, the connector promotes to the most permissive compatible type:
- `Int32` ∪ `Int64` → `LongType`
- `Int32` ∪ `Double` → `DoubleType`
- Any type ∪ `String` → `StringType`
- BSON `Document` ∪ `Document` (different fields) → merged `StructType`
- BSON `Array<T1>` ∪ `Array<T2>` → `ArrayType(promoted)`
- Mixed `Date` and `String` → throws `DataException` unless you provide explicit schema or normalize via `aggregation.pipeline`

### Why prefer explicit schema in production
- **Determinism** — sampling is non-deterministic; a job that worked yesterday can fail today if the sample happens to hit a doc with a new sparse field.
- **Startup cost** — inference forks a sample query before partitioning.
- **Type stability** — explicit `LongType` survives sparse documents where some have `Int32` and others lack the field.
- **Sparse field control** — explicit schema lets you opt into capturing rarely-present fields the sample might miss.

Generate the schema once, store it as JSON, version it with the pipeline:
```python
schema_json = df.schema.json()  # snapshot
# store in s3://schemas/orders.json
schema = StructType.fromJson(json.loads(open("orders.json").read()))
```

---

## 7. Batch writes

V10 batch writes use `MongoBulkWriter` underneath, batching documents per partition via `BulkWriteOperation`.

### Write modes

```python
(df.write
    .format("mongodb")
    .mode("append")  # also: "overwrite", "errorIfExists", "ignore"
    .option("connection.uri", uri)
    .option("database", "analytics")
    .option("collection", "orders_processed")
    .option("operationType", "replace")  # insert | update | replace
    .option("idFieldList", "tenant,order_id")
    .option("upsertDocument", "true")
    .option("writeConcern.w", "majority")
    .option("maxBatchSize", "512")
    .save())
```

### `operationType` semantics

| Value | Mongo operation | Idempotent? | Notes |
| --- | --- | --- | --- |
| `insert` | `insertOne` | No (fails on duplicate `_id`) | Use for first-load / append-only sinks |
| `update` | `updateOne` with `$set` on each field | Yes when `idFieldList` is stable | Only changes the listed fields; leaves others untouched |
| `replace` | `replaceOne` | Yes | Replaces the entire document; default if `_id` exists in DF |

`upsertDocument=true` (default) makes `update`/`replace` create the document if no match exists. Set `false` to skip inserts when the match key is missing.

### `idFieldList` and idempotency

The match filter for `update`/`replace` is constructed from `idFieldList`. If `idFieldList` is unset, the connector uses `_id`. For composite keys:

```python
.option("idFieldList", "tenant,event_date,event_type")
```

This translates to `updateOne({tenant: x, event_date: y, event_type: z}, ...)`. **Index the composite key in MongoDB** — without it, each upsert does a collection scan and write throughput collapses.

### `mode("overwrite")`
Drops the target collection before writing. This is **destructive and not transactional** — the drop happens on driver startup, then partitions write in parallel. If a partition fails after the drop, the data is gone. Prefer `mode("append")` with `operationType="replace"` + a stable `idFieldList` for idempotent overwrite semantics.

### `maxBatchSize`
Documents per bulk-write request. Default 512. Lower this if individual documents are large (>1MB) or if WiredTiger ticket exhaustion shows up in Atlas metrics. Raise to 1024 for small (<1KB) docs to reduce round-trip overhead.

### Write concern
`writeConcern.w` defaults to `1` (acknowledged by primary). For pipelines that need durability before reporting success:
- `"majority"` — survives single replica failure but adds latency
- Integer `2` or `3` — fixed-count acknowledgment
- `"journal": true` — wait for on-disk journal commit

For idempotent retryable jobs, `w=1` is usually correct; the retry handles the durability question.

---

## 8. Structured Streaming reads (change streams)

V10 wires Mongo change streams into Spark Structured Streaming. Each micro-batch reads change events since the last committed resume token.

### Minimal streaming read

```python
events = (spark.readStream
    .format("mongodb")
    .option("connection.uri", uri)
    .option("database", "sales")
    .option("collection", "orders")
    .option("change.stream.publish.full.document.only", "true")
    .option("change.stream.full.document", "updateLookup")
    .load())

query = (events.writeStream
    .format("delta")
    .option("checkpointLocation", "s3://lake/checkpoints/orders/")
    .outputMode("append")
    .start("s3://lake/raw/orders/"))
```

### Key streaming-read options

| Option | Purpose |
| --- | --- |
| `change.stream.publish.full.document.only=true` | Emit the post-image document directly (matches schema inference); when `false`, emit the full change-event envelope with `operationType`, `documentKey`, `fullDocument`, `updateDescription` |
| `change.stream.full.document=updateLookup` | For updates, fetch the post-image; default `default` omits it |
| `change.stream.startup.mode=latest|timestamp|resumeAfter` | Where to begin if no checkpoint exists |
| `change.stream.startup.timestamp.start.at.operation.time` | Required when `startup.mode=timestamp` (BSON timestamp string) |
| `change.stream.micro.batch.max.partition.count` | Split a micro-batch into N partitions for parallel downstream processing |
| `aggregation.pipeline` | Filter the change stream server-side (recommended for high-traffic collections) |
| `collection="*"` | Stream all collections in a DB; new collections auto-include |

### Resume tokens and checkpoints

Spark's `checkpointLocation` stores the most recent MongoDB resume token after each successful micro-batch commit. On restart, the connector calls `aggregate.changeStream({resumeAfter: <token>})` to pick up exactly where it left off.

**Failure mode:** if the checkpoint is older than the oplog window, the resume token is invalid and the stream fails with `ChangeStreamHistoryLost`. Atlas oplog windows are tier-dependent and workload-dependent — verify the actual `Oplog Window (hours)` value in Atlas → Metrics → Replica Set Status before estimating tolerance. M10/M20 dev clusters commonly show 1–6 hours under load; M30+ clusters typically show 24+ hours. Mitigations:
1. Lengthen the oplog window in Atlas (Configuration → Additional Settings → Oplog Min Retention Hours).
2. Use `change.stream.startup.mode=timestamp` with a fallback timestamp as recovery path.
3. Monitor checkpoint lag — `currentBatchId - lastCommittedBatchId` in Spark UI's Streaming tab.

### Schema inference for streaming
Schema is inferred from the first change event observed at stream start. **Collections created after stream start are NOT included in inference** even if `collection="*"` would otherwise include them. Provide an explicit schema for production streaming.

### Watermarks and aggregation
For windowed aggregations on streaming data, use Spark's `withWatermark()` on the event-time column from your documents. The MongoDB connector does not project change-stream cluster time as event-time automatically — extract it from `fullDocument` or from the change event's `clusterTime` field (when not using `publish.full.document.only`).

```python
events_with_event_time = (events
    .withColumn("event_time", col("created_at").cast("timestamp"))
    .withWatermark("event_time", "10 minutes"))
```

---

## 9. Structured Streaming writes

The streaming sink writes each micro-batch as a bulk-write batch.

```python
query = (df.writeStream
    .format("mongodb")
    .option("connection.uri", uri)
    .option("database", "analytics")
    .option("collection", "events_silver")
    .option("operationType", "update")
    .option("idFieldList", "event_id")
    .option("upsertDocument", "true")
    .option("checkpointLocation", "s3://lake/checkpoints/silver/")
    .outputMode("append")
    .trigger(processingTime="30 seconds")
    .start())
```

### `outputMode` rules
- `append` — only new rows; works with most pipelines.
- `update` — only rows whose aggregation state changed; requires the sink to support upsert (Mongo does, via `operationType=update`).
- `complete` — every micro-batch rewrites the full result; usually inappropriate for MongoDB sinks. Use only with `groupBy` aggregates and small result sets.

### Microbatch mode for non-streaming sinks
10.4 added microbatch streaming write — useful when chaining a stream into a sink that requires micro-batch semantics (e.g., writing to S3 via foreachBatch).

### Exactly-once semantics
**The streaming sink is at-least-once, not exactly-once.** Spark's checkpoint commits the offset before the write is fully durable in MongoDB; a driver crash mid-commit can replay the last micro-batch. To make the pipeline effectively exactly-once:
1. Use `operationType=update` or `replace` with a stable `idFieldList` — replays become no-ops.
2. Index `idFieldList` in MongoDB.
3. Make downstream consumers (if any) idempotent.

---

## 10. Databricks integration

### Cluster library installation
Two paths:

**Maven (preferred)** — Cluster → Libraries → Install New → Maven → Coordinates:
```
org.mongodb.spark:mongo-spark-connector_2.12:10.5.0
```
Databricks resolves the artifact at cluster start. Requires outbound HTTPS to Maven Central; on restricted networks, mirror to an internal Nexus/Artifactory and set the Maven repository URL in the cluster init script.

**JAR upload** — download the shaded uber-jar from Maven Central, upload via DBFS or workspace files. Use this when:
- The runtime blocks Maven library installation.
- You need a custom build of the connector.
- The cluster is configured with `spark.databricks.driver.disableScalaOutput=true`.

### Driver compatibility
The connector ships with a bundled `mongodb-driver-sync`. Conflicts with other libraries that pull in their own MongoDB driver (most commonly the Atlas Stream Processing SDK or older client libraries) surface as `IllegalAccessError` on `MongoNamespace`. Resolutions:
- Use the shaded uber-jar (`mongo-spark-connector` artifact already shades the driver).
- Pin a single `org.mongodb:mongodb-driver-sync` version cluster-wide.
- Move conflicting client code to a separate notebook with its own library scope.

### Secret scopes for Atlas credentials
Never inline the connection string in notebooks. Use Databricks secret scopes:

```python
uri = dbutils.secrets.get(scope="atlas", key="connection_uri")
df = spark.read.format("mongodb").option("connection.uri", uri).load()
```

Backend options:
- **Databricks-backed scope** — `databricks secrets create-scope --scope atlas`. Simplest; ACL via workspace.
- **Azure Key Vault-backed scope** — `databricks secrets create-scope --scope atlas --scope-backend-type AZURE_KEYVAULT --resource-id <vault>`. Rotation handled by Key Vault.
- **AWS Secrets Manager via custom init** — pull at cluster start into env vars; less integrated than the Azure path but works on any cloud.

Avoid storing the secret in `spark.conf.set()` at session start because the value appears in Spark UI's "Environment" tab.

### Network access to Atlas
| Path | When to use | Notes |
| --- | --- | --- |
| **IP allowlist** | Single-region pilots, lower envs | Add Databricks workspace NAT IPs to Atlas Network Access. NAT IPs change if you don't pin them. |
| **VPC peering** | Same cloud, same region | Cleanest path; no public traversal. Set up Atlas → AWS VPC peer to your Databricks VPC. |
| **PrivateLink (AWS) / Private Endpoint (Azure)** | Production, cross-account | Atlas exposes a PrivateLink endpoint; Databricks workspace VPC creates an endpoint to it. Atlas connection string becomes `mongodb+srv://...privatelink-srv.mongodb.net`. |
| **Cross-cloud (e.g., Atlas-AWS → Databricks-Azure)** | Multi-cloud | Public endpoint with IP allowlist + TLS; ensure egress through a stable NAT. |

### Init scripts for connector preconfiguration
For repeated cluster deployments, put connector config in a cluster init script:

```bash
cat > /databricks/driver/conf/00-mongo.conf <<EOF
spark.mongodb.connection.uri {{secrets/atlas/connection_uri}}
spark.mongodb.read.partitioner com.mongodb.spark.sql.connector.read.partitioner.AutoBucketPartitioner
spark.mongodb.read.partitioner.options.partition.size 64
EOF
```

Databricks resolves `{{secrets/...}}` placeholders at cluster start, keeping the secret out of the file system.

### Delta Lake + MongoDB pattern (bronze/silver/gold)
A common Databricks pattern for Mongo CDC:

```
MongoDB → readStream (change stream) → Delta bronze (raw events) 
        → silver (deduplicated, schema-enforced) 
        → gold (aggregated, served to BI)
```

```python
# Bronze: raw change events with full document
bronze_query = (spark.readStream
    .format("mongodb")
    .option("connection.uri", uri)
    .option("database", "sales")
    .option("collection", "orders")
    .option("change.stream.publish.full.document.only", "true")
    .schema(orders_schema)
    .load()
    .writeStream
    .format("delta")
    .option("checkpointLocation", "s3://lake/_checkpoints/orders_bronze")
    .outputMode("append")
    .table("bronze.orders"))
```

### Delta Live Tables (DLT) — when to use
DLT manages the orchestration, retries, and dependency graph between bronze/silver/gold tables. For MongoDB sources, DLT does **not** have a native MongoDB streaming source — you wrap the connector inside a `@dlt.table` definition that reads from MongoDB and yields to a Delta table. The Kafka + DLT path (MongoDB → Kafka Source Connector → Confluent → DLT) is often used instead for production CDC because it gives stronger backpressure and replay semantics than the direct Spark Connector path.

---

## 11. Spark Connector vs alternatives

When MongoDB and Databricks (or Spark) both appear in a design, the right tool depends on latency, transformation complexity, and operational tolerance.

### Spark Connector (direct)
**Best for:** ad-hoc batch reads, ML feature extraction from Mongo, simple CDC into Delta where exactly-once isn't required, joining Mongo with other Spark sources, ETL where the transform logic lives in PySpark/Scala.

**Trade-offs:** the connector reads via standard Mongo queries. High-volume change streams can stress the source cluster (cursor overhead, oplog reads). Resume token loss means data loss without snapshot recovery logic.

### Kafka Source Connector + Spark
**Best for:** production CDC, multi-consumer fan-out (Spark + Snowflake + downstream apps), strict ordering guarantees, replay semantics, decoupling source-cluster availability from Spark job uptime.

**Trade-offs:** added infrastructure (Kafka cluster + Connect workers). Higher operational complexity.

### Atlas Data Federation
**Best for:** federated queries across multiple Atlas clusters + S3 + Azure Blob, SQL-based analytics, low-volume ad-hoc analysis. Use `$out` to S3 to materialize results.

**Trade-offs:** not a streaming source. Query-time only; no incremental processing. Charges per-TB scanned.

### Atlas Stream Processing
**Best for:** simple stream transformations entirely inside MongoDB (windowed aggregations, enrichment, filtering) where the result lands back in MongoDB or an external sink (Kafka, S3).

**Trade-offs:** newer offering. Less mature than Spark Structured Streaming for complex transforms. No native Delta sink.

### Decision matrix
Legend: ✓ = fit, ✗ = poor fit, △ = conditional (depends on configuration or scale).

| Need | Spark Connector | Kafka Connect | Data Federation | Stream Processing |
| --- | --- | --- | --- | --- |
| Ad-hoc analytics | ✓ | ✗ (overkill) | ✓ (SQL) | ✗ |
| Production CDC | △ (low/medium volume) | ✓ | ✗ | △ (simple transforms) |
| Cross-cluster joins | ✗ | △ (via topic join) | ✓ | ✗ |
| Sub-second latency | ✗ (micro-batch) | ✓ | ✗ | ✓ |
| ML feature engineering in Spark | ✓ | △ (via Spark consumer) | △ (read-only) | ✗ |
| Strict exactly-once | ✗ (at-least-once) | ✓ (with idempotent sink) | n/a | △ (depends on sink) |
| Operational simplicity | ✓ (one connector) | ✗ (Kafka cluster + Connect) | ✓ | ✓ |

---

## 12. Common error patterns

### `scala.MatchError: com.mongodb.spark.sql.connector.schema.InferSchema`
**Cause:** mixed types in the sample (e.g., a field is `Date` in some docs and `String` in others), or a nested document with inconsistent shapes.
**Fix:** supply an explicit `StructType` schema. If you must keep inference, prepend an `aggregation.pipeline` that normalizes the offending field with `$convert` or `$dateFromString`.

### `Unrecognized pipeline stage name: '$sample'`
**Cause:** older mongod (3.0 / 3.2) doesn't support `$sample`, used by `SamplePartitioner` and `AutoBucketPartitioner`.
**Fix:** upgrade the server (recommended) or switch to `PaginateBySizePartitioner`.

### Driver killed / OOM during schema inference
**Cause:** schema inference materializes the sample into a `Document` array on the driver. With `inferSchema.sampleSize=100000` and 1MB documents, that's 100GB on the driver.
**Fix:** lower `sampleSize`, supply explicit schema, or increase driver memory.

### `ChangeStreamHistoryLost`
**Cause:** the resume token is older than the oplog window.
**Fix:** extend Atlas oplog retention; fall back to `change.stream.startup.mode=latest` and re-snapshot to backfill.

### Slow reads despite pushdown
**Cause:** partition skew (one partition pulling 80% of the data), missing index for the filter predicate, or pipeline stage forcing collection scan.
**Fix:** check Spark UI for task duration variance; run `db.collection.explain()` with the connector-generated aggregation pipeline; add a matching index.

### `IllegalAccessError: tried to access class com.mongodb.internal.connection.Cluster`
**Cause:** two different `mongodb-driver-sync` versions on the classpath (the connector's shaded copy and another library's unshaded copy).
**Fix:** use the shaded uber-jar of `mongo-spark-connector`, pin a single driver version, or relocate one of the conflicting libraries.

### `collStats command failed`
**Cause:** running against AWS DocumentDB (Mongo-compatible but doesn't support `collStats`).
**Fix:** switch to a partitioner that doesn't call `collStats` — `SamplePartitioner` is usually safe; explicitly set `partitioner=com.mongodb.spark.sql.connector.read.partitioner.SinglePartitionPartitioner` as a no-partitioning fallback.

### Streaming write duplicates
**Cause:** at-least-once semantics + non-idempotent sink (`operationType=insert` or no `idFieldList`).
**Fix:** switch to `operationType=update` or `replace` with a stable `idFieldList` that covers a unique business key.

### `NoClassDefFoundError: scala/Product$class`
**Cause:** Scala 2.12 vs 2.13 mismatch between the connector artifact and the Spark/Databricks runtime.
**Fix:** match the `_2.12` or `_2.13` suffix to the runtime.

---

## 13. Performance tuning checklist

Apply in order:

1. **Pre-filter at the source.** A `$match` stage in `aggregation.pipeline` is usually 10x more impactful than any tuning knob.
2. **Supply explicit schema.** Saves 30–120s on startup; eliminates type drift surprises.
3. **Choose the right partitioner.** `AutoBucketPartitioner` for most workloads; `SamplePartitioner` for single-indexed-field reads; size partitions at 32–128MB.
4. **Index the read filters and `idFieldList`.** Index choice on the source side dominates connector tuning.
5. **Tune connection pool.** Set `maxPoolSize` on the connection URI (default 100) — too small and executors block; too large and Atlas hits its connection limit. Rule of thumb: `min(num_executors × cores_per_executor, 80% of Atlas-tier connection limit)`. Atlas connection limits are tier-based (M10: 1500, M30: 3000, M40: 6000, M60+: 18000–32000); check the cluster's "Connection Limits" page for the exact value.
6. **Match Spark partition count to MongoDB parallelism.** Reads from a 3-shard cluster benefit from `partition.count = 3 × N`. From a 3-node replica set with secondary reads enabled, target `partition.count = 2 × N` (primary + 1 secondary read).
7. **Use secondary reads for analytics.** Add `readPreference=secondary` to the URI for read-heavy reporting workloads; never for writes.
8. **`maxBatchSize` for writes.** Default 512. Drop to 100 for documents >256KB; raise to 1024 for tiny documents.
9. **`writeConcern=1`** for fast loads where downstream replay handles durability; `majority` for transactional sinks.
10. **Monitor with Spark UI + Atlas metrics simultaneously.** Spark stage time + Atlas ops/sec + connection count + ticket queue depth — the bottleneck is usually visible in one of these.

---

## 14. Migration: V2.x → V10.x

The two namespaces coexist, so migrate one job at a time.

| V2 (`com.mongodb.spark.sql.DefaultSource`) | V10 (`com.mongodb.spark.sql.connector.MongoTableProvider`) |
| --- | --- |
| `.format("com.mongodb.spark.sql.DefaultSource")` | `.format("mongodb")` |
| `spark.mongodb.input.uri` | `spark.mongodb.connection.uri` + `spark.mongodb.read.database` + `spark.mongodb.read.collection` |
| `spark.mongodb.output.uri` | `spark.mongodb.write.connection.uri` (or shared `connection.uri`) |
| `spark.mongodb.input.partitioner=MongoSamplePartitioner` | `spark.mongodb.read.partitioner=com.mongodb.spark.sql.connector.read.partitioner.SamplePartitioner` (FQCN required) |
| `spark.mongodb.input.partitionerOptions.partitionSizeMB=64` | `spark.mongodb.read.partitioner.options.partition.size=64` |
| `replaceDocument=true` | `operationType=replace` |
| `replaceDocument=false` | `operationType=update` |
| Streaming via custom workaround | Native `spark.readStream.format("mongodb")` |

Migration steps:
1. Add the V10 artifact alongside V2 (different package, no conflict).
2. Rewrite one job to V10 + add a parallel verification step (count + sample equality).
3. Promote when verified; remove V2 dependency once all jobs are migrated.

---

## 15. Authoritative references

Bookmark these. The connector evolves rapidly — always check the version-specific docs.

- **Official docs (current):** https://www.mongodb.com/docs/spark-connector/current/
- **V10.x docs:** https://www.mongodb.com/docs/spark-connector/v10.x/
- **Release notes:** https://www.mongodb.com/docs/spark-connector/current/release-notes/
- **GitHub source:** https://github.com/mongodb/mongo-spark
- **Batch read config:** https://www.mongodb.com/docs/spark-connector/current/batch-mode/batch-read-config/
- **Batch write config:** https://www.mongodb.com/docs/spark-connector/current/batch-mode/batch-write-config/
- **Streaming read config:** https://www.mongodb.com/docs/spark-connector/current/streaming-mode/streaming-read-config/
- **Streaming write config:** https://www.mongodb.com/docs/spark-connector/current/streaming-mode/streaming-write-config/
- **FAQ / troubleshooting:** https://www.mongodb.com/docs/spark-connector/current/faq/
- **MongoDB + Databricks partner page:** https://www.mongodb.com/company/partners/databricks
- **Databricks structured streaming checkpoints:** https://docs.databricks.com/aws/en/structured-streaming/checkpoints
- **Spark Structured Streaming guide:** https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html

## Related skills

- `mongodb-change-streams` — change-stream semantics, oplog window, resume tokens (the source side of streaming reads)
- `mongodb-aggregation-pipeline` — pipeline stages used in `aggregation.pipeline` and pushdown
- `mongodb-atlas-data-federation` — alternative to Spark Connector for federated queries
- `mongodb-migration-patterns` — ETL/CDC migration patterns including Spark/Kafka choices
- `mongodb-kafka-connector` — Kafka Connect-based alternative for CDC pipelines
- `mongodb-indexes-deep` — indexing the read filters and `idFieldList` for write performance
- `mongodb-sharding` — `ShardedPartitioner` and shard-aware partitioning
- `mongodb-atlas-iac` / `mongodb-atlas-terraform` — provisioning the Atlas cluster, network peering, secrets infrastructure
