"""Cross-check the Chrome extension's JavaScript optimizer against the Python reference.

Every fixture is cut at ~40 evenly spaced points, so half-typed queries exercise the parser's error
recovery as well as the normal paths. Skipped when Node.js is not installed.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from mdbx.mql.optimize import optimize, to_dict

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "optimizer"
BATCH = ROOT / "editors" / "chrome" / "test" / "batch.mjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _inputs() -> list[str]:
    out = []
    for src in sorted(FIX.glob("*.txt")):
        text = src.read_text(encoding="utf-8")
        step = max(1, len(text) // 40)
        out += [text[:i] for i in range(0, len(text) + 1, step)]
        out.append(text)
    return out


def test_js_matches_python_on_prefixes():
    texts = _inputs()
    r = subprocess.run(["node", str(BATCH)], input=json.dumps(texts), capture_output=True, text=True,
                       check=True, timeout=120)
    js = json.loads(r.stdout)
    assert len(js) == len(texts)
    mismatches = []
    for text, got in zip(texts, js, strict=True):
        want = {"apply": to_dict(optimize(text)), "read_only": to_dict(optimize(text, apply=False))}
        if got != want:
            mismatches.append(text[-80:])
    assert not mismatches, f"{len(mismatches)} of {len(texts)} differ; e.g. …{mismatches[0]!r}"
