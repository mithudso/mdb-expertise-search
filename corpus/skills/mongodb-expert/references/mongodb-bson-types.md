<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-bson-types` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-bson-types
category: mongodb
tags: [mongodb, bson, extended-json, objectid, uuid, decimal128, date-handling, binary-data, gridfs, type-system, driver-types, schema-validation, mongoexport, mongodump, type-coercion]
version: 1.1.0
updated: 2026-05-29
description: |
  MongoDB BSON type system deep reference — complete type table with codes and aliases, BSON comparison
  sort order, ObjectId 12-byte structure and creation-time range queries, Date/Timestamp handling and
  UTC pitfalls, Decimal128 vs Double vs Int32/Int64 for financial and scientific data, Binary subtypes
  and GridFS thresholds, driver type mapping for Node.js/Python/Java/Go/C#, Extended JSON v1 vs v2
  canonical vs relaxed modes, $type and $convert querying, UUID subtype-4 best practices and sharding
  implications, BSON document/nesting/field size limits and overhead calculations.
  TRIGGER: choosing a numeric BSON type (Double, Int32, Int64, Decimal128); ObjectId or UUID _id design;
  BSON Date vs Timestamp confusion; type mismatch causing zero query results; Extended JSON / EJSON format
  for mongoexport or bsondump; Binary subtype selection; $type query operator; $convert or $toDecimal
  in aggregation; UUID representation across drivers; BSON document size limit (16 MB); field name
  length overhead; GridFS vs inline binary decision.
  SKIP: aggregation pipeline design — use mongodb-aggregation-pipeline; index design — use
  mongodb-indexes-deep; schema modeling patterns — use mongodb-schema-design; sharding with UUID _id —
  cross-reference mongodb-sharding for the write-distribution tradeoff but stay here for the BSON mechanics.
when_to_use:
  - Choosing the right numeric type for financial vs scientific vs counter data
  - Diagnosing type mismatch bugs where a query returns no results (string "123" vs number 123)
  - Configuring driver type mapping for ObjectId, UUID, Date, or Decimal128
  - Exporting/importing data with mongoexport, mongodump, or bsondump and understanding the Extended JSON format
  - Designing _id fields (ObjectId vs UUID vs custom)
  - Schema validation with $jsonSchema type constraints
  - Understanding BSON size limits for document design decisions
  - Working with Binary data subtypes or GridFS
  - Using $type query operator or $convert aggregation operator
whenNotToUse:
  - Aggregation pipeline construction — use mongodb-aggregation-pipeline
  - Index design for BSON fields — use mongodb-indexes-deep
  - Document schema modeling patterns — use mongodb-schema-design
  - Sharding strategy for UUID _id — use mongodb-sharding (BSON mechanics stay here)
related_skills:
  - mongodb-expert
  - mongodb-schema-design
  - mongodb-aggregation-pipeline
  - mongodb-indexes-deep
  - mongodb-sharding
  - mongodb-developer
  - mongodb-query-performance
---

# MongoDB BSON Types and Extended JSON

## Overview

BSON (Binary JSON) is MongoDB's binary-encoded serialization format for storing documents and making remote procedure calls. It extends JSON with additional data types (ObjectId, Date, Decimal128, Binary, Timestamp) and carries explicit type information for every field. Understanding BSON types is essential for correct data modeling, precise querying with `$type`, type-safe driver usage, and lossless data exchange via Extended JSON.

---

## 1. BSON Type System Overview

### Complete Type Table

| Type | Number | Alias | Notes |
|---|---|---|---|
| Double | 1 | `"double"` | 64-bit IEEE 754 float |
| String | 2 | `"string"` | UTF-8 encoded |
| Object | 3 | `"object"` | Embedded document |
| Array | 4 | `"array"` | Ordered list |
| Binary data | 5 | `"binData"` | Bytes with subtype byte |
| Undefined | 6 | `"undefined"` | **Deprecated** |
| ObjectId | 7 | `"objectId"` | 12-byte unique ID |
| Boolean | 8 | `"bool"` | true / false |
| Date | 9 | `"date"` | UTC milliseconds since epoch |
| Null | 10 | `"null"` | Null or missing |
| Regular Expression | 11 | `"regex"` | Pattern + options |
| DBPointer | 12 | `"dbPointer"` | **Deprecated** |
| JavaScript | 13 | `"javascript"` | JS code string |
| Symbol | 14 | `"symbol"` | **Deprecated** |
| JavaScript with scope | 15 | `"javascriptWithScope"` | **Deprecated** |
| 32-bit integer | 16 | `"int"` | |
| Timestamp | 17 | `"timestamp"` | **Internal MongoDB use** |
| 64-bit integer | 18 | `"long"` | |
| Decimal128 | 19 | `"decimal"` | IEEE 754 decimal128 |
| Min key | -1 | `"minKey"` | Always less than all other types |
| Max key | 127 | `"maxKey"` | Always greater than all other types |

### Binary Data Subtypes

| Subtype | Hex | Description |
|---|---|---|
| Generic | 0x00 | Default binary blob |
| Function | 0x01 | Serialized function code |
| Binary (old) | 0x02 | Legacy binary format |
| UUID (old) | 0x03 | Legacy UUID — byte order varies by driver |
| UUID | 0x04 | Standard RFC 4122 UUID — consistent byte order across all drivers |
| MD5 | 0x05 | MD5 hash |
| Encrypted BSON | 0x06 | Client-side field encryption ciphertext |
| Compressed time series | 0x07 | Used by MongoDB 5.2+ time series internally |
| Sensitive data | 0x08 | Not written to server logs |
| Vector | 0x09 | Vector embedding data (Atlas Vector Search) |
| User-defined | 0x80 | Custom application-defined binary |

### Special Type Aliases

The `$type` query operator supports the special alias `"number"` which matches `int`, `long`, `double`, and `decimal` types simultaneously. The aggregation operator `$isNumber` returns `true` for all four numeric types.

---

## 2. BSON Comparison and Sort Order

When sorting or comparing values of different BSON types, MongoDB applies this order from lowest to highest:

1. **MinKey** (internal)
2. **Null** (missing fields also sort here)
3. **Numbers** — int, long, double, decimal (treated as equivalent)
4. **Symbol, String** (binary comparison unless Collation is specified)
5. **Object**
6. **Array**
7. **BinData** — sorted by: (1) data length, (2) subtype byte, (3) byte-by-byte
8. **ObjectId**
9. **Boolean**
10. **Date**
11. **Timestamp**
12. **Regular Expression**
13. **JavaScript Code**
14. **JavaScript Code with Scope**
15. **MaxKey** (internal)

**Key rules:**
- Missing fields sort the same as `null`
- All four numeric types (int, long, double, decimal) are considered equivalent for ordering
- Arrays: ascending sort uses the smallest element; descending sort uses the largest element
- BSON Objects: compared key-value pair by key-value pair in declaration order

---

## 3. ObjectId

### Structure (12 bytes)

```
[4 bytes: Unix timestamp (seconds)] [5 bytes: random per-process value] [3 bytes: incrementing counter]
```

- **Timestamp (bytes 0–3):** Seconds since Unix epoch, big-endian. Allows approximate creation time extraction.
- **Random value (bytes 4–8):** Generated once per process at startup. Unique to machine+process.
- **Counter (bytes 9–11):** Starts at a random value, increments per ObjectId created in the process. Resets on restart.

Timestamp and counter use big-endian (most-significant byte first), unlike other BSON values that use little-endian. This makes ObjectIds approximately sortable by creation time.

### ObjectId Usage in mongosh

```javascript
// Generate new ObjectId
const id = new ObjectId();

// Create from hex string
const id2 = new ObjectId("507f1f77bcf86cd799439011");

// Extract creation timestamp (returns Date)
id.getTimestamp();  // ISODate("2024-01-15T10:30:00.000Z")

// Compare (lexicographic on hex string)
id1 < id2  // older ObjectId sorts lower

// Construct a "range query by creation time" dummy ObjectId
// .padStart(8,'0') guards against timestamps whose hex is < 8 chars
const startId = new ObjectId(
  Math.floor(new Date("2024-01-01").getTime() / 1000).toString(16).padStart(8, '0') + "0000000000000000"
);
db.events.find({ _id: { $gt: startId } });
```

### ObjectId in Driver Contexts

- **Node.js:** `new ObjectId()` from `mongodb` or `bson` package
- **Python:** `from bson import ObjectId; ObjectId()`
- **Java:** `new ObjectId()` (org.bson.types)
- **Go:** `primitive.NewObjectID()`
- **C#:** `ObjectId.GenerateNewId()` (MongoDB.Bson)

### ObjectId vs UUID as `_id`

| Property | ObjectId | UUID (Binary subtype 4) |
|---|---|---|
| Size | 12 bytes | 16 bytes |
| Monotonic | Approximately (per process) | No (random UUIDv4) / Yes (UUIDv7) |
| Embeds creation time | Yes | No (v4) / Yes (v7) |
| Sharding write distribution | Hot spot on range shard key | Uniform (v4) |
| Cross-system portability | MongoDB-specific | Industry standard |
| WiredTiger cache efficiency | Good (sequential writes) | Worse (random v4 fragments B-tree) |

**Recommendation:** Use ObjectId for MongoDB-native applications. Use UUID (subtype 4, preferably UUIDv7) when interoperating with external systems that manage IDs, or when you need globally unique IDs independent of MongoDB.

---

## 4. Date and Timestamp Handling

### BSON Date

- **Stored as:** signed 64-bit integer — milliseconds since Unix epoch (January 1, 1970 00:00:00 UTC)
- **Range:** approximately ±290 million years from epoch
- **Precision:** milliseconds (not microseconds or nanoseconds)
- **Always UTC:** MongoDB stores and retrieves all BSON Date values in UTC

```javascript
// mongosh: both constructors are equivalent
new Date("2024-06-15T10:30:00Z")  // ISODate("2024-06-15T10:30:00.000Z")
ISODate("2024-06-15")             // ISODate("2024-06-15T00:00:00.000Z")

// Convert to millisecond epoch value
ISODate("2024-01-01").valueOf()   // 1704067200000
```

### Common Date Pitfalls

1. **Storing dates as strings** — breaks range queries and date arithmetic in aggregation. Always use BSON Date.
2. **Local timezone confusion** — `new Date()` in client code may pass a local timezone string; ensure UTC conversion before insert.
3. **Strings in Extended JSON** — `"2024-06-15"` (a string) is NOT a BSON Date. Use `ISODate("2024-06-15")` or `{ $date: "2024-06-15T00:00:00Z" }`.
4. **Millisecond precision** — applications expecting microsecond precision (PostgreSQL, Python datetime.microsecond) must store a separate field.

### Date Arithmetic in Aggregation

```javascript
// $dateAdd — add 30 days
{ $dateAdd: { startDate: "$createdAt", unit: "day", amount: 30 } }

// $dateDiff — calendar days between two dates (not business days)
{ $dateDiff: { startDate: "$startDate", endDate: "$endDate", unit: "day" } }

// $dateSubtract — subtract 6 months
{ $dateSubtract: { startDate: "$updatedAt", unit: "month", amount: 6 } }

// $dateToParts with timezone — extract date parts in America/New_York
{ $dateToParts: { date: "$eventDate", timezone: "America/New_York" } }
// Returns: { year: 2024, month: 6, day: 14, hour: 21, minute: 30, second: 0, millisecond: 0 }

// $dateToString — format for display
{ $dateToString: { format: "%Y-%m-%d", date: "$createdAt", timezone: "Europe/London" } }
```

### BSON Timestamp vs BSON Date

BSON Timestamp (type 17) is **for internal MongoDB use only** (oplog `ts` field). It is a 64-bit value: upper 32 bits = seconds since epoch, lower 32 bits = incrementing ordinal within that second. Do not use Timestamp for application dates — use BSON Date instead.

---

## 5. Decimal128 and Numeric Types

### Numeric Type Comparison

| Type | BSON | Bits | Range / Precision | Use Case |
|---|---|---|---|---|
| Double | 1 | 64 | ~15–17 significant decimal digits (binary float) | Scientific, approximate values, geo coordinates |
| Int32 | 16 | 32 | −2,147,483,648 to 2,147,483,647 | Counters, small IDs, flags |
| Int64 | 18 | 64 | −9.2×10^18 to 9.2×10^18 | Large counters, epoch milliseconds, user IDs |
| Decimal128 | 19 | 128 | 34 decimal digits, exponent −6143 to +6144 | Financial, tax, currency, exact arithmetic |

### Double Precision Problem

```javascript
// Binary floating-point cannot represent 0.1 exactly
0.1 + 0.2 === 0.3  // false in JavaScript and MongoDB Double
// Stored as: 0.30000000000000004

// Use Decimal128 for monetary values (conceptual — Decimal128 objects are not
// compared with === in drivers; use driver-specific equality or aggregation)
// In mongosh: NumberDecimal("0.10") + NumberDecimal("0.20") displays as 0.30 exactly
```

### Decimal128 in mongosh

```javascript
// Insert monetary value
db.prices.insertOne({ item: "widget", price: NumberDecimal("19.99") })

// Query exact match
db.prices.find({ price: NumberDecimal("19.99") })

// Aggregation arithmetic preserves precision
db.prices.aggregate([
  { $project: { total: { $multiply: ["$price", NumberDecimal("1.08")] } } }
])

// fromStringWithRounding — mongosh/driver method (not a server version gate)
Decimal128.fromStringWithRounding("1234.99999999999")
```

### Decimal128 Limitations

- **No direct $sum in older versions:** `$sum` on Decimal128 fields works in MongoDB 4.0+
- **Driver support required:** Not all client libraries handle Decimal128 natively; check driver docs
- **No IEEE 754 special values in queries:** NaN and Infinity comparisons behave differently than with Double
- **Performance:** Decimal128 arithmetic is slower than Double; avoid in high-throughput, non-financial contexts

### Int32 vs Int64 Overflow Behavior

```javascript
// In mongosh, integer literals are Int32 by default if they fit
NumberInt(2147483647)  // Max Int32
NumberLong(9007199254740993)  // Use Long for values > Number.MAX_SAFE_INTEGER

// JavaScript numbers lose precision for integers > 2^53
// Always use Long/BigInt for large MongoDB int64 values in Node.js
const { Long } = require('bson');
Long.fromString("9007199254740993")  // safe — pass as string; fromNumber(9007199254740993) truncates before it runs
```

### Monetary Data Best Practice

Use `NumberDecimal` / Decimal128 for all monetary amounts. The "scale factor" alternative (store cents as Int64) works but requires all application code to know the scale factor and risks inconsistency.

---

## 6. Binary Data

### Storing Binary in Documents

```javascript
// Node.js: Binary from Buffer
const { Binary } = require('bson');
const imageBuffer = fs.readFileSync('photo.jpg');
db.photos.insertOne({ data: new Binary(imageBuffer) });

// Python: bytes type auto-encodes as subtype 0
db.photos.insert_one({ "data": open("photo.jpg", "rb").read() })

// Python: explicit subtype
from bson.binary import Binary
db.photos.insert_one({ "data": Binary(data, 5) })  # subtype 5 = MD5
```

### GridFS vs Inline Binary

| Criterion | Inline Binary | GridFS |
|---|---|---|
| Max size | 16MB (document limit) | Unlimited (255KB chunks) |
| Access pattern | Load entire document | Streaming, range reads |
| Indexing | Full document in memory | Metadata indexed separately |
| Atomicity | Atomic with document | Not atomic across chunks |
| Query | Can query on metadata alongside binary | Metadata in `fs.files`, binary in `fs.chunks` |

**Rule of thumb:** Use inline Binary for images/files under ~1MB that are always loaded with the document. Use GridFS for larger files or when streaming is needed.

### GridFS Chunk Size

Default GridFS chunk size is 255 KB. Each chunk is one document in `fs.chunks`. The default chunk size can be overridden per bucket.

---

## 7. Driver Type Mapping Reference

### Node.js (bson / mongodb npm packages)

```javascript
import { ObjectId, Binary, Decimal128, Long, Timestamp, UUID, BSON } from 'mongodb';

// ObjectId
const id = new ObjectId();
const fromHex = new ObjectId("507f1f77bcf86cd799439011");

// Decimal128
const price = Decimal128.fromString("19.99");

// Long (Int64)
const counter = Long.fromNumber(9007199254741000);

// UUID (generates and stores as Binary subtype 4)
const uuid = new UUID();  // or new UUID("existing-uuid-string")

// Binary with explicit subtype
const blob = new Binary(buffer, 0);  // subtype 0 = generic

// Timestamp (internal use)
const ts = new Timestamp({ t: 1234567890, i: 1 });

// Serialize/deserialize raw BSON
const bytes = BSON.serialize(doc);
const doc2 = BSON.deserialize(bytes);
```

### Python (PyMongo / bson)

```python
import pymongo
from bson import ObjectId, Decimal128, Int64
from bson.binary import Binary, UuidRepresentation
from datetime import datetime, timezone

# ObjectId
oid = ObjectId()
oid_from_str = ObjectId("507f1f77bcf86cd799439011")
oid.generation_time  # datetime in UTC

# Decimal128
price = Decimal128("19.99")
price.to_decimal()  # returns Python decimal.Decimal

# Int64 — small integers are Int32 by default
large = Int64(9007199254741000)

# Binary subtype 0 (bytes auto-encode as subtype 0)
data = Binary(b"\x00\x01\x02", 0)

# UUID — configure at client level for consistency
client = pymongo.MongoClient(uuidRepresentation=UuidRepresentation.STANDARD)

# Dates — always use UTC-aware datetime
dt = datetime(2024, 6, 15, 10, 30, tzinfo=timezone.utc)
```

### Java (org.bson)

```java
import org.bson.BsonDateTime;
import org.bson.BsonObjectId;
import org.bson.UuidRepresentation;
import org.bson.types.Binary;
import org.bson.types.Decimal128;
import org.bson.types.ObjectId;
import com.mongodb.MongoClientSettings;
import java.math.BigDecimal;
import java.util.Date;

// ObjectId
ObjectId id = new ObjectId();
ObjectId fromHex = new ObjectId("507f1f77bcf86cd799439011");
Date creationDate = id.getDate();  // extract timestamp

// Decimal128
Decimal128 price = Decimal128.parse("19.99");
Decimal128 fromBigDecimal = new Decimal128(new BigDecimal("19.99"));

// Date — use java.util.Date or Instant
BsonDateTime dt = new BsonDateTime(System.currentTimeMillis());

// UUID — configure MongoClient with STANDARD for Binary subtype 4
MongoClientSettings settings = MongoClientSettings.builder()
    .uuidRepresentation(UuidRepresentation.STANDARD)
    .build();
```

### Go (go.mongodb.org/mongo-driver/bson/primitive)

> Note: The v1 `primitive` package is deprecated. New projects should use `go.mongodb.org/mongo-driver/v2/bson` (driver v2). The API is nearly identical; replace the import path.

```go
// Driver v1 (deprecated — use v2 for new projects)
import "go.mongodb.org/mongo-driver/bson/primitive"
// Driver v2: import "go.mongodb.org/mongo-driver/v2/bson"

// ObjectId
id := primitive.NewObjectID()
id2, _ := primitive.ObjectIDFromHex("507f1f77bcf86cd799439011")
t := id.Timestamp()  // time.Time

// DateTime — wraps int64 (milliseconds since epoch)
dt := primitive.NewDateTimeFromTime(time.Now().UTC())

// Decimal128
d, _ := primitive.ParseDecimal128("19.99")

// Binary with UUID subtype
b := primitive.Binary{Subtype: 0x04, Data: uuidBytes}

// Document representations
doc := bson.D{{"name", "Alice"}, {"age", 30}}   // ordered
m := bson.M{"name": "Alice", "age": 30}          // unordered map
```

### C# (.NET — MongoDB.Bson)

```csharp
using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

// ObjectId
var id = ObjectId.GenerateNewId();
var fromStr = new ObjectId("507f1f77bcf86cd799439011");
DateTime created = id.CreationTime;

// Decimal128
var price = new Decimal128(19.99m);  // from C# decimal

// DateTime — C# driver stores as UTC automatically
[BsonDateTimeOptions(Kind = DateTimeKind.Utc)]
public DateTime CreatedAt { get; set; }

// UUID — configure for standard subtype 4
var settings = MongoClientSettings.FromConnectionString(uri);
settings.GuidRepresentation = GuidRepresentation.Standard;
```

---

## 8. Extended JSON v1 vs v2

Extended JSON bridges BSON's type system and plain JSON by adding `$`-prefixed wrappers to preserve type information.

### Extended JSON v2 Modes

**Canonical Mode** — lossless, full type preservation. Used by `bsondump` (converts raw BSON to Extended JSON). Note: `mongodump` outputs raw BSON binary files, not Extended JSON — use `bsondump` to convert those files.
**Relaxed Mode** — human-readable, may lose type precision (integers become native JSON numbers). Default for `mongoexport`.

### v2 Type Representations

| BSON Type | v2 Canonical | v2 Relaxed |
|---|---|---|
| Int32 | `{"$numberInt":"10"}` | `10` |
| Int64 | `{"$numberLong":"50"}` | `50` |
| Double | `{"$numberDouble":"10.5"}` | `10.5` |
| Decimal128 | `{"$numberDecimal":"10.99"}` | `{"$numberDecimal":"10.99"}` |
| Date (1970–9999) | `{"$date":{"$numberLong":"1565546054692"}}` | `{"$date":"2019-08-11T17:54:14.692Z"}` |
| ObjectId | `{"$oid":"5d505646cf6d4fe581014ab2"}` | Same as Canonical |
| Binary | `{"$binary":{"base64":"<b64>","subType":"00"}}` | Same as Canonical |
| Regex | `{"$regularExpression":{"pattern":"^H","options":"i"}}` | Same as Canonical |
| Timestamp | `{"$timestamp":{"t":1565545664,"i":1}}` | Same as Canonical |
| MinKey | `{"$minKey":1}` | Same as Canonical |
| MaxKey | `{"$maxKey":1}` | Same as Canonical |

Note: Decimal128, ObjectId, Binary, Regex, and Timestamp are **identical** in both canonical and relaxed modes. Only the four numeric types and Date differ.

### Extended JSON v1 (Legacy)

v1 has two sub-modes: **Strict** (RFC-JSON parseable) and **mongo Shell** (evaluated by mongosh).

| Type | v1 Strict | v1 Shell Mode |
|---|---|---|
| ObjectId | `{"$oid":"<id>"}` | `ObjectId("<id>")` |
| Date | `{"$date":"<ISO-8601>"}` or `{"$date":<ms>}` | `new Date(<ms>)` |
| Binary | `{"$binary":"<b64>","$type":"<hex>"}` | `BinData(<t>,<data>)` |
| Int64 | `{"$numberLong":"<n>"}` | `Long("<n>")` |
| Decimal128 | `{"$numberDecimal":"<n>"}` | `Decimal128("<n>")` |
| Regex | `{"$regex":"<pattern>","$options":"<opts>"}` | `/<pattern>/<opts>` |

**v1 vs v2 key differences:**
- v1 Binary format uses top-level `$binary` + `$type` keys; v2 uses nested object with `base64` and `subType`
- v1 Date can be either ISO string or millisecond number; v2 canonical uses `$numberLong` wrapper, relaxed uses ISO string
- v1 only officially supported by C# and Ruby drivers; all other drivers use v2
- `mongoexport` before MongoDB 4.2 outputs v1 strict; 4.2+ outputs v2 relaxed by default

### Tool Reference

| Tool | Default Format | Override Flag |
|---|---|---|
| `mongoexport` | v2 Relaxed | `--jsonFormat=canonical` |
| `mongoimport` | v2 Relaxed or Canonical | `--legacy` for v1 |
| `mongodump` | Raw BSON binary (not Extended JSON) | — |
| `bsondump` | v2 Canonical Extended JSON | — |

> Note: `mongodump` writes `.bson` files (raw binary), not Extended JSON. Use `bsondump` to convert a `.bson` file to human-readable Extended JSON v2 Canonical format.

### EJSON API in mongosh

```javascript
// Serialize document to Extended JSON
const serialized = EJSON.serialize(db.collection.findOne());

// Parse Extended JSON string back to BSON-like object
const obj = EJSON.parse('{"_id":{"$oid":"507f1f77bcf86cd799439011"}}');

// Stringify with options
EJSON.stringify(doc, { relaxed: false });  // canonical mode
```

---

## 9. Type Coercion and Querying

### `$type` Query Operator

Selects documents where a field matches one or more BSON types. Useful for auditing mixed-type collections (data quality).

```javascript
// Single type by alias
db.users.find({ age: { $type: "int" } })

// Single type by number
db.users.find({ age: { $type: 16 } })

// Match any numeric type
db.users.find({ price: { $type: "number" } })

// Multiple types
db.users.find({ value: { $type: ["string", "int", "double"] } })

// Find documents where field is an array (not just contains array elements)
db.orders.find({ tags: { $type: "array" } })

// Find fields that are null OR missing (both sort as null in BSON)
// To match ONLY missing fields, use: { email: { $exists: false } }
db.users.find({ email: { $type: "null" } })
```

**Array behavior:** When the field is an array, `$type` returns the document if **any element** matches. To match the field itself being an array, use `$type: "array"`.

### `$type` Aggregation Operator

Returns the BSON type name of a value as a string:

```javascript
db.data.aggregate([
  { $project: {
      fieldType: { $type: "$value" }
  }}
])
// Returns strings: "double", "string", "objectId", "array", "missing", etc.
```

### `$convert` Aggregation Operator

```javascript
{
  $convert: {
    input: "$rawValue",
    to: "decimal",           // target type: string alias or numeric BSON type ID
    onError: "CONVERSION_ERROR",   // value if conversion fails
    onNull: NumberDecimal("0")     // value if input is null/missing
  }
}
```

**Supported conversion matrix (partial):**

| From | To |
|---|---|
| String | double, int, long, decimal, date, objectId, bool, binData |
| Double | int, long, decimal, bool, date, string |
| ObjectId | string, date |
| Date | long, string, objectId |
| Bool | int, long, double, decimal, string |

### Shorthand Conversion Operators

`$toInt`, `$toLong`, `$toDouble`, `$toDecimal`, `$toDate`, `$toString`, `$toBool`, `$toObjectId`, `$toUUID`

These are equivalent to `$convert` with no `onError`/`onNull` handlers (they throw on failure).

### Critical Type Coercion Pitfalls

**1. String vs number query mismatch:**
```javascript
// WRONG: "age" stored as Int32 but querying with string
db.users.find({ age: "30" })  // returns 0 results

// RIGHT: match the stored type
db.users.find({ age: 30 })
db.users.find({ age: { $type: "int" } })
```

**2. String "false" converts to boolean `true`:**
```javascript
// $toBool converts any non-empty, non-null string to true
{ $toBool: "false" }  // returns true — counterintuitive!

// To parse "true"/"false" strings semantically:
{ $eq: ["$flagField", "true"] }
// or use $switch:
{ $switch: {
    branches: [
      { case: { $eq: ["$flag", "true"] }, then: true },
      { case: { $eq: ["$flag", "false"] }, then: false }
    ],
    default: null
}}
```

**3. Implicit coercion in arithmetic:**
```javascript
// Double arithmetic loses precision — always use Decimal128 for monetary
{ $multiply: [1.1, 3] }  // may return 3.3000000000000003
{ $multiply: [NumberDecimal("1.1"), NumberDecimal("3")] }  // returns 3.3
```

**4. Schema validation type enforcement:**
```javascript
db.createCollection("users", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["email", "age"],
      properties: {
        email: { bsonType: "string" },
        age:   { bsonType: "int", minimum: 0, maximum: 150 },
        price: { bsonType: "decimal" }
      }
    }
  }
})
```

---

## 10. UUID Best Practices

### Why Binary Subtype 4, Not String

| Aspect | String UUID | Binary Subtype 4 UUID |
|---|---|---|
| Storage size | 36 bytes (with hyphens) | 16 bytes |
| Index size | ~36 bytes per entry | ~16 bytes per entry |
| Query performance | Slower (string comparison) | Faster (binary comparison) |
| Cross-driver consistency | N/A | Consistent byte order (RFC 4122) |
| Human readability | Immediately readable | Requires conversion |

For a collection with 100M documents, string UUIDs cost ~2GB more in index space than binary UUIDs.

### UUID Representation History

MongoDB drivers historically used subtype 3 with inconsistent byte ordering:

```
Canonical UUID: 00112233-4455-6677-8899-aabbccddeeff
PyMongo (legacy):  00112233-4455-6677-8899-aabbccddeeff  (same byte order)
.NET/C# (legacy):  33221100-5544-7766-8899-aabbccddeeff  (swapped first 8 bytes)
Java (legacy):     77665544-3322-1100-ffee-ddccbbaa9988  (fully swapped)
```

Subtype 4 (STANDARD) enforces RFC 4122 byte order uniformly. **Always use subtype 4 for new applications.**

### Configuring UUID Representation per Driver

**Node.js:**
```javascript
const { UUID } = require('mongodb');
const myUUID = new UUID();          // generates random UUID as Binary subtype 4
new UUID("existing-string-uuid")   // wraps existing UUID string
```

**Python:**
```python
import uuid
import pymongo
from bson.binary import UuidRepresentation

client = pymongo.MongoClient(uri, uuidRepresentation=UuidRepresentation.STANDARD)
# Now: inserting Python uuid.UUID objects → stored as Binary subtype 4
doc = { "_id": uuid.uuid4() }  # stored as Binary subtype 4
```

**Java:**
```java
MongoClientSettings settings = MongoClientSettings.builder()
    .uuidRepresentation(UuidRepresentation.STANDARD)
    .build();
```

### UUID as `_id`: Sharding Implications

- **Random UUIDv4 as range shard key:** Inserts are uniformly distributed across shards (no hot spot), but random writes fragment the B-tree, increasing I/O and cache churn in WiredTiger.
- **Sequential ObjectId as range shard key:** Creates a write hot spot on the max shard, but is cache-friendly (append-only).
- **Best practice:** Use **hashed sharding** if using ObjectId or UUIDv7 as shard key. Use **range sharding** only on UUIDv4 if uniform write distribution is required and cache fragmentation is acceptable.
- **UUIDv7** (time-ordered UUID) provides monotonic ordering similar to ObjectId with industry-standard UUID format — best of both worlds for new systems.

```javascript
// Hashed shard key on _id avoids hot spots with sequential keys
sh.shardCollection("mydb.events", { _id: "hashed" })
```

---

## 11. BSON Limits and Size Calculations

### Hard Limits

| Limit | Value |
|---|---|
| Maximum document size | **16 mebibytes (16,777,216 bytes)** |
| Maximum nesting depth | **100 levels** |
| Maximum index key size | 1,024 bytes (configurable in some versions) |
| Maximum indexes per collection | 64 |
| Maximum fields in compound index | 32 |
| Namespace length (unsharded) | 255 bytes |
| Namespace length (sharded) | 235 bytes |

### BSON Encoding Overhead per Field

Each field in a BSON document incurs overhead:

```
Field = 1 byte (type code) + key string + 1 byte (null terminator) + value bytes
```

For a document `{ "a": 1 }`:
- `{"a":1}` = 7 bytes as plain JSON
- As BSON: 4 (doc length) + 1 (type: int32) + 2 (key "a" + null) + 4 (int32 value) + 1 (end marker) = **12 bytes**

**Practical implication:** Short field names matter. Field name `"transactionId"` (14 chars) costs 14× more per field in key overhead than `"tid"` (4 chars) across millions of documents.

### Document Size Calculation Strategy

```javascript
// Check a document's size in mongosh
Object.bsonsize(db.orders.findOne())  // returns bytes

// Estimate collection average document size
db.orders.stats().avgObjSize  // in bytes

// For very large documents, approach 16MB limit:
// 1. Move array data to separate collection + $lookup
// 2. Use GridFS for binary attachments
// 3. Apply the Bucket or Subset patterns for time-series/historical data
```

### Nesting Depth Example

```javascript
// 100 levels is the maximum
function buildNested(depth) {
  if (depth === 0) return { value: "leaf" };
  return { child: buildNested(depth - 1) };
}
db.test.insertOne(buildNested(99));   // ok (100 levels total including root)
db.test.insertOne(buildNested(100));  // error: too deep
```

### Array Size Considerations

Arrays are stored as embedded BSON documents with integer string keys (`"0"`, `"1"`, etc.). A 10,000-element integer array costs approximately:
- 10,000 × (1 type + avg 3-char key + null + 4 int32) = ~90KB

Very large arrays (thousands of elements) degrade query and update performance. Consider the Bucket Pattern (group N items per document) or moving array elements to a separate collection.

---

## References

- [BSON Types — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/bson-types/)
- [BSON Comparison/Sort Order — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/bson-type-comparison-order/)
- [MongoDB Extended JSON (v2) — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/mongodb-extended-json/)
- [MongoDB Extended JSON (v1) — MongoDB Manual](https://docs.mongodb.com/manual/reference/mongodb-extended-json-v1/)
- [ObjectId() — mongosh method](https://www.mongodb.com/docs/manual/reference/method/objectid/)
- [Model Monetary Data — MongoDB Manual](https://www.mongodb.com/docs/manual/tutorial/model-monetary-data/)
- [MongoDB Limits and Thresholds](https://www.mongodb.com/docs/manual/reference/limits/)
- [$type Query Operator](https://www.mongodb.com/docs/manual/reference/operator/query/type/)
- [$convert Aggregation Operator](https://www.mongodb.com/docs/manual/reference/operator/aggregation/convert/)
- [UUIDs — PyMongo Driver](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/data-formats/uuid/)
- [BSON Binary UUID Specification](https://specifications.readthedocs.io/en/latest/bson-binary-uuid/uuid/)
- [Work with BSON Data — Node.js Driver](https://www.mongodb.com/docs/drivers/node/current/data-formats/bson/)
- [primitive package — Go Driver](https://pkg.go.dev/go.mongodb.org/mongo-driver/bson/primitive)
- [BSON Date Developer Article](https://www.mongodb.com/developer/products/mongodb/bson-data-types-date/)
- [Decimal128 vs Double — kn8 blog](https://kn8.hashnode.dev/decimal128-vs-double-in-mongodb)

## See Also

- [[mongodb-expert]] — comprehensive MongoDB reference
- [[mongodb-schema-design]] — document modeling patterns, anti-patterns, and $jsonSchema validation
- [[mongodb-developer]] — application development patterns, CRUD, aggregation
- [[mongodb-query-performance]] — index strategies, query planner, explain plans
- [[mongodb-aggregation-pipeline]] — complete aggregation stage reference
