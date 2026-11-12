#!/usr/bin/env bash
# Re-run `mdbx index` (keyword + resumable semantic embedding) whenever a corpus file changes.
# This is the repo's semantic indexer hook: `mdbx index` itself embeds new chunks via Ollama.
# Needs fswatch (brew install fswatch) or inotifywait (inotify-tools). Ctrl+C to stop.
set -euo pipefail
cd "$(dirname "$0")/.."
export MDBX_CORPUS="${MDBX_CORPUS:-corpus}"
CORPUS="$MDBX_CORPUS"
MDBX=".venv/bin/mdbx"
reindex() { echo "[watch] change detected; reindexing"; "$MDBX" index || echo "[watch] index failed (see above)"; }
consume() {
  while read -r _; do
    # Collapse events already queued before the next serial rebuild.
    for _batch in {1..64}; do
      read -r -t 1 _ || break
    done
    reindex
  done
}
watch_changes() {
  if command -v fswatch >/dev/null; then
    fswatch -r -o -l 2 -- "$CORPUS" | consume
  elif command -v inotifywait >/dev/null; then
    inotifywait --monitor --quiet --format '%e' -r -e close_write,create,delete,move -- "$CORPUS" | consume
  else
    echo "install fswatch (macOS) or inotify-tools (Linux)" >&2
    return 1
  fi
}
if watch_changes; then
  :
else
  status=$?
  echo "[watch] filesystem watcher failed" >&2
  exit "$status"
fi
