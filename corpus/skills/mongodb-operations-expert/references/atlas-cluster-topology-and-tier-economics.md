<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Created by `/dr` deep research 2026-10-19; research dir `<local-path>`.

---
name: atlas-cluster-topology-and-tier-economics
description: "Atlas cluster topology and tier economics: tier families (General vs Low-CPU R-tiers vs NVMe fixed-storage tiers); replica set node cost (electable, read-only, analytics nodes; three-node minimum); sharded cluster cost (replication factor x shards, config servers, 8.0 config shards); data transfer tiers (same-region vs cross-region vs internet); storage and IOPS forecasting (provisioned GB, 90% auto-scaling, Gen2 IOPS); Search Nodes (S-tier node-hours, 2-node minimum); vector quantization (scalar 3.75x, binary 24x mongot RAM). TRIGGER: Low-CPU vs General tier; NVMe tier cost; analytics node tier; what sharding costs; cross-region transfer bill; storage auto-scaling cost; Search Node pricing; quantization memory savings. SKIP: invoice line items -> atlas-billing-mechanics-and-cost-visibility; compression and archive -> storage-and-data-lifecycle-cost-levers; Flex pricing -> atlas-pricing-programs-cost-governance-and-tco."
version: "1.0.0"
updated: "2026-10-19"
category: "research"
whenToUse:
  - "compare Low-CPU, General and NVMe Atlas tiers on cost"
  - "estimate what a sharded or multi-region Atlas cluster will cost"
  - "forecast storage and IOPS growth cost"
  - "size Search Nodes or quantize vectors to cut cost"
keywords: ["low-cpu tier", "NVMe tier", "R40", "analytics node", "electable nodes", "sharded cluster cost", "config servers", "config shard", "data transfer cost", "cross-region", "storage auto-scaling", "IOPS", "Gen2", "search nodes", "S20", "vector quantization", "binary quantization"]
tags: ["mongodb", "atlas", "cost", "cluster-tiers", "sharding", "topology", "data-transfer", "search-nodes", "vector-search"]
provenance: "/dr · <local-path>"
---

# Atlas Cluster Topology and Tier Economics

## Overview

Atlas dedicated clusters come in three tier families at the same M-size. General has the standard vCPU count. Low-CPU (API names R40, R50) keeps RAM and storage but halves vCPUs at a lower hourly price. NVMe (M40_NVME etc.) uses locally attached ephemeral SSD with fixed storage tied to the tier, on AWS and Azure only, with several operational restrictions. The only public hourly figures found are AWS us-east-1 numbers calculated in January 2022, so they are stale; no public NVMe hourly price was found.

An Atlas replica set's cost scales with the count and tier of data-bearing nodes. Electable nodes (3, 5 or 7 total) provide high availability and elections. Read-only nodes add regional read capacity but do not vote. Analytics nodes isolate reporting reads, do not vote, and can use a different tier than the operational nodes, priced prorated per node. Atlas uses one tier for all data-bearing operational nodes, so going from 3 to 5 electable nodes raises compute roughly in proportion to node count at the same tier, with no extra write throughput. Arbiters, the self-managed cost shortcut, are documented for self-managed sets only; the manual does not describe them for Atlas. Multi-region topologies add data transfer charges. Docs do not state whether same-region replication traffic is billed.

Atlas bills a sharded cluster as replication factor x shard count data-bearing nodes at the chosen tier, plus three config servers at a separate flat rate that tier and storage choices do not change. Documentation does not mention a mongos charge. Backup storage also sums the config replica set and may temporarily grow when topology changes. Every shard must have the same node counts, storage and NVMe tier, though shards may differ in compute tier under independent shard scaling (default for clusters created after 2024-12-09). MongoDB advises considering another shard at sustained 60-70% utilization of a large tier (M60 with 4 TB example) and says vertical scaling gets costlier at the top end. MongoDB 8.0 config shards (Atlas default for up to 3 shards) remove dedicated config server cost. Cost and operational downsides: wasteful shard-key mistakes, scatter-gather queries, slow resharding.

Atlas passes cloud-provider data transfer charges through to customers, tabulated daily, in tiers from cheapest to dearest: same-region, cross-region, then internet and cross-cloud. MongoDB's AWS pricing page lists $0.01/GB same-region, $0.02/GB cross-region and $0.09/GB internet, and says transfer is under 10% of the bill for most customers. Multi-region clusters cost more because replication crosses region boundaries, but the docs give no formula. Cross-cloud, on-premises-to-Atlas and cross-continent paths are named as the highest-cost paths. No official Atlas cross-cloud rate table was found. Atlas also bills intra-cluster replication and heartbeats as same-region transfer, and a 2025 AWS NLB metering fix raised that line slightly for PrivateLink users. Mitigations are nearest reads, writes from the highest-priority region, projection and driver compression.

On Atlas Core dedicated clusters, storage is billed per provisioned GB, not per GB used, and IOPS is tied to disk size (Gen1, Azure, GCP) or has a size-based baseline plus separately billed Extended Standard IOPS (Gen2 on AWS/GCP). Storage auto-scaling is on by default, triggers at 90% used on any node, targets 70% used, and only goes up. It can force a tier upgrade when the disk exceeds the tier's max storage. Manual shrinking is done by provisioning new volumes and resyncing, with per-node downtime. AWS EBS allows four modifications per volume per rolling 24 hours, so changes can be delayed. A forecast must therefore model disk as a ratchet: size to the 70% target, include about 20% WiredTiger overhead, and treat IOPS as either free with capacity or a paid add-on.

Atlas Search (mongot) runs either co-located on the database nodes (mongod) at no extra fee, or on dedicated Search Nodes billed per node-hour. Co-located is cheapest but shares CPU/RAM with the database and is documented for testing and prototyping only. Dedicated Search Nodes need an M10+ cluster, a minimum of two nodes (max 32 per region per shard), and bill by tier (S20 and up; S10 added July 2026) and node class (high-CPU, low-CPU, storage-optimized). Cloud and region change the hourly rate. Cost levers: node class matched to the bottleneck (storage vs CPU vs RAM), tier right-sizing from measured index size and QPS, per-region node counts in multi-region clusters, and search-to-database network transfer, billed at cluster level. All evidence found is MongoDB-authored; no independent cost study or user report surfaced.

Atlas Vector Search can shrink the in-memory footprint of embeddings with automatic scalar (int8) or binary (int1) quantization, or by ingesting pre-quantized BSON BinData vectors. MongoDB documents a 3.75x mongot RAM reduction for scalar and 24x for binary, less than the 4x and 32x vector-value reductions because the HNSW graph is not compressed. Full-fidelity vectors stay on disk for rescoring and exact search, so disk use does not fall and the Atlas UI Size metric can rise. For tier economics the lever is memory: quantization lets a given vector set fit a smaller search-node or cluster RAM footprint, while disk sizing must still cover full vectors. Binary quantization needs rescoring and suits high-dimension, zero-centred embeddings; Elastic and Microsoft sources corroborate the recall trade-offs. All headline savings figures are vendor-reported.

## Core Concepts

### Cluster Tier Families and Hourly Pricing (General vs Low-CPU vs NVMe)

- Low-CPU tiers keep the same RAM and storage range as the General tier of the same size but halve vCPUs: on AWS Gen2 M40 has 4 vCPU and M40 Low-CPU (R40) has 2 vCPU, both 16 GiB RAM and 10 GB-1 TB storage; M50 has 8 vCPU vs R50 4 vCPU at 32 GiB. verified-as-of: 2026-10-18[^c1-2][^c1-5]
- Public Atlas-on-AWS hourly prices (us-east-1, calculated January 2022): M40 $1.04, M40 Low-CPU $0.77 (~26% less), M50 $2.00, M50 Low-CPU $1.48 (~26% less). Treat as stale; confirm in the Atlas pricing page or calculator. (two sources) verified-as-of: 2022-01-01[^c1-3][^c1-5]
- NVMe tiers use locally attached ephemeral NVMe SSD, are available only on AWS (Gen2: M40, M50, M60, M80, M200, M400) and Azure (M60, M80, M200, M300, M400, M600), not on Google Cloud, not in multi-cloud clusters, and not on Atlas Infinite. verified-as-of: 2026-10-18[^c1-4][^c1-1]
- NVMe storage and RAM are fixed per tier, not user-selectable: AWS M40_NVME 380 GB, M50_NVME 760 GB (vs General 80/160 GB defaults, scalable to 1/4 TB). NVMe M40 shows 15.25 GB RAM; the instance has 2 vCPU (i8g.large), same as Low-CPU. verified-as-of: 2026-10-18[^c1-2][^c1-4]
- Low-CPU tiers are supported on Atlas Core from M40 and on Atlas Infinite (public preview) M40-M60; General from M10. M10/M20 use burstable infrastructure that can throttle CPU. (two sources) verified-as-of: 2026-10-18[^c1-1][^c1-2]

### Replica Set Node Topology Cost

- Atlas requires the total number of electable nodes across all providers and regions in a cluster to be 3, 5, or 7. Electable nodes provide high availability and can become primary. verified-as-of: 2026-10-18[^c2-1][^c2-6]
- Read-only and analytics nodes do not participate in elections, cannot become primary, and so provide no high availability. Analytics nodes are available on dedicated (M10+) clusters only, not Free or Flex. verified-as-of: 2026-10-18[^c2-1][^c2-3]
- Atlas deploys all data-bearing servers in a cluster at the selected cluster tier, and the per-hour charge covers that tier's default RAM and storage. Each added data-bearing node is therefore a full node at the same hourly tier cost, except analytics nodes with a separate tier. (two sources) verified-as-of: 2026-10-18[^c2-2][^c2-1]
- Customizing storage is billed at the full custom amount, not the increment over the tier default. Every data-bearing node carries that storage, so storage customization multiplies with node count. (two sources) verified-as-of: 2026-10-18[^c2-2][^c2-1]

### Sharded Cluster Cost Economics

- Atlas charges instance and storage cost for each data-bearing node. For a sharded cluster the node count is replication factor x number of shards (3 shards at RF 3 = 9 nodes).[^c3-1][^c3-3]
- When sharding is enabled with dedicated config servers, Atlas adds three config servers billed at a separate rate. Cluster tier and data storage selections do not change that config server cost. The rate itself is not published on the billing page. verified-as-of: 2026-10-18[^c3-1][^c3-2]
- Backup billing for a sharded cluster covers each shard replica set plus the config server replica set. Atlas may retain more than one full snapshot when topology changes (for example when a shard is added), which raises backup storage for a period. Cloud Backup rates on the page are AWS $0.14-$0.19, Azure $0.34-$0.65, Google Cloud $0.08-$0.12 per GB-month. (two sources) verified-as-of: 2026-10-18[^c3-1][^c3-3]
- Every shard must be a replica set, so the minimum footprint of one shard is a multi-node replica set, and the cluster adds config server nodes on top.[^c3-2][^c3-1]
- Sharding on Atlas requires an M30 or larger cluster. (two sources) verified-as-of: 2026-10-18[^c3-3][^c3-2]

### Multi-Region and Cross-Cloud Data Transfer Costs

- Atlas data transfer cost depends on the cloud provider hosting the cluster. The docs rank paths from lowest to highest cost, and name queries from on-premises into Atlas, traffic across cloud providers, and traffic between continents on one provider as the highest-cost paths. (two sources)[^c4-1][^c4-2]
- MongoDB's AWS pricing page lists Atlas data transfer at $0.01/GB same region, $0.02/GB cross-region and $0.09/GB internet. M0, M2 and M5 are exempt. The page gives no date for these rates, while its instance pricing says January 2022. (two sources) verified-as-of: 2026-10-18[^c4-2][^c4-1]
- Multi-region clusters might have higher data transfer costs, depending on the number and location of additional regions and the number of clusters per region. The docs give no formula or worked example.[^c4-1][^c4-2]
- MongoDB states that data transfer is under 10% of the bill for most Atlas customers, depending on usage patterns. This is a general statement, not a guarantee for a multi-region or cross-cloud topology. (two sources) verified-as-of: 2026-10-18[^c4-2][^c4-3]
- Tentative: Traffic between cluster nodes (replication of writes, deletes and index builds, plus heartbeats) and traffic between an app in the same region and the cluster is billed on the 'Atlas AWS Data Transfer (Same Region)' line. A MongoDB employee estimated heartbeats at about 6.2 to 6.8 GB/day per replica set, roughly $0.06 to $0.07/day, in a 2020 thread. verified-as-of: 2020-02-14[^c4-3]
- Tentative: Raw AWS billing: cross-AZ transfer is billed $0.01/GB in each direction, so about $0.02/GB effective. A 2019 test of US inter-region transfer (Virginia to Oregon) billed only the sender, about $0.02/GB. That test found inter-region the same per-GB cost as cross-AZ, not double as the pricing table implied. verified-as-of: 2019-10-21[^c4-4]
- Tentative: Atlas does not charge for incoming data transfer to a cluster, and the Atlas Live Migration Service is free.[^c4-1]

### Storage Growth and IOPS Forecasting for Cost

- If a customer sets a custom storage size, Atlas bills the full custom amount and does not deduct the tier's default storage. Example: a 10 GB M10 raised to 50 GB is billed for 50 GB, not for the extra 40 GB.[^c5-3][^c5-1]
- Atlas storage auto-scaling is enabled by default. It raises disk when used space reaches 90% on any node and sizes the new disk to reach 70% used on AWS, Azure and GCP. It only scales up. verified-as-of: 2026-10-18[^c5-2][^c5-1]
- Atlas Core storage speed is tied to capacity on Gen1, Azure and GCP: raising capacity raises max IOPS at no extra charge, and extra IOPS beyond that costs more. On AWS Gen1, choosing a custom speed (Fast/Fastest) switches the volume from general-purpose SSD to provisioned-IOPS SSD and adds cost. verified-as-of: 2026-10-18[^c5-3][^c5-1]
- Paused clusters still incur storage charges for the default storage; no other service or transfer charges apply. (two sources)[^c5-3][^c5-1]

### Atlas Search and Dedicated Search Nodes Cost

- Enabling Atlas Search on a cluster adds no fee when mongot is co-located with mongod, but co-located search consumes cluster CPU/RAM, and the docs warn of resource contention between mongod and mongot. The docs position co-located deployment for testing and prototyping. (two sources)[^c6-1][^c6-4]
- Dedicated Search Nodes require an M10+ cluster and a minimum of 2 nodes per cluster, up to 32 per region per shard. On sharded clusters Atlas deploys the node set per shard (2 nodes x 3 shards = 6 nodes), so the node floor multiplies with shard count.[^c6-1][^c6-2]
- Search Nodes bill hourly per node, and a partial hour counts as a full hour. Adding or removing a node bills the new configuration immediately. Changing tier bills both old and new instances for the first hour. A replacement of an unhealthy node is free. Network charges cover traffic between Search Nodes and database nodes and appear at cluster level, not as a Search Node line item.[^c6-2][^c6-1]
- On the MongoDB pricing page (updated 2026-09-29, AWS us-east-1) high-CPU Search Node prices run from S20 $0.12/hr (4 GB RAM, 2 vCPU, 106 GB) through S50 $0.99/hr to S80 $3.26/hr. Low-CPU S30 is $0.11/hr and storage-optimized S40-S is $0.25/hr. Because of the two-node minimum, the floor is about double the listed S20 rate (about $0.24/hr, roughly $175/month, derived). (two sources) verified-as-of: 2026-09-29[^c6-3][^c6-2]
- Search Node price varies by cloud for the same tier name: high-CPU S20 is $0.12/hr on AWS us-east-1, $0.14/hr on Google Cloud us-central1, $0.15/hr on Azure eastus2; S50 is $0.99, $1.15 and $1.27/hr respectively. Storage per tier also differs by cloud (S20: 106, 128, 80 GB). (two sources) verified-as-of: 2026-09-29[^c6-3][^c6-2]
- MongoDB announced an S10 Dedicated Search Node tier on 2026-07-23 on AWS, GCP and Azure as a lower-cost entry below S20, aimed at M10/M20/M30 clusters. The announcement gives no price or spec, and the deployment-options page still states S20 as the production minimum. (two sources) verified-as-of: 2026-07-23[^c6-5][^c6-1]

### Vector Search Quantization and Embedding Storage Cost

- Atlas automatic scalar quantization (int8) cuts mongot RAM by 3.75x and automatic binary quantization (int1) by 24x. Vector values themselves shrink 4x and 32x. (two sources) verified-as-of: 2026-10-18[^c7-1][^c7-2]
- The RAM saving is below the vector-value ratio because the HNSW graph structure is not compressed. Sizing must therefore budget graph memory separately from vector memory. (two sources)[^c7-1][^c7-3]
- Full-fidelity vectors remain on disk and are read only for rescoring (binary) or exact (ENN) search. Quantization therefore does not reduce disk use, and the Atlas UI Size metric can look larger because it counts the HNSW graph, quantized vectors and full vectors. The Required Memory metric is the one to use for query-time RAM.[^c7-1][^c7-2]

## Tools & Frameworks

- In the Atlas Administration API, an R prefix in the tier name (R40, R50) selects the Low-CPU variant via replicationSpecs[n].regionConfigs[m].electableSpecs.instanceSize. (two sources)[^c1-2][^c1-1] _(Cluster Tier Families and Hourly Pricing (General vs Low-CPU vs NVMe))_
- Changing an electable node to read-only is done by adding a read-only node and removing an electable node in one operation. Atlas does not guarantee that an analytics node keeps its hostname after a topology change, so connection strings should use replica set tags, not hostnames. (two sources) verified-as-of: 2026-10-18[^c2-1][^c2-3] _(Replica Set Node Topology Cost)_
- The Atlas billing page does not mention a mongos router charge, tier minimums or per-tier hourly prices. Cost modelling must take the rates from the instance-size pricing section or the pricing calculator. (two sources) verified-as-of: 2026-10-18[^c3-1][^c3-3] _(Sharded Cluster Cost Economics)_
- Independent shard scaling lets each shard use its own compute tier and, on AWS and Azure, its own IOPS. It is the default for clusters created on or after 2024-12-09; older clusters scale all shards together. It is controlled through the Admin API, CLI or Terraform, not the UI, and after using it the Cluster Builder UI can no longer manage the cluster. The auto-scaler permits at most a 2-tier gap between the highest and lowest shard. (two sources) verified-as-of: 2026-10-18[^c3-3][^c3-2] _(Sharded Cluster Cost Economics)_
- Tentative: Enabling automatic quantization is a per-field index-definition setting (quantization: scalar or binary) that triggers an index rebuild and needs no query change. Max dimensions are 8192. Non-float-array values are silently skipped. MongoDB suggests it for collections over about 100,000 vectors. verified-as-of: 2026-10-18[^c7-1] _(Vector Search Quantization and Embedding Storage Cost)_

## Methodology

- Tentative: Third-party guidance suggests downgrading one tier when average CPU is below 20% and peak below 40%, and claims 30-60% savings from combined optimizations. These are unverified estimates, not MongoDB figures. verified-as-of: 2026-03-31[^c2-8] _(Replica Set Node Topology Cost)_
- MongoDB advises considering an extra shard at sustained 60-70% utilization of RAM, vCPU or storage on a sizable machine. Its Atlas example is an M60 with a 4 TB disk. It states vertical scaling becomes increasingly expensive and that horizontal scaling is more predictable and cost-effective at scale. (two sources)[^c3-4][^c3-2] _(Sharded Cluster Cost Economics)_
- Plan for roughly 20% more disk than compressed data size under WiredTiger, because buffer, journal and log files and a no-overwrite engine consume space. Size forecasts from disk used, not from logical data size. (two sources)[^c5-1][^c5-2] _(Storage Growth and IOPS Forecasting for Cost)_
- Search Nodes run on compute-intensive instances with local SSDs that need about 20% storage overhead, so index size must fit the fixed per-tier disk. Index size depends on field mappings; estimate by indexing 1-2 GB of representative data (example ratio 0.25:1). (two sources)[^c6-1][^c6-4] _(Atlas Search and Dedicated Search Nodes Cost)_
- Tentative: Sizing rule of thumb from MongoDB: about 10 QPS per vCPU (two S20 nodes = 4 vCPU = about 40 QPS); target latency under 100 ms; if adding CPU lowers latency the deployment is underprovisioned; scale out to up to 32 nodes for throughput; consider sharding above roughly 10k inserts/updates per second. These are vendor estimates, not benchmarks. verified-as-of: 2025-08-12[^c6-4] _(Atlas Search and Dedicated Search Nodes Cost)_
- Independent vendors corroborate the shape of the trade-off. Azure AI Search says int8 gives a 4x and binary up to 28x vector index size reduction, and that binary works best above 1024 dimensions with zero-centred embeddings. Elastic calls naive binary quantization exceptionally lossy and needing 10x-100x reranking candidates. Elastic's improved BBQ reaches over 90% recall at 3x oversampling on 1024-dimension Cohere vectors. verified-as-of: 2026-07-02[^c7-4][^c7-3] _(Vector Search Quantization and Embedding Storage Cost)_

## Practical Patterns

- Low-CPU is the cheaper option for memory-heavy, CPU-light workloads: similar RAM and storage at a lower price. Vantage (Jan 2024) says the same. (two sources)[^c1-5][^c1-3] _(Cluster Tier Families and Hourly Pricing (General vs Low-CPU vs NVMe))_
- NVMe clusters auto-scale to the next higher tier when 90% of storage is full, because storage cannot grow independently. This makes capacity planning a tier-cost decision.[^c1-4][^c1-1] _(Cluster Tier Families and Hourly Pricing (General vs Low-CPU vs NVMe))_
- An analytics node tier can be set larger or smaller than the base tier. A tier on the Analytics Tier tab is priced like the same tier on the Base Tier tab, with the price adjusted prorated per node when it differs. Atlas shows the price in the UI at create or edit time. verified-as-of: 2026-10-18[^c2-1][^c2-3] _(Replica Set Node Topology Cost)_
- MongoDB positions a smaller analytics tier as a cost saving versus scaling the whole cluster tier for BI workloads. The announcement gives no price figures. (two sources)[^c2-3][^c2-1] _(Replica Set Node Topology Cost)_
- An arbiter holds no data and votes in elections, giving two data-bearing members an odd vote count at lower cost. The manual recommends at most one arbiter, warns that PSA sets can suffer performance problems with w:majority when a secondary lags, and warns that PSA shards can lose availability. The manual page covers self-managed sets and does not mention Atlas. (two sources)[^c2-4][^c2-6] _(Replica Set Node Topology Cost)_
- Atlas requires the same number of electable, read-only and analytics nodes, the same storage capacity and the same NVMe tier on every shard (Global clusters may vary node counts per zone). Storage cannot be sized per shard, so a hot shard forces extra storage cost on all shards. verified-as-of: 2026-10-18[^c3-3][^c3-1] _(Sharded Cluster Cost Economics)_
- Tentative: MongoDB 8.0 config shards let a sharded cluster run without dedicated config servers. In Atlas, sharded clusters with up to 3 shards on 8.0 use config shards by default, which removes the separate three-node config server charge for small clusters. verified-as-of: 2026-10-18[^c3-4] _(Sharded Cluster Cost Economics)_
- Documented mitigations: use the 'nearest' read preference for cross-region reads, send cross-region writes from the Highest Priority Region, keep clients in the cluster's region and provider, project only needed fields, and enable driver network compression. Atlas already compresses intra-cluster traffic. (two sources)[^c4-1][^c4-3] _(Multi-Region and Cross-Cloud Data Transfer Costs)_
- Gen2 Dedicated clusters (M30+, AWS/GCP) charge for storage including a baseline IOPS tied to disk size, and bill Extended Standard IOPS separately above that baseline. After switching Gen1 to Gen2, Atlas recommends re-tuning capacity and IOPS independently to cut cost. (two sources) verified-as-of: 2026-10-18[^c5-3][^c5-1] _(Storage Growth and IOPS Forecasting for Cost)_
- Replica sets are limited to 4 TB per node. Beyond that, Atlas recommends sharding for long-term growth; extended storage is a temporary fix that slows initial syncs and can reduce availability. (two sources) verified-as-of: 2026-10-18[^c5-1][^c5-3] _(Storage Growth and IOPS Forecasting for Cost)_
- Tentative: The deployment-options page tells users to move to dedicated Search Nodes once they exceed roughly 2 million documents to index, 10 GB of indexed data, or 10,000 queries in 7 days. verified-as-of: 2026-10-18[^c6-1] _(Atlas Search and Dedicated Search Nodes Cost)_
- Three node classes trade RAM:vCPU and storage: low-CPU 8:1 (vector search, low data volume), high-CPU 2:1 (lexical search, heavy indexing/query), storage-optimized 8:1 with 375-6000 GB (large indexes, moderate load). MongoDB claims storage-optimized nodes cut Search Node storage cost up to 50% and are about 40% cheaper than high-CPU when RAM-anchored. List prices agree in direction: AWS S40-S $0.25/hr vs high-CPU S40 $0.48/hr, both 16 GB RAM. Choose storage-optimized when storage is the constraint and CPU is moderate. (two sources) verified-as-of: 2026-09-29[^c6-4][^c6-3] _(Atlas Search and Dedicated Search Nodes Cost)_
- Tentative: Since 2026-06-30 (GA), multi-region clusters can set a different dedicated Search Node count per region. MongoDB estimates 25-40% lower Search Node spend where secondary regions carry little search traffic. The figure is a vendor estimate. Use it to avoid duplicating full node counts in DR regions. verified-as-of: 2026-06-30[^c6-6] _(Atlas Search and Dedicated Search Nodes Cost)_
- Tentative: Ingesting pre-quantized BSON BinData vectors (float32, int8, int1 subtypes) needs about three times less disk space than a standard float32 array. Requirements: MongoDB 6.0.11/7.0.2 or later and a supported driver (Node.js 6.11+, PyMongo 4.10+, Java 5.3.1+). int1 supports euclidean similarity only and needs dimensions in multiples of 8. verified-as-of: 2026-10-18[^c7-1] _(Vector Search Quantization and Embedding Storage Cost)_
- MongoDB recommends binary quantization with rescoring for most embedding models, and scalar quantization for lower-dimension models that are not quantization-aware trained. Scalar gave the highest average recall in MongoDB's own chart. Binary assumes a zero midpoint, so it suits normalised embeddings. (two sources)[^c7-1][^c7-2] _(Vector Search Quantization and Embedding Storage Cost)_
- Tentative: Azure lets binary-quantized indexes discard original vectors (discardOriginals) and rescore with the binary dot product, saving disk. Atlas documents no equivalent: binary rescoring there reads full-fidelity float vectors from disk. verified-as-of: 2026-07-02[^c7-4] _(Vector Search Quantization and Embedding Storage Cost)_

## Anti-Patterns

- NVMe operational constraints with cost impact: scaling needs a file-copy initial sync that degrades the source primary; backup cannot be disabled and hourly snapshots limited to every 12 hours; a hidden secondary with a provisioned volume supports backup; the cluster cannot be paused; no independent shard scaling.[^c1-4][^c1-1] _(Cluster Tier Families and Hourly Pricing (General vs Low-CPU vs NVMe))_
- Setting the analytics tier significantly below the base tier can cause replication lag; the analytics node might fall off the oplog. On Atlas Core, analytics storage size must match the base tab, so a small analytics tier does not shrink storage cost; mixing General and Low-CPU across the tabs disables disk auto-scaling. (two sources) verified-as-of: 2026-10-18[^c2-1][^c2-2] _(Replica Set Node Topology Cost)_
- Tentative: Atlas enforces a three-node minimum for dedicated replica sets, so a test environment pays for two idle secondaries. A MongoDB staff reply (Sept 2024) defended the minimum for availability; the requester rejected it. verified-as-of: 2024-09-11[^c2-6] _(Replica Set Node Topology Cost)_
- Tentative: A one-shard sharded cluster on M30 was described in a MongoDB Jira ticket (PM-2290) as costing about twice an M30 replica set because of dedicated config servers. Undated and internal, so treat as a rough indicator only. verified-as-of: 2026-10-18[^c3-6] _(Sharded Cluster Cost Economics)_
- Poor shard-key choice and queries lacking the shard key are the main hidden costs: scatter-gather queries are broadcast to all shards and run long, and resharding is slow and resource intensive. (two sources)[^c3-2][^c3-5] _(Sharded Cluster Cost Economics)_
- Tentative: Log export to external services routes through the Atlas control plane in AWS us-east-1 regardless of cluster region or provider. A cluster outside us-east-1 pays cross-region or inter-cloud charges on top of internet egress.[^c4-1] _(Multi-Region and Cross-Cloud Data Transfer Costs)_
- If an auto-scaled disk would exceed the current tier's maximum storage, Atlas raises the cluster tier even when tier scaling is disabled (docs example: M30 to M40 when 600 GB is needed). This also disables automatic tier scale-down, so storage growth can silently raise the compute line item. verified-as-of: 2026-10-18[^c5-2][^c5-3] _(Storage Growth and IOPS Forecasting for Cost)_
- If a tier scale-down target cannot support the current disk capacity or IOPS, Atlas does not scale the cluster down. An oversized disk therefore blocks compute savings. (two sources)[^c5-2][^c5-1] _(Storage Growth and IOPS Forecasting for Cost)_
- Atlas cannot shrink storage in place on AWS, Azure or GCP. It provisions new volumes and resyncs from the old ones, which causes downtime on each node during the sync, and sync time grows with data size. Over-provisioning is therefore sticky cost, so do not size up speculatively.[^c5-1][^c5-4] _(Storage Growth and IOPS Forecasting for Cost)_
- Search Node cost is additive to the base cluster: node count x tier rate, plus search-to-database transfer billed under cluster network charges. Pricing-page cluster rates do not include Search Nodes, so model them as a separate line (the sibling multi-region transfer concept covers network cost). (two sources)[^c6-2][^c6-3] _(Atlas Search and Dedicated Search Nodes Cost)_
- Tentative: MongoDB's 96% figure for binary quantization with rescoring is processing-memory reduction in MongoDB's own tests, not total storage. The post names no dataset or model, gives no chart values and uses 50 queries. verified-as-of: 2025-04-29[^c7-2] _(Vector Search Quantization and Embedding Storage Cost)_
- Binary quantization is risky for low-dimension embeddings. Elastic's own post notes a smaller speed advantage on 384-dimension-class E5-small, and Azure advises testing quality or using scalar below 1024 dimensions. Validate recall on your own data before downsizing a tier. (two sources)[^c7-4][^c7-3] _(Vector Search Quantization and Embedding Storage Cost)_

## Troubleshooting

- Tentative: Atlas docs say Low-CPU may also carry fewer max connections depending on tier; the AWS reference page does not list connection limits, so check the connection-limits page before downsizing.[^c1-2] _(Cluster Tier Families and Hourly Pricing (General vs Low-CPU vs NVMe))_
- Multi-region clusters can incur higher data transfer costs depending on the number and location of added regions. Atlas compresses intra-cluster communication. The data transfer page does not say whether same-region or cross-AZ replication traffic is billed. (two sources) verified-as-of: 2026-10-18[^c2-5][^c2-7] _(Replica Set Node Topology Cost)_
- Tentative: AWS fixed under-metering of cross-zone NLB data transfer on 2025-05-01. Atlas uses cross-zone NLBs for its AWS PrivateLink endpoint service. MongoDB covered the cost through 2025-05-15, then expected invoices to rise about 1.0% on average, on the 'Atlas AWS Data Transfer (Same Region)' line. verified-as-of: 2025-05-15[^c4-5] _(Multi-Region and Cross-Cloud Data Transfer Costs)_
- AWS EBS allows at most four modifications per volume in a rolling 24 hours and a volume resize can take hours. Atlas delays further capacity or IOPS changes until AWS permits another, so a fast-growing cluster can hit the cap during bulk loads.[^c5-1][^c5-4] _(Storage Growth and IOPS Forecasting for Cost)_
- Atlas auto-scaling needs a large enough oplog window: the minimum oplog retention window must be up to 60 seconds times GB of disk configured, and Atlas delays a scaling event until the oplog covers the estimated scaling time. Heavy writes can outrun auto-scaling, so docs advise avoiding high-speed writes when planning to scale up. (two sources)[^c5-1][^c5-2] _(Storage Growth and IOPS Forecasting for Cost)_
- On AWS M40+ clusters with fast disk pre-warming, Atlas may temporarily provision a higher-performance volume when replacing or adding a node. That cost lands on the monthly storage line, so storage cost can run above forecast in months with node replacements. (two sources)[^c5-3][^c5-1] _(Storage Growth and IOPS Forecasting for Cost)_
- Because Atlas keeps full vectors on disk plus a quantized copy in memory, enabling quantization raises total disk need while lowering RAM need. Disk and memory must be sized separately when choosing a tier or search node. (two sources)[^c7-1][^c7-2] _(Vector Search Quantization and Embedding Storage Cost)_

## Disagreements & Open Questions

- Disagreement (Cluster Tier Families and Hourly Pricing (General vs Low-CPU vs NVMe)): A search-snippet third-party blog claimed General costs ~20% more than Low-CPU, while the MongoDB 2022 price table shows ~35% more (1.04 vs 0.77). Not reconciled; blog not fetched.[^c1-3]
- Open (Cluster Tier Families and Hourly Pricing (General vs Low-CPU vs NVMe)): Current (2026) hourly prices for General, Low-CPU and NVMe tiers; no public NVMe hourly price found.
- Open (Cluster Tier Families and Hourly Pricing (General vs Low-CPU vs NVMe)): Max connection limits for Low-CPU vs General.
- Open (Cluster Tier Families and Hourly Pricing (General vs Low-CPU vs NVMe)): Whether Low-CPU price ratio holds on Azure/GCP and on Gen2 Graviton instances.
- Open (Cluster Tier Families and Hourly Pricing (General vs Low-CPU vs NVMe)): Page cluster-tier mentions Gen1 vs Gen2 storage/IOPS billing; Gen2 pricing details not explored.
- Disagreement (Replica Set Node Topology Cost): A forum requester argues node count should be a user choice independent of tier; MongoDB staff say the three-node minimum is needed for availability on all tiers.[^c2-6]
- Open (Replica Set Node Topology Cost): Whether Atlas bills same-region cross-AZ replication traffic; the data transfer page is silent.
- Open (Replica Set Node Topology Cost): Whether Atlas supports arbiters at all; the manual page does not cover Atlas.
- Open (Replica Set Node Topology Cost): Exact per-hour rates per node; docs show them only in the UI, not in fetched text.
- Open (Replica Set Node Topology Cost): Evidence is mostly MongoDB-authored; only IBM Community and oneuptime are other organisations and neither covers node-count cost.
- Disagreement (Sharded Cluster Cost Economics): MongoDB's manual recommends starting every new application on a sharded cluster, citing cost-effective scaling, while the Atlas billing page shows a sharded cluster adds three config servers (unless a config shard is used) and multiplies nodes by shard count, and the Jira ticket suggests a one-shard cluster can cost about twice a replica set. Early sharding is not obviously cheaper.[^c3-4][^c3-1][^c3-6]
- Open (Sharded Cluster Cost Economics): Current published hourly rate for Atlas dedicated config servers, and whether it varies by region.
- Open (Sharded Cluster Cost Economics): Whether mongos routers add any billed cost on Atlas (docs silent).
- Open (Sharded Cluster Cost Economics): Whether config-shard default (up to 3 shards on 8.0) is still current and what it does to the bill versus dedicated config servers.
- Open (Sharded Cluster Cost Economics): No independent third-party (non-MongoDB) cost analysis was found; sources are almost all MongoDB documentation. Negation round found no contradiction, only the early-sharding versus cost tension noted above.
- Disagreement (Multi-Region and Cross-Cloud Data Transfer Costs): The 2019 inter-region test found inter-region cost equal to cross-AZ per GB. The pricing table of the time implied twice as much. Sender-only billing also differs from the Atlas page's flat per-GB tiers.[^c4-4]
- Disagreement (Multi-Region and Cross-Cloud Data Transfer Costs): In the forum thread, a user's 7.477 GB over 72 hours (about 2.5 GB/day) did not match the 6.2 to 6.8 GB/day heartbeat estimate, and no per-component breakdown was given.[^c4-3]
- Disagreement (Multi-Region and Cross-Cloud Data Transfer Costs): Third-party blogs claim multi-region cost is mostly duplicated compute and backup, and quote cross-cloud rates up to $0.16/GB. Neither claim was confirmed against official MongoDB sources, so neither is asserted here.[^c4-1]
- Open (Multi-Region and Cross-Cloud Data Transfer Costs): No official Atlas rate table for cross-cloud (for example AWS to Azure or GCP) was found.
- Open (Multi-Region and Cross-Cloud Data Transfer Costs): Azure and GCP inter-region per-GB rates for Atlas were not found; the fetched docs page did not render provider-specific figures.
- Open (Multi-Region and Cross-Cloud Data Transfer Costs): The date of the MongoDB AWS pricing page transfer rates is unknown.
- Open (Multi-Region and Cross-Cloud Data Transfer Costs): Atlas docs do not break out multi-region replication volume or give a cost formula for N regions.
- Disagreement (Storage Growth and IOPS Forecasting for Cost): A MongoDB staff forum reply (Feb 2025) said Atlas storage cannot be reduced directly on AWS and advised Live Migration to a smaller cluster. The poster quoted Atlas support and the docs saying Atlas reduces capacity in place via new volumes and resync, with downtime per node. The current docs support the in-place resync path.[^c5-5][^c5-1]
- Open (Storage Growth and IOPS Forecasting for Cost): Only two independent organisations (MongoDB, AWS) were deep-read; no third-party cost analysis was verified, so the 3-source depth contract is not fully met.
- Open (Storage Growth and IOPS Forecasting for Cost): Current per-GB and per-IOPS list prices were not extracted; they sit on the Atlas pricing page, which is not in scope here.
- Open (Storage Growth and IOPS Forecasting for Cost): Exact Gen2 baseline IOPS-per-GB formula and Extended Standard IOPS price were not captured.
- Open (Storage Growth and IOPS Forecasting for Cost): Search snippets cited a 2020 Studio 3T article with Gen1 M50 IOPS cost figures; not fetched and likely outdated.
- Open (Storage Growth and IOPS Forecasting for Cost): Forum thread 209954 reports ~130 GB disk for ~2 GB data after auto-scale; not fetched, cause unknown.
- Disagreement (Atlas Search and Dedicated Search Nodes Cost): Minimum production search tier is inconsistent across MongoDB pages: deployment-options says S20, an earlier search snippet of a vector-search page said S30, the S10 announcement (2026-07-23) says S10 now sits below S20, and the pricing page lists no S10.[^c6-1][^c6-5][^c6-3]
- Open (Atlas Search and Dedicated Search Nodes Cost): No independent (non-MongoDB) source was found: every cost claim traces to MongoDB. The depth contract of 3 independent organisations is not met; claims are capped at medium.
- Open (Atlas Search and Dedicated Search Nodes Cost): S10 price, specs and whether the two-node minimum applies are unpublished in sources read.
- Open (Atlas Search and Dedicated Search Nodes Cost): Negation round (2 searches for user complaints and independent cost comparisons) found no contradicting reports, no independent TCO benchmarks, and no OpenSearch/Elastic price comparison.
- Open (Atlas Search and Dedicated Search Nodes Cost): Whether the 40% and 50% storage-optimized savings and the 25-40% asymmetric-region savings hold in practice is unverified.
- Disagreement (Vector Search Quantization and Embedding Storage Cost): MongoDB's blog says binary quantization keeps up to 95% accuracy and cuts memory 96%, while its docs give 24x (about 96% of RAM) and Elastic says naive binary is exceptionally lossy. MongoDB's 95% depends on rescoring, and the blog states no dataset.[^c7-2][^c7-3]
- Disagreement (Vector Search Quantization and Embedding Storage Cost): The MongoDB blog body calls the feature public preview, while its April 2025 update says generally available.[^c7-2]
- Open (Vector Search Quantization and Embedding Storage Cost): How Required Memory translates to specific Atlas Search Node tier choices (sibling concept: Atlas Search and Dedicated Search Nodes Cost).
- Open (Vector Search Quantization and Embedding Storage Cost): Independent (non-vendor) benchmarks of Atlas automatic quantization recall; none found.
- Open (Vector Search Quantization and Embedding Storage Cost): The MongoDB docs page was read only to the first 100000 of 325412 characters, so later sections were not checked.
- Open (Vector Search Quantization and Embedding Storage Cost): A search-result snippet quoting 66% BSON storage reduction (41 GB to 14 GB) was not verified against its source.

## References

### Cluster Tier Families and Hourly Pricing (General vs Low-CPU vs NVMe)

[^c1-1]: https://www.mongodb.com/docs/atlas/cluster-tier/ — Atlas Cluster Tier (docs)
[^c1-2]: https://www.mongodb.com/docs/atlas/reference/amazon-aws/ — Atlas AWS cluster reference (docs)
[^c1-3]: https://www.mongodb.com/mongodb-on-aws/pricing — MongoDB on AWS pricing (Jan 2022 figures) (docs)
[^c1-4]: https://www.mongodb.com/docs/atlas/nvme-storage/ — NVMe Storage for Atlas Clusters (docs)
[^c1-5]: https://www.vantage.sh/blog/mongodb-cost-optimization-tips — MongoDB Cost Optimization Tips (Vantage) (blog)

### Replica Set Node Topology Cost

[^c2-1]: https://www.mongodb.com/docs/atlas/cluster-config/multi-cloud-distribution/ — Atlas multi-cloud distribution / node types (docs)
[^c2-2]: https://www.mongodb.com/docs/atlas/billing/cluster-configuration-costs/ — Atlas cluster configuration costs (docs)
[^c2-3]: https://www.mongodb.com/company/blog/product-release-announcements/introducing-ability-independently-scale-atlas-analytics-node-tiers — Independently scale Atlas analytics node tiers (blog)
[^c2-4]: https://www.mongodb.com/docs/manual/core/replica-set-arbiter/ — Replica set arbiter (manual) (docs)
[^c2-5]: https://www.mongodb.com/docs/atlas/billing/data-transfer-costs — Atlas data transfer costs (docs)
[^c2-6]: https://www.mongodb.com/community/forums/t/feature-request-possibility-to-reduce-number-of-nodes-in-replicaset-for-stg-test-environments/296384 — Forum: reduce replica set nodes for stg/test (forum)
[^c2-7]: https://community.ibm.com/community/user/blogs/manish-negandhi/2026/04/14/optimizing-mongodb-atlas-cost — Optimizing MongoDB Atlas Cost (IBM Community) (blog)
[^c2-8]: https://oneuptime.com/blog/post/2026-03-31-mongodb-optimize-atlas-costs/view — How to Optimize MongoDB Atlas Costs (blog)

### Sharded Cluster Cost Economics

[^c3-1]: https://www.mongodb.com/docs/atlas/billing/cluster-configuration-costs — Atlas Cluster Configuration Costs (docs)
[^c3-2]: https://www.mongodb.com/docs/manual/sharding/ — MongoDB Manual: Sharding (docs)
[^c3-3]: https://mongodb.com/docs/atlas/cluster-sharding/ — Atlas: Sharding requirements and independent shard scaling (docs)
[^c3-4]: https://www.mongodb.com/docs/manual/core/sharding-start-with-sharding/ — MongoDB Manual: Start with Sharded Clusters (docs)
[^c3-5]: https://www.dragonflydb.io/faq/mongodb-sharding-disadvantages — Dragonfly FAQ: disadvantages of MongoDB sharding (search snippet only, not fetched) (blog)
[^c3-6]: https://jira.mongodb.org/browse/COMPASS-6208 — PM-2290: dedicated config servers optional (Jira, search snippet only) (forum)

### Multi-Region and Cross-Cloud Data Transfer Costs

[^c4-1]: https://mongodb.com/docs/atlas/billing/data-transfer-costs — Atlas Data Transfer Costs (docs)
[^c4-2]: https://mongodb.com/mongodb-on-aws/pricing — MongoDB on AWS pricing (docs)
[^c4-3]: https://www.mongodb.com/community/forums/t/aws-atlas-data-transfer-usage/553 — AWS Atlas Data Transfer Usage (forum, Feb 2020) (forum)
[^c4-4]: https://www.lastweekinaws.com/blog/aws-cross-az-data-transfer-costs-more-than-aws-says — Cross-AZ data transfer costs (Last Week in AWS, 2019) (blog)
[^c4-5]: https://intercom-help.mongodb.com/en/articles/11100710-mongodb-atlas-billing-changes-due-to-aws-updates — Atlas billing changes due to AWS updates (NLB) (docs)

### Storage Growth and IOPS Forecasting for Cost

[^c5-1]: https://www.mongodb.com/docs/atlas/customize-storage/ — Atlas Customize Cluster Storage (docs)
[^c5-2]: https://www.mongodb.com/docs/atlas/cluster-autoscaling-storage/ — Atlas Cluster Storage Auto-Scaling (docs)
[^c5-3]: https://www.mongodb.com/docs/atlas/billing/cluster-configuration-costs — Atlas Cluster Configuration Costs (docs)
[^c5-4]: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modify-volume.html — Modify an Amazon EBS volume using Elastic Volumes (docs)
[^c5-5]: https://www.mongodb.com/community/forums/t/scale-down-cluster-storage-with-no-downtime/312168 — Scale Down Cluster Storage with No Downtime (forum)

### Atlas Search and Dedicated Search Nodes Cost

[^c6-1]: https://mongodb.com/docs/atlas/atlas-search/about/deployment-options — Atlas Search deployment options (docs)
[^c6-2]: https://mongodb.com/docs/atlas/billing/search-node — Atlas Search Node billing (docs)
[^c6-3]: https://www.mongodb.com/pricing.md — MongoDB Pricing (updated 2026-09-29) (docs)
[^c6-4]: https://mongodb.com/company/blog/technical/the-art-and-science-of-sizing-search-nodes — The art and science of sizing search nodes (blog)
[^c6-5]: https://www.mongodb.com/products/updates/introducing-the-s10-dedicated-search-node-tier/ — Introducing the S10 Dedicated Search Node Tier (blog)
[^c6-6]: https://www.mongodb.com/products/updates/now-ga-asymmetric-per-region-dedicated-search-node-counts — Now GA: Asymmetric Per-Region Dedicated Search Node Counts (blog)

### Vector Search Quantization and Embedding Storage Cost

[^c7-1]: https://www.mongodb.com/docs/vector-search/about/vector-quantization.md — MongoDB Vector Search: vector quantization (docs)
[^c7-2]: https://mongodb.com/blog/post/binary-quantization-rescoring-96-less-memory-faster-search — Binary Quantization & Rescoring: 96% Less Memory, Faster Search (blog)
[^c7-3]: https://www.elastic.co/search-labs/de/blog/better-binary-quantization-lucene-elasticsearch — Better Binary Quantization (BBQ) in Lucene and Elasticsearch (blog)
[^c7-4]: https://learn.microsoft.com/en-my/Azure/search/vector-search-how-to-quantization — Compress vectors using quantization - Azure AI Search (docs)
