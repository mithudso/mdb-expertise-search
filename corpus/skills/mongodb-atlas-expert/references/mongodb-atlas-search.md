<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-search` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-search
description: |
  Deep reference for MongoDB Atlas Search — the Lucene/BM25 full-text search engine embedded in Atlas (NOT vector search). Use this skill whenever the conversation involves: building a search bar or typeahead in MongoDB, $search or $searchMeta aggregation stages, Atlas Search index design (static/dynamic mappings, field types, analyzers), custom analyzers (tokenizers, token filters, synonyms, stemming), the compound operator, faceted search with $searchMeta, highlighting search results, relevance scoring and boosting (BM25, boost, gauss, log1p, function score), autocomplete with edgeGram, dedicated Search Nodes, or diagnosing Atlas Search performance problems and anti-patterns. Also use when the user asks why search results are missing, why scores seem wrong, how to tune relevance, or how to separate search from database workloads. Explicitly excludes $vectorSearch / knnVector — see mongodb-search-ai for hybrid patterns.
category: mongodb
tags:
  - mongodb
  - atlas
  - search
  - lucene
  - full-text
  - bm25
  - aggregation
  - facets
  - autocomplete
  - analyzers
  - scoring
  - indexing
---

# MongoDB Atlas Search (Lucene Full-Text)

Comprehensive reference for MongoDB Atlas Search — the Lucene-based full-text search engine embedded in Atlas. Covers the full lifecycle from index design through query construction, relevance tuning, and production deployment. Explicitly excludes Vector Search (`$vectorSearch`); see [[mongodb-search-ai]] for hybrid and semantic patterns.

## When to Use This Skill

- Building full-text search features: search bars, typeahead, faceted filtering
- Relevance-ranked results with BM25 scoring
- Complex text queries: phrase, fuzzy, wildcard, regex, proximity
- Faceted navigation (e-commerce filters, category counts)
- Autocomplete / search-as-you-type
- Multi-language content with language-specific analyzers
- Rich scoring control: boost, decay, function score

**Cluster tier requirement:** Atlas Search requires **M10 or higher**. It is not available on M0 (free), M2, or M5 shared-tier clusters. If the user is on a free/shared tier, they must upgrade to enable `$search`.

**Do NOT use Atlas Search when:**
- You need immediate consistency — Atlas Search indexes are eventually consistent via change streams; if a freshly-written document must be queryable within milliseconds, use a regular B-tree index with `$regex` or `$text`
- Exact-match on a handful of fields — standard B-tree compound indexes are faster and consistent
- The collection is very small (< 10k docs) and a `$regex` scan is fast enough

---

## 1. Atlas Search Architecture

### The mongot Process

Atlas Search is powered by **mongot**, a Java process that wraps **Apache Lucene** and runs alongside `mongod` on each node. mongot was open-sourced under SSPL in January 2026 (https://github.com/mongodb/mongot).

**Query execution flow:**
```
Application
  → mongod  ($search / $searchMeta aggregation stage)
  → mongot  (Lucene index lookup + scoring)
  → mongod  (receives doc IDs + scores; fetches full docs; runs remaining pipeline)
  → Application (ordered results)
```

mongod never hands documents directly to mongot — it delegates the search predicate and receives back a ranked list of `_id` values plus scores.

### Index Synchronization

mongot maintains its Lucene indexes **asynchronously** via MongoDB Change Streams. This means:
- Index updates are not in the transaction commit path — no write latency impact
- There is a replication lag (typically sub-second to a few seconds under normal load, but can grow under high write pressure or resource contention)
- **Do not rely on Atlas Search for workloads that require read-your-writes consistency**

### Index Build Status

A newly created or rebuilt search index goes through an `INITIAL SYNC` phase before it can serve queries. During this phase `$search` returns no results (not an error). Check build status:

```js
// Shell / mongosh
db.collection.getSearchIndexes()
// Look for "status": "READY" before querying
```

You can also monitor build progress in the Atlas UI under the collection's Search Indexes tab. For large collections with `autocomplete` fields, initial builds can take minutes to hours.

### Deployment Topologies

**Sidecar (default for M10–M40):** mongot runs on the same node as mongod, sharing CPU and RAM. Suitable for dev/test and low-to-moderate search workloads.

**Dedicated Search Nodes (M10+ search tier):** mongot processes run on separate, dedicated instances. Benefits:
- Lucene indexing and query execution no longer compete with mongod for RAM/CPU
- Scale search and database tiers independently
- Required for high-QPS or large-index production workloads

### Sharded Cluster Behavior

In a sharded cluster, each shard has its own mongot instance. `mongos` scatter-gathers `$search` queries to all relevant shards, each executes against its local Lucene index, and results are merge-sorted by `$searchScore` descending before being returned to the application.

---

## 2. Search Index Definition and Mapping

### Index Creation Syntax (Atlas UI / API / CLI)

A search index is a separate entity from a standard MongoDB index. It is defined in JSON and stored in Atlas (not in `system.indexes`).

```json
{
  "name": "default",
  "type": "search",
  "definition": {
    "analyzer": "lucene.standard",
    "searchAnalyzer": "lucene.standard",
    "mappings": {
      "dynamic": false,
      "fields": {
        "title": { "type": "string", "analyzer": "lucene.english" },
        "body": { "type": "string" },
        "category": { "type": "stringFacet" },
        "price": { "type": "number" },
        "publishedAt": { "type": "date" },
        "tags": { "type": "string" },
        "slug": { "type": "token" },
        "location": { "type": "geo" }
      }
    }
  }
}
```

### Dynamic vs. Static Mapping

| Mode | Behavior | Use When |
|---|---|---|
| `"dynamic": true` | Indexes all supported field types automatically | Prototyping; schema-flexible collections |
| `"dynamic": false` | Only indexes explicitly listed fields | Production; control index size and cost |
| Mixed | `"dynamic": false` at root + specific embedded doc fields as `"dynamic": true` | Large docs with a known searchable subset |

**Dynamic mapping caveats:**
- Does NOT auto-index `autocomplete` or `stringFacet` types — these must always be declared statically
- Indexes all strings with the top-level `analyzer` setting — no per-field analysis control
- Increases index build time and storage for large collections with many fields

### Field Types Reference

| Type | Use For | Notes |
|---|---|---|
| `string` | Full-text search with analyzers (BM25 scoring) | Most common; supports `analyzer`, `searchAnalyzer`, `indexOptions`, `store` |
| `token` | Exact-match (no analysis); case-sensitive | Use for enum/ID-like fields needing exact match via `equals`/`in`/`range` |
| `autocomplete` | Prefix autocomplete via `autocomplete` operator | Must be declared statically; not in dynamic mapping |
| `stringFacet` | Bucketed counts for string fields | Must be declared statically; cannot also serve text search without multi-type |
| `number` | Range queries; numeric facets; score boosting via `path` | Subtypes: `double`, `float`, `int`, `long` |
| `date` | Range queries; date facets; near operator | BSON Date / ISO 8601 string |
| `boolean` | Exact true/false via `equals` | — |
| `objectId` | Exact match / range on ObjectId | — |
| `uuid` | Exact match on UUID | — |
| `geo` | `geoWithin`, `geoShape` operators | GeoJSON Point/Polygon |
| `embeddedDocuments` | Query nested document arrays without `$unwind` | Uses the `embeddedDocument` operator |
| `knnVector` | (Legacy) vector similarity | Deprecated; use `$vectorSearch` instead |

### String Field Options

```json
"body": {
  "type": "string",
  "analyzer": "lucene.english",
  "searchAnalyzer": "lucene.standard",
  "indexOptions": "offsets",
  "store": true,
  "multi": {
    "exact": { "type": "string", "analyzer": "lucene.keyword" }
  }
}
```

- `analyzer`: Applied at **index time** — determines how text is tokenized and stored
- `searchAnalyzer`: Applied at **query time** (defaults to `analyzer` if omitted) — can differ from index analyzer for asymmetric analysis
- `indexOptions`: `"docs"` (existence only), `"freqs"` (term frequency), `"positions"` (phrase support), `"offsets"` (highlighting support — **default**)
- `store`: Whether the original field value is stored for highlighting; defaults to `true`
- `multi`: Define multiple sub-analyzers on the same field for cross-analyzer querying

---

## 3. Custom Analyzers

An analyzer is a pipeline: `charFilters → tokenizer → tokenFilters`. Only the tokenizer is required.

### Definition Structure

```json
{
  "analyzers": [
    {
      "name": "my_html_english",
      "charFilters": [
        { "type": "htmlStrip" },
        { "type": "mapping", "mappings": { "&": "and", "@": "at" } }
      ],
      "tokenizer": { "type": "standard" },
      "tokenFilters": [
        { "type": "lowercase" },
        { "type": "stopword", "tokens": ["the", "a", "an", "is"] },
        { "type": "englishMinimalStem" }
      ]
    }
  ]
}
```

### Character Filters (`charFilters`)

| Type | Purpose | Key Options |
|---|---|---|
| `htmlStrip` | Remove HTML tags before tokenization | — |
| `mapping` | Replace character sequences (abbreviations, special chars) | `"mappings": { "src": "replacement" }` |
| `icuNormalize` | Unicode normalization (NFC/NFD/NFKC/NFKD) | `"normalizationForm"` |
| `persian` | Correct spacing around Persian zero-width non-joiner | — |

### Tokenizers

| Type | Behavior | Key Options |
|---|---|---|
| `standard` | Unicode Text Segmentation word-break rules | `"maxTokenLength"` (default 255) |
| `whitespace` | Splits on whitespace only (preserves punctuation) | `"maxTokenLength"` |
| `keyword` | Entire input as one token (exact match) | `"maxTokenLength"` |
| `edgeGram` | Prefix n-grams anchored to word start | `"minGram"`, `"maxGram"`, `"tokenChars"` |
| `nGram` | Sliding window n-grams (substring match) | `"minGram"`, `"maxGram"`, `"tokenChars"` |
| `regexSplit` | Split on regex pattern | `"pattern"` |
| `uaxUrlEmail` | URL + email-aware word splitting | `"maxTokenLength"` |

**Important constraint:** A custom analyzer that uses an `edgeGram` or `nGram` tokenizer **cannot** be used as the `analyzer` for an `autocomplete` field type, nor in synonym mappings. For autocomplete fields, use the built-in `tokenization` parameter on the field type itself (see Section 5).

### Token Filters (`tokenFilters`)

| Type | Purpose | Key Options |
|---|---|---|
| `lowercase` | Lowercase all tokens | — |
| `uppercase` | Uppercase all tokens | — |
| `stopword` | Remove stop words | `"tokens": [...]`, `"ignoreCase"` |
| `length` | Remove tokens outside length range | `"min"`, `"max"` |
| `trim` | Strip leading/trailing whitespace from tokens | — |
| `englishMinimalStem` | Light English stemmer (plurals → singular) | — |
| `porterStem` | Aggressive English Porter stemmer | — |
| `snowballStem` | Snowball stemmer for multiple languages | `"language"` |
| `synonym` | Expand or replace terms with synonyms | `"synonyms"` (synonym mapping name) |
| `shingle` | Multi-token phrase n-grams | `"minShingleSize"`, `"maxShingleSize"` |
| `edgeGram` | Prefix n-grams (post-tokenize) | `"minGram"`, `"maxGram"` |
| `nGram` | Sliding n-grams (post-tokenize) | `"minGram"`, `"maxGram"` |
| `reverse` | Reverse token characters (suffix search hack) | — |
| `kStemming` | Kstem English stemmer | — |
| `icuFolding` | ICU Unicode folding (accent/diacritic removal) | — |
| `icuNormalize` | ICU Unicode normalization | `"normalizationForm"` |
| `daitchMokotoffSoundex` | Phonetic matching | `"originalTokens": "include"` |
| `regex` | Replace matched pattern in token | `"pattern"`, `"replacement"`, `"matches"` |
| `spanishPluralStem` | Spanish plural stemmer | — |

### Synonyms

Synonyms are managed as a separate MongoDB collection **in the same database as the collection being indexed** (not inside the analyzer definition, and not in a different database). Create a collection (e.g., `synonyms`) with documents following this schema:

```json
// Equivalent synonyms — any term matches any other
{ "mappingType": "equivalent", "synonyms": ["coat", "jacket", "blazer"] }

// Explicit — queries for "mad" expand to the listed synonyms; not vice versa
{ "mappingType": "explicit", "input": ["mad"], "synonyms": ["angry", "upset", "furious"] }
```

Reference the synonym collection in the index definition:
```json
{
  "synonyms": [
    {
      "name": "clothing_synonyms",
      "analyzer": "lucene.english",
      "source": { "collection": "synonyms" }
    }
  ]
}
```

Use in a query by referencing the synonym mapping name:
```js
db.products.aggregate([{
  $search: {
    "index": "default",
    "text": {
      "query": "coat",
      "path": "name",
      "synonyms": "clothing_synonyms"
    }
  }
}])
```

Note: `fuzzy` and `synonyms` cannot be combined on the same `text` operator.

---

## 4. $search Operator Reference

### Stage Syntax

```js
db.collection.aggregate([
  {
    $search: {
      "index": "default",           // optional; defaults to "default"
      "count": { "type": "total" }, // optional: get result count alongside docs
      "highlight": { "path": "body" },
      "scoreDetails": true,         // optional: expose per-clause score breakdown
      "sort": { "publishedAt": -1 }, // optional: sort by field (Atlas Search 7.0+)
      // <operator>: { <specification> }
    }
  }
])
```

### Sorting Within $search

As of Atlas Search on MongoDB 7.0+, you can include a `sort` option **inside** the `$search` stage to sort results by any indexed field while still applying Atlas Search's index. This is different from adding a `$sort` stage **after** `$search`, which discards relevance ranking and re-sorts the already-fetched documents.

```js
{
  $search: {
    "compound": {
      "must": [{ "text": { "query": "laptop", "path": "name" } }],
      "filter": [{ "equals": { "path": "inStock", "value": true } }]
    },
    "sort": { "price": 1 }   // sort by price ascending, within Atlas Search
  }
}
```

Use `sort` inside `$search` when you need a deterministic field-based order (e.g., price, date) instead of relevance rank. For blending recency with relevance, prefer the `near` operator or `gauss` function score (see Section 8) over a hard sort.

### Pagination with searchSequenceToken

For cursor-based pagination (safer than `$skip` which re-scans from the start), use `searchAfter` / `searchBefore` with a `searchSequenceToken`:

```js
// First page — no searchAfter (omit the key entirely)
const page1 = await col.aggregate([
  { $search: { "text": { "query": "laptop", "path": "name" } } },
  { $limit: 20 },
  { $project: { name: 1, score: { $meta: "searchScore" }, paginationToken: { $meta: "searchSequenceToken" } } }
]).toArray()

// Next page — pass the last doc's token as searchAfter
const lastToken = page1[page1.length - 1].paginationToken
const page2 = await col.aggregate([
  { $search: { "text": { "query": "laptop", "path": "name" }, "searchAfter": lastToken } },
  { $limit: 20 },
  { $project: { name: 1, score: { $meta: "searchScore" }, paginationToken: { $meta: "searchSequenceToken" } } }
]).toArray()
```

`searchBefore` navigates backwards from a token. Tokens are opaque — store and pass them from the client; do not construct them manually. Do not pass `null` for the first page — omit `searchAfter` entirely.

### compound — Boolean Query Logic

The most important and most commonly used operator. Combines sub-queries with four clause types:

| Clause | Effect | Affects Score |
|---|---|---|
| `must` | Document MUST match all clauses | Yes |
| `mustNot` | Document MUST NOT match any clause | No (excludes only) |
| `should` | Document SHOULD match (boosts score if it does) | Yes |
| `filter` | Document must match but contributes no score | No — use for pure boolean filters |

```js
{
  $search: {
    "compound": {
      "must": [
        { "text": { "query": "laptop", "path": "category" } }
      ],
      "should": [
        { "text": { "query": "gaming", "path": "title", "score": { "boost": { "value": 2 } } } },
        // near: origin and pivot are epoch-milliseconds for date fields; 7776000000ms = 90 days
        { "near": { "path": "publishedAt", "origin": 1751328000000, "pivot": 7776000000 } }
      ],
      "mustNot": [
        { "text": { "query": "refurbished", "path": "condition" } }
      ],
      "filter": [
        { "range": { "path": "price", "gte": 500, "lte": 2000 } }
      ],
      "minimumShouldMatch": 1
    }
  }
}
```

`minimumShouldMatch` (default 0): require at least N `should` clauses to match. Nested compound queries are allowed for complex boolean trees.

### text — Full-Text Search

```js
{
  "text": {
    "query": "mongodb full text search",
    "path": "body",              // string, array of strings, or { "wildcard": "*" }
    "fuzzy": {
      "maxEdits": 1,             // 1 or 2 Levenshtein edits allowed
      "prefixLength": 4,         // leading chars exempt from fuzzy expansion
      "maxExpansions": 50        // max candidate terms to check
    },
    "synonyms": "my_synonyms",   // cannot combine with fuzzy
    "score": { "boost": { "value": 1.5 } }
  }
}
```

The analyzer used at query time is determined by the field's `searchAnalyzer` in the index definition (falls back to `analyzer` if not set).

### phrase — Ordered Proximity Search

```js
{
  "phrase": {
    "query": "quick brown fox",
    "path": "description",
    "slop": 2       // allow up to 2 transpositions/insertions between phrase terms
  }
}
```

Requires `indexOptions: "positions"` or `"offsets"` (both are the default — only breaks if you explicitly set `"docs"` or `"freqs"`).

### queryString — Lucene Query Syntax

```js
{
  "queryString": {
    "defaultPath": "body",
    "query": "title:(mongodb atlas) AND category:search NOT status:deprecated"
  }
}
```

Supports full Lucene query parser syntax: `AND`, `OR`, `NOT`, `field:value`, wildcards, ranges `[a TO b]`, phrases `"..."`, boosting with `^`. Use with caution in user-facing search boxes — malformed input causes parse errors.

### wildcard — Pattern Matching

```js
{
  "wildcard": {
    "query": "mongo*",
    "path": "name",
    "allowAnalyzedSearch": false   // default false; set true to match analyzed tokens
  }
}
```

`?` matches one character; `*` matches zero or more. **Leading wildcards (`*mongo`) are expensive** — they cannot use the inverted index and force a full scan of all terms in every Lucene segment.

### regex — Regular Expression

```js
{
  "regex": {
    "query": "^mongo.*db$",
    "path": "slug",
    "allowAnalyzedSearch": false
  }
}
```

Like wildcard, regex cannot use index structures for the pattern — it scans all terms in the index. Avoid complex patterns on large collections.

### range — Numeric, Date, String, ObjectId Ranges

```js
{
  "range": {
    "path": "price",
    "gte": 100,
    "lte": 500
  }
}
```

Works for `number`, `date`, `objectId`, `token` field types. For strings, range is lexicographic. Put range conditions in the `filter` clause of `compound` when they should not affect the relevance score.

### near — Proximity to a Value

```js
// Numeric near (score decays as rating diverges from 4.5)
{ "near": { "path": "rating", "origin": 4.5, "pivot": 1.0 } }

// Date near (recency boost — score halves at 30-day distance)
// origin and pivot are milliseconds since epoch for date fields
{ "near": { "path": "publishedAt", "origin": 1751328000000, "pivot": 2592000000 } }

// Geo near (score halves at 1000m from the point)
{ "near": { "path": "location", "origin": { "type": "Point", "coordinates": [-73.9, 40.7] }, "pivot": 1000 } }
```

`pivot`: the distance at which the score factor is halved. Uses an inverse linear decay function (not Gaussian — use `gauss` in `function` score for Gaussian decay).

### equals / in — Exact Value Match

```js
// Single value
{ "equals": { "path": "status", "value": "active" } }

// Multiple values (OR semantics)
{ "in": { "path": "tags", "value": ["nodejs", "python", "java"] } }
```

Works on `boolean`, `date`, `objectId`, `number`, `token`, `uuid` fields. Does not work on `string` fields (use `text` or `phrase` for string fields).

### exists — Field Presence Check

```js
{ "exists": { "path": "thumbnailUrl" } }
```

### moreLikeThis — Similar Document Search

```js
{
  "moreLikeThis": {
    "like": [
      { "_id": ObjectId("..."), "title": "...", "body": "..." }
    ]
  }
}
```

Pass one or more "seed" documents (or partial documents); Atlas Search returns similar documents based on term overlap. Useful for "more like this" product or article recommendations.

### geoWithin / geoShape — Geospatial Operators

```js
// Points within a polygon
{
  "geoWithin": {
    "path": "location",
    "polygon": {
      "type": "Polygon",
      "coordinates": [[[-74, 40], [-73, 40], [-73, 41], [-74, 41], [-74, 40]]]
    }
  }
}

// Shape relationship (intersects, within, disjoint, contains)
{
  "geoShape": {
    "path": "area",
    "relation": "intersects",
    "geometry": { "type": "Point", "coordinates": [-73.9, 40.7] }
  }
}
```

### embeddedDocument — Query Array of Subdocuments

```js
{
  "embeddedDocument": {
    "path": "reviews",
    "operator": {
      "compound": {
        "must": [
          { "text": { "query": "excellent", "path": "reviews.comment" } },
          { "range": { "path": "reviews.rating", "gte": 4 } }
        ]
      }
    },
    "score": { "embedded": { "aggregate": "maximum" } }
  }
}
```

This is the key difference from querying root-level arrays: both conditions must match **within the same array element**. Without `embeddedDocument`, conditions could match across different elements in the array.

---

## 5. Autocomplete

Atlas Search provides a dedicated `autocomplete` operator and `autocomplete` field type for search-as-you-type.

### Index Configuration

```json
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "title": [
        {
          "type": "string",
          "analyzer": "lucene.standard"
        },
        {
          "type": "autocomplete",
          "tokenization": "edgeGram",
          "minGrams": 4,
          "maxGrams": 15,
          "foldDiacritics": true
        }
      ]
    }
  }
}
```

A field can have **multiple index type definitions** as an array — here `title` is indexed as both `string` (for regular text search) and `autocomplete` (for prefix queries). This is the recommended pattern when you need both.

### Tokenization Options

| Option | Behavior | Use When |
|---|---|---|
| `edgeGram` (default) | Left-anchored prefix tokens: "mo", "mon", "mong"... | Standard prefix autocomplete — most common |
| `rightEdgeGram` | Right-anchored suffix tokens: "b", "db", "odb"... | Suffix / reverse autocomplete |
| `nGram` | All substring tokens — most storage, most recall | Substring matching anywhere mid-word |
| `standard` | Word-boundary tokens only | Word-level (not character-level) prefix matching |
| `keyword` | Entire field as a single token | Exact field completion only |

**Performance guidelines:**
- `minGrams` ≥ 4 recommended for large collections — values < 4 cause token count explosion
- `maxGrams` ≤ 15 to bound index size and RAM
- Apply `autocomplete` type only to fields users actually type into — never in dynamic mappings

### Autocomplete Operator

```js
db.movies.aggregate([
  {
    $search: {
      "autocomplete": {
        "query": "stran",
        "path": "title",
        "tokenOrder": "sequential",  // "sequential" (query order) or "any" (any order)
        "fuzzy": {
          "maxEdits": 1,
          "prefixLength": 4,
          "maxExpansions": 20
        }
      }
    }
  },
  { $limit: 10 },
  { $project: { title: 1, score: { $meta: "searchScore" } } }
])
```

- `tokenOrder: "sequential"`: tokens must appear in query order — better for typed phrases
- `tokenOrder: "any"`: tokens can appear in any order — broader matching, more false positives
- `fuzzy`: allow typos — use sparingly, increases latency and index scan cost

### Separate Autocomplete vs. Full Search

Best practice: use the `autocomplete` operator for typeahead (fast, prefix-biased), and switch to the `text` operator when the user submits the full query. The `autocomplete` operator has lower recall than `text` because it only matches tokens generated at index time.

---

## 6. Facets

Facets group search results into labeled buckets with counts — essential for filter sidebars in e-commerce and catalog UIs.

### Required Field Types

| Facet Type | Index Field Type | Notes |
|---|---|---|
| String facet | `stringFacet` | Strings: categories, brands, tags |
| Number facet | `number` | Numeric range buckets: price, rating |
| Date facet | `date` | Date range buckets: year, month |

A field indexed as `stringFacet` cannot serve regular text search queries. If you need both, declare the field twice as an array of types (see Section 2 multi-type pattern).

### Index Definition for Facets

```json
{
  "mappings": {
    "dynamic": false,
    "fields": {
      "name": { "type": "string" },
      "category": { "type": "stringFacet" },
      "brand": { "type": "stringFacet" },
      "price": { "type": "number" },
      "createdAt": { "type": "date" }
    }
  }
}
```

### $searchMeta — Facet Counts Only (No Documents)

Use when you only need the bucket counts, not the matched documents:

```js
db.products.aggregate([
  {
    $searchMeta: {
      "index": "facets_index",
      "facet": {
        "operator": {
          "text": { "query": "laptop", "path": "name" }
        },
        "facets": {
          "categoryBuckets": {
            "type": "string",
            "path": "category",
            "numBuckets": 10
          },
          "priceBuckets": {
            "type": "number",
            "path": "price",
            "boundaries": [0, 100, 500, 1000, 5000],
            "default": "other"
          },
          "dateBuckets": {
            "type": "date",
            "path": "createdAt",
            "boundaries": [
              new Date("2024-01-01"),
              new Date("2025-01-01"),
              new Date("2026-01-01")
            ],
            "default": "other"
          }
        }
      }
    }
  }
])
```

### $search + facet Collector — Documents and Counts in One Query

Rather than running two separate aggregations (one for documents, one for facet counts), use a single `$search` with the `facet` collector to retrieve both. The `$$SEARCH_META` variable holds the facet metadata within the same pipeline:

```js
db.products.aggregate([
  {
    $search: {
      "facet": {
        "operator": {
          "compound": {
            "must": [{ "text": { "query": "laptop", "path": "name" } }],
            "filter": [{ "range": { "path": "price", "gte": 500 } }]
          }
        },
        "facets": {
          "categoryFacet": { "type": "string", "path": "category" }
        }
      }
    }
  },
  { $limit: 20 },
  {
    $facet: {
      "docs": [{ $project: { name: 1, price: 1, score: { $meta: "searchScore" } } }],
      "meta": [{ $replaceWith: "$$SEARCH_META" }, { $limit: 1 }]
    }
  }
])
```

### Facet Count Accuracy

```js
$search: {
  "count": { "type": "total" },   // exact count — more expensive
  // "count": { "type": "lowerBound" }  // default — fast approximate, may undercount
  "facet": { /* ... */ }
}
```

---

## 7. Highlighting

Highlighting returns the matched text in context, marking which tokens hit the query — useful for showing users why a result matched.

### Basic Syntax

```js
db.articles.aggregate([
  {
    $search: {
      "text": { "query": "mongodb performance", "path": "body" },
      "highlight": {
        "path": "body",
        "maxCharsToExamine": 500000,  // default: 500,000
        "maxNumPassages": 5           // default: 5
      }
    }
  },
  {
    $project: {
      title: 1,
      body: 1,
      highlights: { $meta: "searchHighlights" }
    }
  }
])
```

### Output Structure

```json
{
  "highlights": [
    {
      "path": "body",
      "score": 1.43,
      "texts": [
        { "value": "Improving ", "type": "text" },
        { "value": "MongoDB", "type": "hit" },
        { "value": " query ", "type": "text" },
        { "value": "performance", "type": "hit" },
        { "value": " requires indexing.", "type": "text" }
      ]
    }
  ]
}
```

- `type: "hit"` — the matched token (wrap with `<mark>` or `<em>` for UI)
- `type: "text"` — surrounding context (display as-is)
- Passages are sorted by their relevance score; highest-scoring passage first
- The field must be indexed with `indexOptions: "offsets"` (the default)

### Parameter Details

| Parameter | Default | Effect |
|---|---|---|
| `maxCharsToExamine` | 500,000 | How far into each document Atlas Search scans; lower = faster but may miss matches in long documents |
| `maxNumPassages` | 5 | Max highlight snippets per path per document; lower = smaller response |

### Multi-Field and Wildcard Paths

```js
// Multiple specific fields
"highlight": { "path": ["title", "body", "summary"] }

// Wildcard path
"highlight": { "path": { "wildcard": "content.*" } }
```

### Limitations

- Cannot use `highlight` with the `embeddedDocument` operator
- `highlight` is a top-level child of `$search`, not nested inside operator clauses
- Setting `maxCharsToExamine` too low may return zero passages for long documents even when they match

---

## 8. Relevance Scoring and Boosting

### BM25 Default Scoring

Atlas Search uses **Okapi BM25** as the default similarity function for `text`, `phrase`, `queryString`, and `autocomplete` operators. BM25 score is a product of:

- **IDF (Inverse Document Frequency)**: rare terms score higher
- **TF (Term Frequency)**: more occurrences in the document = higher score, with logarithmic diminishing returns
- **Field length normalization**: shorter documents score higher for the same term frequency

Retrieve the score in a `$project` stage:
```js
{ $project: { title: 1, score: { $meta: "searchScore" } } }
```

Debug per-clause score breakdown with `scoreDetails`:
```js
{
  $search: {
    "text": { "query": "...", "path": "..." },
    "scoreDetails": true
  }
}
// Project: { scoreDetails: { $meta: "searchScoreDetails" } }
```

### Score Modification Options

Every operator accepts a `score` option. The four types are:

### boost — Multiply Base Score

```js
// By constant factor
"score": { "boost": { "value": 3.0 } }

// By numeric field value (e.g., IMDb rating)
"score": { "boost": { "path": "imdb.rating", "undefined": 2.5 } }
```

The `"undefined"` key (a literal JSON key, not the JavaScript keyword) provides a fallback numeric value used when the document does not have the `path` field. Without it, documents missing the field score 0.

### constant — Replace Score with Fixed Value

```js
"score": { "constant": { "value": 1.0 } }
```

Use when you want a clause to filter (include/exclude) but have no relevance contribution. In most cases, the `filter` clause of `compound` achieves the same effect without needing this.

### function — Compute Score from Expression

The most powerful option. An arithmetic expression tree over numeric fields and the base relevance score:

```js
"score": {
  "function": {
    "multiply": [
      { "score": "relevance" },           // BM25 base score
      {
        "log1p": {                         // log10(views + 1) — popularity signal
          "path": { "value": "views", "undefined": 1 }
        }
      },
      {
        "gauss": {                         // recency decay
          "path": { "value": "publishedAt", "undefined": 946684800000 },
          "origin": 1748476800000,         // reference epoch-ms (set dynamically in production)
          "scale": 7776000000,             // 90 days in ms — score multiplier = decay at this distance
          "offset": 86400000,              // 1-day grace period with no decay
          "decay": 0.5                     // score multiplier at scale distance
        }
      }
    ]
  }
}
```

**Function expression types:**

| Expression | Description |
|---|---|
| `multiply: [...]` | Multiply a list of numeric expressions |
| `add: [...]` | Sum a list of numeric expressions |
| `constant: <n>` | A literal number |
| `path: "field"` | Value of a numeric indexed field |
| `score: "relevance"` | The BM25 base score |
| `log: <expr>` | log10(x) — error if x ≤ 0 |
| `log1p: <expr>` | log10(x+1) — safe for zero and small values |
| `gauss: {...}` | Gaussian decay from an origin point |

**Gaussian decay parameters:**
- `origin`: The center point (score multiplier = 1.0 here); pass as epoch-milliseconds for date fields
- `scale`: Distance from origin where the multiplier equals `decay`
- `offset`: Distance from origin within which no decay applies (grace zone)
- `decay`: The multiplier at distance = `scale` (must be between 0 and 1 exclusive; default 0.5)

### Score Normalization

To normalize scores to [0, 1] relative to the top result in the same query, collect all documents first then divide by the max:

```js
// After $search, add the raw score
{ $project: { title: 1, rawScore: { $meta: "searchScore" } } },
// Collect all docs and find max in one $group
{ $group: { _id: null, docs: { $push: "$$ROOT" }, maxScore: { $max: "$rawScore" } } },
// Re-expand and compute normalized score
{ $unwind: "$docs" },
{ $replaceRoot: { newRoot: { $mergeObjects: ["$docs", { normalizedScore: { $divide: ["$docs.rawScore", "$maxScore"] } }] } } }
```

### Multi-Clause Scoring with compound

In a `compound` query:
- `must` and `should` clauses contribute to the final score **additively**
- `filter` clauses do not affect score — use for pure boolean constraints
- `mustNot` clauses exclude documents but do not modify the score
- `minimumShouldMatch: N` requires at least N `should` clauses to match

---

## 9. Atlas Search Nodes (Dedicated Tier)

### What Are Search Nodes

Search Nodes are dedicated compute instances that run only the mongot process — no mongod. This separates the search and database tiers so they scale independently.

**Supported from:** M10 and above (the database cluster tier; search nodes have their own separate instance sizing)

### When to Enable

Enable dedicated search nodes when:
- Search queries visibly compete with database operations for RAM/CPU (check Atlas metrics)
- Index builds are affecting write throughput
- Sustained search QPS > ~100 queries/sec
- Lucene index size > 10–20 GB
- You want horizontal scale for search without over-provisioning the database

For dev/test and light production workloads, the sidecar model is sufficient.

### Sizing Guide

Lucene is memory-hungry — the active Lucene index segments should ideally fit in RAM for optimal performance.

General heuristics:
- RAM needed ≈ (uncompressed index size) × 1.2–1.5 for hot working set
- Text-heavy workloads: start with nodes having ≥ 4 GB RAM per mongot process
- Autocomplete indexes (high edgeGram token count): RAM requirements are significantly higher
- Scale horizontally (add nodes) before scaling vertically for QPS-limited workloads

### Deployment Regions

Search Nodes are available in all GCP regions but only in a subset of AWS and Azure regions. Verify availability in the Atlas UI before designing your deployment.

### Cost Model

- Billed per search node per hour, separately from the database cluster
- No data transfer charges between search nodes and data nodes in the same region
- Index storage on search nodes is billed separately from cluster storage
- Rough baseline: a 2-node deployment at the minimum search tier ≈ 2× the hourly rate of the smallest search node SKU

### Migrating from Sidecar to Search Nodes

1. In the Atlas UI: cluster → Search → Enable Search Nodes
2. Atlas provisions the dedicated nodes and migrates mongot processes
3. Zero downtime: change stream sync continues during migration
4. After migration, all search indexes are stored and served from dedicated nodes only

### Monitoring Key Metrics

| Metric | Alert Threshold | Action |
|---|---|---|
| Search CPU utilization | > 60% sustained | Scale up or add nodes |
| Search memory utilization | > 80% | Increase node RAM or reduce index size |
| Index replication lag | Growing trend | Investigate write pressure / resource contention |
| Query latency p99 | Baseline regression | Check query complexity, index size, CPU |

---

## 10. Atlas Search Anti-Patterns

### AP-1: Dynamic Mapping in Production at Scale

**Problem:** `"dynamic": true` indexes every field in every document. For wide documents this causes bloated index size, slow builds, and high RAM consumption on mongot.

**Fix:** Switch to `"dynamic": false` and enumerate only the fields that will actually be queried.

### AP-2: Leading Wildcards and Unbounded Regex

**Problem:**
```js
{ "wildcard": { "query": "*database", "path": "name" } }
{ "regex": { "query": ".*database.*", "path": "name" } }
```
Both cannot use the inverted index — they scan all terms in every Lucene segment. Query latency spikes, especially on large collections.

**Fix:** Anchor patterns to the left (`mongo*`), or use a `text` operator with an edgeGram-based custom analyzer for prefix matching.

### AP-3: Autocomplete in Dynamic Mappings

**Problem:** The `autocomplete` type is not auto-indexed, and even when added to many fields manually, generates enormous numbers of tokens (up to `maxGrams` per word per document).

**Fix:** Apply `autocomplete` type only to specific user-facing fields with static mappings. Use `maxGrams ≤ 15` and `minGrams ≥ 4` for large collections.

### AP-4: Two Queries Instead of One for Facets + Documents

**Problem:**
```js
// Inefficient: two round-trips, two index scans
const docs = await col.aggregate([{ $search: { text: /* ... */ } }])
const meta = await col.aggregate([{ $searchMeta: { facet: /* ... */ } }])
```

**Fix:** Use a single `$search` with `facet` collector + `$facet` stage to get both in one query (see Section 6 — "$search + facet Collector"). The `$$SEARCH_META` variable gives access to bucket counts within the same aggregation pipeline.

### AP-5: Over-Indexing with Multiple Analyzers on Every Field

**Problem:** Defining 4–5 analyzer variants for every string field (standard, english, keyword, autocomplete, exact) multiplies index size and build time.

**Fix:** Only add multiple analyzers where query requirements specifically demand it. Use the `multi` sub-field syntax so extra analyzers are additive only where needed.

### AP-6: Relying on Atlas Search for Write-Your-Read Consistency

**Problem:** Writing a document and immediately querying Atlas Search expects it to appear — the async change stream lag means it may not appear in results for hundreds of milliseconds to several seconds.

**Fix:** For workloads that need immediate readback (identity lookup, confirmation pages), query mongod directly with a B-tree index. Reserve Atlas Search for discovery and exploration queries where eventual consistency is acceptable.

### AP-7: Not Using filter for Non-Scoring Conditions

**Problem:**
```js
{
  "compound": {
    "must": [
      { "text": { "query": "laptop", "path": "name" } },
      { "range": { "path": "price", "gte": 100 } }   // Price affects score here — unnecessary
    ]
  }
}
```

**Fix:** Put range/date/boolean conditions that are pure constraints in the `filter` clause:
```js
{
  "compound": {
    "must": [{ "text": { "query": "laptop", "path": "name" } }],
    "filter": [{ "range": { "path": "price", "gte": 100 } }]
  }
}
```
`filter` is faster because it uses a cached bitset and skips score computation for that clause.

### AP-8: Overriding Relevance Ranking with a Post-Search $sort

**Problem:** Running `$search` and then applying `$sort: { createdAt: -1 }` **after** `$search` as a separate pipeline stage discards the relevance ranking Atlas Search computed.

**Fix:** Let Atlas Search sort by score (default behavior). For a blend of recency and relevance, use the `near` operator on the date field inside a `compound` `should` clause, or use the `gauss` function expression in the score. For hard field-based sort, use the `sort` option **inside** `$search` (Section 4).

### AP-9: indexOptions: "docs" Breaks Phrase and Highlighting

**Problem:** Setting `"indexOptions": "docs"` to shrink index size removes position and offset data, silently breaking:
- `phrase` operator (requires `positions`)
- `highlight` option (requires `offsets`)

**Fix:** Use the default `"indexOptions": "offsets"` unless you have measured that the storage saving is worth losing these capabilities. Use `"freqs"` if you need term frequency scoring but not positions.

### AP-10: Querying Unindexed Fields Silently Returns Zero Results

**Problem:** With `dynamic: false`, querying a field not in the index definition returns zero results — no error is raised.

**Fix:** Validate index definitions in staging. Use `scoreDetails: true` to inspect which fields Atlas Search is evaluating. Add integration tests that assert non-zero result counts for known documents.

### AP-11: maxGrams Too High on Large Collections

**Problem:** `maxGrams: 30` on a 10M-document collection generates hundreds of tokens per document, causing extremely slow initial builds, very large indexes (3–5× a standard text index), and high RAM pressure on mongot.

**Fix:** Keep `maxGrams ≤ 15`. Users typically type 4–8 characters before selecting a suggestion — 15 characters covers the vast majority of autocomplete interactions.

### AP-12: Putting Autocomplete and Text Fields in the Same Index

**Problem:** Autocomplete fields in the same index as full-text search fields forces a full index rebuild when either type's configuration changes, and makes the autocomplete storage cost opaque.

**Fix:** Use separate search indexes — one for text/facet queries, one for autocomplete. This allows independent builds, rebuilds, and sizing.

---

## References and See Also

### Official MongoDB Documentation
- [Atlas Search Overview](https://www.mongodb.com/docs/atlas/atlas-search/)
- [Operators and Collectors](https://www.mongodb.com/docs/atlas/atlas-search/operators-and-collectors/)
- [compound Operator](https://www.mongodb.com/docs/atlas/atlas-search/compound/)
- [Score Modification](https://www.mongodb.com/docs/atlas/atlas-search/score/modify-score/)
- [Custom Analyzers](https://www.mongodb.com/docs/atlas/atlas-search/analyzers/custom/)
- [Autocomplete Field Type](https://www.mongodb.com/docs/atlas/atlas-search/field-types/autocomplete-type/)
- [Highlighting](https://www.mongodb.com/docs/atlas/atlas-search/highlighting/)
- [Facets Tutorial](https://www.mongodb.com/docs/atlas/atlas-search/tutorial/facet-tutorial/)
- [Query Performance](https://www.mongodb.com/docs/atlas/atlas-search/performance/query-performance/)
- [Paginate Results](https://www.mongodb.com/docs/atlas/atlas-search/paginate-results/)
- [mongot GitHub (SSPL)](https://github.com/mongodb/mongot)

### Key Blog Posts and Articles
- [Now Source Available: The Engine Powering MongoDB Search](https://www.mongodb.com/company/blog/product-release-announcements/now-source-available-the-engine-powering-mongodb-search)
- [When NOT to Use Atlas Search](https://dev.to/erikhatcher/when-not-to-use-atlas-search-kh9)
- [Dynamic Term-Based Boosting in MongoDB Atlas Search](https://www.mongodb.com/company/blog/technical/dynamic-term-based-boosting-in-mongodb-atlas-search)
- [Atlas Search BM25 Score Details](https://dev.to/franckpachot/atlas-search-score-details-the-bm25-calculation-2g55)
- [Compound Text Search — Practical MongoDB Aggregations](https://www.practical-mongodb-aggregations.com/examples/full-text-search/compound-text-search.html)

### Related Skills
- [[mongodb-search-ai]] — Hybrid search (lexical + vector), Atlas Vector Search, RAG patterns
- [[mongodb-atlas-expert]] — Atlas platform overview, cluster management, Atlas CLI
- [[mongodb-indexes-deep]] — B-tree indexes, compound indexes, covered queries, index selection
