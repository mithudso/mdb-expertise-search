# MongoDB MQL Query Optimizer — demo

**Find what makes a MongoDB query slow, fix what is safe to fix, and get the index it needs — before the
query reaches production.**

The MQL Query Optimizer is an AI skill plus a command-line tool. Give it a `find()`, an aggregation pipeline,
an update or delete filter, or a change-stream pipeline. It returns:

1. **Findings** — each defect, how serious it is, and why it costs time or returns wrong results.
2. **Safe rewrites, already applied** — changes that return exactly the same documents.
3. **Index recommendations** — `createIndex` commands in the right key order, with the reason.
4. **A link to the explanation** for every finding, from a curated MongoDB knowledge base.

It works offline on query text alone. In an AI assistant connected to your cluster, the skill goes one step
further and checks each change against real `explain()` output.

---

## Who it is for

| Role | What they get |
|---|---|
| Application developer | A review of every new query in seconds, in the editor or in CI, with fixes they can paste. |
| Database or platform engineer | ESR-ordered index recommendations and a short list of the queries worth a deeper look. |
| Tech lead / reviewer | A severity model that separates "wrong results" from "slow" from "style", so reviews focus on what matters. |
| AI-assisted teams | A tool an agent (Claude Code, Cursor, any MCP client) can call to optimize a query and explain why. |

---

## Three walkthroughs

All output below is real, produced by `mdbx optimize <file>` on the query shown. File paths are shortened.

### 1. The order-history page that gets slower on every page

A customer opens their order history and pages back. Page 100 takes far longer than page 1.

```js
db.orders.find(
  { customerId: 4711, status: { $ne: "cancelled" } },
  { orderNo: 1, total: 1, createdAt: 1 }
).sort({ createdAt: -1 }).skip(2000).limit(20)
```

```text
MQL optimizer (static audit) — orders.mql: 1 query, 2 medium

Findings:
  orders.mql:1:1: MEDIUM [P8 deep-skip] skip(2000) walks and discards 2000 index keys or documents on every
    page, and on a sharded collection mongos asks each shard for limit+skip. Use keyset pagination: sort on a
    unique key and filter { _id: { $gt: lastSeenId } } with limit().
  orders.mql:2:33: MEDIUM [P4 negation] status: $ne cannot use selective index bounds and also matches
    documents missing the field. Where the domain is known, match the wanted values positively ($in /
    equality) — this changes results unless the field is always present, so it is not auto-applied.

Recommended indexes (recommend-only — build on non-prod first, check existing indexes):
  db.orders.createIndex({ customerId: 1, createdAt: -1 })
      ESR order: equality customerId -> sort createdAt.
```

**What this means.** The cost of `skip(2000)` grows with every page, so the fix is keyset pagination ("give
me the 20 orders older than the last one I showed"). The `$ne` is flagged but **not** rewritten: replacing it
with a positive list such as `status: { $in: ["paid", "shipped"] }` is faster but would change which documents
match if some orders have no `status`. The optimizer leaves that decision to you. The index serves the
equality on `customerId` and returns orders already sorted by `createdAt`, so MongoDB never sorts in memory.

### 2. The monthly sales report that runs out of memory

```js
db.sales.aggregate([
  { $lookup: { from: "stores", localField: "storeId", foreignField: "_id", as: "store" } },
  { $addFields: { month: { $dateTrunc: { date: "$soldAt", unit: "month" } } } },
  { $match: { region: "EMEA", soldAt: { $gte: ISODate("2026-01-01") } } },
  { $sort: { amount: -1 } },
  { $group: { _id: "$month", sales: { $push: "$$ROOT" } } },
  { $project: { top10: { $slice: ["$sales", 10] } } }
])
```

```text
MQL optimizer (static audit) — sales.mql: 1 query, 2 high; 1 rewrite(s) applied in 1 iteration(s)

Applied rewrites (result-preserving):
  ✓ [P5 match-not-early-rewrite] Move $match ahead of $lookup, $addFields.

Findings:
  sales.mql:6:39: HIGH [P5 group-root] $push: "$$ROOT" carries whole documents into $group memory (100 MB per
    stage). $project only the fields you need first.
  sales.mql:6:39: HIGH [P5 push-then-slice] sales builds an unbounded array with $push and a later stage
    slices it. Use a bounded accumulator ($firstN / $lastN / $topN / $bottomN, 5.2+) so the discarded
    elements are never held in memory.

Recommended indexes (recommend-only — build on non-prod first, check existing indexes):
  db.sales.createIndex({ region: 1, soldAt: 1 })
      [leading $match/$sort] ESR order: equality region -> range soldAt.

Rewritten query:
db.sales.aggregate([
  { $match: { region: "EMEA", soldAt: { $gte: ISODate("2026-01-01") } } },
  { $lookup: { from: "stores", localField: "storeId", foreignField: "_id", as: "store" } },
  { $addFields: { month: { $dateTrunc: { date: "$soldAt", unit: "month" } } } },
  { $sort: { amount: -1 } },
  { $group: { _id: "$month", sales: { $push: "$$ROOT" } } },
  { $project: { top10: { $slice: ["$sales", 10] } } }
])
```

**What this means.** The `$match` did not depend on the joined `store` or the computed `month`, so the
optimizer moved it to the front. Now it filters before the join, and it can use the recommended index. The
two high findings explain the memory failure: every sale in a month is pushed into one array, then all but
ten are thrown away. Replacing that pair with `{ $topN: { n: 10, sortBy: { amount: -1 }, output: … } }` keeps
only ten per month in memory. That rewrite needs a choice of output fields, so the optimizer explains it
rather than guessing.

### 3. The product filter that returns the wrong products

```js
db.products.find({
  "attributes.name": "color",
  "attributes.value": "red",
  price: { $lt: "50" },
  sku: /-XL$/
})
```

```text
MQL optimizer (static audit) — products.mql: 1 query, 2 blocking, 1 medium

Findings:
  products.mql:2:3: BLOCKING [P4 kv-without-elemmatch] Separate predicates on attributes.name and
    attributes.value can be satisfied by different elements of the attributes array, so an element
    name=a,value=1 next to name=b,value=2 matches name=a,value=2. Put both inside
    { attributes: { $elemMatch: { name: …, value: … } } } and index
    { "attributes.name": 1, "attributes.value": 1 }. Reported, not applied: it changes the result set.
  products.mql:4:17: BLOCKING [P4 string-numeric-compare] price $lt "50" compares strings lexicographically
    ("10" < "2"). If the field holds numbers as strings, results are wrong; store numbers as numbers.
    Reported, not applied.
  products.mql:5:8: MEDIUM [P4 unanchored-regex] /-XL$/ is not anchored, so it scans every index key (or
    document). Anchor it with ^ if the value is a prefix, or use Atlas Search for substring / full-text
    matching.
```

**What this means.** This query is not just slow — it is wrong. A blue product with a `size: red` attribute
matches "color = red", and a price of `"100"` sorts before `"50"` as text. These are **blocking** findings: the
optimizer reports them first and never rewrites them, because the correct fix changes the result set and
belongs to the data owner.

---

## How it decides

### Severity

| Severity | Meaning | Examples |
|---|---|---|
| **Blocking** | Results may be wrong, or a rewrite would change them. Reported, never auto-applied. | numbers stored or compared as strings; key/value array predicates outside `$elemMatch` |
| **High** | Large, predictable cost. | `$where`; whole documents pushed into `$group`; unbounded `$push` later sliced; `$in` with 10,000+ values |
| **Medium** | Real cost with a known fix. | unanchored or case-insensitive regex; `$ne`/`$nin`; `$in` of 201+ values before a sort; deep `skip()`; `$match` placed late; tiny `batchSize` |
| **Low** | Worth knowing. | `sort()` with no `limit()`; a pinned `hint()`; `$group` that reads the whole collection |

### Audit passes

| Pass | Checks |
|---|---|
| P2 Index use and ESR | Index key order (Equality, Sort, Range — and when to test Range before Sort), one index per `$or` branch, covered-query opportunities, pinned hints vs 8.0 query settings |
| P4 Operator anti-patterns | regex, negation, `$in` size thresholds, same-field `$or`, degenerate ranges, `$expr`, `$where`, type mismatches, array key/value patterns |
| P5 Stage order | `$match` placement, `$lookup` indexes, `$group` memory, `$sort` + `$group` `DISTINCT_SCAN` shape, search-adjacent stages, change streams, `$sample` |
| P6 Sort and cursor cost | blocking sorts, `batchSize`, `count()` vs `countDocuments()` vs `estimatedDocumentCount()`, `distinct()` limits |
| P7 Projection | covered queries (`PROJECTION_COVERED`, `_id: 0`) |
| P8 Pagination | `skip()` / `$skip` depth, keyset pagination |

### Rewrites it applies by itself

Only rewrites that return the same documents: same-field `$or` → `$in`; `{ $gte: x, $lte: x }` → `x`;
moving a `$match` ahead of stages that do not produce the fields it reads (layout preserved);
`countDocuments({})` → `estimatedDocumentCount()`. It re-audits the rewritten text and repeats until nothing
changes, at most three passes.

---

## What it never does

- **Never changes results.** Anything that would return different documents is reported as blocking and left
  to you.
- **Never creates or drops an index.** Index commands are printed for you to review and build on a
  non-production cluster first. Retiring an index follows hide → observe → drop.
- **Never runs a write to "test" a rewrite.** In connected mode it uses read-only `explain`, `find`, `count`
  and `aggregate` only.
- **Never claims a speed-up it has not measured.** Offline findings are predictions; the report says so and
  tells you what to check in `explain("executionStats")`.

---

## Two ways to run it

### As a skill in your AI assistant (connected mode)

In Claude Code or another assistant with the MongoDB MCP server connected to a **non-production** cluster:

> Optimize this pipeline and verify the changes.

The skill reads the collection's indexes and schema, runs the audit, applies the safe rewrites, and checks
each one with `explain`: the plan moves from `COLLSCAN` to `IXSCAN`, an in-memory `SORT` disappears,
`totalDocsExamined / nReturned` moves toward 1, and `nReturned` stays the same. It repeats the check at low-,
medium- and high-cardinality values, because a fix that only wins on the rarest value is not a fix. Any change
that does not improve the plan is backed out.

### As a command-line tool (offline mode)

```bash
pip install -e '.[all]'                      # from the mdb-expertise-search repository
mdbx optimize queries/orders.mql             # report + rewritten text
mdbx optimize --write queries/orders.mql     # apply safe rewrites in place
mdbx optimize --json queries/orders.mql      # machine-readable, for CI or scripts
cat query.js | mdbx optimize -               # from stdin
```

The exit code is 1 when a high or blocking finding remains, so `mdbx optimize` can gate a pull request. The
same findings appear as you type in VS Code, Neovim or Helix (the `mql-lsp` language server), and as the
`mql_optimize` tool for any MCP-capable agent.

---

## Try it in five minutes

```bash
git clone <repository> && cd mdb-expertise-search
python3 -m venv .venv && .venv/bin/pip install -e '.[all]'
.venv/bin/mdbx optimize examples/slow-queries.mql
```

`examples/slow-queries.mql` holds five queries with common defects. Expect 10 findings (2 blocking, 3 high,
4 medium, 1 low), 4 rewrites applied, and 5 index recommendations. Then follow the
`optimize-an-mql-query` runbook (`mdbx recipe optimize`) to confirm a fix with `explain()` on your own data.

---

## Frequently asked questions

**Does it need access to my database?** No. Offline mode reads query text only. Connected mode, through the AI
skill, needs read access to a non-production cluster for `explain`.

**Does my query text leave my machine?** Not in offline mode: `mdbx optimize` runs locally. In connected mode
your AI assistant's own data policy applies.

**Which MongoDB versions does it understand?** The rules carry version notes where behavior changed — for
example `$where` deprecation and `setQuerySettings` (8.0), bounded accumulators such as `$topN` (5.2), and the
cost-based plan ranker (8.3). Confirm version-sensitive advice against your deployment.

**Can it be wrong?** Offline, it does not know your data size, value distribution or existing indexes, so an
index it recommends may already exist, or a finding may not matter on a tiny collection. That is why every
impact claim is labelled static and every recommendation is recommend-only until `explain` confirms it.

**What about Atlas Search and Vector Search?** It checks the stages around a `$search` stage (sorting after
search, over-fetching limits). Relevance and analyzer tuning are out of scope.

---

*Static analysis only. Validate every recommendation with `explain("executionStats")` on representative data
before applying it in production.*
