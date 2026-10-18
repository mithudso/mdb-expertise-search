<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-time-series` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-time-series
version: "1.1"
updated: "2026-05-29"
description: >
  MongoDB Time Series Collections expert — collection creation options (timeField, metaField,
  granularity, custom bucketing), columnar bucket internals (delta encoding, RLE, Zstd, block
  processing), secondary index constraints, TTL automatic deletion, aggregation pipeline
  optimization ($densify, $fill, $dateTrunc, $setWindowFields), Atlas Charts integration,
  change stream and trigger limitations with workarounds, migration from regular collections,
  performance benchmarks (70-90% compression, MongoDB 8.0 block processing), sharding patterns,
  and anti-patterns. Covers MongoDB 5.0 through 8.x on Atlas and self-managed.
  TRIGGER: creating a time series collection, choosing timeField/metaField/granularity,
  debugging slow queries on time series, designing secondary indexes for time series, configuring
  TTL on time series, writing $densify/$fill/$setWindowFields pipelines, implementing moving
  averages or gap-fill queries, migrating to time series, troubleshooting cache pressure from
  high metaField cardinality, planning time series sharding, or understanding MongoDB 8.0 block
  processing improvements.
  SKIP: general aggregation pipeline design, $lookup, $merge (use mongodb-aggregation-pipeline);
  manual bucket pattern for pre-5.0 or when transactions/change-streams are needed (use
  mongodb-schema-design); ESR compound index design on regular collections (use mongodb-indexes-deep);
  Atlas Charts general usage (use mongodb-atlas-charts); general IoT schema without time series
  collection type (use mongodb-schema-design).
when_to_use:
  - Creating or designing a MongoDB time series collection
  - Choosing timeField, metaField, granularity, or bucketMaxSpanSeconds settings
  - Debugging slow queries against time series collections
  - Designing secondary indexes for time series — understanding constraints (no unique, no text, no partial on measurement fields)
  - Configuring TTL and automatic data expiration for time series data
  - Writing aggregation pipelines with $densify, $fill, or $setWindowFields for time series analysis
  - Implementing moving averages, rolling sums, lag/lead analysis, or OHLCV bars
  - Migrating an existing regular collection to a time series collection
  - Troubleshooting high memory or WiredTiger cache pressure from time series workloads
  - Planning sharding for a time series collection at high ingestion rates
  - Understanding limitations — no transactions on writes, no unique indexes, no change streams
  - Sizing a cluster for IoT sensor, metrics, financial tick, or observability data
  - Comparing MongoDB 8.0 block processing improvements vs earlier versions
when_not_to_use:
  - General aggregation pipeline design, $lookup, $merge, $out to regular collections (use mongodb-aggregation-pipeline)
  - Manual bucket pattern decisions or IoT schema without native time series type (use mongodb-schema-design)
  - ESR compound index design, partial/sparse/wildcard indexes on regular collections (use mongodb-indexes-deep)
  - Atlas Charts general dashboard design not specific to time series (use mongodb-atlas-charts)
  - Change streams on time series data — not supported; design alternatives are in this skill
  - Atlas Stream Processing source configuration — time series cannot be a $source (use mongodb-atlas-stream-processing)
related_skills:
  - mongodb-schema-design
  - mongodb-aggregation-pipeline
  - mongodb-aggregation-stages-deep
  - mongodb-indexes-deep
  - mongodb-capacity-planning
  - mongodb-atlas-charts
  - mongodb-sharding
  - mongodb-data-lifecycle
  - mongodb-atlas-stream-processing
---

# MongoDB Time Series Collections

## Overview

MongoDB Time Series Collections, introduced in MongoDB 5.0 (GA), are a specialized collection type optimized for time-stamped measurement data. They use an internal columnar storage format with automatic bucketing, delta encoding, and Zstd compression to achieve 50-90% storage reduction over regular collections while dramatically improving query performance for time-range access patterns.

Time series collections are the preferred choice over the manual bucket pattern for IoT sensor data, server metrics, financial tick data, application events, observability signals, and any domain where data is appended in timestamp order and queried by time range.

> **Skill boundaries:**
> - Use this skill (`mongodb-time-series`) for: collection creation options, bucket internals, TTL, time-series-specific index constraints, $densify/$fill/$dateTrunc/$setWindowFields in a time-series context, Atlas triggers/change-stream limitations, migration, sharding for time series, and performance sizing.
> - Use `mongodb-aggregation-pipeline` for: general pipeline stage design, $lookup, $merge/$out to regular collections, explain profiling, memory/allowDiskUse tuning.
> - Use `mongodb-schema-design` for: the manual bucket pattern, embedding vs referencing decisions, general IoT schema modeling without the native time series collection type.
> - Use `mongodb-indexes-deep` for: ESR compound index design, partial/sparse/wildcard/text index types on regular collections.

**Version timeline:**
- MongoDB 5.0: Initial release (create, insert, query, TTL, basic indexing)
- MongoDB 5.1: $densify aggregation stage
- MongoDB 5.2: Columnar compression format (major storage improvement)
- MongoDB 5.3: $fill aggregation stage
- MongoDB 6.0: partial index support with $or/$in/$geoWithin
- MongoDB 6.3: Custom bucketing parameters (`bucketMaxSpanSeconds`, `bucketRoundingSeconds`)
- MongoDB 7.0: $out can write to time series collections; TTL partial filter on metaField
- MongoDB 8.0: Block processing — direct write into column-compressed format (2-3x throughput, 10-20x cache reduction); timeField shard key deprecated
- MongoDB 8.3: timeField cannot start with `$`; creating `"_id_"` index returns error
- Atlas (2023+): Atlas Stream Processing introduced — time series collections can be a *sink* but not a `$source` (no change stream support)

**Sources:**
- [MongoDB Time Series Documentation](https://www.mongodb.com/docs/manual/core/timeseries-collections/)
- [MongoDB 8.0 Block Processing Blog](https://www.mongodb.com/company/blog/technical/key-enhancements-mongodb-8-0-block-processing)
- [Columnar Storage Cost Savings Blog](https://www.mongodb.com/company/blog/technical/columnar-storage-time-series-collection-cost-savings)

---

## Core Concepts

### 1. Collection Creation and Configuration

Time series collections are created with `db.createCollection()` using a `timeseries` subdocument. The `timeField` is the only required parameter; all others are optional but significantly affect performance.

```javascript
db.createCollection("sensor_readings", {
  timeseries: {
    timeField: "timestamp",        // REQUIRED: must be a Date field
    metaField: "metadata",         // OPTIONAL but strongly recommended
    granularity: "seconds",        // "seconds" | "minutes" | "hours"
    // MongoDB 6.3+: custom bucketing (overrides granularity)
    bucketMaxSpanSeconds: 3600,
    bucketRoundingSeconds: 3600,
    // MongoDB 5.0+: automatic TTL
    expireAfterSeconds: 2592000    // 30 days
  }
})
```

**Parameter reference:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `timeField` | string | Yes | Field holding the measurement timestamp (Date type). Immutable after creation. |
| `metaField` | string | No | Field holding device/source identity. Drives bucketing. Immutable after creation. |
| `granularity` | string | No | Controls max bucket time span. Default: `"seconds"`. |
| `bucketMaxSpanSeconds` | integer | No | Custom bucket time window (MongoDB 6.3+). Must equal `bucketRoundingSeconds`. |
| `bucketRoundingSeconds` | integer | No | Rounds bucket start times to interval boundaries (MongoDB 6.3+). |
| `expireAfterSeconds` | integer | No | TTL: remove buckets where all measurements are older than N seconds. |

**Granularity and bucket time spans:**

| Granularity | Default Max Bucket Span |
|-------------|------------------------|
| `seconds` | 1 hour |
| `minutes` | 24 hours |
| `hours` | 30 days |

**Changing parameters after creation:** Use `collMod` to update `granularity`, `bucketMaxSpanSeconds`, `bucketRoundingSeconds`, and `expireAfterSeconds`. You can only **increase** bucket span, never decrease it. `timeField` and `metaField` are permanently immutable.

```javascript
// Increase granularity (allowed)
db.runCommand({
  collMod: "sensor_readings",
  timeseries: { granularity: "minutes" }
})

// Set custom bucketing (MongoDB 6.3+)
db.runCommand({
  collMod: "sensor_readings",
  timeseries: {
    bucketMaxSpanSeconds: 86400,
    bucketRoundingSeconds: 86400
  }
})
```

**Sources:**
- [Time Series Considerations](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-considerations/)
- [Create and Query Procedures v7.0](https://www.mongodb.com/docs/v7.0/core/timeseries/timeseries-procedures/)
- [Community: Granularity and metaField](https://www.mongodb.com/community/forums/t/timeseries-collections-in-mongodb-granularity-and-metafield/222943)

---

### 2. Internal Bucket Architecture

MongoDB stores time series documents in internal `system.buckets.<collectionName>` bucket documents, not as individual BSON records. The view layer (`<collectionName>`) presents unpacked measurements to applications.

**Bucket structure:**

```javascript
// Internal bucket document (system.buckets.sensor_readings)
{
  "_id": ObjectId("..."),
  "control": {
    "version": 2,
    "min": {
      "_id": ObjectId("..."),
      "timestamp": ISODate("2024-01-01T00:00:00.000Z"),
      "temperature": 18.2
    },
    "max": {
      "_id": ObjectId("..."),
      "timestamp": ISODate("2024-01-01T00:59:59.000Z"),
      "temperature": 23.7
    },
    "closed": false
  },
  "meta": { "sensorId": "A42", "location": "building-3" },
  "data": {
    "timestamp": { "0": ISODate("..."), "1": ISODate("..."), ... },
    "temperature": { "0": 18.2, "1": 18.5, ... },
    "humidity": { "0": 61, "1": 62, ... }
  }
}
```

**Bucket lifecycle:**
- A bucket is opened when the first measurement for a given `metaField` value arrives.
- A bucket is **closed** when it reaches either ~1,000 measurements OR ~125 KB, whichever comes first, or when the bucket's time span limit (determined by granularity) is exceeded.
- Closed buckets are compressed and eligible for WiredTiger cache eviction.

**Compression mechanisms (MongoDB 5.2+):**

1. **Column-oriented storage**: Values for each field (temperature, humidity, pressure) are stored together rather than per-document. This enables delta encoding and RLE to be applied across entire columns.
2. **Delta encoding**: Stores the first value absolutely, then subsequent values as differences (`+0.1`, `-0.2`). Highly effective for monotonic timestamps and slowly changing sensor readings.
3. **Run-Length Encoding (RLE)**: Repeated values (e.g., `status: "active"` for 1,000 measurements) stored as `(value, count)`.
4. **Metadata deduplication**: Field names and BSON types stored once per bucket rather than per document.
5. **Zstd block compression** (WiredTiger level): Applied on top of the already column-compressed data.

**MongoDB 8.0 block processing**: Documents are written directly into column-compressed format, eliminating the decompression-recompression cycle on write. This results in 2-3x write throughput improvement and 10-20x cache usage reduction compared to MongoDB 7.0 for time series workloads.

**Sources:**
- [Columnar Storage Blog](https://www.mongodb.com/company/blog/technical/columnar-storage-time-series-collection-cost-savings)
- [Time Series Compression](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-compression/)
- [High vs Low Ingestion Study](https://www.mongodb.com/company/blog/technical/a-practical-study-of-mongodb-time-series-bucket-behavior)
- [MongoDB 8.0 Block Processing](https://dev.to/mongodb/supercharging-time-series-collections-key-enhancements-in-mongodb-80-with-block-processing-5b3i)

---

### 3. Secondary Indexes

Time series collections index at the bucket level, not the document level. The `control.min` and `control.max` values on each bucket function as a clustered range index that enables bucket-level pruning for time-range queries.

**Default clustered index:** A clustered index on the `metaField` and `timeField` is automatically created. No explicit `_id` index is created (unlike regular collections). In MongoDB 5.0, only a single compound index on `metaField` + `timeField` was supported; secondary indexes on measurement fields were added in later versions.

> **Skill boundary:** For general compound index design (ESR rule, multikey, partial, sparse, wildcard), use `mongodb-indexes-deep`. This section covers only time-series-specific index constraints and patterns.

**Supported secondary index types:**

| Index Type | On timeField | On metaField | On measurement fields |
|------------|-------------|--------------|----------------------|
| Single-field | Yes | Yes | Yes |
| Compound | Yes (at end of key) | Yes | Yes |
| Multikey | No | Yes only | No |
| 2dsphere | No | Yes only | No |
| 2d | No | Yes only | No |
| Sparse | No | Yes only | No |
| Partial (partialFilterExpression) | Limited | Yes (MongoDB 7.0+) | No |
| Text | No | No | No |
| Unique | No | No | No |
| Hashed | No (as of 8.0) | Yes | No |

**Adding a compound secondary index:**

```javascript
// Index for queries filtering by sensor + time range
db.sensor_readings.createIndex(
  { "metadata.sensorId": 1, "timestamp": 1 }
)

// Index on measurement field (metaField sub-field + measurement)
db.sensor_readings.createIndex(
  { "metadata.location": 1, "temperature": 1 }
)

// TTL partial filter on metaField (MongoDB 7.0+)
db.sensor_readings.createIndex(
  { "timestamp": 1 },
  {
    expireAfterSeconds: 86400,
    partialFilterExpression: { "metadata.tier": "free" }
  }
)
```

**Key indexing constraints:**
- `partialFilterExpression` can only reference the `metaField` (not measurement fields).
- Unique indexes are not supported — duplicate prevention must be handled at the application layer or using `$match` + `$group` in aggregation.
- Text indexes are not supported — consider Atlas Search for full-text needs.
- The `distinct()` command is not efficiently supported; use `$group` with a supporting compound index instead.

**Query on object metaField — use sub-field dot notation:**

```javascript
// GOOD: queries a scalar sub-field
db.sensor_readings.find({ "metadata.sensorId": "A42" })

// BAD: queries the entire metaField object (no index benefit)
db.sensor_readings.find({ metadata: { sensorId: "A42", location: "b3" } })
```

**Sources:**
- [Time Series Indexes](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-index/)
- [Add Secondary Indexes](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-secondary-index/)
- [Time Series Limitations](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-limitations/)

---

### 4. TTL and Automatic Data Expiration

Time series collections support bucket-granularity TTL via `expireAfterSeconds`. Unlike regular collection TTL indexes (which delete individual documents), TTL on time series collections deletes entire buckets once all measurements within the bucket are older than the threshold.

**Set at creation:**

```javascript
db.createCollection("metrics", {
  timeseries: {
    timeField: "ts",
    metaField: "host",
    granularity: "minutes",
    expireAfterSeconds: 604800   // 7 days
  }
})
```

**Modify after creation (cannot use createIndex):**

```javascript
db.runCommand({
  collMod: "metrics",
  expireAfterSeconds: 2592000    // change to 30 days
})
```

**TTL behavior:**
- The background TTL task runs every 60 seconds.
- A bucket is deleted only when **all** measurements in that bucket have expired (i.e., `control.max.timestamp + expireAfterSeconds < now`).
- Because of bucket aggregation, actual deletion may be delayed by up to bucket-span + 60s after expiration.
- A bucket created with `granularity: "hours"` covering a 30-day span won't be deleted until all 30 days of measurements within it have expired.

**Tiered TTL pattern (MongoDB 7.0+ with partial filter):**

```javascript
// Different retention for free vs. paid tier sensors
db.metrics.createIndex(
  { "ts": 1 },
  {
    expireAfterSeconds: 86400,    // 1 day for free tier
    partialFilterExpression: { "host.tier": "free" }
  }
)
// Paid tier uses collection-level expireAfterSeconds (longer)
```

**Sources:**
- [TTL for Time Series](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-automatic-removal/)
- [TTL Indexes](https://www.mongodb.com/docs/manual/core/index-ttl/)

---

### 5. Aggregation Pipeline — Time Series Optimizations

MongoDB provides three specialized aggregation stages that are particularly valuable for time series analysis:

> **Skill boundary — aggregation stages:** For general aggregation pipeline design ($lookup, $group, $merge, $out, explain profiling, memory limits), use `mongodb-aggregation-pipeline`. This section covers only time-series-optimized stages ($densify, $fill) and time-series-specific $setWindowFields usage. `$dateTrunc` (for downsampling into time buckets) is also covered here as it is the primary time-bucketing operator.

#### $dateTrunc — Time-Bucket Downsampling

`$dateTrunc` truncates a date to a specified granularity boundary. It is the canonical operator for downsampling raw measurements into fixed time buckets (minute candles, hourly rollups, daily aggregates).

```javascript
// Downsample 1-second ticks into 5-minute OHLCV bars
db.equity_ticks.aggregate([
  { $match: { "instrument.ticker": "AAPL" } },
  {
    $group: {
      _id: {
        ticker: "$instrument.ticker",
        bucket: { $dateTrunc: { date: "$tradeTime", unit: "minute", binSize: 5 } }
      },
      open:   { $first: "$price" },
      high:   { $max: "$price" },
      low:    { $min: "$price" },
      close:  { $last: "$price" },
      volume: { $sum: "$quantity" }
    }
  },
  { $sort: { "_id.bucket": 1 } }
])
```

The `binSize` parameter (MongoDB 5.0+) groups dates into multiples of the unit — e.g., `binSize: 5, unit: "minute"` snaps all timestamps to 5-minute boundaries.

#### $densify (MongoDB 5.1+)

Fills gaps in a time series by inserting synthetic documents at regular intervals where data is missing. Critical for dashboards and window function inputs that assume uniform spacing.

```javascript
// Fill hourly gaps in weather data
// NOTE: stationId here is a top-level field (the metaField itself, not a nested sub-field)
db.weather.aggregate([
  { $match: { "stationId": "WS-101" } },
  {
    $densify: {
      field: "timestamp",
      partitionByFields: ["stationId"],
      range: {
        step: 1,
        unit: "hour",
        bounds: [
          ISODate("2024-01-01T00:00:00Z"),
          ISODate("2024-01-02T00:00:00Z")
        ]
      }
    }
  }
])
```

**bounds values:**
- `"full"` — spans min to max across all documents in the collection.
- `"partition"` — spans min to max within each partition group.
- `[lower, upper]` — explicit range; lower inclusive, upper exclusive.

#### $fill (MongoDB 5.3+)

Populates `null` or missing fields in densified documents using interpolation or last-observed-carry-forward (LOCF).

```javascript
db.weather.aggregate([
  { $densify: { field: "timestamp", range: { step: 1, unit: "hour", bounds: "full" } } },
  {
    $fill: {
      sortBy: { "timestamp": 1 },
      // partitionBy key names are arbitrary output labels, not field paths
      partitionBy: { "stationId": "$stationId" },
      output: {
        "temperature": { method: "linear" },     // linear interpolation between known values
        "status": { method: "locf" }              // carry last known value forward
      }
    }
  }
])
```

**Fill methods:**
- `"linear"` — calculates value proportionally between surrounding non-null values.
- `"locf"` (Last Observation Carried Forward) — repeats the last known non-null value.

#### $setWindowFields (MongoDB 5.0+)

Applies window functions over ordered partitions without collapsing documents (unlike `$group`). Enables rolling averages, cumulative sums, lag/lead comparisons, and rankings — all SQL-standard window function patterns.

```javascript
db.sensor_readings.aggregate([
  {
    $setWindowFields: {
      partitionBy: "$metadata.sensorId",
      sortBy: { "timestamp": 1 },
      output: {
        // 5-minute rolling average
        "rollingAvgTemp": {
          $avg: "$temperature",
          window: { range: [-5, 0], unit: "minute" }
        },
        // Cumulative sum since start of partition
        "cumulativeEnergy": {
          $sum: "$energyWh",
          window: { documents: ["unbounded", "current"] }
        },
        // Previous reading (lag)
        "prevTemp": {
          $shift: { output: "$temperature", by: -1, default: null }
        },
        // Rank by temperature within window
        "tempRank": { $rank: {} }
      }
    }
  }
])
```

**Window types:**
- `documents`: `["unbounded", "current"]`, `[-N, M]` — count-based.
- `range`: `[-N, M]` with `unit` for time-based (ms, second, minute, hour, day, week, month, quarter, year).

**Important performance note:** Window functions on time series collections do not automatically push down through the bucket storage format. Use `$match` on `metaField` and `timeField` before `$setWindowFields` to minimize the scanned document set.

**Sources:**
- [$densify Reference](https://www.mongodb.com/docs/manual/reference/operator/aggregation/densify/)
- [$setWindowFields Reference](https://www.mongodb.com/docs/manual/reference/operator/aggregation/setwindowfields/)
- [Percona Window Functions in MongoDB 5.0](https://www.percona.com/blog/window-functions-in-mongodb-5-0/)
- [MongoDB Developer: time-series-window-functions](https://github.com/mongodb-developer/time-series-window-functions)

---

### 6. Atlas-Specific Features

#### Atlas Charts Integration

Atlas Charts works natively with time series collections. The time-series-optimized aggregation engine (bucket-level pruning, columnar projection) applies to Charts queries automatically — no special configuration needed.

**Use cases with Atlas Charts:**
- Real-time IoT sensor dashboards using time-range filters
- Environmental monitoring with rolling average overlays
- Infrastructure metrics with aggregated panels (mean, p95, max)
- Financial dashboards showing OHLCV candlestick data

**Limitation:** Embedded charts querying time series collections with a high-cardinality `metaField` can generate expensive scatter-gather queries. Use time-range and `metaField` equality filters in the embedded chart filter to scope queries.

**Sources:**
- [Visualizing Atlas Data with Charts](https://www.mongodb.com/resources/products/platform/visualizing-your-data-with-atlas-charts)
- [IoT + Atlas Charts Example](https://www.mongodb.com/developer/products/atlas/iot-mongodb-powering-time-series-analysis-household-power-consumption/)

#### Atlas Triggers — Not Supported

Time series collections **do not support change streams** and therefore **cannot use Database Triggers**. The optimized bucket storage format does not emit per-document change events.

**Workaround patterns:**
1. **Dual-write to a regular collection**: Write events to both a regular collection (for triggers) and a time series collection (for historical queries). The regular collection can be capped or have a short TTL.
2. **Scheduled triggers**: Use scheduled Atlas triggers to run aggregations over the time series collection at regular intervals and emit derived events or aggregated results to another collection.
3. **Atlas Stream Processing**: Use Kafka or Atlas Stream Processing `$source` stage to consume events before they enter the time series collection and react in real-time. Note: time series collections cannot serve as a `$source` in ASP.

**Sources:**
- [Community: Change Stream Workaround](https://www.mongodb.com/community/forums/t/mongodb-timeseries-change-stream-support-or-any-alternative/192106)
- [Triggers Limitations](https://www.mongodb.com/docs/atlas/atlas-ui/triggers/limitations/)

#### Atlas Flex Clusters

Atlas Flex clusters (the replacement for M2/M5 and Serverless instances, as of January 2026) support time series collections as they run MongoDB 5.0+ wire protocol. However, Flex clusters have limitations compared to Dedicated clusters:
- No Continuous backup / Point-in-Time Restore (snapshots only)
- No cross-region replication
- Private Endpoints support is limited — verify current availability in the Atlas docs, as Flex private endpoint support has been expanding since 2025

For production time series workloads requiring PITR, guaranteed HA, or private networking, use Dedicated clusters (M10+).

**Sources:**
- [Manage Flex Clusters](https://www.mongodb.com/docs/atlas/manage-flex-clusters/)
- [Flex Migration Guide](https://www.mongodb.com/docs/atlas/flex-migration/)

---

### 7. Sharding Time Series Collections

Sharding enables horizontal scaling for very high ingestion rates. Time series sharding has several important constraints that differ from regular collection sharding.

**Shard key rules:**
- Shard key must contain only the `metaField`, sub-fields of `metaField`, or (deprecated) the `timeField`.
- `timeField` as a shard key component is **deprecated in MongoDB 8.0** because monotonically increasing values cause write hotspots on a single shard.
- `metaField` can be used as a ranged or hashed shard key.
- Zone sharding is **not supported** for time series collections.

**Recommended shard key patterns:**

```javascript
// Shard on metaField sub-field (range sharding — best for region-scoped queries)
sh.shardCollection(
  "iot.sensor_readings",
  { "metadata.region": 1 }
)

// Hashed sharding on metaField (even distribution for high-cardinality deviceId)
sh.shardCollection(
  "iot.sensor_readings",
  { "metadata.deviceId": "hashed" }
)

// Compound: region + deviceId (best balance for multi-region IoT)
sh.shardCollection(
  "iot.sensor_readings",
  { "metadata.region": 1, "metadata.deviceId": 1 }
)
```

**Anti-pattern — timeField-only shard key:**

```javascript
// BAD: All writes land on the shard holding the current time range
sh.shardCollection("metrics.readings", { "timestamp": 1 })
```

**Pre-splitting:** If device groups or regions are known in advance, pre-split chunks before ingestion to avoid initial primary-shard hotspot.

**Sources:**
- [Shard a Time Series Collection](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-shard-collection/)
- [Time Series Limitations — Sharding](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-limitations/)

---

### 8. Performance Benchmarks and Working Set Sizing

#### Storage Compression

| Configuration | Compression Ratio | Source |
|---------------|------------------|--------|
| Typical numeric IoT sensor data (MongoDB 5.2+) | 70-90% over regular collection | MongoDB Engineering Blog |
| High-frequency uniform sensors (600 docs/min) | ~94% (1 MB vs 16.8 MB for 864K docs) | Medium: CodeX benchmark |
| Columnar + Zstd combined | Up to 95%+ for repetitive measurement data | MongoDB Blog |

#### Write Performance (MongoDB 8.0 vs 7.0)

| Metric | Improvement |
|--------|-------------|
| Write throughput | 2-3x |
| WiredTiger cache usage | 10-20x reduction |
| Write I/O amplification | Significantly reduced (direct columnar write) |

#### Working Set Sizing for Time Series

Unlike regular collections where the working set is the "hot" subset of documents, for time series the working set is primarily:
1. **Open buckets** (currently being written) — proportional to `metaField` cardinality.
2. **Recently queried time ranges** — based on your typical query lookback window.

**Sizing formula:**
```
Open bucket RAM   = (unique metaField values) × (avg bucket size ~125 KB)
Recent query RAM  = (query lookback seconds / granularity bucket span seconds)
                    × (unique metaField values) × (avg bucket size ~125 KB)
```

Granularity bucket span seconds reference:
- `seconds` granularity → 3,600 s (1 hour)
- `minutes` granularity → 86,400 s (24 hours)
- `hours`   granularity → 2,592,000 s (30 days)

**Example (10,000 IoT sensors, `minutes` granularity = 86,400 s span, 1-hour lookback):**
```
Open buckets  = 10,000 × 125 KB            = ~1.2 GB
Recent queries = (3,600 / 86,400) × 10,000 × 125 KB = ~54 MB
Total working set ≈ 1.3 GB
```
(At `seconds` granularity the same 1-hour lookback covers exactly 1 bucket span, so recent-query RAM ≈ open-bucket RAM = ~1.2 GB — an important difference when choosing granularity.)

**Recommendation:** Size WiredTiger cache (`storage.wiredTiger.engineConfig.cacheSizeGB`) at 50-60% of available RAM, targeting > 95% cache hit rate. Monitor `wiredTiger.cache.bytes currently in the cache` and `page faults` in Atlas metrics.

**Sources:**
- [Columnar Storage Cost Savings Blog](https://www.mongodb.com/company/blog/technical/columnar-storage-time-series-collection-cost-savings)
- [Time Series Compression Docs](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-compression/)
- [Bucket Behavior Study](https://www.mongodb.com/company/blog/technical/a-practical-study-of-mongodb-time-series-bucket-behavior)
- [Medium: Storage Comparison](https://medium.com/codex/analyzing-data-storage-regular-collection-vs-time-series-collection-54532ade7088)

---

## Practical Patterns

### Pattern 1: IoT Multi-Sensor Ingestion

**Schema design:**

```javascript
// Document shape
{
  "timestamp": ISODate("2024-06-17T10:00:00.000Z"),   // timeField
  "metadata": {                                          // metaField
    "sensorId": "HVAC-B3-F2-01",
    "buildingId": "B3",
    "sensorType": "environmental",
    "firmware": "2.3.1"
  },
  "temperature": 21.5,
  "humidity": 68.2,
  "pressure": 1013.25,
  "co2ppm": 412
}

// Collection creation
db.createCollection("hvac_readings", {
  timeseries: {
    timeField: "timestamp",
    metaField: "metadata",
    granularity: "minutes",         // 5-minute readings → minutes granularity
    expireAfterSeconds: 7776000     // 90-day retention
  }
})

// Supporting index for building-level queries
db.hvac_readings.createIndex({ "metadata.buildingId": 1, "timestamp": -1 })
```

**Batched insertion (critical for performance):**

```javascript
await db.collection("hvac_readings").insertMany(readings, { ordered: false })
// ordered: false allows parallelism; failures are non-blocking
```

---

### Pattern 2: Financial Tick Data

```javascript
db.createCollection("equity_ticks", {
  timeseries: {
    timeField: "tradeTime",
    metaField: "instrument",         // { ticker, exchange, assetClass }
    granularity: "seconds",          // sub-second to second ingestion
    bucketMaxSpanSeconds: 3600,      // 1-hour custom buckets (MongoDB 6.3+)
    bucketRoundingSeconds: 3600,
    expireAfterSeconds: 31536000     // 1-year raw tick retention
  }
})

// OHLCV aggregation (1-minute candles)
db.equity_ticks.aggregate([
  { $match: { "instrument.ticker": "AAPL", "tradeTime": { $gte: ISODate("2024-01-02") } } },
  {
    $group: {
      _id: {
        ticker: "$instrument.ticker",
        minute: { $dateTrunc: { date: "$tradeTime", unit: "minute" } }
      },
      open:   { $first: "$price" },
      high:   { $max: "$price" },
      low:    { $min: "$price" },
      close:  { $last: "$price" },
      volume: { $sum: "$quantity" }
    }
  },
  { $sort: { "_id.minute": 1 } }
])
```

---

### Pattern 3: Moving Average with $setWindowFields

```javascript
db.sensor_readings.aggregate([
  {
    $match: {
      "metadata.sensorId": "TEMP-001",
      "timestamp": { $gte: ISODate("2024-01-01"), $lt: ISODate("2024-01-02") }
    }
  },
  {
    $setWindowFields: {
      partitionBy: "$metadata.sensorId",
      sortBy: { "timestamp": 1 },
      output: {
        "movingAvg15m": {
          $avg: "$temperature",
          window: { range: [-15, 0], unit: "minute" }
        },
        "stdDev1h": {
          $stdDevPop: "$temperature",
          window: { range: [-60, 0], unit: "minute" }
        },
        "deltaFromPrev": {
          $subtract: [
            "$temperature",
            { $shift: { output: "$temperature", by: -1, default: "$$REMOVE" } }
          ]
        }
      }
    }
  }
])
```

---

### Pattern 4: Gap-Fill Dashboard Query

```javascript
// Ensure uniform hourly data points for charting even when sensors go offline
db.sensor_readings.aggregate([
  { $match: { "metadata.buildingId": "B3", "timestamp": { $gte: ISODate("2024-01-01"), $lt: ISODate("2024-01-08") } } },
  {
    $densify: {
      field: "timestamp",
      // $densify partitionByFields supports dotted paths for metaField sub-fields.
      // For measurement fields, dotted paths are NOT supported — use $addFields to promote first.
      partitionByFields: ["metadata.sensorId"],
      range: { step: 1, unit: "hour", bounds: "partition" }
    }
  },
  {
    $fill: {
      sortBy: { "timestamp": 1 },
      // partitionBy values are expressions; keys are arbitrary output labels
      partitionBy: { "sensorId": "$metadata.sensorId" },
      output: { "temperature": { method: "locf" }, "humidity": { method: "linear" } }
    }
  }
])
```

---

### Pattern 5: Versioning for Correctable Measurements

Time series collections cannot update measurement fields. Use the versioning pattern to handle corrections:

```javascript
// Original insert
db.readings.insertOne({
  timestamp: ISODate("2024-01-01T10:00:00Z"),
  metadata: { sensorId: "A1", version: 1, superseded: false },
  temperature: 21.5   // original, possibly erroneous
})

// Correction: insert new version, mark old as superseded via metaField update
db.readings.insertOne({
  timestamp: ISODate("2024-01-01T10:00:00Z"),
  metadata: { sensorId: "A1", version: 2, superseded: false },
  temperature: 22.1   // corrected value
})

db.readings.updateMany(
  { "metadata.sensorId": "A1", "metadata.version": 1 },
  { $set: { "metadata.superseded": true } }   // only metaField updates allowed
)

// Query always uses latest non-superseded version
db.readings.aggregate([
  { $match: { "metadata.superseded": false, "metadata.sensorId": "A1" } },
  { $sort: { "timestamp": 1, "metadata.version": -1 } },
  { $group: { _id: "$timestamp", doc: { $first: "$$ROOT" } } }
])
```

**Source:** [Versioning Pattern with Time Series Data](https://medium.com/mongodb/versioning-pattern-with-time-series-data-in-mongodb-595b5e8cdac4)

---

## Migration: Regular Collection to Time Series

**You cannot convert an existing collection in-place.** Migration always requires creating a new time series collection and copying data.

### Method 1: Aggregation Pipeline with $out (MongoDB 7.0+)

```javascript
// Step 1: Rename existing collection as staging
db.adminCommand({ renameCollection: "mydb.readings", to: "mydb.readings_old" })

// Step 2: Create new time series collection
db.createCollection("readings", {
  timeseries: { timeField: "timestamp", metaField: "device", granularity: "minutes" }
})

// Step 3: Copy data (batched internally by $out)
db.readings_old.aggregate([
  { $project: { _id: 0 } },   // _id will be auto-generated
  { $out: { db: "mydb", coll: "readings" } }
])

// Step 4: Validate counts and spot-check
db.readings.countDocuments() === db.readings_old.countDocuments()

// Step 5: Drop staging collection when satisfied
db.readings_old.drop()
```

### Method 2: mongodump + mongorestore

```bash
# Dump existing collection
mongodump --db mydb --collection readings_old --out ./dump

# Create time series collection first (mongorestore does not auto-create with TS options)
mongosh --eval 'db.createCollection("readings_ts", { timeseries: { timeField: "ts", metaField: "device" } })'

# Restore into time series collection
mongorestore --db mydb --collection readings_ts --drop ./dump/mydb/readings_old.bson
```

### Method 3: Kafka Connector (streaming cutover)

For live production systems with continuous ingestion, use the MongoDB Kafka Connector to dual-write during cutover:
1. Configure source connector reading from existing collection.
2. Configure sink connector writing to new time series collection.
3. Once data is synced and validated, cut application writes over to the time series collection.
4. Drain and stop connectors.

**Sources:**
- [Migrate with Aggregation Pipeline](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-migrate-with-aggregation/)
- [Migrate with Database Tools](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-migrate-with-tools/)
- [Kafka Connector Migration Tutorial](https://www.mongodb.com/docs/kafka-connector/current/tutorials/migrate-time-series/)

---

## Anti-Patterns

### Anti-Pattern 1: Using timeField as the Only Shard Key

```javascript
// BAD: monotonically increasing field → all writes to one shard
sh.shardCollection("metrics.events", { "timestamp": 1 })

// GOOD: metaField provides distribution
sh.shardCollection("metrics.events", { "metadata.region": 1 })
```

### Anti-Pattern 2: Wrong Granularity for Ingestion Rate

**Mismatch 1 — granularity too coarse (high-frequency data):** Setting `granularity: "hours"` for a sensor that reports every second means each bucket can remain open for up to 30 days before the *time* limit triggers a close. In practice, the *measurement-count* limit (~1,000 documents) is hit first (after ~17 minutes at 1/s), but this still produces far more bucket churn than needed and misrepresents the intended data cadence to the storage engine, degrading compression locality.

**Mismatch 2 — granularity too fine (low-frequency data):** Setting `granularity: "seconds"` for a sensor that only reports once per hour means each bucket closes after 1 hour (time limit), typically containing only ~1 measurement. This destroys compression — you lose all the benefit of columnar storage across many measurements.

```javascript
// BAD for 1/second data: granularity implies 30-day lifecycle
// (count limit fires at ~17min but bucket metadata is misleading)
{ granularity: "hours" }

// BAD for 1/hour data: each bucket closes after 1 hour with ~1 document
{ granularity: "seconds" }

// GOOD: match granularity to how often the same source sends data
{ granularity: "seconds" }   // sub-minute ingestion (1s, 10s, 30s intervals)
{ granularity: "minutes" }   // 1–60 minute intervals
{ granularity: "hours" }     // hourly or less frequent data

// BEST for custom cadences (MongoDB 6.3+):
{ bucketMaxSpanSeconds: 300, bucketRoundingSeconds: 300 }  // exactly 5-min buckets
```

### Anti-Pattern 3: High metaField Cardinality with Unbounded Values

Each unique `metaField` value maintains a separate open bucket in the working set. If `metaField` includes a UUID or a user-specific ID that changes per request, the working set explodes.

```javascript
// BAD: sessionId is unique per request — millions of open buckets
{ metaField: "sessionId" }

// GOOD: stable device identifier, bounded cardinality
{ metaField: "deviceId" }
```

### Anti-Pattern 4: Attempting Transactions or Multi-document Updates

```javascript
// BAD: writes to time series collections inside transactions throw an error
session.startTransaction()
db.readings.insertOne({ timestamp: new Date(), ... })  // throws error
session.commitTransaction()

// BAD: updating measurement fields
db.readings.updateMany({}, { $set: { "temperature": 22 } })  // error: not metaField

// GOOD: only metaField updates are allowed; use versioning pattern for corrections
db.readings.updateMany(
  { "metadata.sensorId": "A1" },
  { $set: { "metadata.calibrationVersion": 3 } }
)
```

### Anti-Pattern 5: Padding Missing Fields with Nulls/Empty Arrays

```javascript
// BAD: inconsistent schema breaks column compression
{ timestamp: ISODate("..."), temp: 21.5, humidity: null, pressure: [] }

// GOOD: omit fields entirely when not present
{ timestamp: ISODate("..."), temp: 21.5 }
```

### Anti-Pattern 6: Using distinct() for Cardinality Queries

```javascript
// BAD: distinct() is not supported efficiently on time series
db.readings.distinct("metadata.sensorId")

// GOOD: use aggregation with a compound index
db.readings.createIndex({ "metadata.sensorId": 1 })
db.readings.aggregate([
  { $group: { _id: "$metadata.sensorId" } }
])
```

### Anti-Pattern 7: Querying metaField as a Whole Object

```javascript
// BAD: no index hit — queries entire embedded document
db.readings.find({ metadata: { sensorId: "A1", type: "temp" } })

// GOOD: query scalar sub-fields — uses index
db.readings.find({ "metadata.sensorId": "A1", "metadata.type": "temp" })
```

---

## Troubleshooting

### Issue: Buckets are Too Large / Too Small

**Diagnosis:**
```javascript
// Check actual bucket sizes
// Use bracket notation or getCollection() — dot notation fails in some drivers for system.buckets.*
db.getCollection("system.buckets.sensor_readings").aggregate([
  { $project: { count: { $size: { $objectToArray: "$data.timestamp" } } } },
  { $group: { _id: null, avgBucketSize: { $avg: "$count" }, maxBucketSize: { $max: "$count" } } }
])
```

**Fix:** Adjust `granularity` or `bucketMaxSpanSeconds` with `collMod`. Remember: you can only increase span, not decrease it.

---

### Issue: Queries Are Slow Despite Indexes

**Diagnosis:**
```javascript
db.sensor_readings.find({ "metadata.sensorId": "A1", "timestamp": { $gte: ISODate("...") } })
  .explain("executionStats")
```

Look for `COLLSCAN` on `system.buckets.*` — this indicates missing indexes or the query optimizer not using bucket-level pruning.

**Common causes:**
- Querying measurement fields in `$match` without preceding `metaField` filter.
- Not using dot notation on `metaField` sub-fields.
- Missing compound index for the combination of `metaField` sub-field + `timeField`.

---

### Issue: High Memory / WiredTiger Cache Pressure

**Symptoms:** High cache utilization, frequent evictions, rising page faults.

**Diagnosis:** High `metaField` cardinality generating too many open buckets.

**Fix options:**
1. Reduce `metaField` cardinality by grouping sensors into logical partitions.
2. Increase granularity to close buckets faster (shorter time span per bucket).
3. Upgrade to MongoDB 8.0 for 10-20x cache reduction from block processing.
4. Scale up cluster tier (more RAM) or scale out (sharding).

---

### Issue: TTL Not Deleting Data

**Verify expiration config:**
```javascript
db.sensor_readings.getCollectionInfos()[0].options.timeseries
// Check expireAfterSeconds
```

**Common causes:**
- `expireAfterSeconds` was never set at creation (default: no expiration).
- Bucket span is too large — the bucket won't delete until ALL measurements in it expire.
- Background TTL task has lag (up to 60s + bucket span after last measurement expires).

---

### Issue: Migration Validation After $out

```javascript
// Count comparison
const original = db.readings_old.countDocuments()
const migrated = db.readings.countDocuments()
print(`Original: ${original}, Migrated: ${migrated}, Match: ${original === migrated}`)

// Spot-check a document
const sample = db.readings_old.findOne()
const ts = sample.timestamp
db.readings.findOne({ "metadata.deviceId": sample.device, "timestamp": ts })
```

---

## Limitations Reference

| Limitation | Details |
|-----------|---------|
| Transactions | Reads allowed; writes throw an error |
| Updates | Only `metaField` can be updated; must use `updateMany`; no `upsert: true` |
| Deletes | Only via TTL; no `deleteMany` matching measurement fields |
| Change streams | Not supported |
| Atlas Triggers | Not supported (requires change streams) |
| Schema validation | Not supported |
| `$merge` into time series | Not allowed; use `$out` |
| `distinct()` | Not supported efficiently; use `$group` instead |
| Unique indexes | Not supported |
| Text indexes | Not supported |
| Partial indexes | Only on `metaField` (measurement fields excluded) |
| Zone sharding | Not supported |
| Max document size | 4 MB (vs 16 MB for regular collections) |
| Date range without index | Dates before 1970 or after 2038 require explicit `timeField` index |
| Collection type change | Cannot convert to/from time series after creation |
| `renameCollection` | Not supported |
| `reIndex` | Not supported |
| MongoDB Search | Not supported |
| CSFLE / Queryable Encryption | Not supported |
| Atlas Stream Processing source | Not supported (no change streams) |

---

## References

1. [MongoDB Time Series Collections — Official Documentation](https://www.mongodb.com/docs/manual/core/timeseries-collections/) — Core reference for all time series features.
2. [Time Series Limitations](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-limitations/) — Comprehensive list of unsupported operations.
3. [Best Practices for Time Series Collections](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-best-practices/) — Official best practices: compression, batching, metaField design.
4. [Columnar Storage Cost Savings — MongoDB Engineering Blog](https://www.mongodb.com/company/blog/technical/columnar-storage-time-series-collection-cost-savings) — Delta encoding, RLE, and Zstd compression mechanics with benchmarks.
5. [MongoDB 8.0 Block Processing](https://www.mongodb.com/company/blog/technical/key-enhancements-mongodb-8-0-block-processing) — 2-3x throughput and 10-20x cache reduction from direct columnar writes.
6. [High vs Low Ingestion Bucket Behavior Study](https://www.mongodb.com/company/blog/technical/a-practical-study-of-mongodb-time-series-bucket-behavior) — Empirical study of granularity impact on bucket lifecycle under different ingestion rates.
7. [$densify Reference](https://www.mongodb.com/docs/manual/reference/operator/aggregation/densify/) — Full parameter reference and examples.
8. [$setWindowFields Reference](https://www.mongodb.com/docs/manual/reference/operator/aggregation/setwindowfields/) — Window function accumulator and range options.
9. [Migrate Data into a Time Series Collection](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-migrate-data-into-timeseries-collection/) — Official migration procedures.
10. [Versioning Pattern with Time Series Data](https://medium.com/mongodb/versioning-pattern-with-time-series-data-in-mongodb-595b5e8cdac4) — Pattern for handling measurement corrections.
11. [Window Functions and Time Series Performance — Medium](https://medium.com/mongodb-performance-tuning/mongodb-windows-function-and-time-series-performance-8d742addac34) — Performance analysis of $setWindowFields with time series collections.
12. [Shard a Time Series Collection](https://www.mongodb.com/docs/manual/core/timeseries/timeseries-shard-collection/) — Sharding rules and shard key selection.

---

## See also

- **`mongodb-aggregation-stages-deep`** — for the full `$densify` (numeric and date range, partition-aware bounds), `$fill` (linear / LOCF / constant), `$linearFill`, and `$setWindowFields` (`$derivative`, `$integral`, `$expMovingAvg`, `$shift`, ranks) reference. Includes canonical gap-filled-hourly-chart recipe combining `$group` -> `$densify` -> `$fill` and the 100 MB-per-partition memory-limit caveats.
