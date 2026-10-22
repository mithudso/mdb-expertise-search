<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Created by `/dr` deep research 2026-10-19; research dir `<local-path>`.

---
name: mongodb-time-series-query-optimization
description: "MongoDB time-series query and index optimization: per-bucket indexing (control.min/control.max; metaField stored as-is), the 6.3 default (metaField, timeField) compound index and when sub-field indexes are needed, metaField cardinality anti-patterns (sparse short-lived buckets; bucket close rules; bucket catalog 2.5% RAM cap), $_internalUnpackBucket and $match pushdown rewrites, 8.0 block processing (SBE, automatic, verify with explain), index-backed sorts and last-point queries (DISTINCT_SCAN), bounded sort and the 100 MB limit, working-set sizing (1000-measurement / 125 KiB buckets). TRIGGER: 'time series query slow despite metaField index', 'metaField too granular', 'bucket unpacking in explain', 'block processing in 8.0', 'last-point query', 'time series working set'. SKIP: collection creation, granularity, TTL, downsampling -> mongodb-time-series; explain/plan cache basics -> mongodb-explain-plans-and-query-planner; cluster capacity planning -> atlas-diagnostics-expert."
version: "1.0.0"
updated: "2026-10-19"
category: "research"
whenToUse:
  - "speed up a slow query on a time series collection"
  - "choose or fix indexes on metaField and timeField"
  - "diagnose metaField cardinality or bucket fragmentation"
  - "read bucket unpacking and block processing in explain"
keywords: ["time series", "metaField", "timeField", "bucket", "bucket unpacking", "$_internalUnpackBucket", "block processing", "secondary index time series", "metaField cardinality", "control.min", "last point query", "DISTINCT_SCAN", "bounded sort", "working set"]
tags: ["mongodb", "time-series", "query-optimization", "indexes", "buckets"]
provenance: "/dr · <local-path>"
---

# MongoDB Time-Series Query and Index Optimization

## Overview

MongoDB indexes time series collections per bucket, not per measurement. Since 6.0 you can add secondary indexes on any field. Each index stores the min and max of a field across a bucket, except the metaField, which is stored as is. Since 6.3 the server also creates a default compound index on (metaField, timeField). The default index covers the whole metaField subdocument, so it only helps equality matches. Indexes on specific metaField subfields serve other predicates such as $in. Sorts and last-point queries use compound indexes on metaField plus timeField. The index type list is limited: text and unique indexes are prohibited, and the manual disagrees with itself on 2d and sparse. A find with sort and limit on the timeField was reported not to use a timeField index and to unpack all buckets. That report dates from 2022-2025 and is not resolved. The official manual is one organisation, so independence is limited.

MongoDB time series collections group documents into buckets keyed on an exact metaField match plus a close timeField span. Bucket count therefore tracks the number of distinct metaField values. A fine-grained or frequently changing metaField (raw UUIDs, status flags, measurement values) yields many sparse, short-lived buckets, which MongoDB docs say lowers storage and query efficiency. Bucket close rules (1000 docs, size caps, bucket catalog memory at 2.5% of RAM, cache pressure) add further fragmentation under high cardinality. Guidance: pick stable identifiers used in filters, keep non-filter fields as measurements, query on scalar sub-fields, batch inserts by metaField, and match granularity to ingest interval. No official numeric cardinality threshold exists; a community report shows bucket proliferation (3,120 buckets for 20,539 docs) causing slowdowns on 6.0.

A time series collection is a view over an internal bucket collection. Queries compile to a pipeline that starts with the internal $_internalUnpackBucket stage, which turns each bucket into per-measurement documents. The optimizer tries to move $match predicates ahead of that stage, rewritten as bucket-level predicates, so buckets can be skipped or served by an index before unpacking. Predicates on the metaField push down exactly. Measurement predicates are rewritten against control.min/control.max, for example $lt becomes $lt on control.min. Pushdown has caused several correctness bugs, all fixed: stages that change document shape between the $match and the unpack, and $group rewrites that use control.min. Official docs do not document the pushdown rules; the evidence is mostly the MongoDB Jira tracker. Verify placement with explain().

Starting in MongoDB 8.0, the server may run certain time series aggregations with block processing. It works on batches (blocks) of column-level values from bucket data instead of unpacking and reshaping one document at a time. It is part of the slot-based execution engine (SBE). Use is automatic and per query; users cannot force it on or off. The docs list pipelines that begin with $match, $sort on the timeField, or $group. Unsupported operators or expressions fall back to the classic engine. Verify with explain (slotBasedPlan.stages) or the queryFramework field in slow-query logs. Vendor speedup figures vary widely: the docs say only that gains depend on workload and configuration, while a MongoDB blog reports 10-40x. No independent benchmarks were found. All sources are MongoDB-authored.

Sorting and time-range filtering on MongoDB time series collections run against the underlying bucket collection. A sort on timeField, or on metaField then timeField, can use an index (the default compound index or a secondary one), and a point predicate on metaField lets a metaField+timeField compound index serve a timeField-only sort. Without such an index the sort unpacks buckets and sorts in memory, hitting the 100 MB limit. Last-point queries (sort meta asc, time desc, then $group with $first) get DISTINCT_SCAN only when timeField is indexed descending. Planner gaps remain: a reversed-direction bug (SERVER-100910) was fixed only in 9.0.0-rc0, and bounded sort for non-timeField sorts is still backlog (SERVER-96923). Public benchmark evidence is thin and old.

Time series collections store measurements in columnar buckets, so the working set is the set of active buckets plus the indexes on timeField and metaField, held in the WiredTiger internal cache. MongoDB docs say the bucket format gives much smaller indexes and better cache use than one-document-per-point collections. Bucket max size is 1000 measurements or 125 KiB; MongoDB may lower it for high-cardinality data so the bucket working set fits the cache. The bucket catalog (in-memory) is capped by default at 2.5% of system memory. General WiredTiger sizing applies: default cache is max(50% of (RAM - 1 GB), 256 MB), cached collection data is uncompressed, and sizing guidance is cache for working set plus write headroom. No MongoDB-published time-series-specific RAM formula was found.

## Core Concepts

### Secondary Indexes on Time Series

- Since MongoDB 6.0 a secondary index can be added to any field of a time series collection. The server indexes buckets rather than individual documents, and stores the min and max of every field except the metaField, which reduces index size.[^c1-1][^c1-2]
- Since MongoDB 6.3 the server automatically creates a compound index on the metaField and timeField for new time series collections. No index exists on _id; a hint on _id fails unless the user creates that index, and in 8.3 an index or hint named "_id_" returns an error. verified-as-of: 2026-10-14[^c1-2][^c1-3]
- Partial indexes work on time series collections. Since 6.0 they accept $or, $in and $geoWithin, but cannot be created on the metaField and timeField. Since 7.0 a TTL index with a partialFilterExpression that depends only on the metaField is allowed. (two sources) verified-as-of: 2026-10-14[^c1-1][^c1-5]

### metaField Cardinality Anti-Patterns

- Bucket count depends on the number of unique metaField values, because documents share a bucket only if their metaField values match exactly (for object/array metaFields, all fields/elements must match).[^c2-2][^c2-1]
- A new bucket is created when the metaField matches no active bucket, the timestamp is outside all active buckets' ranges, or the doc exceeds remaining size/count limits. Buckets close at 1000 docs by default, 125KiB size cap, when the active bucket set exceeds storage-engine cache, or when the bucket catalog exceeds its memory allocation (default 2.5% of system memory). High cardinality means many open buckets and so earlier closures. verified-as-of: 2026-10-14[^c2-2][^c2-1]
- Scoping: docs state the compressed bucket format in cache 'supports high cardinality workloads while preserving efficient query performance', so high cardinality is not prohibited; the penalty applies mainly to sparse/short-lived buckets from fine-grained or changing values. (two sources)[^c2-1][^c2-2]

### Time-Series Bucket Unpacking and $match Pushdown

- The optimizer pushes $match predicates past $_internalUnpackBucket: predicates on the metaField push down exactly, $lt on a measurement becomes $lt on control.min in the bucket predicate, and $geoWithin becomes $_internalBucketGeoWithin. The same logic is reused to translate partial index filters into bucket-level filters. (two sources)[^c3-2][^c3-6]
- Each bucket stores control.min and control.max for the time field and measurements, which lets range queries skip buckets that fall entirely outside the query range before unpacking. (two sources)[^c3-6][^c3-5]

### MongoDB 8.0 Block Processing (time series)

- Starting in MongoDB 8.0, the server may execute certain time series queries with block processing, which processes data in blocks instead of individual values. The docs say this improves query speed and throughput on time series collections.[^c4-1][^c4-3]
- Block processing is automatic. Users cannot enable or disable it for a single query. Eligibility is decided per query, and queries with unsupported operators or expressions run on the classic engine. SBE support is version specific and still changing. verified-as-of: 2026-10-19[^c4-1][^c4-3]

### Time-Series Sort and Range Query Patterns

- Per MongoDB docs, a sort on { timeField: ±1 } uses a secondary index on timeField; a sort on { metaField: ±1, timeField: ±1 } uses the default compound index; a sort on { timeField: ±1 } uses a { metaField, timeField } compound index only when the query has a point predicate on metaField.[^c5-1][^c5-4]

### Working Set Sizing for Time Series

- MongoDB's docs state a bucket holds at most 1000 measurements or 125 KiB, whichever is lower, and MongoDB may enforce a lower maximum for high-cardinality data so the working set of buckets fits in the WiredTiger cache. (two sources)[^c6-1][^c6-2]
- The bucket catalog is an in-memory cache in WiredTiger that tracks open buckets to coordinate concurrent writes. Its memory use grows with the number of distinct metaField values open at once. (two sources)[^c6-1][^c6-2]
- Because data is indexed per bucket by metaField rather than one index entry per data point, MongoDB docs say time series indexes are much smaller than on regular collections, which improves WiredTiger in-memory cache use. (two sources)[^c6-1][^c6-2]
- Collection data in the WiredTiger cache is uncompressed, so block compression saves disk but not cache space; the OS filesystem cache holds the compressed on-disk form. Indexes in cache still benefit from prefix compression. Compressed time series storage size therefore understates the cache footprint of hot buckets. (two sources)[^c6-3][^c6-2]

## Tools & Frameworks

- Some operations on a time series collection only use an index when it is passed as a hint. A hint can be an index name or a key pattern. (two sources)[^c1-2][^c1-3] _(Secondary Indexes on Time Series)_
- distinct() cannot be efficiently indexed on time series collections; use $match on a metaField prefix with $group over a compound metaField index instead. For high-cardinality workloads, flattening nested measurement objects may help, but docs recommend it only if nesting causes significant performance issues. (two sources)[^c2-3][^c2-1] _(metaField Cardinality Anti-Patterns)_
- To check whether a query used block processing, inspect explain output at queryPlanner.winningPlan.slotBasedPlan.stages. A slotBasedPlan field means SBE ran the query. Slow-query logs carry a queryFramework field with value sbe or classic. The docs show no example of what block-processing stages look like.[^c4-1][^c4-3] _(MongoDB 8.0 Block Processing (time series))_

## Methodology

- Guidance on field roles: use the metaField index for filtering and equality, and use the timeField and other indexed fields for range queries. If timeField values fall before 1970-01-01 or after 2038-01-19, create an index on the timeField to keep queries fast.[^c1-1][^c1-3] _(Secondary Indexes on Time Series)_
- Tentative: MongoDB's blog (published 2024-12-09, updated 2025-07-21) claims 10-40x improvements across workloads, up to 100x for some large aggregations, and 20x ops/sec versus 7.0 in a worked example. The example ran on an Atlas M50 using MongoDB's TSBS fork: about 6 million events, a 24-hour $match, $sort, $group with $dateTrunc, $setWindowFields and $expMovingAvg. verified-as-of: 2025-07-21[^c4-2] _(MongoDB 8.0 Block Processing (time series))_
- Allegro's 5.0.3 benchmark found aggregation over a random six-hour window 23-48% faster on a time series collection than a regular one (10K to 100K queries), but single-timestamp lookups were nearly equal (16.854s vs 16.038s for 1M queries). (two sources) verified-as-of: 2021-12-01[^c5-2][^c5-1] _(Time-Series Sort and Range Query Patterns)_
- Default WiredTiger internal cache is the larger of 50% of (RAM - 1 GB) or 256 MB. MongoDB advises against raising it above the default, and in containers it must be set below the container's RAM limit. verified-as-of: 2026-10-18[^c6-3][^c6-5] _(Working Set Sizing for Time Series)_
- Working set is the subset of data and indexes touched in a typical window, rarely the whole database. Practitioner guidance is to size the cache to working set plus write headroom, and to use a sustained post-warmup page-fault rate as a proxy when the size is unknown. (two sources)[^c6-5][^c6-4] _(Working Set Sizing for Time Series)_
- Tentative: A MongoDB staff forum answer (March 2022) gave an informal rule of thumb of RAM at 15-20% of total data size, covering indexes, working set, queries and OS. It is not an official time-series formula and cites MongoDB 4.0 docs.[^c6-4] _(Working Set Sizing for Time Series)_

## Practical Patterns

- The default compound index covers the whole metaField subdocument, so it is only used for $eq on the metaField. To serve other predicates such as $in, create a secondary index on specific metaField subfields, for example metadata.type.[^c1-2][^c1-4] _(Secondary Indexes on Time Series)_
- Sort on {timeField: ±1} uses a secondary index on the timeField. Sort on {metaField: ±1, timeField: ±1} uses the default compound index. A sort on the timeField uses a {metaField, timeField} index when the query has a point predicate on the metaField.[^c1-2][^c1-1] _(Secondary Indexes on Time Series)_
- Last-point queries (latest reading per metaField value) are served by compound indexes on the metaField and timeField in any direction. They are fastest with the DISTINCT_SCAN optimization, which needs a descending timeField index, for example {metadata.sensorId: 1, timestamp: -1}. (two sources)[^c1-2][^c1-4] _(Secondary Indexes on Time Series)_
- Docs' metaField rules: choose fields that rarely or never change; prefer stable identifiers common in filters; do not put fields not used for filtering in the metaField, store them as measurements. The docs say the metaField choice has the biggest impact on query optimization.[^c2-3][^c2-1] _(metaField Cardinality Anti-Patterns)_
- Granularity must match per-source ingest interval: 'seconds' (1h bucket span) with sparse data leads to buckets with a single document; 'hours' (30-day span) leads to longer traversal. Custom bucketMaxSpanSeconds/bucketRoundingSeconds exist since 6.3. Granularity mismatch compounds metaField cardinality fragmentation.[^c2-3][^c2-1] _(metaField Cardinality Anti-Patterns)_
- Insert tip for many metaField values: batch documents with identical metaField together in insertMany with ordered:false, so one insert cost is paid per metaField value rather than per document.[^c2-3][^c2-1] _(metaField Cardinality Anti-Patterns)_
- Put metaField and time-range $match stages first in the pipeline, and index the metaField (and time) fields. A leading $match on indexed meta fields restricts the buckets that get unpacked; a compound index on meta subfields supports a $match then $group pattern in place of distinct(). (two sources)[^c3-1][^c3-3] _(Time-Series Bucket Unpacking and $match Pushdown)_
- Block processing applies to aggregation pipelines that begin with $match, with $sort on the timeField only, or with $group. A MongoDB blog also names $setWindowFields as an analytical stage that benefits, but gives no complete list of supported operators. (two sources) verified-as-of: 2026-10-19[^c4-1][^c4-2] _(MongoDB 8.0 Block Processing (time series))_
- Tentative: Last-point queries (latest measurement per metaField value) use $sort { meta: 1, time: -1 } then $group with $first. They are fastest with DISTINCT_SCAN, which the docs say is available only when the index on timeField is descending; confirm via explain('executionStats') showing DISTINCT_SCAN.[^c5-1] _(Time-Series Sort and Range Query Patterns)_
- Granularity mismatch inflates bucket count or traversal cost: granularity 'hours' for 5-minute data puts up to a month of events in one bucket (slower queries); 'seconds' creates many single-document buckets. Granularity or bucketing span can later be increased but not decreased. (two sources)[^c6-2][^c6-1] _(Working Set Sizing for Time Series)_
- Tentative: Compression best practices (omit empty fields, round numerics, keep consistent field order) reduce on-disk bucket size; schema changes between documents leave following documents uncompressed.[^c6-2] _(Working Set Sizing for Time Series)_

## Anti-Patterns

- Text indexes and unique indexes are not supported on time series collections.[^c1-1][^c1-3][^c1-5] _(Secondary Indexes on Time Series)_
- Fine-grained or changing metaField values generate many sparsely packed, short-lived buckets, increasing collection cardinality and decreasing storage and query efficiency (official docs; no numeric threshold given).[^c2-1][^c2-2] _(metaField Cardinality Anti-Patterns)_
- Tentative: Anti-pattern: using a unique per-device ID (e.g. UUID) as a top-level string metaField makes one bucket per ID per time window (example: 100,000 UUIDs -> 100,000 buckets). The blog suggests grouping attributes (region, device type) with the raw ID as a subfield so region queries still co-locate. Blog advice, not MongoDB-endorsed; blog gives no numeric threshold. verified-as-of: 2026-03-31[^c2-4] _(metaField Cardinality Anti-Patterns)_
- Anti-pattern: putting measurement values (temperature, CPU) or frequently changing status flags in the metaField forces a new bucket whenever the value changes. (two sources)[^c2-4][^c2-1] _(metaField Cardinality Anti-Patterns)_
- Query tip: MongoDB reorders object metaField contents, so query scalar sub-fields (e.g. metaField.sensorId) rather than equality on the whole metaField object. Arrays as metaField may behave unexpectedly because array equality is order-dependent. The metaField field itself cannot be redefined after creation.[^c2-3][^c2-1] _(metaField Cardinality Anti-Patterns)_
- SERVER-63279: pushing a metaField predicate past a stage that changes document contents (for example $project) returned wrong results. Affected 5.0.5 and 5.2.0; fixed in 5.0.7, 5.2.2 and 5.3.0. After the fix, a $match placed after a document-reshaping stage may stay after the unpack and cost more. (two sources) verified-as-of: 2026-10-19[^c3-3][^c3-2] _(Time-Series Bucket Unpacking and $match Pushdown)_
- Tentative: Because buckets group by exact metaField value, many unique metaField values produce many sparse buckets, which lowers query efficiency; pushdown then prunes fewer useful buckets.[^c3-1] _(Time-Series Bucket Unpacking and $match Pushdown)_
- The official docs make no numeric performance claim. They say only that the gain varies with workload and instance configuration. The vendor blog's 10-100x figures are therefore workload-specific best cases and should not be assumed for other pipelines. (two sources)[^c4-1][^c4-2] _(MongoDB 8.0 Block Processing (time series))_
- On MongoDB 5.0.3, sorting a 10M-document time series collection by timestamp with no index failed with 'Sort exceeded memory limit of 104857600 bytes, but did not opt in to external sorting'; the author had to add an index to sort by time. (two sources) verified-as-of: 2021-12-01[^c5-2][^c5-6] _(Time-Series Sort and Range Query Patterns)_
- Tentative: SERVER-96923, a bounded sort optimization for time series queries that do not sort on timeField, is an unresolved backlog feature request (last updated 2026-09-25), so such sorts are not guaranteed to be bounded. verified-as-of: 2026-09-25[^c5-4] _(Time-Series Sort and Range Query Patterns)_

## Troubleshooting

- Tentative: 2dsphere indexes can be created on the timeField, metaField or measurement fields since 6.0, per the secondary index page. The OneUptime blog says they are supported only on metaField subfields. Time series collections support only $geoNear for sorting by distance; $near and $nearSphere do not work.[^c1-2][^c1-3] _(Secondary Indexes on Time Series)_
- Before downgrading the feature compatibility version, drop every time series secondary index that the lower FCV does not support. Otherwise the downgrade is blocked. (two sources)[^c1-1][^c1-3] _(Secondary Indexes on Time Series)_
- Tentative: Reported limit: a find with sort {timestamp: -1} and limit 1 on a time series collection did a COLLSCAN on system.buckets.<name> and unpacked about 294,000 documents (server 5.0.6, a secondary index on timestamp existed). An answer from MongoDB staff said usual index improvements do not apply, and pointed to SERVER-4507. A 2025-06-27 post says the issue was still open. The thread does not show whether current releases still behave this way. verified-as-of: 2025-06-27[^c1-6] _(Secondary Indexes on Time Series)_
- Tentative: A forum workaround sorts system.buckets.<name> on control.max.timestamp and then looks up the document in the view. One reader reported that control.max.timestamp did not return the true latest record in their data, so the workaround can be wrong with out-of-order ingest.[^c1-6] _(Secondary Indexes on Time Series)_
- Tentative: Community report: on 6.0.5 with metaField=userid, granularity=hours, ~40B events/3TB, reads and writes degraded after ~3 weeks; one user had 3,120 buckets for 20,539 docs, dropping to 370 after read/delete/re-insert, giving >10x faster queries. A second user reported ~10s for a project/group over ~6M records. No MongoDB staff answer or confirmed fix in the thread. verified-as-of: 2024-11-11[^c2-5] _(metaField Cardinality Anti-Patterns)_
- Tentative: Explain output for a time series query shows a $_internalUnpackBucket stage and, even when the predicate was pushed down, a separate $match stage still appears afterward to re-check unpacked documents. Do not read the residual $match as proof that pushdown failed.[^c3-5] _(Time-Series Bucket Unpacking and $match Pushdown)_
- SERVER-79136: a $match followed by $group on the metaField with $min/$max was rewritten to use bucket-level control.min/control.max, ignoring the filter, so results were wrong (5 instead of 21 in the report). Affected 6.0.8 and 7.0.0-rc8; fixed in 5.0.20, 6.0.9, 7.0.0-rc9 and 7.1.0-rc0. (two sources) verified-as-of: 2026-10-19[^c3-4][^c3-3] _(Time-Series Bucket Unpacking and $match Pushdown)_
- Tentative: The SBE reference page says SBE is disabled automatically on collections that have an index with a hashed-field prefix followed by a non-hashed field, with both fields in the index. Ineligible queries fall back to the classic engine. The page does not tie this rule to time series specifically. verified-as-of: 2026-10-19[^c4-3] _(MongoDB 8.0 Block Processing (time series))_
- Tentative: During 8.0 development, Jira SERVER-88316 (fixed in 8.0.0-rc0) showed the server using block processing for a GroupByNull test case with only featureFlagSbeFull set, when the test expected none. This shows the block-processing decision depended on several feature flags.[^c4-4] _(MongoDB 8.0 Block Processing (time series))_
- Tentative: Forum reports show a blank-filter sort on timeField descending produces a backward COLLSCAN on system.buckets followed by $_internalUnpackBucket, with multi-second runtimes and memory-limit errors unless allowDiskUse is set; explain on a time series collection reports the bucket collection plan.[^c5-6] _(Time-Series Sort and Range Query Patterns)_
- SERVER-100910: for compound time series indexes the planner's sortMatchesTraversalPreference always returned false, so reversed-direction (backward scan) plans were not generated and sorts could miss the bounded sort optimization. Closed Fixed in 9.0.0-rc0 on 2026-05-14; earlier versions are affected. (two sources) verified-as-of: 2026-05-14[^c5-3][^c5-1] _(Time-Series Sort and Range Query Patterns)_
- Tentative: A forum report with indexes on t/c in both directions shows a range filter { c: x, t: { $lte: ... } } with sort { t: -1 } spending IXSCAN ~4s but FETCH ~2-5 minutes, while a similar $gte ascending query took ~1s; no answer was given, version unstated.[^c5-5] _(Time-Series Sort and Range Query Patterns)_
- A bucket closes when the set of active buckets does not fit within the allowed storage engine cache size, or when the bucket catalog exceeds its memory allocation (default 2.5% of system memory). The docs point to collStats for reviewing this. (two sources) verified-as-of: 2026-10-19[^c6-1][^c6-2] _(Working Set Sizing for Time Series)_
- Tentative: Undersized-cache signals per one monitoring vendor: sustained fill above ~80% with rising eviction rates, dirty ratio above 15% (warning) or 20% (critical), and application-thread evictions. These thresholds are vendor heuristics, not MongoDB documentation.[^c6-5] _(Working Set Sizing for Time Series)_

## Disagreements & Open Questions

- Disagreement (Secondary Indexes on Time Series): The manual contradicts itself on 2d and sparse indexes. The limitations page says 2d and sparse indexes are allowed only on the metaField. The time series index page lists 2d indexes as prohibited and says sparse indexes cannot be created on the metaField.[^c1-3][^c1-1]
- Disagreement (Secondary Indexes on Time Series): The OneUptime blog says wildcard indexes are unsupported and 2dsphere works only on metaField subfields. The manual's secondary index page says 2dsphere works on timeField, metaField or measurement fields. The manual pages read here do not mention wildcard indexes.[^c1-5][^c1-2]
- Disagreement (Secondary Indexes on Time Series): The OneUptime blog says the automatic index is on (metaField, timeField) but also describes it as (meta, control.min.time, control.max.time). A forum answer says normal index improvements do not apply to time series views, while the manual says secondary indexes improve sort and last-point performance.[^c1-5][^c1-6]
- Open (Secondary Indexes on Time Series): Only two organisations were found (MongoDB and OneUptime); the third-organisation requirement was not met and no independent benchmark of index layouts exists in the results.
- Open (Secondary Indexes on Time Series): Which of 2d, sparse, hashed and wildcard indexes are allowed on current releases? The manual is self-contradictory and does not mention hashed or wildcard.
- Open (Secondary Indexes on Time Series): Is SERVER-4507 (sort and limit on timeField using the index) fixed in 8.x? The latest forum post is from 2025-06-27.
- Open (Secondary Indexes on Time Series): Does a TTL partial index on the metaField need 6.3 or 7.0? One manual passage says 6.3, the index page says 7.0.
- Disagreement (metaField Cardinality Anti-Patterns): Docs warn high cardinality degrades efficiency yet also say compressed in-cache buckets support high-cardinality workloads; no source quantifies where the line is.[^c2-1]
- Disagreement (metaField Cardinality Anti-Patterns): Forum thread expects ~1 bucket per metaField per month at hours granularity but observed thousands; docs do not explain this, and the blog's 'one bucket per unique value per window' model is a simplification.[^c2-5][^c2-4]
- Open (metaField Cardinality Anti-Patterns): No official numeric cardinality threshold or benchmark found.
- Open (metaField Cardinality Anti-Patterns): Whether 7.x/8.x fixed bucket proliferation seen in the 6.0 forum report; no confirmed fix found.
- Open (metaField Cardinality Anti-Patterns): How to diagnose bucket fragmentation officially (bucket count vs docs per bucket); collStats timeseries section not verified here.
- Disagreement (Time-Series Bucket Unpacking and $match Pushdown): The gitconnected author expected a pushed-down predicate to remove the separate $match from explain, but both stages appear; the author could not tell whether explain reports it correctly.[^c3-5]
- Open (Time-Series Bucket Unpacking and $match Pushdown): Official docs do not document the pushdown rules; only Jira tickets (all MongoDB-run) describe them, so independence is limited.
- Open (Time-Series Bucket Unpacking and $match Pushdown): Which current versions (8.x) push which measurement operators beyond $lt/$gt down to control.min/max.
- Open (Time-Series Bucket Unpacking and $match Pushdown): SERVER-101506 (unpack stage rewrites before end-of-pipeline optimization, affecting $sort/$limit) and SERVER-70160 ($getField match pushed too early, fixed 5.0.14) were seen only in search snippets, not fetched.
- Open (Time-Series Bucket Unpacking and $match Pushdown): Only one negation search was done; it found correctness bugs but no claim that pushdown is overhyped.
- Disagreement (MongoDB 8.0 Block Processing (time series)): Search-result snippets show the docs claiming gains of more than 200% for $group, while the blog reports 10-40x and 20x (2000%) in its example. The fetched docs page itself gave no number. Third-party webinar slides cited an unconfirmed 60% $group gain.[^c4-1][^c4-2]
- Open (MongoDB 8.0 Block Processing (time series)): All sources are MongoDB-authored (docs, blog, Jira). No independent organisation or third-party benchmark was found, so the 3-independent-source depth contract was not met.
- Open (MongoDB 8.0 Block Processing (time series)): Exact operator/expression support list for block processing (for example which $group accumulators) is undocumented in the fetched pages.
- Open (MongoDB 8.0 Block Processing (time series)): An older Jira ticket reportedly says block processing is unsupported with allowDiskUse: true. This was only seen in a search snippet and not verified.
- Open (MongoDB 8.0 Block Processing (time series)): The negation rounds found no regression reports or critiques. This is an absence of evidence, not evidence of absence.
- Open (MongoDB 8.0 Block Processing (time series)): Whether a $match-first pipeline over a metaField index still gets block processing when it uses the bucket unpack path is covered by sibling concepts.
- Disagreement (Time-Series Sort and Range Query Patterns): Allegro (5.0.3) says explain showed COLLSCAN yet times were similar to indexed regular collection; later docs describe index-backed sorts, so the 2021 index-less picture is outdated for 6.3+.[^c5-2][^c5-1]
- Open (Time-Series Sort and Range Query Patterns): Whether the 100 MB sort limit and allowDiskUse apply identically to $_internalBoundedSort.
- Open (Time-Series Sort and Range Query Patterns): Current numeric benchmarks for range+sort on 8.x; none found from an independent organisation after 2021.
- Open (Time-Series Sort and Range Query Patterns): Exact backports of SERVER-100910 to 8.x branches.
- Open (Time-Series Sort and Range Query Patterns): Only MongoDB and Allegro are independent organisations; Allegro data is 5.0.3-era.
- Disagreement (Working Set Sizing for Time Series): Forum rule of thumb (RAM = 15-20% of data size) differs in framing from the docs/vendor view (size cache to working set plus headroom); the forum thread itself questions whether the cache or total RAM is the target.[^c6-4][^c6-5]
- Open (Working Set Sizing for Time Series): No MongoDB source gives a time-series-specific formula for index or working-set size per metaField value.
- Open (Working Set Sizing for Time Series): Exact size reduction of the bucket cap under high cardinality is undocumented.
- Open (Working Set Sizing for Time Series): Negation round found no source contradicting the docs' smaller-index claim, and no independent benchmark confirming it.

## References

### Secondary Indexes on Time Series

[^c1-1]: https://www.mongodb.com/docs/manual/core/timeseries/timeseries-index.md — Time Series Indexes (docs)
[^c1-2]: https://www.mongodb.com/docs/manual/core/timeseries/timeseries-secondary-index.md — Add Secondary Indexes to Time Series Collections (docs)
[^c1-3]: https://www.mongodb.com/docs/manual/core/timeseries/timeseries-limitations.md — Time Series Collection Limitations (docs)
[^c1-4]: https://www.mongodb.com/docs/manual/core/timeseries/timeseries-best-practices.md — Time Series Best Practices (docs)
[^c1-5]: https://oneuptime.com/blog/post/2026-03-31-mongodb-time-series-secondary-indexes/markdown — How to Use Secondary Indexes on Time Series Collections in MongoDB (blog)
[^c1-6]: https://www.mongodb.com/community/forums/t/time-series-how-to-get-the-most-recent-document/149455 — Time series: How to get the most recent document? (forum)

### metaField Cardinality Anti-Patterns

[^c2-1]: https://www.mongodb.com/docs/manual/core/timeseries/timeseries-considerations.md — Time Series Collections Considerations (docs)
[^c2-2]: https://www.mongodb.com/docs/manual/core/timeseries/timeseries-bucketing.md — About Time Series Data (docs)
[^c2-3]: https://www.mongodb.com/docs/manual/core/timeseries/timeseries-best-practices.md — Best Practices for Time Series Collections (docs)
[^c2-4]: https://oneuptime.com/blog/post/2026-03-31-mongodb-time-series-metafields/markdown — How to Design MetaFields for Time Series Collections in MongoDB (blog)
[^c2-5]: https://mongodb.com/community/forums/t/mongodb-v6-0-time-series-slowness-issue/283439 — Mongodb v6.0 Time Series Slowness Issue (forum)

### Time-Series Bucket Unpacking and $match Pushdown

[^c3-1]: https://www.mongodb.com/docs/manual/core/timeseries/timeseries-best-practices.md — Best Practices for Time Series Collections (docs)
[^c3-2]: https://jira.mongodb.org/browse/SERVER-59163 — SERVER-59163 partial indexes on time-series (repo)
[^c3-3]: https://jira.mongodb.org/browse/SERVER-63279 — SERVER-63279 metaField predicate pushdown wrong results (repo)
[^c3-4]: https://jira.mongodb.org/browse/SERVER-79136 — SERVER-79136 group min rewrite wrong results (repo)
[^c3-5]: https://levelup.gitconnected.com/how-mongodb-time-series-collection-works-under-the-hood-2348f3a2318e — How MongoDB Time Series Collection Works Under the Hood (blog)
[^c3-6]: https://oneuptime.com/blog/post/2026-03-31-mongodb-time-series-buckets/view — How to Query Time Series Buckets in MongoDB (blog)

### MongoDB 8.0 Block Processing (time series)

[^c4-1]: https://www.mongodb.com/docs/v8.2/core/timeseries/timeseries-querying/ — Querying time series data (block processing) (docs)
[^c4-2]: https://mongodb.com/company/blog/technical/key-enhancements-mongodb-8-0-block-processing — Key enhancements in MongoDB 8.0: block processing (blog)
[^c4-3]: https://mongodb.com/docs/v8.0/reference/sbe — Slot-based query execution engine (docs)
[^c4-4]: https://jira.mongodb.org/browse/SERVER-88316 — SERVER-88316 timeseries_group.js featureFlagSbeFull (repo)

### Time-Series Sort and Range Query Patterns

[^c5-1]: https://www.mongodb.com/docs/manual/core/timeseries/timeseries-secondary-index.md — Add Secondary Indexes to Time Series Collections (docs)
[^c5-2]: https://blog.allegro.tech/2021/12/performance-evaluation-of-timeseries.html — Evaluating performance of time series collections (blog)
[^c5-3]: https://jira.mongodb.org/browse/SERVER-100910 — SERVER-100910 Do not generate reversed sort direction plans for time-series (repo)
[^c5-4]: https://jira.mongodb.org/browse/SERVER-96923 — SERVER-96923 bounded sort for non-timeField time-series queries (repo)
[^c5-5]: https://www.mongodb.com/community/forums/t/filter-on-time-series-with-lte-on-timestamp-and-reverse-index-is-too-slow/296074 — Filter on Time-Series with lte on timestamp and reverse index is too slow (forum)
[^c5-6]: https://www.mongodb.com/community/forums/t/is-sorting-in-mongodb-supposed-to-be-very-slow-and-memory-consuming/229344 — Is sorting in MongoDB supposed to be very slow and memory consuming (forum)

### Working Set Sizing for Time Series

[^c6-1]: https://www.mongodb.com/docs/manual/core/timeseries/timeseries-bucketing/ — Time Series Bucketing (docs)
[^c6-2]: https://www.mongodb.com/docs/manual/core/timeseries/timeseries-best-practices/ — Best Practices for Time Series Collections (docs)
[^c6-3]: https://www.mongodb.com/docs/manual/faq/storage/ — FAQ: MongoDB Storage (docs)
[^c6-4]: https://www.mongodb.com/community/forums/t/working-set-should-be-sized-to-fit-into-ram-or-wiredtiger-internal-cache/140684 — Working set sizing: RAM or WiredTiger cache? (forum)
[^c6-5]: https://www.netdata.cloud/guides/mongodb/mongodb-cache-undersized-working-set/ — MongoDB cache too small: sizing the WiredTiger cache for your working set (blog)
