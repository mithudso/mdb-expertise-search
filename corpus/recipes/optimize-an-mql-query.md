---
name: optimize-an-mql-query
title: Optimize one MQL query or pipeline and verify the fix
summary: Run the static MQL optimizer on a find(), aggregation or write filter, apply its result-preserving rewrites, build the ESR index it recommends on non-prod, and confirm the gain with explain("executionStats").
applies_to: [atlas, self-managed]
sources:
  - skills/mongodb-expert/references/deep-mongodb-mql-query-optimizer.md
  - skills/mongodb-expert/references/mongodb-query-shape-optimization.md
  - skills/mongodb-expert/references/mongodb-compound-index-design.md
  - skills/mongodb-expert/references/mongodb-explain-plans-and-query-planner.md
  - skills/mongodb-expert/references/mongodb-advanced-explain-and-planner-changes.md
  - llms/mongodb-query-shape-optimization.llms/llms-facts.txt
---
# Optimize one MQL query or pipeline and verify the fix

## When to use
- You have the text of a slow query: from application code, a slow-query log line, the profiler, or Performance Advisor.
- A code review needs a quick check of a new query or aggregation before it ships.
- You want an index recommendation that follows the Equality, Sort, Range (ESR) guideline for one exact query.

## Prerequisites (checklist)
- [ ] `mdbx` is installed (`pip install -e .`), so `mdbx optimize` runs.
- [ ] The query is saved in a `.mql` / `.js` file in mongosh syntax, or you can pipe it on stdin.
- [ ] For verification: mongosh access to a non-production cluster with representative data, and the existing index list (`db.coll.getIndexes()`).

## Steps

1. **Run the optimizer in report mode.**
   ```bash
   mdbx optimize --read-only queries/orders.mql
   ```
   Expect: one finding per defect with a severity (blocking, high, medium, low), the audit pass (P2 index use, P4 operator anti-patterns, P5 stage order, P6 sort and cursor cost, P8 pagination) and a `read more` corpus path. The exit code is 1 when any high or blocking finding exists.

2. **Read the blocking findings first.** Blocking means the query may return wrong results (a string compared to a number, key/value predicates that can match different array elements). The optimizer reports these and never rewrites them, because the fix changes the result set. Fix them with the schema or application owner.

3. **Apply the safe rewrites.**
   ```bash
   mdbx optimize --write queries/orders.mql
   ```
   Expect: rewrites that return the same documents — same-field `$or` to `$in`, `{ $gte: x, $lte: x }` to an equality, a `$match` moved ahead of stages that do not produce its fields, `countDocuments({})` to `estimatedDocumentCount()`. The tool repeats the audit until nothing else changes (at most 3 passes). Review the diff before you commit it.

4. **Check the recommended index against what exists.**
   ```js
   db.orders.getIndexes()
   ```
   Expect: the printed `createIndex` may already exist, or an existing index may share its leading keys. A shorter existing index is not redundant just because a longer one shares its prefix.

5. **Capture a baseline on non-production.**
   ```js
   db.orders.find(<filter>).sort(<sort>).explain("executionStats")
   ```
   Record `winningPlan` stages, `totalKeysExamined`, `totalDocsExamined`, `nReturned` and `executionTimeMillis`.

6. **Build the recommended index on non-production.**
   ```js
   db.orders.createIndex({ customerId: 1, total: -1, createdAt: 1 })
   ```
   Expect: the build finishes; on production use a rolling or off-peak build (see the index-build recipe).

7. **Re-run explain and compare.** Run the rewritten query with `explain("executionStats")` at a low-, medium- and high-cardinality value of each filter field.
   Expect: COLLSCAN becomes IXSCAN, an in-memory SORT stage disappears, `totalDocsExamined / nReturned` moves toward 1, and `nReturned` is unchanged. If the range predicate is far more selective than the sort, also test the ERS key order (range before sort) and keep the faster one.

## Verify
- `nReturned` before and after is identical at every tested value; if not, back the rewrite out.
- The winning plan uses the new index and has no blocking SORT.
- `totalDocsExamined` is at or near `nReturned` (0 for a covered query: `PROJECTION_COVERED`).

## Rollback
- Revert the query file to the committed version.
- Hide the new index before dropping it, so you can restore it instantly: `db.orders.hideIndex("<name>")`, observe, then `db.orders.dropIndex("<name>")`.

## Gotchas
- The optimizer is static. It does not know collection size, cardinality or existing indexes, so every impact claim needs explain to confirm it.
- `$in` with 201 or more values is planned like a range and can stop a following sort from using the index.
- A case-insensitive regex cannot use tight index bounds even with `^`; use a lower-cased copy of the field or a collation index.
- `hint()` in application code pins a plan forever; on 8.0+ prefer `setQuerySettings` for an intentional pin.

## Sources
- `skills/mongodb-expert/references/deep-mongodb-mql-query-optimizer.md`
- `skills/mongodb-expert/references/mongodb-query-shape-optimization.md`
- `skills/mongodb-expert/references/mongodb-compound-index-design.md`
- `skills/mongodb-expert/references/mongodb-explain-plans-and-query-planner.md`
