---
name: mongodb-atlas-platform-changelog
description: "Dated Atlas and MongoDB platform changes since late 2024 — 8.0/8.2/8.3 server releases, Flex tier migration timeline and limits, Atlas Stream Processing GA, Voyage AI acquisition and Automated Embedding, Lexical Prefilters, $rankFusion hybrid search, Search Nodes GA, Queryable Encryption enhancements, Terraform Provider 2.0, Admin API rate limiting GA, Architecture Center compliance additions, Atlas CLI updates, and AI/agentic positioning. Read this when a version cutoff, GA date, or pricing figure is load-bearing."
version: "1.0.0"
updated: "2026-07-17"
origin: local
category: mongodb
---

# Recent Atlas platform changes (2025-2026 refresh)

<!-- provenance: extracted from mongodb-atlas-expert/SKILL.md "Recent platform changes" section during a skill-optimizer Pass J length-budget pass · verified-as-of: 2026-05-25 -->

This file captures major Atlas and MongoDB platform changes since late 2024.
Last refreshed: **2026-05-25**. Confirm against the linked official docs/release
notes when precision matters — this is a condensed changelog, not the source
of truth.

### MongoDB server versions on Atlas

- **MongoDB 8.0** (GA October 2024): 32% query throughput improvement, 56%
  faster bulk writes, 200% faster time-series aggregations, 50x faster data
  distribution for sharding at 50% lower cost. Introduced default maximum time
  limits for queries and the ability to reject recurring problem queries.
  <https://www.mongodb.com/docs/manual/release-notes/8.0/>
- **MongoDB 8.2** (2025): Public preview of enhanced Queryable Encryption
  (prefix, suffix, substring queries on encrypted fields), `$currentDate` in
  `aggregate()`, standardized spill-to-disk metrics in explain output.
  <https://www.mongodb.com/docs/manual/release-notes/8.2/>
- **MongoDB 8.3** (May 2026): ~45% more reads and ~35% more writes vs 8.0,
  sub-100ms retrieval targets for agent workloads, new `$hash` and `$hexHash`
  aggregation expressions (MD5, SHA-256, XXH64), `arrayIndexAs` field in
  `$map`/`$filter`/`$reduce`, `removeShard` deprecated in favor of four new
  drain/removal commands, security hardening and native type-coercion
  expressions.
  <https://www.mongodb.com/docs/manual/release-notes/8.3/>

### Flex clusters (replaces Shared and Serverless tiers)

- **Atlas Flex tier** is the unified replacement for M2, M5, and Serverless
  instances. It combines the best of Shared and Serverless into a single
  offering with dynamic scaling.
- As of **March 2025**, Serverless instances are no longer supported; existing
  instances were migrated to Free, Flex, or Dedicated clusters.
- As of **May 2025**, all M2/M5 clusters have been auto-migrated to Flex.
- As of **January 2026**, the old `createGroupCluster` (M2/M5) and
  `createGroupServerlessInstance` API endpoints only support Flex clusters.
- Flex includes 100 ops/sec and 5 GB storage by default, scales to 500 ops/sec
  dynamically, $8 base + usage-based billing capped at $30/month.
  <https://www.mongodb.com/docs/atlas/manage-flex-clusters/>
- **Flex key limits:** 500 connections max, 5 GB storage hard cap (no auto-expand),
  500 collections max, 100 databases max, MongoDB 8.0 minimum (auto-upgrade only).
- **Flex does NOT support:** Private Endpoints (no PrivateLink/VPC peering),
  Continuous Backup/PITR (daily snapshot only), BYOK encryption at rest, Database
  Auditing, Performance Advisor, Rolling index builds, `allowDiskUse`, server-side JS.
- **Flex DOES support** (unlike old M2/M5): Atlas Search, Atlas Vector Search,
  Change Streams, Triggers — but Vector Search shares resources with `mongod` on Flex;
  upgrade to M10+ with dedicated Search Nodes before production Vector Search.
- **Migration is one-way:** Flex → dedicated is supported (downtime required);
  dedicated → Flex downgrade is NOT supported. Download Flex snapshots before upgrading
  as they do not transfer to dedicated clusters.
- For full Flex decision matrix, pricing breakdown, and tooling migration, see
  `mongodb-atlas-flex-serverless` skill.

### Atlas Stream Processing (GA)

- **Atlas Stream Processing** reached general availability as of **March 2025**.
- Enables continuous stream processing pipelines over Atlas data using
  aggregation-pipeline syntax.
- Supports emitting to **Time Series Collections**, Kafka headers, and
  multiple tiers (SP10 for low-traffic, SP30 for production).
- Available on AWS and Azure across global regions.
  <https://www.mongodb.com/docs/atlas/atlas-stream-processing/>

### Voyage AI acquisition and Automated Embedding

- MongoDB acquired **Voyage AI** in February 2025 (~$220M) to embed
  high-accuracy embedding models directly into Atlas Vector Search.
- **Automated Embedding** (public preview May 2026) uses the `autoEmbed` index
  field type to automatically generate Voyage AI vector embeddings on insert,
  update, and query -- no external pipeline needed.
- Available models: `voyage-4-large`, `voyage-4`, `voyage-4-lite`,
  `voyage-code-3`.
- Pricing: per million tokens ($0.12 large / $0.06 standard / $0.02 lite);
  first 200M tokens free per account; Batch API gives 33% discount.
  <https://www.mongodb.com/docs/atlas/atlas-vector-search/>

### Lexical Prefilters for Vector Search

- **Lexical Prefilters** allow advanced text and geo analysis filters (fuzzy
  search, phrase matching, wildcards, `geoWithin`) as prefilters before vector
  similarity search.
- Unlike standard `$vectorSearch` filters (equals, range, exists), lexical
  prefilters use full analyzed-text capabilities from Atlas Search operators.
- Create a `$search` index with vector type fields and use
  `$search.vectorSearch` in aggregation pipelines.
  <https://www.mongodb.com/company/blog/product-release-announcements/semantic-power-lexical-precision-advanced-filtering-for-vector-search>

### Hybrid Search with `$rankFusion`

- The **`$rankFusion`** aggregation operator merges and re-ranks results from
  multiple search pipelines (full-text + vector).
- Requires **MongoDB 8.1+** on Atlas.
- Enables true hybrid search combining keyword precision with semantic
  intelligence in a single query.
  <https://www.mongodb.com/docs/atlas/atlas-vector-search/hybrid-search/>

### Search Nodes (dedicated search infrastructure)

- **Search Nodes** are generally available on AWS, Google Cloud, and Azure for
  both development and production deployments.
- Provide dedicated infrastructure for Atlas Search and Vector Search,
  independent of database compute, with up to 60% query-time reduction.
- **Multi-region Search Nodes** are available in preview for multi-region and
  multi-cloud clusters.
  <https://www.mongodb.com/docs/atlas/atlas-search/>

### Queryable Encryption enhancements

- **Equality and range queries** on encrypted fields are GA and production-ready
  at no additional cost on Atlas, Enterprise Advanced, and Community Edition.
- **Prefix, suffix, and substring queries** on encrypted string fields are in
  public preview starting MongoDB 8.2.
  <https://www.mongodb.com/docs/manual/core/queryable-encryption/>

### Terraform Provider 2.0

- **MongoDB Atlas Terraform Provider 2.0** shipped in 2025 with semantic
  versioning, no-breaking-change guarantees in minor/patch releases, eliminated
  hanging timeouts, and simplified advanced-cluster migrations.
- **Migration required** from 1.x; see the 2.0.0 Upgrade Guide.
- Atlas Architecture Center examples now target Provider 2.x.
  <https://www.mongodb.com/products/updates/terraform-mongodb-atlas-provider-2-0-now-available/>

### Atlas Admin API standardized rate limiting

- **Standardized rate limiting** for the Atlas Admin API v2 became GA in
  **March 2026**, using a token-bucket algorithm.
- Automation and integration code should handle `429 Too Many Requests`
  responses and respect `Retry-After` headers.
  <https://www.mongodb.com/company/blog/product-release-announcements/introducing-standardized-atlas-admin-api-rate-limiting>

### Atlas Architecture Center compliance additions

- **PCI DSS Compliance** page added February 2026.
- **HIPAA Compliance** page added February 2026.
- Multi-region opinionated guidance, Reliability section, and Operational
  Readiness Checklist added August 2025.
  <https://www.mongodb.com/docs/atlas/architecture/current/changelog/>

### Atlas CLI updates (2025-2026)

- `atlas api` subcommand reached **GA** in October 2025.
- TLS 1.3 support added for `atlas api clusters` commands (December 2025).
- `atlas api aiModelRateLimits resetModelRateLimit` command added April 2026.
  <https://www.mongodb.com/docs/atlas/cli/current/atlas-cli-changelog/>

### AI and agentic positioning

- MongoDB is positioning Atlas as a **converged datastore for agentic AI**:
  operational data + vector search + stream processing + agent memory in one
  platform.
- First-class integrations with **LangGraph.js** (long-term memory store, GA),
  and major agent frameworks.
- Atlas AI Integrations documentation consolidates RAG, agent, and embedding
  patterns.
  <https://www.mongodb.com/docs/atlas/ai-integrations/>
