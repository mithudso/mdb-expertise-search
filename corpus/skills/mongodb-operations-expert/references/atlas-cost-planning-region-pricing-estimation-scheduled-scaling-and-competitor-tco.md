<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Created by `/dr` deep research 2026-10-19; research dir `<local-path>`.

---
name: atlas-cost-planning-region-pricing-estimation-scheduled-scaling-and-competitor-tco
description: "Atlas cost planning: region and cloud price differentials (M30 $0.54 AWS vs $0.51 Azure vs $0.44 GCP; tier shapes and backup/transfer rates vary by provider and region); pre-deployment estimation (working-set-to-RAM sizing, Pricing Calculator, hourly x 730 x nodes plus storage, backup, egress); scheduled and predictive scaling (predictive auto-scaling scales up only, M30+; conservative 24h scale-down; no native time-of-day schedule); cross-vendor pricing (DocumentDB instance-hours and Standard vs I/O-Optimized storage, Cosmos DB RU/s billed per region, DynamoDB on-demand). TRIGGER: cheapest region for Atlas; estimate Atlas cost before launch; Atlas pricing calculator; schedule tier changes; predictive autoscaling; Atlas vs DocumentDB vs Cosmos DB cost. SKIP: tier families -> atlas-cluster-topology-and-tier-economics; self-managed TCO -> atlas-pricing-programs-cost-governance-and-tco; autoscaling mechanics -> Elastic Compute Autoscaling pack."
version: "1.0.0"
updated: "2026-10-19"
category: "research"
whenToUse:
  - "pick the cheapest Atlas region or cloud for a tier"
  - "estimate an Atlas bill before deploying"
  - "schedule or predict Atlas tier changes to cut cost"
  - "compare Atlas pricing with DocumentDB, Cosmos DB or DynamoDB"
keywords: ["region pricing", "cloud provider price", "reference region", "pricing calculator", "cost estimation", "working set sizing", "wiredtiger cache", "predictive auto-scaling", "scheduled scaling", "scale-down rules", "cron pause", "DocumentDB pricing", "Cosmos DB RU", "DynamoDB on-demand", "competitor TCO"]
tags: ["mongodb", "atlas", "cost", "planning", "regions", "estimation", "autoscaling", "competitors", "tco"]
provenance: "/dr · <local-path>"
---

# Atlas Cost Planning: Region Pricing, Estimation, Scheduled Scaling and Competitor TCO

## Overview

Atlas dedicated-cluster hourly rates differ by cloud provider and by region, and the public pricing page publishes only one reference region per provider (AWS us-east-1, Azure eastus2, GCP us-central1). On that page, M30 is $0.54/hr on AWS, $0.51 on Azure and $0.44 on GCP; M10 is $0.08 on all three. Backup, data transfer and multi-region node costs also vary by provider and region, and multi-region clusters cost more than single-region. Planners must therefore price the exact provider and region in the Atlas calculator or cluster-creation UI rather than extrapolate from the headline table. Per-region dedicated-tier rate tables were not found in public docs.

Before deploying, estimate Atlas cost in two steps: size the tier from RAM and working set (Atlas sizing docs), then price it as cluster hourly rate plus storage, backup, data transfer and add-ons. MongoDB's pricing page points to an Atlas Core Pricing Calculator and lists the cost drivers. The tier is the foundational driver. Third-party guides give explicit formulas and worked examples, but they use AWS us-east-1 rates and assumed backup/egress figures. Egress and PITR backup are the most commonly underestimated lines. Right-sizing after launch uses metrics thresholds. The calculator's inputs and outputs were not independently inspected.

Atlas has no native time-based tier schedule. Cost control from time patterns comes from two sources. First, predictive auto-scaling (rolled out from Nov 2025) scales replica sets up ahead of forecast cyclical spikes; it never scales down, so it adds capacity earlier rather than cutting spend. Second, customer-run schedules pause and resume non-production dedicated clusters via the Admin API, CLI or Terraform (paused clusters bill storage only, max 30 days before auto-resume). Reactive scale-down is slow and conservative (24h cooldown, 4h low-load window), so spiky batch workloads can sit on a larger tier for many hours. MongoDB's own simulation of predictive scaling claims about 9 cents/hour average savings per replica set, but this is a vendor simulation on 2023 data, not production evidence.

Atlas competitors bill on different units, so list prices cannot be compared directly. Amazon DocumentDB charges per instance-hour plus storage, with Standard (per-I/O) or I/O-Optimized storage. Azure Cosmos DB charges per provisioned or consumed Request Unit, plus storage, multiplied by regions. DynamoDB charges per request unit, on-demand or provisioned; on-demand prices fell 50% on 2024-11-01. Public Atlas-vs-competitor comparisons are vendor-authored and conflict: Microsoft claims its own Azure DocumentDB is 39-70% cheaper than Atlas on AWS, while Vantage modeled AWS DocumentDB 26.7% dearer than Atlas for a 16 vCPU multi-AZ cluster. Atlas includes replica nodes in tier price; DocumentDB bills each instance. A fair TCO needs one workload model, normalised for HA, storage, I/O, regions and commitments.

## Core Concepts

### Region and Cloud Provider Price Differentials for Atlas

- The public Atlas pricing page quotes dedicated-tier base prices for a single reference region per provider: AWS N. Virginia (us-east-1), Azure Virginia (eastus2), GCP Iowa (us-central1). Prices include default storage and change if storage is customized. verified-as-of: 2026-10-14[^c1-1][^c1-3]
- In those reference regions, M30 (8 GB RAM, 2 vCPU) lists at $0.54/hr on AWS, $0.51/hr on Azure and $0.44/hr on GCP; M50 lists at $2.00, $1.95 and $1.66/hr; M10 is $0.08/hr on all three. GCP is the cheapest at M30 and above, roughly 18% below AWS at M30. (two sources) verified-as-of: 2026-10-14[^c1-1][^c1-4]
- Atlas docs state that the choice of cloud provider and region affects cluster cost. For multi-region clusters, cost depends on the number and location of additional regions; the creation UI shows the tier cost for the Preferred Region only, and the Cluster Overview shows the true total.[^c1-3][^c1-4]
- Cloud Backup storage is billed per GB per month with rates that vary between providers and between regions within a provider (docs example: $0.14/GB-month for an AWS region); continuous-backup snapshot/oplog rates are likewise tabulated by provider and region. (two sources) verified-as-of: 2026-10-18[^c1-3][^c1-4]
- Atlas data-transfer pricing varies by cloud provider and by the region of source and destination nodes. Transfers rank from cheapest to costliest: same region/zone, cross-region within a provider, then out to the Internet or another provider. Inbound data is free; multi-region clusters can have higher transfer costs. verified-as-of: 2026-10-18[^c1-2][^c1-5]

### Pre-Deployment Cost Estimation and Sizing Model (Atlas Pricing Calculator)

- MongoDB's pricing page directs users to an 'Atlas Core' Pricing Calculator for estimating monthly cost, and lists the drivers: cluster tier and type, cloud provider and region, data storage (data plus indexes), data transfer (mainly egress and cross-region), backup (snapshots and oplogs), and add-ons such as Stream Processing and dedicated Search Nodes. (two sources) verified-as-of: 2026-10-18[^c2-1][^c2-4]
- Atlas recommends M30+ for production. M10/M20 suit low-traffic production, and sustained load on them may degrade performance over time. The pricing page likewise positions M10/M20 as pre-production or small non-critical, and M30+ as dedicated-vCPU performance tiers. verified-as-of: 2026-10-18[^c2-2][^c2-1]
- Pricing-page rules for line items: inbound transfer is typically free; egress and cross-region traffic is billed at cloud-provider rates; Free and Flex are not charged for outgoing data; backup cost depends on region and monthly snapshot plus oplog storage for continuous backup. (two sources) verified-as-of: 2026-10-18[^c2-1][^c2-4]

### Scheduled and Predictive Scaling for Atlas Cost

- Predictive auto-scaling only triggers scale-up events ahead of forecast cyclical spikes; scale-down is still triggered only by the existing reactive logic, and predictive scaling respects the user's configured min and max cluster tiers. It needs no setup beyond enabling auto-scaling. verified-as-of: 2026-04-07[^c3-4][^c3-5]
- Predictive auto-scaling eligibility: General or Low-CPU class, tier M30 or larger, auto-scaling enabled (if down-scaling is on, the minimum size must be M30 or larger), cluster active at least two weeks, no NVMe storage, not AWS Gen2 dedicated. It applies only to electable and read-only nodes, not search or analytics nodes. M10/M20 never qualify. (two sources) verified-as-of: 2026-10-19[^c3-1][^c3-4]
- The Nov 2025 product update says rollout began Nov 3 on some existing auto-scaling clusters and would reach all eligible clusters over the following months. The Apr 2026 engineering post says about a third of customers had enabled auto-scaling and would soon get both predictive and reactive scaling. (two sources) verified-as-of: 2026-04-07[^c3-4][^c3-5]
- Reactive scale-down is conservative. Atlas scales down only if the cluster was not scaled, provisioned or unpaused in the past 24 hours and no node restarted in the past 12 hours. Normalized system CPU must be below 45% for at least the last 10 minutes and the last 4 hours. WiredTiger cache must be below 90% and projected memory at the lower tier below 60% over the same windows. Checks start only when down-scaling is enabled, not retroactively. Atlas moves down one tier at a time. (two sources) verified-as-of: 2026-10-19[^c3-1][^c3-3]
- Pause rules: M10+ clusters without NVMe storage can be paused for up to 30 days, after which Atlas resumes them. Atlas charges paused clusters for storage only, with no other service or data transfer charges. A resumed cluster must run at least 60 minutes before it can be paused again. Pausing needs disk usage below 95% and a healthy cluster. Flex clusters cannot be paused. Free clusters are auto-paused after 30 days of inactivity. (two sources) verified-as-of: 2026-10-19[^c3-2][^c3-7]

### Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB)

- AWS cut DynamoDB on-demand throughput prices by 50% and global tables prices by up to 67% (replicated writes: 67% on-demand, 33% provisioned), effective 2024-11-01 in all Regions. AWS now recommends on-demand as the default mode and says most provisioned-capacity workloads get a lower price on on-demand. verified-as-of: 2024-11-14[^c4-1][^c4-2]
- Amazon DocumentDB instance-based clusters bill four dimensions on Standard storage (instance-hours, storage, I/O per million, backup beyond free allotment) and three on I/O-Optimized (no I/O charge). AWS lists storage at $0.10/GB-month and I/O at $0.20 per million on Standard, and storage at $0.30/GB-month on I/O-Optimized. verified-as-of: 2026-10-19[^c4-3][^c4-4]
- Tentative: DocumentDB also has Serverless billed per DCU-hour ($0.0822 Standard, $0.0905 I/O-Optimized, 0.5 DCU minimum) and Elastic Clusters billed at $0.132 per vCPU-hour plus $0.30/GB-month storage, per the AWS pricing page. verified-as-of: 2026-10-19[^c4-3]
- Azure Cosmos DB (NoSQL) bills provisioned throughput hourly at the maximum RU/s in that hour in 100 RU/s units, at about $0.008 per 100 RU/s per hour for a single write region and $0.016 with multi-region writes (US example rates). Storage is about $0.25/GB-month. Serverless mode bills $0.25 per million RUs consumed. verified-as-of: 2026-04-27[^c4-5][^c4-6]
- Tentative: A Microsoft Cosmos DB dev blog (2026-02-26) claims Azure DocumentDB (the Mongo-compatible vCore service) is 39-70% cheaper per hour than Atlas on AWS, e.g. M30-equivalent $0.296/h vs $0.570/h, M60 $2.369 vs $4.180. The article does not state currency, region or commitment terms, and the table is vendor-authored. verified-as-of: 2026-02-26[^c4-7]

## Tools & Frameworks

- Atlas has no documented native time-of-day tier schedule. MongoDB's cost guidance for dev/test is to run a cron job that pauses clusters overnight by setting the Admin API 'paused' field to true on the Modify One Cluster endpoint, or via the Terraform cluster resource. A third-party walkthrough does this with GitHub Actions cron (resume 08:00 UTC, pause 20:00 UTC on weekdays) calling a PATCH with paused true/false. (two sources)[^c3-3][^c3-7] _(Scheduled and Predictive Scaling for Atlas Cost)_
- Cosmos DB reserved capacity gives up to 30% off for 1- or 3-year terms (Microsoft's worked example uses 20%), usable as a monetary credit across regions and APIs. (two sources) verified-as-of: 2026-04-27[^c4-5][^c4-6] _(Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB))_

## Methodology

- Atlas sizing starts from RAM: the working set is all indexes plus frequently accessed documents. To estimate it, take total index space from db.stats() and assume a percentage of data space is accessed frequently. (two sources)[^c2-2][^c2-3] _(Pre-Deployment Cost Estimation and Sizing Model (Atlas Pricing Calculator))_
- Tentative: WiredTiger cache is 50% of physical RAM on M40+ and 25% on M30 and smaller, so physical RAM needed is about twice the working set on M40+. The docs' worked example: a 172 GB working set needs at least 344 GB RAM, which lands on M300. verified-as-of: 2026-10-18[^c2-2] _(Pre-Deployment Cost Estimation and Sizing Model (Atlas Pricing Calculator))_
- Tentative: A third-party manual formula is (cluster $/hr x 730 hrs x nodes) + storage + backup + egress + multi-region multiplier. Its worked example: single-region M30 about $1,535/month (cluster $1,182.60, storage $60, PITR on 200 GB about $200, 1 TB egress $92.16), and a two-region M30 about $2,997, roughly 2x, driven mostly by duplicated compute and backup. verified-as-of: 2026-08-07[^c2-4] _(Pre-Deployment Cost Estimation and Sizing Model (Atlas Pricing Calculator))_
- The prototype has a Forecaster, an Estimator and a Planner. In MongoDB's simulation on 2023 data from 10,000 opted-in replica sets, the average replica set would have saved about 9 cents per hour versus the reactive scaler. The planner targets 50-75% CPU. The authors extrapolate millions of dollars a year across Atlas. This is simulated on historical data, not measured in production. (two sources)[^c3-5][^c3-6] _(Scheduled and Predictive Scaling for Atlas Cost)_
- Tentative: The claim that nightly/weekend pausing of dev and staging clusters cuts cost by '60% or more' appears only in a vendor-neutral blog with no calculation. Treat it as an illustrative figure. A 12h weekday window is about 64% of weekly hours, but storage billing continues while paused, so actual savings are lower than compute-only arithmetic.[^c3-7] _(Scheduled and Predictive Scaling for Atlas Cost)_

## Practical Patterns

- Tier shapes are not identical across providers: M10 is 2 vCPU/2 GB on AWS, 1 vCPU/2 GB on Azure and 0.5 vCPU/1.7 GB on GCP at the same $0.08/hr list price, and the GCP M20 has 3.75 GB RAM vs 4 GB elsewhere. Price per hour alone is not like-for-like. (two sources) verified-as-of: 2026-10-14[^c1-1][^c1-3] _(Region and Cloud Provider Price Differentials for Atlas)_
- Atlas states most customers spend under 10% of budget on data transfer; mitigations are co-locating apps in the cluster's region and provider and using nearest read preference for unavoidable cross-region reads. (two sources)[^c1-2][^c1-4] _(Region and Cloud Provider Price Differentials for Atlas)_
- Tentative: Post-launch right-sizing uses at least 2 weeks of hourly metrics. One guide's thresholds: downsize if p95 CPU <20% or RAM <50%; upsize if p95 CPU >70% or RAM >85%; cache hit rate below about 90-95% suggests the working set does not fit in RAM. verified-as-of: 2026-03-31[^c2-3] _(Pre-Deployment Cost Estimation and Sizing Model (Atlas Pricing Calculator))_
- Pre-deployment estimates do not capture auto-scaling: auto-scaling raises the tier within a user-set min/max, and storage auto-scales when 90% of disk is used. Budget at the configured maximum tier as the worst case. (two sources) verified-as-of: 2026-10-18[^c2-2][^c2-3] _(Pre-Deployment Cost Estimation and Sizing Model (Atlas Pricing Calculator))_
- Only seasonal workloads benefit. The long-term forecaster had about 3% connection-forecast error on seasonal clusters versus 50% on non-seasonal ones. Most Atlas replica sets have daily seasonality and about 25% also have weekly seasonality (weekly usually implies daily; hourly seasonality is rare). The estimator excluded 13% of replica sets. A self-censoring check stops the forecaster being trusted when its recent error is high. (two sources)[^c3-5][^c3-6] _(Scheduled and Predictive Scaling for Atlas Cost)_
- Defaults and bounds: in the Atlas UI, 'allow cluster to be scaled down' is checked by default on new clusters, but via the Admin API auto-scaling must be enabled explicitly. Default maximum size is one tier above the current tier and default minimum is the current tier. Scaling never leaves the min/max range or crosses from General to Low-CPU class. Setting these bounds is the cost cap. (two sources) verified-as-of: 2026-10-19[^c3-1][^c3-3] _(Scheduled and Predictive Scaling for Atlas Cost)_
- Right-sizing guidance from MongoDB: if usage stays steadily below 45% of allocated resources over a rolling 30-day period, manually move down a tier. Right-sizing is described as often the single biggest cost lever, and Atlas also recommends M10 or M30 for dev/test. (two sources)[^c3-3][^c3-1] _(Scheduled and Predictive Scaling for Atlas Cost)_
- AWS's rule for DocumentDB: choose Standard if I/O is expected to be under 25% of total cluster cost, I/O-Optimized if over 25%. A cluster can switch to I/O-Optimized once every 30 days, and back to Standard at any time, with no downtime or reboot.[^c4-4][^c4-3] _(Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB))_
- Cosmos DB throughput and storage are billed in every replicated region: total RU/s billed = RU/s x number of regions. Billing is per wall-clock hour, so a scale-up for part of an hour charges the full hour at the higher rate. Autoscale bills the peak RU/s each hour (10-100% of the set maximum) at a 1.5x single-write-region multiplier.[^c4-5][^c4-6] _(Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB))_
- Tentative: Vantage (2025-02-11) modeled a 16 vCPU, 300 GB multi-AZ workload: Atlas M60 at $3.95/h (about $2,844/month, 320 GB included) vs DocumentDB db.r5.4xlarge I/O-Optimized at $2.44/h per instance, two instances plus storage totalling $3,603.60/month, making DocumentDB 26.7% dearer. Main driver: Atlas includes its replica set in the tier price while DocumentDB bills each instance. verified-as-of: 2025-02-11[^c4-8] _(Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB))_

## Anti-Patterns

- Tentative: Export Logs to External Services routes through the Atlas control plane in AWS us-east-1 regardless of cluster region or provider, so clusters elsewhere pay cross-region or inter-cloud transfer on top of Internet egress. verified-as-of: 2026-10-18[^c1-2] _(Region and Cloud Provider Price Differentials for Atlas)_
- Tentative: Egress can dominate small clusters: one guide's example of 15 TB/month to the internet at $0.09/GB adds $1,350, over twice the roughly $500 compute of a 3-node M40. It also says PITR can push backup from about 10% to 20-25% of cluster cost, using an assumed blended $1.00/GB rate. verified-as-of: 2026-08-07[^c2-4] _(Pre-Deployment Cost Estimation and Sizing Model (Atlas Pricing Calculator))_
- Pausing side effects relevant to schedule design: Atlas deletes Search Node data and rebuilds the search indexes on resume (search queries are unavailable meanwhile). Backups stop while paused. Maintenance tasks queued during the pause may start immediately on resume and delay availability. (two sources)[^c3-2][^c3-7] _(Scheduled and Predictive Scaling for Atlas Cost)_
- AWS's page example for two db.r5.large instances in US East shows $449.42/month on Standard (200M I/Os) and $459.86/month on I/O-Optimized (1,000M I/Os). The advertised 24.5% saving only holds when both are compared at the same I/O volume, so the totals on the page are not directly comparable. (two sources) verified-as-of: 2026-10-19[^c4-3][^c4-4] _(Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB))_
- The two public Atlas-vs-competitor comparisons reach opposite conclusions (Microsoft: competitor cheaper; Vantage: Atlas cheaper) because they compare different competitor services (Azure DocumentDB vs AWS DocumentDB), different HA assumptions and different years. Neither is a neutral basis for a TCO claim; model the customer's own workload instead. (two sources)[^c4-7][^c4-8] _(Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB))_

## Troubleshooting

- Tentative: A third-party guide says AWS us-east-1 is typically among the lowest-cost regions and quotes $0.01/GB same-region and $0.02/GB cross-region transfer plus $0.09/GB Internet egress; these are generic AWS-style figures, not Atlas-published rates. verified-as-of: 2026-07-30[^c1-4] _(Region and Cloud Provider Price Differentials for Atlas)_
- Tentative: Spiky batch workloads suffer from slow scale-down: a user reported a daily 1.5-hour pipeline that scales M20 to M30 but then stays at M30 for about 22.5 hours before scaling back, and asked for a configurable scale-down window. The request (created Aug 2022, 194 votes) had no staff reply on the page. This is one anecdote, not a measured finding. verified-as-of: 2025-01-14[^c3-8] _(Scheduled and Predictive Scaling for Atlas Cost)_
- Name clash: 'DocumentDB' means Amazon DocumentDB (AWS, Mongo-compatible, instance plus I/O billing) and, in Microsoft's 2026 material, 'Azure DocumentDB' (vCore Mongo-compatible service in the Cosmos DB family). Cite the vendor prefix in any TCO table. (two sources)[^c4-7][^c4-3] _(Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB))_

## Disagreements & Open Questions

- Disagreement (Region and Cloud Provider Price Differentials for Atlas): CloudZero asserts us-east-1 is typically among the cheapest regions, but Atlas publishes no per-region dedicated-tier table to confirm it; only the single reference region per provider is public.[^c1-4][^c1-1]
- Open (Region and Cloud Provider Price Differentials for Atlas): Exact per-region dedicated-tier hourly deltas (e.g. sa-east-1, ap-northeast-1 vs us-east-1) are not in public docs; only calculator/console shows them.
- Open (Region and Cloud Provider Price Differentials for Atlas): Per-GB Atlas inter-region transfer rates were not captured from the provider-selector widget on the data-transfer page.
- Open (Region and Cloud Provider Price Differentials for Atlas): Whether GCP's M30+ discount persists in non-reference regions is unverified.
- Disagreement (Pre-Deployment Cost Estimation and Sizing Model (Atlas Pricing Calculator)): The Amnic formula multiplies hourly rate by nodes, while the oneuptime and docs framing treats the tier as a replica-set price. Whether the listed hourly rate is per node or per cluster is not settled by the sources read.[^c2-4][^c2-1]
- Disagreement (Pre-Deployment Cost Estimation and Sizing Model (Atlas Pricing Calculator)): Cache hit-rate threshold is inconsistent inside the oneuptime article (95% in the script, 90% in the text). Its tier spec table (M30 40 GB storage) also differs from pricing-page storage ranges.[^c2-3]
- Open (Pre-Deployment Cost Estimation and Sizing Model (Atlas Pricing Calculator)): The Atlas Core Pricing Calculator itself was not fetched: its inputs, defaults and whether it models backup, PITR, egress and auto-scaling are unverified.
- Open (Pre-Deployment Cost Estimation and Sizing Model (Atlas Pricing Calculator)): Whether the pricing-page hourly rate is per node or per replica set.
- Open (Pre-Deployment Cost Estimation and Sizing Model (Atlas Pricing Calculator)): Whether the docs' RAM sizing rule (cache = 50% RAM) applies unchanged to Atlas Infinite tiers.
- Open (Pre-Deployment Cost Estimation and Sizing Model (Atlas Pricing Calculator)): The Amnic page has conflicting publication dates (July 8 and August 7, 2026), and its backup and PITR rates are assumptions.
- Disagreement (Scheduled and Predictive Scaling for Atlas Cost): Scale-down rules are described inconsistently. The compute auto-scaling page uses a 24h cooldown and 10-minute/4-hour windows at 45% CPU. The cost-saving page says scale-down happens once every six hours. Search snippets of an older MongoDB developer article cite a 72-hour, 50% rule (not fetched, likely outdated). Use the compute auto-scaling page as authoritative.[^c3-1][^c3-3]
- Disagreement (Scheduled and Predictive Scaling for Atlas Cost): The 2024 prototype Planner scaled down as soon as overload risk passed and could skip tiers, whereas the shipped version only scales up and leaves scale-down to the reactive scaler, so the prototype's savings estimate overstates what production delivers.[^c3-6][^c3-5]
- Disagreement (Scheduled and Predictive Scaling for Atlas Cost): The third-party blog says pausing 'stops charging for compute' without mentioning storage; official docs state storage is still charged. Search snippets also gave conflicting tier limits (M10-M40) and auto-terminate-after-30-days claims, contradicted by the official docs (M10+, auto-resume).[^c3-7][^c3-2]
- Open (Scheduled and Predictive Scaling for Atlas Cost): Is predictive scaling's net cost effect positive or negative in production? Scale-up-early adds spend and only scale-down is reactive; no production savings figure exists.
- Open (Scheduled and Predictive Scaling for Atlas Cost): Whether a native Atlas scheduled-scaling feature now exists; 2020-2024 feedback threads requested it and none was found, but the feedback site 404'd on one thread.
- Open (Scheduled and Predictive Scaling for Atlas Cost): Exact dollar savings of pause schedules depend on storage, backup and snapshot charges while paused, not quantified by any source.
- Open (Scheduled and Predictive Scaling for Atlas Cost): Cost-saving page 'once every six hours' scale-down wording was not reconciled with the 24h cooldown on the compute page.
- Open (Scheduled and Predictive Scaling for Atlas Cost): The Predictive Auto-Scaling docs page itself (separate from the compute page) was not fetched; eligibility is taken from the compute auto-scaling page.
- Disagreement (Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB)): Microsoft says its DocumentDB is 39-70% cheaper than Atlas on AWS; Vantage says AWS DocumentDB is 26.7% more expensive than Atlas for a 16 vCPU multi-AZ workload. Different products, HA and dates.[^c4-7][^c4-8]
- Disagreement (Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB)): AWS's page presents I/O-Optimized as 24.5% cheaper, but that compares different I/O volumes (1,000M vs 200M); at equal volume the example shows Standard cheaper at low I/O.[^c4-3]
- Open (Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB)): Current USD DynamoDB on-demand per-million RRU/WRU rates in us-east-1 were not read from the official AWS pricing page (the 2024 announcement gives only percentages).
- Open (Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB)): Cosmos DB autoscale and serverless dollar rates on the live Azure pricing page were empty in search output; the $0.008/$0.25 figures come from the Learn billing article.
- Open (Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB)): Vantage article labels db.r5.4xlarge as Graviton, which is wrong; its figures were not independently rechecked.
- Open (Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB)): Whether Microsoft's Atlas comparison assumes 3-node Atlas with equivalent HA is unstated.
- Open (Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB)): Old Cosmos DB vs DynamoDB comparisons (2018) and 'on-demand tax' critiques predate the 2024 DynamoDB cut and were discarded as outdated.

## References

### Region and Cloud Provider Price Differentials for Atlas

[^c1-1]: https://www.mongodb.com/pricing.md — MongoDB Pricing (docs)
[^c1-2]: https://mongodb.com/docs/atlas/billing/data-transfer-costs — Atlas Data Transfer Costs (docs)
[^c1-3]: https://www.mongodb.com/docs/atlas/billing/cluster-configuration-costs — Atlas Cluster Configuration Costs (docs)
[^c1-4]: https://www.cloudzero.com/blog/mongodb-pricing — CloudZero MongoDB pricing (blog)
[^c1-5]: https://community.ibm.com/community/user/blogs/manish-negandhi/2026/04/14/optimizing-mongodb-atlas-cost — Optimizing MongoDB Atlas cost (IBM community) (blog)

### Pre-Deployment Cost Estimation and Sizing Model (Atlas Pricing Calculator)

[^c2-1]: https://www.mongodb.com/pricing — MongoDB Pricing (docs)
[^c2-2]: https://www.mongodb.com/docs/atlas/sizing-tier-selection/ — Atlas Sizing and Tier Selection (docs)
[^c2-3]: https://oneuptime.com/blog/post/2026-03-31-mongodb-right-size-atlas-clusters/view — How to Right-Size MongoDB Atlas Clusters (blog)
[^c2-4]: https://amnic.com/blogs/mongodb-atlas-pricing-tiers-real-costs-and-how-to-control-them — MongoDB Atlas Pricing: Tiers, Real Costs, and How to Control Them (blog)

### Scheduled and Predictive Scaling for Atlas Cost

[^c3-1]: https://www.mongodb.com/docs/atlas/cluster-autoscaling-compute-core/ — Compute Auto-Scaling on Atlas Core (docs)
[^c3-2]: https://mongodb.com/docs/atlas/pause-terminate-cluster/ — Pause, Resume, or Terminate a Cluster (docs)
[^c3-3]: https://mongodb.com/docs/atlas/architecture/current/cost-saving-config — Recommendations for Atlas Cost-Saving Configurations (docs)
[^c3-4]: https://www.mongodb.com/products/updates/predictive-auto-scaling-for-mongodb-atlas — Predictive Auto-Scaling for MongoDB Atlas (product update, 2025-11-19) (docs)
[^c3-5]: https://mongodb.com/company/blog/engineering/mongodb-predictive-auto-scaling-an-experiment — MongoDB Predictive Auto-Scaling: an Experiment (2026-04-07) (blog)
[^c3-6]: https://emptysqua.re/blog/mongodb-predictive-scaling-experiment/ — MongoDB predictive scaling experiment (2024-10-31) (blog)
[^c3-7]: https://oneuptime.com/blog/post/2026-03-31-mongodb-atlas-pause-resume-clusters/markdown — How to Pause and Resume Atlas Clusters (OneUptime, 2026-03-31) (blog)
[^c3-8]: https://feedback.mongodb.com/ideas/CUSTOMER-I-9126 — Autoscaling with custom conditions to scale up (forum)

### Cross-Vendor Document Database Pricing Comparison (DocumentDB Cosmos DB DynamoDB)

[^c4-1]: https://aws.amazon.com/blogs/database/new-amazon-dynamodb-lowers-pricing-for-on-demand-throughput-and-global-tables/ — AWS: DynamoDB lowers on-demand and global tables pricing (docs)
[^c4-2]: https://www.cloudzero.com/blog/dynamodb-pricing — CloudZero DynamoDB pricing (search snippet only, not fetched) (blog)
[^c4-3]: https://aws.amazon.com/documentdb/pricing/ — Amazon DocumentDB pricing (docs)
[^c4-4]: https://docs.aws.amazon.com/documentdb/latest/devguide/db-cluster-storage-configs.md — DocumentDB cluster storage configurations (docs)
[^c4-5]: https://learn.microsoft.com/en-us/azure/cosmos-db/understand-your-bill — Understanding your Azure Cosmos DB bill (docs)
[^c4-6]: https://azure.microsoft.com/pricing/details/cosmos-db/autoscale-provisioned/ — Azure Cosmos DB autoscale/provisioned pricing (search snippet only, not fetched) (docs)
[^c4-7]: https://devblogs.microsoft.com/cosmosdb/azure-documentdb-mongodb-compatible/ — Microsoft Cosmos DB devblog: Azure DocumentDB vs Atlas (blog)
[^c4-8]: https://vantage.sh/blog/documentdb-vs-mongodb-price-comparison — Vantage: DocumentDB vs MongoDB price comparison (blog)
