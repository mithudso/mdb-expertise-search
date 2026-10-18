<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-app-services` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-app-services
title: "MongoDB Atlas App Services — Full Platform Reference (Beyond Triggers & Functions)"
version: "1.1.0"
last-updated: "2026-05-29"
category: mongodb
description: >
  Reference for Atlas App Services platform layers beyond Triggers and Functions — covering the
  full pre-EOL surface plus migration guidance post-September 2025.
  TRIGGER: user asks about Atlas App Services Authentication providers (email/password, anonymous,
  API key, OAuth2, Custom JWT, Custom Function auth), configuring or debugging App Services Rules
  and Permissions (roles, apply_when expressions, field-level access, document filters), App Services
  schema validation vs mongod $jsonSchema, the Atlas GraphQL API (deprecated March 2025 — migration to
  Hasura), the Atlas Data API (deprecated September 30 2025 — migration paths), Custom HTTPS Endpoints
  (deprecated), App Services deployment (appservices push/pull, GitHub auto-deploy, draft mode,
  rollback), Values and Secrets (context.values.get, secret linking, environment values), App Services
  billing model, or migrating away from deprecated App Services features.
  SKIP: Database Triggers, Scheduled Triggers, Authentication Triggers, and Atlas Functions invoked by
  triggers (use mongodb-atlas-triggers-functions), Device Sync and Realm mobile SDK
  (use mongodb-realm-mobile-sync), Atlas cluster configuration and billing (use mongodb-atlas-expert),
  general MongoDB authentication and LDAP (use mongodb-security-architecture or mongodb-atlas-iam-rbac).
tags:
  - "mongodb"
  - "atlas"
  - "app-services"
  - "authentication"
  - "permissions"
  - "rules"
  - "schema-validation"
  - "graphql"
  - "data-api"
  - "deprecated"
  - "eol"
  - "deployment"
  - "secrets"
  - "migration"
  - "realm"
keywords:
  - "atlas app services"
  - "app services authentication"
  - "email password auth"
  - "anonymous auth"
  - "api key auth"
  - "custom jwt"
  - "oauth2 google facebook apple"
  - "custom function auth"
  - "app services rules"
  - "app services permissions"
  - "role-based permissions"
  - "apply_when expression"
  - "field-level permissions"
  - "document-level permissions"
  - "app services schema"
  - "jsonSchema app services"
  - "atlas graphql api"
  - "graphql deprecated"
  - "hasura migration"
  - "atlas data api"
  - "data api deprecated"
  - "custom https endpoints"
  - "appservices push"
  - "appservices pull"
  - "github deployment app services"
  - "app services cli"
  - "context.values.get"
  - "app services secrets"
  - "app services values"
  - "environment values"
  - "app services billing"
  - "app services free tier"
  - "app services eol"
  - "atlas app services deprecation"
  - "realm migration"
  - "device sync eol"
whenToUse:
  - "User asks about Atlas App Services Authentication providers — email/password, anonymous, API key, JWT, OAuth2, Custom JWT, or custom function auth"
  - "User needs to configure or debug App Services Rules and Permissions (roles, apply_when expressions, field-level access, filters)"
  - "User asks about Atlas App Services schema validation and how it differs from mongod $jsonSchema"
  - "User asks about the Atlas GraphQL API, its deprecation (March 2025), or migration to Hasura"
  - "User asks about the Atlas Data API — what it was, its endpoints, deprecation (Sep 2025), and migration paths"
  - "User asks about Custom HTTPS Endpoints in App Services (webhook patterns, request/response transformation)"
  - "User needs to understand App Services deployment: appservices push/pull, GitHub auto-deploy, draft mode, rollback"
  - "User asks about App Services Values and Secrets (context.values.get, secret linking, environment values)"
  - "User asks about App Services billing model — free tier, request pricing, compute hours, sync runtime"
  - "User is migrating away from deprecated Atlas App Services features (Data API, GraphQL, Device Sync, Custom Endpoints)"
  - "User asks what still works in Atlas App Services post-September 2025 (Triggers remain; most else is EOL)"
whenNotToUse:
  - "Database Triggers, Scheduled Triggers, Authentication Triggers, or Atlas Functions invoked by triggers — use mongodb-atlas-triggers-functions"
  - "Device Sync, Realm mobile SDK, or offline-first mobile sync — use mongodb-realm-mobile-sync"
  - "Atlas cluster configuration, networking, or billing — use mongodb-atlas-expert"
  - "General MongoDB authentication at the cluster level (LDAP, x.509, SCRAM) — use mongodb-security-architecture or mongodb-atlas-iam-rbac"
  - "Ops Manager or self-managed MongoDB management — use mongodb-ops-manager"
related_skills:
  - "mongodb-atlas-triggers-functions"
  - "mongodb-realm-mobile-sync"
  - "mongodb-atlas-expert"
  - "mongodb-security-architecture"
  - "mongodb-atlas-iam-rbac"
---

# MongoDB Atlas App Services — Full Platform Reference

> **CRITICAL STATUS NOTE (as of May 2026):** Atlas App Services reached a split end-of-life on September 30, 2025.
> - **STILL LIVE:** Database Triggers, Scheduled Triggers, Authentication Triggers, Atlas Functions (invoked by triggers only)
> - **EOL (shut down September 30, 2025):** Atlas Data API, GraphQL API, Custom HTTPS Endpoints, Atlas Device Sync & Device SDKs, static hosting
> - Auth providers, Rules/Permissions, and Values/Secrets are only relevant now as context for the still-live Triggers surface
> - See the [deprecation page](https://www.mongodb.com/docs/atlas/app-services/deprecation/) for official migration guidance
>
> This skill documents the full pre-EOL platform for historical reference and migration support. For active Triggers and Functions usage, see `mongodb-atlas-triggers-functions`.

---

## Overview: App Services Platform Architecture

Atlas App Services was MongoDB's managed backend-as-a-service layer built on top of Atlas clusters. An **App** is the unit of deployment — each Atlas project can have multiple apps, each with its own authentication, rules, functions, schemas, secrets, and endpoints. Apps have a unique **App ID** (e.g. `myapp-abcde`) used in SDK initialization and CLI operations.

```
Atlas Project
└── App Services App (App ID: myapp-abcde)
    ├── Authentication Providers  ← topic of this skill
    ├── Rules & Permissions       ← topic of this skill
    ├── Schema Validation         ← topic of this skill
    ├── Values & Secrets          ← topic of this skill
    ├── Atlas Functions           ← covered by mongodb-atlas-triggers-functions
    ├── Triggers                  ← covered by mongodb-atlas-triggers-functions
    ├── GraphQL API (DEPRECATED)  ← topic of this skill
    ├── Data API (DEPRECATED)     ← topic of this skill
    └── Custom HTTPS Endpoints (DEPRECATED) ← topic of this skill
```

**Related skills:**
- `mongodb-atlas-triggers-functions` — Database/Scheduled/Auth Triggers, Functions runtime, HTTPS Endpoints (trigger-invoked), CLI deployment
- `mongodb-realm-mobile-sync` — Device Sync, Realm SDK, Flexible Sync permissions model, offline-first

---

## Authentication Providers

### All Supported Providers

| Provider | Type ID | Description | Status (2026) |
|---|---|---|---|
| Anonymous | `anon-user` | No credentials, temporary identity | Active — used with Triggers |
| Email/Password | `local-userpass` | Register with email + password | EOL (Sep 30 2025) |
| API Key | `api-key` | Server or user API keys | Active — used with Triggers |
| Google OAuth2 | `oauth2-google` | OAuth2 via Google | EOL (Sep 30 2025) |
| Facebook OAuth2 | `oauth2-facebook` | OAuth2 via Facebook | EOL (Sep 30 2025) |
| Apple ID | `oauth2-apple` | OAuth2 via Apple | EOL (Sep 30 2025) |
| Custom JWT | `custom-token` | Third-party JWT verification | EOL (Sep 30 2025) |
| Custom Function | `custom-function` | Arbitrary auth logic in a Function | EOL (Sep 30 2025) |

### Anonymous Authentication

Simplest provider — creates a temporary user with no credentials. Ideal for read-only access or pre-registration flows. Anonymous users can later be **linked** to a permanent account (email/password, OAuth) using the Realm SDK `linkCredentials()` method. Anonymous user data is deleted after 90 days of inactivity.

### Email/Password Authentication

Configuration in `/auth/providers.json`:
```json
{
  "local-userpass": {
    "type": "local-userpass",
    "config": {
      "autoConfirm": false,
      "emailConfirmationUrl": "https://myapp.com/confirm",
      "confirmEmailSubject": "Confirm your account",
      "runConfirmationFunction": false,
      "confirmationFunctionName": "",
      "resetPasswordUrl": "https://myapp.com/reset",
      "resetPasswordSubject": "Reset your password",
      "runResetFunction": false,
      "resetFunctionName": ""
    }
  }
}
```

**Email addresses are case-sensitive** (`user@example.com` ≠ `User@example.com`).

**Confirmation methods (mutually exclusive):**
1. **Send confirmation email** — App Services sends a link with `token` + `tokenId` query params, valid 30 minutes. Client calls `confirmUser(token, tokenId)`. Emails always come from a `mongodb.com` domain — use Custom Function method for branded emails.
2. **Run a confirmation Function** — Function receives `{ username, token, tokenId }`, returns `{ status: 'success' | 'pending' | 'fail' }`. Return `pending` to require the client to call `confirmUser()` after an out-of-band verification (SMS, internal check).
3. **Automatically confirm** — Never use in production. No email validation; no recovery path.

**Password reset methods (mutually exclusive):**
1. **Send a reset email** — Same token pattern, 30-minute expiry.
2. **Run a reset Function** — Receives `{ username, password, token, tokenId, currentPasswordValid }`. **CRITICAL SECURITY WARNING:** `callResetPasswordFunction()` is **unauthenticated** — any caller can invoke it. Returning `success` immediately changes the password. Always return `pending` and perform out-of-band identity verification before finalizing.

### API Key Authentication

Two subtypes:
- **Server API Keys** — Created in the Atlas UI or via Admin API. Used by server processes (scripts, CI/CD, backend services) calling Data API endpoints or via the Realm Web SDK.
- **User API Keys** — Created by authenticated users via the Realm SDK. Scoped to the creating user's identity and permissions.

API key strings are shown **once** at creation and cannot be retrieved again.

### Custom JWT Authentication

For integrating with any third-party identity provider (Auth0, Firebase Auth, AWS Cognito, Okta, or any IdP that issues JWTs).

**Verification options:**
1. **Manual signing keys** — You provide one or more HMAC (HS256) or RSA (RS256) signing keys as secrets. App Services verifies the JWT signature locally.
2. **JWK URI** — Point to the provider's `/.well-known/jwks.json` endpoint. App Services fetches the public keys and verifies. Supports up to 3 keys. Automatically uses RS256.

```json
{
  "custom-token": {
    "config": {
      "useJWKURI": true,
      "jwkURI": "https://your-idp.com/.well-known/jwks.json",
      "audience": ["your-app-client-id"]
    }
  }
}
```

**JWT metadata field mapping** — Map arbitrary JWT claims to user metadata:
```json
{
  "metadata_fields": [
    { "required": true, "name": "user_data.name", "field_name": "name" },
    { "required": false, "name": "user_data.email", "field_name": "email" }
  ]
}
```
Use dot notation for nested fields; escape literal periods with `\.`.

**Access token behavior:** App Services always enforces a **30-minute access token expiry**, regardless of the JWT's `exp` claim. Realm SDKs auto-refresh; Data API callers must handle 401s and refresh.

**Limits:** Max JWT length 1 million chars; max metadata field value 4,096 chars.

### Custom Function Authentication

Runs an Atlas Function that receives credentials as a JSON object, validates them against any external system, and returns `{ id: "<unique user id>" }` on success or throws on failure. Useful for legacy auth systems.

### OAuth2 Providers (Google, Facebook, Apple)

All three use OAuth 2.0 authorization code flow. Configuration requires:
- **Client ID** and **Client Secret** (stored as a Secret)
- **Redirect URI** whitelist
- Optional metadata field mapping from the provider's profile endpoint

Users can link multiple OAuth identities to a single App Services user account.

---

## Rules and Permissions Engine

> **Note:** Rules and Permissions were relevant primarily for Data API and Device Sync — both are now EOL. They still gate access when functions call the MongoDB data source via non-system context. **System functions bypass all rules.**

### Architecture

Permissions are defined per-collection and enforced dynamically per-document per-request. The engine intercepts every MongoDB operation from a non-system execution context and:
1. Evaluates which **Role** applies to the requesting user + target document
2. Applies document-level and field-level permissions from that role
3. **Denies access** if no role matches

### Role Definition Structure

```json
{
  "name": "Owner",
  "apply_when": { "owner_id": "%%user.id" },
  "insert": true,
  "delete": true,
  "search": true,
  "read": true,
  "write": true,
  "fields": {
    "salary": { "read": false, "write": false }
  },
  "additional_fields": { "read": true, "write": true },
  "document_filters": {
    "read": { "owner_id": "%%user.id" },
    "write": { "owner_id": "%%user.id" }
  }
}
```

### Role Evaluation Algorithm

1. If the collection has explicit roles defined, evaluate only those (App Services does **not** fall back to default roles when collection-level roles exist — this is a common gotcha).
2. Evaluate each role's `apply_when` expression **in order** against the requesting user's context (`%%user`, `%%user.custom_data`) and the target document (`%%root`).
3. **First matching role wins** — role order matters. List most-specific roles first.
4. If no role matches, the operation is **denied entirely** (reads return empty, writes fail with permission error).

### Rule Expressions (%%variables)

App Services uses a JSON-based expression DSL. Common variables:

| Variable | Description |
|---|---|
| `%%user.id` | Authenticated user's unique ID |
| `%%user.data.<field>` | User's provider-specific data |
| `%%user.custom_data.<field>` | Custom user data (from a linked collection) |
| `%%root.<field>` | Field value in the current document |
| `%%true` / `%%false` | Boolean constants |
| `%%environment.tag` | Current environment tag (e.g., "production") |
| `%%environment.values.<name>` | Environment-specific value |

**Operators in expressions:**
```json
{ "%or": [expr1, expr2] }
{ "%and": [expr1, expr2] }
{ "%not": expr }
{ "<field>": { "%in": ["a", "b"] } }
```

### Filters

Filters are applied **before** rule evaluation and modify the query predicate. They add additional match conditions and can project out fields, reducing the documents the permissions engine must evaluate. Filters improve performance for large collections where most documents are irrelevant to the requesting user.

```json
{
  "name": "Only active records",
  "apply_when": {},
  "query": { "status": "active" },
  "projection": { "internal_notes": 0 }
}
```

### Document-Level vs Field-Level Permissions

| Level | Controls | Configuration |
|---|---|---|
| Document | Insert, Delete, Search on entire docs | Top-level `insert`, `delete`, `search` booleans |
| Field | Read/Write per named field | `fields.<fieldName>.read`, `fields.<fieldName>.write` |
| Default fields | Read/Write for unlisted fields | `additional_fields.read`, `additional_fields.write` |

Field-level permissions apply to **embedded documents** via dot notation:
```json
{
  "fields": {
    "address.zipCode": { "read": true, "write": false }
  }
}
```

### Device Sync vs. Non-Sync Permission Behavior

Without Device Sync: roles are evaluated **per-document, per-request** — different documents in the same query result may get different roles.

With Device Sync (Flexible Mode): roles are evaluated **once per session, per collection** — the role is locked at sync session start and remains for the session's lifetime. This is why sync-compatible roles must use **document filters** rather than `apply_when` referencing `%%root` fields.

### Security Side-Channel Warning

Rules hide documents/fields from query results but do **not** prevent information leakage through: error messages that encode existence, timing side-channels (query execution time), or functions that run as system users and bypass all rules.

---

## Schema Validation as a Service

### How It Works

App Services schemas are JSON Schema definitions (based on draft 4, with BSON type extensions) applied per-collection. App Services validates every write operation **after** the operation is computed but **before** it is committed:
- If any document fails validation, the **entire operation is rejected** and rolled back
- Validation applies to insertions, updates, and replaces from non-system execution contexts

```json
{
  "title": "Order",
  "bsonType": "object",
  "required": ["orderId", "customerId", "total"],
  "properties": {
    "orderId": { "bsonType": "objectId" },
    "customerId": { "bsonType": "string" },
    "total": { "bsonType": "decimal" },
    "status": {
      "bsonType": "string",
      "enum": ["pending", "shipped", "delivered", "cancelled"]
    },
    "items": {
      "bsonType": "array",
      "items": {
        "bsonType": "object",
        "required": ["sku", "qty"],
        "properties": {
          "sku": { "bsonType": "string" },
          "qty": { "bsonType": "int" }
        }
      }
    }
  }
}
```

### Key Differences from mongod `$jsonSchema`

| Dimension | App Services Schema | mongod `$jsonSchema` |
|---|---|---|
| Enforcement point | App Services layer (before cluster commit) | MongoDB server-side |
| Who can bypass | System functions always bypass App Services schema | Only `mongod` level operations bypass; driver operations still checked |
| Configuration | Stored in App Services config files (`/data_sources/<source>/<db>/<collection>/schema.json`) | Stored as `$jsonSchema` validator on the collection in mongod |
| Draft support | JSON Schema draft 4 + BSON extensions | JSON Schema draft 4 + BSON extensions |
| Simultaneous use | Can coexist with mongod validator, but **incompatible interactions are possible** | Independent |
| Recommendation | Start with `warn` validation level on mongod side when running both | N/A |
| Device Sync interaction | Schema drives Realm SDK object model generation | No sync awareness |

**Incompatibility risk:** App Services validates post-operation (checks the resulting document state), while mongod validates at the server level. Running both with `error` mode on mongod can cause App Services to attempt an operation that then fails at the cluster level, resulting in confusing error paths.

### Device Sync Schema Constraints

When using Device Sync with schemas, avoid:
- `required` fields on embedded documents or arrays (sync treats missing/null/empty-array as equivalent)
- Distinguishing between `undefined`, `null`, `[]`, and `{}` — the sync protocol normalizes these
- Schema changes that remove required fields without a client migration

---

## Atlas GraphQL API (DEPRECATED — EOL March 5, 2025)

> **Status:** End-of-life March 5, 2025. GraphQL endpoints shut down. Migrate to Hasura or build your own GraphQL layer.

### What It Was

An automatically generated GraphQL API derived from App Services collection schemas. Each collection with a schema got:
- Auto-generated `query` (find one, find many, with filtering/sorting/pagination)
- Auto-generated `mutation` (insertOne, updateOne, updateMany, deleteOne, deleteMany, replaceOne)
- Auto-generated input types mirroring the schema

### Custom Resolvers

Custom resolvers extended the auto-generated schema with app-specific queries and mutations backed by Atlas Functions. A resolver defined:
- The GraphQL type extension (added to query/mutation root)
- The return type (an existing generated type, a custom type, or a scalar)
- The backing Atlas Function
- Input type definition

```graphql
type Query {
  # Auto-generated
  order(query: OrderQueryInput): Order
  orders(query: OrderQueryInput, limit: Int, sortBy: OrderSortByInput): [Order]!
  # Custom resolver
  ordersByRegion(region: String!, limit: Int): [Order]!
}
```

### Known Limitations (Pre-deprecation)

- Not real-time — no subscriptions support
- Relationships required explicit resolver setup; no foreign key auto-join
- No batching (N+1 query problem without explicit custom resolvers)
- 4 MB response payload limit
- Authentication: same App Services auth providers (Bearer token or credential headers)
- Performance: every GraphQL query ran through the App Services function runtime, adding ~50–100ms overhead vs. direct driver connections

### Migration Path

MongoDB's official recommendation: [Migrate to Hasura](https://www.mongodb.com/docs/atlas/app-services/graphql/migrate-hasura/) — Hasura provides equivalent auto-generated GraphQL + custom resolvers against MongoDB Atlas. Alternative: build a custom GraphQL server using Apollo Server or Yoga + MongoDB Node.js driver.

---

## Atlas Data API (DEPRECATED — EOL September 30, 2025)

> **Status:** End-of-life September 30, 2025. All endpoints shut down. **Do not build new integrations against the Data API.**

### What It Was

A managed HTTPS interface providing MongoDB CRUD and aggregation operations over standard HTTP requests, without requiring a MongoDB driver. Useful for: IoT devices, low-code platforms, CI/CD scripts, and client-side JavaScript that couldn't use the driver.

**Base URL pattern:** `https://data.mongodb-api.com/app/<App-ID>/endpoint/data/v1`

### Endpoint Catalog (Historical)

| Action | Method | Path |
|---|---|---|
| findOne | POST | `/action/findOne` |
| find | POST | `/action/find` |
| insertOne | POST | `/action/insertOne` |
| insertMany | POST | `/action/insertMany` |
| updateOne | POST | `/action/updateOne` |
| updateMany | POST | `/action/updateMany` |
| deleteOne | POST | `/action/deleteOne` |
| deleteMany | POST | `/action/deleteMany` |
| aggregate | POST | `/action/aggregate` |

All requests were JSON POST bodies:
```json
{
  "dataSource": "Cluster0",
  "database": "mydb",
  "collection": "orders",
  "filter": { "status": "pending" },
  "projection": { "_id": 1, "total": 1 }
}
```

### Authentication Methods (Historical)

1. **API Key** — `api-key: <key>` header
2. **Email/Password session** — Start session via `/auth/providers/local-userpass/login`, use Bearer token from response
3. **Custom JWT** — `jwtTokenString: <token>` header
4. **Bearer token** — `Authorization: Bearer <access_token>` after establishing a session

### Limits (Historical)

| Limit | Value |
|---|---|
| Request timeout | 300 seconds |
| Response payload | 350 MB |
| Rate limits | Shared with App Services request billing |

### Migration Paths (Current Recommendation)

| Use case | Recommended migration |
|---|---|
| Server-side Node.js | MongoDB Node.js driver + Express/Fastify |
| Server-side Python | PyMongo + FastAPI |
| Server-side Java | MongoDB Java driver + Spring Boot |
| IoT / embedded | MongoDB driver for target language |
| AWS Lambda | MongoDB driver + Lambda |
| Azure Functions | [One-click Azure Functions template](https://github.com/mongodb-partners/MongoDB_DataAPI_Azure) |
| Drop-in replacement | [Delbridge Data API](https://github.com/delbridge-io/data-api) (open source) |
| GraphQL + REST | [Hasura](https://hasura.io/) or [RESTHeart](https://restheart.org/) |

---

## Custom HTTPS Endpoints (DEPRECATED — EOL September 30, 2025)

> **Status:** End-of-life September 30, 2025. Migrate to AWS Lambda, Azure Functions, Google Cloud Run, or Vercel serverless functions + MongoDB driver.

### What They Were

App-specific HTTP routes backed by Atlas Functions. Unlike the generated Data API endpoints, Custom Endpoints let you define arbitrary routes, request validation, and response transformation.

Configuration in `https_endpoints/config.json`:
```json
{
  "route": "/webhook/stripe",
  "http_method": "POST",
  "function_name": "handleStripeWebhook",
  "validation_method": "VERIFY_PAYLOAD",
  "secret_name": "stripe_webhook_secret",
  "respond_result": true,
  "fetch_custom_user_data": false,
  "create_user_on_auth": false,
  "disabled": false
}
```

### Request/Response Pattern

The backing Function received a `request` object and returned a `response` object:
```javascript
exports = async function({ body, headers, query }) {
  // Parse and validate
  const payload = JSON.parse(body.text());
  
  // Compute response
  const result = await context.services.get("mongodb-atlas")
    .db("mydb").collection("events")
    .insertOne({ ...payload, receivedAt: new Date() });
  
  return {
    statusCode: 200,
    headers: { "Content-Type": ["application/json"] },
    body: JSON.stringify({ insertedId: result.insertedId })
  };
};
```

### Payload Verification

For webhook endpoints (Stripe, GitHub, etc.), App Services supported **payload signature verification** using an HMAC secret. The secret was stored as an App Services Secret and referenced by name in the endpoint config.

---

## Values and Secrets

> **Status:** Still relevant — Values/Secrets are used by Triggers and Functions, which remain live.

### Values

A **Value** is a named, server-side JSON constant. Access from functions:
```javascript
const config = context.values.get("appConfig");
// Returns whatever JSON you defined: string, number, array, or object
```

Values are included in exported App configuration and visible in the Atlas UI.

### Secrets

A **Secret** is a private string value (max 500 characters) stored encrypted. Secrets:
- Are never exported (they disappear from exported app config)
- Cannot be read back after creation (you can only overwrite)
- Are accessed indirectly — link a Secret to a Value, then access via `context.values.get()`

```javascript
// WRONG — no direct secret access
const apiKey = context.secret.get("stripeKey"); // Does not exist

// RIGHT — link secret to a value named "stripeKeyValue"
const apiKey = context.values.get("stripeKeyValue"); // Returns secret value
```

CLI management:
```bash
appservices secrets create --name stripeKey --value sk_live_...
appservices secrets list
appservices secrets update --secret-id <id> --value <newval>
appservices secrets delete --secret-id <id>
```

### Environment Values

App Services supports environment tags: `""` (default), `"development"`, `"testing"`, `"qa"`, `"production"`. Environment-specific values resolve at runtime based on the app's current environment tag.

```javascript
// In a function
const endpoint = context.environment.values.apiBaseUrl;

// In a rule expression
{ "endpoint": "%%environment.values.apiBaseUrl" }
```

Use Case: Single app deployed to dev/staging/prod with different cluster connections or third-party API endpoints without code changes.

---

## App Services Deployment Model

### Apps and Configuration Files

App Services apps are fully represented as a directory tree of JSON/JS files. The canonical layout:
```
myapp/
├── config.json             # App metadata, cluster links, environment
├── auth/
│   └── providers.json      # Auth provider configurations
├── data_sources/
│   └── mongodb-atlas/
│       └── mydb/
│           └── orders/
│               ├── schema.json    # Collection schema
│               └── rules.json     # Collection roles/filters
├── functions/
│   ├── config.json
│   └── myFunction/
│       └── source.js
├── https_endpoints/
│   └── config.json
├── triggers/
│   └── myTrigger.json
├── values/
│   └── appConfig.json
└── environments/
    ├── development.json
    └── production.json
```

### Deployment Methods

#### 1. App Services UI
Interactive editor in Atlas. Immediate deployment. Best for initial setup and ad-hoc changes.

#### 2. App Services CLI (`appservices`)

```bash
# Install
npm install -g mongodb-app-services-cli

# Authenticate
appservices login --api-key <key> --private-api-key <private>

# Fetch current deployed config
appservices pull --remote <App-ID> --local ./myapp

# Deploy local changes
appservices push --remote <App-ID> --local ./myapp

# Deploy and include dependency upgrades
appservices push --remote <App-ID> --include-node-modules
```

**Draft mode:** To stage changes without immediately deploying, push with `--draft` (or omit `--yes`) so App Services creates a draft deployment you can review and promote via the UI or Admin API.

#### 3. GitHub Automatic Deployment

Link an App to a GitHub repository branch. Any push to the linked branch triggers automatic deployment. The repo must contain the App configuration directory at the root or a specified path.

**Setup:** App Services UI → App Settings → Deployment → GitHub. Requires GitHub OAuth app authorization.

**Gotcha:** Secrets are **not** included in the repo. After enabling GitHub deployment (or copying an app), you must re-enter all Secret values manually.

#### 4. Admin API

REST API at `https://services.cloud.mongodb.com/api/admin/v3.0/`. Supports all deployment operations programmatically. Authentication requires Atlas API Key pair with `project owner` permissions.

```bash
# List recent deployments
GET /groups/{groupId}/apps/{appId}/deployments

# Rollback to previous deployment
POST /groups/{groupId}/apps/{appId}/deployments/{deploymentId}/restore
```

### Deployment History and Rollback

App Services stores the **last 25 deployments**. You can:
- View deployment history in the Atlas UI under App Settings → Deployment
- Export any deployment as a zip archive
- Roll back to any of the last 25 via UI or Admin API

### Environments

Apps have one active environment tag. Switch tags in config.json or via Admin API. All `context.environment.values.<name>` references resolve to the active environment's values.

---

## Billing Model

> **Context:** Pre-EOL billing model. Triggers remain active and continue to consume the shared App Services billing budget.

### Free Tier (Shared Per Atlas Project)

All App Services apps in a project share a single monthly free tier:

| Resource | Free Allowance |
|---|---|
| Requests (Function invocations) | 1,000,000 / month |
| Compute time | 500 hours / month |
| Sync runtime (was) | 10,000 hours / month |
| Data transfer | 10 GB / month |

**Whichever limit is hit first** triggers billing for that resource. The thresholds are aggregated across all apps in the project, not per-app.

### Billable Events (Post-Free Tier)

- Each **Trigger invocation** = 1 request
- Each **Function call** = 1 request (when called from another function or via HTTP)
- Each **Data API request** (was) = 1 request
- Each **Custom HTTPS Endpoint** request (was) = 1 request
- **Compute time** = wall-clock time the function ran (rounded to nearest 100ms)
- **Sync runtime** (was) = duration of active Device Sync sessions

### Cost Avoidance Tips (Triggers)

1. Use **Match Expressions** to filter trigger events before function invocation — filtered events don't count as requests
2. Batch-process in scheduled triggers rather than one function per document
3. Minimize function execution time: avoid large loops, use aggregation pipelines, index correctly
4. Avoid trigger loops (writing to a collection from a trigger on that same collection without filtering)

---

## Anti-Patterns and Common Mistakes

### Authentication Anti-Patterns

1. **Auto-confirm in production** — Allows fake/typo email addresses; breaks password recovery. Always use email confirmation or a custom function.
2. **`callResetPasswordFunction` returning `success` immediately** — Unauthenticated callers can reset any user's password. Always return `pending` and perform out-of-band verification.
3. **Hardcoding JWT signing keys in function code** — Use Secrets and link to Values. Never put credentials in `source.js` files.
4. **Single authentication provider** — Linking multiple providers to one user account improves UX and reduces orphaned accounts.

### Rules/Permissions Anti-Patterns

1. **Collection-level roles defined but relying on default roles** — If you define any collection-level roles, App Services stops checking default roles. Ensure your collection-level roles cover all legitimate access patterns.
2. **Role order wrong** — Most permissive role first means every user gets admin access. List most restrictive/specific roles first.
3. **Using `%%root` in Device Sync `apply_when`** — Document field evaluation in `apply_when` is incompatible with Flexible Sync; use `document_filters` instead.
4. **System functions bypass all rules** — Don't assume App Services rules protect data modified by system-context functions (e.g., trigger functions using system context).

### Schema Anti-Patterns

1. **Running App Services schema AND mongod `$jsonSchema` with `validationAction: "error"`** — App Services validates post-operation; mongod validates at write time. Incompatible validation can cause confusing double-rejection errors. Start mongod at `"warn"` while debugging.
2. **Required fields in embedded arrays for Device Sync** — Sync protocol normalizes empty arrays and null; `required` on array items causes schema mismatch errors.

### Deployment Anti-Patterns

1. **Committing Secrets to git** — Secrets are not exported; never store them in the config repo. Use GitHub repository secrets for CI/CD, and populate App Services Secrets via CLI during deployment.
2. **Manual UI edits in a GitHub-linked app** — UI changes are overwritten by the next GitHub push. Use the repo as the source of truth.
3. **Not pinning npm dependency versions** — App Services resolves npm deps at deploy time; an unpinned dependency can change behavior on re-deploy.

---

## Migration Reference (Post-EOL)

### What to Migrate FROM and TO

| Feature | EOL Date | Recommended Replacement |
|---|---|---|
| Atlas Data API | Sep 30, 2025 | MongoDB driver + Express/FastAPI/Spring Boot or cloud functions (Lambda, Azure, GCR) |
| Atlas GraphQL API | Mar 5, 2025 | Hasura on MongoDB, Apollo Server + driver |
| Custom HTTPS Endpoints | Sep 30, 2025 | Cloud functions (AWS Lambda, Azure Functions, Google Cloud Run, Vercel) |
| Atlas Device Sync | Sep 30, 2025 | Couchbase Lite, PouchDB + CouchDB, custom sync layer, or Realm standalone (no sync) |
| Device SDKs | Sep 30, 2025 | Standard MongoDB drivers + custom mobile sync logic |
| Static Hosting | Sep 30, 2025 | Vercel, Netlify, AWS S3 + CloudFront |
| Authentication providers | Sep 30, 2025 | Auth0, Firebase Auth, AWS Cognito, Clerk |
| Rules/Permissions | Sep 30, 2025 | Application-layer authorization (middleware, OPA, attribute-based access control) |

### What STILL WORKS

- **Database Triggers** — Available in Atlas UI, backed by change streams
- **Scheduled Triggers** — Available in Atlas UI, cron-based
- **Authentication Triggers** — Available in Atlas UI, user lifecycle events
- **Atlas Functions** (when invoked by triggers) — V8 runtime, `context` object

---

## Troubleshooting Reference

### Common Errors

| Error | Cause | Fix |
|---|---|---|
| `"no rule exists"` on a query | No role matched the requesting user+document combination | Add or debug role `apply_when` expressions; check role order |
| `"schema validation failed"` | Document field type mismatch | Check `bsonType` in schema vs. actual data; note App Services uses `bsonType` not `type` |
| JWT `access token expired` after 30 min | App Services always enforces 30-min expiry | Implement token refresh in SDK or API client |
| `"confirmation token expired"` | Email confirmation link clicked > 30 min after registration | Re-send confirmation email; consider shortening UX flow |
| Trigger not firing | Match expression filtering all events | Test match expression against a sample change event; verify collection/DB name |
| GitHub deployment not updating | Secrets not re-entered after GitHub link | Enter all secrets manually after each new app copy or initial GitHub link |

---

## References

1. [Atlas App Services Documentation — Authentication](https://www.mongodb.com/docs/atlas/app-services/authentication/) — provider types, configuration
2. [Email/Password Authentication](https://www.mongodb.com/docs/atlas/app-services/authentication/email-password/) — confirmation/reset methods, security warnings
3. [Custom JWT Authentication](https://www.mongodb.com/docs/atlas/app-services/authentication/custom-jwt/) — JWK URI, metadata mapping
4. [Define Data Access Permissions](https://www.mongodb.com/docs/atlas/app-services/rules/) — Rules and Permissions overview
5. [Role-based Permissions](https://www.mongodb.com/docs/atlas/app-services/rules/roles/) — role evaluation algorithm, field-level permissions
6. [Filter Incoming Queries](https://www.mongodb.com/docs/atlas/app-services/rules/filters/) — filter patterns for performance
7. [Define & Enforce a Schema](https://www.mongodb.com/docs/atlas/app-services/schemas/enforce-a-schema/) — App Services schema validation
8. [Data API and HTTPS Endpoints Deprecation](https://www.mongodb.com/docs/atlas/app-services/data-api/data-api-deprecation/) — EOL notice and migration paths
9. [MongoDB Atlas App Services CLI](https://www.mongodb.com/docs/atlas/app-services/cli/) — appservices push/pull/secrets
10. [Atlas Device Sync EOL Forum Post](https://www.mongodb.com/community/forums/t/atlas-device-sync-end-of-life-and-deprecation/296687) — Device Sync deprecation announcement
11. [Data API EOL Forum Post](https://www.mongodb.com/community/forums/t/mongodb-atlas-data-api-and-custom-https-endpoints-end-of-life-and-deprecation/296686) — Data API deprecation announcement
12. [Values and Secrets](https://www.mongodb.com/docs/atlas/app-services/values-and-secrets/) — Value/Secret access patterns
