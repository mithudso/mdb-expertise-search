<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-stream-processing` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-stream-processing
category: mongodb
tags: [mongodb, atlas, stream-processing, kafka, change-streams, windowing, real-time]
version: 1.3.0
updated: 2026-05-29
audience: Atlas practitioners adding real-time stream processing to an existing Atlas project
description: "MongoDB Atlas Stream Processing (ASP) — fully managed, Atlas-native stream processing engine. TRIGGER when the request involves creating or debugging ASP stream processors, $source/$emit stages, tumbling/hopping/session windows, SPI tier selection, connection registry setup (Kafka + Atlas connections), DLQ and $validate configuration, watermarks and late-event handling, ASP monitoring and consumer lag, or choosing ASP vs Kafka Connector vs Flink for a streaming workload. SKIP for batch re-processing of historical datasets (use scheduled aggregation pipelines or Atlas Data Federation), Kafka Connect configuration without ASP involvement (use mongodb-kafka-connector), or MongoDB Spark Connector streaming (use mongodb-spark-connector)."
when_to_use:
  - Designing or implementing a real-time stream processing pipeline in Atlas
  - Debugging a stream processor — consumer lag, DLQ growth, validation failures
  - Choosing between ASP, Kafka Connector, and Flink for a new streaming workload
  - Writing $source/$emit pipeline syntax for Kafka or Atlas change stream sources
  - Configuring tumbling, hopping, or session windows for time-series analytics
  - Setting up connection registry entries for Kafka clusters or Atlas clusters
  - Sizing SPI tiers (SP2/SP5/SP10/SP30/SP50) for a target throughput
  - Monitoring ASP via stats(), consumerLag, and Atlas UI metrics
  - Near-real-time materialized views via continuous $emit to an Atlas collection
  - Configuring DLQ and $validate for schema enforcement in streaming pipelines
when_not_to_use:
  - Batch re-processing of finite historical datasets — use scheduled Atlas Aggregation Pipelines or Atlas Data Federation
  - Kafka Connect-only pipelines with no ASP involvement — use mongodb-kafka-connector
  - Spark Structured Streaming from MongoDB — use mongodb-spark-connector
  - Complex stateful ML inference or graph processing requiring Flink — ASP does not have a native Flink sink
  - On-premises or self-managed stream processing infrastructure — ASP is Atlas-only
related_skills:
  - mongodb-kafka-connector
  - mongodb-change-streams
  - mongodb-spark-connector
  - mongodb-atlas-triggers-functions
  - mongodb-cdc-architecture
  - mongodb-time-series
  - mongodb-views-materialized-views
  - mongodb-atlas-iac
  - mongodb-atlas-terraform
---

# MongoDB Atlas Stream Processing

## Scope

This reference covers Atlas Stream Processing (ASP) from architecture through operations. After reading it you will be able to:

- Choose the right SPI tier and window type for a workload
- Write complete `$source → pipeline → $emit` processors
- Configure connections, DLQ, and monitoring
- Recognize and avoid the seven most common anti-patterns

**Intended audience:** MongoDB Atlas users (developers, data engineers, solution architects) who have an existing Atlas project and want to add real-time stream processing without operating separate Kafka Streams or Flink infrastructure.

---

## 1. Overview

MongoDB Atlas Stream Processing (ASP) is a fully managed, cloud-native stream processing engine built directly into the Atlas developer data platform. It lets you define, run, and monitor continuous aggregation pipelines on streaming data — Kafka topics, Atlas change streams, or synthetic sample feeds — without provisioning or operating a separate cluster of stream-processing infrastructure.

**GA date:** Generally available since May 2, 2024, following a public preview that launched in late 2023.

**Positioning vs. alternatives:**

| Capability | Atlas Stream Processing | Apache Kafka Streams | Apache Flink |
|---|---|---|---|
| Ops model | Fully managed, zero infra | Self-hosted or Confluent Cloud | Self-hosted or managed (Kinesis DA, Confluent) |
| Query language | MongoDB Aggregation Pipeline (MQL) | Java/Kotlin DSL | Java/Python/SQL |
| State store | Managed, serverless | Local RocksDB | Managed checkpoints |
| Sink options | Atlas collection, Kafka | Kafka topics, KTable | Kafka, JDBC, custom |
| Prerequisite skill | MQL / Atlas knowledge | JVM + Kafka APIs | JVM + Flink APIs |
| Change stream native | Yes (first-class) | No | Connector needed |
| Schema validation | Built-in `$validate` | KStream serdes | Flink Table API |

**When to choose ASP:** Your team already uses Atlas and wants to avoid operating JVM-based stream processing infrastructure; workloads can be expressed as aggregation pipelines.

**When ASP is not the right fit:** Stateful machine-learning inference, complex graph processing, or workloads requiring durable message queuing belong with Flink or Kafka respectively. ASP is also not suitable for batch re-processing of finite historical datasets — use scheduled Atlas Aggregation Pipelines or Atlas Data Federation for that.

---

## 2. Stream Processor Architecture

### Stream Processing Instance (SPI)

A **Stream Processing Instance** is the compute unit that hosts one or more stream processors. You create an SPI in a chosen Atlas project and region; it is separate from your Atlas database clusters. Each SPI belongs to one Atlas project and one cloud region.

SPI tiers (as of late 2025):

| Tier | Use case |
|---|---|
| SP2 / SP5 | Development and light workloads |
| SP10 / SP30 | Moderate to intensive processing |
| SP50 | High-traffic, resource-intensive operations |

SP10 and SP30 originally used a legacy per-worker billing model; they migrated to per-processor pricing in December 2025. Workspaces (introduced mid-2025) group processors under a single SPI for easier management.

**Note on regional availability:** ASP is available in a subset of Atlas regions. Verify availability for your target region at `mongodb.com/docs/atlas/atlas-stream-processing/` before designing a multi-region architecture.

### Delivery Semantics

| Scenario | Guarantee | Condition |
|---|---|---|
| Kafka → Atlas collection | At-least-once | Default |
| Kafka → Kafka | Exactly-once | Kafka idempotent producer enabled on the connection + `acks=all` |
| Change stream → Atlas | At-least-once | Resume token persisted via checkpoint |

### Stream Processor

A **stream processor** is a named, persistent pipeline that runs continuously inside an SPI. It is composed of:

1. A **`$source`** stage — reads from a Kafka topic, Atlas change stream, or synthetic feed.
2. One or more **processing stages** — standard aggregation operators (`$match`, `$project`, `$addFields`, `$lookup`, `$group`, windowing operators, `$validate`, etc.).
3. A **`$emit`** sink stage — writes results to a Kafka topic or Atlas collection.

Processors are stateful and checkpoint their progress so they can resume after failure.

### Regions and Connectivity

SPIs are created in a single Atlas-supported region. Kafka clusters must be reachable from that region; private endpoints, VPC peering, or public internet (TLS required) are all supported. Atlas connections in the connection registry reference Atlas clusters in any region.

---

## 3. `$source` Operators

The `$source` stage is always the first stage in a stream processor. Only one `$source` is allowed per processor.

### Kafka Source

```javascript
{
  $source: {
    connectionName: "myKafkaConnection",
    topic: "sensor-events",
    config: {
      "auto.offset.reset": "earliest"
    },
    tsFieldName: "eventTimestamp"   // map Kafka record timestamp to a document field
  }
}
```

- `connectionName` references a Kafka entry in the connection registry.
- `topic` is the Kafka topic name (wildcards and topic lists are supported).
- `tsFieldName` controls which document field becomes the event-time timestamp used by windowing operators. If omitted, ASP uses the Kafka record timestamp.
- Pass raw Kafka consumer config under `config`.

### Atlas Change Stream Source

```javascript
{
  $source: {
    connectionName: "myAtlasConnection",
    db: "iot",
    coll: "readings",
    config: {
      fullDocument: "updateLookup"
    }
  }
}
```

Watches the given collection for insert/update/replace/delete events. The `fullDocument` option mirrors the MongoDB change stream `fullDocument` setting. The processor automatically resumes from the last resume token after restarts.

### Sample Data Source

A synthetic source for development and testing that emits pre-built documents at a configurable rate. Useful for trying out pipeline logic before wiring up real Kafka topics.

```javascript
{ $source: { connectionName: "$sampleData" } }
```

**Note:** The Atlas Database is not a standalone `$source` type. To join stream events with static Atlas data, use `$lookup` with an Atlas connection (see Section 6).

---

## 4. `$emit` Operators (Sink Stages)

The `$emit` stage is always the last stage. It defines where processed documents are written.

### Emit to Kafka Topic

```javascript
{
  $emit: {
    connectionName: "myKafkaConnection",
    topic: "processed-alerts",
    config: {
      "acks": "all"
    }
  }
}
```

Documents emitted to Kafka are serialized as JSON. Kafka producer config (acks, compression, etc.) can be passed under `config`.

### Emit to Atlas Collection (standard)

```javascript
{
  $emit: {
    connectionName: "myAtlasConnection",
    db: "analytics",
    coll: "aggregated_metrics"
  }
}
```

### Emit to Atlas Time Series Collection

```javascript
{
  $emit: {
    connectionName: "myAtlasConnection",
    db: "analytics",
    coll: "sensor_ts",
    timeseries: {
      timeField: "windowEnd",
      metaField: "sensorId",
      granularity: "minutes"
    }
  }
}
```

When `timeseries` is specified, Atlas creates the time series collection automatically if it does not exist.

### Emit with Upsert Semantics

ASP's `$emit` stage performs inserts by default. To maintain rolling aggregation documents (e.g., a per-device "latest state" record), the recommended pattern is to emit to a Kafka topic and use a downstream Kafka Connect sink with upsert mode, or to emit to an Atlas collection and rely on a separate trigger/aggregation for deduplication.

The ASP changelog (`mongodb.com/docs/atlas/atlas-stream-processing/changelog/`) tracks native upsert support additions — verify the current capability against your Atlas version before implementing.

---

## 5. Windowing

Streaming aggregations require finite, time-bounded subsets of the stream. ASP provides three window types. Use this decision guide:

| Situation | Window type |
|---|---|
| Fixed time buckets, no overlap (e.g., per-minute stats) | `$tumblingWindow` |
| Sliding/moving aggregation (e.g., 5-min rolling average, updated every 1 min) | `$hoppingWindow` |
| Natural activity sessions separated by inactivity gaps | `$sessionWindow` |

### Tumbling Windows (`$tumblingWindow`)

Non-overlapping, fixed-size time buckets. Every document belongs to exactly one window.

```javascript
{
  $tumblingWindow: {
    interval: { size: 1, unit: "minute" },
    pipeline: [
      { $group: {
          _id: "$sensorId",
          avgTemp: { $avg: "$temperature" },
          maxTemp: { $max: "$temperature" }
      }}
    ]
  }
}
```

### Hopping Windows (`$hoppingWindow`)

Fixed-size windows that advance by a step smaller than the window size, creating overlapping windows.

```javascript
{
  $hoppingWindow: {
    interval: { size: 5, unit: "minute" },
    hopSize:  { size: 1, unit: "minute" },
    pipeline: [
      { $group: { _id: "$deviceId", count: { $sum: 1 } } }
    ]
  }
}
```

A document within the 5-minute window appears in five successive 1-minute hops. Use for moving averages and rolling counts.

### Session Windows (`$sessionWindow`)

Groups documents into sessions based on activity gaps. A session closes when no new document with the same partition key arrives within the gap duration.

```javascript
{
  $sessionWindow: {
    gap: { size: 30, unit: "second" },
    partitionBy: "$userId",
    pipeline: [
      { $group: {
          _id: "$userId",
          eventCount: { $sum: 1 },
          sessionStart: { $min: "$eventTimestamp" },
          sessionEnd:   { $max: "$eventTimestamp" }
      }}
    ]
  }
}
```

Ideal for user-session analytics, machine-activity tracking, or any event stream where "silence" defines a natural boundary. **Caution:** session windows create variable-length state that is harder to bound memory-wise than tumbling or hopping windows. Prefer tumbling/hopping for regular time-series data (fixed-interval sensor readings).

### Watermarks and Late-Event Tolerance

Watermarks tell ASP how long to wait for late-arriving events before closing a window. Always configure `lateTolerance`; the default may be too tight for your source.

**Setting `lateTolerance`** — pass it as a processor option at creation time:

```javascript
sp.createStreamProcessor(
  "myProc",
  [
    { $source: { connectionName: "myKafkaConnection", topic: "events", tsFieldName: "ts" } },
    { $tumblingWindow: { interval: { size: 1, unit: "minute" }, pipeline: [...] } },
    { $emit: { connectionName: "myAtlasConnection", db: "out", coll: "results" } }
  ],
  {
    dlq: { connectionName: "myKafkaConnection", topic: "asp-dlq" },
    // Late-event tolerance: wait up to 10 seconds beyond the window end for straggler events
    lateTolerance: { size: 10, unit: "second" }
  }
)
```

**Rule of thumb:** measure your stream's maximum event-time skew under load and set `lateTolerance` to at least 2× that value. Events arriving after the watermark advances are routed to the DLQ if one is configured, or silently dropped if not.

---

## 6. Aggregation in Streams

ASP supports the majority of MongoDB aggregation pipeline operators inside window pipelines and between `$source` and `$emit` stages.

### `$match` — filter events early

```javascript
{ $match: { "payload.severity": { $gte: 3 } } }
```

Place `$match` immediately after `$source` to reduce the document volume before windowing or lookup.

### `$project` / `$addFields` — reshape documents

```javascript
{
  $addFields: {
    celsius: { $subtract: [ { $multiply: ["$fahrenheit", 0.5556] }, 17.78 ] },
    ingestedAt: "$$NOW"
  }
}
```

### `$group` — aggregate within windows

```javascript
{
  $group: {
    _id: { sensorId: "$sensorId", region: "$region" },
    readings: { $sum: 1 },
    p95Latency: { $percentile: { input: "$latencyMs", p: [0.95], method: "approximate" } }
  }
}
```

### `$lookup` — enrich stream events with reference data

```javascript
{
  $lookup: {
    from:         { connectionName: "myAtlasConnection", db: "ref", coll: "devices" },
    localField:   "deviceId",
    foreignField: "_id",
    as:           "deviceInfo"
  }
}
```

`$lookup` against Atlas is a remote call on every document. On a 10,000 msg/sec stream a 5ms round-trip becomes the pipeline bottleneck. Keep reference collections small, index the foreign key, and prefer low-cardinality join keys.

### `$validate` — schema enforcement

`$validate` checks that documents conform to a JSON schema and routes non-conforming documents to the DLQ (or halts the processor). It is a pipeline stage; DLQ routing is configured at the processor level, not inside the stage.

```javascript
// Pipeline stage — validates shape and types
{
  $validate: {
    validator: {
      $jsonSchema: {
        required: ["deviceId", "temperature", "ts"],
        properties: {
          temperature: { bsonType: "double", minimum: -100, maximum: 200 }
        }
      }
    },
    validationAction: "warn"   // "warn": route failures to DLQ and continue
                               // "error": halt the processor on first failure
  }
}
```

The DLQ destination is configured at processor creation (see Section 8), not inside `$validate`.

### Time-based sub-bucketing inside windows

Windows provide the outer time boundary. For finer buckets within a window use `$dateTrunc`:

```javascript
{
  $group: {
    _id: {
      minute: { $dateTrunc: { date: "$ts", unit: "minute" } },
      sensor: "$sensorId"
    },
    avg: { $avg: "$value" }
  }
}
```

---

## 7. Connection Registry

Before creating stream processors, register connections in the SPI's connection registry via the Atlas UI, Atlas CLI, or Terraform. Connections are named and reusable across multiple processors.

### Kafka Cluster Connection (Atlas CLI)

Via Atlas CLI (verify exact flags against your installed version with `atlas streams connections create --help`):

```bash
atlas streams connections create \
  --instance mySPI \
  --type Kafka \
  --bootstrapServers broker1:9092,broker2:9092 \
  --authMechanism PLAIN \
  --username <user> \
  --password <pass> \
  --securityProtocol SASL_SSL \
  --name myKafkaConnection
```

Supported security protocols: `PLAINTEXT`, `SSL`, `SASL_SSL`.
- Confluent Cloud: `SASL_SSL` + `PLAIN`
- Amazon MSK with IAM: `SASL_SSL` + custom config block per MSK IAM auth

See also: [Atlas CLI streams connections reference](https://www.mongodb.com/docs/atlas/cli/stable/command/atlas-streams-connections-create/)

### Atlas Connection (Atlas CLI)

```bash
atlas streams connections create \
  --instance mySPI \
  --type Atlas \
  --cluster Cluster0 \
  --name myAtlasConnection
```

Atlas connections authenticate with an Atlas database user whose credentials are stored securely in the SPI. No connection string is exposed in the pipeline definition.

### Terraform Support

Atlas Stream Processing instances and connections can be managed via the MongoDB Atlas Terraform provider (`mongodbatlas_stream_instance`, `mongodbatlas_stream_connection`), enabling IaC workflows.

### Listing and Deleting Connections (mongosh)

```javascript
sp.connections.list()
sp.connections.delete("myConnectionName")  // only succeeds if no processor is using it
```

---

## 8. Error Handling

### Dead Letter Queue (DLQ)

A DLQ is a Kafka topic or Atlas collection where ASP routes documents that fail validation, deserialization, or emit. Configure it when creating the processor:

```javascript
sp.createStreamProcessor(
  "myProc",
  pipeline,
  {
    dlq: {
      connectionName: "myKafkaConnection",
      topic: "asp-dlq"
    }
  }
)
```

Each DLQ record includes:
- `originalDocument` — the document that failed
- `errorMessage` — human-readable failure reason
- `errorCode` — numeric ASP error code
- `processorName`, `timestamp`

### `$validate` + DLQ integration

When `$validate` uses `validationAction: "warn"`, non-conforming documents are silently routed to the DLQ and processing continues. Use `validationAction: "error"` only in development (it halts the processor on the first failure).

### Sampling for debugging

```javascript
// Non-persistent interactive run — results (and any DLQ hits) display inline
sp.process(pipeline)

// Sample up to 25 live documents from a running persistent processor
sp.processor("myProc").sample()
```

`sp.process()` surfaces DLQ messages inline during development, making it easy to catch schema errors before deploying a persistent processor.

### Checkpoint and Recovery

ASP saves processor state periodically. On restart (manual or after a fault), the processor resumes from the last checkpoint — committing Kafka offsets for Kafka sources, persisting the resume token for change stream sources. Checkpoint frequency is managed by Atlas and is not user-configurable.

---

## 9. Monitoring Stream Processors

### Atlas UI Monitoring Tab

Navigate to **Atlas > Stream Processing > [your SPI] > Monitoring** to view:

- Throughput (messages/sec in and out)
- Consumer lag (for Kafka sources — how far behind the processor is from the latest offset)
- Error rate (messages routed to DLQ per second)
- CPU and memory utilization of the SPI

### `stats()` — mongosh / Atlas CLI

```javascript
sp.processor("myProcessor").stats()
```

Returns a document like:

```json
{
  "name": "myProcessor",
  "status": "running",
  "inputMessageCount": 4820341,
  "outputMessageCount": 47921,
  "dlqMessageCount": 12,
  "inputThroughput": 1234.5,
  "outputThroughput": 12.1,
  "consumerLag": 0,
  "lastCheckpointTime": "2025-11-10T14:22:00Z"
}
```

Key metrics to watch:

| Metric | Healthy value | Action if unhealthy |
|---|---|---|
| `consumerLag` | Near 0 | Scale SPI tier up; optimize pipeline (add early `$match`) |
| `dlqMessageCount` growing | 0 | Inspect DLQ records; check for upstream schema drift |
| `inputThroughput` drops to 0 | Stable | Check Kafka connectivity; verify connection registry entry |
| `outputThroughput` << `inputThroughput` | Proportional to filter selectivity | Expected with aggressive filtering; verify `$match` is intentional |

### Alerting

Atlas Alerts can be configured on stream processor metrics (lag, error rate) via the Atlas UI or the Atlas Admin API. Supported notification channels: PagerDuty, Slack, email, webhook.

**Always alert on `dlqMessageCount` growth.** Schema drift in upstream Kafka topics will silently route an increasing share of messages to the DLQ while throughput metrics look healthy.

---

## 10. Pricing Model

Atlas Stream Processing uses a **per-processor pricing model** (migrated from a legacy per-worker model in December 2025).

### Compute (per-processor-hour)

You pay per stream processor-hour at a rate determined by the SPI tier. Smaller tiers (SP2/SP5) cost less per hour; larger tiers (SP50) cost more but handle higher throughput.

MongoDB does not publish fixed dollar rates in documentation — prices vary by region and contract. Use the Atlas pricing calculator at `mongodb.com/pricing` for current figures.

### Data Transfer

- Connections themselves have no fixed cost.
- **Data egress** from Atlas (to Kafka or external Atlas clusters) is billed at standard Atlas egress rates by transfer type and destination region.
- Reads from Atlas change streams within the same Atlas project incur no additional egress charge.

### Storage

ASP does not charge separately for internal processing state storage (checkpoints, windowed state). Emitted data written to Atlas collections is billed under normal Atlas storage rates.

### Cost Optimization Tips

1. Use the smallest SPI tier that meets throughput requirements; scale up only when `consumerLag` grows.
2. Place `$match` as early as possible to reduce the documents that traverse the rest of the pipeline.
3. Prefer emitting to Atlas collections in the same region as the SPI to avoid cross-region egress.
4. Archive DLQ topics/collections on a schedule — DLQ storage is billed under normal Atlas/Kafka rates.

---

## 11. Common Use Cases

### IoT Event Processing

Ingest high-frequency sensor readings from Kafka. Apply a 1-minute tumbling window with `$group` to compute min/max/avg per device. Emit to an Atlas time series collection for Atlas Charts dashboards.

```
[Sensors] → [MQTT Broker] → [Kafka Connect] → [Kafka topic]
                                                     ↓
                                         [ASP: $source Kafka
                                               → $tumblingWindow / $group
                                               → $emit Atlas TS]
                                                     ↓
                                             [Atlas Charts]
```

### Real-Time Fraud Alerting

```
[Atlas change stream: orders]
  → $match { riskScore: { $gte: 0.85 } }
  → $lookup { coll: "customers" }      // enrich with account data
  → $emit Kafka topic "fraud_alerts"
  → [Notification service]
```

### Change Stream Enrichment and Fan-out

```
[Atlas change stream: transactions]
  → $addFields / $lookup               // enrich with account metadata
  → $emit Kafka topic "enriched_txns"  // intermediate topic
      ↓                  ↓               ↓
 [Audit proc]   [Analytics proc]   [Notification proc]
```

Splitting into an enrichment processor writing to an intermediate topic and separate consumer processors gives independent scaling and replay capability.

### Session Analytics

```
[Kafka topic: page_view]
  → $sessionWindow { gap: 30s, partitionBy: "$userId" }
  → $group { _id: "$userId", pageCount, sessionDuration }
  → $emit Atlas coll "user_sessions"
```

### Operational Data Tiering

```
[Atlas change stream: events (hot)]
  → $match / $project               // filter & trim fields for long-term retention
  → $emit Atlas time series coll    // automatic data tiering
```

---

## 12. Anti-Patterns

| Anti-pattern | Risk | Mitigation |
|---|---|---|
| Using ASP for batch workloads | SPI resources wasted; processor may time out | Use scheduled Atlas Aggregation Pipeline or Data Federation |
| Missing `lateTolerance` config | Late events silently dropped; incorrect window results | Set `lateTolerance` ≥ 2× measured max skew |
| Ignoring the DLQ | Schema drift causes silent data loss | Alert on `dlqMessageCount` growth; review DLQ after upstream schema changes |
| Expensive `$lookup` on high-throughput paths | `$lookup` is a synchronous network call; becomes bottleneck at high volume | Small reference collections + indexed foreign key; pre-join upstream via CDC |
| One giant processor | Hard to debug, scale, or replay partial failures | Split into filter/validate processor → intermediate Kafka topic → aggregate processor |
| Not pinning `auto.offset.reset` | Unpredictable behavior on first deploy or consumer group reset | Always set `"auto.offset.reset": "earliest"` or `"latest"` explicitly |
| Overusing session windows for time-series data | Variable-length state is hard to bound memory-wise | Use tumbling or hopping windows for fixed-interval data; reserve session windows for genuine activity-gap semantics |

---

## Quick Reference: mongosh Commands

```javascript
// Connect to your SPI
const sp = db.getSiblingDB("$streamProcessing").getStreamProcessingInstance("mySPI")

// List all processors
sp.listStreamProcessors()

// Create a persistent processor with DLQ and late-tolerance
sp.createStreamProcessor(
  "myProc",
  pipeline,
  {
    dlq: { connectionName: "kafka", topic: "asp-dlq" },
    lateTolerance: { size: 10, unit: "second" }
  }
)

// Start / stop / drop
sp.processor("myProc").start()
sp.processor("myProc").stop()
sp.processor("myProc").drop()

// Stats
sp.processor("myProc").stats()

// Interactive (non-persistent) run — results and DLQ hits display inline
sp.process(pipeline)

// Sample up to 25 docs from a running processor's output
sp.processor("myProc").sample()

// Connection registry
sp.connections.list()
sp.connections.delete("myConnectionName")
```

## Quick Reference: Atlas CLI Commands

```bash
# List stream processing instances
atlas streams instances list

# Create an instance
atlas streams instances create mySPI --provider AWS --region US_EAST_1 --tier SP10

# List processors
atlas streams processors list --instance mySPI

# Start / stop / delete a processor
atlas streams processors start  myProc --instance mySPI
atlas streams processors stop   myProc --instance mySPI
atlas streams processors delete myProc --instance mySPI

# Create a Kafka connection
atlas streams connections create \
  --instance mySPI --type Kafka \
  --bootstrapServers broker1:9092 \
  --authMechanism PLAIN --username u --password p \
  --securityProtocol SASL_SSL --name myKafkaConn

# Create an Atlas connection
atlas streams connections create \
  --instance mySPI --type Atlas \
  --cluster Cluster0 --name myAtlasConn

# List connections
atlas streams connections list --instance mySPI
```

---

## Key Documentation Links

- [Overview](https://www.mongodb.com/docs/atlas/atlas-stream-processing/overview/)
- [Get Started Tutorial](https://www.mongodb.com/docs/atlas/atlas-stream-processing/tutorial/)
- [Windows Reference](https://www.mongodb.com/docs/atlas/atlas-stream-processing/windows/)
- [Monitoring](https://www.mongodb.com/docs/atlas/atlas-stream-processing/monitoring/)
- [Billing](https://www.mongodb.com/docs/atlas/billing/stream-processing-costs/)
- [Changelog](https://www.mongodb.com/docs/atlas/atlas-stream-processing/changelog/)

---

## Atlas Stream Processing vs. MongoDB Kafka Connector

A dedicated comparison skill now exists: see **`mongodb-kafka-connector`** for the full Kafka Connector reference. Key decision summary:

| Dimension | Kafka Connector | Atlas Stream Processing |
|---|---|---|
| Deployment | Self-managed (Confluent Cloud / MSK Connect / self-hosted) | Fully managed, Atlas-native |
| Processing | SMTs + custom Java write strategies | Full MQL aggregation pipeline + windowing |
| Windowing | Not native (requires Kafka Streams/Flink) | Tumbling, hopping, session windows built-in |
| Cost model | Per task-hour on hosting provider | Per SPI-hour; ~25% of Kafka Connector cost (per MongoDB) |
| Best for | Existing Kafka ecosystems, multi-sink fan-out, Debezium CDC | Atlas-centric pipelines, MQL teams, simplified ops |

**When ASP is the better fit over the Kafka Connector:**
- Your team already uses Atlas and knows MQL but not JVM/Java
- You need native windowing or stateful aggregations
- You want a single managed service instead of operating Kafka Connect workers
- Cost efficiency on Atlas-to-Atlas or Atlas-to-Kafka pipelines is a priority

**When the Kafka Connector is the better fit:**
- You already have a Kafka Connect platform serving multiple source/sink systems
- You need Debezium CDC handlers for non-MongoDB sources (MySQL, Postgres, SQL Server)
- You need custom Java write model strategies or CDC handlers not available in ASP
- You require on-premises or self-managed Kafka infrastructure
