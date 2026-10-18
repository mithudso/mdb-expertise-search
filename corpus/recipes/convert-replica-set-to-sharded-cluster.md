---
name: convert-replica-set-to-sharded-cluster
title: Convert a replica set to a sharded cluster
summary: Plan and run the move from a replica set to a sharded cluster on Atlas or self-managed, with a build-new-and-migrate fallback, and know which steps the corpus covers only as pointers.
applies_to: [atlas, self-managed]
sources:
  - skills/mongodb-expert/references/mongodb-sharding.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-global-clusters.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-identity-policy-frontier-20261001.md
  - skills/mongodb-operations-expert/references/mongodb-mongosync.md
  - skills/mongodb-operations-expert/references/mongodb-migration-patterns.md
  - skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md
  - skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md
  - llms/mongodb.com.llms/llms-full.txt
---
# Convert a replica set to a sharded cluster

Corpus coverage note: the corpus describes the sharded architecture, the Atlas CLI for creating and updating clusters, and the mongosync migration route in detail. For the in-place conversion procedures it holds only tutorial titles and one-line descriptions. Steps that depend on the full tutorials say "Verify in the current MongoDB docs:".

## When to use
- One replica set can no longer carry the write throughput, the working set no longer fits in RAM, or the data volume needs several nodes.
- Vertical scaling, indexing and schema fixes are exhausted (the corpus treats "sharding too early" as an anti-pattern).
- You have a shard key candidate for at least the largest collection. Sharding the cluster does not shard any collection by itself; the recipe `shard-a-collection` does that.
- You can accept a planned maintenance window (self-managed path) or a cluster reconfiguration (Atlas path).

## Prerequisites (checklist)
- [ ] The workload review is done: top queries, write rate, largest collections, shard key candidates.
- [ ] A recent backup or snapshot exists, and you have tested a restore.
- [ ] Self-managed: hosts for a 3-member config server replica set (dedicated) and for 2+ `mongos` routers. The corpus alternative is an embedded config shard (7.0+), where the config servers also hold data.
- [ ] Self-managed: keyfile or x.509 internal authentication is planned for all members (the Database Manual index lists keyfile deployment tutorials for sharded clusters).
- [ ] Applications can switch their connection string to `mongos` (Atlas: the new cluster connection string). Applications must never connect to individual shards for normal operations.
- [ ] Scripts that talk directly to a shard are inventoried. From 8.0, only an allowlist of commands works against a shard directly.
- [ ] Atlas: a dedicated tier (M30 or higher is the corpus minimum for Global Clusters; confirm the minimum for plain sharded clusters) and a user with permission to change cluster configuration (the CLI reference says cluster updates need M10+ and the Project Cluster Manager role).
- [ ] Atlas: no Atlas Resource Policy blocks the change. The corpus notes that a policy for conversion needs the condition `!context.cluster.isConvertingToSharded`. Verify in the current MongoDB docs: the exact resource-policy expression and attribute name.
- [ ] You decided between in-place conversion and build-new-and-migrate (step 1).

## Steps

### 1. Choose the path
```text
In-place, Atlas        -> change the cluster to a sharded type (UI or API/CLI file update); the platform runs the change.
In-place, self-managed -> add config servers and mongos, restart the replica set as a shard, then register it with sh.addShard.
Build new + migrate    -> create a new sharded cluster, sync with mongosync (or Atlas Live Migration), cut over.
```
Expect: one path chosen. Choose build-new-and-migrate if you also want to change the shard key, change the tier or the cloud provider, or keep the old cluster as a rollback target.

### 2A. Atlas in-place: inspect the cluster
```bash
atlas clusters describe <cluster-name> --projectId <project-id> --output json
```
Expect: JSON for the current configuration, with the cluster type `REPLICASET`. Save it.

### 2B. Atlas in-place: apply the sharded configuration
The CLI reference documents `atlas clusters update ... --file`, where the JSON file holds the full cluster spec, and `atlas clusters create --type SHARDED --shards <n>`.
```bash
# edit the saved JSON so the cluster type is sharded and the shard count is set, then:
atlas clusters update <cluster-name> --projectId <project-id> \
  --file updated-cluster.json --output json
atlas clusters watch <cluster-name> --projectId <project-id>
```
Expect: the cluster goes into a configuration-update state and `atlas clusters watch` prints "Cluster available." when it returns to IDLE.

Verify in the current MongoDB docs: how Atlas converts a replica set to a sharded cluster in place (UI action, supported tiers, the JSON fields to change, expected downtime and any one-way restrictions). The corpus does not hold those steps. The `--type` flag is documented in the corpus only for `atlas clusters create`.

### 2C. Atlas alternative: new sharded cluster plus migration
```bash
atlas clusters create <new-cluster-name> \
  --projectId <project-id> \
  --provider AWS --region US_EAST_1 \
  --members 3 --tier M30 \
  --shards 2 --type SHARDED \
  --watch
```
Expect: `atlas clusters create` returns once the new cluster is IDLE (with `--watch`). Replace provider, region and tier with your values. Then move the data with Atlas Live Migration or mongosync (step 4C). The Atlas docs index lists "Example: Live Migration of Replica Sets to Sharded Clusters", which covers specifying sharding configuration and creating the needed indexes.

### 3. Self-managed in-place: prepare the config server replica set
Start three new `mongod` processes with the config server role, then initiate them.
```yaml
# mongod.conf on each config server host
sharding:
  clusterRole: configsvr
replication:
  replSetName: cfgRS
```
```javascript
// mongosh on one config server host
rs.initiate({
  _id: "cfgRS",
  configsvr: true,
  members: [
    { _id: 0, host: "cfg1.example.net:27019" },
    { _id: 1, host: "cfg2.example.net:27019" },
    { _id: 2, host: "cfg3.example.net:27019" }
  ]
})
```
Expect: `ok: 1`, and `rs.status()` shows one primary and two secondaries.

Verify in the current MongoDB docs: the exact config file options and default ports in the "Convert a Self-Managed Replica Set to a Sharded Cluster" tutorial (listed in the Database Manual index). For an embedded config shard, use the tutorial "Convert Replica Set to an Embedded Config Shard" instead (7.0+; see the corpus note on `transitionToDedicatedConfigServer` and `transitionFromDedicatedConfigServer`).

### 4A. Self-managed in-place: restart the existing replica set as a shard
Rolling restart, one secondary at a time, then step down the primary and restart it last. Add the shard role to each member.
```yaml
# mongod.conf on each member of the existing replica set
sharding:
  clusterRole: shardsvr
```
```javascript
// before restarting the primary
rs.stepDown()
```
Expect: each restarted member rejoins and `rs.status()` shows all members healthy with a primary elected.

Verify in the current MongoDB docs: the safe order and the application-impact notes in the conversion tutorial. This restart-ordering follows the corpus rolling-restart pattern (upgrade-paths reference): secondaries first, primary last.

### 4B. Self-managed in-place: start `mongos` and add the shard
```bash
mongos --configdb cfgRS/cfg1.example.net:27019,cfg2.example.net:27019,cfg3.example.net:27019 \
       --bind_ip <bind-address> --port 27017
```
```javascript
// mongosh connected to mongos, as an admin user
db.hello()                                   // "msg": "isdbgrid"
sh.addShard("rs0/db1.example.net:27018,db2.example.net:27018,db3.example.net:27018")
sh.status()
```
Expect: `sh.addShard()` returns `shardAdded: "rs0"` and `sh.status()` lists the shard. Add a second shard with another `sh.addShard()` when you want more than one.

Verify in the current MongoDB docs: how existing application databases and users are handled after the first shard is added, and what must change in client connection strings.

### 4C. Build-new-and-migrate: sync with mongosync
Use this path for either platform. The corpus shows the shard key remapping setting in mongosync, so the new cluster can shard chosen collections during the sync.
```json
{
  "source": "cluster0",
  "destination": "cluster1",
  "sharding": {
    "createSupportingIndexes": true,
    "shardingEntries": [
      {
        "database": "mydb",
        "collection": "orders",
        "shardCollection": { "key": [ { "customerId": 1 }, { "region": 1 } ] }
      }
    ]
  }
}
```
Expect: collections listed in `shardingEntries` are sharded on the destination with the given key; collections not listed land unsharded on the primary shard. Cut over when the sync reports it can commit, then repoint applications.

Verify in the current MongoDB docs: the mongosync start and commit API calls and the version requirements. The corpus also says the source replica set must meet mongosync version requirements (source MongoDB 6.0.8+ appears in the migration-patterns reference).

### 5. Shard the collections and tune
```javascript
sh.enableSharding("mydb")
sh.shardCollection("mydb.orders", { customerId: 1, createdAt: 1 })
sh.getBalancerState()
```
Expect: `ok: 1`, balancer state `true`. Follow the recipe `shard-a-collection` for key analysis, the supporting index and verification. An unsharded collection stays on the database's primary shard until you shard it.

### 6. Switch the applications
Change connection strings to the `mongos` hosts (self-managed) or the new cluster string (Atlas). Run with 2+ `mongos` routers behind a load balancer or a driver seed list.
Expect: the application connects, `db.hello()` through the same string returns `"msg": "isdbgrid"`, and error rates stay flat.

## Verify
```javascript
sh.status()                                 // shards, balancer, databases, collections
db.getSiblingDB("config").shards.find()     // all shards registered
sh.getBalancerState()
db.orders.getShardDistribution()            // after the collection is sharded
```
Expect:
- Every shard is listed and healthy; config servers form a healthy 3-member set (or the config shard is in place).
- Document counts match the source (migration path: compare per-collection counts and `dbHash`; the corpus notes `dbHash` works on sharded clusters when run per shard primary).
- Application queries that include the shard key are targeted; `explain("executionStats")` shows no `SHARD_MERGE` on the hot paths.
- Atlas: `atlas clusters describe <cluster-name> --projectId <project-id> --output json` shows the sharded type and the expected shard count.

## Rollback / abort
- Atlas in-place: the corpus does not describe a way back to a replica set. Take a snapshot first; if you must go back, restore to a new replica set cluster. The corpus notes that restoring a snapshot onto a cluster with added or removed shards is not supported for Global Clusters.
- Atlas Global Cluster note: a Global Cluster cannot be converted to a standard sharded cluster after deployment, so do not choose that type as a stepping stone.
- Self-managed in-place: the Database Manual index lists "Convert Self-Managed Sharded Cluster to Replica Set". Verify in the current MongoDB docs: its prerequisites before you rely on it, and note that it is a separate procedure, not an undo.
- Build-new-and-migrate: the old replica set is untouched. Roll back by pointing the applications at it again before you retire it. Keep it until the verification above passes.
- Abort before step 6 changes nothing for the applications; stop at any step and leave the original replica set serving traffic.

## Pitfalls
- Assuming the conversion shards your data. Collections stay unsharded until you run `sh.shardCollection()`.
- Connecting applications directly to a shard. Use `mongos` only; from 8.0 most commands fail against a shard directly.
- Running a single `mongos`: it is a single point of failure. Run 2+.
- Undersized or shared config servers: the corpus recommends a dedicated 3-member replica set.
- Picking a shard key in a hurry. The key is hard to change (refine or reshard are both heavy). Use the key analysis from the recipe `shard-a-collection`.
- Restarting the primary first during the rolling restart. Do secondaries first, primary last.
- Leaving the balancer stopped after maintenance (the upgrade runbook in the corpus stops it before changes and starts it after).
- Atlas policy blocks: a policy that sets a minimum shard count counts a replica set as 1 shard and can mark replica sets non-compliant; conversion needs `!context.cluster.isConvertingToSharded` in the policy (Verify in the current MongoDB docs: the exact expression).
- Choosing a Global Cluster just to get sharding: it needs M30+, cannot be converted to a standard sharded cluster, and does not support Atlas Search, Vector Search, or Online Archive.
- Migration path: the destination sharded cluster must have the same number of shards as the source or more; with a replica set source, make sure `createSupportingIndexes` or a pre-built index exists for each shard key.
- Direct-to-shard backup or health scripts that break on 8.0.

## Sources
- Components, config servers, `mongos`, `db.hello()` check: `skills/mongodb-expert/references/mongodb-sharding.md:126`, `:146`
- Production readiness checklist (3-member config servers, 2+ `mongos`): `skills/mongodb-expert/references/mongodb-sharding.md:767`
- Balancer, `sh.status`, config database queries: `skills/mongodb-expert/references/mongodb-sharding.md:339`, `:656`
- Atlas CLI create with `--type SHARDED`, `--shards`, update from a JSON file, restrictions: `skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md:307`, `:382`
- `atlas clusters describe` and `watch`: `skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md:356`, `:374`
- Resource policy gotcha for conversion: `skills/mongodb-atlas-expert/references/mongodb-atlas-identity-policy-frontier-20261001.md:92`
- Global Cluster limits and irreversibility: `skills/mongodb-atlas-expert/references/mongodb-atlas-global-clusters.md:118`, `:420`, `:640`
- mongosync replica set to sharded, `sharding` entries and `createSupportingIndexes`: `skills/mongodb-operations-expert/references/mongodb-mongosync.md:17`, `:495`
- Sharded migration planning, destination shard count, `dbHash` per shard, source version: `skills/mongodb-operations-expert/references/mongodb-migration-patterns.md:306`, `:522`, `:624`
- Rolling upgrade order (config servers, shards, `mongos`), balancer stop and start, config shard caveat: `skills/mongodb-operations-expert/references/mongodb-upgrade-paths.md:225`, `:257`
- Config shard transition commands, direct-to-shard restriction (8.0): `skills/mongodb-operations-expert/references/mongodb-7.0-vs-8.0-differences.md:228`, `:235`
- Tutorial index entries (self-managed conversion, embedded config shard, sharded to replica set, Atlas live migration example, Ops Manager and Cloud Manager conversion): `llms/mongodb.com.llms/llms-full.txt:5520`, `:5521`, `:5523`, `:6032`, `:7249`, `:7803`
