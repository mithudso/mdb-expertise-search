"""Synthetic regressions for preimport state, fixture Git, and the CI report contract."""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'scripts' / 'test_isolation.py'


def _run(script, tmp_path, *, env=None):
    path = tmp_path / 'probe.py'
    path.write_text(script)
    return subprocess.run([sys.executable, str(path)], env=env, capture_output=True,
                          text=True, check=True, timeout=30)


def _bootstrap(scratch):
    return (
        'import importlib.util, pathlib, sys\n'
        f'spec=importlib.util.spec_from_file_location("test_isolation", {str(HELPER)!r})\n'
        'isolation=importlib.util.module_from_spec(spec)\nspec.loader.exec_module(isolation)\n'
        f'isolation.prepare_environment(pathlib.Path({str(scratch)!r}))\n'
        'isolation.install_fake_factories()\n')


def test_hostile_git_environment_templates_and_hooks_never_reach_fixture_commits(tmp_path):
    hostile = tmp_path / 'hostile'
    (hostile / 'template' / 'hooks').mkdir(parents=True)
    (hostile / 'global-hooks').mkdir()
    marker = tmp_path / 'unexpected-hook-execution'
    script = '#!/bin/sh\nprintf unsafe >> ' + str(marker) + '\nexit 99\n'
    for hook in (hostile / 'template/hooks/post-commit', hostile / 'global-hooks/pre-commit'):
        hook.write_text(script)
        hook.chmod(0o700)
    config = hostile / 'global-config'
    config.write_text(f'[core]\n hooksPath = {hostile / "global-hooks"}\n'
                      f'[init]\n templateDir = {hostile / "template"}\n')
    env = dict(os.environ)
    selectors = ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR',
                 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES',
                 'GIT_NAMESPACE', 'GIT_CEILING_DIRECTORIES', 'GIT_EXEC_PATH')
    env.update({key: str(hostile / 'nonexistent') for key in selectors})
    env.update(GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_SYSTEM=str(config),
               GIT_CONFIG_PARAMETERS="'core.hooksPath=synthetic-hostile'", GIT_CONFIG_COUNT='19',
               GIT_CONFIG_KEY_18='core.hooksPath', GIT_CONFIG_VALUE_18=str(hostile / 'global-hooks'),
               GIT_TEMPLATE_DIR=str(hostile / 'template'), GIT_TERMINAL_PROMPT='1')
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    probe = _bootstrap(scratch) + f"""
import json, os, subprocess
repo=pathlib.Path({str(tmp_path / 'repo')!r})
def git(*args):
    return subprocess.check_output(['git',*args],text=True,stderr=subprocess.STDOUT)
assert not any(key in os.environ for key in {selectors!r})
assert 'GIT_CONFIG_PARAMETERS' not in os.environ and 'GIT_CONFIG_KEY_18' not in os.environ
assert os.environ['GIT_TERMINAL_PROMPT']=='0'
git('init','-q','--template',{str(hostile / 'template')!r},str(repo))
git('-C',str(repo),'config','core.hooksPath',{str(hostile / 'global-hooks')!r})
git('-C',str(repo),'commit','-q','--allow-empty','-m','root')
(repo/'sub').mkdir(); (repo/'sub/later').write_text('synthetic')
git('-C',str(repo/'sub'),'add','later')
git('-C',str(repo/'sub'),'-c','core.hooksPath={hostile / 'global-hooks'}','commit','-q','-m','later')
assert git('-C',str(repo),'rev-list','--count','HEAD').strip()=='2'
assert not any((repo/'.git/hooks').iterdir()) if (repo/'.git/hooks').exists() else True
state=pathlib.Path(os.environ['MDBX_FIXTURE_GIT_ROOT'])
rows=[json.loads(line) for line in (state/'commit-preflight.jsonl').read_text().splitlines()]
assert len(rows)==2 and all(all(row.values()) for row in rows)
assert (state/'empty-config').read_bytes()==b''
assert not any((state/'template').iterdir()) and not any((state/'hooks').iterdir())
"""
    _run(probe, tmp_path, env=env)
    assert not marker.exists()


def test_state_and_factories_are_synthetic_before_product_imports(tmp_path):
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    probe = _bootstrap(scratch) + """
import os
from mdbx import embed, embed_onnx
assert pathlib.Path.home()==pathlib.Path(os.environ['MDBX_TEST_ISOLATION_ROOT'])/'home'
for key in ('MDBX_DB','MDBX_CORPUS','MDBX_ONNX_MODEL','HF_HOME','OLLAMA_MODELS',
            'MDBX_DENYLIST','MDBX_REDACTIONS','XDG_CONFIG_HOME','XDG_CACHE_HOME'):
    assert pathlib.Path(os.environ[key]).is_relative_to(pathlib.Path(os.environ['MDBX_TEST_ISOLATION_ROOT']))
assert 'SYNTHETIC_AUTH_TOKEN' not in os.environ
assert embed_onnx._runtime.__module__==isolation.__name__
assert embed._client.__module__==isolation.__name__
assert embed_onnx._runtime_original is embed_onnx._locked_runtime
try: embed_onnx._runtime()
except embed_onnx.OnnxUnavailable as exc: assert 'synthetic runtime' in str(exc)
else: raise AssertionError('runtime factory was not replaced')
try: embed._client(1,0)
except embed.OllamaUnavailable: pass
else: raise AssertionError('client factory was not replaced')
import onnxruntime, tokenizers, huggingface_hub, transformers, sentence_transformers
for factory in (onnxruntime.InferenceSession, tokenizers.Tokenizer.from_file,
                huggingface_hub.hf_hub_download, transformers.pipeline,
                sentence_transformers.SentenceTransformer):
    try: factory('synthetic')
    except RuntimeError as exc: assert 'synthetic factory' in str(exc)
    else: raise AssertionError('optional factory was not replaced')
"""
    env = dict(os.environ, SYNTHETIC_AUTH_TOKEN='synthetic-only', MDBX_ONNX_MODEL='/synthetic-hostile')
    _run(probe, tmp_path, env=env)


def test_real_artifact_loader_is_explicit_and_uses_fake_dependencies(monkeypatch, tmp_path):
    from mdbx import embed, embed_onnx
    # Collection installs the fake runtime. This test deliberately restores only the loader.
    assert hasattr(embed_onnx, '_runtime_original')
    monkeypatch.setattr(embed_onnx, '_runtime', embed_onnx._runtime_original)
    monkeypatch.setenv('MDBX_EMBED_BACKEND', 'onnx')
    monkeypatch.setenv('MDBX_ONNX_MODEL', str(tmp_path))
    calls = []
    original = embed_onnx._resolve
    def resolve(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(embed_onnx, '_resolve', resolve)
    embed_onnx._clear_runtime()
    try:
        with pytest.raises(embed.EmbedError) as error:
            embed.embed(['synthetic'])
        assert calls == [{'download': False}]
        assert isinstance(error.value.__cause__, embed_onnx.OnnxUnavailable)
        assert isinstance(error.value.__cause__.__cause__, embed_onnx.OnnxUnavailable)
    finally:
        embed_onnx._clear_runtime()


def test_node_descendant_keeps_scratch_state_and_python_fake_factories(tmp_path):
    import shutil
    if shutil.which('node') is None:
        pytest.skip('node is not installed')
    report = tmp_path / 'child-state.json'
    python_code = """import json,os,pathlib
from mdbx import embed_onnx
try: embed_onnx._runtime()
except embed_onnx.OnnxUnavailable: pass
else: raise AssertionError('live runtime')
pathlib.Path(os.environ['SYNTHETIC_REPORT']).write_text(json.dumps({'home':os.environ['HOME'],'root':os.environ['MDBX_TEST_ISOLATION_ROOT']}))
"""
    node = "const p=require('node:child_process'); const r=p.spawnSync(process.env.SYNTHETIC_PYTHON,['-c',process.env.SYNTHETIC_CODE],{stdio:'inherit'}); process.exit(r.status ?? 1);"
    # The launcher sanitizes arbitrary inherited variables, so arguments carry fixture data.
    node = ("process.env.SYNTHETIC_REPORT=" + json.dumps(str(report)) + ";"
            "process.env.SYNTHETIC_PYTHON=" + json.dumps(sys.executable) + ";"
            "process.env.SYNTHETIC_CODE=" + json.dumps(python_code) + ";" + node)
    subprocess.run([sys.executable, str(ROOT / 'scripts/offline_test.py'), '--', 'node', '-e', node],
                   check=True, capture_output=True, text=True, timeout=30)
    row = json.loads(report.read_text())
    assert Path(row['home']) == Path(row['root']) / 'home'
    assert not Path(row['root']).exists()  # launcher owns and removes its scratch state


def _ci_smoke_assertions():
    text = (ROOT / '.github/workflows/ci.yml').read_text()
    snippet = text[text.index('          import json, subprocess, sys'):]
    snippet = snippet[:snippet.index('          PY')]
    tree = ast.parse(textwrap.dedent(snippet))
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'r'
                                            for target in node.targets))]
    return compile(tree, '<CI optimizer smoke assertions>', 'exec')


def _valid_report():
    return {'input': {'kind': 'mongosh', 'interpreted': None},
            'queries': [{'kind': 'find', 'method': 'find', 'collection': 'c',
                         'line': 1, 'column': 1, 'evidence': {}}],
            'findings': [], 'applied': [], 'indexes': [], 'rewritten': None, 'iterations': 0}


@pytest.mark.parametrize('payload,code', [({}, 0), ({'error':'synthetic failure'}, 1),
    ({**_valid_report(), 'queries': []}, 0), ({**_valid_report(), 'applied': [{}]}, 0),
    ({**_valid_report(), 'rewritten': 'changed'}, 0), (_valid_report(), 1),
    ({**_valid_report(), 'iterations': True}, 0)])
def test_ci_optimizer_smoke_rejects_invalid_reports(payload, code):
    result = subprocess.CompletedProcess([], code, json.dumps(payload), '')
    with pytest.raises(AssertionError):
        exec(_ci_smoke_assertions(), {'r': result})  # noqa: S102


@pytest.mark.parametrize('code', [0, 1])
def test_ci_optimizer_smoke_accepts_maintained_read_only_report(code):
    report = _valid_report()
    if code:
        report['findings'] = [{'severity': 'high', 'code': 'fixture', 'pass': 'fixture',
                               'message': 'synthetic', 'ref': None, 'line': 1, 'column': 1}]
    result = subprocess.CompletedProcess([], code, json.dumps(report), '')
    exec(_ci_smoke_assertions(), {'r': result})  # noqa: S102
