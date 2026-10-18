<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-relational-migrator` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-relational-migrator
title: MongoDB Relational Migrator
version: 1.1.0
updated: "2026-05-29"
category: mongodb
tags: [mongodb, relational-migrator, migration, rdbms, oracle, mysql, postgresql, sql-server, db2, sybase, cdc, schema-mapping, code-generation, embedding, denormalization, snapshot, kafka, jdbc, pre-migration-analysis]
description: >
  Expert reference for MongoDB Relational Migrator (free GUI tool) — migrating RDBMS
  workloads (Oracle, MySQL, PostgreSQL, SQL Server, DB2, Sybase, YugabyteDB,
  CockroachDB) to MongoDB. Covers supported sources and JDBC connectivity, per-source
  permission requirements, schema mapping (embed vs reference, synthetic FKs, calculated
  fields, mapping rule types), code generation (Java/Spring Data, C#, JavaScript, AI
  SQL-to-MQL converter), snapshot and CDC continuous sync modes, Kafka vs embedded
  deployment, execution monitoring, data verification, 7 schema anti-patterns, and a
  symptom→cause→fix troubleshooting table.

  TRIGGER: user mentions Relational Migrator, migrating from Oracle/MySQL/PostgreSQL/
  SQL Server/DB2/Sybase to MongoDB, table-to-collection mapping, FK embedding decisions,
  snapshot migration, CDC migration with RM, relational schema anti-patterns for MongoDB,
  RM troubleshooting, RM code generation, SQL-to-MQL query converter, or pre-migration
  analysis reports.

  SKIP: MongoDB-to-MongoDB migrations (use mongodb-mongosync or mongodb-migration-patterns);
  schema design patterns without migration context (use mongodb-schema-design); Kafka CDC
  pipelines not using RM (use mongodb-kafka-connector); Atlas Live Migration
  (use mongodb-migration-patterns).

keywords: [relational migrator, rdbms to mongodb, oracle migration, postgresql migration, mysql migration, sql server migration, schema mapping, embedding, denormalization, CDC, change data capture, snapshot migration, code generation, spring data mongodb, node.js driver, data verification, pre-migration analysis, synthetic foreign key, calculated fields, mongosync vs relational migrator]
whenToUse:
  - "Customer is migrating from Oracle, MySQL, PostgreSQL, SQL Server, DB2, or Sybase to MongoDB"
  - "How do I map relational tables to MongoDB collections?"
  - "Should I embed or reference for this FK relationship?"
  - "Relational Migrator job failing — how do I troubleshoot it?"
  - "CDC migration is lagging or losing data with Relational Migrator"
  - "Generate Java Spring Data code from the migrated schema"
  - "What does the pre-migration analysis risk report mean?"
  - "How do I plan a zero-downtime cutover using CDC continuous sync?"
  - "Relational Migrator vs mongosync — which should I use?"
  - "How do I convert stored procedures to MongoDB aggregation pipelines?"
  - "Integer surrogate key as _id — should I keep it or use ObjectId?"
  - "Unbounded embedded array problem in migrated schema"

whenNotToUse:
  - Source is a MongoDB cluster (not RDBMS) — use mongodb-mongosync or mongodb-migration-patterns
  - Kafka CDC pipeline not using Relational Migrator — use mongodb-kafka-connector
  - Atlas Live Migration (MongoDB-to-Atlas) — use mongodb-migration-patterns
  - Pure schema design advice with no migration context — use mongodb-schema-design
  - mongosync operation or troubleshooting — use mongodb-mongosync

related_skills:
  - mongodb-migration-patterns
  - mongodb-schema-design
  - mongodb-mongosync
  - mongodb-kafka-connector
  - mongodb-expert
  - mongodb-atlas-expert
---

# MongoDB Relational Migrator

## Overview

MongoDB Relational Migrator (RM) is a **free GUI tool** that streamlines full migration of relational database workloads to MongoDB. It addresses three distinct phases of a migration project:

1. **Schema design** — visual ER-diagram–based mapping from relational tables to MongoDB collections, with FK → embed/reference decisions, field transformations, and AI-assisted recommendations.
2. **Data migration** — snapshot (one-time full load) or continuous (CDC-based) data movement, with optional data verification.
3. **Application code generation** — generates boilerplate entity classes, persistence layers, and converted SQL queries/stored procedures for Java, C#, and JavaScript.

RM is the correct tool whenever the **source is a relational database**. When both source and destination are MongoDB clusters, use mongosync instead (see Section 9).

### How to Use This Skill

When a question or task activates this skill:

1. **Identify the sub-topic** from the user's question — source DB connectivity, schema mapping, migration mode, validation, anti-patterns, troubleshooting, or tool comparison.
2. **Apply the relevant section** as the authoritative reference. Cite section numbers and table rows directly in your response.
3. **Response format:**
   - For advisory questions (embed vs reference, which migration mode): use a short decision rule or bullet list drawn from Section 3, 5, or 8.
   - For troubleshooting: use the symptom → cause → fix table from Section 11.
   - For comparison questions (RM vs mongosync): use the comparison table from Section 9.
   - For permissions/setup: quote the relevant sub-section from Section 1 verbatim.
4. **Ask one clarifying question** before giving a detailed recommendation if the following are unknown:
   - Source database type (if not specified and multiple interpretations are possible)
   - Whether downtime is acceptable (determines snapshot vs CDC recommendation)
   - Target destination (Atlas vs self-managed affects `_id` and sharding advice)
   If the context makes these obvious, proceed without asking.

**Download:** https://www.mongodb.com/try/download/relational-migrator  
**Docs root:** https://www.mongodb.com/docs/relational-migrator/

---

## 1. Supported Sources and Connectivity

### Primary Supported Databases (GA)

| Source Database | Snapshot | CDC (Continuous) |
|---|---|---|
| Oracle 11g, 12c, 18c, 19c, 21c | Yes | Yes (LogMiner) |
| Microsoft SQL Server 2016, 2017, 2019, 2022, Azure SQL | Yes | Yes (SQL Server CDC) |
| MySQL 5.7, 8.0, 8.4 | Yes | Yes (binlog) |
| PostgreSQL 9.6, 10, 11, 12, 13, 14, 15, 16 | Yes | Yes (logical replication) |
| IBM DB2 LUW 10.5, 11.1, 11.5 | Yes | Limited |
| Sybase ASE (SAP ASE) 16.x | Yes | Yes |

### Additional JDBC Sources (added 2025)

As of early 2025, Relational Migrator extended JDBC connectivity to support additional Postgres-compatible and SQL-compatible databases:
- YugabyteDB
- CockroachDB
- SAP Sybase IQ (SAP IQ)
- SAP SQL Anywhere

These use snapshot mode only with standard JDBC connectivity.

### Pre-Migration Analysis Support

Pre-migration analysis (automated risk assessment) is available for: **Oracle, SQL Server, MySQL, PostgreSQL**. DB2 and Sybase have limited analysis coverage.

### JDBC Connectivity

Relational Migrator uses JDBC to connect to all source databases:
- **SQL Server and PostgreSQL JDBC drivers** are bundled and installed automatically.
- **Oracle** requires manual placement of `ojdbc11.jar` (version 21.6.0.0) in the Drivers folder.
- **MySQL** requires `mysql-connector-j-9.1.x.jar` placed in the Drivers folder.
- **DB2** requires the IBM JDBC driver (Type 4).

Connection string formats by source:
- Oracle: `jdbc:oracle:thin:@<host>:<port>:<sid>` or `jdbc:oracle:thin:@//<host>:<port>/<service>`
- MySQL: `jdbc:mysql://<host>:<port>/<database>`
- PostgreSQL: `jdbc:postgresql://<host>:<port>/<database>`
- SQL Server: `jdbc:sqlserver://<host>:<port>;databaseName=<database>`
- DB2: `jdbc:db2://<host>:<port>/<database>`

### Permission Requirements Per Source

**Oracle (Snapshot)**
- `CONNECT` and `SELECT` on each table to be migrated
- If service account does not own the tables: `SELECT ANY TABLE` or explicit grants
- Multi-tenant (CDB): permissions must include `CONTAINER=ALL`

**Oracle (CDC)**
- Database must be in `ARCHIVELOG` mode
- `EXECUTE ON DBMS_LOGMNR`, `SELECT` on `V$LOG`, `V$LOGFILE`, `V$ARCHIVED_LOG`, `V$LOG_HISTORY`, `V$TRANSACTION`
- `LOGMINING` privilege (Oracle 12c+)
- All-column supplemental logging must be enabled on migrated tables
- Oracle 12c: run setup as SYSDBA on CDB, not PDB

**PostgreSQL (Snapshot)**
- `USAGE` on each schema, `SELECT` on each table

**PostgreSQL (CDC)**
- `REPLICATION` role or superuser
- `wal_level = logical` in `postgresql.conf`
- `CREATE PUBLICATION` privilege
- RM auto-generates the setup SQL via the "Generate Script" button

**SQL Server (Snapshot)**
- `SELECT` on each table, `VIEW DATABASE STATE`

**SQL Server (CDC)**
- CDC enabled at database level (`sys.sp_cdc_enable_db`)
- CDC enabled per table (`sys.sp_cdc_enable_table`)
- `db_owner` or explicit CDC read permissions
- RM provides a Generate Script button to auto-configure CDC prerequisites

**MySQL (Snapshot)**
- `SELECT` on each table to be migrated
- `SHOW DATABASES` and `SHOW VIEW` privileges

**MySQL (CDC)**
- Binary logging enabled (`binlog_format = ROW`)
- `REPLICATION SLAVE`, `REPLICATION CLIENT` privileges
- `SELECT` on all migrated tables

**DB2 (Snapshot)**
- `CONNECT` privilege on the database
- `SELECT` on each table to be migrated
- `SYSIBM.SYSCOLUMNS`, `SYSIBM.SYSTABLES` read access for schema discovery

**Sybase ASE (Snapshot)**
- `SELECT` on each table to be migrated
- Access to system tables for schema discovery (`sysobjects`, `syscolumns`)

**Automatic Configuration Check**

When you set the migration Mode, RM checks if prerequisites are met. If issues are found, a warning banner and "Generate Script" button appear — clicking it downloads an SQL script with all required configuration statements to run on the source.

---

## 2. Schema Analysis and Mapping

### Project Setup

A Relational Migrator **project** contains:
- A source relational database connection
- A target MongoDB connection (Atlas or self-managed)
- Mapping rules (the schema transformation spec)
- Migration job history

### Visual Schema Discovery

When you connect to the source, RM auto-reads:
- All tables, columns, data types, constraints
- Primary keys, foreign keys, unique constraints, indexes
- Views (visible but not directly migrated as views)
- ER diagram rendered automatically

### Starting Schema Options

You can begin mapping from three starting points:

1. **Recommended schema** — RM analyzes FK relationships and suggests embeddings based on common document patterns
2. **1:1 mapping** — every table becomes its own collection with no denormalization (fastest start, rarely optimal)
3. **New schema** — blank canvas, build mapping rules manually

### Schema Mapping Concepts

**Collection mapping** — each mapping rule specifies which table(s) map to which MongoDB collection. Options:
- One table → one collection (default)
- Multiple tables → one collection (merge/embed)
- One table → multiple collections (split, rare)

**Field mapping** — each column maps to a document field. Customizations:
- Rename fields (e.g., `customer_id` → `customerId`)
- Change BSON type (e.g., `VARCHAR` → `String`, `DECIMAL` → `Decimal128`)
- Exclude columns from migration
- Mark fields as computed (JavaScript expression, not migrated from source)

**_id field configuration** — by default, RM preserves the relational PK as `_id`. You can:
- Use the original PK value as `_id` (e.g., integer PK, UUID)
- Generate a new ObjectId and store the original PK as a regular field
- Compose a compound `_id` from multiple columns

### Foreign Key Handling

Every FK relationship in the source becomes a decision point in RM:

| FK Cardinality | Options |
|---|---|
| One-to-One | Embed child into parent as nested document, or keep as separate collection with reference |
| One-to-Many | Embed child array into parent (denormalize), or keep child as separate collection with reference field |
| Many-to-Many (junction table) | Embed arrays in one or both sides, or keep junction as separate collection |

**Default behavior:** All FKs are translated to document references (separate collections, FK value preserved as a field). You must explicitly add embedding rules to denormalize.

### Synthetic Foreign Keys

When the source database lacks explicit FK constraints (common in legacy schemas), you can define **synthetic foreign keys** in RM. A synthetic FK:
- Represents a logical relationship between two tables
- Is defined solely within RM — not written to the source DB
- Allows the same embed/reference mapping rules to be applied

Synthetic FK cardinalities: One-to-One or One-to-Many.

### Pre-Migration Analysis

Available for Oracle, SQL Server, MySQL, PostgreSQL. The analysis report identifies:

- **Schema risks** — database or table configuration that creates mapping difficulty
- **Data type incompatibilities** — types that RM cannot automatically convert
- **Unsupported features** — source features with no MongoDB equivalent (triggers, views, sequences, stored procedures)
- **Performance risks** — large table sizes, missing indexes on join columns, high-cardinality concerns

The **Incompatible Features** tab lists everything RM cannot automatically migrate. These require manual remediation (application-layer logic, Atlas Triggers, etc.).

**Limitation:** Pre-migration analysis does not analyze SQL code inside stored procedures, views, or triggers — it flags their existence but does not evaluate their logic.

---

## 3. Mapping Rules Reference

### Rule Types

**New Document Rule** (table → collection)  
Maps one source table to one destination collection. This is the baseline rule every mapped table must have.

**Embedded Documents Rule** (one-to-one FK → nested object)  
Denormalizes a one-to-one FK relationship by embedding the child document into the parent. The child table's columns become nested fields under a specified key.

```json
// Parent: orders — Child: order_detail (one-to-one)
// Result in MongoDB:
{
  "_id": 101,
  "order_date": "2025-01-15T00:00:00Z",
  "order_detail": {
    "item_count": 3,
    "subtotal": 149.99
  }
}
```

**Embedded Array Rule** (one-to-many FK → array of subdocuments)  
Denormalizes a one-to-many FK relationship by embedding the child rows as an array in the parent document.

```json
// Parent: customers — Child: addresses (one-to-many)
// Result:
{
  "_id": "CUST001",
  "name": "Acme Corp",
  "addresses": [
    { "type": "billing", "city": "New York" },
    { "type": "shipping", "city": "Chicago" }
  ]
}
```

**Array Conditions**  
Embedded arrays support:
- **Sort** — sort subdocuments by a field before embedding (e.g., sort `order_items` by `sequence_number`)
- **Limit** — cap the number of embedded subdocuments (applies the Subset Pattern for large child sets)
- **Filter** — JavaScript expression to exclude certain child rows from embedding

**Many-to-Many (Junction Table) Strategies**

For a junction table `order_products` linking `orders` and `products`:

Option A: Embed product IDs as array in orders
```json
{ "_id": 101, "product_ids": [42, 57, 91] }
```

Option B: Embed full product subdocuments in orders (denormalized)
```json
{ "_id": 101, "products": [{ "id": 42, "name": "Widget" }] }
```

Option C: Keep junction as a separate collection (appropriate when the relationship has its own attributes like `quantity`, `price_at_time`)
```json
{ "order_id": 101, "product_id": 42, "quantity": 2, "unit_price": 19.99 }
```

### Merge Fields into Parent

The "Merge fields into parent" option flattens child table columns directly into the parent document (rather than nesting under a key), useful when the related table is purely an extension of the parent.

### Calculated Fields

JavaScript expressions that compute new field values during migration:

```javascript
// Concatenate first_name + last_name into full_name
firstName + " " + lastName

// Compute age from birth_date
Math.floor((new Date() - new Date(birthDate)) / (365.25 * 24 * 60 * 60 * 1000))

// Convert status integer to string
statusCode === 1 ? "active" : statusCode === 2 ? "inactive" : "unknown"
```

Calculated fields are migration-time transformations — not stored procedures or triggers. They run during the snapshot/CDC pipeline.

### Field Renaming and Exclusion

- **Rename**: map `CUST_ID` → `customerId`, `ACCT_NBR` → `accountNumber`
- **Exclude**: mark columns to skip (e.g., audit columns like `created_by`, `modified_dt` you don't need in MongoDB)
- **BSON type override**: force `NUMERIC(15,4)` → `Decimal128` instead of default `Double`

### Mapping Rule Filters

Filter rules allow including/excluding rows from a table based on a JavaScript expression evaluated against column values:

```javascript
// Only migrate active customers
status === "A"

// Only migrate orders from 2023 onwards
new Date(order_date) >= new Date("2023-01-01")
```

---

## 4. Code Generation

### Overview

After defining the schema mapping, RM generates application-layer boilerplate code derived from the MongoDB collections. Code generation analyzes each collection in the destination and produces language-specific files.

### Supported Languages and Frameworks

| Language | Framework/Driver |
|---|---|
| Java | Spring Data MongoDB (repositories, entities) |
| Java | Plain Java with MongoDB Java Driver |
| C# | .NET MongoDB Driver (POCO classes, IMongoCollection) |
| JavaScript | Node.js MongoDB Driver |
| JSON | Schema JSON (collection schema definition) |

### What Gets Generated

For each collection:
- **Entity/model classes** — POJOs (Java), C# classes, or JS objects matching the document structure, including nested embedded documents and arrays
- **Repository interfaces** (Spring Data MongoDB) — CRUD operations, common query methods
- **API scaffolding** (Spring Boot) — controller + service layer skeletons
- **Collection configuration** — index definitions, validation rules

Example generated Java entity (Spring Data MongoDB):

```java
@Document(collection = "customers")
public class Customer {
    @Id
    private String id;
    private String name;
    private String email;
    private List<Address> addresses;  // embedded array

    // getters, setters...
}

@Repository
public interface CustomerRepository extends MongoRepository<Customer, String> {
    List<Customer> findByEmail(String email);
}
```

### Query Converter (AI-Powered SQL → MQL)

The Query Converter uses **generative AI** to convert SQL artifacts to MongoDB Query API syntax:

**What it converts:**
- SQL `SELECT` statements → MongoDB `find()` or aggregation pipeline
- `INSERT`/`UPDATE`/`DELETE` → MongoDB write operations
- SQL Views → MongoDB aggregation pipelines (as `$lookup`-based queries or Atlas views)
- DML Triggers → MongoDB Atlas Triggers (JavaScript)
- Stored Procedures → MongoDB JavaScript / aggregation equivalents
- Oracle Packages → individual MongoDB functions/aggregations
- SQL Server Functions → MongoDB equivalents

**Target languages:** JavaScript, C#, Java

**How to use:**
1. Paste SQL code into the Query Converter pane
2. Select target language
3. RM sends to AI model with project mapping context
4. Receives converted MongoDB code

**Important limitations:**
- AI may produce incorrect results for complex or long queries
- Queries referencing tables not in the project schema will fail conversion
- Stored procedure conversion is best-effort — verify all output before production use
- Oracle `ROWNUM`-based pagination, `CONNECT BY` hierarchical queries, and complex `MERGE` statements often require manual adjustment
- Some conversions will not complete at all — RM flags these for manual attention

### Template Customization

Code generation uses template files. You can customize templates to match your project's naming conventions, package structure, or framework version.

---

## 5. Migration Modes

### Mode 1: Snapshot (One-Time Full Load)

A **snapshot job** migrates all data once and stops. This is the standard migration mode for planned cutovers.

**Characteristics:**
- Requires application downtime during migration (or a brief write-freeze at cutover)
- Simpler to configure and operate
- No CDC prerequisites on the source
- Supports all source databases including DB2 and Sybase ASE
- Idempotent when using "Drop destination collections before migration" option

**Use when:**
- Downtime is acceptable
- Source database does not support CDC (DB2, older Sybase)
- Migration window is short (< 4 hours for dataset size)
- Testing or staging environment migrations

**Parallel execution:** You can split a large snapshot into parallel batches using table filters — creating multiple jobs each targeting a subset of tables.

### Mode 2: Continuous Sync (CDC — Change Data Capture)

A **continuous sync job** first takes an initial snapshot, then continuously streams changes (INSERT, UPDATE, DELETE) from the source to MongoDB using CDC. This enables near-zero-downtime cutovers.

**Characteristics:**
- Initial snapshot phase (like a snapshot job) followed by continuous CDC streaming
- Source changes replicated in near-real time
- Requires CDC prerequisites on source (see Section 1)
- Supported for Oracle, SQL Server, MySQL, PostgreSQL, Sybase ASE
- Deployment via Embedded mode or Kafka mode

**Typical cutover workflow:**
1. Start continuous sync → RM takes initial snapshot
2. CDC streaming begins — source and MongoDB stay in sync
3. Application traffic still hitting source DB
4. When lag is near zero, freeze writes to source (maintenance window, seconds to minutes)
5. Verify MongoDB is caught up
6. Switch application connection strings to MongoDB
7. Stop RM continuous sync job

**Known data integrity issue (fixed in 1.14):** Before v1.14, CDC mode had a silent data loss/corruption bug. All users must upgrade to 1.14+ before running CDC migrations.

### Deployment Modes for CDC

**Embedded mode (default):**
- CDC pipeline runs inside the RM application process
- Simpler setup, suitable for most migrations
- On failure, restart RM application to resume (manual)

**Kafka mode:**
- CDC pipeline uses a Kafka cluster (self-managed or Confluent Cloud)
- More resilient: Kafka health checks auto-resume CDC after broker failures for up to 24 hours
- Required for very large datasets or enterprise reliability requirements
- Configuration: `kafka` profile (self-managed) or `confluent` profile (Confluent Cloud)
- Docker Compose deployment supported for containerized Kafka

**Confluent Cloud mode:**
- Managed Kafka via Confluent Cloud
- Eliminates Kafka operations overhead
- Available in early access program

---

## 6. Execution and Monitoring

### Installation and System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| RAM | 8 GB | 16 GB+ |
| OS | Windows 10+, macOS 11+, Linux (RHEL/Ubuntu), Docker | |
| Browser | Chrome, Firefox, Edge, Safari (latest) | |
| Java | Bundled (not required separately) | |

**Platforms:** Windows (.msi), macOS (.dmg), Linux (.tar.gz / .rpm), Docker

**JDBC drivers bundled:** SQL Server, PostgreSQL. Oracle and MySQL require manual driver download.

### Creating and Running a Migration Job

1. Open project → Data Migration tab
2. Click "Create new job"
3. Select migration mode (Snapshot or Continuous)
4. Select tables to include (default: all mapped tables; can use filters)
5. Set migration options:
   - **Drop destination collections before migration** — drops and recreates (safe for reruns)
   - **Verify migrated data** — enables post-migration row count + content check (adds significant time)
   - **Write concern** — default `majority`, can lower for speed
6. Start job

### Parallelism and Batch Tuning

- RM runs multi-threaded snapshots with multiple concurrent table loads
- Performance improvements for multithreaded snapshots with cyclic dependencies in recent releases
- Write performance enhancements for embedded arrays in multithreaded mode
- Table filtering lets you run multiple jobs in parallel targeting non-overlapping table subsets

### Migration Job Lifecycle

Jobs execute in stages visible on the Job Overview pane:
1. **Pre-flight checks** — validates connections, permissions, prerequisites
2. **Snapshot phase** — full table reads and writes to MongoDB
3. **CDC phase** (continuous mode only) — streams ongoing changes
4. **Verification phase** (if enabled) — row count and content comparison
5. **Complete / Error**

### Monitoring Metrics

From the History pane (Data Migration tab):
- Job status: In Progress, Completed, Failed
- Tables migrated: count and progress
- Documents written to MongoDB
- Throughput (MB/s, documents/s) — available in benchmark reporting
- Error details for failed tables

**Best practice for performance bottleneck identification:** Monitor in this order:
1. Source database I/O and CPU
2. RM application CPU/memory
3. Network bandwidth between RM and source + target
4. MongoDB write performance (Atlas performance advisor, mongostat)

### Job Stop and Recovery

**Snapshot jobs:**
- Can be stopped, but **cannot be resumed**
- To re-migrate, create a new job with "Drop destination collections before migration" enabled

**Continuous sync jobs (Embedded mode):**
- Can be paused; restart RM application to resume
- Recovery is manual

**Continuous sync jobs (Kafka mode):**
- Kafka health checks automatically attempt resume for up to 24 hours after broker failure
- Recovery for individual Kafka broker failures is automatic

### REST API

RM exposes a REST API for programmatic job management:
- Start, stop, monitor migration jobs
- Useful for integrating RM into CI/CD pipelines or automated migration workflows
- Documented at: https://www.mongodb.com/docs/api/doc/mongodb-relational-migrator-rest-api/

---

## 7. Validation

### Built-In Data Verification

RM includes a post-migration data verification step. **It is opt-in** — you must enable "Verify migrated data" in Migration Options before starting the job.

**What it verifies:**
- **Row count match**: source table row count == destination collection document count
- **Content equivalence**: source rows are equivalent to destination documents (sample-based comparison)

**Important constraints:**
- Supported for **snapshot (one-time) jobs only** — not for continuous sync
- Can add as much time as the migration itself
- Not enabled by default due to performance cost

**Success criteria:** Source and destination states match at job completion.

### Manual Validation Patterns (Beyond Built-In)

For production migrations, supplement RM's built-in verification with:

**1. Row/document count comparison**
```javascript
// MongoDB: count documents in each collection
db.customers.countDocuments()
db.orders.countDocuments()

// Compare against source SQL:
// SELECT COUNT(*) FROM customers;
// SELECT COUNT(*) FROM orders;
```

**2. Checksum / hash comparison**  
Compute hash on a sorted, projected subset of source rows and compare to equivalent MongoDB aggregation output.

**3. Data type spot-checks**  
Verify BSON type assignments match expectations — especially for:
- Decimal/numeric columns → should be `Decimal128`, not `Double`
- Date/time columns → should be `Date`, not `String`
- Binary columns → `BinData`, not missing

**4. Referential integrity verification**  
MongoDB does not enforce referential integrity. After migration, run aggregation queries to check for "dangling references":
```javascript
// Find orders with no matching customer
db.orders.aggregate([
  { $lookup: { from: "customers", localField: "customerId", foreignField: "_id", as: "customer" }},
  { $match: { customer: { $size: 0 }}},
  { $count: "orphaned_orders" }
])
```

**5. Custom validation queries**  
Write application-specific business rule checks:
```javascript
// All orders must have at least one line item
db.orders.countDocuments({ "lineItems": { $size: 0 }})  // should be 0
```

**6. Reconciliation for CDC migrations**  
After cutover, run a reconciliation pass:
- Compare timestamps: last CDC event time vs current time
- Spot-check recently modified records in source vs MongoDB
- Verify no transactions were lost during the cutover window

---

## 8. Schema Conversion Anti-Patterns

These are the most common mistakes when using Relational Migrator, especially when starting with a 1:1 mapping and leaving it unchanged.

### Anti-Pattern 1: 1:1 Table → Collection Copy

**The mistake:** Taking the default 1:1 mapping (every table → its own collection, all FKs as reference fields) and shipping it to production.

**Why it's wrong:** This is a relational schema in MongoDB clothing. You lose MongoDB's primary value proposition — embedding related data for fast, single-document reads. Every query that needed a JOIN in SQL now needs a `$lookup` in MongoDB, which is expensive.

**The correct approach:** Analyze your application's read patterns. For each FK:
- If the child is always read with the parent → embed
- If the child has unbounded growth → reference
- If the child is queried independently → reference
- If the child is rarely needed → reference (subset pattern with limit)

### Anti-Pattern 2: Over-Embedding (Unbounded Arrays)

**The mistake:** Embedding a one-to-many relationship where the "many" side can grow without bound.

**Example:** Embedding all `order_line_items` inside an `order` document when orders can have thousands of items, or embedding all `user_activity_events` inside a `user` document.

**Why it's wrong:**
- MongoDB document size limit is 16 MB
- Large documents consume more RAM (entire document loaded even if you only need one field)
- Array updates on large arrays are slow (`$push` on a 10,000-element array)
- WiredTiger in-place updates fail on document growth → document moves → fragmentation

**The correct approach:** 
- Use the Subset Pattern (embed only the N most recent/relevant items via array conditions)
- Move the high-cardinality side to its own collection with a parent reference
- Set array Limit in RM's embedded array options if the relationship has bounded growth at a known limit

### Anti-Pattern 3: Ignoring Read Patterns

**The mistake:** Designing the MongoDB schema based on the relational structure rather than how the application actually reads data.

**Why it's wrong:** MongoDB schema design is application-driven. The optimal schema depends on which queries run most frequently, not on normalization theory.

**The correct approach before using RM:**
- Profile the top 10-20 most frequent queries in the existing application
- Map each query to a document access pattern
- Design collections to satisfy those patterns with single-document reads where possible
- Use RM mapping rules to implement the access-pattern-driven design

### Anti-Pattern 4: Keeping Integer Surrogate Keys as `_id`

**The mistake:** Mapping the relational integer auto-increment primary key directly to MongoDB `_id`.

**Why it can be problematic:**
- Integer `_id` values are predictable and expose record count information
- If migrating to Atlas, integer `_id` in a sharded collection creates monotonically increasing hotspot on the shard key
- Loses the benefits of ObjectId's built-in timestamp and distributed generation

**The correct approach:**
- For Atlas sharded collections: generate new ObjectId as `_id`, store the original integer as `legacyId` (indexed)
- For non-sharded or self-managed: integer `_id` is acceptable if application references remain consistent
- RM provides the option to customize `_id` generation per mapping rule

### Anti-Pattern 5: Migrating Normalization Without Questioning It

**The mistake:** Faithfully migrating a 5NF (fifth normal form) relational schema with dozens of lookup tables, all as separate MongoDB collections.

**Common example:** Address type, country, state, city all as separate reference tables → 5 `$lookup` stages in MongoDB to reconstruct an address.

**The correct approach:** Collapse lookup/reference tables into string values or embedded enums in the parent document. In MongoDB, denormalized string values are cheap to store and fast to read. Normalization to eliminate update anomalies is a relational concern — MongoDB handles this differently (application-level or Atlas Triggers for cascading updates when needed).

### Anti-Pattern 6: Not Configuring `_id` for Embedded Documents

**The mistake:** Embedding arrays of subdocuments without considering whether those subdocuments need independent addressability.

**Why it matters:** MongoDB has no auto-generated `_id` for array subdocuments unless you explicitly add one. Without an `_id`, you cannot efficiently target a specific array element for update (you must use positional operators or `arrayFilters`, which require matching criteria).

**The correct approach:** Add an `_id` (ObjectId or UUID) to embedded subdocuments if:
- Individual subdocuments need to be updated by ID
- Subdocuments are referenced from other collections
- Use RM calculated fields to generate `{ $oid: ... }` for each subdocument

### Anti-Pattern 7: Migrating Views as Collections

**The mistake:** Treating SQL views as data sources to migrate into MongoDB collections.

**Why it's wrong:** Views in SQL are query abstractions, not data. Migrating view output as a snapshot creates a stale, denormalized copy that never updates.

**The correct approach:**
- Analyze what the view was doing
- If it's an aggregation: rewrite as a MongoDB aggregation pipeline or Atlas view
- If it's a join: implement as `$lookup` pipeline
- If it's a filter: apply filter at the application layer or as a partial index

---

## 9. Relational Migrator vs mongosync

| Dimension | Relational Migrator | mongosync |
|---|---|---|
| **Source** | Relational DBs (Oracle, MySQL, PostgreSQL, SQL Server, DB2, Sybase, JDBC) | MongoDB clusters only |
| **Destination** | MongoDB Atlas or self-managed | MongoDB Atlas or self-managed |
| **Schema transformation** | Full — embed/reference decisions, field mapping, type conversion | None — copies documents as-is |
| **GUI** | Yes — full visual UI | No — CLI tool |
| **CDC** | Yes (via Debezium, Kafka optional) | Yes (oplog/change streams) |
| **Verification** | Built-in row count + content check | Built-in embedded verifier |
| **Code generation** | Yes — Java, C#, JavaScript | No |
| **Free** | Yes | Yes |
| **Use case** | RDBMS → MongoDB migration | MongoDB → MongoDB migration, cluster upgrades, topology changes |

### Decision Rule

```text
Source is a relational database (Oracle, MySQL, PostgreSQL, SQL Server, DB2, Sybase)?
  → Use Relational Migrator

Source is a MongoDB cluster?
  → Use mongosync (or Atlas Live Migration if Atlas is the destination)

Source is MongoDB < 4.4?
  → Upgrade MongoDB first, then use mongosync
  → Or use mongodump/mongorestore for very old versions

Both source and destination are MongoDB, but you need schema transformation?
  → Use mongosync for data movement + custom aggregation pipeline for transformation
  → Or use Relational Migrator if re-modeling from scratch is preferred
```

### What mongosync Does NOT Do

- Cannot connect to any relational database
- Cannot transform document structure during sync
- Cannot convert data types
- Cannot generate application code

### What Relational Migrator Does NOT Do

- Cannot migrate between two MongoDB clusters (no MongoDB → MongoDB)
- Cannot read from MongoDB as a source
- Is not a replacement for custom ETL pipelines when complex business logic transformations are needed beyond what calculated fields support

---

## 10. Known Limitations

### Data Type Limitations

| Source | Unsupported / Limited Types |
|---|---|
| Oracle | `BFILE`, `LONG`, `LONG RAW` — skipped during import (error logged) |
| Oracle | `XMLTYPE` — limited support |
| SQL Server | `FILESTREAM` — skipped during import (error logged) |
| SQL Server | `HIERARCHYID`, `GEOMETRY`, `GEOGRAPHY` — limited |
| MySQL | `GEOMETRY` — limited; `ENUM` migrated as String |
| PostgreSQL | Custom array types — limited; `HSTORE` limited |
| All | Very large `BLOB`/`CLOB` columns may hit memory limits |

Relational Migrator added improved **error reporting** in recent versions: when an unsupported binary type is encountered, the job logs a clear error and skips that column rather than silently dropping data.

### Stored Procedure Limitations

- Stored procedures are **not migrated as executable objects** — MongoDB has no stored procedure equivalent
- Query Converter can attempt to convert stored procedure logic to MongoDB aggregation pipelines or Atlas Triggers
- Complex T-SQL/PL-SQL features (cursors, complex exception handling, dynamic SQL, `EXEC`, `OPENQUERY`) often require manual rewrite
- Long or complex procedures may not convert at all — RM flags these
- **Recommendation:** Inventory all stored procedures before migration. Categorize as: (a) convert to aggregation, (b) move to application layer, (c) convert to Atlas Trigger

### View Limitations

- SQL views are **not migrated as MongoDB views** automatically
- Views appear in the schema analysis but must be manually recreated as MongoDB aggregation pipeline views or `$lookup` queries
- Query Converter can help convert simple view SQL to pipeline syntax

### Trigger Limitations

- SQL triggers have **no direct MongoDB equivalent**
- Query Converter can attempt DML trigger → Atlas Trigger conversion
- Complex triggers (multi-statement, conditional, cascading) require manual migration
- Pre-migration analysis flags trigger existence but does not analyze trigger logic

### Snapshot Resume

- Stopped snapshot jobs **cannot be resumed** — create a new job
- For very large datasets, plan for uninterrupted migration windows or use table-filter batching to create resumable logical units

### Continuous Sync Limitations

- CDC requires source database prerequisites that may need DBA involvement (ARCHIVELOG, supplemental logging, publication creation)
- Kafka deployment is recommended for production CDC — embedded mode is less resilient
- Schema changes on the source during CDC (DDL) are **not automatically propagated** — RM must be reconfigured and the job restarted
- `ALTER TABLE ADD COLUMN` during CDC requires stopping the job, updating mapping rules, and restarting

### Scale Limitations

- Very large tables (> 100M rows) require performance tuning (parallelism, network proximity, Atlas instance tier)
- Benchmarks available at: https://www.mongodb.com/docs/relational-migrator/benchmarks/
- RM is not designed as a long-term ETL/streaming pipeline — it is a migration tool

### Source-Specific Constraints

- **Oracle PDB (Pluggable Database):** CDC setup commands must run on the CDB root, not the PDB. RM documentation covers this pattern.
- **SQL Server Always On:** CDC works but requires additional configuration for availability group listeners.
- **MySQL GTID replication:** Must be enabled for reliable CDC.
- **PostgreSQL RDS / Aurora:** Logical replication supported with parameter group changes (`rds.logical_replication = 1`).

---

## 11. Troubleshooting Common Failures

### Job Fails at Pre-flight Checks

| Symptom | Likely Cause | Fix |
|---|---|---|
| "Permission denied on table X" | Service account lacks SELECT on that table | Grant `SELECT` or `SELECT ANY TABLE`; re-run Generate Script |
| "CDC not enabled" (SQL Server) | CDC not turned on at DB or table level | Run the Generate Script output as `db_owner`; verify with `sys.databases` |
| "ARCHIVELOG mode not enabled" (Oracle) | DB in NOARCHIVELOG | DBA must enable ARCHIVELOG; requires DB restart |
| "wal_level must be logical" (PostgreSQL) | `postgresql.conf` not updated | Set `wal_level = logical`, restart Postgres; RDS: set `rds.logical_replication = 1` |
| "Driver not found" (Oracle/MySQL) | JDBC driver JAR missing from Drivers folder | Download and copy the correct JAR; restart RM |

### Snapshot Job Fails Mid-Run

| Symptom | Likely Cause | Fix |
|---|---|---|
| Job stops with "OutOfMemory" | Large BLOB/CLOB columns or very wide tables | Exclude large binary columns, or increase RM JVM heap via startup options |
| Specific tables fail, others succeed | Unsupported data types (BFILE, FILESTREAM) | Check error log; exclude affected columns or change BSON type mapping |
| "Duplicate key error" on `_id` | PK collision — multiple source rows map to same `_id` | Review `_id` customization rules; switch to ObjectId generation |
| Job hangs on large table | Network timeout or source DB lock contention | Use table filters to migrate large tables in separate jobs; check source DB for long-running locks |

### CDC Continuous Sync Issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| CDC lag grows continuously | Source change rate exceeds RM throughput | Switch to Kafka deployment mode; scale up RM host |
| "Lost connection to source" | Source DB restarted or network interrupted | Restart RM (Embedded) or wait for auto-recovery (Kafka, up to 24h) |
| Silent data loss or corruption | RM version < 1.14 bug | **Upgrade to 1.14+ immediately** — this is a known critical bug |
| DDL change breaks CDC | `ALTER TABLE` executed on source during sync | Stop job, update mapping rules in RM project, restart job |
| Events stop flowing, no error | Supplemental logging disabled on new table | Re-run Generate Script for Oracle; re-enable publication for PostgreSQL |

### Data Verification Failures

| Symptom | Likely Cause | Fix |
|---|---|---|
| Row count mismatch | Rows filtered by mapping rule filter expression | Verify filter JavaScript expression is correct; check for NULL PK rows skipped |
| Content mismatch on date fields | Timezone conversion difference | Verify BSON Date type mapping; compare raw values, not formatted strings |
| Verification runs longer than migration | Large collection with content comparison enabled | Expected behavior — verification is O(n); plan migration window accordingly |

### Code Generation Issues

| Symptom | Likely Cause | Fix |
|---|---|---|
| Query Converter returns empty output | Query references tables not in project schema | Add all referenced tables to the RM project first |
| Generated Java code won't compile | Package/import mismatch | Customize code generation templates to match project package structure |
| Converted stored procedure logic is wrong | AI conversion limit on complex PL/SQL | Review output carefully; manually rewrite complex cursor logic |

---

## References and See Also

### Official Documentation
- [MongoDB Relational Migrator Docs](https://www.mongodb.com/docs/relational-migrator/)
- [Supported Databases](https://www.mongodb.com/docs/relational-migrator/supported-databases/)
- [Data Modeling / Mapping Rules](https://www.mongodb.com/docs/relational-migrator/mapping-rules/introduction/)
- [Schema Mapping](https://www.mongodb.com/docs/relational-migrator/mapping-rules/schema-mapping/)
- [Embedded Documents](https://www.mongodb.com/docs/relational-migrator/mapping-rules/mapping-rule-options/embedded-documents/)
- [Embedded Array](https://www.mongodb.com/docs/relational-migrator/mapping-rules/mapping-rule-options/embedded-array/)
- [Calculated Fields](https://www.mongodb.com/docs/relational-migrator/mapping-rules/fields/calculated-fields/calculated-fields/)
- [Synthetic Foreign Keys](https://www.mongodb.com/docs/relational-migrator/mapping-rules/synthetic-foreign-key/)
- [Pre-Migration Analysis](https://www.mongodb.com/docs/relational-migrator/app-analysis/)
- [Migration Risk Reference](https://www.mongodb.com/docs/relational-migrator/app-analysis/risk-reference/)
- [Data Migration Jobs](https://www.mongodb.com/docs/relational-migrator/jobs/sync-jobs/)
- [Monitor a Migration Job](https://www.mongodb.com/docs/relational-migrator/jobs/monitoring-jobs/)
- [Recover a Migration Job](https://www.mongodb.com/docs/relational-migrator/jobs/recover-jobs/)
- [Data Verification](https://www.mongodb.com/docs/relational-migrator/jobs/data-verification/)
- [Code Generation](https://www.mongodb.com/docs/relational-migrator/code-generation/)
- [Query Converter](https://www.mongodb.com/docs/relational-migrator/code-generation/query-converter/)
- [Data Type Conversion Reference](https://www.mongodb.com/docs/relational-migrator/mapping-rules/fields/data-type-conversion-guide/)
- [Migration Benchmarks](https://www.mongodb.com/docs/relational-migrator/benchmarks/)
- [Kafka Deployment](https://www.mongodb.com/docs/relational-migrator/installation/kafka-deployments/migrator-with-kafka/)
- [Release Notes](https://www.mongodb.com/docs/relational-migrator/release-notes/)

### Blog / Guides
- [Announcing MongoDB Relational Migrator](https://www.mongodb.com/company/blog/product-release-announcements/announcing-mongodb-relational-migrator)
- [AI-Powered SQL Query Converter](https://www.mongodb.com/company/blog/product-release-announcements/ai-powered-sql-query-converter-tool-now-available-relational-migrator)
- [Automated Risk Analysis](https://www.mongodb.com/company/blog/product-release-announcements/introducing-automated-risk-analysis-in-relational-migrator)
- [3 Pitfalls: PostgreSQL to MongoDB](https://medium.com/mongodb/3-pitfalls-to-avoid-when-migrating-postgresql-to-mongodb-f40ef2f7cf15)
- [Migrate to MongoDB Atlas on AWS](https://www.mongodb.com/resources/products/tools/migrate-mongodb-atlas-aws-relational-migrator)
- [AWS Prescriptive Guidance — Relational Migrator](https://docs.aws.amazon.com/prescriptive-guidance/latest/migration-mongodb-atlas/relational-migrator.html)
- [Building Spring Boot App with Relational Migrator](https://dev.to/mongodb/building-a-spring-boot-crud-application-using-mongodbs-relational-migrator-59kf)

### Related Skills
- [[mongodb-migration-patterns]] — broader migration tooling (mongosync, Atlas Live Migration, cutover strategies)
- [[mongodb-schema-design]] — MongoDB schema design patterns, embedding vs referencing, anti-patterns
- [[mongodb-mongosync]] — mongosync deep reference (MongoDB-to-MongoDB sync)
