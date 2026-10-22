<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Created by `/dr` deep research 2026-10-19; research dir `<local-path>`.

---
name: storage-and-data-lifecycle-cost-levers
description: "MongoDB storage and data-lifecycle cost levers: TTL delete vs Online Archive vs Data Federation cost model ($5/TB processed, per-GB archive storage, query limits); WiredTiger block compression (snappy, zlib, zstd) and index prefix compression as disk-cost levers; schema choices that change stored bytes (field-name length under compression, value types, unnecessary indexes); query efficiency as a cost signal (scanned/returned 1000:1 alert, Performance Advisor, $indexStats pruning). TRIGGER: shrink MongoDB storage bill; archive vs TTL vs federate cold data; Online Archive query cost; zstd vs snappy savings; compact and disk reclaim; short field names worth it; unused index removal. SKIP: archive rule mechanics -> mongodb-atlas-expert; WiredTiger cache internals -> mongodb-expert; tier pricing -> atlas-cluster-topology-and-tier-economics; invoice line items -> atlas-billing-mechanics-and-cost-visibility."
version: "1.0.0"
updated: "2026-10-19"
category: "research"
whenToUse:
  - "reduce MongoDB storage cost"
  - "choose TTL vs Online Archive vs Data Federation for cold data"
  - "estimate zstd or snappy compression savings"
  - "prune unused indexes to cut storage and write cost"
keywords: ["online archive cost", "data federation pricing", "TTL index", "block compression", "zstd", "snappy", "prefix compression", "storageSize", "field name length", "unused indexes", "$indexStats", "scanned returned ratio", "performance advisor", "covered query", "compact", "storage cost"]
tags: ["mongodb", "atlas", "cost", "storage", "compression", "online-archive", "data-federation", "indexes", "schema"]
provenance: "/dr · <local-path>"
---

# Storage and Data-Lifecycle Cost Levers

## Overview

Three levers cut hot-tier storage cost for ageing MongoDB data. A TTL index deletes documents: zero retained cost, data gone, delete load on the primary. Atlas Online Archive moves aged documents to managed object storage and keeps them queryable: cheap storage, but $5/TB processed per query plus data-returned charges. Atlas Data Federation over your own S3 bucket gives the same query engine with more tuning control and more operational work. Choose by retention need and query frequency: delete if the data has no value, archive if it is read rarely, federate if you need custom formats or partitioning. Cost surprises come from unfiltered archive queries and from mass TTL deletes.

WiredTiger compresses collection data with block compression (snappy default; zlib and zstd optional; zstd default for time-series) and indexes with prefix compression (on by default). Block compression cuts on-disk bytes, so it lowers provisioned-storage cost, at the price of CPU, and collection data is uncompressed in the WiredTiger cache. Prefix compression also shrinks index RAM. Moving from snappy to zstd is the main tunable lever: a Percona test on 14.95GB showed 10.75GB (snappy) vs 7.69GB (zstd) with similar CPU. Changing the default only affects new collections; existing ones need a rebuild. Ratios are workload-specific and published numbers conflict.

Schema choices change MongoDB storage bytes and therefore cost. The measurable levers are: field-name length (stored in every BSON document), value types (ints vs strings, Date vs string), omitted vs null fields, stray metadata fields like spring-data _class, and index count (unused or redundant indexes). Block compression shrinks the field-name lever sharply: MongoDB calls the extra benefit of short names modest, and older tests show about 2.5% with zlib versus about 10% uncompressed. Indexes are unaffected by field-name length. Document bloat (unrelated fields stored together) mostly hurts working set and RAM, not disk. No current zstd measurement of field-name savings was found.

Inefficient queries (collection scans, partially indexed queries) burn CPU, disk I/O and cache, which pushes teams toward larger Atlas cluster tiers. Atlas exposes the signal as the scanned-to-returned ratio (alert default 1000:1, ideal near 1) and Performance Advisor index suggestions ranked by wasted bytes read. Covered queries read only the index and skip document fetches. The counter-force is that every index costs write work, storage and WiredTiger cache, so unused or redundant indexes must be pruned. MongoDB docs describe the mechanics but make no explicit cost or tier-downsizing claims; the link from query tuning to a smaller tier is an inference that has to be validated by measuring CPU, cache and write latency before and after. Write-penalty evidence is thin and workload dependent.

## Core Concepts

### Data Lifecycle Cost Model (TTL vs Online Archive vs Data Federation)

- A TTL index deletes documents; MongoDB's own TTL page tells users whose goal is reducing storage cost to consider Atlas Online Archive, which tiers infrequently accessed data to managed S3 instead of deleting it.[^c1-3][^c1-6]
- Online Archive is billed through Atlas Data Federation: storage by GB and days stored (rate varies by cloud provider and region), plus $5.00 per TB of archived data processed with a 10 MB minimum per query, plus data returned/transferred. verified-as-of: 2026-10-18[^c1-1][^c1-2]
- Tentative: Third-party blog figures of about $0.25/GB/month for cluster storage versus about $0.023/GB/month for Online Archive are unverified; the blog page fetched gave no per-GB rates, so these numbers do not hold as a cost basis. verified-as-of: 2026-10-18[^c1-6]

### WiredTiger Block and Prefix Compression as Storage Cost Lever

- WiredTiger uses snappy block compression for most collections and prefix compression for all indexes by default; time-series collections default to zstd. Compression costs extra CPU in exchange for lower storage use. verified-as-of: 2026-10-18[^c2-1][^c2-2]
- Collection data in the WiredTiger internal cache is uncompressed, so block compression saves disk, not cache RAM. The filesystem cache holds the compressed on-disk format. Index prefix compression deduplicates common prefixes and also reduces index RAM in the cache.[^c2-1][^c2-2]

### Schema Design for Storage Cost

- BSON stores field names inside every document, so field-name length multiplies by document count. Allegro (MongoDB 4.4, snappy) measured a flat test document dropping from about 3.4MB to 2MB (about 40%) with shorter field names alone. (two sources)[^c3-1][^c3-2]
- MongoDB's own guidance: field names compress well under WiredTiger block compression, so the additional benefit of short field names is modest; do not abbreviate to single letters because it obscures data.[^c3-6][^c3-2]
- Compression sharply reduces the field-name saving: on uncompressed MongoDB 2.2.5, short names saved about 10% (22.47 GB to 20.42 GB, 100M synthetic docs); on TokuMX with zlib, long vs short names were 4.38 GB vs 4.27 GB (about 2.5%). (two sources)[^c3-3][^c3-6]
- Percona disputes treating compression as the whole story: document size also affects app memory, network transfer, the replication log, cache memory, compressor input and journal; only on-disk and journal involve compression. In its example, shorter field names cut a document from 54,879 to 41,392 bytes (about 25%). (two sources)[^c3-2][^c3-6]
- Shorter field names do not shrink indexes: index entries hold key values with a predefined structure, not field names. Allegro also found index size unchanged when switching _id from string to int32. (two sources)[^c3-2][^c3-1]
- WiredTiger block compression covers collections (snappy default in 3.0, zlib optional) and prefix compression covers indexes; compression is page-level, so repeated field names across documents in a page compress well, while random and already-compressed binary data does not. (two sources) verified-as-of: 2026-10-18[^c3-6][^c3-3]

### Query Efficiency as a Cost Lever

- Atlas Scanned Objects / Returned alert fires when the server-wide average of documents scanned versus returned exceeds a threshold; the default is 1000:1. The Scanned / Returned alert (index keys examined) is not enabled by default. The ideal ratio is close to 1. verified-as-of: 2026-10-18[^c4-1][^c4-2]

## Tools & Frameworks

- zlib and zstd are the alternative block compressors, set globally with storage.wiredTiger.collectionConfig.blockCompressor, or per collection/index at creation (e.g. configString block_compressor=zstd). Index prefix compression is disabled with storage.wiredTiger.indexConfig.prefixCompression.[^c2-1][^c2-2][^c2-5] _(WiredTiger Block and Prefix Compression as Storage Cost Lever)_
- zstd level defaults to 6 in WiredTiger and is tunable (MongoDB blockCompressorQuality 1-22 per blogs). WiredTiger does not store which compressor wrote a block. (two sources) verified-as-of: 2026-10-18[^c2-4][^c2-5] _(WiredTiger Block and Prefix Compression as Storage Cost Lever)_
- Performance Advisor watches queries slower than 100 ms, groups them by shape, ranks suggested indexes by Impact (total wasted bytes read), and suggests an index only when scanned minus returned documents exceeds 500. The Impact formula is not published. (two sources) verified-as-of: 2026-10-18[^c4-2][^c4-1] _(Query Efficiency as a Cost Lever)_

## Methodology

- Cost controls for archive queries: configure query limits to cap processed data, run explain and multiply typical processed bytes by monthly query count, set billing alerts. The Online Archive federated-instance page shows bytes processed and query counts but not cost; cost appears only on the Atlas billing page.[^c1-1][^c1-6] _(Data Lifecycle Cost Model (TTL vs Online Archive vs Data Federation))_
- storageSize() reports compressed on-disk size and can be smaller than dataSize(); totalIndexSize() reflects prefix-compressed size. Compare these to measure savings.[^c2-2][^c2-1] _(WiredTiger Block and Prefix Compression as Storage Cost Lever)_
- MongoDB lists unnecessary indexes (rarely used, redundant because a compound index covers them, or unused) as a schema anti-pattern that bloats storage and slows writes. Procedure: find them with $indexStats (run on every node), hide with hideIndex(), then dropIndexes(). Atlas Performance Advisor (M10+) and Compass also surface them. verified-as-of: 2026-10-18[^c3-4][^c3-1] _(Schema Design for Storage Cost)_
- Tentative: $indexStats counters reset on mongod restart and internal operations can inflate them. Wait a full workload cycle (24h+ of normal load) before treating zero usage as removable, run it per shard primary on sharded clusters (not on mongos), and exclude _id and unique indexes.[^c4-5] _(Query Efficiency as a Cost Lever)_
- Tentative: No official MongoDB source found that quantifies or states that query/index tuning lets a cluster drop a tier. The query-targeting and Performance Advisor pages describe only performance impact, not cost. The tuning-to-smaller-tier link is an inference; third-party guidance suggests collecting about two weeks of metrics and checking cache hit rate above 90% before downsizing. verified-as-of: 2026-03-31[^c4-7] _(Query Efficiency as a Cost Lever)_

## Practical Patterns

- Data Federation charges 'Data Processed' (bytes read from the source, rounded up to the MB) and 'Data Returned/Transferred'; AWS-side return/transfer within a region is $0.01 per GB. Partitioning S3 data lets a query read one partition (1 GB of 10 GB) instead of the whole file, but a blank $match still reads everything. verified-as-of: 2026-10-18[^c1-2][^c1-1] _(Data Lifecycle Cost Model (TTL vs Online Archive vs Data Federation))_
- Tentative: Online Archive is fully managed; pointing Data Federation at your own S3 bucket allows more tuning but adds complexity and ongoing management. Keep Data Federation in the same AWS region as the S3 source to avoid excess charges.[^c1-5] _(Data Lifecycle Cost Model (TTL vs Online Archive vs Data Federation))_
- Percona test (PSMDB 6.0.4, 4vCPU/14GB): 14.95GB of data became 10.75GB with snappy and 7.69GB with zstd level 6, with average CPU 34% vs 31.72%. Percona concludes snappy suits write-heavy low-CPU workloads and zstd suits read-heavy or storage-saving goals. (two sources)[^c2-3][^c2-6] _(WiredTiger Block and Prefix Compression as Storage Cost Lever)_
- Another test (Vicuesoft, 9.79KB avg docs) measured 711.54MB snappy, 449.48MB zlib, 380.43MB zstd. Ratios are data-dependent; MongoDB itself says the ratio depends on the data and library, and gives no universal figure. Blog ranges (snappy 2-3x, zstd 3-5x) are generic estimates. (two sources)[^c2-6][^c2-2][^c2-5] _(WiredTiger Block and Prefix Compression as Storage Cost Lever)_
- Value types matter: Allegro found an int32 ID roughly halved on-disk collection size versus a string ID; Percona warns that numbers and dates stored as strings waste space. Enum labels replaced by ordinals saved little with snappy on but considerably more with compression off. (two sources)[^c3-1][^c3-2] _(Schema Design for Storage Cost)_
- Tentative: Flattening nested sub-documents saved about 0.4MB (3.4MB to 3MB, roughly 12% of the personal-data fields) in Allegro's synthetic test; a modest lever compared with type and field-name choices.[^c3-1] _(Schema Design for Storage Cost)_
- Bloated documents (related fields not read together stored in one document) inflate the working set so it may stop fitting in RAM, and raise bandwidth. MongoDB's fix is to split hot fields and detail fields into separate linked collections; the trade-off is $lookup cost. This is mainly a RAM/IOPS cost lever (instance tier), not a disk-bytes lever. (two sources) verified-as-of: 2026-10-18[^c3-5][^c3-2] _(Schema Design for Storage Cost)_
- A covered query is answered entirely from an index with no document reads. It requires all queried and returned fields in the index, _id excluded in the projection unless indexed, no null comparisons, and no array-field coverage on multikey indexes. On sharded collections the index must contain the shard key. MongoDB attributes the speed to index keys being smaller than documents and typically in RAM.[^c4-3][^c4-6] _(Query Efficiency as a Cost Lever)_
- Tentative: Overlapping indexes are redundant: Performance Advisor de-duplicates suggestions so only { a: 1, b: 1 } is suggested when { a: 1 } is its prefix.[^c4-2] _(Query Efficiency as a Cost Lever)_

## Anti-Patterns

- Archive queries that omit the archive partition fields (for example createdAt) scan more data and cost more, so include partition-field filters. (two sources)[^c1-6][^c1-2] _(Data Lifecycle Cost Model (TTL vs Online Archive vs Data Federation))_
- Federated query layer limits that scope the archive/federation option: no indexes on federated sources, object storage is read-only, no change streams or multi-document transactions, 30 concurrent queries per federated instance, 6-hour query limit, 16 MB document limit. (two sources) verified-as-of: 2026-10-18[^c1-4][^c1-2] _(Data Lifecycle Cost Model (TTL vs Online Archive vs Data Federation))_
- Tentative: Changing the global blockCompressor affects only newly created collections; existing collections keep their compressor. Blogs say compact does not recompress, so switching needs copy to a new collection (or dump/restore).[^c2-5] _(WiredTiger Block and Prefix Compression as Storage Cost Lever)_
- Tentative: Allegro (synthetic data): storing explicit nulls took more than 1MB per 1M documents versus omitting the field; removing the spring-data _class field cut a minimal test document by over 50%, though the percentage is much smaller for documents with many fields.[^c3-1] _(Schema Design for Storage Cost)_
- Every index must be updated on each write. Updates that change an indexed field remove and reinsert the entry in each affected index, so unused indexes add sustained disk I/O and CPU per write.[^c4-3][^c4-5][^c4-4] _(Query Efficiency as a Cost Lever)_
- Tentative: In WiredTiger, index pages compete with documents for cache space, so a large unused index reduces memory for active data and can raise latency via application-thread eviction.[^c4-5] _(Query Efficiency as a Cost Lever)_

## Troubleshooting

- TTL deletion runs on a single-threaded background task on the primary, roughly every 60 seconds; each index pass stops at 50,000 deletes or 1 second. A new TTL index or a lowered expireAfterSeconds can make a huge backlog eligible at once and cause heavy delete load; MongoDB advises creating it off-hours or pre-deleting in batches. Mass deletion can fragment storage and may need compact or initial sync to reclaim space.[^c1-3][^c1-1] _(Data Lifecycle Cost Model (TTL vs Online Archive vs Data Federation))_
- Tentative: Restoring archived data to the cluster requires pausing the archive, connecting to the archive-only endpoint and running a $merge aggregation, which incurs query charges; archive queries are also reported (anecdotally) to add seconds of latency.[^c1-6] _(Data Lifecycle Cost Model (TTL vs Online Archive vs Data Federation))_
- Deleted-document space is reused inside data files but not returned to the OS except via compact or resyncing a replica set member; dropping a collection or index frees its space. Compression savings therefore do not shrink billed disk until space is reclaimed. (two sources)[^c2-2][^c2-1] _(WiredTiger Block and Prefix Compression as Storage Cost Lever)_
- A Query Targeting alert can fire with no Performance Advisor suggestion, so advisor output is not a complete list of inefficient queries; use explain(), Query Profiler or Namespace Insights too.[^c4-1][^c4-2] _(Query Efficiency as a Cost Lever)_
- Write-penalty magnitude is workload dependent. One author benchmark (N=1, laptop, 1000-index vs no-index updates) showed about 50% slower writes at 1000 indexes and a minimal penalty at 100 indexes or fewer, assuming indexes fit in RAM. A MongoDB forum thread on ~14 indexes per collection attributes slowness to mixed causes (many collections, dhandle count, disk) rather than index count alone. (two sources)[^c4-6][^c4-4] _(Query Efficiency as a Cost Lever)_

## Disagreements & Open Questions

- Disagreement (Data Lifecycle Cost Model (TTL vs Online Archive vs Data Federation)): A oneuptime post (via search snippet) cites $0.25 vs $0.023 per GB/month, but the fetched oneuptime page gives no per-GB rates and MongoDB docs only point to the pricing page.[^c1-6][^c1-1]
- Open (Data Lifecycle Cost Model (TTL vs Online Archive vs Data Federation)): Current official per-GB/month Online Archive storage rate by provider/region (not on the docs pages; pricing page needed).
- Open (Data Lifecycle Cost Model (TTL vs Online Archive vs Data Federation)): Depth contract needs 3 independent organisations; only MongoDB and oneuptime were found, no AWS/Percona/independent cost benchmark.
- Open (Data Lifecycle Cost Model (TTL vs Online Archive vs Data Federation)): Break-even query volume (TB scanned per month) at which Online Archive stops beating cluster storage.
- Open (Data Lifecycle Cost Model (TTL vs Online Archive vs Data Federation)): Whether a paused archive still incurs storage charges.
- Disagreement (WiredTiger Block and Prefix Compression as Storage Cost Lever): One blog says compact after a restart rewrites data with the new compressor; others say compact does not change the compressor and a rebuild is required.[^c2-5]
- Disagreement (WiredTiger Block and Prefix Compression as Storage Cost Lever): Ratio figures diverge: generic blog ranges vs measured 1.4x (Percona snappy->zstd 10.75 to 7.69GB) vs Vicuesoft zstd about 1.9x smaller than snappy.[^c2-3][^c2-6]
- Open (WiredTiger Block and Prefix Compression as Storage Cost Lever): Whether Atlas lets customers set per-collection block_compressor via configString or any global default; no source confirmed.
- Open (WiredTiger Block and Prefix Compression as Storage Cost Lever): No official MongoDB doc fetched stating that compact leaves the compressor unchanged.
- Open (WiredTiger Block and Prefix Compression as Storage Cost Lever): No measured prefix-compression savings percentage found.
- Open (WiredTiger Block and Prefix Compression as Storage Cost Lever): Effect of compressing already-encrypted or pre-compressed data not covered by sources.
- Disagreement (Schema Design for Storage Cost): Percona says the MongoDB manual's 'little benefit' line ignores about three-quarters of the impact (network, oplog, cache); MongoDB says compression makes the benefit modest. Allegro (snappy) saw about 40% with short names on a tiny flat document, far above the roughly 2.5% zlib figure.[^c3-2][^c3-6][^c3-1]
- Open (Schema Design for Storage Cost): No current measurement of field-name savings under WiredTiger zstd (Atlas default is snappy) was found; negation search returned none.
- Open (Schema Design for Storage Cost): Allegro and Percona figures are synthetic and mostly chart-only; real-world savings depend on document width vs value size.
- Open (Schema Design for Storage Cost): Whether Atlas storage billing counts compressed or uncompressed bytes for each tier is out of scope here; check sibling concepts.
- Disagreement (Query Efficiency as a Cost Lever): Conventional advice says more indexes mean slower writes; the one available benchmark finds the penalty minimal below about 100 indexes if they fit in RAM, and a forum thread attributes slowness to other factors.[^c4-6][^c4-4]
- Open (Query Efficiency as a Cost Lever): Whether any MongoDB-published case study quantifies a tier reduction from index/query tuning.
- Open (Query Efficiency as a Cost Lever): Current Atlas Performance Advisor Drop Index suggestion criteria were not read.
- Open (Query Efficiency as a Cost Lever): Magnitude of index share of storage (a 20-40% figure appears only in unverified blogs and was not used).

## References

### Data Lifecycle Cost Model (TTL vs Online Archive vs Data Federation)

[^c1-1]: https://www.mongodb.com/docs/atlas/billing/online-archive/ — Online Archive Costs (docs)
[^c1-2]: https://www.mongodb.com/docs/atlas/billing/data-federation/ — Data Federation Costs (docs)
[^c1-3]: https://www.mongodb.com/docs/current/core/index-ttl/ — TTL Indexes (docs)
[^c1-4]: https://www.mongodb.com/docs/atlas/data-federation/supported-unsupported/limitations/ — Data Federation Limitations (docs)
[^c1-5]: https://mongodb.com/community/forums/t/archiving-data-to-mongodb-online-archive-or-s3-archive-which-is-best-in-performance-and-cost/226699 — Online Archive vs S3 archive thread (forum)
[^c1-6]: https://oneuptime.com/blog/post/2026-03-31-mongodb-atlas-online-archive/markdown — How to Use MongoDB Atlas Online Archive for Cold Data (blog)

### WiredTiger Block and Prefix Compression as Storage Cost Lever

[^c2-1]: https://www.mongodb.com/docs/manual/core/wiredtiger/ — WiredTiger Storage Engine (MongoDB manual) (docs)
[^c2-2]: https://www.mongodb.com/docs/manual/faq/storage/ — FAQ: MongoDB Storage (docs)
[^c2-3]: https://www.percona.com/blog/compression-methods-in-mongodb-snappy-vs-zstd/ — Compression Methods in MongoDB: Snappy vs. Zstd (Percona) (blog)
[^c2-4]: https://source.wiredtiger.com/develop/compression.html — WiredTiger compression docs (docs)
[^c2-5]: https://oneuptime.com/blog/post/2026-03-31-mongodb-snappy-zlib-zstd-compression/markdown — Choose Between Snappy, Zlib, Zstd (OneUptime) (blog)
[^c2-6]: https://vicuesoft.com/blog/titles/MongoDB_compression_options — MongoDB compression options (Vicuesoft) (blog)

### Schema Design for Storage Cost

[^c3-1]: https://blog.allegro.tech/2021/01/impact-of-the-data-model-on-the-MongoDB-database-size.html — Impact of data model on MongoDB database size (blog)
[^c3-2]: https://www.percona.com/blog/2016/03/24/percona-how-to-field-names-and-document-size-in-mongodb/ — Percona: field names and document size in MongoDB (blog)
[^c3-3]: https://www.percona.com/blog/tokumx-tip-create-any-field-name-you-want/ — TokuMX tip: Create any field name you want (blog)
[^c3-4]: https://www.mongodb.com/docs/manual/data-modeling/design-antipatterns/unnecessary-indexes/ — Remove Unnecessary Indexes (docs)
[^c3-5]: https://www.mongodb.com/docs/manual/data-modeling/design-antipatterns/bloated-documents/ — Bloated Documents (docs)
[^c3-6]: https://www.mongodb.com/blog/post/new-compression-options-mongodb-30 — New Compression Options in MongoDB 3.0 (docs)

### Query Efficiency as a Cost Lever

[^c4-1]: https://mongodb.com/docs/atlas/reference/alert-resolutions/query-targeting — Atlas alert resolution: Query Targeting (docs)
[^c4-2]: https://www.mongodb.com/docs/atlas/performance-advisor/index-ranking/ — Atlas Performance Advisor index ranking (docs)
[^c4-3]: https://www.mongodb.com/docs/manual/core/query-optimization/ — MongoDB manual: Query optimization (docs)
[^c4-4]: https://mongodb.com/community/forums/t/performance-impact-of-955-indexes-in-one-database/300227 — Forum: performance impact of 955 indexes (forum)
[^c4-5]: https://www.netdata.cloud/guides/mongodb/mongodb-unused-indexes/ — Netdata: MongoDB unused indexes (blog)
[^c4-6]: https://thecodebarbarian.com/when-should-you-use-mongodb-indexes.html — Code Barbarian: when to use MongoDB indexes (blog)
[^c4-7]: https://oneuptime.com/blog/post/2026-03-31-mongodb-right-size-atlas-clusters/markdown — OneUptime: Right-size Atlas clusters (blog)
