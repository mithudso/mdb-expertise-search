---
name: set-up-ttl-and-online-archive
title: Set up data lifecycle with TTL indexes and Atlas Online Archive
summary: Choose between deleting expired data with a TTL index and tiering cold data to queryable object storage with Atlas Online Archive, then set up, monitor and roll back whichever you pick.
applies_to: [atlas, self-managed]
sources:
  - skills/mongodb-operations-expert/references/mongodb-data-lifecycle.md
  - skills/mongodb-expert/references/mongodb-indexes-deep.md
  - skills/mongodb-expert/references/mongodb-80-performance-changes.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-online-archive.md
---
# Set up data lifecycle with TTL indexes and Atlas Online Archive

## When to use
- Collections grow without bound (sessions, events, logs, orders) and you need a retention policy.
- Storage cost on an Atlas cluster is driven by cold data that is rarely read.
- You must decide whether old data may be deleted or must stay queryable.

## Prerequisites (checklist)
- [ ] A written retention rule: how long data stays hot, whether it must stay queryable afterward, whether it may ever be deleted.
- [ ] The date field exists, is a BSON `Date` in every document that should expire or archive, and is indexed where the recipe says so.
- [ ] A backup you have restored at least once, because TTL deletion and archive expiration are permanent.
- [ ] Atlas Online Archive only: a dedicated M10 or larger cluster, a standard (not time-series, not capped, not a view) collection, and a role that can manage archives.
- [ ] Clocks synchronized (NTP) across replica set members for TTL.

## Steps

1. **Choose the mechanism.**
   | Question | TTL index | Online Archive |
   |---|---|---|
   | What happens to expired data? | Deleted permanently | Moved to object storage, still queryable (read-only) |
   | Where does it run? | Any MongoDB | Atlas M10+ only |
   | Rule shape | One date field, one duration | Date rule or custom MQL filter |
   | Access to old data | None | Slower queries through a federated endpoint |
   | Extra cost | Delete I/O | Storage at object-storage rates plus query processing charges |
   Expect: a decision. Use TTL for data with no recovery need (sessions, tokens, queue entries). Use Online Archive when deleted data must remain queryable. Do not use TTL as an archive. For time-series collections, set `expireAfterSeconds` on the collection itself instead of using Online Archive.

2. **TTL: confirm the field type.**
   ```js
   db.sessions.find({ createdAt: { $not: { $type: "date" } } }).limit(5)
   ```
   Expect: zero results. A document whose field is missing or not a Date is never expired.

3. **TTL: create the index.**
   ```js
   // Expire 30 days after createdAt
   db.sessions.createIndex({ createdAt: 1 }, { expireAfterSeconds: 2592000 })

   // Per-document expiry: each document carries its own expireAt
   db.events.createIndex({ expireAt: 1 }, { expireAfterSeconds: 0 })
   ```
   Expect: the index appears in `getIndexes()` with `expireAfterSeconds`. TTL indexes are single-field only; a compound index ignores the option. They cannot be created on capped collections.

4. **TTL (optional): limit what expires with a partial filter.**
   ```js
   db.sessions.createIndex(
     { lastActive: 1 },
     { expireAfterSeconds: 86400, partialFilterExpression: { status: "inactive" } }
   )
   ```
   Expect: only matching documents expire. A document that stops matching the filter stops being subject to TTL.

5. **TTL: understand and monitor the deletion rhythm.** The TTL monitor runs on the primary roughly every 60 seconds. For each TTL index it deletes until 50,000 documents, 1 second, or no more expired documents, then moves on. Deletion is not instant, and a large backlog takes several cycles.
   ```js
   db.sessions.countDocuments({ createdAt: { $lt: new Date(Date.now() - 2592000 * 1000) } })
   db.serverStatus().metrics.ttl
   ```
   Expect: the count of overdue documents falls over time toward zero. The `metrics.ttl` document (passes and deleted documents) should increase. Verify in the current MongoDB docs: the exact field names under `serverStatus().metrics.ttl` for your version.

6. **TTL: change the duration safely.** Reducing it can make a huge set eligible at once.
   ```js
   // IRREVERSIBLE: deleted documents cannot be recovered except from a backup. Test the filter with a count first.
   // First, delete the soon-to-be-expired documents in small batches (never one unbounded deleteMany)
   const cutoff = new Date(Date.now() - 7*24*3600*1000);
   db.sessions.countDocuments({ createdAt: { $lt: cutoff } });   // confirm the expected number
   let deleted;
   do {
     const ids = db.sessions.find({ createdAt: { $lt: cutoff } }, { _id: 1 })
                            .sort({ _id: 1 }).limit(1000).toArray().map(d => d._id);
     deleted = ids.length ? db.sessions.deleteMany({ _id: { $in: ids } }).deletedCount : 0;
     sleep(500);   // pause so replication lag and IOPS can recover
   } while (deleted > 0);
   // Then change the index
   db.runCommand({ collMod: "sessions", index: { keyPattern: { createdAt: 1 }, expireAfterSeconds: 604800 } })
   ```
   Expect: `getIndexes()` shows the new `expireAfterSeconds`. On Atlas, TTL deletions count against oplog and IOPS budgets; watch Disk IOPS and replication lag during large purges.

7. **Online Archive: check eligibility and index the date field.**
   ```js
   db.orders.createIndex({ createdAt: 1 })
   ```
   Expect: an indexed `createdAt`. For a DATE rule the `dateField` must be an already-indexed Date field. Confirm the tier is M10 or larger and the collection is a standard collection.

8. **Online Archive: design the rule and the partition fields before creating it.**
   ```json
   {
     "criteria": { "type": "DATE", "dateField": "createdAt", "expireAfterDays": 90 },
     "partitionFields": [
       { "fieldName": "createdAt", "order": 0 },
       { "fieldName": "region", "order": 1 }
     ]
   }
   ```
   Expect: a rule where the DATE field is partition field 0, with at most two partition fields. In the Atlas Admin API the DATE criteria field is `expireAfterDays`. Verify in the current MongoDB docs: that the DATE field must be partition field 0, the maximum number of partition fields, that partition fields cannot be changed after archiving begins, and that queries omitting the first partition field scan the whole archive. Pick partition fields from your common archive query filters, with low-to-medium cardinality. A `CUSTOM` rule takes an MQL filter string instead of `expireAfterDays`. Verify in the current MongoDB docs: the 7-day minimum for `expireAfterDays`.

9. **Online Archive: create the archive.**
   ```
   Atlas UI -> Cluster -> Online Archive -> Configure Online Archive -> choose namespace, rule, partition fields, schedule
   ```
   Expect: a new archive in `PENDING`, then `ARCHIVING`/`IDLE`. Verify in the current MongoDB docs: the current Atlas CLI or Admin API call for creating an archive; the corpus describes the UI and mentions a Terraform resource but gives no CLI command. Optional settings: a scheduled archiving window (daily, weekly or monthly, minimum 2 hours) to avoid peak hours, and a data expiration rule to delete from the archive after a set number of days (which cannot be undone).

10. **Online Archive: monitor throughput.** Atlas evaluates the rule every 5 minutes in continuous mode and archives up to 2 GB per cycle.
    ```
    Atlas UI -> Online Archive -> status, Bytes Archived, Archival Backlog, Archival Errors
    ```
    Expect: Archival Backlog trends down; cluster data size falls after archived documents are deleted from the live cluster. Fix field-not-found or type-mismatch errors by correcting the `dateField` data.

11. **Online Archive: query the archive.** Atlas gives two read-only connection strings: archive-only and cluster plus archive (federated). Use the archive-only string for analytics.
    ```js
    // Include the leading partition field to prune partitions
    db.orders.find({ createdAt: { $gte: ISODate("2023-01-01"), $lt: ISODate("2023-04-01") }, region: "us-east-1" })
    ```
    Expect: results in seconds to minutes rather than milliseconds. No writes, no `$lookup` across stores, no change streams, no transactions. Query processing is charged per terabyte processed with a 10 MB minimum per query.

12. **Set alerts.** Alert on Online Archive state changes and on billing thresholds.
    Expect: an alert fires before query-processing charges surprise you.

## Verify
- TTL: documents older than the threshold disappear within a few minutes per cycle, and `getIndexes()` shows the intended `expireAfterSeconds`.
- TTL: no document with a non-Date field was expected to expire (spot-check with the `$type` query from Step 2).
- Archive: the status is `IDLE` or `ARCHIVING`, backlog is falling, and Atlas storage metrics drop.
- Archive: a query through the archive-only endpoint returns an old document that no longer exists in the live collection.
- Cost: archived data volume times object-storage rates, plus expected query volume, is below the cluster storage it replaced. The corpus rule of thumb is that archive is cost-effective for data read less than about once a week.

## Rollback / abort
- TTL: remove the policy with `db.sessions.dropIndex("createdAt_1")`. Deleted documents are not recoverable except from backups.
- TTL: raise `expireAfterSeconds` with `collMod` to stop a runaway purge, then investigate.
- Archive: pause it in the UI. Pausing stops further archiving.
- Archive restore: there is no automated restore. Pause the archive first, then use the archive-only connection string and a `$merge` back into the live cluster.
  ```js
  db.orders.aggregate([
    { $match: { createdAt: { $gte: ISODate("2023-01-01"), $lt: ISODate("2023-04-01") } } },
    { $merge: { into: { atlas: { clusterName: "<cluster-name>", db: "mydb", coll: "orders" } },
                on: ["_id"], whenMatched: "keepExisting", whenNotMatched: "insert" } }
  ])
  ```
  Expect: documents reappear in the live collection. Verify them, then delete the archive. Restoring about 1 TB or more across many partitions is not recommended.
- Archive deleted: stored data is removed (state `DELETED`).

## Pitfalls
- Treating TTL as archival. It deletes; nothing is kept.
- Expecting precise timing. The monitor runs about every 60 seconds and has per-cycle limits.
- Lowering `expireAfterSeconds` on a big collection in one step. It triggers a deletion storm that hurts foreground traffic.
- Trying a compound TTL index. The TTL behavior is silently ignored.
- A field that is a string or number, not a Date. Those documents never expire.
- Changing a partially indexed document so it no longer matches the partial filter. TTL stops applying.
- TTL and multi-field retention rules. Use a scheduled job or application logic for complex rules, audit-grade retention, or mixed retention by document type.
- Archiving hot data. Every read costs processing charges and runs slowly.
- Wrong or missing partition fields. Every archive query then scans everything. They cannot be changed later.
- High-cardinality partition fields such as `_id` or a UUID. They create enormous numbers of tiny partitions.
- Using `$lookup` against archived data. It is not supported on federated stores; denormalize before archiving.
- Restoring while the archive rule is active. Restored documents can be re-archived immediately; pause first.
- Ignoring backlog. Throughput is capped at 2 GB per 5-minute cycle, so heavy write rates build a backlog.
- The 8.0 note in the corpus: there was no intentional batched-delete change from 7.0 to 8.0; fixes for TTL edge cases (for example time-series pre-1970 timestamps) landed in later 8.0.x releases. Check your patch level.

## Sources
- skills/mongodb-operations-expert/references/mongodb-data-lifecycle.md:342-370 (TTL fundamentals, Date requirement, single-field, `expireAfterSeconds: 0`)
- skills/mongodb-operations-expert/references/mongodb-data-lifecycle.md:370-387 (TTL monitor, 60 seconds, 50,000 documents or 1 second, deletion storm tip)
- skills/mongodb-operations-expert/references/mongodb-data-lifecycle.md:389-440 (primary-only, NTP, partial TTL, compound TTL ignored, `collMod`)
- skills/mongodb-operations-expert/references/mongodb-data-lifecycle.md:442 (when not to use TTL)
- skills/mongodb-expert/references/mongodb-indexes-deep.md:314-356 (TTL requirements, capped collections excluded, Atlas oplog and IOPS consideration)
- skills/mongodb-expert/references/mongodb-80-performance-changes.md:61 (batchedDeletes and TTL notes for 8.0)
- skills/mongodb-atlas-expert/references/mongodb-atlas-online-archive.md:145-200 (eligibility table, mechanism, tiers, limits)
- skills/mongodb-atlas-expert/references/mongodb-atlas-online-archive.md:200-282 (rules, partition fields, window, expiration)
- skills/mongodb-atlas-expert/references/mongodb-atlas-online-archive.md:309-362 (connection strings, partition pruning, query limits)
- skills/mongodb-atlas-expert/references/mongodb-atlas-online-archive.md:421-545 (status, metrics, errors, restore with `$merge`, cost model)
- skills/mongodb-atlas-expert/references/mongodb-atlas-online-archive.md:562-695 (limitations and anti-patterns)
