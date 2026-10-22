#!/usr/bin/env bash
# One-command setup for mdbx on this machine:
#   scripts/install.sh [--no-model] [--no-index] [--no-agent]
# 1. pulls the latest code            4. downloads the in-process embedding model (no Ollama needed)
# 2. builds .venv on Python 3.11-3.13 5. builds/updates the search index
# 3. installs mdbx with all extras     6. installs the corpus auto-update agent (macOS launchd), then smoke-tests
# Re-run any time: every step is idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."

NO_MODEL=0 NO_INDEX=0 NO_AGENT=0
for a in "$@"; do
  case "$a" in
    --no-model) NO_MODEL=1 ;;
    --no-index) NO_INDEX=1 ;;
    --no-agent) NO_AGENT=1 ;;
    -h|--help) sed -n 2,7p "$0"; exit 0 ;;
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
PY="$(pick_python)" || { echo "error: need Python 3.11-3.13 (try: brew install python@3.13)" >&2; exit 1; }

say "Updating code"
git pull --ff-only || echo "note: not fast-forwarding (local changes or no upstream); continuing with the current checkout"

say "Virtualenv (.venv)"
if [ -x .venv/bin/python ]; then
  cur="$(.venv/bin/python -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  case "$cur" in 3.11|3.12|3.13) ;; *) echo "recreating .venv: it uses Python $cur"; rm -rf .venv ;; esac
fi
[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/python --version

say "Installing mdbx with extras (dev, tui, lsp, mcp, onnx)"
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e '.[dev,onnx]'

if [ "$NO_MODEL" = 0 ]; then
  say "Downloading the in-process embedding model (~550 MB, cached after the first run)"
  .venv/bin/mdbx embed-fetch
fi

if [ "$NO_INDEX" = 0 ]; then
  say "Building the search index (embeds with Ollama if it is running, else the in-process model; the first run can take a while)"
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
  MDBX_EMBED_BACKEND=onnx .venv/bin/mdbx search -m semantic -n 1 "why is my sort not using an index" | head -3
fi
say "Done"
