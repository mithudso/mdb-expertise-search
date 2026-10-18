<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-azure` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

# MongoDB Atlas on Azure — Networking, Identity & Integration

Deep reference for MongoDB Atlas on Microsoft Azure covering Private Link and DNS architecture, Entra ID OIDC/LDAP identity federation and Managed Identity for Atlas authentication, Azure Key Vault BYOK encryption with key rotation and failsafe behavior, Atlas Kubernetes Operator on AKS with Workload Identity, Azure service integrations (OpenAI, Event Hub, Functions, App Service, Container Apps, Synapse), MACC and Azure Native MongoDB billing, Azure Monitor / Log Analytics / Sentinel observability, the complete Azure region map, Terraform and Bicep IaC patterns, and a full Azure-specific troubleshooting playbook. This skill fills the gap beyond [[mongodb-atlas-multicloud]], which covers the basics of Azure PrivateLink and multi-cloud replica sets.

## When to use this skill

- When configuring Atlas Private Link on Azure including private DNS zones, NSG rules, hub-and-spoke topology, Azure Private DNS Resolver, or ExpressRoute integration
- When setting up Entra ID OIDC/LDAP federation, Managed Identity, or Workload Identity Federation for Atlas authentication
- When implementing Azure Key Vault as Atlas Encryption at Rest (BYOK), including secretless authentication, key rotation, or KV Managed HSM
- When deploying Atlas Kubernetes Operator (AKO) on AKS with Workload Identity or configuring KEDA / Dapr sidecar patterns
- When integrating Atlas with Azure OpenAI embeddings / Vector Search, Event Hub Stream Processing, Azure Functions, or App Service
- When evaluating MACC eligibility for Atlas spend, comparing ANM vs standard Atlas, or managing Azure Marketplace billing
- When setting up Atlas log export to Log Analytics, Microsoft Sentinel, Application Insights, or OpenTelemetry
- When designing Azure compliance architecture (Defender for Cloud, Azure Policy, PIM, FedRAMP/HIPAA/PCI) for Atlas deployments
- When writing Terraform with the mongodbatlas + azurerm providers or Bicep templates for Atlas private endpoint infrastructure
- When troubleshooting Private Link DNS failures, NSG blocking, Entra ID token claim errors, or Key Vault access denials

## When NOT to use this skill

- For AWS-specific Atlas networking (VPC peering, AWS PrivateLink, Transit Gateway, AWS KMS) — use `mongodb-aws-networking`
- For GCP-specific Atlas networking or Private Service Connect — use `mongodb-atlas-multicloud` or `mongodb-atlas-gcp`
- For pure Terraform IaC patterns without Azure-specific context — use `mongodb-atlas-terraform`
- For Atlas general administration, scaling, or monitoring not tied to Azure — use `mongodb-atlas-expert`
- For multi-cloud replica set topology decisions — use `mongodb-atlas-multicloud`

---

## 1. Azure Networking with Atlas

### 1.1 VNet Peering vs Private Endpoint

VNet peering is a legacy connectivity option that works at the network level; MongoDB Atlas still supports it but recommends Private Endpoints (Azure Private Link) for new deployments. Key differences:

| Feature | VNet Peering | Private Endpoint (Private Link) |
|---|---|---|
| Traffic path | Direct VNet-to-VNet | NIC in your VNet → Azure Private Link Service → Atlas load balancer |
| DNS | No extra zone needed; cluster FQDN resolves to peered VNet IP | Requires Private DNS Zone `privatelink.mongodb.net` (or sub-zone) |
| Cross-region | Requires global VNet peering | Supported in Atlas-supported regions |
| Hub-and-spoke | Complex — peer every spoke | Private endpoint in hub, accessed by spokes via VNet peering |
| Recommended | Legacy | Yes (recommended since 2022) |

### 1.2 Private Link Deep Dive

**How it works:**
1. You request a Private Endpoint in Atlas UI/API, specifying your Azure subscription, region, and VNet/subnet.
2. Atlas creates an Azure Private Link Service backed by a Standard Load Balancer in Atlas's VNet.
3. Azure creates a Network Interface Card (NIC) in your subnet with a private IP.
4. Atlas endpoint service status moves: `Creating → Available`.
5. Your endpoint status moves: `Initiating → Available`.

**DNS zones — two options:**

Option A — Zone per cluster subdomain (recommended):
```
Private DNS Zone name: <cluster-id>.mongodb.net   (e.g., uzgh6.mongodb.net)
A record: pl-0-eastus2   →  10.x.x.4
A record: pl-1-eastus2   →  10.x.x.5
```

Option B — Umbrella mongodb.net zone:
```
Private DNS Zone name: mongodb.net
A records for each cluster endpoint pl-0-eastus2.uzgh6.mongodb.net → 10.x.x.4
```

The private endpoint-aware connection string uses the SRV subdomain:
```
mongodb+srv://cluster0-pl-0.uzgh6.mongodb.net
```
The SRV record resolves to `pl-0-eastus2.uzgh6.mongodb.net`, which is an **A record** (not CNAME) pointing to the NIC's private IP. This differs from AWS which uses CNAMEs.

**AMPLS co-existence:** Azure Monitor Private Link Scope (AMPLS) also creates private DNS zones for `privatelink.monitor.azure.com` and related hostnames. Avoid accidentally allowing Atlas hostnames to resolve through the AMPLS DNS zone. Keep Atlas private DNS zones scoped only to the VNets that need Atlas connectivity.

### 1.3 NSG Rules for Atlas

NSGs operate at NIC level and subnet level. For Atlas Private Link:

**Outbound rules — choose based on connection string type:**

*Standard connection string (`mongodb://host:27017`):*
```
Priority: 100  Direction: Outbound  Protocol: TCP
Source: application subnet prefix
Destination: private endpoint subnet range
Port: 27017
Action: Allow
```

*Private-endpoint-aware SRV connection string (`mongodb+srv://...`) — required for Atlas private endpoints:*
```
Priority: 100  Direction: Outbound  Protocol: TCP
Source: application subnet prefix
Destination: private endpoint subnet range
Port: 1024-65535
Action: Allow
```

**Why 1024–65535 for SRV:** Atlas private endpoint connection strings resolve to per-node high ports (1024, 1025, 1026, etc.) via SRV records. Restricting to port 27017 alone blocks these connections. The SRV-aware range is required for `mongodb+srv://` connection strings, which are the default for Atlas.

**Private endpoint NIC policies:** By default, Azure disables NSG enforcement on private endpoint NICs. To apply NSG rules to the private endpoint subnet, explicitly enable the policy:
```bash
# Azure CLI ≥ 2.53 (recommended — uses explicit flag name)
az network vnet subnet update \
  --name snet-private-endpoints \
  --resource-group myRG \
  --vnet-name myVNet \
  --private-endpoint-network-policies Enabled

# Azure CLI < 2.53 (legacy flag — counterintuitive: "false" = enable policies)
# az network vnet subnet update ... --disable-private-endpoint-network-policies false
```

**Flow logs:** Enable NSG flow logs to diagnose blocked Atlas connections:
```bash
az network watcher flow-log create \
  --name atlas-nsg-flow \
  --nsg myAtlasSubnetNSG \
  --resource-group myRG \
  --storage-account myStorageAccount \
  --enabled true
```

### 1.4 Hub-and-Spoke with Atlas

Azure hub-and-spoke places the private endpoint in the **hub VNet**. Spoke VNets access Atlas through VNet peering to the hub. DNS forwarding is the key challenge.

**Architecture:**
```
Spoke A VNet ─── VNet Peering ─── Hub VNet
Spoke B VNet ─── VNet Peering ─┤    ├── Private Endpoint (Atlas NIC)
                                     ├── Azure Private DNS Resolver (inbound endpoint)
                                     └── Private DNS Zone: uzgh6.mongodb.net
```

**Azure Private DNS Resolver (replaces BIND forwarder):**

The legacy pattern used a BIND server or Azure DNS Forwarder VM to forward `.mongodb.net` queries from spokes to Azure DNS (168.63.129.16). Azure Private DNS Resolver provides a managed, HA alternative:

```bash
# Create resolver in hub VNet
az dns-resolver create \
  --name atlas-dns-resolver \
  --resource-group myRG \
  --location eastus \
  --id "/subscriptions/.../virtualNetworks/hubVnet"

# Create inbound endpoint (receives DNS from spokes)
az dns-resolver inbound-endpoint create \
  --dns-resolver-name atlas-dns-resolver \
  --endpoint-name inbound-ep \
  --resource-group myRG \
  --ip-configurations "[{privateIpAllocationMethod:Dynamic,id:'/subscriptions/.../subnets/snet-dns-resolver'}]"
```

Spoke VNets configure a DNS forwarding ruleset pointing `mongodb.net` queries to the resolver's inbound endpoint IP.

**Azure Firewall in hub:** If Azure Firewall sits between spokes and the hub, add a network rule allowing TCP 1024-65535 from spoke address spaces to the Atlas private endpoint IP. Application rules will not decode MongoDB wire protocol.

### 1.5 ExpressRoute + Atlas (On-Premises)

ExpressRoute connects on-premises networks to Azure via a dedicated circuit. For Atlas access from on-premises:

1. Route on-premises traffic into Azure hub VNet via ExpressRoute.
2. Place Atlas private endpoint in hub VNet (same as hub-and-spoke above).
3. DNS forwarding: Configure on-premises DNS server to forward `*.mongodb.net` to Azure Private DNS Resolver inbound endpoint IP (which is reachable via ExpressRoute).
4. Ensure ExpressRoute circuit advertises the private endpoint subnet to on-premises routers.

**Latency note:** ExpressRoute adds ~5-15ms RTT vs direct cloud connectivity. For write-heavy Atlas workloads, co-locate primary node in the Azure region closest to the ExpressRoute circuit endpoint.

---

## 2. Azure Active Directory (Entra ID) + Atlas

### 2.1 Workforce Identity Federation (OIDC) — GA June 2024

Workforce Identity Federation lets human users SSO into Atlas database access using their Entra ID credentials. No separate MongoDB passwords.

**Setup steps:**

1. **Register an Entra ID application** for workforce access:
```bash
az ad app create --display-name "MongoDB Atlas Workforce"
# Note the appId (client ID)
```

2. **Configure in Atlas** (Organization → Security → Workforce Identity Provider):
   - Provider: Microsoft
   - Issuer URI: `https://login.microsoftonline.com/<tenant-id>/v2.0`
   - Client ID: `<appId from step 1>`
   - Requested Scopes: `openid profile email offline_access`
   - User claim: `preferred_username` or `email`
   - Group claim: `groups` (requires configuring group claims in the Entra ID app manifest)

3. **Group-to-role mapping:** In Atlas, map Entra ID group Object IDs to Atlas roles:
   - Atlas org role or project role per group
   - Requires the `groups` claim in the token (configure via Entra ID app registration → Token configuration → Add groups claim → Security groups)

4. **Conditional Access:** Entra ID Conditional Access policies apply at the Entra ID app level. You can enforce MFA, compliant device, or specific IP ranges for Atlas database access. Atlas respects whatever tokens Entra ID issues — if Conditional Access blocks a token, Atlas will reject the user.

### 2.2 Workload Identity Federation (OAuth 2.0) — GA June 2024

Workload Identity Federation allows Azure Managed Identities and Service Principals to authenticate to Atlas **without passwords**, using short-lived OAuth 2.0 tokens.

**Register a separate Entra ID app for workload access** (separate from workforce):
```bash
az ad app create --display-name "MongoDB Atlas Workload"
# Note appId
az ad sp create --id <appId>
```

**Configure in Atlas** (Organization → Security → Workload Identity Provider):
- Identity Provider: Azure
- Issuer URI: `https://sts.windows.net/<tenant-id>/`
- Audience: The appId of your workload Entra ID app

**Create Atlas database user** mapped to the Managed Identity or Service Principal:
- Auth type: OAuth 2.0 Access Token
- Subject: Object ID of the Managed Identity (for system-assigned) or client ID (for user-assigned)

**Application connection string:**
```
mongodb+srv://cluster.mongodb.net/?authMechanism=MONGODB-OIDC&authMechanismProperties=ENVIRONMENT:azure,TOKEN_RESOURCE:<audience>
```
For AKS with Workload Identity, omit `TOKEN_RESOURCE` — the driver reads the token from the OIDC file projected into the pod.

### 2.3 AKS Workload Identity Setup

```bash
# 1. Create AKS cluster with OIDC issuer and workload identity enabled
az aks create \
  --resource-group myRG \
  --name myAKSCluster \
  --enable-oidc-issuer \
  --enable-workload-identity

# 2. Get OIDC issuer URL
OIDC_ISSUER=$(az aks show --name myAKSCluster --resource-group myRG --query "oidcIssuerProfile.issuerUrl" -o tsv)

# 3. Create a User-Assigned Managed Identity
az identity create --name atlas-workload-id --resource-group myRG
CLIENT_ID=$(az identity show --name atlas-workload-id --resource-group myRG --query clientId -o tsv)
OBJECT_ID=$(az identity show --name atlas-workload-id --resource-group myRG --query principalId -o tsv)

# 4. Create Kubernetes service account
TENANT_ID=$(az account show --query tenantId -o tsv)
kubectl create serviceaccount atlas-sa --namespace myapp
kubectl annotate serviceaccount atlas-sa \
  azure.workload.identity/client-id=$CLIENT_ID \
  azure.workload.identity/tenant-id=$TENANT_ID \
  --namespace myapp

# 5. Create federated credential
az identity federated-credential create \
  --name atlas-federated-cred \
  --identity-name atlas-workload-id \
  --resource-group myRG \
  --issuer $OIDC_ISSUER \
  --subject "system:serviceaccount:myapp:atlas-sa" \
  --audience "api://AzureADTokenExchange"
```

In the pod manifest, add the label `azure.workload.identity/use: "true"` to enable the webhook injection.

### 2.4 Entra ID DS (LDAP over TLS)

Azure Active Directory Domain Services (AADDS) provides a managed LDAP endpoint. Atlas supports LDAP authentication over TLS:

- **LDAP host:** `ldaps://<domain>.aadds.azure.com:636`
- **Bind DN:** `CN=<service-account>,OU=AADDS Users,DC=example,DC=com`
- **CA cert:** Download from AADDS → Secure LDAP → Certificate (DER format, convert to PEM)
- **Limitation:** AADDS does not support the `memberOf` overlay by default; use Entra ID OIDC with group claims instead for group-based role mapping

### 2.5 SAML Federation

Atlas supports SAML 2.0 for Atlas UI/API access (not database-level auth). Configure Entra ID as the SAML IdP:
- Entity ID: `https://www.okta.com/saml2/service-provider/<atlasOrgId>` (Atlas uses Okta-formatted entity IDs)
- ACS URL: Provided in Atlas Organization → Federation Management App
- User attribute: `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress`

**SAML vs OIDC path for Atlas:**
- SAML: Atlas UI/API console access (federation via Atlas Federation Management)
- OIDC workforce: Database-level access for human users
- OIDC workload: Database-level access for applications/services

---

## 3. Azure Key Vault and Encryption at Rest

### 3.1 Architecture

Atlas uses a two-tier encryption scheme:
- **Data Encryption Key (DEK):** Encrypts the actual data files. Managed by Atlas internally.
- **Key Encryption Key (KEK):** Wraps the DEK. Stored in Azure Key Vault (AKV). Customer owns and controls it.

Atlas uses RSA-2048 or RSA-4096 keys with operations: `get`, `wrapKey`, `unwrapKey` (or equivalently `encrypt`/`decrypt`).

### 3.2 Secretless Authentication (Recommended)

The modern pattern eliminates long-lived client secrets. Atlas uses its own Azure Service Principal (`atlasAzureAppId: 9efedfcc-2eca-4b27-a613-0cad1e114cb7`) to authenticate to AKV via short-lived OAuth 2.0 tokens.

**Complete setup:**

```bash
# 1. Get tenant ID
TENANT_ID=$(az account show --query tenantId -o tsv)

# 2. Create Atlas service principal in your tenant
az ad sp create --id 9efedfcc-2eca-4b27-a613-0cad1e114cb7
SP_OBJECT_ID=$(az ad sp list --filter "appId eq '9efedfcc-2eca-4b27-a613-0cad1e114cb7'" --query "[0].id" -o tsv)

# 3. Register with Atlas Cloud Provider Access API
# POST /api/atlas/v2/groups/{groupId}/cloudProviderAccess
# Body: { "providerName": "AZURE", "tenantId": "$TENANT_ID",
#         "servicePrincipalId": "$SP_OBJECT_ID",
#         "atlasAzureAppId": "9efedfcc-2eca-4b27-a613-0cad1e114cb7" }
# Response includes a roleId

# 4. Grant Key Vault permissions (RBAC model — recommended)
az role assignment create \
  --assignee-object-id "$SP_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Key Vault Crypto User" \
  --scope "/subscriptions/$SUB_ID/resourceGroups/$RG/providers/Microsoft.KeyVault/vaults/$KV_NAME"

az role assignment create \
  --assignee-object-id "$SP_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Reader" \
  --scope "/subscriptions/$SUB_ID/resourceGroups/$RG/providers/Microsoft.KeyVault/vaults/$KV_NAME"

# 5. Configure EAR in Atlas
# PATCH /api/atlas/v2/groups/{groupId}/encryptionAtRest
# Body: { "azureKeyVault": { "enabled": true, "roleId": "<roleId>",
#         "subscriptionID": "...", "resourceGroupName": "...",
#         "keyVaultName": "...",
#         "keyIdentifier": "https://<vault>.vault.azure.net/keys/<key>",
#         "azureEnvironment": "AZURE" } }
```

**Key identifier without version:** Omitting the version suffix (e.g., `https://myvault.vault.azure.net/keys/atlaskey`) enables Atlas to automatically use the latest key version after rotation — no Atlas configuration update needed.

### 3.3 Access Policies vs RBAC

| Model | Set in | Granularity | Recommended |
|---|---|---|---|
| Key Vault Access Policies (legacy) | Key Vault → Access policies blade | Per-principal, per-operation | No |
| Azure RBAC | IAM on Key Vault resource | Role assignment; supports Entra ID PIM | Yes |

With RBAC, the **Key Vault Crypto User** built-in role grants: `get`, `encrypt`, `decrypt`, `wrapKey`, `unwrapKey`, `sign`, `verify`. This is slightly broader than strictly needed (Atlas only needs `get`, `wrapKey`, `unwrapKey`) but is the standard managed role.

### 3.4 Key Rotation Workflow

**Automated rotation (recommended):** Configure the AKV rotation policy so new key versions are created automatically, then use a versionless key identifier in Atlas so no Atlas config change is required on rotation.

```bash
# Set AKV rotation policy (creates new version every 90 days, expires after 180)
az keyvault key rotation-policy update \
  --vault-name $KV_NAME --name atlaskey \
  --value '{
    "lifetimeActions": [{"trigger": {"timeAfterCreate": "P90D"}, "action": {"type": "Rotate"}}],
    "attributes": {"expiryTime": "P180D"}
  }'
```

**Manual rotation flow:**
1. Create a new key version in AKV (or wait for the rotation policy to fire).
2. If Atlas `keyIdentifier` includes a version: update the Atlas EAR config with the new version URI via `PATCH /api/atlas/v2/groups/{groupId}/encryptionAtRest`.
3. If Atlas `keyIdentifier` is versionless (no trailing `/<version>`): no Atlas update needed — Atlas resolves to the latest version on the next key access automatically.
4. Atlas re-wraps the DEK with the new key version on the next periodic validation cycle.
5. Retain old key versions in AKV for at least the full backup retention period before disabling them — restoring an old snapshot requires the key version that encrypted it.

**Key Vault Managed HSM:** Premium tier option providing FIPS 140-2 Level 3 validated hardware. Configuration is identical to standard Key Vault from Atlas's perspective — replace `vault.azure.net` with `managedhsm.azure.net` in the key identifier. Higher cost; recommended for regulated industries (PCI DSS, HIPAA, FedRAMP High).

**Azure Dedicated HSM:** Azure also offers Luna Network HSMs (Azure Dedicated HSM). These are customer-managed physical HSMs. Atlas does not natively integrate with Dedicated HSM — you would need to front it with a Key Vault or similar wrapper. Use Key Vault Managed HSM instead for Atlas BYOK.

### 3.5 Failsafe Behavior on Key Vault Outage

- Atlas **does not provide automatic KMS failover** across regions.
- If AKV becomes inaccessible, Atlas logs a warning but the running cluster continues operating (the DEK is cached in memory).
- On the next `mongod` restart (planned or unplanned), if Atlas cannot reach AKV to unwrap the DEK, **mongod refuses to start** and the cluster shuts down.
- Atlas sends email alerts when KMS access fails.
- **Recovery:** Restore AKV access (fix firewall/private endpoint/RBAC), then restart the cluster from Atlas UI.
- **Multi-region clusters:** Create a private endpoint from AKV to **each** Atlas region where nodes are deployed. If any region's nodes cannot reach AKV, those nodes will fail to restart after a crash.

### 3.6 Key Vault Private Endpoint for Atlas EAR

Route all Atlas→AKV traffic over Azure's private backbone by configuring a Private Link connection from Atlas to your Key Vault. This is distinct from the cluster private endpoint — it is a separate endpoint provisioned by Atlas on your behalf.

**Step 1 — Request the private endpoint via Atlas Admin API:**
```bash
curl -u "$ATLAS_PUBLIC_KEY:$ATLAS_PRIVATE_KEY" --digest \
  -X POST \
  "https://cloud.mongodb.com/api/atlas/v2/groups/$GROUP_ID/encryptionAtRest/AZURE/privateEndpoints" \
  -H "Content-Type: application/json" \
  -d '{
    "regionName": "US_EAST_2"
  }'
# Response includes "privateEndpointConnectionName" and status "INITIATING"
```

**Step 2 — Approve the connection in Azure:**
```bash
# List pending connections on your Key Vault
az keyvault private-endpoint-connection list \
  --vault-name $KV_NAME --resource-group $RG

# Approve
az keyvault private-endpoint-connection approve \
  --vault-name $KV_NAME \
  --resource-group $RG \
  --name <privateEndpointConnectionName>
```

**Step 3 — Verify status via Atlas API:**
```bash
curl -u "$ATLAS_PUBLIC_KEY:$ATLAS_PRIVATE_KEY" --digest \
  "https://cloud.mongodb.com/api/atlas/v2/groups/$GROUP_ID/encryptionAtRest/AZURE/privateEndpoints"
# Status should transition: INITIATING → PENDING_ACCEPTANCE → ACTIVE
```

**Limitations:**
- Once a private endpoint is active for a Key Vault, you cannot change `keyVaultName`, `subscriptionID`, or `resourceGroupName` without first deleting all private endpoint connections.
- For multi-region clusters, repeat Steps 1–2 for each Atlas-deployed region.
- Key Vault firewall must not block the Atlas private endpoint subnet (set `defaultAction: Deny` and add the Atlas-managed private endpoint to the allowed list).

---

## 4. Azure Native Service Integrations

### 4.1 AKS + Atlas Kubernetes Operator (AKO)

AKO lets you manage Atlas resources (clusters, database users, projects) as Kubernetes CRDs.

**Step 1 — Create the Atlas API key Secret:**
```bash
# AKO reads Atlas credentials from a Kubernetes Secret in its namespace
kubectl create secret generic mongodb-atlas-operator-api-key \
  --namespace mongodb-atlas-system \
  --from-literal="orgId=<atlas-org-id>" \
  --from-literal="publicApiKey=<atlas-public-key>" \
  --from-literal="privateApiKey=<atlas-private-key>"
```

**Step 2 — Install AKO via Helm:**
```bash
helm repo add mongodb https://mongodb.github.io/helm-charts
helm install mongodb-atlas-operator mongodb/mongodb-atlas-operator \
  --namespace mongodb-atlas-system \
  --create-namespace \
  --set-string atlas.orgId=<org-id>
```

**Namespace scoping:** By default AKO watches all namespaces. For multi-tenant clusters, restrict to specific namespaces:
```bash
helm install mongodb-atlas-operator mongodb/mongodb-atlas-operator \
  --namespace mongodb-atlas-system \
  --set watchedNamespaces="{app-ns-1,app-ns-2}"
```

**Step 3 — AtlasProject CRD referencing the secret:**
```yaml
apiVersion: atlas.mongodb.com/v1
kind: AtlasProject
metadata:
  name: my-project
  namespace: app-ns-1
spec:
  name: "My Project"
  connectionSecretRef:
    name: mongodb-atlas-operator-api-key
    namespace: mongodb-atlas-system
  encryptionAtRest:
    enabled: true
    azure:
      enabled: true
      subscriptionID: "<sub>"
      resourceGroupName: "<rg>"
      keyVaultName: "<kv>"
      keyIdentifier: "https://<kv>.vault.azure.net/keys/<key>"
      # roleId from Cloud Provider Access secretless setup (§3.2)
      roleId: "<atlas-managed-role-id>"
```

The AKO pod's service account should have Workload Identity assigned so it can access Key Vault and call the Atlas Admin API without storing long-lived credentials in the Secret.

### 4.2 Azure Functions + Atlas

**Connection pooling (critical for serverless):**

Azure Functions runs multiple isolated instances; each instance must create its own MongoClient. Share the client across invocations within one instance using a module-level (non-async) singleton:

```javascript
// Node.js Azure Function
const { MongoClient } = require('mongodb');
let client;

async function getClient() {
  if (!client) {
    client = new MongoClient(process.env.ATLAS_URI, {
      maxPoolSize: 5,        // Low pool — Functions scales horizontally
      serverSelectionTimeoutMS: 5000,
      socketTimeoutMS: 30000,
    });
    await client.connect();
  }
  return client;
}

module.exports = async function (context, req) {
  const db = (await getClient()).db('mydb');
  // ...
};
```

**Consumption plan caveat:** Cold starts bring up a new process and create a new connection. Under high burst load, connection count spikes. Use M10+ clusters and set `maxPoolSize` low (3-5 per Function instance). Consider using Atlas with connection pooling middleware (Prisma Accelerate or similar) for extreme serverless scenarios.

**Durable Functions:** For long-running orchestrations that poll Atlas change streams, use a Durable Function with an activity function. Keep the MongoClient in the activity function, not the orchestrator (orchestrators are replayed and must be deterministic/stateless).

### 4.3 Azure Event Hub + Atlas Stream Processing

Atlas Stream Processing (ASP) supports Azure Event Hubs via the Kafka-compatible endpoint (GA on Azure as of 2024).

**Supported Azure regions for ASP (at GA):** eastus, eastus2, westus, westeurope (expanding).

**Event Hub connection string for ASP:**
```
kafka://<namespace>.servicebus.windows.net:9093
SASL mechanism: PLAIN
Username: $ConnectionString
Password: <Event Hub Shared Access connection string>
```

**Create connection in Atlas:**
```bash
atlas streams connections create \
  --instance myStreamInstance \
  --type Kafka \
  --config event-hub-conn.json
```

Where `event-hub-conn.json`:
```json
{
  "name": "azure-event-hub",
  "type": "Kafka",
  "kafka": {
    "bootstrapServers": "<namespace>.servicebus.windows.net:9093",
    "security": {
      "protocol": "SASL_SSL",
      "mechanism": "PLAIN",
      "username": "$ConnectionString",
      "password": "<connection-string>"
    }
  }
}
```

**Consumer group exhaustion:** Event Hub Standard tier supports 20 consumer groups per hub; Premium supports unlimited. ASP creates one consumer group per stream processor. Monitor consumer group count; upgrade to Premium if you have many pipelines reading the same hub.

**Schema Registry:** Use Azure Schema Registry (part of Event Hubs namespace, Premium/Standard) or Confluent Schema Registry. ASP supports Confluent-compatible schema registry via the connection registry.

**Private Link for ASP→Event Hub:** Configure Private Link endpoint in ASP connection registry to route Event Hub traffic over Azure backbone instead of public internet.

### 4.4 Azure Service Bus Integration

Atlas Triggers → Service Bus is a common pattern for decoupled event-driven architectures.

**Atlas Trigger → Service Bus via Atlas Function:**
```javascript
// Atlas Function (Node.js)
const { ServiceBusClient } = require("@azure/service-bus");

exports = async function(changeEvent) {
  const sbClient = new ServiceBusClient(context.values.get("SERVICE_BUS_CONN_STR"));
  const sender = sbClient.createSender("atlas-events");
  await sender.sendMessages({ body: changeEvent });
  await sender.close();
  await sbClient.close();
};
```

**Dead-letter handling:** Service Bus automatically moves messages that exceed `maxDeliveryCount` to the dead-letter queue (`<queue>/$DeadLetterQueue`). Set up an Alert Rule on `DeadLetteredMessages` metric and route to a Logic App that writes failures back to a MongoDB `dead_letter_log` collection.

### 4.5 Azure App Service + Atlas

**Managed Identity authentication:**
1. Enable system-assigned Managed Identity on App Service.
2. Register the Managed Identity as a Workload Identity provider in Atlas (see §2.2).
3. Connection string uses OIDC: `mongodb+srv://...?authMechanism=MONGODB-OIDC&authMechanismProperties=ENVIRONMENT:azure`

**Slot deployment pattern:**
- Store Atlas URI in App Service → Configuration → Application settings.
- Use slot-specific settings (not sticky) for the connection string so swaps don't carry production Atlas credentials into staging.
- **Slot swap race condition:** During a swap, new instances start with the swapped connection string before old instances drain. Use Atlas connection string with `waitQueueTimeoutMS` and `serverSelectionTimeoutMS` to handle brief disconnects.

### 4.6 Azure Container Apps + Atlas

**KEDA ScaledObject for Atlas change stream lag:**

Custom KEDA scaler using Atlas metrics API to scale Container Apps based on Atlas oplog lag or queue depth (requires a custom external scaler or the Atlas webhook → KEDA HTTP scaler pattern).

**Dapr sidecar:** Container Apps supports Dapr. Use the MongoDB state store component with your Atlas URI for distributed state:
```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: atlas-statestore
spec:
  type: state.mongodb
  version: v1
  metadata:
  - name: host
    value: "mongodb+srv://cluster.mongodb.net"
  - name: username
    secretKeyRef:
      name: atlas-secret
      key: username
```

### 4.7 Azure Synapse Analytics + Atlas

**Federated query via Atlas Data Federation:**
Atlas Data Federation creates a virtual data catalog over Atlas clusters and cloud storage. Synapse can query via ODBC/JDBC using Atlas SQL Interface:

1. Enable Atlas Data Federation on your project.
2. Create a federated database instance pointing to Atlas cluster.
3. Use Atlas SQL: `jdbc:mongodb://atlas-sql-<id>.mongodb.net:27017/<db>?ssl=true`
4. In Synapse Studio, create a linked service with the ODBC driver.

**Direct Synapse → Atlas via Spark connector:**
```python
# Azure Synapse Spark pool
df = spark.read \
  .format("mongodb") \
  .option("connection.uri", "mongodb+srv://...") \
  .option("database", "mydb") \
  .option("collection", "mycoll") \
  .load()
```

### 4.8 Azure OpenAI + Atlas Vector Search

This is a flagship integration pattern as of 2024-2025 (highlighted at Microsoft Ignite 2025).

**Embedding pipeline architecture:**
```
Documents → Azure OpenAI Embeddings API (text-embedding-3-large)
         → MongoDB Atlas collection with vector field
         → Atlas Vector Search index (knnVector type)
         
Query → Azure OpenAI Embeddings API
      → Atlas $vectorSearch aggregation stage
      → Top-K results → Azure OpenAI Chat API (RAG)
```

**Atlas Vector Search index definition:**
```json
{
  "fields": [{
    "type": "vector",
    "path": "embedding",
    "numDimensions": 3072,
    "similarity": "cosine"
  }]
}
```

**Python example (Azure OpenAI + Atlas):**
```python
from openai import AzureOpenAI
from pymongo import MongoClient

oai_client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_KEY"],
    api_version="2024-08-01"
)

def get_embedding(text):
    return oai_client.embeddings.create(
        input=text, model="text-embedding-3-large"
    ).data[0].embedding

atlas_client = MongoClient(os.environ["ATLAS_URI"])
coll = atlas_client["mydb"]["docs"]

# Vector search
results = coll.aggregate([{
    "$vectorSearch": {
        "index": "vector_index",
        "path": "embedding",
        "queryVector": get_embedding(user_query),
        "numCandidates": 150,
        "limit": 5
    }
}])
```

**Azure OpenAI "on your data" integration:** Azure OpenAI Service has a native data connector for MongoDB Atlas (API version 2024-08-01+). Configured via Azure AI Foundry — uses Atlas Vector Search as the retrieval backend for Azure OpenAI's built-in RAG.

**Voyage AI embeddings:** MongoDB acquired Voyage AI in 2025. Atlas Vector Search supports automated Voyage embeddings (voyage-3, voyage-3-large) inline in the index definition, removing the need for a separate embedding pipeline for new collections.

---

## 5. MACC and Azure Marketplace Billing

### 5.1 MACC Eligibility

Microsoft Azure Consumption Commitment (MACC) is a multi-year pre-commitment to Azure spend in exchange for discounts. Third-party SaaS purchased through Azure Marketplace counts toward MACC drawdown.

**MongoDB Atlas counts toward MACC when:**
- Purchased through Azure Marketplace (Pay-As-You-Go or committed-use listing)
- Billed directly on Azure invoice

**What counts:**
- Atlas cluster compute and storage
- Atlas Advanced Security add-ons
- Atlas Dedicated Search Nodes
- Atlas Stream Processing units

**What may not count:**
- Atlas Global Writes or multi-cloud egress (depends on listing SKU)
- On-demand Atlas support plans purchased separately
- Verify SKU eligibility in the Azure Marketplace listing or with your Microsoft account team

**Tracking in Azure Portal:** Cost Management → MACC → Drawdown tab shows third-party marketplace spend against your commitment. There is typically a 24-48 hour lag before marketplace transactions appear.

### 5.2 Azure Native MongoDB (ANM)

ANM (also called "Azure Native Integration" or the MongoDB Atlas integrated offering) makes Atlas a first-party Azure resource type, discoverable in Azure Portal under "MongoDB Atlas":

**ANM vs Standard Atlas:**

| Aspect | ANM | Standard Atlas |
|---|---|---|
| Provisioning | Azure Portal / ARM / Bicep / azurerm TF provider | Atlas UI / Atlas Admin API / mongodbatlas TF provider |
| Billing | Azure invoice (MACC-eligible) | MongoDB invoice (not on Azure invoice) |
| Feature parity | Generally at parity; some newer Atlas features lag slightly | Full feature access immediately |
| Identity | Azure RBAC controls Atlas Portal access | Atlas native RBAC |
| Migration | ANM → Standard: contact MongoDB sales | Standard → ANM: re-provision via Azure Portal |

**Azure Marketplace listing types:**
- **Pay-As-You-Go (PAYG):** Available in 48 regions; no upfront commitment; appears on Azure bill; MACC-eligible
- **Committed-use:** Pre-purchased Atlas credits via Marketplace; also MACC-eligible; potential discount vs PAYG

**EA vs CSP vs PAYG:**
- EA (Enterprise Agreement): Microsoft bills through EA enrollment; Atlas Marketplace purchases appear on EA invoice
- CSP (Cloud Solution Provider): Partner bills; Atlas Marketplace available; verify CSP partner supports Atlas Marketplace SKUs
- PAYG: Credit card; full Atlas Marketplace access; no MACC commitment

**Multi-subscription consolidation:** Atlas organizations span subscriptions. Billing is per Atlas organization. If a customer has Atlas clusters across multiple Azure subscriptions under one org, the org-level invoice consolidates spend. MACC drawdown applies per Azure subscription where the Marketplace resource was purchased.

---

## 6. Azure Monitoring and Observability

### 6.1 Atlas → Microsoft Sentinel

The MongoDB Atlas Data Connector in Sentinel uses an Azure Function to pull Atlas logs via the Admin API and push to Log Analytics via DCR/DCE.

**Deployment via Sentinel Content Hub:**
1. Microsoft Sentinel → Content Hub → Search "MongoDB Atlas" → Install
2. Configure the connector: provide Atlas Project ID, Org ID, API public/private key (store in Key Vault)
3. Deployed resources: Function App, Storage Account (JobState table), DCE, DCR, Log Analytics custom table `MDBALogTable_CL`

**Log types ingested:**
- `mongod` process logs (shard/replica set activity)
- `mongos` router logs
- Audit logs (authCheck, authenticate, createCollection, dropCollection, etc.)
- Log categories: `NETWORK`, `ACCESS`, `QUERY`

**KQL example — failed authentication attempts:**
```kusto
MDBALogTable_CL
| where category == "ACCESS" and severity == "W"
| where message contains "Authentication"
| summarize count() by bin(TimeGenerated, 1h), tostring(split(message, "@")[1])
| render timechart
```

**GitHub source:** `Azure/Azure-Sentinel/tree/master/Solutions/MongoDBAtlas`

### 6.2 Log Analytics Workspace Direct

Atlas also supports **direct log export to Azure Blob Storage**, from which Log Analytics can ingest:
```bash
# Atlas Admin API: configure log export to Azure Blob Storage
curl -u "$ATLAS_PUBLIC_KEY:$ATLAS_PRIVATE_KEY" --digest \
  -X POST "https://cloud.mongodb.com/api/atlas/v2/groups/$GROUP_ID/logCollectionJobs" \
  -H "Content-Type: application/json" \
  -d '{
    "resourceType": "REPLICASET",
    "resourceName": "myCluster",
    "redacted": false
  }'
```

Alternatively, use Atlas Log Integration (OpenTelemetry-based, GA 2024) to export via OTel to any OTel-compatible backend including Azure Monitor via the OpenTelemetry Collector with the `azuremonitor` exporter.

### 6.3 Application Insights + MongoDB Driver

Instrument the MongoDB driver with OpenTelemetry to send traces and metrics to Application Insights:

```javascript
// Node.js
const { NodeTracerProvider } = require('@opentelemetry/sdk-node');
const { AzureMonitorTraceExporter } = require('@azure/monitor-opentelemetry-exporter');
const { MongoDBInstrumentation } = require('@opentelemetry/instrumentation-mongodb');

const provider = new NodeTracerProvider();
provider.addSpanProcessor(new SimpleSpanProcessor(
  new AzureMonitorTraceExporter({ connectionString: process.env.APPINSIGHTS_CONNECTIONSTRING })
));
provider.register();

// MongoDB driver auto-instrumented via MongoDBInstrumentation
// Traces include: command name, collection, duration, db.statement
```

MongoDB driver 6.x emits `commandStarted`, `commandSucceeded`, `commandFailed` events. The OTel MongoDB instrumentation package captures these automatically.

**Connection pool events (Application Insights custom metrics):**
```javascript
client.on('connectionPoolCreated', (event) => {
  appInsights.defaultClient.trackMetric({ name: 'Atlas.PoolCreated', value: 1 });
});
client.on('connectionCheckOutFailed', (event) => {
  appInsights.defaultClient.trackMetric({ name: 'Atlas.CheckoutFailed', value: 1,
    properties: { reason: event.reason } });
});
```

### 6.4 Azure Monitor (Metrics via Custom Scraper)

Atlas does not natively push metrics to Azure Monitor. The Azure Architecture Center reference architecture uses an **Azure Functions app** that periodically scrapes the Atlas Metrics API:

```text
Atlas Admin API (/groups/{id}/processes/{host}/measurements)
  → Azure Function (timer trigger, every 1 min)
  → Azure Monitor Custom Metrics Ingestion API
  → Application Insights dashboards / Azure Workbooks
```

The scraper API key (Atlas service account) is stored in Key Vault; the Function uses Managed Identity to access Key Vault.

**Alert rule chaining:** Create Azure Monitor alert rules on custom Atlas metrics → Action Group → Logic App → Teams/Slack notification or PagerDuty webhook. You can also chain in the other direction: Atlas Alert → Atlas webhook → Azure Logic App → Azure Monitor Alert (for unified alerting).

### 6.5 Azure Workbooks for Atlas

Create custom workbooks in Azure Monitor using the custom Atlas metrics or `MDBALogTable_CL` from Log Analytics:
- Connections over time (from Atlas Metrics API scraper)
- Query targeting ratio (scan-to-returned ratio — key performance signal)
- Authentication failures (from audit logs in Sentinel/Log Analytics)
- Replication lag across regions

---

## 7. Azure Regions and Atlas Region Mapping

Atlas is available in 48+ Azure regions. The Atlas region name (used in API/Terraform/CLI) differs from the Azure display name.

**Major regions — Atlas API name → Azure display name:**

| Atlas Region Name | Azure Display Name | Azure Code | Notes |
|---|---|---|---|
| AZURE_EASTUS | East US | eastus | Virginia; ★ recommended |
| AZURE_EASTUS2 | East US 2 | eastus2 | Virginia; ★ recommended |
| AZURE_WESTUS | West US | westus | California |
| AZURE_WESTUS2 | West US 2 | westus2 | Washington; ★ recommended |
| AZURE_WESTUS3 | West US 3 | westus3 | Phoenix |
| AZURE_CENTRALUS | Central US | centralus | Iowa |
| AZURE_NORTHCENTRALUS | North Central US | northcentralus | Illinois |
| AZURE_SOUTHCENTRALUS | South Central US | southcentralus | Texas |
| AZURE_WESTCENTRALUS | West Central US | westcentralus | Wyoming |
| AZURE_CANADACENTRAL | Canada Central | canadacentral | Toronto; ★ recommended |
| AZURE_CANADAEAST | Canada East | canadaeast | Quebec City |
| AZURE_NORTHEUROPE | North Europe | northeurope | Ireland; ★ recommended |
| AZURE_WESTEUROPE | West Europe | westeurope | Netherlands; ★ recommended |
| AZURE_UKSOUTH | UK South | uksouth | London; ★ recommended |
| AZURE_UKWEST | UK West | ukwest | Cardiff |
| AZURE_FRANCECENTRAL | France Central | francecentral | Paris; ★ recommended |
| AZURE_GERMANYWESTCENTRAL | Germany West Central | germanywestcentral | Frankfurt; ★ recommended |
| AZURE_SWITZERLANDNORTH | Switzerland North | switzerlandnorth | Zurich |
| AZURE_NORWAYEAST | Norway East | norwayeast | Oslo |
| AZURE_SWEDENCENTRAL | Sweden Central | swedencentral | Gävle |
| AZURE_POLANDCENTRAL | Poland Central | polandcentral | Warsaw |
| AZURE_ITALYNORTH | Italy North | italynorth | Milan |
| AZURE_SPAINCENTRAL | Spain Central | spaincentral | Madrid |
| AZURE_EASTASIA | East Asia | eastasia | Hong Kong; ★ recommended |
| AZURE_SOUTHEASTASIA | Southeast Asia | southeastasia | Singapore; ★ recommended |
| AZURE_JAPANEAST | Japan East | japaneast | Tokyo; ★ recommended |
| AZURE_JAPANWEST | Japan West | japanwest | Osaka |
| AZURE_AUSTRALIAEAST | Australia East | australiaeast | New South Wales; ★ recommended |
| AZURE_AUSTRALIASOUTHEAST | Australia Southeast | australiasoutheast | Victoria |
| AZURE_AUSTRALIACENTRAL | Australia Central | australiacentral | Canberra |
| AZURE_CENTRALINDIA | Central India | centralindia | Pune; ★ recommended |
| AZURE_SOUTHINDIA | South India | southindia | Chennai |
| AZURE_WESTINDIA | West India | westindia | Mumbai |
| AZURE_BRAZILSOUTH | Brazil South | brazilsouth | Sao Paulo; ★ recommended |
| AZURE_KOREACENTRAL | Korea Central | koreacentral | Seoul; ★ recommended |
| AZURE_KOREASOUTH | Korea South | koreasouth | Busan |
| AZURE_SOUTHAFRICANORTH | South Africa North | southafricanorth | Johannesburg |
| AZURE_UAENORTH | UAE North | uaenorth | Dubai |
| AZURE_ISRAELCENTRAL | Israel Central | israelcentral | Tel Aviv |

**Note:** Always verify current availability at [MongoDB Atlas Cloud Providers and Regions](https://www.mongodb.com/docs/atlas/cloud-providers-regions/) as Atlas adds new Azure regions regularly.

### 7.1 Recommended Region Pairs for HA/DR

| Primary | Secondary | Use case |
|---|---|---|
| AZURE_EASTUS2 | AZURE_EASTUS | US East HA |
| AZURE_WESTUS2 | AZURE_WESTUS3 | US West HA |
| AZURE_NORTHEUROPE | AZURE_WESTEUROPE | EU HA |
| AZURE_UKSOUTH | AZURE_UKWEST | UK HA |
| AZURE_FRANCECENTRAL | AZURE_NORTHEUROPE | France DR |
| AZURE_JAPANEAST | AZURE_JAPANWEST | Japan HA |
| AZURE_AUSTRALIAEAST | AZURE_AUSTRALIASOUTHEAST | ANZ HA |

### 7.2 Availability Zones

Atlas automatically distributes replica set nodes across Azure Availability Zones in regions that support them (★ recommended regions). For a 3-node replica set in eastus2:
- Node 1 → AZ 1
- Node 2 → AZ 2
- Node 3 → AZ 3

For a 5-node replica set, two nodes share an AZ. You cannot control which node is in which AZ; Atlas manages distribution automatically.

### 7.3 Atlas for Government (AtlasGov)

Atlas for Government is a separate deployment on Azure Government (MAG — Microsoft Azure Government):
- Supported regions: `US GOV VIRGINIA` (`AZURE_US_GOV_VIRGINIA`), `US GOV ARIZONA` (`AZURE_US_GOV_ARIZONA`)
- Compliant with FedRAMP High, DoD IL2/IL4/IL5 (check current certifications)
- Separate Atlas control plane: `cloud.mongodbgov.com`
- Separate Terraform provider configuration: use `MONGODB_ATLAS_GOV_BASE_URL`

---

## 8. IaC Patterns: Terraform + Bicep

### 8.1 Provider Setup

```hcl
terraform {
  required_providers {
    mongodbatlas = {
      source  = "mongodb/mongodbatlas"
      version = "~> 2.7"  # v2.x is current; v2 removed mongodbatlas_cluster — see mongodb-atlas-terraform skill
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

provider "mongodbatlas" {
  public_key  = var.atlas_public_key
  private_key = var.atlas_private_key
}

provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
}
```

### 8.2 Private Endpoint — Complete Terraform Pattern

```hcl
# Step 1: Create Atlas Private Link endpoint service
resource "mongodbatlas_privatelink_endpoint" "atlas" {
  project_id    = var.atlas_project_id
  provider_name = "AZURE"
  region        = "AZURE_EASTUS2"
}

# Step 2: Create Azure Private Endpoint (NIC in your VNet)
resource "azurerm_private_endpoint" "atlas" {
  name                = "pe-atlas-eastus2"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.private_endpoints.id

  private_service_connection {
    name                           = "psc-atlas"
    private_connection_resource_id = mongodbatlas_privatelink_endpoint.atlas.private_link_service_resource_id
    is_manual_connection           = true
    request_message                = "Atlas private endpoint"
  }
}

# Step 3: Register the Azure endpoint with Atlas
resource "mongodbatlas_privatelink_endpoint_service" "atlas" {
  project_id                  = var.atlas_project_id
  private_link_id             = mongodbatlas_privatelink_endpoint.atlas.id
  endpoint_service_id         = azurerm_private_endpoint.atlas.id
  provider_name               = "AZURE"
  private_endpoint_ip_address = azurerm_private_endpoint.atlas.private_service_connection[0].private_ip_address
}

# Step 4: Private DNS Zone and link
resource "azurerm_private_dns_zone" "atlas" {
  name                = "${var.cluster_id}.mongodb.net"
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_private_dns_zone_virtual_network_link" "atlas" {
  name                  = "link-atlas-dns"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.atlas.name
  virtual_network_id    = azurerm_virtual_network.main.id
  registration_enabled  = false
}

resource "azurerm_private_dns_a_record" "atlas_node" {
  name                = "pl-0-eastus2"
  zone_name           = azurerm_private_dns_zone.atlas.name
  resource_group_name = azurerm_resource_group.main.name
  ttl                 = 300
  records             = [azurerm_private_endpoint.atlas.private_service_connection[0].private_ip_address]
}

# Multi-region loop pattern
variable "atlas_regions" {
  default = ["AZURE_EASTUS2", "AZURE_WESTEUROPE"]
}

# Use for_each with a map of regions to create endpoints per region
```

### 8.3 Key Vault + Atlas EAR Terraform

```hcl
resource "azurerm_key_vault" "atlas" {
  name                = "kv-atlas-${var.env}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"  # or "premium" for Managed HSM
  enable_rbac_authorization = true
  purge_protection_enabled  = true
  soft_delete_retention_days = 90
}

resource "azurerm_key_vault_key" "atlas" {
  name         = "atlas-cmk"
  key_vault_id = azurerm_key_vault.atlas.id
  key_type     = "RSA"
  key_size     = 4096
  key_opts     = ["decrypt", "encrypt", "sign", "unwrapKey", "verify", "wrapKey"]

  rotation_policy {
    automatic {
      time_after_creation = "P90D"
    }
    expire_after         = "P180D"
    notify_before_expiry = "P30D"
  }
}

# Atlas service principal RBAC
resource "azurerm_role_assignment" "atlas_crypto" {
  scope                = azurerm_key_vault.atlas.id
  role_definition_name = "Key Vault Crypto User"
  principal_id         = var.atlas_service_principal_object_id
}

resource "mongodbatlas_encryption_at_rest" "atlas" {
  project_id = var.atlas_project_id
  azure_key_vault_config {
    enabled               = true
    azure_environment     = "AZURE"
    subscription_id       = var.azure_subscription_id
    resource_group_name   = azurerm_resource_group.main.name
    key_vault_name        = azurerm_key_vault.atlas.name
    key_identifier        = azurerm_key_vault_key.atlas.versionless_id
    # Use versionless_id for automatic rotation pickup
  }
}
```

### 8.4 Entra ID + Atlas OIDC Terraform

```hcl
# Create Entra ID app for workload federation
resource "azuread_application" "atlas_workload" {
  display_name = "MongoDB Atlas Workload Identity"
}

resource "azuread_service_principal" "atlas_workload" {
  client_id = azuread_application.atlas_workload.client_id
}

# Atlas OIDC provider config (via Atlas Admin API, no official TF resource yet)
# Use mongodbatlas_federated_settings_org_config for SAML federation
```

### 8.5 Azure Bicep Example — Private Endpoint for Atlas

```bicep
param location string = resourceGroup().location
param vnetName string
param subnetName string
param atlasPrivateLinkServiceResourceId string  // from Atlas API

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-09-01' = {
  name: 'pe-mongodb-atlas'
  location: location
  properties: {
    subnet: {
      id: resourceId('Microsoft.Network/virtualNetworks/subnets', vnetName, subnetName)
    }
    privateLinkServiceConnections: [
      {
        name: 'atlas-connection'
        properties: {
          privateLinkServiceId: atlasPrivateLinkServiceResourceId
          requestMessage: 'Atlas PE request'
        }
      }
    ]
  }
}

resource privateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.mongodb.net'
  location: 'global'
}

resource dnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateDnsZone
  name: 'atlas-dns-link'
  location: 'global'
  properties: {
    virtualNetwork: {
      id: resourceId('Microsoft.Network/virtualNetworks', vnetName)
    }
    registrationEnabled: false
  }
}

output privateEndpointId string = privateEndpoint.id
output privateEndpointNicIp string = privateEndpoint.properties.customDnsConfigs[0].ipAddresses[0]
```

---

## 9. Azure-Specific Troubleshooting Playbook

### 9.1 Private Endpoint DNS Resolution Failures

**Symptom:** `nslookup pl-0-eastus2.uzgh6.mongodb.net` returns public IP or NXDOMAIN.

**Step 1 — Verify the Private DNS Zone is linked to the VNet:**
```bash
az network private-dns link vnet list \
  --zone-name uzgh6.mongodb.net --resource-group myRG
# If empty: create the VNet link — resolution will fail without it
az network private-dns link vnet create \
  --zone-name uzgh6.mongodb.net --resource-group myRG \
  --name atlas-vnet-link --virtual-network myVNet --registration-enabled false
```

**Step 2 — Verify the A record exists in the DNS zone:**
```bash
az network private-dns record-set a list \
  --zone-name uzgh6.mongodb.net --resource-group myRG
# If missing: add A record pointing to the private endpoint NIC IP
```

**Step 3 — Verify the VM/pod is using Azure DNS:**
```bash
cat /etc/resolv.conf   # Linux — nameserver should be 168.63.129.16
# Custom DNS servers bypass Azure DNS; configure conditional forwarding:
# Forward *.mongodb.net to 168.63.129.16 (Azure DNS resolver)
```

**Step 4 — Check for split-horizon DNS conflict:**
If your custom DNS server has a public zone for `mongodb.net`, it shadows the private zone. Fix: add a conditional forwarder for `*.mongodb.net` pointing exclusively to the Azure Private DNS Resolver inbound endpoint IP.

**Step 5 — Hub-and-spoke: verify spoke VNet linkage:**
The Private DNS Zone must be linked to *every* VNet that needs resolution — including spoke VNets. If using Azure Private DNS Resolver, confirm the forwarding ruleset is applied to the spoke VNet's DNS settings.

### 9.2 NSG Blocking Atlas Connection

**Symptom:** DNS resolves to private IP, but connection times out.

```bash
# Test from within VNet
telnet pl-0-eastus2.uzgh6.mongodb.net 1024  # (port from SRV record)
# If "Connection timed out": NSG is blocking

# Identify blocking rule
az network watcher test-connectivity \
  --source-resource <vm-resource-id> \
  --dest-address <private-endpoint-ip> \
  --dest-port 1024 \
  --resource-group myRG
```

**Check:**
- NSG on compute subnet — outbound rule for TCP 1024-65535 to private endpoint subnet IP
- NSG on private endpoint subnet — if `disablePrivateEndpointNetworkPolicies` is false, inbound rule needed
- Azure Firewall between compute and private endpoint — add network rule TCP 1024-65535

### 9.3 AKS Pod-to-Atlas Connectivity

**Decision: Private endpoint or public endpoint?**
- Preferred: Private endpoint in the AKS node pool VNet (or peered hub VNet)
- DNS in AKS pods: AKS uses CoreDNS → Azure DNS. Ensure the AKS VNet is linked to the Atlas private DNS zone.

```bash
# Test from a debug pod
kubectl run -it --rm debug --image=busybox --restart=Never -- sh
nslookup pl-0-eastus2.uzgh6.mongodb.net
# Should return private IP
```

**Common AKS issue:** The AKS node pool VNet is peered to a hub VNet containing the private endpoint, but the node VNet is not linked to the Private DNS Zone. Fix: link the AKS VNet to the Atlas private DNS zone.

### 9.4 Entra ID OIDC Token Claim Mapping Failures

**Symptom:** Atlas rejects token with "Authentication failed" despite valid Entra ID token.

**Step 1 — Decode the JWT and check the `iss` (issuer) claim:**
```bash
# Decode the token header+payload (base64 -d on each dot-separated segment)
echo "<token_part_2>" | base64 -d 2>/dev/null | python3 -m json.tool | grep iss
# Atlas expects:  "iss": "https://sts.windows.net/<tenant-id>/"
# v2.0 tokens may issue: "https://login.microsoftonline.com/<tenant-id>/v2.0"
# Fix: configure Atlas Workload IDP issuer to match exactly what Entra ID issues
```

**Step 2 — Verify the `aud` (audience) claim:**
The `aud` must match the Client ID configured in the Atlas Workload Identity Provider. For AKS federated credentials the audience is `api://AzureADTokenExchange` — ensure the Atlas IDP audience field matches.

**Step 3 — Check group claims for workforce OIDC:**
```bash
# Verify Entra ID app manifest has groupMembershipClaims set
az ad app show --id <appId> --query "groupMembershipClaims"
# Should return "SecurityGroup" — if null, groups claim is omitted from tokens
```
Large group membership (>150 groups): Entra ID omits the `groups` claim and adds `_claim_names` with a Graph API URL instead — Atlas cannot follow this URL. Fix: switch to app roles, or use the "Groups to emit" filter in the Entra ID app Token Configuration to restrict to relevant groups only.

**Step 4 — Check token expiry and clock skew:**
Atlas validates the `exp` claim. Ensure the host generating tokens and the Atlas control plane have synchronized clocks (NTP). A skew >5 minutes causes validation failures.

### 9.5 Key Vault Access Denied During Atlas Cluster Startup

**Symptom:** Cluster fails to start with "KMS access failure" or EAR validation error.

**Step 1 — Verify the Atlas service principal has the correct RBAC roles:**
```bash
az role assignment list \
  --assignee <atlas-sp-object-id> \
  --scope "/subscriptions/.../Microsoft.KeyVault/vaults/<kv-name>"
# Expect both: "Key Vault Crypto User" and "Reader"
# If missing: re-run the role assignment commands from §3.2
```

**Step 2 — Check the Key Vault network firewall:**
```bash
az keyvault show --name <kv-name> --query "properties.networkAcls"
# If defaultAction == "Deny": ensure the Atlas private endpoint connection is Approved,
# or add Atlas IP ranges to the allowlist for non-private-endpoint setups
```

**Step 3 — Verify the key exists and has not been deleted:**
```bash
az keyvault key show --vault-name <kv-name> --name atlaskey
# If key was deleted and purge protection is enabled: it cannot be restored for 7-90 days
# Use: az keyvault key recover --vault-name <kv-name> --name atlaskey
```

**Multi-region cluster note:** Each region's Atlas nodes must independently reach AKV. If using AKV private endpoint, a separate approved private endpoint connection is required for each Atlas-deployed region.

### 9.6 MACC Consumption Not Tracking

**Symptoms:** Atlas spend not appearing in Azure Cost Management MACC drawdown.

**Checks:**
1. Was Atlas purchased through Azure Marketplace (not directly from MongoDB)?
   - If direct MongoDB invoice: not MACC-eligible. Switch to Marketplace Pay-As-You-Go.
2. Is there a billing lag? 24-48 hours is normal.
3. Is the Azure subscription associated with the MACC enrollment?
   - EA customers: verify the subscription is under the correct EA enrollment.
4. Are you using the correct Atlas Marketplace SKU?
   - "MongoDB Atlas (Pay As You Go)" → MACC-eligible
   - Legacy Atlas SKUs created pre-2022 → may not be eligible; recreate with current SKU

### 9.7 Event Hub Consumer Group Exhaustion

**Symptom:** Atlas Stream Processing fails to connect to Event Hub with "Consumer group ... does not exist" or "Too many active receivers."

Standard Event Hub tier supports 20 consumer groups per hub; Premium tier supports unlimited. Each Atlas Stream Processor consumes one consumer group.

```bash
# Count current consumer groups
az eventhubs eventhub consumer-group list \
  --namespace-name <ns> \
  --eventhub-name <hub> \
  --resource-group myRG \
  --query "length(@)"

# If at or near 20: either upgrade the namespace to Premium,
# reduce concurrent stream processors sharing this hub,
# or split load across multiple Event Hubs
az eventhubs namespace update \
  --name <ns> --resource-group myRG --sku Premium
```

### 9.8 App Service Slot Swap Connection String Race

**Symptom:** Brief connection errors immediately after slot swap.

**Root cause:** During swap, new instances start before old instances drain. Connections using the old connection string hit the new database briefly.

**Fix:**

1. **Use slot-specific (non-sticky) connection strings** — mark the Atlas URI app setting as a deployment slot setting so each slot retains its own string through the swap.
2. **Add a warmup probe** — configure App Service startup with a health check that verifies Atlas connectivity before the slot goes live:
   ```json
   // host.json (Azure Functions) or app_command_line
   { "healthMonitor": { "enabled": true, "healthCheckInterval": "00:00:10" } }
   ```
3. **Tune driver timeouts** to absorb the brief swap transient:
   ```
   serverSelectionTimeoutMS=15000&connectTimeoutMS=10000
   ```
4. **Rely on built-in Atlas retry** — `retryWrites=true&retryReads=true` is on by default in the SRV connection string; verify it has not been disabled.

---

## 10. Azure Security and Compliance

### 10.1 Microsoft Defender for Cloud

Defender for Cloud assesses your Azure workloads and can detect threats. For Atlas:

- **Defender for Servers:** If Atlas data leaves the Atlas VPC (e.g., to an Azure VM for processing), protect that VM with Defender for Servers.
- **Defender for App Service:** Recommended for Azure Functions and App Service that connect to Atlas.
- **Regulatory compliance blade:** Check Atlas-adjacent Azure resources against CIS, NIST, PCI DSS, HIPAA benchmarks. Atlas itself is not an Azure resource so won't appear in Defender posture, but the surrounding Azure infrastructure will.

### 10.2 Azure Policy for Atlas Private Endpoint Enforcement

Deny public Atlas access at the infrastructure level using Azure Policy:

```json
{
  "mode": "All",
  "policyRule": {
    "if": {
      "allOf": [
        { "field": "type", "equals": "Microsoft.Network/virtualNetworks" },
        { "field": "tags['atlas-cluster']", "exists": "true" },
        {
          "not": {
            "field": "Microsoft.Network/virtualNetworks/subnets[*].privateEndpoints[*].id",
            "exists": "true"
          }
        }
      ]
    },
    "then": {
      "effect": "Deny"
    }
  }
}
```

More practical: use **Azure Policy to audit** VNets that have Atlas peering without corresponding private endpoints, and remediate by migrating to Private Link.

For the Atlas side, enable "Block public access" in Atlas project → Network Access to prevent non-private-endpoint connections:
```bash
atlas accessLists delete --all  # Remove all public IP allowlist entries
# Then in Atlas UI: Network Access → Private Endpoint → Block Public Access
```

### 10.3 PIM (Privileged Identity Management) for Atlas Admin Access

Entra ID PIM provides just-in-time (JIT) access to Atlas administrative functions federated through Entra ID SAML/OIDC.

**Pattern:**
1. Configure Atlas SAML federation with Entra ID.
2. Create an Entra ID group for "Atlas Org Admins."
3. In PIM, configure this group as eligible (not permanent).
4. Atlas admins request elevation in PIM → MFA + approval → group membership granted for 1-4 hours → Atlas SAML token includes Atlas Org Admin role.
5. After expiry, membership removed automatically.

This satisfies least-privilege requirements for SOC 2, PCI DSS, and FedRAMP.

### 10.4 Atlas Backup Compliance Policy + Azure Backup Alignment

Atlas Backup Compliance Policy (BCP) locks backup settings for all clusters in a project — deletion and modification require MPA (Multi-Party Authorization). Align with Azure:

- **Retention:** Set Atlas backup retention to match or exceed Azure Policy backup requirements (e.g., 35 days for PCI).
- **Point-in-Time Recovery (PITR):** Enable Atlas PITR with oplog window. For HIPAA/PCI, 24-hour PITR minimum is standard.
- **Export to Azure Blob:** Atlas Cloud Backup supports snapshot export to Azure Blob Storage for long-term archival compliance.

### 10.5 Regulatory Compliance

| Framework | Atlas Certification | Azure shared responsibility |
|---|---|---|
| SOC 2 Type II | Yes | Azure: infrastructure. Atlas: application layer |
| ISO 27001 | Yes | Joint |
| PCI DSS 4.0 | Yes (since 2023) | Azure + Atlas share the cardholder data scope |
| HIPAA | Yes (BAA available) | Azure BAA + Atlas BAA both required |
| FedRAMP High | AtlasGov (Azure Gov regions) | Azure Gov FedRAMP + AtlasGov |
| GDPR | Yes (DPA available) | Azure DPA + Atlas DPA |
| ISO 27017/27018 | Yes | Joint |

**Shared responsibility nuance:** For PCI DSS, Atlas handles network segmentation and encryption of stored data (SAQ criteria). The customer is responsible for access control (configuring Atlas users/roles), audit logging (enabling Atlas auditing), and securing the application layer running in Azure.

---

## Common Anti-Patterns

- **Using port 27017 in NSG rules with private endpoint-aware connection strings** — SRV records return high ports (1024+); restrict to 1024-65535 TCP outbound from compute to private endpoint subnet.
- **Forgetting to link the Private DNS Zone to every VNet** that needs Atlas resolution, especially in hub-and-spoke when adding new spoke VNets.
- **Using the same Entra ID app registration for both workforce and workload identity** — separate registrations are required; they have different token audiences and lifetimes.
- **Using Key Vault Access Policies instead of RBAC** — RBAC is the modern pattern, supports PIM, Conditional Access, and proper audit trail; Access Policies are being deprecated.
- **Including the key version in the Atlas key identifier** — omit the version to enable automatic rotation pickup; specifying a version requires manual Atlas config update on every rotation.
- **Not creating a Key Vault private endpoint in every Atlas cluster region** — multi-region Atlas clusters need a KV private endpoint per deployed region; missing one region causes node startup failures after a crash.
- **Using PAYG Azure Functions (consumption plan) with large MongoClient pools** — each Function invocation cold-starts a new process; set `maxPoolSize: 3-5`; do not use default pool of 100.
- **Purchasing Atlas directly from MongoDB when MACC drawdown is needed** — only Marketplace purchases count toward MACC; verify the customer's billing path before deployment.
- **Using VNet peering instead of Private Link for new deployments** — peering requires managing address space overlap across all peered VNets; Private Link is recommended and simpler.
- **Not enabling Atlas Backup Compliance Policy before enabling regulated workloads** — once data is live, enabling BCP requires MPA and cannot retroactively protect snapshots that already exist without the policy.

---

## References

- [MongoDB Atlas Private Endpoint Management](https://www.mongodb.com/docs/atlas/security-manage-private-endpoint/)
- [Atlas Private Endpoint Troubleshooting](https://www.mongodb.com/docs/atlas/troubleshoot-private-endpoints/)
- [Deploy MongoDB Atlas in Azure — Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/databases/architecture/mongodb-atlas-baseline)
- [Atlas Secretless Azure Key Vault Authentication](https://www.mongodb.com/docs/atlas/security/azure-kms-secretless/)
- [Atlas Workforce Identity Federation (OIDC)](https://www.mongodb.com/docs/atlas/workload-oidc/)
- [MongoDB Blog: Workforce Identity Federation GA](https://www.mongodb.com/blog/post/introduces-workforce-identity-federation-openid-connect-support-database-access)
- [MongoDB Blog: Workload Identity Federation GA](https://www.mongodb.com/blog/post/mongodb-introduces-workload-identity-federation-database-access)
- [Atlas Stream Processing on Azure + Private Link](https://www.mongodb.com/blog/post/atlas-stream-processing-now-supports-azure-and-azure-private-link)
- [MongoDB Atlas Logs in Microsoft Sentinel](https://www.mongodb.com/company/blog/innovation/simplifying-enterprise-security-management-mongodb-atlas-logs-microsoft-sentinel)
- [RAG with MongoDB Atlas and Azure OpenAI](https://www.mongodb.com/company/blog/technical/rag-made-easy-mongodb-atlas-azure-openai)
- [Azure OpenAI on your MongoDB Atlas data](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/references/mongo-db)
- [Atlas Manage Connections with Azure Functions](https://www.mongodb.com/docs/atlas/manage-connections-azure-functions/)
- [Atlas Azure Event Hubs + Kafka Connector](https://www.mongodb.com/blog/post/using-azure-event-hubs-with-connector-apache-kafka)
- [Azure Native MongoDB (ANM)](https://azure.microsoft.com/en-us/solutions/mongodb)
- [MACC tracking in Azure Cost Management](https://learn.microsoft.com/en-us/azure/cost-management-billing/benefits/macc/track-consumption-commitment)
- [MongoDB Atlas Pay-As-You-Go on Azure Marketplace](https://www.mongodb.com/blog/post/introducing-pay-as-you-go-atlas-azure-marketplace)
- [Atlas AKS create MongoDB infrastructure](https://learn.microsoft.com/en-us/azure/aks/create-mongodb-infrastructure)
- [mongodbatlas Terraform provider](https://registry.terraform.io/providers/mongodb/mongodbatlas/latest/docs)
- [Atlas KMS Encryption over Private Endpoints](https://www.mongodb.com/docs/atlas/security/azure-kms-over-private-endpoint/)
- [Atlas Guidance for Data Encryption](https://www.mongodb.com/docs/atlas/architecture/current/data-encryption/)
- [Microsoft Ignite 2025: MongoDB + Azure AI](https://www.mongodb.com/company/blog/events/microsoft-ignite-2025-deepening-mongodb-microsoft-alliance)
- [Atlas HIPAA Compliance](https://www.mongodb.com/docs/atlas/architecture/current/compliance/hipaa/)
- [Atlas PCI DSS Compliance](https://www.mongodb.com/docs/atlas/architecture/current/compliance/pcidss/)
- [Atlas Cloud Providers and Regions](https://www.mongodb.com/docs/atlas/cloud-providers-regions/)
- [Atlas for Government — Supported Regions](https://www.mongodb.com/docs/atlas/government/overview/supported-regions/)
- [GitHub: eugenebogaart/Atlas-Azure-Link Terraform example](https://github.com/eugenebogaart/Atlas-Azure-Link)
- [GitHub: Azure-Sentinel/Solutions/MongoDBAtlas](https://github.com/Azure/Azure-Sentinel/tree/master/Solutions/MongoDBAtlas)

## See Also

- [[mongodb-atlas-multicloud]] — multi-cloud replica sets, cross-cloud DR, GCP PSC basics, VNet peering fundamentals
- [[mongodb-aws-networking]] — analogous AWS-specific skill (VPC peering, AWS PrivateLink, Transit Gateway, KMS)
- [[mongodb-atlas-expert]] — Atlas general operations, cluster management, backup, scaling
- [[mongodb-encryption]] — MongoDB encryption in depth (client-side field level encryption, queryable encryption, TLS)
- [[mongodb-atlas-stream-processing]] — Atlas Stream Processing pipeline authoring, operators, windowing
