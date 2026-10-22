<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-drivers-k8s` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-drivers-k8s
description: "MongoDB driver patterns (Node.js, Python, Java, Go) and Kubernetes operator — connection management, transactions, change streams, retry patterns, and StatefulSet configuration. TRIGGER: MongoDB driver code, transactions, change streams, or Kubernetes (Community/Enterprise/Atlas operator) deployments. SKIP: Atlas UI-only tasks (use mongodb-atlas-expert), schema design (use mongodb-schema-design), sharding config (use mongodb-sharding)."
category: mongodb
version: "1.1.0"
updated: "2026-05-29"
when_to_use:
  - "Writing or debugging MongoDB driver code in Node.js, Python, Java, or Go"
  - "Designing connection pooling, read preferences, or write concern strategies"
  - "Implementing multi-document transactions or change streams"
  - "Deploying MongoDB on Kubernetes via Community, Enterprise, or Atlas operator"
  - "Troubleshooting driver-level connection issues, slow queries, or failover behavior"
  - "Configuring StatefulSets, PVCs, TLS, or operator CRDs for MongoDB"
  - "Implementing retry patterns for TransientTransactionError or UnknownTransactionCommitResult"
  - "Setting up MongoClient singleton patterns for serverless or containerized apps"
keywords:
  - "mongodb node.js driver"
  - "pymongo"
  - "motor async mongodb"
  - "mongodb java driver"
  - "go mongodb driver"
  - "mongodb transactions"
  - "mongodb change streams"
  - "mongodb connection pool"
  - "mongodb community kubernetes operator"
  - "mongodb enterprise kubernetes operator"
  - "atlas kubernetes operator"
  - "mongodbcommunity crd"
  - "mongodb statefulset"
  - "mongodb persistent volume"
  - "mongodb retry writes"
  - "TransientTransactionError"
  - "resume token change stream"
  - "mongodb read preference"
  - "write concern majority"
  - "mongodb csfle client encryption"
tags:
  - "mongodb"
  - "drivers"
  - "kubernetes"
  - "node.js"
  - "python"
  - "java"
  - "go"
  - "transactions"
  - "change-streams"
  - "k8s-operator"
related_skills:
  - "mongodb-developer"
  - "mongodb-atlas-expert"
  - "mongodb-schema-design"
  - "mongodb-sharding"
  - "mongodb-performance-troubleshooting"
  - "mongodb-atlas-kubernetes-operator"
whenNotToUse:
  - "MongoDB Atlas UI-only tasks — use mongodb-atlas-expert"
  - "Schema design and document modeling decisions — use mongodb-schema-design"
  - "Sharded cluster architecture and zone sharding — use mongodb-sharding"
  - "Atlas Kubernetes Operator advanced GitOps patterns — use mongodb-atlas-kubernetes-operator"
---

# MongoDB Drivers & Kubernetes

## When to Use This Skill

Activate when the task involves any of:
- Writing or debugging MongoDB driver code in Node.js, Python, Java, or Go
- Designing connection pooling, read preferences, or write concern strategies
- Implementing multi-document transactions or change streams
- Deploying MongoDB on Kubernetes (Community, Enterprise, or Atlas operators)
- Troubleshooting driver-level connection issues, slow queries, or failover behavior
- Configuring StatefulSets, PVCs, TLS, or operator CRDs for MongoDB

**Do not activate** for: MongoDB Atlas UI-only tasks (use `mongodb-atlas-expert`), schema design decisions (use `mongodb-schema-design`), sharding configuration (use `mongodb-sharding`), or Azure/GCP/AWS-specific AKO networking (use `mongodb-atlas-azure`, `mongodb-atlas-gcp`, or `mongodb-aws-networking`).

## Prerequisites

- Transactions and change streams require a **replica set** or sharded cluster; they do not work on a standalone `mongod`. A single-member replica set is enough for local development, but production replica sets use 3+ members so `w: "majority"` survives a node loss.
- Change streams require MongoDB 3.6+; pre/post images require MongoDB 6.0+.
- The Atlas Kubernetes Operator requires an Atlas account and API keys.
- The Enterprise Operator requires a MongoDB Enterprise Advanced license and Ops Manager.

## Related Skills

- `mongodb-developer` — broader MongoDB development patterns
- `mongodb-atlas-expert` — Atlas-specific cluster management
- `mongodb-schema-design` — document modeling and index design
- `mongodb-sharding` — sharded cluster architecture
- `mongodb-kb` — diagnostic commands and KB articles
- `mongodb-performance-troubleshooting` — deep query performance analysis

## Example Use Cases

**Input:** "How do I implement a resilient change stream consumer in Node.js that survives pod restarts?"
**Output:** Resume token persistence pattern + `for await` loop with `startAtOperationTime` fallback (see Change Streams section).

**Input:** "My MongoDB pod on Kubernetes keeps getting OOMKilled. How do I fix it?"
**Output:** WiredTiger cache sizing formula, `cacheSizeGB` config in CRD, `kubectl top` monitoring (see Troubleshooting — OOM section).

**Input:** "Write a Python function that transfers funds between two accounts atomically."
**Output:** PyMongo transaction with `ReadConcern`/`WriteConcern`, session context manager, commit-on-exit pattern (see Python — Transactions section).

**Input:** "Deploy a 3-member MongoDB replica set on Kubernetes with TLS."
**Output:** `MongoDBCommunity` CRD YAML + cert-manager TLS secret + StorageClass with `reclaimPolicy: Retain` (see MongoDB on Kubernetes section).

**Input:** "What's the correct retry logic for MongoDB multi-document transactions?"
**Output:** `TransientTransactionError` → retry whole transaction; `UnknownTransactionCommitResult` → retry commit only; never retry on `WriteConflict` without aborting first (see Transactions — Deep Dive section).

---

## Overview

MongoDB official drivers for Node.js, Python, Java, and Go. Plus running MongoDB on Kubernetes via the community, enterprise, and Atlas operators. This skill covers production-grade patterns for connection management, transactions, change streams, retry logic, and K8s deployment.

---

## Connection Management

### URI Format

```
# Standalone
mongodb://user:pass@host:27017/dbname?authSource=admin

# Replica set
mongodb://user:pass@host1:27017,host2:27017,host3:27017/dbname?replicaSet=rs0&authSource=admin

# SRV (Atlas / DNS-based discovery)
mongodb+srv://user:pass@cluster0.abc123.mongodb.net/dbname?retryWrites=true&w=majority

# TLS
mongodb://host:27017/dbname?tls=true&tlsCAFile=/path/to/ca.pem
```

### Connection Pool Settings

| Option | Default | Notes |
|--------|---------|-------|
| `maxPoolSize` | 100 | Max connections per pool (per host in replica set) |
| `minPoolSize` | 0 | Pre-warmed connections kept open |
| `maxIdleTimeMS` | 0 (no limit) | Time before idle connection is closed |
| `waitQueueTimeoutMS` | 0 (no limit) | How long to wait for a connection from the pool |
| `connectTimeoutMS` | 30000 | Socket connect timeout |
| `socketTimeoutMS` | 0 (no limit) | Socket read/write timeout |
| `serverSelectionTimeoutMS` | 30000 | How long to pick a server before giving up |

### Read Preferences

```
primary            # Default. All reads from primary.
primaryPreferred   # Prefer primary; fall back to secondary if unavailable.
secondary          # Always read from secondary.
secondaryPreferred # Prefer secondary; fall back to primary.
nearest            # Lowest latency, regardless of role.
```

Read preferences can include tag sets and `maxStalenessSeconds` (minimum 90s).

### Write Concerns

```
w: 0          # Fire-and-forget. No acknowledgment.
w: 1          # Default. Primary acknowledges.
w: majority   # Wait for majority of voting replica set members.
w: <number>   # Wait for N members to acknowledge.
j: true       # Wait for write to be committed to the journal.
wtimeout: N   # Milliseconds before write concern times out (not an error by itself).
```

### Authentication Mechanisms

```
SCRAM-SHA-256  # Default for MongoDB 4.0+
SCRAM-SHA-1    # Legacy; MongoDB 3.x
MONGODB-X509   # TLS certificate-based
MONGODB-AWS    # AWS IAM roles (Atlas, Atlas on AWS)
PLAIN (LDAP)   # Enterprise only
GSSAPI         # Kerberos; Enterprise only
```

---

## Node.js Driver (mongodb v6+)

### Install

```bash
npm install mongodb
```

### MongoClient Singleton Pattern

```js
// db.js — create once, reuse everywhere
import { MongoClient } from 'mongodb';

let client;

export async function getClient() {
  if (!client) {
    client = new MongoClient(process.env.MONGODB_URI, {
      maxPoolSize: 50,
      minPoolSize: 5,
      serverSelectionTimeoutMS: 5000,
      socketTimeoutMS: 45000,
    });
    await client.connect();
  }
  return client;
}

export async function getDb(dbName = 'myapp') {
  const c = await getClient();
  return c.db(dbName);
}
```

### CRUD Operations

```js
const db = await getDb();
const users = db.collection('users');

// Insert
const { insertedId } = await users.insertOne({ name: 'Alice', age: 30 });
const { insertedIds } = await users.insertMany([
  { name: 'Bob' }, { name: 'Carol' }
]);

// Find
const user = await users.findOne({ name: 'Alice' });
const cursor = users.find({ age: { $gte: 18 } })
  .sort({ name: 1 })
  .skip(0)
  .limit(20)
  .project({ name: 1, email: 1, _id: 0 });
const results = await cursor.toArray();

// Update
await users.updateOne(
  { _id: insertedId },
  { $set: { age: 31 }, $currentDate: { updatedAt: true } }
);
await users.updateMany(
  { verified: false },
  { $set: { verified: true } }
);

// Replace
await users.replaceOne({ _id: insertedId }, { name: 'Alice', age: 32 });

// Delete
await users.deleteOne({ _id: insertedId });
await users.deleteMany({ inactive: true });

// findOneAndUpdate (returns document)
const updated = await users.findOneAndUpdate(
  { name: 'Alice' },
  { $inc: { loginCount: 1 } },
  { returnDocument: 'after' }
);
```

### Aggregation Pipeline

```js
const pipeline = [
  { $match: { status: 'active' } },
  { $group: {
      _id: '$department',
      count: { $sum: 1 },
      avgSalary: { $avg: '$salary' }
  }},
  { $sort: { count: -1 } },
  { $limit: 10 },
  { $project: { department: '$_id', count: 1, avgSalary: { $round: ['$avgSalary', 2] }, _id: 0 } }
];

const results = await db.collection('employees').aggregate(pipeline).toArray();
```

### Change Streams

```js
async function watchOrders(db) {
  const collection = db.collection('orders');

  // Filter to only insert/update events
  const pipeline = [
    { $match: { operationType: { $in: ['insert', 'update', 'replace'] } } }
  ];

  let resumeToken = await loadResumeToken(); // load from persistent store

  const changeStream = collection.watch(pipeline, {
    fullDocument: 'updateLookup',
    resumeAfter: resumeToken,  // omit on first run
  });

  changeStream.on('change', async (event) => {
    console.log('Change:', event.operationType, event.fullDocument);
    resumeToken = event._id;
    await saveResumeToken(resumeToken); // persist after processing
  });

  changeStream.on('error', (err) => {
    console.error('Change stream error:', err);
    // Stream will attempt to resume automatically if the token is valid
  });

  return changeStream;
}
```

### Transactions

```js
async function transferFunds(client, fromId, toId, amount) {
  const session = client.startSession();

  try {
    await session.withTransaction(async () => {
      const accounts = client.db('bank').collection('accounts');

      await accounts.updateOne(
        { _id: fromId },
        { $inc: { balance: -amount } },
        { session }
      );
      await accounts.updateOne(
        { _id: toId },
        { $inc: { balance: amount } },
        { session }
      );
    }, {
      readPreference: 'primary',
      readConcern: { level: 'majority' },
      writeConcern: { w: 'majority' }
    });
  } finally {
    await session.endSession();
  }
}
```

### GridFS

```js
import { GridFSBucket } from 'mongodb';
import fs from 'fs';

const bucket = new GridFSBucket(db, { bucketName: 'uploads' });

// Upload
const uploadStream = bucket.openUploadStream('photo.jpg', {
  metadata: { uploadedBy: userId }
});
fs.createReadStream('/tmp/photo.jpg').pipe(uploadStream);

// Download
const downloadStream = bucket.openDownloadStreamByName('photo.jpg');
downloadStream.pipe(fs.createWriteStream('/tmp/output.jpg'));

// Find files
const files = await bucket.find({ 'metadata.uploadedBy': userId }).toArray();

// Delete
await bucket.delete(fileId);
```

### Client-Side Field Level Encryption (CSFLE)

```js
import { ClientEncryption } from 'mongodb-client-encryption';

const keyVaultNamespace = 'encryption.__keyVault';
const kmsProviders = {
  local: { key: Buffer.from(process.env.MASTER_KEY_B64, 'base64') }
};

const encryptedClient = new MongoClient(uri, {
  autoEncryption: {
    keyVaultNamespace,
    kmsProviders,
    schemaMap: {
      'myapp.patients': {
        bsonType: 'object',
        encryptMetadata: { keyId: [dataKeyId] },
        properties: {
          ssn: {
            encrypt: {
              bsonType: 'string',
              algorithm: 'AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic'
            }
          }
        }
      }
    }
  }
});
```

---

## Python Driver (PyMongo 4.x)

### Install

```bash
pip install pymongo[srv]
pip install motor  # async
```

### Synchronous with PyMongo

```python
import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import (
    ConnectionFailure, OperationFailure,
    DuplicateKeyError, BulkWriteError
)

# Singleton pattern
_client = None

def get_client():
    global _client
    if _client is None:
        _client = MongoClient(
            os.environ['MONGODB_URI'],
            maxPoolSize=50,
            minPoolSize=5,
            serverSelectionTimeoutMS=5000,
            retryWrites=True,
            w='majority',
        )
    return _client

def get_db(name='myapp'):
    return get_client()[name]

# CRUD
db = get_db()
users = db['users']

# Insert
result = users.insert_one({'name': 'Alice', 'age': 30})
print(result.inserted_id)

# Query
user = users.find_one({'name': 'Alice'})
cursor = users.find({'age': {'$gte': 18}}).sort('name', ASCENDING).limit(20)
for doc in cursor:
    print(doc)

# Update
users.update_one({'_id': result.inserted_id}, {'$set': {'age': 31}})
users.update_many({'verified': False}, {'$set': {'verified': True}})

# Delete
users.delete_one({'_id': result.inserted_id})

# Aggregation
pipeline = [
    {'$match': {'status': 'active'}},
    {'$group': {'_id': '$dept', 'count': {'$sum': 1}}},
    {'$sort': {'count': -1}}
]
results = list(users.aggregate(pipeline))
```

### Bulk Operations

```python
from pymongo import InsertOne, UpdateOne, DeleteOne, ReplaceOne

requests = [
    InsertOne({'name': 'Dave'}),
    UpdateOne({'name': 'Alice'}, {'$set': {'age': 32}}),
    DeleteOne({'name': 'Bob'}),
]

try:
    result = users.bulk_write(requests, ordered=False)
    print(f"Inserted: {result.inserted_count}, Modified: {result.modified_count}")
except BulkWriteError as e:
    print(e.details)
```

### Transactions

```python
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

def transfer(client, from_id, to_id, amount):
    with client.start_session() as session:
        with session.start_transaction(
            read_concern=ReadConcern('majority'),
            write_concern=WriteConcern(w='majority'),
        ):
            accounts = client['bank']['accounts']
            accounts.update_one(
                {'_id': from_id},
                {'$inc': {'balance': -amount}},
                session=session
            )
            accounts.update_one(
                {'_id': to_id},
                {'$inc': {'balance': amount}},
                session=session
            )
            # Commit is automatic on context exit (no exception)
```

### Async with Motor

```python
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient(os.environ['MONGODB_URI'])
    db = client['myapp']

    await db['users'].insert_one({'name': 'Alice'})

    async for doc in db['users'].find({'age': {'$gte': 18}}):
        print(doc)

    # Aggregation
    async for result in db['orders'].aggregate([
        {'$match': {'status': 'shipped'}},
        {'$group': {'_id': '$customerId', 'total': {'$sum': '$amount'}}}
    ]):
        print(result)

asyncio.run(main())
```

### Codec Options and Type Handling

```python
from bson.codec_options import CodecOptions
from bson import Decimal128
import datetime

opts = CodecOptions(tz_aware=True, unicode_decode_error_handler='ignore')
collection = db.get_collection('events', codec_options=opts)

# Datetime handling
doc = {
    'event': 'purchase',
    'timestamp': datetime.datetime.now(tz=datetime.timezone.utc),
    'amount': Decimal128('19.99'),
}
```

---

## Java Driver (4.x / 5.x)

### Maven Dependencies

```xml
<!-- Sync driver -->
<dependency>
  <groupId>org.mongodb</groupId>
  <artifactId>mongodb-driver-sync</artifactId>
  <version>5.1.0</version>
</dependency>

<!-- Reactive Streams driver -->
<dependency>
  <groupId>org.mongodb</groupId>
  <artifactId>mongodb-driver-reactivestreams</artifactId>
  <version>5.1.0</version>
</dependency>
```

### MongoClient Singleton

```java
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.MongoClientSettings;
import com.mongodb.ConnectionString;

public class MongoConfig {
    private static MongoClient client;

    public static synchronized MongoClient getClient() {
        if (client == null) {
            MongoClientSettings settings = MongoClientSettings.builder()
                .applyConnectionString(new ConnectionString(System.getenv("MONGODB_URI")))
                .applyToConnectionPoolSettings(builder -> builder
                    .maxSize(50)
                    .minSize(5)
                    .maxWaitTime(30, TimeUnit.SECONDS)
                )
                .applyToSocketSettings(builder -> builder
                    .connectTimeout(5, TimeUnit.SECONDS)
                    .readTimeout(45, TimeUnit.SECONDS)
                )
                .build();
            client = MongoClients.create(settings);
        }
        return client;
    }
}
```

### CRUD with Builders API

```java
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Updates;
import com.mongodb.client.model.Sorts;
import com.mongodb.client.model.Projections;
import org.bson.Document;

MongoCollection<Document> users = client.getDatabase("myapp").getCollection("users");

// Insert
users.insertOne(new Document("name", "Alice").append("age", 30));

// Find
Document user = users.find(Filters.eq("name", "Alice")).first();
List<Document> results = users
    .find(Filters.gte("age", 18))
    .sort(Sorts.ascending("name"))
    .projection(Projections.fields(Projections.include("name", "email"), Projections.excludeId()))
    .limit(20)
    .into(new ArrayList<>());

// Update
users.updateOne(
    Filters.eq("name", "Alice"),
    Updates.combine(Updates.set("age", 31), Updates.currentDate("updatedAt"))
);

// Delete
users.deleteOne(Filters.eq("name", "Alice"));
```

### POJO Codec

```java
import org.bson.codecs.configuration.CodecRegistry;
import org.bson.codecs.pojo.PojoCodecProvider;
import static org.bson.codecs.configuration.CodecRegistries.*;

// Domain class
public class User {
    @BsonId
    public ObjectId id;
    public String name;
    public int age;
    // getters/setters...
}

// Configure codec
CodecRegistry registry = fromRegistries(
    MongoClientSettings.getDefaultCodecRegistry(),
    fromProviders(PojoCodecProvider.builder().automatic(true).build())
);

MongoCollection<User> userCollection = db
    .getCollection("users", User.class)
    .withCodecRegistry(registry);

User alice = new User();
alice.name = "Alice";
alice.age = 30;
userCollection.insertOne(alice);
```

### Transactions (Java)

```java
try (ClientSession session = client.startSession()) {
    TransactionOptions txnOptions = TransactionOptions.builder()
        .readPreference(ReadPreference.primary())
        .readConcern(ReadConcern.MAJORITY)
        .writeConcern(WriteConcern.MAJORITY)
        .build();

    session.withTransaction(() -> {
        accounts.updateOne(session,
            Filters.eq("_id", fromId),
            Updates.inc("balance", -amount));
        accounts.updateOne(session,
            Filters.eq("_id", toId),
            Updates.inc("balance", amount));
        return null;
    }, txnOptions);
}
```

---

## Go Driver (go.mongodb.org/mongo-driver v1.x / v2.x)

### Install

```bash
go get go.mongodb.org/mongo-driver/v2/mongo
```

### Client Setup

```go
package db

import (
    "context"
    "os"
    "sync"
    "time"

    "go.mongodb.org/mongo-driver/v2/mongo"
    "go.mongodb.org/mongo-driver/v2/mongo/options"
    "go.mongodb.org/mongo-driver/v2/mongo/readpref"
)

var (
    client *mongo.Client
    once   sync.Once
)

func GetClient(ctx context.Context) (*mongo.Client, error) {
    var err error
    once.Do(func() {
        opts := options.Client().
            ApplyURI(os.Getenv("MONGODB_URI")).
            SetMaxPoolSize(50).
            SetMinPoolSize(5).
            SetServerSelectionTimeout(5 * time.Second).
            SetConnectTimeout(10 * time.Second)

        client, err = mongo.Connect(opts)
        if err != nil {
            return
        }
        // Verify connection
        err = client.Ping(ctx, readpref.Primary())
    })
    return client, err
}
```

### CRUD Operations

```go
import (
    "go.mongodb.org/mongo-driver/v2/bson"
    "go.mongodb.org/mongo-driver/v2/mongo/options"
)

type User struct {
    ID   bson.ObjectID `bson:"_id,omitempty"`
    Name string        `bson:"name"`
    Age  int           `bson:"age"`
}

col := client.Database("myapp").Collection("users")
ctx := context.Background()

// Insert
res, err := col.InsertOne(ctx, User{Name: "Alice", Age: 30})

// Find one
var user User
err = col.FindOne(ctx, bson.M{"name": "Alice"}).Decode(&user)

// Find many
filter := bson.D{{Key: "age", Value: bson.D{{Key: "$gte", Value: 18}}}}
opts := options.Find().SetSort(bson.D{{Key: "name", Value: 1}}).SetLimit(20)
cursor, err := col.Find(ctx, filter, opts)
defer cursor.Close(ctx)
var users []User
if err = cursor.All(ctx, &users); err != nil {
    log.Fatal(err)
}

// Update
_, err = col.UpdateOne(ctx,
    bson.M{"name": "Alice"},
    bson.M{"$set": bson.M{"age": 31}},
)

// Delete
_, err = col.DeleteOne(ctx, bson.M{"name": "Alice"})
```

### Aggregation

```go
pipeline := mongo.Pipeline{
    {{Key: "$match", Value: bson.D{{Key: "status", Value: "active"}}}},
    {{Key: "$group", Value: bson.D{
        {Key: "_id", Value: "$department"},
        {Key: "count", Value: bson.D{{Key: "$sum", Value: 1}}},
    }}},
    {{Key: "$sort", Value: bson.D{{Key: "count", Value: -1}}}},
}

cursor, err := col.Aggregate(ctx, pipeline)
var results []bson.M
cursor.All(ctx, &results)
```

### Connection Monitoring

```go
import "go.mongodb.org/mongo-driver/v2/event"

monitor := &event.CommandMonitor{
    Started: func(ctx context.Context, evt *event.CommandStartedEvent) {
        log.Printf("CMD start: %s %s", evt.CommandName, evt.DatabaseName)
    },
    Succeeded: func(ctx context.Context, evt *event.CommandSucceededEvent) {
        log.Printf("CMD ok: %s (%dms)", evt.CommandName, evt.Duration.Milliseconds())
    },
    Failed: func(ctx context.Context, evt *event.CommandFailedEvent) {
        log.Printf("CMD fail: %s %v", evt.CommandName, evt.Failure)
    },
}

opts := options.Client().ApplyURI(uri).SetMonitor(monitor)
```

---

## Transactions — Deep Dive

### Session Lifecycle

```
client.startSession()
  └── session.startTransaction()
       ├── operations (must pass session to each)
       ├── session.commitTransaction()   OR
       └── session.abortTransaction()
  └── session.endSession()
```

### Retry Pattern (Manual)

```js
// Node.js — manual retry for non-withTransaction usage
async function runTransactionWithRetry(txnFunc, client) {
  while (true) {
    const session = client.startSession();
    try {
      await session.startTransaction({
        readConcern: { level: 'majority' },
        writeConcern: { w: 'majority' }
      });
      await txnFunc(session);
      await commitWithRetry(session);
      return;
    } catch (err) {
      if (err.hasErrorLabel('TransientTransactionError')) {
        // Network blip or primary election — safe to retry entire txn
        continue;
      }
      throw err;
    } finally {
      await session.endSession();
    }
  }
}

async function commitWithRetry(session) {
  while (true) {
    try {
      await session.commitTransaction();
      return;
    } catch (err) {
      if (err.hasErrorLabel('UnknownTransactionCommitResult')) {
        // Commit may or may not have applied — retry commit only
        continue;
      }
      throw err;
    }
  }
}
```

### Read Concern for Transactions

| Level | Description | Use Case |
|-------|-------------|----------|
| `local` | Latest committed data on this node | Fast reads, non-critical |
| `majority` | Data acknowledged by majority | Default for transactions |
| `snapshot` | Consistent snapshot at txn start | Complex multi-doc reads |
| `linearizable` | Strongest; confirms primary is current | Critical reads, slow |

### Transaction Limits

- Max 60 seconds by default (`transactionLifetimeLimitSeconds`)
- MongoDB 4.4+ chains a large transaction across multiple oplog entries (each still ≤16 MB BSON), so total size is bounded by oplog space and WiredTiger cache — not by a single 16 MB entry (the pre-4.4 cap)
- Avoid long-running transactions; they hold locks and cause blocking

---

## Change Streams — Deep Dive

### Watch Levels

```js
// Collection level
const stream = db.collection('orders').watch(pipeline, options);

// Database level (all collections in DB)
const stream = db.watch(pipeline, options);

// Deployment level (all databases)
const stream = client.watch(pipeline, options);
```

### Full Document Pre/Post Images (MongoDB 6.0+)

```js
// Enable on collection
await db.command({
  collMod: 'orders',
  changeStreamPreAndPostImages: { enabled: true }
});

// Request images in change stream
const stream = db.collection('orders').watch([], {
  fullDocument: 'whenAvailable',       // post-image
  fullDocumentBeforeChange: 'whenAvailable'  // pre-image
});
```

### Filtering Change Events

```js
const pipeline = [
  {
    $match: {
      $or: [
        { operationType: 'insert' },
        { operationType: 'update', 'updateDescription.updatedFields.status': { $exists: true } }
      ],
      'fullDocument.priority': { $gte: 5 }
    }
  },
  {
    $project: {
      _id: 1,
      operationType: 1,
      'fullDocument._id': 1,
      'fullDocument.status': 1
    }
  }
];
```

### Resume Token Persistence

```js
// In a real app: store in DB, Redis, or file
async function persistentChangeStream(collection, store) {
  const token = await store.get('resumeToken');
  const opts = token ? { resumeAfter: token } : { startAtOperationTime: new Date() };

  const stream = collection.watch([], { ...opts, fullDocument: 'updateLookup' });

  for await (const event of stream) {
    await processEvent(event);
    await store.set('resumeToken', event._id); // save AFTER successful processing
  }
}
```

---

## Retry Patterns

### Retryable Writes (Driver Built-in)

Enabled by default in drivers since MongoDB 4.2. Covers single-statement write operations that are idempotent. The driver retries once on a network error or primary failover.

```js
// Retryable by default (URI option)
const client = new MongoClient(uri, { retryWrites: true });

// These are retried automatically:
// insertOne, insertMany (if not ordered=true w/ partial failure)
// updateOne, replaceOne, deleteOne
// findOneAndUpdate, findOneAndReplace, findOneAndDelete
```

### Retryable Reads

```js
const client = new MongoClient(uri, { retryReads: true }); // default true
// find, findOne, aggregate (non-$out/$merge), count, etc. are retried once
```

### Custom Application Retry

```js
async function withRetry(operation, { maxAttempts = 3, baseDelayMs = 100 } = {}) {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await operation();
    } catch (err) {
      const isRetryable =
        err.code === 11600 || // InterruptedAtShutdown
        err.code === 91 ||    // ShutdownInProgress
        err.name === 'MongoNetworkError' ||
        err.name === 'MongoNetworkTimeoutError';

      if (!isRetryable || attempt === maxAttempts) throw err;

      const delay = baseDelayMs * Math.pow(2, attempt - 1); // exponential backoff
      await new Promise(r => setTimeout(r, delay));
    }
  }
}

// Usage
const result = await withRetry(() =>
  db.collection('inventory').updateOne(
    { sku: 'ABC', qty: { $gte: 10 } },
    { $inc: { qty: -10 } }
  )
);
```

### Idempotency Patterns

```js
// Use a client-generated idempotency key to prevent double-processing
const orderId = new ObjectId(); // generated client-side

await orders.updateOne(
  { _id: orderId },
  {
    $setOnInsert: { _id: orderId, createdAt: new Date(), items, total },
    $set: { status: 'pending' }
  },
  { upsert: true }
);
// Safe to retry: second call is a no-op if order already exists
```

---

## MongoDB on Kubernetes

### MongoDB Community Kubernetes Operator

#### Install

```bash
helm repo add mongodb https://mongodb.github.io/helm-charts
helm install community-operator mongodb/community-operator \
  --namespace mongodb \
  --create-namespace \
  --set operator.watchNamespace='*'
```

#### MongoDBCommunity CRD — Replica Set

```yaml
apiVersion: mongodbcommunity.mongodb.com/v1
kind: MongoDBCommunity
metadata:
  name: my-replica-set
  namespace: mongodb
spec:
  members: 3
  type: ReplicaSet
  version: "7.0.11"
  security:
    authentication:
      modes: ["SCRAM"]
  users:
    - name: app-user
      db: myapp
      passwordSecretRef:
        name: app-user-password
      roles:
        - name: readWrite
          db: myapp
        - name: clusterMonitor
          db: admin
      scramCredentialsSecretName: app-user-scram
  additionalMongodConfig:
    storage.wiredTiger.engineConfig.journalCompressor: zlib
  statefulSet:
    spec:
      template:
        spec:
          containers:
            - name: mongod
              resources:
                requests:
                  cpu: "0.5"
                  memory: "1Gi"
                limits:
                  cpu: "2"
                  memory: "4Gi"
      volumeClaimTemplates:
        - metadata:
            name: data-volume
          spec:
            storageClassName: standard
            accessModes: ["ReadWriteOnce"]
            resources:
              requests:
                storage: 20Gi
```

#### User Password Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-user-password
  namespace: mongodb
type: Opaque
stringData:
  password: "my-secure-password"
```

#### Connection from In-Cluster App

```yaml
# The operator creates this service:
# my-replica-set-svc.mongodb.svc.cluster.local
# Connection string format:
# mongodb://app-user:password@my-replica-set-0.my-replica-set-svc.mongodb.svc.cluster.local:27017,.../?replicaSet=my-replica-set
```

### TLS Configuration (Community Operator)

```yaml
spec:
  security:
    tls:
      enabled: true
      certificateKeySecretRef:
        name: mongodb-tls-cert
      caConfigMapRef:
        name: mongodb-ca
  # Generate self-signed cert with cert-manager or supply manually
```

### Persistent Volume Considerations

```yaml
# Prefer local SSDs for performance; use WaitForFirstConsumer binding
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: mongodb-ssd
provisioner: kubernetes.io/gce-pd  # or your CSI driver
parameters:
  type: pd-ssd
volumeBindingMode: WaitForFirstConsumer  # important for topology-aware scheduling
reclaimPolicy: Retain  # NEVER Delete for production MongoDB
allowVolumeExpansion: true
```

### StatefulSet Pod Anti-Affinity

```yaml
# Ensure replica set members land on different nodes
spec:
  statefulSet:
    spec:
      template:
        spec:
          affinity:
            podAntiAffinity:
              requiredDuringSchedulingIgnoredDuringExecution:
                - labelSelector:
                    matchLabels:
                      app: my-replica-set
                  topologyKey: kubernetes.io/hostname
```

### Readiness and Liveness Probes

The Community Operator injects these automatically. For custom StatefulSets:

```yaml
readinessProbe:
  exec:
    command:
      - mongosh
      - --eval
      - "db.adminCommand('ping')"
      - --quiet
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 6

livenessProbe:
  exec:
    command:
      - mongosh
      - --eval
      - "db.adminCommand('ping')"
      - --quiet
  initialDelaySeconds: 60
  periodSeconds: 30
  timeoutSeconds: 5
  failureThreshold: 3
```

---

## MongoDB Enterprise Kubernetes Operator

### Overview

Requires MongoDB Enterprise Advanced license and Ops Manager (or Cloud Manager).

### Install

```bash
helm repo add mongodb https://mongodb.github.io/helm-charts
helm install enterprise-operator mongodb/enterprise-operator \
  --namespace mongodb \
  --create-namespace
```

### Ops Manager CRD

```yaml
apiVersion: mongodb.com/v1
kind: MongoDBOpsManager
metadata:
  name: ops-manager
  namespace: mongodb
spec:
  replicas: 1
  version: "6.0.21"
  adminCredentials: ops-manager-admin-secret
  externalConnectivity:
    type: LoadBalancer
  applicationDatabase:
    members: 3
    version: "7.0.11"
    persistent: true
    podSpec:
      persistence:
        single:
          storage: 10Gi
```

### Enterprise MongoDB Replica Set

```yaml
apiVersion: mongodb.com/v1
kind: MongoDB
metadata:
  name: my-replica-set
  namespace: mongodb
spec:
  members: 3
  version: "7.0.11"
  type: ReplicaSet
  opsManager:
    configMapRef:
      name: my-project
  credentials: my-credentials
  persistent: true
  podSpec:
    persistence:
      single:
        storage: 50Gi
    podTemplate:
      spec:
        containers:
          - name: mongodb-enterprise-database
            resources:
              limits:
                cpu: "4"
                memory: "8Gi"
```

---

## Atlas Kubernetes Operator

### Install

```bash
helm repo add mongodb https://mongodb.github.io/helm-charts
helm install atlas-operator mongodb/mongodb-atlas-operator \
  --namespace atlas-operator \
  --create-namespace \
  --set-string atlas.orgId=<org-id>
```

### Atlas API Key Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: atlas-api-key
  namespace: atlas-operator
  labels:
    atlas.mongodb.com/type: credentials
type: Opaque
stringData:
  orgId: "YOUR_ORG_ID"
  publicApiKey: "YOUR_PUBLIC_KEY"
  privateApiKey: "YOUR_PRIVATE_KEY"
```

### AtlasProject

```yaml
apiVersion: atlas.mongodb.com/v1
kind: AtlasProject
metadata:
  name: my-project
  namespace: atlas-operator
spec:
  name: MyK8sProject
  connectionSecretRef:
    name: atlas-api-key
  projectIpAccessList:
    - ipAddress: "0.0.0.0/0"  # restrict in production!
      comment: "Allow all (dev only)"
```

### AtlasDeployment

```yaml
apiVersion: atlas.mongodb.com/v1
kind: AtlasDeployment
metadata:
  name: my-cluster
  namespace: atlas-operator
spec:
  projectRef:
    name: my-project
  deploymentSpec:
    name: my-cluster
    clusterType: REPLICASET
    replicationSpecs:
      - numShards: 1
        regionConfigs:
          - regionName: US_EAST_1
            providerName: AWS
            priority: 7
            electableSpecs:
              instanceSize: M10
              nodeCount: 3
    mongoDBMajorVersion: "7.0"
    backupEnabled: true
    autoScaling:
      diskGB:
        enabled: true
      compute:
        enabled: true
        scaleDownEnabled: true
        minInstanceSize: M10
        maxInstanceSize: M40
```

### AtlasDatabaseUser

```yaml
apiVersion: atlas.mongodb.com/v1
kind: AtlasDatabaseUser
metadata:
  name: app-user
  namespace: atlas-operator
spec:
  username: app-user
  databaseName: admin
  projectRef:
    name: my-project
  passwordSecretRef:
    name: app-user-password
  roles:
    - roleName: readWrite
      databaseName: myapp
```

### Retrieve Connection String

```bash
# The operator creates a secret with connection details
kubectl get secret my-project-my-cluster-app-user -n atlas-operator -o jsonpath='{.data.connectionStringStandardSrv}' | base64 -d
```

---

## Performance Tuning

### Index Strategies

```js
// Compound index — field order matters: equality, sort, range
db.orders.createIndex({ customerId: 1, status: 1, createdAt: -1 });

// Partial index — only index documents matching a filter
db.orders.createIndex(
  { status: 1, createdAt: -1 },
  { partialFilterExpression: { status: { $in: ['pending', 'processing'] } } }
);

// TTL index — auto-delete expired documents
db.sessions.createIndex({ createdAt: 1 }, { expireAfterSeconds: 3600 });

// Wildcard index — for dynamic field schemas
db.products.createIndex({ 'attributes.$**': 1 });

// Text search
db.articles.createIndex({ title: 'text', body: 'text' }, { weights: { title: 10, body: 1 } });
```

### Explain Plan Interpretation

```js
const plan = await db.collection('orders').find({ customerId: 'abc123' })
  .explain('executionStats');

// Key fields to check:
// plan.queryPlanner.winningPlan.stage === 'IXSCAN'  ← good (index scan)
// plan.queryPlanner.winningPlan.stage === 'COLLSCAN' ← bad (full collection scan)
// plan.executionStats.totalDocsExamined vs nReturned — ratio should be ~1 for efficient queries
// plan.executionStats.executionTimeMillis
```

### Connection Pool Sizing

```
# Rule of thumb:
# maxPoolSize per replica set member (not per deployment)
# For web apps: (number_of_app_instances * maxPoolSize) should not exceed
#   mongo_max_connections / (replica_set_members * 1.5 safety factor)
#
# MongoDB default max_connections ≈ 65536 (varies by ulimits)
# For 10 app pods, maxPoolSize=50: 10*50 = 500 connections to primary — fine
```

### Read Scaling with Read Preferences

```js
// Read from secondaries for analytics queries
const analyticsDb = client.db('myapp').withReadPreference(
  ReadPreference.secondaryPreferred
);

// Nearest for low-latency reads that tolerate stale data
const cacheDb = client.db('myapp').withReadPreference(
  new ReadPreference('nearest', [], { maxStalenessSeconds: 120 })
);
```

### Profiler

```js
// Enable slow query profiling (operations > 100ms)
db.setProfilingLevel(1, { slowms: 100 });

// Query the profiler
db.system.profile.find().sort({ ts: -1 }).limit(10).pretty();

// Find slow aggregations
db.system.profile.find({ op: 'command', 'command.aggregate': { $exists: true } })
  .sort({ millis: -1 });
```

---

## Anti-Patterns

### Opening a New MongoClient per Request

```js
// BAD — creates a new connection pool on every request
app.get('/users', async (req, res) => {
  const client = new MongoClient(uri); // DON'T DO THIS
  await client.connect();
  const users = await client.db('myapp').collection('users').find().toArray();
  await client.close();
  res.json(users);
});

// GOOD — share a singleton client
app.get('/users', async (req, res) => {
  const db = await getDb(); // singleton from module
  const users = await db.collection('users').find().toArray();
  res.json(users);
});
```

### Not Handling Write Concern Timeouts

```js
// BAD — wtimeout error is NOT a write failure; it's ambiguous
// The write may have succeeded; wtimeout just means the driver stopped waiting

// GOOD — check and handle wtimeout separately
try {
  await col.insertOne(doc, { writeConcern: { w: 'majority', wtimeout: 5000 } });
} catch (err) {
  if (err.result?.writeConcernError?.code === 64) { // WriteConcernTimeout
    // The write may have succeeded — check before retrying
    const existing = await col.findOne({ _id: doc._id });
    if (!existing) await col.insertOne(doc); // safe to retry
  }
}
```

### Running Long Transactions

```
- Transactions hold snapshot reads and block oplog cleanup
- Keep transactions under 1000ms; 60s hard limit by default
- Break large imports into batches of 500-1000 documents
- Use ordered bulk writes instead of transactions for bulk inserts
```

### Not Resuming Change Streams

```js
// BAD — loses events on restart
const stream = collection.watch();
for await (const event of stream) { process(event); }

// GOOD — always persist and use resume tokens
```

### Using _id as a Sort Guarantee

```js
// ObjectId _id is NOT guaranteed to be monotonically increasing across shards
// Use { createdAt: 1, _id: 1 } for stable pagination
const page = await col.find({ createdAt: { $gt: lastCreatedAt } })
  .sort({ createdAt: 1, _id: 1 })
  .limit(20)
  .toArray();
```

---

## Troubleshooting

### Connection Timeout Debugging

```bash
# Check replica set status from inside pod (use mongosh; mongo shell removed in MongoDB 6.0)
kubectl exec -it my-replica-set-0 -n mongodb -- mongosh --eval "rs.status()" --quiet

# Check primary/election state (rs.isMaster() deprecated in 5.0; use hello)
kubectl exec -it my-replica-set-0 -n mongodb -- mongosh --eval "db.hello()" --quiet

# Check network connectivity to another replica set member
kubectl exec -it my-replica-set-0 -n mongodb -- \
  mongosh "mongodb://my-replica-set-1.my-replica-set-svc.mongodb.svc.cluster.local:27017" \
  --eval "db.adminCommand('ping')" --quiet

# Common causes:
# 1. serverSelectionTimeoutMS too short for startup (increase to 30000)
# 2. Network policy blocking port 27017 between pods
# 3. DNS resolution failure for replica set members
# 4. TLS mismatch (tlsAllowInvalidCertificates or wrong CA)
# 5. Pod not yet in Running state — check: kubectl get pods -n mongodb -w
```

### Replica Set Failover in Drivers

```
- Drivers detect primary failure via server monitoring (heartbeat every 10s by default)
- During election (~10-30s), writes will fail with NotWritablePrimary error
- With retryWrites=true, driver retries once after new primary is elected
- Increase serverSelectionTimeoutMS (e.g., 30000) for apps that must survive elections
- Monitor MongoServerError code 10107 (NotPrimary) and 13435 (NotMasterNoSlaveOk)
```

### Slow Query Diagnosis

```js
// Run these in mongosh (mongo shell removed in MongoDB 6.0)

// Step 1: Find slow operations in flight
db.adminCommand({ currentOp: true, active: true, secs_running: { $gt: 5 } });

// Step 2: Kill a runaway operation
db.adminCommand({ killOp: 1, op: <opid> });

// Step 3: Use explain to understand query plan
db.orders.find({ customerId: 'abc' }).explain('executionStats');

// Step 4: Check index usage stats
db.orders.aggregate([{ $indexStats: {} }]);

// Step 5: Check for missing indexes (collections with high scan ratios)
db.orders.aggregate([
  { $indexStats: {} },
  { $group: { _id: '$name', ops: { $sum: '$accesses.ops' } } },
  { $sort: { ops: -1 } }
]);
```

### K8s PVC Scheduling Issues

```bash
# PVC stuck in Pending — check events
kubectl describe pvc data-volume-my-replica-set-0 -n mongodb

# Common causes:
# 1. StorageClass does not exist or provisioner not installed
# 2. WaitForFirstConsumer + no matching node
# 3. Insufficient disk quota in cloud provider
# 4. Node selector/affinity preventing scheduling

# Force reschedule (delete pod, StatefulSet will recreate)
kubectl delete pod my-replica-set-0 -n mongodb

# Expand PVC (if StorageClass has allowVolumeExpansion: true)
kubectl patch pvc data-volume-my-replica-set-0 -n mongodb \
  -p '{"spec": {"resources": {"requests": {"storage": "50Gi"}}}}'
```

### Diagnosing OOM in K8s MongoDB Pods

```bash
# Check pod termination reason
kubectl describe pod my-replica-set-0 -n mongodb | grep -A5 "Last State"

# Tune WiredTiger cache — should be ~50% of container memory limit
# In MongoDBCommunity additionalMongodConfig:
# storage.wiredTiger.engineConfig.cacheSizeGB: 2

# Monitor memory
kubectl top pod -n mongodb
```

---

## Quick Reference

### Driver Version Matrix

| Language | Package | Latest Stable | Min MongoDB |
|----------|---------|--------------|-------------|
| Node.js | `mongodb` | 6.x | 4.0 |
| Python | `pymongo` | 4.x | 4.0 |
| Python async | `motor` | 3.x | 4.0 |
| Java sync | `mongodb-driver-sync` | 5.x | 4.0 |
| Java reactive | `mongodb-driver-reactivestreams` | 5.x | 4.0 |
| Go | `go.mongodb.org/mongo-driver/v2` | 2.x | 4.0 |

### K8s Operator Comparison

| Operator | CRD Kind | License Required | Ops Manager | Atlas |
|----------|----------|-----------------|-------------|-------|
| Community | `MongoDBCommunity` | None | No | No |
| Enterprise | `MongoDB` | Enterprise | Yes | Optional |
| Atlas | `AtlasDeployment` | None | No | Yes (Atlas account) |

### Common MongoDB Error Codes

| Code | Name | Action |
|------|------|--------|
| 11000 | DuplicateKey | Idempotent upsert or catch and handle |
| 112 | WriteConflict | Abort then retry whole transaction (driver does not auto-retry this) |
| 251 | NoSuchTransaction | Session expired or transaction timed out; abort and retry whole transaction |
| 10107 | NotWritablePrimary | Wait for election; retryWrites handles this |
| 91 | ShutdownInProgress | Retry with backoff |
| 6 | HostUnreachable | Check network/DNS |
| 7 | HostNotFound | Check DNS resolution |
| 89 | NetworkTimeout | Increase socketTimeoutMS or fix network |
