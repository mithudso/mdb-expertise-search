<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-cli` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

# MongoDB Atlas CLI

## Overview

The MongoDB Atlas CLI (`atlas`) is the official command-line interface for managing MongoDB Atlas resources from the terminal. It provides full programmatic control over clusters, users, networking, backups, search indexes, Kubernetes integration, and Atlas Stream Processing — making it the standard tool for DevOps automation, CI/CD pipelines, and infrastructure-as-code workflows.

**When to use this skill:**
- Installing or authenticating the Atlas CLI
- Creating, modifying, pausing, or deleting Atlas clusters from the terminal
- Managing database users, custom roles, and API keys
- Configuring network access: IP allowlists, private endpoints, VPC peering
- Automating backup snapshots and restores
- Managing Atlas Search indexes via CLI
- Integrating Atlas with Kubernetes using AKO
- Setting up Atlas CLI in GitHub Actions, GitLab CI, or other pipelines
- Using `atlas quickstart` / `atlas setup` for rapid development cluster creation
- Spotting and fixing Atlas CLI anti-patterns in scripts

**See also:** [[mongodb-atlas-expert]], [[mongodb-atlas-terraform]], [[mongodb-atlas-kubernetes-operator]]

---

## 1. Installation and Authentication

### 1.1 Installing the Atlas CLI

**macOS (Homebrew)**
```bash
# Installs both Atlas CLI and mongosh
brew install mongodb-atlas

# Verify installation
atlas --version
```

**Linux/Ubuntu/Debian (apt)**
```bash
# Install prerequisites
sudo apt-get install gnupg curl

# Import MongoDB GPG key (replace 7.0 with your MongoDB server version)
curl -fsSL https://pgp.mongodb.com/server-7.0.asc | \
  sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor

# Add repository (Ubuntu 22.04 Jammy)
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] \
  https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Update and install (with mongosh)
sudo apt-get update
sudo apt-get install -y mongodb-atlas

# Or Atlas CLI only
sudo apt-get install -y mongodb-atlas-cli
```

**RHEL/CentOS/Amazon Linux (yum)**
```bash
# Create repo file
cat > /etc/yum.repos.d/mongodb-org-7.0.repo << 'EOF'
[mongodb-org-7.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/$releasever/mongodb-org/7.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://pgp.mongodb.com/server-7.0.asc
EOF

sudo yum install -y mongodb-atlas
# or Atlas CLI only: sudo yum install -y mongodb-atlas-cli
```

**Windows (Chocolatey)**
```powershell
choco install mongodb-atlas
# Enter 'A' to confirm, then close and reopen terminal
```

**Direct binary download (all platforms)**

Binaries are published to `fastdl.mongodb.org`. Example for Linux x86-64:
```bash
# Download (replace 1.54.0 with current version)
curl -LO https://fastdl.mongodb.org/mongocli/mongodb-atlas-cli_1.54.0_linux_x86_64.tar.gz
tar -xzf mongodb-atlas-cli_1.54.0_linux_x86_64.tar.gz
mv bin/atlas /usr/local/bin/atlas
atlas --version
```

Available packages: `.zip`, `.msi` (Windows); `.deb` (Debian/Ubuntu); `.rpm` (RHEL); `.tar.gz` (generic Linux). macOS ARM and x86-64 `.zip` variants are both published.

**Docker**
```bash
# Pull the official image
docker pull mongodb/atlas

# Run interactive shell (atlas commands run inside the container)
docker run --rm -it mongodb/atlas bash
# atlas --help
```

**Update**
```bash
brew upgrade mongodb-atlas                          # macOS
sudo apt-get install --only-upgrade mongodb-atlas   # apt
yum update mongodb-atlas                            # yum
choco upgrade mongodb-atlas                         # Chocolatey
atlas --version                                     # verify after update
```

### 1.2 Authentication Methods

The Atlas CLI supports three authentication flows. Select the method that matches your use case:

| Method | Command | Best For |
|--------|---------|---------|
| UserAccount | `atlas auth login` (select UserAccount) | Interactive human sessions |
| ServiceAccount | `atlas auth login` (select ServiceAccount) | CI/CD, OAuth apps |
| API Keys | `atlas auth login` (select APIKeys) | Programmatic, older automation |

**UserAccount (browser OAuth2 — 12-hour token)**
```bash
atlas auth login
# 1. Select "UserAccount"
# 2. CLI opens a browser and shows a one-time activation code (expires 10 min)
# 3. Paste code at the Atlas login page and click Confirm Authorization
# 4. Success message: "Successfully logged in as <email>"
```
Note: As of March 2025, Atlas enforces mandatory MFA. The browser flow handles MFA automatically.

**ServiceAccount (OAuth2 client credentials — programmatic)**
```bash
atlas auth login
# 1. Select "ServiceAccount"
# 2. Enter Client ID and Client Secret
# 3. Select default organization and project

# Or set environment variables and skip interactive login:
export MONGODB_ATLAS_CLIENT_ID="<client_id>"
export MONGODB_ATLAS_CLIENT_SECRET="<client_secret>"
```

**API Keys (programmatic)**
```bash
atlas auth login
# 1. Select "APIKeys"
# 2. Enter public and private API keys
# 3. Accept default profile options

# Or use environment variables:
export MONGODB_ATLAS_PUBLIC_API_KEY="<public_key>"
export MONGODB_ATLAS_PRIVATE_API_KEY="<private_key>"
```

**Government/GovCloud (federation auth)**
```bash
# For Atlas for Government (GovCloud) environments
atlas auth login --gov
```
Use `--gov` when your Atlas account is in the `.gov` domain. The flag redirects the OAuth2 flow to the government identity federation endpoint.

Security note: Atlas CLI v1.46 and earlier stored API keys in plaintext in the config file. v1.47+ uses secure credential storage. Treat config files like passwords.

**Verify current authentication**
```bash
atlas auth whoami
```

**Log out**
```bash
atlas auth logout
```

### 1.3 Profile Configuration

Profiles allow you to manage multiple organizations/projects simultaneously.

**Create a named profile**
```bash
atlas auth login --profile myProfile
# or for API key profiles
atlas config init --profile myProfile
```

**Use a named profile**
```bash
atlas clusters list --profile myProfile
```

**Set default org/project for a profile**
```bash
# During auth login, the CLI prompts you to select:
# - Default Organization
# - Default Project
# - Default Output Format (json or plaintext)
# - MongoDB Shell path
```

**View profile settings**
```bash
atlas config describe myProfile
```

**Config file location**

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/atlascli/config.toml` |
| Linux | `$XDG_CONFIG_HOME/atlascli/config.toml` (default: `$HOME/.config/atlascli`) |
| Windows | `%AppData%/atlascli/config.toml` |

**Settings precedence** (highest to lowest):
1. Command-line flags (`--projectId`, `--orgId`)
2. Environment variables
3. Profile settings in `config.toml`

### 1.4 Environment Variables

Full list of supported environment variables:

| Variable | Purpose |
|----------|---------|
| `MONGODB_ATLAS_PUBLIC_API_KEY` | Public API key |
| `MONGODB_ATLAS_PRIVATE_API_KEY` | Private API key |
| `MONGODB_ATLAS_CLIENT_ID` | Service Account client ID |
| `MONGODB_ATLAS_CLIENT_SECRET` | Service Account client secret |
| `MONGODB_ATLAS_ACCESS_TOKEN` | Access token (12-hour validity) |
| `MONGODB_ATLAS_REFRESH_TOKEN` | Refresh token for auto-renewal |
| `MONGODB_ATLAS_PROJECT_ID` | Default project ID (replaces `--projectId`) |
| `MONGODB_ATLAS_ORG_ID` | Default org ID (replaces `--orgId`) |
| `MONGODB_ATLAS_OUTPUT` | Default output format (`json`, etc.) |
| `MONGODB_ATLAS_MONGOSH_PATH` | Full path to `mongosh` binary |
| `DO_NOT_TRACK` | Set to `1` to disable telemetry |
| `MONGODB_ATLAS_TELEMETRY_ENABLED` | Set to `false` to disable telemetry |
| `MONGODB_ATLAS_SKIP_UPDATE_CHECK` | Set to `yes` to skip update prompts |
| `MONGODB_ATLAS_SILENCE_STORAGE_WARNING` | Set to `true` to suppress storage warnings |
| `HTTP_PROXY` / `HTTPS_PROXY` | Proxy configuration |
| `NO_PROXY` | URLs that bypass proxy |

---

## 2. Cluster Management

### 2.1 Create Clusters

```bash
# Syntax
atlas clusters create [name] [options]

# Free M0 cluster (shared, always free)
atlas clusters create myFreeCluster \
  --projectId <projectId> \
  --provider AWS \
  --region US_EAST_1 \
  --tier M0

# Flex cluster with tags
atlas clusters create myFlexCluster \
  --projectId <projectId> \
  --provider AWS \
  --region US_EAST_1 \
  --tier FLEX \
  --tag env=dev

# M10 replica set on AWS (blocks until ready)
atlas clusters create myRS \
  --projectId <projectId> \
  --provider AWS \
  --region US_EAST_1 \
  --members 3 \
  --tier M10 \
  --mdbVersion 7.0 \
  --diskSizeGB 10 \
  --watch   # blocks terminal until cluster reaches IDLE state

# M10 replica set on Azure
atlas clusters create myRS \
  --projectId <projectId> \
  --provider AZURE \
  --region US_EAST_2 \
  --members 3 \
  --tier M10 \
  --mdbVersion 7.0 \
  --diskSizeGB 10

# M10 replica set on GCP
atlas clusters create myRS \
  --projectId <projectId> \
  --provider GCP \
  --region EASTERN_US \
  --members 3 \
  --tier M10 \
  --mdbVersion 7.0 \
  --diskSizeGB 10

# Sharded cluster with independent shard scaling
atlas clusters create mySharded \
  --projectId <projectId> \
  --provider GCP \
  --region EASTERN_US \
  --members 3 \
  --tier M10 \
  --shards 2 \
  --type SHARDED \
  --autoScalingMode independentShardScaling

# From JSON configuration file (full cluster spec)
atlas clusters create --projectId <projectId> --file cluster-spec.json

# With termination protection enabled
atlas clusters create myCluster \
  --projectId <projectId> \
  --provider AWS --region US_EAST_1 --tier M10 \
  --enableTerminationProtection
```

**Key flags for `atlas clusters create`:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--provider` | string | required* | `AWS`, `AZURE`, or `GCP` |
| `--region` | string | required* | Cloud provider region |
| `--tier` | string | `FLEX` | `M0`, `FLEX`, `M10`, `M20`, … |
| `--mdbVersion` | string | latest stable | Major MongoDB version |
| `--members`, `-m` | int | `3` | Replica set member count |
| `--shards`, `-s` | int | `1` | Shard count |
| `--type` | string | `REPLICASET` | `REPLICASET` or `SHARDED` |
| `--diskSizeGB` | float | `2` | Root volume size (GB) |
| `--file`, `-f` | string | — | JSON cluster spec file |
| `--backup` | flag | — | Enable continuous cloud backup |
| `--tag` | key=value | — | Metadata tags |
| `--autoScalingMode` | string | `clusterWideScaling` | Scaling mode |
| `--enableTerminationProtection` | flag | — | Prevents accidental deletion |
| `--watch`, `-w` | flag | — | Block until cluster is IDLE |
| `--output`, `-o` | string | — | `json`, `json-path`, `go-template` |

*Required unless `--file` is specified. `--file` is mutually exclusive with tier/provider/region/members/diskSizeGB/mdbVersion/type/shards flags.

Note: M2 and M5 tiers are deprecated; they are automatically created as FLEX tier.

### 2.2 Watch and Wait for Clusters

```bash
# Block until cluster is ready (IDLE state)
atlas clusters watch myCluster --projectId <projectId>
# Prints "Cluster available." when done
# Interrupt with CTRL-C

# Using --watch flag inline during create/update
atlas clusters create myCluster ... --watch
```

`atlas clusters watch` polls continuously and is the correct pattern for CI/CD scripts that must wait for cluster readiness before running migrations or tests. Without this, you may try to connect to a cluster that is still provisioning (see Anti-Patterns section).

### 2.3 List, Describe, and Connection Strings

```bash
# List all clusters in a project
atlas clusters list --projectId <projectId>
atlas clusters list --projectId <projectId> --output json

# Describe a specific cluster
atlas clusters describe myCluster --projectId <projectId>
atlas clusters describe myCluster --projectId <projectId> --output json

# Get connection string
atlas clusters connectionStrings describe myCluster --projectId <projectId>
# Returns SRV connection string: mongodb+srv://...
```

### 2.4 Update Clusters

```bash
# Change tier
atlas clusters update myCluster --projectId <projectId> --tier M50

# Increase disk size
atlas clusters update myCluster --projectId <projectId> --diskSizeGB 100

# Upgrade MongoDB version (cannot downgrade)
atlas clusters update myCluster --projectId <projectId> --mdbVersion 7.0

# Add or replace tags
atlas clusters update myCluster --projectId <projectId> --tag env=staging

# Remove all tags
atlas clusters update myCluster --projectId <projectId> --tag =

# Enable termination protection
atlas clusters update myCluster --projectId <projectId> --enableTerminationProtection

# Update from JSON file
atlas clusters update myCluster --projectId <projectId> \
  --file updated-cluster.json --output json

# Auto-scaling mode change
atlas clusters update myCluster --projectId <projectId> \
  --autoScalingMode independentShardScaling
```

Restrictions: cluster name cannot be changed, MongoDB version cannot be downgraded, `--file` is mutually exclusive with individual flags. Requires M10+ and Project Cluster Manager role.

### 2.5 Pause and Resume Clusters

```bash
# Pause a running cluster (M10+ only; M0 cannot be paused)
atlas clusters pause myCluster --projectId <projectId>

# Resume (start) a paused cluster
atlas clusters start myCluster --projectId <projectId>
```

Pausing stops compute billing but retains data and configuration. Useful for dev/staging clusters outside business hours.

### 2.6 Delete Clusters

```bash
# Delete with confirmation prompt
atlas clusters delete myCluster --projectId <projectId>

# Delete without confirmation (for CI scripts)
atlas clusters delete myCluster --projectId <projectId> --force

# Watch deletion complete before next step
atlas clusters delete myCluster --projectId <projectId> --force && \
  echo "Cluster deleted"
```

Warning: `--force` bypasses the interactive confirmation prompt. Use with caution in scripts; always pair with explicit variable validation to avoid deleting the wrong cluster.

---

## 3. Backup and Restore Commands

### 3.1 Snapshot Management

```bash
# List all snapshots for a cluster
atlas backups snapshots list --clusterName myCluster \
  --projectId <projectId>
atlas backups snapshots list --clusterName myCluster \
  --projectId <projectId> --output json

# Describe a specific snapshot
atlas backups snapshots describe <snapshotId> \
  --clusterName myCluster --projectId <projectId>

# Create an on-demand snapshot
atlas backups snapshots create --clusterName myCluster \
  --projectId <projectId> \
  --desc "Pre-deployment snapshot"

# Watch snapshot creation until complete
atlas backups snapshots watch <snapshotId> \
  --clusterName myCluster --projectId <projectId>

# Delete a snapshot
atlas backups snapshots delete <snapshotId> \
  --clusterName myCluster --projectId <projectId> --force

# Download a snapshot (Flex clusters)
atlas backups snapshots download <snapshotId> \
  --clusterName myFlexCluster --projectId <projectId>
```

### 3.2 Restore Jobs

Three restore types are available:

**Automated restore** — restores a snapshot to a target cluster (wipes all existing data on target first):
```bash
atlas backups restores start automated \
  --clusterName mySourceCluster \
  --snapshotId 5e7e00128f8ce03996a47179 \
  --targetClusterName myTargetCluster \
  --targetProjectId <targetProjectId>
```

**Download restore** — downloads the snapshot files for manual restoration:
```bash
atlas backups restores start download \
  --clusterName myCluster \
  --snapshotId 5e7e00128f8ce03996a47179
```

**Point-in-time restore** — restores to a specific UTC timestamp (wipes all existing data on target first):
```bash
# By Unix timestamp (within last 24 hours)
atlas backups restores start pointInTime \
  --clusterName myCluster \
  --pointInTimeUTCSeconds 1588523147 \
  --targetClusterName myTargetCluster \
  --targetProjectId <targetProjectId>

# By oplog timestamp and increment
atlas backups restores start pointInTime \
  --clusterName myCluster \
  --oplogTs 1588523147 \
  --oplogInc 1 \
  --targetClusterName myTargetCluster \
  --targetProjectId <targetProjectId>
```

**Watch restore job completion:**
```bash
atlas backups restores watch <restoreJobId> \
  --clusterName myCluster --projectId <projectId>
```

**List restore jobs:**
```bash
atlas backups restores list --clusterName myCluster \
  --projectId <projectId> --output json
```

Restrictions: Flex clusters support only automated restore. Automated and point-in-time restores overwrite all data on the target cluster. Requires Project Owner role.

### 3.3 Backup Schedule

```bash
# View backup schedule for a cluster
atlas backups schedule describe myCluster --projectId <projectId>

# Update backup schedule from file
atlas backups schedule update --clusterName myCluster \
  --projectId <projectId> --file schedule.json

# Delete backup schedule
atlas backups schedule delete myCluster --projectId <projectId>
```

### 3.4 Cloud Backup Exports

```bash
# Create an export job (exports to S3)
atlas backups exports jobs create \
  --clusterName myCluster \
  --projectId <projectId> \
  --snapshotId <snapshotId> \
  --exportBucketId <bucketId>

# List export buckets
atlas backups exports buckets list --projectId <projectId>

# Create an export bucket (S3)
atlas backups exports buckets create \
  --projectId <projectId> \
  --cloudProvider AWS \
  --bucketName my-export-bucket \
  --iamRoleId <iamRoleId>
```

### 3.5 Backup Compliance Policy

```bash
# Enable compliance policy (irreversible without MongoDB support)
atlas backups compliancePolicy enable \
  --projectId <projectId> \
  --authorizedEmail admin@example.com \
  --authorizedFirstName Admin \
  --authorizedLastName User

# Describe current compliance policy
atlas backups compliancePolicy describe --projectId <projectId>

# Setup compliance policy from file
atlas backups compliancePolicy setup \
  --projectId <projectId> \
  --file compliance-policy.json
```

Warning: Enabling Backup Compliance Policy is largely irreversible and prevents deletion of snapshots that would violate the policy. Contact MongoDB support to disable.

---

## 4. Networking and Security Commands

### 4.1 IP Access Lists

```bash
# List access list entries
atlas accessLists list --projectId <projectId>

# Add your current IP address (--currentIp is a standalone boolean flag)
atlas accessLists create --projectId <projectId> --currentIp

# Add a specific IP address
atlas accessLists create --projectId <projectId> \
  --type ipAddress --ip 203.0.113.42

# Add a CIDR block
atlas accessLists create --projectId <projectId> \
  --type cidrBlock --ip 10.0.0.0/8

# Add with auto-expiry (temporary access)
atlas accessLists create --projectId <projectId> \
  --type ipAddress --ip 203.0.113.42 \
  --deleteAfterDate "2025-12-31T00:00:00Z"

# Add AWS Security Group
atlas accessLists create --projectId <projectId> \
  --type awsSecurityGroup --ip sg-0a1b2c3d4e5f67890

# Delete an entry
atlas accessLists delete 203.0.113.42 --projectId <projectId> --force

# Describe an entry
atlas accessLists describe 203.0.113.42 --projectId <projectId>
```

Never add `0.0.0.0/0` in production; restrict to known CIDRs. Use `--deleteAfterDate` for temporary access grants in build agents.

### 4.2 Private Endpoints

Private endpoint commands are organized by cloud provider.

**AWS Private Endpoints:**
```bash
# Create a new AWS private endpoint for your project
atlas privateEndpoints aws create \
  --projectId <projectId> \
  --region us-east-1

# Watch until endpoint is available
atlas privateEndpoints aws watch <endpointId> \
  --projectId <projectId>

# List all AWS private endpoints
atlas privateEndpoints aws list --projectId <projectId>

# Describe a specific endpoint
atlas privateEndpoints aws describe <endpointId> \
  --projectId <projectId>

# Create interface for a private endpoint
atlas privateEndpoints aws interfaces create <endpointId> \
  --projectId <projectId> \
  --vpcId vpc-0a1b2c3d \
  --subnetIds subnet-0a1b2c3d

# Delete a private endpoint
atlas privateEndpoints aws delete <endpointId> \
  --projectId <projectId> --force
```

**Azure Private Endpoints:**
```bash
atlas privateEndpoints azure create \
  --projectId <projectId> --region eastus2

atlas privateEndpoints azure watch <endpointId> \
  --projectId <projectId>

atlas privateEndpoints azure describe <endpointId> \
  --projectId <projectId>
```

**GCP Private Endpoints:**
```bash
atlas privateEndpoints gcp create \
  --projectId <projectId> --region us-east4

atlas privateEndpoints gcp watch <endpointId> \
  --projectId <projectId>
```

### 4.3 Network Peering

```bash
# List network peering connections
atlas networking peering list --projectId <projectId>

# Create VPC peering (AWS)
atlas networking peering create aws \
  --projectId <projectId> \
  --atlasCidrBlock 192.168.0.0/24 \
  --accountId <awsAccountId> \
  --vpcId <vpcId> \
  --region us-east-1 \
  --routeTableCidrBlock 10.0.0.0/8

# Describe a peering connection
atlas networking peering describe <peeringId> \
  --projectId <projectId>

# Delete a peering connection
atlas networking peering delete <peeringId> \
  --projectId <projectId> --force

# Watch until peering is available
atlas networking peering watch <peeringId> \
  --projectId <projectId>
```

---

## 5. Users and RBAC Commands

### 5.1 Database Users

```bash
# List all database users
atlas dbusers list --projectId <projectId>
atlas dbusers list --projectId <projectId> --output json

# Describe a specific user
atlas dbusers describe myUser --projectId <projectId>

# Create user with built-in role (SCRAM-SHA password auth)
atlas dbusers create atlasAdmin \
  --username myAdmin \
  --projectId <projectId>

# Create read/write user
atlas dbusers create readWriteAnyDatabase \
  --username myUser \
  --password "SecurePassword123!" \
  --projectId <projectId>

# Create user with scoped roles
atlas dbusers create \
  --username myUser \
  --password "SecurePassword123!" \
  --role "readWrite@mydb" \
  --projectId <projectId>

# Create user with multiple roles
atlas dbusers create \
  --username myUser \
  --role "clusterMonitor,backup" \
  --projectId <projectId>

# Create user with collection-level role
atlas dbusers create \
  --username myUser \
  --role "read@mydb.orders" \
  --projectId <projectId>

# Create user with scoped cluster access
atlas dbusers create \
  --username myUser \
  --role clusterMonitor \
  --scope <replicaSetId>,<storeName> \
  --projectId <projectId>

# Create X.509-authenticated user (Atlas-managed cert)
atlas dbusers create \
  --username "CN=myUser,OU=myOrg" \
  --x509Type MANAGED \
  --projectId <projectId>

# Create AWS IAM-authenticated user
atlas dbusers create \
  --username "arn:aws:iam::123456789:user/myUser" \
  --awsIAMType USER \
  --projectId <projectId>

# Create LDAP group user
atlas dbusers create \
  --username "cn=mygroup,ou=groups,dc=example,dc=com" \
  --ldapType GROUP \
  --role readWriteAnyDatabase \
  --projectId <projectId>

# Create with automatic deletion date (temporary user)
atlas dbusers create \
  --username tempUser \
  --password "TempPass123!" \
  --role readAnyDatabase \
  --deleteAfterDate "2025-12-31T00:00:00Z" \
  --projectId <projectId>

# Update a user
atlas dbusers update myUser \
  --password "NewPassword456!" \
  --role readWriteAnyDatabase \
  --projectId <projectId>

# Delete a user
atlas dbusers delete myUser --projectId <projectId> --force
```

**Authentication type flags for `atlas dbusers create`:**

| Flag | Values | Description |
|------|--------|-------------|
| `--x509Type` | `NONE`, `MANAGED`, `CUSTOMER` | X.509 certificate auth |
| `--awsIAMType` | `NONE`, `USER`, `ROLE` | AWS IAM auth |
| `--ldapType` | `NONE`, `USER`, `GROUP` | LDAP auth |
| `--oidcType` | `NONE`, `USER`, `IDP_GROUP` | OIDC auth (mutually exclusive with `--password`) |

When all auth type flags are `NONE` (default), SCRAM-SHA password auth is used.

**Role format:** `roleName[@dbName[.collection]]`

Examples: `atlasAdmin`, `readWriteAnyDatabase`, `read@mydb`, `readWrite@mydb.orders`

### 5.2 X.509 Certificates

```bash
# Create a new X.509 certificate for a user
atlas dbusers certs create --username myUser \
  --monthsUntilExpiration 12 \
  --projectId <projectId>

# List certificates for a user
atlas dbusers certs list --username myUser --projectId <projectId>
```

### 5.3 Custom Database Roles

```bash
# List custom roles
atlas customDbRoles list --projectId <projectId>

# Describe a custom role
atlas customDbRoles describe myRole --projectId <projectId>

# Create a custom role
atlas customDbRoles create myRole \
  --projectId <projectId> \
  --privilege "FIND@orders_db.orders" \
  --privilege "INSERT@orders_db.orders"

# Create role inheriting from built-in roles
atlas customDbRoles create myRole \
  --projectId <projectId> \
  --inheritedRole read \
  --privilege "INSERT@mydb.allowedCollection"

# Update a custom role
atlas customDbRoles update myRole \
  --projectId <projectId> \
  --privilege "FIND@orders_db.orders"

# Delete a custom role
atlas customDbRoles delete myRole --projectId <projectId> --force
```

### 5.4 Teams

```bash
# List teams in an organization
atlas teams list --orgId <orgId>

# Create a team
atlas teams create myTeam --orgId <orgId>

# Add users to a team
atlas teams users add <teamId> \
  --orgId <orgId> \
  --user user1@example.com,user2@example.com

# Remove users from a team
atlas teams users delete <teamId> \
  --orgId <orgId> --username user1@example.com

# Add team to a project
atlas projects teams add <teamId> \
  --projectId <projectId> \
  --role GROUP_READ_ONLY
```

### 5.5 Project API Keys

```bash
# Create a project-level API key
atlas projects apiKeys create \
  --projectId <projectId> \
  --role GROUP_OWNER \
  --desc "CI/CD automation key"

# List project API keys
atlas projects apiKeys list --projectId <projectId>

# Assign an existing API key to a project
atlas projects apiKeys assign <apiKeyId> \
  --projectId <projectId> \
  --role GROUP_DATA_ACCESS_READ_WRITE

# Delete a project API key assignment
atlas projects apiKeys delete <apiKeyId> \
  --projectId <projectId> --force

# Create organization-level API key
atlas organizations apiKeys create \
  --orgId <orgId> \
  --role ORG_OWNER \
  --desc "Org admin key"
```

Note: When you create an API key, Atlas shows the private key exactly once. Capture and store it securely immediately.

---

## 6. Search and Data Commands

### 6.1 Atlas Search Index Management

```bash
# List all search indexes on a cluster
atlas clusters search indexes list \
  --clusterName myCluster \
  --db mydb \
  --collection myCollection \
  --projectId <projectId>

# Describe a search index
atlas clusters search indexes describe <indexId> \
  --clusterName myCluster \
  --projectId <projectId>

# Create a search index from a JSON definition file
atlas clusters search indexes create \
  --clusterName myCluster \
  --file search-index.json \
  --projectId <projectId>

# Create with inline name
atlas clusters search indexes create mySearchIndex \
  --clusterName myCluster \
  --file search-index.json \
  --projectId <projectId>

# Update a search index from file
atlas clusters search indexes update <indexId> \
  --clusterName myCluster \
  --file updated-index.json \
  --projectId <projectId>

# Delete a search index
atlas clusters search indexes delete <indexId> \
  --clusterName myCluster \
  --projectId <projectId> --force
```

**Sample `search-index.json` for Atlas Search:**
```json
{
  "name": "mySearchIndex",
  "type": "search",
  "collectionName": "products",
  "database": "ecommerce",
  "definition": {
    "mappings": {
      "dynamic": true
    }
  }
}
```

**Sample `search-index.json` for Atlas Vector Search:**
```json
{
  "name": "myVectorIndex",
  "type": "vectorSearch",
  "collectionName": "embeddings",
  "database": "aidb",
  "definition": {
    "fields": [
      {
        "type": "vector",
        "path": "embedding",
        "numDimensions": 1536,
        "similarity": "cosine"
      }
    ]
  }
}
```

Authentication requirement: Project Data Access Admin role.

### 6.2 Search Nodes

```bash
# List search nodes for a cluster
atlas clusters search nodes list \
  --clusterName myCluster --projectId <projectId>

# Create dedicated search nodes
atlas clusters search nodes create \
  --clusterName myCluster \
  --projectId <projectId> \
  --instanceSize S20_HIGHCPU_NVME \
  --nodeCount 2

# Delete search nodes
atlas clusters search nodes delete \
  --clusterName myCluster --projectId <projectId> --force
```

### 6.3 Data Federation

```bash
# List federated database instances
atlas dataFederation list --projectId <projectId>

# Create a federated database instance
atlas dataFederation create myFedDB \
  --projectId <projectId> \
  --file federated-db.json

# Describe a federated database instance
atlas dataFederation describe myFedDB --projectId <projectId>

# Update a federated database instance
atlas dataFederation update myFedDB \
  --projectId <projectId> \
  --file updated-fedDB.json

# Delete a federated database instance
atlas dataFederation delete myFedDB --projectId <projectId> --force

# View query limits
atlas dataFederation queryLimits list myFedDB --projectId <projectId>
```

### 6.4 Atlas Stream Processing

```bash
# Manage stream processing instances
atlas streams instances list --projectId <projectId>

atlas streams instances create myStream \
  --projectId <projectId> \
  --provider AWS \
  --region us-east-1 \
  --tier SP30

atlas streams instances describe myStream --projectId <projectId>

atlas streams instances update myStream \
  --projectId <projectId> --tier SP10

atlas streams instances delete myStream --projectId <projectId> --force

# Manage stream connections
atlas streams connections list \
  --instance myStream --projectId <projectId>

atlas streams connections create myKafkaConn \
  --instance myStream \
  --projectId <projectId> \
  --file kafka-connection.json

atlas streams connections describe myKafkaConn \
  --instance myStream --projectId <projectId>

atlas streams connections update myKafkaConn \
  --instance myStream \
  --projectId <projectId> \
  --file updated-connection.json

atlas streams connections delete myKafkaConn \
  --instance myStream --projectId <projectId> --force

# Manage PrivateLink endpoints for streams
atlas streams privateLinks list --projectId <projectId>
atlas streams privateLinks create --projectId <projectId> \
  --provider AWS --region us-east-1
```

---

## 7. Kubernetes Integration

The Atlas CLI provides first-class support for the Atlas Kubernetes Operator (AKO), allowing you to export existing Atlas configurations as Kubernetes CRDs and install the operator into an existing cluster.

### 7.1 Generate Kubernetes CRD Configuration

`atlas kubernetes config generate` exports an existing Atlas project, clusters, and database users as Atlas Kubernetes Operator-compatible YAML resources. The output goes to stdout for review or piping into `kubectl apply`.

```bash
# Generate CRDs for entire project (no secrets)
atlas kubernetes config generate --projectId <projectId>

# Generate with Kubernetes secrets included
atlas kubernetes config generate \
  --projectId <projectId> \
  --includeSecrets

# Generate for specific clusters only
atlas kubernetes config generate \
  --projectId <projectId> \
  --clusterName cluster1,cluster2 \
  --includeSecrets \
  --targetNamespace atlas-operator

# Generate for specific data federations
atlas kubernetes config generate \
  --projectId <projectId> \
  --dataFederationName fed1,fed2 \
  --targetNamespace atlas-operator

# Generate for specific AKO version
atlas kubernetes config generate \
  --projectId <projectId> \
  --targetNamespace atlas-operator \
  --operatorVersion 2.5.0

# Use independent resources (external IDs instead of Kubernetes references)
# Useful when resources are managed independently across namespaces
atlas kubernetes config generate \
  --projectId <projectId> \
  --independentResources

# Pipe directly to kubectl
atlas kubernetes config generate \
  --projectId <projectId> \
  --includeSecrets \
  --targetNamespace atlas-operator | kubectl apply -f -

# Save to file for GitOps review
atlas kubernetes config generate \
  --projectId <projectId> \
  --includeSecrets \
  --targetNamespace atlas-operator > atlas-resources.yaml
```

**Flags for `atlas kubernetes config generate`:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--clusterName` | strings | — | Comma-separated cluster names to include |
| `--dataFederationName` | strings | — | Comma-separated data federation names |
| `--includeSecrets` | flag | false | Include API key data as Kubernetes secrets |
| `--independentResources` | flag | false | Use external IDs instead of K8s references |
| `--operatorVersion` | string | `2.13.0` | Target AKO version for resource generation |
| `--targetNamespace` | string | — | Kubernetes namespace for generated resources |
| `--orgId` | string | — | Override organization ID |
| `--projectId` | string | — | Override project ID |

### 7.2 Apply Kubernetes Configuration

`atlas kubernetes config apply` is the counterpart to `config generate`: instead of printing YAML to stdout, it directly creates or updates the Atlas Kubernetes Operator resources in the connected cluster. Use `config generate` when you want to review or commit the manifest first (GitOps); use `config apply` for direct one-shot application.

```bash
# Apply Atlas resources directly to the connected Kubernetes cluster
atlas kubernetes config apply --projectId <projectId>

# Apply with secrets, targeting a specific namespace
atlas kubernetes config apply \
  --projectId <projectId> \
  --includeSecrets \
  --targetNamespace atlas-operator

# Apply for specific clusters only
atlas kubernetes config apply \
  --projectId <projectId> \
  --clusterName cluster1,cluster2 \
  --targetNamespace atlas-operator
```

### 7.3 Install Atlas Kubernetes Operator

`atlas kubernetes operator install` installs AKO into your currently connected Kubernetes cluster and automatically creates a new API key, converts it to a Kubernetes secret, and configures the operator.

```bash
# Install latest AKO into current kubectl context
atlas kubernetes operator install

# Install to specific namespace
atlas kubernetes operator install \
  --targetNamespace atlas-operator

# Install specific AKO version
atlas kubernetes operator install \
  --operatorVersion 2.5.0 \
  --targetNamespace atlas-operator

# Install and import existing Atlas resources
atlas kubernetes operator install \
  --projectId <projectId> \
  --targetNamespace atlas-operator \
  --import
```

The install command:
1. Creates a new Atlas API key with appropriate permissions
2. Creates the API key as a Kubernetes secret in the target namespace
3. Deploys the AKO CRDs and operator deployment
4. Optionally imports existing Atlas resources as CRD manifests

**GitOps workflow with Atlas CLI + AKO:**
```bash
# Export existing cluster as K8s manifest
atlas kubernetes config generate \
  --projectId <projectId> \
  --clusterName prod-cluster \
  --includeSecrets \
  --targetNamespace atlas-operator \
  > gitops-repo/atlas/cluster.yaml

# Commit to GitOps repo, ArgoCD/Flux picks it up
git add gitops-repo/atlas/cluster.yaml
git commit -m "feat: export prod-cluster to AKO"
git push
```

---

## 8. CI/CD Automation Patterns

### 8.1 Environment Variables for Non-Interactive Auth

Never call `atlas auth login` in CI. Use environment variables instead:

```bash
# API Key authentication (recommended for most CI systems)
export MONGODB_ATLAS_PUBLIC_API_KEY="${{ secrets.ATLAS_PUBLIC_API_KEY }}"
export MONGODB_ATLAS_PRIVATE_API_KEY="${{ secrets.ATLAS_PRIVATE_API_KEY }}"
export MONGODB_ATLAS_PROJECT_ID="${{ secrets.ATLAS_PROJECT_ID }}"
export MONGODB_ATLAS_ORG_ID="${{ secrets.ATLAS_ORG_ID }}"

# Service Account (OAuth) authentication
export MONGODB_ATLAS_CLIENT_ID="${{ secrets.ATLAS_CLIENT_ID }}"
export MONGODB_ATLAS_CLIENT_SECRET="${{ secrets.ATLAS_CLIENT_SECRET }}"

# Suppress interactive prompts
export MONGODB_ATLAS_SKIP_UPDATE_CHECK=yes
```

### 8.2 GitHub Actions

MongoDB provides an official GitHub Action at `mongodb/atlas-github-action` (marketplace: "Atlas CLI GitHub Action"). It supports only Linux runners.

**Basic workflow — create ephemeral test cluster:**
```yaml
name: Integration Tests

on:
  push:
    branches: [main, 'feature/**']

env:
  MONGODB_ATLAS_PUBLIC_API_KEY: ${{ secrets.ATLAS_PUBLIC_API_KEY }}
  MONGODB_ATLAS_PRIVATE_API_KEY: ${{ secrets.ATLAS_PRIVATE_API_KEY }}
  MONGODB_ATLAS_ORG_ID: ${{ secrets.ATLAS_ORG_ID }}

jobs:
  integration-test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install Atlas CLI
        uses: mongodb/atlas-github-action@v0
        # or pin a specific version:
        # uses: mongodb/atlas-github-action@v0.2.0

      - name: Create project and cluster
        id: cluster
        run: |
          # Create project
          PROJECT_ID=$(atlas projects create "ci-${{ github.run_id }}" \
            --output json | jq -r '.id')
          echo "PROJECT_ID=$PROJECT_ID" >> $GITHUB_ENV

          # Add CI runner IP to access list (use specific IP, not 0.0.0.0/0)
          RUNNER_IP=$(curl -s https://api.ipify.org)
          atlas accessLists create --projectId "$PROJECT_ID" \
            --type ipAddress --ip "$RUNNER_IP"

          # Create cluster and wait for it to be ready
          atlas clusters create ciCluster \
            --projectId "$PROJECT_ID" \
            --provider AWS --region US_EAST_1 --tier M10 \
            --watch

          # Get connection string
          CONN_STR=$(atlas clusters connectionStrings describe ciCluster \
            --projectId "$PROJECT_ID" --output json | jq -r '.standardSrv')
          echo "CONN_STR=$CONN_STR" >> $GITHUB_ENV

          # Create test DB user
          atlas dbusers create readWriteAnyDatabase \
            --projectId "$PROJECT_ID" \
            --username ciUser --password "${{ secrets.CI_DB_PASSWORD }}"

      - name: Run integration tests
        run: npm test
        env:
          MONGODB_URI: "mongodb+srv://ciUser:${{ secrets.CI_DB_PASSWORD }}@${{ env.CONN_STR }}"

      - name: Teardown — always runs
        if: always()
        run: |
          atlas clusters delete ciCluster \
            --projectId "$PROJECT_ID" --force
          atlas projects delete "$PROJECT_ID" --force
```

**Using predefined workflows from the official action:**
```yaml
- name: Setup Atlas CLI (predefined workflow)
  uses: mongodb/atlas-github-action@v0
  with:
    project-id: ${{ secrets.ATLAS_PROJECT_ID }}
    public-api-key: ${{ secrets.ATLAS_PUBLIC_API_KEY }}
    private-api-key: ${{ secrets.ATLAS_PRIVATE_API_KEY }}
```

**Listing clusters with Service Account:**
```yaml
- name: List clusters
  run: |
    atlas clusters list \
      --projectId "$MONGODB_ATLAS_PROJECT_ID" \
      --output json
  env:
    MONGODB_ATLAS_CLIENT_ID: ${{ secrets.ATLAS_CLIENT_ID }}
    MONGODB_ATLAS_CLIENT_SECRET: ${{ secrets.ATLAS_CLIENT_SECRET }}
    MONGODB_ATLAS_PROJECT_ID: ${{ secrets.ATLAS_PROJECT_ID }}
```

### 8.3 Docker in CI

```dockerfile
# Dockerfile for CI image with Atlas CLI
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y curl gnupg && \
    curl -fsSL https://pgp.mongodb.com/server-7.0.asc | \
      gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor && \
    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] \
      https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
      tee /etc/apt/sources.list.d/mongodb-org-7.0.list && \
    apt-get update && apt-get install -y mongodb-atlas-cli
```

Or use the official Docker image directly:
```yaml
# GitLab CI example
integration:
  image: mongodb/atlas:latest
  script:
    - atlas clusters list --output json
  variables:
    MONGODB_ATLAS_PUBLIC_API_KEY: $ATLAS_PUBLIC_API_KEY
    MONGODB_ATLAS_PRIVATE_API_KEY: $ATLAS_PRIVATE_API_KEY
    MONGODB_ATLAS_PROJECT_ID: $ATLAS_PROJECT_ID
```

### 8.4 Scripting with JSON Output

Use `--output json` for machine-parseable output; pipe through `jq`:

```bash
# Get cluster status
STATUS=$(atlas clusters describe myCluster \
  --projectId "$ATLAS_PROJECT_ID" --output json | jq -r '.stateName')

# Extract connection string
CONN_STR=$(atlas clusters connectionStrings describe myCluster \
  --projectId "$ATLAS_PROJECT_ID" --output json | jq -r '.standardSrv')

# List cluster names only
atlas clusters list --projectId "$ATLAS_PROJECT_ID" --output json | \
  jq -r '.[].name'

# Check if cluster exists
if atlas clusters describe "$CLUSTER_NAME" --projectId "$ATLAS_PROJECT_ID" \
  --output json > /dev/null 2>&1; then
  echo "Cluster exists"
else
  echo "Cluster not found"
fi
```

### 8.5 Exit Codes and Error Handling

```bash
# Non-zero exit code on error — use in scripts
if ! atlas clusters create myCluster \
  --provider AWS --region US_EAST_1 --tier M10 --watch; then
  echo "Cluster creation failed" >&2
  exit 1
fi

# Combining watch with subsequent steps
atlas clusters create myCluster \
  --provider AWS --region US_EAST_1 --tier M10 --watch && \
  echo "Cluster ready, running migrations..." && \
  npm run db:migrate

# Always-cleanup pattern with trap
cleanup() {
  atlas clusters delete "$CLUSTER_NAME" \
    --projectId "$PROJECT_ID" --force || true
}
trap cleanup EXIT
```

---

## 9. Atlas Quickstart

`atlas setup` (canonical command; `atlas quickstart` is an alias) is an interactive wizard designed for rapid development cluster creation. It handles the complete setup flow in a single command.

### 9.1 What It Does

`atlas setup` performs:
1. Sign up or log into Atlas account
2. Create a free M0 cluster
3. Load sample data
4. Add your current IP to the access list
5. Create a database user
6. Connect via `mongosh`

### 9.2 Usage

```bash
# Full interactive setup (all prompts)
atlas setup

# Or the quickstart alias
atlas quickstart

# Fully automated (non-interactive)
atlas setup \
  --clusterName myDevCluster \
  --provider AWS \
  --region US_EAST_1 \
  --username myUser \
  --password "DevPassword123!" \
  --skipSampleData \
  --skipMongosh

# Skip sample data loading (faster)
atlas setup --skipSampleData

# Skip mongosh connection at the end
atlas setup --skipMongosh

# Specify MongoDB version
atlas setup --mdbVersion 7.0

# Tag the cluster
atlas setup --clusterName myCluster --tag purpose=dev

# Connect with specific method
atlas setup --connectWith mongosh
```

**Default M0 cluster configuration from `atlas setup`:**
```
Cluster name:     Cluster<number>
Cloud provider:   AWS - US_EAST_1
Username:         Cluster<number>
Password:         (auto-generated)
Sample data:      loaded
IP access:        <your-current-IP>
```

### 9.3 Development Workflow

```bash
# Start a fresh development environment in under 5 minutes
atlas setup --skipSampleData --clusterName devLocal

# Get the connection string after setup
atlas clusters connectionStrings describe devLocal \
  --output json | jq -r '.standardSrv'

# Load sample data later
atlas clusters loadSampleData devLocal

# Connect with mongosh
mongosh "$(atlas clusters connectionStrings describe devLocal \
  --output json | jq -r '.standardSrv')" \
  --username <yourUser>
```

---

## 10. Anti-Patterns

### 10.1 Hardcoded API Keys in Scripts

**Wrong:**
```bash
# NEVER do this — exposes credentials in script/repo
# (Atlas CLI has no --publicApiKey flag; the wrong pattern is storing
#  keys in plaintext in a wrapper script or config file)
export MONGODB_ATLAS_PUBLIC_API_KEY="abc123def456"    # hardcoded in script
export MONGODB_ATLAS_PRIVATE_API_KEY="789xyz..."      # committed to repo
atlas clusters list
```

**Correct:**
```bash
# Inject from the CI platform's secrets store — never hardcode values
export MONGODB_ATLAS_PUBLIC_API_KEY="$ATLAS_PUB_KEY"   # sourced from env
export MONGODB_ATLAS_PRIVATE_API_KEY="$ATLAS_PRIV_KEY"
atlas clusters list
```

Rotate credentials periodically. In CI, use platform secrets (GitHub Secrets, GitLab CI Variables, AWS Secrets Manager). For dynamic credentials, consider HashiCorp Vault's MongoDB Atlas secrets engine which creates time-limited, auto-revoked API keys.

### 10.2 Missing `--watch` in CI (Race Condition)

**Wrong:**
```bash
# Cluster is still provisioning when next command runs
atlas clusters create myCluster --provider AWS --region US_EAST_1 --tier M10
npm run db:migrate   # FAILS — cluster not ready yet
```

**Correct:**
```bash
# Block until IDLE state before proceeding
atlas clusters create myCluster \
  --provider AWS --region US_EAST_1 --tier M10 --watch
npm run db:migrate   # Now safe
```

The same pattern applies after `atlas clusters update` on operations that change cluster state.

### 10.3 Not Using `--output json` for Parsing

**Wrong:**
```bash
# Parsing human-readable text output is fragile
CLUSTER_ID=$(atlas clusters describe myCluster | grep "ID:" | awk '{print $2}')
```

**Correct:**
```bash
# Use --output json and jq for robust parsing
CLUSTER_ID=$(atlas clusters describe myCluster \
  --output json | jq -r '.id')
```

### 10.4 Deleting Clusters Without Force Guard in CI

**Wrong:**
```bash
# Interactive prompt will hang the CI job
atlas clusters delete myCluster --projectId "$PROJECT_ID"
```

**Correct:**
```bash
# Always use --force in non-interactive CI scripts
atlas clusters delete myCluster --projectId "$PROJECT_ID" --force
```

Protect against variable expansion mistakes with a guard:
```bash
if [[ -z "$CLUSTER_NAME" ]]; then
  echo "ERROR: CLUSTER_NAME is empty, refusing to delete" >&2
  exit 1
fi
atlas clusters delete "$CLUSTER_NAME" --projectId "$PROJECT_ID" --force
```

### 10.5 Using 0.0.0.0/0 in Production Access Lists

**Wrong:**
```bash
# Opens Atlas to the entire internet
atlas accessLists create --type cidrBlock --ip "0.0.0.0/0"
```

**Correct:**
```bash
# Add only the specific IPs/CIDRs that need access
atlas accessLists create --type cidrBlock --ip "10.0.0.0/8"

# For CI agents, use --deleteAfterDate to auto-expire access
atlas accessLists create --type ipAddress --ip "$CI_RUNNER_IP" \
  --deleteAfterDate "$(date -u -d '+1 hour' +%Y-%m-%dT%H:%M:%SZ)"
```

### 10.6 Not Cleaning Up Test Clusters

**Wrong:**
```bash
# Test cluster created but never deleted — costs money
atlas clusters create ciCluster --tier M10 --watch
npm test
# Script ends without deleting cluster
```

**Correct:**
```bash
# Always use trap to clean up on exit
CLUSTER_NAME="ci-$GITHUB_RUN_ID"
cleanup() {
  echo "Cleaning up test cluster..."
  atlas clusters delete "$CLUSTER_NAME" \
    --projectId "$ATLAS_PROJECT_ID" --force || true
}
trap cleanup EXIT INT TERM

atlas clusters create "$CLUSTER_NAME" --tier M10 --watch
npm test
```

### 10.7 Running `atlas auth login` in CI

`atlas auth login` requires an interactive browser flow and will hang a CI job. Use environment variables instead — see §8.1 for the full non-interactive auth pattern.

**Wrong:**
```bash
atlas auth login   # hangs — no browser available in CI
atlas clusters list
```

**Correct:**
```bash
# No login call needed; CLI authenticates from env vars automatically
export MONGODB_ATLAS_PUBLIC_API_KEY="$SECRET_PUB_KEY"
export MONGODB_ATLAS_PRIVATE_API_KEY="$SECRET_PRIV_KEY"
atlas clusters list
```

### 10.8 Ignoring Exit Codes

**Wrong:**
```bash
# If cluster creation fails silently, subsequent commands will error with confusing messages
atlas clusters create myCluster --provider AWS --region US_EAST_1 --tier M10
atlas clusters watch myCluster
atlas dbusers create readWriteAnyDatabase --username app
```

**Correct:**
```bash
# Use set -e or explicit error handling
set -euo pipefail

atlas clusters create myCluster \
  --provider AWS --region US_EAST_1 --tier M10 --watch || {
  echo "Cluster creation failed" >&2
  exit 1
}
```

---

## References and Sources

1. [Atlas CLI Documentation — Official](https://www.mongodb.com/docs/atlas/cli/current/) — Main reference
2. [Install or Update the Atlas CLI](https://www.mongodb.com/docs/atlas/cli/current/install-atlas-cli/) — Installation guide
3. [Connect from the Atlas CLI](https://www.mongodb.com/docs/atlas/cli/current/connect-atlas-cli/) — Auth methods
4. [Atlas CLI Environment Variables](https://www.mongodb.com/docs/atlas/cli/current/atlas-cli-env-variables/) — Full env var list
5. [atlas clusters — Command Reference](https://www.mongodb.com/docs/atlas/cli/current/command/atlas-clusters/) — Cluster commands
6. [atlas backups — Command Reference](https://www.mongodb.com/docs/atlas/cli/current/command/atlas-backups/) — Backup commands
7. [atlas dbusers — Command Reference](https://www.mongodb.com/docs/atlas/cli/current/command/atlas-dbusers/) — User management
8. [atlas clusters search indexes create](https://www.mongodb.com/docs/atlas/cli/current/command/atlas-clusters-search-indexes-create/) — Search index creation
9. [atlas kubernetes config generate](https://www.mongodb.com/docs/atlas/cli/current/command/atlas-kubernetes-config-generate/) — K8s CRD generation
10. [Atlas CLI GitHub Action — GitHub Marketplace](https://github.com/marketplace/actions/atlas-cli-github-action) — Official GitHub Action
11. [mongodb/atlas-github-action README](https://github.com/mongodb/atlas-github-action/blob/main/README.md) — GitHub Actions patterns
12. [Perfect CI/CD Pipelines with MongoDB Atlas CLI — MongoDB Blog](https://www.mongodb.com/blog/post/perfect-ci-cd-pipelines-mongodbs-new-github-action-docker-image-atlas-cli) — CI/CD patterns
13. [atlas streams — Command Reference](https://www.mongodb.com/docs/atlas/cli/current/command/atlas-streams/) — Stream Processing
14. [atlas kubernetes operator — Command Reference](https://www.mongodb.com/docs/atlas/cli/stable/command/atlas-kubernetes-operator/) — AKO install
15. [7 Best Practices for MongoDB Atlas Credentials — DEV Community](https://dev.to/arunangshu_das/7-best-practices-for-mongodb-atlas-credentials-in-the-cloud-2c6l) — Security practices

## See Also

- [[mongodb-atlas-expert]] — Deep Atlas platform knowledge
- [[mongodb-atlas-terraform]] — Infrastructure-as-code with Terraform provider
- [[mongodb-atlas-kubernetes-operator]] — AKO CRD management and GitOps
