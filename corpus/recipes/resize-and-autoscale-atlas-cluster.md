---
name: resize-and-autoscale-atlas-cluster
title: Resize an Atlas cluster and configure autoscaling
summary: Change an Atlas cluster tier or disk size, enable compute and storage autoscaling with explicit bounds, and run pre- and post-change checks around the rolling resize.
applies_to: [atlas]
sources:
  - skills/atlas-diagnostics-expert/references/mongodb-capacity-planning.md
  - skills/atlas-diagnostics-expert/references/mongodb-monitoring-observability.md
  - skills/mongodb-operations-expert/references/mongodb-cost-optimization.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-terraform.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-flex-serverless.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-tiers-upgrades.md
---
# Resize an Atlas cluster and configure autoscaling

## When to use
- Working set no longer fits in cache, CPU is saturated, or disk is filling, and you need a larger tier or more storage.
- A cluster is over-provisioned and you want to scale down.
- You want Atlas to scale compute or storage on its own within limits you control.
- You are moving a Flex cluster to a dedicated tier.

## Prerequisites (checklist)
- [ ] You hold Project Cluster Manager (or higher) on the project. `atlas clusters update` needs M10+ and that role.
- [ ] You know the current tier, disk size and the numbers that justify the change: cache used %, CPU %, disk used %, connections, replication lag.
- [ ] Applications use retryable writes and reads (`retryWrites=true`, `retryReads=true`) and `serverSelectionTimeoutMS=30000`, because elections take 10 to 30 seconds.
- [ ] A recent healthy backup exists and the cluster state is IDLE with no replication lag.
- [ ] A change window agreed with stakeholders; avoid peak traffic.
- [ ] A cost ceiling: the maximum tier and disk size you are willing to pay for.
- [ ] Terraform users: you know whether the cluster is Terraform-managed (see the drift pitfall).
- [ ] Alerts for disk, CPU, connections and replication lag exist (see `set-up-alerts-and-monitoring`).

## Steps

### 1. Capture a baseline
```bash
atlas clusters describe <cluster-name> --projectId <project-id>
```
```javascript
const ss = db.adminCommand({ serverStatus: 1 });
ss.connections
const c = ss.wiredTiger.cache;
print((c["bytes currently in the cache"] / c["maximum bytes configured"] * 100).toFixed(1) + "% cache used")
rs.printSecondaryReplicationInfo()
```
Expect: tier, disk size, state IDLE, cache percentage, connection counts and lag values. Save them for the post-change comparison.

### 2. Decide the target
Use the corpus guidance:
- Cache misses or RAM pressure: scale vertically (bigger tier).
- Single-node write throughput or storage past about 4 TB or a working set larger than the biggest tier's RAM: scale horizontally (sharding), not a resize.
- Size for peak, not average (about 2 times expected peak). Autoscaling reacts to sustained load, typically over 15 to 30 minutes, so a 10 minute spike can saturate before it reacts.
- Reference tiers in the corpus: M10 2 GB RAM, M20 4 GB, M30 8 GB, M40 16 GB, M50 32 GB, M60 64 GB, M80 128 GB. M30 is the smallest tier recommended for production. Verify in the current MongoDB docs: current tier specs and storage maximums.

Expect: one target tier and one target disk size written down.

### 3. Resize the tier
```bash
atlas clusters update <cluster-name> --projectId <project-id> --tier M40 --watch
```
The CLI reference shows `--tier` for `atlas clusters update`, while the capacity planning reference says `--instanceSize` and states `--tier` is not valid. Verify in the current MongoDB docs: run `atlas clusters update --help` and use the flag that it lists. UI alternative:
```text
Atlas UI: Cluster > ... > Edit Configuration > Cluster Tier
```
Expect: cluster state moves to UPDATING, then IDLE with `--watch`. Atlas resizes in a rolling fashion: secondaries one at a time, the primary last with a replica-set election. Writes pause for the election (typically 10 to 30 seconds), a 3-node replica set takes roughly 5 to 15 minutes, and a sharded cluster takes longer in proportion to shard count.

### 4. Increase disk size
```bash
atlas clusters update <cluster-name> --projectId <project-id> --diskSizeGB 200 --watch
```
Expect: state returns to IDLE and `describe` shows the new `diskSizeGB`. Plan growth with headroom: add about 20% of data size for index overhead in forecasts.

### 5. Enable autoscaling with bounds (UI)
```text
Atlas UI: Cluster > ... > Edit Configuration > Auto-scale
  Cluster Tier Auto-scaling: enable
    Scale up   (on)
    Scale down (on, optional)
    Minimum tier: <tier>
    Maximum tier: <tier>
  Storage Auto-scaling: enable
```
Corpus defaults and guidance for compute autoscaling (M10+):
- Moves one tier at a time, never skipping tiers.
- Scale up when CPU is above 75% for about an hour or cache dirty bytes approach capacity (recommended override: CPU above 70% for 30 minutes).
- Scale down when CPU is below 50% over the trailing 24 hours (recommended override: below 40% for 24 hours). The 24 hour delay prevents oscillation.
- Set an explicit maximum tier. With no cap there is a runaway cost risk. For production, set the minimum at M30 or higher.
- Storage autoscaling triggers at 90% disk used and expands by roughly 25%.

Expect: the Auto-scale section shows your min and max. Verify in the current MongoDB docs: which thresholds are configurable in the UI versus fixed by Atlas.

### 6. Or enable autoscaling with Terraform
```hcl
resource "mongodbatlas_advanced_cluster" "main" {
  project_id           = var.project_id
  name                 = "<cluster-name>"
  cluster_type         = "REPLICASET"
  use_effective_fields = true

  replication_specs = [{
    region_configs = [{
      provider_name = "AWS"
      region_name   = "US_EAST_1"
      priority      = 7
      electable_specs = { instance_size = "M30", node_count = 3 }
      auto_scaling = {
        compute_enabled            = true
        compute_scale_down_enabled = true
        compute_min_instance_size  = "M30"
        compute_max_instance_size  = "M50"
        disk_gb_enabled            = true
      }
    }]
  }]
}
```
Expect: `terraform plan` shows no change after Atlas autoscales, because `use_effective_fields = true` lets Atlas-managed `instance_size` and `disk_size_gb` reflect in state. Without it, add a `lifecycle { ignore_changes = [...] }` for those two attributes, or Terraform will revert the autoscaled values.

### 7. Add a disk alert ahead of the autoscale trigger
```text
Atlas UI: Project > Alerts > Add New Alert > Disk utilization above 85% for 5 minutes > notify pager + chat
```
Expect: the alert fires about 2 to 4 hours before the 90% trigger on a high-write cluster, giving time to intervene. For sharded clusters, autoscaling applies per shard; coordinate with capacity planning.

### 8. Flex to dedicated (one-way)
```text
Atlas UI: Cluster > ... > Modify Cluster > select M10 or larger
```
Expect: downtime during the upgrade. Download existing Flex snapshots first (they do not transfer), then restart application servers to pick up the new connection string. You cannot go back to Flex. Move when you consistently approach 500 ops/sec, exceed 5 GB, or need private endpoints, PITR, BYOK or Performance Advisor.

## Verify
1. State and size:
```bash
atlas clusters describe <cluster-name> --projectId <project-id>
```
Expect: IDLE, the new tier and disk size, and the autoscaling bounds if you set them.
2. Health: `rs.status()` shows one PRIMARY and healthy secondaries; `rs.printSecondaryReplicationInfo()` shows lag returning to normal.
3. Compare cache %, CPU %, connections with the baseline from step 1. Expect: lower cache pressure and CPU after an upsize.
4. Application: error rate returns to normal; "not primary" or timeout errors during the election window are expected, persistent ones are not.
5. Warm-up: expect slower first queries for about 30 to 60 seconds after the election and cold WiredTiger cache on restarted nodes.
6. Activity Feed shows each autoscale event; confirm it matches the bounds you set. Set a billing alert at 110% of current spend.

## Rollback / abort
- Tier: resize back to the previous tier with the same `atlas clusters update` command. This is another rolling change with another election, so do it in a window.
- Disk: do not assume you can shrink. Verify in the current MongoDB docs: whether disk size can be reduced on your cluster before relying on it. Reclaim space with `compact` during maintenance (secondaries first, then primary) after large deletes or TTL expirations; the corpus says this can recover 30 to 60% and avoid an autoscale event.
- Autoscaling: turn off compute or storage autoscaling in Edit Configuration, or set `compute_enabled = false` / `disk_gb_enabled = false` in Terraform and apply.
- Flex to dedicated cannot be reversed.
- If an update appears stuck, check the Activity Feed and contact support rather than issuing more changes.

## Pitfalls
- Resizing during peak hours or with drivers lacking retryable writes; `serverSelectionTimeoutMS` of 3000 gives up before a 12 second election finishes.
- Relying on autoscaling for a spike that lasts 10 minutes; it reacts to sustained load.
- No maximum tier set, so a bug or load test scales cost without limit.
- Autoscaling and Terraform fighting: without `use_effective_fields` or `ignore_changes`, the next apply reverts the autoscaled size.
- Disk alert placed at the autoscale trigger (90%). Writes can stall before the expansion completes.
- Scaling down too eagerly: the 24 hour scale-down window exists to prevent oscillation.
- Strict latency SLAs with autoscaling on: each scale event is a rolling restart with an election. Opt out and scale manually in a window.
- Sharded clusters: autoscaling is per shard and tier limits differ; scale-up cannot fix a poor shard key.
- Assuming more RAM fixes everything. If queries do a collection scan, add the index instead of paying for a tier.
- Flex: it throttles at 500 ops/sec rather than autoscaling; it is not elastic.
- Free and shared tiers (M0) have no autoscaling; M2 and M5 are deprecated and created as Flex.
- Fleet heterogeneity: same-tier clusters may run on different hardware generations, so compare benchmarks with care.
- A Flex snapshot is not carried to the dedicated cluster; download it first.

## Sources
- `skills/atlas-diagnostics-expert/references/mongodb-capacity-planning.md:321-347` (tier table, vertical versus horizontal, resize command and `--instanceSize` note)
- `skills/atlas-diagnostics-expert/references/mongodb-capacity-planning.md:205-221` (storage growth, index overhead)
- `skills/atlas-diagnostics-expert/references/mongodb-capacity-planning.md:596-601` (size for 2x peak; autoscaling reaction window)
- `skills/mongodb-operations-expert/references/mongodb-cost-optimization.md:131-185` (compute autoscaling rules, overrides, opt-out cases, storage autoscale trigger, 85% alert, compaction)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md:376-413` (`atlas clusters update` examples and restrictions)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-terraform.md:238-270,1367-1385` (autoscaling block, `use_effective_fields`, drift)
- `skills/atlas-diagnostics-expert/references/mongodb-monitoring-observability.md:753-840` (rolling maintenance, election duration, retryable writes, connection options)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-flex-serverless.md:226-258` (Flex to dedicated triggers and caveats)
- `skills/mongodb-atlas-expert/references/mongodb-atlas-tiers-upgrades.md:39-60` (rolling election mechanics, cold cache after restart, Gen2 heterogeneity)
