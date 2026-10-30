<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Created by `/dr` deep research 2026-10-18; research dir `<local-path>`.

---
name: initial-sync-and-cdc
description: "mongosync initial sync (collection copy) and change event application (CDC): phase order, what the destination holds during the sync, /progress fields (info, collectionCopy, lag, canCommit, canWrite), temporary index changes, restart and oplog-window limits. TRIGGER: mongosync collection copy vs change event application; CEA; canCommit false; lag.overallLagSeconds; canWrite; destination not consistent before commit; mongosync restart after outage. SKIP: namespace filtering, verifier, reverse sync, loadLevel tuning -> mongosync reference."
version: "1.0.0"
updated: "2026-10-18"
category: "research"
whenToUse:
  - "why is canCommit false in mongosync"
  - "what does mongosync do after the initial copy"
  - "can I read the destination during mongosync"
keywords: ["mongosync", "initial sync", "collection copy", "change event application", "CEA", "CDC", "change stream", "canCommit", "canWrite", "lag", "commit timestamp", "oplog window"]
tags: ["mongodb", "mongosync", "migration", "cdc"]
provenance: "/dr · <local-path>"
---

# initial-sync-and-cdc

## Overview

mongosync migrates a source cluster to a destination in two sequential phases. In the collection copy phase it splits source collections into partitions and copies them to the destination. In the change event application (CEA, the CDC) phase it opens a change stream on the source and applies events, first those received during the copy, then live ones. The destination is not consistent with the source while the sync runs, and it cannot serve application traffic until you call commit and /progress reports canWrite true. Progress is read from /progress: info names the phase, collectionCopy gives byte estimates, lag.overallLagSeconds gives replication lag, and canCommit turns true once the initial copy is done and lag is 30 seconds or less (version 1.21+).

## Core Concepts

### initial-sync-and-cdc

- mongosync runs two phases in order: collection copy (initial transfer, by splitting source collections into partitions) and then change event application (CEA), which starts after the copy ends.[^c1-1][^c1-3]
- CEA opens a change stream on the source and applies events to the destination. It applies events received during the copy phase first, then events received during CEA. (two sources)[^c1-1][^c1-2]
- mongosync combines and reorders writes during the sync, so for a given document the number of writes on the destination can differ from the source. Documents are inserted in undefined order, not source natural order.[^c1-2][^c1-1]
- The destination is not guaranteed to match the source at any point while the sync runs, including while paused. Call commit to reach a matching state; at COMMITTING mongosync takes the commit timestamp (time of the latest source operation) and applies events up to it.[^c1-2][^c1-1]
- Tentative: canCommit is true only when the initial sync is complete, the embedded verifier is ready, and lag for mongosync and the verifier is 30 seconds or less (30-second rule from 1.21). lagTimeSeconds is deprecated in 1.21; use lag.overallLagSeconds. verified-as-of: 2026-10-18[^c1-3]
- During the copy, unique indexes sync as non-unique, TTL indexes get expireAfterSeconds set to MAX_INT, hidden indexes sync as non-hidden, and capped collections get the maximum size. These revert during COMMIT. On source 6.0+ (or buildIndexes afterDataCopy) indexes build after the data copy. (two sources)[^c1-2][^c1-1]
- Tentative: Transactions might not appear atomically on the destination, and retryable writes may not be retryable there.[^c1-2]

## Tools & Frameworks

_(none recorded)_

## Methodology

- Read /progress to see the phase: info is "collection copy", "change event application", "waiting for commit to complete" or "commit completed". collectionCopy.estimatedCopiedBytes is per instance; sum it across instances and divide by estimatedTotalBytes for percent complete. (two sources) verified-as-of: 2026-10-18[^c1-3][^c1-1] _(initial-sync-and-cdc)_

## Practical Patterns

- Tentative: For total size of 64 GB or less migrating to a destination with 4 or fewer CPUs, the copy phase issues fewer concurrent writes. Set an explicit load level at start or restart to override. verified-as-of: 2026-10-18[^c1-1] _(initial-sync-and-cdc)_

## Anti-Patterns

- Do not send application reads or writes to the destination until commit has run and /progress shows canWrite true. Do not use mongosync to maintain a standing secondary for DR or analytics.[^c1-1][^c1-2] _(initial-sync-and-cdc)_
- Avoid DDL, rolling index builds, an enabled balancer, and moveChunk/moveRange/movePrimary during the sync. DDL raises failure risk; a balancer enabled after start makes mongosync fail. (two sources)[^c1-2][^c1-1] _(initial-sync-and-cdc)_

## Troubleshooting

- mongosync is stateless and keeps restart metadata on the destination. After an outage, restart with the same parameters and confirm /progress returns state RUNNING. If the source outage exceeds the oplog window, mongosync cannot resume and the migration restarts from scratch, wiping migrated data. (two sources)[^c1-2][^c1-1] _(initial-sync-and-cdc)_

## Disagreements & Open Questions

- Open (initial-sync-and-cdc): The exact semantics of ceaStage values (e.g. steady state) and the lag.crudLagSeconds / ddlLagSeconds split were not read.
- Open (initial-sync-and-cdc): Whether the 30-second canCommit lag rule applies to pre-1.21 versions.

## References

### initial-sync-and-cdc

[^c1-1]: https://www.mongodb.com/docs/mongosync/current/about-mongosync/ — How mongosync Works (docs)
[^c1-2]: https://www.mongodb.com/docs/mongosync/current/reference/mongosync-behavior/ — mongosync Behavior (docs)
[^c1-3]: https://www.mongodb.com/docs/mongosync/current/reference/api/progress/ — mongosync progress API (docs)
