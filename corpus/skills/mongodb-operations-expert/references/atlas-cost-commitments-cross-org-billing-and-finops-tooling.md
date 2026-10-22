<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Created by `/dr` deep research 2026-10-19; research dir `<local-path>`.

---
name: atlas-cost-commitments-cross-org-billing-and-finops-tooling
description: "Atlas cost commitments, cross-org billing and FinOps tooling: marketplace purchases that draw down AWS EDP, Azure MACC or Google Minimum Commitment; cross-organization billing (one paying org, up to 250 linked orgs); FOCUS 1.3 cost report and FOCUS Data API plus USD and percent-change billing alerts; Terraform tag enforcement (Sentinel/OPA on plans); Resource Policy drift via the nonCompliantResources endpoint (no auto-remediation); Matryoshka dimension truncation (Voyage 4, text-embedding-3) stacked with quantization. TRIGGER: does Atlas count toward my EDP or MACC; one invoice for many Atlas orgs; ingest Atlas billing into a FinOps tool; FOCUS report; enforce cost tags in Terraform; clusters violating a Resource Policy; shrink embedding dimensions. SKIP: invoice basics -> atlas-billing-mechanics-and-cost-visibility; Resource Policy authoring -> atlas-pricing-programs-cost-governance-and-tco; quantization basics -> atlas-cluster-topology-and-tier-economics."
version: "1.0.0"
updated: "2026-10-19"
category: "research"
whenToUse:
  - "check whether Atlas marketplace spend retires a cloud commitment"
  - "consolidate many Atlas organizations onto one invoice"
  - "feed Atlas FOCUS billing data into FinOps tooling"
  - "find Resource Policy violations or enforce cost tags in Terraform"
keywords: ["EDP drawdown", "MACC", "google minimum commitment", "marketplace private offer", "cross-organization billing", "linked organizations", "FOCUS 1.3", "FOCUS data API", "BilledCost", "ContractApplied", "billing alerts", "terraform tags", "sentinel", "OPA", "nonCompliantResources", "resource policy drift", "matryoshka", "dimension truncation"]
tags: ["mongodb", "atlas", "cost", "marketplace", "commitments", "cross-org-billing", "finops", "focus", "terraform", "resource-policies", "vector-search"]
provenance: "/dr · <local-path>"
---

# Atlas Cost Commitments, Cross-Org Billing and FinOps Tooling

## Overview

Customers with a hyperscaler spend commitment can pay for Atlas through that cloud's marketplace so Atlas spend decrements the commitment. Programs differ by cloud: Azure calls it MACC, Google calls it Minimum Commitment drawdown, AWS calls it EDP (not researched here). On Google, 100% of eligible Marketplace spend counts, except services not running on Google Cloud, professional services and some resale cases. Channel private offers since 2025-06-09 draw down at 100% of price but capped at 25% of the commitment. On Azure, eligibility is per offer and Azure-only. Atlas docs describe only pay-as-you-go marketplace linking (one Atlas org to one billing account) and are silent on drawdown terms and private offers, so the exact drawdown treatment of an Atlas contract must be confirmed with MongoDB and the cloud account team.

Cross-organization billing is an Atlas subscription feature (bought via MongoDB Sales) that lets one paying organization settle a single invoice covering many linked organizations. Each linked organization still gets its own monthly invoice showing its usage and a proportional share of the subscription cost, so FinOps can allocate per organization while finance pays once. Organizations stay separate authorization boundaries. Linking has strict prerequisites (matching plan terms, no failed payments, no self-serve support or marketplace subscriptions, no overlapping commitments), a 250-org cap, and role requirements. Tooling (Charts billing ingestion, Invoices API, third-party FinOps platforms) must be pointed at the paying organization or at each organization separately. Evidence comes almost entirely from MongoDB's own docs; unlink behavior is undocumented in sources found.

Atlas exposes billing to FinOps tooling in two ways: a FOCUS 1.3 cost and usage report (console CSV or Atlas Admin API FOCUS Data API, GA 2026-08-19) and the older Invoices API that tools like Vantage use. FOCUS converts Atlas Credit Units into billing currency and adds credit-type and contract fields. For guardrails, Atlas natively offers USD threshold alerts (daily billed, monthly org/project totals) and percent-increase alerts (daily, weekly, monthly), so a basic anomaly and budget layer exists without third-party tools. Third parties (DoiT, Vantage) add cross-vendor views, with uneven documented anomaly and budget support. The FOCUS spec itself does not yet standardise anomaly detection.

Atlas resource tags (key-value pairs on clusters, documented also for projects) flow into invoice CSVs and the Admin API pending-invoice lineItems.tags field, making them the recommended cost-allocation dimension. MongoDB advises enforcing mandatory tags and managing them through Terraform. The mongodbatlas provider exposes tags on mongodbatlas_advanced_cluster as a set of key/value objects, not a map, and has no AWS-style default_tags, so enforcement must come from modules plus plan-time policy (Sentinel or OPA in HCP Terraform, or equivalent) rather than provider features. No Atlas-specific published policy examples were found; generic HashiCorp tag-policy patterns apply. Invoice tagging is limited to cluster-level line items and lags up to 48 hours.

Atlas Resource Policies (Cedar-based, allow-by-default, org-wide) block new non-conforming changes but do not fix or block resources that already exist. The Admin API endpoint GET /api/atlas/v2/orgs/{orgId}/nonCompliantResources (operation getOrgNonCompliantResources, API version 2024-08-05, also exposed as `atlas api resourcePolicies getNonCompliantResources`) lists projects, clusters or networks that violate current policies. MongoDB docs strongly recommend polling it proactively. For cost governance it is the drift detector: oversized tiers, autoscaling bounds and topology that predate a policy stay in place and are only reported here. No Terraform data source for it was found, so monitoring is an API/CLI polling job.

Matryoshka Representation Learning (MRL) trains an embedding model so that the leading N dimensions form a usable shorter embedding. Keeping a prefix and re-normalizing cuts vector storage and index RAM linearly with dimension count, with a small retrieval-quality cost. Voyage AI models (2048/1024/512/256) and OpenAI text-embedding-3 (via the dimensions parameter) support it. For Atlas Vector Search the lever stacks with automatic scalar (about 1/3.75 RAM) and binary (1/24 RAM) quantization, because index RAM, not disk, drives search-node tier size. Evidence on quality loss is mixed: a May 2026 paper finds plain truncation of non-MRL models competitive until about 70-80% reduction, while a vendor post claims MRL is not lossless. Dimensions are fixed in the index definition, so changing them means re-indexing.

## Core Concepts

### Cloud Commit Drawdown via Atlas Marketplace (EDP MACC GCP commit)

- Google Cloud documents a 100% drawdown rate: spend on Google Cloud Marketplace services counts toward a customer's Minimum Commitment unless excluded. Documented exclusions are Google Maps offerings, Google Ads, services not running on Google Cloud, resold services where the vendor has not opted into the resale program, services owned by the buyer/reseller/affiliate, and professional services. Google may change the list at its sole discretion. verified-as-of: 2026-10-13[^c1-1][^c1-7]
- Since 2025-06-09, Google Cloud Marketplace Channel Private Offers (purchases through a Google-authorized channel partner) draw down at 100% of the private offer's final price, but the amount applied to the customer's minimum commitment is capped at 25%. verified-as-of: 2025-05-15[^c1-2][^c1-3]
- Atlas on Azure Marketplace (pay-as-you-go listing) is advertised as drawing down existing Azure committed spend (MACC and Azure commit-to-consume), with one monthly Azure invoice including Atlas usage and upgraded support billed through Azure. MongoDB's page gives no rates or eligibility rules. (two sources) verified-as-of: 2025-03-18[^c1-5][^c1-6]

### Cross-Organization Billing and Linked Invoices

- Cross-organization billing shares one billing subscription across many organizations; the paying organization's invoice lists charges incurred by all linked organizations.[^c2-1][^c2-2]
- Linked organizations are bound by the paying organization's subscription agreement: support level, subscription charges, discounts and payment terms. (two sources)[^c2-1][^c2-2]
- Each linked organization gets its own monthly invoice with its usage plus a percentage of the total subscription cost proportional to its usage; payment still flows only through the paying organization. (two sources)[^c2-1][^c2-2]
- Linking prerequisites: paying org has an Atlas subscription; Organization Billing Admin or Organization Owner on both orgs; linked org has the same minimums, uplifts and SLA as the paying org or no support plan (Atlas Basic).[^c2-1][^c2-2]
- A paying organization can link at most 250 organizations (UI or Admin API); more requires contacting support. A paying organization cannot itself be a linked organization. The subscription enabling the feature is bought through MongoDB Sales. (two sources) verified-as-of: 2026-10-19[^c2-1][^c2-2]

### FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets)

- Atlas provides billing cost and usage data in FOCUS 1.3 format. Users get it from the Invoices page (choose 'CSV FOCUS Cost & Usage Report') or from the FOCUS Data API; MongoDB announced GA on 2026-08-19. verified-as-of: 2026-08-19[^c3-1][^c3-3]
- FOCUS removes the manual conversion of Atlas Credit Units into billing currency: BilledCost and EffectiveCost are returned in billing currency, and PricingCurrency/x_PricingCurrencyRate expose the Atlas Credit rate.[^c3-1][^c3-2]
- The ContractApplied field identifies which Atlas credit covered usage (Prepaid, Promotional or Elastic); InvoiceIssuer distinguishes direct MongoDB billing from marketplace billing; Tags carries resource tags. These give commitment and allocation analysis without custom SKU mapping.[^c3-1][^c3-2]

### Terraform Tag Enforcement and Policy-as-Code for Atlas Cost

- Atlas resource tags are key-value pairs; max 50 tags per cluster, keys and values up to 255 characters, keys unique and case sensitive ('environment' and 'Environment' are distinct). Managing them needs Project Owner or Organization Owner role. verified-as-of: 2026-10-18[^c4-1][^c4-2]
- Tags reach billing: tag keys appear as column headings in the invoice CSV export and as a field in the Admin API invoice payload; the pending-invoices endpoint returns results.lineItems.tags. Tags typically show on line items within 48 hours of being added. verified-as-of: 2026-10-18[^c4-2][^c4-3]

### Resource Policy Drift Monitoring (nonCompliantResources)

- The endpoint is GET /api/atlas/v2/orgs/{orgId}/nonCompliantResources with Accept header application/vnd.atlas.2024-08-05+json. It returns the projects, clusters or networks in an organization that violate current resource policies. The Atlas CLI exposes it 1:1 as `atlas api resourcePolicies getNonCompliantResources --orgId <id> --version 2024-08-05`. verified-as-of: 2026-10-18[^c5-2][^c5-3]
- Atlas does not auto-remediate or block existing out-of-compliance resources. A resource that predates a policy stays unchanged and is only reported. Example: a pre-existing 0.0.0.0/0 access-list entry was not removed after a blocking policy was applied, but appeared as non-compliant.[^c5-3][^c5-1]

### Matryoshka Dimension Truncation for Vector Storage Cost

- Voyage AI documents that vector storage and compute cost scales linearly with embedding dimensionality and with bits per value; its Matryoshka embeddings let a 2048-dimension vector be truncated to its first 256, 512 or 1024 dimensions, each slightly lower in retrieval quality, and the docs show truncation followed by re-normalization.[^c6-1][^c6-2]
- OpenAI states the text-embedding-3 models can be shortened with the dimensions parameter (dropping trailing values) and that text-embedding-3-large cut to 256 dimensions still beats the full 1536-dimension text-embedding-ada-002 on MTEB; this is an OpenAI-reported figure, not independently verified here. (two sources)[^c6-3][^c6-1]

## Tools & Frameworks

- Atlas GCP Marketplace billing (listing 'MongoDB Atlas (Pay as You Go)') has no upfront commitment. An admin picks a Google Cloud Billing Account at subscription, then links an Atlas organization; outstanding or failed invoices must be resolved first. While linked, the payment method shows 'GCP Marketplace Subscription' and cannot be edited; removing it requires unlinking the billing account. Cancelling is done in GCP under Your Orders. (two sources)[^c1-4][^c1-1] _(Cloud Commit Drawdown via Atlas Marketplace (EDP MACC GCP commit))_
- Charts billing ingestion: for cross-org billing, enter the paying organization's ID and toggle ingestion of linked invoices. The API key pair needs Organization Billing Admin and Billing Viewer roles. (two sources)[^c2-3][^c2-1] _(Cross-Organization Billing and Linked Invoices)_
- Tentative: Third-party FinOps tooling such as DoiT connects each Atlas organization separately (one service account per org) and maps organization.id to a billing-account dimension; the page does not describe paying/linked org handling. verified-as-of: 2026-10-19[^c2-5] _(Cross-Organization Billing and Linked Invoices)_
- The FOCUS Data API adds three endpoints to the Atlas Administration API. The first, List Invoices for an Organization (GET /api/atlas/v2/orgs/{orgId}/associatedInvoices), takes month and year filters and can include linked organizations for cross-org billing. All endpoints need Organization Billing Admin, Organization Owner or Organization Billing Viewer. verified-as-of: 2026-10-18[^c3-2][^c3-1] _(FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets))_
- Atlas has native billing alerts in USD: the last daily amount billed (excluding credits applied) per org or project, and monthly totals per organization or per project that reset when the pending invoice closes. These work as budget thresholds. verified-as-of: 2026-10-18[^c3-4][^c3-6] _(FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets))_
- Atlas also has native percentage-increase spend alerts: org daily vs previous day, org weekly vs previous 7 days, org monthly vs previous 30 days, and project daily and weekly. This is a simple built-in anomaly-style detector. (two sources) verified-as-of: 2026-10-18[^c3-4][^c3-6] _(FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets))_
- Atlas sends billing alerts to Organization Owners and Billing Admins by default; a billing email address can be added or used exclusively. (two sources)[^c3-5][^c3-4] _(FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets))_
- Tentative: DoiT Cloud Intelligence added a MongoDB Intelligence module (announced 2025-11-07) that pulls Atlas cost and usage data automatically from a connected organization. Its changelog describes anomaly investigation through the Ava assistant, not a dedicated Atlas anomaly feature, and does not mention budgets. verified-as-of: 2025-11-07[^c3-7] _(FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets))_
- Tentative: Vantage ingests Atlas costs through the Invoices API, not FOCUS, using an org API key with Organization Billing Viewer and Organization Read Only. Atlas credits do not appear in Vantage because the provider API does not expose credit information; per-cluster Active Resources need Project Read Only on each project. verified-as-of: 2026-10-19[^c3-8] _(FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets))_
- HCP Terraform evaluates Sentinel or OPA policy sets against the plan on each workspace run; failed policies can stop the run depending on enforcement level, and permitted users can override. Each policy set uses one framework, but sets from different frameworks can be attached to one workspace. A newer HCL-based 'Terraform policy' (beta) also covers Stacks. (two sources) verified-as-of: 2026-10-19[^c4-7][^c4-6] _(Terraform Tag Enforcement and Policy-as-Code for Atlas Cost)_
- Tentative: Policies can be managed with the Atlas Terraform provider (resource mongodbatlas_resource_policy; provider 1.33.0 or later needed for minimum-TLS and cipher-suite rules). The MongoDB docs describe no Terraform data source for nonCompliantResources, so drift monitoring is done by polling the API or CLI, for example from a scheduled job. verified-as-of: 2026-10-19[^c5-1] _(Resource Policy Drift Monitoring (nonCompliantResources))_

## Methodology

- Daily subscription uplift is billed to each organization on its own usage. At period end an unmet monthly minimum is split across linked and paying organizations by usage share (docs example: $199 unmet split $132.70/$66.30 for 2/3 and 1/3 of charges). (two sources)[^c2-1][^c2-2] _(Cross-Organization Billing and Linked Invoices)_
- FOCUS data is invoice-scoped: it is retrieved per invoice (current or past billing period), so an ingestion pipeline polls invoices by month rather than streaming real-time spend. (two sources)[^c3-2][^c3-1] _(FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets))_
- MongoDB docs strongly recommend proactively monitoring the list of non-compliant resources via the nonCompliantResources endpoint. Policies enforce end-state goals, not intermediate states, so a failing downstream component can temporarily leave a policy non-compliant.[^c5-1][^c5-3] _(Resource Policy Drift Monitoring (nonCompliantResources))_
- Truncation and quantization are multiplicative, complementary levers: Voyage docs state 8-bit gives 4x and 1-bit gives 32x smaller vectors, so a 2048-dimension float32 vector (8 KB) truncated to 512 dimensions and binary-quantized is 64 bytes raw. Atlas's measured RAM ratio for binary is 1/24, so expect less than the raw arithmetic. (two sources)[^c6-1][^c6-2] _(Matryoshka Dimension Truncation for Vector Storage Cost)_
- Truncate only models documented as Matryoshka-trained (Voyage 4 series, OpenAI text-embedding-3) and re-normalize after slicing; validate recall on your own queries at the target dimension before re-indexing, since quality retention depends on model, corpus and query mix. (two sources)[^c6-1][^c6-4] _(Matryoshka Dimension Truncation for Vector Storage Cost)_

## Practical Patterns

- Microsoft MACC eligibility is per offer: each Marketplace offer must be enrolled (Partner Center shows Enrolled/Not Enrolled), free and BYOL offers are not eligible, and only licenses used exclusively in Azure contribute. Atlas clusters deployed on non-Azure clouds are therefore a risk for MACC credit; the Atlas page does not address this. (two sources) verified-as-of: 2026-10-01[^c1-6][^c1-5] _(Cloud Commit Drawdown via Atlas Marketplace (EDP MACC GCP commit))_
- Documented use case: keep separate organizations per team for authorization isolation while paying through one organization; a 250+ project company can create new organizations and link them to avoid project limits and keep one invoice source. (two sources)[^c2-1][^c2-2] _(Cross-Organization Billing and Linked Invoices)_
- FOCUS v1.4 lists anomaly detection, forecasting and exchange-rate modeling only as capabilities future versions 'will consider'. FOCUS standardises the data shape, so anomaly detection and budgets stay tool-specific. (two sources) verified-as-of: 2026-10-19[^c3-9][^c3-1] _(FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets))_
- MongoDB's guidance: define a strategy enforcing mandatory tags on all deployments (start with environment and application), use a standard case-sensitive format, use namespaces/prefixes per business unit, manage tags via Terraform or Admin API, and run a governance routine that checks for untagged or improperly tagged deployments. Cost keys suggested: cost-center or billing-unit.[^c4-2][^c4-1] _(Terraform Tag Enforcement and Policy-as-Code for Atlas Cost)_
- Tentative: AWS provider default_tags (since v3.38.0, April 30 2021) is a provider-block feature where resource-level tags win and Auto Scaling Groups are excluded. The Atlas registry page for advanced_cluster documents no provider-level default tags, so Atlas tags must be set per resource or merged in a module via locals and merge(). verified-as-of: 2026-10-19[^c4-6] _(Terraform Tag Enforcement and Policy-as-Code for Atlas Cost)_
- Tentative: A plan-time tag policy for Atlas would check mongodbatlas_advanced_cluster resources in the plan for required tag keys (e.g. environment, application, cost-center) and fail on missing keys. No published Atlas-specific Sentinel/OPA example was found; HashiCorp's own tag examples target AWS and Azure resources.[^c4-7] _(Terraform Tag Enforcement and Policy-as-Code for Atlas Cost)_
- A new policy applies to new clusters immediately. A non-compliant existing cluster can only be changed in ways that bring it into compliance (for example, if AWS is blocked, an AWS cluster can only move to Azure or Google Cloud). (two sources)[^c5-1][^c5-4] _(Resource Policy Drift Monitoring (nonCompliantResources))_
- Policies are allow-by-default and organization-wide, with per-project exclusions possible. Each policy needs a unique name (duplicate returns 400). Create, update and delete generate activity-feed events. Docs recommend several small policies over one large one, which keeps non-compliance reports attributable to a specific policy. (two sources)[^c5-1][^c5-4] _(Resource Policy Drift Monitoring (nonCompliantResources))_
- Atlas Vector Search fixes numDimensions in the index definition. For Voyage autoEmbed fields it accepts 256, 512, 1024 or 2048 (default 1024), and the autoEmbed fields quantization and numDimensions cannot be edited after creation; changing them means building a new index and deleting the old one. verified-as-of: 2026-10-14[^c6-2][^c6-1] _(Matryoshka Dimension Truncation for Vector Storage Cost)_
- Atlas automatic quantization cuts index RAM to about 1/3.75 of float32 for scalar (int8) and 1/24 for binary (not 1/32, because the HNSW graph is not compressed); binary requires numDimensions to be a multiple of 8. MongoDB recommends quantization for large collections (over 100,000 vectors). Because binary needs a multiple of 8, truncated dimension choices must respect that. verified-as-of: 2026-10-14[^c6-2][^c6-1] _(Matryoshka Dimension Truncation for Vector Storage Cost)_

## Anti-Patterns

- Tentative: Google excludes Marketplace services not running on Google Cloud from drawdown, and Google defers to the vendor on which services run on Google Cloud. For Atlas, clusters on AWS or Azure billed through the GCP Marketplace listing may therefore not count; this is an inference, and no Atlas or Google source states it for Atlas. verified-as-of: 2026-10-13[^c1-1] _(Cloud Commit Drawdown via Atlas Marketplace (EDP MACC GCP commit))_
- Paying and linked organizations cannot have failed payments, an active self-serve support plan, an active self-serve marketplace subscription, or overlapping monthly commitment subscriptions.[^c2-1][^c2-2] _(Cross-Organization Billing and Linked Invoices)_
- FOCUS SaaS support is described by the spec as 'foundational' (columns for pricing currency, effective cost and contracted pricing in non-monetary units such as credits), so cross-vendor comparisons of Atlas data may still need vendor-specific handling. (two sources)[^c3-9][^c3-2] _(FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets))_
- Invoice tagging scope is limited: line items not billed at the cluster level are not eligible for tagging, and cluster line items without a given tag key show blank cells for that column. Untagged spend therefore remains in any report. (two sources) verified-as-of: 2026-10-18[^c4-2][^c4-3] _(Terraform Tag Enforcement and Policy-as-Code for Atlas Cost)_
- Do not put PII/PHI in tags: Billing and other MongoDB services can read them, and cluster tags are sent to Datadog and Prometheus integrations. Tag changes are recorded in the Project Activity Feed.[^c4-1][^c4-2] _(Terraform Tag Enforcement and Policy-as-Code for Atlas Cost)_
- Shard-count false positives: Atlas treats a replica set as having one shard. A minShardCount policy above 1 without a cluster-type check flags every replica set in scope as non-compliant, flooding the endpoint. Use minShardCount only for minimums and maxShardCount only for maximums, and add the !context.cluster.isConvertingToSharded exception for replica-set-to-sharded conversions.[^c5-1][^c5-4] _(Resource Policy Drift Monitoring (nonCompliantResources))_
- Tentative: A May 2026 study (arXiv 2605.16608) reports that truncated embeddings of ordinary non-MRL models are competitive with, and often beat, MRL-trained models up to roughly 70-80% size reduction; MRL helps mainly at heavier truncation (about 80%+), mostly for smaller models. verified-as-of: 2026-05-01[^c6-4] _(Matryoshka Dimension Truncation for Vector Storage Cost)_
- Tentative: ZeroEntropy (a competing embedding vendor) argues MRL is not lossless: on its internal 22-dataset harness a learned post-hoc projection beat the best MRL configuration by about 0.02-0.03 NDCG@10 from 2560 down to 80 dimensions, and it says the original MRL paper's equal-accuracy claim was shown on ImageNet, not text retrieval. The evaluation uses LLM-judged relevance and is unreplicated. verified-as-of: 2026-04-21[^c6-5] _(Matryoshka Dimension Truncation for Vector Storage Cost)_

## Troubleshooting

- Tentative: Atlas docs list Marketplace as a distinct subscription type: invoices for usage come from the marketplace the customer subscribed through, not from MongoDB. The self-serve GCP page does not cover commitment drawdown, private offers, or changing the linked billing account. verified-as-of: 2026-10-19[^c1-4] _(Cloud Commit Drawdown via Atlas Marketplace (EDP MACC GCP commit))_
- Enabling linked invoices on an existing Charts ingestion limits the dashboard to the last three months of each linked org's data; a new ingestion gets twelve months. Invoice updates are picked up only for invoices within three months; ingestion runs daily. (two sources) verified-as-of: 2026-10-19[^c2-3][^c2-2] _(Cross-Organization Billing and Linked Invoices)_
- Tentative: Querying a linked invoice through the Admin API requires Organization Billing Admin or Organization Owner, while the same endpoint's role table lists only Organization Billing Viewer, so the page is internally inconsistent about the role needed.[^c2-4] _(Cross-Organization Billing and Linked Invoices)_
- In the mongodbatlas provider, tags on mongodbatlas_advanced_cluster are written with a map-like literal (tags = { Key = "Value" }) in the registry example but are 'effectively implemented as a set of objects' per a maintainer, so lifecycle ignore_changes cannot target a single tag key such as tags["costcenter"]. The issue was closed March 14, 2024 with no schema change visible. (two sources) verified-as-of: 2026-10-19[^c4-4][^c4-5] _(Terraform Tag Enforcement and Policy-as-Code for Atlas Cost)_
- Autoscaling drift: if a cluster's existing autoscaling limits exceed a new policy's bounds, the cluster keeps scaling automatically beyond them, but manual scaling past the policy limits is refused. Docs say to use nonCompliantResources to find and fix such clusters, which matters for cost because compute autoscaling ceilings can stay above the cap. (two sources)[^c5-1][^c5-2] _(Resource Policy Drift Monitoring (nonCompliantResources))_

## Disagreements & Open Questions

- Disagreement (Cloud Commit Drawdown via Atlas Marketplace (EDP MACC GCP commit)): Redress Compliance says 100% of channel private offer spend counts against the commitment with no cap and that direct SaaS listings may cap at 50%; Google's blog states a 25% cap for channel private offers. Google's own text governs; the 50% figure was not confirmed in Google materials.[^c1-7][^c1-2]
- Open (Cloud Commit Drawdown via Atlas Marketplace (EDP MACC GCP commit)): Whether the 25% cap applies to the offer value or the commitment, and how 'qualifying' is defined (Google's commit-policy page was not fetched).
- Open (Cloud Commit Drawdown via Atlas Marketplace (EDP MACC GCP commit)): Whether Atlas clusters on non-Google clouds billed via the GCP Marketplace count toward the Google commitment.
- Open (Cloud Commit Drawdown via Atlas Marketplace (EDP MACC GCP commit)): AWS EDP drawdown for Atlas via AWS Marketplace was not researched; 'EDP' is AWS terminology, 'MACC' is Azure, GCP uses 'Minimum Commitment'.
- Open (Cloud Commit Drawdown via Atlas Marketplace (EDP MACC GCP commit)): Whether Atlas private offers (vs pay-as-you-go listing) draw down differently; Atlas docs are silent.
- Disagreement (Cross-Organization Billing and Linked Invoices): Admin API getOrgInvoice page says linked invoices need Billing Admin/Owner but its role-requirements list shows only Organization Billing Viewer.[^c2-4]
- Open (Cross-Organization Billing and Linked Invoices): What happens to discounts, minimums and invoices when an org is unlinked (no documentation found).
- Open (Cross-Organization Billing and Linked Invoices): Exact Admin API schema field for linked invoices (linkedInvoices vs linkedInvoice) not confirmed from the official schema.
- Open (Cross-Organization Billing and Linked Invoices): Evidence is nearly all MongoDB-authored; independent third-party confirmation of proportional-split behavior not found. Whether DoiT/other tools consolidate a paying org's linked invoices is unknown.
- Open (Cross-Organization Billing and Linked Invoices): Whether marketplace/commitment subscriptions purchased in one org are consumable by linked orgs (feedback-portal request suggests yes) is unconfirmed in official docs.
- Disagreement (FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets)): A MongoDB feedback-portal request describes only daily billed-amount alerts and asks for monthly project alerts; the Atlas alert-conditions reference lists monthly org/project totals and percentage-increase alerts. The docs are newer and authoritative; the feedback snippet is probably dated.[^c3-6][^c3-4]
- Disagreement (FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets)): Vantage marketing claims Atlas budgets and anomaly alerts; the Vantage Atlas connection docs do not document them and mention no FOCUS use, and the search snippet could not be confirmed.[^c3-8]
- Open (FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets)): Whether Vantage or CloudZero ingest the Atlas FOCUS report directly (Vantage docs show Invoices API only).
- Open (FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets)): Data freshness and lag of the FOCUS Data API for the current open invoice.
- Open (FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets)): Whether DoiT's Atlas module has dedicated anomaly detection and budgets beyond its Ava assistant.
- Open (FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets)): Exact alert-event enum names for Admin API billing alerts (third-party blog cites PENDING_INVOICE_OVER_THRESHOLD; not verified officially).
- Disagreement (Terraform Tag Enforcement and Policy-as-Code for Atlas Cost): Atlas tags docs say tags apply to projects and clusters; the 2023 invoice blog and a feedback post say only clusters/serverless were covered and project tagging was roadmap (an older feedback post says the project resource lacks tags). Current provider support for project tags was not verified.[^c4-1][^c4-2]
- Open (Terraform Tag Enforcement and Policy-as-Code for Atlas Cost): Does mongodbatlas_project (or its tags support) exist in the current provider, and do project/org tags appear on invoices?
- Open (Terraform Tag Enforcement and Policy-as-Code for Atlas Cost): Do tags on deleted or ephemeral clusters appear on invoices (a feedback request suggests they may show untagged; unverified, page 404).
- Open (Terraform Tag Enforcement and Policy-as-Code for Atlas Cost): Any public Sentinel/OPA/Conftest policy library with mongodbatlas tag rules.
- Open (Terraform Tag Enforcement and Policy-as-Code for Atlas Cost): Whether the Terraform registry page was fully read; WebFetch of it was truncated at 100000 of 100364 characters.
- Open (Resource Policy Drift Monitoring (nonCompliantResources)): Exact response schema of getOrgNonCompliantResources (fields per resource, whether the violated policy id is included) was not read from the API reference page.
- Open (Resource Policy Drift Monitoring (nonCompliantResources)): Whether terraform plan or the provider surfaces a policy-violating existing cluster is undocumented; no provider issue was found.
- Open (Resource Policy Drift Monitoring (nonCompliantResources)): Whether the endpoint is paginated or rate-limited for large orgs is unverified.
- Open (Resource Policy Drift Monitoring (nonCompliantResources)): Independence caveat: the MongoDB docs, CLI docs and MongoDB blog share one vendor, and the foojay post is a third-party tutorial. No independent critical source was found in one negation search (queried the provider-drift angle; found nothing contradicting).
- Disagreement (Matryoshka Dimension Truncation for Vector Storage Cost): Vendors (Voyage, OpenAI) present MRL truncation as near-free; ZeroEntropy says MRL is measurably lossy versus a learned projection, and arXiv 2605.16608 finds plain truncation of non-MRL models competitive until about 70-80% reduction.[^c6-5][^c6-4][^c6-1]
- Open (Matryoshka Dimension Truncation for Vector Storage Cost): No independent retrieval-recall benchmark of Voyage 4 truncated to 256/512 dimensions was found.
- Open (Matryoshka Dimension Truncation for Vector Storage Cost): The Atlas quantization docs call automatic quantization Preview in older pages; current GA status was not confirmed.
- Open (Matryoshka Dimension Truncation for Vector Storage Cost): How much search-node tier (and so dollar) reduction a given RAM cut yields on Atlas pricing was not researched.

## References

### Cloud Commit Drawdown via Atlas Marketplace (EDP MACC GCP commit)

[^c1-1]: https://docs.cloud.google.com/marketplace/docs/commit-drawdown — Google Cloud Marketplace commitment drawdown rates (docs)
[^c1-2]: https://cloud.google.com/blog/topics/partners/upgrades-to-google-cloud-marketplace-for-partners — Upgrades to Google Cloud Marketplace for partners (blog)
[^c1-3]: https://www.channelinsider.com/tech-companies/google-cloud-marketplace-partner-commit/ — Google Cloud Marketplace Moves to Incentivize Partner Growth (blog)
[^c1-4]: https://mongodb.com/docs/atlas/billing/gcp-self-serve-marketplace/ — Atlas GCP self-serve marketplace (docs)
[^c1-5]: https://www.mongodb.com/company/blog/news/introducing-pay-as-you-go-atlas-azure-marketplace — Pay-as-you-go Atlas on Azure Marketplace (blog)
[^c1-6]: https://learn.microsoft.com/en-us/partner-center/marketplace-offers/azure-consumption-commitment-enrollment — Azure Consumption Commitment enrollment (docs)
[^c1-7]: https://redresscompliance.com/gcp-negotiation-leverage-framework — Redress GCP negotiation leverage framework (blog)

### Cross-Organization Billing and Linked Invoices

[^c2-1]: https://www.mongodb.com/docs/atlas/billing — Manage Billing (Atlas docs) (docs)
[^c2-2]: https://www.mongodb.com/docs/atlas/billing/invoices — Manage Invoices (Atlas docs) (docs)
[^c2-3]: https://www.mongodb.com/docs/charts/dashboards/manage-dashboards/billing-dashboards/ — Charts billing dashboards (docs)
[^c2-4]: https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/2025-02-19/operation/operation-getorginvoice — Atlas Admin API: Return One Invoice (docs)
[^c2-5]: https://www.doit.com/platform/mongodb-intelligence/ — DoiT MongoDB Intelligence (blog)

### FinOps Tooling for Atlas (FOCUS Ingestion Anomaly Detection Budgets)

[^c3-1]: https://www.mongodb.com/docs/atlas/billing/focus-report/ — Access the FOCUS Cost and Usage Report (docs)
[^c3-2]: https://www.mongodb.com/docs/atlas/billing/focus-api/ — Atlas FOCUS Data API (docs)
[^c3-3]: https://www.mongodb.com/products/updates/now-ga-mongodb-atlas-support-for-focus-v1-3-cost-and-usage-reports/ — Now GA: MongoDB Atlas Support for FOCUS v1.3 (docs)
[^c3-4]: https://www.mongodb.com/docs/atlas/reference/alert-conditions/ — Atlas alert conditions (docs)
[^c3-5]: https://www.mongodb.com/docs/atlas/billing/ — Atlas billing (docs)
[^c3-6]: https://feedback.mongodb.com/ideas/CUSTOMER-I-10398 — MongoDB feedback: billing alerts request (forum)
[^c3-7]: https://www.doit.com/changelog/mongodb-intelligence-finops-visibility-for-atlas-built-into-doit-cloud-intellige — DoiT MongoDB Intelligence (blog)
[^c3-8]: https://docs.vantage.sh/connecting_mongodb-atlas — Vantage: connecting MongoDB Atlas (docs)
[^c3-9]: https://focus.finops.org/docs/specification/v1-4/sections/introduction/ — FOCUS v1.4 introduction (docs)

### Terraform Tag Enforcement and Policy-as-Code for Atlas Cost

[^c4-1]: https://www.mongodb.com/docs/atlas/tags — Atlas Resource Tags (docs)
[^c4-2]: https://mongodb.com/blog/post/deployment-tags-billing-invoices-now-generally-available — Resource Tags in Billing Invoices GA (blog)
[^c4-3]: https://www.mongodb.com/docs/atlas/architecture/current/billing-data/ — Atlas Architecture Center: billing data (docs)
[^c4-4]: https://github.com/mongodb/terraform-provider-mongodbatlas/issues/2006 — Provider issue 2006: tags as map for ignore_changes (repo)
[^c4-5]: https://registry.terraform.io/providers/mongodb/mongodbatlas/latest/docs/resources/advanced_cluster — mongodbatlas_advanced_cluster docs (docs)
[^c4-6]: https://www.hashicorp.com/en/blog/default-tags-in-the-terraform-aws-provider — Default Tags in the Terraform AWS Provider (blog)
[^c4-7]: https://developer.hashicorp.com/terraform/cloud-docs/policy-enforcement — HCP Terraform policy enforcement (docs)

### Resource Policy Drift Monitoring (nonCompliantResources)

[^c5-1]: https://mongodb.com/docs/atlas/atlas-resource-policies — Atlas Resource Policies (docs)
[^c5-2]: https://www.mongodb.com/docs/atlas/cli/current/command/atlas-api-resourcePolicies-getNonCompliantResources/ — atlas api resourcePolicies getNonCompliantResources (docs)
[^c5-3]: https://foojay.io/today/enforcing-governance-in-mongodb-atlas-with-resource-policies/ — Enforcing governance in MongoDB Atlas with resource policies (blog)
[^c5-4]: https://mongodb.com/company/blog/innovation/control-mongodb-atlas-cluster-configurations-with-resource-policies — Control Atlas cluster configurations with resource policies (blog)

### Matryoshka Dimension Truncation for Vector Storage Cost

[^c6-1]: https://www.mongodb.com/docs/voyageai/tutorials/dimensions-and-quantization.md — Flexible Dimensions and Quantization (docs)
[^c6-2]: https://www.mongodb.com/docs/vector-search/indexes/vector-search-type.md — How to Index Fields for Vector Search (docs)
[^c6-3]: https://openai.com/index/new-embedding-models-and-api-updates/ — New embedding models and API updates (blog)
[^c6-4]: https://www.emergentmind.com/papers/2605.16608 — arXiv 2605.16608 truncation of MRL vs non-MRL embeddings (paper)
[^c6-5]: https://zeroentropy.dev/articles/matryoshka-is-dead/ — Matryoshka Is Dead (blog)
