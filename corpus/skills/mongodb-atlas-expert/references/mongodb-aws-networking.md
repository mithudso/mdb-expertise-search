<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-aws-networking` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-aws-networking
description: >
  MongoDB Atlas networking on AWS — VPC peering, AWS PrivateLink, network access lists, DNS/SRV,
  multi-region networking, Transit Gateway patterns, TLS encryption, security groups, connection
  troubleshooting, CloudFormation/Terraform IaC, EventBridge/Lambda/KMS integration, and the
  AWS ISV Accelerate/Marketplace partnership model.
  TRIGGER: designing or troubleshooting Atlas network architecture on AWS; configuring VPC
  peering or PrivateLink; debugging Atlas connection timeouts or DNS failures; planning
  CloudFormation/Terraform IaC for Atlas on AWS; KMS encryption at rest; EventBridge/Lambda
  integration; AWS Marketplace private offers or EDP credits for Atlas; ISV Accelerate co-sell;
  AWS funded days; "atlas networking", "vpc peering atlas", "privatelink atlas", "atlas aws",
  "connection timeout mongodb", "dns srv mongodb", "transit gateway atlas", "kms atlas",
  "edp credits atlas", "aws marketplace mongodb".
  SKIP: Azure networking — use mongodb-atlas-azure; GCP networking — use mongodb-atlas-gcp;
  Kubernetes-specific Atlas networking — use mongodb-atlas-kubernetes-operator; generic
  Atlas cluster configuration without networking focus — use mongodb-atlas-expert.
version: "1.1.0"
updated: "2026-05-29"
origin: research
category: mongodb
tags:
  - mongodb-atlas
  - aws
  - networking
  - vpc-peering
  - privatelink
  - terraform
  - cloudformation
  - kms
  - eventbridge
  - lambda
  - marketplace
  - isv-accelerate
  - private-endpoint
  - tls
  - connection-troubleshooting
  - msk
  - kafka
triggers:
  - atlas networking
  - vpc peering
  - private endpoint
  - privatelink
  - atlas aws
  - mongodb aws
  - aws marketplace mongodb
  - atlas terraform
  - atlas cloudformation
  - kms encryption atlas
  - connection timeout atlas
  - dns srv mongodb
  - multi-region atlas
  - transit gateway atlas
  - aws funded days
  - edp credits atlas
whenNotToUse:
  - Azure networking for Atlas — use mongodb-atlas-azure
  - GCP networking for Atlas — use mongodb-atlas-gcp
  - Kubernetes-specific Atlas networking — use mongodb-atlas-kubernetes-operator
  - Non-networking Atlas cluster configuration — use mongodb-atlas-expert
related_skills:
  - mongodb-atlas-expert
  - mongodb-atlas-azure
  - mongodb-atlas-gcp
  - mongodb-atlas-kubernetes-operator
  - mongodb-atlas-iac
  - mongodb-kafka-connector
---

# MongoDB Atlas on AWS — Networking, Integration & Partnership

## 1. Atlas Networking Architecture

### VPC Peering

VPC Peering creates a private, encrypted connection between your AWS VPC and Atlas's AWS VPC. Traffic flows over AWS's private backbone.

**Setup**: Atlas Admin Console → Network Access → Peering → accept in your AWS account → configure route tables → verify bidirectional connectivity.

**Constraints**:
- Region-specific: peering works only within the same AWS region
- CIDR conflicts: your VPC CIDR cannot overlap Atlas VPC CIDR (Atlas uses /18 ranges)
- No transitive connectivity: VPC-A peers with Atlas, VPC-A peers with VPC-B — VPC-B cannot reach Atlas
- Atlas VPC is managed by MongoDB; you cannot modify its routing or security groups
- No additional peering charges; standard AWS data transfer rates apply

### Private Endpoints (AWS PrivateLink)

PrivateLink exposes Atlas as a service endpoint in your VPC. Applications connect to a local ENI without traversing the public internet.

**Advantages over VPC peering**:
- Unidirectional (your VPC → Atlas only)
- Works with all cluster types including sharded
- No CIDR overlap required
- Multi-VPC access without multiple peering connections
- Compatible with AWS Transit Gateway and Direct Connect

**Terraform**:
```hcl
resource "mongodbatlas_privatelink_endpoint" "pe" {
  project_id    = var.atlas_project_id
  provider_name = "AWS"
  region_name   = "us-east-1"
}

resource "aws_vpc_endpoint" "atlas" {
  vpc_id             = var.vpc_id
  service_name       = mongodbatlas_privatelink_endpoint.pe.endpoint_service_name
  vpc_endpoint_type  = "Interface"
  subnet_ids         = var.private_subnet_ids
  security_group_ids = [aws_security_group.atlas_pe.id]
}
```

**Atlas Admin API**:
```
POST /api/atlas/v2/groups/{projectId}/privateEndpoint/endpointService
{ "providerName": "AWS", "region": "us-east-1" }
```

### Network Access Lists

Project-wide IP allowlist limiting which IPs/CIDRs can connect.

- Maximum 200 entries per project
- Supports single IPs, CIDR ranges, and AWS security group IDs
- Propagation: ~5 minutes cluster-wide
- **Anti-pattern**: 0.0.0.0/0 exposes the cluster to the public internet — eliminates network-layer isolation
- Best practice: use private endpoints or VPC peering; restrict allowlist to known application CIDRs

### DNS and SRV Records

**mongodb+srv format**: `mongodb+srv://user:pass@cluster0.abc123.mongodb.net/db`

- Client performs SRV query for `_mongodb._tcp.cluster0.abc123.mongodb.net`
- DNS returns all mongos/replica set member addresses
- Automatic discovery without hardcoding IPs

**Split-horizon DNS**: Atlas returns different IPs based on connection source:
- Public internet → public IPs
- Private endpoint → private endpoint address
- VPC peering → private replica set member IPs

**Diagnostic**: `dig _mongodb._tcp.cluster0.abc123.mongodb.net SRV`

### Multi-Region Networking

- Replication traffic between regions encrypted with TLS 1.2+
- No Atlas data transfer charges between regions (AWS internal)
- Latency: typically 10-50ms per region pair
- Global Clusters: automatic sharding by region, client connects to nearest
- Multi-region write concern adds 30-100ms for majority acknowledgment

### Transit Gateway

Atlas does not support direct Transit Gateway peering. Patterns:
1. **Private Endpoints (preferred)**: single endpoint accessible from multiple VPCs via TGW
2. **VPC peering + TGW**: peer Atlas VPC to app VPC, use TGW for inter-app connectivity
3. **Multi-account**: share Private Endpoint across accounts using AWS Resource Access Manager (RAM)

### Network Encryption

- TLS 1.2 minimum enforced; TLS 1.3 supported
- Certificates from AWS Certificate Manager or DigiCert; auto-rotated
- All connections encrypted end-to-end (no plaintext option)
- VPC peering and PrivateLink traffic encrypted by AWS infrastructure automatically

### Security Groups

Atlas uses project-level network access lists (not per-cluster security groups).

Customer-side configuration:
- Allow outbound to ports 27015-27017 (MongoDB standard + sharded range)
- For Private Endpoints: SG on the ENI allowing inbound from application SGs
- Restrict egress to Atlas VPC CIDR or private endpoint IP

### Connection Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| Connection timeout | Firewall/SG blocking, allowlist missing | Verify SGs, NACLs, IP allowlist entry |
| TLS handshake failure | Wrong TLS version or CA bundle | Ensure driver supports TLS 1.2+; update CA bundle |
| DNS resolution failed | SRV query blocked | Verify DNS egress on port 53; check `dig SRV` |
| Connection refused | Port closed or cluster paused | Verify port 27017/27015-27017; check cluster state |
| Connection pool exhausted | Too many connections | Reduce maxPoolSize; check instance count |
| Authentication failed | Wrong credentials or authSource | Verify user/pass; use `authSource=admin` |

**Diagnostic steps**:
1. `telnet cluster0.mongodb.net 27017` — verify network path
2. `dig _mongodb._tcp.cluster0.abc123.mongodb.net SRV` — verify DNS
3. Atlas Activity Log → connection events and rejections
4. Driver logs → enable connection debug logging

---

## 2. AWS Integration Services

### CloudFormation

MongoDB Atlas CFN resources (`MongoDB::Atlas::*`) deploy Atlas infrastructure as IaC.

**Coverage**: Clusters, database users, network peering, private endpoints, IP access lists, encryption at rest, auditing, project settings.
**Limitation**: CloudFormation only deploys Atlas clusters to AWS — Azure/GCP require Terraform or CDK.
**Resource types**: `MongoDB::Atlas::Cluster`, `MongoDB::Atlas::DatabaseUser`, `MongoDB::Atlas::NetworkPeering`, `MongoDB::Atlas::PrivateEndpointService`

**Status (2026)**: 17/26 target Atlas features shipped in CFN; remaining 9 in progress.

### Terraform Atlas Provider

Provider: `mongodb/mongodbatlas` — version 2.12.0 (May 2026), 72.5M downloads, 139 versions.

**Key resources**:
- `mongodbatlas_cluster` / `mongodbatlas_advanced_cluster`
- `mongodbatlas_privatelink_endpoint` / `mongodbatlas_privatelink_endpoint_service`
- `mongodbatlas_network_peering`
- `mongodbatlas_database_user`
- `mongodbatlas_project_ip_access_list`
- `mongodbatlas_encryption_at_rest`
- `mongodbatlas_cloud_backup_schedule`
- `mongodbatlas_federated_settings_org_config`

### EventBridge

Atlas integrates as an EventBridge event source — change events from Atlas trigger downstream AWS services (Lambda, Step Functions, SNS, SQS).

**Use cases**: Event-driven architectures, real-time data pipelines, operational alerts.
**Setup**: Atlas Admin Console → Triggers → EventBridge → configure AWS account ID and region.

### Lambda

Atlas + Lambda serverless pattern:
- Lambda connects to Atlas via connection string (use Secrets Manager or KMS-encrypted env vars)
- Connection pooling: reuse connections across Lambda invocations via module-level initialization
- Cold start: first invocation establishes TLS connection (~200-500ms); subsequent invocations reuse
- VPC Lambda: if Lambda is in a VPC, use Private Endpoint for Atlas connectivity

### KMS Encryption

**Encryption at Rest (EAR)** with customer-managed keys (CMK/BYOK):
- AWS KMS key ARN configured per Atlas project
- Atlas encrypts data files, journal, and oplog using the customer's KMS key
- Key rotation: automatic via KMS key rotation policy (annual) or manual rotation
- CSFLE/Queryable Encryption: client-side encryption using KMS as the key provider

**Terraform**:
```hcl
resource "mongodbatlas_encryption_at_rest" "ear" {
  project_id = var.atlas_project_id
  aws_kms_config {
    enabled              = true
    customer_master_key_id = var.kms_key_id
    region               = "us-east-1"
    role_id              = mongodbatlas_cloud_provider_access_setup.aws.role_id
  }
}
```

### IAM Authentication

Atlas supports passwordless authentication via AWS IAM:
- AssumeRole: applications authenticate using IAM role credentials instead of username/password
- OIDC Workforce Identity: federate corporate IdP (Okta, Azure AD) to Atlas via OIDC
- Connection string: `mongodb+srv://...?authMechanism=MONGODB-AWS`

### Data Federation & Stream Processing

- **Atlas Data Federation**: query S3 data lakes through Atlas SQL interface; federated queries across Atlas clusters + S3
- **Atlas Stream Processing**: ingest from Kafka, Kinesis; process with aggregation pipeline; write to Atlas or S3

### AWS Landing Zone Pattern

AWS Prescriptive Guidance publishes a reference architecture for building an AWS landing zone that includes MongoDB Atlas:
- Multi-account structure (shared services, workload, security)
- PrivateLink connectivity from workload accounts to Atlas
- Centralized DNS resolution via Route 53
- KMS key hierarchy per account
- CloudFormation StackSets for consistent Atlas resource deployment

---

## 3. AWS Partnership & Commercial Model

### ISV Accelerate Program

MongoDB participates in the AWS ISV Accelerate co-sell program:
- Joint selling with AWS sales organization
- ACE (APN Customer Engagement) opportunity sharing
- Co-sell referral benefits and incentives
- Marketing Development Funds (MDF) for demand generation (2026: available to newly enrolled partners)

### AWS Marketplace

Atlas is listed on AWS Marketplace:
- **Procurement**: customers can purchase Atlas through Marketplace, consolidating billing with AWS
- **Private Offers**: custom pricing/terms negotiated between MongoDB and the customer, fulfilled through Marketplace
- **EDP Credits**: customers with AWS Enterprise Discount Program commitments can apply EDP credits toward Atlas Marketplace purchases — Atlas consumption counts toward their AWS commit
- **MPOPP**: AWS Marketplace Private Offer Promotion Program provides promotional credits to incentivize new customer acquisition

### Funded Days / Migration Credits

- **AWS funded consulting days**: AWS provides PS/consulting days to partners for customer engagements. Eligibility often requires Atlas consumption or a documented migration path to Atlas.
- **ISV Workload Migration Program (WMP)**: direct credit disbursement to end customers for eligible SaaS deployments through Marketplace
- **Migration Acceleration Program (MAP)**: AWS credits for customers migrating workloads to AWS; applicable when migrating on-prem MongoDB to Atlas on AWS
- **Scope restriction**: AWS-funded days may not apply to on-prem-only MongoDB work unless tied to an Atlas consumption or migration path

### Competitive Dynamics

AWS offers competing database services:
- **Amazon DocumentDB**: MongoDB-compatible (wire protocol) managed service
- **Amazon DynamoDB**: key-value/document NoSQL service
- **Aurora PostgreSQL**: relational alternative

**Coexistence**: MongoDB and AWS maintain a strategic partnership despite competition. Atlas runs on AWS infrastructure; MongoDB is an Advanced Technology Partner. Joint reference architectures, re:Invent sessions, and co-marketing continue. The partnership is commercially motivated — Atlas consumption on AWS generates AWS infrastructure revenue.

### Deal Patterns

- **Commit-and-consume**: customer commits to a spend level on Atlas via Marketplace; consumption draws down the commitment
- **EDP alignment**: Atlas purchases through Marketplace count toward the customer's AWS EDP commit, making Atlas spend "free" against existing AWS commitments
- **Private offers**: negotiated pricing for enterprise customers; can include multi-year terms, custom SLAs
- **Co-sell**: AWS sales team refers opportunities to MongoDB; MongoDB refers opportunities to AWS. Both track via ACE pipeline.

---

## 4. Anti-Patterns

| Anti-Pattern | Why It Fails | Remedy |
|---|---|---|
| 0.0.0.0/0 allowlist | Exposes cluster to internet | Use Private Endpoints or VPC Peering |
| VPC Peering for sharded clusters | Incomplete connectivity | Use Private Endpoints (full sharded support) |
| Hardcoding IP addresses | Breaks on failover/scaling | Use mongodb+srv connection strings |
| Single-region deployment | No DR capability | Deploy multi-region with Global Clusters |
| Lambda without connection reuse | Cold start on every invocation | Initialize client at module scope, outside handler |
| KMS key in same account as data | Single blast radius | Use dedicated security account for KMS keys |
| Terraform without state locking | Concurrent modifications | Use S3 backend with DynamoDB lock table |
| Ignoring EDP credit applicability | Missed cost savings | Verify Atlas Marketplace purchases count toward EDP commit |

---

## 5. References

- [MongoDB Atlas on AWS](https://www.mongodb.com/mongodb-on-aws)
- [Atlas AWS PrivateLink Setup](https://www.mongodb.com/docs/atlas/security-private-endpoint/)
- [Terraform Atlas Provider](https://registry.terraform.io/providers/mongodb/mongodbatlas/latest/docs)
- [Atlas CloudFormation Integration](https://www.mongodb.com/products/integrations/aws-cloudformation)
- [AWS KMS Encryption at Rest](https://docs.atlas.mongodb.com/security-aws-kms/)
- [AWS Landing Zone with Atlas](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/build-aws-landing-zone-that-includes-mongodb-atlas.html)
- [AWS ISV Accelerate Program](https://aws.amazon.com/partners/programs/isv-accelerate/)
- [Atlas EventBridge Integration](https://www.mongodb.com/company/newsroom/press-releases/mongodb-atlas-adds-support-for-aws-cloudformation-eventbridge-privatelink-and-more)
- [MongoDB Atlas Data Encryption Guidance](https://www.mongodb.com/docs/atlas/architecture/current/data-encryption/)
- [AWS Migration Architectures for MongoDB](https://docs.aws.amazon.com/prescriptive-guidance/latest/migration-mongodb-atlas/architecture.html)

---

## MongoDB Kafka Connector on AWS (addendum)

When deploying the MongoDB Kafka Connector on AWS, two managed options exist:

### Amazon MSK Connect

Deploy the connector as a custom plugin on MSK Connect:

1. Upload the connector JAR to S3.
2. Create a custom plugin in MSK Connect from the S3 object.
3. Create a connector using the plugin with MSK IAM or SCRAM auth.

**IAM role requirements for MSK Connect → Atlas:**
- MSK IAM connect permissions on the cluster/topic ARNs (`kafka-cluster:Connect`, `kafka-cluster:WriteData`, `kafka-cluster:ReadData`)
- Network access from MSK Connect workers to Atlas: configure Atlas IP access list with MSK worker subnet CIDRs, or use VPC peering / Atlas PrivateLink from the MSK VPC to Atlas

**MSK IAM authentication** (in worker config):
```properties
security.protocol=SASL_SSL
sasl.mechanism=AWS_MSK_IAM
sasl.jaas.config=software.amazon.msk.auth.iam.IAMLoginModule required;
sasl.client.callback.handler.class=software.amazon.msk.auth.iam.IAMClientCallbackHandler
```

**MongoDB AWS IAM auth** (MONGODB-AWS mechanism — connector v1.5+):
```
connection.uri=mongodb+srv://cluster.mongodb.net/?authMechanism=MONGODB-AWS&authSource=%24external
```
Credentials are sourced from the MSK Connect execution role's instance profile automatically.

### MSK Serverless + MSK Connect + Atlas (serverless pipeline)

A fully serverless pattern: MSK Serverless as the broker (no cluster management), MSK Connect for the connector workers (auto-scaled), Atlas as the destination. Authentication uses IAM throughout. See the [AWS Big Data Blog walkthrough](https://aws.amazon.com/blogs/big-data/build-a-serverless-streaming-pipeline-with-amazon-msk-serverless-amazon-msk-connect-and-mongodb-atlas/).

See `mongodb-kafka-connector` skill for full connector source/sink configuration, write model strategies, and DLQ setup.
