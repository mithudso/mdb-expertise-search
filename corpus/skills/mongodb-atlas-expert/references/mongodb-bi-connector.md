<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-bi-connector` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-bi-connector
category: mongodb
version: "1.1.0"
updated: "2026-05-29"
description: >
  MongoDB BI Connector and Atlas SQL Interface expert — SQL-based BI tool integration (Tableau, Power BI,
  Excel, Looker, MicroStrategy) with MongoDB, including legacy BI Connector (mongosqld, DRDL schema files,
  ODBC/JDBC setup, SCRAM/LDAP/Kerberos auth, EOL Sept 2026) and the current Atlas SQL Interface (MongoSQL,
  certified Power BI and Tableau connectors, dynamic schema, Atlas Data Federation backing).
  Also covers the removed Atlas Data API (shut down Sept 30, 2025) and replacement HTTP CRUD patterns via
  MongoDB drivers with Express, FastAPI, Lambda, Delbridge, and RESTHeart.
  TRIGGER: "connect Tableau to MongoDB", "Power BI MongoDB", "SQL queries on Atlas", "ODBC driver MongoDB",
  "REST API for MongoDB", "Data API deprecated", "mongosqld auth error", "schema not showing in Tableau",
  "BI Connector LDAP", "migrate from BI Connector", "Atlas SQL Interface", "MongoSQL".
  SKIP: Atlas Charts native visualization (use mongodb-atlas-charts), Kafka-based data pipelines
  (use mongodb-kafka-connector), general Atlas cluster administration (use mongodb-atlas-expert).
tags:
  - mongodb
  - bi
  - sql
  - atlas
  - odbc
  - jdbc
  - rest-api
  - deprecated
whenToUse:
  - "User is connecting Tableau, Power BI, Excel, Looker, or any BI tool to MongoDB"
  - "User is setting up or troubleshooting MongoDB BI Connector (mongosqld)"
  - "User asks about ODBC or JDBC drivers for MongoDB"
  - "User asks about SQL queries against MongoDB"
  - "User is planning migration from BI Connector to Atlas SQL Interface before September 2026"
  - "User asks about Atlas SQL Interface or MongoSQL"
  - "User asks about Atlas Data API (to explain it was removed Sept 30, 2025)"
  - "User is migrating from Atlas Data API to a replacement HTTP pattern"
  - "User asks about Custom HTTPS Endpoints or Atlas App Services HTTP features"
  - "User needs HTTP/REST access to MongoDB without a persistent driver connection"
  - "User asks about Atlas GraphQL API (to explain it was removed)"
  - "User is evaluating Hasura, RESTHeart, or Delbridge as MongoDB HTTP API alternatives"
  - "User asks about DRDL files or schema sampling for BI tools"
  - "User asks about LDAP, SCRAM, or Kerberos authentication for SQL/BI access"
whenNotToUse:
  - "Atlas Charts built-in visualization — use mongodb-atlas-charts"
  - "Kafka-based data pipelines — use mongodb-kafka-connector"
  - "General Atlas cluster administration — use mongodb-atlas-expert"
  - "Spark/Databricks analytics pipelines — use mongodb-spark-connector"
related_skills:
  - mongodb-atlas-expert
  - mongodb-atlas-triggers-functions
  - mongodb-migration-patterns
  - mongodb-atlas-charts
  - api-design-patterns
  - mongodb-atlas-data-federation
---

# MongoDB BI Connector and Atlas SQL Interface

Expert reference for connecting BI tools (Tableau, Power BI, Excel, Looker) to MongoDB via SQL, and for HTTP-based data access patterns following the deprecation of the Atlas Data API.

## CRITICAL LIFECYCLE NOTICES (2025–2026)

| Component | Status | EOL Date |
|---|---|---|
| MongoDB Connector for BI (mongosqld) | **EOL** | September 2026 |
| Atlas Data API (App Services) | **Removed** | September 30, 2025 |
| Atlas GraphQL API (App Services) | **Removed** | September 30, 2025 |
| Atlas HTTPS Custom Endpoints (App Services) | **Removed** | September 30, 2025 |
| Atlas SQL Interface (MongoSQL) | **Current** | No EOL |

**For all new BI integrations: use the Atlas SQL Interface (MongoSQL), not the legacy BI Connector.**
**For HTTP CRUD access: use MongoDB Drivers + Express/FastAPI/Spring Boot or serverless (Lambda, Cloud Run), not the deprecated Data API.**

---

## Part 1: MongoDB BI Connector (Legacy — EOL Sept 2026)

### Overview

The MongoDB Connector for BI translates SQL queries from BI clients into MongoDB Query Language (MQL) and executes them against a `mongod` or `mongos` instance. Use this section only when supporting existing BI Connector deployments during migration to Atlas SQL Interface.

Sources: [MongoDB BI Connector Docs](https://www.mongodb.com/docs/bi-connector/current/), [Components Reference](https://www.mongodb.com/docs/bi-connector/current/components/), [FAQ](https://www.mongodb.com/docs/bi-connector/current/faq/)

### Architecture

```
[Tableau / Power BI / Excel / Looker]
         |
    [ODBC/JDBC Driver]
         |
    [mongosqld]  ← central proxy; SQL → aggregation pipeline (via internal mongotranslate)
         |      uses DRDL schema to map collections → relational tables
         |
    [mongod / mongos]
```

**Core Components:**
- `mongosqld` — listens on port 3307 (MySQL wire protocol), proxies SQL requests to MongoDB. Internally invokes `mongotranslate` for SQL→MQL translation. Always enables `allowDiskUse` for aggregation.
- `mongodrdl` — generates DRDL schema files from collection sampling; run once to produce initial schema.
- `mongotranslate` — standalone CLI beta utility to translate SQL → aggregation pipeline without a running cluster (useful for debugging translation output).

**Version Note:** v2.0+ replaced the PostgreSQL Foreign Data Wrapper (FDW) with `mongosqld`. The `mongobiuser` and `mongobischema` helpers were removed in v2.0.

### Schema Management — DRDL Files

DRDL (Document Relational Definition Language) files define how MongoDB collections map to relational tables. Schema is sampled at startup by default; for production, generate and pin a DRDL file.

```bash
# Generate schema from a running cluster
mongodrdl --host localhost:27017 --db mydb --collection orders -o orders.drdl

# Load from DRDL file at mongosqld startup
mongosqld --schema orders.drdl --addr 0.0.0.0:3307
```

**Schema caching behavior:**
- Without `--schema`: mongosqld samples the collection at startup and caches in memory.
- With `--schema`: loads DRDL file on startup; use `--schemaRefreshIntervalSecs` for periodic refresh (only works with `--schema`).
- Schema 2.11+ change: schema management is stored in a dedicated MongoDB collection rather than in-memory only.

**DRDL Anti-Patterns:**
- Sampling from large heterogeneous collections produces poor schema (polymorphic documents confuse the sampler).
- Using MongoDB Views to normalize types before sampling is the recommended workaround.
- Arrays are sampled as separate virtual tables; deeply nested arrays multiply table count.

### Authentication

| Mechanism | Requires |
|---|---|
| SCRAM-SHA-1 (default) | MongoDB auth enabled |
| SCRAM-SHA-256 | MongoDB auth enabled |
| PLAIN (LDAP) | MongoDB Enterprise |
| GSSAPI (Kerberos) | MongoDB Enterprise |

**Note: X.509 is NOT supported by mongosqld.**

```yaml
# mongosqld config.yml — LDAP example
security:
  enabled: true
  defaultMechanism: "PLAIN"
  defaultSource: "$external"

mongodb:
  net:
    auth:
      mechanism: "PLAIN"
```

**Client username format for LDAP:** `grace?mechanism=PLAIN&source=$external`

TLS/SSL is strongly recommended — PLAIN sends passwords in cleartext without it.

### BI Tool Setup (BI Connector)

**Tableau (deprecated as of Tableau's own docs — prefer Atlas SQL Interface):**
1. Install MongoDB BI Connector ODBC Driver.
2. Create a System DSN pointing to `localhost:3307`.
3. In Tableau: Connect → MySQL → enter DSN credentials.

**Power BI:**
1. Install ODBC Driver (v1.2+ for DirectQuery mode).
2. Get Data → ODBC → select MongoDB DSN.
3. DirectQuery requires ODBC Driver 1.2+.

**Compatible tools:** Tableau, Power BI, MicroStrategy, Excel, MySQL Workbench, DBeaver, Looker (via MySQL connector).

### SQL-to-MQL Translation and Performance Limitations

**What translates well (pushdown to aggregation pipeline):**
- `SELECT`, `WHERE`, `GROUP BY`, `ORDER BY`, `LIMIT`, `OFFSET`
- `JOIN` (translated to `$lookup`)
- `LIKE` with literal patterns (pushed down as regex)
- Aggregate functions: `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`
- EXISTS subqueries (as `$lookup` + `$match`)

**What falls back to in-memory execution (no pushdown):**
- Complex SQL constructs with no direct MQL equivalent
- Certain window functions
- UNION / INTERSECT / EXCEPT
- Correlated subqueries
- Non-literal LIKE patterns

**Index usage:** BI Connector can use MongoDB indexes for `$match` predicates that are pushed down. Ensure compound indexes on fields used in WHERE clauses.

**Performance tuning:**
- Use MongoDB Views to pre-filter and normalize data before BI Connector schema sampling.
- Limit schema to required collections only (reduces startup time and memory).
- Use `--maxVarcharLength` to cap string column width and reduce memory.
- For Tableau extracts (not live queries), performance is better — schedule off-peak.

---

## Part 2: Atlas SQL Interface (MongoSQL) — Current Replacement

### Overview

The Atlas SQL Interface (MongoSQL) replaces the BI Connector with a modern SQL-over-ODBC/JDBC layer backed by Atlas Data Federation. No proxy process to manage; drivers connect directly.

Sources: [Atlas SQL Interface Overview](https://www.mongodb.com/docs/sql-interface/), [Transition Guide](https://www.mongodb.com/docs/atlas/tutorial/transition-bic-to-atlas-sql/), [Power BI Connector](https://learn.microsoft.com/en-us/power-query/connectors/mongodb-atlas-sql-interface), [Atlas SQL GA Blog](https://www.mongodb.com/blog/post/real-time-insights-through-atlas-sql-interface)

### Architecture

```
[Tableau / Power BI / Excel]
         |
  [MongoDB ODBC/JDBC Driver]
         |
  [Atlas SQL Schema Builder]   ← translates SQL → aggregation pipeline
         |
  [Atlas Data Federation]      ← query engine; unified view across clusters, S3, HTTPS
         |
  [Atlas Cluster(s)]
```

**No mongosqld proxy required** — the driver connects directly to Atlas.

### Key Advantages Over BI Connector

| Feature | BI Connector | Atlas SQL Interface |
|---|---|---|
| Setup | Proxy + DRDL files | Drivers only, no proxy |
| Schema | Sampled/manual DRDL | Dynamic, accurate, stored in DB |
| Multi-source | Atlas only | Atlas + S3 + HTTPS endpoints |
| Cost | Subscription required | Free (pay for Data Federation queries) |
| Status | EOL Sept 2026 | Current, no EOL |
| Authentication | SCRAM/LDAP/Kerberos | X.509, OIDC |

### Supported BI Tools

| Tool | Connector Type | Notes |
|---|---|---|
| Power BI Desktop | Microsoft-certified connector | DirectQuery supported |
| Power BI Service | Native connector | Via On-Premises Data Gateway |
| Tableau Desktop | Partnership-built Tableau Connector | |
| Tableau Server | Supported | |
| Tableau Prep | Supported | |
| Tableau Cloud | Supported (GA as of 2025) | Verify current status at mongodb.com/try/download |
| Excel | ODBC Driver | |
| Others | Generic ODBC/JDBC | MySQL-compatible wire protocol |

### Driver Installation

```bash
# Download from:
# https://www.mongodb.com/try/download/odbc-driver

# Power BI — connect via Get Data → Database → MongoDB Atlas SQL
# Tableau — Connect → Atlas SQL Interface → select Tableau Connector

# For ODBC-generic tools:
# DSN setup points to Atlas federated endpoint (host:27015 by default)
```

### Authentication (SQL Interface)

- **X.509 certificates** — recommended for enterprise/production
- **OIDC** — federated identity provider integration
- Database username/password via Atlas (stored as DB user)

### Schema Builder

Instead of DRDL files, use the **MongoDB SQL Schema Builder**:
1. In Atlas UI: Data Federation → your federated instance → Schema Builder.
2. Schema is stored in the database (not in-memory), persists across restarts.
3. Accurate schema mapping with no sampling errors — schema is derived from actual documents.
4. Supports nested documents flattened as columns, arrays unwound as rows.

### MongoSQL Limitations

- **Read-only** — no INSERT/UPDATE/DELETE (same as BI Connector)
- **SQL-92 dialect only** — no advanced SQL window functions in all cases
- All [Atlas Data Federation limitations](https://www.mongodb.com/docs/atlas/data-federation/supported-unsupported/limitations/) apply
- Requires Atlas cluster (MongoDB 5.0+) or **MongoDB Enterprise Advanced (EA) for self-managed** (MongoDB 6.0+). EA is a paid license tier; contact MongoDB Sales or your rep. Community Edition is not supported.
- Not available for self-managed Community Edition

### Migration: BI Connector → Atlas SQL Interface

Use the **MongoSQL Transition Readiness Tool** to analyze compatibility before migrating:

```bash
# Download tool from MongoDB docs
chmod +x mongosql-transition-tool

./mongosql-transition-tool \
  --input /path/to/mongosql/logs \
  --uri mongodb+srv://cluster.mongodb.net/ \
  --username <your-username> \
  --output /path/to/report
```

The tool produces:
- Historical query analysis (which SQL constructs are used)
- Schema compatibility report
- List of queries needing syntax changes
- Data type compatibility issues

**Migration steps:**
1. Run Transition Readiness Tool against existing BI Connector logs.
2. Enable Atlas SQL Interface on your federated database instance.
3. Install new ODBC/JDBC drivers and update DSN configuration.
4. Rebuild schema via Schema Builder (don't port DRDL files).
5. Test BI tool connections and queries.
6. Fix failing queries (SQL-92 dialect differences).
7. Cut over production BI tools before September 2026.

---

## Part 3: Atlas Data API (Historical Context — Removed Sept 30, 2025)

> **Status: REMOVED.** The Atlas Data API, Custom HTTPS Endpoints, GraphQL API, and Atlas App Services features were shut down September 30, 2025. This section is historical context only — to help teams understand what they had and what to migrate to. See Part 4 for current replacement patterns.

### What the Data API Was

The Atlas Data API provided pre-configured HTTPS endpoints for CRUD operations against Atlas collections without installing a driver. It was useful for lightweight serverless and mobile integrations that couldn't maintain a persistent driver connection.

**Actions it supported:** `findOne`, `find`, `insertOne`, `insertMany`, `updateOne`, `updateMany`, `deleteOne`, `deleteMany`, `aggregate`

**Why it was removed:** MongoDB deprecated the entire Atlas App Services platform (Device Sync, SDKs, Data API, GraphQL, Static Hosting, HTTPS Endpoints) in favour of driver-based patterns and purpose-built alternatives. The App Services runtime added operational complexity and the Data API's capabilities are better served by a thin driver-backed API layer the team owns.

Sources: [Deprecation Notice](https://www.mongodb.com/docs/atlas/app-services/data-api/data-api-deprecation/), [EOL Community Thread](https://www.mongodb.com/community/forums/t/mongodb-atlas-data-api-and-custom-https-endpoints-end-of-life-and-deprecation/296686), [Softinstigate Migration Guide](https://softinstigate.com/en/blog/posts/mongodb-deprecates-data-api/)

---

## Part 4: Replacement Patterns for HTTP Data Access

Since the Atlas Data API was removed, here are the production-grade replacement patterns ordered by fit.

### Pattern 1: MongoDB Driver + Express.js (Node.js)

Best for: Web apps, serverless APIs, microservices.

```javascript
// src/server.js — Express + MongoDB native driver
import express from 'express';
import { MongoClient } from 'mongodb';

const client = new MongoClient(process.env.MONGODB_URI);
await client.connect(); // connect once at startup

const app = express();
app.use(express.json());

// Replaces Data API findOne
app.post('/api/findOne', async (req, res) => {
  const { database, collection, filter } = req.body;
  const doc = await client.db(database).collection(collection).findOne(filter);
  res.json(doc ?? {});
});

// Replaces Data API insertOne
app.post('/api/insertOne', async (req, res) => {
  const { database, collection, document } = req.body;
  const result = await client.db(database).collection(collection).insertOne(document);
  res.json({ insertedId: result.insertedId });
});

app.listen(3000);
```

### Pattern 2: MongoDB Driver + FastAPI (Python)

Best for: Data science pipelines, Python-native teams, ML feature stores.

```python
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import Any
import os

app = FastAPI()
client = AsyncIOMotorClient(os.environ["MONGODB_URI"])

class FindOneRequest(BaseModel):
    database: str
    collection: str
    filter: dict[str, Any]

@app.post("/findOne")
async def find_one(req: FindOneRequest):
    doc = await client[req.database][req.collection].find_one(req.filter)
    return doc or {}
```

### Pattern 3: AWS Lambda + MongoDB Driver

Best for: Serverless, event-driven, AWS-native deployments.

```javascript
// lambda/handler.js
import { MongoClient } from 'mongodb';

// Declared outside handler — reused across warm Lambda invocations
let client;

export const handler = async (event) => {
  if (!client) {
    client = new MongoClient(process.env.MONGODB_URI);
    await client.connect();
  }
  const { action, database, collection, filter } = JSON.parse(event.body);
  // ... route to appropriate collection method
};
```

**Key pattern:** Declare `client` outside the handler so it survives Lambda container reuse. Creating a new connection per invocation exhausts the Atlas connection pool.

### Pattern 4: Delbridge Data API (Drop-in Replacement)

Best for: Teams with existing Data API clients that need a wire-compatible replacement with no code changes.

- Open-source, listed on MongoDB's official deprecation alternatives page
- Supports all 9 original Data API operations with compatible request/response payloads
- Self-hosted; connect to your Atlas cluster via connection string
- Source: [Delbridge Data API](https://github.com/delbridge-io/data-api)

### Pattern 5: RESTHeart

Best for: Enterprise deployments needing a production-ready REST API without writing custom server code.

- MongoDB-recommended alternative; maintained by Softinstigate
- REST + GraphQL over MongoDB, with built-in auth (basic auth, JWT, X.509)
- Open-core with commercial support
- Source: [restheart.org](https://restheart.org/docs/)

### Selecting the Right Pattern

| Scenario | Recommended Pattern |
|---|---|
| New REST API for web/mobile app | Express.js + MongoDB driver |
| Python data pipeline | FastAPI + Motor |
| AWS-native serverless | Lambda + MongoDB driver |
| Need Data API wire compatibility | Delbridge |
| Enterprise REST API without custom code | RESTHeart |
| Edge/CDN functions | MongoDB driver (Node) in Cloudflare Workers / Vercel |

---

## Part 5: Atlas GraphQL API (Historical — Removed Sept 30, 2025)

> **Status: REMOVED.** No new apps could enable GraphQL after July 2024. All Atlas GraphQL endpoints were shut down September 30, 2025.

### What It Was

Auto-generated GraphQL schema from MongoDB document schemas, with custom resolver support backed by Atlas Functions. Used for read-heavy frontend clients, Apollo integration, and dashboards.

**Replacements for GraphQL over MongoDB:**
- **Hasura** — GraphQL engine with native MongoDB support (Hasura v3). Declarative permission model.
- **AWS AppSync + Lambda** — Managed GraphQL service; Lambda resolvers call MongoDB driver.
- **Apollo Server + MongoDB driver** — Self-hosted; full control over schema.
- **Prisma + MongoDB** — TypeScript-first ORM with GraphQL Nexus integration.

---

## Part 6: Decision Guide — BI and HTTP Access

### BI Tool Integration Decision Tree

```
Need SQL/BI access to MongoDB?
  ├─ Atlas cluster (MongoDB 5.0+) OR Enterprise Advanced (6.0+)?
  │    └─ YES → Atlas SQL Interface (MongoSQL) ← preferred
  │         ├─ Tableau/Power BI → use dedicated certified connectors
  │         └─ Other tools → ODBC/JDBC driver
  └─ Self-managed Community Edition?
       └─ BI Connector (until Sept 2026) → migrate to EA or Atlas before EOL
```

### HTTP Data Access Decision Tree

```
Need HTTP/REST access to MongoDB?
  ├─ Serverless/FaaS (Lambda, Cloud Run, Vercel)?
  │    └─ MongoDB driver + serverless function (reuse connection)
  ├─ Existing app server?
  │    └─ MongoDB driver + Express/FastAPI/Spring Boot
  ├─ Drop-in Data API replacement?
  │    └─ Delbridge (self-hosted)
  └─ Need production REST API without custom code?
       └─ RESTHeart
```

### GraphQL Decision Tree

```
Need GraphQL over MongoDB?
  ├─ Managed service? → Hasura or AWS AppSync + Lambda resolver
  ├─ Self-hosted, TypeScript? → Apollo Server + MongoDB driver
  └─ TypeScript ORM + GQL? → Prisma + Nexus
```

---

## Anti-Patterns

### BI Connector Anti-Patterns
- **Continuing to build on BI Connector** — EOL September 2026; any new integration should use Atlas SQL Interface.
- **Sampling heterogeneous collections without views** — produces unstable DRDL schema. Always normalize with MongoDB Views before sampling.
- **Running live dashboard queries against primary** — BI Connector honors read preference; set `readPreference=secondary` in DSN.
- **No indexes on BI filter fields** — SQL predicates that can be pushed down still need indexes. Check the aggregation pipeline with `mongotranslate`.
- **Large DRDL files with unused tables** — slows `mongosqld` startup; include only needed collections.

### Atlas SQL Interface Anti-Patterns
- **Trying to write via SQL Interface** — it is read-only by design.
- **Expecting full SQL-99 support** — MongoSQL is SQL-92; avoid window functions, CTEs, and ROLLUP.
- **Not rebuilding schema after collection schema changes** — dynamic schema is not live-updated; regenerate via Schema Builder.
- **Querying without Atlas Data Federation configured** — SQL Interface requires a federated database instance to be set up first.

### HTTP/Data API Anti-Patterns
- **Building new integrations against the deprecated Data API** — it was removed September 30, 2025.
- **Creating new MongoClient per Lambda invocation** — causes connection pool exhaustion; reuse across warm container invocations.
- **Exposing MongoDB connection strings to browser clients** — always proxy through a server-side function.
- **Using Data API API keys in frontend code** — API keys grant database access; treat as secrets, never embed in client bundles.

---

## Troubleshooting — BI Connector

| Symptom | Likely Cause | Fix |
|---|---|---|
| `Authentication failed` | Mechanism mismatch | Check `?mechanism=` in username; ensure LDAP/Kerberos are Enterprise |
| Schema shows wrong column types | Polymorphic documents | Create MongoDB View to normalize types; regenerate DRDL |
| Slow queries | SQL construct not pushable | Run `EXPLAIN <query>` in BI Connector; check `allowDiskUse` warning in logs |
| `mongosqld` high memory | Large schema or uncapped varchar | Use `--maxVarcharLength`; limit schema to used collections |
| Missing columns in Tableau | Array fields not unwound | Add `$unwind` to DRDL table definition |
| Connection refused | Port 3307 not listening | Verify `mongosqld` is running; check `--addr` flag |

## Troubleshooting — Atlas SQL Interface

| Symptom | Likely Cause | Fix |
|---|---|---|
| `Unsupported SQL syntax` | SQL-92 violation | Rewrite query; avoid CTEs, window functions |
| Schema builder returns empty | No federated database configured | Enable Atlas Data Federation first |
| Power BI DirectQuery slow | Large result sets without filters | Add WHERE clauses; check Data Federation query cost |
| Tableau can't connect | Old BI Connector ODBC installed | Uninstall old driver; install MongoDB ODBC driver for Atlas SQL |
| Auth fails with X.509 | Certificate CN mismatch | Verify DB user CN matches cert subject |

---

## References

1. [MongoDB BI Connector Documentation](https://www.mongodb.com/docs/bi-connector/current/) — components, DRDL, authentication, FAQ
2. [mongosqld Reference](https://www.mongodb.com/docs/bi-connector/current/reference/mongosqld/) — all flags and configuration options
3. [Atlas SQL Interface Overview](https://www.mongodb.com/docs/sql-interface/) — MongoSQL architecture and setup
4. [Transition BI Connector → Atlas SQL](https://www.mongodb.com/docs/atlas/tutorial/transition-bic-to-atlas-sql/) — migration guide and readiness tool
5. [Atlas SQL GA Blog](https://www.mongodb.com/blog/post/real-time-insights-through-atlas-sql-interface) — official GA announcement with Power BI/Tableau details
6. [Microsoft Power Query: MongoDB Atlas SQL Connector](https://learn.microsoft.com/en-us/power-query/connectors/mongodb-atlas-sql-interface) — Microsoft certified connector docs
7. [Data API Deprecation Notice](https://www.mongodb.com/docs/atlas/app-services/data-api/data-api-deprecation/) — official deprecation and alternatives
8. [Data API EOL Community Thread](https://www.mongodb.com/community/forums/t/mongodb-atlas-data-api-and-custom-https-endpoints-end-of-life-and-deprecation/296686) — community Q&A
9. [Atlas SQL Interface Product Page](https://www.mongodb.com/products/platform/atlas-sql-interface) — feature comparison and connector downloads
10. [BI Connector Authentication Docs](https://www.mongodb.com/docs/bi-connector/current/authentication/) — SCRAM/LDAP/Kerberos config
11. [Softinstigate Data API Migration Blog](https://softinstigate.com/en/blog/posts/mongodb-deprecates-data-api/) — RESTHeart migration patterns
12. [metadesignsolutions Migration Guide](https://metadesignsolutions.com/migrating-from-atlas-data-api-and-custom-https-endpoints-previously-realm-what-are-your-options/) — comprehensive alternatives overview
13. [BI Connector DRDL Reference](https://www.mongodb.com/docs/bi-connector/current/reference/drdl/) — DRDL file syntax
14. [Atlas SQL ODBC Driver Download](https://www.mongodb.com/try/download/odbc-driver) — official driver download page

## See Also
- `mongodb-atlas-expert` — Atlas platform, cluster config, networking
- `mongodb-atlas-triggers-functions` — Atlas Functions for serverless logic (note: App Services EOL but Triggers remain)
- `mongodb-migration-patterns` — migrating data between clusters and sources
- `mongodb-atlas-charts` — built-in BI visualization native to Atlas (no SQL required)
- `api-design-patterns` — REST/GraphQL API design for MongoDB-backed services
