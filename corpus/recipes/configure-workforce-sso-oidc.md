---
name: configure-workforce-sso-oidc
title: Configure workforce SSO and OIDC federation for Atlas
summary: Connect an external identity provider to an Atlas organization for UI login (SAML) and optionally database login (workforce OIDC), map IdP groups to roles, test, and roll back safely.
applies_to: [atlas]
sources:
  - skills/mongodb-atlas-expert/references/mongodb-atlas-federated-auth.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-iam-rbac.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-identity-policy-frontier-20261001.md
  - skills/mongodb-operations-expert/references/mongodb-security-architecture.md
---
# Configure workforce SSO and OIDC federation for Atlas

## When to use
- Your company wants employees to sign in to the Atlas UI through the corporate identity provider (IdP) instead of Atlas passwords.
- You want IdP groups to grant Atlas organization and project roles automatically.
- You want humans to reach databases through mongosh or Compass with SSO identities instead of long-lived SCRAM passwords (workforce OIDC).

Two separate configurations are involved:
- **Atlas UI login** uses SAML 2.0 through the Federation Management Console (FMC). It does not control database authentication.
- **Database login for humans** uses a workforce OIDC IdP. It is a different IdP entry from the SAML one. An organization supports at most one SAML IdP (UI) plus one OIDC IdP (database access).

For application workloads, use workload identity federation instead (see `create-database-users-and-roles`).

## Prerequisites (checklist)
- [ ] You are Organization Owner in Atlas.
- [ ] You have admin access to the IdP (for example Okta or Microsoft Entra ID, which the corpus documents).
- [ ] You control a routable email domain (`<your-domain>`) and can add a DNS TXT record, or host a file at that domain.
- [ ] A breakglass Organization Owner exists on an email domain that will NOT be federated, with a strong password in a secrets manager and Atlas 2FA on.
- [ ] MFA is enforced at the IdP. Federated logins bypass Atlas-side 2FA.
- [ ] For database OIDC: dedicated cluster M10 or larger, MongoDB 7.0.11 or later, mongosh 2.1.4+ or Compass 1.38+ (tentative per corpus).
- [ ] A private browser window and a test user in a test group are ready.

## Steps

### 1. Open the Federation Management Console
```text
Atlas UI: Organization Settings > Identity & Access > Federation > Open Federation Management App
```
Expect: the console with Identity Providers, Domains, Organizations and Role Mappings.

### 2. Create the SAML app in the IdP with placeholders
In the IdP create a SAML 2.0 application. Use placeholder SSO URL and Audience values for now. Download the signing certificate and convert it to PEM:
```bash
openssl x509 -in mycert.crt -out mycert.pem -outform PEM
```
Expect: `mycert.pem` exists.

### 3. Create the IdP entry in Atlas
```text
FMC > Identity Providers > Setup Identity Provider
  Upload the PEM certificate
  Request Binding: HTTP POST
  Algorithm: SHA-256
```
Expect: the IdP appears with status Inactive until a domain is associated (step 6).

### 4. Exchange metadata
Download the Atlas metadata XML from the FMC. In the IdP set the Single sign-on URL to the Atlas ACS URL and the Audience URI to the Atlas Entity ID, both taken from that XML. Set Name ID format to Unspecified (or emailAddress) with the user email as value. Sign the response and assertion with RSA-SHA256 and SHA256 digest. Then copy the IdP's real Issuer URI and SSO URL back into the Atlas IdP entry.

Expect: the IdP "Setup Instructions" values are stored in Atlas; no `localhost` placeholders remain.

### 5. Add attribute statements
Add these in the IdP, with exact, case-sensitive names:

| Attribute | Value |
|---|---|
| `firstName` | user first name |
| `lastName` | user last name |
| `memberOf` | group names (Okta example: group attribute statement, filter "Matches regex", value `.*` or a narrower prefix) |

For Microsoft Entra ID: customize the group claim name to `memberOf`, leave Namespace blank, uncheck "Emit groups as role claims". If the source attribute is Group Id, Atlas needs the group Object ID (GUID), not the display name.

Expect: a test assertion contains `memberOf`, `firstName`, `lastName` and a NameID that is an email address.

### 6. Verify the domain and associate it with the IdP
```text
FMC > Domains > Add a Domain > DNS Record
Add TXT record:  mongodb-site-verification=<32-character-string>
FMC > Domains > Verify
FMC > Identity Providers > Edit > Associated Domains > select the domain > Confirm
```
Check DNS:
```bash
dig TXT <your-domain>
```
Expect: the TXT value is returned and the domain shows Verified. Propagation can take minutes to hours (up to 24 to 48 hours in the corpus). The IdP changes from Inactive to Active after association. Claim only the exact domain your IdP manages; a broad domain such as a shared public mail domain sends the wrong people to SSO.

### 7. Save the bypass URL and link the organization
```text
FMC > Identity Providers > <your IdP> > copy "Bypass SAML Mode URL"   (do not click the toggle)
FMC > Link Organizations > Configure Access > Connect Identity Provider > <your IdP> > Confirm
```
Expect: the organization shows as connected. Store the bypass URL in your secrets manager.

### 8. Create role mappings and a default role
```text
FMC > Organizations > <org> > Manage Role Mappings > Create A Role Mapping
  Group Name:       <exact IdP group name, or Object ID for Entra ID>
  Organization Role: e.g. Organization Member
  Project Role(s):  e.g. Project Data Access Read Only (optional)
FMC > Organizations > <org> > Default User Role > Organization Member
```
Expect: mappings listed. Rules: names are case-sensitive and at most 200 characters; matched roles from all groups are added together; IdP groups cannot be mapped to Atlas teams, only to org and project roles; the last Organization Owner cannot be removed.

### 9. Test in a private browser
```text
Open a private window > https://cloud.mongodb.com > enter test-user@<your-domain>
```
Expect: redirect to the IdP, then landing in the organization with the mapped roles. First login creates the account just in time (JIT).

### 10. (Optional) Add SCIM for real-time deprovisioning
Role changes from `memberOf` sync only at next login. Verify in the current MongoDB docs: this entire step. Confirm whether Atlas offers an IdP-facing SCIM provisioning endpoint for workforce users at all, and if it does, its endpoint, authentication method and supported attributes. Do not assume one exists; until confirmed, plan to remove leavers from the IdP and from Atlas organization membership manually (or via the Atlas API), and rely on session expiry for revocation.

### 11. (Optional) Workforce OIDC for database access
```text
FMC > Identity Providers > Setup Identity Provider > Workforce Identity Provider (OIDC)
  Issuer URI:     <IdP issuer URL>
  Audience:       <audience value registered in the IdP>
  Authorization:  Group Membership (groups claim, default "groups")  or  User ID (default claim "sub")
```
Link the OIDC IdP to the organization, then add a federated database user:
```text
Database Access > Add New Database User > Federated Auth
  Identity Provider: <your OIDC IdP>
  Identifier:        <IdP group or user identifier>
  Roles:             <built-in or custom database roles>
```
Connect with mongosh (device flow for machines without a browser):
```bash
mongosh "mongodb+srv://<cluster-name>.<id>.mongodb.net/?authMechanism=MONGODB-OIDC&authSource=%24external" --oidcFlows=device-auth
```
Expect: the browser or device-code prompt appears, then `db.runCommand({connectionStatus: 1})` shows the federated user. Use a dedicated group prefix in the groups claim filter instead of `.*` so the token stays under the default 16 KiB pre-auth size limit.

## Verify
```text
Atlas UI > Organization > Access Manager  (mapped users show roles)
Atlas UI > Organization > Activity Feed   (look for federation and login events)
```
- A user in the mapped group gets the expected roles; a user outside every group gets only the default role.
- Remove the test user from the group, log in again, and confirm the mapped role is gone.
- A user on a non-federated domain (the breakglass account) can still sign in.
- Confirm the IdP certificate expiry alert exists (Atlas creates it when orgs are mapped) and note the expiry date shown in the IdP entry.

## Rollback / abort
1. Use the saved Bypass SAML Mode URL to sign in with Atlas credentials if SSO is broken (enabled by default).
2. Disconnect the IdP from the organization: `FMC > Organizations > Manage > Disconnect Identity Provider`. Existing users keep access; new SSO logins no longer auto-provision membership.
3. To delete a domain mapping, first disassociate it from every IdP, then delete.
4. If locked out with bypass disabled and no breakglass account, contact MongoDB Support with the org id and proof of ownership. This is slow.
5. Once SSO is validated, consider disabling bypass mode, but only while a non-federated breakglass owner works.

## Pitfalls
- Audience mismatch: the Audience in the assertion must exactly match the Atlas Entity ID from the metadata XML (no trailing slash, exact case). A leftover placeholder from setup is the usual cause.
- NameID format other than `unspecified` or `emailAddress` is rejected.
- `memberOf` attribute missing or misspelled: login works but no roles appear.
- Entra ID: using the group display name instead of the Object ID in the Atlas mapping.
- Claiming the breakglass account's domain for SSO locks the breakglass account out.
- Clock skew between IdP and Atlas causes intermittent failures; keep NTP on and do not exceed a 300 second tolerance.
- Expired IdP signing certificate breaks every login. Add the new certificate, test, then remove the old one.
- A domain mapped to several IdPs redirects to the first SAML IdP; use the per-IdP login URL.
- Do not edit per-user roles in Access Manager for users governed by group mappings.
- Pulling every group into the OIDC token (`.*`) can exceed the token size limit; Entra ID may return an overage reference when a user has more than 200 groups.
- Workforce OIDC (humans) and workload OIDC (applications) are separate IdP configurations.
- Development tiers (M0, Flex) cannot test database OIDC; use a small M10.

## Sources
- `skills/mongodb-atlas-expert/references/mongodb-atlas-federated-auth.md:88-146` (architecture, what federation disables)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-federated-auth.md:163-240` (Okta and Entra ID steps, attribute statements)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-federated-auth.md:244-320` (connected orgs, role mapping behavior and constraints)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-federated-auth.md:322-406` (domain verification, bypass mode, breakglass)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-federated-auth.md:458-505` (SCIM, with the "verify the endpoint" warning)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-federated-auth.md:583-720` (troubleshooting, setup checklist)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-iam-rbac.md:492-561` (workforce federation, memberOf mapping, limits)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-iam-rbac.md:1015-1060` (tier gating, authMechanism and authSource cheat sheet)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-identity-policy-frontier-20261001.md:25,40-46,62-64,87-90` (workforce OIDC requirements, flows, group claim size, Entra overage)
