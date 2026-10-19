# Architecture

```
corpus/ (.md/.txt) ──corpus.py──▶ chunks ──index.py──▶ SQLite data/mdbx.sqlite
                                                        ├─ chunks            (text, path, source, kind, line)
                                                        ├─ chunks_fts        (FTS5, BM25, porter)
                                                        └─ vectors           (sha1(text) → float32 blob)
query ──search.py──▶ keyword(BM25) ┐
                     semantic(cos) ├─ RRF fusion ─▶ Hit list ─▶ cli.py / tui.py
Ollama /api/embed ◀─ embed.py ─────┘

MQL text ──parser.py──▶ analyze.py (lint) ────────┐
         └────────────▶ optimize.py (static audit) ├─▶ mdbx lint / optimize, mql_lint / mql_optimize (MCP),
                                                    └─▶ mql-lsp diagnostics + quick fixes
```

## Data flow
1. `corpus.iter_chunks` walks `corpus/`, classifies each file (`skill`, `llms`, `memory`) and splits it
   at markdown headings into chunks of at most 1600 characters; each chunk keeps a heading breadcrumb and
   its first line number.
2. `index.build_keyword` truncates and refills `chunks` and `chunks_fts`.
3. `index.build_semantic` embeds only chunk digests with no vector yet, so re-indexing is cheap and resumable.
4. `search.hybrid` ranks with BM25 and cosine similarity separately and fuses with reciprocal-rank fusion (k=60).

5. MQL path (no index involved): `mql/parser.py` parses mongosh text; `analyze.py` lints it; `optimize.py`
   finds each `db.<coll>.find/aggregate/count/update/delete/watch` call (and `const` pipelines), runs the
   offline audit passes, recommends ESR-ordered indexes (recommend-only) and, with `apply=True`, rewrites
   result-preserving fixes until nothing changes (cap `max_iters=3`). Findings carry a corpus `ref` to read with
   `mdbx show`. The CLI, the MCP tool and the language server call the same `optimize()`.

## Decisions
- **One SQLite file** holds text, FTS and vectors: no server, trivially portable.
- **Vectors keyed by text digest**: identical text copied across skills is embedded once.
- **NumPy brute-force cosine**: ~7k vectors × 768 dims fits in memory (~20 MB); no ANN index needed.
- **Hybrid default with keyword fallback**: search still works when Ollama is unreachable.
- **Textual is an optional extra** so the CLI has no TUI dependency.
- **Optimizer is static and offline**: no cluster connection, so no cardinality, existing-index or explain data; blocking findings are reported, never rewritten.
- **Embedding model change purges vectors**: `index.build_semantic` compares `meta.embed_model` with `MDBX_EMBED_MODEL` and deletes all vectors when they differ.
- **Private corpus stays local**: customer-flavoured files are indexed but gitignored.
