#!/usr/bin/env bash
# Re-run `mdbx index` (keyword + resumable semantic embedding) whenever a corpus file changes.
# This is the repo's semantic indexer hook: `mdbx index` itself embeds new chunks via Ollama.
# Needs fswatch (brew install fswatch) or inotifywait (inotify-tools). Ctrl+C to stop.
set -euo pipefail
cd "$(dirname "$0")/.."
CORPUS="${MDBX_CORPUS:-corpus}"
MDBX=".venv/bin/mdbx"
reindex() { echo "[watch] change detected; reindexing"; "$MDBX" index || echo "[watch] index failed (see above)"; }
if command -v fswatch >/dev/null; then
  fswatch -o -l 2 --exclude '/\.' "$CORPUS" | while read -r _; do reindex; done
elif command -v inotifywait >/dev/null; then
  while inotifywait -qq -r -e close_write,create,delete,move "$CORPUS"; do sleep 2; reindex; done
else
  echo "install fswatch (macOS) or inotify-tools (Linux)" >&2
  exit 1
fi
