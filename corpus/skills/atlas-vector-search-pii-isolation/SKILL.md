---
name: atlas-vector-search-pii-isolation
description: >-
  Isolating PII and enforcing entitlement boundaries in MongoDB Atlas Vector
  Search + RAG deployments for regulated (FSI/bank) customers. TRIGGER: keeping
  tenants/entitlements from leaking across a vector index; $vectorSearch
  pre-filtering as an access-control boundary; per-tenant vs shared index design;
  Atlas RBAC, database users, view-based restriction, Search Nodes workload
  isolation; Queryable Encryption/CSFLE interplay with vector search (what can
  and cannot be encrypted when a field must be embedded/searched); PrivateLink,
  CMEK/BYOK, data residency, audit logging for bank RAG. SKIP: prompt-injection /
  lethal-trifecta defense -> rag-prompt-injection-defense; embedding inversion /
  vector-store leakage -> embedding-inversion-threat-model; general Atlas Vector
  Search query/index tuning (HNSW, numCandidates, quantization) ->
  mongodb-atlas-expert; QE/CSFLE mechanics in general -> mongodb-operations-expert;
  bank AI governance/model risk -> bank-genai-model-risk-governance.
version: 1.1.0
updated: 2026-06-29
category: custom
whenToUse:
  - How do I stop one tenant's or user's data from leaking through a shared Atlas vector index?
  - Can I use the $vectorSearch pre-filter as an entitlement/access-control boundary?
  - Per-tenant index vs shared index with metadata filtering — which for a bank?
  - How do Queryable Encryption / CSFLE interact with Atlas Vector Search? Can I encrypt the embedding?
  - What RBAC, view, and network controls isolate PII in an Atlas RAG deployment?
  - A bank needs data residency, private endpoints, CMEK, and audit logging on its vector-search RAG.
keywords:
  - Atlas Vector Search PII isolation
  - vectorSearch pre-filter entitlement access control
  - per-tenant vs shared vector index multi-tenancy
  - Atlas RBAC database users view-based access restriction
  - Search Nodes workload isolation
  - Queryable Encryption CSFLE vector search interplay
  - cannot encrypt embedding vector searchable
  - PrivateLink private endpoint IP access list
  - customer managed keys CMEK BYOK encryption at rest
  - data residency audit logging bank RAG
tags:
  - mongodb
  - atlas
  - vector-search
  - rag
  - data-security
  - pii
  - fsi
  - multi-tenancy
  - encryption
  - tam
---

# Atlas Vector Search — PII Isolation for Regulated RAG

Patterns for isolating PII and enforcing entitlement boundaries in a **MongoDB
Atlas Vector Search + RAG** deployment for banks/FSI. **Core thesis: the
`$vectorSearch` pre-filter and Atlas access controls must enforce the *same*
entitlement boundary the application enforces — a shared vector index without
that boundary is a cross-tenant data-leak waiting to happen.**

## 1. The shared-index leak

ANN search ranks by vector similarity, **not** by who's allowed to see the
result. If you put many tenants' or many entitlement-classes' documents in one
index and don't constrain the query, a RAG retrieval can surface another
party's data into the LLM context. This is **OWASP LLM02 (Sensitive Info
Disclosure)** realized through retrieval. Pair with `rag-prompt-injection-defense`
(the trifecta) and `embedding-inversion-threat-model` (why the embedding itself leaks).

## 2. Enforce entitlements in the `$vectorSearch` pre-filter

- `$vectorSearch` supports a **`filter`** (pre-filter) evaluated **during** ANN
  traversal over indexed `filter`-type fields — so you don't get a full result set
  then post-filter (which wrecks recall and can leak counts).
- Index the entitlement keys (e.g. `tenantId`, `legalEntity`, `dataClass`,
  `allowedRoles`) as filter fields, and **always** inject the requesting principal's
  allowed values server-side — never from client input.

```js
{ $vectorSearch: {
    index: "rag_idx",
    path: "embedding",
    queryVector: qvec,
    numCandidates: 200, limit: 10,
    filter: { tenantId: ctx.tenantId, dataClass: { $in: ctx.allowedClasses } }
} }
```

- ⚠️ The pre-filter is an **application-enforced** boundary: if any code path can set
  `ctx.tenantId` from untrusted input, the boundary is gone. Treat it like a SQL
  tenant predicate — centralize it, test it, log it.

## 3. Per-tenant vs shared index

| Model | Isolation | Cost/ops | Use when |
|---|---|---|---|
| **Shared index + pre-filter** | Logical (query-enforced) | Cheapest, simplest | Many small tenants, equal sensitivity, strong central filter discipline |
| **Per-tenant index/collection** | Physical | More indexes to manage; per-tenant tuning | High-sensitivity tenants, hard regulatory separation, noisy-neighbor concerns |
| **Per-tenant database/cluster** | Strongest | Highest | Top-tier regulated tenants, data-residency-per-tenant, contractual isolation |

🔶 Banks frequently land on **physical isolation for the most sensitive data class**
and shared+filtered for the rest. Decide per data-classification, not globally.

## 4. Access control & workload isolation

- **Atlas RBAC + database users** scoped to the minimum collections/actions; map app
  service accounts to least-privilege roles.
- **View-based restriction**: expose a filtered/redacted **view** and point the RAG
  ingestion/query at the view, so the retrieval surface can't see restricted fields.
- **Search Nodes** isolate search/vector workloads onto dedicated nodes — operational
  isolation and predictable performance, separate from the OLTP path.

## 5. Encryption interplay (the key constraint)

- **The embedding vector must be stored as raw floats to be searchable** — you
  **cannot** Queryable-Encrypt or CSFLE-encrypt the vector field and still run
  `$vectorSearch` over it. (See `embedding-inversion-threat-model` for why that raw
  vector is itself sensitive.)
- **Do** encrypt the **sensitive source/metadata fields** (account numbers, names, SSNs)
  with **Queryable Encryption** (equality/range GA) or **CSFLE**, keeping them out of
  plaintext server-side, while leaving the embedding + coarse filter keys queryable.
- **Encryption at rest** is on by default in Atlas; add **customer-managed keys
  (CMEK/BYOK)** via AWS KMS / Azure Key Vault / GCP KMS for key custody and
  crypto-shredding. See `mongodb-operations-expert` for QE/CSFLE mechanics.

## 6. Network, residency & audit (the bank checklist)

- **Private networking**: AWS PrivateLink / Azure Private Link / GCP Private Service
  Connect endpoints; tighten the **IP access list**; no public exposure.
- **Data residency**: pin clusters (and per-tenant clusters where required) to in-region;
  multi-region only with residency in mind.
- **Audit logging**: enable Atlas database auditing; ship logs to the bank's SIEM;
  capture access to PII collections/views.
- **Bring this to the first technical meeting** — large-bank-class procurement expects the
  PrivateLink + CMEK + audit + Terraform/Atlas-Operator story up front (see the
  account-intelligence skills + `enterprise-vendor-management-and-tprm`).

## Sources

- MongoDB Atlas Vector Search docs — `$vectorSearch` pre-filtering, index definition
  (mongodb.com/docs/atlas/atlas-vector-search/).
- MongoDB Atlas Search Nodes, RBAC, view, and database-auditing docs (mongodb.com/docs/atlas/).
- MongoDB Queryable Encryption & CSFLE docs (mongodb.com/docs/manual/core/queryable-encryption/).
- MongoDB Atlas network security / private endpoints & CMEK docs.

⚠️ Verify the current GA/preview status of any encryption + vector-search combination
against the live MongoDB docs before a customer commitment; this interplay is evolving.
