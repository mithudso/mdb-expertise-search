<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-iam-rbac` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-iam-rbac
title: MongoDB Atlas IAM and RBAC
version: "1.0.1"
updated: "2026-10-02"
description: MongoDB Atlas identity, access control, and federation across organization, project, and database layers. Covers the three-tier identity model, 30+ built-in roles (including the 15 purpose-built project roles), custom database roles, Atlas Service Accounts (OAuth 2.0, GA April 2025), programmatic API keys (legacy), workforce/workload identity federation (SAML and OIDC), AWS IAM database auth (MONGODB-AWS), X.509, LDAP (deprecated 8.0), SCRAM, Atlas Resource Policies (Cedar guardrails), database auditing and SIEM log push, activity feed, M0/Flex vs M10+ feature gating, and IdP group-to-role mapping. Use when designing Atlas identity architecture, debugging auth errors, migrating from API keys to service accounts, configuring federation, choosing among SCRAM/X.509/LDAP/IAM/OIDC for database access, or auditing access for SOC 2, SOX, HIPAA, or PCI compliance.
category: mongodb
tags:
  - mongodb
  - atlas
  - iam
  - rbac
  - security
  - federation
  - oauth
  - oidc
  - saml
  - compliance
keywords:
  - mongodb-atlas-iam-rbac
  - atlas iam
  - atlas rbac
  - atlas service accounts
  - atlas oauth 2.0
  - atlas api keys
  - atlas federated authentication
  - atlas workforce identity federation
  - atlas workload identity federation
  - atlas oidc
  - atlas saml
  - atlas okta
  - atlas entra id
  - atlas azure ad
  - atlas google workspace
  - atlas ping identity
  - atlas custom database roles
  - atlas database users
  - atlas aws iam authentication
  - mongodb-aws
  - irsa atlas
  - atlas x509
  - atlas ldap
  - atlas ldaps
  - atlas scram
  - atlas resource policies
  - cedar policy atlas
  - atlas database auditing
  - atlas audit logs
  - atlas activity feed
  - atlas log push
  - atlas siem datadog splunk
  - atlas org project database
  - atlas role mapping
  - atlas teams
  - atlas identity provider
  - atlas memberOf claim
  - atlas free tier auth
  - atlas m10 enterprise auth
when_to_use:
  - Designing or reviewing Atlas identity architecture (org/project/database tiers, role assignments)
  - Migrating from programmatic API keys to Service Accounts via OAuth 2.0
  - Configuring federated authentication (SAML or OIDC) with Okta, Entra ID, Google Workspace, or PingOne
  - Setting up Workload Identity Federation for applications on AWS/Azure/GCP/EKS/AKS/GKE
  - Choosing among SCRAM, X.509, LDAP, AWS IAM, or OIDC for database authentication
  - Defining custom database roles, privilege actions, or role inheritance
  - Debugging Atlas auth errors (401 Unauthorized, federation group mapping failures, IAM ARN mismatches)
  - Configuring Atlas Resource Policies (Cedar-based org-wide guardrails)
  - Enabling database auditing or activity feed forwarding to SIEM (Datadog, Splunk, S3, OTel)
  - Mapping Atlas controls to SOC 2, SOX, HIPAA, PCI DSS, GDPR, or FedRAMP requirements
---

# MongoDB Atlas IAM and RBAC

Atlas identity, access control, and federation across organization, project, and database layers. Updated May 2026. Covers GA features through April 2025: Service Accounts via OAuth 2.0, Resource Policies, 15 purpose-built project roles.

> Quick navigation: picking the right auth mechanism — section 17 (Decision Matrix). Migrating from API keys — section 6 (Service Account Migration). Debugging why a user has the role they have — section 18 (Role Resolution Precedence). Common auth errors — section 19 (Common Issues and Triage).

## When NOT to Use

- **CSFLE or Queryable Encryption implementation** — use [[mongodb-encryption]] for field-level encryption, key providers, and KMIP configuration
- **Self-managed MongoDB security** (mongod.conf, keyfile auth, TLS config, internal X.509 replica set auth) — use [[mongodb-security-architecture]]
- **Compliance framework deep-dives** (SOC 2 control evidence, PCI DSS cardholder data scope, HIPAA BAA requirements) — use [[mongodb-compliance]]
- **Azure-specific networking or Azure Key Vault CMK** — use [[mongodb-atlas-azure]]
- **GCP-specific networking or Cloud KMS CMK** — use [[mongodb-atlas-gcp]]

---

## 1. Three-Tier Identity Model

Atlas uses distinct organization, project, and database identity scopes, with explicit role inheritance from organization to project. Database users remain separate from Atlas users.

| Tier | Identity Type | Purpose | Authentication Methods | Permission Model |
| --- | --- | --- | --- | --- |
| **Organization** | Atlas user, service account, API key | Manage org settings, billing, projects, federation, resource policies | UI: federated auth (preferred) or Atlas creds + MFA. API: Service Account OAuth 2.0 or legacy API key Digest. | Organization roles |
| **Project** | Same identities, scoped per project | Manage clusters, network access, database users, backups within a project | Same as org tier | Project roles |
| **Database** | Database users (separate identities) | Connect to clusters and read/write data | SCRAM, X.509, LDAP, AWS IAM, Workforce OIDC, Workload OIDC | Database roles |

**Key implication**: an `Organization Owner` inherits `Project Owner` privileges across the organization's projects, including Atlas Data Explorer access, even when assigned a lower project role. The current [Atlas roles reference](https://www.mongodb.com/docs/atlas/reference/user-roles/#mongodb-authrole-Organization-Owner) documents that inheritance and database access. Do not claim that an Organization Owner has no access to cluster documents. Atlas users and database users are still separate identities: [database users](https://www.mongodb.com/docs/atlas/security-add-mongodb-users/) authenticate direct driver connections, while Atlas roles govern the Atlas application and Admin API. A Project Owner or Organization Owner can create database users, but the Atlas role itself is not a database login credential.

### Identity Hierarchy

```
Atlas Organization (top-level container — billing, federation, resource policies)
├── Organization Users / Service Accounts / API Keys
├── Organization Teams (groups of org users for bulk project assignment)
├── Resource Policies (Cedar-based guardrails — applied org-wide)
└── Projects (formerly "Groups" in API — networking + cluster isolation boundary)
    ├── Project Users / Service Accounts / API Keys (subset of org identities)
    ├── Project Teams (org teams added to this project with a project role)
    ├── Network Access Lists (IP allowlist + PrivateLink endpoints)
    ├── Custom Database Roles (defined per project)
    └── Clusters
        └── Database Users (separate authn — SCRAM/X.509/LDAP/IAM/OIDC)
            └── Database Roles + Custom Roles
```

### Project = "Group" in the API

The Atlas Admin API still uses the legacy term `groupId` in URL paths (`/api/atlas/v2/groups/{groupId}/...`). The UI and CLI call this a "project". Same thing. When you read documentation that says "group" in an API context, mentally substitute "project".

### Why projects exist

Projects are the **network isolation boundary**. Each project has its own VPC peering connections, PrivateLink endpoints, IP access list, and custom database roles. Best practice is one project per environment (dev/staging/prod) so that:

- A dev cluster cannot share network access list with prod
- Custom roles defined for prod don't leak into dev
- LDAP/federation configs are project-scoped where applicable
- Activity feeds remain scoped to actionable change windows

Up to 250 projects per organization is the hard limit but most orgs run far fewer.

---

## 2. Organization Roles (7 roles)

Organization roles control billing, project creation, federation, and org-wide settings. Default for new users is `Organization Member`.

| Role | API Name | What it can do |
| --- | --- | --- |
| **Organization Owner** | `ORG_OWNER` | Root. Manage all users/settings/billing/resource tags/federation. Implicit Project Owner on every project in the org. **Should be a service account, not a human.** Atlas requires at least 1 Org Owner — last-owner removal fails. |
| **Organization Project Creator** | `ORG_GROUP_CREATOR` | Create projects + Organization Member privileges. Useful for self-service platform teams. |
| **Organization Billing Admin** | `ORG_BILLING_ADMIN` | Manage payment methods, billing alerts, view invoices. + Organization Member. |
| **Organization Stream Processing Admin** | `ORG_STREAM_PROCESSING_ADMIN` | Project Stream Processing Owner on every project + manage private endpoints/VPC peering. + Organization Read Only. |
| **Organization Billing Viewer** | `ORG_BILLING_READ_ONLY` | View billing info. + Organization Member. |
| **Organization Read Only** | `ORG_READ_ONLY` | View-only on org settings, all users, all projects. Useful for auditors. |
| **Organization Member** | `ORG_MEMBER` | Default. View org name/users. Access only to **assigned projects** — actual cluster privileges come from the project role. |

**Key behavior**: `Organization Member` users do NOT see all projects automatically. They see only projects where they have been explicitly added (directly or via a team). `Organization Read Only` users DO see all projects (read-only).

**Anti-pattern**: granting `Organization Owner` to a developer. Use Project Owner on specific projects instead, or use teams. Org Owner should be:
- One break-glass human account
- One service account used during initial provisioning
- Optionally one IdP group for the security team

---

## 3. Project Roles (15 Purpose-Built Roles, GA 2024-2025)

Atlas expanded from 5 to 15+ project roles to enable least-privilege without granting `Project Owner`. Roles are purpose-built around platform responsibilities. All project roles inherit `Project Read Only`.

### Administrative

| Role | API Name | Permissions |
| --- | --- | --- |
| **Project Owner** | `GROUP_OWNER` | Full cluster management, project settings, IP access list, API keys, DB users, backups, Data Explorer, Charts, triggers, stream workspaces. Use sparingly for humans — prefer Project Cluster Manager + Database Access Admin. |
| **Project Access Manager** | `GROUP_ACCESS_MANAGER` | Invite users, manage teams, create/update API keys and service accounts within the project. The "delegate IAM admin" role. |

### Cluster Lifecycle (split intentionally)

| Role | API Name | Permissions |
| --- | --- | --- |
| **Project Cluster Creator** | `GROUP_CLUSTER_CREATOR` | Create clusters only. Cannot delete or modify existing clusters. |
| **Project Cluster Manager** | `GROUP_CLUSTER_MANAGER` | Edit, pause, resume clusters. Test failover. Cannot create. |
| **Project Replica Set Manager** | `GROUP_REPLICA_SET_MANAGER` | Edit global cluster config, zones, replication specs, tier; pause/resume; test resilience. |
| **Project Cluster Log Viewer** | `GROUP_CLUSTER_LOG_VIEWER` | View/download mongod, mongos, audit logs; view database access history. |
| **Project Cluster Resilience Tester** | `GROUP_CLUSTER_RESILIENCE_TESTER` | Trigger failover tests only. |

### Data Access (UI-only — does NOT grant database query access)

These roles control the **Atlas UI Data Explorer**. They do not create or grant database users. To actually query a cluster from an application, a separate database user is required.

| Role | API Name | UI Permissions |
| --- | --- | --- |
| **Project Data Access Admin** | `GROUP_DATA_ACCESS_ADMIN` | Full Data Explorer access; view/create/drop databases, collections, indexes; modify/delete documents via UI; retrieve logs; inherits Search Index Editor. |
| **Project Data Access Read/Write** | `GROUP_DATA_ACCESS_READ_WRITE` | Data Explorer R/W on documents; view indexes; view performance insights. |
| **Project Data Access Read Only** | `GROUP_DATA_ACCESS_READ_ONLY` | Data Explorer read-only. |
| **Project Database Access Admin** | `GROUP_DATABASE_ACCESS_ADMIN` | Manage database users and custom roles. Retrieve database access logs. This is the role that controls the data plane identities. |

### Backup / Recovery (split for least-privilege)

| Role | API Name | Permissions |
| --- | --- | --- |
| **Project Backup Manager** | `GROUP_BACKUP_MANAGER` | All backup operations: list, create, recover, export, policy. Inherits Creator + Recovery Operator + Export Operator. |
| **Project Backup Creator** | `GROUP_BACKUP_CREATOR` | List snapshots, create on-demand snapshots. |
| **Project Backup Recovery Operator** | `GROUP_BACKUP_RECOVERY_OPERATOR` | List snapshots, restore from backup. |
| **Project Backup Export Operator** | `GROUP_BACKUP_EXPORT_OPERATOR` | List snapshots, export/download backups. |

### Network & Security

| Role | API Name | Permissions |
| --- | --- | --- |
| **Project Network Access Manager** | `GROUP_NETWORK_ACCESS_MANAGER` | Manage IP access lists, VPC peering, PrivateLink. Cannot manage clusters or DB users. |
| **Project Support Access Manager** | `GROUP_SUPPORT_ACCESS_MANAGER` | Grant MongoDB support engineers access to clusters and logs (for case troubleshooting). |

### Observability / Performance

| Role | API Name | Permissions |
| --- | --- | --- |
| **Project Observability Viewer** | `GROUP_OBSERVABILITY_VIEWER` | Performance Advisor, Namespace Insights, Query Shape Insights, Query Profiler, Real-Time Performance Panel. |
| **Project Index Manager** | `GROUP_INDEX_MANAGER` | Performance Advisor + create rolling indexes. |
| **Project Real Time Performance Operator** | `GROUP_REAL_TIME_PERFORMANCE_OPERATOR` | Run `killOp` to terminate runaway operations. Useful for on-call. |

### Application Layer

| Role | API Name | Permissions |
| --- | --- | --- |
| **Project Search Index Editor** | `GROUP_SEARCH_INDEX_EDITOR` | Create/view/edit/delete Atlas Search indexes. |
| **Project Trigger Manager** | `GROUP_TRIGGER_MANAGER` | Create/update/delete database triggers (App Services). |
| **Project Alerts Manager** | `GROUP_ALERTS_MANAGER` | Create/view/update/delete alert settings and view active alerts. |
| **Project Stream Processing Owner** | `GROUP_STREAM_PROCESSING_OWNER` | Edit clusters; manage database access; access Data Explorer; manage stream processing workspaces and connection registry. |
| **Project Model Owner** | `GROUP_MODEL_OWNER` | Create/delete Model API keys (AI/embedding pipelines). |
| **Project Read Only** | `GROUP_READ_ONLY` | View metadata, users, roles, metrics. **No** Data Explorer, **no** logs. Inherited by every other project role. |

**Role assignment caveats**:
- Data Explorer access (`GROUP_DATA_ACCESS_*`) does not grant Atlas Admin API access to read or write documents. The API does not have a data-read surface — for that, you create a database user with database roles and connect via the driver.
- Project roles are additive. A user with `Cluster Manager` + `Network Access Manager` gets the union.
- Custom roles do not exist at the UI level — only at the database level (covered next).

---

## 4. Database Users and Database Roles

Database users are **separate identities** from Atlas users. They authenticate to the cluster (data plane), not to the Atlas API/UI (control plane). Even an `Organization Owner` who wants to run `db.collection.find()` must be added as a database user.

### Built-in database roles (subset most-used)

| Role | Database scope | Purpose |
| --- | --- | --- |
| `atlasAdmin` | admin (project-wide) | Full Atlas-flavored DB admin (DBA equivalent). Includes user management, custom roles, queries, indexes. |
| `readWriteAnyDatabase` | admin | R/W on every user database. Excludes `admin`, `local`, `config`. |
| `readAnyDatabase` | admin | R/O on every user database. |
| `dbAdminAnyDatabase` | admin | DDL ops (indexes, collMod, validate) on every database. |
| `clusterMonitor` | admin | Read replSet status, system.profile, currentOp. Used by monitoring agents. |
| `backup` / `restore` | admin | Used by backup tools — not relevant on Atlas since backups are managed. |
| `readWrite` / `read` | per-database | Standard application roles. Scope to the specific app database. |
| `dbAdmin` / `dbOwner` / `userAdmin` | per-database | Per-DB admin variants. `dbOwner` = readWrite + dbAdmin + userAdmin. |

Full list: see MongoDB Manual — Built-in Roles. Atlas does NOT support `__system`, `root`, or `clusterAdmin` from on-prem MongoDB.

### Adding a database user (authentication options)

Each database user must pick exactly one authentication method:

- **SCRAM-SHA-256** — username + password (default). Dev/test only per Atlas guidance.
- **AWS IAM** — IAM user ARN or IAM role ARN. Passwordless.
- **X.509 certificate** — Atlas-managed (Atlas generates cert) or self-managed (you upload CA).
- **LDAP** — LDAP user DN or group DN (deprecated MongoDB 8.0).
- **Federated Auth (OIDC)** — Workforce IdP user/group claim, or Workload IdP subject/group claim.

A single user can hold at most one auth method but can hold multiple database roles and custom roles (up to 20 custom roles per user).

### Temporary database users

Atlas can create time-bounded database users that auto-delete after a duration:
- 6 hours, 1 day, 1 week, or 1 month

Best practice for human ad-hoc access (developer debugging prod with a JIT credential). Audit each temp user separately. Use in conjunction with HashiCorp Vault or AWS Secrets Manager for dynamic credential generation in production.

---

## 5. Custom Database Roles

When built-in roles don't fit (e.g., read-only on most collections but write to one), create custom roles. Custom roles are project-scoped.

### Limits

| Constraint | Value |
| --- | --- |
| Max custom roles assignable to a single user | 20 |
| Max custom roles per project (default) | 100 |
| Max custom roles per project (API extended) | 1400 |
| Custom role propagation time (Free/Flex) | ~30 seconds |
| Required to create | Org Owner, Project Owner, or Project Database Access Admin |

### Privilege definition

Each privilege = `{ resource: <scope>, actions: [<action>, ...] }`. Resource scopes:

- **Global**: applies to all databases and the cluster
- **Database**: `{ db: "<name>", collection: "" }` or `{ db: "<name>", collection: "<name>" }`
- **Apply to any database**: `{ db: "", collection: "" }` — **dangerous**, includes `admin`/`local`/`config`/`__mdb_internal_`. Avoid writes here.

### Common privilege actions

| Category | Actions |
| --- | --- |
| Read | `find`, `listCollections`, `listIndexes`, `dbHash`, `dbStats`, `collStats` |
| Write | `insert`, `update`, `remove`, `bypassDocumentValidation` |
| DDL | `createCollection`, `createIndex`, `dropCollection`, `dropIndex`, `collMod`, `renameCollectionSameDB` |
| Sharding | `enableSharding`, `splitChunk`, `moveChunk` |
| Cluster ops | `killop`, `currentOp`, `inprog`, `setParameter` |
| Custom role mgmt | `createRole`, `dropRole`, `grantRole`, `revokeRole`, `viewRole` |
| Atlas-specific | `bypassDefaultMaxTimeMS`, `useTenant`, `clusterMonitorView` |

Full list: MongoDB Manual — Privilege Actions Reference. The Atlas custom-role surface is a **subset** — actions like `shutdown`, `applyOps`, `internal` are not available.

### Role inheritance and conflict resolution

A custom role can inherit from:
- Other custom roles (in the same project)
- Built-in database roles (`read`, `readWrite`, etc.)

When a user has multiple roles with overlapping permissions, **the union (highest privilege) wins**:

```
User has Role A: read on db.X + bypassDocumentValidation
User has Role B: dbAdmin on db.X
Effective: dbAdmin on db.X + bypassDocumentValidation
```

This is OR-logic, not AND. There is no "deny" privilege — you cannot subtract permissions. To restrict a role, do not grant the broader role in the first place.

### Restrictions

- Custom role name must not match a built-in role name, must not start with `xgen-`, and must not equal `atlasAdmin`.
- Cannot delete a custom role if removing it would leave a database user with zero roles, or leave a child role without any parent.
- "Apply to any database" implicitly includes system databases — never grant write actions there.

### Creating custom roles

```bash
# Atlas CLI
atlas customDbRoles create readOnlyExceptOrders \
  --inheritedRoles readWriteAnyDatabase \
  --privilege "find@db1.collection1,find@db1.collection2"

# Atlas Admin API
POST /api/atlas/v2/groups/{groupId}/customDBRoles/roles
{
  "roleName": "readOnlyExceptOrders",
  "inheritedRoles": [{ "role": "read", "db": "admin" }],
  "actions": [
    { "action": "find", "resources": [{ "db": "sales", "collection": "" }] }
  ]
}

# Terraform
resource "mongodbatlas_custom_db_role" "example" {
  project_id = var.project_id
  role_name  = "readOnlyExceptOrders"
  actions {
    action = "FIND"
    resources {
      database_name   = "sales"
      collection_name = ""
    }
  }
  inherited_roles {
    role_name     = "read"
    database_name = "admin"
  }
}
```

---

## 6. Atlas Service Accounts (OAuth 2.0) — GA April 2025

The modern replacement for programmatic API keys. Use service accounts for any new automation — Terraform, CI/CD, Kubernetes Operator, custom scripts.

### Core properties

| Attribute | Value |
| --- | --- |
| Auth protocol | OAuth 2.0 Client Credentials grant |
| Credential format | Client ID + Client Secret |
| Access token TTL | 3600 seconds (1 hour) — non-renewable, request a new one |
| Owning scope | One organization (just like API keys) |
| Project grants | Same identity can be granted org roles and/or project roles on multiple projects within its org |
| UI access | None — API only |
| Data access | None — Admin API only |
| Identity provider | MongoDB Atlas itself acts as IdP + authorization server |
| Lifecycle management | Atlas UI, Admin API, Atlas CLI (`atlas serviceAccounts`), Atlas Go SDK, Terraform provider 1.21+, Atlas Kubernetes Operator |

### OAuth flow

Token endpoint: `https://cloud.mongodb.com/api/oauth/token` (AtlasGov uses the equivalent `cloudgov.mongodb.com` host).

```
1. Request an access token:
   curl --user "<client_id>:<client_secret>" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -X POST https://cloud.mongodb.com/api/oauth/token \
     -d "grant_type=client_credentials"

2. Response:
   {
     "access_token": "<jwt>",
     "token_type": "Bearer",
     "expires_in": 3600,
     "scope": "..."
   }

3. Use token for subsequent API calls:
   curl https://cloud.mongodb.com/api/atlas/v2/groups \
     -H "Authorization: Bearer <jwt>" \
     -H "Accept: application/vnd.atlas.2024-11-13+json"

4. Revoke a token (optional, before expiry):
   curl --user "<client_id>:<client_secret>" \
     -X POST https://cloud.mongodb.com/api/oauth/revoke \
     -d "token=<jwt>"
```

### IP access list semantics

- IP access list applies to **token usage**, not token generation.
- You can request a token from any IP, but the request that uses the token must come from an allowlisted IP (if the access list is enabled).
- Token revocation is also IP-unrestricted.

### Secret rotation

Each service account can have up to 2 active secrets simultaneously. To rotate:
1. Create a second secret (now both active).
2. Update all consumers to use the new secret.
3. Delete the old secret.

This avoids downtime during rotation. The CLI command is `atlas serviceAccounts secrets create`.

### Role assignment

Service accounts get Atlas roles (org and project) the same way users do. A common pattern:
- One service account per environment (dev/staging/prod), each scoped to one project.
- Role: `GROUP_OWNER` for full IaC management, or narrower (e.g., `GROUP_DATABASE_ACCESS_ADMIN` + `GROUP_CLUSTER_MANAGER`) for least privilege.

### Service Account Migration

Migrating from programmatic API keys:

| Step | Action |
| --- | --- |
| 1. Inventory | List all API keys in org via `atlas accessLogs list` or Admin API. Map to consumers. |
| 2. Create service accounts | One per consumer (Terraform workspace, CI job, K8s operator deployment). Mirror the role assignments. |
| 3. Side-by-side | Run both auths in parallel for 1-2 weeks. Verify all consumers can authenticate via OAuth. |
| 4. Cut over | Update consumers to OAuth. Revoke old API keys. |
| 5. Monitor activity feed | Watch for failed authentications post-cutover. |

The Atlas Terraform Provider supports OAuth via `public_key` + `private_key` (legacy) **or** `client_id` + `client_secret`. The Atlas Kubernetes Operator supports both. The Atlas CLI uses service accounts natively via `atlas config init`.

---

## 7. Programmatic API Keys (Legacy)

Still supported but treat as legacy. New automation should use Service Accounts.

### Properties

| Attribute | Value |
| --- | --- |
| Auth protocol | HTTP Digest Authentication (nonce-based) |
| Credential format | Public Key + Private Key |
| Scope | Organization or project |
| Token | No bearer token — credentials hashed per request via Digest |
| UI access | None |

### Common pitfalls

- IP access list is **required** for API keys in new orgs created via the UI. Missing IP entries return a generic 401 that does not indicate the IP problem clearly.
- Curl flag must be `--digest -u "<pub>:<priv>"`, not basic auth.
- API keys cannot generate or rotate themselves via the API — must be done in the UI or by another key with appropriate role.

### Example

```bash
curl --digest --user "$ATLAS_PUB_KEY:$ATLAS_PRIV_KEY" \
  -H "Accept: application/vnd.atlas.2024-11-13+json" \
  "https://cloud.mongodb.com/api/atlas/v2/groups"
```

---

## 8. Workforce Identity Federation

Federation for **human users** signing into Atlas. Two protocols supported:

### SAML 2.0

The original Atlas federation protocol. Supported IdPs: Okta, Microsoft Entra ID (Azure AD), Google Workspace, PingOne, OneLogin, any SAML 2.0-compliant IdP.

### OIDC (announced June 2023, GA June 2024)

Newer protocol. Supported for both Atlas UI auth (workforce) and database auth (Workforce Identity Federation for database access — covered in next section).

### Federation Management

Configured once per organization, then applied to multiple Atlas projects:

```
Org Settings → Identity & Access → Federation → Open Federation Management App
  ├── Identity Providers (define IdP metadata)
  ├── Domains (verify ownership, map to IdP)
  ├── Organizations (connect federated orgs)
  └── Role Mappings (IdP group → Atlas role)
```

### Setup steps (high level)

1. **Verify domain ownership** — add a DNS TXT record at the email domain you want to federate (e.g., `acme.com`).
2. **Configure IdP** — upload IdP metadata XML (SAML) or OIDC discovery URL.
3. **Map domain to IdP** — `*@acme.com` users redirect to that IdP.
4. **Connect organization** — federation applies to all members of the org with matching email domain.
5. **Create role mappings** — IdP group `Engineering` → Atlas project role `Project Cluster Manager` on project X.

### Authentication flow

- **SP-initiated**: User visits `cloud.mongodb.com`, enters email, Atlas redirects to IdP, IdP authenticates, returns SAML/OIDC assertion, Atlas creates session.
- **IdP-initiated**: User clicks the Atlas tile in IdP dashboard. IdP sends SAML/OIDC assertion. User lands in Atlas.

When federation is enabled for a user's domain, **all other auth mechanisms are disabled** for that user. No password fallback in the Atlas UI. Atlas users with federated emails are forced through IdP.

### IdP group to role mapping (memberOf claim)

Atlas extracts the `memberOf` SAML attribute (or `groups` OIDC claim) and compares it to configured role mappings:

| IdP claim | Atlas action |
| --- | --- |
| `memberOf: ["acme-engineering"]` | Map to Org Member + Project Cluster Manager on project X |
| `memberOf: ["acme-billing"]` | Map to Org Billing Admin |
| User in multiple mapped groups | Atlas applies **union of all roles** |
| User removed from IdP group | On next login, Atlas removes the mapped role |

**Special case for Microsoft Entra ID**: when using "Group ID" as the source attribute, enter the group's **Object ID** (GUID) in Atlas, not the display name. This is a frequent source of "group mapping doesn't work" tickets.

### Org and project mapping limits

| Constraint | Value |
| --- | --- |
| Group name length | ≤ 200 characters |
| Mapping target | Org roles OR project roles (not teams — see below) |
| Default role when no mapping matches | Configurable; otherwise no roles applied |
| Last-Org-Owner protection | Cannot remove the last user with Org Owner |

### What federation does NOT support

- **Direct team assignment**: IdP groups cannot be mapped to Atlas teams. Map to project roles instead. This is intentional per MongoDB feedback responses — not planned.
- **Just-in-time provisioning of new orgs**: federation maps users into existing Atlas orgs only.
- **Skipping MFA at IdP level**: Atlas relies on the IdP for MFA. If MFA isn't enforced at IdP, federated users have no Atlas-level MFA. Atlas MFA is bypassed for federated logins.

### Restricted Employee Access mode

For sensitive deployments, enable "Restrict Support Access" to prevent MongoDB support engineers from accessing your cluster data even with case-driven access. This is separate from federation but often configured together.

---

## 9. Workload Identity Federation (Database Auth via OIDC)

For applications running in cloud environments — passwordless database access using cloud-issued OIDC tokens.

### Requirements

| Constraint | Value |
| --- | --- |
| Cluster tier | M10+ (dedicated only — no M0/Flex/Serverless) |
| MongoDB version | 7.0.11 or later |
| Driver support | Modern drivers only — Java 5.1+, .NET 2.25+, Go 1.17+, PyMongo 4.7+, Node.js 6.7+, Rust 3.2+ |
| Tools | NOT supported by mongosh or Compass for workload mode |

### Supported workload identity types

| Cloud | Identity type | Token source |
| --- | --- | --- |
| Azure | Managed Identity (system or user assigned), Service Principal | Azure Instance Metadata Service or AKS federated token file |
| GCP | Service Account | GCP metadata service or GKE service account token |
| AWS | (use AWS IAM mechanism — see next section, not OIDC) | — |
| Kubernetes (any) | Kubernetes Service Account | Projected token at `/var/run/secrets/kubernetes.io/serviceaccount/token` |

### Atlas configuration

**Workload IdP setup** (separate from workforce IdP):

```
Federation Management → Identity Providers → Set Up Identity Provider
  → Select "Workload Identity Provider"
  → Configuration:
      Configuration Name: "Azure-Prod-Workload"
      Issuer URI: https://login.microsoftonline.com/<tenant-id>/v2.0
      Audience: api://<application-id-uri>
      Authorization Type: User ID  | Group Membership
      User Claim: sub  (default)
      Groups Claim: groups  (only if Group Membership)
```

Then connect the workload IdP to the organization, just like the workforce IdP.

### Adding a database user with Workload IF

```
Database & Network Access → Add Database User
  Authentication Method: Federated Auth
  Identity Provider: <Workload IdP>
  Identifier: <Object ID for Azure | Unique ID for GCP Service Account>
  Roles: <built-in or custom DB roles>
```

**Critical**: the Identifier is NOT the display name. For Azure, it's the Object ID of the Service Principal or user group. For GCP, it's the Unique ID of the Service Account. Using display names silently fails authentication.

### Driver configuration examples

**Azure Managed Identity (Node.js)**:
```javascript
const client = new MongoClient(
  'mongodb+srv://cluster.mongodb.net/?authMechanism=MONGODB-OIDC',
  { authMechanismProperties: { ENVIRONMENT: 'azure', TOKEN_RESOURCE: 'api://<app-id-uri>' } }
);
```

**AKS (omit TOKEN_RESOURCE)**:
```javascript
const client = new MongoClient(
  'mongodb+srv://cluster.mongodb.net/?authMechanism=MONGODB-OIDC',
  { authMechanismProperties: { ENVIRONMENT: 'azure' } }
);
```

**GCP Service Account (Python)**:
```python
client = MongoClient(
  'mongodb+srv://cluster.mongodb.net/',
  authMechanism='MONGODB-OIDC',
  authMechanismProperties={'ENVIRONMENT': 'gcp', 'TOKEN_RESOURCE': '<custom-audience>'}
)
```

**Kubernetes service account (any)**:
The driver reads `/var/run/secrets/kubernetes.io/serviceaccount/token` automatically. Configure the audience to match what was set when configuring the Atlas Workload IdP.

### Group authorization

To authorize by group membership instead of individual identities:

1. Configure groups claim in IdP (Azure: token configuration → add groups claim with type "Security" and source "Group ID").
2. Atlas Workload IdP setting: Authorization Type = Group Membership, Groups Claim = `groups`.
3. Add a Database User with Identifier = Object ID of the IdP group.

All workload identities in that group inherit the roles assigned to the user.

### JWKS rotation

When tokens are issued, the driver caches the JWKS (signing keys). To force a rotation:
- Federation Management → Workload IdP → Manage → Revoke JWKS
- All connected clients should be restarted to pick up new keys

### Common errors

| Error | Cause |
| --- | --- |
| `Invalid audience` | TOKEN_RESOURCE doesn't match IdP Audience setting |
| `Token expired` | MongoDB version below 7.0.11, or JWKS not rotated after manual revocation |
| `Group not found` | Used display name instead of Object/Unique ID |
| `Auth mechanism not supported` | Driver too old, or cluster is M0/Flex |

---

## 10. AWS IAM Database Authentication

For applications running on AWS — use the IAM identity instead of OIDC. Native to AWS, predates Workload OIDC, and remains the recommended approach for AWS workloads.

### Supported AWS identities

| Identity | Use case |
| --- | --- |
| **IAM User** | Direct user-credentials access (rare in production — usually for developers via STS) |
| **IAM Role** | EC2, Lambda, ECS, EKS, AssumeRole flows (recommended) |

### Database user setup

```
Add Database User
  Authentication Method: AWS IAM
  Select: IAM User | IAM Role
  ARN: arn:aws:iam::123456789012:user/myUser  |  arn:aws:iam::123456789012:role/myRole
  Roles: <database roles>
```

### Driver/connection string

```
mongodb+srv://cluster.mongodb.net/?authMechanism=MONGODB-AWS&authSource=$external
```

The driver retrieves credentials from the standard AWS SDK chain (env vars → metadata service → STS). No username/password in the connection string when using IAM roles.

### Per-platform behavior

| Platform | Credential source |
| --- | --- |
| **EC2** | Instance Metadata Service (IMDSv2) at `169.254.169.254` |
| **Lambda** | Auto-populated env vars: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` |
| **ECS** | `169.254.170.2${AWS_CONTAINER_CREDENTIALS_RELATIVE_URI}` |
| **EKS / IRSA** | `AWS_WEB_IDENTITY_TOKEN_FILE` (path to projected token) + `AWS_ROLE_ARN`. AssumeRoleWithWebIdentity is invoked by the SDK. |
| **Fargate** | ECS task execution IAM role + container credentials endpoint |

### EKS IRSA example

```yaml
# ServiceAccount with IRSA annotation
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/my-atlas-role
---
# Pod uses that service account
spec:
  serviceAccountName: my-app
  containers:
    - name: app
      env:
        - name: MONGODB_URI
          value: "mongodb+srv://cluster.mongodb.net/?authMechanism=MONGODB-AWS&authSource=$external"
```

The IAM role's trust policy must allow the EKS OIDC provider, and the Atlas database user ARN must match the role ARN exactly (not the assumed-role session ARN).

### Limits and gotchas

| Constraint | Value |
| --- | --- |
| AWS STS rate limit | 600 requests/second per account per region (AWS default quota) |
| LDAP incompatibility | Cannot enable AWS IAM auth when LDAP authorization is enabled on the cluster |
| mongosh support | Requires mongosh v0.9.0+ |
| Cross-account roles | Supported — Atlas validates the ARN as-is |

### Choosing IAM vs Workload OIDC on AWS

- **IAM**: When the app already uses AWS SDK, IRSA is set up, and you want the simplest path. The default for AWS workloads.
- **Workload OIDC**: When you need a cross-cloud identity story (same auth mechanism on Azure/GCP/AWS) or you want to use a custom OIDC provider in front of AWS.

---

## 11. X.509 Certificate Authentication

Mutual TLS (mTLS) — clients present a cert, Atlas validates against CA, and the cert's Subject DN is the database user identity.

### Two flavors

| Type | CA | User certs | When to use |
| --- | --- | --- | --- |
| **Atlas-managed X.509** | Atlas internal CA | Atlas generates per-user cert (download once) | Quick start, no PKI infrastructure |
| **Self-managed X.509** | Your CA (upload PEM) | You issue and rotate certs | Existing PKI, compliance requires customer-controlled CA |

### Self-managed setup

1. **Upload CA**: Security → Database & Network Access → Advanced → Self-Managed X.509 → Upload PEM. Multiple CAs allowed in one PEM (concatenate).
2. **Add Database User**: Authentication Method = CERTIFICATE; enter the user's Subject DN exactly: `CN=appuser,O=AcmeCo,C=US`.
3. **Atlas auto-creates a project-level alert** 30 days before CA expiration, repeating daily until resolved.

### Subject DN format (RFC 4514)

Common attributes:
- `CN` — Common Name (required, 1-64 chars) — the database user identifier
- `O` — Organization
- `OU` — Organizational Unit
- `C` — Country (ISO 3166, 2 chars)
- `L` — Locality (City)
- `ST` — State/Province
- `DC` — Domain Component
- `emailAddress` — IA5String

Atlas matches the **entire Subject DN string** as the database user. If the cert says `CN=appuser,O=AcmeCo,C=US`, the database user must be registered with that exact DN string (order matters).

### Connection string

```
mongodb+srv://cluster.mongodb.net/?authMechanism=MONGODB-X509&authSource=$external
```

Driver also needs `tlsCertificateKeyFile=/path/to/cert.pem` (cert + private key concatenated).

### Limits

- Cannot use X.509 Atlas-managed with LDAP authorization enabled.
- Self-managed X.509 works with LDAP only if the cert's CN matches the LDAP user's DN exactly.
- The cert CN cannot equal another database user (across all auth methods).

---

## 12. LDAP / LDAPS

LDAP authentication and authorization via your own directory server. Atlas Enterprise feature. **Deprecated in MongoDB 8.0** — will be removed in a future major release. Migrate to Workforce/Workload OIDC.

### Properties

| Attribute | Value |
| --- | --- |
| Protocol | LDAPS only (TLS required, no plaintext LDAP) |
| Cluster tier | M10+ (no Free/Flex) |
| Scope | One LDAP config per project (applies to all clusters) |
| Network | VPC/VNet peering recommended; public LDAP IP is a risk because Atlas cluster public IPs rotate |
| MongoDB version | 7.0+ on Atlas |

### Setup

1. Configure LDAP server URL, port, bind user/password, CA cert (PEM).
2. Optionally enable **LDAP authorization** with a query template — `{USER}?memberOf?base` to retrieve group memberships.
3. Add database users:
    - Type "User" with the full DN: `cn=alice,cn=Users,dc=example,dc=com`
    - Or type "Group" with the group DN — all members get the assigned roles

### Connection string

```
mongodb+srv://cluster.mongodb.net/?authMechanism=PLAIN&authSource=$external
```

Username = full LDAP DN. Password = LDAP password.

### Restrictions

- Cannot mix LDAP + SCRAM for the same user.
- Cannot use OIDC when LDAP authorization is enabled.
- Atlas-managed X.509 incompatible with LDAP authorization.
- If a user is authenticated via LDAP but has no group memberships when authz is enabled, **all access is denied** (no default role).

### Why it's deprecated

OIDC + Workforce IF achieves the same SSO outcome with better security (no bind password to manage, no TLS cert rotation, tokens are short-lived) and works across cloud and on-prem IdPs. New deployments should not enable LDAP.

---

## 13. SCRAM-SHA-256

Default username + password authentication. Atlas guidance: **dev/test only**.

| Attribute | Value |
| --- | --- |
| Algorithm | SCRAM-SHA-256 (SHA-1 also supported for legacy clients) |
| Auth source | `admin` database (always) |
| Password storage | Salted, hashed server-side (5000 iteration default) |
| Atlas enforces password policy? | No — minimum length only |

### Production guidance

If using SCRAM in production despite Atlas guidance:
- Generate long random passwords (32+ chars) — use a secrets manager (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault).
- Rotate every 90 days at maximum.
- Use database username per-application, not shared.
- Never put SCRAM credentials in code, env vars logged to monitoring, or container images.

The HashiCorp Vault MongoDB Atlas secrets engine generates ephemeral SCRAM database users with TTL-based revocation:

```hcl
path "mongodbatlas/creds/myrole" {
  capabilities = ["read"]
}
```

Each read produces a fresh SCRAM user with a Vault lease; revocation deletes the database user.

---

## 14. Atlas Resource Policies (GA April 2025)

Cedar-based guardrails that enforce constraints across an entire Atlas organization. Public preview Feb 10, 2025. GA April 14, 2025. As of GA, **10 policies available**:

| Policy | Effect |
| --- | --- |
| Restrict cloud provider | Only allow clusters on approved providers (AWS, Azure, GCP) |
| Restrict cloud region | Limit deployments to specific regions per provider (data residency) |
| Block wildcard IP | Disallow `0.0.0.0/0` in IP access lists |
| Enforce Atlas cluster size limits | Set min/max tier (e.g., M30-M60) — cost control |
| Restrict IP access list modifications | Block new public IP entries (force PrivateLink/VPC peering) |
| Restrict VPC peering modifications | Freeze existing peering configs |
| Restrict private endpoint modifications | Freeze existing PrivateLink endpoints |
| Enforce minimum TLS version | Force modern TLS (e.g., TLS 1.2+) |
| Restrict TLS cipher suites | Whitelist specific ciphers |
| Require maintenance windows | All projects must have a maintenance window configured |

### Cedar syntax (sample)

```cedar
permit (
  principal,
  action,
  resource
)
when {
  resource.clusterSize >= "M30" && resource.clusterSize <= "M60"
};

forbid (
  principal,
  action == Action::"cluster:create",
  resource
)
when {
  !(resource.cloudProvider == "AWS")
};
```

### Behavior

- Policies apply **automatically** to all new resources in the org.
- Existing non-compliant resources can only be modified to bring them into compliance (e.g., an existing M70 cluster under a M30-M60 policy can only be modified to M60).
- Configured at org level by Org Owners. No per-project override (though specific projects can be exempted by name in the Cedar policy).
- Available via Atlas UI, Admin API, Terraform (`mongodbatlas_resource_policy`), CloudFormation.

### When to use

- Multi-team self-service Atlas with central security policy.
- Compliance: enforce data residency (region restrictions), cost guardrails (size limits).
- Defense in depth: block wildcard IP + require PrivateLink.

---

## 15. Database Auditing

Track data-plane events for compliance and forensics. M10+ feature.

### Enabling

```
Security → Database & Network Access → Advanced → Database Auditing: ON
```

Required role: Org Owner or Project Owner.

### Auditable actions (atype)

| Category | atype values |
| --- | --- |
| Authentication | `authenticate`, `authCheck` (read/write failures or successes), `createUser`, `dropUser`, `directAuthMutation`, `createRole`, `dropRole`, `grantRolesToUser`, `revokeRolesFromUser` |
| DDL | `createCollection`, `dropCollection`, `createIndex`, `dropIndex`, `renameCollection`, `createDatabase`, `dropDatabase` |
| Replication | `replSetReconfig`, `replSetSyncFrom` |
| Server-level | `shutdown`, `applicationMessage`, `clientMetadata` |
| Sharding | `addShard`, `removeShard`, `shardCollection` |

### Audit filter (JSON)

```json
// Audit all auth events
{ "atype": "authenticate" }

// Audit failed reads + writes
{
  "atype": "authCheck",
  "param.command": { "$in": ["find", "insert", "update", "delete"] }
}

// Audit user/role changes
{
  "atype": { "$in": ["createUser", "dropUser", "createRole", "dropRole", "grantRolesToUser"] }
}
```

**Performance warning**: Auditing all authorization successes (not just failures) on a high-QPS cluster has measurable CPU/IO cost. Default Atlas behavior is to audit only failures. Audit all only if compliance requires it, and benchmark first.

### Where audit logs live

- Audit logs written to disk on each replica node.
- Accessible via Atlas UI (Monitoring → Logs), Admin API (`GET /api/atlas/v2/groups/{groupId}/clusters/{clusterName}/logs`), Atlas CLI.

### Log push (SIEM forwarding)

Atlas can stream mongod, mongos, and audit logs to:
- **Datadog** — direct integration via API key
- **Splunk** — HTTP Event Collector (HEC)
- **AWS S3** — long-term retention; bring your own bucket
- **Azure Blob Storage** — same as S3
- **GCP Cloud Storage** — same
- **OpenTelemetry endpoint** — any OTel-compatible backend (Sumo Logic, New Relic, Elastic)

Enable via Atlas UI → Project Settings → Log Push. Logs are forwarded in near-real-time.

### Activity Feed (control-plane events)

Separate from database auditing. Tracks:

| Scope | Events |
| --- | --- |
| Organization | User logins, project create/delete, API key create/delete, billing changes, federation changes, resource policy changes |
| Project | Cluster lifecycle (create/update/pause/delete), database user changes, IP access list changes, alert config changes, custom role changes, backup operations |

Query via Admin API:
```
GET /api/atlas/v2/orgs/{orgId}/events
GET /api/atlas/v2/groups/{groupId}/events
```

Filter by event type, date range. Commonly polled by SIEM integrations.

### Audit best practices

- Audit user/role/auth changes always — these are governance-critical.
- Audit failed authCheck always — captures attack attempts.
- Audit data reads only if regulated (HIPAA PHI access, PCI cardholder data).
- Export both audit logs and activity feed events to SIEM. They cover different layers.

---

## 16. M0 / Flex / M10+ Feature Gating

Not every auth feature is available on every cluster tier. Be explicit about tier when designing.

| Feature | M0 (Free) | Flex | M10+ Dedicated |
| --- | --- | --- | --- |
| SCRAM | Yes | Yes | Yes |
| Atlas-managed X.509 | Yes | Yes | Yes |
| Self-managed X.509 | No | No | Yes |
| AWS IAM auth | No | No | Yes |
| Workforce OIDC (DB) | No | No | Yes (7.0.11+) |
| Workload OIDC (DB) | No | No | Yes (7.0.11+) |
| LDAP | No | No | Yes (Enterprise feature, deprecated 8.0) |
| Database Auditing | No | No | Yes |
| Log Push (SIEM) | No | Limited | Yes |
| PrivateLink | No | No | Yes |
| VPC Peering | No | No | Yes |
| Custom Database Roles | Yes (slow propagation) | Yes | Yes |
| Resource Policies | Apply org-wide regardless of tier | | |

**Implication**: dev clusters on M0 cannot test the same auth path that production will use. Use Flex or a small M10 for federation testing. Avoid promising M0 deployments to customers who need to validate enterprise auth.

---

## 17. Decision Matrix

| Identity | Resource | Production recommendation | Acceptable in dev/test |
| --- | --- | --- | --- |
| Human user | Atlas UI | Federated SAML or OIDC + MFA at IdP | Atlas creds + MFA |
| Human user | Database | Workforce OIDC (Compass/mongosh) | Temporary SCRAM users with short TTL |
| Application on AWS | Database | AWS IAM role (IRSA on EKS, instance profile elsewhere) | Same as prod, or SCRAM for unit tests |
| Application on Azure | Database | Workload OIDC with Managed Identity | Same |
| Application on GCP | Database | Workload OIDC with Service Account | Same |
| Application on-prem / multi-cloud | Database | Workload OIDC with internal OIDC IdP (Keycloak, Auth0) | X.509 with self-managed PKI |
| Automation / CI / IaC | Atlas Admin API | Service Account (OAuth 2.0) | API key (legacy) for existing tooling |
| Cluster monitor / agent | Database | SCRAM with `clusterMonitor` role only | Same |

### Authentication mechanism connection string cheat sheet

| Auth | authMechanism | authSource |
| --- | --- | --- |
| SCRAM-SHA-256 | (default; omit or `SCRAM-SHA-256`) | `admin` |
| X.509 | `MONGODB-X509` | `$external` |
| LDAP | `PLAIN` | `$external` |
| AWS IAM | `MONGODB-AWS` | `$external` |
| OIDC (workforce or workload) | `MONGODB-OIDC` | `$external` |

---

## 18. Role Resolution Precedence

When a user has roles from multiple sources, the final permission set is calculated as follows.

### Atlas (control plane)

1. Start with role from direct user/team assignment in the org.
2. Add role from any IdP group mapping (if federated).
3. Add role from any team that the user belongs to that has been added to the project.
4. Take the **union** of all applicable roles.

There is no role precedence — Atlas does not have a deny mechanism. To restrict, simply do not grant the broader role.

### Database (data plane)

1. Start with all built-in roles assigned to the database user.
2. Add all custom roles assigned.
3. Recursively expand inherited roles.
4. Take the **union** of all actions on all resources.

Conflict example:

```
User has:
  Built-in: read on db.sales
  Custom: readWrite on db.* (with sales-specific bypass)

Effective: readWrite on db.sales (highest wins per resource)
```

### Service Accounts vs API Keys vs Database Users

These are three completely separate identity pools. A user named `alice` could exist as:
- An Atlas user (control plane, federated)
- A database user (data plane, SCRAM or X.509)
- A service account (no concept of name — just clientId)

They share nothing — no automatic mapping. The same human/system is typically all three with the same logical name for human clarity, but Atlas treats them as different principals.

---

## 19. Common Issues and Triage

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `401 Unauthorized` from API call | API key not in org, IP not on allowlist, or wrong digest auth | Check `curl --digest`, IP allowlist, key has not been revoked |
| Service account token works once then fails | Token expired (1h TTL) | Re-request token; tokens are NOT refreshable |
| Federated user gets default role only | IdP group not mapped, or memberOf claim missing | Check Federation Management role mappings, IdP attribute mapping |
| Federated user gets logged out unexpectedly | IdP session timeout shorter than Atlas session | Tune IdP session; Atlas inherits IdP duration |
| `Authentication failed` on `MONGODB-AWS` | IAM role ARN in DB user doesn't match runtime role | Compare actual ARN from `aws sts get-caller-identity` to DB user |
| OIDC fails with "Invalid audience" | TOKEN_RESOURCE in driver doesn't match IdP audience | Match exactly; case-sensitive |
| Group authorization with Azure fails silently | Used display name instead of Object ID | Replace with Object ID GUID |
| Custom role assigned but user can't query | Role propagation lag on Free/Flex (~30s) or stale connection | Wait, reconnect, or upgrade cluster |
| LDAP user gets denied with no group memberships | LDAP authorization on + user has empty `memberOf` | Add user to a mapped LDAP group, or disable authorization |
| Can't enable AWS IAM auth | LDAP authorization already enabled on cluster | Move cluster to a different project or disable LDAP |
| Workload OIDC fails on mongosh | mongosh doesn't support Workload OIDC | Use a driver application or Workforce OIDC instead |

### Diagnostic queries (control plane)

```bash
# List all org users + roles
atlas users list --orgId <orgId>

# Show all roles for a user
atlas users describe <userId> --orgId <orgId>

# Audit activity feed for recent role changes
curl -H "Authorization: Bearer $TOKEN" \
  "https://cloud.mongodb.com/api/atlas/v2/orgs/$ORG_ID/events?eventType=USER_ROLE_CHANGED"

# List all DB users in a project
atlas dbusers list --projectId <projectId>

# Inspect a DB user
atlas dbusers describe --username "appuser" --projectId <projectId>
```

### Diagnostic queries (data plane)

```javascript
// Inside mongosh connected to admin
db.runCommand({ connectionStatus: 1, showPrivileges: true })
// Returns authenticated user, roles, and effective privileges

db.runCommand({ usersInfo: 1, showPrivileges: true })
// Lists all users on this database with their privileges
```

---

## 20. Compliance Alignment

IAM/RBAC controls are central to most security frameworks. Quick mapping:

| Framework | Control area | Atlas mechanism |
| --- | --- | --- |
| **SOC 2 (CC6.1, CC6.2, CC6.3)** | Logical access controls | Federated auth + MFA, Service Accounts, least-privilege project roles, custom DB roles |
| **SOC 2 (CC7.2)** | Detection of unauthorized changes | Activity feed + database audit logs forwarded to SIEM |
| **SOX (ITGC)** | Privileged access review | Quarterly review of Org Owner, Project Owner, atlasAdmin DB users via Admin API |
| **HIPAA (164.312(a))** | Access control | Workforce/Workload OIDC, audit logs, BAA required |
| **HIPAA (164.312(b))** | Audit controls | Database auditing enabled with PHI-collection coverage; log retention per policy |
| **PCI DSS (8.x)** | Authentication and identification | No shared accounts (Service Accounts per consumer), MFA via IdP, password rotation if SCRAM used |
| **PCI DSS (10.x)** | Logging and monitoring | Audit logs + activity feed forwarded to SIEM with 90+ day retention |
| **GDPR / data residency** | Geographic restrictions | Resource Policy: Restrict cloud region |
| **ISO 27001 (A.9)** | Access control | Same as SOC 2 |
| **FedRAMP / AtlasGov** | All of the above + dedicated tenancy | Use Atlas for Government (FedRAMP Moderate) |

See the `mongodb-compliance` skill for detailed compliance posture guidance.

---

## 21. References

- [Atlas Authorization and Authentication Guidance](https://www.mongodb.com/docs/atlas/architecture/current/auth/) — Architecture Center
- [Atlas Admin API Authentication Methods](https://www.mongodb.com/docs/atlas/api/api-authentication/) — Service Accounts vs API keys
- [Atlas User Roles Reference](https://www.mongodb.com/docs/atlas/reference/user-roles/) — Full role table
- [Configure Database Users](https://www.mongodb.com/docs/atlas/security-add-mongodb-users/) — Atlas users and database users are distinct; direct database connections use database users
- [15 New Purpose-Built Project Roles](https://www.mongodb.com/products/updates/15-new-purpose-built-project-roles-for-mongodb-atlas/) — Role expansion announcement
- [Configure Custom Database Roles](https://www.mongodb.com/docs/atlas/security-add-mongodb-roles/) — Privilege actions, role inheritance
- [Service Accounts via OAuth 2.0](https://www.mongodb.com/company/blog/product-release-announcements/introducing-mongodb-atlas-service-accounts-via-oauth-2-0) — GA blog post
- [Service Accounts Overview](https://www.mongodb.com/docs/atlas/api/service-accounts-overview/) — Token endpoints, lifecycle
- [Configure Federated Authentication](https://www.mongodb.com/docs/atlas/security/federated-authentication/) — SAML/OIDC workforce
- [Set up Workload Identity Federation](https://www.mongodb.com/docs/atlas/workload-oidc/) — Azure / GCP / K8s OIDC for DB
- [Workforce Identity Federation with OIDC for Database](https://www.mongodb.com/blog/post/introduces-workforce-identity-federation-openid-connect-support-database-access) — Human DB auth via OIDC
- [Configure Federated Auth from Okta](https://www.mongodb.com/docs/atlas/security/federated-auth-okta/) — Okta SAML setup
- [Manage IdP Role Mapping](https://www.mongodb.com/docs/atlas/security/manage-role-mapping/) — memberOf claim
- [AWS IAM Authentication](https://www.mongodb.com/docs/atlas/security/aws-iam-authentication/) — MONGODB-AWS mechanism, IRSA
- [LDAP Authentication and Authorization](https://www.mongodb.com/docs/atlas/security-ldaps/) — LDAPS setup (deprecated MongoDB 8.0)
- [LDAP Deprecation Notice](https://www.mongodb.com/docs/manual/core/ldap-deprecation/) — Removal timeline
- [Self-Managed X.509 Certificates](https://www.mongodb.com/docs/atlas/security-self-managed-x509/) — Customer-CA mTLS
- [Database Auditing Setup](https://www.mongodb.com/docs/atlas/database-auditing/) — Audit filters, atype list
- [Atlas Resource Policies GA](https://www.mongodb.com/company/blog/7-new-resource-policies-strengthen-atlas-security) — 10 Cedar policies
- [Decoupling Authorization at Scale (Cedar)](https://aws.amazon.com/blogs/opensource/decoupling-authorization-at-scale-mongodb-atlas-and-cedar-based-resource-policies/) — AWS blog on Atlas+Cedar
- [Manage Organization Teams](https://www.mongodb.com/docs/atlas/access/manage-teams-in-orgs/) — Teams structure and limits
- [Atlas UI Authorization Model](https://www.mongodb.com/docs/atlas/atlas-ui-authorization/) — How org and project roles combine
- [Atlas Activity Feed](https://www.mongodb.com/docs/atlas/tutorial/activity-feed/) — Org and project event logs
- [Atlas Free Cluster Limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/) — M0 feature restrictions
- [HashiCorp Vault MongoDB Atlas Secrets Engine](https://developer.hashicorp.com/vault/docs/secrets/mongodbatlas) — Dynamic credential rotation
- [Atlas Terraform Provider — Custom DB Role](https://registry.terraform.io/providers/mongodb/mongodbatlas/latest/docs/resources/custom_db_role) — IaC for custom roles
- [Atlas Architecture: Network Security](https://www.mongodb.com/docs/atlas/architecture/current/network-security/) — IP allowlist vs PrivateLink

### Related skills

- `mongodb-atlas-expert` — Atlas platform overview and admin API
- `mongodb-compliance` — SOC 2, HIPAA, PCI DSS, FedRAMP details
- `mongodb-encryption` — KMS auth (BYOK), CSFLE, Queryable Encryption
- `mongodb-aws-networking` — AWS IAM, PrivateLink, VPC peering
- `mongodb-atlas-azure` — Entra ID federation, AKS Workload Identity
- `mongodb-atlas-gcp` — GCP Workload Identity Federation, Cloud KMS auth
- `okta-expert` — Okta IdP configuration patterns
- `web-auth-patterns` — General OAuth 2.1, OIDC, SAML deep reference
- `security-reviewer` — Security review workflow for Atlas changes
