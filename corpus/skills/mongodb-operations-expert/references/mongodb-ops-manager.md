<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-ops-manager` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-ops-manager
title: MongoDB Ops Manager and Cloud Manager — Self-Managed and Hosted Control Plane
description: |
  MongoDB Ops Manager (self-hosted) and Cloud Manager (hosted SaaS) control plane reference.
  Covers App DB sizing/HA, MongoDB Agent (automation, monitoring, backup), declarative goal-state
  automation, continuous backup with PITR, blockstore vs filesystem vs S3 snapshot stores,
  Backup Daemon placement, LDAP/Kerberos/SAML/x509/OIDC federation, air-gap and Local Mode with
  version-manifest mirroring, immutable S3 snapshots with Object Lock, Kubernetes Operator
  deployment, Datadog/Splunk/PagerDuty integrations, Live Migration to Atlas via mongosync,
  Cloud Manager vs Ops Manager fit, Enterprise Advanced licensing, Admin API (/api/public/v1.0),
  upgrade procedures, common failure modes, agent connectivity, oplog window issues, multi-org
  scale patterns, AppDB performance tuning, and backup daemon disk pressure resolution.
  USE WHEN designing, deploying, troubleshooting, or sizing a self-managed MongoDB control plane
  or its hosted Cloud Manager equivalent.
  SKIP WHEN the deployment is Atlas-only (use mongodb-atlas-expert) or the question is pure
  backup/restore mechanics shared with Atlas (use mongodb-backup-restore).
category: mongodb
keywords:
  - ops-manager
  - opsmanager
  - cloud-manager
  - cloudmanager
  - mongodb-enterprise
  - enterprise-advanced
  - ea-licensing
  - app-db
  - appdb-replica-set
  - cross-dc-appdb
  - automation-agent
  - monitoring-agent
  - backup-agent
  - backup-daemon
  - backup-daemon-stuck
  - head-db
  - mongodb-agent
  - mongocli-ops-manager
  - automation-config
  - goal-state
  - goal-state-stuck
  - continuous-backup
  - pitr
  - point-in-time-recovery
  - oplog-store
  - oplog-window
  - live-migration-oplog
  - blockstore
  - block-size
  - s3-blockstore
  - snapshot-store
  - object-lock
  - immutable-snapshots
  - worm-backup
  - version-manifest
  - version-manifest-update
  - local-mode
  - air-gap
  - air-gapped
  - offline-installer
  - kubernetes-operator
  - mongodb-controllers-for-kubernetes
  - mongodbopsmanager-cr
  - multi-cluster-kubernetes
  - live-migration
  - migration-host
  - mongosync
  - mongomirror
  - cloud-manager-free-tier
  - cloud-manager-premium
  - datadog-mongodb
  - splunk-mongodb
  - opentelemetry-mongodb-receiver
  - pagerduty
  - opsgenie
  - victorops
  - webhook-templating
  - ldap-deprecation
  - workforce-identity-federation
  - workload-identity-federation
  - oidc-federation
  - kerberos-mongodb
  - x509-auth
  - self-managed
  - on-premise
  - on-prem
  - control-plane
  - ops-manager-api
tags:
  - mongodb
  - mongodb-enterprise
  - control-plane
  - self-managed
  - monitoring
  - backup
  - automation
  - migration
whenToUse:
  - Sizing or installing Ops Manager (App DB, Backup Daemon, blockstore, file system, S3)
  - Designing Ops Manager HA — load balancer + multi-host UI + App DB replica set
  - Choosing between Cloud Manager (hosted) and Ops Manager (self-hosted)
  - Configuring goal-state automation, version upgrades, parameter changes via Automation Config
  - Designing continuous backup + PITR for self-managed clusters
  - Configuring or troubleshooting Backup Daemons, oplog stores, blockstores
  - Setting up Ops Manager for air-gapped or Local Mode deployments
  - Configuring LDAP / Kerberos / SAML / x509 / OIDC federation for Ops Manager users or managed clusters
  - Wiring Ops Manager alerts to PagerDuty, Splunk, Datadog, webhooks
  - Planning Live Migration (push) from Ops Manager or Cloud Manager into Atlas
  - Deploying Ops Manager on Kubernetes (single or multi-cluster mode)
  - Reviewing Enterprise Advanced licensing posture for Ops Manager
  - Troubleshooting MongoDB Agent not reaching goal state, stuck snapshots, manifest staleness
  - Using the Ops Manager Admin API (/api/public/v1.0) for programmatic cluster management
  - Upgrading Ops Manager server versions, AppDB requirements, agent compatibility
  - Diagnosing common failure modes — AppDB outage, backup oplog behind, Daemon disk pressure, TLS SAN errors
  - Scaling multi-org deployments — project isolation, monitoring distribution limits, AppDB connection pool tuning
whenNotToUse:
  - The deployment is 100% Atlas — use mongodb-atlas-expert instead
  - The question is generic backup/restore (snapshot lifecycle, Atlas Cloud Backup) — use mongodb-backup-restore
  - The question is generic monitoring (Atlas dashboards, Prometheus exporters) — use mongodb-monitoring-observability
  - The question is purely about live-migration mechanics between Atlas clusters — use mongodb-migration-patterns
seeAlso:
  - mongodb-backup-restore — Atlas/OM-shared snapshot lifecycle, retention policies, restore workflows
  - mongodb-monitoring-observability — Agent metrics, alert routing, FTDC across Atlas + OM
  - mongodb-migration-patterns — mongosync, mongomirror, mongorestore, cross-platform migration
  - mongodb-atlas-expert — Atlas managed-cluster reference
  - mongodb-disaster-recovery — RPO/RTO planning that uses Ops Manager Backup as a building block
  - mongodb-encryption — KMIP and encryption-at-rest for self-managed clusters
---

# MongoDB Ops Manager and Cloud Manager

This skill is the dedicated reference for **MongoDB's self-managed and hosted control plane**. Atlas operators rarely interact with these systems; they exist for customers who run MongoDB Enterprise on their own infrastructure (Ops Manager) or want the same management surface as a SaaS without standing up the control plane themselves (Cloud Manager).

Atlas-only coverage lives in `mongodb-atlas-expert`. Pure backup mechanics (snapshot lifecycle, restore workflows shared with Atlas) live in `mongodb-backup-restore`. Agent metrics shared with Atlas live in `mongodb-monitoring-observability`. This skill focuses on what's unique to the self-managed and Cloud Manager control plane: App DB, Backup Daemon, blockstore sizing, automation goal-state model, air-gap, multi-host HA, and Live Migration paths out.

---

## 1. What Ops Manager and Cloud Manager Are

**Ops Manager** is the on-premises deployment of MongoDB's management platform, shipped as part of **MongoDB Enterprise Advanced**. You install and operate every component yourself on Linux hosts, Kubernetes, or air-gapped infrastructure.

**Cloud Manager** is the hosted SaaS equivalent — MongoDB runs the control plane in their cloud; you only deploy lightweight MongoDB Agents next to your `mongod`/`mongos` processes. Cloud Manager and Ops Manager share the **same agent architecture and the same web UI concepts**; the difference is who operates the control plane itself.

Both deliver:

- **Monitoring** with real-time dashboards, customizable alerts, and 10-second resolution metrics
- **Automation** for declarative deployment, version upgrades, parameter changes, and re-shaping topology
- **Backup with PITR** — continuous oplog tailing + periodic snapshots + point-in-time restore
- **Performance Advisor** — slow-query analysis and index recommendations

### When to use which

| Decision driver | Choose |
| --- | --- |
| Need control plane in your own data center (regulatory, air-gap, sovereignty) | **Ops Manager** |
| Already on Enterprise Advanced and want the easiest path | **Ops Manager** is included in EA |
| Self-managed clusters but no appetite to host the control plane | **Cloud Manager** (subscription) |
| Want fastest path to features — Cloud Manager updates more frequently than Ops Manager | **Cloud Manager** |
| Want a fully managed *database* (not just control plane) | **Atlas** — different product entirely |
| Free monitoring for community-edition deployments | **Cloud Manager Free Tier** (basic metrics only) |
| Hybrid: some clusters in Atlas, some self-managed | **Atlas for the managed clusters, Cloud Manager (or Ops Manager) for the self-managed ones** — there is no single pane of glass across both today; plan for two control planes |

Cloud Manager updates more frequently than Ops Manager because it's a managed service. New features land in Cloud Manager first, then in Ops Manager point releases. Cloud Manager also has integrations Ops Manager doesn't — notably **AWS / Azure cloud provisioning** for spinning up backing infrastructure as part of automation. If a customer says "we tried it in Cloud Manager but our auditors require on-prem," that maps cleanly to Ops Manager with the same skills carrying over.

### Cloud Manager pricing levels (signal, not contract)

Cloud Manager has historically had three plan tiers, billed per-server per-month (public list pricing has hovered around **$39/server/month for paid tiers**; final pricing is per contract):

- **Free Tier** — basic monitoring, limited metric resolution, 24-hour metric retention, no automation, no backup
- **Standard** — full monitoring + automation, no backup
- **Premium** — adds continuous backup with PITR

Ops Manager is bundled in **Enterprise Advanced**; there's no separate per-server Ops Manager line item. Enterprise Advanced subscription pricing is per-server or per-core, typically ranging from low five figures to mid six figures per year depending on server count, support tier, and contract length. Multi-year commits and volume discounts are routine.

---

## 2. Architecture — Three Roles, One Brain

Both Ops Manager and Cloud Manager (from the customer's side) revolve around three logical components:

```
                                ┌──────────────────────────────┐
                                │  Ops Manager Application     │
                                │  (Java/web UI/REST API)      │
                                │  stateless behind LB         │
                                └──────────────┬───────────────┘
                                               │
                              ┌────────────────┼──────────────────┐
                              ▼                ▼                  ▼
                  ┌───────────────────┐ ┌──────────────┐ ┌──────────────────┐
                  │ Application DB    │ │ Backup DB    │ │ Backup Daemon(s) │
                  │ (replica set)     │ │ (blockstore  │ │ (head DB + sync) │
                  │ stores metadata,  │ │  or S3 +     │ │                  │
                  │ users, monitoring │ │  filesystem) │ │                  │
                  │ data, alerts      │ │              │ │                  │
                  └───────────────────┘ └──────────────┘ └──────────────────┘
                                               ▲
                                               │ TCP 8080 (HTTP) / 8443 (HTTPS)
                                               │
                  ┌────────────────────────────┴──────────────────────────┐
                  │                MongoDB Agents on managed hosts        │
                  │     (Automation + Monitoring + Backup functions)      │
                  └───────────────────────────────────────────────────────┘
```

### Ops Manager Application

A stateless Java application that serves the UI and the REST API. Multiple Application hosts can sit behind a load balancer to deliver UI HA — any host can serve any request, as long as all Application hosts point at the same App DB. This is the canonical multi-host UI pattern:

- Deploy 2+ Application hosts
- Front them with a TCP or HTTP/HTTPS load balancer
- Set `URL to Access Ops Manager` to the load balancer URL
- Set `Load Balancer Remote IP Header` to `X-Forwarded-For` so the app sees the real client IP

If one Application host dies, the load balancer routes around it; sessions are kept alive in the App DB.

### Application Database (App DB)

A **dedicated MongoDB replica set** that hosts only Ops Manager's own data — projects, users, hosts, monitoring time-series, alerts, automation configs, and backup state. This is *not* shared with customer application data; mixing the two is a hard-fail anti-pattern.

Key App DB facts:

- Must be a replica set (not standalone) for any production deployment
- App DB version follows Ops Manager's required matrix — Ops Manager ships with a bundled MongoDB binary it expects to run
- Backup data goes elsewhere (blockstore / S3 / filesystem). App DB stores *metadata* and monitoring metrics, not snapshots
- Many internal writes use `w:2` write concern — secondary co-location with the primary in the same region matters for latency
- If you replicate the App DB across regions, expect the secondary in the primary's region to handle the bulk of w:2 acks for performance
- **Cross-DC App DB anti-pattern**: if the primary is in DC1 and both secondaries are in DC2, every w:2 write requires a cross-DC ack. Latency-sensitive ops (UI page loads, monitoring ingest, alert evaluation) all degrade. Always co-locate at least one secondary with the primary, even if you stretch a third member across DCs for DR
- App DB stores **monitoring time-series at 10-second resolution for the most recent ~24 hours**, then progressively rolls up (1-minute for the last week, coarser thereafter). Size disk for that retention horizon, not raw 10-second-forever (see §3 sizing and §7 monitoring retention)

### Backup Daemon

The component that actually performs backups. In Ops Manager versions prior to 8.0, each Daemon ran a **head database** — a private mongod that maintained a synchronized copy of the data from each replica set being backed up, used to take snapshots without impacting production. **Ops Manager 8.0+ no longer requires head databases**; the Backup Daemon Service handles this directly.

- You can run multiple Daemons in parallel for capacity and locality
- Daemons can be assigned to specific data centers so a DC1 Daemon backs up DC1 clusters (latency / sovereignty)
- When a deployment enables backup, Ops Manager picks which Daemon to use and the head database resides on that daemon's host
- Daemon hosts need at least 100 GB free disk per active head; total capacity depends on how many backed-up clusters live there

### MongoDB Agent

A single binary on each managed `mongod`/`mongos` host. It performs three functions configured per-process:

| Function | What it does |
| --- | --- |
| **Automation** | Deploys, configures, upgrades, and scales MongoDB processes via Ops Manager directives. Reaches "goal state" |
| **Monitoring** | Collects metrics from every managed process and ships to Ops Manager every 10 seconds |
| **Backup** | Sends oplog and data files to the Backup Daemon's head DB |

The Agent polls Ops Manager regularly to fetch the current goal config, applies any changes, and reports current status back. **Hardware metrics are only collected when the Agent is also performing automation for the process** — bare monitoring agents report DB metrics only, not host CPU/disk.

Minimum Agent host: 2 CPU cores, 2 GB RAM. Lighter than people assume.

### Snapshot stores

Three types, **not interchangeable**:

| Store | Where snapshots live | When to use |
| --- | --- | --- |
| **Blockstore** | A separate dedicated MongoDB replica set | Default for on-prem; deduplicates identical blocks across snapshots to reduce storage |
| **Filesystem** | Mounted volume on the Daemon host | Simpler, no extra MongoDB to operate, but no dedup |
| **S3-compatible blockstore** | S3 / MinIO / Ceph / etc. | Scale-out object storage; supports Object Lock for immutable snapshots |

Each snapshot store **streams blocks** through Ops Manager during restore. The Backup Restore Utility on the target then applies oplog entries to roll forward to the requested PIT.

**Immutable S3 snapshots with Object Lock**: only the S3-compatible store supports immutable snapshots. Blockstore and filesystem stores do not.

---

## 3. Sizing Cheat Sheet

Numbers from MongoDB documentation sizing guidelines. Always confirm with MongoDB for production sizing — these are starting points.

### Ops Manager Application host

- Minimum: 8 GiB RAM, 4 vCPU (small dev)
- Production: 16-32 GiB RAM, 8+ vCPU
- `/tmp` must have **≥ 20 GiB free** — Ops Manager unpacks installers and version manifests there
- CPU/RAM listed in docs assume **backup is not enabled** on the same host. With backup, plan separately for the Daemon

### App DB replica set

- 3 voting members in production
- Working set sizing: 1-2 GB RAM per 100 managed processes is a rough lower bound
- SSD storage; size for monitoring retention horizon (10-second metrics for short window, rolled up over time)
- Run it as a dedicated cluster — never co-tenant with application data

### Backup Daemon host

- ≥ 100 GB free disk for head DB workspace
- Head DB on the Daemon mirrors **the full data size of each backed-up replica set on that Daemon** — plan disk capacity accordingly
- Throughput: high disk IO bandwidth; the Daemon both tails oplogs and writes snapshot blocks

### Backup Database (blockstore)

- If you use the dedicated blockstore (MongoDB) snapshot store: provision **2-3× the total backed-up production data size** for the blockstore disks. Block deduplication helps, but plan for the worst case
- Block size default: **1 MB**; if your backups include files > 100 GB, bump block size to 2 MB+ to keep block index tractable

### Replica set size advisory

When sizing backups, **keep each backed-up replica set's uncompressed data ≤ 2 TB**. This isn't a hard limit on MongoDB itself; it's MongoDB's documented guidance for keeping Ops Manager Backup performant — restore times grow linearly with snapshot size.

---

## 4. Goal-State Automation

The Automation system uses an **Automation Configuration document** (a JSON blob stored in the App DB) to declare the desired state of every managed process. The MongoDB Agent then makes the running state match.

### The mental model

> The Automation Configuration is to MongoDB processes what a Kubernetes Deployment is to pods. You declare the target; agents converge.

When a `mongod`/`mongos` matches its declared configuration, the process is in **goal state**. The project as a whole is at goal state when every process has reached its target.

For replica sets, the project reaches goal state when "the replica set is active and has a healthy majority" — not when every member is healthy. This matters during rolling restarts; goal state can flap.

### What the Automation Config controls

- Process inventory — which hosts run `mongod`/`mongos`, with which roles (PRIMARY/SECONDARY/ARBITER/CONFIG/SHARD/MONGOS)
- MongoDB version per process
- Storage engine, paths, port
- Replica set membership, voting, priority, tags, hidden flag
- Sharded cluster topology (shards, config server, mongos routers)
- Authentication mechanism (SCRAM, x509, LDAP, Kerberos)
- TLS config and certs
- Server parameter changes (`setParameter`)
- Custom build paths if you compile your own MongoDB

### How agents reach goal state

1. Agent polls Ops Manager for the current Automation Config version
2. If version is newer than what's running, agent computes a diff
3. Agent executes changes (config file rewrites, restarts, rs.reconfig, etc.)
4. **Agent gathers state from each cluster member every 10 seconds** and reports back
5. Ops Manager stores the most recent version of the config for which goal state was reached — if an agent **can't** apply a change, the agent continuously retries; the last successfully converged config version is preserved as the reference baseline so operators can identify the failing delta

### Atomic, ordered changes

Ops Manager orchestrates changes so they're **rolling and safe**:

- Adding a replica set member: the new member is initial-synced from existing nodes before voting members are reconfigured
- Version upgrade across a replica set: one secondary at a time, primary last, with majority writeable throughout
- Adding a shard: new shard nodes are deployed and added to the cluster atomically
- Changing TLS mode: rolling re-key with `allowTLS` → `preferTLS` → `requireTLS` progression

The operator's job is to **edit the config and watch goal state**; the agents handle the ordering.

### Common automation pitfalls

- Editing `mongod.conf` by hand on an automation-managed host — the agent will overwrite it
- Killing a `mongod` started by automation without going through the UI — the agent restarts it
- Running `rs.reconfig()` manually on an automation-managed replica set — Ops Manager will revert or, worse, fight the change
- Editing the Automation Config JSON directly via API without understanding the validation pipeline — easy to push an invalid config and lose goal state

---

## 5. Continuous Backup with PITR

Ops Manager Backup is **continuous** — every write that lands in the oplog is replicated to the Backup Daemon's head DB in near-real-time. Snapshots are then taken from the head DB at configurable intervals (typically every 6 hours).

### The flow

```
Source replica set
   │  oplog tail (designated secondary, not primary)
   ▼
Backup Daemon's head DB
   │  scheduled snapshots
   ▼
Snapshot store (blockstore | filesystem | S3)
   │
   │  + separately, oplogs stored in an "oplog store"
   ▼
Restore: take baseline snapshot + apply oplog entries to PIT
```

### How PITR works

To restore to a specific time T:

1. Ops Manager picks the most recent snapshot taken **before** T
2. Streams the snapshot to the target host via the MongoDB Backup Restore Utility
3. Streams oplog entries from time T_snapshot to T from the oplog store
4. Backup Restore Utility on the target replays oplog entries to roll forward to exactly T

Restore time depends largely on **oplog volume between the snapshot and T**. If snapshots are every 6 hours and you restore to a point 5h 59m past the snapshot, you're applying ~6 hours of oplog. Tighter snapshot intervals trade off backup overhead for faster PIT restores.

### Backup from a secondary, never the primary

The Backup Daemon's Agent backup function should sync from a **designated secondary** (the `Sync Source` setting in Ops Manager). Backing up from the primary is an anti-pattern — it consumes primary I/O and page cache, and degrades application performance. Atlas does this automatically; Ops Manager requires you to set it.

### Immutable snapshots — Object Lock

For ransomware/compliance protection, configure an **S3-compatible blockstore with Object Lock** (S3 governance or compliance mode). Once written, snapshots can't be deleted or modified for the retention period — even by Ops Manager admins.

Caveat: immutable snapshots only work on the S3 store. If you need WORM behavior, you must use S3 (or an S3-compatible store with Object Lock).

---

## 6. Backup Daemon Placement and HA

For a highly available backup service:

- Run **multiple Daemons in different failure domains** (different racks, AZs, data centers)
- Each Daemon has its own head DB workspace
- Ops Manager assigns clusters to Daemons; if a Daemon goes down, you can manually fail clusters over to a healthy Daemon (Ops Manager doesn't auto-failover Daemons — it picks one when backup is *enabled* and that one stays until reassigned via Admin > Backup > Daemons)
- For multi-DC setups, assign Daemons by data center so DC1 clusters back up to DC1 Daemons (latency, network egress, sovereignty)

For the **Backup DB (blockstore)**:

- Run it as a replica set, not standalone
- For multi-DC: stretch the blockstore replica set across DCs so a DC failure doesn't take backups offline
- Use commit log / journaling for crash safety
- Monitor disk capacity proactively — running out of blockstore disk causes backup failures across many clusters at once

For the **oplog store** (where PITR oplog entries live before being applied):

- Replica set, like the blockstore
- Sized for retention horizon × peak oplog ingestion rate

---

## 7. Monitoring and Third-Party Integrations

The MongoDB Agent ships metrics at **10-second resolution** by default. Ops Manager rolls them up over time:

- Last 24 hours: 10-second resolution
- Last week: 1-minute resolution
- Older: progressively rolled up

### Built-in alerts

Same alert types as Atlas:

- Host metrics: CPU, disk space, IOPS
- DB metrics: connections, opcounters, replication lag, oplog window
- Backup metrics: snapshot success, oplog window, head DB lag
- Process events: failover, host down, agent unresponsive

Alerts route via:

- Email
- SMS (via Twilio or similar)
- PagerDuty (native integration, bidirectional)
- Slack
- HipChat (legacy)
- Microsoft Teams
- Webhooks (templated payloads — variable substitution and regex helpers supported)
- Datadog forwarding
- OpsGenie
- VictorOps

### PagerDuty integration specifics

- Configure with either PagerDuty API key or sign in via OAuth from the Project Integrations page
- Bidirectional sync: when an Ops Manager alert closes, the PagerDuty incident resolves automatically
- Multiple alerts from the same source are filtered into the same incident
- Test button on the Send To configuration validates the integration

### Webhook templating

Webhook notifications support template variables in the URL and body. Useful for routing to:

- Custom incident management
- ChatOps systems
- Internal ticketing
- Splunk HTTP Event Collector (HEC)

Templates support variable substitution (alert metadata) and regex helpers for parsing fields.

### Datadog integration

Two flavors that are easy to confuse:

1. **Ops Manager → Datadog forwarder** (alerts only): forwards alert events to Datadog as events
2. **Datadog Agent → MongoDB direct** (metrics): Datadog runs its own MongoDB integration that connects to your `mongod` and pulls metrics. Doesn't require Ops Manager

For full visibility you typically want both — Ops Manager's automation-aware metrics, plus Datadog's view from its own agent for correlation with non-MongoDB infrastructure. The MongoDB check is included in the Datadog Agent — no separate install.

### Splunk integration

- Splunk's native MongoDB Monitor was **deprecated, end of support January 15, 2025**
- Replacement path: use the **OpenTelemetry MongoDB receiver** to ship metrics into Splunk Observability Cloud
- Or: send Ops Manager alerts via webhook to Splunk HEC and run search-driven alerting in Splunk Enterprise

If a customer asks about "Splunk + Ops Manager" today, the answer is OTel-based collection, not the deprecated Splunk-native check.

### FTDC and diagnostic capture

MongoDB Enterprise emits **Full Time Diagnostic Capture (FTDC)** files in `diagnostic.data/` under the data directory. These contain per-second metrics for the process and are invaluable for support cases. Ops Manager can collect them automatically — make sure the Agent has read access to the data directory.

---

## 8. Authentication and Federation

There are two **separate** authentication surfaces in Ops Manager:

1. **Ops Manager users** — who logs into the UI / API
2. **Managed MongoDB clusters** — what authentication the `mongod`/`mongos` processes use for *their* clients

Don't conflate them in design discussions.

### Ops Manager users (UI / API)

| Mechanism | Notes |
| --- | --- |
| Local Ops Manager users (username + password) | Default; fine for tiny deployments only |
| LDAP user authentication | Users log in to Ops Manager, Ops Manager binds to LDAP, syncs user name/email from LDAP. Deprecated in MongoDB 8.0 (LDAP for cluster auth specifically); for Ops Manager *user* auth it's still supported |
| SAML SSO | Identity Provider URL configured in Ops Manager settings; supports federation with Okta, AD FS, Azure AD, Ping, etc. |
| Two-factor authentication | Per-user TOTP on top of local or LDAP login |

### Managed cluster auth (what `mongod` uses)

> **LDAP deprecation (MongoDB 8.0):** LDAP external authentication for `mongod` processes is deprecated as of MongoDB 8.0 and targeted for removal in a future major release. This applies to *cluster auth only* — LDAP for Ops Manager UI login is a separate surface and remains supported. Migrate LDAP-authenticated clusters to OIDC / Workforce Identity Federation.

| Mechanism | Notes |
| --- | --- |
| SCRAM-SHA-1 / SCRAM-SHA-256 | Default; works everywhere |
| LDAP (external auth) | **Deprecated MongoDB 8.0** — still works in 8.x, removal in future major. Migrate to OIDC |
| Kerberos / GSSAPI | Industry standard for large client-server systems; common in legacy enterprise. Both the Monitoring Agent and Automation Agent need Kerberos principals to connect to authenticated `mongod` |
| x.509 certificate auth | Mutual TLS; supported for clients and inter-cluster |
| OIDC / Workforce + Workload Identity Federation | Modern replacement for LDAP. **No credentials stored in MongoDB**, identity comes from federated IdP. MongoDB recommends this as the LDAP successor |

### Workforce vs Workload federation

- **Workforce Identity Federation**: human users authenticating via IdP (Okta, AAD, etc.)
- **Workload Identity Federation**: service accounts / workloads authenticating via signed JWTs from cloud IdPs (AWS STS, GCP service accounts, Azure managed identity)

Both are configured per project in Ops Manager and supersede LDAP for new deployments.

### Agent → cluster auth specifics

When you enable Kerberos or LDAP on managed clusters, you must:

1. Provision the Agent user in the directory (Kerberos principal or LDAP entry)
2. Configure the MongoDB Agent's auth settings via the Automation Config
3. Roll the cluster through the auth mode change (Ops Manager orchestrates this with rolling restarts)

Skipping step 2 — turning on Kerberos via Automation Config but forgetting to give the Agent itself a principal — leaves the Agent unable to connect and goal state never reaches green.

---

## 9. Air-Gapped Deployments and Local Mode

For installations with limited or no internet access — regulated industries, government, sovereign clouds, secure enclaves — Ops Manager runs in **Local Mode**.

### What Local Mode changes

By default, the MongoDB Agent downloads MongoDB binaries from `downloads.mongodb.com` when automation provisions a new process. In Local Mode:

- The MongoDB Agent downloads binaries from **Ops Manager itself**, not the internet
- Ops Manager hosts a local copy of the **version manifest** (the catalog of valid MongoDB versions)
- Ops Manager hosts a local copy of the **archived binaries** in a designated Versions Directory

### The version manifest

Ops Manager needs a list of which MongoDB versions can be installed. This is the **version manifest**, fetched by default from:

```
https://opsmanager.mongodb.com/static/version_manifest/<OM_VERSION>.json
```

For Ops Manager 8.0, that's `https://opsmanager.mongodb.com/static/version_manifest/8.0.json`.

### Air-gap workflow

1. From a host with internet access, download the version manifest JSON for your Ops Manager version
2. Download the matching MongoDB binary archives (`.tgz` or `.zip` per OS/arch) from downloads.mongodb.com
3. Transfer manifest + binaries to the air-gapped network
4. Upload the manifest to Ops Manager via the API or copy into the Versions Directory
5. Place binaries in the Versions Directory on each Ops Manager Application host
6. Ops Manager runs **a pre-flight check at startup in Local Mode** — if a binary referenced by the manifest is missing from the Versions Directory, startup fails

This pre-flight is intentional: in Local Mode, missing binaries can't be downloaded on demand, so the system refuses to start with a manifest it can't fulfill.

### API upload alternative

You can `PUT` the manifest JSON to:

```
PUT /api/public/v1.0/versionManifest
```

with appropriate admin credentials. Useful for automation when you have a small egress channel for the manifest but not for binaries.

### Mirroring strategy

For a stable air-gapped operation:

- Keep a copy of the latest manifest pinned to your approved MongoDB version range
- Pre-mirror all binaries for OSes and archs you use (RHEL 8/9, Ubuntu, AIX, Windows, ARM, x86, IBM Power, IBM Z)
- Re-mirror only when you intentionally adopt a new MongoDB version
- Test the manifest upload + binary placement on a staging Ops Manager before production

### License activation in air-gap

Ops Manager doesn't phone home for licensing (Enterprise Advanced is bundled). The Agent doesn't need internet access either. The only outbound traffic in a fully Local Mode install is whatever you explicitly configure (Datadog, PagerDuty webhook, etc.) — and you can disable all of those if needed.

---

## 10. Kubernetes Operator Deployment

The **MongoDB Controllers for Kubernetes Operator** (formerly Enterprise Operator) deploys Ops Manager — and the clusters it manages — as Kubernetes custom resources.

### Two deployment modes

| Mode | What it deploys |
| --- | --- |
| **Single Kubernetes cluster mode** | One Ops Manager Application instance + App DB + Daemons, all in one K8s cluster. Manages MongoDB resources in that cluster (and optionally in other K8s clusters) |
| **Multiple Kubernetes cluster mode** | Multiple Ops Manager Application + App DB instances spread across K8s clusters. Higher availability and multi-region resilience |

### Custom resources

- `MongoDBOpsManager` — the Ops Manager Application + App DB topology
- `MongoDB` — a managed replica set or sharded cluster
- `MongoDBUser` — DB user
- `MongoDBCommunity` — for the (best-effort, deprecating) Community Operator path

The Operator owns the lifecycle: creating Services, StatefulSets, ConfigMaps, Secrets, and the underlying Pods. You describe **what** you want; the Operator and Ops Manager both converge to make it real.

### Architecture support

Recent Operator releases support **multi-architecture deployments**:

- x86_64 (amd64) — default
- IBM Power (ppc64le)
- IBM Z (s390x)
- ARM64 (aarch64) — increasingly common

### Community Operator deprecation

The Community Kubernetes Operator (free, MongoDB Community deployments only) reached end-of-support in November 2025 and is now in best-effort maintenance mode only. New deployments should use the Enterprise Operator (Controllers for Kubernetes) — it manages both Enterprise and Community workloads.

---

## 11. Live Migration: Ops Manager / Cloud Manager → Atlas

When a customer decides to retire their self-managed control plane and move to Atlas, the path is **Live Migration (push)** using mongosync under the hood.

### The architecture

```
Source replica set / sharded cluster
   ↑ monitored by
   Ops Manager or Cloud Manager
                              \
                               \  Live Migration session
                                \  (mongosync on migration host)
                                 ▼
                          Target Atlas cluster
```

A dedicated **migration host** runs a dedicated MongoDB Agent. That agent runs `mongosync`, which copies data in parallel chunks and tails the source oplog for continuous sync. When the customer is ready to cut over, traffic switches to Atlas; mongosync handles the final cutover with minimal downtime.

### Migration host requirements (mongosync path)

For MongoDB 6.0.17+ or 7.0.13+ sources (applies to both Cloud Manager and Ops Manager managed sources using the mongosync-based push path):

- **64-bit CPU architecture**
- **Minimum 8 CPUs**
- **Minimum 24 GB RAM**

Provision the migration host adjacent to the source so it has low-latency, high-bandwidth access to read from the source.

### Deprecation matrix

| Source version | Source managed by | Live Migration (push) status |
| --- | --- | --- |
| MongoDB 5.0 and earlier | Ops Manager | **Deprecated** |
| MongoDB 5.0 and earlier | Cloud Manager | Limited support, plan upgrade |
| MongoDB 6.0+ | Ops Manager | Supported (via mongosync) |
| MongoDB 6.0+ | Cloud Manager | Supported (via mongosync) |
| Community Edition (unmanaged) | n/a | Use `mongomirror` or `mongosync` directly, or onboard to Ops Manager / Cloud Manager temporarily |

For 5.0-and-earlier sources, the practical recommendation is: upgrade in place to 6.0 or 7.0 first (using Ops Manager Automation), then migrate. This avoids the deprecated mongomirror code path.

### Migration workflow

1. Add the source deployment to Ops Manager / Cloud Manager (if not already)
2. Provision the migration host (8 CPU, 24 GB RAM, low-latency to source)
3. Install the MongoDB Agent on the migration host with the migration role
4. Prepare the target Atlas cluster (M-tier sized appropriately, network access configured)
5. From Atlas, start the live migration session pointing at the source via Ops Manager
6. Initial sync runs in parallel chunks; mongosync writes to Atlas
7. Once initial sync completes, oplog tailing keeps Atlas current
8. At cutover: stop application writes, wait for sync to drain, switch app to Atlas connection string, resume writes

### Why this is the recommended path

- **Mongosync handles cutover phase** automatically — no manual oplog replay
- **Continuous sync** lets you take days/weeks to do the migration, with cutover at a maintenance window
- **Atlas-side orchestration** means progress, errors, and cutover are visible in the Atlas UI
- **Bidirectional during sync** — you can roll back if cutover testing fails (though writes must remain only on the source until cutover)

### Pre-cutover validations

Before the cutover window:

- Run mongosync verification — automated diff between source and target
- Confirm indexes built on target match source
- Validate connection strings and IP allowlists for the new app config
- Confirm Atlas backup and PITR window covers your post-cutover recovery needs
- Test rollback plan: if something breaks post-cutover, can you fail back to source?

### Source oplog window — the hidden migration killer

Mongosync tails the source oplog continuously between initial sync completion and cutover. If the **source oplog rolls over** (writes overwrite the start of the oplog tail mongosync is reading), mongosync falls behind and must restart initial sync from zero.

Rule of thumb: the source oplog window must be **at least 2× the expected migration duration** at peak write rate. For a multi-day migration of a write-heavy cluster:

- Confirm `rs.printReplicationInfo()` shows an oplog window comfortably larger than your planned migration window
- If the window is tight, grow `replSetResizeOplog` on the source ahead of the migration (online; no restart needed since MongoDB 3.6)
- Monitor "Replication Lag" on the migration host throughout — it's the canary for an oplog catch-up problem

A common failure pattern: customer plans a 36-hour migration with a 24-hour oplog window, hits a high-write business hour mid-migration, oplog rolls over, mongosync restarts from zero, customer misses cutover window. Sizing the oplog first is non-negotiable.

---

## 12. Admin API (`/api/public/v1.0`)

The Ops Manager Public API provides programmatic access to every management surface in the UI. Base URL:

```
https://<ops-manager-host>:<port>/api/public/v1.0/
```

### Authentication

HTTP Digest Authentication using programmatic API keys:
- **Public key** as username; **private key** used in Digest HMAC — never sent in plaintext
- Generate keys: User menu → API Keys (project-scope) or Organization → API Keys (org-scope)
- Optional IP/CIDR access lists per key

```bash
curl --user '{PUBLIC-KEY}:{PRIVATE-KEY}' --digest \
  --header 'Accept: application/json' \
  --request GET \
  "https://om-host:8080/api/public/v1.0/groups/{projectId}/clusters"
```

### Key resource paths

| Resource | Path | Purpose |
| --- | --- | --- |
| Organizations | `GET /orgs` | List orgs |
| Projects | `GET/POST /groups` | Create/list projects |
| Automation Config | `GET/PUT /groups/{gId}/automationConfig` | Read/write goal-state doc |
| Automation Status | `GET /groups/{gId}/automationStatus` | Check agent convergence |
| Hosts | `GET /groups/{gId}/hosts` | List monitored hosts |
| Measurements | `GET /groups/{gId}/hosts/{hId}/measurements` | Time-series metrics |
| Alerts | `GET /groups/{gId}/alerts` | List/acknowledge alerts |
| Alert Configs | `GET/POST /groups/{gId}/alertConfigs` | Create/update thresholds |
| Backup Configs | `GET/PATCH /groups/{gId}/backupConfigs/{clusterId}` | Backup settings |
| Snapshots | `GET /groups/{gId}/clusters/{cId}/snapshots` | List snapshots |
| Restore Jobs | `POST /groups/{gId}/clusters/{cId}/restoreJobs` | Trigger restores |
| Agents | `GET /groups/{gId}/agents/{type}` | List agents by type |
| Version Manifest | `PUT /api/public/v1.0/versionManifest` | Upload manifest (Local Mode) |

### Pagination

All list endpoints support `pageNum` (1-based) and `itemsPerPage` (max 500, default 100). Responses include a `links` array with `self`, `previous`, and `next` rel-links.

### Automation config workflow

```bash
# 1. Fetch current config
curl --user '{KEY}:{SECRET}' --digest \
  "https://om:8080/api/public/v1.0/groups/{gId}/automationConfig" > config.json

# 2. Edit config.json (add member, change version, etc.)

# 3. Push updated config
curl --user '{KEY}:{SECRET}' --digest \
  --header 'Content-Type: application/json' --request PUT \
  --data @config.json \
  "https://om:8080/api/public/v1.0/groups/{gId}/automationConfig"

# 4. Poll until all agents converge
curl --user '{KEY}:{SECRET}' --digest \
  "https://om:8080/api/public/v1.0/groups/{gId}/automationStatus"
# goalVersion == lastVersionAchieved on each agent = converged
```

### Error handling

| Code | Meaning |
| --- | --- |
| 400 | Invalid request — invalid fields are rejected, not silently ignored |
| 401 | Bad API key or insufficient role |
| 409 | Conflict (duplicate unique field) |
| 5xx | Server error — retry with backoff |

No built-in concurrency protection: last PUT to `automationConfig` wins. Implement optimistic locking by checking the `version` field before pushing updates.

---

## 13. Upgrade Procedures

### Version upgrade path — no skipping majors

| Current | Required path to 8.0 |
| --- | --- |
| 8.0.x | Direct to latest 8.0 patch |
| 7.0.x | Latest 7.0 → 8.0 |
| 6.0.x | Latest 6.0 → latest 7.0 → 8.0 |
| 5.0.x | Latest 5.0 → latest 6.0 → latest 7.0 → 8.0 |

Always upgrade to the latest patch of each major before moving to the next.

### Pre-upgrade checklist

1. **AppDB MongoDB version**: Ops Manager 8.0 requires MongoDB 6.0.0+ for the AppDB. Run `db.version()` on the AppDB primary.
2. **Managed cluster versions**: Ops Manager 8.0 does not support managing MongoDB 4.2 or earlier. Upgrade managed clusters first.
3. **Storage engine**: AppDB must use WiredTiger (not MMAPv1).
4. **Back up config files** before upgrading:
   ```bash
   cp /opt/mongodb/mms/conf/conf-mms.properties ~/backup/
   cp /opt/mongodb/mms/conf/gen.key ~/backup/
   ```
5. **AppDB replica set health**: verify `rs.status()` shows all members healthy.

### Upgrade Mode (HA deployments)

For Ops Manager 4.2+ with multiple hosts sharing one AppDB, **Upgrade Mode** activates automatically after the first host is upgraded:
- Monitoring and alerts continue operating
- UI is accessible read-only
- Write/delete APIs are disabled until all hosts are upgraded
- **Upgrade one host at a time** — never simultaneously

### Step-by-step (RPM/DEB)

```bash
# 1. Stop Backup Daemon (if on this host)
sudo service mongodb-mms-backup-daemon stop

# 2. Stop Ops Manager
sudo service mongodb-mms stop

# 3. Install package (DEB: dpkg -i, RPM: rpm -Uvh)
sudo dpkg -i mongodb-mms_<version>_x86_64.deb

# 4. Check for new required properties
diff /opt/mongodb/mms/conf/conf-mms.properties \
     /opt/mongodb/mms/conf/conf-mms.properties.rpmnew

# 5. Start Ops Manager
sudo service mongodb-mms start

# 6. Verify: log in to the UI successfully

# 7. Repeat on each additional OM host
```

### Updating agents after OM upgrade

After all Ops Manager hosts are upgraded: log in → look for "One or more agents are out of date" banner → click **Update Software Components** → confirm. Ops Manager pushes the new agent binary via rolling restart.

### Common upgrade errors

| Error | Fix |
| --- | --- |
| `Unrecognized VM option 'UseParNewGC'` | Remove `-XX:+UseParNewGC` from `mms.conf` and init script |
| `retryWrites` driver errors | Add `?retryWrites=false&retryReads=false&maxPoolSize=150` to `mongo.mongoUri` |
| Config overwritten by RPM | Check `.rpmnew` file for new required properties; merge manually |

---

## 14. Common Failure Modes

> **See also §18 Common Troubleshooting Threads** for quick-lookup diagnosis steps. This section provides deeper root-cause and resolution detail.

### Agent not reaching goal state

**Symptoms**: Deployment stuck "In Progress"; banner "Agent can't communicate with Ops Manager."

**Diagnosis**:
1. Verify agent is running: `ps aux | grep mongodb-mms-automation`
2. Check agent log: `/var/log/mongodb-mms-automation/automation-agent-verbose.log`
3. Test HTTP connectivity from agent host: `curl -v http://ops-manager-host:8080/api/public/v1.0`
4. Firewall checklist: agent → OM TCP 8080/8443; all cluster members ↔ each other TCP 27017

**Common causes**: filesystem permission errors on `dbPath`/`logPath`; port conflict; mongod.conf edited manually (agent overwrites it); version manifest missing requested MongoDB version (Local Mode); TLS cert missing SAN (agent v11.12.0.7384+); Kerberos principal not provisioned for agent

**Resolution**: fix the root cause, then use "Allow Override & Edit Configuration" in the UI or push a corrected automation config via API.

### AppDB replica set failure

**Symptoms**: Ops Manager UI unavailable or shows stale data; agents hold last known config but accept no new changes.

**Diagnosis**: `mongosh <appdb_uri>` → `rs.status()`. Check disk usage on AppDB hosts — a full disk prevents writes. Check connection pool exhaustion: add `?maxPoolSize=150` to `mongo.mongoUri` in `conf-mms.properties`.

**Recovery**: restore majority of AppDB voting members. Agents preserve running deployments while AppDB is down but cannot receive new config until connectivity is restored.

### Backup Daemon disk pressure

**Symptoms**: "No daemon has space to bind" error; `applyOps` errors in backup logs.

**Diagnosis**: `df -h` on all Daemon hosts; Admin → Backup → Daemons in the UI shows reported disk per daemon.

**Resolution**: add a Daemon host with sufficient disk; increase filesystem on existing Daemon hosts; tighten snapshot retention policy; verify groom jobs are running (they should free expired snapshots automatically).

### Backup oplog behind / oplog window exceeded

**Symptoms**: Alert "Backup Oplog Is Behind"; backup job stuck in non-Active state; PIT window shrinking.

**Root cause**: Backup Agent has not sent oplog slices for >1 hour — agent down, overloaded, can't reach replica set, or network issue. Alternatively: primary oplog rolling over faster than slices transmit (high write throughput + undersized oplog).

**Resolution**:
1. Check agent logs: Admin → Agents → {host} in UI, or `/var/log/mongodb-mms-automation/backup-agent.log`
2. If oplog is undersized: `db.adminCommand({replSetResizeOplog: 1, size: 10240})` (online, no restart)
3. After fixing: if gap is too large, trigger a **Resync** from Backup → project → affected deployment → Resync
4. Check `mms.backup.minimumOplogWindowHours` in `conf-mms.properties` — if set too high it blocks backup start even when healthy

### Agent TLS SAN requirement (v11.12.0.7384+)

MongoDB Agent v11.12.0.7384+ requires TLS certificates to include a Subject Alternative Name (SAN). Certificates with only a CommonName field will cause connection failures after agent upgrade. Verify all TLS certs include SAN values before upgrading agents.

---

## 15. Scale and Multi-Org Patterns

### Organizations and projects hierarchy

```
Global Admin
  └── Organization A
  │     ├── Project A-1  (independent Monitoring + Automation + Backup)
  │     └── Project A-2
  └── Organization B
        └── Project B-1
```

- Each **project** is a complete management silo: separate automation config, alert rules, backup jobs, API keys, and agent pool
- A host belongs to exactly one project — splitting a replica set across projects is not supported
- **Teams** (org-level) can be assigned to multiple projects for access management at scale
- Use one project per environment (prod/staging/QA) or per business unit; not per cluster

### Monitoring distribution limit

Ops Manager distributes monitoring assignments across up to **100 active MongoDB Agents per project**. For deployments with 100+ hosts, split across multiple projects to stay within this limit and prevent monitoring assignment bottlenecks.

### AppDB performance at scale

| Tuning lever | Recommendation |
| --- | --- |
| `mongo.mongoUri` connection pool | Add `?maxPoolSize=150&retryWrites=false&retryReads=false` |
| Metric retention | Reduce granular retention (Admin → Ops Manager Config → Monitoring) to limit AppDB growth |
| AppDB hardware | Dedicated hosts, SSD, 16+ GB RAM; avoid shared SAN for IOPS predictability |
| AppDB topology | 3-node replica set; co-locate at least one secondary with primary for `w:2` latency |

### Backup performance at scale

Key `conf-mms.properties` knobs (file location: `/opt/mongodb/mms/conf/conf-mms.properties` on RPM/DEB installs; `<install-dir>/conf/conf-mms.properties` on tar.gz):

```properties
# Snapshot concurrency per Daemon
mms.backup.snapshot.maxWorkers=4
mms.backup.snapshot.maxSumFileForWorkersMB=2048

# Minimum oplog window before backup is allowed to start
mms.backup.minimumOplogWindowHours=3

# Queryable snapshot JVM cache
brs.queryable.lruCacheCapacityMB=512

# Enable Prometheus metrics endpoint for Ops Manager process health
prom.listening.enabled=true
prom.listening.port=9090
```

Rule of thumb: deploy **one Backup Daemon per ~20–30 backed-up deployments**. Co-locate Daemons with snapshot stores to minimize network latency.

### Load balancing the OM UI at scale

- 2+ Ops Manager Application hosts behind an HTTP/TCP load balancer
- Load balancer must **not cache responses** — Ops Manager responses must reach the client directly
- All OM Application hosts must reach the same AppDB and snapshot stores
- Set `Load Balancer Remote IP Header: X-Forwarded-For` in OM settings so the app logs real client IPs

---

## 16. Operational Anti-Patterns

| Anti-pattern | Why it bites | What to do instead |
| --- | --- | --- |
| Co-locating App DB with customer application data | App DB I/O patterns and security domain are completely different; mixing creates lock contention and a blast radius | Dedicated 3-member replica set for App DB only |
| Single Ops Manager Application host | All UI / API access dies with one host | 2+ hosts behind a load balancer, with `X-Forwarded-For` |
| Backing up from the primary instead of designated secondary | Steals primary I/O and page cache | Set `Sync Source` to a designated secondary |
| One Backup Daemon for all clusters | Single Daemon outage = all backups offline | Multiple Daemons across failure domains |
| Letting blockstore disk fill | Backup failures cascade across many clusters | Monitor blockstore disk; alert at 70% |
| Editing `mongod.conf` on automation-managed hosts | Agent overwrites your changes | Edit the Automation Configuration through the UI/API |
| Running `rs.reconfig()` on an automation-managed replica set | Ops Manager fights you | Change replica set config via Automation Config |
| Internet-dependent Ops Manager in a regulated environment | Compliance failure; manifest fetch breaks on egress block | Local Mode with mirrored manifest and Versions Directory |
| Skipping immutable snapshots for ransomware-sensitive workloads | Snapshot deletion is part of modern ransomware playbooks | S3-compatible store with Object Lock (governance or compliance mode) |
| Mixing Ops Manager user auth with managed-cluster auth in design | These are independent — confusion in design discussions creates flawed federation strategy | Map each surface separately (OM users vs cluster clients) |
| Live Migration with a 5.0 source | Deprecated path; mongomirror has known limitations | Upgrade source to 6.0+ in place via Ops Manager Automation, then migrate |
| Sizing the App DB like a 100-host monitoring deployment when you have 5 hosts | Wasted resources | Start small; the App DB can scale up vertically as you grow |

---

## 17. Quick Decision Tables

### Which snapshot store?

| Scenario | Pick |
| --- | --- |
| Standard on-prem deployment, want dedup | **Blockstore** (MongoDB) |
| Limited operational appetite, smaller deployment | **Filesystem** |
| Need WORM / immutable snapshots | **S3 with Object Lock** |
| Need cheap scale-out object storage | **S3-compatible** (S3, MinIO, Ceph) |
| Multi-DC backup capacity | **Multiple Daemons + blockstore replica set spanning DCs** |

### How many Ops Manager hosts?

| Deployment size | Application hosts | Daemons |
| --- | --- | --- |
| Dev / single cluster | 1 | 1 (or backup off) |
| Small prod, < 20 managed processes | 2 behind LB | 1-2 |
| Medium prod, 20-100 managed processes | 2-3 behind LB | 2+ across failure domains |
| Large prod, 100+ managed processes | 3+ behind LB, sized for peak | Multiple per DC |

### When to recommend Atlas instead?

- Customer doesn't want to operate the control plane *or* the database
- Multi-cloud or multi-region with Global Clusters is a goal
- Modern features (Atlas Search, Atlas Vector Search, Atlas Stream Processing, Charts, App Services) are required
- Self-managed compliance / sovereignty isn't a hard requirement

When sovereignty *is* a hard requirement (air-gap, classified networks, regulated industries that disallow public cloud), Ops Manager remains the answer.

---

## 18. Common Troubleshooting Threads

### "Agents stuck — not reaching goal state"

1. Check the Deployment Page for the failing process — Ops Manager shows the specific stage
2. SSH to the host, check Agent log: `/var/log/mongodb-mms-automation/automation-agent.log`
3. Common causes: filesystem permissions, port conflicts, prior `mongod.conf` collision, version manifest missing the requested version (Local Mode), Kerberos/LDAP misconfig
4. After fixing the host, manually retry from the Deployment Page

### "Snapshots failing"

1. Backup Daemon health: blockstore disk full, sync source unreachable (pre-8.0: head DB lag)
2. Source-side: oplog window too short to catch up (snapshots can fall behind on write-heavy clusters)
3. Network: Daemon → source latency, blockstore → Daemon throughput
4. Pre-8.0: validate the head DB is in sync with the source replica set. 8.0+: check Daemon service status and Daemon → source connectivity directly.

### "Restore is slow"

1. Snapshot recency — restore time grows with oplog replay distance
2. Target host disk IOPS — restores can be IO-bound on target
3. Network throughput from snapshot store to target
4. Block size on blockstore — if your data has large files and block size is still 1 MB, restore performance suffers

### "Manifest doesn't show the version I want (Local Mode)"

1. The manifest you uploaded predates the MongoDB release
2. Re-download manifest from `opsmanager.mongodb.com/static/version_manifest/<OM_VERSION>.json`
3. Place matching binary archives in Versions Directory before re-uploading
4. Restart Ops Manager Application to clear the manifest cache

### "Cloud Manager UI shows agents reporting, but no metrics"

1. Confirm Agent has connectivity to Cloud Manager endpoints (outbound HTTPS)
2. Confirm Agent has DB user creds with `clusterMonitor` role on each managed `mongod`
3. For Datadog forwarding specifically: confirm the project-level integration is configured, not just the Datadog Agent on the host
4. Check the Agent log for auth failures during metric collection

---

## 19. TL;DR Facts

- **Ops Manager is not Atlas.** It's a control plane for self-managed MongoDB. Atlas is a managed database service.
- **Cloud Manager is not Atlas either.** It's hosted Ops Manager. Customer still operates the clusters.
- **Ops Manager App DB is metadata only.** Backups go to a separate snapshot store, not the App DB.
- **The Backup Daemon does the actual backup work.** Multiple Daemons = multiple parallel backup capacity.
- **Goal state is the model.** You declare, agents converge. Don't hand-edit `mongod.conf`.
- **Air-gap means Local Mode.** Manifest + binaries pre-staged, no internet calls during operation.
- **LDAP is deprecated as of MongoDB 8.0** for cluster auth. Migrate to OIDC / Workforce or Workload Identity Federation.
- **Live Migration uses mongosync.** Migration host needs 8 CPU / 24 GB RAM minimum.
- **Source oplog window must exceed migration duration × 2.** Or mongosync restarts from zero.
- **Object Lock requires S3-compatible store.** Blockstore and filesystem stores can't be made immutable.
- **The Splunk-native MongoDB Monitor is dead** (EOS Jan 2025). Use OpenTelemetry receiver.

---

## 20. Concrete Examples

### Automation Configuration excerpt — adding a member to a replica set

The Automation Config is JSON stored in the App DB. You can edit it through the UI or `PUT /api/public/v1.0/groups/{groupId}/automationConfig`. Adding a third member to a replica set looks roughly like:

```json
{
  "processes": [
    { "name": "rs0_1", "hostname": "host1.corp", "port": 27017,
      "args2_6": { "replication": { "replSetName": "rs0" } }, "version": "7.0.14" },
    { "name": "rs0_2", "hostname": "host2.corp", "port": 27017,
      "args2_6": { "replication": { "replSetName": "rs0" } }, "version": "7.0.14" },
    { "name": "rs0_3", "hostname": "host3.corp", "port": 27017,
      "args2_6": { "replication": { "replSetName": "rs0" } }, "version": "7.0.14" }
  ],
  "replicaSets": [
    { "_id": "rs0", "members": [
        { "_id": 0, "host": "rs0_1", "priority": 1, "votes": 1 },
        { "_id": 1, "host": "rs0_2", "priority": 1, "votes": 1 },
        { "_id": 2, "host": "rs0_3", "priority": 1, "votes": 1 }
    ]}
  ],
  "version": 42
}
```

Submit, then watch the Deployment Page for the new member's stages: `INSTALL` → `INITIAL_SYNC` → `RUNNING` → reach goal state.

### Kubernetes Operator — MongoDBOpsManager CR

A minimal Ops Manager CR for the Enterprise Kubernetes Operator:

```yaml
apiVersion: mongodb.com/v1
kind: MongoDBOpsManager
metadata:
  name: ops-manager
  namespace: mongodb
spec:
  replicas: 2
  version: "8.0.0"
  adminCredentials: ops-manager-admin-secret
  applicationDatabase:
    members: 3
    version: "7.0.14"
    persistent: true
  externalConnectivity:
    type: LoadBalancer
  backup:
    enabled: true
    headDB:
      storage: 500Gi
      storageClass: fast-ssd
```

The Operator creates the StatefulSets for the App DB, the Deployment for the Ops Manager Application, the LoadBalancer Service, and the Backup Daemon StatefulSet.

### Version manifest upload (air-gap)

```bash
# On a host with internet access
curl -fsSL https://opsmanager.mongodb.com/static/version_manifest/8.0.json \
  -o version_manifest_8.0.json

# Transfer to air-gapped network, then POST to Ops Manager admin API
curl -u "admin:password" --digest \
  -X PUT "https://ops-manager.corp/api/public/v1.0/versionManifest" \
  -H "Content-Type: application/json" \
  --data @version_manifest_8.0.json
```

After this, place the matching MongoDB binary archives in the Versions Directory on each Application host.

---

## Sources

1. [Ops Manager Architecture — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/core/system-overview/)
2. [Ops Manager Overview — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/application/)
3. [Ops Manager System Requirements — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/core/requirements/)
4. [Configure a Highly Available Ops Manager Application — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/configure-application-high-availability/)
5. [Configure a Highly Available Ops Manager Backup Service — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/configure-backup-high-availability/)
6. [Install the Ops Manager Application Database and Backup Database — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/prepare-backing-mongodb-instances/)
7. [Enable Application Database Monitoring — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/enable-appdb-monitoring/)
8. [Automation Configuration — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/reference/cluster-configuration/)
9. [Update a Project's Automation Configuration — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/update-automation-configuration/)
10. [FAQ: Automation — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/reference/faq/faq-automation/)
11. [Backup Process — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/core/backup-overview/)
12. [Backup Preparations — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/core/backup-preparations/)
13. [Restore from a Specific Point-in-Time — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/restore-pit-snapshot-http/)
14. [Snapshot Storage — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/admin/backup/snapshot-storage-page/)
15. [Manage Blockstore Snapshot Storage — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/manage-blockstore-storage/)
16. [Manage S3-Compatible Snapshot Storage — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/manage-s3-blockstore-storage/)
17. [Manage File System Snapshot Storage — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/manage-filestore-storage/)
18. [Configure Block Size in a Blockstore — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/upcoming/tutorial/configure-block-size/)
19. [Immutable S3 Snapshots with Object Lock — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/immutable-s3-snapshots/)
20. [Configure Deployment to Have Limited Internet Access (Local Mode) — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/configure-local-mode/)
21. [Update Version Manifest Manually — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/update-version-manifest/)
22. [Retrieve the Ops Manager Version Manifest — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/reference/api/version-manifest/)
23. [Enable LDAP Authentication for your Ops Manager Project — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/enable-ldap-authentication-for-group/)
24. [Enable Kerberos Authentication for your Ops Manager Project — MongoDB Docs](https://docs.opsmanager.mongodb.com/current/tutorial/enable-kerberos-authentication-for-group/)
25. [Configure Ops Manager Users for LDAP Authentication and Authorization — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/configure-for-ldap-authentication/)
26. [LDAP Deprecation — MongoDB Manual](https://www.mongodb.com/docs/manual/core/ldap-deprecation/)
27. [Monitor with Third-Party Service Integrations — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/third-party-service-integrations/)
28. [Integrate with PagerDuty — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/pagerduty-integration/)
29. [Configure Alert Settings — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/manage-alert-configurations/)
30. [Datadog MongoDB Integration — Datadog Docs](https://docs.datadoghq.com/integrations/mongodb/)
31. [Splunk MongoDB (end of support) — Splunk Observability](https://help.splunk.com/en/splunk-observability-cloud/manage-data/available-data-sources/supported-integrations-in-splunk-observability-cloud/applications-databases/mongodb-end-of-support)
32. [Migrate from Ops Manager to Atlas — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/migrate-to-atlas/)
33. [Provision a Migration Host for MongoDB Agent — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/provision-migration-host/)
34. [Live Data Migration from Ops Manager to MongoDB Atlas — MongoDB Docs](https://www.mongodb.com/docs/ops-manager/current/reference/api/cloud-migration/)
35. [Live Migrate (Push) a Cluster Monitored by Cloud Manager into Atlas — Atlas Docs](https://www.mongodb.com/docs/atlas/import/c2c-push-live-migration/)
36. [Deploy an Ops Manager Resource — Kubernetes Operator Docs](https://www.mongodb.com/docs/kubernetes/current/tutorial/deploy-om-container/)
37. [Plan Your Ops Manager Resource — Kubernetes Operator Docs](https://www.mongodb.com/docs/kubernetes/current/tutorial/plan-om-resource/)
38. [Ops Manager Architecture in Kubernetes — Kubernetes Operator Docs](https://www.mongodb.com/docs/kubernetes-operator/v1.25/tutorial/om-arch/)
39. [Enterprise Advanced — Ops Manager Product Page](https://www.mongodb.com/products/self-managed/enterprise-advanced/ops-manager)
40. [Cloud Manager Overview — Cloud Manager Docs](https://www.mongodb.com/docs/cloud-manager/application/)
41. [Monitoring Metrics Per Cloud Manager Plan — Cloud Manager Docs](https://www.mongodb.com/docs/cloud-manager/reference/monitoring-metrics-per-plan/)
42. [MongoDB Cloud Manager Product Page](https://www.mongodb.com/products/tools/cloud-manager)
