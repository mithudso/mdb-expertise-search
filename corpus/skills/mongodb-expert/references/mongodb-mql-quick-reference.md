# MQL Methods, Operators, and APIs — Quick Reference

This is a **condensed high-value inventory** of core CRUD, query/projection/update, and aggregation
building blocks — not a verbatim dump of every MongoDB operator or method. It was extracted from
the `mongodb-expert` SKILL.md bundled context to keep that file under its token budget; for deeper
treatment of any row here, follow the linked reference file from the hub's Sub-skill routing table
(`mongodb-developer` for driver/CRUD usage, `mongodb-aggregation-pipeline` and
`mongodb-aggregation-stages-deep` for aggregation, `mongodb-query-performance` for query tuning).

## CRUD methods and commands

| API | Purpose | Key args/params | Return/effect | Typical usage | Caveats |
|---|---|---|---|---|---|
| `db.collection.insertOne()` | Insert one document ([CRUD](https://www.mongodb.com/docs/manual/crud/)) | document | Adds one document to a collection | Single-document creation | Targets one collection; creates collection if needed |
| `db.collection.insertMany()` | Insert multiple documents ([CRUD](https://www.mongodb.com/docs/manual/crud/)) | array of documents | Adds many documents | Batch creation | Still collection-scoped |
| `find` command / `db.collection.find()` | Select documents from a collection or view ([CRUD commands](https://www.mongodb.com/docs/manual/reference/mql/crud-commands/)) | query filter, projection, options | Returns matching documents/cursor semantics depending API | Reads by predicate | Behavior differs slightly by driver/shell surface |
| `update` command / update methods | Update one or more documents ([CRUD commands](https://www.mongodb.com/docs/manual/reference/mql/crud-commands/)) | filter, update document/operators, options | Modifies matched docs | Targeted updates | Single-doc atomicity only |
| `delete` command / delete methods | Delete one or more documents ([CRUD commands](https://www.mongodb.com/docs/manual/reference/mql/crud-commands/)) | filter | Removes matched docs | Cleanup or lifecycle deletion | Multi-doc deletions are not atomic as a whole |
| `findAndModify` | Modify and return a single document ([CRUD commands](https://www.mongodb.com/docs/manual/reference/mql/crud-commands/)) | filter, modification, options | Returns/modifies one document | Read-modify-write workflows | Single-document oriented |
| `aggregate` | Run aggregation pipeline on collection or view ([CRUD commands](https://www.mongodb.com/docs/manual/reference/mql/crud-commands/), [Aggregation](https://www.mongodb.com/docs/manual/aggregation/)) | pipeline stages, options | Computed result set | Analytics, reshaping, derived results | Prefer pipelines over older/simpler aggregation approaches |
| `distinct` | Return distinct values for a field ([CRUD commands](https://www.mongodb.com/docs/manual/reference/mql/crud-commands/)) | field, filter/options | Unique values | Faceting-style retrieval | Index support matters for performance |
| `bulkWrite` | Perform many write ops in one request ([CRUD commands](https://www.mongodb.com/docs/manual/reference/mql/crud-commands/)) | batched operations | Many inserts/updates/deletes | High-throughput batch write workflows | The `db.collection.bulkWrite()` method predates 8.0; only the top-level, multi-namespace `bulkWrite` command is new in 8.0 |

## Query, projection, and update operators

| API | Purpose | Key args/params | Return/effect | Typical usage | Caveats |
|---|---|---|---|---|---|
| Query predicates | Boolean document matching expressions ([Query operators](https://www.mongodb.com/docs/manual/reference/operator/query/)) | field/operator/value expressions | Match or reject documents | Filtering in reads and updates | Operator category matters: array, comparison, logical, geospatial, etc. |
| `$eq` and other comparison operators | Compare field values in predicates ([Query operators](https://www.mongodb.com/docs/manual/reference/operator/query/)) | field comparisons | Match docs by comparison | Standard filtered reads | Use the right operator family for the predicate |
| `$expr` | Use expressions inside query predicates ([Aggregation operators](https://www.mongodb.com/docs/manual/reference/operator/aggregation/)) | expression tree | Boolean match behavior in query context | Computed predicate logic | Pulls expression semantics into query matching |
| `$` projection operator | Project first array element matching query condition ([Projection operators](https://www.mongodb.com/docs/manual/reference/mql/projection/)) | projection syntax | Limits returned array content | Array-focused reads | Not supported on view `find()` operations |
| `$elemMatch` projection | Project first array element matching explicit condition ([Projection operators](https://www.mongodb.com/docs/manual/reference/mql/projection/)) | `$elemMatch` projection condition | Limits returned array content | Focused array projections | Not supported on view `find()` operations |
| `$slice` projection | Limit number of projected array elements ([Projection operators](https://www.mongodb.com/docs/manual/reference/mql/projection/)) | skip/limit slice args | Returns subset of array | Smaller array payloads | Not supported on view `find()` operations |
| `$set` | Set field value in document ([Update operators](https://www.mongodb.com/docs/manual/reference/mql/update/)) | field/value map | Overwrites target field values | Standard updates | Can clobber concurrent overwrite-based updates |
| `$inc` | Increment numeric field by amount ([Update operators](https://www.mongodb.com/docs/manual/reference/mql/update/), [Write atomicity](https://www.mongodb.com/docs/manual/core/write-operations-atomicity/)) | field/amount map | Adds delta | Counters, safer concurrent increments | Preferred in some concurrent update scenarios |
| `$currentDate` | Set field to current date or timestamp ([Update operators](https://www.mongodb.com/docs/manual/reference/mql/update/)) | field spec | Writes current temporal value | Updated-at style fields | Field ordering behavior is version-sensitive |
| `$setOnInsert` | Set field only on upsert-insert path ([Update operators](https://www.mongodb.com/docs/manual/reference/mql/update/)) | field/value map | Applies only when upsert inserts | Default values on upsert | No effect on plain matched update |

## Aggregation building blocks

| API | Purpose | Key args/params | Return/effect | Typical usage | Caveats |
|---|---|---|---|---|---|
| Aggregation pipeline | Preferred aggregation flow ([Aggregation](https://www.mongodb.com/docs/manual/aggregation/)) | ordered list of stages | Transforms/aggregates documents | Reporting, reshaping, analytics | Stage order matters |
| `$project` | Reshape/project fields ([Aggregation operators](https://www.mongodb.com/docs/manual/reference/operator/aggregation/)) | projection expression | New document shape | Output shaping | Expression-driven, stateless logic |
| `$addFields` | Add computed fields ([Aggregation operators](https://www.mongodb.com/docs/manual/reference/operator/aggregation/)) | field/expression mapping | Augmented document | Derived values mid-pipeline | Watch pipeline complexity |
| `$group` | Group documents and compute accumulated values ([Aggregation](https://www.mongodb.com/docs/manual/aggregation/), [Aggregation operators](https://www.mongodb.com/docs/manual/reference/operator/aggregation/)) | grouping key plus accumulators | Grouped aggregate output | Rollups and metrics | Requires accumulator semantics |
| Expressions such as `$add` | Compute values from constants, operators, and field paths ([Aggregation operators](https://www.mongodb.com/docs/manual/reference/operator/aggregation/)) | operator plus operands | Value result | Arithmetic, transforms, computed projections | Expressions are stateless |
