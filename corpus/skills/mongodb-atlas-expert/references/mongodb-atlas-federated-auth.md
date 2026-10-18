<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-federated-auth` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-federated-auth
title: MongoDB Atlas Federated Authentication
version: 1.2.0
updated: 2026-05-29
description: "Deep-reference skill for Atlas organization-level SSO via SAML 2.0 federated authentication. TRIGGER when configuring, debugging, or reviewing Atlas federation: Federation Manager setup, Okta/Entra ID/PingOne/Google Workspace IdP configuration, connected organizations, domain verification, IdP group-to-role mapping, bypass/breakglass users, JIT provisioning, SCIM lifecycle management, or troubleshooting SAML assertion failures. SKIP for database-level authentication (OIDC workload federation, X.509, SCRAM, LDAP) — use mongodb-atlas-iam-rbac. SKIP for general Okta configuration unrelated to Atlas SSO — use okta-expert instead."
category: mongodb
tags:
  - mongodb
  - atlas
  - security
  - sso
  - saml
  - federation
  - okta
  - entra-id
  - azure-ad
  - scim
  - identity
  - iam
when_to_use:
  - Configuring Atlas organization-level SSO with an identity provider
  - Debugging SAML assertion errors or federation login failures
  - Setting up Okta or Microsoft Entra ID as an Atlas IdP
  - Mapping IdP groups to Atlas org or project roles
  - Verifying and claiming email domains for federation
  - Managing bypass/breakglass users for SSO outage access
  - Understanding JIT vs SCIM provisioning for Atlas user lifecycle
  - Connecting multiple Atlas orgs under one federation
  - Reviewing Atlas federation security posture
  - Configuring Atlas Kubernetes Operator AtlasFederatedAuth custom resource
  - Rotating an expiring IdP signing certificate in Atlas
  - Diagnosing memberOf group-mapping not applying to a user
when_not_to_use:
  - Database-level authentication (OIDC workload/workforce federation, X.509, SCRAM, LDAP) — use mongodb-atlas-iam-rbac
  - General Okta application configuration unrelated to Atlas SSO — use okta-expert
  - Entra ID configuration for Azure resources unrelated to MongoDB Atlas — use mongodb-atlas-azure
  - Atlas programmatic API keys or service account authentication — use mongodb-atlas-iam-rbac
keywords:
  - atlas federated authentication
  - atlas sso
  - atlas saml
  - atlas identity provider
  - atlas okta sso
  - atlas entra id sso
  - atlas azure ad sso
  - atlas scim
  - atlas connected orgs
  - atlas domain verification
  - atlas group role mapping
  - atlas federation manager
  - atlas bypass saml
  - atlas jit provisioning
  - atlas org sso
  - atlas federation management console
  - atlas memberOf claim
  - atlas domain restriction
  - atlas idp configuration
  - atlas saml sp
  - atlas federation management app
  - atlas breakglass account
  - atlas bypass saml mode
  - saml assertion validation failure
  - atlas certificate expiry sso
related_skills:
  - mongodb-atlas-expert
  - mongodb-security-architecture
  - okta-expert
  - mongodb-atlas-azure
  - mongodb-atlas-iam-rbac
  - mongodb-atlas-kubernetes-operator
---

# MongoDB Atlas Federated Authentication

## Overview

Atlas Federated Authentication implements **Federated Identity Management (FIM)** at the Atlas *organization* layer. Your identity provider (IdP) manages all credentials; Atlas acts as the SAML 2.0 Service Provider (SP). When a user logs in, their browser exchanges SAML assertions with the IdP instead of submitting MongoDB credentials directly.

**Scope of federation**: One federation application can span multiple Atlas organizations under a single IdP, unified via the **Federation Management Console** (FMC). Federation covers **Atlas UI access only** — it does not control database-level user authentication. For OIDC workforce federation, X.509, SCRAM, or LDAP database auth, see [[mongodb-atlas-iam-rbac]].

> **SAML vs OIDC disambiguation**: This skill covers SAML 2.0 federation for Atlas *UI login* (org-level SSO). If the question is about authenticating *application workloads* to the Atlas database via an IdP, that is Workload/Workforce Identity Federation (OIDC) — a different feature documented in [[mongodb-atlas-iam-rbac]].

> **Guardrail**: Use only the API endpoint paths, attribute names, and URLs explicitly stated in this skill. Do not extrapolate or invent Atlas Admin API paths — verify any path not listed here against the [Atlas Admin API reference](https://www.mongodb.com/docs/atlas/reference/api-resources-spec/) before use.

---

## 1. How Atlas Federated Authentication Works

### Architecture

```
User Browser
     |
     | 1. User visits cloud.mongodb.com, enters email (e.g., alice@corp.com)
     v
Atlas (SAML SP)
     |
     | 2. Atlas matches corp.com → configured IdP, sends SAML AuthnRequest
     v
Identity Provider (IdP)
     |
     | 3. IdP authenticates user (password, MFA, etc.)
     | 4. IdP issues SAML Response (signed XML assertion)
     v
Atlas (SAML SP / Assertion Consumer Service)
     |
     | 5. Atlas validates assertion: signature, audience, timestamps
     | 6. Atlas extracts NameID (email), firstName, lastName, memberOf groups
     | 7. Atlas creates/updates user account (JIT), applies role mappings
     v
User lands in Atlas organization(s)
```

### Key concepts

| Concept | Details |
|---------|---------|
| **Service Provider (SP)** | Atlas; validates SAML assertions, issues sessions |
| **Identity Provider (IdP)** | Okta, Entra ID, PingOne, Google Workspace, etc. |
| **Assertion Consumer Service (ACS) URL** | Atlas endpoint that receives the POST-bound SAML Response; provided in Atlas metadata XML |
| **Audience URI / SP Entity ID** | Identifier that Atlas expects in `<AudienceRestriction>`; provided in Atlas metadata XML |
| **Federation ID** | 24-character hexadecimal identifier for the federation application; shown in FMC |
| **NameID** | The SAML subject; Atlas uses this as the user's email/username. Format must be `unspecified` or `emailAddress` |
| **memberOf** | SAML attribute Atlas reads for IdP group names/IDs; drives role mapping |

### SP-initiated vs IdP-initiated flow

- **SP-initiated**: User goes to `cloud.mongodb.com`, enters their email, Atlas redirects to IdP. Most common. Works with domain mapping.
- **IdP-initiated**: User clicks a tile in Okta/Entra ID My Apps. IdP posts SAML Response directly to Atlas ACS. Requires setting RelayState to the Atlas Login URL. Both flows are supported.

### What federation disables

While federation is active for an org, Atlas disables direct Atlas credential login for users whose email matches a mapped domain. Atlas also bypasses Atlas-managed 2FA — configure MFA at the IdP level instead.

---

## 2. Supported Identity Providers

### Full platform support (end-to-end tutorials)

| Identity Provider | Atlas Docs Tutorial |
|-------------------|---------------------|
| **Okta** | `docs/atlas/security/federated-auth-okta/` |
| **Microsoft Entra ID** (Azure AD) | `docs/atlas/security/federated-auth-azure-ad/` |
| **Google Workspace** | `docs/atlas/security/federated-auth-google-ws/` |
| **PingOne** | `docs/atlas/security/federated-auth-ping-one/` |

Any SAML 2.0-compliant IdP works. JumpCloud, OneLogin, Auth0, and custom SAML providers are supported as generic IdPs.

---

### Okta + Atlas: Configuration steps

**Prerequisites**: Okta account, custom routable domain, Organization Owner in Atlas.

**Step 1 – Create SAML App in Okta**
1. Admin Console → Applications → Create App Integration → SAML 2.0
2. Enter app name; set temporary placeholder values for SSO URL and Audience URI (`http://localhost` / `urn:idp:default`)
3. Download the signing certificate (Active cert → Actions → Download); convert to PEM:
   ```bash
   openssl x509 -in mycert.crt -out mycert.pem -outform PEM
   ```

**Step 2 – Create IdP in Atlas FMC**
1. Open FMC → Identity Providers → Setup Identity Provider
2. Fill placeholders initially; upload the PEM certificate; set Request Binding: `HTTP POST`, Algorithm: `SHA-256`

**Step 3 – Exchange metadata; update Okta**
1. Download Atlas metadata XML from FMC
2. In Okta: SAML Settings → Edit → set:
   - **Single sign-on URL** → Atlas ACS URL (from metadata)
   - **Audience URI** → Atlas Audience URI (from metadata)
   - **Name ID format**: Unspecified; **Application username**: Email
3. Advanced Settings: Response: Signed, Assertion: Signed, Algorithm: RSA-SHA256, Digest: SHA256, Encryption: Unencrypted

**Step 4 – Attribute Statements in Okta**

| Attribute Name | Format | Value |
|----------------|--------|-------|
| `firstName` | Unspecified | `user.firstName` |
| `lastName` | Unspecified | `user.lastName` |

For group role mapping, add a Group Attribute Statement:

| Name | Filter | Value |
|------|--------|-------|
| `memberOf` | Matches regex | `.*` |

**Step 5 – Update Atlas IdP with real Okta values**
- View Setup Instructions in Okta app → copy real Issuer URI and SSO URL → update Atlas FMC IdP config

---

### Microsoft Entra ID + Atlas: Configuration steps

**Prerequisites**: Entra ID tenant with Application Administrator role, custom domain, Organization Owner in Atlas.

**Step 1 – Add MongoDB Atlas app from gallery**
1. Entra admin center → Entra ID → Enterprise apps → New application
2. Search "MongoDB Atlas - SSO" → add

**Step 2 – Configure SAML in Entra ID**
1. Enterprise apps → MongoDB Atlas - SSO → Single sign-on → SAML
2. Enter temporary values in Basic SAML Configuration:
   - **Identifier (Entity ID)**: `https://www.okta.com/saml2/service-provider/MongoDBCloud`
   - **Reply URL (ACS URL)**: `https://auth.mongodb.com/sso/saml2/`
3. Download **Certificate (Base64)** from SAML Signing Certificate section

**Step 3 – Configure user claims (case-sensitive)**

| Claim Name | Source Attribute |
|------------|------------------|
| `email` | `user.userprincipalname` |
| `firstName` | `user.givenname` |
| `lastName` | `user.surname` |

**Step 4 – Configure group claims for role mapping**
1. Add a group claim → Security groups
2. Source attribute: **Group Id** (sends Object ID) or display name attribute
3. Advanced options: Customize claim name → set **Name** to `memberOf`, leave Namespace blank, uncheck "Emit groups as role claims"

> **Critical**: When creating Atlas role mappings with Entra ID, if Group Id (Object ID) is selected as source attribute, enter the group's **Object ID** (GUID), not its display name, in the Atlas role mapping "Group Name" field.

**Step 5 – Import Atlas metadata into Entra ID**
1. In Atlas FMC, configure the IdP with the Entra ID values (Login URL, Entra Identifier)
2. Download Atlas metadata XML
3. In Entra ID SAML config → Upload metadata file → this sets the real ACS URL and Audience URI

**Step 6 – JIT Provisioning**: Enabled by default in Entra ID integration. No additional action needed — users are auto-created on first login.

---

## 3. Connected Organizations

A **federation** is a container that can hold multiple Atlas organizations, all governed by the same IdP configuration. This is the "connected orgs" model.

### Key facts

- One IdP can map to **multiple Atlas organizations**
- Each Atlas organization can be connected to only **one IdP** at a time
- All member orgs of a federation share the same domain verification pool and IdP registry
- The Federation ID identifies the federation application uniquely (24-char hex)

### Linking an organization

1. Open FMC → Click **Link Organizations**
2. All orgs where you are Organization Owner are listed
3. Orgs not yet linked show a **Configure Access** button
4. Click Configure Access → Connect Identity Provider → select IdP → Confirm

### Changing the mapped IdP for an org

You must first disconnect the current IdP (FMC → Organizations → Manage → Disconnect Identity Provider), then connect the new one.

### Disconnecting an org from federation

When disconnected: Atlas no longer grants org membership or default roles to IdP-authenticated users for that org. Existing users retain access; future SSO logins no longer auto-provision membership.

### Domain restriction per org

After linking an org, you can restrict it to only allow users whose email matches an approved domain list. See Section 5 → "Restrict access by domain" for the org-level toggle procedure.

---

## 4. Group-to-Atlas Role Mapping

Role mapping lets IdP group membership automatically grant Atlas organization and project roles.

### How it works at login

1. Atlas receives the SAML assertion containing the `memberOf` attribute
2. `memberOf` lists the groups the authenticating user belongs to (by name or Object ID, depending on IdP config)
3. Atlas looks up role mappings for each group name in organizations connected to the same IdP
4. **All matched roles from all groups are applied** — role grants are additive
5. If the user loses group membership (next login), Atlas removes the corresponding role from that org/project
6. If no group maps apply and a default org role is configured, the default role is assigned instead
7. If no group maps and no default role, the user gets no org/project roles (can still log in, but has no access)

### Adding a role mapping

1. FMC → Organizations → select org → Manage Role Mappings → Create A Role Mapping
2. Enter **Group Name** (must exactly match IdP group name, or Object ID for Entra ID with Group Id source)
3. Assign **Organization Role(s)**: Organization Owner, Organization Member, Organization Read Only, etc.
4. (Optional) Click Next → assign **Project Role(s)**: Project Owner, Project Data Access Admin, Project Read Only, etc.
5. Review and confirm

### Microsoft Entra ID group name caveat

If Entra ID sends `memberOf` as Group Object ID (GUID): enter the GUID in the "Group Name" field in Atlas, not the human-readable display name.

### Default role (guest role)

Assign a default role under FMC → Organizations → org → Default User Role. This role is assigned to any IdP-authenticated user who:
- Has no group-based role mappings in this org, OR
- Whose group memberships produce no Atlas roles

**Typical choice**: `Organization Member` (read-only org access) or a custom minimal role.

### Important constraints

- Every org must maintain at least one Organization Owner. Atlas prevents removing a role mapping if it would eliminate the last owner.
- When group-based role mappings are active, you cannot manually edit per-user roles from the Access Manager page for those federated users.
- Group names are **case-sensitive** and must match exactly as displayed in the IdP. Maximum 200 characters.

### Role removal behavior

If a federated user's group membership changes between logins, Atlas syncs roles on the **next login** — not in real-time. SCIM provisioning (Section 8) enables real-time sync.

---

## 5. Domain Verification

Domain verification proves to Atlas that you control `example.com` before Atlas will route `@example.com` users through your IdP.

### Two verification methods (choose once — cannot change without deleting the domain entry)

**Method A: DNS TXT Record** (recommended for automation/ops)

1. FMC → Add a Domain → enter Display Name and Domain Name → Next → select **DNS Record**
2. Copy the TXT record value: `mongodb-site-verification=<32-character-string>`
3. Add to your domain's DNS at your registrar (GoDaddy, Route 53, Cloudflare, etc.)
4. Click Finish, then click **Verify** on the Domains screen
5. DNS propagation can take minutes to hours

**Method B: HTML File Upload** (manual)

1. FMC → Add a Domain → Next → select **HTML File Upload**
2. Download `mongodb-site-verification.html` from Atlas
3. Host it at `https://<host>.<domain>/mongodb-site-verification.html` — must be accessible
4. Click Finish, then click **Verify**
5. **Security**: Delete the verification file after successful verification to avoid information disclosure

### After verification: associate domain with IdP

1. FMC → Identity Providers → Edit → **Associated Domains**
2. Select the verified domain
3. Click Confirm

Without domain association, the IdP shows as **Inactive** and no users are routed through it.

### Multiple IdPs and domain mapping

A domain can be mapped to multiple IdPs. However, when a user logs in via the Atlas web UI, Atlas redirects to the **first SAML IdP configured for Atlas** for that domain. Use SP-initiated or IdP-initiated login URLs to reach a secondary IdP.

### Deleting a domain mapping

You must first disassociate the domain from all IdPs before deleting it. FMC → Identity Providers → Edit Associated Domains → deselect domain → Confirm → then delete.

### Restrict access by domain (org-level)

After domain verification, enable domain restriction per org:
1. FMC → Organizations → ellipsis (...) → Restrict Access by Domain → toggle On
2. Add approved domains manually or import from existing org members
3. Effect: Only users with email addresses from listed domains can join the org. New invitations are also restricted.
4. Existing users outside approved domains retain access (not retroactively locked out).

---

## 6. Bypass and Breakglass Users

### Bypass SAML Mode

Atlas provides a **Bypass SAML Mode URL** per IdP configuration that lets administrators log in with their Atlas credentials (not IdP credentials), bypassing federation entirely.

- **Enabled by default** when you configure federation
- The URL is unique per IdP and allows Atlas credential login for users with the mapped domain
- **To find the URL**: FMC → Identity Providers → click the IdP entry → copy **Bypass SAML Mode URL** (do not toggle the on/off switch when your intent is only to copy the URL — toggling changes the bypass state)

**When to use**: During IdP outage, misconfigured SAML settings, certificate expiry, or initial testing.

**Recommendation**: Disable Bypass SAML Mode once federation is validated in production (as a security measure), but maintain at least one breakglass service account (see below).

### Breakglass service accounts

MongoDB's best practice: Keep one or more Atlas **Organization Owner** accounts that:
- Are NOT under the federated email domain (e.g., use an `@admin.example.com` address that is not mapped to any IdP)
- Have a strong password stored in a secrets manager (1Password, Vault, AWS SSM, etc.)
- Have Atlas 2FA enabled on the Atlas side

These accounts bypass SSO entirely because their email domain is not mapped. Use only during SSO outage or emergency admin lockout.

### Atlas Support and federation lockout

If the federation admin account is locked out and bypass SAML mode is disabled:
- Contact MongoDB Support with your org ID and proof of ownership
- Support can temporarily disable federation settings or provide escalation to unlock access
- This process is slow — justify keeping at least one bypass-capable account active

### Restrict User Membership to Federation (advanced)

FMC → Advanced Settings → toggle **Restrict Membership** On. Effect:
- Federated users cannot create Atlas orgs outside the federation
- Federated users cannot accept invitations to non-federated orgs
- Organization Owners can still create orgs (auto-connected to federation)
- Non-owners cannot create any orgs

---

## 7. Just-In-Time (JIT) User Provisioning

### What JIT does

When a user successfully authenticates via SAML for the first time, Atlas **automatically creates their Atlas account** from the SAML assertion attributes. No pre-provisioning in Atlas is required.

- **Enabled by default** for all Atlas federated authentication
- No additional configuration in Atlas is needed
- Applies to Okta, Entra ID, Google Workspace, PingOne, and any SAML 2.0 IdP

### Required SAML attributes for JIT

These must be in the SAML assertion. Names are **case-sensitive**.

| Attribute Name | Maps To | Format |
|----------------|---------|--------|
| `firstName` | User first name | String |
| `lastName` | User last name | String |
| **NameID** (Subject) | Username + email | Email address format |

The `memberOf` attribute is required for role mapping (not strictly for account creation):

| Attribute Name | Maps To | Format |
|----------------|---------|--------|
| `memberOf` | IdP group memberships | Multi-value string or array |

### Entra ID JIT attribute mapping

```
email       → user.userprincipalname  (or user.mail)
firstName   → user.givenname
lastName    → user.surname
memberOf    → Group Object IDs or display names (see Section 2)
```

### JIT vs SCIM comparison

| Aspect | JIT | SCIM |
|--------|-----|------|
| **User creation** | On first successful login | Pushed from IdP proactively |
| **User deprovisioning** | Not supported — user stays in Atlas when removed from IdP | User deactivated/removed from Atlas when IdP deactivates |
| **Group sync** | Only at login time | Continuous/scheduled push |
| **Attribute updates** | Updated at each login | Pushed by IdP on change |
| **Setup complexity** | Zero (enabled by default) | Requires SCIM app configuration in IdP |
| **Best for** | Small orgs, low churn | Enterprise with frequent staff changes, compliance requirements |

---

## 8. SCIM Provisioning

SCIM 2.0 (System for Cross-domain Identity Management) enables automated user lifecycle management, pushing create/update/deactivate events from the IdP to Atlas without waiting for a user to log in.

### What SCIM enables for Atlas

- Automatic Atlas account creation when a user is assigned to the Atlas SAML app in the IdP
- **Deprovisioning**: When a user is removed from the IdP (termination, offboarding), their Atlas access is removed — critical for compliance
- **Group sync**: IdP groups can be pushed to Atlas, keeping role mappings current without waiting for login
- **Attribute writeback**: Some IdPs support writing Atlas-side updates back to the IdP directory

### Okta SCIM setup with Atlas

Okta's MongoDB Atlas integration supports:
- User creation and updates
- Account deactivation (`active=false` on deprovisioning)
- Group push and group linking
- Schema discovery
- Attribute writeback

**Setup steps** (Okta side):
1. In the MongoDB Atlas Okta app → Provisioning tab → Configure API Integration
2. Provide the Atlas SCIM endpoint and a bearer token:
   - **SCIM base URL**: `https://cloud.mongodb.com/api/atlas/v2/federationSettings/{federationSettingsId}/connectedOrgConfigs/{orgId}/users` — obtain the `federationSettingsId` from FMC (shown as Federation ID) and `orgId` from your Atlas org settings. Verify the exact path against the [Atlas Admin API reference](https://www.mongodb.com/docs/atlas/reference/api-resources-spec/) before use, as endpoint paths may update between Atlas API versions.
   - **Bearer token**: Generate via Atlas Admin API service account or programmatic API key with Org Owner permissions; pass as `Authorization: Bearer <token>`
3. Enable Create/Update/Deactivate operations
4. Under Push Groups: configure IdP group push to Atlas

**Deprovisioning behavior**: When an admin removes a user from Okta, SCIM sends `PATCH /Users/{id}` with `active=false` → Atlas deactivates the user. Re-provisioning sets `active=true`.

### Entra ID SCIM setup with Atlas

1. Enterprise apps → MongoDB Atlas - SSO → Provisioning → Provisioning Mode: Automatic
2. Enter Atlas SCIM tenant URL using the same pattern as Okta above and the bearer token as the secret token. Verify the exact path against the [Atlas Admin API reference](https://www.mongodb.com/docs/atlas/reference/api-resources-spec/) before use.
3. Test connection → Save
4. Configure attribute mappings (firstName, lastName, email, groups)
5. Assign users/groups for provisioning scope

**Deprovisioning behavior**: When a user is removed in Entra ID or the app assignment is revoked, Entra ID sends a SCIM deactivation request → Atlas removes access.

### JIT + SCIM coexistence

JIT and SCIM can coexist. SCIM handles proactive create/deprovision; JIT handles attribute sync at login time (updates name/email). Best practice for enterprise: enable both.

### SCIM vs SAML group assertions

- **SAML group assertions** (via `memberOf`): Groups evaluated at each login. Stale if user's group membership changes between logins.
- **SCIM group sync**: Groups pushed continuously. More accurate for dynamic group membership.
- For compliance-sensitive orgs with rapid staff turnover: prefer SCIM.

---

## 9. Federation Manager

The **Federation Management Console (FMC)** is the Atlas UI surface for configuring all federation components. It is a separate administrative interface from the standard Atlas project/org UI.

### Accessing the FMC

1. Log into Atlas → select any organization in your federation
2. Left sidebar → **Identity & Access** → **Federation**
3. Click **Open Federation Management App**

> The FMC URL pattern: `https://cloud.mongodb.com/v2#/federation/<federation-id>/`

### FMC navigation structure

| Section | Purpose |
|---------|---------|
| **Home / Quick Start** | 4-step guided setup: add domain → configure IdP → connect domain → activate IdP |
| **Identity Providers** | Create, edit, delete SAML IdP configurations; download Atlas metadata; manage Associated Domains; toggle Bypass SAML Mode; view Login URL per IdP |
| **Organizations** | Link/unlink orgs to federation; configure per-org default roles; set domain restrictions; manage role mappings per org |
| **Domains** | Add, verify, and delete domain entries; view verification status |
| **Advanced Settings** | Restrict User Membership to Federation toggle |

### Identity Provider configuration fields

| Field | Description |
|-------|-------------|
| **Configuration Name** | Human-readable label (e.g., "Okta Corp") |
| **Configuration Description** | Optional notes |
| **IdP Issuer URI** | SAML EntityID of the IdP (from IdP metadata) |
| **IdP Single Sign-On URL** | URL Atlas sends AuthnRequest to |
| **IdP Signature Certificate** | PEM-encoded public cert; Atlas validates SAML Response signatures |
| **Request Binding** | `HTTP POST` or `HTTP REDIRECT` |
| **Response Signature Algorithm** | `SHA-256` (recommended) or `SHA-1` |

### Downloading Atlas SAML metadata XML

From FMC → Identity Providers → click **Download metadata** next to the IdP entry. The XML contains:
- ACS URL (SP endpoint for SAML Response)
- Audience URI (SP EntityID)
- Atlas self-signed certificate for request signing

Upload this file to your IdP to auto-populate SP configuration values.

### Login URL per IdP

Each configured IdP gets a unique **Login URL** in FMC. Share this URL with users for SP-initiated login that goes directly to the correct IdP, bypassing the email-lookup step.

### RelayState URLs for multiple MongoDB properties

Use RelayState to direct users to specific MongoDB services after authentication. The URLs below contain MongoDB's own static Okta app IDs — these are fixed values provided by MongoDB, not customer-specific. Copy them exactly.

| Service | RelayState URL |
|---------|----------------|
| MongoDB Atlas | Use the Login URL from FMC (unique per customer IdP) |
| Support Portal | `https://auth.mongodb.com/app/salesforce/exk1rw00vux0h1iFz297/sso/saml` |
| MongoDB University | `https://auth.mongodb.com/home/mongodb_thoughtindustriesstaging_1/0oadne22vtcdV5riC297/alndnea8d6SkOGXbS297` |
| Community Forums | `https://auth.mongodb.com/home/mongodbexternal_communityforums_3/0oa3bqf5mlIQvkbmF297/aln3bqgadajdHoymn297` |
| Feedback Engine | `https://auth.mongodb.com/home/mongodbexternal_uservoice_1/0oa27cs0zouYPwgj0297/aln27cvudlhBT7grX297` |
| MongoDB JIRA | `https://auth.mongodb.com/app/mongodbexternal_mongodbjira_1/exk1s832qkFO3Rqox297/sso/saml` |

### Audit logging for federation events

Atlas activity feeds and database audit logs are available at the org level. For federation-specific SSO events (login, failure, configuration changes), check:
- Atlas UI → Organization → Activity Feed (filter for auth/security events)
- Atlas Admin API: `GET /api/atlas/v2/orgs/{orgId}/events` — filter by event type
- IdP-side audit logs (Okta System Log, Entra ID Sign-in logs) for SAML assertion details

### Atlas Kubernetes Operator

The `AtlasFederatedAuth` custom resource allows Kubernetes-managed configuration of federation settings, supporting GitOps-driven IdP management. See: `docs/atlas/operator/current/ak8so-configure-federated-authentication/`

---

## 10. Troubleshooting

### Systematic debugging approach

1. Check the IdP-side logs first (Okta System Log, Entra ID Sign-in logs) — they show the raw SAML Response and any errors
2. Use your browser developer tools (Network tab) to capture the SAML POST to the ACS URL; base64-decode and inspect the assertion
3. Validate these assertion fields: `Issuer`, `Audience` (must match Atlas SP Entity ID), `NotBefore`/`NotOnOrAfter` timestamps, `NameID` format and value, `AttributeStatement` names (especially `memberOf`, `firstName`, `lastName`)
4. Check Atlas Activity Feed for server-side rejection events

### Error: SAML assertion validation failure (audience restriction mismatch)

**Symptom**: User gets authentication error; IdP logs show successful assertion issuance.

**Root cause**: The `<AudienceRestriction><Audience>` value in the SAML assertion does not **exactly** match the SP Entity ID Atlas expects.

**Fix**:
1. In Atlas FMC → Identity Providers → Download metadata → open XML → copy `entityID` attribute from `<EntityDescriptor>`
2. In your IdP's SAML app, set **Audience URI / SP Entity ID** to exactly this value (no trailing slash, exact case)
3. **Entra ID common mistake**: The setup guide uses `https://www.okta.com/saml2/service-provider/MongoDBCloud` as a *temporary* Identifier only until Atlas metadata is uploaded; after Step 5 of the Entra ID setup, the real Audience URI from the Atlas metadata replaces it. If the real value was never updated after upload, this placeholder will still be in place — check Entra ID Basic SAML Configuration to confirm the Identifier shows the value from the Atlas metadata XML, not the placeholder.

### Error: NameID format rejected

**Symptom**: Login fails; assertion is issued but Atlas rejects it.

**Root cause**: NameID format in the assertion is not `unspecified` or `emailAddress`.

**Fix**: In the IdP SAML app settings, set **Name ID Format** to `Unspecified`. Atlas requires:
```
urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified
```
or
```
urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress
```
The NameID value must be a valid email address matching the user's Atlas username.

### Error: Clock skew (assertion not yet valid / already expired)

**Symptom**: Intermittent login failures, especially across regions or after server restarts.

**Root cause**: The `NotBefore` or `NotOnOrAfter` timestamps in the assertion fall outside the SP's tolerance window because system clocks are not synchronized.

**Fix**:
1. Ensure NTP is configured on the IdP servers
2. Most SAML libraries allow a `clockSkewMs` tolerance setting; a 180-second tolerance is typical
3. Do not exceed 300 seconds — this is a security control

### Error: Group mapping not applying (memberOf attribute name mismatch)

**Symptom**: User logs in successfully but no roles appear in Atlas, even though role mappings are configured.

**Root cause**: The SAML attribute name the IdP sends does not match `memberOf` exactly, or the attribute is missing.

**Diagnostic**:
1. Capture SAML Response (browser DevTools → Network → look for POST to ACS URL → base64 decode the SAMLResponse param)
2. Check for attribute named `memberOf` in `<AttributeStatement>`; note exact name
3. Verify IdP group attribute statement is configured with exactly `memberOf` (case-sensitive)

**Entra ID specific**: Ensure the group claim is customized with name `memberOf` and Namespace is blank. "Emit groups as role claims" must be **unchecked**.

**Okta specific**: Group Attribute Statement must use name `memberOf`, filter `Matches regex .*` (or narrower regex).

**Atlas role mapping**: Group Name in Atlas must exactly match what appears in `memberOf` — either display name or Object ID, depending on IdP configuration.

### Error: Domain verification failing

**Symptom**: DNS TXT record added but Atlas shows domain as unverified.

**Causes and fixes**:
- **DNS propagation**: Wait up to 24–48 hours after adding TXT record
- **Wrong TXT value**: Verify the exact string `mongodb-site-verification=<32-char-string>` is in DNS; check with `dig TXT yourdomain.com` or `nslookup -type=TXT yourdomain.com`
- **HTML file not accessible**: Ensure `https://host.domain/mongodb-site-verification.html` returns HTTP 200 with file content; HTTPS required
- **Wrong subdomain**: TXT record must be on the exact domain (not a subdomain) unless the domain mapping is for a subdomain

### Error: Bypass user accidentally added to SSO domain

**Symptom**: An admin/breakglass account can no longer log in with Atlas credentials.

**Root cause**: The breakglass account's email domain was claimed and mapped to an IdP.

**Fix**: Either remap the breakglass account to an unclaimed email domain, or temporarily disable bypass SAML mode (if accessible), or use Atlas Support escalation.

### Error: Domain restriction too broad (wrong domain claimed)

**Symptom**: Users who should not be SSO-gated are being redirected to IdP, or users outside the org cannot be invited.

**Root cause**: A broad domain (e.g., `gmail.com` or `company.com` when the IdP only manages `us.company.com`) was verified and mapped.

**Fix**: Remove the overly broad domain mapping from FMC → Domains, add the correct narrow domain, and re-verify.

### Error: Certificate expiry

**Symptom**: All SSO logins fail after a date; IdP logs show signature validation failure.

**Root cause**: The IdP signing certificate uploaded to Atlas has expired.

**Fix**:
1. Generate/download new certificate from IdP
2. FMC → Identity Providers → Edit → upload new PEM certificate
3. Test login before removing old cert (some IdPs allow overlapping certs during rotation)

**Proactive rotation** (before expiry):
- Atlas generates an alert "Organization's IdP certificate is about to expire" when orgs are mapped — configure this alert to notify your ops team
- Check FMC → Identity Providers → the cert expiry date is visible in the IdP entry
- Rotate procedure: generate new cert in IdP → add new cert to Atlas IdP config → verify login works → remove old cert from IdP → update Atlas if IdP rotates its signing key

### Error: Multiple IdP redirect (wrong IdP selected)

**Symptom**: User lands on wrong IdP login page.

**Root cause**: One domain is mapped to multiple IdPs; Atlas routes to the first configured.

**Fix**: Use SP-initiated login URL (unique per IdP in FMC) to direct users to the correct IdP. Do not rely on the general Atlas login page when multiple IdPs share a domain.

---

## Quick-Reference Checklist: New Federation Setup

```
[ ] Organization Owner role confirmed
[ ] Custom routable domain available
[ ] IdP admin access confirmed
[ ] SAML app created in IdP (Okta / Entra ID / other)
[ ] IdP signing certificate downloaded and converted to PEM
[ ] Atlas FMC opened, IdP entry created with placeholder values
[ ] Atlas SAML metadata XML downloaded from FMC
[ ] Atlas metadata uploaded to IdP (sets real ACS URL and Audience URI)
[ ] IdP real Issuer URI and SSO URL entered in Atlas FMC
[ ] Attribute statements configured in IdP: firstName, lastName, memberOf
[ ] Domain verified (DNS TXT or HTML file) in FMC
[ ] Domain associated with IdP in FMC
[ ] Bypass SAML Mode URL saved securely
[ ] Tested in private browser with real user credentials
[ ] Role mappings created for IdP groups
[ ] Default org role set (optional)
[ ] Breakglass account confirmed working (non-federated domain or bypass URL)
[ ] Domain restriction enabled (optional)
[ ] SCIM provisioning configured in IdP (if deprovisioning required)
```

---

## References and See Also

**MongoDB Official Documentation**
- [Configure Federated Authentication](https://www.mongodb.com/docs/atlas/security/federated-authentication/)
- [Manage Identity Providers](https://www.mongodb.com/docs/atlas/security/manage-federated-auth/)
- [Advanced Options for Federated Authentication](https://www.mongodb.com/docs/atlas/security/federation-advanced-options/)
- [Manage Organization Mapping](https://www.mongodb.com/docs/atlas/security/manage-org-mapping/)
- [Manage Role Mapping](https://www.mongodb.com/docs/atlas/security/manage-role-mapping/)
- [Configure Federated Auth from Okta](https://www.mongodb.com/docs/atlas/security/federated-auth-okta/)
- [Configure Federated Auth from Microsoft Entra ID](https://www.mongodb.com/docs/atlas/security/federated-auth-azure-ad/)
- [Configure Federated Auth from Google Workspace](https://www.mongodb.com/docs/atlas/security/federated-auth-google-ws/)
- [Configure Federated Auth from PingOne](https://www.mongodb.com/docs/atlas/security/federated-auth-ping-one/)
- [AtlasFederatedAuth Kubernetes Operator CRD](https://www.mongodb.com/docs/atlas/operator/current/ak8so-configure-federated-authentication/)

**Microsoft Entra ID**
- [Configure MongoDB Atlas - SSO for Single Sign-On with Microsoft Entra ID](https://learn.microsoft.com/en-us/entra/identity/saas-apps/mongodb-cloud-tutorial)
- [SCIM endpoint development guide](https://learn.microsoft.com/en-us/entra/identity/app-provisioning/use-scim-to-provision-users-and-groups)

**Okta**
- [Integrate MongoDB Atlas with Okta](https://www.okta.com/integrations/mongodb-atlas/)
- [JumpCloud MongoDB Cloud integration](https://jumpcloud.com/support/integrate-with-mongodb-cloud)

**SAML debugging**
- [SAML debugging handbook 2026 — Scalekit](https://www.scalekit.com/blog/saml-debugging-handbook-2026-how-to-diagnose-log-and-resolve-sso-failures)
- [Diagnosing SAML assertion failures — WorkOS](https://workos.com/blog/saml-assertion-failures-debugging-guide)

**Related skills**:
- [[mongodb-atlas-expert]] — Atlas product breadth and tier feature gating
- [[mongodb-security-architecture]] — Broader Atlas security posture, threat model
- [[okta-expert]] — Okta-specific configuration, SAML app setup, SCIM in Okta
- [[mongodb-atlas-azure]] — Entra ID integration in the Azure/Atlas context
- [[mongodb-atlas-iam-rbac]] — Full Atlas IAM including OIDC, X.509, LDAP, service accounts
