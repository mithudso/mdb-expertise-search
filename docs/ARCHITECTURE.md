# Architecture

```
corpus/ (.md/.txt) ──corpus.py──▶ chunks ──index.py──▶ SQLite data/mdbx.sqlite
                                                        ├─ chunks            (text, path, source, kind, line)
                                                        ├─ chunks_fts        (FTS5, BM25, porter)
                                                        └─ vectors           (sha1(text) → float32 blob)
query ──search.py──▶ keyword(BM25) ┐
                     semantic(cos) ├─ RRF fusion ─▶ Hit list ─▶ cli.py / tui.py
Ollama /api/embed ◀─ embed.py ─────┘
```

## Data flow
1. `corpus.iter_chunks` walks `corpus/`, classifies each file (`skill`, `llms`, `memory`) and splits it
   at markdown headings into chunks of at most 1600 characters; each chunk keeps a heading breadcrumb and
   its first line number.
2. `index.build_keyword` truncates and refills `chunks` and `chunks_fts`.
3. `index.build_semantic` embeds only chunk digests with no vector yet, so re-indexing is cheap and resumable.
4. `search.hybrid` ranks with BM25 and cosine similarity separately and fuses with reciprocal-rank fusion (k=60).

## Decisions
- **One SQLite file** holds text, FTS and vectors: no server, trivially portable.
- **Vectors keyed by text digest**: identical text copied across skills is embedded once.
- **NumPy brute-force cosine**: ~7k vectors × 768 dims fits in memory (~20 MB); no ANN index needed.
- **Hybrid default with keyword fallback**: search still works when Ollama is unreachable.
- **Textual is an optional extra** so the CLI has no TUI dependency.
- **Private corpus stays local**: customer-flavoured files are indexed but gitignored.
