---
name: atlas-private-link
title: Add an Atlas private endpoint (AWS PrivateLink, with Azure and GCP differences)
summary: Create the Atlas endpoint service, build the consumer-side endpoint in your cloud network, register it back with Atlas, and switch applications to the private-endpoint-aware connection string.
applies_to: [atlas]
sources:
  - skills/mongodb-atlas-expert/references/mongodb-aws-networking.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-terraform.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-azure.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-gcp.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-multicloud.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-platform-changelog.md
  - skills/mongodb-operations-expert/references/mongodb-security-architecture.md
---
# Add an Atlas private endpoint (AWS PrivateLink, with Azure and GCP differences)

## When to use
- Production traffic must reach a dedicated Atlas cluster without crossing the public internet.
- You need one-way connectivity (your network initiates, Atlas cannot call back), unlike peering.
- The cluster is sharded, or you need several VPCs/VNets (or a transit gateway / hub network) to reach Atlas without a peering per network.
- You want to remove `0.0.0.0/0` and other public entries from the project IP access list afterwards.

## Prerequisites (checklist)
- [ ] The cluster is a dedicated tier (M10 or larger). Flex does not support private endpoints; a policy that forbids public exposure needs a dedicated cluster.
- [ ] You know the Atlas project id (`<project-id>`) and the cloud region(s) of every cluster node. One endpoint is needed per Atlas region of the cluster.
- [ ] Atlas API keys or an Atlas CLI login with a role that can manage network access (the corpus lists "Project Network Access Admin" as a role that manages IP lists and private endpoints).
- [ ] Cloud-side permission to create an interface endpoint (AWS), a private endpoint (Azure) or a forwarding rule (GCP) in the target network.
- [ ] A subnet (AWS: one or more private subnets; Azure/GCP: a subnet in the same region as the cluster nodes) and a security group / NSG / firewall you control.
- [ ] You know how DNS is resolved in the consuming network (cloud default resolver, custom resolver, on-premises DNS).

## Steps

### AWS PrivateLink (main path)

1. Create the Atlas-side endpoint service for the region.
   ```bash
   atlas privateEndpoints aws create \
     --projectId <project-id> \
     --region us-east-1
   atlas privateEndpoints aws watch <endpoint-service-id> --projectId <project-id>
   ```
   Equivalent API call:
   ```
   POST /api/atlas/v2/groups/<project-id>/privateEndpoint/endpointService
   { "providerName": "AWS", "region": "us-east-1" }
   ```
   Expect: Atlas returns an endpoint service id and an AWS service name to target; `watch` returns once the service is ready.

2. Read the service name Atlas created.
   ```bash
   atlas privateEndpoints aws describe <endpoint-service-id> --projectId <project-id>
   ```
   Expect: output includes the endpoint service name (Terraform exposes it as `endpoint_service_name`) that your VPC endpoint must target.

3. Create the interface VPC endpoint in your VPC, targeting that service name, in the private subnets, with a security group that allows your application security groups to reach it.
   ```hcl
   resource "aws_vpc_endpoint" "atlas" {
     vpc_id             = var.vpc_id
     service_name       = mongodbatlas_privatelink_endpoint.pe.endpoint_service_name
     vpc_endpoint_type  = "Interface"
     subnet_ids         = var.private_subnet_ids
     security_group_ids = [aws_security_group.atlas_pe.id]
   }
   ```
   Expect: a `vpce-...` id and one network interface (ENI) per subnet in your VPC.

4. Open the security group. Allow inbound to the endpoint ENIs from the application security groups, and allow outbound from the application to the endpoint. The AWS corpus note lists 27015-27017. The Azure and GCP notes show that private-endpoint SRV connection strings use per-node high ports starting at 1024, so allow TCP 1024-65535 to the endpoint unless current docs say otherwise (see Pitfalls).
   ```bash
   aws ec2 describe-security-groups --group-ids <sg-id>
   ```
   Expect: inbound rules from the application security groups to the ports above.

5. Register the VPC endpoint with Atlas.
   ```bash
   atlas privateEndpoints aws interfaces create <endpoint-service-id> \
     --privateEndpointId <vpce-id> \
     --projectId <project-id>
   ```
   The corpus shows a second form with `--vpcId` and `--subnetIds`; the two sources disagree. Run `atlas privateEndpoints aws interfaces create --help` and use the flags it lists.
   Expect: the interface shows up under the endpoint service and moves to an available state (watch with `atlas privateEndpoints aws watch`).

6. Fetch the private-endpoint-aware connection string. In the UI it is under the cluster Connect dialog after choosing the private endpoint connection type. In Terraform it is the output `connection_strings[0].private_endpoint[*].connection_string`.
   ```bash
   terraform output connection_string_private_endpoint
   ```
   That output exists only if you define it from the cluster resource. Otherwise copy the string from the UI. Expect: a `mongodb+srv://` string whose host name differs from the standard `cluster0.xxxxx.mongodb.net` string (the Azure corpus example is `cluster0-pl-0.<id>.mongodb.net`).

7. Make sure DNS in the consuming network returns the endpoint's private IPs for the Atlas private hostnames (see "DNS and access list notes").
   ```bash
   nslookup -type=SRV _mongodb._tcp.<private-srv-host>
   nslookup <node-host-from-srv-answer>
   ```
   Expect: the SRV answer lists node hosts with ports; the A answers are private addresses from your subnet.

8. Switch the application to the private string and test with mongosh from a host inside the network.
   ```bash
   mongosh "<private-endpoint-srv-connection-string>" --username <db-user> \
     --eval 'db.runCommand({ ping: 1 })'
   ```
   Expect: `{ ok: 1 }`.

9. Repeat steps 1 to 8 for every Atlas region the cluster spans (see "Per-region and per-cluster").

### Azure Private Link differences
- Create: `atlas privateEndpoints azure create --region US_EAST_2 --projectId <project-id>`. Atlas creates a Private Link Service and returns a Resource ID and an Alias. Region spelling differs between corpus examples (`US_EAST_2` and `eastus2`); use what `atlas privateEndpoints azure create --help` accepts.
- In the Azure Portal: Private Link Center, Private Endpoints, Create, choose "Connect to an Azure resource by resource ID or alias", paste the Atlas alias, pick your subscription, VNet and subnet. The endpoint must be in the same Azure region as the cluster nodes.
- Link back: `atlas privateEndpoints azure interfaces create <endpoint-service-id> --privateEndpointId <azure-private-endpoint-resource-id> --privateEndpointIpAddress <private-ip> --projectId <project-id>`.
- Status path in the corpus: Atlas endpoint service `Creating -> Available`; your endpoint `Initiating -> Available`.
- NSG: for the `mongodb+srv://` private string allow TCP 1024-65535 outbound from the application subnet to the endpoint subnet, not only 27017. If NSG rules should apply to the endpoint subnet, enable network policies on it (`az network vnet subnet update --name <subnet> --resource-group <rg> --vnet-name <vnet> --private-endpoint-network-policies Enabled`, Azure CLI 2.53 or later).
- DNS: create a Private DNS Zone named for the cluster subdomain (for example `<cluster-id>.mongodb.net`) with A records (not CNAMEs) such as `pl-0-<region>` pointing to the endpoint NIC IP, and link the zone to every VNet that needs resolution. AWS uses CNAMEs; Azure uses A records.
- Hub-and-spoke: put the endpoint in the hub VNet and forward `mongodb.net` queries from spokes to a DNS resolver in the hub.

### GCP Private Service Connect differences
- Prefer the port-mapped design: one PSC endpoint (one IP, one forwarding rule) per Atlas region. Verify in the current MongoDB docs: the legacy design is said to need 50 IPs and 50 forwarding rules per region and to be deprecated on 2027-04-30; confirm both the counts and the date.
- Create the Atlas side with port mapping on:
  ```bash
  curl -4 -i --digest -u "<public-key>:<private-key>" --request POST \
    --header "Content-Type: application/json" \
    --header "Accept: application/vnd.atlas.2025-03-12+json" \
    --data '{"providerName": "GCP", "region": "CENTRAL_US", "portMappingEnabled": true}' \
    "https://cloud.mongodb.com/api/atlas/v2/groups/<project-id>/privateEndpoint/endpointService"
  ```
- Reserve an internal IP, then create the forwarding rule against the Atlas service attachment (`--target-service-attachment=<attachment from Atlas>`, `--load-balancing-scheme=""`). Add `--allow-psc-global-access` if clients in other GCP regions must reach it.
- Register the forwarding rule **name** (not its IP) with Atlas: `atlas privateEndpoints gcp interfaces create <endpoint-service-id> --endpointName <forwarding-rule-name> --gcpProjectId <gcp-project-id> --projectId <project-id>`. Run `atlas privateEndpoints gcp interfaces create --help` and use the flags it lists, since flag names can differ by CLI version. Expect "Available" after about 10 minutes.
- Firewall: allow egress TCP 1024-65535 to the PSC subnet range.
- Connection strings: port-mapped strings use the `psc` prefix (`cluster1-psc-0...`), legacy ones use `pl`.

## DNS and access list notes
- Atlas answers differently by source (split-horizon): public clients get public IPs, private-endpoint clients get the endpoint address, peered clients get private member IPs.
- The private SRV record resolves to node host names (for example `pl-0-<region>...mongodb.net`) on separate ports. Do not hardcode IPs.
- Custom resolvers that do not forward `*.mongodb.net` to the cloud resolver break resolution; on GKE add a `mongodb.net:53 { forward . /etc/resolv.conf }` stanza to CoreDNS.
- A public `mongodb.net` zone on a custom DNS server shadows the private zone (Azure note). Forward `*.mongodb.net` only to the resolver that knows the private zone.
- Access list: the corpus states project access lists apply unless private networking is used, and one Azure note says IP allow-listing of the endpoint source is optional with Private Link. Verify in the current MongoDB docs: whether your project still needs an access-list entry for private endpoint traffic. Remove `0.0.0.0/0` only after you prove private access works from every client network.

## Per-region and per-cluster
- Every Atlas region of a multi-region cluster needs its own private endpoint. A three-region cluster needs three. Missing one leaves those nodes unreachable.
- With Terraform, create one `mongodbatlas_privatelink_endpoint` per distinct region (`for_each = toset(local.atlas_regions)`).
- The endpoint service is created per project and region (the API call takes `groupId` and `region`). Verify in the current MongoDB docs: how many clusters in the same project and region share one endpoint service.
- Reaching Atlas from several VPCs: put the endpoint in one VPC and route through Transit Gateway, or share it across accounts with AWS Resource Access Manager. Atlas itself does not peer with Transit Gateway.
- Azure and GCP endpoints cannot span regions on the Atlas side; GCP can use Global Access on the consumer forwarding rule.

## Verify
```bash
atlas privateEndpoints aws list --projectId <project-id>
nslookup -type=SRV _mongodb._tcp.<private-srv-host>
mongosh "<private-endpoint-srv-connection-string>" --eval 'db.runCommand({ ping: 1 })'
```
Expect: the endpoint and its interface are available, SRV and A answers are private addresses, ping returns `ok: 1` from inside the network and the same string fails from outside it. Run the ping from every network that must connect (each VPC, each spoke, on-premises).

## Rollback / abort
1. Point applications back to the previous (public or peering) connection string before touching the endpoint. Keep the old access list entries until this is done.
2. Delete the Atlas interface registration, then the cloud-side endpoint, then the Atlas endpoint service: `atlas privateEndpoints aws delete <endpoint-service-id> --projectId <project-id> --force`. Confirm no cluster in that region still depends on it.
3. Remove private DNS zones or records you added so names do not resolve to dead IPs.
4. GCP stuck in "Waiting for User" for more than 30 minutes: delete the Atlas endpoint and the forwarding rule and recreate both.

## Pitfalls
- Restricting to port 27017 (or 27015-27017) when the private SRV string advertises ports from 1024 up: DNS resolves, then connections time out.
- Registering the wrong identifier: GCP needs the forwarding rule name, not its IP; AWS needs the `vpce-` id.
- One endpoint for a multi-region cluster. Each region needs its own.
- Region naming: Atlas names (`US_EAST_2`, `CENTRAL_US`) are not cloud names (`eastus2`, `us-central1`). Mixing them causes silent failures.
- Forgetting to link the Azure private DNS zone to every VNet, especially new spokes and the AKS node VNet.
- Recreating a GCP endpoint changes its IP; hand-made A records go stale. Prefer Atlas-provided private hostnames.
- Using Flex for a no-public-exposure requirement. Flex has no private endpoint support.
- Removing the public access list before verifying every client network.
- Using legacy GCP PSC for new work.
- The AWS corpus note lists ports 27015-27017 while Azure/GCP notes list 1024-65535. Verify in the current MongoDB docs: the exact AWS PrivateLink port range for your cluster type.

## Sources
- skills/mongodb-atlas-expert/references/mongodb-aws-networking.md:98 (PrivateLink advantages, Terraform, Admin API), :132 (access list), :142 (DNS/SRV, split-horizon), :165 (Transit Gateway, RAM), :179 (security groups)
- skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md:624 (aws/azure/gcp privateEndpoints commands)
- skills/mongodb-atlas-expert/references/mongodb-atlas-terraform.md:361 (private endpoint connection string output), :466 (AWS three-resource pattern)
- skills/mongodb-operations-expert/references/mongodb-security-architecture.md:281 (Project Network Access Admin role), :480 (setup flow, `interfaces create --privateEndpointId`), :511 (disabling public access)
- skills/mongodb-atlas-expert/references/mongodb-atlas-multicloud.md:122 (Azure Private Link steps and CLI), :248 (GCP PSC), :672 (per-region requirement)
- skills/mongodb-atlas-expert/references/mongodb-atlas-azure.md:52 (Azure DNS, A records), :84 (NSG ports), :133 (hub-and-spoke), :1161 (DNS troubleshooting)
- skills/mongodb-atlas-expert/references/mongodb-atlas-gcp.md:49 (legacy vs port-mapped), :98 (setup), :145 (DNS), :179 (Global Access), :1109 (stuck state), :1301 (anti-patterns)
- skills/mongodb-atlas-expert/references/mongodb-atlas-platform-changelog.md:53 (Flex has no private endpoints)
