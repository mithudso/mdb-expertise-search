<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-security-architecture` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

# MongoDB Security Architecture
<!-- version: 1.1.0 | updated: 2026-05-28 | covers: Atlas + self-managed 6.0–8.0 -->

## Overview

This skill covers the full MongoDB security stack — from client authentication through network isolation, RBAC, audit logging, secrets management, and compliance posture hardening. It applies equally to Atlas-managed clusters and self-managed deployments, calling out differences throughout.

**Use this skill when:**
- Designing or reviewing authentication architecture for a MongoDB deployment
- Configuring RBAC roles at any granularity level (org, project, cluster, collection)
- Setting up or troubleshooting audit logging and SIEM forwarding
- Hardening network access (IP lists, VPC peering, private endpoints)
- Evaluating or configuring BYOK/CMK encryption at rest
- Managing secrets and credential rotation for MongoDB credentials
- Performing a security posture review or pre-compliance audit

**Do not use this skill when:**
- You need deep CSFLE or Queryable Encryption implementation details → use [[mongodb-encryption]]
- You need compliance framework mapping (SOC 2, PCI DSS, HIPAA controls) → use [[mongodb-compliance]]
- You need Atlas-specific Azure networking or Azure Key Vault CMK → use [[mongodb-atlas-azure]]
- You need Atlas-specific GCP networking or Cloud KMS CMK → use [[mongodb-atlas-gcp]]

---

## 1. Authentication Methods Comparison Matrix

### Method Summary

| Method | Protocol | User Type | Atlas Support | Self-Managed | Recommended Environments |
|---|---|---|---|---|---|
| SCRAM-SHA-256 | Password challenge-response | Both | Yes | Yes (default) | Dev/test only; avoid in production |
| SCRAM-SHA-1 | Password challenge-response (legacy) | Both | Legacy only | Yes (deprecated) | Avoid — upgrade to SCRAM-SHA-256 |
| X.509 Client Certificates | Mutual TLS (mTLS) | Both | Yes | Yes | Staging, production |
| LDAP (PLAIN SASL) | LDAP proxy | Both | Yes (M10+) | Yes (Enterprise) | Enterprises with LDAP directories |
| OIDC — Workforce Identity | OpenID Connect | Human users | Yes | Yes (7.0+) | Production — human/developer SSO |
| OIDC — Workload Identity | OAuth 2.0 | Applications | Yes | Yes (7.0+) | Production — apps on Azure, GCP, OAuth IdPs |
| AWS IAM | SigV4 + IAM roles/users | Workloads | Yes | No | AWS-native applications |
| Kerberos (GSSAPI) | Kerberos tickets | Both | No | Yes (Enterprise) | On-prem enterprise with Active Directory |
| Service Accounts (OAuth 2.0) | OAuth 2.0 tokens | API/automation | Yes (Atlas API) | N/A | Atlas Admin API automation |

### SCRAM-SHA-256

MongoDB's default authentication mechanism since MongoDB 4.0. Uses a salted challenge-response protocol with SHA-256 hashing. The server performs password hashing server-side. SCRAM-SHA-1 is the legacy variant (SHA-1 hashing) and should be avoided in new deployments.

**When to use:** Development and testing environments only. For production, prefer X.509, OIDC, or AWS IAM.

**Config (mongod.conf):**
```yaml
security:
  authorization: enabled
  authenticationMechanisms: SCRAM-SHA-256
```

**Driver connection string:**
```
mongodb://username:password@host:27017/authdb?authMechanism=SCRAM-SHA-256
```

### X.509 Client Certificate Authentication

Clients authenticate with TLS certificates instead of passwords. The authentication database is `$external`. MongoDB matches the certificate's Subject DN to the username. Supports mutual TLS (mTLS) — both client and server present certificates.

**When to use:** Staging and production. Suitable for both Atlas and self-managed. Requires certificate lifecycle management on the application side.

**Atlas setup:**
1. Upload your CA certificate to Atlas project settings
2. Create database users with X.509 auth and set the Subject DN as the username
3. Application connects with client certificate in the connection string

**Driver connection string:**
```
mongodb://host:27017/?authMechanism=MONGODB-X509&tls=true&tlsCertificateKeyFile=/path/to/client.pem
```

**Self-managed mongod.conf:**
```yaml
net:
  tls:
    mode: requireTLS
    certificateKeyFile: /etc/ssl/mongodb/server.pem
    CAFile: /etc/ssl/mongodb/ca.pem
security:
  authorization: enabled
  authenticationMechanisms: MONGODB-X509
```

### LDAP (PLAIN SASL)

MongoDB Enterprise and Atlas proxy authentication requests to an external LDAP server. User credentials (or group membership for authorization) are validated against the LDAP directory. Supports both LDAP authentication and LDAP authorization (role-mapping from LDAP groups to MongoDB roles).

**When to use:** Enterprises with existing LDAP/Active Directory infrastructure needing centralized user management. Not available in self-managed Community edition.

**Atlas:** Configure under Security > Advanced > LDAP Configuration. Requires M10+ clusters.

**Self-managed mongod.conf:**
```yaml
security:
  ldap:
    servers: "ldap.example.com"
    transportSecurity: tls
    bind:
      method: simple
      queryUser: "cn=service,dc=example,dc=com"
      queryPassword: "<store-in-secrets-manager-not-plaintext>"
    userToDNMapping: '[{match: "(.+)", substitution: "uid={0},ou=users,dc=example,dc=com"}]'
    authz:
      queryTemplate: "{USER}?memberOf?base"
  authorization: enabled
  authenticationMechanisms: PLAIN
```

### OIDC — Workforce Identity Federation

OIDC-based authentication for human users (developers, DBAs, administrators). Users authenticate via an identity provider (Okta, Microsoft Entra ID, Ping Identity) and receive a database session without managing a separate MongoDB password.

**When to use:** Production environments. Eliminates per-user database passwords for human access. Supports just-in-time (JIT) provisioning of temporary database users.

**Supported IdPs:** Okta, Microsoft Entra ID, Ping Identity, any OIDC-compliant IdP.

**Atlas setup:** Security > Advanced > Workforce Identity Federation. Map IdP groups to Atlas RBAC roles.

**Constraints:** Cannot use when LDAP authorization is enabled. Cannot change a user's auth method after creation — must create a new user.

### OIDC — Workload Identity Federation (OAuth 2.0)

Passwordless authentication for applications using cloud provider service identities. Applications running on Azure (Managed Identities), GCP (Service Accounts), or any OAuth 2.0-compliant platform authenticate without embedding credentials.

**When to use:** Production applications on Azure or GCP. Eliminates long-lived credentials from application configuration.

**Atlas setup:** Security > Advanced > Workload Identity Federation. Configure audience and issuer URL matching your cloud provider.

### AWS IAM Authentication

Applications running on AWS infrastructure (EC2, ECS, Lambda, etc.) authenticate to Atlas using IAM roles or IAM user credentials via SigV4 signing. The authentication database is `$external`.

**When to use:** AWS-native application workloads. Best when combined with IAM roles (not long-lived IAM user credentials).

**Atlas setup:** Create database users with AWS IAM auth type, specify ARN for the IAM role or user.

**Connection string:**
```
mongodb+srv://host/?authMechanism=MONGODB-AWS&authSource=$external
```

Environment variables `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optionally `AWS_SESSION_TOKEN` are used automatically from the instance metadata service when using IAM roles.

### Kerberos (GSSAPI)

Kerberos single sign-on for MongoDB Enterprise self-managed deployments. Integrates with Active Directory Kerberos infrastructure. Not available in MongoDB Atlas.

**When to use:** On-premises enterprise deployments with Active Directory and existing Kerberos infrastructure. Not supported on Atlas.

**mongod.conf:**
```yaml
security:
  authorization: enabled
  authenticationMechanisms: GSSAPI
setParameter:
  saslHostName: mongodb.example.com
  saslServiceName: mongodb
```

### Service Accounts (OAuth 2.0) — Atlas Admin API

For programmatic Atlas Administration API access by automation, CI/CD pipelines, and Terraform. Service accounts issue short-lived access tokens and require secret rotation. Preferred over legacy API keys.

**Best practice:** Assign minimum required Atlas project/org roles. Enable IP access list on the service account. Rotate secrets before expiration using a secrets manager.

---

## 2. Atlas Database Access Authentication

Atlas offers multiple authentication mechanisms for database-level access. Key constraints:
- Cannot use both LDAP and SCRAM for the same database user
- Cannot use OIDC when LDAP authorization is enabled
- Cannot change a user's authentication method after creation

### Authentication Method Decision Tree

```
Is the user a human (developer/DBA)?
├── Yes: Use Workforce OIDC → maps SSO identity to temporary DB user
│         Fallback for dev/test only: SCRAM with secrets manager
└── No (application workload):
    ├── Running on AWS? → AWS IAM authentication
    ├── Running on Azure or GCP? → Workload OIDC (OAuth 2.0)
    ├── Need mTLS? → X.509 client certificates
    └── Everything else (dev/test) → SCRAM with Vault/Secrets Manager rotation
```

### Temporary Database Users (Just-in-Time Access)

Atlas supports creating database users with automatic expiration:
- **Durations:** 6 hours, 1 day, 1 week
- **Use case:** Human operators needing break-glass access; CI/CD pipelines for short jobs
- **UI:** Database Access > Add New Database User > Temporary User

```bash
# Atlas CLI — create temporary SCRAM user (6-hour TTL)
# macOS (BSD date):
atlas dbusers create \
  --username ci-pipeline \
  --password "$(openssl rand -base64 32)" \
  --role readWrite@mydb \
  --deleteAfter $(date -u -v+6H +%Y-%m-%dT%H:%M:%SZ) \
  --projectId <project-id>

# Linux (GNU date):
atlas dbusers create \
  --username ci-pipeline \
  --password "$(openssl rand -base64 32)" \
  --role readWrite@mydb \
  --deleteAfter $(date -u -d '+6 hours' +%Y-%m-%dT%H:%M:%SZ) \
  --projectId <project-id>
```

### X.509 Self-Managed Certificate Users (Atlas)

1. Navigate to Security > Advanced > Client Certificate Authentication
2. Upload your CA certificate PEM
3. Create users: Database Access > Add New User > Certificate > enter Subject DN

```bash
# Subject DN format for user creation
/CN=app-service/O=MyOrg/L=New York/ST=NY/C=US
```

### AWS IAM Database Users (Atlas)

```bash
# Atlas CLI — create IAM role database user
atlas dbusers create \
  --username "arn:aws:iam::123456789012:role/my-app-role" \
  --authDatabase "\$external" \
  --awsIAMType ROLE \
  --role readWrite@mydb
```

### LDAP/OIDC Atlas Configuration Notes

- LDAP requires M10+ clusters and Atlas Enterprise
- OIDC Workforce: Go to Security > Workforce Identity Federation; add OIDC IdP, configure the Audience claim and Issuer URI
- OIDC Workload: Go to Security > Workload Identity Federation; configure cloud provider OIDC endpoint

---

## 3. RBAC Design Patterns

MongoDB Atlas has two distinct RBAC layers: **Atlas control plane access** (org/project roles for Atlas UI and API) and **database-level access** (cluster roles for data operations).

### Atlas Control Plane Roles (Org Level)

| Role | Purpose | Recommended Assignment |
|---|---|---|
| Organization Owner | Full org control | Service account only; break-glass SAML JIT group |
| Organization Member | View org settings | Ops/platform team admins |
| Organization Project Creator | Create projects programmatically | Dedicated service account per dev team |
| Organization Billing Admin | Access billing API | FinOps service account |
| Organization Read Only | View org-level resources | Auditors, read-only observers |

### Atlas Control Plane Roles (Project Level)

| Role | Purpose | Notes |
|---|---|---|
| Project Owner | Full cluster/project management | Restrict to service accounts in prod |
| Project Cluster Manager | Manage clusters but not project settings | Platform engineering teams |
| Project Data Access Admin | Full DB user and data management | DBA team |
| Project Data Access Read/Write | Data read/write without schema changes | Application teams (use sparingly) |
| Project Data Access Read Only | Read-only data access | Analysts, monitoring |
| Project Read Only | View project without modifications | Auditors, developers (view only) |
| Project Network Access Admin | Manage IP access lists and private endpoints | Network/security team |

### Database-Level Built-In Roles

**Read/Write Roles:**
| Role | Scope | Permissions |
|---|---|---|
| `read` | Database | Find, list collections, aggregate on all collections |
| `readWrite` | Database | read + insert, update, delete, createCollection, createIndex |
| `readAnyDatabase` | All databases | read on all databases (admin db only) |
| `readWriteAnyDatabase` | All databases | readWrite on all databases (admin db only) |

**Admin Roles (grant with extreme caution):**
| Role | Scope | Permissions |
|---|---|---|
| `dbAdmin` | Database | Schema management, index management, stats — no data read/write |
| `dbAdminAnyDatabase` | All databases | dbAdmin on all databases |
| `userAdmin` | Database | Create/modify users and roles |
| `userAdminAnyDatabase` | All databases | userAdmin on all databases |
| `clusterAdmin` | Cluster | Full cluster management including shutdown, replSetReconfig |
| `clusterMonitor` | Cluster | Read-only cluster monitoring |
| `hostManager` | Cluster | Manage mongod processes |
| `backup` | Cluster | Backup operations |
| `restore` | Cluster | Restore operations |

**Superuser (never use for applications):**
| Role | Permissions |
|---|---|
| `root` | Superuser — combines readWriteAnyDatabase, dbAdminAnyDatabase, userAdminAnyDatabase, clusterAdmin |

### Custom Roles — Collection-Level Granularity

Built-in roles like `readWrite` grant access to all collections in a database. For least-privilege, create custom roles scoped to specific collections.

**Atlas UI:** Database Access > Custom Roles > Add New Custom Role

**Example: read-only on specific collections:**
```javascript
// Custom role: orders-reader
{
  "roleName": "orders-reader",
  "privileges": [
    {
      "resource": { "db": "ecommerce", "collection": "orders" },
      "actions": ["find"]
    },
    {
      "resource": { "db": "ecommerce", "collection": "order_items" },
      "actions": ["find"]
    }
  ],
  "inheritedRoles": []
}
```

**Terraform:**
```hcl
resource "mongodbatlas_custom_db_role" "orders_reader" {
  project_id = var.project_id
  role_name  = "orders-reader"

  actions {
    action = "FIND"
    resources {
      collection_name = "orders"
      database_name   = "ecommerce"
    }
  }
  actions {
    action = "FIND"
    resources {
      collection_name = "order_items"
      database_name   = "ecommerce"
    }
  }
}
```

**Assign to database user:**
```hcl
resource "mongodbatlas_database_user" "app_service" {
  project_id         = var.project_id
  username           = "app-service"
  password           = var.db_password
  auth_database_name = "admin"

  roles {
    role_name     = mongodbatlas_custom_db_role.orders_reader.role_name
    database_name = "ecommerce"
  }
}
```

### Role Inheritance and Conflict Resolution

- A role can inherit from other roles (`inheritedRoles` array in custom role definition)
- If a user has multiple roles that grant conflicting permissions, Atlas honors the **highest permission** within any assigned role
- Roles are scoped to a specific database — a role defined on `ecommerce` does not apply to `analytics`

### Least-Privilege Design Patterns

1. **One service account per application** — do not share credentials between services
2. **Scope to minimum collections** — use custom roles with collection-level resources, not built-in `readWrite`
3. **Separate read and write roles** — most services need read on more collections than they write to
4. **Never assign `root` or `clusterAdmin` to application users**
5. **Use JIT temporary users** for human operators instead of permanent SCRAM users
6. **Provision with IaC** (Terraform, Atlas Kubernetes Operator) — prevents role drift
7. **Regular access review** — audit unused users every 30-90 days
8. **Scope Atlas project roles** — application teams should have `Project Data Access Read/Write` or narrower; only platform teams get `Project Owner`

### Role Mapping from IdP Groups (OIDC/SAML JIT)

When using Federated Authentication or Workforce OIDC, map IdP groups to Atlas roles to enable JIT provisioning:

**Atlas UI:** Security > Manage Federated Authentication > Role Mapping

Example mapping:
- IdP group `atlas-db-admins` → Atlas role `Project Data Access Admin`
- IdP group `atlas-developers` → Atlas role `Project Data Access Read/Write`
- IdP group `atlas-readers` → Atlas role `Project Data Access Read Only`

---

## 4. Network Security Layers

Atlas applies defense-in-depth with multiple network security controls. For production, combine private networking with IP access list restrictions.

### Layer 1: TLS Encryption (Mandatory)

All connections to Atlas clusters are protected by TLS. It cannot be disabled.

- **Default:** TLS 1.2
- **Available:** TLS 1.3 (rolling out fleet-wide as of 2025)
- **Enforcement:** As of July 31, 2025, Atlas no longer supports TLS 1.0 or 1.1
- **Certificate Authority:** Let's Encrypt or Google Trust Services (auto-rotated by Atlas)
- **Custom cipher suites:** Available for enterprise compliance requirements (select specific cipher suites in cluster additional settings)

**Set minimum TLS version (Terraform):**
```hcl
resource "mongodbatlas_advanced_cluster" "prod" {
  # ...
  advanced_configuration {
    minimum_enabled_tls_protocol = "TLS1_2"
  }
}
```

### Layer 2: IP Access Lists

Every Atlas project maintains an IP access list. All access is blocked by default; connections are only allowed from explicitly listed IPs/CIDRs.

**Best practices:**
- Use `/32` for individual application servers — never use `0.0.0.0/0` in production
- Create temporary entries (with expiration) for break-glass scenarios
- Maintain separate IP access lists for API keys/service accounts
- Atlas supports up to 200 IP access list entries per project

```bash
# Add a specific IP
atlas accessList create 10.0.1.50 \
  --type ipAddress \
  --comment "app-server-1 prod" \
  --projectId <project-id>

# Add a CIDR range
atlas accessList create 10.0.1.0/24 \
  --type cidrBlock \
  --comment "prod VPC subnet" \
  --projectId <project-id>
```

**Terraform:**
```hcl
resource "mongodbatlas_project_ip_access_list" "app_server" {
  project_id = var.project_id
  ip_address = "10.0.1.50"
  comment    = "app-server-1"
}
```

### Layer 3: VPC/VNet Peering

Establishes a private routing path between your VPC and the Atlas VPC. Traffic stays on the cloud provider's backbone and never traverses the public internet.

- **Mapping:** One-to-one between Atlas project and customer VPC
- **CIDR requirement:** Atlas VPC CIDR must not overlap with your VPC CIDR
- **Supported clouds:** AWS, Azure, Google Cloud
- **Security groups/ACLs:** Apply additional restrictions on the peering connection from your side

```bash
# Create AWS VPC peering connection
atlas networking peering create aws \
  --accountId 123456789012 \
  --atlasCidrBlock 192.168.0.0/24 \
  --region us-east-1 \
  --routeTableCidrBlock 10.0.0.0/16 \
  --vpcId vpc-0abc1234
```

### Layer 4: Private Endpoints (Recommended for Production)

Private endpoints create a private IP address in your VPC that routes directly to Atlas. No public IP exposure, no public internet traversal. One-way connection: your VPC initiates connections to Atlas; Atlas cannot initiate connections back.

| Cloud | Technology | Atlas Tier |
|---|---|---|
| AWS | PrivateLink | M10+ |
| Azure | Private Link | M10+ |
| GCP | Private Service Connect | M10+ |

**Setup flow:**
1. Create private endpoint in Atlas (Atlas creates an endpoint service)
2. Create corresponding endpoint resource in your cloud provider's VPC
3. Register the cloud provider endpoint ID with Atlas
4. Switch application connection string to the private SRV endpoint

```bash
# Step 1: Create Atlas endpoint service
atlas privateEndpoints aws create \
  --region us-east-1 \
  --projectId <project-id>

# Step 2: (In AWS console/CLI) Create VPC endpoint targeting the service name from step 1

# Step 3: Register with Atlas
atlas privateEndpoints aws interfaces create \
  <endpoint-service-id> \
  --privateEndpointId vpce-0abc1234 \
  --projectId <project-id>
```

### Layer 5: Disabling Public Internet Access

For maximum security, remove all public IP access list entries after establishing private endpoints:

1. Set up private endpoints (or VPC peering) in all regions where your Atlas cluster operates
2. Remove `0.0.0.0/0` and any public IP entries from the project IP access list
3. Add only private endpoint IPs or peered VPC CIDR ranges to the access list

**Atlas Resource Policies (org-level enforcement):**
Atlas Resource Policies allow organizations to enforce network security requirements across all projects, preventing project owners from inadvertently opening up public access. Apply policies via the Atlas Admin API or Terraform.

---

## 5. Atlas Audit Logging

Atlas audit logging is available on M10+ dedicated clusters. It captures DDL, DML, DCL, and authentication events.

### Enabling Audit Logging

**Atlas UI:** Security > Database Auditing > Enable

**Atlas CLI:**
```bash
atlas auditing update \
  --enabled \
  --auditFilter '{"atype": {"$in": ["authenticate", "authCheck", "createCollection", "dropCollection"]}}' \
  --projectId <project-id>
```

**Terraform:**
```hcl
resource "mongodbatlas_auditing" "project_auditing" {
  project_id                 = var.project_id
  enabled                    = true
  audit_authorization_success = false  # true significantly impacts performance
  audit_filter = jsonencode({
    "$or" = [
      { "atype" = { "$in" = ["authenticate", "logout", "authCheck"] } },
      { "atype" = { "$in" = ["createCollection", "dropCollection", "createIndex", "dropIndex"] } },
      { "atype" = { "$in" = ["createUser", "dropUser", "updateUser", "grantRolesToUser", "revokeRolesFromUser"] } },
      { "atype" = { "$in" = ["replSetReconfig", "shutdown"] } }
    ]
  })
}
```

### Filter Syntax Reference

Audit filters use MongoDB query predicate syntax against the audit message document fields.

**Key filter fields:**

| Field | Description | Example Values |
|---|---|---|
| `atype` | Action type | `authenticate`, `authCheck`, `createCollection`, `dropCollection`, `createIndex`, `dropIndex`, `createUser`, `dropUser`, `updateUser`, `logout`, `replSetReconfig` |
| `param.db` | Database name | `"mydb"` |
| `param.ns` | Namespace (db.collection) | `"mydb.orders"` |
| `param.command` | Command name (with authCheck) | `"find"`, `"insert"`, `"update"`, `"delete"`, `"aggregate"` |
| `roles` | User roles at operation time | `{"role": "readWrite", "db": "mydb"}` |
| `users` | Users performing operation | `[{"user": "alice", "db": "admin"}]` |

**Common filter patterns:**

```json
// All authentication events
{ "atype": "authenticate" }

// Authentication on a specific database
{ "atype": "authenticate", "param.db": "mydb" }

// All CRUD operations (requires auditAuthorizationSuccess: true — use carefully)
{
  "atype": "authCheck",
  "param.command": { "$in": ["find", "insert", "update", "delete", "findAndModify"] }
}

// Schema-change events only
{
  "atype": { "$in": ["createCollection", "dropCollection", "createIndex", "dropIndex", "collMod", "dropDatabase"] }
}

// User management events
{
  "atype": { "$in": ["createUser", "dropUser", "updateUser", "grantRolesToUser", "revokeRolesFromUser", "createRole", "dropRole"] }
}

// Multiple conditions with $or
{
  "$or": [
    { "atype": "authenticate" },
    { "atype": { "$in": ["createCollection", "dropCollection"] }, "param.ns": { "$regex": "^production\\." } }
  ]
}

// Filter by user role
{ "roles": { "$elemMatch": { "role": "readWrite", "db": "production" } } }

// CRUD on specific collection only
{
  "atype": "authCheck",
  "param.ns": "mydb.financial_transactions",
  "param.command": { "$in": ["find", "insert", "update", "delete"] }
}
```

### Recommended Minimum Audit Events

At minimum, audit:
- Failed and successful logins (`authenticate`)
- Logout events (`logout`)
- Unauthorized operation attempts (`authCheck` with failed authorization)
- User/role management changes (`createUser`, `dropUser`, `updateUser`, `grantRolesToUser`)
- Schema changes (`createCollection`, `dropCollection`, `createIndex`, `dropIndex`)
- Database configuration changes (`collMod`, `replSetReconfig`)
- Backup/restore operations

### Performance Considerations

- `auditAuthorizationSuccess: false` (default) — only failed authorization attempts are logged for `authCheck`; minimal performance impact
- `auditAuthorizationSuccess: true` — logs every authorized operation; **significant performance impact**; use only when compliance requires full CRUD audit trail
- Disable auditing in development environments unless required

### SIEM Integration and Log Forwarding

**Atlas Log Integration (OpenTelemetry):**
Atlas supports native log streaming to major observability platforms:
- Amazon S3 (every 5 minutes)
- Splunk (via OpenTelemetry collector or MongoDB Atlas receiver)
- Datadog
- Google Cloud Logging
- Microsoft Azure Monitor
- Any OpenTelemetry-compatible endpoint

**Atlas UI:** Integrations > Log Export > select destination

**Log types available for export:** `mongod`, `mongos`, `audit`

**S3 export (Terraform):**
```hcl
resource "mongodbatlas_push_based_log_export" "audit_export" {
  project_id  = var.project_id
  bucket_name = "my-audit-logs-bucket"
  iam_role_id = mongodbatlas_cloud_provider_access_authorization.this.role_id
  prefix_path = "mongodb-audit/"
}
```

**Splunk — MongoDB Atlas receiver configuration:**
```yaml
receivers:
  mongodbatlas:
    public_key: ${ATLAS_PUBLIC_KEY}
    private_key: ${ATLAS_PRIVATE_KEY}
    alerts:
      enabled: true
    logs:
      projects:
        - project_id: <project-id>
          collect_audit_logs: true
```

---

## 6. Self-Managed MongoDB Security Configuration

### Core Security Settings (mongod.conf)

```yaml
# /etc/mongod.conf — security hardening
net:
  port: 27017
  bindIp: 127.0.0.1,10.0.1.50   # Never bind to 0.0.0.0 unless required
  tls:
    mode: requireTLS              # Options: disabled, allowTLS, preferTLS, requireTLS
    certificateKeyFile: /etc/ssl/mongodb/server.pem
    CAFile: /etc/ssl/mongodb/ca.pem
    allowConnectionsWithoutCertificates: false
    disabledProtocols: TLS1_0,TLS1_1  # Force TLS 1.2+

security:
  authorization: enabled
  authenticationMechanisms: SCRAM-SHA-256  # Comma-separate for multiple
  javascriptEnabled: false                 # Disable server-side JS if not needed
  keyFile: /etc/ssl/mongodb/keyfile        # For keyfile-based internal auth

storage:
  dbPath: /var/lib/mongodb
  wiredTiger:
    engineConfig:
      cacheSizeGB: 2

operationProfiling:
  mode: slowOp
  slowOpThresholdMs: 100

setParameter:
  enableLocalhostAuthBypass: 0   # Disable after initial user setup
```

### Internal Authentication: Keyfile vs. X.509

**Keyfile authentication** (simpler, suitable for most deployments):
- All replica set members share the same keyfile (minimum 6 characters, up to 1024 characters, base64 content)
- File must have permission `400` or `600` (owner-read only on UNIX)
- Rotate by performing a rolling restart with a new keyfile

```bash
# Generate a keyfile
openssl rand -base64 756 > /etc/ssl/mongodb/keyfile
chmod 400 /etc/ssl/mongodb/keyfile
chown mongod:mongod /etc/ssl/mongodb/keyfile
```

```yaml
security:
  keyFile: /etc/ssl/mongodb/keyfile
  clusterAuthMode: keyFile
```

**X.509 internal authentication** (stronger, recommended for production):
- Each replica set member uses its own X.509 certificate for inter-member authentication (mTLS)
- Single CA must sign all member certificates
- Subject Alternative Name (SAN) in each certificate must match the hostname used by other members
- Preferred over keyfiles; upgrade path is rolling and non-disruptive

```yaml
net:
  tls:
    mode: requireTLS
    certificateKeyFile: /etc/ssl/mongodb/member.pem
    CAFile: /etc/ssl/mongodb/ca.pem
    clusterCertificateKeyFile: /etc/ssl/mongodb/member.pem  # Same or separate

security:
  clusterAuthMode: x509   # Options: keyFile, sendKeyFile, sendX509, x509
  authorization: enabled
```

**Rolling upgrade from keyfile to X.509:**
1. Set `clusterAuthMode: sendKeyFile` on all members (rolling restart) — accepts both
2. Set `clusterAuthMode: sendX509` on all members (rolling restart) — sends X.509, accepts both
3. Set `clusterAuthMode: x509` on all members (rolling restart) — requires X.509 only

### Hardening Checklist for Self-Managed

```yaml
# Disable JavaScript (breaks $where, $accumulator, $function — check app compatibility first)
security:
  javascriptEnabled: false

# Wire object check is enabled by default — keep it
net:
  wireObjectCheck: true

# Bind to specific interfaces only
net:
  bindIp: 127.0.0.1,<replica-set-internal-ip>

# Run MongoDB as dedicated OS user (not root)
# Create user: useradd -r -s /sbin/nologin mongod
processManagement:
  fork: true
```

**Firewall rules (iptables example):**
```bash
# Allow MongoDB port only from app servers and replica set members
iptables -A INPUT -p tcp --dport 27017 -s 10.0.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 27017 -j DROP
```

**File system permissions:**
```bash
chown -R mongod:mongod /var/lib/mongodb /var/log/mongodb /etc/ssl/mongodb
chmod 700 /var/lib/mongodb
chmod 400 /etc/ssl/mongodb/*.pem /etc/ssl/mongodb/keyfile
```

### Encryption at Rest (Self-Managed)

- **WiredTiger Native Encryption** (MongoDB Enterprise): AES256-CBC or AES256-GCM with KMIP-compatible KMS
- **Filesystem encryption**: dm-crypt/LUKS on Linux, BitLocker on Windows — applies at block device level
- **Client-Side Field Level Encryption (CSFLE)**: Application-layer encryption for specific fields; plaintext never sent to server

```yaml
# WiredTiger encryption (Enterprise)
security:
  enableEncryption: true
  kmip:
    serverName: kmip.example.com
    port: 5696
    clientCertificateFile: /etc/ssl/kmip/client.pem
    serverCAFile: /etc/ssl/kmip/ca.pem
```

---

## 7. Atlas Organization and Project Governance

### Organization-Level SSO with Federated Authentication

Atlas Federated Authentication connects your identity provider to Atlas using SAML 2.0. Once configured, Atlas disables all other authentication for users in mapped domains.

**Supported IdPs:** Okta, Microsoft Entra ID (formerly Azure AD), Ping Identity, any SAML 2.0 IdP.

**Setup (Okta example):**
1. In Okta Admin: Add SAML 2.0 app for MongoDB Atlas
2. Configure SSO URL: `https://account.mongodb.com/account/saml`
3. In Atlas: Security > Federated Authentication > Identity Providers > Add
4. Enter Okta IdP metadata URL or upload metadata XML
5. Map your domain(s) to the identity provider
6. Configure role mappings (IdP groups → Atlas roles)

**Microsoft Entra ID:**
1. In Azure Portal: Enterprise Applications > New Application > Search "MongoDB Atlas"
2. Configure SAML SSO with Atlas as Service Provider
3. Map Entra group Object-IDs to Atlas org/project roles in Atlas Federation Settings

**Advanced Federated Auth options:**
- **Domain restriction:** Only allow emails from specific domains to log in via the IdP
- **IP restriction:** Restrict Atlas UI access to specific IP ranges (enforced at org level)
- **Bypass list:** Designate specific users who can bypass federation (emergency access)
- **JIT provisioning:** Users are auto-created in Atlas on first SSO login based on role mappings

### Organization-Level Access Control Patterns

```
Organization
├── Organization Owner: 1-2 service accounts only; SAML JIT break-glass group
├── Organization Project Creator: 1 service account per product team
├── Organization Billing Admin: FinOps service account
└── Projects (1 per environment per application, or 1 per business unit)
    ├── Project Owner: platform/ops service account
    ├── Project Cluster Manager: infra team
    ├── Project Data Access Admin: DBA team
    └── Project Data Access Read/Write: application service accounts
```

### Cross-Project Access Control

- Database users are **scoped to a project** — they do not have automatic cross-project access
- To give a user access to multiple projects, create separate database users in each project
- For org-wide monitoring, use the Atlas Admin API with a service account that has `Organization Read Only` + per-project `Project Data Access Read Only`

### Atlas Resource Policies (Defense-in-Depth at Org Level)

Atlas Resource Policies allow organization owners to enforce security constraints across all projects, preventing project owners from violating org-wide policies:

- **Require private networking:** Block creation of clusters without private endpoints
- **Require encryption at rest:** Block clusters without BYOK configured
- **Restrict cloud providers/regions:** Limit deployments to approved cloud regions
- **Deny public internet access:** Prevent addition of `0.0.0.0/0` to IP access lists

Configure via the Atlas Admin API or Terraform (`mongodbatlas_organization` and related policy resources in the MongoDB Atlas Terraform provider).

### Audit Logging for Atlas User Actions (Org/Project Level)

In addition to database audit logs, Atlas logs all Atlas user and API actions (project creation, user management, cluster scaling, etc.) in the **Activity Feed**. Export to SIEM via the Atlas API or Event Log Integration.

---

## 8. Encryption in Transit

### TLS Configuration Summary

| Setting | Atlas Clusters | Self-Managed |
|---|---|---|
| TLS required | Always — cannot disable | Configurable |
| Minimum version | TLS 1.2 (TLS 1.0/1.1 removed July 2025) | Configurable |
| TLS 1.3 | Rolling out fleet-wide (2025) | Available in MongoDB 4.0+ |
| Certificate Authority | Let's Encrypt / Google Trust Services (auto-rotated) | Customer-managed CA |
| mTLS support | Yes (self-managed X.509 cert users) | Yes |
| Custom cipher suites | Yes (Atlas enterprise setting) | Yes (via `net.tls.disabledProtocols`) |

### Certificate Authority Options for Atlas

**Atlas-managed CA (default):**
- Atlas automatically provisions TLS certificates for cluster nodes using Let's Encrypt or Google Trust Services
- Certificates are automatically rotated — no operator action required
- Application trust stores should include both Let's Encrypt and Google Trust Services root CAs

**Customer-managed CA (self-managed X.509 for client auth):**
- Upload your own CA certificate to Atlas for client certificate authentication
- Atlas uses your CA to validate client certificates presented during mTLS authentication
- You manage certificate issuance, expiration, and revocation

### Mutual TLS (mTLS) for Client Authentication

mTLS requires both the server and client to present valid certificates. Configure in Atlas:

1. Enable X.509 authentication for database users
2. Upload CA certificate (your own CA or a certificate from your PKI)
3. Issue client certificates from the same CA
4. Application presents client certificate in connection string

```python
# PyMongo mTLS connection
from pymongo import MongoClient
import ssl

client = MongoClient(
    "mongodb+srv://cluster.mongodb.net/",
    tls=True,
    tlsCertificateKeyFile="/path/to/client.pem",
    tlsCAFile="/path/to/ca.pem",
    authMechanism="MONGODB-X509",
    authSource="$external"
)
```

### TLS Certificate Rotation

**Atlas-managed certificates:** Automatic — no operator action required. Atlas uses multiple CAs to ensure high availability during rotation.

**Self-managed certificates (internal auth X.509):**
1. Issue new certificate with future expiration from same CA
2. Perform rolling restart of replica set members (one at a time, waiting for SECONDARY state)
3. Old certificates continue to work until they expire
4. After all members restarted with new certs, revoke old certificates

**Atlas custom cipher suites:**
```bash
# Set minimum TLS protocol via Atlas Admin API v2
curl --user "public:private" --digest \
  -X PATCH "https://cloud.mongodb.com/api/atlas/v2/groups/<project-id>/clusters/<cluster-name>" \
  -H "Accept: application/vnd.atlas.2023-01-01+json" \
  -H "Content-Type: application/json" \
  -d '{"advancedSettings": {"minimumEnabledTlsProtocol": "TLS1_2"}}'
```

---

## 9. Secrets Management for Atlas Credentials

### Anti-Patterns to Avoid

- Hardcoding credentials in application code or config files
- Storing credentials in environment variables without a secrets manager backing
- Using the same long-lived SCRAM user across multiple applications
- No credential rotation schedule (long-lived static passwords)
- Using organization-owner API keys for application access

### HashiCorp Vault — MongoDB Atlas Dynamic Secrets

Vault generates ephemeral credentials for MongoDB Atlas databases with automatic TTL-based revocation. Credentials are created when requested and deleted when the TTL expires.

**Setup:**
```bash
# Enable Atlas database secrets engine
vault secrets enable database

# Configure Atlas plugin
vault write database/config/my-atlas-cluster \
  plugin_name=mongodbatlas-database-plugin \
  public_key="<atlas-api-public-key>" \
  private_key="<atlas-api-private-key>" \
  project_id="<project-id>"

# Create a Vault role with TTL
vault write database/roles/app-service \
  db_name=my-atlas-cluster \
  creation_statements='{"database_name": "mydb", "roles": [{"databaseName": "mydb", "roleName": "readWrite"}]}' \
  default_ttl="1h" \
  max_ttl="24h"
```

**Application retrieves credentials:**
```bash
# Request temporary credentials
vault read database/creds/app-service
# Returns: username=v-app-XXXX, password=<generated>, lease_duration=1h

# Credentials are auto-revoked after TTL
```

**HCP Vault Secrets — automatic rotation:**
For static SCRAM credentials, HCP Vault Secrets can automatically rotate Atlas database username/password on a schedule, without requiring application code changes when using dynamic lease renewal.

**Important limitation:** The Atlas API root user (public/private key pair) cannot be rotated by Vault — protect it separately.

### AWS Secrets Manager with Atlas

**Managed rotation for Atlas SCRAM users:**
AWS Secrets Manager supports Atlas database user rotation via a Lambda rotation function.

1. Store initial SCRAM credentials as a secret: `{"username": "app-user", "password": "initial-pass"}`
2. Configure rotation with AWS-provided or custom Lambda function
3. Lambda creates new Atlas database user, updates application, deletes old user

**Terraform:**
```hcl
resource "aws_secretsmanager_secret" "atlas_db" {
  name                    = "atlas/production/app-service"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_rotation" "atlas_rotation" {
  secret_id           = aws_secretsmanager_secret.atlas_db.id
  rotation_lambda_arn = aws_lambda_function.atlas_rotator.arn

  rotation_rules {
    automatically_after_days = 30
  }
}
```

### Recommended Credential Strategy by Environment

| Credential Type | Dev/Test | Staging | Production |
|---|---|---|---|
| Application DB user | SCRAM + Secrets Manager | X.509 or SCRAM + Vault | OIDC Workload / AWS IAM / X.509 |
| Human operator DB access | Temporary SCRAM user (1-day TTL) | Workforce OIDC | Workforce OIDC (JIT, 6h TTL) |
| Atlas Admin API | Service account (restricted roles) | Service account | Service account (IP-restricted) |
| CI/CD pipeline | Short-lived SCRAM + Vault lease | X.509 cert per pipeline | OIDC Workload (no static creds) |

### X.509 Certificate Lifecycle Management

X.509 certificates require active lifecycle management:
- Issue from an internal CA with appropriate expiration (90-365 days)
- Track expiration using a PKI management tool (HashiCorp Vault PKI engine, Cert-Manager for Kubernetes)
- Rotate before expiration — overlap old and new certificates during rolling deployment
- Revoke compromised certificates immediately via CRL or OCSP

**Vault PKI for certificate issuance:**
```bash
vault secrets enable pki
vault write pki/root/generate/internal common_name="MongoDB Internal CA" ttl=87600h
vault write pki/roles/mongodb-clients \
  allowed_domains="myorg.internal" \
  allow_subdomains=true \
  max_ttl="720h"  # 30-day certs

# Issue certificate for an application
vault write pki/issue/mongodb-clients \
  common_name="app-service.myorg.internal"
```

---

## 10. Atlas Security Posture Checklist

Use this checklist for Atlas project/org security reviews. Each item includes the risk it mitigates.

### Authentication and Access

- [ ] **MFA enabled for all Atlas UI users** — Required as of March 2025; mitigates credential theft
- [ ] **Federated authentication (SSO) configured** — Centralizes policy enforcement, enables MFA at IdP level
- [ ] **No organization owner role assigned to human users** — Org Owner should be a service account or SAML JIT break-glass group only
- [ ] **No `0.0.0.0/0` in IP access list** — Open access allows connections from any internet IP
- [ ] **API keys / service accounts have IP access lists** — Prevents use of leaked API keys from unknown IPs
- [ ] **No shared database users across applications** — Shared credentials make breach attribution and rotation difficult
- [ ] **SCRAM credentials stored in secrets manager** — Prevents credentials in code/config files
- [ ] **Temporary database users for human operators** — Reduces window of exposure for administrative access

### Network Security

- [ ] **Private endpoints configured (M10+)** — Eliminates public internet exposure of cluster endpoints
- [ ] **Public internet access disabled or restricted** — No public IPs in access list after private endpoint setup
- [ ] **TLS minimum version set to 1.2+** — TLS 1.0/1.1 removed by Atlas July 2025; verify no legacy clients
- [ ] **VPC peering established for cross-service connectivity** — Avoids routing through public internet for internal services

### Encryption

- [ ] **Encryption at rest enabled** — Atlas enables by default; verify not bypassed
- [ ] **BYOK/CMK configured (M10+)** — Customer-managed keys give you sole control over data key lifecycle; required for some compliance frameworks
- [ ] **BYOK key rotation scheduled** — AWS KMS, Azure Key Vault, and GCP KMS should have annual or more frequent rotation
- [ ] **Backup snapshots encrypted with CMK** — Oplog data collected for PITR is also encrypted with CMK when BYOK is enabled

### Audit Logging

- [ ] **Database auditing enabled** — Required for SOC 2, PCI DSS, HIPAA, ISO 27001 compliance
- [ ] **Audit filter captures minimum required events** — Authentication, user management, schema changes, backup/restore
- [ ] **Audit logs forwarded to SIEM** — Logs must be ingested into centralized system; S3, Splunk, Datadog, etc.
- [ ] **Audit log retention policy defined** — Regulatory requirements often mandate 1-7 year retention
- [ ] **Atlas Activity Feed integrated with SIEM** — Captures Atlas control plane actions (user/project/cluster changes)

### Backup and Recovery

- [ ] **Backup Compliance Policy enabled** — Prevents any user (including Project Owner) from deleting snapshots before expiration
- [ ] **PITR (Point-in-Time Recovery) enabled** — Enables recovery to any minute within the retention window (RPO as low as 1 min)
- [ ] **Backup retention policy meets RPO/RTO requirements** — Minimum daily snapshots; hourly for critical data
- [ ] **Backup restoration tested** — At least quarterly; WORM compliance is meaningless if restore procedure is untested

### RBAC and User Management

- [ ] **No `root` role assigned to application database users** — `root` grants unrestricted access; use custom least-privilege roles
- [ ] **Custom roles scoped to minimum collections** — Built-in `readWrite` grants access to all collections
- [ ] **Periodic access review scheduled (30-90 days)** — Remove unused users; review role assignments
- [ ] **Database users provisioned via IaC** — Terraform/Kubernetes Operator prevents role drift and enables audit trail
- [ ] **No admin users in application databases** — Application users should not have `userAdmin` or `dbAdmin` on production databases

### Compliance Posture

- [ ] **Compliance framework mappings identified** (SOC 2, PCI DSS, HIPAA, ISO 27001, FedRAMP) — Atlas documentation provides per-framework guidance
- [ ] **Atlas Well-Architected Review completed** — Use Atlas Architecture Center as checklist framework
- [ ] **Vulnerability notifications subscribed** — Subscribe to MongoDB security advisories for CVE notifications
- [ ] **MongoDB version within supported lifecycle** — Check end-of-life dates; upgrade before EOL to receive security patches

### Advanced Security (Enterprise/High-Security Workloads)

- [ ] **Client-Side Field Level Encryption (CSFLE) for ultra-sensitive fields** — Encrypts at application layer; MongoDB never sees plaintext
- [ ] **Queryable Encryption for search on encrypted fields** — Enables equality queries on encrypted data without decryption
- [ ] **Atlas Resource Policies enforced at org level** — Prevents project owners from violating security baseline
- [ ] **Dedicated search nodes for Atlas Search** — Isolates search workloads; CMK for search nodes available 2025

---

## References

### Official MongoDB Documentation

- [Authentication on Self-Managed Deployments](https://www.mongodb.com/docs/manual/core/authentication/)
- [SCRAM Authentication](https://www.mongodb.com/docs/manual/core/security-scram/)
- [X.509 Certificate Authentication](https://www.mongodb.com/docs/manual/core/security-x.509/)
- [Atlas Authentication Guidance](https://www.mongodb.com/docs/atlas/architecture/current/auth/authentication/)
- [Atlas Authorization Guidance](https://www.mongodb.com/docs/atlas/architecture/current/auth/authorization/)
- [Configure Database Users (Atlas)](https://www.mongodb.com/docs/atlas/security-add-mongodb-users/)
- [AWS IAM Authentication (Atlas)](https://www.mongodb.com/docs/atlas/security/aws-iam-authentication/)
- [Set Up Self-Managed X.509 Certificates](https://www.mongodb.com/docs/atlas/security-self-managed-x509/)
- [Configure Federated Authentication from Okta](https://www.mongodb.com/docs/atlas/security/federated-auth-okta/)
- [Atlas Network Security Guidance](https://www.mongodb.com/docs/atlas/architecture/current/network-security/)
- [Atlas Auditing Guidance](https://www.mongodb.com/docs/atlas/architecture/current/auditing/)
- [Configure Audit Filters](https://www.mongodb.com/docs/manual/tutorial/configure-audit-filters/)
- [Set Up Database Auditing (Atlas)](https://www.mongodb.com/docs/atlas/database-auditing/)
- [Encryption at Rest with Customer Key Management](https://www.mongodb.com/docs/atlas/security-kms-encryption/)
- [Self-Managed Internal/Membership Authentication](https://www.mongodb.com/docs/manual/core/security-internal-authentication/)
- [Security Checklist for Self-Managed Deployments](https://www.mongodb.com/docs/manual/administration/security-checklist/)
- [Security in Atlas Well-Architected Framework](https://www.mongodb.com/docs/atlas/architecture/current/security/)
- [Backup Compliance Policy](https://www.mongodb.com/docs/atlas/backup/cloud-backup/backup-compliance-policy/)
- [TLS/SSL Transport Encryption](https://www.mongodb.com/docs/manual/core/security-transport-encryption/)
- [Atlas Private Endpoints](https://www.mongodb.com/docs/atlas/security-private-endpoint/)

### HashiCorp Vault

- [MongoDB Atlas Database Secrets Engine](https://developer.hashicorp.com/vault/docs/secrets/databases/mongodbatlas)
- [MongoDB Database Secrets Engine](https://developer.hashicorp.com/vault/docs/secrets/databases/mongodb)
- [HCP Vault Secrets — MongoDB Atlas Rotation](https://developer.hashicorp.com/hcp/docs/vault-secrets/auto-rotation/create-rotating-secret/mongodb-atlas)

### AWS

- [MongoDB Atlas Database User (AWS Secrets Manager)](https://docs.aws.amazon.com/secretsmanager/latest/userguide/mes-partner-MongoDBAtlasDatabaseUser.html)
- [Connecting Applications Securely with AWS PrivateLink](https://aws.amazon.com/blogs/apn/connecting-applications-securely-to-a-mongodb-atlas-data-plane-with-aws-privatelink/)

### Microsoft Entra ID

- [Configure MongoDB Atlas SSO with Microsoft Entra ID](https://learn.microsoft.com/en-us/entra/identity/saas-apps/mongodb-cloud-tutorial)

### See Also

- [[mongodb-compliance]] — SOC 2, PCI DSS, HIPAA, ISO 27001 compliance deep-dives
- [[mongodb-encryption]] — CSFLE, Queryable Encryption, WiredTiger native encryption, KMIP
- [[mongodb-atlas-expert]] — Atlas cluster management, configuration, and operations
- [[mongodb-atlas-azure]] — Azure-specific Atlas networking, Entra ID integration, Azure Key Vault CMK
- [[mongodb-atlas-gcp]] — GCP-specific Atlas networking, Google Workspace SSO, Cloud KMS CMK
