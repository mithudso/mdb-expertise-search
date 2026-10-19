---
name: shard-a-collection
title: Shard a collection
summary: Pick a shard key, create its index, shard the collection and verify chunk distribution.
applies_to: [atlas, self-managed]
sources:
  - skills/mongodb-expert/references/sharding.md
---
# Shard a collection

## Steps

1. Choose a shard key with high cardinality and non-monotonic values.
2. Create an index that starts with the shard key.
3. Run sh.shardCollection("db.coll", { key: 1 }) and watch the balancer distribute chunks.

## Verify

Run db.coll.getShardDistribution() and confirm every shard holds data.
