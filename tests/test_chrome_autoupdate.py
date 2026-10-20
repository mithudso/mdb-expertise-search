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
    monkeypatch.setattr(au, "build_from_clone", lambda cfg: src)
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
