<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-global-clusters` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-global-clusters
title: "MongoDB Atlas Global Clusters"
category: mongodb
version: "1.1.0"
updated: "2026-05-29"
description: >
  Deep reference for MongoDB Atlas Global Clusters: zone-based sharding for
  geographic data distribution, compound shard key requirements (location field prefix),
  Atlas-managed vs. self-managed sharding, zone-to-region mapping (ISO-3166), local
  reads/writes with zone-aware routing, global writes architecture, cross-zone
  scatter-gather query characteristics, data residency and compliance patterns
  (GDPR, data sovereignty), feature limitations (no Atlas Search, no Online Archive,
  no serverless, M30+ minimum), pricing structure, migration strategy from regional
  clusters, and decision matrix for Global Clusters vs. multi-region replica sets.
  TRIGGER: customer needs geo-partitioned writes, strict data residency per region,
  or single-connection-string global read/write locality; "GDPR data stays in EU",
  "Atlas Global Cluster", "zone sharding", "data residency compliance MongoDB",
  "GEOSHARDED", "location field shard key", "global writes Atlas".
  SKIP: general Atlas sharding mechanics without geo requirements (use mongodb-sharding),
  multi-cloud deployment without zone isolation (use mongodb-atlas-multicloud), GDPR
  legal compliance framework (use mongodb-compliance).
tags:
  - mongodb
  - atlas
  - global-clusters
  - zone-sharding
  - data-residency
  - geo-distribution
  - compliance
  - sharding
keywords:
  - atlas global clusters
  - zone sharding
  - geographic sharding
  - data residency
  - GDPR
  - data sovereignty
  - location field
  - compound shard key
  - ISO-3166
  - global writes
  - atlas-managed sharding
  - zone mapping
  - GEOSHARDED
  - cross-zone query
  - scatter-gather global cluster
  - M30 global cluster
  - global cluster limitations
  - global cluster pricing
  - regional cluster migration
  - zone-aware read preference
  - local reads global cluster
  - global writes zone
  - atlas global cluster terraform
whenToUse:
  - "When a customer needs data to stay in a specific geographic region (GDPR, CCPA, PDPA, data sovereignty)"
  - "When designing an application that writes data to the nearest geographic zone (low-latency global writes)"
  - "When evaluating whether Atlas Global Clusters are the right architecture for a use case"
  - "When evaluating Atlas Global Clusters vs. multi-region replica sets or separate regional clusters"
  - "When configuring compound shard keys with a location prefix for an Atlas Global Cluster"
  - "When mapping ISO-3166 country or subdivision codes to Atlas Global Cluster zones"
  - "When troubleshooting cross-zone scatter-gather queries on a Global Cluster"
  - "When planning migration from a regional sharded or replica-set cluster to a Global Cluster"
  - "When advising on Atlas Global Cluster limitations — Atlas Search, Online Archive, serverless"
  - "When calculating cost for a Global Cluster vs. standard multi-region deployment"
  - "When setting up Atlas-managed sharding vs. self-managed zone configuration"
whenNotToUse:
  - "General Atlas sharding mechanics without geographic data placement requirements — use mongodb-sharding"
  - "Multi-cloud deployment without zone isolation requirements — use mongodb-atlas-multicloud"
  - "GDPR legal compliance framework guidance — use mongodb-compliance"
  - "Atlas Search full-text search configuration — Global Clusters do not support Atlas Search"
  - "Self-managed (non-Atlas) zone sharding — use mongodb-sharding"
related_skills:
  - mongodb-sharding
  - mongodb-atlas-multicloud
  - mongodb-compliance
  - mongodb-atlas-expert
see_also:
  - mongodb-sharding        # underlying zone sharding mechanics
  - mongodb-atlas-multicloud # multi-cloud zone configurations, Terraform examples
  - mongodb-compliance       # GDPR, data sovereignty framework guidance
  - mongodb-atlas-expert     # Atlas general reference
sources:
  - title: "Shard a Global Collection - Atlas Docs"
    url: "https://www.mongodb.com/docs/atlas/shard-global-collection/"
  - title: "Create a Global Cluster - Atlas Docs"
    url: "https://www.mongodb.com/docs/atlas/tutorial/create-global-cluster/"
  - title: "Global Data - Atlas Architecture Center"
    url: "https://www.mongodb.com/docs/atlas/architecture/current/deployment-paradigms/global-data/"
  - title: "Multi-Region Latency Reduction - Atlas Architecture Center"
    url: "https://www.mongodb.com/docs/atlas/architecture/current/deployment-paradigms/latency-strategies/"
  - title: "Global Clusters Admin API v2"
    url: "https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/group/endpoint-global-clusters"
  - title: "Atlas Service Limits"
    url: "https://www.mongodb.com/docs/atlas/reference/atlas-limits/"
  - title: "Cluster Configuration Costs - Atlas Docs"
    url: "https://www.mongodb.com/docs/atlas/billing/cluster-configuration-costs/index.html"
  - title: "Enforce Data Sovereignty With MongoDB Atlas Resource Policies"
    url: "https://www.mongodb.com/company/blog/innovation/enforce-data-sovereignty-with-mongodb-atlas-resource-policies"
---

# MongoDB Atlas Global Clusters

Atlas Global Clusters are the Atlas-managed flavor of zone sharding, purpose-built
for **geographic data distribution**: data residency compliance, low-latency
global reads/writes, and single-connection-string access to a geographically
distributed dataset. They require M30+ tier sharded clusters and carry significant
operational complexity — read the decision matrix in Section 13 before recommending
them.

**Scope of this skill:** Atlas-specific UX/automation (Atlas-Managed Sharding,
zone mapping UI, global-writes toggle), compound shard key structure required for
global collections, zone-to-ISO-3166 mapping, local reads/writes with zone
awareness, cross-zone query characteristics, data residency patterns,
limitations, pricing, and migration. For underlying zone sharding mechanics
(sh.addShardToZone, sh.updateZoneKeyRange, balancer behaviour), see
`mongodb-sharding`. For multi-cloud zone configurations and Terraform examples,
see `mongodb-atlas-multicloud`.

---

## 1. What Is an Atlas Global Cluster?

A Global Cluster is a **sharded cluster with `clusterType: GEOSHARDED`** where
Atlas manages the mapping from ISO-3166 geographic codes to shard zones. Each
zone is backed by one or more shards, each shard is a multi-node replica set,
and writes are routed by the `location` field in the shard key.

Key properties:
- **Single connection string** — clients connect to one `mongodb+srv://` URI;
  the Atlas-managed mongos layer routes writes to the correct zone.
- **Up to 9 zones** per Global Cluster; up to **70 shards** total.
- **Minimum tier:** M30 sharded cluster. Global Writes is an M30+ toggle.
- **Cannot be converted** to a standard sharded cluster after deployment.
- One shard per zone by default; add shards to a zone to handle heavy zone
  write load.

**Sources:** [Create a Global Cluster](https://www.mongodb.com/docs/atlas/tutorial/create-global-cluster/), [Shard a Global Collection](https://www.mongodb.com/docs/atlas/shard-global-collection/)

---

## 2. Atlas-Managed Sharding vs. Self-Managed

| Mode | What Atlas Does | When to Use |
|------|----------------|-------------|
| **Atlas-Managed Sharding** (default) | Automatically creates the `location` field in the shard key, creates zone ranges mapped to ISO-3166 codes, distributes initial chunks | First-time setup, simple geo-routing by country/subdivision |
| **Self-Managed** | You define shard key, zone ranges, and zone mappings manually via API or UI | Custom multi-key routing, non-ISO location codes, complex shard key requirements |

With Atlas-Managed Sharding enabled, Atlas creates at least one chunk per
location code and attempts to distribute chunks evenly across shards within each
zone. You provide the **custom shard key** (second field); Atlas prepends
`location`.

**Source:** [Shard a Global Collection](https://www.mongodb.com/docs/atlas/shard-global-collection/)

---

## 3. Compound Shard Key Structure

Atlas Global Clusters require a **compound shard key** of the form:

```
{ location: 1, <customShardKey>: 1 }
```

- `location` must be the **first (prefix) field**. It holds an ISO-3166-1 alpha-2
  country code (`"US"`, `"DE"`, `"SG"`) or an ISO-3166-2 subdivision code
  (`"US-CA"`, `"DE-BE"`, `"IN-DL"`).
- `<customShardKey>` is a second field you choose (e.g., `userId`, `tenantId`,
  `orderId`) that provides additional distribution within a zone.
- Documents whose `location` field does not conform to a recognized ISO code
  can be routed to **any shard** in the cluster — this is intentional for
  "catch-all" handling but means unrecognized codes lose geo-affinity.

For the zone-range prefix rule: if a zone range is defined on `{ location, userId }`,
any query filter must include `location` as the prefix for the range to
participate in targeted routing.

**Hashed variant:** When Atlas-Managed Sharding uses a compound hashed shard key,
Atlas creates at least 1 chunk per location code, then distributes chunks across
shards in the zone.

**Important:** Do NOT use a hashed shard key for `location` — the hash destroys
the lexicographic range that zone mapping depends on.

**Critical — shard key immutability:** The `location` field value on a document
is **immutable once written** (MongoDB 4.4+ allows shard key updates only via
`findAndModify`/`updateOne` with the full shard key in the filter, and only for
non-`_id` shard keys). If a user moves from `"US"` to `"DE"`, the document does
**not** automatically migrate to the EU zone — you must delete and reinsert, or
use `update` with the full compound shard key to change `location`. Failing to
handle this breaks data residency guarantees silently.

**Source:** [Shard a Global Collection - Atlas Docs](https://www.mongodb.com/docs/atlas/shard-global-collection/), [Add Custom Zone Mapping - Admin API](https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/operation/operation-creategroupclusterglobalwritecustomzonemapping)

---

## 4. Zone-to-Region Mapping

### 4.1 Automatic Mapping

When you create a Global Cluster, Atlas automatically maps each ISO-3166
location code to the **geographically closest zone** based on the zone's
highest-priority region. This auto-mapping covers all countries and many
subdivisions.

The full list of supported codes is published at:
```
https://cloud.mongodb.com/static/atlas/country_iso_codes.txt
```

### 4.2 Custom Zone Mappings

Override the automatic mapping via the Atlas UI or Admin API to pin specific
countries or subdivisions to non-default zones (e.g., routing Swiss data to a
Germany-hosted EU zone):

```bash
# Admin API v2: add custom zone mapping
curl --user "$PUB_KEY:$PRI_KEY" --digest \
  -X POST \
  "https://cloud.mongodb.com/api/atlas/v2/groups/{groupId}/clusters/{clusterName}/globalWrites/customZoneMapping" \
  -H "Content-Type: application/json" \
  -d '{"location": "CH", "zone": "EU-Zone"}'
```

Custom mappings take precedence over automatic mappings. To remove all custom
mappings and revert to automatic:

```bash
curl --user "$PUB_KEY:$PRI_KEY" --digest -X DELETE \
  "https://cloud.mongodb.com/api/atlas/v2/groups/{groupId}/clusters/{clusterName}/globalWrites/customZoneMapping"
```

**Source:** [Add One Custom Zone Mapping - Admin API](https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/operation/operation-creategroupclusterglobalwritecustomzonemapping)

### 4.3 Zone Coverage Examples

| Location Code | Type | Typical Nearest Zone |
|--------------|------|---------------------|
| `US` | Country | Americas zone (e.g., `us-east-1`) |
| `DE` | Country | EU zone (e.g., `eu-central-1`) |
| `SG` | Country | APAC zone (e.g., `ap-southeast-1`) |
| `US-CA` | US Subdivision | Americas West zone |
| `DE-BE` | German Subdivision | EU zone |
| `AU` | Country | APAC/ANZ zone |

---

## 5. Local Reads and Writes (Zone-Aware Routing)

### 5.1 Write Routing

For each document in a write operation, MongoDB inspects the `location` field
of the shard key and routes the write to a shard **in the corresponding zone**.
This delivers write locality — apps in Frankfurt writing EU user data write
directly to the EU zone's shards.

Requirements for zone-aware writes:
1. The document must include the `location` field.
2. `location` must be a valid ISO-3166 code that maps to a zone.
3. The write concern is satisfied at the **zone's replica set level** — the zone's
   primary shard acknowledges the write. `w:"majority"` requires a majority of that
   zone's replica set members to acknowledge; with nodes spread across cloud regions
   within a zone, this can add 10–50 ms of intra-zone replication latency. Use
   `w:1` for latency-sensitive workloads where zone-level durability is acceptable,
   and `w:"majority"` where you need durability guarantees (recommended default).

### 5.2 Read Routing with `nearest` / `localThreshold`

To achieve read locality, configure read preference on the driver:

```javascript
// Driver: prefer reads from nearest member (local zone secondary)
const client = new MongoClient(uri, {
  readPreference: "nearest",
  localThresholdMS: 15  // only members within 15ms of the fastest member
});
```

With `nearest` read preference and low `localThresholdMS`, reads go to the
closest replica set member — typically the same zone as the writing app.

**Important caveat:** `nearest` still reads from the local zone's secondary,
which may lag behind the primary. For strong consistency requirements, use
`primary` read preference but accept cross-zone latency if the primary is
in a different zone.

Atlas pre-defined replica set tags also support zone-aware routing:
- `{ "region": "US_EAST_1" }` — reads from that specific region's members
- Use `Query using Pre-Defined Replica Set Tags` in Atlas docs for full tag list

**Source:** [Multi-Region Latency Reduction - Atlas Architecture Center](https://www.mongodb.com/docs/atlas/architecture/current/deployment-paradigms/latency-strategies/), [Query using Pre-Defined Replica Set Tags](https://www.mongodb.com/docs/atlas/reference/replica-set-tags/)

---

## 6. Global Writes Zones

**Global Writes** is the specific Atlas toggle (`enableGlobalWrites: true`) that
activates zone-based write routing. Without it, a multi-zone sharded cluster
does not automatically route writes by zone.

Key rules:
- Requires M30+ tier.
- Each zone is a **Global Writes Zone** once the toggle is on.
- Atlas-managed sharding is available only with Global Writes enabled.
- You can enable Global Writes at cluster creation; you cannot enable it
  retroactively on an existing non-global sharded cluster.
- There is **no application-level conflict resolution** for global writes —
  MongoDB does not support multi-master across zones. Each zone has its own
  primary; writes to a zone go to that zone's primary. Cross-zone document
  conflicts cannot occur because zone sharding ensures each document lives
  exclusively in one zone.

**Source:** [Create a Global Cluster - Atlas Docs](https://www.mongodb.com/docs/atlas/tutorial/create-global-cluster/)

---

## 7. Cross-Zone Queries and Scatter-Gather Behavior

### 7.1 Targeted vs. Scatter-Gather

| Query Type | Behavior | Performance |
|-----------|-----------|-------------|
| Query includes `location` prefix | Targeted to one zone's shards | Fast — single zone |
| Query omits `location` | Scatter-gather across all zones and shards | Slow — fan-out proportional to zone count × shard count per zone |
| Aggregation pipeline with `$match` on `location` | Targeted if `$match` is first stage | Generally efficient |
| Global aggregation (no zone filter) | All shards participate | High latency; plan for merging at mongos |

### 7.2 Optimization Strategies

1. **Always include `location` in query filters** that don't need cross-zone data.
2. **Shard key prefix rule:** queries must include the entire prefix of the shard
   key to get targeted routing — `{ location: "DE" }` targets the EU zone; a
   filter on `{ userId: "abc" }` alone will scatter.
3. **Analytics vs. operational queries:** Run global aggregations on analytics
   nodes or Atlas Data Federation, not on the write path.
4. **Connection string locality hint:** Use separate connection strings per region
   for applications that never need cross-zone data — reduces mongos fan-out.

### 7.3 `explain()` on Global Clusters

```javascript
db.collection.explain("executionStats").find({ location: "US", userId: "abc123" })
// Look for: "SINGLE_SHARD" (targeted) vs. "SHARD_MERGE" (scatter-gather)
```

---

## 8. Data Residency and Compliance Patterns

### 8.1 GDPR — EU Data Stays in EU Zones

Pattern: create one zone per geographic jurisdiction, route user data by the
user's country code.

```javascript
// Application write: EU user
db.users.insertOne({
  location: "DE",          // ISO-3166: Germany → EU zone
  userId: "u_8823",
  email: "...",
  // ...
})
```

Atlas ensures the document goes to a shard in the EU zone (e.g., nodes in
`eu-central-1` / `westeurope`). The document **never migrates** to a
non-EU zone as long as the shard key value is unchanged and zone ranges are
correctly defined.

**Requirements for strict GDPR compliance with Global Clusters:**
- All EU nodes must be in approved EU cloud regions (see `mongodb-compliance`
  for the full EU region list per cloud provider).
- Atlas DPA (Data Processing Agreement) must be executed.
- Confirm that analytics nodes, if any, are also in EU regions.
- The Atlas control plane remains US-based — document this as a control-plane
  exception in the risk register if regulators ask.

### 8.2 Multi-Jurisdiction Patterns

| Jurisdiction | Zone Strategy |
|-------------|--------------|
| EU (GDPR) | One zone: all EU country codes mapped to EU-region nodes |
| US (CCPA strict) | One zone: `US`, `US-CA` etc. mapped to US-region nodes |
| APAC sovereignty | Per-country zones: separate zones for `SG`, `AU`, `JP`, `IN` |
| Global default | Catch-all zone for codes not requiring residency |

**Tip:** Use custom zone mappings to explicitly pin jurisdiction-sensitive codes
rather than relying solely on geographic proximity auto-mapping.

### 8.3 Atlas Resource Policies for Enforcement

Atlas Resource Policies (org-level) can enforce that clusters may only be
deployed in approved regions. Combine with Global Cluster zone configuration
to create defense-in-depth data residency:
1. Resource Policy restricts which regions are allowed.
2. Global Cluster zone mapping routes data to those regions.
3. Atlas audit logging captures all writes for evidence.

**Source:** [Enforce Data Sovereignty With Atlas Resource Policies](https://www.mongodb.com/company/blog/innovation/enforce-data-sovereignty-with-mongodb-atlas-resource-policies)

---

## 9. Feature Limitations

Global Clusters have more restrictions than standard Atlas sharded clusters:

| Feature | Available on Global Clusters? |
|---------|------------------------------|
| **Atlas Search** (Lucene full-text) | No |
| **Atlas Vector Search** | No |
| **Online Archive** | No |
| **Atlas Data Federation** (federated queries) | Not supported as a data source on global clusters; Data Federation can query S3/Atlas but cannot use a global cluster as a federated collection source |
| **Serverless instances** | No (M30+ dedicated required) |
| **Flex clusters** | No |
| **Converting to standard sharded cluster** | No (irreversible) |
| **Cloud Backups** | Yes (standard cloud backup support) |
| **Backup restore to cluster with shard topology change** | No — restoring a snapshot to a cluster with added/removed shards is not supported |
| **Atlas Charts** | Generally supported via standard connection |
| **Atlas Triggers / App Services** | Supported but triggers fire per-shard — review event ordering assumptions |
| **Maximum zones** | 9 zones |
| **Maximum shards** | 70 shards total |
| **Minimum tier** | M30 |

**Alternative for Atlas Search:** If full-text search is required alongside
geo-distribution, consider separate regional clusters with Atlas Search enabled,
or use a separate Atlas Search index cluster that reads from a global cluster via
Atlas Data Federation (where supported).

**Source:** [Atlas Service Limits](https://www.mongodb.com/docs/atlas/reference/atlas-limits/), [Shard a Global Collection](https://www.mongodb.com/docs/atlas/shard-global-collection/)

---

## 10. Pricing Structure

Global Cluster pricing = **sum of all zone costs** + cross-region data transfer.

### 10.1 Cost Components

| Component | Details |
|-----------|---------|
| Cluster instances | Each zone's nodes billed at standard M-class per-hour rates. Three-zone deployment ≈ 3× single-region cost at same tier. |
| Cross-region data transfer | AWS: ~$0.02/GB; Azure: ~$0.04/GB. Write replication within a zone's replica set also incurs cross-region charges if nodes span regions. |
| Backup storage | Standard backup pricing per zone. |
| mongos routers | Included in the cluster cost. |

### 10.2 Cost Comparison: Global Cluster vs. Multi-Region Replica Set

| Factor | Global Cluster | Multi-Region Replica Set |
|--------|---------------|--------------------------|
| Write routing | Zone-local (low latency) | All writes to single primary |
| Read locality | Yes, via `nearest` | Yes, via read preference |
| Horizontal scale | Yes (sharding across zones) | No (single shard) |
| Data residency enforcement | Strong (zone ranges guarantee placement) | Weaker (secondaries can be in other regions) |
| Cost baseline | 3× for 3 zones | ~1.3–1.6× for additional secondaries |
| Atlas Search | No | Yes |
| Operational complexity | High | Medium |

**Rule of thumb:** For data residency with moderate write volumes and no need for
horizontal scale, a multi-region replica set with carefully placed electable nodes
is simpler and cheaper. Global Clusters are justified when:
- Writes must be zone-local AND
- Dataset/throughput exceeds single shard capacity OR
- Strict enforcement of geo-placement (documents cannot accidentally land in the
  wrong region) is required.

**Source:** [Cluster Configuration Costs - Atlas Docs](https://www.mongodb.com/docs/atlas/billing/cluster-configuration-costs/index.html)

---

## 11. Migration to a Global Cluster

### 11.1 Key Constraint: Irreversibility

Once you create a Global Cluster, **you cannot convert it back to a standard
sharded cluster**. Plan carefully.

### 11.2 Migration Path from Regional Cluster

**From a replica set:**
1. Create a new Global Cluster (M30+) with the desired zones.
2. Enable Atlas Live Migration (pull-based) to seed the global cluster.
3. Modify the application to include the `location` field in all documents
   before the cutover.
4. Cut over the connection string; monitor zone distribution in Atlas UI.

**From a standard sharded cluster:**
1. Cannot migrate in-place to GEOSHARDED topology.
2. Use `mongodump` / `mongorestore` or Atlas Live Migration to a new global cluster.
3. Backfill the `location` field on all existing documents before migrating
   (critical — documents without `location` route to arbitrary shards).
4. Validate zone distribution post-migration: `db.collection.getShardDistribution()`.
   Healthy output shows roughly even chunk counts across shards within each zone and
   no shard holding >2× the average chunks of its zone peers. A shard at 0 chunks
   indicates zone range misconfiguration; a single shard holding all chunks indicates
   the balancer has not yet run or zone ranges are not covering all location values.

### 11.3 Backfilling the `location` Field

```javascript
// Bulk backfill: add location based on existing user.country field
db.users.updateMany(
  { location: { $exists: false } },
  [{ $set: { location: "$country" } }]   // if country is already ISO-3166
)
// For non-ISO source fields, map values first, then update
```

After backfill, re-shard or reshape documents to align chunks with zone ranges.
Expect a rebalancing period (minutes to hours depending on dataset size).

**Source:** [Create a Global Cluster](https://www.mongodb.com/docs/atlas/tutorial/create-global-cluster/), [Surfside Media - Advanced Guide](https://www.surfsidemedia.in/post/mongodb-atlas-global-clusters-an-advanced-guide)

---

## 12. Terraform and Atlas CLI Configuration

For full multi-cloud zone Terraform examples, see `mongodb-atlas-multicloud`.
Below is the minimum Atlas Terraform resource sketch for a single-cloud global cluster:

```hcl
resource "mongodbatlas_cluster" "global" {
  project_id   = var.project_id
  name         = "global-app"
  cluster_type = "GEOSHARDED"

  # Zone 1: Americas
  replication_specs {
    zone_name  = "Americas"
    num_shards = 1
    regions_config {
      region_name     = "US_EAST_1"
      provider_name   = "AWS"
      priority        = 7
      electable_nodes = 3
      read_only_nodes = 0
    }
  }

  # Zone 2: Europe
  replication_specs {
    zone_name  = "Europe"
    num_shards = 1
    regions_config {
      region_name     = "EU_CENTRAL_1"
      provider_name   = "AWS"
      priority        = 7
      electable_nodes = 3
      read_only_nodes = 0
    }
  }

  # Zone 3: APAC
  replication_specs {
    zone_name  = "APAC"
    num_shards = 1
    regions_config {
      region_name     = "AP_SOUTHEAST_1"
      provider_name   = "AWS"
      priority        = 7
      electable_nodes = 3
      read_only_nodes = 0
    }
  }

  provider_name               = "AWS"
  provider_instance_size_name = "M30"
  mongo_db_major_version      = "8.0"  # use current major version; update as needed
}
```

**Sharding the collection after cluster creation:**

```javascript
// Enable sharding on the database
sh.enableSharding("myApp")

// Shard the collection with the required compound shard key
sh.shardCollection("myApp.users", { location: 1, userId: 1 })
```

### 12.1 Atlas CLI Commands

```bash
# Create a Global Cluster (M30+, GEOSHARDED)
atlas clusters create global-app \
  --provider AWS \
  --region US_EAST_1 \
  --tier M30 \
  --type GEOSHARDED \
  --mdbVersion 8.0 \
  --projectId <projectId>

# List managed namespaces for a global cluster
atlas api globalClusters getManagedNamespace \
  --groupId <projectId> --clusterName global-app

# Add a custom zone mapping via Atlas CLI (wraps Admin API)
atlas api globalClusters createCustomZoneMapping \
  --groupId <projectId> --clusterName global-app \
  --body '{"customZoneMappings":[{"location":"CH","zone":"Europe"}]}'

# Remove all custom zone mappings
atlas api globalClusters deleteAllCustomZoneMappings \
  --groupId <projectId> --clusterName global-app
```

**Source:** [Pulumi mongodbatlas.GlobalClusterConfig](https://www.pulumi.com/registry/packages/mongodbatlas/api-docs/globalclusterconfig/), [Atlas Terraform Provider](https://registry.terraform.io/providers/mongodb/mongodbatlas/latest/docs), [atlas api globalClusters - Atlas CLI](https://www.mongodb.com/docs/atlas/cli/current/command/atlas-api-globalclusters/)

---

## 13. Decision Matrix — Global Cluster vs. Alternatives

| Requirement | Global Cluster | Multi-Region Replica Set | Separate Regional Clusters |
|-------------|---------------|--------------------------|---------------------------|
| Data never leaves a specific region | Strong guarantee (zone range) | Moderate (node placement, but one primary) | Strong (fully isolated) |
| Low-latency writes per region | Yes | No (single primary) | Yes |
| Low-latency reads per region | Yes (nearest) | Yes (nearest) | Yes |
| Horizontal write scale | Yes | No | Yes (per cluster) |
| Atlas Search | No | Yes | Yes |
| Single global connection string | Yes | Yes | No (one string per cluster) |
| Cross-region aggregations | Expensive (scatter-gather) | Available | Requires application join |
| Operational complexity | High | Low | Medium |
| Cost (3 regions) | ~3× + egress | ~1.5× + egress | ~3× + egress |
| Compliance: GDPR strict | Yes (with DPA + EU regions) | Possible but manual enforcement | Yes (cleanest model) |
| Atlas Triggers / App Services | Yes (with caveats) | Yes | Yes (per cluster) |

**Atlas recommendation:** In most cases, the Multi-Region Deployment Paradigm
(replica set or separate clusters) fulfills requirements. Global Clusters are
for the most complex cases — when zone-local writes AND horizontal scale AND
a single connection string are all required simultaneously.

**Source:** [Global Data - Atlas Architecture Center](https://www.mongodb.com/docs/atlas/architecture/current/deployment-paradigms/global-data/)

---

## 14. Quick Reference: Gotchas

1. **No Atlas Search** — the most common surprise. Evaluate before committing.
2. **Irreversible topology** — cannot convert back to standard sharded or
   replica-set after enabling GEOSHARDED.
3. **`location` field must be in every document** — documents without it go to
   arbitrary shards, breaking residency guarantees.
4. **ISO code must be recognised** — unrecognised codes route to any shard;
   use the published country_iso_codes.txt to validate your value set.
5. **Control-plane is US-based** — a common audit finding for EU customers.
   Document in risk register.
6. **Rebalancing after schema changes** — adding zones or changing zone ranges
   triggers a balancer run that can take hours on large datasets.
7. **Atlas Triggers fire per-shard** — if you rely on change streams or Triggers
   for event ordering, review the per-shard fan-out behaviour.
8. **Backup topology lock** — cannot restore a snapshot to a cluster with a
   different shard count (added/removed shards).
9. **Maximum 9 zones** — if data residency requires more granularity (e.g., 15+
   country-specific zones), use separate regional clusters instead.
10. **M30 minimum** — no option to right-size to M10/M20 for low-traffic zones;
    each zone pays for M30 nodes.
