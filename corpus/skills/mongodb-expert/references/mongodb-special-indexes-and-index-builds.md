<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Created by deep research 2026-10-19; research dir `<local-path>

---
name: mongodb-special-indexes-and-index-builds
description: "MongoDB wildcard and compound wildcard indexes ({$**:1}, path.$**, wildcardProjection; attribute pattern; slower than targeted indexes), hidden indexes (hideIndex to test a drop safely; still maintained, still unique/TTL; no hint), index build mechanics (4.2 hybrid builds; 4.4 simultaneous builds with commitQuorum/setIndexCommitQuorum, one unreachable voter stalls; rolling builds; in-flight conflicts) and index overhead (every index costs disk, cache and write work; hot indexes plus working set should fit the WiredTiger cache). TRIGGER: 'wildcard index for unknown fields', 'is it safe to drop this index', 'hide an index', 'index build stuck waiting for quorum', 'rolling index build', 'write cost of an index', 'indexes fit in RAM'. SKIP: key order/ESR/covering -> mongodb-compound-index-design; explain/plan cache -> mongodb-explain-plans-and-query-planner; every index type -> mongodb-indexes-deep; upgrade-time FCV changes -> mongodb-operations-expert."
version: "1.0.0"
updated: "2026-10-19"
category: "research"
whenToUse:
  - "decide whether a wildcard index fits unknown field names"
  - "test dropping an index by hiding it first"
  - "unblock or plan an index build on a replica set or sharded cluster"
  - "estimate what an extra index costs on writes and RAM"
keywords: ["wildcard index", "compound wildcard index", "wildcardProjection", "hidden index", "hideIndex", "index build", "hybrid index build", "commitQuorum", "setIndexCommitQuorum", "rolling index build", "index build conflict", "index overhead", "write amplification", "totalIndexSize", "prefix compression"]
tags: ["mongodb", "indexes", "index-builds", "wildcard", "hidden-index"]
provenance: "deep research · <local-path>
---

# MongoDB Wildcard and Hidden Indexes, Index Builds and Index Overhead

## Overview

A wildcard index ({"$**": 1} or {"path.$**": 1}) indexes every scalar value under a path, so queries on unknown or varying field names can use an index. Compound wildcard indexes (new in MongoDB 7.0) pair exactly one wildcard term with regular single-key terms, covering the attribute pattern (e.g. tenantId + customFields.$**). MongoDB's own docs say wildcard indexes perform worse than targeted indexes and should be used only when fields are unknown. Key limits: one query predicate per wildcard term, sparse (no $exists:false), no unique/TTL/text/hashed/geo, no shard key, strict wildcardProjection rules (tightened in 8.3/8.2.4/8.0.18/7.0.29). Azure Cosmos DB for MongoDB implements a different, divergent wildcard model.

A hidden index is a normal index the query planner ignores. Hiding lets you test the effect of dropping an index without dropping it: if queries regress, unhide, and the index is usable at once because it was fully maintained. Hiding saves nothing on writes, disk or memory. Hidden unique indexes still enforce uniqueness, and hidden TTL indexes still expire documents. Restrictions: the _id index cannot be hidden, cursor.hint() cannot use a hidden index, and hiding or unhiding resets $indexStats. Current docs (9.0) require featureCompatibilityVersion 7.0 or higher to hide an index. The feature arrived in 4.4. Hiding is a collMod / hideIndex operation, so it is the safe step before dropping an index judged unused.

Since MongoDB 4.2 every index build is a single optimized hybrid build: exclusive lock only briefly at start and end, collection scan yields to reads and writes, concurrent writes go to a side-writes table that is drained later. Since 4.4 (FCV 4.4+), replica set and sharded builds run simultaneously on all data-bearing members, committed once a commit quorum votes. The alternative is a manual rolling build: one member at a time is hidden, restarted standalone, indexed, and rejoined, then the primary is stepped down and done last. MongoDB recommends rolling only under CPU or cache pressure, because it lowers resiliency, lengthens the build and needs an election. A 2022 critical alert showed rolling builds via Atlas/Cloud Manager/Ops Manager could leave inconsistent indexes after rollback or crash.

Since MongoDB 4.4 (FCV 4.4+), index builds on replica sets and sharded clusters run simultaneously on all data-bearing members. Secondaries start on the startIndexBuild oplog entry and vote to the primary. The primary commits only after commitQuorum votes (default votingMembers = all data-bearing voting members), then writes commitIndexBuild; a constraint violation produces abortIndexBuild. With the default quorum, one unreachable voter stalls the build. setIndexCommitQuorum can lower the quorum mid-build, but not for builds started with 0, and it had a bug (SERVER-56976, fixed 4.4.7/5.0). In-flight builds are stopped with dropIndexes (whole createIndexes batch), not killOp. Commit quorum is not write concern. Rolling and replicated builds must not be mixed.

Every index costs disk, cache and write work. A write that changes an indexed field makes MongoDB update every index keyed on that field; inserts and deletes touch all indexes. In WiredTiger, index pages compete with documents for the internal cache. Cached indexes use a different layout than on disk but keep prefix compression, which reduces RAM use. Performance is best when hot indexes plus working set fit in memory; this is a recommendation, not a hard rule, except for the in-memory engine. Random-valued indexes (hashed, UUID) are the worst case: once the index outgrows cache, each insert evicts and reloads pages. Per-index size is read from collStats indexSizes, and $indexStats finds unused indexes to drop. Hard numeric overhead per index is not given by official docs.

## Core Concepts

### Wildcard and Compound Wildcard Indexes

- Wildcard indexes are intended for queries on fields whose names are unknown, vary between documents, or live in inconsistent embedded documents. MongoDB's manual says to use them only when the indexed fields are unknown or may change, and that they do not perform as well as targeted indexes on specific fields.[^c1-3][^c1-2]
- Compound wildcard indexes were introduced in MongoDB 7.0. They hold one wildcard term plus one or more regular terms, e.g. { tenantId: 1, "customFields.$**": 1 } or { Region: 1, "Attributes.$**": 1 }, and target the attribute pattern so one index serves many dynamic sub-field queries.[^c1-2][^c1-4][^c1-6]
- A wildcard index supports only one query predicate field per query; other predicates are resolved without it and unsupported ones show in rejectedPlans in explain output. In a compound wildcard index the wildcard term supports one predicate while the regular terms can support the rest. The planner may reuse the same wildcard index for each independent $or argument.[^c1-1][^c1-2]
- Since MongoDB 7.0, wildcard indexes support both ascending and descending sort order; earlier versions allowed only ascending. (two sources)[^c1-1][^c1-2]

### Hidden Indexes

- A hidden index is not visible to the query planner and cannot support a query. Hiding it lets you evaluate the impact of dropping the index without dropping it; if the impact is negative, you unhide it instead of rebuilding it.[^c2-1][^c2-3]
- Apart from planner visibility, a hidden index behaves like an unhidden one: a hidden unique index still enforces its unique constraint, a hidden TTL index still expires documents, and the index still appears in listIndexes and getIndexes() with "hidden": true.[^c2-1][^c2-3]
- Restrictions: the _id index cannot be hidden, and cursor.hint() cannot force a hidden index.[^c2-1][^c2-2]
- In the 9.0 manual, hiding an index (hideIndex / collMod) and creating one with createIndex({...},{hidden:true}) both require featureCompatibilityVersion 7.0 or greater. Earlier manual versions listed lower thresholds (4.4 for the original feature), so check the FCV of an older deployment. (two sources) verified-as-of: 2026-10-19[^c2-1][^c2-2]

### Index Build Strategies

- Since MongoDB 4.2 all index builds use one optimized process: an exclusive X lock on the collection only at the start and end, with the middle phase downgraded to IX and yielding to reads and writes. The old foreground/background distinction is gone and the `background` option is ignored.[^c3-1][^c3-4]
- During the build, writes to the collection are recorded as keys in a temporary side-writes table that is drained FIFO. A shared S lock (blocks writes) and then a final X lock are held only while the last records drain and the index is committed. Key-generation errors go to a constraint-violation table checked at the end. (two sources)[^c3-1][^c3-2]
- On replica sets and sharded clusters with featureCompatibilityVersion 4.4+, a build runs simultaneously on all data-bearing members (on sharded clusters only on shards holding the collection). The primary writes startIndexBuild, members vote when done scanning, and the primary writes commitIndexBuild after a commit quorum (default votingMembers) votes and no constraint violation is found; otherwise abortIndexBuild.[^c3-1][^c3-3]

### Index Build Conflicts and Commit Quorum and In-Flight Builds

- From MongoDB 4.4, index builds on a replica set or sharded cluster run simultaneously on all data-bearing members (on sharded clusters only on shards holding data for the collection). The primary needs a commit quorum of data-bearing voting members, itself included, to finish before it marks the index ready. This requires featureCompatibilityVersion 4.4+ on every mongod.[^c4-1][^c4-2][^c4-3]
- Replicated build protocol: primary writes a startIndexBuild oplog entry; secondaries build after replicating it and vote by writing to an internal replicated collection on the primary; once the quorum is met and no key-constraint violations remain, the primary writes commitIndexBuild. On a violation the primary aborts and writes abortIndexBuild, and secondaries discard the build job. (two sources)[^c4-1][^c4-4]
- commitQuorum accepts 'votingMembers' (default, all data-bearing voting members), 'majority', a positive integer, a replica-set tag name, or 0. Nodes with buildIndexes:false cannot be in a quorum, so if any voting node has buildIndexes:false the default votingMembers cannot be used.[^c4-2][^c4-3][^c4-4]
- Commit quorum is not write concern. It does not guarantee secondary indexes are usable when createIndexes returns. A secondary receiving commitIndexBuild stops applying further oplog entries until its local build commits, so slow builds on secondaries (including ones outside the quorum) cause replication lag. Since 8.0 write concern controls how many nodes must replicate the commitIndexBuild entry before success returns; before 8.0 it controlled how many nodes had finished building. (two sources) verified-as-of: 2026-10-19[^c4-3][^c4-1]
- Index builds take exclusive X locks only at start and end, plus a shared S lock during the final side-writes drain. These blocks cover reads, writes, replicated writes and metadata commands on the collection. Writes during the build are held in a side writes table, and key-constraint violations are recorded and checked at commit time rather than rejecting writes. (two sources)[^c4-1][^c4-2]
- Tentative: maxNumActiveUserIndexBuilds caps concurrent index builds; builds beyond the limit block until the count drops.[^c4-1]

### Index Storage and RAM Fit and Write-Path Overhead

- If a write modifies an indexed field, MongoDB updates all indexes that have that field as a key, so write-heavy applications can see index maintenance affect performance.[^c5-1][^c5-4]
- Every insert adds entries to all indexes, every delete removes entries from all indexes, and an update that changes an indexed field removes the old entry and adds a new one in each affected index. (two sources)[^c5-3][^c5-1]
- Indexes in the WiredTiger internal cache use a different representation than on disk but still benefit from index prefix compression, which deduplicates common prefixes and reduces RAM use. Prefix compression is the default for all indexes and can be disabled via storage.wiredTiger.indexConfig.prefixCompression. (two sources)[^c5-2][^c5-3]
- Fitting hot indexes and the working set in RAM is a performance recommendation, not a strict requirement for most storage engines; MongoDB staff said the docs' 'must' should read 'should'. The In-Memory Storage Engine (Enterprise) does require all data to fit in inMemorySizeGB. (two sources)[^c5-5][^c5-2]

## Tools & Frameworks

- db.collection.hideIndex() and unhideIndex() are mongosh wrappers for the collMod command (index.hidden option). They accept an index name or key document; a text index must be hidden by name. Required privilege is collMod on the database (built-in role dbAdmin). Hiding an already hidden index is a no-op that still writes an empty oplog entry. (two sources)[^c2-2][^c2-1] _(Hidden Indexes)_
- Self-hosted index builds default to maxIndexBuildMemoryUsageMegabytes=200 per createIndexes command, split equally across the indexes in that command, spilling to _tmp under --dbpath. With the default maxNumActiveUserIndexBuilds=3, total can reach 3x. Raising it is rarely needed (many indexes in one command, or data over 500GB). On Atlas the defaults vary by tier and maxIndexBuildMemoryUsageMegabytes cannot be changed. (two sources) verified-as-of: 2026-10-14[^c3-1][^c3-4] _(Index Build Strategies)_
- MongoDB 7.1 added early error reporting during the collection scan (except duplicate keys), a secondary can ask the primary to abort a failing build instead of crashing (unless it already voted to commit), and indexBuildMinAvailableDiskSpaceMB can stop builds when free disk is low; earlier versions do not stop on low disk. (two sources) verified-as-of: 2026-10-14[^c3-1][^c3-3] _(Index Build Strategies)_
- setIndexCommitQuorum changes the quorum of an in-progress build. indexNames must list the entire set of in-progress builds from one createIndexes call, and it has no effect on builds started with commitQuorum 0.[^c4-3][^c4-1] _(Index Build Conflicts and Commit Quorum and In-Flight Builds)_
- Stop an in-flight build with dropIndexes (or dropIndex helpers), not killOp: the docs say not to use killOp on replica sets or sharded clusters. dropIndexes aborts the build via abortIndexBuild, and it must name every index from the same createIndexes batch. Percona's post instead says killOp cancels the build, which conflicts with the docs. (two sources)[^c4-1][^c4-4] _(Index Build Conflicts and Commit Quorum and In-Flight Builds)_
- Per-index size is available from the indexSizes document in db.collection.stats() (collStats); $indexStats gives per-index usage counters used to find unused indexes before dropping them.[^c5-1][^c5-4] _(Index Storage and RAM Fit and Write-Path Overhead)_

## Methodology

- wildcardProjection works only when the wildcard term is $** (not a path like someFields.$**). Wildcard indexes omit _id by default; include it with $** or by adding _id: 1 to wildcardProjection. A field cannot appear both in the wildcard pattern and as a regular compound term; use exclusions in wildcardProjection to remove it.[^c1-1][^c1-2][^c1-3] _(Wildcard and Compound Wildcard Indexes)_
- Tentative: Workflow shown by Percona: run explain() to see which index wins, hideIndex(), re-run explain() to confirm the planner picks another plan (the hidden index is absent from rejected plans too), then unhideIndex() if the plan regresses.[^c2-3] _(Hidden Indexes)_
- A rolling index build hides and sets priority 0 on one secondary at a time, restarts it as a standalone (no replSetName, different port, disableLogicalSessionCacheRefresh=true), runs createIndex, restarts it as a member, waits for catch-up and unhides it. After all secondaries, rs.stepDown() the primary and repeat on the former primary.[^c3-3][^c3-4] _(Index Build Strategies)_
- Tentative: Dropping an unused index takes an exclusive collection lock and can stall concurrent writes; run it in a quiet window and watch globalLock.currentQueue and opLatencies.writes before and after.[^c5-3] _(Index Storage and RAM Fit and Write-Path Overhead)_

## Practical Patterns

- A wildcard index can satisfy a sort only if the planner picks it for the predicate, the sort names only the predicate field, and that field is never an array. A covered query additionally needs exactly one wildcard-covered predicate field and a projection that excludes _id and includes only that field.[^c1-1][^c1-3][^c1-6] _(Wildcard and Compound Wildcard Indexes)_
- Consolidating many single-field indexes into one wildcard index helps stay under the 64-index-per-collection limit. A collection may hold several wildcard indexes and they may overlap other indexes. Compound wildcard indexes are sparse: a document is indexed if it has at least one of the compound fields. (two sources)[^c1-2][^c1-3] _(Wildcard and Compound Wildcard Indexes)_
- Because a hidden index is fully maintained, unhiding takes effect immediately with no rebuild. Dropping an index, by contrast, requires a full rebuild to undo.[^c2-1][^c2-2] _(Hidden Indexes)_
- MongoDB advises rolling builds only if average CPU exceeds (N-1)/N - 10% (N = CPU threads available to mongod) or WiredTiger cache fill regularly exceeds 90%; otherwise use the default build. Rolling builds lower cluster resiliency, increase build duration, require at least one election, and are not supported on Atlas Infinite clusters. verified-as-of: 2026-10-14[^c3-2][^c3-3] _(Index Build Strategies)_
- Heavy write load on the target collection reduces write performance and lengthens the build; MongoDB recommends a maintenance window with reduced writes. Unique-index duplicates are only detected at the end of the build, so validate data first or stop non-compliant writers. (two sources)[^c3-1][^c3-2] _(Index Build Strategies)_
- Tentative: For a bulk load, creating the index after the insert sorts data in memory and performs an ordered insert on all indexes, which the FAQ presents as the remedy for random-insert slowdown.[^c5-1] _(Index Storage and RAM Fit and Write-Path Overhead)_

## Anti-Patterns

- A compound wildcard index may contain only one wildcard term (e.g. { userID: 1, "object1.$**": 1, "object2.$**": 1 } is rejected), and its non-wildcard terms must be single-key; multikey (array) terms are not allowed.[^c1-1][^c1-6] _(Wildcard and Compound Wildcard Indexes)_
- Wildcard indexes cannot be unique, TTL, text, hashed, 2d or 2dsphere, cannot serve $text queries, and cannot be a shard key index. They are sparse: they do not index documents missing the field (null values are indexed), so they cannot serve { field: { $exists: false } }.[^c1-1][^c1-3][^c1-5] _(Wildcard and Compound Wildcard Indexes)_
- Tentative: Wildcard indexes store the contents of documents and arrays, not the containers, so exact equality or inequality on a whole embedded document or array (e.g. { "product_attributes": { price: 29.99 } }) is unsupported (matching {} is the exception). If a field is an array in any document, the index cannot support $ne null on it.[^c1-1] _(Wildcard and Compound Wildcard Indexes)_
- Hiding an index does not reduce write cost or storage. Hidden indexes are updated on every write and keep consuming disk space and memory, and they still count in db.collection.stats() and $indexStats.[^c2-1][^c2-2] _(Hidden Indexes)_
- The oplog must be large enough to cover the whole rolling build on each member. A member that falls off the oplog window must do a full resync.[^c3-3][^c3-4] _(Index Build Strategies)_
- For a unique index, the rolling procedure requires stopping all writes to the collection for the duration; otherwise members can diverge. If writes cannot be stopped, run createIndex on the primary instead. (two sources)[^c3-3][^c3-1] _(Index Build Strategies)_
- Never run rolling and replicated (default) index builds concurrently; MongoDB warns of broken builds and crash loops.[^c3-2][^c3-1] _(Index Build Strategies)_
- Do not run rolling index builds and replicated (simultaneous) builds concurrently; the docs warn of broken builds and crash loops. (two sources)[^c4-1][^c4-5] _(Index Build Conflicts and Commit Quorum and In-Flight Builds)_
- Bulk inserts of random data (for example hashed indexes) create random index entries. Once each insert touches a different index entry, the index no longer fits in cache, WiredTiger cache eviction and replacement rate rises, and insert performance drops.[^c5-1][^c5-3] _(Index Storage and RAM Fit and Write-Path Overhead)_

## Troubleshooting

- Tentative: Starting in MongoDB 8.3, 8.2.4, 8.0.18 and 7.0.29, stricter wildcardProjection validation applies to compound wildcard indexes: projection cannot be empty; inclusions and exclusions cannot be mixed except for _id; included fields cannot overlap regular index fields; an _id-only exclusion needs _id as a regular index field; an exclusion projection must exclude all regular index fields. Existing non-compliant indexes keep working; new ones cannot be created. verified-as-of: 2026-10-19[^c1-1] _(Wildcard and Compound Wildcard Indexes)_
- Azure Cosmos DB for MongoDB diverges: its docs say wildcard indexes there can support multiple fields in query predicates with no performance difference versus per-property indexes, but they cannot be compound, TTL or unique, and cannot use wildcardProjection with multiple specific fields (include or exclude). Cosmos advises individually indexed paths for write-heavy workloads because wildcard indexing of many-field documents raises write RU charges. Do not assume Cosmos behavior matches MongoDB Server. (two sources) verified-as-of: 2026-04-27[^c1-5][^c1-1] _(Wildcard and Compound Wildcard Indexes)_
- Tentative: No benchmark or measured numbers for wildcard or compound wildcard index performance appeared in any source read; vendor and blog claims of efficiency ("efficiently and easily", "fewer system resources") are unquantified.[^c1-4] _(Wildcard and Compound Wildcard Indexes)_
- Hiding an unhidden index, or unhiding a hidden one, resets that index's $indexStats counters. Hiding an already hidden index (or unhiding an unhidden one) does not reset them. Usage counts gathered before the toggle are lost, so record them first.[^c2-1][^c2-2] _(Hidden Indexes)_
- Tentative: A community forum test reported that hiding an index on the primary also showed as hidden on a secondary, i.e. the hide replicates (anecdotal, single test). Because the toggle is a collMod oplog entry, it is expected to replicate.[^c2-4] _(Hidden Indexes)_
- Tentative: Rolling index builds driven by Atlas, Cloud Manager and Ops Manager (affected MongoDB 4.2.19+, 4.4.13+, 5.0.6+, 6.0.0+; agent 11.13.0.7438-1 to 12.4.0.7702-1) could create indexes with log=(enabled=true), so after a replication rollback or primary crash the indexes were not rolled back with the documents, giving missing or extra entries and wrong query results. Unique indexes were not affected. Remediation: run validate per node, resync bad nodes, upgrade the agent. verified-as-of: 2026-10-19[^c3-5] _(Index Build Strategies)_
- Tentative: Interrupted builds: on a replica set with default commit quorum, a clean shutdown or SIGTERM saves progress and the build resumes once from the checkpoint (since 5.0 also across rollbacks); a crash restarts from scratch. A member restarted as standalone leaves the build paused until dropped. A standalone mongod loses the build entirely. Use dropIndexes, not killOp, to stop a replicated build.[^c3-1] _(Index Build Strategies)_
- With the default votingMembers quorum, an unreachable data-bearing voting member makes the createIndexes hang until it returns. Percona's test (3-node, one down) ran about 4,678 s; the index was listed by getIndexes() but unusable and queries used COLLSCAN. With 'majority' the same build finished in about 2.5 s.[^c4-1][^c4-4] _(Index Build Conflicts and Commit Quorum and In-Flight Builds)_
- Tentative: Bug SERVER-56976: a build already waiting for votes did not pick up a setIndexCommitQuorum change (found after a half-finished rolling build left one secondary with the index, which treated startIndexBuild as a no-op). Affected 4.4.6 and 5.0.0; fixed in 4.4.7 and 5.0.0-rc0/5.1.0-rc0. On old 4.4.x/5.0.0 binaries lowering the quorum may not unstick a build.[^c4-5] _(Index Build Conflicts and Commit Quorum and In-Flight Builds)_
- Interrupted builds resume from a checkpoint only after a clean shutdown (force:true or SIGTERM) with commit quorum votingMembers. A crash restarts the build from the beginning, and a checkpoint resume works only once per build. Restarting as a standalone cannot restart the build. (two sources)[^c4-1][^c4-3] _(Index Build Conflicts and Commit Quorum and In-Flight Builds)_
- Tentative: Index pages compete with documents for WiredTiger cache. A large unused index leaves less cache for active data, and if eviction threads fall behind, application threads perform eviction themselves and add latency.[^c5-3] _(Index Storage and RAM Fit and Write-Path Overhead)_
- Tentative: When WiredTiger runs in a container with less RAM than the host, it may not honor the container limit; set the WiredTiger cache explicitly and check the effective limit with the hostInfo command.[^c5-2] _(Index Storage and RAM Fit and Write-Path Overhead)_

## Disagreements & Open Questions

- Disagreement (Wildcard and Compound Wildcard Indexes): Multi-field predicates: MongoDB Server docs say a wildcard index supports only one query predicate field per query; Azure Cosmos DB for MongoDB docs say its wildcard indexes can support multiple fields in query predicates with no performance difference.[^c1-1][^c1-5]
- Open (Wildcard and Compound Wildcard Indexes): Exact release in which wildcardProjection stricter validation lands per branch beyond 8.3/8.2.4/8.0.18/7.0.29 (e.g. 6.0 not addressed; compound wildcard is 7.0+).
- Open (Wildcard and Compound Wildcard Indexes): No independent benchmark of wildcard vs targeted or compound indexes found; magnitude of query and write-path penalty unquantified.
- Open (Wildcard and Compound Wildcard Indexes): The restrictions page lists incompatible types with the string "$.**", apparently a typo for "$**".
- Disagreement (Hidden Indexes): featureCompatibilityVersion threshold differs by manual version: Percona (4.4) says FCV 4.4, older manuals listed 5.0/6.0, the 9.0 manual says 7.0 for both hiding and createIndex hidden:true.[^c2-3][^c2-1]
- Open (Hidden Indexes): Whether hiding or unhiding invalidates cached plans on each member; no source found.
- Open (Hidden Indexes): Whether hidden-index tests on a primary give valid results when secondaries serve reads (plan cache is per member); unconfirmed.
- Open (Hidden Indexes): Exact FCV threshold per server version (5.0/6.0/7.0 history) was only seen via search snippets, not fetched.
- Open (Hidden Indexes): Only one independent non-vendor source (Percona, 2020) was found; the 'negation' round found no contradicting evidence.
- Disagreement (Index Build Strategies): Percona (2019, 3.4/3.6 era) builds the index in foreground on the detached node and recommends plain background builds for indexes that fit in memory; current docs say foreground/background no longer exist and rolling is only for CPU/cache pressure. Percona's default build memory figure (500 MB) also differs from the current 200 MB default.[^c3-4][^c3-1]
- Disagreement (Index Build Strategies): Current rolling-builds page says members are 'hidden'; the 6.3 tutorial procedure hides and sets priority 0 on the member, while Percona's 2019 procedure only detaches it as standalone.[^c3-2][^c3-4]
- Open (Index Build Strategies): Only two organisations (MongoDB, Percona) were deep-read; no independent post-4.4 third-party benchmark of default vs rolling build impact was found.
- Open (Index Build Strategies): The critical alert page gives no publication date; the slug says Sept 2022 but the page states an Atlas fix on 2023-08-22. Date discrepancy unresolved.
- Open (Index Build Strategies): A March 2026 oneuptime blog (not fetched, search snippet only) claims rolling builds can use replSetMaintenance mode; this is absent from official docs and was not relied on.
- Open (Index Build Strategies): Whether Atlas performs its own rolling builds for UI-created indexes was not confirmed.
- Open (Index Build Strategies): The 6.3 tutorial was cited for the procedure; the current manual version may differ slightly (current /manual page text was read via library only for the .md twin).
- Open (Index Build Strategies): Early 4.4 Jira tickets reportedly described a 'majority' commit quorum default vs current votingMembers; not verified.
- Disagreement (Index Build Conflicts and Commit Quorum and In-Flight Builds): Percona says killOp cancels a stalled build; MongoDB docs say never to use killOp on replica sets/sharded clusters and to use dropIndexes. A reader comment on Percona suggests setIndexCommitQuorum instead.[^c4-4][^c4-1]
- Disagreement (Index Build Conflicts and Commit Quorum and In-Flight Builds): Early 4.4 driver tickets disagreed on the default commitQuorum ('votingMembers' vs 'all'); current docs say votingMembers.[^c4-2]
- Open (Index Build Conflicts and Commit Quorum and In-Flight Builds): How collMod and other DDL conflict with in-flight builds (searches found nothing; docs only say X/S locks block metadata commands at the end stages).
- Open (Index Build Conflicts and Commit Quorum and In-Flight Builds): Exact error code/message when DDL hits a collection with a build in flight (pre-5.2 BackgroundOperationInProgressForNamespace for dropIndex on another index).
- Open (Index Build Conflicts and Commit Quorum and In-Flight Builds): The 8.3 behavior where a secondary that already voted cannot request a stop and crashes.
- Disagreement (Index Storage and RAM Fit and Write-Path Overhead): Older manual wording said indexes 'must' fit in RAM; a MongoDB staff reply (2020) says this should be 'should', and it is not strict outside the in-memory engine.[^c5-5]
- Open (Index Storage and RAM Fit and Write-Path Overhead): The 'Ensure Indexes Fit in RAM' tutorial returned 404 on current and v5.0 docs paths, so the right-most-index exception was seen only in search snippets and is not claimed.
- Open (Index Storage and RAM Fit and Write-Path Overhead): No official or independent benchmark quantifies per-index write cost; a single-run unofficial benchmark seen only in a search snippet was not verified.

## References

### Wildcard and Compound Wildcard Indexes

[^c1-1]: https://www.mongodb.com/docs/upcoming/core/indexes/index-types/index-wildcard/reference/restrictions/ — Wildcard Index Restrictions (MongoDB docs, upcoming) (docs)
[^c1-2]: https://mongodb.com/docs/v7.0/core/indexes/index-types/index-wildcard/index-wildcard-compound — Compound Wildcard Indexes (MongoDB 7.0 docs) (docs)
[^c1-3]: https://www.mongodb.com/docs/manual/core/index-wildcard/ — Wildcard Indexes (MongoDB manual) (docs)
[^c1-4]: https://mongodb.com/blog/post/query-enhancement-mongodb-7-0 — Crafting Precision: Query Enhancements in MongoDB 7.0 (blog)
[^c1-5]: https://learn.microsoft.com/en-us/azure/cosmos-db/mongodb/indexing — Manage Indexing - Azure Cosmos DB for MongoDB (docs)
[^c1-6]: https://oneuptime.com/blog/post/2026-03-31-mongodb-new-features-7-compound-wildcard-indexes-automerger/markdown — How to Use New Features in MongoDB 7.0 (Compound Wildcard Indexes, AutoMerger) (blog)

### Hidden Indexes

[^c2-1]: https://www.mongodb.com/docs/manual/core/index-hidden/ — Hidden Indexes (MongoDB manual 9.0) (docs)
[^c2-2]: https://www.mongodb.com/docs/manual/reference/method/db.collection.hideIndex/ — db.collection.hideIndex() (docs)
[^c2-3]: https://www.percona.com/blog/new-in-mongodb-4-4-hidden-index/ — New in MongoDB 4.4: Hidden Index (Percona, 2020-11-05) (blog)
[^c2-4]: https://www.mongodb.com/community/forums/t/hiding-index-replication-ops-manager/270730 — Hiding Index Replication Ops Manager (forum)

### Index Build Strategies

[^c3-1]: https://www.mongodb.com/docs/manual/core/index-creation.md — Index Builds on Populated Collections (docs)
[^c3-2]: https://www.mongodb.com/docs/manual/core/rolling-index-builds.md — Rolling Index Builds (docs)
[^c3-3]: https://www.mongodb.com/docs/v6.3/tutorial/build-indexes-on-replica-sets — Create a Rolling Index Build on Replica Sets (docs)
[^c3-4]: https://www.percona.com/blog/mongodb-impact-free-index-builds-using-detached-replicaset-nodes/ — MongoDB: Impact-free Index Builds using Detached ReplicaSet Nodes (Percona, 2019) (blog)
[^c3-5]: https://mongodb.com/alerts/critical-alert-mongodb-rolling-index-build-issue-sept-2022 — Critical Alert: MongoDB Rolling Index Build Issue (postmortem)

### Index Build Conflicts and Commit Quorum and In-Flight Builds

[^c4-1]: https://www.mongodb.com/docs/manual/core/index-creation/ — Index Builds on Populated Collections (docs)
[^c4-2]: https://www.mongodb.com/docs/manual/reference/command/createIndexes/ — createIndexes (database command) (docs)
[^c4-3]: https://www.mongodb.com/docs/manual/reference/command/setindexcommitquorum/ — setIndexCommitQuorum (docs)
[^c4-4]: https://www.percona.com/blog/commitquorum-in-index-creation-from-percona-server-for-mongodb-4-4/ — commitQuorum in Index Creation from Percona Server for MongoDB 4.4 (blog)
[^c4-5]: https://jira.mongodb.org/browse/SERVER-56976 — SERVER-56976 setIndexCommitQuorum has no effect while waiting for quorum (forum)

### Index Storage and RAM Fit and Write-Path Overhead

[^c5-1]: https://www.mongodb.com/docs/manual/faq/indexes.md — FAQ: Indexes (docs)
[^c5-2]: https://www.mongodb.com/docs/manual/core/wiredtiger/ — WiredTiger Storage Engine (MongoDB manual) (docs)
[^c5-3]: https://www.netdata.cloud/guides/mongodb/mongodb-unused-indexes/ — Netdata: MongoDB unused indexes (blog)
[^c5-4]: https://www.percona.com/blog/2018/11/21/identifying-unused-indexes-in-mongodb/ — Percona: Identifying unused indexes in MongoDB (2018-11-21) (blog)
[^c5-5]: https://www.mongodb.com/community/forums/t/working-set-must-fit-in-memory/3287 — Working set MUST fit in memory? (2020-04-30) (forum)
