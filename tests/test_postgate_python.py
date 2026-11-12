"""Synthetic contracts for the completed gate2 findings. Never contacts a service."""
import importlib
import importlib.util
import json
import os
import subprocess
import sys
import types
import zipfile
from pathlib import Path

import pytest

import mdbx
from mdbx import cli, recipes

SOURCE = Path(mdbx.__file__).resolve().parent.parent


def module(name):
    spec = importlib.util.spec_from_file_location("postgate_" + name, SOURCE / "scripts" / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SOURCE / "scripts"))
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize("command", ["lint", "optimize"])
@pytest.mark.parametrize("kind", ["missing", "directory", "invalid"])
def test_cli_input_errors_are_controlled(tmp_path, capsys, command, kind):
    path = tmp_path / "input"
    if kind == "directory":
        path.mkdir()
    elif kind == "invalid":
        path.write_bytes(b"\xff")
    assert cli.main([command, str(path)]) == 2
    captured = capsys.readouterr()
    assert "cannot read" in captured.err.lower() and "Traceback" not in captured.err


def test_search_existence_check_does_not_compute_stats(monkeypatch, capsys):
    import sqlite3
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE chunks(id INTEGER)")
    con.execute("INSERT INTO chunks VALUES(1)")
    monkeypatch.setattr(cli.idx, "connect", lambda *a: con)
    monkeypatch.setattr(cli.idx, "stats", lambda *a: (_ for _ in ()).throw(AssertionError("full statistics forbidden")))
    monkeypatch.setattr(cli.srch, "search", lambda *a, **kw: [])
    assert cli.main(["search", "-m", "keyword", "synthetic"]) == 1


def test_recipe_header_exhaustion_is_not_fallback_metadata(tmp_path):
    folder = tmp_path / "recipes"
    folder.mkdir()
    (folder / "physical.md").write_text("---\nname: advertised\n" + "\n" * 1023 + "---\n# Body\n")
    assert recipes.load(tmp_path) == []


def test_recipe_inspection_errors_skip_one_entry(tmp_path, monkeypatch):
    folder = tmp_path / "recipes"
    folder.mkdir()
    (folder / "good.md").write_text("---\nname: good\n---\n# Body\n")
    (folder / "bad.md").write_text("# bad")
    original = Path.is_file
    def inspected(path):
        if path.name == "bad.md":
            raise PermissionError("synthetic")
        return original(path)
    monkeypatch.setattr(Path, "is_file", inspected)
    assert [r.name for r in recipes.load(tmp_path)] == ["good"]


def test_mcp_search_operator_exposes_text_context():
    from mdbx import mcp_server
    result = mcp_server.mql_operator("$search")
    assert result["arguments"]["text"] == "string"
    assert result["arguments"]["stage"] == "object"
    assert result["argument"] is None


def test_link_checker_full_fragments_and_bad_scheme(monkeypatch, capsys):
    m = module("check_chrome_doc_links")
    m.SRC = 'const M="https://www.mongodb.com/docs/"; const a=M+"manual/"+"bad/";'
    assert m.urls() == ["https://www.mongodb.com/docs/manual/bad/"]
    monkeypatch.setattr(m, "urls", lambda: ["without-a-scheme", "https://synthetic.invalid/"])
    monkeypatch.setattr(m.urllib.request, "urlopen", lambda *a, **kw: (_ for _ in ()).throw(ValueError("synthetic")))
    assert m.main() == 1
    assert "2 broken" in capsys.readouterr().out


def synthetic_updater(m, tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for key, value in {
        "ROOT": workspace, "HOME": tmp_path / "home", "CONFIG_PATH": tmp_path / "config",
        "DEFAULT_CLONE_DIR": tmp_path / "clone", "DEFAULT_INSTALL_DIR": tmp_path / "install",
        "LOG_PATH": tmp_path / "log", "AGENT_PLIST": tmp_path / "agent.plist",
    }.items():
        if hasattr(m, key):
            monkeypatch.setattr(m, key, value)
    return workspace


@pytest.mark.parametrize("overlap", ["workspace", "clone", "parent", "nested"])
def test_extension_rejects_destructive_install_overlap(tmp_path, monkeypatch, overlap):
    m = module("chrome_extension_autoupdate")
    workspace = synthetic_updater(m, tmp_path, monkeypatch)
    clone = tmp_path / "clone"
    clone.mkdir()
    install = {"workspace": workspace, "clone": clone, "parent": tmp_path, "nested": clone / "extension"}[overlap]
    cfg = {"repo": "synthetic", "branch": "main", "clone_dir": str(clone), "install_dir": str(install),
           "source": "release", "python": sys.executable, "no_vectors": True, "interval_min": 1}
    monkeypatch.setattr(m, "release_commit", lambda cfg: (_ for _ in ()).throw(AssertionError("external work reached")))
    with pytest.raises((ValueError, RuntimeError), match="overlap|working|installation"):
        m.run_update(cfg)
    assert workspace.is_dir() and clone.is_dir()


def test_extension_archive_limits_before_extract(tmp_path, monkeypatch):
    m = module("chrome_extension_autoupdate")
    synthetic_updater(m, tmp_path, monkeypatch)
    archive = tmp_path / "many.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("irrelevant", b"x" * 32)
    monkeypatch.setattr(m, "MAX_ARCHIVE_BYTES", 8, raising=False)
    with pytest.raises(RuntimeError, match="limit|large"):
        m.unpack_archive(archive, tmp_path / "output")
    assert not list((tmp_path / "output").glob("*"))


def test_corpus_sweep_response_shapes_are_controlled(tmp_path, monkeypatch):
    m = module("corpus_autoupdate")
    synthetic_updater(m, tmp_path, monkeypatch)
    for value in ["[]", "null"]:
        monkeypatch.setattr(m.subprocess, "run", lambda *a, value=value, **kw: types.SimpleNamespace(stdout=value, returncode=0))
        assert m.sweep(tmp_path, sys.executable) == (2, [])


def test_holdback_hides_rejected_path(tmp_path, monkeypatch, capsys):
    m = module("corpus_autoupdate")
    synthetic_updater(m, tmp_path, monkeypatch)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "SYNTH_SECRET.md").write_text("synthetic")
    monkeypatch.setattr(m, "git", lambda *a: types.SimpleNamespace(returncode=1))
    m.restore_committed(tmp_path, ["corpus/SYNTH_SECRET.md"])
    captured = capsys.readouterr()
    assert "SYNTH_SECRET" not in captured.out + captured.err + m.LOG_PATH.read_text()


def test_rotation_marker_includes_retention_and_ignores_fences(tmp_path, monkeypatch):
    m = module("rotate_workflow_logs")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    log = tmp_path / "synthetic.md"
    log.write_text("## v3\nnew\n```md\n## v99\n```\n## validation\ntext\n## v2\nmiddle\n## v1\nold\n")
    original = log.read_bytes()
    monkeypatch.setattr(m, "replace_preserving", lambda *a: (_ for _ in ()).throw(OSError("synthetic")))
    with pytest.raises(OSError):
        m.rotate(log, 0, 2, False)
    archive = next((tmp_path / "docs/archive").glob("synthetic-*.md"))
    assert b"middle" not in archive.read_bytes()
    monkeypatch.setattr(m, "replace_preserving", lambda path, data, *a: path.write_bytes(data))
    assert m.rotate(log, 0, 1, False)
    assert b"middle" in archive.read_bytes()
    assert log.read_bytes() == original[:original.index(b"## v2")]


def test_redactor_preserves_yaml_and_normalizes_hostname_case(tmp_path, monkeypatch, capsys):
    m = module("redact_corpus")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "CORPUS", tmp_path / "corpus")
    monkeypatch.setenv("MDBX_REDACTIONS", str(tmp_path / "SYNTH_SECRET.rules"))
    m.load_private()
    assert "SYNTH_SECRET" not in "".join(capsys.readouterr())
    assert m.redact_text("{path: /Users/synthetic/note}", []) == "{path: <local-path>}"
    assert m.redact_text("HOST.CORP.MONGODB.COM", []) == "internal.example.com"


def test_sweep_missing_explicit_rules_and_invalid_config_are_errors(tmp_path, monkeypatch, capsys):
    m = module("sweep_customers")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "note.md").write_text("synthetic")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **kw: types.SimpleNamespace(stdout=b"corpus/note.md\0"))
    rule = tmp_path / "rules"
    monkeypatch.setenv("MDBX_DENYLIST", str(rule))
    assert m.main(["--json"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "error"
    rule.write_text("[invalid")
    assert m.main(["--json"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "error"


def test_sweep_matches_wrapped_terms_and_sanitizes_git_env(tmp_path, monkeypatch, capsys):
    m = module("sweep_customers")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "note.md").write_text("Synthetic\nCustomer")
    rules = tmp_path / "rules"
    rules.write_text(r"Synthetic\s+Customer")
    monkeypatch.setenv("MDBX_DENYLIST", str(rules))
    monkeypatch.setenv("GIT_DIR", "SYNTH_REDIRECT")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    calls = []
    def git(argv, **kwargs):
        calls.append((argv, kwargs))
        return types.SimpleNamespace(stdout=b"corpus/note.md\0")
    monkeypatch.setattr(m.subprocess, "run", git)
    assert m.main(["--json"]) == 1
    assert len(calls) == 1 and "GIT_DIR" not in calls[0][1]["env"]
    assert json.loads(capsys.readouterr().out)["hits"][0]["line"] == 1


def test_source_copy_atomic_and_does_not_propagate_readonly_mode(tmp_path):
    m = module("sync_corpus_sources")
    source = tmp_path / "source"
    source.mkdir()
    note = source / "note.md"
    note.write_text("one")
    note.chmod(0o444)
    target = tmp_path / "target"
    state = tmp_path / "state.json"
    m.sync_tree(source, target, state)
    assert (target / "note.md").stat().st_mode & 0o200
    note.chmod(0o644)
    note.write_text("two")
    m.sync_tree(source, target, state)
    assert (target / "note.md").read_text() == "two"


def test_link_literal_scan_has_independent_runtime_bound(tmp_path):
    program = """import importlib.util,sys
spec=importlib.util.spec_from_file_location('links',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.SRC='const M="https://www.mongodb.com/docs/"; // "'+'\\\\'*100
m.urls()
"""
    result = subprocess.run([sys.executable, "-c", program, str(SOURCE / "scripts/check_chrome_doc_links.py")],
                            capture_output=True, timeout=2, check=False)
    assert result.returncode == 0


def test_mcp_store_cache_is_thread_confined_and_avoids_keyword_store(tmp_path, monkeypatch):
    import threading

    from mdbx import mcp_server as m
    path = tmp_path / "identity.sqlite"
    path.touch()
    monkeypatch.setattr(m.idx, "default_db", lambda: path)
    connections, stores, calls = [], [], []
    def db():
        con = types.SimpleNamespace(owner=threading.get_ident(), close=lambda: None)
        connections.append(con)
        return con
    def store(con):
        assert con.owner == threading.get_ident()
        result = types.SimpleNamespace(owner=con.owner)
        stores.append(result)
        return result
    def search(con, *a, **kwargs):
        assert con.owner == threading.get_ident()
        current = kwargs.get("store")
        if current is None and a[1] != "keyword":
            current = store(con)  # Faithful search._ready_store behavior when no store is supplied.
        if current is not None:
            assert current.owner == threading.get_ident()
        calls.append(kwargs)
        return []
    monkeypatch.setattr(m, "_db", db)
    monkeypatch.setattr(m.srch, "VectorStore", store)
    monkeypatch.setattr(m.srch, "search", search)
    assert m.mdb_search("one", mode="semantic") == []
    assert m.mdb_search("two", mode="hybrid") == []
    assert len(stores) == 1
    m.mdb_search("keyword", mode="keyword")
    assert "store" not in calls[-1]
    errors = []
    def work():
        try:
            m.mdb_search("thread", mode="semantic")
        except Exception as exc:  # noqa: BLE001 - transport worker failure to the test thread
            errors.append(type(exc).__name__)
    thread = threading.Thread(target=work)
    thread.start()
    thread.join(timeout=3)
    assert not errors and not thread.is_alive()
    assert len(stores) == 2 and len({s.owner for s in stores}) == 2


def transaction_fixture(tmp_path, monkeypatch):
    root = tmp_path / "owned-repository"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True, timeout=10)
    (root / ".gitignore").write_text("")
    corpus = root / "corpus"
    corpus.mkdir()
    (corpus / "old.md").write_text("old validated bytes")
    source = tmp_path / "sources/mongodb-synthetic"
    source.mkdir(parents=True)
    (source / "note.md").write_text("new validated bytes")
    rules = tmp_path / "rules"
    rules.write_text("SYNTH_SECRET")
    values = {
        "MDBX_SKILLS_SRC": str(source.parent), "MDBX_LLMS_SRC": str(tmp_path / "absent-llms"),
        "MDBX_MONGODB_DOCS_LLMS": str(tmp_path / "absent-docs"), "MDBX_CONCEPTS_SRC": str(tmp_path / "absent-concepts"),
        "MDBX_DENYLIST": str(rules), "MDBX_REDACTIONS": str(tmp_path / "absent-rules"), "MDBX_SKIP_INDEX": "1",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    m = module("sync_corpus_transaction")
    monkeypatch.setattr(m, "ROOT", root)
    return m, root, source


def test_staged_sync_never_publishes_flagged_candidate(tmp_path, monkeypatch):
    m, root, source = transaction_fixture(tmp_path, monkeypatch)
    (source / "note.md").write_text("SYNTH_SECRET")
    seen = []
    real = m.sweep_customers.main
    def gate(argv):
        seen.append(argv)
        assert (root / "corpus/old.md").read_text() == "old validated bytes"
        assert not (root / "corpus/skills").exists()
        return real(argv)
    monkeypatch.setattr(m.sweep_customers, "main", gate)
    assert m.main() == 1
    assert seen
    assert (root / "corpus/old.md").read_text() == "old validated bytes"
    assert not (root / "corpus/skills").exists()
    assert not list(root.glob(".mdbx-corpus-stage-*")) and not list(root.glob(".mdbx-corpus-preparation-*"))


def test_staged_sync_publishes_valid_generation_and_retains_old_bytes(tmp_path, monkeypatch):
    m, root, _source = transaction_fixture(tmp_path, monkeypatch)
    assert m.main() == 0
    assert (root / "corpus/skills/mongodb-synthetic/note.md").read_text() == "new validated bytes"
    recovery = list((root / ".git/mdbx-corpus-recovery").glob("*/corpus/old.md"))
    assert len(recovery) == 1 and recovery[0].read_text() == "old validated bytes"
    assert not list(root.glob(".mdbx-corpus-stage-*")) and not list(root.glob(".mdbx-corpus-preparation-*"))
    assert not (root / "data/.corpus-sync-journal.json").exists()


def test_staged_sync_exchange_failure_is_recoverable_without_data_loss(tmp_path, monkeypatch):
    m, root, _source = transaction_fixture(tmp_path, monkeypatch)
    exchange = m.exchange_entries
    monkeypatch.setattr(m, "exchange_entries", lambda *a: (_ for _ in ()).throw(OSError("synthetic")))
    assert m.main() == 1
    assert (root / "corpus/old.md").read_text() == "old validated bytes"
    assert (root / "data/.corpus-sync-journal.json").exists()
    monkeypatch.setattr(m, "exchange_entries", exchange)
    assert m.main() == 0
    assert (root / "corpus/skills/mongodb-synthetic/note.md").read_text() == "new validated bytes"


def test_redaction_linked_metadata_fails_before_replacement(tmp_path, monkeypatch):
    m = module("redact_corpus")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    file = corpus / "note.md"
    original = "/Users/synthetic/private"
    file.write_text(original)
    (tmp_path / ".git").write_text("gitdir: /untrusted/external")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "CORPUS", corpus)
    monkeypatch.setattr(m, "load_private", lambda: ([], None))
    assert m.main() == 1
    assert file.read_text() == original


def test_sync_entrypoint_holds_live_bytes_on_failed_privacy_gate(tmp_path, monkeypatch):
    import shutil
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True, timeout=10)
    shutil.copytree(SOURCE / "scripts", root / "scripts")
    (root / "corpus").mkdir()
    (root / "corpus/old.md").write_text("old validated bytes")
    source = tmp_path / "source/mongodb-synthetic"
    source.mkdir(parents=True)
    (source / "note.md").write_text("SYNTH_SECRET")
    deny = tmp_path / "deny"
    deny.write_text("SYNTH_SECRET")
    env = dict(os.environ, MDBX_SKILLS_SRC=str(source.parent), MDBX_DENYLIST=str(deny),
               MDBX_SKIP_INDEX="1", MDBX_LLMS_SRC=str(tmp_path/"absent"),
               MDBX_MONGODB_DOCS_LLMS=str(tmp_path/"absent"), MDBX_CONCEPTS_SRC=str(tmp_path/"absent"))
    result = subprocess.run(["/bin/bash", str(root/"scripts/sync_corpus.sh")], env=env, cwd=root,
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode != 0
    assert "SYNTH_SECRET" not in result.stdout + result.stderr
    assert (root/"corpus/old.md").read_text() == "old validated bytes"
    assert not (root/"corpus/skills/mongodb-synthetic/note.md").exists()


def test_sync_traversal_failure_preserves_owned_destination(tmp_path, monkeypatch):
    m = module("sync_corpus_sources")
    source = tmp_path/"source"
    source.mkdir()
    target = tmp_path/"target"
    target.mkdir()
    (target/"kept.md").write_text("keep")
    state = tmp_path/"state.json"
    original = json.dumps({str(target): ["kept.md"]})
    state.write_text(original)
    def fail(*args, **kwargs):
        kwargs["onerror"](PermissionError("synthetic unreadable subtree"))
        yield
    monkeypatch.setattr(m.os, "walk", fail)
    with pytest.raises(PermissionError):
        m.sync_tree(source, target, state)
    assert (target/"kept.md").read_text() == "keep" and state.read_text() == original


def test_sync_parent_swap_cannot_write_outside(tmp_path, monkeypatch):
    m = module("sync_corpus_sources")
    source = tmp_path/"source"
    (source/"nested").mkdir(parents=True)
    (source/"nested/note.md").write_text("candidate")
    target = tmp_path/"target"
    outside = tmp_path/"outside"
    outside.mkdir()
    (outside/"note.md").write_text("outside sentinel")
    real = m.atomic_write
    def swap(path, *args, **kwargs):
        if path == target/"nested/note.md":
            (target/"nested").mkdir()
            (target/"nested").rename(target/"retained")
            (target/"nested").symlink_to(outside, target_is_directory=True)
        return real(path, *args, **kwargs)
    monkeypatch.setattr(m, "atomic_write", swap)
    with pytest.raises((ValueError, OSError)):
        m.sync_tree(source, target, tmp_path/"state.json")
    assert (outside/"note.md").read_text() == "outside sentinel"


def test_redaction_retains_late_descriptor_write_privately(tmp_path, monkeypatch):
    m = module("redact_corpus")
    corpus = tmp_path/"corpus"
    corpus.mkdir()
    (tmp_path/".git").mkdir()
    path = corpus/"note.md"
    path.write_text("/Users/synthetic/private")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "CORPUS", corpus)
    monkeypatch.setattr(m, "load_private", lambda: ([], None))
    fd = os.open(path, os.O_WRONLY | os.O_APPEND)
    try:
        assert m.main() == 0
        os.write(fd, b" late descriptor write")
    finally:
        os.close(fd)
    retained = list((tmp_path/".git/mdbx-redaction-recovery").iterdir())
    assert len(retained) == 1
    assert retained[0].read_bytes().endswith(b" late descriptor write")
    assert path.read_text() == "<local-path>"


def test_redaction_standard_patch_mixed_state_and_reintroduction(tmp_path, monkeypatch):
    m = module("redact_corpus")
    corpus = tmp_path/"corpus"
    corpus.mkdir()
    a, b = corpus/"a.md", corpus/"b.md"
    a.write_text("after\n")
    b.write_text("before\n")
    patch = tmp_path/"standard.patch"
    patch.write_text("".join(
        f"--- a/corpus/{name}.md\n+++ b/corpus/{name}.md\n@@ -1 +1 @@\n-before\n+after\n"
        for name in ["a", "b"]))
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "CORPUS", corpus)
    monkeypatch.setattr(m, "load_private", lambda: ([], str(patch)))
    assert m.main() == 0 and a.read_text() == b.read_text() == "after\n"
    patch.write_text("--- a/corpus/a.md\n+++ b/corpus/a.md\n@@ -1 +1 @@\n-after\n+SYNTH_SECRET\n")
    monkeypatch.setattr(m, "load_private", lambda: ([("SYNTH_SECRET", "redacted")], str(patch)))
    assert m.main() == 1 and a.read_text() == "after\n"


def test_updater_reaps_descendants_before_timeout_returns(tmp_path, monkeypatch):
    m = module("corpus_autoupdate")
    synthetic_updater(m, tmp_path, monkeypatch)
    marker = tmp_path/"late-write"
    child = "import time;from pathlib import Path;time.sleep(.3);Path(" + repr(str(marker)) + ").write_text('late')"
    parent = "import subprocess,sys,time;subprocess.Popen([sys.executable,'-c'," + repr(child) + "]);time.sleep(5)"
    with pytest.raises(subprocess.TimeoutExpired):
        m.run_sync([sys.executable, "-c", parent], cwd=str(tmp_path), env=dict(os.environ), timeout=.1)
    import time
    time.sleep(.4)
    assert not marker.exists()


def fake_extension(m, path):
    path.mkdir()
    for name in m.RUNTIME_FILES:
        (path / name).write_text("synthetic")
    for folder in ["lib", "icons", "data"]:
        (path / folder).mkdir()
    (path / "manifest.json").write_text(json.dumps({"manifest_version": 3, "version": "1.0"}))
    (path / "data/build.json").write_text(json.dumps({"version": "1.0", "commit": "a" * 12}))


def test_extension_dependency_missing_keeps_installed_generation(tmp_path, monkeypatch):
    m = module("chrome_extension_autoupdate")
    synthetic_updater(m, tmp_path, monkeypatch)
    src, install = tmp_path / "source", tmp_path / "install"
    fake_extension(m, src)
    fake_extension(m, install)
    (src / "background.js").write_text("import {capture} from './lib/missing.js';")
    with pytest.raises(RuntimeError, match="incomplete"):
        m.sync_runtime(src, install)
    assert (install / "background.js").read_text() == "synthetic"


def test_extension_exchange_keeps_path_present_and_recovers_displaced_stage(tmp_path, monkeypatch):
    m = module("chrome_extension_autoupdate")
    synthetic_updater(m, tmp_path, monkeypatch)
    src, install = tmp_path / "source", tmp_path / "install"
    fake_extension(m, src)
    fake_extension(m, install)
    (src / "background.js").write_text("new runtime")
    exchange = m.exchange_entries
    seen = []
    def publish(left, right, root):
        assert (install / "background.js").read_text() == "synthetic"
        exchange(left, right, root)
        assert (install / "background.js").read_text() == "new runtime"
        seen.append(True)
    monkeypatch.setattr(m, "exchange_entries", publish)
    rename = m.os.rename
    def interrupt(left, right, *a, **kw):
        if Path(right).name.startswith(".install.backup-"):
            raise OSError("synthetic interruption after atomic exchange")
        return rename(left, right, *a, **kw)
    monkeypatch.setattr(m.os, "rename", interrupt)
    with pytest.raises(OSError):
        m.sync_runtime(src, install)
    journal = tmp_path / ".install.swap.json"
    assert seen == [True] and journal.exists()
    stage = Path(json.loads(journal.read_text())["stage"])
    assert (stage / "background.js").read_text() == "synthetic"
    monkeypatch.setattr(m.os, "rename", rename)
    m.recover_install(install, journal)
    assert not journal.exists() and not stage.exists()
    assert (install / "background.js").read_text() == "new runtime"


def test_extension_partial_clone_timeout_has_no_poisoned_destination(tmp_path, monkeypatch):
    m = module("chrome_extension_autoupdate")
    synthetic_updater(m, tmp_path, monkeypatch)
    clone = tmp_path / "clone"
    cfg = {"clone_dir": str(clone), "repo": "synthetic", "branch": "main"}
    def fail(argv, **kwargs):
        Path(argv[-1]).mkdir(exist_ok=True)
        (Path(argv[-1]) / "partial").write_text("partial")
        raise subprocess.TimeoutExpired(argv, 1)
    monkeypatch.setattr(m.subprocess, "run", fail)
    with pytest.raises(subprocess.TimeoutExpired):
        m.ensure_clone(cfg)
    assert not clone.exists() and not list(tmp_path.glob(".clone.clone-*"))


def test_extension_reindexes_existing_cache_with_sanitized_environment(tmp_path, monkeypatch):
    m = module("chrome_extension_autoupdate")
    synthetic_updater(m, tmp_path, monkeypatch)
    clone = tmp_path / "clone"
    (clone / "data").mkdir(parents=True)
    (clone / "data/mdbx.sqlite").write_bytes(b"existing keyword cache")
    (clone / "editors/chrome").mkdir(parents=True)
    (clone / "editors/chrome/manifest.json").write_text('{"version":"1.0"}')
    monkeypatch.setenv("GIT_DIR", "SYNTH_OTHER_REPO")
    monkeypatch.setenv("GIT_WORK_TREE", "SYNTH_OTHER_TREE")
    seen = []
    def run(argv, **kw):
        seen.append((argv, kw))
        return types.SimpleNamespace(returncode=0)
    monkeypatch.setattr(m.subprocess, "run", run)
    monkeypatch.setattr(m, "unpack_archive", lambda *a: None)
    m.build_from_clone({"clone_dir": str(clone), "python": sys.executable, "no_vectors": True},
                       tmp_path / "built")
    assert len(seen) == 2 and seen[0][0][-2:] == ["index", "--skip-semantic"]
    assert "--no-vectors" in seen[1][0]
    assert all("GIT_DIR" not in kw["env"] and "GIT_WORK_TREE" not in kw["env"] for _, kw in seen)


def test_recipe_index_escapes_names_and_refuses_incomplete_source(tmp_path, monkeypatch):
    m = module("gen_recipes_index")
    name = '<x>&*a*_b_[c]`'
    row = m.row(types.SimpleNamespace(name=name, path="recipes/x.md", summary="", applies_to=[]))
    assert "&lt;x&gt;&amp;" in row and r"\*a\*" in row and r"\_b\_" in row and r"\[c\]" in row
    (tmp_path / "docs").mkdir()
    (tmp_path / "corpus/recipes").mkdir(parents=True)
    target = tmp_path / "docs/RECIPES.md"
    target.write_text("prior complete source")
    monkeypatch.setattr(m, "ROOT", tmp_path)
    def incomplete(root, *, strict=False):
        assert strict
        raise ValueError("recipe metadata unavailable")
    monkeypatch.setattr(m.recipes, "load", incomplete)
    with pytest.raises(ValueError):
        m.main()
    assert target.read_text() == "prior complete source"


def test_pending_refresh_retries_publication_without_resync(tmp_path, monkeypatch):
    m = module("corpus_autoupdate")
    synthetic_updater(m, tmp_path, monkeypatch)
    clone = tmp_path / "clone"
    (clone / ".git").mkdir(parents=True)
    cfg = {"clone_dir": str(clone), "python": sys.executable, "repo": "synthetic", "branch": "main"}
    monkeypatch.setattr(m, "ensure_clone", lambda cfg: clone)
    monkeypatch.setattr(m, "run_sync", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("pending refresh resynced")))
    monkeypatch.setattr(m, "sweep", lambda *a, **kw: (0, []))
    commands = []
    failed = [False]
    def git(args, cwd, *extra):
        commands.append(args)
        if args[0] == "push" and not failed[0]:
            failed[0] = True
            return types.SimpleNamespace(returncode=1, stdout="")
        output = "a" * 40 if args[:2] == ["rev-parse", "HEAD"] else "corpus/note.md" if args[0] == "diff-tree" else ""
        return types.SimpleNamespace(returncode=0, stdout=output)
    monkeypatch.setattr(m, "git", git)
    m.record_pending(clone)
    with pytest.raises(RuntimeError, match="push failed"):
        m.run_update(cfg)
    assert m.pending_path(clone).exists()
    assert m.run_update(cfg) == 0 and not m.pending_path(clone).exists()
    assert sum(args[0] == "push" for args in commands) == 2


def test_human_answer_and_glean_terminal_controls_are_escaped(monkeypatch, capsys):
    from mdbx import providers
    auth = types.ModuleType("ai_auth")
    auth.NotConfigured = type("NotConfigured", (Exception,), {})
    auth.AIAuthError = type("AIAuthError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "ai_auth", auth)
    monkeypatch.setattr(providers, "available", lambda: True)
    secret = "\x1b[2Jsynthetic\r"
    class Connection:
        def execute(self, *args):
            return self
        def fetchone(self):
            return [1]
        def close(self):
            pass
    monkeypatch.setattr(cli.idx, "connect", lambda *a: Connection())
    monkeypatch.setattr(cli.idx, "stats", lambda *a: {"chunks": 1})
    monkeypatch.setattr(cli.srch, "search", lambda *a, **kw: [])
    answer = types.SimpleNamespace(text=secret, provider="fake", kind="test", model="fake")
    sources = [{"n": 1, "source": secret, "heading": secret, "location": secret}]
    monkeypatch.setattr(providers, "ask", lambda *a, **kw: (answer, sources))
    monkeypatch.setattr(providers, "glean_search", lambda *a, **kw: {
        "results": [{"title": secret, "datasource": secret, "url": secret, "snippet": secret}]})
    assert cli.main(["ask", "-m", "keyword", "synthetic"]) == 0
    assert cli.main(["glean", "synthetic"]) == 0
    captured = capsys.readouterr()
    assert "\x1b" not in captured.out + captured.err and "\r" not in captured.out + captured.err
    assert "synthetic" in captured.out


def test_glean_import_initialization_failure_is_one_safe_json(monkeypatch, capsys):
    import builtins
    original = builtins.__import__
    def fail(name, *a, **kw):
        if name == "ai_auth.glean_helper":
            raise RuntimeError("SYNTH_SECRET")
        return original(name, *a, **kw)
    monkeypatch.setattr(builtins, "__import__", fail)
    with pytest.raises(SystemExit) as stopped:
        module("glean_cli_helper")
    assert stopped.value.code == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out)["code"] == 1
    assert not captured.err and "SYNTH_SECRET" not in captured.out
