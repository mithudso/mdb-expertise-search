<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-kubernetes-operator` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-kubernetes-operator
description: >
  Deep reference for the MongoDB Atlas Kubernetes Operator (AKO) — managing
  Atlas clusters, users, networking, backup, and search declaratively from
  Kubernetes CRDs.
  TRIGGER: installing or upgrading AKO; writing AtlasProject / AtlasDeployment /
  AtlasDatabaseUser / AtlasBackupPolicy / AtlasSearchIndexConfig /
  AtlasPrivateEndpoint / AtlasNetworkPeering / AtlasStreamConnection manifests;
  Helm chart values for the Atlas operator; GitOps with ArgoCD or Flux for Atlas
  resources; Workload Identity (IRSA/GKE/AKS) for passwordless Atlas auth;
  reconciliation errors or clusters stuck in UPDATING; choosing between AKO vs
  Terraform vs Atlas CLI; migrating existing Atlas resources into Kubernetes
  management; "kubernetes operator", "atlas CRDs", "atlas operator helm",
  "kubectl atlas", "atlas gitops", managing Atlas via YAML manifests.
  SKIP: self-hosted MongoDB pods inside Kubernetes (use mongodb-drivers-k8s or
  mongodb-ops-manager); pure Terraform questions without Kubernetes (use
  mongodb-atlas-terraform); Atlas CLI scripting without Kubernetes context (use
  mongodb-atlas-cli).
whenNotToUse:
  - Managing self-hosted MongoDB pods inside Kubernetes — use mongodb-drivers-k8s
  - Pure Terraform-only questions without Kubernetes — use mongodb-atlas-terraform
  - Atlas CLI scripting without Kubernetes context — use mongodb-atlas-cli
  - Questions about MongoDB Community/Enterprise Operator (MCK) for on-prem pods
related_skills:
  - mongodb-atlas-expert
  - mongodb-atlas-iac
  - mongodb-atlas-terraform
  - mongodb-aws-networking
  - mongodb-atlas-gcp
  - mongodb-atlas-azure
  - mongodb-drivers-k8s
---

# MongoDB Atlas Kubernetes Operator (AKO)

AKO lets you manage MongoDB Atlas cloud resources (clusters, users, networking,
backup, search) as Kubernetes Custom Resources. Declare desired state in YAML;
the operator reconciles against the Atlas Administration API continuously.

**Latest stable:** v2.14.1 (May 2026) · GitHub: `mongodb/mongodb-atlas-kubernetes`

---

## Quick Start (5 minutes)

```bash
# 1. Install via Helm (cluster-wide)
helm repo add mongodb https://mongodb.github.io/helm-charts && helm repo update
helm install atlas-operator --namespace atlas-operator --create-namespace \
  mongodb/mongodb-atlas-operator

# 2. Create API key secret (label is required — operator searches by it)
kubectl create secret generic mongodb-atlas-operator-api-key \
  --from-literal="orgId=<org_id>" \
  --from-literal="publicApiKey=<pub_key>" \
  --from-literal="privateApiKey=<priv_key>" \
  -n mongodb-atlas-system
kubectl label secret mongodb-atlas-operator-api-key \
  atlas.mongodb.com/type=credentials -n mongodb-atlas-system

# 3. Minimal project + cluster + user
kubectl apply -f - <<'EOF'
apiVersion: atlas.mongodb.com/v1
kind: AtlasProject
metadata:
  name: my-project
  namespace: mongodb-atlas-system
spec:
  name: "My Project"
  projectIpAccessList:
    - cidrBlock: "0.0.0.0/0"
      comment: "Allow all (dev only)"
---
apiVersion: atlas.mongodb.com/v1
kind: AtlasDeployment
metadata:
  name: my-cluster
  namespace: mongodb-atlas-system
spec:
  projectRef:
    name: my-project
  deploymentSpec:
    name: my-cluster
    clusterType: REPLICASET
    replicationSpecs:
      - zoneName: US
        regionConfigs:
          - providerName: AWS
            regionName: US_EAST_1
            priority: 7
            electableSpecs:
              instanceSize: M10
              nodeCount: 3
---
apiVersion: atlas.mongodb.com/v1
kind: AtlasDatabaseUser
metadata:
  name: appuser
  namespace: mongodb-atlas-system
spec:
  username: appuser
  databaseName: admin
  passwordSecretRef:
    name: appuser-password   # Secret with key "password"
  roles:
    - roleName: readWrite
      databaseName: myapp
  projectRef:
    name: my-project
EOF

# 4. Wait for user to be ready (~10 min for M10 cluster provisioning)
# AKO uses custom condition types — poll status.conditions instead of kubectl wait
until kubectl get atlasdatabaseuser appuser -n mongodb-atlas-system \
  -o jsonpath='{.status.conditions[?(@.type=="DatabaseUserReady")].status}' \
  | grep -q True; do echo "waiting..."; sleep 15; done

# Retrieve connection string (secret created once DeploymentReady + DatabaseUserReady)
kubectl get secret my-project-my-cluster-appuser \
  -n mongodb-atlas-system \
  -o jsonpath='{.data.connectionStringStandardSrv}' | base64 -d
```

---

## Architecture Summary

AKO uses the standard **controller-runtime** reconcile loop:
1. Informer detects CR change → enqueues reconciliation
2. Reconciler reads CR spec (desired) and Atlas API (actual)
3. Calls Atlas Admin API v2 to close any gap
4. Updates `status.conditions` (`Ready: True` on success; error + requeue on failure)
5. Periodic requeue catches out-of-band Atlas drift (minutes cadence)

**Deletion protection (v2.0+):** Deleting a CR in Kubernetes does NOT delete the
Atlas resource by default — the operator just stops managing it. Override per-resource:
```yaml
metadata:
  annotations:
    mongodb.com/atlas-resource-policy: "delete"   # force delete in Atlas
    mongodb.com/atlas-reconciliation-policy: "skip"  # pause reconciliation
```

**AKO vs MCK:** AKO manages Atlas (fully managed cloud). MongoDB Controllers for
Kubernetes (MCK, formerly Enterprise Operator) deploys self-hosted MongoDB pods inside K8s.

---

## CRD Quick Reference (18+ resources, all `apiVersion: atlas.mongodb.com/v1`)

| CRD | `kubectl` short | Purpose |
|---|---|---|
| AtlasProject | `ap` | Project + org-level settings, API key binding |
| AtlasDeployment | `ad` | Cluster (ReplicaSet / Sharded / Flex) |
| AtlasDatabaseUser | `adu` | DB users — SCRAM, X.509, AWS IAM, OIDC |
| AtlasBackupPolicy | `abp` | Snapshot frequency + retention |
| AtlasBackupSchedule | `abs` | Schedule + cross-region copy; references AtlasBackupPolicy |
| AtlasBackupCompliance | `abcp` | Org-level backup compliance policy |
| AtlasCustomRole | `acr` | Custom DB roles |
| AtlasIPAccessList | `aal` | IP / CIDR / AWS SG access entries (v2.7+) |
| AtlasNetworkContainer | `anc` | VPC container for peering (v2.8+) |
| AtlasNetworkPeering | `anp` | VPC/VNet peering (v2.8+) |
| AtlasPrivateEndpoint | `ape` | AWS PrivateLink / Azure PL / GCP PSC (v2.6+) |
| AtlasSearchIndexConfig | `asic` | Reusable search analyzer config |
| AtlasStreamConnection | `asc` | Stream Processing source/sink |
| AtlasStreamWorkspace | `asi` | Stream Processing workspace |
| AtlasDataFederation | `adf` | Federated database instances |
| AtlasFederatedAuth | `afa` | SSO / federated auth |
| AtlasTeam | `at` | Project team membership |
| AtlasOrgSettings | `aos` | Organization settings |

**CRD evolution:** v1.x nested everything in AtlasProject. v2.0+ made sub-resources
independent CRDs with their own lifecycles. v2.5+ allows AtlasDeployment /
AtlasDatabaseUser to reference an Atlas project by ID (`externalProjectRef`) without
requiring an AtlasProject CR in the same cluster.

---

## Credential Scoping (Priority Order)

1. **Resource-level** `spec.connectionSecret.name` — used with `externalProjectRef`
2. **Project-level** `spec.connectionSecretRef.name` — on AtlasProject CR
3. **Global** `<helm-release>-api-key` secret in operator namespace (fallback)

Secret must be labeled `atlas.mongodb.com/type=credentials` or it won't be found.

---

## Reference Files

Read the relevant file before answering detailed questions:

| File | Read when asked about… |
|---|---|
| `references/crds.md` | Any CRD spec, field names, YAML examples for AtlasProject/AtlasDeployment/AtlasDatabaseUser/backup/networking/search/stream |
| `references/helm-gitops.md` | Helm values, RBAC, namespace vs cluster-wide scope, ArgoCD/Flux integration, ESO/Sealed Secrets for API keys |
| `references/workload-identity.md` | Passwordless Atlas auth, IRSA on EKS, GKE Workload Identity, AKS Workload Identity, `awsIamType`/`oidcAuthType` |
| `references/troubleshooting.md` | Status condition errors, stuck clusters, secret format issues, rate limiting, dry run mode, upgrade paths |
| `references/iac-comparison.md` | AKO vs Terraform vs CLI decision matrix + migration playbooks |

---

## Common Patterns at a Glance

**Check resource status:**
```bash
kubectl get atlasdeployments,atlasprojects,atlasdatabaseusers -A
kubectl describe atlasdeployment <name> -n <ns>   # shows Events + conditions
kubectl get atlasdeployment <name> -n <ns> -o jsonpath='{.status.conditions}' | jq .
```

**Pause reconciliation during Atlas maintenance:**
```bash
kubectl annotate atlasdeployment <name> mongodb.com/atlas-reconciliation-policy=skip -n <ns>
# ... do manual changes in Atlas ...
kubectl annotate atlasdeployment <name> mongodb.com/atlas-reconciliation-policy- -n <ns>
```

**Import existing Atlas cluster:**
```bash
atlas kubernetes config generate --projectId <id> --clusterName <name> > resources.yaml
kubectl apply -f resources.yaml   # operator adopts without re-creating
```

**Connection secret name formula:** `{atlasproject-name}-{cluster-name}-{dbuser-name}`

---

## See Also

- [[mongodb-atlas-expert]] — Atlas platform (tiers, regions, billing, projects)
- [[mongodb-atlas-gcp]] — GCP networking, Private Service Connect, GKE patterns
- [[mongodb-atlas-azure]] — Azure networking, Private Link, AKS patterns
- [[mongodb-aws-networking]] — AWS VPC, PrivateLink, IRSA
- [[mongodb-drivers-k8s]] — MongoDB drivers inside Kubernetes pods
