<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-replication` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-replication
title: MongoDB Replication Expert
description: >
  MongoDB replica set architecture (primary, secondaries, arbiters, hidden, delayed members),
  elections and failover (priority, votes, Raft-based protocol v1), oplog mechanics (sizing,
  window, capped collection behavior), write concern levels (w:0/1/majority/tag, j:true,
  wtimeout), read preference modes (primary, primaryPreferred, secondary, secondaryPreferred,
  nearest), read concern levels (local, available, majority, linearizable, snapshot),
  rollbacks (cause, prevention with w:majority, rollback files), replication lag diagnosis
  (rs.printReplicationInfo, rs.printSecondaryReplicationInfo, flow control), initial sync
  process, change streams over replica sets, and replica set maintenance operations.
  Use when designing, operating, troubleshooting, or tuning MongoDB replica sets.
  SKIP: sharded-cluster topology, config-server replica sets, and chunk-migration interaction
  (use mongodb-sharding); deep change-stream/CDC patterns, resume tokens, and pre/post images
  (use mongodb-change-streams or mongodb-data-lifecycle); keeping two separate clusters in sync
  or live migration (use mongosync); single-cluster performance tuning unrelated to replication
  lag (use mongodb-performance-troubleshooting).
tags:
  - mongodb
  - replication
  - replica-set
  - high-availability
  - distributed-systems
  - database
keywords:
  - mongodb-replication
  - replica set
  - primary
  - secondary
  - arbiter
  - hidden member
  - delayed member
  - oplog
  - oplog window
  - election
  - failover
  - write concern
  - read preference
  - read concern
  - w:majority
  - w:1
  - j:true
  - wtimeout
  - rollback
  - replication lag
  - initial sync
  - change streams
  - rs.status
  - rs.conf
  - rs.stepDown
  - rs.reconfig
  - rs.initiate
  - rs.printReplicationInfo
  - rs.printSecondaryReplicationInfo
  - flow control
  - streaming replication
  - heartbeat
  - electionTimeoutMillis
  - priority
  - votes
  - majority commit point
  - causal consistency
when_to_use:
  - Designing or deploying a MongoDB replica set topology
  - Troubleshooting election failures or unexpected primary step-downs
  - Diagnosing replication lag or oplog window issues
  - Choosing write concern and read preference levels for an application
  - Understanding or preventing rollbacks during failover
  - Planning initial sync for new replica set members
  - Performing replica set maintenance (step-down, reconfig, member add/remove)
  - Configuring read concern for consistency vs availability tradeoffs
  - Monitoring replica set health and replication metrics
  - Working with change streams on replica sets
  - Investigating causal consistency session requirements
references:
  - title: "Replica Set Members - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/replica-set-members/"
  - title: "Replica Set Elections - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/replica-set-elections/"
  - title: "Replica Set Oplog - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/replica-set-oplog/"
  - title: "Write Concern - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/reference/write-concern/"
  - title: "Read Preference - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/read-preference/"
  - title: "Read Concern - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/reference/read-concern/"
  - title: "Rollbacks During Replica Set Failover - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/replica-set-rollbacks/"
  - title: "Replica Set Data Synchronization - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/replica-set-sync/"
  - title: "Change Streams - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/changestreams/"
  - title: "Troubleshoot Replica Sets - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/tutorial/troubleshoot-replica-sets/"
  - title: "Replica Set Deployment Architectures - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/replica-set-architectures/"
  - title: "Perform Maintenance on Replica Set Members - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/tutorial/perform-maintence-on-replica-set-members/"
  - title: "Write Concern for Replica Sets - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/replica-set-write-concern/"
  - title: "Read Preference Use Cases - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/read-preference-use-cases/"
  - title: "Delayed Replica Set Members - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/replica-set-delayed-member/"
  - title: "Hidden Replica Set Members - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/core/replica-set-hidden-member/"
  - title: "Percona: MongoDB Replica Set Elections"
    url: "https://www.percona.com/blog/mongodb-replica-set-scenarios-and-internals-part-ii-elections/"
  - title: "Percona: MongoDB Rollback in Replicaset"
    url: "https://www.percona.com/blog/mongodb-rollback-in-replicaset/"
  - title: "Percona: Delayed Secondary Member"
    url: "https://www.percona.com/blog/mongodb-delayed-secondary-member-of-a-replica-set-and-how-it-can-be-useful/"
  - title: "Severalnines: Developer's Guide to MongoDB Replica Sets"
    url: "https://severalnines.com/blog/developer-s-guide-mongodb-replica-sets/"
  - title: "Severalnines: How to Prevent Rollbacks in MongoDB"
    url: "https://severalnines.com/blog/how-to-prevent-rollbacks-mongodb/"
  - title: "MongoDB Rollback: Minimize Data Loss - ScaleGrid"
    url: "https://scalegrid.io/blog/mongodb-rollback/"
  - title: "Fix Oplog Issues - Atlas Docs"
    url: "https://www.mongodb.com/docs/atlas/reference/alert-resolutions/replication-oplog/"
  - title: "Reconfigure Replica Set with Unavailable Members - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/tutorial/reconfigure-replica-set-with-unavailable-members/"
  - title: "db.collection.watch() - MongoDB Docs"
    url: "https://www.mongodb.com/docs/manual/reference/method/db.collection.watch/"
  - title: "Mydbops: MongoDB Read Concerns"
    url: "https://www.mydbops.com/blog/read-concerns-in-mongodb"
  - title: "DZone: MongoDB Replication Lag and Facts of Life"
    url: "https://dzone.com/articles/mongodb-replication-lag-and"
related_skills:
  - mongodb-expert
  - mongodb-atlas-expert
  - mongodb-data-lifecycle
  - mongodb-sharding
  - mongodb-performance-troubleshooting
---

# MongoDB Replication Expert

## Overview

MongoDB replication provides redundancy and high availability through **replica sets** -- groups of `mongod` processes that maintain the same data set. A replica set contains one primary member that receives all writes and one or more secondary members that replicate the primary's data asynchronously via the **oplog** (operations log). Replica sets are the foundation of MongoDB's data durability, fault tolerance, and read scaling strategy.

Key guarantees of a properly configured replica set:
- **Automatic failover**: if the primary becomes unavailable, an election promotes a secondary to primary within ~12 seconds (median, with default settings).
- **Data redundancy**: every data-bearing member holds a complete copy of the data set.
- **Read scaling**: applications can distribute reads across secondaries using read preferences.
- **Tunable consistency**: write concern and read concern let applications choose their durability and consistency guarantees per operation.

---

## 1. Replica Set Architecture

### 1.1 Member Types

| Member Type | Holds Data | Can Become Primary | Votes | Visible to Clients |
|---|---|---|---|---|
| **Primary** | Yes | Is primary | 1 | Yes |
| **Secondary** | Yes | Yes (if priority > 0) | 1 (default) | Yes |
| **Arbiter** | No | No | 1 | No |
| **Hidden** | Yes | No (priority must be 0) | 0 or 1 | No (excluded from read preference) |
| **Delayed** | Yes | No (priority must be 0) | 0 (recommended) | No (should be hidden) |

**Primary**: The only member that accepts write operations. Records all writes to its oplog. At most one primary per replica set at any time.

**Secondary**: Maintains an identical copy of the primary's data set by asynchronously applying operations from the primary's oplog. Can serve read operations when read preference allows it. Can be elected primary during failover.

**Arbiter**: Participates in elections but holds no data. Provides a tiebreaking vote in even-member-count topologies. Must not run on the same system as primary or secondary members. Has exactly 1 election vote and a default priority of 0.

**Hidden Members**: Must have `priority: 0`, so they cannot become primary. Excluded from default client read routing. Use for dedicated tasks: reporting queries, backups, analytics workloads. Only reachable by direct connection.

**Delayed Members**: Maintain a time-delayed copy of the data (configured via `secondaryDelaySecs`). Must be hidden and should be non-voting. Serve as a defense against accidental data destruction -- the delayed copy preserves the state from N seconds ago.

Configuration for a delayed member:
```javascript
{
  "_id": 3,
  "host": "delayed.example.net:27017",
  "priority": 0,
  "hidden": true,
  "secondaryDelaySecs": 3600,  // 1-hour delay
  "votes": 0
}
```

### 1.2 Topology Limits

| Limit | Value |
|---|---|
| Maximum total members | 50 |
| Maximum voting members | 7 |
| Minimum recommended (production) | 3 data-bearing members |

### 1.3 Recommended Topologies

**Three-member replica set (P-S-S)**: One primary, two secondaries. This is the minimum recommended production topology. Tolerates one member failure while maintaining a majority for elections and `w: "majority"` writes.

**Primary-Secondary-Arbiter (P-S-A)**: Costs less than P-S-S but carries availability risk. If the sole data-bearing secondary goes down, `w: "majority"` writes fail because no majority of data-bearing voting members remains. Avoid in sharded clusters.

**Geographically distributed**: Place members across data centers for disaster recovery. Ensure a majority of voting members resides in the primary data center so elections can proceed without cross-DC quorum.

---

## 2. Elections and Failover

### 2.1 Election Triggers

Elections occur when:
1. A new node is added to the replica set.
2. The replica set is initiated with `rs.initiate()`.
3. Maintenance commands are issued: `rs.stepDown()`, `rs.reconfig()`.
4. Secondaries lose connectivity to the primary for longer than `electionTimeoutMillis` (default: **10 seconds**).
5. The primary detects it can see only a minority of voting members and steps down.

### 2.2 Election Protocol (pv1)

MongoDB uses a Raft-based consensus protocol (protocol version 1, `pv1`):
- Replica set members send **heartbeats every 2 seconds**.
- If a heartbeat does not return within 10 seconds, the member is marked inaccessible.
- Before calling a real election, a candidate runs a **dry election** (`replSetRequestVotes` without incrementing the term) to check if it would win.
- If the dry election succeeds, the candidate calls the actual election with an incremented term.
- The first member to receive a **majority of votes** becomes primary.

**Eligible voting states**: PRIMARY, SECONDARY, STARTUP2 (unless newly added), RECOVERING, ARBITER, ROLLBACK.

### 2.3 Priority and Votes

- **Higher-priority members** call elections sooner and are more likely to win.
- `priority: 0` members cannot become primary and do not seek election.
- Elections continue until the highest-priority available member becomes primary.
- Non-voting members must have `priority: 0` and `votes: 0`.
- Maximum 7 voting members, but up to 50 total members.

### 2.4 Election Timing

| Metric | Default Value |
|---|---|
| `electionTimeoutMillis` | 10,000 ms (10 seconds) |
| Heartbeat interval | 2,000 ms (2 seconds) |
| Median election time | ~12 seconds |
| `catchUpTimeoutMillis` | Configurable; balances faster failover vs. preserving `w:1` writes |

### 2.5 Behavior During Elections

- **Writes**: Cannot be processed until a new primary is elected.
- **Reads**: Continue on secondaries if read preference permits.
- **Retryable writes**: Compatible drivers automatically retry once on failover (enabled by default in MongoDB 4.2+).
- **Open connections**: The primary closes all open client connections when stepping down.

---

## 3. Oplog Mechanics

### 3.1 What Is the Oplog

The oplog (`local.oplog.rs`) is a special **capped collection** that records all write operations in an **idempotent** format. Every replica set member maintains its own oplog. Secondaries copy and apply entries from the primary's oplog to keep their data set current.

Key properties:
- Operations are idempotent: applying them once or multiple times produces the same result.
- Multi-document updates are decomposed into individual per-document operations.
- The oplog can grow beyond its configured size to avoid deleting the **majority commit point**.
- You cannot drop or manually write to `local.oplog.rs` on replica set members (MongoDB 5.0+).

### 3.2 Default Oplog Size

| Platform | Storage Engine | Default | Min | Max |
|---|---|---|---|---|
| Unix/Windows | WiredTiger | 5% of free disk space | 990 MB | 50 GB |
| Unix/Windows | In-Memory | 5% of physical memory | 990 MB | 50 GB |
| macOS (64-bit) | WiredTiger | 192 MB | -- | -- |

### 3.3 Oplog Window

The **oplog window** is the time difference between the newest and oldest oplog entry. A secondary that falls behind by more than the oplog window cannot catch up through normal replication and must perform a **full initial sync**.

Monitoring the oplog window:
```javascript
rs.printReplicationInfo()
// Output includes:
//   configured oplog size (MB)
//   log length start to end (hours)
//   oplog first/last event timestamps
```

### 3.4 Configuring Oplog Size

**Before first start** (mongod config file):
```yaml
replication:
  oplogSizeMB: 10240  # 10 GB
```

**Dynamic resize on running instance**:
```javascript
db.adminCommand({ replSetResizeOplog: 1, size: 10240 })
```

**Minimum retention period** (keeps entries even if oplog is full):
```yaml
storage:
  oplogMinRetentionHours: 24
```

Or dynamically:
```javascript
db.adminCommand({ replSetResizeOplog: 1, minRetentionHours: 24 })
```

Retention rules: entries are removed only when both (a) the oplog reaches max configured size AND (b) the entry is older than the retention period.

### 3.5 Workloads Requiring Larger Oplog

- **Multi-document updates**: translated into individual operations, using significant oplog space.
- **High deletion rates**: equal oplog entries as inserts even though disk stays stable.
- **Frequent in-place updates**: many oplog entries with no net disk size change.

### 3.6 Streaming Replication

MongoDB uses **streaming replication** by default: the source member sends a continuous stream of oplog entries to secondaries instead of waiting for polling. Benefits:
- Reduced replication lag under high load or high latency.
- Reduced secondary read staleness.
- Reduced risk of losing `w:1` writes during failover.
- Lower latency for `w: "majority"` and `w: >1` writes.

Disable with `--setParameter oplogFetcherUsesExhaust=false` (only if source member resource constraints require it).

---

## 4. Write Concern

Write concern controls the durability guarantee of a write operation before the server acknowledges it.

### 4.1 Write Concern Specification

```javascript
{ w: <value>, j: <boolean>, wtimeout: <number> }
```

### 4.2 `w` Values

| Value | Behavior | Rollback Risk |
|---|---|---|
| `w: 0` | No acknowledgment. May still return socket/network errors. | High |
| `w: 1` | Primary acknowledges after in-memory write. | Moderate -- data can roll back if primary steps down before replicating. |
| `w: "majority"` | Majority of data-bearing voting members durably write to oplog. Default for most deployments (MongoDB 5.0+). | None for acknowledged writes. |
| `w: <number>` (>1) | Primary + (n-1) secondaries acknowledge. Hidden, delayed, and priority-0 members can participate. | Low (depends on n). |
| `w: "<tag>"` | Custom tagged write concern using `settings.getLastErrorModes`. | Depends on tag definition. |

### 4.3 `j` (Journal) Option

| Setting | Behavior |
|---|---|
| `j: true` | Write must be synced to on-disk journal before acknowledgment. |
| `j: false` | Write acknowledged after in-memory application (faster, less durable). |
| `j` unspecified + `w: "majority"` | Depends on `writeConcernMajorityJournalDefault` (defaults to `true`). |

### 4.4 `wtimeout`

- Specifies a time limit (ms) for the write to propagate to the required members.
- **Does not apply** if `w <= 1`.
- Returns a write concern error if timeout exceeded, but **does not undo** data modifications already applied.
- `wtimeout: 0` means no timeout (wait indefinitely).

### 4.5 Default Write Concern

For most deployments: `{ w: "majority" }` (implicit default in MongoDB 5.0+).

Exception for arbiter topologies:
```
IF (arbiter_count > 0) AND (non_arbiter_count <= majority(voting_count))
  THEN default = { w: 1 }
  ELSE default = { w: "majority" }
```

| Topology | Non-Arbiters | Arbiters | Default |
|---|---|---|---|
| P-S-A | 2 | 1 | `{ w: 1 }` |
| P-S-S-S-A | 4 | 1 | `{ w: "majority" }` |

### 4.6 Calculating Majority

```
majority = MIN(
  majority_of_all_voting_members,
  count_of_all_data_bearing_voting_members
)
```

Use `rs.status()` which returns the `writeMajorityCount` field.

### 4.7 Write Concern and Transactions

Set write concern at the **transaction level**, not on individual operations within a transaction:
```javascript
session.startTransaction({ writeConcern: { w: "majority" } });
```

---

## 5. Read Preference

Read preference determines which replica set member(s) receive read operations.

### 5.1 Modes

| Mode | Where Reads Go | Default | Use Case |
|---|---|---|---|
| `primary` | Primary only | Yes | Strongest consistency; freshest data. |
| `primaryPreferred` | Primary; falls back to secondary if primary unavailable | No | Near-fresh reads that tolerate failover. |
| `secondary` | Secondaries only | No | Offload primary; freshness not required. |
| `secondaryPreferred` | Secondaries; falls back to primary if none available | No | Analytics, reporting, read-heavy workloads. |
| `nearest` | Lowest-latency member regardless of role | No | Geo-distributed deployments; minimizing latency. |

### 5.2 Staleness and `maxStalenessSeconds`

All non-primary modes may return stale data because secondaries replicate asynchronously.

`maxStalenessSeconds` excludes secondaries whose replication lag exceeds the specified threshold. Minimum value is 90 seconds. This reduces stale reads when using `secondary`, `secondaryPreferred`, or `nearest`.

```javascript
// Node.js driver example
const client = new MongoClient(uri, {
  readPreference: 'secondaryPreferred',
  maxStalenessSeconds: 120
});
```

### 5.3 Tag Sets

Tag sets route reads to specific members based on custom labels (e.g., data center, hardware tier):
```javascript
readPreference: {
  mode: 'secondary',
  tagSets: [{ dc: 'us-east-1' }, { dc: 'us-west-2' }, {}]
}
```
The driver tries tag sets in order and falls through to the next set if no member matches. An empty tag set `{}` matches any member.

### 5.4 Hedged Reads

For `nearest` read preference on sharded clusters, MongoDB can send reads to two members and return the first response. Enable per operation or connection-wide. Reduces tail latency for latency-sensitive workloads.

---

## 6. Read Concern

Read concern controls the consistency and isolation of data returned by read operations.

### 6.1 Levels

| Level | Guarantees | Rollback Risk | Transactions | Performance |
|---|---|---|---|---|
| `"local"` | Returns instance data; no majority guarantee | May be rolled back | Yes | Fastest |
| `"available"` | Like local but may return orphaned docs (sharded) | May be rolled back | No | Fastest |
| `"majority"` | Returns data acknowledged by majority; durable | None | Yes | Comparable |
| `"linearizable"` | Reflects all majority-acknowledged writes before read | None | No | Slowest |
| `"snapshot"` | Majority-committed data at a single point in time | None (if txn commits with w:majority) | Yes | Comparable |

### 6.2 Consistency vs Availability Spectrum

```
Strongest consistency                              Highest availability
linearizable --> majority --> snapshot --> local --> available
```

### 6.3 Key Constraints

- **`"linearizable"`**: Only works on primary. Query filter must uniquely identify a single document. Always use `maxTimeMS` to avoid indefinite blocking if majority members are unavailable. Cannot use with `$out` or `$merge`.
- **`"available"`**: Avoid on sharded collections; can return orphaned documents during chunk migrations. Use `"local"` instead.
- **`"snapshot"`**: For transactions, the transaction must commit with `w: "majority"` to guarantee snapshot consistency.
- **`"majority"`**: Reads from an in-memory view of the data at the majority-commit point. Requires WiredTiger storage engine.

### 6.4 Causal Consistency

To guarantee causal consistency within a session, use:
- Read concern: `"majority"`
- Write concern: `{ w: "majority" }`

This ensures read-your-own-writes, monotonic reads, monotonic writes, writes-follow-reads across the session. MongoDB automatically sets `afterClusterTime` on reads in causally consistent sessions.

```javascript
const session = client.startSession({ causalConsistency: true });
const coll = session.getDatabase('mydb').getCollection('data');
coll.updateOne({ _id: 1 }, { $set: { x: 10 } },
  { writeConcern: { w: 'majority' } });
coll.findOne({ _id: 1 },
  { readConcern: { level: 'majority' } });
```

---

## 7. Rollbacks

### 7.1 When Rollbacks Occur

A rollback reverts write operations on a former primary when it rejoins its replica set after failover. It happens when:
1. The primary accepted writes that had **not** replicated to a majority of secondaries.
2. The primary stepped down (due to election, network partition, or `rs.stepDown()`).
3. A new primary was elected and accepted new writes.
4. The former primary rejoins and must reconcile its divergent oplog.

Rollbacks are rare and typically result from network partitions or secondaries unable to keep up with write throughput.

### 7.2 Rollback Algorithms

**Recover-to-a-timestamp** (default, MongoDB 4.0+): The former primary reverts to a consistent point in time and then applies operations until catching up to the sync source. No size limitation.

**Rollback via refetch** (legacy): Finds the common oplog point, reverts all operations to that point. Limited to 300 MB of rolled-back data. Only occurs when `enableMajorityReadConcern` is `false` (which is fixed to `true` and cannot be changed from MongoDB 5.0+).

### 7.3 Rollback Data Files

By default, MongoDB writes rolled-back data to BSON files:
```
<dbpath>/rollback/<collectionUUID>/removed.<timestamp>.bson
```

Read with `bsondump`:
```bash
bsondump <dbpath>/rollback/20f74796-d5ea-42f5-8c95-f79b39bad190/removed.2020-02-19T04-57-11.0.bson
```

Controlled by `createRollbackDataFiles` parameter (default: `true`).

### 7.4 Preventing Rollbacks

The primary defense is `{ w: "majority" }` write concern:
- Ensures writes replicate to a majority before acknowledgment.
- Acknowledged data is guaranteed not to roll back.
- Default in MongoDB 5.0+ for most deployments.

Additional measures:
- Enable journaling on all voting members.
- Monitor replication lag to ensure secondaries keep pace.
- Avoid P-S-A topologies where the loss of one data-bearing member prevents majority writes.

### 7.5 Rollback Limits

- Default rollback time limit: **24 hours** (configurable via `rollbackTimeLimitSecs`).
- Measured from the first common oplog operation to the last divergent entry.
- User operations are killed when a member enters the `ROLLBACK` state (MongoDB 4.2+).

---

## 8. Replication Lag Diagnosis

### 8.1 Checking Oplog Status

```javascript
// On any member: shows oplog size and time window
rs.printReplicationInfo()
```
Output includes configured oplog size (MB), log length in hours, and first/last event timestamps.

### 8.2 Checking Secondary Lag

```javascript
// Shows how far behind each secondary is from the primary
rs.printSecondaryReplicationInfo()
```
Provides a readable summary of each secondary's lag in seconds.

### 8.3 Detailed Status

```javascript
// Full replica set status including optimeDate per member
rs.status()
```
Compare `optimeDate` between primary and each secondary to calculate current lag.

### 8.4 Common Causes of Replication Lag

| Cause | Diagnosis | Remediation |
|---|---|---|
| Slow secondary disk I/O | Check `iostat`, IOPS metrics | Upgrade storage, separate data/journal volumes |
| Secondary under heavy read load | Monitor query throughput on secondary | Offload reads, add more secondaries |
| Index builds on secondary | Check `currentOp` for index build operations | Use rolling index builds |
| Network congestion | Monitor bandwidth between primary/secondary | Upgrade network, place members in same DC |
| Large bulk writes on primary | Oplog application cannot keep pace | Batch writes, increase secondary resources |
| Long-running transactions | Oplog entries deferred until commit | Keep transactions short |

### 8.5 Flow Control

Flow control (enabled by default) limits the primary's write rate to keep `majority committed` lag under `flowControlTargetLagSeconds` (default: 10 seconds). This prevents secondaries from falling too far behind but may throttle write throughput on the primary.

### 8.6 Alerting Thresholds

- Set alerts when lag exceeds 30-60 seconds.
- Ensure oplog window is at least 24 hours for safe operations.
- Monitor `members[n].optimeDate` differences in `rs.status()`.
- In Atlas, use the Replication Oplog Window alert to detect when the oplog window falls below a threshold.

---

## 9. Initial Sync

### 9.1 Logical Initial Sync (Default)

When a new member joins a replica set or an existing member's data is too stale to recover via oplog, MongoDB performs initial sync:

1. **Database cloning**: Scans every collection in the source member and inserts all data into the destination member.
2. **Index building**: In parallel with data cloning, all collection indexes are built.
3. **Oplog buffering**: During cloning, newly arriving oplog records are stored in a temporary collection in the `local` database.
4. **Oplog application**: Buffered oplog entries are applied to bring the member up to date.
5. **State transition**: Member transitions from `STARTUP2` to `SECONDARY`.

### 9.2 File Copy Based Initial Sync (Enterprise Only)

Uses file system copy operations; potentially faster than logical initial sync.

Enable with:
```
--setParameter initialSyncMethod=fileCopyBased
```

Limitations: cannot run backups during sync, only one source member at a time.

### 9.3 Sync Source Selection

Default: `primaryPreferred` for voting members, `primary` if chaining is disabled.

**First-pass criteria**: member must be in PRIMARY or SECONDARY state, online, visible (not hidden), within 30 seconds of newest oplog entry, matching index build and vote settings.

**Fault tolerance**: persistent network errors restart initial sync from the beginning. Temporary errors allow resumption for up to 24 hours (configurable via `initialSyncTransientErrorRetryPeriodSeconds`). Up to 10 retry attempts before fatal error.

### 9.4 Sizing Considerations

- Ensure the oplog window is large enough to cover the entire initial sync duration plus a buffer for concurrent writes.
- Ensure the destination member has sufficient disk space for data, indexes, and the temporary oplog buffer.

---

## 10. Change Streams Over Replica Sets

### 10.1 Overview

Change streams provide a real-time, ordered stream of data changes on collections, databases, or entire deployments. They require a replica set or sharded cluster.

### 10.2 Resume Tokens

Every change event includes an `_id` field that serves as the **resume token**. This token encodes the position in the oplog. To resume a change stream after interruption:

```javascript
const resumeToken = lastChangeEvent._id;
const stream = db.collection('orders').watch([], {
  resumeAfter: resumeToken
});
```

### 10.3 `resumeAfter` vs `startAfter`

| Option | Behavior |
|---|---|
| `resumeAfter` | Resume after the event identified by the token. Fails if the event was an invalidate. |
| `startAfter` | Resume after the token, even if it was an invalidate event. Use to resume after drop/rename. |

### 10.4 Token Validity

Resume tokens remain valid only while the originating oplog entry exists. If the oplog entry has been truncated (fallen off the oplog window), the change stream cannot resume from that token.

Best practices:
- Process change events promptly or persist resume tokens externally.
- Size the oplog to accommodate your change stream processing latency.
- Use `startAtOperationTime` for broader resumption without a specific token.

### 10.5 Pre- and Post-Images

MongoDB 6.0+ supports retrieving the full document before (`fullDocumentBeforeChange`) and after (`fullDocument: 'updateLookup'` or `'whenAvailable'`) the change. Requires enabling `changeStreamPreAndPostImages` on the collection.

> **Cross-reference**: See the `mongodb-data-lifecycle` skill for deeper coverage of change stream patterns, CDC architectures, and pre/post image configuration.

---

## 11. Replica Set Maintenance

### 11.1 Stepping Down the Primary

```javascript
// Step down, allowing a new election (default: 60s step-down period)
rs.stepDown()

// Step down for 120 seconds, wait up to 30 seconds for secondary to catch up
rs.stepDown(120, 30)
```

The primary closes all client connections and transitions to SECONDARY state. An election occurs to choose a new primary.

### 11.2 Adding a Member

```javascript
rs.add("newhost.example.net:27017")

// With options:
rs.add({
  host: "newhost.example.net:27017",
  priority: 0,
  votes: 0
})
```

The new member performs initial sync. After sync completes, adjust priority and votes as needed via `rs.reconfig()`.

### 11.3 Removing a Member

```javascript
rs.remove("oldhost.example.net:27017")
```

Or via `rs.reconfig()` by modifying the `members` array.

**Constraint**: Reconfiguration can add or remove at most **one voting member at a time**. To add or remove multiple voting members, issue a series of reconfigs.

### 11.4 Force Reconfiguration

Use when a majority of members are unavailable:
```javascript
cfg = rs.conf()
cfg.members = [cfg.members[0], cfg.members[2]]  // Keep only surviving members
rs.reconfig(cfg, { force: true })
```

**Warning**: Force reconfiguration immediately installs the new config even if it changes multiple voting members. Can cause rollback of `w: "majority"` committed writes. Use only as a last resort.

### 11.5 Performing Rolling Maintenance

For maintenance on secondaries:
1. Connect to the secondary.
2. Shut down the `mongod` instance.
3. Perform maintenance (upgrade, index build, config change).
4. Restart the `mongod` instance.
5. Wait for the member to catch up via replication.

For the primary:
1. Complete maintenance on all secondaries first.
2. Use `rs.stepDown()` to trigger an election.
3. Perform maintenance on the former primary (now secondary).

### 11.6 Preventing a Secondary from Becoming Primary

```javascript
cfg = rs.conf()
cfg.members[2].priority = 0
rs.reconfig(cfg)
```

Use for: secondaries in remote data centers, members dedicated to backups or analytics.

---

## 12. Anti-Patterns

| Anti-Pattern | Why It Is Harmful | Recommendation |
|---|---|---|
| Using `w: 1` for critical writes | Data can roll back if primary fails before replicating | Use `w: "majority"` for all critical writes |
| P-S-A topology in sharded clusters | Loss of one data-bearing member prevents majority writes | Use P-S-S (three data-bearing members) |
| Ignoring oplog window | Secondaries may fall off the oplog and require full resync | Monitor oplog window; set `oplogMinRetentionHours` |
| Reading stale data without awareness | Non-primary read preferences may return stale or rolled-back data | Set `maxStalenessSeconds`; understand consistency tradeoffs |
| Running arbiter on data-bearing host | Resource contention; arbiter should be lightweight | Deploy arbiter on separate, minimal host |
| Force reconfig as routine operation | Can cause rollback of majority-committed writes | Use only when majority of members are down |
| No `maxTimeMS` with linearizable reads | Can block indefinitely if majority members unavailable | Always set `maxTimeMS` |
| Disabling journaling on voting members | Rollback data may be lost; w:majority guarantees weakened | Keep journaling enabled on all voting members |
| Very large transactions blocking oplog | Defers oplog entries until commit, causing lag spikes | Keep transactions short; batch operations |
| Not monitoring replication lag | Silent data staleness; missed oplog window | Set alerts at 30-60s lag; monitor oplog window |

---

## 13. Troubleshooting Checklist

### Election Not Completing
- [ ] Verify majority of voting members are reachable (`rs.status()`)
- [ ] Check `electionTimeoutMillis` setting
- [ ] Confirm no member has `priority` higher than available candidates' optime
- [ ] Look for network partition between members
- [ ] Check for term mismatches in replica set logs

### Replication Lag
- [ ] Run `rs.printSecondaryReplicationInfo()` to quantify lag
- [ ] Check secondary disk I/O and CPU utilization
- [ ] Verify no index builds running on secondary (`db.currentOp()`)
- [ ] Check network throughput between primary and secondary
- [ ] Verify flow control is not overly throttling primary (`serverStatus.flowControl`)
- [ ] Check for long-running transactions holding oplog entries

### Rollback Occurred
- [ ] Examine rollback files in `<dbpath>/rollback/`
- [ ] Review write concern used by application (was it `w: "majority"`?)
- [ ] Check for network partition timeline
- [ ] Use `bsondump` to inspect rolled-back documents
- [ ] Verify `writeConcernMajorityJournalDefault` is `true`

### Initial Sync Failing
- [ ] Verify oplog window is large enough for sync duration
- [ ] Check disk space on destination member
- [ ] Verify sync source is in PRIMARY or SECONDARY state
- [ ] Check network connectivity to sync source
- [ ] Review logs for `initialSyncTransientErrorRetryPeriodSeconds` exhaustion

---

## 14. Quick Reference Commands

```javascript
// Initialize a new replica set
rs.initiate({
  _id: "myRS",
  members: [
    { _id: 0, host: "mongo1:27017" },
    { _id: 1, host: "mongo2:27017" },
    { _id: 2, host: "mongo3:27017" }
  ]
})

// View replica set status
rs.status()

// View replica set configuration
rs.conf()

// Check oplog info
rs.printReplicationInfo()

// Check secondary lag
rs.printSecondaryReplicationInfo()

// Step down primary
rs.stepDown()

// Add a member
rs.add("mongo4:27017")

// Remove a member
rs.remove("mongo4:27017")

// Reconfigure (e.g., change priority)
cfg = rs.conf()
cfg.members[1].priority = 2
rs.reconfig(cfg)

// Resize oplog dynamically
db.adminCommand({ replSetResizeOplog: 1, size: 20480 })

// Check write majority count
rs.status().writeMajorityCount

// Force a member to sync from a specific source
db.adminCommand({ replSetSyncFrom: "mongo2:27017" })
```

---

## 15. Cross-References

- **mongodb-expert**: General MongoDB architecture and operations -- complements replication with broader server administration context.
- **mongodb-atlas-expert**: Atlas-managed replica sets, Atlas-specific replication settings and monitoring.
- **mongodb-data-lifecycle**: Change streams (deep coverage of resume tokens, pre/post images, CDC), TTL indexes, time series collections.
- **mongodb-sharding**: Sharded cluster replication (config server replica sets, shard replica sets, chunk migration interaction with replication).
- **mongodb-performance-troubleshooting**: Performance diagnosis that overlaps with replication lag analysis, slow oplog application, and write throughput tuning.
- **mongosync**: Inter-cluster replication via the mongosync binary — initial sync + change-stream-based CDC between two replica sets or sharded clusters, used for Atlas Live Migration, MongoDB 7.0 Cluster-to-Cluster Sync, multi-cloud/DR active-passive, and live cutover/rollback. Load `mongosync` when the question is "how do I keep two MongoDB clusters in sync" or "how do I size the source oplog window for a migration" rather than "how does primary election work in my single replica set". The `mongosync` skill covers `--cluster0`/`--cluster1` config, filters (`includeNamespaces`/`excludeNamespaces`), the IDLE/RUNNING/PAUSED/COMMITTING/COMMITTED/REVERSING state machine, oplog-window-vs-`ChangeStreamHistoryLost` failure mode, one-mongosync-per-shard topology, verification (embedded, dbHash, migration-verifier), reverse sync, and the mongosync vs Atlas Live Migration vs C2C Sync decision matrix.
