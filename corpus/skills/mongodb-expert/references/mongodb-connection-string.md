<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-connection-string` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-connection-string
title: MongoDB Connection String URI Reference
version: "1.1.0"
last-updated: "2026-05-29"
category: mongodb
description: >
  Complete reference for MongoDB connection string URI formats and options.
  TRIGGER: building or debugging a MongoDB connection string (mongodb:// or mongodb+srv://),
  configuring authentication mechanisms (SCRAM, MONGODB-AWS, X.509, GSSAPI, OIDC, PLAIN),
  setting up TLS/mTLS for Atlas or self-hosted deployments, tuning connection pool settings
  (maxPoolSize, minPoolSize, maxConnecting, maxIdleTimeMS), choosing read preference for
  secondary reads, setting write concern and read concern, enabling retryWrites/retryReads,
  understanding CSOT (timeoutMS / Client-Side Operations Timeout), enabling wire protocol
  compression (snappy, zlib, zstd), configuring topology options (directConnection,
  loadBalanced, replicaSet), percent-encoding special characters in passwords, or handling
  driver-specific quirks across Node.js, Python, Java, .NET, and Go.
  SKIP: driver API usage beyond connection setup (use mongodb-developer or mongodb-driver-internals),
  Atlas-specific cluster networking like VPC peering or PrivateLink (use mongodb-aws-networking),
  AWS IAM / Atlas access manager configuration (use mongodb-atlas-iam-rbac),
  MongoDB replication topology design (use mongodb-replication).
tags:
  - mongodb
  - connection
  - uri
  - driver
  - authentication
  - tls
  - connection-pool
  - read-preference
  - write-concern
keywords:
  - "mongodb connection string"
  - "mongodb uri"
  - "mongodb+srv"
  - "maxPoolSize"
  - "retryWrites"
  - "authMechanism"
  - "tls mongodb"
  - "serverSelectionTimeoutMS"
  - "connection pool mongodb"
  - "readPreference mongodb"
  - "authSource mongodb"
  - "SCRAM-SHA-256"
  - "MONGODB-AWS"
  - "tlsCAFile"
  - "maxIdleTimeMS"
  - "timeoutMS CSOT"
  - "compressors mongodb"
  - "directConnection"
  - "loadBalanced"
  - "replicaSet connection string"
  - "MONGODB-OIDC"
  - "GSSAPI Kerberos"
  - "mTLS mutual TLS"
whenToUse:
  - Building or debugging a MongoDB connection string from scratch
  - Configuring authentication: SCRAM, MONGODB-AWS, X.509, GSSAPI, PLAIN, OIDC
  - Setting up TLS or mutual TLS for Atlas or self-hosted MongoDB
  - Tuning connection pool: maxPoolSize, minPoolSize, maxConnecting, maxIdleTimeMS
  - Configuring read preference for secondary reads or Analytics Nodes
  - Setting write concern (w:majority) or read concern in the connection string
  - Enabling or disabling retryWrites / retryReads
  - Debugging serverSelectionTimeoutMS or connectTimeoutMS timeouts
  - Enabling wire protocol compression (snappy, zlib, zstd)
  - Connecting with directConnection or loadBalanced mode for Serverless/Flex
  - Understanding mongodb+srv SRV DNS auto-discovery vs standard format
  - Percent-encoding special characters in usernames or passwords
  - Configuring CSOT (timeoutMS) client-side operations timeout
  - Driver-specific connection options: Node.js, Python, Java, .NET, Go
whenNotToUse:
  - MongoDB driver API usage beyond connection setup — use mongodb-developer or mongodb-driver-internals
  - Atlas cluster networking (VPC peering, PrivateLink, IP allowlist) — use mongodb-aws-networking or mongodb-atlas-expert
  - AWS IAM access configuration or Atlas RBAC — use mongodb-atlas-iam-rbac
  - Replica set topology design and election tuning — use mongodb-replication
  - Connection pool exhaustion diagnosis in a running system — use mongodb-performance-troubleshooting
related_skills:
  - mongodb-developer
  - mongodb-driver-internals
  - mongodb-security-architecture
  - mongodb-atlas-expert
  - mongodb-performance-troubleshooting
  - mongodb-atlas-iam-rbac
  - mongodb-replication
  - mongodb-transactions
---

# MongoDB Connection String URI Reference

## Overview + When to Use

This skill covers every facet of MongoDB connection strings — from the two URI formats (Standard and SRV) through every configurable option group. Use it when:

- Composing a connection string from scratch for Atlas, replica set, or standalone
- Debugging authentication failures (`authMechanism`, `authSource`, credential encoding)
- Configuring TLS for Atlas, mutual TLS, or self-hosted deployments
- Tuning connection pool behavior (`maxPoolSize`, `maxConnecting`, `waitQueueTimeoutMS`)
- Choosing the right read preference and understanding staleness
- Setting write/read concern guarantees for transactions or operations
- Enabling wire protocol compression to reduce bandwidth
- Understanding topology options (`replicaSet`, `directConnection`, `loadBalanced`)
- Using the new Client-Side Operations Timeout (`timeoutMS` / CSOT)
- Handling driver-specific quirks across Node.js, Python, Java, and Go

**Quick rule of thumb:** When in doubt, use the SRV format (`mongodb+srv://`) for Atlas and DNS-managed replica sets. Use the standard format (`mongodb://`) for self-hosted, localhost, or when you need direct port control.

---

## 1. URI Formats

### 1.1 Standard Format (`mongodb://`)

```text
mongodb://[username:password@]host1[:port1][,host2[:port2],...][/[defaultauthdb][?options]]
```

**Components:**

| Component | Required | Notes |
|-----------|----------|-------|
| `mongodb://` | Yes | Scheme prefix |
| `username:password@` | No | Percent-encode special chars in both fields |
| `host[:port]` | Yes | Hostname or IP; default port is `27017` |
| `,host2[:port2]` | No | Comma-separated additional hosts for replica sets |
| `/defaultauthdb` | No | Default auth database; falls back to `admin` |
| `?options` | No | Key-value pairs separated by `&` |

**Single standalone:**
```text
mongodb://localhost:27017/mydb
```

**Authenticated standalone:**
```text
mongodb://alice:s%40feP%40ss@localhost:27017/mydb?authSource=admin
```

**Replica set (3 members):**
```text
mongodb://user:pass@host1:27017,host2:27017,host3:27017/mydb?replicaSet=rs0
```

**Notes:**
- The `defaultauthdb` path component sets the default authentication database only when `authSource` is NOT specified.
- Authentication database resolution order: explicit `authSource` option → `defaultauthdb` path → `admin`.
- Multiple hosts require `replicaSet=<name>` to avoid topology ambiguity.
- UNIX domain sockets are supported: `mongodb://%2Ftmp%2Fmongodb-27017.sock/mydb`.

### 1.2 DNS Seedlist Format (`mongodb+srv://`)

```text
mongodb+srv://[username:password@]host[/[defaultauthdb][?options]]
```

**Key rules:**
- Exactly **one hostname**, no port.
- The driver queries `_mongodb._tcp.<host>` SRV DNS records to discover all members.
- Optional TXT record at `<host>` can specify `replicaSet=<name>&authSource=<db>`.
- Query string options override TXT record values.
- **TLS is enabled by default** (implicit `tls=true`).

**How DNS resolution works:**
```text
DNS SRV query: _mongodb._tcp.cluster0.example.net
→ mongodb1.example.net:27017
→ mongodb2.example.net:27017
→ mongodb3.example.net:27017

DNS TXT query: cluster0.example.net
→ "authSource=admin&replicaSet=atlas-xyz"
```

**Atlas SRV example (copied from Atlas UI):**
```text
mongodb+srv://myuser:mypassword@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
```

**Notes:**
- Atlas **always uses SRV format** except for online archive endpoints.
- `srvMaxHosts` caps how many hosts are selected from the SRV record (default `0` = unlimited; useful for sharded cluster `mongos` selection).
- `srvServiceName` overrides the default `mongodb` SRV service name (default: `mongodb`).
- If DNS is unavailable and no cached records exist, connection fails immediately.

### 1.3 Standard vs SRV Comparison

| Feature | `mongodb://` | `mongodb+srv://` |
|---------|-------------|-----------------|
| Multiple hosts in URI | Yes, comma-separated | No, single hostname only |
| Port specification | Yes | No (from DNS) |
| TLS default | `false` | `true` (auto-enabled) |
| Auto-discovers members | No | Yes (via DNS SRV) |
| DNS TXT record config | No | Yes (`replicaSet`, `authSource`) |
| Works without DNS | Yes | No |
| Atlas standard | No (legacy) | Yes |
| Best for | Localhost, self-hosted, direct | Atlas, DNS-managed replica sets |

---

## 2. Authentication Options

### 2.1 Special Character Encoding

Usernames and passwords must **percent-encode** any of these characters:

| Char | Encoded | Char | Encoded |
|------|---------|------|---------|
| `@` | `%40` | `#` | `%23` |
| `:` | `%3A` | `[` | `%5B` |
| `/` | `%2F` | `]` | `%5D` |
| `?` | `%3F` | `$` | `%24` |

Password `P@ss/w0rd!` → `P%40ss%2Fw0rd!`

### 2.2 Core Auth Options

| Option | Default | Type | Description |
|--------|---------|------|-------------|
| `authSource` | `admin` | string | Database where user credentials are stored. Set to `$external` for PLAIN, GSSAPI, MONGODB-AWS, MONGODB-X509 |
| `authMechanism` | auto-negotiated | string | Explicit auth mechanism. Drivers auto-negotiate SCRAM-SHA-256 or SCRAM-SHA-1 when omitted |
| `authMechanismProperties` | — | string | Comma-separated `KEY:VALUE` pairs for mechanism-specific settings |
| `gssapiServiceName` | `mongodb` | string | **Deprecated** — use `authMechanismProperties=SERVICE_NAME:name` instead |

### 2.3 authMechanism Values

| Mechanism | Use Case | Notes |
|-----------|----------|-------|
| `SCRAM-SHA-256` | Standard username/password (MongoDB 4.0+) | Default for modern deployments |
| `SCRAM-SHA-1` | Legacy username/password | Use only for pre-4.0 compatibility |
| `MONGODB-X509` | Client TLS certificate | No username/password in URI; requires `tls=true` + `tlsCertificateKeyFile` |
| `MONGODB-AWS` | AWS IAM credentials | Requires `authSource=$external`; uses EC2/ECS/Lambda env for creds |
| `GSSAPI` | Kerberos (Enterprise only) | Requires `authSource=$external`; needs OS Kerberos ticket |
| `PLAIN` | LDAP (Enterprise only) | Requires `authSource=$external`; credentials sent plaintext over TLS |
| `MONGODB-OIDC` | OpenID Connect (MongoDB 7.0+) | Requires `authSource=$external`; cloud-managed identity |

### 2.4 authMechanismProperties Reference

| Property Key | Mechanism | Description |
|-------------|-----------|-------------|
| `SERVICE_NAME` | GSSAPI | Kerberos service name (default: `mongodb`) |
| `CANONICALIZE_HOST_NAME` | GSSAPI | Hostname canonicalization: `none`, `forward`, `forwardAndReverse` |
| `SERVICE_REALM` | GSSAPI | Kerberos realm override |
| `AWS_SESSION_TOKEN` | MONGODB-AWS | STS session token for temporary credentials |
| `ENVIRONMENT` | MONGODB-AWS | `aws`, `gcp`, `azure` for credential provider selection |
| `TOKEN_RESOURCE` | MONGODB-OIDC | Azure/GCP resource URI |

### 2.5 Authentication Examples

**SCRAM-SHA-256 (default):**
```text
mongodb://alice:s3cr3t@host:27017/mydb?authSource=admin
```

**MONGODB-X509 (no password):**
```text
mongodb://host:27017/?authMechanism=MONGODB-X509&tls=true&tlsCertificateKeyFile=/certs/client.pem&authSource=$external
```

**MONGODB-AWS with session token:**
```text
mongodb://host:27017/?authMechanism=MONGODB-AWS&authMechanismProperties=AWS_SESSION_TOKEN:sess123&authSource=$external
```

**GSSAPI (Kerberos):**
```text
mongodb://user%40DOMAIN.COM@host:27017/?authMechanism=GSSAPI&authSource=$external&authMechanismProperties=SERVICE_NAME:mongodb
```

---

## 3. TLS/SSL Options

Atlas requires TLS on all connections. Self-hosted deployments with `tls=true` follow the same option set.

### 3.1 TLS Option Reference

| Option | Default | Type | Description |
|--------|---------|------|-------------|
| `tls` | `false` (std), `true` (SRV) | boolean | Enable TLS/SSL. `ssl` is a deprecated synonym |
| `tlsCAFile` | system CA store | string | Path to PEM file with CA certificate chain for server verification |
| `tlsCertificateKeyFile` | — | string | Path to PEM file containing client certificate + private key (for mutual TLS) |
| `tlsCertificateKeyFilePassword` | — | string | Password for encrypted private key in `tlsCertificateKeyFile` |
| `tlsInsecure` | `false` | boolean | **Dangerous.** Disables all certificate and hostname validation |
| `tlsAllowInvalidCertificates` | `false` | boolean | Skip server certificate verification (allows self-signed certs) |
| `tlsAllowInvalidHostnames` | `false` | boolean | Skip hostname verification (cert CN/SAN not checked) |
| `tlsDisableCertificateRevocationCheck` | `false` | boolean | Skip OCSP/CRL revocation check |
| `tlsDisableOCSPEndpointCheck` | `false` | boolean | Skip only OCSP endpoint check |

**Warning:** `tlsInsecure=true` sets both `tlsAllowInvalidCertificates=true` and `tlsAllowInvalidHostnames=true`. Never use in production.

### 3.2 TLS Examples

**Standard TLS (server certificate validated via system CA):**
```text
mongodb://host:27017/mydb?tls=true
```

**Custom CA (self-signed or private CA):**
```text
mongodb://host:27017/mydb?tls=true&tlsCAFile=/etc/ssl/ca.pem
```

**Mutual TLS (mTLS) — client presents a certificate:**
```text
mongodb://host:27017/mydb?tls=true&tlsCAFile=/certs/ca.pem&tlsCertificateKeyFile=/certs/client.pem&tlsCertificateKeyFilePassword=keypass
```

**Atlas (SRV — TLS is implicit):**
```text
mongodb+srv://user:pass@cluster0.abcde.mongodb.net/mydb?retryWrites=true&w=majority
```

**Direct connection to replica set member (bypasses discovery, TLS on):**
```text
mongodb://replicaMember1:27017/mydb?directConnection=true&tls=true
```

**Development with self-signed cert (never production):**
```text
mongodb://host:27017/mydb?tls=true&tlsAllowInvalidCertificates=true
```

### 3.3 Certificate Format Notes

- MongoDB requires the client certificate and private key to be **concatenated in a single PEM file** for `tlsCertificateKeyFile`.
- The CA chain in `tlsCAFile` should include the full chain to the root.
- For X.509 authentication, the username in the URI must match the Subject or CN from the certificate, or can be omitted entirely (driver derives it from the cert).

---

## 4. Connection Pool Options

The driver maintains a pool of persistent connections per server in the topology. Getting pool settings right is critical for throughput and latency under load.

### 4.1 Pool Option Reference

| Option | Default | Type | Description |
|--------|---------|------|-------------|
| `maxPoolSize` | `100` | integer | Maximum total connections (in-use + idle) per server |
| `minPoolSize` | `0` | integer | Minimum idle connections maintained. Pool pre-warms to this count at startup |
| `maxConnecting` | `2` | integer | Max connections being established concurrently. Prevents thundering herd. Not supported in Rust driver |
| `maxIdleTimeMS` | no limit | integer | Milliseconds a connection can be idle before the pool removes and replaces it |
| `waitQueueTimeoutMS` | driver-specific | integer | Max time (ms) a thread waits for an in-use connection to be returned. `0` = no limit |
| `connectTimeoutMS` | `30000` | integer | Timeout for establishing a new TCP connection to a server (ms) |
| `socketTimeoutMS` | no timeout | integer | **Deprecated.** TCP socket send/receive timeout. Do not use to prevent slow operations — use `timeoutMS` instead |

### 4.2 Pool Behavior

```text
New request arrives
  → Is an idle connection available? → YES → use it
  → NO: is pool size < maxPoolSize?
      → YES: is current connecting count < maxConnecting?
          → YES → establish new connection (async)
          → NO  → wait for a connecting slot to free up (bounded by connectTimeoutMS)
      → NO → wait up to waitQueueTimeoutMS for an in-use connection to be returned
```

### 4.3 Tuning Guidelines

**Serverless / Lambda / short-lived processes:**
```text
maxPoolSize=5&minPoolSize=0&maxIdleTimeMS=10000
```

**High-throughput API server:**
```text
maxPoolSize=200&minPoolSize=10&maxConnecting=4&maxIdleTimeMS=120000
```

**Prevent connection storms on startup:**
- Keep `maxConnecting=2` (default) unless you profile a startup bottleneck
- Set `minPoolSize` > 0 to pre-warm the pool before traffic hits

**Atlas M0/M2/M5 free tiers:**
- Enforce low connection limits — keep `maxPoolSize=5` or lower

---

## 5. Read Preference Options

Read preference determines which cluster members the driver routes read operations to.

### 5.1 Option Reference

| Option | Default | Type | Description |
|--------|---------|------|-------------|
| `readPreference` | `primary` | string | Read routing mode |
| `readPreferenceTags` | — | string | Comma-separated `key:value` tags to filter members |
| `maxStalenessSeconds` | no limit | integer | Maximum allowed replication lag (seconds) for secondary reads. Minimum: `90` |
| `hedgedReads` | `false` | boolean | Atlas only. Sends parallel read to two members, uses fastest response |

### 5.2 readPreference Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `primary` | Always reads from primary | Strong consistency requirement |
| `primaryPreferred` | Primary if available; secondary on failover | High availability with consistency preference |
| `secondary` | Always reads from a secondary | Offload read traffic from primary |
| `secondaryPreferred` | Secondary if available; primary if no secondary | Analytics, reporting; tolerates stale data |
| `nearest` | Lowest network latency member (any role) | Globally distributed reads; geographically local data |

> **Note:** There is no `analytics` read-preference *mode*. Atlas Analytics Nodes are targeted with `readPreference=secondary` plus `readPreferenceTags=nodeType:ANALYTICS` (see §5.3).

### 5.3 Tag Sets

Tags filter which members are eligible. Multiple `readPreferenceTags` parameters are tried in order (fallback chain):

```text
mongodb://host/db?readPreference=secondary&readPreferenceTags=nodeType:ANALYTICS&readPreferenceTags=
```

The trailing empty `readPreferenceTags=` acts as a catch-all fallback.

**Atlas Analytics Node example:**
```text
mongodb+srv://user:pass@cluster0.abcde.mongodb.net/?readPreference=secondary&readPreferenceTags=nodeType:ANALYTICS
```

### 5.4 maxStalenessSeconds

The driver estimates each secondary's staleness using `lastWriteDate` from `hello` responses and excludes members lagging beyond this threshold.

- **Minimum value: 90 seconds** (smaller values cause an error)
- **Not compatible with `primary` mode** (will error)
- **Formula check:** `maxStalenessSeconds` must be >= `heartbeatFrequencyMS / 1000 + 10`

```text
mongodb://host/db?readPreference=secondaryPreferred&maxStalenessSeconds=120
```

---

## 6. Write Concern and Read Concern Options

### 6.1 Write Concern Options

| Option | Default | Type | Description |
|--------|---------|------|-------------|
| `w` | `1` (server default) | integer or string | Acknowledgment level: `0` (no ack), `1` (primary only), `<N>` (N members), `majority`, or a custom tag set name |
| `wTimeoutMS` | no timeout | integer | **Deprecated** (use `timeoutMS`). Max time (ms) to wait for write concern acknowledgment |
| `journal` | `false` | boolean | Require write to be committed to on-disk journal before acknowledgment. Alias: `j=true` |

**Atlas default:** Atlas clusters default to `w=majority`.

**Write concern levels explained:**

| `w` Value | Meaning |
|-----------|---------|
| `0` | Fire-and-forget — no acknowledgment |
| `1` | Primary acknowledges only |
| `2` | Primary + 1 secondary |
| `majority` | Majority of voting members (durable across elections) |
| `"tagName"` | All members with a specific replica set tag |

**Examples:**
```text
# Safe for most workloads
mongodb://host/db?w=majority&journal=true

# High-throughput bulk inserts — WARNING: w=0 means no acknowledgment; data loss
# is possible on network error or primary failure. Never use for important data.
mongodb://host/db?w=0

# Fast with durability
mongodb://host/db?w=1&journal=true
```

### 6.2 Read Concern Options

| Option | Default | Type | Description |
|--------|---------|------|-------------|
| `readConcernLevel` | `local` | string | Isolation level for read operations |

**Read concern levels:**

| Level | Guarantees | Use Case |
|-------|-----------|---------|
| `local` | Returns most recent data from the queried member; may be rolled back | Default; general reads |
| `available` | Like `local` but for sharded clusters; ignores orphan documents | Sharded reads where orphans are tolerable |
| `majority` | Returns data acknowledged by a majority of nodes; durable | Causal consistency, transactions |
| `linearizable` | Reads reflect all prior majority-committed writes; single-document reads only | Strongest isolation; high latency |
| `snapshot` | Point-in-time consistent view (multi-document transactions, MongoDB 5.0+) | Transactions only |

**Example:**
```text
mongodb://host/db?readConcernLevel=majority&w=majority&journal=true
```

---

## 7. Compression Options

Wire protocol compression reduces bytes transferred between client and server. Effective for large documents and high-latency networks.

### 7.1 Option Reference

| Option | Default | Type | Description |
|--------|---------|------|-------------|
| `compressors` | none | string | Comma-separated ordered list of compressor algorithms to advertise to the server |
| `zlibCompressionLevel` | `-1` (OS default, ~6) | integer | Zlib compression level: `-1` (default), `0` (no compression), `1` (fastest) to `9` (best ratio) |

### 7.2 Compressor Algorithms

| Algorithm | Speed | Ratio | Notes |
|-----------|-------|-------|-------|
| `snappy` | Fastest | Moderate | Google's Snappy; good for general use. May require extra install (Python, Go, Java) |
| `zlib` | Medium | Good | Built into most runtimes; level-tunable |
| `zstd` | Fast | Best | Zstandard; MongoDB 4.2+ and modern drivers; may require extra install |

**Ordering matters:** The client sends its list in preference order. The server selects the first match.

```text
# Prefer zstd, fall back to snappy, then zlib
mongodb://host/db?compressors=zstd,snappy,zlib

# Zlib only with max compression
mongodb://host/db?compressors=zlib&zlibCompressionLevel=9
```

### 7.3 When Compression Helps vs Hurts

**Helps when:**
- High-latency connections (cross-region, WAN)
- Large documents or large result sets
- CPU has spare capacity

**Hurts (avoid) when:**
- Data is already compressed (JPEG, PNG, gzip files, encrypted blobs)
- CPU-bound workloads — compression adds CPU overhead
- Very small documents — overhead exceeds savings
- Low-latency LAN deployments — bandwidth is rarely the bottleneck

---

## 8. Replica Set and Topology Options

### 8.1 Option Reference

| Option | Default | Type | Description |
|--------|---------|------|-------------|
| `replicaSet` | — | string | Name of the replica set. Required when using standard `mongodb://` to connect to a replica set |
| `directConnection` | `false` | boolean | Connect to exactly one host; skip topology discovery and replica set negotiation |
| `loadBalanced` | `false` | boolean | Operates in load-balanced mode. Required for Atlas Serverless and Flex clusters. Single host only |
| `srvMaxHosts` | `0` (unlimited) | integer | Cap the number of hosts selected from a DNS SRV seedlist. Useful for sharded cluster `mongos` selection |
| `srvServiceName` | `mongodb` | string | Override the SRV service name in DNS lookup. Rarely changed |

### 8.2 Topology Decision Tree

```text
Connecting to Atlas (any tier)?
  → Use mongodb+srv:// (SRV auto-handles topology)

Connecting to a self-hosted replica set?
  → mongodb://h1:27017,h2:27017,h3:27017/db?replicaSet=rs0

Connecting directly to a specific member (primary or secondary) without discovery?
  → mongodb://h1:27017/db?directConnection=true
  → Note: directConnection=true also works for mongos in sharded clusters

Atlas Serverless or Flex clusters?
  → mongodb+srv://... (loadBalanced=true is set automatically by Atlas)

Testing against a local mongod or mongos?
  → mongodb://localhost:27017/db
  → directConnection=true avoids discovery delay with single-node test instances
```

### 8.3 directConnection Notes

- With `directConnection=true`, the driver does NOT check if the host is actually the primary
- Writes to a secondary with `directConnection=true` will fail with `NotWritablePrimary`
- Useful for reading from a specific secondary for debugging or analytics
- Incompatible with multiple hosts in the URI (only one host is allowed)
- Can be combined with `tls=true`

### 8.4 loadBalanced Notes

- Setting `loadBalanced=true` disables topology monitoring (`hello` commands)
- Exactly one host in the URI; `replicaSet` and `directConnection` must NOT be set
- Required for Atlas Serverless instances (MongoDB sets this automatically in the Atlas-provided string)
- Cursors and transactions must stay on the same connection — the driver handles this

---

## 9. Timeout and Retry Options

### 9.1 Retry Options

| Option | Default | Type | Description |
|--------|---------|------|-------------|
| `retryWrites` | `true` | boolean | Retry single write operations (insert, update, delete, findAndModify) on transient network errors. Enabled by default in driver v4+ |
| `retryReads` | `true` | boolean | Retry read operations on transient errors. Enabled by default in driver v4+ |

**What retryWrites covers:**
- Single insert, update, delete, `findAndModify`
- **Not covered:** multi-statement transactions, `mapReduce`, bulk writes (use `ordered:false` + application retry for bulk)

**What retryReads covers:**
- `find`, `aggregate`, `distinct`, `count`, and read commands
- Not cursor `getMore` operations

```text
# Explicitly disable (useful for debugging or testing failure paths)
mongodb://host/db?retryWrites=false&retryReads=false

# Atlas default — both enabled
mongodb+srv://user:pass@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
```

### 9.2 CSOT — Client-Side Operations Timeout (`timeoutMS`)

`timeoutMS` is the **single deadline** for an entire operation including all retry attempts, server selection, connection checkout, and server-side execution.

**Status (as of 2026):** Experimental in most drivers — may change in future releases. Stable in Java driver v5+.

| Option | Default | Type | Description |
|--------|---------|------|-------------|
| `timeoutMS` | unset | integer | Overall operation timeout (ms). `0` = infinite (but `serverSelectionTimeoutMS` still applies) |

**What `timeoutMS` supersedes when set:**

| Legacy Option | Superseded By |
|---------------|--------------|
| `socketTimeoutMS` | `timeoutMS` |
| `waitQueueTimeoutMS` | `timeoutMS` |
| `wTimeoutMS` | `timeoutMS` |
| `maxTimeMS` (per-operation) | `timeoutMS` |
| `maxCommitTimeMS` | `timeoutMS` |

**Priority hierarchy (highest wins):**
1. Operation-level `timeoutMS`
2. Transaction `defaultTimeoutMS`
3. Session `defaultTimeoutMS`
4. Collection → Database → Client-level `timeoutMS`

```text
# Set client-wide 30s deadline
mongodb://host/db?timeoutMS=30000
```

```js
// Cursor with iteration-mode CSOT (each getMore gets its own slice)
const cursor = coll.find({}, { timeoutMS: 5000, timeoutMode: 'iteration' });
```

### 9.3 Other Timeout and Monitoring Options

| Option | Default | Description |
|--------|---------|-------------|
| `connectTimeoutMS` | `30000` | TCP connection establishment timeout |
| `serverSelectionTimeoutMS` | `30000` | How long to search for a suitable server before failing |
| `heartbeatFrequencyMS` | `10000` (multi-thread), `60000` (single-thread) | How often the driver checks server health via `hello`. Minimum: `500` ms |
| `serverMonitoringMode` | `auto` | How the driver monitors servers: `stream` (push-based, default for multi-threaded), `poll` (request-based, default for single-threaded), `auto` (driver chooses) |
| `socketTimeoutMS` | no timeout | **Deprecated.** Use `timeoutMS` instead |
| `wTimeoutMS` | no timeout | **Deprecated.** Use `timeoutMS` instead |

---

## 10. Driver-Specific Considerations

### 10.1 Node.js / Mongoose

**Removed deprecated options (driver v4+):**
- `useNewUrlParser` — always `true`; remove from your code
- `useUnifiedTopology` — always `true`; remove from your code

**Current minimal connection:**
```js
import { MongoClient } from 'mongodb';
const client = new MongoClient(
  'mongodb+srv://user:pass@cluster0.abcde.mongodb.net/mydb?retryWrites=true&w=majority'
);
await client.connect();
```

**Serverless / Lambda pattern (reuse across invocations):**
```js
let _client;
async function getClient() {
  if (!_client) {
    _client = new MongoClient(process.env.MONGODB_URI, {
      maxPoolSize: 10,
      serverSelectionTimeoutMS: 5000,
    });
    await _client.connect();
  }
  return _client;
}
```

### 10.2 Python (PyMongo)

**`connect=False` for lazy connection:**
```python
from pymongo import MongoClient

# connect=False defers actual socket connection until first operation
# Useful in apps where the event loop or fork() happens after import
client = MongoClient(
    "mongodb+srv://user:pass@cluster0.abcde.mongodb.net/",
    connect=False,
    serverSelectionTimeoutMS=5000,
)
```

**Compressors in Python:**
```python
client = MongoClient(uri, compressors=["snappy", "zlib"])
```

**Note:** `snappy` requires the `python-snappy` package; `zstd` requires `zstandard`. Neither is bundled with pymongo — install separately.

### 10.3 Java (Sync/Reactive)

Two ways to configure — URI or `MongoClientSettings`:

**Via URI:**
```java
MongoClient client = MongoClients.create(
    "mongodb+srv://user:pass@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority"
);
```

**Via MongoClientSettings (preferred for complex config):**
```java
MongoClientSettings settings = MongoClientSettings.builder()
    .applyConnectionString(new ConnectionString(uri))
    .applyToConnectionPoolSettings(builder ->
        builder.maxSize(100).minSize(5))
    .applyToSocketSettings(builder ->
        builder.connectTimeout(10, TimeUnit.SECONDS))
    .build();
MongoClient client = MongoClients.create(settings);
```

**Compression in Java:**
- Zlib: built-in (JDK)
- Snappy/Zstd: add `org.xerial.snappy:snappy-java` or `com.github.luben:zstd-jni`

### 10.4 .NET (C# Driver)

**Via URI:**
```csharp
var client = new MongoClient("mongodb+srv://user:pass@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority");
```

**Via MongoClientSettings:**
```csharp
var settings = MongoClientSettings.FromConnectionString(uri);
settings.MaxConnectionPoolSize = 100;
settings.ConnectTimeout = TimeSpan.FromSeconds(10);
var client = new MongoClient(settings);
```

### 10.5 Go Driver

**Via URI:**
```go
client, err := mongo.Connect(
    context.TODO(),
    options.Client().ApplyURI("mongodb+srv://user:pass@cluster0.abcde.mongodb.net/"),
)
```

**Via options (combined):**
```go
opts := options.Client().
    ApplyURI(uri).
    SetMaxPoolSize(100).
    SetServerSelectionTimeout(5 * time.Second)
client, err := mongo.Connect(context.TODO(), opts)
```

**Compression in Go:**
- Snappy/Zstd require explicit import: `_ "go.mongodb.org/mongo-driver/x/mongo/driver/compressors/snappy"`

### 10.6 UUID Representation

Different drivers historically used different BSON UUID subtypes. If you store UUIDs from mixed drivers, set `uuidRepresentation` to avoid cross-driver corruption:

| Value | Driver Default |
|-------|---------------|
| `standard` | Go, Python 3.x, Ruby |
| `csharpLegacy` | .NET (legacy) |
| `javaLegacy` | Java (legacy) |
| `pythonLegacy` | PyMongo (legacy, <3.x) |

```text
mongodb://host/db?uuidRepresentation=standard
```

---

## Quick Reference: Full Options Table

| Option | Default | Group | Notes |
|--------|---------|-------|-------|
| `authSource` | `admin` | Auth | Override for LDAP/GSSAPI/AWS: `$external` |
| `authMechanism` | auto | Auth | SCRAM-SHA-256, SCRAM-SHA-1, MONGODB-X509, MONGODB-AWS, GSSAPI, PLAIN, MONGODB-OIDC |
| `authMechanismProperties` | — | Auth | `KEY:VALUE` pairs, comma-separated |
| `tls` / `ssl` | false (std), true (SRV) | TLS | `ssl` is deprecated synonym |
| `tlsCAFile` | system store | TLS | Path to CA PEM |
| `tlsCertificateKeyFile` | — | TLS | Client cert + key PEM (mTLS) |
| `tlsCertificateKeyFilePassword` | — | TLS | Key file password |
| `tlsInsecure` | `false` | TLS | Disables ALL validation — never use in prod |
| `tlsAllowInvalidCertificates` | `false` | TLS | Skips server cert check |
| `tlsAllowInvalidHostnames` | `false` | TLS | Skips hostname check |
| `tlsDisableCertificateRevocationCheck` | `false` | TLS | Skip OCSP/CRL revocation check |
| `tlsDisableOCSPEndpointCheck` | `false` | TLS | Skip only OCSP endpoint check |
| `maxPoolSize` | `100` | Pool | Max connections per server |
| `minPoolSize` | `0` | Pool | Pool pre-warms to this count |
| `maxConnecting` | `2` | Pool | Concurrent connection establishment limit |
| `maxIdleTimeMS` | no limit | Pool | Remove idle connections after this |
| `waitQueueTimeoutMS` | driver-dep | Pool | Max wait for a pool slot |
| `connectTimeoutMS` | `30000` | Timeout | TCP handshake timeout |
| `serverSelectionTimeoutMS` | `30000` | Timeout | Topology discovery timeout |
| `heartbeatFrequencyMS` | `10000` | Timeout | Server health check interval |
| `serverMonitoringMode` | `auto` | Timeout | `stream` (push-based), `poll` (request-based), `auto` (driver chooses) |
| `socketTimeoutMS` | none | Timeout | **Deprecated** — use `timeoutMS` |
| `timeoutMS` | unset | CSOT | Single operation deadline (experimental) |
| `readPreference` | `primary` | ReadPref | primary, primaryPreferred, secondary, secondaryPreferred, nearest (Analytics Nodes via `readPreferenceTags`, not a mode) |
| `readPreferenceTags` | — | ReadPref | `key:value` tag filter (multiple allowed) |
| `maxStalenessSeconds` | no limit | ReadPref | Min: 90s; secondary only |
| `hedgedReads` | `false` | ReadPref | Atlas only |
| `w` | server default | WriteConcern | 0, 1, N, majority, tagName |
| `wTimeoutMS` | no limit | WriteConcern | **Deprecated** — use `timeoutMS` |
| `journal` | `false` | WriteConcern | Require journal acknowledgment (`j=true`) |
| `readConcernLevel` | `local` | ReadConcern | local, available, majority, linearizable, snapshot |
| `compressors` | none | Compression | zstd, snappy, zlib (order = preference) |
| `zlibCompressionLevel` | `-1` | Compression | -1 to 9; higher = smaller, slower |
| `replicaSet` | — | Topology | Replica set name (required for std format RS) |
| `directConnection` | `false` | Topology | Skip discovery, connect to single host |
| `loadBalanced` | `false` | Topology | Atlas Serverless/Flex; no topology monitoring |
| `srvMaxHosts` | `0` | Topology | Cap hosts from DNS SRV (0 = unlimited) |
| `srvServiceName` | `mongodb` | Topology | Override SRV DNS service name |
| `localThresholdMS` | `15` | Topology | Server selection latency window |
| `retryWrites` | `true` | Retry | Retry single writes on network error |
| `retryReads` | `true` | Retry | Retry reads on transient error |
| `appName` | — | Misc | Tag in `currentOp`, logs, profiler |
| `uuidRepresentation` | driver-dep | Misc | standard, csharpLegacy, javaLegacy, pythonLegacy |

---

## References and See Also

### Official MongoDB Docs
- [Connection String Formats](https://www.mongodb.com/docs/manual/reference/connection-string-formats/)
- [Connection String Options](https://www.mongodb.com/docs/manual/reference/connection-string-options/)
- [TLS/SSL Configuration for Clients](https://www.mongodb.com/docs/manual/tutorial/configure-ssl-clients/)
- [Connection Pool Overview](https://www.mongodb.com/docs/manual/administration/connection-pool-overview/)
- [Read Preference](https://www.mongodb.com/docs/manual/core/read-preference/)
- [Write Concern](https://www.mongodb.com/docs/manual/reference/write-concern/)
- [Read Concern](https://www.mongodb.com/docs/manual/reference/read-concern/)
- [CSOT — Node.js Driver](https://www.mongodb.com/docs/drivers/node/current/connect/connection-options/csot/)
- [Network Compression — Node.js Driver](https://www.mongodb.com/docs/drivers/node/v6.x/connect/connection-options/network-compression/)
- [Authentication Mechanisms — Go Driver](https://www.mongodb.com/docs/drivers/go/v1.x/fundamentals/auth/)

### Related Skills
- [[mongodb-developer]] — General MongoDB development patterns
- [[mongodb-driver-internals]] — Deep driver behavior: SDAM, CMAP, retryable operations
- [[mongodb-security-architecture]] — TLS, X.509, LDAP, encryption at rest
- [[mongodb-atlas-expert]] — Atlas-specific connection and configuration patterns
- [[mongodb-performance-troubleshooting]] — Diagnosing pool exhaustion, slow queries, timeout errors
- [[mongodb-atlas-iam-rbac]] — AWS IAM / MONGODB-AWS auth patterns
- [[mongodb-replication]] — Replica set topology, elections, read preferences
- [[mongodb-transactions]] — Write concern and read concern in transaction context
