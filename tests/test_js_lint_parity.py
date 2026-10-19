"""Cross-check the Chrome extension's JavaScript MQL analyzer against the Python reference.

Every lint and optimizer fixture is cut at ~40 evenly spaced points, so half-typed queries exercise the
parser's error recovery and the analyzer's null-value paths as well as the normal ones. Also checks
that the committed lint goldens and the generated operator table are current. The parity test is
skipped when Node.js is not installed; the staleness tests need only Python.
"""
import importlib.util
import json
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from mdbx.mql import operators

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = [ROOT / "tests" / "fixtures" / "lint", ROOT / "tests" / "fixtures" / "optimizer"]
BATCH = ROOT / "editors" / "chrome" / "test" / "lint-batch.mjs"
SCRIPTS = ROOT / "scripts"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


gen_lint_golden = _load_script("gen_lint_golden")


def _inputs() -> list[str]:
    out = []
    for fixtures in FIXTURES:
        for src in sorted(fixtures.glob("*.txt")):
            text = src.read_text(encoding="utf-8")
            step = max(1, len(text) // 40)
            out += [text[:i] for i in range(0, len(text) + 1, step)]
            out.append(text)
    return out


def _words() -> list[str]:
    """Misspelled and unrelated operator-like words for difflib parity (deterministic)."""
    rng = random.Random(7)
    names = sorted(operators.OPERATORS)
    words = ["$", "$$", "$a", "$grup", "$gtt", "$zzzqqq", "$" + "x" * 250, "$" + "ab" * 150, ""]
    for name in names:
        words.append(name[:-1])
        words.append(name + "s")
        i = rng.randrange(1, len(name))
        words.append(name[:i] + rng.choice("aeiouxz") + name[i + 1:])
        words.append(name[:i] + name[i + 1:])
    return words


def _run_js(texts: list[str], words: list[str]) -> dict:
    r = subprocess.run(["node", str(BATCH)], input=json.dumps({"texts": texts, "words": words}),
                       capture_output=True, text=True, check=True, timeout=240)
    return json.loads(r.stdout)


@needs_node
def test_js_lint_matches_python_on_prefixes():
    texts = _inputs()
    assert len(texts) > 500
    js = _run_js(texts, [])["lint"]
    assert len(js) == len(texts)
    mismatches = [text[-80:] for text, got in zip(texts, js, strict=True)
                  if got != gen_lint_golden.lint_dict(text)]
    assert not mismatches, f"{len(mismatches)} of {len(texts)} differ; e.g. …{mismatches[0]!r}"


@needs_node
def test_js_suggest_matches_difflib():
    words = _words()
    js = _run_js([], words)["suggest"]
    assert len(js) == len(words)
    bad = [(w, got, operators.suggest(w)) for w, got in zip(words, js, strict=True)
           if got != operators.suggest(w)]
    assert not bad, f"{len(bad)} of {len(words)} differ; e.g. {bad[0]!r}"


def _check(script: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), "--check"], check=False, capture_output=True,
                          text=True, timeout=120)


def test_lint_goldens_are_current():
    r = _check("gen_lint_golden.py")
    assert r.returncode == 0, r.stdout + r.stderr


def test_chrome_operator_table_is_current():
    r = _check("gen_chrome_operators.py")
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_diagnostic_code_has_a_golden():
    seen = set()
    for g in (ROOT / "tests" / "fixtures" / "lint").glob("*.lint.json"):
        seen |= {d["code"] for d in json.loads(g.read_text(encoding="utf-8"))["diagnostics"]}
    source = (ROOT / "mdbx" / "mql" / "analyze.py").read_text(encoding="utf-8")
    emitted = set(re.findall(r'(?:ERROR|WARNING|INFO|HINT),\s*"([a-z-]+)"', source)) | {"syntax"}
    assert emitted - seen == set(), f"no fixture triggers: {sorted(emitted - seen)}"
