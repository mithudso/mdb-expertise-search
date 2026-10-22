<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-vector-search` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

# MongoDB Atlas Vector Search and RAG

Deep expertise in MongoDB Atlas Vector Search — HNSW index tuning, `$vectorSearch` operator, hybrid search with `$rankFusion`/`$scoreFusion`, Voyage AI auto-embedding, RAG architecture patterns, embedding pipeline design, dedicated Search Nodes, performance tuning, and anti-patterns.

## When to Use This Skill

- Designing or troubleshooting Atlas Vector Search indexes (HNSW parameters, quantization, filter fields)
- Writing `$vectorSearch` aggregation pipelines (ANN vs ENN, numCandidates, filters, scoring)
- Implementing hybrid search combining `$vectorSearch` + `$search` via `$rankFusion` or `$scoreFusion`
- Setting up Voyage AI auto-embedding or choosing between Voyage 4 embedding models
- Architecting RAG systems on MongoDB (chunking, parent-doc retrieval, metadata filtering, re-ranking)
- Designing embedding pipelines (batch, real-time triggers, change streams, auto-embedding)
- Sizing dedicated Search Nodes (S20/S30/S50-storage) for vector workloads
- Tuning recall-vs-latency tradeoffs with numCandidates, HNSW m/efConstruction, quantization
- Implementing multi-vector patterns (multiple embeddings per doc, late chunking)
- Avoiding common pitfalls (poor recall, full scans, wrong similarity metric, dim mismatch)

---

> **Securing vector search for regulated (FSI/PII) data:** for entitlement-filtered
> retrieval, tenant/PII isolation, and the rule that the embedding field cannot be
> Queryable-Encrypted yet searched, see `atlas-vector-search-pii-isolation`;
> embedding-inversion / vector-store leakage risk in `embedding-inversion-threat-model`;
> LLM-layer injection defense in `rag-prompt-injection-defense`; bank AI governance in
> `bank-genai-model-risk-governance`.

## 1. Vector Index Definition and HNSW Parameters

### Index Type and Required Fields

A vector search index is defined with type `"vectorSearch"` and requires at least one field of `"type": "vector"`.

```python
from pymongo.operations import SearchIndexModel

index_model = SearchIndexModel(
    definition={
        "fields": [
            {
                "type": "vector",
                "path": "embedding",          # Field path in the document
                "numDimensions": 1536,         # Must match embedding model output
                "similarity": "cosine",        # euclidean | cosine | dotProduct
                # Optional HNSW tuning:
                # "efConstruction": 200,
                # "maxConnections": 32,        # Also called 'm'
                # Optional quantization:
                # "quantization": "scalar",    # scalar | binary
            },
            # Optional filter fields (for pre-filtering):
            { "type": "filter", "path": "category" },
            { "type": "filter", "path": "year" },
            { "type": "filter", "path": "price" },
        ]
    },
    name="vector_index",
    type="vectorSearch"
)
collection.create_search_index(model=index_model)
```

### Core Vector Field Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | string | Yes | Must be `"vector"` |
| `path` | string | Yes | Document field path holding the embedding array |
| `numDimensions` | integer | Yes | Number of dimensions — must match embedding model output exactly (e.g., 1536 for OpenAI ada-002, 1024 for Voyage 4 / voyage-3, 2048 for voyage-4-large / voyage-3-large, 768 for many sentence transformers) |
| `similarity` | string | Yes | Distance metric: `euclidean`, `cosine`, or `dotProduct` |

**numDimensions limits:** MongoDB Atlas supports up to 8192 dimensions (increased from 4096 in 2025). The value must exactly match the embedding model's output dimensionality.

### Similarity Metric Selection

| Metric | Use When | Notes |
|--------|----------|-------|
| `cosine` | General semantic search, normalized or unnormalized embeddings | Measures angle between vectors; ignores magnitude; recommended default |
| `dotProduct` | Pre-normalized embeddings (unit vectors) | Equivalent to cosine when vectors are L2-normalized; slightly faster |
| `euclidean` | Absolute distance matters; spatial or dense numeric data | Sensitive to magnitude; less common for text embeddings |

**Rule:** Use `dotProduct` with Voyage AI embeddings (they are normalized). Use `cosine` for OpenAI embeddings. Never mix similarity metric at index time vs. query time — the index bakes in the metric.

### HNSW Parameters

HNSW (Hierarchical Navigable Small Worlds) is the underlying approximate nearest neighbor algorithm.

| Parameter | Field Name | Default | Range | Effect |
|-----------|-----------|---------|-------|--------|
| Connections per node | `maxConnections` (also `m`) | 16 | 2–512 | Higher = better recall, more memory, slower build |
| Build candidate list | `efConstruction` | 200 | 10–2000 | Higher = better graph quality, slower index build only (does NOT affect query latency) |

**Practical guidance:**
- `efConstruction=200, maxConnections=32` is a good production starting point
- `efConstruction` affects only index build quality — once built, increase numCandidates at query time to trade latency for recall
- Higher `maxConnections` increases memory proportionally; 16–32 covers 95% of use cases
- `efSearch` (the query-time candidate list) is controlled by `numCandidates` in `$vectorSearch`, not in the index definition

### Filter Fields

Any field that will be used in a `$vectorSearch` filter clause **must be indexed** as a filter field in the vector search index:

```json
{ "type": "filter", "path": "genres" }
{ "type": "filter", "path": "year" }
{ "type": "filter", "path": "price" }
```

Supported types: BSON boolean, date, objectId, numeric (int32, int64, double, decimal128), string, UUID, and arrays of these types.

**Critical:** Filtering in `$vectorSearch` without a declared filter field causes a full collection scan — major performance impact.

### Quantization in the Index

Add quantization inside the vector field definition:

```json
{
  "type": "vector",
  "path": "embedding",
  "numDimensions": 1024,
  "similarity": "cosine",
  "quantization": "scalar"    // or "binary"
}
```

Full quantization reference in Section 8.

---

## 2. $vectorSearch Operator Reference

`$vectorSearch` must be the **first stage** of any aggregation pipeline where it appears. It cannot appear inside `$lookup` sub-pipelines, `$facet`, or view definitions.

### Full Parameter Reference

```javascript
{
  "$vectorSearch": {
    "index": "vector_index",        // Required: name of the vectorSearch index
    "path": "embedding",             // Required: field path containing vectors
    "queryVector": [0.1, 0.2, ...], // Required: the query embedding array
    "limit": 10,                     // Required: max documents to return
    "numCandidates": 200,            // Required for ANN; omit for exact ENN
    "exact": false,                  // Optional: true = ENN, false/absent = ANN
    "filter": {                      // Optional: pre-filter before vector search
      "category": "electronics",
      "year": { "$gte": 2020 }
    }
  }
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `index` | string | Yes | Name of the `vectorSearch` index |
| `path` | string | Yes | Document field path with the stored vector |
| `queryVector` | array | Yes | Embedding to search against — must match `numDimensions` |
| `limit` | integer | Yes | Number of documents to return |
| `numCandidates` | integer | ANN only | Candidate pool size before narrowing to `limit`; controls recall vs. latency |
| `exact` | boolean | No | `true` = exact ENN (exhaustive); `false`/absent = ANN (HNSW) |
| `filter` | document | No | Pre-filter expression; fields must be declared as `"type": "filter"` in index |

### ANN vs. ENN

**ANN (Approximate Nearest Neighbors)** — default:
- Uses HNSW algorithm; does NOT scan every vector
- `numCandidates` controls how many candidates are examined before narrowing to `limit`
- Recommended minimum: `numCandidates >= limit × 20`
- Target recall: 90–95% overlap with ENN at reasonable latency

**ENN (Exact Nearest Neighbors)**:
- Exhaustively computes distance to every indexed vector
- Set `"exact": true`; do not set `numCandidates`
- Use for: small datasets (< 100K vectors), accuracy validation, or when recall must be 100%
- Latency scales linearly with collection size

### Score Output

Vector search scores are exposed via the `vectorSearchScore` metadata:

```javascript
{
  "$project": {
    "title": 1,
    "score": { "$meta": "vectorSearchScore" }
  }
}
```

Score range: 0 to 1, where 1 = maximum similarity. Pre-filtering does NOT affect score values.

### Complete Query Example

```python
def vector_search(collection, query_embedding, category=None, limit=10):
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": limit * 20,
                "limit": limit,
                **({"filter": {"category": category}} if category else {})
            }
        },
        {
            "$project": {
                "embedding": 0,           # Always exclude embedding from results
                "title": 1,
                "body": 1,
                "score": { "$meta": "vectorSearchScore" }
            }
        }
    ]
    return list(collection.aggregate(pipeline))
```

### Restrictions

- Cannot be used in `$lookup` sub-pipelines (can pass `$vectorSearch` results into `$lookup` as input)
- Cannot be used in `$facet`
- Cannot be used in view definitions
- Cannot appear after other pipeline stages
- `numCandidates` must be >= `limit`; maximum is 10,000

---

## 3. Hybrid Search ($rankFusion and $scoreFusion)

Hybrid search combines `$vectorSearch` (semantic/dense) with `$search` (full-text/sparse) in a single pipeline for better relevance than either alone.

### When to Use Hybrid Search

| Approach | Use When |
|----------|----------|
| Vector only | Query intent is purely semantic; no exact terms needed |
| Full-text only | Exact keyword matching; product codes, names, technical terms |
| Hybrid | Unpredictable query intent; best of both worlds; production recommendation systems |

### $rankFusion (MongoDB 8.0+)

Uses Reciprocal Rank Fusion (RRF) — combines results based on rank position, not scores.

**RRF formula:** `score = Σ(weight × 1/(rank_constant + rank))` where `rank_constant = 60` (fixed).

```javascript
[
  {
    "$rankFusion": {
      "input": {
        "pipelines": {
          "vectorPipeline": [
            {
              "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": 100,
                "limit": 50
              }
            }
          ],
          "fullTextPipeline": [
            {
              "$search": {
                "index": "text_index",
                "text": {
                  "query": query_text,
                  "path": ["title", "description"],
                  "fuzzy": { "maxEdits": 2 }
                }
              }
            },
            { "$limit": 50 }
          ]
        }
      },
      "combination": {
        "weights": {
          "vectorPipeline": 1.0,
          "fullTextPipeline": 0.8
        }
      },
      "scoreDetails": true
    }
  },
  {
    "$project": {
      "title": 1,
      "score": { "$meta": "score" },
      "scoreDetails": { "$meta": "scoreDetails" }
    }
  },
  { "$sort": { "score": -1 } },
  { "$limit": 10 }
]
```

### $scoreFusion (MongoDB 8.2+)

Uses normalized score combination — merges results based on actual relevance scores (usually 0–1), weighted and averaged.

```javascript
[
  {
    "$scoreFusion": {
      "input": {
        "pipelines": {
          "semanticPipeline": [
            {
              "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": 150,
                "limit": 50
              }
            }
          ],
          "keywordPipeline": [
            {
              "$search": {
                "index": "text_index",
                "text": { "query": query_text, "path": "content" }
              }
            },
            { "$limit": 50 }
          ]
        }
      },
      "combination": {
        "weights": {
          "semanticPipeline": 0.6,
          "keywordPipeline": 0.4
        }
      }
    }
  }
]
```

### $rankFusion vs. $scoreFusion

| Aspect | $rankFusion | $scoreFusion |
|--------|-------------|--------------|
| Algorithm | Reciprocal Rank Fusion (position-based) | Weighted score normalization |
| MongoDB version | 8.0+ | 8.2+ |
| Sensitivity | Insensitive to score scale differences | Sensitive to score normalization |
| Use case | Default choice; easier to reason about | Fine-grained control; complex weighting |
| Rank constant | 60 (fixed) | N/A |

### Sub-Pipeline Constraints

Both `$rankFusion` and `$scoreFusion` sub-pipelines support only: `$search`, `$vectorSearch`, `$match`, `$sort`, `$geoNear`. No `$project`, no `$lookup`. Sub-pipelines execute serially (not in parallel) against the same collection.

### Multiple Vector Pipelines

Combine two different embedding fields (e.g., title + body):

```javascript
"pipelines": {
  "titleVector": [
    { "$vectorSearch": { "path": "title_embedding", "numCandidates": 50, "limit": 25, ... } }
  ],
  "bodyVector": [
    { "$vectorSearch": { "path": "body_embedding", "numCandidates": 100, "limit": 50, ... } }
  ]
}
```

---

## 4. Voyage AI Auto-Embedding (2025)

### Acquisition Context

MongoDB acquired Voyage AI in February 2025 for $220M. Voyage AI produces embedding and reranking models that are now natively integrated into Atlas Vector Search. The strategic goal: combine OLTP storage, vector index, and embedding model in one unified system — eliminating external embedding API dependencies.

### Auto-Embedding Feature

**Public Preview** as of May 2026 (MongoDB Community Edition; Atlas coming soon).

Auto-embedding automates the full embedding lifecycle:
- Generates embeddings at index creation (batch, initial sync)
- Re-embeds only affected fields on document insert/update (field-level delta detection)
- Uses asynchronous dynamic batch processing optimized for each model's max token limit
- Eliminates custom change-stream pipelines and manual re-embedding logic

### Available Voyage 4 Models (current generation)

| Model | Dimensions | Best For |
|-------|-----------|---------|
| `voyage-4-large` | 2048 | High-accuracy retrieval; large-scale production |
| `voyage-4` | 1024 | General-purpose; best price/performance |
| `voyage-4-lite` | 512 | Lightweight; cost-sensitive applications |
| `voyage-code-3` | 1024 | Code search, technical documentation |
| `voyage-multimodal-3.5` | 1024 | Text + images + video (GA) |

Earlier models still available: `voyage-3-large` (2048d), `voyage-3` (1024d), `voyage-3-lite` (512d), `voyage-multilingual-2` (1024d), `voyage-context-3` (1024d).

**All Voyage 4 models are quantization-aware** — specifically trained to preserve semantic properties after scalar or binary quantization, making them ideal for memory-efficient deployments.

### Embedding Generation with Voyage SDK

```python
import voyageai

client = voyageai.Client(api_key=VOYAGE_API_KEY)

def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed document chunks for indexing."""
    result = client.embed(
        texts,
        model="voyage-4",
        input_type="document"   # "document" for indexing, "query" for search
    )
    return result.embeddings

def embed_query(query: str) -> list[float]:
    """Embed a search query."""
    result = client.embed(
        [query],
        model="voyage-4",
        input_type="query"
    )
    return result.embeddings[0]
```

**Critical:** Use `input_type="document"` when embedding corpus text and `input_type="query"` when embedding search queries. Mismatching degrades recall significantly (asymmetric embedding space).

### Voyage AI Reranking

Voyage AI also provides reranker models that can be used after `$vectorSearch` to re-score candidates:

```python
reranking = client.rerank(
    query=query_text,
    documents=[doc["text"] for doc in candidates],
    model="rerank-2",
    top_k=5
)
```

Apply reranking as a post-processing step on the `limit`-sized result set from `$vectorSearch`.

---

## 5. RAG Architecture Patterns with Atlas

### Core RAG Pipeline

```
[Source Documents]
       ↓
[Chunk + Embed]          ← Voyage AI / OpenAI / Cohere
       ↓
[MongoDB Atlas collection]
  - chunk text
  - embedding vector
  - metadata (source, page, date, category)
       ↓
[Atlas Vector Search Index]
       ↓
User Query → Embed Query → $vectorSearch → Top-K chunks → LLM → Answer
```

### Document Chunking Strategies

| Strategy | Chunk Size | Overlap | Use When |
|----------|-----------|---------|---------|
| Fixed-size | 512–1000 tokens | 50–100 tokens | Simple; baseline; mixed content |
| Recursive/paragraph | Variable | Optional | Structured documents (markdown, HTML) |
| Semantic | Variable | None | When paragraphs have natural semantic boundaries |
| Sliding window | Fixed | Large (50–70%) | Dense, highly contextual content |

**Recommendations:**
- Child chunk size for parent-doc retrieval: 100–300 tokens
- Parent chunk: 1000–2000 tokens or full document section
- Always include context in the chunk text, not just the raw excerpt

### Metadata Filtering Pattern

Store rich metadata alongside embeddings to enable pre-filtered vector search:

```python
# Document schema for RAG
doc = {
    "_id": ObjectId(),
    "text": "chunk content...",
    "embedding": [...],          # 1024-dimensional vector
    "metadata": {
        "source": "docs/api.md",
        "section": "authentication",
        "created_at": datetime.utcnow(),
        "product": "Atlas",
        "version": "7.0"
    },
    # Flatten top-level fields for vectorSearch filter access:
    "source": "docs/api.md",
    "product": "Atlas",
    "version": "7.0"
}
```

**Note:** Filter fields in `$vectorSearch` must be at the **top level** of the document (not nested inside a subdocument). Declare them as `"type": "filter"` fields in the vector index definition.

```javascript
// Filtered RAG query
{
  "$vectorSearch": {
    "index": "vector_index",
    "path": "embedding",
    "queryVector": query_embedding,
    "filter": {
      "product": "Atlas",
      "version": { "$in": ["6.0", "7.0", "8.0"] }
    },
    "numCandidates": 200,
    "limit": 10
  }
}
```

### Parent Document Retrieval

Search on small child chunks; return full parent documents to the LLM for richer context.

```python
from langchain_mongodb.retrievers import MongoDBAtlasParentDocumentRetriever
from langchain_voyageai import VoyageAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

embedding_model = VoyageAIEmbeddings(model="voyage-4")

child_splitter = RecursiveCharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=20
)

retriever = MongoDBAtlasParentDocumentRetriever.from_connection_string(
    connection_string=MONGODB_URI,
    child_splitter=child_splitter,
    embedding_model=embedding_model,
    database_name="rag_db",
    collection_name="documents",
    text_key="page_content",
    relevance_score_fn="dotProduct",
    search_kwargs={"k": 10}
)

# Add documents (stores both parent and children in same collection)
retriever.add_documents(source_docs)

# Query — returns parent documents, not child chunks
results = retriever.invoke("What is Atlas Vector Search?")
```

**Storage structure (single collection):**
- Child docs: `{ page_content: "chunk...", embedding: [...], doc_id: <parent _id> }`
- Parent docs: `{ _id: ObjectId, page_content: "full text...", metadata: {...} }`
- Only child documents have embeddings; parent docs are fetched by `doc_id` join

### Hybrid RAG (Vector + Full-Text)

For production RAG, combine vector search with keyword search using `$rankFusion`:

```python
def hybrid_rag_pipeline(query_text, query_embedding, top_k=10):
    return [
        {
            "$rankFusion": {
                "input": {
                    "pipelines": {
                        "vectorSearch": [
                            {
                                "$vectorSearch": {
                                    "index": "vector_index",
                                    "path": "embedding",
                                    "queryVector": query_embedding,
                                    "numCandidates": top_k * 20,
                                    "limit": top_k * 2
                                }
                            }
                        ],
                        "fullTextSearch": [
                            {
                                "$search": {
                                    "index": "text_index",
                                    "text": {
                                        "query": query_text,
                                        "path": ["text", "title"],
                                        "fuzzy": {"maxEdits": 1}
                                    }
                                }
                            },
                            { "$limit": top_k * 2 }
                        ]
                    }
                },
                "combination": {
                    "weights": {
                        "vectorSearch": 1.0,
                        "fullTextSearch": 0.7
                    }
                }
            }
        },
        { "$project": { "embedding": 0, "text": 1, "title": 1, "score": { "$meta": "score" } } },
        { "$sort": { "score": -1 } },
        { "$limit": top_k }
    ]
```

### Re-ranking Pipeline

After initial retrieval, re-rank with Voyage reranker for precision:

```python
def rag_with_reranking(query, collection, limit=5, candidates=20):
    # Step 1: Vector search to get candidates
    embedding = embed_query(query)
    raw_results = vector_search(collection, embedding, limit=candidates)
    
    # Step 2: Rerank candidates with Voyage AI
    reranked = voyage_client.rerank(
        query=query,
        documents=[r["text"] for r in raw_results],
        model="rerank-2",
        top_k=limit
    )
    
    # Step 3: Return reranked results
    return [raw_results[r.index] for r in reranked.results]
```

---

## 6. Embedding Pipeline Design

### Architecture Options

| Approach | Latency | Throughput | Freshness | Complexity |
|----------|---------|-----------|----------|-----------|
| Manual batch (Python script) | Minutes/hours | High | Stale until next run | Low |
| Atlas Triggers (serverless) | Seconds | Medium | Near-real-time | Medium |
| Change Stream + worker service | Seconds | High | Real-time | High |
| Auto-Embedding (Voyage AI built-in) | Seconds | High | Real-time (field-level delta) | None |

### Batch Embedding Pipeline (Python)

```python
import voyageai
from pymongo import MongoClient
from pymongo.operations import UpdateOne
from itertools import islice

client = voyageai.Client()
db = MongoClient(MONGODB_URI)["mydb"]
collection = db["documents"]

def batch(iterable, n):
    """Yield successive n-sized chunks."""
    it = iter(iterable)
    while chunk := list(islice(it, n)):
        yield chunk

# Batch embed documents without embeddings
docs = list(collection.find({"embedding": {"$exists": False}}))

for doc_batch in batch(docs, 128):   # Voyage allows up to 128 per request
    texts = [f"Title: {d['title']}\n{d['body']}" for d in doc_batch]
    result = client.embed(texts, model="voyage-4", input_type="document")
    
    bulk_ops = [
        UpdateOne(
            {"_id": d["_id"]},
            {"$set": {"embedding": emb}}
        )
        for d, emb in zip(doc_batch, result.embeddings)
    ]
    collection.bulk_write(bulk_ops)
```

### Atlas Triggers Approach (Real-Time)

Configure an Atlas Database Trigger on insert/update events:

```javascript
// Atlas Trigger function (JavaScript, runs on Atlas serverless)
exports = async function(changeEvent) {
  const docId = changeEvent.documentKey._id;
  const doc = changeEvent.fullDocument;
  
  if (!doc || !doc.body) return;
  
  // Call external embedding API
  const response = await context.http.post({
    url: "https://api.voyageai.com/v1/embeddings",
    headers: {
      "Authorization": [`Bearer ${context.values.get("VOYAGE_API_KEY")}`],
      "Content-Type": ["application/json"]
    },
    body: JSON.stringify({
      input: [doc.body],
      model: "voyage-4",
      input_type: "document"
    })
  });
  
  const embedding = JSON.parse(response.body.text()).data[0].embedding;
  
  // Write embedding back to document
  const mongodb = context.services.get("mongodb-atlas");
  await mongodb.db("mydb").collection("documents").updateOne(
    { _id: docId },
    { $set: { embedding: embedding } }
  );
};
```

**Trigger configuration:** Watch for `insert` and `update` events; use `match` expression to only fire when text fields change (avoid infinite loops from embedding updates).

### Change Stream Worker (Node.js)

```javascript
const { MongoClient } = require("mongodb");
const voyageai = require("voyageai");  // npm install voyageai

const voyage = new voyageai.VoyageAIClient({ apiKey: process.env.VOYAGE_API_KEY });

async function generateEmbedding(text) {
  const result = await voyage.embed({
    input: [text],
    model: "voyage-4",
    inputType: "document"
  });
  return result.embeddings[0];
}

async function startEmbeddingWorker() {
  const mongo = await MongoClient.connect(process.env.MONGODB_URI);
  const collection = mongo.db("mydb").collection("documents");
  
  const changeStream = collection.watch([
    { $match: { operationType: { $in: ["insert", "update"] } } }
  ]);
  
  for await (const change of changeStream) {
    const doc = change.fullDocument || 
                await collection.findOne({ _id: change.documentKey._id });
    
    if (!doc?.body) continue;
    
    // Generate embedding via Voyage AI
    const embedding = await generateEmbedding(doc.body);
    
    await collection.updateOne(
      { _id: doc._id },
      { $set: { embedding, embeddedAt: new Date() } }
    );
  }
}
```

### Auto-Embedding (Native Atlas / Voyage AI)

When using Auto-Embedding (currently public preview on Community Edition, coming to Atlas):
- Define the embedding model directly in the index configuration
- Atlas handles embedding generation, batching, delta detection, and sync
- No external pipeline required
- Re-embeds only documents where indexed fields changed (field-level delta detection)
- Dynamic batching optimizes token throughput per model limits

---

## 7. Vector Search Nodes (Dedicated Tier)

### Architecture Overview

By default, `mongod` (data node) and `mongot` (search node process) run on the same machine — resource contention under load. Dedicated Search Nodes move `mongot` to separate infrastructure for workload isolation.

### Node Types and Tiers

| Tier | Profile | CPU | RAM | Disk:RAM | Best For |
|------|---------|-----|-----|----------|---------|
| S20 (High-CPU) | High CPU, standard RAM | High | Medium | ~6:1 | High-QPS workloads; concurrent queries |
| S30 (Low-CPU) | Lower CPU, standard RAM | Medium | Medium | ~6:1 | Moderate query loads; cost optimization |
| S50-storage | Storage-optimized | Low | Low | ~25:1 | Large quantized indexes; cost-efficient scale |

**Minimum for production:** S30 or higher on a dedicated M10+ cluster.

### When to Use Dedicated Search Nodes

Use dedicated Search Nodes when:
- Index build time or query latency is affected by data node load
- RAM for vector indexes exceeds 20–30% of data node RAM
- Vector query QPS is > 10 and/or latency p99 > 100ms
- Index size > 1GB and growing

Keep on shared nodes for:
- Development, prototyping, or low-traffic applications
- Very small collections (< 100K vectors)

### Memory Sizing Formula

```
Index RAM = numVectors × numDimensions × bytesPerDimension

Bytes per dimension:
  float32 (no quantization): 4 bytes
  int8 (scalar quantization): 1 byte
  int1 (binary quantization): 0.125 bytes (1/8 byte)
```

**Examples:**
| Scenario | Vectors | Dimensions | Quantization | Index RAM |
|----------|---------|-----------|--------------|----------|
| 1M docs, OpenAI ada-002 | 1M | 1536 | None | ~6 GB |
| 1M docs, Voyage 4 | 1M | 1024 | None | ~4 GB |
| 1M docs, Voyage 4 | 1M | 1024 | Scalar | ~1 GB |
| 1M docs, Voyage 4 | 1M | 1024 | Binary | ~128 MB |
| 5.5M docs, Voyage 3-large (2048d) | 5.5M | 2048 | Scalar | ~22 GB |
| 5.5M docs, Voyage 3-large (2048d) | 5.5M | 2048 | Binary | ~3.4 GB |

**RAM headroom rule:** Search node RAM must be at least 10% larger than total vector index size.

### Horizontal Scaling

Scale from minimum 2 Search Nodes up to 32 nodes for throughput:
- Each additional node adds linear QPS capacity
- Latency improves via parallel query routing
- Scaling out (more nodes) vs. scaling up (bigger tier) are independent operations

### Storage-Optimized Nodes

Introduced in 2025 for workloads where binary quantization shifts the bottleneck to storage rather than RAM. With binary quantization:
- Index RAM is reduced 24× vs. float32
- Disk space remains large (full vector data stored for rescoring)
- S50-storage provides high disk:RAM ratio at lower cost than S20/S30

### Cloud Provider Availability

Search Nodes are available on AWS, Azure, and GCP (subset of regions for AWS/Azure). Verify region support before cluster creation. Cross-cloud migration may require index rebuild.

---

## 8. Performance Tuning

### The Primary Tuning Knobs

| Lever | Controls | Trade-off |
|-------|---------|-----------|
| `numCandidates` | Recall vs. query latency | More candidates = better recall, higher latency |
| `maxConnections` (m) | Graph connectivity | Higher = better recall, more RAM, slower build |
| `efConstruction` | Graph build quality | Higher = better recall (baked in), no query latency impact |
| Quantization | RAM vs. recall | Binary: 24× RAM savings, ~5–10% recall drop (recovered by rescoring) |
| Search Node tier | QPS ceiling | Bigger tier or more nodes = higher concurrent QPS |

### numCandidates Tuning Guide

The `numCandidates` parameter controls the efSearch equivalent in HNSW — how many candidates the graph traversal accumulates before stopping.

```
Starting rule:  numCandidates = limit × 20
Target recall:  90–95% overlap with ENN (Jaccard similarity)
Max value:      10,000
```

**With quantization, increase numCandidates to compensate:**

| Quantization | numCandidates multiplier vs. float32 |
|-------------|--------------------------------------|
| Float32 (none) | 1× baseline |
| Scalar (int8) | ~1.5× to achieve same recall |
| Binary (int1) | ~3–5× to achieve same recall (rescoring partially compensates) |

**Practical calibration:**
1. Run ENN baseline (`"exact": true`) on a sample of 50 queries; record result sets
2. Run ANN with increasing `numCandidates`; measure Jaccard similarity vs. ENN
3. Stop when Jaccard >= 0.90–0.95 at acceptable latency

### Recall vs. Latency Benchmark Data

From MongoDB's Amazon Reviews benchmark (15.3M vectors, voyage-3-large, 2048d):

| Configuration | numCandidates | Recall | P50 latency |
|---------------|--------------|--------|-------------|
| Float32 ANN | 100 | ~95% | ~35ms |
| Scalar (int8) | 100 | ~99% | ~25ms |
| Binary (int1) | 100 | ~91% | ~10ms |
| Binary (int1) | 500 | ~97% | ~40ms |
| Binary + rescore | 100 | ~95% | ~20ms |

All quantized methods maintain < 50ms latency at 90–95% recall for 15.3M vectors at highest dimensionality.

### Quantization Configuration Reference

```python
# Scalar quantization — int8, 4× memory savings
scalar_index = {
    "fields": [{
        "type": "vector",
        "path": "embedding",
        "numDimensions": 1024,
        "similarity": "cosine",
        "quantization": "scalar"    # Converts float32 → int8
    }]
}

# Binary quantization — 1-bit, 24× memory savings + auto-rescoring
binary_index = {
    "fields": [{
        "type": "vector",
        "path": "embedding",
        "numDimensions": 1024,
        "similarity": "cosine",
        "quantization": "binary"    # Converts float32 → 1-bit; Atlas adds rescoring step
    }]
}
```

**Binary quantization rescoring:** When `"quantization": "binary"` is set, Atlas automatically adds a rescoring step — the top `numCandidates` binary results are reordered using full-precision float32 vectors on disk before returning the top `limit`. This partially restores recall lost to quantization at minimal latency cost.

### BSON BinData Vector Format

For large deployments, store embeddings as BSON binary instead of float arrays:

```python
from bson.binary import Binary, BinaryVectorDtype
import numpy as np

def to_bson_vector(array: list[float]) -> Binary:
    """Store as BSON float32 binary — 3× less disk space than array storage."""
    return Binary.from_vector(
        np.array(array, dtype=np.float32),
        BinaryVectorDtype.FLOAT32
    )

# For int8 scalar quantization storage (min-max normalization):
def to_bson_int8(array: list[float]) -> Binary:
    arr = np.array(array, dtype=np.float32)
    min_val, max_val = arr.min(), arr.max()
    # Scale to [-128, 127] using the actual range of this vector
    if max_val == min_val:
        int8_arr = np.zeros_like(arr, dtype=np.int8)
    else:
        scaled = (arr - min_val) / (max_val - min_val) * 255 - 128
        int8_arr = np.clip(np.round(scaled), -128, 127).astype(np.int8)
    return Binary.from_vector(int8_arr, BinaryVectorDtype.INT8)
# Note: Atlas performs its own quantization internally when "quantization": "scalar"
# is set in the index definition — prefer that over manual pre-quantization.
```

Benefits: ~60% smaller document footprint, faster hydration during ID lookups, less network transfer.

### Query Optimization Checklist

- [ ] Always `$project` to exclude the embedding field from results (`"embedding": 0`)
- [ ] Declare all filter fields as `"type": "filter"` in the index definition
- [ ] Use `numCandidates >= limit × 20` as the starting point
- [ ] Prefer scalar quantization as the default; binary for cost-sensitive large indexes
- [ ] Store embeddings as BSON BinData for collections > 1M documents
- [ ] Use dedicated Search Nodes for production (M10+ data nodes + S30+ search nodes)
- [ ] Enable `scoreDetails: true` in `$rankFusion`/`$scoreFusion` during debugging
- [ ] Benchmark with ENN first to establish recall baseline before tuning ANN

---

## 9. Multi-Vector and Advanced Patterns

### Multiple Embeddings Per Document

Store and index multiple embedding fields in a single document for different aspects:

```python
# Document with multiple embedding fields
doc = {
    "_id": ObjectId(),
    "title": "Introduction to RAG",
    "body": "Retrieval-Augmented Generation...",
    "code_snippet": "def rag_pipeline(query): ...",
    
    # Multiple embeddings
    "title_embedding": embed_query(doc["title"]),           # 512d via voyage-4-lite
    "body_embedding": embed_document(doc["body"]),          # 1024d via voyage-4
    "code_embedding": embed_code(doc["code_snippet"]),      # 1024d via voyage-code-3
}

# Index definition with multiple vector fields
# All vector fields can share one index — each declares its own path and numDimensions
index = SearchIndexModel(
    definition={
        "fields": [
            { "type": "vector", "path": "title_embedding", "numDimensions": 512, "similarity": "dotProduct" },
            { "type": "vector", "path": "body_embedding", "numDimensions": 1024, "similarity": "dotProduct" },
            { "type": "vector", "path": "code_embedding", "numDimensions": 1024, "similarity": "dotProduct" },
            { "type": "filter", "path": "category" }
        ]
    },
    name="multi_vector_index",   # Single index covers all three vector paths
    type="vectorSearch"
)
```

Then combine with `$rankFusion`:

```javascript
{
  "$rankFusion": {
    "input": {
      "pipelines": {
        "titleSearch": [
          { "$vectorSearch": { "index": "multi_vector_index", "path": "title_embedding", "queryVector": title_emb, "numCandidates": 100, "limit": 20 } }
        ],
        "bodySearch": [
          { "$vectorSearch": { "index": "multi_vector_index", "path": "body_embedding", "queryVector": body_emb, "numCandidates": 200, "limit": 50 } }
        ]
      }
    },
    "combination": { "weights": { "titleSearch": 1.5, "bodySearch": 1.0 } }
  }
}
```

### Late Chunking Pattern

Late chunking embeds full documents with a long-context model (Voyage context-3) but produces chunk-level embeddings that retain whole-document context:

```python
# voyage-context-3 supports late chunking
result = client.embed(
    texts=document_chunks,              # Individual chunks
    model="voyage-context-3",
    input_type="document",
    # Late chunking: model encodes full document context per chunk
    # Each chunk embedding reflects surrounding context
)
```

Benefits over naive chunking: better recall on queries that refer to context outside a chunk boundary.

### Sparse + Dense Hybrid

For technical corpora (code, APIs, medical), combine dense (Voyage) with sparse (Atlas `$search` text) via `$rankFusion`. Sparse retrieval handles exact term matching (function names, error codes) that dense vectors handle poorly.

### Vector Arrays (ColBERT-style Multi-Vector)

MongoDB supports storing arrays of vectors per document for token-level multi-vector retrieval:

```python
# Store multiple vectors per document (e.g., one per token/sentence)
doc = {
    "_id": ObjectId(),
    "text": "...",
    "token_embeddings": [
        [0.1, 0.2, ...],   # Token 1 embedding
        [0.3, 0.4, ...],   # Token 2 embedding
        # ...
    ]
}

# Index multi-vector fields (using vectorSearch index on array field)
# $vectorSearch on an array path searches all vectors in the array
# and returns the max score (MaxSim operation)
```

**Note:** Native ColBERT (MaxSim over all token pairs) is not fully implemented in Atlas as of 2025/2026. The recommended approach is to use sentence-level embeddings per paragraph with `$rankFusion` for multi-granularity retrieval instead.

### Cross-Collection Vector Search

`$vectorSearch` operates on a single collection. For cross-collection search, use `$unionWith`:

```javascript
// Search documents and blog posts simultaneously
[
  { "$vectorSearch": { "index": "doc_vector_index", "path": "embedding", "queryVector": emb, "numCandidates": 200, "limit": 10 } },
  { "$project": { "text": 1, "score": { "$meta": "vectorSearchScore" }, "source": { "$literal": "docs" } } },
  {
    "$unionWith": {
      "coll": "blog_posts",
      "pipeline": [
        { "$vectorSearch": { "index": "blog_vector_index", "path": "embedding", "queryVector": emb, "numCandidates": 200, "limit": 10 } },
        { "$project": { "text": 1, "score": { "$meta": "vectorSearchScore" }, "source": { "$literal": "blog" } } }
      ]
    }
  },
  { "$sort": { "score": -1 } },
  { "$limit": 10 }
]
```

### Geospatial + Vector Hybrid

Combine geospatial filtering with semantic search using `$rankFusion` with `$geoNear`:

```javascript
{
  "$rankFusion": {
    "input": {
      "pipelines": {
        "locationPipeline": [
          { "$geoNear": { "near": { "type": "Point", "coordinates": [lng, lat] }, "distanceField": "dist", "maxDistance": 5000 } }
        ],
        "semanticPipeline": [
          { "$vectorSearch": { "index": "vector_index", "path": "embedding", "queryVector": emb, "numCandidates": 200, "limit": 50 } }
        ]
      }
    },
    "combination": { "weights": { "locationPipeline": 0.4, "semanticPipeline": 0.6 } }
  }
}
```

---

## 10. Anti-Patterns

### AP-1: numCandidates Too Low

**Problem:** Setting `numCandidates` close to `limit` (e.g., `limit: 5, numCandidates: 10`) causes the HNSW graph traversal to terminate too early, yielding poor recall (< 70%).

**Fix:** Use `numCandidates >= limit × 20`. Measure recall against ENN baseline before going to production.

```python
# BAD
{ "limit": 10, "numCandidates": 15 }

# GOOD
{ "limit": 10, "numCandidates": 200 }
```

---

### AP-2: Missing Filter Field Declaration

**Problem:** Using a field in `$vectorSearch` `"filter"` without declaring it as `"type": "filter"` in the index definition causes a full collection scan on that field — O(N) behavior that negates the entire point of a vector index.

**Fix:** Always add filter fields to the index definition.

```python
# BAD: filtering on "category" without index declaration
# vectorSearch will scan the entire collection for category values

# GOOD: index definition includes filter field
{
    "fields": [
        { "type": "vector", "path": "embedding", "numDimensions": 1024, ... },
        { "type": "filter", "path": "category" },   # Required for efficient filtering
    ]
}
```

---

### AP-3: Wrong Similarity Function

**Problem:** Using `euclidean` for normalized embeddings, or `cosine` for raw unnormalized embeddings when the embedding provider expects `dotProduct`.

**Fix:** Match similarity metric to the embedding model:
- Voyage AI models: use `dotProduct` (embeddings are L2-normalized)
- OpenAI `text-embedding-3-*`: use `cosine` or `dotProduct` (both work; cosine is safer)
- HuggingFace sentence transformers: check model card; most use `cosine`
- Cohere `embed-english-v3.0`: use `dotProduct` (embeddings normalized)

**Critical:** The similarity metric is baked into the index at creation time and cannot be changed without rebuilding the index.

---

### AP-4: Embedding Dimension Mismatch

**Problem:** The `queryVector` dimensions at query time don't match the `numDimensions` declared in the index. This causes an error or silently wrong results.

**Fix:** `numDimensions` in the index must exactly match the model's output. Always validate on startup:

```python
def validate_embedding_config(collection, index_name, embedding_model):
    test_embedding = embed_query("test")
    
    # Check index numDimensions matches
    index_info = collection.list_search_indexes(index_name)
    index_dims = index_info["fields"][0]["numDimensions"]
    
    assert len(test_embedding) == index_dims, (
        f"Embedding model produces {len(test_embedding)}d vectors "
        f"but index expects {index_dims}d"
    )
```

---

### AP-5: Not Using Quantization for Large Indexes

**Problem:** A 10M-vector, 1536-dimensional float32 index requires ~60GB RAM. Without quantization, this either forces very expensive Search Node tiers or degrades query performance as the OS swaps the index to disk.

**Fix:** Enable scalar quantization by default for indexes > 1M vectors; binary for > 5M vectors:

```json
{ "quantization": "scalar" }   // 4× memory savings, <1% recall drop with proper numCandidates
{ "quantization": "binary" }   // 24× memory savings, ~5% recall drop (offset by rescoring)
```

---

### AP-6: Using the Same Embedding Model for Documents and Queries Without `input_type`

**Problem:** Voyage AI and some other models use different internal representations for document indexing vs. query encoding. Passing `input_type="document"` for queries (or omitting `input_type`) produces embeddings in the wrong part of the embedding space, dramatically reducing recall.

**Fix:** Always specify `input_type`:
- `input_type="document"` when embedding text for storage/indexing
- `input_type="query"` when embedding user queries at search time

---

### AP-7: Returning Embeddings in Query Results

**Problem:** Including the embedding field in `$project` outputs arrays of 1024+ floats per document — massively inflating network transfer and client memory usage.

**Fix:** Always exclude the embedding field:

```javascript
{ "$project": { "embedding": 0, "title": 1, "text": 1, "score": { "$meta": "vectorSearchScore" } } }
```

---

### AP-8: No Evaluation Framework

**Problem:** Deploying vector search without measuring recall leads to silent quality degradation — users see bad results but there's no metric to detect or debug it.

**Fix:** Build a ground-truth evaluation set of 50–100 labeled query→result pairs. Measure:
- **Recall@K:** Fraction of expected results in top-K
- **NDCG@K:** Normalized Discounted Cumulative Gain
- **MRR:** Mean Reciprocal Rank

Run ENN queries against the same set to establish the ceiling; then tune ANN `numCandidates` to reach 90–95% of the ENN baseline.

---

### AP-9: Ignoring Hybrid Search for Production

**Problem:** Pure vector search alone fails on queries with important keywords (product names, error codes, proper nouns) that the embedding model generalizes away. Recall for precise queries can drop to 40–60%.

**Fix:** Use `$rankFusion` with both `$vectorSearch` and `$search` in production RAG pipelines. The cost is negligible and the recall improvement for keyword-heavy queries is substantial.

---

### AP-10: Chunking Without Overlap

**Problem:** Fixed-size chunks with zero overlap split sentences mid-thought. Queries that semantically span a chunk boundary retrieve neither chunk reliably.

**Fix:** Use 10–20% overlap between adjacent chunks. For sentence-boundary chunking, always split on sentence boundaries and include the last sentence of the previous chunk as overlap.

---

## References

**Official MongoDB Docs:**
- [Vector Search Index Types](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-type/)
- [Run Vector Search Queries ($vectorSearch)](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-stage/)
- [Hybrid Search](https://www.mongodb.com/docs/atlas/atlas-vector-search/hybrid-search/)
- [$rankFusion Aggregation](https://www.mongodb.com/docs/manual/reference/operator/aggregation/rankfusion/)
- [RAG with MongoDB](https://www.mongodb.com/docs/atlas/atlas-vector-search/rag/)
- [Parent Document Retrieval](https://www.mongodb.com/docs/atlas/ai-integrations/langchain/parent-document-retrieval/)
- [Vector Quantization](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-quantization/)
- [Deployment Options](https://www.mongodb.com/docs/atlas/atlas-vector-search/deployment-options/)
- [Benchmark Overview](https://www.mongodb.com/docs/atlas/atlas-vector-search/benchmark/overview/)
- [Benchmark Results](https://www.mongodb.com/docs/atlas/atlas-vector-search/benchmark/results/)

**MongoDB Blog:**
- [Voyage AI Acquisition Announcement (Feb 2025)](https://investors.mongodb.com/news-releases/news-release-details/mongodb-announces-acquisition-voyage-ai-enable-organizations)
- [Auto-Embedding Introduction](https://www.mongodb.com/company/blog/product-release-announcements/unlocking-ai-search-introducing-automated-embedding-in-mongodb-vector-search)
- [$rankFusion Deep Dive](https://www.mongodb.com/company/blog/technical/harness-power-atlas-search-vector-search-with-rankfusion)
- [Native Hybrid Search Announcement](https://www.mongodb.com/company/blog/product-release-announcements/boost-search-relevance-mongodb-atlas-native-hybrid-search)
- [Scaling with Quantization + Voyage AI](https://www.mongodb.com/company/blog/technical/scaling-vector-search-mongodb-atlas-quantization-voyage-ai-embeddings)
- [Binary Quantization + Rescoring](https://www.mongodb.com/company/blog/product-release-announcements/binary-quantization-rescoring-96-less-memory-faster-search)
- [Search Node Sizing Guide](https://www.mongodb.com/company/blog/technical/the-art-and-science-of-sizing-search-nodes)
- [Search Nodes GA](https://www.mongodb.com/company/blog/product-release-announcements/dedicated-search-nodes-vector-search-now-in-general-availability)
- [New Benchmark Factors](https://www.mongodb.com/company/blog/innovation/new-benchmark-tests-reveal-key-vector-search-performance-factors)

**See Also:**
- [[mongodb-search-ai]] — Atlas Search full-text operators, analyzers, autocomplete
- [[mongodb-atlas-gcp]] — Atlas on GCP including regional Search Node availability
- [[mongodb-atlas-azure]] — Atlas on Azure including Search Node migration
- [[mongodb-atlas-expert]] — Atlas cluster tiers, M-series sizing, Atlas CLI
- [[mongodb-aggregation-pipeline]] — Aggregation pipeline fundamentals
- [[rag-architecture]] — Framework-agnostic RAG design patterns
