#!/usr/bin/env python3
"""Fail if docs/high_signal_file_index.json lists a path that does not exist."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
missing = [e["path"] for e in json.loads((ROOT / "docs" / "high_signal_file_index.json").read_text())
           if not (ROOT / e["path"]).exists()]
if missing:
    print("dead index entries:", *missing, sep="\n  ")
    sys.exit(1)
print("doc index ok")
