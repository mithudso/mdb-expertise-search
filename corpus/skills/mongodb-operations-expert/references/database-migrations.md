<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `database-migrations` skill.
> Sibling topics in this family are now reference files under the hubs (`mongodb-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not** standalone
> skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that name a bare sibling
> skill; load that topic's `references/<name>.md` from the owning hub (see the hub's "Cross-hub map").

---

---
name: database-migrations
title: "Database Migration Patterns"
description: >
  Database migration expert for safe schema and data migrations in production.
  TRIGGER: user asks about rename/drop/modify column without downtime, expand-contract pattern,
  backfill strategy, schema migration tool selection (Flyway, Liquibase, Prisma Migrate, Atlas,
  goose, golang-migrate), online schema change (gh-ost, pt-online-schema-change, pgroll),
  MongoDB document schema versioning, migration rollback, migration locking in multi-node deploys,
  blue-green database deployment, or reviewing a migration script for safety.
  SKIP: greenfield schema design with no existing data to migrate (use mongodb-expert);
  query optimization on an existing schema (use mongodb-expert, or atlas-diagnostics-expert for live clusters);
  CDC architecture for streaming as an operational pipeline (use mongodb-operations-expert).
category: developer
version: 1.1.1
updated: "2026-05-31"
tags:
  - database
  - migration
  - schema
  - zero-downtime
  - devops
  - mongodb
  - postgresql
  - mysql
keywords:
  - database migration
  - schema migration
  - zero-downtime migration
  - expand-contract pattern
  - backfill strategy
  - rollback pattern
  - schema versioning
  - Flyway
  - Liquibase
  - Prisma Migrate
  - Atlas
  - golang-migrate
  - gh-ost
  - pt-online-schema-change
  - pgroll
  - MongoDB schema evolution
  - blue-green database deployment
  - data migration pipeline
  - online schema change
  - CDC change data capture
  - migration lock
whenToUse:
  - Planning or executing database schema changes in production
  - Implementing zero-downtime migration strategies
  - Choosing a database migration tool (Flyway, Liquibase, Prisma, Atlas, goose, golang-migrate)
  - Designing expand-contract migration workflows
  - Building backfill pipelines for large-scale data migration
  - Planning rollback strategies for schema changes
  - Migrating MongoDB document schemas with versioning
  - Setting up blue-green database deployments
  - Reviewing migration code for safety and anti-patterns
  - Testing database migrations before production deployment
  - Comparing online schema change tools (gh-ost, pt-online-schema-change, pgroll)
  - Coordinating migration execution across multiple application nodes
whenNotToUse:
  - Designing a new schema from scratch with no existing data (use mongodb-expert)
  - Tuning slow queries on an existing schema (use mongodb-expert, or atlas-diagnostics-expert for live clusters)
  - Setting up CDC streaming pipelines for operational use (use mongodb-operations-expert)
  - Backing up or restoring a database (use mongodb-operations-expert)
related_skills:
  - mongodb-expert
  - devops-infra
  - software-engineering-patterns
  - mongodb-operations-expert
---

# Database Migration Patterns

Expert reference for database schema migration strategies, zero-downtime patterns, tooling, MongoDB-specific migration, testing, and production safety. A response from this skill is correct when it identifies the right migration category, recommends a backward-compatible sequencing, and flags any dangerous operations before they are executed.

> **Staleness note:** Tool-specific details (license terms, version numbers, feature availability) were current as of May 2026. Verify against current documentation before committing to a tool choice.

**Navigation:** Consult sections by task:
- Choosing a migration approach → §1–2 (strategy, zero-downtime patterns)
- Backfilling large datasets → §3
- Rollback planning → §4
- Versioning scheme selection → §5
- Picking a migration tool → §6 (matrix + decision tree); deep-dive CLI in `references/migration-tools.md`
- Online schema changes for MySQL/PostgreSQL → §7
- MongoDB document schema migration → §8
- Blue-green deployments → §9
- Testing and linting migrations → §10
- Multi-node locking and coordination → §11
- CDC pipelines → §12
- Anti-patterns and dangerous operations → §13
- Production runbook (pre/during/post steps) → §14
- Advanced patterns (strangler fig, canary, state machine) → §15

---

## 1. Migration Strategy Overview

### 1.1 What Is a Database Migration?

A database migration is a versioned, ordered change to a database structure (schema) or its data. Each migration has an "up" operation (apply the change) and optionally a "down" operation (revert). A migration tool tracks which migrations have been applied so each runs exactly once.

### 1.2 Migration Categories

| Category | Description | Risk Level |
|----------|-------------|------------|
| **Schema-only** | DDL changes: add/drop columns, indexes, constraints, tables | Medium |
| **Data-only** | DML changes: backfill, transform, move data between tables | High |
| **Combined** | Schema + data in coordinated steps | Very High |
| **Structural** | Table renames, column type changes, constraint changes | Critical |

### 1.3 Forward-Only vs Reversible Migrations

**Forward-only (recommended for production):**
- Treat migrations as immutable, append-only history
- If a release fails, deploy a new compensating migration
- Avoids the complexity of maintaining reliable down scripts
- Aligns with GitOps and infrastructure-as-code principles

**Reversible (useful for development):**
- Each migration includes both up and down scripts
- Down scripts are tested before production deploy
- Not all operations are safely reversible (data loss on column drop)
- Tools like Atlas compute rollbacks automatically from schema diff

---

## 2. Zero-Downtime Migration Patterns

### 2.1 The Golden Rule

> Every migration must be backward compatible with the currently running application code. The migration completes while the old version is still running. Only after the migration finishes should you deploy the new application code.

### 2.2 The Expand-Contract Pattern (Parallel Change)

The most important pattern for zero-downtime schema changes. Never remove or rename something in place -- instead, add the new structure first, transition the application, then remove the old structure.

**Phase 1 -- Expand:**
- Add new columns, tables, or indexes without removing anything
- Old application code continues working because nothing it depends on has changed
- New columns are nullable or have defaults

**Phase 2 -- Migrate:**
- Deploy application code that dual-writes to both old and new structures
- Backfill existing data from old to new structure in batches
- Validate data consistency between old and new

**Phase 3 -- Contract:**
- Deploy application code that reads only from new structure
- Remove old columns, tables, or indexes
- Apply final constraints (NOT NULL, unique, etc.)

**Each phase is a separate deployment.** This allows independent rollback of any phase.

### 2.3 Expand-Contract: Column Rename Example

```sql
-- Phase 1: Expand (Deploy 1)
ALTER TABLE users ADD COLUMN full_name TEXT;

-- Phase 2: Migrate (Deploy 2 -- application dual-writes)
-- Backfill in batches:
UPDATE users SET full_name = name
WHERE full_name IS NULL AND id BETWEEN 1 AND 10000;
-- Repeat for all ID ranges

-- Phase 3: Contract (Deploy 3 -- application reads full_name only)
ALTER TABLE users ALTER COLUMN full_name SET NOT NULL;
ALTER TABLE users DROP COLUMN name;
```

### 2.4 Expand-Contract: Column Type Change Example

```sql
-- Phase 1: Add new column with correct type
ALTER TABLE orders ADD COLUMN total_v2 NUMERIC(12,2);

-- Phase 2: Application dual-writes to both columns
-- Backfill:
UPDATE orders SET total_v2 = CAST(total AS NUMERIC(12,2))
WHERE total_v2 IS NULL AND id BETWEEN ? AND ?;

-- Phase 3: Switch reads, drop old column
ALTER TABLE orders DROP COLUMN total;
ALTER TABLE orders RENAME COLUMN total_v2 TO total;
```

### 2.5 Adding a NOT NULL Column Safely

```sql
-- Step 1: Add nullable column
ALTER TABLE users ADD COLUMN email TEXT;

-- Step 2: Deploy code that writes email for all new rows

-- Step 3: Backfill in batches
UPDATE users SET email = 'unknown@placeholder.com'
WHERE email IS NULL AND id BETWEEN ? AND ?;

-- Step 4: Add constraint
ALTER TABLE users ALTER COLUMN email SET NOT NULL;
```

### 2.6 Safe Index Creation

**PostgreSQL:**
```sql
-- ALWAYS use CONCURRENTLY for production indexes
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);

-- Never do this in production:
-- CREATE INDEX idx_users_email ON users(email);  -- LOCKS TABLE
```

**MySQL:**
```sql
-- Use ALGORITHM=INPLACE when available
ALTER TABLE users ADD INDEX idx_email (email), ALGORITHM=INPLACE, LOCK=NONE;

-- For large tables, prefer external tools:
-- gh-ost or pt-online-schema-change
```

**MongoDB:**
```javascript
// Use background option (default in 4.2+, but explicit is clearer)
db.users.createIndex({ email: 1 }, { background: true });

// For Atlas: indexes build on secondaries first, then primary
// Monitor with db.currentOp({ "command.createIndexes": { $exists: true } })
```

### 2.7 Table/Collection Rename Pattern

Direct renames cause downtime. Instead:

1. Create new table/collection with desired name
2. Set up dual-write in application layer
3. Backfill historical data from old to new
4. Switch reads to new table/collection
5. Stop writes to old table/collection
6. Drop old table/collection after cooling period

---

## 3. Backfill Strategies

### 3.1 Batch-Based Backfill

The standard approach for large-scale data backfills.

```python
# Python pseudocode for batched backfill
BATCH_SIZE = 5000
last_id = 0

while True:
    rows = db.execute("""
        UPDATE users SET full_name = name
        WHERE full_name IS NULL
          AND id > %s
        ORDER BY id
        LIMIT %s
        RETURNING id
    """, [last_id, BATCH_SIZE])

    if not rows:
        break

    last_id = rows[-1].id
    time.sleep(0.1)  # Throttle to avoid overloading
    log(f"Backfilled up to id={last_id}")
```

**Key principles:**
- Use primary key ranges, not OFFSET (which rescans)
- Keep batch sizes small enough to avoid long-running transactions
- Add sleep/throttle between batches to let production queries breathe
- Log progress for observability
- Make backfill idempotent (safe to re-run)

### 3.2 Dual-Write + Backfill

1. Deploy application code that writes to both old and new columns/tables
2. Run backfill to catch up historical data
3. Verify consistency: `SELECT COUNT(*) WHERE old_col != new_col`
4. Switch reads to new column/table
5. Remove dual-write code

### 3.3 CDC-Based Backfill (Change Data Capture)

For very large datasets where batch UPDATE is impractical:

1. Start CDC stream (Debezium, MongoDB Change Streams, PostgreSQL logical replication)
2. Take a consistent snapshot of existing data
3. Apply snapshot to new structure
4. Apply buffered CDC events that occurred during snapshot
5. Continue applying CDC events until caught up
6. Cut over reads to new structure

**MongoDB Change Streams for CDC:**
```javascript
const pipeline = [{ $match: { operationType: { $in: ['insert', 'update'] } } }];
const changeStream = db.collection('users').watch(pipeline, {
  fullDocument: 'updateLookup',
  startAtOperationTime: snapshotTimestamp
});

changeStream.on('change', (change) => {
  const transformed = transformDocument(change.fullDocument);
  db.collection('users_v2').replaceOne(
    { _id: transformed._id },
    transformed,
    { upsert: true }
  );
});
```

### 3.4 Shadow Table / Ghost Table Pattern

Used by online schema change tools (gh-ost, pt-online-schema-change):

1. Create a shadow table with the new schema
2. Copy data from original to shadow in chunks
3. Capture ongoing changes (via triggers or binlog)
4. Apply captured changes to shadow table
5. Atomic rename: swap shadow and original table names
6. Drop old table after verification

### 3.5 Backfill Performance Guidelines

| Factor | Recommendation |
|--------|---------------|
| Batch size | 1,000-10,000 rows per batch |
| Throttle delay | 50-200ms between batches |
| Transaction scope | One batch = one transaction |
| Progress tracking | Persist last-processed ID for restartability |
| Monitoring | Track rows/sec, replication lag, lock waits |
| Off-peak execution | Schedule during low-traffic windows |
| Idempotency | Always use upsert or conditional updates |

---

## 4. Rollback Patterns

### 4.1 Why Rollbacks Are Hard

Rolling back database changes is fundamentally different from rolling back application code:
- Data may have been written using the new schema
- Dropped columns lose data permanently
- Type conversions can be lossy
- Constraints may have rejected data that now needs re-processing
- Other systems may have consumed data in the new format

### 4.2 Rollback Strategy Hierarchy

**Tier 1 -- No rollback needed (additive changes):**
- Adding a nullable column
- Adding an index (CONCURRENTLY)
- Adding a new table/collection
- Adding a new constraint with NOT VALID

**Tier 2 -- Simple rollback (removal):**
- Drop newly added column
- Drop newly added index
- Drop newly added table

**Tier 3 -- Compensating migration (forward fix):**
- Deploy a new migration that reverses the effect
- Preferred over down migrations in production
- Works with forward-only migration strategies

**Tier 4 -- Point-in-time recovery (last resort):**
- Restore from backup to a point before the migration
- Loses all data written after the migration
- Only for catastrophic failures

### 4.3 Feature Flags as Rollback

Use feature flags as a rapid rollback mechanism:

```typescript
async function getUser(id: string) {
  if (featureFlags.isEnabled('use_new_email_column')) {
    return db.query('SELECT email_v2 AS email FROM users WHERE id = $1', [id]);
  }
  return db.query('SELECT email FROM users WHERE id = $1', [id]);
}
```

Benefits: instant rollback (no deployment), gradual rollout, decouples schema change from app behavior change.

### 4.4 Rollback Testing Checklist

- [ ] Rollback script exists and is version-controlled
- [ ] Rollback tested on a production-like dataset
- [ ] Rollback preserves data written during the migration window
- [ ] Rollback duration estimated and documented
- [ ] Dependent services identified and notified
- [ ] Monitoring dashboards updated to detect rollback state

---

## 5. Schema Versioning Schemes

### 5.1 Sequential Integer Versioning

```
V001__create_users_table.sql
V002__add_email_column.sql
V003__create_orders_table.sql
```

Used by: Flyway, golang-migrate, goose

**Pros:** Simple, ordered, easy to reason about
**Cons:** Merge conflicts when two developers create V004 simultaneously

### 5.2 Timestamp-Based Versioning

```
20260526120000_create_users_table.sql
20260526120100_add_email_column.sql
20260526130000_create_orders_table.sql
```

Used by: Rails ActiveRecord, Prisma Migrate, golang-migrate (optional)

**Pros:** No merge conflicts, natural ordering
**Cons:** Less readable than sequential numbers

### 5.3 Declarative / Desired-State Versioning

Define the desired end-state schema; the tool computes the diff:

```hcl
# Atlas HCL schema
schema "public" {
  table "users" {
    column "id"    { type = int }
    column "email" { type = varchar(255) }
    index "idx_email" { columns = [column.email] }
  }
}
```

Used by: Atlas, Prisma, Liquibase (partial)

**Pros:** Single source of truth, computed rollbacks, drift detection
**Cons:** Less control over HOW changes are applied

### 5.4 Changelog-Based Versioning

```xml
<!-- Liquibase changelog -->
<databaseChangeLog>
  <changeSet id="1" author="dev">
    <createTable tableName="users">
      <column name="id" type="int" autoIncrement="true">
        <constraints primaryKey="true"/>
      </column>
      <column name="email" type="varchar(255)"/>
    </createTable>
  </changeSet>
</databaseChangeLog>
```

Used by: Liquibase

**Pros:** Database-agnostic abstraction, built-in rollback generation
**Cons:** Verbose, abstraction leaks for complex operations

### 5.5 Document-Level Versioning (MongoDB)

```javascript
{
  _id: ObjectId("..."),
  schemaVersion: 2,
  fullName: "Jane Doe",
  email: "jane@example.com"
}
```

The application handles multiple versions simultaneously. See Section 8 for full MongoDB patterns.

---

## 6. Migration Tool Comparison

### 6.1 Tool Matrix

| Feature | Flyway | Liquibase | Prisma Migrate | Atlas | goose | golang-migrate |
|---------|--------|-----------|----------------|-------|-------|----------------|
| **Language** | Java | Java | Node.js/TS | Go | Go | Go |
| **Approach** | Versioned SQL | Changelog (XML/YAML/SQL) | Declarative schema | Declarative (HCL/SQL/ORM) | Versioned SQL/Go | Versioned SQL |
| **Rollback** | Paid tier only | Built-in auto | Manual (new migration) | Computed from diff | Built-in down | Built-in down |
| **Drift Detection** | Yes | Yes | Yes | Yes | No | No |
| **CI/CD Lint** | Paid advisors | Preconditions | Warnings on data loss | `atlas migrate lint` | No | No |
| **Multi-DB** | 20+ DBs | 50+ DBs | PostgreSQL, MySQL, SQLite, SQL Server, MongoDB | PostgreSQL, MySQL, MariaDB, SQLite, SQL Server | 15+ DBs | 20+ DBs |
| **License** | Apache 2 / Proprietary | FSL (was Apache 2) | Apache 2 | Apache 2 | MIT | MIT |
| **MongoDB Support** | No | Yes (via extension) | Yes (Prisma + MongoDB) | No | No | Yes (community) |

> Full tool deep-dives (CLI examples, key flags, version notes): see `references/migration-tools.md`.

### 6.2 Tool Selection Decision Tree

```
Start
  |
  +-- Java/JVM project?
  |     +-- Single DB vendor? --> Flyway
  |     +-- Multi DB vendor?  --> Liquibase
  |
  +-- Node.js/TypeScript?
  |     +-- Using Prisma ORM? --> Prisma Migrate
  |     +-- Not using Prisma? --> Atlas or node-pg-migrate
  |
  +-- Go project?
  |     +-- Want minimal tooling?     --> goose
  |     +-- Want library embedding?   --> golang-migrate
  |     +-- Want declarative + lint?  --> Atlas
  |
  +-- Python project?
  |     +-- Using SQLAlchemy? --> Alembic
  |     +-- Using Django?     --> Django Migrations
  |
  +-- Multiple languages / declarative preference?
        +--> Atlas (language-agnostic, schema-as-code)
```

---

## 7. Online Schema Change Tools

### 7.1 The Problem

Standard ALTER TABLE on large MySQL tables acquires metadata locks that block reads and writes. Even PostgreSQL's ALTER TABLE for certain operations (adding NOT NULL, changing types) can require full table rewrites and exclusive locks.

### 7.2 Online Schema Change Comparison

| Feature | gh-ost | pt-osc | pgroll |
|---------|--------|--------|--------|
| Database | MySQL | MySQL | PostgreSQL |
| Mechanism | Binlog | Triggers | Schema versioning |
| Pausable | Yes | No | Yes |
| Testable (dry-run) | Yes | Limited | No |
| Concurrent DML | Yes | Yes | Yes |
| Foreign keys | Limited | Limited | Yes |

> Full CLI examples and flags for each tool: see `references/migration-tools.md`.

### 7.3 pgroll: Serving Multiple Schema Versions

pgroll is the primary zero-downtime option for PostgreSQL large-table changes. During a migration, both old and new schema versions are accessible via different PostgreSQL schemas, enabling true zero-downtime contract changes.

```bash
pgroll start migration.json
pgroll complete    # or pgroll rollback
```

### 7.4 Reshape (PostgreSQL)

Reshape is an independent PostgreSQL project that uses a similar expand-contract approach with temporary views:

1. Creates new columns/tables with desired schema
2. Adds views that present the old schema using new storage
3. Backfills data lazily
4. On completion, drops views and old columns

> Note: Reshape and pgroll are separate projects by different organizations. Both provide online schema changes for PostgreSQL using expand-contract semantics, but they are not related.

---

## 8. MongoDB-Specific Migration Patterns

### 8.1 Schema Versioning Pattern

MongoDB's flexible document model allows documents with different structures to coexist in the same collection. The Schema Versioning Pattern adds a `schemaVersion` field to track document structure.

```javascript
// Version 1 document
{
  _id: ObjectId("..."),
  schemaVersion: 1,
  firstName: "Jane",
  lastName: "Doe",
  phone: "555-1234"
}

// Version 2 document (same collection)
{
  _id: ObjectId("..."),
  schemaVersion: 2,
  fullName: "John Smith",
  phones: ["555-5678"],
  email: "john@example.com"
}
```

### 8.2 Application-Layer Version Handling

```javascript
class UserRepository {
  async getUser(id) {
    const doc = await db.collection('users').findOne({ _id: id });
    return this._normalize(doc);
  }

  _normalize(doc) {
    switch (doc.schemaVersion) {
      case 1:
        return {
          ...doc,
          fullName: `${doc.firstName} ${doc.lastName}`,
          phones: doc.phone ? [doc.phone] : [],
          email: doc.email || null,
          schemaVersion: 2
        };
      case 2:
        return doc;
      default:
        throw new Error(`Unknown schema version: ${doc.schemaVersion}`);
    }
  }

  async saveUser(user) {
    user.schemaVersion = 2;
    await db.collection('users').replaceOne(
      { _id: user._id },
      user,
      { upsert: true }
    );
  }
}
```

### 8.3 Eager vs Lazy Migration Strategies

**Eager Migration:**
- Run a batch job to update all documents to the latest version at once
- Pros: Clean data, simpler application code
- Cons: Long-running operation, I/O intensive, may impact performance
- Best for: Collections under ~10M documents, scheduled maintenance windows

**Medium collections (10M–100M documents):** Use batched eager migration with aggressive throttling (50ms delay between batches, batch size 500–1,000) and schedule during off-peak hours. Monitor oplog lag — if replication lag exceeds 10s, pause and let replicas catch up before resuming.

```javascript
const BATCH_SIZE = 1000;
let processed = 0;

const cursor = db.collection('users').find({ schemaVersion: 1 }).batchSize(BATCH_SIZE);
const bulk = db.collection('users').initializeUnorderedBulkOp();
let count = 0;

while (await cursor.hasNext()) {
  const doc = await cursor.next();
  bulk.find({ _id: doc._id }).updateOne({
    $set: {
      schemaVersion: 2,
      fullName: `${doc.firstName} ${doc.lastName}`,
      phones: doc.phone ? [doc.phone] : []
    },
    $unset: { firstName: "", lastName: "", phone: "" }
  });

  count++;
  if (count >= BATCH_SIZE) {
    await bulk.execute();
    processed += count;
    count = 0;
    console.log(`Migrated ${processed} documents`);
  }
}

if (count > 0) await bulk.execute();
```

**Lazy Migration:**
- Documents are migrated when read (read-modify-write on access)
- Pros: No batch operation needed, spreads load over time
- Cons: Application must handle all versions indefinitely, read-then-write overhead
- Best for: Collections over 100M documents, always-on systems, gradual rollout

```javascript
async function getUser(id) {
  const doc = await db.collection('users').findOne({ _id: id });
  if (doc.schemaVersion < CURRENT_VERSION) {
    const migrated = migrateToLatest(doc);
    await db.collection('users').replaceOne({ _id: id }, migrated);
    return migrated;
  }
  return doc;
}
```

### 8.4 MongoDB $jsonSchema Validation Evolution

```javascript
// During migration: warn but don't reject
db.runCommand({
  collMod: 'users',
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['schemaVersion'],
      properties: {
        schemaVersion: { bsonType: 'int', minimum: 1 }
      }
    }
  },
  validationLevel: 'moderate',
  validationAction: 'warn'
});

// After migration complete: tighten validation
db.runCommand({
  collMod: 'users',
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['schemaVersion', 'fullName', 'email'],
      properties: {
        schemaVersion: { bsonType: 'int', enum: [2] },
        fullName: { bsonType: 'string' },
        email: { bsonType: 'string' },
        phones: { bsonType: 'array', items: { bsonType: 'string' } }
      }
    }
  },
  validationLevel: 'strict',
  validationAction: 'error'
});
```

### 8.5 MongoDB Aggregation Pipeline for Migrations

```javascript
db.collection('users').aggregate([
  { $match: { schemaVersion: 1 } },
  { $addFields: {
    schemaVersion: 2,
    fullName: { $concat: ['$firstName', ' ', '$lastName'] },
    phones: { $cond: {
      if: { $ifNull: ['$phone', false] },
      then: ['$phone'],
      else: []
    }}
  }},
  { $unset: ['firstName', 'lastName', 'phone'] },
  { $merge: {
    into: 'users',
    on: '_id',
    whenMatched: 'replace',
    whenNotMatched: 'discard'
  }}
]);
```

### 8.6 MongoDB Index Migration Safety

```javascript
// Build unique index safely -- check for duplicates first
db.users.aggregate([
  { $group: { _id: '$email', count: { $sum: 1 } } },
  { $match: { count: { $gt: 1 } } }
]);
// Fix duplicates, then:
db.users.createIndex({ email: 1 }, { unique: true, name: 'idx_email_unique' });

// Monitor index builds:
db.currentOp({ 'command.createIndexes': { $exists: true } });

// Drop unused indexes (check with $indexStats first):
db.users.aggregate([{ $indexStats: {} }]);
```

### 8.7 MongoDB Atlas Live Migration

Atlas provides built-in live migration for moving data between self-managed MongoDB, Atlas clusters, or community editions. The process uses oplog tailing:

1. Initial sync copies all data
2. Continuous oplog tailing captures changes during migration
3. Cutover switches the application connection string
4. DNS propagation completes the transition

> MongoDB-specific tools (Mongock for Java, migrate-mongo for Node.js): see `references/migration-tools.md`.

---

## 9. Blue-Green Database Deployments

### 9.1 Core Concept

Maintain two environments (blue = active, green = standby). Update the inactive environment first, test, then switch traffic.

### 9.2 Shared-Database Blue-Green

Most common pattern: both environments share the same database. Schema changes must be backward-compatible.

```
Traffic --> [Load Balancer]
                |
        +-------+-------+
        |               |
    [Blue App v1]   [Green App v2]
        |               |
        +-------+-------+
                |
          [Shared DB]
```

**Deployment sequence:**
1. Run backward-compatible migration on shared DB
2. Deploy new app code to green environment
3. Run smoke tests against green
4. Switch load balancer from blue to green
5. Monitor; if issues, switch back to blue (migration was backward-compatible)
6. Run contract migration to clean up old schema elements

### 9.3 Dual-Database Blue-Green

For maximum isolation: each environment has its own database. Requires CDC-based data synchronization between blue and green during the transition window.

**AWS RDS Blue/Green Deployments** (MySQL, MariaDB, Aurora): creates a staging environment mirroring production, uses logical replication, and supports atomic switchover.

---

## 10. Testing Database Migrations

> **See also:** Section 14 (Production Migration Runbook) for the pre/during/post execution checklist. This section covers how to validate a migration before running it; Section 14 covers what to do when running it.

### 10.1 Pre-Deployment Testing Checklist

- [ ] Migration runs successfully on empty database (fresh install path)
- [ ] Migration runs successfully on production-like database (upgrade path)
- [ ] Migration completes within acceptable time window
- [ ] Rollback script runs successfully
- [ ] Application works with both pre- and post-migration schema (backward compatibility)
- [ ] Indexes created CONCURRENTLY where applicable
- [ ] No full table locks on large tables
- [ ] Batch sizes tested with realistic data volumes
- [ ] Replication lag monitored during migration test
- [ ] Data integrity verified after migration (row counts, checksums)

### 10.2 Testing with Realistic Data Volumes

```bash
# A migration that takes 2 seconds on dev may take 2 hours in production

# PostgreSQL: dump production schema + anonymized data
pg_dump --schema-only prod_db > schema.sql
pg_dump --data-only --table=users prod_db | \
  sed 's/real@email.com/test@test.com/g' > data.sql

# MongoDB: mongodump with query filter for subset
mongodump --uri="mongodb://prod" --db=mydb \
  --query='{"createdAt": {"$gt": {"$date": "2026-01-01"}}}' \
  --out=/tmp/test-data
```

### 10.3 Migration Linting

**Squawk (PostgreSQL):**
```bash
squawk migration.sql
# Detects: adding-not-nullable-field, adding-serial-primary-key, ban-drop-column
```

**Atlas Lint:**
```bash
atlas migrate lint --dev-url "docker://postgres/15"
# Detects: destructive changes, data-dependent changes, missing concurrent index creation
```

### 10.4 CI/CD Integration

```yaml
name: Migration Safety Check
on: [pull_request]
jobs:
  lint-migrations:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - name: Install Atlas
        run: curl -sSf https://atlasgo.sh | sh
      - name: Lint migrations
        run: |
          atlas migrate lint \
            --dev-url "postgres://postgres:test@localhost:5432/test?sslmode=disable" \
            --dir "file://migrations" \
            --latest 1
      - name: Dry-run migration
        run: |
          atlas migrate apply \
            --url "postgres://postgres:test@localhost:5432/test?sslmode=disable" \
            --dir "file://migrations" \
            --dry-run
```

---

## 11. Migration Locking and Coordination

Multi-node deployments create a race: multiple application instances can start up simultaneously and all attempt to run migrations.

### 11.1 Tool-Level Locking

Most migration tools acquire a DB-level advisory lock automatically:

| Tool | Lock mechanism |
|------|---------------|
| Flyway | PostgreSQL advisory lock; MySQL metadata lock on schema history table |
| Liquibase | `DATABASECHANGELOGLOCK` table row lock |
| Atlas | Advisory lock on a dedicated lock record |
| goose | `goose_db_version` table exclusive row lock |
| golang-migrate | Advisory lock (PostgreSQL); table lock (others) |

**Rule:** Only one process should run migrations on startup. Gate migration execution with the tool's built-in lock. Do not roll your own.

### 11.2 Startup Sequencing Patterns

**Pattern A: Run-once init container (Kubernetes preferred)**
```yaml
initContainers:
  - name: migrate
    image: myapp:v1.2.3
    command: ["./migrate", "up"]
    env:
      - name: DATABASE_URL
        valueFrom: { secretKeyRef: { name: db-secret, key: url } }
containers:
  - name: app
    image: myapp:v1.2.3
```
The init container exits 0 before any app replica starts. Kubernetes ensures this runs exactly once per rollout.

**Pattern B: Leader election before migration**

When init containers are not available, have each node attempt to acquire a distributed lock (Redis, DynamoDB, or the DB advisory lock) and only the winner runs migrations. Losers wait then poll for completion.

**Pattern C: Decouple migration from deployment**

Run `migrate up` as a separate CI/CD step before the rolling deploy begins. App pods start only after the migration job completes successfully. This is the safest pattern for blue-green and rolling deployments.

### 11.3 What Happens When a Migration Fails Mid-Run

- All tools wrap each migration in a transaction where the DB supports transactional DDL (PostgreSQL, SQL Server).
- MySQL/MariaDB do not support transactional DDL for most ALTER TABLE operations -- partial migrations can leave the table in an intermediate state. Always back up before running large ALTER TABLE operations on MySQL.
- MongoDB has no concept of transactional DDL; each aggregation pipeline operation is atomic per-document but not across the full collection.

---

## 12. Data Migration Pipelines

### 12.1 ETL vs ELT for Migrations

**ETL (Extract-Transform-Load):** Transform before writing. Better for complex transformations, higher memory usage.

**ELT (Extract-Load-Transform):** Load raw data first, transform in destination DB. Uses destination DB compute, better for large datasets with simple transformations.

### 12.2 CDC-Based Migration Pipeline

```
[Source Database]
    |
    +-- [Debezium / Change Streams / Logical Replication]
    |
    +-- [Kafka / Event Stream]
    |
    +-- [Consumer / Transformer]
    |
    +-- [Destination Database]
    |
[Lag Monitor]
    +-- Alert if lag > threshold
```

**Tools:**
- **Debezium:** CDC for MySQL, PostgreSQL, MongoDB, SQL Server, Oracle
- **MongoDB Change Streams:** Native CDC for MongoDB replica sets and sharded clusters
- **PostgreSQL Logical Replication:** Built-in CDC for PostgreSQL 10+
- **AWS DMS:** Managed migration service supporting 20+ source/target combinations

---

## 13. Anti-Patterns and Common Mistakes

### 13.1 Dangerous Operations

| Operation | Why It's Dangerous | Safe Alternative |
|-----------|-------------------|------------------|
| `ALTER TABLE ... ADD COLUMN ... NOT NULL` | Full table rewrite + lock | Add nullable, backfill, then add constraint |
| `ALTER TABLE ... ALTER COLUMN TYPE` | Full table rewrite | Add new column, dual-write, backfill, switch |
| `CREATE INDEX ...` (without CONCURRENTLY) | Locks table for duration | `CREATE INDEX CONCURRENTLY` (PostgreSQL) |
| `ALTER TABLE ... RENAME COLUMN` | Breaks running application | Expand-contract over multiple deploys |
| `DROP TABLE / DROP COLUMN` | Irreversible data loss | Rename to `_deprecated_*`, drop after cooling period |
| `TRUNCATE TABLE` in migration | Data loss | Never in production migrations |

### 13.2 Migration Anti-Patterns

1. **Big Bang Migration:** Running all schema + data changes in one transaction
   Fix: Break into small, independent, backward-compatible steps

2. **Testing with Toy Data:** Migration works on dev with 100 rows, fails on prod with 10M rows
   Fix: Always test with production-scale data volumes

3. **Missing Rollback Plan:** No documented way to undo a migration
   Fix: Every migration has a tested rollback procedure

4. **Coupling Schema and Application Deploys:** Deploying schema change and application code simultaneously
   Fix: Schema change first (backward-compatible), then application deploy

5. **Ignoring Replication Lag:** Migration overwhelms replicas, causing read failures
   Fix: Monitor replica lag, throttle migration batch rate

6. **Lock Escalation:** Single long-running UPDATE locks the entire table
   Fix: Batch updates with small transaction scopes

7. **Non-Idempotent Migrations:** Migration fails halfway and cannot be safely re-run
   Fix: Use IF NOT EXISTS, ON CONFLICT, upsert semantics

8. **Shared State in Migration Scripts:** Migration depends on application config or environment
   Fix: Migrations should be self-contained SQL/scripts

9. **Skipping Validation Post-Migration:** Assuming migration succeeded without verification
   Fix: Automated row counts, checksum comparison, constraint validation

10. **Manual Production Migrations:** Running migrations by hand instead of through CI/CD
    Fix: Automate migration execution in deployment pipeline

11. **Multiple Nodes Racing to Migrate:** App instances all run migrations on startup without locking
    Fix: Use init container, leader election, or decouple migration from deployment (Section 11)

### 13.3 MongoDB-Specific Anti-Patterns

1. **Unbounded Array Growth in Migrations:** Fix: Use the bucket pattern or cap array sizes
2. **No schemaVersion Field:** Fix: Always include `schemaVersion` in documents
3. **Eager Migration on Massive Collections:** Fix: Use lazy migration or batched eager migration with throttling
4. **Dropping Fields Before Application Update:** Fix: Update application to handle missing fields first
5. **Ignoring Write Concern During Migration:** Fix: Use `{ writeConcern: { w: "majority" } }` for migration operations

---

## 14. Production Migration Runbook

### 14.1 Pre-Migration

1. Review migration script with team (code review)
2. Run migration lint (Squawk, Atlas lint, or equivalent)
3. Test on staging with production-scale data
4. Estimate migration duration
5. Document rollback procedure and test it
6. Notify stakeholders (on-call, SRE, dependent teams)
7. Verify backup is recent and restorable
8. Check maintenance window or confirm zero-downtime compatibility

### 14.2 During Migration

1. Enable enhanced monitoring (query latency, lock waits, replication lag)
2. Execute migration through CI/CD pipeline (not manually)
3. Monitor progress (rows migrated, estimated time remaining)
4. Watch for replication lag exceeding threshold
5. Watch for elevated error rates in application metrics
6. Be ready to pause or abort if issues arise

### 14.3 Post-Migration

1. Verify migration completed successfully (row counts, data spot-checks)
2. Run application smoke tests
3. Monitor error rates for 15-30 minutes
4. Check replication lag has returned to normal
5. Document migration outcome
6. Schedule contract phase if using expand-contract

---

## 15. Advanced Patterns

### 15.1 Strangler Fig Migration

For migrating from one database to another entirely:

1. New writes go to both old and new database
2. New reads gradually shift to new database (canary)
3. Backfill historical data to new database
4. Increase canary percentage as confidence grows
5. At 100%, decommission old database

### 15.2 Version-Gated Queries

```javascript
const users = await db.collection('users').aggregate([
  {
    $addFields: {
      normalizedName: {
        $switch: {
          branches: [
            {
              case: { $eq: ['$schemaVersion', 1] },
              then: { $concat: ['$firstName', ' ', '$lastName'] }
            },
            {
              case: { $eq: ['$schemaVersion', 2] },
              then: '$fullName'
            }
          ],
          default: '$fullName'
        }
      }
    }
  }
]).toArray();
```

### 15.3 Canary Migrations

Apply migration to a subset of data first:

```javascript
const sampleIds = await db.collection('users')
  .aggregate([
    { $match: { schemaVersion: 1 } },
    { $sample: { size: Math.ceil(totalCount * 0.01) } },
    { $project: { _id: 1 } }
  ]).toArray();

await migrateDocuments(sampleIds.map(d => d._id));
await validateMigratedDocuments(sampleIds.map(d => d._id));
// If verified, proceed with full migration
```

### 15.4 Migration State Machine

Track migration progress as a state machine for complex multi-step migrations:

```
PENDING --> EXPANDING --> BACKFILLING --> VALIDATING --> CONTRACTING --> COMPLETED
                |              |              |              |
                v              v              v              v
            FAILED         FAILED         FAILED         FAILED
                |              |              |              |
                v              v              v              v
          ROLLING_BACK   ROLLING_BACK   ROLLING_BACK   ROLLING_BACK
```

---

## References

Full reference links: `references/database-migrations.md`

Tool deep-dives (CLI examples, per-tool flags, Mongock, migrate-mongo): `references/migration-tools.md`
