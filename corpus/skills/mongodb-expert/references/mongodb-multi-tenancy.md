<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-multi-tenancy` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

# MongoDB Multi-Tenancy Architecture Patterns

## Overview

Multi-tenancy in MongoDB means a single deployment serves multiple customers (tenants) while keeping their data logically or physically isolated. The right architecture depends on the number of tenants, their relative size, compliance requirements, and how much operational complexity you can absorb.

### When to use this skill

- Architecting a SaaS product on MongoDB Atlas
- Choosing among shared-collection, database-per-tenant, or cluster-per-tenant isolation
- Designing shard keys and zone sharding for data residency (GDPR, CCPA)
- Implementing RBAC, connection pooling, or row-level security for multi-tenant workloads
- Automating tenant lifecycle with the Atlas Admin API
- Diagnosing noisy-neighbor or cross-tenant data leakage bugs
- Setting up Atlas Projects for billing chargeback

### When NOT to use this skill

- Single-tenant applications — no isolation patterns needed; use standard MongoDB schema design
- On-premises deployments without Atlas — some patterns (Atlas Projects, Data Federation, Atlas App Services Rules) are Atlas-only
- Fewer than ~5 tenants with no growth plans — operational overhead of isolation patterns exceeds the benefit; use a single database with simple RBAC
- Internal tooling where all users belong to the same trust boundary

### Quick decision flowchart

```
Need contractual isolation, dedicated throughput, or custom cloud region per tenant?
│
├─ Yes → Model D: Separate Atlas Project per tenant
│
└─ No — How many tenants, and will that count grow?
        │
        ├─ <100, stable, varied schemas or per-tenant compliance/backup needs
        │     → Model C: Separate database per tenant (shared cluster)
        │
        ├─ Growing (100s–millions), uniform schemas, cost-sensitive
        │     → Model A: Shared collection with tenantId field
        │
        └─ Mixed tiers (SMB + enterprise)
              → Hybrid: Model A for SMB, Model C for mid-market, Model D for enterprise
```

---

## 1. Tenant Isolation Models — Decision Matrix

MongoDB supports four principal isolation models. Each trades resource efficiency against isolation strength. Production SaaS systems often run a **hybrid**: small tenants on shared infrastructure, large enterprise tenants on dedicated clusters.

### Model A: Shared Database + Shared Collection

All tenants share one collection. Every document carries a `tenantId` field that scopes all reads and writes.

```javascript
// Every document
{
  _id: ObjectId(),
  tenantId: "acme-corp",        // mandatory on every document
  createdAt: ISODate(),
  payload: { ... }
}

// Every query — never omit tenantId
db.events.find({ tenantId: "acme-corp", status: "active" })

// Required compound index — tenantId MUST be the leading field
db.events.createIndex({ tenantId: 1, createdAt: -1 })
db.events.createIndex({ tenantId: 1, status: 1, createdAt: -1 })
```

**When to use:** Indefinitely growing SaaS with hundreds to millions of similar-sized tenants.

**Advantages:**
- Highest resource efficiency; lowest cost per tenant
- Horizontally scalable via sharding on `tenantId`
- Single schema migration applies to all tenants simultaneously
- Simplest backup and maintenance (one collection)

**Disadvantages:**
- Data isolation is purely logical — application bugs can leak cross-tenant data
- RBAC operates at collection level, not document level; one compromised DB user sees all tenants
- Noisy-neighbor risk: a large tenant running expensive aggregations spikes latency for all
- Per-tenant customization (different schemas, retention) is painful

**MongoDB's official recommendation for scale:** This is the preferred model when the tenant count is expected to grow without an upper bound.

---

### Model B: Shared Database + Separate Collections per Tenant

Each tenant gets its own collection within a single database.

```javascript
// Collection naming convention
const tenantCollection = (tenantId) => `events_${tenantId}`;
db[tenantCollection("acme-corp")].find({ status: "active" })
```

**When to use:** Rarely — MongoDB's own documentation recommends avoiding this model. It complicates application code, inflates the number of data files on disk, and provides neither the scalability of shared collections nor the isolation of separate databases.

**Hard limit:** Each collection and each index is a separate file on disk. MongoDB recommends keeping total data files (collections + indexes) below **1,000 per node** to avoid resource exhaustion. With 50 tenants each having 10 collections and 5 indexes each, you already consume 750 files.

---

### Model C: Separate Database per Tenant

Each tenant has their own MongoDB database within a shared cluster.

```javascript
// Application selects database by tenant
const db = mongoClient.db(`tenant_${tenantId}`);
db.events.find({ status: "active" })  // no tenantId filter needed

// Create dedicated user per tenant database
db.createUser({
  user: "acme-corp-app",
  pwd: "<password>",
  roles: [{ role: "readWrite", db: "tenant_acme-corp" }]
})
```

**When to use:** Small to medium SaaS with tens to low hundreds of tenants that have meaningfully different schemas, compliance requirements, or need per-tenant backup/restore.

**Advantages:**
- Strong isolation via MongoDB RBAC: each tenant's DB user cannot access other databases
- Per-tenant index configuration (different fields, unique constraints)
- Easy migration: `mongodump --db tenant_acme-corp` captures one tenant
- Per-tenant schema validation

**Disadvantages:**
- Atlas default limit: **100 database users per project** (can be raised via support)
- 1,000 data files per node limit becomes a real constraint at hundreds of tenants
- Cross-tenant analytics require Atlas Data Federation or aggregate cluster-level queries
- Schema migrations must run N times (once per tenant database)

---

### Model D: Separate Atlas Project or Cluster per Tenant

Each large enterprise tenant has their own Atlas Project, or at minimum their own dedicated cluster.

```
Organization: MyCompany
├── Project: AcmeCorp-Prod       ← dedicated cluster(s), API keys, network peering
├── Project: GlobalBank-Prod
├── Project: SmallTenants-Prod   ← shared cluster for long tail
└── Project: Staging
```

**When to use:** Enterprise SaaS with large tenants that demand contractual isolation, dedicated throughput, or custom cloud regions.

**Advantages:**
- Hardest isolation boundary: separate VPC/network peering per tenant
- Complete billing isolation via project-level invoicing
- Per-tenant Atlas API key for tenant self-service provisioning
- No shared oplog; complete operational independence
- Supports tenant-specific cloud provider, region, and cluster tier

**Disadvantages:**
- Highest cost; cannot share idle capacity across tenants
- Operational complexity scales with tenant count
- Atlas Admin API automation is essential (manual provisioning does not scale)
- Cross-tenant analytics require Atlas Data Federation across projects

---

### Hybrid Strategy (Recommended for Production SaaS)

```
Tier 1: Enterprise tenants ($50k+/yr)  → Model D (dedicated cluster per Atlas Project)
Tier 2: Mid-market tenants ($5k–50k/yr) → Model C (database per tenant, shared cluster)
Tier 3: SMB / free tier tenants        → Model A (shared collection, tenantId field)
```

A **meta-store** document maps each `tenantId` to its connection string, database name, and tier:

```javascript
// meta-store collection in control plane database
{
  tenantId: "acme-corp",
  tier: "enterprise",
  connectionString: "mongodb+srv://...",
  databaseName: "tenant_acme-corp",
  region: "us-east-1",
  createdAt: ISODate("2024-01-15"),
  status: "active"
}
```

---

## 2. Shard Key Design and Zone Sharding

### Shard Key for Multi-Tenancy

For shared-collection models, always use a compound shard key with `tenantId` as the **prefix**:

```javascript
// Preferred: tenantId + high-cardinality sub-field
sh.shardCollection("app.events", { tenantId: 1, _id: 1 })

// For time-series workloads
sh.shardCollection("app.metrics", { tenantId: 1, timestamp: 1 })

// For user-centric workloads
sh.shardCollection("app.userActivity", { tenantId: 1, userId: 1 })
```

**Why `tenantId` as prefix:**
- All documents for a tenant land on the same shard (data locality), eliminating scatter-gather for tenant-scoped queries
- Shard-targeted reads never fan out to all shards when `tenantId` is in the query filter
- The balancer keeps tenant chunks together, simplifying tenant migration

### Hashed vs Ranged Shard Key

| Strategy | Use when | Risk |
|---|---|---|
| `{ tenantId: "hashed" }` | Many small tenants of similar size | Scatter-gather for range queries; cannot use zones |
| `{ tenantId: 1, _id: 1 }` ranged | Mixed tenant sizes; need zones for data residency | Jumbo chunks from large tenants |
| `{ tenantId: 1, timestamp: 1 }` ranged | Time-series; tenant-scoped range queries | Large-tenant hot shard risk |

### Jumbo Chunk Risk

A single large tenant writing millions of documents with the same `tenantId` prefix can create **jumbo chunks** — chunks that exceed `chunkSize` and cannot be split because all documents share the same leading shard key value.

**Mitigations:**
```javascript
// Option 1: Add a high-cardinality suffix field
sh.shardCollection("app.events", { tenantId: 1, _id: 1 })
// ObjectId _id provides sufficient cardinality within a tenant's range

// Option 2: Use a hashed suffix
sh.shardCollection("app.events", { tenantId: 1, bucketId: 1 })
// bucketId = hash(userId) % 16 — artificially increases key cardinality per tenant

// Option 3: Zone-based isolation for large tenants (see below)
```

### Zone Sharding for Data Residency (GDPR / Data Sovereignty)

Zone sharding lets you pin tenant data to specific shards or geographic regions. This is the primary MongoDB mechanism for GDPR, HIPAA, or data sovereignty compliance.

```javascript
// MongoDB 6.0+ API (preferred)
// Step 1: Assign zone labels to shards
sh.addShardToZone("shard-eu-west-1", "EU")
sh.addShardToZone("shard-us-east-1", "US")
sh.addShardToZone("shard-ap-southeast-1", "APAC")

// Step 2: Map tenantId ranges to zones
// EU tenants: tenantId values starting with "eu-"
sh.updateZoneKeyRange(
  "app.events",
  { tenantId: "eu-" },              // min — inclusive
  { tenantId: "eu-￿" },        // max — exclusive (U+FFFF is lexicographic ceiling)
  "EU"
)

// US tenants
sh.updateZoneKeyRange(
  "app.events",
  { tenantId: "us-" },
  { tenantId: "us-￿" },
  "US"
)

// Step 3 (Atlas): Use Zone configuration in Atlas UI or API
// The balancer migrates chunks automatically to enforce placement

// Legacy aliases (MongoDB <6.0, still accepted but deprecated):
// sh.addShardTag() / sh.addTagRange() — same semantics, older names
```

**Atlas Global Clusters** provide a managed zone sharding experience for multi-region deployments:
- Define geographic zones (Americas, Europe, Asia-Pacific)
- Atlas handles chunk placement; application uses the global connection string
- Compound shard key: `{ location: 1, _id: 1 }` where location encodes region

---

## 3. RBAC and Connection Security

### Database-Level RBAC for Model C (Database per Tenant)

```javascript
// Create a tenant-scoped user with minimal privileges
db.getSiblingDB("tenant_acme-corp").createUser({
  user: "acme-app",
  pwd: "<strong-random-password>",
  roles: [
    { role: "readWrite", db: "tenant_acme-corp" }
    // Never grant readAnyDatabase or clusterAdmin
  ]
})

// Custom role — read-only analyst role for a specific tenant
db.getSiblingDB("admin").createRole({
  role: "acme-analyst",
  privileges: [
    {
      resource: { db: "tenant_acme-corp", collection: "" },  // all collections in tenant db
      actions: ["find", "listCollections", "listIndexes"]
    }
  ],
  roles: []
})
```

### Collection-Level RBAC (Finer Granularity)

```javascript
// Restrict a user to a single collection within a shared database
db.getSiblingDB("admin").createRole({
  role: "acme-events-reader",
  privileges: [
    {
      resource: { db: "app", collection: "events" },
      actions: ["find"]
    }
  ],
  roles: []
})
// Note: This alone does NOT prevent reading other tenants' documents in "events".
// Collection-level RBAC must be combined with application-layer tenant filter injection.
```

### Per-Tenant Encryption: CSFLE vs Queryable Encryption

For sensitive fields that must be cryptographically isolated per tenant, use **CSFLE** (Client-Side Field Level Encryption) with per-tenant Data Encryption Keys (DEKs). Note: despite a common naming conflation, CSFLE and Queryable Encryption (QE) are distinct products with different APIs and trade-offs.

**CSFLE** uses `autoEncryption` + `schemaMap` in the driver:

```javascript
// Each tenant has their own DEK stored in a Key Management Service
// At application startup per tenant:
const clientEncryption = new ClientEncryption(keyVaultClient, {
  keyVaultNamespace: "encryption.__keyVault",
  kmsProviders: { aws: { accessKeyId, secretAccessKey } }
});

// Create (or retrieve) DEK for this tenant
const tenantDEK = await clientEncryption.createDataKey("aws", {
  masterKey: {
    key: `arn:aws:kms:us-east-1:123456789:key/tenant-${tenantId}-cmk`,
    region: "us-east-1"
  },
  keyAltNames: [`tenant-${tenantId}-dek`]
});

// CSFLE MongoClient for this tenant — uses schemaMap (not encryptedFieldsMap)
const encryptedClient = new MongoClient(uri, {
  autoEncryption: {
    keyVaultNamespace: "encryption.__keyVault",
    kmsProviders: { aws: { accessKeyId, secretAccessKey } },
    schemaMap: {                          // CSFLE uses schemaMap
      "app.users": {
        bsonType: "object",
        properties: {
          ssn: {
            encrypt: {
              bsonType: "string",
              algorithm: "AEAD_AES_256_CBC_HMAC_SHA_512-Deterministic",
              keyId: [tenantDEK]
            }
          }
        }
      }
    }
  }
});
```

**CSFLE vs Queryable Encryption for multi-tenancy:**

| Aspect | CSFLE | Queryable Encryption |
|---|---|---|
| Per-tenant DEK | Yes — one DEK per tenant | Difficult — single key per field by default |
| Query support | Equality (deterministic) only | Equality and range queries on encrypted fields |
| Driver API | `autoEncryption.schemaMap` | `autoEncryption.encryptedFieldsMap` |
| Connection model | One `MongoClient` per tenant (required) | Shared client possible |
| Use when | Tenants need cryptographic key separation | Need range/equality queries on encrypted fields |

**Key constraint:** CSFLE requires one `MongoClient` instance per tenant (because each client is configured with that tenant's DEK). See Section 4 for managing per-tenant connection pools without exhausting Atlas connection limits.

### Atlas Resource Policies (Cedar-Based RBAC)

Atlas introduced Cedar-based Resource Policies (2025) for org-wide RBAC enforcement:
- Enforce constraints across all projects and clusters unless explicitly exempted
- Example: require MFA for all Atlas UI access org-wide, or block public cluster access
- Tenant self-service is scoped to their project's API key with project-scoped roles

---

## 4. Connection Pooling Strategies

### Shared Pool (Recommended for Model A)

A single `MongoClient` instance shared across the application serves all tenants. All queries include the `tenantId` filter at the application layer.

```javascript
// server.js — create once at startup
const client = new MongoClient(process.env.MONGODB_URI, {
  maxPoolSize: 100,
  minPoolSize: 10,
  maxIdleTimeMS: 30_000,
  connectTimeoutMS: 5_000,
  serverSelectionTimeoutMS: 5_000,
  socketTimeoutMS: 45_000
});
await client.connect();

// Request handler — always inject tenantId
async function getEvents(tenantId, filter) {
  return client.db("app").collection("events").find({
    tenantId,          // MANDATORY — never skip
    ...filter
  }).toArray();
}
```

### Per-Tenant Connection Pool (Required for CSFLE per-Tenant DEK)

When per-tenant encrypted clients are needed, cache them by `tenantId`. Use an LRU cache (e.g., `lru-cache` npm package) so inactive tenant clients are evicted automatically rather than accumulating unboundedly:

```javascript
import { LRUCache } from 'lru-cache';  // npm install lru-cache

// Evict least-recently-used tenant clients; cap at 100 concurrent tenant pools
const tenantClients = new LRUCache({
  max: 100,
  dispose: async (client) => {
    await client.close();  // close evicted client's connections cleanly
  }
});

async function getTenantClient(tenantId) {
  if (tenantClients.has(tenantId)) {
    return tenantClients.get(tenantId);
  }
  const dek = await lookupTenantDEK(tenantId);
  const client = new MongoClient(uri, {
    autoEncryption: buildEncryptionConfig(dek),
    maxPoolSize: 5,       // Keep small — N active tenants × 5 connections
    minPoolSize: 0,       // 0 so evicted clients release connections promptly
    maxIdleTimeMS: 60_000
  });
  await client.connect();
  tenantClients.set(tenantId, client);
  return client;
}
```

**Pool exhaustion rule of thumb:** `max LRU size × maxPoolSize` must stay below the Atlas cluster's connection limit. Atlas M10 ≈ 1,500 connections → max 100 tenants × 5 connections = 500 (safe). Raise `max` and lower `maxPoolSize` proportionally as tenant count grows.

### Serverless / Lambda Connection Caching

The challenge in serverless is that each function invocation may open a new connection. The pattern is to cache the client in module scope outside the handler:

```javascript
// lambda.js
let cachedClient = null;

async function connectToMongoDB() {
  if (cachedClient && cachedClient.topology?.isConnected()) {
    return cachedClient;
  }
  cachedClient = new MongoClient(process.env.MONGODB_URI, {
    maxPoolSize: 5,        // Low per instance — many concurrent Lambda instances
    serverSelectionTimeoutMS: 5_000,
    socketTimeoutMS: 10_000,
    connectTimeoutMS: 5_000
  });
  await cachedClient.connect();
  return cachedClient;
}

export const handler = async (event) => {
  const client = await connectToMongoDB();
  const { tenantId } = JSON.parse(event.body);
  const results = await client.db("app").collection("events")
    .find({ tenantId })
    .toArray();
  return { statusCode: 200, body: JSON.stringify(results) };
};
```

**Key settings for Lambda/Cloud Run:**
- `maxPoolSize: 5–10` per instance (not the total; scale by concurrent instances)
- `minPoolSize: 0` so cold instances don't hold connections open indefinitely
- `maxIdleTimeMS: 15_000–30_000` to release connections after idle bursts
- Do **not** call `client.close()` inside the handler — reuse across invocations

**For extreme concurrency:** Use a dedicated connection pooler service (e.g., a small Express microservice) rather than having each Lambda instance maintain its own TCP connections to Atlas.

### Atlas Serverless Instances

For very spiky workloads with many small tenants, **Atlas Serverless** handles connection management automatically:
- No connection pool to configure
- Scales to zero between requests
- Best for infrequent, unpredictable per-tenant workloads
- Not suitable for sustained high-throughput tenants (use dedicated clusters)

---

## 5. Schema Design for Multi-Tenancy

### Document Structure

```javascript
// Canonical multi-tenant document — tenantId in every document, every collection
{
  _id: ObjectId(),
  tenantId: "acme-corp",          // required — always the FIRST indexed field
  createdAt: ISODate("2024-01-15T10:30:00Z"),
  updatedAt: ISODate("2024-01-15T10:30:00Z"),
  // ... business fields
}
```

### Mandatory Compound Indexes

Every collection in a shared model needs `tenantId` as the **leading field** in all compound indexes. A query that filters only on a non-tenant field without `tenantId` will scan the entire collection.

```javascript
// Time-range queries per tenant
db.events.createIndex({ tenantId: 1, createdAt: -1 })

// Status + time per tenant
db.events.createIndex({ tenantId: 1, status: 1, createdAt: -1 })

// Lookup by business key per tenant (unique within a tenant)
db.orders.createIndex(
  { tenantId: 1, orderNumber: 1 },
  { unique: true }
)

// Subdocument field search per tenant
db.contacts.createIndex({ tenantId: 1, "address.zipCode": 1 })

// Text search within a tenant (Atlas Search is preferred for production)
db.articles.createIndex({ tenantId: 1, title: "text", body: "text" })
```

### Partial Indexes for Sparse Tenant Data

When a field only exists on a subset of documents, use a **partial index** to avoid indexing nulls across tenants:

```javascript
// Index only documents where isPremium is true, within a specific tenant
db.accounts.createIndex(
  { tenantId: 1, isPremium: 1, mrr: -1 },
  { partialFilterExpression: { isPremium: { $eq: true } } }
)

// Index only active sessions — avoids bloating the index with expired records
db.sessions.createIndex(
  { tenantId: 1, userId: 1 },
  { partialFilterExpression: { expiresAt: { $gt: new Date() } } }
)
```

### Schema Validation per Tenant

In Model C (database per tenant), apply `$jsonSchema` validation at the collection level for each tenant database:

```javascript
// Per-tenant collection validator (applied when creating the collection)
db.createCollection("orders", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenantId", "createdAt", "status", "lineItems"],
      properties: {
        tenantId: { bsonType: "string" },
        status: { enum: ["pending", "processing", "shipped", "delivered", "cancelled"] },
        lineItems: { bsonType: "array", minItems: 1 }
      }
    }
  },
  validationAction: "error",
  validationLevel: "strict"
})
```

For Model A (shared collection), enforce schema at the application layer with a validation library (Zod, Joi, Mongoose) rather than per-tenant collection validators.

### Avoiding Cross-Tenant Data Leakage in Aggregations

Every `$match` stage at the start of an aggregation pipeline must include `tenantId`:

```javascript
// CORRECT — tenantId as the first $match stage
db.events.aggregate([
  { $match: { tenantId: "acme-corp", status: "active" } },  // Stage 1: filter first
  { $group: { _id: "$category", count: { $sum: 1 } } },
  { $sort: { count: -1 } }
])

// DANGEROUS — tenantId omitted from $match; returns data for all tenants
db.events.aggregate([
  { $group: { _id: "$category", count: { $sum: 1 } } },  // Bug: cross-tenant aggregate
  { $sort: { count: -1 } }
])

// Pattern: Repository wrapper that prepends tenantId to all pipelines
class TenantRepository {
  constructor(db, collection, tenantId) {
    this.col = db.collection(collection);
    this.tenantId = tenantId;
  }

  aggregate(pipeline) {
    return this.col.aggregate([
      { $match: { tenantId: this.tenantId } },  // Always prepend
      ...pipeline
    ]);
  }

  find(filter) {
    return this.col.find({ tenantId: this.tenantId, ...filter });
  }

  insertOne(doc) {
    if (doc.tenantId && doc.tenantId !== this.tenantId) {
      throw new Error("tenantId mismatch — cross-tenant write blocked");
    }
    return this.col.insertOne({ ...doc, tenantId: this.tenantId });
  }
}
```

---

## 6. Atlas Projects as Hard Isolation

### Organization and Project Hierarchy

```
MongoDB Atlas Organization
├── Billing (consolidated at org level)
├── Users & Teams (org-wide membership)
├── Project: Production-SharedTenants
│   ├── Cluster: shared-m30
│   ├── Database Users: app-readonly, app-readwrite
│   ├── Network Access: VPC peering / private endpoint
│   └── Atlas Search indexes
├── Project: Tenant-AcmeCorp-Prod
│   ├── Cluster: acme-m50 (dedicated)
│   ├── Database Users: acme-app, acme-analytics
│   ├── Network Access: VPC peering to Acme's AWS VPC
│   └── Backup: continuous, 7-day PIT
└── Project: Tenant-GlobalBank-Prod
    ├── Cluster: bank-m200 (enterprise)
    ├── Network Access: PrivateLink to GlobalBank's Azure VNET
    └── Backup: daily snapshots, 30-day retention
```

### Project-Level Isolation Features

| Feature | Scope | Benefit |
|---|---|---|
| Database users | Per project | Credential scope cannot cross projects |
| Network access lists | Per project | IP allowlist / VPC peering unique per tenant |
| Private endpoints (PrivateLink) | Per project | Tenant traffic never traverses public internet |
| Atlas API keys | Per project | Tenant self-service without org-level access |
| Alerts & monitoring | Per project | Tenant-specific SLA monitoring |
| Backup policies | Per project | Per-tenant retention and recovery windows |
| Encryption at rest | Per project | Tenant-managed KMS key (BYOK via AWS KMS / Azure Key Vault / GCP KMS) |

### Provisioning an Atlas Project per Enterprise Tenant

```bash
# Atlas Admin API v2 — create project for a new enterprise tenant
curl -X POST "https://cloud.mongodb.com/api/atlas/v2/groups" \
  -H "Accept: application/vnd.atlas.2023-01-01+json" \
  -H "Content-Type: application/json" \
  --digest -u "${ORG_PUBLIC_KEY}:${ORG_PRIVATE_KEY}" \
  -d '{
    "name": "Tenant-AcmeCorp-Prod",
    "orgId": "'"${ORG_ID}"'"
  }'

# Create a project-scoped API key for tenant self-service
curl -X POST "https://cloud.mongodb.com/api/atlas/v2/groups/${PROJECT_ID}/apiKeys" \
  -H "Accept: application/vnd.atlas.2023-01-01+json" \
  -H "Content-Type: application/json" \
  --digest -u "${ORG_PUBLIC_KEY}:${ORG_PRIVATE_KEY}" \
  -d '{
    "desc": "AcmeCorp self-service key",
    "roles": ["GROUP_CLUSTER_MANAGER"]
  }'
```

Alternatively, use the Terraform Atlas Provider for declarative project provisioning:

```hcl
resource "mongodbatlas_project" "tenant_acme" {
  name   = "Tenant-AcmeCorp-Prod"
  org_id = var.atlas_org_id
}

resource "mongodbatlas_cluster" "acme_cluster" {
  project_id   = mongodbatlas_project.tenant_acme.id
  name         = "acme-prod"
  cluster_type = "REPLICASET"
  provider_name         = "AWS"
  provider_region_name  = "US_EAST_1"
  provider_instance_size_name = "M50"
  mongo_db_major_version = "8.0"
  cloud_backup           = true
}
```

---

## 7. Billing and Cost Chargeback

### Atlas Billing Hierarchy

Billing aggregates at the **Organization** level. Use **Projects** as the cost allocation unit for per-tenant chargeback:

```
Organization Invoice
├── Project: Production-SharedTenants    $1,240/mo  → split by tenant usage %
├── Project: Tenant-AcmeCorp-Prod        $2,100/mo  → direct chargeback to AcmeCorp
└── Project: Tenant-GlobalBank-Prod      $3,800/mo  → direct chargeback to GlobalBank
```

### Resource Tags for Cost Attribution

Apply Atlas resource tags to clusters at creation time:

```bash
# Atlas Admin API — tag a cluster with tenant metadata
curl -X PATCH "https://cloud.mongodb.com/api/atlas/v2/groups/${PROJECT_ID}/clusters/acme-prod" \
  --digest -u "${PUBLIC_KEY}:${PRIVATE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "tags": [
      { "key": "tenant", "value": "acme-corp" },
      { "key": "tier", "value": "enterprise" },
      { "key": "cost-center", "value": "CC-1042" }
    ]
  }'
```

Tags appear in billing line items via the API:

```bash
# Retrieve pending invoice line items with tags
curl "https://cloud.mongodb.com/api/atlas/v2/orgs/${ORG_ID}/invoices/pending" \
  --digest -u "${PUBLIC_KEY}:${PRIVATE_KEY}" \
  -H "Accept: application/vnd.atlas.2023-01-01+json"
# Response: results[].lineItems[].tags — contains tenant, tier, cost-center
```

### Tenant Usage Metering in Shared Collections

For shared-collection models where multiple tenants share one cluster, track per-tenant usage at the application level:

```javascript
// Append usage metrics on every request (or via change stream)
db.tenantUsage.insertOne({
  tenantId: "acme-corp",
  timestamp: new Date(),
  operationType: "query",
  collectionName: "events",
  documentsScanned: stats.nscanned,
  executionTimeMs: stats.executionStats.executionTimeMillis
})

// Monthly aggregation for chargeback
db.tenantUsage.aggregate([
  {
    $match: {
      timestamp: {
        $gte: ISODate("2024-01-01"),
        $lt: ISODate("2024-02-01")
      }
    }
  },
  {
    $group: {
      _id: "$tenantId",
      totalQueries: { $sum: 1 },
      totalDocsScanned: { $sum: "$documentsScanned" },
      avgLatencyMs: { $avg: "$executionTimeMs" }
    }
  }
])
```

### Atlas Data Federation for Cross-Tenant Analytics

Use Atlas Data Federation to run analytical queries across all tenant databases without impacting production clusters. ADF exposes a **named virtual database** configured in the Atlas UI (Federated Database Instance settings) — not `$external`, which is reserved for X.509/LDAP auth.

```javascript
// Connect to the Federated Database Instance connection string (separate from cluster SRV)
// Configure in Atlas UI: Data Federation → Create Federated Database → add data sources
const fedClient = new MongoClient(process.env.ATLAS_FEDERATED_URI);

// The virtual database name matches what you configured in the Federated Database Instance
const fedDb = fedClient.db("myFederatedDB");   // name set in Atlas UI

// Standard aggregation against federated collections — no $search here;
// use $match, $group, $lookup across tenant databases mapped as collections
const results = await fedDb.collection("all_tenant_events").aggregate([
  { $match: { timestamp: { $gte: startOfMonth } } },
  { $group: { _id: "$tenantId", eventCount: { $sum: 1 } } },
  { $sort: { eventCount: -1 } }
]).toArray();
```

**Setup:** In Atlas, create a Federated Database Instance and map each tenant database (or S3 archive) as a collection in the virtual database. Use the dedicated federated connection string — the cluster SRV will not route to ADF.

---

## 8. Tenant Lifecycle Operations

### Tenant Onboarding (Model A — Shared Collection)

```javascript
// 1. Register tenant in meta-store
await metaDb.collection("tenants").insertOne({
  tenantId: nanoid(),                   // generate unique ID
  name: tenantName,
  tier: "standard",
  status: "provisioning",
  createdAt: new Date(),
  settings: defaultSettings
});

// 2. Create required indexes (idempotent)
await ensureTenantIndexes(db, tenantId);

// 3. Seed initial data
await db.collection("configs").insertOne({
  tenantId,
  ...defaultConfig
});

// 4. Update status
await metaDb.collection("tenants").updateOne(
  { tenantId },
  { $set: { status: "active", activatedAt: new Date() } }
);
```

### Tenant Onboarding (Model D — Atlas Project per Tenant)

Automate via Atlas Admin API or Terraform. The snippet below is **pseudocode** — wrap the Atlas Admin API REST calls in your own client class or use the official `mongodb-atlas-sdk` (Node) / `mongodbatlas` (Python) packages:

```javascript
// Pseudocode — AtlasAdminApiClient wraps Atlas Admin API v2 REST calls.
// Real options: atlas-api-client npm package, direct fetch(), or Terraform provider.
const atlasClient = new AtlasAdminApiClient({ publicKey, privateKey });

// 1. Create project
const project = await atlasClient.createProject({
  name: `Tenant-${tenantId}-Prod`,
  orgId: process.env.ATLAS_ORG_ID
});

// 2. Create cluster
const cluster = await atlasClient.createCluster(project.id, {
  name: "prod",
  clusterType: "REPLICASET",
  providerSettings: { instanceSizeName: "M30", providerName: "AWS", regionName: "US_EAST_1" },
  mongoDBMajorVersion: "8.0",
  backupEnabled: true
});

// 3. Wait for cluster to be ready (poll every 30s)
await waitForClusterState(atlasClient, project.id, cluster.name, "IDLE");

// 4. Create database user
await atlasClient.createDatabaseUser(project.id, {
  username: `app-${tenantId}`,
  password: generateStrongPassword(),
  roles: [{ roleName: "readWrite", databaseName: `tenant_${tenantId}` }]
});

// 5. Configure network access
await atlasClient.addIpToAccessList(project.id, {
  cidrBlock: tenantVpcCidr,
  comment: `${tenantId} app VPC`
});

// 6. Store connection string in secret manager
await secretsManager.putSecret(
  `mongodb/${tenantId}/connection-string`,
  cluster.connectionStrings.standardSrv
);
```

### Tenant Offboarding

```javascript
// Model A — Shared collection offboarding
async function offboardTenant(tenantId) {
  // 1. Soft-delete: mark inactive immediately
  await metaDb.collection("tenants").updateOne(
    { tenantId },
    { $set: { status: "offboarding", offboardingStartedAt: new Date() } }
  );

  // 2. Export tenant data for compliance archive (before deletion)
  const tenantData = await exportTenantData(tenantId);
  await archiveToS3(tenantId, tenantData);

  // 3. Hard delete documents in batches to avoid long-running lock contention
  // NOTE: deleteMany() has no limit option — batch via repeated deletes on _id
  let deleted;
  do {
    // Fetch a batch of _ids first, then delete only those
    const batch = await db.collection("events")
      .find({ tenantId }, { projection: { _id: 1 } })
      .limit(1000)
      .toArray();
    if (batch.length === 0) break;
    const ids = batch.map(d => d._id);
    const result = await db.collection("events").deleteMany({ _id: { $in: ids } });
    deleted = result.deletedCount;
  } while (deleted > 0);

  // 4. Remove from meta-store
  await metaDb.collection("tenants").deleteOne({ tenantId });
}
```

### Per-Tenant Backup Policies

For Model D (Atlas Project per tenant), configure the cluster backup schedule via the `/backup/schedule` endpoint, and optionally lock minimum retention floors via the Backup Compliance Policy endpoint.

```bash
# Set per-tenant backup schedule (standard schedule endpoint)
curl -X PATCH \
  "https://cloud.mongodb.com/api/atlas/v2/groups/${TENANT_PROJECT_ID}/clusters/${CLUSTER_NAME}/backup/schedule" \
  --digest -u "${PUBLIC_KEY}:${PRIVATE_KEY}" \
  -H "Accept: application/vnd.atlas.2023-01-01+json" \
  -H "Content-Type: application/json" \
  -d '{
    "scheduledPolicyItems": [
      {
        "frequencyType": "hourly",
        "frequencyInterval": 6,
        "retentionUnit": "days",
        "retentionValue": 7
      },
      {
        "frequencyType": "daily",
        "frequencyInterval": 1,
        "retentionUnit": "days",
        "retentionValue": 30
      }
    ],
    "referenceHourOfDay": 2,
    "referenceMinuteOfHour": 0
  }'

# Optionally: enforce minimum retention floors via Backup Compliance Policy
# (org-level governance; prevents schedules from being weakened)
# PATCH /groups/${PROJECT_ID}/backupCompliancePolicy
```

### Tenant Migration Between Clusters

Use `moveCollection` (MongoDB 8.0+) to relocate a tenant's collection to a different shard **within the same cluster** — useful when promoting a tenant from a shared shard to a dedicated shard on the same cluster. For cross-cluster migration (shared cluster → dedicated cluster), use mongosync or Atlas Live Migrate instead.

```javascript
// MongoDB 8.0+: Move a collection to a different shard WITHIN the same cluster
db.adminCommand({
  moveCollection: "app.events",
  toShard: "dedicated-tenant-shard"   // shard must be in the same sharded cluster
})

// Cross-cluster migration (e.g., shared cluster → dedicated cluster):
// Use mongosync (self-managed) or Atlas Live Migrate (managed)
```

---

## 9. Row-Level Security Patterns

MongoDB does not have native row-level security (RLS) like PostgreSQL. RLS must be approximated at the application layer. There are three patterns:

### Pattern 1: Query Filter Injection (Recommended)

Every database call passes through a middleware that appends the `tenantId` to the filter. This is enforced structurally rather than relying on developer discipline.

```javascript
// Express middleware — inject tenantId from JWT into all db operations
function tenantMiddleware(req, res, next) {
  const { tenantId, userId } = verifyJwt(req.headers.authorization);
  req.tenantId = tenantId;
  req.userId = userId;
  // Attach tenant-scoped db accessor to the request
  req.db = new TenantScopedDB(mongoClient.db("app"), tenantId);
  next();
}

class TenantScopedDB {
  constructor(db, tenantId) {
    this._db = db;
    this._tenantId = tenantId;
  }

  collection(name) {
    return new TenantScopedCollection(this._db.collection(name), this._tenantId);
  }
}

class TenantScopedCollection {
  constructor(col, tenantId) {
    this._col = col;
    this._tenantId = tenantId;
  }

  find(filter = {}) {
    return this._col.find({ ...filter, tenantId: this._tenantId });
  }

  findOne(filter = {}) {
    return this._col.findOne({ ...filter, tenantId: this._tenantId });
  }

  insertOne(doc) {
    if (doc.tenantId && doc.tenantId !== this._tenantId) {
      throw new Error("Cross-tenant write blocked");
    }
    return this._col.insertOne({ ...doc, tenantId: this._tenantId });
  }

  updateOne(filter, update, options) {
    return this._col.updateOne(
      { ...filter, tenantId: this._tenantId },
      update,
      options
    );
  }

  deleteOne(filter) {
    return this._col.deleteOne({ ...filter, tenantId: this._tenantId });
  }

  aggregate(pipeline) {
    return this._col.aggregate([
      { $match: { tenantId: this._tenantId } },
      ...pipeline
    ]);
  }
}

// Usage in route handler
app.get("/events", tenantMiddleware, async (req, res) => {
  // req.db.collection() automatically scopes all queries to the tenant
  const events = await req.db.collection("events")
    .find({ status: "active" })
    .toArray();
  res.json(events);
});
```

### Pattern 2: MongoDB Views as Logical RLS

Create a read-only view per tenant that pre-filters documents:

```javascript
// Create a tenant-scoped view (read-only; supports find and aggregation)
db.createView(
  "events_acme",          // view name
  "events",               // source collection
  [
    { $match: { tenantId: "acme-corp" } },
    { $project: { tenantId: 0 } }    // optionally hide tenantId from tenant users
  ]
)

// Grant the tenant's DB user access to the view, not the base collection
db.getSiblingDB("admin").createRole({
  role: "acme-events-view-reader",
  privileges: [
    {
      resource: { db: "app", collection: "events_acme" },
      actions: ["find"]
    }
  ],
  roles: []
})
```

**Limitation:** Views are read-only. Write operations must still target the base collection via the application layer.

### Pattern 3: Data API with JWT-Injected Filters (Atlas App Services)

Atlas App Services (formerly Realm) supports JWT-based rule injection. Rules automatically append `tenantId` from the JWT before executing any query — enforced by the App Services engine before the query reaches MongoDB, not by application code.

**Prerequisite:** Each App Services user must have a `tenantId` field in their **custom user data** document (a MongoDB collection you designate in App Services → App Users → Custom User Data settings). App Services reads this on each request and exposes it as `%%user.custom_data`. Populate it during user provisioning.

```json
{
  "roles": [
    {
      "name": "tenant-user",
      "apply_when": { "%%user.custom_data.tenantId": { "%%exists": true } },
      "document_filters": {
        "read":  { "tenantId": "%%user.custom_data.tenantId" },
        "write": { "tenantId": "%%user.custom_data.tenantId" }
      },
      "read": true,
      "write": true
    }
  ]
}
```

**How it works:** `%%user.custom_data.tenantId` is resolved from the user's custom data document at query time. The filter `{ "tenantId": "%%user.custom_data.tenantId" }` is merged into every read and write operation automatically. A user whose custom data has no `tenantId` field matches no documents (the `apply_when` condition gates role activation).

This is the strongest isolation guarantee of the three patterns — no application code path can accidentally omit the filter.

### Audit Logging per Tenant

Enable MongoDB audit logs and tag with tenant context:

```javascript
// Application-layer audit trail
async function auditedFind(tenantId, userId, collection, filter) {
  const result = await db.collection(collection).find({
    ...filter,
    tenantId
  }).toArray();

  await db.collection("_audit").insertOne({
    tenantId,
    userId,
    action: "find",
    collection,
    filter: JSON.stringify(filter),
    resultCount: result.length,
    timestamp: new Date()
  });

  return result;
}
```

---

## 10. Anti-Patterns

### AP-1: No tenantId in Compound Indexes

```javascript
// WRONG — index does not start with tenantId
db.events.createIndex({ status: 1, createdAt: -1 })
// Result: queries filtered by tenantId do a collection scan within the status index

// CORRECT
db.events.createIndex({ tenantId: 1, status: 1, createdAt: -1 })
```

**Impact:** Full collection scans for tenant queries. In a collection with 10M documents across 500 tenants, each query scans ~10M documents instead of ~20K.

### AP-2: Omitting tenantId from Query Filters

```javascript
// DANGEROUS — missing tenantId returns all tenants' documents
const events = await db.collection("events").find({ status: "active" }).toArray();

// SAFE — always include tenantId
const events = await db.collection("events")
  .find({ tenantId, status: "active" })
  .toArray();
```

### AP-3: Using readPreference "secondary" for Analytics Without Tenant Scoping

Running analytics queries on secondary nodes without proper tenant scoping causes two problems: they still do full-collection scans, and they compete with primary-write replication.

```javascript
// WRONG — unscoped analytics on secondary degrades all tenants
db.collection("events").find({}).readPreference("secondaryPreferred")

// CORRECT — scoped to tenant, isolated on secondary
db.collection("events")
  .find({ tenantId, eventType: "purchase" })
  .readPreference("secondaryPreferred")  // only after verifying tenantId filter hits index
```

Use **Atlas Search Nodes** (dedicated search tier) to isolate heavy analytics from OLTP traffic.

### AP-4: Unbounded Documents per Tenant

```javascript
// WRONG — appending to an unbounded array inside a single document
db.tenantStats.updateOne(
  { tenantId },
  { $push: { events: newEvent } }  // document grows without bound → 16MB limit
)

// CORRECT — use the Bucket Pattern or separate collection
db.events.insertOne({ tenantId, ...newEvent })  // one document per event
// Or: Bucket Pattern for time-series
db.eventBuckets.updateOne(
  { tenantId, bucket: hourlyBucket, count: { $lt: 200 } },
  {
    $push: { events: newEvent },
    $inc: { count: 1 },
    $setOnInsert: { tenantId, bucket: hourlyBucket, startTime: bucketStart }
  },
  { upsert: true }
)
```

### AP-5: Missing TTL Indexes per Tenant

Short-lived data (sessions, tokens, audit logs) without TTL indexes accumulates forever:

```javascript
// CORRECT — TTL index scoped to prevent unbounded growth
db.sessions.createIndex(
  { expiresAt: 1 },
  { expireAfterSeconds: 0 }  // MongoDB deletes docs when expiresAt < now
)

// Verify TTL is working per tenant
db.sessions.aggregate([
  { $match: { tenantId, expiresAt: { $lt: new Date() } } },
  { $count: "expiredSessions" }
])
```

### AP-6: Shared Atlas Project for All Enterprise Tenants

Running enterprise customers in the same Atlas Project eliminates billing isolation, shares the network access list, and means one compromised project API key exposes all tenants.

```
WRONG:
Project: AllCustomers
├── Cluster: tenant-acme (separate cluster name only)
└── Cluster: tenant-globalbank

CORRECT:
Project: Tenant-AcmeCorp-Prod
└── Cluster: prod

Project: Tenant-GlobalBank-Prod
└── Cluster: prod
```

### AP-7: Collection-per-Tenant in a Shared Database (Model B)

Avoid creating `events_tenantA`, `events_tenantB`, `events_tenantC`. This pattern:
- Makes cross-tenant queries require `$unionWith` across N collections
- Hits the 1,000 data files per node limit quickly
- Complicates migrations and schema evolution
- Provides no meaningful security improvement over shared collections

### AP-8: No Connection Pool Size Discipline in Serverless

```javascript
// WRONG — default maxPoolSize (100) in Lambda
const client = new MongoClient(uri);  // inherits maxPoolSize: 100

// CORRECT — small pool per Lambda instance
const client = new MongoClient(uri, {
  maxPoolSize: 5,
  minPoolSize: 0,
  maxIdleTimeMS: 15_000
});
```

With 100 concurrent Lambda invocations and `maxPoolSize: 100`, this creates 10,000 connections — far exceeding Atlas M10 limits (~1,500 connections).

### AP-9: Missing Compound Shard Key (tenantId Only)

```javascript
// WRONG — shard key with only tenantId creates a jumbo chunk per large tenant
sh.shardCollection("app.events", { tenantId: 1 })

// CORRECT — compound key breaks large-tenant chunks apart
sh.shardCollection("app.events", { tenantId: 1, _id: 1 })
```

### AP-10: Querying Without the Shard Key Prefix

If the shard key is `{ tenantId: 1, _id: 1 }`, every query that includes `tenantId` is shard-targeted. A query without `tenantId` broadcasts to all shards (scatter-gather):

```javascript
// WRONG — scatter-gather across all shards (includes all tenants)
db.events.find({ status: "active", createdAt: { $gt: yesterday } })

// CORRECT — shard-targeted (all tenants' data co-located per shard)
db.events.find({ tenantId: "acme-corp", status: "active", createdAt: { $gt: yesterday } })
```

---

## References

### MongoDB Official Documentation
- [Build a Multi-Tenant Architecture — Atlas Docs](https://www.mongodb.com/docs/atlas/build-multi-tenant-arch/)
- [Build a Multi-Tenant Architecture for MongoDB Vector Search](https://www.mongodb.com/docs/atlas/atlas-vector-search/multi-tenant-architecture/)
- [Role-Based Access Control — MongoDB Manual](https://www.mongodb.com/docs/manual/core/authorization/)
- [Atlas Administration API v2](https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/)
- [Atlas Architecture: Automation](https://www.mongodb.com/docs/atlas/architecture/current/automation/)
- [Atlas Billing Data Features](https://www.mongodb.com/docs/atlas/architecture/current/billing-data/)
- [Choosing In-Use Encryption: QE vs CSFLE](https://www.mongodb.com/docs/manual/core/queryable-encryption/about-qe-csfle/)

### Articles and Deep-Dives
- [Multi-Tenancy and MongoDB — Mike LaSpina, MongoDB Blog](https://medium.com/mongodb/multi-tenancy-and-mongodb-5658512ed398) — official patterns, hybrid strategy, meta-store design
- [Implementing Multi-Tenancy RBAC in MongoDB — Permit.io](https://www.permit.io/blog/implement-multi-tenancy-rbac-in-mongodb) — application vs database RBAC
- [Enhance MongoDB Security for Atlas With Scalable Tenant Isolation — Jit.io](https://www.jit.io/blog/enhance-mongodb-security-for-atlas-with-scalable-tenant-isolation) — Data API + JWT filter injection
- [How to Design Multi-Tenant Schemas in MongoDB — OneUptime](https://oneuptime.com/blog/post/2026-01-25-mongodb-multi-tenant-schema-design/view) — index strategies, repository pattern
- [Fine-Tuning MongoDB for Multi-Tenant SaaS — Reintech](https://reintech.io/blog/fine-tuning-mongodb-multi-tenant-saas) — performance tuning, connection pool settings
- [Zone Sharding in MongoDB — OneUptime](https://oneuptime.com/blog/post/2026-03-31-mongodb-zone-sharding/view) — zone configuration walkthrough
- [Data Isolation and Sharding Architectures for Multi-Tenant Systems — Justin Hamade](https://medium.com/@justhamade/data-isolation-and-sharding-architectures-for-multi-tenant-systems-20584ae2bc31)
- [CSFLE and Multi-Tenancy, Encryption Key per Tenant — MongoDB Community Forums](https://www.mongodb.com/community/forums/t/csfle-and-multi-tenancy-encryption-key-per-tenant/180064)

### See Also

- [[mongodb-schema-design]] — Embedding vs referencing, bucket pattern, schema versioning
- [[mongodb-sharding]] — Shard key selection, chunk management, balancer, zone configuration
- [[mongodb-atlas-expert]] — Atlas cluster tiers, Atlas Projects, Atlas CLI, Atlas Admin API
- [[mongodb-security-architecture]] — Encryption at rest, network security, LDAP/OIDC integration, audit logging
- [[mongodb-indexes-deep]] — Compound indexes, partial indexes, sparse indexes, index selection
- [[mongodb-atlas-iac]] — Terraform Atlas provider, Atlas Kubernetes Operator, infrastructure automation
