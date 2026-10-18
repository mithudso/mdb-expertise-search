<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-mongosh` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

# mongodb-mongosh

MongoDB Shell (mongosh) expert knowledge — the official interactive JavaScript/REPL shell for MongoDB. Covers installation, connection, configuration, REPL features, CRUD, BSON types, scripting, snippets, transactions, and performance diagnostics.

## When to Use

- Writing or debugging mongosh one-liners or scripts
- Connecting to MongoDB with TLS, auth, or Atlas connection strings
- Configuring `.mongoshrc.js` or `mongosh.conf.yaml`
- Migrating legacy `mongo` shell scripts to mongosh
- BSON type construction and type-safe queries
- Running multi-document transactions from the shell
- Performance diagnostics: `explain()`, `currentOp()`, profiler, `rs.status()`
- Automating MongoDB operations in CI/CD pipelines
- Using the snippet system for schema analysis or compatibility shims

## When NOT to Use

- **Visual data exploration** — use MongoDB Compass (GUI) instead
- **Application code** — use the appropriate MongoDB driver (Node.js, Python, Java, etc.); mongosh is for interactive and scripted admin/ops work, not app logic
- **Atlas Data API / App Services** — use the Atlas UI, Atlas CLI (`atlas`), or the REST API directly; mongosh cannot call Atlas-layer services
- **Data migrations in production at scale** — prefer `mongodump`/`mongorestore` or `mongosync` for volume operations

---

## 1. mongosh vs Legacy `mongo` Shell

### Architecture Change

| Aspect | Legacy `mongo` | `mongosh` |
|---|---|---|
| Runtime | C++ / SpiderMonkey JS engine | Node.js (TypeScript-compiled) |
| Bundled with server | Yes (MongoDB ≤ 5.x) | Separate binary, independent release |
| Removed from server | N/A | `mongo` removed in MongoDB 6.0 |
| ES6+ support | Limited | Full (async/await, destructuring, arrow functions, template literals) |
| Async/await | Not supported | Native — all DB calls are async under the hood |
| `--shell` flag | Required to stay in shell after `--eval` | Use `--shell` to override auto-exit; default behavior auto-exits |
| Retryable writes | Disabled by default | **Enabled by default** |
| Error output | All to stdout | Errors go to **stderr**; data to **stdout** |
| Number storage | All numbers as `Double` | `Int32` when fits, else `Double` |

### Key Behavioral Differences

**Number types**: Legacy `mongo` stored all JS numbers as `Double`. mongosh uses `Int32` for whole numbers that fit, otherwise `Double`. Use explicit constructors (`Int32()`, `Long()`, `Decimal128()`) when type matters.

**ObjectId methods changed**:
```javascript
// legacy mongo          // mongosh
obj.str                  // undefined (removed)
obj.valueOf()            // returns formatted string ObjectId("...") (was hex in legacy)
obj.toString()           // returns hex string (was formatted string in legacy)
```

**Deprecated methods** — migrate these:
| Legacy | mongosh replacement |
|---|---|
| `db.coll.count()` | `countDocuments()` or `estimatedDocumentCount()` |
| `db.coll.insert()` | `insertOne()` / `insertMany()` / `bulkWrite()` |
| `db.coll.remove()` | `deleteOne()` / `deleteMany()` / `findOneAndDelete()` |
| `db.coll.save()` | `insertOne()` / `updateOne()` / `findOneAndUpdate()` |
| `db.coll.update()` | `updateOne()` / `updateMany()` / `findOneAndUpdate()` |
| `DBQuery.shellBatchSize` | `config.set("displayBatchSize", N)` |
| `rs.secondaryOk()` | Not needed — set read preference on connection |

**`show` helpers always use `primaryPreferred`**: `show dbs`, `show collections`, `show tables` ignore your read preference setting.

**Undefined → null**: Inserting `{ field: undefined }` stores `{ field: null }` in mongosh.

**Configuration file renamed**: `.mongorc.js` → `.mongoshrc.js`. If mongosh finds the old file without the new one, it prints a migration warning and does **not** load it.

**Async limitations**: Database calls cannot be used in certain synchronous JavaScript contexts:
```javascript
// FAILS — class constructor is synchronous
class Finder {
  constructor() {
    this.result = db.users.find(); // TypeError
  }
}
// WORKS — async IIFE; note: this.result holds a Promise<Cursor>, not the cursor directly
class Finder {
  constructor() {
    this.result = (async () => db.users.find())();
  }
}

// FAILS — non-async generator
function* gen() { yield db.users.findOne(); }
// WORKS
async function* gen() { yield db.users.findOne(); }

// FAILS — sort callback with DB call
db.getCollectionNames().sort((a, b) =>
  db[a].estimatedDocumentCount() - db[b].estimatedDocumentCount()
);
// WORKS — map first, sort on pre-fetched values
db.getCollectionNames()
  .map(n => ({ name: n, size: db[n].estimatedDocumentCount() }))
  .sort((a, b) => a.size - b.size)
  .map(c => c.name);
```

---

## 2. Installation and Connection

### Install mongosh

```bash
# macOS — Homebrew
brew install mongosh

# macOS / Linux — direct download (replace <version> with actual release)
curl -O https://downloads.mongodb.com/compass/mongosh-<version>-linux-x64.tgz

# Windows — MSI installer or winget
winget install MongoDB.Shell

# Note: mongosh is a standalone binary, separate from both the MongoDB server
# package and from the MongoDB Database Tools (mongodump, mongorestore, etc.).
# It has been independently released since MongoDB 6.0 removed the legacy mongo shell.
```

Verify: `mongosh --version`

### Basic Connection Forms

```bash
# Default — localhost:27017, no auth
mongosh

# Explicit host/port
mongosh --host 192.168.1.10 --port 27017

# Full connection string (preferred)
mongosh "mongodb://localhost:27017/mydb"

# Replica set
mongosh "mongodb://rs1.example.com:27017,rs2.example.com:27017/mydb?replicaSet=myRS"

# Atlas (DNS SRV)
mongosh "mongodb+srv://cluster0.abc12.mongodb.net/mydb" \
  --username myUser --password

# Switch database after connecting
use mydb
```

### Authentication Flags

```bash
# Username/password
mongosh --username admin --password           # prompts for password
mongosh -u admin -p secret --authenticationDatabase admin

# Specific auth mechanism
mongosh --username user --authenticationMechanism SCRAM-SHA-256

# X.509 certificate auth
mongosh --tls --tlsCertificateKeyFile client.pem \
  --authenticationMechanism MONGODB-X509

# AWS IAM auth
mongosh --authenticationMechanism MONGODB-AWS

# Kerberos (GSSAPI)
mongosh --authenticationMechanism GSSAPI --gssapiServiceName mongodb
```

Security tip: prefix commands with a space in bash/zsh to prevent password storage in shell history.

### TLS Flags

```bash
# Enable TLS (server cert validated against system CA)
mongosh --tls "mongodb://secure.example.com:27017"

# Custom CA file
mongosh --tls --tlsCAFile /path/to/ca.pem "mongodb://..."

# Mutual TLS (client certificate)
mongosh --tls \
  --tlsCAFile /path/to/ca.pem \
  --tlsCertificateKeyFile /path/to/client.pem \
  --tlsCertificateKeyFilePassword "keypassword" \
  "mongodb://..."

# Allow invalid certificates (dev only — never production)
mongosh --tls --tlsAllowInvalidCertificates "mongodb://..."

# Use OS certificate store (Windows/macOS)
mongosh --tlsUseSystemCA "mongodb://..."

# Disable specific protocols
mongosh --tls --tlsDisabledProtocols TLS1_0,TLS1_1 "mongodb://..."
```

### Scripting / Non-interactive Flags

```bash
# Evaluate a single expression and exit
mongosh --eval 'db.users.countDocuments()'

# Multiple --eval args (only last result is printed)
mongosh --eval 'use mydb' --eval 'db.stats()'

# Output Extended JSON (machine-readable)
mongosh --quiet --json=relaxed --eval 'db.stats()'

# Run a script file
mongosh --file /path/to/script.js
mongosh -f script.js

# Stay in REPL after --eval
mongosh --eval 'use mydb' --shell

# Skip .mongoshrc.js (for clean/predictable automation)
mongosh --norc --file script.js

# Stable API enforcement
mongosh --apiVersion 1 --apiStrict "mongodb://localhost"
```

---

## 3. Configuration Files

### `.mongoshrc.js` — Per-User Startup Script

**Location**: `~/.mongoshrc.js` (HOME directory)

Loaded automatically on every interactive startup, before the first prompt. For `--eval` / `--file` runs, it loads *after* the script finishes. Suppress with `--norc`.

**Common customizations**:

```javascript
// Custom prompt showing database and host
{
  const hostnameSymbol = Symbol('hostname');
  prompt = () => {
    if (!db[hostnameSymbol])
      db[hostnameSymbol] = db.serverStatus().host;
    return `${db.getName()}@${db[hostnameSymbol]}> `;
  };
}

// Numbered command prompt
let cmdCount = 1;
prompt = () => (cmdCount++) + '> ';

// Log each connection with timestamp
db.getSiblingDB('admin').clientConnections.insertOne({ connectTime: ISODate() });

// Set config preferences
config.set('inspectDepth', Infinity);
config.set('displayBatchSize', 50);
config.set('redactHistory', 'remove-redact');

// Helper functions available in all sessions
function findById(coll, id) {
  return db[coll].findOne({ _id: ObjectId(id) });
}

// Silence greeting
// (use disableGreeting in mongosh.conf.yaml instead — see below)
```

**Per-project `.mongoshrc.js`**: Place a `.mongoshrc.js` in the current working directory; mongosh loads it after the global one when launched from that directory.

### `mongosh.conf.yaml` — Global Config File

**Location**:
- Linux/macOS: `/etc/mongosh.conf`
- Windows: `%ProgramData%\MongoDB\mongosh.conf`

YAML format, all settings under the `mongosh:` key:

```yaml
mongosh:
  displayBatchSize: 50
  historyLength: 5000
  inspectDepth: 20
  redactHistory: "remove-redact"
  showStackTraces: false
  enableTelemetry: false
  disableGreeting: true      # suppress "Welcome to mongosh" banner
```

### Config API (in-shell or in `.mongoshrc.js`)

```javascript
// View all settings
config

// Read a setting
config.get('displayBatchSize')    // → 20

// Set a setting (persists across sessions)
config.set('displayBatchSize', 50)
config.set('historyLength', 5000)
config.set('inspectDepth', Infinity)
config.set('showStackTraces', true)
config.set('redactHistory', 'remove-redact')  // 'keep' | 'remove' | 'remove-redact'
config.set('enableTelemetry', false)
config.set('editor', 'vim')                   // external editor for .editor mode
```

### Complete Settings Reference

| Setting | Default | Description |
|---|---|---|
| `displayBatchSize` | 20 | Items shown per cursor iteration (`it` shows next batch) |
| `historyLength` | 1000 | Lines kept in REPL history |
| `inspectDepth` | 6 | Object nesting depth in output (`Infinity` = full) |
| `inspectCompact` | 3 | Elements shown inline before line-break mode; `false` = one per line |
| `redactHistory` | `remove` | `keep` = store all; `remove` = strip sensitive; `remove-redact` = redact values |
| `showStackTraces` | `false` | Show full JS stack traces on errors |
| `enableTelemetry` | `true` | Anonymous usage data to MongoDB |
| `editor` | `null` | External editor for `.editor` mode (overrides `$EDITOR`) |
| `browser` | system default | Browser for OIDC auth redirect; `false` to disable |
| `snippetAutoload` | `true` | Auto-load installed snippets on startup |
| `snippetIndexSourceURLs` | MongoDB CDN | Semicolon-separated snippet registry URLs |
| `logLocation` | OS default | Absolute path for log directory |
| `logMaxFileCount` | 100 | Max log files retained |
| `logRetentionDays` | 30 | Days before old log files are deleted |
| `disableGreeting` | `false` | Suppress the "Welcome to mongosh" banner on startup (global config file only) |

---

## 4. REPL Features

### Navigation and History

```text
↑ / ↓          — cycle through command history
Ctrl-R          — reverse incremental search through history
Ctrl-C          — cancel current input
Ctrl-D          — exit (same as exit / quit())
Tab             — autocomplete (methods, fields, collection names, keywords)
Tab Tab         — show all completions
```

### Shell Commands (REPL directives — not JavaScript, no semicolon)

These are recognized by the REPL before JS parsing. They cannot be used inside scripts loaded via `--file` or `load()`.

```text
show dbs            -- list databases
show databases      -- alias for show dbs
show collections    -- list collections in current db
show tables         -- alias for show collections
show profile        -- show system.profile entries (last 5, slowms > 0)
show users          -- users in current db
show roles          -- roles in current db
show logs           -- list available log names
show log global     -- print global log

use mydb            -- switch database (creates if needed on first write)
cls                 -- clear screen (also Ctrl-L)
exit                -- exit shell
quit()              -- exit shell (this one IS valid JS)
it                  -- iterate cursor (show next displayBatchSize results)
```

### Multi-line Input and Editor Mode

mongosh automatically detects incomplete input (open braces, parentheses) and enters multi-line mode with `...` prefix.

```javascript
// Multi-line — type naturally, mongosh waits for closing brace
db.users.aggregate([
  { $match: { status: "active" } },
  { $group: { _id: "$country", count: { $sum: 1 } } }
])

// .editor — open full editor for complex scripts
// Type .editor, write code, Ctrl-D to execute, Ctrl-C to cancel
.editor
```

### Cursor Iteration

```javascript
// find() returns a cursor; mongosh auto-prints first displayBatchSize docs
db.users.find()

// Type 'it' to see next batch
it

// Consume all results as an array
db.users.find().toArray()

// forEach — most common iteration pattern
db.users.find({ active: true }).forEach(doc => printjson(doc))

// Cursor methods (chain before iteration)
db.users.find({ active: true })
  .sort({ name: 1 })
  .skip(20)
  .limit(10)
  .hint({ name: 1 })     // force index
  .projection({ name: 1, email: 1, _id: 0 })  // same as second arg to find()

// Manual async cursor iteration (mongosh cursor methods are async)
const cursor = db.users.find();
while (await cursor.hasNext()) {
  printjson(await cursor.next());
}
```

### Tab Completion

mongosh uses live schema sampling for tab completion. It samples the collection to discover field names — disable with `config.set('disableSchemaSampling', true)` if this causes performance issues.

```javascript
db.us<Tab>           // completes collection name
db.users.f<Tab>      // shows find, findOne, findOneAndUpdate, ...
db.users.find({ sta<Tab>  // completes known field names
```

---

## 5. CRUD and Helper Methods

### Query

```javascript
// Basic find
db.users.find({ age: { $gte: 18 } })
db.users.findOne({ email: "alice@example.com" })

// Projection
db.users.find({}, { name: 1, email: 1, _id: 0 })

// Cursor methods
db.users.find({ active: true })
  .sort({ createdAt: -1 })
  .skip(0)
  .limit(25)
  .explain("executionStats")   // analyze query plan

// Count
db.users.countDocuments({ status: "active" })      // exact, uses query
db.users.estimatedDocumentCount()                   // fast, uses metadata
db.users.distinct("country", { active: true })

// Async cursor iteration
const cur = db.users.find();
while (await cur.hasNext()) {
  const doc = await cur.next();
  print(doc.name);
}
```

### Insert

```javascript
// Insert one
db.users.insertOne({
  name: "Alice",
  email: "alice@example.com",
  createdAt: new Date()
});
// → { acknowledged: true, insertedId: ObjectId("...") }

// Insert many
db.users.insertMany([
  { name: "Bob", email: "bob@example.com" },
  { name: "Carol", email: "carol@example.com" }
]);
// → { acknowledged: true, insertedIds: { '0': ObjectId(...), '1': ObjectId(...) } }

// With write concern
db.orders.insertOne(
  { product: "widget", qty: 100 },
  { writeConcern: { w: "majority", j: true } }
);
```

### Update

```javascript
// Update one
db.users.updateOne(
  { email: "alice@example.com" },
  { $set: { status: "premium" }, $inc: { loginCount: 1 } }
);

// Update many
db.users.updateMany(
  { status: "trial" },
  { $set: { status: "expired" } }
);

// Upsert
db.users.updateOne(
  { email: "new@example.com" },
  { $setOnInsert: { createdAt: new Date() }, $set: { name: "New User" } },
  { upsert: true }
);

// Replace entire document
db.users.replaceOne(
  { _id: ObjectId("507f1f77bcf86cd799439011") },
  { name: "Replaced", email: "new@example.com", version: 2 }
);

// Atomic find-and-modify
const before = db.users.findOneAndUpdate(
  { email: "alice@example.com" },
  { $inc: { points: 10 } },
  { returnDocument: "before" }  // "before" or "after"
);
```

### Delete

```javascript
db.users.deleteOne({ email: "old@example.com" });
// → { acknowledged: true, deletedCount: 1 }

db.users.deleteMany({ status: "expired" });

// Atomic find-and-delete (returns deleted doc)
const deleted = db.users.findOneAndDelete({ email: "alice@example.com" });
```

### Bulk Operations

```javascript
const result = await db.users.bulkWrite([
  { insertOne: { document: { name: "U1", email: "u1@example.com" } } },
  { updateOne: {
      filter: { email: "alice@example.com" },
      update: { $set: { status: "active" } }
  }},
  { updateMany: {
      filter: { status: "trial" },
      update: { $set: { notified: true } }
  }},
  { deleteOne: { filter: { email: "spam@example.com" } } },
  { replaceOne: {
      filter: { email: "bob@example.com" },
      replacement: { name: "Bob", email: "bob@example.com", v: 2 }
  }}
], { ordered: true });   // false = don't stop on first error
// → { acknowledged, insertedCount, matchedCount, modifiedCount, deletedCount, ... }
```

### Aggregation

```javascript
db.orders.aggregate([
  { $match: { status: "completed", date: { $gte: ISODate("2025-01-01") } } },
  { $group: { _id: "$customerId", total: { $sum: "$amount" }, count: { $sum: 1 } } },
  { $sort: { total: -1 } },
  { $limit: 10 }
]);

// With pipeline explain
db.orders.explain("executionStats").aggregate([...]);
```

### Admin Commands

```javascript
db.runCommand({ ping: 1 })
db.runCommand({ collStats: "users" })
db.adminCommand({ currentOp: 1 })
db.adminCommand({ killOp: 1, op: <opid> })
db.adminCommand({ listDatabases: 1 })

// Collection management
db.createCollection("logs", { capped: true, size: 10485760, max: 10000 })
db.users.createIndex({ email: 1 }, { unique: true })
db.users.getIndexes()
db.users.dropIndex("email_1")
db.users.drop()
db.dropDatabase()
db.users.renameCollection("accounts")

// Database stats
db.stats()
db.users.stats()
db.users.totalSize()
```

---

## 6. BSON Type Constructors

mongosh uses BSON type constructors that differ from both legacy `mongo` and from raw JSON.

### ObjectId

```javascript
ObjectId()                          // generate new
ObjectId("507f1f77bcf86cd799439011") // from hex string

// Methods
const oid = ObjectId();
oid.toString()      // → "507f1f77bcf86cd799439011"  (hex — reversed from legacy!)
oid.valueOf()       // → 'ObjectId("507f1f77bcf86cd799439011")'
oid.getTimestamp()  // → ISODate of creation
oid.toHexString()   // → "507f1f77bcf86cd799439011"

// In queries
db.users.findOne({ _id: ObjectId("507f1f77bcf86cd799439011") })
```

**Migration note**: In legacy `mongo`, `ObjectId.toString()` returned the formatted string and `.str` returned the hex. In mongosh these are reversed. Also `.str` is removed.

### Dates

```javascript
new Date()              // current UTC — returns Date object, stored as ISODate
ISODate()               // alias for new Date()
new Date("2025-06-15")  // from ISO string
ISODate("2025-06-15T00:00:00Z")

Date()                  // WRONG for storage — returns a STRING, not Date object
                        // only use Date() to see current time as a string

// Usage
db.events.find({ ts: { $gte: ISODate("2025-01-01") } })
db.events.insertOne({ createdAt: new Date() })
```

### Numeric Types

```javascript
// Int32 — 32-bit signed integer (default for whole numbers in mongosh)
Int32(42)
NumberInt(42)          // legacy alias — still works

// Long — 64-bit signed integer
Long("9007199254740993")        // pass as string — an integer literal > 2^53 is truncated by JS before Long sees it
NumberLong("9007199254740993")  // use string to avoid JS precision loss
// Note: NumberLong() in mongosh ONLY accepts strings, not integers

// Decimal128 — 128-bit decimal, 34 significant digits — use for money
Decimal128("19.99")
NumberDecimal("19.99")  // legacy alias

// Double — explicit 64-bit float
Double(3.14)

// Check stored type
typeof db.prices.findOne().amount           // unreliable for BSON
db.prices.findOne().amount.constructor.name // → "Decimal128", "Long", etc.
```

### Binary and UUID

```javascript
// UUID — stored as BinData subtype 4
UUID("3b241101-e2bb-4255-8caf-4136c566a962")
// or
BinData(4, "<base64-encoded-value>")

// Generic binary
BinData(0, "dGhpcyBpcyBhIHRlc3Q=")   // subtype 0, base64 value
```

### Timestamps (internal BSON type)

```javascript
// Timestamp — BSON internal type (NOT for user dates; used by oplog)
Timestamp()                            // current time, increment 1
Timestamp({ t: 1686000000, i: 1 })    // explicit seconds + increment
Timestamp(1686000000, 1)               // positional: (t, i)
```

### Other Types

```javascript
MinKey()          // less than all BSON values
MaxKey()          // greater than all BSON values

// EJSON — extended JSON for type-safe serialization
EJSON.stringify(db.users.findOne())
// → '{"_id":{"$oid":"..."},"createdAt":{"$date":"..."}}'

EJSON.parse('{"_id":{"$oid":"507f1f77bcf86cd799439011"}}')
// → { _id: ObjectId("507f1f77bcf86cd799439011") }

// Type queries using $type
db.data.find({ field: { $type: "int" } })      // Int32
db.data.find({ field: { $type: "long" } })     // Long
db.data.find({ field: { $type: "decimal" } })  // Decimal128
db.data.find({ field: { $type: "date" } })     // Date
```

---

## 7. Scripting and Automation

### `--eval` One-liners

```bash
# Simple query
mongosh "mongodb://localhost/mydb" --eval 'db.users.countDocuments()'

# Machine-readable JSON output (use with --quiet to suppress prompts)
mongosh --quiet --json=relaxed --eval 'db.users.find({active:true}).toArray()'

# Multiple --eval args — only last result printed
mongosh --eval 'use mydb' --eval 'db.stats()'

# Stay in REPL after eval
mongosh --eval 'use mydb' --shell
```

### `--file` Script Execution

```bash
# Run a script
mongosh --file /path/to/script.js
mongosh -f script.js

# With auth
mongosh -u admin -p secret --authenticationDatabase admin -f script.js

# Multiple scripts in order
mongosh -f setup.js -f seed.js -f verify.js

# Best practice: use --file explicitly, not positional
mongosh "mongodb://localhost/mydb" --file script.js
```

### `load()` — Script from within mongosh

```javascript
// Absolute path (preferred for automation)
load("/path/to/helpers.js")

// Relative to CWD where mongosh was launched
load("scripts/seed.js")

// Access script path inside loaded script
__filename   // absolute path of current script
__dirname    // directory of current script
```

### Script Structure and Exit Codes

```javascript
// script.js — portable pattern (no hardcoded connection)
try {
  const count = db.getSiblingDB("mydb").users.countDocuments({ active: true });
  print(`Active users: ${count}`);

  if (count === 0) {
    exit(1);   // non-zero = failure for CI
  }

  exit(0);     // explicit success
} catch (err) {
  print("Error: " + err.message);
  exit(1);
}
```

Run it: `mongosh --host mongo.example.com --file check.js`

Exit code convention: `exit(0)` = success, `exit(N)` where N > 0 = failure. CI tools like GitHub Actions / Jenkins read `$?`.

### Output Functions

```javascript
print("plain string")
printjson({ key: "value" })   // pretty-print with BSON awareness

// EJSON for type-preserving output — best for machine parsing
EJSON.stringify(db.users.findOne())
// → '{"_id":{"$oid":"..."},"createdAt":{"$date":"..."},...}'

// Relaxed EJSON (numbers stay as numbers, not wrapped)
EJSON.stringify(db.users.findOne(), null, 2)

// JSON.stringify — loses BSON type info (ObjectId → undefined, Date → string)
// Use only when you know all values are plain JS types
JSON.stringify(db.stats())
```

### Passing Variables between `--eval` and `--file`

```bash
# Set a variable in --eval, then load script that uses it
mongosh --eval 'var ENV = "staging"; var DB_NAME = "myapp_staging"' --file deploy.js

# Inside deploy.js:
# const db = db.getSiblingDB(DB_NAME);  // uses ENV variable from --eval
```

### CI/CD Integration Pattern

```bash
#!/bin/bash
mongosh \
  --quiet \
  --norc \
  --username "$MONGO_USER" \
  --password "$MONGO_PASS" \
  --authenticationDatabase admin \
  "mongodb://$MONGO_HOST:27017/mydb" \
  --file /scripts/migrate.js

if [ $? -ne 0 ]; then
  echo "Migration failed"
  exit 1
fi
```

---

## 8. Snippet System

Snippets are experimental npm packages that extend mongosh with additional shell functions. Requires npm to be installed.

### Core Commands

```bash
# List available snippets from registry
snippet search
snippet search schema      # filter by keyword

# Install a snippet
snippet install analyze-schema

# List installed snippets
snippet ls

# Get help / README for a snippet
snippet help analyze-schema

# Update installed snippets
snippet refresh

# Uninstall
snippet uninstall analyze-schema

# View registry info
snippet info
```

### Built-in / Well-Known Snippets

| Snippet | Usage | Description |
|---|---|---|
| `analyze-schema` | `schema(db.collection)` | Sample collection and display schema with type frequencies |
| `mongocompat` | Adds legacy shell functions | Restores `Array.sum()`, `tojsononeline()`, and other legacy helpers |
| `resumetoken` | Decode change stream tokens | Parse and inspect change stream resume tokens |
| `spawn-mongod` | Start local mongod | Spin up a temporary mongod for testing |
| `mock-collection` | Mock data testing | Create in-memory mock collections |

```javascript
// After: snippet install analyze-schema
schema(db.reservations)
// → table showing field names, presence %, and BSON types

// After: snippet install mongocompat
Array.sum([1, 2, 3])        // → 6
tojsononeline({ a: 1 })    // → '{ "a" : 1 }'
```

### Custom Snippet Registry

```javascript
// View current registry URL
config.get('snippetIndexSourceURLs')

// Add a private registry (semicolon-separated)
config.set('snippetIndexSourceURLs',
  'https://compass.mongodb.com/mongosh/snippets-index.bson.br;' +
  'https://internal.corp.com/mongosh-snippets/index.bson.br'
)

// Set custom npm registry for snippet installs
config.set('snippetRegistryURL', 'https://registry.npmjs.internal.corp.com')
```

### Disable Auto-load

```javascript
// Stop installed snippets from loading on every startup
config.set('snippetAutoload', false)
```

**Note**: Snippets are experimental and unsupported by MongoDB Inc. They are community-maintained at `github.com/mongodb-labs/mongosh-snippets`.

---

## 9. Transactions from mongosh

Multi-document ACID transactions require MongoDB 4.0+ replica sets or 4.2+ sharded clusters.

### Manual Transaction Pattern

```javascript
const session = db.getMongo().startSession();

session.startTransaction({
  readConcern:  { level: "snapshot" },
  writeConcern: { w: "majority" }
});

try {
  const orders    = session.getDatabase("mydb").orders;
  const inventory = session.getDatabase("mydb").inventory;

  await orders.insertOne(
    { product: "widget", qty: 5, customerId: "C123" },
    { session }
  );

  await inventory.updateOne(
    { product: "widget" },
    { $inc: { stock: -5 } },
    { session }
  );

  await session.commitTransaction();
  print("Transaction committed");
} catch (err) {
  await session.abortTransaction();
  print("Aborted: " + err.message);
} finally {
  session.endSession();
}
```

### `withTransaction()` — Recommended (Automatic Retry)

```javascript
const session = db.getMongo().startSession();

await session.withTransaction(async () => {
  const accounts = session.getDatabase("banking").accounts;

  await accounts.updateOne(
    { _id: "A" },
    { $inc: { balance: -100 } },
    { session }
  );

  await accounts.updateOne(
    { _id: "B" },
    { $inc: { balance: 100 } },
    { session }
  );
});

session.endSession();
```

`withTransaction()` automatically:
- Retries on `TransientTransactionError`
- Retries commit on `UnknownTransactionCommitResult`
- Aborts and rolls back if the callback throws

### Transaction Options

```javascript
session.startTransaction({
  readConcern:     { level: "snapshot" },   // or "local", "majority"
  writeConcern:    { w: "majority", j: true },
  maxCommitTimeMS: 2000                      // timeout for commit
});
```

### Session State Methods

```javascript
session.getTransactionState()     // → "NO_TRANSACTION" | "STARTING" | "TRANSACTION" | "COMMITTED" | "ABORTED"
session.inTransaction()           // → boolean
session.getDatabase("dbname")     // get DB handle bound to this session
session.endSession()              // always call in finally block
```

---

## 10. Performance and Diagnostic Helpers

### Query Explain

```javascript
// Get execution plan
db.users.explain().find({ email: "alice@example.com" })

// With execution stats (runs query)
db.users.explain("executionStats").find({ email: "alice@example.com" })

// With all plans (slower, tests all candidate plans)
db.users.explain("allPlansExecution").find({ email: "alice@example.com" })

// Aggregate explain
db.orders.explain("executionStats").aggregate([
  { $match: { status: "completed" } },
  { $group: { _id: "$customerId", total: { $sum: "$amount" } } }
])

// Key fields to check in executionStats
// executionStats.totalDocsExamined  — should be close to nReturned
// executionStats.totalKeysExamined  — index keys scanned
// winningPlan.stage — COLLSCAN (bad), IXSCAN (good), FETCH, SORT
```

### Current Operations

```javascript
// List all running operations
db.currentOp()

// Filter to slow operations (> 5 seconds)
db.currentOp({ secs_running: { $gt: 5 } })

// Show only active operations, exclude idle
db.currentOp({ active: true, op: { $ne: "none" } })

// Kill an operation by opid
db.killOp(12345)

// Via adminCommand (same result)
db.adminCommand({ currentOp: 1, active: true })
db.adminCommand({ killOp: 1, op: 12345 })
```

### Query Profiler

```javascript
// Get current profiling level
db.getProfilingLevel()        // → 0 (off), 1 (slow), 2 (all)
db.getProfilingStatus()       // → { was: 0, slowms: 100, sampleRate: 1 }

// Enable profiling
db.setProfilingLevel(0)                    // off
db.setProfilingLevel(1, { slowms: 100 })   // slow ops > 100ms
db.setProfilingLevel(2)                    // all operations (dev only!)

// Query the profiler
db.system.profile.find().sort({ ts: -1 }).limit(10)

// Find slow queries specifically
db.system.profile.find(
  { millis: { $gt: 200 }, op: "query" }
).sort({ millis: -1 }).limit(5)

// Key fields in profile output
// millis — execution time
// ns — namespace (db.collection)
// op — command type (query, update, insert, command)
// planSummary — COLLSCAN vs IXSCAN
// keysExamined / docsExamined — scan efficiency
```

**Warning**: Level 2 profiling degrades performance and writes unencrypted query data including field values to system.profile. Avoid on production.

### Server and Replication Status

```javascript
// Server metrics
db.serverStatus()
db.serverStatus().connections   // connection pool stats
db.serverStatus().opcounters    // operations/second by type
db.serverStatus().mem           // memory usage
db.serverStatus().metrics       // detailed counters

// Database and collection statistics
db.stats()
db.users.stats()
db.users.totalSize()
db.users.storageSize()

// Replica set
rs.status()                     // replica set member states, lag, heartbeat
rs.conf()                       // replica set configuration
rs.isMaster()                   // deprecated; use hello()
db.hello()                      // primary/secondary info

// Sharding
sh.status()                     // sharding topology, chunk distribution
sh.balancerStatus()             // balancer on/off, running
db.adminCommand({ listShards: 1 })  // list shard members
```

### Index Diagnostics

```javascript
// List indexes
db.users.getIndexes()

// Per-index usage stats via $indexStats aggregation stage
db.users.aggregate([{ $indexStats: {} }])

// Check if index is being used (look for IXSCAN in explain)
db.users.explain("executionStats").find({ email: "x" })

// Find unused indexes (accesses.ops = 0 since last mongod restart)
db.users.aggregate([
  { $indexStats: {} },
  { $match: { "accesses.ops": 0 } }
])

// Index size
db.users.stats().indexSizes
```

### Useful Diagnostic Patterns

```javascript
// Find top 5 collections by document count
db.getCollectionNames()
  .map(n => ({ name: n, count: db[n].estimatedDocumentCount() }))
  .sort((a, b) => b.count - a.count)
  .slice(0, 5)

// Check replication lag (seconds behind primary)
rs.status().members
  .filter(m => m.stateStr === "SECONDARY")
  .map(m => ({ host: m.name, lagSecs: m.optimeDate && (new Date() - m.optimeDate) / 1000 }))

// Kill all ops longer than 30 seconds — CAUTION: review ops before killing in production
// Run db.currentOp({ secs_running: { $gt: 30 } }) first to inspect, then kill selectively
db.currentOp({ secs_running: { $gt: 30 } })
  .inprog
  .forEach(op => {
    print(`Killing op ${op.opid}: ${op.op} on ${op.ns} (${op.secs_running}s)`);
    db.killOp(op.opid);
  })
```

---

## References and See Also

### Official Documentation
- [mongosh Overview](https://www.mongodb.com/docs/mongodb-shell/) — main entry point
- [mongosh Reference — Options](https://www.mongodb.com/docs/mongodb-shell/reference/options/) — all CLI flags
- [mongosh Compatibility Changes](https://www.mongodb.com/docs/mongodb-shell/reference/compatibility/) — legacy shell migration
- [mongosh Data Types](https://www.mongodb.com/docs/mongodb-shell/reference/data-types/) — BSON constructors
- [mongosh Configure Settings](https://www.mongodb.com/docs/mongodb-shell/reference/configure-shell-settings/) — config API + YAML
- [mongosh Write Scripts](https://www.mongodb.com/docs/mongodb-shell/write-scripts/) — scripting guide
- [mongosh Snippets](https://www.mongodb.com/docs/mongodb-shell/snippets/) — snippet system
- [mongosh .mongoshrc.js](https://www.mongodb.com/docs/mongodb-shell/mongoshrc/) — startup config
- [GitHub: mongodb-js/mongosh](https://github.com/mongodb-js/mongosh) — source + issue tracker

### See Also (Related Skills)
- [[mongodb-expert]] — MongoDB query patterns, operators, aggregation pipeline
- [[mongodb-developer]] — MongoDB application development patterns
- [[mongodb-bson-types]] — Deep BSON type reference including encoding details
- [[mongodb-performance-troubleshooting]] — Query optimization, index strategy, slow query analysis
- [[mongodb-aggregation-pipeline]] — Aggregation stages and pipeline construction
- [[mongodb-transactions]] — Multi-document transaction patterns and error handling
