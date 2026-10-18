<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-developer` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-developer
version: "1.1"
updated: "2026-05-29"
origin: local
category: mongodb
description: >
  MongoDB Developer reference — all official drivers (Node.js, Python, Java, Go, C#, Rust,
  PHP, Ruby, Kotlin, Scala, C, C++), mongosh scripting, Atlas CLI, connection string construction
  and pooling configuration, error handling and retry logic, multi-document transactions,
  bulk write operations, aggregation pipelines from driver code, change streams, GridFS, and
  customer troubleshooting playbooks.
  TRIGGER: writing driver code in any official MongoDB language, constructing or debugging
  a connection string, configuring connection pooling (maxPoolSize, minPoolSize, maxIdleTimeMS),
  handling driver errors (DuplicateKeyError, ServerSelectionTimeoutError, WriteConcernError),
  implementing multi-document transactions with withTransaction(), writing bulk operations,
  running aggregation pipelines from application code, setting up change streams with resume
  tokens, using GridFS, writing mongosh scripts, using Atlas CLI for automation, or reviewing
  driver anti-patterns (new client per request, missing appName, unbounded find without limit).
  SKIP: driver internals — CMAP pool states, SDAM topology, txnNumber mechanics, CSOT
  implementation (use mongodb-driver-internals); index design (use mongodb-indexes-deep);
  schema design (use mongodb-schema-design); field-level encryption setup (use
  mongodb-encryption); Atlas platform administration beyond CLI (use mongodb-atlas-expert).
when_to_use:
  - Writing or reviewing driver code in Node.js, Python, Java, Go, C#, Rust, PHP, Ruby, Kotlin, or Scala
  - Constructing or debugging a MongoDB connection string
  - Configuring connection pooling — maxPoolSize, minPoolSize, maxIdleTimeMS, waitQueueTimeoutMS
  - Handling driver errors — DuplicateKeyError, ServerSelectionTimeoutError, WriteConcernError
  - Implementing multi-document transactions with the withTransaction() callback pattern
  - Writing ordered or unordered bulk write operations
  - Running aggregation pipelines from application code with allowDiskUse or maxTimeMS
  - Setting up change streams with resume token persistence for crash recovery
  - Using GridFS for large file storage
  - Writing mongosh scripts for maintenance, migration, or automation
  - Using the Atlas CLI for cluster management and automation
  - Reviewing driver anti-patterns — new client per request, missing appName, no projections
when_not_to_use:
  - Driver internals — CMAP pool states, SDAM topology, txnNumber mechanics, CSOT (use mongodb-driver-internals)
  - Index design, ESR rule, explain analysis (use mongodb-indexes-deep or mongodb-query-performance)
  - Schema design, embedding vs referencing, design patterns (use mongodb-schema-design)
  - Field-level encryption setup — CSFLE or Queryable Encryption (use mongodb-encryption)
  - Atlas platform administration beyond CLI automation (use mongodb-atlas-expert)
  - Change stream internals or resumability mechanics (use mongodb-change-streams)
related_skills:
  - mongodb-driver-internals
  - mongodb-schema-design
  - mongodb-query-performance
  - mongodb-encryption
  - mongodb-change-streams
  - mongodb-atlas-expert
  - mongodb-error-codes
  - mongodb-transactions
---

# MongoDB Developer Context

This local skill is generated from `docs/mongodb-developer-context.md` in an internal repository.

## When to use this skill

Use this skill when the user needs help with:
- Writing code using any MongoDB official driver (Node.js, Python, Java, Go, C#, Rust, PHP, Ruby, Kotlin, Scala, C, C++)
- Connection string construction, pooling configuration, and topology events
- Error handling, retry logic, and resilient application patterns
- Multi-document transactions and causal consistency
- Bulk write operations, ordered and unordered
- Aggregation pipelines from driver code
- Change streams from driver code
- GridFS file storage and retrieval
- mongosh commands, scripting, and automation
- Atlas CLI automation
- MongoDB error codes and their resolutions
- Atlas Admin API calls
- Atlas MCP server tools
- Schema design, index strategy, aggregation patterns
- Antipatterns and common failure modes
- Customer troubleshooting (slow queries, connection issues, auth failures, replica set elections)

Start from the bundled context below, and defer to the cited official documentation for exact APIs, commands, and edge-case behavior.

## Skill guidance

- Treat `docs/mongodb-developer-context.md` as the source document for this skill.
- Prefer the workflows, checklists, and patterns captured in the bundled context before improvising.
- Cross-reference with `mongodb-expert` skill for general MQL/aggregation depth.
- Cross-reference with `mongodb-atlas-expert` skill for Atlas-specific operational depth.
- Cross-reference with `mongodb-performance-troubleshooting` skill for deep performance analysis.
- Cross-reference with `mongodb-schema-design` skill for data modeling patterns.
- Cross-reference with `mongodb-data-lifecycle` skill for change streams and TTL details.
- Cross-reference with `mongodb-encryption` skill for CSFLE and Queryable Encryption.
- If the request is outside this topic, choose a more appropriate skill instead of forcing this one.

---

## 1. Connection Strings and URI Format

### Standard Connection String

```
mongodb://[username:password@]host1[:port1][,...hostN[:portN]][/[defaultauthdb][?options]]
```

### SRV Connection String (Atlas and DNS seedlist)

```
mongodb+srv://[username:password@]host[/[defaultauthdb][?options]]
```

SRV records provide automatic host discovery and TLS defaults. Atlas always provides SRV URIs. The driver resolves DNS SRV and TXT records to discover all mongos/replica set members.

### Common URI Options

| Option | Default | Description |
|---|---|---|
| `retryWrites` | `true` (4.2+) | Retry eligible write ops once on transient errors |
| `retryReads` | `true` (4.2+) | Retry eligible read ops once on transient errors |
| `w` | `majority` (5.0+) | Write concern |
| `readPreference` | `primary` | Where to route reads |
| `readConcernLevel` | `local` | Isolation level for reads |
| `maxPoolSize` | `100` | Max connections per server |
| `minPoolSize` | `0` | Connections maintained during idle |
| `maxIdleTimeMS` | `0` (no limit) | Max idle time before a connection is closed |
| `connectTimeoutMS` | `10000` | TCP connect timeout |
| `socketTimeoutMS` | `0` (no limit) | Socket read/write timeout |
| `serverSelectionTimeoutMS` | `30000` | Time to find suitable server |
| `heartbeatFrequencyMS` | `10000` | Frequency of server monitoring |
| `appName` | none | Identifier shown in `$currentOp` and logs |
| `compressors` | none | `snappy`, `zlib`, `zstd` for wire compression |
| `authMechanism` | `SCRAM-SHA-256` | Auth mechanism |
| `tls` | `true` for SRV | Enable TLS |
| `directConnection` | `false` | Connect to a single host without discovery |

### Connection String Best Practices

1. Always set `appName` so ops teams can trace connections in server logs.
2. Use SRV connection strings for Atlas and any DNS-seedlist deployment.
3. Never hard-code credentials; use environment variables or a secrets manager.
4. Set `compressors=zstd` for bandwidth-sensitive workloads (requires server and driver support).
5. For serverless functions (Lambda, Cloud Functions), set `maxPoolSize=1` and `maxIdleTimeMS=10000` to avoid connection exhaustion.
6. Set `retryWrites=true&retryReads=true` explicitly in shared URIs for clarity (both are default since 4.2).

---

## 2. Connection Pooling

### How Pools Work

Each `MongoClient` maintains a pool of TCP connections **per server** (per replica set member or mongos). When your application requests an operation, the driver checks out a connection from the pool, executes the operation, and returns the connection.

### Key Pool Parameters

| Parameter | Default | Guidance |
|---|---|---|
| `maxPoolSize` | 100 | Set to expected peak concurrent operations per server. Too high wastes server file descriptors; too low causes wait-queue stalls. |
| `minPoolSize` | 0 | Set >0 in long-running services to avoid cold-start latency on first burst. |
| `maxConnecting` | 2 | Max simultaneous connection establishments. Increase in high-churn environments. |
| `maxIdleTimeMS` | 0 | Set to 60000-300000 in serverless or bursty workloads to reclaim idle connections. |
| `waitQueueTimeoutMS` | 0 (no timeout) | Time a thread waits for a pooled connection. Set to avoid indefinite blocking. |

### The Golden Rule: One Client Per Application

Create a **single `MongoClient`** instance and share it across your application. The client is thread-safe (or goroutine-safe, or async-safe) in every official driver. Opening a new client per request is the most common pooling antipattern.

### Pool Monitoring Events

All drivers emit connection pool events for observability:
- `connectionPoolCreated` / `connectionPoolClosed`
- `connectionCreated` / `connectionClosed`
- `connectionCheckedOut` / `connectionCheckedIn`
- `connectionCheckOutFailed` / `connectionCheckOutStarted`
- `connectionPoolCleared`

Subscribe to these events to track pool saturation, connection churn, and wait-queue depth.

### Pool Tuning by Environment

| Environment | `maxPoolSize` | `minPoolSize` | `maxIdleTimeMS` | Notes |
|---|---|---|---|---|
| Long-running web server | 100-200 | 10-25 | 300000 | Stable pool, low churn |
| Serverless (Lambda) | 1 | 0 | 10000 | One connection per invocation |
| Microservice (moderate) | 25-50 | 5 | 120000 | Right-size to actual concurrency |
| Batch/ETL job | 50-100 | 0 | 60000 | Burst then release |

---

## 3. Driver Patterns by Language

### 3.1 Node.js (mongodb package)

**Installation**: `npm install mongodb`

**Singleton Pattern**:
```javascript
// lib/db.js
import { MongoClient } from 'mongodb';

const uri = process.env.MONGODB_URI;
const client = new MongoClient(uri, {
  maxPoolSize: 50,
  minPoolSize: 5,
  maxIdleTimeMS: 120000,
  retryWrites: true,
  retryReads: true,
  compressors: ['zstd'],
  appName: 'my-node-service',
});

let dbPromise;
export function getDb(dbName = 'mydb') {
  if (!dbPromise) {
    dbPromise = client.connect().then(() => client.db(dbName));
  }
  return dbPromise;
}
```

**Error Handling**:
```javascript
import { MongoServerError, MongoNetworkError } from 'mongodb';

try {
  await collection.insertOne(doc);
} catch (err) {
  if (err instanceof MongoServerError) {
    if (err.code === 11000) {
      // Duplicate key — handle idempotency
    }
  } else if (err instanceof MongoNetworkError) {
    // Network issue — retryWrites handles single retries automatically
  }
}
```

**Topology Events**:
```javascript
client.on('serverHeartbeatFailed', (event) => {
  logger.warn('Heartbeat failed', { host: event.connectionId, failure: event.failure });
});
client.on('topologyDescriptionChanged', (event) => {
  const newPrimary = [...event.newDescription.servers.values()]
    .find(s => s.type === 'RSPrimary');
  if (newPrimary) logger.info('New primary', { host: newPrimary.address });
});
```

**Graceful Shutdown**:
```javascript
process.on('SIGTERM', async () => {
  await client.close();
  process.exit(0);
});
```

### 3.2 Python (PyMongo)

**Installation**: `pip install pymongo[srv]`

**Singleton Pattern**:
```python
# db.py
from pymongo import MongoClient
import os

_client = None

def get_client():
    global _client
    if _client is None:
        _client = MongoClient(
            os.environ["MONGODB_URI"],
            maxPoolSize=50,
            minPoolSize=5,
            maxIdleTimeMS=120000,
            retryWrites=True,
            retryReads=True,
            appName="my-python-service",
        )
    return _client

def get_db(db_name="mydb"):
    return get_client()[db_name]
```

**Error Handling**:
```python
from pymongo.errors import (
    DuplicateKeyError,
    ConnectionFailure,
    OperationFailure,
    ServerSelectionTimeoutError,
    AutoReconnect,
    WriteConcernError,
)

try:
    collection.insert_one(doc)
except DuplicateKeyError:
    # Handle idempotent insert
    pass
except ConnectionFailure as e:
    # Includes AutoReconnect; driver retries once automatically
    logger.error(f"Connection failure: {e}")
except ServerSelectionTimeoutError:
    # No suitable server found within serverSelectionTimeoutMS
    logger.critical("Cannot reach any MongoDB server")
except OperationFailure as e:
    logger.error(f"Operation failed: code={e.code}, details={e.details}")
```

**Motor (Async PyMongo)**:
```python
import motor.motor_asyncio

client = motor.motor_asyncio.AsyncIOMotorClient(
    os.environ["MONGODB_URI"],
    maxPoolSize=50,
)
db = client["mydb"]

async def insert_doc(doc):
    result = await db.collection.insert_one(doc)
    return result.inserted_id
```

### 3.3 Java (mongodb-driver-sync / mongodb-driver-reactivestreams)

**Maven Dependency** (sync driver):
```xml
<dependency>
  <groupId>org.mongodb</groupId>
  <artifactId>mongodb-driver-sync</artifactId>
  <version>5.4.0</version>
</dependency>
```

**Client Setup**:
```java
import com.mongodb.ConnectionString;
import com.mongodb.MongoClientSettings;
import com.mongodb.client.MongoClients;
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoDatabase;
import java.util.concurrent.TimeUnit;

MongoClientSettings settings = MongoClientSettings.builder()
    .applyConnectionString(new ConnectionString(System.getenv("MONGODB_URI")))
    .applyToConnectionPoolSettings(builder ->
        builder.maxSize(100)
               .minSize(10)
               .maxConnectionIdleTime(120, TimeUnit.SECONDS)
               .maxWaitTime(5, TimeUnit.SECONDS)
               .maxConnectionLifeTime(30, TimeUnit.MINUTES))
    .applicationName("my-java-service")
    .retryWrites(true)
    .retryReads(true)
    .build();

MongoClient client = MongoClients.create(settings);
MongoDatabase db = client.getDatabase("mydb");
```

**Error Handling**:
```java
import com.mongodb.MongoWriteException;
import com.mongodb.MongoCommandException;
import com.mongodb.MongoTimeoutException;
import com.mongodb.ErrorCategory;

try {
    collection.insertOne(doc);
} catch (MongoWriteException e) {
    if (e.getError().getCategory() == ErrorCategory.DUPLICATE_KEY) {
        // Duplicate key — handle idempotency
    }
} catch (MongoTimeoutException e) {
    // Connection pool exhausted or server selection timed out
} catch (MongoCommandException e) {
    logger.error("Command failed: code={}, message={}", e.getCode(), e.getMessage());
}
```

**Spring Data MongoDB Integration**:
```java
@Configuration
public class MongoConfig extends AbstractMongoClientConfiguration {
    @Override
    protected String getDatabaseName() {
        return "mydb";
    }
    // MongoClient bean is auto-configured from spring.data.mongodb.uri
}
```

### 3.4 Go (go.mongodb.org/mongo-driver v2)

**Installation**: `go get go.mongodb.org/mongo-driver/v2/mongo`

**Client Setup**:
```go
package main

import (
    "context"
    "os"
    "time"
    "go.mongodb.org/mongo-driver/v2/mongo"
    "go.mongodb.org/mongo-driver/v2/mongo/options"
)

func newClient(ctx context.Context) (*mongo.Client, error) {
    opts := options.Client().
        ApplyURI(os.Getenv("MONGODB_URI")).
        SetMaxPoolSize(100).
        SetMinPoolSize(10).
        SetMaxConnecting(5).
        SetMaxConnIdleTime(2 * time.Minute).
        SetConnectTimeout(10 * time.Second).
        SetServerSelectionTimeout(15 * time.Second).
        SetAppName("my-go-service").
        SetRetryWrites(true).
        SetRetryReads(true).
        SetCompressors([]string{"zstd"})

    client, err := mongo.Connect(ctx, opts)
    if err != nil {
        return nil, err
    }

    // Verify connectivity
    if err := client.Ping(ctx, nil); err != nil {
        return nil, err
    }
    return client, nil
}
```

**Error Handling**:
```go
import "go.mongodb.org/mongo-driver/v2/mongo"

_, err := collection.InsertOne(ctx, doc)
if err != nil {
    if mongo.IsDuplicateKeyError(err) {
        // Handle duplicate
    } else if mongo.IsNetworkError(err) {
        // Network error — retryWrites handled one retry
    } else if mongo.IsTimeout(err) {
        // Server selection or socket timeout
    }
}
```

### 3.5 C# (.NET Driver)

**NuGet**: `MongoDB.Driver`

```csharp
using MongoDB.Driver;

var settings = MongoClientSettings.FromConnectionString(
    Environment.GetEnvironmentVariable("MONGODB_URI"));
settings.MaxConnectionPoolSize = 100;
settings.MinConnectionPoolSize = 10;
settings.MaxConnectionIdleTime = TimeSpan.FromMinutes(2);
settings.RetryWrites = true;
settings.RetryReads = true;
settings.ApplicationName = "my-dotnet-service";

var client = new MongoClient(settings);
var db = client.GetDatabase("mydb");
```

---

## 4. Retryable Writes and Reads

### Retryable Writes

Enabled by default since MongoDB 4.2. The driver automatically retries eligible write operations **exactly once** after a transient network error or a failover.

**Eligible operations**: `insertOne`, `updateOne`, `replaceOne`, `deleteOne`, `findOneAndUpdate`, `findOneAndReplace`, `findOneAndDelete`, `insertMany` (ordered or unordered), `bulkWrite` (ordered or unordered).

**NOT retryable**:
- `updateMany`, `deleteMany` (not idempotent at the protocol level)
- Writes with `w: 0` (unacknowledged)
- Individual writes within an explicit transaction (the transaction itself is retried)

**Error Labels**:
- `RetryableWriteError` — the driver retries automatically
- `NoWritesPerformed` (MongoDB 6.1+) — both attempts failed without writing; safe to retry at app layer
- `TransientTransactionError` — retry the entire transaction
- `UnknownTransactionCommitResult` — retry `commitTransaction()`

### Retryable Reads

Enabled by default since MongoDB 4.2. The driver retries eligible read operations **exactly once** after transient network errors.

**Eligible operations**: `find`, `findOne`, `aggregate` (without `$out`/`$merge`), `distinct`, `count`, `estimatedDocumentCount`, `listDatabases`, `listCollections`, `listIndexes`.

### Building a Resilient Application

```javascript
// Node.js — custom retry wrapper for non-retryable operations
async function withRetry(fn, maxRetries = 3, baseDelay = 100) {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      const isTransient = err.hasErrorLabel?.('TransientTransactionError')
        || err.hasErrorLabel?.('RetryableWriteError')
        || err instanceof MongoNetworkError;

      if (!isTransient || attempt === maxRetries) throw err;

      const delay = baseDelay * Math.pow(2, attempt) + Math.random() * 100;
      await new Promise(r => setTimeout(r, delay));
    }
  }
}
```

---

## 5. Error Handling Reference

### Common Error Codes

| Code | Name | Cause | Action |
|---|---|---|---|
| 11000 | DuplicateKey | Unique index violation | Use upsert or catch and skip |
| 11600 | InterruptedAtShutdown | Server shutting down | Retry on new primary |
| 11602 | InterruptedDueToReplStateChange | Election in progress | Retry (driver does this) |
| 13 | Unauthorized | Auth failure | Check credentials and roles |
| 18 | AuthenticationFailed | Bad credentials | Verify user, password, authSource |
| 50 | MaxTimeMSExpired | Operation hit maxTimeMS | Optimize query or increase limit |
| 89 | NetworkTimeout | Socket timeout | Check network, increase socketTimeoutMS |
| 91 | ShutdownInProgress | Cluster node draining | Retry on healthy node |
| 112 | WriteConflict | WiredTiger write conflict | Retry the operation or transaction |
| 211 | KeyNotFound | Missing expected key | Usually internal — check for data corruption |
| 290 | TransactionExceededLifetimeLimitSeconds | Transaction >60s default | Break into smaller transactions |
| 10107 | NotWritablePrimary | Write to secondary | Driver re-selects primary automatically |
| 13435 | NotPrimaryNoSecondaryOk | Read from non-primary with primary preference | Check readPreference |
| 16500 | TooManyRequests (Atlas) | Rate-limited in serverless | Implement backoff or reduce request rate |

### Error Handling Strategy Checklist

1. Let the driver handle retryable errors (retryWrites/retryReads).
2. Catch `DuplicateKeyError` (11000) for idempotent upserts.
3. Catch `ServerSelectionTimeoutError` for connectivity failures and alert.
4. Catch `WriteConcernError` when `w: majority` cannot be satisfied.
5. Catch `MaxTimeMSExpired` (50) and investigate slow queries.
6. Wrap bulk operations to inspect `BulkWriteError.writeErrors` array.
7. Log error codes, not just messages, for searchability.
8. Never swallow errors silently; always log or propagate.

---

## 6. Multi-Document Transactions

### When to Use

- Use transactions when business logic requires atomic updates across multiple documents or collections.
- Prefer single-document atomicity when possible; redesign schemas before reaching for transactions.
- Transactions are supported on replica sets (4.0+) and sharded clusters (4.2+).

### Transaction Lifecycle

```
startSession() -> startTransaction() -> operations -> commitTransaction() / abortTransaction()
```

### Production Constraints

| Constraint | Value |
|---|---|
| Default max runtime | 60 seconds (`transactionLifetimeLimitSeconds`) |
| Max oplog entry size | 16 MB |
| Recommended max documents modified | 1,000 per transaction |
| WiredTiger cache pressure | Transactions hold snapshots; long-running txns increase cache pressure |
| Write conflicts | Optimistic concurrency: first writer wins, conflict aborts the loser |
| DDL operations | Not allowed inside transactions (createCollection, createIndex, etc.) |

### Transaction Patterns by Language

**Node.js**:
```javascript
const session = client.startSession();
try {
  await session.withTransaction(async () => {
    await orders.insertOne({ item: 'widget', qty: 10 }, { session });
    await inventory.updateOne(
      { item: 'widget' },
      { $inc: { qty: -10 } },
      { session }
    );
  });
} finally {
  await session.endSession();
}
```

**Python**:
```python
with client.start_session() as session:
    def txn_body(s):
        orders.insert_one({"item": "widget", "qty": 10}, session=s)
        inventory.update_one(
            {"item": "widget"},
            {"$inc": {"qty": -10}},
            session=s,
        )
    session.with_transaction(txn_body)
```

**Java**:
```java
try (ClientSession session = client.startSession()) {
    session.withTransaction(() -> {
        orders.insertOne(session, new Document("item", "widget").append("qty", 10));
        inventory.updateOne(session,
            Filters.eq("item", "widget"),
            Updates.inc("qty", -10));
        return null;
    });
}
```

**Go**:
```go
sess, err := client.StartSession()
if err != nil { return err }
defer sess.EndSession(ctx)

_, err = sess.WithTransaction(ctx, func(sc mongo.SessionContext) (interface{}, error) {
    _, err := orders.InsertOne(sc, bson.D{{"item", "widget"}, {"qty", 10}})
    if err != nil { return nil, err }
    _, err = inventory.UpdateOne(sc,
        bson.D{{"item", "widget"}},
        bson.D{{"$inc", bson.D{{"qty", -10}}}})
    return nil, err
})
```

### Transaction Retry Pattern

Use `withTransaction()` (available in all drivers) instead of manual `startTransaction()`/`commitTransaction()`. The helper automatically retries on `TransientTransactionError` and retries commit on `UnknownTransactionCommitResult`.

If using manual control:
```javascript
async function runTransaction(session, txnFn) {
  while (true) {
    try {
      session.startTransaction();
      await txnFn(session);
      while (true) {
        try {
          await session.commitTransaction();
          return; // success
        } catch (commitErr) {
          if (commitErr.hasErrorLabel('UnknownTransactionCommitResult')) {
            continue; // retry commit
          }
          throw commitErr;
        }
      }
    } catch (err) {
      if (err.hasErrorLabel('TransientTransactionError')) {
        continue; // retry entire transaction
      }
      throw err;
    }
  }
}
```

### Transaction Anti-Patterns

1. Transactions lasting >5 seconds (increases WiredTiger cache pressure and conflict risk).
2. Modifying >1,000 documents in a single transaction.
3. Using transactions for single-document operations (unnecessary overhead).
4. Not using `withTransaction()` helper (loses automatic retry logic).
5. Running DDL inside transactions (createCollection, createIndex).
6. Relying on transactions instead of redesigning schema for single-document atomicity.

---

## 7. Bulk Operations

### Ordered vs Unordered

| Mode | Behavior | Use When |
|---|---|---|
| Ordered (`ordered: true`) | Stops on first error | Insert order matters, or you need early failure |
| Unordered (`ordered: false`) | Continues past errors, reports all at end | Maximizing throughput, tolerating partial failures |

### Bulk Write Pattern by Language

**Node.js**:
```javascript
const result = await collection.bulkWrite([
  { insertOne: { document: { name: 'A', value: 1 } } },
  { updateOne: { filter: { name: 'B' }, update: { $set: { value: 2 } } } },
  { deleteOne: { filter: { name: 'C' } } },
  { replaceOne: { filter: { name: 'D' }, replacement: { name: 'D', value: 4 } } },
], { ordered: false });

console.log(`Inserted: ${result.insertedCount}, Modified: ${result.modifiedCount}`);
```

**Python**:
```python
from pymongo import InsertOne, UpdateOne, DeleteOne, ReplaceOne

result = collection.bulk_write([
    InsertOne({"name": "A", "value": 1}),
    UpdateOne({"name": "B"}, {"$set": {"value": 2}}),
    DeleteOne({"name": "C"}),
    ReplaceOne({"name": "D"}, {"name": "D", "value": 4}),
], ordered=False)
```

**Java**:
```java
List<WriteModel<Document>> writes = List.of(
    new InsertOneModel<>(new Document("name", "A").append("value", 1)),
    new UpdateOneModel<>(Filters.eq("name", "B"), Updates.set("value", 2)),
    new DeleteOneModel<>(Filters.eq("name", "C")),
    new ReplaceOneModel<>(Filters.eq("name", "D"), new Document("name", "D").append("value", 4))
);
BulkWriteResult result = collection.bulkWrite(writes, new BulkWriteOptions().ordered(false));
```

**Go**:
```go
models := []mongo.WriteModel{
    mongo.NewInsertOneModel().SetDocument(bson.D{{"name", "A"}, {"value", 1}}),
    mongo.NewUpdateOneModel().SetFilter(bson.D{{"name", "B"}}).SetUpdate(bson.D{{"$set", bson.D{{"value", 2}}}}),
    mongo.NewDeleteOneModel().SetFilter(bson.D{{"name", "C"}}),
}
opts := options.BulkWrite().SetOrdered(false)
result, err := collection.BulkWrite(ctx, models, opts)
```

### Client-Level Bulk Write (MongoDB 8.0+)

MongoDB 8.0 introduced client-level `bulkWrite()` that can write to **multiple collections and databases** in a single network round-trip:

```javascript
// Node.js — client-level bulk write across namespaces
const result = await client.bulkWrite([
  {
    namespace: 'mydb.orders',
    name: 'insertOne',
    document: { orderId: 1, status: 'new' },
  },
  {
    namespace: 'mydb.inventory',
    name: 'updateOne',
    filter: { sku: 'ABC' },
    update: { $inc: { qty: -1 } },
  },
]);
```

### Bulk Operation Best Practices

1. Use **unordered** for maximum throughput when order does not matter.
2. Batch sizes: the driver auto-batches into 100,000-operation groups. For very large imports, chunk at the application level.
3. Catch `BulkWriteError` and inspect `writeErrors` to identify which operations failed.
4. Use `upsert: true` in UpdateOne/ReplaceOne models for idempotent loads.
5. For multi-million-row imports, use `mongoimport` or `mongorestore` instead of driver bulk writes.

---

## 8. Aggregation from Drivers

### Running Pipelines

All drivers support `collection.aggregate(pipeline, options)`. Key options:

| Option | Purpose |
|---|---|
| `allowDiskUse` | Let stages spill to disk when exceeding 100 MB memory limit |
| `batchSize` | Cursor batch size for large result sets |
| `maxTimeMS` | Abort if pipeline exceeds time limit |
| `collation` | Language-specific string comparison |
| `hint` | Force a specific index for `$match` |
| `let` | Pass variables into the pipeline |
| `comment` | Attach metadata for profiler/log correlation |

### Pipeline Patterns in Code

**Node.js**:
```javascript
const cursor = collection.aggregate([
  { $match: { status: 'active', createdAt: { $gte: cutoff } } },
  { $group: { _id: '$category', total: { $sum: '$amount' } } },
  { $sort: { total: -1 } },
  { $limit: 10 },
], { allowDiskUse: true, maxTimeMS: 30000 });

for await (const doc of cursor) {
  console.log(doc);
}
```

**Python**:
```python
pipeline = [
    {"$match": {"status": "active", "createdAt": {"$gte": cutoff}}},
    {"$group": {"_id": "$category", "total": {"$sum": "$amount"}}},
    {"$sort": {"total": -1}},
    {"$limit": 10},
]
for doc in collection.aggregate(pipeline, allowDiskUse=True, maxTimeMS=30000):
    print(doc)
```

### Aggregation Best Practices

1. Place `$match` and `$project` as early as possible to reduce documents flowing through the pipeline.
2. Use `$match` before `$lookup` to limit the join scope.
3. Set `allowDiskUse: true` only when necessary (large groupings/sorts).
4. Use `maxTimeMS` to prevent runaway pipelines.
5. Use `$merge` or `$out` for materialized views, not in-app aggregation.
6. Use `explain('executionStats')` to verify index utilization in `$match` stages.

---

## 9. Change Streams from Drivers

### Opening a Change Stream

```javascript
// Node.js — watch a collection
const changeStream = collection.watch(
  [{ $match: { operationType: { $in: ['insert', 'update'] } } }],
  {
    fullDocument: 'updateLookup',          // or 'whenAvailable' (6.0+)
    fullDocumentBeforeChange: 'whenAvailable', // pre-image (6.0+)
    resumeAfter: savedResumeToken,         // resume from last position
    maxAwaitTimeMS: 5000,
  }
);

changeStream.on('change', (event) => {
  console.log(event.operationType, event.fullDocument);
  // Persist event._id (resume token) for crash recovery
});
changeStream.on('error', (err) => {
  // Driver auto-resumes on transient errors since 4.2
  // For non-resumable errors, restart the change stream
});
```

**Python**:
```python
with collection.watch(
    [{"$match": {"operationType": {"$in": ["insert", "update"]}}}],
    full_document="updateLookup",
    resume_after=saved_resume_token,
) as stream:
    for change in stream:
        process(change)
        save_resume_token(change["_id"])
```

### Change Stream Best Practices

1. **Always persist resume tokens** — store in a separate collection or external store for crash recovery.
2. Use `fullDocument: 'updateLookup'` when you need the complete document after an update.
3. Use `fullDocumentBeforeChange: 'whenAvailable'` (6.0+) for audit trails.
4. Filter early with `$match` in the pipeline to reduce network traffic.
5. Handle `invalidate` events (dropped collection, renamed collection) by reopening the stream.
6. For cross-collection CDC, watch at the database level: `db.watch()`.
7. For cluster-wide events, watch at the client level: `client.watch()`.

---

## 10. GridFS

### When to Use

- Files larger than 16 MB BSON document limit.
- Storing files alongside metadata in MongoDB without a separate file service.
- Accessing portions of large files without loading the entire file into memory.
- Keeping files synchronized across distributed deployments.

### How GridFS Works

GridFS stores each file as two sets of documents:
- `fs.files` — metadata (filename, length, chunkSize, uploadDate, md5, contentType)
- `fs.chunks` — binary data in 255 KB chunks (default), indexed by `files_id` + `n`

### GridFS by Language

**Node.js**:
```javascript
import { GridFSBucket } from 'mongodb';
import fs from 'fs';

const bucket = new GridFSBucket(db, { bucketName: 'attachments', chunkSizeBytes: 1024 * 255 });

// Upload
const uploadStream = bucket.openUploadStream('report.pdf', {
  metadata: { author: 'user123', department: 'finance' },
});
fs.createReadStream('/path/to/report.pdf').pipe(uploadStream);

// Download
const downloadStream = bucket.openDownloadStreamByName('report.pdf');
downloadStream.pipe(fs.createWriteStream('/tmp/report.pdf'));

// Delete
await bucket.delete(fileId);
```

**Python**:
```python
from gridfs import GridIn, GridOut
import gridfs

bucket = gridfs.GridFS(db, collection="attachments")

# Upload
with open("/path/to/report.pdf", "rb") as f:
    file_id = bucket.put(f, filename="report.pdf", metadata={"author": "user123"})

# Download
grid_out = bucket.get(file_id)
with open("/tmp/report.pdf", "wb") as f:
    f.write(grid_out.read())

# Delete
bucket.delete(file_id)
```

### GridFS Best Practices

1. Use GridFS only for files >16 MB. For smaller files, store as `BinData` in documents.
2. Set appropriate `chunkSizeBytes` — smaller chunks for random-access reads, larger for sequential streaming.
3. Index `fs.files` on fields you query (e.g., `metadata.author`, `filename`).
4. Use streaming APIs (not `readAll`) to avoid loading entire files into memory.
5. Consider Atlas Data Lake or S3 for very large-scale file storage; GridFS is not a CDN replacement.

---

## 11. mongosh Scripting and Automation

### Running Scripts

```bash
# Execute a script file
mongosh "mongodb+srv://cluster.example.net/mydb" --file maintenance.js

# Evaluate inline
mongosh "mongodb+srv://cluster.example.net/mydb" --eval 'db.users.countDocuments({})'

# With auth
mongosh "mongodb+srv://cluster.example.net/mydb" \
  --username admin --password "$MONGO_PWD" \
  --authenticationDatabase admin \
  --file migration.js

# Quiet mode (suppress banner)
mongosh --quiet --file script.js
```

### Inside mongosh

```javascript
// Load another script
load('/path/to/helpers.js');

// Use async/await (ES2022+ environment)
const count = await db.orders.countDocuments({ status: 'pending' });
print(`Pending orders: ${count}`);

// Iterate with cursor
const cursor = db.products.find({ price: { $gt: 100 } });
while (cursor.hasNext()) {
  const doc = cursor.next();
  printjson(doc);
}

// Aggregation
const results = db.sales.aggregate([
  { $group: { _id: '$region', total: { $sum: '$amount' } } },
  { $sort: { total: -1 } },
]);
results.forEach(printjson);
```

### Common Maintenance Scripts

```javascript
// Reindex a collection
db.runCommand({ reIndex: 'myCollection' });

// Kill long-running operations
db.currentOp({ secs_running: { $gte: 60 }, op: { $ne: 'none' } }).inprog.forEach(op => {
  print(`Killing op ${op.opid}: ${op.ns} running ${op.secs_running}s`);
  db.killOp(op.opid);
});

// Check replica set status
const status = rs.status();
status.members.forEach(m => {
  print(`${m.name}: ${m.stateStr}, optime: ${m.optimeDate}`);
});

// Compact a collection (reclaim disk space)
db.runCommand({ compact: 'myCollection' });
```

### mongosh Configuration

```javascript
// ~/.mongoshrc.js — auto-loaded on startup
config.set('inspectDepth', 10);
config.set('historyLength', 5000);
prompt = () => `${db.getName()}> `;
```

### mongosh Best Practices

1. Use `--file` for repeatable scripts, not interactive copy-paste.
2. Use `--quiet` in CI/CD to suppress the mongosh banner.
3. Use `printjson()` for structured output; `print()` for plain text.
4. Store maintenance scripts in version control alongside application code.
5. Use `--eval` for one-liners in shell scripts and cron jobs.
6. mongosh supports full ES2022+: use `async/await`, destructuring, `for...of`, and template literals.
7. Use `.mongoshrc.js` for custom prompts, helpers, and default config.

---

## 12. Common Driver Anti-Patterns

### Connection Anti-Patterns

| Anti-Pattern | Why It Hurts | Fix |
|---|---|---|
| New client per request | Exhausts server connections, slow startup | Share one client per app |
| Not setting appName | Cannot trace connections in server logs | Always set `appName` |
| Ignoring serverSelectionTimeoutMS | App hangs indefinitely during outage | Set explicit timeout |
| Not closing client on shutdown | Leaked connections, file descriptor exhaustion | Handle SIGTERM/SIGINT |
| Using directConnection in production | Bypasses failover, breaks HA | Use replica set URI |

### Query Anti-Patterns

| Anti-Pattern | Why It Hurts | Fix |
|---|---|---|
| Not using projections | Transfers unnecessary data | Specify only needed fields |
| Missing indexes on query fields | Full collection scans | Create appropriate indexes |
| Using `$where` or `$expr` with JS | Slow, cannot use indexes | Rewrite with MQL operators |
| Unbounded `find()` without limit | Crashes on large collections | Always use limit + pagination |
| Sorting without index support | In-memory sort, 100 MB limit | Create compound index covering sort |

### Write Anti-Patterns

| Anti-Pattern | Why It Hurts | Fix |
|---|---|---|
| Large documents (>5 MB) | Slow transfers, WiredTiger overhead | Subset or bucket pattern |
| Unbounded array growth | Document exceeds 16 MB, poor cache utilization | Cap arrays or use separate collection |
| update without `$set` | Replaces entire document | Use update operators |
| Missing write concern validation | Silent data loss on failover | Use `w: 'majority'` |
| Not handling duplicate key errors | Application crashes on retries | Catch error code 11000 |

---

## 13. Driver Version Matrix

| Language | Package | Current Stable | Min Server | Key Features |
|---|---|---|---|---|
| Node.js | `mongodb` | 6.x | 3.6 | Native Promises, TypeScript types |
| Python | `pymongo` | 4.x | 3.7 | Async via Motor, type hints |
| Java Sync | `mongodb-driver-sync` | 5.x | 3.6 | Builder pattern, POJOs |
| Java Reactive | `mongodb-driver-reactivestreams` | 5.x | 3.6 | Project Reactor compatible |
| Go | `mongo-driver/v2` | 2.x | 3.6 | Context-based, generics |
| C# (.NET) | `MongoDB.Driver` | 3.x | 3.6 | LINQ provider, async |
| Rust | `mongodb` | 3.x | 3.6 | Tokio async, serde integration |
| PHP | `mongodb` (ext) + `mongodb/mongodb` (lib) | 2.x + 1.x | 3.6 | Extension + library split |
| Ruby | `mongo` | 2.x | 3.6 | Mongoid ODM integration |
| Kotlin | `mongodb-driver-kotlin-sync` | 5.x | 3.6 | Data classes, coroutines |
| Scala | `mongo-scala-driver` | 5.x | 3.6 | Observables, case classes |

---

## 14. Resilient Application Checklist

Use this checklist when reviewing any application that connects to MongoDB:

- [ ] **Single client instance** shared across the application
- [ ] **Connection string** uses SRV format for Atlas / DNS seedlist deployments
- [ ] **appName** set for observability
- [ ] **retryWrites** and **retryReads** enabled (default since 4.2)
- [ ] **Write concern** set to `majority` for durability
- [ ] **Read preference** matches the use case (primary for consistency, secondary for read scale)
- [ ] **maxPoolSize** right-sized for deployment environment
- [ ] **serverSelectionTimeoutMS** set to a reasonable value (not infinite)
- [ ] **Graceful shutdown** closes the client
- [ ] **Error handling** catches specific error types, not generic exceptions
- [ ] **Duplicate key errors** handled for idempotent operations
- [ ] **Transactions** use `withTransaction()` helper with automatic retry
- [ ] **Projections** used to limit returned fields
- [ ] **Indexes** cover query patterns (ESR rule)
- [ ] **maxTimeMS** set on long-running queries and aggregations
- [ ] **Change stream resume tokens** persisted for crash recovery
- [ ] **Monitoring events** wired to observability stack (pool events, command events, SDAM events)

---

## References

### Official Driver Documentation
- [Node.js Driver](https://www.mongodb.com/docs/drivers/node/current/)
- [PyMongo Driver](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/)
- [Java Sync Driver](https://www.mongodb.com/docs/drivers/java/sync/current/)
- [Go Driver](https://www.mongodb.com/docs/drivers/go/current/)
- [C#/.NET Driver](https://www.mongodb.com/docs/drivers/csharp/current/)
- [Rust Driver](https://www.mongodb.com/docs/drivers/rust/current/)

### Connection and Pooling
- [Connection Pool Overview](https://www.mongodb.com/docs/manual/administration/connection-pool-overview/)
- [Tuning Connection Pool Settings](https://www.mongodb.com/docs/manual/tutorial/connection-pool-performance-tuning/)
- [Node.js Connection Pools](https://www.mongodb.com/docs/drivers/node/current/connect/connection-options/connection-pools/)
- [PyMongo Connection Pools](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/connect/connection-options/connection-pools/)
- [Java Connection Pools](https://www.mongodb.com/docs/drivers/java/sync/current/connection/specify-connection-options/connection-pools/)

### Retryable Operations
- [Retryable Writes](https://www.mongodb.com/docs/manual/core/retryable-writes/)
- [Retryable Reads](https://www.mongodb.com/docs/manual/core/retryable-reads/)
- [Build a Resilient Application](https://www.mongodb.com/docs/cloud-manager/reference/resilient-application/)

### Transactions
- [Transactions — Production Considerations](https://www.mongodb.com/docs/manual/core/transactions-production-consideration/)
- [Transactions — Sharded Clusters](https://www.mongodb.com/docs/manual/core/transactions-sharded-clusters/)
- [Performance Best Practices: Transactions](https://www.mongodb.com/company/blog/technical/performance-best-practices-transactions-and-read-write-concerns)

### GridFS
- [GridFS Manual](https://www.mongodb.com/docs/manual/core/gridfs/)
- [PyMongo GridFS](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/crud/gridfs/)

### mongosh
- [Write Scripts](https://www.mongodb.com/docs/mongodb-shell/write-scripts/)
- [Script Considerations](https://www.mongodb.com/docs/mongodb-shell/write-scripts/considerations/)
- [Run Commands](https://www.mongodb.com/docs/mongodb-shell/run-commands/)

### Specifications
- [Connection Monitoring and Pooling Spec](https://github.com/mongodb/specifications/blob/master/source/connection-monitoring-and-pooling/connection-monitoring-and-pooling.md)
- [Retryable Writes Spec](https://github.com/mongodb/specifications/blob/master/source/retryable-writes/retryable-writes.md)
- [Retryable Reads Spec](https://github.com/mongodb/specifications/blob/master/source/retryable-reads/retryable-reads.md)
