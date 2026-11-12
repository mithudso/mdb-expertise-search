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
        sources = sorted(fixtures.glob("*.txt"))
        assert sources, f"missing or empty fixture directory: {fixtures}"
        for src in sources:
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
                       capture_output=True, encoding="utf-8", check=True, timeout=240)
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
    emitted = set(re.findall(r"""(?:ERROR|WARNING|INFO|HINT),\s*["']([a-z-]+)["']""", source)) | {"syntax"}
    assert emitted - seen == set(), f"no fixture triggers: {sorted(emitted - seen)}"



@needs_node
def test_parser_and_analyzer_adversarial_contracts():
    script = r"""
import assert from 'node:assert/strict';
import {parse} from './editors/chrome/lib/parser.js';
import {analyze, diagnosticsToDicts} from './editors/chrome/lib/analyze.js';
import {getCloseMatches, suggest} from './editors/chrome/lib/operators.js';
const original = 'new Date(0)';
assert.equal(original.slice(parse(original)[0][0].node.start, parse(original)[0][0].node.end), original);
const [st, errors] = parse(String.raw`{"\u0024match":{"tag":"\x61\b\f\v\0","face":"\uD83D\uDE00"}}`);
assert.deepEqual(errors, []);
assert.equal(st[0].node.props[0].key, '$match');
assert.equal(st[0].node.props[0].value.props[0].value.value, 'a\b\f\v\0');
assert.equal(st[0].node.props[0].value.props[1].value.value, '😀');
for (const src of [String.raw`"\uZZZZ"`, String.raw`"\xGG"`, String.raw`"\u{110000}"`]) assert.ok(parse(src)[1].length);
for (const name of ['InfinityPipeline','NaNInput']) {
  const [[s], e] = parse(`db.c.aggregate(${name})`);
  assert.deepEqual(e, []); assert.equal(s.node.items.length, 1); assert.equal(s.node.items[0].value, name);
}
assert.equal(parse('db.café.find({a:1})')[0][0].node.target.target.value, 'café');
for (const sep of ['\r','\u2028','\u2029']) assert.equal(parse('// note'+sep+'{x:1}')[0].length, 1);
for (const src of ['[1 2]','{a:1 b:2}','f(1 2)','{,a:1}','f(,1)','@\n{x:1}']) assert.ok(parse(src)[1].length, src);
assert.doesNotThrow(() => parse('['.repeat(20000)+'0'+']'.repeat(20000)));
assert.equal(parse('db'+'.x'.repeat(20000))[0][0].node.walk().length, 20001);
for (const src of ['{a: @"}", b:1}', '{a:[f(1], b:2}', '{a: @/* } */0,b:1}']) {
  const [[s],e] = parse(src); assert.ok(e.length); assert.deepEqual(s.node.props.map(p=>p.key), ['a','b']);
}
const codes = src => analyze(src).diagnostics.map(d=>d.code);
for (const src of ['db.c.aggregate(42)','db.c.find({},[])','db.c.find({}).sort(false)',
 'db.c.aggregate([{$out:7}])','db.c.aggregate([{$merge:7}])','db.c.aggregate([{$unionWith:7}])',
 'db.c.find({$jsonSchema:7})','db.c.find({$sampleRate:"bad"})',
 'db.c.aggregate([{$project:{x:{$subtract:1}}}])','db.c.updateOne({},{$inc:{n:{value:1}}})',
 'db.c.find({a:{$size:-1}})','db.c.aggregate([{$limit:Infinity}])']) assert.ok(codes(src).includes('bad-argument'), src);
for(const calls of ['db.c.aggregate(p);db.c.updateOne({},p);','db.c.updateOne({},p);db.c.aggregate(p);'])
 assert.equal(codes('const p=[{$match:{}}];'+calls).filter(c=>c==='stage-position').length,1);
for(const calls of ['db.c.find(d);db.c.updateOne({},d);','db.c.updateOne({},d);db.c.find(d);'])
 assert.equal(codes('const d={x:1};'+calls).filter(c=>c==='update-shape').length,1);
assert.ok(codes('db.c.find({},{keep:1,nested:{_id:0}})').includes('projection-mix'));
for (const op of ['$near','$nearSphere']) assert.ok(codes(`db.c.aggregate([{$match:{loc:{${op}:{$geometry:{type:'Point',coordinates:[0,0]}}}}}])`).includes('misplaced-operator'));
assert.deepEqual(codes('db.c.aggregate([{$setWindowFields:{sortBy:{t:1},output:{total:{$sum:"$x",window:{documents:["unbounded","current"]}}}}}])'), []);
assert.ok(codes('db.c.aggregate([{$group:{_id:null,n:{$abs:"$x"}}}])').includes('misplaced-operator'));
assert.ok(codes('db.c.aggregate([{$project:{n:{$push:"$x"}}}])').includes('misplaced-operator'));
assert.deepEqual(getCloseMatches('ab',['ab\uE000','ab\u{10000}'],2), ['ab\u{10000}','ab\uE000']);
for(const n of [0,-1]) {assert.throws(()=>getCloseMatches('x',['x'],n),RangeError);assert.throws(()=>suggest('$grup',n),RangeError);}
for(const c of [-0.01,1.01,NaN]) assert.throws(()=>getCloseMatches('x',['x'],1,c),RangeError);
const count=128, text='x\n'.repeat(count);
const ds=Array.from({length:count},(_,i)=>({start:2*i,end:2*i+1,severity:'error',code:'synthetic',message:'synthetic',fix:null}));
const prior=String.prototype.indexOf; let scans=0;
String.prototype.indexOf=function(needle,...args){ if(needle==='\n'&&String(this)===text)scans++;return Reflect.apply(prior,this,[needle,...args]); };
try { assert.deepEqual(diagnosticsToDicts(text,ds).map(d=>[d.line,d.column]),ds.map((_,i)=>[i,0])); assert.ok(scans<=4*count, String(scans)); }
finally {String.prototype.indexOf=prior;}
"""
    result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, check=False,
                            capture_output=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr


def test_parity_inputs_reject_missing_directory(tmp_path, monkeypatch):
    monkeypatch.setitem(globals(), 'FIXTURES', [tmp_path / 'missing'])
    with pytest.raises((AssertionError, FileNotFoundError, ValueError), match='missing'):
        _inputs()


def test_inventory_recognizes_single_quotes(tmp_path, monkeypatch):
    fixtures = tmp_path / 'tests/fixtures/lint'
    fixtures.mkdir(parents=True)
    (fixtures / 'syntax.lint.json').write_text(json.dumps({'diagnostics':[{'code':'syntax'}]}))
    target = tmp_path / 'mdbx/mql/analyze.py'
    target.parent.mkdir(parents=True)
    target.write_text("emit(WARNING, 'uncovered-code')\n")
    monkeypatch.setitem(globals(), 'ROOT', tmp_path)
    with pytest.raises(AssertionError, match='uncovered-code'):
        test_every_diagnostic_code_has_a_golden()
