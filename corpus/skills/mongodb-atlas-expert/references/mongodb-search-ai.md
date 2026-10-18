<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-search-ai` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-search-ai
description: "MongoDB search and AI retrieval expert -- Atlas Search (Lucene-based full-text, analyzers, compound queries, facets, scoring, highlighting, autocomplete, synonyms, storedSource/returnStoredSource, scoreDetails/BM25 diagnostics, stableTfl/boolean similarity for pagination), Vector Search (HNSW/IVF indexes, similarity functions, quantization, lexical prefilters, $rankFusion/$scoreFusion hybrid search, ENN vs ANN, 8192 dim limit), and Auto Embedding (Voyage AI integration, autoEmbed field type, voyage-4 model family, automatic chunking, free tier). Covers search node architecture, replication lag monitoring, typeSets dynamic indexing, production sizing, and when-to-use decision guidance."
version: 1.2.0
origin: local
updated: 2026-05-29
triggers:
  - Atlas Search
  - MongoDB full-text search
  - $search operator
  - $searchMeta
  - vector search MongoDB
  - $vectorSearch
  - HNSW index
  - IVF index
  - hybrid search MongoDB
  - $rankFusion
  - $scoreFusion
  - autoEmbed
  - Voyage AI
  - automated embedding
  - MongoDB semantic search
  - faceted search MongoDB
  - Atlas Search analyzers
  - vector quantization MongoDB
  - search nodes
  - MongoDB RAG
  - compound query Atlas Search
  - storedSource
  - returnStoredSource
  - scoreDetails Atlas Search
  - stableTfl
  - mongot replication lag
  - Atlas Search pagination
  - typeSets Atlas Search
keywords:
  - mongodb
  - atlas-search
  - vector-search
  - full-text-search
  - lucene
  - hnsw
  - ivf
  - hybrid-search
  - rankfusion
  - scorefusion
  - autoembed
  - voyage-ai
  - embedding
  - semantic-search
  - rag
  - search-nodes
  - quantization
  - facets
  - analyzers
  - compound-query
  - stored-source
  - score-details
  - bm25
  - stable-tfl
  - type-sets
  - replication-lag
  - enn
  - ann
related_skills:
  - mongodb-expert
  - mongodb-atlas-expert
  - mongodb-developer
  - mongodb-performance-troubleshooting
  - ai-datastores
  - llm-models
---

# MongoDB Search and AI Retrieval: Atlas Search, Vector Search, and Auto Embedding

> Comprehensive reference for building search and AI retrieval systems on MongoDB Atlas.
> Covers full-text search (Atlas Search), semantic similarity (Vector Search),
> automated embedding generation (Auto Embedding with Voyage AI), and hybrid patterns
> that combine all three.

---

## 1. Atlas Search (Lucene-Based Full-Text Search)

### 1.1 Architecture

Atlas Search is powered by Apache Lucene and runs as a dedicated **mongot** process alongside every **mongod** node. The mongot process maintains its own inverted indexes, monitors changes through change streams, and executes all `$search` and `$searchMeta` operations. [Source: MongoDB Docs -- Atlas Search Overview](https://www.mongodb.com/docs/atlas/atlas-search/)

Key architectural facts:
- **mongod** handles CRUD, transactions, and WiredTiger storage
- **mongot** handles Lucene-based inverted indexes, HNSW vector graphs, and search execution
- Change streams keep mongot indexes synchronized with mongod data
- On dedicated **Search Nodes**, mongot runs on separate infrastructure for workload isolation

### 1.2 Index Types: Static vs Dynamic Mappings

Atlas Search indexes are defined as JSON documents specifying field mappings:

**Dynamic mappings** (`"dynamic": true`):
- Automatically index all supported field types
- Convenient for prototyping; indexes every string, number, date, boolean, and objectId
- Can be scoped with `typeSets` to auto-index only specific BSON types (2025+). Example: `"typeSets": ["string", "date"]` restricts dynamic indexing to those types, shrinking index size while retaining auto-discovery for the configured types.

**Static mappings** (`"dynamic": false`):
- Explicitly declare which fields to index and how
- Required for `autocomplete`, `stringFacet`/`numberFacet`, and custom analyzer configurations — these field types **cannot** be used with dynamic mapping
- Better for production — smaller indexes, predictable behavior, no surprise indexing of new fields

```json
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "title": {
        "type": "string",
        "analyzer": "lucene.standard"
      },
      "description": {
        "type": "string",
        "analyzer": "lucene.english",
        "searchAnalyzer": "lucene.english"
      },
      "category": {
        "type": "stringFacet"
      },
      "price": {
        "type": "numberFacet"
      },
      "titleAutocomplete": {
        "type": "autocomplete",
        "tokenization": "edgeGram",
        "minGrams": 2,
        "maxGrams": 15
      }
    }
  }
}
```

[Source: MongoDB Docs -- Define Field Mappings](https://www.mongodb.com/docs/atlas/atlas-search/define-field-mappings/)

### 1.3 Analyzers

An analyzer processes text through three stages: **character filters** -> **tokenizer** -> **token filters**.

**Built-in analyzers:**

| Analyzer | Behavior | Use Case |
|---|---|---|
| `lucene.standard` | Splits on word boundaries, lowercases, strips punctuation | Default; language-neutral |
| `lucene.simple` | Splits on non-letter characters, lowercases | Basic text matching |
| `lucene.whitespace` | Splits on whitespace only | Case-sensitive, preserves punctuation |
| `lucene.keyword` | Treats entire input as a single token | Exact match on full field value |
| `lucene.english` | Standard + English stemming + stop words | English-language content |
| `lucene.french`, `lucene.german`, etc. | Language-specific stemming and stop words | Localized content |

[Source: MongoDB Docs -- Standard Analyzer](https://www.mongodb.com/docs/atlas/atlas-search/analyzers/standard/)

**Custom analyzers** combine:

- **Tokenizers**: `standard`, `keyword`, `whitespace`, `edgeGram`, `nGram`, `regexCaptureGroup`, `uaxUrlEmail`
- **Character filters**: `htmlStrip`, `mapping`, `icuNormalize`, `persian`
- **Token filters**: `lowercase`, `stopword`, `stemmer`, `shingle`, `snowballStemming`, `regex`, `trim`, `edgeGram`, `nGram`, `icuFolding`, `icuNormalize`, `length`, `reverseString`, `wordDelimiterGraph`

```json
{
  "analyzers": [
    {
      "name": "htmlStripAnalyzer",
      "charFilters": [{ "type": "htmlStrip" }],
      "tokenizer": { "type": "standard" },
      "tokenFilters": [
        { "type": "lowercase" },
        { "type": "stopword", "tokens": ["the", "a", "an"] }
      ]
    }
  ]
}
```

[Source: MongoDB Docs -- Custom Analyzers](https://www.mongodb.com/docs/atlas/atlas-search/analyzers/custom/)
[Source: MongoDB Docs -- Tokenizers](https://www.mongodb.com/docs/atlas/atlas-search/analyzers/tokenizers/)

### 1.4 Search Operators (`$search`)

The `$search` aggregation stage must be the first stage in a pipeline. Key operators:

| Operator | Purpose |
|---|---|
| `text` | Full-text search with analyzer processing |
| `phrase` | Ordered sequence of terms |
| `wildcard` | Pattern matching with `*` and `?` |
| `regex` | Regular expression matching |
| `autocomplete` | Prefix/edge-ngram completion |
| `range` | Numeric or date range queries |
| `near` | Proximity-based scoring for numbers/dates/geo |
| `exists` | Documents where field is present |
| `equals` | Exact match for boolean, objectId, date, number, string, UUID |
| `moreLikeThis` | Find documents similar to input documents |
| `queryString` | Lucene query parser syntax |
| `geoShape` / `geoWithin` | Geospatial queries |
| `in` | Match any value in an array |
| `compound` | Combine multiple operators (see below) |
| `facet` | Faceted search collector |

[Source: MongoDB Docs -- Operators and Collectors](https://www.mongodb.com/docs/atlas/atlas-search/operators-and-collectors/)

### 1.5 Compound Queries

The `compound` operator is the primary way to build complex search logic. It provides four clause types:

| Clause | Required to Match? | Affects Score? | Purpose |
|---|---|---|---|
| `must` | Yes | Yes | Required conditions that influence ranking |
| `mustNot` | Excludes matches | No | Exclude documents matching these conditions |
| `should` | No | Yes | Optional conditions that boost score when matched |
| `filter` | Yes | No | Required conditions that do NOT affect score |

```javascript
db.products.aggregate([
  {
    $search: {
      compound: {
        must: [
          { text: { query: "wireless headphones", path: "title" } }
        ],
        should: [
          {
            text: {
              query: "noise cancelling",
              path: "description",
              score: { boost: { value: 2.0 } }
            }
          }
        ],
        filter: [
          { range: { path: "price", gte: 50, lte: 300 } }
        ],
        mustNot: [
          { text: { query: "refurbished", path: "condition" } }
        ]
      },
      highlight: { path: ["title", "description"] }
    }
  },
  { $limit: 20 },
  {
    $project: {
      title: 1,
      price: 1,
      score: { $meta: "searchScore" },
      highlights: { $meta: "searchHighlights" }
    }
  }
])
```

**Scoring customization options:**
- `boost`: Multiply the score by a constant or field value
- `constant`: Replace the score with a fixed value
- `function`: Compute score using `log1p`, `add`, `multiply`, `path`, `score`, `gauss`, etc.

[Source: MongoDB Docs -- compound Operator](https://www.mongodb.com/docs/atlas/atlas-search/compound/)
[Source: MongoDB Docs -- Customize Score](https://www.mongodb.com/docs/atlas/atlas-search/tutorial/compound-query-custom-score/)

### 1.6 Similarity Algorithms (Scoring)

By default, the `text`, `phrase`, `queryString`, and `autocomplete` operators use **BM25** to score documents. Two additional algorithms were added in 2025 for deployments with dedicated Search Nodes that paginate by relevance score:

| Algorithm | Description | Best For |
|---|---|---|
| `bm25` | Term frequency × inverse document frequency; default | General relevance ranking |
| `stableTfl` | Uses term length to derive rarity; produces **consistent scores across replicas** | Pagination on Search Nodes; secondary/nearest read preference |
| `boolean` | Counts how many query terms appear; no TF/IDF weighting | Consistent ordering when BM25 variance causes page-boundary drift |

**Why this matters:** On multi-node Search Node deployments (or with `readPreference: nearest`), BM25 scores can vary slightly between nodes because IDF is computed per-node. If your UI sorts results by `searchScore` and paginates, you may see documents shuffle between pages. Setting `similarity.type` to `stableTfl` or `boolean` in the index definition forces deterministic, cross-node consistent scores.

**Index configuration:**
```json
{
  "mappings": {
    "fields": {
      "title": {
        "type": "string",
        "similarity": {
          "type": "stableTfl"
        }
      }
    }
  }
}
```

[Source: MongoDB -- New Scoring Options for Consistent Pagination on Search Nodes](https://www.mongodb.com/products/updates/new-scoring-options-for-consistent-pagination-on-search-nodes/)

### 1.7 Faceted Search

Facets group search results by field values or ranges, typically used for sidebar filter UIs.

```javascript
// Use $searchMeta for metadata-only results (no documents returned)
db.products.aggregate([
  {
    $searchMeta: {
      facet: {
        operator: {
          text: { query: "laptop", path: "title" }
        },
        facets: {
          brandFacet: {
            type: "string",
            path: "brand",
            numBuckets: 10
          },
          priceFacet: {
            type: "number",
            path: "price",
            boundaries: [0, 500, 1000, 2000, 5000]
          }
        }
      }
    }
  }
])
```

Returns buckets with `_id` and `count` for each group. Use `$searchMeta` when you need only facet counts (e.g., rendering filter sidebar without loading full documents).

[Source: MongoDB Docs -- facet](https://www.mongodb.com/docs/atlas/atlas-search/facet/)

### 1.8 Highlighting, Autocomplete, and Synonyms

**Highlighting** returns text snippets with matched terms:
- Specify `highlight: { path: [...] }` in the `$search` stage
- Access via `$meta: "searchHighlights"` in `$project`
- Each highlight has `type: "hit"` (matched text) or `type: "text"` (surrounding context)
- Configure `maxNumPassages` and `maxCharsToExamine` to control highlight extraction cost

**Autocomplete** requires a field mapped as `type: "autocomplete"`:
- Tokenization: `edgeGram` (prefix) or `nGram` (substring)
- Configure `minGrams`, `maxGrams`, and `foldDiacritics`
- Use the `autocomplete` operator in `$search`

**Synonyms** enable query expansion:
- Define synonym mappings in a dedicated MongoDB collection **on the same cluster**
- Reference the synonym source in the search index definition
- Supports `equivalent` (bidirectional) and `explicit` (one-directional) mappings
- Required schema: `{ mappingType: "equivalent"|"explicit", synonyms: [...], input: [...], output: [...] }`

[Source: MongoDB Docs -- Atlas Search Highlighting](https://www.mongodb.com/docs/atlas/atlas-search/highlighting/)
[Source: OneUpTime -- Atlas Search Full-Text](https://oneuptime.com/blog/post/2026-03-31-mongodb-atlas-search-full-text/view)

### 1.9 Score Details and Search Diagnostics

Use `scoreDetails: true` in the `$search` stage to get a full BM25 score breakdown per document — invaluable for debugging relevance.

```javascript
db.products.aggregate([
  {
    $search: {
      index: "default",
      text: { query: "wireless headphones", path: "title" },
      scoreDetails: true
    }
  },
  {
    $project: {
      title: 1,
      score: { $meta: "searchScore" },
      details: { $meta: "searchScoreDetails" }
    }
  }
])
```

The `searchScoreDetails` result shows the BM25 components:

```json
{
  "value": 4.23,
  "description": "sum of:",
  "details": [
    {
      "value": 4.23,
      "description": "weight(title:wireless in 42), result of:",
      "details": [
        { "value": 3.1, "description": "idf, computed as log(1 + (N - n + 0.5) / (n + 0.5))" },
        { "value": 1.36, "description": "tf, computed as freq / (freq + k1 * (1 - b + b * dl / avgdl))" }
      ]
    }
  ]
}
```

**Key diagnostics:**
- **idf** (inverse document frequency): high = rare term, more discriminating
- **tf** (term frequency): how often the term appears in the document
- Low score + high idf = term is rare but not present enough; consider lowering `boost`
- Low score + low idf = term is too common; add to a stop-word filter or use `mustNot`

**Explain for `$vectorSearch`** — use `db.collection.explain("executionStats").aggregate([{ $vectorSearch: ... }])`. The explain output includes a `stats` field with time spent in each stage, `numCandidatesConsidered`, and `numDocumentsReturned`.

**Index status check:**
```javascript
db.collection.getSearchIndexes()
// Returns: { name, status: "READY"|"BUILDING"|"STALE", queryable, latestDefinition }
```

Monitor replication lag via the Atlas UI alert **"Search Max Replication Lag"**. If lag grows until mongot falls outside the oplog window, Atlas triggers a full index rebuild — search continues on stale results during the rebuild. Mitigation: increase oplog size, scale up Search Nodes, or throttle bulk write bursts.

> **8.0.14+ behavior change:** `scoreDetails` and `returnStoredSource` must be explicitly `true` or `false`. Passing `null` for either option causes the query to fail.

[Source: MongoDB Docs -- Return Score Details](https://www.mongodb.com/docs/atlas/atlas-search/score/get-details/)
[Source: MongoDB Docs -- Monitor Atlas Search](https://www.mongodb.com/docs/atlas/atlas-search/monitoring/)
[Source: MongoDB Docs -- Explain Vector Search](https://www.mongodb.com/docs/atlas/atlas-vector-search/explain/)

### 1.10 Stored Source (Performance Optimization)

By default, every `$search` result triggers a secondary fetch from mongod to retrieve document fields (the `$_internalSearchIdLookup` stage). **Stored Source** eliminates this round-trip for the fields you specify by storing them directly on mongot.

**Index definition — configure `storedSource`:**
```json
{
  "mappings": { "dynamic": false, "fields": { "title": { "type": "string" } } },
  "storedSource": {
    "include": ["title", "price", "category", "thumbnailUrl"]
  }
}
```

Use `"storedSource": true` to store all fields, or `{ "exclude": ["largeField"] }` to store all except specific fields.

**Query — set `returnStoredSource: true`:**
```javascript
db.products.aggregate([
  {
    $search: {
      index: "product_index",
      text: { query: "bluetooth speaker", path: "title" },
      returnStoredSource: true   // skip mongod fetch; use stored fields
    }
  },
  { $limit: 20 }
])
```

**When to use Stored Source:**
- Search result cards only need a subset of fields (title, thumbnail, price)
- Full documents are large (>10KB) and fetching them adds measurable latency
- You want to reduce read load on primary/secondary mongod nodes
- High-throughput search workloads where the `$_internalSearchIdLookup` stage is a bottleneck

**Requirements and caveats:**
- Requires MongoDB 7.0+ on Atlas
- Stored fields are a snapshot — they reflect the document at index-sync time, not real-time. For fields that change frequently, weigh staleness risk against latency gain.
- Starting with MongoDB 8.0.14: `returnStoredSource` must be `true` or `false`; `null` causes query failure
- Nested fields in arrays of objects are supported (as of 2026)

[Source: MongoDB Docs -- Define Stored Source Fields](https://www.mongodb.com/docs/atlas/atlas-search/stored-source-definition/)
[Source: MongoDB Docs -- Return Stored Source Fields](https://www.mongodb.com/docs/atlas/atlas-search/return-stored-source/)

### 1.11 Search Nodes (Dedicated Infrastructure)

Search Nodes separate the mongot process onto dedicated infrastructure:

- **Workload isolation**: mongot memory and CPU no longer compete with mongod
- **Independent scaling**: add more search nodes without scaling the database tier
- **Memory-optimized**: purpose-built for Lucene indexes and HNSW graphs
- **Multi-region**: available on AWS (GA), Google Cloud (GA), and Azure
- **Asymmetric scaling**: scale search capacity independently of transactional capacity

Use Search Nodes when:
- Search workloads cause resource contention with CRUD operations
- You need to scale search throughput independently
- Vector search indexes are large and require dedicated memory
- You want predictable search latency under mixed workloads

[Source: MongoDB Blog -- Dedicated Search Nodes and Vector Search GA](https://www.mongodb.com/company/blog/product-release-announcements/dedicated-search-nodes-vector-search-now-in-general-availability)
[Source: MongoDB Blog -- Search Nodes Public Preview](https://www.mongodb.com/company/blog/product-release-announcements/search-nodes-now-public-preview-performance-scale-dedicated-infrastructure)

---

## 2. MongoDB Vector Search

### 2.1 Overview

MongoDB Atlas Vector Search enables semantic similarity search using dense vector embeddings stored directly in MongoDB documents. It uses the `$vectorSearch` aggregation stage and supports approximate nearest neighbor (ANN) search through HNSW and IVF algorithms.

[Source: MongoDB Docs -- Vector Search Overview](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/)

### 2.2 Index Types

**HNSW (Hierarchical Navigable Small Worlds)** -- default and recommended:
- Graph-based algorithm with hierarchical layers
- Sub-linear time complexity for ANN search
- Higher layers are sparse for fast global navigation; lower layers are dense for precise local search
- Parameters:
  - `m` -- max edges per node (default 16; higher = more accurate but more memory)
  - `efConstruction` -- search width during build (default 64; higher = slower build, better graph quality)

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    }
  ]
}
```

**IVF (Inverted File Index)**:
- Partitions the vector space into clusters (Voronoi cells)
- Faster build time than HNSW for very large datasets
- Parameters:
  - `numLists` -- number of clusters (start with sqrt(numVectors))
  - `numCandidates` at query time controls how many clusters to probe

[Source: OneUpTime -- Tune HNSW Parameters](https://oneuptime.com/blog/post/2026-03-31-mongodb-tune-hnsw-vector-search/view)
[Source: DataCamp -- Vector Search in MongoDB Guide](https://www.datacamp.com/tutorial/vector-search-in-mongodb-guide)

### 2.3 Similarity Functions

| Function | Formula | Best For |
|---|---|---|
| `cosine` | 1 - cosine_distance | Normalized embeddings (most common for text) |
| `euclidean` | 1 / (1 + euclidean_distance) | When magnitude matters |
| `dotProduct` | (1 + dotProduct) / 2 | Pre-normalized unit vectors; fastest computation |

Choose `cosine` as the default for text embeddings. Use `dotProduct` when vectors are already L2-normalized for a performance gain. Use `euclidean` when absolute distances (not just angles) are meaningful.

### 2.4 The `$vectorSearch` Stage

```javascript
db.articles.aggregate([
  {
    $vectorSearch: {
      index: "vector_index",
      path: "embedding",
      queryVector: [0.12, -0.34, ...],  // 1536-dim vector (max 8192 dims)
      numCandidates: 200,
      limit: 10,
      filter: {
        category: { $eq: "technology" },
        publishedDate: { $gte: ISODate("2025-01-01") }
      }
    }
  },
  {
    $project: {
      title: 1,
      summary: 1,
      score: { $meta: "vectorSearchScore" }
    }
  }
])
```

**Key parameters:**
- `numCandidates`: How many candidates the HNSW graph explores. Rule of thumb: set to at least **20x the limit** for 90%+ recall. Higher values improve recall at the cost of latency. **Not applicable when `exact: true`.**
- `limit`: Maximum documents returned
- `filter`: Pre-filter using exact match on boolean, date, objectId, numeric, string, UUID fields (including arrays)
- `exact`: Set to `true` for Exact Nearest Neighbor (ENN) search — exhaustively compares all indexed vectors, always returns the true nearest neighbors. Useful for small datasets (<100K vectors), multi-tenant scenarios, or recall benchmarking. When `exact: true`, omit `numCandidates`.
- `queryString`: Used **only with `autoEmbed` indexes** — pass plain text and the index's configured model generates the embedding at query time. Do not use `queryString` with manually managed vector indexes; use `queryVector` instead. (See Section 4.4.)

[Source: MongoDB Docs -- Run Vector Search Queries](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-stage/)

### 2.5 Lexical Prefilters for Vector Search

> **Preview feature:** Lexical prefilters were in preview as of 2025. The syntax below shows the directional API shape — always verify against the [latest MongoDB docs](https://www.mongodb.com/docs/atlas/atlas-search/operators-collectors/vectorsearch/) before using in production, as GA syntax may differ.

Standard `$vectorSearch` filters support only basic operators (equals, range, exists). **Lexical prefilters** extend this with analyzed text capabilities:

- Fuzzy search (typo-tolerant)
- Phrase matching
- Wildcard pattern matching
- Location/geo filtering
- queryString (Lucene syntax)

Lexical prefilters use the `vectorSearch` operator within the `$search` aggregation stage (not `$vectorSearch`), enabling Lucene text analysis as a pre-filtering step before vector similarity ranking.

```javascript
// Lexical prefilter: fuzzy text match BEFORE vector similarity
db.articles.aggregate([
  {
    $search: {
      vectorSearch: {
        vector: queryEmbedding,
        path: "embedding",
        similarity: "cosine",
        limit: 10,
        numCandidates: 200,
        filter: {
          text: {
            query: "performnce tuning",   // typo-tolerant via fuzzy
            path: "tags",
            fuzzy: { maxEdits: 1 }
          }
        }
      }
    }
  }
])
```

[Source: MongoDB Blog -- Semantic Power, Lexical Precision](https://www.mongodb.com/company/blog/product-release-announcements/semantic-power-lexical-precision-advanced-filtering-for-vector-search)

### 2.6 Vector Quantization

Quantization reduces vector memory footprint while preserving search quality. GA as of April 2025.

| Type | Compression | Memory Savings | Recall Impact |
|---|---|---|---|
| **Scalar** | float32 -> int8 | 4x reduction | Minimal; high baseline recall |
| **Binary** | float32 -> 1-bit | 32x reduction | Requires more numCandidates + automatic rescoring |

**Configuration** -- add `quantization` to the vector index definition:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine",
      "quantization": "scalar"
    }
  ]
}
```

**Binary quantization rescoring**: When using `"quantization": "binary"`, Atlas Vector Search automatically performs a rescoring step, re-ranking top binary results using their full-precision vector counterparts. This requires higher `numCandidates` to achieve 90-95% recall (with corresponding latency trade-off).

**Production benchmarks** (15.3M vectors, voyage-3-large at 2048 dimensions):
- Scalar or binary quantization retains 90-95% accuracy
- Query latency under 50ms
- When combined with Search Nodes, further cost reduction and performance improvement

[Source: MongoDB Blog -- Vector Quantization GA](https://www.mongodb.com/company/blog/product-release-announcements/vector-quantization-scale-search-generative-ai-applications)
[Source: MongoDB Blog -- Scaling Vector Search with Quantization](https://www.mongodb.com/company/blog/technical/scaling-vector-search-mongodb-atlas-quantization-voyage-ai-embeddings)
[Source: MongoDB Blog -- Binary Quantization Rescoring](https://www.mongodb.com/company/blog/product-release-announcements/binary-quantization-rescoring-96-less-memory-faster-search)

### 2.7 Search Score Details

Use `$meta: "vectorSearchScore"` to access the similarity score for each result. Score ranges depend on the similarity function:
- `cosine`: 0 to 1 (1 = identical)
- `euclidean`: 0 to 1 (1 = identical, approaches 0 for distant vectors)
- `dotProduct`: 0 to 1 when vectors are L2-normalized; for non-normalized vectors, scores can exceed 1 or go negative -- always normalize your embeddings when using dotProduct similarity

### 2.8 Production Sizing Guidelines

| Factor | Guidance |
|---|---|
| **Index type** | HNSW for most workloads; IVF if build time is critical |
| **Dimensions** | Higher dims = more memory; consider quantization above 1024 dims |
| **numCandidates** | 20x limit for 90%+ recall; tune up for binary quantization |
| **Quantization** | Scalar for quality-sensitive; binary for cost-sensitive at scale |
| **Search Nodes** | Use when vector indexes exceed available RAM on database nodes |
| **Cluster tier** | M10+ for production; M0/Flex for development and prototyping |
| **Scaling** | Scale out search nodes or increase vCPUs for throughput bottlenecks |

[Source: MongoDB Docs -- Vector Search Benchmark Results](https://www.mongodb.com/docs/atlas/atlas-vector-search/benchmark/results/)

---

## 3. Hybrid Search: Combining Full-Text and Vector

### 3.1 Why Hybrid Search

Neither full-text nor vector search alone is optimal for all queries:
- **Full-text (BM25)**: Excels at exact keyword matches, product codes, rare terms, typo tolerance
- **Vector (kNN)**: Excels at semantic intent, synonyms, concept matching, multilingual similarity

Hybrid search combines both, delivering the precision of keywords with the recall of semantics.

**When hybrid adds measurable value vs. when to keep it simple:**

| Scenario | Recommendation |
|---|---|
| Queries are keyword-heavy (product codes, IDs, names) | Atlas Search alone — hybrid adds latency with no gain |
| Queries are intent/meaning-heavy ("how do I fix X?") | Vector Search alone — full-text adds noise |
| Mixed query types (e-commerce, docs, knowledge bases) | Hybrid — the typical case where it pays off |
| Dataset < 10K documents | Vector ENN alone is fast enough; skip hybrid overhead |
| Low-latency SLA (< 20ms) | Profile hybrid pipeline first; `$rankFusion` adds ~5–15ms |

Start with `$rankFusion` (simpler, no tuning), measure relevance vs. latency, then consider `$scoreFusion` only if you need per-query weight control.

### 3.2 `$rankFusion` (Reciprocal Rank Fusion)

Available on MongoDB 8.0+. Combines ranked lists from `$search` and `$vectorSearch` using the RRF algorithm. Easier to get started -- no score normalization needed.

```javascript
db.articles.aggregate([
  {
    $rankFusion: {
      input: {
        pipelines: {
          fullText: [
            {
              $search: {
                text: { query: "machine learning optimization", path: "content" }
              }
            }
          ],
          semantic: [
            {
              $vectorSearch: {
                index: "vector_index",
                path: "embedding",
                queryVector: [0.12, -0.34, ...],
                numCandidates: 200,
                limit: 50
              }
            }
          ]
        }
      }
    }
  },
  { $limit: 10 },
  {
    $project: {
      title: 1,
      score: { $meta: "score" }
    }
  }
])
```

RRF calculates: `score = SUM(1 / (k + rank_i))` across all pipelines, where `k` is a constant (default 60) that dampens the impact of high-ranking outliers.

[Source: MongoDB Community -- Announcing $rankFusion](https://www.mongodb.com/community/forums/t/announcing-hybrid-search-support-via-rankfusion/324476)
[Source: MongoDB Blog -- Harness Power of $rankFusion](https://www.mongodb.com/company/blog/technical/harness-power-atlas-search-vector-search-with-rankfusion)

### 3.3 `$scoreFusion` (Weighted Score Fusion)

Available on MongoDB 8.2+. Normalizes scores from sub-pipelines and combines them via weighted mathematical expressions. Offers finer control than `$rankFusion`.

**Normalization options:**
- `none` -- use raw scores as-is
- `sigmoid` -- apply sigmoid function for bounded output
- `minMaxScaler` -- normalize to 0-1 range based on min/max scores

**Combination** defaults to `average` of normalized scores; weights control each pipeline's contribution.

```javascript
db.articles.aggregate([
  {
    $scoreFusion: {
      input: {
        pipelines: {
          fullText: [
            {
              $search: {
                text: { query: "machine learning optimization", path: "content" }
              }
            }
          ],
          semantic: [
            {
              $vectorSearch: {
                index: "vector_index",
                path: "embedding",
                queryVector: [0.12, -0.34, ...],
                numCandidates: 200,
                limit: 50
              }
            }
          ]
        }
      },
      normalization: "minMaxScaler",
      weights: {
        fullText: 0.4,
        semantic: 0.6
      }
    }
  },
  { $limit: 10 }
])
```

**When to use which:**
- `$rankFusion` -- simpler, no tuning needed, good baseline
- `$scoreFusion` -- when you need per-query weight adjustment, score transparency, or different normalization strategies

[Source: MongoDB Docs -- $scoreFusion aggregation](https://www.mongodb.com/docs/manual/reference/operator/aggregation/scorefusion/)
[Source: MongoDB Blog -- Native Hybrid Search with $scoreFusion](https://www.mongodb.com/company/blog/product-release-announcements/boost-search-relevance-mongodb-atlas-native-hybrid-search)

### 3.4 Hybrid Search Patterns

**Pattern 1: E-commerce product search**
- Full-text for product name/SKU exact matching
- Vector search for "find similar" by description embedding
- `$rankFusion` for balanced results

**Pattern 2: Knowledge base / documentation**
- Vector search weighted higher (0.7) for intent understanding
- Full-text weighted lower (0.3) for catching specific error codes or API names
- `$scoreFusion` with `minMaxScaler`

**Pattern 3: RAG retrieval pipeline**
- Vector search for semantic document retrieval
- Full-text as a secondary signal for keyword grounding
- Filter by metadata (date, source, category) in both sub-pipelines

**Best practice**: There is no universal weight ratio. Tune weights per query type; some queries benefit more from vector similarity, others from exact keyword matching. Start with equal weights and adjust based on relevance testing.

[Source: MongoDB Docs -- Hybrid Search](https://www.mongodb.com/docs/atlas/atlas-vector-search/hybrid-search/)
[Source: MongoDB Docs -- Vector Search with Full-Text Search](https://www.mongodb.com/docs/atlas/atlas-vector-search/hybrid-search/vector-search-with-full-text-search/)

> **Securing search/AI for regulated (FSI/PII) data:** entitlement-filtering a
> RAG corpus, tenant/PII isolation, and the encryption-vs-searchable-vector
> constraint are covered in the `atlas-vector-search-pii-isolation` skill;
> prompt-injection defense for the LLM layer in `rag-prompt-injection-defense`;
> why the stored embedding is itself sensitive in `embedding-inversion-threat-model`;
> and bank model-risk/governance in `bank-genai-model-risk-governance`.

---

## 4. Auto Embedding (Voyage AI Integration)

### 4.1 Overview

Automated Embedding was in **public preview** as of May 2026, eliminating the need for external embedding pipelines. MongoDB Vector Search automatically generates, stores, and queries text embeddings using Voyage AI models through the `autoEmbed` field type. Available on MongoDB 8.3+.

> **Check current status:** As of the skill's last update (2026-05-28), Auto Embedding is in public preview. Verify GA status, pricing, and rate limits at [mongodb.com/docs](https://www.mongodb.com/docs/atlas/atlas-vector-search/crud-embeddings/create-embeddings-automatic/) before relying on it in production SLAs.

[Source: MongoDB Blog -- Unlocking AI Search: Introducing Automated Embedding](https://www.mongodb.com/company/blog/product-release-announcements/unlocking-ai-search-introducing-automated-embedding-in-mongodb-vector-search)

### 4.2 Supported Embedding Models

| Model | Dimensions | Context | Best For |
|---|---|---|---|
| `voyage-4-large` | 2048 | 32K tokens | Highest accuracy; production RAG |
| `voyage-4` | 1536 | 32K tokens | Balanced accuracy and cost |
| `voyage-4-lite` | 512 | 32K tokens | Low-latency, cost-efficient |
| `voyage-code-3` | 1024 | 16K tokens | Source code and technical docs |

All Voyage 4 series models share a **compatible embedding space**, meaning you can mix and match models (e.g., embed with voyage-4-large, query with voyage-4-lite) with acceptable accuracy trade-offs.

[Source: MongoDB Docs -- Voyage AI Text Embeddings](https://www.mongodb.com/docs/voyageai/models/text-embeddings/)
[Source: PR Newswire -- Voyage 4 Models](https://www.prnewswire.com/news-releases/mongodb-sets-a-new-standard-for-retrieval-accuracy-voyage-4-models-for-production-ready-ai-applications-302662558.html)

### 4.3 Index Configuration with `autoEmbed`

```json
{
  "name": "auto_embed_index",
  "type": "vectorSearch",
  "definition": {
    "fields": [
      {
        "type": "autoEmbed",
        "path": "description",
        "model": "voyage-4",
        "modality": "text"
      }
    ]
  }
}
```

**How it works:**
1. **Index creation**: MongoDB reads existing documents and generates embeddings for the specified text field via Voyage AI
2. **Document inserts/updates**: Embeddings are automatically regenerated when the source text field changes
3. **Query time**: Text queries are automatically embedded using the same model before vector search
4. Embeddings stay synchronized as underlying data changes -- no external pipeline needed

[Source: MongoDB Docs -- Automatically Generate Vector Embeddings](https://www.mongodb.com/docs/atlas/atlas-vector-search/crud-embeddings/create-embeddings-automatic/)
[Source: MongoDB Docs -- Automated Embedding Overview](https://www.mongodb.com/docs/vector-search/crud-embeddings/automated-embedding/)

### 4.4 Querying with Auto Embedding

With autoEmbed, you query using plain text -- no need to generate embeddings client-side:

```javascript
db.articles.aggregate([
  {
    $vectorSearch: {
      index: "auto_embed_index",
      path: "description",
      queryString: "how to optimize database performance",
      numCandidates: 150,
      limit: 10
    }
  }
])
```

The embedding model specified in the index definition automatically converts the query string to a vector before executing the search.

### 4.5 Free Tier and Pricing

- **Free tier**: 200M tokens across Voyage AI models with no credit card required
- **Cluster support**: M0 (free tier), Flex, and dedicated (M10+) clusters
- **Preview status**: Pricing and edge-case behavior subject to change before GA

### 4.6 Auto Embedding in Community Edition

As of May 2026, Automated Embedding is also available in **MongoDB Community Edition** (public preview), extending these capabilities beyond Atlas-only deployments.

[Source: MongoDB -- Automated Embedding in Community Edition](https://www.mongodb.com/products/updates/now-in-public-preview-automated-embedding-in-vector-search-in-community-edition/)

### 4.7 Automatic Chunking

For long documents, Auto Embedding handles chunking automatically, splitting text into appropriately sized segments for the selected model's context window. This eliminates the need for custom chunking logic in the application layer.

[Source: TLD Recap -- Auto Embedding in Vector Search](https://tldrecap.tech/posts/2026/mongodb-local-sf/mongodb-automated-embedding-search/)

---

## 5. Decision Guide: When to Use What

### 5.1 Feature Selection Matrix

| Requirement | Atlas Search | Vector Search | Auto Embedding | Hybrid |
|---|---|---|---|---|
| Keyword/exact match | Yes | No | No | Yes |
| Semantic similarity | No | Yes | Yes | Yes |
| Typo tolerance/fuzzy | Yes | No | No | Yes |
| Faceted navigation | Yes (requires static mapping + stringFacet/numberFacet field types) | No | No | Yes (via $search sub-pipeline) |
| No embedding pipeline | Yes | No | Yes | Partial (auto embed covers vector side) |
| Multi-language | With analyzers | With multilingual model | With Voyage 4 models | Yes |
| Product code/SKU | Yes | No | No | Yes |
| "Find similar" | Limited | Yes | Yes | Yes |
| RAG retrieval | Limited | Yes | Yes | Yes (recommended) |

### 5.2 Decision Flowchart

1. **Users search by keywords/filters only?** -> Atlas Search
2. **Users search by meaning/intent?** -> Vector Search (or Auto Embedding if you want zero-pipeline)
3. **Both keywords and meaning matter?** -> Hybrid with `$rankFusion` or `$scoreFusion`
4. **Need faceted navigation + semantic results?** -> Hybrid with Atlas Search facets in the full-text sub-pipeline
5. **Building RAG for LLM?** -> Vector Search (or Auto Embedding) with metadata filters; optionally hybrid for keyword grounding
6. **Want to avoid managing embeddings?** -> Auto Embedding with Voyage AI

### 5.3 Version Requirements Summary

| Feature | Minimum Version | Notes |
|---|---|---|
| Atlas Search | MongoDB 4.2+ on Atlas | |
| Stored Source (`storedSource`) | MongoDB 7.0+ on Atlas | |
| Vector Search (`$vectorSearch`) | MongoDB 7.0+ on Atlas | |
| `$rankFusion` | MongoDB 8.0+ | |
| `$scoreFusion` | MongoDB 8.2+ | |
| Vector Quantization (GA) | April 2025+ | Scalar and binary |
| `stableTfl` / `boolean` similarity | 2025+ | For consistent pagination on Search Nodes |
| `typeSets` dynamic indexing | 2025+ | Restricts auto-index to specified BSON types |
| Vector dimension limit | Up to 8192 dims | Increased from 4096 in 2025 |
| `returnStoredSource` / `scoreDetails` null behavior | MongoDB 8.0.14+ | Must be `true`/`false`; `null` causes query failure |
| Auto Embedding (`autoEmbed`) | MongoDB 8.3+ (May 2026) | Public preview; check current GA status |
| Lexical Prefilters | Preview (2025+) | Verify GA status before production use |
| Views support for `$search` | 2025+ | Create search indexes on standard Views |

---

## 6. Common Patterns and Recipes

### 6.1 RAG Retrieval with Metadata Filtering

```javascript
// Step 1: Generate query embedding (or use autoEmbed)
const queryEmbedding = await generateEmbedding("explain connection pooling");

// Step 2: Vector search with metadata filter
db.knowledge.aggregate([
  {
    $vectorSearch: {
      index: "rag_index",
      path: "embedding",
      queryVector: queryEmbedding,
      numCandidates: 200,
      limit: 5,
      filter: {
        source: { $in: ["docs", "kb-articles"] },
        updatedAt: { $gte: ISODate("2024-01-01") }
      }
    }
  },
  {
    $project: {
      content: 1,
      source: 1,
      score: { $meta: "vectorSearchScore" }
    }
  }
])
```

### 6.2 Autocomplete with Boosted Exact Matches

```javascript
db.products.aggregate([
  {
    $search: {
      compound: {
        should: [
          {
            autocomplete: {
              query: "wire",
              path: "titleAutocomplete",
              fuzzy: { maxEdits: 1 }
            }
          },
          {
            text: {
              query: "wire",
              path: "title",
              score: { boost: { value: 5.0 } }
            }
          }
        ]
      }
    }
  },
  { $limit: 10 },
  { $project: { title: 1, score: { $meta: "searchScore" } } }
])
```

### 6.3 Semantic Search with Auto Embedding (Zero Pipeline)

```javascript
// 1. Create autoEmbed index (one-time)
// Note: createSearchIndex() is a mongosh collection-level method.
// Driver equivalent: collection.createSearchIndex({ name, definition })
db.articles.createSearchIndex({
  name: "semantic_index",
  type: "vectorSearch",
  definition: {
    fields: [
      {
        type: "autoEmbed",
        path: "content",
        model: "voyage-4",
        modality: "text"
      }
    ]
  }
});

// 2. Insert documents -- embeddings generated automatically
db.articles.insertMany([
  { title: "Connection Pooling", content: "Connection pooling reduces..." },
  { title: "Index Strategies", content: "Choosing the right index..." }
]);

// 3. Query with plain text -- embedding generated at query time
db.articles.aggregate([
  {
    $vectorSearch: {
      index: "semantic_index",
      path: "content",
      queryString: "how to reduce database connection overhead",
      numCandidates: 100,
      limit: 5
    }
  }
])
```

### 6.4 Hybrid E-commerce Search

```javascript
db.products.aggregate([
  {
    $rankFusion: {
      input: {
        pipelines: {
          keyword: [
            {
              $search: {
                compound: {
                  must: [
                    { text: { query: userQuery, path: ["title", "brand"] } }
                  ],
                  filter: [
                    { range: { path: "price", gte: minPrice, lte: maxPrice } }
                  ]
                }
              }
            }
          ],
          semantic: [
            {
              $vectorSearch: {
                index: "product_vectors",
                path: "descriptionEmbedding",
                queryVector: queryEmbedding,
                numCandidates: 200,
                limit: 50,
                filter: {
                  inStock: { $eq: true }
                }
              }
            }
          ]
        }
      }
    }
  },
  { $limit: 20 }
])
```

---

## 7. Operational Checklist

### Pre-production

- [ ] Choose static mappings for Atlas Search indexes in production
- [ ] Set appropriate analyzers per field (language-specific where applicable)
- [ ] Configure `numCandidates` >= 20x limit for vector search
- [ ] Evaluate quantization (scalar or binary) for large vector datasets
- [ ] Test hybrid search weight ratios with representative queries
- [ ] Provision Search Nodes if search workload is significant

### Monitoring

- [ ] Track `mongot` memory and CPU usage
- [ ] Monitor search latency percentiles (p50, p95, p99)
- [ ] Watch for index sync lag between mongod and mongot
- [ ] Set alerts on search error rates
- [ ] Review vector search recall metrics periodically

### Cost optimization

- [ ] Use scalar quantization to reduce vector memory 4x
- [ ] Use binary quantization for 32x memory savings where recall trade-off is acceptable
- [ ] Consider Auto Embedding free tier (200M tokens) before building custom pipelines
- [ ] Right-size Search Nodes independently of database tier
- [ ] Use Voyage 4 lite for cost-sensitive workloads with acceptable accuracy

---

## 8. Limitations and Gotchas

- **`$search` must be the first stage** in an aggregation pipeline. You cannot place `$match` or other stages before it. Use `compound.filter` for pre-search filtering instead.
- **`$vectorSearch` must also be the first stage** when used standalone (outside `$rankFusion`/`$scoreFusion`).
- **Index build time is not instant.** Large collections can take minutes to hours for initial index sync. Monitor index status via `db.collection.getSearchIndexes()`.
- **Eventual consistency.** The mongot process syncs from mongod via change streams, so there is a brief lag (typically sub-second, but can be longer under load) before newly written documents appear in search results.
- **Atlas-only for most features.** Atlas Search, Vector Search, and Auto Embedding require MongoDB Atlas (or Atlas-compatible environments). The Community Edition autoEmbed preview is an exception but is limited in scope.
- **`$rankFusion`/`$scoreFusion` version requirements.** These stages are not available on MongoDB < 8.0 / < 8.2 respectively. On older versions, implement hybrid search client-side by running two pipelines and merging results.
- **numCandidates is not limit.** Setting `numCandidates` equal to `limit` will produce poor recall. Always use numCandidates >= 20x limit.
- **Quantization trade-offs.** Binary quantization (32x savings) requires automatic rescoring and higher numCandidates; do not assume it is a free optimization.
- **Auto Embedding GA status — verify before production use.** As of May 2026, Auto Embedding was in public preview. Pricing, rate limits, and API surface may differ at GA. See Section 4.1 for the current-status check link.
- **Synonym collections must be on the same cluster** as the search index and must follow the required schema (`mappingType`, `synonyms`, `input`, `output`).

---

## Sources

1. [MongoDB Docs -- Atlas Search Overview](https://www.mongodb.com/docs/atlas/atlas-search/)
2. [MongoDB Docs -- Define Field Mappings](https://www.mongodb.com/docs/atlas/atlas-search/define-field-mappings/)
3. [MongoDB Docs -- Standard Analyzer](https://www.mongodb.com/docs/atlas/atlas-search/analyzers/standard/)
4. [MongoDB Docs -- Custom Analyzers](https://www.mongodb.com/docs/atlas/atlas-search/analyzers/custom/)
5. [MongoDB Docs -- Tokenizers](https://www.mongodb.com/docs/atlas/atlas-search/analyzers/tokenizers/)
6. [MongoDB Docs -- Operators and Collectors](https://www.mongodb.com/docs/atlas/atlas-search/operators-and-collectors/)
7. [MongoDB Docs -- compound Operator](https://www.mongodb.com/docs/atlas/atlas-search/compound/)
8. [MongoDB Docs -- facet](https://www.mongodb.com/docs/atlas/atlas-search/facet/)
9. [MongoDB Docs -- Vector Search Overview](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/)
10. [MongoDB Docs -- Run Vector Search Queries](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-stage/)
11. [MongoDB Docs -- Vector Quantization](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-quantization/)
12. [MongoDB Docs -- Hybrid Search](https://www.mongodb.com/docs/atlas/atlas-vector-search/hybrid-search/)
13. [MongoDB Docs -- Vector Search with Full-Text Search](https://www.mongodb.com/docs/atlas/atlas-vector-search/hybrid-search/vector-search-with-full-text-search/)
14. [MongoDB Docs -- $scoreFusion aggregation](https://www.mongodb.com/docs/manual/reference/operator/aggregation/scorefusion/)
15. [MongoDB Docs -- $rankFusion aggregation](https://www.mongodb.com/docs/manual/reference/operator/aggregation/rankfusion/)
16. [MongoDB Docs -- Automated Embedding Overview](https://www.mongodb.com/docs/vector-search/crud-embeddings/automated-embedding/)
17. [MongoDB Docs -- Automatically Generate Vector Embeddings](https://www.mongodb.com/docs/atlas/atlas-vector-search/crud-embeddings/create-embeddings-automatic/)
18. [MongoDB Docs -- Voyage AI Text Embeddings](https://www.mongodb.com/docs/voyageai/models/text-embeddings/)
19. [MongoDB Docs -- Manage Automated Embedding](https://www.mongodb.com/docs/vector-search/crud-embeddings/automated-embedding/management/)
20. [MongoDB Docs -- Vector Search Benchmark Results](https://www.mongodb.com/docs/atlas/atlas-vector-search/benchmark/results/)
21. [MongoDB Blog -- Unlocking AI Search: Automated Embedding](https://www.mongodb.com/company/blog/product-release-announcements/unlocking-ai-search-introducing-automated-embedding-in-mongodb-vector-search)
22. [MongoDB Blog -- Vector Quantization GA](https://www.mongodb.com/company/blog/product-release-announcements/vector-quantization-scale-search-generative-ai-applications)
23. [MongoDB Blog -- Scaling Vector Search with Quantization](https://www.mongodb.com/company/blog/technical/scaling-vector-search-mongodb-atlas-quantization-voyage-ai-embeddings)
24. [MongoDB Blog -- Binary Quantization Rescoring](https://www.mongodb.com/company/blog/product-release-announcements/binary-quantization-rescoring-96-less-memory-faster-search)
25. [MongoDB Blog -- Semantic Power, Lexical Precision](https://www.mongodb.com/company/blog/product-release-announcements/semantic-power-lexical-precision-advanced-filtering-for-vector-search)
26. [MongoDB Blog -- Harness Power of $rankFusion](https://www.mongodb.com/company/blog/technical/harness-power-atlas-search-vector-search-with-rankfusion)
27. [MongoDB Blog -- Native Hybrid Search with $scoreFusion](https://www.mongodb.com/company/blog/product-release-announcements/boost-search-relevance-mongodb-atlas-native-hybrid-search)
28. [MongoDB Blog -- Dedicated Search Nodes GA](https://www.mongodb.com/company/blog/product-release-announcements/dedicated-search-nodes-vector-search-now-in-general-availability)
29. [MongoDB Blog -- Search Nodes Public Preview](https://www.mongodb.com/company/blog/product-release-announcements/search-nodes-now-public-preview-performance-scale-dedicated-infrastructure)
30. [MongoDB Blog -- AI Search for Agents: Automated Embedding in Atlas](https://www.mongodb.com/company/blog/product-release-announcements/ai-search-for-agents-announcing-automated-embedding-atlas)
31. [MongoDB -- Automated Embedding in Community Edition](https://www.mongodb.com/products/updates/now-in-public-preview-automated-embedding-in-vector-search-in-community-edition/)
32. [MongoDB -- Voyage 4 Series Now Available](https://www.mongodb.com/products/updates/the-voyage-4-series-now-available/)
33. [PR Newswire -- Voyage 4 Models](https://www.prnewswire.com/news-releases/mongodb-sets-a-new-standard-for-retrieval-accuracy-voyage-4-models-for-production-ready-ai-applications-302662558.html)
34. [MongoDB Community -- Announcing $rankFusion](https://www.mongodb.com/community/forums/t/announcing-hybrid-search-support-via-rankfusion/324476)
35. [TLD Recap -- Auto Embedding in Vector Search](https://tldrecap.tech/posts/2026/mongodb-local-sf/mongodb-automated-embedding-search/)
36. [OneUpTime -- Tune HNSW Parameters](https://oneuptime.com/blog/post/2026-03-31-mongodb-tune-hnsw-vector-search/view)
37. [DataCamp -- Vector Search in MongoDB Guide](https://www.datacamp.com/tutorial/vector-search-in-mongodb-guide)
38. [OneUpTime -- Atlas Search Full-Text](https://oneuptime.com/blog/post/2026-03-31-mongodb-atlas-search-full-text/view)
39. [MongoDB Docs -- Customize Score](https://www.mongodb.com/docs/atlas/atlas-search/tutorial/compound-query-custom-score/)
40. [Steele O'Brien Consulting -- MongoDB 8.3 for AI Agents](https://steeleobrienconsulting.com/blog/mongodb-data-layer-for-ai-agents/)
41. [MongoDB Docs -- Define Stored Source Fields](https://www.mongodb.com/docs/atlas/atlas-search/stored-source-definition/)
42. [MongoDB Docs -- Return Stored Source Fields](https://www.mongodb.com/docs/atlas/atlas-search/return-stored-source/)
43. [MongoDB Docs -- Return Score Details](https://www.mongodb.com/docs/atlas/atlas-search/score/get-details/)
44. [MongoDB Docs -- Monitor Atlas Search](https://www.mongodb.com/docs/atlas/atlas-search/monitoring/)
45. [MongoDB Docs -- Fix Atlas Search Issues (Alert Resolutions)](https://www.mongodb.com/docs/atlas/reference/alert-resolutions/atlas-search-alerts/)
46. [MongoDB Docs -- Explain Vector Search Results](https://www.mongodb.com/docs/atlas/atlas-vector-search/explain/)
47. [MongoDB -- New Scoring Options for Consistent Pagination on Search Nodes](https://www.mongodb.com/products/updates/new-scoring-options-for-consistent-pagination-on-search-nodes/)
48. [MongoDB Docs -- Atlas Search Performance](https://www.mongodb.com/docs/atlas/atlas-search/performance/)
49. [OneUpTime -- Stored Source in MongoDB Atlas Search](https://oneuptime.com/blog/post/2026-03-31-mongodb-atlas-search-stored-source/view)
50. [OneUpTime -- Monitor Atlas Search Index Size and Performance](https://oneuptime.com/blog/post/2026-03-31-mongodb-how-to-monitor-atlas-search-index-size-and-performance/view)
