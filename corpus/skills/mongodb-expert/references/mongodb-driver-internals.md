<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-driver-internals` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-driver-internals
version: "1.1"
updated: "2026-05-29"
origin: local
category: mongodb
description: >
  MongoDB driver internals expert -- CMAP connection pooling (pool states, checkout algorithm,
  pool clear, monitoring events), SDAM topology state machine (server types, heartbeat protocols,
  streaming vs polling hello), server selection algorithm (latency window, operationCount load
  balancing, maxStalenessSeconds), retryable writes and reads with txnNumber deduplication,
  read/write concerns, causal consistency with afterClusterTime, sessions, sharded transaction
  coordinator with two-phase commit, Client Side Operations Timeout (CSOT timeoutMS),
  DNS SRV polling, TLS configuration, compression.
  TRIGGER: debugging connection pool exhaustion or WaitQueueTimeoutError, diagnosing
  MongoServerSelectionError, understanding retry behavior on elections, tracing
  TransientTransactionError or UnknownTransactionCommitResult labels, tuning timeoutMS
  (CSOT) vs legacy socketTimeoutMS/serverSelectionTimeoutMS, diagnosing DNS SRV resolution
  failures, configuring TLS or OCSP, understanding streaming hello vs polling heartbeat,
  explaining why operations fail during primary elections, or any driver-server protocol
  question backed by the mongodb/specifications repo.
  SKIP: driver API surface — CRUD methods, aggregation helpers, Mongoose/Spring ODM setup
  (use mongodb-developer); index design (use mongodb-indexes-deep); replication topology design
  (use mongodb-replication); Atlas platform administration (use mongodb-atlas-expert);
  Kubernetes-specific driver deployment patterns (use mongodb-drivers-k8s).
when_to_use:
  - Debugging connection pool exhaustion — WaitQueueTimeoutError, pool cleared events, maxPoolSize tuning
  - Diagnosing MongoServerSelectionError — topology Unknown, no suitable server, election failover
  - Understanding retryable write / retryable read mechanics — txnNumber, RetryableWriteError label
  - Tracing TransientTransactionError or UnknownTransactionCommitResult in transaction code
  - Tuning timeoutMS (CSOT) or understanding the legacy timeout option matrix
  - Diagnosing DNS SRV resolution failures with mongodb+srv:// URIs
  - Configuring TLS, OCSP, or mutual TLS (X.509 auth) at the driver level
  - Explaining the streaming hello protocol vs polling and their impact on election detection latency
  - Understanding causal consistency, afterClusterTime, and operationTime gossip
  - Choosing read preference modes and understanding latency window / operationCount load balancing
  - Explaining sharded transaction coordinator two-phase commit behavior
  - Understanding wire protocol compression (snappy, zstd, zlib negotiation)
when_not_to_use:
  - Driver API surface — CRUD methods, aggregation helpers, ODM setup (use mongodb-developer)
  - Index design, ESR rule, compound indexes (use mongodb-indexes-deep)
  - Replication topology design, election protocol, oplog internals (use mongodb-replication)
  - Atlas platform administration, cluster creation, Atlas CLI (use mongodb-atlas-expert)
  - Kubernetes-specific driver deployment patterns, sidecar patterns (use mongodb-drivers-k8s)
  - Application-level transaction patterns — withTransaction, session management in app code (use mongodb-transactions)
related_skills:
  - mongodb-developer
  - mongodb-error-codes
  - mongodb-transactions
  - mongodb-replication
  - mongodb-drivers-k8s
  - mongodb-performance-troubleshooting
  - mongodb-change-streams
---

# MongoDB Driver Internals

This skill covers the internal mechanics of MongoDB official drivers — the wire-level behavior, state machines, retry policies, timeouts, and protocols that customers actually hit during incidents. It complements `mongodb-developer` (which covers the driver API surface) and `mongodb-drivers-k8s` (which covers Kubernetes-specific deployment).

The content is sourced from the canonical [mongodb/specifications](https://github.com/mongodb/specifications) repository, which is the source of truth all official drivers implement against.

## When to use this skill

Use this skill when:

- Debugging **connection pool exhaustion** (`waitQueueTimeoutMS` exceeded, `MongoServerSelectionError: no available servers`, pool `PoolClearedEvent` storms)
- Diagnosing **failover behavior** on the driver side — what happens during an election, how SDAM detects topology changes, when retryable writes save the operation vs surface to the user
- Understanding **retry semantics** — what makes a write retryable, which errors carry the `RetryableWriteError` label, how `txnNumber` deduplicates
- Tracing **transaction failures** — `TransientTransactionError` and `UnknownTransactionCommitResult` labels, sharded transaction coordinator behavior, two-phase commit between coordinator and participant shards
- Understanding **causal consistency** — when `afterClusterTime` is sent, why `readConcern: majority` + `writeConcern: majority` is the only fully durable combination
- Tuning **timeouts** — `timeoutMS` (CSOT, unified) vs the legacy `socketTimeoutMS` / `connectTimeoutMS` / `serverSelectionTimeoutMS` / `waitQueueTimeoutMS` / `wTimeoutMS` / `maxTimeMS` matrix
- Diagnosing **DNS SRV** issues — `mongodb+srv://` resolution, SRV polling for sharded clusters, `srvMaxHosts`, TXT-record options
- Reviewing **TLS** configuration — `tlsCAFile`, `tlsCertificateKeyFile`, `tlsAllowInvalidCertificates` (anti-pattern), Atlas implicit TLS
- Explaining the **streaming `hello` protocol** vs legacy polling, FaaS-specific tuning (Lambda / Cloud Run), `heartbeatFrequencyMS`
- Choosing a **read preference** correctly — when `secondary` is wrong, why `secondaryPreferred` falls back to primary on tag-set miss but `secondary` errors, `localThresholdMS` latency window
- Differentiating **maxStalenessSeconds vs localThresholdMS vs hedged reads** vs operationCount load balancing for server selection

Skip this skill for: pure aggregation pipeline syntax (`mongodb-aggregation-pipeline`), index design (`mongodb-indexes-deep`), replication topology design (`mongodb-replication`), Atlas platform admin (`mongodb-atlas-expert`), or driver API reference (`mongodb-developer`).

## See also

- `mongodb-developer` — driver API surface (Node, Python, Java, Go, C#, etc.), mongosh, Atlas CLI
- `mongodb-error-codes` — full error-code reference, retry-safe codes
- `mongodb-transactions` — application-level transaction patterns
- `mongodb-replication` — replica set topology, election protocols, write concern interaction
- `mongodb-drivers-k8s` — K8s-specific deployment patterns
- `mongodb-performance-troubleshooting` — slow query / connection issues with broader scope
- `mongodb-change-streams` — change stream resumability (uses same retryable read semantics)

## 1. Connection Monitoring and Pooling (CMAP)

The [CMAP specification](https://github.com/mongodb/specifications/blob/master/source/connection-monitoring-and-pooling/connection-monitoring-and-pooling.md) defines how drivers manage a pool of connections to each server in the topology. Every MongoDB official driver implements this state machine identically.

### 1.1 Pool states

A connection pool transitions through three states:

| State | Meaning |
|-------|---------|
| **paused** | Initial state after creation, or after a `clear()` operation. Prevents checkouts and background population until marked ready. |
| **ready** | Healthy operational state — checkouts succeed, background fill respects `minPoolSize`. |
| **closed** | Terminal state. All future operations fail. Pool was deliberately closed (e.g. `MongoClient.close()`). |

The pool starts **paused**. When SDAM marks the corresponding server as known and reachable, the monitor calls `pool.ready()`. On any network error from a non-streaming operation, the pool clears and returns to **paused** until the monitor confirms the server is reachable again.

### 1.2 Pool configuration

| Option | Default | Purpose |
|--------|---------|---------|
| `maxPoolSize` | **100** | Maximum total connections per server (0 = unlimited). Includes both available and in-use. |
| `minPoolSize` | **0** | Minimum connections to maintain via background population. |
| `maxIdleTimeMS` | **0** (unlimited) | Connection idle timeout before being closed as stale. |
| `maxConnecting` | **2** | Max concurrent connection establishments in flight (prevents thundering herd on cold start / pool clear). |
| `waitQueueTimeoutMS` | **0** (unlimited) | Max time to wait for a connection slot. Deprecated in favor of `timeoutMS` (CSOT). |

`maxPoolSize=100` is per-server in the topology, not global. A 3-node replica set with default settings has up to 300 connections from the client (though the client only uses connections to its currently-selected server for any given operation).

### 1.3 Connection states

Each connection inside the pool has its own state:

- **pending** — Created but TCP/TLS/auth handshake not yet complete.
- **available** — In pool, idle, ready to check out.
- **in use** — Checked out by an operation; not in pool.
- **closed** — Socket closed (perished). Cannot be reused.

### 1.4 Checkout algorithm

The exact algorithm (paraphrased from the spec):

```
ConnectionCheckOut(pool):
  emit ConnectionCheckOutStartedEvent
  enter wait queue (timeout = waitQueueTimeoutMS or timeoutMS-remaining)
  await front of wait queue

  loop:
    if pool.state == "closed":
      emit ConnectionCheckOutFailedEvent(reason="poolClosed")
      return error PoolClosedError

    if pool.state == "paused":
      emit ConnectionCheckOutFailedEvent(reason="connectionError")
      return error PoolClearedError(retryable=true)

    # search available connections for a non-perished one
    for conn in availableConnections:
      if conn.perished():
        close conn (reason="stale" or "idle")
      else:
        mark conn "in use"
        emit ConnectionCheckedOutEvent
        return conn

    # no available connection — try to create one
    if (totalConnectionCount < maxPoolSize)
       and (pendingConnectionCount < maxConnecting):
      conn = create pending connection
      establish synchronously (handshake)
      mark "in use"
      emit ConnectionCheckedOutEvent
      return conn

    # blocked — wait for slot or timeout
    await (connection available OR maxConnecting slot OR timeout)
    if timeout:
      emit ConnectionCheckOutFailedEvent(reason="timeout")
      return WaitQueueTimeoutError
```

A connection is **perished** if:
- Its socket has errored (e.g. EPIPE, RST detected).
- It exceeded `maxIdleTimeMS` since last use.
- Its `generation` is less than the pool's current `generation` (i.e. the pool was cleared after this connection was created).

### 1.5 Check-in (return) behavior

When an operation completes:

1. Driver emits `ConnectionCheckedInEvent`.
2. If the connection is perished OR pool is closed → close it (do not return to pool).
3. Otherwise → mark as available, decrement `inUseConnections`, increment `availableConnections`.

### 1.6 Pool clear

A pool clear is triggered when SDAM marks the server as Unknown (network error from a non-monitor operation, election, ShutdownInProgress, etc.). The clear semantics differ between standard and load-balanced topologies:

**Standard (non-load-balanced):**
1. Increment pool `generation` — every existing connection becomes stale on next checkout/return.
2. Transition pool state to `paused`.
3. Cancel all waiting checkouts with a retryable `PoolClearedError`.
4. If `interruptInUseConnections=true` was passed (used for network-timeout-triggered clears in MongoDB 4.4+): forcibly close in-use connections too. Otherwise, they stay open until check-in.
5. Emit `PoolClearedEvent`.

**Load-balanced:**
- Clear increments a *per-serviceId* generation, not the global pool generation. Pool does **not** pause. This is necessary because in load-balanced mode the driver cannot distinguish individual backends.

### 1.7 Pool monitoring events

Drivers must expose subscribable events for observability. Example (Node.js):

```javascript
client.on('connectionPoolCreated', e => console.log('pool created', e.address));
client.on('connectionPoolReady',   e => console.log('pool ready',   e.address));
client.on('connectionPoolCleared', e => console.log('pool cleared', e.address, e.serviceId));
client.on('connectionCheckOutFailed', e => console.warn('checkout failed', e.address, e.reason));
client.on('connectionCheckedOut',   e => metrics.gauge('mongo.pool.inUse', +1, { addr: e.address }));
client.on('connectionCheckedIn',    e => metrics.gauge('mongo.pool.inUse', -1, { addr: e.address }));
```

Python equivalent uses `pymongo.monitoring.register(PoolListener())`; Java uses `MongoClientSettings.builder().applyToConnectionPoolSettings(b -> b.addConnectionPoolListener(...))`.

Full event list:

| Event | When emitted |
|-------|--------------|
| `PoolCreatedEvent` | Pool instantiated |
| `PoolReadyEvent` | Pool transitioned to ready |
| `PoolClearedEvent` | Generation incremented, state paused |
| `PoolClosedEvent` | Pool marked closed |
| `ConnectionCreatedEvent` | Connection object created (before handshake) |
| `ConnectionReadyEvent` | TCP + TLS + MongoDB handshake + auth complete |
| `ConnectionClosedEvent` | Connection closed (carries reason: stale/idle/error/poolClosed) |
| `ConnectionCheckOutStartedEvent` | Checkout attempt begins |
| `ConnectionCheckOutFailedEvent` | Checkout failed (reason: timeout/connectionError/poolClosed) |
| `ConnectionCheckedOutEvent` | Connection successfully obtained |
| `ConnectionCheckedInEvent` | Connection returned to pool |

Drivers also emit debug-level log messages with `serverHost`, `serverPort`, `connectionId`, `duration`, and event-specific fields. These show up in driver logs (Node.js `MongoClient.on('connectionPoolEvent', ...)`, Python `monitoring.register`, Java `addConnectionPoolListener`).

### 1.8 Diagnosing pool issues

**Symptom: `MongoServerSelectionError: connection pool cleared because another operation failed`**
- A network error from another operation caused a pool clear. This is propagated to in-flight checkout attempts as a retryable error. If retryable writes/reads are on, the next attempt usually succeeds — if the customer sees this as a *final* error, retries are disabled or the underlying server is genuinely unreachable.

**Symptom: `MongoTimeoutError: Timed out while checking out a connection from connection pool`**
- All connections are in use, and `maxPoolSize` has been reached. New checkouts are queued and exhausted `waitQueueTimeoutMS` (or `timeoutMS` if CSOT is on).
- Causes: (1) app concurrency exceeds `maxPoolSize`, (2) operations holding connections for too long (long-running aggregations, blocked transactions), (3) replica set primary stepped down and the pool drained but new connections to the new primary haven't finished handshaking.
- Fix: Raise `maxPoolSize`, shorten operations, ensure `maxConnecting` is high enough for parallel handshakes on cold-start.

**Symptom: Steady-state CPU on app server, pool stays near `maxPoolSize`**
- Application concurrency exceeds pool capacity. The wait queue is doing its job, but app latency is dominated by checkout wait. Tune `maxPoolSize` upward (each connection consumes ~1MB of RAM and a server-side socket).

## 2. Server Discovery and Monitoring (SDAM)

SDAM is the topology state machine. The driver maintains an in-memory `TopologyDescription` representing its view of the cluster.

### 2.1 Topology types

| Topology type | Description |
|---------------|-------------|
| **Unknown** | Initial state, or all servers marked Unknown. |
| **Single** | Direct connection to one server (`directConnection=true` in URI). Stays Single permanently. |
| **ReplicaSetNoPrimary** | Replica set confirmed but no primary currently known. |
| **ReplicaSetWithPrimary** | Replica set with identified primary. |
| **Sharded** | One or more mongos servers. |
| **LoadBalanced** | Connection through a load balancer (Atlas Serverless / shared tiers). |

### 2.1.1 `directConnection=true`

When the URI sets `directConnection=true` (or the legacy `connect=direct`), the driver skips topology discovery entirely. Topology is forced to **Single**, and all operations route to the single seed-list host regardless of its `hello` response. This is useful for:

- Targeting a specific replica set member (e.g., a secondary for an admin task).
- Talking to a standalone mongod where SDAM discovery would be unnecessary.

It is **incorrect** for production replica set / sharded cluster connections — a `directConnection` URI to a primary will never re-discover the new primary after a step-down. Customers occasionally set this accidentally when copying URIs from mongosh examples.

### 2.2 Server types

Each server has a `ServerType`:
- `Standalone` — single mongod
- `Mongos` — mongos router
- `RSPrimary` — replica set primary
- `RSSecondary` — replica set secondary
- `RSArbiter` — replica set arbiter (no data)
- `RSOther` — recovering / startup / removed
- `RSGhost` — replica set member responding before fully initialized
- `PossiblePrimary` — single-threaded driver heuristic
- `LoadBalancer` — load balancer endpoint
- `Unknown` — initial or after error

### 2.3 Heartbeat protocols

Drivers monitor every server using one of two protocols, governed by `serverMonitoringMode`:

**Polling protocol (MongoDB < 4.4 servers, or `serverMonitoringMode=poll`):**
- Send `hello` (or legacy `isMaster`) command.
- Process response, update topology.
- Sleep for `heartbeatFrequencyMS` (default **10s** multi-threaded, **60s** single-threaded; minimum **500ms**).
- Repeat.

**Streaming protocol (MongoDB 4.4+ servers, `serverMonitoringMode=stream` or `auto`):**
- Send `hello` with `topologyVersion` and `maxAwaitTimeMS` set.
- Server holds the connection open and pushes a response when topology changes or `maxAwaitTimeMS` elapses.
- Driver immediately re-sends without waiting.
- Result: topology changes detected in tens of milliseconds, not seconds.

The streaming protocol uses **two dedicated connections** per server: one streaming connection for topology updates, one RTT connection for round-trip-time measurement every `heartbeatFrequencyMS`.

`serverMonitoringMode=auto` (default) chooses based on environment: polling on FaaS platforms, streaming elsewhere. The spec defines FaaS detection via well-known environment variables — `AWS_LAMBDA_FUNCTION_NAME` (AWS Lambda), `FUNCTIONS_WORKER_RUNTIME` (Azure Functions), `K_SERVICE` (Google Cloud Functions / Cloud Run), and `VERCEL`. FaaS environments accumulate stale topology data during suspension/resume cycles; polling avoids this by issuing discrete checks on each invocation.

### 2.4 RTT measurement

For server selection, the driver tracks per-server RTT:
- Driver maintains the minimum RTT of the (at most) last 10 samples.
- Reports `minRTT = 0` until at least 2 samples have been gathered (cold-start protection).
- RTT is measured on the dedicated RTT connection (streaming protocol) or on the monitoring socket (polling).

### 2.5 SDAM error handling

When a server check fails or an application operation hits a network error from a previously-known server:

1. Mark server as `Unknown` in topology.
2. Clear connection pool for that server (with `interruptInUseConnections=true` for network timeouts).
3. **Do not sleep** — immediately retry the monitoring check (network errors get one retry without waiting).
4. If the retry fails too, fall back to the normal `heartbeatFrequencyMS` cadence.
5. Emit `ServerHeartbeatFailedEvent` and `TopologyDescriptionChangedEvent`.

### 2.6 Topology state transitions

The SDAM spec includes a full state-transition table. Key transitions:

- Topology=Unknown, response is Mongos → Topology=Sharded.
- Topology=Unknown, response is RSPrimary → Topology=ReplicaSetWithPrimary; `updateRSFromPrimary` (compare election id, set version; remove unknown hosts; add new hosts; rebuild monitors).
- Topology=ReplicaSetWithPrimary, primary response is now RSSecondary → demote: Topology=ReplicaSetNoPrimary, mark primary Unknown.
- Topology=Single → never changes (single-host direct connection).

### 2.7 Diagnosing SDAM issues

**Symptom: `MongoServerSelectionError: getaddrinfo ENOTFOUND` repeatedly**
- DNS resolution failing. For SRV URIs check `_mongodb._tcp.{host}` records; for standard URIs each hostname. SRV polling will retry every `rescanSRVIntervalMS` (default 60s).

**Symptom: After failover, operations error for 5–10 seconds before recovering**
- This is SDAM detecting the topology change. With streaming protocol, detection is sub-second; with polling at 10s `heartbeatFrequencyMS`, average ~5s. Retryable writes paper over this with one automatic retry, but only after the first attempt fails.
- If customer sees minutes of errors: their driver is too old to support streaming, or `serverSelectionTimeoutMS` is too short (default 30s should cover any normal election).

## 3. Server selection algorithm

After SDAM gives the driver a `TopologyDescription`, server selection picks one server for the operation.

### 3.1 Read preference modes

| Mode | Behavior |
|------|----------|
| **primary** (default) | Read from primary only. Error if no primary. |
| **primaryPreferred** | Primary if available, else secondaries (filtered by tag/staleness). |
| **secondary** | Secondaries only. Error if none eligible. **Never falls back to primary.** |
| **secondaryPreferred** | Secondaries if eligible, else primary (graceful fallback). |
| **nearest** | Any member (primary or secondary) within `localThresholdMS` of fastest. |

**Common antipattern:** Using `secondary` to "offload" reads from the primary. This is almost always wrong because:
1. Secondaries are stale (async replication).
2. If `maxStalenessSeconds` is not set, the secondary may be arbitrarily lagged.
3. During a step-down, all reads error until a new primary is elected (`secondary` does not fall back).

Prefer `secondaryPreferred` with `maxStalenessSeconds: 120` for analytics workloads.

### 3.2 Server selection algorithm

The multi-threaded algorithm:

```
SelectServer(topology, readPreference, operationTimeout):
  start_time = now()
  while now() - start_time < serverSelectionTimeoutMS:
    if topology.compatibilityError: return error  # wire version mismatch
    suitable = findSuitableServersByTopologyType(topology, readPreference)
    if suitable is empty:
      request immediate SDAM update (wake monitors)
      wait (capped at heartbeatFrequencyMS)
      continue
    suitable = applyCustomSelectors(suitable)
    suitable = filterByLatencyWindow(suitable, localThresholdMS)
    selected = selectByOperationCount(suitable)  # not pure random
    return selected
  return MongoServerSelectionError("Server selection timeout")
```

### 3.3 Latency window (`localThresholdMS`)

Default: **15 ms**.

After filtering by topology+read preference, suitable servers are filtered to those whose `minRTT <= fastestServerMinRTT + localThresholdMS`. So if the fastest server has 5ms RTT and `localThresholdMS=15`, all servers with RTT ≤ 20ms are eligible.

Tune for geo-distributed clusters: a cross-region cluster needs `localThresholdMS` raised to include multi-region replicas, otherwise `nearest` mode collapses to the single closest server.

### 3.4 Operation count load balancing (drivers ≥ 2022)

Within the latency window, the driver picks the server with the lower in-flight operation count using a "power of two choices" strategy: pick two servers at random, choose the one with fewer outstanding operations. This is provably better than pure random under uneven load (e.g. when one secondary is doing heavier work like an index rebuild).

### 3.5 `maxStalenessSeconds`

Filters secondaries by replication lag.

- Comparison rule: if primary exists, lag = primary's last write - secondary's last write.
- If no primary, lag = freshest secondary's last write - this secondary's last write.
- `maxStalenessSeconds <= 0` → no filtering (default).
- Spec minimum: must be ≥ 90 seconds when set (server constraint).

If a secondary exceeds `maxStalenessSeconds`, it is removed from suitable set. For `secondary` mode this may produce an error; for `secondaryPreferred` it may fall back to primary.

### 3.6 Hedged reads (sharded clusters, deprecated 8.0)

For sharded `nearest` reads on mongos, hedged reads sent the same query to two replicas and used whichever returned first. Deprecated in MongoDB 8.0 due to load amplification — replaced by mongos's overload-aware selection when secondaries are under load.

### 3.7 `serverSelectionTimeoutMS`

Default: **30000 ms** (30s).

This timeout covers the entire selection loop. It must be long enough to absorb a normal primary election (~10–20s typically). Customers who set this too low (e.g. 1s) see spurious `MongoServerSelectionError` during routine elections, then mistakenly conclude the cluster is unhealthy.

## 4. Retryable writes

### 4.1 Mechanism

For supported write operations with retryable writes enabled (`retryWrites` URI default became `true` in driver 4.2+; the feature itself requires MongoDB server 3.6+ replica set / sharded cluster):

1. Driver acquires a `ClientSession` (implicit if not provided).
2. Driver assigns a `txnNumber` — monotonically increasing 64-bit int, unique within the session.
3. Driver sends the write command with `lsid` (session ID) + `txnNumber`.
4. Server records `(lsid, txnNumber)` → write result in `config.transactions`.
5. On a retryable error, driver sends the **same command** with the **same `(lsid, txnNumber)`**.
6. Server sees the duplicate, returns the original result — at-most-once semantics.

This is fundamentally different from naive client-side retry: the server-side dedup ensures the write is applied exactly once, even if the network ate the original ack.

### 4.2 Supported operations

**Single-statement:**
- `insertOne`, `updateOne`, `replaceOne`, `deleteOne`
- `findOneAndUpdate`, `findOneAndReplace`, `findOneAndDelete`

**Multi-statement (must be ordered+homogeneous):**
- `insertMany`
- `bulkWrite` (only if it contains no `updateMany` or `deleteMany` ops)

**Not retryable:**
- `updateMany`, `deleteMany` (multi-document updates can't be safely deduped)
- Aggregation with `$out` or `$merge`
- Operations with `writeConcern: {w: 0}` (no ack, no retry possible)
- Operations inside a transaction (transaction itself has different retry semantics)
- Generic `runCommand` for non-CRUD commands

### 4.3 Retryable errors

For MongoDB 4.4+ servers, the server attaches the `RetryableWriteError` label to errors that should trigger retry. The driver retries any error carrying that label.

For pre-4.4 servers (which don't emit the label), the driver itself adds `RetryableWriteError` to the error before deciding whether to retry, based on hard-coded error codes:
- `NotWritablePrimary` (10107)
- `NotPrimaryNoSecondaryOk` (13435)
- `NotPrimaryOrSecondary` (13436)
- `InterruptedAtShutdown` (11600)
- `InterruptedDueToReplStateChange` (11602)
- `PrimarySteppedDown` (189)
- `ShutdownInProgress` (91)
- `HostNotFound` (7)
- `HostUnreachable` (6)
- `NetworkTimeout` (89)
- `SocketException` (9001)
- `ExceededTimeLimit` (262)

Plus any network exception during the write attempt.

### 4.4 Retry count

By default, **one retry** per operation. With CSOT (`timeoutMS`) enabled, the driver retries as many times as the budget allows.

### 4.5 Requirements

- Server must be MongoDB 3.6+ (`maxWireVersion >= 6`).
- Topology must be replica set or sharded (not standalone — standalone has no oplog, no `config.transactions`).
- Server must report `logicalSessionTimeoutMinutes` in its hello response.
- Driver must support sessions.

### 4.6 Error-handling example

When a write fails after the driver's automatic retry, the application sees the final error. Inspect the error labels to distinguish retry-eligible failures from terminal ones:

```javascript
try {
  await collection.updateOne({ _id }, { $set: { processed: true } });
} catch (err) {
  if (err.hasErrorLabel && err.hasErrorLabel('RetryableWriteError')) {
    // The driver already retried once and it still failed.
    // The write may or may not have been applied; if idempotent, safe to retry again.
    log.warn({ err }, 'retryable write exhausted retries');
  } else if (err.code === 11000) {
    // Duplicate key — possibly a retry-after-success situation; usually safe to ignore
    // if the upstream operation is idempotent on _id.
    log.debug({ err }, 'duplicate key, likely retry-after-success');
  } else {
    throw err;
  }
}
```

Python:
```python
from pymongo.errors import OperationFailure
try:
    coll.update_one({"_id": _id}, {"$set": {"processed": True}})
except OperationFailure as exc:
    if exc.has_error_label("RetryableWriteError"):
        log.warning("retryable write exhausted retries: %s", exc)
    else:
        raise
```

### 4.7 The `retryWrites=false` antipattern

Customers occasionally disable retryable writes because:
- They saw a duplicate-key error during a retry (which is correct — the write was applied, the retry hit the duplicate).
- They want "predictable" behavior.

This is almost always wrong. Disabling retryable writes converts every primary step-down into application-visible errors. The correct fix for duplicate-on-retry is to handle `E11000` idempotently in app code, not to disable the safety net.

## 5. Retryable reads

Symmetric to retryable writes, but for reads. Default `retryReads=true`.

### 5.1 Supported operations

- CRUD reads: `find`, `aggregate` (no `$out`/`$merge`), `distinct`, `count`, `estimatedDocumentCount`, `countDocuments`, `findOne`
- Change streams: `MongoClient.watch`, `Database.watch`, `Collection.watch` (initial creation only — `getMore` is not retryable, but change streams have their own resume-token-based recovery)
- Enumeration: `listDatabases`, `listCollections`, `listIndexes`

**Not retryable:**
- `mapReduce` (deprecated anyway)
- `Cursor.getMore` (cursor state is server-side, can't be safely resumed)
- Generic `runCommand`
- Reads inside a transaction

### 5.2 Why `getMore` is not retryable

A cursor is server-side state. If the original server is gone, the cursor is gone — the driver cannot resume mid-iteration. This is why long-running iterations through large result sets are fragile.

Mitigations:
- Smaller batches via `batchSize` — minimizes work lost on cursor death.
- Process and persist offset (e.g. `_id` watermark) so the app can restart from there on cursor errors.
- For change streams: use the resume token (built-in mechanism).

### 5.3 Retry count

Default: **one retry**, same as writes. With CSOT, retries continue until timeout budget expires.

## 6. Read and write concerns

### 6.1 Write concern (`w`, `j`, `wtimeoutMS`)

| Setting | Meaning |
|---------|---------|
| `w: 0` | No acknowledgment. Fire and forget. No retry possible. |
| `w: 1` | Primary ack only (default for older deployments). |
| `w: "majority"` | Acks from majority of voting members (default for Atlas / modern deployments). |
| `w: N` (int ≥ 1) | Acks from N members. Avoid except in advanced scenarios. |
| `w: "tag"` | Acks from members matching custom replica set tags. |
| `j: true` | Wait for journal sync (fsync of WiredTiger journal). |
| `j: false` | No journal wait (just memory). |
| `wtimeoutMS: N` | Reject the write with WriteConcernTimeout after N ms. Server-side timeout. Deprecated for CSOT `timeoutMS`. |

**Critical**: `wtimeoutMS` does **not** cancel the write. The write may still be applied; the client just gets a `WriteConcernTimeout` error. This is a frequent source of "the data is there but the API returned an error" confusion.

**`w: "majority"` and `j: true`**: With `j: true`, "majority" means majority of journaled writes. This is the strongest durability guarantee — survives full cluster restart.

### 6.2 Read concern levels

| Level | Meaning | When applicable |
|-------|---------|-----------------|
| `local` | Reads from the node's local state, no majority requirement. **Default**. | All MongoDB versions. |
| `available` | Like local but allows orphaned-doc reads in sharded clusters (cheaper). | All versions. Sharded clusters only matter. |
| `majority` | Reads from the majority commit point — data guaranteed durable. | 3.2+. Required for causal consistency + durability. |
| `linearizable` | Strongest consistency. Reads block until concurrent majority writes complete. **Primary only.** | 3.4+. Very high latency, rarely used. |
| `snapshot` | Point-in-time read at a specific `atClusterTime`. | 5.0+ for non-transaction reads. Required inside transactions for snapshot isolation. |

**Important nuance**: `readConcern: {}` is **not** the same as `readConcern: {level: "local"}`. Empty means "use server default"; explicit `local` overrides any default. This matters in Atlas where the default may differ.

### 6.3 Read concern + replica set member

- `local` on a secondary may return data that gets rolled back after a primary failover.
- `majority` on a secondary returns data guaranteed durable cluster-wide.
- `linearizable` only works on primary.
- `snapshot` works on any member that has the relevant `atClusterTime` available.

### 6.4 Sharded write concern semantics

When a write hits multiple shards and any subset fails its write concern, mongos returns a composite error with code `WriteConcernTimeout` and per-shard breakdowns. The successful shards have already committed — there is no global rollback.

## 7. Causal consistency

### 7.1 Definitions

Causal consistency guarantees:
1. **Read your own writes** — within the session.
2. **Monotonic reads** — successive reads never see older data than earlier reads.
3. **Monotonic writes** — writes within the session preserve order.
4. **Writes follow reads** — a write executes after the writes that produced the data we read.

### 7.2 Mechanism

A `ClientSession` with `causalConsistency: true` (default for explicit sessions):

1. After every operation, the driver records the `operationTime` from the server response.
2. The driver also gossips `$clusterTime` to every server, providing a signed cluster-wide logical clock.
3. On the **next read** in this session, the driver sends `readConcern: {afterClusterTime: <session.operationTime>}`.
4. The server waits until its local state includes that cluster time before reading.

If you write to the primary, then read from a secondary with the same causally-consistent session, the secondary will block until it has replicated up to your write's `operationTime` — and then read.

### 7.3 The durability combination matrix

Only **one** combination provides all four causal-consistency guarantees with full durability:

| Read concern | Write concern | All 4 guarantees | Durable across partitions |
|--------------|---------------|------------------|---------------------------|
| `majority` | `majority` | yes | yes |
| `majority` | `w: 1` | yes | no — primary writes can roll back |
| `local` | `majority` | only monotonic writes | yes for writes only |
| `local` | `w: 1` | none guaranteed | no |

For production systems where causal consistency matters, only `readConcern: majority` + `writeConcern: majority` is correct.

### 7.4 `$clusterTime` gossip security

Drivers send the highest observed `$clusterTime` on every command. The cluster time carries an HMAC signature; the server validates it. This prevents a malicious client from forwarding an absurdly high `$clusterTime` to cause the cluster to wait forever.

### 7.5 Unacknowledged writes are not causally consistent

`writeConcern: {w: 0}` writes don't return an `operationTime`, so the driver can't add them to the session's logical clock. A read after such a write in the same session may or may not see the write.

## 8. Sessions

### 8.1 Implicit vs explicit

**Implicit sessions** are created automatically by the driver for any operation that doesn't pass one explicitly. They exist to ensure every command has an `lsid` for monitoring and retryable writes.

**Explicit sessions** are created via `client.startSession()`. Required for:
- Multi-document transactions.
- Causal consistency.
- Snapshot reads outside transactions.

### 8.2 Session ID

The `lsid` is a document `{id: UUID}`. Drivers generate the UUID locally (no server roundtrip) using RFC 4122 v4 UUIDs in BSON binary subtype 4.

### 8.3 Server session pool

The `MongoClient` maintains a pool of `ServerSession` objects. When acquiring:
1. Check pool for sessions with ≥1 minute before expiration.
2. Discard expired or "dirty" (network-error-tainted) sessions.
3. If pool empty, create new.

When returning:
1. Discard if expired or dirty.
2. Otherwise return to pool.

### 8.4 `logicalSessionTimeoutMinutes`

Server-side setting (default 30 minutes). Reported in `hello` response. Sessions unused longer than this are discarded server-side. If your app keeps a long-lived `ClientSession` and runs no operation in it for 30+ minutes, the next operation will fail with `NoSuchSession`.

### 8.5 Session affinity

In sharded transactions, the session is **pinned** to a specific mongos after the first read. All subsequent operations and the commit must go through the same mongos.

### 8.6 `endSessions` command

When `ClientSession.endSession()` is called (or the session pool returns to its limit), the driver buffers the session ID and eventually batches an `endSessions` command to the server, freeing server resources earlier than the 30-minute timeout.

## 9. Multi-document transactions

### 9.1 API

```javascript
const session = client.startSession();
try {
  await session.withTransaction(async () => {
    await coll.insertOne({...}, { session });
    await coll.updateOne({...}, {...}, { session });
  }, {
    readConcern: { level: 'snapshot' },
    writeConcern: { w: 'majority' },
    readPreference: 'primary',
  });
} finally {
  await session.endSession();
}
```

`withTransaction` is the **callback API** and is strongly recommended over the core API. It handles `TransientTransactionError` and `UnknownTransactionCommitResult` retry automatically.

### 9.2 Transaction states

A `ClientSession` cycles through:

```
no transaction → starting → in progress → committed → no transaction
                                       \→ aborted   → no transaction
```

Each `startTransaction` increments the session's `txnNumber`.

### 9.3 Error labels

| Label | Meaning | Recommended action |
|-------|---------|--------------------|
| `TransientTransactionError` | Transient failure inside transaction (network blip, write conflict, election). Transaction aborted server-side. | Retry the entire transaction (start over). |
| `UnknownTransactionCommitResult` | `commitTransaction` failed but we don't know if it committed (server selection / network / write concern error during commit). | Retry the commit (server will return the committed/aborted result deterministically). |

### 9.4 commitTransaction retry semantics

The driver MUST retry `commitTransaction` exactly once on a retryable error, regardless of `retryWrites` setting. On the retry, the write concern is upgraded to `w: majority` with `wtimeoutMS: 10000` to prevent split-brain commits during a failover.

### 9.5 abortTransaction error handling

Drivers MUST NOT propagate errors from `abortTransaction`. The transaction will time out and abort server-side anyway after `transactionLifetimeLimitSeconds`.

### 9.6 Lifetimes and timeouts

| Setting | Default | Scope |
|---------|---------|-------|
| `transactionLifetimeLimitSeconds` | **60** | Server-side (mongod). Max wall-clock time a transaction can be open. |
| `maxTransactionLockRequestTimeoutMillis` | **5** | Server-side. Max time an op inside a transaction waits for a lock before failing. |
| `maxCommitTimeMS` | unset | Client-side. Server-side timeout for the commit phase only. Deprecated for `timeoutMS`. |
| `timeoutMS` | unset | Client-side unified timeout (CSOT). Covers entire `withTransaction` block including retries. |

The `maxTransactionLockRequestTimeoutMillis=5` is the source of many "Unable to acquire lock" transient errors under contention — but those errors are correctly labeled `TransientTransactionError` so `withTransaction` retries them.

### 9.7 Restrictions inside transactions

- No `listCollections`, `listIndexes`, `count` (use aggregation instead).
- No writes to capped collections.
- No `killCursors` as first op.
- Cross-shard writes can't implicitly create collections (pre-create them).
- All operations must use primary read preference (snapshot reads inside transactions still hit primary).
- Operations within a transaction are NOT retryable on their own — they rely on `TransientTransactionError` retry of the whole transaction.

### 9.8 Sharded transaction coordinator

For multi-shard transactions, MongoDB uses a two-phase commit (2PC) protocol with a designated coordinator shard:

**Setup phase:**
1. First operation in the transaction picks a coordinator: the primary of the first shard touched.
2. The session is pinned to the mongos that selected the coordinator.
3. As more shards are touched, each is enrolled as a participant.

**Commit phase (when application calls `commitTransaction`):**
1. mongos sends `coordinateCommitTransaction` to the coordinator with the participant shard list.
2. Coordinator persists a coordinator record in `config.transaction_coordinators` (durable, survives crashes).
3. **Prepare phase**: coordinator sends `prepareTransaction` to all participants. Each participant locks the docs, writes a prepare entry to its oplog, ensures it can commit, replies with prepare timestamp.
4. Coordinator collects all prepare timestamps, picks the maximum as the commit timestamp.
5. Coordinator writes a "commit decision" durably.
6. **Commit phase**: coordinator sends `commitTransaction` with commit timestamp to all participants. They apply and release locks.
7. Coordinator cleans up its record.

**Failure handling:**
- If coordinator fails between prepare and commit decision: a new coordinator (next primary after failover) reads the durable record, completes the protocol.
- The `recoveryToken` returned by mongos lets the driver retry commit through a different mongos — useful when a mongos crashes mid-commit. The driver MUST include `recoveryToken` in `commitTransaction` retries.

**Practical limits:**
- Transactions touching many shards have high latency (prepare + commit phases each cross the network).
- Limit: avoid transactions touching more than 2–3 shards if latency matters.
- Lock conflicts across shards can cascade.

### 9.9 Diagnosing transaction issues

**`TransactionTooLargeForCache` (MongoDB 6.2+):**
- Transaction's total dirty data exceeds 5% of the WiredTiger cache.
- Not retried automatically. Reduce transaction size.

**`WriteConflict` inside a transaction:**
- Two transactions tried to write the same document. Server picks one to abort.
- Aborted one gets `TransientTransactionError` → withTransaction retries automatically.
- Repeated conflicts at high concurrency are a sign of hot documents.

**`NoSuchTransaction`:**
- The transaction expired (>`transactionLifetimeLimitSeconds`) or the session was already used for a newer transaction.
- Usually means the app held the transaction open too long.

## 10. Client Side Operations Timeout (CSOT, `timeoutMS`)

### 10.1 The problem CSOT solves

Pre-CSOT, configuring driver timeouts required understanding seven different options whose interactions were not obvious:

- `serverSelectionTimeoutMS` — selecting a server
- `connectTimeoutMS` — TCP/TLS handshake
- `socketTimeoutMS` — socket read after established
- `waitQueueTimeoutMS` — checkout from pool
- `wtimeoutMS` — server-side write concern timeout
- `maxTimeMS` — server-side operation timeout
- `maxCommitTimeMS` — server-side commit timeout

Setting them inconsistently caused operations to either hang forever or time out at random points without telling the application how much time was left.

### 10.2 The CSOT model

A single `timeoutMS` covers the entire operation's wall-clock time:
1. Server selection.
2. Connection checkout (pool wait).
3. Connection establishment (if a new connection needed).
4. Client-side encryption (if CSFLE/QE enabled).
5. Socket I/O (write the command, read the response).
6. Server execution (driver translates remaining budget into `maxTimeMS`).

The driver tracks remaining time as each phase completes. When the budget runs out, the driver aborts and raises a distinguished `MongoOperationTimeoutError`.

### 10.3 Hierarchy

`timeoutMS` can be set at:
- `MongoClient` — applies to all operations.
- `MongoDatabase` — overrides client for that DB.
- `MongoCollection` — overrides DB.
- Per-operation — overrides collection.

Per-session `timeoutMS` is also supported.

### 10.4 Deprecations under CSOT

| Old option | Replaced by |
|------------|-------------|
| `socketTimeoutMS` | `timeoutMS` |
| `waitQueueTimeoutMS` | `timeoutMS` |
| `wtimeoutMS` | `timeoutMS` |
| `maxTimeMS` (client-set) | `timeoutMS` |
| `maxCommitTimeMS` | `timeoutMS` |

`serverSelectionTimeoutMS` and `connectTimeoutMS` remain as floors (e.g. an extremely small `timeoutMS` won't reduce server selection below the configured floor).

### 10.5 Retry budget within CSOT

With CSOT enabled, retryable operations retry as many times as the remaining budget allows. Without CSOT, exactly one retry. This is significant for retryable reads where many small operations may need retry.

### 10.6 Cursor behavior under CSOT

The new `timeoutMode` option:

| Value | Behavior |
|-------|----------|
| `cursorLifetime` (default for non-tailable) | `timeoutMS` is the budget for **all** operations on this cursor (initial + every `getMore`). |
| `iteration` | `timeoutMS` applies independently to initial command and each `getMore`. |

Tailable cursors default to `iteration` since they live indefinitely.

### 10.7 Transactions under CSOT

`withTransaction(callback, options)` with `timeoutMS` covers the entire callback execution including retries. If the callback times out, the timeout is "refreshed" for the abort phase (so abort gets to run).

### 10.8 Migration recommendation

For new applications, use `timeoutMS` exclusively. For existing applications:
1. Audit current values of the deprecated options.
2. Set `timeoutMS` at the client level (e.g. 30000).
3. Override per-operation for known-fast or known-slow ops.
4. Remove the deprecated options.

## 11. DNS SRV and seedlist URIs

### 11.1 `mongodb+srv://` scheme

```
mongodb+srv://user:pass@cluster.example.com/myDB?retryWrites=true
```

The driver:
1. Resolves DNS SRV record `_mongodb._tcp.cluster.example.com`.
2. Each SRV record yields `(host, port)` pairs — these become the seed list.
3. Resolves TXT record at `cluster.example.com` for default options (subset only — `authSource`, `replicaSet`, `loadBalanced` allowed; `ssl/tls` not allowed via TXT since `mongodb+srv://` implies TLS).
4. Validates returned hostnames share the original domain (security).

### 11.2 SRV polling (`rescanSRVIntervalMS`)

For sharded clusters, the driver re-queries SRV every **60s** (`rescanSRVIntervalMS`, MongoDB 4.x+ drivers). Atlas adds/removes mongos hosts dynamically; SRV polling keeps the driver in sync.

For replica sets, SRV is queried once at startup. Replica set membership changes are discovered through SDAM (hello responses include `hosts` list).

### 11.3 `srvMaxHosts`

Limits the seed list size from SRV results. Useful for very large sharded clusters where you don't want the driver opening monitors to every mongos.

### 11.4 Why SRV exists

- Atlas-style: a single static hostname (`cluster.example.com`) backs a dynamic set of nodes. SRV lets you change the nodes without changing the URI.
- TLS implied by scheme — no `tls=true` needed.
- Default options in TXT record — central config.

### 11.5 SRV pitfalls

- **Port in URI**: not allowed with `mongodb+srv://`. Driver rejects.
- **Multiple hostnames**: not allowed with `mongodb+srv://`. Driver rejects.
- **DNS caching**: badly-behaved resolvers may cache SRV records well beyond TTL, delaying detection of new nodes. Use a known-good resolver or fall back to `mongodb://` with explicit seed list if your network DNS is unreliable.

## 12. TLS / SSL

### 12.1 Options

| Option | Production use |
|--------|----------------|
| `tls=true` | Required for Atlas. Implied by `mongodb+srv://`. |
| `tlsCAFile=path/to/ca.pem` | Custom CA for self-signed certificates. |
| `tlsCertificateKeyFile=path/to/cert.pem` | Client certificate for mutual TLS (X.509 auth). |
| `tlsCertificateKeyFilePassword=...` | Decrypts the client key. |
| `tlsAllowInvalidCertificates=true` | **Testing only.** Disables cert verification. |
| `tlsAllowInvalidHostnames=true` | **Testing only.** Allows cert/hostname mismatch. |
| `tlsInsecure=true` | **Testing only.** Both of the above. |

### 12.2 Atlas TLS

Atlas uses a public CA chain. No `tlsCAFile` is needed — system CAs work. If a customer is hitting cert errors connecting to Atlas:
1. System CA store is missing / outdated. Update OS CA bundles.
2. Corporate MITM proxy is intercepting TLS. The customer's IT has installed a custom root CA — needs `tlsCAFile` pointing to the corporate CA, or the proxy must be bypassed for `*.mongodb.net`.

### 12.3 X.509 auth

`authMechanism=MONGODB-X509` uses the client certificate as the auth identity. The certificate subject becomes the username. Common in Atlas + private endpoint deployments.

### 12.4 TLS antipatterns

- `tlsAllowInvalidCertificates=true` in production — defeats the purpose of TLS, no MITM protection. Find and fix the cert chain instead.
- `tlsInsecure=true` "for now" — never gets removed. Always pre-stage the proper CA bundle in deployment.

### 12.5 OCSP and certificate revocation

MongoDB drivers that wrap OpenSSL or platform TLS perform OCSP (Online Certificate Status Protocol) checks during handshake. Atlas certificates include an OCSP responder URL.

- **`tlsDisableOCSPEndpointCheck=true`**: skip OCSP-responder lookups, falling back to whatever revocation data is already cached or stapled. Useful when egress to the OCSP responder is firewalled.
- **`tlsDisableCertificateRevocationCheck=true`**: skip OCSP entirely (Go and some driver variants).

Customers behind strict egress firewalls sometimes see Atlas connection hangs of 5–10 seconds during handshake — the symptom of OCSP timeout. Allow outbound port 80 to `ocsp.*.amazontrust.com` (or whatever CA's OCSP responder Atlas uses), enable OCSP stapling, or set `tlsDisableOCSPEndpointCheck=true` (acceptable for short-lived Atlas certs but reduces revocation safety).

## 13. Compression

The `compressors` URI option enables wire-protocol compression:

```
mongodb://...?compressors=zstd,snappy,zlib
```

### 13.1 Negotiation

During the initial `hello` handshake, the client advertises the ordered list of `compressors` it supports. The server picks the first algorithm it also supports and confirms it in the response. From then on, both sides use `OP_COMPRESSED` framing:

```
OP_COMPRESSED { originalOpcode, uncompressedSize, compressorId, compressedData }
```

The `compressorId` field identifies which algorithm — `0` = noop, `1` = snappy, `2` = zlib, `3` = zstd. Each message is framed and compressed independently.

### 13.2 What gets compressed

Most application commands (find, insert, update, delete, aggregate, getMore, etc.) are compressed. Some commands are excluded (always sent uncompressed) per the OP_COMPRESSED spec: `hello`/`isMaster`, `saslStart`, `saslContinue`, `getnonce`, `authenticate`, `createUser`, `updateUser`, `copydbSaslStart`, `copydbgetnonce`, `copydb` — i.e., handshake and auth. This is so the server can read auth handshakes without negotiating compression first.

### 13.3 Algorithm choice

- **snappy**: fastest, modest compression ratio. Recommended for low-CPU clients.
- **zstd**: best ratio, slightly slower than snappy. Recommended for most workloads. Atlas default.
- **zlib**: backward compatibility. `zlibCompressionLevel` 1–9 trades CPU for ratio. Avoid for new deployments.

### 13.4 When to enable

- High-egress applications hitting cloud egress fees.
- Cross-region clusters where bandwidth latency dominates.
- BSON payloads with high textual redundancy (logs, JSON-heavy documents).

Compression adds CPU cost on both client and server — for CPU-bound workloads on small documents, compression may hurt throughput. Benchmark in your environment.

## 14. Authentication mechanisms

| Mechanism | Notes |
|-----------|-------|
| `SCRAM-SHA-256` | Default for MongoDB 4.0+. Username + password. |
| `SCRAM-SHA-1` | Legacy. Avoid for new deployments. |
| `MONGODB-X509` | Client cert as identity. |
| `MONGODB-AWS` | IAM via AWS STS, used for Atlas IAM auth. |
| `MONGODB-OIDC` | OIDC tokens. Used for human SSO and workload identity (Azure, GCP). |
| `GSSAPI` (Kerberos) | Enterprise only. |
| `PLAIN` (LDAP) | Enterprise only. |

The `authSource` URI option specifies which database holds the user document — usually `admin` for non-default users. Default depends on mechanism (e.g. SCRAM defaults to `admin`).

## 15. Putting it together: incident playbooks

### 15.1 All writes failing with `MongoServerSelectionError`

**Symptom**: Burst of `MongoServerSelectionError: Server selection timed out` errors from application code.

**Diagnose**:
- Read SDAM event logs. What was the last `TopologyDescriptionChangedEvent`? Topology `Unknown` means total discovery failure (DNS, firewall, wrong URI).
- Check pool events — repeated `PoolClearedEvent` indicates server-side instability (election, `ShutdownInProgress`), not a driver bug.
- Check the configured `serverSelectionTimeoutMS`. Values below 5000 turn normal elections into spurious failures.
- Confirm driver version. Drivers without streaming SDAM (pre-4.4 wire support) detect failover at `heartbeatFrequencyMS` cadence (~10s average).

**Fix**:
- Keep `serverSelectionTimeoutMS` at the 30000 default. Retryable writes will absorb the election window automatically.
- If discovery is broken, fix DNS/firewall first; the driver cannot recover from a topology it cannot reach.

### 15.2 Connections leak — pool grows to maxPoolSize

**Symptom**: Pool size climbs toward `maxPoolSize`; checkouts stall; `ConnectionCheckOutFailedEvent { reason: 'timeout' }` events fire.

**Diagnose**:
- Compare `ConnectionCheckedOutEvent` and `ConnectionCheckedInEvent` counts. A persistent gap means handles are not being returned.
- Common culprits: unconsumed cursors (manual iteration without `try/finally cursor.close()`), explicit sessions without `endSession()`, transactions started with the core API and abandoned on the error path.

**Fix**:
- Wrap every cursor and session in `try/finally`.
- Prefer `withTransaction` over the core API; it always closes the session.
- If the workload genuinely needs more concurrency, raise `maxPoolSize` (note: per-server memory cost).

### 15.3 Transactions sporadically fail with no clear reason

**Symptom**: Intermittent transaction errors during steady-state.

**Diagnose**:
- Inspect `err.errorLabels`. `TransientTransactionError` and `UnknownTransactionCommitResult` are both designed for automatic retry by `withTransaction`.
- `WriteConflict` (no label, exposed when the app catches inside the callback) means contention on a hot document.
- `TransactionTooLargeForCache` means dirty data exceeded 5% of WiredTiger cache.
- `NoSuchTransaction` means the transaction exceeded `transactionLifetimeLimitSeconds` (default 60s).

**Fix**:
- Switch from core API to `withTransaction` if not already using it.
- For `WriteConflict` storms: reduce contention (document layout, batching, or single-writer pattern).
- For `TransactionTooLargeForCache`: split the transaction or raise WiredTiger cache.
- For long-running transactions: split into smaller units or raise `transactionLifetimeLimitSeconds` server-side.

### 15.4 After enabling causal consistency, reads stall

**Symptom**: Latency spikes on reads after switching to `causalConsistency: true`.

**Diagnose**:
- Customer is reading from a heavily-lagged secondary. The driver sends `afterClusterTime`; the secondary blocks until its applied oplog passes that cluster time.
- Check secondary replication lag in Atlas metrics or `rs.printSecondaryReplicationInfo()`.

**Fix**:
- Reduce replication lag (sizing, network), or
- Switch the affected reads to `readPreference: primary`, or
- Pair the session with `readConcern: majority` + `writeConcern: majority` (the only combination that provides the full guarantees the customer probably assumes).

### 15.5 DNS SRV intermittently returns no hosts

**Symptom**: Connections succeed for hours, then a burst of `MongoServerSelectionError: getaddrinfo ENOTFOUND`.

**Diagnose**:
- Run `dig +short SRV _mongodb._tcp.cluster.example.com` from the affected host. If empty or inconsistent: local resolver issue.
- Check resolver negative-cache TTL.

**Fix**:
- Restart resolver, raise positive/negative TTLs sensibly.
- Mid-incident workaround: replace `mongodb+srv://` with explicit `mongodb://host1,host2,host3/...` URI to bypass SRV entirely.

### 15.6 Reads from secondary return data older than expected

**Symptom**: App reads via `readPreference: secondary` see data minutes old.

**Diagnose**:
- Check `maxStalenessSeconds` in the URI / read preference. If unset, secondary lag is unbounded.

**Fix**:
- Add `maxStalenessSeconds: 120` for analytics workloads.
- Use `secondaryPreferred` instead of `secondary` so primary fallback is possible.
- For consistency-critical reads, the correct answer is `primary` or `primaryPreferred`.

## 16. Reference: driver options summary

Defaults below are for modern (4.x+) drivers in the Node.js, Python, Java, Go, and C# lines unless noted.

| Option | Default | Notes |
|--------|---------|-------|
| `appName` | unset | Identifies the app in server logs. Always set in production. |
| `authMechanism` | mechanism negotiation | SCRAM-SHA-256 in most cases. |
| `authSource` | `admin` (SCRAM) | Auth DB. |
| `compressors` | unset | Set to `zstd,snappy,zlib` for bandwidth-heavy workloads. |
| `connectTimeoutMS` | 30000 | TCP/TLS handshake floor. |
| `directConnection` | false | Don't do SDAM discovery — talk to one server only. Rarely correct for production. |
| `heartbeatFrequencyMS` | 10000 (multi) / 60000 (single) | Polling cadence. Min 500. |
| `journal` (j) | unset | Force journal-sync writes. |
| `loadBalanced` | false | For Atlas Serverless / shared tiers. |
| `localThresholdMS` | 15 | Latency window for nearest mode and load balancing. |
| `maxConnecting` | 2 | Concurrent connection establishments. |
| `maxIdleTimeMS` | 0 | Idle timeout. 0 = unlimited. |
| `maxPoolSize` | 100 | Per-server connection pool max. |
| `maxStalenessSeconds` | unset | Filter stale secondaries. Min 90. |
| `minPoolSize` | 0 | Background-populated minimum. |
| `readConcernLevel` | server default | local/majority/snapshot/linearizable/available. |
| `readPreference` | primary | primary/primaryPreferred/secondary/secondaryPreferred/nearest. |
| `replicaSet` | unset | Required for non-SRV replica set URIs. |
| `retryReads` | true | Default-on in driver 4.2+. |
| `retryWrites` | true | Default-on in driver 4.x+. |
| `serverMonitoringMode` | auto | auto/stream/poll. |
| `serverSelectionTimeoutMS` | 30000 | Server selection budget. |
| `srvMaxHosts` | 0 (unlimited) | SRV seed list cap. |
| `srvServiceName` | mongodb | RFC 6335 SRV service name. |
| `timeoutMS` | unset | CSOT unified timeout. Recommended for new apps. |
| `tls` | false (true with srv) | Enable TLS. |
| `tlsCAFile` | unset | Custom CA. |
| `tlsCertificateKeyFile` | unset | Client cert. |
| `w` | server default | Write concern. Atlas defaults `majority`. |
| `waitQueueTimeoutMS` | 0 | Pool checkout wait. Deprecated for `timeoutMS`. |
| `wtimeoutMS` | unset | Server-side write concern timeout. Deprecated for `timeoutMS`. |
| `zlibCompressionLevel` | unset | 1–9 if using zlib. |

## 17. Java driver 5.x version timeline & 8.0 compatibility (verified-as-of: 2026-07-14)

<!-- appended by /dr deep-research 2026-07-14 · gap-fill: driver version recency for upgrade-regression triage -->

Release timeline (mongodb-driver-sync; dates from GitHub releases / community announcements):

| Version | Released | Perf-relevant notes |
|---|---|---|
| 5.4.0 | ~Jan 2025 (forum announcement) | — |
| 5.5.0 | ~Apr 2025 (forum announcement) | — |
| 5.6.0 | 2025 | `CommandCursorResult.results` cleared after `next()`/`tryNext()` (memory); cluster topology events added; `MongoStalePrimaryException` added |
| 5.6.4 | **2026-02-23** | patch on 5.6 line |
| 5.7.0 | 2026 | **"Restores the optimized codec path for `RawBsonDocument` encoding, fixing a performance regression"** (i.e. 5.6.x carried a codec perf regression); "Reuses `ConnectionSource` to avoid extra server selection"; stack-safe async loops; Netty update; CSOT/RTT timeout handling improvements; idle-`getMore` connection release fix |
| 5.8.0 | **2026-05-28** (latest as of 2026-07-14) | `RawBsonDocument` encode/decode optimization (eliminates intermediate allocations); vector search operators; libmongocrypt 1.18.1 |

Triage facts:
- **5.6.4 (Feb 2026) is a recent driver** — released ~16 months after MongoDB 8.0 GA (Oct 2024), fully 8.0-compatible under the drivers' minor-version-compatibility rule. A "driver too old for 8.0" framing is wrong for any 5.x ≥ 5.2.
- **5.6.x carries a known driver-side perf regression** (RawBsonDocument codec path) fixed in 5.7.0 — cheap-win upgrade recommendation in perf cases, but note it is a **constant client-side cost**: if the same driver version ran against both sides of a server A/B comparison, the driver version cannot by itself explain a delta between the runs.
- Compat matrix note: MongoDB drivers follow minor-version compatibility — a driver series that supports server 8.0 supports all 8.0.x patches.

Sources: [GitHub releases](https://github.com/mongodb/mongo-java-driver/releases) · [5.6.2 announcement](https://www.mongodb.com/community/forums/t/mongo-java-driver-5-6-2-released/332411) · [Java sync release notes](https://www.mongodb.com/docs/drivers/java/sync/current/reference/release-notes/) · [compat tables index](https://www.mongodb.com/docs/drivers/java/sync/current/compatibility/)

## Sources

1. [MongoDB CMAP Specification](https://github.com/mongodb/specifications/blob/master/source/connection-monitoring-and-pooling/connection-monitoring-and-pooling.md) — pool states, checkout algorithm, events.
2. [MongoDB SDAM Specification](https://github.com/mongodb/specifications/blob/master/source/server-discovery-and-monitoring/server-discovery-and-monitoring.md) — topology types, server types, state transitions.
3. [MongoDB Server Monitoring Specification](https://github.com/mongodb/specifications/blob/master/source/server-discovery-and-monitoring/server-monitoring.md) — polling vs streaming `hello`, RTT measurement.
4. [MongoDB Server Selection Specification](https://github.com/mongodb/specifications/blob/master/source/server-selection/server-selection.md) — read preference, latency window, `serverSelectionTimeoutMS`, operationCount load balancing.
5. [MongoDB Retryable Writes Specification](https://github.com/mongodb/specifications/blob/master/source/retryable-writes/retryable-writes.md) — txnNumber, RetryableWriteError label, supported ops.
6. [MongoDB Retryable Reads Specification](https://github.com/mongodb/specifications/blob/master/source/retryable-reads/retryable-reads.md) — read retry semantics, default-on behavior.
7. [MongoDB Read/Write Concern Specification](https://github.com/mongodb/specifications/blob/master/source/read-write-concern/read-write-concern.md) — w/j/wtimeoutMS, readConcern levels.
8. [MongoDB Causal Consistency Specification](https://github.com/mongodb/specifications/blob/master/source/causal-consistency/causal-consistency.md) — afterClusterTime, operationTime, $clusterTime gossip.
9. [MongoDB Driver Sessions Specification](https://github.com/mongodb/specifications/blob/master/source/sessions/driver-sessions.md) — lsid, server session pool, logicalSessionTimeoutMinutes.
10. [MongoDB Snapshot Sessions Specification](https://github.com/mongodb/specifications/blob/master/source/sessions/snapshot-sessions.md) — atClusterTime, snapshot read concern.
11. [MongoDB Transactions Specification](https://github.com/mongodb/specifications/blob/master/source/transactions/transactions.md) — error labels, commit retry, sharded coordinator.
12. [MongoDB Client Side Operations Timeout Specification](https://github.com/mongodb/specifications/blob/master/source/client-side-operations-timeout/client-side-operations-timeout.md) — `timeoutMS`, deprecations, hierarchy.
13. [MongoDB DNS Seedlist Discovery Specification](https://github.com/mongodb/specifications/blob/master/source/initial-dns-seedlist-discovery/initial-dns-seedlist-discovery.md) — `mongodb+srv://`, SRV polling.
14. [MongoDB Read Preference Modes documentation](https://www.mongodb.com/docs/manual/core/read-preference/) — modes, tag sets, hedged reads, antipatterns.
15. [MongoDB Causal Consistency and Read/Write Concerns](https://www.mongodb.com/docs/manual/core/causal-consistency-read-write-concerns/) — durability combinations matrix.
16. [MongoDB Transactions Internals documentation](https://www.mongodb.com/docs/manual/core/transactions/) — transactionLifetimeLimitSeconds, lock timeouts, withTransaction.
17. [MongoDB Node.js Driver Connection Options](https://www.mongodb.com/docs/drivers/node/current/fundamentals/connection/connection-options/) — TLS option matrix, Atlas patterns.
18. [SERVER-42809: Transaction coordinator metrics](https://jira.mongodb.org/browse/SERVER-42809) — sharded 2PC internals.
