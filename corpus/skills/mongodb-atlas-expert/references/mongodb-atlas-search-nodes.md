<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-search-nodes` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-search-nodes
description: >-
  Dedicated search infrastructure tier that decouples Atlas Search and Vector
  Search workloads from data-bearing mongod nodes. Covers tier sizing
  (S20–S90 HIGHCPU, Low-CPU, Storage-Optimized), embedded vs dedicated decision
  matrix, enabling via UI/Terraform/CLI/Kubernetes Operator, replication model,
  cost, monitoring, zero-downtime migration, and limitations. TRIGGER: advising
  on Atlas Search performance isolation; dedicated search tier sizing; migration
  from embedded mongot; Search Node monitoring; mongot OOM or CPU alert fired;
  IaC setup for search nodes. SKIP: Atlas Search index design, analyzers, or
  $search query syntax (mongodb-search-ai); Vector Search ANN tuning or
  $vectorSearch patterns (mongodb-atlas-vector-search); general Atlas cluster
  sizing unrelated to search (mongodb-capacity-planning).
category: mongodb
version: "1.1.0"
updated: "2026-05-29"
tags:
  - mongodb
  - atlas
  - atlas-search
  - vector-search
  - mongot
  - search-nodes
  - dedicated-search
  - performance
  - infrastructure
  - terraform
  - kubernetes
keywords:
  - atlas search nodes
  - dedicated search nodes
  - mongot
  - S20_HIGHCPU_NVME
  - S30_HIGHCPU_NVME
  - S50_HIGHCPU_NVME
  - S80_HIGHCPU_NVME
  - search node sizing
  - embedded mongot vs search nodes
  - mongodbatlas_search_deployment
  - atlas search performance
  - search replication lag
  - atlas search monitoring
  - search node migration
  - search node cost
  - workload isolation
  - atlas search tier
whenToUse:
  - "Atlas Search is slowing down my cluster — should I use dedicated Search Nodes"
  - "mongot OOM alert fired — what are my options"
  - "size dedicated Search Nodes for production Atlas Search workload"
  - "migrate from embedded mongot to dedicated Search Nodes"
  - "Search Normalized Process CPU above 70% sustained"
  - "configure Search Nodes in Terraform or Atlas CLI"
  - "Search Nodes in Kubernetes Operator AtlasDeployment CRD"
  - "what is the difference between S20_HIGHCPU_NVME and S30_LOWCPU_NVME"
  - "Search Node replication lag above 1 second"
  - "cost of dedicated Search Nodes vs scaling up the data cluster tier"
whenNotToUse:
  - "Atlas Search index definition, analyzers, or $search query syntax — use mongodb-search-ai"
  - "Vector Search ANN index tuning or $vectorSearch patterns — use mongodb-atlas-vector-search"
  - "General Atlas cluster sizing unrelated to search — use mongodb-capacity-planning"
related_skills:
  - mongodb-search-ai
  - mongodb-atlas-vector-search
  - mongodb-cost-optimization
  - mongodb-monitoring-observability
  - mongodb-atlas-expert
  - mongodb-atlas-terraform
  - mongodb-atlas-kubernetes-operator
---

# MongoDB Atlas Search Nodes

> Dedicated search infrastructure tier that decouples Atlas Search and Vector Search workloads from data-bearing mongod nodes. Use this skill when advising on Atlas Search performance isolation, dedicated search tier sizing, migration from embedded mongot, or Search Node monitoring.
>
> **Skip this skill** when the question is about Atlas Search index design, query syntax, or analyzers — use [[mongodb-search-ai]] instead. For Vector Search ANN tuning or quantization, use [[mongodb-atlas-vector-search]].

## Overview

Atlas Search Nodes are a separate compute tier within MongoDB Atlas that runs only the `mongot` process (the Apache Lucene-based search engine). They were announced in public preview in 2023 and reached general availability on December 4, 2023 for AWS, with Google Cloud and Azure GA on June 25, 2024. Multi-region availability reached all three major cloud providers in August 2024 / March 2025.

**When to use this skill:**
- Customer asks "why is Atlas Search slowing down my cluster?"
- Advising on production Atlas Search or Vector Search deployments
- Sizing or cost analysis for search infrastructure
- Enabling or migrating to dedicated Search Nodes
- Monitoring and alerting for search workloads
- IaC (Terraform, Kubernetes Operator) setup for search nodes

**When NOT to use this skill:**
- Atlas Search index definition, analyzers, tokenizers, or `$search` query syntax → [[mongodb-search-ai]]
- Vector Search ANN index tuning or `$vectorSearch` query patterns → [[mongodb-atlas-vector-search]]
- General Atlas cluster sizing unrelated to search → [[mongodb-capacity-planning]]

---

## 1. What Are Search Nodes

### The mongot Process

Every Atlas cluster that has Atlas Search indexes runs a process called `mongot` alongside each `mongod` node. `mongot` is a Java-based web process that:
- Maintains all Atlas Search (Lucene) and Vector Search indexes
- Processes `$search` and `$vectorSearch` aggregation pipeline stages
- Uses MongoDB Change Streams to replicate writes from `mongod` into the Lucene index
- Consumes CPU, memory, and disk independently from `mongod`

In the **embedded** (default) deployment, `mongot` shares CPU, RAM, and disk with `mongod` on the same node. This means search workloads compete directly with database workloads for resources.

### What Dedicated Search Nodes Change

Search Nodes are Atlas nodes that **only run `mongot`** — they are not data-bearing. They are deployed as a separate tier alongside the existing replica set:

```
[Replica Set]            [Search Tier]
  mongod (Primary)         mongot (Search Node 1)
  mongod (Secondary)  -->  mongot (Search Node 2)
  mongod (Secondary)       mongot (Search Node 3) [optional]
     |
     | Change Streams
     v
  mongot on each Search Node independently replicates
```

Key architectural properties:
- Search Nodes do **not** store MongoDB documents; they only store Lucene index data
- Each Search Node runs a fully independent replica of all search indexes
- Queries are routed through a load balancer across all `mongot` processes on Search Nodes
- Enables concurrent intra-query parallelism using the `$search` `concurrent` option
- Storage and query load become fully independent of the MongoDB cluster tier

### Supported Atlas Tiers

Search Nodes require:
- **M10 or higher** dedicated cluster (not available on M0 Free Tier or Flex clusters)
- An active Atlas Search or Vector Search index on the cluster

---

## 2. Search Node Tiers

Search Nodes are offered in three classes with NVMe-backed local storage:

### High-CPU Nodes (`_HIGHCPU_NVME`)

Optimized for high-throughput full-text search, lexical search, and workloads with high query rates or complex query patterns.

**RAM:vCPU ratio: 2:1**

| Tier | vCPUs | RAM | NVMe Storage Range |
|------|-------|-----|--------------------|
| S20_HIGHCPU_NVME | 2 | 4 GB | 100–200 GB |
| S30_HIGHCPU_NVME | 4 | 8 GB | ~200–400 GB |
| S50_HIGHCPU_NVME | 8 | 16 GB | ~400–800 GB |
| S60_HIGHCPU_NVME | 16 | 32 GB | ~800–1,600 GB |
| S80_HIGHCPU_NVME | 32 | 64 GB | ~1,600–3,200 GB |
| S90_HIGHCPU_NVME | 64 | 128 GB | ~3,200 GB |

### Low-CPU Nodes

Memory-intensive workloads, vector search where embedding indexes fit comfortably in RAM.

**RAM:vCPU ratio: 8:1**

| Tier | vCPUs | RAM | NVMe Storage Range |
|------|-------|-----|--------------------|
| S30_LOWCPU_NVME | 2 | 16 GB | 50–100 GB |

### Storage-Optimized Nodes

For workloads where index size is the primary scaling constraint (very large text indexes, binary-quantized vector search at scale), not query throughput.

**RAM:vCPU ratio: 8:1, but 2–3x more NVMe storage than High-CPU at the same RAM**

| Tier | Relative Cost vs High-CPU |
|------|--------------------------|
| S40_LOWCPU_NVME (storage-optimized) | ~40% cheaper per GB of storage |

Storage-optimized nodes provide:
- 2x+ storage capacity vs. High-CPU nodes at the same specs
- Up to 50% savings on search node storage costs for index-heavy workloads
- Up to 6,000 GB NVMe storage on larger tiers

> **Note:** Exact per-tier CPU/RAM specs are region- and cloud-provider-dependent. Always verify current values in the Atlas UI or Admin API (`GET /api/atlas/v2/groups/{groupId}/clusters/{clusterName}/search/deployment`) before sizing.

### Choosing a Tier

| Primary Constraint | Recommended Class |
|-------------------|-------------------|
| High QPS (>100), complex lexical queries | High-CPU |
| Latency-sensitive search, high concurrency | High-CPU (vertical scale) |
| Large vector indexes, moderate QPS | Low-CPU or Storage-Optimized |
| Index footprint > 1 TB, binary quantization | Storage-Optimized |
| Development / testing | Embedded (no Search Nodes) |

**Baseline sizing estimate:**
- ~10 QPS per vCPU core under sustained load
- Minimum production setup: 2× S20_HIGHCPU_NVME = 4 vCPUs → ~40 QPS
- RAM should be at least 10% larger than your total index size

---

## 3. Embedded mongot vs Search Nodes Decision

### When Embedded mongot Is Sufficient

- **Development, testing, staging** — resource sharing is acceptable
- **Low QPS** — fewer than 20–30 search queries/second
- **Small index size** — indexes fit comfortably within the memory allocation for mongot on the data node
- **Infrequent search use** — search is not a critical path for the application

On dedicated cluster tiers, mongot gets approximately:
| Cluster Tier | Total RAM | RAM available to mongot |
|---|---|---|
| M10 | 2 GB | ~1 GB (50%) |
| M20 | 4 GB | ~2 GB (50–75%) |
| M30 | 8 GB | ~4 GB |
| M40+ | Varies | ~50% |

### Signs You Need Dedicated Search Nodes

**CPU signals:**
- `Search Normalized Process CPU` consistently above 60–70%
- Data node CPU spikes during search query bursts (indicating contention)
- `mongot` CPU alerts firing frequently

**Memory signals:**
- `Search Process: Ran out of memory` alert fires
- `Search JVM Heap Memory` consistently near its cap
- Query latency degrades as JVM GC pressure increases

**Performance signals:**
- P99 search latency > 1 second on queries that should be <200ms
- Replication lag for search indexes consistently above 1 second
- `mongod` query latency increases during high search load

**Workload signals:**
- Vector search index > 2 GB RAM
- Large full-text index (> 5 GB on disk)
- Search QPS > 30 on embedded nodes
- Production SLA requires search availability independent of database maintenance

### Summary Decision Matrix

| Signal | Threshold | Action |
|--------|-----------|--------|
| Search Normalized Process CPU | > 70% sustained | Migrate to Search Nodes |
| mongot OOM alert fires | Any | Migrate to Search Nodes or scale up data tier |
| Data node CPU spikes track search QPS | Correlated | Migrate to Search Nodes |
| P99 search latency | > 1s for <200ms queries | Migrate to Search Nodes |
| Index size vs node RAM | > 50% of available mongot RAM | Migrate to Search Nodes |
| Replication lag | > 1s sustained | Migrate + scale Search Nodes |
| Search QPS | > 30 on embedded | Migrate to Search Nodes |
| Environment | Dev / test / staging | Embedded is fine |

---

## 4. Enabling Search Nodes

### Via Atlas UI

1. Navigate to **Database → Clusters → Edit Configuration** for your cluster
2. Select the **Cloud Provider & Region** tab
3. Scroll to **Search Nodes for Workload Isolation** section
4. Choose a **Search Tier** (e.g., S20_HIGHCPU_NVME)
5. Set **Number of Search Nodes** (minimum 2, maximum 32)
6. Review cost impact and click **Apply Changes**

Atlas will:
- Deploy the new Search Nodes
- Perform initial sync — build all indexes on the new nodes while continuing to serve queries from embedded mongot
- Switch query routing to Search Nodes once all indexes are built
- Remove embedded mongot indexes from data nodes

### Via Terraform

Use the `mongodbatlas_search_deployment` resource (separate from `mongodbatlas_advanced_cluster`):

```hcl
resource "mongodbatlas_advanced_cluster" "main" {
  project_id   = var.project_id
  name         = "prod-cluster"
  cluster_type = "REPLICASET"

  replication_specs {
    region_configs {
      provider_name = "AWS"
      region_name   = "US_EAST_1"
      priority      = 7
      electable_specs {
        instance_size = "M30"
        node_count    = 3
      }
    }
  }
}

resource "mongodbatlas_search_deployment" "search" {
  project_id   = mongodbatlas_advanced_cluster.main.project_id
  cluster_name = mongodbatlas_advanced_cluster.main.name

  specs = [
    {
      instance_size = "S20_HIGHCPU_NVME"
      node_count    = 2
    }
  ]
}
```

> The `specs` array currently supports only **one element** (one instance size per cluster). To change tier, update `instance_size`; to scale horizontally, update `node_count`.

### Via Atlas CLI

```bash
# Create a search nodes config file (search-nodes.json)
cat > search-nodes.json << 'EOF'
{
  "specs": [
    {
      "instanceSize": "S20_HIGHCPU_NVME",
      "nodeCount": 2
    }
  ]
}
EOF

# Create search nodes for a cluster
atlas clusters search nodes create \
  --clusterName prod-cluster \
  --projectId <projectId> \
  --file search-nodes.json

# List search nodes
atlas clusters search nodes list --clusterName prod-cluster

# Update (scale) search nodes
atlas clusters search nodes update \
  --clusterName prod-cluster \
  --file search-nodes-updated.json

# Delete search nodes (reverts to embedded mongot)
atlas clusters search nodes delete --clusterName prod-cluster
```

### Via Kubernetes Operator

In the `AtlasDeployment` custom resource, add `searchNodes` under `spec.deploymentSpec`:

```yaml
apiVersion: atlas.mongodb.com/v1
kind: AtlasDeployment
metadata:
  name: prod-cluster
  namespace: mongodb-atlas-system
spec:
  deploymentSpec:
    clusterType: REPLICASET
    name: prod-cluster
    replicationSpecs:
    - regionConfigs:
      - electableSpecs:
          instanceSize: M30
          nodeCount: 3
        priority: 7
        providerName: AWS
        regionName: US_EAST_1
      zoneName: Zone 1
    searchNodes:
    - instanceSize: S20_HIGHCPU_NVME
      nodeCount: 2
  projectRef:
    name: my-project
    namespace: mongodb-atlas-system
```

> `backingProviderName` is only required for multi-cloud or multi-region configs. Single-provider single-region deployments use `providerName` only.

Field reference for `searchNodes[]`:
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `instanceSize` | string | No | Tier name, e.g. `S20_HIGHCPU_NVME` |
| `nodeCount` | integer | No | Min: 2, Max: 32 |

---

## 5. Scaling

### Horizontal Scaling (Adding Nodes)

Increase `nodeCount` to add more Search Nodes. Additional nodes:
- Receive a full replica of all search indexes
- Participate in load balancing for incoming `$search` / `$vectorSearch` queries
- Increase aggregate QPS capacity (~10 QPS per vCPU added)

Maximum: **32 Search Nodes per cluster/shard/region**.

```bash
# Scale from 2 to 4 nodes via CLI
atlas clusters search nodes update \
  --clusterName prod-cluster \
  --file '{"specs":[{"instanceSize":"S20_HIGHCPU_NVME","nodeCount":4}]}'
```

### Vertical Scaling (Tier Upgrade)

Change `instanceSize` to a higher tier to increase RAM, CPU, and disk per node. Use vertical scaling when:
- P99 latency is high despite CPU < 70% (memory pressure, I/O bottleneck)
- Index size approaches RAM capacity on current tier
- Complex query patterns need more vCPUs per node

### Autoscaling

**Search Nodes do not support automatic autoscaling as of 2025.** Scaling is manual-only — you must change `nodeCount` or `instanceSize` through the UI, Terraform, CLI, or API. Monitor metrics and scale proactively.

Cluster data node autoscaling (for `mongod`) has no effect on Search Nodes.

### Scaling Guidelines

| Constraint | Solution |
|---|---|
| QPS capacity insufficient | Add nodes horizontally (increase `nodeCount`) |
| P99 latency high | Scale vertically (upgrade `instanceSize`) |
| Index size approaching disk cap | Upgrade tier or switch to storage-optimized |
| Replication lag > 1s during write bursts | Add cluster secondaries, shard if > 10k ops/sec |
| Budget-constrained, large index footprint | Use storage-optimized tier |

---

## 6. Search Replication

### How Search Nodes Replicate Indexes

Each Search Node maintains a **complete, independent replica** of all search indexes for the cluster (or shard, in sharded clusters). The replication mechanism:

1. Each Search Node's `mongot` process subscribes to the MongoDB **Change Stream** for every collection that has a search index
2. As write operations (inserts, updates, deletes) occur on the replica set, the primary and secondaries publish change events to the oplog
3. Each `mongot` process tails the oplog via Change Streams and applies changes to its local Lucene index independently
4. This means each Search Node is effectively an independent read replica of the search index

### Leader/Follower Model

Unlike a traditional leader-follower replication model, Search Nodes do **not** replicate from each other. Each Search Node independently replicates from the MongoDB replica set's oplog. There is no designated "primary" search node — all nodes are equivalent replicas.

**Query routing:** Queries are distributed across all healthy Search Nodes via a load balancer. If one Search Node is unhealthy, queries route to the remaining nodes.

### Consistency Guarantees

- Search indexes have **eventual consistency** relative to the primary mongod — there is always some replication lag (typically milliseconds to seconds under normal load)
- The `$search` stage does not guarantee linearizable reads; it reflects the state of the search index at the time of the query
- **Index Replication Lag** is the key metric: measures how many milliseconds `mongot` is behind in replicating from the oplog
- If replication lag exceeds the oplog window, `mongot` falls off the oplog and must perform a full index rebuild (indexes go stale during rebuild)

### During Initial Sync

When Search Nodes are first enabled on a cluster with existing data:
- The new Search Nodes perform a **full initial sync** (building all indexes from scratch)
- During this period, the old embedded `mongot` processes on data nodes continue serving queries
- Atlas does not switch query routing to Search Nodes until all indexes are built successfully
- **No query downtime** during initial sync

### Replication Lag Targets

| Lag | Status |
|-----|--------|
| < 1 second | Healthy |
| 1–10 seconds | Monitor closely, investigate write volume |
| > 10 seconds | Alert, scale up or reduce write pressure |
| Falls off oplog | Full index rebuild required (may take hours) |

---

## 7. Cost Model

### Pricing Structure

Search Nodes are **billed separately** from data nodes. You pay for:
1. Data node cluster tier (M10, M30, M50, etc.) — unchanged
2. **Search Node tier × node count** — additive charge per hour

MongoDB does not publicly list per-node prices (they vary by cloud, region, and commitment type). Use the [Atlas Pricing Calculator](https://www.mongodb.com/pricing/calculator) to estimate costs for your specific configuration.

### Cost Drivers

- **Instance size**: Higher CPU/RAM/NVMe tiers cost more per hour
- **Node count**: Each additional node multiplies the per-node cost
- **Cloud provider and region**: Pricing varies across AWS, GCP, Azure, and by region
- **Commitment**: On-demand vs. annual commitment discounts (aligned to cluster discount tiers)

### Storage-Optimized Tiers for Cost Savings

If your primary scaling constraint is index storage (not CPU/QPS), storage-optimized nodes are approximately **40% cheaper** than High-CPU nodes at equivalent storage capacity. For large binary-quantized vector search deployments, this can represent significant savings.

### Cost vs. Scaling Up Data Nodes

The alternative to Search Nodes is scaling up the data node tier to give more RAM and CPU to the embedded `mongot`. The break-even analysis depends on:

| Factor | Favors Search Nodes | Favors Larger Data Nodes |
|--------|--------------------|-----------------------|
| Search is a primary workload | Yes | — |
| Data tier already right-sized for DB | Yes (don't over-provision for search) | — |
| Search workload is light/infrequent | — | Yes |
| Need search HA independent of DB | Yes | — |
| Cost sensitivity, small workload | — | Yes (simpler, one bill) |
| Production with SLA requirements | Yes | — |

**Rule of thumb:** If you would need to jump 2+ M-tier levels (e.g., M30 → M60) primarily because of mongot, dedicated Search Nodes are almost always cheaper and provide better isolation.

### Enterprise Discounts

Search Node pricing is eligible for the same enterprise commit discounts as cluster pricing. MongoDB's default negotiating position is to protect Search Node pricing while discounting cluster aggressively — push for aligned discounts. Price-protection clauses lock Search Node rates for contract terms.

---

## 8. Monitoring

### Search Node Metrics Tab

Dedicated Search Nodes have their own **Metrics tab** in the Atlas UI (separate from the cluster metrics tab). Navigate to:
**Database → Clusters → [Cluster Name] → Search Nodes tab → View Metrics**

### Key Metrics

| Metric | What It Measures | Alert Threshold |
|--------|-----------------|-----------------|
| `Search Process CPU` | % CPU used by mongot (can exceed 100% on multi-core) | > 70% sustained |
| `Search Normalized Process CPU` | CPU scaled to 0–100% by dividing by core count | > 70% |
| `Search JVM Heap Memory` | JVM heap currently in use | > 80% of JVM max heap |
| `Search Process Memory` | Total bytes occupied by mongot | Approach node RAM limit |
| `Search Index Size` | Total index size on disk | Approach 85% of disk |
| `Search Disk Space Used` | Total bytes used (indexes + logs + diagnostics) | > 85% disk capacity |
| `Search Max Replication Lag` | ms behind oplog replication | > 1,000 ms (1 second) |
| `Search Fields Indexed` | Total fields across all search indexes | — |
| `Search Opcounters` | Operations per second (insert/update/delete/getmore) | — |
| `Search Query Status` | Successful vs. error query counts | Error count > 0 |
| `Search Page Fault` | Page faults per second | Elevated = memory pressure |

### Atlas Search Alerts (Dedicated Search Nodes)

Configure these alerts via **Atlas UI → Project Settings → Alerts**:

| Alert | Trigger | Severity |
|-------|---------|----------|
| `Atlas Search: Index Replication Lag` | mongot behind oplog by threshold ms | Critical if near oplog window |
| `Atlas Search: Mongot stopped replication` | Disk ≥ 90%, replication paused | Critical (search-nodes-only alert) |
| `Atlas Search: Mongot is approaching replication stop threshold` | Disk ≥ 85% | Warning |
| `Atlas Search: Mongot paused initial sync` | High disk during initial sync | Warning |
| `Search Process: Ran out of memory` | mongot OOM | Critical (auto-enabled) |
| `Search Process: CPU (User) %` | CPU exceeds threshold | Warning |
| `Atlas Search: Index Size on Disk` | Total index bytes threshold | Warning |
| `Insufficient disk space to rebuild search indexes` | Cannot rebuild | Critical (auto-enabled) |

> `Atlas Search: Mongot stopped replication` is **only available for dedicated Search Nodes** — it does not fire for embedded mongot deployments.

### Programmatic Metrics Access

```bash
# Retrieve search metrics via Atlas Admin API
curl --header "Authorization: Bearer {ACCESS-TOKEN}" \
     --header "Accept: application/vnd.atlas.2023-01-01+json" \
     "https://cloud.mongodb.com/api/atlas/v2/groups/{groupId}/hosts/{processId}/fts/metrics/indexes/{db}/{collection}/{indexName}/measurements?granularity=PT1M&period=PT1H&metrics=SEARCH_INDEX_SIZE,SEARCH_MAX_REPLICATION_LAG"
```

---

## 9. Migration from Embedded mongot

### Overview

Moving from embedded mongot (collocated with mongod) to dedicated Search Nodes is a **zero-downtime operation** when adding Search Nodes. Removing Search Nodes has downtime — avoid unless intentional.

### Adding Search Nodes (Zero Downtime)

When you configure Search Nodes on a cluster that currently uses embedded mongot:

1. **Atlas deploys new Search Nodes** in the background
2. **Embedded mongot continues serving queries** — no interruption
3. New Search Nodes perform a **full initial sync** (build all indexes from scratch from the oplog)
4. During initial sync, **dual reads** occur: embedded mongot handles live queries while new Search Nodes build indexes
5. Once all indexes are built on all Search Nodes, Atlas **atomically switches query routing** to the new Search Nodes
6. Atlas then **removes embedded mongot indexes** from data nodes, freeing resources

**Expected impact:** No query downtime. The initial sync duration depends on index size and write throughput.

### Post-Migration Verification

After migration, verify:
```javascript
// Check that $search queries return results
db.collection.aggregate([
  { $search: { text: { query: "test", path: "field" } } }
])

// Check replication lag in Atlas Metrics
// Target: < 1 second sustained lag
```

### Reversing (Removing Search Nodes) — Has Downtime

**Do not remove all Search Nodes unless you intend to revert.** When all Search Nodes are deleted:
- Atlas must rebuild embedded mongot indexes on data nodes
- **Query downtime occurs** while indexes rebuild on data nodes (mongot cannot serve queries during initial sync on the same node as mongod)
- Duration depends on index size

### Migration Checklist

```
[ ] Cluster tier is M10 or higher
[ ] Target region supports Search Nodes (verify in Atlas UI)
[ ] Current search index count < 2,500 (hard limit)
[ ] Sufficient NVMe storage on chosen tier for all indexes
[ ] Alerts configured for replication lag and disk on Search Nodes
[ ] Verify $search / $vectorSearch queries work post-migration
[ ] Monitor replication lag for 24h post-migration
[ ] Confirm embedded mongot RAM freed on data nodes after cutover
```

---

## 10. Limitations

### Architecture Limitations

| Limitation | Detail |
|-----------|--------|
| **Minimum node count** | 2 Search Nodes (cannot run a single Search Node) |
| **Maximum node count** | 32 Search Nodes per cluster/shard/region |
| **One tier per cluster** | All Search Nodes in a deployment must use the same instance size |
| **Global Clusters** | Not supported when Global Writes are enabled |
| **Free/Flex clusters** | Search Nodes require M10+ dedicated clusters |
| **No autoscaling** | Manual scaling only (as of 2025) |

### Search Index Limits

| Limit | Value |
|-------|-------|
| Max search indexes per cluster | 2,500 (hard limit) |
| Max index objects per replica | 2.1 billion (use `numPartitions` or shard beyond this) |
| Max document size for indexing | 16 MB (recommended: 8 MB) |
| Vector dimension limit | 8,192 dimensions |

### Regional Availability

- Not all AWS and Azure regions support Search Nodes; Google Cloud has broader coverage
- Multi-region Search Nodes: available on all three cloud providers as of 2025, but must move cluster to a region that supports Search Nodes if adding to an existing cluster
- For a full list of unsupported regions: see Atlas documentation → Cloud Provider Regions

### Feature Compatibility

- `$search` `concurrent` option requires dedicated Search Nodes (not available in embedded mode)
- Customer-managed encryption (KMIP/AWS KMS) for search indexes: AWS only (as of 2025)
- Atlas Search and Vector Search features that have incompatibilities are documented in [Feature Compatibility](https://www.mongodb.com/docs/atlas/atlas-search/about/feature-compatibility/)
- Paused replication (disk > 90%) stops index updates; if paused beyond the oplog window, a full index rebuild is required

### Disk Replication Stop Behavior

When disk utilization on a Search Node reaches **90%**:
- `mongot` stops replication (pauses indexing)
- Queries continue to serve but from a stale index
- Replication **automatically resumes** when disk falls below 85%
- If paused too long and mongot falls off the oplog: full index rebuild required

---

## References

- [Dedicated Search Nodes GA Announcement](https://www.mongodb.com/company/blog/product-release-announcements/dedicated-search-nodes-vector-search-now-in-general-availability) — Dec 2023
- [Atlas Search Nodes Multi-Region Availability](https://www.mongodb.com/company/blog/product-release-announcements/atlas-search-nodes-now-with-multi-region-availability) — Aug 2024
- [The Art and Science of Sizing Search Nodes](https://www.mongodb.com/company/blog/technical/the-art-and-science-of-sizing-search-nodes) — MongoDB Engineering
- [Review Deployment Options](https://www.mongodb.com/docs/atlas/atlas-vector-search/deployment-options/) — Atlas Docs
- [Monitor MongoDB Search](https://www.mongodb.com/docs/atlas/atlas-search/monitoring/) — Atlas Docs
- [Atlas Search Alerts Reference](https://www.mongodb.com/docs/atlas/reference/alert-resolutions/atlas-search-alerts/) — Atlas Docs
- [Modify a Cluster (Search Nodes UI)](https://www.mongodb.com/docs/atlas/scale-cluster/) — Atlas Docs
- [mongodbatlas_search_deployment Terraform Resource](https://registry.terraform.io/providers/mongodb/mongodbatlas/latest/docs/resources/search_deployment) — Terraform Registry
- [AtlasDeployment Custom Resource (searchNodes)](https://www.mongodb.com/docs/atlas/reference/atlas-operator/atlasdeployment-custom-resource/) — Kubernetes Operator Docs
- [Atlas CLI: atlas clusters search nodes](https://www.mongodb.com/docs/atlas/cli/current/command/atlas-clusters-search-nodes/) — Atlas CLI Docs
- [Monitoring Atlas Search: Key Metrics](https://medium.com/mongodb/monitoring-atlas-search-the-key-metrics-66c90c39d480) — MongoDB Medium
- [Atlas Service Limits](https://www.mongodb.com/docs/atlas/reference/atlas-limits/) — Atlas Docs

## See Also

- [[mongodb-search-ai]] — Atlas Search index design, analyzers, query patterns
- [[mongodb-atlas-vector-search]] — Vector index sizing, ANN configuration, quantization
- [[mongodb-cost-optimization]] — Atlas cost levers, tier right-sizing, commitment discounts
- [[mongodb-monitoring-observability]] — Atlas metrics, alerting, observability patterns
- [[mongodb-atlas-expert]] — Comprehensive Atlas architecture reference
- [[mongodb-atlas-terraform]] — Terraform provider patterns for Atlas, including `mongodbatlas_search_deployment`
- [[mongodb-atlas-kubernetes-operator]] — AtlasDeployment CRD reference and search node configuration
