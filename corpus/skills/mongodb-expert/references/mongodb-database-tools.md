<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-database-tools` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

# MongoDB Database Tools

## When NOT to Use

- **Production backups on Atlas** — use Atlas Cloud Backup (managed snapshots with PITR). mongodump degrades cache performance and lacks cross-shard consistency guarantees.
- **Live migration with minimal downtime** — use MongoDB Live Migrate (Atlas) or [[mongodb-mongosync]].
- **Collections using Queryable Encryption** — mongodump is not compatible with encrypted collections.
- **Large-scale monitoring beyond a quick check** — use [[mongodb-monitoring-observability]] for Atlas metrics, Cloud Manager, or Ops Manager dashboards.

---

## Overview

The MongoDB Database Tools are a suite of command-line utilities for importing, exporting, diagnosing, and managing data in MongoDB deployments. Since MongoDB 4.4 they ship as an independent package (`mongodb-database-tools`) with their own versioning (starting at `100.0.0`), separate from both the MongoDB Server and `mongosh`.

**Current stable version:** 100.15.0
**Server compatibility:** MongoDB 4.2 through 8.0

### Tools in this skill
| Tool | Purpose |
|------|---------|
| `mongodump` | Binary export (BSON) — full or partial |
| `mongorestore` | Restore from mongodump output |
| `mongoexport` | Human-readable JSON/CSV export |
| `mongoimport` | Import JSON, CSV, or TSV |
| `mongostat` | Real-time server statistics |
| `mongotop` | Per-collection read/write time |

### When to use which tool

| Goal | Tool |
|------|------|
| Production backup (self-managed) | `mongodump` with `--oplog` on replica sets |
| Staging environment refresh | `mongodump` (prod) + `mongorestore` (staging) |
| Cross-tenant / namespace copy | `mongodump --archive` + `mongorestore --nsFrom/--nsTo` |
| Atlas-to-self-managed migration | `mongodump` from Atlas, `mongorestore` to target |
| Export data for BI/spreadsheet tools | `mongoexport --type csv` |
| Exchange data with other systems (JSON) | `mongoexport --type json` |
| Seed from JSON/CSV fixture files | `mongoimport` |
| Live server throughput check | `mongostat` |
| Identify hot collections | `mongotop` |
| Production backups on Atlas | Atlas Cloud Backup (NOT mongodump) |

---

## 1. mongodump Reference

`mongodump` creates BSON binary exports that preserve all native MongoDB types (ObjectId, Date, Decimal128, etc.). It is the correct tool for backup/restore workflows where type fidelity matters.

### Synopsis

```bash
mongodump [options] [<connection-string>]
```

### Connection Options

| Option | Description |
|--------|-------------|
| `--uri=<connectionString>` | Full MongoDB URI (overrides host/port/auth flags) |
| `--host=<hostname>[:<port>]` | Default: `localhost:27017` |
| `--port=<port>` | Default: `27017` |

### Authentication Options

| Option | Description |
|--------|-------------|
| `--username=<user>, -u` | Database username |
| `--password=<pass>, -p` | Password (prompted if omitted — preferred over inline) |
| `--authenticationDatabase=<db>` | Default: the db specified by `--db`, or `admin` |
| `--authenticationMechanism=<name>` | `SCRAM-SHA-1`, `SCRAM-SHA-256`, `MONGODB-X.509`, `MONGODB-AWS`, `GSSAPI`, `PLAIN` |
| `--awsSessionToken=<token>` | AWS session token (MONGODB-AWS auth) |
| `--config=<file>` | YAML config for sensitive values (password, URI, sslPEMKeyPassword) |

### TLS/SSL Options

| Option | Description |
|--------|-------------|
| `--ssl` | Enable TLS/SSL |
| `--sslCAFile=<file>` | Root CA certificate (.pem) |
| `--sslPEMKeyFile=<file>` | TLS certificate and key (.pem) |
| `--sslPEMKeyPassword=<value>` | Password for encrypted certificate key |
| `--sslCRLFile=<file>` | Certificate Revocation List |
| `--sslAllowInvalidCertificates` | Bypass certificate validation (dev only) |
| `--sslAllowInvalidHostnames` | Disable hostname validation (dev only) |

### Scope Options

| Option | Description |
|--------|-------------|
| `--db=<database>, -d` | Single database to dump; omit for all |
| `--collection=<coll>, -c` | Single collection; requires `--db` |
| `--query=<json>, -q` | Filter documents by JSON query; requires `--collection` |
| `--queryFile=<path>` | Path to file containing JSON query |
| `--excludeCollection=<coll>` | Exclude a collection; use multiple times |
| `--excludeCollectionsWithPrefix=<prefix>` | Exclude collections matching prefix |

### Output Options

| Option | Description |
|--------|-------------|
| `--out=<path>, -o` | Output directory (default: `dump/`) |
| `--archive[=<file>]` | Write to single archive file; omit filename to write to stdout |
| `--gzip` | Compress output (`.bson.gz`, `.metadata.json.gz`, or compressed archive) |

Using `--archive --gzip` together produces a single compressed archive — the most portable output format for transfer and storage.

### Advanced Options

| Option | Description |
|--------|-------------|
| `--oplog` | Include `oplog.bson` capturing writes during dump; required for consistent replica-set restore via `--oplogReplay` |
| `--readPreference=<string\|doc>` | Default: `primary`; set `secondary` to reduce primary load |
| `--numParallelCollections=<int>, -j` | Parallel collection exports (default: 4) |
| `--viewsAsCollections` | Export views as collections (materializes documents) |
| `--dumpDbUsersAndRoles` | Include user/role definitions (not available on Atlas M0/M2/M5) |

### Dump File Structure

```
dump/
├── mydb/
│   ├── users.bson              # BSON documents
│   ├── users.metadata.json     # Indexes, UUID, collection options (Extended JSON v2)
│   ├── orders.bson
│   ├── orders.metadata.json
│   └── system.js.bson          # system.js is included; other system.* are excluded
├── admin/                      # Only if explicitly dumped
└── oplog.bson                  # Only present with --oplog
```

With `--gzip`: all files gain `.gz` suffix.
With `--archive`: a single opaque binary file (no directory structure).

### --oplog Point-in-Time Behavior

`--oplog` captures all oplog entries generated during the dump run and stores them in `oplog.bson` at the root of the dump directory. On `mongorestore --oplogReplay`, these entries are replayed after data import to bring the dataset to the state at the moment the dump completed — not an arbitrary timestamp.

**Constraints:**
- Only works against **replica sets**, not standalone instances
- Cannot be used with `--db`, `--collection`, or `--query` (full dump required)
- Not available on Atlas M0/M2/M5 free/shared tiers
- Fails if a resharding operation is in progress

### Atlas-Specific Restrictions

On M0/M2/M5 (free/shared) clusters, the following are unavailable:
- `--db admin`
- `--dumpDbUsersAndRoles`
- `--oplog`

`mongodump` cannot be used with collections that use **Queryable Encryption**.

### Key Behavioral Notes

- Default read preference is `primary`. Use `--readPreference=secondary` to reduce primary load (secondary may be slightly behind).
- On case-insensitive file systems (Windows/macOS), collections differing only by case will overwrite each other. Use `--archive` as a workaround.
- WiredTiger outputs **uncompressed** data regardless of storage-level compression; `--gzip` is in-flight compression.
- Performance impact: if data exceeds system memory, mongodump will push working-set data out of cache. Schedule during low-traffic windows.

### Common Examples

```bash
# Full backup of all databases, compressed archive piped to S3
mongodump --uri="mongodb://localhost:27017" \
  --archive --gzip | aws s3 cp - s3://my-bucket/backup-$(date +%Y%m%d).archive.gz

# Single database backup with oplog for PIT restore
mongodump --host="rs0/host1:27017,host2:27017" \
  --oplog --gzip --out=/backup/$(date +%Y%m%d)

# Dump from secondary to reduce primary load
mongodump --uri="mongodb://user:pass@host1:27017/?authSource=admin" \
  --readPreference=secondary \
  --db=myapp --gzip --out=/backup/myapp

# Partial dump: export only active users
mongodump --db=myapp --collection=users \
  --query='{"status": "active"}' \
  --out=/tmp/active-users-dump

# Exclude sensitive collections
mongodump --db=myapp \
  --excludeCollection=audit_log \
  --excludeCollection=payment_tokens \
  --archive=myapp-no-pii.archive

# Increase parallelism for large databases
mongodump --uri="mongodb://localhost:27017" \
  --numParallelCollections=8 \
  --gzip --out=/backup/fast
```

---

## 2. mongorestore Reference

`mongorestore` restores from `mongodump` output. It performs **inserts only** — it does not update existing documents. If a document with the same `_id` already exists in the target, it is skipped (not overwritten) unless `--drop` is used.

### Synopsis

```bash
mongorestore [options] [<directory> | <archive> | <bsonfile>]
```

### Connection + Auth Options

Same as mongodump: `--uri`, `--host`, `--port`, `--username`, `--password`, `--authenticationDatabase`, `--authenticationMechanism`, `--ssl*`, `--config`.

### Input Options

| Option | Description |
|--------|-------------|
| `<directory>` | Path to dump directory (positional argument) |
| `--dir=<path>` | Explicit dump directory path |
| `--archive[=<file>]` | Restore from archive file; omit filename to read from stdin |
| `--gzip` | Decompress `.gz` files or compressed archive |

`--dir` and `--archive` are mutually exclusive.

### Namespace Options

| Option | Description |
|--------|-------------|
| `--db=<database>, -d` | Target database (deprecated for directory/archive; prefer `--nsInclude`) |
| `--collection=<coll>, -c` | Target collection (deprecated; prefer `--nsInclude`) |
| `--nsInclude=<pattern>` | Include namespaces matching pattern (e.g., `mydb.*`, `mydb.users`) |
| `--nsExclude=<pattern>` | Exclude namespaces matching pattern |
| `--nsFrom=<pattern>` | Source namespace pattern for rename |
| `--nsTo=<pattern>` | Target namespace pattern; use `$var$` wildcards |

### Restore Behavior Options

| Option | Description |
|--------|-------------|
| `--drop` | Drop each collection before restoring |
| `--oplogReplay` | Replay `oplog.bson` after restore for PIT consistency |
| `--preserveUUID` | Use original collection UUIDs from dump (requires `--drop`) |
| `--bypassDocumentValidation` | Skip JSON schema validation on insert |
| `--stopOnError` | Halt on first error (default: continue on duplicate key / validation errors) |
| `--maintainInsertionOrder` | Insert documents in dump order (also enables `--stopOnError`, sets workers to 1) |
| `--writeConcern=<doc>` | Write concern (default: `majority`); e.g., `{w:1}` for speed |
| `--numParallelCollections=<int>, -j` | Parallel collection restores (default: 4) |
| `--numInsertionWorkersPerCollection=<int>` | Parallel workers per collection |
| `--noIndexRestore` | Skip index creation |
| `--keepIndexVersion` | Do not upgrade index versions |
| `--convertLegacyIndexes` | Remove invalid index options and fix legacy key values |

### Index Rebuild Behavior

mongorestore recreates indexes **after** data insertion by default, using the index specifications in `.metadata.json` files. This is usually optimal — building indexes on already-inserted data is faster than maintaining them during bulk insert.

For very large restores (hundreds of GB), consider using `--noIndexRestore` and creating indexes separately with `db.collection.createIndex()` to control timing and avoid memory pressure.

### --preserveUUID and Change Streams

Change streams subscribe to collection events by UUID. If you restore without `--preserveUUID`, MongoDB assigns new UUIDs to the restored collections, breaking any active change stream cursors and resume tokens tied to the old UUIDs. Always use `--drop --preserveUUID` when restoring collections that have active change stream consumers.

### Atlas Limitations (M0/M2/M5 and Flex)

On free/shared/Flex clusters:
- Cannot restore to `admin` database
- Cannot use `--restoreDbUsersAndRoles`
- Cannot use `--oplogReplay`
- Cannot use `--preserveUUID`

### Required Permissions

| Scenario | Role Required |
|----------|---------------|
| Basic restore | `restore` |
| Restore `system.profile` | `dbAdmin` or `dbAdminAnyDatabase` |
| `--oplogReplay` | Custom role with `anyAction` on `anyResource` |

### Common Examples

```bash
# Restore full backup from directory
mongorestore --uri="mongodb://user:pass@localhost:27017/?authSource=admin" \
  --drop /backup/20240115

# Restore from compressed archive
mongorestore --archive=/backup/myapp.archive.gz --gzip

# Restore single collection from full dump directory
mongorestore --nsInclude="myapp.users" \
  --uri="mongodb://localhost:27017" /backup/20240115

# Restore single collection by pointing at BSON file directly
mongorestore --db=myapp --collection=users \
  /backup/20240115/myapp/users.bson

# Staging refresh: rename prod namespace to staging
mongorestore --archive=/backup/prod.archive \
  --nsFrom="production.*" --nsTo="staging.*" --drop

# Wildcard namespace rename (cross-tenant pattern)
# Restores data.orders_customer1 → customer1.orders, etc.
mongorestore --nsInclude="data.*" \
  --nsFrom="data.\$prefix\$_\$customer\$" \
  --nsTo="\$customer\$.\$prefix\$" /backup/

# PIT restore from oplog-enabled dump
mongorestore --oplogReplay --drop \
  /backup/20240115-with-oplog

# Preserve UUIDs for change stream compatibility
mongorestore --drop --preserveUUID \
  --uri="mongodb://localhost:27017" /backup/

# High-throughput restore (tune workers, relax write concern)
mongorestore --uri="mongodb://localhost:27017" \
  --numParallelCollections=8 \
  --writeConcern="{w:1}" \
  --drop /backup/large-db

# Restore from stdin (pipe from remote host)
ssh backup-server "cat /backup/latest.archive.gz" | \
  mongorestore --archive --gzip --drop
```

---

## 3. mongoexport Reference

`mongoexport` exports data in **human-readable JSON or CSV format**. It is designed for interoperability — feeding BI tools, generating CSVs for spreadsheets, or exchanging data with non-MongoDB systems.

**Important:** mongoexport is NOT a backup tool. It outputs Extended JSON, which loses some BSON type fidelity on round-trip. For backups, use `mongodump`.

### Synopsis

```bash
mongoexport --collection=<coll> [options] [<connection-string>]
```

`--collection` and `--db` are required.

### Connection + Auth Options

Same as mongodump: `--uri`, `--host`, `--port`, `--username`, `--password`, `--authenticationDatabase`, `--authenticationMechanism`, `--ssl*`, `--config`.

### Export Format Options

| Option | Description |
|--------|-------------|
| `--type=<json\|csv>` | Output format (default: `json`) |
| `--out=<file>, -o` | Output file (default: stdout) |
| `--jsonFormat=<canonical\|relaxed>` | Extended JSON mode (default: `relaxed`) |
| `--jsonArray` | Wrap output in a JSON array instead of newline-delimited documents |
| `--pretty` | Pretty-print JSON |
| `--noHeaderLine` | Omit CSV header row |

### Field Selection (Required for CSV)

| Option | Description |
|--------|-------------|
| `--fields=<f1,f2,...>, -f` | Comma-separated field list |
| `--fieldFile=<file>` | File with one field name per line |

CSV export **requires** `--fields` or `--fieldFile`. Fields containing spaces must be quoted: `--fields "first name,last name"`.

### Filtering and Pagination

| Option | Description |
|--------|-------------|
| `--query=<json>, -q` | JSON filter (Extended JSON v2; use single quotes to prevent shell interpretation) |
| `--queryFile=<file>` | JSON filter from file |
| `--sort=<json>` | Sort specification; use with `--limit` for pages |
| `--limit=<int>` | Maximum documents to export |
| `--skip=<int>` | Documents to skip before exporting |
| `--readPreference=<string\|doc>` | Default: `primary` |

### mongoexport vs mongodump

| Dimension | mongoexport | mongodump |
|-----------|-------------|-----------|
| Output format | JSON / CSV (human-readable) | BSON (binary) |
| Type fidelity | Partial — Extended JSON loses some BSON types on round-trip | Full — BSON types preserved exactly |
| Suitable for backup | No | Yes |
| Suitable for BI/CSV | Yes | No |
| Supports query filter | Yes | Yes |
| Supports aggregation | No (use `--query` only) | No |
| Streaming large sets | Yes (line-delimited by default) | Yes |
| Cross-system exchange | Yes | No |

### CSV Limitations

- Cannot represent arrays or nested documents in cells. Nested fields are either omitted or flattened with dot notation keys.
- Arrays are output as a string representation, not individual columns.
- Use JSON format for any documents with nested structure.

### Extended JSON Output

The default `--jsonFormat=relaxed` outputs dates as ISO strings and numbers as native JSON numbers. Use `--jsonFormat=canonical` for full type fidelity (stores BSON type wrappers like `{ "$oid": "..." }`). For feeding back into `mongoimport`, `canonical` format is safer.

### Common Examples

```bash
# Export collection to JSON (line-delimited, default)
mongoexport --uri="mongodb://localhost:27017" \
  --db=myapp --collection=orders --out=orders.json

# Export as JSON array (easier for some parsers)
mongoexport --uri="mongodb://localhost:27017" \
  --db=myapp --collection=orders \
  --jsonArray --pretty --out=orders-array.json

# Export to CSV with explicit fields
mongoexport --uri="mongodb://localhost:27017" \
  --db=myapp --collection=customers \
  --type=csv \
  --fields=name,email,status,createdAt \
  --out=customers.csv

# Export filtered subset (active users only)
mongoexport --uri="mongodb://localhost:27017" \
  --db=myapp --collection=users \
  --query='{"status": "active", "createdAt": {"$gte": {"$date": "2024-01-01T00:00:00Z"}}}' \
  --out=active-users.json

# Export with sort and limit (paginated export)
mongoexport --db=myapp --collection=events \
  --sort='{"timestamp": -1}' --limit=1000 \
  --out=recent-events.json

# Canonical Extended JSON for roundtrip fidelity
mongoexport --uri="mongodb://localhost:27017" \
  --db=myapp --collection=products \
  --jsonFormat=canonical --out=products-canonical.json

# Export to stdout and pipe to gzip
mongoexport --uri="mongodb://localhost:27017" \
  --db=myapp --collection=bigdata | gzip > bigdata.json.gz

# Skip header line in CSV
mongoexport --db=myapp --collection=orders --type=csv \
  --fields=orderId,amount --noHeaderLine --out=orders-raw.csv
```

---

## 4. mongoimport Reference

`mongoimport` imports data from JSON (line-delimited or array), CSV, or TSV files into a MongoDB collection. It is the complement to `mongoexport` and is useful for seeding data, loading fixtures, and one-off data loads from external systems.

### Synopsis

```bash
mongoimport [options] [<connection-string>] [<file>]
```

### Connection + Auth Options

Same as other tools: `--uri`, `--host`, `--port`, `--username`, `--password`, `--authenticationDatabase`, `--authenticationMechanism`, `--ssl*`, `--config`.

### Target Options

| Option | Description |
|--------|-------------|
| `--db=<database>, -d` | Target database (default: `test`) |
| `--collection=<coll>, -c` | Target collection; inferred from filename if omitted |
| `--file=<path>` | Input file (stdin if omitted) |
| `--drop` | Drop collection (and indexes) before importing |

### Format Options

| Option | Description |
|--------|-------------|
| `--type=<json\|csv\|tsv>` | Input format (default: `json`) |
| `--jsonArray` | Input is a JSON array (entire array loaded into memory at once; unsuitable for large files) |
| `--legacy` | Treat input as Extended JSON v1 (legacy mongod output) |

### CSV/TSV Header Options

| Option | Description |
|--------|-------------|
| `--fields=<f1,f2,...>, -f` | Declare field names for CSV/TSV without a header row |
| `--fieldFile=<file>` | File with one field name per line |
| `--headerline` | Use the first line of the file as field names |
| `--ignoreBlanks` | Skip empty fields (omit key from document) |
| `--columnsHaveTypes` | Field names encode type: `name.string(),age.int32()` |
| `--useArrayIndexFields` | Interpret `a.0,a.1` as array elements |

### Import Mode Options

| Option | Description |
|--------|-------------|
| `--mode=<insert\|upsert\|merge\|delete>` | How to handle existing documents (default: `insert`) |
| `--upsertFields=<fields>` | Fields to match on for upsert/merge/delete (default: `_id`) |

Mode details:
- **insert** — Insert documents; error on duplicate `_id` (default behavior)
- **upsert** — Replace matching document or insert if not found
- **merge** — Update matching document (set provided fields only) or insert
- **delete** — Delete matching documents; does not insert

### Reliability and Performance Options

| Option | Description |
|--------|-------------|
| `--stopOnError` | Stop on first error (default: continue on duplicate key / validation errors) |
| `--maintainInsertionOrder` | Preserve document order; implies `--stopOnError`, sets workers to 1 |
| `--numInsertionWorkers=<int>` | Concurrent insertion workers (default: 1) |
| `--writeConcern=<doc>` | Write concern (default: `majority`) |
| `--bypassDocumentValidation` | Skip JSON schema validation |

### Performance Tuning for Large Imports

- Increase `--numInsertionWorkers` to match available CPU cores on the MongoDB host (typically 4–8).
- Use `--writeConcern="{w:1}"` to relax durability guarantees for speed on non-critical data.
- Use line-delimited JSON (not `--jsonArray`) for large files — it streams without loading everything into memory.
- Drop secondary indexes before the import and rebuild them afterward for bulk-load scenarios.
- Avoid `--maintainInsertionOrder` unless document order matters — it forces single-threaded insertion.

### Duplicate Key Handling

By default, mongoimport logs duplicate key errors and continues. To skip duplicates gracefully, use `--mode=upsert` with `--upsertFields=_id`. To error out on first duplicate, use `--stopOnError`.

### Common Examples

```bash
# Import JSON fixture file
mongoimport --uri="mongodb://localhost:27017" \
  --db=myapp --collection=users --file=users.json

# Import JSON array file
mongoimport --db=myapp --collection=products \
  --file=products.json --jsonArray

# Import CSV with header row
mongoimport --db=myapp --collection=orders \
  --type=csv --headerline --file=orders.csv

# Import CSV without header, declare fields
mongoimport --db=myapp --collection=events \
  --type=csv --fields=eventId,userId,action,timestamp \
  --file=events.csv

# Import CSV with column type hints
mongoimport --db=myapp --collection=products \
  --type=csv --headerline --columnsHaveTypes \
  --fields "name.string(),price.double(),qty.int32()" \
  --file=products.csv

# Upsert by email (idempotent import)
mongoimport --db=myapp --collection=users \
  --file=users.json --mode=upsert --upsertFields=email

# Merge partial updates (only update provided fields)
mongoimport --db=myapp --collection=users \
  --file=status-updates.json --mode=merge --upsertFields=userId

# High-throughput import (tune workers, relax write concern)
mongoimport --uri="mongodb://localhost:27017" \
  --db=analytics --collection=events \
  --file=large-events.json \
  --numInsertionWorkers=8 \
  --writeConcern="{w:1}"

# Drop collection and reload from fixture
mongoimport --db=myapp --collection=seed_data \
  --file=seed.json --drop

# Import from stdin (pipe from curl)
curl -s https://api.example.com/export.json | \
  mongoimport --uri="mongodb://localhost:27017" \
  --db=myapp --collection=imported
```

---

## 5. mongostat Reference

`mongostat` provides a real-time, periodic snapshot of statistics from a running `mongod` or `mongos` instance — similar to Unix `vmstat` but for MongoDB. By default it polls every second.

### Synopsis

```bash
mongostat [options] [<connection-string>] [<polling-interval-in-seconds>]
```

### Connection + Auth Options

Same as other tools: `--uri`, `--host`, `--port`, `--username`, `--password`, `--authenticationDatabase`, `--ssl*`.

### Output Options

| Option | Description |
|--------|-------------|
| `--rowcount=<n>, -n` | Stop after `n` rows (0 = run indefinitely) |
| `--json` | Output in JSON format (useful for programmatic consumption) |
| `--interactive` | Non-scrolling interactive interface |
| `--noheaders` | Suppress column headers |
| `--humanReadable=<bool>` | Default: `true`; format numbers for readability |
| `-o=<fields>` | Show only specified fields |
| `-O=<fields>` | Add fields to default output |
| `--discover` | Report on all replica set members or sharded cluster shards |
| `--all` | Show all optional fields |

### Output Fields Explained

| Field | Meaning |
|-------|---------|
| `inserts` | Documents inserted per second (replicated ops marked with `*`) |
| `query` | Query operations per second |
| `update` | Update operations per second |
| `delete` | Delete operations per second |
| `getmore` | Cursor getMore batch operations per second |
| `command` | Commands per second; local\|replicated on secondaries |
| `dirty` | **WiredTiger**: % of cache holding dirty (unwritten) bytes |
| `used` | **WiredTiger**: % of cache currently in use |
| `flushes` | WiredTiger checkpoints triggered in the interval |
| `vsize` | Virtual memory in use (MB) |
| `res` | Resident memory in use (MB) |
| `qr\|qw` | Read/write client queue lengths (blocked clients) |
| `ar\|aw` | Active read/write client counts |
| `netIn` | Network bytes received |
| `netOut` | Network bytes sent |
| `conn` | Total open connections |
| `repl` | Replication state (PRI, SEC, REC, UNK, RTR, ARB) |

### Interpreting WiredTiger Cache Metrics

**dirty%** is the most important WiredTiger health indicator:
- Calculated as: `tracked dirty bytes / maximum cache bytes configured`
- Normal range: 0–5%
- Warning zone: 5–20% — evictions are running to free dirty pages
- Critical: >20% — the eviction loop cannot keep up; writes will begin to stall
- If dirty% is persistently high, consider increasing `wiredTigerCacheSizeGB` or reducing write throughput.

**used%** shows overall cache utilization:
- Calculated as: `bytes currently in cache / maximum cache bytes configured`
- A value near 100% means the cache is full; MongoDB is evicting pages to make room.
- High used% alone is normal (cache should be full); problems arise when dirty% is also high.

### Common Examples

```bash
# Watch all stats every second until Ctrl-C
mongostat --uri="mongodb://user:pass@localhost:27017/?authSource=admin"

# Print 20 rows at 5-second intervals then exit
mongostat --rowcount=20 5

# JSON output for scripting/alerting
mongostat --json 10

# Discover and monitor all replica set members
mongostat --discover --uri="mongodb://host1:27017,host2:27017,host3:27017/"

# Custom field selection
mongostat -o="host=HOST,time=T,inserts,query,update,dirty,used,conn"

# Add extra fields to default output
mongostat -O="host,version,storageEngine"

# Watch just dirty and used cache metrics
mongostat -o="dirty,used" 2
```

### mongostat on Atlas

mongostat works against Atlas clusters with the appropriate credentials. The user needs `clusterMonitor` role at minimum. You can point mongostat at any Atlas connection string:

```bash
mongostat "mongodb+srv://monitor-user:pass@cluster0.example.mongodb.net/?authSource=admin"
```

---

## 6. mongotop Reference

`mongotop` tracks the time a `mongod` instance spends reading and writing on a **per-collection basis**. It is the primary CLI tool for identifying hot collections — collections with disproportionate I/O time.

### Synopsis

```bash
mongotop [options] [<connection-string>] [<polling-interval-in-seconds>]
```

### Connection + Auth Options

Same as other tools: `--uri`, `--host`, `--port`, `--username`, `--password`, `--authenticationDatabase`, `--ssl*`, `--config`.

### Output and Polling Options

| Option | Description |
|--------|-------------|
| `--rowcount=<int>, -n` | Number of output lines (0 = indefinite) |
| `--json` | JSON output format |
| `--locks` | Report per-database lock usage (MongoDB 2.6 and earlier only) |
| `--quiet` | Suppress non-essential output |
| `--verbose, -v` | Increase verbosity |
| `<sleeptime>` | Polling interval in seconds (default: 1) |

### Output Fields

| Field | Meaning |
|-------|---------|
| `ns` | Namespace: `database.collection` |
| `total` | Total time spent in this namespace (ms) in the interval |
| `read` | Time spent on read operations (ms) |
| `write` | Time spent on write operations (ms) |
| `<timestamp>` | When this row was recorded |

Only **active namespaces** appear in the output. Collections with no recent activity are omitted.

### Identifying Hot Collections

1. Run `mongotop 5` (5-second intervals) during peak load.
2. Look for collections with high `total` values — these consume the most I/O time.
3. Compare `read` vs. `write` breakdown to determine workload character.
4. Collections consistently at the top of the list across multiple intervals are hot.

```bash
# Poll every 10 seconds
mongotop 10

# JSON output for processing with jq
mongotop --json 5 | jq '.totals | to_entries | sort_by(-.value.total) | .[0:10]'

# Limit to 10 intervals then exit
mongotop --rowcount=10 5
```

### Required Permissions

The authenticated user needs:
- `serverStatus` privilege
- `top` privilege

Minimum role: `clusterMonitor`.

### mongotop vs Atlas Real-Time Performance Panel

| Capability | mongotop | Atlas Real-Time Perf Panel |
|-----------|----------|---------------------------|
| Deployment type | Self-managed or Atlas (with credentials) | Atlas only (built-in) |
| Per-collection metrics | Yes | Yes |
| Real-time data | Yes (configurable interval) | Yes |
| Historical data | No | Yes (up to 24 hours) |
| Slow operation log | No | Yes |
| GUI | No (CLI only) | Yes |
| Setup required | Install + credentials | None (built into Atlas UI) |
| Programmatic access | `--json` flag | Atlas API / metrics API |

For self-managed deployments, `mongotop` is the primary tool. For Atlas, the Real-Time Performance Panel provides equivalent visibility with historical trending.

---

## 7. Database Tools vs Atlas Backups — Decision Guide

### Quick Decision Matrix

| Scenario | Recommended Approach |
|----------|---------------------|
| Production backup on Atlas | **Atlas Cloud Backup** (snapshots) |
| Production backup on self-managed | `mongodump --oplog` on replica sets; filesystem snapshots for large deployments |
| Staging refresh from production | `mongodump` (from prod, off secondary) + `mongorestore --drop` (to staging) |
| Atlas → self-managed migration | `mongodump` from Atlas + `mongorestore` to self-managed |
| Self-managed → Atlas migration | MongoDB Live Migrate (preferred) or `mongodump` + `mongorestore` |
| Cross-tenant data copy | `mongodump --archive` + `mongorestore --nsFrom/--nsTo` |
| Schema migration on same cluster | `mongoexport` + transform + `mongoimport` |
| Data exchange with external system | `mongoexport` (JSON/CSV) or `mongoimport` |
| Disaster recovery (large, RTO < 1hr) | Atlas Cloud Backup snapshots or filesystem snapshots |

### Why NOT mongodump for Atlas Production

1. **Performance impact**: mongodump reads all data, pushing the working set out of the WiredTiger cache. On large clusters this causes read latency spikes for live traffic.
2. **Consistency window**: Even with `--oplog`, you get at best replica set consistency — not cross-shard transaction consistency on sharded clusters.
3. **Speed**: Restoring 1 TB via mongorestore takes hours. Atlas Cloud Backup restores from a block-level snapshot in minutes.
4. **Automation**: Atlas Cloud Backup has retention policies, point-in-time recovery (PITR), and cross-region replication built in. mongodump requires custom scripting for all of this.
5. **Tier limitations**: `--oplog` is not available on M0/M2/M5.

### When mongodump/mongorestore IS the right choice

- **Development and staging environments**: Cheap, flexible, no Atlas backup licensing cost. Run against secondary.
- **Data portability**: Moving data between cloud providers, between Atlas and self-managed, or exporting for archival.
- **Selective restores**: Restore a single collection or namespace without restoring an entire snapshot.
- **Dataset < 300 GB**: Migration with an acceptable downtime window.
- **Schema migrations with downtime**: Dump, transform, restore to new schema.
- **Anonymous/sanitized data export**: Use `--query` to filter which *documents* to export, then `--fields` (mongoexport) or a post-processing step (jq, driver) to remove sensitive *fields* before loading into dev environments.

### Sharded Cluster Warning

`mongodump` on a sharded cluster **does not guarantee consistency** across shards. Cross-shard multi-document transactions may not be captured atomically. For sharded cluster backups, use:
- MongoDB Atlas Cloud Backup
- MongoDB Cloud Manager
- MongoDB Ops Manager (for self-managed)

If you must use mongodump on sharded clusters (e.g., for collection-level exports), stop the balancer and pause all DDL operations first.

---

## 8. Installation and Versioning

### Package Separation (MongoDB 4.4+)

Starting with MongoDB 4.4, the Database Tools are released as a separate package (`mongodb-database-tools`) with independent versioning. The first independent version is `100.0.0`. Current version: `100.15.0`.

**Important:** The tools are also NOT bundled with `mongosh`. Installing `mongosh` does not install `mongodump`, `mongorestore`, etc.

### Version Compatibility Rule

The Database Tools use a `100.x.y` versioning scheme independent of the MongoDB Server's `4.x`–`8.x` versioning. Compatibility is determined by the **MongoDB Server major versions listed in the tools release notes**, not by numeric comparison.

**Decision rule:** Always use the **latest available tools release** (`100.15.0` as of this writing). Every current tools release supports MongoDB 4.2 through 8.0. If you are on a very old server (≤ 4.0), pin to an older tools release that lists that version in its compatibility matrix.

For dump/restore pairs: use the **same tools version** for both mongodump and mongorestore to avoid metadata format mismatches.

### Installation

**macOS (Homebrew)**
```bash
brew tap mongodb/brew
brew install mongodb-database-tools

# Verify
mongodump --version
```

**Ubuntu/Debian (apt)**
```bash
# Add MongoDB apt repository first (see MongoDB docs for current key/repo)
wget -qO - https://www.mongodb.org/static/pgp/server-8.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/8.0 multiverse" \
  | sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list
sudo apt-get update
sudo apt-get install -y mongodb-database-tools
```

**RHEL/CentOS/Amazon Linux (yum/dnf)**
```bash
# Add MongoDB yum repository first
sudo yum install -y mongodb-database-tools

# Or with dnf
sudo dnf install -y mongodb-database-tools
```

**Windows (Chocolatey)**
```powershell
choco install mongodb-database-tools
```

Or download the MSI from [MongoDB Download Center](https://www.mongodb.com/try/download/database-tools).

**Docker**

The official `mongo` image includes the Database Tools:
```bash
# Run mongodump inside a Docker container
docker run --rm mongo:latest mongodump \
  --uri="mongodb://host.docker.internal:27017" \
  --out=/dump

# With a mounted volume for output
docker run --rm -v $(pwd)/backup:/backup mongo:latest mongodump \
  --uri="mongodb://host.docker.internal:27017" \
  --out=/backup
```

### Check Installed Version

```bash
mongodump --version
mongorestore --version
mongoexport --version
mongoimport --version
mongostat --version
mongotop --version
```

---

## 9. Common Patterns

### Pattern 1: Staging Environment Refresh from Production

Refresh a staging database with production data, reading from a secondary to avoid production impact.

```bash
# Step 1: Dump production DB from secondary (off-peak hours)
mongodump \
  --uri="mongodb://user:pass@prod-host1:27017,prod-host2:27017,prod-host3:27017/myapp?authSource=admin&replicaSet=rs0" \
  --readPreference=secondary \
  --db=myapp \
  --archive --gzip > /tmp/prod-myapp-$(date +%Y%m%d).archive.gz

# Step 2: Restore to staging (drop first for clean state)
mongorestore \
  --uri="mongodb://user:pass@staging-host:27017/?authSource=admin" \
  --archive=/tmp/prod-myapp-$(date +%Y%m%d).archive.gz \
  --gzip \
  --drop
```

### Pattern 2: Collection-Level Restore from Full Dump

Restore a single collection without touching the rest of the database.

```bash
# Create full dump (with oplog for consistency)
mongodump --uri="mongodb://localhost:27017" --oplog --out=/backup/daily

# Restore only the orders collection to a different namespace
mongorestore \
  --uri="mongodb://localhost:27017" \
  --nsInclude="myapp.orders" \
  --drop \
  /backup/daily

# Or restore from the specific BSON file
mongorestore \
  --uri="mongodb://localhost:27017" \
  --db=myapp --collection=orders \
  /backup/daily/myapp/orders.bson
```

### Pattern 3: Cross-Tenant Data Migration

Copy data between tenant namespaces, renaming database during restore.

```bash
# Dump tenant1's data from production
mongodump --db=tenant1_prod --archive=/tmp/tenant1.archive

# Restore into new tenant2 namespace
mongorestore \
  --archive=/tmp/tenant1.archive \
  --nsFrom="tenant1_prod.*" \
  --nsTo="tenant2_staging.*" \
  --drop
```

### Pattern 4: Automated Daily Backup to S3

Shell script for a nightly backup job.

```bash
#!/usr/bin/env bash
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
S3_BUCKET="s3://my-backups/mongodb"
MONGO_URI="${MONGO_URI:-mongodb://localhost:27017}"

echo "Starting backup at ${TIMESTAMP}"
mongodump \
  --uri="${MONGO_URI}" \
  --readPreference=secondary \
  --oplog \
  --archive \
  --gzip | aws s3 cp - "${S3_BUCKET}/backup-${TIMESTAMP}.archive.gz"

echo "Backup complete: ${S3_BUCKET}/backup-${TIMESTAMP}.archive.gz"
```

### Pattern 5: Anonymous Data Export for Dev Environments

Export a subset of users without PII for development fixtures. Since mongoexport does not support aggregation pipelines, use mongosh or a driver for the transform step.

```bash
# Step 1: Export active users (mongoexport with query filter)
mongoexport \
  --uri="mongodb://localhost:27017" \
  --db=myapp --collection=users \
  --query='{"status": "active"}' \
  --fields=_id,role,preferences,createdAt \
  --out=/tmp/users-no-pii.json

# Step 2: Scrub any remaining PII with jq
jq '. + {"email": (.email | gsub("[^@]"; "x")), "name": "Test User"}' \
  /tmp/users-no-pii.json > /tmp/users-anon.json

# Step 3: Import into dev environment
mongoimport \
  --uri="mongodb://dev-host:27017" \
  --db=myapp --collection=users \
  --file=/tmp/users-anon.json \
  --drop
```

### Pattern 6: Atlas to Self-Managed Migration

```bash
# Dump from Atlas (use the SRV connection string from Atlas UI)
mongodump \
  "mongodb+srv://user:pass@cluster0.example.mongodb.net/myapp?authSource=admin" \
  --out=/backup/atlas-export \
  --readPreference=secondary

# Restore to self-managed
mongorestore \
  --uri="mongodb://localhost:27017" \
  --nsInclude="myapp.*" \
  --drop \
  /backup/atlas-export
```

### Pattern 7: Database Clone (Rename)

Clone a database under a different name on the same or different cluster.

```bash
mongodump --db=source_db --archive=/tmp/source_db.archive

mongorestore \
  --archive=/tmp/source_db.archive \
  --nsFrom="source_db.*" \
  --nsTo="target_db.*" \
  --drop
```

---

## 10. Anti-Patterns

### Anti-Pattern 1: Using mongodump as Atlas Production Backup

```bash
# WRONG: Do not rely on this for Atlas production backup
mongodump "mongodb+srv://user:pass@cluster0.example.mongodb.net" \
  --archive=prod-backup.archive
```

**Why wrong:** Performance impact on production, no PITR, slow restore. Use Atlas Cloud Backup instead.

### Anti-Pattern 2: Importing CSV with Nested/Array Fields

```bash
# WRONG: CSV cannot represent nested documents or arrays
mongoexport --type=csv --fields=userId,tags,address.city,addresses \
  --collection=users --out=users.csv
```

**Why wrong:** `tags` (an array) becomes a string representation; `address.city` (nested) may be empty if the field doesn't exist. Use JSON format for documents with nested structure.

### Anti-Pattern 3: --drop in Wrong Environment

```bash
# EXTREMELY DANGEROUS if run against production accidentally
mongorestore --drop --uri="mongodb://prod:27017" /backup/old-data/
```

**Why wrong:** `--drop` drops each collection before restoring. Always double-check `--uri` points to the correct environment. Use environment-specific config files or environment variables.

### Anti-Pattern 4: Ignoring --preserveUUID on Restore

```bash
# WRONG: restores with new UUIDs, breaks change stream resume tokens
mongorestore --drop /backup/
```

**Why wrong:** If change streams subscribe to restored collections, new UUIDs invalidate their resume tokens. Add `--preserveUUID` when change streams are in use:

```bash
mongorestore --drop --preserveUUID /backup/
```

### Anti-Pattern 5: Large Import Without Tuning Workers

```bash
# SLOW: single insertion worker (default) for a 50M document dataset
mongoimport --db=analytics --collection=events --file=50m-events.json
```

**Why wrong:** Default is 1 insertion worker. For large imports, tune:

```bash
mongoimport --db=analytics --collection=events \
  --file=50m-events.json \
  --numInsertionWorkers=8 \
  --writeConcern="{w:1}"
```

### Anti-Pattern 6: Not Checking mongorestore Exit Code in Scripts

```bash
# WRONG: silent failure
mongorestore /backup/latest
echo "Restore complete"  # Prints even if mongorestore failed
```

**Why wrong:** mongorestore can fail partway through, leaving an inconsistent database. Always check exit codes:

```bash
if ! mongorestore /backup/latest; then
  echo "ERROR: restore failed" >&2
  exit 1
fi
```

### Anti-Pattern 7: mongodump on Sharded Cluster Without Stopping Balancer

```bash
# WRONG: may produce inconsistent cross-shard snapshots
mongodump --uri="mongodb://mongos-host:27017" --out=/backup/
```

**Why wrong:** The chunk balancer moves data between shards during the dump. Documents may appear in multiple shards or be missed. Stop the balancer before dumping:

```bash
# In mongosh first:
sh.stopBalancer()

# Then run dump
mongodump --uri="mongodb://mongos-host:27017" --out=/backup/

# Re-enable after
sh.startBalancer()
```

### Anti-Pattern 8: Using --jsonArray for Large File Imports

```bash
# RISKY: jsonArray loads the entire file into memory
mongoimport --file=5gb-data.json --jsonArray --db=mydb --collection=data
```

**Why wrong:** `--jsonArray` requires the entire JSON array to be read into memory and is capped at 16 MB per document. For large files, use line-delimited JSON (one document per line, no array wrapper):

```bash
mongoimport --file=5gb-data.json --db=mydb --collection=data
```

### Anti-Pattern 9: Storing Passwords in Command History

```bash
# WRONG: password visible in shell history and process list
mongodump --username=admin --password=secret123 --host=localhost
```

**Why wrong:** Password appears in `~/.bash_history`, `ps aux`, and shell history. Use `--config` or environment variables:

```bash
# Use a YAML config file with restricted permissions (chmod 600)
mongodump --config=/secure/mongodump-config.yaml

# Or use URI from environment variable
mongodump "${MONGO_URI}"
```

---

## References and See Also

### Official Documentation
- [MongoDB Database Tools Documentation](https://www.mongodb.com/docs/database-tools/) — Top-level tools index
- [mongodump Reference](https://www.mongodb.com/docs/database-tools/mongodump/) — Full option reference
- [mongorestore Reference](https://www.mongodb.com/docs/database-tools/mongorestore/) — Full option reference
- [mongoexport Reference](https://www.mongodb.com/docs/database-tools/mongoexport/) — Full option reference
- [mongoimport Reference](https://www.mongodb.com/docs/database-tools/mongoimport/) — Full option reference
- [mongostat Reference](https://www.mongodb.com/docs/database-tools/mongostat/) — Full option reference
- [mongotop Reference](https://www.mongodb.com/docs/database-tools/mongotop/) — Full option reference
- [Back Up and Restore with MongoDB Tools](https://www.mongodb.com/docs/manual/tutorial/backup-and-restore-tools/) — Manual guide
- [Backup a Sharded Cluster with Database Dumps](https://www.mongodb.com/docs/manual/tutorial/backup-sharded-cluster-with-database-dumps/) — Sharded cluster procedure
- [Seed with mongorestore (Atlas)](https://www.mongodb.com/docs/atlas/import/mongorestore/) — Atlas seeding guide

### Related Skills
- [[mongodb-backup-restore]] — Broader backup strategy (snapshots, Atlas Cloud Backup, PITR)
- [[mongodb-migration-patterns]] — Live migration, mongomirror, mongosync, and Atlas Live Migrate
- [[mongodb-mongosh]] — MongoDB Shell for ad-hoc queries and administrative tasks
- [[mongodb-monitoring-observability]] — Atlas monitoring, Cloud Manager, Ops Manager
- [[mongodb-change-streams]] — Change stream resume tokens and UUID implications
- [[mongodb-wiredtiger]] — WiredTiger cache internals (dirty%, used%)
