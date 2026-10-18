---
name: create-atlas-vector-search-index
title: Create an Atlas Vector Search index and query it
summary: Define a vectorSearch index (dimensions, similarity, filter fields), generate and store embeddings, run $vectorSearch with the right numCandidates and filter, and add hybrid search where it helps.
applies_to: [atlas]
sources:
  - skills/mongodb-atlas-expert/references/mongodb-atlas-vector-search.md
  - skills/mongodb-atlas-expert/references/mongodb-search-ai.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-hybrid-retrieval-frontier-20261001.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-search-nodes.md
  - skills/mongodb-atlas-expert/SKILL.md
  - skills/atlas-vector-search-pii-isolation/SKILL.md
---
# Create an Atlas Vector Search index and query it

## When to use
- You need semantic search or retrieval for a RAG application over data in Atlas.
- You already have (or will generate) embedding vectors per document or chunk.
- You need to filter vector results by metadata such as category, tenant or date.

## Prerequisites (checklist)
- [ ] An Atlas cluster with the target collection.
- [ ] An embedding model chosen, and its output dimension known exactly.
- [ ] You know whether the model's vectors are normalized (this decides the similarity metric).
- [ ] You listed every field you will filter on in `$vectorSearch`.
- [ ] A plan for how new and changed documents get embeddings (batch job, trigger, change-stream worker, or Auto Embedding).
- [ ] A small labeled set of queries (50-100 per the corpus) to measure recall.
- [ ] Access control reviewed: if the index holds data for several tenants or entitlement groups, do not rely on the application alone; see the PII isolation material in this corpus.

## Steps

1. **Pick dimensions and similarity from the model, not from habit.**
   | Model family (examples in the corpus) | `numDimensions` | `similarity` |
   |---|---|---|
   | OpenAI ada-002 | 1536 | `cosine` |
   | Voyage 4 / voyage-3 | 1024 | follow the model's recommended metric (`dotProduct` on normalized vectors, or `cosine`) |
   | many sentence transformers | 768 | check the model card; most use `cosine` |
   The example in step 3 uses `cosine` with 1024 dimensions; the metric you choose must match the embedding model's recommendation, so replace it if your model calls for `dotProduct` or `euclidean`.
   Expect: one pair of values. `numDimensions` must equal the model output exactly; the corpus states Atlas supports up to 8192 dimensions. The similarity metric is baked into the index at creation, and changing it means rebuilding the index.

2. **Decide on quantization up front.** Memory scales with vector count times dimensions times bytes per dimension (float32 is 4 bytes, int8 scalar is 1 byte, binary is 1/8 byte).
   ```
   1M vectors x 1536 dims x 4 bytes = about 6 GB of index RAM
   ```
   Expect: a RAM estimate with at least 10% headroom on the search node. The corpus advises scalar quantization above about 1M vectors and binary above about 5M, with a higher `numCandidates` to compensate.

3. **Write the index definition.** Declare the vector field and every filter field.
   ```json
   {
     "fields": [
       { "type": "vector", "path": "embedding", "numDimensions": 1024, "similarity": "cosine" },
       { "type": "filter", "path": "category" },
       { "type": "filter", "path": "year" }
     ]
   }
   ```
   Expect: valid JSON. Optional tuning on the vector field: an `hnswOptions` object with `maxEdges` and `numEdgeCandidates`, and `"quantization": "scalar"` or `"binary"`. Verify in the current MongoDB docs: the defaults and allowed ranges for `maxEdges` and `numEdgeCandidates`, and that higher `numEdgeCandidates` improves build quality at the cost of build time rather than query latency.

4. **Create the index.**
   ```python
   from pymongo.operations import SearchIndexModel
   model = SearchIndexModel(
       definition={"fields": [
           {"type": "vector", "path": "embedding", "numDimensions": 1024, "similarity": "cosine"},
           {"type": "filter", "path": "category"},
       ]},
       name="vector_index", type="vectorSearch")
   collection.create_search_index(model=model)
   ```
   mongosh equivalent: `db.articles.createSearchIndex({ name: "vector_index", type: "vectorSearch", definition: { fields: [ ... ] } })`.
   Expect: the index starts building. Verify in the current MongoDB docs: the current CLI command for creating a `vectorSearch` index, because the corpus documents the CLI only for Atlas Search indexes.

5. **Generate and store embeddings.** Use a document-side input type when you embed content, and a query-side type when you embed user queries.
   ```python
   result = voyage_client.embed(texts, model="voyage-4", input_type="document")
   collection.bulk_write([UpdateOne({"_id": d["_id"]}, {"$set": {"embedding": e}})
                          for d, e in zip(batch, result.embeddings)])
   ```
   Expect: every document has an `embedding` array of exactly `numDimensions` floats. The corpus batch example sends up to 128 texts per request and selects documents with `{"embedding": {"$exists": False}}`. Alternatives: an Atlas trigger (near-real-time), a change-stream worker (real-time), or Auto Embedding with an `autoEmbed` field (public preview as of May 2026; check status before production).

6. **Chunk before you embed when documents are long.** Use fixed chunks of about 512-1000 tokens with 50-100 tokens of overlap as a baseline, and put context in the chunk text.
   Expect: one document per chunk, with metadata fields (source, category, tenant) next to the vector so filters work.

7. **Wait until the index is queryable.**
   ```js
   db.articles.getSearchIndexes()
   ```
   Expect: your index with `status: "READY"` and `queryable: true`.

8. **Run an approximate (ANN) query.** `$vectorSearch` must be the first stage.
   ```js
   db.articles.aggregate([
     { $vectorSearch: {
         index: "vector_index",
         path: "embedding",
         queryVector: queryEmbedding,       // same model, query input type
         numCandidates: 200,
         limit: 10,
         filter: { category: "electronics" }
     } },
     { $project: { embedding: 0, title: 1, body: 1, score: { $meta: "vectorSearchScore" } } }
   ])
   ```
   Expect: up to 10 documents with `vectorSearchScore` between 0 and 1. Start with `numCandidates` at 20 times `limit`; the maximum is 10,000 and it must be at least `limit`. The `filter` field must be declared as `"type": "filter"` in the index or the filter will not use the index efficiently.

9. **Measure recall against exact search.** Run the same queries with `exact: true` (omit `numCandidates`) on a sample.
   ```js
   { $vectorSearch: { index: "vector_index", path: "embedding", queryVector: queryEmbedding, exact: true, limit: 10 } }
   ```
   Expect: a ground-truth result set. Raise `numCandidates` until the overlap with the exact results is about 90-95% at acceptable latency. Exact search is fine for small sets (under about 100K vectors) and for validation.

10. **Add keyword matching with hybrid search when queries contain names, codes or rare terms.** `$rankFusion` combines `$vectorSearch` and `$search` by rank.
    ```js
    db.articles.aggregate([
      { $rankFusion: {
          input: { pipelines: {
            vectorPipeline: [{ $vectorSearch: { index: "vector_index", path: "embedding", queryVector: queryEmbedding, numCandidates: 100, limit: 50 } }],
            fullTextPipeline: [{ $search: { index: "text_index", text: { query: queryText, path: ["title", "body"] } } }, { $limit: 50 }]
          } },
          combination: { weights: { vectorPipeline: 1.0, fullTextPipeline: 0.8 } },
          scoreDetails: true
      } },
      { $project: { title: 1, score: { $meta: "score" } } },
      { $limit: 10 }
    ])
    ```
    Expect: one de-duplicated, fused ranking. `$rankFusion` needs MongoDB 8.0 or later. `$scoreFusion` is the score-based alternative; the corpus disagrees on its minimum version (8.2 in one place, 8.3 in the current reference), so verify in the current MongoDB docs before relying on it. Sub-pipelines run serially, allow only `$search`, `$vectorSearch`, `$match`, `$sort` and `$geoNear` (and `$limit` and `$skip` for `$scoreFusion`), and cannot use `$project`; project after the fusion stage. Verify in the current MongoDB docs: whether `$limit` is allowed inside `$rankFusion` sub-pipelines (the `$limit: 50` in the example above); if it is not, remove it and cap results with `limit` inside `$vectorSearch` and a final `$limit` after the fusion stage.

11. **Size for production.** If vector RAM is a large share of data-node RAM (the corpus gives 20-30%), or QPS and p99 latency are rising, move to dedicated Search Nodes.
    Expect: search node RAM at least 10% larger than the total vector index size; a minimum of two Search Nodes.

## Verify
- `getSearchIndexes()` shows `READY` and `queryable: true` for the `vectorSearch` index.
- A test query returns results; the top hits are semantically sensible for five hand-picked queries.
- `len(queryVector)` equals the index `numDimensions` (assert this at application startup).
- Recall against the `exact: true` baseline is in your target range (about 90-95%).
- Results omit the embedding field (check payload size).
- A filtered query returns only documents that match the filter.

## Rollback / abort
- Wrong dimensions, wrong similarity, or wrong filter set: you cannot change the metric in place. Create a new index with a new name, switch the application's `index` parameter, then delete the old one.
- Embeddings from the wrong model: write new vectors to a new field (for example `embedding_v2`) with its own index, switch over, then remove the old field and index.
- Hybrid query regresses relevance: remove the `$rankFusion` stage and go back to plain `$vectorSearch`; no data change is needed.
- Cost too high: enable quantization on a new index and compare recall, or delete unused indexes.

## Pitfalls
- `numCandidates` close to `limit`. Recall drops sharply (below 70% in the corpus example). Use at least 20 times `limit`.
- Filtering on an undeclared field. The index does not cover it and performance degrades.
- Wrong similarity for the model, for example `euclidean` on normalized vectors.
- Dimension mismatch between the index and the query vector.
- Missing `input_type` (`document` for stored text, `query` for questions) with models that need it, which reduces recall.
- Returning the embedding array in results. It inflates payloads; always exclude it.
- Using `$vectorSearch` inside `$lookup`, `$facet` or a view definition. It is not allowed, and it cannot follow other stages (outside the fusion stages).
- No evaluation set. Without recall@K you cannot tell quality loss from index tuning.
- Pure vector search for keyword-heavy queries (product names, error codes). Add a text pipeline.
- Binary quantization treated as free. It needs a higher `numCandidates` and rescoring.
- Multi-tenant data in one shared index without pre-filtering. Isolation by filter is an access-control boundary and must be tested.
- Relying on score details alone. The format is not guaranteed, so do not parse it in production code.

## Sources
- skills/mongodb-atlas-expert/references/mongodb-atlas-vector-search.md:39-139 (index definition, parameters, similarity, HNSW, filter fields, quantization)
- skills/mongodb-atlas-expert/references/mongodb-atlas-vector-search.md:140-238 (`$vectorSearch` parameters, ANN vs ENN, score, restrictions)
- skills/mongodb-atlas-expert/references/mongodb-atlas-vector-search.md:239-383 (`$rankFusion`, `$scoreFusion`, sub-pipeline constraints)
- skills/mongodb-atlas-expert/references/mongodb-atlas-vector-search.md:478-492 (chunking), :649-700 (embedding pipelines), :776-851 (Auto Embedding, Search Nodes, sizing formula)
- skills/mongodb-atlas-expert/references/mongodb-atlas-vector-search.md:870-905 (numCandidates tuning), :967-978 (query checklist), :1127-1260 (anti-patterns)
- skills/mongodb-atlas-expert/references/mongodb-search-ai.md:405-420 (index status check), :1039-1065 (mongosh createSearchIndex for vectorSearch), :1151-1165 (limitations)
- skills/mongodb-atlas-expert/references/mongodb-atlas-hybrid-retrieval-frontier-20261001.md:29-60 (fusion semantics, version disagreement for `$scoreFusion`, scoreDetails caveat)
- skills/mongodb-atlas-expert/references/mongodb-atlas-search-nodes.md:632-660 (Search Node minimum counts and limits)
- skills/mongodb-atlas-expert/SKILL.md:438-446 (vector search standards, Auto Embedding preview note)
- skills/atlas-vector-search-pii-isolation/SKILL.md:55-97 (pre-filter is an application-enforced entitlement boundary; shared vs per-tenant index)
