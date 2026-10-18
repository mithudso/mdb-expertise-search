---
name: atlas-network-peering
title: Set up VPC or VNet peering between your network and Atlas
summary: Plan the Atlas network container CIDR, request a peering connection from Atlas, accept it on the cloud side, add routes and an access list entry, and verify connectivity (AWS main path, Azure and GCP differences).
applies_to: [atlas]
sources:
  - skills/mongodb-atlas-expert/references/mongodb-aws-networking.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-terraform.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-multicloud.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-azure.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-gcp.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-iac.md
  - skills/mongodb-operations-expert/references/mongodb-security-architecture.md
---
# Set up VPC or VNet peering between your network and Atlas

## When to use
- You need private routing between an application VPC/VNet and a dedicated Atlas cluster and you accept two-way routing.
- A private endpoint is not an option (existing design, policy, or you want private member IPs in the peered range).
- You are maintaining an existing peered setup. For new Azure and GCP deployments the corpus recommends Private Link or Private Service Connect instead (see the `atlas-private-link` recipe).

## Prerequisites (checklist)
- [ ] Dedicated cluster (M10 or larger). Flex does not support peering.
- [ ] You decided the Atlas network container CIDR before the first cluster or peering exists. Atlas locks the CIDR once an M10+ cluster or a peering connection exists; changing it means removing clusters and peerings.
- [ ] The Atlas container CIDR does not overlap your VPC/VNet CIDR, any other peered network, or any on-premises range that routes into those networks.
- [ ] AWS: account id, VPC id, region and VPC CIDR. Azure: directory (tenant) id, subscription id, resource group, VNet name. GCP: GCP project id and VPC network name.
- [ ] Permission to accept a peering connection and edit route tables (AWS), peerings (Azure) or network peerings (GCP) in your account.
- [ ] Atlas project id (`<project-id>`) and an Atlas role that can manage network access.

## Steps

### AWS (main path)

1. Plan CIDRs. Write down your VPC CIDR(s), the Atlas container CIDR, and every network that must reach Atlas.
   ```text
   your VPC:        10.0.0.0/16
   Atlas container: 192.168.248.0/21   (example value from the Terraform corpus)
   ```
   The corpus is inconsistent on size: one note says Atlas uses /18 ranges for AWS, the Terraform example uses a /21, and a CLI example uses /24. Verify in the current MongoDB docs: the allowed size and default for an AWS container CIDR.
   Expect: no overlap between any two ranges in your list.

2. Create or check the network container for the region. Terraform models it explicitly; with the CLI or UI Atlas creates it with the first cluster or peering.
   ```hcl
   resource "mongodbatlas_network_container" "aws" {
     project_id       = var.project_id
     atlas_cidr_block = "192.168.248.0/21"
     provider_name    = "AWS"
     region_name      = "US_EAST_1"
   }
   ```
   Expect: one container per project and region for AWS (one per project for GCP).

3. Request the peering from Atlas.
   ```bash
   atlas networking peering create aws \
     --projectId <project-id> \
     --atlasCidrBlock 192.168.248.0/21 \
     --accountId <aws-account-id> \
     --vpcId <vpc-id> \
     --region us-east-1 \
     --routeTableCidrBlock 10.0.0.0/16
   atlas networking peering watch <peering-id> --projectId <project-id>
   ```
   UI path: Atlas Network Access, Peering, add the peering connection. Terraform: `mongodbatlas_network_peering` with `container_id`, `aws_account_id`, `vpc_id`, `accepter_region_name`, `route_table_cidr_block`.
   Expect: a peering id; the connection waits for you to accept it in AWS.

4. Accept the request in your AWS account.
   ```bash
   aws ec2 describe-vpc-peering-connections --filters Name=status-code,Values=pending-acceptance
   aws ec2 accept-vpc-peering-connection --vpc-peering-connection-id <pcx-id>
   ```
   Terraform equivalent: `aws_vpc_peering_connection_accepter` with `vpc_peering_connection_id = mongodbatlas_network_peering.aws_peer.connection_id`.
   Expect: status becomes `active`; `atlas networking peering watch` returns when the Atlas side is available.

5. Add routes in every route table that serves subnets needing Atlas. Destination is the Atlas container CIDR, target is the peering connection.
   ```bash
   aws ec2 create-route --route-table-id <rtb-id> \
     --destination-cidr-block 192.168.248.0/21 \
     --vpc-peering-connection-id <pcx-id>
   ```
   Expect: the route shows state `active` in `aws ec2 describe-route-tables`.

6. Allow your side's traffic. Outbound security group rules must permit MongoDB ports to the Atlas CIDR. The AWS corpus note lists 27015-27017 outbound, restricted to the Atlas VPC CIDR. Network ACLs must allow the same.
   Expect: no explicit deny in the security group or NACL for the Atlas CIDR on those ports.

7. Add an access list entry. Peering does not bypass the project IP access list. Add the peered VPC CIDR (or an AWS security group id from the peered VPC).
   ```bash
   atlas accessLists create --projectId <project-id> \
     --type cidrBlock --ip 10.0.0.0/16 --comment "peered app VPC"
   # or:
   atlas accessLists create --projectId <project-id> \
     --type awsSecurityGroup --ip <sg-id>
   ```
   Expect: the entry lists as active within about five minutes (the corpus quotes roughly 5 minutes of propagation).

8. Use the peering-aware connection string (Terraform: `connection_strings[0].private` and `private_srv`; in the UI, the "Peering" connection type). Test from an instance in a routed subnet.
   ```bash
   mongosh "<peering-srv-connection-string>" --username <db-user> \
     --eval 'db.runCommand({ ping: 1 })'
   ```
   Expect: `{ ok: 1 }`. Hostnames in the SRV answer resolve to private member IPs inside the Atlas container CIDR.

### Azure differences
1. Create a VNet in the same region as the cluster. Atlas network container CIDR is set once per project and region and cannot change after the first cluster is deployed, so set it at project creation.
2. In Atlas: Network Access, VNet Peering, Add Peering Connection. Supply subscription id, resource group, VNet name and tenant id (Terraform: `azure_directory_id`, `azure_subscription_id`, `resource_group_name`, `vnet_name`).
3. Accept in the Azure Portal under Virtual Network, Peerings.
4. Add the Atlas CIDR to NSGs and route tables where needed. Application and Atlas address spaces must not overlap.
5. Cross-region needs global VNet peering. In hub-and-spoke designs every spoke needs its own peering, which is why Private Link is recommended.

### GCP differences
1. A container is created per project (not per region). The Atlas VPC CIDR is auto-assigned (default /18, matching the Terraform container example `192.168.0.0/18`) and customisable only at project creation. Verify in the current MongoDB docs: the default container size for GCP.
2. Request the peering from Atlas with your GCP project id and VPC network name (`mongodbatlas_network_peering`, provider `GCP`).
3. Create the reciprocal peering on the GCP side using the Atlas GCP project id and Atlas VPC name that Atlas returns (`atlas_gcp_project_id`, `atlas_vpc_name`):
   ```hcl
   resource "google_compute_network_peering" "gcp_to_atlas" {
     name         = "gcp-to-atlas"
     network      = google_compute_network.app.id
     peer_network = "https://www.googleapis.com/compute/v1/projects/${mongodbatlas_network_peering.gcp_peer.atlas_gcp_project_id}/global/networks/${mongodbatlas_network_peering.gcp_peer.atlas_vpc_name}"
   }
   ```
4. Add the peered range to the Atlas access list. The corpus calls GCP peering legacy: it exchanges routes in both directions and extends the trust boundary.

### Kubernetes operator
`AtlasNetworkContainer` and `AtlasNetworkPeering` are independent CRDs (operator v2.8 or later per the corpus). If you also leave `AtlasProject.spec.networkPeers` set, the operator alternates between the two configurations on each reconcile; remove the old sub-object.

## Verify
```bash
atlas networking peering list --projectId <project-id>
atlas networking peering describe <peering-id> --projectId <project-id>
aws ec2 describe-vpc-peering-connections --vpc-peering-connection-ids <pcx-id>
nslookup -type=SRV _mongodb._tcp.<peering-srv-host>
mongosh "<peering-srv-connection-string>" --eval 'db.runCommand({ ping: 1 })'
```
Expect: the peering is available on both sides, routes are active, SRV answers resolve to private IPs in the container CIDR, and ping returns `ok: 1` from every subnet you routed. Test from one subnet per route table.

## Rollback / abort
1. Switch applications back to the previous connection string and keep the old access list entries until traffic is confirmed.
2. Remove the routes to the peering from your route tables.
3. Delete the peering: `atlas networking peering delete <peering-id> --projectId <project-id> --force`, and delete the cloud-side peering connection if it remains.
4. Remove the access list entry for the peered CIDR.
5. Do not delete the container to change its CIDR unless you accept removing every cluster and peering that depends on it.

## Pitfalls
- Overlapping CIDRs. Atlas cannot be re-addressed after the first cluster exists; plan before creating anything.
- Accepting the peering but forgetting the route table entries, or adding them to only one of several route tables.
- Expecting transitive reach: if VPC-A peers with Atlas and VPC-A peers with VPC-B, VPC-B cannot reach Atlas. Atlas does not peer with Transit Gateway; use private endpoints for hub designs.
- Forgetting the access list entry: peering gives a route, not authorisation.
- Peering is region-bound in the corpus ("works only within the same AWS region", Azure needs global VNet peering for cross-region). Verify in the current MongoDB docs: current cross-region peering support.
- The corpus lists "VPC Peering for sharded clusters" as an anti-pattern with "incomplete connectivity". Verify in the current MongoDB docs before relying on peering for a sharded cluster; a private endpoint has full sharded support.
- Hardcoding member IPs instead of using the SRV string.
- Using peering for new GCP deployments when PSC is available.
- Declaring both the AKO sub-object and the independent CRD for the same peering.

## Sources
- skills/mongodb-atlas-expert/references/mongodb-aws-networking.md:85 (AWS peering constraints), :132 (access list, propagation), :165 (Transit Gateway), :179 (security groups), :335 (anti-patterns)
- skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md:589 (access list commands), :678 (peering commands)
- skills/mongodb-atlas-expert/references/mongodb-atlas-terraform.md:375 (container CIDR locking), :405 (AWS, Azure, GCP peering), :356 (connection string outputs)
- skills/mongodb-operations-expert/references/mongodb-security-architecture.md:461 (peering layer), :511 (access list after private networking)
- skills/mongodb-atlas-expert/references/mongodb-atlas-multicloud.md:110 (Azure peering steps, container CIDR)
- skills/mongodb-atlas-expert/references/mongodb-atlas-azure.md:40 (peering vs Private Link), :1437 (anti-pattern)
- skills/mongodb-atlas-expert/references/mongodb-atlas-gcp.md:32 (GCP peering vs PSC), :1315 (anti-pattern); multicloud.md:237 (GCP VPC per project-region, default /18; Verify in the current MongoDB docs)
- skills/mongodb-atlas-expert/references/mongodb-atlas-iac.md:463, :1244 (AKO independent CRDs, alternating reconcile)
- skills/mongodb-atlas-expert/references/mongodb-atlas-platform-changelog.md:53 (Flex has no peering)
