# Caching and optimization

- Vectors are cached in SQLite keyed by chunk text digest; re-indexing embeds only new text.
- `VectorStore` loads the vector matrix once per process (TUI keeps one per session).
- FTS5 `bm25()` weights: heading 4, text 1, source 2.
- Results are de-duplicated by the first 300 whitespace-normalised characters of the chunk.
