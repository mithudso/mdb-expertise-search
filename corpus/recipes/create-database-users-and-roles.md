---
name: create-database-users-and-roles
title: Create database users and least-privilege custom roles
summary: Create Atlas (or self-managed) database users with a chosen auth method, grant them collection-scoped custom roles, and rotate credentials safely.
applies_to: [atlas, self-managed]
sources:
  - skills/mongodb-atlas-expert/references/mongodb-atlas-iam-rbac.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md
  - skills/mongodb-operations-expert/references/mongodb-security-architecture.md
  - skills/mongodb-expert/references/mongodb-multi-tenancy.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-service-accounts.md
---
# Create database users and least-privilege custom roles

## When to use
- An application, job, or person needs to connect to the data plane (run `find`, `insert`, and so on) and needs a dedicated identity.
- A built-in role such as `readWrite` is broader than needed and you want collection-level privileges.
- You are replacing a shared or over-privileged account (for example one holding `atlasAdmin` or `readWriteAnyDatabase`).
- You need to rotate a database credential without downtime.

Atlas database users are separate from Atlas (control-plane) users. An Organization Owner who wants to run `db.collection.find()` still needs a database user.

## Prerequisites (checklist)
- [ ] You hold Org Owner, Project Owner, or Project Database Access Admin on the Atlas project (needed to create custom roles).
- [ ] You know the project id (`<project-id>`), database (`mydb`) and collections (`mydb.orders`) the identity needs.
- [ ] You picked ONE auth method. The method cannot be changed after creation, and LDAP and SCRAM cannot be combined for one user.
- [ ] Atlas CLI installed and authenticated (`atlas auth login`), or access to the Atlas UI under Database Access.
- [ ] A secrets store (vault or cloud secrets manager) exists for any SCRAM password.
- [ ] Self-managed only: `security.authorization: enabled` is set and you have an admin user (see step 8).

## Steps

### 1. Choose the authentication method
Use this order of preference from the corpus decision tree: human users, workforce OIDC; app on AWS, AWS IAM; app on Azure or GCP, workload OIDC; need mTLS, X.509; dev/test only, SCRAM with a secrets manager.

```text
Atlas UI: Database Access > Add New Database User > Authentication Method
```
Expect: the form shows Password (SCRAM), AWS IAM, X.509 Certificate, LDAP and Federated Auth options. Workload OIDC needs an M10+ dedicated cluster and MongoDB 7.0.11 or later.

### 2. List existing users and roles to avoid duplicates
```bash
atlas dbusers list --projectId <project-id>
atlas customDbRoles list --projectId <project-id>
```
Expect: a table of current database users and custom roles. Note anything holding `atlasAdmin` or `readWriteAnyDatabase`.

### 3. Create a collection-scoped custom role
Privilege syntax in the CLI is `ACTION@db.collection`.
```bash
atlas customDbRoles create orders-reader \
  --projectId <project-id> \
  --privilege "FIND@mydb.orders" \
  --privilege "FIND@mydb.order_items"
```
Expect: the CLI echoes the new role. On Free/Flex tiers a custom role can take about 30 seconds to propagate.

To add narrow write access on top of a built-in read role:
```bash
atlas customDbRoles create orders-writer \
  --projectId <project-id> \
  --inheritedRole read \
  --privilege "INSERT@mydb.orders"
```
Expect: role created with `read` inherited and `INSERT` on `mydb.orders`.

Constraints: the role name must not equal a built-in role, must not start with `xgen-`, and must not be `atlasAdmin`. Limits in the corpus: 20 custom roles per user, 100 per project by default (1400 with the extended API limit). Never use the "apply to any database" resource (`db: ""`, `collection: ""`) for write actions; it includes `admin`, `local` and `config`.

### 4. Create the database user with SCRAM (dev/test or last resort)
```bash
atlas dbusers create \
  --username app-orders \
  --password "$(openssl rand -base64 32)" \
  --role "orders-reader@admin" \
  --projectId <project-id>
```
Expect: the CLI echoes the new user. Store the generated password in your secrets store immediately; Atlas will not show it again.

Note: the corpus shows built-in roles in the form `roleName@db[.collection]` (for example `readWrite@mydb`). For custom roles the database part is normally `admin`. Verify in the current MongoDB docs: the exact `--role` value for a custom role.

### 5. Or create a passwordless user (preferred for workloads)
AWS IAM role:
```bash
atlas dbusers create \
  --username "arn:aws:iam::<account-id>:role/<role-name>" \
  --awsIAMType ROLE \
  --role "readWrite@mydb" \
  --projectId <project-id>
```
X.509 managed by Atlas (Verify in the current MongoDB docs: for Atlas-managed X.509 the username is a plain name and Atlas builds the certificate subject itself; the `CN=...,OU=...` distinguished-name form applies to self-managed X.509, where the username must match the client certificate subject):
```bash
atlas dbusers create \
  --username "app-service" \
  --x509Type MANAGED \
  --role "readWrite@mydb" \
  --projectId <project-id>
atlas dbusers certs create --username "app-service" --monthsUntilExpiration 12 --projectId <project-id>
```
OIDC (mutually exclusive with `--password`): add `--oidcType USER` or `--oidcType IDP_GROUP`. For workload OIDC the identifier is the object or unique id, not a display name; a display name fails silently.

Expect: user listed with the chosen auth type in `atlas dbusers list`.

### 6. Make human access temporary
```bash
atlas dbusers create \
  --username debug-session \
  --password "$(openssl rand -base64 32)" \
  --role "read@mydb" \
  --deleteAfterDate "<ISO-8601-UTC-timestamp>" \
  --projectId <project-id>
```
Expect: the user disappears at the timestamp. The UI offers 6 hours, 1 day, 1 week or 1 month. The corpus shows two spellings of this flag (`--deleteAfterDate` in the CLI reference, `--deleteAfter` in the security reference). Verify in the current MongoDB docs: run `atlas dbusers create --help` and use the flag it lists.

### 7. Scope a user to specific clusters
The CLI reference shows a `--scope` flag on `atlas dbusers create`, but its value format is not explained clearly.
```text
Atlas UI: Database Access > Add New Database User > Restrict Access to Specific Clusters/Data Lakes
```
Verify in the current MongoDB docs: the `--scope` value format, then confirm the result with `atlas dbusers describe <username> --projectId <project-id>`.

### 8. Self-managed: create users and roles in mongosh
Do this in two stages. Setting `enableLocalhostAuthBypass: 0` in the same change that enables auth would lock you out before the first admin exists.

Stage 1: enable authorization, keep the localhost exception (the default), restart, then connect from localhost and create the first admin user (see the role and user example below).
```yaml
security:
  authorization: enabled
```
Stage 2 (optional, only after the first admin exists and you have confirmed you can log in): disable the localhost exception and restart.
```yaml
setParameter:
  enableLocalhostAuthBypass: 0
```
Create a role and a user:
```javascript
db.getSiblingDB("admin").createRole({
  role: "orders-reader",
  privileges: [
    { resource: { db: "mydb", collection: "orders" }, actions: ["find"] }
  ],
  roles: []
})
db.getSiblingDB("mydb").createUser({
  user: "app-orders",
  pwd: passwordPrompt(),
  roles: [ { role: "orders-reader", db: "admin" } ]
})
```
Expect: `{ ok: 1 }` for each command. `passwordPrompt()` keeps the password out of shell history.

### 9. Rotate a SCRAM password
Atlas:
```bash
atlas dbusers update app-orders --password "$(openssl rand -base64 32)" --projectId <project-id>
```
Self-managed:
```javascript
db.getSiblingDB("mydb").changeUserPassword("app-orders", passwordPrompt())
```
Expect: success message. Update the secret and restart or reload consumers. For zero-downtime rotation use two users (create `app-orders-b`, switch consumers, delete the old user) or a vault dynamic-secret engine that issues short-lived credentials.

### 10. Rotate X.509 certificates
Issue the new certificate from the CA with a 90 to 365 day lifetime, deploy it alongside the old one in a rolling deployment, then retire the old one. Revoke compromised certificates immediately via CRL or OCSP.

Expect: clients authenticate with the new certificate before the old one expires.

## Verify
```bash
atlas dbusers describe app-orders --projectId <project-id>
atlas customDbRoles describe orders-reader --projectId <project-id>
```
Expect: the expected roles and auth type are shown.

Then test with the new identity (not an admin) in mongosh:
```javascript
db.getSiblingDB("mydb").orders.findOne()          // allowed
db.getSiblingDB("mydb").orders.insertOne({x: 1})  // must fail: not authorized
db.getSiblingDB("mydb").other.findOne()           // must fail: not authorized
```
Expect: the read succeeds; the other two return an "not authorized" (code 13) error.

Self-managed: `db.getUsers()` and `db.getRoles({showPrivileges: true})` list what exists.

## Rollback / abort
- Atlas: `atlas dbusers delete app-orders --projectId <project-id> --force` removes the user. You cannot delete a custom role if that would leave any user with zero roles, so reassign the user first.
- Revert a password change by setting a known good secret with `atlas dbusers update ... --password`.
- Self-managed: `db.dropUser("app-orders")` and `db.dropRole("orders-reader")`.
- Keep the old user until all consumers are confirmed on the new one.

## Pitfalls
- No deny privilege exists. Effective permissions are the union of every assigned role, so a broad built-in role defeats a narrow custom one. Do not grant the broad role at all.
- The "apply to any database" resource includes `admin`, `local` and `config`. Do not grant writes there.
- Atlas does not support `__system`, `root` or `clusterAdmin`.
- Collection-level roles do not isolate tenants sharing a collection; combine them with an application-layer tenant filter.
- Project data-access roles (for example Project Data Access Admin) only govern Data Explorer in the UI; they do not create a queryable identity.
- Auth method cannot be changed after creation; delete and recreate.
- Workload OIDC with a display name instead of the object or unique id fails silently.
- A shared account for several services makes rotation and auditing hard; use one identity per application.
- Self-managed: leaving `enableLocalhostAuthBypass` enabled after the first user exists.
- Passing passwords on the command line leaves them in shell history; read them from a secrets store.
- Audit findings the corpus lists: users with `atlasAdmin` or `readWriteAnyDatabase` that should have collection-scoped access.

## Sources
- `skills/mongodb-atlas-expert/references/mongodb-atlas-iam-rbac.md:241-337` (user vs Atlas user, auth methods, temporary users, custom role limits, restrictions, union semantics)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-iam-rbac.md:565-671` (workload OIDC requirements, identifier pitfall)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md:710-849` (`atlas dbusers` and `atlas customDbRoles` commands, role format, auth type flags)
- `skills/mongodb-operations-expert/references/mongodb-security-architecture.md:181-256` (auth decision tree, constraints, temporary users)
- `skills/mongodb-operations-expert/references/mongodb-security-architecture.md:380-390` (least-privilege patterns)
- `skills/mongodb-operations-expert/references/mongodb-security-architecture.md:674-706` (self-managed `security.authorization`, localhost bypass)
- `skills/mongodb-operations-expert/references/mongodb-security-architecture.md:1017-1048` (credential strategy, X.509 lifecycle)
- `skills/mongodb-expert/references/mongodb-multi-tenancy.md:292-335` (`createUser` / `createRole` mongosh examples and the tenant-filter caveat)
