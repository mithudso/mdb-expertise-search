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
    sources = sorted(FIX.glob("*.txt"))
    assert sources, f"missing or empty fixture directory: {FIX}"
    for src in sources:
        text = src.read_text(encoding="utf-8")
        step = max(1, len(text) // 40)
        out += [text[:i] for i in range(0, len(text) + 1, step)]
        out.append(text)
    assert out
    return out


def test_js_matches_python_on_prefixes():
    texts = _inputs()
    r = subprocess.run(["node", str(BATCH)], input=json.dumps(texts), capture_output=True, encoding="utf-8",
                       check=True, timeout=120)
    js = json.loads(r.stdout)
    assert len(js) == len(texts)
    mismatches = []
    for text, got in zip(texts, js, strict=True):
        want = {"apply": to_dict(optimize(text)), "read_only": to_dict(optimize(text, apply=False))}
        if not _typed_equal(got, want):
            mismatches.append(text[-80:])
    assert not mismatches, f"{len(mismatches)} of {len(texts)} differ; e.g. …{mismatches[0]!r}"


def test_optimizer_parity_requires_fixtures(tmp_path, monkeypatch):
    monkeypatch.setitem(globals(), "FIX", tmp_path / "missing")
    with pytest.raises(AssertionError, match="missing"):
        _inputs()


def _typed_equal(left, right):
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_typed_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_typed_equal(a, b) for a, b in zip(left, right, strict=True))
    return left == right


def test_json_comparison_preserves_boolean_number_types():
    assert not _typed_equal({"iterations": True}, {"iterations": 1})
    assert _typed_equal({"docsExamined": 1.0}, {"docsExamined": 1})
