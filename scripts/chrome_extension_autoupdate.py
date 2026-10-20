#!/usr/bin/env python3
"""Keep an unpacked install of the MongoDB Expertise Chrome extension current with GitHub.

Chrome only auto-updates Web Store / force-installed extensions. For a *Load unpacked* install this
script is the updater: a launchd agent runs it every few minutes; when ``origin/<branch>`` has moved
it pulls its own clone of the repo, rebuilds the extension (``scripts/package_chrome_extension.py``,
with vectors when a local Ollama is up), swaps the files into the folder Chrome loads, and writes
``data/build.json``. The extension's service worker (``editors/chrome/lib/autoupdate.js``) notices the
new build id within five minutes and calls ``chrome.runtime.reload()``. Push → live, no clicks.

    python scripts/chrome_extension_autoupdate.py install-agent [--interval-min 10] [--install-dir DIR]
    python scripts/chrome_extension_autoupdate.py status          # installed build vs. origin
    python scripts/chrome_extension_autoupdate.py run [--force]   # one update pass (what the agent runs)
    python scripts/chrome_extension_autoupdate.py uninstall-agent

Sources (``--source``):
  git      (default) clone/fetch ``--repo`` (this checkout's origin) into ~/Library/Caches/mdbx/chrome-autoupdate/repo
           and build locally — keeps semantic vectors when Ollama is running.
  release  download the CI build (``gh release download chrome-latest``), keyword search only; needs ``gh`` auth.

First time: run ``install-agent``, then in chrome://extensions → Load unpacked → pick the install dir
(printed; default ``~/Library/Application Support/mdbx/chrome-extension``). Settings persist in
``~/.config/mdbx/chrome-autoupdate.json``; log: ``~/Library/Logs/mdbx-chrome-autoupdate.log``.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
CONFIG_PATH = Path(os.environ.get("MDBX_AUTOUPDATE_CONFIG", HOME / ".config" / "mdbx" / "chrome-autoupdate.json"))
DEFAULT_INSTALL_DIR = HOME / "Library" / "Application Support" / "mdbx" / "chrome-extension"
DEFAULT_CLONE_DIR = HOME / "Library" / "Caches" / "mdbx" / "chrome-autoupdate" / "repo"
LOG_PATH = HOME / "Library" / "Logs" / "mdbx-chrome-autoupdate.log"
AGENT_LABEL = "com.mdbx.chrome-autoupdate"
AGENT_PLIST = HOME / "Library" / "LaunchAgents" / f"{AGENT_LABEL}.plist"
DEFAULT_REPO = "https://github.com/mithudso/mdb-expertise-search.git"
RELEASE_TAG = "chrome-latest"
RELEASE_ASSET = "mongodb-expertise-chrome.zip"
RUNTIME_FILES = ["manifest.json", "background.js", "popup.html", "popup.css", "popup.js", "app.html", "app.css",
                 "app.js"]
RUNTIME_DIRS = {"lib": {".js"}, "icons": {".png"}, "data": {".json", ".bin"}}
STATE_KEYS = ("source", "repo", "branch", "install_dir", "clone_dir", "python", "interval_min", "no_vectors")


def log(msg: str) -> None:
    line = f"[{dt.datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


# ---- config ----
def load_config() -> dict:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({k: cfg[k] for k in STATE_KEYS if k in cfg}, indent=2) + "\n", encoding="utf-8")


def origin_url(repo_dir: Path = ROOT) -> str:
    try:
        out = subprocess.run(["git", "-C", str(repo_dir), "remote", "get-url", "origin"], capture_output=True,
                             text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip()


def effective_config(args) -> dict:
    cfg = load_config()
    for key in STATE_KEYS:
        val = getattr(args, key, None)
        if val is not None:
            cfg[key] = str(val) if isinstance(val, Path) else val
    cfg.setdefault("source", "git")
    cfg.setdefault("repo", origin_url() or DEFAULT_REPO)
    cfg.setdefault("branch", "main")
    cfg.setdefault("install_dir", str(DEFAULT_INSTALL_DIR))
    cfg.setdefault("clone_dir", str(DEFAULT_CLONE_DIR))
    cfg.setdefault("python", sys.executable)
    cfg.setdefault("interval_min", 10)
    cfg.setdefault("no_vectors", False)
    return cfg


# ---- build identity ----
def read_stamp(ext_dir: Path) -> dict:
    try:
        data = json.loads((Path(ext_dir) / "data" / "build.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def build_id(stamp: dict) -> str:
    commit = str(stamp.get("commit") or "").strip()
    if commit and commit != "unknown":
        return commit
    v, b = str(stamp.get("version") or ""), str(stamp.get("built_at") or "")
    return f"{v}@{b}" if (v or b) else ""


def needs_update(installed: dict, upstream_commit: str, *, force: bool = False) -> bool:
    """True when the installed build is not the upstream commit (prefix match on short SHAs)."""
    if force or not upstream_commit:
        return force
    have = build_id(installed)
    if not have:
        return True
    return not (upstream_commit.startswith(have) or have.startswith(upstream_commit))


# ---- git source ----
def git(args: list[str], cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False)


def ensure_clone(cfg: dict) -> Path:
    clone = Path(cfg["clone_dir"])
    if not (clone / ".git").is_dir():
        clone.parent.mkdir(parents=True, exist_ok=True)
        log(f"cloning {cfg['repo']} → {clone}")
        res = subprocess.run(["git", "clone", "--branch", cfg["branch"], "--single-branch", cfg["repo"], str(clone)],
                             capture_output=True, text=True, timeout=900, check=False)
        if res.returncode != 0:
            raise RuntimeError(f"git clone failed: {res.stderr.strip()[-400:]}")
    return clone


def upstream_commit(cfg: dict) -> str:
    clone = ensure_clone(cfg)
    res = git(["fetch", "--quiet", "origin", cfg["branch"]], clone)
    if res.returncode != 0:
        raise RuntimeError(f"git fetch failed: {res.stderr.strip()[-400:]}")
    res = git(["rev-parse", "--short=12", f"origin/{cfg['branch']}"], clone)
    return res.stdout.strip()


def checkout_upstream(cfg: dict) -> str:
    clone = ensure_clone(cfg)
    res = git(["reset", "--hard", f"origin/{cfg['branch']}"], clone)
    if res.returncode != 0:
        raise RuntimeError(f"git reset failed: {res.stderr.strip()[-400:]}")
    return git(["rev-parse", "--short=12", "HEAD"], clone).stdout.strip()


def build_from_clone(cfg: dict) -> Path:
    clone = Path(cfg["clone_dir"])
    argv = [cfg["python"], str(clone / "scripts" / "package_chrome_extension.py")]
    if cfg.get("no_vectors"):
        argv.append("--no-vectors")
    env = dict(os.environ)
    env.setdefault("MDBX_CORPUS", str(clone / "corpus"))
    # the clone's own index: built once, then reused (vectors need Ollama; keyword-only otherwise)
    db = clone / "data" / "mdbx.sqlite"
    env.setdefault("MDBX_DB", str(db))
    if not db.exists():
        log("building the clone's search index (first run)")
        idx = subprocess.run([cfg["python"], "-m", "mdbx.cli", "index"], cwd=str(clone), env=env,
                             capture_output=True, text=True, timeout=3600, check=False)
        if idx.returncode not in (0, 1):  # 1 = keyword index built, Ollama absent
            raise RuntimeError(f"mdbx index failed: {(idx.stderr or idx.stdout).strip()[-400:]}")
    log("packaging the extension from the clone")
    res = subprocess.run(argv, cwd=str(clone), env=env, capture_output=True, text=True, timeout=1800, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"package script failed: {(res.stderr or res.stdout).strip()[-600:]}")
    log(res.stdout.strip().splitlines()[-1] if res.stdout.strip() else "packaged")
    return clone / "editors" / "chrome"


# ---- release source ----
def release_commit(cfg: dict) -> str:
    """Commit recorded in the CI release's build.json (downloaded to a temp dir)."""
    with tempfile.TemporaryDirectory(prefix="mdbx-rel-") as tmp:
        res = subprocess.run(["gh", "release", "download", RELEASE_TAG, "--repo", repo_slug(cfg["repo"]),
                              "--pattern", "build.json", "--dir", tmp, "--clobber"],
                             capture_output=True, text=True, timeout=120, check=False)
        if res.returncode != 0:
            raise RuntimeError(f"gh release download failed: {res.stderr.strip()[-300:]}")
        stamp = json.loads(Path(tmp, "build.json").read_text(encoding="utf-8"))
    return str(stamp.get("commit") or "")


def download_release(cfg: dict, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(["gh", "release", "download", RELEASE_TAG, "--repo", repo_slug(cfg["repo"]),
                          "--pattern", RELEASE_ASSET, "--dir", str(dest), "--clobber"],
                         capture_output=True, text=True, timeout=600, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"gh release download failed: {res.stderr.strip()[-300:]}")
    unpacked = dest / "unpacked"
    if unpacked.exists():
        shutil.rmtree(unpacked)
    with zipfile.ZipFile(dest / RELEASE_ASSET) as z:
        z.extractall(unpacked)
    return unpacked


def repo_slug(url: str) -> str:
    u = url.strip()
    u = u.removesuffix(".git")
    if u.startswith("git@github.com:"):
        return u.split(":", 1)[1]
    return "/".join(u.rstrip("/").split("/")[-2:])


# ---- install ----
def runtime_files(src: Path) -> list[Path]:
    files = [src / f for f in RUNTIME_FILES if (src / f).is_file()]
    for d, suffixes in RUNTIME_DIRS.items():
        if (src / d).is_dir():
            files += sorted(p for p in (src / d).iterdir() if p.suffix in suffixes and p.is_file())
    return files


def sync_runtime(src: Path, install_dir: Path) -> int:
    """Copy the runtime files into ``install_dir`` atomically (build next to it, then swap)."""
    install_dir = Path(install_dir)
    files = runtime_files(src)
    if not any(f.name == "manifest.json" for f in files):
        raise RuntimeError(f"no manifest.json under {src}")
    staging = install_dir.with_name(install_dir.name + ".new")
    backup = install_dir.with_name(install_dir.name + ".old")
    for d in (staging, backup):
        if d.exists():
            shutil.rmtree(d)
    staging.mkdir(parents=True)
    for f in files:
        rel = f.relative_to(src)
        (staging / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, staging / rel)
    if install_dir.exists():
        os.rename(install_dir, backup)
    os.rename(staging, install_dir)
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    return len(files)


def run_update(cfg: dict, *, force: bool = False) -> int:
    install_dir = Path(cfg["install_dir"])
    installed = read_stamp(install_dir)
    if cfg["source"] == "release":
        target = release_commit(cfg)
    else:
        target = upstream_commit(cfg)
    if not needs_update(installed, target, force=force):
        log(f"up to date: {build_id(installed) or '(no stamp)'} == origin {target}")
        return 0
    log(f"update: installed {build_id(installed) or '(none)'} → {target} via {cfg['source']}")
    if cfg["source"] == "release":
        with tempfile.TemporaryDirectory(prefix="mdbx-rel-") as tmp:
            src = download_release(cfg, Path(tmp))
            n = sync_runtime(src, install_dir)
    else:
        checkout_upstream(cfg)
        src = build_from_clone(cfg)
        n = sync_runtime(src, install_dir)
    log(f"installed {n} files into {install_dir}; build {build_id(read_stamp(install_dir))}")
    return 0


# ---- launchd ----
def agent_plist(cfg: dict, script: Path | None = None) -> dict:
    script = script or Path(__file__).resolve()
    return {
        "Label": AGENT_LABEL,
        "ProgramArguments": [cfg["python"], str(script), "run"],
        "StartInterval": int(cfg["interval_min"]) * 60,
        "RunAtLoad": True,
        "StandardOutPath": str(LOG_PATH),
        "StandardErrorPath": str(LOG_PATH),
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
                                 "HOME": str(HOME), "MDBX_AUTOUPDATE_CONFIG": str(CONFIG_PATH)},
    }


def install_agent(cfg: dict) -> int:
    if sys.platform != "darwin":
        print("install-agent needs macOS launchd; on other systems run `run` from cron", file=sys.stderr)
        return 2
    save_config(cfg)
    AGENT_PLIST.parent.mkdir(parents=True, exist_ok=True)
    with open(AGENT_PLIST, "wb") as fh:
        plistlib.dump(agent_plist(cfg), fh)
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(AGENT_PLIST)], capture_output=True, check=False)
    res = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(AGENT_PLIST)], capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(f"launchctl bootstrap failed: {res.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"agent installed: {AGENT_PLIST} (every {cfg['interval_min']} min, source={cfg['source']})")
    print(f"config:          {CONFIG_PATH}")
    print(f"log:             {LOG_PATH}")
    print(f"extension dir:   {cfg['install_dir']}")
    print("Running the first update now…")
    try:
        run_update(cfg, force=not Path(cfg["install_dir"]).exists())
    except RuntimeError as exc:
        print(f"first update failed: {exc}", file=sys.stderr)
        return 1
    print(f"\nIn Chrome: chrome://extensions → Developer mode → Load unpacked → {cfg['install_dir']}")
    print("Later pushes to GitHub reach the extension automatically (agent ≤ interval, reload ≤ 5 min).")
    return 0


def uninstall_agent() -> int:
    if AGENT_PLIST.exists():
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(AGENT_PLIST)], capture_output=True, check=False)
        AGENT_PLIST.unlink()
        print(f"removed {AGENT_PLIST}")
    else:
        print("agent not installed")
    return 0


def status(cfg: dict) -> int:
    installed = read_stamp(Path(cfg["install_dir"]))
    try:
        target = release_commit(cfg) if cfg["source"] == "release" else upstream_commit(cfg)
    except RuntimeError as exc:
        target = f"? ({exc})"
    agent = "installed" if AGENT_PLIST.exists() else "not installed"
    print(json.dumps({"install_dir": cfg["install_dir"], "installed_build": build_id(installed) or None,
                      "installed_version": installed.get("version"), "built_at": installed.get("built_at"),
                      "upstream": target, "source": cfg["source"], "repo": cfg["repo"], "branch": cfg["branch"],
                      "agent": agent, "interval_min": cfg["interval_min"], "log": str(LOG_PATH)}, indent=2))
    return 0 if installed and isinstance(target, str) and not needs_update(installed, target) else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", choices=["git", "release"])
    ap.add_argument("--repo", help="git URL (default: this checkout's origin)")
    ap.add_argument("--branch")
    ap.add_argument("--install-dir", dest="install_dir", type=Path, help=f"folder Chrome loads (default {DEFAULT_INSTALL_DIR})")
    ap.add_argument("--clone-dir", dest="clone_dir", type=Path)
    ap.add_argument("--python", help="interpreter with mdbx + numpy installed (default: this one)")
    ap.add_argument("--interval-min", dest="interval_min", type=int)
    ap.add_argument("--no-vectors", dest="no_vectors", action="store_const", const=True, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("install-agent", help="write the launchd agent, save settings, run the first update")
    sub.add_parser("uninstall-agent")
    sub.add_parser("status")
    r = sub.add_parser("run", help="one update pass")
    r.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    cfg = effective_config(a)
    try:
        if a.cmd == "install-agent":
            return install_agent(cfg)
        if a.cmd == "uninstall-agent":
            return uninstall_agent()
        if a.cmd == "status":
            return status(cfg)
        return run_update(cfg, force=a.force)
    except RuntimeError as exc:
        log(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
