"""Public offline CI must not require optional private-install credentials."""
import importlib.util
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_public_dev_dependency_closure_does_not_require_private_auth():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']
    extras = project['optional-dependencies']
    dependencies = list(project['dependencies'])
    pending, visited = ['dev'], set()
    while pending:
        extra = pending.pop()
        if extra in visited:
            continue
        visited.add(extra)
        for dependency in extras[extra]:
            if dependency.startswith(project['name'] + '['):
                pending.extend(dependency.split('[', 1)[1].split(']', 1)[0].split(','))
            else:
                dependencies.append(dependency)
    assert not {'ai', 'ollama'} & visited
    assert all('git+' not in dependency and ' @ ' not in dependency for dependency in dependencies)
    workflow = (ROOT / '.github/workflows/ci.yml').read_text()
    assert "python -m pip install -e '.[dev]'" in workflow
    assert 'run: python scripts/ci_private_dependency.py' not in workflow
    assert 'OLLAMA_CLIENT_DEPLOY_KEY' not in workflow
    assert 'chrome-release:' not in workflow
    assert 'contents: write' not in workflow
    assert 'macos-latest' in workflow and 'ubuntu-latest' in workflow


def test_explicit_private_helper_without_key_fails_before_any_effect(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('private_dependency_contract', ROOT / 'scripts/ci_private_dependency.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    monkeypatch.delenv('OLLAMA_CLIENT_DEPLOY_KEY', raising=False)
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))

    def forbidden(*args, **kwargs):
        raise AssertionError('private helper dispatched before missing-key validation')

    monkeypatch.setattr(helper.urllib.request, 'urlopen', forbidden)
    monkeypatch.setattr(helper.subprocess, 'run', forbidden)
    with pytest.raises(SystemExit, match='required for private dependency installation'):
        helper.main()
    assert list(tmp_path.iterdir()) == []
