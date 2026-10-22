<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Created by `/dr` deep research 2026-10-19; research dir `<local-path>`.

---
name: mongodb-compound-index-design
description: "MongoDB compound index design for query performance: ESR (Equality, Sort, Range) key ordering and its ERS exception, index prefixes, selectivity, covered queries (IXSCAN with no FETCH, totalDocsExamined 0, _id and multikey caveats), multikey index bounds and $elemMatch intersection, partial indexes (partialFilterExpression planner eligibility), sparse indexes (incomplete-result refusal), index intersection (AND_SORTED/AND_HASH, rarely chosen) and index anti-patterns (redundant, unused; hide-then-drop). TRIGGER: 'what index for this query', 'which field order', 'ESR rule', 'covered query', 'docsExamined far above nReturned', 'partial vs sparse index', 'multikey bounds', 'redundant indexes'. SKIP: explain, plan cache, hint semantics -> mongodb-explain-plans-and-query-planner; wildcard/hidden/TTL indexes, index builds -> mongodb-special-indexes-and-index-builds; every index type -> mongodb-indexes-deep; fix-loop on one query -> deep-mongodb-mql-query-optimizer."
version: "1.0.0"
updated: "2026-10-19"
category: "research"
whenToUse:
  - "choose the key order for a compound index"
  - "make a query covered or explain why it is not"
  - "decide between partial and sparse indexes"
  - "clean up redundant or unused indexes"
keywords: ["compound index", "ESR rule", "equality sort range", "index prefix", "covered query", "selectivity", "multikey index", "elemMatch", "partial index", "partialFilterExpression", "sparse index", "index intersection", "index anti-patterns", "redundant index"]
tags: ["mongodb", "indexes", "query-optimization", "esr", "covered-queries"]
provenance: "/dr · <local-path>"
---

# MongoDB Compound Index Design: ESR, Selectivity, Covering and Multikey Bounds

## Overview

ESR (Equality, Sort, Range) is MongoDB's guideline for ordering keys in a compound index. Equality fields go first, then sort fields, then range fields. Sort-before-range lets the index return documents already ordered, so the query avoids a blocking in-memory SORT stage, at the cost of scanning more index keys. MongoDB's manual calls it a guideline, not a law: if the range predicate is very selective, ERS (range before sort) can win. Operators such as $ne, $nin and $regex count as range, and $in behaves like equality below 201 elements and like range at 201 or more. Verify any ordering with explain('executionStats'): check for a SORT stage and compare keys and documents examined with documents returned.

Selectivity is how well a predicate filters a collection. Selective predicates (equality on unique fields) use indexes well; $ne/$nin and broad regexes do not. A covered query is answered from the index alone: explain shows IXSCAN with no FETCH and totalDocsExamined 0. Coverage requires every filtered and returned field to be in the index, _id excluded unless indexed, no null-equality predicates, and no array-field coverage on multikey indexes. Official docs rank range selectivity against sort position (ERS exception) but do not rank equality fields by cardinality; a third-party blog says high-cardinality first, which the docs do not support. Coverage is not a guaranteed speedup: wider indexes are larger and can be slower.

A multikey index holds one entry per distinct array element. Because separate predicates on an array field can match different elements, MongoDB only intersects bounds when $elemMatch ties the predicates to one element. Without $elemMatch the planner scans one bound and applies the other as a FETCH filter, which inflates keysExamined and docsExamined. In compound multikey indexes, bounds on scalar fields compound normally (path-level multikey tracking, MongoDB 3.3.8+). Bounds on two fields from the same array compound only if $elemMatch targets their shared parent path. A compound index allows at most one array field per document. Multikey indexes also affect sorting (in-memory sort), covering (the array cannot be projected, and $elemMatch blocks covering), and exact-array matches (index finds candidates, then FETCH filters). Check explain for indexBounds, multiKeyPaths and the FETCH filter.

A partial index (partialFilterExpression) indexes only documents matching a filter, cutting storage and build/maintenance cost versus a full index. The planner uses it only when the query predicate implies the filter (same or narrower condition); otherwise it would return incomplete results. The filter may reference fields outside the index keys, which sparse indexes cannot do. Unique partial indexes enforce uniqueness only among matching documents. Operator support is limited and planner matching is fragile for complex filters such as $or, so verify with explain().

A MongoDB sparse index holds entries only for documents that contain the indexed field (null counts as present). For a sparse compound index, a document is indexed if it has at least one of the keys, so the index can carry many entries whose leading key is missing. The planner refuses a sparse index when it would give incomplete results for a query or sort, unless hint() forces it; hinted counts and sorts silently drop documents. Sparse plus unique allows many documents that omit the key. MongoDB's docs now steer users to partial indexes for precise control, and a community report shows a sparse compound index with an $exists:true predicate examining far more keys than the equivalent partial index. Depth caveat: all primary evidence is MongoDB-authored; the only independent source is one 2026 blog.

Index intersection lets MongoDB combine two single-field or prefix index scans (AND_SORTED or AND_HASH plan stages) to answer a multi-predicate query. The vendor manual documents it but states the optimizer rarely selects it: hash-based intersection is disabled by default and sort-based intersection is disfavored in plan scoring. Official guidance is that schema designs should not rely on it and should use compound indexes instead. An independent engineer's analysis found the planner's scoring penalty and productivity metric explain the avoidance, and forcing intersection needs internal test-only parameters. A 2024 request to expose forcing via query settings was closed Won't Do. For compound index design, intersection is a fallback to confirm in explain(), not a strategy.

The core MongoDB index anti-pattern is the unnecessary index: indexing every field or every query, leaving redundant indexes (a single-field index already covered by the prefix of a compound index) or indexes no query uses. Each index adds write cost, disk and cache use. MongoDB's manual names three categories: rarely used, redundant, and unused. Detection uses the $indexStats stage, but its counters reset on restart, are per node, and miss periodic jobs, secondary reads and constraint-only (unique/TTL) indexes. The recommended removal path is hide first (hideIndex, FCV 7.0+), watch, then drop. Hiding keeps write cost, so it tests read impact only.

## Core Concepts

### Compound Indexes and ESR Rule

- The ESR guideline orders compound index keys as Equality, then Sort, then Range. Equality fields always come first, and any number of equality keys may appear in any order among themselves.[^c1-1][^c1-2][^c1-3]
- Placing sort fields before range fields lets the index return results in index order and avoids a blocking in-memory SORT stage. The trade-off is that more index keys may be scanned.[^c1-1][^c1-2]
- Tentative: An index supports a sort on a subset of its keys only when the query has equality conditions on all prefix keys that precede the sort keys.[^c1-1]

### Index Selectivity and Covering Queries

- Query selectivity is how well a predicate filters out documents. An equality match on unique _id is highly selective. $ne and $nin match much of the index, so with an index they may perform no better than a collection scan. (two sources)[^c2-1][^c2-4]
- An index covers a query only if all filtered and returned fields are in the index. The projection must exclude _id with _id: 0 unless _id is indexed. No query field may equal null. Not all index types can cover queries (geospatial cannot). (two sources)[^c2-1][^c2-3]

### Multikey Indexes and Array Query Bounds

- A multikey index stores one entry per distinct array element, each pointing to the same document. MongoDB marks an index multikey automatically when an indexed field holds an array. (two sources)[^c3-2][^c3-4]
- MongoDB intersects bounds on a multikey array field only when $elemMatch joins the predicates. Example: grades: {$elemMatch: {$gte: 90, $lte: 99}} yields bounds [[90, 99]].[^c3-1][^c3-3]
- Without $elemMatch, {grades: {$gte: 90, $lte: 99}} can be satisfied by different elements, so MongoDB uses only one of [[90, Infinity]] or [[-Infinity, 99]]. The docs say MongoDB gives no guarantee which one. The planner applies the other predicate as a FETCH filter.[^c3-1][^c3-5][^c3-3]
- In a compound multikey index, MongoDB compounds bounds across scalar-field keys and array-field keys. Example: {item: 1, ratings: 1} with item: 'XYZ', ratings: {$gte: 3} yields both bounds. If bounds cannot be compounded, MongoDB constrains the scan by the leading field only.[^c3-1][^c3-4]
- Since MongoDB 3.3.8 (SERVER-15086), the server tracks multikey status per path rather than one flag per index. This lets the planner apply both bounds on a scalar leading field of a compound multikey index. Before that, it could bound only one side and filtered the rest after FETCH. explain now shows multiKeyPaths on IXSCAN. The change covers WiredTiger and in-memory engines. (two sources)[^c3-4][^c3-1]
- A compound multikey index allows at most one array-valued field per document. Creating the index fails if documents have arrays in more than one indexed field, and later inserts that violate this fail. (two sources)[^c3-2][^c3-4]
- Tentative: A multikey index can cover a query only if the array field is not projected (so the index must be compound) and the query has no $elemMatch. Exact-match queries on a whole array use the index to find candidates by the first element, then FETCH and filter. $expr does not support multikey indexes. Hashed indexes cannot be multikey, and a multikey index cannot be a shard key index.[^c3-2]

### Partial Indexes

- A query can use a partial index only if its predicate includes the partialFilterExpression or a narrower condition; otherwise the planner skips it to avoid incomplete results. Example: index filter rating>5 serves rating>=8 but not rating<8.[^c4-1][^c4-4]
- The filter may reference fields not in the index keys. Index {name:1} with filter {email:{$exists:true}} serves only queries that also constrain name and require non-null email; {name:1} with {name:{$exists:true}} behaves like a sparse index. (two sources)[^c4-1][^c4-4]
- partialFilterExpression cannot be combined with sparse; _id indexes and shard key indexes cannot be partial; with CSFLE/Queryable Encryption the filter cannot reference an encrypted field; a TTL index on a time series collection may filter only on the metaField. (two sources)[^c4-1][^c4-3]
- From MongoDB 7.3, equivalent indexes (same keys and same partial expression with a collation) cannot be created; pre-existing ones in upgraded databases are kept but only the first is used. Since 5.0, multiple partial indexes with the same key pattern are allowed if filters are not equivalent. (two sources) verified-as-of: 2026-10-18[^c4-1][^c4-3]

### Sparse Indexes

- A sparse index contains entries only for documents that have the indexed field, even when the value is null. Documents missing the field are skipped. A non-sparse index stores null for those documents.[^c5-1][^c5-5]
- A sparse compound index of ascending/descending keys indexes a document only if it contains a value for at least one of the keys. Adding a geospatial or text component changes this: the document is indexed only when it matches that geospatial or text field. (two sources)[^c5-1][^c5-2]
- Starting in MongoDB 5.0, a unique sparse index and a unique non-sparse index with the same key pattern can coexist on one collection, as can sparse and basic indexes with the same key pattern. (two sources) verified-as-of: 2026-10-14[^c5-1][^c5-2]
- The 2d, 2dsphere (version 2), text and wildcard index types are always sparse. (two sources) verified-as-of: 2026-10-14[^c5-1][^c5-2]

### Index Intersection

- MongoDB can combine the scans of two indexes (nested intersections are possible) to answer a query, using either whole indexes or index prefixes. The manual's example combines separate { qty: 1 } and { item: 1 } indexes on an orders collection.[^c6-1][^c6-3]
- The MongoDB 6.0 manual states that the query optimizer rarely selects index intersection plans, that hash-based index intersection is disabled by default, and that sort-based intersection is disfavored in plan selection, to prevent bad plan selection. verified-as-of: 2024-01-01[^c6-1][^c6-2]

### Index Anti-Patterns

_(no core claims)_

## Tools & Frameworks

- Verify an index ordering with explain('executionStats'). A SORT stage in the winning plan means an in-memory sort. Compare keys and documents examined against documents returned. Use cursor.hint() to force a candidate index while testing. (two sources)[^c1-1][^c1-3] _(Compound Indexes and ESR Rule)_
- In explain, an index-only plan shows PROJECTION_COVERED over IXSCAN with totalDocsExamined 0. A default projection that includes _id, or a partial projection, shows FETCH then PROJECTION_SIMPLE. Projecting _id forces a fetch because the index's $recordId is not _id. (two sources)[^c2-3][^c2-1] _(Index Selectivity and Covering Queries)_
- Diagnose with explain('executionStats'): a combined range in indexBounds on the array path means bounds were intersected. A single open-ended bound plus a FETCH filter, or keysExamined far above nReturned, means they were not. multiKeyPaths shows which path prefixes make the index multikey. In Pachot's demo, the no-$elemMatch query examined 44 keys with a FETCH filter; with $elemMatch it examined 38 with a single combined range. (two sources)[^c3-3][^c3-5] _(Multikey Indexes and Array Query Bounds)_
- Documented partialFilterExpression operators: equality, $exists:true (not false), $gt/$gte/$lt/$lte, $type, $and, $or, $in, $geoWithin, $geoIntersects. Originally (3.1.1) only $exists:true, comparisons, $eq, $type and top-level $and; richer expressions ($elemMatch, $exists:false, $ne/$not) remain an open backlog ticket. verified-as-of: 2026-07-21[^c4-1][^c4-3] _(Partial Indexes)_
- In explain() output, an intersection plan appears as an AND_SORTED stage (merges two RecordId-ordered index scans, like a merge join) or an AND_HASH stage (hashes one scan's results and probes with the other, with memory growing with matches).[^c6-2][^c6-3] _(Index Intersection)_
- Detect unused indexes with the $indexStats aggregation stage: an index with accesses.ops of 0 has not been used since the counter's `since` timestamp.[^c7-1][^c7-4] _(Index Anti-Patterns)_

## Methodology

- MongoDB's current manual presents ESR as a guideline with an explicit exception. If the range predicate is very selective, putting it before the sort fields (ERS) reduces the number of documents sorted, and the query accepts an in-memory sort. If avoiding in-memory sorts is critical, use ESR. verified-as-of: 2026-10-18[^c1-1][^c1-3] _(Compound Indexes and ESR Rule)_
- Tentative: Alex Bevi's explain examples show the trade-off. With sort on region and range on joined, {joined:1, region:1} examined 4 keys and used an in-memory SORT stage. {region:1, joined:1} examined 5 keys with no blocking sort. He also says equality fields need not be ordered from most to least selective.[^c1-2] _(Compound Indexes and ESR Rule)_
- Tentative: Reported size savings (e.g. 500MB full vs 25MB partial) are hypothetical illustrations, not benchmarks; no measured write-cost numbers found.[^c4-4] _(Partial Indexes)_
- Tentative: Diagnostic workflow: run explain('executionStats') or explain('allPlansExecution') and look for AND_SORTED/AND_HASH in the winning or rejected plans; use $indexStats to compare per-index usage. Intersection is a fallback when a compound index cannot be added.[^c6-3] _(Index Intersection)_
- Hide before dropping: db.collection.hideIndex() makes the planner ignore an index; unhideIndex() restores it instantly, avoiding a rebuild. MongoDB's manual workflow is identify, hide, measure, then dropIndexes() if the impact is negative.[^c7-2][^c7-1] _(Index Anti-Patterns)_
- A hidden index is still updated on every write and still uses disk and memory; a hidden unique index still enforces uniqueness and a hidden TTL index still expires documents. Hiding therefore tests read impact only and saves no write cost until the index is dropped. (two sources)[^c7-2][^c7-1] _(Index Anti-Patterns)_

## Practical Patterns

- Example from the MongoDB manual: for find({directors:'David Lynch', runtime:{$lt:130}}).sort({year:1}), the recommended index is {directors:1, year:1, runtime:1}. (two sources)[^c1-1][^c1-3] _(Compound Indexes and ESR Rule)_
- $ne, $nin and $regex are range operators, not equality operators, for ESR purposes. (two sources)[^c1-1][^c1-2] _(Compound Indexes and ESR Rule)_
- With .sort(), an $in list of fewer than 201 elements is expanded and merged in index sort order with a SORT_MERGE stage, so it acts like an equality field. At 201 or more elements it is ordered like a range, and later index fields cannot be used for sorting. MongoDB says this threshold is not guaranteed to stay the same across versions. (two sources) verified-as-of: 2026-10-18[^c1-1][^c1-3] _(Compound Indexes and ESR Rule)_
- Tentative: The ESR documentation says equality fields come first and a more selective equality makes the index more efficient. If the range predicate is very selective, place it before the sort fields (ERS), accepting a possible in-memory sort. $in arrays under 201 elements act like equality; 201 or more act like range.[^c2-2] _(Index Selectivity and Covering Queries)_
- Tentative: Cardinality ordering of equality fields is contested. A third-party blog says to place high-cardinality fields first and labels { customerId: 1, status: 1 } good. The MongoDB ESR page says equality fields may appear in any order among themselves and does not mention cardinality.[^c2-5][^c2-2] _(Index Selectivity and Covering Queries)_
- Index keys from the same array compound their bounds only if (a) the keys share the same path up to but excluding the field names, and (b) the query uses $elemMatch on that path. If the query predicates cover several array fields without $elemMatch, MongoDB compounds the leading scalar field with only one of them and does not guarantee which.[^c3-1][^c3-3] _(Multikey Indexes and Array Query Bounds)_
- Tentative: Sorting on a multikey-indexed array field adds an in-memory sort stage unless the bounds for all sort fields are [MinKey, MaxKey] and no multikey field bound shares the sort pattern's path prefix.[^c3-2] _(Multikey Indexes and Array Query Bounds)_
- A unique partial index enforces uniqueness only among documents matching the filter; non-matching documents may share key values (e.g. unique email filtered on password $exists:true, or on status:'active').[^c4-1][^c4-4] _(Partial Indexes)_
- Common patterns: index only active/pending status subsets, soft-delete (deletedAt:null), high-value items, conditional uniqueness, and TTL limited to a subset; benefit is smaller index and less write cost for non-matching documents. (two sources)[^c4-1][^c4-4] _(Partial Indexes)_
- A sparse unique index enforces uniqueness only among documents that have the field and allows multiple documents that omit it.[^c5-1][^c5-5] _(Sparse Indexes)_
- MongoDB docs recommend a partial index over a sparse index for precise control. A partial index with partialFilterExpression {field:{$exists:true}} reproduces sparse behavior, and a single index cannot specify both partialFilterExpression and sparse.[^c5-1][^c5-2][^c5-5] _(Sparse Indexes)_
- A { $exists: true } query on a sparse-indexed field is answered from the index alone with no FETCH. A { $exists: false } query does not use a sparse index and falls to a collection scan. (two sources)[^c5-3][^c5-5] _(Sparse Indexes)_
- Official guidance: schema designs should not rely on index intersection; compound indexes should be used instead. Independent writers agree (a well-designed compound index almost always beats intersection; 'if you think you need index intersection, you probably need better compound indexes').[^c6-1][^c6-2][^c6-3] _(Index Intersection)_

## Anti-Patterns

- Tentative: A third-party blog lists further exceptions: a covered query may justify range before sort when the result set is small, and a low-cardinality equality field needs careful placement. These are practitioner advice, not in the MongoDB manual.[^c1-3] _(Compound Indexes and ESR Rule)_
- Multikey indexes can cover queries over non-array fields only if the index tracks which fields cause it to be multikey. They cannot cover queries over array fields. In one forum case an index including an array field forced a FETCH and examined about 5.1M documents; the same index without that field examined none. (two sources)[^c2-1][^c2-4] _(Index Selectivity and Covering Queries)_
- Tentative: Covered indexes cost size. In a forum case a fully covering index was about 8x the single-field index and ran slightly slower than it for a name-only query. Unanchored regex scans the whole index keyspace; an anchored prefix regex bounds the scan and is much faster.[^c2-4] _(Index Selectivity and Covering Queries)_
- $elemMatch on the wrong path defeats compounding. For index {ratings.scores.q1: 1, ratings.scores.q2: 1}, ratings: {$elemMatch: {'scores.q1': 2, 'scores.q2': 8}} leaves ratings.scores.q2 unconstrained. Use {'ratings.scores': {$elemMatch: {q1: 2, q2: 8}}} instead. (two sources)[^c3-1][^c3-4] _(Multikey Indexes and Array Query Bounds)_
- Tentative: Large or unbounded arrays make multikey indexes costly: one entry per element, and index build and read performance degrade as arrays grow. Specific write-amplification claims come from a single third-party blog and are unverified. verified-as-of: 2026-03-31[^c3-6] _(Multikey Indexes and Array Query Bounds)_
- Tentative: Safer workaround for complex filters: set a boolean/flag field on write and use a simple equality partialFilterExpression; confirm with explain('executionStats') and hint().[^c4-2] _(Partial Indexes)_
- If a sparse index would return an incomplete result set for a query or sort, the planner does not select it unless hint() names it. Example: find().sort({plot:-1}) on a collection where some documents lack plot ignores a sparse index on plot. With hint({plot:1}) the query returns only documents that have plot.[^c5-1][^c5-5] _(Sparse Indexes)_
- Hinting a sparse index on a count of all documents (empty predicate) uses the sparse index even though the count is wrong: countDocuments({}, {hint:{rated:1}}) returns only documents that have rated.[^c5-1][^c5-5] _(Sparse Indexes)_
- Index intersection does not help a sort that needs an index separate from the query predicate; indexed sorts require a compound index whose key order matches the filter and sort. (two sources)[^c6-1][^c6-3] _(Index Intersection)_
- MongoDB's manual defines unnecessary indexes as three kinds: rarely used, redundant because another compound index covers them, or not used at all. Indexing every field or every query bloats the collection and hurts write performance.[^c7-1][^c7-3] _(Index Anti-Patterns)_
- Write amplification: every insert and delete updates all indexes on the collection, and an update that changes an indexed field removes the old entry and adds a new one in each index containing that field. Unused indexes also take WiredTiger cache space.[^c7-3][^c7-4] _(Index Anti-Patterns)_
- A single-field index whose key is the leading prefix of a compound index (e.g. {field:1} next to {field:1, other:1}) is redundant: the compound index serves the same filter. Keep the compound index and drop the prefix one. The manual's example drops {time:1} as covered by {day:1, time:1}, though that example's field names are inconsistent (days vs day). (two sources)[^c7-1][^c7-3] _(Index Anti-Patterns)_
- Tentative: Zero read ops does not prove an index is droppable: a unique index can enforce integrity with no reads, and dropping it permits duplicate keys. Netdata also says to exclude the _id index.[^c7-3] _(Index Anti-Patterns)_

## Troubleshooting

- Do not rely on the stage name alone to detect coverage. A forum reply reports a covered query shows plain PROJECTION on 4.0 and PROJECTION_COVERED on 5.0. totalDocsExamined 0 is the more dependable check, except when the query returns no results. (two sources) verified-as-of: 2026-10-18[^c2-4][^c2-5] _(Index Selectivity and Covering Queries)_
- Tentative: Real-world symptom: on MongoDB 4.4.14 a range query on a multikey path (products.productInfo.productId) with $gt and $lte used only the (479894, inf] bound, with the $lte as a FETCH filter. It examined 741,071 keys and 399,367 docs and took 10-14 s. Wrapping both predicates in $elemMatch fixed it.[^c3-5] _(Multikey Indexes and Array Query Bounds)_
- Tentative: From MongoDB 9.0, a query on an indexed field that becomes multikey while the query runs may fail with QueryKilledError; re-run it after the insert or update finishes. verified-as-of: 2026-10-14[^c3-2] _(Multikey Indexes and Array Query Bounds)_
- Partial indexes with an $or filter are a known planner weak spot: forum reports (MongoDB 6.0.4 and 6.0.13) show a query repeating the identical $or still got COLLSCAN or another index, while a query with plain conditions (e.g. comments:{$exists:true}) used it. No accepted fix is shown on the threads. (two sources) verified-as-of: 2024-02-09[^c4-2][^c4-3] _(Partial Indexes)_
- Tentative: Community report (Jan 2022, no replies captured): on a ~1.2M-document collection, a sparse compound index {A,B,C} serving { A:{$exists:true}, B:false, C:{$lt:date} } logged about 575,000 keys examined and almost 300,000 documents examined. The same keys as a partial index with filter {A:{$exists:true}} gave much better targeting. This is consistent with, but not proof of, the sparse compound rule that documents lacking A are still indexed.[^c5-4] _(Sparse Indexes)_
- Tentative: Why the planner avoids intersection (per Franck Pachot's analysis of server source tag r8.2.2): plans that finish their trial first get an 'EOF bonus', intersection plans take a small score penalty, and the productivity metric counts units of work without weighing their cost. Without the penalty the planner would still not pick AND_SORTED. verified-as-of: 2025-11-27[^c6-2] _(Index Intersection)_
- Forcing intersection is possible only via internal, test-only parameters (e.g. internalQueryForceIntersectionPlans) and is not supported; hint() accepts only a single index. A request (SERVER-86940, created 2024-02-22) to accept that flag in persistent query settings was closed Won't Do on 2024-04-25 with no recorded rationale. (two sources) verified-as-of: 2026-10-18[^c6-4][^c6-2] _(Index Intersection)_
- Tentative: The dedicated Index Intersection page no longer resolves in the live manual: the 4.4 and 6.0 URLs now serve the Indexes overview page. The 6.0 text survives in the Wayback Machine only, so cite versioned or archived copies. verified-as-of: 2026-10-19[^c6-1] _(Index Intersection)_
- $indexStats counters reset when mongod restarts, so zero ops after a recent restart is meaningless. Sources advise a long enough uptime to cover every query pattern (Netdata: at least 24 hours as a minimum, and a full workload cycle).[^c7-3][^c7-4] _(Index Anti-Patterns)_
- $indexStats counts only the node where it runs. MongoDB says to run it on each node for full usage; Pythian lists secondary-node usage as a precondition before dropping.[^c7-1][^c7-4] _(Index Anti-Patterns)_
- Hiding or unhiding an index resets its $indexStats counters, so record usage counts before toggling. Hiding needs featureCompatibilityVersion 7.0 or higher; the _id index cannot be hidden; cursor.hint() cannot target a hidden index. (two sources) verified-as-of: 2026-10-19[^c7-2][^c7-1] _(Index Anti-Patterns)_
- Tentative: Dropping an index takes a lock that can block operations (Pythian: write lock on the database; Netdata: exclusive collection lock), so schedule drops in low-traffic windows and keep a backup or the index definition to rebuild. verified-as-of: 2018-09-27[^c7-4] _(Index Anti-Patterns)_

## Disagreements & Open Questions

- Disagreement (Compound Indexes and ESR Rule): Older MongoDB docs (4.2/4.4) say a range before the sort forces a blocking sort and recommend range after sort. Current docs add the ERS exception for very selective ranges. The OneUptime blog states ESR with little discussion of ERS.[^c1-1][^c1-3]
- Open (Compound Indexes and ESR Rule): No quantified benchmark found for when ERS beats ESR (what selectivity threshold).
- Open (Compound Indexes and ESR Rule): Whether the 201-element $in threshold has changed in MongoDB 8.x.
- Open (Compound Indexes and ESR Rule): Alex Bevi's separate 'Tips and Tricks for Effective Indexing' talk, which lists the ESR exceptions, was not read.
- Disagreement (Index Selectivity and Covering Queries): OneUptime says high-cardinality equality fields go first. The MongoDB ESR page puts equality fields first in any order and does not rank them by cardinality. A MongoDB Learn course snippet (seen only in search results, not fetched) reportedly recommends a low-cardinality prefix to shrink the index.[^c2-5][^c2-2]
- Disagreement (Index Selectivity and Covering Queries): The manual says multikey indexes cannot cover array-field queries. Pachot's explain output shows FETCH with isMultiKey: true even for a scalar-valued document, so the planner may fetch more broadly than the doc wording implies.[^c2-1][^c2-3]
- Open (Index Selectivity and Covering Queries): The MongoDB Learn 'Index Size' page could not be fetched (returned only a title), so the low-cardinality-prefix size claim is unverified.
- Open (Index Selectivity and Covering Queries): Whether covered queries are consistently faster in real workloads; the only evidence found is one forum anecdote.
- Open (Index Selectivity and Covering Queries): Exact server version at which PROJECTION_COVERED became the reported stage name.
- Open (Multikey Indexes and Array Query Bounds): Only three organisations appear (MongoDB, an independent author writing from a Microsoft profile, OneUptime); no independent benchmark of multikey bounds was found.
- Open (Multikey Indexes and Array Query Bounds): Whether MongoDB 9.0 QueryKilledError on a field turning multikey is in a released version or only preview docs.
- Open (Multikey Indexes and Array Query Bounds): Current-version behaviour of the older docs claim that bounds intersection for scalar+array compound applies to WiredTiger/in-memory only; the current docs no longer state the engine limit.
- Open (Multikey Indexes and Array Query Bounds): SERVER-15086 notes that constraining multiple predicates on the same array-of-subdocuments path without $elemMatch remained unsolved; current status unchecked.
- Disagreement (Partial Indexes): OneUptime post lists $in/$or as supported and treats partial and sparse as equivalent for $exists:true; Jira SERVER-17853 (original scope) lists a narrower operator set. Current manual v7.3 includes $or/$in, so the blog is consistent with current docs but not older ones.[^c4-4][^c4-3]
- Open (Partial Indexes): Only two organisations (MongoDB, OneUptime) covered; no independent third-party benchmark of partial-index write savings found.
- Open (Partial Indexes): Whether the $or planner matching failure is fixed in 7.x/8.x.
- Open (Partial Indexes): Behaviour with parameterized/driver-bound queries not documented in any source found.
- Open (Partial Indexes): Manual v7.3 page has field-name typos (genre/rating vs genres/rated) in prose.
- Disagreement (Sparse Indexes): The OneUptime blog suggests hint({_id:1}) to sort without losing documents and says sparse indexes are kept for backward compatibility. The MongoDB manual says neither; it only says partial indexes give more control.[^c5-5][^c5-1]
- Open (Sparse Indexes): Depth contract not fully met: only two organisations (MongoDB, OneUptime) found; searches for Percona, Studio3T and Stack Overflow coverage returned only MongoDB docs.
- Open (Sparse Indexes): Whether the 2022 forum report's poor targeting is caused by sparse-compound membership rules or by the planner's bounds for $exists:true on the leading key; the thread has no answer.
- Open (Sparse Indexes): The sparse-compound row in the docs table says 'at least one of the keys'; not tested against a live server in this run.
- Open (Index Intersection): Whether the MongoDB 8.0/9.0 manual still documents index intersection or has dropped the page; only 6.0 text and older was read.
- Open (Index Intersection): Whether SBE-executed plans change intersection availability; no source found either way (SERVER-62150 concerns SBE multiplanning only).
- Open (Index Intersection): Why SERVER-86940 was closed Won't Do; the ticket has no comments.
- Disagreement (Index Anti-Patterns): Index-count guidance differs. The MongoDB developer article reportedly advises at most 50 indexes per collection, a MongoDB Learn course cites the hard limit of 64, and the manual's anti-pattern page gives no number. Only search snippets were seen; the developer-article URL returned 404 on fetch.[^c7-1]
- Disagreement (Index Anti-Patterns): Pythian (2018) recommends a backup before dropping and does not mention hiding; the current manual recommends hide-first. Pythian's lock statement (database write lock) also differs from Netdata's (exclusive collection lock) and is not verified against current server docs.[^c7-4][^c7-3]
- Open (Index Anti-Patterns): Is the 50-index recommendation still in MongoDB's developer article (fetch returned 404)? The 64-per-collection hard limit was not verified in the manual.
- Open (Index Anti-Patterns): Low-cardinality leading-field anti-pattern: no source found in this run; it belongs to the selectivity sibling concept.
- Open (Index Anti-Patterns): Current server docs on dropIndex lock behaviour were not checked.
- Open (Index Anti-Patterns): Unique/TTL caveat rests on Netdata only; the hidden-index manual confirms hidden unique/TTL indexes keep working but says nothing on dropping them.

## References

### Compound Indexes and ESR Rule

[^c1-1]: https://www.mongodb.com/docs/manual/tutorial/equality-sort-range-rule/ — MongoDB Manual: ESR guideline (docs)
[^c1-2]: https://alexbevi.com/blog/2020/05/16/optimizing-mongodb-compound-indexes-the-equality-sort-range-esr-rule/ — Alex Bevi: Optimizing compound indexes, ESR rule (blog)
[^c1-3]: https://oneuptime.com/blog/post/2026-03-31-mongodb-esr-rule-compound-index/markdown — OneUptime: How to Use the ESR Rule (blog)

### Index Selectivity and Covering Queries

[^c2-1]: https://www.mongodb.com/docs/manual/core/query-optimization/ — MongoDB manual: Query optimization (docs)
[^c2-2]: https://mongodb.com/docs/v7.0/tutorial/equality-sort-range-rule — MongoDB docs: ESR guideline (v7.0) (docs)
[^c2-3]: https://dev.to/franckpachot/index-only-scan-on-json-documents-with-covering-and-multi-key-indexes-in-mongodb-53h4 — Index-only scan on JSON documents with covering and multi-key indexes (blog)
[^c2-4]: https://mongodb.com/community/forums/t/adding-the-projected-fields-to-compound-index-to-create-covered-query-doesnt-improve-performance/199267 — MongoDB forum: covered index doesn't improve performance (forum)
[^c2-5]: https://oneuptime.com/blog/post/2025-12-15-mongodb-compound-indexes/view — OneUptime: MongoDB compound indexes (blog)

### Multikey Indexes and Array Query Bounds

[^c3-1]: https://www.mongodb.com/docs/manual/core/indexes/index-types/index-multikey/multikey-index-bounds.md — Multikey Index Bounds (docs)
[^c3-2]: https://www.mongodb.com/docs/manual/core/indexes/index-types/index-multikey.md — Multikey Indexes (docs)
[^c3-3]: https://dev.to/franckpachot/elemmatch-and-multi-key-indexes-i6e — $elemMatch and Multi-Key Indexes (Franck Pachot, May 2025) (blog)
[^c3-4]: https://jira.mongodb.org/browse/SERVER-15086 — SERVER-15086 Allow efficient range queries over non-array fields in multikey indices (repo)
[^c3-5]: https://www.mongodb.com/community/forums/t/mongo-indexbounds-doubts/165994 — Mongo IndexBounds doubts (MongoDB Community, May 2022) (forum)
[^c3-6]: https://oneuptime.com/blog/post/2026-03-31-mongodb-how-to-avoid-the-unbounded-array-growth-anti-pattern-in-mong/markdown — How to Avoid the Unbounded Array Growth Anti-Pattern in MongoDB (blog)

### Partial Indexes

[^c4-1]: https://mongodb.com/docs/v7.3/core/index-partial — Partial Indexes (MongoDB Manual v7.3) (docs)
[^c4-2]: https://www.mongodb.com/community/forums/t/partial-index-not-covering-or-query-filter/220425 — Partial Index not covering OR query filter (forum)
[^c4-3]: https://jira.mongodb.org/browse/SERVER-17853 — SERVER-17853 more complex partial filter expressions (forum)
[^c4-4]: https://oneuptime.com/blog/post/2025-12-15-mongodb-partial-indexes/view — How to Use MongoDB Partial Indexes (OneUptime, 2025-12-15) (blog)

### Sparse Indexes

[^c5-1]: https://www.mongodb.com/docs/manual/core/index-sparse.md — Sparse Indexes (MongoDB Manual) (docs)
[^c5-2]: https://www.mongodb.com/docs/manual/core/index-partial.md — Partial Indexes (MongoDB Manual) (docs)
[^c5-3]: https://www.mongodb.com/docs/manual/reference/operator/query/exists/ — $exists operator (MongoDB Manual) (docs)
[^c5-4]: https://www.mongodb.com/community/forums/t/sparse-vs-partial-index-for-compound-index/143869 — Sparse vs. Partial Index for compound index (forum)
[^c5-5]: https://oneuptime.com/blog/post/2026-03-31-mongodb-sparse-index/markdown — How to Create a Sparse Index in MongoDB (OneUptime, 2026-03-31) (blog)

### Index Intersection

[^c6-1]: https://web.archive.org/web/2024/https://www.mongodb.com/docs/v6.0/core/index-intersection/ — MongoDB Manual 6.0: Index Intersection (Wayback copy) (docs)
[^c6-2]: https://dev.to/franckpachot/mongodb-index-intersection-and-postgresql-bitmap-scan-40a6 — MongoDB Index Intersection (and PostgreSQL Bitmap-and) (blog)
[^c6-3]: https://oneuptime.com/blog/post/2026-03-31-mongodb-how-to-use-index-intersection-in-mongodb/markdown — How to Use Index Intersection in MongoDB (blog)
[^c6-4]: https://jira.mongodb.org/browse/SERVER-86940 — SERVER-86940 Persistent Query Setting to force index intersection (forum)

### Index Anti-Patterns

[^c7-1]: https://mongodb.com/docs/manual/data-modeling/design-antipatterns/unnecessary-indexes/ — MongoDB Manual: Unnecessary Indexes (design anti-pattern) (docs)
[^c7-2]: https://www.mongodb.com/docs/upcoming/core/index-hidden/ — MongoDB Manual: Hidden Indexes (docs)
[^c7-3]: https://www.netdata.cloud/guides/mongodb/mongodb-unused-indexes/ — Netdata: MongoDB unused indexes (blog)
[^c7-4]: https://www.pythian.com/blog/how-to-find-unused-index-and-drop-them-safely-in-mongodb — Pythian: How to find unused indexes and drop them safely in MongoDB (blog)
