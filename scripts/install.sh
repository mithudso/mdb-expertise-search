#!/usr/bin/env bash
# One-command setup for mdbx on this machine:
#   scripts/install.sh [--no-model] [--no-index] [--no-agent]
# 1. pulls the latest code            4. downloads the in-process embedding model (no Ollama needed)
# 2. builds .venv on Python 3.11-3.13 5. builds/updates the search index
# 3. installs mdbx with all extras     6. installs the corpus auto-update agent (macOS launchd), then smoke-tests
# Re-run any time: every step is idempotent.
set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
cd "$(dirname "$SCRIPT_PATH")/.."

NO_MODEL=0 NO_INDEX=0 NO_AGENT=0
for a in "$@"; do
  case "$a" in
    --no-model) NO_MODEL=1 ;;
    --no-index) NO_INDEX=1 ;;
    --no-agent) NO_AGENT=1 ;;
    -h|--help) sed -n 2,7p "$SCRIPT_PATH"; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done
say() { printf '\n==> %s\n' "$*"; }

# onnxruntime (the in-process embedder) has no wheels for the newest Pythons, so pin to 3.11-3.13.
pick_python() {
  for v in 3.13 3.12 3.11; do
    for p in "python$v" "/opt/homebrew/bin/python$v" "/usr/local/bin/python$v"; do
      if command -v "$p" >/dev/null 2>&1; then command -v "$p"; return 0; fi
    done
  done
  return 1
}


install_lock="$PWD/.mdbx-install.lock"
if ! mkdir "$install_lock" 2>/dev/null; then
  echo "another installer owns this checkout; retry after it exits" >&2
  exit 1
fi
trap 'rmdir "$install_lock" 2>/dev/null || true' EXIT

say "Updating code"
git pull --ff-only || echo "note: not fast-forwarding (local changes or no upstream); continuing with the current checkout"

say "Virtualenv (.venv)"
if [ -x .venv/bin/python ]; then
  cur="$(.venv/bin/python -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  case "$cur" in
    3.11|3.12|3.13) ;;
    *)
      PY="$(pick_python)" || { echo "error: need Python 3.11-3.13; existing .venv preserved" >&2; exit 1; }
      backup=".venv.pre-install-$(date +%s)-$$"
      mv .venv "$backup"
      if ! "$PY" -m venv .venv; then
        rm -rf .venv
        mv "$backup" .venv
        exit 1
      fi
      echo "previous virtualenv preserved at $backup"
      ;;
  esac
fi
if [ ! -x .venv/bin/python ]; then
  PY="$(pick_python)" || { echo "error: need Python 3.11-3.13 (try: brew install python@3.13)" >&2; exit 1; }
  "$PY" -m venv .venv
fi
.venv/bin/python --version

say "Installing mdbx with extras (dev, tui, lsp, mcp, onnx)"
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -e '.[dev,onnx]'

if [ "$NO_MODEL" = 0 ]; then
  say "Downloading the in-process embedding model (~550 MB, cached after the first run)"
  .venv/bin/mdbx embed-fetch
fi

if [ "$NO_INDEX" = 0 ]; then
  say "Building the search index (uses a cached in-process model, or an explicitly installed Ollama adapter; --no-model requires one of these)"
  .venv/bin/mdbx index
fi

if [ "$NO_AGENT" = 0 ]; then
  if [ "$(uname)" = Darwin ]; then
    say "Installing the corpus auto-update agent"
    [ -f "$HOME/.config/mdbx/denylist.txt" ] || echo "warning: ~/.config/mdbx/denylist.txt is missing; the agent will refuse to publish until it exists"
    "$PWD/.venv/bin/python" scripts/corpus_autoupdate.py --python "$PWD/.venv/bin/python" install-agent
  else
    echo "skipping the auto-update agent: it needs macOS launchd"
  fi
fi

say "Smoke test"
.venv/bin/mdbx stats
if [ "$NO_MODEL" = 0 ] && [ "$NO_INDEX" = 0 ]; then
  .venv/bin/mdbx search -m semantic -n 1 "why is my sort not using an index" | head -3
fi
say "Done"
