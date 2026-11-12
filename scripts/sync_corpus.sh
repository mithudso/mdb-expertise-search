#!/usr/bin/env bash
# Prepare and privacy-check a private generation, then publish atomically.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/sync_corpus_transaction.py
