# Integrations and assumptions

- Ollama with `nomic-embed-text` (768-dim, needs `search_document:` / `search_query:` prefixes, which `embed.py` adds).
- Corpus is plain `.md`/`.txt`; `.json`/`.jsonl` files are ignored.
- Corpus layout: `corpus/skills/<skill>/…` → kind `skill`; `corpus/llms/<set>.llms/…` → kind `llms`;
  `corpus/llms/memory-central/…` → kind `memory`.
- Assumes UTF-8 text; undecodable bytes are replaced.
