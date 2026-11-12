"""Synthetic regression fixtures for the maintenance scripts. No live sources or services."""
from __future__ import annotations

import builtins
import json
import os
import runpy
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return runpy.run_path(str(ROOT / "scripts" / name), run_name="_tooling_test")


def executable(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    path.chmod(0o755)


def test_doc_link_checker_reads_both_quote_forms(monkeypatch):
    module = load("check_chrome_doc_links.py")
    module["urls"].__globals__["SRC"] = """const M = "https://www.mongodb.com/docs/"; const a = 'https://www.mongodb.com/docs/missing/'; const b = M + 'manual/';"""
    assert module["urls"]() == ["https://www.mongodb.com/docs/manual/", "https://www.mongodb.com/docs/missing/"]
    seen = []
    def fail(request, **kwargs):
        import urllib.error
        seen.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, 404, "synthetic", {}, None)
    monkeypatch.setattr(module["urllib"].request, "urlopen", fail)
    assert module["main"]() == 1
    assert len(seen) == 2


def test_install_help_before_any_setup(tmp_path):
    script = tmp_path / "scripts/install.sh"
    script.parent.mkdir()
    shutil.copyfile(ROOT / "scripts/install.sh", script)
    result = subprocess.run(["/bin/bash", "./install.sh", "--help"], cwd=script.parent,
                            capture_output=True, check=False, encoding="utf-8", timeout=5)
    assert result.returncode == 0, result.stderr
    assert "One-command setup" in result.stdout


def test_install_reuses_existing_supported_virtualenv(tmp_path):
    script = tmp_path / "scripts/install.sh"
    script.parent.mkdir()
    shutil.copyfile(ROOT / "scripts/install.sh", script)
    for name, body in {"python": "printf '3.13\\n'", "pip": "exit 0", "mdbx": "exit 0"}.items():
        executable(tmp_path / ".venv/bin" / name, body)
    wrapper = 'command() { if [[ "$1" == -v && "$2" == *python3.* ]]; then return 1; fi; builtin command "$@"; }; git() { return 0; }; export -f command git; exec /bin/bash "$@"'
    result = subprocess.run(["/bin/bash", "-c", wrapper, "synthetic", str(script), "--no-model", "--no-index", "--no-agent"],
                            env={**os.environ, "PATH": "/usr/bin:/bin"},
                            capture_output=True, check=False, encoding="utf-8", timeout=5)
    assert result.returncode == 0, result.stderr
    assert "==> Done" in result.stdout


def test_watcher_passes_dash_prefixed_corpus_as_path(tmp_path):
    script = tmp_path / "scripts/watch_and_index.sh"
    script.parent.mkdir()
    shutil.copyfile(ROOT / "scripts/watch_and_index.sh", script)
    bindir = tmp_path / "bin"
    executable(bindir / "fswatch", 'printf "%s\\n" "$@" > "$WATCHED_ARGS"')
    executable(tmp_path / ".venv/bin/mdbx", "exit 0")
    result = subprocess.run(["/bin/bash", str(script)],
                            env={**os.environ, "PATH": str(bindir) + ":/usr/bin:/bin", "MDBX_CORPUS": "--help",
                                 "WATCHED_ARGS": str(tmp_path / "args")},
                            capture_output=True, check=False, encoding="utf-8", timeout=5)
    assert result.returncode == 0, result.stderr
    args = (tmp_path / "args").read_text().splitlines()
    assert "--" in args and args.index("--") < args.index("--help")


def recipe_generator(tmp_path, monkeypatch):
    module = load("gen_recipes_index.py")
    main = module["main"]
    monkeypatch.setitem(main.__globals__, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "corpus/recipes").mkdir(parents=True)
    return main, module["recipes"], tmp_path / "docs/RECIPES.md"


def test_recipe_index_preserves_names_paths_and_table_cells(tmp_path, monkeypatch):
    main, recipes, output = recipe_generator(tmp_path, monkeypatch)
    items = [SimpleNamespace(name=name, path="recipes/physical file.md", summary="left | right", applies_to=["atlas|managed"])
             for name in ("shard-a-collection", "extra")]
    monkeypatch.setattr(recipes, "load", lambda root: items)
    main()
    text = output.read_text(encoding="utf-8")
    for item in items:
        assert f"[{item.name}](../corpus/recipes/physical%20file.md)" in text
    assert text.count("| atlas\\|managed | left \\| right |") == 2


def test_recipe_index_rejects_duplicate_names_before_write(tmp_path, monkeypatch):
    main, recipes, output = recipe_generator(tmp_path, monkeypatch)
    monkeypatch.setattr(recipes, "load", lambda root: [
        SimpleNamespace(name="same", path=f"recipes/{name}.md", summary="", applies_to=[]) for name in ("a", "b")])
    output.write_text("previous index", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        main()
    assert output.read_text(encoding="utf-8") == "previous index"


def test_recipe_index_writes_utf8_explicitly(tmp_path, monkeypatch):
    main, recipes, output = recipe_generator(tmp_path, monkeypatch)
    monkeypatch.setattr(recipes, "load", lambda root: [])
    original = Path.open
    def locale_open(self, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        return original(self, mode, buffering, "ascii" if encoding in (None, "locale") else encoding, errors, newline)
    monkeypatch.setattr(Path, "open", locale_open)
    main()
    assert "—" in output.read_text(encoding="utf-8")


@pytest.mark.parametrize("name,code,message", [
    ("ai_auth", 2, "ai-auth library not installed"),
    ("synthetic_dependency", 1, "ai-auth helper import failed"),
])
def test_glean_helper_distinguishes_package_and_dependency_failure(monkeypatch, capsys, name, code, message):
    original = builtins.__import__
    def missing(module, *args, **kwargs):
        if module == "ai_auth.glean_helper":
            raise ModuleNotFoundError("synthetic private payload", name=name)
        return original(module, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", missing)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / "scripts/glean_cli_helper.py"), run_name="__main__")
    assert exc.value.code == code
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["error"] == message and payload["code"] == code
    assert "synthetic private payload" not in captured.out + captured.err


def test_sync_sources_reconcile_owned_files_without_writing_symlink_target(tmp_path):
    sync = load("sync_corpus_sources.py")["sync_tree"]
    source, destination = tmp_path / "source", tmp_path / "corpus/skills/mongodb-synthetic"
    source.mkdir()
    destination.mkdir(parents=True)
    state = tmp_path / "state.json"
    (source / "a.md").write_text("synthetic")
    (source / "unsafe.csv").write_text("fixture_customer_93815")
    (destination / "curated.md").write_text("curated")
    sync(source, destination, state)
    assert (destination / "a.md").read_text() == "synthetic"
    assert not (destination / "unsafe.csv").exists()
    (source / "a.md").unlink()
    sync(source, destination, state)
    assert not (destination / "a.md").exists() and (destination / "curated.md").read_text() == "curated"
    outside = tmp_path / "outside.txt"
    outside.write_text("external synthetic content")
    (source / "link.txt").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        sync(source, destination, state)
    assert outside.read_text() == "external synthetic content"
    (source / "link.txt").unlink()
    (destination / "link.md").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        sync(source, destination, state)
    assert outside.read_text() == "external synthetic content"


def test_sync_shell_gates_hide_payload_and_pin_index_root(tmp_path):
    subprocess.run(["git", "-c", "init.templateDir=", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("sync_corpus.sh", "sync_corpus_sources.py", "maintenance_safety.py"):
        if (ROOT / "scripts" / name).exists():
            shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    (scripts / "redact_corpus.py").write_text("print('redaction ok')\n")
    (scripts / "sweep_customers.py").write_text("import os,sys; print('fixture_customer_93815');sys.exit(int(os.environ.get('FAIL_GATE','0')))\n")
    skills = tmp_path / "source/mongodb-synthetic"
    skills.mkdir(parents=True)
    (skills / "note.md").write_text("synthetic documentation")
    executable(tmp_path / ".venv/bin/mdbx", 'printf "%s\\n" "$@" > "$INDEX_ARGS"')
    deny = tmp_path / "deny"; deny.write_text("# synthetic\n")
    env = {**os.environ, "MDBX_SKIP_INDEX": "0", "MDBX_DENYLIST": str(deny), "MDBX_SKILLS_SRC": str(skills.parent), "MDBX_LLMS_SRC": str(tmp_path / "empty"),
           "MDBX_MONGODB_DOCS_LLMS": str(tmp_path / "empty/docs"), "MDBX_CONCEPTS_SRC": str(tmp_path / "empty/concepts"),
           "MDBX_CORPUS": str(tmp_path / "alternate"), "INDEX_ARGS": str(tmp_path / "index-args")}
    result = subprocess.run(["/bin/bash", str(scripts / "sync_corpus.sh")], env=env,
                            capture_output=True, check=False, encoding="utf-8", timeout=10)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "index-args").read_text().splitlines() == ["index", "--corpus", str(tmp_path / "corpus")]
    result = subprocess.run(["/bin/bash", str(scripts / "sync_corpus.sh")], env={**env, "FAIL_GATE": "1"},
                            capture_output=True, check=False, encoding="utf-8", timeout=10)
    assert result.returncode != 0 and "fixture_customer_93815" not in result.stdout + result.stderr


def test_sync_publication_rejects_unscanned_candidates(tmp_path, monkeypatch):
    module = load("sync_corpus_sources.py")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "unsafe.csv").write_text("synthetic only")
    monkeypatch.setattr(module["subprocess"], "run", lambda *args, **kwargs: SimpleNamespace(stdout=b"corpus/unsafe.csv\0"))
    with pytest.raises(ValueError, match="not inspected"):
        module["check_publication"](corpus)


def test_sync_fact_families_keep_only_selected_exports(tmp_path):
    sync = load("sync_corpus_sources.py")["sync_tree"]
    source, destination = tmp_path / "source", tmp_path / "corpus"
    source.mkdir()
    for name in ("llms.txt", "llms-full.txt", "llms-small.txt", "llms-facts.txt"):
        (source / name).write_text("synthetic")
    sync(source, destination, tmp_path / "state.json", facts_only=True)
    assert sorted(p.name for p in destination.iterdir()) == ["llms-facts.txt", "llms.txt"]
