<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Created by deep research 2026-10-01.

---
name: mongodb-atlas-identity-policy-frontier-20261001
description: "Configure and troubleshoot Atlas API machine identities, human and workload database federation, and Cedar resource guardrails with explicit control-plane and data-plane boundaries. TRIGGER: Atlas service account OAuth tokens or rotation, workforce or workload OIDC setup, issuer audience group claims, and resource policy compliance or exceptions. SKIP: general database CRUD authorization, self-managed authentication, and encryption configuration."
version: "1.0.1"
updated: "2026-10-01"
category: "mongodb"
whenToUse:
  - "Configure Atlas service account tokens and secret rotation"
  - "Troubleshoot workforce or workload OIDC claims"
  - "Review Cedar resource policy compliance boundaries"
keywords: ["atlas", "service accounts", "oauth", "oidc", "workforce identity", "workload identity", "cedar", "resource policies", "secret rotation", "group claims", "audience", "nonCompliantResources"]
tags: ["mongodb", "atlas", "security", "iam", "federation", "oauth", "oidc", "cedar"]
provenance: "deep research 2026-10-01"
---

# Atlas Identity Federation and Resource Policy Boundaries

## Overview

Atlas service accounts are MongoDB's recommended machine identity for the Atlas Administration API, using the OAuth 2.0 client-credentials grant with Atlas acting as its own authorization server. A service account is a client ID plus rotatable secrets, belongs to one organization, and can hold org- or project-level roles. It trades credentials at POST /api/oauth/token for a 1-hour Bearer JWT. API keys (HTTP Digest) are now labelled legacy. Service accounts reach only the Admin API: no UI login, no cluster data access. Secrets carry mandatory expiry (8 hours to 365 days), are shown once, and rotation gives the old secret a 7-day grace window. IP access lists gate token use, not token creation. Terraform now lets creation omit the bootstrap secret to keep secrets out of state.

Workforce Identity Federation lets Atlas dedicated clusters (M10+, MongoDB 7.0.11+) authenticate human users through an external OIDC IdP (Entra ID, Okta, PingOne) using mongosh or Compass, via Authorization Code + PKCE or Device Authorization flows. Authorization maps either IdP group claims or a user claim to Atlas database roles. It is configured once per organization by an Organization Owner, and an org may link at most one OIDC IdP (database access) plus one SAML IdP (Atlas UI). Main operational hazards: oversized group claims (16 KiB preAuthMaximumMessageSizeBytes) and Entra's 200-group JWT overage. Provider-side overage behavior does not establish Atlas-side Graph lookup behavior.

Atlas Workload Identity Federation (WIF) lets applications authenticate to Atlas database clusters with short-lived OAuth 2.0/OIDC JWTs issued by an external IdP (Azure Entra ID managed identities and service principals, GCP service accounts, AWS-issued tokens, or any OIDC provider) instead of database passwords. MongoDB stores identifiers and privileges, not secrets. An org owner registers a Workload Identity Provider (issuer URI, audience, user/group claim) in Atlas Federation Management, links it to orgs, and creates federated database users. Requires M10+ dedicated clusters, MongoDB 7.0.11+, and driver support; mongosh and Compass are unsupported. MongoDB's architecture guidance lists WIF, AWS IAM and X.509 as workload authentication choices. It was announced May 2024 and reached GA June 2024.

Atlas Resource Policies are organization-level guardrails written in the open-source Cedar language. They are forbid-only and allow-by-default: they constrain what RBAC-authorized users may configure (cloud provider, region, IP access list, cluster size, TLS, maintenance window, CMK, auditing, VPC peering, private endpoints, Search/AI features) rather than granting access. Atlas evaluates RBAC first, then passes contextual attributes to a Cedar evaluator. Policies govern new and modified resources; existing resources are not automatically repaired, and existing auto-scaling settings may continue beyond new policy limits. Monitor the nonCompliantResources endpoint. Preview began Feb 2025, GA April 2025, and the current catalogue includes additional configuration constraints. Managed via UI, Admin API, Terraform, CloudFormation. They are a resource-configuration boundary, distinct from identity federation.

## Core Concepts

### Atlas Service Accounts OAuth 2.0

- Atlas service accounts authenticate via the OAuth 2.0 client-credentials flow: Basic-auth client ID:secret with grant_type=client_credentials sent to POST https://cloud.mongodb.com/api/oauth/token returns a Bearer JWT with expires_in 3600 (1 hour). Tokens are reusable within that hour and are replaced by requesting a new one before expiry (the access token cannot be refreshed).[^c1-1][^c1-2]
- MongoDB recommends service accounts over API keys for the Atlas Administration API and calls API keys (HTTP Digest, public/private key pair) a legacy method. Service accounts became generally available on 2025-04-02. verified-as-of: 2026-10-01[^c1-2][^c1-3]
- Service accounts (like API keys) grant access to the Atlas Administration API only: they cannot log into the Atlas UI and give no access to cluster data. Each belongs to a single organization and can be given org-level or project-level roles.[^c1-2][^c1-3]
- RFC 6749 section 4.4 describes client-credentials clients acting on their own behalf, requires client authentication, and says a refresh token SHOULD NOT be included. Separately, Atlas documents replacing its access token by requesting a new token rather than refreshing the existing access token. (two sources)[^c1-6][^c1-2]

### Atlas Workforce Identity Federation

- Workforce Identity Federation requires Atlas dedicated clusters (M10+) running MongoDB 7.0.11 or later. verified-as-of: 2026-10-01[^c2-1]
- An organization supports at most two Workforce IdPs: one OIDC IdP for database access and one SAML IdP for Atlas UI access; each org maps to one IdP per purpose, and Organization Owner is needed to configure. verified-as-of: 2026-10-01[^c2-1][^c2-2]
- Tentative: Authorization is either by group membership (groups claim, default 'groups') or by user ID (user claim, default 'sub'); on Entra ID groups arrive as Object IDs, and user claim can be upn or oid.[^c2-1]
- Tentative: Org mapping can assign a default org role to IdP-authenticated users (applies only if no role is mapped from their IdP group), restrict by approved domains, and requires prior domain mapping; mapping auto-creates an IdP certificate-expiry alert.[^c2-2]

### Atlas Workload Identity Federation

- Atlas WIF requires dedicated M10+ clusters running MongoDB 7.0.11 or later. verified-as-of: 2026-03-23[^c3-1][^c3-3]
- WIF was announced 2024-05-02 and became generally available 2024-06-05, initially with Java, C#, Node and Python drivers; current docs list Java 5.1+, .NET 2.25+, Go 1.17+, PyMongo 4.7+, Node 6.7+, Kotlin 5.1+, Rust 3.0+, Scala 5.1+. (two sources) verified-as-of: 2026-10-01[^c3-4][^c3-1]
- Workload Identity Federation authentication is supported by MongoDB drivers. The Atlas page states that mongosh and MongoDB Compass do not support this authentication mechanism. (two sources)[^c3-1][^c3-2]

### Atlas Resource Policies Cedar

- Atlas resource policies are written in Cedar and only the `forbid` effect is allowed (no `permit`); conditions use `when` / `unless`. With no policies, users can do everything their role allows.[^c4-1][^c4-4]
- Authorization is two-stage: Atlas RBAC first checks the user may perform the action, then contextual attributes (cloud provider, region, TLS version, etc.) go to the Cedar evaluator, which returns a binary decision. Policies therefore only narrow RBAC; they never widen it.[^c4-2][^c4-1]
- Policies are organization-level by default and apply to all projects and clusters; specific projects can be excluded from a policy. Viewing needs Organization Read Only or Member; create/update/delete needs Organization Owner. (two sources)[^c4-1][^c4-3]
- The MongoDB announcement dates public preview to 2025-02-10 and general availability to 2025-04-14. The current documentation describes dedicated-config-server, customer-managed-key and auditing constraints; their addition dates were not verified. (two sources) verified-as-of: 2026-10-01[^c4-3][^c4-1]

## Tools & Frameworks

- Tentative: The Terraform provider (PR #4735, opened 2026-09-16, closed 2026-09-18) made secret_expires_after_hours optional on service account creation; omitting it sends withoutInitialSecret=true, documented as the recommended flow so an org-owned bootstrap secret does not live in Terraform state. verified-as-of: 2026-09-18[^c1-5] _(Atlas Service Accounts OAuth 2.0)_
- Tentative: Supported flows are Authorization Code with PKCE (recommended) and Device Authorization (for browserless machines, mongosh --oidcFlows=device-auth); clients are mongosh 2.1.4+ and Compass 1.38+. Only JWT access tokens are accepted, not opaque tokens. verified-as-of: 2026-10-01[^c2-1] _(Atlas Workforce Identity Federation)_
- Tentative: Federated database users and groups can receive database roles, be temporary, and be restricted to selected clusters. Keep project/database authorization separate from organization-level IdP linkage; do not interpret org linkage as database access to every project. verified-as-of: 2026-10-01[^c2-1] _(Atlas Workforce Identity Federation)_
- Two client flows exist: built-in (driver fetches the token automatically on GCP Compute Engine/App Engine/Functions/Cloud Run/GKE/Cloud Build, Azure VMs/AKS, AWS EKS, and self-managed Kubernetes service accounts) and callback (application supplies a token callback, e.g. MSAL or client-credentials, for any OAuth 2.0 provider). (two sources) verified-as-of: 2026-10-01[^c3-1][^c3-2] _(Atlas Workload Identity Federation)_
- Policy actions are ResourcePolicy::Action values such as cluster.modify, project.ipAccessList.modify, project.maintenanceWindow.modify, project.vpcPeering.modify, project.privateEndpoint.modify, search.index.modify, search.deployment.modify, project.rerank.modify and project.aiModelAPI.modify; context attributes include context.cluster.cloudProviders, regions, minTLSVersion, diskSizeGB and context.project.ipAccessList. (two sources) verified-as-of: 2026-10-01[^c4-1][^c4-4] _(Atlas Resource Policies Cedar)_
- Policies can be managed through the Atlas Admin API, Terraform (mongodbatlas_resource_policy), CloudFormation and the Atlas UI, so Cedar files can be versioned in Git and code-reviewed.[^c4-3][^c4-4][^c4-2] _(Atlas Resource Policies Cedar)_

## Methodology

- Service account secrets must be given an expiry of 8 hours to 365 days, the full value is viewable only once at creation, and Atlas raises an alert 'Service Account Secrets are about to expire'. Rotation: generate new secret, update the app, revoke the old one. (two sources)[^c1-4][^c1-2] _(Atlas Service Accounts OAuth 2.0)_
- Tentative: JWKS revocation in Atlas is for compromised signing keys only, not routine rotation; update IdP keys first, then revoke, and clients must restart.[^c2-1] _(Atlas Workforce Identity Federation)_
- Atlas configuration of a Workload Identity Provider needs Issuer URI (resolved via /.well-known/openid-configuration), Audience, Authorization Type (User ID or Group Membership), User Claim (default sub, do not change) and a Groups Claim (default groups) when using group membership. Setup requires Organization Owner access, then linking the IdP to organizations and adding federated database users.[^c3-1][^c3-2] _(Atlas Workload Identity Federation)_
- Tentative: Google Cloud metadata servers can issue an ID token for an attached service account and an explicitly chosen target audience. This documents Google token acquisition only; Atlas compatibility and driver setup must be checked against MongoDB documentation.[^c3-6] _(Atlas Workload Identity Federation)_
- Tentative: OWASP recommends deny-by-default authorization and testing authorization checks. Atlas resource policies narrow existing RBAC permissions; their allow-by-default guardrail layer does not replace the underlying grant decision. Test allowed and denied configuration changes together.[^c4-6] _(Atlas Resource Policies Cedar)_

## Practical Patterns

- Tentative: When a new secret is created, the old secret's expiry is capped at 7 days (shortened if it was longer, kept if already sooner), giving a bounded overlap window for rotation.[^c1-4] _(Atlas Service Accounts OAuth 2.0)_
- Best practice: reuse a token for its hour rather than minting one per request, mint a replacement before expiry, and revoke tokens no longer needed via the Revoke Service Account Token endpoint. (two sources)[^c1-2][^c1-1] _(Atlas Service Accounts OAuth 2.0)_
- Tentative: OWASP recommends least-privilege access to secrets and supported or automated rotation. Apply this independent security guidance to Atlas client secrets; OWASP does not specify Atlas secret lifetimes or rotation overlap.[^c1-7] _(Atlas Service Accounts OAuth 2.0)_
- Workforce (human, mongosh/Compass) and Workload (application, driver-only) OIDC are separate IdP configurations; an Entra Workforce provider does not cover application data connections. [^c2-1] _(Atlas Workforce Identity Federation)_
- Tentative: Atlas documents Azure identities using the identity or group Object ID and GCP service accounts using their Unique ID. Configure the matching claim and database principal; do not substitute a display name.[^c3-1] _(Atlas Workload Identity Federation)_
- The Atlas Architecture Center lists Workload Identity Federation, AWS IAM and X.509 as workload authentication choices. It also lists X.509 or SCRAM as development/test choices. (two sources)[^c3-5][^c3-4] _(Atlas Workload Identity Federation)_
- Cedar's native model has both permit and forbid effects plus entities, scope and optional schema; Atlas exposes only the forbid subset, which is why Atlas policies cannot express allow-lists directly and use `unless` for allow-list-style constraints. (two sources)[^c4-5][^c4-4] _(Atlas Resource Policies Cedar)_

## Anti-Patterns

- Tentative: Managing a project-level service account that also has access to the organization or other projects (rotate/revoke its secrets) requires the Organization Owner role.[^c1-2] _(Atlas Service Accounts OAuth 2.0)_
- Tentative: Using '.*' as the groups-claim filter is discouraged: it pulls every group into the token and can push it past preAuthMaximumMessageSizeBytes (16 KiB default), causing auth failures; use a dedicated Atlas group naming prefix filter instead.[^c2-1] _(Atlas Workforce Identity Federation)_
- Tentative: Microsoft advises obtaining managed-identity tokens with its identity libraries and treating tokens as credentials: do not expose them in logs or send them to unrelated services. This is provider-side security guidance, not a statement that any arbitrary Microsoft token is valid for Atlas.[^c3-7] _(Atlas Workload Identity Federation)_
- Tentative: Gotchas: replica sets count as shard count 1, so a minimum shard count >1 can mark all replica sets non-compliant; converting replica set to sharded needs `&& !context.cluster.isConvertingToSharded`; private-endpoint policies need individual IPs (no wildcards); TLS/cipher-suite policies need Terraform provider 1.33.0+. verified-as-of: 2026-10-01[^c4-1] _(Atlas Resource Policies Cedar)_

## Troubleshooting

- Tentative: IP access lists apply to using a token, not to creating one: tokens can be minted from any IP but API calls with them are only accepted from listed IPs (403 access_denied on failure). Token requests are subject to API rate limits (429 with Retry-After).[^c1-1] _(Atlas Service Accounts OAuth 2.0)_
- Microsoft documents that more than 200 group memberships can produce an overage reference instead of group IDs in a JWT. Scope the groups claim to relevant groups and inspect the emitted claims. The retrieved Atlas documentation does not establish that Atlas calls Microsoft Graph to resolve overage or that failure is silent. (two sources) verified-as-of: 2026-01-15[^c2-3][^c2-1] _(Atlas Workforce Identity Federation)_
- Tentative: Entra ID setup needs scope <client-id>/.default, requestedAccessTokenVersion=2 in the app manifest, and 'Allow public client flows' for device auth; refresh tokens need the offline_access scope. verified-as-of: 2026-10-01[^c2-1] _(Atlas Workforce Identity Federation)_
- Tentative: For signing-key compromise, Atlas provides JWKS revocation. Follow the Atlas and IdP revocation procedure; ordinary key rotation and emergency revocation are different operations.[^c3-1] _(Atlas Workload Identity Federation)_
- Tentative: Atlas Resource Policies do not retroactively repair existing resources. Monitor /orgs/{ORG-ID}/nonCompliantResources. Existing auto-scaling limits may continue scaling beyond a newly added policy even when manual scaling beyond its limits is denied; policy compliance is not a continuous remediation guarantee.[^c4-1] _(Atlas Resource Policies Cedar)_

## Disagreements & Open Questions

- Open (Atlas Service Accounts OAuth 2.0): A search snippet (not confirmed on the fetched Atlas Service Limits page) cited limits of 200 service accounts/org, 200 access-list entries, 2 secrets and 100 active tokens per service account; unverified here.
- Open (Atlas Service Accounts OAuth 2.0): No API-key sunset date found; 'legacy' status is stated but no end-of-life timeline.
- Open (Atlas Workforce Identity Federation): Whether Atlas handles Entra group overage by calling Graph or just fails; docs do not say.
- Open (Atlas Workforce Identity Federation): Terraform registry page for federated_settings_identity_provider rendered empty; arg details unverified.
- Open (Atlas Workforce Identity Federation): Manual (self-managed) workforce landing page links to config pages not read; Enterprise-only 7.0.11+ noted but self-managed specifics unread.
- Disagreement (Atlas Workload Identity Federation): Server manual lists built-in Azure support only for Azure VMs, whereas Atlas docs also list AKS/Kubernetes; scope differs between pages.[^c3-2][^c3-1]
- Open (Atlas Workload Identity Federation): Search snippet claimed a 16 KiB preAuthMaximumMessageSizeBytes token size limit and Linux-only OIDC; the fetched pages did not confirm token-size, so omitted. Linux-only comes from the self-managed server manual.
- Open (Atlas Workload Identity Federation): No contradicting or overhyped-critique evidence found in the single negation round.
- Open (Atlas Workload Identity Federation): AWS outbound federation and sts:GetWebIdentityToken were not independently verified; treat them as a research frontier, not a supported setup recipe.
- Open (Atlas Workload Identity Federation): The workforce page explicitly rejects opaque tokens, but an equivalent workload-specific prohibition was not verified; no blanket opaque-token exclusion is asserted here.
- Open (Atlas Resource Policies Cedar): Whether project exclusions were added after GA or were always present.
- Open (Atlas Resource Policies Cedar): Exact policy-count and file-size limits (docs summary did not state them).
- Open (Atlas Resource Policies Cedar): Negation round found no critique/retraction of the headline claims; only scoping caveats (existing resources, forbid-only).

## References

### Atlas Service Accounts OAuth 2.0

[^c1-1]: https://www.mongodb.com/docs/atlas/api/service-accounts/generate-oauth2-token/ — Generate Service Account Token (docs)
[^c1-2]: https://www.mongodb.com/docs/atlas/api/api-authentication/ — Atlas Administration API Authentication Methods (docs)
[^c1-3]: https://www.mongodb.com/company/blog/product-release-announcements/introducing-mongodb-atlas-service-accounts-via-oauth-2-0 — Introducing MongoDB Atlas Service Accounts via OAuth 2.0 (blog)
[^c1-4]: https://www.mongodb.com/docs/atlas/tutorial/rotate-service-account-secrets/ — Rotate Service Account Secrets (docs)
[^c1-5]: https://github.com/mongodb/terraform-provider-mongodbatlas/pull/4735 — TF provider PR 4735: optional secret_expires_after_hours (repo)
[^c1-6]: https://datatracker.ietf.org/doc/html/rfc6749 — RFC 6749 The OAuth 2.0 Authorization Framework (paper)
[^c1-7]: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html — OWASP Secrets Management Cheat Sheet (docs)

### Atlas Workforce Identity Federation

[^c2-1]: https://www.mongodb.com/docs/atlas/workforce-oidc/ — Set up Workforce Identity Federation with OIDC - Atlas (docs)
[^c2-2]: https://www.mongodb.com/docs/atlas/security/manage-org-mapping/ — Manage Organization Mapping for Federated Authentication (docs)
[^c2-3]: https://learn.microsoft.com/en-us/troubleshoot/entra/entra-id/app-integration/get-signed-in-users-groups-in-access-token — Get Signed-in User Group List from a Group Overage Claim (docs)

### Atlas Workload Identity Federation

[^c3-1]: https://www.mongodb.com/docs/atlas/workload-oidc/ — Atlas Workload Identity Federation docs (docs)
[^c3-2]: https://www.mongodb.com/docs/manual/core/oidc/workload/ — Server manual: Workload Identity Federation (docs)
[^c3-3]: https://jimmydqv.com/m2m-outbound-federation-mongodb/ — AWS Outbound Identity Federation to Atlas (blog)
[^c3-4]: https://www.mongodb.com/blog/post/mongodb-introduces-workload-identity-federation-database-access — MongoDB introduces WIF (blog)
[^c3-5]: https://www.mongodb.com/docs/atlas/architecture/current/auth/authentication/ — Atlas Architecture Center: authentication (docs)
[^c3-6]: https://docs.cloud.google.com/docs/authentication/get-id-token — Google Cloud: Get an ID token (docs)
[^c3-7]: https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/overview-for-developers — Microsoft: Managed identities developer guidelines (docs)

### Atlas Resource Policies Cedar

[^c4-1]: https://www.mongodb.com/docs/atlas/atlas-resource-policies/ — Atlas Resource Policies - MongoDB Docs (docs)
[^c4-2]: https://aws.amazon.com/blogs/opensource/decoupling-authorization-at-scale-mongodb-atlas-and-cedar-based-resource-policies/ — Decoupling Authorization at Scale: MongoDB Atlas and Cedar-Based Resource Policies (blog)
[^c4-3]: https://www.mongodb.com/company/blog/7-new-resource-policies-strengthen-atlas-security — 7 New Resource Policies To Strengthen Atlas Security (blog)
[^c4-4]: https://foojay.io/today/enforcing-governance-in-mongodb-atlas-with-resource-policies/ — Enforcing Governance in MongoDB Atlas with Resource Policies (blog)
[^c4-5]: https://docs.cedarpolicy.com/overview/terminology.html — Cedar terminology (docs)
[^c4-6]: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html — OWASP Authorization Cheat Sheet (docs)
