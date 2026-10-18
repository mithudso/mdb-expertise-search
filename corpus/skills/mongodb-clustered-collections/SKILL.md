---
name: mongodb-clustered-collections
description: >-
  MongoDB clustered collections (clustered index) expert: collections that
  store documents together with the _id index in _id order, in one WiredTiger
  file, instead of a separate _id index file.
  TRIGGER: creating a clustered collection (db.createCollection with
  clusteredIndex { key: { _id: 1 }, unique: true }); deciding whether to use a
  clustered vs regular collection; clustered index as a TTL index
  (expireAfterSeconds); one-write/one-read storage benefit; range/equality
  scans on _id without a secondary index; clustered-collection limitations
  (single clustered index, no in-place conversion, large/random _id key
  penalties); IoT/log/event/time-ordered workloads keyed on _id.
  SKIP: general index types (single/compound/multikey/partial/TTL/wildcard/hashed),
  Time Series collections, WiredTiger storage-engine internals
  (cache/checkpoint/MVCC), and embedding-vs-referencing schema design ->
  mongodb-expert (see its references/ for each topic).
version: 1.0.2
updated: 2026-07-17
model: claude-sonnet-5
effort: medium
category: mongodb
whenToUse: >-
  Use when creating or evaluating a MongoDB clustered collection: choosing a
  clustered vs regular collection, wiring the clusteredIndex option, using the
  clustered index as a TTL index, or diagnosing why a clustered collection
  underperforms (large or random _id keys, need for a second clustered index).
keywords:
  - clustered collection
  - clustered index
  - clusteredIndex
  - createCollection
  - _id order storage
  - ttl clustered index
  - expireAfterSeconds
  - wiredtiger single file
  - range scan _id
  - iot log storage
tags:
  - mongodb
  - clustered-collections
  - indexes
  - storage
  - ttl
  - data-modeling
---

# MongoDB Clustered Collections

> Scope: the **clustered-collection storage feature** and its clustered index.
> For the full index-type catalog see `mongodb-expert` (`references/mongodb-indexes-deep.md`);
> for Time Series collections (a different columnar storage optimization) see
> `mongodb-expert` (`references/mongodb-time-series.md`); for WiredTiger engine
> internals see `mongodb-expert` (`references/mongodb-wiredtiger-internals.md`).
>
> `verified-as-of: 2026-07-15` — behavior confirmed against the MongoDB Manual
> (docs published from v6.0 through v8.x); re-verify version-specific claims
> before quoting.

## Overview

A **clustered collection** stores its documents and the `_id` index **together**,
ordered by the clustered index key, in a single WiredTiger file. A regular
(non-clustered) collection stores the `_id` index in a **separate** file from the
documents, so an insert/update/delete costs **two writes** (document + index) and
a lookup costs **two reads** (index then document). A clustered collection folds
these into **one write** and **one read**, because the index *is* the document
store. [^cc-manual]

## Core concepts

- **Clustered index key must be `{ _id: 1 }`** and the index must be `unique: true`.
  You cannot cluster on an arbitrary field. [^cc-manual][^createcoll]
- **Documents are physically stored in `_id` order.** This makes range scans and
  equality comparisons on `_id` fast **without a secondary index**, because the
  data itself is the ordered index. [^cc-manual]
- **Lower storage size** than a regular collection (no separate `_id` index
  file), which also improves bulk-insert and query performance. [^cc-manual]
- **Creation is at collection-create time only** via `db.createCollection()` with
  the `clusteredIndex` option specifying the `_id` key and `unique: true`.
  [^createcoll]

## Creating a clustered collection

```javascript
db.createCollection("events", {
  clusteredIndex: {
    key: { _id: 1 },
    unique: true,
    name: "events clustered key"
  }
})
```

Add `expireAfterSeconds` to make the clustered index double as a **TTL index**
(see below). Clustered collections can also be created through the Compass and
Atlas UIs. [^compass][^createcoll]

## TTL on the clustered index

A clustered index **is also a TTL index** when you set `expireAfterSeconds`.
Using the clustered index as the TTL index (rather than a separate TTL index on a
date field) **improves delete performance and further reduces storage size**,
because the collection needs no secondary TTL index at all. This makes clustered
collections a strong fit for expiring event/log data keyed on a time-ordered
`_id`. [^cc-manual]

## When to use (decision guide)

Prefer a clustered collection when **all** of the following hold:
1. The workload queries or ranges primarily on `_id`. [^cc-manual]
2. The `_id` values are **monotonic / time-ordered** (e.g. ObjectId, a timestamp,
   or an ascending sequence) — insert-ordered appends keep writes cheap.
3. You want lower storage and single-read/single-write economics — good for IoT,
   logs, events, and other append-and-expire data. [^cc-manual]

Prefer a **regular collection** (or Time Series — see `mongodb-expert`'s
`references/mongodb-time-series.md`) when you query mostly on non-`_id` fields,
need multiple clustered orderings, or your `_id` keys are large or random.

## Anti-patterns / limitations

- **Only one clustered index per collection** — documents can be stored in only
  one physical order. [^cc-manual]
- **No in-place conversion** either direction: you cannot turn a regular
  collection into a clustered one, or a clustered one back. Recreate + migrate to
  change. [^cc-manual]
- **Large `_id` keys hurt.** A large clustered key inflates the storage size of
  both the collection and every secondary index (secondary indexes reference the
  clustered key), degrading performance. Keep `_id` compact. [^cc-manual]
- **Randomly generated `_id` values decrease performance** — random insert
  positions defeat the ordered-append advantage. Use monotonic keys. [^cc-manual]

## Troubleshooting

- **"Need a second clustered ordering"** → not possible; add secondary indexes for
  other access paths, or reconsider the data model. [^cc-manual]
- **Clustered collection slower than expected** → check for large or random `_id`
  keys, or heavy querying on non-`_id` fields (which needs secondary indexes and
  loses the benefit). [^cc-manual]
- **"Can I convert my existing collection?"** → no; create a new clustered
  collection and migrate the data. [^cc-manual]
- **Optimizing a specific slow query against a clustered collection**
  (explain-verified rewrite loop) → mongodb-expert (references/deep-mongodb-mql-query-optimizer.md) (/dmqo).

## References

[^cc-manual]: MongoDB Manual: Clustered Collections (storage model, `{_id:1}`/unique key, one-write/one-read, TTL via expireAfterSeconds, benefits, limitations). https://www.mongodb.com/docs/manual/core/clustered-collections/
[^createcoll]: MongoDB Manual: db.createCollection() (clusteredIndex option syntax and constraints). https://www.mongodb.com/docs/manual/reference/method/db.createCollection/
[^compass]: MongoDB Compass docs: Create a Clustered Collection (UI creation path). https://www.mongodb.com/docs/compass/collections/clustered-collection/
