<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-terraform` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

# MongoDB Atlas Terraform Provider

## Overview

The `mongodb/mongodbatlas` Terraform provider lets you manage the full lifecycle of MongoDB Atlas infrastructure as code. It covers clusters (dedicated, Flex replacing legacy serverless), networking (VPC peering, Private Link), project/org management, database users, search indexes, encryption at rest, backups, and alert configurations. As of September 2025, provider **v2.0.0** is the current major version with semantic versioning guarantees — minor and patch releases will not introduce breaking changes.

**Registry:** `registry.terraform.io/providers/mongodb/mongodbatlas`
**GitHub:** `github.com/mongodb/terraform-provider-mongodbatlas`

## When to Use This Skill

- Provisioning Atlas clusters, networking, or users via Terraform
- Migrating from `mongodbatlas_cluster` (v1 legacy) to `mongodbatlas_advanced_cluster` (v2 preferred)
- Debugging provider v1 → v2 breaking changes and upgrade errors
- Setting up Private Link, VPC peering, or network containers
- Configuring encryption at rest (AWS KMS, Azure Key Vault, GCP KMS)
- Writing search index resources or search node deployments
- Designing module interfaces for reusable Atlas IaC patterns
- Configuring Atlantis or Terraform Cloud for Atlas API key management

## When NOT to Use This Skill

- Using Pulumi for MongoDB Atlas (use the Pulumi `mongodbatlas` package instead)
- Using Crossplane for MongoDB Atlas (use the Crossplane MongoDB Atlas provider)
- Using the Atlas Kubernetes Operator (`mongodbatlas-kubernetes-operator` skill covers that)
- CloudFormation / CDK stacks for Atlas resources

---

## 1. Provider Setup and Authentication

### Required Providers Block

Pin a specific minor version to avoid unplanned upgrades:

```hcl
# versions.tf
terraform {
  required_providers {
    mongodbatlas = {
      source  = "mongodb/mongodbatlas"
      version = "~> 2.7"
    }
  }
  required_version = ">= 1.5"
}
```

For v1.x users not yet ready to migrate:

```hcl
version = "~> 1.21"
```

### Authentication Methods

**Method 1 — Environment Variables (recommended for CI/CD):**

```bash
export MONGODB_ATLAS_PUBLIC_KEY="your-public-key"
export MONGODB_ATLAS_PRIVATE_KEY="your-private-key"
export MONGODB_ATLAS_ORG_ID="your-org-id"   # optional org-level default
```

Provider block with no credentials (reads from env):

```hcl
provider "mongodbatlas" {}
```

**Method 2 — Explicit in provider block (use only with secrets injection):**

```hcl
provider "mongodbatlas" {
  public_key  = var.atlas_public_key
  private_key = var.atlas_private_key
}
```

Never hard-code keys in `.tf` files. Use HashiCorp Vault, AWS Secrets Manager, or TFC workspace variables.

**Method 3 — Service Account (new in v2, recommended for production):**

Atlas supports Service Accounts with OAuth 2.0 client credentials. The provider reads `MONGODB_ATLAS_CLIENT_ID` and `MONGODB_ATLAS_CLIENT_SECRET` environment variables:

```hcl
provider "mongodbatlas" {
  client_id     = var.atlas_client_id
  client_secret = var.atlas_client_secret
}
```

**Note — AWS IAM Assumed Role (for resource-level cloud access, not provider auth):**

The provider does not authenticate to Atlas via IAM. IAM assumed roles are used by Atlas to access your AWS resources (KMS, S3 export buckets). This is configured via `mongodbatlas_cloud_provider_access_setup` and `mongodbatlas_cloud_provider_access_authorization` resources — see Section 5 for the full three-step example.

### API Key IP Access List

Programmatic API keys require IP access list entries. In production, add your Terraform Cloud / Atlantis egress IP range. You can use `0.0.0.0/0` for development but never for production.

### Multiple Provider Aliases (Multi-Org)

```hcl
provider "mongodbatlas" {
  alias       = "org_b"
  public_key  = var.org_b_public_key
  private_key = var.org_b_private_key
}

resource "mongodbatlas_project" "secondary" {
  provider = mongodbatlas.org_b
  name     = "secondary-project"
  org_id   = var.org_b_id
}
```

### Version Pinning Best Practices

- Use `~> 2.7` (allows patch updates within 2.x, blocks 3.x)
- Lock to an exact version in **production**, allow patch updates (`~> 2.7`) in dev/staging
- Run `terraform init -upgrade` explicitly when bumping the version constraint
- Check the CHANGELOG before any minor version bump for deprecation notices

---

## 2. Advanced Cluster Resource

`mongodbatlas_advanced_cluster` is the preferred resource as of provider v1.18+ and the **only** cluster resource in v2.x (`mongodbatlas_cluster` was removed).

### Minimal Single-Region Replica Set

```hcl
resource "mongodbatlas_advanced_cluster" "main" {
  project_id             = var.project_id
  name                   = "production"
  cluster_type           = "REPLICASET"
  backup_enabled         = true
  termination_protection_enabled = true

  replication_specs = [{
    region_configs = [{
      provider_name = "AWS"
      region_name   = "US_EAST_1"
      priority      = 7
      electable_specs = {
        instance_size = "M30"
        node_count    = 3
      }
    }]
  }]
}
```

### Multi-Region Replica Set (High Availability)

```hcl
resource "mongodbatlas_advanced_cluster" "ha" {
  project_id   = var.project_id
  name         = "ha-cluster"
  cluster_type = "REPLICASET"
  backup_enabled = true

  replication_specs = [{
    region_configs = [
      {
        provider_name = "AWS"
        region_name   = "US_EAST_1"
        priority      = 7
        electable_specs = {
          instance_size = "M30"
          node_count    = 3
        }
      },
      {
        provider_name = "AWS"
        region_name   = "US_WEST_2"
        priority      = 6
        electable_specs = {
          instance_size = "M30"
          node_count    = 2
        }
      }
    ]
  }]
}
```

### Sharded Cluster

Each element in `replication_specs` represents **one shard**:

```hcl
resource "mongodbatlas_advanced_cluster" "sharded" {
  project_id   = var.project_id
  name         = "sharded-prod"
  cluster_type = "SHARDED"
  backup_enabled = true

  replication_specs = [
    # Shard 1
    {
      region_configs = [{
        provider_name = "AWS"
        region_name   = "US_EAST_1"
        priority      = 7
        electable_specs = {
          instance_size = "M30"
          node_count    = 3
        }
      }]
    },
    # Shard 2
    {
      region_configs = [{
        provider_name = "AWS"
        region_name   = "US_EAST_1"
        priority      = 7
        electable_specs = {
          instance_size = "M30"
          node_count    = 3
        }
      }]
    }
  ]
}
```

### Auto-Scaling Configuration

Use `use_effective_fields = true` to eliminate `lifecycle.ignore_changes` blocks and let Atlas-managed scaling reflect correctly in state:

```hcl
resource "mongodbatlas_advanced_cluster" "autoscaled" {
  project_id           = var.project_id
  name                 = "autoscaled-cluster"
  cluster_type         = "REPLICASET"
  use_effective_fields = true

  replication_specs = [{
    region_configs = [{
      provider_name = "AWS"
      region_name   = "US_EAST_1"
      priority      = 7
      electable_specs = {
        instance_size = "M10"
        node_count    = 3
      }
      auto_scaling = {
        compute_enabled            = true
        compute_scale_down_enabled = true
        compute_min_instance_size  = "M10"
        compute_max_instance_size  = "M40"
        disk_gb_enabled            = true
      }
    }]
  }]
}
```

Without `use_effective_fields`, you need:

```hcl
lifecycle {
  ignore_changes = [
    replication_specs[0].region_configs[0].electable_specs[0].instance_size,
    replication_specs[0].region_configs[0].electable_specs[0].disk_size_gb,
  ]
}
```

### Analytics Nodes

Add `analytics_specs` inside a `region_configs` block alongside `electable_specs`:

```hcl
resource "mongodbatlas_advanced_cluster" "analytics" {
  project_id   = var.project_id
  name         = "analytics-cluster"
  cluster_type = "REPLICASET"

  replication_specs = [{
    region_configs = [{
      provider_name = "AWS"
      region_name   = "US_EAST_1"
      priority      = 7
      electable_specs = {
        instance_size = "M30"
        node_count    = 3
      }
      analytics_specs = {
        instance_size = "M30"
        node_count    = 1
      }
    }]
  }]
}
```

### Flex Cluster (Free/Shared Tier)

```hcl
resource "mongodbatlas_advanced_cluster" "flex" {
  project_id   = var.project_id
  name         = "dev-flex"
  cluster_type = "REPLICASET"

  replication_specs = [{
    region_configs = [{
      provider_name         = "FLEX"
      backing_provider_name = "AWS"
      region_name           = "US_EAST_1"
      priority              = 7
    }]
  }]
}
```

### Advanced Configuration

```hcl
advanced_configuration {
  javascript_enabled                   = false
  minimum_enabled_tls_protocol         = "TLS1_2"
  no_table_scan                        = false
  oplog_size_mb                        = 2048
  transaction_lifetime_limit_seconds   = 60
}
```

### Key Computed Outputs

```hcl
output "connection_string_srv" {
  value = mongodbatlas_advanced_cluster.main.connection_strings[0].standard_srv
}

output "cluster_id" {
  value = mongodbatlas_advanced_cluster.main.cluster_id
}

output "state" {
  value = mongodbatlas_advanced_cluster.main.state_name
}
```

Connection string types available:
- `connection_strings[0].standard` — `mongodb://` URI
- `connection_strings[0].standard_srv` — `mongodb+srv://` URI
- `connection_strings[0].private` — VPC peering URI
- `connection_strings[0].private_srv` — VPC peering SRV URI
- `connection_strings[0].private_endpoint[*].connection_string` — Private Link URI

### Import

```bash
terraform import mongodbatlas_advanced_cluster.main PROJECT_ID-CLUSTER_NAME
# Example:
terraform import mongodbatlas_advanced_cluster.main 6494919b2b3afd2b4ff2e70c-production
```

---

## 3. Networking Resources

### Network Container

A network container is a prerequisite for VPC peering. One container per region (AWS/Azure) or per project (GCP):

```hcl
resource "mongodbatlas_network_container" "aws" {
  project_id       = var.project_id
  atlas_cidr_block = "192.168.248.0/21"
  provider_name    = "AWS"
  region_name      = "US_EAST_1"
}
```

**GCP container** (one per project):

```hcl
resource "mongodbatlas_network_container" "gcp" {
  project_id       = var.project_id
  atlas_cidr_block = "192.168.0.0/18"
  provider_name    = "GCP"
}
```

**Important:** Atlas locks the CIDR block once an M10+ cluster or network peering connection exists. Plan the CIDR carefully — you cannot modify it without removing all clusters and peering connections first.

Import:
```bash
terraform import mongodbatlas_network_container.aws PROJECT_ID-CONTAINER_ID
```

### VPC Peering — AWS

Two-step: create the Atlas peering request, then accept from the AWS side.

```hcl
resource "mongodbatlas_network_peering" "aws_peer" {
  project_id            = var.project_id
  container_id          = mongodbatlas_network_container.aws.id
  provider_name         = "AWS"
  accepter_region_name  = "us-east-1"
  aws_account_id        = var.aws_account_id
  vpc_id                = var.aws_vpc_id
  route_table_cidr_block = var.aws_vpc_cidr
}

# Accept from AWS side
resource "aws_vpc_peering_connection_accepter" "accept" {
  vpc_peering_connection_id = mongodbatlas_network_peering.aws_peer.connection_id
  auto_accept               = true
}
```

### VPC Peering — Azure

```hcl
resource "mongodbatlas_network_peering" "azure_peer" {
  project_id            = var.project_id
  container_id          = mongodbatlas_network_container.azure.id
  provider_name         = "AZURE"
  azure_directory_id    = var.azure_directory_id
  azure_subscription_id = var.azure_subscription_id
  resource_group_name   = var.resource_group_name
  vnet_name             = var.vnet_name
}
```

### VPC Peering — GCP

```hcl
resource "mongodbatlas_network_peering" "gcp_peer" {
  project_id    = var.project_id
  container_id  = mongodbatlas_network_container.gcp.id
  provider_name = "GCP"
  gcp_project_id = var.gcp_project_id
  network_name   = var.gcp_network_name
}

# Reciprocal peering on GCP side requires atlas_gcp_project_id and atlas_vpc_name
# from the computed outputs of the above resource:
resource "google_compute_network_peering" "gcp_to_atlas" {
  name         = "gcp-to-atlas"
  network      = google_compute_network.app.id
  peer_network = "https://www.googleapis.com/compute/v1/projects/${mongodbatlas_network_peering.gcp_peer.atlas_gcp_project_id}/global/networks/${mongodbatlas_network_peering.gcp_peer.atlas_vpc_name}"
}
```

Peering import:
```bash
terraform import mongodbatlas_network_peering.aws_peer PROJECTID-PEERID-AWS
```

### Private Link — AWS (Three-Resource Pattern)

Dependencies must be in this order: Atlas endpoint → AWS VPC endpoint → Atlas endpoint service.

```hcl
# Step 1: Request Private Link endpoint from Atlas
resource "mongodbatlas_privatelink_endpoint" "pl" {
  project_id    = var.project_id
  provider_name = "AWS"
  region        = "US_EAST_1"
}

# Step 2: Create AWS-side VPC Interface Endpoint
resource "aws_vpc_endpoint" "mongo" {
  vpc_id              = var.vpc_id
  service_name        = mongodbatlas_privatelink_endpoint.pl.endpoint_service_name
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.subnet_ids
  security_group_ids  = [aws_security_group.mongo_pl.id]
  auto_accept         = true

  tags = { Name = "atlas-private-link" }
}

# Step 3: Register AWS endpoint with Atlas
resource "mongodbatlas_privatelink_endpoint_service" "pl_svc" {
  project_id          = mongodbatlas_privatelink_endpoint.pl.project_id
  private_link_id     = mongodbatlas_privatelink_endpoint.pl.private_link_id
  endpoint_service_id = aws_vpc_endpoint.mongo.id
  provider_name       = "AWS"
}
```

### Private Link — Azure

```hcl
resource "mongodbatlas_privatelink_endpoint" "pl_azure" {
  project_id    = var.project_id
  provider_name = "AZURE"
  region        = "US_EAST_2"
}

resource "azurerm_private_endpoint" "mongo" {
  name                = "atlas-private-endpoint"
  resource_group_name = var.resource_group_name
  location            = var.location
  subnet_id           = var.subnet_id

  private_service_connection {
    name                           = "atlas-connection"
    private_connection_resource_id = mongodbatlas_privatelink_endpoint.pl_azure.private_link_id
    is_manual_connection           = true
    request_message                = "Private Link request"
  }
}

resource "mongodbatlas_privatelink_endpoint_service" "pl_azure_svc" {
  project_id                    = var.project_id
  private_link_id               = mongodbatlas_privatelink_endpoint.pl_azure.private_link_id
  endpoint_service_id           = azurerm_private_endpoint.mongo.id
  private_endpoint_ip_address   = azurerm_private_endpoint.mongo.private_service_connection[0].private_ip_address
  provider_name                 = "AZURE"
}
```

### Private Link — GCP

GCP uses forwarding rules instead of interface endpoints:

```hcl
resource "mongodbatlas_privatelink_endpoint" "pl_gcp" {
  project_id    = var.project_id
  provider_name = "GCP"
  region        = "CENTRAL_US"
}

resource "mongodbatlas_privatelink_endpoint_service" "pl_gcp_svc" {
  project_id      = var.project_id
  private_link_id = mongodbatlas_privatelink_endpoint.pl_gcp.private_link_id
  provider_name   = "GCP"
  gcp_project_id  = var.gcp_project_id
  endpoint_service_id = "projects/${var.gcp_project_id}/regions/us-central1/serviceAttachments/..."

  dynamic "endpoints" {
    for_each = var.gcp_forwarding_rule_names
    content {
      ip_address    = google_compute_address.mongo[endpoints.key].address
      endpoint_name = google_compute_forwarding_rule.mongo[endpoints.key].name
    }
  }
}
```

### IP Access List

```hcl
resource "mongodbatlas_project_ip_access_list" "office" {
  project_id = var.project_id
  cidr_block = "203.0.113.0/24"
  comment    = "Office IP range"
}

resource "mongodbatlas_project_ip_access_list" "aws_lambda" {
  project_id = var.project_id
  aws_security_group = var.lambda_sg_id
  comment    = "Lambda security group"
}
```

---

## 4. Project, Users, and RBAC Resources

### Project

```hcl
resource "mongodbatlas_project" "app" {
  name   = "my-application"
  org_id = var.org_id

  # Optional: associate teams (deprecated in v2, use team_project_assignment)
  # teams { ... }

  is_collect_database_specifics_statistics_enabled = true
  is_data_explorer_enabled                         = true
  is_extended_storage_sizes_enabled                = false
  is_performance_advisor_enabled                   = true
  is_realtime_performance_panel_enabled            = true
  is_schema_advisor_enabled                        = true
}

output "project_id" {
  value = mongodbatlas_project.app.id
}
```

Import: `terraform import mongodbatlas_project.app PROJECT_ID`

### Database Users

**SCRAM (password) auth:**

```hcl
resource "mongodbatlas_database_user" "app_user" {
  project_id         = var.project_id
  username           = "appuser"
  password           = var.db_password  # stored plaintext in state — use sensitive var
  auth_database_name = "admin"

  roles {
    role_name     = "readWrite"
    database_name = "appdb"
  }

  scopes {
    name = mongodbatlas_advanced_cluster.main.name
    type = "CLUSTER"
  }
}
```

**AWS IAM user auth:**

```hcl
resource "mongodbatlas_database_user" "iam_user" {
  project_id         = var.project_id
  username           = "arn:aws:iam::123456789012:user/dbuser"
  auth_database_name = "$external"
  aws_iam_type       = "USER"

  roles {
    role_name     = "read"
    database_name = "reporting"
  }
}
```

**AWS IAM role auth:**

```hcl
resource "mongodbatlas_database_user" "iam_role" {
  project_id         = var.project_id
  username           = aws_iam_role.app.arn
  auth_database_name = "$external"
  aws_iam_type       = "ROLE"

  roles {
    role_name     = "readWrite"
    database_name = "appdb"
  }
}
```

**OIDC auth:**

```hcl
resource "mongodbatlas_database_user" "oidc_user" {
  project_id         = var.project_id
  username           = "idp-identifier/user@example.com"
  auth_database_name = "$external"
  oidc_auth_type     = "USER"

  roles {
    role_name     = "readWrite"
    database_name = "appdb"
  }
}
```

Import (supports dashes in username with slash separator):
```bash
terraform import mongodbatlas_database_user.app_user PROJECT_ID/USERNAME/admin
```

### Custom Database Roles

```hcl
resource "mongodbatlas_custom_db_role" "app_role" {
  project_id = var.project_id
  role_name  = "AppReadWriteRole"

  actions {
    action = "FIND"
    resources {
      collection_name = ""
      database_name   = "appdb"
    }
  }
  actions {
    action = "INSERT"
    resources {
      collection_name = ""
      database_name   = "appdb"
    }
  }
  actions {
    action = "UPDATE"
    resources {
      collection_name = ""
      database_name   = "appdb"
    }
  }

  inherited_roles {
    role_name     = "read"
    database_name = "reporting"
  }
}
```

**Note:** In v2.x, the `actions` attribute is no longer sensitive to order — Terraform plans will not show spurious diffs from reordering.

Assign custom role to a user:
```hcl
resource "mongodbatlas_database_user" "custom_user" {
  project_id         = var.project_id
  username           = "customuser"
  password           = var.custom_password
  auth_database_name = "admin"

  roles {
    role_name     = mongodbatlas_custom_db_role.app_role.role_name
    database_name = "admin"
  }
}
```

### Project API Key

```hcl
resource "mongodbatlas_project_api_key" "ci_key" {
  project_id  = var.project_id
  description = "CI/CD pipeline key"

  project_assignment {
    project_id = var.project_id
    role_names = ["GROUP_CLUSTER_MANAGER"]
  }
}

output "ci_public_key" {
  value = mongodbatlas_project_api_key.ci_key.public_key
}

output "ci_private_key" {
  value     = mongodbatlas_project_api_key.ci_key.private_key
  sensitive = true
}
```

### Team Assignment (v2 pattern)

In v2.x, `mongodbatlas_teams` resource was removed. Use dedicated assignment resources:

```hcl
# Assign an Atlas team to a project
resource "mongodbatlas_team_project_assignment" "dev_team" {
  project_id = mongodbatlas_project.app.id
  team_id    = var.dev_team_id
  role_names = ["GROUP_READ_ONLY"]
}
```

---

## 5. Search, Encryption, and Backup Resources

### Search Index — Standard

```hcl
resource "mongodbatlas_search_index" "text_search" {
  project_id      = var.project_id
  cluster_name    = mongodbatlas_advanced_cluster.main.name
  collection_name = "products"
  database        = "shop"
  name            = "product_search"

  analyzer        = "lucene.standard"
  search_analyzer = "lucene.standard"
  mappings_dynamic = true
}
```

### Search Index — Static Mapping

```hcl
resource "mongodbatlas_search_index" "typed_search" {
  project_id      = var.project_id
  cluster_name    = mongodbatlas_advanced_cluster.main.name
  collection_name = "articles"
  database        = "content"
  name            = "article_search"

  analyzer         = "lucene.english"
  mappings_dynamic = false
  mappings_fields  = jsonencode({
    title = {
      type     = "string"
      analyzer = "lucene.english"
    }
    body = {
      type     = "string"
      analyzer = "lucene.english"
    }
    published_at = {
      type = "date"
    }
  })

  synonyms {
    name               = "product_synonyms"
    source_collection  = "synonyms"
    analyzer           = "lucene.standard"
  }
}
```

### Vector Search Index

```hcl
resource "mongodbatlas_search_index" "vector_idx" {
  project_id      = var.project_id
  cluster_name    = mongodbatlas_advanced_cluster.main.name
  collection_name = "embeddings"
  database        = "ai"
  name            = "vector_search"
  type            = "vectorSearch"

  fields = jsonencode([
    {
      type          = "vector"
      path          = "embedding"
      numDimensions = 1536
      similarity    = "cosine"
    },
    {
      type = "filter"
      path = "category"
    }
  ])
}
```

### Search Deployment (Dedicated Search Nodes)

```hcl
resource "mongodbatlas_search_deployment" "nodes" {
  project_id   = var.project_id
  cluster_name = mongodbatlas_advanced_cluster.main.name

  specs = [{
    instance_size = "S20_HIGHCPU_NVME"
    node_count    = 2
  }]
}
```

Import:
```bash
terraform import mongodbatlas_search_index.text_search PROJECT_ID-CLUSTER_NAME-INDEX_ID
```

### Encryption at Rest — AWS KMS

```hcl
# Step 1: Create cloud provider access role
resource "mongodbatlas_cloud_provider_access_setup" "aws_access" {
  project_id    = var.project_id
  provider_name = "AWS"
}

resource "aws_iam_role" "atlas_role" {
  name = "atlas-encryption-role"
  # Trust the Atlas AWS account (536227242015) to assume this role,
  # scoped to the external ID Atlas provides — do NOT use your own account root.
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::536227242015:root" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "sts:ExternalId" = mongodbatlas_cloud_provider_access_setup.aws_access.aws.atlas_assumed_role_external_id
        }
      }
    }]
  })
}

resource "mongodbatlas_cloud_provider_access_authorization" "auth" {
  project_id = var.project_id
  role_id    = mongodbatlas_cloud_provider_access_setup.aws_access.role_id
  aws {
    iam_assumed_role_arn = aws_iam_role.atlas_role.arn
  }
}

# Step 2: Enable encryption at rest
resource "mongodbatlas_encryption_at_rest" "enc" {
  project_id = var.project_id

  aws_kms_config {
    enabled                = true
    customer_master_key_id = aws_kms_key.atlas_key.id
    region                 = "US_EAST_1"
    # role_id references the authorized cloud access role (not the KMS key policy role)
    role_id                = mongodbatlas_cloud_provider_access_authorization.auth.role_id
  }
}

# Step 3: Reference in cluster
resource "mongodbatlas_advanced_cluster" "encrypted" {
  project_id                   = var.project_id
  name                         = "encrypted-cluster"
  cluster_type                 = "REPLICASET"
  encryption_at_rest_provider  = "AWS"
  # ... replication_specs ...
}
```

### Encryption at Rest — Azure Key Vault

```hcl
resource "mongodbatlas_encryption_at_rest" "azure_enc" {
  project_id = var.project_id

  azure_key_vault_config {
    enabled             = true
    azure_environment   = "AZURE"
    subscription_id     = var.azure_subscription_id
    resource_group_name = var.resource_group_name
    key_vault_name      = var.key_vault_name
    key_identifier      = var.key_identifier
    role_id             = var.atlas_service_principal_object_id
    client_id           = var.azure_client_id
    secret              = var.azure_client_secret
    tenant_id           = var.azure_tenant_id
  }
}
```

### Encryption at Rest — GCP KMS

```hcl
resource "mongodbatlas_encryption_at_rest" "gcp_enc" {
  project_id = var.project_id

  google_cloud_kms_config {
    enabled                 = true
    key_version_resource_id = google_kms_crypto_key.atlas_key.primary[0].name
    role_id                 = mongodbatlas_cloud_provider_access_authorization.gcp_auth.role_id
  }
}
```

Import: `terraform import mongodbatlas_encryption_at_rest.enc PROJECT_ID`

### Cloud Backup Schedule

```hcl
resource "mongodbatlas_cloud_backup_schedule" "schedule" {
  project_id    = var.project_id
  cluster_name  = mongodbatlas_advanced_cluster.main.name

  reference_hour_of_day   = 2    # UTC 2am
  reference_minute_of_hour = 0
  restore_window_days     = 7

  policy_item_hourly {
    frequency_interval = 6      # Every 6 hours
    retention_unit     = "days"
    retention_value    = 2
  }

  policy_item_daily {
    frequency_interval = 1
    retention_unit     = "days"
    retention_value    = 7
  }

  policy_item_weekly {
    frequency_interval = 6      # Saturday
    retention_unit     = "weeks"
    retention_value    = 4
  }

  policy_item_monthly {
    frequency_interval = 40     # Last day of month
    retention_unit     = "months"
    retention_value    = 12
  }

  policy_item_yearly {
    frequency_interval = 1      # January
    retention_unit     = "years"
    retention_value    = 3
  }
}
```

**Known issue (v2.x):** Removing the `mongodbatlas_cloud_backup_schedule` resource causes an error if the cluster has continuous cloud backup enabled, because removing the hourly policy item while continuous backup is on triggers a 400 error. Use `skip_destroy = true` or disable continuous backup on the cluster first.

**Azure restore_window_days:** On Azure, `restore_window_days` is mandatory. Omitting it raises a validation error.

Import:
```bash
terraform import mongodbatlas_cloud_backup_schedule.schedule PROJECT_ID-CLUSTER_NAME
```

### Maintenance Window

```hcl
resource "mongodbatlas_maintenance_window" "weekly" {
  project_id  = var.project_id
  day_of_week = 7        # Sunday (1=Monday … 7=Sunday)
  hour_of_day = 3        # UTC 3am — Required in v2.x
  # start_asap is Computed-only in v2.x; do not set it
}
```

Import: `terraform import mongodbatlas_maintenance_window.weekly PROJECT_ID`

**v2.x behavioral change:** `hour_of_day` is now Required (was optional). `start_asap` is now Computed-only — remove it from any v1 configs before upgrading.

### Backup Compliance Policy

```hcl
resource "mongodbatlas_backup_compliance_policy" "bcp" {
  project_id                 = var.project_id
  authorized_email           = "admin@example.com"
  authorized_user_first_name = "Admin"
  authorized_user_last_name  = "User"
  copy_protection_enabled    = false
  encryption_at_rest_enabled = false
  on_demand_policy_item {
    frequency_interval = 0    # Must be 0 for on-demand — the only valid value
    retention_unit     = "days"
    retention_value    = 3
  }

  policy_item_hourly {
    frequency_interval = 6
    retention_unit     = "days"
    retention_value    = 7
  }
}
```

---

## 6. Import and State Management

### CLI Import (Terraform < 1.5)

Each resource documents its import ID format:

```bash
# Project
terraform import mongodbatlas_project.app PROJECT_ID

# Cluster
terraform import mongodbatlas_advanced_cluster.main PROJECT_ID-CLUSTER_NAME

# Database user (slash form supports dashes)
terraform import mongodbatlas_database_user.user PROJECT_ID/USERNAME/admin

# Network peering
terraform import mongodbatlas_network_peering.peer PROJECTID-PEERID-AWS

# Backup schedule
terraform import mongodbatlas_cloud_backup_schedule.sched PROJECT_ID-CLUSTER_NAME

# Encryption at rest
terraform import mongodbatlas_encryption_at_rest.enc PROJECT_ID
```

Get IDs with Atlas CLI:
```bash
atlas projects list
atlas clusters list --projectId <id>
atlas networking peering list --projectId <id> --provider AWS
```

### Declarative Import Blocks (Terraform 1.5+)

```hcl
# import.tf — run once, then optionally remove after import
import {
  to = mongodbatlas_advanced_cluster.existing
  id = "6494919b2b3afd2b4ff2e70c-my-cluster"
}

import {
  to = mongodbatlas_database_user.app
  id = "6494919b2b3afd2b4ff2e70c/appuser/admin"
}
```

Generate configuration from existing resources:
```bash
terraform plan -generate-config-out=generated.tf
terraform apply
```

**Constraint:** Import blocks are only allowed in the root module, not inside module code.

### Moved Blocks (Cluster → Advanced Cluster Migration)

When migrating from `mongodbatlas_cluster` to `mongodbatlas_advanced_cluster` in the same state file:

```hcl
moved {
  from = mongodbatlas_cluster.existing
  to   = mongodbatlas_advanced_cluster.existing
}
```

This is the recommended approach because `terraform state mv` is more error-prone.

### Handling Atlas-Managed Fields

Atlas may modify fields outside Terraform (auto-scaling, connection string updates, cluster IDs). Patterns:

1. **`use_effective_fields = true`** — for advanced_cluster auto-scaling (preferred in v2)
2. **`lifecycle.ignore_changes`** — for specific attributes when `use_effective_fields` is not applicable
3. **Computed-only fields** — `connection_strings`, `cluster_id`, `mongo_db_version` are always computed; never set them explicitly

### State Migration Between Provider Versions

When upgrading from v1.x to v2.x, follow this order — attempting `terraform plan` with removed resources still in place will error immediately:

1. **Migrate resources first** (while still on v1.x): add `moved {}` blocks for `mongodbatlas_cluster` → `mongodbatlas_advanced_cluster`, remove removed resources from HCL, and run `terraform state rm` for any that can't be migrated
2. **Verify plan is clean** on v1.x before touching the provider version
3. **Bump the provider version** in `versions.tf` to `~> 2.7`
4. **Review deprecation warnings** — removed resources produce "unknown resource type" errors, not just warnings
5. **Update HCL for removed attributes** (`replication_specs.#.id`, top-level `disk_size_gb`, `num_shards`)

Upgrade checklist:
```bash
# While still on v1.x — migrate resources first
terraform plan   # must be clean before version bump

# Then bump provider version in versions.tf and:
terraform init -upgrade
terraform plan   # review all diffs carefully — watch for forced replacements
terraform apply
```

---

## 7. Module Patterns

### Official Community Module

The `terraform-mongodbatlas-modules/terraform-mongodbatlas-cluster` module provides a production-ready interface:

```hcl
module "atlas_cluster" {
  source  = "terraform-mongodbatlas-modules/atlas-basic/mongodbatlas"
  version = "~> 1.0"

  project_id   = var.project_id
  name         = "production"
  cluster_type = "REPLICASET"

  # Simplified topology (alternative to replication_specs)
  regions = [{
    provider_name = "AWS"
    region_name   = "US_EAST_1"
    priority      = 7
    node_count    = 3
    instance_size = "M30"
  }]

  backup_enabled                 = true
  retain_backups_enabled         = true
  termination_protection_enabled = true
  redact_client_log_data         = true
}

output "connection_string" {
  value = module.atlas_cluster.connection_strings
}
```

Module outputs: `cluster_id`, `cluster_name`, `connection_strings`, `mongo_db_version`, `state_name`, `create_date`.

### Custom Module Interface Pattern

Structure a reusable module:

```
modules/
  atlas-cluster/
    main.tf          # mongodbatlas_advanced_cluster resource
    variables.tf     # typed input variables
    outputs.tf       # connection_strings, cluster_id
    versions.tf      # required_providers constraint
environments/
  dev/
    main.tf          # calls module with dev vars
  staging/
    main.tf
  prod/
    main.tf
```

`variables.tf` with validation:

```hcl
variable "instance_size" {
  type        = string
  description = "Atlas instance size (M10, M20, M30, M40, M50, M60, M80, M200, M300)"

  validation {
    condition     = can(regex("^M(10|20|30|40|50|60|80|200|300)$", var.instance_size))
    error_message = "instance_size must be a valid dedicated tier (M10–M300)."
  }
}

variable "backup_enabled" {
  type        = bool
  description = "Enable continuous cloud backups"
  default     = true
}
```

> **Security note:** Do NOT declare `atlas_public_key` / `atlas_private_key` as module input variables. Provider credentials must be set at the root module level (via environment variables or TFC workspace vars), not propagated through module inputs.

`outputs.tf`:

```hcl
output "connection_string_srv" {
  description = "Standard SRV connection string"
  value       = mongodbatlas_advanced_cluster.main.connection_strings[0].standard_srv
}

output "cluster_id" {
  description = "Atlas cluster unique ID"
  value       = mongodbatlas_advanced_cluster.main.cluster_id
}

output "state_name" {
  description = "Current cluster state"
  value       = mongodbatlas_advanced_cluster.main.state_name
}
```

### Remote State Pattern

Store connection strings in remote state for consumption by application modules:

```hcl
# In the application module's data block
data "terraform_remote_state" "atlas" {
  backend = "s3"
  config = {
    bucket = "my-terraform-state"
    key    = "atlas/production/terraform.tfstate"
    region = "us-east-1"
  }
}

locals {
  mongo_uri = data.terraform_remote_state.atlas.outputs.connection_string_srv
}
```

---

## 8. Atlantis and Terraform Cloud

### Terraform Cloud (TFC) Workspace Configuration

Store Atlas API credentials as TFC workspace environment variables (marked sensitive):

```
MONGODB_ATLAS_PUBLIC_KEY   = <your-public-key>   (sensitive)
MONGODB_ATLAS_PRIVATE_KEY  = <your-private-key>  (sensitive)
```

Remote backend configuration:

```hcl
terraform {
  cloud {
    organization = "my-org"
    workspaces {
      name = "atlas-production"
    }
  }
}
```

### Workspace-Per-Environment Pattern

```
atlas-dev       → dev/ directory, M10 clusters
atlas-staging   → staging/ directory, M30 clusters
atlas-prod      → prod/ directory, M50+ clusters with backup
```

Each workspace has isolated state and separate Atlas API keys. Cross-workspace data access via remote state data sources.

### Atlantis Configuration

`atlantis.yaml`:

```yaml
version: 3
projects:
  - name: atlas-prod
    dir: environments/prod
    workspace: default
    autoplan:
      when_modified: ["*.tf", "../../modules/**/*.tf"]
      enabled: true
    apply_requirements: [approved, mergeable]

  - name: atlas-staging
    dir: environments/staging
    workspace: default
    autoplan:
      when_modified: ["*.tf"]
      enabled: true
```

Pass Atlas credentials to Atlantis via environment variables in the Atlantis server config or deployment manifest:

```yaml
# atlantis-deployment.yaml (Kubernetes)
env:
  - name: MONGODB_ATLAS_PUBLIC_KEY
    valueFrom:
      secretKeyRef:
        name: atlas-credentials
        key: public_key
  - name: MONGODB_ATLAS_PRIVATE_KEY
    valueFrom:
      secretKeyRef:
        name: atlas-credentials
        key: private_key
```

### Atlantis + TFC Integration

Atlantis can delegate `plan` and `apply` to Terraform Cloud via `ATLANTIS_TFE_TOKEN`. This requires the team token to have "Manage Workspaces" permission. Atlantis does **not** support local state — use TFC free remote state or an S3/Azure backend.

### State Locking

All remote backends support state locking to prevent concurrent applies:
- TFC: built-in
- S3: requires DynamoDB table with `LockID` key
- Azure Blob: uses lease locking natively
- GCS: uses object locking natively

---

## 9. Common Bugs and Gotchas

### 1. Auto-Scaling Causes Perpetual Drift

**Problem:** When `auto_scaling.disk_gb_enabled = true` or `auto_scaling.compute_enabled = true`, Atlas modifies `disk_size_gb` and `instance_size` in the background. On the next `terraform plan`, Terraform sees a diff and will revert to the declared value.

**Fix (v2 preferred):**
```hcl
use_effective_fields = true
```

**Fix (v1 workaround):**
```hcl
lifecycle {
  ignore_changes = [
    replication_specs[0].region_configs[0].electable_specs[0].instance_size,
    replication_specs[0].region_configs[0].electable_specs[0].disk_size_gb,
  ]
}
```

**Limitation:** `lifecycle.ignore_changes` cannot accept dynamic expressions (a known Terraform limitation, issue #3427).

### 2. replication_specs Ordering Causes Forced Replace

**Problem:** Between provider versions ~1.8–1.9, a random reordering of `region_configs` elements caused Terraform to plan a destroy/create of the entire cluster (issue #1204). Later versions fixed this by ordering by priority, but the issue can resurface in complex multi-region configs.

**Fix:** Ensure `region_configs` elements are ordered by descending `priority` (7 first, 1 last) in your HCL. This matches how the provider normalizes the order returned from the Atlas API.

**Also check:** If you see an unexpected cluster replacement, add `-target` to narrow the scope and review the diff carefully before applying.

### 3. Network Container CIDR Cannot Be Changed

**Problem:** After creating an M10+ cluster or network peering connection, Atlas locks the network container CIDR. Running `terraform apply` with a new CIDR results in a 400 error.

**Fix:** Plan your CIDR block before creating any clusters. If you must change it:
1. Delete all M10+ clusters in the project
2. Delete all network peering connections
3. Update and apply the container CIDR
4. Recreate clusters and peering

Use a `/21` or larger block to avoid exhausting subnets as you scale.

### 4. Provider v2 Removed Resources Cause Init Errors

**Problem:** Upgrading `version = "~> 2.0"` while still having `mongodbatlas_cluster`, `mongodbatlas_serverless_instance`, `mongodbatlas_teams`, or `mongodbatlas_org_invitation` in your configuration causes `terraform init` or `terraform plan` to fail with "unknown resource type."

**Fix:** Before bumping the provider version:
1. Migrate `mongodbatlas_cluster` → `mongodbatlas_advanced_cluster` using `moved {}` blocks
2. Remove serverless resources (or migrate to flex clusters via `FLEX` provider_name)
3. Replace `mongodbatlas_teams` with `mongodbatlas_team_project_assignment`
4. Replace invitation resources with `mongodbatlas_cloud_user_project_assignment`

### 5. Custom DB Role Assignment Fails (400 UNSUPPORTED_ROLE)

**Problem:** Assigning a custom role to a database user fails when the role depends on the `mongodbatlas_custom_db_role` resource but Terraform applies the user before the role is created.

**Fix:** Add explicit dependency:
```hcl
resource "mongodbatlas_database_user" "user" {
  # ...
  depends_on = [mongodbatlas_custom_db_role.app_role]
}
```

Or reference the role name directly (creates implicit dependency):
```hcl
roles {
  role_name     = mongodbatlas_custom_db_role.app_role.role_name
  database_name = "admin"
}
```

### 6. Cloud Backup Schedule Delete Error (Continuous Backup)

**Problem:** Removing `mongodbatlas_cloud_backup_schedule` when the cluster has continuous backup enabled causes a 400 error: "Continuous Cloud Backup cannot be on without an hourly policy item."

**Fix option A:** Set `skip_destroy = true` on the resource so Terraform removes it from state without calling the Atlas API delete.

**Fix option B:** Disable `pit_enabled` (point-in-time restore) on the cluster before deleting the schedule resource.

### 7. replication_specs node_count = 0 vs. Removing the Block

**Problem:** Setting `analytics_specs` or `read_only_specs` with `node_count = 0` and later removing the block can cause spurious plan diffs because the Atlas API returns the block with zero counts.

**Fix:** Rather than removing a spec block, set `node_count = 0` explicitly. This signals intent without ambiguity.

### 8. X.509 Authentication Deprecation

**Problem:** Code using `mongodbatlas_x509_authentication_database_user` breaks on provider v2.x with "unknown resource type."

**Fix:** Replace with `mongodbatlas_database_user` and set `x509_type`:

```hcl
resource "mongodbatlas_database_user" "x509_user" {
  project_id         = var.project_id
  username           = "CN=myuser"
  auth_database_name = "$external"
  x509_type          = "MANAGED"   # or "CUSTOMER" for self-managed certs

  roles {
    role_name     = "readWrite"
    database_name = "appdb"
  }
}
```

### 9. Backup Schedule Azure Mandatory restore_window_days

**Problem:** On Azure clusters, `mongodbatlas_cloud_backup_schedule` requires `restore_window_days` to be set. Omitting it raises a mandatory field validation error.

**Fix:** Always include `restore_window_days` when targeting Azure clusters, or add it universally as a default.

### 10. advanced_cluster timeout during Create

Long cluster creation (M40+, multi-region) can exceed the default 3-hour timeout. In v2.x, `delete_on_create_timeout = true` (default) will delete the partially-created cluster automatically. To avoid this:

```hcl
resource "mongodbatlas_advanced_cluster" "large" {
  # ...
  timeouts {
    create = "4h"
    update = "2h"
    delete = "2h"
  }
}
```

---

## 10. Provider v1 → v2 Migration Guide

### What Changed in v2.0.0 (September 15, 2025)

#### Removed Resources (must migrate before upgrading)

| Removed Resource | Replacement |
|---|---|
| `mongodbatlas_cluster` | `mongodbatlas_advanced_cluster` |
| `mongodbatlas_serverless_instance` | `mongodbatlas_advanced_cluster` with `FLEX` provider |
| `mongodbatlas_privatelink_endpoint_serverless` | `mongodbatlas_privatelink_endpoint` |
| `mongodbatlas_privatelink_endpoint_service_serverless` | `mongodbatlas_privatelink_endpoint_service` |
| `mongodbatlas_teams` | `mongodbatlas_team_project_assignment` |
| `mongodbatlas_org_invitation` | `mongodbatlas_cloud_user_org_assignment` |
| `mongodbatlas_project_invitation` | `mongodbatlas_cloud_user_project_assignment` |
| `mongodbatlas_data_lake_pipeline` | (Atlas Data Lake deprecated) |

#### Removed Data Sources

| Removed Data Source | Replacement |
|---|---|
| `mongodbatlas_teams` | `mongodbatlas_team` |
| `mongodbatlas_atlas_user` | `mongodbatlas_cloud_user_org_assignment` |
| `mongodbatlas_atlas_users` | (removed) |
| `mongodbatlas_org_invitation` | (removed) |
| `mongodbatlas_project_invitation` | (removed) |

#### Removed Attributes on Existing Resources

| Resource | Removed Attribute | Replacement |
|---|---|---|
| `advanced_cluster` | `id` | use `cluster_id` |
| `advanced_cluster` | top-level `disk_size_gb` | set in `electable_specs.disk_size_gb` |
| `advanced_cluster` | `replication_specs.#.id` | not needed; use `zone_id` |
| `advanced_cluster` | `replication_specs.#.num_shards` | number of list elements = num shards |
| `advanced_cluster` | `advanced_configuration.default_read_concern` | removed from Atlas API |
| `cloud_backup_schedule` | `copy_settings.#.replication_spec_id` | use `zone_id` |
| `global_cluster_config` | `custom_zone_mapping` | use `custom_zone_mapping_zone_id` |
| `project` | `teams` inline block | use `mongodbatlas_team_project_assignment` |

#### Behavioral Changes

- `advanced_cluster.delete_on_create_timeout` defaults to `true` (was `false`)
- `search_deployment.delete_on_create_timeout` defaults to `true`
- `cloud_backup_schedule.export` and `auto_export_enabled` are now Optional only
- `maintenance_window.hour_of_day` is now Required
- `maintenance_window.start_asap` is now Computed-only (cannot be set)
- `custom_db_role` actions are no longer order-sensitive (fixes spurious plan diffs)

### Step-by-Step Migration

**Step 1: Migrate clusters before bumping provider version**

```hcl
# Add moved block while still on v1.x
moved {
  from = mongodbatlas_cluster.app
  to   = mongodbatlas_advanced_cluster.app
}

# Replace mongodbatlas_cluster.app resource block with:
resource "mongodbatlas_advanced_cluster" "app" {
  project_id   = var.project_id
  name         = "app-cluster"
  cluster_type = "REPLICASET"
  # ... (convert fields to v2 schema)
}
```

Apply the `moved {}` block with the v1 provider to verify no replacement occurs, then commit the configuration change.

**Step 2: Remove deprecated resources from configuration**

Before bumping `version = "~> 2.0"`, remove or replace all resources in the removed list. Use `terraform state rm` for any that cannot be migrated:

```bash
terraform state rm mongodbatlas_serverless_instance.dev
terraform state rm mongodbatlas_org_invitation.user1
```

**Step 3: Update the provider version constraint**

```hcl
mongodbatlas = {
  source  = "mongodb/mongodbatlas"
  version = "~> 2.7"
}
```

**Step 4: Initialize and plan**

```bash
terraform init -upgrade
terraform plan
```

Review all diffs. Pay particular attention to:
- Clusters with top-level `disk_size_gb` (must move into `electable_specs`)
- Any `num_shards > 1` (must convert to multiple `replication_specs` list elements)
- References to `replication_specs.#.id` (replace with `zone_id`)

**Step 5: Migrate num_shards to list elements**

v1 pattern (no longer valid):
```hcl
# INVALID in v2:
replication_specs {
  num_shards = 2
  regions_config { ... }
}
```

v2 pattern (one element per shard):
```hcl
replication_specs = [
  { region_configs = [{ ... }] },   # shard 1
  { region_configs = [{ ... }] }    # shard 2
]
```

### Using the Atlas CLI Terraform Generator

For importing existing Atlas infrastructure (not originally created by Terraform), use the `atlas terraform generate` command built into the [Atlas CLI](https://www.mongodb.com/docs/atlas/cli/stable/command/atlas-terraform-generate/) to generate `.tf` files from live Atlas resources:

```bash
# Requires Atlas CLI >= 1.14
atlas terraform generate --projectId <id> --targetFile ./generated.tf
```

This produces Terraform resource configurations for all existing resources in the project. Review the generated files, add `import {}` blocks for each resource, then run:

```bash
terraform plan -generate-config-out=imported.tf
terraform apply
```

---

## References and See Also

- [Provider Registry](https://registry.terraform.io/providers/mongodb/mongodbatlas/latest/docs) — official resource documentation
- [Provider Configuration Guide](https://registry.terraform.io/providers/MongoDB/mongodbatlas/latest/docs/guides/provider-configuration) — authentication options
- [Cluster to Advanced Cluster Migration](https://registry.terraform.io/providers/mongodb/mongodbatlas/2.7.0/docs/guides/cluster-to-advanced-cluster-migration-guide) — moved block guide
- [v2.0.0 Upgrade Guide](https://registry.terraform.io/providers/mongodb/mongodbatlas/latest/docs/guides/2.0.0-upgrade-guide) — full breaking changes list
- [Provider CHANGELOG](https://github.com/mongodb/terraform-provider-mongodbatlas/blob/master/CHANGELOG.md) — release-by-release changes
- [Provider GitHub Issues](https://github.com/mongodb/terraform-provider-mongodbatlas/issues) — known bugs and workarounds
- [Atlas Terraform Getting Started](https://www.mongodb.com/docs/atlas/terraform/) — MongoDB official guide
- [terraform-mongodbatlas-modules](https://github.com/terraform-mongodbatlas-modules/terraform-mongodbatlas-cluster) — community cluster module
- [Atlas Architecture Center — Network Security](https://www.mongodb.com/docs/atlas/architecture/current/network-security/) — Private Link architecture guidance
- [Atlantis TFC Docs](https://www.runatlantis.io/docs/terraform-cloud.html) — Atlantis + TFC integration

**Related Skills:**
- [[mongodb-atlas-expert]] — Atlas administration and configuration
- [[mongodb-aws-networking]] — AWS VPC, Private Link, IAM patterns
- [[mongodb-atlas-azure]] — Azure-specific Atlas integration
- [[mongodb-atlas-gcp]] — GCP-specific Atlas integration
- [[terraform-kafka-infra]] — other infrastructure Terraform patterns
