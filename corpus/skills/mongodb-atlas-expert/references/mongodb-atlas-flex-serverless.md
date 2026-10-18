<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-flex-serverless` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

# MongoDB Atlas Flex Clusters and Serverless Instances

## Overview

MongoDB Atlas Flex tier (GA: February 6, 2025) is the successor to both the shared tier (M2/M5) and the serverless tier. As of January 22, 2026, M2/M5 clusters and Serverless instances are end-of-life and no longer supported — all existing instances were automatically migrated. Flex is now the entry-level paid cluster in Atlas, bridging the gap between the free M0 tier and full dedicated clusters (M10+).

**Why this matters for TAMs:** Customers with development clusters, MVPs, GenAI prototypes, or low-traffic SaaS products need accurate guidance on Flex vs. dedicated sizing thresholds, migration urgency, and billing predictability.

---

## Tier Landscape (2025–2026)

| Tier | Cost | RAM/vCPU | Storage | Connections | Network | Use Case |
|------|------|----------|---------|-------------|---------|----------|
| **M0 (Free)** | $0 | Shared, minimal | 512 MB | 500 | Public IP only | Exploration, learning |
| **Flex** | $8–$30/mo | Shared, elastic | 5 GB (hard cap) | 500 | Public IP only | Dev, staging, MVP, light prod |
| **M10 Dedicated** | ~$57/mo | 2 GB RAM, 2 vCPU | 10 GB+ | 1,500 | VPC Peering + PrivateLink | Production, consistent load |
| **M30 Dedicated** | ~$190/mo | 8 GB RAM, 2 vCPU | 40 GB+ | Higher | Full networking | Performance-critical prod |

---

## Serverless Instances (Deprecated)

### What Serverless Was
Atlas Serverless (launched 2022, deprecated 2025) offered fully elastic compute billed on a per-operation basis using two units:

- **RPU (Read Processing Unit):** One RPU = one document read (up to 4 KB) or one index key read (up to 256 bytes). Pricing: ~$0.10/million reads (first 50M/day), $0.05/million for next 500M/day, then $0.01/million.
- **WPU (Write Processing Unit):** One WPU = one write operation. Pricing: ~$1.00/million writes.
- **Storage:** $0.25/GB-month.

### Serverless Billing Hazards
The RPU model's per-document-scan cost created runaway charges for poorly indexed queries. A single unoptimized query scanning 20+ documents would charge 20+ RPUs per call. Real-world example: one developer experienced $54/day (~$19,710/year) from a single unindexed email count query. Proper partial compound indexes reduced this to near-zero.

### Cold Start Behavior
Serverless clusters suspended after ~5 minutes of idle, causing 30–60 second reconnect delays on first connection. This made serverless unsuitable for latency-sensitive applications that experience idle periods.

### Why Serverless Was Replaced
1. Unpredictable billing spikes from query inefficiency
2. Cold start latency made SLAs difficult to guarantee
3. Feature gaps: no Atlas Search, no Change Streams, no Triggers initially
4. Operational complexity of RPU optimization vs. just indexing for performance

---

## Atlas Flex Tier (Current Standard)

### Pricing Model
Flex uses an **ops-per-second tiered hourly model** capped monthly — no more per-document billing:

| Capacity (sustained) | Cumulative Monthly (if held all month) |
|----------------------|----------------------------------------|
| Base: 100 ops/sec + 5 GB storage | $8 |
| Burst to 200 ops/sec | $15 |
| Burst to 300 ops/sec | $21 |
| Burst to 400 ops/sec | $26 |
| Burst to 500 ops/sec | $30 (hard cap) |

**Key billing properties:**
- Billed hourly, prorated — you only pay for the tier you're in each hour, not sustained monthly commitment
- Burst to 500 ops/sec for 1 hour ≠ $30; that 1 hour costs a fraction of the monthly cap
- Cap is $30/month — no runaway billing even under sustained maximum load
- No auto-pause; Flex runs continuously (unlike M0 which pauses after 30 days idle)
- Example: 100 ops/sec for 20 days + 250 ops/sec for 5 days + 500 ops/sec for 5 days = ~$13.67

### Flex vs. Serverless: What Changed
| Aspect | Serverless (old) | Flex (new) |
|--------|------------------|------------|
| Billing unit | Per RPU/WPU per document | Per ops/sec tier, hourly |
| Max monthly cost | Unbounded | $30 hard cap |
| Cold start | Yes (~30–60 sec after idle) | No (always warm) |
| Atlas Search | No (not at launch; added late 2023) | Yes (full support) |
| Vector Search | No | Yes |
| Change Streams | Limited (no resume after pause) | Yes (full support) |
| Triggers | Limited | Yes |
| Connection limit | ~500 | 500 |
| Storage | ~1 TB (elastic) | 5 GB (hard cap) |
| Auto-pause | After 5 min idle | Never |

---

## Flex Cluster Technical Specifications

### Limits (from `docs/atlas/reference/flex-limitations/`)

| Resource | Limit |
|----------|-------|
| Max connections | 500 |
| Max ops/sec | 500 (read + write combined) |
| Max storage | 5 GB (auto-managed, cannot configure) |
| Max databases | 100 |
| Max collections | 500 total |
| Namespace length | 95 bytes |
| DB name length | 38 bytes |
| Sort in-memory | 32 MB |
| Aggregation stages | 50 max |
| BSON nesting depth | 50 levels |
| Query utilization | Must stay under 100% over any 5-min window |
| MongoDB version | Minimum 8.0; auto-upgrade only (user cannot select version) |

### Unsupported Features on Flex
- Private Endpoints (AWS PrivateLink, Azure Private Link, GCP PSC)
- VPC/VNet Peering (network peering connections of all kinds)
- Continuous Backup and Point-in-Time Restore (daily snapshot only, auto-enabled, cannot disable; limited retention — verify current retention window in Atlas UI)
- Database Auditing
- Customer Key Management (BYOK encryption at rest)
- Access tracking
- Rolling index builds
- Server-side JavaScript (`$where`, `mapReduce`)
- `noTimeout` cursor option
- `allowDiskUse` for aggregations
- `$currentOp`, `$listLocalSessions`, `$listSessions`, `$planCacheStats` aggregation stages
- `$$USER_ROLES` system variable
- Sharded clusters (replica sets only)
- Performance Advisor
- Real-Time Performance Panel
- Auto-indexing
- On-demand snapshots
- Manual failover testing

### Supported Features on Flex (vs. old M2/M5)
Flex adds significant capability over the old shared tiers:
- Atlas Search (full-text Lucene)
- Atlas Vector Search (HNSW — but with resource contention caveat)
- Change Streams
- Atlas Triggers and App Services
- Full driver compatibility

**Vector Search caveat:** On Flex, `mongod` and `mongot` share the same node. Resource contention causes higher query latency. MongoDB recommends upgrading to dedicated (M10+) with Search Nodes before production.

### Regional Availability
Flex is available in a subset of AWS, GCP, and Azure regions (not all dedicated cluster regions). Check Atlas UI for available regions per cloud provider.

---

## Migration Timeline and EOL

| Date | Event |
|------|-------|
| February 2025 | Flex GA. New M2/M5 and Serverless creation disabled across all tooling |
| March 2025 | Atlas auto-migrated Serverless instances to Free/Flex/Dedicated based on usage |
| January 22, 2026 | EOL: M2/M5 and Serverless no longer supported. All remaining instances migrated |

### What Was Migrated To What
- M2/M5 clusters → Flex clusters (automatic)
- Serverless instances → Free, Flex, or Dedicated (based on usage pattern)

---

## Tooling Migration (Serverless/M2/M5 → Flex)

### Atlas CLI
```bash
# Create a Flex cluster
atlas clusters create my-flex-cluster \
  --provider AWS --region US_EAST_1 \
  --tier FLEX --projectId <projectId>

# List clusters (Flex shows tier=FLEX)
atlas clusters list --projectId <projectId>

# Upgrade Flex → Dedicated
atlas clusters upgrade my-flex-cluster \
  --tier M10 --projectId <projectId>
```

### Atlas Admin API
- Old serverless endpoint `creategroupserverlessinstance` → now maps to Flex
- `listgroupprivateendpointserverlessinstanceendpoint` is deprecated and errors

### Terraform
```hcl
# Use the flex_cluster resource
resource "mongodbatlas_flex_cluster" "example" {
  project_id = var.project_id
  name       = "my-flex-cluster"
  provider_settings = {
    backing_provider_name = "AWS"
    region_name           = "US_EAST_1"
  }
}
```

> **CloudFormation note:** Do NOT use `MongoDB::Atlas::FlexCluster` in CloudFormation — use `MongoDB::Atlas::Cluster` instead. Future updates will only be available through the main Cluster resource.

### Kubernetes Operator
- Upgrade to Atlas Kubernetes Operator 2.12.0+ (serverless-dependency-free)
- Use `spec.flexSpec` in `AtlasDeployment` CRD

```yaml
spec:
  flexSpec:
    providerSettings:
      backingProviderName: AWS
      regionName: US_EAST_1
```

- To upgrade Flex → Dedicated via Kubernetes:
```yaml
spec:
  upgradeToDedicated: true
```

---

## Flex vs. Dedicated Decision Matrix

Use this to guide customers on when to stay on Flex vs. upgrade:

### Stay on Flex if ALL of these are true:
- Peak throughput stays under 500 ops/sec
- Data < 5 GB total
- Concurrent connections < 500
- No private networking requirement (no VPC peering, no PrivateLink)
- No PITR backup requirement
- No BYOK encryption requirement
- Development, staging, prototype, or low-traffic production

### Move to Dedicated (M10+) when ANY of these trigger:
- Approaching 500 ops/sec peak consistently
- Data exceeds or will exceed 5 GB
- Need private endpoints or VPC peering (security policy)
- Need PITR (compliance requirement)
- Need BYOK encryption at rest
- Need Performance Advisor for query optimization
- Atlas Vector Search going to production (resource contention on Flex)
- SLA requires predictable low-latency (dedicated resources)
- Need more than 500 concurrent connections
- Need custom MongoDB version pinning

### Cost Break-Even Analysis
- Flex max: $30/month
- M10 dedicated: ~$57/month
- Break-even: If consistently hitting 400–500 ops/sec and needing M10 features, dedicated is ~2x cost but provides isolation, PrivateLink, and PITR
- For light workloads (<100 ops/sec, <1 GB data): Flex saves 85%+ vs. M10

---

## Migration Path: Flex → Dedicated

### Process
1. **Atlas UI:** Cluster card → "..." menu → "Modify Cluster" → select M10+ tier
2. **Admin API:** `PATCH /groups/{groupId}/clusters/{clusterName}` with new tier
3. **Kubernetes Operator:** Set `spec.upgradeToDedicated: true`

### Important Caveats
- **One-way:** You CANNOT downgrade from dedicated back to Flex
- **Downtime:** Upgrading Flex → M10+ incurs downtime
- **Snapshots not migrated:** Download existing Flex snapshots before upgrading — they do not transfer to dedicated
- **Restart apps:** After upgrade, restart application servers to reconnect with new connection string

---

## Free Tier (M0) vs. Flex Quick Comparison

| Feature | M0 (Free) | Flex |
|---------|-----------|------|
| Cost | $0 | $8–$30/mo |
| Storage | 512 MB | 5 GB |
| Connections | 500 | 500 |
| Atlas Search | Yes | Yes |
| Vector Search | Yes | Yes |
| Backups | No | Daily snapshot (automatic) |
| Auto-pause | Yes (30 days idle) | No |
| Cold start after pause | ~30 sec | N/A (never pauses) |
| Per-project limit | 1 per project | Multiple |

**Key insight:** M0 auto-pauses after 30 days idle and has a cold start on resume. Flex does not pause, making it more suitable for always-on dev/staging environments even with infrequent traffic.

---

## Practical Patterns

### Pattern 1: GenAI / RAG Prototype on Flex
Use Flex for embedding storage + Vector Search POC. At $8–$30/mo it's cheaper than any dedicated tier. When moving to production, upgrade to M30+ with dedicated Search Nodes for workload isolation.

```python
# connection string pattern for Flex — same as dedicated
MONGO_URI = "mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/?retryWrites=true&w=majority"
```

### Pattern 2: Multi-Environment Strategy
- M0 (Free): individual developer testing
- Flex ($8–$30): shared dev/staging environment
- M10–M20 ($57–$100): pre-production
- M30+ ($190+): production

### Pattern 3: Monitoring Flex Cost
Flex provides limited metrics: Connections, Logical Size, Network, Opscounter only. Set Atlas billing alerts at 80% of budget. The $30 cap prevents runaway costs entirely.

### Pattern 4: Serverless → Flex Migration (for existing users)
If the customer has old serverless tooling:
1. Remove all `serverless_instance` Terraform resources
2. Replace with `flex_cluster` resources
3. Remove `continuousBackupEnabled` parameter (not supported on Flex)
4. Remove serverless private endpoint configuration
5. Upgrade Atlas Kubernetes Operator to 2.12.0+

---

## Anti-Patterns

- **Using Flex for production with PrivateLink requirement:** Flex does not support private endpoints — any security policy requiring no public internet exposure must use dedicated M10+.
- **Running production Vector Search on Flex:** Resource contention between `mongod` and `mongot` causes latency spikes. Upgrade to M10+ with dedicated Search Nodes before going to production.
- **Expecting PITR on Flex:** Daily snapshots only. If compliance requires PITR, use M10+ with continuous cloud backup.
- **Pinning MongoDB version on Flex:** Flex auto-upgrades. If version pinning is required (e.g., ISV certification), use dedicated.
- **Overbuilding M10 for dev/staging:** Flex handles dev and staging fine at 1/7th the cost of M10. Reserve M10+ for actual production.
- **Relying on RPU calculations for cost estimation:** The serverless RPU model is deprecated. Flex uses ops/sec; stop trying to estimate RPUs.

---

## Troubleshooting

### "I'm hitting my 500 ops/sec limit"
- Symptoms: Query slowdowns, increased latency at peak
- Action: Either upgrade to M10 dedicated, or optimize queries/indexes to reduce operation count
- Flex throttles at 500 ops/sec — it does not auto-scale beyond that

### "My Flex data is at 5 GB limit"
- Flex has a 5 GB hard cap — storage does not auto-expand
- Drop unnecessary indexes (often 30–50% of storage)
- Archive cold data to Atlas Data Federation / S3
- Upgrade to dedicated if 5 GB is regularly needed

### "I need to restore a specific point in time"
- Not available on Flex (daily snapshots only)
- Upgrade to M10+ with continuous cloud backup for PITR
- As interim: use mongodump/mongorestore from most recent daily snapshot

### "Atlas Search is slow on Flex"
- `mongot` (Search) and `mongod` share node resources on Flex
- Expected for POC; upgrade to M10+ with dedicated Search Nodes for production

### "My Serverless instance was migrated but Terraform is broken"
- The `mongodbatlas_serverless_instance` resource is deprecated
- Replace with `mongodbatlas_flex_cluster` or `mongodbatlas_advanced_cluster`
- Remove `continuousBackupEnabled` and serverless private endpoint references

### "Can I go back from dedicated to Flex?"
- No. Dedicated → Flex downgrade is not supported
- Plan upgrades carefully; test on Flex, then upgrade permanently to dedicated

---

## References

1. MongoDB Blog: "Dynamic Workloads, Predictable Costs: The MongoDB Atlas Flex Tier" (Feb 2025) — https://www.mongodb.com/blog/post/dynamic-workloads-predictable-costs-mongodb-atlas-flex-tier
2. MongoDB Docs: Atlas Flex Cluster Limitations — https://www.mongodb.com/docs/atlas/reference/flex-limitations/
3. MongoDB Docs: Manage Flex Clusters — https://www.mongodb.com/docs/atlas/manage-flex-clusters/
4. MongoDB Docs: Migrate Programmatic Tools from M2/M5/Serverless to Flex — https://www.mongodb.com/docs/atlas/flex-migration/
5. MongoDB Docs: Atlas Free Cluster Limits — https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/
6. MongoDB Docs: Atlas Vector Search Deployment Options — https://www.mongodb.com/docs/atlas/atlas-vector-search/deployment-options/
7. MongoDB Products: "Now GA: MongoDB Atlas Flex Tier" (Feb 6, 2025) — https://www.mongodb.com/products/updates/now-ga-mongodb-atlas-flex-tier/
8. CloudZero: MongoDB Pricing Explained (2025) — https://www.cloudzero.com/blog/mongodb-pricing/
9. Inboxes App: "MongoDB Serverless: A Cautionary Tale" — https://inboxesapp.com/mongodb-serverless-a-cautionary-tale/
10. MongoDB Community: High Serverless WPU Pricing discussion — https://www.mongodb.com/community/forums/t/high-serverless-instance-wpu-pricing/261523
11. MongoDB Docs: Atlas Service Limits — https://www.mongodb.com/docs/atlas/reference/atlas-limits/
12. MongoDB Atlas Pricing Calculator — https://www.mongodb.com/pricing/calculator
