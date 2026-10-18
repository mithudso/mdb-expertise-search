---
name: set-up-alerts-and-monitoring
title: Set up alerts and monitoring
summary: Configure a starter set of Atlas alerts with notification channels and thresholds, and set up basic self-managed monitoring with serverStatus, mongostat and FTDC.
applies_to: [atlas, self-managed]
sources:
  - skills/atlas-diagnostics-expert/references/mongodb-monitoring-observability.md
  - skills/atlas-diagnostics-expert/references/mongodb-capacity-planning.md
  - skills/mongodb-operations-expert/references/mongodb-cost-optimization.md
  - skills/mongodb-operations-expert/references/mongodb-compliance.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-iac.md
  - skills/mongodb-expert/references/mongodb-wiredtiger.md
---
# Set up alerts and monitoring

## When to use
- A new Atlas project or cluster has only default alerts and you need a deliberate starter set.
- You had an incident that monitoring did not catch (full disk, connection exhaustion, replication lag).
- You run self-managed MongoDB and need a baseline of metrics, command-line checks and diagnostic capture.
- An audit finding says "no Atlas alerts configured for unusual activity".

## Prerequisites (checklist)
- [ ] Atlas: Project Owner, or a role that can create alert settings (the corpus lists Project Alerts Manager as the API role `GROUP_ALERTS_MANAGER`).
- [ ] A notification destination exists: a paging service integration key, a chat channel webhook, or a distribution list. Escalation policy is defined on the paging side.
- [ ] You know the cluster tier, expected connection count and disk size. Dedicated tiers (M10+) have 1-minute metric granularity; free and shared tiers are coarser (5 minutes).
- [ ] Self-managed: shell access to the hosts and a monitoring user with the `clusterMonitor` role.
- [ ] The names of the people or rotation who will respond. An alert with no owner is noise.

## Steps

### 1. Review what already exists
```bash
atlas alerts settings list --projectId <project-id>
```
Expect: the default alert settings for the project. Note which have no notification attached.

### 2. Add notification channels
```text
Atlas UI: Project > Settings > Integrations  (add PagerDuty, Slack, Opsgenie, webhook, Datadog as needed)
Atlas UI: Project > Alerts > Alert Settings > <alert> > Notifications
```
Available channels in the corpus: email, Slack, PagerDuty, webhook, Datadog, OpsGenie, VictorOps (Splunk On-Call), and SMS or phone on some plan tiers. Use a delay (for example notify if it persists 5 minutes) to suppress transient spikes.

Expect: a test notification or a visible integration entry. Route critical alerts to a pager, warnings to chat or email.

### 3. Create the starter alert set
Scope: project-level alerts cover all clusters in the project; cluster-level alerts cover one cluster. Create these in the UI under Project > Alerts > Add New Alert.

| Alert | Warn | Critical | Why |
|---|---|---|---|
| Disk utilization | 75% to 85% | 90% | Full disk stalls writes. Autoscale fires at 90% and expansion takes time, so alert earlier (85% for high-write clusters) to leave a 2 to 4 hour window |
| Connections | 80% of limit | 90% of limit | Pool churn and leaks end in refused connections |
| Replication lag | 15s (5s for strict secondary reads) | 60s (15s strict) | Stale reads, then secondaries falling off the oplog |
| Oplog window | below 48 hours | below 4 hours | Short window puts restores and resyncs at risk |
| CPU (process or system) | 75% on M10 to M30 | 85% sustained on larger tiers | Saturation precedes timeouts |
| Query targeting (scanned to returned) | high ratio | very high ratio | Indicates missing indexes |
| Backup | last snapshot older than expected | restore or snapshot failure | Protects recovery objectives |
| Billing | spend at 110% of current | | Catches unexpected autoscale-up |
| Security events | new database user, IP access list change, project role granted | authentication failure spike | Detects unusual access |

The corpus gives different numbers in different places (for example disk 75/90 versus 85). Pick one set, document it, and tune after two weeks of data. Verify in the current MongoDB docs: the exact metric names and limit values for your tier before setting absolute thresholds.

Create from the CLI (discover fields first):
```bash
atlas alerts settings fields type --projectId <project-id>
atlas alerts settings create --help
```
Verify in the current MongoDB docs: the flags of `atlas alerts settings create`; the corpus lists the command but not its flags. With Terraform the resource is `mongodbatlas_alert_configuration`, with `mongodbatlas_third_party_integration` for channels.

Expect: new entries in `atlas alerts settings list`.

### 4. Add Atlas Search alerts if you use dedicated Search Nodes
Alerts named in the corpus: Index Replication Lag, Mongot stopped replication (disk 90% or more), Mongot approaching replication stop threshold (disk 85% or more), Mongot paused initial sync, and Search Process ran out of memory (enabled automatically).

### 5. Tune the slow query threshold
```text
Atlas UI: Cluster > Configuration > Slow Query Threshold
```
Guidance: 20 to 50 ms for strict OLTP, 100 ms (the default) for mixed, 200 to 500 ms for analytics, raise to 1000 ms during bulk loads. Expect: Performance Advisor and Profiler show only queries above the threshold.

### 6. Self-managed: capture a metric baseline with serverStatus
```javascript
const ss = db.adminCommand({ serverStatus: 1 });
ss.connections                    // current, available, totalCreated
ss.opcounters
ss.wiredTiger.cache["bytes currently in the cache"]
ss.flowControl                    // isLagged true means the primary is throttling writes
```
Expect: numbers you can store as a baseline. Alert when `connections.current` passes 80% of `current + available`.

### 7. Self-managed: live checks with mongostat, mongotop, currentOp
```bash
mongostat --uri "mongodb://<host>:27017" --discover --rowcount 60
mongotop --uri "mongodb://<host>:27017" 5
```
```javascript
db.adminCommand({ currentOp: true, active: true, secs_running: { $gt: 2 } })
```
Expect: `mongostat` rows with `dirty`, `used`, `qrw`, `arw`, `conn`, `repl` columns. Watch for rising queues (`qrw/arw`), `dirty` and `used` cache above about 80%, and connection spikes.

### 8. Self-managed: replication health
```javascript
rs.printSecondaryReplicationInfo()
```
Expect: a lag in seconds per secondary. Alert when lag exceeds your threshold from step 3.

### 9. Self-managed: keep FTDC and know where it is
FTDC is on by default since 3.2 and writes to `<dbPath>/diagnostic.data/`. It records `serverStatus` every second plus a lighter subset every 200 ms. Files rotate at about 10 MB. Do not delete this directory.
```bash
ls -l <dbPath>/diagnostic.data/
tar czf ftdc-$(date +%F).tgz -C <dbPath> diagnostic.data
```
Expect: `metrics.<timestamp>-NNNNN` files and `metrics.interim`. Copying while `mongod` runs is safe; `metrics.interim` is a partial buffer. Atlas keeps FTDC for you and exposes it to MongoDB Support.

### 10. Self-managed: long-term trending and alerting
Choose one: Ops Manager or Cloud Manager (monitoring agent polls `serverStatus`, `replSetGetStatus`, `dbStats`, `collStats` and sends alerts), or a Prometheus exporter such as `mongodb_exporter` (default port 9216) with Grafana. Apply the same alert set from step 3 in whichever system you pick.

## Verify
1. Trigger a safe test: temporarily set one warning alert (for example connections) to a very low threshold, or use the product's test-notification button.
```bash
atlas alerts list --projectId <project-id>
```
Expect: the alert appears as open and the notification arrives at the right channel with a readable message. Restore the real threshold afterward.
2. Confirm each alert has an owner and a notification channel in `atlas alerts settings list`.
3. Confirm the Activity Feed shows alert setting changes.
4. Self-managed: confirm `diagnostic.data/` is growing and monitoring dashboards show current data.

## Rollback / abort
- Disable a noisy alert without deleting it: `atlas alerts settings disable <alert-config-id> --projectId <project-id>` (re-enable with `atlas alerts settings enable`). Verify in the current MongoDB docs: the argument form.
- Delete a mistaken alert setting: `atlas alerts settings delete <alert-config-id> --projectId <project-id>`.
- Acknowledge an open alert while you work: `atlas alerts acknowledge <alert-id> --projectId <project-id>`.
- Self-managed: monitoring is read-only; remove the exporter or agent to stop collection. Do not delete `diagnostic.data/` to "reset" anything.

## Pitfalls
- Defaults only: no one is notified about disk or connections until the incident.
- Disk alert at the same level as the autoscale trigger (90%): writes can stall before expansion completes.
- No delay on spiky metrics (CPU, connections) causes alert fatigue; a delay of about 5 minutes filters transient spikes.
- Mixing up per-node and per-cluster limits: connection limits are per node.
- Absolute thresholds copied from another tier. Recompute for your tier, or use percentages.
- Alert on the oplog window too late: keep it above 4 hours.
- Using profiling level 2 in production to "see everything" adds overhead. Use level 1 with a tuned `slowms`.
- Averaging hides short stalls: 1-minute dashboards can miss a 5-second checkpoint stall that FTDC shows.
- Using `optime.ts` instead of `optimeDate` when computing lag in scripts.
- Disabling flow control to stop throttling risks oplog overflow; fix the lagging secondary instead.
- Alerts routed only to email and read the next morning.
- Security alerts (new user, access list change) missing; compliance reviews flag this.
- Terraform-managed alerts edited by hand in the UI drift from code; pick one owner.

## Sources
- `skills/atlas-diagnostics-expert/references/mongodb-monitoring-observability.md:118-215` (Atlas metrics, alert scopes, categories, channels, tuning)
- `skills/atlas-diagnostics-expert/references/mongodb-monitoring-observability.md:146-172` (Ops Manager monitoring agent)
- `skills/atlas-diagnostics-expert/references/mongodb-monitoring-observability.md:393-460` (Prometheus exporter, FTDC contents, location, retrieval)
- `skills/atlas-diagnostics-expert/references/mongodb-monitoring-observability.md:464-523` (mongostat, mongotop, currentOp)
- `skills/atlas-diagnostics-expert/references/mongodb-monitoring-observability.md:525-670` (profiler, slow threshold, replication lag, connection counters)
- `skills/atlas-diagnostics-expert/references/mongodb-capacity-planning.md:495-516` (recommended alert levels, inconsistent with other files)
- `skills/mongodb-operations-expert/references/mongodb-cost-optimization.md:160-185` (disk autoscale trigger and 85% alert guidance, billing alert)
- `skills/mongodb-operations-expert/references/mongodb-compliance.md:855-868` (security event alerts)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-iac.md:151` (Terraform alert resources)
- `skills/mongodb-expert/references/mongodb-wiredtiger.md:564-576` (FTDC and short stalls)
- `llms/mongodb.com.llms/llms-full.txt:7962-7990` (Atlas CLI `atlas alerts` command list)
