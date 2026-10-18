# Requirements

Functional: index a directory of `.md`/`.txt`; keyword, semantic and hybrid search with kind/source
filters; JSON output; browse in a TUI; resumable embedding.
Non-functional: no server; works offline for keyword search; index of ~11k chunks builds keyword-only in
seconds. Dependencies: `numpy` (runtime), `textual`/`rich` (TUI extra), `pytest`, `pytest-asyncio`, `ruff` (dev).
