"""Chrome extension auto-updater: build identity, update decision, atomic sync, launchd plist."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("chrome_autoupdate", ROOT / "scripts" / "chrome_extension_autoupdate.py")
au = importlib.util.module_from_spec(spec)
sys.modules["chrome_autoupdate"] = au
spec.loader.exec_module(au)


def test_build_id_and_needs_update():
    assert au.build_id({"commit": "abcdef123456"}) == "abcdef123456"
    assert au.build_id({"commit": "unknown", "version": "0.3.0", "built_at": "t"}) == "0.3.0@t"
    assert au.build_id({}) == ""
    assert au.needs_update({}, "abcdef123456") is True            # nothing installed
    assert au.needs_update({"commit": "abcdef123456"}, "abcdef123456") is False
    assert au.needs_update({"commit": "abcdef1"}, "abcdef123456") is False  # short-SHA prefix match
    assert au.needs_update({"commit": "abcdef123456"}, "fedcba654321") is True
    assert au.needs_update({"commit": "abcdef123456"}, "") is False  # unknown upstream: do nothing
    assert au.needs_update({"commit": "abcdef123456"}, "", force=True) is True


def test_repo_slug():
    assert au.repo_slug("https://github.com/mithudso/mdb-expertise-search.git") == "mithudso/mdb-expertise-search"
    assert au.repo_slug("git@github.com:mithudso/x.git") == "mithudso/x"
    assert au.repo_slug("https://github.com/a/b/") == "a/b"


def _fake_ext(src: Path) -> None:
    (src / "lib").mkdir(parents=True)
    (src / "data").mkdir()
    (src / "icons").mkdir()
    (src / "test").mkdir()
    for f in au.RUNTIME_FILES:
        (src / f).write_text(f"// {f}")
    (src / "manifest.json").write_text(json.dumps({"manifest_version": 3, "version": "0.3.0", "background": {"service_worker": "background.js"}, "action": {"default_popup": "popup.html"}}))
    (src / "lib" / "a.js").write_text("x")
    (src / "lib" / "notes.md").write_text("skip me")
    (src / "data" / "build.json").write_text(json.dumps({"commit": "c2", "version": "0.3.0"}))
    (src / "data" / "chunks.bin").write_bytes(b"\x00\x01")
    (src / "icons" / "icon16.png").write_bytes(b"png")
    (src / "test" / "x.test.mjs").write_text("skip")
    (src / "README.md").write_text("skip")


def test_sync_runtime_copies_only_runtime_and_swaps_atomically(tmp_path):
    src = tmp_path / "src"
    _fake_ext(src)
    install = tmp_path / "ext"
    install.mkdir()
    (install / "stale.js").write_text("old")
    (install / "data").mkdir()
    (install / "data" / "build.json").write_text(json.dumps({"commit": "c1"}))
    n = au.sync_runtime(src, install)
    assert n == len(au.RUNTIME_FILES) + 4  # a.js, build.json, chunks.bin, icon16.png
    assert not (install / "stale.js").exists()
    assert not (install / "README.md").exists() and not (install / "test").exists()
    assert not (install / "lib" / "notes.md").exists()
    assert (install / "lib" / "a.js").read_text() == "x"
    assert au.read_stamp(install)["commit"] == "c2"
    assert not install.with_name("ext.new").exists() and not install.with_name("ext.old").exists()


def test_sync_runtime_refuses_without_manifest(tmp_path):
    import pytest
    (tmp_path / "src").mkdir()
    with pytest.raises(RuntimeError):
        au.sync_runtime(tmp_path / "src", tmp_path / "ext")


def test_agent_plist_shape(tmp_path):
    cfg = {"python": "/usr/bin/python3", "interval_min": 7, "install_dir": str(tmp_path)}
    plist = au.agent_plist(cfg, script=Path("/repo/scripts/chrome_extension_autoupdate.py"))
    assert plist["Label"] == au.AGENT_LABEL
    assert plist["ProgramArguments"] == ["/usr/bin/python3", "/repo/scripts/chrome_extension_autoupdate.py", "run"]
    assert plist["StartInterval"] == 420 and plist["RunAtLoad"] is True
    assert "/opt/homebrew/bin" in plist["EnvironmentVariables"]["PATH"]


def test_run_update_skips_when_current(tmp_path, monkeypatch, capsys):
    install = tmp_path / "ext"
    (install / "data").mkdir(parents=True)
    (install / "data" / "build.json").write_text(json.dumps({"commit": "abc123456789"}))
    monkeypatch.setattr(au, "upstream_commit", lambda cfg: "abc123456789")
    monkeypatch.setattr(au, "checkout_upstream", lambda cfg: (_ for _ in ()).throw(AssertionError("must not build")))
    monkeypatch.setattr(au, "LOG_PATH", tmp_path / "log.txt")
    cfg = {"source": "git", "install_dir": str(install), "clone_dir": str(tmp_path / "clone"), "repo": "r",
           "branch": "main", "python": sys.executable, "interval_min": 10, "no_vectors": False}
    assert au.run_update(cfg) == 0
    assert "up to date" in capsys.readouterr().out


def test_run_update_builds_and_installs(tmp_path, monkeypatch):
    src = tmp_path / "clone" / "editors" / "chrome"
    _fake_ext(src)
    install = tmp_path / "ext"
    monkeypatch.setattr(au, "upstream_commit", lambda cfg: "c2")
    monkeypatch.setattr(au, "checkout_upstream", lambda cfg: "c2")
    monkeypatch.setattr(au, "build_from_clone", lambda cfg, destination=None: src)
    monkeypatch.setattr(au, "LOG_PATH", tmp_path / "log.txt")
    cfg = {"source": "git", "install_dir": str(install), "clone_dir": str(tmp_path / "clone"), "repo": "r",
           "branch": "main", "python": sys.executable, "interval_min": 10, "no_vectors": False}
    assert au.run_update(cfg) == 0
    assert au.read_stamp(install)["commit"] == "c2"
    assert (install / "manifest.json").exists()


def test_effective_config_merges_file_and_args(tmp_path, monkeypatch):
    monkeypatch.setattr(au, "CONFIG_PATH", tmp_path / "cfg.json")
    (tmp_path / "cfg.json").write_text(json.dumps({"interval_min": 3, "source": "release"}))
    ns = type("NS", (), {k: None for k in au.STATE_KEYS})()
    ns.install_dir = tmp_path / "ext"
    cfg = au.effective_config(ns)
    assert cfg["interval_min"] == 3 and cfg["source"] == "release"
    assert cfg["install_dir"] == str(tmp_path / "ext") and cfg["branch"] == "main"
    au.save_config(cfg)
    saved = json.loads((tmp_path / "cfg.json").read_text())
    assert set(saved) <= set(au.STATE_KEYS) and saved["install_dir"] == str(tmp_path / "ext")
    restored = au.effective_config(type("NS", (), {})())
    assert restored["source"] == "release" and restored["interval_min"] == 3
    assert restored["install_dir"] == str(tmp_path / "ext")

def test_sync_runtime_preserves_install_on_promotion_failure(tmp_path, monkeypatch):
    import pytest
    source = tmp_path / "source"
    _fake_ext(source)
    install = tmp_path / "ext"
    (install / "data").mkdir(parents=True)
    (install / "data/build.json").write_text(json.dumps({"commit": "c1"}))
    real_rename = au.os.rename
    def fail_promotion(src, dst):
        if Path(src).name.startswith(".ext.stage-") and Path(dst) == install:
            raise OSError("synthetic promotion failure")
        return real_rename(src, dst)
    monkeypatch.setattr(au.os, "rename", fail_promotion)
    with pytest.raises(OSError, match="synthetic promotion failure"):
        au.sync_runtime(source, install)
    assert au.read_stamp(install)["commit"] == "c1"


def test_install_preserves_unowned_siblings_and_rolls_back_failure(tmp_path, monkeypatch):
    import pytest
    src = tmp_path / "src"; _fake_ext(src); install = tmp_path / "ext"; install.mkdir(); (install / "previous").write_text("keep")
    sibling = tmp_path / "ext.old"; sibling.mkdir(); (sibling / "private").write_text("preserve")
    real = au.os.rename
    def fail_stage(source, destination):
        if str(source).find(".stage-") >= 0: raise OSError("synthetic rename failure")
        return real(source, destination)
    monkeypatch.setattr(au.os, "rename", fail_stage)
    with pytest.raises((OSError, RuntimeError)): au.sync_runtime(src, install)
    assert (install / "previous").read_text() == "keep"
    assert (sibling / "private").read_text() == "preserve"


def test_install_rejects_incomplete_manifest_runtime(tmp_path):
    import pytest
    src = tmp_path / "src"; _fake_ext(src); (src / "background.js").unlink()
    install = tmp_path / "ext"; install.mkdir(); (install / "keep").write_text("old")
    with pytest.raises(RuntimeError): au.sync_runtime(src, install)
    assert (install / "keep").read_text() == "old"


def test_build_explicitly_confines_destinations_and_skips_semantic(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import pytest
    clone = tmp_path / "clone"; clone.mkdir()
    monkeypatch.setenv("MDBX_DB", str(tmp_path / "unrelated.sqlite")); monkeypatch.setenv("MDBX_CORPUS", str(tmp_path / "private"))
    seen = []
    def run(argv, **kwargs):
        seen.append((argv, kwargs["env"]))
        assert kwargs["env"]["MDBX_DB"] == str(clone / "data/mdbx.sqlite")
        assert kwargs["env"]["MDBX_CORPUS"] == str(clone / "corpus")
        if "index" in argv: assert "--skip-semantic" in argv
        if any(str(arg).endswith("package_chrome_extension.py") for arg in argv):
            assert "--no-vectors" in argv
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(au.subprocess, "run", run); monkeypatch.setattr(au, "LOG_PATH", tmp_path / "log")
    cfg = {"clone_dir": str(clone), "python": sys.executable, "no_vectors": True}
    with pytest.raises((OSError, RuntimeError, ValueError)): au.build_from_clone(cfg)
    assert seen


def test_existing_unowned_clone_and_bad_revision_are_refused(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import pytest
    clone = tmp_path / "clone"; (clone / ".git").mkdir(parents=True)
    cfg = {"clone_dir": str(clone), "repo": "synthetic-repo", "branch": "main"}
    with pytest.raises(RuntimeError): au.ensure_clone(cfg)
    monkeypatch.setattr(au, "ensure_clone", lambda cfg: clone)
    monkeypatch.setattr(au, "git", lambda args, cwd: SimpleNamespace(returncode=0, stdout="origin/missing", stderr="synthetic secret"))
    with pytest.raises(RuntimeError): au.upstream_commit(cfg)


def test_config_paths_option_order_and_sanitized_log(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(au, "CONFIG_PATH", tmp_path / "cfg"); monkeypatch.setattr(au, "LOG_PATH", tmp_path / "log")
    monkeypatch.chdir(tmp_path); monkeypatch.setattr(au, "origin_url", lambda: "synthetic")
    captured = {}; monkeypatch.setattr(au, "install_agent", lambda cfg: captured.update(cfg) or 0)
    assert au.main(["install-agent", "--interval-min", "3", "--install-dir", "relative"]) == 0
    assert Path(captured["install_dir"]).is_absolute()
    au.log("https://user:SYNTH_SECRET@example.test/repo.git")
    assert "SYNTH_SECRET" not in capsys.readouterr().out; assert "SYNTH_SECRET" not in (tmp_path / "log").read_text()


def test_interrupted_swap_recovers_the_owned_backup(tmp_path):
    source = tmp_path / "src"; _fake_ext(source)
    install = tmp_path / "ext"; backup = tmp_path / ".ext.backup-synthetic"; backup.mkdir(); (backup / "previous").write_text("keep")
    stage = tmp_path / ".ext.stage-synthetic"; stage.mkdir()
    journal = tmp_path / ".ext.swap.json"; journal.write_text(json.dumps({"backup": str(backup), "stage": str(stage)}))
    au.recover_install(install, journal)
    assert (install / "previous").read_text() == "keep"; assert not stage.exists(); assert not journal.exists()


def test_duplicate_update_reports_busy_without_touching_sources(tmp_path, monkeypatch):
    from maintenance_safety import lock
    clone = tmp_path / "clone"; install = tmp_path / "install"; monkeypatch.setattr(au, "LOG_PATH", tmp_path / "log")
    monkeypatch.setattr(au, "upstream_commit", lambda cfg: (_ for _ in ()).throw(AssertionError("must not fetch while busy")))
    with lock(tmp_path / ".clone.chrome-update.lock"):
        assert au.run_update({"clone_dir": str(clone), "install_dir": str(install)}) == 0


def test_expected_operational_errors_use_the_command_boundary(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(au, "CONFIG_PATH", tmp_path / "cfg"); monkeypatch.setattr(au, "LOG_PATH", tmp_path / "log")
    monkeypatch.setattr(au, "origin_url", lambda: "synthetic")
    monkeypatch.setattr(au, "run_update", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("SYNTH_SECRET")))
    assert au.main(["run"]) == 1; assert "SYNTH_SECRET" not in capsys.readouterr().out
