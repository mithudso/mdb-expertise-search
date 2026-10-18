<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-service-accounts` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-service-accounts
category: mongodb
version: 1.1.0
updated: "2026-05-29"
description: |
  Reference skill for MongoDB Atlas Service Accounts — the OAuth 2.0 Client Credentials
  (machine-to-machine) authentication mechanism for the Atlas Administration API, introduced
  in 2024 and GA April 2025. Covers creating service accounts, token exchange flow,
  org/project role scoping, secret rotation, Terraform and Atlas CLI integration, migration
  from API key pairs, audit logging, and security best practices.
  TRIGGER: configuring programmatic Atlas Admin API access; replacing legacy API key pairs
  with service accounts; MONGODB_ATLAS_CLIENT_ID / MONGODB_ATLAS_CLIENT_SECRET env vars;
  OAuth 2.0 client credentials flow for Atlas; mongodbatlas_service_account Terraform resource;
  rotating Atlas service account secrets; zero-downtime secret rotation; Atlas CLI service
  account login; IP access list for service accounts; org/project roles for automation;
  audit logging for token issuance; AWS Secrets Manager or HCP Vault integration with Atlas.
  SKIP: MongoDB database user authentication (SCRAM, x509, LDAP) — use mongodb-atlas-iam-rbac;
  Atlas cluster data-plane operations — service accounts only cover the Admin API; Atlas Workload
  Identity Federation (OIDC) — use mongodb-atlas-federated-auth.
when_to_use:
  - Configuring programmatic access to the Atlas Admin API for any automation
  - Setting up service accounts in Terraform, Atlas CLI, or CI/CD pipelines
  - Rotating service account secrets with zero downtime
  - Migrating an existing codebase from API key pairs to service accounts
  - Designing least-privilege IAM for Atlas programmatic access
  - Investigating audit logs for service account token issuance
  - Integrating Atlas service accounts with AWS Secrets Manager or HCP Vault
whenNotToUse:
  - MongoDB database user authentication (SCRAM, x509, LDAP) — use mongodb-atlas-iam-rbac
  - Data-plane (document read/write) access — use database users, not service accounts
  - Atlas Workload Identity Federation (OIDC) — use mongodb-atlas-federated-auth
  - Cloud Manager programmatic access — separate product with a different auth model
related_skills:
  - mongodb-atlas-expert
  - mongodb-security-architecture
  - mongodb-atlas-terraform
  - mongodb-atlas-cli
  - mongodb-atlas-iam-rbac
  - mongodb-atlas-federated-auth
---

# MongoDB Atlas Service Accounts

## Overview

MongoDB Atlas Service Accounts are the **recommended programmatic authentication method** for the Atlas Administration API. Introduced in 2024 and reaching General Availability on April 2, 2025, they use the industry-standard **OAuth 2.0 Client Credentials flow** (machine-to-machine auth) to replace the legacy Programmatic API Key (PAK) / HTTP Digest approach.

A service account is a non-human identity used by applications, scripts, CI/CD pipelines, and infrastructure-as-code tools. It lives at the **organization level** in Atlas and can be granted access to one or more projects within that org.

## When to Use This Skill

Use this skill to answer questions about, generate configurations for, or troubleshoot:

- Configuring programmatic access to the Atlas Admin API for any automation
- Setting up service accounts in Terraform, Atlas CLI, or CI/CD pipelines
- Rotating service account secrets with zero downtime
- Migrating an existing codebase from API key pairs to service accounts
- Designing least-privilege IAM for Atlas programmatic access
- Investigating audit logs for service account token issuance

**Not applicable for:** Reading or writing cluster data (documents, collections). Service accounts authenticate to the **Atlas Administration API only** — not the MongoDB data plane. For data-plane access use database users with SCRAM, X.509, or Workload Identity Federation.

**Usage guardrail:** When answering questions or generating configurations using this skill, only use the org roles, project roles, API endpoints, and event type names explicitly listed in this document. Do not invent role names, endpoint paths, or event type strings — Atlas rejects unknown values silently or with generic errors.

---

## 1. Service Accounts vs. API Key Pairs

### Summary Comparison

| Feature | API Key Pairs (Legacy) | Service Accounts (Recommended) |
|---------|------------------------|--------------------------------|
| Auth protocol | HTTP Digest | OAuth 2.0 Client Credentials |
| Credential components | Public Key + Private Key | Client ID + Client Secret |
| Token lifetime | Short (nonce-based) | 3600 s Bearer JWT (1 hour) |
| Multi-secret support | No | Yes (enables zero-downtime rotation) |
| Secret rotation | Recreate key pair | Add new secret, remove old one |
| Audit trail | Yes | Yes (richer, includes token issuance events) |
| Cloud-native integrations | Limited | AWS Secrets Manager, HCP Vault, OIDC federation |
| Atlas UI management | Yes | Yes |
| Atlas CLI env vars | `MONGODB_ATLAS_PUBLIC_KEY` / `MONGODB_ATLAS_PRIVATE_KEY` | `MONGODB_ATLAS_CLIENT_ID` / `MONGODB_ATLAS_CLIENT_SECRET` |
| Recommendation | Legacy only | All new implementations |

### Authentication Flow Difference

**API Key Pairs (HTTP Digest):**
- Each request computes a hash of the request + nonce
- Nonce is short-lived and single-use
- No bearer token; credentials are per-request

**Service Accounts (OAuth 2.0 Client Credentials):**
1. Exchange `client_id` + `client_secret` for a Bearer JWT at the token endpoint
2. Cache the token for up to ~55 minutes
3. Present `Authorization: Bearer <token>` on every API call
4. Re-exchange when token approaches expiry

### When API Keys May Still Be Needed

- Legacy Terraform provider versions (< v1.15 that predate service account support)
- Third-party tools that have not yet adopted OAuth 2.0 for Atlas
- Atlas for Government environments (check docs for GA status)
- Cloud Manager (separate product — uses a different programmatic access model)

---

## 2. Creating Service Accounts

### Required Permissions

Creating a service account at the **organization level** requires the `Organization Owner` role. Adding a service account to a **project** requires the `Project Owner` role for that project.

### Via Atlas UI

1. Go to [cloud.mongodb.com](https://cloud.mongodb.com) and select your organization
2. In the left sidebar click **Access Manager** → **Applications**
3. Click the **Service Accounts** tab
4. Click **Create Service Account**
5. Fill in:
   - **Name** (1–64 characters, alphanumeric + `-_.,' `)
   - **Description** (1–250 characters)
   - **Organization Roles** — select one or more (see Section 4)
   - **Secret Expiry** — hours until the initial secret expires (8–8760 h)
6. Click **Create**
7. **Copy the Client Secret immediately** — it is shown only once. Save to a secrets manager.
8. Note the **Client ID** (format: `mdb_sa_id_<24-hex>`)

### Via Atlas Admin API v2

> **Bootstrap note:** To create the very first service account you need an existing credential with `Organization Owner` access — either an existing API key pair (HTTP Digest) or an authenticated Atlas session. Once you have one service account, you can use its Bearer token to manage others.

```bash
# POST /api/atlas/v2/orgs/{orgId}/serviceAccounts
# Using an existing API key pair (HTTP Digest) to bootstrap
curl -u "$PUBLIC_KEY:$PRIVATE_KEY" --digest \
  --request POST \
  --header "Content-Type: application/vnd.atlas.2024-08-05+json" \
  --header "Accept: application/vnd.atlas.2024-08-05+json" \
  "https://cloud.mongodb.com/api/atlas/v2/orgs/${ORG_ID}/serviceAccounts" \
  --data '{
    "name": "my-ci-service-account",
    "description": "Used by GitHub Actions CI pipeline",
    "roles": ["ORG_MEMBER"],
    "secretExpiresAfterHours": 8760
  }'
```

**Response (201 Created):**
```json
{
  "clientId": "mdb_sa_id_507f1f77bcf86cd799439011",
  "createdAt": "2025-04-10T12:00:00Z",
  "description": "Used by GitHub Actions CI pipeline",
  "name": "my-ci-service-account",
  "roles": ["ORG_MEMBER"],
  "secret": "mdb_sa_sk_...<shown once — copy immediately>",
  "secrets": [
    {
      "createdAt": "2025-04-10T12:00:00Z",
      "expiresAt": "2026-04-10T12:00:00Z",
      "id": "507f1f77bcf86cd799439012"
    }
  ]
}
```

The top-level `secret` field (plaintext) is **only present in the creation response**. Subsequent `GET` calls return `maskedSecretValue` inside the `secrets` array only — the plaintext is never retrievable again.

### Client ID Format

Client IDs always match `^mdb_sa_id_[a-fA-F\d]{24}$`. Store this alongside the secret in your secrets manager.

---

## 3. OAuth2 Token Exchange

Service accounts authenticate via the **OAuth 2.0 Client Credentials grant** (`grant_type=client_credentials`). MongoDB Atlas acts as both the Identity Provider and the Authorization Server.

### Token Endpoint

```
POST https://cloud.mongodb.com/api/oauth/token
```

### Request

```bash
# Encode credentials: base64(client_id:client_secret)
B64=$(echo -n "${CLIENT_ID}:${CLIENT_SECRET}" | base64)

curl --request POST \
  --url "https://cloud.mongodb.com/api/oauth/token" \
  --header "Accept: application/json" \
  --header "Authorization: Basic ${B64}" \
  --header "Cache-Control: no-cache" \
  --header "Content-Type: application/x-www-form-urlencoded" \
  --data "grant_type=client_credentials"
```

### Response

```json
{
  "access_token": "eyJhbGciOiJFUzUxMiIsInR5cCI6IkpXVCIsImtpZCI6Ii4uLiJ9...",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

| Field | Type | Value |
|-------|------|-------|
| `access_token` | string | ES512-signed JWT |
| `expires_in` | integer | 3600 (seconds = 1 hour) |
| `token_type` | string | `"Bearer"` |

### Using the Token

```bash
# Encode credentials first (or reuse $B64 from the Request block above)
B64=$(echo -n "${CLIENT_ID}:${CLIENT_SECRET}" | base64)

ACCESS_TOKEN=$(curl -s --request POST \
  --url "https://cloud.mongodb.com/api/oauth/token" \
  --header "Authorization: Basic ${B64}" \
  --header "Content-Type: application/x-www-form-urlencoded" \
  --data "grant_type=client_credentials" | jq -r '.access_token')

# Use the token in API calls
curl --request GET \
  --url "https://cloud.mongodb.com/api/atlas/v2/orgs/${ORG_ID}" \
  --header "Authorization: Bearer ${ACCESS_TOKEN}" \
  --header "Accept: application/vnd.atlas.2023-02-01+json"
```

### Token Exchange in Python

```python
import base64
import requests
import time

class AtlasTokenManager:
    TOKEN_URL = "https://cloud.mongodb.com/api/oauth/token"
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        self._token_expiry = 0

    def get_token(self) -> str:
        # Cache token with 60-second buffer before expiry
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        
        resp = requests.post(
            self.TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Cache-Control": "no-cache",
            },
            data={"grant_type": "client_credentials"},
        )
        resp.raise_for_status()
        data = resp.json()
        
        self._token = data["access_token"]
        self._token_expiry = time.time() + data["expires_in"]
        return self._token

    def get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "Accept": "application/vnd.atlas.2023-02-01+json",
        }
```

### Token Exchange in Node.js

```javascript
// Requires Node.js 18+ (built-in fetch). For older Node, use node-fetch.
async function getAtlasToken(clientId, clientSecret) {
  const credentials = Buffer.from(`${clientId}:${clientSecret}`).toString('base64');
  const response = await fetch('https://cloud.mongodb.com/api/oauth/token', {
    method: 'POST',
    headers: {
      'Authorization': `Basic ${credentials}`,
      'Content-Type': 'application/x-www-form-urlencoded',
      'Cache-Control': 'no-cache',
    },
    body: 'grant_type=client_credentials',
  });
  if (!response.ok) throw new Error(`Token exchange failed: ${response.status}`);
  return response.json(); // { access_token, expires_in, token_type }
}
```

### Rate Limiting on Token Endpoint

The token endpoint is rate-limited to **10 requests per minute per service account**. Caching tokens (see Section 10) is essential to avoid hitting this limit.

### IP Access Lists and Tokens

- You can **exchange credentials for a token from any IP address**
- You can only **use the token to call the Atlas API** from IPs on the service account's IP access list
- Configure IP access lists via Atlas UI (Applications → Service Accounts → Edit → Access List) or the API

---

## 4. Scopes and Permissions

### Organization-Level Roles

Assigned when creating the service account. Controls what it can do across the entire organization.

| Role | Capabilities |
|------|-------------|
| `ORG_OWNER` | Full control over the org, all projects, all settings |
| `ORG_MEMBER` | View org info, create projects (if also `ORG_GROUP_CREATOR`) |
| `ORG_READ_ONLY` | Read-only access to org resources |
| `ORG_BILLING_ADMIN` | Manage billing, payment methods, invoices |
| `ORG_BILLING_READ_ONLY` | View billing information |
| `ORG_GROUP_CREATOR` | Create new projects within the org |
| `ORG_STREAM_PROCESSING_ADMIN` | Manage Atlas Stream Processing at org level |

### Project-Level Roles

After creating a service account at the org level, you can add it to specific projects with project-scoped roles.

| Role | Capabilities |
|------|-------------|
| `GROUP_OWNER` | Full control over the project |
| `GROUP_READ_ONLY` | Read-only access to project resources |
| `GROUP_DATA_ACCESS_ADMIN` | Manage database users, network access |
| `GROUP_DATA_ACCESS_READ_ONLY` | Read database user and network config |
| `GROUP_DATA_ACCESS_READ_WRITE` | Read/write database users |
| `GROUP_CLUSTER_MANAGER` | Create, modify, delete clusters |
| `GROUP_SEARCH_INDEX_EDITOR` | Manage Atlas Search indexes |
| `GROUP_STREAM_PROCESSING_OWNER` | Manage stream processing instances |
| `GROUP_BACKUP_MANAGER` | Manage backups and restores |
| `GROUP_OBSERVABILITY_VIEWER` | View monitoring, metrics, logs |
| `GROUP_DATABASE_ACCESS_ADMIN` | Full database access management |

### Adding a Service Account to a Project

Via API:
```bash
curl --request POST \
  --url "https://cloud.mongodb.com/api/atlas/v2/groups/${PROJECT_ID}/serviceAccounts" \
  --header "Authorization: Bearer ${ACCESS_TOKEN}" \
  --header "Content-Type: application/vnd.atlas.2024-08-05+json" \
  --data '{
    "clientId": "mdb_sa_id_507f1f77bcf86cd799439011",
    "roles": ["GROUP_READ_ONLY"]
  }'
```

### Least-Privilege Design

- **Infrastructure automation** (Terraform, IaC): `ORG_MEMBER` + `GROUP_CLUSTER_MANAGER`
- **CI/CD deployment pipelines**: `GROUP_CLUSTER_MANAGER` + `GROUP_DATA_ACCESS_ADMIN`
- **Monitoring / observability**: `GROUP_OBSERVABILITY_VIEWER` or `GROUP_READ_ONLY`
- **Billing automation**: `ORG_BILLING_READ_ONLY` or `ORG_BILLING_ADMIN`
- **Backup jobs**: `GROUP_BACKUP_MANAGER`

Do **not** use `ORG_OWNER` for automation. Create per-workflow service accounts with narrowly scoped roles.

---

## 5. Secret Rotation

### Secret Lifecycle

Secrets expire after a configured duration of **8 to 8760 hours** (8 hours to 365 days). When a secret nears expiry, Atlas triggers a **"Service Account Secrets are about to expire"** alert.

Multiple secrets can be active simultaneously on a single service account. This is the foundation for **zero-downtime rotation**.

### Zero-Downtime Rotation Procedure

1. **Generate a new secret** while the current one is still active
2. **Update all consumers** (applications, CI/CD secrets, IaC vars) with the new secret
3. **Verify** new secret works by running a test token exchange
4. **Revoke the old secret** — once revoked, the old secret immediately becomes invalid

> When you add a new secret, the old secret's expiry is shortened to a maximum of **7 days** from the new secret's creation (if the original expiry was farther away). Plan accordingly — don't delay consumer updates.

### Via Atlas UI

1. Organizations menu → **Applications** → **Service Accounts**
2. Click the service account name
3. Click **Generate New Client Secret**
4. Select expiration duration → Click **Generate New**
5. **Copy the secret immediately** (shown only once)
6. Update all consumers, verify, then click **Revoke** next to the old secret

### Via Atlas Admin API v2

```bash
# Step 1: Create new secret
curl --request POST \
  --url "https://cloud.mongodb.com/api/atlas/v2/orgs/${ORG_ID}/serviceAccounts/${CLIENT_ID}/secrets" \
  --header "Authorization: Bearer ${ACCESS_TOKEN}" \
  --header "Content-Type: application/vnd.atlas.2024-08-05+json" \
  --data '{"secretExpiresAfterHours": 8760}'

# Step 2: Delete the old secret after updating consumers
curl --request DELETE \
  --url "https://cloud.mongodb.com/api/atlas/v2/orgs/${ORG_ID}/serviceAccounts/${CLIENT_ID}/secrets/${SECRET_ID}" \
  --header "Authorization: Bearer ${ACCESS_TOKEN}"
```

### AWS Secrets Manager Automated Rotation

AWS Secrets Manager supports **native automated rotation** for MongoDB Atlas service account secrets (GA 2026). Configure via the AWS Secrets Manager console:

1. Store the secret with type `MongoDB Atlas Service Account`
2. Configure rotation schedule and rotation Lambda
3. AWS Secrets Manager automatically: creates a new secret, updates the value, and deletes the old one

See: [AWS Secrets Manager MongoDB Atlas Service Account partner integration](https://docs.aws.amazon.com/secretsmanager/latest/userguide/mes-partner-MongoDBAtlasServiceAccount.html)

### HashiCorp Vault Integration

HCP Vault Secrets also supports [automatic rotation for MongoDB Atlas service accounts](https://developer.hashicorp.com/hcp/docs/vault-secrets/auto-rotation/create-rotating-secret/mongodb-atlas), enabling vault-managed credential lifecycle.

---

## 6. Terraform Integration

### Provider Version

Service account support requires **MongoDB Atlas Terraform Provider ≥ v1.15.0**. Verify: `terraform providers`.

### Provider Configuration with Service Accounts

```hcl
terraform {
  required_providers {
    mongodbatlas = {
      source  = "mongodb/mongodbatlas"
      version = "~> 1.15"
    }
  }
}

provider "mongodbatlas" {
  # Authenticate with service account
  client_id     = var.mongodb_atlas_client_id
  client_secret = var.mongodb_atlas_client_secret
}
```

**Environment variable alternative** (preferred for CI/CD — no secrets in `.tfvars`):
```bash
export MONGODB_ATLAS_CLIENT_ID="mdb_sa_id_507f1f77bcf86cd799439011"
export MONGODB_ATLAS_CLIENT_SECRET="<your-secret>"
```

When these env vars are set, the provider picks them up automatically — no `client_id` / `client_secret` in the provider block needed.

### Creating a Service Account via Terraform

```hcl
resource "mongodbatlas_service_account" "ci_pipeline" {
  org_id      = var.org_id
  name        = "ci-pipeline-service-account"
  description = "Service account for GitHub Actions CI/CD"
  roles       = ["ORG_MEMBER"]
  secret_expires_after_hours = 2160  # 90 days
}

resource "mongodbatlas_service_account_secret" "ci_pipeline_secret" {
  org_id    = var.org_id
  client_id = mongodbatlas_service_account.ci_pipeline.client_id
  secret_expires_after_hours = 2160
}

# Output the credentials (store in Vault / Secrets Manager — never in state unencrypted)
output "service_account_client_id" {
  value = mongodbatlas_service_account.ci_pipeline.client_id
}

output "service_account_client_secret" {
  value     = mongodbatlas_service_account_secret.ci_pipeline_secret.secret
  sensitive = true
}
```

### Important: Terraform State Security

> **Warning:** Managing service accounts with Terraform stores the `client_secret` in Terraform state. Use a **remote state backend with encryption** (Terraform Cloud, S3 with KMS, or GCS with CMEK). Never commit state files to version control.

### Secret Resource Constraints

`mongodbatlas_service_account_secret` **does not support updates** — to rotate, create a new secret resource and remove the old one. See [Guide: Service Account Secret Rotation](https://www.mongodb.com/docs/atlas/tutorial/rotate-service-account-secrets/).

### Import Syntax

```bash
terraform import mongodbatlas_service_account.example "${ORG_ID}/${CLIENT_ID}"
```

> **Note:** `mongodbatlas_service_account_secret` **does not support Terraform import**. Secrets are write-only resources — the plaintext is only available at creation time and cannot be re-read into state. Manage rotation outside Terraform state (see Section 5), or use `terraform destroy` + recreate.

---

## 7. Atlas CLI Integration

### Environment Variables (Preferred for CI/CD)

```bash
export MONGODB_ATLAS_CLIENT_ID="mdb_sa_id_507f1f77bcf86cd799439011"
export MONGODB_ATLAS_CLIENT_SECRET="<your-secret>"
```

With these set, all `atlas` CLI commands authenticate as the service account without interactive prompts.

### Interactive Login

```bash
atlas auth login
# Select "ServiceAccount" option
# Enter Client ID and secret when prompted
# Select default project and output format
```

### Non-Interactive (CI/CD)

```bash
# Use env vars — no login command needed
atlas clusters list --projectId "${PROJECT_ID}" --orgId "${ORG_ID}"
atlas alerts list --projectId "${PROJECT_ID}"
atlas deployments list --orgId "${ORG_ID}"
```

### Config Profile for Service Account

For CI/CD, prefer environment variables (see above). For a named profile that persists across local development sessions, use `atlas auth login` interactively — it writes the profile for you:

```bash
atlas auth login --profile my-sa-profile
# Select "ServiceAccount", enter Client ID and secret when prompted
atlas clusters list --profile my-sa-profile --projectId "${PROJECT_ID}"
```

### GitHub Actions Example

```yaml
name: Atlas Deployment
on: [push]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Install Atlas CLI
        run: |
          curl -fsSL https://fastdl.mongodb.org/mongocli/mongodb-atlas-cli_latest_linux_x86_64.tar.gz \
            | tar -xz --strip-components=1 -C /usr/local/bin atlas

      - name: List clusters
        env:
          MONGODB_ATLAS_CLIENT_ID: ${{ secrets.ATLAS_CLIENT_ID }}
          MONGODB_ATLAS_CLIENT_SECRET: ${{ secrets.ATLAS_CLIENT_SECRET }}
        run: atlas clusters list --projectId "${{ secrets.ATLAS_PROJECT_ID }}"
```

---

## 8. Migration from API Keys to Service Accounts

### Migration Strategy

Migration is **non-breaking** — API keys and service accounts work simultaneously. Migrate incrementally per-application.

### Step-by-Step Migration

1. **Create a service account** with equivalent org roles to the existing API key
2. **Add it to the same projects** with equivalent project roles
3. **Configure the application** to use OAuth 2.0 token exchange instead of HTTP Digest
4. **Test in staging** — verify the service account can perform all required operations
5. **Deploy to production** with the new service account credentials
6. **Monitor** for any `401 Unauthorized` errors
7. **Delete the old API key** after confirming stable operation

### Code Migration: HTTP Digest → OAuth 2.0

**Before (API Key / HTTP Digest):**
```python
import requests
from requests.auth import HTTPDigestAuth

response = requests.get(
    f"https://cloud.mongodb.com/api/atlas/v2/orgs/{org_id}",
    auth=HTTPDigestAuth(public_key, private_key),
    headers={"Accept": "application/vnd.atlas.2023-02-01+json"},
)
```

**After (Service Account / OAuth 2.0 Bearer):**
```python
import requests, base64

# Token exchange (cache this token — see Section 10)
b64 = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
token_resp = requests.post(
    "https://cloud.mongodb.com/api/oauth/token",
    headers={"Authorization": f"Basic {b64}",
             "Content-Type": "application/x-www-form-urlencoded"},
    data={"grant_type": "client_credentials"},
)
access_token = token_resp.json()["access_token"]

# API call with Bearer token
response = requests.get(
    f"https://cloud.mongodb.com/api/atlas/v2/orgs/{org_id}",
    headers={
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.atlas.2023-02-01+json",
    },
)
```

### Terraform Migration

**Before (API key in provider):**
```hcl
provider "mongodbatlas" {
  public_key  = var.atlas_public_key
  private_key = var.atlas_private_key
}
```

**After (service account in provider):**
```hcl
provider "mongodbatlas" {
  client_id     = var.atlas_client_id
  client_secret = var.atlas_client_secret
}
```

Or via environment variables:
```bash
# Unset old vars
unset MONGODB_ATLAS_PUBLIC_KEY MONGODB_ATLAS_PRIVATE_KEY

# Set new vars
export MONGODB_ATLAS_CLIENT_ID="mdb_sa_id_..."
export MONGODB_ATLAS_CLIENT_SECRET="<secret>"
```

### Atlas CLI Migration

**Before:**
```bash
export MONGODB_ATLAS_PUBLIC_KEY="..."
export MONGODB_ATLAS_PRIVATE_KEY="..."
```

**After:**
```bash
export MONGODB_ATLAS_CLIENT_ID="mdb_sa_id_..."
export MONGODB_ATLAS_CLIENT_SECRET="..."
```

---

## 9. Audit Logging

### What Gets Logged

Service account activity appears in two places:
1. **Atlas Organization/Project Activity Feed** — management-plane events (service account created, secret generated, service account added to project, access token issued)
2. **Atlas Database Audit Logs** (M10+ clusters, optional) — cluster-level authentication and operation auditing

### Identifying Service Account Activity

Service account tokens carry the `clientId` in the audit event. The activity feed event types below are based on Atlas documentation — verify exact string values against the [Atlas Admin API events endpoint](https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/group/endpoint-events) before using them as query filters in production:

- `SERVICE_ACCOUNT_CREATED` — new service account provisioned
- `SERVICE_ACCOUNT_DELETED` — service account removed
- `SERVICE_ACCOUNT_SECRET_ADDED` — new secret generated
- `SERVICE_ACCOUNT_SECRET_DELETED` — secret revoked
- `SERVICE_ACCOUNT_TOKEN_ISSUED` — access token generated (use this to detect leaked-secret usage from unexpected IPs)

### Monitoring via Atlas Admin API

```bash
# Retrieve organization audit events (verify eventType string against Atlas API docs)
curl --request GET \
  --url "https://cloud.mongodb.com/api/atlas/v2/orgs/${ORG_ID}/events?itemsPerPage=100&eventType=SERVICE_ACCOUNT_TOKEN_ISSUED" \
  --header "Authorization: Bearer ${ACCESS_TOKEN}" \
  --header "Accept: application/vnd.atlas.2023-02-01+json"
```

### Log Retention

Atlas retains the last **30 days** of log messages and system event audit messages. For longer retention, export logs to a SIEM or object storage.

### Alert on Anomalous Token Issuance

Configure alerts in Atlas UI under **Organization → Alerts** for:
- **"Service Account Secrets are about to expire"** — built-in alert type, configurable threshold
- Unexpected spikes in token issuance events (query the `/orgs/{orgId}/events` endpoint and feed into your SIEM)
- Token issuance from IPs outside expected ranges (Atlas blocks *use* from non-allowlisted IPs but the attempt is still logged in the activity feed)

### Database Audit Logging

For deeper visibility into what a service account *does* within a cluster (not just token issuance), enable MongoDB Database Auditing on M10+ clusters. Custom audit filters can target specific service account identities. Note: enabling audit authorization successes can significantly impact cluster performance — audit selectively.

---

## 10. Security Best Practices

### Never Store Secrets in Code or Environment

```bash
# BAD: secret in source code or .env committed to git
CLIENT_SECRET="abc123..."

# GOOD: pull from Vault or AWS Secrets Manager at runtime
CLIENT_SECRET=$(vault kv get -field=client_secret secret/atlas/my-service-account)
```

Use these secrets managers with Atlas service accounts:
- **HashiCorp Vault** (HCP Vault Secrets with auto-rotation)
- **AWS Secrets Manager** (native Atlas service account rotation, GA 2026)
- **GCP Secret Manager**
- **Azure Key Vault**
- **External Secrets Operator** (Kubernetes-native bridge to Vault/ASM/GSM — do not use raw Kubernetes Secrets for client secrets, as they are base64-encoded in etcd by default, not encrypted)

### Token Caching — Do Not Exchange on Every Request

The token endpoint is rate-limited to **10 requests/minute**. Cache the Bearer token for up to ~55 minutes (expiry - 60 seconds buffer):

```javascript
// Requires Node.js 18+ (built-in fetch). See Section 3 for the full getAtlasToken() implementation.
const tokenCache = { token: null, expiresAt: 0 };

async function getToken(clientId, clientSecret) {
  if (tokenCache.token && Date.now() < tokenCache.expiresAt - 60_000) {
    return tokenCache.token; // reuse cached token
  }
  const credentials = Buffer.from(`${clientId}:${clientSecret}`).toString('base64');
  const resp = await fetch('https://cloud.mongodb.com/api/oauth/token', {
    method: 'POST',
    headers: {
      'Authorization': `Basic ${credentials}`,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: 'grant_type=client_credentials',
  });
  if (!resp.ok) throw new Error(`Token exchange failed: ${resp.status}`);
  const { access_token, expires_in } = await resp.json();
  tokenCache.token = access_token;
  tokenCache.expiresAt = Date.now() + expires_in * 1000;
  return tokenCache.token;
}
```

### One Service Account Per Application

- Do **not** share a service account across multiple independent applications
- If a secret leaks, you can revoke it without impacting other applications
- Enables per-application audit trails and role scoping

### Scope to Least Privilege

- Assign only the roles required for the specific automation task
- Use project-level roles rather than org-level roles when possible
- Review service account permissions quarterly

### Configure IP Access Lists

Even though tokens can be generated from any IP, add an IP access list to restrict where tokens can be *used*:

```bash
# Add IP access list entry for service account
curl --request POST \
  --url "https://cloud.mongodb.com/api/atlas/v2/orgs/${ORG_ID}/serviceAccounts/${CLIENT_ID}/accessList" \
  --header "Authorization: Bearer ${ACCESS_TOKEN}" \
  --header "Content-Type: application/vnd.atlas.2024-08-05+json" \
  --data '[{"ipAddress": "192.168.1.0/24", "comment": "GitHub Actions runner pool"}]'
```

### Secret Expiry Policy

- Set secrets to expire in **90 days or less** for production service accounts
- Use **8760 hours (365 days)** only if your rotation automation is fully verified
- Configure Atlas alerts for **"Service Account Secrets are about to expire"**

### Rotate Secrets Before Expiry

- Never let secrets expire — use the zero-downtime rotation procedure in Section 5
- Automate rotation via AWS Secrets Manager or HCP Vault Secrets

### Monitor for Compromise Indicators

- Unexpected token issuance events from unknown IPs (blocked at use, but visible in audit log)
- Unusual spike in API call volume on a service account
- Token issuance at unexpected times (e.g., outside CI/CD window)
- Service account in use after it should have been decommissioned

### Secure Terraform State

If managing service accounts with Terraform, always use a remote backend with encryption:

```hcl
terraform {
  backend "s3" {
    bucket         = "my-terraform-state"
    key            = "atlas/service-accounts.tfstate"
    region         = "us-east-1"
    encrypt        = true
    kms_key_id     = "arn:aws:kms:us-east-1:123456789:key/..."
    dynamodb_table = "terraform-lock"
  }
}
```

---

## References and See Also

### Official MongoDB Documentation
- [Atlas Administration API Authentication Methods](https://www.mongodb.com/docs/atlas/api/api-authentication/)
- [Generate Service Account Token](https://www.mongodb.com/docs/atlas/api/service-accounts/generate-oauth2-token/)
- [Manage Programmatic Access to an Organization](https://www.mongodb.com/docs/atlas/configure-api-access-org/)
- [Manage Programmatic Access to a Project](https://www.mongodb.com/docs/atlas/configure-api-access-project/)
- [Rotate Service Account Secrets](https://www.mongodb.com/docs/atlas/tutorial/rotate-service-account-secrets/)
- [Guidance for Atlas Authentication](https://www.mongodb.com/docs/atlas/architecture/current/auth/authentication/)
- [Atlas Service Accounts — Admin API v2](https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/group/endpoint-service-accounts)
- [Atlas CLI: Connect with Service Accounts](https://www.mongodb.com/docs/atlas/cli/current/connect-atlas-cli/)
- [Set Up Workload Identity Federation](https://www.mongodb.com/docs/atlas/workload-oidc/)

### MongoDB Blog
- [Introducing MongoDB Atlas Service Accounts via OAuth 2.0 (GA, April 2025)](https://www.mongodb.com/company/blog/product-release-announcements/introducing-mongodb-atlas-service-accounts-via-oauth-2-0)

### Terraform
- [Terraform Registry: mongodb/mongodbatlas Provider Configuration Guide](https://registry.terraform.io/providers/MongoDB/mongodbatlas/latest/docs/guides/provider-configuration)
- [Resource: mongodbatlas_service_account_secret (GitHub)](https://github.com/mongodb/terraform-provider-mongodbatlas/blob/master/docs/resources/service_account_secret.md)

### Integrations
- [AWS Secrets Manager: MongoDB Atlas Service Account](https://docs.aws.amazon.com/secretsmanager/latest/userguide/mes-partner-MongoDBAtlasServiceAccount.html)
- [HCP Vault Secrets: MongoDB Atlas Auto-Rotation](https://developer.hashicorp.com/hcp/docs/vault-secrets/auto-rotation/mongodb-atlas)
- [Developer Examples Repo: atlas-admin-api-serviceaccount-auth](https://github.com/mongodb-developer/atlas-admin-api-serviceaccount-auth)

### Related Skills
- [[mongodb-atlas-expert]] — Full Atlas feature reference
- [[mongodb-security-architecture]] — Atlas security design patterns
- [[mongodb-atlas-terraform]] — Terraform provider patterns for Atlas
- [[mongodb-atlas-cli]] — Atlas CLI usage patterns
- [[mongodb-atlas-iam-rbac]] — Atlas IAM and role-based access control
