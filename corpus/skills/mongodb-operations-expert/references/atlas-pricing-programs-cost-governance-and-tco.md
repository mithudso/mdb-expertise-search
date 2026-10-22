<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Created by `/dr` deep research 2026-10-19; research dir `<local-path>`.

---
name: atlas-pricing-programs-cost-governance-and-tco
description: "Atlas pricing programs, cost governance and TCO: Flex pricing bands ($8 base to $30 cap, 100-500 ops/sec, 5 GB; M2/M5 and Serverless retired) and Flex-vs-M10 break-even; cost guardrails (org Resource Policies as Cedar forbid rules capping tier, autoscaling bounds, disk and cluster count; project billing alerts; no hard spend cap); FinOps Framework 2025 Inform/Optimize/Operate mapped to Cost Explorer, tags and FOCUS reports; self-managed vs Atlas TCO (labor, backup, Enterprise-only features, lock-in); AI services pricing (Voyage AI per-token rates, Agent Engine preview). TRIGGER: Flex vs dedicated cost; when to leave Flex; cap Atlas spend; Resource Policy for cluster tier; Atlas budget enforcement; FinOps for Atlas; is self-hosting MongoDB cheaper; Voyage embedding cost; Agent Engine pricing. SKIP: invoice and tag mechanics -> atlas-billing-mechanics-and-cost-visibility; tier and node pricing -> atlas-cluster-topology-and-tier-economics; Flex feature limits -> mongodb-atlas-expert."
version: "1.0.0"
updated: "2026-10-19"
category: "research"
whenToUse:
  - "decide whether Flex or a dedicated tier is cheaper"
  - "cap Atlas spend with Resource Policies or IaC"
  - "apply FinOps practices to an Atlas estate"
  - "compare self-managed MongoDB TCO against Atlas"
keywords: ["atlas flex pricing", "flex vs dedicated", "M10", "ops/sec bands", "resource policies", "cedar", "mongodbatlas_resource_policy", "autoscaling bounds", "spend cap", "finops framework", "FOCUS", "inform optimize operate", "self-managed vs atlas", "TCO", "enterprise advanced", "voyage ai pricing", "agent engine"]
tags: ["mongodb", "atlas", "cost", "flex", "governance", "resource-policies", "finops", "tco", "ai-pricing"]
provenance: "/dr · <local-path>"
---

# Atlas Pricing Programs, Cost Governance and TCO

## Overview

Atlas Flex is a usage-banded tier that replaced M2/M5 and Serverless. It costs $8/month for 100 ops/sec and 5 GB, rises in $7/$6/$5/$4 steps to 500 ops/sec, and is hard-capped at $30/month. The cheapest Dedicated tier, M10, lists at about $0.08/hour (about $57-58/month), so at list price Flex is always cheaper and there is no cost crossover. The move to Dedicated is forced by limits instead: 5 GB storage, 500 ops/sec ceiling with per-connection cooldown throttling, and missing features (configurable backups, PITR, private endpoints, peering, multi-region). Cost jumps roughly 2x at that boundary with no middle rung. Third-party blogs quoting per-RPU/WPU Flex rates conflict with the official ops/sec model and should be discounted.

Atlas has no hard spending cap. Cost guardrails are of two kinds. Preventive: org-level Resource Policies, written as Cedar forbid rules, cap cluster tier and autoscaling bounds, disk size, cluster count per project, topology, shard count, cloud provider and region. Owners manage them via UI, Admin API, Terraform (mongodbatlas_resource_policy) or CloudFormation. Detective: project-level billing alerts (monthly pending invoice threshold), Cost Explorer, tags, and cluster pause or termination-protection settings in IaC. Policies are allow-by-default and do not retroactively fix non-compliant clusters; those are only flagged through an API endpoint. Policies bound configuration, not total spend.

Comparing self-managed MongoDB with Atlas on sticker price alone favors self-hosting by a wide margin; TCO depends on labor, backup/PITR tooling, feature dependence and team size. Published evidence is thin: no independent controlled study or Forrester/IDC-style TEI was found, only vendor-adjacent blogs, one migration case study and forum advice. A worked example puts 3-node Atlas M30 near $1,180/month versus about $440 self-hosted compute, with assumed ops labor of $600-1,200/month erasing the gap for small teams. A real migration (Prosopo) cut $3,000+/month to about $160 but ran a single standalone server with cron mongodump backups and did not report staff time. Atlas-only features (Search, Vector Search, Triggers, Data Federation) and Community Edition gaps (no hot backup/PITR) are the main hidden costs. Enterprise Advanced is the self-managed licensed middle path.

The FinOps Foundation Framework 2025 (approved March 2025) runs an iterative Inform, Optimize, Operate lifecycle over Scopes, with SaaS and Public Cloud as initial Scopes. MongoDB publishes no official Inform/Optimize/Operate mapping for Atlas; the mapping here is inference. Atlas supplies the Inform inputs: Cost Explorer (organization, project, cluster, service grouping), resource tags on invoice line items via the Admin API, and FOCUS 1.3 reports through the console and a FOCUS Data API. Its Well-Architected cost pillar points to auto-scaling and billing-data integration with external FinOps tools. Third-party tools such as DoiT ingest Atlas billing. Known gaps from the MongoDB feedback portal: tags are resolved at export time, so deleted clusters appear untagged (status Started, July 2026), and cost is tracked per cluster, not per database.

Atlas AI spend has two parts. Voyage AI embedding and reranking is metered per token (per pixel for multimodal) with published rates, billed to the Atlas org that owns the API key. Automated Embedding in Atlas Vector Search uses the same token rates and meters initial sync, inserts, updates and queries. Atlas Agent Engine (Agent Runtime and Agent Memory) launched 2026-09-29 in public preview with consumption pricing that draws down existing Atlas commitments, but no unit rates are published. Cost governance: Cost Explorer filters by AI model or Automated Embedding, invoices break out per model, and free tokens are one-time per org per model. Older models get no free tokens.

## Core Concepts

### Atlas Flex Pricing and Flex-vs-Dedicated Break-Even

- Flex pricing is a banded ops/sec model: $8 base (0-100 ops/sec, $0.0110/hr), then marginal $7 (to $15, $0.0205/hr), $6 (to $21, $0.0288/hr), $5 (to $26, $0.0356/hr), $4 (to $30, $0.0411/hr) for 400-500 ops/sec. Billed hourly, prorated. verified-as-of: 2026-10-18[^c1-1][^c1-2][^c1-3]
- Flex monthly cost is capped at $30. The base price includes 5 GB storage (uncompressed BSON plus indexes), 100 ops/sec and unlimited data transfer. Atlas does not charge Flex clusters for outgoing data transfer. verified-as-of: 2026-10-18[^c1-1][^c1-2]
- The cheapest Dedicated tier, M10, lists at $0.08/hr (pricing page headline: starts at $56.94/month), versus the Flex ceiling of $30/month. At list price Flex is cheaper at every load it can serve, so there is no cost break-even; the switch is driven by limits and features. The cost step is roughly 1.9-2x with no intermediate tier. verified-as-of: 2026-10-18[^c1-2][^c1-1][^c1-6]
- Flex replaced Shared and Serverless: new M2/M5 and Serverless creation ended Feb 2025; as of Jan 22, 2026 existing M2/M5 and Serverless instances were migrated (M2/M5 to Flex; Serverless under 5 GB to Free or Flex, larger or with serverless private endpoints to Dedicated). Migrated clusters now bill on ops/sec bands. verified-as-of: 2026-10-18[^c1-4][^c1-5][^c1-1]

### Cost Governance Guardrails (Resource Policies and IaC Cost Controls)

- Atlas Resource Policies are org-level, Cedar-based, forbid-only rules (permit is not supported). With no policies, users can do anything their role allows.[^c2-1][^c2-5]
- Cost-relevant policy dimensions include min/max cluster tier and autoscaling bounds (minGeneralClassInstanceSizeValue, maxGeneralClassInstanceSizeValue), disk size (diskSizeGB), clusters per project (context.project.clustersInProject), topology, shard count, cloud provider and region. The tier cap does not cover Low CPU or NVMe SSD classes.[^c2-1][^c2-2]

### Self-Managed MongoDB vs Atlas TCO

- Illustrative comparison: a 3-node Atlas M30 replica set is about $1,180/month before storage and transfer, versus about $440/month compute for three AWS r6g.xlarge self-hosted nodes. Adding assumed ops labor of 4-8 h/month at $150/h ($600-1,200) gives roughly $1,040-1,640/month self-hosted, so the gap closes or inverts for small teams. Backup, monitoring and patching are listed but not priced, and the labor figures are assumptions, not measurements. (two sources) verified-as-of: 2026-03-31[^c3-2][^c3-4]
- Atlas bill drivers beyond instance size are backup storage (PITR extra), internet/cross-region egress (ingress is free) and add-ons such as Search; in the Prosopo case backup plus data transfer was about 55% of the bill. Cost modelling should itemize these rather than compare VM prices. (two sources)[^c3-3][^c3-1]
- Community Edition lacks built-in hot backups/PITR, LDAP/Kerberos, TDE and audit logging (Enterprise-only), has no official Kubernetes operator and no official support. Self-managed teams own replica set failover, monitoring, backup scripts, tuning and upgrades. Enterprise Advanced is a per-server/per-core subscription that adds support and Ops Manager, with licensing rising at scale; Percona (a competing vendor) offers open-source alternatives. (two sources) verified-as-of: 2025-04-14[^c3-3][^c3-4]

### FinOps Framework Applied to Atlas

- Tentative: FinOps Framework 2025 was approved in March 2025. It adds Scopes, defined as a segment of technology-related spending to which practitioners apply FinOps concepts. The initial Scopes are Public Cloud, SaaS and Data Center. Scopes are not mutually exclusive.[^c4-1]

### Atlas AI Services Pricing (Agent Engine and Voyage AI)

- Atlas Embedding and Reranking API is pay-as-you-go: text models bill per token, multimodal models per pixel. Billing is set at organization level, and charges go to the Atlas account linked to the model API key.[^c5-1][^c5-4]
- Current text embedding list prices per 1M tokens: voyage-4-large $0.12, voyage-4 $0.06, voyage-4-lite $0.02, voyage-code-4 $0.12. voyage-finance-2, voyage-law-2 and voyage-code-2 are $0.12. verified-as-of: 2026-10-14[^c5-1][^c5-4][^c5-3]
- Free tier is 200M tokens for most current models and 50M for voyage-finance-2, voyage-law-2 and voyage-code-2. Older models (voyage-3-large and voyage-code-3 at $0.18, voyage-3.5 at $0.06, voyage-3.5-lite at $0.02) get no free tokens. verified-as-of: 2026-10-14[^c5-1][^c5-4]
- Automated Embedding in Atlas Vector Search bills the same per-token model rates. Tokens are metered at index creation (initial sync), on document inserts and updates, and on every $vectorSearch query. The free allowance is 200M tokens per model, one-time, shared across all projects and clusters in the org, and it does not refresh. verified-as-of: 2026-10-14[^c5-2][^c5-3]
- Atlas Agent Engine was announced 2026-09-29 and is in public preview. Atlas Agent Runtime and Atlas Agent Memory are consumption-priced, and usage counts against existing Atlas commitments, so no new contract is needed. verified-as-of: 2026-10-02[^c5-5][^c5-6]
- Tentative: Multimodal Voyage models (voyage-multimodal-3.5 and 3) cost $0.12 per 1M text tokens plus $0.60 per billion pixels, with 200M text tokens and 150B pixels free. verified-as-of: 2026-10-19[^c5-4]

## Tools & Frameworks

- Terraform resource mongodbatlas_resource_policy takes org_id, name, optional description and a policies list whose body holds Cedar text. It is imported as {ORG_ID}-{POLICY_ID}. Policies can be committed and run through CI. Atlas docs also list the Admin API, UI and CloudFormation. Only Organization Owners can create, update or delete policies.[^c2-4][^c2-5][^c2-1] _(Cost Governance Guardrails (Resource Policies and IaC Cost Controls))_
- Project-level billing alert: Alerts > Add Project Alert > Billing > 'Monthly pending invoice ($) total is...' with an operator, threshold and notification channels. It tracks cumulative billed amount for the current calendar month. It notifies only and does not stop spend. The Atlas cost docs recommend an alert at a set amount (example $100). (two sources) verified-as-of: 2026-01-30[^c2-6][^c2-3] _(Cost Governance Guardrails (Resource Policies and IaC Cost Controls))_
- Atlas Cost Explorer filters and groups usage by organization, project, cluster and service. It shows six months of usage and up to 18 months of billing data, and spans linked organizations under cross-organizational billing. This is the native Inform-phase visibility layer. (two sources) verified-as-of: 2026-10-18[^c4-3][^c4-2] _(FinOps Framework Applied to Atlas)_
- Atlas provides billing data in FOCUS 1.3 format. The FinOps Open Cost and Usage Specification gives a vendor-neutral schema. Reports come from the Invoices page (CSV FOCUS Cost & Usage Report) or from the FOCUS Data API's asynchronous request and retrieve endpoints. Columns include BilledCost, EffectiveCost in billing currency, and SubAccountName in place of groupName. (two sources) verified-as-of: 2026-10-18[^c4-2][^c4-3] _(FinOps Framework Applied to Atlas)_
- Tentative: Third-party FinOps platforms ingest Atlas billing directly. DoiT's MongoDB Intelligence module, announced 2025-11-07, breaks spend down by organization, project and SKU, with trend tracking and an AI assistant. verified-as-of: 2025-11-07[^c4-5] _(FinOps Framework Applied to Atlas)_
- Cost visibility: Cost Explorer can filter by AI model, and Automated Embedding has its own Service filter value. Metering-derived costs refresh every 24 hours. Invoices break out usage per model and per project. (two sources)[^c5-1][^c5-2] _(Atlas AI Services Pricing (Agent Engine and Voyage AI))_

## Methodology

- Tentative: Cost governance pattern: model Flex spend as a monthly bound ($8-$30 per cluster) so dev/test fleets have a known worst case. A fleet of N always-busy Flex clusters costs at most $30N, so consolidating onto one shared M10 (about $57) only wins when N is 2 or more clusters that each sit near the cap and fit the Dedicated feature need. This is derived from list prices, not a vendor statement.[^c1-1] _(Atlas Flex Pricing and Flex-vs-Dedicated Break-Even)_
- Tentative: The Framework lifecycle is iterative: Operate outputs inform changes to the Scope, Inform updates the Scope, Optimize sets refinements as targets, then the cycle repeats. The 2025 update dropped 'cloud' from domain and capability names, for example 'Optimize Usage and Cost'.[^c4-1] _(FinOps Framework Applied to Atlas)_
- Tentative: Atlas Well-Architected cost guidance maps to the Optimize phase: enable auto-scaling on the cluster tier to cut over-provisioning, and use tags plus programmatic billing pulls for allocation. MongoDB does not publish an explicit Inform/Optimize/Operate mapping, so this mapping is the researcher's inference.[^c4-3] _(FinOps Framework Applied to Atlas)_

## Practical Patterns

- MongoDB's worked example: 100 ops/sec for 20 days, 250 ops/sec for 5 days, 500 ops/sec for 5 days costs about $13.67 (about $5.28 if deleted after the first 20 days). Because billing is hourly and prorated, bursts cost only for the hours spent in the higher band. (two sources)[^c1-3][^c1-1] _(Atlas Flex Pricing and Flex-vs-Dedicated Break-Even)_
- Triggers to leave Flex for Dedicated (M10+): storage beyond 5 GB; sustained throughput at or above 500 ops/sec (pricing tiers stop there and a hard limit applies, with a sub-second per-connection cooldown that can queue operations over a second); need for dedicated hardware, consistent resources, or granular backup configuration.[^c1-1][^c1-4] _(Atlas Flex Pricing and Flex-vs-Dedicated Break-Even)_
- Example cost cap: forbid cluster.modify when min tier is below M30 or max tier is above M60; forbid diskSizeGB above 4096; forbid clustersInProject above 2. This blocks provisioning and manual or auto scaling outside the range.[^c2-1][^c2-2] _(Cost Governance Guardrails (Resource Policies and IaC Cost Controls))_
- Atlas cost guidance pairs detective controls with IaC levers: consistent tags (team, env, cost center) feed Cost Explorer; dev/test clusters can be paused (paused=true) or terminated via Terraform or the Admin API on a schedule; autoscale-down happens at most once per six hours; manual scale-down is suggested when usage stays below about 45% over 30 days. (two sources)[^c2-3][^c2-6] _(Cost Governance Guardrails (Resource Policies and IaC Cost Controls))_
- Tentative: Prosopo reported cutting an Atlas bill of over $3,000/month (about $1,000 M40 instance, $700 continuous cloud backup, $1,000 internet data transfer) to about $160/month on one dedicated Hetzner server for roughly 500GB. The stated 90% matches neither figure exactly; $3,000 to $160 is about 95%. Staffing time was not reported. verified-as-of: 2025-11-12[^c3-1] _(Self-Managed MongoDB vs Atlas TCO)_
- Decision heuristic repeated across sources: Atlas is the default for small teams with limited DBA/ops staff (MongoDB staff on the community forum call it the most cost-effective option for DBA/ops headcount); self-hosting fits large deployments with dedicated DBAs, compliance/data-residency or air-gapped needs, or scale where Atlas cost is prohibitive. (two sources)[^c3-2][^c3-4] _(Self-Managed MongoDB vs Atlas TCO)_
- Atlas resource tags (for example department, project or cost center) appear on invoice line items. The Return All Pending Invoices endpoint exposes them in results.lineItems.tags. MongoDB recommends feeding that data into external FinOps tools for chargeback, by environment, team or tag value.[^c4-3][^c4-4] _(FinOps Framework Applied to Atlas)_
- Rate limits (RPM and TPM) are set at org level and can be lowered per project. Usage tier rises with cumulative spend: add a payment method for Tier 1, $100 for Tier 2, $1,000 for Tier 3. A linked child org takes the higher of its own and its parent's tier. Automated Embedding rate limits apply per cluster instead. (two sources) verified-as-of: 2026-10-14[^c5-1][^c5-3] _(Atlas AI Services Pricing (Agent Engine and Voyage AI))_

## Anti-Patterns

- Flex does not support multi-region/multi-cloud, sharding, global clusters, network peering, private endpoints, LDAP/auditing, or point-in-time restore; only select cloud regions are available. These gaps force a Dedicated move regardless of cost. (two sources) verified-as-of: 2026-10-14[^c1-4][^c1-1] _(Atlas Flex Pricing and Flex-vs-Dedicated Break-Even)_
- Existing non-compliant clusters are not fixed or blocked. They can only be changed in ways that bring them into compliance, and are flagged via the /orgs/{ORG-ID}/nonCompliantResources endpoint. Existing autoscaling limits outside a new policy can still scale automatically, but manual scaling beyond policy limits is blocked.[^c2-1][^c2-5] _(Cost Governance Guardrails (Resource Policies and IaC Cost Controls))_
- Tentative: Resource policies bound configuration, not total spend. No Atlas control found hard-stops billing. Policies only limit cluster shape, so spend can still grow through number of allowed clusters, storage use within the cap, or data transfer.[^c2-1] _(Cost Governance Guardrails (Resource Policies and IaC Cost Controls))_
- The Prosopo savings came with reduced resilience and scope: a single standalone server (not a replica set), daily cron mongodump backups to a storage box, self-run VPN/firewall/monitoring, and a workload that is ML batch rather than real-time. A like-for-like replica set with PITR would cost more, so the 90% figure is not a general benchmark. (two sources)[^c3-1][^c3-3] _(Self-Managed MongoDB vs Atlas TCO)_
- Atlas-only features (Atlas Search, Vector Search, Data Federation, Triggers, Charts, performance advisor, online archive) have no self-hosted equivalent in Community; equivalent search needs a separate cluster such as Elasticsearch. Search, triggers and device sync use Atlas-specific APIs, which raises migration-off cost. (two sources)[^c3-2][^c3-3] _(Self-Managed MongoDB vs Atlas TCO)_
- Tentative: Atlas resolves tags at invoice export time, not when the cost occurs. A cluster deleted before export shows as untagged, which breaks tag-based allocation for ephemeral clusters. A customer request filed 2026-06-24 (status Started) got a MongoDB reply on 2026-07-15 saying it is being evaluated for prioritization. Workaround: export invoices before deleting short-lived clusters, or keep an external tag-to-cluster mapping. verified-as-of: 2026-07-15[^c4-6] _(FinOps Framework Applied to Atlas)_

## Troubleshooting

- Gotchas: duplicate policy names return 400 Bad Request; one policy per .cedar file; a minimum shard count above 1 needs a !context.cluster.isConvertingToSharded exception or replica-set to sharded conversions are blocked; TLS policies need Terraform provider 1.33.0 or later. (two sources) verified-as-of: 2026-10-18[^c2-1][^c2-2] _(Cost Governance Guardrails (Resource Policies and IaC Cost Controls))_
- Tentative: Self-managing gives control Atlas withholds: Prosopo could not kill leaked connections from the Atlas admin shell and had to stop services, while on its own server it manages connections directly.[^c3-1] _(Self-Managed MongoDB vs Atlas TCO)_
- Neither the MongoDB announcement nor press coverage publishes Agent Engine unit rates, billing units or free-tier terms. Agent Memory uses Voyage AI embeddings, so token-metered embedding cost is likely part of it. Memory and governance can be adopted without the runtime. (two sources) verified-as-of: 2026-10-02[^c5-5][^c5-6] _(Atlas AI Services Pricing (Agent Engine and Voyage AI))_
- Tentative: Rerank prices are $0.05 per 1M tokens for the standard reranker and $0.02 for the lite one. The Voyage pricing page names the models rerank-3 and rerank-3-lite, while search summaries cited rerank-2.5. The model name needs checking before it goes in a TCO model. verified-as-of: 2026-10-19[^c5-4] _(Atlas AI Services Pricing (Agent Engine and Voyage AI))_

## Disagreements & Open Questions

- Disagreement (Atlas Flex Pricing and Flex-vs-Dedicated Break-Even): The Flex costs doc says Dedicated clusters start at $60/month; the pricing page headlines M10 at $56.94/month ($0.08/hr). Both are list estimates over differing hour counts.[^c1-1][^c1-2]
- Disagreement (Atlas Flex Pricing and Flex-vs-Dedicated Break-Even): A third-party blog describes Flex with per-million RPU/WPU rates and per-GB storage (looks like the retired Serverless model, and gives no 5 GB or 500 ops/sec limits). MongoDB's own docs use ops/sec bands with a $30 cap; the official model is treated as authoritative.[^c1-6][^c1-1]
- Open (Atlas Flex Pricing and Flex-vs-Dedicated Break-Even): How ops/sec bands are measured (sustained average vs peak per hour) is not stated on the pages read; the blog's 250 ops/sec example is not a table row.
- Open (Atlas Flex Pricing and Flex-vs-Dedicated Break-Even): Exact Flex throttling behaviour above 500 ops/sec was not confirmed from the Flex Limitations page itself.
- Open (Atlas Flex Pricing and Flex-vs-Dedicated Break-Even): Whether Flex backup (snapshots) is billed separately was not confirmed; the costs page does not mention it.
- Open (Atlas Flex Pricing and Flex-vs-Dedicated Break-Even): M10 effective monthly figure: 0.08/hr x 730h = $58.40 vs the page's $56.94; basis unexplained.
- Disagreement (Cost Governance Guardrails (Resource Policies and IaC Cost Controls)): A customer request (Dec 2025) said Atlas offers only daily billing alerts; a MongoDB admin replied (Jan 2026) that a project-level monthly pending invoice alert already exists. The idea is still marked 'Will Not Implement'.[^c2-6]
- Open (Cost Governance Guardrails (Resource Policies and IaC Cost Controls)): GA vs preview status per policy type was not visible on the truncated docs page.
- Open (Cost Governance Guardrails (Resource Policies and IaC Cost Controls)): No Terraform or API budget or hard spend cap resource was found; confirm none exists.
- Open (Cost Governance Guardrails (Resource Policies and IaC Cost Controls)): Whether the monthly pending invoice alert is available at org level, not only project level.
- Disagreement (Self-Managed MongoDB vs Atlas TCO): Prosopo claims a 90% cut, but its own figures ($3,000+ to $160) imply about 95%; and OneUptime's model implies self-hosting with labor roughly equals or exceeds Atlas for small teams, contradicting the savings narrative.[^c3-1][^c3-2]
- Disagreement (Self-Managed MongoDB vs Atlas TCO): 2021 forum replies disagree on which is cheaper: one says EC2 may be cheaper with more work, MongoDB staff say Atlas is the most cost-effective in staffing terms.[^c3-4]
- Open (Self-Managed MongoDB vs Atlas TCO): No independent controlled TCO study or Forrester/IDC TEI comparing Atlas with self-managed was found; vendor-published TEI may exist on mongodb.com.
- Open (Self-Managed MongoDB vs Atlas TCO): Real staff-hour and incident costs for self-managed MongoDB are unmeasured; the $150/h x 4-8 h figures are assumptions.
- Open (Self-Managed MongoDB vs Atlas TCO): Current Atlas M30/M40 list prices and Enterprise Advanced per-server pricing were not verified against official pricing pages.
- Disagreement (FinOps Framework Applied to Atlas): Secondary commentary on the FinOps Framework lists the domains inconsistently (four vs six domains). The finops.org page names only three domains in text, with the full list in an image.[^c4-1]
- Open (FinOps Framework Applied to Atlas): Whether Atlas projects themselves are taggable and tagged on invoices (docs list organizations and clusters; a 2021 feedback item was planned).
- Open (FinOps Framework Applied to Atlas): Whether cost can be split below cluster level, for example per database, for shared clusters (customer requests say no).
- Open (FinOps Framework Applied to Atlas): Whether MongoDB has shipped the fix for tags on deleted clusters since July 2026.
- Open (FinOps Framework Applied to Atlas): Which FinOps Scope Atlas falls under (SaaS vs Public Cloud vs a data platform scope); the finops.org page gives no statement.
- Disagreement (Atlas AI Services Pricing (Agent Engine and Voyage AI)): The Voyage pricing page lists rerank-3 and rerank-3-lite in its reranker table. Its free-token section reportedly names rerank-2 and rerank-2.5, which the older-models section says have none. Search summaries cite rerank-2.5 at $0.05. Free-token eligibility for rerankers is unclear.[^c5-4]
- Disagreement (Atlas AI Services Pricing (Agent Engine and Voyage AI)): voyage-code-3 appears at $0.18 in the Automated Embedding price table, but the Embedding API billing page lists it as an older model with no free tokens.[^c5-3][^c5-1]
- Open (Atlas AI Services Pricing (Agent Engine and Voyage AI)): Agent Runtime and Agent Memory unit rates and billing units are unpublished; check agentengine.mongodb.com or the Atlas account team.
- Open (Atlas AI Services Pricing (Agent Engine and Voyage AI)): Whether Agent Engine charges at general availability differ from public-preview terms.
- Open (Atlas AI Services Pricing (Agent Engine and Voyage AI)): Whether free tokens apply to rerankers, and the current reranker model names.
- Open (Atlas AI Services Pricing (Agent Engine and Voyage AI)): Whether Agent Memory embedding tokens are billed separately from Agent Memory consumption.

## References

### Atlas Flex Pricing and Flex-vs-Dedicated Break-Even

[^c1-1]: https://mongodb.com/docs/atlas/billing/atlas-flex-costs — Atlas Flex Costs (docs)
[^c1-2]: https://www.mongodb.com/pricing — MongoDB Pricing (docs)
[^c1-3]: https://www.mongodb.com/blog/post/dynamic-workloads-predictable-costs-mongodb-atlas-flex-tier — Dynamic Workloads, Predictable Costs: The MongoDB Atlas Flex Tier (blog)
[^c1-4]: https://www.mongodb.com/docs/atlas/create-database-deployment.md — Cluster Types (docs)
[^c1-5]: https://intercom-help.mongodb.com/en/articles/11689655-serverless-to-dedicated-costs-explained — Serverless to dedicated costs explained (docs)
[^c1-6]: https://oneuptime.com/blog/post/2026-03-31-mongodb-atlas-flex-cluster-pricing-model/markdown — How to Understand Atlas Flex Cluster Pricing Model (blog)

### Cost Governance Guardrails (Resource Policies and IaC Cost Controls)

[^c2-1]: https://www.mongodb.com/en-us/docs/atlas/atlas-resource-policies/ — Atlas Resource Policies (docs)
[^c2-2]: https://mongodb.com/company/blog/innovation/control-mongodb-atlas-cluster-configurations-with-resource-policies — Control Atlas cluster configurations with resource policies (2026-01-13) (blog)
[^c2-3]: https://mongodb.com/docs/atlas/architecture/current/cost-saving-config — Atlas cost saving config (docs)
[^c2-4]: https://www.pulumi.com/registry/packages/mongodbatlas/api-docs/resourcepolicy — Pulumi mongodbatlas ResourcePolicy (docs)
[^c2-5]: https://foojay.io/today/enforcing-governance-in-mongodb-atlas-with-resource-policies/ — Enforcing governance in MongoDB Atlas with resource policies (2025-08-13) (blog)
[^c2-6]: https://feedback.mongodb.com/ideas/CUSTOMER-I-10398 — Monthly billing alert idea and MongoDB reply (forum)

### Self-Managed MongoDB vs Atlas TCO

[^c3-1]: https://prosopo.io/blog/we-cut-our-mongodb-costs-by-90-percent/ — We cut our Mongo DB costs by 90% by moving to Hetzner (blog)
[^c3-2]: https://oneuptime.com/blog/post/2026-03-31-mongodb-atlas-vs-self-hosted-cost-management/markdown — MongoDB Atlas vs Self-Hosted MongoDB: Cost and Management Comparison (blog)
[^c3-3]: https://www.percona.com/blog/mongodb-pricing-explained-what-youre-really-paying-for/ — MongoDB Pricing Explained: What You're Really Paying For (Percona) (blog)
[^c3-4]: https://www.mongodb.com/community/forums/t/migration-to-atlas-vs-on-ec2/121219 — Migration to Atlas vs on EC2 (MongoDB community forum, 2021) (forum)

### FinOps Framework Applied to Atlas

[^c4-1]: https://finops.org/insights/2025-finops-framework — FinOps Framework 2025 update (docs)
[^c4-2]: https://www.mongodb.com/docs/atlas/billing/focus-api/ — Atlas FOCUS Data API (docs)
[^c4-3]: https://www.mongodb.com/docs/atlas/architecture/current/billing-data/ — Features for Atlas Billing Data (docs)
[^c4-4]: https://mongodb.com/blog/post/deployment-tags-billing-invoices-now-generally-available — Resource Tags in Billing Invoices GA (blog)
[^c4-5]: https://www.doit.com/changelog/mongodb-intelligence-finops-visibility-for-atlas-built-into-doit-cloud-intellige — DoiT MongoDB Intelligence (blog)
[^c4-6]: https://feedback.mongodb.com/ideas/CUSTOMER-I-10624 — Preserve Cluster Tags in Invoices After Cluster Deletion (forum)

### Atlas AI Services Pricing (Agent Engine and Voyage AI)

[^c5-1]: https://www.mongodb.com/docs/voyageai/management/billing/ — Manage Billing for the Embedding and Reranking API (docs)
[^c5-2]: https://www.mongodb.com/docs/vector-search/crud-embeddings/automated-embedding/billing/ — Manage Billing for Automated Embedding (docs)
[^c5-3]: https://www.mongodb.com/docs/vector-search/crud-embeddings/automated-embedding/models/ — Models for Automated Embedding (docs)
[^c5-4]: https://docs.voyageai.com/pricing — Voyage AI pricing (docs)
[^c5-5]: https://www.mongodb.com/de-de/company/newsroom/press-releases/mongodb-launches-atlas-agent-engine-to-put-ai-agents-in-production-without-a-new-stack — MongoDB press release: Atlas Agent Engine (docs)
[^c5-6]: https://itbrief.co.uk/story/mongodb-launches-atlas-agent-engine-for-ai-production — IT Brief: MongoDB launches Atlas Agent Engine (blog)
