<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Created by `/dr` deep research 2026-10-19; research dir `<local-path>`.

---
name: atlas-billing-mechanics-and-cost-visibility
description: "Atlas billing mechanics and cost visibility: invoice anatomy (Usage Details line items by SKU/project/cloud, Payment Details, CSV/FOCUS exports); Cost Explorer UI and async Admin API (18-month history); resource tags on invoice line items (Tag/<key> CSV columns, export-time snapshot) for showback and chargeback; billing alerts (notification-only); subscription types (Elastic, Prepaid, Flex and Monthly Commitment, credit drawdown); cloud marketplace billing (AWS/GCP/Azure pay-as-you-go linking); support plan pricing (Developer/Pro/Enterprise). TRIGGER: read an Atlas invoice; which SKU grew; Cost Explorer API; tag clusters for chargeback; Atlas billing alert; prepaid credits ran out; pay Atlas through AWS Marketplace; support plan cost. SKIP: tier and node pricing -> atlas-cluster-topology-and-tier-economics; Flex pricing and cost guardrails -> atlas-pricing-programs-cost-governance-and-tco."
version: "1.0.0"
updated: "2026-10-19"
category: "research"
whenToUse:
  - "understand an Atlas invoice and its line items"
  - "pull Atlas spend by project or cluster with Cost Explorer or the API"
  - "attribute Atlas cost to teams with tags"
  - "set up Atlas billing alerts or marketplace billing"
keywords: ["atlas invoice", "usage details", "SKU", "cost explorer", "billing API", "FOCUS report", "resource tags", "chargeback", "showback", "billing alerts", "prepaid credits", "monthly commitment", "elastic billing", "AWS marketplace", "Azure marketplace", "GCP marketplace", "support plan"]
tags: ["mongodb", "atlas", "cost", "billing", "invoice", "cost-explorer", "tags", "marketplace", "support"]
provenance: "/dr · <local-path>"
---

# Atlas Billing Mechanics and Cost Visibility

## Overview

Atlas bills at the organization level and posts usage charges the day after they are incurred. Each org has a pending (current) invoice and past invoices. An invoice page has a header card (amount due, PDF/CSV/FOCUS downloads), Payment Details itemized by payment method, Total Usage and By Deployment charts, Summary By Project and Summary by Service tables, and Usage Details line items (dates, quantity in server hours, project, cloud provider, SKU rate, amount). Billed Usage can differ from Usage because of monthly minimums or multi-month catch-up billing. Total Cost is unit price times billed usage plus taxes. Dedicated clusters bill hourly, data transfer daily, and support minimums monthly. Unpaid invoices lead to suspension after 30 days and lock after 60. The Admin API exposes the same structure (list, single, pending invoices with lineItems). Third-party coverage is thin; most claims rest on MongoDB's own docs.

Atlas Cost Explorer is a UI under Billing that charts monthly spend grouped by organization, project, cluster or service, with six months charted and 18 months of billing data reachable. The same data is exposed through the Atlas Administration API as an asynchronous create-then-poll pair (POST creates a query and returns a 64-character token; GET with the token returns results or a 'processing' response). Line-item data is also available via pending-invoice and invoice endpoints (with tags) and, since FOCUS 1.3 GA (Aug 2026), via a FOCUS CSV report API that converts Atlas Credits to billing currency. Third-party FinOps tools (DoiT, OpenCost) ingest it through billing-read credentials. Caveats: usage lags provider reporting, current-month values are estimates, tags reflect call-time config, and FOCUS reports exclude shortfall, tax and adjustments.

Atlas resource tags are case-sensitive key-value pairs on projects and clusters. Atlas copies cluster tags onto billing output: each tag key becomes a Tag/<key> column in the invoice CSV, and the Admin API returns them in results.lineItems.tags. Teams use that line-item data to build showback (visibility) or chargeback (billing back) reports in external FinOps tools or MongoDB Charts. The main limit is timing: tags are read at export or API-call time, not when the cost was incurred. Retagging mid-cycle rewrites the whole invoice view, and clusters deleted before export show as untagged. Non-cluster line items are not taggable. The FinOps Foundation frames the same pattern as allocation, with tagging as one mechanism and unallocated spend reported separately.

Atlas billing alerts are notification-only. Organization Owners (and Billing Admins, with limited rights) create them on the Organization Alerts page by choosing the Billing target. Conditions: credit card about to expire, amount billed yesterday, current bill for any single project, current bill for the organization, and percentage gross-spend change (daily, weekly, monthly) at organization level, plus project-level daily/weekly billing change. Thresholds are USD amounts or percentages. Alerts go to roles, users, email, SMS, Slack, PagerDuty, Datadog, Teams, and others. Atlas has no setting that stops or pauses spend at a billing threshold; the only hard ceiling found is Flex clusters, capped at $30 per month by pricing design. All primary evidence comes from MongoDB itself; independent corroboration was not found.

Atlas bills against subscription types: Elastic (pay as you go, monthly invoice), Prepaid (credits bought up front for a term), Flex Commitment (unused credits charged in the final month), Monthly Commitment (greater of usage or prorated commitment; unused credits cover later overages), and Marketplace. Credits draw down in table order. When credits run out, Monthly Commitment orgs move to Elastic Billing and usage beyond credits is billed, with two tax invoices in the transition period. Invoices show credits as a negative line and a PREPAID status. Expired subscriptions fall back to the payment method on file. Sources are all MongoDB-owned; the only independent source is a vendor-interested advisory white paper that does not address overage or expiry, so overage rates and term-end credit expiry remain unconfirmed.

Atlas can be paid through AWS, Google Cloud and Azure marketplaces. Each self-serve listing is a Pay-as-You-Go subscription with no upfront commitment. The customer links a marketplace billing account to one Atlas organization. After linking, the cloud provider issues the invoice and Atlas shows the marketplace as the payment method. Linking requires clearing unpaid Atlas invoices first. Unlinking happens on the cloud side and does not delete clusters, so charges can resume against MongoDB. MongoDB's docs do not cover private offers, contracts, commitment drawdown, frequency of Azure/GCP billing or required roles. Per-cloud differences matter when reconciling cost.

Atlas support is an organization-level paid subscription layered on top of usage. Basic is free. Developer (30-day trial, 8h first response), Pro (from 2h) and Enterprise/Platinum add response speed and services. The only public price formula is a MongoDB-staff forum post from Jan 2024: Developer is the greater of $49 or 20% of total monthly Atlas charges; Pro starts at $799. Official docs and the plans page publish no prices; the Atlas UI (Support > View plan) shows the estimate. Plan changes take effect the first of next month, cancellation at month end, and reactivation bills retroactively up to 90 days. Invoices show support per cloud provider with the minimum computed once per org. Current list prices are unverified.

## Core Concepts

### Atlas Billing and Invoice Anatomy

- Atlas charges for services at the organization level and posts charges the day after they are incurred. Viewing billing needs Organization Billing Viewer or higher; changing payment method or billing profile needs Organization Owner or Billing Admin. (two sources)[^c1-1][^c1-2]
- The current (pending) invoice page has: header card (amount due, total usage cost, billing info, downloads as PDF usage summary, CSV usage summary, or CSV FOCUS report), Payment Details, Total Usage chart, By Deployment chart, Summary By Project table (excludes subscription charges), Summary by Service table, and Usage Details. (two sources) verified-as-of: 2026-10-18[^c1-1][^c1-3]
- Usage Details is the line-item layer: dates used and billed, quantity (server hours), project, hosting cloud provider, SKU rate, and amount. Usage not tied to a cloud provider appears under 'Other Atlas Usage'. It can be downloaded as CSV. (two sources)[^c1-1][^c1-4]
- Payment Details columns: payment method (prepaid/promotional credits, monthly commitment, marketplace, credit card, PayPal), Date, Payment status, Usage, Billed Usage, Total Cost, Amount Due, Actions (PDF, VIEW DETAILS, PAY NOW for YayPay customers, RETRY for failed payments). Total Cost = unit price x billed usage + taxes. (two sources)[^c1-1][^c1-2]
- Metering cadence differs by service: dedicated clusters hourly, data transfer daily, BI Connector as a daily uplift capped at a monthly maximum, support minimum computed once monthly per org, Flex clusters capped at $30/month. Support appears as a separate line per cloud provider (AWS Support, Google Cloud Support, Microsoft Azure Support). (two sources) verified-as-of: 2026-10-18[^c1-3][^c1-1]
- Tentative: Under cross-organization billing, the paying org's invoice lists charges for all linked orgs, each linked org also gets its own monthly invoice, and an unmet monthly minimum is distributed across linked invoices in proportion to their usage.[^c1-2]

### Atlas Cost Explorer and Billing Data API

- Cost Explorer is in the Billing section of the Atlas UI and is visible only to users with the Organization Owner, Billing Admin or Organization Billing Viewer role.[^c2-5][^c2-1]
- Cost Explorer groups and filters usage by organization, project, cluster and service, showing a stacked-column Usage chart and a Usage By Month table. The organization filter requires cross-organization billing.[^c2-1][^c2-5]
- The docs chart the past six months in Cost Explorer and allow access to billing data up to the past 18 months. The announcement blog describes 'up to 18 months' as the window. (two sources) verified-as-of: 2026-10-18[^c2-1][^c2-5]

### Resource Tags and Cost Allocation (Showback/Chargeback)

- Atlas resource tags are key-value pairs added to projects and clusters. Limits: 50 tags per cluster, keys and values up to 255 characters each, unique keys, and each tag value on at most 1,000 resources. Keys and values are case-sensitive, so environment and Environment are different keys. verified-as-of: 2026-10-18[^c3-1][^c3-5]
- In the invoice CSV, Atlas adds one column per tag key with the header Tag/<your key>, and the cell holds the tag value. The Admin API returns the tags in the results.lineItems.tags field of the Return All Pending Invoices for One Organization endpoint.[^c3-2][^c3-3][^c3-4]

### Billing Alerts and Budget Controls

- Billing alerts are created from the Organization Alerts page by choosing Target = Billing. Conditions offered: Credit card is about to expire; Amount billed yesterday is above; Current bill for any single project is above; Current bill for the organization is above; Organization gross spend daily, weekly and monthly change is above. verified-as-of: 2026-10-18[^c4-1][^c4-2]
- Dollar-threshold conditions take a USD amount. The 'current bill' conditions (single project, organization) are organization-only, count the monthly total, and reset when the current pending invoice closes. 'Amount billed yesterday' ignores credits applied for that day and applies to both organizations and projects. verified-as-of: 2026-10-18[^c4-2][^c4-1]
- Gross-spend change alerts fire on a percentage increase versus the prior period (previous day, previous 7 days, previous 30 days). The organization variants are configured on the Organization Alerts page; the project variants (daily and weekly billing change) on the Project Alerts page. (two sources) verified-as-of: 2026-10-18[^c4-2][^c4-1]
- Tentative: The credit-card-expiry alert triggers at the start of the month the card expires, and Atlas enables it automatically when a card is first added.[^c4-2]
- Managing all organization alerts needs the Organization Owner role; Organization Billing Admin has limited authorization to manage billing alerts. Project alerts need Project Owner or Project Alerts Manager. (two sources)[^c4-1][^c4-3]

### Atlas Credits Prepaid Subscriptions and Overage

- Atlas subscription types are Elastic (monthly invoice for usage, no commitment), Prepaid (credits bought up front for a chosen term), Flex Commitment, Monthly Commitment and Marketplace. Purchase of commitments goes through MongoDB Sales; activation needs Organization Owner or Organization Billing Admin. (two sources)[^c5-1][^c5-3]
- Tentative: Flex Commitment: unused credits are charged in the last month of the term. Monthly Commitment: each month bills the greater of usage or the prorated monthly commitment, and unused credits carry forward to cover later overages in the term.[^c5-1]
- Available credits are drawn down from the top item to the bottom in the order shown in the Available Credits table; upcoming credits appear grey and are not yet spent. Expired credits appear in the History table. (two sources)[^c5-1][^c5-2]
- Tentative: Direct Atlas pay as you go accepts credit card, PayPal and invoice with no minimum; the AWS Marketplace pay-as-you-go listing removed the earlier upfront-commitment requirement (page updated 2025-09-23). verified-as-of: 2025-09-23[^c5-3]

### Cloud Marketplace Billing for Atlas (AWS GCP Azure)

- Atlas self-serve marketplace listings on AWS, Google Cloud and Azure are Pay-as-You-Go subscriptions with no upfront commitment.[^c6-2][^c6-3][^c6-1]
- Atlas usage and support costs bought through the AWS Marketplace are billed together to the customer's AWS account daily, with no payment minimum. (two sources) verified-as-of: 2025-09-23[^c6-5][^c6-2]
- For marketplace subscribers the invoice comes from the marketplace, not MongoDB. The subscriptions page says purchasers receive an invoice with an amount due through that marketplace, and no MongoDB tax invoice. (two sources)[^c6-4][^c6-5]
- Before an Atlas organization can be linked to an AWS, Azure or GCP billing account, all outstanding or failed invoices in that organization must be resolved.[^c6-2][^c6-3][^c6-1]
- After linking, Payment Method stays empty until the cloud sync finishes, then shows the marketplace subscription. The Payment Method Edit button is disabled while the subscription is active; the only way to remove it is to unlink on the cloud side.[^c6-2][^c6-3][^c6-1]

### Atlas Support Plan Pricing

- Atlas support tiers are Basic (free), Developer, Pro and Enterprise; the plans page also lists Platinum. Initial Severity-1 response goals: Developer 8 hours, Pro 2 hours, Enterprise 30 minutes, Platinum 15 minutes (the docs say Enterprise 15 min to 2 hours). (two sources) verified-as-of: 2026-10-18[^c7-1][^c7-4]
- Tentative: A MongoDB staff member (Andrew Davidson, 2024-01-05) stated Atlas Developer is priced starting at $49/month, billed at the greater of $49 or 20% of total monthly charges, and Atlas Pro starts at $799/month. verified-as-of: 2024-01-05[^c7-3]
- Third-party guidance says premium support typically costs up to 20% of monthly cluster spend, with negotiated rates for large enterprise deals; this is consistent with the 20% forum figure but is not an official MongoDB price. (two sources) verified-as-of: 2026-10-18[^c7-5][^c7-3]
- Neither the Atlas support docs nor the public Atlas support plans page publishes dollar or percentage prices; exact cost is shown in the Atlas UI (organization Support page, View plan) or via sales, and Enterprise is arranged by contacting MongoDB. verified-as-of: 2026-10-18[^c7-1][^c7-4]
- Tentative: On invoices, paid support appears as a monthly total in the Summary and as per-cloud-provider line items in Details, split proportionally to usage per provider; unattributed support lands under Other Atlas Usage. The support minimum is computed once per month for the whole organization. verified-as-of: 2026-10-18[^c7-2]

## Tools & Frameworks

- The Admin API exposes invoices at /api/atlas/v2/orgs/{ORG_ID}/invoices (list), /invoices/{INVOICE_ID} (single, JSON or CSV), and /invoices/pending. The list returns id, startDate, endDate, amountBilledCents; detail returns lineItems with sku, totalPriceCents (unit price x quantity x 100), groupId (project). Reading needs Organization Billing Viewer. (two sources) verified-as-of: 2026-10-18[^c1-4][^c1-6] _(Atlas Billing and Invoice Anatomy)_
- Past invoices can be filtered by status (pending payment, $0.00 total, paid) and by date range; the Billing Cost Explorer retains up to 18 months of billing data. (two sources) verified-as-of: 2026-10-18[^c1-2][^c1-1] _(Atlas Billing and Invoice Anatomy)_
- The Cost Explorer API is asynchronous: POST /api/atlas/v2/orgs/{orgId}/billing/costExplorer/usage (createOrgBillingCostExplorerUsageProcess) returns a 64-character token; GET .../costExplorer/usage/{token} (getOrgBillingCostExplorerUsage) returns results, or a 'processing' response telling the caller to retry later.[^c2-2][^c2-6] _(Atlas Cost Explorer and Billing Data API)_
- The Cost Explorer query body requires startDate (inclusive) and endDate (exclusive), both of which must be the start of a month. Optional fields: organizations, projects, clusters (24-hex IDs), services (enum such as Clusters, Storage, Backup, Data Transfer, Support, Credits, AI Model APIs), groupBy (organizations|projects|clusters|services) and includePartialMatches (default false). A groupBy dimension needs at least one filter value for it. (two sources) verified-as-of: 2026-10-18[^c2-2][^c2-6] _(Atlas Cost Explorer and Billing Data API)_
- Tentative: The Atlas CLI exposes the Cost Explorer API as `atlas api invoices createCostExplorerProcess --orgId <id> --file request.json` (autogenerated 1:1 from the Admin API; version 2023-01-01). verified-as-of: 2026-10-18[^c2-6] _(Atlas Cost Explorer and Billing Data API)_
- The 'Return All Pending Invoices for One Organization' endpoint returns line items whose results.lineItems.tags field reflects applied resource tags, so FinOps tools can break spend down by environment or team. Atlas's published Go SDK examples also list historical invoices (with linked invoices) and export to CSV or JSON.[^c2-1][^c2-2] _(Atlas Cost Explorer and Billing Data API)_
- Tentative: The Atlas FOCUS Data API (FOCUS 1.3, CSV only) works as list invoices (GET /orgs/{orgId}/associatedInvoices), request report (POST /orgs/{orgId}/invoices/{invoiceId}/reports), then retrieve (GET .../reports/{reportId}). States run PENDING, RUNNING, SUCCEEDED or FAILED. Poll no more than every 5 seconds. The download URL lasts 15 minutes and the report 7 days. Each request covers one invoice for one organization. verified-as-of: 2026-10-18[^c2-3] _(Atlas Cost Explorer and Billing Data API)_
- To create or modify tags a user needs the Project Owner role on the project or the Organization Owner role on its parent organization. Atlas records every tag add, change or delete in the Project Activity Feed. Tags can be managed from the Atlas UI, Admin API, Atlas CLI, or the Terraform provider. (two sources)[^c3-1][^c3-5] _(Resource Tags and Cost Allocation (Showback/Chargeback))_
- Billing alerts can be delivered through Atlas Organization roles, Atlas User, Email, Mobile (SMS), Slack, PagerDuty, Datadog, VictorOps, Opsgenie and Microsoft Teams. The 'send if condition lasts at least' and 'resend after' options are not available for billing alerts, which are event-based. (two sources) verified-as-of: 2026-10-18[^c4-1][^c4-2] _(Billing Alerts and Budget Controls)_
- Tentative: Invoices list credits as a payment method; CSV exports contain a row whose Description contains 'Credit' with a negative Amount (filter it out to compute the subtotal, or use it to see when credits ran out). Invoice status PREPAID means the prepaid subscription covered the invoice with credits.[^c5-2] _(Atlas Credits Prepaid Subscriptions and Overage)_
- Tentative: Azure linking lets the user add optional key-value tags on the Azure subscription at purchase time.[^c6-3] _(Cloud Marketplace Billing for Atlas (AWS GCP Azure))_

## Methodology

- The FinOps Framework defines allocation as apportioning costs to those responsible for them. Resource-level naming conventions and tags make that finer-grained. The strategy decides whether costs go to showback (to teams), chargeback (to finance) or cost-center allocation. Reports should surface spend not covered by the allocation metadata, and shared costs are split by a stated model (proportional, fixed or even). Tagging works better with automation and infrastructure as code. (two sources)[^c3-7][^c3-3] _(Resource Tags and Cost Allocation (Showback/Chargeback))_
- The billing docs frame alerts as 'Billing Quota Management': they notify a designated person when a bill exceeds a USD limit or a credit card is about to expire. (two sources)[^c4-3][^c4-4] _(Billing Alerts and Budget Controls)_
- Unlinking is done in the cloud console: AWS 'Cancel Subscription' on the agreement, Azure 'Cancel subscription' on the resource, GCP 'Cancel Purchase' on Your Orders.[^c6-2][^c6-3][^c6-1] _(Cloud Marketplace Billing for Atlas (AWS GCP Azure))_
- Only users with the Organization Owner role can change an organization's support plan. Developer has a 30-day free trial and auto-enrolls into paid Developer at the estimated cost afterwards. (two sources)[^c7-1][^c7-3] _(Atlas Support Plan Pricing)_
- Tentative: Switching plans changes billing on the first day of the next month; canceling during a trial stops billing immediately; canceling outside a trial takes effect at month end with billing continuing until then. verified-as-of: 2026-10-18[^c7-1] _(Atlas Support Plan Pricing)_

## Practical Patterns

- Tentative: Credits applied to an invoice appear in the CSV as a row whose Description contains 'Credit' with a negative Amount; filter that row out to get the pre-credit subtotal.[^c1-1] _(Atlas Billing and Invoice Anatomy)_
- Third-party tools consume Atlas billing data with read-only billing credentials. DoiT uses a service account with Organization Billing Viewer, Read Only and Member roles, imports six months on connect and then updates hourly. The OpenCost plugin uses an org API key pair and says MongoDB detailed costs are only retrievable for the current month. (two sources) verified-as-of: 2026-10-18[^c2-8][^c2-7] _(Atlas Cost Explorer and Billing Data API)_
- Service accounts (client ID/secret) are the authentication method shown in MongoDB's Go SDK billing examples; API key pairs also work (OpenCost). Cross-org billing: linked invoices are visible only to Organization Billing Admin or Owner of the paying organization. (two sources)[^c2-1][^c2-7] _(Atlas Cost Explorer and Billing Data API)_
- MongoDB's recommended tagging practice: use a standardized, case-sensitive format across all resource types, and use a consistent cost-allocation key such as cost-center or billing-unit. Also apply environment and application tags to every resource, use namespaces or prefixes for business units, enforce a mandatory-tag policy with regular checks for untagged deployments, and manage tags through the Admin API, Atlas CLI or Terraform provider.[^c3-1][^c3-5] _(Resource Tags and Cost Allocation (Showback/Chargeback))_
- The Atlas Architecture Center's FinOps path combines four mechanisms. Tags give cost allocation by department, project or cost center. The pending-invoices Admin API feeds external FinOps tools. Cross-organization billing gives one paying organization visibility across linked organizations. MongoDB Charts billing dashboards accept tag-based charts and filters. Cost Explorer groups only by organization, project, cluster and service, not by tag. (two sources) verified-as-of: 2026-10-18[^c3-3][^c3-2] _(Resource Tags and Cost Allocation (Showback/Chargeback))_
- Billing alert recipients: by default Organization Owners and Billing Admins. If a Billing Email Address is set and 'Only send invoice emails to the Billing Email Address' is unchecked, alerts go to that address plus Owners and Billing Admins; if checked, to the billing address only. (two sources) verified-as-of: 2026-10-18[^c4-3][^c4-1] _(Billing Alerts and Budget Controls)_
- Tentative: Atlas Flex clusters are the one built-in cost ceiling: priced at $8 to $30 per 30 days and capped at $30 per month, billed hourly, from 5 GB storage and 100 ops/sec base up to 500 ops/sec. verified-as-of: 2026-10-18[^c4-5] _(Billing Alerts and Budget Controls)_
- Tentative: If a Monthly Commitment org runs out of credits it automatically transitions to Elastic Billing, and usage beyond credits is billed. The transition produces two tax invoices for the same billing period. The Elastic Billing indicator shows only that it is enabled, not that it is active. verified-as-of: 2026-10-18[^c5-1] _(Atlas Credits Prepaid Subscriptions and Overage)_
- Tentative: On Google Cloud Monthly Commitment the monthly minimum is total commitment divided by months; once cumulative usage exceeds the total commitment, the account moves to elastic billing and pays the minimum plus elastic usage. verified-as-of: 2026-10-18[^c5-1] _(Atlas Credits Prepaid Subscriptions and Overage)_
- Tentative: A buyer-side advisory firm (Redress Compliance, unsourced estimates, sells negotiation services) claims a default 3-year Atlas Credits commit with 15-30% annual ramp; treat as unverified. verified-as-of: 2025-09-29[^c5-4] _(Atlas Credits Prepaid Subscriptions and Overage)_
- Linking is per Atlas organization: after subscribing in the cloud console, the user picks an organization on the Atlas 'Select an Organization to Link' page. A disabled Link button means the organization is ineligible; a tooltip gives the reason.[^c6-2][^c6-3][^c6-1] _(Cloud Marketplace Billing for Atlas (AWS GCP Azure))_
- Tentative: Private-offer-only marketplace listings exist as a separate procurement path with fixed-term contract pricing (for example an AWS listing for MongoDB Enterprise Advanced on GovCloud, 12 months, no refunds). That listing is not Atlas Pay-as-You-Go. verified-as-of: 2026-10-18[^c6-6] _(Cloud Marketplace Billing for Atlas (AWS GCP Azure))_
- Granular database auditing, customer-key encryption at rest and LDAP are paid add-ons on Developer and Pro but included in Enterprise and Platinum; the billing docs say the 15% (KMS/LDAP) and 10% (auditing) cluster uplifts exclude Enterprise and Platinum customers. (two sources) verified-as-of: 2026-10-18[^c7-4][^c7-2] _(Atlas Support Plan Pricing)_

## Anti-Patterns

- Tentative: If an org fails to pay an invoice for over 30 days, Atlas suspends the org and stops backups without terminating them. Over 60 days, Atlas locks the org and can terminate backups and deployments. verified-as-of: 2026-10-18[^c1-2] _(Atlas Billing and Invoice Anatomy)_
- Tags in invoice CSVs and Admin API responses reflect the tag configuration at the moment of generation or the call. Changing tags mid-cycle makes the invoice show only the latest configuration, so retag history is not preserved in billing data. (two sources)[^c2-4][^c2-1] _(Atlas Cost Explorer and Billing Data API)_
- Invoice tags reflect the tag configuration at the moment the CSV is generated or the API is called. If a team retags a resource mid-billing-cycle, the whole invoice shows only the latest tags. Showback and chargeback reports must therefore treat tags as a snapshot, not a history.[^c3-2][^c3-4] _(Resource Tags and Cost Allocation (Showback/Chargeback))_
- Atlas stores tag values in plain text. Billing can read them, and Atlas sends cluster tags to the Datadog and Prometheus integrations. Tags must not hold PII or PHI.[^c3-1][^c3-5] _(Resource Tags and Cost Allocation (Showback/Chargeback))_
- Atlas billing alerts only notify. A MongoDB community moderator stated in April 2023 that no feature stops services when a billing threshold is reached and suggested a feature request; the current docs describe alert conditions only and list no spend-limit setting. (two sources) verified-as-of: 2026-10-18[^c4-4][^c4-2] _(Billing Alerts and Budget Controls)_
- Tentative: If a subscription activation code is not added within the first 30 days of use, MongoDB charges the account's credit card, and card charges are non-refundable. verified-as-of: 2026-10-18[^c5-1] _(Atlas Credits Prepaid Subscriptions and Overage)_
- Tentative: Cancelling the AWS subscription unlinks billing but does not delete Atlas resources or data, and the AWS page warns charges continue for them. Plan a replacement payment method in Atlas before cancelling.[^c6-2] _(Cloud Marketplace Billing for Atlas (AWS GCP Azure))_
- Atlas docs for the three marketplace pages cover Subscriptions only. They do not describe private offers, marketplace contracts, cloud commitment drawdown, required cloud roles, or invoice frequency for Azure and GCP. (two sources) verified-as-of: 2026-10-18[^c6-4][^c6-3] _(Cloud Marketplace Billing for Atlas (AWS GCP Azure))_
- Reactivating Developer or self-serve Pro after cancelling bills support retroactively from when a non-Basic plan was last active, up to 90 days back; the forum example showed a confirmation prompt adding ~$705.48 of prior charges to the pending invoice. Exceptions: Developer to self-serve Pro, and self-serve Pro to subscription-tied Pro.[^c7-1][^c7-3] _(Atlas Support Plan Pricing)_

## Troubleshooting

- Billed Usage can differ from Usage when a month's usage is below the subscription's monthly minimum, or when one month's billed usage encompasses usage from multiple months. (two sources)[^c1-1][^c1-2] _(Atlas Billing and Invoice Anatomy)_
- Dedicated clusters (M10+) run a minimum 3-node replica set, so an idle cluster bills 72 server hours per calendar day (3 x 24); billing follows provisioned instances, not actual use. Daily rows of 72 hours on an invoice are therefore normal. (two sources)[^c1-5][^c1-3] _(Atlas Billing and Invoice Anatomy)_
- Tentative: FOCUS reports cover usage-based costs only and exclude shortfall charges, tax line items and adjustments or refunds. Pending-month values are estimates, so re-pull after the month closes. BilledCost and EffectiveCost are already in billing currency; PricingCurrency* columns stay in Atlas Credits. verified-as-of: 2026-10-18[^c2-3] _(Atlas Cost Explorer and Billing Data API)_
- Billing lag: usage at the end of a billing period can land on the next period's invoice (e.g. Oct 31 usage processed in November). Data transfer, private endpoint and backup costs can post days later because of cloud provider reporting lag. The invoice schema notes charges typically post the next day. (two sources)[^c2-4][^c2-2] _(Atlas Cost Explorer and Billing Data API)_
- Tentative: Because Atlas fetches tags at export time, clusters deleted before the export appear untagged on the invoice. A customer request filed 2026-06-24 (CUSTOMER-I-10624) asks Atlas to record tags when the cost is incurred. Its status is Started with 5 votes. On 2026-07-15 MongoDB said it is evaluating priority, with no timeline. The requester has no reliable workaround and matches creation and deletion logs to line items by hand. verified-as-of: 2026-07-15[^c3-6] _(Resource Tags and Cost Allocation (Showback/Chargeback))_
- Tentative: Per the 2023 GA announcement (updated 2025-03), tags usually appear on invoice line items within 48 hours of being added. Line items not billed at the cluster level are not eligible for tags, and cluster-related line items with no tag stay untagged. These statements pre-date the current docs, which also mention project tags, so recheck eligibility before relying on them. verified-as-of: 2025-03-11[^c3-4] _(Resource Tags and Cost Allocation (Showback/Chargeback))_
- Tentative: Cluster labels will be deprecated in a future release, and MongoDB strongly recommends resource tags instead. verified-as-of: 2026-10-18[^c3-1] _(Resource Tags and Cost Allocation (Showback/Chargeback))_
- Tentative: When a subscription expires, Atlas charges remaining usage to the payment method on file, reverts paid support plans to Basic, risks suspension if the payment method declines, and bills unpaid charges on the next subscription activation. Deployments must be terminated to stop charges. verified-as-of: 2026-10-18[^c5-1] _(Atlas Credits Prepaid Subscriptions and Overage)_
- Tentative: The AWS page says a credit card cannot be added as backup payment while the AWS Marketplace subscription is active.[^c6-2] _(Cloud Marketplace Billing for Atlas (AWS GCP Azure))_

## Disagreements & Open Questions

- Disagreement (Atlas Billing and Invoice Anatomy): The invoices docs say line items live under Usage Details on the invoice page, while the billing page tells readers to 'view all of your invoices' for line items; the UI path to past-invoice line items is described inconsistently.[^c1-2][^c1-1]
- Open (Atlas Billing and Invoice Anatomy): Only one independent non-MongoDB source (OneUptime blog, which itself warns to verify against the API reference) was found; no independent confirmation of invoice mechanics exists in this pass.
- Open (Atlas Billing and Invoice Anatomy): Full Admin API invoice schema (statusName values, payments, credits, salesTaxCents, startingBalanceCents) not read; WebFetch truncated the 150k-char page.
- Open (Atlas Billing and Invoice Anatomy): Timezone of the billing day boundary (UTC assumed from API startDate ISO 8601 UTC in search snippet) not confirmed in the docs fetched.
- Open (Atlas Billing and Invoice Anatomy): Invoice-breakdown page does not state proration or tax rules; International Usage and Taxation page not read.
- Open (Atlas Billing and Invoice Anatomy): Negation round found no disputed numbers; it surfaced a reported April 2026 backup-overcharge billing bug on the status page and an April 2024 billing-delay incident (search snippets only, not fetched).
- Disagreement (Atlas Cost Explorer and Billing Data API): Docs say Cost Explorer charts six months while billing data is accessible for 18 months; the announcement blog says a window of up to 18 months. OpenCost says detailed costs are retrievable only for the current month, which narrows what that plugin can see versus the Admin API.[^c2-1][^c2-5][^c2-7]
- Open (Atlas Cost Explorer and Billing Data API): Required roles, rate limits and token expiry for the Cost Explorer API are not documented on pages read (CLI page lacks them; the Admin API operation page body was not fully retrieved).
- Open (Atlas Cost Explorer and Billing Data API): Shape of CostExplorerQueryResult is an untyped object in the OpenAPI spec.
- Open (Atlas Cost Explorer and Billing Data API): Whether Cost Explorer figures equal invoice totals after month close (FAQ and FOCUS docs only imply estimates/lag; no explicit reconciliation statement found).
- Open (Atlas Cost Explorer and Billing Data API): No independent forum evidence found of Cost Explorer discrepancies; negation search returned only feedback-portal requests about billing alerts.
- Disagreement (Resource Tags and Cost Allocation (Showback/Chargeback)): The 2023 blog says tagging applies to clusters and serverless instances, and that tagging projects is on the roadmap. The current docs say tags can be added to projects and clusters. Whether project tags reach invoice line items is not stated.[^c3-5][^c3-1]
- Disagreement (Resource Tags and Cost Allocation (Showback/Chargeback)): The Architecture Center says the pending-invoices tags field reflects tags on resources 'such as organizations and clusters'. The tags docs list only projects and clusters as taggable.[^c3-3][^c3-1]
- Open (Resource Tags and Cost Allocation (Showback/Chargeback)): Do project-level tags appear on invoice CSV or API line items, and do non-cluster line items (support, data transfer, backup) carry tags today?
- Open (Resource Tags and Cost Allocation (Showback/Chargeback)): Does the mongodbatlas_advanced_cluster Terraform resource expose tags? The registry page could not be fetched, and a 2024 feedback post said mongodbatlas_project lacked tags.
- Open (Resource Tags and Cost Allocation (Showback/Chargeback)): Has MongoDB shipped point-in-time tag capture for deleted clusters (CUSTOMER-I-10624)?
- Open (Resource Tags and Cost Allocation (Showback/Chargeback)): Is the 48-hour tag propagation delay from the 2023 blog still accurate?
- Open (Resource Tags and Cost Allocation (Showback/Chargeback)): FinOps-vendor thresholds (80% tag accuracy, under 5% untagged) came only from vendor blogs and were not verified against FinOps Foundation publications.
- Disagreement (Billing Alerts and Budget Controls): A MongoDB feedback-portal thread (search snippets only, page not fetchable) shows conflicting statements on monthly project-level billing alerts: one request marked 'Will Not Implement', a later staff reply saying monthly project-level alerts already exist. Current docs list project-level daily/weekly change alerts and org-level monthly totals, so the exact project-monthly status is unresolved.[^c4-2]
- Open (Billing Alerts and Budget Controls): Every source is MongoDB-owned; no independent (non-MongoDB) corroboration was verified. Third-party blogs (oneuptime) showed API event names PENDING_INVOICE_OVER_THRESHOLD and CREDIT_CARD_CURRENT_MONTH_USAGE_THRESHOLD_EXCEEDED, unverified against the Admin API reference.
- Open (Billing Alerts and Budget Controls): Only CREDIT_CARD_ABOUT_TO_EXPIRE was confirmed as a billing eventTypeName in the Admin API (via search snippet); full billing event-type list not read.
- Open (Billing Alerts and Budget Controls): Whether a project-level monthly billing alert exists (feedback threads conflict).
- Open (Billing Alerts and Budget Controls): Whether Atlas has any spend-cap feature beyond Flex ($30) in 2026; none found.
- Open (Atlas Credits Prepaid Subscriptions and Overage): Overage rate versus committed rate is not documented on public pages.
- Open (Atlas Credits Prepaid Subscriptions and Overage): Credit expiry rule at term end for Prepaid is not stated in the public docs; contracts may differ.
- Open (Atlas Credits Prepaid Subscriptions and Overage): Spanish docs page was the search-snippet source for ordering; English page confirmed it on fetch.
- Open (Atlas Credits Prepaid Subscriptions and Overage): Feedback-forum posts (alert 30 days before credits run out; Elastic Billing code labelled 'Atlas Prepaid Credits') surfaced only in search snippets; the fetched post URL returned 404, so unverified.
- Open (Atlas Credits Prepaid Subscriptions and Overage): Depth bar of 3 independent orgs unmet: only one non-MongoDB source, and it is low-value.
- Disagreement (Cloud Marketplace Billing for Atlas (AWS GCP Azure)): The AWS Marketplace listing text mentions recurring monthly usage fees through the AWS bill while showing a 12-month contract price; the schedule is unclear (and the listing is not Atlas PAYG).[^c6-6]
- Open (Cloud Marketplace Billing for Atlas (AWS GCP Azure)): Billing frequency for Azure and GCP Atlas Pay-as-You-Go is undocumented in fetched pages.
- Open (Cloud Marketplace Billing for Atlas (AWS GCP Azure)): Whether Atlas marketplace spend counts toward AWS EDP / Azure MACC / GCP commit: only consultancy marketing found, unverified and excluded.
- Open (Cloud Marketplace Billing for Atlas (AWS GCP Azure)): Whether one cloud billing account can link several Atlas organizations.
- Open (Cloud Marketplace Billing for Atlas (AWS GCP Azure)): Depth contract unmet: independent organisations limited to MongoDB plus one AWS listing for a different product; no third-party verification found.
- Disagreement (Atlas Support Plan Pricing): Enterprise first-response goal differs: docs say 15 minutes to 2 hours; the plans page says Enterprise 30 minutes and Platinum 15 minutes.[^c7-1][^c7-4]
- Disagreement (Atlas Support Plan Pricing): A forum user compared the ~20% Atlas support charge to ~3% at AWS/Google Cloud; staff defended it as deep database expertise but did not address the figure.[^c7-3]
- Open (Atlas Support Plan Pricing): Current (2026) Developer and Pro minimums and whether the 20% rate still holds; the only figures are from a Jan 2024 forum post.
- Open (Atlas Support Plan Pricing): Whether Pro uses the same greater-of-20% rule as Developer.
- Open (Atlas Support Plan Pricing): Whether the 20% base excludes taxes, credits or marketplace spend.
- Open (Atlas Support Plan Pricing): Pricing for Platinum and Enterprise is sales-negotiated.

## References

### Atlas Billing and Invoice Anatomy

[^c1-1]: https://www.mongodb.com/docs/atlas/billing/invoices — Manage Invoices (Atlas docs) (docs)
[^c1-2]: https://www.mongodb.com/docs/atlas/billing — Manage Billing (Atlas docs) (docs)
[^c1-3]: https://www.mongodb.com/docs/atlas/billing/invoice-breakdown/ — Atlas invoice breakdown (docs)
[^c1-4]: https://oneuptime.com/blog/post/2026-03-31-mongodb-atlas-billing-cost-management/markdown — How to Use Atlas Billing and Cost Management (OneUptime, 2026-03-31) (blog)
[^c1-5]: https://www.mongodb.com/community/forums/t/how-the-charge-for-mongodb-atlas-is-72hrs-per-day/139618 — How the charge for Atlas is 72hrs per day (MongoDB Community, 2022-01) (forum)
[^c1-6]: https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/operation/operation-getorginvoice — Atlas Admin API: Return One Invoice for One Organization (docs)

### Atlas Cost Explorer and Billing Data API

[^c2-1]: https://www.mongodb.com/docs/atlas/architecture/current/billing-data/ — Features for Atlas Billing Data (docs)
[^c2-2]: https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2.json — Atlas Admin API v2 OpenAPI spec (docs)
[^c2-3]: https://www.mongodb.com/docs/atlas/billing/focus-api/ — Atlas FOCUS Data API (docs)
[^c2-4]: https://www.mongodb.com/docs/atlas/reference/faq/billing/ — Atlas billing FAQ (docs)
[^c2-5]: https://mongodb.com/company/blog/product-release-announcements/view-analyze-your-monthly-mongodb-atlas-usage-cost-explorer — Cost Explorer announcement (2023, updated 2025-03-11) (blog)
[^c2-6]: https://www.mongodb.com/docs/atlas/cli/v1.55/command/atlas-api-invoices-createcostexplorerprocess/ — atlas api invoices createCostExplorerProcess (docs)
[^c2-7]: https://opencost.io/docs/integrations/plugins/mongo — OpenCost MongoDB Atlas plugin (docs)
[^c2-8]: https://www.doit.com/integrations/mongodb — DoiT MongoDB Atlas integration (docs)

### Resource Tags and Cost Allocation (Showback/Chargeback)

[^c3-1]: https://www.mongodb.com/docs/atlas/tags — Atlas Resource Tags (docs)
[^c3-2]: https://www.mongodb.com/docs/atlas/billing/invoices — Atlas Invoices: Resource Tags on Invoices (docs)
[^c3-3]: https://www.mongodb.com/docs/atlas/architecture/current/billing-data/ — Atlas Architecture Center: Billing Data (docs)
[^c3-4]: https://mongodb.com/blog/post/deployment-tags-billing-invoices-now-generally-available — Resource Tags in Billing Invoices GA (blog)
[^c3-5]: https://mongodb.com/blog/post/operating-at-scale-using-resource-tags — Operating at Scale Using Resource Tags (blog)
[^c3-6]: https://feedback.mongodb.com/ideas/CUSTOMER-I-10624 — Preserve Cluster Tags in Invoices After Cluster Deletion (forum)
[^c3-7]: https://www.finops.org/framework/capabilities/allocation — FinOps Framework: Allocation (docs)

### Billing Alerts and Budget Controls

[^c4-1]: https://www.mongodb.com/docs/atlas/configure-alerts.md — Atlas: Configure Alert Settings (docs)
[^c4-2]: https://www.mongodb.com/docs/atlas/reference/alert-conditions.md — Atlas: Alert Conditions (docs)
[^c4-3]: https://www.mongodb.com/docs/atlas/billing — Atlas: Billing (docs)
[^c4-4]: https://mongodb.com/community/forums/t/i-was-charged-2-60-when-using-m0-forever-free-tier/223141 — MongoDB Community: charged $2.60 on M0 (forum)
[^c4-5]: https://www.mongodb.com/docs/atlas/billing/atlas-flex-costs.md — Atlas Flex Costs (docs)

### Atlas Credits Prepaid Subscriptions and Overage

[^c5-1]: https://mongodb.com/docs/atlas/billing/subscriptions/ — Manage Subscriptions (docs)
[^c5-2]: https://mongodb.com/docs/atlas/billing/invoices — Atlas invoices (docs)
[^c5-3]: https://mongodb.com/blog/post/introducing-pay-as-you-go-mongodb-atlas-aws-marketplace — Introducing Pay as You Go MongoDB Atlas on AWS Marketplace (blog)
[^c5-4]: https://redresscompliance.com/mongodb-atlas-negotiation-landing — Redress Compliance MongoDB Atlas negotiation white paper (blog)

### Cloud Marketplace Billing for Atlas (AWS GCP Azure)

[^c6-1]: https://www.mongodb.com/docs/atlas/billing/gcp-self-serve-marketplace/ — Atlas GCP Self-Serve Marketplace (docs)
[^c6-2]: https://mongodb.com/docs/atlas/billing/aws-self-serve-marketplace — Atlas AWS Self-Serve Marketplace (docs)
[^c6-3]: https://mongodb.com/docs/atlas/billing/azure-self-serve-marketplace — Atlas Azure Self-Serve Marketplace (docs)
[^c6-4]: https://mongodb.com/docs/atlas/billing/subscriptions/ — Atlas Manage Subscriptions (docs)
[^c6-5]: https://mongodb.com/blog/post/introducing-pay-as-you-go-mongodb-atlas-aws-marketplace — Introducing Pay as You Go MongoDB Atlas on AWS Marketplace (blog)
[^c6-6]: https://aws.amazon.com/marketplace/pp/prodview-3oxgzxmuefzly — AWS Marketplace: MongoDB Enterprise Advanced GovCloud private offer (docs)

### Atlas Support Plan Pricing

[^c7-1]: https://www.mongodb.com/docs/atlas/support/ — Atlas Support docs (docs)
[^c7-2]: https://www.mongodb.com/docs/atlas/billing/additional-services/ — Atlas Additional Services billing (docs)
[^c7-3]: https://mongodb.com/community/forums/t/atlas-support-pricing/258990 — Atlas Support Pricing (MongoDB forum, staff reply) (forum)
[^c7-4]: https://mongodb.com/services/support/atlas-support-plans — Atlas support plans page (docs)
[^c7-5]: https://airbyte.com/data-engineering-resources/mongodb-pricing — Airbyte MongoDB pricing guide (blog)
