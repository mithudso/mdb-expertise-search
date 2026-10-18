<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-iac` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-iac
description: MongoDB Atlas Infrastructure as Code — Terraform provider mongodb/mongodbatlas v2.x, Atlas Kubernetes Operator (AKO) v2.14 with all CRDs (AtlasProject/Deployment/DatabaseUser/IPAccessList/NetworkPeering/PrivateEndpoint/SearchIndexConfig/StreamInstance/FederatedAuth/OrgSettings), Atlas CLI, Atlas Admin API v2, Pulumi, AWS CloudFormation third-party resources, AWS CDK. Covers Service Account OAuth 2.0 vs legacy Programmatic API keys, drift detection, multi-environment patterns, independent vs subobject CRDs, the Terraform-provider mongodbatlas_cluster → mongodbatlas_advanced_cluster migration (provider v2.0), AKO dry-run mode, and migration paths between IaC tools. TRIGGER when provisioning Atlas via code, choosing between Terraform/AKO/CFN/Pulumi/CDK, debugging IaC drift or reconciliation, importing existing clusters, or distinguishing the Atlas Kubernetes Operator (manages Atlas from inside K8s) from the MongoDB Community/Enterprise Operator (runs MongoDB inside K8s). SKIP when running MongoDB inside Kubernetes nodes (use mongodb-drivers-k8s), or for non-IaC Atlas topics like indexing, schema design, or query performance.
---

# MongoDB Atlas Infrastructure as Code

## Overview

MongoDB Atlas exposes the same underlying Atlas Admin API v2 surface through every Infrastructure as Code (IaC) tool in the ecosystem. The choice of tool — Terraform, the Atlas Kubernetes Operator, Pulumi, CloudFormation, AWS CDK, or direct REST — depends on where your platform engineering already lives, not on capability gaps. All tools eventually call the same `cloud.mongodb.com/api/atlas/v2/` endpoints under OAuth 2.0 or HTTP Digest authentication.

**Why this matters for TAMs and platform engineers:** Customers running Atlas at scale rarely use a single tool. A common shape is Terraform for project/cluster baseline, AKO for application teams' database users and search indexes, the Atlas CLI for one-off scripted operations, and direct Admin API calls for things no IaC tool has caught up to yet (typically new features within their first six months of GA). Mixing tools is fine; mixing tools **with manual UI changes** is the universal anti-pattern.

**Versions current as of May 2026:**
- Terraform provider (`mongodb/mongodbatlas`): **v2.12.0** (May 6, 2026) — 72.5M downloads
- Atlas Kubernetes Operator (AKO): **v2.14**
- Atlas CLI: **v1.46.x**
- Atlas Admin API: **v2** (the v1 surface still works under `/api/atlas/v1.0/` but is deprecated)
- Pulumi provider: parity with Terraform via bridge
- AWS CloudFormation resources: **33+ resource types** (and growing)
- AWS CDK package: `awscdk-resources-mongodbatlas`

---

## Authentication Methods (universal across all IaC tools)

Every Atlas IaC tool boils down to one of two authentication patterns. Service Accounts are the strongly preferred method as of 2026; Programmatic API Keys are legacy and will eventually be deprecated.

### Service Accounts (OAuth 2.0 Client Credentials) — recommended

Service Accounts use the OAuth 2.0 client credentials flow with MongoDB Atlas as both the identity provider and authorization server. Each Service Account has a **Client ID** and **Client Secret** that function as username/password to mint short-lived access tokens (1-hour TTL per the OAuth 2.0 spec). Each Terraform/Pulumi/CDK operation generates a new token used only for that operation.

```bash
# Get an OAuth 2.0 access token
curl --request POST \
  --url https://cloud.mongodb.com/api/oauth/token \
  --header 'Accept: application/json' \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --user "${CLIENT_ID}:${CLIENT_SECRET}" \
  --data 'grant_type=client_credentials'
# → { "access_token": "...", "expires_in": 3600, "token_type": "Bearer" }
```

**Scopes:** Service Accounts can be scoped at the **Organization** or **Project** level. Project-scoped SAs are the principle of least privilege default; org-scoped SAs are needed only when the IaC tool itself creates projects.

**Why preferred over API Keys:**
1. Industry-standard OAuth 2.0 with short-lived bearer tokens
2. Client Secret rotation without changing the Client ID (vs. API key pair rotation which requires changes everywhere)
3. Better support in modern Atlas tooling (Atlas Go SDK, Terraform v2.x, Pulumi, AKO v2.14)
4. Workload Identity Federation (WIF) lets you replace static secrets entirely on GKE, AKS, EKS, and Cloud Run

### Programmatic API Keys (HTTP Digest) — legacy

The older method uses an HTTP Digest auth pair: `public_key` (username) + `private_key` (password). Each key pair is scoped to a single Org or Project and listed under "Access Manager → API Keys" in the Atlas UI.

```bash
# Direct curl call
curl --user "${PUBLIC_KEY}:${PRIVATE_KEY}" --digest \
  --header 'Accept: application/vnd.atlas.2024-05-30+json' \
  https://cloud.mongodb.com/api/atlas/v2/groups/${PROJECT_ID}/clusters
```

**Operational pain points:**
- API keys cannot be rotated atomically — you must create a new pair, switch every consumer, then delete the old pair
- No fine-grained scope beyond Org/Project + Atlas role
- Counted as "users" in the project member list (visible noise)
- All access on a key revokes simultaneously on deletion

### Environment variable conventions (all tools)

| Variable | Used by | Purpose |
|---|---|---|
| `MONGODB_ATLAS_CLIENT_ID` | Terraform, Pulumi, Atlas Go SDK | Service Account Client ID |
| `MONGODB_ATLAS_CLIENT_SECRET` | Terraform, Pulumi, Atlas Go SDK | Service Account Client Secret |
| `MONGODB_ATLAS_PUBLIC_KEY` | Terraform, Pulumi, Atlas CLI | Programmatic API public key |
| `MONGODB_ATLAS_PRIVATE_KEY` | Terraform, Pulumi, Atlas CLI | Programmatic API private key |
| `MONGODB_ATLAS_BASE_URL` | All | For AtlasGov: `https://cloud.mongodbgov.com/` |
| `MONGODB_ATLAS_PROJECT_ID` | Atlas CLI | Implicit `--projectId` |
| `MONGODB_ATLAS_ORG_ID` | Atlas CLI | Implicit `--orgId` |

---

## Tool 1: Terraform — `mongodb/mongodbatlas` Provider

Terraform is the most widely-used Atlas IaC tool by a wide margin (72.5M provider downloads vs. ~10k for the Pulumi equivalent). The official provider is maintained by MongoDB at `github.com/mongodb/terraform-provider-mongodbatlas`.

### Provider configuration

```hcl
terraform {
  required_version = ">= 1.5"
  required_providers {
    mongodbatlas = {
      source  = "mongodb/mongodbatlas"
      version = "~> 2.12"  # pin to minor; allow patch upgrades
    }
  }
}

# Option A: Service Account (preferred)
provider "mongodbatlas" {
  client_id     = var.atlas_client_id      # or set MONGODB_ATLAS_CLIENT_ID
  client_secret = var.atlas_client_secret  # or set MONGODB_ATLAS_CLIENT_SECRET
}

# Option B: Programmatic API key (legacy)
provider "mongodbatlas" {
  public_key  = var.atlas_public_key   # or MONGODB_ATLAS_PUBLIC_KEY
  private_key = var.atlas_private_key  # or MONGODB_ATLAS_PRIVATE_KEY
}

# Option C: Pre-minted OAuth access token (rare; mostly for testing)
provider "mongodbatlas" {
  access_token = var.atlas_oauth_token  # short-lived; reissue every <60min
}
```

### Resource catalog (high-traffic resources)

| Category | Resource | Purpose |
|---|---|---|
| **Org/Project** | `mongodbatlas_organization` | Create new org (rare; usually pre-existing) |
| | `mongodbatlas_project` | Project (groups all clusters + users + network) |
| | `mongodbatlas_project_api_key` | Programmatic API key scoped to project |
| | `mongodbatlas_project_invitation` | Invite Atlas users (deprecated → use `org_invitation`) |
| | `mongodbatlas_organization_invitation` | Invite users to org |
| | `mongodbatlas_team` | Atlas team within org |
| | `mongodbatlas_teams` | Bind a team to a project with roles |
| **Cluster** | `mongodbatlas_advanced_cluster` | **Use this** — replaces `mongodbatlas_cluster` |
| | `mongodbatlas_cluster` | Deprecated as of v2.0 (Apr 2025); removed in next major |
| | `mongodbatlas_flex_cluster` | Flex tier (post-Jan 2026 M2/M5/Serverless replacement) |
| | `mongodbatlas_search_index` | Atlas Search + Vector Search indexes |
| | `mongodbatlas_search_deployment` | Dedicated Search Nodes |
| **Users / Auth** | `mongodbatlas_database_user` | Mongo users (SCRAM/X.509/AWS IAM/OIDC) |
| | `mongodbatlas_x509_authentication_database_user` | X.509 user cert |
| | `mongodbatlas_custom_db_role` | Custom RBAC role |
| | `mongodbatlas_federated_settings_identity_provider` | SAML/OIDC IdP for workforce |
| | `mongodbatlas_federated_settings_org_config` | Org-level federation config |
| **Network** | `mongodbatlas_project_ip_access_list` | Single CIDR/IP entry |
| | `mongodbatlas_network_container` | VPC-equivalent network container |
| | `mongodbatlas_network_peering` | VPC Peering (AWS/Azure/GCP) |
| | `mongodbatlas_privatelink_endpoint` | PrivateLink/Private Service Connect resource |
| | `mongodbatlas_privatelink_endpoint_service` | Service mapping for PrivateLink endpoint |
| **Backup** | `mongodbatlas_cloud_backup_schedule` | Backup policy (frequency/retention) |
| | `mongodbatlas_cloud_backup_snapshot` | One-off snapshot |
| | `mongodbatlas_cloud_backup_snapshot_restore_job` | Restore a snapshot |
| | `mongodbatlas_backup_compliance_policy` | Compliance backup policy (1-time enable, no undo) |
| **Encryption** | `mongodbatlas_encryption_at_rest` | BYOK (AWS KMS / Azure KV / GCP KMS) |
| **Data tier** | `mongodbatlas_online_archive` | Move cold data to S3-backed archive |
| | `mongodbatlas_data_lake_pipeline` | Data Lake federation |
| | `mongodbatlas_federated_database_instance` | Atlas Data Federation |
| **Streams** | `mongodbatlas_stream_instance` | Stream Processing Instance |
| | `mongodbatlas_stream_connection` | Source/sink connection |
| **Alerts** | `mongodbatlas_alert_configuration` | Alert rule |
| | `mongodbatlas_third_party_integration` | Datadog/Slack/PagerDuty/Webhook |
| **App Services** | `mongodbatlas_event_trigger` | Trigger (database/scheduled/auth) |

(Total resource count: **80+** as of v2.12.0)

### Canonical `advanced_cluster` example

```hcl
resource "mongodbatlas_project" "prod" {
  name   = "ecommerce-prod"
  org_id = var.atlas_org_id

  # Limits help guardrail accidental over-provisioning
  limits {
    name  = "atlas.project.deployment.clusters"
    value = 10
  }
}

resource "mongodbatlas_advanced_cluster" "prod_us" {
  project_id     = mongodbatlas_project.prod.id
  name           = "prod-us-east"
  cluster_type   = "REPLICASET"  # or SHARDED, GEOSHARDED
  backup_enabled = true
  pit_enabled    = true          # continuous backup / point-in-time
  mongo_db_major_version = "8.0"
  encryption_at_rest_provider = "AWS"

  replication_specs {
    region_configs {
      provider_name = "AWS"
      region_name   = "US_EAST_1"
      priority      = 7           # highest = preferred for primary

      electable_specs {
        instance_size = "M30"
        node_count    = 3
        disk_iops     = 3000      # only valid on M30+ AWS
      }

      analytics_specs {
        instance_size = "M30"
        node_count    = 1
      }

      auto_scaling {
        compute_enabled            = true
        compute_min_instance_size  = "M30"
        compute_max_instance_size  = "M60"
        compute_scale_down_enabled = true
        disk_gb_enabled            = true
      }
    }
  }

  tags {
    key   = "environment"
    value = "production"
  }
  tags {
    key   = "cost_center"
    value = "platform-eng"
  }

  lifecycle {
    # Prevent accidental destroys of production
    prevent_destroy = true
    # Ignore provider-side computed-only fields that cause perpetual diffs
    ignore_changes = [disk_size_gb]
  }
}
```

### `mongodbatlas_cluster` → `mongodbatlas_advanced_cluster` migration (v2.x)

`mongodbatlas_cluster` is deprecated as of provider v2.0 (April 2025) and slated for removal in the next major. `mongodbatlas_advanced_cluster` is required to use any modern Atlas feature: multi-cloud clusters, asymmetric sharding, independent analytics node scaling, ISRS (Independent Shard Replica Scaling), and any new feature shipped after early 2024.

**Recommended migration path (using `moved` block):**

1. Run `terraform plan` — confirm no pending changes on the existing `mongodbatlas_cluster` resource
2. Use the **Atlas CLI plugin** to generate the new resource block:
   ```bash
   atlas plugin install mongodb/atlas-cli-plugin-terraform
   atlas terraform generate --type=advanced_cluster --resource=mongodbatlas_cluster.my_cluster > new_cluster.tf
   ```
   This preserves your variable references and expression formatting.
3. Add a `moved` block to your config:
   ```hcl
   moved {
     from = mongodbatlas_cluster.my_cluster
     to   = mongodbatlas_advanced_cluster.my_cluster
   }
   ```
4. `terraform plan` — should show zero infrastructure changes; only the resource type renaming
5. `terraform apply` — Terraform records the move in state without touching Atlas

**Asymmetric sharding gotcha:** When `replication_specs[*].id` becomes non-uniform (because shards scale independently), `mongodbatlas_cloud_backup_schedule.copy_settings` must switch from `replication_spec_id` to `zone_id`. The provider migration guide covers this.

### Drift detection patterns

`terraform plan` is the canonical drift check — it refreshes state from the Atlas API and diffs against config. For Atlas specifically:

```bash
# Detailed exit code drift detection (for CI)
terraform plan -detailed-exitcode -out=plan.bin
# Exit 0 = no changes; 1 = error; 2 = changes present (drift!)

# Refresh-only without proposed changes (state-only sync)
terraform plan -refresh-only

# Save drift snapshot to S3 for review
terraform show -json plan.bin > drift-$(date +%Y%m%d).json
aws s3 cp drift-$(date +%Y%m%d).json s3://platform-drift-logs/
```

**Schedule a daily drift job in GitHub Actions:**

```yaml
# .github/workflows/atlas-drift.yml
name: Atlas Drift Detection
on:
  schedule:
    - cron: '0 13 * * *'   # 13:00 UTC daily
  workflow_dispatch:

jobs:
  drift:
    runs-on: ubuntu-latest
    env:
      MONGODB_ATLAS_CLIENT_ID:     ${{ secrets.ATLAS_CLIENT_ID }}
      MONGODB_ATLAS_CLIENT_SECRET: ${{ secrets.ATLAS_CLIENT_SECRET }}
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with: { terraform_version: 1.9.x }
      - run: terraform init
      - id: plan
        run: terraform plan -detailed-exitcode -no-color -out=tfplan
        continue-on-error: true
      - if: steps.plan.outputs.exitcode == 2
        run: |
          # Open a GitHub issue rather than auto-applying in prod
          gh issue create --title "Atlas drift detected on $(date)" \
            --body "$(terraform show -no-color tfplan)" \
            --label drift,atlas
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Key rule:** never auto-`terraform apply` drift in production. Alert, open an issue, require human review. Auto-remediation is acceptable in dev/staging environments where the cost of an unintended revert is low.

---

## Tool 2: Atlas Kubernetes Operator (AKO)

The **Atlas Kubernetes Operator** (AKO) is a CNCF Operator Framework controller that manages Atlas resources via Kubernetes Custom Resource Definitions (CRDs). It runs **inside your Kubernetes cluster** and reconciles Atlas state against the CRD spec on a loop.

**Critical distinction:** AKO **does not run MongoDB inside Kubernetes** — that is the [MongoDB Community/Enterprise Operator](https://github.com/mongodb/mongodb-kubernetes-operator), a separate project. AKO **manages Atlas cluster resources from inside Kubernetes** but the cluster nodes themselves run on Atlas-managed VMs in AWS/Azure/GCP, not in your K8s cluster. Confusing the two is the #1 pre-sales misconception.

**Current version:** **v2.14** (May 2026). Helm chart published at `mongodb/mongodb-atlas-operator` v2.13.2 on Artifact Hub.

### Supported CRDs (v2.14)

| Category | CRD | Manages |
|---|---|---|
| **Core** | `AtlasProject` | Atlas Project (org-scoped) |
| | `AtlasDeployment` | Cluster (replicaset/sharded/geosharded/serverless/flex) |
| | `AtlasDatabaseUser` | MongoDB users + roles |
| | `AtlasOrgSettings` | Org-level settings |
| **Backup** | `AtlasBackupPolicy` | Backup policy definitions |
| | `AtlasBackupSchedule` | Bind a policy + schedule to a deployment |
| **Network** | `AtlasIPAccessList` | Independent IP access list entries |
| | `AtlasNetworkContainer` | Network container (VPC-equivalent) |
| | `AtlasNetworkPeering` | VPC peering connection |
| | `AtlasPrivateEndpoint` | PrivateLink/PSC endpoint |
| **Security** | `AtlasCustomRole` | Custom DB role |
| | `AtlasFederatedAuth` | SAML/OIDC federation config |
| **Data / Search** | `AtlasDataFederation` | Federated database instance |
| | `AtlasSearchIndexConfig` | Search/Vector Search index |
| **Streams** | `AtlasStreamConnection` | Stream source/sink |
| | `AtlasStreamInstance` | Stream Processing Instance |
| **Teams / Integrations** | `AtlasTeam` | Atlas team |
| | `AtlasThirdPartyIntegration` | Datadog/Slack/PagerDuty |

### Installation methods

**Helm (recommended):**
```bash
helm repo add mongodb https://mongodb.github.io/helm-charts
helm install atlas-operator mongodb/mongodb-atlas-operator \
  --namespace atlas-operator-system \
  --create-namespace \
  --set objectDeletionProtection=true
```

**Atlas CLI (zero-config bootstrap):**
```bash
# Auto-installs operator + creates API key + writes Secret into K8s
atlas kubernetes operator install \
  --orgId $ATLAS_ORG_ID \
  --projectName "my-project" \
  --import   # import existing Atlas project into K8s
```

**OperatorHub (OpenShift / Kubernetes):**
```bash
kubectl apply -f https://operatorhub.io/install/mongodb-atlas-kubernetes.yaml
```

**Raw manifests (CD-friendly):**
```bash
kubectl apply -f https://raw.githubusercontent.com/mongodb/mongodb-atlas-kubernetes/v2.14.0/deploy/all-in-one.yaml
```

### Authentication: create the Atlas connection Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: atlas-credentials
  namespace: app-team
  labels:
    atlas.mongodb.com/type: "credentials"  # IMPORTANT: makes operator discover it
stringData:
  # Service Account (preferred) — operator must be v2.5+
  clientId:     "mdb_sa_id_..."
  clientSecret: "mdb_sa_sc_..."
  # OR Programmatic API key
  # orgId:      "5e..."
  # publicKey:  "abcdefgh"
  # privateKey: "12345678-90ab-cdef-1234-567890abcdef"
```

### CRD example: AtlasProject + AtlasDeployment + AtlasDatabaseUser

```yaml
apiVersion: atlas.mongodb.com/v1
kind: AtlasProject
metadata:
  name: ecommerce-prod
  namespace: app-team
spec:
  name: "ecommerce-prod"
  connectionSecret:
    name: atlas-credentials
  # Independent CRDs — preferred — point to this project via projectRef
---
apiVersion: atlas.mongodb.com/v1
kind: AtlasDeployment
metadata:
  name: prod-cluster
  namespace: app-team
spec:
  projectRef:
    name: ecommerce-prod
    namespace: app-team
  deploymentSpec:
    name: prod-cluster
    clusterType: REPLICASET
    backupEnabled: true
    mongoDBMajorVersion: "8.0"
    replicationSpecs:
      - regionConfigs:
          - providerName: AWS
            regionName: US_EAST_1
            priority: 7
            electableSpecs:
              instanceSize: M30
              nodeCount: 3
            autoScaling:
              compute:
                enabled: true
                minInstanceSize: M30
                maxInstanceSize: M60
              diskGB:
                enabled: true
---
apiVersion: atlas.mongodb.com/v1
kind: AtlasDatabaseUser
metadata:
  name: app-user
  namespace: app-team
spec:
  projectRef:
    name: ecommerce-prod
    namespace: app-team
  username: app-user
  databaseName: admin
  passwordSecretRef:
    name: app-user-password
  roles:
    - roleName: readWrite
      databaseName: ecommerce
```

### Subobject CRDs vs Independent CRDs (deprecation alert)

Pre-v2.6 AKO embedded resources like network peering, database users, integrations, and teams **inside** `AtlasProject.spec.*` subobjects. Starting with **v2.6**, these became **independent CRDs** (`AtlasNetworkPeering`, `AtlasIPAccessList`, etc.) referenced by `projectRef`. The subobject form is **deprecated** and will be removed in a later release.

**Why this matters:** Subobject-only ownership creates ownership conflicts when multiple teams manage parts of the same project (e.g., platform team owns AtlasProject, app teams own database users). Independent CRDs let you split RBAC across namespaces.

**Migration path:**
1. Add `mongodb.com/atlas-reconciliation-policy: "skip"` to the parent AtlasProject metadata to pause reconciliation
2. Create the new independent CRDs (e.g., AtlasIPAccessList, AtlasNetworkPeering)
3. Remove the corresponding subobjects from AtlasProject.spec
4. Remove the skip annotation; resume reconciliation
5. Verify with the dry-run mode (see below) that no deletion is planned

### Dry-run mode (v2.8+)

```bash
# Run AKO as a Job with --dry-run flag
kubectl create job atlas-dryrun-$(date +%s) \
  --image=mongodb/mongodb-atlas-kubernetes-operator:2.14.0 \
  --image-pull-policy=Always \
  -- /manager --dry-run
# Then inspect events for "DryRun" entries
kubectl get events -A --field-selector=reason=DryRun
```

The operator emits events for every POST/PATCH/PUT/DELETE it **would** call against the Atlas Admin API. Critical for staged upgrades — run dry-run before an operator version upgrade to surface unintended subobject vs. independent CRD reconciliation conflicts.

### Deletion protection (default since v2.0)

As of v2.0, **deleting a custom resource in Kubernetes no longer deletes the underlying Atlas resource**. The operator instead releases ownership; the Atlas resource remains but is unmanaged.

```yaml
# Override per-resource:
metadata:
  annotations:
    mongodb.com/atlas-resource-policy: "delete"  # cascade delete to Atlas
    # or
    mongodb.com/atlas-resource-policy: "keep"   # explicitly preserve
```

```bash
# Override globally on operator install
helm install atlas-operator mongodb/mongodb-atlas-operator \
  --set objectDeletionProtection=false  # restore pre-v2.0 behavior
```

### Reconciliation skip annotation

```yaml
metadata:
  annotations:
    mongodb.com/atlas-reconciliation-policy: "skip"
```

Pauses the operator from reconciling that one resource until the annotation is removed. Use cases:
- Migrating subobject → independent CRDs
- Pausing during incident response while running manual Admin API repairs
- Holding a stale spec while you investigate drift

---

## Tool 3: Atlas CLI

The Atlas CLI (`atlas`) is MongoDB's official command-line tool. Distinct from `mongosh` (which connects to a deployment) — `atlas` manages the Atlas control plane.

### Install

```bash
# macOS
brew install mongodb-atlas-cli

# Debian/Ubuntu
sudo apt-get install mongodb-atlas

# RHEL/CentOS
sudo yum install mongodb-atlas

# Windows
choco install mongodb-atlas

# Verify
atlas --version
```

### Auth + profiles

```bash
# Interactive setup
atlas auth login      # opens browser; OIDC device flow
# OR scripted
atlas config init     # prompts for org/project/keys
# OR pure env
export MONGODB_ATLAS_PUBLIC_KEY=...
export MONGODB_ATLAS_PRIVATE_KEY=...
export MONGODB_ATLAS_PROJECT_ID=...

# Named profiles (one per env)
atlas config set --profile staging public_api_key  abc...
atlas config set --profile staging private_api_key 12345...
atlas config set --profile staging project_id      5e...

atlas clusters list --profile staging
atlas clusters describe prod-us --profile prod -o json | jq '.mongoDBVersion'
```

Profile config persists at `~/.config/atlas/config.toml`.

### Common scripting workflows

```bash
# Create a cluster from a JSON config file
atlas clusters create --file cluster-config.json

# Pause/resume — common cost-saving pattern in non-prod
atlas clusters pause  prod-us
atlas clusters start  prod-us

# Snapshot ops
atlas backups snapshots create     prod-us --desc "pre-upgrade snapshot"
atlas backups snapshots list       prod-us --output json | jq '.results[0].id'
atlas backups restores start automated --clusterName prod-us --snapshotId 5e...

# Network access in CI
atlas accessLists create $RUNNER_IP --type ipAddress --comment "ci-runner-$BUILD_ID"
# Always undo at teardown:
atlas accessLists delete $RUNNER_IP --force

# DB user lifecycle
atlas dbusers create atlasAdmin --username svc --password "$PASS"
atlas dbusers delete svc --force

# Export Atlas state into Kubernetes manifests (operator handoff)
atlas kubernetes config generate --projectId $PROJ > atlas-resources.yaml
atlas kubernetes config apply    --projectId $PROJ   # apply directly to current kubectl context
```

### Atlas CLI as a Terraform companion

The Atlas CLI has a **Terraform plugin** that generates `mongodbatlas_advanced_cluster` HCL from existing clusters — the canonical way to import existing infrastructure into Terraform:

```bash
atlas plugin install mongodb/atlas-cli-plugin-terraform
atlas terraform generate \
  --projectId $PROJ \
  --clusterName prod-us \
  > prod-us.tf
```

This preserves the cluster topology cleanly and avoids the messy default of `terraform plan -generate-config-out`.

---

## Tool 4: Atlas Admin API v2 (direct REST)

When IaC tools haven't caught up to a new Atlas feature, you fall back to direct REST. Same Service Account or API key auth as everything else.

### Required header: API version

```bash
curl -X GET https://cloud.mongodb.com/api/atlas/v2/groups \
  --user "$PUBLIC_KEY:$PRIVATE_KEY" --digest \
  -H "Accept: application/vnd.atlas.2024-05-30+json"
```

**Critical:** the `Accept: application/vnd.atlas.YYYY-MM-DD+json` header pins the API version. Atlas Admin API v2 uses date-versioned media types. If you omit the date, you get the **earliest** stable version which may be missing fields you need.

### Example: provision a cluster with curl + jq

```bash
PROJECT_ID="..."
TOKEN=$(curl -sX POST https://cloud.mongodb.com/api/oauth/token \
  --user "$CLIENT_ID:$CLIENT_SECRET" \
  -d 'grant_type=client_credentials' | jq -r '.access_token')

curl -X POST https://cloud.mongodb.com/api/atlas/v2/groups/$PROJECT_ID/clusters \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.atlas.2024-05-30+json" \
  -H "Content-Type: application/vnd.atlas.2024-05-30+json" \
  -d '{
    "name": "scripted-cluster",
    "clusterType": "REPLICASET",
    "mongoDBMajorVersion": "8.0",
    "backupEnabled": true,
    "replicationSpecs": [{
      "regionConfigs": [{
        "providerName": "AWS",
        "regionName": "US_EAST_1",
        "priority": 7,
        "electableSpecs": { "instanceSize": "M30", "nodeCount": 3 }
      }]
    }]
  }'
```

### Common endpoints

| Operation | Endpoint |
|---|---|
| List orgs | `GET /orgs` |
| List org's projects | `GET /orgs/{ORG_ID}/groups` |
| Create project | `POST /groups` (body: `{name, orgId}`) |
| List clusters | `GET /groups/{PROJECT_ID}/clusters` |
| Create cluster | `POST /groups/{PROJECT_ID}/clusters` |
| Modify cluster | `PATCH /groups/{PROJECT_ID}/clusters/{NAME}` |
| Delete cluster | `DELETE /groups/{PROJECT_ID}/clusters/{NAME}` |
| List DB users | `GET /groups/{PROJECT_ID}/databaseUsers` |
| Add IP entry | `POST /groups/{PROJECT_ID}/accessList` |
| Trigger snapshot | `POST /groups/{PROJECT_ID}/clusters/{NAME}/backup/snapshots` |
| List snapshots | `GET /groups/{PROJECT_ID}/clusters/{NAME}/backup/snapshots` |

**Project ID = Group ID** — the API still uses the legacy term `groups/{GROUP_ID}` in URL paths; Atlas UI renamed it to "Project" years ago but the API path kept the old name for compatibility.

### Pagination

Atlas Admin API uses query parameters `pageNum=1&itemsPerPage=100` (max 500). The response envelope is:
```json
{ "results": [...], "totalCount": 1234, "links": [{"rel":"next","href":"..."}] }
```

### Rate limits

Service Accounts: 1000 req/min per Service Account.
Programmatic API keys: 100 req/min per key pair.
Hitting the limit returns 429 with a `Retry-After` header. Service Accounts are not just preferred for security — they have a **10x higher rate limit**.

---

## Tool 5: Pulumi `mongodbatlas` Provider

Pulumi's Atlas provider is a TF-bridge over the official Terraform provider, so resource parity is essentially 1:1. You get the same fields and behavior but in TypeScript/Python/Go/.NET/Java.

### Install

```bash
# TypeScript / JavaScript
npm install @pulumi/mongodbatlas

# Python
pip install pulumi-mongodbatlas

# Go
go get github.com/pulumi/pulumi-mongodbatlas/sdk/v3/go/mongodbatlas

# .NET
dotnet add package Pulumi.Mongodbatlas
```

### TypeScript example

```typescript
import * as mongodbatlas from "@pulumi/mongodbatlas";

const project = new mongodbatlas.Project("ecommerce-prod", {
  orgId: process.env.ATLAS_ORG_ID!,
  name:  "ecommerce-prod",
});

const cluster = new mongodbatlas.AdvancedCluster("prod-us", {
  projectId:           project.id,
  name:                "prod-us",
  clusterType:         "REPLICASET",
  backupEnabled:       true,
  mongoDbMajorVersion: "8.0",
  replicationSpecs: [{
    regionConfigs: [{
      providerName: "AWS",
      regionName:   "US_EAST_1",
      priority:     7,
      electableSpecs: { instanceSize: "M30", nodeCount: 3 },
      autoScaling: {
        computeEnabled:           true,
        computeMinInstanceSize:   "M30",
        computeMaxInstanceSize:   "M60",
        computeScaleDownEnabled:  true,
        diskGbEnabled:            true,
      },
    }],
  }],
});

export const connectionString = cluster.connectionStrings;
```

### Authentication

Configure via Pulumi config or env vars (same names as Terraform):

```bash
pulumi config set --secret mongodbatlas:clientId     $ATLAS_CLIENT_ID
pulumi config set --secret mongodbatlas:clientSecret $ATLAS_CLIENT_SECRET
```

### When to prefer Pulumi over Terraform

- Your team already uses Pulumi for non-Atlas infra (avoid mixed-tool overhead)
- You want loops/conditionals/typing without HCL acrobatics
- You're generating cluster configs from external data sources at runtime
- You need to integrate with Pulumi-native automation (Pulumi Automation API for ephemeral envs)

**When to stick with Terraform:** community examples, Atlas-specific guides, and Atlas CLI Terraform-plugin output are all HCL. The Pulumi version trails by 1-2 weeks on new resource releases (bridge regeneration cycle).

---

## Tool 6: AWS CloudFormation Atlas Resources

MongoDB publishes **third-party CloudFormation resources** under the `MongoDB::Atlas::*` namespace. The repo is `mongodb/mongodbatlas-cloudformation-resources`. As of 2026, **33+ resources** are available.

### Activation (one-time, per AWS account + region)

CloudFormation third-party resources are not pre-installed. You must activate each resource type in each region where you intend to use it:

```bash
# Activate the cluster resource in us-east-1
aws cloudformation activate-type \
  --type RESOURCE \
  --type-name MongoDB::Atlas::Cluster \
  --publisher-id bb989456c78c398a858fef18f2ca1bfc1fbba082 \
  --region us-east-1

# Then create the secret holding your Atlas credentials
aws secretsmanager create-secret \
  --name cfn/atlas/profile/default \
  --secret-string '{"PublicKey":"abc","PrivateKey":"def"}'
```

### Example CloudFormation template

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Resources:
  AtlasProject:
    Type: MongoDB::Atlas::Project
    Properties:
      Name: ecommerce-prod
      OrgId: !Ref AtlasOrgId
      Profile: default

  AtlasCluster:
    Type: MongoDB::Atlas::Cluster
    Properties:
      Profile: default
      ProjectId: !GetAtt AtlasProject.Id
      Name: prod-us
      ClusterType: REPLICASET
      MongoDBMajorVersion: "8.0"
      BackupEnabled: true
      ReplicationSpecs:
        - NumShards: 1
          AdvancedRegionConfigs:
            - ProviderName: AWS
              RegionName: US_EAST_1
              Priority: 7
              ElectableSpecs: { InstanceSize: M30, NodeCount: 3 }
```

### Common Atlas CFN resource types

`MongoDB::Atlas::Project`, `::Cluster`, `::DatabaseUser`, `::ProjectIpAccessList`, `::NetworkPeering`, `::PrivateEndpointService`, `::CloudBackupSchedule`, `::EncryptionAtRest`, `::CustomDBRole`, `::ServerlessInstance` (legacy), `::FlexCluster`, `::Search Index`, `::StreamInstance`, `::Team`, `::ThirdPartyIntegration`, etc.

### When CloudFormation Atlas resources make sense

- Your AWS team standardizes on CloudFormation as the AWS-only IaC
- You're inside AWS Control Tower or AWS Service Catalog
- You need AWS Partner Solutions Quick Start templates for Atlas + AWS combos (SageMaker, MEAN Stack on Fargate, etc.)

**Friction points:**
- Activation per region per account is annoying at scale (~33 activate-type calls × N regions)
- Third-party publisher trust prompt confuses non-admins
- Stack drift detection on third-party resources is less mature than native AWS resources
- IAM permissions for the resource handler require `iam:GetRole` + the Atlas Profile Secrets Manager secret read

---

## Tool 7: AWS CDK — `awscdk-resources-mongodbatlas`

The AWS CDK package `awscdk-resources-mongodbatlas` wraps the CloudFormation third-party resources in L1/L2 CDK constructs. Available for TypeScript/JavaScript, with Python/Java/Go/.NET support promised.

```bash
npm install awscdk-resources-mongodbatlas
```

### TypeScript CDK example

```typescript
import * as cdk from "aws-cdk-lib";
import * as atlas from "awscdk-resources-mongodbatlas";

class AtlasStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string) {
    super(scope, id);

    const project = new atlas.CfnProject(this, "EcommerceProject", {
      profile: "default",
      name:    "ecommerce-prod",
      orgId:   process.env.ATLAS_ORG_ID!,
    });

    new atlas.CfnCluster(this, "ProdCluster", {
      profile:             "default",
      projectId:           project.attrId,
      name:                "prod-us",
      clusterType:         "REPLICASET",
      mongoDbMajorVersion: "8.0",
      backupEnabled:       true,
      replicationSpecs: [{
        numShards: 1,
        advancedRegionConfigs: [{
          providerName: "AWS",
          regionName:   "US_EAST_1",
          priority:     7,
          electableSpecs: { instanceSize: "M30", nodeCount: 3 },
        }],
      }],
    });
  }
}
```

### When CDK is the right choice

You already use CDK for everything else (Lambda, API Gateway, ECS) and want one mental model. The L1 constructs are tight wrappers around CFN — same activation requirements, same Profile + Secrets Manager pattern.

---

## Decision Methodology: Choosing the Right Tool

```
┌─────────────────────────────────────────────────────────────────┐
│           Where does your platform team already live?           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
   ┌────▼────┐           ┌─────▼─────┐         ┌──────▼──────┐
   │Terraform│           │ Kubernetes │         │   AWS-only  │
   │ already │           │ everywhere │         │ shop / CFN  │
   └────┬────┘           └─────┬──────┘         └──────┬──────┘
        │                      │                       │
   ┌────▼────┐           ┌─────▼─────┐         ┌──────▼──────┐
   │mongodb/ │           │   Atlas   │         │  MongoDB::  │
   │mongodb- │           │Kubernetes │         │   Atlas::   │
   │  atlas  │           │ Operator  │         │  CFN types  │
   │provider │           │  (AKO)    │         │  + CDK L1   │
   └─────────┘           └───────────┘         └─────────────┘

   Pulumi: pick if your team already runs Pulumi. Parity with Terraform via bridge.
   Atlas CLI: scripting + glue + Terraform/AKO bootstrap, never the primary tool.
   Direct API: 6-month grace for new Atlas features not yet in IaC tools.
```

### Decision matrix

| Factor | Terraform | AKO | CloudFormation | Pulumi | CDK |
|---|---|---|---|---|---|
| **Feature coverage** | 95% | 90% | 85% | 95% | 85% |
| **New-feature lag** | 1-2 weeks | 1-3 months | 3-6 months | 2-4 weeks | 3-6 months |
| **Multi-cloud Atlas** | excellent | excellent | AWS-only | excellent | AWS-only |
| **GitOps friendliness** | OK (TF Cloud) | excellent | OK (Stacks) | OK (Pulumi Cloud) | OK |
| **Imperative escape hatch** | no | no | no | yes (Automation API) | yes |
| **Drift detection** | `terraform plan` | reconcile loop | CFN drift | `pulumi preview` | CFN drift |
| **Learning curve** | HCL | YAML + K8s | YAML + JSON | code | code |
| **Best for** | platform team | app teams + DevOps | AWS-bound platform | code-fluent platform | AWS CDK shops |

### Mixing tools in practice

A common mature pattern:
- **Terraform:** platform team owns projects, clusters, network peering/PrivateLink, encryption-at-rest, federated auth — i.e., everything in the "expensive to misconfigure" set
- **AKO:** app teams own their own database users, search indexes, third-party integrations, alert configs — within projects already created by Terraform
- **Atlas CLI:** ad hoc scripts in runbooks, snapshot/restore operations, CI access list additions
- **Admin API:** only for features < 6 months old that haven't landed in Terraform yet

The cross-tool ownership boundary should be enforced by **least-privilege Service Accounts**: the platform team's SA has org-scope, the app team's SA has project-scope and limited resource types.

---

## Practical Patterns

### Pattern 1: Multi-environment Terraform (recommended: directories)

HashiCorp officially **does not recommend** CLI workspaces for env separation. Use directories instead:

```
infra/
├── modules/
│   └── atlas-cluster/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── envs/
│   ├── dev/
│   │   ├── main.tf          # module "cluster" { source = "../../modules/atlas-cluster"; instance_size = "M10" }
│   │   ├── backend.tf        # backend "s3" { bucket = "tf-state-dev"; ... }
│   │   └── terraform.tfvars
│   ├── staging/
│   │   ├── main.tf
│   │   ├── backend.tf
│   │   └── terraform.tfvars
│   └── prod/
│       ├── main.tf           # instance_size = "M60"; prevent_destroy = true
│       ├── backend.tf
│       └── terraform.tfvars
```

**Why directories beat workspaces:**
- Each env has its own backend (separate S3 bucket + DynamoDB lock table → separate IAM)
- `prod/` can carry `lifecycle { prevent_destroy = true }` blocks the others don't
- Modules accept different variable shapes without hidden `terraform.workspace` interpolation
- RBAC: only platform SREs can push to `prod/`; dev/ is wide open

### Pattern 2: Service Account per environment + per tool

**Don't share Service Accounts between environments or tools.** Even if it's tempting.

```
atlas-org/
├── sa-terraform-prod          (project: ecommerce-prod, role: Project Owner)
├── sa-terraform-staging       (project: ecommerce-staging, role: Project Owner)
├── sa-terraform-dev           (project: ecommerce-dev, role: Project Owner)
├── sa-ako-prod                (project: ecommerce-prod, role: Project Cluster Manager + DB User Admin)
├── sa-ci-runner               (org-scope: API Key Access List + Project Read; ephemeral IPs)
└── sa-readonly-monitoring     (org-scope: Project Read; for Datadog)
```

This pattern means a leaked credential blast-radius is bounded to one env + one tool. SA secret rotation can be done per-env without lockstep risk.

### Pattern 3: Network access list IP coordination

The `mongodbatlas_project_ip_access_list` resource has a footgun: the API key has **no resource-level ownership** of the entry. If two Terraform states both manage the same CIDR `10.0.0.0/8`, whichever runs second will detect the entry already exists; whichever applies later may revoke the other team's access.

**Mitigations:**
- Strict ownership: only one Terraform state controls IP access for a given project
- Use `comment` fields to namespace ownership: `"managed-by:platform-tf-state"` vs `"managed-by:app-team-ako"`
- If multiple tools must each add entries, use **distinct CIDR slices** rather than overlapping blocks
- Audit periodically with `atlas accessLists list -o json` and reconcile against config

### Pattern 4: Importing existing infra into Terraform

```bash
# Method A: Atlas CLI Terraform plugin (cleanest)
atlas plugin install mongodb/atlas-cli-plugin-terraform
atlas terraform generate --projectId $PROJ --clusterName prod-us > prod-us.tf

# Method B: Native terraform import block (modern Terraform 1.5+)
cat > import.tf <<EOF
import {
  to = mongodbatlas_advanced_cluster.prod_us
  id = "${PROJECT_ID}-prod-us"
}
EOF
terraform plan -generate-config-out=generated.tf
# Inspect generated.tf — usually noisier than the Atlas CLI plugin output
```

After import, **immediately run `terraform plan` and expect zero changes**. If non-zero changes appear, the imported state has drift you need to resolve before any future apply.

### Pattern 5: Backup compliance policy is one-way

`mongodbatlas_backup_compliance_policy` is a **one-time enable**. Once applied, the policy cannot be disabled via API or UI — only by contacting MongoDB Support. This is intentional for regulated workloads. **Never** apply this resource in a dev environment as a learning exercise.

```hcl
resource "mongodbatlas_backup_compliance_policy" "regulated" {
  project_id          = mongodbatlas_project.regulated.id
  authorized_email    = "compliance-officer@example.com"
  authorized_user_first_name = "Sec"
  authorized_user_last_name  = "Officer"
  copy_protection_enabled = true

  on_demand_policy_item {
    frequency_interval = 0
    frequency_type     = "ondemand"
    retention_unit     = "weeks"
    retention_value    = 4
  }

  lifecycle {
    prevent_destroy = true
    # Document the irreversibility in code:
    # WARNING: Once applied, this resource cannot be removed without MongoDB Support
  }
}
```

### Pattern 6: Tags + cost allocation

Tag every resource for cost attribution. Atlas exposes tags in the billing API and in Atlas project resource limits.

```hcl
resource "mongodbatlas_advanced_cluster" "this" {
  # ...
  tags {
    key   = "environment"
    value = var.environment   # dev/staging/prod
  }
  tags {
    key   = "owner"
    value = var.owning_team
  }
  tags {
    key   = "cost_center"
    value = var.cost_center
  }
  tags {
    key   = "managed_by"
    value = "terraform"
  }
}
```

---

## Anti-Patterns (10 most common)

### 1. The "I'll just fix it in the UI" anti-pattern

The most common, most damaging IaC anti-pattern. Someone makes a "quick fix" in the Atlas UI (a database user, an IP allowlist entry, a backup retention bump). The next `terraform apply` reverts it. Drift accumulates silently across multiple manual changes.

**Mitigation:** scheduled drift detection (see GitHub Actions example earlier), and Service-Account scoping so only the IaC tool's SA can modify production. Block production manual changes by giving humans only `Project Read Only` in prod orgs; production write access is reserved for the SA.

### 2. Using `mongodbatlas_cluster` instead of `mongodbatlas_advanced_cluster`

`mongodbatlas_cluster` was deprecated in provider v2.0 (April 2025) and removal is imminent. Modern features (multi-cloud, asymmetric sharding, ISRS, search nodes) require `advanced_cluster`. If you're greenfield, never use the legacy resource.

### 3. AKO and Terraform managing the same Atlas resource

Don't have AKO manage an `AtlasDatabaseUser` while Terraform also manages a `mongodbatlas_database_user` for the same Mongo user. The two will fight each other on every reconciliation cycle. Pick one tool per resource type within a given project, and document the boundary.

### 4. Hardcoding `instance_size` in modules instead of variabilizing

```hcl
# BAD — copy-pasted module across envs with hardcoded values
resource "mongodbatlas_advanced_cluster" "this" {
  # ...
  electable_specs { instance_size = "M60" }   # this is now wrong in dev
}

# GOOD
variable "instance_size" { type = string }
resource "mongodbatlas_advanced_cluster" "this" {
  # ...
  electable_specs { instance_size = var.instance_size }
}
```

### 5. Pinning `version = "~> 2.0"` and never upgrading

The Atlas provider's API surface evolves with new Atlas features; staying months behind the latest version means missing schema fields and accumulating technical debt. Subscribe to the [provider's GitHub Releases](https://github.com/mongodb/terraform-provider-mongodbatlas/releases) and upgrade monthly.

### 6. Storing API keys in plaintext `.tfvars`

Always use environment variables (`MONGODB_ATLAS_CLIENT_ID/SECRET`) or a secrets backend (HashiCorp Vault, AWS Secrets Manager, Doppler). Never commit `.tfvars` containing Atlas credentials. Use `.gitignore` rigorously.

### 7. Granting `Organization Owner` to a Service Account "just to be safe"

The Atlas role model is granular for a reason. Org Owner can delete the entire org. Default new SAs to `Project Owner` on a specific project; if the SA needs to create new projects, escalate to `Organization Project Creator` rather than full Org Owner.

### 8. Provisioning Atlas Search indexes without `wait_for_index_build_completion = true`

Without the wait flag, `terraform apply` returns success while the index is still building in the background. A subsequent test that queries the index will fail. Always wait for index build on prod paths.

```hcl
resource "mongodbatlas_search_index" "this" {
  # ...
  wait_for_index_build_completion = true
}
```

### 9. Letting CRDs and Atlas state drift in AKO

When subobjects exist on `AtlasProject` and the equivalent independent CRD exists in the same namespace, the operator can flip-flop. Use the dry-run mode before any upgrade past v2.6. Migrate one resource type at a time.

### 10. Mixing tool ownership without explicit boundaries

If your team has Terraform AND AKO AND someone running scripts AND devs poking the UI, you will have drift. The fix isn't more tools — it's a written ownership table, enforced by SA scopes, with drift detection in CI.

---

## Migration Paths Between IaC Tools

### Terraform → Atlas Kubernetes Operator

For an existing Terraform-managed project that you want to hand off to app teams via K8s:

1. **Audit** what's in Terraform state. Decide what stays in Terraform (cluster, network, encryption, federated auth) vs. what moves to AKO (DB users, search indexes, integrations).
2. **Generate AKO manifests** from the live Atlas state:
   ```bash
   atlas kubernetes config generate --projectId $PROJ \
     --targetNamespace app-team \
     --includeSecrets \
     > ako-manifests.yaml
   ```
3. **Remove the migrated resources from Terraform** by using `terraform state rm` (not `terraform destroy`):
   ```bash
   terraform state rm mongodbatlas_database_user.app
   terraform state rm mongodbatlas_search_index.app_search
   # Then remove the resource blocks from .tf files
   ```
4. **Apply AKO manifests** with the operator in dry-run mode first:
   ```bash
   kubectl apply -f ako-manifests.yaml --dry-run=server
   kubectl apply -f ako-manifests.yaml
   ```
5. **Verify** ownership by checking annotations and events on the new CRs.

### AKO → Terraform (rarer, usually for compliance reasons)

1. Add `mongodb.com/atlas-resource-policy: "keep"` to every CR you're migrating
2. Delete the CRs (`kubectl delete -f manifests.yaml`); Atlas resources stay
3. Run `atlas terraform generate` to produce HCL
4. `terraform import` each resource into the new state
5. `terraform plan` — expect zero changes

### CloudFormation → Terraform

CloudFormation third-party Atlas resources aren't directly importable into Terraform. The workflow is:

1. Use the Atlas CLI Terraform plugin to generate HCL from live state
2. Delete the CFN stack with **DeletionPolicy: Retain** on every Atlas resource:
   ```yaml
   AtlasCluster:
     Type: MongoDB::Atlas::Cluster
     DeletionPolicy: Retain  # keeps the Atlas resource when stack is deleted
     Properties: {...}
   ```
3. Once Atlas resources are detached, run `terraform import` to bring them into Terraform state

---

## Troubleshooting

### "Error: invalid_client" on Terraform plan

Service Account Client ID/Secret is wrong, or the SA has been deleted. Check:
```bash
curl -X POST https://cloud.mongodb.com/api/oauth/token \
  --user "$CLIENT_ID:$CLIENT_SECRET" \
  -d 'grant_type=client_credentials'
```
If this returns 401, the SA credentials are bad. If it returns a token but Terraform still fails, the SA doesn't have permission on the target project.

### `terraform apply` hangs forever on cluster creation

Cluster provisioning takes 7-15 minutes. Terraform polls every 30s. If it hangs past 30 minutes, check:
- Atlas Status Page for incidents
- The Atlas UI to see if the cluster is in a `failed` state (rare but possible)
- Run with `TF_LOG=DEBUG terraform apply` to see API responses

### AKO operator pod is `CrashLoopBackOff`

Common causes:
1. Missing or malformed `atlas-credentials` Secret — check the label `atlas.mongodb.com/type: "credentials"` is present
2. Invalid SA credentials (test via curl as above)
3. RBAC issue — operator service account lacks permission to read Secrets in target namespaces
4. Version skew — operator container version doesn't match the CRD schema versions

```bash
kubectl logs -n atlas-operator-system deploy/atlas-operator
kubectl describe pod -n atlas-operator-system -l app.kubernetes.io/name=mongodb-atlas-operator
```

### Persistent diff on `disk_size_gb` in terraform plan

Atlas auto-scales storage; the field becomes computed at runtime. Use `lifecycle { ignore_changes = [disk_size_gb] }` in your config to suppress the diff.

### `Error: resource already exists in Atlas` on apply

Someone (or another tool) created the resource outside Terraform. Either:
- Import it: `terraform import mongodbatlas_advanced_cluster.this <project_id>-<cluster_name>`
- Delete the duplicate manually if it's stale
- Rename the Terraform resource to avoid the collision

### CloudFormation third-party resource registration fails

Verify the publisher ID and re-activate:
```bash
aws cloudformation describe-type \
  --type-name MongoDB::Atlas::Cluster \
  --type RESOURCE \
  --publisher-id bb989456c78c398a858fef18f2ca1bfc1fbba082
```
If it returns "type not found", run `activate-type` again. If region-specific issues, repeat per region.

### AKO subobject + independent CRD conflict

After enabling independent CRDs (e.g., `AtlasNetworkPeering`), if you didn't remove the corresponding subobject from `AtlasProject.spec.networkPeers`, the operator alternates between the two configurations on each reconcile. Use dry-run to detect:
```bash
kubectl create job ako-dryrun --image=mongodb/mongodb-atlas-kubernetes-operator:2.14.0 -- /manager --dry-run
kubectl get events -A --field-selector reason=DryRun
```
Then either remove the subobject or annotate with `atlas-reconciliation-policy: skip` while you reconcile.

---

## References

1. [MongoDB Atlas Terraform Provider on Registry](https://registry.terraform.io/providers/mongodb/mongodbatlas/latest)
2. [terraform-provider-mongodbatlas GitHub](https://github.com/mongodb/terraform-provider-mongodbatlas)
3. [Atlas Kubernetes Operator Docs (current)](https://www.mongodb.com/docs/atlas/operator/current/)
4. [Atlas Kubernetes Operator GitHub](https://github.com/mongodb/mongodb-atlas-kubernetes)
5. [Independent CRDs Guide](https://www.mongodb.com/docs/atlas/operator/current/ak8so-independent-crd/)
6. [AKO Dry Run Mode](https://www.mongodb.com/docs/atlas/operator/current/ak8so-dry-run/)
7. [Atlas CLI Docs](https://www.mongodb.com/docs/atlas/cli/current/)
8. [Atlas CLI `kubernetes config generate`](https://www.mongodb.com/docs/atlas/cli/current/command/atlas-kubernetes-config-generate/)
9. [Atlas Admin API v2 Documentation](https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/)
10. [Atlas Admin API Authentication](https://www.mongodb.com/docs/atlas/api/api-authentication/)
11. [Atlas Service Accounts via OAuth 2.0 Announcement](https://www.mongodb.com/company/blog/product-release-announcements/introducing-mongodb-atlas-service-accounts-via-oauth-2-0)
12. [Generate Service Account Token](https://www.mongodb.com/docs/atlas/api/service-accounts/generate-oauth2-token/)
13. [Pulumi mongodbatlas Provider](https://www.pulumi.com/registry/packages/mongodbatlas/)
14. [pulumi-mongodbatlas GitHub](https://github.com/pulumi/pulumi-mongodbatlas)
15. [MongoDB Atlas CloudFormation Resources GitHub](https://github.com/mongodb/mongodbatlas-cloudformation-resources)
16. [Atlas + CloudFormation CDK GA Announcement](https://www.mongodb.com/blog/post/atlas-integrations-aws-cloud-formation-cdk-now-generally-available)
17. [awscdk-resources-mongodbatlas GitHub](https://github.com/mongodb/awscdk-resources-mongodbatlas)
18. [AWS Partner Solutions Atlas Quick Start](https://aws-ia.github.io/cfn-ps-mongodb-atlas/)
19. [Terraform Cluster → Advanced Cluster Migration Guide](https://registry.terraform.io/providers/mongodb/mongodbatlas/latest/docs/guides/cluster-to-advanced-cluster-migration-guide)
20. [Terraform Advanced Cluster v2.0 Migration Guide](https://registry.terraform.io/providers/mongodb/mongodbatlas/2.0.0/docs/guides/migrate-to-advanced-cluster-2.0)
21. [HashiCorp on Drift Detection](https://www.hashicorp.com/en/blog/detecting-and-managing-drift-with-terraform)
22. [Terraform Manage Resource Drift Tutorial](https://developer.hashicorp.com/terraform/tutorials/state/resource-drift)
23. [AKO Helm Chart on Artifact Hub](https://artifacthub.io/packages/helm/mongodb-helm-charts/mongodb-atlas-operator)
24. [AKO Operator Hub Listing](https://operatorhub.io/operator/mongodb-atlas-kubernetes)
25. [Import Atlas Projects into AKO](https://www.mongodb.com/docs/atlas/operator/current/ak8so-import-projects/)
26. [Atlas Workload Identity Federation with OAuth 2.0](https://www.mongodb.com/docs/atlas/workload-oidc/)
27. [Atlas Architecture Center: Authentication Guidance](https://www.mongodb.com/docs/atlas/architecture/current/auth/authentication/)
28. [Atlas Admin API Service Account Auth Examples](https://github.com/mongodb-developer/atlas-admin-api-serviceaccount-auth)

---

## See Also

- `mongodb-atlas-expert` — Atlas platform overview, org/project/cluster, networking, backup
- `mongodb-atlas-iam-rbac` — Atlas IAM, Service Accounts, RBAC roles, federated auth (shares the SA auth surface with this skill)
- `mongodb-atlas-azure` — Azure-specific PrivateLink, Entra ID, Bicep IaC, AKS + AKO
- `mongodb-atlas-gcp` — GCP-specific PSC, Workload Identity Federation, Terraform GCP provider
- `mongodb-aws-networking` — AWS-specific VPC peering, PrivateLink, AWS CFN Atlas
- `mongodb-atlas-flex-serverless` — Flex tier IaC (mongodbatlas_flex_cluster), M2/M5/Serverless EOL
- `mongodb-atlas-multicloud` — Multi-cloud replica sets, global clusters via IaC
- `mongodb-drivers-k8s` — MongoDB Community/Enterprise Operator (runs MongoDB *inside* K8s — distinct from AKO managing Atlas)
- `mongodb-developer` — Atlas CLI and Atlas Admin API for application developers
- `cicd-pipelines` — CI/CD pipeline patterns (Terraform + GitHub Actions + drift detection)
