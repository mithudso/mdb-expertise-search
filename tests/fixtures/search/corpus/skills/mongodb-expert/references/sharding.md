# Sharding

## Choosing a Shard Key

A good shard key has high cardinality, low frequency and non-monotonic values. A monotonically
increasing shard key such as a timestamp sends every insert to one chunk: a hot shard.

## Chunk Migration and the Balancer

The balancer moves chunks between shards in the balancing window. Jumbo chunks exceed the chunk size
and cannot be split because every document shares one shard key value.

## Targeted and Scatter-Gather Queries

A query that includes the shard key is routed to one shard (SINGLE_SHARD). Without it, mongos sends
the query to every shard and merges the results (SHARD_MERGE), which is a scatter-gather query.
