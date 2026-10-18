<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-cost-optimization` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-cost-optimization
description: >
  MongoDB Atlas cost optimization reference — cluster right-sizing, storage tier selection
  (GP3 vs Provisioned IOPS vs NVMe), compute and storage autoscaling configuration, backup
  retention tuning, network egress cost reduction, reserved capacity / committed-use discounts,
  cluster pause scheduling, index storage pruning, and cost monitoring strategy.
  TRIGGER: reducing Atlas spend; Atlas invoice review; cluster right-sizing; tier down from
  M80/M60/M50/M30; non-prod cluster pause automation; backup retention cost; provisioned IOPS
  migration to GP3; unused index cleanup; Atlas committed-use discount; AWS/GCP/Azure Marketplace
  private offer; EDP credits for Atlas; Atlas autoscaling thresholds; orphaned cluster cleanup;
  "Atlas is too expensive"; "how do I reduce my Atlas bill"; "Atlas cost breakdown";
  "cluster oversized"; "pausing Atlas clusters"; "backup storage cost".
  SKIP: Flex tier pricing model — use mongodb-atlas-flex-serverless; Atlas cluster feature
  configuration unrelated to cost — use mongodb-atlas-expert; M0 free tier — cost is zero,
  no optimization needed.
category: mongodb
tags: [mongodb, atlas, cost, optimization, sizing, autoscaling, storage, backup, egress, committed-use]
version: "1.2.0"
updated: "2026-05-29"
whenNotToUse:
  - Flex tier cost model ($8–$30/mo cap) — use mongodb-atlas-flex-serverless
  - Atlas cluster feature/capability questions unrelated to cost — use mongodb-atlas-expert
  - Atlas Serverless RPU/WPU billing (deprecated) — use mongodb-atlas-flex-serverless
related_skills:
  - mongodb-atlas-expert
  - mongodb-atlas-flex-serverless
  - mongodb-capacity-planning
  - mongodb-indexes-deep
  - mongodb-backup-restore
  - mongodb-aws-networking
---

# MongoDB Atlas Cost Optimization

Expert guidance on reducing MongoDB Atlas spend while maintaining performance SLAs. Applicable to all Atlas dedicated cluster tiers (M10–M700+). Real-world context: this skill was developed in part to support a $300k cost optimization target for enterprise Atlas deployments.

## Scope

**In scope:** Atlas dedicated clusters (M10 and above), replica sets, sharded clusters, backup, network egress, index storage, and committed-use pricing.

**Out of scope:** Atlas Serverless and Atlas Flex clusters use per-operation and range-based pricing models that differ fundamentally from instance-based pricing. Cost guidance for Serverless and Flex requires separate analysis — this skill does not cover them. Atlas App Services (triggers, Data API) costs are also excluded.

---

## Quick Reference — Cost Levers by Impact

Use this table to prioritize effort. Detail for each lever is in the numbered sections below.

| Lever | Effort | Typical Savings |
|---|---|---|
| Committed-use discount renegotiation | Low (sales conversation) | 15–35% of total |
| Cluster right-sizing (tier down) | Medium (test + rolling restart) | 30–60% per cluster |
| Non-prod cluster pause schedules | Low (API automation) | 60–70% of non-prod compute |
| Backup retention reduction | Low (UI policy change) | 20–40% of backup line |
| Provisioned IOPS → GP3 migration | Low-medium | 40–70% of storage cost |
| Unused index pruning | Medium (analysis required) | 10–30% of storage |
| Cross-region → single-region | High (architecture change) | 50–70% of compute on affected clusters |
| Orphaned cluster cleanup | Low | 100% of cluster cost |

---

## 1. Instance Right-Sizing — M-Tier Sizing Methodology

### Sizing philosophy
Right-sizing is an iterative process, not a one-time event. Atlas clusters are over-provisioned by default because teams size for peak-of-peak and never revisit. Most production clusters run at <40% CPU and <60% RAM utilization on average.

### CPU targets
- **Sustained CPU < 60%**: healthy headroom. If sustained CPU consistently sits below 30%, the cluster is a candidate for one tier down.
- **P99 CPU < 80%**: spikes above 80% during batch windows are acceptable if they are brief and predictable.
- **CPU steal > 5%** on M10/M20 clusters: signal that the underlying host is saturated; consider moving up one tier to get more dedicated compute headroom.

### RAM targets
- **Working set fit**: the most critical metric. If the Atlas "Page Faults" metric (in Metrics → Cache) shows sustained page faults, your working set has outgrown RAM. Size up until page faults are near zero.
- **Cache utilization > 90%**: investigate query patterns first (indexes, projections, covered queries) before adding RAM.
- **Target 70–85% cache utilization** as a healthy steady state.

### IOPS targets
- Monitor "Disk IOPS" in Atlas Metrics. If IOPS consistently approach the tier's provisioned limit, consider scaling up or switching to Provisioned IOPS storage (NVMe or custom IOPS).
- For write-heavy workloads, watch "Disk Queue Depth" — values above 1 sustained indicate I/O saturation.

### Tier step-down methodology
1. Pull 30-day P50/P95/P99 CPU, memory cache utilization, and IOPS from Atlas Metrics or Data Explorer.
2. Identify the busiest 3-hour window in the week (typically Monday morning or end-of-month batch).
3. Simulate one tier down: will P95 CPU stay below 75%? Will working set still fit?
4. For RS primaries, validate oplog window stays above 24 hours after downsizing (oplog window shrinks with smaller disks).
5. Apply the change via Atlas UI rolling restart (Atlas changes secondaries first, then the primary automatically via election). Watch metrics for 24 hours after the rolling restart completes before declaring success.

### Cluster count reduction
Consolidating several under-utilized M30 clusters onto fewer M50 clusters often saves more than tier reduction alone. Evaluate multi-tenant cluster patterns (separate databases per tenant) when per-cluster overhead exceeds actual workload cost.

---

## 2. Storage Tier Selection

### Atlas storage tiers (as of 2025)
| Tier | Description | Best For | Relative Cost |
|---|---|---|---|
| Standard (GP3) | AWS gp3, GCP pd-balanced, Azure premium | Most workloads | Baseline |
| Provisioned IOPS (io1/io2) | Fixed IOPS independent of disk size | Write-heavy, latency-sensitive | 2–4× standard |
| NVMe (local SSD) | Local NVMe on M40 NVMe SKU and above (separate SKU from standard M40; not all M40s include NVMe) | Extreme IOPS, caching tier | Premium; node failure requires peer resync |
| Standard HDD | Not available in Atlas directly | — | — |

### When to use Standard (GP3)
- OLTP workloads with moderate write rates (< 3,000 sustained IOPS).
- Analytical or reporting workloads.
- Development, staging, and QA environments — always use standard here.
- Majority of M30–M60 production clusters that are not latency-sensitive.

### When to use Provisioned IOPS
- Write-heavy workloads where disk queue depth consistently exceeds 1.
- When you need deterministic IOPS SLA for compliance (fintech, healthcare).
- Clusters where you can't size disk larger (data volume constraint) but need more IOPS.
- Cost break-even: provisioned IOPS becomes cost-effective only when you need > 3,000 IOPS from a disk that would otherwise require scaling the cluster tier.

### When to use NVMe
- Hot data caches (Okta session store, rate-limiting counters, real-time leaderboards).
- When working set exceeds 500 GB and cache miss latency is unacceptable.
- Note: NVMe local disks are not network-attached persistent storage — if an individual node fails, WiredTiger data on that node must be rebuilt by initial sync from a healthy peer. Atlas manages this automatically, but it means the replica set must stay healthy (never lose quorum) or recovery time increases significantly.

### Cost optimization rule
**Audit provisioned IOPS allocations quarterly.** Teams frequently provision 10,000 IOPS for a cluster consuming 800. Move over-provisioned io1 clusters to GP3 with IOPS matching actual P95 usage + 30% headroom.

---

## 3. Elastic Compute / Autoscaling

### What Atlas compute autoscaling does
Atlas Compute Autoscaling (available M10+, enabled per cluster) monitors CPU and memory, then scales up or down one tier at a time. It does not skip tiers.

### Scale-up rules (Atlas defaults)
- CPU utilization > 75% for 1 hour (or shorter sustained window depending on tier).
- OR cache dirty bytes approaching capacity.
- Scale-up is immediate (rolling restart, no downtime for RS).

### Scale-down rules (Atlas defaults)
- CPU utilization < 50% for the trailing 24 hours.
- The 24-hour delay is intentional — Atlas will not oscillate. Reduce to 12 hours only if your workload has predictable weekly patterns (e.g., weekday-only traffic).

### Autoscaling thresholds — recommended overrides

| Setting | Recommended Value | Rationale |
|---|---|---|
| Scale Up Trigger | CPU > 70% for 30 minutes | Aggressive protection against saturation |
| Scale Down Trigger | CPU < 40% for 24 hours | Conservative — avoids oscillation |
| Min Tier | M30 (production) | Never autoscale below M30 in prod |
| Max Tier | Set explicitly | No cap = runaway cost risk |

### Opt-in vs opt-out strategy
- **Opt in** for: non-production clusters, single-region analytics clusters, clusters with variable batch workloads.
- **Opt out** for: sharded clusters (autoscaling applies per shard — coordinate with capacity planning), clusters with strict latency SLAs where a rolling restart during a scale event is disruptive, M0/M2/M5 free/shared tiers (autoscaling not available on shared infrastructure).

### Monitoring autoscaling events
Atlas Project Activity Feed logs every scale event. Set a budget alert at 110% of current spend to catch unexpected autoscale-up events.

---

## 4. Storage Autoscaling

### Atlas disk autoscaling default
Atlas triggers disk autoscaling when disk utilization reaches **90% of provisioned storage**. The disk is expanded by approximately 25% (rounded to the next billing increment).

### Why the 90% trigger is dangerous
By the time Atlas fires the autoscale event and the expansion completes, the cluster can momentarily spike above 90%, causing the `WiredTiger` storage engine to stall writes. For high-write clusters, configure the disk alert at **85%** to give yourself a 2–4 hour window to intervene manually.

### Disk space alert setup (Atlas UI)

Configure in Atlas UI → Project → Alerts → Add Alert:

- **Condition**: Disk Utilization > 85%
- **Notification channels**: PagerDuty + Slack channel
- **Evaluation window**: 5 minutes

### Manual vs auto disk scaling
- **Manual scaling** is preferred for predictable growth patterns (data archival, known ingest schedules). Avoids unexpected storage cost jumps.
- **Auto scaling** is appropriate when ingest rate is variable and unpredictable. Set a maximum disk size cap in cluster configuration to avoid runaway expansion.

### Compaction and space recovery
- Atlas does not automatically compact reclaimed disk space after large deletes. Use `compact` command during maintenance windows on secondaries, then primary, to reclaim space.
- After TTL index deletes or large bulk-delete operations, compaction can recover 30–60% of disk, avoiding an autoscale event.

---

## 5. Backup Cost Optimization

### Backup pricing model
Atlas charges for backup storage separately from cluster storage. Snapshot storage list price starts at approximately $0.14/GB-month (varies by cloud provider and region; see `references/mongodb-backup-restore.md` for the same figure). Snapshots are incremental after the first, so realized cost is typically well under the full dataset size times that rate. Continuous (PIT) backups add overhead for oplog tailing.

### Snapshot retention tuning
Default Atlas backup policies are often set to 7 daily + 4 weekly + 12 monthly + 2 yearly. For non-production environments, this is severe overkill.

**Recommended retention by environment:**
| Environment | Daily | Weekly | Monthly | Yearly |
|---|---|---|---|---|
| Production | 7 | 4 | 3 | 1 |
| Staging | 3 | 1 | 0 | 0 |
| Dev/QA | 1 | 0 | 0 | 0 |

Applying minimal retention to staging/dev/QA clusters alone can reduce backup spend by 20–40% for organizations with many non-prod clusters.

### Queryable backups vs continuous backups
- **Queryable backups** (Backup Query) allow running read queries against a snapshot without restoring. They incur an additional charge per hour the queryable session is active. Terminate sessions immediately after use — stale queryable backup sessions are a common surprise charge.
- **Continuous backups** (Point-in-Time Restore, PITR) require oplog storage in addition to snapshots. For clusters with high write rates, oplog storage can equal or exceed base snapshot storage. PITR is essential for production; disable it on all non-production clusters.

### Cross-region backup cost
Atlas charges cloud provider data transfer rates for cross-region snapshot copies. Example: us-east-1 → eu-west-1 snapshot copy on AWS costs ~$0.02/GB in egress. For a 2 TB cluster with weekly cross-region backup copies, this is ~$40/week ($2,080/year) in egress alone, before storage.

**Optimization:** Use cross-region backup only for your most critical production clusters. For DR, consider whether a replica set spanning regions (geo-distributed RS) eliminates the need for cross-region backup copies.

---

## 6. Network Egress Costs

### Free paths
- **Intra-region, same VPC/peering**: traffic between your application VPC and Atlas via VPC peering in the same cloud region is free on AWS and GCP (standard peering rules). This is the target architecture.
- **Private Link / Private Endpoint within the same region**: free for data transfer; you pay for the endpoint hour only.

### Charged paths
- **Cross-region data transfer**: any data that crosses cloud provider region boundaries is charged at the provider's inter-region rate (~$0.02/GB on AWS, similar on GCP/Azure).
- **Internet egress (no peering)**: clusters accessed over the public internet are charged at provider internet egress rates (~$0.09/GB on AWS). This is the most expensive path and should be eliminated in production.
- **Atlas Data Federation**: egress from Atlas Data Federation to S3 or external storage layers has its own pricing. Review federation query patterns.

### Marketplace billing and egress credits
When Atlas is purchased through AWS Marketplace (or GCP/Azure Marketplace), egress charges from Atlas to compute in the same cloud are often offset by Marketplace agreements. Verify with your MongoDB sales rep whether your Marketplace agreement includes egress credits.

### Egress cost reduction tactics
1. Co-locate application and Atlas cluster in the same region. Mismatched regions are the single largest source of unplanned egress costs.
2. Use VPC peering or Private Link everywhere — eliminate public endpoint usage.
3. Minimize cross-shard scatter queries in sharded clusters (scatter-gather reads data from all shards, multiplying egress if shards span regions).
4. Atlas Charts and Atlas Data Federation running cross-region against production clusters generate egress at query time.

---

## 7. Reserved Capacity / Committed Use Discounts

### Atlas committed use discounts
MongoDB offers committed-use pricing (similar to cloud provider reserved instances) through multi-year Atlas contracts. Discounts range from 15–35% depending on commitment term and volume:
- 1-year commitment: ~15% discount
- 2-year commitment: ~25% discount
- 3-year commitment: ~30–35% discount

### Marketplace private offers
AWS, GCP, and Azure Marketplace support Private Offer agreements where MongoDB can negotiate custom pricing with volume commitments. These are distinct from on-demand Marketplace rates and are typically accessed through MongoDB's enterprise sales team. Private Offers can bundle:
- Atlas cluster usage
- Atlas Search (Lucene-powered)
- Atlas Stream Processing
- Professional services

### Enterprise Discount Programs (EDP)
For AWS customers with an existing AWS EDP agreement, Atlas Marketplace spend can count toward your EDP commitment and receive EDP discounts. This stacks with any MongoDB-level committed-use discount. Validate with both your AWS account team and MongoDB sales rep.

**Key question to ask:** "Does my Atlas Marketplace spend count toward my AWS EDP draw-down, and is there a private offer available that reduces the per-unit rate further?"

### When to trigger a renegotiation
- Annual Atlas spend > $100k: dedicated Technical Account Manager and discount eligibility.
- Annual Atlas spend > $250k: committed-use discount almost always warranted.
- At Okta's $300k cost optimization target: combination of right-sizing + committed-use renegotiation + Marketplace private offer is the typical playbook.

---

## 8. Cluster Pause

### What cluster pause does
Pausing a cluster in Atlas stops all compute charges (you continue to pay for storage). Atlas M0 (free) clusters are excluded; M10+ clusters can be paused via UI or API.

### Savings from pausing
For a paused cluster, you pay storage cost only — typically 5–15% of the running cluster cost. A paused M30 cluster ($0.54/hour compute) saves ~$389/month, paying only ~$20–40/month in storage.

### Cold-start time
Cluster resume takes 1–5 minutes (Atlas provisions the compute instances, mounts storage, initiates replica set election). Plan for this in CI/CD pipelines that spin up on-demand.

### Pause schedule automation
Use Atlas API + a cron job or Atlas Scheduled Triggers to automate pause/resume for non-production clusters:

```bash
# Pause cluster via Atlas API
curl --digest -u "$PUBLIC_KEY:$PRIVATE_KEY" \
  -X PATCH "https://cloud.mongodb.com/api/atlas/v2/groups/$PROJECT_ID/clusters/$CLUSTER_NAME" \
  -H "Content-Type: application/json" \
  -d '{"paused": true}'

# Resume
curl --digest -u "$PUBLIC_KEY:$PRIVATE_KEY" \
  -X PATCH "https://cloud.mongodb.com/api/atlas/v2/groups/$PROJECT_ID/clusters/$CLUSTER_NAME" \
  -H "Content-Type: application/json" \
  -d '{"paused": false}'
```

### Recommended pause schedule for dev/staging
- Pause: weekdays 8pm local time
- Resume: weekdays 7am local time
- Pause all weekend (Friday 8pm → Monday 7am)
- Savings: ~65% of compute hours eliminated

### Pause limitations
- Clusters with active Atlas Search indexes cannot be paused (as of Atlas 7.x).
- Clusters paused for more than 60 days are automatically resumed by Atlas (to prevent indefinitely stale configs). Set a calendar reminder or monitoring alert if long-term pause is intended.
- Paused clusters still run scheduled Atlas triggers and Atlas Charts queries — review and disable these before pausing.

---

## 9. Index Storage Cost

### Indexes and storage billing
Every index consumes disk storage, which is included in your cluster's storage billing. For large collections, indexes can represent 20–50% of total disk usage.

### The too-many-indexes anti-pattern
Teams frequently create indexes during development and never prune them. Common patterns:
- ESR (Equality, Sort, Range) indexes created separately instead of as compound indexes.
- Indexes created for a feature that was never launched or was retired.
- Redundant prefix indexes: `{a:1}` when `{a:1, b:1}` already exists (the compound covers the single-field case).
- Text indexes on every string field "just in case."

### Monitoring index size
In Atlas Data Explorer or mongosh:
```javascript
// Per-index sizes for a collection
db.myCollection.aggregate([
  { $indexStats: {} }
])

// Storage sizes including indexes
db.myCollection.stats({ indexDetails: true })

// Full database storage breakdown
db.runCommand({ dbStats: 1, scale: 1024 * 1024 })
```

Atlas Metrics also exposes "Index Size" at the cluster level in the Storage metrics group.

### Finding unused indexes
```javascript
// $indexStats tracks accesses since last restart
db.myCollection.aggregate([
  { $indexStats: {} },
  { $match: { "accesses.ops": { $lt: 100 } } },  // low access count
  { $sort: { "accesses.ops": 1 } }
])
```

For Atlas clusters, use Atlas Performance Advisor — it surfaces "Redundant Indexes" and "Unused Indexes" recommendations automatically.

### Safe index removal process
1. Identify candidate unused index via `$indexStats` over a 14-day window (catch monthly jobs).
2. Hide the index first: `db.collection.hideIndex("index_name")` — hidden indexes are maintained but not used by the query planner. Monitor for 1–2 weeks.
3. If no degradation observed, drop: `db.collection.dropIndex("index_name")`.
4. For large indexes (> 10 GB), expect an immediate disk space reduction after compaction.

---

## 10. Cost Monitoring

### Atlas Billing Dashboard
Navigate to Atlas Organization → Billing to see:
- **Invoices**: line-item breakdown by project and cluster.
- **Cost Explorer** (Atlas Advanced): filter by project, cluster, service type (compute, storage, backup, data transfer) across date ranges.
- **Usage details CSV export**: machine-readable daily usage for offline analysis.

### Tagging strategy
Atlas supports resource tags on projects and clusters. Align tags with your cloud provider's tagging taxonomy for cost allocation:
```
Environment: production | staging | development | qa
Team: platform | data-engineering | product-backend
CostCenter: CC-1234
Application: user-auth | analytics | search
```

Tags flow through to Marketplace bills and can be used in cloud provider Cost Explorer for consolidated reporting.

### Budget alerts
Set Atlas budget alerts at the organization and project levels:
- **Organization budget alert**: 90% and 110% of monthly budget.
- **Per-project alert**: for projects with known spend floors; alert at 120% of 3-month average.
- Alert destinations: email, PagerDuty, Slack webhook.

### Automated cost anomaly detection
Use the Atlas API to pull daily cost data and feed it to a cost anomaly tool (AWS Cost Anomaly Detection if using Marketplace, or a custom time-series alert). A 20% day-over-day spike in a project's cost is worth investigating — common causes are autoscale-up events, runaway Data Federation queries, or accidentally un-paused dev clusters.

### Monthly cost review cadence
For accounts > $10k/month Atlas spend, establish a monthly review:
1. Pull invoice line items, sort by cost descending.
2. Identify top 5 clusters by cost — are they appropriately sized?
3. Review autoscaling events in Activity Feed.
4. Check for orphaned clusters (no connections in 30 days per Atlas access logs).
5. Validate backup retention policies match current policy.

---

## 11. Tier 0 / Tier 1 / Tier 2 Strategy

### Tier definitions (internal operational classification)
This is a customer-defined classification, not an Atlas-native concept. Align with your SRE or platform team's existing tier model.

| Tier | Description | Recommended Config |
|---|---|---|
| Tier 0 | Revenue-critical, highest SLA (99.99%+) | M60+, multi-region RS or global cluster, PITR, Provisioned IOPS if needed, no pause |
| Tier 1 | Business-critical, standard SLA (99.9%) | M30–M50, single-region RS, standard IOPS, PITR enabled, no pause |
| Tier 2 | Non-critical, internal tools, analytics | M10–M30, single-region, standard IOPS, snapshot-only backup, pause outside business hours |

### Mixing tiers strategically
- **Don't gold-plate Tier 2**: a common mistake is running internal dashboards and analytics clusters at Tier 1 specs "because it's easy." An M30 with a 3-day daily snapshot is almost always sufficient for internal tools.
- **Separate clusters by tier**: avoid co-mingling Tier 0 and Tier 2 workloads on the same cluster (multi-tenancy) — a noisy Tier 2 workload can degrade Tier 0 performance.
- **Tier 2 pause savings**: if you have 20 Tier 2 clusters at M20 average, pausing them 65% of the time saves ~$5,000–$8,000/month.

### Okta-scale application
For an account targeting $300k in savings:
- Audit all clusters: classify into T0/T1/T2.
- Right-size T1 clusters (likely 20–40% of spend, 40% reduction = $30–60k savings).
- Pause T2 clusters off-hours (~$60–80k savings if significant T2 footprint).
- Negotiate committed-use discount on remaining T0/T1 spend (~15–25% = $60–120k savings).
- Prune backup retention on T1/T2 (~$20–30k savings).
- Total: $170–290k annualized, reaching or exceeding the $300k target with combined levers.

---

## 12. Common Cost Overruns

### Over-provisioned IOPS
**Pattern**: Team provisions io1 storage with 10,000 IOPS "to be safe" for a cluster consuming 600 IOPS at P95.
**Detection**: Atlas Metrics → Disk IOPS → compare provisioned vs actual over 30 days.
**Fix**: Switch to GP3 storage, set IOPS to `actual_P95 * 1.5` (minimum 3,000 for GP3).
**Savings**: Can be 50–70% of storage cost for over-provisioned io1 clusters.

### Oversized clusters
**Pattern**: M80 cluster purchased for a projected workload peak that never materialized. Team inherited it and never questioned the spec.
**Detection**: 30-day CPU P95 < 30% AND page faults near zero AND disk utilization < 50%.
**Fix**: Rolling tier-down via Atlas UI. Start one tier at a time, validate, continue.
**Savings**: Each tier step is roughly 40–60% cost reduction.

### Redundant backups
**Pattern**: Both continuous backups (PITR) and aggressive snapshot retention enabled on dev/staging clusters.
**Detection**: Atlas Billing → filter by "Backup" service type — compare backup cost vs compute cost per cluster. Backup > 30% of cluster cost is a red flag for non-production.
**Fix**: Disable PITR on staging; reduce to 1-day daily retention for dev clusters.

### Orphaned clusters
**Pattern**: Cluster created for a proof-of-concept 18 months ago. PoC ended, cluster never deleted.
**Detection**: Atlas Data Explorer or `listClusters` API → filter for clusters with zero connections in the past 30 days via Atlas access logs.
**Fix**: Confirm with application team, take final snapshot, delete cluster.

### Runaway Data Federation queries
**Pattern**: Atlas Data Federation configured to query S3 data on-demand. A scheduled report or misconfigured dashboard runs full-collection scans every 5 minutes.
**Detection**: Atlas Billing → Data Federation line items spiking. Atlas Data Federation logs show query frequency.
**Fix**: Add query result caching, reduce schedule frequency, add `$match` filters to reduce data scanned.

### Multi-region clusters where single-region suffices
**Pattern**: 3-region global cluster deployed "for availability" on an internal analytics workload that has no international users.
**Detection**: Atlas cluster topology → global write distribution map → low write/read volume outside primary region.
**Fix**: Convert to single-region RS with appropriate tier. 3-region global clusters are 3× the base compute cost.

### Forgotten Atlas Search indexes
**Pattern**: Atlas Search (Lucene) indexes deployed on collections that are no longer queried via Atlas Search (application switched to a different search path).
**Detection**: Atlas Search Index list → check `queryCount` via Atlas Search metrics. Search indexes on large collections add meaningful storage overhead.
**Fix**: Drop unused Search indexes via Atlas UI → Search → Indexes.

---

## References and Atlas Documentation Pointers

- [Atlas Cluster Autoscaling](https://cloud.mongodb.com/docs/atlas/cluster-autoscaling/)
- [Atlas Backup Documentation](https://cloud.mongodb.com/docs/atlas/backup/)
- [Atlas Billing](https://cloud.mongodb.com/docs/atlas/billing/)
- [Atlas Performance Advisor](https://cloud.mongodb.com/docs/atlas/performance-advisor/)
- [Atlas API — Clusters](https://cloud.mongodb.com/docs/atlas/reference/api-resources-spec/v2/#tag/Clusters)
- [$indexStats aggregation stage — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/operator/aggregation/indexStats/)

---

## 13. Atlas Flex Tier Cost Guidance

*Cross-pollinated from `mongodb-atlas-flex-serverless` — researched 2026-05-28.*

Flex is the entry-level paid Atlas tier ($8–$30/month hard cap) that replaced M2/M5 shared clusters and Serverless instances (EOL: January 22, 2026). It is the most cost-efficient option for development, staging, and low-traffic production workloads.

### When Flex saves money vs. dedicated
| Workload profile | Flex cost | M10 dedicated cost | Savings |
|-----------------|-----------|-------------------|---------|
| < 100 ops/sec, < 1 GB data | $8/mo | ~$57/mo | 86% |
| Sporadic bursts to 500 ops/sec | $8–$30/mo | ~$57/mo | 47–86% |
| Sustained 500 ops/sec (all month) | $30/mo | ~$57/mo | 47% |

### Flex billing model
- Ops/sec tiered, billed hourly prorated — $8 base (100 ops/sec, 5 GB), caps at $30/month at 500 ops/sec
- No per-document billing (unlike the deprecated Serverless RPU model)
- No runaway billing: $30/month is the absolute maximum regardless of load spikes

### When NOT to use Flex (upgrade to M10+ dedicated)
- Private Endpoints / VPC Peering required (security policy)
- PITR backup required (compliance)
- BYOK encryption at rest required
- Data > 5 GB
- Connections > 500
- Ops/sec > 500 sustained
- Atlas Vector Search going to production (resource contention on Flex)

### Multi-environment cost strategy
- M0 (Free): individual dev — $0
- Flex: shared dev/staging — $8–$30/mo (saves ~$500–700/mo vs multiple M10s)
- M10–M20: pre-production — $57–$100/mo
- M30+: production — $190+/mo

For full Flex technical limits, migration steps, and tooling, see `mongodb-atlas-flex-serverless`.
