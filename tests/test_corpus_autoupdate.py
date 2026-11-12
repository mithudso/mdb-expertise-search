"""Corpus auto-updater: sync into its own clone, hold back flagged files, commit and push only clean ones."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("corpus_autoupdate", ROOT / "scripts" / "corpus_autoupdate.py")
cu = importlib.util.module_from_spec(spec)
sys.modules["corpus_autoupdate"] = cu
spec.loader.exec_module(cu)

FAKE_SYNC = """#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
mkdir -p corpus
echo "fresh note about indexes" > corpus/good.md
echo "see mdb-tam for details" > corpus/leak.md
echo "edited source text with mdb-tam" > corpus/kept.md
"""


def run(cwd: Path, *args: str) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True, timeout=30).stdout


def make_origin(tmp: Path) -> Path:
    work = tmp / "seed"
    (work / "scripts").mkdir(parents=True)
    (work / "corpus").mkdir()
    shutil.copy(ROOT / "scripts" / "sweep_customers.py", work / "scripts" / "sweep_customers.py")
    shutil.copy(ROOT / "scripts" / "maintenance_safety.py", work / "scripts" / "maintenance_safety.py")
    (work / "scripts" / "sync_corpus.sh").write_text(FAKE_SYNC)
    (work / "corpus" / "kept.md").write_text("clean committed text\n")
    run(work, "git", "init", "-q", "-b", "main")
    run(work, "git", "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    run(work, "git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed")
    bare = tmp / "origin.git"
    run(tmp, "git", "clone", "-q", "--bare", str(work), str(bare))
    return bare


def test_hit_regex_extracts_corpus_path():
    m = cu.HIT_RE.match("corpus/skills/x/SKILL.md:12: /mdb-tam/ text")
    assert m and m.group(1) == "corpus/skills/x/SKILL.md"
    assert cu.HIT_RE.match("note: no denylist") is None


def test_agent_plist_runs_the_script(tmp_path):
    cfg = {"python": "/usr/bin/python3", "interval_min": 360}
    plist = cu.agent_plist(cfg)
    assert plist["StartInterval"] == 360 * 60
    assert plist["ProgramArguments"][-1] == "run"
    assert plist["ProgramArguments"][1].endswith("corpus_autoupdate.py")


def test_run_update_pushes_clean_files_and_holds_back_flagged(tmp_path, monkeypatch):
    origin = make_origin(tmp_path)
    deny = tmp_path / "denylist.txt"
    deny.write_text("# none\n")
    monkeypatch.setenv("MDBX_DENYLIST", str(deny))
    monkeypatch.setattr(cu, "LOG_PATH", tmp_path / "log.txt")
    monkeypatch.setattr(cu, "PROTECTED", [])
    for git_env in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(git_env, "t")
    for git_env in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(git_env, "t@t")
    cfg = {"repo": str(origin), "branch": "main", "clone_dir": str(tmp_path / "clone"), "python": sys.executable}

    clone = cu.ensure_clone(cfg)
    run(clone, "git", "config", "user.name", "fixture")
    run(clone, "git", "config", "user.email", "fixture@example.invalid")
    assert cu.run_update(cfg) == 0

    check = tmp_path / "check"
    run(tmp_path, "git", "clone", "-q", str(origin), str(check))
    assert (check / "corpus" / "good.md").read_text() == "fresh note about indexes\n"
    assert not (check / "corpus" / "leak.md").exists()                      # new + flagged: dropped
    assert (check / "corpus" / "kept.md").read_text() == "clean committed text\n"  # tracked + flagged: reverted

    # a second pass has nothing new to commit
    before = run(check, "git", "rev-list", "--count", "HEAD").strip()
    assert cu.run_update(cfg) == 0
    run(check, "git", "pull", "-q")
    assert run(check, "git", "rev-list", "--count", "HEAD").strip() == before


def test_run_update_refuses_without_denylist(tmp_path, monkeypatch):
    monkeypatch.setenv("MDBX_DENYLIST", str(tmp_path / "missing.txt"))
    monkeypatch.setattr(cu, "LOG_PATH", tmp_path / "log.txt")
    cfg = {"repo": str(make_origin(tmp_path)), "branch": "main", "clone_dir": str(tmp_path / "clone"),
           "python": sys.executable}
    assert cu.run_update(cfg) == 1


def test_unowned_checkout_and_traversal_paths_are_preserved(tmp_path):
    import pytest
    origin = make_origin(tmp_path)
    clone = tmp_path / "clone"
    run(tmp_path, "git", "clone", "-q", str(origin), str(clone))
    victim = tmp_path / "victim"; victim.write_text("keep")
    before = run(clone, "git", "rev-parse", "HEAD")
    cfg = {"clone_dir": str(clone), "repo": str(origin), "branch": "main"}
    with pytest.raises(RuntimeError, match="not owned"): cu.ensure_clone(cfg)
    assert run(clone, "git", "rev-parse", "HEAD") == before
    assert (clone / "corpus/kept.md").read_text() == "clean committed text\n"
    with pytest.raises(RuntimeError): cu.restore_committed(clone, ["corpus/../../victim"])
    assert victim.read_text() == "keep"


def test_sync_failure_aborts_before_gate_and_protected_missing_paths_restore(tmp_path, monkeypatch):
    from types import SimpleNamespace
    clone = tmp_path / "clone"; clone.mkdir(); deny = tmp_path / "deny"; deny.write_text("synthetic")
    monkeypatch.setenv("MDBX_DENYLIST", str(deny)); monkeypatch.setattr(cu, "LOG_PATH", tmp_path / "log")
    monkeypatch.setattr(cu, "ensure_clone", lambda cfg: clone); monkeypatch.setattr(cu, "reset_to_origin", lambda *a: None)
    monkeypatch.setattr(cu, "run_sync", lambda *a, **k: SimpleNamespace(returncode=4, stdout="SYNTH_SECRET", stderr="SYNTH_SECRET"))
    monkeypatch.setattr(cu, "sweep", lambda *a: (_ for _ in ()).throw(AssertionError("must abort before sweep")))
    cfg = {"clone_dir": str(clone), "repo": "synthetic", "branch": "main", "python": sys.executable}
    assert cu.run_update(cfg) == 1; assert "SYNTH_SECRET" not in (tmp_path / "log").read_text()


def test_config_validation_lazy_origin_and_environment(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    import pytest
    cfgfile = tmp_path / "config"; monkeypatch.setattr(cu, "CONFIG_PATH", cfgfile)
    cfgfile.write_text(json.dumps({"repo": "configured", "clone_dir": None}))
    monkeypatch.setattr(cu, "origin_url", lambda: (_ for _ in ()).throw(AssertionError("unnecessary origin lookup")))
    with pytest.raises((ValueError, RuntimeError)): cu.effective_config(SimpleNamespace())
    cfgfile.write_text(json.dumps({"repo": "configured"})); monkeypatch.setenv("MDBX_DENYLIST", str(tmp_path / "deny"))
    config = cu.effective_config(SimpleNamespace()); assert config["repo"] == "configured"
    assert cu.agent_plist(config)["EnvironmentVariables"]["MDBX_DENYLIST"] == str(tmp_path / "deny")


def test_rebased_outgoing_tree_is_swept_and_missing_protected_paths_restore(tmp_path, monkeypatch):
    from types import SimpleNamespace
    clone = tmp_path / "clone"; clone.mkdir(); deny = tmp_path / "deny"; deny.write_text("synthetic")
    monkeypatch.setenv("MDBX_DENYLIST", str(deny)); monkeypatch.setattr(cu, "LOG_PATH", tmp_path / "log")
    monkeypatch.setattr(cu, "ensure_clone", lambda cfg: clone); monkeypatch.setattr(cu, "reset_to_origin", lambda *a: None)
    monkeypatch.setattr(cu, "run_sync", lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""))
    restored = []; monkeypatch.setattr(cu, "PROTECTED", ["corpus/missing.md"]); monkeypatch.setattr(cu, "restore_committed", lambda clone, files: restored.extend(files))
    trace = []
    sweeps = iter([(0, []), (0, []), (2, [])])
    def sweep(*args):
        trace.append("sweep")
        return next(sweeps)
    monkeypatch.setattr(cu, "sweep", sweep)
    commands = []
    def must(args, *other):
        commands.append(args)
        trace.append(args[0])
        if args[0] == "status":
            return " M corpus/good.md\n"
        if args[0] == "rev-parse":
            return "a" * 40
        if args[0] == "diff-tree":
            return "corpus/good.md\n"
        return ""
    def git(args, *other):
        trace.append("pull-rebase" if args[:2] == ["pull", "--rebase"] else args[0])
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(cu, "must_git", must); monkeypatch.setattr(cu, "git", git)
    assert cu.run_update({"clone_dir": str(clone), "branch": "main", "python": sys.executable}) == 1
    assert restored == ["corpus/missing.md"]
    assert trace.index("commit") < trace.index("pull-rebase") < len(trace) - 1
    assert trace[-1] == "sweep"
    assert not any(args[0] == "push" for args in commands)


def test_sweep_crash_has_a_distinct_private_failure_category(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace
    monkeypatch.setattr(cu, "LOG_PATH", tmp_path / "log")
    monkeypatch.setattr(cu.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=7, stdout="SYNTH_SECRET", stderr="SYNTH_SECRET"))
    assert cu.sweep(tmp_path, sys.executable) == (2, [])
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "exit 7" in output and "SYNTH_SECRET" not in output
