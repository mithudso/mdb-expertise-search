<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-multicloud` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-multicloud
description: >-
  Authoritative reference for MongoDB Atlas deployments on Azure and GCP,
  including private networking (Azure PrivateLink / GCP PSC), multi-cloud
  replica sets, Global Clusters with zone sharding, marketplace billing
  (MACC/CUD), partnership programs, DR patterns, and egress cost analysis.
  TRIGGER: designing Atlas private network connectivity on Azure (PrivateLink)
  or GCP (PSC); planning multi-cloud replica set topology and write-concern
  latency tradeoffs; evaluating Atlas marketplace billing and MACC/CUD
  applicability; architecting cross-cloud DR with Atlas; auditing egress cost
  for multi-cloud clusters. SKIP: deep Azure-only content (DNS zones, NSG,
  Entra ID OIDC, AKS) — use mongodb-atlas-azure; deep GCP-only content
  (Shared VPC, Workload Identity, GKE, Vertex AI) — use mongodb-atlas-gcp;
  AWS-only networking — use mongodb-aws-networking.
  NOTE: Terraform examples use mongodbatlas provider (hashicorp/mongodbatlas).
  Resource schemas differ between v1.x and v2.x — verify against your pinned version.
category: mongodb
version: "1.2.0"
updated: "2026-05-29"
tags:
  - mongodb
  - atlas
  - azure
  - gcp
  - multi-cloud
  - private-link
  - private-service-connect
  - marketplace
  - billing
  - disaster-recovery
keywords:
  - multi-cloud replica set
  - Azure PrivateLink
  - GCP Private Service Connect
  - PSC port mapping
  - MACC Azure commitment
  - GCP CUD committed use
  - cross-cloud DR
  - cross-cloud egress cost
  - priority-0 secondary
  - hidden secondary failover
  - Atlas Global Clusters zone sharding
  - mongodbatlas_privatelink_endpoint
  - AtlasPrivateEndpoint AKO
  - Azure Native Integration
  - GCP Marketplace Atlas
whenToUse:
  - "design Atlas PrivateLink on Azure — steps, CLI, Terraform, AKO"
  - "set up GCP Private Service Connect for Atlas"
  - "multi-cloud replica set: AWS primary + Azure DR secondary"
  - "write-concern latency impact of cross-cloud majority acknowledgment"
  - "Atlas billing through Azure Marketplace and MACC credit"
  - "GCP Marketplace Atlas and committed use discounts"
  - "cross-cloud egress cost estimate for replication traffic"
  - "Global Cluster zone sharding across Azure + GCP regions"
  - "DR firedrill: promote Azure secondary by adjusting node priority"
  - "one Private Link endpoint per region requirement"
whenNotToUse:
  - "Deep Azure-only: DNS private zones, NSG rules, Entra ID OIDC, AKS, Sentinel — use mongodb-atlas-azure"
  - "Deep GCP-only: Shared VPC, Workload Identity Federation, GKE, Vertex AI, BigQuery — use mongodb-atlas-gcp"
  - "AWS-only networking or PrivateLink — use mongodb-aws-networking"
  - "Atlas Search Nodes (not supported with Global Writes) — use mongodb-atlas-search-nodes"
related_skills:
  - mongodb-atlas-azure
  - mongodb-atlas-gcp
  - mongodb-atlas-terraform
  - mongodb-atlas-kubernetes-operator
  - mongodb-atlas-expert
  - mongodb-cost-optimization
  - mongodb-disaster-recovery
---

# MongoDB Atlas Multi-Cloud (Azure + GCP)

## 1. Atlas on Azure

### Supported Regions

Atlas mirrors the Azure region catalog. Dedicated clusters (M10+) are available in all major Azure regions, including:

- **Americas:** eastus, eastus2, westus2, westus3, centralus, brazilsouth, canadacentral
- **Europe:** westeurope, northeurope, uksouth, germanywestcentral, swedencentral, francesouthcentral
- **Asia-Pacific:** southeastasia, eastasia, japaneast, australiaeast, centralindia, koreacentral
- **Middle East / Africa:** uaenorth, southafricanorth

Serverless and Flex (former M0 successor) tiers have a narrower region subset—verify in the Atlas UI or `atlas clusters availableRegions` before provisioning.

### Deployment Model

Atlas on Azure runs fully within Microsoft's infrastructure but is managed by MongoDB's control plane. Each dedicated cluster lives in an Atlas-owned Azure subscription. Your application VNet and the Atlas VNet are separate; connectivity options are:

| Method | When to use |
|---|---|
| IP allowlist | Quick dev/test; exposes Atlas IP to internet |
| VNet Peering | Same or peered region; low-latency; requires non-overlapping CIDRs |
| Azure Private Link | Preferred production path; private, no IP exposure |
| Azure Private Endpoint (Serverless) | Serverless/Flex instances use Private Endpoint API separately |

### Azure VNet Integration (Peering)

1. Create a VNet in the same Azure region as the Atlas cluster.
2. In Atlas, **Network Access → VNet Peering → Add Peering Connection** — supply your Azure Subscription ID, Resource Group, VNet name, and Tenant ID.
3. Atlas initiates the peering; you must accept it in the Azure Portal under **Virtual Network → Peerings**.
4. Add CIDR of the Atlas VNet to your NSGs/route tables if needed.
5. Route tables must not have RFC-1918 overlap between application VNet and Atlas VNet.

> **Network container:** Atlas wraps its VNet in an *Atlas network container* (an internal VPC construct). The container CIDR is set once per Atlas project + Azure region and cannot be changed after the first cluster is deployed. Customize it at project creation time to avoid address-space conflicts with your corporate network.

---

## 2. Azure Private Link

### Overview

Azure Private Link exposes Atlas clusters as Private Link *Services*. You create a Private Endpoint in your own VNet, which gets a private IP from your address space. All traffic stays on the Microsoft backbone — the Atlas cluster never acquires a public IP from your perspective.

### Region Constraints

- The Private Endpoint **must be in the same Azure region** as the Atlas cluster node(s) it connects to.
- Multi-region Atlas clusters (different Azure regions) require **one Private Link setup per region**.
- Cross-region Private Link for Atlas is not supported — use Global VNet Peering for that scenario, or route via Azure's own inter-region infrastructure before hitting Private Link.

### Setup Steps (Console)

1. Atlas → **Network Access → Private Endpoint → Dedicated Clusters → Azure**.
2. Select the Atlas cluster region.
3. Atlas creates a Private Link Service; note the **Resource ID** and **Alias**.
4. In Azure Portal: **Private Link Center → Private Endpoints → Create**.
   - Select "Connect to an Azure resource by resource ID or alias."
   - Paste the Atlas alias.
   - Choose your subscription, VNet, and subnet.
5. Approve the connection in Atlas (or enable auto-approve).
6. Update Atlas IP Access List to include `0.0.0.0/0` or the specific private IPs — Atlas still checks connection strings, but IP allowlisting of the private endpoint source IP is optional when Private Link is in use.
7. Update connection string to use **private endpoint DNS** (Atlas displays this in the UI).

### CLI Alternative (Atlas CLI)

```bash
# Create the Atlas-side Private Link endpoint
atlas privateEndpoints azure create \
  --region US_EAST_2 \
  --projectId <projectId>

# List endpoints to get the private link service resource ID
atlas privateEndpoints azure list --projectId <projectId>

# After creating the Azure Private Endpoint, link it back to Atlas
atlas privateEndpoints azure interfaces create <endpointServiceId> \
  --privateEndpointId <azurePrivateEndpointResourceId> \
  --privateEndpointIpAddress <privateIp> \
  --projectId <projectId>
```

### Atlas Kubernetes Operator (AKO)

For AKO-managed clusters, configure private endpoints via `AtlasPrivateEndpoint` CRD:

```yaml
apiVersion: atlas.mongodb.com/v1
kind: AtlasPrivateEndpoint
metadata:
  name: atlas-azure-pe
spec:
  projectRef:
    name: my-atlas-project
  provider: AZURE
  region: US_EAST_2
  azureConfiguration:
    id: /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Network/privateEndpoints/<pe-name>
    ipAddress: 10.0.1.10
```

AKO reconciles the endpoint state on every sync cycle — no manual Atlas Console approval required.

### Terraform (mongodbatlas provider)

```hcl
resource "mongodbatlas_privatelink_endpoint" "az" {
  project_id    = var.atlas_project_id
  provider_name = "AZURE"
  region        = "US_EAST_2"  # Atlas region name (underscores, uppercase)
}

resource "azurerm_private_endpoint" "atlas" {
  name                = "atlas-private-endpoint"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = azurerm_subnet.private.id

  private_service_connection {
    name                           = "atlas-psc"
    private_connection_resource_id = mongodbatlas_privatelink_endpoint.az.private_link_service_resource_id
    is_manual_connection           = true
    request_message                = "Atlas Private Link"
  }
}

resource "mongodbatlas_privatelink_endpoint_service" "az_svc" {
  project_id                  = var.atlas_project_id
  private_link_id             = mongodbatlas_privatelink_endpoint.az.private_link_id
  endpoint_service_id         = azurerm_private_endpoint.atlas.id
  private_endpoint_ip_address = azurerm_private_endpoint.atlas.private_service_connection[0].private_ip_address
  provider_name               = "AZURE"
}
```

Key Atlas region name mapping: Azure `eastus` → Atlas `US_EAST`, Azure `eastus2` → Atlas `US_EAST_2`, Azure `westeurope` → Atlas `EUROPE_WEST`. Full mapping in Atlas docs.

---

## 3. Atlas on GCP

### Supported Regions

GCP region support in Atlas includes:

- **Americas:** us-east4, us-east1, us-central1, us-west2, us-west3, us-west4, northamerica-northeast1, southamerica-east1
- **Europe:** europe-west1, europe-west2, europe-west3, europe-west4, europe-west6, europe-north1, europe-central2
- **Asia-Pacific:** asia-east1, asia-east2, asia-northeast1, asia-northeast2, asia-southeast1, asia-south1, australia-southeast1
- **Middle East:** me-west1

### GCP Project Structure

Atlas GCP clusters run in MongoDB's own GCP projects. Your application GCP project is separate. Atlas creates a dedicated VPC per project-region pair inside MongoDB's GCP org.

Key facts:
- Each Atlas project + GCP region = one dedicated Atlas VPC.
- Atlas VPC CIDRs are auto-assigned (default `/21`); you can customize the CIDR at project creation time but not after.
- Peering or PSC connects your GCP project VPC to the Atlas VPC.

### Deployment Model

Unlike AWS where Atlas uses VPC Peering as the legacy standard and PrivateLink as the upgrade, GCP originally used **VPC Peering** as the primary isolation mechanism. **Private Service Connect (PSC)** is now the preferred new architecture.

---

## 4. GCP Private Service Connect (PSC)

### Overview

Atlas exposes each cluster as a GCP **Managed Service** (PSC producer). You create a PSC **endpoint** (consumer) in your VPC, which gets a private IP from your address space. Traffic never traverses the public internet.

Atlas supports two PSC architectures:

| Architecture | Description |
|---|---|
| **Port Mapping (preferred)** | One PSC endpoint per Atlas VPC region; each replica set member is reached via a different port. Scales without endpoint re-provisioning. |
| **Legacy (pre-port-mapping)** | One PSC endpoint per Atlas node (typically 3+). Requires redeployment when node count changes. |

Port Mapping is the default for all new PSC endpoints created in 2025+.

### Region Constraints

- PSC endpoints must be in the **same GCP region** as the Atlas cluster nodes they target.
- Multi-region Atlas clusters require **one PSC endpoint per region**.
- **Global Access** is a PSC feature that allows clients in *any* GCP region to reach a PSC endpoint in another region via Google's backbone — Atlas supports Global Access for PSC, useful when your GCP workloads span regions but cluster nodes are concentrated.

### Setup Steps (Console)

1. Atlas → **Network Access → Private Endpoint → Dedicated Clusters → GCP**.
2. Choose Atlas project and GCP region.
3. Atlas returns a **Service Attachment URI** and a **DNS zone**.
4. In GCP Console: **Network Services → Private Service Connect → Create Endpoint**.
   - Target: Managed Service → paste the Atlas Service Attachment URI.
   - Endpoint Network: your VPC.
   - Endpoint Subnet: must be in same region as attachment.
   - Enable Global Access if needed.
5. Copy the reserved internal IP for the endpoint.
6. Back in Atlas, register the endpoint (Console or API) — Atlas shows "Available" once handshake completes.
7. Update connection string to use the private endpoint hostnames Atlas provides.

### CLI Alternative (Atlas CLI)

```bash
# Create the Atlas-side GCP PSC endpoint
atlas privateEndpoints gcp create \
  --region US_EAST_4 \
  --projectId <projectId>

# List to get the service attachment names
atlas privateEndpoints gcp list --projectId <projectId>

# After creating GCP forwarding rule, link back to Atlas
atlas privateEndpoints gcp interfaces create <endpointServiceId> \
  --endpointName <gcpForwardingRuleName> \
  --gcpProjectId <gcpProjectId> \
  --projectId <projectId>
```

### Atlas Kubernetes Operator (AKO)

```yaml
apiVersion: atlas.mongodb.com/v1
kind: AtlasPrivateEndpoint
metadata:
  name: atlas-gcp-psc
spec:
  projectRef:
    name: my-atlas-project
  provider: GCP
  region: US_EAST_4
  gcpConfiguration:
    projectId: my-gcp-project
    endpoints:
      - name: atlas-psc-endpoint
        ipAddress: 10.0.2.10
```

### Terraform (mongodbatlas provider + google provider)

```hcl
resource "mongodbatlas_privatelink_endpoint" "gcp" {
  project_id    = var.atlas_project_id
  provider_name = "GCP"
  region        = "US_EAST_4"  # Atlas GCP region name
}

resource "google_compute_address" "psc_ip" {
  name         = "atlas-psc-ip"
  region       = "us-east4"
  subnetwork   = google_compute_subnetwork.private.id
  address_type = "INTERNAL"
}

resource "google_compute_forwarding_rule" "psc" {
  name                  = "atlas-psc-endpoint"
  region                = "us-east4"
  target                = mongodbatlas_privatelink_endpoint.gcp.service_attachment_names[0]
  load_balancing_scheme = ""
  network               = google_compute_network.vpc.id
  ip_address            = google_compute_address.psc_ip.id
  allow_global_access   = false  # set true for Global Access
}

resource "mongodbatlas_privatelink_endpoint_service" "gcp_svc" {
  project_id          = var.atlas_project_id
  private_link_id     = mongodbatlas_privatelink_endpoint.gcp.private_link_id
  provider_name       = "GCP"
  endpoint_service_id = google_compute_forwarding_rule.psc.name
  endpoints {
    ip_address    = google_compute_address.psc_ip.address
    endpoint_name = google_compute_forwarding_rule.psc.name
  }
}
```

---

## 5. Multi-Cloud Clusters (Replica Sets)

### What It Is

A standard Atlas replica set can span members across two or three cloud providers simultaneously. Each node runs in a distinct cloud and region. The replica set election and replication protocols are provider-agnostic — they run over the Atlas control plane's inter-cloud network.

### Supported Combinations

Atlas supports any combination of AWS, Azure, and GCP nodes in a single replica set. Common configurations:

| Config | Members | Use Case |
|---|---|---|
| AWS primary + Azure secondary | 3 nodes (2 AWS, 1 Azure) | DR warm standby on Azure |
| AWS + GCP + Azure | 5 nodes | True multi-cloud HA + analytics offload |
| GCP primary + AWS analytics | 3 nodes (2 GCP, 1 AWS) | Analytics on cheap AWS node |
| Azure primary + GCP secondary | 3 nodes | EU sovereignty with GCP DR |

### Latency Considerations

- Cross-cloud replication adds **15–80 ms** of WAN latency depending on region pairs (lower end for geographically close pairs such as AWS us-east-1 + Azure eastus; higher end for intercontinental pairs).
- `w: majority` writes must wait for cross-cloud acknowledgment if the majority quorum spans clouds. On a 3-node cluster where all three are in different clouds, p99 write latency typically increases by 30–80 ms vs. a same-cloud cluster — enough to breach SLOs on latency-sensitive paths.
- **Best practice:** place the majority of nodes (primary + one secondary) in the same cloud. Use the cross-cloud node as a **priority-0 secondary** (it can still be elected in an emergency but is not preferred) or a **hidden secondary** (priority 0 + hidden: true, completely removed from read routing). These are distinct: priority-0 nodes appear in read routing unless hidden; hidden nodes do not.
- Read preference `secondary` with tag sets can route reads to the cheapest or lowest-latency provider node.

### Use Cases

- **Cloud vendor lock-in avoidance:** workloads can shift primary provider without data migration.
- **Regulatory DR:** primary in AWS, warm standby in Azure satisfies some regulator requirements for geographic and vendor diversification.
- **Analytics offload:** route analytics reads to a cheaper cloud's secondary node.
- **Blue/green cloud migration:** run dual-cloud, gradually shift app traffic, then drop old cloud nodes.

---

## 6. Multi-Cloud Global Clusters (Zone Sharding)

### What It Is

Atlas Global Clusters apply **zone sharding** across geographic zones, where each zone maps to one or more cloud-region combinations. This enables:

- **Data residency:** EU user data lives only in EU zones (Azure westeurope + GCP europe-west1).
- **Low-latency writes:** apps write to the nearest zone.
- **Multi-cloud zones:** a single zone can include nodes from multiple clouds in the same geography.

### Zone Configuration

A Global Cluster zone specifies:
- A **geographic region** (a MongoDB geographic zone label, e.g., `EU`, `APAC`).
- One or more **cloud-region pairs** for the zone's shards.
- Shard count per zone.

Example: a Global Cluster with two zones:
```
Zone: Americas
  - AWS us-east-1 (3 nodes, M30)
  - Azure eastus2 (2 nodes, M30)

Zone: Europe
  - Azure westeurope (3 nodes, M30)
  - GCP europe-west1 (2 nodes, M30)
```

Shard keys for Global Clusters must include a **location field** (often a country code or region enum) that Atlas uses to route writes to the correct zone.

### Terraform Sketch

```hcl
# mongodbatlas_advanced_cluster is the current resource for provider 2.x.
# mongodbatlas_cluster (legacy) was deprecated in provider 1.x and removed in 2.x.
resource "mongodbatlas_advanced_cluster" "global" {
  project_id   = var.project_id
  name         = "global-multi-cloud"
  cluster_type = "GEOSHARDED"

  replication_specs {
    zone_name  = "Americas"
    num_shards = 2
    region_configs {
      region_name     = "US_EAST_1"
      provider_name   = "AWS"
      priority        = 7
      electable_specs {
        instance_size = "M30"
        node_count    = 3
      }
    }
    region_configs {
      region_name     = "US_EAST_2"
      provider_name   = "AZURE"
      priority        = 6
      electable_specs {
        instance_size = "M30"
        node_count    = 2
      }
    }
  }

  replication_specs {
    zone_name  = "Europe"
    num_shards = 2
    region_configs {
      region_name     = "EUROPE_WEST"
      provider_name   = "AZURE"
      priority        = 7
      electable_specs {
        instance_size = "M30"
        node_count    = 3
      }
    }
    region_configs {
      region_name     = "EUROPE_WEST_1"
      provider_name   = "GCP"
      priority        = 6
      electable_specs {
        instance_size = "M30"
        node_count    = 2
      }
    }
  }
}
```

---

## 7. Multi-Cloud Billing

### How Atlas Billing Works Across Clouds

Atlas billing is always **centralized in MongoDB's billing system**, regardless of which cloud the cluster nodes run on. The MongoDB bill reflects all node-hours, storage, data transfer, and backup charges across all clouds in a single invoice.

The cloud marketplaces provide **alternative payment channels** — they do not change what Atlas bills, only who handles the invoice and whether spend counts toward cloud commitments.

| Marketplace | What it covers |
|---|---|
| AWS Marketplace | Atlas spend billed through AWS; counts toward AWS EDP/PPA |
| Azure Marketplace | Atlas spend billed through Azure; counts toward MACC |
| GCP Marketplace | Atlas spend billed through GCP; counts toward CUD/committed use |
| Direct with MongoDB | Standard MongoDB invoice; no cloud commitment credit |

### Multi-Cloud Cluster Billing

When a cluster spans AWS + Azure + GCP, **all node costs appear in a single Atlas line item**, regardless of the payment channel. You cannot split a multi-cloud cluster's bill across multiple marketplace subscriptions.

Practical implication: if your budget rules require Azure spend to count toward MACC and GCP spend toward GCP committed use, you cannot split a single multi-cloud cluster across both marketplaces. You would need separate single-cloud clusters in each provider and shard/sync at the application layer.

### Choosing a Marketplace

- Use the marketplace that matches your largest committed cloud spend commitment.
- Atlas supports **one active marketplace subscription per Atlas organization**. Switching requires unlinking and relinking — a support-assisted process.
- PAYG (pay-as-you-go) marketplace subscriptions are available for both Azure and GCP for customers without committed spend.

---

## 8. Azure Partnership

### Microsoft Co-Sell

MongoDB participates in Microsoft's **Co-Sell Ready** and **Co-Sell Prioritized** partner programs. Co-sell means Microsoft field sellers can include Atlas in joint proposals with Azure services.

- MongoDB was recognized as the **2025 Microsoft United States Partner of the Year**.
- Co-sell engagements can accelerate procurement through Microsoft's EA (Enterprise Agreement) channels.
- Joint reference architectures (Azure Architecture Center) document Atlas as a first-class Azure database option.

### Azure Native Integration (ANI)

Atlas is an **Azure Native Integration** service — discoverable and deployable directly from the Azure Portal alongside first-party Azure services. This means:

- Atlas appears in Azure Portal's resource creation flow.
- Resource management (view, delete) is surfaced in the Azure Portal.
- Billing is unified on the Azure invoice.
- Support tickets can be opened from the Azure Portal and routed jointly.

### MACC (Microsoft Azure Consumption Commitment)

When Atlas is purchased through the Azure Marketplace, spend **counts toward MACC**. This is significant for customers with large Azure MACC commitments who want to use Atlas without "wasting" committed spend.

Setup: subscribe to Atlas via Azure Marketplace → link MongoDB account → all Atlas usage on that account flows through Azure billing.

Important nuance: MACC credit applies to Azure Marketplace purchases. If the Atlas organization is also subscribed to AWS Marketplace, **only the active marketplace subscription receives billing**. You cannot double-dip across marketplace channels for MACC.

---

## 9. GCP Partnership

### Google Cloud Partner Advantage

MongoDB participates in Google Cloud's **Partner Advantage** program at the Premier tier. Benefits include:

- Co-sell with Google Cloud field teams.
- Joint GTM (go-to-market) for regulated industries, analytics workloads.
- Inclusion in Google Cloud reference architectures and solution briefs.

### GCP Marketplace

Atlas is available on **Google Cloud Marketplace** with PAYG and committed-use pricing options. Purchasing through GCP Marketplace:

- Routes Atlas billing through Google Cloud Billing accounts.
- Spend can count toward **Google Cloud Committed Use Discounts (CUDs)** or **Sustained Use Discounts** depending on contract structure.
- Supports GCP Marketplace private offers for enterprise contract terms.

### Integration Depth

- Atlas integrates with **Vertex AI** for vector search and RAG pipelines (Atlas Vector Search as the retrieval layer).
- **Gemini + Atlas** reference architecture is co-developed with Google.
- Atlas supports **Google Cloud KMS** for Encryption at Rest (BYOK), and **Google Workload Identity** federation for Atlas database users.
- **Cloud SQL Federation** patterns allow BigQuery to federate reads against Atlas via Federated Queries.

---

## 10. Multi-Cloud DR Pattern

### Primary AWS + DR Azure/GCP

The most common enterprise DR pattern:

```
Normal state:
  AWS us-east-1 → Primary (M30, 3 nodes)
  Azure eastus2 → Secondary, priority 0, hidden: false (M30, 2 nodes)

DR trigger:
  Atlas auto-failover: if AWS nodes lose majority, Azure secondary can be
  promoted (if not priority 0) or manual failover initiated via Atlas API.
```

#### Priority Configuration for DR

- **Priority 0** on the Azure/GCP nodes: they never become primary automatically. Safe standby.
- **Priority 1–6** on the Azure/GCP nodes: they can become primary during failover. Choose based on whether you want automatic cloud failover.
- **Hidden secondary:** removed from client read routing entirely. True cold standby.

#### Failover Patterns

1. **Automatic cross-cloud failover:** Azure/GCP node has electable priority > 0. If AWS loses quorum, the Azure/GCP secondary becomes primary. Apps using Atlas connection strings with SRV (`mongodb+srv://`) automatically discover the new primary via DNS. RTO: ~30 seconds (election + DNS TTL).

2. **Manual failover:** Azure/GCP node is priority 0. A human or automation script calls `POST /api/atlas/v2/groups/{groupId}/clusters/{clusterName}/restartPrimaries` or adjusts node priorities via Atlas API to trigger election in Azure/GCP. RTO: minutes.

3. **Backup restore to DR cloud:** No cross-cloud replica; instead, Atlas continuous cloud backup restores to a new Azure/GCP cluster. RPO: ~15 minutes (oplog restore). RTO: 15–60 minutes depending on cluster size.

#### DR Testing (FireDrill Pattern)

Node priority is cluster topology config, not an advanced setting — use the Atlas Admin API to PATCH the cluster spec:

```bash
# Demote AWS nodes to priority 0, promoting Azure/GCP nodes to priority 7
# This triggers a new election; the Azure/GCP node with highest priority becomes primary
curl -s -u "${PUBLIC_KEY}:${PRIVATE_KEY}" --digest \
  -X PATCH "https://cloud.mongodb.com/api/atlas/v2/groups/${PROJECT_ID}/clusters/${CLUSTER_NAME}" \
  -H "Content-Type: application/json" \
  -d '{
    "replicationSpecs": [{
      "regionConfigs": [
        {"providerName":"AWS","regionName":"US_EAST_1","priority":0,"electableSpecs":{"instanceSize":"M30","nodeCount":3}},
        {"providerName":"AZURE","regionName":"US_EAST_2","priority":7,"electableSpecs":{"instanceSize":"M30","nodeCount":2}}
      ]
    }]
  }'

# Wait for state to reach IDLE, then verify primary cloud
atlas clusters describe ${CLUSTER_NAME} --projectId ${PROJECT_ID} \
  | jq '.replicationSpecs[].regionConfigs[] | {provider: .providerName, region: .regionName, priority: .priority}'

# Restore AWS priority to 7 to fail back
```

---

## 11. Cross-Cloud Egress Costs

### When Multi-Cloud Is Expensive

Cross-cloud data transfer is **billed by the source cloud** at standard inter-cloud egress rates. This is **outside Atlas billing** — it appears on your cloud bill.

| Transfer type | Approximate cost |
|---|---|
| AWS → Azure (same region pair) | ~$0.08–0.09/GB |
| AWS → GCP | ~$0.08–0.09/GB |
| Azure → GCP | ~$0.08/GB |
| Within same cloud, same region | $0.00 |
| Within same cloud, cross-region | $0.01–0.02/GB |

Atlas replication traffic between cross-cloud nodes **incurs egress from the source cloud**. For a 3-node replica set (AWS primary, Azure secondary, GCP secondary), every write that replicates generates egress from AWS → Azure and AWS → GCP.

**At 100 GB/day write throughput:**
- Cross-cloud replication egress cost: ~$16–18/day = ~$500/month just for egress
- Plus Atlas node costs on all three clouds

### When Multi-Cloud Makes Sense Despite Cost

- **DR value exceeds egress cost:** a $500/month egress bill is cheap insurance for a business-critical system.
- **Compliance mandate:** regulatory requirement for multi-cloud or multi-vendor redundancy.
- **Lock-in risk:** strategic decision to avoid any single-cloud dependency.
- **Low write throughput:** small databases with < 5 GB/day replication have negligible egress costs.

### Cost Optimization Techniques

1. **Priority-0 DR node:** replica still receives writes (replication is mandatory) but is not in the read pool, so no extra app reads generate cross-cloud traffic.
2. **Oplog sizing:** large oplog reduces re-sync egress during transient network partitions.
3. **Atlas Data Federation:** for analytics, federate reads across clouds without replication — read-only cross-cloud access, not continuous replication.
4. **Single-cloud primary + backup-based DR:** avoid continuous cross-cloud replication entirely; use cloud backup + restore for DR.

---

## 12. Common Multi-Cloud Failures and Pitfalls

### 1. Cross-Cloud Latency Assumptions

**Failure:** treating a cross-cloud secondary as equivalent to a same-cloud secondary for `w: majority` writes.

Write to AWS primary with `w: majority` on a 3-node (AWS, Azure, GCP) cluster: Atlas must wait for at least one non-primary (Azure or GCP) to acknowledge. If the nearest non-primary is cross-cloud at 60 ms RTT, p99 write latency increases by 50–150 ms vs. a same-cloud majority — typically enough to breach a 10 ms write SLO and cause client-visible tail latency spikes.

**Fix:** configure majority of nodes (2 of 3) in the primary cloud. Use `w: 1` for latency-sensitive paths and accept durability tradeoff, or accept the latency.

### 2. Private Link / PSC Per-Region Requirement

**Failure:** assuming one Private Link / PSC endpoint covers all regions of a multi-region cluster.

Each Atlas region in a cluster requires its own Private Endpoint. A 3-region cluster (us-east-1, us-west-2, eu-west-1) needs 3 Private Link configurations — missing any one means the app cannot reach that shard/node.

**Fix:** automate endpoint provisioning with Terraform; iterate over all `replicationSpecs[].regionsConfig` region names. Example pattern:

```hcl
locals {
  # Collect all distinct Atlas regions from the cluster spec
  atlas_regions = distinct([
    for spec in mongodbatlas_cluster.main.replication_specs :
    for rc in spec.regions_config : rc.region_name
  ])
}

resource "mongodbatlas_privatelink_endpoint" "per_region" {
  for_each      = toset(local.atlas_regions)
  project_id    = var.atlas_project_id
  provider_name = "AWS"   # or AZURE / GCP
  region        = each.value
}
```

One `mongodbatlas_privatelink_endpoint` per region ensures every cluster node is reachable through private networking.

### 3. Billing Surprise: Egress on Analytics Reads

**Failure:** routing analytics queries to a cross-cloud secondary assuming "reads don't cost egress."

Read replies also generate egress from the cloud where the secondary lives back to the client. A large analytics scan on a GCP secondary, with the app running in AWS, generates GCP egress charges.

**Fix:** co-locate analytics compute with the analytics secondary node cloud, or use Atlas Data Federation, which federates reads and can cache results in the primary cloud.

### 4. Marketplace Single-Subscription Limit

**Failure:** expecting to subscribe to both Azure Marketplace and GCP Marketplace simultaneously to capture MACC + GCP commitment credit on the same Atlas org.

Only one marketplace subscription can be active per Atlas organization at a time.

**Fix:** choose the marketplace that maximizes committed-spend credit. Use a separate Atlas org for the secondary cloud if billing split is a hard requirement (operational complexity tradeoff).

### 5. Region Availability Gaps

Not all Atlas features are available in all regions or all clouds. Known gaps (verify in Atlas docs for current state):

- **Atlas Stream Processing:** Azure regions were added later than AWS; GCP followed. Always check the Stream Processing supported regions list before architecture commits.
- **Serverless / Flex instances:** narrower region set than dedicated clusters on all three clouds.
- **Atlas Search (Lucene):** available across clouds, but dedicated Search Nodes have a narrower region set than embedded Search.
- **Atlas Vector Search:** generally available on AWS; Azure and GCP coverage expanding — verify for specific regions.

### 6. VNet/VPC CIDR Conflicts

**Failure:** Atlas VPC CIDR overlaps with the application VNet, blocking peering.

Atlas auto-assigns `/21` CIDRs. If your corporate network uses `192.168.0.0/16` or `10.0.0.0/8` broadly, there is a high probability of conflict.

**Fix:** customize the Atlas project network CIDR at project creation time before any clusters are deployed (cannot change after first cluster). Use `/21` subnets from a dedicated, non-routed range.

### 7. DNS Resolution in Private Endpoint Scenarios

**Failure:** app can reach the Private Endpoint IP but connection string hostnames do not resolve.

Atlas Private Link hostnames use a special DNS zone. In Azure, you need a **Private DNS Zone** linked to your VNet. In GCP with PSC, you configure a **Cloud DNS private zone** pointing to the PSC endpoint IP(s).

**Fix:**
- Azure: create `privatelink.mongodb.net` Private DNS Zone; link to VNet; add A records that Atlas provides.
- GCP: create a Cloud DNS managed private zone with Atlas-provided FQDN → PSC endpoint IP mapping.

---

## Quick Reference: Atlas Multi-Cloud Terraform Module Structure

```
modules/
  atlas-cluster/
    main.tf          # mongodbatlas_cluster with replication_specs
    variables.tf     # project_id, regions, node_counts, provider_names
    outputs.tf       # connection_strings, srv_address, cluster_id

  atlas-azure-private-link/
    main.tf          # mongodbatlas_privatelink_endpoint + azurerm_private_endpoint
    variables.tf     # atlas_project_id, azure_subnet_id, region

  atlas-gcp-psc/
    main.tf          # mongodbatlas_privatelink_endpoint + google_compute_forwarding_rule
    variables.tf     # atlas_project_id, gcp_network, gcp_region
    dns.tf           # google_dns_managed_zone + google_dns_record_set for PSC FQDNs
```

---

## Sources

- [Announcing Azure Private Link Integration for MongoDB Atlas](https://www.mongodb.com/blog/post/announcing-azure-private-link-integration-for-mongo-db-atlas)
- [Atlas Stream Processing Now Supports Azure and Azure Private Link](https://www.mongodb.com/blog/post/atlas-stream-processing-now-supports-azure-and-azure-private-link)
- [Announcing Google Private Service Connect Integration for MongoDB Atlas](https://www.mongodb.com/company/blog/product-release-announcements/announcing-google-private-service-connect-psc-integration-mongodb-atlas)
- [Introducing PSC Interconnect and Global Access for MongoDB Atlas](https://www.mongodb.com/developer/products/atlas/psc-interconnect-and-global-access/)
- [Multi-Cloud Deployment Paradigm — Atlas Architecture Center](https://www.mongodb.com/docs/atlas/architecture/current/deployment-paradigms/multi-cloud/)
- [MongoDB Atlas Launches on Microsoft Azure Marketplace](https://www.mongodb.com/company/newsroom/press-releases/mongodb-atlas-launches-on-microsoft-azure-marketplace-offering-unified-billing-for-joint-customers)
- [Microsoft Ignite 2025: Deepening the MongoDB Alliance with Microsoft](https://www.mongodb.com/company/blog/events/microsoft-ignite-2025-deepening-mongodb-microsoft-alliance)
- [GCP Self-Serve Marketplace — Atlas Docs](https://www.mongodb.com/docs/atlas/billing/gcp-self-serve-marketplace/)
- [Accessing Multi-Regional MongoDB Atlas with Private Service Connect (Google Codelabs)](https://codelabs.developers.google.com/codelabs/psc-mongo-globalaccess)
- [Deploy MongoDB Atlas in Azure — Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/databases/architecture/mongodb-atlas-baseline)

## See Also

- [[mongodb-atlas-azure]] — Deep Azure-specific reference: Private Link DNS zones, NSG rules, hub-and-spoke, Entra ID OIDC/Workload Identity, Azure Key Vault BYOK, AKO on AKS, Event Hub stream processing, MACC billing, Sentinel observability, Terraform + Bicep IaC, and Azure troubleshooting playbook
- [[mongodb-atlas-gcp]] — Deep GCP-specific reference: PSC port-mapped architecture and migration, Cloud DNS, Shared VPC, Workload Identity Federation OIDC, Cloud KMS BYOK with two-alert failsafe, GKE + AKO, Vertex AI + Vector Search, BigQuery/Dataflow CDC, Cloud Run connection pooling, Pub/Sub stream processing, GCP Marketplace billing, full region mapping table, Terraform IaC, and GCP troubleshooting playbook
