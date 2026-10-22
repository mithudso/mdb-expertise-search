<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Created by `/dr` deep research 2026-10-19; research dir `<local-path>`.

---
name: mongodb-query-shape-optimization
description: "MongoDB query-shape optimization — rewriting slow find/aggregate query shapes so indexes do the work; deep skip/offset pagination, keyset pagination and sort patterns. Index-backed vs blocking SORT, skip/limit vs keyset pagination, operator anti-patterns (unanchored or case-insensitive $regex, $ne/$nin/$not/$exists:false, $where, limited $expr), $in/$or union plans (201-element $in threshold, SORT_MERGE), projection and PROJECTION_COVERED vs FETCH, countDocuments vs estimatedDocumentCount, batchSize/getMore, maxTimeMS, sharded targeting vs scatter-gather (shard key in filter). TRIGGER: 'sort exceeded memory limit', 'deep pagination slow', '$regex not using index', '$or does COLLSCAN', 'count is slow', 'batchSize or maxTimeMS', 'query hits all shards'. SKIP: index key order/ESR -> mongodb-compound-index-design; explain, plan cache, hint -> mongodb-explain-plans-and-query-planner; fix-loop on one query -> deep-mongodb-mql-query-optimizer."
version: "1.0.0"
updated: "2026-10-19"
category: "research"
whenToUse:
  - "rewrite a query shape that cannot use an index"
  - "replace skip/limit with keyset pagination"
  - "fix a blocking in-memory sort"
  - "make a sharded query targeted instead of scatter-gather"
keywords: ["blocking sort", "in-memory sort", "keyset pagination", "skip limit", "regex anchor", "negation operators", "$in", "$or", "SORT_MERGE", "projection", "covered query", "countDocuments", "estimatedDocumentCount", "batchSize", "maxTimeMS", "scatter-gather", "shard key targeting"]
tags: ["mongodb", "query-optimization", "pagination", "sort", "sharding"]
provenance: "/dr · <local-path>"
---

# MongoDB Query Shape Optimization: Sort, Pagination, Operators and Sharded Targeting

## Overview

A MongoDB sort is index-backed when the plan walks an index in the requested order, so no SORT stage appears in explain and results stream. Otherwise the server runs a blocking (in-memory) SORT stage that must read every matching document before returning the first. Since 6.0, a sort over 100 MB spills to temporary disk files by default unless allowDiskUse is false. An index can serve a sort on its prefix, or on a non-prefix subset if the query has equality on every preceding key. Sort direction must match the index or its exact inverse. Multikey indexes and collation mismatches can force a blocking sort. The ESR guideline places equality, then sort, then range keys to avoid the SORT stage. A very selective range can justify ERS instead. With a limit, a blocking sort only keeps the top k. An index that supplies the order is still best.

MongoDB offers two pagination shapes. skip()+limit() maps to page numbers but the server scans and discards every skipped result, so cost grows with offset. Range (keyset) pagination filters on the last-seen sort value, using an index to seek straight to the next page, so cost stays flat at any depth. Keyset needs a unique sort key or tiebreaker (usually _id) and a matching compound index. It gives up random page access and total counts. Both approaches need a deterministic sort. The $or form of compound keyset filters had a planner bug for descending sorts, fixed in 3.4.2.

Some query operators cannot narrow index bounds, so they scan many index keys or whole collections. $regex only gets a tight index range when it is case-sensitive with a literal ^ prefix. Negation ($ne, $nin, $not, $exists:false) matches most of a collection and also matches documents missing the field. $where runs JavaScript on every document, cannot use indexes, and is deprecated from MongoDB 8.0 per secondary reporting. $expr with native operators avoids JavaScript, but its index use is limited to field-vs-constant comparisons. The fix is usually to rewrite as positive, selective, sargable predicates and confirm with explain().

$in on one field becomes a single index scan with multiple point bounds; $or becomes an OR (index union) plan with one IXSCAN per clause. MongoDB uses indexes for $or only if every clause is index-supported; one unindexed clause forces a COLLSCAN of the whole query. Same-field equality $or should be written as $in. With a sort, $in under 201 elements is expanded and merged by SORT_MERGE (equality-like under ESR); 201+ elements act like a range and block index sorting on later keys. Rooted $or with sort may pick a blocking SORT instead of SORT_MERGE (SERVER-19114, unresolved). Very large $or lists cost planner time (bound unionizing, fixed in 5.0) and a forum benchmark shows $or degrading far faster than $in as list size grows. Compound indexes are generally cheaper than unions of single-field indexes.

A covered query is answered entirely from an index with no document fetch. It needs every filter field and every returned field in one index, no equality-to-null predicate, and an explicit _id: 0 unless _id is indexed. Multikey indexes cover only queries that do not return the array field (and avoid $elemMatch). On sharded collections accessed via mongos, the index must also contain the shard key. A plain projection without full index coverage still fetches the document (FETCH then PROJECTION_SIMPLE); only PROJECTION_COVERED with totalDocsExamined 0 proves coverage. Projection without coverage still trims network and processing cost.

Three read-shape tools that look cheap but hide scans. estimatedDocumentCount() reads collection metadata (fast, approximate, no filter). countDocuments() is an exact $match + $group {$sum:1} aggregation, so it is only as fast as the index behind its filter; a covered count shows COUNT_SCAN with 0 docs examined. distinct() can be index-covered and uses DISTINCT_SCAN, but returns one BSON document (16 MB cap), may return orphans on shards, and is poor on dotted fields and time series; $group is the cursor-returning alternative. $sample uses a pseudo-random B-tree cursor only when it is the first stage, N is under 5% of the collection and the collection exceeds 100 documents; otherwise it does a random top-k sort, and the cursor path is not uniform. Sharded behaviour is a recurring caveat.

Three knobs shape how a query's results travel and where it runs. batchSize sets documents per server round trip: the first batch is the lesser of 101 documents or 16 MiB, later getMore batches are capped at 16 MiB, and mongos does not forward batchSize to shards. It changes round trips and memory, not what the application iterates. maxTimeMS is a server-side cumulative processing limit on a cursor, killed at interrupt points; it is not idle time and should be paired with a larger client socket timeout. Read preference chooses which replica member serves the read; every non-primary mode can return stale data, maxStalenessSeconds bounds that, and offloading reads to secondaries trades consistency and availability for capacity. For a query-shape topic these are the delivery-side levers once the index and sort are right.

In a sharded cluster, mongos targets a query at a subset of shards only when the filter contains the shard key or a leading prefix of a compound shard key. Otherwise it broadcasts to every shard, waits for all responses and merges them (scatter-gather). Broadcast cost grows with shard count and does not scale linearly. Sort and limit run per shard, but skip cannot be pushed down, so mongos fetches limit+skip from each shard and discards the excess. Hashed shard keys trade range-query targeting for even distribution. Including the shard key does not guarantee single-shard routing. Verify with explain (SHARD_MERGE vs SINGLE_SHARD, shards array). Aggregations over large data can benefit from parallel scatter-gather. The main shape levers are: put the shard key or prefix in the predicate, use shard-key-aware single-document writes, and choose the key to match dominant query shapes.

## Core Concepts

### Blocking Sort and Index-Backed Sort

- If MongoDB cannot use an index to obtain the sort order, the plan contains an in-memory (blocking) SORT stage; a sort served by an index has no SORT stage and generally performs better.[^c1-1][^c1-3][^c1-4]
- Starting in MongoDB 6.0, a pipeline stage or sort needing more than 100 MB of memory writes temporary files to disk by default; passing allowDiskUse: false restores the error-on-overflow behavior. Before 6.0 the sort failed unless allowDiskUse was set. verified-as-of: 2026-10-14[^c1-3][^c1-1]
- allowDiskUse has no effect on sorts answered by an index, or on blocking sorts that fit under 100 MB. (two sources)[^c1-3][^c1-1]

### Pagination Patterns (skip-limit vs range-keyset)

- skip() makes the server scan from the beginning of the input result set before returning results, so skip() gets slower as the offset increases.[^c2-1][^c2-3]
- When combining skip() with sort(), include a field with unique values (easiest: _id) in the sort. Duplicate sort values can yield inconsistent order across executions, especially while the collection receives writes.[^c2-1][^c2-3]

### Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists)

- For case-sensitive $regex, an index lets MongoDB match the regex against index values, which can beat a collection scan. If the regex is a prefix expression (starts with ^ or \A followed by simple symbols), MongoDB builds an index range from the prefix and scans only that range.[^c3-1][^c3-8]
- Tentative: Server-side JavaScript ($where, $function, $accumulator) is reported deprecated from MongoDB 8.0 with a server warning. The fetched $where and $function pages do not state this, so the claim rests on one search-result excerpt of the current manual and is unverified. verified-as-of: 2026-10-18[^c3-2]

### $in and $or Index Bounds and Union Plans

- MongoDB uses indexes to evaluate an $or only if every clause is supported by an index; if any clause lacks index support, the query performs a collection scan. Each $or clause can use its own index, so separate single-field indexes are recommended over a compound index for different-field clauses.[^c4-1][^c4-5]
- ESR guideline: $in used alone is an equality operator (a series of equality matches). With .sort(), an $in of fewer than 201 elements is expanded and merged in index sort order by a SORT_MERGE stage, behaving like equality; with 201 or more elements it is ordered like a range, subsequent index fields cannot be used for sorting, and it behaves like a range predicate. verified-as-of: 2026-10-14[^c4-2][^c4-1]

### Projection Optimization and Covered Query Design

- An index covers a query only if all query fields (including those needed internally, e.g. for sharding) and all returned fields are in the same index, and no query field is compared to null ({field: null} or {field: {$eq: null}} cannot be covered).[^c5-1][^c5-4]
- Multikey indexes can cover queries over non-array fields (the index tracks which fields make it multikey) but cannot cover queries over array fields. A multikey index covers a query only if the projection does not return the array field and the query does not use $elemMatch; to cover a query that filters on the array field, the index must be compound.[^c5-1][^c5-2]
- On sharded collections queried through mongos, an index covers a query only if it contains the shard key; the manual states an _id-only exception, but that exception is disputed (see disagreements). (two sources) verified-as-of: 2026-10-18[^c5-1][^c5-2]
- Not every index type can cover queries; hashed indexes cannot be multikey, and support must be checked on each index type's docs page. (two sources)[^c5-1][^c5-2]

### Count and Distinct and Sampling Optimization

- estimatedDocumentCount() takes no filter and returns the count from collection metadata, so it does not scan; on a view there is no metadata and it runs the view pipeline, so it is not fast there.[^c6-1][^c6-5]
- countDocuments() does not use metadata. It wraps aggregate([{$match: query}, {$group: {_id: null, n: {$sum: 1}}}]), giving an exact count even after unclean shutdown or with orphans, and its cost therefore follows the filter's index support.[^c6-2][^c6-5]
- distinct operations can use indexes and can be covered by them. For array fields distinct treats each array element as a separate value. On sharded clusters distinct may return orphaned documents; on time series collections it cannot use indexes efficiently and the docs say to use $group; in transactions on sharded collections distinct is not allowed and $group must be used.[^c6-3][^c6-8]
- $sample uses a pseudo-random cursor only if it is the first pipeline stage, N is under 5% of the collection (threshold not configurable), and the collection has more than 100 documents. Otherwise it reads all input and does a top-k random sort, which is subject to sort memory limits and can spill to disk. On a view $sample is never first, so it always scans.[^c6-4][^c6-6]

### Cursor and Read-Path Tuning (batchSize and maxTimeMS and read preference)

- By default the first batch of a find or aggregate is the lesser of 101 documents or 16 MiB; later getMore batches have no document-count default and are capped at 16 MiB. A set batchSize can only lower the limit below 16 MiB, never raise it.[^c7-1][^c7-2][^c7-5]
- In a sharded cluster mongos does not forward batchSize to the shards, and later getMore batches return up to 16 MiB per batch regardless of the configured batchSize. (two sources) verified-as-of: 2026-10-14[^c7-1][^c7-2]
- batchSize changes only how many documents each network round trip fetches. Driver iteration (next, hasNext, for-await) still yields one document at a time from the fetched batch. With batchSize 1 and 1000 results the driver issues 999 getMore calls. (two sources)[^c7-5][^c7-6]
- maxTimeMS is a cumulative server-side processing limit for a cursor. The server terminates the operation like killOp, and only at an interrupt point. It is unrelated to idle time (noCursorTimeout). Client-to-server latency is not counted, but in a sharded cluster mongos-to-mongod latency is.[^c7-4][^c7-2]
- On getMore, maxTimeMS applies per call. For a tailable awaitData cursor it equals maxAwaitTimeMS (how long to wait for new documents). For a non-tailable cursor a timeout raises an error. (two sources)[^c7-2][^c7-4]
- Every read preference mode except primary may return stale data because secondaries replicate asynchronously. maxStalenessSeconds lets the client skip secondaries whose estimated lag is too high. The modes secondary and secondaryPreferred compare lag with the primary; primaryPreferred and nearest compare with the freshest secondary when there is no primary.[^c7-3][^c7-7]

### Sharded Query Targeting and Scatter-Gather

- mongos performs a targeted operation when the query includes the shard key or a prefix of a compound shard key. For key {a:1,b:1,c:1} the usable prefixes are {a:1} and {a:1,b:1}. A query on {b:1} alone is not a prefix and broadcasts.[^c8-1][^c8-5]
- A query without the shard key is broadcast to all shards for the collection. mongos must query every shard, wait for all responses, then merge. MongoDB calls these scatter/gather queries and says they can be long running. Docs say to favor targeted operations over broadcast ones.[^c8-1][^c8-2]
- Queries that involve multiple shards per request are less efficient and do not scale linearly when shards are added. A Netdata guide estimates a scatter-gather query on a 50-shard cluster can use up to 50x the CPU, memory and I/O of a targeted query. The 50x figure is an unbenchmarked estimate, not a measured number. (two sources)[^c8-2][^c8-5]
- Including the shard key does not guarantee a single-shard route. Depending on data distribution and query selectivity, mongos may still broadcast (for example a range predicate spanning chunks on several shards).[^c8-1][^c8-3]
- Broadcast cost depends on overall cluster load, network latency, individual shard load and documents returned per shard. (two sources)[^c8-1][^c8-5]

## Tools & Frameworks

- Check for a blocking sort with explain(): a SORT stage in the plan means a blocking sort; no SORT stage means the index supplies the order. Use hint() when testing candidate indexes.[^c1-2][^c1-4][^c1-3] _(Blocking Sort and Index-Backed Sort)_
- Tentative: Atlas Search ($search) paginates with its own token-based searchAfter/searchBefore, and should not be mixed with _id cursors. verified-as-of: 2026-01-07[^c2-3] _(Pagination Patterns (skip-limit vs range-keyset))_
- Server-side scripting can be turned off (security.javascriptEnabled=false or --noscripting) when no $where, $function, $accumulator or mapReduce is used. This removes the anti-pattern at the configuration level. (two sources)[^c3-2][^c3-6] _(Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists))_
- In explain output an index-union $or appears as an OR stage (often under SUBPLAN) with one IXSCAN child per clause, usually under a FETCH; two IXSCAN children confirm both indexes are used. (two sources)[^c4-5][^c4-6] _($in and $or Index Bounds and Union Plans)_
- To confirm coverage, read explain("executionStats"): look for IXSCAN directly under PROJECTION_COVERED with no FETCH and totalDocsExamined: 0. Flexible schema means MongoDB cannot assume indexed fields exist in all documents, so any projection not fully satisfied by index keys keeps FETCH.[^c5-4][^c5-1] _(Projection Optimization and Covered Query Design)_
- Too large a batchSize makes the cursor allocate more resources than needed; too small adds network round trips. A batchSize of 0 opens the cursor and returns no documents in the first batch. Third-party sizing ranges (50-200 for large documents or memory limits, 500-2000 for small documents and bulk throughput) are heuristics, not vendor guidance. (two sources)[^c7-1][^c7-6] _(Cursor and Read-Path Tuning (batchSize and maxTimeMS and read preference))_
- To detect a broadcast: run explain('executionStats') through mongos and check whether the shards array lists every shard or the top stage is SHARD_MERGE. Also check the mongos slow query log for nShards equal to total shard count. A targeted query shows one or a few shards (SINGLE_SHARD for one). (two sources)[^c8-5][^c8-1] _(Sharded Query Targeting and Scatter-Gather)_

## Methodology

- ERS exception: if the range predicate is very selective, MongoDB's docs say to place the range before the sort keys so fewer documents are sorted, accepting an in-memory sort of the reduced set. (two sources)[^c1-2][^c1-1] _(Blocking Sort and Index-Backed Sort)_
- The 10,000-document rule of thumb for preferring keyset over skip is a practitioner heuristic, not a measured benchmark; OpenReplay gives no timings. The only quantified offset-vs-seek numbers found are from Postgres (LIMIT 100 ~0.06 ms vs OFFSET 5,000,000 ~758 ms), which show the shape of the effect but not MongoDB's magnitude. (two sources)[^c2-3][^c2-2] _(Pagination Patterns (skip-limit vs range-keyset))_
- Tentative: A filtered count is covered when an index holds all filter fields; verify with explain('executionStats') showing a COUNT_SCAN stage and totalDocsExamined: 0.[^c6-5] _(Count and Distinct and Sampling Optimization)_
- MongoDB's shard-key selection guidance lists query isolation as a criterion: a good shard key appears in most queries so mongos routes to the relevant shards only. (two sources)[^c8-2][^c8-1] _(Sharded Query Targeting and Scatter-Gather)_

## Practical Patterns

- A compound index supports a sort on all its keys or on a prefix, with sort keys in index order. Directions must match the index pattern or its exact inverse: {a:1,b:-1} supports {a:1,b:-1} and {a:-1,b:1}, but not {a:1,b:1} or {a:-1,b:-1}.[^c1-1][^c1-2] _(Blocking Sort and Index-Backed Sort)_
- An index can serve a sort on a non-prefix subset of its keys only if the query has equality conditions on all index keys that precede the sort keys. With index {a,b,c,d}, find({a:{$gt:2}}).sort({c:1}) does not use the index efficiently.[^c1-1][^c1-2] _(Blocking Sort and Index-Backed Sort)_
- ESR guideline: put equality keys first, then sort keys, then range keys, so the index delivers sorted output without an in-memory sort. Sorting after equality also makes the sort non-blocking.[^c1-2][^c1-4] _(Blocking Sort and Index-Backed Sort)_
- ESR classification: $ne, $nin and $regex are range operators, not equality. $in alone is equality. With a sort, $in under 201 elements expands and merges via a SORT_MERGE stage (acts like equality); at 201 or more it behaves like a range and later index keys cannot supply the sort. The 201 threshold is documented as not guaranteed across versions. (two sources) verified-as-of: 2026-10-14[^c1-2][^c1-1] _(Blocking Sort and Index-Backed Sort)_
- When a sort is followed by a limit and no index supplies the order, the server keeps only the top k rows (about skip+limit) in sorter memory rather than all matches. It still examines every matching document, so an index-provided order remains the strongest option. (two sources)[^c1-5][^c1-3] _(Blocking Sort and Index-Backed Sort)_
- MongoDB's documented range-query pagination: pick a field such as _id that changes consistently over time and has a unique index, filter with $lt (descending) or $gt (ascending), sort on it, and store the last-seen value for the next query. Range queries use indexes to avoid scanning unwanted documents.[^c2-1][^c2-3] _(Pagination Patterns (skip-limit vs range-keyset))_
- For a non-unique sort field such as createdAt, keyset pagination needs a compound filter: $or of {createdAt < last} and {createdAt == last, _id < lastId}, sorted by {createdAt:-1,_id:-1}, backed by an index with the same fields and directions. (two sources)[^c2-3][^c2-4] _(Pagination Patterns (skip-limit vs range-keyset))_
- /^a/, /^a.*/ and /^a.*$/ match equivalent strings and all can use an index, but /^a.*/ and /^a.*$/ are slower. /^a/ can stop scanning after the prefix. Write the bare anchored prefix, not a trailing .*. (two sources)[^c3-1][^c3-8] _(Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists))_
- $expr with non-JavaScript aggregation operators is faster than $where because it runs no JavaScript. If custom JavaScript is unavoidable, $function inside $expr is preferred over $where. $where does not work inside $elemMatch (top-level documents only).[^c3-2][^c3-6] _(Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists))_
- $exists:false cannot use a sparse index (requires a COLLSCAN) and requires a FETCH on a non-sparse index. $exists:true is most efficient on a sparse index (exact match, no FETCH). To exclude null and missing values, {field:{$ne:null}} avoids needing a sparse index. (two sources)[^c3-5][^c3-7] _(Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists))_
- Tentative: Rewrite negation as a positive predicate where the allowed set is small or known: use $in over the wanted values instead of $nin over excluded values, and add an indexable equality or range predicate so the negation only filters a small residue.[^c3-7] _(Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists))_
- When $or clauses are equality checks on the same field, the MongoDB manual says to use $in instead; $in runs one IXSCAN in total, whereas $or runs one IXSCAN per condition.[^c4-1][^c4-6][^c4-5] _($in and $or Index Bounds and Union Plans)_
- Index placement guidance: put $in earlier in the compound index (equality position) if it typically has small arrays; put it where a range predicate would go if it typically has large arrays. The docs state the 201-element threshold is not guaranteed to stay the same across MongoDB versions, so confirm with explain on the target version. (two sources) verified-as-of: 2026-10-14[^c4-2][^c4-1] _($in and $or Index Bounds and Union Plans)_
- A compound index often outperforms a union of single-field indexes for an $or with shared extra filters, because a union must merge and deduplicate results. This is asserted by a blog and a forum reply without a controlled benchmark. (two sources)[^c4-5][^c4-6] _($in and $or Index Bounds and Union Plans)_
- If the index does not include _id, the projection must explicitly set _id: 0, otherwise the query is not covered. Excluding _id alone (without listing only indexed fields) leaves FETCH then PROJECTION_SIMPLE.[^c5-1][^c5-4] _(Projection Optimization and Covered Query Design)_
- Even when a query cannot be covered, projecting only needed fields reduces network traffic and processing time; coverage additionally removes document reads, so a covered design should index filter fields first (ESR order) and then projected-only fields. (two sources)[^c5-1][^c5-4] _(Projection Optimization and Covered Query Design)_
- Tentative: For counts read many times per second, a counter document maintained with $inc avoids repeated counting, at the cost of drift (reconcile periodically with countDocuments()) and extra write logic.[^c6-5] _(Count and Distinct and Sampling Optimization)_
- An aggregation starting with $sort then $group using $first or $last can run as a DISTINCT_SCAN (loose index scan) that reads one index entry/document per group, provided a matching index exists and the group fields are not multikey; the author's 10-group example examined 10 documents versus about 200,000 index rows for PostgreSQL DISTINCT ON. (two sources) verified-as-of: 2025-12-03[^c6-7][^c6-3] _(Count and Distinct and Sampling Optimization)_
- Sort and limit behave differently in the router. Unsorted results come from a round-robin over shard cursors. With limit(), mongos passes the limit to each shard and re-applies it to the merged result. With skip(), mongos cannot push the skip down: it passes limit+skip to the shards, then skips while assembling results. Deep skip on a sharded collection therefore costs more.[^c8-1][^c8-5] _(Sharded Query Targeting and Scatter-Gather)_
- Tentative: A $limit caps the final output across shards, not per shard. A forum participant states mongos can still receive up to N documents from each shard (up to shards*N total) because it cannot know the global top N before merging sorted per-shard streams. The thread has no accepted answer; the two repliers differ on intermediate transfer.[^c8-4] _(Sharded Query Targeting and Scatter-Gather)_
- updateOne(), replaceOne() and deleteOne() must include the shard key or _id; otherwise MongoDB returns an error instead of broadcasting. updateMany() and deleteMany() are broadcast unless the query specifies the full shard key. Multi-update operations are always broadcast.[^c8-1][^c8-5] _(Sharded Query Targeting and Scatter-Gather)_
- Scatter-gather is not always bad. For aggregation queries over a large amount of data, MongoDB docs say scatter-gather lets the query run in parallel on all shards and can be useful. The warning targets frequent, latency-sensitive queries. (two sources)[^c8-2][^c8-1] _(Sharded Query Targeting and Scatter-Gather)_

## Anti-Patterns

- Sorting on an indexed array field (multikey index) yields an in-memory SORT stage unless the index bounds for all sort fields are [MinKey, MaxKey] and no multikey field bounds share a path prefix with the sort pattern. (two sources)[^c1-1][^c1-3] _(Blocking Sort and Index-Backed Sort)_
- To use an index for string sorting, the operation must specify the same collation as the index; a different collation means the index cannot supply the string order and a blocking sort results. (two sources)[^c1-1][^c1-2] _(Blocking Sort and Index-Backed Sort)_
- Keyset pagination cannot jump to an arbitrary page, since reaching page N generally means visiting earlier pages, and it does not easily return total counts. It suits infinite scroll and next/previous navigation. Skip-limit suits shallow paging, small datasets and jump-to-page UIs.[^c2-3][^c2-2] _(Pagination Patterns (skip-limit vs range-keyset))_
- Offset pagination is inconsistent under concurrent writes: inserts or deletes between requests cause duplicate or missing items. Keyset is more stable for changes before the current page but not immune; mutable sort fields can still cause duplicates or misses.[^c2-2][^c2-3] _(Pagination Patterns (skip-limit vs range-keyset))_
- Case-insensitive indexes (collation) do not help $regex, because $regex is not collation-aware. The case-insensitive (i) option therefore forfeits efficient prefix bounds. The wording 'cannot use any index' is stronger than the docs; the safer reading is 'no efficient bounds', and explain() decides. (two sources)[^c3-1][^c3-8] _(Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists))_
- Unanchored $regex (no literal ^ prefix, e.g. /^.*laptop/ or /laptop/) cannot build a range. With an index it may still run a full IXSCAN over every key rather than a COLLSCAN; without an index it scans the collection. Either way cost grows with collection size. (two sources)[^c3-1][^c3-8] _(Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists))_
- Tentative: The *UCP regex option makes queries slower than the same query without it, because it needs a multistage table lookup to match.[^c3-1] _(Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists))_
- $where evaluates JavaScript for each document and cannot take advantage of indexes. Alone it requires a collection scan. MongoDB evaluates the non-$where predicates first, and those can use an index, so always pair $where with at least one indexable standard predicate.[^c3-2][^c3-6] _(Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists))_
- Tentative: Documented $expr index limits (in the $lookup subpipeline section): only $eq, $lt, $lte, $gt and $gte can use an index, and only for field-vs-constant comparisons. $a vs $b cannot use an index. Multikey, partial and sparse indexes are not used there. The page documents this only for $lookup; the general find() case is not stated in the fetched text.[^c3-3] _(Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists))_
- $ne, $nin and $not match documents that lack the field. {$not:{$gt:180}} differs from {$lte:180}, which returns only documents where the field exists. Negation therefore returns a large share of the collection and is poorly selective. (two sources)[^c3-4][^c3-7] _(Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists))_
- Tentative: Blog advice that $text index handles arbitrary substring search is wrong: $text matches whole stemmed words, not substrings. Mid-string search needs a different structure such as an n-gram or Atlas Search index. The same blog's benchmark numbers (2,300 ms vs 1 ms) carry no methodology and should not be cited.[^c3-8] _(Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists))_
- Tentative: A rooted $or (single top-level $or) with a sort may choose a blocking SORT over a faster SORT_MERGE because the subplanner picks the locally best plan per clause without considering sort order. A SORT stage instead of SORT_MERGE in explain('queryPlanner') diagnoses it. Ticket SERVER-19114 is Backlog/Unresolved, last updated 2025-03-26. verified-as-of: 2025-03-26[^c4-3] _($in and $or Index Bounds and Union Plans)_
- Tentative: A community benchmark (July 2022) measured $or rising from 52 ms at 1,000 items to 11,684 ms at 20,000, while $in rose from 45 ms to 236 ms; the $or test had no index, so the comparison is unequal and is only directional evidence that $in scales better.[^c4-6] _($in and $or Index Bounds and Union Plans)_
- Tentative: If an $or includes a $text clause, every clause must be index-supported, otherwise the query errors; a $near/$nearSphere clause means $or cannot contain any other clauses.[^c4-1] _($in and $or Index Bounds and Union Plans)_
- Adding an array field to a compound index to 'complete' coverage can backfire: in a forum case the index became multikey, the plan fell back to PROJECTION_SIMPLE (not covered), and the poster measured 100 s vs 6 s versus the index without the array field (5.1M docs, MongoDB 4.0.10). (two sources)[^c5-3][^c5-2] _(Projection Optimization and Covered Query Design)_
- countDocuments() rejects $where, $near and $nearSphere in its query; the documented substitutes are $expr and $geoWithin with $center / $centerSphere. Inside a transaction, both countDocuments() and estimatedDocumentCount() do not filter out uncommitted multi-document transactions. (two sources)[^c6-2][^c6-1] _(Count and Distinct and Sampling Optimization)_
- Tentative: distinct on a dotted field cannot be covered (SERVER-2104), and SERVER-23582 (closed 2016-05-17) reported the planner choosing a non-multikey DISTINCT_SCAN with a FETCH that cost more than a collection scan; check explain on dotted-field distincts. verified-as-of: 2016-05-17[^c6-8] _(Count and Distinct and Sampling Optimization)_
- The pseudo-random cursor walks the B-tree and is not guaranteed uniform; skew is likelier with unbalanced trees, many deleted documents, or many documents invisible to the transaction. For a uniform sample put another stage (such as $match) before $sample or use N above 5%, accepting the scan. (two sources)[^c6-4][^c6-9] _(Count and Distinct and Sampling Optimization)_
- Tentative: If maxTimeMS equals the driver's client socket timeout, the driver closes the connection first and the server can never return MaxTimeMSExpired, causing connection churn. Set the client timeout above maxTimeMS.[^c7-8] _(Cursor and Read-Path Tuning (batchSize and maxTimeMS and read preference))_
- Hashed sharding gives more even distribution at the cost of targeting. Post-hash, documents with close key values are unlikely to share a shard, so mongos is more likely to broadcast a ranged query. Equality matches can still be targeted to a single shard. The docs say 'more likely', not 'always'.[^c8-3][^c8-5] _(Sharded Query Targeting and Scatter-Gather)_

## Troubleshooting

- Tentative: Tencent Cloud reports that placing a range field ahead of the sort field forced an in-memory sort, and that reordering to ESR cut an order query from second-level latency to about 10 ms and a report from timeout to 200 ms. These are single-vendor anecdotes, not benchmarks.[^c1-4] _(Blocking Sort and Index-Backed Sort)_
- Tentative: SERVER-24027 (Core Server, fixed in 3.4.2/3.5.2, closed Jan 2017): for $or keyset pagination sorted descending on a compound key, the planner did not reverse an index scan to get SORT_MERGE and fell back to an in-memory sort. The pre-fix workaround was a descending index plus hint(). On pre-3.4.2 servers, check explain() for SORT or a blocking sort.[^c2-4] _(Pagination Patterns (skip-limit vs range-keyset))_
- Tentative: A low-selectivity $nin on an indexed array field can be slower with the index than without it. In one forum report, the indexed plan examined about 3 million index keys and took about 1,962 ms; the COLLSCAN took about 107 ms. A document matches $nin only if none of its array keys match. The reporter forced a collection scan with hint({$natural:1}). Single anecdote, not a benchmark.[^c3-7] _(Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists))_
- Tentative: Workarounds for the rooted-$or SORT problem: hint one index that serves all clauses to force a merge sort; use an index filter (not persistent across restarts, set per node); or ensure each clause has an index providing the sort order and none offers an index requiring a blocking sort.[^c4-3] _($in and $or Index Bounds and Union Plans)_
- Tentative: Very large $or lists were slow in the planner because IndexBoundsBuilder::unionize() merged clause bounds one at a time (roughly quadratic); SERVER-34012 was fixed in 5.0.0-rc0. The reporter's diagnostic patch cut a 20,000-clause query from ~40 s to ~400 ms; the official fix's gain is not stated. verified-as-of: 2026-10-18[^c4-4] _($in and $or Index Bounds and Union Plans)_
- Tentative: Older servers label covered plans PROJECTION rather than PROJECTION_COVERED (observed on 4.0 vs 5.0.13), so totalDocsExamined: 0 is the version-robust coverage check. verified-as-of: 2022-11-22[^c5-3] _(Projection Optimization and Covered Query Design)_
- estimatedDocumentCount() can be inaccurate after an unclean shutdown (drift depends on writes since the last checkpoint, usually 60 s) and on a sharded cluster does not filter orphaned documents; running validate on each collection restores the count statistic. (two sources)[^c6-1][^c6-5] _(Count and Distinct and Sampling Optimization)_
- On a sharded cluster each shard samples independently and mongos samples the merged result. SERVER-68623 (closed Won't Do, 2022-09-28) reports each shard gets the full requested size and so picks random sort instead of the cursor, because a mongod does not know the cluster-wide document count; the 5% rule is documented only for mongod behaviour. (two sources) verified-as-of: 2022-09-28[^c6-4][^c6-9] _(Count and Distinct and Sampling Optimization)_
- Server sessions idle for 30 minutes expire and the server may kill their cursors, including cursors with noCursorTimeout or a maxTimeMS over 30 minutes. A very large maxTimeMS therefore does not keep a cursor alive. (two sources) verified-as-of: 2026-10-14[^c7-4][^c7-2] _(Cursor and Read-Path Tuning (batchSize and maxTimeMS and read preference))_
- Tentative: From MongoDB 8.2, long-running secondary reads in a sharded cluster can be terminated before orphaned-document cleanup after a chunk migration; the terminateSecondaryReadsOnOrphanCleanup parameter controls this. Long scans on secondaries should expect and retry this. verified-as-of: 2026-10-14[^c7-3] _(Cursor and Read-Path Tuning (batchSize and maxTimeMS and read preference))_
- Tentative: Historic bug: in MongoDB 3.0.0-3.0.3, long-running secondary reads did not yield and could stall replication, growing lag and stale reads (SERVER-18190, fixed in 3.0.4). Heavy secondary reads still compete with oplog application for resources.[^c7-7] _(Cursor and Read-Path Tuning (batchSize and maxTimeMS and read preference))_
- Tentative: Mitigations named by the Netdata guide: put the shard key or leading prefix in predicates, set maxTimeMS on unavoidable scatter-gather queries, avoid deep skip() pagination, and re-evaluate the shard key against dominant query shapes. A low-cardinality key (e.g. continent, at most seven chunks) limits scaling regardless of shard count. Single-vendor-blog advice; not independently verified.[^c8-5] _(Sharded Query Targeting and Scatter-Gather)_

## Disagreements & Open Questions

- Disagreement (Blocking Sort and Index-Backed Sort): Tencent Cloud's guidance says in-memory sorting is prohibited and over-limit sorts fail with an error. MongoDB 6.0+ documents default spill-to-disk, so the Tencent behavior is version- or product-specific.[^c1-4][^c1-3]
- Disagreement (Blocking Sort and Index-Backed Sort): ESR says sort before range to avoid a blocking sort, but MongoDB's own guideline also says a very selective range may go first (ERS). Neither source gives a numeric selectivity threshold.[^c1-2]
- Open (Blocking Sort and Index-Backed Sort): No source gives a quantitative selectivity cutoff for choosing ERS over ESR.
- Open (Blocking Sort and Index-Backed Sort): The MongoDB Jira ticket DOCS-16663 (large $in ordering under ESR) could not be read because the fetch returned only a login page; the 201-element $in claim rests on the ESR doc alone.
- Open (Blocking Sort and Index-Backed Sort): Whether the 100 MB spill threshold and 201-element $in threshold hold on the latest server release was not checked against release notes.
- Open (Blocking Sort and Index-Backed Sort): Independent (non-MongoDB, non-vendor) benchmarks comparing blocking and index-backed sort cost were not found.
- Disagreement (Pagination Patterns (skip-limit vs range-keyset)): Offset thresholds differ: OpenReplay suggests skip is fine under ~10,000 documents; the MongoDB manual gives no threshold, only that cost grows with offset.[^c2-3][^c2-1]
- Open (Pagination Patterns (skip-limit vs range-keyset)): Whether current servers (8.x) execute the $or keyset filter as efficiently as a tuple comparison; no source covers $expr/array tuple comparison.
- Open (Pagination Patterns (skip-limit vs range-keyset)): How to keyset-paginate on a mutable sort field without duplicates or misses.
- Open (Pagination Patterns (skip-limit vs range-keyset)): No MongoDB-specific benchmark of skip vs range was found.
- Disagreement (Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists)): Blog says case-insensitive or unanchored regex 'cannot use indexes' or 'disables index usage'. MongoDB docs say only that collation indexes do not help $regex and that non-prefix patterns lose the range optimization; an IXSCAN over all keys remains possible.[^c3-1][^c3-8]
- Open (Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists)): Only two organisations (mongodb.com, oneuptime.com) were deep-read; the depth contract's third independent source was not met.
- Open (Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists)): Whether the 8.0 deprecation of $where/$function/$accumulator is stated in the current manual; the fetched pages did not say so.
- Open (Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists)): Whether $expr with $eq/$gt etc. uses indexes in plain find()/$match (outside $lookup) and in which versions.
- Open (Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists)): Exact explain() index bounds for case-insensitive anchored regex on the current server version.
- Disagreement ($in and $or Index Bounds and Union Plans): The oneuptime blog says two IXSCANs mean indexes are used 'in parallel'; the OR stage typically reads children sequentially, so the wording is doubtful. The blog's compound-vs-union comparison also uses a query with no $or and no benchmark.[^c4-5]
- Disagreement ($in and $or Index Bounds and Union Plans): The $or manual page says sorted $or queries can use indexes that support the clauses, but SERVER-19114 shows a rooted $or with sort can still pick a blocking SORT.[^c4-1][^c4-3]
- Open ($in and $or Index Bounds and Union Plans): Only two organisations are represented (MongoDB: docs, Jira, community forum; oneuptime blog); no third independent vendor source was found, so claims rest mostly on MongoDB's own material.
- Open ($in and $or Index Bounds and Union Plans): Whether the 201-element $in threshold still holds on current server versions; docs say it is not guaranteed.
- Open ($in and $or Index Bounds and Union Plans): Whether SERVER-19114 behaviour persists on 8.x; the ticket is unresolved but its version claim is from 2020.
- Open ($in and $or Index Bounds and Union Plans): Real cost of OR-stage deduplication versus a single compound IXSCAN; no controlled benchmark found.
- Open ($in and $or Index Bounds and Union Plans): Forum report (5.0.6) of an $or clause being slower once indexed was not verified.
- Disagreement (Projection Optimization and Covered Query Design): Some blogs claim multikey indexes never cover queries or that no indexed field may be an array; the manual narrows this to 'cannot cover queries over array fields' and allows coverage when the array field is not returned. Franck Pachot's blog shows a single-key-entry query on a multikey index still planning FETCH/PROJECTION_SIMPLE in its example, which is narrower than the manual's wording.[^c5-2][^c5-4]
- Open (Projection Optimization and Covered Query Design): Whether the manual's _id-index exception for covered queries on mongos is real: search snippet of Jira DOCS-14205 suggests _id queries actually FETCH via IDHACK to filter orphans; SERVER-14304 historically disabled covered _id projections on sharded connections. Jira pages needed login and could not be read.
- Open (Projection Optimization and Covered Query Design): Current-version behavior of covered queries on multikey index when only a single-key entry is queried (blog example appears to show FETCH).
- Disagreement (Count and Distinct and Sampling Optimization): A third-party blog (search snippet) describes the 5% rule without the first-stage and more-than-100-documents conditions; the official $sample page lists all three conditions.[^c6-6][^c6-4]
- Open (Count and Distinct and Sampling Optimization): The 16 MB distinct result cap is reported by forum/Jira search snippets (DOCS-9120, SERVER-94406, community threads) but was not confirmed on the fetched distinct manual page, so no claim is made.
- Open (Count and Distinct and Sampling Optimization): Whether SERVER-68623 sharded $sample behaviour still holds on current releases is unverified; the ticket was closed Won't Do in 2022.
- Open (Count and Distinct and Sampling Optimization): The dev.to DISTINCT_SCAN author writes for MongoDB, so it is not fully independent of the vendor docs. All fetched Jira and docs sources share one organisation; only the OneUptime blog is a separate one.
- Open (Count and Distinct and Sampling Optimization): No benchmark numbers for countDocuments() versus estimatedDocumentCount() on large collections were found.
- Disagreement (Cursor and Read-Path Tuning (batchSize and maxTimeMS and read preference)): Older docs and the forum thread describe the initial batch as exactly 101 documents with no byte cap; the current mongosh reference says the lesser of 101 documents or 16 MiB. Older pages also say 16 megabytes rather than MiB.[^c7-5][^c7-1]
- Disagreement (Cursor and Read-Path Tuning (batchSize and maxTimeMS and read preference)): A web search summary called DRIVERS-2971 open; the fetched page shows it Closed as a Duplicate of DRIVERS-2884 (resolved 2025-06-27).[^c7-8]
- Open (Cursor and Read-Path Tuning (batchSize and maxTimeMS and read preference)): Only two organisations are represented: MongoDB (docs, forum, Jira) and OneUptime (blog). No independent vendor or engineering postmortem on batchSize or read-preference tuning was found.
- Open (Cursor and Read-Path Tuning (batchSize and maxTimeMS and read preference)): Whether current mongos forwards maxTimeMS to shards on getMore: SERVER-21218 (3.2-era) reported it did not and was not read; the current docs only say mongos-to-mongod latency counts.
- Open (Cursor and Read-Path Tuning (batchSize and maxTimeMS and read preference)): Whether the 'read from secondary to scale reads' advice in older (4.0) docs is still stated in current docs; the current page was not checked for it.
- Open (Cursor and Read-Path Tuning (batchSize and maxTimeMS and read preference)): The oneuptime tuning ranges are unsourced heuristics.
- Disagreement (Sharded Query Targeting and Scatter-Gather): Forum repliers disagree on whether each shard returns up to N documents for a global $limit N: one says the limit caps output across shards; the other says mongos can receive up to N from each shard before merging. The manual says only that mongos passes the limit to shards and re-applies it.[^c8-4][^c8-1]
- Open (Sharded Query Targeting and Scatter-Gather): No measured benchmark found for scatter-gather vs targeted latency; the 50x figure is an estimate from one blog.
- Open (Sharded Query Targeting and Scatter-Gather): Whether a sort on a non-shard-key field is merged with a streaming k-way merge on mongos (SHARD_MERGE with sort) in current versions was not confirmed from primary docs.
- Open (Sharded Query Targeting and Scatter-Gather): Jira SERVER-46487 (mongos CPU iterating chunk boundaries during scatter-gather with skewed chunks) was seen only in search snippets and not fetched.

## References

### Blocking Sort and Index-Backed Sort

[^c1-1]: https://www.mongodb.com/docs/manual/tutorial/sort-results-with-indexes/ — Use Indexes to Sort Query Results (docs)
[^c1-2]: https://www.mongodb.com/docs/manual/tutorial/equality-sort-range-guideline/ — The ESR (Equality, Sort, Range) Guideline (docs)
[^c1-3]: https://www.mongodb.com/docs/manual/reference/method/cursor.allowDiskUse/ — cursor.allowDiskUse() (docs)
[^c1-4]: https://intl.cloud.tencent.com/document/product/240/80772 — Tencent Cloud MongoDB sort/ESR index guidance (docs)
[^c1-5]: https://codemia.io/knowledge-hub/path/how_does_top-k_sort_algorithm_work_in_mongodb — How does top-k sort algorithm work in MongoDB (blog)

### Pagination Patterns (skip-limit vs range-keyset)

[^c2-1]: https://www.mongodb.com/docs/v8.2/reference/method/cursor.skip/ — cursor.skip() MongoDB manual v8.2 (docs)
[^c2-2]: https://begriffs.com/posts/2016-03-30-five-ways-to-paginate.html — Five ways to paginate in Postgres (blog)
[^c2-3]: https://blog.openreplay.com/pagination-patterns-mongodb/ — Pagination Patterns in MongoDB (OpenReplay) (blog)
[^c2-4]: https://jira.mongodb.org/browse/SERVER-24027 — SERVER-24027 planner reverse scan SORT_MERGE (forum)

### Query Operator Anti-Patterns ($regex and negation and $where and $expr and $exists)

[^c3-1]: https://www.mongodb.com/docs/current/reference/operator/query/regex/ — $regex (query predicate operator) (docs)
[^c3-2]: https://www.mongodb.com/docs/manual/reference/operator/query/where.md — $where (query predicate operator) (docs)
[^c3-3]: https://www.mongodb.com/docs/manual/reference/operator/query/expr.md — $expr (query predicate operator) (docs)
[^c3-4]: https://www.mongodb.com/docs/manual/reference/operator/query/not/ — $not (query predicate operator) (docs)
[^c3-5]: https://www.mongodb.com/docs/manual/reference/operator/query/exists/ — $exists (query predicate operator) (docs)
[^c3-6]: https://www.mongodb.com/docs/manual/reference/operator/aggregation/function/ — $function (aggregation operator) (docs)
[^c3-7]: https://www.mongodb.com/community/forums/t/index-is-slower-when-using-nin/112757 — Index is slower when using $nin (forum)
[^c3-8]: https://oneuptime.com/blog/post/2026-03-31-mongodb-avoid-regex-without-anchors/markdown — How to Avoid Using Regex Without Anchors for Queries in MongoDB (blog)

### $in and $or Index Bounds and Union Plans

[^c4-1]: https://www.mongodb.com/docs/manual/reference/operator/query/or/ — $or (query predicate operator) (docs)
[^c4-2]: https://www.mongodb.com/docs/manual/tutorial/equality-sort-range-guideline/ — The ESR (Equality, Sort, Range) Guideline (docs)
[^c4-3]: https://jira.mongodb.org/browse/SERVER-19114 — SERVER-19114 Rooted $or with sort may select SORT over SORT_MERGE (forum)
[^c4-4]: https://jira.mongodb.org/browse/SERVER-34012 — SERVER-34012 Planner union of index bounds slow for large $or (forum)
[^c4-5]: https://oneuptime.com/blog/post/2026-03-31-mongodb-index-for-or-queries/view — How to Index for OR Queries in MongoDB (blog)
[^c4-6]: https://mongodb.com/community/forums/t/performance-of-or-vs-in/175513 — Performance of $or vs $in (forum)

### Projection Optimization and Covered Query Design

[^c5-1]: https://www.mongodb.com/docs/manual/core/query-optimization/ — MongoDB manual: Query optimization (docs)
[^c5-2]: https://www.mongodb.com/docs/manual/core/indexes/index-types/index-multikey/ — MongoDB manual: Multikey indexes (docs)
[^c5-3]: https://mongodb.com/community/forums/t/adding-the-projected-fields-to-compound-index-to-create-covered-query-doesnt-improve-performance/199267 — MongoDB forum: covered index doesn't improve performance (forum)
[^c5-4]: https://dev.to/franckpachot/index-only-scan-on-json-documents-with-covering-and-multi-key-indexes-in-mongodb-53h4 — Index-only scan on JSON documents with covering and multi-key indexes (blog)

### Count and Distinct and Sampling Optimization

[^c6-1]: https://www.mongodb.com/docs/manual/reference/method/db.collection.estimatedDocumentCount/ — MongoDB manual: estimatedDocumentCount() (docs)
[^c6-2]: https://www.mongodb.com/docs/manual/reference/method/db.collection.countDocuments/ — MongoDB manual: countDocuments() (docs)
[^c6-3]: https://www.mongodb.com/docs/manual/reference/command/distinct/ — MongoDB manual: distinct command (docs)
[^c6-4]: https://www.mongodb.com/docs/manual/reference/operator/aggregation/sample/ — MongoDB manual: $sample (docs)
[^c6-5]: https://oneuptime.com/blog/post/2026-03-31-mongodb-index-for-count-operations/markdown — How to Index for Count Operations in MongoDB (blog)
[^c6-6]: https://oneuptime.com/blog/post/2026-03-31-mongodb-sample-random-documents/markdown — How to Use $sample to Randomly Select Documents (search-snippet only, not fetched) (blog)
[^c6-7]: https://dev.to/franckpachot/firstlast-per-group-postgresql-distinct-on-and-mongodb-distinctscan-performance-1e9d — First/last per group: PostgreSQL DISTINCT ON and MongoDB DISTINCT_SCAN performance (blog)
[^c6-8]: https://jira.mongodb.org/browse/SERVER-23582 — SERVER-23582 DISTINCT_SCAN on dotted field (repo)
[^c6-9]: https://jira.mongodb.org/browse/SERVER-68623 — SERVER-68623 $sample random cursor on sharded collections (repo)

### Cursor and Read-Path Tuning (batchSize and maxTimeMS and read preference)

[^c7-1]: https://www.mongodb.com/docs/manual/reference/method/cursor.batchSize.md — cursor.batchSize() (mongosh method) (docs)
[^c7-2]: https://www.mongodb.com/docs/manual/reference/command/getMore.md — getMore (database command) (docs)
[^c7-3]: https://www.mongodb.com/docs/manual/core/read-preference.md — Read Preference (docs)
[^c7-4]: https://www.mongodb.com/docs/manual/reference/method/cursor.maxTimeMS.md — cursor.maxTimeMS() (mongosh method) (docs)
[^c7-5]: https://www.mongodb.com/community/forums/t/mis-understanding-batchsize/169713/2 — (Mis)Understanding batchSize? (forum)
[^c7-6]: https://oneuptime.com/blog/post/2026-03-31-mongodb-batch-size-control-cursor-fetching/markdown — How to Use Batch Size to Control Cursor Fetching in MongoDB (blog)
[^c7-7]: https://jira.mongodb.org/browse/SERVER-18190 — Secondary reads may block replication (forum)
[^c7-8]: https://jira.mongodb.org/browse/DRIVERS-2971 — Read server responses after client-side timeouts (forum)

### Sharded Query Targeting and Scatter-Gather

[^c8-1]: https://www.mongodb.com/docs/manual/core/sharded-cluster-query-router/ — Routing with mongos (docs)
[^c8-2]: https://www.mongodb.com/docs/manual/core/sharding-choose-a-shard-key/ — Choose a Shard Key (docs)
[^c8-3]: https://www.mongodb.com/docs/manual/core/hashed-sharding/ — Hashed Sharding (docs)
[^c8-4]: https://www.mongodb.com/community/forums/t/limit-in-a-scatter-and-gather-query-to-a-sharded-collection/237373 — $limit in a scatter and gather query to a sharded collection (forum)
[^c8-5]: https://www.netdata.cloud/guides/mongodb/mongodb-scatter-gather-queries/ — MongoDB scatter-gather queries: when mongos fans out to every shard (blog)
