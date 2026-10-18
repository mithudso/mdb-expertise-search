# MongoDB expert context

> Extracted from the hub `SKILL.md` body on 2026-07-20 to keep the hub under its per-invocation
> token budget.
> The hub's routing tables stay in `SKILL.md`; this file carries the general MongoDB
> fundamentals and is the fallback reference when no Sub-skill routing-table row matches.

## How to use this context

Use this file as a **practical MongoDB reference** when designing schemas, writing queries, reviewing data-access code, or debugging performance issues. Treat the **MongoDB Manual** and **driver docs** as the primary operational/application references, and use the **MQL, operator, command, and method reference pages** for exact behavior and syntax details ([MongoDB Manual](https://www.mongodb.com/docs/manual/), [MongoDB Drivers](https://www.mongodb.com/docs/drivers/), [MQL reference](https://www.mongodb.com/docs/manual/reference/mql/), [mongosh methods](https://www.mongodb.com/docs/manual/reference/method/)).

## Source scope

- **Platform overview:** MongoDB docs home and Manual ([MongoDB docs](https://www.mongodb.com/docs/), [MongoDB Manual](https://www.mongodb.com/docs/manual/)).
- **Application-facing usage:** official MongoDB driver docs ([MongoDB Drivers](https://www.mongodb.com/docs/drivers/)).
- **Exact language behavior:** MongoDB Query Language reference, CRUD command reference, query predicate operators, update operators, projection operators, aggregation docs, and aggregation operator reference ([MQL reference](https://www.mongodb.com/docs/manual/reference/mql/), [CRUD commands](https://www.mongodb.com/docs/manual/reference/mql/crud-commands/), [Query operators](https://www.mongodb.com/docs/manual/reference/operator/query/), [Update operators](https://www.mongodb.com/docs/manual/reference/mql/update/), [Projection operators](https://www.mongodb.com/docs/manual/reference/mql/projection/), [Aggregation](https://www.mongodb.com/docs/manual/aggregation/), [Aggregation operators](https://www.mongodb.com/docs/manual/reference/operator/aggregation/)).
- **Shell-specific usage:** mongosh method reference ([mongosh methods](https://www.mongodb.com/docs/manual/reference/method/)).
- **Design and performance guidance:** data modeling, indexes, write atomicity, and transactions docs ([Data modeling](https://www.mongodb.com/docs/manual/data-modeling/), [Indexes](https://www.mongodb.com/docs/manual/indexes/), [Write atomicity](https://www.mongodb.com/docs/manual/core/write-operations-atomicity/), [Transactions](https://www.mongodb.com/docs/manual/core/transactions/)).
- These sources are **MongoDB-specific references and practices**, not a general application architecture style guide. Where they do not prescribe naming, repository structure, or language-specific code style, defer to project-local conventions ([MongoDB Manual](https://www.mongodb.com/docs/manual/), [MongoDB Drivers](https://www.mongodb.com/docs/drivers/)).

## Quick rules

1. Model data around **access patterns**; data accessed together should generally be stored together ([Data modeling](https://www.mongodb.com/docs/manual/data-modeling/)).
2. Prefer **embedding** when it lets you satisfy common reads in a single-document fetch; MongoDB explicitly highlights document structures as a way to avoid unnecessary multi-document transactions ([Data modeling](https://www.mongodb.com/docs/manual/data-modeling/), [Transactions](https://www.mongodb.com/docs/manual/core/transactions/)).
3. Remember that write operations are **atomic at the single-document level**, but multi-document operations are not atomic as a whole unless you use transactions ([CRUD](https://www.mongodb.com/docs/manual/crud/), [Write atomicity](https://www.mongodb.com/docs/manual/core/write-operations-atomicity/), [Transactions](https://www.mongodb.com/docs/manual/core/transactions/)).
4. Create indexes for repeatedly queried fields, but remember every index has a **write cost** ([Indexes](https://www.mongodb.com/docs/manual/indexes/)).
5. Prefer **aggregation pipelines** for aggregations; MongoDB calls them the preferred aggregation method ([Aggregation](https://www.mongodb.com/docs/manual/aggregation/)).
6. Use the **driver** in applications; the MongoDB docs explicitly note that most interactions use an idiomatic driver rather than JavaScript shell methods ([mongosh methods](https://www.mongodb.com/docs/manual/reference/method/), [MongoDB Drivers](https://www.mongodb.com/docs/drivers/)).
7. When concurrent updates matter, include the **expected current value in the filter** or use operators like `$inc` to avoid accidental lost updates ([Write atomicity](https://www.mongodb.com/docs/manual/core/write-operations-atomicity/)).
8. Use transactions only when you truly need multi-document atomicity; many use cases can be modeled to avoid them ([Transactions](https://www.mongodb.com/docs/manual/core/transactions/), [Data modeling](https://www.mongodb.com/docs/manual/data-modeling/)).
9. Treat MQL as more than simple find filters: it includes query predicates, projections, updates, expressions, and aggregation stages/operators ([MQL reference](https://www.mongodb.com/docs/manual/reference/mql/)).
10. Separate **driver usage** from **mongosh usage** in your mental model; shell methods are reference and tooling conveniences, not the main application API surface ([mongosh methods](https://www.mongodb.com/docs/manual/reference/method/), [MongoDB Drivers](https://www.mongodb.com/docs/drivers/)).
11. Use **projections deliberately** to reduce payload and focus reads, especially for arrays and metadata-heavy results ([Projection operators](https://www.mongodb.com/docs/manual/reference/mql/projection/)).

## Core MongoDB model

### Document model and collections

- MongoDB is a **document-oriented operational database** that stores rich JSON-like documents which map naturally to application objects ([MongoDB docs](https://www.mongodb.com/docs/)).
- The document data model is **flexible**: documents in the same collection do not need identical fields, and a field’s type can differ between documents in the same collection ([MongoDB Manual](https://www.mongodb.com/docs/manual/), [Data modeling](https://www.mongodb.com/docs/manual/data-modeling/)).
- Collections group documents; insert operations target a single collection and create it if it does not exist ([CRUD](https://www.mongodb.com/docs/manual/crud/)).

### MQL and how to think about it

- MongoDB Query Language (MQL) includes **query predicates, aggregation pipelines, expressions, projections, accumulators, update operators, and CRUD commands** ([MQL reference](https://www.mongodb.com/docs/manual/reference/mql/)).
- Query predicates are boolean expressions that determine whether a document matches a query ([Query operators](https://www.mongodb.com/docs/manual/reference/operator/query/)).
- Aggregation expressions are **stateless** and resolve to a value without mutating their inputs ([Aggregation operators](https://www.mongodb.com/docs/manual/reference/operator/aggregation/)).

## CRUD and write semantics

### CRUD basics

- CRUD covers **create, read, update, and delete** of documents ([CRUD](https://www.mongodb.com/docs/manual/crud/)).
- MongoDB provides collection-level methods such as `insertOne()` and `insertMany()` for insert operations ([CRUD](https://www.mongodb.com/docs/manual/crud/)).
- At the command layer, CRUD includes commands such as `find`, `insert`, `update`, `delete`, `distinct`, `aggregate`, `findAndModify`, `count`, and `bulkWrite` ([CRUD commands](https://www.mongodb.com/docs/manual/reference/mql/crud-commands/)).

### Atomicity and concurrent updates

- All write operations are atomic at the **single-document level**, even if they modify multiple values inside that document ([CRUD](https://www.mongodb.com/docs/manual/crud/), [Write atomicity](https://www.mongodb.com/docs/manual/core/write-operations-atomicity/)).
- A multi-document update operation modifies each individual document atomically, but the operation as a whole is **not** atomic ([Write atomicity](https://www.mongodb.com/docs/manual/core/write-operations-atomicity/)).
- To avoid conflicts in concurrent updates, include the expected current value in the update filter; filtering only by `_id` while setting a value can cause the second update to overwrite the first silently ([Write atomicity](https://www.mongodb.com/docs/manual/core/write-operations-atomicity/)).
- `$inc` is specifically called out as a safer concurrent pattern than naive overwrite-based `$set` in some conflict scenarios ([Write atomicity](https://www.mongodb.com/docs/manual/core/write-operations-atomicity/)).

## Transactions

- Single-document operations are atomic, and MongoDB explicitly notes that embedded documents and arrays often remove the need for multi-document transactions ([Transactions](https://www.mongodb.com/docs/manual/core/transactions/)).
- MongoDB supports transactions across **multiple operations, collections, databases, documents, and shards** when true multi-document atomicity is required ([Transactions](https://www.mongodb.com/docs/manual/core/transactions/)).
- The callback transaction API starts a transaction, executes operations, and commits or ends it on error; it also incorporates retry logic for some errors such as `TransientTransactionError` and `UnknownTransactionCommitResult` ([Transactions](https://www.mongodb.com/docs/manual/core/transactions/)).
- There are version-sensitive transaction caveats, including explicit notes in the docs about changed retry behavior in newer server versions ([Transactions](https://www.mongodb.com/docs/manual/core/transactions/)).

## Data modeling and schema design guidance

### Core design principle

- A core MongoDB modeling principle is that **data accessed together should be stored together** ([Data modeling](https://www.mongodb.com/docs/manual/data-modeling/)).
- Structure the model according to actual **application data access patterns** to optimize performance ([Data modeling](https://www.mongodb.com/docs/manual/data-modeling/)).

### Embedding vs referencing

- MongoDB’s examples explicitly favor embedding when related data is commonly returned together in a single query, such as department info embedded in employee records ([Data modeling](https://www.mongodb.com/docs/manual/data-modeling/)).
- Referencing or separating collections makes sense when some related data is accessed much less frequently, such as older product reviews stored separately from the hot product-page subset ([Data modeling](https://www.mongodb.com/docs/manual/data-modeling/)).
- Because documents can be polymorphic, a single collection can support differently shaped items when that matches the application’s model ([Data modeling](https://www.mongodb.com/docs/manual/data-modeling/)).

## Indexes and performance

- Indexes allow MongoDB to avoid scanning every document in a collection for supported queries ([Indexes](https://www.mongodb.com/docs/manual/indexes/)).
- Without an appropriate index, MongoDB must scan every document to return results ([Indexes](https://www.mongodb.com/docs/manual/indexes/)).
- Indexes improve read/query performance but add negative performance impact to writes because inserts and updates must also maintain indexes ([Indexes](https://www.mongodb.com/docs/manual/indexes/)).
- If your application repeatedly runs queries on the same fields, MongoDB explicitly recommends creating indexes on those fields ([Indexes](https://www.mongodb.com/docs/manual/indexes/)).

## Aggregation

- Aggregation processes multiple documents and returns computed results, including grouping values, analyzing changes over time, and querying the latest form of data ([Aggregation](https://www.mongodb.com/docs/manual/aggregation/)).
- MongoDB calls **aggregation pipelines** the preferred aggregation method ([Aggregation](https://www.mongodb.com/docs/manual/aggregation/)).
- A pipeline is made of one or more stages, each of which transforms or filters documents before passing them to the next stage ([Aggregation](https://www.mongodb.com/docs/manual/aggregation/)).
- Aggregation expressions can be used in stages like `$project`, `$addFields`, and `$group`, in `$expr` predicates, and in projections ([Aggregation operators](https://www.mongodb.com/docs/manual/reference/operator/aggregation/)).

## Driver vs mongosh guidance

- Most real application interaction with MongoDB uses an **idiomatic driver**, not JavaScript shell methods ([mongosh methods](https://www.mongodb.com/docs/manual/reference/method/), [MongoDB Drivers](https://www.mongodb.com/docs/drivers/)).
- The mongosh method reference is specifically about shell methods and notes that these are functional replacements for legacy shell APIs, not exact replacements in every detail ([mongosh methods](https://www.mongodb.com/docs/manual/reference/method/)).
- Application code should primarily think in terms of the official driver for its language/runtime, while keeping the shell reference available for exploration, debugging, and administrative workflows ([MongoDB Drivers](https://www.mongodb.com/docs/drivers/), [mongosh methods](https://www.mongodb.com/docs/manual/reference/method/)).

## Methods, operators, and APIs inventory

The condensed CRUD-methods, query/projection/update-operators, and aggregation-building-blocks
tables live in `references/mongodb-mql-quick-reference.md` — **Read that file** for the
quick-glance operator/method tables; for real depth on any of them, use the hub `SKILL.md`
Sub-skill routing table (`mongodb-developer`, `mongodb-aggregation-pipeline`,
`mongodb-aggregation-stages-deep`, `mongodb-query-performance`).

## Known ambiguities / version-sensitive notes

- The MongoDB docs site is a **living docs system**; exact behavior can vary by server version, driver version, and API surface, so record the relevant version when precision matters ([MongoDB docs](https://www.mongodb.com/docs/), [MongoDB Drivers](https://www.mongodb.com/docs/drivers/)).
- Some command and transaction behaviors are explicitly version-sensitive in the docs, such as `bulkWrite` being marked new in 8.0 and transaction retry caveats changing in newer versions ([CRUD commands](https://www.mongodb.com/docs/manual/reference/mql/crud-commands/), [Transactions](https://www.mongodb.com/docs/manual/core/transactions/)).
- The mongosh method reference is **not** a universal application API reference; it is shell-specific and explicitly distinguished from idiomatic driver usage ([mongosh methods](https://www.mongodb.com/docs/manual/reference/method/), [MongoDB Drivers](https://www.mongodb.com/docs/drivers/)).
- This file is intentionally condensed. For exhaustive operators, stages, and commands, use the referenced MQL, operator, command, and method index pages directly ([MQL reference](https://www.mongodb.com/docs/manual/reference/mql/), [Query operators](https://www.mongodb.com/docs/manual/reference/operator/query/), [Aggregation operators](https://www.mongodb.com/docs/manual/reference/operator/aggregation/), [mongosh methods](https://www.mongodb.com/docs/manual/reference/method/)).
