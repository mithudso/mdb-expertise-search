<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-analytics-node` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-analytics-node
category: mongodb
version: 1.2.0
updated: 2026-05-29
tags: [mongodb, atlas, analytics, olap, workload-isolation, read-preference, bi-connector]
description: "Authoritative reference for MongoDB Atlas Analytics Nodes — dedicated read-only replica set members (priority:0, votes:0) that isolate OLAP workloads from OLTP traffic on M10+ Atlas clusters. TRIGGER when the request involves adding or sizing analytics nodes, routing queries via readPreference=secondary&readPreferenceTags=nodeType:ANALYTICS, connecting BI Connector or Atlas SQL Interface to analytics nodes, configuring Terraform analyticsSpecs or AKO analyticsSpecs, Atlas Data Federation store readPreference, monitoring replication lag on analytics nodes, or migrating from a manual hidden-secondary analytics pattern. SKIP for M0/M2/M5/Flex clusters (analytics nodes require M10+), for questions about Atlas Search nodes (separate feature — use mongodb-atlas-search-nodes), or for general read preference configuration unrelated to workload isolation."
when_to_use:
  - Explaining what analytics nodes are and how they differ from secondaries or hidden secondaries
  - Configuring analytics nodes via Atlas UI, Admin API, Terraform, or AKO
  - Routing queries to analytics nodes with readPreference=secondary + readPreferenceTags=nodeType:ANALYTICS
  - Sizing analytics nodes for BI, reporting, and aggregation pipelines
  - Connecting BI Connector, Atlas SQL Interface, Tableau, or Power BI to analytics nodes
  - Monitoring analytics node metrics, replication lag, and slow operations
  - Estimating cost model for analytics node tiers vs. scaling the entire cluster
  - Migrating from a manual hidden-secondary analytics pattern to official analytics nodes
  - Explaining analytics node limitations (no elections, no writes, no primary promotion)
when_not_to_use:
  - Cluster is M0, M2, M5, or Flex — analytics nodes require M10+ dedicated clusters
  - The question is about Atlas Search nodes — those are a separate feature (use mongodb-atlas-search-nodes)
  - Analytical queries are under 5% of total query volume and don't measurably impact operational latency
  - The cluster already has dedicated readOnlySpecs nodes sized for the same analytical workload
  - The use case requires write access from the reporting tier — analytics nodes are strictly read-only
  - The goal is custom per-node indexes — all indexes replicate from primary; analytics-only indexes are not possible
related_skills:
  - mongodb-atlas-expert
  - mongodb-bi-connector
  - mongodb-replication
  - mongodb-cost-optimization
  - mongodb-atlas-iac
  - mongodb-atlas-terraform
  - mongodb-atlas-kubernetes-operator
  - mongodb-monitoring-observability
---

# MongoDB Atlas Analytics Node

Authoritative reference for MongoDB Atlas Analytics Nodes — the dedicated OLAP tier that separates analytical read workloads from operational OLTP traffic on Atlas dedicated clusters.

## When to Use This Skill

- Explaining what analytics nodes are and how they differ from secondaries / hidden secondaries
- Configuring analytics nodes via Atlas UI, Admin API, Terraform, or AKO
- Routing queries to analytics nodes with `readPreference: secondary` + `readPreferenceTags=nodeType:ANALYTICS`
- Sizing analytics nodes for BI, reporting, and aggregation pipelines
- Connecting BI Connector, Atlas SQL Interface, Tableau, Power BI to analytics nodes
- Monitoring analytics node metrics, replication lag, and slow operations
- Estimating cost model for analytics node tiers vs. scaling the entire cluster
- Migrating from a manual hidden-secondary analytics pattern to official analytics nodes
- Explaining analytics node limitations (no elections, no writes, no primary promotion)

## When NOT to Use Analytics Nodes

Do not recommend adding analytics nodes when:

- The cluster is M0, M2, M5, or Flex — analytics nodes require M10+.
- Analytical queries are < 5% of total query volume and do not measurably impact operational latency — the cost of an extra node is not justified.
- The cluster already has dedicated read-only nodes (`readOnlySpecs`) sized and routed for the same analytical workload — adding analytics nodes would be redundant.
- The use case requires **write access** from the reporting tier — analytics nodes are strictly read-only.
- The customer needs **custom per-node indexes** (e.g., indexes only on the analytics node) — all indexes on Atlas nodes replicate from the primary; you cannot create analytics-only indexes without those same indexes existing on operational nodes, increasing write overhead cluster-wide.

---

## 1. What Analytics Nodes Are

### Overview

Analytics nodes are **dedicated read-only replica set members** provisioned in MongoDB Atlas specifically for analytical workloads (reporting, BI, aggregations, ETL). They occupy the same shard as the primary and operational secondaries, replicate the same data, but are entirely isolated from operational traffic through Atlas's pre-defined replica set tags.

Introduced in **2022**, analytics nodes are available on **M10 and larger dedicated clusters** only (not M0 Flex or shared-tier clusters).

### Replica Set Topology

A standard three-node Atlas replica set has:
- 1 **primary** — accepts reads and writes
- 2 **operational secondaries** — electable, serve operational reads

Adding an analytics node creates a fourth (or more) member:
- **analytics node** — read-only, `priority: 0`, `votes: 0`, tagged `nodeType: ANALYTICS`

Analytics nodes have **lower resource priority for oplog reads** than operational secondaries. This protects the oplog cursor on operational nodes and keeps their replication lag minimal, while analytics nodes may fall slightly behind during heavy write periods.

### How Analytics Nodes Differ from Other Node Types

| Property | Primary | Operational Secondary | Read-Only Node | Analytics Node |
|---|---|---|---|---|
| Can become primary | Yes | Yes | No | No |
| Votes in elections | Yes | Yes | No | No |
| Serves operational reads | Yes | Yes | Yes | No |
| Serves analytics reads | Yes | Secondary reads | Yes | Yes (dedicated) |
| Tag | `nodeType: ELECTABLE` | `nodeType: ELECTABLE` | `nodeType: READ_ONLY` | `nodeType: ANALYTICS` |
| `workloadType` tag | `OPERATIONAL` | `OPERATIONAL` | `OPERATIONAL` | _(not tagged OPERATIONAL)_ |
| Independent tier | No | No | Yes | Yes |

#### vs. Hidden Secondary

A **hidden secondary** (priority: 0, hidden: true) is invisible to drivers and receives no reads from clients without custom routing. It is the traditional "roll your own" analytics isolation pattern and requires manual configuration of replica set member options and careful read-preference management.

An **analytics node** is an Atlas-managed variant: it is **not hidden** (hidden: false), is automatically tagged by Atlas, and integrates with Atlas monitoring, the BI Connector, Atlas SQL Interface, and Atlas Data Federation without extra setup. You cannot manually create a hidden secondary in Atlas — analytics nodes are the supported replacement.

#### vs. Read-Only Node

A **read-only node** (`readOnlySpecs` in the API) is optimized for local reads in a geo-distributed cluster and tagged `nodeType: READ_ONLY`. It still receives the `workloadType: OPERATIONAL` tag, so operational read traffic can reach it. An analytics node never carries the `workloadType: OPERATIONAL` tag, guaranteeing true isolation from operational traffic.

### Use Cases

- **BI dashboards** (Tableau, Power BI, Metabase, Looker) hitting the cluster without affecting application latency
- **Reporting aggregations** — `$group`, `$lookup`, `$facet` pipelines that scan large collections
- **ETL export jobs** — bulk `find()` or aggregation-based exports to data lakes
- **Atlas Data Federation** queries that reference live Atlas collections
- **Atlas SQL Interface** (`mongoSQL`) queries from SQL-speaking tools
- **BI Connector for Atlas** (reaching EOL September 2026 — prefer Atlas SQL Interface for new projects)

---

## 2. Configuration

### 2a. Atlas UI

1. Open your cluster in the Atlas UI.
2. Click **Edit Configuration**.
3. Toggle **"Multi-Cloud, Multi-Region & Workload Isolation (M10+ clusters)"** to **On**.
4. Scroll to **Analytics nodes for workload isolation**.
5. Click **Add a provider/region**.
6. Select:
   - **Cloud provider** (AWS, GCP, or Azure)
   - **Region** — must match or be compatible with your data nodes
   - **Number of nodes** (typically 1–3)
7. Optionally select a separate **Analytics Tier** under the Cluster Tier section.
8. Click **Review Changes → Apply Changes**.

**Removing analytics nodes:** Click the trash icon next to the provider/region in the Analytics nodes section, then apply changes.

### 2b. Atlas Admin API (v2)

Analytics nodes live in `replicationSpecs[].regionConfigs[].analyticsSpecs`.

```http
PATCH /api/atlas/v2/groups/{groupId}/clusters/{clusterName}
Content-Type: application/json

{
  "replicationSpecs": [
    {
      "regionConfigs": [
        {
          "providerName": "AWS",
          "regionName": "US_EAST_1",
          "priority": 7,
          "electableSpecs": {
            "instanceSize": "M30",
            "nodeCount": 3
          },
          "analyticsSpecs": {
            "instanceSize": "M30",
            "nodeCount": 1
          }
        }
      ]
    }
  ]
}
```

Key constraints:
- `replicationSpecs[].regionConfigs[]` must have at least one `electableSpecs` object within the spec.
- `analyticsSpecs.instanceSize` can differ from `electableSpecs.instanceSize` — this is what enables independent analytics tier sizing.
- If your `regionConfigs` has **only** `analyticsSpecs` or `readOnlySpecs` (no electable nodes in that region), set `priority: 0` for that region.
- A `PATCH` that omits `analyticsSpecs` leaves existing analytics nodes unchanged; setting `nodeCount: 0` removes them.

### 2c. Terraform — `mongodbatlas_advanced_cluster`

```hcl
resource "mongodbatlas_advanced_cluster" "analytics_example" {
  project_id   = var.project_id
  name         = "prod-cluster"
  cluster_type = "REPLICASET"

  replication_specs = [
    {
      region_configs = [
        {
          provider_name = "AWS"
          region_name   = "US_EAST_1"
          priority      = 7

          electable_specs = {
            instance_size = "M30"
            node_count    = 3
          }

          analytics_specs = {
            instance_size = "M40"    # Larger tier for heavier OLAP queries
            node_count    = 1
          }
        }
      ]
    }
  ]
}
```

**`analytics_specs` block parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `instance_size` | string | Yes | Instance tier (e.g. `M10`, `M30`, `M40`, `R40`) |
| `node_count` | int | No | Number of analytics nodes in the region (default: 0) |
| `disk_size_gb` | int | No | Root volume storage in GB; must match `electable_specs` if set |
| `disk_iops` | int | No | Provisioned IOPS (AWS M30+, Azure M40+) |
| `ebs_volume_type` | string | No | `STANDARD` or `PROVISIONED` (AWS only) |

**Important Terraform notes:**
- Storage (`disk_size_gb`) and IOPS must remain consistent across all node spec types in a region.
- If compute auto-scaling is enabled, `instance_size` and disk fields in `analytics_specs` are **ignored** — Atlas manages them dynamically. Read actual values from `effective_analytics_specs` in the data source.
- Incompatible tier combinations (General + Low-CPU) disable disk auto-scaling.

### 2d. Atlas Kubernetes Operator (AKO)

In `AtlasDeployment` CRD, analytics nodes map to `spec.deploymentSpec.replicationSpecs[].regionConfigs[].analyticsSpecs`:

```yaml
apiVersion: atlas.mongodb.com/v1
kind: AtlasDeployment
metadata:
  name: my-cluster
spec:
  projectRef:
    name: my-project
  deploymentSpec:
    name: my-cluster
    clusterType: REPLICASET
    replicationSpecs:
      - regionConfigs:
          - providerName: AWS
            regionName: US_EAST_1
            priority: 7
            electableSpecs:
              instanceSize: M30
              nodeCount: 3
            analyticsSpecs:
              instanceSize: M40
              nodeCount: 1
```

The AKO CRD constraints mirror the Admin API: each `regionConfigs` entry must have at least one `electableSpecs`, and `analyticsSpecs` can use a different `instanceSize`.

---

## 3. Read Preference Routing to Analytics Nodes

### The `nodeType: ANALYTICS` Tag

Atlas automatically assigns the following replica set tags to every analytics node:

```
nodeType: ANALYTICS
workloadType: (not set — absent from analytics nodes)
```

Operational nodes (electable and read-only) receive:

```
nodeType: ELECTABLE  (or READ_ONLY)
workloadType: OPERATIONAL
```

This dual-tag system allows drivers to precisely target one class or the other.

### Connection String — Direct to Analytics Nodes

```
mongodb+srv://<user>:<pass>@cluster0.example.mongodb.net/mydb
  ?readPreference=secondary
  &readPreferenceTags=nodeType:ANALYTICS
  &readConcernLevel=local
```

- **`readPreference=secondary`** — reads only from secondaries; never falls back to the primary even if all tagged nodes are unavailable (returns an error instead). This is intentional: it prevents OLAP traffic from hitting the primary.
- **`readPreferenceTags=nodeType:ANALYTICS`** — restricts the secondary pool to analytics nodes only.
- **`readConcernLevel=local`** — required for sharded clusters to avoid returning orphaned documents.

> **Warning:** Do NOT use `readPreference=secondaryPreferred` for analytics routing. `secondaryPreferred` falls back to the primary when no tagged secondaries are available, defeating workload isolation.

### With Fallback (High-Availability Pattern)

```
mongodb+srv://<user>:<pass>@cluster0.example.mongodb.net/mydb
  ?readPreference=secondary
  &readPreferenceTags=nodeType:ANALYTICS
  &readPreferenceTags=
  &readConcernLevel=local
```

- First tag set `nodeType:ANALYTICS` — try analytics nodes first.
- Second tag set `` (empty) — fall back to any available secondary if all analytics nodes are unavailable (e.g., during disk scale-down, initial sync, or NVMe tier changes).
- This avoids read errors at the cost of occasionally hitting an operational secondary.

### Keeping Operational Traffic Off Analytics Nodes

Add `workloadType:OPERATIONAL` tag to operational service connections:

```
mongodb+srv://<user>:<pass>@cluster0.example.mongodb.net/mydb
  ?readPreference=secondary
  &readPreferenceTags=workloadType:OPERATIONAL
  &readConcernLevel=local
```

Analytics nodes do **not** carry the `workloadType: OPERATIONAL` tag, so they are never selected by this tag set.

### Driver Examples

**Node.js (mongodb driver)**

```javascript
const { MongoClient, ReadPreference } = require('mongodb');

// Via connection string (recommended)
const client = new MongoClient(
  'mongodb+srv://user:pass@cluster.mongodb.net/db' +
  '?readPreference=secondary' +
  '&readPreferenceTags=nodeType:ANALYTICS' +
  '&readConcernLevel=local'
);

// Via MongoClientOptions
const clientOpts = new MongoClient(uri, {
  readPreference: new ReadPreference(
    ReadPreference.SECONDARY,
    [{ nodeType: 'ANALYTICS' }, {}]   // fallback to any secondary
  )
});
```

**Python (PyMongo)**

```python
from pymongo import MongoClient
from pymongo.read_preferences import Secondary

# Via connection string
client = MongoClient(
    "mongodb+srv://user:pass@cluster.mongodb.net/db"
    "?readPreference=secondary"
    "&readPreferenceTags=nodeType:ANALYTICS"
    "&readConcernLevel=local"
)

# Via constructor options
client = MongoClient(
    "mongodb+srv://user:pass@cluster.mongodb.net/",
    readPreference=Secondary(tag_sets=[{"nodeType": "ANALYTICS"}, {}])
)
db = client["mydb"]
```

**Java (Sync driver)**

```java
import com.mongodb.ReadPreference;
import com.mongodb.TagSet;
import com.mongodb.Tag;
import com.mongodb.MongoClientSettings;
import com.mongodb.client.MongoClients;

TagSet analyticsTag = new TagSet(new Tag("nodeType", "ANALYTICS"));
ReadPreference analyticsReadPref = ReadPreference.secondary(analyticsTag);

MongoClientSettings settings = MongoClientSettings.builder()
    .applyConnectionString(new ConnectionString("mongodb+srv://..."))
    .readPreference(analyticsReadPref)
    .build();

MongoClient client = MongoClients.create(settings);
```

**Go (mongo-driver)**

```go
import (
    "go.mongodb.org/mongo-driver/mongo/readpref"
    "go.mongodb.org/mongo-driver/tag"
)

rp, err := readpref.New(
    readpref.SecondaryMode,
    readpref.WithTagSets(
        tag.Set{tag.Tag{Name: "nodeType", Value: "ANALYTICS"}},
        tag.Set{},  // empty fallback to any secondary
    ),
)
if err != nil {
    log.Fatal(err)
}

clientOpts := options.Client().
    ApplyURI("mongodb+srv://...").
    SetReadPreference(rp)
```

### Compass and Studio 3T

Both GUI tools support read preference tags in the connection string. When connecting, paste the full connection string including `readPreferenceTags=nodeType:ANALYTICS` in the connection URI field.

---

## 4. BI Connector and Atlas SQL Interface

### Atlas SQL Interface (Recommended for New Projects)

The **Atlas SQL Interface** (uses the MongoSQL dialect) routes queries to analytics nodes natively when analytics nodes are present in the cluster. It is the successor to the BI Connector for Atlas.

> **EOL notice:** The MongoDB Connector for Business Intelligence for Atlas and on-premises reaches end-of-life and will no longer be supported after **September 2026**. Use Atlas SQL Interface for new projects.

Connect Power BI, Tableau, and other ODBC/JDBC tools to Atlas SQL Interface using the dedicated MongoDB Atlas SQL ODBC/JDBC drivers. The Atlas SQL Interface automatically prefers analytics nodes if they are available, directing OLAP SQL queries away from the primary.

### BI Connector (Legacy — EOL September 2026)

The MongoDB Connector for BI (`mongosqld`) supports analytics node routing via the `readPreference` and `readPreferenceTags` configuration options.

**Connection string for BI Connector → analytics nodes:**

```
mongodb+srv://<user>:<pass>@cluster.mongodb.net/db
  ?readPreference=secondary
  &readPreferenceTags=nodeType:ANALYTICS
```

Set the BI Connector read preference to **Analytics** in the Atlas BI Connector settings panel.

**Why route BI Connector to analytics nodes:**
- Prevents Tableau/Power BI → `mongosqld` → MongoDB scan queries from competing with application write traffic on the primary.
- For multi-cloud clusters with BI Connector, routing to analytics nodes also **stabilizes the connection string** — if electable nodes fail over across cloud providers, the analytics node SRV host remains constant.

**Supported BI tools:**
- Tableau Desktop
- Microsoft Power BI Desktop (Windows, via Power Query connector)
- Qlik Sense
- MySQL Workbench
- Excel (via ODBC DSN)

---

## 5. Atlas Data Federation Integration

Atlas Data Federation (ADF) uses a distributed query engine to route queries across MongoDB Atlas clusters, Atlas Online Archive, and cloud object storage (S3, Azure Blob, GCS).

**Routing ADF queries to analytics nodes:** ADF uses an elastic pool of query agents in the region nearest your data. For live Atlas cluster sources, ADF pushes down filtering and aggregation stages to the source when possible — which means the read issued against the Atlas cluster will use whatever read preference is configured in the ADF store. Large scans benefit from analytics nodes because the workload does not affect operational read/write latency.

To route those reads to the analytics node, set `readPreference` in the ADF store configuration. In the Atlas UI federated database store JSON (or via the ADF API):

```json
{
  "stores": [
    {
      "name": "myAtlasStore",
      "provider": "atlas",
      "clusterName": "myCluster",
      "readPreference": {
        "mode": "secondary",
        "tagSets": [
          [{"name": "nodeType", "value": "ANALYTICS"}],
          []
        ]
      }
    }
  ]
}
```

The outer `tagSets` array is tried in order: first try nodes tagged `nodeType: ANALYTICS`; if none are available, the inner empty array `[]` allows fallback to any secondary. This ensures federated `$lookup` operations and collection scans hit the analytics node rather than the primary or operational secondaries.

**Practical use cases with analytics nodes + ADF:**
- Joining live transactional data (from Atlas cluster via analytics node) with historical data from Atlas Online Archive or S3
- Running `$lookup` aggregations across Atlas collections without impacting application performance
- Time-series reporting across the full data lifecycle (hot data in Atlas, cold data in archive/S3)

---

## 6. Sizing Analytics Nodes

### Choosing the Analytics Tier

Since August 2022, analytics nodes can use a **different instance tier** from the operational (electable + read-only) nodes. This is the key differentiator from standard secondaries.

**Scale UP the analytics tier when:**
- Many concurrent BI users run dashboards simultaneously
- Aggregation pipelines require large in-memory sorts (`$sort` stage) that exceed available RAM
- Report queries scan large collections and benefit from faster I/O

**Scale DOWN the analytics tier when:**
- Analytics usage is intermittent or limited to off-peak hours
- Reporting queries are simple and do not compete for memory
- Cost optimization is a priority (analytics workloads are secondary to OLTP)

### Instance Tier Reference (AWS, approximate pricing — verify current rates at mongodb.com/pricing)

| Tier | vCPUs | RAM | Storage | Approx. $/hr/node |
|---|---|---|---|---|
| M10 | 2 | 2 GB | 10 GB | ~$0.08 |
| M20 | 2 | 4 GB | 20 GB | ~$0.20 |
| M30 | 2 | 8 GB | 40 GB | ~$0.54 |
| M40 | 4 | 16 GB | 80 GB | ~$1.04 |
| M50 | 8 | 32 GB | 160 GB | ~$2.00 |
| M60 | 16 | 64 GB | 320 GB | ~$3.95 |
| R40 | 4 | 32 GB | 80 GB | ~$1.20 (RAM-optimized) |
| R50 | 8 | 64 GB | 160 GB | ~$2.40 (RAM-optimized) |

Use RAM-optimized (`R` series) tiers when aggregation pipelines frequently spill to disk due to the 100 MB in-memory sort limit (or when `allowDiskUse: true` is set).

### NVMe Considerations

NVMe-backed analytics nodes (M60 and above on AWS/Azure) provide low-latency sequential reads beneficial for:
- Collection scans over large datasets
- `$group` with large cardinality keys
- `$lookup` with large foreign collections

**NVMe constraints for analytics nodes:**
- If the Base Tier uses NVMe (e.g., M60 NVMe), the Analytics Tier must also be the same NVMe tier level.
- NVMe clusters cannot be paused.
- Azure supports NVMe on M60, M80, M200, M300, M400, M600; GCP does not support NVMe clusters.

### Replication Lag Warning

If you size analytics nodes **significantly below** the base tier:
- Analytics nodes may develop persistent replication lag.
- In extreme cases, analytics nodes can fall off the **oplog window** and require a full initial sync.
- Monitor replication lag metric in Atlas and set alerts (see Section 7).

### Storage

Analytics nodes **replicate all data from the primary** — they do not store a separate dataset. Storage capacity on the analytics node must be at least as large as the primary's data set. Storage settings must match across node types within a region when they are configured (disk_size_gb must be consistent).

---

## 7. Monitoring Analytics Nodes

### Atlas Metrics for Analytics Nodes

In the Atlas UI, analytics node metrics are available under **Metrics** on the cluster view. Select the analytics node host from the host selector dropdown to view node-specific metrics.

**Key metrics to monitor:**

| Metric | Description | Alert threshold |
|---|---|---|
| `opcounters.query` | Read operations per second on analytics node | Baseline + 2× stddev |
| `opcounters.command` | Aggregation commands per second | Baseline + 2× stddev |
| `replicationLag` | Seconds analytics node lags behind primary | > 30s (warning), > 120s (critical) |
| `cpu.user` / `cpu.kernel` | CPU utilization on analytics node | > 80% sustained |
| `memory.resident` | Resident memory usage | > 90% of available RAM |
| `connections.current` | Active connections | > 80% of max connections |
| `queryTargetingRatioAveraged` | Ratio of docs scanned to returned | > 100 (indicates missing index) |

### Query Profiler

Enable the Atlas Query Profiler on the analytics node host to capture slow operations:

1. In Atlas, open the cluster and click the **Profiler** tab (or navigate to **Performance Advisor → Query Profiler**).
2. Select the analytics node host from the host dropdown.
3. Set the slow operation threshold (default: 100 ms).
4. Review the scatterplot of operation execution times.

The Query Profiler captures up to the most recent **100,000 operations** and retains them for **7 days**. It shows:
- `millis` — query execution time
- `docsExamined` — documents scanned
- `keysExamined` — index keys examined
- `nReturned` — documents returned
- Missing index suggestions

### Real-Time Performance Panel (RTPP)

The RTPP is available per-node in Atlas and shows live:
- Active operations on the analytics node
- Network I/O
- Replication lag on the analytics node vs. the primary
- Hottest collections (by scan rate)

Use RTPP during load tests to verify analytics queries are hitting the analytics node (not the primary or operational secondaries).

### Atlas Alerts for Analytics Nodes

Configure these Atlas alerts specifically for analytics nodes:

- **Replication Oplog Window < 1 hour** — analytics node at risk of falling off oplog
- **Replication Lag > 120s** — analytics node lagging significantly; workload isolation may be degraded
- **System CPU > 90%** — analytics node overloaded; consider scaling up the analytics tier
- **Connections % > 80%** — connection pool exhaustion on analytics node
- **Disk Space Used % > 85%** — storage filling up on analytics node

---

## 8. Cost Model

### Billing

Analytics nodes are billed at the **standard Atlas hourly rate** for their configured instance tier, **prorated per node**:

```
Analytics node cost = analytics_tier_hourly_rate × node_count × hours_running
```

There is no premium or discount for analytics nodes vs. equivalent-tier operational nodes. An M40 analytics node costs the same per hour as an M40 electable node.

### When Analytics Nodes Save Money

**Scenario: BI dashboard on M30 cluster without analytics nodes**

Without analytics nodes, you would scale the entire cluster (primary + 2 secondaries) to M50 to handle concurrent BI queries without impacting application latency:

```
Current cost:  3 × M30 nodes = 3 × $390/mo = $1,170/mo
Scaled cost:   3 × M50 nodes = 3 × $1,450/mo = $4,350/mo  (+$3,180/mo)
```

**With 1 analytics node at M50 tier:**

```
Operational nodes: 3 × M30 = $1,170/mo  (unchanged)
Analytics node:    1 × M50 = $1,450/mo
Total:             $2,620/mo  (+$1,450/mo vs. baseline, saves $1,730/mo vs. full scale-up)
```

Adding a single larger analytics node is significantly cheaper than scaling the entire cluster.

**When analytics nodes may NOT save money:**
- If operational read traffic also needs scaling independently, full tier scale-up may be warranted.
- For very small clusters (M10) where a single analytics node is a major percentage of total cost.
- When analytics usage is so light it does not require a dedicated node at all.

### Right-Sizing for Cost

- Start analytics nodes at the same tier as base nodes.
- Monitor `cpu.user` and `memory.resident` under peak analytics load.
- Scale analytics tier up if CPU > 80% sustained; scale down if CPU < 20% sustained.
- For seasonal analytics (month-end reporting), consider programmatic tier changes via the Admin API to scale analytics nodes down between peaks. Note: clusters using NVMe storage cannot be paused — use tier downscaling instead.

---

## 9. Migration from Manual Hidden Secondary

### The Manual Pattern (Pre-Analytics Nodes)

Before analytics nodes, teams would configure a priority-0, hidden secondary in a self-managed replica set:

```javascript
// rs.reconfig() — self-managed replica sets only
rs.reconfig({
  members: [
    { _id: 0, host: "primary:27017", priority: 2 },
    { _id: 1, host: "secondary1:27017", priority: 1 },
    { _id: 2, host: "secondary2:27017", priority: 1 },
    {
      _id: 3,
      host: "analytics:27017",
      priority: 0,
      hidden: true,
      votes: 0,        // non-voting
      tags: { nodeType: "ANALYTICS" }
    }
  ]
})
```

This pattern is **not available in Atlas** — Atlas manages replica set configuration automatically. Analytics nodes are the Atlas-managed equivalent.

### Migration Steps

1. **Add analytics nodes to your Atlas cluster** (UI, API, or Terraform — see Section 2).

2. **Update read preference** in BI / reporting application connection strings:

   If migrating from a **self-managed hidden secondary** with a custom tag (e.g., `nodeType: analytics_custom`), update both the tag name and add `readConcernLevel`:

   ```
   Before (self-managed, custom tag):
   readPreference=secondary&readPreferenceTags=nodeType:analytics_custom

   After (Atlas analytics node, Atlas pre-defined tag):
   readPreference=secondary&readPreferenceTags=nodeType:ANALYTICS&readConcernLevel=local
   ```

   If already using `nodeType:ANALYTICS` as your custom tag, only `readConcernLevel=local` needs to be added (for sharded clusters). Verify the exact tag name used in your existing replica set config before assuming no change is needed.

3. **Retire the manual hidden secondary** (if migrating from a self-managed cluster to Atlas). Atlas does not expose hidden secondaries; once your analytics nodes are provisioned and replication is confirmed healthy, decommission the old node.

4. **Configure BI Connector / Atlas SQL Interface** to use analytics read preference (see Section 4).

5. **Verify routing** with the Real-Time Performance Panel: confirm queries appear under the analytics node host, not the primary or operational secondaries.

6. **Set up monitoring and alerts** (see Section 7) — analytics nodes are separately monitored in Atlas, unlike hidden members which were less visible.

### Key Differences After Migration

| Aspect | Manual hidden secondary | Atlas analytics node |
|---|---|---|
| Visibility | Hidden — not seen by drivers without explicit tag | Not hidden — visible, but only served by `analytics` read preference |
| Atlas monitoring | Partial (appears as generic member) | Full node-level metrics, profiler, RTPP |
| BI Connector integration | Manual `mongosqld` `--readPreference` config | Atlas UI setting + native routing |
| Tag naming | Custom (you define) | Atlas pre-defined (`nodeType: ANALYTICS`) |
| Tier independence | Not applicable (same hardware) | Fully independent tier sizing |
| Maintenance | Manual oplog window management | Atlas-managed, with replication lag alerts |

---

## 10. Limitations

### Elections and Availability

- Analytics nodes **cannot participate in elections** and **cannot become primary**.
- They are effectively `priority: 0`, `votes: 0` members from the replica set's perspective.
- A cluster's **availability (HA)** is not affected by analytics node count — only electable nodes count toward quorum.
- If all analytics nodes become unavailable, no HA impact occurs, but queries using `readPreference=secondary&readPreferenceTags=nodeType:ANALYTICS` will fail or fall back to empty tag set (if fallback is configured).

### Write Operations

- Analytics nodes are **strictly read-only**. All write operations must target the primary.
- Attempting to write directly to an analytics node's host will return a `NotWritablePrimary` error.

### Read Preference Restriction

- Analytics nodes are **only addressable** via `readPreference=secondary` (or `nearest`) **plus** `readPreferenceTags=nodeType:ANALYTICS`.
- They cannot serve requests for `readPreference=primary`, `primaryPreferred`, or untagged `secondary`/`nearest` reads.
- `secondaryPreferred` with analytics tags will route to the primary if analytics nodes are unavailable — avoid this for true isolation (use `secondary` instead).

### Minimum Cluster Tier

- Analytics nodes require **M10 or larger dedicated clusters**.
- Not available on M0 (free), M2, M5 (shared), or Flex clusters.

### Tier Constraints

- If the base tier uses **NVMe-backed storage** (e.g., M60 NVMe), the analytics tier must be the **same tier level** (no mixing NVMe and non-NVMe).
- Mixing **General** and **Low-CPU** tier families between base and analytics nodes disables **disk auto-scaling**.
- Storage (`disk_size_gb`) must remain consistent across node types within a region.

### Node Count Limits

- No per-region maximum specifically for analytics nodes, but the cluster-wide limit is **50 total nodes** across all shards and regions (multi-region constraint).
- For sharded clusters, the number of electable, read-only, and analytics nodes **must be the same across all shards**.

### No Independent Data Storage

Analytics nodes **replicate all data from the primary** — they do not serve as a separate data tier or store different collections. Every byte in the operational cluster is also present on the analytics node.

### Transient Unavailability

Analytics nodes may become temporarily unavailable (0–10 minutes typically) during:
- Initial sync (after adding or resizing an analytics node)
- Disk scale-down operations
- NVMe cluster tier changes

Always implement the **fallback empty tag set** in analytics connections to handle these windows gracefully.

### JDBC Driver Bug (Known Issue)

As of 2023, the MongoDB JDBC driver had a known bug where `readPreferenceTag` for analytics nodes in connection strings was ignored (GitHub issue #362 in `mongodb/mongo-jdbc-driver`). Check the driver changelog for your version before relying on JDBC-based routing to analytics nodes. Use the native MongoDB drivers (Java sync/async) when possible.

---

## References

### Official Documentation
- [Analytics Nodes for Workload Isolation](https://www.mongodb.com/docs/atlas/cluster-config/multi-cloud-distribution/#std-label-deploy-analytics-nodes/)
- [Query using Pre-Defined Replica Set Tags](https://www.mongodb.com/docs/atlas/reference/replica-set-tags/)
- [FAQ: Deployment — Atlas](https://www.mongodb.com/docs/atlas/reference/faq/deployment/)
- [Atlas Admin API v2 — Update One Cluster](https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/operation/operation-updategroupcluster)
- [mongodbatlas_advanced_cluster — Terraform Registry](https://registry.terraform.io/providers/mongodb/mongodbatlas/latest/docs/resources/advanced_cluster)
- [AtlasDeployment Custom Resource — AKO](https://www.mongodb.com/docs/atlas/reference/atlas-operator/atlasdeployment-custom-resource/)
- [Atlas SQL Interface](https://www.mongodb.com/products/platform/atlas-sql-interface)
- [Connect to a Cluster via the BI Connector](https://www.mongodb.com/docs/atlas/bi-connection/)
- [Transition from BI Connector to Atlas SQL](https://www.mongodb.com/docs/sql-interface/transition-bic-to-atlas-sql/)
- [Introducing Independent Analytics Node Tier Scaling](https://www.mongodb.com/blog/post/introducing-ability-independently-scale-atlas-analytics-node-tiers)
- [Monitor Query Performance — Atlas Query Profiler](https://www.mongodb.com/docs/atlas/tutorial/query-profiler/)

### Community and Third-Party
- [Fun With MongoDB Atlas Analytics Nodes — Patrick McLain](https://pmclain.com/mongodb/2022/09/28/fun-with-mongodb-atlas-analytics-nodes.html)
- [Maximizing CRM Efficiency with Atlas Analytics Tier — Tekion](https://tekionc.medium.com/maximizing-crm-efficiency-leveraging-atlas-analytics-tier-node-in-mongodb-1a2aee8830d1)
- [MongoDB Atlas Read Preference Tags — Studio 3T](https://studio3t.com/whats-new/mongodb-atlas-read-preference-tags-and-studio-3t/)
- [PyMongo Read Preferences API](https://pymongo.readthedocs.io/en/stable/api/pymongo/read_preferences.html)

## See Also

- [[mongodb-atlas-expert]] — general Atlas cluster configuration, tiers, and deployment
- [[mongodb-bi-connector]] — BI Connector setup, `mongosqld`, and SQL Interface migration
- [[mongodb-replication]] — replica set internals, elections, oplog, replication lag
- [[mongodb-cost-optimization]] — Atlas cost management, auto-scaling, tier selection strategies
