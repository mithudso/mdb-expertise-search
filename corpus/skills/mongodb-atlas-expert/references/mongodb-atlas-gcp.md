<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-gcp` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

# MongoDB Atlas on GCP — Networking, Integration & Partnership

Deep reference for MongoDB Atlas on Google Cloud Platform covering everything beyond the basics in `mongodb-atlas-multicloud`. Topics include Private Service Connect (PSC) port-mapped and legacy architectures with Cloud DNS and forwarding rules, GCP IAM and Workload Identity Federation for Atlas OIDC authentication, Google Cloud KMS BYOK envelope encryption with key rotation and failsafe behavior, GKE + Atlas Kubernetes Operator deployment, Vertex AI + Atlas Vector Search embedding pipelines, BigQuery and Dataflow CDC integration, Cloud Run and Cloud Functions serverless connection patterns, GCP Pub/Sub with Atlas Stream Processing, GCP Marketplace billing, a complete GCP-to-Atlas region mapping table, Terraform IaC patterns, and a GCP-specific troubleshooting playbook.

## When to use this skill
- When configuring Atlas Private Service Connect (PSC) on GCP including port-mapped vs legacy architecture, DNS private zones, forwarding rules, and Shared VPC topology
- When setting up GCP IAM / Workload Identity Federation (OIDC) for Atlas database authentication from GCE, GKE, Cloud Run, Cloud Functions, or App Engine
- When implementing Google Cloud KMS as Atlas Encryption at Rest BYOK/CMEK including key rotation workflow and failsafe behavior
- When deploying Atlas Kubernetes Operator (AKO) on GKE and managing CRDs for Atlas resources
- When integrating Atlas Vector Search with Vertex AI embedding pipelines, Agent Engine, or Gemini-backed RAG
- When connecting Cloud Run or Cloud Functions to Atlas and avoiding serverless connection pooling anti-patterns
- When setting up Atlas Stream Processing with Google Cloud Pub/Sub as a sink
- When evaluating GCP Marketplace Atlas billing, EDP commit applicability, or startup credit stacking
- When troubleshooting PSC connectivity, DNS SRV resolution failures, cross-project Shared VPC, or Cloud KMS access for Atlas
- When looking up the GCP region name → Atlas region identifier mapping for Terraform or API calls
- When configuring Atlas + Dataflow CDC pipelines, BigQuery Data Federation, or Cloud Storage federated queries

---

## 1. GCP Networking with Atlas

### 1.1 Architecture Overview: VPC Peering vs Private Service Connect

**VPC Peering (legacy):**
- Bidirectional route exchange between Atlas producer VPC and customer VPC
- Atlas can initiate connections back to your VPC (trust boundary extends both ways)
- IP CIDR overlap restrictions apply
- Still functional but not recommended for new deployments

**Private Service Connect (PSC) — current recommended:**
- Unidirectional: your VPC reaches Atlas; Atlas cannot initiate connections back
- No trust boundary extension — your VPC never peers with Atlas's producer project
- RFC 1918 addresses on your side; Atlas traffic never traverses the public internet
- Per-region forwarding rule maps your private IP to Atlas service attachment
- Supports cross-region access via **Global Access** flag on the forwarding rule

**Decision rule:** New deployments should always use PSC. Existing VPC-peered clusters can continue running but consider migrating to PSC for better security isolation.

### 1.2 PSC Architecture: Legacy vs Port-Mapped

| Aspect | Legacy (deprecated Apr 30 2027) | Port-Mapped (current) |
|---|---|---|
| Connection string prefix | `_pl-[index]_` | `_psc-[index]_` |
| IP addresses per region | 50 (one per node/connection) | 1 |
| Forwarding rules per region | 50 | 1 |
| Service attachments | 50 | Consolidated |
| Load balancers | 50 | Consolidated |
| Scaling | Full redeployment required | Decoupled — no redeployment needed |
| Subnet size needed | /26 (64 IPs) minimum | /29 or smaller |
| API flag | none / default | `portMappingEnabled: true` |

**Port-mapped PSC API example:**
```bash
curl -4 -i --digest -u "ATLAS_PUBLIC_KEY:ATLAS_PRIVATE_KEY" \
  --request POST \
  --header "Content-Type: application/json" \
  --header "Accept: application/vnd.atlas.2025-03-12+json" \
  --data '{"providerName": "GCP", "region": "CENTRAL_US", "portMappingEnabled": true}' \
  "https://cloud.mongodb.com/api/atlas/v2/groups/{GROUP_ID}/privateEndpoint/endpointService"
```

### 1.3 Migrating Legacy PSC to Port-Mapped PSC (Required before Apr 30 2027)

Legacy non-port-mapped endpoints are deprecated and will be disabled on **April 30, 2027**. Migrate proactively using this zero-downtime 3-step procedure:

**Step 1 — Create new port-mapped endpoint (alongside the existing legacy one)**
```bash
curl -4 -i --digest -u "ATLAS_PUBLIC_KEY:ATLAS_PRIVATE_KEY" \
  --request POST \
  --header "Content-Type: application/json" \
  --header "Accept: application/vnd.atlas.2025-03-12+json" \
  --data '{"providerName": "GCP", "region": "CENTRAL_US", "portMappingEnabled": true}' \
  "https://cloud.mongodb.com/api/atlas/v2/groups/{GROUP_ID}/privateEndpoint/endpointService"
```
Create the new GCP forwarding rule for the new service attachment (one IP, one rule). Both old and new endpoints are live simultaneously.

**Step 2 — Update application connection strings**
- Retrieve the new `_psc-[index]_` connection string from Atlas UI
- Update application config/environment to use new string
- Deploy and verify connections succeed through the new endpoint
- The old `_pl-[index]_` endpoint remains active during this window

**Step 3 — Remove legacy endpoint**
Once all traffic confirmed on new endpoint: delete legacy Atlas endpoint + all 50 legacy GCP forwarding rules.

**Identification:** Legacy endpoints show `_pl-` prefix in connection strings. Port-mapped show `_psc-` prefix.

### 1.4 PSC Step-by-Step Setup (Port-Mapped, New Deployments)

**Step 1: Create consumer VPC and subnets**
```bash
gcloud compute networks create consumer-vpc --subnet-mode=custom
gcloud compute networks subnets create app-subnet \
  --range=10.10.10.0/29 --network=consumer-vpc --region=us-central1

# PSC endpoint subnet — needs to be in same region as Atlas deployment
gcloud compute networks subnets create psc-endpoint-us-central1 \
  --range=192.168.10.0/26 --network=consumer-vpc --region=us-central1
```

**Step 2: Reserve a static internal IP for the PSC forwarding rule**
```bash
gcloud compute addresses create atlas-psc-ip \
  --region=us-central1 \
  --subnet=psc-endpoint-us-central1 \
  --address-type=INTERNAL
```

**Step 3: Create PSC forwarding rule pointing at Atlas service attachment**
```bash
# Atlas generates the service attachment ID; retrieve from Atlas UI or API
# --allow-psc-global-access is optional here; it can also be added later via 'update' (see 1.6)
gcloud compute forwarding-rules create atlas-psc-fw \
  --region=us-central1 \
  --network=consumer-vpc \
  --address=atlas-psc-ip \
  --target-service-attachment=projects/ATLAS_PROJECT/regions/us-central1/serviceAttachments/SA_NAME \
  --load-balancing-scheme="" \
  --allow-psc-global-access   # Include now for cross-region access, or add later via update
```

**Step 4: Submit endpoint to Atlas (portal or API)**
Upload the forwarding rule name to Atlas → it accepts/activates the connection (takes ~10 minutes to reach `Available` state).

**Step 5: Outbound firewall rule**
```bash
gcloud compute firewall-rules create allow-atlas-psc-outbound \
  --network=consumer-vpc \
  --direction=EGRESS \
  --action=ALLOW \
  --rules=tcp:1024-65535 \
  --destination-ranges=192.168.10.0/26
```

### 1.5 Cloud DNS Private Zone for Atlas SRV Records

When using PSC, Atlas connection strings use `mongodb+srv://` which resolves a `_mongodb._tcp.` SRV record. Those SRV entries point to hostnames like `pl-0-us-central1-gcp.xxxxx.mongodb.net`. You must ensure your VMs/pods can resolve these hostnames to your PSC forwarding rule's private IP.

**Atlas DNS resolution chain (port-mapped):**
```
mongodb+srv://cluster1-psc-0.xxxxx.mongodb.net
  → SRV _mongodb._tcp.cluster1-psc-0.xxxxx.mongodb.net
    → pl-0-us-central1-gcp.xxxxx.mongodb.net (port 1024)
    → pl-0-us-central1-gcp.xxxxx.mongodb.net (port 1025)  [secondary]
    → pl-0-us-central1-gcp.xxxxx.mongodb.net (port 1026)  [secondary]
      → Resolves via Atlas public DNS to your PSC forwarding rule IP
```

Atlas handles the final DNS resolution automatically once the PSC endpoint is `Available`; you do NOT need to create a Cloud DNS private zone for Atlas hostnames in most setups. However, for GKE pods or environments with custom resolvers that block external DNS for `*.mongodb.net`, create a Cloud DNS private zone:

```bash
# Create private zone for mongodb.net
gcloud dns managed-zones create atlas-private \
  --dns-name="mongodb.net." \
  --description="Atlas PSC DNS" \
  --visibility=private \
  --networks=consumer-vpc

# Add CNAME or A record pointing pl-0-us-central1-gcp.xxxxx.mongodb.net → PSC IP
gcloud dns record-sets create pl-0-us-central1-gcp.xxxxx.mongodb.net. \
  --zone=atlas-private \
  --type=A \
  --ttl=300 \
  --rrdatas=192.168.10.5   # PSC forwarding rule IP
```

**Alternative (preferred):** Use the Atlas-provided private endpoint connection string that avoids SRV entirely and contains the direct PSC hostnames.

### 1.6 Global Access (Cross-Region PSC)

GCP PSC forwarding rules are regional. To allow a VM in `us-east1` to reach a PSC endpoint defined in `us-central1`:

```bash
# On the consumer-side forwarding rule:
gcloud compute forwarding-rules update atlas-psc-fw \
  --region=us-central1 \
  --allow-psc-global-access
```

No change needed on the Atlas side. Traffic stays within GCP backbone — does not traverse the public internet.

### 1.7 Shared VPC (Host + Service Project Topology)

When your organization uses Shared VPC:
- Create the PSC endpoint (forwarding rule and reserved IP) in the **host project's** VPC
- Resources in all attached **service projects** can reach Atlas through the shared host VPC
- The Atlas endpoint service receives traffic from the host project's IP range

Steps:
1. Verify IAM: service project users need `compute.networkUser` role on the host project network
2. Create PSC forwarding rule in the host project's VPC (target subnet is in host project)
3. Grant service project service accounts access to the host VPC subnet
4. All service project workloads resolve Atlas hostnames via the shared VPC PSC endpoint

**Important:** If using Shared VPC in a non-host project context, the forwarding rule must reference the host project's subnet by full resource path.

### 1.8 Cloud NAT for Atlas Public Access (Non-PSC)

If PSC is not available (Flex/M2/M5 clusters), use Cloud NAT for outbound Atlas connectivity from private VMs:
```bash
gcloud compute routers create atlas-router --network=consumer-vpc --region=us-central1
gcloud compute routers nats create atlas-nat \
  --router=atlas-router \
  --auto-allocate-nat-external-ips \
  --nat-all-subnet-ip-ranges \
  --region=us-central1
```
Add the NAT gateway's external IP to the Atlas project IP access list.

---

## 2. GCP IAM and Authentication

### 2.1 Workload Identity Federation (OIDC) for Atlas Database Access

**What it does:** GCP workloads (GKE pods, Cloud Run, Cloud Functions, GCE VMs, App Engine) authenticate to Atlas using their native GCP service account identity — no hardcoded MongoDB credentials.

**Requirements:**
- MongoDB 7.0.11 or later
- Atlas M10+ dedicated cluster (not Free/Flex)
- Supported driver (Java v5.1+, C# v2.25+, Go v1.17+, PyMongo v4.7+, Node v6.7+, Kotlin v5.1+, Rust v3.2+)

**Step 1: Configure Atlas Workload IdP (one-time per org)**
In Atlas UI → Organization Settings → Federated Authentication → Add Identity Provider → select type Workload:
- **Issuer URI:** `https://accounts.google.com`
- **Audience:** Choose any custom value (e.g., `https://atlas.mongodb.com/gcp`)
- **User Claim:** `sub` (leave default)
- **Authorization Type:** User ID (for individual service accounts) or Group Membership

**Step 2: Create Atlas database user**
- Auth method: Federated Authentication (OIDC)
- External auth name: GCP service account's **Unique Id** (numeric, found in GCP Console → IAM → Service Accounts)

**Step 3: Application connection string**
```
mongodb+srv://<cluster>.mongodb.net/?authMechanism=MONGODB-OIDC&authMechanismProperties=ENVIRONMENT:gcp,TOKEN_RESOURCE:<audience>
```

No code changes required — the driver fetches GCP service account tokens automatically from the GCP metadata server when `ENVIRONMENT:gcp` is set.

**Supported GCP compute surfaces (built-in auth — no code needed):**
| Environment | Principal |
|---|---|
| Compute Engine (GCE) | GCP Service Account |
| GKE (Workload Identity) | GCP Service Account via KSA |
| Cloud Run | GCP Service Account |
| Cloud Functions (Gen 1 & 2) | GCP Service Account |
| App Engine (Standard/Flexible) | GCP Service Account |
| Cloud Build | GCP Service Account |

### 2.2 Service Account-Based Atlas Admin API Authentication (for Terraform / CI)

When Terraform or Cloud Build pipelines need to call the Atlas Administration API:
- Use Atlas API keys (public/private key pair) stored in Secret Manager
- Access via `gcloud secrets versions access latest --secret=atlas-api-key`
- For advanced setups, use Atlas Organization-level Workload Identity Provider scoped to a GCP project service account → Atlas API key rotation becomes unnecessary

**Cloud Build example:**
```yaml
# cloudbuild.yaml
steps:
  - name: 'hashicorp/terraform:1.9'
    secretEnv: ['ATLAS_PUBLIC_KEY', 'ATLAS_PRIVATE_KEY']
    script: |
      terraform init && terraform apply -auto-approve
availableSecrets:
  secretManager:
    - versionName: projects/$PROJECT_ID/secrets/atlas-public-key/versions/latest
      env: 'ATLAS_PUBLIC_KEY'
    - versionName: projects/$PROJECT_ID/secrets/atlas-private-key/versions/latest
      env: 'ATLAS_PRIVATE_KEY'
```

### 2.3 Google Workspace / Google Cloud Directory Sync → Atlas Federated Login

For human Atlas console login with Google Workspace as the Identity Provider:
- Use Atlas Federation Management → Add Identity Provider → SAML
- Google Workspace acts as SAML 2.0 IdP for Atlas Organization
- GCDS (Google Cloud Directory Sync) can provision groups to Atlas organization roles
- SSO users access Atlas console without a separate MongoDB password

**Not to confuse with Workload Identity Federation:** Google Workspace SSO is for human operators; Workload Identity Federation is for automated workloads/applications.

### 2.4 IAM for Atlas Admin API in Terraform (Recommended Pattern)

```hcl
# Create service account for Terraform
resource "google_service_account" "terraform_atlas" {
  account_id   = "terraform-atlas-sa"
  display_name = "Terraform Atlas Admin SA"
}

# Store Atlas API keys in Secret Manager, grant SA access
resource "google_secret_manager_secret_iam_member" "atlas_key_access" {
  secret_id = google_secret_manager_secret.atlas_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.terraform_atlas.email}"
}
```

---

## 3. GCP KMS and Encryption at Rest

### 3.1 Architecture: Envelope Encryption

Atlas implements three-layer envelope encryption with Cloud KMS:

```
Customer-Managed Key (CMK) in Cloud KMS
  └─ encrypts → MongoDB Master Key (per replica set node, stored locally encrypted)
                  └─ encrypts → Per-Database Encryption Keys (via WiredTiger)
                                  └─ encrypts → cluster data files and snapshots
```

CMK never leaves Cloud KMS; Atlas only calls Encrypt/Decrypt APIs. Atlas stores the encrypted MongoDB Master Key locally on each node.

### 3.2 Required Service Account Permissions

Atlas uses an **Atlas-owned GCP service account** (displayed in Atlas UI when you enable GCP KMS). Grant it two IAM roles:

```bash
# Allow encrypt/decrypt operations
gcloud kms keys add-iam-policy-binding KEY_NAME \
  --location=LOCATION \
  --keyring=KEYRING_NAME \
  --member="serviceAccount:ATLAS_OWNED_SA@gcpproject.iam.gserviceaccount.com" \
  --role="roles/cloudkms.cryptoKeyEncrypterDecrypter"

# Allow key version lookup
gcloud kms keys add-iam-policy-binding KEY_NAME \
  --location=LOCATION \
  --keyring=KEYRING_NAME \
  --member="serviceAccount:ATLAS_OWNED_SA@gcpproject.iam.gserviceaccount.com" \
  --role="roles/cloudkms.viewer"
```

**Note:** As of 2024+, Atlas prefers role-based auth (Atlas-managed SA) over customer-provided static service account JSON keys. Static key auth is deprecated — do not use `service_account_key` in new setups.

### 3.3 Key Version Resource ID Format

The Atlas UI and API require the **fully-qualified** key version resource name:
```
projects/MY-PROJECT/locations/us-east4/keyRings/my-keyring/cryptoKeys/my-key/cryptoKeyVersions/1
```

Obtain it:
```bash
gcloud kms keys versions list \
  --key=my-key \
  --keyring=my-keyring \
  --location=us-east4 \
  --filter="state=ENABLED"
```

### 3.4 Key Rotation Workflow

**Atlas MongoDB Master Keys (Atlas-managed):**
- Rotated automatically at least every 90 days
- Happens during the cluster's maintenance window
- Rolling basis — no data rewrite, no downtime

**Customer-Managed Key (CMK) rotation (your responsibility):**
- Atlas creates a 90-day rotation reminder alert by default
- Options: Manual rotation or automatic GCP KMS rotation (default period: ~365 days)
- If you configure auto-rotation in Cloud KMS, update the Atlas rotation alert to >365 days to avoid noise

**Manual CMK rotation procedure:**
1. In Cloud KMS, create a new key version (or let auto-rotation create one)
2. In Atlas: Project → Advanced → Security → Encryption at Rest → Edit
3. Enter the new **Key Version Resource ID** (new version number)
4. Click **Update Credentials** — Atlas re-wraps master keys on each node (rolling, no downtime)
5. **Do not disable/delete the old key version** until all snapshots referencing it are expired

### 3.5 Cloud HSM-Backed Keys

Cloud KMS supports HSM-backed keys (`protection_level = HSM`). Atlas treats these identically to software-backed keys — the KMS API interface is the same. Use HSM keys for regulated workloads requiring FIPS 140-2 Level 3 protection:

```bash
gcloud kms keys create my-hsm-key \
  --keyring=my-keyring \
  --location=us-east4 \
  --purpose=encryption \
  --protection-level=hsm
```

### 3.6 KMS Unavailability Behavior (Failsafe)

If Atlas loses access to the CMK (key revoked, service account permissions removed, KMS API unavailable):
- **Atlas shuts down all cluster nodes** — data becomes completely inaccessible
- No read-only fallback mode exists
- Restoring CMK access → cluster nodes restart automatically

**Two distinct alerts to configure:**
- `ENCRYPTION_KEY_NEEDS_ROTATION` — fires when the 90-day rotation reminder is due; CMK is still valid, no service impact. Rotate promptly.
- `ENCRYPTION_KEY_INVALID` — fires when Atlas cannot access the CMK at all; **cluster shutdown is imminent or already happening**. Treat as P1.

**Prevention checklist:**
- Never delete/disable a key version while it's referenced by Atlas
- Use Cloud KMS key rotation (not version deletion) to cycle keys
- Set up both alerts above with PagerDuty/Slack escalation
- Test key restoration in staging before enforcing key policies

### 3.7 Terraform: GCP KMS + Atlas Encryption at Rest

```hcl
# Create Cloud KMS key
resource "google_kms_key_ring" "atlas" {
  name     = "atlas-keyring"
  location = "us-east4"
}

resource "google_kms_crypto_key" "atlas" {
  name            = "atlas-cmk"
  key_ring        = google_kms_key_ring.atlas.id
  rotation_period = "7776000s"  # 90 days
}

# Grant Atlas-owned service account access
# Note: atlas_sa_email comes from Atlas UI after enabling GCP KMS on the project
resource "google_kms_crypto_key_iam_member" "atlas_encrypter" {
  crypto_key_id = google_kms_crypto_key.atlas.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${var.atlas_gcp_service_account_email}"
}

resource "google_kms_crypto_key_iam_member" "atlas_viewer" {
  crypto_key_id = google_kms_crypto_key.atlas.id
  role          = "roles/cloudkms.viewer"
  member        = "serviceAccount:${var.atlas_gcp_service_account_email}"
}

# Configure Atlas to use this key (role-based auth)
resource "mongodbatlas_encryption_at_rest" "main" {
  project_id = var.atlas_project_id

  google_cloud_kms_config {
    enabled                 = true
    key_version_resource_id = "${google_kms_crypto_key.atlas.id}/cryptoKeyVersions/1"
    # NOTE: hardcodes version /1 — update to the active version after each key rotation.
    # Static service_account_key is DEPRECATED. Role-based auth is automatic:
    # once Atlas UI shows the Atlas-owned SA email and you have granted IAM above,
    # no additional field is needed — Atlas authenticates via its managed SA.
  }
}
```

---

## 4. GCP Native Service Integrations

### 4.1 GKE + Atlas Kubernetes Operator (AKO)

AKO lets you manage Atlas resources (clusters, projects, users, private endpoints) as Kubernetes custom resources. On GKE, combine AKO with Workload Identity to avoid static credentials.

**Install AKO via Helm:**
```bash
helm repo add mongodb https://mongodb.github.io/helm-charts
helm install atlas-operator mongodb/atlas-operator \
  --namespace=atlas-operator \
  --create-namespace \
  --set "watchedNamespaces=my-app"
```

**Core CRD types:**
- `AtlasProject` — maps to an Atlas project (holds API credentials reference)
- `AtlasDeployment` — creates/manages a cluster within the project
- `AtlasDatabaseUser` — manages database users
- `AtlasNetworkPeering` / `AtlasPrivateEndpoint` — network config
- `AtlasFederatedAuth` — federated authentication config

**AtlasProject CRD example (with Secret reference for API keys):**
```yaml
apiVersion: atlas.mongodb.com/v1
kind: AtlasProject
metadata:
  name: my-gcp-project
  namespace: my-app
spec:
  name: my-gcp-atlas-project
  connectionSecretRef:
    name: atlas-api-keys   # Kubernetes Secret with publicKey/privateKey
```

**AtlasDeployment CRD example:**
```yaml
apiVersion: atlas.mongodb.com/v1
kind: AtlasDeployment
metadata:
  name: my-cluster
  namespace: my-app
spec:
  projectRef:
    name: my-gcp-project
  deploymentSpec:
    name: prod-cluster
    clusterType: REPLICASET
    providerSettings:
      backingProviderName: GCP
      instanceSizeName: M30
      regionName: CENTRAL_US
    autoScaling:
      diskGB:
        enabled: true
      compute:
        enabled: true
        scaleDownEnabled: true
        minInstanceSize: M30
        maxInstanceSize: M60
```

**GKE Workload Identity for AKO:** Store Atlas API keys in Google Secret Manager; mount them into the AKO pod via External Secrets Operator or Workload Identity-aware sidecar. The AKO operator itself does not yet natively use Workload Identity Federation for its Atlas API calls — it reads a Kubernetes Secret containing the API key pair.

**Deletion protection (AKO v2.0+):** Deleting an AKO CRD no longer automatically deletes the Atlas resource. Set `--object-deletion-protection=false` only if you want the old behavior.

### 4.2 Cloud Run + Atlas: Connection Pooling Patterns

Cloud Run scales to zero and cold-starts when traffic arrives. Each cold start creates a new process and a new `MongoClient` if not handled carefully.

**The correct pattern — module-level client caching:**
```javascript
const { MongoClient } = require('mongodb');

// Declare OUTSIDE the request handler — reused across warm invocations
let cachedClient = null;

async function getMongoClient() {
  if (!cachedClient) {
    cachedClient = new MongoClient(process.env.MONGODB_URI, {
      maxPoolSize: 5,          // Low per-instance pool (Cloud Run scales horizontally)
      maxIdleTimeMS: 60000,    // Close idle connections after 1 minute
      serverSelectionTimeoutMS: 5000,
    });
    await cachedClient.connect();
  }
  return cachedClient;
}

exports.handler = async (req, res) => {
  const client = await getMongoClient();
  // ... use client
};
```

**Cloud Run connection tuning:**
- `maxPoolSize: 5` — keep per-instance pool small; Cloud Run spins many instances under load
- `maxIdleTimeMS: 60000` — prevents "connection reset" errors from Atlas idle timeout (Atlas server-side default is 30 minutes, but Cloud Run instances are recycled sooner; closing idle connections proactively avoids stale-socket errors on warm restart)
- `srvMaxHosts: 3` — for sharded clusters, avoid connecting to all mongos instances
- Increase Cloud Run **concurrency** (default 80) so one warm instance handles more concurrent requests with one pool

**Serverless VPC Access Connector:** Required for Cloud Run to reach Atlas via PSC (private IP). Create a connector in the same region as the Cloud Run service:
```bash
gcloud compute networks vpc-access connectors create atlas-connector \
  --region=us-central1 \
  --network=consumer-vpc \
  --range=10.8.0.0/28
```
Then in Cloud Run: set `--vpc-connector=atlas-connector --vpc-egress=private-ranges-only`

### 4.3 Cloud Functions (Gen 2) + Atlas

Cloud Functions Gen 2 runs on Cloud Run infrastructure — the same pooling patterns apply. Key differences:
- Gen 2 supports **multiple concurrent invocations per instance** — critical for connection reuse
- Set `maxInstances` and adjust `concurrency` to control total connection count
- Prefer Gen 2 over Gen 1 for Atlas workloads (Gen 1 is single-threaded per instance)

```python
# Python example with module-level client
from pymongo import MongoClient
import os
import functions_framework

_client = None

def get_client():
    global _client
    if _client is None:
        _client = MongoClient(
            os.environ['MONGODB_URI'],
            maxPoolSize=5,
            maxIdleTimeMS=60000
        )
    return _client

@functions_framework.http
def handler(request):
    client = get_client()
    db = client.mydb
    # ...
```

### 4.4 Vertex AI + Atlas Vector Search

**Architecture: RAG with Vertex AI Embeddings → Atlas Vector Search**

```
[Source Docs]
     ↓
[Vertex AI Embeddings API (text-embedding-004 or text-multilingual-embedding-002)]
     ↓ 768-dim vectors
[MongoDB Atlas Collection with vector field]
     ↓  (Atlas Vector Search Index, type: vectorSearch, dimensions: 768)
[User Query] → Vertex AI embed query → Atlas $vectorSearch → top-k docs
     ↓
[Vertex AI Gemini API] + retrieved docs → response
```

**Vector Search index for Vertex AI embeddings:**
```json
{
  "name": "vector_index",
  "type": "vectorSearch",
  "definition": {
    "fields": [
      {
        "type": "vector",
        "path": "embedding",
        "numDimensions": 768,
        "similarity": "cosine"
      }
    ]
  }
}
```

**Embedding and insert example (Python):**
```python
from vertexai.language_models import TextEmbeddingModel
from pymongo import MongoClient

model = TextEmbeddingModel.from_pretrained("text-embedding-004")

def embed_and_store(texts, collection):
    embeddings = model.get_embeddings(texts)
    docs = [
        {"text": t, "embedding": e.values}
        for t, e in zip(texts, embeddings)
    ]
    collection.insert_many(docs)
```

**Atlas Vector Search query:**
```python
pipeline = [
  {
    "$vectorSearch": {
      "index": "vector_index",
      "path": "embedding",
      "queryVector": query_embedding,
      "numCandidates": 100,
      "limit": 5
    }
  }
]
results = list(collection.aggregate(pipeline))
```

**Vertex AI integrations available (2025):**
- **Vertex AI Agent Engine**: Build agents that call Atlas Vector Search as a tool
- **Vertex AI Extensions**: Natural language → MongoDB queries
- **Gemini Code Assist**: MongoDB documentation and code snippets available in IDE (MongoDB is a launch partner)
- **Firebase Extension for Atlas**: Firebase ↔ Atlas real-time sync and vector database support

### 4.5 BigQuery + Atlas: Dataflow Templates and Data Federation

**Three Dataflow templates (Google-provided, Apache Beam-based):**

| Template | Type | Direction |
|---|---|---|
| MongoDB to BigQuery | Batch | Atlas → BigQuery |
| BigQuery to MongoDB | Batch | BigQuery → Atlas |
| MongoDB Change Stream to BigQuery | Streaming CDC | Atlas → BigQuery (real-time) |

**Streaming CDC template — how it works:**
1. Atlas Change Stream → Pub/Sub topic (using Atlas Triggers or Atlas Stream Processing `$emit`)
2. Dataflow job subscribes to Pub/Sub, transforms, writes to BigQuery
3. BigQuery table auto-created with JSON-typed columns (native JSON support, GA 2025)

**Datastream for CDC from MongoDB → BigQuery:**
Google Cloud Datastream can directly connect to MongoDB Atlas as a source and replicate changes to BigQuery or Cloud Storage in near-real-time — without requiring Pub/Sub as an intermediate layer.

**Atlas Data Federation on GCS:**
```javascript
// Atlas Data Federation federated database config
{
  "stores": [{
    "name": "gcs-archive",
    "provider": "gcs",
    "bucket": "my-archive-bucket",
    "prefix": "/archive"
  }],
  "databases": [{
    "name": "archive",
    "collections": [{
      "name": "events",
      "dataSources": [{"storeName": "gcs-archive", "path": "/{year}/{month}/*.json"}]
    }]
  }]
}
```

Supports querying Parquet, JSON, CSV, BSON files on GCS using standard MQL/aggregation pipeline.

### 4.6 Atlas Stream Processing + Google Cloud Pub/Sub

Atlas Stream Processing (ASP) can publish processed change stream events directly to GCP Pub/Sub topics with no intermediate infrastructure.

**Setup:**
1. In Atlas → Project Integrations → GCP Integration: note the **Atlas Service Account ID**
2. Grant IAM roles to Atlas SA:
```bash
gcloud projects add-iam-policy-binding GCP_PROJECT_ID \
  --member="serviceAccount:ATLAS_SERVICE_ACCOUNT_ID" \
  --role="roles/pubsub.viewer"

gcloud projects add-iam-policy-binding GCP_PROJECT_ID \
  --member="serviceAccount:ATLAS_SERVICE_ACCOUNT_ID" \
  --role="roles/pubsub.publisher"
```

3. Add Pub/Sub connection in Atlas Stream Processing Connection Registry
4. Use `$emit` stage in stream processor:

```javascript
{
  "$emit": {
    "connectionName": "my-pubsub-conn",
    "topic": "atlas-events",
    "projectId": "my-gcp-project",
    "region": "us-central1",
    "orderingKey": "$customerId",
    "attributes": {
      "eventType": "$type",
      "source": "mongodb-atlas"
    },
    "config": {
      "outputFormat": "relaxedJson"
    }
  }
}
```

**Use cases:** Fan-out to Cloud Functions / Cloud Run / Dataflow on data change events; AI agents reacting to inventory changes; operational event propagation.

**PSC support:** Atlas Stream Processing Pub/Sub integration supports Private Service Connect for private connectivity to Pub/Sub.

### 4.7 Looker / Looker Studio + Atlas BI Connector

Use the **MongoDB Atlas BI Connector** to expose Atlas collections as SQL-queryable virtual tables:
1. Enable BI Connector in Atlas cluster settings (M10+)
2. Connect Looker (or Looker Studio) using MySQL wire protocol
3. BI Connector translates SQL → MongoDB aggregation pipeline
4. Suitable for BI/reporting; not recommended for high-throughput transactional queries

---

## 5. GCP Monitoring and Observability

### 5.1 Atlas Metrics to Cloud Monitoring

Atlas does not natively push metrics to Cloud Monitoring (Ops Suite). Standard integration path:

**Option A: Third-party (Datadog, Grafana Cloud)**
- Use Atlas Integrations → Datadog or Grafana
- Datadog agent available on GCE/GKE can bridge to Cloud Monitoring via metric forwarding

**Option B: Pub/Sub + Cloud Monitoring custom metrics**
1. Configure Atlas Alerts to trigger webhooks
2. Webhook → Cloud Functions → write custom metric to Cloud Monitoring API
3. Or: Atlas Stream Processing → Pub/Sub → Cloud Functions → `metricDescriptors.create` + `timeSeries.create`

**Option C: Atlas + OpenTelemetry**
MongoDB drivers (Node, Java, Python, Go) support OTEL tracing. Configure OTLP exporter to send to Cloud Trace:
```javascript
const { trace } = require('@opentelemetry/api');
const { TraceExporter } = require('@google-cloud/opentelemetry-cloud-trace-exporter');
// Configure OTEL with TraceExporter → sends MongoDB spans to Cloud Trace
```

### 5.2 Atlas Audit Logs to Cloud Logging

Atlas audit logs can be forwarded to your GCS bucket (Atlas Audit Log Export → GCS). To ingest those files into Cloud Logging, use an Eventarc trigger on the GCS bucket to invoke a Cloud Function that calls the Cloud Logging write API:

```bash
# Create a log bucket destination for parsed Atlas audit events
gcloud logging buckets create atlas-audit-logs \
  --location=global \
  --retention-days=90

# Eventarc trigger: fires when Atlas drops a new audit log file into GCS
gcloud eventarc triggers create atlas-audit-ingest \
  --location=us-central1 \
  --destination-run-service=atlas-audit-importer \
  --destination-run-region=us-central1 \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=my-atlas-audit-bucket" \
  --service-account=eventarc-sa@PROJECT.iam.gserviceaccount.com
```

The `atlas-audit-importer` Cloud Run service reads the GCS object, parses BSON/JSON audit records, and writes them as structured log entries via the Cloud Logging API.

### 5.3 Atlas Alerts → Pub/Sub → Cloud Functions Escalation

```
Atlas Alert (e.g., CONNECTIONS_MAX) 
  → Webhook to Cloud Functions endpoint 
    → Publish to Pub/Sub topic 
      → PagerDuty / Slack notification
      → Auto-remediation: scale cluster (call Atlas API to increase tier)
```

Atlas webhook payload is JSON; Cloud Functions can parse and route to any GCP service.

---

## 6. GCP Billing and Marketplace

### 6.1 GCP Marketplace Purchase Flow

1. In GCP Console: **Marketplace** → Search "MongoDB Atlas" → "MongoDB Atlas (Pay as You Go)"
2. Select your **GCP Billing Account** → Accept terms → Subscribe
3. Click **Register with MongoDB** → redirected to Atlas
4. Select which **Atlas Organization** to link to this GCP Billing Account
5. Wait for sync (~minutes) → Atlas Payment Method field shows "GCP Marketplace Subscription"

**Result:** All Atlas cluster charges in that org appear on your GCP invoice as Marketplace line items.

### 6.2 Billing Architecture

- **Invoice consolidation:** Atlas usage charges appear on GCP invoice alongside other GCP services
- **Annual but billed monthly:** GCP Marketplace Atlas packages are annual commitments billed monthly based on actual consumption
- **Cannot mix billing:** Once linked to GCP Marketplace, the Atlas org Payment Method field is locked; must unlink via GCP to switch back to direct billing
- **Multi-project:** One GCP Billing Account → one Atlas org. Multiple GCP projects under the same billing account all funnel to the same Atlas org billing

### 6.3 EDP / Committed Use and Startup Credits

**GCP Enterprise Discount Program (EDP):**
- Atlas Marketplace charges **can count toward your GCP EDP committed spend** — confirm with your Google Cloud account team, as this varies by EDP contract terms
- Not all Marketplace products are EDP-eligible; MongoDB Atlas has been qualified as EDP-eligible for enterprise agreements

**Google Cloud Startup / Startup School credits:**
- Google for Startups Cloud Program credits apply to GCP services including Marketplace purchases
- MongoDB Atlas on GCP Marketplace charges are typically covered by startup credit grants
- Stack with MongoDB for Startups program for additional Atlas credits
- Contact: mdb-gcp-marketplace@mongodb.com for private offers and startup credit stacking guidance

**Comparing Marketplace vs direct billing:**
| Factor | GCP Marketplace | Direct MongoDB billing |
|---|---|---|
| Invoice | Single GCP invoice | Separate MongoDB invoice |
| EDP credit applicability | Potentially yes (verify with GCP AM) | No |
| Startup credits | GCP startup credits may apply | MongoDB for Startups credits only |
| Private offers | Available via MongoDB account team | Standard pricing |
| Flexibility | Limited (locked billing method) | Full flexibility |

### 6.4 Marketplace Co-Sell and Joint GTM

MongoDB's 6-year streak as **Google Cloud Partner of the Year for Data & Analytics - Marketplace** translates to practical billing benefits:
- Marketplace listing is actively maintained — new Atlas features appear in Marketplace quickly
- Co-sell motions mean Google Cloud AEs actively recommend Atlas, often bundling Marketplace subscription setup into GCP account planning
- Private offers negotiated jointly by MongoDB and Google Cloud AMs can yield custom pricing tiers not available on the public Marketplace listing
- Contact mdb-gcp-marketplace@mongodb.com to initiate a private offer discussion

See Section 10 for the full partnership program details including Partner of the Year recognition, GDC, and AI/ML partnerships.

---

## 7. GCP Regions and Atlas Region Mapping

All GCP regions supported by MongoDB Atlas with their Atlas API/Terraform identifiers:

### Americas

| GCP Region | Location | Atlas Region Identifier | Free | Flex | M10+ |
|---|---|---|---|---|---|
| `us-central1` | Iowa, USA | `CENTRAL_US` | ✓ | ✓ | ✓ |
| `us-east1` | South Carolina, USA | `EASTERN_US` | ✓ | ✓ | ✓ |
| `us-east4` | N. Virginia, USA | `US_EAST_4` | ✓ | ✓ | ✓ |
| `us-east5` | Columbus, OH, USA | `US_EAST_5` | ✓ | ✓ | ✓ |
| `us-south1` | Dallas, TX, USA | `US_SOUTH_1` | ✓ | ✓ | ✓ |
| `us-west1` | Oregon, USA | `WESTERN_US` | ✓ | ✓ | ✓ |
| `us-west2` | Los Angeles, CA, USA | `US_WEST_2` | ✓ | ✓ | ✓ |
| `us-west3` | Salt Lake City, UT, USA | `US_WEST_3` | ✓ | ✓ | ✓ |
| `us-west4` | Las Vegas, NV, USA | `US_WEST_4` | ✓ | ✓ | ✓ |
| `northamerica-northeast1` | Montreal, Canada | `NORTH_AMERICA_NORTHEAST_1` | ✓ | ✓ | ✓ |
| `northamerica-northeast2` | Toronto, Canada | `NORTH_AMERICA_NORTHEAST_2` | ✓ | ✓ | ✓ |
| `northamerica-south1` | Querétaro, Mexico | `NORTH_AMERICA_SOUTH_1` | — | — | ✓ |
| `southamerica-east1` | Sao Paulo, Brazil | `SOUTH_AMERICA_EAST_1` | — | — | ✓ |
| `southamerica-west1` | Santiago, Chile | `SOUTH_AMERICA_WEST_1` | — | — | ✓ |

### Europe

| GCP Region | Location | Atlas Region Identifier | Free | Flex | M10+ |
|---|---|---|---|---|---|
| `europe-west1` | Belgium | `WESTERN_EUROPE` | ✓ | ✓ | ✓ |
| `europe-north1` | Finland | `EUROPE_NORTH_1` | ✓ | ✓ | ✓ |
| `europe-west2` | London, UK | `EUROPE_WEST_2` | ✓ | ✓ | ✓ |
| `europe-west3` | Frankfurt, Germany | `EUROPE_WEST_3` | — | — | ✓ |
| `europe-west4` | Netherlands | `EUROPE_WEST_4` | ✓ | ✓ | ✓ |
| `europe-west6` | Zurich, Switzerland | `EUROPE_WEST_6` | ✓ | ✓ | ✓ |
| `europe-west8` | Milan, Italy | `EUROPE_WEST_8` | — | — | ✓ |
| `europe-west9` | Paris, France | `EUROPE_WEST_9` | — | — | ✓ |
| `europe-west10` | Berlin, Germany | `EUROPE_WEST_10` | ✓ | ✓ | ✓ |
| `europe-west12` | Turin, Italy | `EUROPE_WEST_12` | ✓ | ✓ | ✓ |
| `europe-central2` | Warsaw, Poland | `EUROPE_CENTRAL_2` | ✓ | ✓ | ✓ |
| `europe-southwest1` | Madrid, Spain | `EUROPE_SOUTHWEST_1` | — | — | ✓ |

### Asia Pacific

| GCP Region | Location | Atlas Region Identifier | Free | Flex | M10+ |
|---|---|---|---|---|---|
| `asia-east1` | Taiwan | `EASTERN_ASIA_PACIFIC` | ✓ | ✓ | ✓ |
| `asia-east2` | Hong Kong | `ASIA_EAST_2` | ✓ | ✓ | ✓ |
| `asia-northeast1` | Tokyo, Japan | `NORTHEASTERN_ASIA_PACIFIC` | — | — | ✓ |
| `asia-northeast2` | Osaka, Japan | `ASIA_NORTHEAST_2` | ✓ | ✓ | ✓ |
| `asia-northeast3` | Seoul, Korea | `ASIA_NORTHEAST_3` | ✓ | ✓ | ✓ |
| `asia-southeast1` | Singapore | `SOUTHEASTERN_ASIA_PACIFIC` | ✓ | ✓ | ✓ |
| `asia-southeast2` | Jakarta, Indonesia | `ASIA_SOUTHEAST_2` | ✓ | ✓ | ✓ |
| `asia-south1` | Mumbai, India | `ASIA_SOUTH_1` | ✓ | ✓ | ✓ |
| `asia-south2` | Delhi, India | `ASIA_SOUTH_2` | ✓ | ✓ | ✓ |
| `australia-southeast1` | Sydney, Australia | `AUSTRALIA_SOUTHEAST_1` | — | — | ✓ |
| `australia-southeast2` | Melbourne, Australia | `AUSTRALIA_SOUTHEAST_2` | ✓ | ✓ | ✓ |

### Middle East and Africa

| GCP Region | Location | Atlas Region Identifier | Free | Flex | M10+ |
|---|---|---|---|---|---|
| `me-west1` | Tel Aviv, Israel | `MIDDLE_EAST_WEST_1` | ✓ | ✓ | ✓ |
| `me-central1` | Doha, Qatar | `MIDDLE_EAST_CENTRAL_1` | ✓ | ✓ | ✓ |
| `me-central2` | Dammam, Saudi Arabia | `MIDDLE_EAST_CENTRAL_2` | ✓ | ✓ | ✓ |
| `africa-south1` | Johannesburg, South Africa | `AFRICA_SOUTH_1` | ✓ | ✓ | ✓ |

### Recommended HA Region Pairs (GCP)

| Primary | Secondary | Notes |
|---|---|---|
| `us-central1` (`CENTRAL_US`) | `us-east4` (`US_EAST_4`) | US-East/Central recommended pair |
| `us-east1` (`EASTERN_US`) | `us-east4` (`US_EAST_4`) | Both US-East zones for low latency |
| `europe-west1` (`WESTERN_EUROPE`) | `europe-west4` (`EUROPE_WEST_4`) | Belgium ↔ Netherlands, ~5ms |
| `europe-west2` (`EUROPE_WEST_2`) | `europe-west1` (`WESTERN_EUROPE`) | UK ↔ Belgium |
| `asia-southeast1` (`SOUTHEASTERN_ASIA_PACIFIC`) | `asia-northeast1` (`NORTHEASTERN_ASIA_PACIFIC`) | Singapore ↔ Tokyo |
| `asia-south1` (`ASIA_SOUTH_1`) | `asia-south2` (`ASIA_SOUTH_2`) | Mumbai ↔ Delhi for India HA |

**Terraform region identifier convention:** Use Atlas region identifier values (e.g., `CENTRAL_US`), NOT GCP region names (e.g., `us-central1`), in all `mongodbatlas_*` resources.

---

## 8. IaC Patterns: Terraform

### 8.1 Provider Setup

```hcl
terraform {
  required_providers {
    mongodbatlas = {
      source  = "mongodb/mongodbatlas"
      version = "~> 2.12"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "mongodbatlas" {
  public_key  = var.atlas_public_key
  private_key = var.atlas_private_key
}

provider "google" {
  project = var.gcp_project
  region  = var.gcp_region
}
```

### 8.2 Atlas Cluster on GCP

```hcl
resource "mongodbatlas_advanced_cluster" "main" {
  project_id   = var.atlas_project_id
  name         = "prod-cluster"
  cluster_type = "REPLICASET"

  replication_specs {
    region_configs {
      provider_name = "GCP"
      region_name   = "CENTRAL_US"       # Atlas region identifier
      priority      = 7

      electable_specs {
        instance_size = "M30"
        node_count    = 3
      }
    }
  }
}
```

### 8.3 PSC Private Endpoint (Port-Mapped)

```hcl
# Step 1: Create Atlas endpoint service
resource "mongodbatlas_privatelink_endpoint" "gcp" {
  project_id    = var.atlas_project_id
  provider_name = "GCP"
  region        = "CENTRAL_US"
}

# Step 2: Reserve GCP internal IPs
resource "google_compute_address" "psc" {
  name         = "atlas-psc-ip"
  region       = var.gcp_region
  subnetwork   = google_compute_subnetwork.psc.id
  address_type = "INTERNAL"
}

# Step 3: GCP forwarding rule → Atlas service attachment
resource "google_compute_forwarding_rule" "atlas_psc" {
  name                  = "atlas-psc-fw"
  region                = var.gcp_region
  project               = var.gcp_project
  network               = google_compute_network.main.id
  ip_address            = google_compute_address.psc.id
  target                = mongodbatlas_privatelink_endpoint.gcp.service_attachment_names[0]
  load_balancing_scheme = ""

  lifecycle {
    # Required: forwarding rules can't be updated, only replaced
    replace_triggered_by = [mongodbatlas_privatelink_endpoint.gcp.service_attachment_names]
  }
}

# Step 4: Register endpoint with Atlas
resource "mongodbatlas_privatelink_endpoint_service" "gcp" {
  project_id          = var.atlas_project_id
  private_link_id     = mongodbatlas_privatelink_endpoint.gcp.id
  provider_name       = "GCP"
  endpoint_service_id = google_compute_forwarding_rule.atlas_psc.name

  endpoints {
    ip_address    = google_compute_address.psc.address
    endpoint_name = google_compute_forwarding_rule.atlas_psc.name
  }
}
```

### 8.4 Cloud DNS Private Zone for Atlas

```hcl
resource "google_dns_managed_zone" "atlas" {
  name        = "atlas-private"
  dns_name    = "mongodb.net."
  description = "Atlas PSC private DNS resolution"
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = google_compute_network.main.id
    }
  }
}

resource "google_dns_record_set" "atlas_node" {
  name         = "pl-0-us-central1-gcp.${var.atlas_cluster_srv_suffix}.mongodb.net."
  type         = "A"
  ttl          = 300
  managed_zone = google_dns_managed_zone.atlas.name
  rrdatas      = [google_compute_address.psc.address]
}
```

### 8.5 GCP KMS + Atlas Encryption at Rest (Role-Based Auth)

See Section 3.7 for the complete Terraform example. Key points:
- Use `mongodbatlas_encryption_at_rest` resource with `google_cloud_kms_config` block
- Obtain `atlas_gcp_service_account_email` from Atlas UI after enabling GCP KMS on the project
- Do NOT use `service_account_key` (deprecated) — use role-based auth (Atlas-managed SA)

### 8.6 Workload Identity Federation via Terraform

```hcl
# Configure Atlas OIDC identity provider (org-level)
resource "mongodbatlas_identity_provider" "gcp" {
  federation_settings_id = var.atlas_federation_settings_id
  name                   = "gcp-workload-idp"
  issuer_uri             = "https://accounts.google.com"
  client_id              = var.atlas_oidc_audience  # custom audience value
  request_type           = "WORKLOAD"
  idp_type               = "WORKLOAD"
  user_claim             = "sub"
}
```

---

## 9. GCP-Specific Troubleshooting Playbook

### 9.1 PSC Endpoint Stuck in "Waiting for User" or "Pending" State

**Symptom:** Atlas endpoint service shows "Waiting for User" for >30 min.

**Diagnosis:**
1. Verify forwarding rule exists in the correct GCP project and region
2. Check forwarding rule target matches Atlas service attachment: `gcloud compute forwarding-rules describe atlas-psc-fw --region=us-central1`
3. Confirm GCP forwarding rule is in `ACTIVE` state (not `DELETING`)
4. Verify the endpoint name submitted to Atlas exactly matches `google_compute_forwarding_rule.name` (not IP address)

**Resolution:**
- Delete the Atlas endpoint, delete the GCP forwarding rule, and recreate both
- Ensure you're using the forwarding rule **name** (not IP) as `endpoint_service_id` in `mongodbatlas_privatelink_endpoint_service`

### 9.2 DNS / SRV Resolution Failures

**Symptom:** `MongoServerSelectionError: getaddrinfo ENOTFOUND cluster1-psc-0.xxxxx.mongodb.net`

**Diagnosis chain:**
```bash
# 1. Check SRV record resolves (from within GCP VPC)
nslookup -type=SRV _mongodb._tcp.cluster1-psc-0.xxxxx.mongodb.net

# 2. Check that A record resolves to PSC forwarding rule IP (not public)
nslookup pl-0-us-central1-gcp.xxxxx.mongodb.net

# 3. Verify firewall rule allows TCP 1024-65535 egress
gcloud compute firewall-rules list --filter="direction=EGRESS"

# 4. Test direct TCP connectivity
nc -zv pl-0-us-central1-gcp.xxxxx.mongodb.net 1024
```

**Common causes:**
- Cloud DNS private zone overrides the Atlas `*.mongodb.net` zone incorrectly (wrong A record IP or wrong hostname)
- GKE node uses custom CoreDNS that doesn't forward `.mongodb.net` queries to the VPC resolver
- Firewall egress rule missing (outbound 1024-65535 must be allowed to PSC subnet)
- Multi-region endpoint: connection string uses index 1+ instead of index 0 after regions were added

**Fix for GKE CoreDNS:**
Add a forward stub zone to CoreDNS ConfigMap:
```yaml
mongodb.net:53 {
    forward . /etc/resolv.conf
}
```

### 9.3 GCP Forwarding Rule Quota Exhaustion (Legacy PSC)

**Symptom (legacy PSC only):** `Error 403: Quota 'FORWARDING_RULES' exceeded`

**Context:** Legacy PSC creates 50 forwarding rules per region. GCP default `FORWARDING_RULES` quota is 50/region for some projects.

**Resolution:**
1. Migrate to **port-mapped PSC** (single forwarding rule per region) — strongly recommended
2. Or: Request quota increase in GCP Console → IAM & Admin → Quotas → `FORWARDING_RULES`
3. Quota increase may take 24-48 hours; file 3-5 business days before needed

### 9.4 Cross-Project Shared VPC: PSC Not Accessible from Service Projects

**Symptom:** VMs in service projects cannot reach Atlas PSC endpoint defined in host project.

**Diagnosis:**
```bash
# Check if service project has compute.networkUser role on host VPC subnet
gcloud projects get-iam-policy HOST_PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.role=roles/compute.networkUser"
```

**Resolution:**
- Grant `roles/compute.networkUser` on the PSC subnet to service project's default service account or specific SAs
- Verify the PSC forwarding rule was created in the host project (not a service project)
- Check that the service project's VMs use the host VPC (not a local VPC)

### 9.5 Cloud Run Cold-Start Connection Exhaustion

**Symptom:** `MongoServerError: connection pool is full` or `MongoNetworkTimeoutError` during traffic spikes after a period of inactivity.

**Root cause:** Each cold-started Cloud Run instance opens new connections to Atlas. If many instances start simultaneously (e.g., sudden traffic burst after scale-to-zero), Atlas connection limits can be hit.

**Fixes:**
1. Set `maxPoolSize: 5` (not default 100) — each Cloud Run instance maintains a tiny pool
2. Set `maxIdleTimeMS: 60000` — close connections on quiet instances before they get recycled
3. Set minimum Cloud Run **min-instances: 1** (prevents scale-to-zero, keeps pool warm)
4. For extreme traffic: deploy a **connection proxy** (mongos or connection pooler) in Cloud Run sidecar or separate service
5. Use `srvMaxHosts: 3` for sharded clusters to limit per-instance connections

### 9.6 Cloud Build → Atlas API Authentication Failures

**Symptom:** Terraform apply fails in Cloud Build with `401 Unauthorized` from Atlas API.

**Common causes:**
- Atlas API key stored as plaintext environment variable (rotated or expired)
- Secret Manager secret version not yet accessible by Cloud Build SA

**Fix:**
```yaml
# cloudbuild.yaml — use availableSecrets block
availableSecrets:
  secretManager:
    - versionName: projects/$PROJECT_ID/secrets/atlas-public-key/versions/latest
      env: MONGODB_ATLAS_PUBLIC_KEY
    - versionName: projects/$PROJECT_ID/secrets/atlas-private-key/versions/latest
      env: MONGODB_ATLAS_PRIVATE_KEY
```
Ensure Cloud Build SA has `roles/secretmanager.secretAccessor` on the secrets.

### 9.7 GKE Pod Cannot Connect to Atlas PSC

**Symptom:** GKE pods get DNS resolution failures for Atlas hostnames; external GCE VMs in same VPC work fine.

**Root cause:** GKE uses node-local DNS cache (NodeLocal DNSCache) which may not forward `*.mongodb.net` queries to the VPC Cloud DNS resolver that can see the PSC endpoint.

**Fix:**
1. Check if NodeLocal DNSCache is enabled: `kubectl get ds -n kube-system node-local-dns`
2. If yes, add a forward rule in the NodeLocal DNSCache ConfigMap to forward `mongodb.net.` to the VPC resolver (`169.254.20.10` or kube-dns cluster IP)
3. Alternatively, use a Cloud DNS private zone (see Section 1.5) with A records pointing to the PSC IP — these are served by VPC resolver and work correctly with NodeLocal DNSCache

### 9.8 GCP KMS Access Revoked — Atlas Nodes Shutdown

**Symptom:** Atlas alerts fire `ENCRYPTION_KEY_NEEDS_ROTATION` or `ENCRYPTION_KEY_INVALID`; all cluster nodes stop accepting connections.

**Recovery:**
1. Verify KMS key version is enabled: `gcloud kms keys versions list ...`
2. Verify Atlas-owned service account still has `cloudkms.cryptoKeyEncrypterDecrypter` role
3. If permissions were removed, re-add them immediately
4. Wait for Atlas to detect key restoration (typically 5-15 minutes); nodes restart automatically
5. If key was deleted (unrecoverable): restore from Cloud Backup snapshot to a new cluster with a new KMS key configured

**Prevention:** Enable Cloud KMS key rotation alerts and Atlas `ENCRYPTION_KEY_INVALID` alert → PagerDuty/Slack escalation.

---

## 10. GCP Partnership Programs

### 10.1 Google Cloud Partner of the Year and Co-Sell

MongoDB has been named **Google Cloud Partner of the Year for Data & Analytics - Marketplace** for 6 consecutive years through 2025. Practical implications:
- Strong joint support escalation path — MongoDB and Google Cloud TAMs/SEs can collaborate on enterprise accounts
- Co-sell eligibility: MongoDB AEs can engage with Google Cloud Sales on joint opportunities
- Marketplace listing is actively maintained; new Atlas features appear in Marketplace quickly
- Private offer discussions: contact mdb-gcp-marketplace@mongodb.com

### 10.2 MongoDB for Startups + Google Cloud Startup Credits

- **MongoDB for Startups:** Apply at mongodb.com/startups for Atlas credits (up to $500/month for 12 months)
- **Google for Startups Cloud Program:** GCP credits ($0-$200K+ depending on stage) cover Marketplace charges including Atlas
- **Stacking:** Both programs can be active simultaneously — use GCP startup credits to cover Atlas Marketplace charges while MongoDB for Startups credits offset direct charges
- Contact: mdb-gcp-marketplace@mongodb.com for private offers tailored to startups

### 10.3 Google Cloud Ready — Regulated and Sovereignty Solutions

MongoDB Atlas earned the **Google Cloud Ready - Regulated and Sovereignty Solutions** badge (2025), indicating:
- Validated for regulated industry workloads (financial services, healthcare, government)
- Supports Google Cloud's sovereign cloud requirements
- Suitable for FedRAMP, HIPAA-eligible, PCI-DSS, ISO 27001 workloads on GCP

### 10.4 Google Cloud AI/ML Partner — Atlas Vector Search + Vertex AI

MongoDB is a launch partner for **Gemini Code Assist** (MongoDB docs and code snippets in IDE) and provides reference architectures for:
- **Vertex AI + Atlas Vector Search:** RAG pipeline patterns
- **Firebase + Atlas:** Real-time sync and vector database for Firebase apps
- **Vertex AI Agent Engine:** Atlas as a tool/memory store for autonomous agents

### 10.5 MongoDB Enterprise Advanced on Google Distributed Cloud (GDC)

For air-gapped, private cloud deployments:
- **MongoDB Enterprise Advanced** runs on **Google Distributed Cloud Hosted (GDCH)**
- GDCH is Google's air-gapped private cloud — no public internet required
- Deployed via the **MongoDB Enterprise Kubernetes Operator** (only supported method on GDC)
- Designed for public sector and regulated enterprises with strict data residency requirements
- MongoDB is a **preferred partner** for GDCH deployments

**Architecture:** GDC runs on Kubernetes; Operator manages replica sets, sharded clusters, backup.

### 10.6 Google Migration Center Integration

MongoDB Atlas is integrated into **Google Migration Center**:
- Cost assessments for on-premises MongoDB migrations to Atlas on GCP
- Migration plan generation with capacity recommendations
- Visibility into Community and Enterprise self-managed MongoDB deployments for migration sizing

### 10.7 Cloud Foundation Fabric (FAST) Integration

MongoDB Atlas is available within **Google Cloud Foundation Fabric FAST**:
- Pre-defined enterprise-grade Atlas deployment design
- Terraform reference implementation included
- Reduces time-to-production for Atlas-on-GCP enterprise landings

---

## Common Anti-Patterns

1. **Creating a new `MongoClient` per Cloud Run/Cloud Functions request** — causes connection exhaustion and cold-start amplification; always cache at module scope with `maxPoolSize: 5` and `maxIdleTimeMS: 60000`

2. **Using legacy PSC (50 forwarding rules per region)** past the April 30 2027 deprecation deadline — migrate to port-mapped PSC now to reduce resource footprint and future migration risk

3. **Using static GCP service account JSON in Terraform `mongodbatlas_encryption_at_rest`** — the `service_account_key` field is deprecated; use role-based auth (Atlas-managed SA with IAM binding) instead

4. **Deleting a Cloud KMS key version before rotating Atlas keys** — Atlas will shut down all cluster nodes when the CMK is inaccessible; old key versions must remain active until all snapshots referencing them expire

5. **Using Atlas region identifier format inconsistently** — the Terraform `mongodbatlas_*` resources require Atlas region names (`CENTRAL_US`) not GCP region names (`us-central1`); mixing these causes silent failures or cluster deployment in wrong regions

6. **Forgetting `--allow-psc-global-access` for cross-region access** — VMs in a different GCP region than the PSC forwarding rule cannot reach it without this flag; add it to the consumer-side forwarding rule

7. **Using VPC Peering for new Atlas deployments on GCP** — PSC is the current recommended approach; VPC peering extends the network trust boundary bidirectionally and has CIDR overlap restrictions

8. **Granting Atlas Pub/Sub SA `roles/pubsub.admin` instead of scoped roles** — grant only `roles/pubsub.viewer` + `roles/pubsub.publisher` (scoped to specific topics if possible) to follow least-privilege

9. **Setting `maxPoolSize` to default (100) on GKE pods** — when 100+ Atlas pod replicas each maintain 100 connections, Atlas connection limits are quickly hit; set `maxPoolSize: 5-10` for pod-based workloads

10. **Forgetting to update Cloud DNS private zone A records after Atlas endpoint rotation** — if PSC forwarding rule IP changes (e.g., endpoint recreation), manually created A records in Cloud DNS must be updated; prefer Atlas-managed private endpoint connection strings that use PSC hostnames directly

---

## References

- [MongoDB Atlas GCP Region Reference](https://www.mongodb.com/docs/atlas/reference/google-gcp/)
- [Add GCP Private Endpoint (Atlas Docs)](https://www.mongodb.com/docs/atlas/security-private-endpoint/?cloud-provider=gcp)
- [Port Mapping for GCP PSC (MongoDB Blog)](https://www.mongodb.com/company/blog/technical/port-mapping-for-google-private-service-connect-on-mongodb-atlas)
- [Multi-regional Atlas with PSC (Google Codelabs)](https://codelabs.developers.google.com/codelabs/psc-mongo-globalaccess)
- [Troubleshoot Private Endpoints (Atlas Docs)](https://www.mongodb.com/docs/atlas/troubleshoot-private-endpoints/)
- [Manage Connections from Google Cloud (Atlas Docs)](https://www.mongodb.com/docs/atlas/manage-connections-google-cloud/)
- [Workload Identity Federation (Atlas Docs)](https://www.mongodb.com/docs/atlas/workload-oidc/)
- [Manage Customer Keys with GCP KMS (Atlas Docs)](https://www.mongodb.com/docs/atlas/security-gcp-kms/)
- [Integrate Atlas with Vertex AI (Atlas Docs)](https://www.mongodb.com/docs/atlas/ai-integrations/google-vertex-ai/)
- [GCP Self-Serve Marketplace Billing (Atlas Docs)](https://www.mongodb.com/docs/atlas/billing/gcp-self-serve-marketplace/)
- [Atlas Kubernetes Operator (Atlas Docs)](https://www.mongodb.com/docs/atlas/operator/current/)
- [MongoDB to BigQuery Dataflow Template (GCP Docs)](https://docs.cloud.google.com/dataflow/docs/guides/templates/provided/mongodb-to-bigquery)
- [Atlas Stream Processing + GCP Pub/Sub (MongoDB Blog)](https://www.mongodb.com/company/blog/product-release-announcements/google-cloud-pub-sub-now-supported-in-atlas-stream-processing)
- [MongoDB Enterprise Advanced on GDC Hosted (MongoDB Blog)](https://www.mongodb.com/company/blog/product-release-announcements/mongodb-enterprise-advanced-google-distributed-cloud-hosted)
- [What's New at Google Cloud Next 2025 (MongoDB Blog)](https://www.mongodb.com/company/blog/events/whats-new-from-mongodb-at-google-cloud-next-2025)
- [mongodbatlas Terraform Provider (Registry)](https://registry.terraform.io/providers/mongodb/mongodbatlas/latest/docs)
- [Cloud Storage Bucket Data Federation (Atlas Docs)](https://www.mongodb.com/docs/atlas/data-federation/config/config-gcp-bucket/)
- [Encryption at Rest Architecture (Atlas Architecture Center)](https://www.mongodb.com/docs/atlas/architecture/current/data-encryption/)

---

## See Also
- [[mongodb-atlas-multicloud]] — multi-cloud replica sets, cross-cloud DR, Azure comparison, GCP PSC basics
- [[mongodb-aws-networking]] — analogous AWS-specific networking, PrivateLink, IAM auth patterns
- [[mongodb-atlas-azure]] — analogous Azure-specific networking, Private Link, Entra ID, Azure KMS
- [[mongodb-atlas-expert]] — Atlas general operations, cluster management, backup, performance
- [[mongodb-atlas-kubernetes-operator]] — AKO deep dive beyond GKE-specific patterns
- [[mongodb-search-ai]] — Atlas Vector Search, embedding strategies, hybrid search
