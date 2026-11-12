"""Fixture-only scratch state and synthetic factories for offline test processes.

The empty Git configuration and hooks belong only to synthetic test fixtures.
"""
from __future__ import annotations

import functools
import importlib.abc
import importlib.machinery
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import types
from pathlib import Path

_SAFE_ENV = ('PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TERM', 'TMPDIR', 'TZ', 'CI',
             'GITHUB_ACTIONS', 'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE')
_GIT = '/usr/bin/git'


def prepare_environment(root: Path) -> None:
    """Replace inherited state before importing product code or starting descendants."""
    root = root.resolve(strict=True)
    home, gitroot = root / 'home', root / 'fixture-git'
    for path in (home, gitroot / 'hooks', gitroot / 'template', root / 'empty-model',
                 root / 'corpus', root / 'bin', root / 'bootstrap', root / 'tmp'):
        path.mkdir(parents=True, exist_ok=True)
    config = gitroot / 'empty-config'
    if config.exists() and config.read_bytes():
        raise RuntimeError('fixture Git config must remain empty')
    config.touch()
    for directory in (gitroot / 'hooks', gitroot / 'template'):
        if any(directory.iterdir()):
            raise RuntimeError('fixture Git hooks and template must remain empty')
    previous = {key: os.environ[key] for key in _SAFE_ENV if key in os.environ}
    os.environ.clear()
    os.environ.update(previous)
    os.environ.update({
        'TMPDIR': str(root / 'tmp'), 'HOME': str(home), 'XDG_CONFIG_HOME': str(home / 'config'),
        'XDG_CACHE_HOME': str(home / 'cache'), 'XDG_DATA_HOME': str(home / 'data'),
        'XDG_STATE_HOME': str(home / 'state'), 'PYTHONNOUSERSITE': '1',
        'PYTHONDONTWRITEBYTECODE': '1', 'MDBX_TEST_ISOLATION': '1',
        'MDBX_TEST_ISOLATION_ROOT': str(root), 'MDBX_FIXTURE_GIT_ROOT': str(gitroot),
        'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_SYSTEM': str(config),
        'GIT_CONFIG_GLOBAL': str(config), 'GIT_TERMINAL_PROMPT': '0',
        'GIT_TEMPLATE_DIR': str(gitroot / 'template'),
        'MDBX_DB': str(root / 'test.sqlite'), 'MDBX_CORPUS': str(root / 'corpus'),
        'MDBX_ONNX_MODEL': str(root / 'empty-model'),
        'MDBX_OLLAMA_HOST': 'http://127.0.0.1:9', 'MDBX_EMBED_BACKEND': 'ollama',
        'MDBX_DENYLIST': str(root / 'missing-denylist.txt'),
        'MDBX_REDACTIONS': str(root / 'missing-redactions.py'),
        'MDBX_AUTOUPDATE_CONFIG': str(root / 'chrome.json'),
        'MDBX_CORPUS_AUTOUPDATE_CONFIG': str(root / 'corpus.json'),
        'HF_HOME': str(home / 'hf'), 'HF_HUB_CACHE': str(home / 'hf' / 'hub'),
        'HUGGINGFACE_HUB_CACHE': str(home / 'hf' / 'hub'),
        'TRANSFORMERS_CACHE': str(home / 'transformers'),
        'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
        'OLLAMA_MODELS': str(home / 'models'), 'TOKENIZERS_PARALLELISM': 'false',
    })
    # Absolute source paths bind descendants to this helper rather than a user module.
    helper = Path(__file__).resolve()
    launcher = root / 'bin' / 'git'
    launcher.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' '
                        + shlex.quote(str(helper)) + ' --fixture-git "$@"\n')
    launcher.chmod(0o700)
    bootstrap = root / 'bootstrap' / 'sitecustomize.py'
    bootstrap.write_text(
        'import importlib.util, sys\n'
        f'_s = importlib.util.spec_from_file_location("_mdbx_test_isolation", {str(helper)!r})\n'
        '_m = importlib.util.module_from_spec(_s)\n'
        'sys.modules[_s.name] = _m\n_s.loader.exec_module(_m)\n'
        '_m.install_fake_factories()\n')
    os.environ['PATH'] = str(root / 'bin') + os.pathsep + previous.get('PATH', '/usr/bin:/bin')
    os.environ['PYTHONPATH'] = os.pathsep.join(filter(None, (
        str(root / 'bootstrap'), str(helper.parent.parent), previous.get('PYTHONPATH', ''))))
    for number, (key, value) in enumerate((
        ('core.hooksPath', str(gitroot / 'hooks')),
        ('init.templateDir', str(gitroot / 'template')), ('commit.gpgsign', 'false'),
    )):
        os.environ[f'GIT_CONFIG_KEY_{number}'] = key
        os.environ[f'GIT_CONFIG_VALUE_{number}'] = value
    os.environ['GIT_CONFIG_COUNT'] = '3'


def _forbidden_factory(*args, **kwargs):
    raise RuntimeError('synthetic factory required; live model/provider disabled')


def _patch_product(module) -> None:
    if module.__name__ == 'mdbx.embed_onnx':
        module._clear_runtime()
        if not hasattr(module, '_runtime_original'):
            module._runtime_original = module._locked_runtime

        @functools.lru_cache(maxsize=1)
        def fake_runtime():
            raise module.OnnxUnavailable('synthetic runtime required')
        module._runtime = fake_runtime
    elif module.__name__ == 'mdbx.embed':
        def fake_client(*args, **kwargs):
            raise module.OllamaUnavailable('synthetic provider factory required')
        module._client = fake_client


class _SafeLoader(importlib.abc.Loader):
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def create_module(self, spec):
        return self.wrapped.create_module(spec) if hasattr(self.wrapped, 'create_module') else None

    def exec_module(self, module):
        self.wrapped.exec_module(module)
        _patch_product(module)


class _SafeFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('ai_auth', 'ollama_client'):
            raise ModuleNotFoundError('optional live client disabled in synthetic tests', name=fullname)
        if fullname not in ('mdbx.embed', 'mdbx.embed_onnx'):
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and spec.loader:
            spec.loader = _SafeLoader(spec.loader)
        return spec


def install_fake_factories() -> None:
    """Force cached synthetic factories while retaining an explicit artifact-test loader."""
    for name, attributes in {
        'onnxruntime': {'InferenceSession': _forbidden_factory},
        'tokenizers': {'Tokenizer': types.SimpleNamespace(from_file=_forbidden_factory)},
        'huggingface_hub': {'hf_hub_download': _forbidden_factory},
        'transformers': {'pipeline': _forbidden_factory,
                         'AutoModel': types.SimpleNamespace(from_pretrained=_forbidden_factory),
                         'AutoTokenizer': types.SimpleNamespace(from_pretrained=_forbidden_factory)},
        'sentence_transformers': {'SentenceTransformer': _forbidden_factory},
    }.items():
        module = types.ModuleType(name)
        module.__spec__ = importlib.util.spec_from_loader(name, loader=None)
        module.__dict__.update(attributes)
        sys.modules[name] = module
    for name in tuple(sys.modules):
        if name.split('.')[0] in ('ai_auth', 'ollama_client'):
            del sys.modules[name]
    sys.meta_path.insert(0, _SafeFinder())
    for name in ('mdbx.embed_onnx', 'mdbx.embed'):
        if name in sys.modules:
            _patch_product(sys.modules[name])


def fixture_git(args: list[str]) -> int:
    """Execute fixture Git with empty owned configuration, templates, and hook checks."""
    root = Path(os.environ['MDBX_FIXTURE_GIT_ROOT']).resolve(strict=True)
    hooks, template, config = root / 'hooks', root / 'template', root / 'empty-config'
    if any(hooks.iterdir()) or any(template.iterdir()) or config.read_bytes():
        raise RuntimeError('fixture Git isolation state is not empty')
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_SYSTEM=str(config),
               GIT_CONFIG_GLOBAL=str(config), GIT_TERMINAL_PROMPT='0')
    command_at = 0
    while command_at < len(args):
        arg = args[command_at]
        if arg in ('-c', '-C', '--git-dir', '--work-tree', '--namespace', '--config-env'):
            command_at += 2
        elif arg.startswith('-'):
            command_at += 1
        else:
            break
    command = args[command_at] if command_at < len(args) else ''
    prefix = args[:command_at] + [
        '-c', 'core.hooksPath=' + str(hooks), '-c', 'init.templateDir=' + str(template),
        '-c', 'commit.gpgsign=false', '-c', 'user.name=Synthetic Fixture',
        '-c', 'user.email=fixture@example.invalid',
    ]
    tail = args[command_at:]
    if command in ('init', 'clone'):
        filtered, at = [], 0
        while at < len(tail):
            if tail[at] == '--':
                filtered.extend(tail[at:])
                break
            if tail[at] == '--template':
                at += 2
            elif tail[at].startswith('--template='):
                at += 1
            else:
                filtered.append(tail[at])
                at += 1
        tail = filtered
        tail.insert(1, '--template=' + str(template))
    if command == 'commit':
        def query(*extra):
            return subprocess.check_output([_GIT, *prefix, *extra], env=env, text=True,
                                           stderr=subprocess.PIPE, timeout=10).strip()
        effective = Path(query('config', '--path', '--get', 'core.hooksPath')).resolve()
        gitdir = Path(query('rev-parse', '--absolute-git-dir'))
        if effective != hooks or any(effective.iterdir()):
            raise RuntimeError('fixture Git effective hooks must be the owned empty directory')
        copied = gitdir / 'hooks'
        if copied.exists() and any(copied.iterdir()):
            raise RuntimeError('fixture Git copied hooks must be empty')
        with (root / 'commit-preflight.jsonl').open('a') as stream:
            stream.write(json.dumps({'effective_hooks_empty': True, 'template_empty': True,
                                     'inherited_git_config_removed': True}) + '\n')
    os.execve(_GIT, [_GIT, *prefix, *tail], env)
    return 127


if __name__ == '__main__':
    if sys.argv[1:2] != ['--fixture-git']:
        raise SystemExit('test isolation helper requires --fixture-git')
    raise SystemExit(fixture_git(sys.argv[2:]))
