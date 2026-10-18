The file being fixed isn't on disk in this session — it's passed in as text in the prompt. I'll apply the three targeted fixes and output the corrected file. The fixes are surgical:

1. Section 4: prepend `For application-level custom metrics, poll \`$currentOp\` on a schedule.` before "Run from admin-context..."
2. Section 7 Prometheus federation: append `Metrics include everything from \`serverStatus\`, \`replSetGetStatus\`, and \`dbStats\`.` 
3. Section 13 customer template: add intro sentence with `[bracketed]` before the code block

<!-- hub-reference-banner -->
> **Reference file — part of the `atlas-diagnostics-expert` hub.** Formerly standalone `mongodb-monitoring-observability` skill.
> Sibling MongoDB sub-topics now reference files under four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore "use the X skill" / `related_skills` / SKIP pointers naming bare `mongodb-*`/`atlas-*` skills; load that topic's `references/<name>.md` from owning hub.

---

---
name: mongodb-monitoring-observability
title: MongoDB Monitoring and Observability
version: "1.3.0"
last-updated: "2026-05-29"
category: mongodb
description: >
  Comprehensive reference for monitoring MongoDB Atlas and self-managed deployments — Atlas
  built-in dashboards, Ops Manager/Cloud Manager monitoring agents, alert configuration and
  tuning, Datadog/New Relic/Prometheus integrations, FTDC (Full-Time Diagnostic Data Capture)
  analysis, slow query monitoring, replication lag diagnosis, connection metrics, and Atlas
  maintenance windows.
  TRIGGER: questions about Atlas metrics or dashboards, configuring alerts (CPU, replication lag,
  oplog window, connections), setting up Datadog or Prometheus integration for MongoDB,
  analyzing FTDC diagnostic data, slow query profiling (system.profile, Atlas Performance Advisor),
  replication lag root causes, connection pool exhaustion signals, Atlas maintenance windows
  (configuring, deferring, understanding rolling restart behavior), planned maintenance
  communication templates, or mongostat/mongotop/db.currentOp usage.
  SKIP: Atlas Search index tuning (use mongodb-atlas-search), Atlas cost optimization
  (use mongodb-cost-optimization), backup and restore planning (use mongodb-backup-restore),
  WiredTiger cache internals (use mongodb-wiredtiger), full query optimization beyond
  profiler analysis (use mongodb-query-performance).
tags:
  - mongodb
  - atlas
  - monitoring
  - observability
  - datadog
  - prometheus
  - new-relic
  - alerts
  - ftdc
  - slow-queries
  - replication
  - maintenance
  - maintenance-window
  - planned-operations
keywords:
  - Atlas monitoring
  - Atlas alerts
  - Datadog MongoDB integration
  - Prometheus MongoDB
  - New Relic MongoDB
  - FTDC diagnostics
  - slow query analysis
  - replication lag monitoring
  - connection pool monitoring
  - Atlas maintenance window
  - maintenance deferral
  - mongostat
  - mongotop
  - db.currentOp
  - Atlas Performance Advisor
  - system.profile
  - oplog window
  - WiredTiger metrics
  - Atlas Real-Time Performance Panel
  - Ops Manager monitoring
  - Cloud Manager monitoring
whenToUse:
  - Answering questions about Atlas metrics, dashboards, or alert configuration
  - Configuring third-party monitoring integrations (Datadog, Prometheus, New Relic)
  - Analyzing FTDC diagnostic files to diagnose historical performance issues
  - Slow query analysis via Atlas Profiler, system.profile, or mtools
  - Diagnosing replication lag root causes and flow control
  - Investigating connection pool exhaustion or connection limit issues
  - Configuring or deferring Atlas maintenance windows
  - Communicating planned Atlas maintenance to customers or stakeholders
  - Choosing the right monitoring tool for a given diagnostic question
  - Setting up Ops Manager or Cloud Manager for self-managed deployments
whenNotToUse:
  - Atlas Search index performance tuning — use mongodb-atlas-search
  - Atlas cost optimization or billing — use mongodb-cost-optimization
  - Backup and restore planning — use mongodb-backup-restore
  - WiredTiger cache internals and eviction tuning — use mongodb-wiredtiger
  - Deep query optimization beyond profiler output — use mongodb-query-performance
  - Ops Manager deployment, backup daemon, and automation (monitoring only covered here) — use mongodb-ops-manager
related_skills:
  - mongodb-wiredtiger
  - mongodb-performance-troubleshooting
  - mongodb-query-performance
  - mongodb-replication
  - mongodb-atlas-expert
  - mongodb-ops-manager
  - mongodb-backup-restore
  - mongodb-cost-optimization
audience: MongoDB TAMs, DBAs, and developers responsible for operating or advising on MongoDB Atlas and self-managed deployments
---

# MongoDB Monitoring and Observability

Reference for monitoring MongoDB — Atlas built-in dashboards through third-party integrations, CLI tools, FTDC diagnostics.

**When to use:** Atlas metrics, alert config, third-party integrations (Datadog, New Relic, Prometheus), FTDC diagnostics, slow query analysis, replication lag, connection pool behavior, maintenance windows.

**When not to use:** Atlas Search index tuning (use `mongodb-search-ai`), cost optimization (use `mongodb-cost-optimization`), backup/restore (use `mongodb-backup-restore`).

**Required roles:** `clusterMonitor` on `admin` db (self-managed), or Atlas `Project Read Only` / `Project Data Access Read Only` (Atlas UI). Third-party integrations require Atlas `Project Owner` or `Organization Owner`.

**Jump to:** [Quick Reference Tool Matrix](#quick-reference-tool-selection-matrix)

---

## 1. Atlas Cloud Monitoring — Built-in Metrics and Dashboard Customization

Atlas provides real-time and historical metrics for M10+. Free/shared-tier clusters have reduced granularity (5-min vs. 1-min for dedicated).

### Key metric categories available in Atlas UI

- **Opcounters** — insert, query, update, delete, getmore, command rates (ops/sec)
- **CPU / System** — process CPU, system CPU, I/O wait broken by read/write
- **Memory** — resident, virtual, mapped, cache (WiredTiger block cache, dirty bytes)
- **Disk I/O** — IOPS read/write, I/O utilization, disk queue depth
- **Network** — bytes in/out, number of requests
- **Connections** — current, available, total created
- **Replication** — oplog window hours, replication headroom, replication lag per secondary
- **Query targeting** — scanned/returned ratio (key indicator of missing indexes)
- **Tickets** — WiredTiger concurrent read/write tickets in use vs. available

### Dashboard customization

Atlas dashboards are pre-built per cluster but allow:
- Pin charts to custom "Metrics" view for side-by-side node comparison
- Toggle individual node vs. cluster aggregate view
- Adjust time range (1h, 8h, 24h, 48h, 1w, custom)
- Use **Real-Time Performance Panel** (RTPP) for 1-second granularity on live traffic — M10+ via **Real Time** tab

RTPP shows: opcounters, read/write tickets, connections, network, logical size, interactive `currentOp` view with slowest in-flight ops per namespace.

---

## 2. Ops Manager and Cloud Manager — Self-Managed Deployments

> **Deep reference:** see `mongodb-ops-manager` for App DB sizing/HA, Backup Daemon placement, automation goal-state, air-gap/Local Mode, Kubernetes Operator, federation, Live Migration to Atlas. This section covers monitoring agent only.

**MongoDB Ops Manager** — on-premises management platform for self-hosted MongoDB. **MongoDB Cloud Manager** — hosted SaaS version with identical monitoring, automation, backup, no self-hosting required. Same agent architecture.

### Core agents

| Agent | Role |
|---|---|
| **Automation Agent** | Deploys, configures, upgrades, scales MongoDB processes via Ops Manager directives |
| **Monitoring Agent** | Collects real-time metrics from every managed `mongod`/`mongos`, ships to Ops Manager every 10 seconds |
| **Backup Agent** | Coordinates snapshot-based and oplog-based continuous backup |

### Monitoring agent behavior

- Runs as daemon alongside MongoDB processes
- Polls `serverStatus`, `replSetGetStatus`, `dbStats`, `collStats`, `currentOp` (filtered) at configurable intervals
- Stores time-series data in Ops Manager's own MongoDB backing store (separate from application data)
- Sends alerts through Ops Manager's alert system — same types as Atlas

### Ops Manager / Cloud Manager dashboards

Both replicate Atlas-style metric dashboards. Topology view shows replica set health, node states (PRIMARY/SECONDARY/ARBITER), replication lag per member. **Hardware** tab surfaces CPU, disk IOPS, memory at host level.

---

## 3. Atlas Alerts — Types, Channels, and Tuning

### Alert scope levels

- **Project-level alerts** — all clusters in project (e.g., CPU > 80% on any node)
- **Cluster-level alerts** — scoped to specific cluster
- **Billing alerts** — monthly spend thresholds, data transfer thresholds

### Alert condition categories

| Category | Examples |
|---|---|
| Host / Node | CPU %, memory %, disk utilization %, disk IOPS |
| Replication | Replication lag > N seconds, oplog window < N hours |
| Connections | Connections > N (absolute or % of max) |
| Query performance | Slow queries, query targeting ratio |
| Indexes | Index build failures |
| Backup | Last successful snapshot age, restore failures |
| Atlas Search | Search index build failures |
| Billing | Monthly spend threshold, data transfer threshold exceeded |

### Notification channels

| Channel | Configuration |
|---|---|
| **Email** | One or more addresses; configurable delay |
| **Slack** | OAuth or webhook URL; route to specific channels |
| **PagerDuty** | Integration key; supports routing rules/escalation policies |
| **Webhook** | HTTP POST to any endpoint; JSON payload |
| **Datadog** | Forwards Atlas alert events as Datadog events alongside metrics |
| **OpsGenie** | API key |
| **VictorOps (Splunk On-Call)** | Routing key |
| **SMS / Phone** (Twilio-backed) | Limited to some plan tiers |

### Alert tuning best practices

- **Set delay intervals** (e.g., "notify if persists 5 minutes") to suppress transient spikes
- **CPU alert baseline**: M10–M30 alert at 75%; M50+ with sustained IOPS-heavy workloads 85% with short delay
- **Replication lag**: alert at 10–15s for most OLTP; 60s for batch-heavy pipelines
- **Oplog window**: never below 4 hours; alert at 48 hours to investigate before backup windows at risk
- **Connection count**: alert at 80% of `maxIncomingConnections`; calculate from `db.adminCommand({getCmdLineOpts:1})` or Atlas connection string params

---

## 4. Custom Metrics

### Atlas Custom Metrics

Atlas supports custom metric alerts via **Atlas Administration API** (`/api/atlas/v2/groups/{groupId}/alertConfigs`). `metricName` accepts any metric Atlas exposes — including metrics not in UI by default. Full catalog: `https://www.mongodb.com/docs/atlas/reference/alert-conditions/`

### $currentOp polling for application-level insight

For application-level custom metrics, poll `$currentOp` on a schedule. Run from admin-context connection — `$all` deprecated in 4.0, removed in favor of admin-context `currentOp` directly:

```javascript
// Poll every 30 seconds via a dedicated monitoring connection (admin auth required)
// MongoDB 4.0+: run currentOp from admin context without $all
const ops = await db.admin().command({ currentOp: 1 });

// Extract slow ops (> 1 second), skip replication and internal namespaces
const slowOps = ops.inprog.filter(op =>
  op.secs_running > 1 &&
  op.ns &&
  !op.ns.startsWith('local.') &&
  !op.ns.startsWith('admin.')
);

// Emit to your metrics pipeline (Prometheus pushgateway, Datadog StatsD, etc.)
slowOps.forEach(op => {
  metrics.gauge('mongodb.slow_op.seconds', op.secs_running, {
    ns: op.ns,
    op: op.op,
    plan: op.planSummary
  });
});
```

Key fields in `$currentOp`:
- `secs_running` — wall time since op start
- `op` — command type (query, update, insert, command, getmore)
- `ns` — namespace (db.collection)
- `planSummary` — index used or COLLSCAN
- `waitingForLock` — boolean; stuck ops block others
- `msg` — progress message for long-running ops (index builds, aggregations)
- `locks` — lock modes held per resource type

### Application-level metrics to track

Beyond MongoDB server metrics, instrument application code:
- Query latency percentiles (p50, p95, p99) per collection
- Error rates by MongoDB error code
- Connection pool `waitQueueSize` — rising queue = pool exhaustion signal
- Retry attempt counts — spike indicates transient replica set elections or network partitions

---

## 5. Datadog Integration

### Setup

Requires M10+ and Datadog API key. Configure via:
- Atlas UI: **Project → Integrations → Datadog**
- Atlas API: `POST /api/atlas/v2/groups/{groupId}/integrations` with `type: "DATADOG"`
- Select region (`US1`, `US3`, `US5`, `EU1`, `AP1`, `US1_FED`) matching your Datadog account

### Metrics shipped to Datadog

Atlas ships 100+ metrics prefixed `mongodb.atlas.*`. Key ones:

| Metric | Description |
|---|---|
| `mongodb.atlas.connections.current` | Active connections |
| `mongodb.atlas.opcounters.cmd` | Command rate |
| `mongodb.atlas.system.cpu.norm.guest` | Normalized CPU |
| `mongodb.atlas.mem.resident` | Resident memory bytes |
| `mongodb.atlas.cache.usage.dirty` | WiredTiger dirty cache bytes |
| `mongodb.atlas.repl.headroom` | Replication headroom (oplog - lag) |
| `mongodb.atlas.disk.partition.iops.total` | Total disk IOPS |
| `mongodb.atlas.query.targeting.scannedObjectsPerReturned` | Scan ratio |

### Datadog Database Monitoring for Atlas

Separate from metrics integration — requires Datadog Agent with MongoDB integration. Provides:
- Query-level explain plan capture
- Wait event analysis
- Query normalization and fingerprinting
- Query sample storage for historical analysis

Configure via `conf.d/mongo.d/conf.yaml` in Datadog Agent. Use Atlas connection string with monitoring user having `clusterMonitor` role.

### Datadog dashboards

Pre-built **MongoDB Atlas Overview** dashboard in integrations library. Clone to customize. Add:
- Query targeting ratio over time (composite: scanned / returned)
- WiredTiger cache fill % (dirty bytes / total cache)
- Election events as event overlay

---

## 6. New Relic Integration

### Atlas New Relic integration

Configure via Atlas UI: **Project → Integrations → New Relic**. Requires New Relic license key and account ID. Metrics ship as custom events/metrics under `MongoDBAtlas.*` namespace.

### APM correlation

New Relic's primary value: **APM-to-database correlation** — links slow transaction traces in application code to slow MongoDB operations. Shows:
- Which application endpoint triggered slow query
- Time breakdown: application processing vs. MongoDB query time
- Database query fingerprints alongside application traces

### New Relic on-host integration (self-managed)

Use New Relic Infrastructure agent with MongoDB on-host integration (`nri-mongodb`):

```yaml
# /etc/newrelic-infra/integrations.d/mongodb-config.yml
integrations:
  - name: nri-mongodb
    env:
      USERNAME: newrelic_monitor
      PASSWORD: ${MONGODB_PASSWORD}
      HOST: localhost
      PORT: 27017
      AUTH_SOURCE: admin
      SSL: true
      REPLICA_SET: rs0
      EXTENDED_METRICS: true
      COLLECTION_METRICS: true
```

Metrics: throughput, latency, connections, memory, replication lag, collection-level stats when `COLLECTION_METRICS: true`.

---

## 7. Prometheus Integration

### Atlas managed Prometheus endpoint

Atlas exposes Prometheus-compatible scrape endpoint (M10+ only). Enable via:
- Atlas UI: **Project → Integrations → Prometheus**
- Generates scrape URL: `https://cloud.mongodb.com/prometheus/v1.0/groups/{groupId}/metrics`
- Auth: HTTP Basic with Atlas programmatic API public/private key pair

### Scrape configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'mongodb-atlas'
    scrape_interval: 60s
    scrape_timeout: 55s
    scheme: https
    basic_auth:
      username: '<atlas_public_api_key>'
      password: '<atlas_private_api_key>'
    static_configs:
      - targets:
          - 'cloud.mongodb.com'
    metrics_path: '/prometheus/v1.0/groups/<groupId>/metrics'
    # Optional: filter to specific cluster
    params:
      cluster: ['<clusterName>']
```

### Key Prometheus metrics from Atlas

| Metric name | Type | Description |
|---|---|---|
| `hardware_system_cpu_norm_guest_percent` | gauge | Normalized CPU % |
| `assert_regular` | counter | Regular assertions |
| `connections_current` | gauge | Open connections |
| `cache_bytes_currently_in_cache` | gauge | WiredTiger cache bytes |
| `cache_dirty_bytes_in_the_cache` | gauge | Dirty cache bytes |
| `mem_resident` | gauge | Resident memory MB |
| `opcounters_cmd_per_second` | gauge | Commands per second |
| `replication_lag` | gauge | Replication lag seconds |
| `query_targeting_scanned_per_returned` | gauge | Scan ratio |

### Federation and self-managed Prometheus

For self-managed MongoDB, use `mongodb_exporter` (Percona open-source) or official MongoDB community exporter. Connect to Prometheus via standard scrape config on port 9216 (default). Metrics include everything from `serverStatus`, `replSetGetStatus`, and `dbStats`.

```yaml
scrape_configs:
  - job_name: 'mongodb-selfmanaged'
    static_configs:
      - targets: ['mongo-host-1:9216', 'mongo-host-2:9216', 'mongo-host-3:9216']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
```

Search "MongoDB Overview Percona" in Grafana dashboard library for production-ready self-managed Prometheus + Grafana starting point.

---

## 8. FTDC (Full Time Diagnostic Capture)

### What is FTDC

FTDC (Full Time Diagnostic Data Capture) — always-on internal diagnostic system, enabled by default in `mongod`/`mongos` since MongoDB 3.2. First artifact MongoDB Support requests for any performance investigation.

### What FTDC captures

Every **second**:
- Full `serverStatus` (opcounters, memory, connections, WiredTiger stats, lock stats, network)
- `replSetGetStatus` (replica set members)
- `local.oplog.rs` metadata (oplog window, latest/oldest oplog timestamps)
- System CPU and memory counters
- Storage engine internal stats (WiredTiger block cache, page eviction, checkpoint timing)

Every **200ms** (high-frequency): lighter subset focused on CPU and I/O counters — allows reconstructing spikes shorter than 1 second.

### Storage and location

FTDC files at `<dbPath>/diagnostic.data/`:
```
diagnostic.data/
  metrics.2024-01-15T00-00-00Z-00000   # compressed binary
  metrics.interim                        # current unsaved buffer (partial — last ~seconds may be missing)
  metrics.2024-01-16T00-00-00Z-00000
```

Files rotate at ~10 MB (configurable via `diagnosticDataCollectionFileSizeMB`). Atlas retains FTDC and surfaces to MongoDB Support automatically — no manual retrieval needed for Atlas clusters.

### Retrieval for self-managed deployments

Copy entire `diagnostic.data/` directory from server. Copying while `mongod` is live is safe. `metrics.interim` is partial buffer — most recent few seconds may be absent.

### Analysis tools

| Tool | Usage |
|---|---|
| **Keyhole** | `keyhole --ftdc diagnostic.data/` — human-readable reports, Grafana-compatible output |
| **mongodb/ftdc Go library** | Low-level BSON parsing of FTDC metrics chunks |
| **mtools `mloginfo`** | Parses mongod logs alongside FTDC for correlation |
| **Atlas Support** | Direct FTDC access for all Atlas clusters |

### FTDC in troubleshooting

Use FTDC to answer:
- Checkpoint stall? (WiredTiger checkpoint duration spike)
- CPU saturated? (system CPU counters at 100%)
- Connection count spike before incident? (`connections.current` time series)
- Replication lag gradual or sudden? (`replSetGetStatus.members[].optimeDate` delta)
- WiredTiger cache fill and aggressive eviction? (cache dirty % over time)

---

## 9. mongotop / mongostat / db.currentOp

### mongostat

Streams running summary of MongoDB server activity, similar to Unix `vmstat`. Updates every second by default.

```bash
mongostat --uri "mongodb+srv://user:pass@cluster.mongodb.net" \
          --discover \
          --rowcount 60
```

Key columns:
| Column | Meaning |
|---|---|
| `insert/query/update/delete` | Operations per second |
| `getmore` | Cursor getmore ops/sec |
| `command` | Command ops/sec (replicated writes counted twice) |
| `dirty` | WiredTiger dirty cache % |
| `used` | WiredTiger cache in-use % |
| `flushes` | WiredTiger checkpoints in interval |
| `vsize/res` | Virtual/resident memory |
| `qrw/arw` | Queue length and active count for reads/writes |
| `conn` | Current connections |
| `repl` | Replication state (PRI/SEC/REC) |

**When to use**: quick snapshot of overall server load; watching for sudden spikes in op rates or queue buildup; checking cache utilization in real time.

### mongotop

Shows per-collection time on reads and writes, updated every second.

```bash
mongotop --uri "mongodb+srv://user:pass@cluster.mongodb.net" 5
```

`5` = polling interval seconds. Output: `ns` (namespace), `total` (ms/interval), `read` (ms), `write` (ms).

**When to use**: identify hottest collection during performance issue; confirm problematic query hits expected namespace; narrow which collection to profile next.

### db.currentOp()

`db.currentOp()` — mongosh helper alias for `db.adminCommand({currentOp: true, ...})`. Returns in-flight operations at invocation. More detailed than `mongostat`/`mongotop`.

```javascript
// All active operations longer than 2 seconds, excluding replication namespaces
db.adminCommand({
  currentOp: true,
  active: true,
  secs_running: { $gt: 2 },
  ns: { $not: /^local\./ }
})

// Kill a specific operation
db.adminCommand({ killOp: 1, op: <opid> })
```

**When to use**: investigate slow operation in real time; find lock waiters (`waitingForLock: true`); identify which session holds lock before `killOp`.

---

## 10. Slow Query Monitoring

### Atlas Profiler

Atlas exposes query profiler via **Cluster → Performance Advisor** and **Cluster → Profiler** tabs. Profiler tab streams slow queries in near-real-time (~2 minute Atlas data pipeline latency).

- Set slow query threshold via Atlas UI (Cluster → **Configuration** → "Slow Query Threshold") or `db.setProfilingLevel()`
- Default Atlas slow threshold: **100ms** (configurable to 0ms for all queries)
- Atlas Performance Advisor surfaces index recommendations from slow query patterns, ranked by avg execution time × frequency

### system.profile collection

Profiling level 1 or 2 writes operation metadata to `db.system.profile` (capped, 1 MB default):

```javascript
// Enable profiling for ops > 100ms
db.setProfilingLevel(1, { slowms: 100 })

// Query the profile
db.system.profile.find({
  millis: { $gt: 500 },
  ns: { $ne: 'admin.system.profile' }
}).sort({ ts: -1 }).limit(20).pretty()
```

Key fields: `millis`, `ns`, `op`, `planSummary` (IXSCAN vs. COLLSCAN), `keysExamined`, `docsExamined`, `nreturned`, `locks`, `queryHash`, `planCacheKey`.

**Important**: profiling level 2 has measurable overhead on busy clusters — use level 1 with tuned `slowms` in production.

### Slow query log parsing with mtools

```bash
pip install mtools
mloginfo mongod.log --queries
# Groups by query shape, shows count / avg ms / max ms / 95th percentile
```

### Atlas slow query threshold tuning guidance

| Workload | Recommended threshold |
|---|---|
| OLTP (< 10ms target) | 20–50ms |
| Mixed OLTP/analytics | 100ms (default) |
| Analytics-heavy | 200–500ms |
| Bulk load / maintenance windows | Raise to 1000ms to avoid noise |

---

## 11. Replication Lag Monitoring

### Measuring replication lag

```javascript
// From mongosh on any replica set member
rs.printSecondaryReplicationInfo()
// Output: source, syncedTo, lag in seconds, heartbeat lag

// Programmatic approach — use optimeDate (a JS Date), not optime.ts (a BSON Timestamp)
const status = db.adminCommand({ replSetGetStatus: 1 })
const primary = status.members.find(m => m.stateStr === 'PRIMARY')
status.members.filter(m => m.stateStr === 'SECONDARY').forEach(sec => {
  const lagMs = primary.optimeDate.getTime() - sec.optimeDate.getTime()
  console.log(`${sec.name}: lag ${lagMs}ms`)
})
```

Note: use `optimeDate` (JS Date) not `optime.ts` (BSON Timestamp with `.t`/`.i` integer fields) — `.getTime()` on BSON Timestamp returns `undefined`.

### Root causes of replication lag

1. **Secondary under-resourced** — secondary CPU/disk can't keep up; fix by upgrading tier or distributing reads
2. **Replication flow control** (MongoDB 4.2+) — primary throttles writes when secondaries fall behind; visible in `replSetGetStatus.flowControl`
3. **Chained replication misconfiguration** — secondary syncing from another secondary; check `rs.status().syncSourceHost`
4. **Long-running transactions on secondary** — secondary blocks replication to apply multi-doc transactions atomically; check `maxTransactionLockRequestTimeoutMillis`
5. **Network partition or bandwidth saturation** — check `replication.network.bytes` in `serverStatus`

### Flow control diagnostics

```javascript
db.adminCommand({ serverStatus: 1 }).flowControl
// Fields: enabled, targetRateLimit, timeAcquiringMicros, isLagged
```

When `isLagged: true`, primary actively throttles writes. Fix root cause on lagging secondary — don't disable flow control (`enableFlowControl: false`), risks oplog overflow.

### Lag alert thresholds

| Deployment type | Warning | Critical |
|---|---|---|
| OLTP, strict secondary reads | 5s | 15s |
| General purpose | 15s | 60s |
| Analytics/reporting secondaries | 60s | 300s |

Atlas alert: **Replica Set Replication Lag** condition in **Project Alerts → Add New Alert → Replication**.

---

## 12. Connection Metrics

### Key connection counters in serverStatus

```javascript
const ss = db.adminCommand({ serverStatus: 1 })

// Current connection state
ss.connections.current       // Active connections right now
ss.connections.available     // Remaining capacity (maxIncomingConnections - current)
ss.connections.totalCreated  // Cumulative connections since server start (monotonic)

// WiredTiger connection/session info
ss.wiredTiger.concurrentTransactions.read.out   // Active read tickets
ss.wiredTiger.concurrentTransactions.read.available
ss.wiredTiger.concurrentTransactions.write.out  // Active write tickets
ss.wiredTiger.concurrentTransactions.write.available
```

### Connection pool exhaustion signals

| Signal | What to look for |
|---|---|
| `connections.available` approaching 0 | Imminent connection refusal |
| `totalCreated` rate high | Connections closing/reopening rapidly (pool churn) |
| Driver-side `waitQueueSize` rising | Application waiting for pool slot |
| `ServerSelectionTimeoutError` in app logs | Pool exhausted before timeout |
| `Too many open files` in mongod log | OS file descriptor limit hit (ulimit -n) |

### Atlas connection limits by cluster tier

| Tier | Max connections |
|---|---|
| M10 | 1,500 |
| M20 | 3,000 |
| M30 | 3,000 |
| M40 | 6,000 |
| M50 | 16,000 |
| M60 | 32,000 |
| M80 | 64,000 |
| M200+ | 128,000 |

Connections are per-node, not per-cluster. 3-node M30 replica set = 3 × 3,000 = 9,000 total across all nodes, but driver connects only to primary (and secondaries for tagged read preference).

### Connection tuning recommendations

- **Driver `maxPoolSize`**: default 100 per MongoClient. For serverless/Lambda, reduce to 5–10 to avoid connection storms during cold-start bursts.
- **Single MongoClient per process** — most common leak: new `MongoClient` per request.
- **Enable `waitQueueTimeoutMS`** (Node.js) or `waitQueueTimeout` (Python) to surface pool exhaustion quickly.
- **`minPoolSize`**: keeps connections warm for predictable traffic; each minimum connection consumes permanent server-side slot.
- **Atlas `maxIdleTimeMS`**: reduce (e.g., 60000ms) for Lambda/serverless to match function lifecycle.

---

## Quick Reference: Tool Selection Matrix

| Question | Tool |
|---|---|
| What is the server doing right now? | `mongostat` + Atlas RTPP |
| Which collection is hottest? | `mongotop` |
| What specific operation is slow right now? | `db.currentOp()` / `db.adminCommand({currentOp:1})` |
| What slow queries ran in the past hour? | Atlas Profiler / `system.profile` |
| Why was the server slow at 2am? | FTDC + Keyhole |
| Is replication healthy? | `rs.printSecondaryReplicationInfo()` |
| Are connections running out? | `serverStatus.connections` + Atlas alerts |
| Correlate MongoDB to app performance? | Datadog DBM or New Relic APM |
| Long-term trending (weeks/months)? | Prometheus + Grafana or Datadog dashboards |
| Billing and cluster-level spend? | Atlas billing alerts |
| Atlas Search index health? | Atlas UI → Search tab → Index Metrics |
| Self-managed cluster automation + monitoring? | Ops Manager or Cloud Manager |
| When is maintenance scheduled / what window is configured? | `atlas maintenanceWindows describe` / Atlas UI Project Settings → [§13](#13-atlas-maintenance-windows-and-planned-operations) |
| How do I defer upcoming maintenance? | Atlas UI Defer button or `atlas maintenanceWindows defer` → [§13](#13-atlas-maintenance-windows-and-planned-operations) |

---

## 13. Atlas Maintenance Windows and Planned Operations

### Free and shared tier clusters (M0, M2, M5)

**M0, M2, M5 clusters do not support configurable maintenance windows.** Atlas manages all maintenance with no operator timing control — may restart at any time. Need maintenance window control → upgrade to M10+.

Common confusion: project-level maintenance window setting applies only to dedicated-tier (M10+) clusters.

### Maintenance window configuration

Atlas maintenance windows configured at **project level**, apply to all dedicated-tier (M10+) clusters in that project.

**Location:** Atlas UI → **Project Settings** → **Maintenance Window**

**Default behavior:** No custom window → Atlas selects (commonly Tuesday 10:00–12:00 UTC for many regions, varies). Don't rely on default for production — configure explicit window aligned with lowest-traffic period.

**Configuring:**
- Choose day of week (Sunday–Saturday; Sunday=1 in API/CLI)
- Choose start hour UTC (0–23); window is exactly 1 hour
- Minimum: 1 hour (no sub-hourly windows)
- Changes take effect immediately

**Important:** Maintenance windows are project-scoped, not per-cluster. No supported mechanism for different window per cluster within same project. Different requirements (dev vs. prod) → separate Atlas projects.

**Atlas CLI commands:**
```bash
# View the current maintenance window for a project
atlas maintenanceWindows describe --projectId <projectId>

# Set maintenance window to Sundays at 02:00 UTC
atlas maintenanceWindows update \
  --dayOfWeek 1 \
  --hourOfDay 2 \
  --projectId <projectId>

# Clear a configured maintenance window (reverts to Atlas-chosen default)
atlas maintenanceWindows clear --projectId <projectId>
```

Day-of-week values: Sunday=1, Monday=2, Tuesday=3, Wednesday=4, Thursday=5, Friday=6, Saturday=7.

### What triggers maintenance

| Trigger | Follows Maintenance Window? |
|---|---|
| MongoDB patch version upgrade (e.g., 7.0.8 → 7.0.9) | Yes |
| Atlas infrastructure / hardware updates | Yes |
| Feature releases requiring restart | Yes |
| Critical security patch (CVE) | No — Atlas may override window |
| Major version upgrade (e.g., 6.0 → 7.0) | No — separately scheduled by operator |
| Cluster tier scaling (scale up/down) | No — operator-initiated, immediate rolling restart |
| Storage scaling | No — operator-initiated |
| Cluster pause / resume | No — operator-initiated |

Emergency security patches bypass maintenance window entirely. Atlas notifies project and org owners via email before emergency maintenance; window config does not constrain it.

### How Atlas performs rolling maintenance

Atlas uses rolling restart to minimize downtime:

1. **Secondaries first** — one secondary at a time; waits for each to rejoin and catch up before proceeding
2. **Primary last** — triggers replica set election after all secondaries restarted
3. **Election window** — elections typically 10–30 seconds; writes temporarily unavailable, reads fall back to secondaries (if read preference allows)
4. **mongos nodes (sharded clusters only)** — restarted last after all shards complete

**Application impact:** Brief connection interruption during primary election. Drivers with retryable writes handle transparently — detects "not primary" error, retries on newly elected primary. Apps without retryable writes may see transient write failures.

**Atlas alert during maintenance:** **"Primary election"** alert fires during this procedure — expected during every scheduled window. Consider lower-urgency notification channel for this alert type during known windows.

**Total duration:**
- Simple 3-node replica set: typically 5–15 minutes
- Sharded cluster: multiply by number of shards; large topologies 30–60 minutes
- Secondaries significantly behind before maintenance = longer duration

### Deferring maintenance

When Atlas schedules upcoming maintenance, **Defer** button appears in Atlas UI.

**Rules:**
- Deferral postpones by exactly **7 days**
- Each scheduled event deferred **once only**
- After one deferral, cannot defer again
- **Critical security patches cannot be deferred** — attempting returns error

**Atlas UI:** Defer button on cluster detail page and **Project Settings → Maintenance Window** when maintenance active.

**Atlas CLI:**
```bash
atlas maintenanceWindows defer --projectId <projectId>
```

**Atlas API:**
```bash
POST /api/atlas/v2/groups/{groupId}/maintenanceWindow/defer
# No request body required; authorization via API key
```

### Querying the maintenance window via API

```bash
# GET current maintenance window — returns dayOfWeek, hourOfDay, startASAP, autoDeferOnceEnabled
curl -u "{publicKey}:{privateKey}" --digest \
  "https://cloud.mongodb.com/api/atlas/v2/groups/{groupId}/maintenanceWindow" \
  -H "Accept: application/vnd.atlas.2023-01-01+json"
```

Response fields:
- `dayOfWeek` — integer 1–7 (Sunday=1 through Saturday=7); absent if no custom window
- `hourOfDay` — integer 0–23 UTC start hour
- `startASAP` — boolean; true if Atlas queued maintenance at next opportunity
- `autoDeferOnceEnabled` — boolean; if true, Atlas auto-defers next maintenance once

### Emergency and critical security patches

When Atlas identifies critical CVE:
- May perform out-of-window maintenance with **same-day or next-day notice** for critical CVEs
- Lower-severity: typically **24–48 hours notice** via email
- Email to **all Project Owners and Organization Owners**
- Emergency patches **cannot be deferred**
- Still uses rolling restart to minimize impact

Monitor Atlas **Activity Feed** (Atlas UI → Project → Activity) for maintenance events with timestamps.

### Minimizing application impact

Most effective: ensure driver and connection config supports retryable operations.

**Recommended connection string options:**

| Option | Recommended value | Reason |
|---|---|---|
| `retryWrites` | `true` (default since driver 4.2) | Retry writes transparently on primary election |
| `retryReads` | `true` | Retry reads on network errors and primary changes |
| `serverSelectionTimeoutMS` | `30000` | Elections take 10–30s; 3000ms causes premature `ServerSelectionTimeoutError` |
| `connectTimeoutMS` | `10000` | Standard connection establishment timeout |
| `socketTimeoutMS` | `0` (disabled) | Short socket timeouts interfere with long-running operations |

**Why `serverSelectionTimeoutMS` matters:** During election, all nodes briefly report non-primary. If `serverSelectionTimeoutMS` is 3000ms and election takes 12 seconds, driver gives up before new primary elected. 30000ms gives headroom to wait out election.

**Connection pool warm-up:** After primary election, first queries may be slower as connections re-establish and WiredTiger cache warms for new primary's working set. Normal; resolves within 30–60 seconds.

**Alert correlation:** Correlate "Primary election" alerts with maintenance window times. Alerts within configured window = expected; alerts outside window warrant investigation.

### Atlas maintenance for sharded clusters

Sharded cluster maintenance sequence:

1. **Config server replica set** — CSRS restarted first (rolling restart of config server members)
2. **Shard replica sets** — each shard restarted in turn (rolling within each shard; shards processed sequentially, not parallel)
3. **mongos routers** — all mongos instances restarted last (can be parallel since mongos is stateless)

**Balancer behavior:** Chunk balancer suspended during maintenance. In-progress migrations allowed to complete; no new migrations until maintenance finishes. Avoids partial migrations across restart boundary.

**Total time estimation:** Multiply per-shard restart time by number of shards, add config server and mongos restart time. 4-shard cluster × 10 min/shard = ~40–50 minutes for shard restarts alone.

### Customer communication template

When advising customers on how to communicate planned Atlas maintenance to their own end-users or stakeholders, use the template below. Replace all `[bracketed]` placeholders before sending.

```
Subject: Planned database maintenance — [Day, Month DD YYYY]

We have scheduled routine database maintenance to apply a MongoDB patch update.

Maintenance window: [Day of week, YYYY-MM-DD] [HH:MM]–[HH:MM] UTC
Expected impact:    Brief connection interruption lasting less than 30 seconds
                    during the database primary election. No data loss will occur.
Action required:    None. Applications using current MongoDB drivers with retryable
                    writes enabled will handle the interruption automatically.
                    Applications with custom retry logic may see a single retried
                    operation.

If you observe issues after [HH:MM] UTC, please contact [support channel / Slack #channel].
```

**Placeholder guide:**
- `[Day, Month DD YYYY]` — e.g., "Tuesday, June 10 2025"
- `[HH:MM]–[HH:MM] UTC` — e.g., "02:00–03:00 UTC" (configured 1-hour window)
- `[support channel / Slack #channel]` — your team's escalation path

Every maintenance communication must include:
- Specific UTC time window — never "tonight" or "overnight"
- Impact scoped to election (< 30 seconds), not full rolling restart
- Explicit "no data loss" statement — customers conflate restarts with data risk
- Retryable writes note — non-retryable ops may see one transient error
- Clear escalation path if issues persist after window closes