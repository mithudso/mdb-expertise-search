<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-error-codes` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-error-codes
description: >-
  Diagnose MongoDB server error codes and drive correct driver retry behavior.
  Catalogs numeric codes (6, 9001, 24, 50, 89, 91, 112, 121, 133, 134, 148,
  189, 211, 251, 262, 280, 286, 292, 11000, 18/8000, 40415), error labels
  (RetryableWriteError, TransientTransactionError, UnknownTransactionCommitResult,
  NoWritesPerformed), retryable-writes/reads spec semantics, Client-Side Operations
  Timeout (timeoutMS/CSOT), withTransaction patterns, exponential backoff with
  jitter, circuit breakers, idempotency keys, Atlas-specific errors (Flex
  500-connection cap, connection storms from Lambda), change-stream resume
  failures, and SCRAM/auth troubleshooting. TRIGGER: a MongoDB driver error
  surfaces in logs; a support ticket cites an error code; designing retry/backoff
  logic around MongoDB calls; auditing transaction retry loops; debugging
  change-stream resume tokens; timeoutMS vs maxTimeMS vs socketTimeoutMS question.
  SKIP: general MongoDB query design, schema, indexing, or aggregation tuning
  (mongodb-developer, mongodb-schema-design, mongodb-indexes-deep,
  mongodb-aggregation-pipeline); transaction design with no error-handling angle
  (mongodb-transactions).
category: mongodb
version: "1.1.0"
updated: "2026-05-29"
tags:
  - mongodb
  - errors
  - drivers
  - retry
  - transactions
  - change-streams
  - atlas
  - csot
  - reliability
keywords:
  - error code
  - error label
  - RetryableWriteError
  - TransientTransactionError
  - UnknownTransactionCommitResult
  - timeoutMS
  - CSOT
  - retryWrites
  - retryReads
  - WriteConflict
  - LockTimeout
  - PrimarySteppedDown
  - ShutdownInProgress
  - ChangeStreamHistoryLost
  - DocumentValidationFailure
  - ExceededMemoryLimit
  - NoSuchTransaction
  - AuthenticationFailed
  - SocketException
  - HostUnreachable
  - Atlas Flex connection limit
  - connection storm
  - exponential backoff
  - circuit breaker
  - idempotency key
  - SCRAM-SHA-256
whenToUse:
  - "I see a MongoDB error code in a stack trace"
  - "the driver returned RetryableWriteError"
  - "my transaction is retrying in a loop"
  - "change stream is failing with ChangeStreamHistoryLost"
  - "design retry/backoff for MongoDB calls"
  - "Atlas Flex 500 connection limit exceeded"
  - "Lambda connection storm to Atlas"
  - "what does code 112 mean"
  - "timeoutMS vs maxTimeMS vs socketTimeoutMS"
  - "WriteConflict in a transaction"
  - "withTransaction vs manual retry loop"
  - "SCRAM authentication failure — wrong password or authSource"
whenNotToUse:
  - "Designing a schema or choosing a shard key — use mongodb-schema-design or mongodb-sharding"
  - "Slow query tuning where the query succeeds — use mongodb-query-performance"
  - "Transaction design with no error-handling question — use mongodb-transactions"
  - "Choosing a driver or ORM — use mongodb-developer"
related_skills:
  - mongodb-transactions
  - mongodb-change-streams
  - mongodb-performance-troubleshooting
  - mongodb-developer
  - mongodb-atlas-expert
---

# MongoDB Error Codes and Driver Error Handling

A support-grade catalog of the MongoDB server error codes you will actually see in production, paired with the driver behavior, retry semantics, and remediation patterns needed to handle them correctly. Complements `mongodb-kb` (broad ops), `mongodb-developer` (driver usage), `mongodb-transactions` (transient errors), `mongodb-performance-troubleshooting` (timeout investigation).

### When to use this skill

- A MongoDB driver error has a numeric code or label you need to interpret.
- You are writing or reviewing retry / backoff / circuit-breaker code around a MongoDB client.
- A transaction is failing intermittently and you suspect a retry-loop bug.
- A change stream is dying with a resume-token error.
- An Atlas Flex / Serverless cluster is throwing connection or RPU errors.

### When NOT to use this skill

- Designing a new schema, picking shard keys, or building indexes (use `mongodb-schema-design`, `mongodb-sharding`, `mongodb-indexes-deep`).
- Tuning a slow query that succeeds but takes too long (use `mongodb-query-performance`).
- Choosing a driver, ORM, or framework integration (use `mongodb-developer`).

### Triage order — read this before anything else

When you see a MongoDB error, answer in order:

1. **What is the code and label?** Read `error.code`, `error.codeName`, and `error.errorLabels` — never the message alone.
2. **Is it retryable by the driver?** If `error.errorLabels` includes `RetryableWriteError`, `TransientTransactionError`, or `UnknownTransactionCommitResult`, the driver already retried (or will). Section 2 explains each.
3. **Will the next attempt likely succeed, or do I need to fix something first?** If labels are absent, the driver gave up; you must either fix the cause or retry at the application layer with deliberate backoff (Section 7).

---

## Section 1: Top operationally important error codes

Each entry follows the same shape: **code, name, server family, retry semantics, common causes, fix**.

### Code 6 — HostUnreachable

- **Family:** Network / NetworkError
- **Retryable:** Yes (driver retries automatically for retryable reads/writes when `retryWrites=true` / `retryReads=true`)
- **Source:** Server marks this as `NetworkError`; drivers translate as transient.
- **Common causes:**
  - DNS lookup failed during SRV resolution.
  - Firewall or security-group rule blocks the target port (27017, or 27015-27019 for sharded clusters).
  - Atlas IP access list missing the client's egress IP.
  - VPC/VNet peering or PrivateLink misconfigured.
  - Replica set member down and the driver hasn't refreshed its view of the topology yet.
- **Fix:** Validate `mongosh` reaches the cluster from the same host. Confirm Atlas access list. For multi-VPC setups, run a TCP probe (`nc -zv host port`) from the failing region. If transient and retries succeed, no action needed; if persistent, the issue is infrastructure.

### Code 9001 — SocketException

- **Family:** Network / NetworkError
- **Retryable:** Yes (driver-level)
- **Common causes:**
  - TCP RST mid-conversation (NAT idle timeout, load balancer drop, OS-level reset).
  - Server `closeAllOpenConnections` during step-down.
  - Driver socket timeout (`socketTimeoutMS`) shorter than a long-running operation.
  - Kubernetes/Istio sidecar killing idle connections.
- **Fix:** Inspect mongod log around the error time; `closing socket` lines name the trigger. If `socketTimeoutMS` is set too low (legacy guidance was 360s; the modern pattern is `timeoutMS` per operation, leave socket timeout at default or 0), raise it. Add TCP keepalives at the OS layer (`net.ipv4.tcp_keepalive_time=120`) when traversing NATs.

### Code 24 — LockTimeout

- **Family:** Concurrency
- **Retryable:** No automatic driver retry. Safe to retry at the application layer **only** if the operation is idempotent or guarded by an idempotency key.
- **Lock wait controls (the precise knobs, by version):**
  - `maxTimeMS` per operation (no default — unset means wait indefinitely on the lock queue).
  - `maxTransactionLockRequestTimeoutMillis` for transactions (default **5ms** in 4.0+; transactions fail fast on lock contention by design).
  - Chunk migration lock acquisition uses an internal timeout (typically tens of seconds).
- **Common causes:**
  - Long-running operation holds a collection or database IX lock; a chunk migration, `createIndex` (in 4.2 and earlier, the foreground variant), DDL, or another writer is blocked.
  - High write concurrency under WiredTiger cache pressure.
  - Transaction lock conflict with a non-transactional writer.
- **Fix:** Inspect `db.currentOp({ "active": true, "secs_running": { $gte: 1 } })` for the lock holder and `db.serverStatus().globalLock.currentQueue`. Often resolves itself if the blocker completes; if persistent, kill the blocker (after confirming safe), reduce write concurrency, or split the offending operation. From 4.2+ `createIndex` is always background — older guidance about `background: true` no longer applies.
- **Note:** Code 24 sometimes surfaces alongside or interleaved with code 50 / 251 depending on whether the lock-wait was bounded by `maxTimeMS`, the transaction-lock-timeout, or the global lock-acquire timeout.

### Code 50 — MaxTimeMSExpired

- **Family:** Timeout
- **Retryable:** No — `MaxTimeMSExpired` is a deliberate client-imposed deadline (`maxTimeMS`), so the driver does not auto-retry it; retrying would just re-hit the same cap. Do not confuse it with `ExceededTimeLimit` (code **262**), a separate server-internal timeout that the driver *does* treat as retryable (it carries the `RetryableWriteError` label).
- **Note:** Code 50 (`MaxTimeMSExpired`) and code 262 (`ExceededTimeLimit`) are both timeout-family but distinct; only 262 is driver-retryable. Always read the error message and code together, since a `maxTimeMS` budget can also be tripped by a slow lock wait.
- **Common causes:**
  - `maxTimeMS` per-operation budget exceeded (intentional client cap).
  - Aggregation pipeline that scans too many documents without an index.
  - Sort spilling to disk and falling outside the time budget.
  - In sharded clusters, mongos waiting for a slow shard.
- **Fix:** Run `explain()` on the query — look for `COLLSCAN` or large `nReturned/nScanned` ratios. Add an index. Increase `maxTimeMS` if the work genuinely needs more headroom, but treat large jumps as a symptom of a missing index, not a tuning fix.

### Code 89 — NetworkTimeout

- **Family:** Driver-emitted, server-side equivalent is `ExceededTimeLimit` family
- **Retryable:** Yes (driver-level)
- **Common causes:**
  - `socketTimeoutMS` reached on a request that took longer than expected.
  - Driver gave up before mongod responded.
  - Stale topology — driver tried a server that is no longer responsive.
- **Fix:** Same posture as 9001. Prefer `timeoutMS` (CSOT) over `socketTimeoutMS` to bound the whole operation lifecycle instead of just the socket. CSOT was introduced in driver-spec terms in 2024 and is now stable across Node 5.x+, Java 5.x+, Go 1.13+, Python 4.x.

### Code 91 — ShutdownInProgress

- **Family:** Server lifecycle
- **Retryable:** Yes (drivers retry; carries `RetryableWriteError` label on write ops).
- **Common causes:**
  - Atlas cluster scale-up / scale-down / patch in progress.
  - Manual `db.shutdownServer()` invocation.
  - Replica set rolling restart for OS or MongoDB version upgrades.
  - Pod termination in Kubernetes (preStop hook draining connections).
- **Fix:** Usually transient; let driver retries handle it. If sustained more than 30-60 seconds, check Atlas Activity Feed or your orchestrator for in-progress maintenance. Confirm `retryWrites=true` in connection string (it has been default since driver-spec 4.2).
- **Special case:** ShutdownInProgress during the SCRAM handshake itself is also retryable (added explicitly in the spec).

### Code 112 — WriteConflict

- **Family:** Transaction / Concurrency
- **Retryable:** Yes at application layer (transactions) — carries `TransientTransactionError` label when raised inside a transaction.
- **Common causes:**
  - Two transactions modify the same document or unique index entry.
  - High contention on a "hot" document (e.g., counter, sequence).
  - WiredTiger snapshot isolation conflict; the loser must retry.
- **Fix:**
  - In a transaction, **rewrap the entire transaction** in a retry loop (don't just retry the failing op). Drivers ship a `withTransaction` helper that does this; never write your own retry loop without one.
  - Outside transactions, retryable writes will absorb single-doc updates automatically.
  - Reduce contention: shard the hot collection, or split counters into N shards and sum on read.
- **Trap:** Spring Data MongoDB used to translate 112 to `DataIntegrityViolationException` and lose the retry hint. Modern Spring (>=4.x) preserves the label, but verify on older stacks.

### Code 121 — DocumentValidationFailure

- **Family:** Schema validation (`$jsonSchema`, `validator`)
- **Retryable:** No (deterministic; the document is wrong)
- **Common causes:**
  - Document violates a collection validator (`validator`/`$jsonSchema`/`validationLevel`).
  - Required field missing, type mismatch, value outside enum, fails `pattern`.
  - `validationLevel: strict` (default) blocks all updates that would not pass validation; `moderate` only blocks if the document already passed.
- **Fix:** Inspect `errInfo` on the error response — it contains a structured object describing which rule failed and at which path. Drivers expose this as `error.errInfo` or `error.writeErrors[i].errInfo`. Fix the document or relax the validator.

### Code 133 — FailedToSatisfyReadPreference

- **Family:** Server selection
- **Retryable:** Yes (`retryReads=true`; driver retries on a fresh server-selection attempt)
- **Common causes:**
  - No member matches the chosen read preference (e.g., `primaryPreferred` with no primary during an election).
  - Tag-set read preference where no member has the tag.
  - `maxStalenessSeconds` excludes all secondaries.
  - Hidden/delayed members miscounted as eligible.
- **Fix:** Confirm replica set status (`rs.status()`) — is there a primary? Check tag configuration on members. If the issue is election-timing, retries usually succeed within the 10-second `serverSelectionTimeoutMS` default. If persistent, broaden the read preference or fix the topology.

### Code 134 — ReadConcernMajorityNotAvailableYet

- **Family:** Read concern
- **Retryable:** Yes (server marks as `RetriableError`; drivers retry under `retryReads=true`)
- **Common causes:**
  - Majority commit point hasn't advanced because a member is down or lagging — `majority` read concern can't be satisfied yet.
  - Brief during initial election or after a step-down.
  - Common during `getMore` on a cursor when the committed view shifts.
- **Fix:** Almost always transient and resolves on driver retry. If sustained, fix the lagging member or the majority quorum (e.g., PSA architecture with arbiter down may struggle to advance the commit point).

### Code 148 — ReadConcernMajorityNotEnabled (do not confuse with 134)

- **Family:** Read concern / configuration
- **Retryable:** **No** — this is a config problem, not a transient state.
- **Common causes:** `--enableMajorityReadConcern false` was set on the mongod (a legacy flag). From 4.2+ majority read concern is permanently on and cannot be disabled, so 148 typically only appears against older clusters or against a `mongod` started with an explicit override.
- **Fix:** Remove `--enableMajorityReadConcern false`, restart mongod, and confirm `db.serverStatus().storageEngine.persistent === true`. If the deployment is 4.2+, audit startup flags and config files for stale overrides.

### Code 189 — PrimarySteppedDown

- **Family:** Replica set lifecycle
- **Retryable:** Yes — carries `RetryableWriteError` label; drivers retry on the new primary after election.
- **Common causes:**
  - Atlas cluster patch / version upgrade (rolling step-down).
  - Manual `rs.stepDown()`.
  - Heartbeat failure forcing the primary to step down.
  - Network partition that loses the primary's quorum.
- **Fix:** Let driver retries handle it. Election completes in ~10s for typical replica sets. If you see 189 frequently outside maintenance windows, investigate primary stability (CPU pressure, disk I/O, network issues to the primary specifically).

### Code 211 — KeyNotFound

- **Family:** Two flavors — be careful:
  1. **HMAC key not found** (cluster-time signing key). Indicates the cluster's key vault has rotated and a stale gossip token is being presented. Usually transient after a few seconds.
  2. **Application-level "key" missing** in older driver paths (rare; mostly historical).
- **Retryable:** Yes for the HMAC flavor.
- **Common causes:** Time skew across cluster members; key rotation timing.
- **Fix:** Sync NTP across cluster members. Verify `db.serverStatus().clusterTime` is current. Usually self-healing.

### Code 251 — NoSuchTransaction

- **Family:** Transaction lifecycle
- **Retryable:** Yes — carries `TransientTransactionError` label (you retry the **whole transaction**, not the failing op).
- **Common causes:**
  - Transaction exceeded `transactionLifetimeLimitSeconds` (default 60s) and was aborted server-side.
  - `lsid` (logical session) expired due to network partition.
  - Mongos lost track of the transaction state.
  - A previous operation in the transaction failed, aborting it, but the application kept sending ops.
- **Fix:** Rewrap in `withTransaction`. Audit transaction body for ops that take longer than 60s (split into batches). Tune `transactionLifetimeLimitSeconds` only as a last resort — long transactions are usually a design smell.

### Code 292 — QueryExceededMemoryLimitNoDiskUseAllowed (ExceededMemoryLimit)

- **Family:** Aggregation / sort
- **Retryable:** No (deterministic without changes)
- **Default budget:** 100MB per stage (`internalQueryMaxBlockingSortMemoryUsageBytes`, `allowDiskUse`).
- **Common causes:**
  - `$sort`, `$group`, or `$bucket` requires >100MB of in-memory state.
  - Aggregation without supporting index hits the threshold on intermediate stages.
- **Fix:**
  - Add `{ allowDiskUse: true }` to the aggregation call (Node: `aggregate(pipeline, { allowDiskUse: true })`, Java: `.allowDiskUse(true)`). Note: `allowDiskUse` is **default true** in 6.0+ for aggregations, but **still required for `find().sort()`** without an index.
  - Better: add an index that supports the sort so the engine doesn't materialize.
  - Best: redesign the pipeline to use accumulators that don't require buffering full document state.

### Code 18 — AuthenticationFailed (and code 8000 — older AtlasError alias)

- **Family:** Authentication / SCRAM
- **Retryable:** No (deterministic credential failure). Drivers do not retry auth failures.
- **Common causes:**
  - Wrong username or password.
  - Special characters in password not percent-encoded in URI.
  - `authSource` missing — credentials live in a non-default DB (often `admin`).
  - SCRAM mechanism mismatch: client expects SCRAM-SHA-1, server only allows SCRAM-SHA-256 (or vice versa).
  - User's mechanism list doesn't include what the driver is negotiating.
  - Atlas IP access list rejected the IP (some Atlas paths surface as 18 instead of network errors).
- **Fix:**
  - Verify with `mongosh "<connection-string>"` from the same host as the failing client.
  - Percent-encode special characters (`@`, `:`, `/`, `?`, `#`, `[`, `]`).
  - Add `?authSource=admin` (or the correct DB) to the URI.
  - In Atlas, ensure the DB user has SCRAM-SHA-256 enabled (default for new users since 4.0).
  - **Code 8000** historically appeared as an Atlas wrapper around auth/permission errors and certain proxy-layer rejections; modern Atlas largely surfaces 18.

### Code 40415 — Unknown field (BSON parsing / validator)

- **Family:** Schema / BSON validation
- **Retryable:** No (deterministic)
- **Common causes:**
  - `$jsonSchema` with `additionalProperties: false` rejects a field that's in your document but not in the schema.
  - Command-level: a parameter name you sent is not recognized (driver/version mismatch).
- **Fix:** Either remove the offending field from the document, add it to the schema, or set `additionalProperties: true`. If command-level, upgrade the driver or check option name against the target server version.

### Code 286 — ChangeStreamHistoryLost

- **Family:** Change streams
- **Retryable:** **No** at the resume-token level (token is permanently invalid). Application MUST reset the token and re-establish from the present.
- **Common causes:**
  - Application was offline longer than the cluster's oplog retention window (default ~24h on Atlas, can be tuned with `replSetResizeOplog` or `oplogMinRetentionHours`).
  - Cluster underwent a sync (initial sync / mongosync) that truncated history.
  - Cluster migrated to a new replica set / restored from backup.
- **Fix:**
  - Catch error code 286 explicitly. Drop the saved resume token. Open a fresh change stream (from current time, or from a known recovery point in a checkpoint system).
  - Increase oplog retention: `db.adminCommand({ replSetResizeOplog: 1, minRetentionHours: 72 })`.
  - On Atlas, raise the oplog size via cluster tier upgrade or by enabling configurable retention.
  - For long downtime windows, snapshot the resume token after every batch so the gap is small.

---

## Section 2: Error labels — the real contract

Error labels are how MongoDB tells drivers (and you) what kind of error this is, separate from the code. Reading **only the code** is the single biggest mistake teams make.

### `RetryableWriteError`

- **Where it appears:** On the top-level error object's `errorLabels` array.
- **Driver behavior:** If `retryWrites=true` on the `MongoClient`, the driver retries the operation exactly **once** on a new primary (one retry per spec, not infinite — except under CSOT, see below).
- **What carries it:** Network errors, `PoolClearedError`, `NotWritablePrimary` (10107), `NotWritablePrimaryNoSlaveOk` (13435), `InterruptedAtShutdown` (11600), `InterruptedDueToReplStateChange` (11602), `LegacyNotPrimary` (10058), `NotPrimaryOrSecondary` (13436), `PrimarySteppedDown` (189), `ShutdownInProgress` (91), `HostNotFound` (7), `HostUnreachable` (6), `NetworkTimeout` (89), `SocketException` (9001), `ExceededTimeLimit` (262).
- **What does NOT carry it:** Any error inside a transaction other than `commitTransaction` / `abortTransaction`. Drivers MUST NOT add this label inside a non-commit/abort transaction op.

### `TransientTransactionError`

- **Where it appears:** Same `errorLabels` array.
- **Driver behavior:** Application (or `withTransaction`) should retry the **entire transaction** — re-issue every op from the start of the transaction.
- **What carries it:**
  - Any error encountered running a non-commit/abort op in a transaction where the server replied (including 112 `WriteConflict`, 251 `NoSuchTransaction`).
  - Any network error or server-selection error running a non-commit op (driver adds the label client-side).
  - For `commitTransaction`, see `UnknownTransactionCommitResult` (it's labeled differently).
- **Pattern:** Use `session.withTransaction(async () => { ... })`. It already handles both `TransientTransactionError` and `UnknownTransactionCommitResult` correctly.

### `UnknownTransactionCommitResult`

- **Driver behavior:** Retry only `commitTransaction`, not the body. The transaction may have committed or not; commit is idempotent within the same `lsid`/`txnNumber`, so retrying is safe.
- **What carries it:** Network errors, retryable-write-eligible errors, certain explicit codes (50 ExceededTimeLimit, 64 WriteConcernFailed, 91 ShutdownInProgress, 189 PrimarySteppedDown, etc.) on `commitTransaction`.

### `NoWritesPerformed`

- **Driver behavior:** Diagnostic only — tells you the write definitely didn't happen, so the retry will produce the same effect as the first attempt would have.
- **Use case:** Application logic that wants to distinguish "we don't know if it landed" from "we know it didn't land."

---

## Section 3: Retryable Writes — the spec contract

Retryable writes (`retryWrites=true`, default since driver-spec 4.2) cover **single-document writes** automatically. Multi-document writes are NOT retryable as a unit; retry happens per operation.

### What's retryable as a single retryable write

- `insertOne`, `updateOne`, `replaceOne`, `deleteOne`, `findOneAndUpdate`, `findOneAndReplace`, `findOneAndDelete`.
- `insertMany` (the spec breaks this into individual single-doc writes server-side).
- `bulkWrite` with no multi-doc updates (`updateMany`/`deleteMany`).

### What's NOT retryable

- `updateMany`, `deleteMany` — these cannot be retried because the server can't safely tell whether they completed partially.
- Aggregations with `$out` / `$merge`.
- Operations inside a transaction (except `commitTransaction`/`abortTransaction`).

### Retry count

- Default: **one retry** per operation.
- With CSOT (`timeoutMS`): drivers retry **as many times as fit within the timeout budget**. No exponential backoff added by the driver (intentionally — the spec rejected backoff to prevent staleness).

### Operationally, this means:

```javascript
// Node.js driver — retryWrites=true is implicit since 4.0
const client = new MongoClient(uri); // retryWrites=true default
await client.connect();

// Single-doc write — driver will retry once on RetryableWriteError
await client.db('app').collection('users').updateOne(
  { _id: userId },
  { $inc: { loginCount: 1 } }
);
```

To turn off, append `?retryWrites=false` — but you almost never want to.

---

## Section 4: Retryable Reads — symmetric but with caveats

Retryable reads (`retryReads=true`, default since driver-spec 4.2):

- Driver retries a read on a fresh server-selection cycle.
- Default: one retry, more under CSOT budget.
- Covered ops: `find`, `aggregate` (without `$out`/`$merge`), `count`, `distinct`, `estimatedDocumentCount`, listing ops.
- Not covered: change streams (they have their own resume mechanism), cursor `getMore` after a network error (driver MUST NOT silently retry `getMore`; the cursor is gone).

The same retryable-error families apply: networks, step-down, shutdown, 50/91/89/189/9001/6/7.

---

## Section 5: Client-Side Operations Timeout (CSOT) — `timeoutMS`

CSOT is the modern, driver-spec-mandated way to bound the entire operation lifecycle. It supersedes (but does not remove) `socketTimeoutMS`, `serverSelectionTimeoutMS`, `connectTimeoutMS`, `maxTimeMS`, and `wTimeoutMS`.

### Setup

```javascript
// Node 5.x+
const client = new MongoClient(uri, { timeoutMS: 5000 });

// Per-operation override
await collection.findOne({ _id: id }, { timeoutMS: 1000 });

// Per-database / per-collection
const db = client.db('app', { timeoutMS: 2000 });
```

Java:
```java
MongoClientSettings settings = MongoClientSettings.builder()
    .applyConnectionString(new ConnectionString(uri))
    .timeout(5000, TimeUnit.MILLISECONDS)
    .build();
```

Go:
```go
opts := options.Client().ApplyURI(uri).SetTimeout(5 * time.Second)
```

### What CSOT changes

- **Retries are budgeted.** If a retryable error occurs, the driver retries until the timeout expires — no fixed retry count.
- **No driver-added backoff.** The spec deliberately rejected exponential backoff inside the driver. If you want backoff, do it at the **application** layer.
- **Replaces `maxTimeMS`.** When `timeoutMS` is set, drivers compute the per-operation `maxTimeMS` from the remaining budget. Do not set both — the spec gives `timeoutMS` precedence.
- **Replaces `socketTimeoutMS`.** Drivers will close sockets when the timeout expires regardless of the socket-level setting.

### Migration guidance

| Old setting | New CSOT replacement |
| --- | --- |
| `socketTimeoutMS` | `timeoutMS` (covers more) |
| `wtimeoutMS` (write concern) | `timeoutMS` (write concern timeout is derived) |
| `maxTimeMS` per op | `timeoutMS` per op |
| `serverSelectionTimeoutMS` | Still respected, but the overall `timeoutMS` caps it |

---

## Section 6: Transient Transaction Errors — the right loop shape

The single most common transaction bug is hand-rolling a retry loop. Drivers ship `withTransaction` — use it.

### Correct: `withTransaction`

```javascript
const session = client.startSession();
try {
  const result = await session.withTransaction(async () => {
    await ordersColl.insertOne({ /* ... */ }, { session });
    await inventoryColl.updateOne(
      { _id: sku, qty: { $gte: 1 } },
      { $inc: { qty: -1 } },
      { session }
    );
    // If WriteConflict (112) is raised here, withTransaction
    // sees TransientTransactionError and re-runs the whole block.
  }, {
    readPreference: 'primary',
    readConcern: { level: 'snapshot' },
    writeConcern: { w: 'majority' },
  });
} finally {
  await session.endSession();
}
```

`withTransaction` keeps retrying for up to **120 seconds** (the spec default `MaxCommitTimeMS`) and handles both `TransientTransactionError` (retry the body) and `UnknownTransactionCommitResult` (retry the commit).

### Wrong: manual loop without label checking

```javascript
// DON'T do this — misses UnknownTransactionCommitResult and burns retries
for (let i = 0; i < 5; i++) {
  try {
    session.startTransaction();
    // ... ops ...
    await session.commitTransaction();
    break;
  } catch (e) {
    await session.abortTransaction();
    // No label check — retrying a logical error infinitely
  }
}
```

If you absolutely must hand-roll, branch on `error.errorLabels.includes('TransientTransactionError')` and `error.errorLabels.includes('UnknownTransactionCommitResult')` separately.

---

## Section 7: Application error handling patterns

### Pattern 1: Exponential backoff with jitter (application layer)

For non-retryable-by-driver errors that you still want to retry (e.g., 24 LockTimeout, 50 if you want extra attempts beyond CSOT, 121 if data is being repaired upstream):

```javascript
async function retryWithBackoff(fn, {
  maxAttempts = 5,
  baseMs = 100,
  capMs = 5000,
  retryOn = (e) => isTransient(e),
} = {}) {
  let attempt = 0;
  while (true) {
    try {
      return await fn();
    } catch (e) {
      attempt += 1;
      if (attempt >= maxAttempts || !retryOn(e)) throw e;
      const exp = Math.min(capMs, baseMs * 2 ** (attempt - 1));
      const jitter = Math.random() * exp;
      await new Promise(r => setTimeout(r, jitter));
    }
  }
}

function isTransient(e) {
  if (!e) return false;
  const labels = e.errorLabels || [];
  if (labels.includes('RetryableWriteError')) return true;
  if (labels.includes('TransientTransactionError')) return true;
  const code = e.code || (e.writeErrors?.[0]?.code);
  const transientCodes = new Set([6, 7, 89, 91, 134, 189, 9001]);
  return transientCodes.has(code);
}
```

Cap retries to avoid amplifying upstream incidents. Always jitter (full jitter is the safest default — see AWS Architecture Blog "Exponential Backoff and Jitter").

### Pattern 2: Circuit breaker

Wrap the MongoDB client behind a circuit breaker (e.g., `opossum` in Node, `resilience4j` in JVM, `hystrix-go`):

- **Closed:** normal calls go through.
- **Open:** after N consecutive failures, short-circuit calls for a cooldown period.
- **Half-open:** after cooldown, allow one test call.

Trip the breaker on **infrastructure** errors (6, 9001, 91, 189, 133 when chronic) — NOT on logical errors (121, 251, 292). Closing too aggressively on logical errors masks bugs.

### Pattern 3: Idempotency keys

Even with retryable writes, if you have business-critical writes and the driver lost connection during commit acknowledgment, you don't know if it landed.

- Generate a client-side UUID and store as an indexed unique field.
- If the retry fails with duplicate-key (code 11000), you know it already landed — treat as success.

```javascript
async function safeInsert(coll, doc) {
  const idempotencyKey = doc.idempotencyKey || crypto.randomUUID();
  try {
    await coll.insertOne({ ...doc, idempotencyKey });
  } catch (e) {
    if (e.code === 11000 && /idempotencyKey/.test(e.message)) {
      return; // Already landed
    }
    throw e;
  }
}
```

### Pattern 4: Bulkhead

Separate connection pools per workload (analytics vs. transactional) so a slow analytical aggregation doesn't starve transactional writes of connections. Most drivers expose `maxPoolSize` and `minPoolSize`; some support multiple `MongoClient` instances against the same cluster cheaply (Atlas Connection Pool sharing).

---

## Section 8: Atlas-specific operational errors

Atlas adds a layer of error surfaces beyond raw mongod codes. The most common:

### Atlas Flex (replaces M2/M5 and Serverless as of Jan 22, 2026)

- **500 concurrent connection limit** per Flex cluster. Hitting this surfaces as `MongoNetworkError` with the message `connection refused` or `connection limit exceeded` (custom Atlas message; not a mongod-native error code).
- **Fix:** Use connection pooling (singleton `MongoClient` — never per-request), tune `maxPoolSize` (default 100 in most drivers — drop to 20-50 in serverless/Lambda contexts), and use `maxIdleTimeMS` to age out idle connections.

### Atlas Serverless (migrated to Flex in 2026, but legacy clusters remain)

- **RPU exceeded:** Read Processing Units throttled when usage spikes. Surfaces as throttled response (HTTP 429 at the Data API layer, or operation slowness at the driver layer). Not a numeric code in the standard catalog.
- **Fix:** Migrate to Flex with provisioned capacity, or design workloads to smooth out read spikes (cache, batch reads).

### Connection storm patterns

When a serverless/Lambda function fan-outs aggressively, each cold start opens new connections, exceeding the cluster's `maxIncomingConnections`. Symptoms:

- `MongoNetworkError: connection X to ... closed`
- `connection pool destroyed`
- `MongoServerSelectionError: Server selection timed out`

Fixes:

1. **Reuse `MongoClient` across invocations** — store it outside the Lambda handler so the runtime keeps it warm.
2. **Use the Atlas Data API** for truly stateless workloads (no connection pool needed).
3. **Drop `maxPoolSize`** to a small value (5-10) in serverless to limit per-instance fan-out.
4. **Atlas Connection Pool stats**: monitor `connections.current` vs `connections.available`.

### Atlas pause/resume

A paused Atlas cluster returns:
- **HTTP 503** at the Atlas Admin API.
- **`MongoNetworkError`** at the driver layer (the cluster simply doesn't respond).
- No specific server-side error code (mongod isn't running).

---

## Section 9: Change stream errors beyond 286

Change streams have a specific error model:

- **Code 280 — ChangeStreamFatalError:** Stream cannot be resumed. Open a new one.
- **Code 286 — ChangeStreamHistoryLost:** Resume token outside oplog window. Reset token (see Section 1).
- **Code 40573 — `$changeStream` requires a replica set or sharded cluster:** Cannot run on standalone. Move workload to a replica set.

Drivers automatically resume on **resumable errors** (network, step-down, shutdown) using the last seen `_id` (resume token), but only **once**. Any error during the resume itself is fatal — the application must catch it and decide policy.

### Resilient change stream pattern

```javascript
async function watchWithRecovery(coll, pipeline, checkpoint) {
  while (true) {
    let resumeToken = await checkpoint.load();
    const stream = coll.watch(pipeline, { resumeAfter: resumeToken });
    try {
      for await (const change of stream) {
        await processChange(change);
        await checkpoint.save(change._id);
      }
    } catch (e) {
      if (e.code === 286) {
        // History lost — give up on stored token, restart from now
        await checkpoint.clear();
        continue;
      }
      // Other errors — fail loudly
      throw e;
    }
  }
}
```

---

## Section 10: Diagnostic workflow — what to do when you see an error

When triaging a MongoDB error in production:

1. **Capture the full error object**, not just the message. Drivers expose:
   - `error.code` (numeric)
   - `error.codeName` (human-readable)
   - `error.message`
   - `error.errorLabels` (array of labels — read this first)
   - `error.errInfo` (structured detail for validation/parse errors)
   - `error.writeErrors[]` (for bulk ops, per-op errors)
   - `error.result` (for bulk ops, full result with successes and failures)

2. **Match against this catalog.** If the code is in Section 1, you have a fix.

3. **Check error labels** before retry. A code without `RetryableWriteError` should not be retried by your code — it wasn't retried by the driver for a reason.

4. **Correlate with cluster state.** Atlas Activity Feed and mongod logs (`/var/log/mongodb/mongod.log` or Atlas log download) often explain the same incident from the server's perspective. Look for `closing socket`, `stepDown`, `shutDown`, `interrupted`, `WriteConflict`.

5. **For aggregations and slow queries**, run `explain('executionStats')` and look for:
   - `executionTimeMillis` (was the budget realistic?)
   - `totalKeysExamined` vs `totalDocsExamined` vs `nReturned` (the famous "scan ratio")
   - `stage: 'COLLSCAN'` (missing index)
   - `executionStages.allowDiskUse` (did it spill?)

6. **Reproduce with `mongosh`** if possible. If the error reproduces in mongosh from the same host, it's a cluster/data issue. If not, it's a driver/network/auth issue local to your app.

---

## Section 11: Driver-specific quirks

### Node.js driver

- `error.code` is the server code or, for client-side errors, a string like `'ETIMEOUT'`. Always check both.
- `MongoNetworkError`, `MongoServerSelectionError`, `MongoServerError` are the three main classes. Check with `instanceof`.

### Java driver

- `MongoCommandException` for server-returned errors (has `getErrorCode()`, `getErrorMessage()`, `getErrorLabels()`).
- `MongoSocketException`, `MongoTimeoutException` for transport-level errors.

### Go driver

- Use `mongo.IsDuplicateKeyError(err)`, `mongo.IsNetworkError(err)`, `mongo.IsTimeout(err)` helpers — don't string-match.
- For labels: `err.(mongo.ServerError).HasErrorLabel("RetryableWriteError")`.

### Python driver

- `pymongo.errors.OperationFailure` has `.code` and `.code_name`.
- Labels: `error.has_error_label('RetryableWriteError')`.

### C# / .NET driver

- `MongoCommandException` for server errors.
- `MongoConnectionException`, `MongoNotPrimaryException` for transport/topology.
- Labels: `ex.HasErrorLabel("RetryableWriteError")`.

### Rust driver

- `mongodb::error::Error` with `.kind` enum: `CommandError`, `BulkWriteError`, `WriteFailure`, etc.
- Labels: `error.contains_label("RetryableWriteError")`.
- Use `if let mongodb::error::ErrorKind::Command(command_error) = error.kind.as_ref()` to pattern-match server codes.

---

## Quick-reference table

| Code | Name | Retryable | Family |
| ---: | --- | --- | --- |
| 6 | HostUnreachable | Yes (driver) | Network |
| 7 | HostNotFound | Yes (driver) | Network |
| 18 | AuthenticationFailed | No | Auth |
| 24 | LockTimeout | No (app-level only) | Concurrency |
| 50 | MaxTimeMSExpired | No | Timeout |
| 64 | WriteConcernFailed | Yes (on commit) | Write concern |
| 89 | NetworkTimeout | Yes (driver) | Network |
| 91 | ShutdownInProgress | Yes (driver) | Lifecycle |
| 112 | WriteConflict | Yes (transaction) | Concurrency |
| 121 | DocumentValidationFailure | No | Validation |
| 133 | FailedToSatisfyReadPreference | Yes (driver) | Server selection |
| 134 | ReadConcernMajorityNotAvailableYet | Yes (driver) | Read concern |
| 148 | ReadConcernMajorityNotEnabled | No (config) | Read concern |
| 189 | PrimarySteppedDown | Yes (driver) | Lifecycle |
| 211 | KeyNotFound (HMAC) | Yes (driver) | Cluster time |
| 251 | NoSuchTransaction | Yes (whole txn) | Transaction |
| 262 | ExceededTimeLimit | Yes (driver) | Timeout |
| 280 | ChangeStreamFatalError | No | Change streams |
| 286 | ChangeStreamHistoryLost | No (reset token) | Change streams |
| 292 | QueryExceededMemoryLimitNoDiskUseAllowed | No | Aggregation |
| 8000 | AtlasError (auth/permission) | No | Atlas |
| 9001 | SocketException | Yes (driver) | Network |
| 10107 | NotWritablePrimary | Yes (driver) | Topology |
| 11000 | DuplicateKey | No (logical) | Uniqueness |
| 11600 | InterruptedAtShutdown | Yes (driver) | Lifecycle |
| 11602 | InterruptedDueToReplStateChange | Yes (driver) | Topology |
| 13435 | NotWritablePrimaryNoSecondaryOk | Yes (driver) | Topology |
| 13436 | NotPrimaryOrSecondary | Yes (driver) | Topology |
| 40415 | Unknown field | No | BSON / Schema |

---

## Sources

- [MongoDB Manual — Error Codes reference](https://www.mongodb.com/docs/manual/reference/error-codes/)
- [MongoDB Server `error_codes.yml` source of truth](https://github.com/mongodb/mongo/blob/master/src/mongo/base/error_codes.yml)
- [MongoDB Specifications — Retryable Writes](https://github.com/mongodb/specifications/blob/master/source/retryable-writes/retryable-writes.md)
- [MongoDB Specifications — Retryable Reads](https://github.com/mongodb/specifications/blob/master/source/retryable-reads/retryable-reads.md)
- [MongoDB Specifications — Transactions](https://github.com/mongodb/specifications/blob/master/source/transactions/transactions.md)
- [MongoDB Specifications — Client-Side Operations Timeout (CSOT)](https://github.com/mongodb/specifications/blob/master/source/client-side-operations-timeout/client-side-operations-timeout.md)
- [MongoDB Specifications — Change Streams](https://github.com/mongodb/specifications/blob/master/source/change-streams/change-streams.md)
- [MongoDB Manual — Retryable Writes](https://www.mongodb.com/docs/manual/core/retryable-writes/)
- [MongoDB Manual — Change Streams (v7.0)](https://www.mongodb.com/docs/v7.0/changestreams/)
- [Node.js Driver — Connection Options CSOT](https://www.mongodb.com/docs/drivers/node/current/connect/connection-options/csot/)
- [Java Sync Driver — CSOT](https://www.mongodb.com/docs/drivers/java/sync/current/connection/specify-connection-options/csot/)
- [Atlas Flex Clusters management](https://www.mongodb.com/docs/atlas/manage-serverless-instances/)
- [SERVER-35031 — ExceededTimeLimit overloaded code 50](https://jira.mongodb.org/browse/SERVER-35031)
- [DRIVERS-525 — Retryable writes label coverage](https://jira.mongodb.org/browse/DRIVERS-525)
