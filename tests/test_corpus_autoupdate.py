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
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout


def make_origin(tmp: Path) -> Path:
    work = tmp / "seed"
    (work / "scripts").mkdir(parents=True)
    (work / "corpus").mkdir()
    shutil.copy(ROOT / "scripts" / "sweep_customers.py", work / "scripts" / "sweep_customers.py")
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
