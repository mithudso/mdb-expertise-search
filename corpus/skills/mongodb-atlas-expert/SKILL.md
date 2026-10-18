---
description: 'MongoDB Atlas platform hub. TRIGGER: architecture, API/CLI/Terraform/AKO,
  tiers, security, networking, alerts, Search, Vector Search, hybrid fusion, BM25
  diagnostics, streaming and Online Archive. SKIP: queries -> mongodb-expert; live
  diagnosis -> atlas-diagnostics-expert; backups and migration -> mongodb-operations-expert.'
name: mongodb-atlas-expert
category: mongodb
tags:
- mongodb
- atlas
- atlas-expert
- terraform
- kubernetes-operator
- atlas-cli
- admin-api
- security
- networking
- atlas-search
- vector-search
- stream-processing
whenToUse:
- planning Atlas architecture or choosing an Atlas deployment tier
- 'which Atlas surface should I use: UI, Admin API, CLI, Terraform, or AKO'
- 'Atlas tier question: Flex vs dedicated vs M10+'
- 'Atlas security design: IP access list, private endpoints, VPC peering'
- Atlas alerts, metrics, limits, or Performance Advisor setup
- 'deep Atlas sub-area: Atlas Search, Vector Search, Stream Processing, Charts, Triggers,
  IAM/RBAC, federated auth'
- 'recent Atlas platform/availability release: Flex GA, Stream Processing GA, Search
  Nodes, Automated Embedding'
- Atlas Admin API rate limiting or service account authentication
- Terraform Provider 2.0 migration or AKO upgrade
- 'which Atlas feature fits a workload: search, vector, or streaming'
whenNotToUse:
- Data-plane query, index, schema, aggregation, or storage-engine work — use mongodb-expert
- 'Diagnosing a live cluster: metrics, slow queries, performance, monitoring, capacity
  — use atlas-diagnostics-expert'
- Backups, DR, Ops Manager, migration, mongosync, security architecture, encryption/CSFLE/Queryable
  Encryption setup, compliance, Kafka/Spark connectors, or cost — use mongodb-operations-expert
- What changed between MongoDB engine versions (e.g. 7.0→8.0 behavior/feature diffs)
  — use mongodb-operations-expert
- Tenant/PII isolation and entitlement boundaries for Atlas Vector Search — use atlas-vector-search-pii-isolation
- Looking up a MongoDB KB article, or cloning/installing/running this repo — use misc-catch-all
related_skills:
- mongodb-expert
- atlas-diagnostics-expert
- mongodb-operations-expert
- atlas-vector-search-pii-isolation
- misc-catch-all
version: 1.5.4
updated: '2026-10-02'
---

# MongoDB Atlas Expert

Generated from `docs/mongodb-atlas-expert-context.md` in an internal repository. Use it as a **MongoDB Atlas platform reference** when planning Atlas architecture, automating Atlas administration, connecting applications, designing Atlas-backed schemas and queries, or reviewing Atlas operational posture. Start from the context below, then defer to the linked **official MongoDB Atlas docs**, **MongoDB Manual**, and **driver docs** as the source of truth for exact endpoint, command, operator, and version details. For a deep sub-area, match the task to the Sub-skill routing table below and read the listed `references/…md` file before answering.

## Frontier refresh scope

For service accounts, workforce/workload federation, Cedar resource policies, hybrid fusion and BM25 diagnostics, load the October 2026 frontier references below. They verify those scoped details against current sources. In Atlas IAM guidance, use the current roles reference: Organization Owner inherits Project Owner and Data Explorer privileges across projects. Do not repeat the older blanket claim that an Organization Owner cannot read cluster documents. Atlas roles still do not replace database-user credentials for direct driver connections. Other older broad references remain background; verify their role, deployment-tier, version and authorization assertions before reuse. The new references do not refresh every claim in the older references.

## Sub-skill routing table

This skill consolidates 32 Atlas sub-skills as on-demand references — match the task to the table and **Read the listed `references/…md` file before answering deep questions**. Do not rely on this table alone for depth.

| Sub-topic | When to load | Reference file |
| --- | --- | --- |
| `mongodb-atlas-app-services` | Atlas App Services platform layers beyond Triggers and Functions | `references/mongodb-atlas-app-services.md` |
| `mongodb-atlas-azure` | Azure-specific Private Link, NSG, Entra ID, Key Vault BYOK, MACC | `references/mongodb-atlas-azure.md` |
| `mongodb-atlas-charts` | Atlas Charts — chart types, data sources, aggregation pipelines in Charts | `references/mongodb-atlas-charts.md` |
| `mongodb-atlas-cli` | Deep Atlas CLI command reference and scripting | `references/mongodb-atlas-cli.md` |
| `mongodb-atlas-data-federation` | Atlas Data Federation (formerly Atlas Data Lake) and Online Archive federated queries | `references/mongodb-atlas-data-federation.md` |
| `mongodb-atlas-device-sdk` | Atlas Device SDK (Realm successor): object model, Flexible Sync, Atlas Edge | `references/mongodb-atlas-device-sdk.md` |
| `mongodb-atlas-federated-auth` | Org-level SSO via SAML 2.0 federated authentication | `references/mongodb-atlas-federated-auth.md` |
| `mongodb-atlas-flex-serverless` | Flex/Serverless tier deep-dive, decision matrix, pricing, migration | `references/mongodb-atlas-flex-serverless.md` |
| `mongodb-atlas-tiers-upgrades` | Dedicated tier specs (M30: 2 vCPU/8GB/3000 conns, WT cache 25%), connection limits per tier, rolling-upgrade election mechanics, Atlas Gen2 ARM hardware generations, post-upgrade cache-warming expectations. For auto-upgrade cadence/FCV ceiling/write-blocking see `mongodb-atlas-managed-upgrades` below | `references/mongodb-atlas-tiers-upgrades.md` |
| `mongodb-atlas-gcp` | GCP-specific PSC, Workload Identity, networking | `references/mongodb-atlas-gcp.md` |
| `mongodb-atlas-global-clusters` | Global Clusters: zone-based sharding for geo-distributed data | `references/mongodb-atlas-global-clusters.md` |
| `mongodb-atlas-iac` | Atlas IaC — Terraform provider v2.x + AKO v2.14 CRDs together | `references/mongodb-atlas-iac.md` |
| `mongodb-atlas-identity-policy-frontier-20261001` | Verified service-account, workforce/workload federation and Cedar guardrail boundaries; use for current scoped details | `references/mongodb-atlas-identity-policy-frontier-20261001.md` |
| `mongodb-atlas-iam-rbac` | Atlas identity, access control, three-tier identity model, 30+ built-in roles, org-level Resource Policies/governance guardrails | `references/mongodb-atlas-iam-rbac.md` |
| `mongodb-atlas-kubernetes-operator` | AKO-only Kubernetes work, custom resources, reconciliation | `references/mongodb-atlas-kubernetes-operator.md` |
| `mongodb-atlas-managed-upgrades` | Atlas-managed major-version upgrade mechanics — auto-upgrade cadence, maintenance windows, EOL forced upgrades, 7.0→8.0 gotchas (write-blocking, defaultMaxTimeMS, Search index rebuild, App Services timing) | `references/mongodb-atlas-managed-upgrades.md` |
| `mongodb-atlas-multicloud` | Multi-cloud replica set topology, cross-cloud DR, egress costs | `references/mongodb-atlas-multicloud.md` |
| `mongodb-atlas-online-archive` | Automated data tiering from M10+ clusters to object storage | `references/mongodb-atlas-online-archive.md` |
| `mongodb-atlas-hybrid-retrieval-frontier-20261001` | Verified fusion eligibility, score normalization and BM25 diagnostic explanations; load for current scoped detail | `references/mongodb-atlas-hybrid-retrieval-frontier-20261001.md` |
| `mongodb-atlas-platform-changelog` | Dated Atlas releases, availability and version cutoffs; reverify current dates | `references/mongodb-atlas-platform-changelog.md` |
| `mongodb-atlas-search` | Deep Atlas Search index design, analyzers, `$search` query syntax | `references/mongodb-atlas-search.md` |
| `mongodb-atlas-search-nodes` | Dedicated Search Nodes tier decoupling search from database compute | `references/mongodb-atlas-search-nodes.md` |
| `mongodb-atlas-service-accounts` | Service Accounts — OAuth 2.0 Client Credentials for Admin API | `references/mongodb-atlas-service-accounts.md` |
| `mongodb-atlas-stream-processing` | Atlas Stream Processing engine, pipelines, sources/sinks | `references/mongodb-atlas-stream-processing.md` |
| `mongodb-atlas-terraform` | Terraform-only Atlas IaC, provider resources, 2.0 migration | `references/mongodb-atlas-terraform.md` |
| `mongodb-atlas-triggers-functions` | Atlas Triggers (database/scheduled/auth) and Functions | `references/mongodb-atlas-triggers-functions.md` |
| `mongodb-atlas-vector-search` | Vector Search ANN/ENN tuning, `$vectorSearch`, automated embedding | `references/mongodb-atlas-vector-search.md` |
| `mongodb-search-ai` | Search + AI retrieval: full-text, vector, hybrid, RAG patterns | `references/mongodb-search-ai.md` |
| `mongodb-bi-connector` | BI Connector and Atlas SQL Interface (Tableau, Power BI) | `references/mongodb-bi-connector.md` |
| `mongodb-aws-networking` | AWS networking — VPC peering, PrivateLink, access lists, DNS/SRV | `references/mongodb-aws-networking.md` |
| `mongodb-realm-mobile-sync` | MongoDB Realm and Atlas Device Sync (historical context) | `references/mongodb-realm-mobile-sync.md` |
| `mongodb-analytics-node` | Analytics Nodes — read-only members isolating OLAP workloads | `references/mongodb-analytics-node.md` |

## Source scope

### Atlas platform and architecture

- **Atlas docs home:** deployment types, regions, access control, connection,
  alerts, optimization entry points
  <https://www.mongodb.com/docs/atlas/>
- **Atlas Architecture Center:** Atlas well-architected guidance across
  operational efficiency, security, reliability, performance, and cost
  optimization
  <https://www.mongodb.com/docs/atlas/architecture/current/>

### Atlas administration and automation

- **Atlas Admin API v2 reference:** canonical Atlas administration endpoint
  inventory and auth model
  <https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/>
- **Configure Atlas API access:** service-account/API-key setup, IP access list
  behavior, and the REST/data-plane boundary
  <https://www.mongodb.com/docs/atlas/configure-api-access/>
- **Atlas CLI docs:** command-line Atlas management surface and setup flow
  <https://www.mongodb.com/docs/atlas/cli/current/>
- **Atlas Terraform provider guide:** infrastructure-as-code surface for Atlas
  provisioning and lifecycle management
  <https://www.mongodb.com/docs/atlas/terraform/>
- **Atlas Kubernetes Operator:** Kubernetes control-plane integration and
  lifecycle caveats
  <https://www.mongodb.com/docs/atlas/operator/stable/>

### Connection, security, and access control

- **Connect to a database deployment:** connection prerequisites, private
  networking choices, firewall requirements, and data-plane connection flow
  <https://www.mongodb.com/docs/atlas/connect-to-database-deployment/>
- **Atlas IP access list:** project-scoped client network allow-list behavior,
  limits, temporary entries, and CLI entry points
  <https://www.mongodb.com/docs/atlas/security/ip-access-list/>
- **Atlas database users:** Atlas-vs-database-user boundary, auth mechanisms,
  role model, and operational limits
  <https://www.mongodb.com/docs/atlas/security-add-mongodb-users/>

### Data access and MongoDB application design

- **MongoDB drivers:** official application client surfaces by language
  <https://www.mongodb.com/docs/drivers/>
- **MongoDB data modeling:** access-pattern-first schema design, embedding vs
  referencing, and flexible-schema guidance
  <https://www.mongodb.com/docs/manual/data-modeling/>
- **MongoDB indexes:** index types, write/read tradeoffs, Atlas UI/CLI index
  management, and Performance Advisor entry points
  <https://www.mongodb.com/docs/manual/indexes/>
- **MongoDB aggregation:** preferred aggregation-pipeline model and stage-based
  data processing
  <https://www.mongodb.com/docs/manual/aggregation/>

### Atlas search and AI surfaces

- **Atlas Search:** full-text search, analyzers, mappings, `$search`,
  `$searchMeta`, pagination, faceting, and autocomplete
  <https://www.mongodb.com/docs/atlas/atlas-search/>
- **Atlas Vector Search:** ANN/ENN vector search, hybrid search, RAG, automated
  embedding, and version availability
  <https://www.mongodb.com/docs/atlas/atlas-vector-search/>

### Streaming, encryption, and newer surfaces

- **Atlas Stream Processing:** continuous stream processing using
  aggregation-pipeline syntax over Atlas and Kafka sources
  <https://www.mongodb.com/docs/atlas/atlas-stream-processing/>
- **Queryable Encryption:** query encrypted fields without exposing plaintext;
  equality/range GA, prefix/suffix/substring in preview on 8.2+
  <https://www.mongodb.com/docs/manual/core/queryable-encryption/>
- **Atlas AI Integrations:** consolidated RAG, agent memory, and embedding
  pattern documentation
  <https://www.mongodb.com/docs/atlas/ai-integrations/>

### Operations, backup, observability, and limits

- **Atlas alerts:** alert conditions, lifecycle, acknowledgement, and org/project
  settings
  <https://www.mongodb.com/docs/atlas/alerts/>
- **Atlas cluster metrics:** health metrics, real-time metrics, search metrics,
  and operator-facing signals
  <https://www.mongodb.com/docs/atlas/monitor-cluster-metrics/>
- **Atlas Cloud Backup overview:** backup enablement, redundancy, compliance,
  restore-role requirements, and topology caveats
  <https://www.mongodb.com/docs/atlas/backup/cloud-backup/overview/>
- **Atlas limits:** component, connection, and topology limits that shape
  designs and operating posture
  <https://www.mongodb.com/docs/atlas/reference/atlas-limits/>
- **Atlas Performance Advisor:** slow-query analysis, index suggestions, and
  read-vs-write tradeoff reminders
  <https://www.mongodb.com/docs/atlas/performance-advisor/>

## Atlas quick rules

1. Treat **Atlas** as the control plane and **MongoDB drivers / mongosh** as
   the main data-plane application surfaces.
2. Prefer **service accounts** over legacy API keys for new Atlas Admin API
   automation.
3. Remember the **Atlas Admin API does not read or write your cluster data**;
   it manages Atlas resources and access configuration.
4. Design schemas around **access patterns**; data accessed together should
   generally live together.
5. Prefer **embedding** when it lets common reads complete as a single-document
   fetch; use transactions only when requirements truly cross document
   boundaries.
6. Add indexes for repeated query patterns, but account for the **write cost**
   of every index.
7. Use **Performance Advisor**, cluster metrics, alerts, and limits together;
   Atlas performance work is not just about query syntax.
8. Treat **IP access lists, private networking, database users, and Atlas
   users** as distinct security controls with different scopes.
9. Use **Atlas Search** for full-text/relevance workloads and **Atlas Vector
   Search** for semantic similarity/RAG workloads; they are related but not the
   same feature.
10. Check **deployment tier, MongoDB version, and Atlas limits** before giving
    prescriptive advice.
11. Know the **Flex / Free / Dedicated** tier model; Serverless and M2/M5 have
    been removed and auto-migrated to Flex — they cannot be newly provisioned.
12. Consider **Atlas Stream Processing** for event-driven and real-time ETL
    workloads before building external pipelines.
13. For hybrid retrieval, use **`$rankFusion`** (MongoDB 8.1+) to merge
    full-text and vector results in a single query.
14. **Queryable Encryption** is available for sensitive fields that still need
    to be queried; equality/range queries are GA, prefix/suffix/substring are
    in preview on 8.2+. For CSFLE/QE setup and key management, use
    `mongodb-operations-expert`.

## What Atlas expertise should mean

Atlas expertise spans **control-plane design** (organizations, projects,
deployments, users, network boundaries, backups, monitoring, limits,
automation), **application access** (drivers, connection strings, pooling,
query/index fit, aggregation, search, vector search), **operations** (alerts,
metrics, Performance Advisor, capacity, topology, backup/DR posture),
**delivery models** (UI, Admin API, CLI, Terraform, AKO), **streaming**
(Atlas Stream Processing), and **AI/agentic patterns** (automated embedding,
vector search, hybrid search, RAG, agent memory) — the areas mapped
throughout this file.

## Atlas operating model

### Shared responsibility

- Atlas Architecture Center explicitly frames Atlas through a **shared
  responsibility model**: MongoDB operates the underlying platform, while
  customers own their configuration, access control, and data policies.
- Atlas architectural guidance is organized around five pillars:
  **operational efficiency, security, reliability, performance, and cost
  optimization**.

### Core control-plane hierarchy

- Atlas operations are anchored around **organizations, projects, and
  deployments/clusters**.
- Many role assignments and operational actions are scoped differently at the
  organization vs project layer, so advice should always name the required
  scope.

### Deployment and connectivity model

- Atlas lets teams choose deployment tier (**Free, Flex, or Dedicated**), cloud
  provider, and region based on application latency, cost, and security
  requirements. Serverless instances and M2/M5 clusters have been removed and
  auto-migrated to Flex, their replacement; neither can be newly provisioned.
- Application environments must satisfy both **network access** and
  **database-user authentication** to reach an Atlas deployment.
- Private connectivity choices include **VPC/VNet peering** and **private
  endpoints**, while public connectivity requires IP allow-listing.

## Atlas interaction methods inventory

This is the high-value inventory of **how you can work with Atlas** — surface,
best fit, and representative methods in one place. For exact subcommands or
endpoints, follow the linked source sections.

| Surface | Best fit | Representative methods/actions | Primary source |
| --- | --- | --- | --- |
| Atlas UI | manual ops, investigations, operator workflows | interactive administration, dashboards, backup/alerts/metrics, one-off ops | Atlas docs home |
| Atlas Admin API v2 | CI/CD, automation, inventory, governance, integration tooling | OAuth token exchange, org/project listing, deployment management, DB user management, IP address retrieval, alert/backup administration | Admin API v2 |
| Atlas CLI | local operator workflows, scripts, quick admin actions | `atlas setup`, `atlas api`, `atlas accessLists list`, `atlas accessLists describe`, resource-family subcommands | Atlas CLI |
| Atlas Terraform provider | reproducible provisioning, policy-reviewed infra, GitOps-style Atlas infra | `terraform init`, `terraform plan`, `terraform apply`, `terraform destroy` against Atlas provider resources | Terraform |
| Atlas Kubernetes Operator | platform teams aligning Atlas lifecycle to Kubernetes control planes | `AtlasProject`, `AtlasDeployment`, `AtlasDatabaseUser` custom resources and reconciliation | AKO docs |
| MongoDB drivers | production application code | official driver CRUD/query/aggregation/index/transaction APIs by language | Drivers |
| mongosh / Compass / connection strings | local exploration, DBA/dev workflows | debugging, admin inspection, direct database access | Connect to deployment + Manual/Drivers |
| Atlas Search | autocomplete, faceting, ranked text search | `$search`, `$searchMeta`, analyzers, mappings, facet, pagination | Atlas Search |
| Atlas Vector Search | AI applications, semantic retrieval, agentic systems | vector index creation, ANN/ENN vector search, hybrid search, automated embedding | Atlas Vector Search |
| Atlas Stream Processing | event-driven apps, real-time ETL, time-series ingestion | continuous stream processing using aggregation-pipeline syntax | Atlas Stream Processing |

## Atlas Admin API standards

- The Atlas Admin API is a **REST-style control-plane API** for Atlas resource
  administration.
- The preferred authentication method is **OAuth2 service-account access
  tokens**; HTTP Digest API keys are a **legacy** option.
- Service-account tokens are obtained from
  `POST https://cloud.mongodb.com/api/oauth/token` and are reusable for about
  one hour.
- If your organization requires an **API IP access list**, token generation can
  happen from any IP, but API calls that use the token must come from an
  allowed IP.
- The Admin API does **not** expose application data access; reading and
  writing database documents still happens through cluster auth plus a driver or
  other data-plane client.
- As of **March 2026**, the Admin API enforces **standardized rate limiting**
  using a token-bucket algorithm. Automation code must handle `429 Too Many
  Requests` responses and respect `Retry-After` headers.

### Admin API categories to expect

For exact endpoints, use the API reference. In practice, Atlas Admin API work
usually falls into these buckets:

- **organizations and projects**
- **deployments / clusters / topology**
- **database users and access**
- **network access and IP lists**
- **alerts and monitoring metadata**
- **backup and restore administration**
- **inventory, IP address, and project metadata**

## Atlas CLI standards

- Atlas CLI is the terminal-native Atlas control-plane surface.
- `atlas setup` is the fast-start command that signs up or authenticates,
  creates a free database, loads sample data, adds the current IP to the access
  list, creates a database user, and connects with `mongosh`.
- Atlas CLI is appropriate for **operator workflows and scripts**, but when a
  task needs stable, reviewable automation, the Admin API or Terraform may be a
  better fit.
- Atlas docs explicitly surface CLI entry points for actions like **access list
  inspection** and other Atlas resource operations.

## Terraform and Kubernetes Operator standards

### Terraform

- Use Terraform when you want **declarative Atlas infrastructure management**.
- The Atlas Terraform provider is the main Atlas IaC surface for
  provisioning/managing clusters and related Atlas resources from code.
- MongoDB’s guide expects **service-account authentication** for provider
  configuration.
- **Provider 2.0** (2025) introduced semantic versioning with no-breaking-change
  guarantees in minor/patch releases. Projects on 1.x must follow the 2.0.0
  Upgrade Guide before upgrading. See the refresh section below for details.

### Atlas Kubernetes Operator

- Use Atlas Kubernetes Operator when Atlas resources need to be managed from a
  **Kubernetes control plane**.
- AKO manages Atlas state from **custom resources** like `AtlasProject`,
  `AtlasDeployment`, and `AtlasDatabaseUser`.
- AKO 2.0 changed deletion behavior: deleting a Kubernetes custom resource no
  longer deletes the Atlas resource by default.
- The docs explicitly warn to **define desired config values explicitly** to
  avoid inheriting Atlas defaults that can cause reconciliation loops.

## Atlas security and access-control standards

### Network boundaries

- Atlas only allows cluster client connections from the project’s **IP access
  list** unless you use private networking.
- IP access lists are **project-wide**, not per cluster.
- Atlas supports **temporary IP access list entries** with configurable
  expiration.
- For application connectivity, Atlas docs call out three main patterns:
  public IP allow-listing, **VPC/VNet peering**, and **private endpoints**.

### Identity boundaries

- **Atlas users** are not the same as **database users**.
- Atlas users access the Atlas control plane; database users access MongoDB
  data-plane resources.
- Database users can be scoped with built-in roles, specific privileges, and
  custom roles.
- Atlas supports multiple database-user auth methods, including **SCRAM** and
  **X.509**, with environment-sensitive guidance in the docs.

### Practical security defaults

1. Prefer **private networking** for higher-security production environments.
2. Prefer **service accounts** for Atlas control-plane automation.
3. Keep API and cluster network allow-lists **narrow** and time-bound where
   possible.
4. Use the **minimum project/organization role** that can perform the task.
5. Keep the distinction between **control-plane auth** and **data-plane auth**
   explicit in design docs and code.

## MongoDB coding standards that still apply on Atlas

### Schema design

- Model data around **application access patterns**.
- Keep data that is accessed together together.
- Use **embedding** when it reduces joins and multi-document coordination.
- Use **referencing** when data has a different access cadence, lifecycle, or
  cardinality profile.

### Query and index design

- Add indexes for repeated query shapes.
- Remember every additional index raises **write cost**.
- Atlas Performance Advisor is useful, but recommended indexes still need human
  judgment about workload frequency and write tradeoffs.
- Large arrays and `$lookup`-heavy designs are called out in Atlas docs as
  common sources of slow-query pain.

### Write and transaction design

- Single-document operations are atomic; many practical designs should exploit
  that instead of defaulting to transactions.
- Include expected current state in update filters or use intent-specific
  operators like `$inc` where concurrency matters.
- Use transactions only when multi-document, multi-collection, or cross-shard
  atomicity is actually required.

### Driver usage

- Production application code should usually target an **official MongoDB
  driver**.
- Atlas expertise includes choosing the right **driver-level behavior** for the
  language/runtime, not only knowing Atlas admin features.

## Search and vector-search standards

### Atlas Search

- Atlas Search is the embedded full-text and relevance-search system for Atlas.
- Search queries are expressed through aggregation pipeline stages such as
  **`$search`** and **`$searchMeta`**.
- Atlas Search supports **analyzers, autocomplete, pagination, faceting,
  scoring, static mappings, and dynamic mappings**.
- Use Atlas Search when the workload is fundamentally about **relevance-based
  text retrieval**.

### Atlas Vector Search

- Atlas Vector Search is the semantic/vector retrieval surface for Atlas.
- Use it for **semantic search, hybrid search, and RAG/agentic retrieval**
  patterns.
- Atlas docs call out **ANN** and **ENN** availability by MongoDB version; do
  not give vector-search guidance without checking version support.
- **Automated Embedding** uses the `autoEmbed` index field type with built-in
  **Voyage AI** models (`voyage-4-large`, `voyage-4`, `voyage-4-lite`,
  `voyage-code-3`) to generate embeddings on insert, update, and query without
  an external pipeline. Public preview as of May 2026. See the refresh section
  below for pricing and model details.

## Backup, reliability, and disaster-recovery standards

Platform-level facts only — for restore procedure, RTO/RPO planning, and DR
runbooks, use `mongodb-operations-expert`.

- Atlas Cloud Backup uses the cloud provider’s native snapshot functionality and
  inherits provider redundancy guarantees.
- Atlas supports **multi-region snapshot distribution** for added redundancy and
  region-failure recovery posture.
- Backup restore/admin operations require the appropriate **project backup**
  roles; org-level access alone is not sufficient until explicitly added to the
  project.
- Topology matters: Atlas docs note restore caveats for sharded clusters after
  shard-count changes.

## Monitoring, alerts, and capacity standards

### Alerts

- Atlas alerts are configured around **conditions, thresholds, notification
  methods, and lifecycle management**.
- Alert policies can exist at the **organization** or **project** level.
- Atlas supports acknowledge/unacknowledge, disable/enable, and delete flows
  for alerts.

### Metrics

- Atlas collects metrics across **servers, databases, and MongoDB processes**.
- High-signal metrics called out in the docs include **connections, disk IOPS,
  disk usage, query targeting, and normalized system CPU**.
- Atlas exposes **real-time metrics** and **Atlas Search metrics** in addition
  to cluster views.

### Capacity and limits

- Atlas limits around **connections, shards, nodes, and topology** are design
  inputs, not just operational trivia.
- Atlas docs explicitly recommend **connection pooling**, application tuning,
  autoscaling, and tier scaling when nearing connection limits.

(Representative methods for each surface are folded into the **Atlas
interaction methods inventory** table above. For the MongoDB data-plane query
layer itself — filters, projections, updates, aggregation pipelines — see
`mongodb-expert`.)

## Practical defaults for future Atlas coding/review tasks

1. Start with **which Atlas surface** the task belongs to: UI, Admin API, CLI,
   Terraform, AKO, or application driver.
2. Separate **Atlas control-plane actions** from **MongoDB data-plane actions**
   before proposing code.
3. For application design, start with **access patterns**, then schema, then
   indexes, then aggregation/search/vector shape.
4. For operations, review **alerts + metrics + limits + backup posture**
   together.
5. For security, review **network path + identity model + required role +
   auth method** together.
6. For AI/search work, choose explicitly between **Atlas Search**, **Atlas
   Vector Search**, or **hybrid** patterns.

## Recent platform changes (2025-2026 refresh)

Dated platform changes since late 2024 — MongoDB 8.0/8.2/8.3 server releases,
the Flex tier migration timeline and limits, Atlas Stream Processing GA, the
Voyage AI acquisition and Automated Embedding, Lexical Prefilters, `$rankFusion`
hybrid search, Search Nodes GA, Queryable Encryption enhancements, Terraform
Provider 2.0, Admin API rate-limiting GA, and Architecture Center/CLI updates —
are enumerated in `references/mongodb-atlas-platform-changelog.md` (last
refreshed 2026-05-25). Read it when a version cutoff, GA date, or pricing
figure is load-bearing; otherwise confirm against the linked official release
notes.

## Known ambiguities and guardrails

- “All Atlas methods” is too large for a single static file. Use this context
  as the **condensed expert map**, then jump to the linked Admin API, CLI,
  driver, and Atlas feature references for exact syntax and complete inventories.
- Atlas docs are **versioned and living**. For vector search, API behavior, CLI
  commands, and limits, always confirm the current version or page timestamp
  when precision matters.
- Atlas advice often differs by **cluster tier, deployment topology, cloud
  provider, and MongoDB version**. Good answers should say which of those
  variables matter.

## See Also

For deep Atlas sub-areas (Azure, GCP, multicloud, Search, Vector Search, and 24 more), use the **Sub-skill routing table** above and read the matching `references/…md` file — those topics are now consolidated into this hub.

Peer hubs to hand off to:

- [[mongodb-expert]] — data-plane query, index, schema, aggregation, and storage-engine work
- [[atlas-diagnostics-expert]] — live cluster diagnostics, performance, monitoring, and capacity
- [[mongodb-operations-expert]] — backups, DR, Ops Manager, migration, mongosync, security architecture, encryption, compliance, connectors, and cost
- [[misc-catch-all]] — MongoDB knowledge-base article lookup, internal repo cloning/install/run

<!-- cross-hub-map -->
## Cross-hub map — where every MongoDB topic lives

All MongoDB knowledge is split across **four hubs** (plus `misc-catch-all` for KB-article lookups
and internal repo install/run). If a task's deep material is **not** in this hub's Sub-skill routing
table, it is a reference file under a sibling hub — **activate that hub or Read its `references/<name>.md` directly**.

| Hub | Owns | Example reference files |
| --- | --- | --- |
| `mongodb-expert` | Core data plane + **engine internals**: CRUD/MQL, aggregation, indexes, query performance, schema design, transactions, change streams, time-series, geospatial, views, BSON, error codes, connection strings, driver internals, **WiredTiger cache/eviction/checkpoint internals**, mongosh, database tools, multi-tenancy, sharding, replication, Compass | `mongodb-expert/references/mongodb-wiredtiger-internals.md`, `…/mongodb-indexes-deep.md`, `…/mongodb-sharding.md`, `…/mongodb-replication.md` |
| `mongodb-atlas-expert` (this hub) | Atlas **cloud platform**: control plane, Atlas Search, Vector Search, Stream Processing, Charts, Data Federation, App Services, Triggers, Online Archive, Flex, networking, IAM/RBAC, Terraform, AKO | local `references/mongodb-atlas-search.md`, `references/mongodb-atlas-vector-search.md` |
| `atlas-diagnostics-expert` | Live **diagnostics & performance**: ts-diag, FTDC, performance-troubleshooting symptom triage, benchmarking, monitoring/observability, capacity planning | `atlas-diagnostics-expert/references/mongodb-performance-troubleshooting.md` |
| `mongodb-operations-expert` | **Ops & data movement**: backup/restore, DR, Ops Manager, upgrades, migration, mongosync, relational migrator, CDC, data lifecycle, security architecture, encryption, compliance, cost, Kafka/Spark connectors | `mongodb-operations-expert/references/mongosync.md`, `…/mongodb-backup-restore.md` |

**High-overlap routing notes:**
- Performance **symptom triage** (high CPU, cache pressure, slow queries, latency spikes) starts at `atlas-diagnostics-expert`, but **storage-engine root-cause internals** (WiredTiger cache fill / dirty trigger / eviction threads / reconciliation / checkpoints) are owned by `mongodb-expert` — cross-load `mongodb-expert/references/mongodb-wiredtiger-internals.md` (and `mongodb-wiredtiger.md`) for depth.
- Migration symptoms vs migration **execution**: live-cluster diagnosis → `atlas-diagnostics-expert`; the migration/mongosync runbook → `mongodb-operations-expert`.
- Atlas Search/Vector **query syntax & index design** → `mongodb-atlas-expert`; the slowness *triage* of a running search → `atlas-diagnostics-expert`.
