<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-compliance` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-compliance
title: MongoDB Compliance and Regulatory
version: 1.1.0
updated: "2026-05-29"
category: mongodb
tags: [mongodb, atlas, compliance, fedramp, hipaa, pci, soc2, audit, encryption, gdpr, byok, rbac, data-residency, mfa, scim, csfle, queryable-encryption, atlasgovt]
description: >
  Expert reference for MongoDB Atlas compliance certifications, regulatory
  frameworks, audit-ready architecture, and the shared responsibility model.
  Covers SOC 2 Type II, ISO 27001, PCI DSS Level 1 (including v4.0 changes),
  HIPAA BAA, GDPR/DPA, FedRAMP Moderate and High (AtlasGov), data residency,
  encryption at rest (BYOK via AWS KMS/Azure Key Vault/GCP KMS), TLS enforcement,
  CSFLE and Queryable Encryption, Atlas RBAC and federated SSO/SCIM, audit logging
  configuration and forwarding, and common audit findings with remediation steps.

  TRIGGER: user asks about Atlas compliance certifications (SOC 2, HIPAA, PCI DSS,
  FedRAMP, GDPR, ISO 27001), HIPAA BAA, PCI CDE scoping, FedRAMP Moderate or High
  authorization, AtlasGov, BYOK key management, TLS enforcement, Atlas audit logging,
  RBAC least-privilege gaps, MFA enforcement, SCIM provisioning, data residency
  requirements, encryption at rest, or preparing audit evidence artifacts.

  SKIP: application-layer security code reviews (use security-reviewer); CSFLE/QE
  implementation details without compliance framing (use mongodb-encryption);
  network security architecture without Atlas compliance context (use
  mongodb-security-architecture); Okta integration without FedRAMP context
  (use okta-expert).

keywords:
  - mongodb compliance
  - atlas compliance
  - fedramp
  - fedramp high
  - atlasgovt
  - hipaa baa
  - pci dss
  - soc2 type ii
  - gdpr
  - byok
  - cmk
  - encryption at rest
  - audit logging
  - data residency
  - shared responsibility
  - csfle
  - queryable encryption
  - atlas rbac
  - custom roles
  - scim provisioning
  - tls enforcement
  - mfa atlas
  - pci v4.0

whenToUse:
  - "Which Atlas tier and configuration does our HIPAA deployment require?"
  - "Does our Atlas cluster satisfy FedRAMP Moderate or High requirements?"
  - "How do I set up BYOK with AWS KMS for an Atlas cluster?"
  - "What audit log events should I configure for a PCI DSS audit?"
  - "Preparing evidence artifacts for a SOC 2 or ISO 27001 audit"
  - "Atlas FedRAMP High — AtlasGov regions and US-only personnel requirements"
  - "Overprivileged Atlas database users — how do I remediate?"
  - "Do I need a MongoDB HIPAA BAA and how do I get one?"
  - "PCI CDE scoping — which Atlas clusters are in scope?"
  - "GDPR data residency — can I lock Atlas data to EU regions?"
  - "How do I enforce TLS 1.2 minimum on an Atlas cluster?"
  - "SCIM provisioning from Okta to Atlas for user lifecycle management"

whenNotToUse:
  - Application-layer security code review not involving Atlas config — use security-reviewer
  - CSFLE or Queryable Encryption implementation details without compliance framing — use mongodb-encryption
  - MongoDB network architecture (VPC, PrivateLink) without compliance context — use mongodb-security-architecture
  - Okta SAML/OIDC integration without FedRAMP or compliance framing — use okta-expert
  - Atlas RBAC configuration without a compliance audit driver — use mongodb-atlas-iam-rbac

related_skills:
  - mongodb-encryption
  - mongodb-security-architecture
  - mongodb-atlas-iam-rbac
  - okta-expert
  - mongodb-monitoring-observability
  - mongodb-atlas-expert
  - security-reviewer
---

# MongoDB Compliance and Regulatory

## How to Use This Skill

**Bring with you:**
- The applicable regulatory framework(s) (HIPAA, PCI DSS, FedRAMP, SOC 2, GDPR)
- Current Atlas cluster tier (M0/M10/M30+) and cloud provider/region
- Whether cardholder data (CHD) or electronic PHI (ePHI) is actually stored in Atlas
- Whether BYOK / customer-managed keys are already enabled
- Whether the Atlas Organization has MFA and federated SSO configured

**Expected outputs when using this skill:**
- Gap analysis against a specific framework
- Ordered remediation checklist
- Architecture recommendation (cluster tier, network isolation, encryption stack)
- Evidence artifact list for auditors

> **Scope note:** This skill is a lookup and advisory reference — it does **not**
> replace a QSA, legal counsel, or official MongoDB documentation. Configuration
> details vary by Atlas version; verify version-specific claims in current Atlas
> release notes. **Knowledge cutoff: August 2025.**

**Jump to Section 12** for a quick pre-audit finding checklist.
**Jump to Section 15** for a worked end-to-end HIPAA audit scenario.

---

## 1. Atlas Compliance Certifications Overview

MongoDB Atlas maintains a broad compliance portfolio. Certifications are issued
to MongoDB, Inc. as the cloud service provider — not the customer. Customers
inherit controls but must implement their own configuration layer.

| Certification | Scope | Renewal Cadence |
|---|---|---|
| SOC 2 Type II | Security, Availability, Confidentiality | Annual |
| ISO 27001 | Information Security Management | 3-year cert, annual surveillance |
| PCI DSS Level 1 | Cardholder data environment | Annual QSA assessment |
| HIPAA BAA | Covered entity / business associate | Perpetual (BAA is contractual) |
| GDPR | EU data protection | Ongoing (DPA required) |
| FedRAMP Moderate | US Federal workloads | Annual ConMon |
| FedRAMP High (Atlas for Gov) | High-impact federal | Annual ConMon |
| CSA STAR Level 2 | Cloud security assurance | Annual |
| IRAP (Australia) | Australian government | Periodic |

**Key principle:** Certification does **not** mean a customer's Atlas deployment
is compliant. The customer must configure Atlas correctly, use the right tier,
and satisfy their own controls.

Certification reports (SOC 2 Type II, PCI AOC) are available under NDA via
MongoDB Trust Center: `trust.mongodb.com`. Always request the latest report —
never rely on a report older than 12 months for audit purposes.

---

## 2. FedRAMP — Atlas for Government and GovCloud

### FedRAMP Moderate vs. High

- **FedRAMP Moderate** — Atlas on standard cloud infrastructure. Authorized for
  systems with Moderate impact level (most federal SaaS). Suitable for CUI
  (Controlled Unclassified Information) but not all categories.
- **FedRAMP High** — Atlas for Government (AtlasGov), deployed in AWS GovCloud
  (US) regions. Required for systems handling sensitive law enforcement,
  emergency services data, or financial/health data under certain agency rules.

### Atlas for Government (AtlasGov)

- Physically isolated control plane in GovCloud — no commingling with commercial
  Atlas control plane.
- Only US Persons operate the infrastructure (ITAR / EAR implications).
- Dedicated support queue with cleared personnel.
- Available regions: `us-gov-east-1`, `us-gov-west-1` (AWS GovCloud).
- **Not** available on Azure Government or GCP Government at GA as of knowledge
  cutoff — confirm with MongoDB Sales.

### FedRAMP Readiness Checklist (Pattern: Identity Provider Pursuing FedRAMP Authorization)

When a customer using Atlas as a backend is pursuing their own FedRAMP
authorization (Moderate or High), the following Atlas-layer checklist applies:

1. Confirm Atlas cluster region is GovCloud (`us-gov-east-1` or
   `us-gov-west-1`) for High impact; Moderate may allow commercial regions
   depending on the agency AO's acceptance.
2. Ensure the MongoDB Atlas FedRAMP Moderate P-ATO (or High ATO) is referenced
   in the customer's System Security Plan (SSP) as an inherited control.
3. Review MongoDB's Customer Responsibility Matrix (CRM) — the customer owns all
   application-layer controls.
4. Data encryption: FIPS 140-2 validated modules required. Atlas uses an OpenSSL
   FIPS module — verify the specific version is FIPS-validated with MongoDB
   before asserting compliance.
5. MFA: enforce MFA on all Atlas Organization users (Atlas UI and programmatic
   access via IP-allowlisted API keys).
6. Audit logging: must be enabled and shipped to a FedRAMP-authorized SIEM (e.g.,
   Splunk Cloud for Government, AWS CloudWatch in GovCloud).
7. Network: VPC Peering or AWS PrivateLink to GovCloud VPC. No public cluster
   endpoints allowed for High impact.
8. Penetration testing: Atlas undergoes annual pen tests as part of ConMon.
   Customers must run their own app-level pen tests and cannot rely solely on
   MongoDB's.

### FedRAMP ConMon (Continuous Monitoring)

MongoDB submits monthly vulnerability scans and deviation reports to the
JAB/agency AO. Customers should:
- Pull the ConMon package from FedRAMP Marketplace listings (when authorized).
- Track open Plan of Action & Milestones (POA&M) items — any open High or
  Critical POA&M on Atlas infrastructure must be documented in the customer's
  own risk register.

---

## 3. HIPAA — Business Associate Agreement and Configuration

### BAA Process

MongoDB offers a HIPAA BAA (Business Associate Agreement) on M10+ dedicated
clusters. Free and Shared tiers are explicitly excluded.

1. Contact MongoDB Sales or Account Management to request the BAA.
2. BAA is signed at the Organization level, not per-project.
3. Once executed, MongoDB acts as a Business Associate under HIPAA for PHI
   stored in Atlas.
4. BAA does **not** cover Atlas Data Lake, Atlas Search (if offloaded), or
   Charts unless explicitly scoped in the agreement.

### Configuration Requirements for HIPAA Workloads

- **Cluster tier:** M10+ dedicated (no shared infrastructure).
- **Encryption at rest:** Must be enabled. BYOK strongly recommended (see
  Section 8) with customer-managed keys in AWS KMS, Azure Key Vault, or GCP
  Cloud KMS.
- **TLS:** Enforce TLS 1.2 minimum. Disable TLS 1.0 and 1.1 (Atlas default
  since 4.0+, but verify via `minimumEnabledTlsProtocol` cluster setting).
- **Network isolation:** VPC Peering or PrivateLink. IP Access List should
  restrict to known application CIDRs only.
- **Audit logging:** Enable Atlas Audit Log with at minimum: `authenticate`,
  `createCollection`, `dropCollection`, `insert`, `update`, `delete`,
  `createIndex`, `dropIndex`, `createUser`, `dropUser`, `grantRolesToUser`,
  `revokeRolesFromUser`.
- **User access:** No shared database users. Individual users or service
  accounts with least-privilege roles. MFA on all Atlas portal users.
- **Backup:** Enable Cloud Backup (not Legacy Backup). Verify backup encryption
  uses the customer-managed key when BYOK is active.
- **Field-level encryption:** Strongly recommended for ePHI fields (SSN,
  diagnosis codes, medication records) using CSFLE or Queryable Encryption (see
  Section 7).

### HIPAA Breach Notification

HIPAA requires covered entities to notify affected individuals within 60
calendar days of **discovery** of a breach. The BAA with MongoDB specifies
MongoDB's obligation to notify the covered entity (customer) upon discovery of
a breach affecting PHI — review the BAA's notification window (often shorter
than 60 days) and incorporate it into the customer's incident response plan.
MongoDB does not file HHS notifications on the customer's behalf; that
obligation remains with the covered entity.

### What HIPAA Does Not Require (But Customers Often Assume)

HIPAA does not mandate a specific technology — it mandates safeguards. There is
no HIPAA "certification" for Atlas; compliance is assessed by auditors against
the HIPAA Security Rule, not against a MongoDB badge.

---

## 4. PCI DSS — Atlas PCI Scope, Tokenization, Isolation

### Atlas PCI DSS Level 1

MongoDB Atlas is a PCI DSS Level 1 Service Provider. The Attestation of
Compliance (AOC) is available via the MongoDB Trust Center under NDA.

**Critical scoping question:** Is cardholder data (CHD) actually stored in
Atlas, or only tokens/references? The answer determines whether Atlas clusters
are in scope for the CDE.

### Reducing Atlas PCI Scope via Tokenization

Best practice: never store PANs (Primary Account Numbers) in Atlas. Use a
payment processor (Stripe, Braintree, Adyen) to tokenize at ingestion. Atlas
stores only the token — a random opaque string with no mathematical relationship
to the PAN. This removes those Atlas collections from CDE scope.

If tokenization is not possible, the Atlas cluster(s) storing CHD are
**in-scope** for the customer's CDE (Cardholder Data Environment).

### In-Scope Atlas Configuration for PCI

- **Isolation:** Dedicated Atlas Project for CDE clusters. No mixing CDE and
  non-CDE workloads in the same project (see Finding 8 in Section 12).
- **Encryption at rest:** Required. BYOK strongly recommended for key custody
  control.
- **TLS 1.2+:** Required (PCI DSS v4.0 Requirement 4.2.1).
- **Audit logging:** All access to CHD collections must be logged. Ship logs to
  a PCI-compliant SIEM within scope.
- **Access control:** MFA required for all administrative access to CDE systems
  (PCI DSS v4.0 Requirement 8.4.2). This includes Atlas portal access.
- **Vulnerability management:** Subscribe to MongoDB Security Advisories. Apply
  patches within 1 month for critical vulnerabilities (PCI DSS v4.0
  Requirement 6.3.3).
- **Network:** No public endpoints on CDE clusters. PrivateLink or VPC Peering
  only. WAF in front of application layer.
- **Penetration testing:** Annual pen test required. MongoDB's pen test covers
  the service layer; customers must test their application and integration
  layers.

### PCI DSS v4.0 Changes Affecting Atlas Users (Effective March 2025)

- Requirement 6.4.1: Web-facing applications must have an automated technical
  solution (DAST or WAF) detecting and preventing web-based attacks.
- Requirement 8.4.2: MFA required for ALL access into the CDE — not just remote
  access.
- Requirement 12.3.2: Targeted risk analysis for all requirements using
  customized approach.

---

## 5. Data Residency — Region-Locked Deployments, EU Sovereignty, Multi-Region Restrictions

### Region Locking

Atlas allows selecting specific cloud regions for cluster deployment. Data at
rest never leaves the selected region(s) unless explicitly configured (e.g.,
multi-region cluster, Atlas Data Lake pointing to another region).

For strict data residency (EU, APAC, etc.):
- **Single-region cluster:** All nodes in one region. Recommended for strict
  residency.
- **Multi-region cluster:** Electable nodes can span regions. Verify that no
  electable node is placed outside the required jurisdiction.
- **Analytics nodes:** Can be placed in a separate region. If residency is
  strict, keep analytics nodes in the same jurisdiction.

### EU Data Residency and GDPR

- Available EU regions: Frankfurt (`eu-central-1`), Ireland (`eu-west-1`),
  Paris (`eu-west-3`), Stockholm (`eu-north-1`), London (`eu-west-2`) on AWS;
  West Europe (`westeurope`), North Europe (`northeurope`) on Azure; Frankfurt
  (`europe-west3`), Belgium (`europe-west1`) on GCP.
- **Atlas Data Processing Agreement (DPA):** Must be executed for GDPR
  compliance. Available in MongoDB Trust Center.
- **Standard Contractual Clauses (SCCs):** MongoDB includes EU SCCs in the DPA
  for cross-border data transfers. Verify the SCC module matches the transfer
  scenario (Controller-to-Processor for most Atlas use cases).
- **Atlas Search indexes:** Lucene indexes are stored in the same region as the
  cluster — verify if Search is enabled on a residency-sensitive cluster.
- **Atlas Data Federation:** Data Federation queries can pull from S3 buckets.
  If those buckets are in a different region or country, personal data may cross
  borders. Explicitly restrict Data Federation data sources to approved regions.

### EU Sovereignty Considerations

For highest sovereignty requirements (e.g., banking regulators in Germany,
France):
- Use single-region, single-cloud deployments.
- Disable MongoDB Atlas cross-region operational features (e.g., Global
  Clusters if not needed).
- Consider BYOK so encryption keys never leave the EU KMS region.
- **Control plane caveat:** Atlas control plane remains in MongoDB's US-based
  infrastructure — this is a common audit finding. Customers needing full
  data-plane and control-plane EU residency should document the control-plane
  exception in their risk register and note that configuration metadata (cluster
  settings, user names) flows through MongoDB's control plane.

---

## 6. Audit Logging — Configuration, Destinations, Analysis

### Enabling Atlas Audit Logging

Audit logging is available on M10+ dedicated clusters. Enabled per-project in
Atlas UI or via Atlas Admin API.

```jsonc
// Example Atlas Admin API audit log filter
// PUT /api/atlas/v2/groups/{groupId}/auditLog
{
  "auditFilter": "{\"atype\":{\"$in\":[\"authenticate\",\"authCheck\",\"createCollection\",\"dropCollection\",\"createDatabase\",\"dropDatabase\",\"insert\",\"update\",\"delete\",\"find\",\"createUser\",\"dropUser\",\"updateUser\",\"grantRolesToUser\",\"revokeRolesFromUser\",\"createIndex\",\"dropIndex\",\"logout\"]}}",
  "enabled": true
}
```

**Warning:** Logging `find`, `insert`, `update`, `delete` at full collection
scope generates very high log volume. Scope to specific collections/users where
possible. Use the `$filter` expression to target sensitive namespaces.

### Audit Log Destinations

Atlas audit logs are written to the cluster's `mongod` process log files.
Access options:

1. **Atlas UI:** Download compressed audit logs per node per day (manual; not
   suitable for production).
2. **Atlas Admin API**
   (`GET /api/atlas/v2/groups/{groupId}/clusters/{clusterName}/logs/{hostname}/{logName}`):
   Automate log retrieval.
3. **MongoDB Atlas Log Forwarding:** Stream logs directly to AWS S3, Azure Blob,
   or GCP Cloud Storage (configured at the Project level).
4. **Third-party SIEM:** Parse forwarded JSON logs in Splunk, Datadog, Elastic,
   or Sumo Logic. Atlas audit logs are JSON-formatted when forwarded — use a
   JSON ingest parser.

### Audit Log Schema Key Fields

```jsonc
{
  "atype": "find",             // action type
  "ts": { "$date": "..." },   // timestamp (UTC)
  "local": { "ip": "...", "port": 27017 },
  "remote": { "ip": "...", "port": 0 },
  "users": [{ "user": "appUser", "db": "admin" }],
  "roles": [{ "role": "readWrite", "db": "mydb" }],
  "param": {
    "ns": "mydb.sensitiveCollection",
    "filter": { "ssn": "..." }  // logged only if filter audit is enabled
  },
  "result": 0  // 0 = success; non-zero = MongoDB error code
}
```

### Audit Log Analysis Patterns

- **Failed authentication spike:** Alert on `atype: "authenticate"` with
  `result != 0` > N times in M minutes from the same IP.
- **Privilege escalation:** Alert on `grantRolesToUser` or `updateUser` where
  the role granted is `atlasAdmin` or `dbOwner`.
- **After-hours access:** Alert on `find`/`update`/`delete` on sensitive
  namespaces outside business hours.
- **Bulk delete:** Alert on `delete` where the result indicates > 1,000
  documents affected in a single operation.

---

## 7. Encryption Requirements

### Encryption at Rest

- Atlas encrypts all cluster storage at rest by default using AES-256 with
  cloud-provider managed keys.
- For compliance frameworks requiring customer key custody (HIPAA, FedRAMP,
  PCI DSS), enable **Encryption at Rest using Customer Key Management (BYOK)**
  — see Section 8 for setup.
- Backup snapshots are encrypted with the same key as the cluster. When BYOK is
  enabled, backups are encrypted with the CMK. If the CMK is rotated or
  revoked, old backups may become inaccessible — plan key rotation carefully and
  test recovery annually.

### Encryption in Transit

- Atlas enforces TLS for all client connections. The minimum TLS version is
  configurable per cluster.
- **Regulatory minimum:** TLS 1.2 (PCI DSS v4.0 Req 4.2.1, HIPAA addressable
  safeguard, FedRAMP SC-8 control).
- To enforce TLS 1.2+:
  - In Atlas UI: Cluster → Advanced Settings → Minimum TLS Protocol Version →
    TLS 1.2.
  - Via Terraform:
    `advanced_configuration.minimum_enabled_tls_protocol = "TLS1_2"`.
- Atlas peer connections (VPC Peering, PrivateLink) carry TLS — the underlying
  network transport is also encrypted.
- Internal cluster node-to-node communication (replication, elections) uses TLS
  in Atlas by default.

### Field-Level Encryption

Both options are client-side — the MongoDB server never sees plaintext for
encrypted fields:

**CSFLE (Client-Side Field Level Encryption)** — GA in MongoDB 4.2+:
- Encryption at the driver level before data leaves the application.
- Fields encrypted individually using a DEK (Data Encryption Key) stored in a
  KMS provider.
- Limitation: encrypted fields cannot be queried with range/inequality operators
  without decrypting first.

**Queryable Encryption (QE)** — GA in MongoDB 7.0+ (verify current driver
support in MongoDB release notes):
- Encrypted fields support equality queries without the server seeing plaintext.
- Range queries on encrypted fields: check current driver GA status before
  relying on this in production.
- Higher storage overhead than CSFLE due to metadata structures.

**Use case guidance:**

| Scenario | Recommendation |
|---|---|
| Store SSN, must query by SSN (equality) | Queryable Encryption |
| Store PAN, never query directly (tokenized) | CSFLE or omit field-level encryption |
| Store salary, must query by range | Queryable Encryption range (verify GA) |
| Store notes/free text, no query needed | CSFLE with random encryption algorithm |

---

## 8. Key Management — BYOK, Rotation Policies

### Supported KMS Providers

| Provider | Atlas Feature Name |
|---|---|
| AWS KMS | Customer Managed Keys via AWS KMS |
| Azure Key Vault | Customer Managed Keys via Azure Key Vault |
| GCP Cloud KMS | Customer Managed Keys via GCP Cloud KMS |
| HashiCorp Vault | Not natively supported — use envelope encryption pattern manually |

### How Atlas BYOK Works (Envelope Encryption)

1. Customer creates a CMK (Customer Master Key) in their KMS.
2. Atlas generates a per-cluster DEK (Data Encryption Key), encrypted by the
   CMK.
3. Atlas stores only the encrypted DEK — it never holds the plaintext CMK.
4. At cluster startup, Atlas calls the KMS to decrypt the DEK; the DEK then
   decrypts the data files.
5. If the CMK is revoked or deleted, the cluster cannot start and data is
   effectively locked.

### AWS KMS Configuration (IAM Role — Recommended)

Use IAM Role-based access rather than static access keys. The three-resource
Terraform pattern is: (1) create the Atlas cloud provider access setup to get
an AWS IAM role ARN to trust, (2) authorize that role, (3) configure encryption.

```hcl
# Step 1 — get the AWS IAM principal Atlas will assume
resource "mongodbatlas_cloud_provider_access_setup" "setup" {
  project_id    = var.project_id
  provider_name = "AWS"
}

# Step 2 — bind the customer IAM role to the Atlas principal
resource "mongodbatlas_cloud_provider_access_authorization" "auth" {
  project_id = mongodbatlas_cloud_provider_access_setup.setup.project_id
  role_id    = mongodbatlas_cloud_provider_access_setup.setup.role_id

  aws {
    # aws_iam_role must trust the atlas_aws_iam_assumed_role_arn from step 1
    iam_assumed_role_arn = aws_iam_role.atlas_kms_role.arn
  }
}

# Step 3 — enable encryption at rest with the customer CMK
resource "mongodbatlas_encryption_at_rest" "example" {
  project_id = var.project_id

  aws_kms_config {
    enabled                = true
    customer_master_key_id = aws_kms_key.atlas_cmk.id
    region                 = "US_EAST_1"
    # role_id comes from the authorization resource output
    role_id = mongodbatlas_cloud_provider_access_authorization.auth.role_id
  }
}
```

> **Note:** This snippet is illustrative. Refer to the
> [mongodbatlas Terraform provider docs](https://registry.terraform.io/providers/mongodb/mongodbatlas/latest/docs)
> for the current resource schema — attribute names change across provider
> versions.

**Do not** use `access_key_id` / `secret_access_key` in production — static
credentials cannot be rotated automatically and create an audit finding.

### Key Rotation Policies

- **AWS KMS:** Enable automatic key rotation (annual) for the CMK. AWS generates
  new backing material; the key ID stays the same — Atlas is not disrupted.
- **Azure Key Vault:** Set key expiration and rotation policy in Key Vault.
  Update the Atlas project settings with the new key version **before** the old
  one expires.
- **GCP Cloud KMS:** Enable automatic rotation. Same key ring, new key version.
- **DEK rotation:** After CMK rotation, trigger a DEK re-encryption in Atlas
  (Atlas API: `POST /api/atlas/v2/groups/{groupId}/encryptionAtRest` with
  updated key reference). This re-wraps the DEK with the new CMK material.

**Audit finding:** Many customers configure BYOK but never test key revocation
recovery or rotation procedures. Include this in the annual DR drill.

---

## 9. Access Control — RBAC, Custom Roles, Federation, MFA

### Atlas RBAC Layers

Atlas has two distinct access control layers — both must be configured:

1. **Atlas Organization/Project IAM** — controls who accesses the Atlas control
   plane (UI, API). Roles: Org Owner, Org Member, Project Owner, Project Data
   Access Admin, Project Read Only, etc.
2. **Database Access (MongoDB RBAC)** — controls what database users can
   read/write within clusters. Entirely separate from Atlas IAM.

### Built-in Database Roles (Least Privilege First)

| Role | Use Case |
|---|---|
| `read` | Read-only application users |
| `readWrite` | Standard application service accounts |
| `dbAdmin` | Schema/index management (no data read) |
| `atlasAdmin` | Break-glass only; never for service accounts |
| `backup` | Backup service accounts |

### Custom Roles

For fine-grained control, define custom roles scoped to specific collections:

```javascript
// Atlas Admin API: create custom role
// POST /api/atlas/v2/groups/{groupId}/customDBRoles
{
  "roleName": "hipaaReadPHI",
  "actions": [
    {
      "action": "FIND",
      "resources": [{ "db": "clinical", "collection": "patients" }]
    }
  ],
  "inheritedRoles": []
}
```

Custom roles can inherit built-in roles and restrict to specific collections —
use this to implement collection-level least privilege.

### LDAP / SCIM / OIDC Integration

- **Atlas LDAP Authentication:** Verifies database user credentials against an
  enterprise LDAP directory (AD, OpenLDAP). The user still needs a matching
  Atlas database user record; the password check is delegated to LDAP.
- **Atlas LDAP Authorization:** Maps database user roles to LDAP groups —
  distinct from Authentication. When both are enabled, role assignments are
  driven entirely by LDAP group membership, not Atlas-stored roles. Enable
  per-project; requires M10+.
- **Atlas Federated Authentication (SAML/OIDC):** SSO for Atlas portal (UI/API)
  access. Integrate with Okta, Azure AD, PingFederate via SAML 2.0 or OIDC.
  Identity providers are configured at the Organization level.
- **SCIM Provisioning:** Atlas supports SCIM 2.0 for automated user
  provisioning/deprovisioning from Okta or Azure AD. When a user is
  deprovisioned in the IdP, their Atlas organization access is revoked.
  Database users (LDAP-backed) are also cleaned up if LDAP Authorization is
  configured.

**Okta integration pattern:** Configure Atlas as a SAML application in Okta.
Map Okta groups to Atlas Organization roles. Enable SCIM for lifecycle
management. Verify that Atlas MFA is enforced even when SSO is used (Atlas can
require MFA at the organization level as a fallback for non-SSO paths).

### MFA Requirements

- Atlas enforces MFA at the organization level: Settings → Require
  Multi-Factor Authentication.
- Supported second factors: TOTP (Google Authenticator, Authy), SMS (not
  recommended for high-security contexts), WebAuthn/FIDO2.
- API Keys (programmatic access) cannot use MFA — scope them to minimum
  necessary IP allowlist and roles, and rotate on a fixed schedule (90-day
  maximum recommended; 60 days for PCI environments).
- Service accounts using X.509 certificate authentication bypass portal MFA by
  design — ensure the certificate issuance and revocation process is controlled
  and audited.

---

## 10. Compliance Gaps and Shared Responsibility Model

### What Atlas Does NOT Certify

- **SOC 1 / SSAE 18:** Not currently offered for Atlas (relevant for financial
  statement audits).
- **HITRUST CSF:** MongoDB does not hold HITRUST certification. Customers must
  obtain their own.
- **ISO 27701 (Privacy Information Management):** Not certified as of knowledge
  cutoff.
- **ITAR / EAR:** AtlasGov uses US Persons controls but is not explicitly
  ITAR-certified. Consult Legal before storing ITAR-controlled technical data.
- **CMMC (Cybersecurity Maturity Model Certification):** Not certified. FedRAMP
  Moderate is a prerequisite for CMMC Level 2 alignment but does not satisfy
  CMMC alone.

### Shared Responsibility Model

| Control Area | MongoDB Responsibility | Customer Responsibility |
|---|---|---|
| Physical security | Data center (AWS/Azure/GCP) | N/A |
| Host OS patching | MongoDB / cloud provider | N/A |
| MongoDB software patching | MongoDB (Atlas is managed) | N/A |
| Atlas cluster configuration | Secure defaults | Configure BYOK, TLS min version, audit logs, network isolation |
| Database user management | Provides RBAC mechanism | Create/manage DB users and roles |
| Application layer security | N/A | App code, API security, input validation |
| Data classification | N/A | Classify data stored; maintain data flow diagrams |
| Audit log analysis | Log delivery to destination | Ingest, alert, and investigate in SIEM |
| Incident response | Platform-level incidents | App-level incidents and breach notification |
| Backup testing | Backup infrastructure | Test restore procedures quarterly |

### Common Misunderstanding: "Atlas is certified = I'm certified"

Inheriting MongoDB's controls covers only the infrastructure layer. Auditors
will ask for:
- Customer's own risk assessment and risk register
- Customer's own access control documentation
- Evidence of annual penetration testing (customer application layer)
- Evidence of security awareness training for developers
- Data classification policy and data flow diagrams showing where CHD/PHI lives

---

## 11. Audit-Ready Architecture — Landing Zone Patterns, Evidence Collection

### Atlas Compliance Landing Zone Pattern

```
[Customer VPC / VNet / VPC-SC]
     │
     ├── PrivateLink / VPC Peering endpoint
     │        │
     │        └── Atlas Dedicated Cluster (M10+)
     │                 ├── Encryption at Rest (BYOK → customer KMS)
     │                 ├── TLS 1.2+ enforced
     │                 ├── Audit Logging enabled + scoped filter
     │                 └── Cloud Backup (encrypted, same CMK)
     │
     ├── Atlas Audit Log → Log Forwarding → S3 / Blob / GCS
     │        └── SIEM (Splunk / Elastic / Datadog) ingests & alerts
     │
     ├── Atlas Access → Federated SSO (e.g., Okta SAML) + MFA
     │        └── SCIM provisioning for user lifecycle
     │
     └── Atlas API Keys → Secrets Manager (AWS SM / HashiCorp Vault)
              └── Rotated every 60–90 days via automation
```

### Evidence Collection for Audits

Prepare these artifacts for annual compliance audits:

1. **Atlas SOC 2 Type II report** — download from Trust Center under NDA.
2. **Atlas PCI DSS AOC** — download from Trust Center (PCI audits).
3. **Atlas FedRAMP ATO package** — obtain from FedRAMP Marketplace.
4. **BYOK configuration** — Terraform state or Atlas UI screenshot proving CMK
   is customer-controlled.
5. **Audit log sample** — 30-day export showing sensitive collection access.
6. **Network diagram** — shows PrivateLink/VPC Peering, no public endpoints.
7. **Atlas project IAM export** — organization members, roles, MFA enforcement.
8. **Database user export** — least-privilege roles, no shared accounts.
9. **TLS configuration** — cluster settings showing minimum TLS 1.2.
10. **Backup policy** — backup schedule, retention, and test restore evidence.
11. **IP Access List** — restricted CIDR blocks, no `0.0.0.0/0`.
12. **Penetration test report** — customer-conducted, application layer.

### Attestation Reports Timeline

| Report Type | Trigger | Preparation Time |
|---|---|---|
| SOC 2 Type II | Annual (or customer audit request) | 2–4 weeks |
| PCI SAQ-D / ROC | Annual | 4–8 weeks with QSA |
| FedRAMP Annual Assessment | Annual (A&A cycle) | 8–12 weeks |
| HIPAA Risk Assessment | Annual (required by § 164.308(a)(1)) | 2–4 weeks |
| ISO 27001 Surveillance Audit | Annual | 1–2 weeks |

---

## 12. Common Audit Findings

### Finding 1: Overprivileged Database Users

**Description:** Service accounts with `atlasAdmin` or `readWriteAnyDatabase`
roles instead of scoped collection-level access.

**Remediation:**
- Audit: `db.getUsers()` on each cluster + Atlas project database users list.
- Replace broad roles with custom roles scoped to specific databases/collections.
- Immediately rotate credentials for any shared service account.

### Finding 2: Missing or Incomplete Audit Logs

**Description:** Audit logging not enabled, or configured to log only
authentication events — missing DML (insert/update/delete) on sensitive
collections.

**Remediation:**
- Enable audit logging on all M10+ clusters in scope.
- Add `insert`, `update`, `delete`, `find` to the audit filter for sensitive
  namespaces.
- Verify logs are flowing to the SIEM (alert on log gaps > 24 hours).

### Finding 3: No MFA on Atlas Portal

**Description:** Atlas organization does not require MFA. Developers access
Atlas UI with only username/password.

**Remediation:**
- Atlas Organization → Settings → Enable MFA requirement.
- If using SSO (e.g., Okta), ensure the IdP application policy requires MFA.
- Audit active organization members; remove users who no longer need access.

### Finding 4: Weak Password Policies for Database Users

**Description:** Database users with simple passwords, passwords never rotated,
or static credentials hardcoded in application config.

**Remediation:**
- Migrate to X.509 certificate authentication or LDAP where possible.
- For password-based users: enforce minimum 16-character random passwords, store
  in Secrets Manager, rotate every 90 days.
- Remove any database users with names like "test", "admin", "root", or
  "default" unless justified and documented.

### Finding 5: Public Cluster Endpoint

**Description:** Atlas cluster IP Access List contains `0.0.0.0/0` — cluster
is effectively reachable from the public internet.

**Remediation:**
- Immediately restrict to known application CIDRs.
- For production clusters: migrate to PrivateLink or VPC Peering and remove all
  public CIDR entries.
- Set up an Atlas alert for IP Access List modifications.

### Finding 6: No BYOK

**Description:** Atlas cluster relies solely on cloud-provider managed
encryption keys. For HIPAA, PCI DSS, and FedRAMP, customer-managed keys are
expected.

**Remediation:**
- Enable BYOK via Atlas Encryption at Rest settings.
- Create CMK in the appropriate KMS (same region as the cluster).
- Document and test the key rotation schedule annually.

### Finding 7: Backup Not Tested

**Description:** Cloud Backup is enabled but restores have never been tested.
Auditors require evidence of restore testing.

**Remediation:**
- Test point-in-time restore to a non-production cluster quarterly.
- Document restore time (RTO) and verify data integrity post-restore.
- Include backup restoration in the DR runbook.

### Finding 8: No Network Segmentation Between CDE and Non-CDE Workloads (PCI)

**Description:** PCI-scope clusters and non-scope clusters share the same Atlas
Project, network peering connections, and database users.

**Remediation:**
- Move CDE clusters to a dedicated Atlas Project with no shared network peering
  with non-CDE projects.
- Strictly limit Atlas project IAM access for the CDE project to personnel with
  a documented business need.

### Finding 9: Stale Atlas API Keys

**Description:** Atlas programmatic API keys created months or years ago, never
rotated, with overly broad IP allowlists or project roles.

**Remediation:**
- Audit: Organization → Access Manager → API Keys. Review last-used date.
- Delete unused keys immediately.
- Restrict active keys to the minimum necessary project role and CIDR range.
- Implement rotation automation (AWS Secrets Manager with rotation Lambda, or
  HashiCorp Vault dynamic secrets).

### Finding 10: No Atlas Alerts Configured

**Description:** No Atlas alerts configured for unusual activity — no
notification when database users are created, IP Access List changes, or
authentication failure spikes occur.

**Remediation:**
- Configure Atlas Alerts for: new database user created, IP Access List
  modified, Atlas project role granted, authentication failure spike, disk IOPS
  anomaly.
- Route alerts to PagerDuty, OpsGenie, or a dedicated compliance notification
  channel.

---

## 13. Quick Reference — Compliance Requirements vs. Atlas Configuration

| Compliance Need | Minimum Atlas Tier | BYOK | Audit Logs | Private Networking |
|---|---|---|---|---|
| HIPAA (ePHI) | M10+ | Strongly recommended | Required | Required |
| PCI DSS (CHD in scope) | M10+ | Strongly recommended | Required | Required |
| FedRAMP Moderate | M10+ | Required | Required | Required |
| FedRAMP High (AtlasGov) | M10+ GovCloud (M30+ recommended) | Required | Required | Required (PrivateLink) |
| SOC 2 Type II (inherit) | Any dedicated | Optional | Recommended | Recommended |
| GDPR (EU personal data) | Any | Optional | Recommended | Recommended |
| ISO 27001 (inherit) | Any | Optional | Recommended | Recommended |

*The FedRAMP High minimum tier is not a documented Atlas hard floor; M30+ is a
common recommendation for production High-impact workloads. Confirm with
MongoDB Sales.*

---

## 14. Worked Example — HIPAA Audit Readiness for a Clinical SaaS on Atlas

**Scenario:** A digital health startup stores ePHI (patient records, medication
history, appointment notes) in MongoDB Atlas M30 on AWS `us-east-1`. They are
undergoing their first HIPAA audit. The auditor has asked for evidence of
technical safeguards per 45 CFR § 164.312.

**Step 1 — Confirm BAA is in place**
- Verify a signed BAA exists with MongoDB at the Organization level.
- Confirm the BAA covers the specific Atlas project(s) storing ePHI.
- Artifact: countersigned BAA PDF.

**Step 2 — Encryption at rest**
- Check: Atlas UI → Cluster → Security → Encryption at Rest. Is BYOK enabled?
- If not: enable via AWS KMS (see Section 8). Create a dedicated CMK in
  `us-east-1`, restrict key policy to the Atlas IAM role only.
- Artifact: KMS key policy JSON + Atlas encryption settings screenshot.

**Step 3 — Encryption in transit**
- Check: Cluster → Advanced Settings → Minimum TLS Protocol Version = TLS 1.2.
- Verify application driver connection string uses `tls=true` and does not
  disable certificate validation.
- Artifact: cluster settings screenshot + redacted connection string.

**Step 4 — Audit logging**
- Check: Project → Security → Advanced → Database Auditing = Enabled.
- Verify audit filter covers at minimum: `authenticate`, `insert`, `update`,
  `delete`, `find`, `createUser`, `dropUser`, `grantRolesToUser`.
- Verify logs forward to a SIEM or S3 bucket with a 1-year retention policy.
- Artifact: audit filter JSON + log forwarding destination config + 30-day log
  sample showing ePHI collection access events.

**Step 5 — Access control**
- Run `db.getUsers()` on the `clinical` database. Confirm no service account
  has `atlasAdmin` or `readWriteAnyDatabase`.
- Confirm each service account has a custom role scoped to only the collections
  it needs (see Section 9).
- Confirm all Atlas portal users have MFA enabled.
- Artifact: database user list export + custom role definitions + MFA
  enforcement screenshot.

**Step 6 — Network isolation**
- Confirm no entry in IP Access List is `0.0.0.0/0`.
- Confirm cluster connects via VPC Peering or PrivateLink from the application
  VPC — no public endpoint reachability.
- Artifact: IP Access List export + VPC Peering / PrivateLink configuration
  screenshot.

**Step 7 — Backup and recovery**
- Confirm Cloud Backup is enabled with ≥ 7-day point-in-time retention.
- Confirm last successful restore test is documented (date, RTO, data integrity
  check result).
- Artifact: backup policy settings + restore test runbook entry with date stamp.

**Step 8 — Incident response**
- Confirm the organization's incident response plan references the MongoDB BAA
  notification clause and the 60-day HHS reporting window.
- Confirm Atlas Alerts are configured for authentication failure spikes and
  privilege changes, routing to the security team.
- Artifact: IRP excerpt + Atlas alert configuration screenshot.

**Gap summary table for this scenario:**

| Safeguard | Status | Evidence Artifact |
|---|---|---|
| BAA executed | Must verify | Signed BAA PDF |
| Encryption at rest (BYOK) | Must verify | KMS policy + Atlas screenshot |
| TLS 1.2+ | Must verify | Cluster settings screenshot |
| Audit logging (DML scope) | Must verify | Audit filter + 30-day log sample |
| Least-privilege DB users | Must verify | User export + custom role JSON |
| MFA on portal | Must verify | MFA enforcement screenshot |
| No public endpoint | Must verify | IP Access List + network diagram |
| Backup + tested restore | Must verify | Backup policy + restore record |
| IRP referencing BAA | Must verify | IRP document excerpt |

---

## 15. Useful Links and Resources

- MongoDB Trust Center: `https://www.mongodb.com/trust`
- Atlas FedRAMP Marketplace Listing: `https://marketplace.fedramp.gov` (search
  "MongoDB Atlas")
- Atlas Audit Log Documentation:
  `https://www.mongodb.com/docs/atlas/database-auditing/`
- Atlas Encryption at Rest (BYOK):
  `https://www.mongodb.com/docs/atlas/security-kms-encryption/`
- Atlas HIPAA FAQ: `https://www.mongodb.com/cloud/atlas/hipaa`
- Atlas PCI DSS FAQ: `https://www.mongodb.com/cloud/atlas/pci`
- MongoDB Security Advisories: `https://www.mongodb.com/alerts`
- Atlas Admin API Reference: `https://www.mongodb.com/docs/atlas/reference/api-resources-spec/`
