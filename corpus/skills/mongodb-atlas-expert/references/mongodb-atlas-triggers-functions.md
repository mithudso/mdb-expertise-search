<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-triggers-functions` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-triggers-functions
title: MongoDB Atlas Triggers and Functions
version: 1.1.0
updated: "2026-05-29"
category: mongodb
tags: [mongodb, atlas, triggers, functions, serverless, change-streams, app-services, scheduled, cron, webhook, cdc, realm, etl]
description: >
  Expert reference for MongoDB Atlas Triggers (database, scheduled, authentication) and
  Atlas Functions (V8 JavaScript runtime, context object, npm dependencies, secrets,
  HTTPS Endpoints). Covers trigger types, change-event structure, match expressions,
  error handling and retry behavior, suspended state recovery, cost model, App Services
  CLI deployment, migration from Realm services, and production patterns (CDC, ETL,
  webhook handler, fanout/denormalization).

  TRIGGER: user asks about Atlas Triggers, Atlas Functions, App Services serverless
  execution, database trigger on insert/update/delete, scheduled trigger cron jobs,
  authentication triggers, HTTPS Endpoints, trigger error handling or suspension,
  migrating from Realm webhooks/services, App Services CLI, or function cost/limits.

  SKIP: change stream consumption in application code outside Atlas App Services
  (use mongodb-change-streams); Atlas Stream Processing pipelines (use
  mongodb-atlas-stream-processing); full App Services auth/rules/schema (use
  mongodb-atlas-app-services); Kafka CDC pipelines (use mongodb-kafka-connector).

whenToUse:
  - "How do I run code when a document is inserted into MongoDB?"
  - "Set up an Atlas database trigger on order inserts"
  - "How do I write a scheduled cron job in Atlas?"
  - "Trigger keeps suspending — how do I fix it?"
  - "Atlas Function error handling and retry behavior"
  - "Migrating Realm webhooks to HTTPS Endpoints"
  - "How do I call an external API from an Atlas Function?"
  - "What is the Atlas Function free tier and cost model?"
  - "Authentication trigger for post-login user enrichment"
  - "How do I use context.services to query MongoDB from a function?"
  - "CDC pattern from MongoDB Atlas to Elasticsearch via triggers"
  - "Atlas Functions hit 180-second limit — how do I restructure?"

whenNotToUse:
  - User is consuming change streams directly in Node.js/Python/Go/Java app — use mongodb-change-streams
  - User needs Atlas Stream Processing (windowing, Kafka emit, $source stage) — use mongodb-atlas-stream-processing
  - User needs App Services auth providers, Rules engine, Schema validation, or Device Sync — use mongodb-atlas-app-services
  - User is building a Kafka CDC pipeline from MongoDB — use mongodb-kafka-connector
  - User needs the full change-stream API (resume tokens, pre/post images, sharded cluster behavior) — use mongodb-change-streams

related_skills:
  - mongodb-change-streams
  - mongodb-atlas-app-services
  - mongodb-atlas-stream-processing
  - mongodb-kafka-connector
  - mongodb-cdc-architecture
  - mongodb-schema-design
---

# MongoDB Atlas Triggers and Functions

## Overview

Atlas Triggers and Atlas Functions are MongoDB Atlas's serverless execution layer. Triggers respond to events (database changes, schedules, auth events) and invoke Functions — JavaScript code running in a managed, sandboxed V8-based environment. Together they enable event-driven patterns, ETL pipelines, webhook handlers, and scheduled maintenance without provisioning or operating servers.

All triggers and functions are configured per **Atlas App Services application** (formerly Realm). An Atlas project can have multiple App Services apps, each with independent triggers, functions, secrets, and endpoints. Apps are deployed via the Atlas UI, the `appservices` CLI, or GitHub-backed automatic deployment.

| Limit | Value |
|---|---|
| Max function execution time | 180 seconds |
| Max function heap memory | ~256 MB |
| Max HTTPS endpoint response size | 4 MB |
| Max npm dependency bundle size | 200 MB (uncompressed) |

---

## Atlas Triggers — Overview

Three trigger types exist:

| Type | Event source | Typical use |
|---|---|---|
| Database | MongoDB change stream | React to insert/update/delete/replace |
| Scheduled | Internal cron scheduler | Periodic batch jobs, cleanups |
| Authentication | App Services user lifecycle | Post-login enrichment, deletion cleanup |

All trigger types share these behaviors:
- Invoke exactly one Atlas Function per trigger firing.
- Fire asynchronously — the database operation that caused the trigger is not blocked.
- Are retried automatically on transient function failure (behavior varies by type — see Error Handling section).
- Appear in the Atlas UI under **App Services → Triggers**.
- A trigger must be linked to a function within the **same App Services app** — cross-app invocation is not supported.
- Triggers can be enabled or disabled per app environment (development vs. production).

---

## Database Triggers

### How They Work

Database triggers use MongoDB **change streams** under the hood. Atlas opens a change stream on the configured collection and watches for matching `operationType` events. When a matching document appears in the stream, Atlas invokes the linked function with the change event document as the argument.

The change event document structure mirrors the MongoDB change stream specification:
```js
{
  _id: { ... },                       // Resume token
  operationType: "insert",            // insert | update | delete | replace
  fullDocument: { ... },              // Present for insert/replace; optional for update
  fullDocumentBeforeChange: { ... },  // Requires pre-image capture enabled
  ns: { db: "mydb", coll: "orders" },
  documentKey: { _id: ObjectId("...") },
  updateDescription: {                // Only for update events
    updatedFields: { status: "shipped" },
    removedFields: [],
    truncatedArrays: []
  },
  clusterTime: Timestamp(...)
}
```

### Operation Types

- **insert** — New document created. `fullDocument` is always present.
- **update** — Fields modified via `$set`, `$unset`, `$push`, etc. `fullDocument` is `null` by default unless "Full Document" is enabled in trigger settings.
- **delete** — Document removed. `fullDocument` is absent; only `documentKey` is present.
- **replace** — Entire document replaced (e.g., via `replaceOne()`). `fullDocument` is always present.

Enable **Full Document** mode (trigger setting) to receive the complete document state for update events. This issues an additional `findOne` read, adding latency and counting as a read operation against your Atlas cluster.

Enable **Full Document Before Change** (pre-image) if you need the document state prior to the operation. Requires `changeStreamPreAndPostImages` to be enabled on the collection at the MongoDB level.

### Event Ordering

Database triggers process change stream events in order within a single trigger, but **ordering is not guaranteed across multiple trigger invocations** if Atlas invokes them concurrently. For strict ordering requirements:
- Design functions to be idempotent.
- Use the `clusterTime` field in the change event to detect out-of-order processing.
- Consider a single-consumer queue pattern: write change events to a staging collection and process sequentially from a scheduled trigger.

### Match Filters

Triggers support a **Match Expression** (a MongoDB query filter) and a **Project Expression** (field projection) applied to the change event. These are evaluated **before** the function is invoked, meaning filtered-out events never count as function invocations and do not incur request charges.

```js
// Match expression: only trigger on orders with status "paid"
{
  "fullDocument.status": "paid",
  "operationType": { "$in": ["insert", "update"] }
}
```

```js
// Project expression: only include relevant fields
{
  "fullDocument.orderId": 1,
  "fullDocument.total": 1,
  "operationType": 1,
  "documentKey": 1
}
```

### Cluster Configuration

- A trigger targets a specific **linked cluster** (data source) within the Atlas project.
- The trigger must specify **database** and **collection**.
- Serverless clusters (Atlas Serverless instances) support database triggers.
- Multi-region clusters: triggers read from a single change stream — no per-region fan-out.

### Function Signature for Database Triggers

```js
// Atlas Function invoked by a database trigger
exports = async function(changeEvent) {
  const { operationType, fullDocument, documentKey, ns } = changeEvent;

  if (operationType === "insert") {
    console.log(`New document in ${ns.db}.${ns.coll}:`, documentKey._id);
    // ... processing logic
  }
};
```

---

## Scheduled Triggers

### Cron Expressions

Scheduled triggers fire on a **cron schedule**. Atlas uses standard 5-field cron syntax:

```
┌───────── minute (0–59)
│ ┌─────── hour (0–23)
│ │ ┌───── day of month (1–31)
│ │ │ ┌─── month (1–12 or JAN–DEC)
│ │ │ │ ┌─ day of week (0–7 or SUN–SAT; 0 and 7 = Sunday)
│ │ │ │ │
* * * * *
```

Examples:
```
0 9 * * 1-5       Every weekday at 09:00
0 0 1 * *         First day of every month at midnight
*/15 * * * *      Every 15 minutes
0 2 * * 0         Every Sunday at 02:00
```

### Time Zones

The cron schedule runs in **UTC by default**. You can configure an IANA time zone identifier in the trigger settings (e.g., `America/New_York`, `Europe/London`).

Note: Daylight saving time transitions can cause a scheduled trigger to skip or double-fire once per year if scheduled near the DST boundary hour. For critical jobs, schedule outside DST boundaries or use UTC.

### Max Runtime and Retry Behavior

Atlas Functions have a **maximum execution time of 180 seconds** (3 minutes). If a scheduled trigger's function exceeds this limit or throws an unhandled exception, Atlas logs the error but **does not retry** — it simply skips that scheduled interval. The next scheduled firing proceeds normally regardless of prior failures. Monitor the App Services Logs for failures; set up Atlas Alerts on `TRIGGER_FAILURE` events.

### Function Signature for Scheduled Triggers

```js
// Scheduled trigger function — receives no arguments
exports = async function() {
  const today = new Date();
  const cutoff = new Date(today - 30 * 24 * 60 * 60 * 1000); // 30 days ago

  const db = context.services.get("mongodb-atlas").db("myapp");
  const result = await db.collection("sessions").deleteMany({
    lastSeen: { $lt: cutoff }
  });

  console.log(`Cleaned up ${result.deletedCount} expired sessions`);
};
```

---

## Authentication Triggers

### Event Types

Authentication triggers fire on App Services authentication lifecycle events:

| Event | When it fires |
|---|---|
| `LOGIN` | A user successfully authenticates |
| `CREATE` | A new user account is created |
| `DELETE` | A user account is deleted |

The trigger receives an `authEvent` object:
```js
{
  operationType: "LOGIN",  // LOGIN | CREATE | DELETE
  providers: ["local-userpass"],
  user: {
    id: "6478aab...",
    type: "normal",
    data: {
      // Provider-specific: "email" for local-userpass and Google OAuth;
      // field names vary by auth provider
      email: "user@example.com",
      name: "Jane Doe"
    },
    custom_data: { ... },
    identities: [ ... ]
  },
  time: ISODate("2025-01-15T10:30:00Z")
}
```

Authentication triggers are **best-effort**: they get one automatic retry on failure. If both attempts fail, the event is **permanently dropped** — there is no suspension state and no replay mechanism. This makes auth triggers unsuitable as the sole path for compliance-critical operations (e.g., mandatory audit logging of every login). For audit requirements, write the auth event to a MongoDB collection inside the function body; if the write fails, the retry covers it, but a second failure means the record is lost. Supplement with Atlas Database Auditing for guaranteed coverage.

### Integration Patterns

**Post-login enrichment** — Sync user metadata into a MongoDB collection on each login:
```js
exports = async function(authEvent) {
  if (authEvent.operationType !== "LOGIN") return;
  const db = context.services.get("mongodb-atlas").db("myapp");
  await db.collection("users").updateOne(
    { userId: authEvent.user.id },
    { $set: { lastLogin: new Date(), email: authEvent.user.data.email } },
    { upsert: true }
  );
};
```

**User creation provisioning** — Create a default profile document on account creation:
```js
exports = async function(authEvent) {
  if (authEvent.operationType !== "CREATE") return;
  const db = context.services.get("mongodb-atlas").db("myapp");
  await db.collection("profiles").insertOne({
    userId: authEvent.user.id,
    email: authEvent.user.data.email,
    createdAt: new Date(),
    tier: "free"
  });
};
```

**User deletion cleanup** — Remove PII and linked documents on account deletion:
```js
exports = async function(authEvent) {
  if (authEvent.operationType !== "DELETE") return;
  const db = context.services.get("mongodb-atlas").db("myapp");
  const uid = authEvent.user.id;
  await Promise.all([
    db.collection("profiles").deleteOne({ userId: uid }),
    db.collection("preferences").deleteOne({ userId: uid }),
    db.collection("sessions").deleteMany({ userId: uid }),
  ]);
};
```

---

## Atlas Functions

### JavaScript Runtime

Atlas Functions run in a **sandboxed V8-based JavaScript environment**. Key characteristics:

- **No persistent state** between invocations — each function call is isolated.
- **No file system access** — `fs` module is not available.
- **No native add-ons** — pure-JS npm dependencies only.
- **Top-level `exports`** — use `exports = function(...) { ... }` or `exports = async function(...) { ... }`. Do not use ES module `export` syntax.
- **Max execution time**: 180 seconds.
- **Max heap memory**: ~256 MB.
- **Max HTTPS endpoint response size**: 4 MB.
- **`require()` available** for built-in Node.js modules and imported npm packages; not for arbitrary file paths.

### Built-in Modules Available

```js
const crypto      = require("crypto");
const util        = require("util");
const url         = require("url");
const querystring = require("querystring");
const buffer      = require("buffer");
const stream      = require("stream");
const zlib        = require("zlib");
const net         = require("net");    // limited — no server-side listen
const http        = require("http");   // outbound only
const https       = require("https");  // outbound only
```

### External Dependencies (npm)

Add npm packages in the App Services UI under **Functions → Dependencies** or via the App Services CLI by editing `package.json` in your app's configuration directory. Atlas bundles dependencies at deploy time. Only pure-JS packages work (no native add-ons).

```json
// package.json in your app directory
{
  "dependencies": {
    "axios": "^1.6.0",
    "lodash": "^4.17.21",
    "uuid": "^9.0.0"
  }
}
```

Use in functions:
```js
const axios = require("axios");
const { v4: uuidv4 } = require("uuid");
```

### Secrets

Store sensitive values (API keys, tokens) as **App Services Secrets** — not as plain Values and never in function source code. Access them via `context.values.get()`:

```js
// Secret named "STRIPE_SECRET_KEY" defined in App Services UI or appservices CLI
const stripeKey = context.values.get("STRIPE_SECRET_KEY");
```

Secrets are encrypted at rest and **never appear in function logs**. Plain Values (non-secret config such as environment URLs) use the same `context.values.get()` API but are stored in plaintext.

### The `context` Object

Every function receives a global `context` object with these namespaces:

```js
// MongoDB data source access
const collection = context.services
  .get("mongodb-atlas")     // linked data source name (as configured in App Services)
  .db("mydb")
  .collection("orders");

// Secrets and plain config values
const apiKey = context.values.get("MY_SECRET");

// HTTP client for outbound requests
// context.http is the built-in HTTP utility — it replaced the old
// "Realm HTTP Service" (context.services.get("http")) which is now removed.
const response = await context.http.get({
  url: "https://api.example.com/data",
  headers: { "Authorization": [`Bearer ${apiKey}`] }
});

// Authenticated user (available in HTTPS endpoint or client SDK context; null in triggers)
const userId = context.user?.id;
const email = context.user?.data?.email;

// Current function name
const funcName = context.functionName;

// Environment tag (e.g., "development", "production")
const env = context.environment.tag;
const envValues = context.environment.values; // per-environment values map

// Call another function in the same app
const result = await context.functions.execute("myHelperFunction", arg1, arg2);
```

**Note on `context.http`:** This is the built-in outbound HTTP client provided by App Services. It is distinct from Node's `require("http")` (which is also available for lower-level use). The App Services `context.http` client handles SSL automatically and is the recommended approach for outbound API calls.

---

## Function Invocation

### From Triggers

Triggers invoke functions automatically. The trigger passes its event document as the sole argument to the function. No explicit invocation code is required.

### From HTTPS Endpoints

HTTPS endpoints (see HTTPS Endpoints section) invoke a linked function when the endpoint URL receives an HTTP request. The function receives a synthesized `request` object containing `query`, `headers`, `body`, and `httpMethod`.

### From Another Function

Functions can call other functions within the same app via `context.functions.execute()`:

```js
// caller.js
exports = async function(userId) {
  const profile = await context.functions.execute("getUserProfile", userId);
  const enriched = await context.functions.execute("enrichProfile", profile);
  return enriched;
};

// getUserProfile.js
exports = async function(userId) {
  const db = context.services.get("mongodb-atlas").db("myapp");
  return db.collection("profiles").findOne({ userId });
};
```

Function-to-function calls are awaitable from the caller's perspective. Each called function runs in its own isolated V8 context. The total call chain must complete within the 180-second limit of the outermost function.

### From Atlas Device SDK (Client-side)

Mobile and web apps using the Atlas Device SDK can call functions directly when the user is authenticated:
```js
// Atlas Web SDK
const result = await app.currentUser.callFunction("calculateDiscount", [orderId]);
```

---

## HTTPS Endpoints

### What They Are

HTTPS Endpoints expose Atlas Functions as HTTP APIs without requiring a custom backend server. Each endpoint has a unique URL, an HTTP method (GET, POST, PUT, PATCH, DELETE), and links to one Atlas Function.

Format: `https://<region>.data.mongodb-api.com/app/<appId>/endpoint/<path>`

### Authentication Options

| Auth method | When to use |
|---|---|
| No authentication | Public webhooks where the caller verifies a payload secret inside the function |
| Application authentication | Logged-in Device SDK users — JWT passed in `Authorization` header |
| System authentication | Server-to-server; function runs with full system privileges, bypassing Rules |
| API key | Machine-to-machine auth; pass as `apiKey` query param or `Authorization: apiKey <key>` header |

For webhook verification (e.g., Stripe, GitHub), use **No Authentication** and validate the HMAC signature inside the function body:

```js
exports = async function({ headers, body }) {
  const signature = headers["Stripe-Signature"]?.[0];
  const rawBody = body.text();
  const secret = context.values.get("STRIPE_WEBHOOK_SECRET");
  // Validate HMAC-SHA256 signature before processing
};
```

### CORS

Configure allowed origins in the endpoint settings. The App Services runtime handles preflight `OPTIONS` requests automatically when CORS is enabled. Wildcard `*` is permitted but not recommended for endpoints handling mutations.

### Function Signature and Response Formatting

```js
exports = async function(request) {
  const { query, headers, body, httpMethod } = request;

  // Parse JSON body
  const payload = JSON.parse(body.text());

  // Return a Response object
  return {
    statusCode: 200,
    headers: { "Content-Type": ["application/json"] },  // header values are arrays
    body: JSON.stringify({ success: true, id: payload.id })
  };
};
```

`statusCode` defaults to 200 if omitted. `headers` values must be arrays of strings. `body` must be a string.

### Additional Request Context

Inside an HTTPS endpoint function, `context.request` provides server-side metadata:

```js
exports = async function(request) {
  const ip      = context.request.remoteIPAddress;   // caller's IP
  const rawQS   = context.request.rawQueryString;    // "foo=1&bar=2"
  const reqHdrs = context.request.requestHeaders;    // { "X-My-Header": ["value"] }
  // context.request differs from the "request" function argument:
  // - "request" arg: { query, headers, body, httpMethod } — payload
  // - context.request: runtime metadata (IP, raw query string, headers mirror)
};
```

### Rules and System User Context

Atlas Functions invoked by triggers always run as the **system user**, which bypasses all App Services Data Access Rules. HTTPS Endpoints can be configured to run as system user (full access) or as the authenticated user (Rules enforced). When building HTTPS Endpoints that accept user JWTs, set the auth mode to **Application Authentication** — the function then runs under that user's identity and Rules are applied automatically.

```js
// In an Application-auth endpoint, context.user is populated:
exports = async function(request) {
  // This query automatically respects the user's Data Access Rules
  const db = context.services.get("mongodb-atlas").db("myapp");
  const docs = await db.collection("orders")
    .find({ userId: context.user.id })
    .toArray();
  return { statusCode: 200, body: JSON.stringify(docs) };
};
```

### Data API vs. Custom HTTPS Endpoints

Atlas also provides a **Data API** (separate feature) for generic CRUD over HTTP without writing function code. Custom HTTPS Endpoints are for business logic. The two have different URL patterns (`/action/` vs. `/endpoint/`) and different auth models — do not conflate them.

---

## Trigger Error Handling

### Retry Behavior

| Trigger type | Retry behavior on failure |
|---|---|
| Database | Retried with exponential backoff; suspended after consecutive failures |
| Scheduled | No retry — the interval is skipped; next scheduled firing runs normally |
| Authentication | One retry; if both fail, the event is dropped |

### Suspended State (Database Triggers)

A database trigger enters **suspended** state after exhausting its retry attempts. In suspended state:

- The change stream resume token is held but not advancing.
- No new events are processed until the trigger is manually re-enabled.
- When re-enabled, the trigger resumes from the last failed event using the resume token.
- **Critical:** If the resume token expires (change stream history purged, typically after the oplog window — which can be a few hours on busy clusters), re-enabling the trigger causes it to start from **now**, permanently losing the events in the gap.

**Operational must-do:** Configure Atlas Alerts for `TRIGGER_FAILURE` and `TRIGGER_AUTO_RESUMED` events to catch suspensions before the resume token expires.

### Error Logs

Function execution errors appear in:
- **App Services UI → Logs** — searchable and filterable by function name, status, and date range.
- **App Services Admin API** — `/api/admin/v3.0/groups/{groupId}/apps/{appId}/logs` for programmatic access.
- **Log Forwarder** — stream logs to Atlas (a capped collection), S3, or a custom HTTPS endpoint for external observability pipelines.

Log entries include: timestamp, function name, execution duration, error message, and stack trace.

---

## App Services CLI and Deployment

Teams managing App Services in production should use the Atlas CLI (`atlas appservices` subcommands) or GitHub-backed deployment rather than manual UI edits.

### CLI Workflow

```bash
# Install Atlas CLI (recommended — bundles the appservices subcommand)
brew install mongodb/brew/mongodb-atlas-cli
# or: https://www.mongodb.com/docs/atlas/cli/stable/install-atlas-cli/

# Authenticate
atlas auth login
# or with API keys:
atlas config set public_api_key <key>
atlas config set private_api_key <privateKey>

# Pull current app config to local directory
atlas appservices pull --remote <appId>

# Push local changes to Atlas
atlas appservices push --remote <appId>
```

> **Legacy CLI note:** The standalone `realm-cli` (npm: `mongodb-realm-cli`) and `appservices` commands still work but are no longer the recommended install path. Prefer `atlas appservices` for new setups.

### Config Directory Structure

```
my-app/
  app.json                  # App metadata (app ID, name, cluster links, etc.)
  functions/
    getUserProfile/
      config.json           # Function config (runtime, can_evaluate rules)
      source.js             # Function source code
  triggers/
    onOrderInsert/
      config.json           # Trigger config (collection, op types, match filter)
  values/
    ELASTICSEARCH_URL.json  # Plain config values
  secrets.json              # Secret names only (not values — values stay in Atlas)
  environments/
    development.json
    production.json
```

### GitHub Automatic Deployment

Link an App Services app to a GitHub repository branch in the App Services UI under **Deployment**. Every push to the configured branch triggers an automatic deploy. This enables PR-based review workflows for trigger and function changes.

---

## Migration from Realm / App Services

### History

MongoDB Realm was rebranded as **Atlas App Services** in 2022. The underlying platform is the same; "Realm" now refers only to the client-side Device SDK (Atlas Device SDK).

### What Was Deprecated or Changed

| Old term / feature | Current state |
|---|---|
| Realm Functions | Atlas Functions — same capability, renamed |
| Realm Triggers | Atlas Triggers — same capability, renamed |
| Realm HTTP Services (`context.services.get("http")`) | **Removed.** Use the built-in `context.http` object instead |
| Realm 3rd-party services (Twilio, AWS, GitHub built-ins) | **Removed.** Use Atlas Functions + npm packages + `context.http` directly |
| Webhooks (incoming) | Replaced by **HTTPS Endpoints** |
| GraphQL API (Realm GraphQL) | **Deprecated** as of 2025. Migrate to custom HTTPS Endpoints or Atlas Data API |
| Sync (Device Sync / Atlas Device Sync) | Still active; independent of triggers/functions |

### Migration Paths

**From Realm Webhooks to HTTPS Endpoints:**
1. Create an HTTPS Endpoint with the same HTTP method.
2. Move the function code — the `request` object structure is nearly identical.
3. Update callers to the new endpoint URL.

**From Realm 3rd-party services to npm + `context.http`:**
```js
// Old Realm Twilio service (REMOVED — will throw at runtime)
const twilio = context.services.get("twilio");
twilio.send({ to: "+15551234567", from: "+15559876543", body: "Hello" });

// New: use twilio npm package (add "twilio" to dependencies in package.json)
const twilio = require("twilio");
const client = twilio(
  context.values.get("TWILIO_ACCOUNT_SID"),
  context.values.get("TWILIO_AUTH_TOKEN")
);
await client.messages.create({ to: "+15551234567", from: "+15559876543", body: "Hello" });
```

**From Realm HTTP Services to `context.http`:**
```js
// Old (removed): context.services.get("http").get({ url: "..." })
// New — same API shape, different namespace:
const response = await context.http.get({ url: "https://api.example.com/data" });
const body = EJSON.parse(response.body.text());
```

**From Realm GraphQL to Data API / HTTPS Endpoints:**
- For simple CRUD, switch to the Atlas Data API (REST-based, no code required).
- For complex queries or mutations, write custom HTTPS Endpoints backed by Atlas Functions.

---

## Cost Model

Atlas Triggers and Functions pricing is based on **Atlas App Services usage**, billed separately from Atlas cluster compute and storage.

### Free Tier (as of 2025 — verify at mongodb.com/pricing)

| Resource | Free allowance |
|---|---|
| Requests | 1,000,000 / month |
| Compute time | 500 hours / month |
| Sync data transfer | 10 GB / month (Device Sync only) |

Each function invocation (from trigger, HTTPS endpoint, or Device SDK call) counts as one request. Match expressions on database triggers filter events **before** invocation, so filtered-out change events do not count as requests.

### Paid Usage

| Resource | Approximate cost (verify current rates) |
|---|---|
| Requests | ~$2.00 per 1,000,000 beyond free tier |
| Compute time | ~$10.00 per 500 hours beyond free tier |
| Outbound data | Standard Atlas egress rates |

### Cost Optimization Tips

- **Use match expressions** on database triggers — they filter at the change stream level before the function is invoked, avoiding request charges for irrelevant events.
- **Batch in scheduled triggers** — one trigger processing 1,000 documents costs 1 request; 1,000 per-document triggers cost 1,000 requests.
- **Disable Full Document on update triggers** unless you need it — the extra `findOne` adds compute time and a cluster read.
- **Keep functions short** — compute time is wall-clock billed; sleeping, polling, or making slow outbound HTTP calls multiplies cost.
- **Monitor the App Services Usage dashboard** in the Atlas UI for request and compute consumption per app.

---

## Common Patterns

### Change Data Capture (CDC)

Mirror changes from MongoDB to an external system (Elasticsearch, data warehouse, analytics platform):

```js
// Database trigger on "products" collection, all operation types
exports = async function(changeEvent) {
  const { operationType, fullDocument, documentKey } = changeEvent;
  const esUrl = context.values.get("ELASTICSEARCH_URL");
  const apiKey = context.values.get("ELASTICSEARCH_API_KEY");

  if (operationType === "delete") {
    await context.http.delete({
      url: `${esUrl}/products/_doc/${documentKey._id}`,
      headers: { "Authorization": [`ApiKey ${apiKey}`] }
    });
    return;
  }

  // insert, update (with Full Document enabled), or replace
  await context.http.put({
    url: `${esUrl}/products/_doc/${fullDocument._id}`,
    headers: {
      "Authorization": [`ApiKey ${apiKey}`],
      "Content-Type": ["application/json"]
    },
    body: JSON.stringify(fullDocument)
  });
};
```

### ETL Pipeline

Transform and load data from a raw collection to a curated collection on each insert:

```js
exports = async function(changeEvent) {
  if (changeEvent.operationType !== "insert") return;
  const raw = changeEvent.fullDocument;
  const db = context.services.get("mongodb-atlas").db("warehouse");

  const curated = {
    _id: raw._id,
    userId: raw.user_id,
    eventType: raw.event_type.toLowerCase(),
    timestampMs: new Date(raw.ts).getTime(),
    properties: raw.props ?? {},
    ingestedAt: new Date()
  };

  await db.collection("events_curated").insertOne(curated);
};
```

### Webhook Handler (Stripe)

```js
exports = async function({ headers, body }) {
  const crypto = require("crypto");
  const rawBody = body.text();
  const sigHeader = headers["Stripe-Signature"]?.[0] ?? "";
  const secret = context.values.get("STRIPE_WEBHOOK_SECRET");

  // Parse Stripe signature header: t=<timestamp>,v1=<signature>
  const parts = {};
  for (const part of sigHeader.split(",")) {
    const idx = part.indexOf("=");
    if (idx > 0) parts[part.slice(0, idx)] = part.slice(idx + 1);
  }
  const { t: timestamp, v1: receivedSig } = parts;

  const expected = crypto
    .createHmac("sha256", secret)
    .update(`${timestamp}.${rawBody}`)
    .digest("hex");

  if (!timestamp || expected !== receivedSig) {
    return { statusCode: 400, body: JSON.stringify({ error: "Invalid signature" }) };
  }

  const event = JSON.parse(rawBody);
  const db = context.services.get("mongodb-atlas").db("billing");

  if (event.type === "invoice.paid") {
    await db.collection("invoices").updateOne(
      { stripeInvoiceId: event.data.object.id },
      { $set: { status: "paid", paidAt: new Date() } }
    );
  }

  return { statusCode: 200, body: JSON.stringify({ received: true }) };
};
```

### Scheduled Cleanup

```js
// Runs nightly at 02:00 UTC — cron: "0 2 * * *"
exports = async function() {
  const db = context.services.get("mongodb-atlas").db("myapp");
  const cutoff = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000); // 90 days ago

  const [sessions, notifications, auditLogs] = await Promise.all([
    db.collection("sessions").deleteMany({ expiresAt: { $lt: cutoff } }),
    db.collection("notifications").deleteMany({ readAt: { $lt: cutoff } }),
    db.collection("audit_logs").deleteMany({ createdAt: { $lt: cutoff }, archived: true }),
  ]);

  console.log(JSON.stringify({
    sessionsDeleted: sessions.deletedCount,
    notificationsDeleted: notifications.deletedCount,
    auditLogsDeleted: auditLogs.deletedCount
  }));
};
```

### Fanout / Denormalization on Write

When an author's name changes, propagate to all their posts:

```js
// Trigger on "authors" collection, update only, match filter: { "updateDescription.updatedFields.name": { $exists: true } }
exports = async function(changeEvent) {
  if (changeEvent.operationType !== "update") return;
  const { updatedFields } = changeEvent.updateDescription;
  if (!updatedFields.name) return;

  const db = context.services.get("mongodb-atlas").db("blog");
  const authorId = changeEvent.documentKey._id;

  await db.collection("posts").updateMany(
    { "author._id": authorId },
    { $set: { "author.name": updatedFields.name } }
  );
};
```

---

## Anti-Patterns

### Long-Running Functions

**Problem:** A function that loops over millions of documents, calls an external API for each, and takes > 3 minutes will be killed mid-execution, leaving data in a partially-processed state with no automatic recovery.

**Fix:** Process in bounded batches. Use a scheduled trigger to paginate with a cursor stored in a MongoDB "job state" document. Each invocation processes one page and updates the cursor for the next run.

### Unbounded Data Fetches

**Problem:** `collection.find({}).toArray()` on a large collection loads all documents into function heap memory (~256 MB limit).

**Fix:** Always apply `limit()` and cursor-based pagination. Use `$limit` in aggregation pipelines. Write large result sets to a staging collection rather than holding them in memory.

```js
// BAD — loads entire collection into memory
const all = await collection.find({}).toArray();

// GOOD — bounded page with filter to track progress
const page = await collection.find({ processedAt: { $exists: false } })
  .limit(500)
  .toArray();
```

### Missing Error Handling

**Problem:** An unhandled exception in a database trigger causes a retry loop and eventually suspension, losing the change stream resume position.

**Fix:** Wrap the function body in `try/catch`. Log the error. Consciously decide whether to re-throw (Atlas retries, eventually suspends — use for must-not-lose events) or swallow (skips this event — use for tolerable data loss scenarios):

```js
exports = async function(changeEvent) {
  try {
    await processEvent(changeEvent);
  } catch (err) {
    console.error(
      "Failed to process event:",
      err.message,
      JSON.stringify(changeEvent.documentKey)
    );
    // Swallow: tolerable to skip this event (e.g., analytics fanout)
    // Re-throw: event must be processed (e.g., billing record)
  }
};
```

### Trigger Loops

**Problem:** A database trigger writes to the same collection it is watching, causing an infinite chain of trigger firings.

**Fix:** Write to a different collection. If you must write back to the same collection, set a marker field in the written document and add a match expression on the trigger to exclude documents that already carry the marker.

### Secrets in Function Code

**Problem:** Hard-coding API keys or credentials in function source code. App Services stores function source in configuration metadata that can be exported or leaked.

**Fix:** Always use `context.values.get("SECRET_NAME")` for sensitive values. Declare them as App Services Secrets (encrypted). Never store sensitive values as plain Values or in source code.

### Ignoring the Free Tier Ceiling

**Problem:** A database trigger on a high-write collection (millions of writes per day) quickly exhausts the free tier and generates unexpected charges.

**Fix:** Estimate invocation count before enabling: `(writes/day) × (% matching filter) × 30 days`. Use match expressions to minimize unnecessary invocations. Consider replacing per-document triggers with a scheduled trigger that polls for unprocessed documents in batches.

---

## Reference Links

- Atlas App Services: https://www.mongodb.com/docs/atlas/app-services/
- Atlas Triggers: https://www.mongodb.com/docs/atlas/app-services/triggers/
- Atlas Functions: https://www.mongodb.com/docs/atlas/app-services/functions/
- HTTPS Endpoints: https://www.mongodb.com/docs/atlas/app-services/data-api/custom-endpoints/
- App Services CLI: https://www.mongodb.com/docs/atlas/app-services/cli/
- GitHub Deployment: https://www.mongodb.com/docs/atlas/app-services/deploy/automated-deployment/
- Atlas Pricing: https://www.mongodb.com/pricing

## See Also: Atlas App Services EOL and HTTP Access Replacements
The Atlas Data API and Custom HTTPS Endpoints (part of App Services) were removed September 30, 2025. **Atlas Triggers remain available.** For HTTP CRUD access patterns that replace the Data API, use the MongoDB driver directly from Express, FastAPI, or a Lambda function — the `mongodb-developer` skill covers Node.js/Python driver patterns, and `mongodb-atlas-app-services` covers the remaining App Services surface.

## See Also: Full App Services Platform Reference
The `mongodb-atlas-app-services` skill covers the complementary App Services surface that this skill does not: Authentication providers (email/password, API keys, JWT, OAuth2), Rules and Permissions engine (document-level and field-level access), Schema Validation as a service, Values/Secrets management, the App Services billing model, and migration paths from deprecated features (GraphQL API, Data API, Device Sync — all EOL September 30, 2025).
