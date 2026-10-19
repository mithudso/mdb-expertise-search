# MongoDB Indexes

## Compound Indexes and the ESR Rule

A compound index orders keys by Equality, then Sort, then Range. When the sort keys follow the
equality keys, MongoDB returns documents in index order and avoids a blocking in-memory sort.
Indexing the range field before the sort field forces a SORT stage.

## Multikey Indexes

An index on an array field is multikey: one index key per array element. Bounds on multikey
fields can only be intersected when the predicates sit inside one $elemMatch.

## Partial and Sparse Indexes

A partial index stores only documents that match its partialFilterExpression. The planner uses it
only when the query predicate implies that expression. Sparse indexes skip documents that lack the field.

## Hidden Indexes

Hide an index with hideIndex() before dropping it. A hidden index is still maintained on writes
but the planner ignores it, so unhiding it is instant.
