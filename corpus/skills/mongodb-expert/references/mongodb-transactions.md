<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-transactions` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-transactions
description: >-
  MongoDB multi-document transactions — replica set and sharded cluster transactions,
  ACID guarantees, snapshot isolation, retryable transaction patterns, performance
  considerations, and anti-patterns. TRIGGER: designing workflows that require
  multi-document atomicity; debugging TransientTransactionError or
  UnknownTransactionCommitResult; reviewing whether transactions are appropriate vs.
  single-document atomic ops; tuning read/write concern; migrating from relational
  transaction patterns. SKIP: single-document atomic operations (use $inc, $push,
  findOneAndUpdate — no skill needed); error code interpretation beyond transactions
  (mongodb-error-codes); query or schema design with no transaction angle
  (mongodb-developer, mongodb-schema-design).
category: mongodb
version: 1.1.0
updated: "2026-05-29"
tags:
  - mongodb
  - transactions
  - ACID
  - replica-set
  - sharded
  - snapshot-isolation
  - drivers
keywords:
  - multi-document transactions
  - TransientTransactionError
  - UnknownTransactionCommitResult
  - withTransaction
  - snapshot isolation
  - retryable writes
  - write concern majority
  - two-phase commit
  - sharded transactions
  - session.startTransaction
  - WriteConflict 112
  - transactionLifetimeLimitSeconds
  - SnapshotTooOld
whenToUse:
  - "designing a workflow that must atomically update multiple collections"
  - "TransientTransactionError in logs — how do I retry correctly"
  - "UnknownTransactionCommitResult — did my transaction commit or not"
  - "should I use a transaction or a single-document atomic operation"
  - "withTransaction vs manual session.startTransaction retry loop"
  - "transaction read concern snapshot vs local vs majority"
  - "write concern majority vs w:1 on transaction commit"
  - "sharded cluster two-phase commit overhead"
  - "SnapshotTooOld error in a long-running transaction"
  - "migrating SQL BEGIN/COMMIT patterns to MongoDB"
whenNotToUse:
  - "Single-document update — use $inc, $push, findOneAndUpdate (always atomic, no session needed)"
  - "Error code lookup beyond transaction labels — use mongodb-error-codes"
  - "Query tuning or index design — use mongodb-query-performance or mongodb-indexes-deep"
  - "Schema design to avoid needing transactions — use mongodb-schema-design"
related_skills:
  - mongodb-error-codes
  - mongodb-schema-design
  - mongodb-replication
  - mongodb-sharding
  - mongodb-performance-troubleshooting
---

# MongoDB Transactions

---

## 1. Multi-Document Transactions Overview

MongoDB added multi-document ACID transactions in **4.0 (replica sets)** and extended them to **sharded clusters in 4.2**. Before 4.0, atomicity was limited to single-document operations (which remain the preferred approach for most use cases).

**ACID guarantees provided:**
- **Atomicity** — all writes in the transaction commit together or all are rolled back
- **Consistency** — data is moved from one valid state to another; session-level causal consistency is maintained
- **Isolation** — snapshot isolation: the transaction sees a consistent snapshot of data as of the transaction start; no dirty reads, no non-repeatable reads
- **Durability** — committed data survives node failures when `w: "majority"` is used

**Snapshot isolation** is the default isolation level since 4.0. Within a transaction, a client sees the data as it existed at transaction start, even if concurrent writers commit changes. This avoids dirty reads and non-repeatable reads but can cause write conflicts (two transactions modifying the same document — the second writer's commit or a read-write conflict will abort one of them).

```js
// Node.js — conceptual illustration of the ACID boundary
const session = client.startSession();
try {
  session.startTransaction({
    readConcern: { level: "snapshot" },
    writeConcern: { w: "majority" }
  });

  // Both writes are atomic — either both commit or neither does
  await orders.insertOne({ _id: orderId, item: "widget", qty: 5 }, { session });
  await inventory.updateOne(
    { item: "widget" },
    { $inc: { qty: -5 } },
    { session }
  );

  await session.commitTransaction();
} catch (err) {
  await session.abortTransaction();
  throw err;
} finally {
  await session.endSession();
}
```

---

## 2. Replica Set Transactions

All primary-based writes in a replica set transaction are routed to the primary. The session object carries the transaction state.

### Core API (explicit)

```js
const { MongoClient } = require("mongodb");

async function transferFunds(client, fromAcct, toAcct, amount) {
  const session = client.startSession();

  try {
    session.startTransaction({
      readConcern: { level: "snapshot" },
      writeConcern: { w: "majority", j: true }   // note: field is "j", not "journal"
    });

    const accounts = client.db("bank").collection("accounts");

    const from = await accounts.findOne({ _id: fromAcct }, { session });
    if (!from || from.balance < amount) {
      throw new Error("Insufficient funds");
    }

    await accounts.updateOne(
      { _id: fromAcct },
      { $inc: { balance: -amount } },
      { session }
    );
    await accounts.updateOne(
      { _id: toAcct },
      { $inc: { balance: amount } },
      { session }
    );

    await session.commitTransaction();
    console.log("Transfer committed");
  } catch (err) {
    await session.abortTransaction();
    console.error("Transaction aborted:", err.message);
    throw err;
  } finally {
    await session.endSession();
  }
}
```

### withTransaction() callback API (recommended)

`withTransaction()` handles commit retry and transient error retry automatically. Prefer this over the manual try/catch pattern. Available since Node.js driver 3.2+ and PyMongo 3.9+.

```js
async function transferWithHelper(client, fromAcct, toAcct, amount) {
  const session = client.startSession();
  try {
    // The driver passes the active session as the first argument to the callback.
    // Always use that parameter (not the outer `session` closure) so the callback
    // works correctly when withTransaction() retries it.
    await session.withTransaction(async (session) => {
      const accounts = client.db("bank").collection("accounts");

      const from = await accounts.findOne({ _id: fromAcct }, { session });
      if (!from || from.balance < amount) throw new Error("Insufficient funds");

      await accounts.updateOne(
        { _id: fromAcct }, { $inc: { balance: -amount } }, { session }
      );
      await accounts.updateOne(
        { _id: toAcct }, { $inc: { balance: amount } }, { session }
      );
    }, {
      readConcern: { level: "snapshot" },
      writeConcern: { w: "majority" }
    });
  } finally {
    await session.endSession();
  }
}
```

**Key methods:**
| Method | Purpose |
|---|---|
| `session.startTransaction(options)` | Begin transaction with optional read/write concern |
| `session.commitTransaction()` | Commit; returns a promise; retry on `UnknownTransactionCommitResult` |
| `session.abortTransaction()` | Roll back all operations in the transaction |
| `session.withTransaction(fn, options)` | Callback API; handles retry logic internally |
| `session.endSession()` | Release the session back to the pool |

---

## 3. Distributed Transactions on Sharded Clusters

Since MongoDB 4.2, multi-document transactions work across shards using **two-phase commit (2PC)**.

### Two-Phase Commit coordinator

When a transaction touches multiple shards, the `mongos` router designates one of the participant shards as the **coordinator** (the shard that receives the first write). The coordinator:
1. **Prepare phase** — sends `prepareTransaction` to all participant shards; each shard locks its data and votes yes/no
2. **Commit phase** — if all shards vote yes, coordinator sends `commitTransaction` to all; if any vote no, sends `abortTransaction`

The coordinator's decision is durable in `config.transactions` so recovery is possible after coordinator failure.

```js
// Sharded cluster transaction — same driver API; MongoDB routes internally
const session = client.startSession();
try {
  await session.withTransaction(async (session) => {
    // orders collection on shard A, inventory on shard B
    const orders = client.db("shop").collection("orders");
    const inventory = client.db("shop").collection("inventory");

    await orders.insertOne(
      { _id: new ObjectId(), customerId: "c1", sku: "sku-99", qty: 2 },
      { session }
    );
    await inventory.updateOne(
      { sku: "sku-99" },
      { $inc: { available: -2 } },
      { session }
    );
  }, { writeConcern: { w: "majority" } });
} finally {
  await session.endSession();
}
```

**Performance cost vs. replica set transactions:**
- 2PC adds at least one extra round-trip (prepare → commit) per participating shard
- Each shard holds WiredTiger write locks during the prepare phase
- Cross-shard transactions are 2–4× slower than replica set transactions under load
- Prefer co-locating transactional data on the same shard (zone sharding, compound shard keys) to avoid cross-shard transactions

---

## 4. Read Concern in Transactions

The read concern set on `startTransaction()` applies to all reads within the transaction.

| Read Concern | Behavior in transactions |
|---|---|
| `local` | Reads the latest data on the node; not guaranteed majority-committed, so reads can be rolled back on a failover — weakest durability guarantee of the three |
| `majority` | Reads data acknowledged by a majority of replica set members; slower but consistent with majority writes |
| `snapshot` | **Default since 4.0 for transactions.** Reads a consistent snapshot of data as of the transaction's start time; provides the strongest isolation |

```js
// Explicit snapshot read concern (this is the default, shown for clarity)
session.startTransaction({
  readConcern: { level: "snapshot" },
  writeConcern: { w: "majority" }
});

// local read concern — avoids majority read overhead, weaker consistency guarantee
session.startTransaction({
  readConcern: { level: "local" },
  writeConcern: { w: "majority" }
});
```

**Snapshot isolation detail:**
- MongoDB picks a `clusterTime` at transaction start as the snapshot point
- Reads within the transaction consistently see the state as of that clusterTime
- If the snapshot falls behind the oldest in-use WiredTiger snapshot, MongoDB will abort the transaction with `SnapshotTooOld` (increase `wiredTigerCacheSizeGB` or reduce long-running transactions)

```js
// Checking for SnapshotTooOld in error handling
// SnapshotTooOld carries TransientTransactionError label — use withTransaction() or
// manually abort, end the old session, and start a fresh one before retrying.
if (err.codeName === "SnapshotTooOld") {
  await session.abortTransaction();
  await session.endSession();
  // Create a new session — the old snapshot is gone and cannot be reused
  const newSession = client.startSession();
  return retryTransaction(client, newSession);
}
```

---

## 5. Write Concern in Transactions

Write concern on a transaction applies at **commit time** — it controls how many replica set members must acknowledge the commit before the driver considers it successful.

```js
// Recommended production write concern
session.startTransaction({
  readConcern: { level: "snapshot" },
  writeConcern: {
    w: "majority",    // majority of voting members must acknowledge
    j: true,          // commit must be written to journal (fsync)
    wtimeout: 5000    // abort if majority ack not received within 5 seconds
  }
});
```

**Write concern levels:**
| `w` value | Meaning |
|---|---|
| `1` | Only primary acknowledges — risk of data loss on primary failover |
| `"majority"` | Majority of voting members acknowledge — **recommended** |
| Number > 1 | Specific count of members must acknowledge |

**`j: true` (journaled):**
- Ensures the commit is written to the on-disk journal before returning success
- Protects against data loss from process crash (but not disk failure)
- Adds latency; omit only if you can tolerate potential data loss

**`wtimeout`:**
- If the majority acknowledgment isn't received within `wtimeout` milliseconds, the server returns a `WriteConcernError` (code 64 / `wtimeout`)
- The driver wraps this as an error with the `UnknownTransactionCommitResult` label — the transaction **may still have committed** on the primary; the outcome is uncertain
- Correct action: retry the commit only (not the full transaction body); `withTransaction()` does this automatically

```js
// Handle wtimeout — this is UnknownTransactionCommitResult territory
try {
  await session.commitTransaction();
} catch (err) {
  if (err.hasErrorLabel("UnknownTransactionCommitResult")) {
    // Commit may or may not have applied — retry commit only
    await session.commitTransaction(); // driver retries internally in withTransaction()
  } else {
    throw err;
  }
}
```

---

## 6. Transaction Limits

### Operation count
- No fixed cap on the number of operations (reads + writes) per transaction; the practical limit is oplog size and WiredTiger cache pressure (see below). (A "1,000 per transaction" figure sometimes cited is the driver bulk-write batch-group size, not a transaction limit.)

### Oplog entry size
- MongoDB 4.2 and earlier: each transaction generates a single oplog entry capped at **16 MB**
- MongoDB 4.4+: large transactions are broken into a chain of `applyOps` oplog entries, effectively **unlimited in size** (bounded only by available oplog space and WiredTiger cache)

### Transaction lifetime
```js
// mongosh — default is 60 seconds; raise for long-running batch transactions
db.adminCommand({ setParameter: 1, transactionLifetimeLimitSeconds: 120 })
```
- Transactions exceeding `transactionLifetimeLimitSeconds` are automatically aborted by the server
- Long-running transactions hold WiredTiger cache and delay checkpoint — keep transactions short

### WiredTiger cache pressure
- Active transactions pin the oldest required snapshot in the WiredTiger cache
- If cache pressure exceeds 95% utilization, MongoDB aborts the oldest transaction (`WriteConflict` or `TemporarilyUnavailable`)

```js
// Check transaction limits in your workload (Node.js driver)
// db here is client.db("admin") or any db handle — serverStatus is a server-level command
const serverStatus = await client.db("admin").command({ serverStatus: 1 });
console.log(serverStatus.wiredTiger.cache["tracked dirty bytes in the cache"]);
console.log(serverStatus.transactions); // currentActive, totalCommitted, totalAborted
```

---

## 7. Retryable Transactions

MongoDB drivers classify transaction errors into two categories that require different retry strategies.

### Error label taxonomy

| Error label | Meaning | Action |
|---|---|---|
| `TransientTransactionError` | Transaction aborted due to transient condition (write conflict, network blip, step-down) | **Abort and retry the entire transaction** |
| `UnknownTransactionCommitResult` | Commit result uncertain (network timeout, write concern timeout) | **Retry the commit only** — do not re-run the transaction body |

### Manual retry pattern (Node.js)

```js
// txnFunc signature: async (session) => void
// txnFunc is responsible for calling startTransaction() and all DB operations.
// runTransactionWithRetry handles abort-and-retry on TransientTransactionError.
async function runTransactionWithRetry(txnFunc, client) {
  const session = client.startSession();
  try {
    let attempts = 0;
    while (true) {
      try {
        attempts++;
        await txnFunc(session); // txnFunc must call session.startTransaction() internally
        break; // success — txnFunc called commitTransaction()
      } catch (err) {
        if (err.hasErrorLabel("TransientTransactionError") && attempts < 3) {
          console.log(`Transient error, retrying (attempt ${attempts})...`);
          await session.abortTransaction();
          continue; // restart: txnFunc will call startTransaction() again
        }
        throw err;
      }
    }
  } finally {
    await session.endSession();
  }
}

async function commitWithRetry(session) {
  let attempts = 0;
  while (true) {
    try {
      attempts++;
      await session.commitTransaction();
      break;
    } catch (err) {
      if (err.hasErrorLabel("UnknownTransactionCommitResult") && attempts < 3) {
        console.log(`Commit result unknown, retrying commit (attempt ${attempts})...`);
        continue;
      }
      throw err;
    }
  }
}
```

### Automatic retry via withTransaction()

`withTransaction()` handles both `TransientTransactionError` (retries the callback) and `UnknownTransactionCommitResult` (retries commit) automatically. This is the recommended production pattern.

```js
// withTransaction() — automatic retry for both error labels
const session = client.startSession();
try {
  await session.withTransaction(async (session) => {
    const orders = client.db("shop").collection("orders");
    const inventory = client.db("shop").collection("inventory");
    await orders.insertOne({ orderId: "o1", sku: "abc", qty: 1 }, { session });
    await inventory.updateOne({ sku: "abc" }, { $inc: { stock: -1 } }, { session });
  }, {
    readConcern: { level: "snapshot" },
    writeConcern: { w: "majority" }
  });
} finally {
  await session.endSession();
}
```

---

## 8. Driver Examples

### Node.js (mongodb driver 5.x+)

```js
const { MongoClient } = require("mongodb");

const client = new MongoClient(process.env.MONGO_URI);

async function placeOrder(customerId, sku, qty) {
  const session = client.startSession();
  try {
    await session.withTransaction(async (session) => {
      const db = client.db("shop");
      const inv = await db.collection("inventory").findOne({ sku }, { session });
      if (!inv || inv.stock < qty) throw new Error("Out of stock");

      await db.collection("orders").insertOne(
        { customerId, sku, qty, placedAt: new Date() },
        { session }
      );
      await db.collection("inventory").updateOne(
        { sku },
        { $inc: { stock: -qty } },
        { session }
      );
    }, {
      readConcern: { level: "snapshot" },
      writeConcern: { w: "majority" }
    });
    console.log("Order placed");
  } finally {
    await session.endSession();
  }
}
```

### Python (PyMongo 4.x) — callback API

```python
import os
from pymongo import MongoClient
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

client = MongoClient(os.environ["MONGO_URI"])

def place_order(customer_id, sku, qty):
    def txn_body(session):
        db = client["shop"]
        inv = db["inventory"].find_one({"sku": sku}, session=session)
        if not inv or inv["stock"] < qty:
            raise ValueError("Out of stock")
        db["orders"].insert_one(
            {"customer_id": customer_id, "sku": sku, "qty": qty},
            session=session
        )
        db["inventory"].update_one(
            {"sku": sku},
            {"$inc": {"stock": -qty}},
            session=session
        )

    with client.start_session() as session:
        session.with_transaction(
            txn_body,
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern(w="majority")
        )
```

### Python (PyMongo 4.x) — core API (explicit)

```python
from pymongo import MongoClient
from pymongo.errors import OperationFailure
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

def transfer_funds(client, from_id, to_id, amount):
    with client.start_session() as session:
        session.start_transaction(
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern(w="majority", j=True)
        )
        try:
            accts = client["bank"]["accounts"]
            src = accts.find_one({"_id": from_id}, session=session)
            if src["balance"] < amount:
                raise ValueError("Insufficient funds")
            accts.update_one({"_id": from_id}, {"$inc": {"balance": -amount}}, session=session)
            accts.update_one({"_id": to_id}, {"$inc": {"balance": amount}}, session=session)
            session.commit_transaction()
        except Exception:
            session.abort_transaction()
            raise
```

### Java (MongoDB driver 4.x)

```java
import com.mongodb.client.ClientSession;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.TransactionBody;
import com.mongodb.ReadConcern;
import com.mongodb.TransactionOptions;
import com.mongodb.WriteConcern;
import org.bson.Document;
import static com.mongodb.client.model.Filters.eq;
import static com.mongodb.client.model.Updates.inc;

try (ClientSession session = client.startSession()) {
    TransactionOptions txnOptions = TransactionOptions.builder()
        .readConcern(ReadConcern.SNAPSHOT)
        .writeConcern(WriteConcern.MAJORITY)
        .build();

    session.withTransaction((TransactionBody<Void>) () -> {
        MongoCollection<Document> orders = client
            .getDatabase("shop").getCollection("orders");
        MongoCollection<Document> inventory = client
            .getDatabase("shop").getCollection("inventory");

        Document inv = inventory.find(session, eq("sku", sku)).first();
        if (inv == null || inv.getInteger("stock") < qty) {
            throw new RuntimeException("Out of stock");
        }
        orders.insertOne(session, new Document("sku", sku).append("qty", qty));
        inventory.updateOne(session, eq("sku", sku), inc("stock", -qty));
        return null;
    }, txnOptions);
}
```

---

## 9. Performance Impact

### Overhead measurement

Compared to a non-transactional equivalent write, a 2-operation replica set transaction adds:
- **~1–2 ms** coordinator overhead on a local cluster
- **~5–15 ms** additional latency on a cross-datacenter replica set (round-trip for majority ack)
- **~2–4×** slower throughput under high concurrency due to write-conflict aborts

```js
// Benchmark helper — compare transactional vs non-transactional
async function benchmarkTxn(client, iterations) {
  const start = Date.now();
  for (let i = 0; i < iterations; i++) {
    const session = client.startSession();
    try {
      await session.withTransaction(async () => {
        await client.db("bench").collection("a")
          .updateOne({ _id: 1 }, { $inc: { n: 1 } }, { session });
        await client.db("bench").collection("b")
          .updateOne({ _id: 1 }, { $inc: { n: 1 } }, { session });
      }, { writeConcern: { w: "majority" } });
    } finally {
      await session.endSession();
    }
  }
  console.log(`${iterations} txns in ${Date.now() - start}ms`);
}
```

### Write conflict storms

When many concurrent transactions attempt to modify the same document, MongoDB aborts all but the first writer, forcing retries. This is "hot document" contention.

```js
// Detect write conflict storms in server status
const status = await db.admin().serverStatus();
// metrics.operation.writeConflicts — count of write-conflict retries at the storage layer
console.log("writeConflicts:", status.metrics.operation.writeConflicts);
// WiredTiger transaction conflict counter (equivalent low-level metric):
console.log("wtConflicts:", status.wiredTiger.transaction["transaction conflicts between concurrent transactions"]);
```

**Mitigations:**
- Redesign schema to avoid hot documents (counters, queue heads)
- Use `$inc` on a field that's rarely contended vs. an array that many writers append to
- Rate-limit transactional writers at the application layer

### When NOT to use transactions

| Scenario | Better alternative |
|---|---|
| Update a single document | Atomic single-doc operations (`$inc`, `$push`, `$set`, `findAndModify`) — always atomic without a session |
| Append to an event log | `insertOne` — single-doc inserts are already atomic |
| Read-then-write on a single document | `findOneAndUpdate` with `returnDocument: "after"` |
| Idempotent upsert | `updateOne` with `upsert: true` |
| Counter increment | `$inc` — atomic, no transaction needed |

---

## 10. Anti-Patterns

### Anti-patterns summary table

| Anti-pattern | Problem | Fix |
|---|---|---|
| Long-running transactions (> a few seconds) | Hold WiredTiger cache, delay checkpoints, risk `SnapshotTooOld` abort | Break into smaller transactions; denormalize to reduce operations per transaction |
| Using transactions for single-document operations | 5–10× overhead vs. atomic single-doc ops; no correctness benefit | Use `$inc`, `$push`, `findOneAndUpdate`, `updateOne` instead |
| Ignoring `TransientTransactionError` | Transaction silently fails without data change; caller gets incorrect success | Always check error labels; retry the full transaction body |
| Using `w: 1` (not majority) on commit | Risk of data loss if primary steps down before secondaries replicate | Always commit with `w: "majority"` in production |
| Not calling `endSession()` | Session leak; connection pool exhaustion after many failed transactions | Use `try/finally` to always call `session.endSession()` |
| Re-using a session across unrelated logical operations | State contamination; causal consistency applied where not intended | Create a new session per logical transaction unit |
| Modifying the same hot document in concurrent transactions | Write conflict storm; high abort/retry rate | Redesign schema to distribute writes (bucketing, sharding, counters array) |
| Catching errors and not checking `hasErrorLabel()` | Retrying commit when a `TransientTransactionError` requires full retry (or vice versa) | Check `err.hasErrorLabel("TransientTransactionError")` vs `"UnknownTransactionCommitResult"` |

### Long-running transaction example (what NOT to do)

```js
// ANTI-PATTERN: fetching external data inside a transaction
const session = client.startSession();
session.startTransaction();

const doc = await collection.findOne({ _id: id }, { session });

// BAD: this HTTP call takes 3 seconds — transaction holds snapshot the entire time
const enriched = await fetch(`https://api.example.com/enrich/${doc.key}`);

await collection.updateOne({ _id: id }, { $set: { extra: enriched.data } }, { session });
await session.commitTransaction(); // may fail with SnapshotTooOld
await session.endSession();
```

```js
// CORRECT: fetch external data BEFORE opening the transaction
const doc = await collection.findOne({ _id: id }); // non-transactional read
const enriched = await fetch(`https://api.example.com/enrich/${doc.key}`); // outside txn

// Only the DB writes are inside the transaction — runs in < 10ms
const session = client.startSession();
try {
  await session.withTransaction(async (session) => {
    await collection.updateOne(
      { _id: id },
      { $set: { extra: enriched.data } },
      { session }
    );
  }, { writeConcern: { w: "majority" } });
} finally {
  await session.endSession();
}
```

---

## References

1. https://www.mongodb.com/docs/manual/core/transactions/
2. https://www.mongodb.com/docs/manual/core/transactions-in-applications/
3. https://www.mongodb.com/docs/manual/core/transactions-production-consideration/
4. https://www.mongodb.com/docs/manual/reference/method/Session.startTransaction/
5. https://www.mongodb.com/docs/drivers/node/current/fundamentals/transactions/
6. https://www.mongodb.com/docs/manual/core/read-isolation-consistency-recency/
