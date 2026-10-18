# Runbook: rebuild the index

1. Refresh corpus (author machine): `scripts/sync_corpus.sh`. Elsewhere: edit `corpus/` or set `MDBX_CORPUS`.
2. `rm data/mdbx.sqlite` if the embedding model changed.
3. `.venv/bin/mdbx index` (needs Ollama for vectors; ~7k chunks takes a few minutes).
4. Verify: `.venv/bin/mdbx stats` — `vectors` should be > 0 and `search "shard key"` should return hits.
