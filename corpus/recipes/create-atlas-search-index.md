---
name: create-atlas-search-index
title: Create and tune an Atlas Search index
summary: Define an Atlas Search index (static or dynamic mappings, analyzers), create it, wait until it is ready, query it with $search, update it, and size it with cost in mind.
applies_to: [atlas]
sources:
  - skills/mongodb-atlas-expert/references/mongodb-atlas-search.md
  - skills/mongodb-atlas-expert/references/mongodb-search-ai.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-search-nodes.md
  - skills/mongodb-operations-expert/references/mongodb-cost-optimization.md
---
# Create and tune an Atlas Search index

## When to use
- You need relevance-ranked text search, autocomplete, facets or fuzzy matching on an Atlas collection.
- A `$regex` or text-index query is too slow or gives poor ranking.
- You must change an existing search index definition (add a field, change an analyzer).

## Prerequisites (checklist)
- [ ] The data lives in an Atlas cluster (Atlas Search is not part of a plain mongod).
- [ ] You listed the fields users will search, filter, sort and facet on. Each needs a field type.
- [ ] You decided: static mappings (production default) or dynamic mappings (prototype only).
- [ ] You know that a search index is separate from a normal index; it is stored in Atlas and not in `system.indexes`.
- [ ] You can tolerate eventual consistency. Search indexes lag the database; do not use them where read-your-writes is required.
- [ ] You checked the search index count (hard limit 2,500 per cluster per the corpus) and expected index size.
- [ ] A role that can create search indexes on the project.

## Steps

1. **List the queries first.** Write each query as `$search` operators plus the fields they touch.
   ```
   text on title and body; equals on inStock; range on price; facet on category
   ```
   Expect: a field list with one type per use: `string` (analyzed text), `token` (exact match on enum or ID-like values), `number`, `date`, `boolean`, `autocomplete`, `stringFacet`, `geo`.

2. **Choose the mapping mode.**
   | Mode | Behavior | Use when |
   |---|---|---|
   | `"dynamic": true` | Indexes all supported field types | Prototyping or schema-flexible data |
   | `"dynamic": false` | Indexes only listed fields | Production; controls size and cost |
   | Mixed | `false` at the root, `true` for a known embedded subset | Wide documents with a searchable subset |
   Expect: a decision. `autocomplete` and `stringFacet` fields cannot come from dynamic mappings; declare them statically.

3. **Write the index definition JSON** (static mapping with explicit analyzers).
   ```json
   {
     "name": "products_search",
     "type": "search",
     "collectionName": "products",
     "database": "mydb",
     "definition": {
       "analyzer": "lucene.standard",
       "searchAnalyzer": "lucene.standard",
       "mappings": {
         "dynamic": false,
         "fields": {
           "title":    { "type": "string", "analyzer": "lucene.english" },
           "body":     { "type": "string" },
           "category": { "type": "stringFacet" },
           "price":    { "type": "number" },
           "inStock":  { "type": "boolean" },
           "slug":     { "type": "token" }
         }
       }
     }
   }
   ```
   Expect: a valid JSON file. Built-in analyzers include `lucene.standard`, `lucene.simple`, `lucene.whitespace`, `lucene.keyword` and language analyzers such as `lucene.english`. Use `analyzer` for indexing and `searchAnalyzer` for queries if they must differ.

4. **(If needed) add a custom analyzer.** Only the tokenizer is required; char filters and token filters are optional.
   ```json
   "analyzers": [{
     "name": "my_html_english",
     "charFilters": [{ "type": "htmlStrip" }],
     "tokenizer": { "type": "standard" },
     "tokenFilters": [{ "type": "lowercase" }, { "type": "englishMinimalStem" }]
   }]
   ```
   Expect: the analyzer name is then usable in a field's `analyzer`. A custom analyzer built on an `edgeGram` or `nGram` tokenizer cannot be used for an `autocomplete` field; use the field type's own `tokenization` setting.

5. **(If needed) keep autocomplete in its own index.** Put `autocomplete` fields in a separate search index from your text and facet fields, with small gram sizes.
   ```json
   "titleAutocomplete": { "type": "autocomplete", "tokenization": "edgeGram", "minGrams": 2, "maxGrams": 15 }
   ```
   Expect: separate builds and sizing. The corpus recommends `maxGrams` at or below 15 and says very high values make builds slow and indexes several times larger.

6. **Create the index.** Pick one path.
   - Atlas CLI:
     ```bash
     atlas clusters search indexes create \
       --clusterName <cluster-name> \
       --file search-index.json \
       --projectId <project-id>
     ```
   - mongosh:
     ```js
     db.products.createSearchIndex({ name: "products_search", definition: { mappings: { dynamic: false, fields: { title: { type: "string" } } } } })
     ```
   - Atlas UI: cluster -> Search -> Create Search Index.
   Expect: the index is created in a `BUILDING`/initial-sync state. Verify in the current MongoDB docs: the exact mongosh signature for a `type: "search"` index, since the corpus shows `createSearchIndex` only for vector indexes.

7. **Wait for the build to finish.** During initial sync, `$search` returns no results (not an error).
   ```js
   db.products.getSearchIndexes()
   ```
   Expect: your index with `status: "READY"` and `queryable: true`. Large collections or autocomplete fields can take minutes to hours.

8. **Run a first `$search` query.** `$search` must be the first pipeline stage.
   ```js
   db.products.aggregate([
     { $search: {
         index: "products_search",
         compound: {
           must:   [{ text: { query: "wireless headphones", path: "title" } }],
           should: [{ text: { query: "noise cancelling", path: "body", score: { boost: { value: 2 } } } }],
           filter: [{ equals: { path: "inStock", value: true } },
                    { range: { path: "price", gte: 50, lte: 300 } }]
         }
     } },
     { $limit: 20 },
     { $project: { title: 1, price: 1, score: { $meta: "searchScore" } } }
   ])
   ```
   Expect: documents ranked by `searchScore`. Clause roles: `must` and `should` affect score; `filter` must match but adds no score; `mustNot` excludes.

9. **Check relevance, not just that it runs.** Add `scoreDetails: true` temporarily and project `{ $meta: "searchScoreDetails" }` for a few results.
   Expect: a nested tree with term frequency and inverse document frequency parts. Turn it off afterward because it costs performance.

10. **Update the index when requirements change.**
    ```bash
    atlas clusters search indexes update <index-id> \
      --clusterName <cluster-name> --file updated-index.json --projectId <project-id>
    ```
    Expect: the index returns to a building state and then `READY`. The corpus notes that changing field types or analyzers triggers a rebuild. Verify in the current MongoDB docs: whether the old definition keeps serving queries while the new one builds.

11. **Check size, lag and cost.** Look at index size and replication lag in the Atlas UI Search metrics.
    Expect: index size is in line with your estimate. If search queries compete with the database for CPU and RAM, or the Lucene index is above roughly 10-20 GB, or sustained search load is above roughly 100 queries per second, consider dedicated Search Nodes.

12. **Remove indexes nobody queries.** Search indexes on large collections add storage cost.
    ```bash
    atlas clusters search indexes delete <index-id> --clusterName <cluster-name> --projectId <project-id> --force
    ```
    Expect: the index disappears from `getSearchIndexes()`. Confirm that no application path still calls it first.

## Verify
- `db.products.getSearchIndexes()` shows `status: "READY"` for the expected `name`.
- A representative `$search` returns results and `searchScore` values in the order users expect.
- A query for a term you know exists returns the document (not an empty list, which indicates initial sync is not finished).
- Search replication lag stays low after a bulk write (Atlas alert "Search Max Replication Lag" is quiet).
- `explain` on the aggregation completes without errors.

## Rollback / abort
- Bad definition: update the index with the previous definition file (keep the old JSON in version control).
- Wrong index entirely: delete it with `atlas clusters search indexes delete` or the UI. Application queries that name the index will then fail or return nothing; deploy the app change first.
- Build taking too long: delete it and recreate after trimming the mapping (disable dynamic mapping, shrink autocomplete grams).
- Search Nodes migration: moving back from dedicated Search Nodes to embedded mongot has downtime per the corpus; plan that separately.

## Pitfalls
- Leaving `"dynamic": true` in production. It indexes every field, bloating the index and RAM use.
- Expecting `autocomplete` or facet types to appear under dynamic mappings. They never do.
- Putting `autocomplete` and text fields in one index. A change to either forces a full rebuild.
- High `maxGrams` on big collections. It multiplies tokens per document.
- Combining `fuzzy` and `synonyms` on the same `text` operator. That combination is not allowed.
- Putting `$match` before `$search`. `$search` must be first; use `compound.filter` for pre-filtering.
- Using leading wildcards or unbounded regex in `wildcard` or `regex` operators. They scan all terms.
- Using `$sort` after `$search` and expecting relevance order. `$sort` after the stage discards relevance; use the `sort` option inside `$search` (supported in Atlas Search on MongoDB 7.0 and later per the corpus) or `near`.
- Passing `null` for `scoreDetails` or `returnStoredSource` on 8.0.14 and later. They must be explicit `true` or `false`. Verify in the current MongoDB docs: this 8.0.14 claim.
- Treating the search index as strongly consistent. It is fed by change streams and lags.
- Synonym collection in the wrong place. It must be a collection in the same database as the indexed collection and follow the documented schema.
- Forgetting cost. Dedicated Search Nodes bill per node per hour and the minimum is two nodes. Index storage on search nodes is billed separately.
- Disk on a Search Node reaching 90% pauses replication; if the pause outlasts the oplog window, a full rebuild is needed.

## Sources
- skills/mongodb-atlas-expert/references/mongodb-atlas-search.md:60-100 (query flow, async sync via change streams, `INITIAL SYNC`, `getSearchIndexes`)
- skills/mongodb-atlas-expert/references/mongodb-atlas-search.md:107-165 (definition JSON, dynamic vs static, field types)
- skills/mongodb-atlas-expert/references/mongodb-atlas-search.md:261 (synonyms), :364 (compound), :1039 (AP-1), :1056 (AP-3), :1136 (AP-12)
- skills/mongodb-atlas-expert/references/mongodb-atlas-search.md:998-1030 (sizing guide, cost model, key metrics)
- skills/mongodb-atlas-expert/references/mongodb-search-ai.md:105-190 (typeSets, static mappings, analyzers), :405-425 (status values, replication lag), :1151 (limitations)
- skills/mongodb-atlas-expert/references/mongodb-atlas-cli.md:909-960 (search index CLI commands and sample JSON)
- skills/mongodb-atlas-expert/references/mongodb-atlas-search-nodes.md:464-480 (eventual consistency, rebuild), :632-670 (limits, 90% disk behavior)
- skills/mongodb-operations-expert/references/mongodb-cost-optimization.md:460 (forgotten search indexes)
