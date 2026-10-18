<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-operations-expert` hub.** Formerly the standalone `mongodb-backup-restore` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-backup-restore
category: mongodb
version: 1.2.0
updated: 2026-05-29
tags: [mongodb, atlas, backup, restore, disaster-recovery, compliance, pit-recovery, snapshots]
description: "MongoDB backup and restore — Atlas Cloud Backup snapshot policies, Continuous Cloud Backup PIT windows and oplog sizing, Queryable Backups, Ops Manager / Cloud Manager backup for self-managed deployments, restore workflows (download .tar.gz, automated to new cluster, in-place, point-in-time), Backup Compliance Policy and WORM retention, cross-region snapshot copy for DR, restore verification and tabletop exercises, snapshot interactions with primary promotion (case 01574262 pattern), HIPAA/SOC2/PCI backup compliance, or troubleshooting stuck snapshots, failed restores, missing backups, RPO/RTO gaps, and backup anti-patterns. TRIGGER for: Atlas backup policy design, PIT window sizing, Queryable Backup forensics, BCP/WORM compliance, DR runbooks, restore testing, or cases where a customer says 'backups exist but cannot restore'. SKIP for live cluster-to-cluster data movement or zero-downtime cutover — that requires mongosync (use mongosync skill)."
when_to_use:
  - Designing or reviewing an Atlas backup policy (snapshot cadence and retention)
  - Sizing Continuous Cloud Backup PIT windows and explaining cost implications
  - Planning DR with cross-region snapshot copy or regional outage runbooks
  - Investigating restore failures, stuck snapshots, or snapshot/primary-election interactions
  - Reviewing backup compliance for regulated workloads (HIPAA, SOC 2, PCI DSS, GDPR)
  - Authoring restore-test runbooks or tabletop exercises
  - Explaining Backup Compliance Policy (BCP) WORM semantics and modification process
  - Triaging support cases where backups exist but cannot be restored
  - Configuring Ops Manager or Cloud Manager backup for self-managed deployments
  - Choosing between automated restore, PIT restore, download, and queryable backup
when_not_to_use:
  - Live cluster-to-cluster data movement or continuous sync — use mongosync
  - Atlas Live Migration between cloud regions — use mongosync or Atlas Live Migration
  - Schema migration or data transformation during restore — combine with mongodb-migration-patterns
  - Ops Manager infrastructure setup beyond backup configuration — use mongodb-ops-manager
related_skills:
  - mongosync
  - mongodb-ops-manager
  - mongodb-disaster-recovery
  - mongodb-migration-patterns
  - mongodb-atlas-iac
  - mongodb-atlas-terraform
  - mongodb-compliance
  - mongodb-monitoring-observability
---

# MongoDB Backup and Restore

This skill covers the full backup/restore surface for MongoDB Atlas and Ops Manager / Cloud Manager — what to enable, how to size it, how to restore under pressure, and which anti-patterns to refuse to ship.

## When to load this skill

- Designing or reviewing an Atlas backup policy (hourly/daily/weekly/monthly/yearly cadence + retention)
- Sizing Continuous Cloud Backup PIT windows and explaining cost implications to a customer
- Planning DR with cross-region snapshot copy or a runbook for an active-region outage
- Investigating restore failures, stuck snapshots, or snapshot operations that appear to interact with primary election
- Reviewing backup compliance for regulated workloads (HIPAA, SOC 2, PCI DSS, GDPR)
- Authoring restore-test runbooks or tabletop exercises
- Triaging support cases where the customer claims "backups exist" but cannot restore (see case 01574262 pattern)

---

## 1. Atlas Cloud Backup — snapshots, frequency, retention

Atlas Cloud Backup is the default backup mechanism for M10+ dedicated clusters. It uses the **cloud provider's native disk-snapshot capabilities** (AWS EBS / Azure Managed Disks / GCP Persistent Disk), so snapshots are incremental at the block level — fast to take, fast to restore.

### Snapshot frequencies (five tiers)

| Frequency | Typical default retention | Notes |
| --- | --- | --- |
| Hourly   | 2 days   | Highest RPO granularity; main source of recent restores |
| Daily    | 7 days   | Workhorse for "yesterday's data" restores |
| Weekly   | 4 weeks  | Common for monthly compliance windows |
| Monthly  | 12 months | Quarterly / annual compliance |
| Yearly   | up to 7 years | Long-tail regulatory retention |

Each tier has its own retention period and snapshot time (UTC). The default backup policy uses 18:00 UTC and four active tiers (hourly, daily, weekly, monthly).

### Overlap rule

When two policy items would generate the same snapshot, Atlas associates the snapshot with the policy item with the **longest retention** — you do not pay twice for the same snapshot.

### On-demand snapshots

```bash
# Atlas CLI — take an immediate snapshot
atlas backups snapshots create \
  --clusterName myCluster \
  --desc "pre-schema-migration $(date -u +%FT%TZ)" \
  --retentionInDays 30
```

Rule of thumb: take an on-demand snapshot **before** any destructive or schema-changing operation, and **wait until it completes** before performing the change. Atlas refuses a second on-demand snapshot while one is `queued` or `inProgress`.

### Storage

Atlas creates snapshot storage volumes in the **same region as the cluster's current primary**. Maintenance events or cloud-provider events that elect a new primary can move the snapshot storage volume — see Section 9.

---

## 2. Continuous Cloud Backup (Point-in-Time Recovery)

Continuous Cloud Backup adds **oplog tailing** on top of standard snapshots so you can restore to any second within a configured PIT window — not just to the moments when snapshots were taken.

### How it works

1. Atlas takes scheduled snapshots per the cloud-backup policy.
2. Atlas continuously copies the cluster's oplog into S3 (or the equivalent object store) for the duration of the PIT window.
3. On restore, Atlas mounts the most recent snapshot **before** the target time, then replays the oplog forward to the target.

### Granularity

- **Date & Time** target: 1-minute precision (RPO ≈ 1 minute)
- **Oplog Timestamp** target: 1-second precision (use when you need to land just before a specific operation, e.g., right before a destructive `updateMany`)

### Window sizing

The PIT window is configurable (commonly 24 hours to 7 days). Within the window, you can restore to any moment. Outside the window, you fall back to the nearest snapshot.

### Cost implications

PIT is billed on **oplog storage volume** in addition to snapshot storage:

- Longer PIT window → larger oplog footprint → higher monthly cost
- Write-heavy clusters generate larger oplogs than read-heavy clusters
- Backups list price starts at **$0.14/GB/month** for snapshot storage; oplog storage is billed against the same per-GB rate in the highest-priority region

### Configuration (Atlas Admin API)

```bash
# Enable Continuous Cloud Backup via Atlas Admin API
curl --user "$PUB_KEY:$PRIV_KEY" --digest \
  --header "Content-Type: application/json" \
  --request PATCH \
  "https://cloud.mongodb.com/api/atlas/v2/groups/$PROJECT_ID/clusters/$CLUSTER/backup/schedule" \
  --data '{ "useOrgAndGroupNamesInExportPrefix": true,
            "policies": [...],
            "referenceHourOfDay": 18,
            "referenceMinuteOfHour": 0,
            "restoreWindowDays": 7 }'
```

`restoreWindowDays` is the PIT window in days. Set it to match your RPO target — e.g., RPO = 24 h → `restoreWindowDays: 1`; RPO = 7 days → `restoreWindowDays: 7`. Do not set it to "as long as possible" — every additional day costs real money in oplog storage.

---

## 3. Queryable Backups

Queryable Backups let you **run reads against a backup snapshot without restoring it to a live cluster**. The snapshot is mounted as a read-only deployment that accepts standard MongoDB queries.

### Use cases

- **Forensics**: when did the bad write happen? Query several snapshots in a row to bisect the corruption window.
- **Targeted recovery**: pull a single document or collection out of a 2 TB snapshot without provisioning a 2 TB restore cluster.
- **Audit / compliance**: prove what data existed at a regulatory checkpoint without disturbing production.
- **Pick the right PIT target**: query consecutive snapshots to find the last clean state before restoring with PIT to that moment.

### Limitations

- Read-only — no writes, no index builds, no aggregation `$out`/`$merge`.
- Performance is **not** comparable to a live cluster; treat it as cold storage with a query interface.
- Available on Atlas (dedicated M10+) and Ops Manager / Cloud Manager.

### Workflow

```text
1. Open the snapshot in the Atlas UI → Backup → Snapshots → Query
2. Atlas spins up a queryable backup deployment (takes 1-5 min)
3. Connect via the provided connection string (uses standard mongo URI + temp creds)
4. Run reads; the deployment auto-tears-down after idle timeout
```

---

## 4. Ops Manager Backup (self-managed)

> **Deep reference:** for full Ops Manager and Cloud Manager coverage — App DB, Backup Daemon HA, Object Lock, oplog stores, sizing, Live Migration to Atlas, air-gap — see the `mongodb-ops-manager` skill. This section is the backup-focused summary.

Ops Manager is MongoDB's on-premise control plane (Enterprise Advanced). Its backup system mirrors Atlas conceptually but you operate every component.

### Component architecture

```
+-------------------+        +--------------------+
|  MongoDB Agent    |        |  Ops Manager App   |
|  (backup module)  | -----> |  Database (config) |
|  oplog-tails the  |        +--------------------+
|  PRIMARY (or a    |                |
|  designated node) |                v
+-------------------+        +--------------------+
                             |  Backup Daemon(s)  |
                             |  - apply oplog     |
                             |  - take snapshots  |
                             |  - replicate to    |
                             |    snapshot store  |
                             +--------------------+
                                      |
                                      v
                  +---------------------------------------+
                  | Snapshot Store (choose one or more):  |
                  |   - Blockstore (MongoDB-backed)       |
                  |   - S3 Blockstore (AWS S3 / S3-compat)|
                  |   - Filesystem Store (NFS / local FS) |
                  +---------------------------------------+
```

### Snapshot store types

| Store type | Best for | Notes |
| --- | --- | --- |
| **Blockstore** | Small-to-medium fleets | Snapshots stored as binary blocks in a dedicated MongoDB deployment; deduplicated |
| **S3 Blockstore** | Cloud-adjacent on-prem | Blocks pushed to S3 / MinIO / S3-compatible; cheap at scale |
| **Filesystem Store** | Air-gapped / NFS shops | Snapshots as files on disk; required for incremental file-system snapshots |

### Backup Daemon scaling

Multiple Backup Daemons can run in parallel — Ops Manager picks a daemon when a deployment enables backup. Daemons can be assigned to specific data centers so a daemon in DC1 handles DC1 clusters (latency / sovereignty).

### Agent placement

Default: the MongoDB Agent with the backup module tails oplogs **from the primary**. For Atlas-style behavior (tail from a secondary), use the `Sync Source` setting to point the backup agent at a designated secondary — this avoids primary I/O contention.

---

## 5. Restore workflows

Atlas offers three restore modes for any snapshot or PIT target:

### A. Automated restore (to new or existing cluster)

```bash
# Atlas CLI — restore most recent snapshot to a target cluster
atlas backups restores start automated \
  --clusterName source-cluster \
  --targetClusterName restored-cluster \
  --targetProjectId $TARGET_PROJECT \
  --snapshotId $SNAPSHOT_ID
```

- The target cluster's data is **deleted** before restore.
- Target cluster is **unavailable** for the duration of the restore.
- Fastest path for an in-place rollback.

### B. Point-in-time restore

```bash
atlas backups restores start pointInTime \
  --clusterName source-cluster \
  --targetClusterName restored-cluster \
  --pointInTimeUTCSeconds 1716950400
```

- Requires Continuous Cloud Backup to be enabled.
- `pointInTimeUTCSeconds` lands you at 1-second granularity (oplog timestamp).
- Atlas picks the latest snapshot ≤ target, then replays the oplog forward.

### C. Download (.tar.gz)

```bash
# Generate a download URL (one-time, expires in 1 hour)
atlas backups restores start download \
  --clusterName source-cluster \
  --snapshotId $SNAPSHOT_ID
```

- Atlas returns a one-time URL to a `.tar.gz` of the raw data files.
- Download must complete within 1 hour of URL creation.
- Use for off-platform forensics, regulator-mandated extraction, or migration to an on-prem deployment.

### Restore time selection cheat-sheet

| Situation | Restore mode |
| --- | --- |
| Bad migration ran 10 minutes ago, need to roll back | **Point-in-time** to T-15 min |
| Need yesterday's full dataset in a sandbox | **Automated** to a new cluster, pick yesterday's daily snapshot |
| Auditor needs raw data files | **Download** the snapshot |
| Lost a single collection | Restore most recent snapshot to a new cluster, then `mongodump`/`mongorestore` just the collection back to prod |
| Just need to peek at old data | **Queryable Backup** — don't bother with a restore |

---

## 6. Backup Compliance Policy

A Backup Compliance Policy makes backups **WORM (Write Once Read Many)** at the **organization level** — it applies to every project and cluster in the org. Once enabled, no Atlas user — regardless of role — can shorten retention, disable backups, or delete snapshots before they expire. See Section 11 for the complete deep reference including API, compliance frameworks, and pitfalls.

### What it locks down

- **Minimum retention floors** for each policy tier (hourly/daily/weekly/monthly/yearly).
- **PIT window minimum** — operators cannot shrink it.
- **Snapshot copy protection** — copies cannot be deleted before retention expires.
- **Encryption at Rest with Customer Key Management** can be required; non-encrypted clusters fail compliance.

### Disabling requires out-of-band verification

Once enabled, the policy can only be disabled by a **designated security contact** completing an out-of-band email verification with MongoDB Support (typically 3–5 business days processing time). This is intentional: an attacker who steals an Atlas admin credential cannot quickly turn off backups before exfiltrating data.

### Regulatory mapping

| Framework | Backup Compliance Policy satisfies |
| --- | --- |
| HIPAA   | Backup retention immutability, encryption at rest |
| SOC 2   | Change-control over retention policy |
| PCI DSS | Tamper-evident retention, key management |
| GDPR    | Demonstrable data-protection controls (combined with field-level encryption) |

### Encryption at rest for snapshots

Atlas encrypts all snapshot blocks with **AES-256** in the cloud provider's object store (S3 / Azure Blob / GCS). If you enable Customer Key Management, snapshots are wrapped with your KMS-held CMK on top of the provider key, giving you the ability to revoke decryption by revoking the key.

### Example Atlas CLI

```bash
atlas backups compliancePolicy enable \
  --authorizedUserEmail security@example.com \
  --authorizedUserFirstName Security --authorizedUserLastName Lead
```

---

## 7. Cross-region snapshot copy (DR)

By default, Atlas stores snapshots in the **same region as the current primary**. For DR, copy them to one or more secondary regions.

### How copies are scheduled

Each snapshot copy policy item attaches to one of the five frequency tiers and names a target region. Atlas copies snapshots **asynchronously** after the primary snapshot completes — typical copy lag is **15-60 minutes**.

### Selective copy (granular control)

You can copy specific snapshots (e.g., only weekly + monthly + yearly to a cheap DR region) rather than every snapshot in a tier. This reduces cross-region data transfer cost.

### PIT in DR regions

If you set Point-in-Time Restore = On for a snapshot copy policy item, Atlas also copies **oplog segments** to that region. After a primary-region outage, you can restore PIT directly from the DR region.

### Restore performance after a regional outage

- If snapshots are copied to **every region** in a multi-region cluster, Atlas can do a **direct-attach restore** (fast, no streaming).
- Otherwise Atlas does a **streaming restore** across regions — measurably slower (often 2-3x), and bandwidth-billed.

### Configuration example

```json
{
  "copySettings": [
    {
      "cloudProvider": "AWS",
      "regionName": "US_WEST_2",
      "shouldCopyOplogs": true,
      "frequencies": ["WEEKLY", "MONTHLY", "YEARLY"]
    }
  ]
}
```

---

## 8. Backup verification — restore testing and tabletop exercises

**A backup that has never been restored is not a backup; it is an assumption.** Verification is the single highest-leverage activity in this skill.

### Verification pyramid

1. **Continuous**: Atlas / Ops Manager monitors snapshot success and oplog window — alert on failure.
2. **Weekly**: scripted restore of the latest snapshot to a staging cluster, run integrity checks (`db.runCommand({validate: 'collname'})`, document counts vs production).
3. **Monthly**: full PIT restore to a target time, application smoke test against the restored cluster.
4. **Quarterly tabletop**: simulate a real incident (ransomware, accidental `dropDatabase`, region outage). Time the full recovery path — that is your real RTO.

### Minimum integrity checks after restore

```javascript
// Document count parity (per collection)
db.getSiblingDB('app').runCommand({ collStats: 'orders' }).count
// Index parity
db.orders.getIndexes()
// Sample-document spot check
db.orders.find().sort({_id:-1}).limit(10)
// Validate (catches corruption)
db.orders.validate({ full: true })
```

### Tabletop scenarios worth running

| Scenario | What to measure |
| --- | --- |
| `db.dropDatabase()` ran in prod 5 min ago | PIT restore RTO, data loss in seconds |
| Region outage, primary region gone | DR-region restore RTO, lag vs RPO |
| Customer deleted records yesterday under GDPR, now requests recovery (legal hold) | Snapshot accessibility, queryable-backup workflow |
| Ransomware encrypts the live cluster | Compliance-policy-protected snapshots restore cleanly |
| Backup agent stopped silently 30 days ago | Monitoring should have caught this on day 1 |

### Document everything

The runbook **is** the disaster recovery plan. If it lives only in an engineer's head, you do not have a plan.

---

## 9. Snapshot operations and primary promotion (case 01574262 pattern)

There is a documented interaction between long-running snapshot operations and replica-set events that can make snapshots **appear** to block primary promotion. The symptom: a primary step-down or maintenance window is queued behind an in-flight snapshot or snapshot-copy operation, and the cluster appears stuck.

### Root cause

- Atlas creates snapshot storage volumes in the **same region as the current primary**.
- Events that move the primary (maintenance, cloud-provider event, manual `replSetStepDown`) can require Atlas to move or re-create the snapshot storage volume.
- An in-flight snapshot or snapshot copy cannot be cleanly migrated mid-flight; Atlas waits for completion before the election logic finishes the handoff.
- The user-visible effect: "we tried to step down to do a maintenance window, but it's been pending for 40 minutes." The cluster is healthy; the snapshot pipeline is the long pole.

### Operational guidance

- **Before planned maintenance** (version upgrade, instance resize, region change): check `atlas backups snapshots list --status inProgress` and **wait for completion** before triggering the change.
- **Before a major version upgrade**: take an on-demand snapshot and wait for it to finish before launching the upgrade — the docs explicitly call this out.
- **If you see a stuck step-down**: do not force-kill it. Check Atlas Activity Feed for an in-flight snapshot or cross-region copy; let it finish.
- **For repeat customers with this symptom**: schedule maintenance windows **outside** the snapshot frequency tier that runs most often (e.g., if hourly snapshots run at :00, schedule maintenance at :30).

### Detection

```bash
atlas backups snapshots list --clusterName myCluster \
  --status inProgress,queued
```

Anything returned here will gate primary-mutating operations.

### Case 01574262 takeaway

The TS Tools case file shows this exact pattern: customer perceived "snapshots blocking primary promotion" during a maintenance window. Resolution was operational (sequence the maintenance after snapshot completion), not a code defect. Document this in the customer's runbook so the next on-call engineer doesn't escalate.

---

## 10. Backup anti-patterns

| Anti-pattern | Why it hurts | Correct pattern |
| --- | --- | --- |
| **Backup is the entire DR plan** | Backups protect against data loss, not availability. A region outage with no DR cluster = downtime regardless of backups. | Combine backups with multi-region cluster topology, snapshot copy to DR region, documented failover runbook. |
| **Never testing restores** | First time you discover a backup is corrupt is during a real incident. RTO is unknown. | Weekly automated restore to staging; quarterly tabletop. |
| **Replication = backup** | A bad `db.dropDatabase()` replicates to every secondary within milliseconds. Replication protects against node loss, not logical errors. | Backups + PIT to recover from logical errors. |
| **Backing up from the primary** (self-managed) | Backup reads consume primary I/O / page cache, degrading application performance. | Tail oplogs from a designated secondary (Atlas default; Ops Manager `Sync Source` setting). |
| **Unencrypted backups** | Snapshots live in object storage; without encryption at rest, leak = full data exfiltration. | Atlas encrypts by default (AES-256). Enable Customer Key Management for sensitive workloads. Require it via Backup Compliance Policy. |
| **Storing snapshots in the same region as the cluster** | Region outage = no recovery. | Cross-region snapshot copy with PIT enabled in DR region. |
| **Letting PIT window equal "as long as possible"** | Oplog storage cost scales linearly with window × write throughput. Customers get billing surprises. | Size PIT window to RPO target. 24h for most apps; up to 7 days for high-stakes write workloads. |
| **No monitoring on backup success** | Agent stops, snapshots silently fail, 30 days later you find out during a real incident. | Alert on every snapshot failure and on oplog window dropping below threshold. |
| **Manual on-demand snapshots only** | Operator forgets, ships the migration, then needs to roll back from a 7-day-old snapshot. | Automate via scheduled policy; on-demand is the **belt** on top of the **suspenders**. |
| **Restoring directly over production** without testing | Restore takes longer than expected, target cluster is unavailable mid-restore, application down. | Always restore to a **new** cluster first, validate, then swap connection strings or promote. |
| **Ignoring queryable backups** | Customers do unnecessary full restores to look at one collection — burns hours of RTO budget. | Use queryable backup for any "what did the data look like at T" question. |

---

## Decision flowcharts

### "Should I enable Continuous Cloud Backup?"

```
RPO target ≥ 24h?    ─ yes ─→  Daily snapshots alone suffice.
       │
       no
       ↓
RPO target ≥ 1h?     ─ yes ─→  Hourly snapshots may suffice
                                (no oplog cost).
       │
       no
       ↓
ENABLE Continuous Cloud Backup. Size restoreWindowDays to your RPO
target. Atlas guarantees ≈ 1-minute RPO (1-second on oplog-timestamp target).
```

### "How do I restore from a bad migration?"

```
Is Continuous Cloud Backup enabled?
  yes → Point-in-time restore to T-(migration_duration + 1min)
  no  → Restore most recent pre-migration snapshot
        Use queryable backup first to confirm it has the pre-migration state.
```

### "Which restore mode?"

```
Need to keep running on existing cluster?     → In-place restore (downtime)
Want zero risk to production?                  → Automated restore to NEW cluster, then swap
Need raw data files for off-platform tooling?  → Download (.tar.gz)
Just need to read old data, not restore?       → Queryable backup
```

---

## Quick reference: Atlas CLI commands

```bash
# List snapshots
atlas backups snapshots list --clusterName myCluster

# Take on-demand snapshot
atlas backups snapshots create --clusterName myCluster \
  --desc "pre-upgrade" --retentionInDays 30

# List in-flight snapshots (gate for maintenance)
atlas backups snapshots list --clusterName myCluster --status inProgress,queued

# Start automated restore to new cluster
atlas backups restores start automated \
  --clusterName myCluster --targetClusterName myCluster-restored \
  --snapshotId $SNAPSHOT_ID

# PIT restore
atlas backups restores start pointInTime \
  --clusterName myCluster --targetClusterName myCluster-restored \
  --pointInTimeUTCSeconds $(date -u -v -10M +%s)  # 10 minutes ago (BSD date)

# Download snapshot (.tar.gz, URL valid 1h)
atlas backups restores start download \
  --clusterName myCluster --snapshotId $SNAPSHOT_ID

# Enable Backup Compliance Policy
atlas backups compliancePolicy enable \
  --authorizedUserEmail security@example.com \
  --authorizedUserFirstName Security --authorizedUserLastName Lead

# Configure backup schedule (policy items + PIT window)
atlas backups schedule update --clusterName myCluster --file backup-policy.json
```

---

## References

1. [Manage Your Backup Snapshots — MongoDB Atlas Docs](https://www.mongodb.com/docs/atlas/backup/cloud-backup/snapshot-management/)
2. [Backup Scheduling, Retention, and On-Demand Snapshots — MongoDB Atlas Docs](https://www.mongodb.com/docs/atlas/backup/cloud-backup/scheduling/)
3. [Guidance for Atlas Backups — Atlas Architecture Center](https://www.mongodb.com/docs/atlas/architecture/current/backups/)
4. [Recover a Point In Time with Continuous Cloud Backup — Atlas Docs](https://www.mongodb.com/docs/atlas/recover-pit-continuous-cloud-backup/)
5. [Restore from Continuous Cloud Backup — Atlas Docs](https://www.mongodb.com/docs/atlas/backup/cloud-backup/restore-from-continuous/)
6. [Query a Backup Snapshot — Ops Manager Docs](https://www.mongodb.com/docs/ops-manager/current/tutorial/query-backup/)
7. [Ops Manager Backup Process — Ops Manager Docs](https://www.mongodb.com/docs/ops-manager/current/core/backup-overview/)
8. [Ops Manager Snapshot Storage — Ops Manager Docs](https://docs.opsmanager.mongodb.com/current/admin/backup/snapshot-storage-page/)
9. [Restore from a Locally-Downloaded Snapshot — Atlas Docs](https://www.mongodb.com/docs/atlas/backup/cloud-backup/restore-from-local-file/)
10. [Configure a Backup Compliance Policy — Atlas Docs](https://www.mongodb.com/docs/atlas/backup/cloud-backup/backup-compliance-policy/)
11. [Storage Engine and Cloud Backup Encryption — Atlas Docs](https://www.mongodb.com/docs/atlas/backup/cloud-backup/cloud-backup-encryption/)
12. [Copy Snapshots to Additional Regions — Atlas Docs](https://www.mongodb.com/docs/atlas/backup/cloud-backup/snapshot-distribution/)
13. [Guidance for Atlas Disaster Recovery — Atlas Architecture Center](https://www.mongodb.com/docs/atlas/architecture/current/disaster-recovery/)
14. [Optimizing Disaster Recovery: Enhanced Control for Cross-Region Snapshots — MongoDB Blog](https://www.mongodb.com/company/blog/product-release-announcements/introducing-enhanced-control-for-cross-region-snapshots)
15. [Data Resilience With MongoDB Atlas — MongoDB Blog](https://www.mongodb.com/company/blog/data-resilience-with-mongodb-atlas)
16. [Atlas Service Limits — Atlas Docs](https://www.mongodb.com/docs/atlas/reference/atlas-limits/)
17. [Back Up and Restore a Self-Managed Deployment with MongoDB Tools — Database Manual](https://www.mongodb.com/docs/manual/tutorial/backup-and-restore-tools/)
18. [Choosing the Right Atlas Backup Policy — MongoDB Learn](https://learn.mongodb.com/learn/article/choosing-the-right-atlas-backup-policy)
19. [Atlas Backup CLI Reference — atlas backups](https://www.mongodb.com/docs/atlas/cli/current/command/atlas-backups-snapshots/)
20. [Essential MongoDB Backup Best Practices — Percona](https://www.percona.com/blog/mongodb-backup-best-practices/)

## See Also: mongosync (when the goal is a moving target, not a backup)

Backups answer "restore data **to a point in time**". When the operator actually needs to **move data between two live clusters** — Atlas Live Migration, cluster-to-cluster sync, or any cutover with sub-minute downtime — the right tool is `mongosync`, not mongodump/mongorestore or `$out`. Load the `mongosync` skill when the task involves continuous CDC between two MongoDB clusters, `includeNamespaces`/`excludeNamespaces` filtering, the IDLE/RUNNING/PAUSED/COMMITTING/COMMITTED state machine, reverse sync for rollback, or oplog window sizing to avoid `ChangeStreamHistoryLost`. This skill (`mongodb-backup-restore`) stays focused on snapshot, PIT recovery, queryable backup, and dump/restore tooling.

---

## 11. Atlas Backup Compliance Policy (BCP) — Deep Reference

### What BCP is

A Backup Compliance Policy (BCP) is an **irrevocable, org-level governance control** that enforces minimum backup retention floors, prevents snapshot deletion, and applies WORM (Write Once Read Many) semantics to all backup data under its scope. Unlike a per-project backup policy (which any Project Owner can modify), BCP is set at the **Organization level** and, once activated, cannot be modified or disabled by any Atlas user — including Org Owners — without explicit intervention from **MongoDB Atlas Support**. This is by design: an attacker or rogue admin who compromises Atlas credentials cannot deactivate backup protection before exfiltrating or destroying data.

BCP is Atlas's answer to regulated workload requirements (HIPAA, PCI DSS, SOC 2, GDPR) that demand tamper-evident, immutable retention — not just a policy that exists on paper but one that is enforced at the control-plane level.

---

### Enabling BCP

**Required role:** Organization Owner. Project-level roles are insufficient; the toggle lives in the org-level settings panel, not in a project.

**Location in Atlas UI:**
- Organization → Settings → Backup Compliance Policy
- Or navigate directly to: `cloud.mongodb.com/v2#/org/{orgId}/settings/backupCompliance`

**Configuration parameters:**

| Parameter | Description | Typical regulated value |
| --- | --- | --- |
| Minimum snapshot retention | Minimum days/weeks/months/years any snapshot must be kept — operators cannot set a shorter retention | 7 days / 4 weeks / 12 months depending on framework |
| PIT recovery window minimum | Minimum continuous backup window — cannot be reduced below this once set | 7 days for most regulated workloads |
| On-demand snapshot retention | Minimum retention for manually triggered on-demand snapshots | ≥ 1 day |
| Auto-enable backup on new clusters | When checked, every new cluster in the org automatically has backup enabled at creation time | Recommended: enabled |
| Require Encryption at Rest | If checked, clusters that do not have Encryption at Rest with Customer Key Management enabled are considered non-compliant | Required for HIPAA/PCI |

**Activation flow:**
1. Org Owner configures the BCP parameters.
2. Atlas sends a **confirmation email** to the Org Owner's registered email address.
3. The Org Owner must click the confirmation link within the TTL window.
4. BCP becomes active. From this point on, the settings are locked at the control-plane level.

This two-step email confirmation exists so that BCP cannot be silently enabled by a compromised session cookie — the actual mailbox must be accessible.

---

### What BCP locks

Once active, BCP prevents the following operations at every project under the org:

**Snapshot deletion:**
- Users cannot manually delete any snapshot whose age is less than the BCP minimum retention floor.
- The "Delete" button is grayed out / returns a 409 for in-compliance snapshots.
- Snapshots that already exceeded their retention window expire normally — BCP does not make every snapshot immortal, only enforces the floor.

**Backup policy modification:**
- No project can reduce its snapshot retention schedule below the BCP minimums.
- Attempts to `PATCH /backup/schedule` with shorter retention return a 403 referencing the compliance policy.
- Projects **can** increase retention above the BCP floor (more protection is allowed; less is not).

**Backup disable:**
- Backup cannot be turned off for any cluster while BCP is active on the org.
- The "Pause/Disable Backup" option is hidden in the UI and blocked in the API.
- Cluster **deletion** is also affected — see pitfall section below.

**PIT window reduction:**
- The `restoreWindowDays` cannot be set below the BCP minimum PIT window.
- Hourly snapshots required by BCP cannot be removed from the policy schedule.

**Encryption at Rest / EaR (if required by BCP):**
- Clusters without Encryption at Rest (EaR) with Customer Key Management configured fail a compliance check surfaced in the Atlas UI's Backup Compliance Status view.
- Atlas does not automatically enable EaR — the cluster is flagged; the operator must remediate.

---

### BCP and PITR (Point-in-Time Recovery)

BCP can require a **minimum PIT window**, which means:

- Every cluster under the org must have Continuous Cloud Backup enabled.
- The configured `restoreWindowDays` must be ≥ the BCP minimum (e.g., 7 days).
- Reducing `restoreWindowDays` below the BCP minimum via API returns an error.

**How to read PITR status in the Atlas UI:**
- Navigate to Cluster → Backup → Backup Policy.
- The "Continuous Cloud Backup" toggle shows "On" with the configured window in days.
- A BCP badge appears next to the retention controls that are locked by the policy.

**How to read PITR status via API:**

```bash
# Get current backup schedule (includes restoreWindowDays)
curl --user "$PUB_KEY:$PRIV_KEY" --digest \
  "https://cloud.mongodb.com/api/atlas/v2/groups/$PROJECT_ID/clusters/$CLUSTER/backup/schedule"
```

The response includes `"restoreWindowDays"` and a `"copySettings"` array. If BCP is active, a `GET /groups/{groupId}/backupCompliancePolicy` call returns the org-level minimums that gate all modifications.

---

### Atlas API for BCP

**Retrieve current compliance policy:**

```bash
GET /api/atlas/v2/groups/{groupId}/backupCompliancePolicy
```

Response shape:

```json
{
  "authorizedEmail": "security@example.com",
  "copyProtectionEnabled": true,
  "encryptionAtRestEnabled": true,
  "onDemandPolicyItem": {
    "frequencyType": "ondemand",
    "retentionUnit": "days",
    "retentionValue": 7
  },
  "pitEnabled": true,
  "projectId": "<projectId>",
  "restoreWindowDays": 7,
  "scheduledPolicyItems": [
    { "frequencyType": "hourly",  "retentionUnit": "hours",  "retentionValue": 12, "frequencyInterval": 6 },
    { "frequencyType": "daily",   "retentionUnit": "days",   "retentionValue": 7  },
    { "frequencyType": "weekly",  "retentionUnit": "weeks",  "retentionValue": 4  },
    { "frequencyType": "monthly", "retentionUnit": "months", "retentionValue": 12 }
  ],
  "state": "ACTIVE",
  "updatedDate": "2024-01-15T10:00:00Z",
  "updatedUser": "security@example.com"
}
```

**Update compliance policy (restricted — BCP blocks *loosening* of existing locks):**

```bash
PATCH /api/atlas/v2/groups/{groupId}/backupCompliancePolicy
```

> Note: PATCH can only **increase** retention values or **add** new constraints (making the policy stricter). Any attempt to reduce a retention parameter below the currently-active BCP minimum is rejected with a 409. To loosen any constraint, a MongoDB Support ticket is required. After initial activation, the `authorizedEmail` field identifies the designated security contact for Support-side modifications.

**Required permission for API calls:** `Project Backup Manager` or higher on the target project.

**Atlas CLI equivalent:**

```bash
# Enable BCP
atlas backups compliancePolicy enable \
  --authorizedUserEmail security@example.com \
  --authorizedUserFirstName Security \
  --authorizedUserLastName Lead \
  --projectId $PROJECT_ID

# Retrieve current policy
atlas backups compliancePolicy describe --projectId $PROJECT_ID
```

---

### Modifying BCP (requires MongoDB Atlas Support)

Once activated, BCP can only be relaxed through an Atlas Support ticket. No self-service path exists — this is a compliance guarantee, not a UX oversight.

**Process:**

1. Open a P2 or P3 support ticket via `support.mongodb.com` with subject line indicating "Backup Compliance Policy modification request."
2. In the ticket body include:
   - Organization ID (`orgId`)
   - Current BCP configuration (GET response above)
   - Desired new configuration with specific parameters to change
   - Business justification (auditors / legal may review this)
   - Verification that the requester is the current Org Owner or authorized security contact
3. MongoDB Support verifies the identity of the requestor against the `authorizedEmail` on the BCP record via out-of-band communication (phone call or secondary email confirmation).
4. Support modifies the compliance policy in the control plane on behalf of the org.

**SLA:** BCP modification requests are not treated as break/fix incidents. Typical processing time is **3–5 business days** under standard SLA; P1 escalations may be faster but require documented emergency justification.

**What cannot be changed retroactively:**
- Snapshots that were retained under the old BCP minimum **cannot** be deleted even after BCP is relaxed to a shorter retention. Those snapshots must age out naturally per their original policy item retention.
- If BCP required EaR and a cluster was flagged non-compliant, the compliance flag persists until EaR is actually enabled — removing the BCP requirement does not retroactively clear flags.

---

### BCP and compliance frameworks

| Framework | How BCP satisfies the requirement |
| --- | --- |
| **HIPAA** | BCP locks backup retention for ePHI systems to your configured minimum. HIPAA requires policies and procedures to be retained for 6 years; some covered entities apply the same window to backup data as an internal control. Configure yearly policy items to meet your organization's chosen retention floor. Combined with Atlas EaR for encryption of ePHI at rest, BCP is a key HIPAA Technical Safeguard control addressing the "availability" pillar of the HIPAA Security Rule. |
| **PCI DSS v4.0** | Requirement 9.4.5 / 12.3: cardholder data backups must be retained ≥ 1 year with the most recent 3 months immediately available. BCP with a 12-month minimum monthly retention and 90-day minimum daily retention satisfies these floors and prevents any operator from reducing them. |
| **SOC 2 Type II** | BCP provides control evidence for CC7.5 (unauthorized destruction of system components) and A1.2 (backup and recovery testing). Auditors can verify via API that the retention policy is locked — the policy itself is the evidence of a "preventive control," not just a detective one. |
| **GDPR** | GDPR's "right to erasure" creates tension with immutable backups. BCP does not automatically satisfy GDPR Article 17 — it makes selective deletion harder. Orgs relying on BCP must ensure that PII subject to erasure requests is either never placed in Atlas or is encrypted with per-subject keys that can be rotated/deleted (crypto-shredding via field-level encryption). |

**Atlas Backup Compliance Status view:**
- Organization → Backup Compliance → Compliance Status shows a per-project compliance posture dashboard.
- Green (compliant): every cluster meets the BCP minimums.
- Yellow (warning): a cluster was created before BCP was enabled and has not yet been brought into compliance.
- Red (non-compliant): a cluster violates a hard BCP requirement (e.g., EaR disabled when BCP requires it).

---

### Common BCP pitfalls

**Enabling BCP without testing the restore process first.**
BCP prevents you from cleaning up failed or partial test restores whose snapshots fall within the retention window. If your quarterly restore test creates a 2 TB cluster that you want to delete after testing, you cannot delete the cluster's snapshots before they age out. Always test restores in a **separate Atlas project** that you do not intend to place under BCP, then enable BCP on your production org after the restore process is validated.

**Setting the retention window too short, then needing Support to extend it.**
Many customers under-set the minimum (e.g., 7-day daily retention) thinking they can always extend later, only to discover a compliance audit requires 30-day minimum. "Extending" via Support is straightforward — but requires the same 3–5 business day SLA. Set retention to the regulatory requirement at activation, not the operational default.

**Not excluding dev/test clusters from BCP scope.**
BCP applies at the org level — every cluster in every project under the org is subject to it. Ephemeral development clusters accumulate snapshots they cannot delete, burning backup storage costs. Pattern: use a **separate Atlas org** for dev/test with no BCP; use the production org (with BCP) only for production and staging.

**BCP preventing rapid cluster deletion for cost savings.**
A cluster with BCP-protected snapshots **cannot be terminated immediately**. Terminating the cluster stops new snapshots but the cluster's backup data is retained for the full BCP retention window. The cluster appears as "Terminated" but backup storage continues to accrue costs until all protected snapshots expire. Factor BCP snapshot retention costs into total cluster ownership cost.

**Confusing "org-level BCP" with "project-level backup policy."**
Project-level backup policies set the frequency and retention for snapshots — these are editable by Project Owners unless constrained by BCP. BCP is the org-level floor that constrains every project's policy. Many operators enable a project-level policy and assume that equals BCP protection. It does not; a malicious or mistaken Project Owner can still reduce or disable a project-level policy. Only org-level BCP is tamper-resistant.

**Assuming BCP covers snapshot copies in DR regions.**
If you have cross-region snapshot copies enabled, BCP's `copyProtectionEnabled: true` flag extends WORM protection to the copies. If `copyProtectionEnabled` is `false` (the default for existing BCP configurations pre-2024), snapshot copies in DR regions **can still be deleted**. Verify `copyProtectionEnabled` is `true` in your BCP configuration if you rely on DR copies for compliance.

---

### When NOT to enable BCP

Do not enable BCP if any of the following are true — resolve the condition first or accept the permanent consequence:

| Condition | Why it blocks BCP | Resolution |
| --- | --- | --- |
| Restore process has never been tested | BCP prevents cleanup of failed restore artifacts; first failure becomes permanent storage cost | Test restores in a separate project first |
| Dev/test clusters live in the same org | Every ephemeral cluster accrues immutable snapshot storage | Move dev/test to a separate org before enabling |
| Cluster deletion speed is a cost-control lever | BCP-protected snapshots survive cluster termination; storage costs continue until retention expires | Accept the cost model or use a separate org |
| Retention minimums haven't been mapped to regulatory requirements | Under-setting requires a Support ticket to increase; over-setting wastes storage | Complete compliance mapping before activation |
| The `authorizedEmail` is an individual's address | If that person leaves, the security contact is unreachable for Support-side modifications | Use a team or security-ops mailbox |

### BCP decision checklist

Use this checklist before enabling BCP on a production org:

```
[ ] Restore process has been tested end-to-end at least once
[ ] Dev/test clusters are on a separate Atlas org (or BCP cost implications are accepted)
[ ] Minimum retention values match the most stringent applicable regulatory requirement
[ ] PIT window minimum matches RPO targets for all production workloads
[ ] Encryption at Rest requirement assessed — if required, all clusters have EaR configured
[ ] Authorized email address belongs to a shared security mailbox, not an individual's address
[ ] BCP modification SLA (3-5 business days) is documented in incident runbooks
[ ] Compliance posture view URL bookmarked for auditor walkthroughs
[ ] copyProtectionEnabled confirmed true if DR region copies are in scope
[ ] Cost impact of immutable snapshot storage estimated and budget-approved
```
